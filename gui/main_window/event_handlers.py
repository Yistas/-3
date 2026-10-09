# -*- coding: utf-8 -*-

"""
Обработчики событий MainWindow
"""

import time
import traceback
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer


class EventHandlersMixin:
    """Примесь с обработчиками событий"""
    
    def showEvent(self, event):
        """Обработчик события показа окна"""
        self.logger.info("showEvent: начало")
        try:
            super().showEvent(event)
            self.logger.info("showEvent: завершен успешно")
        except Exception as e:
            self.logger.critical(f"showEvent: ошибка - {e}", exc_info=True)
            raise
    
    def on_coin_selected(self, current, previous):
        """Обработчик выбора монеты в таблице"""
        if current is None:
            self.detail_panel.show_coin_info(None)
            return
        
        try:
            coin_id = current.data(Qt.UserRole)
            if coin_id:
                coin = self.db_manager.get_coin(coin_id)
                
                if hasattr(self.detail_panel, '_updating'):
                    self.detail_panel._updating = False
                
                if hasattr(self.detail_panel, 'coin_tab'):
                    if self.detail_panel.coin_tab.edit_mode:
                        self.detail_panel.coin_tab.switch_to_view_mode()
                
                if hasattr(self, 'country_tree') and self.country_tree:
                    self.country_tree.blockSignals(True)
                
                self.detail_panel.show_coin_info(coin)
                
                if hasattr(self, 'country_tree') and self.country_tree:
                    self.country_tree.blockSignals(False)
                
                self.logger.info(f"Выбрана монета ID: {coin_id}")
            else:
                self.detail_panel.show_coin_info(None)
                
        except Exception as e:
            self.logger.error(f"Ошибка при выборе монеты: {e}")
            self.detail_panel.show_coin_info(None)
    
    def on_tab_changed(self, index):
        """Обработчик смены вкладки"""
        if not hasattr(self, 'center_tab_widget') or self.center_tab_widget is None:
            return
        
        tab_text = self.center_tab_widget.tabText(index)
        
        if "Погодовка" in tab_text and hasattr(self, 'yearly_table_tab'):
            self.yearly_table_tab.refresh_current()
        
        if "Стоимость коллекции" in tab_text and hasattr(self, 'detail_panel'):
            current_item = self.country_tree.currentItem()
            if current_item:
                self.update_collection_value_for_selected_item(current_item)
            else:
                self.detail_panel.show_collection_value()
    
    def on_collection_value_updated(self):
        """Обработчик обновления стоимости коллекции"""
        if hasattr(self, 'detail_panel'):
            self.detail_panel.show_collection_value()
    
    def update_collection_value_for_selected_item(self, item):
        """Обновляет стоимость коллекции для выбранного элемента"""
        if hasattr(self, 'detail_panel'):
            self.detail_panel.show_collection_value()
    
    # ========== ОБРАБОТЧИКИ ОБНОВЛЕНИЙ ==========
    
    def on_references_changed(self, ref_name):
        """Обработчик изменения справочника"""
        self.logger.info(f"Справочник '{ref_name}' изменён, обновляем интерфейс")
        
        self.load_coins()
        
        if hasattr(self, 'detail_panel'):
            if hasattr(self.detail_panel, 'coin_tab'):
                if self.detail_panel.coin_tab.current_coin:
                    fresh_coin = self.db_manager.get_coin(self.detail_panel.coin_tab.current_coin.id)
                    self.detail_panel.coin_tab.show_coin_info(fresh_coin)
        
        if hasattr(self, 'statistics_tab'):
            self.statistics_tab.load_data()
        
        if hasattr(self, 'yearly_table_tab'):
            self.yearly_table_tab.refresh_current()
        
        self.status_bar.showMessage(f"✅ Справочник '{ref_name}' обновлён", 3000)
    
    def on_fields_changed(self):
        """Обработчик изменения полей"""
        self.logger.info("Настройки полей изменены, обновляем таблицу")
        
        if hasattr(self, 'table_panel'):
            self.table_panel.refresh_columns()
        
        self.load_coins()
        self.status_bar.showMessage("✅ Настройки полей обновлены", 3000)
    
    def on_data_changed(self):
        """Обработчик общих изменений данных"""
        self.logger.info("Данные изменены, обновляем интерфейс")
        self.load_coins()
    
    # ========== ОБРАБОТЧИК СМЕНЫ ВКЛАДКИ В ЦЕНТРАЛЬНОЙ ОБЛАСТИ ==========
    
# ===== gui/main_window/event_handlers.py =====
# МЕТОД: on_center_tab_changed (ПОЛНОСТЬЮ)

    def on_center_tab_changed(self, index):
        """
        Обработчик смены вкладки в центральной области.
        Скрывает левую и правую панели при переключении на вкладку "Обмен/Продажа",
        и ВОССТАНАВЛИВАЕТ их при переключении на другие вкладки.
        """
        # Проверяем, существует ли атрибут center_tab_widget
        if not hasattr(self, 'center_tab_widget') or self.center_tab_widget is None:
            self.logger.warning("center_tab_widget не найден")
            return
        
        if index < 0:
            return
        
        # Получаем название текущей вкладки
        tab_text = self.center_tab_widget.tabText(index)
        self.logger.info(f"🔍 Переключение на вкладку: '{tab_text}' (индекс {index})")
        
        # Проверяем, активна ли вкладка "Обмен/Продажа"
        is_exchange_tab = "Обмен/Продажа" in tab_text or "💱 Обмен/Продажа" in tab_text
        self.logger.info(f"  is_exchange_tab: {is_exchange_tab}")
        
        if is_exchange_tab:
            self.logger.info("🔒 Скрываем панели для вкладки Обмен/Продажа")
            
            # Скрываем левую панель (дерево стран)
            if hasattr(self, 'left_panel'):
                if self.left_panel.isVisible():
                    self.left_panel.hide()
                    self._left_panel_was_visible = True
                    self.logger.info("  ✅ Левая панель скрыта")
                else:
                    self._left_panel_was_visible = False
                    self.logger.info("  ⏭️ Левая панель уже скрыта")
            else:
                self.logger.warning("  ❌ left_panel не найден")
            
            # Скрываем правую панель (детали)
            if hasattr(self, 'right_panel'):
                if self.right_panel.isVisible():
                    self.right_panel.hide()
                    self._right_panel_was_visible = True
                    self.logger.info("  ✅ Правая панель скрыта")
                else:
                    self._right_panel_was_visible = False
                    self.logger.info("  ⏭️ Правая панель уже скрыта")
            else:
                self.logger.warning("  ❌ right_panel не найден")
            
            # Обновляем состояние кнопки переключения правой панели
            if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'update_toggle_panel_action'):
                self.table_panel.update_toggle_panel_action(False)
            
        else:
            self.logger.info(f"🔓 Восстанавливаем панели для вкладки: {tab_text}")
            
            # Возвращаем панели обратно, если они были скрыты
            if hasattr(self, '_left_panel_was_visible') and self._left_panel_was_visible:
                if hasattr(self, 'left_panel'):
                    self.left_panel.show()
                    self._left_panel_was_visible = False
                    self.logger.info("  ✅ Левая панель показана")
            
            if hasattr(self, '_right_panel_was_visible') and self._right_panel_was_visible:
                if hasattr(self, 'right_panel'):
                    self.right_panel.show()
                    self._right_panel_was_visible = False
                    self.logger.info("  ✅ Правая панель показана")
                    if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'update_toggle_panel_action'):
                        self.table_panel.update_toggle_panel_action(True)

    def closeEvent(self, event):
        """Обработчик закрытия главного окна"""
        self.logger.info("closeEvent: начало")
        try:
            self.logger.info("Закрытие программы, сохранение настроек...")
            
            if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'save_selected_state'):
                self.table_panel.save_selected_state()
            
            if hasattr(self, 'main_splitter'):
                sizes = self.main_splitter.sizes()
                self.left_panel_size = sizes[0]
                self.center_panel_size = sizes[1]
                self.right_panel_size = sizes[2]
            
            if hasattr(self, 'country_tree') and self.country_tree:
                self.logger.info("Сохранение структуры дерева перед закрытием...")
                self.settings_manager.save_tree_structure(self.country_tree)
                time.sleep(0.3)
            
            self.save_settings()
            
            threads_running = False
            if hasattr(self, 'collection_value_tab'):
                if hasattr(self.collection_value_tab, 'loading_thread') and self.collection_value_tab.loading_thread:
                    if self.collection_value_tab.loading_thread.isRunning():
                        threads_running = True
                        self.collection_value_tab.loading_thread.stop()
            
            if threads_running:
                QTimer.singleShot(3000, self.force_close)
                event.ignore()
                self._close_event = event
            else:
                event.accept()
                
            self.logger.info("closeEvent: завершен")
        except Exception as e:
            self.logger.error(f"Ошибка в closeEvent: {e}", exc_info=True)
            event.accept()
    
    def force_close(self):
        """Принудительное закрытие программы"""
        self.logger.warning("Принудительное закрытие программы")
        if hasattr(self, '_close_event'):
            self._close_event.accept()
        QApplication.quit()