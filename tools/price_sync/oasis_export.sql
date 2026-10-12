-- Выгрузка каталога SplitHome (Русклимат / Daichi / Бриз) для сверки цен СплитХаба.
-- Только чтение: ни одной записи не меняем.
--
-- Опт-цена по поставщикам (см. README проекта Site_ostatki_api_teleram):
--   Daichi     — price_wholesale;
--   Русклимат  — stock_stock.price_base («Ваша цена» портала), в price_wholesale розница;
--   Бриз       — в БД розница, настоящий опт только через API Бриза.
-- Поэтому отдаём обе цены, а решает уже price_sync.
SELECT p.source,
       p.nc_code,
       coalesce(b.title, ''),
       p.title,
       coalesce(p.series, ''),
       coalesce(p.price_wholesale, 0),
       coalesce(s.price_base, 0),
       coalesce(s.warehouse, ''),
       coalesce(s.quantity, 0)
FROM catalog_product p
LEFT JOIN catalog_brand b ON b.id = p.brand_id
LEFT JOIN stock_stock s ON s.product_id = p.id
WHERE p.is_active = TRUE
ORDER BY p.source, b.title NULLS LAST, p.title;
