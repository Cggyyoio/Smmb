"""
╔══════════════════════════════════════════╗
║     قاعدة البيانات SQLite — database.py ║
╚══════════════════════════════════════════╝
"""

import sqlite3
import logging
import os
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id      INTEGER UNIQUE NOT NULL,
                    username   TEXT,
                    first_name TEXT,
                    balance    REAL    DEFAULT 0.0,
                    is_banned  INTEGER DEFAULT 0,
                    joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS platforms (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT    NOT NULL,
                    emoji      TEXT    DEFAULT '📱',
                    is_active  INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform_id INTEGER NOT NULL,
                    name        TEXT    NOT NULL,
                    emoji       TEXT    DEFAULT '📂',
                    is_active   INTEGER DEFAULT 1,
                    sort_order  INTEGER DEFAULT 0,
                    FOREIGN KEY (platform_id) REFERENCES platforms(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS services (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id    INTEGER NOT NULL,
                    api_service_id INTEGER NOT NULL,
                    name           TEXT    NOT NULL,
                    description    TEXT    DEFAULT '',
                    price_per_1000 REAL    NOT NULL,
                    api_base_price REAL    DEFAULT 0,
                    min_qty        INTEGER NOT NULL,
                    max_qty        INTEGER NOT NULL,
                    speed          TEXT    DEFAULT '',
                    quality        TEXT    DEFAULT '',
                    warranty       TEXT    DEFAULT '',
                    is_active      INTEGER DEFAULT 1,
                    sort_order     INTEGER DEFAULT 0,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_tg_id   INTEGER NOT NULL,
                    service_id   INTEGER NOT NULL,
                    link         TEXT    NOT NULL,
                    quantity     INTEGER NOT NULL,
                    price        REAL    NOT NULL,
                    api_order_id TEXT,
                    status       TEXT    DEFAULT 'pending',
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS free_services (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id      INTEGER NOT NULL,
                    is_active       INTEGER DEFAULT 0,
                    mode            TEXT    DEFAULT 'all',
                    min_deposit     REAL    DEFAULT 0.0,
                    daily_limit     INTEGER DEFAULT 5,
                    custom_min      INTEGER DEFAULT 0,
                    custom_max      INTEGER DEFAULT 0,
                    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS free_service_users (
                    free_service_id INTEGER NOT NULL,
                    tg_id           INTEGER NOT NULL,
                    PRIMARY KEY (free_service_id, tg_id)
                );

                CREATE TABLE IF NOT EXISTS free_service_usage (
                    free_service_id INTEGER NOT NULL,
                    tg_id           INTEGER NOT NULL,
                    use_date        TEXT    NOT NULL,
                    count           INTEGER DEFAULT 0,
                    PRIMARY KEY (free_service_id, tg_id, use_date)
                );

                CREATE TABLE IF NOT EXISTS gift_codes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    code         TEXT    UNIQUE NOT NULL,
                    amount       REAL    NOT NULL,
                    max_uses     INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    is_active    INTEGER DEFAULT 1,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS gift_code_uses (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_id    INTEGER NOT NULL,
                    user_tg_id INTEGER NOT NULL,
                    used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code_id, user_tg_id),
                    FOREIGN KEY (code_id) REFERENCES gift_codes(id)
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS user_api_keys (
                    tg_id      INTEGER PRIMARY KEY,
                    api_key    TEXT    UNIQUE NOT NULL,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS forced_channels (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id    TEXT    NOT NULL UNIQUE,
                    channel_title TEXT    DEFAULT '',
                    max_members   INTEGER DEFAULT 0,
                    current_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS admins (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id      INTEGER NOT NULL UNIQUE,
                    username   TEXT    DEFAULT '',
                    note       TEXT    DEFAULT '',
                    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_tg_id    INTEGER NOT NULL,
                    txid          TEXT    UNIQUE NOT NULL,
                    network       TEXT    NOT NULL,
                    usdt_amount   REAL    NOT NULL,
                    credit_amount REAL    NOT NULL,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS game_apps (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT    NOT NULL,
                    emoji      TEXT    DEFAULT '🎮',
                    is_active  INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS game_packages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id     INTEGER NOT NULL,
                    name       TEXT    NOT NULL,
                    price      REAL    NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    FOREIGN KEY (app_id) REFERENCES game_apps(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_orders (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_tg_id   INTEGER NOT NULL,
                    app_id       INTEGER NOT NULL,
                    package_id   INTEGER NOT NULL,
                    game_id      TEXT    NOT NULL,
                    price        REAL    NOT NULL,
                    status       TEXT    DEFAULT 'pending',
                    admin_msg_id INTEGER,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS vodafone_charges (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_tg_id   INTEGER NOT NULL,
                    amount       REAL    NOT NULL,
                    screenshot   TEXT    DEFAULT '',
                    from_phone   TEXT    DEFAULT '',
                    status       TEXT    DEFAULT 'pending',
                    admin_msg_id INTEGER DEFAULT NULL,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS support_tickets (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_tg_id  INTEGER NOT NULL,
                    message     TEXT    NOT NULL,
                    status      TEXT    DEFAULT 'open',
                    admin_reply TEXT    DEFAULT '',
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_points (
                    tg_id       INTEGER PRIMARY KEY,
                    points      INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS user_vip (
                    tg_id        INTEGER PRIMARY KEY,
                    discount_pct REAL    DEFAULT 0.0,
                    set_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS blocked_services (
                    user_tg_id INTEGER NOT NULL,
                    service_id INTEGER NOT NULL,
                    PRIMARY KEY (user_tg_id, service_id)
                );

                CREATE TABLE IF NOT EXISTS low_balance_notified (
                    tg_id      INTEGER PRIMARY KEY,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Migration: إضافة api_base_price إن لم تكن موجودة
            try:
                conn.execute("ALTER TABLE services ADD COLUMN api_base_price REAL DEFAULT 0")
            except Exception:
                pass
            # Migration: referral fields
            for col, typ in [("referred_by", "INTEGER DEFAULT NULL"),
                             ("referral_earnings", "REAL DEFAULT 0.0")]:
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
                except Exception:
                    pass
        logger.info("[DB] قاعدة البيانات جاهزة ✅")

    # ════════════════════════════════════════════
    #  Users
    # ════════════════════════════════════════════

    def ensure_user(self, tg_id: int, username: str = None,
                    first_name: str = None) -> bool:
        """Returns True if user is NEW."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE tg_id=?", (tg_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE users SET username=?, first_name=? WHERE tg_id=?",
                    (username, first_name, tg_id)
                )
                return False
            conn.execute(
                "INSERT INTO users (tg_id, username, first_name) VALUES (?,?,?)",
                (tg_id, username, first_name)
            )
            return True

    def get_user(self, tg_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
            return dict(row) if row else None

    # ════════════════════════════════════════════
    #  API Keys (للموقع)
    # ════════════════════════════════════════════

    def get_or_create_api_key(self, tg_id: int) -> str:
        """يرجع الـ API key الخاص بالمستخدم، وينشئه لو مش موجود."""
        import secrets
        from datetime import datetime
        with self._conn() as conn:
            row = conn.execute(
                "SELECT api_key FROM user_api_keys WHERE tg_id=?", (tg_id,)
            ).fetchone()
            if row:
                return row["api_key"]
            key = "smm_" + secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO user_api_keys (tg_id, api_key, created_at) VALUES (?,?,?)",
                (tg_id, key, datetime.utcnow().isoformat())
            )
            return key

    def regenerate_api_key(self, tg_id: int) -> str:
        """ينشئ مفتاح API جديد للمستخدم."""
        import secrets
        from datetime import datetime
        key = "smm_" + secrets.token_urlsafe(32)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_api_keys (tg_id, api_key, created_at) VALUES (?,?,?)",
                (tg_id, key, datetime.utcnow().isoformat())
            )
        return key

    def get_user_by_api_key(self, api_key: str) -> Optional[dict]:
        """يرجع المستخدم بناءً على الـ API key."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT u.* FROM users u
                   JOIN user_api_keys k ON u.tg_id=k.tg_id
                   WHERE k.api_key=?""",
                (api_key,)
            ).fetchone()
            return dict(row) if row else None

    def get_balance(self, tg_id: int) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT balance FROM users WHERE tg_id=?", (tg_id,)
            ).fetchone()
            return round(float(row["balance"]), 4) if row else 0.0

    def add_balance(self, tg_id: int, amount: float):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET balance=balance+? WHERE tg_id=?", (amount, tg_id)
            )

    def deduct_balance(self, tg_id: int, amount: float) -> bool:
        """Atomic deduction; returns False if insufficient balance."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT balance FROM users WHERE tg_id=?", (tg_id,)
            ).fetchone()
            if not row or float(row["balance"]) < amount - 0.0001:
                return False
            conn.execute(
                "UPDATE users SET balance=balance-? WHERE tg_id=?", (amount, tg_id)
            )
            return True

    def set_balance(self, tg_id: int, amount: float):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET balance=? WHERE tg_id=?", (amount, tg_id)
            )

    def ban_user(self, tg_id: int, ban: bool):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET is_banned=? WHERE tg_id=?", (1 if ban else 0, tg_id)
            )

    def is_banned(self, tg_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT is_banned FROM users WHERE tg_id=?", (tg_id,)
            ).fetchone()
            return bool(row["is_banned"]) if row else False

    def get_users_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_all_user_ids(self) -> list:
        with self._conn() as conn:
            return [r[0] for r in conn.execute("SELECT tg_id FROM users WHERE is_banned=0").fetchall()]

    # ════════════════════════════════════════════
    #  Platforms
    # ════════════════════════════════════════════

    def get_platforms(self, active_only=True) -> list:
        with self._conn() as conn:
            q = "SELECT * FROM platforms"
            if active_only:
                q += " WHERE is_active=1"
            q += " ORDER BY sort_order, id"
            return [dict(r) for r in conn.execute(q).fetchall()]

    def get_platform(self, pid: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM platforms WHERE id=?", (pid,)).fetchone()
            return dict(r) if r else None

    def add_platform(self, name: str, emoji: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO platforms (name, emoji) VALUES (?,?)", (name, emoji)
            )
            return cur.lastrowid

    def toggle_platform(self, pid: int, active: bool):
        with self._conn() as conn:
            conn.execute(
                "UPDATE platforms SET is_active=? WHERE id=?", (1 if active else 0, pid)
            )

    def delete_platform(self, pid: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM platforms WHERE id=?", (pid,))

    # ════════════════════════════════════════════
    #  Categories
    # ════════════════════════════════════════════

    def get_categories(self, platform_id: int, active_only=True) -> list:
        with self._conn() as conn:
            q = "SELECT * FROM categories WHERE platform_id=?"
            params = [platform_id]
            if active_only:
                q += " AND is_active=1"
            q += " ORDER BY sort_order, id"
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def get_category(self, cid: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()
            return dict(r) if r else None

    def add_category(self, platform_id: int, name: str, emoji: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO categories (platform_id, name, emoji) VALUES (?,?,?)",
                (platform_id, name, emoji)
            )
            return cur.lastrowid

    def toggle_category(self, cid: int, active: bool):
        with self._conn() as conn:
            conn.execute(
                "UPDATE categories SET is_active=? WHERE id=?", (1 if active else 0, cid)
            )

    def delete_category(self, cid: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM categories WHERE id=?", (cid,))

    # ════════════════════════════════════════════
    #  Services
    # ════════════════════════════════════════════

    def get_services(self, category_id: int, active_only=True) -> list:
        with self._conn() as conn:
            q = "SELECT * FROM services WHERE category_id=?"
            params = [category_id]
            if active_only:
                q += " AND is_active=1"
            q += " ORDER BY sort_order, id"
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def get_service(self, sid: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()
            return dict(r) if r else None

    def add_service(self, category_id: int, api_service_id: int, name: str,
                    description: str, price_per_1000: float, min_qty: int,
                    max_qty: int, speed: str = '', quality: str = '',
                    warranty: str = '', api_base_price: float = 0) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO services
                   (category_id, api_service_id, name, description,
                    price_per_1000, api_base_price, min_qty, max_qty, speed, quality, warranty)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (category_id, api_service_id, name, description,
                 price_per_1000, api_base_price, min_qty, max_qty, speed, quality, warranty)
            )
            return cur.lastrowid

    def toggle_service(self, sid: int, active: bool):
        with self._conn() as conn:
            conn.execute(
                "UPDATE services SET is_active=? WHERE id=?", (1 if active else 0, sid)
            )

    def update_service_field(self, sid: int, field: str, value):
        allowed = {'name', 'description', 'price_per_1000', 'min_qty',
                   'max_qty', 'speed', 'quality', 'warranty'}
        if field not in allowed:
            return
        with self._conn() as conn:
            conn.execute(f"UPDATE services SET {field}=? WHERE id=?", (value, sid))

    def delete_service(self, sid: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM services WHERE id=?", (sid,))

    def get_all_services(self) -> list:
        """جلب كل الخدمات (لتغيير نسبة الربح الشاملة)."""
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM services ORDER BY id"
            ).fetchall()]

    def apply_global_margin(self, new_margin: float):
        """
        تطبيق نسبة ربح جديدة على كل الخدمات.
        يحسب السعر الأصلي من api_base_price ثم يضرب في (1 + margin/100).
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, api_base_price FROM services WHERE api_base_price IS NOT NULL AND api_base_price > 0"
            ).fetchall()
            for row in rows:
                sid, base = row[0], row[1]
                new_price = round(base * (1 + new_margin / 100), 4)
                conn.execute("UPDATE services SET price_per_1000=? WHERE id=?", (new_price, sid))

    def sync_service_price(self, sid: int, new_api_rate: float) -> dict:
        """
        يتحقق من سعر الخدمة في API ويحدّثه إن تغيّر،
        محافظاً على نسبة الربح المحفوظة.

        Returns dict:
          changed   bool  — هل تغيّر السعر؟
          old_price float — السعر القديم /1000
          new_price float — السعر الجديد /1000
          margin    float — نسبة الربح المحسوبة
        """
        svc = self.get_service(sid)
        if not svc:
            return {"changed": False}

        old_base  = float(svc.get("api_base_price") or 0)
        old_price = float(svc["price_per_1000"])

        # إذا لم يكن هناك سعر أصلي مسجّل → لا نغيّر
        if old_base <= 0:
            return {"changed": False}

        # نسبة الربح الحالية محسوبة من القيم المخزنة
        margin = round((old_price / old_base - 1) * 100, 4)

        # تجاهل فروق أقل من 0.0001 (noise)
        if abs(new_api_rate - old_base) < 0.0001:
            return {"changed": False}

        # السعر الجديد مع نفس نسبة الربح
        new_price = round(new_api_rate * (1 + margin / 100), 4)

        with self._conn() as conn:
            conn.execute(
                "UPDATE services SET price_per_1000=?, api_base_price=? WHERE id=?",
                (new_price, new_api_rate, sid),
            )

        return {
            "changed":   True,
            "old_price": old_price,
            "new_price": new_price,
            "old_api":   old_base,
            "new_api":   new_api_rate,
            "margin":    margin,
        }

    def get_service_by_api_id(self, api_service_id: int):
        """جلب خدمة بواسطة api_service_id."""
        with self._conn() as conn:
            r = conn.execute(
                "SELECT * FROM services WHERE api_service_id=?", (api_service_id,)
            ).fetchone()
            return dict(r) if r else None

    def get_services_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]

    # ════════════════════════════════════════════
    #  Orders
    # ════════════════════════════════════════════

    def create_order(self, user_tg_id: int, service_id: int, link: str,
                     quantity: int, price: float, api_order_id: str = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO orders (user_tg_id, service_id, link, quantity,
                   price, api_order_id) VALUES (?,?,?,?,?,?)""",
                (user_tg_id, service_id, link, quantity, price, api_order_id)
            )
            return cur.lastrowid

    def get_user_orders(self, user_tg_id: int, limit: int = 10) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT o.*, s.name as service_name
                   FROM orders o LEFT JOIN services s ON o.service_id=s.id
                   WHERE o.user_tg_id=? ORDER BY o.id DESC LIMIT ?""",
                (user_tg_id, limit)
            ).fetchall()]

    def get_orders_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    def get_order(self, order_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute(
                """SELECT o.*, s.name as service_name
                   FROM orders o LEFT JOIN services s ON o.service_id=s.id
                   WHERE o.id=?""",
                (order_id,)
            ).fetchone()
            return dict(r) if r else None

    # ════════════════════════════════════════════
    #  Gift Codes
    # ════════════════════════════════════════════

    def create_gift_code(self, code: str, amount: float, max_uses: int) -> bool:
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO gift_codes (code, amount, max_uses) VALUES (?,?,?)",
                    (code.upper(), amount, max_uses)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def redeem_gift_code(self, user_tg_id: int, code: str) -> dict:
        with self._conn() as conn:
            gc = conn.execute(
                "SELECT * FROM gift_codes WHERE code=? AND is_active=1",
                (code.upper().strip(),)
            ).fetchone()
            if not gc:
                return {"success": False, "error": "❌ الكود غير موجود أو منتهي الصلاحية"}
            gc = dict(gc)
            if gc["current_uses"] >= gc["max_uses"]:
                return {"success": False, "error": "❌ وصل الكود لحد الاستخدامات القصوى"}
            used = conn.execute(
                "SELECT id FROM gift_code_uses WHERE code_id=? AND user_tg_id=?",
                (gc["id"], user_tg_id)
            ).fetchone()
            if used:
                return {"success": False, "error": "❌ لقد استخدمت هذا الكود مسبقاً"}
            conn.execute(
                "INSERT INTO gift_code_uses (code_id, user_tg_id) VALUES (?,?)",
                (gc["id"], user_tg_id)
            )
            conn.execute(
                "UPDATE gift_codes SET current_uses=current_uses+1 WHERE id=?",
                (gc["id"],)
            )
            conn.execute(
                "UPDATE users SET balance=balance+? WHERE tg_id=?",
                (gc["amount"], user_tg_id)
            )
            return {"success": True, "amount": gc["amount"]}

    def get_active_gift_codes(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM gift_codes WHERE is_active=1 ORDER BY id DESC"
            ).fetchall()]

    def deactivate_gift_code(self, code: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE gift_codes SET is_active=0 WHERE code=? AND is_active=1",
                (code.upper(),)
            )
            return cur.rowcount > 0

    # ════════════════════════════════════════════
    #  Settings
    # ════════════════════════════════════════════

    # ════════════════════════════════════════════
    #  Free Services
    # ════════════════════════════════════════════

    def get_free_services(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT fs.*, s.name as service_name, s.min_qty, s.max_qty
                   FROM free_services fs JOIN services s ON fs.service_id=s.id
                   ORDER BY fs.id"""
            ).fetchall()]

    def get_free_service(self, fs_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute(
                """SELECT fs.*, s.name as service_name, s.min_qty, s.max_qty
                   FROM free_services fs JOIN services s ON fs.service_id=s.id
                   WHERE fs.id=?""", (fs_id,)
            ).fetchone()
            return dict(r) if r else None

    def add_free_service(self, service_id: int) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO free_services (service_id) VALUES (?)", (service_id,)
            )
            return cur.lastrowid

    def update_free_service(self, fs_id: int, **kwargs):
        allowed = {"is_active", "mode", "min_deposit", "daily_limit", "custom_min", "custom_max"}
        fields  = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE free_services SET {sets} WHERE id=?",
                (*fields.values(), fs_id)
            )

    def delete_free_service(self, fs_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM free_services WHERE id=?", (fs_id,))

    def get_free_service_allowed_users(self, fs_id: int) -> list:
        with self._conn() as conn:
            return [r[0] for r in conn.execute(
                "SELECT tg_id FROM free_service_users WHERE free_service_id=?", (fs_id,)
            ).fetchall()]

    def add_free_service_user(self, fs_id: int, tg_id: int):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO free_service_users VALUES (?,?)", (fs_id, tg_id)
            )

    def remove_free_service_user(self, fs_id: int, tg_id: int):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM free_service_users WHERE free_service_id=? AND tg_id=?",
                (fs_id, tg_id)
            )

    def can_use_free_service(self, fs_id: int, tg_id: int) -> tuple[bool, int, str]:
        """يرجع (allowed, remaining_today, reason)
        reason: 'ok' | 'inactive' | 'not_selected' | 'need_deposit' | 'limit_reached'
        """
        from datetime import date
        today = date.today().isoformat()
        with self._conn() as conn:
            fs = conn.execute(
                "SELECT * FROM free_services WHERE id=?", (fs_id,)
            ).fetchone()
            if not fs or not fs["is_active"]:
                return False, 0, "inactive"

            # فحص وضع الوصول
            if fs["mode"] == "selected":
                allowed_user = conn.execute(
                    "SELECT 1 FROM free_service_users WHERE free_service_id=? AND tg_id=?",
                    (fs_id, tg_id)
                ).fetchone()
                if not allowed_user:
                    return False, 0, "not_selected"
            elif fs["mode"] == "min_deposit":
                from_db = conn.execute(
                    "SELECT COALESCE(SUM(credit_amount),0) as total FROM transactions "
                    "WHERE user_tg_id=?",
                    (tg_id,)
                ).fetchone()
                total_dep = float(from_db["total"] if from_db else 0)
                if total_dep < float(fs["min_deposit"]):
                    return False, 0, f"need_deposit:{fs['min_deposit']}:{total_dep:.4f}"

            # فحص الاستخدام اليومي
            row = conn.execute(
                "SELECT count FROM free_service_usage WHERE free_service_id=? AND tg_id=? AND use_date=?",
                (fs_id, tg_id, today)
            ).fetchone()
            used      = int(row["count"]) if row else 0
            limit     = int(fs["daily_limit"])
            remaining = limit - used
            if remaining <= 0:
                return False, 0, "limit_reached"
            return True, remaining, "ok"

    def record_free_service_use(self, fs_id: int, tg_id: int):
        from datetime import date
        today = date.today().isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO free_service_usage (free_service_id, tg_id, use_date, count)
                   VALUES (?,?,?,1)
                   ON CONFLICT(free_service_id,tg_id,use_date)
                   DO UPDATE SET count=count+1""",
                (fs_id, tg_id, today)
            )

    def get_free_services_for_user(self, tg_id: int) -> list:
        """يرجع كل الخدمات المجانية المفعّلة مع حالة المستخدم (مؤهل أم لا وسبب المنع)."""
        from datetime import date
        today = date.today().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT fs.*, s.name as service_name, s.min_qty, s.max_qty, s.description,
                          COALESCE(u.count, 0) as used_today
                   FROM free_services fs
                   JOIN services s ON fs.service_id=s.id
                   LEFT JOIN free_service_usage u
                          ON u.free_service_id=fs.id AND u.tg_id=? AND u.use_date=?
                   WHERE fs.is_active=1""",
                (tg_id, today)
            ).fetchall()
            result = []
            for r in rows:
                rd = dict(r)
                rd["remaining_today"] = max(0, int(rd["daily_limit"]) - int(rd["used_today"]))
                rd["locked"]  = False
                rd["lock_reason"] = "ok"

                if rd["mode"] == "selected":
                    allowed = conn.execute(
                        "SELECT 1 FROM free_service_users WHERE free_service_id=? AND tg_id=?",
                        (rd["id"], tg_id)
                    ).fetchone()
                    if not allowed:
                        rd["locked"] = True
                        rd["lock_reason"] = "not_selected"

                elif rd["mode"] == "min_deposit":
                    row_dep = conn.execute(
                        "SELECT COALESCE(SUM(credit_amount),0) as total FROM transactions WHERE user_tg_id=?",
                        (tg_id,)
                    ).fetchone()
                    total_dep = float(row_dep["total"] if row_dep else 0)
                    if total_dep < float(rd["min_deposit"]):
                        rd["locked"] = True
                        rd["lock_reason"] = f"need_deposit:{rd['min_deposit']}:{total_dep:.4f}"

                if rd["remaining_today"] <= 0 and not rd["locked"]:
                    rd["locked"] = True
                    rd["lock_reason"] = "limit_reached"

                result.append(rd)
            return result

    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                (key, value)
            )

    # ════════════════════════════════════════════
    #  Forced Channels
    # ════════════════════════════════════════════

    def get_forced_channels(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in
                    conn.execute("SELECT * FROM forced_channels ORDER BY id").fetchall()]

    def add_forced_channel(self, channel_id: str, title: str = "",
                           max_members: int = 0) -> bool:
        """
        max_members=0  → لا حد (دائمة)
        max_members>0  → تُحذف تلقائياً بعد هذا العدد من الانضمامات
        """
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO forced_channels
                       (channel_id, channel_title, max_members, current_count)
                       VALUES (?,?,?,0)""",
                    (channel_id, title, max_members)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_forced_channel(self, channel_id: str):
        """حذف بالـ channel_id (يقبل @ أو الـ numeric ID)."""
        with self._conn() as conn:
            # حذف بالنص المباشر أولاً
            rows = conn.execute(
                "DELETE FROM forced_channels WHERE channel_id=?", (channel_id,)
            ).rowcount
            # لو مفيش نتيجة جرب بدون @
            if rows == 0 and channel_id.startswith("@"):
                conn.execute(
                    "DELETE FROM forced_channels WHERE channel_id=?",
                    (channel_id.lstrip("@"),)
                )
            # لو كان رقماً جرب بـ @
            elif rows == 0 and not channel_id.startswith("@"):
                conn.execute(
                    "DELETE FROM forced_channels WHERE channel_id=?",
                    (f"@{channel_id}",)
                )

    def remove_forced_channel_by_id(self, row_id: int):
        """حذف بالـ ID الرقمي في جدول forced_channels."""
        with self._conn() as conn:
            conn.execute("DELETE FROM forced_channels WHERE id=?", (row_id,))

    def increment_forced_channel_count(self, channel_id: str) -> bool:
        """
        يزيد العداد بـ 1.
        يُعيد True لو وصل للحد الأقصى ويجب حذف القناة.
        """
        with self._conn() as conn:
            conn.execute(
                """UPDATE forced_channels
                   SET current_count = current_count + 1
                   WHERE channel_id=?""",
                (channel_id,)
            )
            row = conn.execute(
                "SELECT max_members, current_count FROM forced_channels WHERE channel_id=?",
                (channel_id,)
            ).fetchone()
            if row and row["max_members"] > 0:
                return row["current_count"] >= row["max_members"]
        return False

    def migrate_forced_channels(self):
        """ترقية الجدول القديم لإضافة الأعمدة الجديدة."""
        for col, default in [("max_members", "0"), ("current_count", "0")]:
            try:
                with self._conn() as conn:
                    conn.execute(
                        f"ALTER TABLE forced_channels ADD COLUMN {col} INTEGER DEFAULT {default}"
                    )
            except Exception:
                pass

    # ════════════════════════════════════════════
    #  إدارة الأدمنز المتعددين
    # ════════════════════════════════════════════

    def get_all_admins(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM admins ORDER BY added_at"
            ).fetchall()]

    def add_admin(self, tg_id: int, username: str = "", note: str = "") -> bool:
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO admins (tg_id, username, note) VALUES (?,?,?)",
                    (tg_id, username.lstrip("@"), note)
                )
            return True
        except Exception:
            return False   # موجود بالفعل

    def remove_admin(self, tg_id: int) -> bool:
        with self._conn() as conn:
            rows = conn.execute(
                "DELETE FROM admins WHERE tg_id=?", (tg_id,)
            ).rowcount
            return rows > 0

    def is_sub_admin(self, tg_id: int) -> bool:
        with self._conn() as conn:
            r = conn.execute(
                "SELECT id FROM admins WHERE tg_id=?", (tg_id,)
            ).fetchone()
            return r is not None

    def migrate_admins(self):
        """ترقية — إضافة جدول الأدمنز لو مش موجود."""
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS admins (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        tg_id      INTEGER NOT NULL UNIQUE,
                        username   TEXT    DEFAULT '',
                        note       TEXT    DEFAULT '',
                        added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
        except Exception:
            pass

    # ════════════════════════════════════════════
    #  Crypto Transactions (atomic deposit)
    # ════════════════════════════════════════════

    def process_crypto_deposit(self, user_tg_id: int, txid: str, network: str,
                                usdt_amount: float, credit_amount: float) -> bool:
        """Atomic: record tx + add balance. Returns False if TXID already used."""
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO transactions
                       (user_tg_id, txid, network, usdt_amount, credit_amount)
                       VALUES (?,?,?,?,?)""",
                    (user_tg_id, txid, network, usdt_amount, credit_amount)
                )
                conn.execute(
                    "UPDATE users SET balance=balance+? WHERE tg_id=?",
                    (credit_amount, user_tg_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    # ════════════════════════════════════════════
    #  Game Apps & Packages
    # ════════════════════════════════════════════

    def get_game_apps(self, active_only=True) -> list:
        with self._conn() as conn:
            q = "SELECT * FROM game_apps"
            if active_only:
                q += " WHERE is_active=1"
            q += " ORDER BY sort_order, id"
            return [dict(r) for r in conn.execute(q).fetchall()]

    def get_game_app(self, app_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM game_apps WHERE id=?", (app_id,)).fetchone()
            return dict(r) if r else None

    def add_game_app(self, name: str, emoji: str = "🎮") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO game_apps (name, emoji) VALUES (?,?)", (name, emoji)
            )
            return cur.lastrowid

    def toggle_game_app(self, app_id: int, active: bool):
        with self._conn() as conn:
            conn.execute(
                "UPDATE game_apps SET is_active=? WHERE id=?", (1 if active else 0, app_id)
            )

    def delete_game_app(self, app_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM game_apps WHERE id=?", (app_id,))

    def get_game_packages(self, app_id: int) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM game_packages WHERE app_id=? ORDER BY sort_order, id",
                (app_id,)
            ).fetchall()]

    def get_game_package(self, pkg_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM game_packages WHERE id=?", (pkg_id,)).fetchone()
            return dict(r) if r else None

    def add_game_package(self, app_id: int, name: str, price: float) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO game_packages (app_id, name, price) VALUES (?,?,?)",
                (app_id, name, price)
            )
            return cur.lastrowid

    def delete_game_package(self, pkg_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM game_packages WHERE id=?", (pkg_id,))

    def create_game_order(self, user_tg_id: int, app_id: int, package_id: int,
                          game_id: str, price: float) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO game_orders (user_tg_id, app_id, package_id, game_id, price)
                   VALUES (?,?,?,?,?)""",
                (user_tg_id, app_id, package_id, game_id, price)
            )
            return cur.lastrowid

    def get_game_order(self, order_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute(
                """SELECT go.*, ga.name as app_name, ga.emoji as app_emoji,
                          gp.name as pkg_name
                   FROM game_orders go
                   LEFT JOIN game_apps ga ON go.app_id=ga.id
                   LEFT JOIN game_packages gp ON go.package_id=gp.id
                   WHERE go.id=?""",
                (order_id,)
            ).fetchone()
            return dict(r) if r else None

    def update_game_order_status(self, order_id: int, status: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE game_orders SET status=? WHERE id=?", (status, order_id)
            )

    def set_game_order_admin_msg(self, order_id: int, msg_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE game_orders SET admin_msg_id=? WHERE id=?", (msg_id, order_id)
            )

    # ════════════════════════════════════════════
    #  Referral
    # ════════════════════════════════════════════

    def set_referral(self, user_tg_id: int, referrer_tg_id: int):
        """ربط مستخدم بمن أحاله — مرة واحدة فقط."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT referred_by FROM users WHERE tg_id=?", (user_tg_id,)
            ).fetchone()
            if row and row["referred_by"] is None:
                conn.execute(
                    "UPDATE users SET referred_by=? WHERE tg_id=?",
                    (referrer_tg_id, user_tg_id)
                )

    def get_referrer(self, user_tg_id: int) -> Optional[int]:
        with self._conn() as conn:
            r = conn.execute(
                "SELECT referred_by FROM users WHERE tg_id=?", (user_tg_id,)
            ).fetchone()
            return r["referred_by"] if r else None

    def add_referral_earning(self, referrer_tg_id: int, amount: float):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET balance=balance+?, referral_earnings=referral_earnings+? WHERE tg_id=?",
                (amount, amount, referrer_tg_id)
            )

    def get_referral_count(self, tg_id: int) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM users WHERE referred_by=?", (tg_id,)
            ).fetchone()[0]

    # ════════════════════════════════════════════
    #  Vodafone Charges
    # ════════════════════════════════════════════

    def create_vodafone_charge(self, user_tg_id: int, amount: float,
                               screenshot: str, from_phone: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO vodafone_charges (user_tg_id, amount, screenshot, from_phone)
                   VALUES (?,?,?,?)""",
                (user_tg_id, amount, screenshot, from_phone)
            )
            return cur.lastrowid

    def get_vodafone_charge(self, charge_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute(
                "SELECT * FROM vodafone_charges WHERE id=?", (charge_id,)
            ).fetchone()
            return dict(r) if r else None

    def update_vodafone_status(self, charge_id: int, status: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE vodafone_charges SET status=? WHERE id=?", (status, charge_id)
            )

    def set_vodafone_admin_msg(self, charge_id: int, msg_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE vodafone_charges SET admin_msg_id=? WHERE id=?", (msg_id, charge_id)
            )

    def get_pending_vodafone_charges(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM vodafone_charges WHERE status='pending' ORDER BY created_at DESC"
            ).fetchall()]

    def get_pending_game_orders(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT go.*, ga.name as app_name, ga.emoji as app_emoji, gp.name as pkg_name
                   FROM game_orders go
                   LEFT JOIN game_apps ga ON go.app_id=ga.id
                   LEFT JOIN game_packages gp ON go.package_id=gp.id
                   WHERE go.status='pending' ORDER BY go.created_at DESC"""
            ).fetchall()]

    def get_user_total_spent(self, tg_id: int) -> float:
        with self._conn() as conn:
            r1 = conn.execute(
                "SELECT COALESCE(SUM(price),0) FROM orders WHERE user_tg_id=?", (tg_id,)
            ).fetchone()[0]
            r2 = conn.execute(
                "SELECT COALESCE(SUM(price),0) FROM game_orders WHERE user_tg_id=? AND status='completed'",
                (tg_id,)
            ).fetchone()[0]
            return round(float(r1) + float(r2), 2)

    # ════════════════════════════════════════════
    #  Support Tickets
    # ════════════════════════════════════════════

    def create_ticket(self, user_tg_id: int, message: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO support_tickets (user_tg_id, message) VALUES (?,?)",
                (user_tg_id, message)
            )
            return cur.lastrowid

    def get_ticket(self, ticket_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
            return dict(r) if r else None

    def get_open_tickets(self) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM support_tickets WHERE status='open' ORDER BY id DESC LIMIT 50"
            ).fetchall()]

    def reply_ticket(self, ticket_id: int, reply: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE support_tickets SET admin_reply=?, status='closed', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (reply, ticket_id)
            )

    def close_ticket(self, ticket_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE support_tickets SET status='closed', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (ticket_id,)
            )

    def get_user_tickets(self, tg_id: int, limit: int = 5) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM support_tickets WHERE user_tg_id=? ORDER BY id DESC LIMIT ?",
                (tg_id, limit)
            ).fetchall()]

    # ════════════════════════════════════════════
    #  Points
    # ════════════════════════════════════════════

    def get_points(self, tg_id: int) -> int:
        with self._conn() as conn:
            r = conn.execute("SELECT points FROM user_points WHERE tg_id=?", (tg_id,)).fetchone()
            return int(r["points"]) if r else 0

    def add_points(self, tg_id: int, points: int):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO user_points (tg_id, points, total_earned) VALUES (?,?,?)
                   ON CONFLICT(tg_id) DO UPDATE SET points=points+?, total_earned=total_earned+?""",
                (tg_id, points, points, points, points)
            )

    def redeem_points(self, tg_id: int, points: int) -> bool:
        """يستبدل النقاط برصيد. يرجع True لو نجح."""
        with self._conn() as conn:
            r = conn.execute("SELECT points FROM user_points WHERE tg_id=?", (tg_id,)).fetchone()
            current = int(r["points"]) if r else 0
            if current < points:
                return False
            conn.execute("UPDATE user_points SET points=points-? WHERE tg_id=?", (points, tg_id))
            return True

    def get_points_info(self, tg_id: int) -> dict:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM user_points WHERE tg_id=?", (tg_id,)).fetchone()
            return dict(r) if r else {"tg_id": tg_id, "points": 0, "total_earned": 0}

    # ════════════════════════════════════════════
    #  VIP
    # ════════════════════════════════════════════

    def set_vip(self, tg_id: int, discount_pct: float):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO user_vip (tg_id, discount_pct) VALUES (?,?)
                   ON CONFLICT(tg_id) DO UPDATE SET discount_pct=?, set_at=CURRENT_TIMESTAMP""",
                (tg_id, discount_pct, discount_pct)
            )

    def remove_vip(self, tg_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM user_vip WHERE tg_id=?", (tg_id,))

    def get_vip(self, tg_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM user_vip WHERE tg_id=?", (tg_id,)).fetchone()
            return dict(r) if r else None

    def get_vip_discount(self, tg_id: int) -> float:
        """يرجع نسبة الخصم (0.0 لو مش VIP)."""
        vip = self.get_vip(tg_id)
        return float(vip["discount_pct"]) if vip else 0.0

    # ════════════════════════════════════════════
    #  Blocked Services
    # ════════════════════════════════════════════

    def block_service(self, tg_id: int, service_id: int):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blocked_services (user_tg_id, service_id) VALUES (?,?)",
                (tg_id, service_id)
            )

    def unblock_service(self, tg_id: int, service_id: int):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM blocked_services WHERE user_tg_id=? AND service_id=?",
                (tg_id, service_id)
            )

    def is_service_blocked(self, tg_id: int, service_id: int) -> bool:
        with self._conn() as conn:
            r = conn.execute(
                "SELECT 1 FROM blocked_services WHERE user_tg_id=? AND service_id=?",
                (tg_id, service_id)
            ).fetchone()
            return bool(r)

    def get_blocked_services(self, tg_id: int) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT bs.service_id, s.name as service_name
                   FROM blocked_services bs LEFT JOIN services s ON bs.service_id=s.id
                   WHERE bs.user_tg_id=?""",
                (tg_id,)
            ).fetchall()]

    # ════════════════════════════════════════════
    #  Low Balance Notification
    # ════════════════════════════════════════════

    def should_notify_low_balance(self, tg_id: int) -> bool:
        """يرجع True لو المستخدم مش اتبعتله إشعار في آخر 24 ساعة."""
        with self._conn() as conn:
            r = conn.execute(
                """SELECT 1 FROM low_balance_notified
                   WHERE tg_id=? AND notified_at > datetime('now','-24 hours')""",
                (tg_id,)
            ).fetchone()
            return not bool(r)

    def mark_low_balance_notified(self, tg_id: int):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO low_balance_notified (tg_id) VALUES (?)
                   ON CONFLICT(tg_id) DO UPDATE SET notified_at=CURRENT_TIMESTAMP""",
                (tg_id,)
            )

    def get_users_below_balance(self, threshold: float) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT tg_id FROM users
                   WHERE balance > 0 AND balance < ? AND is_banned=0""",
                (threshold,)
            ).fetchall()]

    # ════════════════════════════════════════════
    #  Daily Stats
    # ════════════════════════════════════════════

    def get_daily_stats(self) -> dict:
        with self._conn() as conn:
            today = "date('now')"
            orders_today = conn.execute(
                f"SELECT COUNT(*) FROM orders WHERE date(created_at)={today}"
            ).fetchone()[0]
            revenue_today = conn.execute(
                f"SELECT COALESCE(SUM(price),0) FROM orders WHERE date(created_at)={today}"
            ).fetchone()[0]
            new_users = conn.execute(
                f"SELECT COUNT(*) FROM users WHERE date(joined_at)={today}"
            ).fetchone()[0]
            refunds_today = conn.execute(
                f"SELECT COALESCE(SUM(refunded_amount),0) FROM orders WHERE date(created_at)={today}"
            ).fetchone()[0]
            return {
                "orders":   orders_today,
                "revenue":  round(float(revenue_today), 4),
                "new_users": new_users,
                "refunds":  round(float(refunds_today or 0), 4),
            }

    # ════════════════════════════════════════════
    #  Pending Orders
    # ════════════════════════════════════════════

    def get_pending_orders_over(self, hours: int = 24) -> list:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT o.*, s.name as service_name, u.username
                   FROM orders o
                   LEFT JOIN services s ON o.service_id=s.id
                   LEFT JOIN users u    ON o.user_tg_id=u.tg_id
                   WHERE o.status IN ('pending','in progress','processing')
                     AND o.created_at < datetime('now', ?)
                   ORDER BY o.created_at ASC LIMIT 50""",
                (f"-{hours} hours",)
            ).fetchall()]

    # ════════════════════════════════════════════
    #  User Detailed Stats
    # ════════════════════════════════════════════

    def get_user_detailed_stats(self, tg_id: int) -> dict:
        with self._conn() as conn:
            total  = conn.execute("SELECT COUNT(*) FROM orders WHERE user_tg_id=?", (tg_id,)).fetchone()[0]
            done   = conn.execute("SELECT COUNT(*) FROM orders WHERE user_tg_id=? AND status='completed'", (tg_id,)).fetchone()[0]
            cancel = conn.execute("SELECT COUNT(*) FROM orders WHERE user_tg_id=? AND status IN ('canceled','cancelled')", (tg_id,)).fetchone()[0]
            partial= conn.execute("SELECT COUNT(*) FROM orders WHERE user_tg_id=? AND status='partial'", (tg_id,)).fetchone()[0]
            spent  = conn.execute("SELECT COALESCE(SUM(price),0) FROM orders WHERE user_tg_id=?", (tg_id,)).fetchone()[0]
            top_svc= conn.execute(
                """SELECT s.name, COUNT(*) as cnt FROM orders o
                   LEFT JOIN services s ON o.service_id=s.id
                   WHERE o.user_tg_id=? GROUP BY o.service_id ORDER BY cnt DESC LIMIT 1""",
                (tg_id,)
            ).fetchone()
            user   = conn.execute("SELECT joined_at FROM users WHERE tg_id=?", (tg_id,)).fetchone()
            return {
                "total":    total,
                "done":     done,
                "cancel":   cancel,
                "partial":  partial,
                "spent":    round(float(spent), 4),
                "top_svc":  top_svc["name"] if top_svc else "—",
                "top_cnt":  top_svc["cnt"]  if top_svc else 0,
                "joined":   user["joined_at"][:10] if user else "—",
            }

        # ════════════════════════════════════════════
    #  Stats
    # ════════════════════════════════════════════

    # ════════════════════════════════════════════
    #  Second Currency + Features Settings
    # ════════════════════════════════════════════

    def get_second_currency(self) -> tuple[str, float]:
        """يرجع (name, rate) للعملة الثانية."""
        name = self.get_setting("second_currency_name", "EGP")
        rate = float(self.get_setting("second_currency_rate", "0") or 0)
        return name, rate

    def second_currency_enabled(self) -> bool:
        return self.get_setting("second_currency_enabled", "0") == "1"

    def points_enabled(self) -> bool:
        return self.get_setting("points_enabled", "0") == "1"

    def low_balance_alert_enabled(self) -> bool:
        return self.get_setting("low_balance_alert", "0") == "1"

    def get_low_balance_threshold(self) -> float:
        return float(self.get_setting("low_balance_threshold", "1.0") or 1.0)

    def get_points_rate(self) -> int:
        """نقاط لكل $1 ينفقه المستخدم."""
        return int(self.get_setting("points_per_dollar", "10") or 10)

    def get_points_redeem_min(self) -> int:
        """الحد الأدنى للاسترداد."""
        return int(self.get_setting("points_redeem_min", "100") or 100)

    def get_points_redeem_value(self) -> float:
        """قيمة النقاط عند الاسترداد ($ لكل points_redeem_min نقطة)."""
        return float(self.get_setting("points_redeem_value", "0.5") or 0.5)

    def daily_report_enabled(self) -> bool:
        return self.get_setting("daily_report_enabled", "0") == "1"

    def get_daily_report_hour(self) -> int:
        return int(self.get_setting("daily_report_hour", "0") or 0)

    # ════════════════════════════════════════════
    #  Low Balance Alert Reset
    # ════════════════════════════════════════════

    def reset_low_balance_notification(self, tg_id: int):
        """إعادة تفعيل الإشعار بعد الشحن."""
        with self._conn() as conn:
            conn.execute("DELETE FROM low_balance_notified WHERE tg_id=?", (tg_id,))

    # ════════════════════════════════════════════
    #  Reorder helper
    # ════════════════════════════════════════════

    def get_order_for_reorder(self, order_id: int, user_tg_id: int) -> Optional[dict]:
        with self._conn() as conn:
            r = conn.execute(
                """SELECT o.*, s.name as service_name, s.min_qty, s.max_qty,
                          s.price_per_1000, s.api_service_id
                   FROM orders o
                   JOIN services s ON o.service_id=s.id
                   WHERE o.id=? AND o.user_tg_id=?""",
                (order_id, user_tg_id)
            ).fetchone()
            return dict(r) if r else None

    def get_stats(self) -> dict:
        with self._conn() as conn:
            users      = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            orders     = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            revenue    = conn.execute("SELECT COALESCE(SUM(price),0) FROM orders").fetchone()[0]
            services   = conn.execute("SELECT COUNT(*) FROM services WHERE is_active=1").fetchone()[0]
            platforms  = conn.execute("SELECT COUNT(*) FROM platforms WHERE is_active=1").fetchone()[0]
            total_bal  = conn.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
            return {
                "users":         users,
                "orders":        orders,
                "revenue":       round(float(revenue), 2),
                "services":      services,
                "platforms":     platforms,
                "total_balance": round(float(total_bal), 4),
            }
