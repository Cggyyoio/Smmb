#!/bin/bash
# ═══════════════════════════════════════════════════════
#  setup.sh — تثبيت كامل لبوت SMM + موقع الفواتير
#  الاستخدام: bash setup.sh
#  المتطلبات: Ubuntu 20+ / Debian 11+ — root
# ═══════════════════════════════════════════════════════
set -e

# ─── الألوان ───────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ─── المسار الثابت ────────────────────────────────────
BOT_DIR="/root/smmbot-main"
BOT_SERVICE="smm_bot"
WEB_SERVICE="smm_invoice"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════╗"
echo "║     SMM Bot — التثبيت الكامل        ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# ─── 1. تحديث النظام + Python ─────────────────────────
info "تحديث النظام وتثبيت Python..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip git curl wget unzip nginx 2>/dev/null || true
success "Python $(python3 --version) جاهز"

# ─── 2. إنشاء مجلد البوت ──────────────────────────────
info "إنشاء مجلد البوت في $BOT_DIR ..."
mkdir -p "$BOT_DIR/data"

# ─── 3. نسخ ملفات البوت ───────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "نسخ الملفات من $SCRIPT_DIR ..."

rsync -a --exclude='data/bot.db' --exclude='__pycache__' \
         --exclude='*.pyc' --exclude='.git' \
         "$SCRIPT_DIR/" "$BOT_DIR/"

success "تم نسخ الملفات"

# ─── 4. تثبيت المكتبات ────────────────────────────────
info "تثبيت المكتبات Python..."
pip3 install -r "$BOT_DIR/requirements.txt" \
     --break-system-packages -q 2>/dev/null || \
pip3 install -r "$BOT_DIR/requirements.txt" -q

success "المكتبات جاهزة"

# ─── 5. إصلاح مسارات ملفات الخدمة ────────────────────
info "ضبط ملفات systemd..."

# smm_bot.service
cat > /etc/systemd/system/${BOT_SERVICE}.service << EOF
[Unit]
Description=SMM Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${BOT_DIR}
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
StandardOutput=append:/var/log/smm_bot.log
StandardError=append:/var/log/smm_bot.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# smm_invoice.service
cat > /etc/systemd/system/${WEB_SERVICE}.service << EOF
[Unit]
Description=A1SMM Invoice Web Server
After=network.target ${BOT_SERVICE}.service

[Service]
Type=simple
User=root
WorkingDirectory=${BOT_DIR}
ExecStart=/usr/bin/python3 invoice_web.py
Restart=always
RestartSec=5
StandardOutput=append:/var/log/smm_invoice.log
StandardError=append:/var/log/smm_invoice.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
success "ملفات systemd جاهزة"

# ─── 6. تشغيل البوت ───────────────────────────────────
info "تشغيل البوت..."
systemctl enable "$BOT_SERVICE" --quiet
systemctl restart "$BOT_SERVICE"
sleep 2

if systemctl is-active --quiet "$BOT_SERVICE"; then
    success "البوت يعمل ✓"
else
    warn "البوت لم يبدأ — تحقق من اللوج:"
    journalctl -u "$BOT_SERVICE" -n 20 --no-pager
fi

# ─── 7. تشغيل خادم الفواتير ───────────────────────────
info "تشغيل خادم الفواتير (Flask)..."
systemctl enable "$WEB_SERVICE" --quiet
systemctl restart "$WEB_SERVICE"
sleep 2

if systemctl is-active --quiet "$WEB_SERVICE"; then
    success "خادم الفواتير يعمل على المنفذ 5000 ✓"
else
    warn "خادم الفواتير لم يبدأ — تحقق من اللوج:"
    journalctl -u "$WEB_SERVICE" -n 20 --no-pager
fi

# ─── 8. إعداد Nginx ───────────────────────────────────
NGINX_CONF="/etc/nginx/sites-available/a1smm.store"
if [ ! -f "$NGINX_CONF" ]; then
    info "ضبط Nginx..."
    cp "$BOT_DIR/a1smm.store.nginx.conf" "$NGINX_CONF"
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t 2>/dev/null && systemctl restart nginx
    success "Nginx جاهز"
fi

# ─── 9. ملخص ──────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ التثبيت اكتمل بنجاح!${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}الخدمات:${NC}"
echo "  البوت:    systemctl status $BOT_SERVICE"
echo "  الموقع:   systemctl status $WEB_SERVICE"
echo ""
echo -e "${CYAN}اللوجات:${NC}"
echo "  tail -f /var/log/smm_bot.log"
echo "  tail -f /var/log/smm_invoice.log"
echo ""
echo -e "${YELLOW}⚠️  للحصول على SSL (HTTPS):${NC}"
echo "  apt install certbot python3-certbot-nginx -y"
echo "  certbot --nginx -d a1smm.store -d www.a1smm.store"
echo ""
