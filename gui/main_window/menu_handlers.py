# -*- coding: utf-8 -*-

"""
Методы MainWindow для обработки пунктов меню
"""

from PySide6.QtWidgets import QMessageBox, QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt


class MenuHandlersMixin:
    """Примесь с методами-обработчиками меню"""
    
    # ========== СПРАВОЧНИКИ ==========
    
    def show_references(self):
        """Открывает единое окно справочников"""
        from gui.dialogs.references_dialog import ReferencesDialog
        dialog = ReferencesDialog(self.db_manager, self)
        dialog.exec()
    
    def show_continent_reference(self):
        """Показывает справочник континентов"""
        from gui.dialogs.continent_reference_dialog import ContinentReferenceDialog
        dialog = ContinentReferenceDialog(self.db_manager, self)
        dialog.exec()
    
    # ========== КАРТЫ ==========
    
    def show_statistics_map(self):
        """Показывает статистическую карту коллекции"""
        self.logger.info("Открытие статистической карты")
        
        try:
            from gui.widgets.map_widget import MapWidget
            
            self.map_dialog = QDialog(self)
            self.map_dialog.setWindowTitle("🗺️ Статистическая карта мира")
            self.map_dialog.setMinimumSize(1200, 800)
            self.map_dialog.setWindowIcon(self.windowIcon())
            
            layout = QVBoxLayout()
            self.map_dialog.setLayout(layout)
            
            map_widget = MapWidget(self.db_manager, self.map_dialog)
            layout.addWidget(map_widget)
            
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            close_btn = QPushButton("❌ Закрыть")
            close_btn.clicked.connect(self.map_dialog.close)
            close_btn.setMinimumHeight(35)
            close_btn.setMinimumWidth(100)
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            
            self.map_dialog.show()
            
        except Exception as e:
            self.logger.error(f"Ошибка при открытии карты: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть карту:\n{str(e)}")
    
    def show_advanced_map(self):
        """Показывает улучшенную историческую карту"""
        self.logger.info("Открытие улучшенной исторической карты")
        
        try:
            from gui.widgets.advanced_map_widget import AdvancedMapWidget
            
            self.advanced_map_dialog = QDialog(self)
            self.advanced_map_dialog.setWindowTitle("🗺️ Историческая карта мира")
            self.advanced_map_dialog.setMinimumSize(1200, 800)
            self.advanced_map_dialog.setWindowIcon(self.windowIcon())
            
            layout = QVBoxLayout()
            self.advanced_map_dialog.setLayout(layout)
            
            map_widget = AdvancedMapWidget(self.db_manager, self.advanced_map_dialog)
            layout.addWidget(map_widget)
            
            close_btn = QPushButton("❌ Закрыть")
            close_btn.clicked.connect(self.advanced_map_dialog.close)
            close_btn.setMinimumHeight(35)
            close_btn.setMinimumWidth(100)
            layout.addWidget(close_btn)
            
            self.advanced_map_dialog.show()
            
        except Exception as e:
            self.logger.error(f"Ошибка при открытии карты: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть карту:\n{str(e)}")
    
    # ========== БЕКАПЫ ==========
    
    def show_backup_settings(self):
        """Показывает диалог настроек бекапа"""
        from gui.dialogs.backup_settings_dialog import BackupSettingsDialog
        dialog = BackupSettingsDialog(self.backup_settings, self)
        if dialog.exec():
            self.status_bar.showMessage("✅ Настройки бекапа сохранены", 3000)
    
    def create_backup(self):
        """Создает резервную копию вручную"""
        from gui.dialogs.backup_dialog import BackupDialog
        dialog = BackupDialog(self.backup_manager, self)
        dialog.exec()
    
    def restore_backup(self):
        """Открывает диалог восстановления из бекапа"""
        from gui.dialogs.backup_dialog import BackupDialog
        dialog = BackupDialog(self.backup_manager, self)
        dialog.exec()
    
    # ========== ТЕМЫ ==========
    
    def change_theme(self, theme_name):
        """Изменяет тему оформления"""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            self.theme_manager.apply_theme(app, theme_name)
            self.saved_theme = theme_name
            # Перекрашиваем панели с собственными стилями
            if hasattr(self, 'tree_panel') and self.tree_panel:
                self.tree_panel.update_style()
            if hasattr(self, 'country_tree') and self.country_tree:
                self.country_tree.update_style()
            if hasattr(self, 'table_panel') and self.table_panel:
                self.table_panel.update_style()
            # Глобальный перекрас всех вкладок (серебро, продажи, статистика, погодовка)
            self.apply_dark_restyle()
            self.status_bar.showMessage(f"✅ Тема изменена на '{theme_name}'", 3000)
            app.processEvents()
            self.save_settings()
    
    def show_theme_manager(self):
        """Показывает диалог управления темами"""
        from gui.theme_manager import ThemeManagerDialog
        dialog = ThemeManagerDialog(self.theme_manager, self)
        dialog.theme_changed.connect(self.on_theme_changed)
        dialog.exec()
    
    def on_theme_changed(self, theme_name):
        """Обработчик смены темы"""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            self.theme_manager.apply_theme(app, theme_name)
            if hasattr(self, 'tree_panel') and self.tree_panel:
                self.tree_panel.update_style()
            if hasattr(self, 'country_tree') and self.country_tree:
                self.country_tree.update_style()
            self.status_bar.showMessage(f"✅ Тема изменена на '{theme_name}'", 3000)
            app.processEvents()
            self.save_settings()
    
    # ========== СЕРВИСЫ ==========
    
    def show_numista_settings(self):
        """Открывает диалог настроек Numista API"""
        from gui.dialogs.numista_settings_dialog import NumistaSettingsDialog
        dialog = NumistaSettingsDialog(self.settings_manager, self)
        dialog.exec()
    
    def show_ucoin_settings(self):
        """Открывает диалог настроек UCOIN"""
        from gui.dialogs.ucoin_settings_dialog import UcoinSettingsDialog
        from utils.password_manager import PasswordManager
        
        password_manager = PasswordManager()
        dialog = UcoinSettingsDialog(password_manager, self)
        dialog.exec()
    
    def open_coin_in_numista(self, coin_id):
        """Открывает монету на Numista в браузере"""
        from utils.numista_api import NumistaAPI
        from PySide6.QtWidgets import QProgressDialog
        
        coin = self.db_manager.get_coin(coin_id)
        if not coin:
            QMessageBox.warning(self, "Ошибка", "Монета не найдена")
            return
        
        api_key = self.settings_manager.get_numista_api_key()
        
        if not api_key:
            reply = QMessageBox.question(
                self, "Настройка Numista",
                "Для поиска на Numista нужен API ключ.\n\nВведите API ключ сейчас?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                key, ok = QInputDialog.getText(self, "API ключ Numista", "Введите ваш API ключ:")
                if ok and key:
                    self.settings_manager.set_numista_credentials(key)
                    api_key = key
                else:
                    return
            else:
                return
        
        progress = QProgressDialog("Поиск монеты на Numista...", "Отмена", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            api = NumistaAPI(api_key)
            url = api.search_by_coin_data(coin)
            
            if url:
                for i in range(self.center_tab_widget.count()):
                    if "Браузер" in self.center_tab_widget.tabText(i):
                        self.center_tab_widget.setCurrentIndex(i)
                        browser = self.center_tab_widget.widget(i)
                        if hasattr(browser, 'add_new_tab'):
                            browser.add_new_tab(url)
                        elif hasattr(browser, 'web_view'):
                            from PySide6.QtCore import QUrl
                            browser.web_view.setUrl(QUrl(url))
                        break
                else:
                    import webbrowser
                    webbrowser.open(url)
            else:
                QMessageBox.information(self, "Не найдено", "Монета не найдена на Numista")
        except Exception as e:
            progress.close()
            self.logger.error(f"Ошибка поиска на Numista: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить поиск:\n{e}")
        finally:
            progress.close()
    
    def load_market_prices(self):
        """Открывает диалог загрузки рыночных цен"""
        from gui.dialogs.load_market_prices_dialog import LoadMarketPricesDialog
        dialog = LoadMarketPricesDialog(self.db_manager, self)
        dialog.exec()
    
    # ========== СТРАНЫ ==========
    
    def add_country_from_toolbar(self):
        """Добавляет новую страну через тулбар"""
        from gui.dialogs.add_country_dialog import AddCountryDialog
        dialog = AddCountryDialog(self.db_manager, self)
        if dialog.exec():
            country_data = dialog.get_country_data()
            if country_data['name']:
                self.create_new_country(country_data)
    
    def add_country_from_menu(self):
        """Добавляет новую страну через меню"""
        self.add_country_from_toolbar()
    
    def manage_continents(self):
        """Управление континентами"""
        QMessageBox.information(self, "Управление континентами",
            "Функция управления континентами находится в разработке.")
    
    def show_successor_dialog(self):
        """Показывает диалог управления исторической преемственностью стран"""
        try:
            from gui.dialogs.successor_dialog import SuccessorDialog
            dialog = SuccessorDialog(self.db_manager, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Ошибка при открытии диалога преемственности: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог:\n{str(e)}")
    
    # ========== О ПРОГРАММЕ ==========
    
    def show_about(self):
        """Показывает информацию о программе"""
        QMessageBox.about(
            self,
            "О программе Coin Collector",
            "<h2>Coin Collector v0.9.0</h2>"
            "<p>Программа для учета коллекции монет</p>"
            "<p><b>Возможности:</b></p>"
            "<ul>"
            "<li>Добавление и редактирование монет</li>"
            "<li>Номер по каталогу для каждой монеты</li>"
            "<li>Раздельные поля для номинала и валюты</li>"
            "<li>Единое окно справочников</li>"
            "<li>Детальная информация о каждой монете</li>"
            "<li>Настройка отображаемых колонок в таблице</li>"
            "<li>Сортировка по клику на заголовок</li>"
            "<li>Дерево стран с фильтрацией и drag & drop</li>"
            "<li>Статистика коллекции</li>"
            "<li>Автоматическое резервное копирование</li>"
            "<li>Смена темы оформления</li>"
            "<li>Статистическая карта мира</li>"
            "<li>Историческая преемственность стран</li>"
            "</ul>"
            "<p><b>Лицензия:</b> MIT</p>"
        )
        
        
# ===== gui/main_window/menu_handlers.py =====
# ДОБАВИТЬ МЕТОД В MenuHandlersMixin

    def import_purchases(self):
        """Открывает диалог импорта закупок"""
        from gui.dialogs.import_purchases_dialog import ImportPurchasesDialog
        dialog = ImportPurchasesDialog(self.db_manager, self)
        if dialog.exec():
            # Обновляем вкладку обмена если она открыта
            if hasattr(self, 'exchange_tab'):
                self.exchange_tab.load_data()
            self.status_bar.showMessage("✅ Импорт завершен", 3000)
            
# ===== gui/main_window/menu_handlers.py =====
# ДОБАВИТЬ В КОНЕЦ КЛАССА MenuHandlersMixin

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
            
    def show_gdrive_sync_dialog(self):
        """Открывает диалог управления синхронизацией с Google Drive"""
        try:
            from gui.dialogs.gdrive_sync_dialog import GDriveSyncDialog
            
            # Проверяем, есть ли атрибут gdrive_sync
            if not hasattr(self, 'gdrive_sync') or self.gdrive_sync is None:
                # Пытаемся инициализировать заново
                try:
                    from utils.gdrive_oauth import get_gdrive_sync
                    self.gdrive_sync = get_gdrive_sync()
                except Exception as e:
                    self.logger.error(f"Ошибка инициализации Google Drive: {e}")
                
                if not hasattr(self, 'gdrive_sync') or self.gdrive_sync is None or not self.gdrive_sync.is_available():
                    QMessageBox.warning(
                        self, 
                        "Синхронизация недоступна",
                        "Google Drive не настроен.\n\n"
                        "Для настройки:\n"
                        "1. Получите credentials.json от Google Cloud Console\n"
                        "2. Положите файл в папку data/\n"
                        "3. Перезапустите программу\n\n"
                        "Или настройте через меню Настройки → Google Drive"
                    )
                    return
            
            dialog = GDriveSyncDialog(self.gdrive_sync, self)
            dialog.exec()
            
        except ImportError as e:
            QMessageBox.warning(
                self, 
                "Модуль не найден",
                f"Не удалось загрузить диалог:\n{e}\n\n"
                f"Убедитесь, что файл gui/dialogs/gdrive_sync_dialog.py существует\n"
                f"и установлены зависимости: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )
        except Exception as e:
            self.logger.error(f"Ошибка открытия диалога: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка: {e}")
            
            
    def show_gdrive_sync_settings(self):
        """Открывает диалог настроек Google Drive"""
        try:
            from gui.dialogs.gdrive_sync_dialog import GDriveSyncDialog
            
            # Проверяем и инициализируем gdrive_sync если нужно
            if not hasattr(self, 'gdrive_sync') or self.gdrive_sync is None:
                try:
                    from utils.gdrive_oauth import get_gdrive_sync
                    self.gdrive_sync = get_gdrive_sync()
                except ImportError:
                    QMessageBox.warning(
                        self,
                        "Библиотеки не установлены",
                        "Для работы с Google Drive установите:\n"
                        "pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
                    )
                    return
                except Exception as e:
                    self.logger.error(f"Ошибка инициализации: {e}")
            
            if not hasattr(self, 'gdrive_sync') or self.gdrive_sync is None:
                QMessageBox.warning(self, "Ошибка", "Не удалось инициализировать Google Drive")
                return
            
            dialog = GDriveSyncDialog(self.gdrive_sync, self)
            dialog.exec()
            
        except ImportError as e:
            QMessageBox.warning(
                self,
                "Модуль не найден",
                f"Не удалось загрузить диалог:\n{e}\n\n"
                f"Проверьте наличие файла gui/dialogs/gdrive_sync_dialog.py"
            )
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка открытия диалога:\n{e}")
            
    def save_all_changes(self):
        """Сохраняет все несохранённые изменения в базу данных с синхронизацией WAL"""
        from PySide6.QtWidgets import QMessageBox, QApplication
        from PySide6.QtCore import Qt
        from sqlalchemy import text
        
        self.logger.info("=" * 60)
        self.logger.info("💾 СОХРАНЕНИЕ ВСЕХ ИЗМЕНЕНИЙ")
        self.logger.info("=" * 60)
        
        # Показываем курсор ожидания
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            saved_count = 0
            errors = []
            details = []
            
            # ===== 1. СОХРАНЯЕМ ИЗМЕНЕНИЯ В ЗАКУПКАХ (EXCHANGE TAB) =====
            if hasattr(self, 'exchange_tab'):
                exchange_tab = self.exchange_tab
                try:
                    # Сохраняем dirty изменения в закупках
                    if hasattr(exchange_tab, '_flush_changes'):
                        exchange_tab._flush_changes()
                        saved_count += 1
                        details.append("  ✅ Закупки (Purchases)")
                        self.logger.info("  ✅ Сохранены закупки")
                    
                    # Сохраняем через _save_timer если есть
                    if hasattr(exchange_tab, '_save_timer') and exchange_tab._save_timer.isActive():
                        exchange_tab._save_timer.stop()
                        if hasattr(exchange_tab, '_flush_changes'):
                            exchange_tab._flush_changes()
                            saved_count += 1
                            details.append("  ✅ Закупки (timer)")
                    
                    # Сохраняем прайс-лист если есть
                    if hasattr(exchange_tab, 'save_status_label'):
                        exchange_tab.save_status_label.setText("💾 Сохранено")
                        
                except Exception as e:
                    errors.append(f"Закупки: {str(e)}")
                    self.logger.error(f"  ❌ Ошибка сохранения закупок: {e}")
            
            # ===== 2. СОХРАНЯЕМ ИЗМЕНЕНИЯ В СДЕЛКАХ (DEALS TAB) =====
            if hasattr(self, 'deals_tab'):
                deals_tab = self.deals_tab
                try:
                    if hasattr(deals_tab, '_flush_changes'):
                        deals_tab._flush_changes()
                        saved_count += 1
                        details.append("  ✅ Сделки (Deals)")
                        self.logger.info("  ✅ Сохранены сделки")
                    
                    # Сохраняем через _save_timer если есть
                    if hasattr(deals_tab, '_save_timer') and deals_tab._save_timer.isActive():
                        deals_tab._save_timer.stop()
                        if hasattr(deals_tab, '_flush_changes'):
                            deals_tab._flush_changes()
                            saved_count += 1
                            details.append("  ✅ Сделки (timer)")
                            
                except Exception as e:
                    errors.append(f"Сделки: {str(e)}")
                    self.logger.error(f"  ❌ Ошибка сохранения сделок: {e}")
            
            # ===== 3. СОХРАНЯЕМ ИЗМЕНЕНИЯ В ПРОДАЖАХ (SALES TAB) =====
            if hasattr(self, 'sales_tab'):
                sales_tab = self.sales_tab
                try:
                    if hasattr(sales_tab, '_flush_changes'):
                        sales_tab._flush_changes()
                        saved_count += 1
                        details.append("  ✅ Продажи (Sales)")
                        self.logger.info("  ✅ Сохранены продажи")
                    
                    if hasattr(sales_tab, '_save_timer') and sales_tab._save_timer.isActive():
                        sales_tab._save_timer.stop()
                        if hasattr(sales_tab, '_flush_changes'):
                            sales_tab._flush_changes()
                            saved_count += 1
                            details.append("  ✅ Продажи (timer)")
                            
                except Exception as e:
                    errors.append(f"Продажи: {str(e)}")
                    self.logger.error(f"  ❌ Ошибка сохранения продаж: {e}")
            
            # ===== 4. СОХРАНЯЕМ ИЗМЕНЕНИЯ В МОНЕТАХ (COIN TAB) =====
            if hasattr(self, 'detail_panel'):
                coin_tab = self.detail_panel.coin_tab
                if coin_tab and coin_tab.edit_mode and coin_tab.current_coin:
                    try:
                        if hasattr(coin_tab, 'save_changes'):
                            # Временно отключаем флаг подавления сообщений
                            old_suppress = getattr(self, '_suppress_messages', False)
                            self._suppress_messages = True
                            coin_tab.save_changes()
                            self._suppress_messages = old_suppress
                            saved_count += 1
                            details.append("  ✅ Монета (CoinTab)")
                            self.logger.info("  ✅ Сохранена редактируемая монета")
                    except Exception as e:
                        errors.append(f"Монета: {str(e)}")
                        self.logger.error(f"  ❌ Ошибка сохранения монеты: {e}")
            
            # ===== 5. СОХРАНЯЕМ ИЗМЕНЕНИЯ В ПОГОДОВКЕ (YEARLY TABLE) =====
            if hasattr(self, 'yearly_table_tab'):
                yearly_tab = self.yearly_table_tab
                if yearly_tab and yearly_tab.is_modified:
                    try:
                        if hasattr(yearly_tab, 'save_current_table'):
                            yearly_tab.save_current_table()
                            saved_count += 1
                            details.append("  ✅ Погодовка (YearlyTable)")
                            self.logger.info("  ✅ Сохранена погодовка")
                    except Exception as e:
                        errors.append(f"Погодовка: {str(e)}")
                        self.logger.error(f"  ❌ Ошибка сохранения погодовки: {e}")
            
            # ===== 6. СОХРАНЯЕМ ИЗМЕНЕНИЯ В ЗАМЕТКАХ (NOTEBOOK) =====
            if hasattr(self, 'notebook_tab'):
                notebook_tab = self.notebook_tab
                try:
                    if hasattr(notebook_tab, 'note_editor'):
                        editor = notebook_tab.note_editor
                        if editor and editor.current_note:
                            editor.save_note()
                            saved_count += 1
                            details.append("  ✅ Заметки (Notebook)")
                            self.logger.info("  ✅ Сохранена заметка")
                except Exception as e:
                    errors.append(f"Заметки: {str(e)}")
                    self.logger.error(f"  ❌ Ошибка сохранения заметок: {e}")
            
            # ===== 7. СОХРАНЯЕМ ИЗМЕНЕНИЯ В СЕРЕБРЕ (SILVER SALES) =====
            if hasattr(self, 'exchange_tab'):
                silver_tab = None
                if hasattr(self.exchange_tab, 'silver_sales_tab'):
                    silver_tab = self.exchange_tab.silver_sales_tab
                elif hasattr(self, 'silver_sales_tab'):
                    silver_tab = self.silver_sales_tab
                
                if silver_tab:
                    try:
                        if hasattr(silver_tab, '_force_save_all'):
                            silver_tab._force_save_all()
                            saved_count += 1
                            details.append("  ✅ Продажа серебра")
                            self.logger.info("  ✅ Сохранены продажи серебра")
                    except Exception as e:
                        errors.append(f"Серебро: {str(e)}")
                        self.logger.error(f"  ❌ Ошибка сохранения серебра: {e}")
            
            # ===== 8. ПРИНУДИТЕЛЬНЫЙ COMMIT В БД =====
            if hasattr(self, 'db_manager'):
                try:
                    self.db_manager.session.commit()
                    self.logger.info("  ✅ Commit в БД выполнен")
                    details.append("  ✅ Commit транзакций")
                except Exception as e:
                    self.db_manager.session.rollback()
                    errors.append(f"Commit БД: {str(e)}")
                    self.logger.error(f"  ❌ Ошибка commit: {e}")
            
            # ===== 9. WAL CHECKPOINT (СИНХРОНИЗАЦИЯ С ОСНОВНЫМ ФАЙЛОМ) =====
            if hasattr(self, 'db_manager'):
                try:
                    with self.db_manager.engine.connect() as conn:
                        # Выполняем полную контрольную точку с усечением WAL
                        result = conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
                        conn.commit()
                        
                        # Получаем результат
                        row = result.fetchone()
                        if row:
                            busy = row[0] if len(row) > 0 else 0
                            log = row[1] if len(row) > 1 else 0
                            checkpointed = row[2] if len(row) > 2 else 0
                            
                            self.logger.info(f"  ✅ WAL checkpoint: busy={busy}, log={log}, checkpointed={checkpointed}")
                            details.append(f"  ✅ WAL синхронизация ({checkpointed} страниц)")
                        else:
                            self.logger.info("  ✅ WAL checkpoint выполнен")
                            details.append("  ✅ WAL синхронизация")
                            
                except Exception as e:
                    errors.append(f"WAL checkpoint: {str(e)}")
                    self.logger.error(f"  ❌ Ошибка WAL checkpoint: {e}")
            
            # ===== 10. ОБНОВЛЯЕМ СТАТУС-БАР ВО ВСЕХ ВКЛАДКАХ =====
            try:
                # Обновляем статус в exchange_tab
                if hasattr(self, 'exchange_tab'):
                    if hasattr(self.exchange_tab, 'save_status_label'):
                        self.exchange_tab.save_status_label.setText("💾 Сохранено")
                        self.exchange_tab.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                        QTimer.singleShot(3000, lambda: self.exchange_tab.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
                
                # Обновляем статус в deals_tab
                if hasattr(self, 'deals_tab'):
                    if hasattr(self.deals_tab, 'status_label'):
                        self.deals_tab.status_label.setText("✅ Все изменения сохранены")
                        self.deals_tab.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                        QTimer.singleShot(3000, lambda: self.deals_tab.status_label.setStyleSheet("color: #666; font-size: 11px;"))
                
                # Обновляем статус в sales_tab
                if hasattr(self, 'sales_tab'):
                    if hasattr(self.sales_tab, 'status_label'):
                        self.sales_tab.status_label.setText("✅ Все изменения сохранены")
                        self.sales_tab.status_label.setStyleSheet("color: #28a745;")
                        QTimer.singleShot(3000, lambda: self.sales_tab.status_label.setStyleSheet("color: #666;"))
                        
            except Exception as e:
                self.logger.warning(f"Не удалось обновить статус-бары: {e}")
            
            # ===== ПОКАЗЫВАЕМ РЕЗУЛЬТАТ =====
            if errors:
                # Формируем детальное сообщение об ошибках
                error_text = "\n".join([f"  • {e}" for e in errors[:10]])
                if len(errors) > 10:
                    error_text += f"\n  • ... и ещё {len(errors) - 10} ошибок"
                
                reply = QMessageBox.warning(
                    self,
                    "Сохранение с ошибками",
                    f"✅ Сохранено компонентов: {saved_count}\n"
                    f"❌ Ошибок: {len(errors)}\n\n"
                    f"Детали сохранённого:\n" + "\n".join(details[-10:]) + "\n\n"
                    f"Ошибки:\n{error_text}\n\n"
                    f"Продолжить работу?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    self.status_bar.showMessage(f"⚠️ Сохранено с {len(errors)} ошибками, работа завершена", 5000)
                else:
                    self.status_bar.showMessage(f"⚠️ Сохранено с {len(errors)} ошибками", 5000)
            else:
                # Успешное сохранение
                QMessageBox.information(
                    self,
                    "Сохранение завершено",
                    f"✅ Все изменения успешно сохранены!\n\n"
                    f"📊 Сохранено компонентов: {saved_count}\n"
                    f"📁 WAL-журнал синхронизирован с основным файлом БД\n\n"
                    f"Детали:\n" + "\n".join(details[-15:])
                )
                self.status_bar.showMessage("✅ Все изменения сохранены (WAL checkpoint)", 5000)
            
            self.logger.info(f"📊 ИТОГО: сохранено {saved_count} компонентов, ошибок {len(errors)}")
            self.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.error(f"Критическая ошибка при сохранении: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить изменения:\n{e}")
        finally:
            # Восстанавливаем курсор
            QApplication.restoreOverrideCursor()