(function () {
  'use strict';

  var root = document.getElementById('admin-root');
  var API = 'api/admin.php';
  var AUTH = 'api/auth.php';
  var PRODUCT_PAGE_SIZE = 100;
  var VISITOR_PAGE_SIZE = 50;
  var state = {
    user: null,
    view: localStorage.getItem('sh_admin_view') || 'overview',
    title: '',
    products: [],
    productsTotal: 0,
    productSummary: { total: 0, active: 0, hidden: 0, custom: 0 },
    priceProducts: [],
    productFilters: { search: '', group: '', status: 'all', page: 1 },
    orders: [],
    orderFilters: { search: '', status: '', date_from: '', date_to: '', page: 1 },
    guests: [],
    guestFilters: { search: '', page: 1 },
    users: [],
    userSearch: '',
    visitorPage: 1,
    selectedOrders: new Set(),
    selectedGuests: new Set(),
    selectedProducts: new Set(),
    editorProduct: null,
    editorTab: 'main',
    charts: {}
  };
  var drawerReturnFocus = null;

  var navItems = [
    { key: 'overview', label: 'Обзор', icon: 'layout-dashboard', section: 'Работа' },
    { key: 'orders', label: 'Заказы', icon: 'package-check', section: 'Работа' },
    { key: 'guests', label: 'Гости', icon: 'shopping-bag', section: 'Работа' },
    { key: 'clients', label: 'Клиенты', icon: 'users', section: 'Работа' },
    { key: 'products', label: 'Товары', icon: 'snowflake', section: 'Каталог' },
    { key: 'catalog', label: 'Прайс', icon: 'file-spreadsheet', section: 'Каталог' },
    { key: 'promo', label: 'Промо', icon: 'badge-percent', section: 'Каталог' },
    { key: 'notifications', label: 'Уведомления', icon: 'bell-ring', section: 'Управление' },
    { key: 'analytics', label: 'Аналитика', icon: 'chart-no-axes-combined', section: 'Управление' },
    { key: 'visitors', label: 'Посетители', icon: 'mouse-pointer-click', section: 'Управление' },
    { key: 'settings', label: 'Настройки', icon: 'settings', section: 'Управление' }
  ];

  var statusMap = {
    new: 'Новый',
    confirmed: 'Подтвержден',
    in_progress: 'В работе',
    shipped: 'Отгружен',
    completed: 'Выполнен',
    cancelled: 'Отменен'
  };

  var stockLabels = {
    in_stock: 'В наличии',
    days_1_2: '1-2 дня',
    days_3_5: '3-5 дней',
    order_7: '7 дней',
    out: 'Нет'
  };

  var groupLabels = {
    inv: 'Инвертор',
    onoff: 'On/Off',
    pac_inv: 'Полупром инвертор',
    pac_onoff: 'Полупром On/Off',
    truba: 'Труба',
    rashod: 'Расходники',
    poluprom: 'Полупром',
    multi: 'Мульти',
    accessory: 'Аксессуар'
  };

  function qs(sel, scope) { return (scope || document).querySelector(sel); }
  function qsa(sel, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(sel)); }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function money(value) {
    return Number(value || 0).toLocaleString('ru-RU') + ' ₽';
  }

  function phone(value) {
    var result = String(value || '').trim();
    return result && result.charAt(0) !== '+' ? '+' + result : result;
  }

  function fmtDate(value) {
    if (!value) return '';
    var d = new Date(String(value).replace(' ', 'T'));
    if (Number.isNaN(d.getTime())) return escapeHtml(value);
    return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function icon(name) {
    return '<i data-lucide="' + name + '"></i>';
  }

  function hydrateIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons({ attrs: { 'aria-hidden': 'true' } });
    }
  }

  function toast(message, type) {
    var host = qs('#toast-host');
    if (!host) return;
    var el = document.createElement('div');
    el.className = 'toast ' + (type || '');
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transform = 'translateY(6px)';
      setTimeout(function () { el.remove(); }, 220);
    }, 3800);
  }

  async function request(url, options) {
    var opts = options || {};
    var res = await fetch(url, opts);
    var data;
    try { data = await res.json(); } catch (e) { data = { ok: false, error: 'Некорректный ответ сервера' }; }
    if (!res.ok || data.ok === false) {
      var err = new Error(data.error || ('HTTP ' + res.status));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function api(action, params, options) {
    params = params || {};
    options = options || {};
    var url = API + '?action=' + encodeURIComponent(action);
    Object.keys(params).forEach(function (key) {
      if (params[key] !== '' && params[key] != null) {
        url += '&' + encodeURIComponent(key) + '=' + encodeURIComponent(params[key]);
      }
    });
    if (options.body instanceof FormData) {
      return request(url, { method: 'POST', body: options.body });
    }
    if (options.method === 'POST') {
      return request(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options.body || {})
      });
    }
    return request(url);
  }

  function auth(action, body) {
    var opts = body ? {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    } : {};
    return request(AUTH + '?action=' + encodeURIComponent(action), opts);
  }

  function renderLogin(error) {
    root.innerHTML = [
      '<main class="login-screen">',
      '<section class="login-card">',
      '<div class="brand-mark">SH</div>',
      '<h1 class="login-title">Админка СплитХаб</h1>',
      '<p class="login-sub">Войдите под администратором, чтобы управлять заказами, клиентами и каталогом.</p>',
      '<div class="error-box ' + (error ? 'on' : '') + '" id="login-error">' + escapeHtml(error || '') + '</div>',
      '<form id="login-form">',
      '<label class="field"><span>Логин или телефон</span><input class="input" name="phone" autocomplete="username" required></label>',
      '<label class="field"><span>Пароль</span><input class="input" name="password" type="password" autocomplete="current-password" required></label>',
      '<button class="btn primary" type="submit">' + icon('log-in') + '<span>Войти</span></button>',
      '</form>',
      '</section>',
      '</main>'
    ].join('');
    qs('#login-form').addEventListener('submit', async function (event) {
      event.preventDefault();
      var fd = new FormData(event.currentTarget);
      try {
        var data = await auth('login', { phone: fd.get('phone'), password: fd.get('password') });
        if (!data.user || data.user.role !== 'admin') {
          await auth('logout').catch(function () {});
          renderLogin('Этот пользователь не администратор');
          return;
        }
        state.user = data.user;
        renderShell();
        switchView(state.view);
      } catch (err) {
        qs('#login-error').textContent = err.message;
        qs('#login-error').classList.add('on');
      }
    });
    hydrateIcons();
  }

  function renderShell() {
    root.innerHTML = [
      '<div class="admin-shell">',
      '<button class="sidebar-scrim" id="sidebar-scrim" aria-label="Закрыть меню"></button>',
      '<aside class="sidebar" id="sidebar">',
      '<div class="sidebar-head"><div class="brand-mark">SH</div><div class="brand-text"><strong>СплитХаб</strong><span>Администрирование</span></div></div>',
       '<nav class="nav" id="nav">',
       navItems.map(function (item, index) {
         var previous = navItems[index - 1];
         var section = !previous || previous.section !== item.section ? '<div class="nav-section">' + escapeHtml(item.section) + '</div>' : '';
         return section + '<button class="nav-link" data-view="' + item.key + '">' + icon(item.icon) + '<span>' + item.label + '</span></button>';
       }).join(''),
      '</nav>',
      '<div class="sidebar-foot">',
      '<div class="user-pill"><div class="avatar">' + escapeHtml((state.user.name || 'A').slice(0, 1).toUpperCase()) + '</div><div><strong>' + escapeHtml(state.user.name || 'Админ') + '</strong><span>' + escapeHtml(state.user.phone || '') + '</span></div></div>',
      '<button class="btn ghost" id="logout-btn">' + icon('log-out') + '<span>Выйти</span></button>',
      '</div>',
      '</aside>',
      '<main class="main">',
      '<header class="topbar">',
      '<button class="icon-btn mobile-menu" id="mobile-menu" title="Меню">' + icon('menu') + '</button>',
      '<div><h1 class="page-title" id="page-title"></h1><div class="page-subtitle" id="page-subtitle"></div></div>',
      '<div class="topbar-actions" id="topbar-actions"></div>',
      '</header>',
      '<section class="content"><div id="view-root" class="view"></div></section>',
      '</main>',
      '</div>',
      '<div class="drawer-backdrop" id="drawer-backdrop"></div>',
      '<aside class="drawer" id="drawer"></aside>',
      '<div class="toast-host" id="toast-host"></div>'
    ].join('');
    qs('#nav').addEventListener('click', function (event) {
      var btn = event.target.closest('[data-view]');
      if (!btn) return;
      switchView(btn.dataset.view);
      toggleMobileSidebar(false);
    });
    qs('#mobile-menu').addEventListener('click', function () { toggleMobileSidebar(true); });
    qs('#sidebar-scrim').addEventListener('click', function () { toggleMobileSidebar(false); });
    qs('#logout-btn').addEventListener('click', async function () {
      await auth('logout').catch(function () {});
      state.user = null;
      renderLogin();
    });
    qs('#drawer-backdrop').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') return;
      toggleMobileSidebar(false);
      closeDrawer();
    });
    hydrateIcons();
  }

  function toggleMobileSidebar(open) {
    var sidebar = qs('#sidebar');
    var scrim = qs('#sidebar-scrim');
    if (sidebar) sidebar.classList.toggle('on', !!open);
    if (scrim) scrim.classList.toggle('on', !!open);
  }

  function setHeader(title, subtitle, actionsHtml) {
    qs('#page-title').textContent = title;
    qs('#page-subtitle').textContent = subtitle || '';
    qs('#topbar-actions').innerHTML = actionsHtml || '';
    hydrateIcons();
  }

  function switchView(view) {
    state.view = view;
    localStorage.setItem('sh_admin_view', view);
    qsa('.nav-link').forEach(function (btn) { btn.classList.toggle('active', btn.dataset.view === view); });
    var map = {
      overview: renderOverview,
      orders: renderOrders,
      guests: renderGuests,
      clients: renderClients,
      promo: renderPromo,
      notifications: renderNotifications,
      analytics: renderAnalytics,
      visitors: renderVisitors,
      catalog: renderCatalog,
      products: renderProducts,
      settings: renderSettings
    };
    (map[view] || renderOverview)();
  }

  function viewRoot() { return qs('#view-root'); }

  function loading(title, subtitle) {
    setHeader(title, subtitle);
    viewRoot().innerHTML = '<div class="loader"><div><div class="spinner"></div><p>Загружаем данные...</p></div></div>';
  }

  function statusBadge(status) {
    return '<span class="status ' + escapeHtml(status || '') + '">' + escapeHtml(statusMap[status] || status || '—') + '</span>';
  }

  function productImageUrl(photo) {
    if (!photo) return '';
    photo = String(photo);
    if (/^https?:\/\//i.test(photo) || photo.indexOf('assets/') === 0 || photo.indexOf('/') === 0) return photo;
    return 'assets/img/products/' + photo;
  }

  function productImg(photo, alt) {
    var url = productImageUrl(photo);
    return '<div class="product-img">' + (url
      ? '<img src="' + escapeHtml(url) + '" alt="' + escapeHtml(alt || '') + '" onerror="this.remove()">'
      : icon('image')) + '</div>';
  }

  function orderItemsHtml(items) {
    if (!items || !items.length) return '<span class="muted">Нет позиций</span>';
    return items.slice(0, 4).map(function (item) {
      return '<div>' + escapeHtml(item.product_name || item.name || 'Товар') + ' x' + Number(item.qty || 1) + '</div>';
    }).join('') + (items.length > 4 ? '<div class="muted">+' + (items.length - 4) + ' еще</div>' : '');
  }

  async function renderOverview() {
    loading('Обзор', 'Сегодняшнее состояние продаж и быстрые действия');
    try {
      var data = await Promise.all([
        api('stats'),
        api('orders', { page: 1 }),
        api('analytics', { days: 14 })
      ]);
      var stats = data[0].stats || {};
      var orders = (data[1].orders || []).slice(0, 6);
      var top = data[2].top_products || [];
      setHeader('Обзор', 'Продажи, клиенты и каталог под рукой', '<button class="btn accent" data-action="send-report" aria-label="Отчет в Telegram">' + icon('send') + '<span>Отчет в TG</span></button>');
      viewRoot().innerHTML = [
        '<section class="metric-grid">',
        metric('Заказы', stats.orders_count, 'Всего заявок'), metric('Новые', stats.orders_new, 'Нужна обработка'),
        metric('Сегодня', stats.orders_today, 'За текущий день'), metric('Выручка', money(stats.orders_revenue), 'Без отмененных'),
        '</section>',
        '<section class="quick-grid">',
        quick('orders', 'Разобрать заказы', 'Статусы, заметки, отправка менеджеру', 'package-check'),
        quick('products', 'Обновить товары', 'Цена, фото, описание, видимость', 'snowflake'),
        quick('catalog', 'Собрать прайс', 'Excel/PDF и отправка файлом', 'file-spreadsheet'),
        '</section>',
        '<section class="split-grid">',
        '<div class="panel"><div class="panel-head"><div><h2 class="panel-title">Последние заказы</h2><div class="panel-subtitle">Первые в очереди на обработку</div></div></div><div class="panel-body">' + ordersListMini(orders) + '</div></div>',
        '<div class="panel"><div class="panel-head"><div><h2 class="panel-title">Топ товаров</h2><div class="panel-subtitle">По выручке за 14 дней</div></div></div><div class="panel-body">' + topProductsMini(top) + '</div></div>',
        '</section>'
      ].join('');
      qs('[data-action="send-report"]').addEventListener('click', sendReport);
      qsa('.quick-action').forEach(function (btn) { btn.addEventListener('click', function () { switchView(btn.dataset.view); }); });
      hydrateIcons();
    } catch (err) {
      failView(err);
    }
  }

  function metric(label, value, hint) {
    return '<div class="metric"><small>' + escapeHtml(label) + '</small><strong>' + escapeHtml(value) + '</strong><span>' + escapeHtml(hint) + '</span></div>';
  }

  function quick(view, title, text, ico) {
    return '<button class="btn quick-action" data-view="' + view + '">' + icon(ico) + '<strong>' + escapeHtml(title) + '</strong><span>' + escapeHtml(text) + '</span></button>';
  }

  function ordersListMini(orders) {
    if (!orders.length) return '<div class="empty">Заказов пока нет</div>';
    return '<div class="mobile-list" style="display:grid">' + orders.map(function (o) {
      return '<div class="mobile-item"><div class="mobile-item-head"><div><div class="mobile-item-title">SH-' + String(o.id).padStart(5, '0') + '</div><div class="mobile-item-meta">' + escapeHtml(o.user_name || '') + ' / ' + escapeHtml(phone(o.user_phone)) + '</div></div>' + statusBadge(o.status) + '</div><strong>' + money(o.total) + '</strong><div class="mobile-item-meta">' + fmtDate(o.created_at) + '</div></div>';
    }).join('') + '</div>';
  }

  function topProductsMini(top) {
    if (!top.length) return '<div class="empty">Пока не хватает данных</div>';
    var max = Math.max.apply(null, top.map(function (p) { return Number(p.rev || 0); }));
    return '<div class="stat-line">' + top.map(function (p) {
      var pct = max ? Math.round(Number(p.rev || 0) / max * 100) : 0;
      return '<div class="stat-line-row"><span>' + escapeHtml(p.product_name || 'Товар') + '</span><div class="bar"><span style="width:' + pct + '%"></span></div><b>' + escapeHtml(p.qty || 0) + '</b></div>';
    }).join('') + '</div>';
  }

  function failView(err) {
    if (err.status === 401 || err.status === 403) {
      renderLogin(err.message);
      return;
    }
    viewRoot().innerHTML = '<div class="empty">Ошибка: ' + escapeHtml(err.message) + '</div>';
  }

  async function sendReport() {
    try {
      await api('send_report', {}, { method: 'POST', body: {} });
      toast('Отчет отправлен', 'ok');
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function renderOrders() {
    loading('Заказы', 'Зарегистрированные клиенты и их заявки');
    try {
      var data = await api('orders', state.orderFilters);
      state.orders = data.orders || [];
      setHeader('Заказы', 'Статусы, заметки, массовые действия', '<a class="btn ghost" href="' + API + '?action=export_orders_csv">' + icon('download') + '<span>CSV</span></a><a class="btn ghost" href="' + API + '?action=export_xlsx">' + icon('file-down') + '<span>XLSX</span></a>');
      viewRoot().innerHTML = [
        orderToolbar('orders'),
        bulkBar('orders'),
        '<div class="panel"><div class="table-wrap">' + ordersTable(state.orders, false) + '</div>' + ordersCards(state.orders, false) + '</div>',
        pager(data.page || 1, data.total || 0, 50, 'orders')
      ].join('');
      bindOrderView(false);
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function orderToolbar(type) {
    var f = type === 'guests' ? state.guestFilters : state.orderFilters;
    var hasFilters = !!(f.search || f.status || f.date_from || f.date_to);
    return [
      '<div class="toolbar">',
      '<div class="toolbar-left">',
      '<input class="input search" id="' + type + '-search" aria-label="Поиск ' + (type === 'guests' ? 'гостевых заказов' : 'заказов') + '" placeholder="Поиск по номеру, имени или телефону" value="' + escapeHtml(f.search || '') + '">',
      type === 'orders' ? '<select class="select" id="orders-status" aria-label="Фильтр по статусу"><option value="">Все статусы</option>' + Object.keys(statusMap).map(function (s) { return '<option value="' + s + '"' + (f.status === s ? ' selected' : '') + '>' + statusMap[s] + '</option>'; }).join('') + '</select>' : '',
      type === 'orders' ? '<input class="input" type="date" id="orders-date-from" aria-label="Дата заказа с" value="' + escapeHtml(f.date_from || '') + '"><input class="input" type="date" id="orders-date-to" aria-label="Дата заказа по" value="' + escapeHtml(f.date_to || '') + '">' : '',
      '</div><div class="toolbar-right">' + (hasFilters ? '<button class="btn ghost" id="' + type + '-reset">' + icon('rotate-ccw') + '<span>Сбросить</span></button>' : '') + '<button class="btn primary" id="' + type + '-apply">' + icon('search') + '<span>Показать</span></button></div>',
      '</div>'
    ].join('');
  }

  function bulkBar(type) {
    var count = type === 'guests' ? state.selectedGuests.size : state.selectedOrders.size;
    var statuses = Object.keys(statusMap).filter(function (s) { return type === 'orders' || s !== 'shipped'; });
    return '<div class="bulkbar ' + (count ? 'on' : '') + '" id="' + type + '-bulk"><strong>Выбрано: ' + count + '</strong><div class="toolbar-right"><select class="select" id="' + type + '-bulk-status">' + statuses.map(function (s) { return '<option value="' + s + '">' + statusMap[s] + '</option>'; }).join('') + '</select><button class="btn ok" id="' + type + '-bulk-apply">' + icon('check') + '<span>Статус</span></button><button class="btn danger" id="' + type + '-bulk-delete">' + icon('trash-2') + '<span>Удалить</span></button></div></div>';
  }

  function ordersTable(orders, guest) {
    if (!orders.length) return '<div class="empty">Ничего не найдено</div>';
    var rows = orders.map(function (o) {
      var id = Number(o.id);
      var num = guest ? 'G-' + String(id).padStart(5, '0') : 'SH-' + String(id).padStart(5, '0');
      var checked = (guest ? state.selectedGuests : state.selectedOrders).has(id) ? ' checked' : '';
      return '<tr class="order-row" data-order-row="' + id + '" data-order-guest="' + (guest ? '1' : '0') + '" tabindex="0" aria-label="Открыть ' + (guest ? 'гостевую заявку ' : 'заказ ') + num + '"><td><input type="checkbox" data-select="' + id + '"' + checked + ' aria-label="Выбрать ' + num + '"></td><td><b>' + num + '</b><div class="muted">' + fmtDate(o.created_at) + '</div></td><td>' + escapeHtml(o.name || o.user_name || '') + '<div class="muted">' + escapeHtml(phone(o.phone || o.user_phone)) + '</div></td><td>' + orderItemsHtml(o.items) + '</td><td class="nowrap"><b>' + money(o.total) + '</b></td><td>' + statusControl(o.status || 'new', id, guest, num) + '</td><td>' + actionButtons(id, guest, num) + '</td></tr>';
    }).join('');
    return '<table class="data-table"><thead><tr><th></th><th>Номер</th><th>Клиент</th><th>Состав</th><th>Сумма</th><th>Статус</th><th>Действия</th></tr></thead><tbody>' + rows + '</tbody></table>';
  }

  function ordersCards(orders, guest) {
    if (!orders.length) return '<div class="mobile-list"><div class="empty">Ничего не найдено</div></div>';
    return '<div class="mobile-list">' + orders.map(function (o) {
      var id = Number(o.id);
      var num = guest ? 'G-' + String(id).padStart(5, '0') : 'SH-' + String(id).padStart(5, '0');
      var checked = (guest ? state.selectedGuests : state.selectedOrders).has(id) ? ' checked' : '';
      return '<article class="mobile-item order-card" data-order-row="' + id + '" data-order-guest="' + (guest ? '1' : '0') + '" tabindex="0" aria-label="Открыть ' + (guest ? 'гостевую заявку ' : 'заказ ') + num + '"><div class="mobile-item-head"><label><input type="checkbox" data-select="' + id + '"' + checked + '> <span class="mobile-item-title">' + num + '</span></label>' + statusBadge(o.status || 'new') + '</div><div class="mobile-item-meta">' + escapeHtml(o.name || o.user_name || '') + ' / ' + escapeHtml(phone(o.phone || o.user_phone)) + '</div><div style="margin:10px 0">' + orderItemsHtml(o.items) + '</div><b>' + money(o.total) + '</b><div class="mobile-item-meta">' + fmtDate(o.created_at) + '</div><div class="table-actions" style="margin-top:10px">' + statusControl(o.status || 'new', id, guest, num) + actionButtons(id, guest, num) + '</div></article>';
    }).join('') + '</div>';
  }

  function statusControl(value, id, guest, num) {
    var statuses = Object.keys(statusMap).filter(function (s) { return !guest || s !== 'shipped'; });
    return '<select class="select" data-status="' + id + '" data-guest="' + (guest ? '1' : '0') + '" aria-label="Статус ' + escapeHtml(num || String(id)) + '">' + statuses.map(function (s) {
      return '<option value="' + s + '"' + (s === value ? ' selected' : '') + '>' + statusMap[s] + '</option>';
    }).join('') + '</select>';
  }

  function actionButtons(id, guest, num) {
    var label = escapeHtml(num || String(id));
    if (guest) {
      return '<div class="table-actions"><button class="btn small danger" data-delete-guest="' + id + '" aria-label="Удалить ' + label + '" title="Удалить">' + icon('trash-2') + '</button></div>';
    }
    return '<div class="table-actions"><button class="btn small" data-note="' + id + '" aria-label="Заметка ' + label + '" title="Заметка">' + icon('sticky-note') + '</button><button class="btn small" data-send="' + id + '" data-channel="tg" aria-label="Отправить ' + label + ' в Telegram" title="Отправить в Telegram">' + icon('send') + '</button><button class="btn small danger" data-delete-order="' + id + '" aria-label="Удалить ' + label + '" title="Удалить">' + icon('trash-2') + '</button></div>';
  }

  function bindOrderView(guest) {
    var type = guest ? 'guests' : 'orders';
    function applyOrderFilters() {
      if (guest) {
        state.guestFilters.search = qs('#guests-search').value.trim();
        state.guestFilters.page = 1;
        renderGuests();
      } else {
        if (qs('#orders-date-from').value && qs('#orders-date-to').value && qs('#orders-date-from').value > qs('#orders-date-to').value) {
          toast('Дата «с» не может быть позже даты «по»', 'bad');
          return;
        }
        state.orderFilters.search = qs('#orders-search').value.trim();
        state.orderFilters.status = qs('#orders-status').value;
        state.orderFilters.date_from = qs('#orders-date-from').value;
        state.orderFilters.date_to = qs('#orders-date-to').value;
        state.orderFilters.page = 1;
        renderOrders();
      }
    }
    qs('#' + type + '-apply').addEventListener('click', applyOrderFilters);
    qs('#' + type + '-search').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); applyOrderFilters(); }
    });
    var reset = qs('#' + type + '-reset');
    if (reset) reset.addEventListener('click', function () {
      if (guest) state.guestFilters = { search: '', page: 1 };
      else state.orderFilters = { search: '', status: '', date_from: '', date_to: '', page: 1 };
      guest ? renderGuests() : renderOrders();
    });
    qsa('[data-select]').forEach(function (el) {
      el.addEventListener('change', function () {
        var set = guest ? state.selectedGuests : state.selectedOrders;
        var id = Number(el.dataset.select);
        if (el.checked) set.add(id); else set.delete(id);
        guest ? renderGuests() : renderOrders();
      });
    });
    qsa('[data-status]').forEach(function (el) {
      el.addEventListener('change', async function () {
        var id = Number(el.dataset.status);
        try {
          if (guest) await api('bulk_status_guest', {}, { method: 'POST', body: { order_ids: [id], status: el.value } });
          else await api('order_status', {}, { method: 'POST', body: { order_id: id, status: el.value } });
          toast('Статус обновлен', 'ok');
          guest ? renderGuests() : renderOrders();
        } catch (err) { toast(err.message, 'bad'); }
      });
    });
    bindBulk(type, guest);
    qsa('[data-delete-order]').forEach(function (btn) { btn.addEventListener('click', function () { deleteOrder(Number(btn.dataset.deleteOrder)); }); });
    qsa('[data-delete-guest]').forEach(function (btn) { btn.addEventListener('click', function () { deleteGuests([Number(btn.dataset.deleteGuest)]); }); });
    qsa('[data-send]').forEach(function (btn) { btn.addEventListener('click', function () { sendOrder(Number(btn.dataset.send), btn.dataset.channel); }); });
    qsa('[data-note]').forEach(function (btn) { btn.addEventListener('click', function () { editOrderNote(Number(btn.dataset.note)); }); });
    qsa('[data-order-row]').forEach(function (row) {
      function openFromRow(event) {
        if (event.target.closest('button, a, input, select, textarea, label')) return;
        if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
        if (event.type === 'keydown') event.preventDefault();
        openOrderDetail(Number(row.dataset.orderRow), row.dataset.orderGuest === '1');
      }
      row.addEventListener('click', openFromRow);
      row.addEventListener('keydown', openFromRow);
    });
  }

  function orderDetailItems(items) {
    if (!items || !items.length) return '<div class="empty compact">Позиций нет</div>';
    return '<div class="detail-list">' + items.map(function (item) {
      var name = item.product_name || item.name || 'Товар';
      var qty = Number(item.qty || 1);
      var price = Number(item.price || item.unit_price || 0);
      return '<div class="detail-line"><div><strong>' + escapeHtml(name) + '</strong>' + (item.sku ? '<small>' + escapeHtml(item.sku) + '</small>' : '') + '</div><span>' + qty + ' шт.' + (price ? ' · ' + money(price) : '') + '</span></div>';
    }).join('') + '</div>';
  }

  function openOrderDetail(id, guest) {
    var list = guest ? state.guests : state.orders;
    var order = list.find(function (item) { return Number(item.id) === id; });
    if (!order) return;
    var num = (guest ? 'G-' : 'SH-') + String(id).padStart(5, '0');
    var clientName = order.name || order.user_name || 'Без имени';
    var clientPhone = phone(order.phone || order.user_phone);
    var body = '<div class="detail-editor"><section class="detail-summary"><div class="detail-kpi"><span>Сумма</span><strong>' + money(order.total) + '</strong></div><div class="detail-kpi"><span>Статус</span>' + statusBadge(order.status || 'new') + '</div><div class="detail-kpi"><span>Создан</span><strong>' + fmtDate(order.created_at) + '</strong></div></section>' +
      '<section class="panel"><div class="panel-head"><div><h3 class="panel-title">Клиент</h3><div class="panel-subtitle">Контактные данные заявки</div></div></div><div class="panel-body detail-grid">' + detailField('Имя', clientName) + detailField('Телефон', clientPhone) + detailField('Email', order.email || order.user_email) + detailField('Telegram', order.telegram) + detailField('Адрес', order.address || order.delivery_address, 'wide') + '</div></section>' +
      '<section class="panel"><div class="panel-head"><div><h3 class="panel-title">Состав</h3><div class="panel-subtitle">Все позиции без обрезания</div></div></div><div class="panel-body">' + orderDetailItems(order.items) + '</div></section>' +
      '<section class="panel"><div class="panel-head"><div><h3 class="panel-title">Обработка</h3><div class="panel-subtitle">Статус' + (guest ? '' : ' и внутренняя заметка') + '</div></div></div><div class="panel-body form-grid"><label class="field"><span>Статус</span>' + detailStatusControl(order.status || 'new', guest) + '</label>' + (guest ? '' : '<label class="field wide"><span>Заметка менеджера</span><textarea class="textarea" id="detail-order-note">' + escapeHtml(order.admin_note || '') + '</textarea></label>') + (order.comment ? '<div class="field wide"><span>Комментарий клиента</span><div class="detail-value">' + escapeHtml(order.comment) + '</div></div>' : '') + '</div></section></div>';
    openDrawer((guest ? 'Гостевая заявка: ' : 'Заказ: ') + num, body, '<button class="btn ghost" data-close-drawer>Закрыть</button><button class="btn primary" id="save-order-detail">' + icon('save') + '<span>Сохранить</span></button>');
    qs('#save-order-detail').addEventListener('click', async function () {
      try {
        var status = qs('#detail-order-status').value;
        if (guest) await api('bulk_status_guest', {}, { method: 'POST', body: { order_ids: [id], status: status } });
        else {
          await api('order_status', {}, { method: 'POST', body: { order_id: id, status: status } });
          await api('admin_note', {}, { method: 'POST', body: { order_id: id, note: qs('#detail-order-note').value } });
        }
        closeDrawer();
        toast(guest ? 'Гостевая заявка сохранена' : 'Заказ сохранен', 'ok');
        guest ? renderGuests() : renderOrders();
      } catch (err) { toast(err.message, 'bad'); }
    });
  }

  function detailStatusControl(value, guest) {
    var statuses = Object.keys(statusMap).filter(function (s) { return !guest || s !== 'shipped'; });
    return '<select class="select" id="detail-order-status">' + statuses.map(function (s) { return '<option value="' + s + '"' + (s === value ? ' selected' : '') + '>' + statusMap[s] + '</option>'; }).join('') + '</select>';
  }

  function detailField(label, value, cls) {
    return '<div class="field ' + (cls || '') + '"><span>' + escapeHtml(label) + '</span><div class="detail-value' + (!value ? ' muted' : '') + '">' + escapeHtml(value || 'Не указано') + '</div></div>';
  }

  function bindBulk(type, guest) {
    var apply = qs('#' + type + '-bulk-apply');
    var del = qs('#' + type + '-bulk-delete');
    if (!apply || !del) return;
    apply.addEventListener('click', async function () {
      var set = guest ? state.selectedGuests : state.selectedOrders;
      var ids = Array.from(set);
      if (!ids.length) return;
      var status = qs('#' + type + '-bulk-status').value;
      try {
        await api(guest ? 'bulk_status_guest' : 'bulk_status', {}, { method: 'POST', body: { order_ids: ids, status: status } });
        set.clear();
        toast('Статусы обновлены', 'ok');
        guest ? renderGuests() : renderOrders();
      } catch (err) { toast(err.message, 'bad'); }
    });
    del.addEventListener('click', function () {
      var set = guest ? state.selectedGuests : state.selectedOrders;
      var ids = Array.from(set);
      if (!ids.length || !confirm('Удалить выбранные записи?')) return;
      guest ? deleteGuests(ids) : deleteOrders(ids);
    });
  }

  async function deleteOrder(id) {
    if (!confirm('Удалить заказ SH-' + String(id).padStart(5, '0') + '?')) return;
    await deleteOrders([id]);
  }

  async function deleteOrders(ids) {
    try {
      await api(ids.length > 1 ? 'bulk_delete_orders' : 'delete_order', {}, { method: 'POST', body: ids.length > 1 ? { order_ids: ids } : { order_id: ids[0] } });
      ids.forEach(function (id) { state.selectedOrders.delete(id); });
      toast('Заказ удален', 'ok');
      renderOrders();
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function deleteGuests(ids) {
    if (!ids.length) return;
    if (!confirm('Удалить гостевые заявки?')) return;
    try {
      await api('bulk_delete_guest_orders', {}, { method: 'POST', body: { order_ids: ids } });
      ids.forEach(function (id) { state.selectedGuests.delete(id); });
      toast('Гостевые заявки удалены', 'ok');
      renderGuests();
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function sendOrder(id, channel) {
    try {
      await api('order_send', {}, { method: 'POST', body: { order_id: id, channel: channel || 'tg' } });
      toast('Заказ отправлен', 'ok');
    } catch (err) { toast(err.message, 'bad'); }
  }

  function editOrderNote(id) {
    var order = state.orders.find(function (o) { return Number(o.id) === id; });
    openDrawer('Заметка к заказу SH-' + String(id).padStart(5, '0'), [
      '<div class="panel"><div class="panel-body"><label class="field"><span>Заметка менеджера</span><textarea class="textarea" id="order-note">' + escapeHtml((order && order.admin_note) || '') + '</textarea></label></div></div>'
    ].join(''), [
      '<button class="btn ghost" data-close-drawer>Закрыть</button>',
      '<button class="btn primary" id="save-note">' + icon('save') + '<span>Сохранить</span></button>'
    ].join(''));
    qs('#save-note').addEventListener('click', async function () {
      try {
        await api('admin_note', {}, { method: 'POST', body: { order_id: id, note: qs('#order-note').value } });
        closeDrawer();
        toast('Заметка сохранена', 'ok');
        renderOrders();
      } catch (err) { toast(err.message, 'bad'); }
    });
  }

  async function renderGuests() {
    loading('Гости', 'Заявки с витрины без регистрации');
    try {
      var data = await api('guest_orders', state.guestFilters);
      state.guests = data.orders || [];
      setHeader('Гости', 'Отдельная очередь гостевых заявок');
      viewRoot().innerHTML = [
        orderToolbar('guests'),
        bulkBar('guests'),
        '<div class="panel"><div class="table-wrap">' + ordersTable(state.guests, true) + '</div>' + ordersCards(state.guests, true) + '</div>',
        pager(data.page || 1, data.total || 0, 50, 'guests')
      ].join('');
      bindOrderView(true);
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  async function renderClients() {
    loading('Клиенты', 'Регистрация, бонусы, роли и реквизиты');
    try {
      var data = await api('users');
      state.users = data.users || [];
      setHeader('Клиенты', 'Поиск, роли, реквизиты, пароль и push-сообщения');
      var list = filterUsers();
      viewRoot().innerHTML = [
        '<div class="toolbar"><div class="toolbar-left"><input class="input search" id="client-search" placeholder="Имя, телефон, email, компания, ИНН" value="' + escapeHtml(state.userSearch) + '"></div><div class="toolbar-right"><a class="btn ghost" href="' + API + '?action=export_xlsx">' + icon('file-down') + '<span>Экспорт</span></a></div></div>',
        '<div class="panel"><div class="table-wrap">' + clientsTable(list) + '</div>' + clientsCards(list) + '</div>'
      ].join('');
      qs('#client-search').addEventListener('input', function () {
        state.userSearch = this.value;
        renderClientsLocal();
      });
      bindClients();
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function filterUsers() {
    var q = state.userSearch.trim().toLowerCase();
    if (!q) return state.users;
    return state.users.filter(function (u) {
      return [u.name, u.phone, u.email, u.telegram, u.company_name, u.inn].some(function (v) {
        return String(v || '').toLowerCase().indexOf(q) >= 0;
      });
    });
  }

  function renderClientsLocal() {
    var list = filterUsers();
    var panel = qs('#view-root .panel');
    panel.innerHTML = '<div class="table-wrap">' + clientsTable(list) + '</div>' + clientsCards(list);
    bindClients();
    hydrateIcons();
  }

  function clientsTable(users) {
    if (!users.length) return '<div class="empty">Клиенты не найдены</div>';
    return '<table class="data-table"><thead><tr><th>Клиент</th><th>Роль</th><th>Компания</th><th>Бонусы</th><th>Заказы</th><th>Действия</th></tr></thead><tbody>' + users.map(clientRow).join('') + '</tbody></table>';
  }

  function clientRow(u) {
    var name = escapeHtml(u.name || String(u.id));
    return '<tr class="client-row" data-client-row="' + u.id + '" tabindex="0" aria-label="Открыть клиента ' + name + '"><td><b>' + name + '</b><div class="muted">' + escapeHtml(phone(u.phone)) + (u.email ? ' / ' + escapeHtml(u.email) : '') + (u.telegram ? ' / @' + escapeHtml(u.telegram) : '') + '</div></td><td>' + roleSelect(u) + '</td><td>' + escapeHtml(u.company_name || '') + '<div class="muted mono">' + escapeHtml(u.inn || '') + '</div></td><td><b>' + money(u.bonus_balance) + '</b></td><td>' + escapeHtml(u.order_count || 0) + '<div class="muted">' + money(u.total_spent) + '</div></td><td><div class="table-actions"><button class="btn small" data-client="' + u.id + '" aria-label="Открыть клиента ' + name + '" title="Открыть карточку">' + icon('panel-right-open') + '</button><button class="btn small danger" data-delete-user="' + u.id + '" aria-label="Удалить клиента ' + name + '" title="Удалить">' + icon('trash-2') + '</button></div></td></tr>';
  }

  function clientsCards(users) {
    if (!users.length) return '<div class="mobile-list"><div class="empty">Клиенты не найдены</div></div>';
    return '<div class="mobile-list">' + users.map(function (u) {
      var name = escapeHtml(u.name || String(u.id));
      return '<article class="mobile-item client-card" data-client-row="' + u.id + '" tabindex="0" aria-label="Открыть клиента ' + name + '"><div class="mobile-item-head"><div><div class="mobile-item-title">' + name + '</div><div class="mobile-item-meta">' + escapeHtml(phone(u.phone)) + (u.email ? ' · ' + escapeHtml(u.email) : '') + '</div></div><span class="status">' + escapeHtml(u.role) + '</span></div><div class="mobile-item-meta">' + escapeHtml(u.company_name || '') + '</div><b>' + money(u.bonus_balance) + '</b><div class="table-actions" style="margin-top:10px"><button class="btn small" data-client="' + u.id + '" aria-label="Открыть клиента ' + name + '" title="Открыть карточку">' + icon('panel-right-open') + '</button><button class="btn small danger" data-delete-user="' + u.id + '" aria-label="Удалить клиента ' + name + '" title="Удалить">' + icon('trash-2') + '</button></div></article>';
    }).join('') + '</div>';
  }

  function roleSelect(u) {
    return '<select class="select" data-role-user="' + u.id + '" aria-label="Роль ' + escapeHtml(u.name || String(u.id)) + '"><option value="client"' + (u.role === 'client' ? ' selected' : '') + '>Клиент</option><option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>Админ</option></select>';
  }

  function bindClients() {
    qsa('[data-role-user]').forEach(function (el) {
      el.addEventListener('change', async function () {
        try {
          await api('set_role', {}, { method: 'POST', body: { user_id: Number(el.dataset.roleUser), role: el.value } });
          toast('Роль обновлена', 'ok');
          renderClients();
        } catch (err) { toast(err.message, 'bad'); renderClients(); }
      });
    });
    qsa('[data-delete-user]').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        var id = Number(btn.dataset.deleteUser);
        if (!confirm('Удалить клиента и его заказы?')) return;
        try {
          await api('delete_user', {}, { method: 'POST', body: { user_id: id } });
          toast('Клиент удален', 'ok');
          renderClients();
        } catch (err) { toast(err.message, 'bad'); }
      });
    });
    qsa('[data-client]').forEach(function (btn) { btn.addEventListener('click', function () { openClient(Number(btn.dataset.client)); }); });
    qsa('[data-client-row]').forEach(function (row) {
      function openFromRow(event) {
        if (event.target.closest('button, a, input, select, textarea, label')) return;
        if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
        if (event.type === 'keydown') event.preventDefault();
        openClient(Number(row.dataset.clientRow));
      }
      row.addEventListener('click', openFromRow);
      row.addEventListener('keydown', openFromRow);
    });
  }

  async function openClient(id) {
    var u = state.users.find(function (x) { return Number(x.id) === id; });
    if (!u) return;
    openDrawer('Клиент: ' + u.name, clientDrawerHtml(u), [
      '<button class="btn ghost" data-close-drawer>Закрыть</button>',
      '<button class="btn primary" id="save-client">' + icon('save') + '<span>Сохранить</span></button>'
    ].join(''));
    qs('#save-client').addEventListener('click', async function () {
      var body = collectForm(qs('#client-form'));
      body.user_id = id;
      try {
        await api('edit_user', {}, { method: 'POST', body: body });
        toast('Клиент сохранен', 'ok');
        closeDrawer();
        renderClients();
      } catch (err) { toast(err.message, 'bad'); }
    });
    qs('#client-pass-btn').addEventListener('click', async function () {
      var pass = qs('#client-pass').value;
      if (!pass || pass.length < 8) return toast('Пароль минимум 8 символов', 'bad');
      try {
        await api('change_password', {}, { method: 'POST', body: { user_id: id, new_password: pass } });
        qs('#client-pass').value = '';
        toast('Пароль изменен', 'ok');
      } catch (err) { toast(err.message, 'bad'); }
    });
    qs('#client-bonus-btn').addEventListener('click', async function () {
      var amount = Number(qs('#client-bonus').value || 0);
      if (!Number.isFinite(amount) || amount === 0) return toast('Укажите ненулевую сумму корректировки', 'bad');
      try {
        await api('bonus_adjust', {}, { method: 'POST', body: { user_id: id, amount: amount, description: qs('#client-bonus-desc').value.trim() || 'Ручная корректировка' } });
        toast('Бонусы обновлены', 'ok');
        renderClients();
      } catch (err) { toast(err.message, 'bad'); }
    });
    qs('#client-push-btn').addEventListener('click', async function () {
      var message = qs('#client-push').value.trim();
      if (!message) return toast('Введите текст push-сообщения', 'bad');
      try {
        await api('push_manager_message', {}, { method: 'POST', body: { user_id: id, body: message } });
        toast('Push отправлен', 'ok');
      } catch (err) { toast(err.message, 'bad'); }
    });
  }

  function clientDrawerHtml(u) {
    return '<div class="client-editor"><form id="client-form" class="panel"><div class="panel-body form-grid">' +
      field('name', 'Имя', u.name) + field('phone', 'Телефон', u.phone) + field('email', 'Email', u.email) + field('telegram', 'Telegram', u.telegram) +
      field('company_name', 'Компания', u.company_name) + field('inn', 'ИНН', u.inn) + field('kpp', 'КПП', u.kpp) +
      field('legal_address', 'Юр. адрес', u.legal_address, 'wide') + '</div></form>' +
      '<div class="panel"><div class="panel-head"><h3 class="panel-title">Доступ и бонусы</h3></div><div class="panel-body form-grid">' +
      '<label class="field"><span>Новый пароль</span><input class="input" id="client-pass" type="password" minlength="8" autocomplete="new-password"><small class="field-hint">Не менее 8 символов</small></label><div class="field"><span>&nbsp;</span><button class="btn" id="client-pass-btn" type="button">' + icon('key-round') + '<span>Сменить</span></button></div>' +
      '<label class="field"><span>Корректировка бонусов</span><input class="input" id="client-bonus" type="number" placeholder="Напр. 500 или -200"></label><label class="field"><span>Комментарий</span><input class="input" id="client-bonus-desc"></label><div class="field"><span>&nbsp;</span><button class="btn" id="client-bonus-btn" type="button">' + icon('badge-russian-ruble') + '<span>Применить</span></button></div>' +
      '<label class="field wide"><span>Push от менеджера</span><textarea class="textarea" id="client-push"></textarea></label><div class="field"><span>&nbsp;</span><button class="btn" id="client-push-btn" type="button">' + icon('send') + '<span>Отправить</span></button></div>' +
      '</div></div></div>';
  }

  function field(name, label, value, cls) {
    return '<label class="field ' + (cls || '') + '"><span>' + label + '</span><input class="input" name="' + name + '" value="' + escapeHtml(value || '') + '"></label>';
  }

  function collectForm(form) {
    var out = {};
    new FormData(form).forEach(function (value, key) { out[key] = value; });
    return out;
  }

  async function renderPromo() {
    loading('Промо', 'Ретробонусы и правила начислений');
    try {
      var data = await api('promo_list');
      var rules = data.rules || [];
      setHeader('Промо', 'Настройка бонусов по группам и сумме');
      viewRoot().innerHTML = '<section class="split-grid"><div class="panel"><div class="panel-head"><h2 class="panel-title">Правила</h2></div><div class="panel-body">' + promoTable(rules) + '</div></div><div class="panel"><div class="panel-head"><h2 class="panel-title">Новое правило</h2></div><div class="panel-body">' + promoForm() + '</div></div></section>';
      bindPromo();
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function promoTable(rules) {
    if (!rules.length) return '<div class="empty">Правил пока нет</div>';
    return '<div class="mobile-list" style="display:grid">' + rules.map(function (r) {
      var name = escapeHtml(r.name || String(r.id));
      return '<div class="mobile-item"><div class="mobile-item-head"><div><div class="mobile-item-title">' + name + '</div><div class="mobile-item-meta">' + escapeHtml(r.product_group || 'Все группы') + ' / от ' + money(r.min_order) + '</div></div><span class="status ' + (Number(r.active) ? 'confirmed' : 'hidden') + '">' + (Number(r.active) ? 'Активно' : 'Выкл') + '</span></div><b>' + escapeHtml(r.bonus_percent) + '%</b><div class="table-actions" style="margin-top:10px"><button class="btn small" data-promo-toggle="' + r.id + '" data-active="' + (Number(r.active) ? 0 : 1) + '" aria-label="' + (Number(r.active) ? 'Выключить ' : 'Включить ') + name + '" title="Изменить активность">' + icon('power') + '</button><button class="btn small danger" data-promo-delete="' + r.id + '" aria-label="Удалить ' + name + '" title="Удалить">' + icon('trash-2') + '</button></div></div>';
    }).join('') + '</div>';
  }

  function promoForm() {
    return '<form id="promo-form" class="form-grid"><label class="field wide"><span>Название</span><input class="input" name="name" required></label><label class="field"><span>Процент</span><input class="input" name="bonus_percent" type="number" min="0.1" max="100" step="0.1" value="3" required></label><label class="field"><span>Группа</span><select class="select" name="product_group"><option value="">Все</option>' + Object.keys(groupLabels).map(function (g) { return '<option value="' + g + '">' + groupLabels[g] + '</option>'; }).join('') + '</select></label><label class="field"><span>Мин. заказ</span><input class="input" name="min_order" type="number" min="0" value="0" required></label><label class="field"><span>Активно</span><select class="select" name="active"><option value="1">Да</option><option value="0">Нет</option></select></label><div class="wide"><button class="btn primary" type="submit">' + icon('plus') + '<span>Создать</span></button></div></form>';
  }

  function bindPromo() {
    qs('#promo-form').addEventListener('submit', async function (event) {
      event.preventDefault();
      try {
        await api('promo_create', {}, { method: 'POST', body: collectForm(event.currentTarget) });
        toast('Правило создано', 'ok');
        renderPromo();
      } catch (err) { toast(err.message, 'bad'); }
    });
    qsa('[data-promo-toggle]').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        try {
          await api('promo_toggle', {}, { method: 'POST', body: { id: Number(btn.dataset.promoToggle), active: Number(btn.dataset.active) } });
          toast(Number(btn.dataset.active) ? 'Правило включено' : 'Правило выключено', 'ok');
          renderPromo();
        } catch (err) { toast(err.message, 'bad'); }
      });
    });
    qsa('[data-promo-delete]').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        if (!confirm('Удалить правило?')) return;
        try {
          await api('promo_delete', {}, { method: 'POST', body: { id: Number(btn.dataset.promoDelete) } });
          toast('Правило удалено', 'ok');
          renderPromo();
        } catch (err) { toast(err.message, 'bad'); }
      });
    });
  }

  async function renderNotifications() {
    loading('Уведомления', 'Push-кампании и сообщения менеджера');
    try {
      var log = await api('push_log').catch(function () { return { campaigns: [] }; });
      setHeader('Уведомления', 'Мобильные push и служебные отправки', '<button class="btn accent" id="send-report-top" aria-label="Отчет в Telegram">' + icon('send') + '<span>TG отчет</span></button>');
      viewRoot().innerHTML = '<section class="split-grid"><div class="panel"><div class="panel-head"><h2 class="panel-title">Промо push</h2></div><div class="panel-body">' + pushForm() + '</div></div><div class="panel"><div class="panel-head"><h2 class="panel-title">Журнал</h2></div><div class="panel-body">' + pushLog(log.campaigns || []) + '</div></div></section>';
      qs('#send-report-top').addEventListener('click', sendReport);
      qs('#push-form').addEventListener('submit', async function (event) {
        event.preventDefault();
        try {
          await api('push_promotion', {}, { method: 'POST', body: collectForm(event.currentTarget) });
          toast('Push отправлен', 'ok');
          renderNotifications();
        } catch (err) { toast(err.message, 'bad'); }
      });
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function pushForm() {
    return '<form id="push-form" class="form-grid"><label class="field wide"><span>Заголовок</span><input class="input" name="title" required></label><label class="field wide"><span>Текст</span><textarea class="textarea" name="body" required></textarea></label><label class="field"><span>Категория</span><input class="input" name="category" placeholder="Напр. inv"></label><div class="wide"><button class="btn primary" type="submit">' + icon('bell-ring') + '<span>Отправить всем</span></button></div></form>';
  }

  function pushLog(rows) {
    if (!rows.length) return '<div class="empty">Журнал пока пуст</div>';
    return '<div class="mobile-list" style="display:grid">' + rows.map(function (r) {
      return '<div class="mobile-item"><div class="mobile-item-title">' + escapeHtml(r.title || r.type) + '</div><div class="mobile-item-meta">' + fmtDate(r.created_at) + '</div><p>' + escapeHtml(r.body || '') + '</p></div>';
    }).join('') + '</div>';
  }

  async function renderAnalytics() {
    loading('Аналитика', 'Заказы, статусы и товарные лидеры');
    try {
      var data = await api('analytics', { days: 30 });
      setHeader('Аналитика', 'Последние 30 дней');
      viewRoot().innerHTML = '<section class="split-grid"><div class="panel"><div class="panel-head"><h2 class="panel-title">Динамика</h2></div><div class="panel-body chart-box"><canvas id="daily-chart"></canvas></div></div><div class="panel"><div class="panel-head"><h2 class="panel-title">Статусы</h2></div><div class="panel-body">' + statusStats(data.by_status || []) + '</div></div></section><section class="panel"><div class="panel-head"><h2 class="panel-title">Топ товаров</h2></div><div class="panel-body">' + topProductsMini(data.top_products || []) + '</div></section>';
      drawDailyChart(data.daily || []);
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function statusStats(rows) {
    if (!rows.length) return '<div class="empty">Нет данных</div>';
    var max = Math.max.apply(null, rows.map(function (r) { return Number(r.cnt || 0); }));
    return '<div class="stat-line">' + rows.map(function (r) {
      var pct = max ? Math.round(Number(r.cnt || 0) / max * 100) : 0;
      return '<div class="stat-line-row"><span>' + escapeHtml(statusMap[r.status] || r.status) + '</span><div class="bar"><span style="width:' + pct + '%"></span></div><b>' + escapeHtml(r.cnt) + '</b></div>';
    }).join('') + '</div>';
  }

  function drawDailyChart(rows) {
    if (!window.Chart || !qs('#daily-chart')) return;
    if (state.charts.daily) state.charts.daily.destroy();
    state.charts.daily = new Chart(qs('#daily-chart'), {
      type: 'line',
      data: {
        labels: rows.map(function (r) { return r.day; }),
        datasets: [
          { label: 'Заказы', data: rows.map(function (r) { return Number(r.cnt || 0); }), borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.12)', tension: .35, fill: true },
          { label: 'Выручка', data: rows.map(function (r) { return Math.round(Number(r.rev || 0) / 1000); }), borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,.12)', tension: .35, fill: true }
        ]
      },
      options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }
    });
  }

  async function renderVisitors() {
    loading('Посетители', 'Собственный трекинг визитов без смешивания с клиентами');
    try {
      var data = await api('visitors_list', { page: state.visitorPage });
      var rows = data.visitors || [];
      setHeader('Посетители', 'Источник, устройство, привязанные контакты');
      viewRoot().innerHTML = '<div class="panel"><div class="table-wrap">' + visitorsTable(rows) + '</div>' + visitorsCards(rows) + '</div>' + pager(data.page || 1, data.total || 0, VISITOR_PAGE_SIZE, 'visitors');
        bindVisitorRows(rows);
        bindPager();
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function visitorsTable(rows) {
    if (!rows.length) return '<div class="empty">Посетителей пока нет</div>';
    return '<table class="data-table"><thead><tr><th>VID</th><th>Первый/последний</th><th>Визиты</th><th>Источник</th><th>Устройство</th><th>Контакт</th></tr></thead><tbody>' + rows.map(function (v) {
        return '<tr class="visitor-row" data-visitor-row="' + escapeHtml(v.vid) + '" tabindex="0" aria-label="Открыть посетителя ' + escapeHtml(v.vid) + '"><td class="mono">' + escapeHtml(v.vid) + '</td><td>' + fmtDate(v.first_seen) + '<div class="muted">' + fmtDate(v.last_seen) + '</div></td><td>' + escapeHtml(v.visits_count) + '</td><td>' + escapeHtml(v.first_utm_source || v.first_referrer || '') + '</td><td>' + escapeHtml(v.device || '') + '<div class="muted">' + escapeHtml(v.last_ip || '') + '</div></td><td>' + escapeHtml(v.linked_name || '') + '<div class="muted">' + escapeHtml(v.linked_phone || '') + '</div></td></tr>';
    }).join('') + '</tbody></table>';
  }

  function visitorsCards(rows) {
    if (!rows.length) return '<div class="mobile-list"><div class="empty">Посетителей пока нет</div></div>';
    return '<div class="mobile-list">' + rows.map(function (v) {
        return '<article class="mobile-item visitor-card" data-visitor-row="' + escapeHtml(v.vid) + '" tabindex="0" aria-label="Открыть посетителя ' + escapeHtml(v.vid) + '"><div class="mobile-item-title mono">' + escapeHtml(v.vid) + '</div><div class="mobile-item-meta">' + fmtDate(v.last_seen) + ' / визитов: ' + escapeHtml(v.visits_count) + '</div><div>' + escapeHtml(v.first_utm_source || v.first_referrer || '') + '</div><div class="mobile-item-meta">' + escapeHtml(v.device || '') + ' ' + escapeHtml(v.last_ip || '') + '</div></article>';
    }).join('') + '</div>';
  }

  function bindVisitorRows(rows) {
    qsa('[data-visitor-row]').forEach(function (row) {
      function openFromRow(event) {
        if (event.target.closest('button, a, input, select, textarea, label')) return;
        if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== ' ') return;
        if (event.type === 'keydown') event.preventDefault();
        var visitor = rows.find(function (item) { return String(item.vid) === row.dataset.visitorRow; });
        if (visitor) showVisitorDetail(visitor);
      }
      row.addEventListener('click', openFromRow);
      row.addEventListener('keydown', openFromRow);
    });
  }

  function showVisitorDetail(visitor) {
    var source = visitor.first_utm_source || visitor.first_referrer || 'Прямой переход';
    var body = '<div class="detail-editor"><section class="detail-summary"><div class="detail-kpi"><span>Визитов</span><strong>' + escapeHtml(visitor.visits_count || 0) + '</strong></div><div class="detail-kpi"><span>Первый визит</span><strong>' + fmtDate(visitor.first_seen) + '</strong></div><div class="detail-kpi"><span>Последний визит</span><strong>' + fmtDate(visitor.last_seen) + '</strong></div></section>' +
      '<section class="panel"><div class="panel-head"><div><h3 class="panel-title">Источник и устройство</h3><div class="panel-subtitle">Откуда пришёл посетитель и с чего заходил</div></div></div><div class="panel-body detail-grid">' + detailField('Источник', source, 'wide') + detailField('UTM medium', visitor.first_utm_medium) + detailField('UTM campaign', visitor.first_utm_campaign) + detailField('Устройство', visitor.device) + detailField('Последний IP', visitor.last_ip) + detailField('Первый referrer', visitor.first_referrer, 'wide') + '</div></section>' +
      '<section class="panel"><div class="panel-head"><div><h3 class="panel-title">Привязанный контакт</h3><div class="panel-subtitle">Данные появятся после идентификации посетителя</div></div></div><div class="panel-body detail-grid">' + detailField('Имя', visitor.linked_name) + detailField('Телефон', visitor.linked_phone) + detailField('Заказ', visitor.linked_order_id ? String(visitor.linked_order_id) : '') + detailField('VID', visitor.vid, 'wide mono') + '</div></section></div>';
    openDrawer('Посетитель', body, '<button class="btn primary" data-close-drawer>Готово</button>');
  }

  async function loadPriceProducts() {
    var data = await api('products_list', { limit: 500, page: 1, status: 'active' });
    state.priceProducts = data.products || [];
    window.PRODUCTS = state.priceProducts.slice();
    return state.priceProducts;
  }

  async function renderCatalog() {
    loading('Прайс', 'Файлы для клиентов и менеджеров');
    try {
      await loadPriceProducts();
      setHeader('Прайс', 'Excel/PDF, отправка в Telegram или email');
      viewRoot().innerHTML = [
        '<section class="quick-grid">',
        '<button class="btn quick-action" id="price-xlsx">' + icon('file-spreadsheet') + '<strong>Скачать Excel</strong><span>Генератор с текущими товарами</span></button>',
        '<button class="btn quick-action" id="price-pdf">' + icon('file-text') + '<strong>Скачать PDF</strong><span>Печатный прайс</span></button>',
        '<button class="btn quick-action" id="price-csv">' + icon('download') + '<strong>CSV товаров</strong><span>Быстрый рабочий экспорт</span></button>',
        '</section>',
        '<section class="panel"><div class="panel-head"><div><h2 class="panel-title">Отправка прайса</h2><div class="panel-subtitle">Сгенерируем файл и передадим через сервер</div></div></div><div class="panel-body form-grid"><button class="btn primary" id="send-xlsx-tg">' + icon('send') + '<span>Excel в TG</span></button><button class="btn ghost" id="send-xlsx-email">' + icon('mail') + '<span>Excel на email</span></button><button class="btn ghost" id="send-pdf-tg">' + icon('send') + '<span>PDF в TG</span></button></div></section>'
      ].join('');
      qs('#price-xlsx').addEventListener('click', function () { runPriceGenerator('xlsx'); });
      qs('#price-pdf').addEventListener('click', function () { runPriceGenerator('pdf'); });
      qs('#price-csv').addEventListener('click', downloadProductsCsv);
      qs('#send-xlsx-tg').addEventListener('click', function () { sendGeneratedPrice('xlsx', 'tg'); });
      qs('#send-xlsx-email').addEventListener('click', function () { sendGeneratedPrice('xlsx', 'email'); });
      qs('#send-pdf-tg').addEventListener('click', function () { sendGeneratedPrice('pdf', 'tg'); });
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function runPriceGenerator(type) {
    try {
      if (type === 'xlsx' && typeof window.downloadPriceExcel === 'function') { toast('Формируем Excel…', 'ok'); window.downloadPriceExcel(); return true; }
      if (type === 'pdf' && typeof window.downloadPricePDF === 'function') { toast('Формируем PDF…', 'ok'); window.downloadPricePDF(); return true; }
    } catch (err) {
      toast(err.message || 'Не удалось сформировать прайс', 'bad');
      return false;
    }

    toast('Генератор прайса еще загружается', 'bad');
    return false;
  }

  function blobToBase64(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(String(reader.result).split(',')[1] || ''); };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  function sendGeneratedPrice(type, channel) {
    window._adminPriceCallback = async function (blob, filename) {
      try {
        var b64 = await blobToBase64(blob);
        await api('send_pricelist', {}, { method: 'POST', body: { data: b64, filename: filename, channel: channel } });
        toast('Прайс отправлен', 'ok');
      } catch (err) {
        toast(err.message, 'bad');
      } finally {
        window._adminPriceCallback = null;
        var progressModal = document.getElementById('priceProgressModal');
        if (progressModal) progressModal.remove();
      }
    };
    if (!runPriceGenerator(type)) window._adminPriceCallback = null;
  }

  function downloadProductsCsv() {
    var rows = [['sku','brand','series','model','group','btu','area','price','stock','active']];
    var products = state.priceProducts.length ? state.priceProducts : state.products;
    products.forEach(function (p) {
      rows.push([p.sku, p.brand, p.series, p.model, p.group, p.btu, p.area, p.price, p.stock, p._active]);
    });
    var csv = rows.map(function (r) { return r.map(function (v) { return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'; }).join(';'); }).join('\r\n');
    var blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'splithub-products-' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(a);
    a.click();
    toast('CSV сформирован', 'ok');
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 1000);
  }

  async function renderProducts() {
      loading('Товары', 'Каталог, цены, доступность и карточки');
    try {
      var data = await api('products_list', Object.assign({ limit: PRODUCT_PAGE_SIZE }, state.productFilters));
      state.products = data.products || [];
      state.productsTotal = data.total || state.products.length;
      state.productSummary = data.summary || state.productSummary;
      window.PRODUCTS = state.products.filter(function (p) { return Number(p._active == null ? 1 : p._active) === 1; });
      setHeader('Товары', 'Каталог, цены, доступность и карточки', '<button class="btn primary" id="new-product" aria-label="Новый товар">' + icon('plus') + '<span>Новый товар</span></button>');
      viewRoot().innerHTML = [
        productsSummary(state.productSummary),
        productsToolbar(),
        productsBulkBar(),
        '<div class="panel catalog-list-panel"><div class="catalog-list-head"><div><h2 class="panel-title">Каталог</h2><div class="panel-subtitle">' + state.productsTotal + ' позиций</div></div><div class="catalog-list-mark">' + icon('sparkles') + '</div></div><div class="table-wrap">' + productsTable(state.products) + '</div>' + productsCards(state.products) + '</div>',
        pager(data.page || state.productFilters.page || 1, state.productsTotal, PRODUCT_PAGE_SIZE, 'products')
      ].join('');
      bindProducts();
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function productsToolbar() {
    var f = state.productFilters;
    return '<section class="catalog-tools"><div class="catalog-search"><span class="catalog-search-icon">' + icon('search') + '</span><input class="input" id="product-search" placeholder="SKU, модель, бренд, серия" value="' + escapeHtml(f.search || '') + '" aria-label="Поиск товара"></div><div class="catalog-selects"><select class="select" id="product-group" aria-label="Группа"><option value="">Все группы</option>' + Object.keys(groupLabels).map(function (g) { return '<option value="' + g + '"' + (f.group === g ? ' selected' : '') + '>' + groupLabels[g] + '</option>'; }).join('') + '</select><select class="select" id="product-status" aria-label="Статус"><option value="all"' + (f.status === 'all' ? ' selected' : '') + '>Все статусы</option><option value="active"' + (f.status === 'active' ? ' selected' : '') + '>Видимые</option><option value="hidden"' + (f.status === 'hidden' ? ' selected' : '') + '>Скрытые</option></select></div><div class="catalog-tools-actions"><button class="icon-btn catalog-reset" id="product-reset" title="Сбросить фильтры" aria-label="Сбросить фильтры">' + icon('rotate-ccw') + '</button><button class="btn primary" id="product-apply">' + icon('search') + '<span>Показать</span></button></div></section>';
  }

  function productsSummary(summary) {
    summary = summary || {};
    var total = Number(summary.total || 0);
    var active = Number(summary.active || 0);
    var hidden = Number(summary.hidden || 0);
    var custom = Number(summary.custom || 0);
    return '<section class="catalog-summary">' +
      '<button class="catalog-stat active" data-product-status-filter="all"><span>' + icon('layers-3') + '</span><b>' + total + '</b><small>Всего</small></button>' +
      '<button class="catalog-stat cyan" data-product-status-filter="active"><span>' + icon('eye') + '</span><b>' + active + '</b><small>Видимые</small></button>' +
      '<button class="catalog-stat muted-stat" data-product-status-filter="hidden"><span>' + icon('eye-off') + '</span><b>' + hidden + '</b><small>Скрытые</small></button>' +
      '<div class="catalog-stat mint"><span>' + icon('sparkles') + '</span><b>' + custom + '</b><small>Свои</small></div>' +
      '</section>';
  }

  function productsBulkBar() {
    var count = state.selectedProducts.size;
    return '<div class="bulkbar ' + (count ? 'on' : '') + '" id="products-bulk"><strong>Выбрано: ' + count + '</strong><div class="toolbar-right"><button class="btn ok" id="products-show">' + icon('eye') + '<span>Показать</span></button><button class="btn danger" id="products-hide">' + icon('eye-off') + '<span>Скрыть</span></button></div></div>';
  }

  function productsTable(products) {
    if (!products.length) return '<div class="empty">Товары не найдены</div>';
    return '<table class="data-table product-table"><thead><tr><th></th><th>Товар</th><th>Группа</th><th>BTU/м²</th><th>Цена</th><th>Наличие</th><th>Статус</th><th></th></tr></thead><tbody>' + products.map(productRow).join('') + '</tbody></table>';
  }

  function productRow(p) {
    var active = Number(p._active == null ? 1 : p._active) === 1;
    var checked = state.selectedProducts.has(p.sku) ? ' checked' : '';
    return '<tr class="product-row" data-open-product="' + escapeHtml(p.sku) + '" tabindex="0" role="button" aria-label="Открыть товар ' + escapeHtml(p.model) + '"><td><input type="checkbox" data-product-select="' + escapeHtml(p.sku) + '"' + checked + ' aria-label="Выбрать товар ' + escapeHtml(p.model) + '"></td><td><div class="product-cell">' + productImg(p.photo, p.model) + '<div><div class="product-name">' + escapeHtml(p.model) + '</div><div class="product-meta mono">' + escapeHtml(p.sku) + '</div><div class="product-meta">' + escapeHtml(p.brand || '') + ' · ' + escapeHtml(p.series || '') + '</div></div></div></td><td>' + escapeHtml(groupLabels[p.group] || p.group || '') + '</td><td>' + escapeHtml(p.btu || '') + '<div class="muted">' + escapeHtml(p.area || '') + ' м²</div></td><td><b>' + money(p.price) + '</b></td><td>' + escapeHtml(stockLabels[p.stock] || p.stock || '') + '</td><td><button class="btn small ' + (active ? 'ok' : 'danger') + '" data-toggle-product="' + escapeHtml(p.sku) + '" data-active="' + (active ? 0 : 1) + '">' + (active ? icon('eye') : icon('eye-off')) + '<span>' + (active ? 'Виден' : 'Скрыт') + '</span></button></td><td><div class="table-actions"><button class="icon-btn product-edit-btn" data-edit-product="' + escapeHtml(p.sku) + '" title="Редактировать" aria-label="Редактировать ' + escapeHtml(p.model) + '">' + icon('pencil') + '</button>' + (p._is_custom ? '<button class="icon-btn product-edit-btn danger" data-delete-product="' + escapeHtml(p.sku) + '" title="Удалить" aria-label="Удалить ' + escapeHtml(p.model) + '">' + icon('trash-2') + '</button>' : '') + '</div></td></tr>';
  }

  function productsCards(products) {
    if (!products.length) return '<div class="mobile-list"><div class="empty">Товары не найдены</div></div>';
    return '<div class="mobile-list">' + products.map(function (p) {
      var active = Number(p._active == null ? 1 : p._active) === 1;
      return '<article class="mobile-item product-card" data-open-product="' + escapeHtml(p.sku) + '" tabindex="0" role="button" aria-label="Открыть товар ' + escapeHtml(p.model) + '"><div class="product-cell">' + productImg(p.photo, p.model) + '<div><div class="product-name">' + escapeHtml(p.model) + '</div><div class="product-meta mono">' + escapeHtml(p.sku) + '</div><div class="product-meta">' + money(p.price) + ' · ' + escapeHtml(stockLabels[p.stock] || p.stock || '') + '</div></div></div><div class="table-actions" style="margin-top:10px"><label class="tag"><input type="checkbox" data-product-select="' + escapeHtml(p.sku) + '"' + (state.selectedProducts.has(p.sku) ? ' checked' : '') + '> Выбрать</label><button class="btn small ' + (active ? 'ok' : 'danger') + '" data-toggle-product="' + escapeHtml(p.sku) + '" data-active="' + (active ? 0 : 1) + '" aria-label="' + (active ? 'Скрыть ' : 'Показать ') + escapeHtml(p.model) + '">' + (active ? icon('eye') : icon('eye-off')) + '</button><button class="icon-btn product-edit-btn" data-edit-product="' + escapeHtml(p.sku) + '" title="Редактировать" aria-label="Редактировать ' + escapeHtml(p.model) + '">' + icon('pencil') + '</button></div></article>';
    }).join('') + '</div>';
  }

  function bindProducts() {
    qs('#new-product').addEventListener('click', function () { openProductEditor(newCustomProduct(), true); });
    function applyProductFilters() {
      state.productFilters.search = qs('#product-search').value.trim();
      state.productFilters.group = qs('#product-group').value;
      state.productFilters.status = qs('#product-status').value;
      state.productFilters.page = 1;
      renderProducts();
    }
    qs('#product-apply').addEventListener('click', applyProductFilters);
    qs('#product-search').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        applyProductFilters();
      }
    });
    qs('#product-reset').addEventListener('click', function () {
      state.productFilters = { search: '', group: '', status: 'all', page: 1 };
      renderProducts();
    });
    qsa('[data-product-status-filter]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.productFilters.search = '';
        state.productFilters.group = '';
        state.productFilters.status = btn.dataset.productStatusFilter;
        state.productFilters.page = 1;
        renderProducts();
      });
    });
    qsa('[data-product-select]').forEach(function (el) {
      el.addEventListener('change', function () {
        var sku = el.dataset.productSelect;
        if (el.checked) state.selectedProducts.add(sku); else state.selectedProducts.delete(sku);
        renderProducts();
      });
    });
    qsa('[data-toggle-product]').forEach(function (btn) {
      btn.addEventListener('click', function () { toggleProduct(btn.dataset.toggleProduct, Number(btn.dataset.active)); });
    });
    qsa('[data-edit-product]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openProductFromSku(btn.dataset.editProduct);
      });
    });
    qsa('[data-delete-product]').forEach(function (btn) {
      btn.addEventListener('click', function () { deleteCustomProduct(btn.dataset.deleteProduct); });
    });
    qs('#products-show').addEventListener('click', function () { bulkToggleProducts(1); });
    qs('#products-hide').addEventListener('click', function () { bulkToggleProducts(0); });
    qsa('[data-open-product]').forEach(function (item) {
      item.addEventListener('click', function (event) {
        if (event.target.closest('button, input, label, a, select, textarea')) return;
        openProductFromSku(item.dataset.openProduct);
      });
      item.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        openProductFromSku(item.dataset.openProduct);
      });
    });
  }

  function openProductFromSku(sku) {
    var product = state.products.find(function (p) { return String(p.sku) === String(sku); });
    if (product) openProductEditor(product, !!product._is_custom);
  }

  async function toggleProduct(sku, active) {
    try {
      await api('product_toggle_active', {}, { method: 'POST', body: { sku: sku, active: active } });
      toast(active ? 'Товар показан' : 'Товар скрыт', 'ok');
      renderProducts();
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function bulkToggleProducts(active) {
    var skus = Array.from(state.selectedProducts);
    if (!skus.length) return;
    try {
      await api('product_bulk_toggle_active', {}, { method: 'POST', body: { skus: skus, active: active } });
      state.selectedProducts.clear();
      toast('Товары обновлены', 'ok');
      renderProducts();
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function deleteCustomProduct(sku) {
    if (!confirm('Удалить кастомный товар?')) return;
    try {
      await api('custom_product_delete', {}, { method: 'POST', body: { sku: sku } });
      toast('Товар удален', 'ok');
      renderProducts();
    } catch (err) { toast(err.message, 'bad'); }
  }

  function newCustomProduct() {
    return {
      id: '',
      sku: '',
      brandCode: 'custom',
      brand: '',
      series: '',
      model: '',
      group: 'inv',
      type: 'split',
      factory: '',
      color: 'white',
      btu: '09',
      area: 25,
      price: 0,
      stock: 'in_stock',
      stockLabel: 'В наличии',
      descShort: '',
      cardBenef: '',
      benefits: [],
      compressor: '',
      freon: 'R32',
      photo: '',
      photos: [],
      active: 1,
      _active: 1,
      _is_custom: true
    };
  }

  function openProductEditor(product, isCustom) {
    state.editorProduct = JSON.parse(JSON.stringify(product));
    state.editorProduct.active = Number(product._active == null ? product.active || 1 : product._active);
    state.editorProduct.photos = Array.isArray(product.photos) ? product.photos.slice(0, 12) : (product.photo ? [product.photo] : []);
    state.editorTab = 'main';
    renderProductEditor(isCustom);
  }

  function renderProductEditor(isCustom) {
    var p = state.editorProduct;
    openDrawer((isCustom ? 'Новый товар' : 'Редактор товара') + (p.model ? ': ' + p.model : ''), productEditorHtml(p, isCustom), productEditorFooter(isCustom));
    bindProductEditor(isCustom);
  }

  function productEditorHtml(p, isCustom) {
    return '<div class="product-editor"><div class="tabs">' +
      tab('main', 'Главное', 'sliders-horizontal') + tab('media', 'Фото', 'images') + tab('text', 'Описание', 'file-text') + tab('tech', 'Характеристики', 'settings-2') +
      '</div><div id="product-editor-body">' + productEditorTabHtml(p, isCustom) + '</div></div>';
  }

  function productEditorFooter(isCustom) {
    return '<button class="btn ghost" data-close-drawer>Закрыть</button><div class="toolbar-right">' +
      (!isCustom ? '<button class="btn danger" id="reset-product">' + icon('rotate-ccw') + '<span>Сбросить</span></button>' : '') +
      '<button class="btn primary" id="save-product">' + icon('save') + '<span>Сохранить</span></button></div>';
  }

  function tab(key, label, ico) {
    return '<button class="tab-btn ' + (state.editorTab === key ? 'active' : '') + '" data-editor-tab="' + key + '">' + icon(ico) + '<span>' + label + '</span></button>';
  }

  function productEditorTabHtml(p, isCustom) {
    if (state.editorTab === 'media') return productMediaTab(p);
    if (state.editorTab === 'text') return productTextTab(p);
    if (state.editorTab === 'tech') return productTechTab(p);
    return productMainTab(p, isCustom);
  }

  function productMainTab(p, isCustom) {
    return '<div class="panel"><div class="panel-body form-grid">' +
      '<label class="field"><span>SKU</span><input class="input" id="pe-sku" value="' + escapeHtml(p.sku || '') + '"' + (!isCustom ? ' disabled' : '') + '></label>' +
      '<label class="field"><span>ID</span><input class="input" id="pe-id" value="' + escapeHtml(p.id || '') + '"' + (!isCustom ? ' disabled' : '') + '></label>' +
      '<label class="field"><span>Бренд</span><input class="input" id="pe-brand" value="' + escapeHtml(p.brand || '') + '"></label>' +
      '<label class="field"><span>Серия</span><input class="input" id="pe-series" value="' + escapeHtml(p.series || '') + '"></label>' +
      '<label class="field wide"><span>Модель</span><input class="input" id="pe-model" value="' + escapeHtml(p.model || '') + '"></label>' +
      '<label class="field"><span>Группа</span><select class="select" id="pe-group">' + Object.keys(groupLabels).map(function (g) { return '<option value="' + g + '"' + (p.group === g ? ' selected' : '') + '>' + groupLabels[g] + '</option>'; }).join('') + '</select></label>' +
      '<label class="field"><span>Тип</span><input class="input" id="pe-type" value="' + escapeHtml(p.type || '') + '"></label>' +
      '<label class="field"><span>Цена</span><input class="input" id="pe-price" type="number" value="' + escapeHtml(p.price || 0) + '"></label>' +
      '<label class="field"><span>Наличие</span><select class="select" id="pe-stock">' + Object.keys(stockLabels).map(function (s) { return '<option value="' + s + '"' + (p.stock === s ? ' selected' : '') + '>' + stockLabels[s] + '</option>'; }).join('') + '</select></label>' +
      '<label class="field"><span>Видимость</span><select class="select" id="pe-active"><option value="1"' + (Number(p.active) ? ' selected' : '') + '>Показывать</option><option value="0"' + (!Number(p.active) ? ' selected' : '') + '>Скрыть</option></select></label>' +
      '<label class="field"><span>Бейдж</span><select class="select" id="pe-badge"><option value="">Нет</option><option value="new"' + (p.badge === 'new' ? ' selected' : '') + '>Новинка</option><option value="sale"' + (p.badge === 'sale' ? ' selected' : '') + '>Акция</option><option value="clearance"' + (p.badge === 'clearance' ? ' selected' : '') + '>Распродажа</option></select></label>' +
      '<label class="field"><span>Текст бейджа</span><input class="input" id="pe-badge-label" value="' + escapeHtml(p.badge_label || '') + '"></label>' +
      '</div></div>';
  }

  function productMediaTab(p) {
    var photos = Array.isArray(p.photos) ? p.photos : [];
    var main = p.photo || photos[0] || '';
    var photoItems = photos.map(function (ph, i) {
      var isMain = ph === main;
      return '<div class="photo-thumb-wrap">' +
        '<button class="photo-thumb' + (isMain ? ' active' : '') + '" data-main-photo="' + i + '" type="button" aria-label="Сделать главным: ' + escapeHtml(ph) + '"><img src="' + escapeHtml(productImageUrl(ph)) + '" alt=""></button>' +
        (isMain ? '<span class="photo-main-badge">Главное</span>' : '') +
        '<button class="photo-remove" data-remove-photo="' + i + '" type="button" aria-label="Удалить фото: ' + escapeHtml(ph) + '">' + icon('x') + '</button></div>';
    }).join('');
    return '<div class="editor-grid"><div class="photo-box"><div class="photo-preview">' + (main ? '<img src="' + escapeHtml(productImageUrl(main)) + '" alt="Главное фото товара">' : '<span class="muted">Фото не выбрано</span>') + '</div><div class="photo-list">' + photoItems + '</div></div><div class="panel"><div class="panel-body form-grid"><label class="field wide"><span>Главное фото</span><input class="input" id="pe-photo" value="' + escapeHtml(p.photo || '') + '" placeholder="Имя файла"><small class="field-hint">Можно выбрать главное фото нажатием на миниатюру слева</small></label><div class="field wide"><span>Загрузить изображения</span><div class="upload-zone" id="pe-upload-zone"><input id="pe-upload" class="upload-input" type="file" accept=".jpg,.jpeg,.png,.webp,.gif,image/jpeg,image/png,image/webp,image/gif" multiple><label class="btn upload-button" for="pe-upload">' + icon('upload') + '<span>Выбрать файлы</span></label><div><strong id="pe-upload-title">Перетащите или выберите изображения</strong><small id="pe-upload-note">JPG, PNG, WEBP или GIF · до 8 МБ каждый</small></div></div></div><label class="field wide"><span>Добавить по имени файла</span><div class="inline-field"><input class="input" id="pe-manual-photo" placeholder="например ultima-elysium.webp"><button class="btn" id="pe-add-photo" type="button" aria-label="Добавить фото по имени">' + icon('plus') + '<span>Добавить</span></button></div></label><div class="wide field-hint">Добавлено: ' + photos.length + ' из 12. Если главное фото не выбрано, используется первое.</div></div></div></div>';
  }

  function productTextTab(p) {
    return '<div class="panel description-panel"><div class="panel-body form-grid"><label class="field wide"><span>Краткое описание</span><input class="input" id="pe-descShort" value="' + escapeHtml(p.descShort || '') + '"></label><label class="field wide"><span>Преимущество в карточке</span><input class="input" id="pe-cardBenef" value="' + escapeHtml(p.cardBenef || '') + '"></label><label class="field wide"><span>Админское описание на карточке</span><textarea class="textarea" id="pe-description">' + escapeHtml(p.description || '') + '</textarea></label><label class="field wide"><span>Преимущества, по одному в строке</span><textarea class="textarea" id="pe-benefits">' + escapeHtml((p.benefits || []).join('\n')) + '</textarea></label></div></div>';
  }

  function productTechTab(p) {
    return '<div class="panel"><div class="panel-body form-grid"><div class="field wide"><span>BTU</span><div class="chip-row">' + ['07','09','12','18','24','30','36','48','60'].map(function (b) { return '<button class="chip ' + (p.btu === b ? 'active' : '') + '" data-btu="' + b + '" type="button">' + b + '</button>'; }).join('') + '</div></div><label class="field"><span>Площадь, м²</span><input class="input" id="pe-area" type="number" value="' + escapeHtml(p.area || 0) + '"></label><label class="field"><span>Завод</span><input class="input" id="pe-factory" value="' + escapeHtml(p.factory || '') + '"></label><label class="field"><span>Компрессор</span><input class="input" id="pe-compressor" value="' + escapeHtml(p.compressor || '') + '"></label><label class="field"><span>Фреон</span><input class="input" id="pe-freon" value="' + escapeHtml(p.freon || '') + '"></label><label class="field"><span>Цвет</span><input class="input" id="pe-color" value="' + escapeHtml(p.color || '') + '"></label><label class="field"><span>Код бренда</span><input class="input" id="pe-brandCode" value="' + escapeHtml(p.brandCode || '') + '"></label></div></div>';
  }

  function bindProductEditor(isCustom) {
    qsa('[data-editor-tab]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        collectEditorFields();
        state.editorTab = btn.dataset.editorTab;
        renderProductEditor(isCustom);
      });
    });
    var save = qs('#save-product');
    if (save) save.addEventListener('click', function () { saveProduct(isCustom); });
    var reset = qs('#reset-product');
    if (reset) reset.addEventListener('click', resetProductOverride);
    qsa('[data-btu]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.editorProduct.btu = btn.dataset.btu;
        renderProductEditor(isCustom);
      });
    });
    qsa('[data-remove-photo]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        collectEditorFields();
        state.editorProduct.photos.splice(Number(btn.dataset.removePhoto), 1);
        if (state.editorProduct.photo && state.editorProduct.photos.indexOf(state.editorProduct.photo) < 0) state.editorProduct.photo = state.editorProduct.photos[0] || '';
        renderProductEditor(isCustom);
      });
    });
    qsa('[data-main-photo]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        collectEditorFields();
        var selected = state.editorProduct.photos[Number(btn.dataset.mainPhoto)];
        if (selected) state.editorProduct.photo = selected;
        renderProductEditor(isCustom);
      });
    });
    var addPhoto = qs('#pe-add-photo');
    if (addPhoto) addPhoto.addEventListener('click', function () {
      collectEditorFields();
      var value = qs('#pe-manual-photo').value.trim();
      if (!value) return toast('Укажите имя файла', 'bad');
      if (state.editorProduct.photos.indexOf(value) >= 0) return toast('Это фото уже добавлено', 'bad');
      if (state.editorProduct.photos.length >= 12) return toast('Можно добавить не больше 12 фото', 'bad');
      state.editorProduct.photos.push(value);
      if (!state.editorProduct.photo) state.editorProduct.photo = value;
      renderProductEditor(isCustom);
    });
    async function uploadProductFiles(fileList) {
      collectEditorFields();
      var available = 12 - state.editorProduct.photos.length;
      var selectedFiles = Array.prototype.slice.call(fileList || []);
      if (!selectedFiles.length) return;
      if (available <= 0) return toast('Можно добавить не больше 12 фото', 'bad');
      var files = selectedFiles.filter(function (file) {
        if (file.size > 8 * 1024 * 1024) { toast(file.name + ': файл больше 8 МБ', 'bad'); return false; }
        if (file.type && file.type.indexOf('image/') !== 0) { toast(file.name + ': нужен файл изображения', 'bad'); return false; }
        return true;
      }).slice(0, available);
      if (!files.length) return;
      var upload = qs('#pe-upload');
      if (upload) upload.disabled = true;
      var title = qs('#pe-upload-title');
      if (title) title.textContent = 'Загружаем 0 из ' + files.length + '…';
      var uploaded = 0;
      for (var i = 0; i < files.length; i++) {
        var fd = new FormData();
        fd.append('photo', files[i]);
        try {
          var res = await api('upload_photo', {}, { body: fd });
          if (res.filename && state.editorProduct.photos.indexOf(res.filename) < 0) {
            state.editorProduct.photos.push(res.filename);
            uploaded++;
          }
          if (!state.editorProduct.photo && res.filename) state.editorProduct.photo = res.filename;
        } catch (err) { toast(err.message, 'bad'); }
        if (title) title.textContent = 'Загружаем ' + (i + 1) + ' из ' + files.length + '…';
      }
      if (selectedFiles.length > files.length) toast('Добавлены только файлы, которые прошли проверку и помещаются в лимит', 'bad');
      if (uploaded) toast('Загружено фото: ' + uploaded, 'ok');
      renderProductEditor(isCustom);
    }
    var upload = qs('#pe-upload');
    if (upload) upload.addEventListener('change', function () {
      uploadProductFiles(upload.files);
    });
    var uploadZone = qs('#pe-upload-zone');
    if (uploadZone) {
      ['dragenter', 'dragover'].forEach(function (eventName) {
        uploadZone.addEventListener(eventName, function (event) { event.preventDefault(); uploadZone.classList.add('is-dragging'); });
      });
      ['dragleave', 'drop'].forEach(function (eventName) {
        uploadZone.addEventListener(eventName, function (event) { event.preventDefault(); uploadZone.classList.remove('is-dragging'); });
      });
      uploadZone.addEventListener('drop', function (event) { uploadProductFiles(event.dataTransfer && event.dataTransfer.files); });
    }
    hydrateIcons();
  }

  function collectEditorFields() {
    var p = state.editorProduct || {};
    var map = {
      'pe-sku': 'sku', 'pe-id': 'id', 'pe-brand': 'brand', 'pe-series': 'series', 'pe-model': 'model',
      'pe-group': 'group', 'pe-type': 'type', 'pe-price': 'price', 'pe-stock': 'stock', 'pe-active': 'active',
      'pe-badge': 'badge', 'pe-badge-label': 'badge_label', 'pe-photo': 'photo', 'pe-descShort': 'descShort',
      'pe-cardBenef': 'cardBenef', 'pe-description': 'description', 'pe-area': 'area', 'pe-factory': 'factory',
      'pe-compressor': 'compressor', 'pe-freon': 'freon', 'pe-color': 'color', 'pe-brandCode': 'brandCode'
    };
    Object.keys(map).forEach(function (id) {
      var el = qs('#' + id);
      if (!el || el.disabled) return;
      var key = map[id];
      p[key] = (key === 'price' || key === 'area' || key === 'active') ? Number(el.value || 0) : el.value;
    });
    var benefits = qs('#pe-benefits');
    if (benefits) p.benefits = benefits.value.split(/\r?\n/).map(function (x) { return x.trim(); }).filter(Boolean);
    if (!Array.isArray(p.photos)) p.photos = [];
    if (p.photo && p.photos.indexOf(p.photo) < 0) p.photos.unshift(p.photo);
    p.stockLabel = stockLabels[p.stock] || p.stockLabel || '';
    state.editorProduct = p;
  }

  async function saveProduct(isCustom) {
    collectEditorFields();
    var p = state.editorProduct;
    if (!p.sku || !p.model) {
      toast('Нужны SKU и модель', 'bad');
      return;
    }
    try {
      if (isCustom) {
        await api('custom_product_save', {}, { method: 'POST', body: p });
      } else {
        await api('product_save_override', {}, { method: 'POST', body: p });
      }
      toast('Товар сохранен', 'ok');
      closeDrawer();
      await renderProducts();
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function resetProductOverride() {
    if (!state.editorProduct || !state.editorProduct.sku) return;
    if (!confirm('Сбросить все изменения этого базового товара?')) return;
    try {
      await api('product_override_delete', {}, { method: 'POST', body: { sku: state.editorProduct.sku } });
      toast('Override сброшен', 'ok');
      closeDrawer();
      renderProducts();
    } catch (err) { toast(err.message, 'bad'); }
  }

  async function renderSettings() {
    loading('Настройки', 'Интеграции, доступ и опасные операции');
    try {
      var data = await api('settings_get');
      var cfg = data.settings || {};
      setHeader('Настройки', 'Telegram, email, бонусы и служебные действия');
      viewRoot().innerHTML = '<section class="split-grid"><div class="panel"><div class="panel-head"><div><h2 class="panel-title">Интеграции</h2><div class="panel-subtitle">Пустое секретное поле сохраняет текущее значение</div></div></div><div class="panel-body">' + settingsForm(cfg) + '</div></div><div class="panel danger-zone"><div class="panel-head"><div><h2 class="panel-title">Опасная зона</h2><div class="panel-subtitle">Счётчик можно сбросить только после удаления всех записей раздела</div></div></div><div class="panel-body form-grid"><button class="btn danger" data-reset-counter="orders">' + icon('rotate-ccw') + '<span>Сбросить номера заказов</span></button><button class="btn danger" data-reset-counter="guest_orders">' + icon('rotate-ccw') + '<span>Сбросить гостевые</span></button><button class="btn danger" data-reset-counter="all">' + icon('triangle-alert') + '<span>Сбросить все счетчики</span></button></div></div></section>';
      qs('#settings-form').addEventListener('submit', async function (event) {
        event.preventDefault();
        try {
          await api('settings_save', {}, { method: 'POST', body: collectForm(event.currentTarget) });
          toast('Настройки сохранены', 'ok');
        } catch (err) { toast(err.message, 'bad'); }
      });
      qsa('[data-reset-counter]').forEach(function (btn) {
        btn.addEventListener('click', async function () {
          if (!confirm('Сброс счетчиков необратим. Продолжить?')) return;
          try {
            await api('reset_counter', {}, { method: 'POST', body: { type: btn.dataset.resetCounter } });
            toast('Счетчик сброшен', 'ok');
          } catch (err) { toast(err.message, 'bad'); }
        });
      });
      hydrateIcons();
    } catch (err) { failView(err); }
  }

  function settingsForm(cfg) {
    var fields = [
      ['BOT_TOKEN', 'Токен Telegram-бота', true],
      ['CHAT_ID', 'ID чата заказов', false],
      ['TG_ADMIN_ID', 'ID администратора Telegram', false],
      ['EMAIL_TO', 'Email получателей', false],
      ['CRON_SECRET', 'Секрет служебных задач', true],
      ['ALLOWED_ORIGIN', 'Разрешённый домен API', false],
      ['TG_FORCE_IP', 'IP Telegram для обхода блокировки', false]
    ];
    return '<form id="settings-form" class="form-grid">' + fields.map(function (item) {
      var key = item[0], label = item[1], secret = item[2];
      var configured = cfg._configured && cfg._configured[key];
      var hint = secret && configured ? 'Сейчас настроено · оставьте пустым, чтобы не менять' : (secret ? 'Оставьте пустым, чтобы сохранить текущее значение' : key);
      return '<label class="field wide"><span>' + escapeHtml(label) + '</span><input class="input" name="' + key + '" value="' + escapeHtml(secret ? '' : (cfg[key] || '')) + '"' + (secret ? ' type="password" autocomplete="new-password"' : '') + '><small class="field-hint">' + escapeHtml(hint) + '</small></label>';
    }).join('') + '<label class="field"><span>Бонусы</span><select class="select" name="bonuses_enabled"><option value="1"' + (cfg.bonuses_enabled !== '0' ? ' selected' : '') + '>Включены</option><option value="0"' + (cfg.bonuses_enabled === '0' ? ' selected' : '') + '>Выключены</option></select></label><div class="wide"><button class="btn primary" type="submit">' + icon('save') + '<span>Сохранить</span></button></div></form>';
  }

  function pager(page, total, limit, type) {
    var pages = Math.max(1, Math.ceil(total / limit));
    return '<div class="toolbar"><div class="muted">Страница ' + page + ' из ' + pages + ' · всего ' + total + '</div><div class="toolbar-right"><button class="btn ghost" data-page="' + (page - 1) + '" data-page-type="' + type + '" aria-label="Предыдущая страница" title="Предыдущая страница"' + (page <= 1 ? ' disabled' : '') + '>' + icon('chevron-left') + '</button><button class="btn ghost" data-page="' + (page + 1) + '" data-page-type="' + type + '" aria-label="Следующая страница" title="Следующая страница"' + (page >= pages ? ' disabled' : '') + '>' + icon('chevron-right') + '</button></div></div>';
  }

  function bindPager() {
    qsa('[data-page-type]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var type = btn.dataset.pageType;
        var page = Number(btn.dataset.page);
        if (type === 'orders') { state.orderFilters.page = page; renderOrders(); }
        if (type === 'guests') { state.guestFilters.page = page; renderGuests(); }
        if (type === 'products') { state.productFilters.page = page; renderProducts(); }
        if (type === 'visitors') { state.visitorPage = page; renderVisitors(); }
      });
    });
  }

  function openDrawer(title, body, foot) {
    var drawer = qs('#drawer');
    var wasOpen = drawer.classList.contains('on');
    if (!wasOpen) {
      var active = document.activeElement;
      if (active && active !== document.body && !active.closest('#drawer')) drawerReturnFocus = active;
    }
    qs('#drawer-backdrop').classList.add('on');
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-label', title);
    drawer.classList.add('on');
    document.body.classList.add('modal-open');
    drawer.innerHTML = '<div class="drawer-head"><h2 class="drawer-title">' + escapeHtml(title) + '</h2><button class="icon-btn" data-close-drawer aria-label="Закрыть редактор" title="Закрыть">' + icon('x') + '</button></div><div class="drawer-scroll">' + body + '</div><div class="drawer-foot">' + foot + '</div>';
    qsa('[data-close-drawer]', drawer).forEach(function (btn) { btn.addEventListener('click', closeDrawer); });
    hydrateIcons();
    var closeButton = qs('[data-close-drawer]', drawer);
    if (!wasOpen && closeButton) closeButton.focus({ preventScroll: true });
  }

  function closeDrawer() {
    var backdrop = qs('#drawer-backdrop');
    var drawer = qs('#drawer');
    if (backdrop) backdrop.classList.remove('on');
    if (drawer) {
      drawer.classList.remove('on');
      drawer.innerHTML = '';
    }
    document.body.classList.remove('modal-open');
    if (drawerReturnFocus && drawerReturnFocus.isConnected) drawerReturnFocus.focus({ preventScroll: true });
    drawerReturnFocus = null;
  }

  async function init() {
    root.innerHTML = '<div class="boot-screen"><div class="boot-card"><div class="boot-logo">SH</div><h1 class="boot-title">Админка СплитХаб</h1><p class="boot-sub">Проверяем сессию и поднимаем рабочую панель.</p><div class="spinner"></div></div></div>';
    try {
      var data = await auth('profile');
      if (!data.user || data.user.role !== 'admin') {
        renderLogin();
        return;
      }
      state.user = data.user;
      renderShell();
      switchView(state.view);
    } catch (err) {
      renderLogin();
    }
  }

  var originalRenderProducts = renderProducts;
  renderProducts = async function () {
    await originalRenderProducts();
    bindPager();
  };
  var originalRenderOrders = renderOrders;
  renderOrders = async function () {
    await originalRenderOrders();
    bindPager();
  };
  var originalRenderGuests = renderGuests;
  renderGuests = async function () {
    await originalRenderGuests();
    bindPager();
  };

  init();
})();
