# ساخت نسخهٔ آزمایشی در لینوکس

از پوشهٔ اصلی پروژه اجرا کنید:

```bash
./tools/build-debug.sh
```

فایل APK در `app/build/outputs/apk/debug/` ساخته می‌شود. آن را به گوشی
منتقل و نصب کنید. خروجی پیش‌فرض برای گوشی‌های `arm64-v8a` است.

برای اجرای تست‌های واحد همراه با ساخت APK:

```bash
./tools/build-debug.sh :app:testDebugUnitTest
```

برای نصب با کابل، USB debugging را در گوشی فعال و اجازهٔ اتصال رایانه را
تأیید کنید. سپس دستگاه‌های متصل را ببینید و فایل خروجی را نصب کنید:

```bash
adb devices
adb install -r app/build/outputs/apk/debug/ArasClient_1.8.71_arm64-v8a.apk
```

با تغییر نسخهٔ پروژه، نام APK نیز عوض می‌شود. نسخهٔ Debug با نام
`ArasClient Test` و شناسهٔ `com.aras.client.debug` کنار نسخهٔ اصلی نصب می‌شود
و تنظیمات و کانفیگ‌های مستقل دارد.

در محیط آماده‌شده، Java و Gradle زیر `~/.local/share/aras-android/` و Android
SDK زیر `~/Android/Sdk/` قرار دارند. تنظیم مسیرها در فایل زیر است:

```bash
source "$HOME/.config/aras-android/env.sh"
```

این فایل در ترمینال‌های جدید Bash به‌صورت خودکار خوانده می‌شود. `local.properties`
مسیر SDK همین رایانه را نگه می‌دارد و وارد Git نمی‌شود.

بدون `keystore.properties` فقط نسخهٔ Debug قابل ساخت است. ساخت Release به کلید
انتشار نیاز دارد. کلید اصلی انتشار برای تست محلی لازم نیست.

هسته‌های آماده داخل `app/libs/` هستند؛ تغییر کد Kotlin معمولاً نیازی به بازسازی
هسته با Go یا NDK ندارد. نصب و اتصال موفق VPN باید جداگانه روی گوشی تست شود.
