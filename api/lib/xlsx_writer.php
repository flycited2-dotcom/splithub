<?php
/**
 * SimpleXlsxWriter — минимальный генератор .xlsx без зависимостей.
 * XLSX = zip-архив с OOXML внутри. Поддержка: несколько листов,
 * жирная шапка, автофильтр, числа vs текст, UTF-8/кириллица.
 *
 * Использование:
 *   $w = new SimpleXlsxWriter();
 *   $w->addSheet('Клиенты', [['ID','Имя'], [1,'Иван']]);
 *   $w->download('export.xlsx'); // шлёт заголовки и тело, exit вызывающий
 */
class SimpleXlsxWriter {
    private $sheets = []; // [ ['name'=>..., 'rows'=>[[...],...]], ... ]

    public function addSheet($name, array $rows) {
        // Имя листа: ≤31 символ, без : \ / ? * [ ]
        $name = preg_replace('/[:\\\\\/\?\*\[\]]/u', ' ', (string)$name);
        $name = trim(mb_substr($name, 0, 31));
        if ($name === '') $name = 'Лист' . (count($this->sheets) + 1);
        $this->sheets[] = ['name' => $name, 'rows' => array_values($rows)];
    }

    private function esc($s) {
        return htmlspecialchars((string)$s, ENT_QUOTES | ENT_XML1, 'UTF-8');
    }

    private function colLetter($n) { // 0 -> A, 26 -> AA
        $s = '';
        $n++;
        while ($n > 0) { $r = ($n - 1) % 26; $s = chr(65 + $r) . $s; $n = intval(($n - 1) / 26); }
        return $s;
    }

    private function sheetXml(array $sheet) {
        $rows = $sheet['rows'];
        $rowCount = count($rows);
        $colCount = 0;
        foreach ($rows as $r) $colCount = max($colCount, count($r));
        $dim = 'A1:' . $this->colLetter(max(0, $colCount - 1)) . max(1, $rowCount);

        $xml  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $xml .= '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';
        $xml .= '<dimension ref="' . $dim . '"/>';
        $xml .= '<sheetData>';
        foreach ($rows as $ri => $row) {
            $rn = $ri + 1;
            $xml .= '<row r="' . $rn . '">';
            $ci = 0;
            foreach ($row as $val) {
                $cell = $this->colLetter($ci) . $rn;
                $isHeader = ($ri === 0);
                $style = $isHeader ? ' s="1"' : '';
                if (is_int($val) || (is_string($val) && $val !== '' && preg_match('/^-?\d{1,15}$/', $val))) {
                    $xml .= '<c r="' . $cell . '"' . $style . '><v>' . $this->esc($val) . '</v></c>';
                } else {
                    $xml .= '<c r="' . $cell . '"' . $style . ' t="inlineStr"><is><t xml:space="preserve">' . $this->esc($val) . '</t></is></c>';
                }
                $ci++;
            }
            $xml .= '</row>';
        }
        $xml .= '</sheetData>';
        if ($rowCount > 0 && $colCount > 0) {
            $af = 'A1:' . $this->colLetter($colCount - 1) . $rowCount;
            $xml .= '<autoFilter ref="' . $af . '"/>';
        }
        $xml .= '</worksheet>';
        return $xml;
    }

    private function build() {
        $n = count($this->sheets);
        if ($n === 0) { $this->addSheet('Лист1', [['']]); $n = 1; }

        $contentTypes  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $contentTypes .= '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">';
        $contentTypes .= '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>';
        $contentTypes .= '<Default Extension="xml" ContentType="application/xml"/>';
        $contentTypes .= '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>';
        $contentTypes .= '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>';
        for ($i = 1; $i <= $n; $i++) {
            $contentTypes .= '<Override PartName="/xl/worksheets/sheet' . $i . '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        }
        $contentTypes .= '</Types>';

        $rootRels  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $rootRels .= '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
        $rootRels .= '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>';
        $rootRels .= '</Relationships>';

        $wbSheets = ''; $wbRels = '';
        $wbRels .= '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>';
        for ($i = 1; $i <= $n; $i++) {
            $nm = htmlspecialchars($this->sheets[$i - 1]['name'], ENT_QUOTES | ENT_XML1, 'UTF-8');
            $wbSheets .= '<sheet name="' . $nm . '" sheetId="' . $i . '" r:id="rId' . $i . '"/>';
            $wbRels   .= '<Relationship Id="rId' . $i . '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' . $i . '.xml"/>';
        }
        $workbook  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $workbook .= '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">';
        $workbook .= '<sheets>' . $wbSheets . '</sheets></workbook>';

        $wbRelsXml  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $wbRelsXml .= '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' . $wbRels . '</Relationships>';

        // styles: s="1" = жирный шрифт для шапки
        $styles  = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
        $styles .= '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';
        $styles .= '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>';
        $styles .= '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>';
        $styles .= '<borders count="1"><border/></borders>';
        $styles .= '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>';
        $styles .= '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>';
        $styles .= '</styleSheet>';

        $tmp = tempnam(sys_get_temp_dir(), 'xlsx');
        $zip = new ZipArchive();
        if ($zip->open($tmp, ZipArchive::OVERWRITE) !== true) {
            throw new RuntimeException('Не удалось создать xlsx-архив');
        }
        $zip->addFromString('[Content_Types].xml', $contentTypes);
        $zip->addFromString('_rels/.rels', $rootRels);
        $zip->addFromString('xl/workbook.xml', $workbook);
        $zip->addFromString('xl/_rels/workbook.xml.rels', $wbRelsXml);
        $zip->addFromString('xl/styles.xml', $styles);
        for ($i = 1; $i <= $n; $i++) {
            $zip->addFromString('xl/worksheets/sheet' . $i . '.xml', $this->sheetXml($this->sheets[$i - 1]));
        }
        $zip->close();
        return $tmp;
    }

    public function download($filename) {
        $tmp = $this->build();
        $data = file_get_contents($tmp);
        @unlink($tmp);
        header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        header('Content-Disposition: attachment; filename="' . preg_replace('/[^A-Za-z0-9_\-\.]/', '_', $filename) . '"');
        header('Content-Length: ' . strlen($data));
        echo $data;
    }

    public function save($path) {
        $tmp = $this->build();
        copy($tmp, $path);
        @unlink($tmp);
    }
}
