# `minifyEnabled false` olduğu için bu dosya bugün ETKİSİZ. Yine de duruyor:
# AGP `proguardFiles` satırında var olmayan bir dosyaya işaret ederse derleme
# durur, yani ileride küçültme açılmak istendiğinde kuralların yeri hazır olsun.
#
# KÜÇÜLTME AÇILIRSA en az bu kurallar gerekir: Chaquopy Python tarafından
# çağrılan Java sınıflarını YANSIMA ile buluyor, R8 ise yansımayla ulaşılan
# hiçbir şeyi göremiyor — buduğunda hata ancak cihazda, açılış anında
# ClassNotFoundException olarak görünür.
-keep class com.chaquo.python.** { *; }
-keep class org.zenginby.gptimagestudio.** { *; }

# WebView'e JS köprüsü eklenirse (@JavascriptInterface) o sınıflar da
# korunmalı. Bugün böyle bir köprü YOK — damlalık Android'de zaten gizli
# (window.EyeDropper da window.pywebview de burada bulunmuyor).
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
