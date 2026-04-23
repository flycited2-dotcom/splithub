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
   PDF — pdfmake (векторный) → blob → кнопка Сохранить
─────────────────────────────────────────────────*/
async function downloadPricePDF() {
  closePriceModal();

  if (typeof pdfMake === 'undefined') {
    alert('Библиотека PDF ещё загружается. Подождите 5 секунд и повторите.');
    return;
  }

  const date  = new Date().toLocaleDateString('ru-RU');
  const fname = 'splithub-price-' + date.replace(/\./g, '-') + '.pdf';
  const ui    = _showProgressModal('📄 Генерируем PDF…');

  try {
    /* Шаг 1: загрузка фото батчами по 5 (та же логика, что в Excel) */
    const uniquePhotos = [...new Set(PRODUCTS.filter(p => p.photo).map(p => p.photo))];
    const photos = {};
    const total  = uniquePhotos.length;
    let   loaded = 0;

    for (let i = 0; i < uniquePhotos.length; i += 5) {
      const batch = uniquePhotos.slice(i, i + 5);
      await Promise.allSettled(batch.map(async ph => {
        const b64 = await _fetchAsJpegSafe(`${PRICE_SITE}/assets/img/products/${ph}`);
        if (b64) photos[ph] = b64;
        loaded++;
        ui.update(Math.round((loaded / total) * 55), `Фото ${loaded} из ${total}…`);
      }));
    }

    /* Шаг 2: строим docDefinition */
    ui.update(60, 'Строим документ…');
    const docDef = _buildPdfDocDef(date, photos);

    /* Шаг 3: генерируем blob через pdfmake (векторный рендер) */
    ui.update(65, 'Генерируем PDF… это займёт 10–30 сек');
    const blob = await new Promise((resolve, reject) => {
      try { pdfMake.createPdf(docDef).getBlob(resolve); }
      catch(e) { reject(e); }
    });

    ui.update(100, `✅ Готово! Фото: ${Object.keys(photos).length}/${total}. Нажмите «Сохранить файл»`);
    ui.enableSave(blob, fname);

  } catch(e) {
    ui.update(0, '❌ Ошибка: ' + e.message);
    console.error('PDF error:', e);
  }
}

/* ── pdfmake docDefinition для прайса ── */
function _buildPdfDocDef(date, photos) {
  const { ac, rashod, truba } = _groupProducts();

  const C_AMBER = '#F59E0B';
  const C_WHITE = '#FFFFFF';
  const C_GRAY  = '#F5F5F5';
  const C_HDR   = '#E0E0E0';
  const C_PRICE = '#D97706';
  const C_OK    = '#10B981';
  const C_WARN  = '#F59E0B';
  const C_NO    = '#EF4444';
  const C_ALT   = '#FAFAFA';

  /* Ширины колонок A4: [№, ID, Модель, Описание, Цена, Фото, Наличие] */
  const WIDTHS = [18, 40, '*', 88, 50, 50, 62];

  /* Регистр изображений — канонический способ pdfmake (надёжнее inline data URI) */
  const images = {};
  for (const [fname, b64] of Object.entries(photos)) {
    images[fname] = 'data:image/jpeg;base64,' + b64;
  }

  const body = [];
  let rowNum = 1;

  /* Шапка колонок (повторяется на каждой странице через headerRows:1) */
  body.push(
    ['№', 'ID', 'Модель', 'Описание', 'Цена, ₽', 'Фото', 'Наличие'].map((t, i) => ({
      text: t, bold: true, fontSize: 8, fillColor: C_HDR,
      alignment: i === 4 ? 'right' : (i === 0 || i === 5) ? 'center' : 'left',
      margin: [3, 5, 3, 5],
    }))
  );

  function addBrand(label) {
    body.push([
      { text: label, colSpan: 7, bold: true, fontSize: 11, color: C_WHITE, fillColor: C_AMBER, margin: [6, 7, 6, 7] },
      {}, {}, {}, {}, {}, {},
    ]);
  }

  function addSeries(label) {
    body.push([
      {},
      { text: label, colSpan: 6, bold: true, fontSize: 9, color: '#444444', fillColor: C_GRAY, margin: [6, 5, 6, 5] },
      {}, {}, {}, {}, {},
    ]);
  }

  function addProduct(p, alt) {
    const bg  = alt ? C_ALT : C_WHITE;
    const sc  = p.stock === 'in_stock' ? C_OK : (p.stock || '').startsWith('days') ? C_WARN : C_NO;
    const fmt = new Intl.NumberFormat('ru-RU').format(p.price) + ' ₽';
    const base = { fillColor: bg, margin: [3, 3, 3, 3] };
    body.push([
      { ...base, text: String(rowNum++), alignment: 'center', fontSize: 8 },
      { ...base, text: p.id || '', fontSize: 7, color: '#888888' },
      { ...base, text: p.model || '', fontSize: 9 },
      { ...base, text: p.descShort || '', fontSize: 8, color: '#555555' },
      { ...base, text: fmt, alignment: 'right', bold: true, color: C_PRICE, fontSize: 9 },
      photos[p.photo]
        ? { ...base, image: p.photo, width: 44, height: 44, alignment: 'center' }
        : { ...base, text: '—', alignment: 'center', color: '#CCCCCC' },
      { ...base, text: p.stockLabel || '', bold: true, color: sc, fontSize: 8 },
    ]);
  }

  /* AC бренды */
  Object.keys(ac).sort().forEach(brand => {
    addBrand(brand);
    Object.keys(ac[brand]).sort().forEach(series => {
      const items = ac[brand][series];
      if (!items.length) return;
      addSeries(series);
      items.forEach((p, i) => addProduct(p, i % 2 === 1));
    });
  });

  /* Медная труба */
  if (truba.length) {
    addBrand('Медная труба');
    truba.forEach((p, i) => addProduct(p, i % 2 === 1));
  }

  /* Расходники */
  const grpOrder = ['Фреон', 'Дренаж', 'Лента', 'Кабель', 'Крепёж', 'Кронштейны', 'Изоляция', 'Прочее'];
  if (grpOrder.some(g => rashod[g] && rashod[g].length)) {
    addBrand('Расходники');
    grpOrder.forEach(grp => {
      const items = rashod[grp];
      if (!items || !items.length) return;
      addSeries(grp);
      items.forEach((p, i) => addProduct(p, i % 2 === 1));
    });
  }

  return {
    pageSize: 'A4',
    pageMargins: [28, 28, 18, 24],
    defaultStyle: { font: 'Roboto', fontSize: 9 },
    images,
    content: [
      { text: 'Прайс-лист СплитХаб', fontSize: 18, bold: true, alignment: 'center', margin: [0, 0, 0, 4] },
      { text: `Оптовые кондиционеры · Симферополь · ${date} · Товаров: ${PRODUCTS.length}`,
        fontSize: 9, color: '#888888', alignment: 'center', margin: [0, 0, 0, 14] },
      {
        table: { headerRows: 1, dontBreakRows: true, widths: WIDTHS, body },
        layout: {
          hLineWidth: (i, node) => i === 0 || i === node.table.body.length ? 0.8 : 0.4,
          vLineWidth: () => 0.4,
          hLineColor: () => '#CCCCCC',
          vLineColor: () => '#EEEEEE',
        },
      },
    ],
    footer: (page, count) => ({
      text: `СплитХаб · Оптовые кондиционеры · Симферополь · Страница ${page} из ${count}`,
      fontSize: 7, color: '#AAAAAA', alignment: 'center', margin: [0, 4, 0, 0],
    }),
  };
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
