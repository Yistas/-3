# -*- coding: utf-8 -*-

"""
Вкладка с информацией о стране
"""

import os
from pathlib import Path
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QGroupBox,
                               QScrollArea, QSizePolicy, QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from utils.paths import paths
from .base_panel import ImageLabel
from database.models import Country


class CountryTab(QWidget):
    """Вкладка с информацией о стране"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.CountryTab')
        
        self.current_country = None
        self.current_country_id = None
        from utils.paths import paths
        self.custom_images_dir = paths.get_data_dir() / "custom_images"
        self.custom_images_dir.mkdir(parents=True, exist_ok=True)
        
        self.init_ui()


    def _theme(self):
        """Возвращает словарь текущей темы"""
        try:
            return self.parent.parent_window.theme_manager.current_theme
        except Exception:
            return {}

    def _apply_theme_styles(self):
        """Применяет стили текущей темы к виджетам вкладки"""
        t = self._theme()
        accent = t.get('accent', '#6c63ff')
        base = t.get('base', '#1a1a2e')
        border = t.get('border', '#2a2a4a')
        text = t.get('text', '#e4e4ef')
        surface = t.get('surface', '#16213e')

        self.country_name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 14px;
            color: {accent};
            padding: 3px;
            background-color: {base};
            border: 1px solid {accent};
            border-radius: 3px;
        """)

        self.detail_content.setStyleSheet(f"""
            QLabel {{
                background-color: {base};
                color: {text};
                padding: 8px;
                border: 1px solid {border};
                border-radius: 3px;
                font-size: 11px;
                line-height: 1.4;
            }}
        """)

        # Рамки для карты, флага и герба
        for lbl in (self.map_label, self.flag_label, self.coat_label):
            lbl.setStyleSheet(f"""
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 2px;
            """)

    def update_style(self):
        """Переприменяет стили текущей темы и перерисовывает информацию"""
        self._apply_theme_styles()
        if getattr(self, 'current_country', None) is not None:
            self.detail_content.setText(self.format_country_info(self.current_country))
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(3)
        scroll_layout.setContentsMargins(1, 1, 1, 1)
        scroll_widget.setLayout(scroll_layout)

        # Название страны
        self.country_name_label = QLabel()
        self.country_name_label.setMaximumHeight(30)
        self.country_name_label.setAlignment(Qt.AlignCenter)
        scroll_layout.addWidget(self.country_name_label)

        # Карта
        self.map_group = QGroupBox("🗺️ Карта")
        self.map_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                margin-top: 3px;
                padding-top: 3px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 5px;
                padding: 0 2px;
            }
        """)
        map_layout = QVBoxLayout()
        map_layout.setSpacing(2)
        map_layout.setContentsMargins(3, 3, 3, 3)
        self.map_label = ImageLabel()
        map_layout.addWidget(self.map_label)
        self.load_map_btn = QPushButton("📁 Загрузить карту")
        self.load_map_btn.setMaximumHeight(24)
        self.load_map_btn.clicked.connect(lambda: self.load_image("map"))
        map_layout.addWidget(self.load_map_btn)
        self.map_group.setLayout(map_layout)
        scroll_layout.addWidget(self.map_group)

        # Флаг и герб
        self.symbols_widget = QWidget()
        symbols_layout = QHBoxLayout()
        symbols_layout.setSpacing(5)
        symbols_layout.setContentsMargins(0, 0, 0, 0)
        self.symbols_widget.setLayout(symbols_layout)

        # Флаг
        flag_group = QGroupBox("🏁 Флаг")
        flag_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; }")
        flag_layout = QVBoxLayout()
        flag_layout.setSpacing(2)
        flag_layout.setContentsMargins(3, 3, 3, 3)
        self.flag_label = ImageLabel()
        flag_layout.addWidget(self.flag_label)
        self.load_flag_btn = QPushButton("📁 Загрузить")
        self.load_flag_btn.setMaximumHeight(24)
        self.load_flag_btn.clicked.connect(self._on_load_flag_clicked)
        flag_layout.addWidget(self.load_flag_btn)
        flag_group.setLayout(flag_layout)
        symbols_layout.addWidget(flag_group)

        # Герб
        coat_group = QGroupBox("🛡️ Герб")
        coat_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; }")
        coat_layout = QVBoxLayout()
        coat_layout.setSpacing(2)
        coat_layout.setContentsMargins(3, 3, 3, 3)
        self.coat_label = ImageLabel()
        coat_layout.addWidget(self.coat_label)
        self.load_coat_btn = QPushButton("📁 Загрузить")
        self.load_coat_btn.setMaximumHeight(24)
        self.load_coat_btn.clicked.connect(lambda: self.load_image("coat"))
        coat_layout.addWidget(self.load_coat_btn)
        coat_group.setLayout(coat_layout)
        symbols_layout.addWidget(coat_group)

        scroll_layout.addWidget(self.symbols_widget)

        # Информационный контент
        self.detail_content = QLabel()
        self.detail_content.setWordWrap(True)
        self.detail_content.setTextFormat(Qt.RichText)
        self.detail_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        scroll_layout.addWidget(self.detail_content)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Применяем стили текущей темы
        self._apply_theme_styles()

    def get_image_path(self, country_id, image_type):
        """Путь к изображению страны в custom_images (герб, карта, копия флага)"""
        from utils.paths import paths
        custom_images_dir = paths.get_data_dir() / "custom_images"
        custom_images_dir.mkdir(parents=True, exist_ok=True)
        return custom_images_dir / f"country_{country_id}_{image_type}.png"
    
    def load_image(self, image_type):
        """Загружает изображение для страны.
        ФЛАГ дополнительно сохраняется в data/country_flags/{id}.png —
        единое хранилище для дерева, таблицы и карточки."""
        if not self.current_country_id:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*.*)")
        if not file_path:
            return
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Изображение", "Не удалось открыть файл изображения")
                return
            # === ФЛАГ сохраняем в ОБА хранилища ===
            if image_type == "flag":
                from utils.paths import paths
                main_dir = paths.get_data_dir() / "country_flags"
                main_dir.mkdir(parents=True, exist_ok=True)
                pixmap.save(str(main_dir / f"{self.current_country_id}.png"), "PNG")
            dest_path = self.get_image_path(self.current_country_id, image_type)
            pixmap.save(str(dest_path), "PNG")
            if image_type == "map":
                self.map_label.setPixmap(pixmap)
            elif image_type == "flag":
                self.flag_label.setPixmap(pixmap)
                self.flag_label.setStyleSheet("")
                self._refresh_flags_everywhere()
            elif image_type == "coat":
                self.coat_label.setPixmap(pixmap)
            self.logger.info(f"Загружено изображение: {dest_path}")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении: {e}")

    def _refresh_flags_everywhere(self):
        """Обновляет флаги в дереве стран и главной таблице"""
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if w.__class__.__name__ == 'MainWindow':
                tree = getattr(w, 'country_tree', None)
                if tree is not None and hasattr(tree, 'refresh_flags'):
                    tree.refresh_flags()
                tp = getattr(w, 'table_panel', None)
                if tp is not None:
                    if hasattr(tp, '_flag_icon_cache'):
                        tp._flag_icon_cache = {}
                    if hasattr(tp, '_render_page'):
                        tp._render_page()
                break

    def load_country_flag(self, country):
        """Заново опрашивает флаг страны:
        1) data/country_flags/{id}.png  2) custom_images.
        Если флага нет — лейбл полностью очищается."""
        self.flag_label.clear()
        pixmap = None
        try:
            from utils.flag_manager import flag_manager
            pixmap = flag_manager.get_pixmap(country.id, 120, 80)
        except Exception as e:
            self.logger.debug(f"flag_manager: {e}")
        if pixmap is None or pixmap.isNull():
            flag_path = self.get_image_path(country.id, "flag")
            if flag_path.exists():
                pixmap = QPixmap(str(flag_path))
        if pixmap and not pixmap.isNull():
            self.flag_label.setPixmap(pixmap)
        else:
            self.flag_label.setText("🏳️")
            self.flag_label.setStyleSheet("font-size: 48px; color: #999;")

    def load_country_map(self, country):
        """Заново опрашивает карту страны. Если карты нет — лейбл очищается."""
        self.map_label.clear()
        map_path = self.get_image_path(country.id, "map")
        if map_path.exists():
            pixmap = QPixmap(str(map_path))
            if not pixmap.isNull():
                self.map_label.setPixmap(pixmap)
                return
        self.map_label.setText("🗺️")
        self.map_label.setStyleSheet("font-size: 48px; color: #999;")

    def load_country_coat(self, country):
        """Заново опрашивает герб страны. Если герба нет — лейбл очищается."""
        self.coat_label.clear()
        coat_path = self.get_image_path(country.id, "coat")
        if coat_path.exists():
            pixmap = QPixmap(str(coat_path))
            if not pixmap.isNull():
                self.coat_label.setPixmap(pixmap)
                return
        self.coat_label.setText("🛡️")
        self.coat_label.setStyleSheet("font-size: 48px; color: #999;")



    def format_country_info(self, country):
        """Форматирует информацию о стране в HTML (цвета из текущей темы)"""
        t = self._theme()
        text = t.get('text', '#e4e4ef')
        muted = t.get('tab_text', '#8888aa')
        row_border = t.get('border', '#2a2a4a')
        error = t.get('error', '#dc3545')

        html = []
        html.append("<table style='width: 100%; border-collapse: collapse;'>")

        def add_row(label, value, icon="", default="—"):
            display_value = value if value and str(value).strip() else default
            html.append(f"""
<tr>
    <td style='padding: 4px; font-weight: bold; width: 40%; border-bottom: 1px solid {row_border}; color: {muted};'>{icon} {label}:</td>
    <td style='padding: 4px; border-bottom: 1px solid {row_border}; color: {text};'>{display_value}</td>
</tr>
""")

        add_row("Столица", country.capital, "🏛️")
        add_row("Континент", country.continent, "🌍")
        add_row("Форма правления", country.government_type, "⚖️")
        add_row("Официальный язык", country.language, "🗣️")
        add_row("Религия", country.religion, "⛪")
        if country.area:
            add_row("Территория", country.get_formatted_area(), "📐")
        else:
            add_row("Территория", None, "📐")
        if country.population:
            add_row("Население", country.get_formatted_population(), "👥")
        else:
            add_row("Население", None, "👥")
        currency = []
        if country.currency_name:
            currency.append(country.currency_name)
        if country.currency_code:
            currency.append(f"({country.currency_code})")
        if currency:
            add_row("Валюта", " ".join(currency), "💰")
        else:
            add_row("Валюта", None, "💰")
        codes = []
        if country.iso2:
            codes.append(f"ISO2: {country.iso2}")
        if country.iso3:
            codes.append(f"ISO3: {country.iso3}")
        if country.ioc_code:
            codes.append(f"МОК: {country.ioc_code}")
        if codes:
            add_row("Коды", " | ".join(codes), "🔢")
        else:
            add_row("Коды", None, "🔢")
        add_row("Независимость", country.independence_date, "📅")
        html.append("</table>")

        if country.is_extinct:
            html.append(f"<hr style='margin: 8px 0; border-color: {row_border};'>")
            html.append(f"<p style='color: {error}; font-weight: bold;'>💀 Исчезнувшая страна</p>")
            # ИСПРАВЛЕНО: используем правильный метод для получения преемников
            successors_display = country.get_successors_display()
            if successors_display:
                html.append(f"<p style='color: {text};'>→ Преемники: {successors_display}</p>")

        html.append(f"<hr style='margin: 8px 0; border-color: {row_border};'>")
        html.append(f"<p style='color: {muted}; font-size: 9px; margin: 2px 0;'>ID: {country.id}")
        if country.updated_at:
            html.append(f"<br>Обновлено: {country.updated_at.strftime('%Y-%m-%d %H:%M')}")
        html.append("</p>")

        return "".join(html)
        
    # ================= ФЛАГ СТРАНЫ =================
    def _flags_dir(self):
        """Каталог флагов: data/country_flags (синхронизируется с Google Drive)"""
        from utils.paths import paths
        d = paths.get_data_dir() / "country_flags"
        d.mkdir(parents=True, exist_ok=True)
        return d


    # ================= ФЛАГ СТРАНЫ =================
    def _update_flag_display(self):
        """Показывает флаг текущей страны из data/country_flags/{id}.png"""
        cid = getattr(self.current_country, 'id', None) if self.current_country else None
        if not cid or not hasattr(self, 'flag_label'):
            return
        from utils.flag_manager import flag_manager
        pix = flag_manager.get_pixmap(cid, 60, 40)
        if pix:
            self.flag_label.setPixmap(pix)
            self.flag_label.setText("")
        else:
            self.flag_label.clear()
            self.flag_label.setText("🏳️")

    def _on_load_flag_clicked(self):
        """Кнопка «📁 Загрузить» у флага: выбирает файл из любого места,
        сохраняет в data/country_flags/{id}.png и обновляет флаг
        в карточке, дереве стран и главной таблице."""
        from PySide6.QtWidgets import QApplication, QMessageBox
        from utils.flag_manager import flag_manager
        cid = getattr(self.current_country, 'id', None) if self.current_country else None
        if not cid:
            QMessageBox.warning(self, "Флаг страны", "Сначала выберите страну")
            return
        if flag_manager.pick_and_save_flag(self, cid):
            self._update_flag_display()
            # Обновляем дерево стран и главную таблицу
            for w in QApplication.topLevelWidgets():
                if w.__class__.__name__ == 'MainWindow':
                    tree = getattr(w, 'country_tree', None)
                    if tree is not None and hasattr(tree, 'refresh_flags'):
                        tree.refresh_flags()
                    tp = getattr(w, 'table_panel', None)
                    if tp is not None:
                        if hasattr(tp, '_flag_icon_cache'):
                            tp._flag_icon_cache = {}
                        if hasattr(tp, '_render_page'):
                            tp._render_page()
                    break

    # ================= ОТОБРАЖЕНИЕ ИНФОРМАЦИИ =================
    def show_country_info(self, country):
        """Отображает информацию о стране.
        При КАЖДОМ выборе страны заново опрашивает флаг, карту и герб."""
        self.current_country = country
        if country is None:
            self.country_name_label.setText("")
            if hasattr(self, 'detail_content'):
                self.detail_content.setText("")
            self.flag_label.clear()
            self.map_label.clear()
            self.coat_label.clear()
            return

        self.country_name_label.setText(country.name or "")

        # === ЗАНОВО ОПРАШИВАЕМ ВСЕ КАРТИНКИ ДЛЯ ВЫБРАННОЙ СТРАНЫ ===
        self.load_country_flag(country)
        self.load_country_map(country)
        self.load_country_coat(country)

        # === Текстовая информация ===
        if hasattr(self, 'format_country_info') and hasattr(self, 'detail_content'):
            self.detail_content.setText(self.format_country_info(country))

        self.logger.info(f"Отображена информация о стране: {country.name}")

    def _update_flag_display(self):
        """Показывает флаг текущей страны в карточке (если файл есть)"""
        if not getattr(self, '_flag_row_ready', False):
            return
        from PySide6.QtCore import Qt

        cid = getattr(getattr(self, 'current_country', None), 'id', None)
        if not cid:
            self.flag_label.clear()
            return
        p = self._flags_dir() / f"{cid}.png"
        if p.exists():
            from PySide6.QtGui import QPixmap
            pix = QPixmap(str(p))
            if not pix.isNull():
                self.flag_label.setPixmap(
                    pix.scaled(56, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.flag_label.clear()