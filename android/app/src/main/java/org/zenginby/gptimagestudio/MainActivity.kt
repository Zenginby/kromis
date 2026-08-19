package org.zenginby.gptimagestudio

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.view.View
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
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
import java.net.URL
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
 *   3. **İndirme.** WebView'in indirme sistemi YOK: bir indirmeyi tanır tanımaz
 *      iptal ediyor. Uygulama devralmazsa PNG indirme ve klasör ZIP'i sessizce
 *      ölür. Devralmanın İKİ yolu var ve ikisi de burada — sayfanın doğrudan
 *      çağırdığı `IndirmeKoprusu` (asıl yol) ve `DownloadListener` (yedek).
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

    /** Açılış hatası diyaloğu bir kez gösterilsin (bkz. `acilisHatasi`). */
    private var acilisHatasiGosterildi = false

    private var uc: PythonServer.Uc? = null

    /**
     * Son geri basışının anı (`SystemClock.elapsedRealtime`); 0 = hiç basılmadı.
     * `cikisiOnayla` bunun üstünde "bir daha bas" penceresini ölçüyor.
     */
    private var sonGeriAni = 0L

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
     * `SameSite=Lax`, `Strict` DEĞİL: indirme ve `<a download>` istekleri
     * gezinme sınıfında değerlendiriliyor ve Strict altında çerezin ilk isteğe
     * eklenmemesi mümkün — indirme 403 dönerdi. Lax bunlara izin verirken
     * çapraz site POST'larını yine kesiyor (zaten çapraz site bir bağlam da
     * yok). İndirmenin ASIL yolu artık `IndirmeKoprusu` ve orada çerez elle
     * konuyor, ama yedek yol hâlâ tarayıcının çerezine bağlı.
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
        acilisHatasi(hata.message ?: hata.javaClass.simpleName)
    }

    /**
     * İki çağrı yolu var — sunucu HİÇ başlamadı (`sunucuyuBaslat`'ın yakalama
     * dalı) ve sunucu başladı ama arayüz yüklenemedi (`WebViewClient`'ın hata
     * geri çağrıları). Kullanıcı açısından ikisi de aynı: uygulama açılmadı.
     *
     * `acilisHatasiGosterildi` muhafızı: tek bir başarısız yükleme hem
     * `onReceivedError` hem `onReceivedHttpError` tetikleyebiliyor ve üst üste
     * iki diyalog, ilkini okunamadan gömerdi.
     */
    private fun acilisHatasi(detay: String) {
        if (acilisHatasiGosterildi) return
        acilisHatasiGosterildi = true

        val kayit = File(filesDir, "hata.log").absolutePath
        perde.visibility = View.VISIBLE
        perdeBaslik.text = getString(R.string.sunucu_baslatilamadi)
        AlertDialog.Builder(this)
            .setTitle(R.string.sunucu_baslatilamadi)
            .setMessage(getString(R.string.sunucu_baslatilamadi_detay, kayit) + "\n\n" + detay)
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
                //
                // Hata varsa perde KALIYOR: `onPageFinished` başarısız bir
                // yüklemeden sonra da çağrılıyor ve perdeyi koşulsuz kaldırmak,
                // kullanıcıyı açıklamasız boş bir WebView'de bırakırdı.
                if (!acilisHatasiGosterildi) perde.visibility = View.GONE
            }

            /**
             * Ağ düzeyi hata (bağlantı kurulamadı, sunucu düştü).
             *
             * `isForMainFrame` SÜZGECİ ŞART: bir görselin ya da JS dosyasının
             * tek başına başarısız olması uygulamayı açılamaz yapmaz, ama bu
             * geri çağrı onlar için de tetikleniyor — süzgeçsiz bir uyarı,
             * çalışan bir uygulamada yanlış alarm verirdi.
             */
            override fun onReceivedError(
                view: WebView, request: WebResourceRequest, error: WebResourceError,
            ) {
                if (!request.isForMainFrame) return
                acilisHatasi(getString(R.string.arayuz_yuklenemedi_detay, error.description))
            }

            /**
             * HTTP düzeyi hata — asıl beklenen durum 403.
             *
             * Sunucu AYAKTA ama oturum kapısı isteği reddetti (bkz.
             * `android_main.SessionCookieGuard`): çerez bayatlamış ya da hiç
             * yazılamamış olabilir. `PythonServer.baslat` fırlatmadığı için
             * `sunucuyuBaslat`'ın yakalama dalı bu durumu HİÇ görmüyordu.
             */
            override fun onReceivedHttpError(
                view: WebView, request: WebResourceRequest,
                errorResponse: WebResourceResponse,
            ) {
                if (!request.isForMainFrame) return
                acilisHatasi(
                    getString(R.string.arayuz_yuklenemedi_detay,
                        "HTTP ${errorResponse.statusCode}")
                )
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

        // KÖPRÜ `loadUrl`den ÖNCE takılmak zorunda: enjeksiyon sayfa yüklenirken
        // yapılıyor, sonradan eklenen bir arayüz ancak bir sonraki yüklemede
        // görünür — yani ilk oturumda indirme yine sessizce ölürdü.
        webView.addJavascriptInterface(IndirmeKoprusu(), KOPRU_ADI)

        // YEDEK YOL. Sayfanın kendi indirmeleri köprüden geçiyor; buraya yalnız
        // BİZİM başlatmadığımız indirmeler düşüyor (uzun basıp "bağlantıyı
        // kaydet"). Adı burada tahmin etmekten başka çare yok, o yüzden
        // `guessFileName` yalnız bu dalda kaldı.
        webView.setDownloadListener { url, _, contentDisposition, mimeTur, _ ->
            val ad = URLUtil.guessFileName(url, contentDisposition, mimeTur)
            indirmeyiIste(Downloader.Istek(url, ad, mimeTur ?: "application/octet-stream"))
        }
    }

    // ── İndirme ─────────────────────────────────────────────────────

    /**
     * Sayfanın doğrudan çağırdığı indirme kapısı (`core.js` `downloadViaAnchor`).
     *
     * NEDEN ASIL YOL BU, `DownloadListener` değil: `<a download>` tıklaması
     * Chromium'da bir gezinme DEĞİL, "renderer kaynaklı indirme" üretiyor.
     * WebView'in indirme sistemi hiç yok — isteği tanır tanımaz iptal edip olayı
     * `AwDownloadManagerDelegate` üzerinden uygulamaya devrediyor. O zincirin
     * herhangi bir halkası kopunca (WebView sürümü, OEM yaması, `WebContents`
     * eşleşmemesi) hiçbir hata çıkmıyor: tıklama SESSİZCE hiçbir şey yapmıyor.
     * Telefonda "indirme çalışmıyor"un tarifi buydu ve tek bir başlık eklemek
     * onu kapatmıyor — zincirin kendisi çıkarılmak zorundaydı.
     *
     * GÜVENLİK. `addJavascriptInterface` bu nesneyi WebView'deki HER sayfaya
     * açıyor, o yüzden yüzey bilerek TEK bir çağrıya indirildi ve
     * `koprudenIndir` adresi KENDİ sunucumuza çiviliyor. Bu WebView'e yabancı
     * içerik zaten hiç girmiyor (dış bağlantılar `shouldOverrideUrlLoading` ile
     * tarayıcıya çıkıyor); çivi, o kuralın bir gün gevşemesine karşı duran
     * ikinci kapı — `Downloader`ın çerezi yalnız loopback'e vermesiyle aynı
     * disiplin.
     */
    private inner class IndirmeKoprusu {
        /**
         * `@JavascriptInterface` ŞART (API 17+): işaretsiz bir yöntem JS'ten
         * hiç görünmez — yani köprü sessizce yok sayılırdı.
         *
         * Gövde ANA THREAD'e taşınıyor: bu çağrı WebView'in "JavaBridge"
         * thread'inde geliyor ve hem `Toast` hem izin isteği ana thread ister.
         */
        @JavascriptInterface
        fun indir(adres: String, dosyaAdi: String) {
            runOnUiThread { koprudenIndir(adres, dosyaAdi) }
        }
    }

    /**
     * Köprüden gelen isteği doğrular ve indirmeye verir.
     *
     * Adres KENDİ sunucumuzu göstermek zorunda: host + port birlikte
     * denetleniyor. Yalnız host yetmezdi — cihazdaki başka bir yerel sunucuyu
     * (127.0.0.1:başka_port) uygulamanın galerisine yazdırmanın yolu açık
     * kalırdı.
     *
     * Dosya adı `guvenliAd`den geçiyor: adı artık frontend veriyor ve klasör
     * ZIP'inde o ad KULLANICI metni (`<klasör adı>.zip`), yani içinde yol
     * ayırıcı olabilir.
     */
    private fun koprudenIndir(adres: String, dosyaAdi: String) {
        val sunucu = uc ?: return
        val hedef = runCatching { URL(adres) }.getOrNull() ?: return
        val yerel = hedef.protocol == "http" &&
            (hedef.host == "127.0.0.1" || hedef.host == "localhost") &&
            hedef.port == sunucu.port
        if (!yerel) {
            // Sessiz dönmüyor: yabancı bir adres bir kusurun işareti ve
            // kullanıcı en azından indirmenin OLMADIĞINI bilmeli.
            bildir(getString(R.string.indirilemedi, hedef.host ?: adres))
            return
        }
        val ad = Downloader.guvenliAd(dosyaAdi, adres)
        indirmeyiIste(Downloader.Istek(adres, ad, Downloader.mimeTuru(ad)))
    }

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
     * Geri tuşu ÖNCE arayüzde geri gider, sonra UYARIR, ancak ikinci basışta çıkar.
     *
     * Sıralamanın tamamı frontend'de (`window.geriTusu`, core.js): açık katmanı
     * kapat → klasörden bir üste çık → Stüdyo'ya dön → `false`. Buraya taşınmadan
     * önce sıralama bu dosyadaki üç CSS seçicisiydi ve iki şey kırılıyordu:
     * sohbet menüleri hiçbirine uymuyordu, bölüm/klasör gezintisi ise geri
     * yığınında hiç yoktu — Medya'dayken geri DOĞRUDAN uygulamayı kapatıyordu.
     * Kotlin artık DOM yapısını hiç bilmiyor.
     *
     * `webView.canGoBack()` hâlâ KULLANILMIYOR: bu tek sayfalık bir uygulama,
     * modal ve paneller gezinme geçmişine hiç girmiyor.
     */
    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (perde.visibility == View.VISIBLE) {
            // Açılış perdesi de aynı kapıdan geçiyor: Python çalışma zamanı 2–5 sn
            // açılırken yanlışlıkla çıkmak, kullanıcının en pahalıya ödediği hâli.
            cikisiOnayla()
            return
        }
        webView.evaluateJavascript(GERI_TUSU_JS) { sonuc ->
            // `evaluateJavascript` sonucu JSON olarak veriyor: boolean'lar
            // tırnaksız "true"/"false" dizeleri olarak geliyor.
            if (sonuc != "true") cikisiOnayla()
        }
    }

    /**
     * `sistemGerisi()`ye giden TEK yol: ilk geri uyarır, ikincisi çıkarır.
     *
     * NEDEN VAR: arayüzde kapatılacak bir şey kalmadığında tek bir geri basışı
     * (ya da kenardan tek bir kaydırma) oturumu kapatıyordu — süren bir üretimin
     * ortasında bile. Jest gezinmesinde ekranın kenarına değmek kolay, yani
     * kazayla çıkmak sık ve bedeli yüksekti.
     *
     * `System.currentTimeMillis()` DEĞİL `SystemClock.elapsedRealtime()`: duvar
     * saati kullanıcı ya da ağ tarafından geriye alınabilir; o an fark negatife
     * düşer ve pencere bir daha hiç açılmaz — yani "iki kez bastım, çıkmıyor".
     * `elapsedRealtime` açılıştan beri monoton artıyor.
     */
    private fun cikisiOnayla() {
        val simdi = SystemClock.elapsedRealtime()
        if (simdi - sonGeriAni < CIKIS_PENCERESI_MS) {
            sistemGerisi()
            return
        }
        sonGeriAni = simdi
        bildir(getString(R.string.cikmak_icin_tekrar_geri))
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
         * Köprünün JS'teki adı — `core.js` `androidKoprusu()` ile AYNI olmak
         * zorunda. Ayrışırsa hiçbir hata çıkmaz: `window.LumeoIndirme` tanımsız
         * kalır, frontend sessizce `<a download>` yoluna düşer ve indirme
         * telefonda yine ölür. Bekçisi `tests/test_mobile.py`.
         */
        private const val KOPRU_ADI = "LumeoIndirme"

        /**
         * Geri basışının uygulama İÇİNDE karşılığı varsa "true" döner.
         *
         * Sıralamanın tamamı frontend'de (`window.geriTusu`, core.js): açık
         * katmanı kapat → klasörden bir üste çık → Stüdyo'ya dön → "false".
         * Buraya arayüzün yapısına dair HİÇBİR bilgi yazılmıyor; eskiden üç CSS
         * seçicisi buradaydı ve index.html'e dizeyle bağlıydı — sohbet menüleri
         * hiçbirine uymadığı için menü açıkken geri uygulamayı kapatıyordu.
         *
         * `typeof` muhafızı: çok eski bir `filesDir/resources/` sürümünde
         * `geriTusu` tanımsız olabilir. O durumda davranış "hiçbir katman
         * kapanmaz"a düşüyor — çökme değil, iyileştirmenin yokluğu.
         */
        private const val GERI_TUSU_JS =
            """typeof window.geriTusu === "function" ? window.geriTusu() : false"""

        /**
         * "Çıkmak için tekrar geri gelin" uyarısının geçerlilik süresi.
         *
         * `Toast.LENGTH_SHORT` (~2 sn) ile AYNI ölçekte olmak zorunda: uyarı
         * ekrandayken ikinci basış çıkarıyor, uyarı söndükten sonraki basış
         * yeniden uyarıyor. Pencere daha uzun olsa uyarı sönmüş olduğu hâlde
         * "ikinci basış" sayılırdı — kullanıcı için sebepsiz bir çıkış.
         */
        private const val CIKIS_PENCERESI_MS = 2_000L
    }
}
