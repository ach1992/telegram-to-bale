<p align="center"><a href="./README.md">English</a></p>

# ربات انتقال محتوا از تلگرام به بله

یک سرویس پایتونی مناسب استفاده عملیاتی که کانال‌های مشخص تلگرام را با یک نشست کاربری مانیتور می‌کند و پیام متنی، تصویر، ویدیو و فایل را از طریق API ربات بله به کانال مقصد می‌فرستد.

## امکانات اصلی

- انتقال متن، تصویر، ویدیو و سند
- صف پردازش محدود برای جلوگیری از متوقف‌شدن event loop تلگرام
- `timeout` شبکه، `exponential backoff` و retry برای خطاهای موقت و rate limit
- تقسیم خودکار متن‌های طولانی
- ساخت تصویر پیش‌نمایش با `ffmpeg` در صورت شکست ارسال ویدیو
- اجرای سرویس با کاربر محدود و اختصاصی `tg2bale` به‌جای `root`
- نصب تکرارپذیر، migration نصب قدیمی و rollback در صورت شکست
- نگهداری امن تنظیمات در `/etc` و session در `/var/lib`
- ابزار خط فرمان برای وضعیت، لاگ، restart، عیب‌یابی و حذف امن
- تست CI روی نسخه‌های پشتیبانی‌شده Debian و Ubuntu

## سیستم‌عامل‌های پشتیبانی‌شده

- Debian 12 و جدیدتر
- Ubuntu 22.04 LTS و جدیدتر
- Python 3.10 و جدیدتر

ماتریس CI فعلی Debian 12/13 و Ubuntu 22.04/24.04/26.04 را بررسی می‌کند.

## اطلاعات موردنیاز

- `API_ID` و `API_HASH` تلگرام از `my.telegram.org`
- شماره تلگرامی که به تمام کانال‌های مبدا دسترسی دارد
- توکن ربات بله
- شناسه کانال مقصد بله
- افزودن ربات بله به کانال مقصد با دسترسی کافی

## نصب سریع

برای حفظ حالت تعاملی نصب، دستور زیر را اجرا کنید:

```bash
sudo bash -c 'bash <(curl -fsSL https://raw.githubusercontent.com/ach1992/telegram-to-bale/main/install.sh)'
```

نصب‌کننده این کارها را انجام می‌دهد:

1. سازگاری سیستم‌عامل را بررسی می‌کند.
2. بسته‌های لازم مانند `python3-venv` و `ffmpeg` را نصب می‌کند.
3. برنامه را در `/opt/telegram-to-bale` قرار می‌دهد.
4. کاربر سیستمی محدود `tg2bale` را می‌سازد.
5. اطلاعات حساس را با دسترسی محدود در `/etc/telegram-to-bale.env` ذخیره می‌کند.
6. session تلگرام را در `/var/lib/tg2bale` می‌سازد.
7. سرویس `tg2bale.service` را نصب و اجرا می‌کند.
8. فرمان سراسری `teltobale` را نصب می‌کند.

اجرای دوباره همین دستور، برنامه را به‌روزرسانی می‌کند و تنظیمات و session قبلی را نگه می‌دارد. اگر نصب قدیمی دارای `.env` و `session.session` محلی باشد و unit قبلی systemd قابل تشخیص باشد، migration خودکار انجام می‌شود.

### نصب غیرتعاملی

برای نصب اولیه می‌توان تنظیمات را از environment ارسال کرد. ایجاد session تلگرام همچنان تعاملی است، مگر اینکه از `--skip-auth` استفاده شود.

```bash
sudo env \
  API_ID='12345' \
  API_HASH='replace-me' \
  BALE_BOT_TOKEN='replace-me' \
  BALE_CHAT_ID='replace-me' \
  SOURCE_CHANNELS='@channel_one,@channel_two' \
  bash -c 'bash <(curl -fsSL https://raw.githubusercontent.com/ach1992/telegram-to-bale/main/install.sh) --non-interactive --skip-auth'
```

احراز هویت در مرحله بعد:

```bash
sudo -u tg2bale /opt/telegram-to-bale/.venv/bin/python \
  /opt/telegram-to-bale/authenticate.py \
  --env-file /etc/telegram-to-bale.env
sudo systemctl restart tg2bale.service
```

## مدیریت سرویس

```bash
teltobale status
sudo teltobale start
sudo teltobale stop
sudo teltobale restart
teltobale logs -n 200
teltobale logs --follow
sudo teltobale doctor
```

دستورات مستقیم systemd:

```bash
sudo systemctl status tg2bale.service
sudo journalctl -u tg2bale.service -n 100 --no-pager
```

## تنظیمات

فایل production در مسیر `/etc/telegram-to-bale.env` قرار دارد.

| متغیر | اجباری | پیش‌فرض | کاربرد |
|---|---:|---:|---|
| `API_ID` | بله | - | شناسه اپلیکیشن تلگرام |
| `API_HASH` | بله | - | هش اپلیکیشن تلگرام |
| `BALE_BOT_TOKEN` | بله | - | توکن ربات بله |
| `BALE_CHAT_ID` | بله | - | شناسه کانال یا چت مقصد بله |
| `SOURCE_CHANNELS` | بله | - | کانال‌های تلگرام با جداکننده کاما |
| `TG2BALE_DATA_DIR` | خیر | `/var/lib/tg2bale` در production | مسیر session و فایل‌های موقت |
| `TG2BALE_REQUEST_TIMEOUT` | خیر | `120` | timeout خواندن پاسخ بله برحسب ثانیه |
| `TG2BALE_MAX_RETRIES` | خیر | `3` | تعداد تلاش ارسال، بین ۱ تا ۱۰ |
| `TG2BALE_RETRY_BASE_SECONDS` | خیر | `1` | زمان پایه backoff |
| `TG2BALE_WORKERS` | خیر | `1` | تعداد worker بین ۱ تا ۸؛ مقدار ۱ ترتیب کلی را حفظ می‌کند |
| `TG2BALE_QUEUE_SIZE` | خیر | `100` | حداکثر پیام‌های منتظر در صف |
| `TG2BALE_TEXT_LIMIT` | خیر | `4096` | اندازه هر بخش متن ارسالی |
| `TG2BALE_LOG_LEVEL` | خیر | `INFO` | سطح logging |

بعد از ویرایش تنظیمات:

```bash
sudo chmod 0640 /etc/telegram-to-bale.env
sudo chown root:tg2bale /etc/telegram-to-bale.env
sudo teltobale doctor
sudo teltobale restart
```

## توسعه محلی

```bash
git clone https://github.com/ach1992/telegram-to-bale.git
cd telegram-to-bale
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup.py
.venv/bin/python authenticate.py
.venv/bin/python main.py
```

اجرای تست‌ها:

```bash
python3 -m compileall -q main.py authenticate.py cli.py setup.py tests
python3 -m unittest discover -s tests -v
bash tests/test_scripts.sh
```

## حذف برنامه

حذف برنامه با نگهداری تنظیمات و session برای نصب مجدد:

```bash
sudo teltobale uninstall
```

حذف دائمی برنامه، تنظیمات، session و کاربر سرویس:

```bash
sudo teltobale uninstall --purge
```

## عیب‌یابی

ابتدا diagnostic را اجرا کنید:

```bash
sudo teltobale doctor
```

سپس لاگ‌ها را ببینید:

```bash
teltobale logs -n 200
```

دلایل رایج شامل session احراز هویت‌نشده، نداشتن دسترسی به کانال مبدا، توکن یا chat ID اشتباه بله، دسترسی ناکافی ربات در کانال مقصد، محدودیت شبکه، rate limit یا ردشدن فرمت رسانه توسط API مقصد است.

## نکات امنیتی

- سرویس با `root` اجرا نمی‌شود.
- اطلاعات حساس خارج از پوشه برنامه و با mode برابر `0640` نگهداری می‌شوند.
- unit سرویس محدودیت‌های filesystem، privilege، namespace، kernel و capability دارد.
- session و فایل‌های موقت در `/var/lib/tg2bale` قرار می‌گیرند.
- فایل‌های `.env` و `.session` را هرگز commit نکنید.

## مجوز

MIT License، Copyright 2025-2026 ach1992.
