package org.zenginby.gptimagestudio

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat

/**
 * uvicorn'u taşıyan süreci ön planda tutan servis.
 *
 * NEDEN ZORUNLU — bu servis olmadan uygulama "çalışıyor gibi görünüp para
 * yakar": `azure_client.READ_TIMEOUT_FIRST = 180 s` ve n=4 üretimde toplam
 * bekleme 180 + 3×120 = 540 saniyeye çıkıyor. Kullanıcı üretim sürerken ana
 * ekrana çıkarsa Android arka plandaki süreci öldürmekte serbesttir; istek
 * Azure'a gitmiş ve ÜCRETLENDİRİLMİŞ olduğu halde yanıt hiç işlenmez.
 * Kalıcı bildirim, sistemin süreci öldürmemesi için ödenen bedel.
 *
 * Servis sunucuyu KENDİSİ başlatmıyor; `PythonServer.baslat` idempotent ve onu
 * Activity zaten çağırıyor. Buradaki tek iş süreç önceliği ve bildirim —
 * sorumluluğu tek yerde tutmak, iki başlatıcının yarışmasından basit.
 */
class ServerService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        kanaliOlustur()
        // Tür AÇIKÇA veriliyor (dataSync). Android 14'ten itibaren tür
        // bildirmeyen bir startForeground çağrısı istisna fırlatıyor.
        ServiceCompat.startForeground(
            this, BILDIRIM_ID, bildirim(),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0,
        )
    }

    /**
     * START_NOT_STICKY, START_STICKY DEĞİL.
     *
     * Süreç öldürülmüşse uvicorn ve o an süren üretim zaten kaybolmuştur;
     * servisi Activity olmadan geri getirmek yalnızca "çalışıyor" diyen bir
     * bildirim gösterir — arkasında hiçbir şey olmadan. Yanlış bilgi veren bir
     * bildirim, hiç bildirim olmamasından kötü.
     */
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int =
        START_NOT_STICKY

    override fun onDestroy() {
        PythonServer.durdur()
        super.onDestroy()
    }

    private fun bildirim() = NotificationCompat.Builder(this, KANAL_ID)
        .setContentTitle(getString(R.string.bildirim_basligi))
        .setContentText(getString(R.string.bildirim_metni))
        .setSmallIcon(R.drawable.ic_bildirim)
        .setOngoing(true)
        // Bildirime dokunmak var olan Activity'yi öne getirsin, YENİSİNİ
        // açmasın: Activity `singleTask` ve yeni bir örnek WebView'i sıfırlar,
        // yani kullanıcının yazdığı prompt kaybolurdu.
        .setContentIntent(
            PendingIntent.getActivity(
                this, 0,
                Intent(this, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE,
            )
        )
        .setPriority(NotificationCompat.PRIORITY_LOW)
        .build()

    private fun kanaliOlustur() {
        // IMPORTANCE_LOW: bildirim görünsün ama ses çıkarmasın. Bu bildirim bir
        // haber değil, sürecin ayakta kalma bedeli.
        val kanal = NotificationChannel(
            KANAL_ID,
            getString(R.string.bildirim_kanali_adi),
            NotificationManager.IMPORTANCE_LOW,
        ).apply { description = getString(R.string.bildirim_kanali_aciklama) }

        getSystemService(NotificationManager::class.java).createNotificationChannel(kanal)
    }

    companion object {
        private const val KANAL_ID = "gis_sunucu"
        private const val BILDIRIM_ID = 1

        fun baslat(context: Context) {
            context.startForegroundService(Intent(context, ServerService::class.java))
        }

        fun durdur(context: Context) {
            context.stopService(Intent(context, ServerService::class.java))
        }
    }
}
