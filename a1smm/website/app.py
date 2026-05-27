"""
🌐 AlMasry SMM Bot — Website
Flask backend مرتبط بقاعدة بيانات البوت مباشرة
"""

import os
import sys
import hmac
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, g
)
import sqlite3

# ── إضافة مسار البوت للـ imports ──────────────────────────
BOT_DIR = os.environ.get("BOT_DIR", "/root/smmbot-main")
sys.path.insert(0, BOT_DIR)

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
DB_PATH    = os.environ.get("DB_PATH",   os.path.join(BOT_DIR, "data/bot.db"))
SECRET_KEY = os.environ.get("WEB_SECRET", secrets.token_hex(32))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_SECURE"]   = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)


# ══════════════════════════════════════════════════════════════
#  Database helpers
# ══════════════════════════════════════════════════════════════

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def db_one(sql, params=()):
    r = get_db().execute(sql, params).fetchone()
    return dict(r) if r else None


def db_all(sql, params=()):
    return [dict(r) for r in get_db().execute(sql, params).fetchall()]


def db_run(sql, params=()):
    db = get_db()
    db.execute(sql, params)
    db.commit()


def get_setting(key, default=""):
    r = db_one("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


# ══════════════════════════════════════════════════════════════
#  Telegram Login Verification
# ══════════════════════════════════════════════════════════════

def verify_telegram_login(data: dict) -> bool:
    """تحقق من صحة بيانات Telegram Login Widget."""
    check_hash = data.pop("hash", "")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    # التحقق من أن البيانات حديثة (خلال ساعة)
    auth_date = int(data.get("auth_date", 0))
    if datetime.utcnow().timestamp() - auth_date > 3600:
        return False
    return hmac.compare_digest(computed, check_hash)


# ══════════════════════════════════════════════════════════════
#  Auth helpers
# ══════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db_one("SELECT * FROM users WHERE tg_id=?", (uid,))


def get_balance(uid):
    r = db_one("SELECT balance FROM users WHERE tg_id=?", (uid,))
    return float(r["balance"]) if r else 0.0


def get_or_create_api_key(uid):
    r = db_one("SELECT api_key FROM user_api_keys WHERE tg_id=?", (uid,))
    if r:
        return r["api_key"]
    key = "smm_" + secrets.token_urlsafe(32)
    db_run(
        "INSERT OR IGNORE INTO user_api_keys (tg_id, api_key, created_at) VALUES (?,?,?)",
        (uid, key, datetime.utcnow().isoformat())
    )
    return key


def ensure_api_key_table():
    get_db().execute("""
        CREATE TABLE IF NOT EXISTS user_api_keys (
            tg_id      INTEGER PRIMARY KEY,
            api_key    TEXT    UNIQUE NOT NULL,
            created_at TEXT
        )
    """)
    get_db().commit()


# ══════════════════════════════════════════════════════════════
#  Pages
# ══════════════════════════════════════════════════════════════

@app.before_request
def setup():
    ensure_api_key_table()


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    bot_username = get_setting("BOT_USERNAME", "AlMasrySMMBot")
    return render_template("login.html", bot_username=bot_username)


@app.route("/auth/telegram", methods=["POST", "GET"])
def telegram_auth():
    data = dict(request.args or request.form)
    if not data or "hash" not in data:
        return redirect(url_for("login_page"))

    if not verify_telegram_login(dict(data)):
        return render_template("login.html",
            error="❌ فشل التحقق — حاول مرة أخرى.",
            bot_username=get_setting("BOT_USERNAME", ""))

    uid   = int(data["id"])
    fname = data.get("first_name", "")
    uname = data.get("username", "")

    # تسجيل المستخدم في DB لو مش موجود
    db_run(
        "INSERT OR IGNORE INTO users (tg_id, first_name, username, balance, created_at) "
        "VALUES (?,?,?,0.0,?)",
        (uid, fname, uname, datetime.utcnow().isoformat())
    )

    session.permanent = True
    session["user_id"]   = uid
    session["user_name"] = fname
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    uid     = session["user_id"]
    user    = get_current_user()
    balance = get_balance(uid)
    api_key = get_or_create_api_key(uid)

    # إحصائيات
    stats = db_one(
        """SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN status IN ('pending','in progress','processing') THEN 1 ELSE 0 END) as active,
            COALESCE(SUM(price),0) as spent
        FROM orders WHERE user_tg_id=?""",
        (uid,)
    ) or {}

    # آخر 5 طلبات
    orders = db_all(
        """SELECT o.id, o.status, o.quantity, o.price, o.created_at,
                  s.name as service_name
           FROM orders o
           LEFT JOIN services s ON o.service_id=s.id
           WHERE o.user_tg_id=?
           ORDER BY o.id DESC LIMIT 5""",
        (uid,)
    )

    # VIP
    vip = db_one("SELECT discount_pct FROM user_vip WHERE tg_id=?", (uid,))

    # عملة ثانية
    cur2_enabled = get_setting("second_currency_enabled", "0") == "1"
    cur2_name    = get_setting("second_currency_name", "EGP")
    cur2_rate    = float(get_setting("second_currency_rate", "0") or 0)

    return render_template("dashboard.html",
        user=user, balance=balance, api_key=api_key,
        stats=stats, orders=orders, vip=vip,
        cur2_enabled=cur2_enabled, cur2_name=cur2_name, cur2_rate=cur2_rate,
    )


@app.route("/services")
@login_required
def services_page():
    platforms = db_all(
        "SELECT * FROM platforms WHERE is_active=1 ORDER BY sort_order, id"
    )
    categories = db_all(
        "SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order, id"
    )
    services = db_all(
        "SELECT * FROM services WHERE is_active=1 ORDER BY sort_order, id"
    )

    uid = session["user_id"]
    vip = db_one("SELECT discount_pct FROM user_vip WHERE tg_id=?", (uid,))
    discount = float(vip["discount_pct"]) if vip else 0

    cur2_enabled = get_setting("second_currency_enabled", "0") == "1"
    cur2_name    = get_setting("second_currency_name", "EGP")
    cur2_rate    = float(get_setting("second_currency_rate", "0") or 0)

    return render_template("services.html",
        platforms=platforms, categories=categories,
        services=services, discount=discount,
        cur2_enabled=cur2_enabled, cur2_name=cur2_name, cur2_rate=cur2_rate,
    )


@app.route("/orders")
@login_required
def orders_page():
    uid  = session["user_id"]
    page = max(1, int(request.args.get("page", 1)))
    per  = 20
    offset = (page - 1) * per

    orders = db_all(
        """SELECT o.*, s.name as service_name
           FROM orders o
           LEFT JOIN services s ON o.service_id=s.id
           WHERE o.user_tg_id=?
           ORDER BY o.id DESC LIMIT ? OFFSET ?""",
        (uid, per, offset)
    )
    total = (db_one("SELECT COUNT(*) as c FROM orders WHERE user_tg_id=?", (uid,)) or {}).get("c", 0)
    pages = (total + per - 1) // per

    return render_template("orders.html",
        orders=orders, page=page, pages=pages
    )


@app.route("/add-order", methods=["POST"])
@login_required
def add_order():
    uid     = session["user_id"]
    svc_id  = request.form.get("service_id", type=int)
    link    = (request.form.get("link") or "").strip()
    qty     = request.form.get("quantity", type=int)

    if not svc_id or not link or not qty:
        return jsonify({"error": "بيانات ناقصة"}), 400

    svc = db_one("SELECT * FROM services WHERE id=? AND is_active=1", (svc_id,))
    if not svc:
        return jsonify({"error": "الخدمة غير موجودة"}), 404

    if qty < svc["min_qty"] or qty > svc["max_qty"]:
        return jsonify({"error": f"الكمية يجب بين {svc['min_qty']:,} و {svc['max_qty']:,}"}), 400

    # حساب السعر مع VIP
    vip = db_one("SELECT discount_pct FROM user_vip WHERE tg_id=?", (uid,))
    discount   = float(vip["discount_pct"]) if vip else 0
    price_unit = svc["price_per_1000"] / 1000 * (1 - discount / 100)
    price      = round(price_unit * qty, 6)

    balance = get_balance(uid)
    if balance < price:
        return jsonify({"error": f"رصيدك غير كافٍ — المطلوب ${price:.4f}، رصيدك ${balance:.4f}"}), 400

    # إرسال للـ API الخارجي
    try:
        import requests as req
        api_url = get_setting("SMM_API_URL", "https://smmalmasry.xyz/api/v2")
        api_key = get_setting("SMM_API_KEY", "")
        resp = req.post(api_url, data={
            "key":      api_key,
            "action":   "add",
            "service":  svc["api_service_id"],
            "link":     link,
            "quantity": qty,
        }, timeout=15)
        result = resp.json()
        api_order_id = result.get("order")
        if not api_order_id:
            return jsonify({"error": result.get("error", "فشل إرسال الطلب للـ API")}), 500
    except Exception as e:
        return jsonify({"error": "تعذّر الاتصال بالخادم"}), 500

    # خصم الرصيد وحفظ الطلب
    db = get_db()
    db.execute("UPDATE users SET balance = balance - ? WHERE tg_id=?", (price, uid))
    db.execute(
        """INSERT INTO orders
           (user_tg_id, service_id, link, quantity, price, status, api_order_id, created_at)
           VALUES (?,?,?,?,?,'pending',?,?)""",
        (uid, svc_id, link, qty, price, str(api_order_id), datetime.utcnow().isoformat())
    )
    db.commit()

    return jsonify({"success": True, "order_id": api_order_id, "price": price})


@app.route("/profile")
@login_required
def profile_page():
    uid     = session["user_id"]
    user    = get_current_user()
    api_key = get_or_create_api_key(uid)
    vip     = db_one("SELECT * FROM user_vip WHERE tg_id=?", (uid,))
    pts     = db_one("SELECT points FROM user_points WHERE tg_id=?", (uid,))
    balance = get_balance(uid)

    cur2_enabled = get_setting("second_currency_enabled", "0") == "1"
    cur2_name    = get_setting("second_currency_name", "EGP")
    cur2_rate    = float(get_setting("second_currency_rate", "0") or 0)

    return render_template("profile.html",
        user=user, api_key=api_key, vip=vip,
        pts=pts, balance=balance,
        cur2_enabled=cur2_enabled, cur2_name=cur2_name, cur2_rate=cur2_rate,
    )


@app.route("/api/regenerate-key", methods=["POST"])
@login_required
def regenerate_key():
    uid = session["user_id"]
    new_key = "smm_" + secrets.token_urlsafe(32)
    db_run(
        "INSERT OR REPLACE INTO user_api_keys (tg_id, api_key, created_at) VALUES (?,?,?)",
        (uid, new_key, datetime.utcnow().isoformat())
    )
    return jsonify({"key": new_key})


# ══════════════════════════════════════════════════════════════
#  Public API (للمستخدمين بالـ api_key)
# ══════════════════════════════════════════════════════════════

def get_user_by_key(key):
    r = db_one(
        "SELECT u.* FROM users u JOIN user_api_keys k ON u.tg_id=k.tg_id WHERE k.api_key=?",
        (key,)
    )
    return r


@app.route("/api/v1/balance")
def api_balance():
    key  = request.args.get("api_key") or request.headers.get("X-API-Key")
    user = get_user_by_key(key) if key else None
    if not user:
        return jsonify({"error": "API key غير صحيح"}), 401
    return jsonify({
        "balance":  round(float(user["balance"]), 6),
        "currency": "USD"
    })


@app.route("/api/v1/services")
def api_services():
    key  = request.args.get("api_key") or request.headers.get("X-API-Key")
    user = get_user_by_key(key) if key else None
    if not user:
        return jsonify({"error": "API key غير صحيح"}), 401

    services = db_all(
        """SELECT s.id, s.name, s.min_qty, s.max_qty, s.price_per_1000,
                  c.name as category, p.name as platform
           FROM services s
           JOIN categories c ON s.category_id=c.id
           JOIN platforms p ON c.platform_id=p.id
           WHERE s.is_active=1"""
    )
    return jsonify(services)


@app.route("/api/v1/order", methods=["POST"])
def api_order():
    data = request.get_json() or request.form
    key  = data.get("api_key") or request.headers.get("X-API-Key")
    user = get_user_by_key(key) if key else None
    if not user:
        return jsonify({"error": "API key غير صحيح"}), 401

    # delegate to add_order logic
    session["user_id"] = user["tg_id"]
    return add_order()


@app.route("/api/v1/status")
def api_status():
    key      = request.args.get("api_key") or request.headers.get("X-API-Key")
    order_id = request.args.get("order_id")
    user     = get_user_by_key(key) if key else None
    if not user:
        return jsonify({"error": "API key غير صحيح"}), 401

    o = db_one(
        "SELECT * FROM orders WHERE api_order_id=? AND user_tg_id=?",
        (order_id, user["tg_id"])
    )
    if not o:
        return jsonify({"error": "الطلب غير موجود"}), 404

    return jsonify({
        "order_id":   o["api_order_id"],
        "status":     o["status"],
        "quantity":   o["quantity"],
        "price":      o["price"],
        "created_at": o["created_at"],
    })


# ══════════════════════════════════════════════════════════════
#  Error pages
# ══════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("404.html", error="خطأ في الخادم"), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
