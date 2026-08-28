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

## فروشگاه VPS (ماژول مجزا)

یه ماژول کاملاً مستقل برای فروش پلن‌های آماده‌ی VPS، بدون هیچ وابستگی به جدول‌ها یا هندلرهای فلوی تستی VPN بالا:

- **کاتالوگ:** `core/models/vps.py` (مدل `VpsPlan`)
- **پرداخت:** intent‌های خودش رو جدا نگه می‌داره (`VpsPaymentIntent`) و فاکتور Stars رو مستقیم با payload به‌شکل `vpsintent:<id>` می‌سازه — به `PaymentIntent`/`WalletLedger` موجود دست نمی‌زنه.
- **تحویل:** خودکار/API پنل هایپروایزر نداره؛ بعد از پرداخت موفق سفارش (`VpsOrder`) با وضعیت `pending_provision` ساخته می‌شه، ادمین‌ها نوتیف می‌گیرن، و ادمین با `/vps_fulfill` مشخصات سرور رو دستی وارد و برای خریدار ارسال می‌کنه.

فعال/غیرفعال بودنش با `VPS_STORE_ENABLED` توی `.env` کنترل می‌شه (پیش‌فرض: فعال). اگه `false` باشه، روتر `handlers/vps.py` اصلاً include نمی‌شه.

جدول‌های `vps_plans`, `vps_payment_intents`, `vps_orders` نیازی به مایگریشن دستی ندارن — چون `db.py` با `Base.metadata.create_all` روی استارت اجرا می‌شه، همون اولین بار که بات بالا میاد ساخته می‌شن.

### دستورات

| دستور | کاربر |
|---|---|
| `/vps` | همه — لیست پلن‌های فعال با دکمه‌ی خرید |
| `/vps_add_plan <price>\|<title>\|<cpu_cores>\|<ram_gb>\|<disk_gb>\|<location>\|<duration_days>` | فقط ادمین (`ADMIN_IDS`) |
| `/vps_disable_plan <plan_id>` | فقط ادمین |
| `/vps_orders` | فقط ادمین — سفارش‌های در انتظار تحویل |
| `/vps_fulfill <order_id> <مشخصات سرور>` | فقط ادمین — تحویل سفارش + DM به خریدار |

## نکات امنیتی

- `.env` هیچ‌وقت commit نمی‌شه (در `.gitignore` هست)
- `wallet_ledger` جدول append-only هست — موجودی همیشه از جمع ردیف‌ها محاسبه می‌شه، هیچ‌جا ستون balance مستقل ذخیره نمی‌شه
- `PaymentIntent` قبل از هر پرداخت ساخته می‌شه؛ در `successful_payment` چک می‌شه intent قبلاً success نشده باشه تا از دابل-کردیت جلوگیری بشه
