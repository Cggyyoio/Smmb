#!/bin/bash
# ════════════════════════════════════════
#  deploy.sh — نشر البوت على VPS
# ════════════════════════════════════════
set -e

BOT_DIR="/opt/smm_bot"
SERVICE="smm_bot"

echo "🚀 بدء النشر..."

# إنشاء المجلد إن لم يكن موجوداً
mkdir -p "$BOT_DIR/data"

# نسخ الملفات
cp -r . "$BOT_DIR/"

# تثبيت المتطلبات
pip3 install -r "$BOT_DIR/requirements.txt" --break-system-packages -q

# نسخ ملف الخدمة
cp "$BOT_DIR/smm_bot.service" /etc/systemd/system/

# إعادة تحميل systemd وتشغيل الخدمة
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"

echo "✅ تم النشر بنجاح!"
echo "📋 حالة الخدمة:"
systemctl status "$SERVICE" --no-pager -l
