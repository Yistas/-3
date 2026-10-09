# -*- coding: utf-8 -*-

"""
Главное окно приложения Coin Collector
"""

import logging
import sys
import os
import json
import traceback
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt, QTimer

from gui.main_window.managers import ManagersMixin
from gui.main_window.ui_setup import UiSetupMixin
from gui.main_window.settings import SettingsMixin
from gui.main_window.coins import CoinsMixin
from gui.main_window.coin_actions import CoinActionsMixin
from gui.main_window.value_helpers import ValueHelpersMixin
from gui.main_window.tree_handlers import TreeHandlersMixin
from gui.main_window.panel_handlers import PanelHandlersMixin
from gui.main_window.menu_handlers import MenuHandlersMixin
from gui.main_window.event_handlers import EventHandlersMixin
from gui.main_window.cloud_handlers import CloudHandlersMixin


class MainWindow(QMainWindow,
                 ManagersMixin,
                 UiSetupMixin,
                 SettingsMixin,
                 CoinsMixin,
                 CoinActionsMixin,
                 ValueHelpersMixin,
                 TreeHandlersMixin,
                 PanelHandlersMixin,
                 MenuHandlersMixin,
                 EventHandlersMixin,
                 CloudHandlersMixin):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('CoinCollector.GUI.MainWindow')
        self.logger.info("="*50)
        self.logger.info("ИНИЦИАЛИЗАЦИЯ ГЛАВНОГО ОКНА")
        self.logger.info("="*50)
        
        # Переменные состояния
        self.right_panel_visible = True
        self.left_panel_size = 280
        self.center_panel_size = 700
        self.right_panel_size = 450
        self.saved_theme = 'Светлая'
        self.current_filter_country_id = None
        self.current_folder_country_ids = None
        self.current_coins = []
        self._close_event = None
        self._updating_splitter = False
        self._skip_auto_select = False
        self._loading_coins = False
        
        # Переменные для управления панелями
        self._left_panel_was_visible = False
        self._right_panel_was_visible = False
        self._panels_state_saved = False
        self._saved_left_panel_visible = True
        self._saved_right_panel_visible = True
        
        # Инициализация менеджеров (ДО init_ui)
        self._init_managers()
        
        # Загрузка настроек (ДО init_ui)
        self.load_settings()
        
        # Создание интерфейса (ПОСЛЕ менеджеров)
        self.init_ui()
        
        # Загрузка данных
        self.load_country_tree()
        if hasattr(self, 'table_panel'):
            self.table_panel.initialize_table_columns()
        self.load_coins()
        
        # Применяем настройки панели
        self.apply_panel_settings()
        
        self.logger.info("✅ Главное окно успешно инициализировано")
        
    def force_close(self):
        """Принудительное закрытие программы"""
        self.logger.warning("Принудительное закрытие программы")
        if hasattr(self, '_close_event'):
            self._close_event.accept()
        QApplication.quit()

    def _suppress_all_dialogs(self):
        """Временно подавляет все диалоговые окна, авто-выбор коллекции и WebEngine."""
        self.logger.info("DEBUG: Полное подавление всех окон и WebEngine...")
        from PySide6.QtWidgets import QProgressDialog, QDialog, QMessageBox
        
        self._original_dialog_exec = QDialog.exec_
        self._original_dialog_show = QDialog.show
        self._original_progress_exec = QProgressDialog.exec_
        self._original_progress_show = QProgressDialog.show
        self._original_warning = QMessageBox.warning
        self._original_info = QMessageBox.information
        self._original_critical = QMessageBox.critical

        QDialog.exec_ = lambda *args, **kwargs: None
        QProgressDialog.exec_ = lambda *args, **kwargs: None
        QDialog.show = lambda *args, **kwargs: None
        QProgressDialog.show = lambda *args, **kwargs: None
        QMessageBox.warning = lambda *args, **kwargs: None
        QMessageBox.information = lambda *args, **kwargs: None
        QMessageBox.critical = lambda *args, **kwargs: None
        
        self._skip_auto_select = True
        
        # === ИСПРАВЛЕНИЕ: Проверяем, не отключен ли уже браузер ===
        if hasattr(self, 'browser_tab') and not hasattr(self, '_saved_browser'):
            try:
                self._saved_browser = self.browser_tab
                for i in range(self.center_tab_widget.count()):
                    if self.center_tab_widget.widget(i) == self.browser_tab:
                        from PySide6.QtWidgets import QLabel
                        stub = QLabel("Загрузка...")
                        stub.setAlignment(Qt.AlignCenter)
                        self.center_tab_widget.removeTab(i)
                        self.center_tab_widget.insertTab(i, stub, "🌐 Браузер")
                        break
            except Exception as e:
                self.logger.debug(f"Ошибка отключения браузера: {e}")
        
        self._dialogs_suppressed = True

    def _restore_dialogs(self):
        """Восстанавливает стандартное поведение диалогов и WebEngine."""
        if not hasattr(self, '_dialogs_suppressed') or not self._dialogs_suppressed:
            return
        
        self.logger.info("DEBUG: Восстановление диалогов и WebEngine...")
        from PySide6.QtWidgets import QProgressDialog, QDialog, QMessageBox
        
        QDialog.exec_ = self._original_dialog_exec
        QDialog.show = self._original_dialog_show
        QProgressDialog.exec_ = self._original_progress_exec
        QProgressDialog.show = self._original_progress_show
        QMessageBox.warning = self._original_warning
        QMessageBox.information = self._original_info
        QMessageBox.critical = self._original_critical
        
        self._skip_auto_select = False
        
        # === ИСПРАВЛЕНИЕ: Восстанавливаем браузер, только если он был сохранён ===
        if hasattr(self, '_saved_browser') and self._saved_browser:
            try:
                for i in range(self.center_tab_widget.count()):
                    if self.center_tab_widget.tabText(i) == "🌐 Браузер":
                        self.center_tab_widget.removeTab(i)
                        self.center_tab_widget.insertTab(i, self._saved_browser, "🌐 Браузер")
                        break
                # Обновляем ссылку на браузер
                self.browser_tab = self._saved_browser
                del self._saved_browser
                self.logger.info("✅ Браузер восстановлен")
            except Exception as e:
                self.logger.debug(f"Ошибка восстановления браузера: {e}")
                # Если восстановление не удалось, пытаемся создать браузер заново
                try:
                    from gui.widgets.embedded_browser import EmbeddedBrowser
                    self.browser_tab = EmbeddedBrowser(self)
                    for i in range(self.center_tab_widget.count()):
                        if self.center_tab_widget.tabText(i) == "🌐 Браузер":
                            self.center_tab_widget.removeTab(i)
                            self.center_tab_widget.insertTab(i, self.browser_tab, "🌐 Браузер")
                            break
                    self.logger.info("✅ Браузер создан заново")
                except Exception as e2:
                    self.logger.error(f"Ошибка создания браузера: {e2}")
        
        self._dialogs_suppressed = False    
    
    def show_cloud_storage_settings(self):
        """Показывает настройки облачного хранилища"""
        from gui.dialogs.cloud_storage_dialog import CloudStorageDialog
        dialog = CloudStorageDialog(self)
        dialog.exec()
        
    def show_cloud_storage_settings(self):
        """Открывает диалог настроек облачного хранилища"""
        try:
            from gui.dialogs.cloud_storage_dialog import CloudStorageDialog
            dialog = CloudStorageDialog(self)
            dialog.exec()
        except ImportError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "Модуль не найден",
                f"Не удалось загрузить диалог облачного хранилища:\n{e}\n\n"
                f"Убедитесь, что файл gui/dialogs/cloud_storage_dialog.py существует"
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Ошибка открытия диалога:\n{e}")
            
    def save_all_changes(self):
        """Сохраняет все несохранённые изменения в базу данных (обёртка)"""
        # Проверяем, есть ли метод в миксине
        if hasattr(self, '_save_all_changes_impl'):
            self._save_all_changes_impl()
        else:
            # Вызываем метод из MenuHandlersMixin
            # (он должен быть доступен через наследование)
            try:
                # Пытаемся вызвать родительский метод
                super().save_all_changes()
            except AttributeError:
                # Если метода нет, используем собственную реализацию
                self._save_all_changes_fallback()
    
    def _save_all_changes_fallback(self):
        """Запасная реализация сохранения всех изменений"""
        from PySide6.QtWidgets import QMessageBox, QApplication
        from PySide6.QtCore import Qt
        from sqlalchemy import text
        
        self.logger.info("💾 Сохранение всех изменений (fallback)...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            saved = 0
            
            # Сохраняем закупки
            if hasattr(self, 'exchange_tab'):
                if hasattr(self.exchange_tab, '_flush_changes'):
                    self.exchange_tab._flush_changes()
                    saved += 1
                    self.logger.info("  ✅ Сохранены закупки")
            
            # Сохраняем сделки
            if hasattr(self, 'deals_tab'):
                if hasattr(self.deals_tab, '_flush_changes'):
                    self.deals_tab._flush_changes()
                    saved += 1
                    self.logger.info("  ✅ Сохранены сделки")
            
            # Сохраняем продажи
            if hasattr(self, 'sales_tab'):
                if hasattr(self.sales_tab, '_flush_changes'):
                    self.sales_tab._flush_changes()
                    saved += 1
                    self.logger.info("  ✅ Сохранены продажи")
            
            # Сохраняем монету в режиме редактирования
            if hasattr(self, 'detail_panel'):
                coin_tab = self.detail_panel.coin_tab
                if coin_tab and coin_tab.edit_mode:
                    old_suppress = getattr(self, '_suppress_messages', False)
                    self._suppress_messages = True
                    coin_tab.save_changes()
                    self._suppress_messages = old_suppress
                    saved += 1
                    self.logger.info("  ✅ Сохранена монета")
            
            # Сохраняем погодовку
            if hasattr(self, 'yearly_table_tab'):
                if self.yearly_table_tab.is_modified:
                    self.yearly_table_tab.save_current_table()
                    saved += 1
                    self.logger.info("  ✅ Сохранена погодовка")
            
            # Commit в БД
            self.db_manager.session.commit()
            self.logger.info("  ✅ Commit выполнен")
            
            # WAL checkpoint
            with self.db_manager.engine.connect() as conn:
                conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
                conn.commit()
                self.logger.info("  ✅ WAL синхронизирован")
            
            QMessageBox.information(
                self,
                "Сохранение завершено",
                f"✅ Все изменения сохранены.\n"
                f"Сохранено компонентов: {saved}\n"
                f"WAL-журнал синхронизирован."
            )
            self.status_bar.showMessage("✅ Все изменения сохранены", 3000)
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()
            
    def reload_database(self):
        """Перечитывает базу данных из файла без перезапуска программы"""
        from PySide6.QtWidgets import QMessageBox, QApplication
        from PySide6.QtCore import Qt
        
        self.logger.info("=" * 60)
        self.logger.info("🔄 ПЕРЕЧИТЫВАНИЕ БАЗЫ ДАННЫХ")
        self.logger.info("=" * 60)
        
        # Подтверждение
        reply = QMessageBox.question(
            self,
            "Перечитать БД",
            "Перечитать базу данных из файла?\n\n"
            "Все несохранённые изменения будут потеряны!\n\n"
            "Рекомендуется сначала сохранить изменения (Ctrl+S).",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # 1. Сохраняем текущее состояние таблицы и дерева
            if hasattr(self, 'table_panel'):
                self.table_panel.save_state()
            if hasattr(self, 'country_tree'):
                self.country_tree.save_expanded_state()
            
            # 2. ОЧИЩАЕМ КЭШ МОНЕТ В ГЛАВНОМ ОКНЕ
            if hasattr(self, 'current_coins'):
                self.current_coins = []
            
            # 3. Закрываем старую сессию
            if hasattr(self, 'db_manager'):
                try:
                    # Откатываем любые незавершённые транзакции
                    self.db_manager.session.rollback()
                    self.db_manager.session.close()
                    self.db_manager.engine.dispose()
                except Exception as e:
                    self.logger.warning(f"Ошибка при закрытии сессии: {e}")
            
            # 4. Пересоздаём менеджер БД
            from database.db_manager import DatabaseManager
            db_path = self.db_manager.db_path if hasattr(self.db_manager, 'db_path') else "data/coins.db"
            self.db_manager = DatabaseManager(db_path)
            
            # 5. Обновляем ссылки в панелях
            if hasattr(self, 'detail_panel'):
                self.detail_panel.db_manager = self.db_manager
                if hasattr(self.detail_panel, 'coin_tab'):
                    self.detail_panel.coin_tab.db_manager = self.db_manager
                    if hasattr(self.detail_panel.coin_tab, 'load_all_combos'):
                        self.detail_panel.coin_tab.load_all_combos()
                if hasattr(self.detail_panel, 'country_tab'):
                    self.detail_panel.country_tab.db_manager = self.db_manager
                if hasattr(self.detail_panel, 'continent_tab'):
                    self.detail_panel.continent_tab.db_manager = self.db_manager
                if hasattr(self.detail_panel, 'dashboard_tab'):
                    self.detail_panel.dashboard_tab.db_manager = self.db_manager
            
            # 6. Обновляем вкладки
            if hasattr(self, 'statistics_tab'):
                self.statistics_tab.db_manager = self.db_manager
            if hasattr(self, 'yearly_table_tab'):
                self.yearly_table_tab.db_manager = self.db_manager
            if hasattr(self, 'collection_value_tab'):
                self.collection_value_tab.db_manager = self.db_manager
            if hasattr(self, 'market_value_tab'):
                self.market_value_tab.db_manager = self.db_manager
            if hasattr(self, 'exchange_tab'):
                self.exchange_tab.db_manager = self.db_manager
                if hasattr(self.exchange_tab, 'load_data'):
                    self.exchange_tab.load_data()
            if hasattr(self, 'deals_tab'):
                self.deals_tab.db_manager = self.db_manager
                if hasattr(self.deals_tab, 'load_data'):
                    self.deals_tab.load_data()
            if hasattr(self, 'sales_tab'):
                self.sales_tab.db_manager = self.db_manager
                if hasattr(self.sales_tab, 'load_data'):
                    self.sales_tab.load_data()
            if hasattr(self, 'notebook_tab'):
                self.notebook_tab.db_manager = self.db_manager
                if hasattr(self.notebook_tab, 'load_notes'):
                    self.notebook_tab.load_notes()
            
            # 7. Обновляем table_panel (сбрасываем кэш)
            if hasattr(self, 'table_panel'):
                self.table_panel._all_coins = []
                self.table_panel._filtered_coins = []
                self.table_panel.current_columns = None
                self.table_panel.initialize_table_columns()
            
            # 8. Перезагружаем дерево стран
            self.load_country_tree(preserve_expanded=True)
            
            # 9. Перезагружаем монеты (сбрасываем current_coins)
            self.load_coins()
            
            # 10. Восстанавливаем состояние
            if hasattr(self, 'table_panel'):
                QTimer.singleShot(100, self.table_panel.restore_state)
            if hasattr(self, 'country_tree'):
                QTimer.singleShot(200, self.country_tree.restore_expanded_state)
            
            # 11. Обновляем статус-бар
            self.status_bar.showMessage("✅ База данных перечитана", 5000)
            self.logger.info("✅ База данных успешно перечитана")
            
            # 12. Обновляем вкладку статистики (если открыта)
            if hasattr(self, 'statistics_tab') and hasattr(self.statistics_tab, 'load_data'):
                self.statistics_tab.load_data()
            
            QMessageBox.information(
                self,
                "Готово",
                "✅ База данных успешно перечитана!\n\n"
                "Все данные обновлены из файла."
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка при перечитывании БД: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось перечитать базу данных:\n{e}"
            )
        finally:
            QApplication.restoreOverrideCursor()
            
    def _add_coin_from_ucoin(self, url):
        """Создаёт копию монеты-донора и запускает парсинг из UCOIN."""
        try:
            from database.models import Coin
            from sqlalchemy import func
            self.logger.info(f"➕ Добавление монеты из UCOIN: {url}")
            
            source_id = None
            if hasattr(self, 'detail_panel') and getattr(self.detail_panel, 'current_coin', None):
                try:
                    source_id = self.detail_panel.current_coin.id
                    self.logger.info(f"🎯 Донор: выделенная курсором монета ID {source_id}")
                except Exception:
                    source_id = None
            if not source_id and hasattr(self, 'table_panel'):
                try:
                    ids = self.table_panel.get_selected_coin_ids()
                    if ids:
                        source_id = ids[0]
                        self.logger.info(f"🎯 Донор: монета с галочкой ID {source_id}")
                except Exception:
                    pass
            if not source_id:
                source_id = getattr(self, '_mass_donor_id', None)
            if not source_id:
                source_id = self.db_manager.session.query(func.max(Coin.id)).scalar()
            if not source_id:
                self.logger.error("Нет монеты-донора")
                return
                
            donor = self.db_manager.get_coin(source_id)
            if not donor:
                self.logger.error(f"Донор ID {source_id} не найден")
                return
                
            self.logger.info(f"📋 Копирование монеты ID: {donor.id}")
            coin_data = {}
            for attr in ['country_id', 'currency_id', 'mint_id', 'metal_id', 'edge_id',
                         'period_id', 'denomination_value', 'currency', 'century', 'year',
                         'weight', 'diameter', 'thickness', 'mintage', 'condition',
                         'rarity', 'status', 'quantity', 'purchase_price',
                         'purchase_place', 'acquisition_type', 'description',
                         'catalog_number', 'shape', 'issue_type', 'avrev',
                         'condition_id', 'rarity_id', 'status_id', 'shape_id',
                         'issue_type_id', 'avrev_id', 'acquisition_type_id',
                         'storage_location_id']:
                try:
                    if hasattr(donor, attr):
                        value = getattr(donor, attr)
                        if value is not None:
                            coin_data[attr] = value
                except Exception:
                    continue
                    
            from datetime import date
            coin_data['purchase_date'] = date.today()
            coin_data['ucoin_url'] = url
            
            # === ГЛАВНОЕ ИСПРАВЛЕНИЕ: СОЗДАЁМ КОПИЮ В БД И ПОЛУЧАЕМ ЕЁ ID ===
            new_id = self.db_manager.add_coin(coin_data)
            if not new_id:
                self.logger.error("❌ Не удалось создать копию монеты в БД")
                return
            self.logger.info(f"🆕 Создана копия монеты: ID {new_id}")

            # === РЕЖИМ ДОБАВЛЕНИЯ ===
            coin_tab = getattr(getattr(self, 'detail_panel', None), 'coin_tab', None)
            if coin_tab is not None:
                coin_tab._ucoin_update_mode = False
                coin_tab._ucoin_fill_running = False
                self.logger.info("🆕 Режим ДОБАВЛЕНИЯ: номер будет сгенерирован после парсинга")

            # === ПОКАЗЫВАЕМ МОНЕТУ ===
            try:
                new_coin = self.db_manager.get_coin(new_id)
                if new_coin and hasattr(self, 'detail_panel'):
                    self.detail_panel.show_coin_info(new_coin)
            except Exception as e:
                self.logger.error(f"Ошибка показа монеты: {e}")

            # === ЗАПУСКАЕМ ПАРСИНГ ===
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self._fill_coin_from_ucoin(new_id, url))
        except Exception as e:
            self.logger.error(f"Ошибка добавления монеты: {e}")
            import traceback
            traceback.print_exc()

    def _start_ucoin_parsing(self, coin_id, url):
        """Запускает парсинг страницы UCOIN для указанной монеты"""
        self.logger.info(f"🔍 Запуск парсинга UCOIN для монеты ID {coin_id}")
        
        # Открываем страницу в браузере
        if hasattr(self, 'browser_tab') and hasattr(self.browser_tab, 'embedded_browser'):
            browser = self.browser_tab.embedded_browser
            browser.load_url(url)
            self.logger.info(f"🌐 Открыта страница: {url}")
        
        # Через 3 секунды после открытия запускаем извлечение данных
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._extract_ucoin_data_for_coin(coin_id))
    
    def _extract_ucoin_data_for_coin(self, coin_id):
        """Извлекает данные со страницы UCOIN и заполняет форму монеты"""
        self.logger.info(f"📥 Извлечение данных UCOIN для монеты ID {coin_id}")
        
        if not hasattr(self, 'detail_panel') or not hasattr(self.detail_panel, 'coin_tab'):
            self.logger.error("coin_tab не найден")
            return
        
        coin_tab = self.detail_panel.coin_tab
        
        # Проверяем, что текущая монета — та, которую мы парсим
        if coin_tab.current_coin and coin_tab.current_coin.id == coin_id:
            # Вызываем метод парсинга
            if hasattr(coin_tab, '_extract_ucoin_data'):
                coin_tab._extract_ucoin_data(self)
                self.logger.info(f"✅ Парсинг запущен для монеты ID {coin_id}")
            else:
                self.logger.error("Метод _extract_ucoin_data не найден в coin_tab")
        else:
            self.logger.warning(f"⚠️ Текущая монета не совпадает с ожидаемой (ID {coin_id})")

    def _fill_coin_from_ucoin(self, coin_id, url):
        """Открывает страницу монеты во вкладке браузера, ПЕРЕКЛЮЧАЕТ ФОКУС
        на вкладку браузера и запускает парсинг по факту загрузки страницы.
        Защищён от дублей: одна монета — один парсинг."""
        try:
            from PySide6.QtCore import QTimer
            self.logger.info(f"🔍 Запуск парсинга UCOIN для монеты ID {coin_id}")
            coin = self.db_manager.get_coin(coin_id)
            if not coin:
                self.logger.error(f"Монета ID {coin_id} не найдена")
                return
            coin_tab = getattr(getattr(self, 'detail_panel', None), 'coin_tab', None)
            if not coin_tab:
                self.logger.error("❌ coin_tab не найден")
                return
            # === ЗАЩИТА ОТ ДУБЛЯ: парсинг этой монеты уже запущен ===
            if getattr(coin_tab, '_ucoin_parsing_id', None) == coin_id:
                self.logger.warning(f"⚠️ Парсинг монеты {coin_id} уже запущен — дубль пропущен")
                return
            coin_tab._ucoin_parsing_id = coin_id
            if hasattr(self, 'detail_panel'):
                self.detail_panel.show_coin_info(coin)
                if hasattr(self.detail_panel, 'tab_widget'):
                    self.detail_panel.tab_widget.setCurrentIndex(3)
            if hasattr(coin_tab, 'switch_to_edit_mode'):
                coin_tab.switch_to_edit_mode()
            coin_tab._ucoin_load_processed = False
            # === ИЩЕМ БРАУЗЕР ===
            browser = getattr(self, 'browser_tab', None)
            if browser is None or not hasattr(browser, 'add_new_tab'):
                from gui.widgets.embedded_browser import EmbeddedBrowser
                browser = self.findChild(EmbeddedBrowser)
            if not browser:
                self.logger.error("❌ Браузер не найден")
                coin_tab._ucoin_load_processed = True
                coin_tab._ucoin_parsing_id = None
                return
            # === ПЕРЕКЛЮЧАЕМ ФОКУС НА ВКЛАДКУ БРАУЗЕРА В ЦЕНТРЕ ===
            if hasattr(self, 'center_tab_widget'):
                for i in range(self.center_tab_widget.count()):
                    if 'Браузер' in self.center_tab_widget.tabText(i):
                        self.center_tab_widget.setCurrentIndex(i)
                        self.logger.info(f"🌐 Фокус переключён на вкладку браузера (индекс {i})")
                        break
            web_view = browser.add_new_tab(url, switch_to=True)
            if not web_view:
                self.logger.error("❌ Не удалось открыть вкладку")
                coin_tab._ucoin_load_processed = True
                coin_tab._ucoin_parsing_id = None
                return
            # Метим вкладку ID монеты — защита от «позднего» парсинга не той монеты
            web_view._ucoin_coin_id = coin_id
            self.logger.info(f"🌐 Открыта страница: {url}")
            state = {'processed': False}

            def on_page_loaded(ok):
                if state['processed']:
                    return
                state['processed'] = True
                try:
                    web_view.loadFinished.disconnect(on_page_loaded)
                except Exception:
                    pass
                if not ok:
                    self.logger.warning("⚠️ Страница UCOIN не загрузилась")
                    coin_tab._ucoin_load_processed = True
                    coin_tab._ucoin_parsing_id = None
                    return
                # Форма всё ещё открыта на ЭТОЙ монете?
                cur = getattr(coin_tab, 'current_coin', None)
                if cur is None or cur.id != coin_id:
                    self.logger.warning(
                        f"⚠️ Форма уже на другой монете — парсинг {coin_id} отменён")
                    coin_tab._ucoin_load_processed = True
                    coin_tab._ucoin_parsing_id = None
                    return
                self.logger.info("📥 Страница загружена — запускаю извлечение данных")
                QTimer.singleShot(1500, lambda: self._safe_extract(coin_tab, web_view, coin_id))

            web_view.loadFinished.connect(on_page_loaded)
            QTimer.singleShot(25000, lambda: self._ucoin_extract_timeout(state, coin_tab))
        except Exception as e:
            self.logger.error(f"Ошибка заполнения из UCOIN: {e}")
            import traceback
            traceback.print_exc()

    def _safe_extract(self, coin_tab, web_view, coin_id=None):
        """Запускает извлечение данных с защитой от парсинга НЕ ТОЙ монеты"""
        try:
            if coin_id is not None:
                cur = getattr(coin_tab, 'current_coin', None)
                if cur is None or cur.id != coin_id:
                    self.logger.warning(
                        f"⚠️ Поздний парсинг отменён: форма открыта на другой монете")
                    coin_tab._ucoin_load_processed = True
                    coin_tab._ucoin_parsing_id = None
                    return
            try:
                coin_tab._extract_ucoin_data(self, web_view)
            except TypeError:
                coin_tab._extract_ucoin_data(self)
        except Exception as e:
            self.logger.error(f"Ошибка извлечения данных: {e}")
            coin_tab._ucoin_load_processed = True
            coin_tab._ucoin_parsing_id = None

    def _ucoin_extract_timeout(self, state, coin_tab):
        """Страховка: если страница не загрузилась за 25 сек — не вешаем очередь"""
        if not state['processed']:
            state['processed'] = True
            self.logger.warning("⏱️ Таймаут загрузки страницы UCOIN (25 сек)")
            coin_tab._ucoin_load_processed = True

    def _do_fill_from_ucoin(self, coin_tab, url):
        """Выполняет заполнение из UCOIN"""
        try:
            # Подавляем подтверждения
            self._suppress_messages = True
            
            # Вызываем метод заполнения
            if hasattr(coin_tab, 'fill_from_ucoin'):
                coin_tab.fill_from_ucoin()
            
            # Снимаем подавление через 3 секунды
            QTimer.singleShot(3000, lambda: setattr(self, '_suppress_messages', False))
            
            # Показываем сообщение, что данные загружены, но не сохранены
            self.status_bar.showMessage("📥 Данные из UCOIN загружены. Нажмите 💾 для сохранения.", 5000)
            
        except Exception as e:
            self.logger.error(f"Ошибка при вызове fill_from_ucoin: {e}")
            self._suppress_messages = False

    def _auto_save_coin(self, coin_tab):
        """Автоматически сохраняет монету без подтверждения.
        После сохранения сбрасывает кэш объектов сессии и перечитывает таблицу,
        чтобы последняя монета массового добавления не отображалась данными донора."""
        try:
            # Проверяем, что монета еще в режиме редактирования
            if coin_tab and coin_tab.edit_mode:
                # Сохраняем без показа сообщений
                old_suppress = getattr(self, '_suppress_messages', False)
                self._suppress_messages = True
                coin_tab.save_changes()
                self._suppress_messages = old_suppress
                # === Сбрасываем кэш объектов SQLAlchemy (identity map) ===
                try:
                    self.db_manager.session.expire_all()
                except Exception:
                    pass
                # === Перечитываем таблицу и дерево СРАЗУ и с задержкой
                # (после финализации очереди массового добавления) ===
                try:
                    self.load_coins()
                    self.load_country_tree(preserve_expanded=True)
                except Exception:
                    pass
                from PySide6.QtCore import QTimer
                QTimer.singleShot(300, self._deferred_refresh_tables)
                self.status_bar.showMessage("✅ Монета сохранена", 3000)
        except Exception as e:
            self.logger.error(f"Ошибка при автосохранении: {e}")

    def _deferred_refresh_tables(self):
        """Отложенное перечитывание таблицы и дерева после автосохранения"""
        try:
            self.db_manager.session.expire_all()
        except Exception:
            pass
        try:
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
        except Exception as e:
            self.logger.debug(f"Ошибка отложенного обновления таблиц: {e}")
            
    def _refresh_tables_now(self):
        """Мгновенно перечитывает монеты и дерево стран из БД"""
        try:
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
        except Exception as e:
            self.logger.debug(f"Ошибка немедленного обновления таблиц: {e}")

    def _refresh_tables_delayed(self, delay=300):
        """Отложенное принудительное обновление таблицы и дерева.
        Гарантирует, что последняя сохранённая монета массового добавления
        отрисуется актуальными данными даже после финализации очереди."""
        QTimer.singleShot(delay, self._refresh_tables_now)
        
    def delete_selected_coins(self):
        """Массовое удаление выделенных монет.
        Приоритет источников выделения:
        1) строки с галочками (checkbox-колонка);
        2) выделенные строки таблицы (Ctrl/Shift+клик);
        3) текущая монета в правой панели (если ничего не выделено).
        После удаления — обновление таблицы, дерева и правой панели."""
        from PySide6.QtWidgets import QMessageBox, QApplication
        from PySide6.QtCore import Qt
        try:
            ids = []
            # === 1) Строки с галочками ===
            if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'get_selected_coin_ids'):
                try:
                    ids = list(self.table_panel.get_selected_coin_ids() or [])
                except Exception as e:
                    self.logger.debug(f"Ошибка get_selected_coin_ids: {e}")
                    ids = []
            # === 2) Выделенные строки таблицы ===
            if not ids and hasattr(self, 'table_panel') and hasattr(self.table_panel, 'table'):
                try:
                    table = self.table_panel.table
                    rows = sorted(set(idx.row() for idx in table.selectedIndexes()))
                    coins_list = (getattr(self.table_panel, '_filtered_coins', None)
                                  or getattr(self.table_panel, 'coins', None) or [])
                    for row in rows:
                        if 0 <= row < len(coins_list):
                            cid = getattr(coins_list[row], 'id', None)
                            if cid:
                                ids.append(cid)
                except Exception as e:
                    self.logger.debug(f"Ошибка сбора выделенных строк: {e}")
            # === 3) Текущая монета (если ничего не выделено) ===
            if not ids:
                coin = getattr(getattr(self, 'detail_panel', None), 'current_coin', None)
                if coin is not None and getattr(coin, 'id', None):
                    ids = [coin.id]
            if not ids:
                QMessageBox.warning(self, "Предупреждение",
                                    "Не выделено ни одной монеты для удаления.\n\n"
                                    "Отметьте строки галочками или выделите их в таблице.")
                return
            ids = list(dict.fromkeys(ids))
            count = len(ids)
            # === Подтверждение ===
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
                return
            # === Удаление ===
            QApplication.setOverrideCursor(Qt.WaitCursor)
            deleted = 0
            errors = []
            try:
                for cid in ids:
                    try:
                        # Удаляем файлы изображений монеты
                        try:
                            coin = self.db_manager.get_coin(cid)
                            if coin:
                                from utils.paths import paths
                                for attr in ('obverse_image', 'reverse_image'):
                                    rel = getattr(coin, attr, None)
                                    if rel:
                                        try:
                                            p = paths.get_root_dir() / rel
                                            if p.exists():
                                                p.unlink()
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        # Удаляем запись БД
                        if hasattr(self.db_manager, 'delete_coin'):
                            self.db_manager.delete_coin(cid)
                        else:
                            from database.models import Coin
                            obj = self.db_manager.session.query(Coin).get(cid)
                            if obj:
                                self.db_manager.session.delete(obj)
                        deleted += 1
                    except Exception as e:
                        errors.append(f"ID {cid}: {e}")
                        try:
                            self.db_manager.session.rollback()
                        except Exception:
                            pass
                try:
                    self.db_manager.session.commit()
                except Exception:
                    pass
            finally:
                QApplication.restoreOverrideCursor()
            # === Обновление интерфейса ===
            try:
                self.load_coins()
            except Exception as e:
                self.logger.debug(f"Ошибка load_coins: {e}")
            try:
                self.load_country_tree(preserve_expanded=True)
            except Exception as e:
                self.logger.debug(f"Ошибка load_country_tree: {e}")
            try:
                if hasattr(self, 'detail_panel') and hasattr(self.detail_panel, 'show_coin_info'):
                    self.detail_panel.show_coin_info(None)
            except Exception:
                pass
            msg = f"✅ Удалено монет: {deleted}"
            if errors:
                msg += f" | ⚠️ ошибок: {len(errors)}"
                for err in errors[:5]:
                    self.logger.error(f"🗑 Ошибка удаления: {err}")
            self.status_bar.showMessage(msg, 5000)
            self.logger.info(f"🗑 Массовое удаление завершено: {deleted} монет")
        except Exception as e:
            self.logger.error(f"Ошибка массового удаления: {e}")
            import traceback
            traceback.print_exc()
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить монеты:\n{e}")