package com.zenginby.kromis

import android.content.Context
import android.util.Log
import com.chaquo.python.Python
import java.io.File
import java.io.IOException

/**
 * `android_main` modülünün Kotlin tarafındaki tek kapısı.
 *
 * İki iş: (1) APK assets'indeki salt-okunur içeriği yazılabilir bir dizine
 * kopyalamak, (2) uvicorn'u başlatıp `(port, token)` çiftini tutmak.
 *
 * `@Synchronized`: MainActivity ile ServerService aynı anda başlatmaya
 * çalışabiliyor (Activity arka plan thread'inde, servis kendi yaşam
 * döngüsünde). Kilitsiz iki çağrı iki uvicorn örneği doğurabilirdi — WebView
 * birine bakarken üretim isteği ötekine giderdi. Python tarafı da ayrıca
 * fikir birliğinde: `android_main.start` ikinci çağrıda mevcut ucu döndürüyor.
 */
object PythonServer {

    data class Uc(val port: Int, val token: String) {
        val taban: String get() = "http://127.0.0.1:$port"
    }

    private const val ETIKET = "GIS"

    /** Assets içindeki kök; `paths.py` bunun kopyalanmış hâlini bekliyor. */
    private const val KAYNAK_KOKU = "resources"

    /** Kopyalamanın hangi sürüme ait olduğunu tutan damga dosyası. */
    private const val SURUM_DAMGASI = ".surum"

    @Volatile
    private var uc: Uc? = null

    fun mevcutUc(): Uc? = uc

    @Synchronized
    fun baslat(context: Context): Uc {
        uc?.let { return it }

        val uygulama = context.applicationContext
        val veriDizini = uygulama.filesDir
        val kaynakDizini = File(veriDizini, KAYNAK_KOKU)
        kaynaklariHazirla(uygulama, kaynakDizini)

        val sonuc = Python.getInstance()
            .getModule("android_main")
            .callAttr("start", veriDizini.absolutePath, kaynakDizini.absolutePath)

        val yeni = Uc(
            port = sonuc.callAttr("get", "port").toInt(),
            token = sonuc.callAttr("get", "token").toString(),
        )
        Log.i(ETIKET, "uvicorn hazır: port=${yeni.port}")
        uc = yeni
        return yeni
    }

    @Synchronized
    fun durdur() {
        if (uc == null) return
        try {
            Python.getInstance().getModule("android_main").callAttr("stop")
        } catch (e: Throwable) {
            // Kapanış yolunda fırlatmak süreci çökertir ve kullanıcı "uygulama
            // kapanırken çöktü" görür — teşhis için log yeter.
            Log.w(ETIKET, "sunucu düzgün kapatılamadı", e)
        }
        uc = null
    }

    /**
     * `static/` ve `bundled/` içeriğini assets'ten yazılabilir dizine kopyalar.
     *
     * NEDEN KOPYA: `app.py` hem `StaticFiles(directory=…)` hem `FileResponse`
     * ile GERÇEK bir dosya sistemi yolu istiyor. Android'in asset yöneticisi
     * yalnız akış veriyor, yol vermiyor — yani assets'i doğrudan sunmanın yolu
     * yok. (Alternatif, `app.py`'yi asset okuyacak biçimde değiştirmekti;
     * reddedildi: masaüstünü ilgilendirmeyen bir kaygıyı ürün koduna sokardı.)
     *
     * NEDEN SÜRÜM DAMGASI: damgasız bir kopyalama ya her açılışta tekrarlanır
     * (gereksiz saniyeler) ya da hiç tekrarlanmaz — ikincisi güncellemeden
     * sonra BAYAT `static/` bırakır ve kullanıcı yeni sürümü eski arayüzle
     * kullanır. Aynı sınıf hata `version.py`'deki cache-buster kuralının da
     * doğuş sebebi.
     */
    private fun kaynaklariHazirla(context: Context, hedef: File) {
        val damga = File(hedef, SURUM_DAMGASI)
        val beklenen = BuildConfig.VERSION_NAME

        if (damga.isFile && runCatching { damga.readText() }.getOrNull() == beklenen) {
            return
        }

        // Ağaç ÜZERİNE yazılmıyor, önce siliniyor: bir sürümde kaldırılan dosya
        // (ör. artık kullanılmayan bir JS) üzerine yazmayla yerinde kalırdı ve
        // eski kod yeni arayüzün yanında yaşamayı sürdürürdü.
        hedef.deleteRecursively()
        if (!hedef.mkdirs() && !hedef.isDirectory) {
            throw IOException("kaynak dizini oluşturulamadı: $hedef")
        }
        kopyala(context, KAYNAK_KOKU, hedef)
        damga.writeText(beklenen)
        Log.i(ETIKET, "kaynaklar açıldı ($beklenen): $hedef")
    }

    private fun kopyala(context: Context, assetYolu: String, hedef: File) {
        val cocuklar = try {
            context.assets.list(assetYolu) ?: emptyArray()
        } catch (e: IOException) {
            emptyArray()
        }

        // `list()` bir DOSYA için boş dizi döndürüyor — özyinelemenin yaprağı bu.
        if (cocuklar.isEmpty()) {
            hedef.parentFile?.mkdirs()
            context.assets.open(assetYolu).use { girdi ->
                hedef.outputStream().use { cikti -> girdi.copyTo(cikti) }
            }
            return
        }

        hedef.mkdirs()
        for (ad in cocuklar) {
            kopyala(context, "$assetYolu/$ad", File(hedef, ad))
        }
    }
}
