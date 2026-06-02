<?php
/**
 * catalog.php — управление каталогом товаров
 * POST ?action=upload   — загрузить XLSX в converter/input/
 * POST ?action=convert  — запустить converter/convert.py
 * GET  ?action=status   — статус
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

require __DIR__ . '/../db/init.php';
adminRequire();

$action   = $_GET['action'] ?? '';
$base     = __DIR__ . '/..';
$inDir    = $base . '/converter/input';
$py3      = '/opt/rh/rh-python313/root/usr/bin/python3';
$convPy   = $base . '/converter/convert.py';
$outJs    = $base . '/converter/out/products.js';

switch ($action) {

    case 'upload':
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') jsonResponse(['ok'=>false,'error'=>'POST only'],405);
        $f = $_FILES['xlsx'] ?? null;
        if (!$f || $f['error'] !== UPLOAD_ERR_OK) {
            jsonResponse(['ok'=>false,'error'=>'Файл не получен'],422);
        }
        $ext = strtolower(pathinfo($f['name'], PATHINFO_EXTENSION));
        if (!in_array($ext, ['xlsx','xls'])) jsonResponse(['ok'=>false,'error'=>'Только .xlsx / .xls'],422);

        // Очищаем старые файлы в input/
        foreach (glob($inDir . '/*.{xlsx,xls}', GLOB_BRACE) as $old) unlink($old);

        $dest = $inDir . '/' . $f['name'];
        if (!move_uploaded_file($f['tmp_name'], $dest)) {
            jsonResponse(['ok'=>false,'error'=>'Не удалось сохранить файл'],500);
        }
        jsonResponse(['ok'=>true,'message'=>'Загружен: '.$f['name']]);

    case 'convert':
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') jsonResponse(['ok'=>false,'error'=>'POST only'],405);
        $xlsx = array_merge(glob($inDir.'/*.xlsx'), glob($inDir.'/*.xls'));
        if (empty($xlsx)) jsonResponse(['ok'=>false,'error'=>'Сначала загрузите master-файл в Каталог'],422);

        $cmd = escapeshellarg($py3).' '.escapeshellarg($convPy).' 2>&1';
        $raw = shell_exec($cmd);

        // Проверяем результат: конвертер пишет СТАТУС: УСПЕШНО
        if (strpos($raw, 'СТАТУС: УСПЕШНО') !== false || strpos($raw, 'USPESHNO') !== false) {
            // Считаем кол-во товаров из products.js
            $count = 0;
            if (file_exists($outJs)) {
                $js = file_get_contents($outJs);
                preg_match_all('/^\s*\{/m', $js, $m);
                $count = count($m[0]);
            }
            jsonResponse(['ok'=>true,'count'=>$count,'message'=>'Каталог обновлён: '.$count.' товаров','log'=>$raw]);
        }

        jsonResponse(['ok'=>false,'error'=>'Конвертер завершился с ошибкой','log'=>$raw]);

    case 'status':
        $xlsx    = array_merge(glob($inDir.'/*.xlsx')?:[], glob($inDir.'/*.xls')?:[]);
        $hasFile = !empty($xlsx);
        $mtime   = $hasFile ? date('d.m.Y H:i', filemtime(reset($xlsx))) : null;
        $fname   = $hasFile ? basename(reset($xlsx)) : null;
        $prodJs  = file_exists($outJs);
        $count   = 0;
        if ($prodJs) {
            $js = file_get_contents($outJs);
            preg_match_all('/^\s*\{/m', $js, $m);
            $count = count($m[0]);
        }
        jsonResponse(['ok'=>true,'has_file'=>$hasFile,'filename'=>$fname,'file_date'=>$mtime,
                      'products_js'=>$prodJs,'products_count'=>$count]);

    default:
        jsonResponse(['ok'=>false,'error'=>'Unknown action'],400);
}
