# Kromis Studio'yu Windows uygulaması olarak derler ve zip'ler.
#
# build.sh'in Windows karşılığıdır; o dosyaya DOKUNULMAZ — macOS hattı kendi
# akışıyla (ad-hoc imza + ditto) çalışmaya devam eder. Ortak olan tek şey
# kromis.spec: iki platform aynı spec'i kullanır, spec kendi içinde
# platforma göre dallanır.
#
# İMZA YOK: Windows'ta ad-hoc imzanın karşılığı yoktur; gerçek imza ücretli bir
# kod imzalama sertifikası ister. Bu yüzden ilk açılışta SmartScreen
# "Bilinmeyen yayımcı" uyarısı çıkar ve kullanıcı "Ek bilgi → Yine de çalıştır"
# demek zorundadır (macOS'taki "Yine de Aç" adımının birebir eşi; KURULUM.md'de
# anlatılır).
#
# Çalıştırma:  .\build.ps1
# ExecutionPolicy engelliyorsa:  powershell -ExecutionPolicy Bypass -File .\build.ps1

# `set -euo pipefail` KARŞILIĞI DEĞİL — burada iki ayrı mekanizma gerekiyor:
# ErrorActionPreference yalnız PowerShell cmdlet'lerinin hatasını ölümcül yapar,
# yerel bir .exe'nin sıfır-dışı çıkış kodunu GÖRMEZ bile. pyinstaller ya da
# pytest başarısız olduğunda betik sessizce devam edip "hazır" derdi. Bu yüzden
# her yerel çağrıdan sonra Assert-Basarili ile $LASTEXITCODE denetleniyor.
$ErrorActionPreference = 'Stop'

# Betiğin bulunduğu dizine geç: kullanıcı başka bir yerden çağırsa da göreli
# yollar (spec, requirements, tests) çözülsün.
Set-Location -LiteralPath $PSScriptRoot

$AppName = 'Kromis'
$AppDir  = Join-Path 'dist' $AppName
$Exe     = Join-Path $AppDir "$AppName.exe"
$Zip     = Join-Path 'dist' "$AppName-windows.zip"

function Assert-Basarili {
    param([string]$Adim)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "HATA: $Adim başarısız (çıkış kodu $LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }
}

# --- Python bulma -----------------------------------------------------------
# `python3` DEĞİL: Windows'ta öyle bir komut genelde yoktur (build.sh'in tersi).
# `py` başlatıcısı tercih edilir çünkü çıplak `python`, Python kurulu değilken
# Microsoft Store kısayoluna düşer: komut VARDIR, çalıştırılır, hiçbir şey
# yapmaz ve Store penceresi açar. Bu yüzden varlık kontrolü yetmez — gerçekten
# sürüm basıp basmadığına bakılıyor.
$Python = $null
foreach ($aday in @(@('py', '-3'), @('python'))) {
    $komut = $aday[0]
    if (-not (Get-Command $komut -ErrorAction SilentlyContinue)) { continue }
    $argv = @($aday[1..($aday.Length - 1)]) + '--version'
    try { $cikti = & $komut @argv 2>$null } catch { continue }
    if ($LASTEXITCODE -eq 0 -and "$cikti" -match 'Python 3') {
        $Python = $aday
        break
    }
}
if (-not $Python) {
    Write-Host 'HATA: Python 3 bulunamadı.' -ForegroundColor Red
    Write-Host 'Kur: https://www.python.org/downloads/windows/'
    Write-Host 'Kurulumda "Add python.exe to PATH" kutusunu İŞARETLE.'
    exit 1
}

# --- Sanal ortam ------------------------------------------------------------
$VenvPy = Join-Path '.venv' (Join-Path 'Scripts' 'python.exe')
if (-not (Test-Path -LiteralPath $VenvPy)) {
    Write-Host '→ .venv yok, oluşturuluyor'
    & $Python[0] @($Python[1..($Python.Length - 1)]) -m venv .venv
    Assert-Basarili 'python -m venv .venv'
}

# Activate.ps1 BİLEREK çağrılmıyor. O betik imzasız olduğu için kısıtlı
# ExecutionPolicy'de (kurumsal makinelerin varsayılanı) çalışmaz ve derleme
# hiç başlamadan ölür. Yorumlayıcıyı tam yolla çağırmak aynı sonucu verir,
# hiçbir politikaya takılmaz.
Write-Host '→ bağımlılıklar'
& $VenvPy -m pip install -q -r requirements.txt -r requirements-dev.txt
Assert-Basarili 'pip install'

Write-Host '→ testler'
& $VenvPy -m pytest tests/ -q
Assert-Basarili 'pytest'

Write-Host '→ temizlik'
foreach ($d in @('build', 'dist')) {
    if (Test-Path -LiteralPath $d) { Remove-Item -LiteralPath $d -Recurse -Force }
}

Write-Host '→ derleme'
# `pyinstaller.exe` yerine `-m PyInstaller`: shim exe'nin gömülü shebang'i
# .venv taşındığında/kopyalandığında bozulur, modül çağrısı bozulmaz.
& $VenvPy -m PyInstaller 'kromis.spec' --noconfirm
Assert-Basarili 'pyinstaller'

# PyInstaller sıfır dönüp yine de beklenen adı üretmemiş olabilir (spec'teki
# `name` değişirse). Zip'lemeden önce kanıt ara — yoksa boş bir zip gönderilir.
if (-not (Test-Path -LiteralPath $Exe)) {
    Write-Host "HATA: beklenen çıktı yok: $Exe" -ForegroundColor Red
    exit 1
}

Write-Host '→ .NET yapılandırması'
# NEDEN spec'in `datas`'ı DEĞİL: PyInstaller 6 onedir'de datas `_internal/`
# altına iniyor, CLR ise varsayılan AppDomain'in config'ini `<exe yolu>.config`
# diye arıyor. `_internal/` altındaki bir kopya HİÇ okunmaz — yani spec'e
# eklemek "yapıldı" görünen, hiçbir şey yapmayan bir değişiklik olurdu.
# Dosyanın kendisi ve gerekçesi: branding/Kromis.exe.config.
$Config = "$Exe.config"
Copy-Item -LiteralPath (Join-Path 'branding' 'Kromis.exe.config') -Destination $Config -Force
if (-not (Test-Path -LiteralPath $Config)) {
    Write-Host "HATA: .NET yapılandırması kopyalanmadı: $Config" -ForegroundColor Red
    exit 1
}

Write-Host '→ zip'
if (Test-Path -LiteralPath $Zip) { Remove-Item -LiteralPath $Zip -Force }
# Compress-Archive DEĞİL: PowerShell 5.1'deki uygulaması zip girdi adlarına ters
# eğik çizgi yazar (bazı çıkarıcılar dosyaları tek bir uzun adlı dosyaya
# çevirir) ve bu boyutta ağaçta belirgin yavaştır. .NET'in ZipFile'ı doğru
# ayırıcıyı yazar; son parametre (includeBaseDirectory) ditto'nun
# --keepParent'ının eşi: çıkarınca dosyalar masaüstüne dağılmaz, tek klasör olur.
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    (Resolve-Path -LiteralPath $AppDir).Path,
    (Join-Path (Resolve-Path -LiteralPath 'dist').Path (Split-Path -Leaf $Zip)),
    [System.IO.Compression.CompressionLevel]::Optimal,
    $true)

Write-Host '→ ara derleme dizinini temizle'
if (Test-Path -LiteralPath 'build') { Remove-Item -LiteralPath 'build' -Recurse -Force }

$mb = [math]::Round((Get-Item -LiteralPath $Zip).Length / 1MB, 1)
Write-Host "✓ hazır: $Zip ($mb MB)" -ForegroundColor Green
