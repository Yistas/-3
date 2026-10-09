# -*- coding: utf-8 -*-

"""
Встроенный браузер на основе WebView2 (Microsoft Edge)
Портативная версия - все данные хранятся в папке с программой
"""

import os
import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QTabWidget, QToolBar, QMessageBox,
                               QLabel, QProgressBar, QApplication, QFrame)
from PySide6.QtCore import Qt, QUrl, QSettings, QTimer, QSize
from PySide6.QtGui import QAction

# Импорт WebView2
try:
    import webview2
    from webview2 import WebView2
    WEBVIEW2_AVAILABLE = True
    print("✅ WebView2 загружен успешно")
except ImportError as e:
    WEBVIEW2_AVAILABLE = False
    print(f"⚠️ WebView2 не загружен: {e}")
except Exception as e:
    WEBVIEW2_AVAILABLE = False
    print(f"⚠️ Ошибка загрузки WebView2: {e}")


class WebView2BrowserWidget(QWidget):
    """Виджет браузера на основе WebView2"""
    
    def __init__(self, parent=None, url="https://www.google.com"):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.WebView2Browser')
        self.url = url
        self.webview = None
        self.is_initialized = False
        
        self.init_ui()
        QTimer.singleShot(100, self.initialize_webview)
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Панель навигации
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(2, 2, 2, 2)
        
        self.back_btn = QPushButton("◀")
        self.back_btn.setFixedSize(28, 28)
        self.back_btn.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("▶")
        self.forward_btn.setFixedSize(28, 28)
        self.forward_btn.clicked.connect(self.go_forward)
        nav_layout.addWidget(self.forward_btn)
        
        self.reload_btn = QPushButton("🔄")
        self.reload_btn.setFixedSize(28, 28)
        self.reload_btn.clicked.connect(self.reload)
        nav_layout.addWidget(self.reload_btn)
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Введите URL...")
        self.url_bar.returnPressed.connect(self.navigate)
        nav_layout.addWidget(self.url_bar)
        
        layout.addLayout(nav_layout)
        
        # Место для WebView2
        self.webview_container = QFrame()
        self.webview_container.setFrameShape(QFrame.NoFrame)
        self.webview_container.setStyleSheet("background-color: white;")
        layout.addWidget(self.webview_container)
    
    def get_user_data_path(self):
        """Возвращает путь для данных пользователя WebView2"""
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent.parent.parent
        
        user_data_path = app_dir / "webview2_data"
        user_data_path.mkdir(parents=True, exist_ok=True)
        return str(user_data_path)
    
    def initialize_webview(self):
        """Инициализирует WebView2"""
        if not WEBVIEW2_AVAILABLE:
            self.show_error("WebView2 не установлен. Установите: pip install webview2")
            return
        
        try:
            # Получаем HWND окна
            hwnd = int(self.webview_container.winId())
            
            # Создаем WebView2
            self.webview = WebView2(
                parent_hwnd=hwnd,
                user_data_folder=self.get_user_data_path(),
                enable_autofill=True,  # Включаем автозаполнение
                enable_authentication=True,  # Включаем сохранение паролей
                enable_cookies=True  # Включаем куки
            )
            
            # Подключаем события
            self.webview.NavigationStarting += self.on_navigation_starting
            self.webview.NavigationCompleted += self.on_navigation_completed
            self.webview.DocumentTitleChanged += self.on_title_changed
            self.webview.CoreWebView2Ready += self.on_core_webview_ready
            
            # Загружаем URL
            self.webview.navigate(self.url)
            
            self.is_initialized = True
            self.logger.info(f"✅ WebView2 браузер создан: {self.url}")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации WebView2: {e}")
            self.show_error(f"Ошибка инициализации браузера: {e}")
    
    def on_core_webview_ready(self, sender, args):
        """Обработчик готовности CoreWebView2"""
        self.logger.info("✅ CoreWebView2 готов")
        
        # Настройка для сохранения паролей
        if hasattr(sender, 'Profile'):
            profile = sender.Profile
            profile.PreferredColorScheme = "light"
            profile.IsPasswordAutosaveEnabled = True  # Включаем сохранение паролей
            profile.IsGeneralAutofillEnabled = True   # Включаем автозаполнение
            self.logger.info("✅ Сохранение паролей включено")
    
    def on_navigation_starting(self, sender, args):
        """Обработчик начала навигации"""
        url = args.Uri
        self.url_bar.setText(url)
        self.logger.debug(f"Навигация: {url}")
    
    def on_navigation_completed(self, sender, args):
        """Обработчик завершения навигации"""
        self.logger.debug("Навигация завершена")
    
    def on_title_changed(self, sender, args):
        """Обработчик изменения заголовка"""
        title = sender.DocumentTitle
        if title and len(title) > 40:
            title = title[:37] + "..."
        # Обновляем заголовок вкладки
        if self.parent() and hasattr(self.parent(), 'update_title'):
            self.parent().update_title(title)
    
    def navigate(self):
        """Переходит по URL"""
        url = self.url_bar.text().strip()
        if not url:
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        if self.webview:
            self.webview.navigate(url)
    
    def go_back(self):
        if self.webview and self.webview.can_go_back():
            self.webview.go_back()
    
    def go_forward(self):
        if self.webview and self.webview.can_go_forward():
            self.webview.go_forward()
    
    def reload(self):
        if self.webview:
            self.webview.reload()
    
    def resizeEvent(self, event):
        """Обработчик изменения размера"""
        super().resizeEvent(event)
        if self.webview and self.is_initialized:
            try:
                self.webview.set_bounds(
                    self.webview_container.x(),
                    self.webview_container.y(),
                    self.webview_container.width(),
                    self.webview_container.height()
                )
            except:
                pass
    
    def show_error(self, message):
        """Показывает сообщение об ошибке"""
        error_label = QLabel(f"❌ Ошибка браузера\n\n{message}")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("color: red; padding: 20px;")
        layout = self.webview_container.layout()
        if layout:
            layout.addWidget(error_label)
        else:
            self.webview_container.setLayout(QVBoxLayout())
            self.webview_container.layout().addWidget(error_label)
    
    def closeEvent(self, event):
        """Обработчик закрытия"""
        if self.webview:
            try:
                self.webview.close()
            except:
                pass
        super().closeEvent(event)


class WebView2BrowserTab(QWidget):
    """Вкладка браузера WebView2"""
    
    def __init__(self, parent=None, url=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.url = url or "https://www.google.com"
        self.browser_widget = None
        self.current_title = "Новая вкладка"
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        self.browser_widget = WebView2BrowserWidget(self, self.url)
        layout.addWidget(self.browser_widget)
    
    def update_title(self, title):
        """Обновляет заголовок"""
        self.current_title = title
        if self.parent_tab and hasattr(self.parent_tab, 'update_tab_title'):
            self.parent_tab.update_tab_title(self, title)
    
    def get_title(self):
        """Возвращает заголовок страницы"""
        return self.current_title
    
    def get_url(self):
        """Возвращает текущий URL"""
        return self.url


class WebView2Browser(QWidget):
    """Главный виджет браузера с вкладками"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.WebView2Browser')
        self.tabs = []
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # Панель инструментов
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Панель вкладок
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.setDocumentMode(True)
        layout.addWidget(self.tab_widget)
        
        # Добавляем первую вкладку
        self.add_new_tab()
    
    def create_toolbar(self):
        """Создает панель инструментов"""
        toolbar = QFrame()
        toolbar.setFrameShape(QFrame.StyledPanel)
        toolbar.setStyleSheet("QFrame { background-color: #f5f5f5; border-radius: 3px; padding: 3px; }")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 3, 5, 3)
        
        # Кнопка новой вкладки
        new_tab_btn = QPushButton("➕")
        new_tab_btn.setFixedSize(28, 28)
        new_tab_btn.clicked.connect(self.add_new_tab)
        layout.addWidget(new_tab_btn)
        
        layout.addStretch()
        
        # Информация о версии
        if WEBVIEW2_AVAILABLE:
            version_label = QLabel("Microsoft Edge (WebView2)")
            version_label.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(version_label)
        
        toolbar.setLayout(layout)
        return toolbar
    
    def add_new_tab(self, url=None):
        """Добавляет новую вкладку"""
        tab = WebView2BrowserTab(self, url)
        title = "Новая вкладка"
        self.tab_widget.addTab(tab, title)
        self.tabs.append(tab)
        self.tab_widget.setCurrentWidget(tab)
    
    def update_tab_title(self, tab, title):
        """Обновляет заголовок вкладки"""
        index = self.tab_widget.indexOf(tab)
        if index >= 0:
            if len(title) > 40:
                title = title[:37] + "..."
            self.tab_widget.setTabText(index, title)
    
    def close_tab(self, index):
        """Закрывает вкладку"""
        if self.tab_widget.count() <= 1:
            QMessageBox.information(self, "Информация", "Нельзя закрыть последнюю вкладку")
            return
        
        widget = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        if widget in self.tabs:
            self.tabs.remove(widget)
        widget.deleteLater()