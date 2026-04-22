/**
 * pricelist.js — Генератор прайса СплитХаб
 * PDF: html2pdf.js on-page → blob → кнопка Сохранить
 * Excel: ExcelJS + батчевая загрузка фото → blob → кнопка Сохранить
 * Группировка: AC бренд→серия, Расходники→подгруппы
 */

const PRICE_SITE = 'https://splithub.ru';

/* ── Маппинг расходников → смысловые группы ── */
const RASHOD_GROUP_MAP = {
  'Фреон':      ['R134a','R22','R32','R410a'],
  'Дренаж':     ['OTMO','Ballu','Ruvinil','Дренаж гибкий'],
  'Лента':      ['AVIORA','K-Flex','(Скотч)Клейкая лента упаковочная 48мм*40мкм 100м ALG'],
  'Кабель':     ['АРСЕНАЛ'],
  'Крепёж':     ['Болт 8-25','Болт 8-30','Болт 8-35','Гайка М8','Гайка М8-пресшайба',
                 'Глухарь','Дюбель','Дюбель 6х40','шайба м8','шайба м8 увеличенная'],
  'Кронштейны': ['Кронштейны'],
  'Изоляция':   ['ТермаЭКО'],
};

const _RASHOD_BRAND_GRP = {};
for (const [grp, brands] of Object.entries(RASHOD_GROUP_MAP)) {
  for (const b of brands) _RASHOD_BRAND_GRP[b] = grp;
}

/* ── Группировка товаров ── */
function _groupProducts() {
  const ac     = {};
  const rashod = {};
  const truba  = [];

  PRODUCTS.forEach(p => {
    if (p.group === 'truba') {
      truba.push(p);
    } else if (p.group === 'rashod') {
      const grp = _RASHOD_BRAND_GRP[p.brand] || 'Прочее';
      if (!rashod[grp]) rashod[grp] = [];
      rashod[grp].push(p);
    } else {
      const brand  = p.brand  || 'Без бренда';
      const series = p.series || 'Без серии';
      if (!ac[brand])         ac[brand] = {};
      if (!ac[brand][series]) ac[brand][series] = [];
      ac[brand][series].push(p);
    }
  });

  return { ac, rashod, truba };
}

/* ── Модальное окно: выбор формата ── */
function openPricelistModal() {
  if (document.getElementById('priceModal')) return;
  document.body.insertAdjacentHTML('beforeend', `
<div id="priceModal" onclick="if(event.target===this)closePriceModal()"
  style="position:fixed;inset:0;background:rgba(10,14,26,0.55);backdrop-filter:blur(8px);
         display:flex;align-items:center;justify-content:center;z-index:9999;">
  <div style="background:rgba(255,255,255,0.97);border-radius:20px;padding:28px 24px;
              max-width:360px;width:90%;box-shadow:0 24px 64px rgba(0,0,0,0.25);">
    <div style="font-family:'Unbounded',sans-serif;font-size:1rem;font-weight:700;margin-bottom:6px;">
      📥 Загрузить прайс
    </div>
    <p style="font-size:0.8rem;color:#6b7280;margin-bottom:20px;">
      Выберите формат файла:
    </p>
    <button onclick="downloadPriceExcel()"
      style="width:100%;padding:14px;margin-bottom:10px;
             background:linear-gradient(135deg,#1D6F42,#2E9E5F);
             color:#fff;border:none;border-radius:12px;
             font-weight:700;cursor:pointer;font-size:0.88rem;
             box-shadow:0 4px 14px rgba(29,111,66,0.35);
             display:flex;align-items:center;justify-content:center;gap:8px;">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
      Скачать Excel (.xlsx)
    </button>
    <button onclick="downloadPricePDF()"
      style="width:100%;padding:14px;margin-bottom:18px;
             background:linear-gradient(135deg,#c0392b,#e74c3c);
             color:#fff;border:none;border-radius:12px;
             font-weight:700;cursor:pointer;font-size:0.88rem;
             box-shadow:0 4px 14px rgba(192,57,43,0.35);
             display:flex;align-items:center;justify-content:center;gap:8px;">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
      Скачать PDF
    </button>
    <button onclick="closePriceModal()"
      style="width:100%;padding:11px;background:#F3F4F6;color:#374151;
             border:none;border-radius:12px;cursor:pointer;font-size:0.84rem;">
      Отмена
    </button>
  </div>
</div>`);
}

function closePriceModal() {
  const m = document.getElementById('priceModal');
  if (m) m.remove();
}

/* ────────────────────────────────────────────────
   ПРОГРЕСС-МОДАЛ (общий для PDF и Excel)
   Возвращает объект { update, enableSave, remove }
─────────────────────────────────────────────────*/
function _showProgressModal(title) {
  const el = document.createElement('div');
  el.id = 'priceProgressModal';
  el.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(10,14,26,0.75);backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;';
  el.innerHTML = `
    <div style="background:#fff;border-radius:20px;padding:28px 24px;max-width:380px;width:92%;box-shadow:0 24px 64px rgba(0,0,0,0.3);">
      <div style="font-family:'Unbounded',sans-serif;font-size:0.95rem;font-weight:700;margin-bottom:16px;">${title}</div>
      <div style="background:#F3F4F6;border-radius:999px;height:8px;margin-bottom:10px;overflow:hidden;">
        <div id="pmBar" style="height:100%;width:0%;background:linear-gradient(90deg,#0d9488,#14B8A6);border-radius:999px;transition:width 0.5s ease;"></div>
      </div>
      <div id="pmStatus" style="font-size:0.78rem;color:#6b7280;margin-bottom:20px;min-height:1.3em;">Подготовка…</div>
      <button id="pmSave" disabled
        style="width:100%;padding:14px;margin-bottom:10px;background:linear-gradient(135deg,#0d9488,#14B8A6);
               color:#fff;border:none;border-radius:12px;font-weight:700;font-size:0.9rem;
               cursor:not-allowed;opacity:0.35;transition:opacity 0.3s;">
        💾 Сохранить файл
      </button>
      <button id="pmCancel"
        style="width:100%;padding:11px;background:#F3F4F6;color:#374151;border:none;border-radius:12px;cursor:pointer;font-size:0.84rem;">
        Отмена
      </button>
    </div>`;
  document.body.appendChild(el);

  document.getElementById('pmCancel').onclick = () => el.remove();

  const ui = {
    update(pct, text) {
      const bar    = document.getElementById('pmBar');
      const status = document.getElementById('pmStatus');
      if (bar)    bar.style.width = Math.min(pct, 100) + '%';
      if (status) status.textContent = text;
    },
    enableSave(blob, filename) {
      const btn = document.getElementById('pmSave');
      if (!btn) return;
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.style.cursor  = 'pointer';
      btn.onclick = () => {
        const url = URL.createObjectURL(blob);
        const a   = document.createElement('a');
        a.href = url; a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        el.remove();
      };
    },
    remove() { if (el.parentNode) el.remove(); },
  };
  return ui;
}

/* ────────────────────────────────────────────────
   УТИЛИТЫ ЗАГРУЗКИ ФОТО
─────────────────────────────────────────────────*/
function _withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), ms)),
  ]);
}

function _fetchViaImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = 80; canvas.height = 80;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, 80, 80);
        ctx.drawImage(img, 0, 0, 80, 80);
        resolve(canvas.toDataURL('image/jpeg', 0.85).split(',')[1]);
      } catch(e) { reject(e); }
    };
    img.onerror = () => reject(new Error('img error'));
    img.src = url;
  });
}

async function _fetchViaBlob(url) {
  const resp = await fetch(url, { credentials: 'same-origin' });
  if (!resp.ok) throw new Error('fetch ' + resp.status);
  const blob   = await resp.blob();
  const objUrl = URL.createObjectURL(blob);
  try   { return await _fetchViaImage(objUrl); }
  finally { URL.revokeObjectURL(objUrl); }
}

async function _fetchAsJpegSafe(url) {
  try   { return await _withTimeout(_fetchViaImage(url), 10000); }
  catch {
    try   { return await _withTimeout(_fetchViaBlob(url), 10000); }
    catch { return null; }
  }
}

/* ────────────────────────────────────────────────
   PDF — on-page html2pdf → blob → кнопка Сохранить
─────────────────────────────────────────────────*/
async function downloadPricePDF() {
  closePriceModal();

  if (typeof html2pdf === 'undefined') {
    alert('Библиотека PDF ещё загружается. Подождите 5 секунд и повторите.');
    return;
  }

  const date  = new Date().toLocaleDateString('ru-RU');
  const fname = 'splithub-price-' + date.replace(/\./g, '-') + '.pdf';
  const ui    = _showProgressModal('📄 Генерируем PDF…');

  // Контейнер позади модала — html2canvas его рендерит по DOM-ссылке
  const container = document.createElement('div');
  container.style.cssText = 'position:absolute;left:0;top:0;width:900px;background:#fff;z-index:-9999;';
  container.innerHTML = _buildPriceContent(date);
  document.body.appendChild(container);
  // Ждём, пока браузер разложит контент (без этого высота = 0 → пустой PDF)
  await new Promise(r => setTimeout(r, 300));

  const priceWrap = container.querySelector('.price-wrap') || container;

  // Псевдо-прогресс пока html2pdf работает (реальный прогресс недоступен)
  ui.update(5, 'Рендерим страницы… это займёт 30–60 сек');
  let pct = 5;
  const ticker = setInterval(() => {
    if (pct < 82) { pct += 1.5; ui.update(pct, 'Рендерим страницы… ' + Math.round(pct) + '%'); }
  }, 1000);

  try {
    const blob = await html2pdf()
      .from(priceWrap)
      .set({
        margin:      [8, 8, 8, 8],
        image:       { type: 'jpeg', quality: 0.82 },
        html2canvas: { scale: 1.2, useCORS: true, logging: false, imageTimeout: 15000 },
        jsPDF:       { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak:   { mode: ['css'], before: '.pb-before' },
      })
      .outputPdf('blob');

    clearInterval(ticker);
    ui.update(100, '✅ Готово! Нажмите «Сохранить файл»');
    ui.enableSave(blob, fname);
  } catch(e) {
    clearInterval(ticker);
    ui.update(0, '❌ Ошибка: ' + e.message);
    console.error('PDF error:', e);
  } finally {
    container.remove();
  }
}

/* ── HTML-контент прайса (для PDF) ── */
function _buildPriceContent(date) {
  const { ac, rashod, truba } = _groupProducts();
  let rowNum = 1;
  let body   = '';

  const styles = `<style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:Arial,sans-serif;background:#fff;font-size:12px;color:#111}
    .hdr{text-align:center;margin-bottom:24px}
    .hdr h1{font-size:20px;margin-bottom:4px}
    .hdr p{color:#888;font-size:12px}
    .brand-group{margin-bottom:28px}
    .brand-title{background:#F59E0B;color:#fff;font-weight:700;font-size:13px;padding:9px 14px;border-radius:6px;margin-bottom:4px}
    .brand-title.truba{background:#b45309}
    .brand-title.rashod{background:#0d9488}
    .series-title{background:#f5f5f5;border-left:3px solid #F59E0B;padding:5px 12px;margin-bottom:6px;font-size:11px;color:#555}
    .series-title.rashod{border-left-color:#0d9488}
    table{width:100%;border-collapse:collapse;margin-bottom:14px;table-layout:fixed}
    col.c-num{width:26px} col.c-id{width:54px} col.c-model{width:195px} col.c-desc{width:138px}
    col.c-price{width:72px} col.c-photo{width:56px} col.c-stock{width:80px}
    th{background:#f0f0f0;padding:7px 5px;text-align:left;font-size:10px;border-bottom:2px solid #ddd;overflow:hidden}
    td{padding:7px 5px;border-bottom:1px solid #eee;vertical-align:middle;overflow:hidden;word-break:break-word}
    .c-num{text-align:center} .c-id{font-family:monospace;font-size:10px;color:#888}
    .c-desc{font-size:10px;color:#666}
    .c-price{text-align:right;font-weight:700;color:#D97706;white-space:nowrap}
    .c-photo{text-align:center} .c-photo img{width:48px;height:48px;object-fit:contain;display:block;margin:0 auto}
    .s-ok{color:#10B981;font-weight:700} .s-warn{color:#F59E0B;font-weight:700} .s-no{color:#EF4444;font-weight:700}
    .pb-before{page-break-before:always}
  </style>`;

  function buildTable(items) {
    let t = `<table><colgroup>
      <col class="c-num"><col class="c-id"><col class="c-model">
      <col class="c-desc"><col class="c-price"><col class="c-photo"><col class="c-stock">
    </colgroup><thead><tr>
      <th class="c-num">№</th><th class="c-id">ID</th>
      <th>Модель</th><th class="c-desc">Описание</th>
      <th class="c-price">Цена</th><th class="c-photo">Фото</th><th>Наличие</th>
    </tr></thead><tbody>`;

    items.forEach(p => {
      const fmt   = new Intl.NumberFormat('ru-RU').format(p.price);
      const sc    = p.stock === 'in_stock' ? 'ok' : (p.stock || '').startsWith('days') ? 'warn' : 'no';
      const photo = p.photo
        ? `<img src="${PRICE_SITE}/assets/img/products/${p.photo}" />`
        : '—';
      t += `<tr>
        <td class="c-num">${rowNum}</td><td class="c-id">${p.id}</td>
        <td>${p.model || ''}</td><td class="c-desc">${p.descShort || ''}</td>
        <td class="c-price">${fmt}&nbsp;₽</td>
        <td class="c-photo">${photo}</td>
        <td class="s-${sc}">${p.stockLabel || ''}</td>
      </tr>`;
      rowNum++;
    });
    return t + `</tbody></table>`;
  }

  let first = true;
  Object.keys(ac).sort().forEach(brand => {
    const cls = first ? 'brand-group' : 'brand-group pb-before';
    first = false;
    body += `<div class="${cls}"><div class="brand-title">${brand}</div>`;
    Object.keys(ac[brand]).sort().forEach(series => {
      const items = ac[brand][series];
      if (!items.length) return;
      const info = (items[0].benefits || []).slice(0, 3).join(' · ');
      body += `<div class="series-title"><strong>${series}</strong>${info ? ' — ' + info : ''}</div>`;
      body += buildTable(items);
    });
    body += `</div>`;
  });

  if (truba.length) {
    body += `<div class="brand-group pb-before"><div class="brand-title truba">Медная труба</div>`;
    body += buildTable(truba);
    body += `</div>`;
  }

  const grpOrder = ['Фреон','Дренаж','Лента','Кабель','Крепёж','Кронштейны','Изоляция','Прочее'];
  if (grpOrder.some(g => rashod[g] && rashod[g].length)) {
    body += `<div class="brand-group pb-before"><div class="brand-title rashod">Расходники</div>`;
    grpOrder.forEach(grpName => {
      const items = rashod[grpName];
      if (!items || !items.length) return;
      body += `<div class="series-title rashod"><strong>${grpName}</strong></div>`;
      body += buildTable(items);
    });
    body += `</div>`;
  }

  return `${styles}<div class="price-wrap">
<div class="hdr">
  <h1>Прайс-лист СплитХаб</h1>
  <p>Оптовые кондиционеры для монтажников и B2B · Симферополь</p>
  <p style="margin-top:5px;color:#bbb">Дата: ${date} · Товаров: ${PRODUCTS.length}</p>
</div>
${body}</div>`;
}

/* ────────────────────────────────────────────────
   EXCEL — батчи фото + ExcelJS → blob → Сохранить
─────────────────────────────────────────────────*/
async function downloadPriceExcel() {
  if (typeof ExcelJS === 'undefined') {
    alert('Библиотека Excel ещё загружается. Подождите 5 секунд и повторите.');
    return;
  }
  closePriceModal();

  const ui = _showProgressModal('📊 Генерируем Excel…');

  try {
    /* ── Шаг 1: загрузка фото батчами по 5 ── */
    const uniquePhotos = [...new Set(PRODUCTS.filter(p => p.photo).map(p => p.photo))];
    const photos = {};
    const total  = uniquePhotos.length;
    let   loaded = 0;

    for (let i = 0; i < uniquePhotos.length; i += 5) {
      const batch = uniquePhotos.slice(i, i + 5);
      await Promise.allSettled(batch.map(async fname => {
        const result = await _fetchAsJpegSafe(`${PRICE_SITE}/assets/img/products/${fname}`);
        if (result) photos[fname] = result;
        loaded++;
        ui.update(Math.round((loaded / total) * 50), `Фото ${loaded} из ${total}…`);
      }));
    }

    /* ── Шаг 2: строим workbook ── */
    ui.update(52, 'Строим таблицы…');

    const date = new Date().toLocaleDateString('ru-RU');
    const wb   = new ExcelJS.Workbook();
    wb.creator  = 'СплитХаб';
    wb.created  = new Date();
    const ws    = wb.addWorksheet('Прайс');

    ws.columns = [
      { key:'num',   width:5  },
      { key:'id',    width:9  },
      { key:'model', width:42 },
      { key:'desc',  width:30 },
      { key:'price', width:14 },
      { key:'photo', width:11 },
      { key:'stock', width:18 },
    ];

    /* Шапка книги */
    ws.mergeCells('A1:G1');
    Object.assign(ws.getCell('A1'), {
      value:     'Прайс-лист СплитХаб',
      font:      { name:'Arial', size:16, bold:true },
      alignment: { horizontal:'center', vertical:'middle' },
    });
    ws.getRow(1).height = 30;

    ws.mergeCells('A2:G2');
    Object.assign(ws.getCell('A2'), {
      value:     `Оптовые кондиционеры · Симферополь · ${date} · Товаров: ${PRODUCTS.length}`,
      font:      { name:'Arial', size:10, color:{argb:'FF888888'} },
      alignment: { horizontal:'center', vertical:'middle' },
    });
    ws.getRow(2).height = 18;
    ws.addRow([]);

    /* Константы цветов */
    const C_AMBER   = 'FFF59E0B';
    const C_WHITE   = 'FFFFFFFF';
    const C_GRAY_BG = 'FFF5F5F5';
    const C_HDR_BG  = 'FFE0E0E0';
    const C_PRICE   = 'FFD97706';
    const C_OK      = 'FF10B981';
    const C_WARN    = 'FFF59E0B';
    const C_NO      = 'FFEF4444';
    const C_ALT     = 'FFFAFAFA';

    const bThin   = () => { const s={style:'thin',color:{argb:'FFDDDDDD'}}; return {top:s,left:s,bottom:s,right:s}; };
    const bMedium = () => { const s={style:'medium',color:{argb:'FF999999'}}; return {top:s,left:s,bottom:s,right:s}; };

    function addBrandRow(label) {
      ws.addRow([]);
      const r = ws.addRow([label,'','','','','','']);
      ws.mergeCells(`A${r.number}:G${r.number}`);
      const c = ws.getCell(`A${r.number}`);
      c.font      = { name:'Arial', size:13, bold:true, color:{argb:C_WHITE} };
      c.fill      = { type:'pattern', pattern:'solid', fgColor:{argb:C_AMBER} };
      c.alignment = { vertical:'middle', horizontal:'left', indent:1 };
      c.border    = bMedium();
      r.height    = 24;
    }

    function addSeriesRow(label) {
      const r = ws.addRow(['', label,'','','','','']);
      ws.mergeCells(`B${r.number}:G${r.number}`);
      const c = ws.getCell(`B${r.number}`);
      c.font      = { name:'Arial', size:11, bold:true, color:{argb:'FF444444'} };
      c.fill      = { type:'pattern', pattern:'solid', fgColor:{argb:C_GRAY_BG} };
      c.alignment = { vertical:'middle', horizontal:'left', indent:1 };
      r.height    = 18;
    }

    function addTableHeader() {
      const r = ws.addRow(['№','ID','Модель','Описание','Цена, ₽','Фото','Наличие']);
      r.height = 18;
      r.eachCell(cell => {
        cell.font      = { name:'Arial', size:10, bold:true };
        cell.fill      = { type:'pattern', pattern:'solid', fgColor:{argb:C_HDR_BG} };
        cell.border    = bThin();
        cell.alignment = { horizontal:'center', vertical:'middle' };
      });
      ws.getCell(`E${r.number}`).alignment = { horizontal:'right', vertical:'middle' };
    }

    function addItemRow(p, num, isAlt) {
      const sc      = p.stock === 'in_stock' ? 'ok' : (p.stock||'').startsWith('days') ? 'warn' : 'no';
      const scColor = sc==='ok' ? C_OK : sc==='warn' ? C_WARN : C_NO;
      const bg      = isAlt ? C_ALT : C_WHITE;

      const r = ws.addRow([num, p.id, p.model||'', p.descShort||'', p.price, '', p.stockLabel||'']);
      r.height = 55;

      r.eachCell(cell => {
        cell.fill      = { type:'pattern', pattern:'solid', fgColor:{argb:bg} };
        cell.border    = bThin();
        cell.font      = { name:'Arial', size:10 };
        cell.alignment = { vertical:'middle', wrapText:false };
      });

      ws.getCell(`A${r.number}`).alignment = { horizontal:'center', vertical:'middle' };
      ws.getCell(`B${r.number}`).font      = { name:'Courier New', size:9, color:{argb:'FF888888'} };

      const pc = ws.getCell(`E${r.number}`);
      pc.value     = p.price;
      pc.numFmt    = '#,##0" ₽"';
      pc.font      = { name:'Arial', size:10, bold:true, color:{argb:C_PRICE} };
      pc.alignment = { horizontal:'right', vertical:'middle' };

      if (p.photo && photos[p.photo]) {
        const imgId = wb.addImage({ base64: photos[p.photo], extension: 'jpeg' });
        ws.addImage(imgId, {
          tl:     { col: 5, row: r.number - 1 },
          ext:    { width: 60, height: 60 },
          editAs: 'oneCell',
        });
      }

      ws.getCell(`G${r.number}`).font = { name:'Arial', size:10, bold:true, color:{argb:scColor} };
    }

    let rowNum = 1;
    const { ac, rashod, truba } = _groupProducts();

    Object.keys(ac).sort().forEach(brand => {
      addBrandRow(brand);
      addTableHeader();
      Object.keys(ac[brand]).sort().forEach(series => {
        const items = ac[brand][series];
        if (!items.length) return;
        addSeriesRow(series);
        items.forEach((p, i) => addItemRow(p, rowNum++, i%2===1));
      });
    });

    if (truba.length) {
      addBrandRow('Медная труба');
      addTableHeader();
      truba.forEach((p, i) => addItemRow(p, rowNum++, i%2===1));
    }

    const grpOrder = ['Фреон','Дренаж','Лента','Кабель','Крепёж','Кронштейны','Изоляция','Прочее'];
    if (grpOrder.some(g => rashod[g] && rashod[g].length)) {
      addBrandRow('Расходники');
      grpOrder.forEach(grpName => {
        const items = rashod[grpName];
        if (!items || !items.length) return;
        addSeriesRow(grpName);
        addTableHeader();
        items.forEach((p, i) => addItemRow(p, rowNum++, i%2===1));
      });
    }

    ws.views = [{ state:'frozen', ySplit:3, activeCell:'A4' }];

    /* ── Шаг 3: финализация ── */
    ui.update(88, 'Финализируем…');
    const buf  = await wb.xlsx.writeBuffer();
    const blob = new Blob([buf], { type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });

    ui.update(100, `✅ Готово! Загружено фото: ${Object.keys(photos).length} из ${total}. Нажмите «Сохранить файл»`);
    ui.enableSave(blob, `splithub-price-${date.replace(/\./g,'-')}.xlsx`);

  } catch(err) {
    console.error('Excel error:', err);
    ui.update(0, '❌ Ошибка: ' + err.message);
  }
}
