# برنچ Linux-Client — Tesla Vpn دسکتاپ لینوکس

[فهرست مستندات](README.md) · [معماری](ARCHITECTURE.md) · [راهنمای توسعه](DEVELOPMENT.md)

> مرجع کد: `94bcb7b` · نسخهٔ دسکتاپ: `1.0.0` · ریشهٔ محصول: `linux/`.

## هدف و حدود محصول

نسخهٔ دسکتاپ برای واردکردن یک کانفیگ و اتصال با TUN یا پراکسی دسکتاپ ساخته شده
است. این برنامه APK را اجرا نمی‌کند و پوسته‌ای دور اپ اندروید نیست؛ منطق
ورود، آماده‌سازی هسته و اتصال در Python بازنویسی شده است. مدل خروجی Aether
اندروید، نقطهٔ تبادل کانفیگ میان دو محصول است.

پنجرهٔ فعلی **۴۵۱×۸۵۲**، دکمهٔ **۱۷۱×۱۷۱** و هالهٔ ۴۴۶×۴۴۶ دارد؛ این اعداد از
`ui.py` مرجع استخراج شده‌اند. README قدیمی همان برنچ که ۳۲۰×۶۰۰ و دکمهٔ ۱۲۸
می‌گوید، توصیف نسخهٔ قبلی است. Geologica و SVGهای محلی، ظاهر مشترک Tesla را می‌سازند.

[فریم طراحی دسکتاپ در Figma](https://www.figma.com/design/gKL0JdFJt1yzb1DuWeAnyu/Tesla-VPN?node-id=12-3)
منبع طراحی است؛ برای نسخهٔ پیاده‌شده، کد کامیت مرجع مبناست.

## استک

| بخش | فناوری |
|---|---|
| برنامه و parser | Python؛ حداقل عملی سورس `3.11` به دلیل `tomllib` و `hashlib.file_digest` |
| رابط | PyQt6، QtWidgets، QPainter، QFontDatabase |
| اتصال و آزمون | QObject/QProcess/QTimer، QtNetwork و SOCKS5 |
| پراکسی HTTP | `asyncio`؛ HTTP و CONNECT روی loopback، با خروجی SOCKS |
| ورود QR | Pillow و `zxing-cpp==3.1.1`؛ دوربین اختیاری با ffmpeg / V4L2 |
| بسته‌بندی | `PyInstaller==6.22.0`، بستهٔ onedir و `tar.gz` |
| تست | `unittest`، socket/asyncio integration و Qt offscreen |
| مسیریابی TUN | sing-box/NekoBox Core، `iproute2`، `nftables` و `pkexec` |
| پراکسی دسکتاپ | ابزارهای KDE و GSettings برای GNOME/GTK |

در ماشین ساختِ ثبت‌شده Python 3.14 و PyQt6 6.10.2 استفاده شده‌اند. `requirements.txt`
بستهٔ PyQt6 را مستقیماً pin نمی‌کند؛ setup ابتدا binding سیستم را می‌پذیرد و
در نبود آن PyQt6 6.10.2 را نصب می‌کند. بنابراین یکسان‌بودن دو محیط صرفاً از
این فایل نتیجه نمی‌شود.

رابط Qt در لایهٔ C++ با binding پایتونی استفاده می‌شود؛ Xray/Psiphon و Aether
به‌عنوان executableهای مستقل (به‌ترتیب در اکوسیستم Go و Rust) اجرا می‌شوند.

## هسته‌های پین‌شده

- Aether `2.4.0`، باینری Linux x86_64 musl و Psiphon همراه آن.
- Xray رسمی `26.3.27` همراه `geoip.dat` و `geosite.dat`.
- `nekobox_core` همراه انتشار Nekoray `4.0.1` برای مسیریابی TUN.
- فایل عمومی bootstrap سایفون، استخراج‌شده از asset ثبت‌شدهٔ پروژه.
- SHA256 هر فایل در `linux/core-checksums.json` کنترل می‌شود.

این هستهٔ Xray با AAR سفارشی اندروید یکسان فرض نمی‌شود. JSON یا قابلیتی که
فقط در fork اندروید وجود دارد، بدون آزمون هستهٔ رسمی دسکتاپ قابل وعده‌دادن نیست.

## سیستم‌عامل و CPU

هدف downloader و بستهٔ فعلی **Linux x86_64** است. بستهٔ موجود روی Ubuntu 26.04
ساخته شده؛ حداقل نسخهٔ توزیع، glibc و سازگاری با Debian/Fedora/Ubuntu قدیمی‌تر
به‌صورت جامع تأیید نشده‌اند. ساخت از سورس روی توزیع مقصد، با پشتیبانی قطعی
همهٔ توزیع‌ها برابر نیست. ARM و ARM64 فعلاً بستهٔ آمادهٔ این برنچ نیستند.

TUN به `/dev/net/tun`، `pkexec`، `iproute2` و `nftables` نیاز دارد. System proxy
برای KDE و محیط‌های مبتنی بر GNOME تعریف شده است؛ روی دسکتاپ دیگر، TUN یا
تنظیم دستی پراکسی برنامه‌ها مطرح است، نه ادعای تنظیم خودکار عمومی.

## معماری اجرا

| فایل | مسئولیت |
|---|---|
| `main.py` | CLI، تک‌نمونه‌بودن GUI و ورود helperهای مستقل |
| `tesla_vpn/profiles.py` | parse بدون اجرا، محدودیت ورودی، تک‌پروفایل و نوشتن اتمی |
| `tesla_vpn/runtime.py` | پورت‌های مجزا، مسیر account، env و argv هسته |
| `tesla_vpn/engine.py` | ماشین حالت اتصال، QProcess، آزمون HTTPS و توقف |
| `tesla_vpn/tun.py` | سرپرست privileged، مسیرها و cleanup |
| `tesla_vpn/system_proxy.py` | snapshot و بازیابی KDE/GNOME |
| `tesla_vpn/http_bridge.py` | تبدیل HTTP/CONNECT محلی به SOCKS |
| `tesla_vpn/ui.py` | نمایش، رنگ، ورود QR و اتصال اکشن‌ها به Engine |

### TUN: تفکیک دسترسی

سرپرست با `pkexec` بالا می‌آید؛ هستهٔ Aether/Xray با UID کاربر و یک GID آزاد
اختصاصی اجرا می‌شود. فقط sing-box و ابزارهای شبکه دسترسی root دارند.
`nftables` ترافیک GID هسته را علامت‌گذاری می‌کند و `ip rule` آن را از مسیر TUN
دور نگه می‌دارد؛ در نتیجه اتصال بالادستی دوباره وارد تونل خودش نمی‌شود.

پس از تأیید SOCKS/HTTPS، UI پیام `enable` می‌فرستد. helper پس از بررسی مسیر
IPv4 و IPv6، رویداد آماده‌شدن می‌دهد و UI اینترنت مستقیم سیستم را دوباره
آزمایش می‌کند. با EOF، توقف یا شکست child، مسیرها و ruleها جمع می‌شوند.

### پراکسی: فقط برنامه‌های پیرو تنظیمات دسکتاپ

HTTP bridge و SOCKS محلی آماده می‌شوند و تنظیمات قبلی ذخیره می‌شوند.
در KDE، تنظیمات GTK/GSettings نیز پوشش داده می‌شود تا Firefox به‌اشتباه
مستقیم خارج نشود. بازیابی، تغییر مستقل کاربر را بی‌دلیل بازنویسی نمی‌کند.
این حالت به معنی اجبار همهٔ برنامه‌ها و سرویس‌ها به عبور از VPN نیست.

## قالب‌ها، داده و امنیت

ورودی‌های تضمین‌شده در parser: `aether://` تک‌مرحله‌ای WG/MASQUE، خروجی
`nekoray://custom#...` از exporter پروژه، JSON Xray، لینک‌های VLESS/VMess/Trojan/
Shadowsocks/SOCKS و WireGuard `.conf`. سایفون اختیاری در مسیر Aether پشتیبانی
می‌شود. `.arasc`، Tor مستقل، GOOL/MIM و زنجیرهٔ عمومی اندروید در این رابط
مسیر کامل ندارند؛ [پروتکل‌ها](PROTOCOLS.md) را ببینید.

دادهٔ محلی در `~/.config/tesla-vpn/` است: `profile.json`، accountها، `session.json`،
وضعیت و backup پراکسی. این‌ها محرمانه‌اند؛ permission دایرکتوری ۷۰۰ و فایل‌های
خصوصی ۶۰۰ است. خروجی Nekoray حامل هویت و کلید است و صرفاً یک نشانی عمومی نیست.

## ساخت و آزمون

```bash
git switch Linux-Client
./linux/setup.sh
./linux/run.sh
QT_QPA_PLATFORM=offscreen linux/.venv/bin/python -m unittest discover -s linux/tests -v
./linux/build.sh
```

آماده‌سازی venv، Qt و ابزارهای ساخت، از جمله `binutils`، لازم است. اجرای تست
بدون هستهٔ native ممکن است بعضی integration testها را skip کند؛ تعداد skipped
را همراه نتیجه ثبت کنید. downloader فقط فایل‌های هم‌خوان با checksum را می‌پذیرد.

خروجی: `artifacts/linux/TeslaVpn/` و
`artifacts/linux/TeslaVpn-1.0.0-linux-x86_64.tar.gz`.
`_internal` باید کنار فایل اجرایی بماند. `install.sh` بستهٔ خروجی، برنامه را در
`~/.local/opt/tesla-vpn` و launcher را در مسیر کاربری نصب می‌کند.

## وضعیت آزمون و ادامهٔ توسعه

۳۲ تست در مرحلهٔ توسعهٔ لینوکس موفق گزارش شده‌اند. همچنین TUN و System proxy
روی میزبان توسعه با خروجی کشور و دسترسی وب بررسی شده‌اند؛ این گزارش تضمین
رفتار همهٔ شبکه‌ها نیست. build سازگار با glibc قدیمی‌تر، آزمون قطع ناگهانی،
پشتیبانی چند توزیع و رندر responsive از کارهای بعدی‌اند.

## منابع کد

- [رابط فعلی و اندازه‌ها](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tesla_vpn/ui.py)
- [TUN و تفکیک UID/GID](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tesla_vpn/tun.py)
- [پراکسی و بازیابی](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tesla_vpn/system_proxy.py)
- [منشأ و نسخهٔ باینری‌ها](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/prepare_cores.py)
- [آزمون واقعی مسیر DNS](https://github.com/sadrarahbar/ArasClient/blob/94bcb7bf6485b4ee2c092f55f52f44e5606ff5ea/linux/tests/test_dns_routing.py)
