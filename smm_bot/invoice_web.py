"""
╔══════════════════════════════════════════════════════════════╗
║          صفحة الفاتورة على الويب — invoice_web.py           ║
║  يُشغَّل بجانب البوت على نفس السيرفر                        ║
║  الدومين: a1smm.store                                        ║
║  الرابط:  https://a1smm.store/pay/INV-XXXX                  ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import logging
import asyncio
import threading
from datetime import datetime, timezone

from flask import Flask, render_template_string, jsonify, request, abort

from database import Database
from config import DATABASE_PATH, BOT_TOKEN, BOT_USERNAME, ADMIN_ID

logger = logging.getLogger(__name__)

app = Flask(__name__)
db  = Database(DATABASE_PATH)


# ══════════════════════════════════════════════════════════════
#  مساعدات
# ══════════════════════════════════════════════════════════════

def _get_vod_rate() -> float:
    """سعر الصرف: كم جنيه = 1 دولار (من autocash أو الإعداد اليدوي)."""
    try:
        from vodafone_cash_pay import VodafoneCashHandler
        vah = VodafoneCashHandler(db, None)
        return vah.get_rate()
    except Exception:
        try:
            return float(db.get_setting("vod_egp_rate", "50"))
        except Exception:
            return 50.0


def _get_stars_rate() -> float:
    """عدد النجوم مقابل 1 دولار."""
    try:
        return float(db.get_setting("stars_per_dollar", "85"))
    except Exception:
        return 85.0


def _stars_enabled() -> bool:
    return db.get_setting("pay_stars", "0") == "1"


def _binance_enabled() -> bool:
    return db.get_setting("pay_binance", "0") == "1"


def _vod_enabled() -> bool:
    """فودافون مفعّل: يدوي أو تلقائي."""
    return bool(db.get_setting("vodafone_number", "")) or \
           db.get_setting("pay_vodafone_auto", "0") == "1"


def _inv_status_ar(status: str) -> str:
    return {"pending": "⏳ قيد الانتظار",
            "paid":    "✅ مدفوعة",
            "expired": "❌ منتهية الصلاحية"}.get(status, status)


def _is_expired(inv: dict) -> bool:
    if inv["status"] != "pending":
        return False
    exp = inv.get("expires_at")
    if not exp:
        return False
    try:
        exp_dt = datetime.fromisoformat(str(exp))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp_dt
    except Exception:
        return False


def _notify_bot_paid(inv_id: str, user_tg_id: int, amount_usd: float, method: str):
    """يرسل إشعاراً للمستخدم والأدمن عبر البوت بشكل async في thread منفصل."""
    async def _send():
        from telegram import Bot
        try:
            bot = Bot(token=BOT_TOKEN)
            balance = db.get_balance(user_tg_id)
            await bot.send_message(
                chat_id=user_tg_id,
                text=(
                    f"✅ <b>تم شحن رصيدك!</b>\n\n"
                    f"🧾 الفاتورة: <code>{inv_id}</code>\n"
                    f"💰 المبلغ: <b>${amount_usd:.2f}</b>\n"
                    f"💳 طريقة الدفع: <b>{method}</b>\n"
                    f"💼 رصيدك الآن: <b>${balance:.2f}</b>"
                ),
                parse_mode="HTML",
            )
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"💰 <b>فاتورة مدفوعة</b>\n\n"
                    f"🧾 {inv_id}\n"
                    f"👤 <code>{user_tg_id}</code>\n"
                    f"💵 ${amount_usd:.2f}\n"
                    f"📲 {method}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"[WEB] إشعار البوت فشل: {e}")

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_send())
        loop.close()

    threading.Thread(target=_run, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  HTML Template
# ══════════════════════════════════════════════════════════════

PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>فاتورة {{ inv_id }} — A1SMM</title>
<style>
  :root{
    --bg:#0d1117;--surface:#161b22;--border:#30363d;
    --accent:#58a6ff;--green:#3fb950;--red:#f85149;
    --yellow:#e3b341;--text:#e6edf3;--muted:#8b949e;
    --card:#1c2128;--radius:12px;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;
       min-height:100vh;display:flex;flex-direction:column;align-items:center;
       padding:20px 16px 60px}

  .logo{display:flex;align-items:center;gap:10px;margin-bottom:28px;margin-top:12px}
  .logo-icon{width:44px;height:44px;background:linear-gradient(135deg,#58a6ff,#1f6feb);
             border-radius:12px;display:flex;align-items:center;justify-content:center;
             font-size:22px}
  .logo-text{font-size:22px;font-weight:700;color:var(--text)}
  .logo-sub{font-size:12px;color:var(--muted)}

  .card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
        width:100%;max-width:520px;overflow:hidden;margin-bottom:16px}

  .card-header{padding:18px 20px;border-bottom:1px solid var(--border);
               display:flex;justify-content:space-between;align-items:center}
  .card-title{font-size:15px;font-weight:600;color:var(--muted)}
  .inv-id{font-family:monospace;font-size:14px;color:var(--accent);background:#1f2937;
          padding:4px 10px;border-radius:6px;cursor:pointer}
  .inv-id:hover{background:#263147}

  .amount-section{padding:28px 20px;text-align:center;
                  border-bottom:1px solid var(--border)}
  .amount-label{font-size:13px;color:var(--muted);margin-bottom:8px}
  .amount-value{font-size:42px;font-weight:800;color:var(--text);letter-spacing:-1px}
  .amount-usd{font-size:18px;color:var(--muted)}

  .meta-row{display:flex;justify-content:space-between;padding:12px 20px;
            border-bottom:1px solid var(--border);font-size:14px}
  .meta-row:last-child{border-bottom:none}
  .meta-key{color:var(--muted)}
  .meta-val{font-weight:500}

  .status-pending{color:var(--yellow)}
  .status-paid   {color:var(--green)}
  .status-expired{color:var(--red)}

  .methods{width:100%;max-width:520px}
  .method-card{background:var(--card);border:1px solid var(--border);
               border-radius:var(--radius);margin-bottom:12px;overflow:hidden;
               transition:border-color .2s}
  .method-card.active{border-color:var(--accent)}
  .method-header{padding:14px 18px;display:flex;align-items:center;gap:12px;
                 cursor:pointer;user-select:none}
  .method-icon{font-size:24px;width:40px;text-align:center}
  .method-title{font-size:15px;font-weight:600}
  .method-sub{font-size:12px;color:var(--muted);margin-top:2px}
  .method-chevron{margin-right:auto;color:var(--muted);transition:transform .25s;font-size:18px}
  .method-card.active .method-chevron{transform:rotate(180deg);color:var(--accent)}
  .method-body{display:none;padding:0 18px 18px}
  .method-card.active .method-body{display:block}

  .info-box{background:#0d1117;border:1px solid var(--border);border-radius:8px;
            padding:14px;font-size:13px;line-height:1.7;margin-bottom:14px}
  .info-box b{color:var(--accent)}
  .info-box .amount-egp{font-size:22px;font-weight:800;color:var(--green);display:block;
                         margin:6px 0}
  .info-box .vod-num{font-size:18px;font-weight:700;color:var(--yellow);display:block;
                     margin:4px 0}

  .btn{display:block;width:100%;padding:13px;border:none;border-radius:8px;
       font-size:15px;font-weight:600;cursor:pointer;text-align:center;
       text-decoration:none;transition:opacity .15s,transform .1s}
  .btn:hover{opacity:.88;transform:translateY(-1px)}
  .btn:active{transform:translateY(0)}
  .btn-primary{background:linear-gradient(135deg,#1f6feb,#58a6ff);color:#fff}
  .btn-stars{background:linear-gradient(135deg,#7c3aed,#a78bfa);color:#fff}
  .btn-binance{background:linear-gradient(135deg,#b45309,#f59e0b);color:#fff}
  .btn-verify{background:var(--surface);border:1px solid var(--border);color:var(--text);
              margin-top:10px}

  .copy-btn{display:inline-flex;align-items:center;gap:6px;background:#1f2937;
            border:1px solid var(--border);color:var(--accent);padding:6px 12px;
            border-radius:6px;font-size:13px;cursor:pointer;margin-top:8px}
  .copy-btn:hover{background:#263147}

  .timer{text-align:center;font-size:13px;color:var(--muted);margin-top:6px}
  .timer span{color:var(--yellow);font-weight:600}

  .paid-banner{background:#0f2a1a;border:1px solid #2ea043;border-radius:var(--radius);
               padding:20px;text-align:center;width:100%;max-width:520px;
               font-size:16px;font-weight:600;color:var(--green);margin-bottom:16px}
  .expired-banner{background:#2d1515;border:1px solid #f85149;border-radius:var(--radius);
                  padding:20px;text-align:center;width:100%;max-width:520px;
                  font-size:16px;font-weight:600;color:var(--red);margin-bottom:16px}

  .spinner{display:inline-block;width:18px;height:18px;border:2px solid rgba(255,255,255,.3);
           border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;
           vertical-align:middle;margin-left:8px}
  @keyframes spin{to{transform:rotate(360deg)}}

  .toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(100px);
         background:#1c2128;border:1px solid var(--border);color:var(--text);
         padding:12px 22px;border-radius:8px;font-size:14px;
         transition:transform .3s;z-index:999}
  .toast.show{transform:translateX(-50%) translateY(0)}

  @media(max-width:540px){
    .amount-value{font-size:32px}
    .card-header{flex-direction:column;gap:8px;align-items:flex-start}
  }
</style>
</head>
<body>

<div class="logo">
  <div class="logo-icon">💎</div>
  <div>
    <div class="logo-text">A1SMM</div>
    <div class="logo-sub">بوابة دفع آمنة</div>
  </div>
</div>

<!-- بطاقة الفاتورة الرئيسية -->
<div class="card">
  <div class="card-header">
    <span class="card-title">رقم الفاتورة</span>
    <span class="inv-id" onclick="copyText('{{ inv_id }}',this)">{{ inv_id }}</span>
  </div>

  <div class="amount-section">
    <div class="amount-label">المبلغ المطلوب</div>
    <div class="amount-value">${{ "%.2f"|format(amount_usd) }}</div>
    <div class="amount-usd">دولار أمريكي</div>
  </div>

  <div class="meta-row">
    <span class="meta-key">الحالة</span>
    <span class="meta-val {{ 'status-'+status }}">{{ status_ar }}</span>
  </div>
  <div class="meta-row">
    <span class="meta-key">وقت الإنشاء</span>
    <span class="meta-val">{{ created_at }}</span>
  </div>
  {% if expires_at %}
  <div class="meta-row">
    <span class="meta-key">تنتهي في</span>
    <span class="meta-val status-pending" id="expires-text">{{ expires_at }}</span>
  </div>
  {% endif %}
</div>

<!-- بانر الدفع المكتمل -->
{% if status == 'paid' %}
<div class="paid-banner">✅ تم الدفع وإضافة الرصيد بنجاح!</div>
{% elif status == 'expired' or expired %}
<div class="expired-banner">❌ انتهت صلاحية هذه الفاتورة</div>
{% else %}

<!-- طرق الدفع -->
<div class="methods">
  <div style="font-size:14px;color:var(--muted);margin-bottom:12px;text-align:center">
    اختر طريقة الدفع المناسبة
  </div>

  <!-- ── فودافون كاش ── -->
  {% if vod_enabled %}
  <div class="method-card" id="mc-vod">
    <div class="method-header" onclick="toggleMethod('vod')">
      <div class="method-icon">📱</div>
      <div>
        <div class="method-title">Vodafone Cash</div>
        <div class="method-sub">دفع لحظي بالجنيه المصري</div>
      </div>
      <div class="method-chevron">⌄</div>
    </div>
    <div class="method-body">
      <div class="info-box">
        💱 سعر الصرف: <b>1$ = {{ vod_rate }} ج.م</b><br>
        المبلغ المطلوب:<br>
        <span class="amount-egp">{{ vod_egp }} ج.م</span>
        حوّل على رقم فودافون كاش:<br>
        <span class="vod-num" id="vod-num">{{ vod_number }}</span>
        <button class="copy-btn" onclick="copyText('{{ vod_number }}',this)">📋 نسخ الرقم</button>
      </div>
      <div id="vod-steps">
        <div style="font-size:13px;color:var(--muted);margin-bottom:10px">
          بعد التحويل أدخل رقم هاتفك للتحقق التلقائي:
        </div>
        <input id="vod-phone" type="tel" placeholder="01xxxxxxxxx"
               style="width:100%;padding:11px;border-radius:8px;border:1px solid var(--border);
                      background:#0d1117;color:var(--text);font-size:15px;margin-bottom:10px">
        <input id="vod-amount-egp" type="number" placeholder="المبلغ الذي حوّلته (جنيه)"
               value="{{ vod_egp }}"
               style="width:100%;padding:11px;border-radius:8px;border:1px solid var(--border);
                      background:#0d1117;color:var(--text);font-size:15px;margin-bottom:10px">
        <button class="btn btn-primary" onclick="verifyVodafone()">
          ✅ تحقق من الدفع
        </button>
      </div>
      <div id="vod-result" style="display:none"></div>
    </div>
  </div>
  {% endif %}

  <!-- ── Telegram Stars ── -->
  {% if stars_enabled %}
  <div class="method-card" id="mc-stars">
    <div class="method-header" onclick="toggleMethod('stars')">
      <div class="method-icon">⭐</div>
      <div>
        <div class="method-title">Telegram Stars</div>
        <div class="method-sub">دفع فوري بنجوم تيليغرام</div>
      </div>
      <div class="method-chevron">⌄</div>
    </div>
    <div class="method-body">
      <div class="info-box">
        ⭐ عدد النجوم المطلوبة:<br>
        <span class="amount-egp" style="color:#a78bfa">{{ stars_count }} نجمة</span>
        💱 السعر: <b>{{ stars_rate }} نجمة = $1</b>
      </div>
      <a class="btn btn-stars"
         href="https://t.me/{{ bot_username }}?start=stars_pay_{{ inv_id }}"
         target="_blank">
        ⭐ ادفع الآن بالنجوم
      </a>
      <div class="timer" style="margin-top:12px;font-size:12px;color:var(--muted)">
        بعد الضغط سيفتح البوت وتتم عملية الدفع تلقائياً
      </div>
    </div>
  </div>
  {% endif %}

  <!-- ── Binance Pay ── -->
  {% if binance_enabled %}
  <div class="method-card" id="mc-binance">
    <div class="method-header" onclick="toggleMethod('binance')">
      <div class="method-icon">💛</div>
      <div>
        <div class="method-title">Binance Pay</div>
        <div class="method-sub">دفع عبر منصة Binance</div>
      </div>
      <div class="method-chevron">⌄</div>
    </div>
    <div class="method-body">
      <div class="info-box">
        💰 المبلغ: <b>${{ "%.2f"|format(amount_usd) }}</b><br>
        حوّل على Binance ID:<br>
        <span style="font-size:20px;font-weight:700;color:var(--yellow);display:block;margin:4px 0"
              id="binance-id">{{ binance_id }}</span>
        <button class="copy-btn" onclick="copyText('{{ binance_id }}',this)">📋 نسخ</button>
      </div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:10px">
        بعد التحويل، ادخل Order ID من تطبيق Binance:
      </div>
      <input id="binance-order" type="text" placeholder="Order ID (مثال: 429587669106335744)"
             style="width:100%;padding:11px;border-radius:8px;border:1px solid var(--border);
                    background:#0d1117;color:var(--text);font-size:14px;margin-bottom:10px;
                    direction:ltr">
      <button class="btn btn-binance" onclick="verifyBinance()">
        🔍 تحقق من الدفع
      </button>
      <div id="binance-result" style="display:none;margin-top:10px"></div>
    </div>
  </div>
  {% endif %}

  <!-- ── USDT / TRX / TON ── -->
  {% if crypto_methods %}
  {% for cm in crypto_methods %}
  <div class="method-card" id="mc-{{ cm.key }}">
    <div class="method-header" onclick="toggleMethod('{{ cm.key }}')">
      <div class="method-icon">{{ cm.icon }}</div>
      <div>
        <div class="method-title">{{ cm.name }}</div>
        <div class="method-sub">{{ cm.network }}</div>
      </div>
      <div class="method-chevron">⌄</div>
    </div>
    <div class="method-body">
      <div class="info-box">
        💰 المبلغ: <b>{{ "%.4f"|format(amount_usd) }} {{ cm.symbol }}</b><br>
        العنوان:<br>
        <span style="font-family:monospace;font-size:12px;word-break:break-all;
                     color:var(--accent);display:block;margin:6px 0">{{ cm.address }}</span>
        <button class="copy-btn" onclick="copyText('{{ cm.address }}',this)">📋 نسخ العنوان</button>
      </div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:10px">
        بعد الإرسال، أدخل TXID للتحقق:
      </div>
      <input id="txid-{{ cm.key }}" type="text" placeholder="Transaction Hash / TXID"
             style="width:100%;padding:11px;border-radius:8px;border:1px solid var(--border);
                    background:#0d1117;color:var(--text);font-size:13px;margin-bottom:10px;
                    direction:ltr">
      <button class="btn btn-primary" onclick="verifyCrypto('{{ cm.key }}','{{ cm.network_id }}')">
        🔍 تحقق من التحويل
      </button>
      <div id="crypto-result-{{ cm.key }}" style="display:none;margin-top:10px"></div>
    </div>
  </div>
  {% endfor %}
  {% endif %}

</div><!-- /methods -->
{% endif %}

<div id="toast" class="toast"></div>

<script>
const INV_ID  = "{{ inv_id }}";
const API_BASE = "";

// ── فتح/إغلاق طرق الدفع ──
function toggleMethod(key){
  const card = document.getElementById('mc-'+key);
  const isActive = card.classList.contains('active');
  document.querySelectorAll('.method-card').forEach(c=>c.classList.remove('active'));
  if(!isActive) card.classList.add('active');
}

// ── نسخ النص ──
function copyText(txt, el){
  navigator.clipboard.writeText(txt).then(()=>{
    const orig = el.textContent;
    el.textContent = '✅ تم النسخ';
    setTimeout(()=>el.textContent=orig, 1500);
  });
}

// ── توست ──
function showToast(msg, isOk=true){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = isOk ? 'var(--green)' : 'var(--red)';
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 3500);
}

// ── عداد الوقت ──
{% if expires_at_iso %}
(function(){
  const exp = new Date("{{ expires_at_iso }}");
  const el  = document.getElementById('expires-text');
  if(!el) return;
  setInterval(()=>{
    const diff = exp - new Date();
    if(diff <= 0){ el.textContent = '⏰ انتهت'; el.className='meta-val status-expired'; return; }
    const m = Math.floor(diff/60000);
    const s = Math.floor((diff%60000)/1000);
    el.textContent = `${m}:${s<10?'0':''}${s} دقيقة`;
  }, 1000);
})();
{% endif %}

// ══════════════════════════════════════════════════════════
//  فودافون كاش
// ══════════════════════════════════════════════════════════
async function verifyVodafone(){
  const phone  = document.getElementById('vod-phone').value.trim();
  const amount = document.getElementById('vod-amount-egp').value.trim();
  const res    = document.getElementById('vod-result');
  const steps  = document.getElementById('vod-steps');
  if(!phone){ showToast('❌ أدخل رقم الهاتف',false); return; }
  if(!amount){ showToast('❌ أدخل المبلغ',false); return; }

  steps.innerHTML = '<div style="text-align:center;padding:16px;color:var(--muted)">⏳ جاري التحقق...<div class="spinner"></div></div>';

  const r = await fetch(`/api/pay/vodafone`, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({inv_id: INV_ID, phone, amount_egp: parseFloat(amount)})
  }).then(x=>x.json()).catch(()=>({ok:false,msg:'خطأ في الاتصال'}));

  if(r.ok){
    steps.style.display='none';
    res.style.display='block';
    res.innerHTML=`<div class="info-box" style="border-color:var(--green);text-align:center">
      ✅ <b>تم التحقق وإضافة رصيدك!</b><br>
      💰 أضيف: <b>$${r.usd}</b><br>
      <a href="https://t.me/{{ bot_username }}" class="btn btn-primary" style="margin-top:12px;display:inline-block;text-decoration:none">🤖 العودة للبوت</a>
    </div>`;
    showToast('✅ تم شحن رصيدك!');
    setTimeout(()=>location.reload(), 5000);
  } else {
    steps.innerHTML = `<div style="font-size:13px;color:var(--muted);margin-bottom:10px">بعد التحويل أدخل رقم هاتفك للتحقق التلقائي:</div>
      <input id="vod-phone" type="tel" placeholder="01xxxxxxxxx"
             value="${phone}"
             style="width:100%;padding:11px;border-radius:8px;border:1px solid var(--border);
                    background:#0d1117;color:var(--text);font-size:15px;margin-bottom:10px">
      <input id="vod-amount-egp" type="number" placeholder="المبلغ الذي حوّلته"
             value="${amount}"
             style="width:100%;padding:11px;border-radius:8px;border:1px solid var(--border);
                    background:#0d1117;color:var(--text);font-size:15px;margin-bottom:10px">
      <button class="btn btn-primary" onclick="verifyVodafone()">✅ تحقق من الدفع</button>`;
    showToast('❌ '+(r.msg||'فشل التحقق'),false);
  }
}

// ══════════════════════════════════════════════════════════
//  Binance Pay
// ══════════════════════════════════════════════════════════
async function verifyBinance(){
  const order_id = document.getElementById('binance-order').value.trim();
  const res = document.getElementById('binance-result');
  if(!order_id){ showToast('❌ أدخل Order ID',false); return; }

  res.style.display='block';
  res.innerHTML='<div style="color:var(--muted);font-size:13px">⏳ جاري التحقق...<div class="spinner"></div></div>';

  const r = await fetch('/api/pay/binance', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({inv_id: INV_ID, order_id})
  }).then(x=>x.json()).catch(()=>({ok:false,msg:'خطأ في الاتصال'}));

  if(r.ok){
    res.innerHTML=`<div class="info-box" style="border-color:var(--green);text-align:center">
      ✅ <b>تم الشحن!</b> أضيف $${r.amount}<br>
      <a href="https://t.me/{{ bot_username }}" class="btn btn-binance" style="margin-top:12px;display:inline-block;text-decoration:none">🤖 العودة للبوت</a>
    </div>`;
    showToast('✅ تم شحن رصيدك!');
    setTimeout(()=>location.reload(), 4000);
  } else {
    res.innerHTML=`<div style="color:var(--red);font-size:13px">❌ ${r.msg||'فشل التحقق'}</div>`;
    showToast('❌ '+(r.msg||'فشل'),false);
  }
}

// ══════════════════════════════════════════════════════════
//  العملات الرقمية
// ══════════════════════════════════════════════════════════
async function verifyCrypto(network, networkId){
  const txid = document.getElementById('txid-'+network).value.trim();
  const res  = document.getElementById('crypto-result-'+network);
  if(!txid){ showToast('❌ أدخل TXID',false); return; }

  res.style.display='block';
  res.innerHTML='<div style="color:var(--muted);font-size:13px">⏳ جاري التحقق...<div class="spinner"></div></div>';

  const r = await fetch('/api/pay/crypto', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({inv_id: INV_ID, txid, network: networkId})
  }).then(x=>x.json()).catch(()=>({ok:false,msg:'خطأ في الاتصال'}));

  if(r.ok){
    res.innerHTML=`<div class="info-box" style="border-color:var(--green);text-align:center">
      ✅ <b>تم الشحن!</b> أضيف $${r.amount}<br>
      <a href="https://t.me/{{ bot_username }}" class="btn btn-primary" style="margin-top:12px;display:inline-block;text-decoration:none">🤖 العودة للبوت</a>
    </div>`;
    showToast('✅ تم شحن رصيدك!');
    setTimeout(()=>location.reload(), 4000);
  } else {
    res.innerHTML=`<div style="color:var(--red);font-size:13px">❌ ${r.msg||'فشل التحقق'}</div>`;
    showToast('❌ '+(r.msg||'فشل'),false);
  }
}

// ── auto-reload عند الانتظار ──
{% if status == 'pending' and not expired %}
setTimeout(()=>location.reload(), 30000);
{% endif %}
</script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════

@app.route("/pay/<inv_id>")
def pay_page(inv_id: str):
    inv = db.get_invoice(inv_id)
    if not inv:
        abort(404)

    expired = _is_expired(inv)
    status  = "expired" if expired else inv["status"]

    # تحضير بيانات العرض
    amount_usd = float(inv["amount_usd"])
    vod_rate   = _get_vod_rate()
    vod_egp    = round(amount_usd * vod_rate)
    vod_number = db.get_setting("vodafone_number", "")
    stars_rate = _get_stars_rate()
    stars_count = int(amount_usd * stars_rate)

    # طرق الكريبتو
    crypto_methods = []
    cph_bep20 = db.get_setting("bep20_enabled", "0") == "1"
    cph_trc20 = db.get_setting("trc20_enabled", "0") == "1"
    ton_on    = db.get_setting("ton_enabled",   "0") == "1"
    trx_on    = db.get_setting("trx_enabled",   "0") == "1"

    if cph_bep20:
        crypto_methods.append({
            "key":"bep20","name":"USDT BEP20","symbol":"USDT",
            "icon":"💵","network":"BNB Smart Chain",
            "network_id":"bep20",
            "address": db.get_setting("bep20_address","")
        })
    if cph_trc20:
        crypto_methods.append({
            "key":"trc20","name":"USDT TRC20","symbol":"USDT",
            "icon":"💵","network":"TRON Network",
            "network_id":"trc20",
            "address": db.get_setting("trc20_address","")
        })
    if ton_on:
        crypto_methods.append({
            "key":"ton","name":"TON","symbol":"TON",
            "icon":"💎","network":"TON Blockchain",
            "network_id":"ton",
            "address": db.get_setting("ton_address","")
        })
    if trx_on:
        crypto_methods.append({
            "key":"trx","name":"TRX","symbol":"TRX",
            "icon":"🔴","network":"TRON Network",
            "network_id":"trx",
            "address": db.get_setting("trx_address","")
        })

    # تنسيق التواريخ
    try:
        created_at = str(inv["created_at"])[:16].replace("T"," ")
    except Exception:
        created_at = ""

    expires_at_display = ""
    expires_at_iso     = ""
    if inv.get("expires_at") and status == "pending":
        try:
            exp = datetime.fromisoformat(str(inv["expires_at"]))
            expires_at_display = exp.strftime("%Y-%m-%d %H:%M")
            expires_at_iso     = exp.isoformat() + "Z"
        except Exception:
            pass

    bot_username = BOT_USERNAME.lstrip("@") if BOT_USERNAME else "bot"

    return render_template_string(
        PAGE_HTML,
        inv_id         = inv_id,
        amount_usd     = amount_usd,
        status         = status,
        status_ar      = _inv_status_ar(status),
        expired        = expired,
        created_at     = created_at,
        expires_at     = expires_at_display,
        expires_at_iso = expires_at_iso,
        vod_enabled    = _vod_enabled(),
        vod_rate       = int(vod_rate),
        vod_egp        = vod_egp,
        vod_number     = vod_number,
        stars_enabled  = _stars_enabled(),
        stars_rate     = int(stars_rate),
        stars_count    = stars_count,
        binance_enabled= _binance_enabled(),
        binance_id     = db.get_setting("binance_pay_id",""),
        crypto_methods = crypto_methods,
        bot_username   = bot_username,
    )


# ══════════════════════════════════════════════════════════════
#  API: التحقق من الدفع
# ══════════════════════════════════════════════════════════════

@app.route("/api/pay/vodafone", methods=["POST"])
def api_pay_vodafone():
    data   = request.json or {}
    inv_id = data.get("inv_id","").strip()
    phone  = data.get("phone","").strip()
    amount_egp = float(data.get("amount_egp", 0))

    inv = db.get_invoice(inv_id)
    if not inv:
        return jsonify(ok=False, msg="فاتورة غير موجودة")
    if inv["status"] == "paid":
        return jsonify(ok=False, msg="هذه الفاتورة مدفوعة مسبقاً")
    if _is_expired(inv):
        return jsonify(ok=False, msg="انتهت صلاحية الفاتورة")
    if not phone or amount_egp <= 0:
        return jsonify(ok=False, msg="بيانات ناقصة")

    try:
        from vodafone_cash_pay import VodafoneCashHandler
        vah = VodafoneCashHandler(db, None)
        result = vah.check_payment(phone=phone, amount_egp=amount_egp)
    except Exception as e:
        return jsonify(ok=False, msg=f"خطأ في التحقق: {e}")

    if not result.get("status"):
        msg = result.get("message", "فشل التحقق من الدفع")
        return jsonify(ok=False, msg=msg)

    # إضافة الرصيد
    vod_rate  = _get_vod_rate()
    usd_added = round(amount_egp / vod_rate, 4)
    db.set_setting(f"inv_{inv_id}_pay_method", "Vodafone Cash")

    inv2 = db.get_invoice(inv_id)
    if not inv2:
        return jsonify(ok=False, msg="خطأ")

    # تحديث الفاتورة
    with db._conn() as conn:
        conn.execute(
            """UPDATE invoices SET status='paid', pay_method='Vodafone Cash',
               paid_at=datetime('now'), credited=1 WHERE inv_id=? AND credited=0""",
            (inv_id,)
        )
    db.add_balance(inv["user_tg_id"], usd_added)

    # إشعار إحالة
    from handlers.charge import _apply_referral_bonus
    _apply_referral_bonus(db, inv["user_tg_id"], usd_added)

    _notify_bot_paid(inv_id, inv["user_tg_id"], usd_added, "Vodafone Cash")
    return jsonify(ok=True, usd=f"{usd_added:.2f}")


@app.route("/api/pay/binance", methods=["POST"])
def api_pay_binance():
    data     = request.json or {}
    inv_id   = data.get("inv_id","").strip()
    order_id = data.get("order_id","").strip()

    inv = db.get_invoice(inv_id)
    if not inv:
        return jsonify(ok=False, msg="فاتورة غير موجودة")
    if inv["status"] == "paid":
        return jsonify(ok=False, msg="مدفوعة مسبقاً")
    if _is_expired(inv):
        return jsonify(ok=False, msg="انتهت الصلاحية")

    # فحص إذا استُخدم order_id من قبل
    used = db.get_setting(f"bnb_used_{order_id}", "")
    if used == "1":
        return jsonify(ok=False, msg="هذا Order ID استُخدم مسبقاً")

    api_key    = db.get_setting("binance_api_key",    "")
    api_secret = db.get_setting("binance_api_secret", "")

    if not api_key or not api_secret:
        # يدوي — أرسل للأدمن
        db.set_setting(f"bnb_used_{order_id}", "pending")
        uid      = inv["user_tg_id"]
        async def _notify():
            from telegram import Bot
            from utils.keyboards import admin_approve_binance_kb
            try:
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"💛 <b>Binance Pay (يدوي من الموقع)</b>\n"
                        f"🧾 الفاتورة: <code>{inv_id}</code>\n"
                        f"👤 <code>{uid}</code>\n"
                        f"🆔 Order ID: <code>{order_id}</code>"
                    ),
                    parse_mode="HTML",
                    reply_markup=admin_approve_binance_kb(order_id, uid),
                )
            except Exception as e:
                logger.warning(f"[WEB-BNB] {e}")

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_notify())
            loop.close()
        threading.Thread(target=_run, daemon=True).start()
        return jsonify(ok=False, msg="تم إرسال الطلب للمراجعة اليدوية، انتظر تأكيد الأدمن")

    # تلقائي
    import asyncio as _aio
    from handlers.stars_binance_pay import _verify_binance_order

    async def _check():
        return await _verify_binance_order(api_key, api_secret, order_id)

    loop   = asyncio.new_event_loop()
    amount = loop.run_until_complete(_check())
    loop.close()

    if amount is None or amount <= 0:
        return jsonify(ok=False, msg="لم يتم العثور على التحويل، تأكد من Order ID")

    db.set_setting(f"bnb_used_{order_id}", "1")
    ok = db.mark_invoice_paid(inv_id, "Binance Pay")
    if ok:
        db.add_balance(inv["user_tg_id"], amount)
        from handlers.charge import _apply_referral_bonus
        _apply_referral_bonus(db, inv["user_tg_id"], amount)
    _notify_bot_paid(inv_id, inv["user_tg_id"], amount, "Binance Pay")
    return jsonify(ok=True, amount=f"{amount:.4f}")


@app.route("/api/pay/crypto", methods=["POST"])
def api_pay_crypto():
    data   = request.json or {}
    inv_id = data.get("inv_id","").strip()
    txid   = data.get("txid","").strip()
    network= data.get("network","").strip()

    inv = db.get_invoice(inv_id)
    if not inv:
        return jsonify(ok=False, msg="فاتورة غير موجودة")
    if inv["status"] == "paid":
        return jsonify(ok=False, msg="مدفوعة مسبقاً")
    if _is_expired(inv):
        return jsonify(ok=False, msg="انتهت الصلاحية")

    if not txid:
        return jsonify(ok=False, msg="أدخل TXID")

    # استخدام CryptoPayHandler الموجود للتحقق
    try:
        from crypto_pay import CryptoPayHandler
        loop = asyncio.new_event_loop()

        async def _verify():
            cph = CryptoPayHandler(db=db, bot=None)
            return await cph.verify_txid(
                user_tg_id=inv["user_tg_id"],
                txid=txid,
                network=network,
            )

        result = loop.run_until_complete(_verify())
        loop.close()
    except Exception as e:
        return jsonify(ok=False, msg=f"خطأ في التحقق: {e}")

    if not result or not result.get("ok"):
        return jsonify(ok=False, msg=result.get("msg","فشل التحقق"))

    amount = float(result.get("credit", 0))
    ok = db.mark_invoice_paid(inv_id, network.upper())
    if ok:
        from handlers.charge import _apply_referral_bonus
        _apply_referral_bonus(db, inv["user_tg_id"], amount)

    _notify_bot_paid(inv_id, inv["user_tg_id"], amount, network.upper())
    return jsonify(ok=True, amount=f"{amount:.4f}")


@app.route("/api/invoice/<inv_id>")
def api_get_invoice(inv_id: str):
    inv = db.get_invoice(inv_id)
    if not inv:
        return jsonify(error="not found"), 404
    expired = _is_expired(inv)
    return jsonify(
        inv_id     = inv["inv_id"],
        amount_usd = inv["amount_usd"],
        status     = "expired" if expired else inv["status"],
        created_at = str(inv["created_at"]),
        expires_at = str(inv.get("expires_at","")),
        paid_at    = str(inv.get("paid_at","")),
    )


# ══════════════════════════════════════════════════════════════
#  Telegram Stars webhook — يستقبل إشعار stars_pay_INV-xxx
# ══════════════════════════════════════════════════════════════

@app.route("/api/stars_confirm", methods=["POST"])
def api_stars_confirm():
    """
    يُستدعى من داخل البوت عند نجاح دفع النجوم لفاتورة ويب.
    البوت يرسل: {inv_id, user_tg_id, stars_paid, usd}
    """
    data       = request.json or {}
    inv_id     = data.get("inv_id","").strip()
    usd        = float(data.get("usd", 0))
    user_tg_id = int(data.get("user_tg_id", 0))

    inv = db.get_invoice(inv_id)
    if not inv or inv["status"] == "paid":
        return jsonify(ok=False)

    ok = db.mark_invoice_paid(inv_id, "Telegram Stars")
    if ok:
        db.add_balance(user_tg_id, usd)
        from handlers.charge import _apply_referral_bonus
        _apply_referral_bonus(db, user_tg_id, usd)

    return jsonify(ok=ok)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=5000, debug=False)
