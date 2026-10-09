# ===== gui/widgets/yearly_table/ucoin_parser.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Парсер таблиц монет с uCoin.net
"""

import re
import json
import logging
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication


class UCoinParser:
    """Класс для парсинга таблиц монет с uCoin.net"""
    
    def __init__(self, web_view):
        self.web_view = web_view
        self.logger = logging.getLogger('CoinCollector.UCoinParser')
        self.parsed_data = None
        self.headers = None
        self.page_title = None
    
    def get_page_title(self):
        """Получает заголовок страницы для определения страны"""
        js_title = """
        (function() {
            var title = document.title;
            var match = title.match(/>\\s*([^<]+)/);
            if (match) {
                return match[1].trim();
            }
            return title.split('>')[0].trim();
        })();
        """
        
        class TitleCallback:
            def __init__(self, parser):
                self.parser = parser
            
            def __call__(self, result):
                if result:
                    self.parser.page_title = result
                    self.parser.logger.info(f"Заголовок страницы: {result}")
        
        callback = TitleCallback(self)
        self.web_view.page().runJavaScript(js_title, 0, callback)
        
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        
        for _ in range(30):
            if self.page_title is not None:
                break
            QTimer.singleShot(100, loop.quit)
            loop.exec()
        
        return self.page_title
    
    def parse_current_page(self, progress_callback=None):
        """
        Парсит текущую страницу в браузере и возвращает данные
        """
        
        js_code = """
        (function() {
            var result = [];
            var headersList = [];
            
            var allTables = document.querySelectorAll('table');
            var targetTable = null;
            
            for (var i = 0; i < allTables.length; i++) {
                var table = allTables[i];
                var text = table.innerText;
                var hasFourDigitNumbers = (text.match(/\\b\\d{4}\\b/g) || []).length > 2;
                var rowCount = table.querySelectorAll('tr').length;
                
                if (hasFourDigitNumbers && rowCount > 3) {
                    targetTable = table;
                    break;
                }
            }
            
            if (!targetTable && allTables.length > 0) {
                var maxRows = 0;
                for (var i = 0; i < allTables.length; i++) {
                    var rows = allTables[i].querySelectorAll('tr').length;
                    if (rows > maxRows) {
                        maxRows = rows;
                        targetTable = allTables[i];
                    }
                }
            }
            
            if (!targetTable) {
                return JSON.stringify({error: 'Table not found'});
            }
            
            function getSpan(cell) {
                return {
                    rowspan: parseInt(cell.getAttribute('rowspan')) || 1,
                    colspan: parseInt(cell.getAttribute('colspan')) || 1
                };
            }
            
            function cleanText(text) {
                if (!text) return '';
                text = text.replace(/[\\n\\r]+/g, ' ').trim();
                text = text.replace(/\\s+/g, ' ');
                return text;
            }
            
            // Получаем все значения из ячейки (для нескольких ссылок)
            function getCellValues(cell) {
                var values = [];
                var links = cell.querySelectorAll('a');
                
                if (links.length > 1) {
                    for (var i = 0; i < links.length; i++) {
                        var linkText = cleanText(links[i].textContent);
                        if (linkText && linkText !== '-') {
                            values.push(linkText);
                        }
                    }
                } else {
                    var text = cleanText(cell.innerText);
                    if (text && text !== '-' && text !== '—') {
                        // Проверяем на разделители
                        if (text.indexOf(' ') !== -1) {
                            var parts = text.split(' ');
                            for (var p = 0; p < parts.length; p++) {
                                if (parts[p].trim()) {
                                    values.push(parts[p].trim());
                                }
                            }
                        } else {
                            values.push(text);
                        }
                    }
                }
                
                return values;
            }
            
            var rows = targetTable.querySelectorAll('tr');
            if (rows.length < 2) {
                return JSON.stringify({error: 'Not enough rows'});
            }
            
            // Находим строку с заголовками
            var headerRowIndex = -1;
            
            for (var r = 0; r < Math.min(rows.length, 5); r++) {
                var cells = rows[r].querySelectorAll('th, td');
                for (var c = 0; c < cells.length; c++) {
                    var text = cleanText(cells[c].innerText);
                    if (text === 'Год' || text === 'Year' || text === 'Год/Year') {
                        headerRowIndex = r;
                        break;
                    }
                }
                if (headerRowIndex !== -1) break;
            }
            
            if (headerRowIndex === -1) {
                headerRowIndex = 0;
            }
            
            // Парсим заголовки (номиналы) в порядке из таблицы
            var headerCells = rows[headerRowIndex].querySelectorAll('th, td');
            var headers = [];
            var colIndex = 0;
            
            for (var i = 0; i < headerCells.length; i++) {
                var cell = headerCells[i];
                var text = cleanText(cell.innerText);
                var span = getSpan(cell);
                
                if (text !== 'Год' && text !== 'Year' && text !== 'Год/Year' && text !== '') {
                    for (var s = 0; s < span.colspan; s++) {
                        headers[colIndex + s] = text;
                    }
                }
                colIndex += span.colspan;
            }
            
            // Убираем пустые заголовки
            headersList = [];
            for (var i = 0; i < headers.length; i++) {
                if (headers[i]) {
                    headersList.push(headers[i]);
                }
            }
            
            // Парсим строки данных
            var allRowsData = [];
            var activeRowspans = {};
            
            for (var r = headerRowIndex + 1; r < rows.length; r++) {
                var cells = rows[r].querySelectorAll('th, td');
                var col = 0;
                var currentYear = null;
                var rowData = {};
                var cellIndex = 0;
                var maxValues = 1;
                var hasMultiple = false;
                
                // Заполняем из активных rowspan
                while (activeRowspans[col]) {
                    var active = activeRowspans[col];
                    var denom = headers[col];
                    if (denom && active.values !== undefined) {
                        rowData[denom] = active.values;
                        if (active.values.length > 1) hasMultiple = true;
                        maxValues = Math.max(maxValues, active.values.length);
                    }
                    active.remaining--;
                    if (active.remaining <= 0) {
                        delete activeRowspans[col];
                    }
                    col++;
                }
                
                while (cellIndex < cells.length) {
                    var cell = cells[cellIndex];
                    var span = getSpan(cell);
                    
                    // Определяем год
                    if (col === 0 || currentYear === null) {
                        var cellText = cleanText(cell.innerText);
                        var yearMatch = cellText.match(/\\b(\\d{4})\\b/);
                        if (yearMatch) {
                            currentYear = yearMatch[1];
                        }
                    }
                    
                    var denom = headers[col];
                    var values = getCellValues(cell);
                    
                    if (denom && values.length > 0) {
                        rowData[denom] = values;
                        if (values.length > 1) hasMultiple = true;
                        maxValues = Math.max(maxValues, values.length);
                    }
                    
                    // Запоминаем для rowspan
                    if (span.rowspan > 1 && denom && values.length > 0) {
                        for (var rs = 1; rs < span.rowspan; rs++) {
                            if (!activeRowspans[col]) {
                                activeRowspans[col] = {
                                    remaining: span.rowspan - rs,
                                    values: values
                                };
                            }
                        }
                    }
                    
                    col += span.colspan;
                    cellIndex++;
                }
                
                if (currentYear) {
                    allRowsData.push({
                        year: currentYear,
                        data: rowData,
                        maxValues: maxValues,
                        hasMultiple: hasMultiple
                    });
                }
            }
            
            // Разворачиваем строки с несколькими значениями
            var expandedRows = [];
            
            for (var i = 0; i < allRowsData.length; i++) {
                var row = allRowsData[i];
                var year = row.year;
                var data = row.data;
                var maxValues = row.maxValues;
                
                if (row.hasMultiple && maxValues > 1) {
                    for (var v = 0; v < maxValues; v++) {
                        var newRowData = {};
                        for (var denom in data) {
                            var valArray = data[denom];
                            if (Array.isArray(valArray)) {
                                if (v < valArray.length && valArray[v]) {
                                    newRowData[denom] = valArray[v];
                                }
                            } else {
                                if (v === 0) {
                                    newRowData[denom] = valArray;
                                }
                            }
                        }
                        expandedRows.push({
                            year: year,
                            data: newRowData
                        });
                    }
                } else {
                    var singleRowData = {};
                    for (var denom in data) {
                        var val = data[denom];
                        if (Array.isArray(val)) {
                            singleRowData[denom] = val[0] || '';
                        } else {
                            singleRowData[denom] = val;
                        }
                    }
                    expandedRows.push({
                        year: year,
                        data: singleRowData
                    });
                }
            }
            
            // Фильтруем пустые строки
            var finalRows = [];
            for (var i = 0; i < expandedRows.length; i++) {
                var row = expandedRows[i];
                var hasData = false;
                for (var denom in row.data) {
                    if (row.data[denom] && row.data[denom] !== '') {
                        hasData = true;
                        break;
                    }
                }
                if (hasData) {
                    finalRows.push({
                        year: row.year,
                        data: row.data
                    });
                }
            }
            
            return JSON.stringify({
                rows: finalRows,
                headers: headersList
            });
        })();
        """
        
        class JSCallback:
            def __init__(self, parser, progress_callback):
                self.parser = parser
                self.progress_callback = progress_callback
            
            def __call__(self, result):
                if result:
                    try:
                        import json
                        data = json.loads(result)
                        if 'error' in data:
                            self.parser.logger.error(f"Ошибка парсинга: {data['error']}")
                            if self.progress_callback:
                                self.progress_callback(100, f"❌ {data['error']}")
                        else:
                            self.parser.parsed_data = data.get('rows', [])
                            self.parser.headers = data.get('headers', [])
                            total_rows = len(self.parser.parsed_data)
                            self.parser.logger.info(f"Парсинг завершён: {total_rows} строк, заголовков: {len(self.parser.headers)}")
                            if self.progress_callback:
                                self.progress_callback(100, f"✅ Найдено {total_rows} строк")
                    except json.JSONDecodeError as e:
                        self.parser.logger.error(f"Ошибка разбора JSON: {e}")
                        if self.progress_callback:
                            self.progress_callback(100, f"❌ Ошибка разбора данных")
                else:
                    self.parser.logger.error("Пустой результат парсинга")
                    if self.progress_callback:
                        self.progress_callback(100, f"❌ Не удалось извлечь данные")
        
        self.parsed_data = None
        self.headers = None
        page_title = self.get_page_title()
        
        if progress_callback:
            progress_callback(10, "🔍 Анализ страницы...")
        
        callback = JSCallback(self, progress_callback)
        self.web_view.page().runJavaScript(js_code, 0, callback)
        
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        
        for _ in range(50):
            if self.parsed_data is not None:
                break
            QTimer.singleShot(100, loop.quit)
            loop.exec()
        
        return self.parsed_data, page_title


def create_yearly_table_from_parser(parsed_data, country_name, headers=None):
    """
    Создаёт структуру таблицы для погодовки на основе распарсенных данных
    
    parsed_data: массив строк [{year: "1994", data: {деноминация: значение}}]
    headers: порядок номиналов из таблицы (если None, собирается из данных)
    
    Returns:
        dict: {'headers': [номиналы], 'rows': [[значения для строки1], ...], 'years': [годы]}
    """
    if not parsed_data:
        return None
    
    # Используем заголовки из таблицы, если они переданы
    if headers and len(headers) > 0:
        all_denominations = headers
    else:
        # Запасной вариант: собираем в порядке обнаружения
        all_denominations = []
        seen_denoms = set()
        for item in parsed_data:
            data = item.get('data', {})
            for denom in data.keys():
                if denom not in seen_denoms:
                    seen_denoms.add(denom)
                    all_denominations.append(denom)
    
    # Создаём строки таблицы
    table_rows = []
    years_list = []
    
    for item in parsed_data:
        year = item.get('year')
        data = item.get('data', {})
        
        years_list.append(year)
        
        row_values = []
        for denom in all_denominations:
            value = data.get(denom, "")
            # Упрощаем длинные значения
            if len(value) > 15:
                value = "✓"
            row_values.append(value)
        
        table_rows.append(row_values)
    
    return {
        'headers': all_denominations,
        'rows': table_rows,
        'years': years_list,
        'country': country_name
    }