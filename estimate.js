/**
 * estimate.js — «Смета для клиента» (как в приложении СплитХаб)
 * Оборудование по цене монтажника для клиента (опт + наценка, округление вверх до 10 ₽;
 * оптовые цены в смету не попадают) + работы → PDF A4 через pdfmake.
 * Наценка, цены работ и контакты исполнителя запоминаются в localStorage.
 * Витрину и заявки не трогает: своя модалка, своё состояние, заявка (cart) только читается.
 */

const EST_SETTINGS_KEY = 'sh_estimate_settings';
const EST_ITEMS_KEY    = 'sh_estimate_items';
const EST_MARKUPS      = [0, 15, 20, 25, 30];
const EST_FILE_ICON    = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="12" x2="12" y2="18"/><polyline points="9 15 12 18 15 15"/></svg>';

/* Типовые работы монтажника — те же, что в приложении; каждая строка редактируется. */
function _estDefaultWorks() {
  return [
    { id: 'install',   name: 'Монтаж сплит-системы (стандартный, до 3 м трассы)', price: 8000, qty: 1 },
    { id: 'meter',     name: 'Дополнительный метр трассы', price: 1200, qty: 0, unit: 'м' },
    { id: 'dismantle', name: 'Демонтаж старого кондиционера', price: 2500, qty: 0 },
    { id: 'chase',     name: 'Штробление стены', price: 1000, qty: 0, unit: 'м' },
    { id: 'drain',     name: 'Дренажная помпа (установка)', price: 1500, qty: 0 },
  ];
}

function _estRead(key) {
  try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { return null; }
}
function _estWrite(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
}

const _est = {
  settings: null,   // { markupPercent, works, contractorName, contractorPhone, validDays }
  items: [],        // [{ id, qty }] — оборудование сметы (своё, заявку не меняет)
  clientName: '',
  objectAddress: '',
  busy: false,
};

function _estLoad() {
  if (_est.settings) return;
  const user = (typeof currentUser !== 'undefined' && currentUser) || {};
  const saved = _estRead(EST_SETTINGS_KEY) || {};
  _est.settings = {
    markupPercent: 25,
    works: _estDefaultWorks(),
    contractorName: user.company_name || user.name || '',
    contractorPhone: user.phone || '',
    validDays: 7,
  };
  if (saved.works && saved.works.length) Object.assign(_est.settings, saved);
  _est.items = (_estRead(EST_ITEMS_KEY) || []).filter(it => _estProduct(it.id));
}
function _estSaveSettings() { _estWrite(EST_SETTINGS_KEY, _est.settings); }
function _estSaveItems()    { _estWrite(EST_ITEMS_KEY, _est.items); }

function _estProduct(id) {
  return typeof findVisibleProduct === 'function' ? findVisibleProduct(id) : PRODUCTS.find(p => p.id === id);
}
function _estName(p) {
  const model = String(p.model || '');
  return p.brand && model.toUpperCase().indexOf(String(p.brand).toUpperCase()) !== 0 ? p.brand + ' ' + model : model;
}

/* ── Расчёт — один в один с приложением (src/features/estimate/estimate.ts) ── */
function estClientUnitPrice(wholesale, markupPercent, roundTo) {
  roundTo = roundTo || 10;
  const markup = Math.max(0, markupPercent);
  return Math.ceil((wholesale * (100 + markup)) / 100 / roundTo) * roundTo;
}

function estCompute() {
  const s = _est.settings;
  let wholesale = 0;
  const equipment = _est.items.map(it => {
    const p = _estProduct(it.id);
    wholesale += p.price * it.qty;
    const unitPrice = estClientUnitPrice(p.price, s.markupPercent);
    return { id: it.id, name: _estName(p), qty: it.qty, unitPrice, total: unitPrice * it.qty };
  });
  const works = s.works
    .filter(w => w.qty > 0 && w.price > 0)
    .map(w => ({ name: w.name, qty: w.qty, unit: w.unit, unitPrice: w.price, total: w.price * w.qty }));
  const equipmentTotal = equipment.reduce((sum, l) => sum + l.total, 0);
  const worksTotal = works.reduce((sum, l) => sum + l.total, 0);
  return { equipment, works, equipmentTotal, worksTotal, total: equipmentTotal + worksTotal, margin: equipmentTotal - wholesale };
}

const _estMoney = v => Number(v || 0).toLocaleString('ru-RU') + ' ₽';
const _estEsc = v => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const _estNum = v => Math.max(0, Number(String(v).replace(/[^\d]/g, '')) || 0);

/* ── Стили модалки (вставляются один раз) ── */
function _estInjectCss() {
  if (document.getElementById('estCss')) return;
  const css = `
.est-ov{position:fixed;inset:0;z-index:9990;background:rgba(10,14,26,0.55);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);display:flex;align-items:flex-end;justify-content:center;}
.est{background:#F7F8FA;width:100%;max-height:94vh;border-radius:22px 22px 0 0;display:flex;flex-direction:column;box-shadow:0 -12px 48px rgba(0,0,0,0.25);font-family:'Inter',sans-serif;color:var(--text,#1A1C22);}
.est-hd{display:flex;align-items:center;gap:10px;padding:16px 16px 12px;border-bottom:1px solid rgba(0,0,0,0.06);}
.est-hd h2{flex:1;margin:0;font-family:'Unbounded',sans-serif;font-size:1rem;font-weight:700;}
.est-x{border:none;background:rgba(0,0,0,0.06);width:34px;height:34px;border-radius:10px;font-size:1rem;cursor:pointer;}
.est-bd{overflow-y:auto;padding:4px 16px 16px;-webkit-overflow-scrolling:touch;}
.est-hint{font-size:0.78rem;color:var(--text2,#5A5F6E);margin:10px 0 0;}
.est-sec{font-size:0.95rem;font-weight:800;margin:18px 0 8px;display:flex;align-items:center;gap:8px;}
.est-sec small{font-weight:500;color:var(--text3,#9298A8);font-size:0.75rem;}
.est-in{width:100%;box-sizing:border-box;padding:11px 14px;margin-bottom:8px;border:1px solid rgba(0,0,0,0.12);background:#fff;border-radius:12px;font:inherit;font-size:0.9rem;color:inherit;outline:none;}
.est-in:focus{border-color:#F59E0B;box-shadow:0 0 0 3px rgba(245,158,11,0.14);}
.est-row2{display:grid;grid-template-columns:1fr;gap:0 10px;}
.est-search{position:relative;}
.est-sug{position:absolute;left:0;right:0;top:44px;z-index:2;background:#fff;border:1px solid rgba(0,0,0,0.1);border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,0.15);max-height:290px;overflow-y:auto;}
.est-sug button{display:flex;width:100%;gap:10px;align-items:center;justify-content:space-between;text-align:left;border:none;background:none;padding:10px 12px;font:inherit;font-size:0.84rem;cursor:pointer;border-bottom:1px solid rgba(0,0,0,0.05);}
.est-sug button:hover,.est-sug button:focus{background:rgba(245,158,11,0.1);outline:none;}
.est-sug b{font-weight:700;}
.est-sug span{color:var(--text3,#9298A8);font-size:0.74rem;display:block;}
.est-sug em{font-style:normal;font-weight:800;color:#D97706;white-space:nowrap;}
.est-empty{font-size:0.82rem;color:var(--text3,#9298A8);padding:6px 2px;}
.est-from-cart{border:1px dashed #F59E0B;background:rgba(245,158,11,0.07);color:#B45309;border-radius:12px;padding:10px;width:100%;font:inherit;font-size:0.84rem;font-weight:700;cursor:pointer;margin-bottom:8px;}
.est-line{display:flex;align-items:center;gap:10px;background:#fff;border-radius:12px;padding:10px 12px;margin-bottom:6px;box-shadow:0 1px 2px rgba(0,0,0,0.04);}
.est-line-tx{flex:1;min-width:0;}
@media(max-width:639px){.est-line{flex-wrap:wrap;row-gap:6px;}.est-line-tx{flex-basis:100%;}.est-line-t{flex:1;}}
.est-line-n{font-weight:700;font-size:0.86rem;}
.est-line-m{font-size:0.76rem;color:var(--text2,#5A5F6E);}
.est-line-t{font-weight:800;color:#D97706;white-space:nowrap;font-size:0.88rem;}
.est-step{display:flex;align-items:center;gap:6px;flex-shrink:0;}
.est-step button{width:30px;height:30px;border:none;border-radius:9px;background:#E5E7EB;font-size:1.05rem;font-weight:800;cursor:pointer;line-height:1;}
.est-step button.plus{background:#F59E0B;color:#fff;}
.est-step b{min-width:18px;text-align:center;font-size:0.9rem;}
.est-del{border:none;background:none;color:#9CA3AF;cursor:pointer;font-size:1rem;padding:4px;}
.est-del:hover{color:#EF4444;}
.est-chips{display:flex;flex-wrap:wrap;gap:8px;}
.est-chip{border:1px solid rgba(245,158,11,0.4);background:rgba(245,158,11,0.12);color:#B45309;border-radius:20px;padding:8px 14px;font:inherit;font-size:0.84rem;font-weight:800;cursor:pointer;}
.est-chip.on{background:#F59E0B;border-color:#F59E0B;color:#fff;}
.est-chip-in{width:84px;text-align:center;padding:7px 10px;}
.est-work{background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:10px 12px;margin-bottom:6px;opacity:0.72;}
.est-work.on{border-color:#F59E0B;opacity:1;}
.est-work-n{width:100%;border:none;background:none;font:inherit;font-weight:700;font-size:0.86rem;padding:0;outline:none;color:inherit;}
.est-work-r{display:flex;align-items:center;gap:8px;margin-top:8px;}
.est-work-p{width:90px;padding:6px 8px;border:1px solid rgba(0,0,0,0.12);border-radius:8px;font:inherit;font-size:0.86rem;}
.est-work-u{font-size:0.8rem;color:var(--text2,#5A5F6E);}
.est-work-r .est-step{margin-left:auto;}
.est-add{width:100%;border:1px dashed #F59E0B;background:none;color:#B45309;border-radius:12px;padding:10px;font:inherit;font-weight:700;font-size:0.86rem;cursor:pointer;}
.est-ft{border-top:1px solid rgba(0,0,0,0.06);padding:12px 16px calc(12px + env(safe-area-inset-bottom));background:#fff;border-radius:0;}
.est-tot{display:flex;justify-content:space-between;font-size:0.8rem;color:var(--text2,#5A5F6E);margin-bottom:2px;}
.est-tot b{color:var(--text,#1A1C22);}
.est-grand{display:flex;justify-content:space-between;align-items:baseline;margin:4px 0 2px;}
.est-grand span{font-weight:800;font-size:0.95rem;}
.est-grand b{font-family:'Unbounded',sans-serif;font-size:1.2rem;color:#D97706;}
.est-margin{font-size:0.74rem;color:#15803D;font-weight:700;margin-bottom:10px;}
.est-btns{display:flex;gap:8px;}
.est-btn{flex:1;padding:13px;border-radius:13px;font:inherit;font-weight:800;font-size:0.88rem;cursor:pointer;border:none;}
.est-btn.pri{background:linear-gradient(135deg,#F59E0B,#D97706);color:#fff;box-shadow:0 4px 14px rgba(217,119,6,0.35);}
.est-btn.sec{background:#fff;border:1px solid #F59E0B;color:#B45309;}
.est-btn:disabled{opacity:0.45;cursor:not-allowed;}
.est-btn-wide{display:block;width:100%;margin-bottom:8px;}
.est-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;}
.est-btn svg{width:17px;height:17px;flex-shrink:0;}
.est-btn.share{display:flex;color:#fff;background:linear-gradient(135deg,#2A7FFF 0%,#5B5BFF 50%,#8A3FFC 100%);box-shadow:0 4px 14px rgba(91,91,255,0.4);}
.est-btn.pdf{color:#fff;background:linear-gradient(180deg,#F0443A,#D93025);box-shadow:0 3px 10px rgba(217,48,37,0.35);}
.est-btn.xlsx{color:#fff;background:linear-gradient(180deg,#21A366,#107C41);box-shadow:0 3px 10px rgba(16,124,65,0.35);}
@media(min-width:640px){
  .est-ov{align-items:center;}
  .est{max-width:760px;width:94%;max-height:92vh;border-radius:22px;}
  .est-ft{border-radius:0 0 22px 22px;}
  .est-row2{grid-template-columns:1fr 1fr;}
  .est-hd{padding:20px 24px 14px;} .est-bd{padding:4px 24px 20px;} .est-ft{padding:14px 24px 18px;}
}
/* Баннер на главной */
.est-cta{display:flex;align-items:center;gap:12px;text-decoration:none;margin:10px 12px 0;padding:12px 16px;border-radius:14px;cursor:pointer;width:calc(100% - 24px);box-sizing:border-box;text-align:left;font:inherit;color:var(--text,#1A1C22);
  background:linear-gradient(135deg,rgba(42,127,255,0.20),rgba(124,77,255,0.16));border:1.5px solid rgba(98,90,255,0.6);
  box-shadow:0 4px 16px rgba(98,90,255,0.18), inset 0 1px 0 rgba(255,255,255,0.7);}
.est-cta-ic{font-size:1.5rem;line-height:1;}
.est-cta-tx{display:flex;flex-direction:column;flex:1;min-width:0;}
.est-cta-tx b{font-size:0.86rem;font-weight:700;}
.est-cta-tx small{font-size:0.7rem;color:var(--text2,#5A5F6E);}
.est-cta-go{flex-shrink:0;font-size:0.8rem;font-weight:800;color:#fff;padding:9px 15px;border-radius:12px;border:1px solid rgba(255,255,255,0.45);background:linear-gradient(135deg,#2A7FFF 0%,#5B5BFF 50%,#8A3FFC 100%);text-shadow:0 1px 1px rgba(30,20,120,0.35);box-shadow:inset 0 1px 0 rgba(255,255,255,0.55),inset 0 -2px 5px rgba(40,20,140,0.35),0 4px 12px rgba(91,91,255,0.5);transition:transform .12s;}
.est-cta:hover .est-cta-go{transform:translateY(-1px);}
@media(max-width:639px){.est-dsk{display:none;}}
@media(min-width:640px){.est-cta{margin:10px auto 0;max-width:960px;width:100%;}.est-cta-tx b{font-size:0.95rem;}.est-cta-tx small{font-size:0.78rem;}}
/* Та же плашка в шторке заявки — на всю ширину, без внешних отступов */
.est-cta.est-cta-dr{width:100%;max-width:none;margin:0 0 10px;padding:10px 12px;gap:10px;}
.est-cta-dr .est-cta-ic{font-size:1.3rem;}
.est-cta-dr .est-cta-tx b{font-size:0.88rem;}
.est-cta-dr .est-cta-tx small{font-size:0.72rem;}
.est-cta-dr .est-cta-go{padding:8px 12px;font-size:0.78rem;}
`;
  const st = document.createElement('style');
  st.id = 'estCss';
  st.textContent = css;
  document.head.appendChild(st);
}

/* ── Модалка ── */
function openEstimate() {
  _estInjectCss();
  _estLoad();
  if (typeof closeD === 'function' && document.getElementById('dr') && document.getElementById('dr').classList.contains('on')) {
    // из заявки: закрываем шторку без history.back(), иначе popstate закроет и смету
    document.getElementById('ov').classList.remove('on');
    document.getElementById('dr').classList.remove('on');
    if (typeof _navStack !== 'undefined' && _navStack.length && _navStack[_navStack.length - 1].name === 'cart') _navStack.pop();
  }
  // Пустая смета + товары в заявке → сразу подставляем их
  if (!_est.items.length && typeof cart !== 'undefined' && cart.length) _estTakeCart();
  if (document.getElementById('estOv')) return;

  const s = _est.settings;
  document.body.insertAdjacentHTML('beforeend', `
<div class="est-ov" id="estOv" onclick="if(event.target===this)closeEstimate()">
  <div class="est" role="dialog" aria-modal="true" aria-label="Смета для клиента">
    <div class="est-hd"><h2>📄 Смета для клиента</h2><button class="est-x" onclick="closeEstimate()" aria-label="Закрыть">✕</button></div>
    <div class="est-bd" id="estBody">
      <p class="est-hint">Цены оборудования для клиента — ваша оптовая цена плюс наценка. Оптовые цены в смете не показываются.</p>

      <div class="est-sec">Клиент</div>
      <div class="est-row2">
        <input class="est-in" id="estClient" placeholder="Имя клиента" value="${_estEsc(_est.clientName)}" oninput="_est.clientName=this.value;_estSchedulePdf()">
        <input class="est-in" id="estAddr" placeholder="Адрес объекта" value="${_estEsc(_est.objectAddress)}" oninput="_est.objectAddress=this.value;_estSchedulePdf()">
      </div>

      <div class="est-sec">Оборудование <small id="estEqCount"></small></div>
      <div class="est-search">
        <input class="est-in" id="estQ" placeholder="🔍 Найти технику: модель, бренд, BTU…" autocomplete="off"
          oninput="_estSuggest(this.value)" onkeydown="if(event.key==='Escape'&&this.value){event.stopPropagation();this.value='';_estSuggest('');}">
        <div class="est-sug" id="estSug" hidden></div>
      </div>
      <div id="estCartBtn"></div>
      <div id="estEq"></div>

      <div class="est-sec">Наценка на оборудование</div>
      <div class="est-chips" id="estChips"></div>

      <div class="est-sec">Работы <small>отметьте количество — в смету попадут строки больше нуля</small></div>
      <div id="estWorks"></div>
      <button class="est-add" onclick="_estAddWork()">+ Добавить работу</button>

      <div class="est-sec">Исполнитель <small>в шапке сметы</small></div>
      <div class="est-row2">
        <input class="est-in" placeholder="Ваше имя или компания" value="${_estEsc(s.contractorName)}"
          oninput="_est.settings.contractorName=this.value;_estSaveSettings();_estSchedulePdf()">
        <input class="est-in" type="tel" placeholder="Телефон" value="${_estEsc(s.contractorPhone)}"
          oninput="_est.settings.contractorPhone=this.value;_estSaveSettings();_estSchedulePdf()">
      </div>
    </div>
    <div class="est-ft" id="estFoot"></div>
  </div>
</div>`);
  document.body.style.overflow = 'hidden';
  _estRenderAll();
  if (typeof navOpen === 'function') navOpen('estimate', closeEstimate);
}

function closeEstimate(_fromPop) {
  if (!_fromPop && typeof navClose === 'function' && navClose('estimate')) return;
  const ov = document.getElementById('estOv');
  if (ov) ov.remove();
  document.body.style.overflow = '';
}

function _estRenderAll() { _estRenderEquipment(); _estRenderChips(); _estRenderWorks(); _estRenderFoot(); }

function _estTakeCart() {
  cart.forEach(c => {
    if (!_estProduct(c.id)) return;
    const ex = _est.items.find(it => it.id === c.id);
    if (ex) ex.qty = Math.max(ex.qty, c.qty); else _est.items.push({ id: c.id, qty: c.qty });
  });
  _estSaveItems();
}

function _estRenderEquipment() {
  const box = document.getElementById('estEq'); if (!box) return;
  const est = estCompute();
  document.getElementById('estEqCount').textContent = est.equipment.length ? '(' + est.equipment.length + ')' : '';

  const cartBox = document.getElementById('estCartBtn');
  const notInEst = (typeof cart !== 'undefined' ? cart : []).filter(c => _estProduct(c.id) && !_est.items.some(it => it.id === c.id));
  cartBox.innerHTML = notInEst.length
    ? `<button class="est-from-cart" onclick="_estTakeCart();_estRenderEquipment();_estRenderFoot()">🛒 Добавить из заявки (${notInEst.length} поз.)</button>`
    : '';

  box.innerHTML = est.equipment.length ? est.equipment.map(l => `
    <div class="est-line">
      <div class="est-line-tx">
        <div class="est-line-n">${_estEsc(l.name)}</div>
        <div class="est-line-m">${l.qty} × ${_estMoney(l.unitPrice)}</div>
      </div>
      <div class="est-line-t">${_estMoney(l.total)}</div>
      <div class="est-step">
        <button onclick="_estQty('${l.id}',-1)" aria-label="Меньше">−</button><b>${l.qty}</b><button class="plus" onclick="_estQty('${l.id}',1)" aria-label="Больше">+</button>
      </div>
      <button class="est-del" onclick="_estQty('${l.id}',-9999)" title="Убрать">✕</button>
    </div>`).join('')
    : '<div class="est-empty">Найдите технику через поиск выше или добавьте товары в заявку из каталога.</div>';
}

function _estQty(id, d) {
  const i = _est.items.findIndex(it => it.id === id); if (i < 0) return;
  _est.items[i].qty += d;
  if (_est.items[i].qty <= 0) _est.items.splice(i, 1);
  _estSaveItems(); _estRenderEquipment(); _estRenderFoot();
}

function _estSuggest(q) {
  const sug = document.getElementById('estSug'); if (!sug) return;
  const words = String(q).toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) { sug.hidden = true; sug.innerHTML = ''; return; }
  const found = PRODUCTS.filter(p => {
    if (typeof productVisible === 'function' && !productVisible(p)) return false;
    if (!(p.price > 0)) return false;
    const hay = [p.brand, p.series, p.model, p.descShort, p.btu ? p.btu + ' btu' : ''].join(' ').toLowerCase();
    return words.every(w => hay.includes(w));
  }).slice(0, 12);
  sug.innerHTML = found.length ? found.map(p => `
    <button onclick="_estAdd('${p.id}')"><span style="flex:1;min-width:0;color:inherit;font-size:inherit"><b>${_estEsc(_estName(p))}</b><span>${_estEsc(p.series || p.descShort || '')}</span></span><em>${_estMoney(p.price)}</em></button>`).join('')
    : '<div class="est-empty" style="padding:12px">Ничего не нашлось</div>';
  sug.hidden = false;
}

function _estAdd(id) {
  const ex = _est.items.find(it => it.id === id);
  if (ex) ex.qty++; else _est.items.push({ id, qty: 1 });
  _estSaveItems();
  const q = document.getElementById('estQ'); if (q) { q.value = ''; q.focus(); }
  _estSuggest(''); _estRenderEquipment(); _estRenderFoot();
}

function _estRenderChips() {
  const box = document.getElementById('estChips'); if (!box) return;
  const m = _est.settings.markupPercent;
  box.innerHTML = EST_MARKUPS.map(v =>
    `<button class="est-chip${m === v ? ' on' : ''}" onclick="_estMarkup(${v})">${v ? '+' + v + '%' : 'Без наценки'}</button>`).join('')
    + `<input class="est-chip est-chip-in${EST_MARKUPS.includes(m) ? '' : ' on'}" inputmode="numeric" maxlength="3" placeholder="свой %"
         value="${EST_MARKUPS.includes(m) ? '' : m}" oninput="_estMarkup(_estNum(this.value), true)">`;
}

function _estMarkup(v, fromInput) {
  _est.settings.markupPercent = v; _estSaveSettings();
  if (!fromInput) _estRenderChips();
  else document.querySelectorAll('#estChips .est-chip').forEach(b => { if (b.tagName === 'BUTTON') b.classList.remove('on'); });
  _estRenderEquipment(); _estRenderFoot();
}

function _estRenderWorks() {
  const box = document.getElementById('estWorks'); if (!box) return;
  box.innerHTML = _est.settings.works.map(w => `
    <div class="est-work${w.qty > 0 ? ' on' : ''}" id="estW-${w.id}">
      <input class="est-work-n" value="${_estEsc(w.name)}" oninput="_estWork('${w.id}',{name:this.value})" aria-label="Название работы">
      <div class="est-work-r">
        <input class="est-work-p" inputmode="numeric" value="${w.price}" oninput="_estWork('${w.id}',{price:_estNum(this.value)})" aria-label="Цена">
        <span class="est-work-u">₽${w.unit ? '/' + _estEsc(w.unit) : ''}</span>
        <div class="est-step">
          <button onclick="_estWorkQty('${w.id}',-1)" aria-label="Меньше">−</button><b>${w.qty}</b><button class="plus" onclick="_estWorkQty('${w.id}',1)" aria-label="Больше">+</button>
        </div>
        ${w.id.indexOf('custom-') === 0 ? `<button class="est-del" onclick="_estDelWork('${w.id}')" title="Удалить">✕</button>` : ''}
      </div>
    </div>`).join('');
}

function _estWork(id, patch) {
  const w = _est.settings.works.find(x => x.id === id); if (!w) return;
  Object.assign(w, patch); _estSaveSettings(); _estRenderFoot();
}
function _estWorkQty(id, d) {
  const w = _est.settings.works.find(x => x.id === id); if (!w) return;
  w.qty = Math.max(0, w.qty + d); _estSaveSettings(); _estRenderWorks(); _estRenderFoot();
}
function _estAddWork() {
  const id = 'custom-' + Date.now();
  _est.settings.works.push({ id, name: 'Своя работа', price: 0, qty: 1 });
  _estSaveSettings(); _estRenderWorks(); _estRenderFoot();
  const inp = document.querySelector('#estW-' + id + ' .est-work-n');
  if (inp) { inp.focus(); inp.select(); }
}
function _estDelWork(id) {
  _est.settings.works = _est.settings.works.filter(w => w.id !== id);
  _estSaveSettings(); _estRenderWorks(); _estRenderFoot();
}

function _estRenderFoot(prepare) {
  const box = document.getElementById('estFoot'); if (!box) return;
  if (prepare !== false) _estSchedulePdf();
  const e = estCompute();
  const off = _est.busy || !e.equipment.length ? ' disabled' : '';
  box.innerHTML = `
    <div class="est-tot"><span>Оборудование</span><b>${_estMoney(e.equipmentTotal)}</b></div>
    <div class="est-tot"><span>Работы</span><b>${_estMoney(e.worksTotal)}</b></div>
    <div class="est-grand"><span>Итого клиенту</span><b>${_estMoney(e.total)}</b></div>
    <div class="est-margin">Ваша наценка на оборудовании: ${_estMoney(e.margin)} (в смете не видна)</div>
    <button class="est-btn share est-btn-wide"${off} onclick="estimateShare()">${_est.busy === 'share' ? '⏳ Готовим PDF…' : '📤 Отправить клиенту PDF'}</button>
    <div class="est-btns">
      <button class="est-btn pdf"${off} onclick="estimateDownload('pdf')">${_est.busy === 'pdf' ? '⏳ PDF…' : EST_FILE_ICON + 'Скачать PDF'}</button>
      <button class="est-btn xlsx"${off} onclick="estimateDownload('xlsx')">${_est.busy === 'xlsx' ? '⏳ Excel…' : EST_FILE_ICON + 'Скачать Excel'}</button>
    </div>`;
}

/* ── PDF (pdfmake) — макет как в приложении ── */
function estimateFileName(d) {
  const pad = n => String(n).padStart(2, '0');
  return `smeta-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}.pdf`;
}

function _estDocDef(e, meta) {
  const INK = '#0F1729', MUTED = '#64748B', ACCENT = '#D97706', LINE = '#E0E5EF', HEAD = '#F2F4F8';
  const content = [
    { columns: [
      { text: 'СМЕТА', fontSize: 26, bold: true, width: 'auto' },
      { text: 'от ' + meta.date.toLocaleDateString('ru-RU'), fontSize: 12, color: MUTED, margin: [14, 12, 0, 0] },
    ] },
    { text: '', margin: [0, 0, 0, 10] },
  ];
  if (meta.contractorName) content.push({ text: [{ text: 'Исполнитель: ', bold: true }, { text: meta.contractorName, bold: true }], fontSize: 11, margin: [0, 0, 0, 4] });
  if (meta.contractorPhone) content.push({ text: 'Телефон: ' + meta.contractorPhone, fontSize: 11, margin: [0, 0, 0, 4] });
  if (meta.clientName) content.push({ text: 'Заказчик: ' + meta.clientName, fontSize: 11, margin: [0, 0, 0, 4] });
  if (meta.objectAddress) content.push({ text: 'Объект: ' + meta.objectAddress, fontSize: 11, margin: [0, 0, 0, 4] });

  const section = (title, lines, total) => {
    if (!lines.length) return;
    const hdr = ['№', 'Наименование', 'Кол-во', 'Цена', 'Сумма'].map((t, i) => ({
      text: t, bold: true, fontSize: 9, color: MUTED, fillColor: HEAD, alignment: i >= 3 ? 'right' : 'left', margin: [0, 3, 0, 3],
    }));
    const body = [hdr].concat(lines.map((l, i) => [
      { text: String(i + 1), color: MUTED },
      { text: l.name },
      { text: l.qty + (l.unit ? ' ' + l.unit : ''), noWrap: true },
      { text: _estMoney(l.unitPrice), alignment: 'right', noWrap: true },
      { text: _estMoney(l.total), alignment: 'right', bold: true, noWrap: true },
    ]));
    content.push(
      { text: title, fontSize: 13, bold: true, color: ACCENT, margin: [0, 16, 0, 6] },
      { table: { headerRows: 1, widths: [18, '*', 46, 70, 76], body },
        layout: { hLineWidth: (i) => (i === 0 ? 0 : 0.5), vLineWidth: () => 0, hLineColor: () => LINE,
                  paddingTop: () => 5, paddingBottom: () => 5, paddingLeft: () => 4, paddingRight: () => 4 },
        fontSize: 10 },
      { text: 'Итого: ' + _estMoney(total), bold: true, fontSize: 11, alignment: 'right', margin: [0, 6, 4, 0] },
    );
  };
  section('Оборудование и материалы', e.equipment, e.equipmentTotal);
  section('Работы', e.works, e.worksTotal);

  content.push(
    { table: { widths: ['*', 'auto'], body: [[
        { text: 'ИТОГО К ОПЛАТЕ', bold: true, fontSize: 13, margin: [8, 9, 0, 9] },
        { text: _estMoney(e.total), bold: true, fontSize: 16, color: ACCENT, margin: [0, 7, 8, 7] },
      ]] },
      layout: { fillColor: () => '#FFF7E6', hLineWidth: () => 0, vLineWidth: () => 0 }, margin: [0, 18, 0, 10], unbreakable: true },
    { text: `Смета действительна ${meta.validDays} дн. Цены на оборудование зафиксированы на дату составления.`, fontSize: 9, color: MUTED },
  );

  return {
    pageSize: 'A4', pageMargins: [40, 50, 40, 50],
    info: { title: 'Смета от ' + meta.date.toLocaleDateString('ru-RU') },
    defaultStyle: { font: 'Roboto', fontSize: 10, color: INK },
    content,
  };
}

/* ── Excel (ExcelJS) — те же строки, суммы формулами с готовым значением ── */
async function _estXlsxBlob(e, meta) {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('Смета', { pageSetup: { paperSize: 9, orientation: 'portrait', fitToPage: true, fitToWidth: 1, fitToHeight: 0 } });
  ws.columns = [{ width: 5 }, { width: 58 }, { width: 9 }, { width: 7 }, { width: 13 }, { width: 14 }];
  const money = '#,##0" ₽"';
  const accent = 'FFD97706';
  const thin = { style: 'thin', color: { argb: 'FFE0E5EF' } };

  ws.addRow(['СМЕТА от ' + meta.date.toLocaleDateString('ru-RU')]).font = { bold: true, size: 18 };
  ws.mergeCells(ws.rowCount, 1, ws.rowCount, 6);
  [['Исполнитель', meta.contractorName], ['Телефон', meta.contractorPhone], ['Заказчик', meta.clientName], ['Объект', meta.objectAddress]]
    .filter(r => r[1])
    .forEach(([k, v]) => { const r = ws.addRow(['', k + ': ' + v]); r.getCell(2).font = { bold: k === 'Исполнитель' }; });

  const totalRefs = [];
  const section = (title, lines) => {
    if (!lines.length) return;
    ws.addRow([]);
    const t = ws.addRow([title]); t.font = { bold: true, size: 13, color: { argb: accent } };
    const h = ws.addRow(['№', 'Наименование', 'Кол-во', 'Ед.', 'Цена', 'Сумма']);
    h.eachCell(c => { c.font = { bold: true, color: { argb: 'FF64748B' } }; c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF2F4F8' } }; c.border = { bottom: thin }; });
    const first = ws.rowCount + 1;
    lines.forEach((l, i) => {
      const n = ws.rowCount + 1;
      const r = ws.addRow([i + 1, l.name, l.qty, l.unit || 'шт', l.unitPrice, { formula: `C${n}*E${n}`, result: l.total }]);
      r.getCell(5).numFmt = money; r.getCell(6).numFmt = money; r.getCell(6).font = { bold: true };
      r.getCell(2).alignment = { wrapText: true, vertical: 'top' };
      r.eachCell(c => { c.border = { bottom: thin }; });
    });
    const last = ws.rowCount;
    const sum = lines.reduce((s, l) => s + l.total, 0);
    const tr = ws.addRow(['', '', '', '', 'Итого:', { formula: `SUM(F${first}:F${last})`, result: sum }]);
    tr.font = { bold: true }; tr.getCell(6).numFmt = money; tr.getCell(5).alignment = { horizontal: 'right' };
    totalRefs.push('F' + tr.number);
  };
  section('Оборудование и материалы', e.equipment);
  section('Работы', e.works);

  ws.addRow([]);
  const g = ws.addRow(['', 'ИТОГО К ОПЛАТЕ', '', '', '', { formula: totalRefs.join('+') || '0', result: e.total }]);
  g.eachCell({ includeEmpty: true }, c => { c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF7E6' } }; });
  g.font = { bold: true, size: 13 }; g.getCell(6).numFmt = money; g.getCell(6).font = { bold: true, size: 14, color: { argb: accent } };
  ws.addRow([]);
  ws.addRow(['', `Смета действительна ${meta.validDays} дн. Цены на оборудование зафиксированы на дату составления.`]).font = { size: 9, color: { argb: 'FF64748B' } };

  const buf = await wb.xlsx.writeBuffer();
  return new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

function _estMeta() {
  return {
    clientName: _est.clientName.trim(),
    objectAddress: _est.objectAddress.trim(),
    contractorName: (_est.settings.contractorName || '').trim(),
    contractorPhone: (_est.settings.contractorPhone || '').trim(),
    validDays: _est.settings.validDays || 7,
    date: new Date(),
  };
}

function _estPdfBlob(e, meta) {
  return new Promise((resolve, reject) => {
    try { pdfMake.createPdf(_estDocDef(e, meta)).getBlob(resolve); } catch (err) { reject(err); }
  });
}

// Готовит файлы сметы; kinds — ['pdf'], ['xlsx'] или оба.
async function _estBuildFiles(kinds) {
  if (kinds.includes('pdf') && typeof pdfMake === 'undefined') throw new Error('библиотека PDF ещё загружается, повторите через пару секунд');
  if (kinds.includes('xlsx') && typeof ExcelJS === 'undefined') throw new Error('библиотека Excel ещё загружается, повторите через пару секунд');
  const e = estCompute(), meta = _estMeta();
  const base = estimateFileName(meta.date).replace(/\.pdf$/, '');
  const out = { e, meta };
  if (kinds.includes('pdf'))  out.pdf  = new File([await _estPdfBlob(e, meta)], base + '.pdf', { type: 'application/pdf' });
  if (kinds.includes('xlsx')) out.xlsx = new File([await _estXlsxBlob(e, meta)], base + '.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  return out;
}

function _estSaveFile(file) {
  const url = URL.createObjectURL(file);
  const a = document.createElement('a');
  a.href = url; a.download = file.name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function estimateDownload(kind) {
  if (_est.busy || !_est.items.length) return;
  _est.busy = kind; _estRenderFoot();
  try {
    const files = await _estBuildFiles([kind]);
    _estSaveFile(files[kind]);
    showEstToast('Смета сохранена: ' + files[kind].name);
  } catch (err) {
    console.error('Estimate file error:', err);
    showEstToast('Не удалось подготовить смету: ' + (err && err.message || 'попробуйте ещё раз'), true);
  } finally {
    _est.busy = false; _estRenderFoot();
  }
}

/* ── Отправка клиенту: сразу файлом PDF через системное «Поделиться»
      (Telegram, WhatsApp, Max, почта — что установлено на телефоне).
      Браузер разрешает «Поделиться» только прямо из нажатия, поэтому PDF собирается
      заранее, пока монтажник заполняет смету, а кнопка отдаёт уже готовый файл. ── */
function _estKey() {
  const m = _estMeta();
  return JSON.stringify([estCompute(), m.clientName, m.objectAddress, m.contractorName, m.contractorPhone, m.validDays]);
}

function _estSchedulePdf() {
  clearTimeout(_est.pdfTimer);
  if (!_est.items.length || typeof pdfMake === 'undefined') return;
  _est.pdfTimer = setTimeout(_estPreparePdf, 400);
}

async function _estPreparePdf() {
  const key = _estKey();
  if (_est.pdf && _est.pdf.key === key) return _est.pdf.file;
  const files = await _estBuildFiles(['pdf']);
  _est.pdf = { key, file: files.pdf };
  return files.pdf;
}

function estimateShare() {
  if (_est.busy || !_est.items.length) return;
  const ready = _est.pdf && _est.pdf.key === _estKey() ? _est.pdf.file : null;
  const canShare = !!(navigator.share && navigator.canShare);
  if (ready && canShare && navigator.canShare({ files: [ready] })) {
    // никаких await до share — иначе браузер сочтёт вызов не от пользователя
    navigator.share({ files: [ready], title: ready.name }).catch(err => {
      if (err && err.name === 'AbortError') return; // закрыли меню
      console.error('Estimate share error:', err);
      showEstToast('Не получилось открыть «Поделиться» (' + (err && err.name || 'ошибка') + '). PDF можно скачать кнопкой ниже.', true);
    });
    return;
  }
  if (!canShare) {
    // компьютер или браузер без отправки файлов — сохраняем PDF, его можно прикрепить в мессенджере
    estimateDownload('pdf');
    return;
  }
  // PDF ещё собирается (первое нажатие сразу после правки) — дособираем и просим нажать ещё раз
  _est.busy = 'share'; _estRenderFoot(false);
  _estPreparePdf().then(
    () => showEstToast('PDF готов — нажмите «Отправить» ещё раз'),
    err => showEstToast('Не удалось подготовить смету: ' + (err && err.message || 'попробуйте ещё раз'), true),
  ).finally(() => { _est.busy = false; _estRenderFoot(false); });
}

// Стили нужны сразу: баннер на главной и кнопка в заявке видны до открытия сметы
_estInjectCss();

function showEstToast(msg, isError) {
  if (typeof showToast === 'function') showToast(_estEsc(msg), isError); else alert(msg);
}
