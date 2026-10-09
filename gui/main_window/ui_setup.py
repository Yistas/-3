# ===== gui/main_window/ui_setup.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Настройка интерфейса MainWindow
"""

import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                               QTabWidget, QStatusBar, QLabel, QSizePolicy,
                               QToolBar, QPushButton)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon


class UiSetupMixin:
    """Примесь с настройкой интерфейса"""
    
    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Coin Collector — Учет монет")
        self.setMinimumSize(1024, 700)

        # Иконка окна
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coin.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # ВАЖНО: стили окна задаются глобальной темой (theme_manager)

        # Меню
        from gui.menus.menu_bar import create_menu_bar
        create_menu_bar(self)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Главный сплиттер
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(5)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

        # Левая панель
        left_panel = self.tree_panel.create_panel()
        self.country_tree = self.tree_panel.get_tree()
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(350)
        self.main_splitter.addWidget(left_panel)
        self.left_panel = left_panel

        # Центральные вкладки
        self.center_tab_widget = self._create_center_tabs()
        self.main_splitter.addWidget(self.center_tab_widget)

        # Правая панель
        from gui.widgets.detail_panel import EditableDetailPanel
        self.detail_panel = EditableDetailPanel(self.db_manager, self)
        self.right_panel = self.detail_panel
        self.right_panel.setMinimumWidth(300)
        self.right_panel.setMaximumWidth(500)
        self.main_splitter.addWidget(self.right_panel)

        # Настройка размеров
        self.main_splitter.setSizes([self.left_panel_size, self.center_panel_size, self.right_panel_size])
        self.main_splitter.splitterMoved.connect(self.on_splitter_moved)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(self.main_splitter)
        central_widget.setLayout(layout)

        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово | Перетаскивайте заголовки колонок для изменения порядка | Кликайте на заголовок для сортировки")

        # ГЛОБАЛЬНЫЙ ПЕРЕКРАС всех виджетов (серебро, продажи, статистика, погодовка и т.д.)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.apply_dark_restyle)

    # ========== МЕТОДЫ СОЗДАНИЯ ВКЛАДОК ==========

    def _create_center_tabs(self):
        """Создает вкладки в центральной части (БЕЗ ЛЕНИВОЙ ЗАГРУЗКИ)"""
        from PySide6.QtWidgets import QTabWidget, QLabel, QSizePolicy
        from PySide6.QtCore import Qt
        
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        
        # Уменьшаем отступы внутри вкладок через стиль
        tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 4px 8px; 
                margin-right: 1px;
            }
        """)
        
        # ПОДКЛЮЧАЕМ СИГНАЛ СМЕНЫ ВКЛАДКИ
        tabs.currentChanged.connect(self.on_center_tab_changed)

        # 1. Таблица монет
        center_panel = self.table_panel.create_panel()
        self.table = self.table_panel.get_table()
        tabs.addTab(center_panel, "🪙 Монеты")

        # 2. Статистика
        try:
            from gui.widgets.statistics_tab import StatisticsTab
            statistics_tab = StatisticsTab(self.db_manager, self)
            self.statistics_tab = statistics_tab
            tabs.addTab(statistics_tab, "📊 Статистика")
        except Exception as e:
            self.logger.error(f"Ошибка создания статистики: {e}")
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "📊 Статистика")

        # 3. Погодовка
        try:
            from gui.widgets.yearly_table.yearly_table_tab import YearlyTableTab
            yearly_tab = YearlyTableTab(self.db_manager, self)
            self.yearly_table_tab = yearly_tab
            self.logger.info("✅ Ссылка сохранена: self.yearly_table_tab")
            tabs.addTab(yearly_tab, "📅 Погодовка")
        except Exception as e:
            self.logger.error(f"Ошибка создания погодовки: {e}")
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "📅 Погодовка")

        # 4. РЫНОК (рыночная стоимость)
        try:
            from gui.widgets.market_value_chart import MarketValueChart
            market_tab = MarketValueChart(self.db_manager, self)
            self.market_value_tab = market_tab
            tabs.addTab(market_tab, "💰 РЫНОК")
        except Exception as e:
            self.logger.error(f"Ошибка создания РЫНКА: {e}")
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "💰 РЫНОК")

        # 5. Драг. металлы
        try:
            from gui.widgets.collection_value_chart import CollectionValueChart
            collection_tab = CollectionValueChart(self.db_manager, self)
            collection_tab.value_updated.connect(self.on_collection_value_updated)
            self.collection_value_tab = collection_tab
            tabs.addTab(collection_tab, "🥇 Драг. металлы")
        except Exception as e:
            self.logger.error(f"Ошибка создания драгметаллов: {e}")
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "🥇 Драг. металлы")

        # 6. Даты (конвертер)
        try:
            from gui.widgets.date_converter_tab import DateConverterTab
            tabs.addTab(DateConverterTab(self.db_manager, self), "📅 Даты")
        except Exception as e:
            self.logger.error(f"Ошибка создания конвертера дат: {e}")
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "📅 Даты")

        # 7. Обмен/Продажа (ЗАГРУЖАЕТСЯ СРАЗУ)
        try:
            from gui.widgets.exchange_tab.exchange_tab import ExchangeTab
            exchange_tab = ExchangeTab(self.db_manager, self)
            self.exchange_tab = exchange_tab
            self.logger.info("✅ Ссылка сохранена: self.exchange_tab")
            tabs.addTab(exchange_tab, "💱 Обмен/Продажа")
        except Exception as e:
            self.logger.error(f"Ошибка создания обмена/продажи: {e}")
            import traceback
            traceback.print_exc()
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "💱 Обмен/Продажа")

        # 8. Заметки
        try:
            from gui.widgets.notebook.notebook_tab import NotebookTab
            notebook_tab = NotebookTab(self.db_manager, self)
            self.notebook_tab = notebook_tab
            tabs.addTab(notebook_tab, "📝 Заметки")
        except Exception as e:
            self.logger.error(f"Ошибка создания заметок: {e}")
            tabs.addTab(QLabel(f"❌ Ошибка: {str(e)[:100]}"), "📝 Заметки")

        # 9. Браузер
        try:
            from gui.widgets.embedded_browser import EmbeddedBrowser
            browser = EmbeddedBrowser(self)
            self.browser_tab = browser
            self.logger.info("✅ Вкладка браузера создана")
            tabs.addTab(browser, "🌐 Браузер")
        except Exception as e:
            self.logger.error(f"Ошибка создания браузера: {e}")
            error_label = QLabel(
                f"❌ Ошибка: {str(e)[:100]}\n"
                f"Установите:\npip install PySide6-WebEngine"
            )
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setWordWrap(True)
            tabs.addTab(error_label, "🌐 Браузер")

        return tabs

    def _adjust_minimum_size(self):
        """Вычисляет минимальный размер окна так, чтобы все вкладки
        и кнопки помещались без обрезания названий"""
        try:
            tab_bar = self.center_tab_widget.tabBar()
            # Суммарная ширина всех вкладок (после первого layout)
            tabs_width = sum(tab_bar.tabRect(i).width() for i in range(tab_bar.count()))
            # Минимальные ширины боковых панелей
            left_min = self.left_panel.minimumWidth()
            right_min = self.right_panel.minimumWidth()
            # Ручки сплиттера + отступы layout
            extra = self.main_splitter.handleWidth() * 2 + 20
            # Центр должен вместить вкладки и тулбар таблицы
            center_min = tabs_width
            toolbar = getattr(self.table_panel, 'toolbar', None)
            if toolbar is not None:
                center_min = max(center_min, toolbar.sizeHint().width())
            min_width = left_min + right_min + center_min + extra
            min_height = 700
            self.setMinimumSize(min_width, min_height)
            self.logger.info(f"Минимальный размер окна: {min_width}x{min_height}")
        except Exception as e:
            self.logger.error(f"Ошибка вычисления минимального размера: {e}")

    def on_tab_changed(self, index):
        """Обработчик смены вкладки (с ленивой загрузкой)"""
        if index < 0:
            return
        
        # Защита от рекурсии
        if self._loading_in_progress:
            return
        
        # Проверяем, загружена ли уже вкладка
        if self._tab_loaded.get(index, False):
            # Если вкладка уже загружена, вызываем обработчик активации
            self._on_tab_activated(index)
            return
        
        # Получаем информацию о вкладке
        tab_info = self._tab_infos.get(index)
        if not tab_info:
            return
        
        self._loading_in_progress = True
        
        # Загружаем содержимое
        try:
            self.logger.info(f"🔄 Ленивая загрузка: {tab_info['name']}")
            
            # Создаём реальный виджет
            real_widget = tab_info['create_func']()
            
            if real_widget:
                # Сохраняем ссылку на виджет в self по имени атрибута
                if tab_info['attr_name']:
                    setattr(self, tab_info['attr_name'], real_widget)
                    self.logger.info(f"✅ Ссылка сохранена: self.{tab_info['attr_name']}")
                
                # Заменяем заглушку
                tab_widget = self.center_tab_widget
                if tab_widget:
                    tab_widget.removeTab(index)
                    tab_widget.insertTab(index, real_widget, tab_info['name'])
                    tab_widget.setCurrentIndex(index)
                
                # Отмечаем как загруженную
                self._tab_loaded[index] = True
                self.logger.info(f"✅ Ленивая загрузка: {tab_info['name']}")
            else:
                self.logger.warning(f"❌ Не удалось загрузить: {tab_info['name']}")
                error_stub = QLabel(f"❌ Ошибка загрузки {tab_info['name']}")
                error_stub.setAlignment(Qt.AlignCenter)
                error_stub.setStyleSheet("color: red; padding: 20px;")
                tab_widget = self.center_tab_widget
                if tab_widget:
                    tab_widget.removeTab(index)
                    tab_widget.insertTab(index, error_stub, tab_info['name'])
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки {tab_info['name']}: {e}")
            import traceback
            traceback.print_exc()
            error_stub = QLabel(f"❌ Ошибка: {str(e)[:100]}")
            error_stub.setAlignment(Qt.AlignCenter)
            error_stub.setStyleSheet("color: red; padding: 20px;")
            tab_widget = self.center_tab_widget
            if tab_widget:
                tab_widget.removeTab(index)
                tab_widget.insertTab(index, error_stub, tab_info['name'])
        finally:
            self._loading_in_progress = False    

    def _add_lazy_tab(self, tabs, tab_name, create_func):
        """Добавляет вкладку с ленивой загрузкой и сохраняет ссылку в self"""
        # Создаём заглушку
        stub = QLabel(f"⏳ Загрузка {tab_name}...")
        stub.setAlignment(Qt.AlignCenter)
        stub.setStyleSheet("font-size: 14px; color: #4a6fa5; padding: 20px;")
        stub.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Добавляем вкладку
        tab_index = tabs.addTab(stub, tab_name)
        self._tab_loaded[tab_index] = False
        
        # Определяем имя атрибута для сохранения
        attr_name = self._get_attr_name(tab_name)
        
        # Сохраняем данные о вкладке
        self._tab_infos[tab_index] = {
            'index': tab_index,
            'name': tab_name,
            'create_func': create_func,
            'stub': stub,
            'attr_name': attr_name
        }
    
    def _get_attr_name(self, tab_name):
        """Возвращает имя атрибута для вкладки"""
        # Убираем эмодзи и пробелы
        clean_name = tab_name.replace("📅", "").replace("📊", "").replace("💰", "").replace("🥇", "").strip()
        # Заменяем пробелы на подчёркивания и добавляем префикс
        attr_name = clean_name.lower().replace("/", "_").replace(" ", "_") + "_tab"
        
        # Специальные случаи
        if "погодовка" in clean_name.lower():
            return "yearly_table_tab"
        if "статистика" in clean_name.lower():
            return "statistics_tab"
        if "рынок" in clean_name.lower():
            return "market_value_tab"
        if "драг" in clean_name.lower() or "металлы" in clean_name.lower():
            return "collection_value_tab"
        if "даты" in clean_name.lower():
            return "date_converter_tab"
        if "обмен" in clean_name.lower() or "продажа" in clean_name.lower():
            return "exchange_tab"
        if "заметки" in clean_name.lower():
            return "notebook_tab"
        if "браузер" in clean_name.lower():
            return "browser_tab"
        
        return attr_name

    def _add_lazy_tab(self, tabs, tab_name, create_func):
        """Добавляет вкладку с ленивой загрузкой"""
        # Создаём заглушку
        stub = QLabel(f"⏳ Загрузка {tab_name}...")
        stub.setAlignment(Qt.AlignCenter)
        stub.setStyleSheet("font-size: 14px; color: #4a6fa5; padding: 20px;")
        stub.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Добавляем вкладку
        tab_index = tabs.addTab(stub, tab_name)
        self._tab_loaded[tab_index] = False
        
        # Сохраняем данные о вкладке
        self._tab_infos[tab_index] = {
            'index': tab_index,
            'name': tab_name,
            'create_func': create_func,
            'stub': stub,
            'attr_name': self._get_attr_name(tab_name)  # Добавляем имя атрибута
        }
    
    def _get_attr_name(self, tab_name):
        """Возвращает имя атрибута для вкладки"""
        # Убираем эмодзи и пробелы
        clean_name = tab_name.replace("📅", "").replace("📊", "").replace("💰", "").replace("🥇", "").strip()
        # Заменяем пробелы на подчёркивания и добавляем префикс
        attr_name = clean_name.lower().replace("/", "_").replace(" ", "_") + "_tab"
        
        # Специальные случаи
        if "погодовка" in clean_name.lower():
            return "yearly_table_tab"
        if "статистика" in clean_name.lower():
            return "statistics_tab"
        if "рынок" in clean_name.lower():
            return "market_value_tab"
        if "драг" in clean_name.lower() or "металлы" in clean_name.lower():
            return "collection_value_tab"
        if "даты" in clean_name.lower():
            return "date_converter_tab"
        if "обмен" in clean_name.lower() or "продажа" in clean_name.lower():
            return "exchange_tab"
        if "заметки" in clean_name.lower():
            return "notebook_tab"
        if "браузер" in clean_name.lower():
            return "browser_tab"
        
        return attr_name
    
    def _on_tab_activated(self, index):
        """Обработчик активации уже загруженной вкладки"""
        if not hasattr(self, 'center_tab_widget') or self.center_tab_widget is None:
            return
        
        tab_text = self.center_tab_widget.tabText(index)
        
        # Обновляем погодовку
        if "Погодовка" in tab_text and hasattr(self, 'yearly_table_tab') and self.yearly_table_tab:
            self.yearly_table_tab.refresh_current()
        
        # Обновляем стоимость коллекции
        if "Драг. металлы" in tab_text and hasattr(self, 'detail_panel'):
            current_item = self.country_tree.currentItem()
            if current_item:
                self.update_collection_value_for_selected_item(current_item)
            else:
                self.detail_panel.show_collection_value()
        
        # Обновляем статистику
        if "Статистика" in tab_text and hasattr(self, 'statistics_tab'):
            self.statistics_tab.load_data()
        
        # Обновляем заметки
        if "Заметки" in tab_text and hasattr(self, 'notebook_tab'):
            if hasattr(self.notebook_tab, 'note_list') and hasattr(self.notebook_tab.note_list, 'refresh'):
                self.notebook_tab.note_list.refresh()
        
        # Обработка вкладки "Обмен/Продажа" — скрываем/показываем панели
        if "Обмен/Продажа" in tab_text:
            self._handle_exchange_tab_visibility(show=False)
        else:
            self._handle_exchange_tab_visibility(show=True)
    
    def _handle_exchange_tab_visibility(self, show=True):
        """
        Управляет видимостью боковых панелей для вкладки "Обмен/Продажа".
        
        Args:
            show: True — показать панели, False — скрыть
        """
        if show:
            # Возвращаем панели обратно, если они были скрыты
            if hasattr(self, '_left_panel_was_visible') and self._left_panel_was_visible:
                if hasattr(self, 'left_panel'):
                    self.left_panel.show()
                    self._left_panel_was_visible = False
            
            if hasattr(self, '_right_panel_was_visible') and self._right_panel_was_visible:
                if hasattr(self, 'right_panel'):
                    self.right_panel.show()
                    self.right_panel_visible = True
                    self._right_panel_was_visible = False
                    if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'update_toggle_panel_action'):
                        self.table_panel.update_toggle_panel_action(True)
        else:
            # Сохраняем текущее состояние панелей перед скрытием
            if not hasattr(self, '_panels_state_saved'):
                self._panels_state_saved = True
                self._saved_left_panel_visible = self.left_panel.isVisible() if hasattr(self, 'left_panel') else True
                self._saved_right_panel_visible = self.right_panel_visible if hasattr(self, 'right_panel_visible') else True
            
            # Скрываем левую панель (дерево стран)
            if hasattr(self, 'left_panel') and self.left_panel.isVisible():
                self.left_panel.hide()
                self._left_panel_was_visible = True
            else:
                self._left_panel_was_visible = False
            
            # Скрываем правую панель (детали)
            if hasattr(self, 'right_panel') and self.right_panel.isVisible():
                self.right_panel.hide()
                self.right_panel_visible = False
                self._right_panel_was_visible = True
            else:
                self._right_panel_was_visible = False
            
            # Обновляем состояние кнопки переключения правой панели
            if hasattr(self, 'table_panel') and hasattr(self.table_panel, 'update_toggle_panel_action'):
                self.table_panel.update_toggle_panel_action(False)
    
    # ===== МЕТОДЫ СОЗДАНИЯ КОНКРЕТНЫХ ВКЛАДОК =====
    
    def _create_statistics_tab(self):
        """Создаёт вкладку статистики"""
        try:
            from gui.widgets.statistics_tab import StatisticsTab
            tab = StatisticsTab(self.db_manager, self)
            self.statistics_tab = tab
            return tab
        except Exception as e:
            self.logger.error(f"Ошибка создания статистики: {e}")
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_yearly_table_tab(self):
        """Создаёт вкладку погодовки"""
        try:
            from gui.widgets.yearly_table.yearly_table_tab import YearlyTableTab
            tab = YearlyTableTab(self.db_manager, self)
            self.yearly_table_tab = tab
            self.logger.info("✅ YearlyTableTab создан и сохранён в self.yearly_table_tab")
            return tab
        except Exception as e:
            self.logger.error(f"Ошибка создания погодовки: {e}")
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_market_value_tab(self):
        """Создаёт вкладку рыночной стоимости"""
        try:
            from gui.widgets.market_value_chart import MarketValueChart
            tab = MarketValueChart(self.db_manager, self)
            self.market_value_tab = tab
            return tab
        except Exception as e:
            self.logger.error(f"Ошибка создания РЫНКА: {e}")
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_collection_value_tab(self):
        """Создаёт вкладку драгметаллов"""
        try:
            from gui.widgets.collection_value_chart import CollectionValueChart
            tab = CollectionValueChart(self.db_manager, self)
            tab.value_updated.connect(self.on_collection_value_updated)
            self.collection_value_tab = tab
            return tab
        except Exception as e:
            self.logger.error(f"Ошибка создания драгметаллов: {e}")
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_date_converter_tab(self):
        """Создаёт вкладку конвертера дат"""
        try:
            from gui.widgets.date_converter_tab import DateConverterTab
            return DateConverterTab(self.db_manager, self)
        except Exception as e:
            self.logger.error(f"Ошибка создания конвертера дат: {e}")
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_exchange_tab(self):
        """Создаёт вкладку обмена/продажи"""
        try:
            from gui.widgets.exchange_tab.exchange_tab import ExchangeTab
            tab = ExchangeTab(self.db_manager, self)
            self.exchange_tab = tab
            return tab
        except Exception as e:
            self.logger.error(f"Ошибка создания обмена/продажи: {e}")
            import traceback
            traceback.print_exc()
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_notebook_tab(self):
        """Создаёт вкладку заметок"""
        try:
            from gui.widgets.notebook.notebook_tab import NotebookTab
            tab = NotebookTab(self.db_manager, self)
            self.notebook_tab = tab
            return tab
        except Exception as e:
            self.logger.error(f"Ошибка создания заметок: {e}")
            from PySide6.QtWidgets import QLabel
            return QLabel(f"❌ Ошибка: {str(e)[:100]}")
    
    def _create_browser_tab(self):
        """Создаёт вкладку браузера"""
        try:
            from gui.widgets.embedded_browser import EmbeddedBrowser
            browser = EmbeddedBrowser(self)
            self.browser_tab = browser
            self.logger.info("✅ Вкладка браузера создана")
            return browser
        except Exception as e:
            self.logger.error(f"Ошибка создания браузера: {e}")
            from PySide6.QtWidgets import QLabel
            error_label = QLabel(
                f"❌ Ошибка: {str(e)[:100]}\n\n"
                f"Установите:\npip install PySide6-WebEngine"
            )
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setWordWrap(True)
            return error_label
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def update_collection_value_for_selected_item(self, item):
        """Обновляет стоимость коллекции для выбранного элемента"""
        if hasattr(self, 'detail_panel'):
            self.detail_panel.show_collection_value()
    
    def on_collection_value_updated(self):
        """Обработчик обновления стоимости коллекции"""
        if hasattr(self, 'detail_panel'):
            self.detail_panel.show_collection_value()
            
            
    def apply_dark_restyle(self):
        """Рекурсивно заменяет светлые хардкод-стили виджетов на тёмные.
        Покрывает все вкладки (серебро, продажи, статистика, погодовка, заметки)."""
        if not self.theme_manager.is_dark():
            return
        replacements = [
            # Фоны
            ('background-color: #f5f5f5', 'background-color: #16213e'),
            ('background-color: #f8f9fa', 'background-color: #16213e'),
            ('background-color: #f0f0f0', 'background-color: #16213e'),
            ('background-color: #fafafa', 'background-color: #16213e'),
            ('background-color: #e0e0e0', 'background-color: #262640'),
            ('background-color: #e9ecef', 'background-color: #262640'),
            ('background-color: white', 'background-color: #16213e'),
            ('background-color: #ffffff', 'background-color: #16213e'),
            ('stop: 0 #f8f9fa', 'stop: 0 #16213e'),
            ('stop: 1 #e9ecef', 'stop: 1 #262640'),
            # Текст
            ('color: #666', 'color: #a8a8d0'),
            ('color: #666666', 'color: #a8a8d0'),
            ('color: #333', 'color: #e4e4ef'),
            ('color: #000000', 'color: #e4e4ef'),
            ('color: #4a6fa5', 'color: #7c74ff'),
            # Границы
            ('border: 1px solid #ddd', 'border: 1px solid #2a2a4a'),
            ('border: 1px solid #ccc', 'border: 1px solid #2a2a4a'),
            ('border: 1px solid #dee2e6', 'border: 1px solid #2a2a4a'),
            ('border: 1px solid #999', 'border: 1px solid #3d3d5c'),
        ]
        from PySide6.QtWidgets import QWidget
        for widget in self.findChildren(QWidget):
            ss = widget.styleSheet()
            if not ss:
                continue
            new_ss = ss
            for old, new in replacements:
                if old in new_ss:
                    new_ss = new_ss.replace(old, new)
            if new_ss != ss:
                widget.setStyleSheet(new_ss)