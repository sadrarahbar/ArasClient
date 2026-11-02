# پروتکل‌ها، قالب‌های کانفیگ و محدودیت انتقال

[فهرست](README.md) · [معماری](ARCHITECTURE.md) · [سازگاری](COMPATIBILITY.md)

## روش خواندن جدول

- **مسیر اختصاصی**: مدل، parser یا builder/launcher مشخص در محصول وجود دارد؛ موفقیت همهٔ تنظیمات و شبکه‌ها از آن نتیجه نمی‌شود.
- **ورودی مشخص**: parser دسکتاپ آن لینک/قالب را می‌شناسد و backend مرتبط را آماده می‌کند.
- **JSON مشروط**: پذیرش اولیهٔ JSON در parser به معنی پشتیبانی هسته از همهٔ outboundها و extensionها نیست.
- **بدون مسیر کامل**: در UI/parser/launcher فعلی قرارداد end-to-end ارائه نشده است.

`main` و `Android-Client` زیرساخت پروتکل اندروید را مشترک دارند؛ در Tesla بسیاری
از منوها پنهان‌اند و دسترسی عملی از سه روش import انجام می‌شود.

## ماتریس اجرای مدیریت‌شده

| پروتکل یا قابلیت | Android main / Tesla backend | Linux desktop | Windows desktop |
|---|---|---|---|
| VMess | مسیر اختصاصی | لینک `vmess://` و JSON سازگار | همان |
| VLESS / TLS / Reality | مسیر اختصاصی | لینک `vless://` با گزینه‌های پیاده‌شده و JSON | همان |
| Trojan | مسیر اختصاصی | لینک `trojan://` و JSON | همان |
| Shadowsocks | مسیر اختصاصی | لینک `ss://` و JSON | همان |
| SOCKS | مسیر اختصاصی | لینک `socks://` و JSON | همان |
| HTTP proxy به‌عنوان سرور | مسیر اختصاصی | parser لینک HTTP ندارد؛ JSON مشروط | همان |
| WireGuard | builder هسته و ورود conf/URI | فایل `[Interface]/[Peer]` به outbound Xray | همان |
| AmneziaWG | مسیر Android با هستهٔ سفارشی | parser/launcher اختصاصی ندارد؛ JSON را مشروط ببینید | همان |
| Hysteria2 | مسیر اختصاصی Android | URI parser اختصاصی ندارد؛ JSON مشروط | همان |
| Hysteria قدیمی | نوع legacy در مدل؛ سازگاری جزئیات باید بررسی شود | بدون مسیر URI اختصاصی | همان |
| AnyTLS | مسیر اختصاصی Android و هستهٔ سفارشی | URI parser اختصاصی ندارد؛ JSON مشروط | همان |
| MASQUE مستقل Android | نوع و outbound اختصاصی | معادل خودکار آن قالب Android ارائه نشده | همان |
| Aether WG / MASQUE تک‌مرحله‌ای | helper مستقل | `aether://` و export پروژه | همان، با exe رسمی Windows |
| Aether GOOL / MIM | مدل دو hop در Android | مسیر ورود Aether فعلی محدود به WG/MASQUE تک‌مرحله‌ای | همان |
| Psiphon داخل Aether | مدل و helper Android | اختیاری در Aether؛ chain/reverse مطابق parser | همان |
| Psiphon مستقل | نوع carrier اختصاصی | لانچر مستقل مدیریت‌شده ندارد | همان |
| Tor مستقل/داخل Aether | مدل و مسیر carrier در Android | parser Aether حالت Tor را نمی‌پذیرد؛ قرارداد مستقل ندارد | همان |
| Mieru | helper مستقل؛ وابسته به موجودی ABI | باینری/لانچر اختصاصی بسته‌بندی نشده | همان |
| Proxy chain / policy group | مدل ترکیب و مدیریت Android | مهاجرت عمومی زنجیرهٔ Android ارائه نشده | همان |
| TUIC | enum عمداً غیرفعال | پشتیبانی محصول اعلام نشده | همان |
| OpenVPN / SSH VPN | مسیر کامل اختصاصی در این پروژه وجود ندارد | ارائه نشده | ارائه نشده |

### چرا برای JSON «مشروط» می‌نویسیم؟

`xray_profile()` دسکتاپ بررسی می‌کند `outbounds` لیستی از objectهای دارای
`protocol` باشد؛ این کار validator کامل schema یا فهرست قابلیت هسته نیست.
پس وجود خروجی قابل parse برای AnyTLS یا Hysteria، به‌تنهایی نشان نمی‌دهد Xray
رسمی همان نسخه آن را اجرا می‌کند. هستهٔ سفارشی AAR اندروید و executable رسمی
دسکتاپ متفاوت‌اند. نسخهٔ هسته و نتیجهٔ اجرای همان config باید بررسی شوند.

## قالب‌های ورود

| قالب | Android | Linux / Windows |
|---|---|---|
| لینک تکی و batch متن | parserهای Fmt؛ در Tesla فقط یک مورد نگه داشته می‌شود | اولین مورد پشتیبانی‌شده؛ تک‌پروفایل |
| QR | دوربین و مسیر scanner Android | Linux: تصویر یا دوربین اختیاری؛ Windows: تصویر |
| `.arasc` عادی/رمزدار | مسیر اختصاصی import/export | پشتیبانی مستقیم ارائه نشده؛ روی Android به قالب مناسب صادر شود |
| `nekoray://custom#...` پروژه | محصول exporter Aether | فقط قرارداد `core = aras-aether` و payload معتبر پروژه |
| JSON Xray | قالب custom و تبدیل‌های موجود | با محدودیت هستهٔ رسمی و schema آن |
| WireGuard `.conf` | parser اختصاصی | تبدیل به outbound wireguard در Xray |
| Clash YAML | تبدیل محدود بخش `proxies` به مدل‌های پروژه | parser مستقیم در دسکتاپ فعلی ندارد |
| Sing-box JSON | Android دارای مبدل `SingboxFmt` | آن را به‌عنوان config دلخواه sing-box وارد نمی‌کند |
| subscription URL | مسیر مدیریت اشتراک Android | parser دسکتاپ URL راه‌دور را خودکار fetch نمی‌کند |
| subscription base64 | مسیرهای ورود متن Android | بازکردن base64 و انتخاب لینک پشتیبانی‌شده |

قالب انتقال، پروتکل شبکه نیست. همچنین پشتیبانی SOCKS/HTTP محلیِ خروجی برنامه
به معنی وجود parser هر نوع لینک SOCKS/HTTP یا اجرای کامل یک کلاینت دیگر نیست.

## قرارداد Export to Nekoray

exporter، فرمان shell یا outbound حلقهٔ محلی اندروید را کپی نمی‌کند؛ envelope
حاوی آرگومان‌های مجاز، نوع پروتکل، هویت WARP و اطلاعات لازم را تولید می‌کند.
محدودهٔ `supports()` شامل WG/MASQUE تک‌مرحله‌ای، بدون Tor و با شرایط مشخص سایفون
است. پروفایل محافظت‌شده، هویت ناقص یا زنجیرهٔ نامناسب باید رد شود.

- این خروجی تبدیل MASQUE به VLESS/VMess نیست.
- URL خروجی شامل اطلاعات خصوصی است؛ QR، کلیپ‌بورد و فایل آن را محرمانه در نظر بگیرید.
- در chain سایفون، listener نهایی با پورت WARP داخلی متفاوت است؛ listener نهایی باید probe شود.
- `Export to Nekoray` در کد Android حفظ شده، اما Share to V2Box محصول فعلی نیست.

## افزودن یک پروتکل جدید

پیش از درج نام آن در جدول پشتیبانی، این زنجیره باید کامل باشد:

```text
شناخت ورودی → اعتبارسنجی → مدل قابل ذخیره → builder/argv
→ هستهٔ واقعی برای OS/ABI → lifecycle و cleanup → آزمون انتقال داده
```

برای یک قابلیت تنها با «وجود نام در enum»، «قبول‌شدن JSON» یا «اجراشدن process»
تیک پشتیبانی نزنید. تنظیماتی که مبدل نادیده می‌گیرد باید صریح مستند شوند؛
اجرای providers، rules و groups کامل Clash ادعا نشود.

## منابع کد

- [نوع‌های Android و TUIC غیرفعال](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/enums/EConfigType.kt)
- [WG، MASQUE، GOOL و MIM](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/enums/AetherEnums.kt)
- [محدودهٔ تبدیل Clash](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/fmt/ClashYamlFmt.kt)
- [قرارداد و محدودیت exporter](https://github.com/sadrarahbar/ArasClient/blob/e48baa88b8d3a6bc9d2ffb70ae7e4c4de566d278/app/src/main/java/com/aras/client/handler/NekorayAetherExporter.kt)
- [ورودی‌های واقعی parser دسکتاپ Linux](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tesla_vpn/profiles.py)
- [ورودی‌های parser دسکتاپ Windows](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/tesla_vpn/profiles.py)
