# -*- coding: utf-8 -*-

"""
Действия с закупками: добавление, удаление, дублирование, вставка строк
"""
from PySide6.QtCore import Qt, QModelIndex, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QInputDialog, QMessageBox, QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QListWidget, QTableWidget, QTableWidgetItem, QAbstractItemView, QPushButton
from datetime import datetime
 

from database.models import Purchase


class PurchasesActionsMixin:
    """Примесь с методами для работы с закупками"""
    
    def _add_new_purchase(self):
        """Добавляет новую пустую закупку"""
        try:
            new_purchase = Purchase()
            self.db_manager.session.add(new_purchase)
            self.db_manager.session.commit()
            
            self._all_purchases.append(new_purchase)
            self._apply_filters()
            self.load_country_filter()
            
            self.save_status_label.setText(f"✅ Новая закупка добавлена (ID: {new_purchase.id})")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка добавления: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
    
    def _show_import_dialog(self):
        """Показывает диалог импорта закупок"""
        from gui.dialogs.import_purchases_dialog import ImportPurchasesDialog
        dialog = ImportPurchasesDialog(self.db_manager, self)
        if dialog.exec():
            self._full_reload()
    
    def _clear_purchases(self):
        """Удаляет все закупки"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить ВСЕ записи из таблицы закупок?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from database.models import ImportCountry
                self.db_manager.session.query(Purchase).delete()
                self.db_manager.session.query(ImportCountry).delete()
                self.db_manager.session.commit()
                self._all_purchases.clear()
                self._purchase_cache.clear()
                self._filtered_purchases.clear()
                self.model.set_data([])
                if hasattr(self, 'purchase_count_label'):
                    self.purchase_count_label.setText("Записей: 0")
            except Exception as e:
                self.db_manager.session.rollback()
                self.logger.error(f"Ошибка очистки: {e}")
    
    def _delete_selected(self):
        """Удаляет выделенные строки"""
        table = self.purchases_table
        if not table:
            return
        
        selected_rows = set()
        for idx in table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            for idx in table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для удаления")
            return
        
        source_rows = []
        model = table.model()
        
        for row in selected_rows:
            proxy_index = model.index(row, 0)
            if hasattr(model, 'mapToSource'):
                source_index = model.mapToSource(proxy_index)
            else:
                source_index = proxy_index
            source_rows.append(source_index.row())
        
        source_rows = sorted(set(source_rows), reverse=True)
        
        if not source_rows:
            return
        
        count = len(source_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить {count} строк(и)?\n\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        table.setUpdatesEnabled(False)
        self.purchases_table.selectionModel().blockSignals(True)
        
        try:
            deleted_ids = []
            for row in source_rows:
                if row < len(self._filtered_purchases):
                    purchase = self._filtered_purchases[row]
                    if purchase and purchase.id:
                        db_purchase = self.db_manager.session.query(Purchase).get(purchase.id)
                        if db_purchase:
                            self.db_manager.session.delete(db_purchase)
                            deleted_ids.append(purchase.id)
            
            self.db_manager.session.commit()
            
            for row in sorted(source_rows, reverse=True):
                if row < len(self._filtered_purchases):
                    purchase = self._filtered_purchases.pop(row)
                    if purchase in self._all_purchases:
                        self._all_purchases.remove(purchase)
            
            self.model.beginResetModel()
            self.model._data = self._filtered_purchases
            self.model.endResetModel()
            
            self.load_country_filter()
            
            if hasattr(self, 'purchase_count_label'):
                self.purchase_count_label.setText(f"Записей: {len(self._filtered_purchases)}")
            
            self.save_status_label.setText(f"🗑️ Удалено {count} строк")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка удаления: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            table.setUpdatesEnabled(True)
            self.purchases_table.selectionModel().blockSignals(False)
    
    def _duplicate_row(self, row):
        """Дублирует одну строку"""
        if row < 0 or row >= len(self._filtered_purchases):
            return
        
        original = self._filtered_purchases[row]
        if not original:
            return
        
        try:
            new_purchase = Purchase()
            
            for key in self.model.COLUMN_KEYS:
                if key and key != 'row_number':
                    value = getattr(original, key, None)
                    setattr(new_purchase, key, value)
            
            self.db_manager.session.add(new_purchase)
            self.db_manager.session.commit()
            
            self._all_purchases.append(new_purchase)
            self._apply_filters()
            self.load_country_filter()
            
            self.save_status_label.setText("✅ Строка дублирована")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
    
    def _copy_row(self, rows):
        """Копирует строки в буфер"""
        if not rows:
            return
        
        if isinstance(rows, int):
            rows = [rows]
        
        self._copied_row_data = []
        for row in rows:
            if row < len(self._filtered_purchases):
                purchase = self._filtered_purchases[row]
                if purchase:
                    data = {}
                    for key in self.model.COLUMN_KEYS:
                        if key and key != 'row_number':
                            value = getattr(purchase, key, None)
                            data[key] = value
                    self._copied_row_data.append(data)
        
        count = len(self._copied_row_data)
        self.save_status_label.setText(f"📝 Скопировано {count} строк")
        self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
    
    def _paste_full_row(self, row):
        """Вставляет скопированные строки после указанной позиции"""
        if not self._copied_row_data:
            return
        
        if isinstance(self._copied_row_data, dict):
            rows_data = [self._copied_row_data]
        else:
            rows_data = self._copied_row_data
        
        new_purchases = []
        for data in rows_data:
            new_purchase = Purchase(
                in_collection=data.get('in_collection', False),
                collection_price=data.get('collection_price'),
                purchase_number=data.get('purchase_number'),
                purchase_batch=data.get('purchase_batch'),
                import_country_id=data.get('import_country_id'),
                continent=data.get('continent'),
                denomination_value=data.get('denomination_value'),
                currency=data.get('currency'),
                year=data.get('year'),
                location_found=data.get('location_found'),
                quantity=data.get('quantity', 1),
                comments=data.get('comments'),
                ucoin_exchange=data.get('ucoin_exchange', False),
                ucoin_exchange_count=data.get('ucoin_exchange_count', 0),
                sold_count=data.get('sold_count'),
                sold_sum=data.get('sold_sum'),
            )
            
            self.db_manager.session.add(new_purchase)
            self.db_manager.session.flush()
            new_purchases.append(new_purchase)
        
        self.db_manager.session.commit()
        
        for p in new_purchases:
            self._all_purchases.append(p)
            self._purchase_cache[p.id] = p
        
        insert_pos = row + 1
        if insert_pos > len(self._filtered_purchases):
            insert_pos = len(self._filtered_purchases)
        
        for i, p in enumerate(new_purchases):
            self._filtered_purchases.insert(insert_pos + i, p)
        
        self.model.set_data(self._filtered_purchases)
        if hasattr(self, 'purchase_count_label'):
            self.purchase_count_label.setText(f"Записей: {len(self._filtered_purchases)}")
        
        idx = self.model.index(insert_pos, 0)
        self.purchases_table.setCurrentIndex(idx)
        self.purchases_table.scrollTo(idx)
        
        self.save_status_label.setText(f"📋 Вставлено строк: {len(new_purchases)}")
    
    def _goto_purchase_by_number(self, purchase_number):
        """Переходит к закупке по номеру №Пок"""
        if not purchase_number:
            QMessageBox.warning(self, "Предупреждение", "Номер закупки не указан")
            return
        
        self._clear_all_filters()
        
        col_index = 3
        self._column_filters[col_index] = {purchase_number}
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
        
        if self._filtered_purchases:
            count = len(self._filtered_purchases)
            if hasattr(self, 'purchase_count_label'):
                self.purchase_count_label.setText(f"Записей: {count} (фильтр: №{purchase_number})")
            
            QMessageBox.information(
                self, "Фильтр применён",
                f"Показано {count} закупок с номером №{purchase_number}\n"
                f"Фильтр активен. Нажмите на метку фильтра для сброса."
            )
        else:
            QMessageBox.warning(
                self, "Не найдено",
                f"Закупки с номером №{purchase_number} не найдены"
            )
            
            
    def _show_cell_context_menu(self, position):
        """Показывает контекстное меню для ячейки"""
        index = self.purchases_table.indexAt(position)
        if not index.isValid():
            return
        
        row = index.row()
        col = index.column()
        
        source_row = row
        
        if source_row < 0 or source_row >= len(self._filtered_purchases):
            return
        
        value = self.model.data(index, Qt.DisplayRole)
        column_name = self.model.HEADERS[col] if col < len(self.model.HEADERS) else ""
        
        menu = QMenu(self)
        
        title = QAction(f"📌 Колонка: {column_name}", menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()

        menu.addSeparator()
        scan_action = QAction('📷 Сканировать и выставить на Meshok', self)
        scan_action.triggered.connect(self.scan_and_list_selected)
        menu.addAction(scan_action)
        
        # Действия с фильтрацией
        if value and str(value).strip():
            filter_action = QAction(f"🔍 Показать только «{value}»", menu)
            filter_action.triggered.connect(lambda: self._filter_by_value(col, value))
            menu.addAction(filter_action)
            
            exclude_action = QAction(f"🚫 Скрыть «{value}»", menu)
            exclude_action.triggered.connect(lambda: self._filter_exclude_value(col, value))
            menu.addAction(exclude_action)
            
            menu.addSeparator()
        
        # Копировать/Вставить
        copy_action = QAction("📋 Копировать ячейку", menu)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        paste_action = QAction("📌 Вставить", menu)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self._paste_to_selected_cells)
        menu.addAction(paste_action)
        
        # Очистить
        clear_action = QAction("🧹 Очистить ячейку", menu)
        clear_action.triggered.connect(self._clear_selected_cells)
        menu.addAction(clear_action)
        
        menu.addSeparator()
        
        # Вернуть в продажу
        return_to_sale_action = QAction("🔄 Вернуть в продажу", menu)
        return_to_sale_action.triggered.connect(self._return_to_sale)
        menu.addAction(return_to_sale_action)
        
        # Добавить к заказу
        add_to_order_action = QAction("➕ Добавить к заказу", menu)
        add_to_order_action.triggered.connect(self._add_to_order)
        menu.addAction(add_to_order_action)
        
        # Выставить на обмен
        exchange_action = QAction("🔄 Выставить на обмен", menu)
        exchange_action.triggered.connect(self._set_exchange_selected)
        menu.addAction(exchange_action)
        
        # Отложено
        delayed_action = QAction("⏸️ Отложено", menu)
        delayed_action.triggered.connect(self._set_delayed_selected)
        menu.addAction(delayed_action)
        
        menu.addSeparator()
        
        # Переместить в мусор
        trash_action = QAction("🗑️ Переместить в МУСОР", menu)
        trash_action.triggered.connect(self._move_to_trash)
        menu.addAction(trash_action)
        
        # Продать мусор
        sell_trash_action = QAction("💰 Продать мусор", menu)
        sell_trash_action.triggered.connect(self._sell_trash)
        menu.addAction(sell_trash_action)
        
        menu.addSeparator()
        
        # Показать дубли
        show_duplicates_action = QAction("🔍 Показать ДУБЛИ", menu)
        show_duplicates_action.triggered.connect(self._show_duplicates)
        menu.addAction(show_duplicates_action)
        
        menu.addSeparator()
        
        # Открыть на Мешке
        open_meshok_action = QAction("📦 Открыть на МЕШОК", menu)
        open_meshok_action.triggered.connect(self._open_meshok_for_selected)
        menu.addAction(open_meshok_action)
        
        menu.addSeparator()
        
        # Отмена
        undo_action = QAction("↩ Отменить", menu)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self._undo_last_change)
        menu.addAction(undo_action)
        
        menu.exec(self.purchases_table.viewport().mapToGlobal(position))
    
    def _show_row_context_menu(self, position):
        """Показывает контекстное меню для строки"""
        row = self.purchases_table.verticalHeader().logicalIndexAt(position)
        if row < 0 or row >= self.purchases_table.model().rowCount():
            return
        
        selected_rows = set()
        for idx in self.purchases_table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            selected_rows.add(row)
        
        source_rows = []
        for r in selected_rows:
            source_rows.append(self._get_source_row(r))
        
        source_rows = sorted(set(source_rows))
        count = len(source_rows)
        
        menu = QMenu(self)
        
        # Вставка строк
        insert_menu = menu.addMenu("⬇️ Вставить строки")
        insert_menu.addAction("1 строку", lambda: self._insert_empty_row(row))
        insert_menu.addAction("5 строк", lambda: self._insert_n_rows(row, 5))
        insert_menu.addAction("10 строк", lambda: self._insert_n_rows(row, 10))
        insert_menu.addAction("✏️ Своё количество...", lambda: self._insert_n_rows(row, None))
        
        menu.addSeparator()
        
        # Дублирование
        menu.addAction(f"📋 Дублировать {count} строк", lambda: self._duplicate_selected_rows(source_rows))
        menu.addSeparator()
        
        # Копировать/Вставить строки
        copy_action = QAction("📝 Копировать строки", menu)
        copy_action.triggered.connect(lambda: self._copy_row(source_rows))
        menu.addAction(copy_action)
        
        paste_action = QAction("📋 Вставить строки из буфера", menu)
        paste_action.setEnabled(self._copied_row_data is not None)
        paste_action.triggered.connect(lambda: self._paste_full_row(row))
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # Очистка строк
        clear_rows_action = QAction("🧹 Очистить выделенные строки", menu)
        clear_rows_action.triggered.connect(self._clear_selected_rows)
        menu.addAction(clear_rows_action)
        
        menu.addSeparator()
        
        # Удаление
        menu.addAction(f"🗑️ Удалить {count} строк", self._delete_selected)
        
        menu.exec(self.purchases_table.verticalHeader().mapToGlobal(position))
    
    def _insert_empty_row(self, row):
        """Вставляет одну пустую строку"""
        self.purchases_table.setUpdatesEnabled(False)
        self.model.blockSignals(True)
        
        try:
            source_row = row
            
            source_purchase_number = None
            if source_row > 0 and source_row - 1 < len(self._filtered_purchases):
                source_purchase = self._filtered_purchases[source_row - 1]
                if source_purchase:
                    source_purchase_number = source_purchase.purchase_number
            
            new_purchase = Purchase()
            new_purchase.purchase_batch = "0"
            new_purchase.purchase_number = source_purchase_number
            new_purchase.quantity = 1
            
            self.db_manager.session.add(new_purchase)
            self.db_manager.session.flush()
            self.db_manager.session.commit()
            
            if new_purchase.import_country_id:
                new_purchase.import_country = self.db_manager.session.query(ImportCountry).get(new_purchase.import_country_id)
            
            self._all_purchases.append(new_purchase)
            self._purchase_cache[new_purchase.id] = new_purchase
            
            old_count = len(self._filtered_purchases)
            self._filtered_purchases.append(new_purchase)
            
            self.model.beginInsertRows(QModelIndex(), old_count, old_count)
            self.model._data = self._filtered_purchases
            self.model.endInsertRows()
            
            if hasattr(self, 'purchase_count_label'):
                self.purchase_count_label.setText(f"Записей: {len(self._filtered_purchases)}")
            
            last_row = self.model.rowCount() - 1
            if last_row >= 0:
                idx = self.model.index(last_row, 0)
                self.purchases_table.setCurrentIndex(idx)
                self.purchases_table.scrollTo(idx)
            
            self.save_status_label.setText(f"✅ Добавлена строка (в конец таблицы)")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(3000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки строки: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            self.model.blockSignals(False)
            self.purchases_table.setUpdatesEnabled(True)
            self.purchases_table.viewport().update()
    
    def _insert_n_rows(self, row, n):
        """Вставляет N пустых строк"""
        if n is None:
            n, ok = QInputDialog.getInt(self, "Вставить строки", "Количество строк:", 5, 1, 100, 1)
            if not ok:
                return
        
        self.purchases_table.setUpdatesEnabled(False)
        
        try:
            source_row = self._get_source_row(row)
            
            source_purchase_number = None
            if source_row > 0 and source_row - 1 < len(self._filtered_purchases):
                source_purchase = self._filtered_purchases[source_row - 1]
                if source_purchase:
                    source_purchase_number = source_purchase.purchase_number
            
            new_purchases = []
            for _ in range(n):
                new_purchase = Purchase()
                new_purchase.purchase_batch = "0"
                new_purchase.purchase_number = source_purchase_number
                new_purchase.quantity = 1
                self.db_manager.session.add(new_purchase)
                self.db_manager.session.flush()
                new_purchases.append(new_purchase)
            
            self.db_manager.session.commit()
            
            for p in new_purchases:
                if p.import_country_id:
                    p.import_country = self.db_manager.session.query(ImportCountry).get(p.import_country_id)
            
            for p in new_purchases:
                self._all_purchases.append(p)
                self._purchase_cache[p.id] = p
            
            filtered_new = []
            for p in new_purchases:
                country_id = self.country_filter.currentData()
                if country_id and p.import_country_id != country_id:
                    continue
                if self._column_filters:
                    match = True
                    for li, filter_val in self._column_filters.items():
                        actual_val = self._get_column_value(p, li)
                        if isinstance(filter_val, set):
                            if not actual_val.strip():
                                if "__EMPTY__" not in filter_val:
                                    match = False
                                    break
                            elif actual_val not in filter_val:
                                match = False
                                break
                    if not match:
                        continue
                filtered_new.append(p)
            
            if filtered_new:
                old_count = len(self._filtered_purchases)
                for p in filtered_new:
                    self._filtered_purchases.append(p)
                
                self.model.set_data(self._filtered_purchases)
                
                if hasattr(self, 'purchase_count_label'):
                    self.purchase_count_label.setText(f"Записей: {len(self._filtered_purchases)}")
                
                QTimer.singleShot(100, self._scroll_to_bottom)
            
            self.save_status_label.setText(f"✅ Добавлено {len(filtered_new)} строк (из {n})")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(3000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки строк: {e}")
            import traceback
            traceback.print_exc()
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            self.purchases_table.setUpdatesEnabled(True)
            self.purchases_table.viewport().update()
    
    def _duplicate_selected_rows(self, source_rows):
        """Дублирует несколько строк"""
        if not source_rows:
            return
        
        count = len(source_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение", f"Дублировать {count} строк(и)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.purchases_table.setUpdatesEnabled(False)
        
        try:
            new_purchases = []
            
            for row in source_rows:
                if row < len(self._filtered_purchases):
                    original = self._filtered_purchases[row]
                    if original:
                        if original.import_country_id and not original.import_country:
                            original.import_country = self.db_manager.session.query(ImportCountry).get(original.import_country_id)
                        
                        new_purchase = Purchase()
                        
                        new_purchase.in_collection = original.in_collection
                        new_purchase.collection_price = original.collection_price
                        new_purchase.purchase_number = original.purchase_number
                        new_purchase.purchase_batch = original.purchase_batch
                        new_purchase.import_country_id = original.import_country_id
                        new_purchase.continent = original.continent
                        new_purchase.denomination_value = original.denomination_value
                        new_purchase.currency = original.currency
                        new_purchase.year = original.year
                        new_purchase.location_found = original.location_found
                        new_purchase.quantity = original.quantity
                        new_purchase.comments = original.comments
                        new_purchase.ucoin_exchange = original.ucoin_exchange
                        new_purchase.ucoin_exchange_count = original.ucoin_exchange_count
                        new_purchase.sold_count = None
                        new_purchase.sold_sum = None
                        new_purchase.total = original.total
                        
                        self.db_manager.session.add(new_purchase)
                        self.db_manager.session.flush()
                        new_purchases.append(new_purchase)
            
            self.db_manager.session.commit()
            
            if not new_purchases:
                return
            
            for p in new_purchases:
                if p.import_country_id:
                    p.import_country = self.db_manager.session.query(ImportCountry).get(p.import_country_id)
            
            for p in new_purchases:
                self._all_purchases.append(p)
            
            filtered_new = []
            for p in new_purchases:
                country_id = self.country_filter.currentData()
                if country_id and p.import_country_id != country_id:
                    continue
                if self._column_filters:
                    match = True
                    for li, filter_val in self._column_filters.items():
                        actual_val = self._get_column_value(p, li)
                        if isinstance(filter_val, set):
                            if not actual_val.strip():
                                if "__EMPTY__" not in filter_val:
                                    match = False
                                    break
                            elif actual_val not in filter_val:
                                match = False
                                break
                    if not match:
                        continue
                filtered_new.append(p)
            
            if filtered_new:
                old_count = len(self._filtered_purchases)
                for p in filtered_new:
                    self._filtered_purchases.append(p)
                
                self.model.set_data(self._filtered_purchases)
                self.load_country_filter()
                
                if hasattr(self, 'purchase_count_label'):
                    self.purchase_count_label.setText(f"Записей: {len(self._filtered_purchases)}")
                
                QTimer.singleShot(100, self._scroll_to_bottom)
            
            self.save_status_label.setText(f"✅ Дублировано {len(filtered_new)} строк (из {len(new_purchases)})")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(3000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка дублирования: {e}")
            import traceback
            traceback.print_exc()
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            self.purchases_table.setUpdatesEnabled(True)
            self.purchases_table.viewport().update()
    
    def _clear_selected_cells(self):
        """Очищает содержимое выделенных ячеек"""
        table = self.purchases_table
        if not table:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Предупреждение", "Выделите ячейки для очистки")
            return
        
        changes = []
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            source_row = self._get_source_row(row)
            
            if source_row < len(self._filtered_purchases):
                purchase = self._filtered_purchases[source_row]
                if purchase:
                    field_name = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                    if field_name:
                        old_value = getattr(purchase, field_name, None)
                        new_value = ""
                        
                        changes.append({
                            'purchase_id': purchase.id,
                            'field': field_name,
                            'old_value': old_value,
                            'new_value': new_value
                        })
                        
                        setattr(purchase, field_name, new_value if new_value else None)
                        purchase.updated_at = datetime.now()
                        self._dirty_ids.add(purchase.id)
        
        if changes:
            self._last_changes.append(changes)
            if len(self._last_changes) > 50:
                self._last_changes.pop(0)
        
        self.model.set_data(self._filtered_purchases)
        
        self.save_status_label.setText(f"🧹 Очищено {len(selected_indexes)} ячеек")
        self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
    
    def _clear_selected_rows(self):
        """Очищает все ячейки в выделенных строках"""
        table = self.purchases_table
        if not table:
            return
        
        selected_rows = set()
        for idx in table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            for idx in table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для очистки")
            return
        
        changes = []
        
        for proxy_row in selected_rows:
            source_row = self._get_source_row(proxy_row)
            if source_row < len(self._filtered_purchases):
                purchase = self._filtered_purchases[source_row]
                if purchase:
                    for col, field_name in enumerate(self.COLUMN_KEYS):
                        if field_name and field_name != 'row_number':
                            old_value = getattr(purchase, field_name, None)
                            if old_value is not None and old_value != "":
                                changes.append({
                                    'purchase_id': purchase.id,
                                    'field': field_name,
                                    'old_value': old_value,
                                    'new_value': ""
                                })
                                setattr(purchase, field_name, None)
                                purchase.updated_at = datetime.now()
                                self._dirty_ids.add(purchase.id)
        
        if changes:
            self._last_changes.append(changes)
            if len(self._last_changes) > 50:
                self._last_changes.pop(0)
        
        self.model.set_data(self._filtered_purchases)
        
        self.save_status_label.setText(f"🧹 Очищено {len(selected_rows)} строк")
        self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
        
        
    def _return_to_sale(self):
        """Возвращает закупку в продажу"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для возврата в продажу")
            return
        
        count = len(selected_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вернуть в продажу {count} закупок?\n\n"
            f"Будут очищены:\n"
            f"  • №Пок (purchase_batch) → 0\n"
            f"  • Место (location_found) → пусто\n"
            f"  • Обмен (ucoin_exchange) → КОЛ (quantity)\n"
            f"  • Сумма (sold_sum) → пусто\n"
            f"  • Продано (sold_count) → пусто",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            updated_count = 0
            for row in selected_rows:
                if row < len(self._filtered_purchases):
                    purchase = self._filtered_purchases[row]
                    if purchase:
                        # №Пок = 0
                        purchase.purchase_batch = "0"
                        # Место = пусто
                        purchase.location_found = None
                        # Обмен = КОЛ (quantity)
                        quantity = purchase.quantity or 1
                        purchase.ucoin_exchange = True
                        purchase.ucoin_exchange_count = quantity
                        # Сумма = пусто
                        purchase.sold_sum = None
                        # Продано = пусто
                        purchase.sold_count = None
                        self._dirty_ids.add(purchase.id)
                        updated_count += 1
            
            self._save_timer.stop()
            self._flush_changes()
            self._apply_filters()
            
            self.save_status_label.setText(f"✅ Возвращено в продажу: {updated_count} закупок")
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка возврата в продажу: {e}")
    
    def _add_to_order(self):
        """Добавляет закупку к заказу"""
        from database.models import Deal
        
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для добавления к заказу")
            return
        
        open_deals = self.db_manager.session.query(Deal).filter(
            (Deal.delivery != '✅') | (Deal.delivery.is_(None))
        ).order_by(Deal.number).all()
        
        if not open_deals:
            QMessageBox.warning(self, "Предупреждение", "Нет незакрытых сделок")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите заказ")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Выберите заказ для добавления:"))
        
        list_widget = QListWidget()
        for deal in open_deals:
            deal_number = getattr(deal, 'number', '')
            deal_buyer = getattr(deal, 'buyer', '')
            list_widget.addItem(f"№{deal_number} - {deal_buyer}")
            list_widget.item(list_widget.count() - 1).setData(Qt.UserRole, deal)
        
        layout.addWidget(list_widget)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ Добавить")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        selected_deal = list_widget.currentItem().data(Qt.UserRole) if list_widget.currentItem() else None
        if not selected_deal:
            return
        
        deal_number = getattr(selected_deal, 'number', '')
        deal_buyer = getattr(selected_deal, 'buyer', '')
        
        if not deal_number:
            return
        
        count = len(selected_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Добавить {count} закупок к заказу №{deal_number} (НИК: {deal_buyer})?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            updated_count = 0
            for row in selected_rows:
                if row < len(self._filtered_purchases):
                    purchase = self._filtered_purchases[row]
                    if purchase:
                        purchase.purchase_batch = str(deal_number)
                        purchase.sold_count = deal_buyer
                        self._dirty_ids.add(purchase.id)
                        updated_count += 1
            
            self._save_timer.stop()
            self._flush_changes()
            self._apply_filters()
            
            self.save_status_label.setText(f"✅ Добавлено {updated_count} закупок к заказу №{deal_number}")
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка добавления к заказу: {e}")
    
    def _get_selected_rows(self):
        """Возвращает список индексов выделенных строк"""
        selected_rows = set()
        for idx in self.purchases_table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            for idx in self.purchases_table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())
        
        return sorted(selected_rows, reverse=True)
    
    def _set_exchange_selected(self):
        """Выставляет выделенные закупки на обмен"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите закупки для выставления на обмен")
            return
        
        count = len(selected_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Выставить на обмен {count} закупок?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        updated_count = 0
        for row in selected_rows:
            if row < len(self._filtered_purchases):
                purchase = self._filtered_purchases[row]
                if purchase:
                    quantity = purchase.quantity or 1
                    purchase.ucoin_exchange = True
                    purchase.ucoin_exchange_count = quantity
                    self._dirty_ids.add(purchase.id)
                    updated_count += 1
        
        self._save_timer.stop()
        self._flush_changes()
        self.model.set_data(self._filtered_purchases)
        self.save_status_label.setText(f"✅ Выставлено на обмен: {updated_count} закупок")
    
    def _set_delayed_selected(self):
        """Помечает выделенные закупки как отложенные"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите закупки для отметки 'Отложено'")
            return
        
        count = len(selected_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Отметить {count} закупок как 'Отложено'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        updated_count = 0
        for row in selected_rows:
            if row < len(self._filtered_purchases):
                purchase = self._filtered_purchases[row]
                if purchase:
                    purchase.location_found = "N"
                    purchase.sold_count = None
                    purchase.purchase_batch = "0"
                    purchase.sold_sum = None
                    purchase.total = None
                    self._dirty_ids.add(purchase.id)
                    updated_count += 1
        
        self._save_timer.stop()
        self._flush_changes()
        self.model.set_data(self._filtered_purchases)
        self.save_status_label.setText(f"✅ Отмечено как 'Отложено': {updated_count} закупок")
    
    def _move_to_trash(self):
        """Перемещает выделенные строки в мусор"""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для перемещения в мусор")
            return
        
        count = len(selected_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Переместить {count} закупок в мусор?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        updated_count = 0
        for row in selected_rows:
            if row < len(self._filtered_purchases):
                purchase = self._filtered_purchases[row]
                if purchase:
                    purchase.purchase_batch = "Т"
                    purchase.sold_count = None
                    self._dirty_ids.add(purchase.id)
                    updated_count += 1
        
        self._save_timer.stop()
        self._flush_changes()
        self._apply_filters()
        self.save_status_label.setText(f"✅ Перемещено в мусор: {updated_count} закупок")
    
    def _sell_trash(self):
        """Продажа мусорных монет"""
        from database.models import Deal
        
        trash_purchases = []
        trash_quantity = 0
        
        for row, purchase in enumerate(self._filtered_purchases):
            if purchase and purchase.purchase_batch == "Т":
                qty = purchase.quantity or 1
                trash_quantity += qty
                trash_purchases.append((row, purchase, qty))
        
        if not trash_purchases:
            QMessageBox.warning(self, "Предупреждение", "Нет закупок, помеченных как мусор (№Пок = 'Т')")
            return
        
        open_deals = self.db_manager.session.query(Deal).filter(
            (Deal.delivery != '✅') | (Deal.delivery.is_(None))
        ).order_by(Deal.number).all()
        
        if not open_deals:
            QMessageBox.warning(self, "Предупреждение", "Нет незакрытых сделок")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Продажа мусора")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"📊 Выбрано монет: {trash_quantity} шт."))
        layout.addWidget(QLabel(f"📋 Количество строк: {len(trash_purchases)}"))
        layout.addWidget(QLabel("Выберите сделку:"))
        
        deal_combo = QComboBox()
        for deal in open_deals:
            deal_number = getattr(deal, 'number', '')
            deal_buyer = getattr(deal, 'buyer', '')
            deal_combo.addItem(f"№{deal_number} - {deal_buyer}", deal.id)
        layout.addWidget(deal_combo)
        
        layout.addWidget(QLabel("Общая сумма продажи (₽):"))
        amount_edit = QLineEdit()
        amount_edit.setPlaceholderText("Введите сумму...")
        layout.addWidget(amount_edit)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ Продать")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        deal_id = deal_combo.currentData()
        total_amount_str = amount_edit.text().strip()
        
        if not total_amount_str:
            QMessageBox.warning(self, "Предупреждение", "Введите сумму продажи")
            return
        
        try:
            total_amount = float(total_amount_str.replace(',', '.'))
        except ValueError:
            QMessageBox.warning(self, "Предупреждение", "Введите корректную сумму")
            return
        
        selected_deal = self.db_manager.session.query(Deal).get(deal_id)
        if not selected_deal:
            return
        
        deal_number = getattr(selected_deal, 'number', '')
        deal_buyer = getattr(selected_deal, 'buyer', '')
        price_per_coin = total_amount / trash_quantity
        
        try:
            updated_count = 0
            for row, purchase, qty in trash_purchases:
                purchase.purchase_batch = str(deal_number)
                purchase.sold_count = deal_buyer
                purchase.sold_sum = round(price_per_coin * qty, 2)
                purchase.total = purchase.sold_sum
                self._dirty_ids.add(purchase.id)
                updated_count += 1
            
            selected_deal.amount = str(total_amount)
            selected_deal.updated_at = datetime.now()
            self.db_manager.session.commit()
            
            main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
            
            if main_window and hasattr(main_window, 'exchange_tab'):
                deals_tab = main_window.exchange_tab.deals_tab
                if deals_tab:
                    deals_tab._refresh_all()
            
            self._save_timer.stop()
            self._flush_changes()
            self._apply_filters()
            
            self.save_status_label.setText(f"✅ Продано мусора: {updated_count} строк, {trash_quantity} монет, на сумму {total_amount:.2f} ₽")
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка продажи мусора: {e}")
    
    def _show_duplicates(self):
        """Показывает диалог с дубликатами монеты для выбора (с сортировкой)"""
        # Получаем текущую выделенную строку
        current_row = self.purchases_table.currentIndex().row()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выделите строку с монетой")
            return
        
        if current_row >= len(self._filtered_purchases):
            return
        
        current_purchase = self._filtered_purchases[current_row]
        if not current_purchase:
            return
        
        # Формируем данные для поиска
        country_name = current_purchase.import_country.name if current_purchase.import_country else ""
        denomination = current_purchase.denomination_value or ""
        year = current_purchase.year or ""
        currency = current_purchase.currency or ""
        
        self.logger.info(f"Поиск дублей для: страна={country_name}, номинал={denomination}, год={year}, валюта={currency}")
        
        # Ищем похожие закупки (не помеченные как проданные и не мусор)
        similar_purchases = []
        for p in self._all_purchases:
            if p.id == current_purchase.id:
                continue
            
            # Пропускаем уже проданные
            if p.sold_count and str(p.sold_count).strip():
                continue
            
            # Пропускаем мусор
            if p.purchase_batch == "Т":
                continue
            
            # Сравниваем страну
            p_country = p.import_country.name if p.import_country else ""
            if not self._fuzzy_match(p_country, country_name):
                continue
            
            # Сравниваем год
            if year and p.year != year:
                continue
            
            # Сравниваем номинал
            if denomination and p.denomination_value != denomination:
                continue
            
            similar_purchases.append(p)
            self.logger.info(f"  Найден дубль: ID={p.id}, №Зак={p.purchase_number}")
        
        if not similar_purchases:
            QMessageBox.information(self, "Информация", "Похожие монеты не найдены")
            return
        
        # Диалог выбора
        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 Похожие монеты")
        dialog.setMinimumWidth(850)
        dialog.setMinimumHeight(450)
        
        layout = QVBoxLayout(dialog)
        dialog.setLayout(layout)
        
        # Информация о текущей монете
        info_label = QLabel(
            f"<b>Текущая монета:</b><br>"
            f"Страна: {country_name}<br>"
            f"Номинал: {denomination}<br>"
            f"Год: {year}<br>"
            f"Валюта: {currency}<br>"
            f"№Зак: {current_purchase.purchase_number or '—'}"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #e8f4f8; padding: 10px; border-radius: 5px;")
        layout.addWidget(info_label)
        
        layout.addWidget(QLabel("<b>Выберите монету для замены/дублирования:</b>"))
        
        # Таблица для отображения похожих монет
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "ID", "Страна", "Номинал", "Валюта", "Год", "Кол-во", "№Зак", "№Пок", "Коментарии"
        ])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Включаем сортировку
        table.setSortingEnabled(True)
        
        # Настройка ширины колонок
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # Страна
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Номинал
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Валюта
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Год
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Кол-во
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # №Зак
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # №Пок
        header.setSectionResizeMode(8, QHeaderView.Stretch)           # Коментарии
        
        # Устанавливаем сортировку по №Зак по умолчанию (по возрастанию)
        header.setSortIndicator(6, Qt.AscendingOrder)
        
        table.setRowCount(len(similar_purchases))
        
        # Вспомогательная функция для получения числового значения №Зак для сортировки
        def get_number_value(purchase):
            try:
                if purchase.purchase_number:
                    return int(purchase.purchase_number)
                return 0
            except (ValueError, TypeError):
                return 0
        
        # Сортируем по №Зак по умолчанию (по возрастанию)
        similar_purchases_sorted = sorted(similar_purchases, key=get_number_value)
        
        for row, p in enumerate(similar_purchases_sorted):
            p_country = p.import_country.name if p.import_country else "—"
            p_currency = p.currency or "—"
            p_comments = p.comments or "—"
            
            # ID
            id_item = QTableWidgetItem(str(p.id))
            id_item.setData(Qt.UserRole, p.id)
            id_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 0, id_item)
            
            # Страна
            country_item = QTableWidgetItem(p_country)
            table.setItem(row, 1, country_item)
            
            # Номинал
            denom_item = QTableWidgetItem(p.denomination_value or "—")
            table.setItem(row, 2, denom_item)
            
            # Валюта
            currency_item = QTableWidgetItem(p_currency)
            currency_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 3, currency_item)
            
            # Год
            year_item = QTableWidgetItem(str(p.year) if p.year else "—")
            year_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 4, year_item)
            
            # Количество
            qty_item = QTableWidgetItem(str(p.quantity or 1))
            qty_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 5, qty_item)
            
            # №Зак (purchase_number) - с числовыми данными для сортировки
            number_value = p.purchase_number if p.purchase_number else "—"
            number_item = QTableWidgetItem(str(number_value))
            number_item.setTextAlignment(Qt.AlignCenter)
            # Сохраняем числовое значение для правильной сортировки
            try:
                number_item.setData(Qt.UserRole + 1, int(number_value) if number_value != "—" else 0)
            except (ValueError, TypeError):
                number_item.setData(Qt.UserRole + 1, 0)
            table.setItem(row, 6, number_item)
            self.logger.info(f"  Строка {row}: ID={p.id}, №Зак={number_value}")
            
            # №Пок (purchase_batch)
            batch_item = QTableWidgetItem(p.purchase_batch or "—")
            batch_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 7, batch_item)
            
            # Коментарии
            comments_item = QTableWidgetItem(p_comments)
            comments_item.setToolTip(p_comments if len(p_comments) > 50 else "")
            table.setItem(row, 8, comments_item)
        
        # Настройка пользовательской сортировки для колонки №Зак
        class NumericTableWidgetItem(QTableWidgetItem):
            def __lt__(self, other):
                if isinstance(other, QTableWidgetItem):
                    my_val = self.data(Qt.UserRole + 1)
                    other_val = other.data(Qt.UserRole + 1)
                    if my_val is not None and other_val is not None:
                        try:
                            return int(my_val) < int(other_val)
                        except (ValueError, TypeError):
                            pass
                return super().__lt__(other)
        
        # Заменяем элементы колонки №Зак на NumericTableWidgetItem для правильной сортировки
        for row in range(table.rowCount()):
            item = table.item(row, 6)
            if item:
                num_item = NumericTableWidgetItem(item.text())
                num_item.setData(Qt.UserRole, item.data(Qt.UserRole))
                num_item.setData(Qt.UserRole + 1, item.data(Qt.UserRole + 1))
                num_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, 6, num_item)
        
        # Автоматически подгоняем ширину колонок
        table.resizeColumnsToContents()
        
        layout.addWidget(table)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        duplicate_btn = QPushButton("📋 Дублировать")
        duplicate_btn.clicked.connect(lambda: self._duplicate_and_replace(
            current_purchase, similar_purchases_sorted, table, 'duplicate', dialog
        ))
        duplicate_btn.setMinimumHeight(35)
        duplicate_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_layout.addWidget(duplicate_btn)
        
        replace_btn = QPushButton("🔄 Заменить")
        replace_btn.clicked.connect(lambda: self._duplicate_and_replace(
            current_purchase, similar_purchases_sorted, table, 'replace', dialog
        ))
        replace_btn.setMinimumHeight(35)
        replace_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        btn_layout.addWidget(replace_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setMinimumHeight(35)
        cancel_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def _replace_duplicate(self, current_purchase, similar_purchases, table, dialog):
        """Заменяет монету выбранной"""
        current_row = table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монету из списка")
            return
        
        selected_id = table.item(current_row, 0).data(Qt.UserRole)
        selected_purchase = None
        for p in similar_purchases:
            if p.id == selected_id:
                selected_purchase = p
                break
        
        if not selected_purchase:
            return
        
        try:
            deal_batch = current_purchase.purchase_batch
            deal_sold = current_purchase.sold_count
            deal_sold_sum = current_purchase.sold_sum
            deal_total = current_purchase.total
            
            current_purchase.purchase_batch = "0"
            current_purchase.sold_count = None
            current_purchase.sold_sum = None
            current_purchase.total = None
            
            selected_purchase.purchase_batch = deal_batch
            selected_purchase.sold_count = deal_sold
            selected_purchase.sold_sum = deal_sold_sum
            selected_purchase.total = deal_total
            self._dirty_ids.add(selected_purchase.id)
            self._dirty_ids.add(current_purchase.id)
            
            self.db_manager.session.commit()
            self._apply_filters()
            
            QMessageBox.information(self, "Успех", "✅ Монета заменена!")
            dialog.accept()
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка замены: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось заменить монету:\n{e}")
    
    def _duplicate_and_replace(self, current_purchase, similar_purchases, table, action, dialog):
        """Дублирует или заменяет монету"""
        current_row = table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монету из списка")
            return
        
        selected_id = table.item(current_row, 0).data(Qt.UserRole)
        selected_purchase = None
        for p in similar_purchases:
            if p.id == selected_id:
                selected_purchase = p
                break
        
        if not selected_purchase:
            return
        
        try:
            if action == 'duplicate':
                new_purchase = Purchase()
                for col in ['in_collection', 'collection_price', 'purchase_number',
                           'import_country_id', 'continent', 'denomination_value',
                           'currency', 'year', 'location_found', 'quantity',
                           'comments', 'ucoin_exchange', 'ucoin_exchange_count']:
                    setattr(new_purchase, col, getattr(current_purchase, col, None))
                
                new_purchase.purchase_batch = current_purchase.purchase_batch
                new_purchase.sold_count = current_purchase.sold_count
                new_purchase.sold_sum = current_purchase.sold_sum
                new_purchase.total = current_purchase.total
                new_purchase.quantity = current_purchase.quantity or 1
                
                self.db_manager.session.add(new_purchase)
                self.db_manager.session.flush()
                
                self._all_purchases.append(new_purchase)
                self._filtered_purchases.append(new_purchase)
                
                QMessageBox.information(self, "Успех", f"✅ Монета дублирована!\nНовая ID: {new_purchase.id}")
                
            else:  # replace
                deal_batch = current_purchase.purchase_batch
                deal_sold = current_purchase.sold_count
                deal_sold_sum = current_purchase.sold_sum
                deal_total = current_purchase.total
                
                current_purchase.purchase_batch = "0"
                current_purchase.sold_count = None
                current_purchase.sold_sum = None
                current_purchase.total = None
                
                selected_purchase.purchase_batch = deal_batch
                selected_purchase.sold_count = deal_sold
                selected_purchase.sold_sum = deal_sold_sum
                selected_purchase.total = deal_total
                self._dirty_ids.add(selected_purchase.id)
                self._dirty_ids.add(current_purchase.id)
                
                QMessageBox.information(self, "Успех", "✅ Монета заменена!")
            
            self.db_manager.session.commit()
            self._apply_filters()
            dialog.accept()
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить операцию:\n{e}")
    
    def _open_meshok_for_selected(self):
        """Открывает поиск на Мешке для выделенной закупки"""
        selected_rows = set()
        for idx in self.purchases_table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            for idx in self.purchases_table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите закупку для поиска")
            return
        
        row = next(iter(selected_rows))
        source_row = self._get_source_row(row)
        
        if source_row < len(self._filtered_purchases):
            purchase = self._filtered_purchases[source_row]
            if purchase:
                self._open_meshok_for_purchase(purchase)
    
    def _open_meshok_for_purchase(self, purchase):
        """Открывает страницу поиска на Meshok для указанной закупки"""
        if not self.embedded_browser:
            QMessageBox.warning(self, "Ошибка", "Браузер не доступен")
            return
        
        country_name = purchase.import_country.name if purchase.import_country else ""
        denomination = purchase.denomination_value or ""
        currency = purchase.currency or ""
        year = purchase.year or ""
        
        if not country_name:
            QMessageBox.warning(self, "Предупреждение", "У закупки не указана страна")
            return
        
        # Формируем поисковый запрос: Страна + Номинал + Валюта + Год
        search_parts = []
        if country_name:
            search_parts.append(country_name)
        if denomination:
            search_parts.append(denomination)
        if currency:
            search_parts.append(currency)
        if year:
            search_parts.append(str(year))
        
        search_query = " ".join(search_parts).strip()
        
        if not search_query:
            QMessageBox.warning(self, "Предупреждение", "Недостаточно данных для поиска")
            return
        
        from urllib.parse import quote
        url = f"https://meshok.net/listing?good=252&opt=3&search={quote(search_query)}&sort=cur_price"
        
        if not self.right_panel_visible:
            self._toggle_browser_panel()
        
        if hasattr(self.embedded_browser, 'add_new_tab'):
            self.embedded_browser.add_new_tab(url)
        elif hasattr(self.embedded_browser, 'web_view'):
            from PySide6.QtCore import QUrl
            self.embedded_browser.web_view.setUrl(QUrl(url))
        
        self.browser_info_label.setText(f"📦 Поиск на Мешке: {search_query}")
        self.save_status_label.setText(f"📦 Открыт поиск на Мешке для: {search_query}")

    def _flush_all_changes(self):
        """Сохраняет все несохранённые изменения в БД"""
        try:
            # Сохраняем dirty изменения
            if hasattr(self, '_dirty_ids') and self._dirty_ids:
                self.db_manager.session.commit()
                self._dirty_ids.clear()
                self.logger.info(f"  ✅ Сохранено {len(self._dirty_ids)} изменений в закупках")
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения закупок: {e}")
            raise
            
    def scan_and_list_selected(self):
        """ПКМ по закупке → «📷 Сканировать и выставить на Meshok».
        Описание лота парсится из СТРАНИЦЫ, ОТКРЫТОЙ В БРАУЗЕРЕ ЗАКУПОК
        (вкладка «Продажи») — без нейросетей."""
        from PySide6.QtWidgets import QMessageBox
        try:
            table = getattr(self, 'purchases_table', None) or getattr(self, 'table', None)
            if table is None:
                QMessageBox.warning(self, 'Предупреждение',
                                    'Таблица закупок не инициализирована.')
                return
            index = table.currentIndex()
            if index is None or not index.isValid():
                QMessageBox.warning(self, 'Предупреждение',
                                    'Выделите строку закупки.')
                return
            row = index.row()
            source_row = row
            try:
                model = table.model()
                if model is not None and hasattr(model, 'mapToSource'):
                    source_row = model.mapToSource(index).row()
            except Exception:
                source_row = row
            purchases = getattr(self, '_filtered_purchases', None) or []
            if not (0 <= source_row < len(purchases)):
                QMessageBox.warning(self, 'Предупреждение',
                                    'Не удалось определить выбранную закупку.')
                return
            purchase = purchases[source_row]

            # Текущая вкладка браузера закупок (вкладка «Продажи»)
            web_view = None
            try:
                eb = getattr(self, 'embedded_browser', None)
                if eb is not None and hasattr(eb, 'get_current_web_view'):
                    web_view = eb.get_current_web_view()
            except Exception:
                web_view = None

            source_data = {
                'country': (getattr(getattr(purchase, 'import_country', None),
                                    'name', '') or ''),
                'continent': getattr(purchase, 'continent', None) or '',
                'denomination': getattr(purchase, 'denomination_value', None) or '',
                'currency': getattr(purchase, 'currency', None) or '',
                'year': getattr(purchase, 'year', None) or '',
                'description': getattr(purchase, 'comments', None) or '',
                'price': (getattr(purchase, 'collection_price', None)
                          or getattr(purchase, 'sold_sum', None)
                          or getattr(purchase, 'total', None) or 0),
                'purchase_id': getattr(purchase, 'id', None),
            }
            from gui.widgets.coin_scanner.scan_list_dialog import ScanAndListDialog
            dlg = ScanAndListDialog(None, self.db_manager, self.window(), self,
                                    source=source_data, web_view=web_view)
            dlg.exec()
        except Exception as e:
            self.logger.error(f"Ошибка scan_and_list_selected: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, 'Ошибка', str(e))