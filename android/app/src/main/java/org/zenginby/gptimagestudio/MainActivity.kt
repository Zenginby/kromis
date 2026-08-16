package org.zenginby.gptimagestudio

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.URLUtil
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import java.io.File
import kotlin.concurrent.thread

/**
 * Uygulamanın tek penceresi: yerel sunucuyu WebView'de gösterir.
 *
 * `desktop.py`'nin pywebview penceresinin karşılığı, ama üç ek işi var —
 * üçü de Android'e özgü ve üçü de olmadan bir özellik SESSİZCE kayboluyor:
 *
 *   1. **Oturum çerezi.** 127.0.0.1 Android'de cihazdaki her uygulamaya açık
 *      ve `app.py`'de kimlik denetimi yok. Çerez sayfa YÜKLENMEDEN yazılıyor,
 *      böylece ilk istek de token'ı taşıyor.
 *   2. **Dosya seçici.** `<input type="file">` WebView'de VARSAYILAN OLARAK
 *      ÇALIŞMAZ; `onShowFileChooser` uygulanmazsa görsel içe aktarma, referans
 *      görsel ekleme ve logo/banner yükleme düğmeleri hiçbir şey yapmaz.
 *   3. **İndirme.** WebView `<a download>`'u kendiliğinden indirmez;
 *      `DownloadListener` olmadan PNG indirme ve klasör ZIP'i sessizce ölür.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var perde: View
    private lateinit var perdeBaslik: TextView

    private var dosyaSecimGeriCagri: ValueCallback<Array<Uri>>? = null
    private lateinit var dosyaSecici: ActivityResultLauncher<Intent>
    private lateinit var bildirimIzni: ActivityResultLauncher<String>
    private lateinit var depolamaIzni: ActivityResultLauncher<String>

    /** İzin istenirken bekleyen indirme; izin verilince buradan sürüyor. */
    private var bekleyenIndirme: Downloader.Istek? = null

    private var uc: PythonServer.Uc? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        perde = findViewById(R.id.perde)
        perdeBaslik = findViewById(R.id.perde_baslik)

        // Launcher kayıtları onCreate'te ve KOŞULSUZ: Activity yeniden
        // yaratıldığında da aynı sırada kaydedilmeleri gerekiyor, aksi halde
        // ActivityResult altyapısı sonucu eşleştiremez.
        dosyaSecici = registerForActivityResult(
            ActivityResultContracts.StartActivityForResult()
        ) { sonuc ->
            // İPTAL DE BİLDİRİLMEK ZORUNDA: geri çağrı `null` ile bile olsa
            // çağrılmazsa o <input type="file"> bir daha HİÇ açılmaz — kullanıcı
            // için "düğme bozuldu" demek.
            dosyaSecimGeriCagri?.onReceiveValue(
                WebChromeClient.FileChooserParams.parseResult(sonuc.resultCode, sonuc.data)
            )
            dosyaSecimGeriCagri = null
        }

        bildirimIzni = registerForActivityResult(
            ActivityResultContracts.RequestPermission()
        ) { /* Reddedilse de akış sürüyor: bildirim yoksa yalnız görünürlük kaybı. */ }

        depolamaIzni = registerForActivityResult(
            ActivityResultContracts.RequestPermission()
        ) { verildi ->
            val istek = bekleyenIndirme
            bekleyenIndirme = null
            if (verildi && istek != null) {
                indirmeyiBaslat(istek)
            } else if (!verildi) {
                bildir(getString(R.string.depolama_izni_gerekli))
            }
        }

        webViewiKur()
        bildirimIzniniIste()
        sunucuyuBaslat()
    }

    // ── Sunucu ──────────────────────────────────────────────────────

    private fun sunucuyuBaslat() {
        // ARKA PLAN THREAD'İ ŞART: ilk açılışta Chaquopy stdlib'i açıyor ve
        // assets kopyalanıyor (2–5 sn). Ana thread'de yapılsaydı sistem ANR
        // diyaloğunu gösterirdi.
        thread(name = "gis-baslatici") {
            try {
                val yeniUc = PythonServer.baslat(this)
                runOnUiThread { sunucuHazir(yeniUc) }
            } catch (e: Throwable) {
                runOnUiThread { acilisHatasi(e) }
            }
        }
    }

    private fun sunucuHazir(yeniUc: PythonServer.Uc) {
        uc = yeniUc
        // Servis sunucu AYAKTAYKEN başlatılıyor: bildirim "çalışıyor" derken
        // arkasında gerçekten çalışan bir sunucu olsun.
        ServerService.baslat(this)
        cereziYaz(yeniUc)
        webView.loadUrl(yeniUc.taban)
    }

    /**
     * Oturum çerezini WebView'in çerez deposuna yazar — sayfa YÜKLENMEDEN ÖNCE.
     *
     * `HttpOnly`: JS'in token'ı okumasına gerek yok (27 fetch çağrısı da göreli,
     * çerez kendiliğinden gidiyor) ve okuyamaması, arayüze sızan herhangi bir
     * üçüncü taraf içeriğin token'ı çalmasını engelliyor.
     *
     * `SameSite=Lax`, `Strict` DEĞİL: `<a download>` tıklaması bir GEZİNME
     * sayılıyor ve Strict altında ilk isteğe çerez eklenmeyebilir — indirme
     * 403 dönerdi. Lax bu gezinmeye izin verirken çapraz site POST'larını yine
     * kesiyor (zaten çapraz site bir bağlam da yok).
     *
     * Port YAZILMIYOR: çerezler porta göre ayrılmaz, `http://127.0.0.1` alanı
     * yeterli — üstelik port her açılışta değişiyor (port=0).
     */
    private fun cereziYaz(hedef: PythonServer.Uc) {
        val yonetici = CookieManager.getInstance()
        yonetici.setAcceptCookie(true)
        yonetici.setAcceptThirdPartyCookies(webView, false)
        yonetici.setCookie(
            "http://127.0.0.1",
            "${OTURUM_CEREZI}=${hedef.token}; Path=/; HttpOnly; SameSite=Lax",
        )
        yonetici.flush()
    }

    /**
     * Açılış hatası kullanıcıya GÖRÜNÜR olmalı.
     *
     * Masaüstündeki `desktop.main()` ile aynı gerekçe: `--windowed` pakette
     * stderr yok, Android'de ise kullanıcının logcat'e hiç erişimi yok. Uyarı
     * olmasaydı ekranda yalnız sonsuza kadar dönen bir çember kalırdı.
     */
    private fun acilisHatasi(hata: Throwable) {
        val kayit = File(filesDir, "hata.log").absolutePath
        perdeBaslik.text = getString(R.string.sunucu_baslatilamadi)
        AlertDialog.Builder(this)
            .setTitle(R.string.sunucu_baslatilamadi)
            .setMessage(
                getString(R.string.sunucu_baslatilamadi_detay, kayit) +
                    "\n\n" + (hata.message ?: hata.javaClass.simpleName)
            )
            .setCancelable(false)
            .setPositiveButton(R.string.cikis) { _, _ -> finish() }
            .show()
    }

    // ── WebView ─────────────────────────────────────────────────────

    @SuppressLint("SetJavaScriptEnabled")
    private fun webViewiKur() {
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            // file:// ve content:// erişimi KAPALI: arayüzün tamamı
            // http://127.0.0.1 üzerinden geliyor, yerel dosya okumaya hiç
            // ihtiyacı yok. Açık bırakmak, bir gün araya giren herhangi bir
            // içeriğe uygulamanın özel dizinini okuma yolu açardı.
            allowFileAccess = false
            allowContentAccess = false
            // WebView'in KENDİ sayfa yakınlaştırması kapalı. Büyüteçteki
            // yakınlaştırma viewer.js'in işi (iki parmak + −/+ düğmeleri) ve
            // ikisi açık kalsaydı aynı hareket hem sayfayı hem görseli
            // ölçekler, kullanıcı da düzeni bozulmuş bir arayüzde kalırdı.
            setSupportZoom(false)
            builtInZoomControls = false
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView, request: WebResourceRequest,
            ): Boolean {
                val adres = request.url
                // Uygulamanın kendi sunucusu WebView'de kalır; DIŞ bağlantılar
                // (yardım linki, mailto) tarayıcıya/eposta uygulamasına gider.
                // Aksi halde dış bir sayfa uygulamanın İÇİNDE açılır ve
                // kullanıcı geri dönemez.
                if (adres.host == "127.0.0.1" || adres.host == "localhost") return false
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, adres))
                    true
                } catch (e: ActivityNotFoundException) {
                    true  // Açacak uygulama yoksa hiçbir şey yapma; çökme.
                }
            }

            override fun onPageFinished(view: WebView, url: String) {
                // Perde ancak arayüz GERÇEKTEN çizildiğinde kalkıyor. Sunucu
                // hazır olur olmaz kaldırılsaydı kullanıcı bir an boş beyaz
                // bir WebView görürdü.
                perde.visibility = View.GONE
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView,
                geriCagri: ValueCallback<Array<Uri>>,
                parametreler: FileChooserParams,
            ): Boolean {
                // Önceki seçim yarıda kaldıysa onu kapat — iki bekleyen geri
                // çağrı WebView'i kalıcı olarak kilitler.
                dosyaSecimGeriCagri?.onReceiveValue(null)
                dosyaSecimGeriCagri = geriCagri
                return try {
                    // `createIntent()` sayfadaki `accept` ve `multiple`
                    // niteliklerini intent'e çeviriyor — üç <input type="file">
                    // alanının MIME listesi böylece seçiciye taşınıyor.
                    dosyaSecici.launch(parametreler.createIntent())
                    true
                } catch (e: ActivityNotFoundException) {
                    dosyaSecimGeriCagri = null
                    geriCagri.onReceiveValue(null)
                    false
                }
            }
        }

        webView.setDownloadListener { url, _, contentDisposition, mimeTur, _ ->
            val ad = URLUtil.guessFileName(url, contentDisposition, mimeTur)
            indirmeyiIste(Downloader.Istek(url, ad, mimeTur ?: "application/octet-stream"))
        }
    }

    // ── İndirme ─────────────────────────────────────────────────────

    private fun indirmeyiIste(istek: Downloader.Istek) {
        if (Downloader.izinGerekiyorMu(this)) {
            bekleyenIndirme = istek
            depolamaIzni.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
            return
        }
        indirmeyiBaslat(istek)
    }

    private fun indirmeyiBaslat(istek: Downloader.Istek) {
        bildir(getString(R.string.indiriliyor, istek.dosyaAdi))
        val cerez = CookieManager.getInstance().getCookie(uc?.taban ?: "http://127.0.0.1")
        Downloader.kaydet(this, istek, cerez) { sonuc ->
            when (sonuc) {
                is Downloader.Sonuc.Basarili ->
                    bildir(getString(R.string.indirildi, sonuc.dosyaAdi))
                is Downloader.Sonuc.Hatali ->
                    bildir(getString(R.string.indirilemedi, sonuc.mesaj))
                Downloader.Sonuc.IzinGerekli ->
                    bildir(getString(R.string.depolama_izni_gerekli))
            }
        }
    }

    // ── İzinler ─────────────────────────────────────────────────────

    private fun bildirimIzniniIste() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            bildirimIzni.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    // ── Geri tuşu ───────────────────────────────────────────────────

    /**
     * Geri tuşu ÖNCE arayüzdeki katmanı kapatır, sonra uygulamadan çıkar.
     *
     * `webView.canGoBack()` KULLANILMIYOR: bu tek sayfalık bir uygulama, modal
     * ve paneller gezinme geçmişine hiç girmiyor — yani geçmişe bakan bir geri
     * tuşu, üstünde açık bir panel varken doğrudan uygulamayı kapatırdı.
     *
     * Kapatma işini frontend'in KENDİ `Escape` şelalesi yapıyor
     * (core.js:134/151/743, folders.js:616/1013, assets.js:501, viewer.js:266).
     * O şelale hangi katmanın önce kapanacağını `stopImmediatePropagation` ile
     * zaten çözüyor; burada ikinci bir öncelik sırası kurmak iki mantığın
     * ayrışmasına ve "geri bazen yanlış paneli kapatıyor" hatasına açık olurdu.
     */
    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (perde.visibility == View.VISIBLE) {
            sistemGerisi()
            return
        }
        webView.evaluateJavascript(GERI_TUSU_JS) { sonuc ->
            // `evaluateJavascript` sonucu JSON olarak veriyor: boolean'lar
            // tırnaksız "true"/"false" dizeleri olarak geliyor.
            if (sonuc != "true") sistemGerisi()
        }
    }

    /**
     * `super.onBackPressed()`i ayrı bir üyeye çıkarmak ŞART, üslup tercihi değil:
     * Kotlin `super` çağrısına lambda içinden izin vermiyor ve yukarıdaki
     * `evaluateJavascript` geri çağrısı bir lambda.
     */
    @Suppress("DEPRECATION")
    private fun sistemGerisi() {
        super.onBackPressed()
    }

    // ── Yaşam döngüsü ───────────────────────────────────────────────

    override fun onDestroy() {
        // Sunucu YALNIZCA kullanıcı uygulamayı gerçekten kapattığında duruyor.
        // `isFinishing` kontrolü olmadan bir yapılandırma değişikliği (tema,
        // yazı tipi ölçeği) sunucuyu düşürür ve süren üretim kaybolurdu.
        if (isFinishing) {
            ServerService.durdur(this)
        }
        dosyaSecimGeriCagri?.onReceiveValue(null)
        dosyaSecimGeriCagri = null
        super.onDestroy()
    }

    private fun bildir(metin: String) {
        Toast.makeText(this, metin, Toast.LENGTH_SHORT).show()
    }

    companion object {
        /** `android_main.SESSION_COOKIE` ile AYNI olmak zorunda. */
        private const val OTURUM_CEREZI = "gis_session"

        /**
         * Açık bir katman varsa `Escape` gönderir ve "true" döner.
         *
         * Seçiciler index.html'deki yapıya bağlı: `.sheet.open` (5 panel),
         * `.modal:not([hidden])` (confirm/logo/media-picker/viewer),
         * `.popover:not([hidden])` (artı menüsü).
         */
        private const val GERI_TUSU_JS = """
            (function () {
              var acik = document.querySelector('.sheet.open')
                      || document.querySelector('.modal:not([hidden])')
                      || document.querySelector('.popover:not([hidden])');
              if (!acik) return false;
              document.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'Escape', bubbles: true, cancelable: true
              }));
              return true;
            })();
        """
    }
}
