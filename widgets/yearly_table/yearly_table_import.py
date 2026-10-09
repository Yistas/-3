# ===== gui/widgets/yearly_table/yearly_table_import.py =====
# НОВЫЙ ФАЙЛ - ИМПОРТ ИЗ UCOIN

# -*- coding: utf-8 -*-

"""
Импорт из UCOIN для погодовки
"""

import re
import logging
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QApplication, QProgressDialog
from PySide6.QtGui import QColor


class YearlyTableImport:
    """Импорт из UCOIN для погодовки"""
    
    def __init__(self, parent):
        self.parent = parent
        self.logger = logging.getLogger('CoinCollector.GUI.YearlyTableImport')
    
    def import_from_ucoin(self):
        """Импортирует таблицу из открытой вкладки браузера uCoin.net"""
        from gui.widgets.yearly_table.ucoin_parser import UCoinParser, create_yearly_table_from_parser
        
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break
        
        if not main_window:
            QMessageBox.warning(self.parent, "Ошибка", "Не найдено главное окно")
            return
        
        browser_tab = None
        if hasattr(main_window, 'center_tab_widget'):
            for i in range(main_window.center_tab_widget.count()):
                tab_text = main_window.center_tab_widget.tabText(i)
                if "Браузер" in tab_text:
                    browser_tab = main_window.center_tab_widget.widget(i)
                    break
        
        if not browser_tab:
            QMessageBox.warning(self.parent, "Ошибка", "Вкладка браузера не найдена")
            return
        
        if hasattr(browser_tab, 'get_current_web_view'):
            web_view = browser_tab.get_current_web_view()
        elif hasattr(browser_tab, 'web_view'):
            web_view = browser_tab.web_view
        else:
            QMessageBox.warning(self.parent, "Ошибка", "Не удалось получить WebView")
            return
        
        if not web_view:
            QMessageBox.warning(self.parent, "Ошибка", "Нет активной страницы в браузере")
            return
        
        current_url = web_view.url().toString()
        if 'ucoin.net' not in current_url:
            reply = QMessageBox.question(
                self.parent, 
                "Подтверждение",
                f"Текущая страница не похожа на uCoin.net.\n"
                f"URL: {current_url[:80]}...\n\n"
                f"Продолжить парсинг?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        progress = QProgressDialog("Парсинг страницы uCoin.net...", "Отмена", 0, 100, self.parent)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setMinimumDuration(500)
        progress.setValue(0)
        progress.show()
        
        parser = UCoinParser(web_view)
        
        def update_progress(value, message):
            if progress.wasCanceled():
                return
            progress.setValue(value)
            progress.setLabelText(message)
            QApplication.processEvents()
        
        data, page_title = parser.parse_current_page(update_progress)
        
        if not data:
            progress.close()
            QMessageBox.warning(self.parent, "Ошибка", "Не удалось распарсить страницу.\n\n"
                               "Убедитесь, что на странице открыта таблица монет uCoin.net\n"
                               "с годами и номиналами.")
            return
        
        if page_title:
            country_name = re.sub(r'[<>:"/\\|?*]', '', page_title).strip()
            if len(country_name) > 50:
                country_name = country_name[:50]
        else:
            country_name = self.parent.current_country_name or "Импорт"
        
        headers_from_parser = getattr(parser, 'headers', None)
        if headers_from_parser:
            self.logger.info(f"📋 Заголовки из таблицы: {headers_from_parser}")
        
        table_data = create_yearly_table_from_parser(data, country_name, headers_from_parser)
        
        if not table_data:
            progress.close()
            QMessageBox.warning(self.parent, "Ошибка", "Не найдены данные о монетах")
            return
        
        progress.setLabelText("Создание таблицы...")
        QApplication.processEvents()
        
        sheet_name = country_name
        base_name = sheet_name
        counter = 1
        while sheet_name in self.parent.sheets:
            sheet_name = f"{base_name}_{counter}"
            counter += 1
        
        self.parent.add_new_sheet(sheet_name)
        
        sheet = self.parent.sheets.get(sheet_name)
        if not sheet:
            progress.close()
            QMessageBox.warning(self.parent, "Ошибка", "Не удалось создать лист")
            return
        
        table = sheet.table
        
        headers = table_data['headers']
        table_rows = table_data['rows']
        years = table_data['years']
        
        table.setRowCount(len(table_rows))
        table.setColumnCount(len(headers))
        
        for col, denom in enumerate(headers):
            header_item = QTableWidgetItem(denom)
            header_item.setTextAlignment(Qt.AlignCenter)
            table.setHorizontalHeaderItem(col, header_item)
        
        for row, year in enumerate(years):
            header_item = QTableWidgetItem(str(year))
            header_item.setTextAlignment(Qt.AlignCenter)
            header_item.setBackground(QBrush(QColor("#4a6fa5")))
            header_item.setForeground(QBrush(QColor("#ffffff")))
            table.setVerticalHeaderItem(row, header_item)
        
        for row in range(len(table_rows)):
            row_values = table_rows[row]
            year = years[row]
            for col, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QBrush(QColor("#000000")))
                
                if value and value != "":
                    item.setForeground(QColor("#28a745"))
                    item.setToolTip(f"{headers[col]} {year}")
                else:
                    item.setBackground(QColor("#9a9a73"))
                
                table.setItem(row, col, item)
                item.setData(Qt.UserRole + 2, True)
        
        table.resizeColumnsToContents()
        
        self.parent._row_cache = {}
        
        progress.close()
        
        QMessageBox.information(
            self.parent,
            "Импорт завершён",
            f"✅ Таблица создана!\n\n"
            f"📊 Страна: {country_name}\n"
            f"📅 Всего строк: {len(table_rows)}\n"
            f"🪙 Номиналов: {len(headers)}\n"
            f"📄 Лист: {sheet_name}\n\n"
            f"Не забудьте сохранить изменения (SAVE ALL)."
        )
        
        self.parent.is_modified = True
        self.parent.refresh_color_legend()
        
        QTimer.singleShot(100, self.parent._load_visible_rows)