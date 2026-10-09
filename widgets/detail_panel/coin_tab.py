# -*- coding: utf-8 -*-
"""
Вкладка с информацией о монете (просмотр и редактирование)
"""
import os
import logging
import shutil
import re
import json
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QStackedWidget, QMessageBox, QApplication,
                               QLabel, QDateEdit, QComboBox, QLineEdit,
                               QCheckBox, QTextEdit, QFrame)
from PySide6.QtCore import Qt, QTimer, QDate, QSize, QUrl
from PySide6.QtGui import QIcon
from database.models import Country, Coin, StandardReference
from gui.dialogs.references_dialog import ReferencesDialog
from gui.widgets.detail_panel.coin_view import CoinViewWidget
from gui.widgets.detail_panel.coin_edit import CoinEditWidget
from gui.widgets.detail_panel.coin_fields import CoinFieldsMixin
from gui.widgets.detail_panel.coin_combos import CoinCombosMixin
from utils.paths import paths


class CoinTab(QWidget, CoinCombosMixin, CoinFieldsMixin):
    """Вкладка с информацией о монете"""
    REF_CURRENCY = 0
    REF_MINT = 1
    REF_METAL = 2
    REF_EDGE = 3
    REF_PURCHASE_COUNTRY = 4
    REF_PERIOD = 7
    REF_STATUS = 8
    REF_CONDITION = 9
    REF_RARITY = 10
    REF_SHAPE = 11
    REF_ISSUE_TYPE = 12
    REF_AVREV = 13
    REF_ACQUISITION_TYPE = 14
    REF_STORAGE_LOCATION = 15

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.CoinTab')
        self.current_coin = None
        self.edit_mode = False
        self.images_dir = Path("data/coin_images")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.edit_fields = {}
        self.custom_edit_fields = {}
        self.save_btn = None
        self.cancel_btn = None
        self.fill_from_ucoin_btn = None
        self.custom_fields = []
        self._is_clearing = False
        self.create_edit_fields()
        self.load_custom_fields()
        self.load_all_combos()
        self.init_ui()

    def load_custom_fields(self):
        """Загружает пользовательские поля из базы данных"""
        try:
            fields = self.db_manager.get_active_custom_fields()
            self.custom_fields_data = []
            for field in fields:
                self.custom_fields_data.append({
                    'id': field.id,
                    'field_key': field.field_key,
                    'name': field.name,
                    'field_type': field.field_type,
                    'show_in_form': field.show_in_form,
                    'show_in_edit': getattr(field, 'show_in_edit', True),
                    'show_in_view': getattr(field, 'show_in_view', True),
                    'sort_order': field.sort_order,
                    'category': field.category,
                    'options': field.options,
                    'default_value': field.default_value
                })
            self.custom_fields = self.custom_fields_data
            self.logger.info(f"Загружено {len(self.custom_fields)} пользовательских полей")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки пользовательских полей: {e}")
            self.custom_fields = []
            self.custom_fields_data = []

    def create_custom_edit_widgets(self, parent_layout):
        """Создает виджеты для пользовательских полей"""
        if not self.custom_fields:
            return
        from PySide6.QtWidgets import QGroupBox, QFormLayout
        custom_group = QGroupBox("📌 Пользовательские поля")
        custom_layout = QFormLayout()
        custom_layout.setSpacing(3)
        custom_layout.setContentsMargins(5, 5, 5, 5)
        for field_dict in self.custom_fields:
            if not field_dict.get('show_in_form', True):
                continue
            field_key = field_dict['field_key']
            field_type = field_dict['field_type']
            field_name = field_dict['name']
            if field_type == "text":
                widget = QLineEdit()
                widget.setPlaceholderText(f"Введите {field_name.lower()}")
                self.custom_edit_fields[field_key] = widget
                custom_layout.addRow(f"{field_name}:", widget)
            elif field_type == "number":
                from PySide6.QtWidgets import QDoubleSpinBox
                widget = QDoubleSpinBox()
                widget.setRange(-9999999, 9999999)
                widget.setDecimals(2)
                widget.setSpecialValueText("Не указано")
                self.custom_edit_fields[field_key] = widget
                custom_layout.addRow(f"{field_name}:", widget)
            elif field_type == "date":
                widget = QDateEdit()
                widget.setCalendarPopup(True)
                widget.setDate(QDate.currentDate())
                widget.setSpecialValueText("Не указана")
                self.custom_edit_fields[field_key] = widget
                custom_layout.addRow(f"{field_name}:", widget)
            elif field_type == "boolean":
                widget = QCheckBox()
                self.custom_edit_fields[field_key] = widget
                custom_layout.addRow(f"{field_name}:", widget)
            elif field_type == "list":
                widget = QComboBox()
                widget.addItem("—", None)
                options = field_dict.get('options')
                if options:
                    try:
                        opts = json.loads(options)
                        for opt in opts:
                            widget.addItem(opt, opt)
                    except Exception:
                        pass
                widget.setEditable(True)
                self.custom_edit_fields[field_key] = widget
                custom_layout.addRow(f"{field_name}:", widget)
            elif field_type == "textarea":
                widget = QTextEdit()
                widget.setMaximumHeight(80)
                widget.setPlaceholderText(f"Введите {field_name.lower()}")
                self.custom_edit_fields[field_key] = widget
                custom_layout.addRow(f"{field_name}:", widget)
        custom_group.setLayout(custom_layout)
        parent_layout.addWidget(custom_group)

    def load_custom_values_to_form(self, coin):
        """Загружает пользовательские значения в форму"""
        if not coin or not coin.custom_data:
            return
        try:
            custom_data = json.loads(coin.custom_data)
        except Exception:
            return
        fields_dict = {f['field_key']: f for f in self.custom_fields}
        for field_key, widget in self.custom_edit_fields.items():
            value = custom_data.get(field_key)
            if value is None:
                continue
            field = fields_dict.get(field_key)
            if not field:
                continue
            field_type = field['field_type']
            if field_type == "text":
                widget.setText(str(value))
            elif field_type == "number":
                try:
                    widget.setValue(float(value))
                except Exception:
                    pass
            elif field_type == "date":
                try:
                    if isinstance(value, str):
                        date_obj = datetime.strptime(value, "%Y-%m-%d").date()
                        widget.setDate(date_obj)
                except Exception:
                    pass
            elif field_type == "boolean":
                widget.setChecked(bool(value))
            elif field_type == "list":
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
                else:
                    widget.setCurrentText(str(value))
            elif field_type == "textarea":
                widget.setText(str(value))

    def collect_custom_values(self):
        """Собирает значения пользовательских полей из формы"""
        custom_data = {}
        fields_dict = {f['field_key']: f for f in self.custom_fields}
        for field_key, widget in self.custom_edit_fields.items():
            field = fields_dict.get(field_key)
            if not field:
                continue
            field_type = field['field_type']
            if field_type == "text":
                value = widget.text().strip()
                if value:
                    custom_data[field_key] = value
            elif field_type == "number":
                value = widget.value()
                if value != 0:
                    custom_data[field_key] = value
            elif field_type == "date":
                if widget.date() and not widget.date().toString() == "01.01.2000":
                    custom_data[field_key] = widget.date().toPython().isoformat()
            elif field_type == "boolean":
                custom_data[field_key] = widget.isChecked()
            elif field_type == "list":
                value = widget.currentData()
                if value is None:
                    value = widget.currentText().strip()
                if value:
                    custom_data[field_key] = value
            elif field_type == "textarea":
                value = widget.toPlainText().strip()
                if value:
                    custom_data[field_key] = value
        return custom_data

    def fill_from_ucoin(self):
        """Заполняет поля ТЕКУЩЕЙ монеты данными со страницы UCOIN (кнопка панели).
        ОБНОВЛЯЕТ текущую монету — копию НЕ создаёт, номер НЕ трогает.
        После нажатия переносит фокус на вкладку браузера."""
        # === ЗАЩИТА ОТ ПОВТОРНОГО ВЫЗОВА (дабл-клик / дубль сигнала) ===
        if getattr(self, '_ucoin_fill_running', False):
            self.logger.warning("⚠️ Заполнение из UCOIN уже выполняется — повторный вызов игнорирую")
            return
        self._ucoin_fill_running = True

        ucoin_url = None
        if hasattr(self, 'edit_fields') and 'ucoin_url' in self.edit_fields:
            try:
                ucoin_url = self.edit_fields['ucoin_url'].text().strip()
            except Exception:
                ucoin_url = None
        if not ucoin_url and self.current_coin:
            ucoin_url = getattr(self.current_coin, 'ucoin_url', None)
        if not ucoin_url:
            self._ucoin_fill_running = False
            QMessageBox.warning(self, "Предупреждение",
                "Не указана ссылка на UCOIN.\nВставьте ссылку в поле 'UCOIN ссылка'.")
            return
        if 'ucoin.net/coin/' not in ucoin_url:
            self._ucoin_fill_running = False
            QMessageBox.warning(self, "Предупреждение",
                "Ссылка не похожа на страницу монеты UCOIN.\n"
                "Ожидается: https://ru.ucoin.net/coin/...")
            return
        coin_id = None
        if self.current_coin:
            try:
                coin_id = self.current_coin.id
            except Exception:
                coin_id = None
        if not coin_id:
            self._ucoin_fill_running = False
            QMessageBox.warning(self, "Предупреждение", "Не выбрана монета")
            return
        from PySide6.QtWidgets import QApplication
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break
        if not main_window or not hasattr(main_window, '_fill_coin_from_ucoin'):
            self._ucoin_fill_running = False
            QMessageBox.warning(self, "Ошибка", "Главное окно не найдено")
            return
        if not self.edit_mode:
            self.switch_to_edit_mode()
        if hasattr(self, 'edit_fields') and 'ucoin_url' in self.edit_fields:
            try:
                self.edit_fields['ucoin_url'].setText(ucoin_url)
            except Exception:
                pass
        # === РЕЖИМ ОБНОВЛЕНИЯ: каталожный номер НЕ перегенерируется ===
        self._ucoin_update_mode = True
        self.logger.info(f"🔗 fill_from_ucoin: делегирую главному окну, монета ID {coin_id} (РЕЖИМ ОБНОВЛЕНИЯ, номер сохраняется)")
        main_window._fill_coin_from_ucoin(coin_id, ucoin_url)
        # === ПЕРЕНОС ФОКУСА НА ВКЛАДКУ БРАУЗЕРА (центральная панель) ===
        from PySide6.QtCore import QTimer
        def _switch_to_browser():
            try:
                if hasattr(main_window, 'center_tab_widget'):
                    for i in range(main_window.center_tab_widget.count()):
                        if 'Браузер' in main_window.center_tab_widget.tabText(i):
                            main_window.center_tab_widget.setCurrentIndex(i)
                            self.logger.info(f"🌐 Фокус перенесён на вкладку браузера (индекс {i})")
                            break
            except Exception as e:
                self.logger.debug(f"Не удалось переключить на браузер: {e}")
        QTimer.singleShot(300, _switch_to_browser)

    def _ucoin_timeout(self, state):
        """Страховка: если страница не загрузилась за 30 сек"""
        if state.get('done'):
            return
        state['done'] = True
        self._ucoin_update_mode = False
        self.logger.warning("⏱️ Таймаут загрузки страницы UCOIN")
        QMessageBox.warning(self, "UCOIN", "Страница не загрузилась за 30 секунд")

    def _ucoin_open_timeout(self, state):
        """Таймаут ожидания загрузки страницы UCOIN"""
        if state.get('processed'):
            return
        state['processed'] = True
        self._ucoin_update_mode = False
        self.logger.warning("⏱️ Таймаут ожидания загрузки страницы UCOIN")
        QMessageBox.warning(self, "Предупреждение",
                            "Страница UCOIN не загрузилась за 25 секунд.\n"
                            "Попробуйте ещё раз или откройте страницу вручную.")

    def _extract_ucoin_data(self, main_window, web_view=None):
        """Извлекает данные со страницы UCOIN через JavaScript.
        web_view передаётся ЯВНО — парсим именно ту вкладку, что открыли.
        В поле описания (coin_info) попадает ТОЛЬКО информация из шапки монеты
        (надписи над фотографией), описания аверса/реверса НЕ парсятся."""
        self.logger.info("📥 _extract_ucoin_data вызван")
        if web_view is None:
            browser = getattr(main_window, 'browser_tab', None)
            if browser is None or not hasattr(browser, 'get_current_web_view'):
                from gui.widgets.embedded_browser import EmbeddedBrowser
                browser = main_window.findChild(EmbeddedBrowser)
            if browser:
                web_view = browser.get_current_web_view()
        if not web_view:
            self.logger.error("❌ Нет WebView для парсинга")
            self._ucoin_load_processed = True
            return
        extract_js = """
(function() {
    var data = {};
    // ===== 1. ПАРСИМ ТАБЛИЦУ С ХАРАКТЕРИСТИКАМИ =====
    var tables = document.querySelectorAll('table.coin-info, table.tbl');
    for (var t = 0; t < tables.length; t++) {
        var rows = tables[t].querySelectorAll('tr');
        for (var i = 0; i < rows.length; i++) {
            var th = rows[i].querySelector('th');
            var td = rows[i].querySelector('td');
            if (th && td) {
                var label = th.textContent.trim().toLowerCase();
                var value = td.textContent.trim();
                if (label === 'год' || label === 'year') {
                    var match = value.match(/(\\d{4})/);
                    if (match) data['year'] = match[1];
                }
                else if (label === 'страна' || label === 'country') {
                    data['country'] = value;
                }
                else if (label === 'номинал' || label === 'denomination') {
                    var match = value.match(/^(\\d+(?:[.,]\\d+)?)\\s*(.+)/);
                    if (match) {
                        data['denomination_value'] = match[1];
                        data['currency_text'] = match[2];
                    } else {
                        data['denomination_value'] = value;
                    }
                }
                else if (label === 'валюта' || label === 'currency') {
                    data['currency_name'] = value;
                }
                else if (label === 'материал' || label === 'металл' || label === 'material') {
                    data['metal'] = value;
                }
                else if (label === 'вес (g)' || label === 'вес' || label === 'weight') {
                    var match = value.match(/([\\d,.]+)/);
                    if (match) data['weight'] = match[1].replace(',', '.');
                }
                else if (label === 'диаметр (mm)' || label === 'диаметр' || label === 'diameter') {
                    var match = value.match(/([\\d,.]+)/);
                    if (match) data['diameter'] = match[1].replace(',', '.');
                }
                else if (label === 'толщина (mm)' || label === 'толщина' || label === 'thickness') {
                    var match = value.match(/([\\d,.]+)/);
                    if (match) data['thickness'] = match[1].replace(',', '.');
                }
                    // === ГУРТ: тип (Рубчатый / Надпись и т.п.) ===
                    else if (label === 'гурт' || label === 'edge') {
                        data['edge'] = value;
                    }
                    // === ОПИСАНИЕ ГУРТА: отдельная строка (есть не всегда) ===
                    else if (label === 'описание гурта' || label === 'описание гурта:' ||
                             label === 'edge description' || label === 'гурт (описание)') {
                        data['edge_description'] = value;
                }
                else if (label === 'форма' || label === 'shape') {
                    data['shape'] = value;
                }
                else if (label === 'монетный двор' || label === 'mint') {
                    data['mint_name_raw'] = value;
                }
                else if (label.indexOf('авс/рев') >= 0 || label.indexOf('отношение') >= 0 || label === 'orientation') {
                    data['avrev_raw'] = value;
                    if (value.indexOf('Монетное') >= 0 || value.indexOf('180°') >= 0) {
                        data['avrev'] = 'Монетное (180°)';
                    }
                    else if (value.indexOf('Медальное') >= 0 || value.indexOf('0°') >= 0) {
                        data['avrev'] = 'Медальное (0°)';
                    }
                }
                else if (label.indexOf('чекан') >= 0 || label.indexOf('вид') >= 0) {
                    data['issue_type'] = value;
                }
                else if (label === 'период' || label === 'period') {
                    data['period'] = value;
                }
                else if (label === 'каталожные номера' || label === 'каталог' || label === 'km' || label.indexOf('km') >= 0) {
                    data['km_number'] = value;
                }
            }
        }
    }
    // ===== 2. РЕДКОСТЬ =====
    var rarityElements = document.querySelectorAll('.rarity-info .rarity');
    var foundRarity = null;
    for (var r = 0; r < rarityElements.length; r++) {
        var cls = rarityElements[r].className;
        if (cls.indexOf('NON') === -1 && cls.indexOf('rarity') >= 0) {
            foundRarity = rarityElements[r].textContent.trim();
            break;
        }
    }
    if (foundRarity) {
        data['rarity'] = foundRarity;
    }
    // ===== 3. ШАПКА МОНЕТЫ: надписи над фотографией (.h) — h2, h3, h4 (НЕ h1) =====
    var coinTitle = '';
    var headerElement = document.querySelector('.h');
    if (headerElement) {
        var selectors = ['h2', 'h3', 'h4'];
        var texts = [];
        var seenTexts = {};
        for (var s = 0; s < selectors.length; s++) {
            var elements = headerElement.querySelectorAll(selectors[s]);
            for (var i = 0; i < elements.length; i++) {
                var text = elements[i].textContent ? elements[i].textContent.trim() : '';
                if (text && !seenTexts[text]) {
                    seenTexts[text] = true;
                    texts.push(text);
                }
            }
        }
        if (texts.length === 0) {
            var altSelectors = ['.sbj', '.subtitle', '.coin-subtitle', '.h2', '.h3', '.h4'];
            for (var s = 0; s < altSelectors.length; s++) {
                var elements = headerElement.querySelectorAll(altSelectors[s]);
                for (var i = 0; i < elements.length; i++) {
                    var text = elements[i].textContent ? elements[i].textContent.trim() : '';
                    if (text && !seenTexts[text]) {
                        seenTexts[text] = true;
                        texts.push(text);
                    }
                }
            }
        }
        coinTitle = texts.join(' ');
    } else {
        var directSelectors = ['h2', 'h3', 'h4', '.sbj', '.subtitle', '.coin-subtitle'];
        var texts = [];
        var seenTexts = {};
        for (var s = 0; s < directSelectors.length; s++) {
            var elements = document.querySelectorAll(directSelectors[s]);
            for (var i = 0; i < elements.length; i++) {
                var parent = elements[i].closest('h1');
                if (!parent) {
                    var text = elements[i].textContent ? elements[i].textContent.trim() : '';
                    if (text && !seenTexts[text]) {
                        seenTexts[text] = true;
                        texts.push(text);
                    }
                }
            }
        }
        coinTitle = texts.join(' ');
    }
    data['coin_title'] = coinTitle;
    // ===== 4. ПАРСИМ ТАБЛИЦУ ТИРАЖЕЙ (.tabMintage) =====
    var mintName = '';
    var mintMark = '';
    var hasMarkColumn = false;
    var isHighlighted = false;
    var mintageDiv = document.querySelector('.tabMintage');
    if (mintageDiv) {
        var mintTable = mintageDiv.querySelector('table.tbl');
        if (!mintTable) mintTable = mintageDiv.querySelector('table');
        if (mintTable) {
            var markColumnIndex = -1;
            var nameColumnIndex = -1;
            var headerRows = mintTable.querySelectorAll('thead tr');
            // Запасной поиск строки заголовков (если thead нет)
            if (headerRows.length === 0) {
                var tmpRows = mintTable.querySelectorAll('tr');
                var foundHeader = [];
                for (var t3 = 0; t3 < tmpRows.length; t3++) {
                    if (tmpRows[t3].querySelectorAll('th').length > 0) {
                        foundHeader = [tmpRows[t3]];
                        break;
                    }
                }
                headerRows = foundHeader;
            }
            for (var h = 0; h < headerRows.length; h++) {
                var headerCells = headerRows[h].querySelectorAll('th');
                for (var c = 0; c < headerCells.length; c++) {
                    var headerText = headerCells[c].textContent.trim();
                    if (headerText === 'Знак') { markColumnIndex = c; hasMarkColumn = true; }
                    if (headerText === 'Монетный двор') { nameColumnIndex = c; }
                }
            }
            var allRows = mintTable.querySelectorAll('tbody tr, tr.slc, tr.sodd');
            var highlightedMint = '';
            var highlightedMark = '';
            var foundHighlighted = false;
            for (var r = 0; r < allRows.length; r++) {
                var row = allRows[r];
                var className = row.className ? row.className : '';
                if (className.indexOf('slc') !== -1 || className.indexOf('sodd') !== -1) {
                    var cells = row.querySelectorAll('th, td');
                    if (cells.length > 0) {
                        var nameIdx = nameColumnIndex !== -1 ? nameColumnIndex : 0;
                        if (nameIdx < cells.length) {
                            var nameCell = cells[nameIdx];
                            var cellText = nameCell.textContent.trim();
                            if (cellText && cellText !== 'Монетный двор') {
                                highlightedMint = cellText;
                                isHighlighted = true;
                                if (markColumnIndex !== -1 && markColumnIndex < cells.length) {
                                    var markCell = cells[markColumnIndex];
                                    var markText = markCell.textContent.trim();
                                    if (markText && !markText.match(/^[\\d,.]+$/) && markText !== '-' && markText !== '—') {
                                        highlightedMark = markText;
                                    }
                                }
                                foundHighlighted = true;
                                break;
                            }
                        }
                    }
                }
            }
            if (foundHighlighted && highlightedMint) {
                mintName = highlightedMint;
                mintMark = highlightedMark;
            } else {
                var rows2 = mintTable.querySelectorAll('tbody tr');
                for (var r = 0; r < rows2.length; r++) {
                    var cells = rows2[r].querySelectorAll('th, td');
                    if (cells.length > 0) {
                        var nameIdx = nameColumnIndex !== -1 ? nameColumnIndex : 0;
                        if (nameIdx < cells.length) {
                            var nameCell = cells[nameIdx];
                            var cellText = nameCell.textContent.trim();
                            if (cellText && cellText !== 'Монетный двор') {
                                mintName = cellText;
                                if (markColumnIndex !== -1 && markColumnIndex < cells.length) {
                                    var markCell = cells[markColumnIndex];
                                    var markText = markCell.textContent.trim();
                                    if (markText && !markText.match(/^[\\d,.]+$/) && markText !== '-' && markText !== '—') {
                                        mintMark = markText;
                                    }
                                }
                                break;
                            }
                        }
                    }
                }
            }
            // Запасной вариант: первая строка, где первая ячейка — не число и не заголовок
            if (!mintName) {
                var rows3 = mintTable.querySelectorAll('tr');
                for (var r = 0; r < rows3.length; r++) {
                    var cells = rows3[r].querySelectorAll('th, td');
                    if (cells.length < 2) continue;
                    var first = cells[0].textContent.trim();
                    if (!first || first === 'Монетный двор' || first.match(/^[\\d,.]+$/)) continue;
                    if (rows3[r].querySelectorAll('th').length > 0 && cells[1].textContent.trim() === 'Знак') continue;
                    mintName = first;
                    var second = cells[1].textContent.trim();
                    if (second && !second.match(/^[\\d,.]+$/) && second !== '-' && second !== '—') {
                        mintMark = second;
                    }
                    break;
                }
            }
        }
    }
    // Если двор не найден в тиражах — берём из основной таблицы
    if (!mintName && data['mint_name_raw']) {
        mintName = data['mint_name_raw'];
    }
    data['mint_name'] = mintName;
    data['mint_mark'] = mintMark;
    data['has_mark_column'] = hasMarkColumn;
    data['is_highlighted'] = isHighlighted;
    // ===== 5. ИЗОБРАЖЕНИЯ =====
    var images = document.querySelectorAll(
        '.gallery img, .coin-images img, img[id^="coin-img"], .photo-box img'
    );
    if (images.length >= 1) {
        var src1 = images[0].getAttribute('srcset') || images[0].src || '';
        data['obverse_image_url'] = src1.split(',')[0].split(' ')[0].trim();
    }
    if (images.length >= 2) {
        var src2 = images[1].getAttribute('srcset') || images[1].src || '';
        data['reverse_image_url'] = src2.split(',')[0].split(' ')[0].trim();
    }
    // ===== 6. ОПИСАНИЕ: ТОЛЬКО ШАПКА МОНЕТЫ (аверс/реверс НЕ парсятся) =====
    if (coinTitle) {
        data['coin_info'] = coinTitle;
    }
    // ===== 7. ГОД из h1 (если не нашёлся в таблице) =====
    if (!data.year) {
        var h1 = document.querySelector('h1');
        if (h1) {
            var m = h1.textContent.match(/(\\d{4})/);
            if (m) data.year = m[1];
        }
    }
    if (!data.year) {
        var m = window.location.pathname.match(/-(\\d{4})\\/?/);
        if (m) data.year = m[1];
    }
    console.log('=== CoinCollector: извлечено полей: ' + Object.keys(data).length + ' ===');
    console.log(data);
    return JSON.stringify(data);
})();
"""
        web_view.page().runJavaScript(extract_js, lambda result: self._process_ucoin_data(result))

    def _process_ucoin_data(self, json_result):
        """Обрабатывает данные UCOIN и заполняет ВСЕ поля формы.
        Режим ОБНОВЛЕНИЯ (_ucoin_update_mode=True):
        - каталожный номер НЕ перегенерируется (остаётся прежним);
        - автосохранения НЕТ — пользователь сам жмёт 💾 Сохранить.
        Режим ДОБАВЛЕНИЯ: каталожный номер генерируется один раз здесь."""
        self.logger.info("📥 _process_ucoin_data вызван")
        if hasattr(self, '_ucoin_timeout_timer'):
            try:
                self._ucoin_timeout_timer.stop()
            except Exception:
                pass
        try:
            if not json_result:
                self.logger.warning("⚠️ JS вернул пустой результат")
                self._ucoin_load_processed = True
                return
            try:
                import json as _json
                data = _json.loads(json_result) if isinstance(json_result, str) else json_result
            except Exception as e:
                self.logger.error(f"Ошибка парсинга JSON: {e}")
                self._ucoin_load_processed = True
                return
            if not data:
                self.logger.warning("⚠️ Пустые данные из UCOIN")
                self._ucoin_load_processed = True
                return
            self.logger.info(f"📊 Извлечено полей: {len(data)}: {list(data.keys())}")
            if not self.edit_mode:
                self.switch_to_edit_mode()
            filled = []
            update_mode = getattr(self, '_ucoin_update_mode', False)

            # === СТРАНА ===
            if data.get('country') and 'country' in self.edit_fields:
                combo = self.edit_fields['country']
                cname = str(data['country']).strip()
                idx = combo.findText(cname)
                if idx < 0:
                    cn_low = cname.lower()
                    for i in range(combo.count()):
                        item = combo.itemText(i).strip().lower()
                        if item and (item == cn_low or cn_low in item or item in cn_low):
                            idx = i
                            break
                if idx < 0:
                    try:
                        from database.models import Country
                        country = Country(name=cname)
                        self.db_manager.session.add(country)
                        self.db_manager.session.commit()
                        if hasattr(self, 'load_countries_to_combo'):
                            self.load_countries_to_combo()
                        idx = combo.findText(cname)
                        self.logger.info(f"➕ Создана страна: {cname}")
                    except Exception as e:
                        self.logger.error(f"Ошибка создания страны: {e}")
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    filled.append('страна')

            # === ПЕРИОД (после страны) ===
            if data.get('period') and 'period_id' in self.edit_fields:
                period_text = str(data['period']).strip()
                combo = self.edit_fields['period_id']
                idx = combo.findText(period_text)
                if idx < 0:
                    pl = period_text.lower()
                    for i in range(combo.count()):
                        it = combo.itemText(i).strip().lower()
                        if it and (it == pl or pl in it or it in pl):
                            idx = i
                            break
                if idx < 0:
                    try:
                        from database.models import Period
                        country_id = self.edit_fields['country'].currentData()
                        new_period = Period(name=period_text, country_id=country_id)
                        self.db_manager.session.add(new_period)
                        self.db_manager.session.commit()
                        if hasattr(self, 'load_periods_to_combo'):
                            self.load_periods_to_combo()
                        idx = combo.findText(period_text)
                        self.logger.info(f"➕ Создан период: {period_text}")
                    except Exception as e:
                        self.logger.error(f"Ошибка создания периода: {e}")
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    filled.append('период')

            # === НОМИНАЛ ===
            denom = data.get('denomination_value') or data.get('denomination')
            if denom and 'denomination_value' in self.edit_fields:
                denom_text = str(denom).strip()
                cur_word = (data.get('currency_text') or '').strip()
                if cur_word and cur_word.lower() not in denom_text.lower():
                    denom_text = f"{denom_text} {cur_word}".strip()
                self.edit_fields['denomination_value'].setText(denom_text)
                filled.append('номинал')

            # === ВАЛЮТА ===
            full_cur = (data.get('currency_name') or data.get('currency') or '').strip()
            short_cur = (data.get('currency_text') or '').strip()
            if (full_cur or short_cur) and 'currency' in self.edit_fields:
                combo = self.edit_fields['currency']
                idx = self._find_currency_index(combo, full_cur, short_cur)
                if idx < 0 and full_cur:
                    try:
                        from database.models import Currency
                        cur_obj = Currency(name=full_cur)
                        self.db_manager.session.add(cur_obj)
                        self.db_manager.session.commit()
                        self.load_currencies_to_combo()
                        idx = combo.findData(cur_obj.id)
                        self.logger.info(f"➕ Создана валюта: {full_cur}")
                    except Exception as e:
                        self.logger.error(f"Ошибка создания валюты: {e}")
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    filled.append('валюта')
                else:
                    self.logger.warning(f"⚠️ Валюта не найдена: {full_cur!r} / {short_cur!r}")

            # === ГОД ===
            year_val = None
            if data.get('year') and 'year' in self.edit_fields:
                try:
                    year_val = int(str(data['year']).strip())
                    w = self.edit_fields['year']
                    if hasattr(w, 'setValue'):
                        w.setValue(year_val)
                    else:
                        w.setText(str(year_val))
                    filled.append('год')
                except Exception:
                    pass

            # === ВЕК: из года, подбор к справочнику (римские: XXI и т.п.) ===
            if year_val and 'century' in self.edit_fields:
                century_num = (year_val - 1) // 100 + 1
                roman = self._century_to_roman(century_num)
                combo = self.edit_fields['century']
                idx = -1
                for cand in (roman, f"{roman} век", f"{roman} в.",
                             str(century_num), f"{century_num} век",
                             f"{century_num}-й век", f"{century_num} в."):
                    idx = combo.findText(cand)
                    if idx >= 0:
                        break
                if idx < 0 and roman:
                    for i in range(combo.count()):
                        if roman in combo.itemText(i).strip().upper():
                            idx = i
                            break
                if idx < 0:
                    for i in range(combo.count()):
                        if str(century_num) in combo.itemText(i):
                            idx = i
                            break
                if idx < 0:
                    combo.addItem(roman)
                    idx = combo.findText(roman)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    filled.append(f'век {century_num} ({combo.itemText(idx)})')
                self.logger.info(f"📅 Век из года {year_val}: {century_num} → '{combo.currentText()}'")

            # === МЕТАЛЛ ===
            if data.get('metal') and 'metal' in self.edit_fields:
                name, purity = self._parse_metal_name_purity(data['metal'])
                metal = self._find_or_create_metal(name, purity) if name else None
                if metal:
                    combo = self.edit_fields['metal']
                    idx = combo.findData(metal.id)
                    if idx < 0:
                        if hasattr(self, 'load_metals_to_combo'):
                            self.load_metals_to_combo()
                        idx = combo.findData(metal.id)
                    if idx < 0:
                        idx = combo.findText(metal.name)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        filled.append(f"металл: {data['metal']}")
                        self.logger.info(
                            f"⚙️ Металл установлен: id={metal.id}, {metal.name} "
                            f"(проба {purity}) из строки UCOIN {data['metal']!r}")
                    else:
                        self.logger.warning(f"⚠️ Металл не найден в комбобоксе: {name} {purity}")
                else:
                    self.logger.warning(f"⚠️ Не удалось определить металл из: {data['metal']!r}")

            # === МОНЕТНЫЙ ДВОР + ЗНАК ===
            mint_name = (data.get('mint_name') or '').strip()
            mint_mark = (data.get('mint_mark') or '').strip()
            if not mint_name and (data.get('mint_name_raw') or '').strip():
                raw = data['mint_name_raw'].strip()
                m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*$', raw)
                if m:
                    mint_name = m.group(1).strip()
                    mint_mark = mint_mark or m.group(2).strip()
                else:
                    mint_name = raw
            if mint_name or mint_mark:
                if 'mint' in self.edit_fields:
                    combo = self.edit_fields['mint']
                    idx = -1
                    if mint_name:
                        mn = mint_name.lower()
                        best, best_len = -1, -1
                        for i in range(combo.count()):
                            it = combo.itemText(i).lower()
                            if it and (it == mn or mn in it or it in mn):
                                if len(it) > best_len:
                                    best_len, best = len(it), i
                        idx = best
                    if idx < 0 and mint_name:
                        try:
                            from database.models import Mint
                            country_id = self.edit_fields['country'].currentData()
                            new_mint = Mint(name=mint_name, mark=mint_mark or '',
                                            country_id=country_id)
                            self.db_manager.session.add(new_mint)
                            self.db_manager.session.commit()
                            self.load_mints_to_combo()
                            idx = combo.findData(new_mint.id)
                            self.logger.info(f"➕ Создан монетный двор: {mint_name}")
                        except Exception as e:
                            self.logger.error(f"Ошибка создания монетного двора: {e}")
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        filled.append('монетный двор')
                    else:
                        self.logger.warning(f"⚠️ Монетный двор не установлен: {mint_name!r}")
                if mint_mark and 'mint_mark' in self.edit_fields:
                    self.edit_fields['mint_mark'].setText(mint_mark)
                    filled.append('знак МД')

            # === ГУРТ (тип) + ОПИСАНИЕ ГУРТА ===
            # Тип гурта (Рубчатый / Надпись...) → комбобокс «Гурт»
            edge_type = (data.get('edge') or '').strip()
            if edge_type and 'edge' in self.edit_fields:
                if self._set_ref_combo_or_create('edge', edge_type):
                    filled.append('гурт')
            # Описание гурта → поле «Описание гурта» ТОЛЬКО если строка есть на UCOIN,
            # иначе ставим прочерк «—»
            edge_desc = (data.get('edge_description') or '').strip()
            if 'edge_description' in self.edit_fields:
                if edge_desc:
                    self.edit_fields['edge_description'].setPlainText(edge_desc)
                    filled.append('описание гурта')
                else:
                    self.edit_fields['edge_description'].setPlainText('—')
                    filled.append('описание гурта: —')

            # === ФОРМА ===
            if data.get('shape') and 'shape' in self.edit_fields:
                if self._set_ref_combo_or_create('shape', data['shape']):
                    filled.append('форма')

            # === АВ/РЕВ ===
            if data.get('avrev') and 'avrev' in self.edit_fields:
                if self._set_ref_combo_or_create('avrev', data['avrev']):
                    filled.append('ав/рев')

            # === ТИП ВЫПУСКА ===
            if data.get('issue_type') and 'issue_type' in self.edit_fields:
                if self._set_ref_combo_or_create('issue_type', data['issue_type']):
                    filled.append('тип выпуска')

            # === ВЕС / ДИАМЕТР / ТОЛЩИНА ===
            for key, field in (('weight', 'weight'),
                               ('diameter', 'diameter'),
                               ('thickness', 'thickness')):
                if data.get(key) and field in self.edit_fields:
                    try:
                        val = float(str(data[key]).replace(',', '.').strip())
                        w = self.edit_fields[field]
                        if hasattr(w, 'setValue'):
                            w.setValue(val)
                        else:
                            w.setText(str(val))
                        filled.append(field)
                    except Exception:
                        pass

            # === ТИРАЖ ===
            if data.get('mintage') and 'mintage' in self.edit_fields:
                try:
                    m = int(str(data['mintage']).replace(' ', '').replace('\xa0', ''))
                    w = self.edit_fields['mintage']
                    if hasattr(w, 'setValue'):
                        w.setValue(m)
                    else:
                        w.setText(str(m))
                    filled.append('тираж')
                except Exception:
                    pass

            # === СОСТОЯНИЕ / РЕДКОСТЬ ===
            for key, field in (('condition', 'condition'), ('rarity', 'rarity')):
                if data.get(key) and field in self.edit_fields:
                    combo = self.edit_fields[field]
                    val = str(data[key]).strip()
                    idx = combo.findText(val)
                    if idx < 0:
                        vl = val.lower()
                        for i in range(combo.count()):
                            it = combo.itemText(i).lower()
                            if it and (vl in it or it in vl):
                                idx = i
                                break
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        filled.append(field)

            # === ОПИСАНИЕ МОНЕТЫ (только шапка) ===
            desc = data.get('coin_info') or data.get('description')
            if desc:
                if 'coin_info' in self.edit_fields:
                    self.edit_fields['coin_info'].setText(str(desc))
                    filled.append('описание')
                elif 'description' in self.edit_fields:
                    self.edit_fields['description'].setText(str(desc))
                    filled.append('описание')

            # === КАТАЛОЖНЫЙ НОМЕР: ТОЛЬКО в режиме добавления ===
            if not update_mode:
                try:
                    metal_name = data.get('metal')
                    if not metal_name and 'metal' in self.edit_fields:
                        metal_name = self.edit_fields['metal'].currentText()
                    new_catalog = self.db_manager.generate_catalog_number(metal_name)
                    if 'catalog_number' in self.edit_fields:
                        self.edit_fields['catalog_number'].setText(new_catalog)
                    filled.append(f'номер {new_catalog}')
                    self.logger.info(
                        f"🔢 Каталог для новой монеты: {new_catalog} (металл: {metal_name})")
                except Exception as e:
                    self.logger.error(f"Ошибка генерации номера: {e}")
            else:
                cur_num = ''
                if 'catalog_number' in self.edit_fields:
                    cur_num = self.edit_fields['catalog_number'].text()
                self.logger.info(f"ℹ️ Режим обновления: каталожный номер сохранён: {cur_num}")

            # === ССЫЛКА UCOIN ===
            if data.get('ucid') and 'ucoin_url' in self.edit_fields:
                if not self.edit_fields['ucoin_url'].text().strip():
                    self.edit_fields['ucoin_url'].setText(
                        f"https://ru.ucoin.net/coin/?ucid={data['ucid']}")
                    filled.append('ucoin_url')

            self.logger.info(f"✅ Заполнено: {filled}")
            self._ucoin_load_processed = True

            # === ЗАВЕРШЕНИЕ: сброс флага режима обновления ===
            if update_mode:
                self._ucoin_update_mode = False
                self.logger.info("✅ Данные с UCOIN заполнены в форму — нажмите 💾 Сохранить")
                try:
                    from PySide6.QtWidgets import QApplication
                    for w in QApplication.topLevelWidgets():
                        if w.__class__.__name__ == 'MainWindow':
                            sb = getattr(w, 'status_bar', None)
                            if sb is None:
                                try:
                                    sb = w.statusBar()
                                except Exception:
                                    sb = None
                            if sb is not None and hasattr(sb, 'showMessage'):
                                sb.showMessage(
                                    "✅ Данные с UCOIN заполнены — нажмите 💾 Сохранить", 5000)
                            break
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"Ошибка обработки данных UCOIN: {e}")
            import traceback
            traceback.print_exc()
            self._ucoin_load_processed = True
            self._ucoin_update_mode = False
        finally:
            # Гарантированный сброс флага занятости — следующий парсинг не блокируется
            self._ucoin_fill_running = False

    @staticmethod
    def _normalize_metal_name(text):
        """Нормализует название металла: убирает цифры, пробу, символы."""
        import re as _re
        t = (text or '').lower()
        t = _re.sub(r'[\d.,‰%°]', ' ', t)
        t = _re.sub(r'(пробы|проба|proof|fine|pure)', ' ', t)
        t = _re.sub(r'\s+', ' ', t).strip()
        return t

    def _find_metal_index(self, combo, parsed):
        """Подбирает индекс металла в комбобоксе."""
        if not parsed:
            return -1
        parsed = parsed.strip()
        parsed_n = self._normalize_metal_name(parsed)
        parsed_digits = ''.join(ch for ch in parsed if ch.isdigit())
        idx = combo.findText(parsed)
        if idx >= 0:
            return idx
        if parsed_n and parsed_digits:
            for i in range(combo.count()):
                item = combo.itemText(i)
                item_digits = ''.join(ch for ch in item if ch.isdigit())
                if item_digits == parsed_digits and self._normalize_metal_name(item) == parsed_n:
                    return i
        if parsed_n:
            for i in range(combo.count()):
                if self._normalize_metal_name(combo.itemText(i)) == parsed_n:
                    return i
        low = parsed.lower()
        for i in range(combo.count()):
            item_low = combo.itemText(i).lower()
            if low in item_low or item_low in low:
                return i
        return -1

    def _find_or_create_metal(self, name, purity):
        """Ищет металл в БД по ТОЧНОЙ паре имя+проба. Если нет — создаёт."""
        from database.models import Metal
        name_l = (name or '').strip().lower()
        if not name_l:
            return None

        def norm_purity(p):
            if not p:
                return ''
            p = str(p).replace(',', '.').strip()
            try:
                v = float(p)
                return str(int(round(v * 1000))) if v <= 1.0 else str(int(round(v)))
            except ValueError:
                return p.strip()

        metals = self.db_manager.session.query(Metal).all()
        if purity:
            for m in metals:
                if (m.name or '').strip().lower() == name_l and norm_purity(m.purity) == purity:
                    return m
            metal = Metal(name=name.strip(), purity=purity)
            self.db_manager.session.add(metal)
            self.db_manager.session.commit()
            self.logger.info(f"➕ Создан металл в справочнике: {name} {purity}")
            return metal
        for m in metals:
            if (m.name or '').strip().lower() == name_l:
                return m
        for m in metals:
            mn = (m.name or '').strip().lower()
            if mn and (name_l in mn or mn in name_l):
                return m
        return None

    def _set_ref_combo_or_create(self, key, text, field_key=None):
        """Устанавливает значение в комбобокс справочника (без создания записей)."""
        if not text or key not in self.edit_fields:
            return False
        combo = self.edit_fields[key]
        if not hasattr(combo, 'findText'):
            return False
        text = str(text).strip()
        if not text:
            return False

        def norm(s):
            return (s or '').replace('–', '-').replace('—', '-').replace('\u00a0', ' ')

        text_norm = norm(text).lower()
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return True
        for i in range(combo.count()):
            item_text = norm(combo.itemText(i)).lower()
            if item_text and (item_text in text_norm or text_norm in item_text):
                combo.setCurrentIndex(i)
                return True
        self.logger.warning(f"⚠️ Не найдено в справочнике {key}: '{text}'")
        return False

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        top_panel = self._create_top_panel()
        layout.addWidget(top_panel)
        self.coin_stack = QStackedWidget()
        self.coin_view_widget = CoinViewWidget(self)
        self.coin_stack.addWidget(self.coin_view_widget)
        self.coin_edit_widget = CoinEditWidget(self.db_manager, self)
        self.coin_edit_widget.parent_tab = self
        self.coin_stack.addWidget(self.coin_edit_widget)
        layout.addWidget(self.coin_stack)
        self.edit_fields['country'].currentIndexChanged.connect(self.on_country_changed)
        # ВАЖНО: кнопка fill_from_ucoin_btn УЖЕ подключена внутри
        # _create_top_panel (через make_btn). Дублирующий connect здесь НЕ НУЖЕН:
        # из-за него кнопка срабатывала дважды (двойной парсинг и каталог +1).
        # Строку "self.fill_from_ucoin_btn.clicked.connect(self.fill_from_ucoin)"
        # здесь НЕ писать вообще (ни с--, ни с#, ни без ничего).
        print("=" * 60)
        print("ВЫЗОВ load_all_combos ИЗ init_ui ПОСЛЕ СОЗДАНИЯ ВИДЖЕТОВ")
        self.load_all_combos()
        print("=" * 60)

    def _create_top_panel(self):
        """Создает верхнюю панель: кнопки-иконки растянуты на всю ширину"""
        from PySide6.QtWidgets import QSizePolicy
        top_panel = QFrame()
        top_panel.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        top_panel.setLayout(layout)
        icon_btn_style = "font-size: 18px;"

        def make_btn(text, tip, slot, hidden=False):
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.setStyleSheet(icon_btn_style)
            btn.setMinimumHeight(32)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(slot)
            if hidden:
                btn.hide()
            layout.addWidget(btn)
            return btn

        self.view_mode_btn = make_btn("👁️", "Просмотр", self.switch_to_view_mode)
        self.view_mode_btn.setEnabled(False)
        self.edit_mode_btn = make_btn("✏️", "Редактировать", self.switch_to_edit_mode)
        self.copy_btn = make_btn("📋", "Копия (каталог +1)", self.copy_current_coin)
        self.fill_from_ucoin_btn = make_btn("📥", "Заполнить из UCOIN", self.fill_from_ucoin, hidden=True)
        self.scan_photos_btn = make_btn(
            "📷", "Сканировать монету: аверс и реверс (автокроп +1 мм)",
            self.scan_coin_photos, hidden=True)
        self.open_ucoin_btn = make_btn("🔗", "Открыть на UCOIN", self.open_ucoin_url)
        self.save_btn = make_btn("💾", "Сохранить", self.save_changes, hidden=True)
        self.cancel_btn = make_btn("❌", "Отмена", self.cancel_edit, hidden=True)
        self.open_meshok_btn = QPushButton("📦")
        self.open_meshok_btn.setToolTip("Открыть на Мешок")
        self.open_meshok_btn.clicked.connect(self.open_meshok_url)
        self.open_meshok_btn.hide()
        return top_panel

    def _set_top_buttons_size(self, w, h):
        """Устанавливает размер кнопок верхней панели"""
        for btn in (self.view_mode_btn, self.edit_mode_btn, self.copy_btn,
                    self.fill_from_ucoin_btn, self.open_ucoin_btn, self.open_meshok_btn,
                    self.save_btn, self.cancel_btn):
            if btn is not None:
                btn.setFixedSize(w, h)

    def update_mode_buttons(self):
        """Подсвечивает кнопку активного режима"""
        t = {}
        try:
            t = self.parent().parent_window.theme_manager.current_theme
        except Exception:
            pass
        accent = t.get('accent', '#6c63ff')
        btn_bg = t.get('button', '#16213e')
        border = t.get('border', '#2a2a4a')
        text = t.get('text', '#e4e4ef')
        active = f"""
            QPushButton {{
                background-color: {accent};
                color: #ffffff;
                border: 1px solid {accent};
                border-radius: 6px;
                font-weight: bold;
            }}
        """
        inactive = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QPushButton:hover {{ border-color: {accent}; }}
        """
        self.view_mode_btn.setStyleSheet(active if not self.edit_mode else inactive)
        self.edit_mode_btn.setStyleSheet(active if self.edit_mode else inactive)

    def show_coin_info(self, coin):
        """Отображает информацию о монете"""
        self.clear_view()
        if coin and coin.id:
            fresh_coin = self.db_manager.get_coin(coin.id)
            if fresh_coin:
                coin = fresh_coin
        self.current_coin = coin
        if self.edit_mode:
            self.switch_to_view_mode()
        self.coin_view_widget.update_display(coin, self.db_manager)
        self.view_mode_btn.setEnabled(coin is not None)
        self.edit_mode_btn.setEnabled(coin is not None)
        self.copy_btn.setEnabled(coin is not None)
        self.coin_stack.setCurrentIndex(0)

    def switch_to_edit_mode(self):
        """Переключает в режим редактирования"""
        if not self.current_coin:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите монету")
            return
        self.edit_mode = True
        self.view_mode_btn.setEnabled(True)
        self.edit_mode_btn.setEnabled(False)
        self.save_btn.show()
        self.cancel_btn.show()
        self.fill_from_ucoin_btn.show()
        self.scan_photos_btn.show()
        fresh_coin = self.db_manager.get_coin(self.current_coin.id)
        if fresh_coin:
            self.current_coin = fresh_coin
        self.coin_edit_widget.rebuild_custom_fields()
        self.coin_edit_widget.load_coin_to_form(self.current_coin)
        self.load_custom_values_to_form(self.current_coin)
        self.coin_edit_widget.coin_edit_empty_label.hide()
        self.coin_edit_widget.coin_edit_form_container.show()
        self.coin_stack.setCurrentIndex(1)
        self.coin_stack.updateGeometry()
        self.updateGeometry()
        QApplication.processEvents()
        QTimer.singleShot(0, self.coin_edit_widget._fit_fields_to_width)

    def switch_to_view_mode(self):
        """Переключает в режим просмотра"""
        self.edit_mode = False
        self.view_mode_btn.setEnabled(False)
        self.edit_mode_btn.setEnabled(True)
        self.save_btn.hide()
        self.cancel_btn.hide()
        self.fill_from_ucoin_btn.hide()
        self.scan_photos_btn.hide()
        if self.current_coin:
            self.coin_view_widget.update_display(self.current_coin, self.db_manager)
            self.coin_view_widget.coin_empty_label.hide()
            self.coin_view_widget.coin_detail_container.show()
        self.coin_edit_widget.coin_edit_empty_label.hide()
        self.coin_edit_widget.coin_edit_form_container.hide()
        self.coin_stack.setCurrentIndex(0)
        self.coin_stack.updateGeometry()
        self.updateGeometry()
        QApplication.processEvents()

    def add_new_coin(self):
        """Создает новую монету"""
        self.clear_view()
        self.current_coin = None
        self.edit_mode = True
        self.view_mode_btn.setEnabled(True)
        self.edit_mode_btn.setEnabled(False)
        self.save_btn.show()
        self.cancel_btn.show()
        self.coin_edit_widget.rebuild_custom_fields()
        self.coin_edit_widget.clear_edit_form()
        for widget in self.custom_edit_fields.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(0)
            elif isinstance(widget, QDateEdit):
                widget.setDate(QDate.currentDate())
                widget.setSpecialValueText("Не указана")
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QTextEdit):
                widget.clear()
        self.coin_stack.setCurrentIndex(1)
        self.coin_stack.updateGeometry()
        self.updateGeometry()

    def cancel_edit(self):
        """Отменяет редактирование"""
        self.save_btn.hide()
        self.cancel_btn.hide()
        self.fill_from_ucoin_btn.hide()
        if self.current_coin:
            self.switch_to_view_mode()
        else:
            self.edit_mode = False
            self.view_mode_btn.setEnabled(False)
            self.edit_mode_btn.setEnabled(True)
            self.coin_stack.setCurrentIndex(0)
            if self.parent() and hasattr(self.parent(), 'parent_window'):
                self.parent().parent_window.table.clearSelection()

    def load_status_combo(self):
        """Загружает справочник статусов в комбобокс"""
        if 'status' not in self.edit_fields:
            return
        combo = self.edit_fields['status']
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        statuses = self.db_manager.session.query(StandardReference).filter_by(
            field_key='status'
        ).order_by(StandardReference.sort_order).all()
        for status in statuses:
            combo.addItem(status.name, status.id)
        combo.blockSignals(False)
        self.logger.debug(f"Загружено статусов: {len(statuses)}")

    def load_all_combos(self):
        """Загружает все комбобоксы"""
        self.load_countries_to_combo()
        self.load_currencies_to_combo()
        self.load_mints_to_combo()
        self.load_metals_to_combo()
        self.load_edges_to_combo()
        self.load_purchase_countries_to_combo()
        self.load_periods_to_combo()
        self.load_condition_combo()
        self.load_rarity_combo()
        self.load_storage_location_combo()
        self.load_issue_type_combo()
        self.load_avrev_combo()
        self.load_acquisition_type_combo()
        self.load_status_combo()
        self.load_shape_combo()

    def save_changes(self):
        """Сохраняет изменения или создает новую монету"""
        try:
            main_window = None
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
            suppress = getattr(main_window, '_suppress_messages', False) if main_window else False
            self.logger.info("💾 СОХРАНЕНИЕ МОНЕТЫ")
            if not hasattr(self, 'coin_edit_widget') or self.coin_edit_widget is None:
                if not suppress:
                    QMessageBox.warning(self, "Ошибка", "Форма редактирования не инициализирована")
                return
            country_text = self.edit_fields['country'].currentText().strip()
            if not country_text:
                if not suppress:
                    QMessageBox.warning(self, "Предупреждение", "Укажите страну")
                return
            if not self.edit_fields['currency'].currentData():
                if not suppress:
                    QMessageBox.warning(self, "Предупреждение", "Выберите валюту")
                return
            if self.edit_fields['country'].currentData():
                country = self.db_manager.session.query(Country).get(
                    self.edit_fields['country'].currentData())
            else:
                country = self.db_manager.get_or_create_country(country_text)
            if not country:
                if not suppress:
                    QMessageBox.warning(self, "Ошибка", "Не удалось определить страну")
                return
            coin_data = self._collect_coin_data(country)
            if not coin_data:
                self.logger.error("❌ Не удалось собрать данные")
                return
            if self.current_coin and self.current_coin.id:
                self._save_coin_images(self.current_coin.id, coin_data)
                success = self.db_manager.update_coin(self.current_coin.id, coin_data)
                if success:
                    # === ГЛАВНОЕ ИСПРАВЛЕНИЕ: сбрасываем кэш объектов сессии,
                    # чтобы таблица и панель не показывали СТАРЫЕ (донорские) данные ===
                    try:
                        self.db_manager.session.expire_all()
                    except Exception:
                        pass
                    self.logger.info("✅ Монета обновлена")
                    if not suppress:
                        QMessageBox.information(self, "Успех", "Монета обновлена")
                    self.current_coin = self.db_manager.get_coin(self.current_coin.id)
                else:
                    if not suppress:
                        QMessageBox.critical(self, "Ошибка", "Не удалось обновить монету")
                    return
            else:
                new_id = self.db_manager.add_coin(coin_data)
                if new_id:
                    # === Сбрасываем кэш сессии после создания ===
                    try:
                        self.db_manager.session.expire_all()
                    except Exception:
                        pass
                    if not suppress:
                        QMessageBox.information(self, "Успех", f"Монета добавлена с ID {new_id}")
                    self._save_coin_images(new_id, coin_data)
                    self.current_coin = self.db_manager.get_coin(new_id)
                else:
                    if not suppress:
                        QMessageBox.critical(self, "Ошибка", "Не удалось добавить монету")
                    return
            self.switch_to_view_mode()
            if self.parent() and hasattr(self.parent(), 'parent_window'):
                main_window = self.parent().parent_window
                if main_window:
                    main_window.load_coins()
                    main_window.load_country_tree(preserve_expanded=True)
                    if self.current_coin:
                        main_window.select_coin_by_id(self.current_coin.id)
            if self.current_coin:
                self.coin_view_widget.update_display(self.current_coin, self.db_manager)
            if main_window and hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage("✅ Монета сохранена", 3000)
        except Exception as e:
            self.logger.error(f"❌ Ошибка при сохранении: {e}")
            import traceback
            traceback.print_exc()
            try:
                if not suppress:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить монету:\n{e}")
            except Exception:
                pass

    def _collect_coin_data(self, country):
        """Собирает данные из формы редактирования"""
        try:
            data = {
                'country_id': country.id,
                'catalog_number': self.edit_fields['catalog_number'].text().strip() or None,
                'denomination_value': self.edit_fields['denomination_value'].text().strip() or None,
                'currency_id': self.edit_fields['currency'].currentData(),
                'year': self.edit_fields['year'].value() if self.edit_fields['year'].value() != 0 else None,
                'century': self.edit_fields['century'].currentText() or None,
                'mint_id': self.edit_fields['mint'].currentData(),
                'mint_mark': self.edit_fields['mint_mark'].text().strip() or None,
                'metal_id': self.edit_fields['metal'].currentData(),
                'weight': self.edit_fields['weight'].value() if self.edit_fields['weight'].value() != 0 else None,
                'diameter': self.edit_fields['diameter'].value() if self.edit_fields['diameter'].value() != 0 else None,
                'edge_id': self.edit_fields['edge'].currentData(),
                'edge_description': self.edit_fields['edge_description'].toPlainText().strip() or None,
                'condition_id': self.edit_fields['condition'].currentData(),
                'rarity_id': self.edit_fields['rarity'].currentData(),
                'shape_id': self.edit_fields['shape'].currentData(),
                'issue_type_id': self.edit_fields['issue_type'].currentData(),
                'avrev_id': self.edit_fields['avrev'].currentData(),
                'status_id': self.edit_fields['status'].currentData(),
                'acquisition_type_id': self.edit_fields['acquisition_type'].currentData(),
                'storage_location_id': self.edit_fields['storage_location'].currentData(),
                'purchase_date': self.edit_fields['purchase_date'].date().toPython() if self.edit_fields['purchase_date'].date() else None,
                'purchase_price': self.edit_fields['purchase_price'].value() if self.edit_fields['purchase_price'].value() != 0 else None,
                'purchase_where': self.edit_fields['purchase_where'].currentText().strip() or None,
                'purchase_country_id': self.edit_fields['purchase_country'].currentData(),
                'acquisition_type': self.edit_fields['acquisition_type'].currentText() or None,
                'purchase_info': self.edit_fields['purchase_info'].toPlainText().strip() or None,
                'coin_info': self.edit_fields['coin_info'].toPlainText().strip() or None,
                'ucoin_url': self.edit_fields['ucoin_url'].text().strip() or None,
                'meshok_url': self.edit_fields['meshok_url'].text().strip() or None,
                'market_price': self.edit_fields['market_price'].value() if self.edit_fields['market_price'].value() != 0 else None,
                'market_price_date': self.edit_fields['market_price_date'].date().toPython() if self.edit_fields['market_price_date'].date() else None,
                'period_id': self.edit_fields['period_id'].currentData(),
                'quantity': self.edit_fields.get('quantity', 1) if hasattr(self, 'edit_fields') and 'quantity' in self.edit_fields else 1,
            }
            if self.edit_fields['status'].currentData():
                data['status_id'] = self.edit_fields['status'].currentData()
            elif self.edit_fields['status'].currentText():
                data['status'] = self.edit_fields['status'].currentText()
            custom_data = self.collect_custom_values()
            if custom_data:
                data['custom_data'] = json.dumps(custom_data, ensure_ascii=False)
            if data.get('condition_id'):
                ref = self.db_manager.session.query(StandardReference).get(data['condition_id'])
                if ref:
                    data['condition'] = ref.value
            if data.get('rarity_id'):
                ref = self.db_manager.session.query(StandardReference).get(data['rarity_id'])
                if ref:
                    data['rarity'] = ref.value
            if data.get('status_id'):
                ref = self.db_manager.session.query(StandardReference).get(data['status_id'])
                if ref:
                    data['status'] = ref.value
            return data
        except Exception as e:
            self.logger.error(f"Ошибка при сборе данных: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_coin_images(self, coin_id, coin_data):
        """Сохраняет изображения для существующей монеты"""
        try:
            images_dir = paths.get_data_dir() / "coin_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            obverse_widget = self.coin_edit_widget.edit_obverse_image
            if obverse_widget and obverse_widget.current_pixmap and not obverse_widget.current_pixmap.isNull():
                pixmap = obverse_widget.current_pixmap
                filename = f"coin_{coin_id}_obverse.png"
                dest_path = images_dir / filename
                if dest_path.exists():
                    try:
                        dest_path.unlink()
                    except Exception:
                        pass
                pixmap.save(str(dest_path))
                rel_path = str(dest_path.relative_to(paths.get_root_dir()))
                coin_data['obverse_image'] = rel_path
                obverse_widget.image_path = rel_path
            else:
                coin_data['obverse_image'] = None
            reverse_widget = self.coin_edit_widget.edit_reverse_image
            if reverse_widget and reverse_widget.current_pixmap and not reverse_widget.current_pixmap.isNull():
                pixmap = reverse_widget.current_pixmap
                filename = f"coin_{coin_id}_reverse.png"
                dest_path = images_dir / filename
                if dest_path.exists():
                    try:
                        dest_path.unlink()
                    except Exception:
                        pass
                pixmap.save(str(dest_path))
                rel_path = str(dest_path.relative_to(paths.get_root_dir()))
                coin_data['reverse_image'] = rel_path
                reverse_widget.image_path = rel_path
            else:
                coin_data['reverse_image'] = None
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении изображений: {e}")
            import traceback
            traceback.print_exc()

    def _save_single_image(self, image_path, coin_id, side):
        """Сохраняет одно изображение в папку coin_images"""
        return self._save_image_to_file(image_path, coin_id, side)

    def _save_image_to_file(self, image_path, coin_id, side):
        """Сохраняет изображение в папку coin_images и возвращает относительный путь"""
        if not image_path:
            return None
        try:
            from pathlib import Path
            import shutil
            images_dir = paths.get_data_dir() / "coin_images"
            images_dir.mkdir(parents=True, exist_ok=True)
            filename = f"coin_{coin_id}_{side}.png"
            dest_path = images_dir / filename
            src_path = Path(image_path)
            if not src_path.exists():
                self.logger.error(f"❌ Файл не найден: {image_path}")
                return None
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            shutil.copy2(src_path, dest_path)
            rel_path = str(dest_path.relative_to(paths.get_root_dir()))
            return rel_path
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении изображения: {e}")
            return None

    def _save_image_to_file_old(self, image_path, coin_id, side):
        """Старый метод, оставлен для совместимости"""
        return self._save_image_to_file(image_path, coin_id, side)

    def copy_current_coin(self):
        """Копирует текущую монету"""
        if not self.current_coin:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите монету")
            return
        try:
            all_coins = self.db_manager.session.query(Coin.catalog_number).all()
            max_number = 0
            max_catalog = None
            max_digits = 0
            for (catalog,) in all_coins:
                if catalog:
                    match = re.search(r'(\d+)', catalog)
                    if match:
                        num = int(match.group(1))
                        if num > max_number:
                            max_number = num
                            max_catalog = catalog
                            max_digits = len(match.group(1))
            new_number = max_number + 1
            if max_catalog:
                prefix = re.sub(r'\d+', '', max_catalog)
                new_catalog = f"{prefix}{str(new_number).zfill(max_digits)}"
            else:
                new_catalog = str(new_number)
            possible_attrs = [
                'country_id', 'currency_id', 'mint_id', 'metal_id', 'edge_id', 'period_id',
                'denomination_value', 'currency', 'century', 'year',
                'mint', 'mint_mark', 'weight', 'diameter', 'shape',
                'edge_description', 'condition', 'rarity', 'storage_location',
                'issue_type', 'avrev', 'purchase_date', 'purchase_price',
                'purchase_place', 'purchase_where', 'purchase_info',
                'purchase_country_id', 'acquisition_type', 'sale_price',
                'obverse_description', 'reverse_description', 'status', 'quantity', 'coin_info',
                'custom_data',
                'condition_id', 'rarity_id', 'shape_id', 'issue_type_id', 'avrev_id',
                'status_id', 'acquisition_type_id', 'storage_location_id'
            ]
            coin_data = {}
            for attr in possible_attrs:
                if hasattr(self.current_coin, attr):
                    value = getattr(self.current_coin, attr)
                    if value is not None:
                        coin_data[attr] = value
            coin_data['catalog_number'] = new_catalog
            new_id = self.db_manager.add_coin(coin_data)
            if self.parent() and hasattr(self.parent(), 'parent_window'):
                self.parent().parent_window.load_coins()
                self.parent().parent_window.load_country_tree(preserve_expanded=True)
                QTimer.singleShot(500, lambda: self.parent().parent_window.select_coin_by_id(new_id))
            QMessageBox.information(self, "Успех", f"Монета скопирована\nНовый ID: {new_id}\nКаталог: {new_catalog}")
        except Exception as e:
            self.logger.error(f"Ошибка при копировании: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось копировать монету:\n{e}")

    def open_references(self, ref_type):
        """Открывает единое окно справочников"""
        ref_map = {
            self.REF_CURRENCY: 0,
            self.REF_MINT: 1,
            self.REF_METAL: 4,
            self.REF_EDGE: 5,
            self.REF_PURCHASE_COUNTRY: 6,
            self.REF_PERIOD: 7,
            self.REF_STATUS: 9,
            self.REF_CONDITION: 9,
            self.REF_RARITY: 9,
            self.REF_SHAPE: 9,
            self.REF_ISSUE_TYPE: 9,
            self.REF_AVREV: 9,
            self.REF_ACQUISITION_TYPE: 9,
            self.REF_STORAGE_LOCATION: 9,
        }
        dialog = ReferencesDialog(self.db_manager, self, ref_map.get(ref_type, 0))
        if dialog.exec():
            if ref_type == self.REF_PURCHASE_COUNTRY:
                self.load_purchase_countries_to_combo()
            elif ref_type == self.REF_PERIOD:
                self.load_periods_to_combo()
            else:
                self.load_all_combos()

    def load_countries_to_purchase_combo(self):
        """Загружает страны приобретения в комбобокс"""
        if hasattr(self, 'edit_fields') and 'purchase_country' in self.edit_fields:
            combo = self.edit_fields['purchase_country']
            combo.clear()
            combo.addItem("—", None)
            for country in self.db_manager.get_all_purchase_countries():
                combo.addItem(country.name, country.id)

    def load_countries_to_combo(self):
        """Загружает страны в комбобокс"""
        if hasattr(self, 'edit_fields') and 'country' in self.edit_fields:
            combo = self.edit_fields['country']
            combo.clear()
            for country in self.db_manager.get_all_countries():
                combo.addItem(country.name, country.id)

    def on_country_changed(self, index):
        """Обработчик изменения страны (обновляет список периодов)"""
        if hasattr(self, 'edit_fields') and 'period_id' in self.edit_fields:
            self.load_periods_to_combo()

    def open_ucoin_url(self):
        """Открывает ссылку на UCOIN в браузере"""
        if not self.current_coin:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите монету")
            return
        url = getattr(self.current_coin, 'ucoin_url', None)
        if not url:
            QMessageBox.warning(self, "Предупреждение", "Ссылка на UCOIN не задана для этой монеты")
            return
        self._open_url_in_browser(url)

    def open_meshok_url(self):
        """Открывает ссылку на Meshok в браузере"""
        if not self.current_coin:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите монету")
            return
        url = getattr(self.current_coin, 'meshok_url', None)
        if not url:
            search_parts = []
            if self.current_coin.country:
                search_parts.append(self.current_coin.country.name)
            if self.current_coin.denomination_value:
                search_parts.append(self.current_coin.denomination_value)
            if self.current_coin.year:
                search_parts.append(str(self.current_coin.year))
            if search_parts:
                search_query = " ".join(search_parts)
                from urllib.parse import quote
                url = f"https://meshok.net/listing?good=252&opt=3&search={quote(search_query)}&sort=cur_price"
            else:
                QMessageBox.warning(self, "Предупреждение", "Не удалось сформировать ссылку для поиска")
                return
        self._open_url_in_browser(url)

    def _open_url_in_browser(self, url):
        """Открывает URL во встроенном браузере"""
        main_window = self.parent().parent_window if hasattr(self.parent(), 'parent_window') else None
        if not main_window:
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
        if main_window and hasattr(main_window, 'center_tab_widget'):
            for i in range(main_window.center_tab_widget.count()):
                if "Браузер" in main_window.center_tab_widget.tabText(i):
                    main_window.center_tab_widget.setCurrentIndex(i)
                    browser = main_window.center_tab_widget.widget(i)
                    if hasattr(browser, 'add_new_tab'):
                        browser.add_new_tab(url)
                    elif hasattr(browser, 'web_view'):
                        browser.web_view.setUrl(QUrl(url))
                    break
            else:
                import webbrowser
                webbrowser.open(url)
        else:
            import webbrowser
            webbrowser.open(url)

    def clear_view(self):
        """Очищает вид просмотра"""
        if hasattr(self, 'coin_view_widget'):
            if hasattr(self.coin_view_widget, 'custom_fields_layout'):
                while self.coin_view_widget.custom_fields_layout.count():
                    child = self.coin_view_widget.custom_fields_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            if hasattr(self.coin_view_widget, 'custom_value_labels'):
                self.coin_view_widget.custom_value_labels.clear()

    def _load_mintage_data(self, web_view):
        """Загружает данные о монетном дворе из вкладки #Mintage"""
        current_url = web_view.url().toString()
        if '#' in current_url:
            current_url = current_url.split('#')[0]
        mintage_url = current_url + '#Mintage'
        main_window = None
        from PySide6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break
        if not main_window or not hasattr(main_window, 'center_tab_widget'):
            return
        browser = None
        for i in range(main_window.center_tab_widget.count()):
            tab_text = main_window.center_tab_widget.tabText(i)
            if "Браузер" in tab_text:
                browser = main_window.center_tab_widget.widget(i)
                break
        if not browser:
            return
        mintage_view = None
        if hasattr(self, '_mintage_views'):
            for view in self._mintage_views:
                try:
                    url = view.url().toString()
                    if '#Mintage' in url:
                        mintage_view = view
                        break
                except Exception:
                    pass
        if not mintage_view:
            mintage_view = browser.add_new_tab(mintage_url, switch_to=False)
            if not mintage_view:
                return
            if not hasattr(self, '_mintage_views'):
                self._mintage_views = []
            self._mintage_views.append(mintage_view)
        coin_tab = self
        self._mintage_processed = False
        self._mintage_message_shown = False
        self._mintage_timeout_timer = QTimer()
        self._mintage_timeout_timer.setSingleShot(True)

        def on_mintage_page_loaded(ok):
            if coin_tab._mintage_processed:
                return
            if not ok:
                coin_tab._mintage_processed = True
                if hasattr(coin_tab, '_mintage_timeout_timer'):
                    coin_tab._mintage_timeout_timer.stop()
                return
            try:
                mintage_view.loadFinished.disconnect(on_mintage_page_loaded)
            except RuntimeError:
                pass
            QTimer.singleShot(1000, extract_mintage_data)

        def extract_mintage_data():
            if coin_tab._mintage_processed:
                return
            mintage_js = """
            (function() {
                var result = { mints: [], mint_from_title: '', mark_from_title: '', coin_title: '' };
                var titleElement = document.querySelector('.h h4');
                if (titleElement) {
                    result.coin_title = titleElement.textContent.trim();
                    var titleText = result.coin_title;
                    var match = titleText.match(/Отметка монетного двора:\\s*[«"']([^"']+)[«"']\\s*-\\s*([^)]+)/);
                    if (match) {
                        result.mark_from_title = match[1].trim();
                        result.mint_from_title = match[2].trim();
                    } else {
                        var match2 = titleText.match(/[«"']([^"']+)[«"']/);
                        if (match2) {
                            result.mark_from_title = match2[1].trim();
                        }
                    }
                }
                var mintageTable = document.querySelector('.tabMintage table.tbl');
                if (!mintageTable) {
                    var tables = document.querySelectorAll('table.tbl');
                    for (var i = 0; i < tables.length; i++) {
                        var text = tables[i].innerText;
                        if (text.indexOf('Монетный двор') !== -1 && text.indexOf('Знак') !== -1) {
                            mintageTable = tables[i];
                            break;
                        }
                    }
                }
                if (mintageTable) {
                    var rows = mintageTable.querySelectorAll('tbody tr');
                    var headers = [];
                    var headerRow = mintageTable.querySelector('thead tr');
                    if (headerRow) {
                        var thCells = headerRow.querySelectorAll('th');
                        for (var i2 = 0; i2 < thCells.length; i2++) {
                            headers.push(thCells[i2].textContent.trim());
                        }
                    }
                    if (headers.length === 0) {
                        var allRows = mintageTable.querySelectorAll('tr');
                        for (var r = 0; r < allRows.length; r++) {
                            var cells = allRows[r].querySelectorAll('th, td');
                            var rowText = '';
                            for (var c = 0; c < cells.length; c++) {
                                rowText += cells[c].textContent.trim() + '|';
                            }
                            if (rowText.indexOf('Монетный двор') !== -1) {
                                for (var c2 = 0; c2 < cells.length; c2++) {
                                    headers.push(cells[c2].textContent.trim());
                                }
                                break;
                            }
                        }
                    }
                    var dataRows = mintageTable.querySelectorAll('tbody tr');
                    if (dataRows.length === 0) {
                        dataRows = mintageTable.querySelectorAll('tr:not(.odd):not(.sodd)');
                    }
                    for (var r2 = 0; r2 < dataRows.length; r2++) {
                        var cells2 = dataRows[r2].querySelectorAll('th, td');
                        var rowData = {};
                        var hasData = false;
                        for (var c3 = 0; c3 < cells2.length && c3 < headers.length; c3++) {
                            var header = headers[c3];
                            var value = cells2[c3].textContent.trim();
                            if (header && value) {
                                rowData[header] = value;
                                hasData = true;
                            }
                        }
                        if (hasData && (rowData['Монетный двор'] || rowData['Знак'])) {
                            result.mints.push(rowData);
                        }
                    }
                }
                return JSON.stringify(result);
            })();
            """

            def mintage_js_callback(result):
                coin_tab._mintage_processed = True
                if hasattr(coin_tab, '_mintage_timeout_timer'):
                    coin_tab._mintage_timeout_timer.stop()
                if result:
                    try:
                        import json
                        data = json.loads(result)
                        coin_tab._process_mintage_data(result)
                    except Exception as e:
                        print(f"DEBUG: Error parsing result: {e}")

            mintage_view.page().runJavaScript(mintage_js, 0, mintage_js_callback)

        mintage_view.loadFinished.connect(on_mintage_page_loaded)

        def on_mintage_timeout():
            if not coin_tab._mintage_processed:
                coin_tab._mintage_processed = True
                try:
                    mintage_view.loadFinished.disconnect(on_mintage_page_loaded)
                except RuntimeError:
                    pass

        self._mintage_timeout_timer.timeout.connect(on_mintage_timeout)
        self._mintage_timeout_timer.start(15000)

    def _process_mintage_data(self, json_result):
        """Обрабатывает данные о монетном дворе из вкладки #Mintage"""
        try:
            import json
            data = json.loads(json_result)
        except Exception:
            return
        mints = data.get('mints', [])
        mint_from_title = data.get('mint_from_title', '')
        mark_from_title = data.get('mark_from_title', '')
        coin_title = data.get('coin_title', '')
        if not coin_title and hasattr(self, '_ucoin_coin_title'):
            coin_title = self._ucoin_coin_title
        if not mints and not mint_from_title:
            return
        mint_name = None
        mint_mark = None
        if mint_from_title:
            mint_name = mint_from_title
            mint_mark = mark_from_title
        else:
            if len(mints) == 1:
                mint_data = mints[0]
                mint_name = mint_data.get('Монетный двор', '')
                mint_mark = mint_data.get('Знак', '')
            else:
                if mark_from_title:
                    for mint_data in mints:
                        if mint_data.get('Знак', '') == mark_from_title:
                            mint_name = mint_data.get('Монетный двор', '')
                            mint_mark = mark_from_title
                            break
                if not mint_name and mints:
                    mint_data = mints[0]
                    mint_name = mint_data.get('Монетный двор', '')
                    mint_mark = mint_data.get('Знак', '')
        if not mint_name and not mint_mark:
            return
        if not self.edit_mode:
            QMessageBox.warning(self, "Предупреждение",
                                "Переключитесь в режим редактирования для заполнения монетного двора")
            return
        if mint_name:
            idx = self.edit_fields['mint'].findText(mint_name)
            if idx >= 0:
                self.edit_fields['mint'].setCurrentIndex(idx)
            else:
                found = False
                for i in range(self.edit_fields['mint'].count()):
                    item_text = self.edit_fields['mint'].itemText(i)
                    if mint_name.lower() in item_text.lower() or item_text.lower() in mint_name.lower():
                        self.edit_fields['mint'].setCurrentIndex(i)
                        found = True
                        break
                if not found:
                    from database.models import Mint
                    country_id = self.edit_fields['country'].currentData()
                    new_mint = Mint(name=mint_name, mark=mint_mark or '', country_id=country_id)
                    self.db_manager.session.add(new_mint)
                    self.db_manager.session.commit()
                    self.load_mints_to_combo()
                    idx = self.edit_fields['mint'].findData(new_mint.id)
                    if idx >= 0:
                        self.edit_fields['mint'].setCurrentIndex(idx)
        if mint_mark:
            self.edit_fields['mint_mark'].setText(mint_mark)
        if coin_title:
            current_info = self.edit_fields['coin_info'].toPlainText() or ""
            if coin_title not in current_info:
                new_info = f"{current_info}\nМонетный двор: {coin_title}".strip()
                self.edit_fields['coin_info'].setText(new_info)
        elif mint_from_title:
            current_info = self.edit_fields['coin_info'].toPlainText() or ""
            info_text = f"Отметка монетного двора: \"{mint_mark}\" - {mint_name}" if mint_mark else f"Монетный двор: {mint_name}"
            if info_text not in current_info:
                new_info = f"{current_info}\n{info_text}".strip()
                self.edit_fields['coin_info'].setText(new_info)
        if not hasattr(self, '_mintage_message_shown') or not self._mintage_message_shown:
            self._mintage_message_shown = True
            QMessageBox.information(
                self,
                "Заполнение из UCOIN",
                f"✅ Монетный двор загружен!\n\n"
                f"🏭 Двор: {mint_name or 'Не найден'}\n"
                f"🔖 Знак: {mint_mark or 'Не найден'}\n"
                f"📝 Информация добавлена в поле 'Информация о монете'.\n\n"
                f"⚠️ Нажмите 💾 Сохранить, чтобы применить изменения."
            )
        self._mintage_processed = True

    def _extract_mintage_data(self, mintage_view):
        """Извлекает данные о монетном дворе из вкладки #Mintage (альтернативный способ)"""
        js_code = """
(function() {
    var data = {};
    var rows = document.querySelectorAll('tr');
    var fieldsMap = {
        'страна': 'country', 'валюта': 'currency', 'номинал': 'denomination',
        'год': 'year', 'гурт': 'edge', 'форма': 'shape', 'материал': 'metal',
        'вес (g)': 'weight', 'вес': 'weight', 'диаметр (mm)': 'diameter',
        'диаметр': 'diameter', 'толщина (mm)': 'thickness', 'толщина': 'thickness',
        'каталожные номера': 'km_number', 'каталожные номера:': 'km_number',
        'тираж': 'mintage', 'вид чекана': 'issue_type', 'тип чекана': 'issue_type',
        'тема': 'theme', 'серия': 'series', 'правитель': 'ruler',
        'отношение авс/рев': 'alignment'
    };
    function normalizeLabel(s) {
        return (s || '').toLowerCase().replace(/[:\\s.]+$/g, '').replace(/^[:\\s.]+/g, '').replace(/\\s+/g, ' ');
    }
    function cleanValue(s) {
        return (s || '').replace(/&nbsp;/g, ' ').replace(/\\s+/g, ' ').trim();
    }
    for (var i = 0; i < rows.length; i++) {
        var tr = rows[i];
        var th = tr.querySelector('th');
        var td = tr.querySelector('td');
        if (!th || !td) continue;
        var label = normalizeLabel(th.textContent);
        var key = fieldsMap[label];
        if (!key) continue;
        var value = cleanValue(td.textContent);
        if (value) data[key] = value;
    }
    function extractNumber(s) {
        if (!s) return null;
        s = s.replace(/\\s/g, '').replace(',', '.');
        var m = s.match(/^[\\d.]+/);
        return m ? m[0] : null;
    }
    ['weight', 'diameter', 'thickness'].forEach(function(k) {
        if (data[k]) {
            var n = extractNumber(data[k]);
            if (n) data[k] = n;
        }
    });
    if (data.mintage) {
        var m = data.mintage.replace(/[^\\d]/g, '');
        if (m) data.mintage = m;
    }
    if (!data.year) {
        var h1 = document.querySelector('h1');
        if (h1) {
            var m = h1.textContent.match(/(\\d{4})/);
            if (m) data.year = m[1];
        }
    }
    if (!data.year) {
        var m2 = window.location.pathname.match(/-(\\d{4})\\/?/);
        if (m2) data.year = m2[1];
    }
    if (!data.denomination) {
        var h1b = document.querySelector('h1');
        if (h1b) {
            var txt = h1b.textContent.replace(/,\\s*\\d{4}/, '').trim();
            var parts = txt.split(/\\s+/);
            if (parts.length >= 3) {
                data.denomination = parts.slice(1).join(' ');
            }
        }
    }
    var images = document.querySelectorAll('.gallery img');
    if (images.length >= 1) {
        var img = images[0];
        data.obverse_image_url = (img.getAttribute('srcset') || img.src || '').split(',')[0].split(' ')[0].trim();
    }
    if (images.length >= 2) {
        var img2 = images[1];
        data.reverse_image_url = (img2.getAttribute('srcset') || img2.src || '').split(',')[0].split(' ')[0].trim();
    }
    if (!data.obverse_image_url) {
        var o = document.getElementById('coin-img0');
        if (o) data.obverse_image_url = o.getAttribute('srcset') || o.src;
    }
    if (!data.reverse_image_url) {
        var r = document.getElementById('coin-img1');
        if (r) data.reverse_image_url = r.getAttribute('srcset') || r.src;
    }
    var descriptions = [];
    var descTables = document.querySelectorAll('table.coin-desc');
    for (var d = 0; d < descTables.length; d++) {
        var td = descTables[d].querySelector('td');
        if (td) {
            var side = d === 0 ? 'Аверс: ' : 'Реверс: ';
            descriptions.push(side + cleanValue(td.textContent));
        }
    }
    if (descriptions.length > 0) {
        data.description = descriptions.join('\\n\\n');
    }
    var ucm = window.location.search.match(/ucid=(\\d+)/);
    if (ucm) data.ucid = ucm[1];
    return data;
})();
"""

        def js_callback(result):
            if result:
                self._process_mintage_data(result)

        mintage_view.page().runJavaScript(js_code, 0, js_callback)

    @staticmethod
    def _parse_metal_name_purity(text):
        """Разбирает строку материала UCOIN на НАЗВАНИЕ и ПРОБУ.
        'Серебро 0.500' -> ('Серебро', '500'); 'Серебро 925' -> ('Серебро', '925')."""
        import re
        text = (text or '').strip()
        if not text:
            return None, None
        m = re.match(r'^([^\d]+?)\s*([\d.,‰%]*)\s*$', text)
        if m:
            name = m.group(1).strip()
            num = m.group(2).strip()
        else:
            m2 = re.match(r'^([^\d]+)', text)
            name = (m2.group(1).strip() if m2 else text)
            num = ''
        purity = None
        if num:
            num = num.replace(',', '.').replace('‰', '').replace('%', '').strip()
            try:
                val = float(num)
                if val <= 1.0:
                    purity = str(int(round(val * 1000)))
                else:
                    purity = str(int(round(val)))
            except ValueError:
                purity = None
        return (name or None), purity
        
    def _find_currency_index(self, combo, full_name, short_word):
        """Подбирает индекс валюты в комбобоксе.
        Приоритет: полное имя со страницы (точное, без учёта регистра) →
        наиболее длинное частичное совпадение → короткое слово ТОЛЬКО точным совпадением.
        Это исключает выбор 'Белорусский рубль' вместо 'Советский рубль'."""
        import re as _re

        def norm(s):
            return _re.sub(r'\s+', ' ', (s or '').strip().lower())

        if full_name:
            fn = norm(full_name)
            for i in range(combo.count()):
                if norm(combo.itemText(i)) == fn:
                    return i
            best, best_len = -1, -1
            for i in range(combo.count()):
                it = norm(combo.itemText(i))
                if it and (it in fn or fn in it):
                    if len(it) > best_len:
                        best_len, best = len(it), i
            if best >= 0:
                return best
        if short_word:
            sw = norm(short_word)
            for i in range(combo.count()):
                if norm(combo.itemText(i)) == sw:
                    return i
        return -1
        
    @staticmethod
    def _century_to_roman(num):
        """Переводит номер века в римскую запись: 21 -> 'XXI', 20 -> 'XX'"""
        table = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                 (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]
        res = ''
        n = int(num)
        for v, s in table:
            while n >= v:
                res += s
                n -= v
        return res
        
    def scan_coin_photos(self):
        """Открывает диалог сканирования сторон и подставляет результат
        в форму редактирования (ImageSelector аверса/реверса)."""
        from gui.widgets.coin_scanner.edit_scan_dialog import CoinEditScanDialog
        dlg = CoinEditScanDialog(self)
        if dlg.exec():
            obverse, reverse = dlg.get_results()
            w = self.coin_edit_widget
            if obverse:
                w.edit_obverse_image.set_image_from_path(obverse)
                w.edit_obverse_image.image_path = obverse
                w.edit_obverse_image.update_display()
            if reverse:
                w.edit_reverse_image.set_image_from_path(reverse)
                w.edit_reverse_image.image_path = reverse
                w.edit_reverse_image.update_display()
            if obverse or reverse:
                self.logger.info("✅ Скан сторон подставлен в форму редактирования")