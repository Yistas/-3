# ===== gui/widgets/exchange_tab/purchases_paste.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Методы для копирования, вставки и Undo/Redo в таблице закупок
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from database.models import ImportCountry


class PurchasesPasteMixin:
    """Примесь с методами копирования/вставки и Undo/Redo"""
    
    def _copy_selected_cells(self):
        """Копирует выделенные ячейки в буфер обмена"""
        table = self.purchases_table
        if not table:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        # Сортируем по строкам и колонкам
        rows = {}
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            if row not in rows:
                rows[row] = {}
            value = idx.data(Qt.DisplayRole) or ""
            rows[row][col] = value
        
        # Формируем текст для буфера обмена
        lines = []
        for row in sorted(rows.keys()):
            cols = rows[row]
            max_col = max(cols.keys()) if cols else 0
            line = []
            for col in range(max_col + 1):
                line.append(cols.get(col, ""))
            lines.append("\t".join(line))
        
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))
        
        self.save_status_label.setText(f"📋 Скопировано {len(selected_indexes)} ячеек")
        self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
    
    def _paste_to_selected_cells(self):
        """Вставляет данные из буфера обмена в выделенные ячейки"""
        table = self.purchases_table
        if not table:
            return
        
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        # Разбираем буфер обмена
        rows_data = []
        for line in text.strip().split("\n"):
            if "\t" in line:
                row = line.split("\t")
            else:
                row = line.split(",")
            rows_data.append([cell.strip() for cell in row])
        
        if not rows_data:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            current = table.currentIndex()
            if current.isValid():
                selected_indexes = [current]
        
        if not selected_indexes:
            return
        
        # СОРТИРУЕМ ПО СТРОКАМ И КОЛОНКАМ
        selected_indexes.sort(key=lambda x: (x.row(), x.column()))
        
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0
        
        print(f"!!! DEBUG: source_rows={source_rows}, source_cols={source_cols}, selected_count={len(selected_indexes)}")
        
        table.setUpdatesEnabled(False)
        
        # Кэш для стран
        country_cache = {}
        
        def get_or_create_country(country_name):
            if not country_name:
                return None
            if country_name in country_cache:
                return country_cache[country_name]
            country = self.db_manager.session.query(ImportCountry).filter_by(name=country_name).first()
            if not country:
                country = ImportCountry(name=country_name)
                self.db_manager.session.add(country)
                self.db_manager.session.flush()
            country_cache[country_name] = country
            return country
        
        try:
            changes_for_undo = []
            
            for i, target_idx in enumerate(selected_indexes):
                source_row = i % source_rows
                source_col = (i // source_rows) % source_cols
                
                if source_row < len(rows_data) and source_col < len(rows_data[source_row]):
                    value = rows_data[source_row][source_col]
                else:
                    value = ""
                
                row = target_idx.row()
                col = target_idx.column()
                
                print(f"!!! DEBUG: target row={row}, col={col}, value='{value}'")
                
                # Получаем source_row в модели
                source_row_idx = self._get_source_row(row)
                
                if source_row_idx < len(self._filtered_purchases):
                    purchase = self._filtered_purchases[source_row_idx]
                    if purchase:
                        field_name = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                        
                        if field_name and value != "":
                            old_value = getattr(purchase, field_name, None)
                            str_old = str(old_value) if old_value is not None else ""
                            
                            if str_old != value:
                                print(f"!!! DEBUG: setting {field_name} = '{value}'")
                                
                                # Обработка разных типов полей
                                if field_name == 'country':
                                    country = get_or_create_country(value)
                                    if country:
                                        purchase.import_country_id = country.id
                                        purchase.import_country = country
                                
                                elif field_name == 'denomination':
                                    purchase.denomination_value = value
                                
                                elif field_name == 'purchase_batch':
                                    purchase.purchase_batch = value
                                
                                elif field_name == 'currency':
                                    purchase.currency = value
                                
                                elif field_name == 'continent':
                                    purchase.continent = value
                                
                                elif field_name == 'year':
                                    try:
                                        purchase.year = int(value) if value else None
                                    except ValueError:
                                        pass
                                
                                elif field_name == 'quantity':
                                    try:
                                        purchase.quantity = int(value) if value else 1
                                    except ValueError:
                                        pass
                                
                                elif field_name == 'collection_price':
                                    try:
                                        purchase.collection_price = float(value) if value else None
                                    except ValueError:
                                        pass
                                
                                elif field_name == 'sold_sum':
                                    try:
                                        purchase.sold_sum = float(value) if value else None
                                    except ValueError:
                                        pass
                                
                                elif field_name == 'ucoin_exchange':
                                    try:
                                        num_value = int(value)
                                        purchase.ucoin_exchange = True
                                        purchase.ucoin_exchange_count = num_value
                                    except ValueError:
                                        if value.lower() in ('true', '✅', '1'):
                                            purchase.ucoin_exchange = True
                                            purchase.ucoin_exchange_count = 1
                                        else:
                                            purchase.ucoin_exchange = False
                                            purchase.ucoin_exchange_count = 0
                                
                                else:
                                    setattr(purchase, field_name, value if value else None)
                                
                                purchase.updated_at = datetime.now()
                                self._dirty_ids.add(purchase.id)
                                
                                # Сохраняем для Undo
                                changes_for_undo.append({
                                    'purchase_id': purchase.id,
                                    'field': field_name,
                                    'old_value': old_value,
                                    'new_value': value
                                })
            
            # Сохраняем ВСЕ изменения одной группой для Undo
            if changes_for_undo:
                if not hasattr(self, '_last_changes'):
                    self._last_changes = []
                self._last_changes.append(changes_for_undo)
                if hasattr(self, '_redo_stack'):
                    self._redo_stack.clear()
            
            # === ВАЖНО: Сохраняем изменения в БД ===
            if self._dirty_ids:
                self.db_manager.session.commit()
                self._dirty_ids.clear()
                self.save_status_label.setText("💾 Изменения сохранены")
                self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
            # Обновляем отображение
            self.model.beginResetModel()
            self.model._data = self._filtered_purchases
            self.model.endResetModel()
            
            self.save_status_label.setText(f"📌 Вставлено в {len(selected_indexes)} ячеек")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки: {e}")
            import traceback
            traceback.print_exc()
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            table.setUpdatesEnabled(True)
    
    def _paste_single_value_to_selected(self, value):
        """Вставляет одно значение во все выделенные ячейки"""
        print(f"!!! DEBUG: _paste_single_value_to_selected CALLED with value='{value}'")
        
        table = self.purchases_table
        if not table:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        table.setUpdatesEnabled(False)
        
        # Кэш для стран
        country_cache = {}
        
        def get_or_create_country(country_name):
            if not country_name:
                return None
            if country_name in country_cache:
                return country_cache[country_name]
            country = self.db_manager.session.query(ImportCountry).filter_by(name=country_name).first()
            if not country:
                country = ImportCountry(name=country_name)
                self.db_manager.session.add(country)
                self.db_manager.session.flush()
            country_cache[country_name] = country
            return country
        
        try:
            changes_for_undo = []
            
            for idx in selected_indexes:
                row = idx.row()
                col = idx.column()
                
                # Получаем source_row в модели
                source_row_idx = self._get_source_row(row)
                
                if source_row_idx < len(self._filtered_purchases):
                    purchase = self._filtered_purchases[source_row_idx]
                    if purchase:
                        field_name = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                        
                        if field_name and value != "":
                            old_value = getattr(purchase, field_name, None)
                            
                            if field_name == 'country':
                                if value:
                                    country = get_or_create_country(value)
                                    if country:
                                        purchase.import_country_id = country.id
                                        purchase.import_country = country
                            
                            elif field_name == 'denomination':
                                purchase.denomination_value = value
                            
                            elif field_name == 'purchase_batch':
                                purchase.purchase_batch = value
                            
                            elif field_name == 'currency':
                                purchase.currency = value
                            
                            elif field_name == 'continent':
                                purchase.continent = value
                            
                            elif field_name == 'ucoin_exchange':
                                try:
                                    num_value = int(value)
                                    purchase.ucoin_exchange = True
                                    purchase.ucoin_exchange_count = num_value
                                except ValueError:
                                    if value.lower() in ('true', '✅', '1'):
                                        purchase.ucoin_exchange = True
                                        purchase.ucoin_exchange_count = 1
                                    else:
                                        purchase.ucoin_exchange = False
                                        purchase.ucoin_exchange_count = 0
                            
                            else:
                                setattr(purchase, field_name, value if value else None)
                            
                            purchase.updated_at = datetime.now()
                            self._dirty_ids.add(purchase.id)
                            
                            # Сохраняем для Undo
                            changes_for_undo.append({
                                'purchase_id': purchase.id,
                                'field': field_name,
                                'old_value': old_value,
                                'new_value': value
                            })
            
            # Сохраняем ВСЕ изменения одной группой для Undo
            if changes_for_undo:
                if not hasattr(self, '_last_changes'):
                    self._last_changes = []
                self._last_changes.append(changes_for_undo)
                if hasattr(self, '_redo_stack'):
                    self._redo_stack.clear()
            
            # === ВАЖНО: Сохраняем изменения в БД ===
            if self._dirty_ids:
                self.db_manager.session.commit()
                self._dirty_ids.clear()
                self.save_status_label.setText("💾 Изменения сохранены")
                self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
            # Обновляем отображение
            self.model.beginResetModel()
            self.model._data = self._filtered_purchases
            self.model.endResetModel()
            
            self.save_status_label.setText(f"📌 Вставлено в {len(selected_indexes)} ячеек")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
        finally:
            table.setUpdatesEnabled(True)
    
    def _get_source_row(self, proxy_row):
        """Возвращает индекс строки в исходной модели"""
        model = self.purchases_table.model()
        proxy_index = model.index(proxy_row, 0)
        if hasattr(model, 'mapToSource'):
            source_index = model.mapToSource(proxy_index)
            return source_index.row()
        return proxy_row
    
    def _undo_last_change(self):
        """Отменяет последнее изменение (Ctrl+Z)"""
        if not hasattr(self, '_last_changes') or not self._last_changes:
            self.save_status_label.setText("ℹ️ Нет действий для отмены")
            return
        
        try:
            changes = self._last_changes.pop()
            
            if not hasattr(self, '_redo_stack'):
                self._redo_stack = []
            self._redo_stack.append(changes)
            
            for change in changes:
                # Ищем закупку в _filtered_purchases
                purchase = None
                for p in self._filtered_purchases:
                    if p.id == change['purchase_id']:
                        purchase = p
                        break
                
                if purchase:
                    setattr(purchase, change['field'], change['old_value'])
                    purchase.updated_at = datetime.now()
                    
                    # Обновляем в _all_purchases
                    for p in self._all_purchases:
                        if p.id == change['purchase_id']:
                            setattr(p, change['field'], change['old_value'])
                            break
                    
                    self._dirty_ids.add(purchase.id)
            
            # Сохраняем в БД
            if self._dirty_ids:
                self.db_manager.session.commit()
                self._dirty_ids.clear()
            
            # Обновляем отображение
            self.model.beginResetModel()
            self.model._data = self._filtered_purchases
            self.model.endResetModel()
            
            self.save_status_label.setText("↩️ Изменение отменено")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка отмены: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
    
    def _redo_last_change(self):
        """Повторяет отменённое изменение (Ctrl+Y)"""
        if not hasattr(self, '_redo_stack') or not self._redo_stack:
            self.save_status_label.setText("ℹ️ Нет действий для повтора")
            return
        
        try:
            changes = self._redo_stack.pop()
            self._last_changes.append(changes)
            
            for change in changes:
                # Ищем закупку в _filtered_purchases
                purchase = None
                for p in self._filtered_purchases:
                    if p.id == change['purchase_id']:
                        purchase = p
                        break
                
                if purchase:
                    setattr(purchase, change['field'], change['new_value'])
                    purchase.updated_at = datetime.now()
                    
                    # Обновляем в _all_purchases
                    for p in self._all_purchases:
                        if p.id == change['purchase_id']:
                            setattr(p, change['field'], change['new_value'])
                            break
                    
                    self._dirty_ids.add(purchase.id)
            
            # Сохраняем в БД
            if self._dirty_ids:
                self.db_manager.session.commit()
                self._dirty_ids.clear()
            
            # Обновляем отображение
            self.model.beginResetModel()
            self.model._data = self._filtered_purchases
            self.model.endResetModel()
            
            self.save_status_label.setText("↪️ Изменение повторено")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка повтора: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")