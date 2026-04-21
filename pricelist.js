/**
 * pricelist.js — Генератор прайса СплитХаб
 * Форматы: PDF (html2pdf) / Excel (SheetJS)
 * Группировка: кондиционеры — Бренд → Серия; расходники — по типу товара
 */

/* ── Маппинг расходников по типу (SKU-prefix → категория) ── */
var RASHOD_CATEGORIES = {
  'drenazh':    'Дренаж',
  'thermaflex': 'Дренаж',
  'kronshtein': 'Крепёж',
  'lenta':      'Лента',
  'izolenta':   'Лента',
  'kabel':      'Кабель',
  'freon':      'Фреон',
};

function _getRashodCategory(p) {
  var sku = p.sku || '';
  for (var prefix in RASHOD_CATEGORIES) {
    if (sku.startsWith(prefix)) return RASHOD_CATEGORIES[prefix];
  }
  return p.brand || 'Расходники';
}

/* ── Группировка товаров ── */
function _groupProducts() {
  const grouped = {};
  PRODUCTS.forEach(p => {
    let brand, series;
    if (p.group === 'rashod') {
      brand  = _getRashodCategory(p);
      series = '_flat_';
    } else {
      brand  = p.brand  || 'Без бренда';
      series = p.series || 'Без серии';
    }
    if (!grouped[brand])         grouped[brand] = {};
    if (!grouped[brand][series]) grouped[brand][series] = [];
    grouped[brand][series].push(p);
  });
  return grouped;
}

/* ── Модальное окно: выбор формата ── */
function openPricelistModal() {
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

/* ── PDF (html2pdf — без диалога печати) ── */
async function downloadPricePDF() {
  if (typeof html2pdf === 'undefined') {
    alert('Библиотека PDF не загружена. Попробуйте обновить страницу.');
    return;
  }
  closePriceModal();

  const html = _buildPriceHTML();
  const tmp  = new DOMParser().parseFromString(html, 'text/html');

  const container = document.createElement('div');
  container.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:960px;background:#fff;';

  const style = document.createElement('style');
  const styleMatch = html.match(/<style>([\s\S]*?)<\/style>/);
  if (styleMatch) style.textContent = styleMatch[1];
  container.appendChild(style);

  const content = document.createElement('div');
  content.innerHTML = tmp.body.innerHTML;
  container.appendChild(content);

  document.body.appendChild(container);

  const filename = `splithub-price-${new Date().toLocaleDateString('ru-RU').replace(/\./g,'-')}.pdf`;
  await html2pdf().set({
    margin:      [8, 6],
    filename,
    image:       { type: 'jpeg', quality: 0.95 },
    html2canvas: { scale: 2, useCORS: true, logging: false },
    jsPDF:       { unit: 'mm', format: 'a4', orientation: 'landscape' },
  }).from(container).save();

  document.body.removeChild(container);
}

function _buildPriceHTML() {
  const grouped = _groupProducts();
  const date    = new Date().toLocaleDateString('ru-RU');
  let rowNum = 1;
  let body = '';

  Object.keys(grouped).sort().forEach(brand => {
    body += `<div class="brand-group">
      <div class="brand-title">${brand}</div>`;

    Object.keys(grouped[brand]).sort().forEach(series => {
      const items = grouped[brand][series];
      if (!items.length) return;
      const info = (items[0].benefits || []).slice(0, 3).join(' · ');

      if (series !== '_flat_') {
        body += `<div class="series-title"><strong>${series}</strong>${info ? ' — ' + info : ''}</div>`;
      }
      body += `<table><thead><tr>
        <th class="c-num">№</th><th class="c-id">ID</th>
        <th>Модель</th><th class="c-desc">Описание</th>
        <th class="c-price">Цена</th><th class="c-photo">Фото</th><th>Наличие</th>
      </tr></thead><tbody>`;

      items.forEach(p => {
        const fmt  = new Intl.NumberFormat('ru-RU').format(p.price);
        const sc   = p.stock === 'in_stock' ? 'ok' : p.stock.startsWith('days') ? 'warn' : 'no';
        const photo = p.photo ? `<img src="assets/img/products/${p.photo}" />` : '—';
        body += `<tr>
          <td class="c-num">${rowNum}</td>
          <td class="c-id">${p.id}</td>
          <td>${p.model}</td>
          <td class="c-desc">${p.descShort || ''}</td>
          <td class="c-price">${fmt} ₽</td>
          <td class="c-photo">${photo}</td>
          <td class="s-${sc}">${p.stockLabel}</td>
        </tr>`;
        rowNum++;
      });

      body += `</tbody></table>`;
    });
    body += `</div>`;
  });

  return `<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<title>Прайс СплитХаб</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;background:#fff;padding:20px;font-size:12px}
.wrap{max-width:960px;margin:0 auto}
.hdr{text-align:center;margin-bottom:28px}
.hdr h1{font-size:20px;margin-bottom:4px}
.hdr p{color:#888;font-size:12px}
.brand-group{margin-bottom:32px;page-break-inside:avoid}
.brand-title{background:#F59E0B;color:#fff;font-weight:700;font-size:14px;padding:10px 14px;border-radius:6px;margin-bottom:4px}
.series-title{background:#f5f5f5;border-left:3px solid #F59E0B;padding:6px 12px;margin-bottom:8px;font-size:11px;color:#555}
table{width:100%;border-collapse:collapse;margin-bottom:16px}
th{background:#f0f0f0;padding:8px 6px;text-align:left;font-size:11px;border-bottom:2px solid #ddd}
td{padding:8px 6px;border-bottom:1px solid #eee;vertical-align:middle}
.c-num{width:28px;text-align:center}
.c-id{width:60px;font-family:monospace;font-size:10px;color:#888}
.c-desc{font-size:10px;color:#666;max-width:160px}
.c-price{text-align:right;font-weight:700;color:#D97706;white-space:nowrap}
.c-photo{width:56px;text-align:center}
.c-photo img{width:50px;height:50px;object-fit:contain}
.s-ok{color:#10B981;font-weight:700}
.s-warn{color:#F59E0B;font-weight:700}
.s-no{color:#EF4444;font-weight:700}
@media print{body{padding:0}.brand-group{page-break-inside:avoid}}
</style></head>
<body><div class="wrap">
<div class="hdr">
  <h1>Прайс-лист СплитХаб</h1>
  <p>Оптовые кондиционеры для монтажников и B2B · Симферополь</p>
  <p style="margin-top:6px;color:#bbb">Дата: ${date} · Товаров: ${PRODUCTS.length}</p>
</div>
${body}
</div></body></html>`;
}

/* ── Excel (SheetJS + стили) ── */
function downloadPriceExcel() {
  if (typeof XLSX === 'undefined') {
    alert('Библиотека Excel не загружена. Попробуйте обновить страницу.');
    return;
  }

  const grouped = _groupProducts();
  const wb  = XLSX.utils.book_new();
  const rows = [];
  const meta = [];   // { rowIdx, type: 'title'|'brand'|'series'|'header'|'stock_ok'|'stock_warn'|'stock_no' }

  const pushRow = (row, type) => {
    meta.push({ rowIdx: rows.length, type });
    rows.push(row);
  };

  const COL = 6;
  const blank = () => Array(COL).fill('');

  // ── Шапка документа ──
  pushRow(['Прайс-лист СплитХаб', ...Array(COL-1).fill('')], 'title');
  pushRow([`Оптовые кондиционеры для монтажников · Симферополь`, ...Array(COL-1).fill('')], 'subtitle');
  pushRow([`Дата: ${new Date().toLocaleDateString('ru-RU')}   Товаров: ${PRODUCTS.length}   zakaz@splithub.ru   +7 978 599-13-69`, ...Array(COL-1).fill('')], 'subtitle');
  pushRow(blank(), 'empty');

  // ── Шапка таблицы ──
  pushRow(['№', 'ID', 'Модель / Описание', 'Характеристики', 'Цена, ₽', 'Наличие'], 'header');

  let rowNum = 1;

  Object.keys(grouped).sort().forEach(brand => {
    pushRow(blank(), 'empty');
    pushRow([brand, ...Array(COL-1).fill('')], 'brand');

    Object.keys(grouped[brand]).sort().forEach(series => {
      const items = grouped[brand][series];
      if (!items.length) return;

      if (series !== '_flat_') {
        const info = (items[0].benefits || []).slice(0, 3).join(' · ');
        pushRow([`  ${series}${info ? ' — ' + info : ''}`, ...Array(COL-1).fill('')], 'series');
      }

      items.forEach(p => {
        const sc = p.stock === 'in_stock' ? 'stock_ok'
                 : p.stock.startsWith('days') ? 'stock_warn' : 'stock_no';
        pushRow([rowNum, p.id, p.model, p.descShort || '', p.price, p.stockLabel], sc);
        rowNum++;
      });
    });
  });

  const ws = XLSX.utils.aoa_to_sheet(rows);

  // ── Ширина столбцов ──
  ws['!cols'] = [
    { wch: 4  },
    { wch: 8  },
    { wch: 42 },
    { wch: 30 },
    { wch: 12 },
    { wch: 18 },
  ];

  // ── Freeze: первые 5 строк (шапка) ──
  ws['!freeze'] = { xSplit: 0, ySplit: 5, topLeftCell: 'A6', activeCell: 'A6', sqref: 'A6' };

  // ── Стили ячеек (работают в xlsx) ──
  const S = {
    title:   { font:{ bold:true, sz:14, color:{rgb:'1A1C22'} }, fill:{ patternType:'solid', fgColor:{rgb:'F59E0B'} } },
    subtitle:{ font:{ sz:9, color:{rgb:'5A5F6E'} } },
    header:  { font:{ bold:true, sz:10, color:{rgb:'FFFFFF'} }, fill:{ patternType:'solid', fgColor:{rgb:'1A1C22'} }, alignment:{ wrapText:true } },
    brand:   { font:{ bold:true, sz:11, color:{rgb:'FFFFFF'} }, fill:{ patternType:'solid', fgColor:{rgb:'D97706'} } },
    series:  { font:{ bold:true, sz:9,  color:{rgb:'5A5F6E'} }, fill:{ patternType:'solid', fgColor:{rgb:'F5F5F0'} } },
    stock_ok:  { font:{ color:{rgb:'10B981'}, bold:true } },
    stock_warn:{ font:{ color:{rgb:'D97706'}, bold:true } },
    stock_no:  { font:{ color:{rgb:'EF4444'}, bold:true } },
    price:   { font:{ bold:true, color:{rgb:'D97706'} }, numFmt: '#,##0' },
  };

  meta.forEach(({ rowIdx, type }) => {
    for (let c = 0; c < COL; c++) {
      const ref = XLSX.utils.encode_cell({ r: rowIdx, c });
      if (!ws[ref]) ws[ref] = { t: 's', v: '' };
      const base = S[type] || {};
      ws[ref].s = { ...base };
      if (c === 4 && (type === 'stock_ok' || type === 'stock_warn' || type === 'stock_no')) {
        ws[ref].s = S.price;
      }
      if (c === 5 && (type === 'stock_ok' || type === 'stock_warn' || type === 'stock_no')) {
        ws[ref].s = S[type];
      }
    }
  });

  // ── Merge: шапка и заголовки брендов на всю ширину ──
  ws['!merges'] = [];
  meta.forEach(({ rowIdx, type }) => {
    if (type === 'title' || type === 'subtitle' || type === 'brand' || type === 'series') {
      ws['!merges'].push({ s:{ r:rowIdx, c:0 }, e:{ r:rowIdx, c:COL-1 } });
    }
  });

  XLSX.utils.book_append_sheet(wb, ws, 'Прайс');
  XLSX.writeFile(wb, `splithub-price-${new Date().toLocaleDateString('ru-RU').replace(/\./g,'-')}.xlsx`);
  closePriceModal();
}
