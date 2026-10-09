# -*- coding: utf-8 -*-

"""
Методы MainWindow для работы с монетами:
- Копирование
- Выделение в таблице
- Открытие редактирования
"""

import re
import traceback
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer

from database.models import Coin


class CoinActionsMixin:
    """Примесь с методами копирования и редактирования монет"""

    def _copy_coin_by_id(self, coin_id):
        """Копирует монету по ID с увеличением каталога на max+1 и открывает редактирование"""
        coin = self.db_manager.get_coin(coin_id)
        if not coin:
            return
        
        # === ПОЛНАЯ БЛОКИРОВКА НА ВРЕМЯ КОПИРОВАНИЯ ===
        self._suppress_all_dialogs()
        self.table.blockSignals(True)
        
        try:
            from database.models import Coin
            import re
            
            self.table_panel.save_state()
            
            all_coins = self.db_manager.session.query(Coin.catalog_number).all()
            max_number = 0
            max_catalog = None
            max_digits = 0
            
            for (catalog,) in all_coins:
                if catalog:
                    match = re.search(r'(\d+)', catalog)
                    if match:
                        num_str = match.group(1)
                        num = int(num_str)
                        if num > max_number:
                            max_number = num
                            max_catalog = catalog
                            max_digits = len(num_str)
            
            new_number = max_number + 1
            if max_catalog:
                prefix = re.sub(r'\d+', '', max_catalog)
                new_num_str = str(new_number).zfill(max_digits)
                new_catalog = f"{prefix}{new_num_str}"
            else:
                new_catalog = str(new_number)
            
            possible_attrs = [
                'country_id', 'currency_id', 'mint_id', 'metal_id', 'edge_id', 'period_id',
                'denomination_value', 'currency', 'century', 'year',
                'year_on_coin', 'mint', 'mint_mark', 'fineness', 'weight',
                'diameter', 'thickness', 'shape', 'edge_description', 'condition',
                'rarity', 'storage_location', 'issue_type', 'avrev',
                'purchase_price', 'purchase_commission', 'purchase_place',
                'purchase_where', 'purchase_info', 'purchase_country_id',
                'acquisition_type', 'sale_price', 'sale_date', 'obverse_description',
                'reverse_description', 'obverse_image', 'reverse_image',
                'main_image_path', 'ucoin_url', 'status', 'quantity', 'notes', 'coin_info',
                'custom_data',
                'condition_id', 'rarity_id', 'shape_id', 'issue_type_id', 'avrev_id',
                'status_id', 'acquisition_type_id', 'storage_location_id'
            ]
            
            coin_data = {}
            for attr in possible_attrs:
                if hasattr(coin, attr):
                    value = getattr(coin, attr)
                    if value is not None:
                        coin_data[attr] = value
            
            coin_data['catalog_number'] = new_catalog
            
            # Обновляем дату покупки на текущую
            from datetime import date
            coin_data['purchase_date'] = date.today()
            
            new_id = self.db_manager.add_coin(coin_data)
            
            self.logger.info(f"Монета скопирована, новый ID: {new_id}")
            
            # ВАЖНО: НЕ вызываем show_coin_info(None)
            # Загружаем данные с подавленными диалогами
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
            
            # Разблокируем сигналы таблицы
            self.table.blockSignals(False)
            
            # Сначала восстанавливаем диалоги
            self._restore_dialogs()
            
            # Затем через таймер выбираем и показываем новую монету
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self._select_and_edit_coin(new_id))
            
            self.status_bar.showMessage(
                f"✅ Монета скопирована (ID: {new_id}, каталог: {new_catalog})", 3000
            )
            
        except Exception as e:
            self.table.blockSignals(False)
            self._restore_dialogs()
            self.logger.error(f"Ошибка при копировании монеты: {e}")
            self.logger.error(traceback.format_exc())
            QMessageBox.critical(self, "Ошибка", f"Не удалось копировать монету:\n{e}")

    def _select_and_edit_coin(self, coin_id):
        """Выбирает монету в таблице и открывает на редактирование"""
        try:
            # Выделяем монету в таблице
            found = False
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item_id = item.data(Qt.UserRole)
                        if item_id == coin_id:
                            self.table.selectRow(row)
                            self.table.scrollToItem(item)
                            self.table.setCurrentCell(row, 0)
                            found = True
                            break
                if found:
                    break
            
            if not found:
                self.logger.warning(f"Монета ID {coin_id} не найдена в таблице")
                return
            
            # Получаем свежую монету из БД
            coin = self.db_manager.get_coin(coin_id)
            if not coin:
                return
            
            # Сбрасываем блокировки
            if hasattr(self.detail_panel, '_updating'):
                self.detail_panel._updating = False
            
            # Показываем монету в detail_panel
            self.detail_panel.show_coin_info(coin)
            
            # Принудительно переключаемся на вкладку монеты
            if hasattr(self.detail_panel, 'tab_widget'):
                self.detail_panel.tab_widget.setCurrentIndex(3)  # TAB_COIN
            
        except Exception as e:
            self.logger.error(f"Ошибка при выделении монеты: {e}")
            self.logger.error(traceback.format_exc())

    def _restore_and_edit(self, coin_id):
        """Восстанавливает диалоги и открывает монету на редактирование."""
        self._restore_dialogs()
        self._select_and_edit_coin(coin_id)

    def _restore_and_edit(self, coin_id):
        """Восстанавливает диалоги и открывает монету на редактирование."""
        self._restore_dialogs()
        self._select_and_edit_coin(coin_id)

    def _select_and_edit_coin(self, coin_id):
        """Выбирает монету в таблице и открывает на редактирование"""
        try:
            # Выделяем монету в таблице
            found = False
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item_id = item.data(Qt.UserRole)
                        if item_id == coin_id:
                            self.table.selectRow(row)
                            self.table.scrollToItem(item)
                            self.table.setCurrentCell(row, 0)
                            found = True
                            break
                if found:
                    break
            
            if not found:
                self.logger.warning(f"Монета ID {coin_id} не найдена в таблице")
                return
            
            # Получаем свежую монету из БД
            coin = self.db_manager.get_coin(coin_id)
            if not coin:
                return
            
            # Сбрасываем блокировки
            if hasattr(self.detail_panel, '_updating'):
                self.detail_panel._updating = False
            
            # Показываем монету в detail_panel
            self.detail_panel.show_coin_info(coin)
            
            # Принудительно переключаемся на вкладку монеты
            if hasattr(self.detail_panel, 'tab_widget'):
                self.detail_panel.tab_widget.setCurrentIndex(3)  # TAB_COIN
            
        except Exception as e:
            self.logger.error(f"Ошибка при выделении монеты: {e}")
            self.logger.error(traceback.format_exc())

    def _open_edit_after_copy(self, coin_id):
        """Открывает режим редактирования после копирования"""
        try:
            coin = self.db_manager.get_coin(coin_id)
            if not coin:
                return
            
            if hasattr(self.detail_panel, 'coin_tab'):
                coin_tab = self.detail_panel.coin_tab
                
                # Устанавливаем монету
                coin_tab.current_coin = coin
                
                # Переключаем в режим редактирования
                coin_tab.switch_to_edit_mode()
                
            self.logger.info(f"Режим редактирования открыт для монеты ID {coin_id}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при открытии редактирования после копирования: {e}")
            self.logger.error(traceback.format_exc())
 
    def _open_edit_after_copy(self, coin_id):
        """Открывает режим редактирования после копирования"""
        try:
            coin = self.db_manager.get_coin(coin_id)
            if not coin:
                return
            
            if hasattr(self.detail_panel, 'coin_tab'):
                coin_tab = self.detail_panel.coin_tab
                
                # Устанавливаем монету
                coin_tab.current_coin = coin
                
                # Переключаем в режим редактирования через стандартный метод
                # НЕ вызываем field.show() вручную — это создаёт окна-сироты
                coin_tab.switch_to_edit_mode()
                
            self.logger.info(f"Режим редактирования открыт для монеты ID {coin_id}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при открытии редактирования после копирования: {e}")
            self.logger.error(traceback.format_exc())
   
    def _log_and_clear_flag(self, coin_id):
        """Логирует и снимает флаг подавления сообщений"""
        self.logger.info(f"Снятие флага _suppress_messages для coin_id={coin_id}")
        # Задержка 2 секунды вместо 500 мс
        self._suppress_messages = False

    def _edit_coin_by_id(self, coin_id):
        """Редактирует монету по ID"""
        from gui.add_coin_dialog import AddCoinDialog
        dialog = AddCoinDialog(self.db_manager, self, coin_id)
        if dialog.exec():
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
            self.status_bar.showMessage("✅ Монета обновлена", 3000)
    
    def _delete_coin_by_id(self, coin_id):
        """Удаляет монету по ID"""
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Удалить монету ID {coin_id}?", 
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.table_panel.save_state()
            self.db_manager.delete_coin(coin_id)
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
            QTimer.singleShot(2000, self.table_panel.restore_state)
            self.status_bar.showMessage("✅ Монета удалена", 3000)
    
    def _set_coin_status(self, coin_id, status):
        """Устанавливает статус монеты"""
        status_names = {
            'in_collection': 'В коллекции',
            'want': 'Хочу',
            'sold': 'Продано',
            'lost': 'Утеряно'
        }
        self.db_manager.update_coin(coin_id, {'status': status})
        self.load_coins()
        self.status_bar.showMessage(
            f"✅ Статус изменён на '{status_names.get(status, status)}'", 2000
        )
    
    def select_coin_by_id(self, coin_id):
        """Выбирает монету с указанным ID в таблице"""
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            if id_item:
                item_id = id_item.data(Qt.UserRole)
                if item_id == coin_id:
                    self.table.selectRow(row)
                    self.table.scrollToItem(id_item)
                    self.table.setCurrentCell(row, 0)
                    
                    if hasattr(self, 'detail_panel'):
                        coin = self.db_manager.get_coin(coin_id)
                        if coin:
                            self.detail_panel.show_coin_info(coin)
                    break
                    
    def _print_holder_labels(self):
        """Печатает этикетки холдеров для выбранных монет"""
        if hasattr(self, 'table_panel') and hasattr(self.table_panel, '_print_holder_labels'):
            self.table_panel._print_holder_labels()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Ошибка", "Функция печати временно недоступна")
            
    def _delete_ids(self, ids):
        """Внутренний метод: удаляет список ID монет с подтверждением
        и БЕЗОПАСНЫМ обновлением интерфейса (сигналы таблицы заблокированы,
        флаг _loading_coins установлен — рекурсия on_coin_selected исключена)."""
        ids = list(dict.fromkeys(ids))
        if not ids:
            QMessageBox.warning(
                self, "Предупреждение",
                "Не выделено ни одной монеты для удаления.\n\n"
                "Отметьте строки галочками ☑ или выделите их в таблице "
                "(Ctrl/Shift+клик).")
            return 0
        if getattr(self, '_delete_in_progress', False):
            self.logger.warning("⚠️ Удаление уже выполняется — повторный вызов игнорирую")
            return 0
        count = len(ids)
        if count == 1:
            msg = f"Удалить монету ID {ids[0]}?\n\nДействие нельзя отменить."
        else:
            preview = ', '.join(str(i) for i in ids[:15])
            if count > 15:
                preview += ', …'
            msg = (f"Удалить выделенные монеты: {count} шт.?\n\n"
                   f"ID: {preview}\n\nДействие нельзя отменить.")
        reply = QMessageBox.question(
            self, "Подтверждение удаления", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return 0
        self._delete_in_progress = True
        deleted = 0
        errors = []
        try:
            # === Сохраняем состояние таблицы (скролл/выделение) ===
            try:
                self.table_panel.save_state()
            except Exception:
                pass
            # === Удаляем записи из БД ===
            for cid in ids:
                try:
                    self.db_manager.delete_coin(cid)
                    deleted += 1
                except Exception as e:
                    errors.append(f"ID {cid}: {e}")
                    self.logger.error(f"🗑 Ошибка удаления ID {cid}: {e}")
                    try:
                        self.db_manager.session.rollback()
                    except Exception:
                        pass
            try:
                self.db_manager.session.commit()
            except Exception:
                pass
            # === БЕЗОПАСНОЕ ОБНОВЛЕНИЕ ИНТЕРФЕЙСА ===
            # Блокируем сигналы таблицы и ставим флаг загрузки, чтобы
            # смена выделения НЕ запускала on_coin_selected → show_coin_info → …
            current_id = None
            try:
                cur = getattr(getattr(self, 'detail_panel', None), 'current_coin', None)
                current_id = getattr(cur, 'id', None)
            except Exception:
                current_id = None
            self._loading_coins = True
            try:
                self.table_panel.table.blockSignals(True)
                try:
                    self.load_coins()
                except Exception as e:
                    self.logger.error(f"Ошибка load_coins после удаления: {e}")
                try:
                    self.load_country_tree(preserve_expanded=True)
                except Exception as e:
                    self.logger.error(f"Ошибка load_country_tree после удаления: {e}")
            finally:
                self.table_panel.table.blockSignals(False)
                self._loading_coins = False
            # === Если удалённая монета была открыта в правой панели — гасим её
            # (один вызов, сигналы таблицы заблокированы → без рекурсии) ===
            if current_id in ids:
                self.table_panel.table.blockSignals(True)
                try:
                    if hasattr(self, 'detail_panel') and hasattr(
                            self.detail_panel, 'show_coin_info'):
                        self.detail_panel.show_coin_info(None)
                except Exception as e:
                    self.logger.debug(f"Ошибка сброса правой панели: {e}")
                finally:
                    self.table_panel.table.blockSignals(False)
            # === Восстанавливаем состояние таблицы (скролл) ===
            QTimer.singleShot(200, self.table_panel.restore_state)
            # === Статус ===
            if count == 1 and deleted == 1:
                self.status_bar.showMessage("✅ Монета удалена", 3000)
            else:
                msg = f"✅ Удалено монет: {deleted}"
                if errors:
                    msg += f" | ⚠️ ошибок: {len(errors)}"
                self.status_bar.showMessage(msg, 5000)
            self.logger.info(f"🗑 Удаление завершено: {deleted} из {count}")
            return deleted
        except Exception as e:
            self.logger.error(f"Ошибка в _delete_ids: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить монеты:\n{e}")
            return deleted
        finally:
            self._delete_in_progress = False

    def _delete_coin_by_id(self, coin_id):
        """Удаляет монету по ID (одиночное удаление — контекстные меню,
        совместимость со старыми вызовами). Делегирует в _delete_ids."""
        return self._delete_ids([coin_id])

    def delete_selected_coins(self):
        """Массовое удаление выделенных монет (кнопка «🗑 Удалить» тулбара).
        Приоритет источников выделения:
        1) строки с галочками ☑ (checkbox-колонка);
        2) выделенные строки таблицы (Ctrl/Shift+клик);
        3) текущая монета в правой панели (если ничего не выделено)."""
        ids = []
        # === 1) Строки с галочками ===
        try:
            if hasattr(self, 'table_panel') and hasattr(
                    self.table_panel, 'get_selected_coin_ids'):
                ids = list(self.table_panel.get_selected_coin_ids() or [])
        except Exception as e:
            self.logger.debug(f"get_selected_coin_ids: {e}")
        # === 2) Выделенные строки таблицы ===
        if not ids:
            try:
                table = self.table_panel.table
                rows = sorted({idx.row() for idx in table.selectedIndexes()})
                coins_list = None
                for attr in ('_filtered_coins', 'filtered_coins',
                             'coins', 'current_coins'):
                    lst = getattr(self.table_panel, attr, None)
                    if lst:
                        coins_list = lst
                        break
                if coins_list:
                    for row in rows:
                        if 0 <= row < len(coins_list):
                            cid = getattr(coins_list[row], 'id', None)
                            if cid:
                                ids.append(cid)
                else:
                    from PySide6.QtCore import Qt as QtCore_Qt
                    model = table.model()
                    for row in rows:
                        cid = model.index(row, 0).data(QtCore_Qt.UserRole)
                        if cid:
                            ids.append(cid)
            except Exception as e:
                self.logger.debug(f"Сбор выделенных строк: {e}")
        # === 3) Текущая монета (если ничего не выделено) ===
        if not ids:
            coin = getattr(getattr(self, 'detail_panel', None), 'current_coin', None)
            if coin is not None and getattr(coin, 'id', None):
                ids = [coin.id]
        return self._delete_ids(ids)