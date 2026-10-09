# ===== gui/menus/menu_bar.py =====
# -*- coding: utf-8 -*-
"""
Создание меню приложения
"""
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction


def create_menu_bar(main_window):
    """Создает меню приложения"""
    menubar = main_window.menuBar()
    # ВАЖНО: не задаём стили меню здесь —
    # меню оформляется глобальной темой (theme_manager)

    # ==================== МЕНЮ "ФАЙЛ" ====================
    file_menu = menubar.addMenu("📁 Файл")

    backup_settings_action = QAction("⚙️ Настройки бекапа", main_window)
    backup_settings_action.triggered.connect(main_window.show_backup_settings)
    file_menu.addAction(backup_settings_action)

    file_menu.addSeparator()

    backup_action = QAction("💾 Создать бекап", main_window)
    backup_action.triggered.connect(main_window.create_backup)
    file_menu.addAction(backup_action)

    restore_action = QAction("♻️ Восстановить из бекапа", main_window)
    restore_action.triggered.connect(main_window.restore_backup)
    file_menu.addAction(restore_action)

    file_menu.addSeparator()

    exit_action = QAction("🚪 Выход", main_window)
    exit_action.setShortcut("Ctrl+Q")
    exit_action.triggered.connect(main_window.close)
    file_menu.addAction(exit_action)

    # ==================== МЕНЮ "НАСТРОЙКИ" ====================
    settings_menu = menubar.addMenu("⚙️ Настройки")

    manage_fields_action = QAction("📊 Управление полями", main_window)
    manage_fields_action.triggered.connect(main_window.manage_custom_fields)
    settings_menu.addAction(manage_fields_action)

    settings_menu.addSeparator()

    numista_settings_action = QAction("🔑 Настройки Numista API", main_window)
    numista_settings_action.triggered.connect(main_window.show_numista_settings)
    settings_menu.addAction(numista_settings_action)

    settings_menu.addSeparator()

    # === СОХРАНИТЬ ИЗМЕНЕНИЯ ===
    save_changes_action = QAction("💾 Сохранить все изменения", main_window)
    save_changes_action.setShortcut("Ctrl+S")
    save_changes_action.triggered.connect(main_window.save_all_changes)
    settings_menu.addAction(save_changes_action)

    settings_menu.addSeparator()

    ucoin_settings_action = QAction("🔑 Настройки UCOIN", main_window)
    ucoin_settings_action.triggered.connect(main_window.show_ucoin_settings)
    settings_menu.addAction(ucoin_settings_action)

    settings_menu.addSeparator()

    manage_themes_action = QAction("🎨 Управление темами", main_window)
    manage_themes_action.triggered.connect(main_window.show_theme_manager)
    settings_menu.addAction(manage_themes_action)

    # ==================== МЕНЮ "СЕРВИСЫ" ====================
    services_menu = menubar.addMenu("🛠️ Сервисы")

    load_prices_action = QAction("📥 Загрузка рыночных цен", main_window)
    load_prices_action.triggered.connect(main_window.load_market_prices)
    services_menu.addAction(load_prices_action)

    services_menu.addSeparator()

    import_purchases_action = QAction("📥 Импорт закупок (Excel)", main_window)
    import_purchases_action.triggered.connect(main_window.import_purchases)
    services_menu.addAction(import_purchases_action)

    services_menu.addSeparator()

    gdrive_settings_action = QAction("☁️ Google Drive синхронизация", main_window)
    gdrive_settings_action.triggered.connect(main_window.show_gdrive_sync_settings)
    services_menu.addAction(gdrive_settings_action)

    services_menu.addSeparator()

    reload_db_action = QAction("🔄 Перечитать БД", main_window)
    reload_db_action.setShortcut("Ctrl+Shift+R")
    reload_db_action.triggered.connect(main_window.reload_database)
    services_menu.addAction(reload_db_action)

    # ==================== МЕНЮ "СПРАВОЧНИКИ" ====================
    references_menu = menubar.addMenu("📚 Справочники")

    references_action = QAction("📚 Все справочники", main_window)
    references_action.triggered.connect(main_window.show_references)
    references_menu.addAction(references_action)

    references_menu.addSeparator()



    advanced_map_action = QAction("🏛️ Историческая карта", main_window)
    advanced_map_action.setShortcut("Ctrl+H")
    advanced_map_action.triggered.connect(main_window.show_advanced_map)
    references_menu.addAction(advanced_map_action)

    references_menu.addSeparator()

    successor_action = QAction("🏛️ Историческая преемственность", main_window)
    successor_action.triggered.connect(main_window.show_successor_dialog)
    references_menu.addAction(successor_action)

    # ==================== МЕНЮ "ВИД" ====================
    view_menu = menubar.addMenu("👁️ Вид")

    toggle_panel_action = QAction("▶️ Скрыть боковую панель", main_window)
    toggle_panel_action.setCheckable(True)
    toggle_panel_action.setChecked(main_window.right_panel_visible)
    toggle_panel_action.triggered.connect(main_window.toggle_right_panel)
    view_menu.addAction(toggle_panel_action)
    main_window.toggle_panel_menu_action = toggle_panel_action

    view_menu.addSeparator()

    theme_menu = view_menu.addMenu("🎨 Тема оформления")

    dark_theme_action = QAction("🌙 Тёмная", main_window)
    dark_theme_action.triggered.connect(lambda: main_window.change_theme('Тёмная'))
    theme_menu.addAction(dark_theme_action)

    light_theme_action = QAction("☀️ Светлая", main_window)
    light_theme_action.triggered.connect(lambda: main_window.change_theme('Светлая'))
    theme_menu.addAction(light_theme_action)

    view_menu.addSeparator()

    # ==================== МЕНЮ "СПРАВКА" ====================
    help_menu = menubar.addMenu("❓ Справка")

    about_action = QAction("ℹ️ О программе", main_window)
    about_action.triggered.connect(main_window.show_about)
    help_menu.addAction(about_action)