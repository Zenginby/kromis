package org.zenginby.gptimagestudio

import android.Manifest
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Log
import androidx.core.content.ContextCompat
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * WebView'in indirme isteklerini karşılar — PNG'ler ve klasör ZIP'leri.
 *
 * NEDEN SİSTEMİN `DownloadManager`'I KULLANILMIYOR: DownloadManager AYRI bir
 * süreçte (`com.android.providers.downloads`) çalışıyor. Bizim sunucumuz
 * 127.0.0.1'de düz HTTP konuşuyor ve o sürece bizim
 * `network_security_config.xml`'imiz UYGULANMIYOR — yani indirmenin çalışıp
 * çalışmayacağı başka bir uygulamanın yapılandırmasına kalırdı. Üstelik
 * oturum çerezini o sürece elden vermek, anahtarı koruyan kapıyı gevşetmek
 * demek. Kendi indiricimiz her iki sorunu da ortadan kaldırıyor.
 *
 * Frontend'in indirme yollarının HEPSİ buraya düşüyor: `core.js:290`
 * `SUPPORTS_SAVE_PICKER` Android WebView'de `false` (File System Access API
 * yok), yani `downloadImage` de, klasör ZIP'i de `downloadViaAnchor`'a iniyor
 * ve `<a download>` DownloadListener'ı tetikliyor. Tek nokta, tek uygulama.
 */
object Downloader {

    private const val ETIKET = "GIS"
    private const val ALT_KLASOR = "GPT-Image Studio"

    private val havuz = Executors.newSingleThreadExecutor()
    private val anaThread = Handler(Looper.getMainLooper())

    data class Istek(val url: String, val dosyaAdi: String, val mimeTur: String)

    sealed interface Sonuc {
        data class Basarili(val dosyaAdi: String) : Sonuc
        data class Hatali(val mesaj: String) : Sonuc
        /** Android 8–9'da herkese açık dizine yazmak izin istiyor. */
        data object IzinGerekli : Sonuc
    }

    /** API 29'un altında herkese açık dizine yazmak için izin şart mı? */
    fun izinGerekiyorMu(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.Q &&
            ContextCompat.checkSelfPermission(
                context, Manifest.permission.WRITE_EXTERNAL_STORAGE,
            ) != PackageManager.PERMISSION_GRANTED

    fun kaydet(context: Context, istek: Istek, cerez: String?, geriCagri: (Sonuc) -> Unit) {
        if (izinGerekiyorMu(context)) {
            geriCagri(Sonuc.IzinGerekli)
            return
        }
        val uygulama = context.applicationContext
        havuz.execute {
            val sonuc = try {
                indir(uygulama, istek, cerez)
                Sonuc.Basarili(istek.dosyaAdi)
            } catch (e: Throwable) {
                Log.w(ETIKET, "indirme başarısız: ${istek.url}", e)
                Sonuc.Hatali(e.message ?: e.javaClass.simpleName)
            }
            anaThread.post { geriCagri(sonuc) }
        }
    }

    private fun indir(context: Context, istek: Istek, cerez: String?) {
        val baglanti = (URL(istek.url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 15_000
            // Klasör ZIP'i sunucuda bellekte üretiliyor ve yüzlerce görsel
            // içerebiliyor; okuma zaman aşımı buna göre cömert.
            readTimeout = 120_000
            // Oturum çerezi ŞART: android_main'deki kapı çerezsiz her isteği
            // 403 ile kesiyor — kendi indirmemiz de bu kuralın istisnası değil.
            if (!cerez.isNullOrBlank()) setRequestProperty("Cookie", cerez)
        }
        try {
            val kod = baglanti.responseCode
            if (kod != HttpURLConnection.HTTP_OK) {
                throw IllegalStateException("sunucu $kod")
            }
            baglanti.inputStream.use { girdi ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    yazMediaStore(context, istek) { cikti -> girdi.copyTo(cikti) }
                } else {
                    yazEskiSurum(context, istek) { cikti -> girdi.copyTo(cikti) }
                }
            }
        } finally {
            baglanti.disconnect()
        }
    }

    /**
     * Android 10+ (scoped storage): MediaStore'a yazılıyor, hiçbir izin yok.
     *
     * `IS_PENDING` ile yazılıyor: kopyalama yarıda kalırsa (bağlantı koptu,
     * süreç öldü) galeri yarım bir PNG göstermez — kayıt tamamlanana kadar
     * diğer uygulamalara görünmüyor.
     */
    private fun yazMediaStore(context: Context, istek: Istek, govde: (java.io.OutputStream) -> Unit) {
        val gorsel = istek.mimeTur.startsWith("image/")
        val koleksiyon = if (gorsel) {
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        } else {
            MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        }
        val klasor = if (gorsel) {
            "${Environment.DIRECTORY_PICTURES}/$ALT_KLASOR"
        } else {
            "${Environment.DIRECTORY_DOWNLOADS}/$ALT_KLASOR"
        }

        val degerler = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, istek.dosyaAdi)
            put(MediaStore.MediaColumns.MIME_TYPE, istek.mimeTur)
            put(MediaStore.MediaColumns.RELATIVE_PATH, klasor)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }

        val cozucu = context.contentResolver
        val uri = cozucu.insert(koleksiyon, degerler)
            ?: throw IllegalStateException("MediaStore kaydı açılamadı")
        try {
            cozucu.openOutputStream(uri)?.use(govde)
                ?: throw IllegalStateException("MediaStore akışı açılamadı")
            cozucu.update(uri, ContentValues().apply {
                put(MediaStore.MediaColumns.IS_PENDING, 0)
            }, null, null)
        } catch (e: Throwable) {
            // Yarım kayıt bırakma: silinmezse galeride 0 baytlık bir görsel kalır.
            runCatching { cozucu.delete(uri, null, null) }
            throw e
        }
    }

    /**
     * Android 8–9: MediaStore.Downloads henüz yok, herkese açık dizine doğrudan
     * yazılıyor (bu yüzden `WRITE_EXTERNAL_STORAGE` yalnız orada isteniyor).
     *
     * Bu dalın var olma sebebi minSdk 26; yalnız Android 10'a çivilenseydi tüm
     * dal ve izin kalkardı, ama Android 8–9 taşıyan cihazlar dışarıda kalırdı.
     */
    private fun yazEskiSurum(context: Context, istek: Istek, govde: (java.io.OutputStream) -> Unit) {
        val gorsel = istek.mimeTur.startsWith("image/")
        val kok = Environment.getExternalStoragePublicDirectory(
            if (gorsel) Environment.DIRECTORY_PICTURES else Environment.DIRECTORY_DOWNLOADS
        )
        val klasor = File(kok, ALT_KLASOR).apply { mkdirs() }
        val hedef = cakismasizAd(klasor, istek.dosyaAdi)

        hedef.outputStream().use(govde)
        // Galeri/dosya yöneticisi yeni dosyayı ancak taramadan sonra görüyor.
        MediaScannerConnection.scanFile(
            context, arrayOf(hedef.absolutePath), arrayOf(istek.mimeTur), null,
        )
    }

    /** `foo.png` doluysa `foo (1).png`. MediaStore bunu kendisi yapıyor, eski dal yapmıyor. */
    private fun cakismasizAd(klasor: File, ad: String): File {
        var aday = File(klasor, ad)
        if (!aday.exists()) return aday
        val nokta = ad.lastIndexOf('.')
        val govde = if (nokta > 0) ad.substring(0, nokta) else ad
        val uzanti = if (nokta > 0) ad.substring(nokta) else ""
        var sayac = 1
        while (aday.exists()) {
            aday = File(klasor, "$govde ($sayac)$uzanti")
            sayac++
        }
        return aday
    }
}
