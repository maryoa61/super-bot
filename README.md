# VPN Telegram Bot

بات تلگرامی فروش اشتراک VPN — پرداخت چند‌درگاهی (Stars, OxaPay, ZarinPal, کارت‌به‌کارت) و اتصال به پنل‌های Marzban/3x-ui.

## استک

- Python 3.11+
- [aiogram 3](https://docs.aiogram.dev/) — فریم‌ورک بات
- SQLAlchemy 2.0 (async) — ORM
- SQLite برای توسعه (قابل تعویض با Postgres از طریق `DATABASE_URL`)

## ساختار پروژه

```
core/models/     مدل‌های دیتابیس (User, WalletLedger, PaymentIntent)
gateways/        الگوی adapter برای درگاه‌های پرداخت (base.py + هر گیت‌وی)
handlers/        هندلرهای aiogram (start, wallet/purchase)
middlewares.py   تزریق session دیتابیس به هر آپدیت
db.py            اتصال و مقداردهی اولیه دیتابیس
config.py        تنظیمات مبتنی بر متغیرهای محیطی
main.py          نقطه‌ی ورود بات
```

## راه‌اندازی

```bash
git clone <repo-url>
cd vpn_bot
python -m venv .venv
source .venv/bin/activate       # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# BOT_TOKEN و بقیه مقادیر رو توی .env پر کن

python main.py
```

## وضعیت درگاه‌های پرداخت

| درگاه       | وضعیت           |
|-------------|-----------------|
| Telegram Stars | ✅ کامل و کارکردی |
| OxaPay (کریپتو) | 🚧 stub — پیاده‌سازی نشده |
| ZarinPal (ریال) | ⏳ برنامه‌ریزی‌شده |
| کارت‌به‌کارت      | ⏳ برنامه‌ریزی‌شده |

اضافه کردن درگاه جدید یعنی: یک کلاس در `gateways/` که `PaymentGateway` (در `gateways/base.py`) رو پیاده‌سازی می‌کنه، بعد یک خط در رجیستری `gateways/__init__.py`. کد handlers/models نیازی به تغییر نداره.

## نکات امنیتی

- `.env` هیچ‌وقت commit نمی‌شه (در `.gitignore` هست)
- `wallet_ledger` جدول append-only هست — موجودی همیشه از جمع ردیف‌ها محاسبه می‌شه، هیچ‌جا ستون balance مستقل ذخیره نمی‌شه
- `PaymentIntent` قبل از هر پرداخت ساخته می‌شه؛ در `successful_payment` چک می‌شه intent قبلاً success نشده باشه تا از دابل-کردیت جلوگیری بشه
