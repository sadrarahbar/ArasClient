# برنچ Windows-Client — Tesla Vpn برای ویندوز

[فهرست مستندات](README.md) · [معماری](ARCHITECTURE.md) · [راهنمای توسعه](DEVELOPMENT.md)

> مرجع کد: `a3d0706` · نسخه: `1.0.0` · ریشهٔ محصول: `windows/`.

## هدف و نسبت با برنچ لینوکس

این برنچ از `Linux-Client` ساخته شده و قرارداد ورود کانفیگ و بخش زیادی از
رابط دسکتاپ را حفظ می‌کند. لایهٔ وابسته به OS، شامل پراکسی، دسترسی مدیر،
مدیریت childها و TUN، مخصوص ویندوز بازنویسی شده است. تغییر نام ELF به EXE یا
اجرای APK روش تولید این محصول نیست.

رابط پایه ۴۵۱×۸۵۲، دکمهٔ ۱۷۱ و هالهٔ هم‌رنگ وضعیت است. ورودی‌ها تک‌کانفیگی‌اند؛
QR از تصویر خوانده می‌شود و ضبط دوربین در این نسخه ارائه نشده است.

## سیستم‌عامل هدف

| مورد | محدودهٔ فعلی |
|---|---|
| Windows 10 | نسخهٔ 1809 / build 17763 یا جدیدتر |
| Windows 11 | هدف پشتیبانی x64 |
| معماری بسته و Python | x64 / AMD64 |
| Windows 7/8/8.1 و x86 | خارج از محدودهٔ بستهٔ فعلی |
| ARM64 | بستهٔ بومی ارائه نشده؛ اجرای احتمالی x64 زیر emulation، تضمین TUN/driver نیست |
| محیط ساخت آزموده‌شده | GitHub runner با Windows Server 2022 و Python 3.12 x64 |

حداقل نسخه در `supported_windows()` و `installer.iss` نیز اعمال شده است.
آزمون Server 2022، ادعای آزمایش کامل تمام نسخه‌های مصرف‌کنندهٔ Windows 10/11 نیست.

## استک و هسته‌ها

| بخش | فناوری / نسخه |
|---|---|
| زبان و محیط ساخت | Python `3.12` x64 در CI |
| UI | PyQt6 و Qt `6.10.2`، QtWidgets، QPainter و Geologica |
| lifecycle و تست شبکه | QProcess/QTimer، QtNetwork، SOCKS5 و HTTPS |
| HTTP bridge | asyncio، HTTP/CONNECT روی loopback |
| QR | Pillow، zxing-cpp `3.1.1`؛ qrcode در آزمون‌ها |
| پراکسی سیستم | WinINET connection options از طریق ctypes |
| مجوز و containment | UAC / ShellExecuteW، Windows Job Object |
| TUN و DNS | sing-box `1.12.12`، Wintun `0.14.1`، DoH داخل پراکسی |
| هستهٔ Aether | انتشار رسمی `2.4.0` برای Windows x64، همراه Psiphon و Lyrebird |
| هستهٔ Xray | انتشار رسمی `26.3.27` و geodata همان بسته |
| خروجی | PyInstaller `6.22.0`؛ Inno Setup 6؛ ZIP و Setup EXE |

آرشیوهای دانلودی و فایل‌های هسته SHA256 ثابت دارند. Wintun، DLL امضاشدهٔ
رسمی است؛ این به معنی امضاشدن تجاری خود TeslaVpn.exe یا Setup نیست.

## معماری مخصوص ویندوز

### System proxy

`WinInet` گزینه‌های واقعی اتصال کاربر، شامل flags مربوط به PAC و WPAD، را
می‌خواند؛ صرفاً یک کلید حدسی `AutoDetect` در رجیستری تغییر نمی‌کند.
`SystemProxy` وضعیت قبلی را اتمی ذخیره می‌کند، پراکسی جدید را اعمال می‌کند و
هنگام قطع/بازیابی آن را بازمی‌گرداند. تغییر مستقل کاربر در طول اتصال حفظ می‌شود.

این تنظیمات، WinINET کاربر فعلی است؛ WinHTTP و برنامه‌های با تنظیم پراکسی مستقل
الزاماً از آن پیروی نمی‌کنند. پورت HTTP bridge پیش از اعلام connected باید واقعاً
آماده شده باشد؛ شروع موفق process به‌تنهایی کافی نیست.

### System VPN / TUN

اگر کاربر مدیر نباشد، انتخاب اتصال TUN، برنامه را با `runas` و تأیید UAC دوباره
اجرا می‌کند؛ مسیر state و انتظار خروج نمونهٔ قبلی منتقل می‌شوند تا lock تداخل نکند.
**در این طرح کل برنامه با دسترسی مدیر اجرا می‌شود**؛ برخلاف لینوکس، هسته‌ها
در همین مسیر به UID کاربر عادی downgrade نمی‌شوند.

سرپرست، backend و sing-box را داخل Job Object با `KILL_ON_JOB_CLOSE` اجرا می‌کند.
routeهای sing-box فقط مسیر دقیق executableهای بسته‌شدهٔ Aether، Xray، Psiphon و
Lyrebird را مستثنا می‌کنند. DoH از خروجی proxy می‌رود و port 53 به DNS داخلی
هدایت می‌شود. `GetBestInterfaceEx` مسیر IPv4 و IPv6 را بررسی می‌کند؛ سپس GUI
درخواست HTTPS بدون پراکسی را برای اثبات مسیر سیستم می‌فرستد.

سرپرست روی EOF یا فرمان stop پایان می‌یابد. Job Object جلوی باقی‌ماندن childها
را می‌گیرد؛ در Proxy، بازیابی تنظیمات با بسته‌شدن stdin والد نیز تلاش می‌شود.
شکست بازیابی، snapshot را برای اجرای بعدی نگه می‌دارد.

## دادهٔ خصوصی و قالب‌ها

مسیر state: `%LOCALAPPDATA%\TeslaVpn`، با ACL کاربر جاری، SYSTEM و Administrators.
فایل‌های account و profile و proxy-recovery نباید داخل installer یا ZIP قرار بگیرند.
نام یا مسیر کاربر ویندوز ممکن است Unicode باشد؛ فایل JSON پروفایل با UTF-8 خوانده می‌شود.

قالب‌های ورود همان مجموعهٔ محدود دسکتاپ‌اند: Aether WG/MASQUE تک‌مرحله‌ای،
خروجی Nekoray پروژه با هویت، Psiphon اختیاری، لینک‌های VLESS/VMess/Trojan/SS/SOCKS،
JSON سازگار با هستهٔ Xray و WireGuard conf. `.arasc`، Tor مستقل و کل قابلیت‌های
هستهٔ سفارشی Android به‌طور خودکار به این محصول منتقل نشده‌اند.

## توسعه و ساخت در ویندوز

از ریشهٔ برنچ با Python 3.12 x64:

```powershell
powershell -ExecutionPolicy Bypass -File windows/setup.ps1
powershell -ExecutionPolicy Bypass -File windows/run.ps1
& ./windows/.venv/Scripts/python.exe -m unittest discover -s windows/tests -v
powershell -ExecutionPolicy Bypass -File windows/build.ps1
```

برای نصب‌کننده، Inno Setup 6 نیز لازم است؛ `ISCC.exe windows/installer.iss` را
پس از ساخت portable اجرا کنید. اسکریپت CI هر مرحله را همراه کنترل exit code انجام می‌دهد.
`TeslaVpn.spec` فایل صریح PyInstaller است؛ حذف آن و بازگشت بی‌بررسی به تولید
CLI می‌تواند خطای quoting گزینهٔ `hide_console` را برگرداند.

### ساخت از میزبان لینوکسی

فایل EXE این پروژه با PyInstaller روی Windows ساخته می‌شود. گردش‌کار
`.github/workflows/windows.yml` با Push تغییرات مربوط در `Windows-Client`، ماشین
Windows را فراهم می‌کند. رویداد `workflow_dispatch` نیز در فایل تعریف شده؛
دردسترس‌بودن اجرای دستی و ref انتخابی در تنظیمات Actions جدا بررسی شود. نصب
ویندوز روی رایانهٔ توسعه‌دهنده شرط ساخت نیست؛ تنظیم حساب/مجوز/سهمیهٔ Actions
همچنان لازم است.

خروجی‌های محلی/دریافت‌شده:

```text
artifacts/windows/TeslaVpn-1.0.0-Windows-x64.zip
artifacts/windows/TeslaVpn-1.0.0-Windows-x64-Setup.exe
artifacts/windows/SHA256SUMS
```

ZIP را کامل استخراج کنید؛ `_internal` را از EXE جدا نکنید. نصب‌کننده در مسیر
کاربر نصب می‌شود و برای نصب اولیه مدیر نمی‌خواهد؛ اتصال TUN جداگانه UAC می‌خواهد.

## وضعیت آزمون

[اجرای ثبت‌شدهٔ GitHub Actions](https://github.com/sadrarahbar/ArasClient/actions/runs/41363810261)
با موفقیت پایان یافته و شامل این موارد بوده است:

- هر ۲۴ تست، از جمله API واقعی WinINET و Job Object.
- اجرای executableهای رسمی و پذیرش کانفیگ توسط sing-box.
- ایجاد و حذف آداپتور Wintun؛ بدون تغییر مسیر پیش‌فرض runner.
- عبور واقعی درخواست محلی از HTTP bridge و Xray/SOCKS و بسته‌شدن listenerها روی EOF.
- اجرای UI بسته‌بندی‌شده و بررسی نبود فایل خصوصی در بسته.
- نصب Setup، اجرای برنامهٔ نصب‌شده و حذف آن.

**اتصال VPN واقعی با هویت کاربر روی Windows 10/11 هنوز ثبت نشده است.**
این شکاف آزمون، اولویت قبل از انتشار عمومی است؛ به‌خصوص UAC، تغییر شبکه، DNS،
IPv6 و برنامه‌هایی که پراکسی سیستم را نادیده می‌گیرند.

## منابع کد

- [UAC، ACL و Job Object](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/tesla_vpn/win32.py)
- [WinINET و بازیابی](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/tesla_vpn/system_proxy.py)
- [مسیریابی و بررسی interface](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/tesla_vpn/tun.py)
- [نصب‌کننده و حداقل OS](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/windows/installer.iss)
- [ساخت و آزمون واقعی روی Windows runner](https://github.com/sadrarahbar/ArasClient/blob/a3d070650bde142f5031641afa21808f87080a56/.github/workflows/windows.yml)
