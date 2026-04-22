/**
 * pricelist.js — Генератор прайса СплитХаб
 * PDF: html2pdf.js (настоящий скачиваемый файл)
 * Excel: ExcelJS (цвета, стили, форматирование)
 * Группировка: Бренд → Серия, Расходники → подгруппы
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
  const ac     = {};   // brand → series → []
  const rashod = {};   // subgroup → []
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

/* ── PDF (html2pdf.js в popup-окне — настоящий скачиваемый файл) ── */
function downloadPricePDF() {
  closePriceModal();
  const date = new Date().toLocaleDateString('ru-RU');
  const fname = 'splithub-price-' + date.replace(/\./g, '-') + '.pdf';
  const content = _buildPriceContent(date);

  const fullHtml = `<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<title>Прайс СплитХаб</title></head>
<body style="margin:0;padding:0;background:#fff">
<div id="msg" style="position:fixed;top:16px;right:16px;z-index:9999;background:#0d9488;color:#fff;padding:12px 20px;border-radius:10px;font-family:Arial;font-size:14px;font-weight:bold;box-shadow:0 4px 14px rgba(0,0,0,.3)">⏳ Генерируем PDF…</div>
${content}
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"><\/script>
<script>
window.onload = function() {
  html2pdf(document.querySelector('.price-wrap'), {
    margin:[8,8,8,8],
    filename:'${fname}',
    image:{type:'jpeg',quality:0.88},
    html2canvas:{scale:1.4,useCORS:true,logging:false,imageTimeout:20000},
    jsPDF:{unit:'mm',format:'a4',orientation:'portrait'},
    pagebreak:{mode:['css','legacy'],before:'.pb-before'}
  }).then(function(){
    document.getElementById('msg').textContent = '✓ PDF готов! Закрываю…';
    setTimeout(function(){ window.close(); }, 2500);
  }).catch(function(e){
    document.getElementById('msg').textContent = '❌ ' + e.message;
  });
};
<\/script>
</body></html>`;

  const w = window.open('', '_blank', 'width=900,height=700');
  if (!w) { alert('Разрешите всплывающие окна для splithub.ru'); return; }
  w.document.write(fullHtml);
  w.document.close();
}

/* ── HTML-контент прайса (для PDF) ── */
function _buildPriceContent(date) {
  const { ac, rashod, truba } = _groupProducts();
  let rowNum = 1;
  let body = '';

  /* Стили встроены в генерируемый HTML */
  const styles = `
    <style>
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
    .c-num{text-align:center}
    .c-id{font-family:monospace;font-size:10px;color:#888}
    .c-desc{font-size:10px;color:#666}
    .c-price{text-align:right;font-weight:700;color:#D97706;white-space:nowrap}
    .c-photo{text-align:center}
    .c-photo img{width:48px;height:48px;object-fit:contain;display:block;margin:0 auto}
    .s-ok{color:#10B981;font-weight:700}
    .s-warn{color:#F59E0B;font-weight:700}
    .s-no{color:#EF4444;font-weight:700}
    .pb-before{page-break-before:always}
    </style>
  `;

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
      const fmt  = new Intl.NumberFormat('ru-RU').format(p.price);
      const sc   = p.stock === 'in_stock' ? 'ok' : (p.stock || '').startsWith('days') ? 'warn' : 'no';
      const photo = p.photo
        ? `<img src="${PRICE_SITE}/assets/img/products/${p.photo}" crossorigin="anonymous" />`
        : '—';
      t += `<tr>
        <td class="c-num">${rowNum}</td>
        <td class="c-id">${p.id}</td>
        <td>${p.model || ''}</td>
        <td class="c-desc">${p.descShort || ''}</td>
        <td class="c-price">${fmt}&nbsp;₽</td>
        <td class="c-photo">${photo}</td>
        <td class="s-${sc}">${p.stockLabel || ''}</td>
      </tr>`;
      rowNum++;
    });

    return t + `</tbody></table>`;
  }

  /* Кондиционеры: бренд → серия */
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

  /* Медная труба */
  if (truba.length) {
    body += `<div class="brand-group pb-before"><div class="brand-title truba">Медная труба</div>`;
    body += buildTable(truba);
    body += `</div>`;
  }

  /* Расходники по подгруппам */
  const grpOrder = ['Фреон','Дренаж','Лента','Кабель','Крепёж','Кронштейны','Изоляция','Прочее'];
  const hasRashod = grpOrder.some(g => rashod[g] && rashod[g].length);
  if (hasRashod) {
    body += `<div class="brand-group pb-before"><div class="brand-title rashod">Расходники</div>`;
    grpOrder.forEach(grpName => {
      const items = rashod[grpName];
      if (!items || !items.length) return;
      body += `<div class="series-title rashod"><strong>${grpName}</strong></div>`;
      body += buildTable(items);
    });
    body += `</div>`;
  }

  return `${styles}
<div class="price-wrap">
<div class="hdr">
  <h1>Прайс-лист СплитХаб</h1>
  <p>Оптовые кондиционеры для монтажников и B2B · Симферополь</p>
  <p style="margin-top:5px;color:#bbb">Дата: ${date} · Товаров: ${PRODUCTS.length}</p>
</div>
${body}
</div>`;
}

/* ── Загрузка изображения → JPEG base64 для встраивания в Excel ── */
function fetchAsJpeg(url) {
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
    img.onerror = () => reject(new Error('load'));
    img.src = url;
  });
}

/* ── Excel (ExcelJS — цвета, стили, фото в ячейках) ── */
async function downloadPriceExcel() {
  if (typeof ExcelJS === 'undefined') {
    alert('Библиотека Excel ещё загружается. Подождите несколько секунд и повторите.');
    return;
  }
  closePriceModal();

  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(10,14,26,0.7);backdrop-filter:blur(6px);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;';
  overlay.innerHTML = `
    <div style="width:52px;height:52px;border:4px solid rgba(255,255,255,0.2);border-top-color:#1D6F42;border-radius:50%;animation:xlSpin 0.8s linear infinite;"></div>
    <div id="xl-status" style="color:#fff;font-family:'Inter',sans-serif;font-size:1rem;font-weight:600;">Загружаем фото…</div>
    <style>@keyframes xlSpin{to{transform:rotate(360deg)}}</style>`;
  document.body.appendChild(overlay);

  try {
    const wb  = new ExcelJS.Workbook();
    wb.creator = 'СплитХаб';
    wb.created = new Date();
    const ws  = wb.addWorksheet('Прайс');

    ws.columns = [
      { key:'num',   width:5  },
      { key:'id',    width:9  },
      { key:'model', width:42 },
      { key:'desc',  width:30 },
      { key:'price', width:14 },
      { key:'photo', width:32 },
      { key:'stock', width:18 },
    ];

    const date = new Date().toLocaleDateString('ru-RU');

    /* Заголовок книги */
    ws.mergeCells('A1:G1');
    const titleCell = ws.getCell('A1');
    titleCell.value = 'Прайс-лист СплитХаб';
    titleCell.font  = { name:'Arial', size:16, bold:true, color:{argb:'FF111111'} };
    titleCell.alignment = { horizontal:'center', vertical:'middle' };
    ws.getRow(1).height = 30;

    ws.mergeCells('A2:G2');
    const subCell = ws.getCell('A2');
    subCell.value = `Оптовые кондиционеры для монтажников и B2B · Симферополь · Дата: ${date} · Товаров: ${PRODUCTS.length}`;
    subCell.font  = { name:'Arial', size:10, color:{argb:'FF888888'} };
    subCell.alignment = { horizontal:'center', vertical:'middle' };
    ws.getRow(2).height = 18;

    ws.addRow([]);

    /* Цвета */
    const C_BRAND_BG  = 'FFF59E0B';  // amber
    const C_BRAND_FG  = 'FFFFFFFF';
    const C_SERIES_BG = 'FFF5F5F5';
    const C_HDR_BG    = 'FFE0E0E0';
    const C_PRICE_FG  = 'FFD97706';
    const C_OK_FG     = 'FF10B981';
    const C_WARN_FG   = 'FFF59E0B';
    const C_NO_FG     = 'FFEF4444';
    const C_ROW_ALT   = 'FFFAFAFA';

    function borderThin() {
      const s = {style:'thin',color:{argb:'FFDDDDDD'}};
      return {top:s,left:s,bottom:s,right:s};
    }
    function borderBrand() {
      const s = {style:'medium',color:{argb:'FF888888'}};
      return {top:s,left:s,bottom:s,right:s};
    }

    function addBrandRow(label, bgArgb) {
      ws.addRow([]);
      const r = ws.addRow([label,'','','','','','']);
      ws.mergeCells(`A${r.number}:G${r.number}`);
      const c = ws.getCell(`A${r.number}`);
      c.font  = { name:'Arial', size:13, bold:true, color:{argb:C_BRAND_FG} };
      c.fill  = { type:'pattern', pattern:'solid', fgColor:{argb:bgArgb} };
      c.alignment = { vertical:'middle', horizontal:'left', indent:1 };
      c.border = borderBrand();
      r.height = 24;
    }

    function addSeriesRow(label, isTealGroup) {
      const r = ws.addRow(['',label,'','','','','']);
      ws.mergeCells(`B${r.number}:G${r.number}`);
      const c = ws.getCell(`B${r.number}`);
      c.font  = { name:'Arial', size:11, bold:true, color:{argb:isTealGroup ? 'FF0D9488' : 'FF555555'} };
      c.fill  = { type:'pattern', pattern:'solid', fgColor:{argb:C_SERIES_BG} };
      c.alignment = { vertical:'middle', horizontal:'left', indent:1 };
      r.height = 18;
    }

    function addTableHeader() {
      const r = ws.addRow(['№','ID','Модель','Описание','Цена, ₽','Фото','Наличие']);
      r.height = 18;
      r.eachCell(cell => {
        cell.font   = { name:'Arial', size:10, bold:true };
        cell.fill   = { type:'pattern', pattern:'solid', fgColor:{argb:C_HDR_BG} };
        cell.border = borderThin();
        cell.alignment = { horizontal:'center', vertical:'middle', wrapText:false };
      });
      ws.getCell(`E${r.number}`).alignment = { horizontal:'right', vertical:'middle' };
    }

    function addItemRow(p, num, isAlt) {
      const fmt = new Intl.NumberFormat('ru-RU').format(p.price);
      const sc  = p.stock === 'in_stock' ? 'ok' : (p.stock||'').startsWith('days') ? 'warn' : 'no';
      const scColor = sc==='ok' ? C_OK_FG : sc==='warn' ? C_WARN_FG : C_NO_FG;
      const rowBg = isAlt ? C_ROW_ALT : 'FFFFFFFF';

      const r = ws.addRow([num, p.id, p.model||'', p.descShort||'', p.price, '', p.stockLabel||'']);
      r.height = 55;

      r.eachCell((cell, col) => {
        cell.fill   = { type:'pattern', pattern:'solid', fgColor:{argb:rowBg} };
        cell.border = borderThin();
        cell.font   = { name:'Arial', size:10 };
        cell.alignment = { vertical:'middle', wrapText:false };
      });

      // № — центр
      ws.getCell(`A${r.number}`).alignment = { horizontal:'center', vertical:'middle' };
      // ID — моно
      ws.getCell(`B${r.number}`).font = { name:'Courier New', size:9, color:{argb:'FF888888'} };
      // Цена
      const priceCell = ws.getCell(`E${r.number}`);
      priceCell.numFmt  = '#,##0" ₽"';
      priceCell.value   = p.price;
      priceCell.font    = { name:'Arial', size:10, bold:true, color:{argb:C_PRICE_FG} };
      priceCell.alignment = { horizontal:'right', vertical:'middle' };
      // Фото — встроенное изображение
      if (p.photo && photos[p.photo]) {
        const imgId = wb.addImage({ base64: photos[p.photo], extension: 'jpeg' });
        ws.addImage(imgId, {
          tl: { col: 5, row: r.number - 1 },
          ext: { width: 60, height: 60 },
          editAs: 'oneCell',
        });
      }
      // Наличие
      ws.getCell(`G${r.number}`).font = { name:'Arial', size:10, bold:true, color:{argb:scColor} };
    }

    /* Предзагрузка фото → JPEG base64 */
    const photos = {};
    const uniquePhotos = [...new Set(PRODUCTS.filter(p => p.photo).map(p => p.photo))];
    await Promise.allSettled(uniquePhotos.map(async fname => {
      try {
        photos[fname] = await fetchAsJpeg(`${PRICE_SITE}/assets/img/products/${fname}`);
      } catch(_) {}
    }));
    const xlStatus = document.getElementById('xl-status');
    if (xlStatus) xlStatus.textContent = 'Генерируем Excel…';

    let rowNum = 1;
    const { ac, rashod, truba } = _groupProducts();

    /* Кондиционеры */
    Object.keys(ac).sort().forEach(brand => {
      addBrandRow(brand, C_BRAND_BG);
      addTableHeader();
      Object.keys(ac[brand]).sort().forEach(series => {
        const items = ac[brand][series];
        if (!items.length) return;
        addSeriesRow(series, false);
        items.forEach((p, i) => { addItemRow(p, rowNum++, i%2===1); });
      });
    });

    /* Медная труба */
    if (truba.length) {
      addBrandRow('Медная труба', C_BRAND_BG);
      addTableHeader();
      truba.forEach((p, i) => { addItemRow(p, rowNum++, i%2===1); });
    }

    /* Расходники */
    const grpOrder = ['Фреон','Дренаж','Лента','Кабель','Крепёж','Кронштейны','Изоляция','Прочее'];
    const hasRashod = grpOrder.some(g => rashod[g] && rashod[g].length);
    if (hasRashod) {
      addBrandRow('Расходники', C_BRAND_BG);
      grpOrder.forEach(grpName => {
        const items = rashod[grpName];
        if (!items || !items.length) return;
        addSeriesRow(grpName, false);
        addTableHeader();
        items.forEach((p, i) => { addItemRow(p, rowNum++, i%2===1); });
      });
    }

    /* Freeze top rows (заголовок всегда виден) */
    ws.views = [{ state:'frozen', ySplit:3, activeCell:'A4' }];

    const buf  = await wb.xlsx.writeBuffer();
    const blob = new Blob([buf], {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `splithub-price-${date.replace(/\./g,'-')}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

  } catch(err) {
    console.error('Excel error:', err);
    alert('Ошибка генерации Excel: ' + err.message);
  } finally {
    overlay.remove();
  }
}
