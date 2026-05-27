/* AlMasry SMM — main.js */

// ── Mobile Menu ──
function toggleMenu() {
  const m = document.getElementById('mobileMenu');
  if (m) m.classList.toggle('open');
}

// ── Toast Notifications ──
function showToast(msg, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// ── Copy to Clipboard ──
function copyText(text, label = 'تم النسخ!') {
  navigator.clipboard.writeText(text).then(() => {
    showToast('📋 ' + label);
  }).catch(() => {
    showToast('❌ فشل النسخ', 'error');
  });
}

// ── Modal ──
function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add('open'); document.body.style.overflow = 'hidden'; }
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove('open'); document.body.style.overflow = ''; }
}

// Close modal on backdrop click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// ── Format Numbers ──
function fmt(n, decimals = 4) {
  return parseFloat(n).toFixed(decimals);
}

// ── API Request helper ──
async function apiRequest(url, method = 'GET', data = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (data) opts.body = JSON.stringify(data);
  const r = await fetch(url, opts);
  return r.json();
}

// ── Regenerate API Key ──
async function regenerateKey() {
  if (!confirm('هل تريد إنشاء مفتاح API جديد؟ المفتاح القديم سيتوقف عن العمل.')) return;
  const r = await apiRequest('/api/regenerate-key', 'POST');
  if (r.key) {
    document.getElementById('apiKeyText').textContent = r.key;
    showToast('✅ تم إنشاء مفتاح جديد');
  }
}

// ── Services Page Logic ──
let allServices = [];

function initServices(services) {
  allServices = services;
  renderServices(services);
}

function filterByPlatform(platformId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');

  if (!platformId) {
    renderServices(allServices);
    return;
  }
  renderServices(allServices.filter(s => s.platform_id == platformId));
}

function filterByCategory(categoryId) {
  document.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  renderServices(allServices.filter(s => s.category_id == categoryId));
}

function searchServices() {
  const q = document.getElementById('svcSearch').value.toLowerCase();
  renderServices(allServices.filter(s => s.name.toLowerCase().includes(q)));
}

function renderServices(svcs) {
  const container = document.getElementById('servicesGrid');
  if (!container) return;
  if (!svcs.length) {
    container.innerHTML = '<p style="color:var(--text2);text-align:center;padding:2rem">لا توجد خدمات</p>';
    return;
  }
  container.innerHTML = svcs.map(s => `
    <div class="service-card" onclick="openOrderModal(${JSON.stringify(s).replace(/"/g, '&quot;')})">
      <div class="svc-name">${s.name}</div>
      <div class="svc-price">$${fmt(s.display_price, 4)} / 1000</div>
      <div class="svc-meta">
        📦 ${s.min_qty.toLocaleString()} — ${s.max_qty.toLocaleString()}
        ${s.platform ? '| 📱 ' + s.platform : ''}
      </div>
    </div>
  `).join('');
}

// ── Order Modal ──
let currentSvc = null;

function openOrderModal(svc) {
  currentSvc = svc;
  document.getElementById('modalSvcName').textContent  = svc.name;
  document.getElementById('modalSvcPrice').textContent = '$' + fmt(svc.display_price, 4) + ' / 1000';
  document.getElementById('modalMinQty').textContent   = svc.min_qty.toLocaleString();
  document.getElementById('modalMaxQty').textContent   = svc.max_qty.toLocaleString();
  document.getElementById('orderQty').value   = svc.min_qty;
  document.getElementById('orderQty').min     = svc.min_qty;
  document.getElementById('orderQty').max     = svc.max_qty;
  document.getElementById('orderLink').value  = '';
  document.getElementById('orderTotal').textContent = '$0.0000';
  document.getElementById('orderSvcId').value = svc.id;
  updateOrderTotal();
  openModal('orderModal');
}

function updateOrderTotal() {
  if (!currentSvc) return;
  const qty = parseInt(document.getElementById('orderQty').value) || 0;
  const total = (currentSvc.display_price / 1000) * qty;
  document.getElementById('orderTotal').textContent = '$' + fmt(total, 4);
}

async function submitOrder() {
  const svcId = document.getElementById('orderSvcId').value;
  const link  = document.getElementById('orderLink').value.trim();
  const qty   = document.getElementById('orderQty').value;

  if (!link) { showToast('❌ أدخل الرابط', 'error'); return; }

  const btn = document.getElementById('orderBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> جاري الإرسال...';

  const formData = new FormData();
  formData.append('service_id', svcId);
  formData.append('link', link);
  formData.append('quantity', qty);

  try {
    const r = await fetch('/add-order', { method: 'POST', body: formData });
    const data = await r.json();
    if (data.success) {
      showToast(`✅ تم إرسال الطلب #${data.order_id} بنجاح`);
      closeModal('orderModal');
      setTimeout(() => window.location.reload(), 1500);
    } else {
      showToast('❌ ' + (data.error || 'فشل الطلب'), 'error');
    }
  } catch {
    showToast('❌ خطأ في الاتصال', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✅ تأكيد الطلب';
  }
}

// ── Status Badge ──
function statusBadge(status) {
  const map = {
    'pending':     ['badge-yellow', '⏳ قيد الانتظار'],
    'in progress': ['badge-blue',   '⚙️ جاري'],
    'processing':  ['badge-blue',   '⚙️ جاري'],
    'completed':   ['badge-green',  '✅ مكتمل'],
    'canceled':    ['badge-red',    '❌ ملغي'],
    'cancelled':   ['badge-red',    '❌ ملغي'],
    'partial':     ['badge-yellow', '⚠️ جزئي'],
  };
  const [cls, label] = map[status?.toLowerCase()] || ['badge-gray', status || '—'];
  return `<span class="badge ${cls}">${label}</span>`;
}

// Init status badges on load
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-status]').forEach(el => {
    el.innerHTML = statusBadge(el.dataset.status);
  });
});
