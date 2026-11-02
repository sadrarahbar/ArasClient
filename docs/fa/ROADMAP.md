# نقشهٔ توسعه و بهینه‌سازی

[فهرست](README.md) · [معماری](ARCHITECTURE.md) · [راهنمای توسعه](DEVELOPMENT.md)

> این صفحه پیشنهاد و کارِ آینده است؛ موارد آن قابلیت آماده یا تضمین‌شده نیستند.
> اولویت بر اساس اثر روی درستی اتصال، حفظ داده، امکان آزمون و نگهداری انتخاب شده است.

## اولویت P0 — درستی، محرمانگی و اثبات روی دستگاه

| کار | محصول | علت / شواهد | معیار پذیرش |
|---|---|---|---|
| پالایش لاگ کانفیگ و هویت | Android main/Tesla | مسیر شکست CoreServiceManager می‌تواند config تولیدشده را در سطح error ثبت کند | fixture دارای secret در لاگ‌های debug/release ظاهر نشود؛ خطای قابل تشخیص باقی بماند |
| آزمون واقعی VPN روی Windows 10/11 | Windows | CI فعلی driver و data path محلی را اثبات کرده، نه VPN واقعی کاربر | هر دو حالت Proxy/TUN، HTTPS، DNS و IPv6 با کانفیگ معتبر و سناریوی قطع/بازیابی ثبت شوند |
| تعیین حداقل توزیع/glibc بسته | Linux | باینری روی Ubuntu 26.04 ساخته شده | ماتریس OS هدف، اسکن وابستگی و اجرای بسته روی قدیمی‌ترین نسخهٔ اعلامی |
| ماتریس تست قدیمی‌ترین Android و ABIها | Android | minSdk 24 با تنوع کتابخانه‌های جانبی و محدودیت firmware | نصب/اتصال/توقف روی API 24 و APIهای هدف؛ وضعیت هر helper برای ABI روشن باشد |
| پوشش بازیابی پس از crash و تغییر شبکه | هر محصول | تنظیمات OS و childها بخشی از lifecycle هستند | قطع اجباری، timeout و مرگ helper، route یا پراکسی خراب و process یتیم نگذارند |

افزودن لاگ بیشتر به‌صورت dump کامل config جای observability مناسب نیست.
رخدادهای ساختاریافتهٔ فاقد secret، شناسهٔ سشن غیرحساس و دلیل مرحله‌ای شکست
برای تشخیص مسیر بهترند.

## اولویت P1 — کاهش ریسک توسعه و هزینهٔ ساخت

| کار | محدوده | روش پیشنهادی | شرط تکمیل |
|---|---|---|---|
| جداسازی helper مدیریتی Windows | Windows | نگه‌داشتن UI عادی و helper محدود با IPC احراز‌شده و ACL | UAC فقط برای عملیات لازم؛ قرارداد request معتبر، cleanup و تست منفی |
| کاهش انتظار هم‌زمان در UI | Qt desktop | تبدیل waitهای startup/stop به signal/state غیرمسدودکننده | UI هنگام آماده‌شدن bridge و بستن سشن پاسخ‌گو بماند؛ readiness تضعیف نشود |
| آزمون قرارداد مشترک parser | Linux/Windows/Android export | fixture مصنوعی و versioned برای export/import | payload مشترک، هویت کامل و دو پورت WARP/Psiphon در هر دو دسکتاپ یکسان تفسیر شوند |
| یکسان‌سازی نسخه‌های محیط ساخت | Linux/Windows | lock دقیق‌تر Python/Qt/Pillow و ثبت metadata خروجی | build قابل تکرار با نسخهٔ روشن و بدون اتکای پنهان به binding سیستم |
| pin و cache ساخت native در CI | Android | ثابت‌کردن ابزارهای فعلیِ latest و cache با کلید ورژن/commit | کاهش زمان ساخت بدون استفادهٔ تصادفی از هستهٔ ناسازگار |
| مسیر CI لینوکس | Linux | build و تست روی توزیع‌های هدف و artifact privacy scan | artifact قابل تحویل با checksum و نتیجهٔ native integration |
| کنترل تغییر فقط مستندات در CI | main | تفکیک تست سبک docs از rebuild سنگین Android | تغییر سند بی‌دلیل native core و Release را بازسازی نکند |
| بهبود UX تلویزیون و نمایش کوچک | Android TV/desktop | فوکوس ریموت، hit target، viewport و DPIهای متفاوت | Import/Connect/Test/Replace بدون لمس و بدون بریدگی قابل دسترس باشند |

کاهش تکرار کد دسکتاپ مفید است، اما استخراج عجولانهٔ یک helper مشترک می‌تواند
تفاوت schema و دسترسی‌های Linux/Windows را پنهان کند. ابتدا قرارداد و fixture
مشترک را تثبیت کنید؛ سپس بخش OS-independent را جدا کنید.

## اولویت P2 — توسعهٔ قابلیت با قرارداد روشن

### پروتکل و قالب

- افزودن parser اختصاصی برای ورودی‌های درخواست‌شده، فقط پس از تأیید هستهٔ OS/ABI مقصد.
- ارزیابی `.arasc` برای دسکتاپ با قرارداد نسخه/رمزنگاری و fixture غیرحساس؛ فعلاً آماده محسوب نمی‌شود.
- طراحی subscription دسکتاپ با سیاست جایگزینی تک‌پروفایل، خطای شبکه و جلوگیری از حذف دادهٔ سالم.
- افزودن پروتکل‌هایی مثل TUIC/OpenVPN/SSH فقط به‌صورت مسیر کامل و قابل آزمون، نه فعال‌کردن یک نام در UI.
- ارتقای sing-box لینوکس از schema قدیمی با مهاجرت DNS/route و regression مستقل از Windows.

### سیستم‌عامل و انتشار

- ساخت ARM64 واقعی Linux/Windows با هسته و driver درست؛ تغییر فیلتر CPU به‌تنهایی کافی نیست.
- امضای انتشار Windows و رویهٔ مدیریت کلید؛ داشتن امضا، وعدهٔ حذف قطعی همهٔ هشدارهای SmartScreen نیست.
- ساخت Android قابل ردیابی با منشأ دقیق AAR، checksum و بررسی قابلیت هسته.
- ارزیابی به‌روزرسانی خودکار با اصالت artifact، rollback و حفظ state کاربر.
- نسخهٔ iOS/macOS پروژهٔ مستقل با الزامات OS و lifecycle مخصوص خود است؛ در وضعیت فعلی محصول آماده ندارد.

### کارایی و تجربهٔ کاربری

- اندازه‌گیری زمان cold start، مصرف RAM، startup هسته، DNS و latency واقعی پیش از بهینه‌سازی.
- کاهش bundle با تحلیل وابستگی و مجوزها؛ DLL یا data لازم برای یک پروتکل بدون آزمون حذف نشود.
- بهبود خواندن QR و مسیرهای ورود بدون دوربین، به‌ویژه در TV و Windows.
- استانداردسازی متن خطا و سطح state: مشکل import، مجوز، handshake، route، DNS و TLS جدا گزارش شوند.

## معیار آماده‌بودن یک قابلیت

| مرحله | مدرک لازم |
|---|---|
| طراحی | قرارداد ورودی/خروجی و اثر روی داده و دسترسی OS |
| پیاده‌سازی | parser/model/builder/runtime/cleanup کامل |
| آزمون واحد | حالت معتبر، نامعتبر، cancellation و rollback مرتبط |
| integration | اجرای هستهٔ همان OS، انتقال داده و cleanup واقعی |
| بسته‌بندی | منابع لازم، license، checksum و نبود اطلاعات خصوصی |
| دستگاه مقصد | نتیجه روی نسخهٔ OS و ABI اعلام‌شده |
| مستندات | تغییر جدول پشتیبانی، راهنمای محصول و محدودیت‌ها در main |

## چه چیزهایی را وعده ندهیم؟

کشور خروجی ثابت، عبور قطعی از هر نوع فیلترینگ، پشتیبانی تمام extensionهای
Xray/Clash، سازگاری تمام توزیع‌های Linux، یا اجرای همهٔ قابلیت‌های Android در
دسکتاپ از کد فعلی نتیجه نمی‌شود. هر ادعای جدید باید شواهد مشخص و محدودهٔ آزمون داشته باشد.

## مبنای فنی پیشنهادها

- [مسیر لاگ شکست و اجرای native](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/core/CoreServiceManager.kt)
- [ساخت هسته و ابزارهای CI](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/.github/workflows/build.yml)
- [lifecycle و انتظارهای QProcess](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tesla_vpn/engine.py)
- [محدودهٔ UAC فعلی](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/tesla_vpn/win32.py)
- [مرز آزمون فعلی Wintun و انتقال محلی](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/smoke_test.py)
