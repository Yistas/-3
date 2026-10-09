# ===== gui/widgets/yearly_table/yearly_table_core.py =====
# НОВЫЙ ФАЙЛ - ВЫНЕСЕННЫЕ МЕТОДЫ

# -*- coding: utf-8 -*-

"""
Ядро погодовки - вынесенные методы для загрузки/сохранения Excel
"""

import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QFileDialog, QApplication, QTableWidgetItem
from PySide6.QtGui import QColor, QBrush


class YearlyTableCore:
    """Ядро погодовки - методы загрузки/сохранения"""
    
    def __init__(self, parent):
        self.parent = parent
        self.logger = logging.getLogger('CoinCollector.GUI.YearlyTableCore')
    
    # ===== СОХРАНЕНИЕ =====
    
    def save_file(self):
        """Сохраняет таблицу в текущий файл (перезаписывает)"""
        if not self.parent.current_file:
            self.save_file_as()
            return
        
        backup = self.parent.current_file + ".backup"
        if os.path.exists(self.parent.current_file):
            try:
                shutil.copy2(self.parent.current_file, backup)
            except:
                pass
        
        try:
            self.parent.save_with_formatting(self.parent.current_file)
            self.parent.is_modified = False
            self.parent.status_label.setText(f"✅ Сохранено: {os.path.basename(self.parent.current_file)}")
            
            if os.path.exists(backup):
                try:
                    os.remove(backup)
                except:
                    pass
        except Exception as e:
            self.logger.error(f"Ошибка сохранения: {e}")
            QMessageBox.critical(self.parent, "Ошибка", f"Не удалось сохранить файл:\n{e}")
            
            if os.path.exists(backup):
                try:
                    shutil.copy2(backup, self.parent.current_file)
                    self.parent.status_label.setText("⚠️ Восстановлено из резервной копии")
                except:
                    pass

    def save_file_as(self):
        """Сохраняет таблицу в новый файл (с выбором имени)"""
        default = f"country_{self.parent.current_country_id}.xlsx" if self.parent.current_country_id else f"{self.parent.current_country_name or 'all'}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent, "Сохранить файл",
            str(self.parent.yearly_dir / default),
            "Excel files (*.xlsx)"
        )
        
        if file_path:
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.parent.save_with_formatting(file_path)
            self.parent.current_file = file_path
            self.parent.is_modified = False
            self.parent.status_label.setText(f"✅ Сохранено: {os.path.basename(file_path)}")

    def save_current_table(self):
        """Сохраняет текущую таблицу в файл (перезаписывает существующий)"""
        if not self.parent.current_file:
            default_name = f"country_{self.parent.current_country_id}.xlsx" if self.parent.current_country_id else f"{self.parent.current_country_name or 'all'}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self.parent, "Сохранить файл",
                str(self.parent.yearly_dir / default_name),
                "Excel files (*.xlsx)"
            )
            if not file_path:
                return False
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            self.parent.current_file = file_path
        
        self.parent.save_with_formatting(self.parent.current_file)
        self.parent.is_modified = False
        self.parent.status_label.setText(f"✅ Сохранено: {os.path.basename(self.parent.current_file)}")
        return True

    def save_all_sheets(self):
        """Сохраняет все листы в файл (перезаписывает существующий)"""
        if not self.parent.current_file:
            default_name = f"country_{self.parent.current_country_id}.xlsx" if self.parent.current_country_id else f"{self.parent.current_country_name or 'all'}.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self.parent, "Сохранить файл",
                str(self.parent.yearly_dir / default_name),
                "Excel files (*.xlsx)"
            )
            if not file_path:
                return False
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            self.parent.current_file = file_path
        
        try:
            self.parent.save_with_formatting(self.parent.current_file)
            self.parent.is_modified = False
            self.parent.status_label.setText(f"✅ Все изменения сохранены: {os.path.basename(self.parent.current_file)}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения: {e}")
            QMessageBox.critical(self.parent, "Ошибка", f"Не удалось сохранить файл:\n{e}")
            return False

    def auto_save(self):
        """Автосохранение (перезаписывает существующий файл)"""
        if self.parent.auto_save_enabled and self.parent.is_modified and self.parent.current_file:
            try:
                self.parent.save_with_formatting(self.parent.current_file)
                self.parent.is_modified = False
                self.parent.status_label.setText("✅ Автосохранение выполнено")
                
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: self.parent.status_label.setText("Готов"))
            except Exception as e:
                self.logger.error(f"Ошибка автосохранения: {e}")

    # ===== ЗАГРУЗКА =====
    
    def open_file(self):
        """Открывает файл Excel"""
        self.parent.yearly_dir.mkdir(parents=True, exist_ok=True)
        
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent, "Открыть файл",
            str(self.parent.yearly_dir),
            "Excel files (*.xlsx *.xls);;CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                self.parent.load_excel_with_formatting(file_path)
                self.parent.current_file = file_path
                self.parent.is_modified = False
                self.parent.status_label.setText(f"Загружен: {os.path.basename(file_path)}")
                self.parent._update_country_from_filename(os.path.basename(file_path))
                self.parent.refresh_color_legend()
                self.parent._row_cache = {}
                QTimer.singleShot(100, self.parent._load_visible_rows)
            except Exception as e:
                error_msg = str(e)
                if "xlrd" in error_msg:
                    QMessageBox.critical(self.parent, "Ошибка", 
                        f"Для работы с файлами .xls требуется библиотека xlrd.\n\n"
                        f"Установите: pip install xlrd\n\n"
                        f"Или сохраните файл в формате .xlsx")
                else:
                    QMessageBox.critical(self.parent, "Ошибка", f"Не удалось загрузить файл:\n{error_msg}")

    def load_dataframe(self, df):
        """Загружает данные из DataFrame"""
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(self.parent, "Ошибка", "Библиотека pandas не установлена")
            return
        
        self.parent.sheet_tabs.clear()
        self.parent.sheets.clear()
        self.parent._row_cache = {}
        self.parent.add_new_sheet("Лист1")
        
        sheet = self.parent.sheets["Лист1"]
        table = sheet.table
        
        table.setRowCount(len(df))
        table.setColumnCount(len(df.columns))
        
        for i, col in enumerate(df.columns):
            header_item = QTableWidgetItem(str(col))
            header_item.setBackground(QBrush(QColor("#4a6fa5")))
            header_item.setForeground(QBrush(QColor("#ffffff")))
            header_item.setTextAlignment(Qt.AlignCenter)
            table.setHorizontalHeaderItem(i, header_item)
        
        for i, row in df.iterrows():
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val) if pd.notna(val) else "")
                item.setForeground(QBrush(QColor("#000000")))
                if pd.isna(val) or val == "":
                    item.setBackground(QBrush(QColor("#6c757d")))
                    item.setForeground(QBrush(QColor("#ffffff")))
                table.setItem(i, j, item)
                item.setData(Qt.UserRole + 2, True)
        
        self.parent.update_size_info()
        self.parent.refresh_color_legend()
        self.parent.is_modified = True
        
        QTimer.singleShot(100, self.parent._load_visible_rows)