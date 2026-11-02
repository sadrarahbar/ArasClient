# آزمون، ساخت و تحویل خروجی

[فهرست](README.md) · [راهنمای توسعه](DEVELOPMENT.md) · [سازگاری](COMPATIBILITY.md)

## شواهد فعلی و محدودهٔ آن‌ها

| محصول | نتیجهٔ ثبت‌شده در توسعه | آنچه از آن نتیجه نمی‌شود |
|---|---|---|
| Android Tesla | ۳۳۸ تست واحد موفق؛ نصب و اتصال روی گوشی تأیید شده | تأیید همهٔ APIها، ROMها، ABIها و Android TV |
| Linux Tesla | ۳۲ تست موفق؛ بررسی TUN و Proxy روی میزبان توسعه | پشتیبانی همهٔ توزیع‌ها، glibcها و شبکه‌ها |
| Windows Tesla | هر ۲۴ تست و smoke/install/uninstall در Server 2022 موفق | VPN واقعی با هویت کاربر روی Windows 10/11 |
| Android main | مسیر CI برای build هسته، تست، lint و APK وجود دارد | موفقیت هر اجرا بدون دیدن گزارش همان commit |

اعداد، snapshot اجرای ثبت‌شده‌اند؛ پس از اضافه/حذف تست می‌توانند تغییر کنند.
نتیجهٔ `OK` همراه skipped را بدون ذکر skipها به «همهٔ integrationها اجرا شدند» تبدیل نکنید.

## فرمان‌های Android

در برنچ هدف و با Java/SDK آماده:

```bash
./tools/build-debug.sh
./gradlew :app:testDebugUnitTest --console=plain
adb devices
```

برای Tesla روی گوشی ARM64:

```bash
adb install -r app/build/outputs/apk/debug/TeslaVpn_1.8.71_arm64-v8a.apk
```

برای `main` نام فعلی خروجی `ArasClient_1.8.71_arm64-v8a.apk` است.
نام‌ها تابع Gradle هستند. برای باکس ARM در `Android-Client`:

```bash
ABI_FILTERS='armeabi-v7a;arm64-v8a' ./tools/build-debug.sh -PUNIVERSAL_APK=true
```

ساخت Release فقط با تنظیمات امضای معتبر و فعال‌بودن variant انجام می‌شود:

```bash
./gradlew :app:testDebugUnitTest :app:lintVitalRelease :app:assembleRelease --console=plain
```

### سناریوهای لازم Android

| بخش | سناریو |
|---|---|
| نصب/ارتقا | امضای یکسان، شناسهٔ بسته، versionCode، حفظ دادهٔ قبلی |
| ورود | QR، متن، فایل، arasc رمزدار؛ رد فایل خراب بدون حذف کانفیگ سالم |
| Tesla | مهاجرت چندپروفایلی، اولین مورد batch، جلوگیری از بازگشت خودکار Free |
| سرویس | اجازه/رد VPN، لغو وسط start، مرگ helper، stop/restart و اعلان |
| شبکه | Wi-Fi و سیم‌کارت، تغییر شبکه، IPv4/IPv6، DNS و HTTPS |
| باکس | D-pad و focus، فایل USB، نبود دوربین، نمایش landscape و مقیاس فونت |

شاخص running سرویس Android با آزمایش اینترنت یکسان نیست. گزارش «متصل است»
باید روشن کند منظور وضعیت UI، برقراری تونل یا عبور واقعی درخواست بوده است.

## فرمان‌های Linux

```bash
./linux/setup.sh
QT_QPA_PLATFORM=offscreen linux/.venv/bin/python -m unittest discover -s linux/tests -v
./linux/build.sh
```

آزمون DNS routing از هستهٔ واقعی استفاده می‌کند و در نبود فایل native می‌تواند
skip شود. build به binutils و سازگاری محیط Qt/Python نیاز دارد. برای آزمون
TUN روی دستگاه واقعی، تنظیمات شبکه را قبل و بعد ثبت کنید؛ کپی دستی ruleهای
cleanup به پیکربندی عمومی شبکه راه‌حل پایدار نیست.

| بررسی Linux | انتظار |
|---|---|
| Proxy در KDE | تنظیم KDE و GSettings مرتبط؛ مرورگر پیرو system proxy |
| Proxy در GNOME | ورود به manual و بازیابی کامل مقادیر قبلی |
| TUN | هر دو خانوادهٔ route به interface برنامه برسند؛ upstream وارد خودش نشود |
| DNS | port 53 به مسیر DNS تعیین‌شده برود؛ rule وابسته به sniff خاموش، تنها مبنا نباشد |
| شکست/خروج | پایان childها و حذف rule/tableهای متعلق به سشن |
| نصب portable | executable و `_internal` با هم باقی بمانند؛ launcher مسیر درست داشته باشد |

## فرمان‌های Windows

```powershell
powershell -ExecutionPolicy Bypass -File windows/setup.ps1
& ./windows/.venv/Scripts/python.exe -m unittest discover -s windows/tests -v
powershell -ExecutionPolicy Bypass -File windows/build.ps1
```

ساخت EXE این پروژه روی Windows انجام می‌شود؛ اجرای PyInstaller لینوکس، EXE
ویندوز تولید نمی‌کند. Actions میزبان Windows را برای ساخت فراهم می‌کند.

### محتوای CI ویندوز

1. Python 3.12 x64 و وابستگی‌های پین‌شده نصب می‌شوند.
2. هسته‌ها و Wintun با SHA256 دریافت/بررسی می‌شوند.
3. تست‌های parser، bridge، UI، Engine، WinINET، ACL و Job Object اجرا می‌شوند.
4. portable با spec صریح PyInstaller ساخته می‌شود.
5. executableهای native و schema sing-box بررسی می‌شوند.
6. آداپتور Wintun بدون تغییر default routing ساخته و پاک می‌شود.
7. درخواست loopback از HTTP به SOCKS و Xray عبور می‌کند؛ EOF، listenerها و childها را می‌بندد.
8. GUI بسته‌شده اجرا و نبود فایل محرمانه در bundle کنترل می‌شود.
9. Inno Setup نصب‌کننده می‌سازد؛ نصب، اجرای نسخهٔ نصب‌شده و uninstall آزمون می‌شوند.
10. ZIP، Setup، SHA256SUMS و preview به Artifact منتقل می‌شوند؛ retention فعلی ۱۴ روز است.

[گزارش موفق ثبت‌شده](https://github.com/sadrarahbar/ArasClient/actions/runs/41363810261)
برای commit `a3d0706` است. برای commit جدید، گزارش تازه بخوانید.

### آزمون دستی باقیماندهٔ Windows

روی Windows 10 1809+ و Windows 11، با کانفیگ معتبر و غیرعمومی، هر دو حالت بررسی
شوند. UAC قبول/لغو، پراکسی قبلی دارای PAC/WPAD، DNS، IPv6، قطع اجباری برنامه،
خواب/بیداری و تغییر شبکه پوشش داده شوند. installer فعلی امضای تجاری ندارد؛
آزمون CI، رفتار SmartScreen روی همهٔ دستگاه‌های مقصد را ثابت نمی‌کند.

## بسته‌ها، نسخه و امضا

| خروجی | محل تولید | نکتهٔ تحویل |
|---|---|---|
| APK | `app/build/outputs/apk/` | ABI، امضا و versionCode را همراه نام فایل ثبت کنید |
| Linux tar.gz | `artifacts/linux/` | OS ساخت و وابستگی‌های باینری را ذکر کنید |
| Windows ZIP/Setup | `artifacts/windows/` | x64 و حداقل 1809؛ ZIP باید کامل استخراج شود |

تغییر نام فایل، شناسهٔ اپ، نسخهٔ داخلی، امضا یا وابستگی‌ها را عوض نمی‌کند.
نام‌گذاری توصیفی مفید است، اما به‌جای metadata داخل بسته نیست.

## قبل از تحویل

- checksum خروجی نهایی محاسبه و با فایل تحویلی بررسی شود؛ فایل قدیمی با نام جدید تحویل نشود.
- artifact برای account، `.toml`، PEM، کلید، profile/session و proxy backup اسکن شود.
- license و notice هسته‌ها و فونت همراه بسته باشند.
- نسخهٔ آماده با نسخهٔ سورس و commit تولیدکننده قابل ردیابی باشد.
- روی portable، اجرای فایل تنها بدون `_internal` پشتیبانی‌شده معرفی نشود.
- uninstall و قطع برنامه نباید route یا پراکسی خراب باقی بگذارند؛ شکست restore باید قابل بازیابی باشد.

## سیاست گیت و CI

فایل‌های نصب را به git push نکنید؛ آن‌ها Artifact یا Release attachment هستند.
گیت‌هاب می‌تواند به خاطر یک blob بزرگ در تاریخچه، حتی پس از حذف فایل در commit
آخر، Push را رد کند. `.gitignore` از ایجاد مجدد مسئله جلوگیری می‌کند ولی
تاریخچه را پاک نمی‌کند. پاک‌سازی history و force-push باید آگاهانه و با حفظ
کار همکاران انجام شوند.

گردش‌کار Android فعلی روی Push به `main` فعال است و فیلتر صرفِ تغییر سورس ندارد؛
Push مستندات به main نیز می‌تواند آن را اجرا کند. build ویندوز برای مسیرهای
`windows/**` و فایل workflow روی `Windows-Client` فیلتر شده است. CI Linux اختصاصی
در snapshot فعلی تعریف نشده است.

## منابع کد

- [مراحل واقعی CI اندروید](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/.github/workflows/build.yml)
- [integration مربوط به DNS لینوکس](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tests/test_dns_routing.py)
- [smoke هسته، Wintun و proxy path](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/smoke_test.py)
- [نصب، اجرای برنامه و حذف](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/installer_smoke.py)
- [workflow و retention خروجی](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/.github/workflows/windows.yml)
