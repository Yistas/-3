# ===== gui/dialogs/import_purchases_dialog.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для импорта данных из Excel в таблицу purchases (лист ЗАКУПКИ)
"""

import re
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QFileDialog, QMessageBox, QProgressBar,
                               QTextEdit, QGroupBox)
from PySide6.QtCore import Qt, QThread, Signal
import pandas as pd

from database.models import ImportCountry, Purchase


class ImportPurchasesThread(QThread):
    """Поток для импорта данных из Excel в БД"""
    progress = Signal(int, int, str)
    finished = Signal(int, int, int)
    error = Signal(str)
    
    def __init__(self, db_manager, file_path):
        super().__init__()
        self.db_manager = db_manager
        self.file_path = file_path
        self._is_running = True
    
    def run(self):
        try:
            # Читаем лист ЗАКУПКИ
            df = pd.read_excel(self.file_path, sheet_name='ЗАКУПКИ', header=None)
            
            # Находим строку с заголовками (ищем "Старана" или "ГОД")
            header_row = None
            for i, row in df.iterrows():
                row_values = [str(v).strip() for v in row.values if pd.notna(v)]
                if 'Старана' in row_values or 'ГОД' in row_values:
                    header_row = i
                    break
            
            if header_row is None:
                self.error.emit("Не найдена строка с заголовками (ищем 'Старана' или 'ГОД')")
                return
            
            # Устанавливаем заголовки из найденной строки
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:]
            
            # Переименовываем колонки согласно структуре Excel
            df.columns = [
                'in_collection',        # 0 - A: КОЛ
                'collection_price',     # 1 - B: ЦК
                'purchase_number',      # 2 - C: №№
                'purchase_batch',       # 3 - D: Покупка (партия)
                'country_name',         # 4 - E: Старана
                'continent',            # 5 - F: Континент
                'denomination_value',   # 6 - G: Номинал
                'currency',             # 7 - H: валюта
                'year',                 # 8 - I: ГОД
                'location_found',       # 9 - J: МЕСТО
                'quantity',             # 10 - K: количество
                'comments',             # 11 - L: КОМЕНТЫ
                'ucoin_exchange_count', # 12 - M: Обмен ucoin.net
                'sold_count',           # 13 - N: Кол-во продано
                'sold_sum',             # 14 - O: Сумма продажи
                'total'                 # 15 - P: ИТОГО
            ]
            
            total_rows = len(df)
            imported = 0
            skipped = 0
            errors = 0
            
            for index, row in df.iterrows():
                if not self._is_running:
                    break
                
                try:
                    # Пропускаем пустые строки
                    country_name = str(row.get('country_name', '')).strip()
                    if not country_name or country_name in ['nan', 'None', '']:
                        skipped += 1
                        continue
                    
                    # Пропускаем строки с формулами в названии страны
                    if country_name.startswith('=') or country_name.startswith('SUM'):
                        skipped += 1
                        continue
                    
                    # Получаем или создаём страну в таблице import_countries
                    import_country = self.db_manager.session.query(ImportCountry).filter_by(
                        name=country_name
                    ).first()
                    
                    if not import_country:
                        import_country = ImportCountry(name=country_name)
                        self.db_manager.session.add(import_country)
                        self.db_manager.session.flush()
                    
                    # Парсим КОЛ (признак попадания в коллекцию)
                    in_collection = False
                    col_val = row.get('in_collection')
                    if pd.notna(col_val):
                        try:
                            in_collection = bool(int(float(str(col_val))))
                        except:
                            pass
                    
                    # Парсим ЦК (цена коллекционная)
                    collection_price = None
                    ck_val = row.get('collection_price')
                    if pd.notna(ck_val) and str(ck_val).strip() not in ['', 'nan', 'None']:
                        try:
                            collection_price = float(str(ck_val))
                        except:
                            pass
                    
                    # Парсим номер закупки
                    purchase_number = None
                    pn_val = row.get('purchase_number')
                    if pd.notna(pn_val) and str(pn_val).strip() not in ['', 'nan', 'None']:
                        purchase_number = str(pn_val).strip()
                    
                    # Парсим партию закупки (колонка D)
                    purchase_batch = None
                    pb_val = row.get('purchase_batch')
                    if pd.notna(pb_val) and str(pb_val).strip() not in ['', 'nan', 'None']:
                        pb_str = str(pb_val).strip()
                        if not pb_str.startswith('=') and not pb_str.startswith('SUM'):
                            purchase_batch = pb_str
                    
                    # Парсим год
                    year = None
                    year_val = row.get('year')
                    if pd.notna(year_val) and str(year_val).strip() not in ['', 'nan', 'None', '...']:
                        try:
                            year = int(float(str(year_val)))
                        except:
                            pass
                    
                    # Парсим количество
                    quantity = 1
                    qty_val = row.get('quantity')
                    if pd.notna(qty_val) and str(qty_val).strip() not in ['', 'nan', 'None']:
                        try:
                            quantity = int(float(str(qty_val)))
                        except:
                            pass
                    
                    # Парсим обмен ucoin
                    ucoin_exchange = False
                    ucoin_exchange_count = 0
                    ue_val = row.get('ucoin_exchange_count')
                    if pd.notna(ue_val) and str(ue_val).strip() not in ['', 'nan', 'None', '0']:
                        try:
                            ucoin_exchange_count = int(float(str(ue_val)))
                            ucoin_exchange = ucoin_exchange_count > 0
                        except:
                            pass
                    
                    # Парсим продано (может быть цифрой или текстом)
                    sold_count = None
                    sc_val = row.get('sold_count')
                    if pd.notna(sc_val) and str(sc_val).strip() not in ['', 'nan', 'None']:
                        sc_str = str(sc_val).strip()
                        # Пробуем преобразовать в число для числовых значений
                        try:
                            sold_count = str(int(float(sc_str)))
                        except:
                            sold_count = sc_str
                    
                    # Парсим сумму продаж
                    sold_sum = None
                    ss_val = row.get('sold_sum')
                    if pd.notna(ss_val) and str(ss_val).strip() not in ['', 'nan', 'None']:
                        try:
                            sold_sum = float(str(ss_val))
                        except:
                            pass
                    
                    # Парсим итого
                    total = None
                    total_val = row.get('total')
                    if pd.notna(total_val) and str(total_val).strip() not in ['', 'nan', 'None']:
                        try:
                            total = float(str(total_val))
                        except:
                            pass
                    
                    # Создаём запись
                    purchase = Purchase(
                        in_collection=in_collection,
                        collection_price=collection_price,
                        purchase_number=purchase_number,
                        purchase_batch=purchase_batch,
                        import_country_id=import_country.id,
                        continent=str(row.get('continent', '')) if pd.notna(row.get('continent')) else None,
                        denomination_value=str(row.get('denomination_value', '')) if pd.notna(row.get('denomination_value')) else None,
                        currency=str(row.get('currency', '')) if pd.notna(row.get('currency')) else None,
                        year=year,
                        location_found=str(row.get('location_found', '')) if pd.notna(row.get('location_found')) else None,
                        quantity=quantity,
                        comments=str(row.get('comments', '')) if pd.notna(row.get('comments')) else None,
                        ucoin_exchange=ucoin_exchange,
                        ucoin_exchange_count=ucoin_exchange_count,
                        sold_count=sold_count,
                        sold_sum=sold_sum,
                        total=total
                    )
                    
                    self.db_manager.session.add(purchase)
                    imported += 1
                    
                    if imported % 100 == 0:
                        self.db_manager.session.commit()
                        self.progress.emit(index + 1, total_rows, f"Импортировано {imported}...")
                
                except Exception as e:
                    errors += 1
                    self.progress.emit(index + 1, total_rows, f"❌ Ошибка в строке {index + 2}: {str(e)[:50]}")
            
            self.db_manager.session.commit()
            self.finished.emit(imported, skipped, errors)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        self._is_running = False


class ImportPurchasesDialog(QDialog):
    """Диалог для импорта закупок из Excel (лист ЗАКУПКИ)"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.import_thread = None
        self.setWindowTitle("Импорт закупок из Excel")
        self.setMinimumSize(600, 500)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📥 Импорт данных о закупках (лист ЗАКУПКИ)")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Информация о формате
        info_group = QGroupBox("📋 Ожидаемые колонки в Excel")
        info_layout = QVBoxLayout()
        info_label = QLabel(
            "A: КОЛ | B: ЦК | C: №№ | D: Партия | E: Страна | F: Континент | "
            "G: Номинал | H: Валюта | I: ГОД | J: МЕСТО | K: Кол-во | "
            "L: КОМЕНТЫ | M: Обмен | N: Продано | O: Сумма | P: ИТОГО"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 5px;")
        info_layout.addWidget(info_label)
        
        note_label = QLabel(
            "💡 Страны из файла сохраняются в отдельный справочник "
            "и не попадают в дерево стран коллекции."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: #4a6fa5; font-size: 11px; padding: 5px;")
        info_layout.addWidget(note_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Выбор файла
        file_group = QGroupBox("📂 Выбор файла")
        file_layout = QHBoxLayout()
        
        self.file_path_edit = QLabel("Файл не выбран")
        self.file_path_edit.setStyleSheet("border: 1px solid #ccc; padding: 5px; background-color: #f5f5f5;")
        self.file_path_edit.setWordWrap(True)
        file_layout.addWidget(self.file_path_edit, 1)
        
        browse_btn = QPushButton("📁 Обзор")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Лог операций
        log_label = QLabel("📋 Лог операций:")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("🚀 Импортировать")
        self.import_btn.clicked.connect(self.start_import)
        self.import_btn.setEnabled(False)
        self.import_btn.setMinimumHeight(35)
        self.import_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(self.import_btn)
        
        self.cancel_btn = QPushButton("❌ Отмена")
        self.cancel_btn.clicked.connect(self.cancel_import)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setMinimumHeight(35)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def browse_file(self):
        """Выбор Excel файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите Excel файл",
            "",
            "Excel files (*.xlsx *.xls);;All files (*.*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            self.import_btn.setEnabled(True)
    
    def start_import(self):
        """Запускает импорт данных"""
        file_path = self.file_path_edit.text()
        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(self, "Предупреждение", "Выберите файл")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Импортировать данные из листа 'ЗАКУПКИ'?\n\n"
            f"Файл: {Path(file_path).name}\n\n"
            f"Новые страны будут добавлены в справочник стран закупок\n"
            f"(не попадут в дерево стран коллекции).",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.import_btn.setEnabled(False)
        self.findChild(QPushButton, "📁 Обзор").setEnabled(False) if self.findChild(QPushButton, "📁 Обзор") else None
        self.cancel_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        self.import_thread = ImportPurchasesThread(self.db_manager, file_path)
        self.import_thread.progress.connect(self.on_progress)
        self.import_thread.finished.connect(self.on_finished)
        self.import_thread.error.connect(self.on_error)
        self.import_thread.start()
    
    def cancel_import(self):
        """Отменяет импорт"""
        if self.import_thread and self.import_thread.isRunning():
            self.import_thread.stop()
            self.add_log("⚠️ Импорт отменён пользователем")
            self.cancel_btn.setEnabled(False)
    
    def on_progress(self, current, total, message):
        """Обновляет прогресс"""
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.add_log(message)
    
    def on_finished(self, imported, skipped, errors):
        """Завершение импорта"""
        self.progress_bar.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        
        self.add_log("=" * 50)
        self.add_log(f"✅ Импорт завершён!")
        self.add_log(f"📥 Импортировано записей: {imported}")
        self.add_log(f"⏭️ Пропущено строк: {skipped}")
        if errors > 0:
            self.add_log(f"❌ Ошибок: {errors}")
        self.add_log("=" * 50)
        
        QMessageBox.information(
            self, "Импорт завершён",
            f"Результаты импорта:\n\n"
            f"✅ Импортировано: {imported}\n"
            f"⏭️ Пропущено: {skipped}\n"
            f"❌ Ошибок: {errors}\n\n"
            f"Данные загружены в таблицу закупок."
        )
    
    def on_error(self, error_msg):
        """Ошибка импорта"""
        self.progress_bar.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.import_btn.setEnabled(True)
        
        self.add_log(f"❌ Критическая ошибка: {error_msg}")
        QMessageBox.critical(self, "Ошибка импорта", f"Не удалось выполнить импорт:\n\n{error_msg}")
    
    def add_log(self, message):
        """Добавляет запись в лог"""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())