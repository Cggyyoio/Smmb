#!/bin/bash
# ══════════════════════════════════════════════════════════════
# AlMasry SMM Website — سكريبت التثبيت الكامل
# Ubuntu 24.04 | VPS 512MB RAM
# ══════════════════════════════════════════════════════════════

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── متغيرات ───────────────────────────────────────────────────
BOT_DIR="/root/smmbot-main"
WEB_DIR="/root/a1smm/website"
DOMAIN="a1smm.store"
BOT_USERNAME="AlMasrySMMBot"   # غيّر ده لاسم البوت بتاعك

# ── 1. تحديث النظام ──────────────────────────────────────────
log "تحديث النظام..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. تثبيت المتطلبات ───────────────────────────────────────
log "تثبيت nginx, python3, certbot..."
apt-get install -y -qq nginx python3 python3-pip python3-venv \
    certbot python3-certbot-nginx

# ── 3. نسخ ملفات الموقع ──────────────────────────────────────
log "نسخ ملفات الموقع..."
mkdir -p "$WEB_DIR"
cp -r /root/a1smm_upload/* "$WEB_DIR/"

# ── 4. Virtual Environment ───────────────────────────────────
log "إنشاء بيئة Python..."
python3 -m venv /root/a1smm/venv
/root/a1smm/venv/bin/pip install -q --upgrade pip
/root/a1smm/venv/bin/pip install -q -r "$WEB_DIR/requirements.txt"

# ── 5. توليد WEB_SECRET ──────────────────────────────────────
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s/CHANGE_THIS_TO_RANDOM_SECRET/$SECRET/" \
    /etc/systemd/system/a1smm.service

# ── 6. تعيين اسم البوت في DB ─────────────────────────────────
log "تعيين اسم البوت في الإعدادات..."
python3 -c "
import sqlite3
db = sqlite3.connect('$BOT_DIR/data/bot.db')
db.execute(\"INSERT OR REPLACE INTO settings (key,value) VALUES ('BOT_USERNAME','$BOT_USERNAME')\")
db.commit()
db.close()
print('✓ Bot username set')
" || warn "تعذّر تعيين اسم البوت — عيّنه يدوياً من لوحة الأدمن"

# ── 7. nginx ─────────────────────────────────────────────────
log "إعداد nginx..."
cp /root/a1smm/nginx/a1smm.conf /etc/nginx/sites-available/a1smm.conf
ln -sf /etc/nginx/sites-available/a1smm.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 8. SSL ───────────────────────────────────────────────────
log "إنشاء SSL certificate..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
    --non-interactive --agree-tos \
    --email "admin@$DOMAIN" \
    --redirect || warn "فشل SSL — شغّل يدوياً: certbot --nginx -d $DOMAIN"

# ── 9. Systemd service ───────────────────────────────────────
log "تفعيل خدمة الموقع..."
cp /root/a1smm/systemd/a1smm.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable a1smm
systemctl start a1smm

# ── 10. تحقق ─────────────────────────────────────────────────
sleep 2
if systemctl is-active --quiet a1smm; then
    log "✅ الموقع شغال على https://$DOMAIN"
else
    err "❌ فشل تشغيل الموقع — شوف: journalctl -u a1smm -n 50"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ التثبيت اكتمل بنجاح!${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo "  🌐 الموقع:  https://$DOMAIN"
echo "  📁 المسار:  $WEB_DIR"
echo "  📝 اللوج:   journalctl -u a1smm -f"
echo ""
