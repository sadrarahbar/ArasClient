# سازگاری سیستم‌عامل، پردازنده و محیط ساخت

[فهرست](README.md) · [پروتکل‌ها](PROTOCOLS.md) · [آزمون و انتشار](TESTING-RELEASE.md)

## جدول محصول

| محصول | حداقل / هدف OS | CPU و بسته | سطح شواهد فعلی |
|---|---|---|---|
| ArasClient در `main` | Android 7.0 / API 24 به بالا | چهار ABI در تنظیمات Gradle؛ تفاوت هسته‌های جانبی مهم است | کد و تنظیمات ساخت بررسی شده؛ ادعای تست همهٔ APIها وجود ندارد |
| Tesla در `Android-Client` | همان API 24؛ گوشی و باکس با firmware مناسب | APK گوشی arm64؛ Universal مورد استفاده شامل ARM32+ARM64 | نصب و اتصال روی گوشی تأیید شده؛ پوشش تمام باکس‌ها تأیید نشده |
| Tesla Linux | بستهٔ فعلی روی Ubuntu 26.04 ساخته شده | Linux x86_64 | تست دسکتاپ و اتصال روی میزبان توسعه ثبت شده؛ سازگاری توزیع‌های قدیمی باز است |
| Tesla Windows | Windows 10 1809 / build 17763 به بالا و Windows 11 | x64؛ ZIP و Setup | آزمون خودکار روی Server 2022؛ اتصال واقعی روی Windows 10/11 هنوز باز است |
| iOS / macOS | محصول اختصاصی فعلی ندارد | بستهٔ بومی ارائه نشده | قابل وعده‌دادن نیست |

پشتیبانی سیستم‌عامل، پشتیبانی CPU و امکان اتصال در یک شبکه سه شرط جدا هستند.
ممکن است APK نصب شود ولی یک helper برای ABI آن موجود نباشد، یا VPN اجرا شود
ولی شبکهٔ کاربر endpoint مورد نظر را مسدود کند.

## Android: معنی اعداد SDK

| مقدار | هر دو برنچ Android | معنی |
|---|---|---|
| minSdk | 24 | حداقل اعلام‌شدهٔ نصب: Android 7.0 |
| compileSdk | 37 | APIهای در دسترس هنگام compile |
| targetSdk | 37 | رفتارها و محدودیت‌های هدف در Android |
| نسخهٔ برنامه | 1.8.71 | مستقل از نسخهٔ Android و SDK |
| versionCode پایه | 1871 | بعضی خروجی‌های ABI، offset جدا به آن اضافه می‌کنند |

عدد compile/target سقف نسخهٔ OS نیست. برای پشتیبانی عملی نسخهٔ جدید، مجوز VPN،
foreground service، اعلان، پس‌زمینه و تغییرات شبکه باید دوباره آزمون شوند.

### تفاوت ABI هسته‌ها

در snapshot، AAR هستهٔ اصلی برای ARM32، ARM64، x86 و x86_64 کتابخانه دارد؛
فهرست nativeهای جانبی کاملِ یکسانی برای همهٔ آن‌ها نیست:

| ABI | Aether / Psiphon / Lyrebird در app/libs | Mieru در app/libs |
|---|---|---|
| `arm64-v8a` | موجود | موجود |
| `armeabi-v7a` | موجود | فایل مستقل دیده نمی‌شود |
| `x86_64` | موجود | فایل مستقل دیده نمی‌شود |
| `x86` | فایل مستقل این helperها دیده نمی‌شود | فایل مستقل دیده نمی‌شود |

این جدول موجودی فایل‌هاست، نه تضمین تمام رفتارهای شبکه. build Universal یا
وجود `include("x86")` به‌تنهایی کمبود helper را رفع نمی‌کند.

### اندروید باکس

برای Allwinner H6 / Cortex-A53 با Android 9، APK ARM Universal انتخاب مناسبی
برای پوشش firmware ۳۲ یا ۶۴ بیتی است. CPU نوع A53 به‌تنهایی ABI فعال سیستم را
تعیین نمی‌کند. روی دستگاه می‌توان بررسی کرد:

```bash
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abilist
```

Manifest لمس و دوربین را اجباری نکرده و Leanback launcher دارد؛ با این حال
فوکوس D-pad، بازکردن فایل از USB، نبود کلیپ‌بورد/دوربین و نمایش روی تلویزیون
باید جدا آزمون شوند. رزولوشن تبلیغی 4K/6K جای این آزمون‌ها را نمی‌گیرد.

## Linux: سازگاری باینری و سورس

بستهٔ PyInstaller شامل Python/Qt و بسیاری از کتابخانه‌هاست، اما نباید آن را
مستقل از ABI سیستم و همهٔ نسخه‌های glibc فرض کرد. برای بستهٔ فعلی، حداقل glibc
با اسکن وابستگی‌ها و آزمون روی توزیع‌های هدف هنوز تعیین نشده است.

اجرای سورس به Python 3.11+، PyQt6 و وابستگی‌های requirements نیاز دارد؛
دانلودر فعلی فقط x86_64 را می‌پذیرد. TUN علاوه بر دسترسی مدیر به ابزارهای
شبکه و kernel TUN نیاز دارد. حالت پراکسی خودکار برای KDE/GNOME پیاده شده است.

## Windows: نصب با TUN فرق دارد

- نصب Setup به‌صورت per-user و بدون درخواست مدیر انجام می‌شود.
- Proxy به تنظیمات کاربر فعلی WinINET متکی است و مدیر لازم ندارد.
- TUN مجوز Administrator می‌خواهد و از DLL رسمی Wintun استفاده می‌کند.
- محیط Python/Qt در بسته همراه است؛ نصب آن‌ها روی دستگاه مقصد لازم نیست.
- Windows x86 و ARM64 بومی در این بسته ارائه نشده‌اند؛ امولیشن x64 تضمین driver نیست.
- `windows-2022` نام runner ساخت است؛ به معنی الزام نصب Server روی رایانهٔ کاربر نیست.

## چه چیزی باید پیش از اعلام پشتیبانی جدید ثبت شود؟

نسخه و build دقیق OS، ABI واقعی، display scaling، نوع شبکه، حالت اتصال، نسخهٔ
هسته، سناریوی reconnect/stop، نتیجهٔ HTTPS و وضعیت DNS/IPv6 باید ثبت شوند.
IP، کلید یا فایل account کامل را به گزارش عمومی پیوست نکنید.

## منابع کد

- [SDK و ABI در main](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/build.gradle.kts)
- [Universal در Android-Client](https://github.com/sadrarahbar/ArasClient/blob/ea250e6e47c3c9773b67e5451c29aac74c3410cc/app/build.gradle.kts)
- [ویژگی‌های سخت‌افزاری اختیاری](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/AndroidManifest.xml)
- [محدودیت Linux x86_64](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/prepare_cores.py)
- [کنترل نسخه و معماری Windows](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/tesla_vpn/win32.py)
- [حداقل نسخهٔ نصب‌کننده](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/installer.iss)
