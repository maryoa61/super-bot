"""
Web admin panel for super-bot.

A small Flask app that talks to the SAME sqlite database the bot uses, so
you can manage plans/products from a browser instead of Telegram commands.

Run (from the project root, with the venv active):
    pip install flask
    python admin_panel.py
or via systemd: super-bot-admin.service

Auth: a single password from ADMIN_PANEL_PASSWORD in .env (falls back to a
random value printed at startup if unset). Sessions last 8h.
"""

import os
import secrets
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from config import settings
from core.models import (
    ContentDeliveryType,
    ContentProduct,
    GiftCardProduct,
    GiftCardStockItem,
    LicenseProduct,
    LicenseStockItem,
    VpsPlan,
)

# --- sync engine to the same db file the bot uses -------------------------
def _sync_db_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite+aiosqlite:///"):
        return "sqlite:///" + url.replace("sqlite+aiosqlite:///", "", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return "sqlite://" + url[len("sqlite+aiosqlite://"):]
    return url  # assume already sync-safe


engine = create_engine(
    _sync_db_url(),
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
# enable WAL so the panel and the bot don't lock each other out
with engine.connect() as _c:
    _c.exec_driver_sql("PRAGMA journal_mode=WAL")
    _c.exec_driver_sql("PRAGMA busy_timeout=5000")

Session = sessionmaker(bind=engine)

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_PANEL_SECRET", secrets.token_hex(32))

ADMIN_PASSWORD = os.environ.get("ADMIN_PANEL_PASSWORD")
if ADMIN_PASSWORD is None:
    ADMIN_PASSWORD = secrets.token_hex(8)
    print(f"[admin-panel] ADMIN_PANEL_PASSWORD not set; generated: {ADMIN_PASSWORD}")

PORT = int(os.environ.get("ADMIN_PANEL_PORT", "8000"))


# --- auth -----------------------------------------------------------------
def _logged_in() -> bool:
    return bool(session.get("auth"))


@app.before_request
def _require_auth():
    # login route is public
    if request.endpoint in ("login", "static"):
        return
    if not _logged_in():
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["auth"] = True
            return redirect(url_for("dashboard"))
        return render_template_string(LOGIN_TPL, error="رمز عبور اشتباهه.")
    return render_template_string(LOGIN_TPL, error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- dashboard ------------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template_string(DASH_TPL)


# --- VPS ------------------------------------------------------------------
@app.route("/vps", methods=["GET", "POST"])
def vps():
    with Session() as s:
        if request.method == "POST":
            f = request.form
            s.add(
                VpsPlan(
                    title=f["title"],
                    cpu_cores=int(f["cpu_cores"]),
                    ram_gb=int(f["ram_gb"]),
                    disk_gb=int(f["disk_gb"]),
                    location=f["location"],
                    duration_days=int(f["duration_days"]),
                    price=int(f["price"]),
                    is_active=True,
                )
            )
            s.commit()
            return redirect(url_for("vps"))
        plans = s.execute(select(VpsPlan).order_by(VpsPlan.id)).scalars().all()
    return render_template_string(VPS_TPL, plans=plans)


@app.route("/vps/disable/<int:plan_id>", methods=["POST"])
def vps_disable(plan_id: int):
    with Session() as s:
        p = s.get(VpsPlan, plan_id)
        if p:
            p.is_active = False
            s.commit()
    return redirect(url_for("vps"))


# --- Content --------------------------------------------------------------
@app.route("/content", methods=["GET", "POST"])
def content():
    with Session() as s:
        if request.method == "POST":
            f = request.form
            s.add(
                ContentProduct(
                    title=f["title"],
                    description=f["description"],
                    price=int(f["price"]),
                    delivery_type=ContentDeliveryType.LINK,
                    url=f["url"],
                    is_active=True,
                )
            )
            s.commit()
            return redirect(url_for("content"))
        items = s.execute(select(ContentProduct).order_by(ContentProduct.id)).scalars().all()
    return render_template_string(CONTENT_TPL, items=items)


@app.route("/content/disable/<int:pid>", methods=["POST"])
def content_disable(pid: int):
    with Session() as s:
        p = s.get(ContentProduct, pid)
        if p:
            p.is_active = False
            s.commit()
    return redirect(url_for("content"))


# --- License --------------------------------------------------------------
@app.route("/licenses", methods=["GET", "POST"])
def licenses():
    with Session() as s:
        if request.method == "POST":
            f = request.form
            if f.get("action") == "stock":
                s.add(
                    LicenseStockItem(
                        product_id=int(f["product_id"]),
                        secret_data=f["secret_data"],
                    )
                )
            else:
                s.add(
                    LicenseProduct(
                        title=f["title"],
                        description=f["description"],
                        category=f["category"],
                        price=int(f["price"]),
                        is_active=True,
                    )
                )
            s.commit()
            return redirect(url_for("licenses"))
        products = s.execute(select(LicenseProduct).order_by(LicenseProduct.id)).scalars().all()
    return render_template_string(LICENSE_TPL, products=products)


@app.route("/licenses/disable/<int:pid>", methods=["POST"])
def licenses_disable(pid: int):
    with Session() as s:
        p = s.get(LicenseProduct, pid)
        if p:
            p.is_active = False
            s.commit()
    return redirect(url_for("licenses"))


# --- Gift cards -----------------------------------------------------------
@app.route("/giftcards", methods=["GET", "POST"])
def giftcards():
    with Session() as s:
        if request.method == "POST":
            f = request.form
            if f.get("action") == "stock":
                s.add(
                    GiftCardStockItem(
                        product_id=int(f["product_id"]),
                        code=f["code"],
                    )
                )
            else:
                s.add(
                    GiftCardProduct(
                        title=f["title"],
                        description=f["description"],
                        value_label=f["value_label"],
                        price=int(f["price"]),
                        is_active=True,
                    )
                )
            s.commit()
            return redirect(url_for("giftcards"))
        products = s.execute(select(GiftCardProduct).order_by(GiftCardProduct.id)).scalars().all()
    return render_template_string(GIFTCARD_TPL, products=products)


@app.route("/giftcards/disable/<int:pid>", methods=["POST"])
def giftcards_disable(pid: int):
    with Session() as s:
        p = s.get(GiftCardProduct, pid)
        if p:
            p.is_active = False
            s.commit()
    return redirect(url_for("giftcards"))


# --- templates ------------------------------------------------------------
LOGIN_TPL = """<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;direction:rtl">
<h2>ورود پنل مدیریت</h2>
{% if error %}<p style=color:red>{{error}}</p>{% endif %}
<form method=post><input type=password name=password placeholder=رمز عبور>
<button>ورود</button></form></body>"""

DASH_TPL = """<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;direction:rtl">
<h2>پنل مدیریت super-bot</h2>
<p><a href=/logout>خروج</a></p>
<ul>
<li><a href=/vps>🖥 فروشگاه VPS</a></li>
<li><a href=/content>📚 فروشگاه محتوا</a></li>
<li><a href=/licenses>🔑 فروشگاه لایسنس</a></li>
<li><a href=/giftcards>🎁 فروشگاه گیفت‌کارت</a></li>
</ul></body>"""

VPS_TPL = """<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;direction:rtl">
<h2>🖥 فروشگاه VPS</h2><p><a href=/>بازگشت</a></p>
<form method=post>
عنوان <input name=title><br>
قیمت (استارز) <input name=price><br>
هسته CPU <input name=cpu_cores><br>
RAM (GB) <input name=ram_gb><br>
دیسک (GB) <input name=disk_gb><br>
لوکیشن <input name=location><br>
مدت (روز) <input name=duration_days><br>
<button>افزودن پلن</button></form>
<hr><table border=1 cellpadding=5>
<tr><th>id</th><th>عنوان</th><th>قیمت</th><th>فعال</th><th></th></tr>
{% for p in plans %}<tr>
<td>{{p.id}}</td><td>{{p.title}}</td><td>{{p.price}}</td>
<td>{{'بله' if p.is_active else 'خیر'}}</td>
<td>{% if p.is_active %}<form method=post action=/vps/disable/{{p.id}}><button>غیرفعال</button></form>{% endif %}</td>
</tr>{% endfor %}</table></body>"""

CONTENT_TPL = """<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;direction:rtl">
<h2>📚 فروشگاه محتوا</h2><p><a href=/>بازگشت</a></p>
<form method=post>
عنوان <input name=title><br>
توضیح <input name=description><br>
قیمت (استارز) <input name=price><br>
لینک <input name=url><br>
<button>افزودن (لینک)</button></form>
<hr><table border=1 cellpadding=5>
<tr><th>id</th><th>عنوان</th><th>قیمت</th><th>فعال</th><th></th></tr>
{% for p in items %}<tr>
<td>{{p.id}}</td><td>{{p.title}}</td><td>{{p.price}}</td>
<td>{{'بله' if p.is_active else 'خیر'}}</td>
<td>{% if p.is_active %}<form method=post action=/content/disable/{{p.id}}><button>غیرفعال</button></form>{% endif %}</td>
</tr>{% endfor %}</table></body>"""

LICENSE_TPL = """<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;direction:rtl">
<h2>🔑 فروشگاه لایسنس</h2><p><a href=/>بازگشت</a></p>
<h3>محصول جدید</h3>
<form method=post>
عنوان <input name=title><br>
توضیح <input name=description><br>
دسته <input name=category><br>
قیمت (استارز) <input name=price><br>
<button>افزودن محصول</button></form>
<h3>اضافه کردن استوک</h3>
<form method=post>
<input type=hidden name=action value=stock>
محصول id <input name=product_id><br>
کلید/اکانت <input name=secret_data><br>
<button>افزودن استوک</button></form>
<hr><table border=1 cellpadding=5>
<tr><th>id</th><th>عنوان</th><th>قیمت</th><th>فعال</th><th></th></tr>
{% for p in products %}<tr>
<td>{{p.id}}</td><td>{{p.title}}</td><td>{{p.price}}</td>
<td>{{'بله' if p.is_active else 'خیر'}}</td>
<td>{% if p.is_active %}<form method=post action=/licenses/disable/{{p.id}}><button>غیرفعال</button></form>{% endif %}</td>
</tr>{% endfor %}</table></body>"""

GIFTCARD_TPL = """<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;direction:rtl">
<h2>🎁 فروشگاه گیفت‌کارت</h2><p><a href=/>بازگشت</a></p>
<h3>محصول جدید</h3>
<form method=post>
عنوان <input name=title><br>
توضیح <input name=description><br>
ارزش (مثلاً $25) <input name=value_label><br>
قیمت (استارز) <input name=price><br>
<button>افزودن محصول</button></form>
<h3>اضافه کردن کد</h3>
<form method=post>
<input type=hidden name=action value=stock>
محصول id <input name=product_id><br>
کد <input name=code><br>
<button>افزودن کد</button></form>
<hr><table border=1 cellpadding=5>
<tr><th>id</th><th>عنوان</th><th>قیمت</th><th>فعال</th><th></th></tr>
{% for p in products %}<tr>
<td>{{p.id}}</td><td>{{p.title}}</td><td>{{p.price}}</td>
<td>{{'بله' if p.is_active else 'خیر'}}</td>
<td>{% if p.is_active %}<form method=post action=/giftcards/disable/{{p.id}}><button>غیرفعال</button></form>{% endif %}</td>
</tr>{% endfor %}</table></body>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
