package com.zenginby.kromis

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/**
 * Chaquopy'nin Python çalışma zamanını süreç başına BİR kez kurar.
 *
 * Neden Application'da, Activity'de değil: `Python.start` süreç ömürlü ve ikinci
 * çağrısı istisna fırlatıyor. Activity yeniden yaratılabildiği için (düşük
 * bellek, "Activity'leri koru" geliştirici ayarı) oraya konsaydı kurulum
 * ikinci açılışta çökerdi. ServerService de aynı süreçte yaşıyor, yani ikisi
 * de burada kurulan tek çalışma zamanını paylaşıyor.
 *
 * Burada YALNIZCA çalışma zamanı kuruluyor; uvicorn başlatılmıyor. Application
 * `onCreate`'i ana thread'de ve uygulamanın her açılışında (bildirim
 * tıklaması, servis yeniden başlatması dahil) koşuyor — sunucuyu buraya koymak
 * ana thread'i saniyelerce kilitlerdi.
 */
class StudioApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
    }
}
