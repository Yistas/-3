# ===== gui/widgets/detail_panel/coin_view.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ
# -*- coding: utf-8 -*-
"""
Виджет просмотра информации о монете (тёмная тема)
"""
import os
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QScrollArea, QGroupBox, QGridLayout, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from .base_panel import ImageSelector


class CoinViewWidget(QWidget):
    """Виджет просмотра информации о монете"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent
        self.db_manager = None
        self.current_coin = None
        self.custom_value_labels = {}
        self.logger = logging.getLogger('CoinCollector.GUI.CoinViewWidget')
        self.init_ui()

    # ---------- ТЕМА ----------
    def _theme(self):
        try:
            mw = self._main_window()
            if mw and hasattr(mw, 'theme_manager'):
                return mw.theme_manager.current_theme
        except Exception:
            pass
        return {}

    def _main_window(self):
        w = self.parent_tab
        while w is not None and not hasattr(w, 'get_coin_value'):
            w = w.parent()
        return w

    def init_ui(self):
        t = self._theme()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(3)
        scroll_layout.setContentsMargins(1, 1, 1, 1)
        scroll_widget.setLayout(scroll_layout)

        self.coin_empty_label = QLabel("Выберите монету в таблице")
        self.coin_empty_label.setAlignment(Qt.AlignCenter)
        self.coin_empty_label.setStyleSheet(
            f"color: {t.get('tab_text', '#8888aa')}; font-size: 11px; padding: 15px;"
        )
        scroll_layout.addWidget(self.coin_empty_label)

        self.coin_detail_container = QWidget()
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(3)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.coin_detail_container.setLayout(detail_layout)

        # Фотографии
        self._create_photos_section(detail_layout)

        # Контейнер для динамических полей
        self.custom_fields_container = QWidget()
        self.custom_fields_layout = QVBoxLayout()
        self.custom_fields_layout.setSpacing(3)
        self.custom_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_fields_container.setLayout(self.custom_fields_layout)
        detail_layout.addWidget(self.custom_fields_container)

        detail_layout.addStretch()
        scroll_layout.addWidget(self.coin_detail_container)
        self.coin_detail_container.hide()

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def _create_photos_section(self, parent_layout):
        from PySide6.QtWidgets import QSizePolicy
        photos_group = QGroupBox("📷 Фотографии")
        photos_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10px;
                margin-top: 2px;
                padding-top: 4px;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #7c74ff;
            }
        """)
        photos_layout = QHBoxLayout()
        photos_layout.setSpacing(8)
        photos_layout.setContentsMargins(6, 6, 6, 6)

        # Аверс — растягивается на половину ширины
        obverse_layout = QVBoxLayout()
        obverse_layout.setSpacing(3)
        obverse_label = QLabel("Аверс")
        obverse_label.setAlignment(Qt.AlignCenter)
        obverse_label.setStyleSheet("font-weight: bold; font-size: 10px; color: #7c74ff;")
        obverse_layout.addWidget(obverse_label)
        self.view_obverse_image = ImageSelector(self, "аверса", editable=False)
        self.view_obverse_image.setMinimumSize(120, 150)
        self.view_obverse_image.setMaximumSize(16777215, 16777215)
        self.view_obverse_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view_obverse_image.setCursor(Qt.PointingHandCursor)
        self.view_obverse_image.setToolTip("Левая кнопка — просмотр | Правая кнопка — редактирование")
        self.view_obverse_image.mousePressEvent = self.create_image_click_handler('obverse')
        obverse_layout.addWidget(self.view_obverse_image, 1)
        photos_layout.addLayout(obverse_layout, 1)

        # Реверс — растягивается на вторую половину
        reverse_layout = QVBoxLayout()
        reverse_layout.setSpacing(3)
        reverse_label = QLabel("Реверс")
        reverse_label.setAlignment(Qt.AlignCenter)
        reverse_label.setStyleSheet("font-weight: bold; font-size: 10px; color: #7c74ff;")
        reverse_layout.addWidget(reverse_label)
        self.view_reverse_image = ImageSelector(self, "реверса", editable=False)
        self.view_reverse_image.setMinimumSize(120, 150)
        self.view_reverse_image.setMaximumSize(16777215, 16777215)
        self.view_reverse_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view_reverse_image.setCursor(Qt.PointingHandCursor)
        self.view_reverse_image.setToolTip("Левая кнопка — просмотр | Правая кнопка — редактирование")
        self.view_reverse_image.mousePressEvent = self.create_image_click_handler('reverse')
        reverse_layout.addWidget(self.view_reverse_image, 1)
        photos_layout.addLayout(reverse_layout, 1)

        photos_group.setLayout(photos_layout)
        parent_layout.addWidget(photos_group)

    def create_image_click_handler(self, side):
        """Создает обработчик клика для изображения (ЛКМ — просмотр, ПКМ — редактирование)"""
        import os
        from pathlib import Path
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QMessageBox

        def handler(event):
            coin = self.parent_tab.current_coin
            if not coin:
                return
            from utils.paths import paths
            root_dir = paths.get_root_dir()
            # Получаем пути к изображениям и преобразуем их в абсолютные
            obverse_path = getattr(coin, 'obverse_image', None) or ""
            reverse_path = getattr(coin, 'reverse_image', None) or ""

            def resolve_path(path):
                if not path:
                    return ""
                if Path(path).is_absolute():
                    return str(path)
                possible_paths = [
                    root_dir / path,
                    root_dir / "system_data" / path,
                    root_dir / "data" / path,
                    Path(path),
                ]
                for possible in possible_paths:
                    if possible.exists():
                        return str(possible)
                return path

            obverse_abs = resolve_path(obverse_path)
            reverse_abs = resolve_path(reverse_path)
            self.logger.info(f"🖱️ Клик по {side}: obverse={obverse_abs}, reverse={reverse_abs}")

            if event.button() == Qt.LeftButton:
                # Левая кнопка — просмотр в полном размере
                from gui.dialogs.image_viewer_dialog import ImageViewerDialog
                obv = QPixmap(obverse_abs) if obverse_abs and os.path.exists(obverse_abs) else None
                rev = QPixmap(reverse_abs) if reverse_abs and os.path.exists(reverse_abs) else None
                if not obv and obverse_path and os.path.exists(obverse_path):
                    obv = QPixmap(obverse_path)
                if not rev and reverse_path and os.path.exists(reverse_path):
                    rev = QPixmap(reverse_path)
                # Если всё ещё нет изображения, ищем в папке coin_images
                if (not obv or obv.isNull()) and coin.id:
                    coin_images_dir = paths.get_data_dir() / "coin_images"
                    for possible in [
                        coin_images_dir / f"coin_{coin.id}_obverse.png",
                        coin_images_dir / f"coin_{coin.id}_obverse.jpg",
                        coin_images_dir / f"coin_{coin.id}_obverse.jpeg",
                    ]:
                        if possible.exists():
                            obv = QPixmap(str(possible))
                            self.logger.info(f"  ✅ Найден аверс в coin_images: {possible}")
                            break
                if (not rev or rev.isNull()) and coin.id:
                    coin_images_dir = paths.get_data_dir() / "coin_images"
                    for possible in [
                        coin_images_dir / f"coin_{coin.id}_reverse.png",
                        coin_images_dir / f"coin_{coin.id}_reverse.jpg",
                        coin_images_dir / f"coin_{coin.id}_reverse.jpeg",
                    ]:
                        if possible.exists():
                            rev = QPixmap(str(possible))
                            self.logger.info(f"  ✅ Найден реверс в coin_images: {possible}")
                            break
                if (not obv or obv.isNull()) and (not rev or rev.isNull()):
                    self.logger.warning("  ❌ Нет изображений для отображения")
                    QMessageBox.warning(self, "Предупреждение", "Нет изображений для просмотра")
                    return
                viewer = ImageViewerDialog(obv, rev, "Просмотр изображения", self)
                if side == 'obverse' and obv and not obv.isNull():
                    viewer.switch_side('obverse')
                elif side == 'reverse' and rev and not rev.isNull():
                    viewer.switch_side('reverse')
                viewer.exec()

            elif event.button() == Qt.RightButton:
                # Правая кнопка — редактирование
                from gui.widgets.detail_panel.image_editor import ImageEditorDialog
                dialog = ImageEditorDialog(obverse_abs, reverse_abs, self)
                if side == 'obverse':
                    dialog.set_current_side('obverse')
                else:
                    dialog.set_current_side('reverse')
                if dialog.exec():
                    new_obverse = dialog.get_obverse_pixmap()
                    new_reverse = dialog.get_reverse_pixmap()
                    changed = False
                    if new_obverse and not new_obverse.isNull():
                        images_dir = paths.get_data_dir() / "coin_images"
                        images_dir.mkdir(parents=True, exist_ok=True)
                        save_path = images_dir / f"coin_{coin.id}_obverse.png"
                        new_obverse.save(str(save_path))
                        rel_path = str(save_path.relative_to(paths.get_root_dir()))
                        coin.obverse_image = rel_path
                        self.view_obverse_image.set_image_from_path(str(save_path))
                        changed = True
                        self.logger.info(f"  ✅ Аверс сохранён: {rel_path}")
                    if new_reverse and not new_reverse.isNull():
                        images_dir = paths.get_data_dir() / "coin_images"
                        images_dir.mkdir(parents=True, exist_ok=True)
                        save_path = images_dir / f"coin_{coin.id}_reverse.png"
                        new_reverse.save(str(save_path))
                        rel_path = str(save_path.relative_to(paths.get_root_dir()))
                        coin.reverse_image = rel_path
                        self.view_reverse_image.set_image_from_path(str(save_path))
                        changed = True
                        self.logger.info(f"  ✅ Реверс сохранён: {rel_path}")
                    if changed and hasattr(self, 'db_manager') and self.db_manager:
                        from datetime import datetime
                        coin.updated_at = datetime.now()
                        self.db_manager.session.commit()
                        QMessageBox.information(self, "Успех", "Изображение обновлено")
                    self.update_display(coin, self.db_manager)

        return handler

    def _make_image_handler(self, side):
        def handler(event):
            coin = self.current_coin
            if not coin:
                return
            if event.button() == Qt.LeftButton:
                from gui.dialogs.image_viewer_dialog import ImageViewerDialog
                obv = self._load_pixmap(getattr(coin, 'obverse_image', None))
                rev = self._load_pixmap(getattr(coin, 'reverse_image', None))
                if (not obv or obv.isNull()) and (not rev or rev.isNull()):
                    return
                viewer = ImageViewerDialog(obv, rev, "Просмотр изображения", self)
                if side == 'obverse' and obv and not obv.isNull():
                    viewer.switch_side('obverse')
                elif side == 'reverse' and rev and not rev.isNull():
                    viewer.switch_side('reverse')
                viewer.exec()
        return handler

    def _load_pixmap(self, path):
        if not path:
            return None
        if not os.path.isabs(path):
            from utils.paths import paths
            for base in (paths.get_root_dir(), paths.get_system_data_dir(), paths.get_data_dir()):
                candidate = base / path
                if candidate.exists():
                    path = str(candidate)
                    break
        if os.path.exists(path):
            return QPixmap(path)
        return None

    # ---------- ОТОБРАЖЕНИЕ ----------
    def update_display(self, coin, db_manager):
        self.db_manager = db_manager
        self.current_coin = coin

        # Очищаем динамические поля
        while self.custom_fields_layout.count():
            child = self.custom_fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.custom_value_labels.clear()

        if coin is None:
            self.coin_empty_label.show()
            self.coin_detail_container.hide()
            return

        self.coin_empty_label.hide()
        self.coin_detail_container.show()

        # Фотографии
        obv = self._load_pixmap(getattr(coin, 'obverse_image', None))
        rev = self._load_pixmap(getattr(coin, 'reverse_image', None))
        self.view_obverse_image.clear_image()
        self.view_reverse_image.clear_image()
        if obv and not obv.isNull():
            self.view_obverse_image.set_image_from_path(getattr(coin, 'obverse_image'))
        if rev and not rev.isNull():
            self.view_reverse_image.set_image_from_path(getattr(coin, 'reverse_image'))

        self._rebuild_fields(coin)

    def clear_view(self):
        """Очищает вид просмотра (вызывается из main_window и coin_tab)"""
        # Очищаем динамические поля
        if hasattr(self, 'custom_fields_layout'):
            while self.custom_fields_layout.count():
                child = self.custom_fields_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        if hasattr(self, 'custom_value_labels'):
            self.custom_value_labels.clear()
        # Очищаем фотографии
        if hasattr(self, 'view_obverse_image'):
            self.view_obverse_image.clear_image()
        if hasattr(self, 'view_reverse_image'):
            self.view_reverse_image.clear_image()
        # Показываем заглушку "Выберите монету"
        if hasattr(self, 'coin_empty_label'):
            self.coin_empty_label.show()
        if hasattr(self, 'coin_detail_container'):
            self.coin_detail_container.hide()

    def _get_value(self, coin, key, mw):
        try:
            if mw is not None:
                return mw.get_coin_value(coin, key)
        except Exception:
            pass
        return getattr(coin, key, None)

    def _rebuild_fields(self, coin):
        t = self._theme()
        if not self.db_manager:
            return
        try:
            fields = self.db_manager.get_all_field_settings()
        except Exception:
            fields = []
        fields = [f for f in fields if getattr(f, 'show_in_view', True)]

        categories = {}
        for f in fields:
            cat = f.category or "Основные"
            categories.setdefault(cat, []).append(f)

        order = ["Основные", "Монетный двор", "Характеристики", "Гурт",
                 "Состояние", "Покупка", "Рыночная цена", "Ссылки",
                 "Информация", "Дополнительные"]
        mw = self._main_window()

        for cat in order + [c for c in categories if c not in order]:
            if cat not in categories:
                continue
            group = QGroupBox(cat)
            grid = QGridLayout()
            grid.setSpacing(2)
            grid.setHorizontalSpacing(8)
            grid.setContentsMargins(8, 8, 8, 8)
            grid.setColumnStretch(1, 1)

            row = 0
            for f in sorted(categories[cat], key=lambda x: x.sort_order or 0):
                if f.field_key in ('select', 'flag', 'id'):
                    continue
                value = self._get_value(coin, f.field_key, mw)

                name_label = QLabel(f"{f.name}:")
                name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                name_label.setStyleSheet(
                    f"color: {t.get('tab_text', '#8888aa')}; font-size: 10px;"
                )

                value_label = QLabel()
                value_label.setWordWrap(True)
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
                value_label.setOpenExternalLinks(True)
                value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

                if f.field_key in ('ucoin_url', 'meshok_url') and value:
                    value_label.setText(f'<a href="{value}" style="color: {t.get("link", "#7c74ff")};">{value[:40]}...</a>')
                else:
                    value_label.setText(str(value) if value not in (None, "") else "—")
                value_label.setStyleSheet(f"color: {t.get('text', '#e4e4ef')}; font-size: 10px;")

                self.custom_value_labels[f.field_key] = value_label
                grid.addWidget(name_label, row, 0)
                grid.addWidget(value_label, row, 1)
                row += 1

            group.setLayout(grid)
            self.custom_fields_layout.addWidget(group)
            
    def rebuild_custom_fields(self):
        """Перестраивает поля просмотра (без группы 'Специальные')"""
        while self.custom_fields_layout.count():
            child = self.custom_fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.custom_value_labels.clear()
        if not self.db_manager:
            return
        field_settings = {f.field_key: f for f in self.db_manager.get_all_field_settings()}
        from gui.dialogs.column_selector import ColumnSelectorDialog
        categories = {}
        skip_fields = [
            'select', 'id', 'flag', 'currency', 'metal', 'purchase_country', 'status',
            'condition', 'rarity', 'shape', 'issue_type', 'avrev',
            'acquisition_type', 'storage_location',
        ]
        for col in ColumnSelectorDialog.STANDARD_COLUMNS:
            if col["key"] in skip_fields:
                continue
            settings = field_settings.get(col["key"])
            if settings:
                if not getattr(settings, 'show_in_view', True):
                    continue
                if not settings.show_in_form:
                    continue
            else:
                if not col.get("show_in_form", True):
                    continue
            field_name = settings.name if settings else col["name"]
            category = (settings.category if settings else col.get("category", "Основные")) or "Основные"
            # НЕ показываем группу "Специальные"
            if category.strip().lower() == "специальные":
                continue
            categories.setdefault(category, []).append({
                "field_key": col["key"],
                "name": field_name,
                "is_standard": True,
                "sort_order": settings.sort_order if settings else col.get("sort_order", 0)
            })
        if hasattr(self.parent_tab, 'custom_fields') and self.parent_tab.custom_fields:
            for field_dict in self.parent_tab.custom_fields:
                if not field_dict.get('show_in_form', True):
                    continue
                if not field_dict.get('show_in_view', True):
                    continue
                category = field_dict.get('category', 'Дополнительные') or "Дополнительные"
                if category.strip().lower() == "специальные":
                    continue
                categories.setdefault(category, []).append({
                    "field_key": field_dict['field_key'],
                    "name": field_dict['name'],
                    "is_standard": False,
                    "sort_order": field_dict.get('sort_order', 0)
                })
        category_order = ["Основные", "Монетный двор", "Характеристики", "Гурт",
                          "Состояние", "Покупка", "Рыночная цена", "Ссылки",
                          "Информация", "Дополнительные"]
        for category in category_order:
            if category in categories:
                self._add_category_group(category, categories[category])
        for category, fields in categories.items():
            if category not in category_order:
                self._add_category_group(category, fields)

    def _add_category_group(self, category_name, fields):
        """Добавляет группу полей для категории"""
        if not fields:
            return
        # НАДЁЖНО убираем группу "Специальные"
        if (category_name or "").strip().lower() == "специальные":
            return
        group = QGroupBox(category_name)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10px;
                margin-top: 2px;
                padding-top: 4px;
                border: 1px solid #2a2a4a;
                border-radius: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
                color: #7c74ff;
            }
        """)
        grid_layout = QGridLayout()
        grid_layout.setSpacing(2)
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(2)
        grid_layout.setContentsMargins(8, 8, 8, 8)
        grid_layout.setColumnStretch(0, 0)
        grid_layout.setColumnStretch(1, 1)
        sorted_fields = sorted(fields, key=lambda f: f.get("sort_order", 0))
        row = 0
        for field in sorted_fields:
            field_key = field["field_key"]
            field_name = field["name"]
            if field_key in self.custom_value_labels:
                continue
            label = QLabel(f"{field_name}:")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setWordWrap(False)
            label.setMinimumWidth(100)
            label.setStyleSheet("color: #8888aa;")
            grid_layout.addWidget(label, row, 0)
            value_label = QLabel()
            value_label.setWordWrap(True)
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setOpenExternalLinks(True)
            value_label.setStyleSheet("color: #e4e4ef;")
            grid_layout.addWidget(value_label, row, 1)
            self.custom_value_labels[field_key] = value_label
            row += 1
        group.setLayout(grid_layout)
        self.custom_fields_layout.addWidget(group)

    def update_dynamic_fields(self, coin):
        """Заполняет динамические поля значениями из монеты"""
        if not coin:
            return
        from database.models import StandardReference
        status_refs = {}
        try:
            refs = self.db_manager.session.query(StandardReference).filter_by(field_key='status').all()
            for ref in refs:
                status_refs[ref.value] = ref.name
        except Exception as e:
            self.logger.error(f"Ошибка загрузки справочника статусов: {e}")

        for field_key, label in self.custom_value_labels.items():
            value = None
            if field_key == "country":
                value = coin.country.name if coin.country else None
            elif field_key == "catalog_number":
                value = coin.catalog_number
            elif field_key == "denomination_value":
                value = coin.denomination_value
            elif field_key == "currency":
                value = coin.currency_obj.get_display_text() if coin.currency_obj else coin.currency
            elif field_key == "mint":
                value = coin.mint_obj.get_display_text() if coin.mint_obj else coin.mint
            elif field_key == "mint_mark":
                value = coin.mint_mark
            elif field_key == "year":
                value = str(coin.year) if coin.year else None
            elif field_key == "period":
                value = coin.period_obj.get_display_text() if hasattr(coin, 'period_obj') and coin.period_obj else None
            elif field_key == "century":
                value = getattr(coin, 'century', None)
            elif field_key == "metal":
                value = coin.metal_obj.get_display_text() if coin.metal_obj else None
            elif field_key == "weight":
                value = f"{coin.weight:.2f} г" if coin.weight else None
            elif field_key == "diameter":
                value = f"{coin.diameter:.2f} мм" if coin.diameter else None
            elif field_key == "shape":
                value = getattr(coin, 'shape', None)
            elif field_key == "edge":
                value = coin.edge_obj.name if hasattr(coin, 'edge_obj') and coin.edge_obj else None
            elif field_key == "edge_description":
                value = getattr(coin, 'edge_description', None)
            elif field_key == "condition":
                value = coin.condition
            elif field_key == "rarity":
                value = getattr(coin, 'rarity', None)
            elif field_key == "storage_location":
                value = getattr(coin, 'storage_location', None)
            elif field_key == "issue_type":
                value = getattr(coin, 'issue_type', None)
            elif field_key == "avrev":
                value = getattr(coin, 'avrev', None)
            elif field_key == "status":
                value = status_refs.get(coin.status, coin.status) if coin.status else None
            elif field_key == "purchase_date":
                value = coin.purchase_date.strftime("%d.%m.%Y") if coin.purchase_date else None
            elif field_key == "purchase_price":
                value = f"{coin.purchase_price:,.2f} ₽" if coin.purchase_price else None
            elif field_key == "purchase_where":
                value = getattr(coin, 'purchase_where', None)
            elif field_key == "purchase_country":
                value = coin.purchase_country_obj.name if hasattr(coin, 'purchase_country_obj') and coin.purchase_country_obj else None
            elif field_key == "acquisition_type":
                value = getattr(coin, 'acquisition_type', None)
            elif field_key == "purchase_info":
                value = getattr(coin, 'purchase_info', None)
            elif field_key == "sale_price":
                value = f"{coin.sale_price:,.2f} ₽" if coin.sale_price else None
            elif field_key == "market_price":
                value = f"{coin.market_price:,.2f} ₽" if coin.market_price else None
            elif field_key == "market_price_date":
                value = coin.market_price_date.strftime("%d.%m.%Y") if coin.market_price_date else None
            elif field_key == "coin_info":
                value = getattr(coin, 'coin_info', None) or getattr(coin, 'notes', None)
            elif field_key == "ucoin_url":
                value = getattr(coin, 'ucoin_url', None)
            elif field_key == "meshok_url":
                value = getattr(coin, 'meshok_url', None)
            else:
                # Пользовательские поля
                if hasattr(coin, 'custom_data') and coin.custom_data:
                    try:
                        import json
                        custom_data = json.loads(coin.custom_data)
                        value = custom_data.get(field_key)
                    except Exception:
                        pass
            if value:
                if isinstance(value, bool):
                    display_value = "✅ Да" if value else "❌ Нет"
                elif field_key in ("ucoin_url", "meshok_url"):
                    display_value = f'<a href="{value}" style="color: #4a6fa5;">{value[:50]}...</a>'
                    label.setTextFormat(Qt.RichText)
                elif isinstance(value, float):
                    display_value = f"{value:.2f}".replace('.', ',')
                else:
                    display_value = str(value)
                label.setText(display_value)
            else:
                label.setText("—")