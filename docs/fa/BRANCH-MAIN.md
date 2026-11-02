# برنچ main — ArasClient اصلی اندروید

[فهرست مستندات](README.md) · [معماری](ARCHITECTURE.md) · [راهنمای توسعه](DEVELOPMENT.md)

> مرجع کد: `e48baa8` · نسخهٔ برنامه: `1.8.71` · هدف: نسخهٔ کامل و چندکانفیگی اندروید.

## مسئولیت و محدوده

`main` پایهٔ اندرویدی پروژه و محل مستندات مرکزی است. این محصول رابط مدیریتی
پروفایل‌ها، گروه‌ها، اشتراک‌ها، آزمون اتصال و تنظیمات پیشرفته را دارد؛ رابط
تک‌دکمه‌ای Tesla مربوط به `Android-Client` است. وجود خروجی Nekoray در `main`
آن را به برنامهٔ لینوکس تبدیل نمی‌کند: این قابلیت، خروجی قابل حمل از داخل اندروید است.

## استک و نسخه‌ها

| لایه | فناوری / مقدار در کد مرجع |
|---|---|
| زبان و JVM هدف | Kotlin `2.4.10`؛ Java/JVM `17` |
| ساخت | Gradle Wrapper `9.5.1`؛ Android Gradle Plugin `9.3.1` |
| رابط | Jetpack Compose؛ Material 3؛ Compose BOM `2026.06.01` |
| وضعیت و چرخهٔ عمر | ViewModel، StateFlow، Kotlin Coroutines، Lifecycle Compose |
| ذخیره‌سازی و JSON | MMKV `1.3.16`؛ Gson `2.14.0` |
| شبکه و پس‌زمینه | OkHttp `5.4.0`؛ WorkManager `2.11.2` |
| تصویر و QR | Coil `2.7.0`، SVG، CameraX `1.6.1`، ZXing `3.5.4` |
| ورودی YAML | SnakeYAML `2.3`؛ تبدیل محدود پروفایل‌های Clash |
| هسته | `aras-core.aar` با bindingهای `libv2ray`؛ هستهٔ Xray سفارشی |
| پردازش‌های کمکی | Aether، Mieru و carrierهای Psiphon/Tor از مسیر مدیرهای اختصاصی |
| بستهٔ رمزدار | `arasc-crypto.aar` و `ArasExportImportManager` |

هستهٔ Xray و bindingهای gomobile در اکوسیستم Go قرار دارند؛ Aether یک پردازش
native مستقل مبتنی بر Rust است. Kotlin مسئول orchestration و UI است، نه
پیاده‌سازی دوبارهٔ رمزنگاری همهٔ پروتکل‌ها.

نسخهٔ binding یا هستهٔ آماده را فقط از نام فایل AAR نتیجه نگیرید.
CI هسته را با مرجع `aras-core-26.10.22` می‌سازد؛ این برچسب، به‌تنهایی هویت هر
AAR محلی موجود روی یک دستگاه توسعه را ثابت نمی‌کند.

## سیستم‌عامل و معماری CPU

- `minSdk = 24`: حداقل اعلام‌شده **Android 7.0**.
- `compileSdk = 37` و `targetSdk = 37`: سطح ساخت و رفتار هدف، نه حداقل یا سقف نسخهٔ قابل نصب.
- Gradle برای `armeabi-v7a`، `arm64-v8a`، `x86` و `x86_64` خروجی ABI تعریف می‌کند.
- پوشش هسته‌های جانبی بین ABIها یکسان نیست؛ برای نمونه، فایل Mieru فعلی فقط در `arm64-v8a` موجود است.
- Manifest دوربین و لمس را الزامی نکرده و ورودی Leanback دارد؛ نصب روی باکس با مناسب‌بودن کامل UX تلویزیون یا تأیید فروشگاه یکسان نیست.

جزئیات نسخه و سطح آزمون در [سازگاری](COMPATIBILITY.md) آمده است.

## معماری و نقاط ورود

| مسئولیت | مسیر / نماد |
|---|---|
| ورود UI و مجوز VPN | `ui/main/MainActivity.kt` |
| وضعیت، اکشن و دادهٔ صفحه | `MainViewModel`، `MainContract`، `MainRepository` / `MainDataSource` |
| پروفایل و اشتراک | `MmkvManager`، `AngConfigManager`، مدل‌های `dto/entities/` |
| تبدیل ورودی | `fmt/*Fmt.kt` و انتخاب نوع در `EConfigType` |
| ساخت کانفیگ اجرایی | `CoreConfigContextBuilder`، `CoreConfigManager`، `CoreOutboundBuilder` |
| انتخاب سرویس | `LauncherManager` |
| اجرای سشن و binding | `CoreServiceManager`، `CoreNativeManager`، `ArasCore` |
| سیستم VPN | `CoreVpnService`، تنظیمات TUN، DNS و مسیرها |
| پراکسی و root | `CoreProxyOnlyService` و `CoreRootService` |
| هسته‌های جانبی | `HelperProcessSupport`، `AetherCoreManager`، `MieruProcessManager` |

رابط مستقیماً JSON اجرایی یا پردازش native را مدیریت نمی‌کند. مدیر سرویس پیش از
ساخت outbound وابسته به SOCKS محلی، هستهٔ جانبی را آماده می‌کند. جزئیات دو مسیر
TUN در [معماری](ARCHITECTURE.md) توضیح داده شده است.

## پروتکل‌ها و قابلیت‌ها

مسیرهای اختصاصی برای VMess، VLESS، Shadowsocks، SOCKS، HTTP، Trojan، WireGuard،
AmneziaWG، Hysteria2، AnyTLS، MASQUE، Aether و Mieru وجود دارند. Psiphon و Tor
به‌عنوان carrier نیز مدل شده‌اند. `PROXYCHAIN` و `POLICYGROUP` نوع ترکیب/سیاست‌اند،
نه پروتکل رمزنگاری مستقل. **TUIC عمداً غیرفعال است**؛ OpenVPN و SSH مسیر اجرایی
کامل اختصاصی ندارند. Hysteria قدیمی را با تضمین اجرای تمام کانفیگ‌های Hysteria2
یا برعکس یکی ندانید.

ورود از لینک، QR، فایل، `.arasc` و برخی قالب‌های تبدیل‌شونده پشتیبانی می‌شود؛
واردکردن Clash YAML به معنی اجرای rules، providers و groups یک کلاینت Clash نیست.
[ماتریس دقیق](PROTOCOLS.md) مرجع محدودیت‌هاست.

## ساخت و اجرای توسعه

از ریشهٔ همین برنچ، با JDK و SDK آماده:

```bash
./tools/build-debug.sh
./gradlew :app:testDebugUnitTest --console=plain
adb install -r app/build/outputs/apk/debug/ArasClient_1.8.71_arm64-v8a.apk
```

`tools/build-debug.sh` در صورت وجود، تنظیمات محلی
`~/.config/aras-android/env.sh` را می‌خواند؛ این مسیر قرارداد عمومی همهٔ ماشین‌ها نیست.
پیش‌فرض اسکریپت `arm64-v8a` است. برای همهٔ ABIهای تعریف‌شده و Universal در `main`:

```bash
./gradlew :app:assembleDebug --console=plain
```

در `main` گزینهٔ خاص `UNIVERSAL_APK` برنچ Tesla وجود ندارد. شمارهٔ نسخه و نام فایل
ممکن است پس از تغییر Gradle متفاوت شوند؛ خروجی واقعی `app/build/outputs/apk/` را بررسی کنید.
Debug شناسهٔ `com.aras.client.debug` دارد؛ Release از `com.aras.client` استفاده می‌کند.
Release بدون تنظیمات امضای معتبر در تنظیمات فعلی غیرفعال می‌شود.

## قرارداد تغییر

- افزودن پروتکل فقط افزودن enum یا فرم نیست: parser، مدل، outbound، هستهٔ سازگار، lifecycle و آزمون لازم است.
- سرویس و پردازش‌های جانبی نباید از Composable آغاز شوند؛ مسیر اکشن و مجوز موجود حفظ شود.
- برای به‌روزرسانی UI از StateFlow و چرخهٔ عمر موجود استفاده شود؛ وضعیت «فرآیند اجرا شد» را با «اینترنت کار می‌کند» یکی نکنید.
- تغییر ذخیره‌سازی باید selection، گروه‌ها و پروفایل محافظت‌شده را حفظ کند.
- رفتار مهاجرت، لغو حین اتصال و توقف هستهٔ جانبی باید جدا آزمایش شود.

## مسیر توسعهٔ بعدی

اولویت‌های این برنچ: حذف دادهٔ محرمانه از لاگ کانفیگ، آزمون واقعی سرویس روی
نسخه‌های اندروید، قابلیت تکرار ساخت هسته و ارزیابی قابلیت‌های ناقص به‌صورت
عمودی از UI تا هسته. جزئیات و معیار پذیرش در [نقشهٔ راه](ROADMAP.md) آمده است.

## منابع کد

- [تنظیمات APK و SDK](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/build.gradle.kts)
- [نسخهٔ کتابخانه‌ها](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/gradle/libs.versions.toml)
- [مدیریت اجرای هسته](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/core/CoreServiceManager.kt)
- [نوع‌های پروفایل](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/enums/EConfigType.kt)
- [ساخت Android و هسته در CI](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/.github/workflows/build.yml)
