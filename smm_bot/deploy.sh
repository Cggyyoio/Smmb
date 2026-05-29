#!/bin/bash
# ════════════════════════════════════════
#  deploy.sh — نشر البوت والموقع على VPS
# ════════════════════════════════════════
set -e

BOT_DIR="/root/smmbot-main"
BOT_SERVICE="smm_bot"
WEB_SERVICE="smm_invoice"

echo "🚀 بدء النشر..."

# إنشاء المجلد إن لم يكن موجوداً
mkdir -p "$BOT_DIR/data"

# نسخ الملفات
rsync -av --exclude='data/bot.db' --exclude='__pycache__' \
      --exclude='*.pyc' . "$BOT_DIR/"

# تثبيت المتطلبات (أضاف flask وgunicorn)
pip3 install -r "$BOT_DIR/requirements.txt" --break-system-packages -q
pip3 install flask --break-system-packages -q

# ── نشر خدمة البوت ──
cp "$BOT_DIR/smm_bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$BOT_SERVICE"
systemctl restart "$BOT_SERVICE"

# ── نشر خدمة الموقع ──
cp "$BOT_DIR/smm_invoice.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$WEB_SERVICE"
systemctl restart "$WEB_SERVICE"

# ── إعداد Nginx (إن لم يكن مضبوطاً) ──
NGINX_CONF="/etc/nginx/sites-available/a1smm.store"
if [ ! -f "$NGINX_CONF" ]; then
    cp "$BOT_DIR/a1smm.store.nginx.conf" "$NGINX_CONF"
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
    echo "⚠️  تم نسخ إعداد Nginx — شغّل certbot للحصول على SSL:"
    echo "    certbot --nginx -d a1smm.store -d www.a1smm.store"
    nginx -t && nginx -s reload || true
fi

echo ""
echo "✅ تم النشر بنجاح!"
echo ""
echo "📋 حالة البوت:"
systemctl status "$BOT_SERVICE"  --no-pager -l
echo ""
echo "🌐 حالة الموقع:"
systemctl status "$WEB_SERVICE" --no-pager -l
