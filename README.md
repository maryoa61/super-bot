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

## فروشگاه محتوا (ماژول مجزا)

فروش فایل/محتوای دیجیتال (ebook، template، ویدیو) — کالای نامحدود، هر بار خرید همون فایل/لینک دوباره تحویل داده می‌شه.

- **کاتالوگ:** `core/models/content.py` (مدل `ContentProduct`، نوع تحویل `file` یا `link`)
- **پرداخت:** `ContentPaymentIntent` جدا، payload به‌شکل `contentintent:<id>`
- **تحویل:** آنی — همون لحظه‌ی پرداخت موفق، فایل (با `file_id` ذخیره‌شده) یا لینک ارسال می‌شه

فعال/غیرفعال: `CONTENT_STORE_ENABLED` در `.env`.

| دستور | کاربر |
|---|---|
| `/content` | همه — لیست محصولات فعال |
| `/content_add_link <price>\|<title>\|<description>\|<url>` | فقط ادمین |
| `/content_add_file <price>\|<title>\|<description>` (به‌صورت caption یه فایل/ویدیو/عکس آپلودی) | فقط ادمین |
| `/content_disable <product_id>` | فقط ادمین |

## فروشگاه لایسنس / اکانت آماده (ماژول مجزا)

فروش کلید لایسنس یا اکانت آماده (SaaS keys، game accounts) — کالای موجودی‌محور؛ هر آیتم فقط یک‌بار فروخته می‌شه.

- **کاتالوگ:** `core/models/licenses.py` (مدل `LicenseProduct` + `LicenseStockItem`)
- **پرداخت:** `LicensePaymentIntent` جدا، payload به‌شکل `licenseintent:<id>`
- **تحویل:** بعد از پرداخت موفق، یه آیتم از استوک به‌صورت **اتمیک** (یه دستور `UPDATE ... WHERE id = (SELECT ... LIMIT 1)`) claim و برای خریدار ارسال می‌شه — دو خریدار هم‌زمان هرگز یه کلید مشترک نمی‌گیرن. اگه دقیقاً هم‌زمان با تمام‌شدن موجودی این اتفاق بیفته (خیلی نادر)، به ادمین‌ها هشدار داده می‌شه.

فعال/غیرفعال: `LICENSE_STORE_ENABLED` در `.env`.

| دستور | کاربر |
|---|---|
| `/licenses` | همه — لیست محصولات فعال + موجودی |
| `/license_add_product <price>\|<title>\|<description>\|<category>` | فقط ادمین |
| `/license_add_stock <product_id>\|<secret_data>` (هر بار یه آیتم) | فقط ادمین |
| `/license_disable <product_id>` | فقط ادمین |
| `/license_stock_count <product_id>` | فقط ادمین |

## فروشگاه کارت هدیه / ووچر دیجیتال (ماژول مجزا)

از نظر منطق دقیقاً مثل فروشگاه لایسنسه (موجودی‌محور، claim اتمیک)، فقط جدول‌ها و هندلر جداگانه دارن چون قرار بود هر فروشگاه کاملاً مستقل باشه.

- **کاتالوگ:** `core/models/giftcards.py` (مدل `GiftCardProduct` + `GiftCardStockItem`)
- **پرداخت:** `GiftCardPaymentIntent` جدا، payload به‌شکل `giftcardintent:<id>`

فعال/غیرفعال: `GIFTCARD_STORE_ENABLED` در `.env`.

| دستور | کاربر |
|---|---|
| `/giftcards` | همه — لیست کارت‌های فعال + موجودی |
| `/giftcard_add_product <price>\|<title>\|<description>\|<value_label>` | فقط ادمین |
| `/giftcard_add_stock <product_id>\|<code>` (هر بار یه کد) | فقط ادمین |
| `/giftcard_disable <product_id>` | فقط ادمین |
| `/giftcard_stock_count <product_id>` | فقط ادمین |

## منوی دائمی ربات

`/start` یه `ReplyKeyboardMarkup` ثابت (نه inline زیر یه پیام) نشون می‌ده که همیشه پایین صفحه می‌مونه: کیف پول، خرید تست VPN، و دکمه‌ی هر فروشگاهی که فعاله. هیچ جدول/داده‌ی جدیدی نمی‌سازه، فقط دکمه‌ها همون توابع `/buy`, `/vps`, `/content`, `/licenses`, `/giftcards` رو صدا می‌زنن.

## نکات امنیتی

- `.env` هیچ‌وقت commit نمی‌شه (در `.gitignore` هست)
- `wallet_ledger` جدول append-only هست — موجودی همیشه از جمع ردیف‌ها محاسبه می‌شه، هیچ‌جا ستون balance مستقل ذخیره نمی‌شه
- `PaymentIntent` قبل از هر پرداخت ساخته می‌شه؛ در `successful_payment` چک می‌شه intent قبلاً success نشده باشه تا از دابل-کردیت جلوگیری بشه
