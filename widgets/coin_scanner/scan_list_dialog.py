# -*- coding: utf-8 -*-
"""
Одно окно: сканирование двух сторон монеты (автокроп +5 мм) и выставление
лота на Meshok.ru. Название лота: Страна, Номинал, Валюта, Год.

Фото: кнопки поворота (↺/↻) и обмена сторон (🔄) вынесены в верхнюю
компактную панель. Поворот СОХРАНЯЕТСЯ В ФАЙЛ на диске, поэтому на Мешок
загружается именно повёрнутое фото.

Описание лота парсится со страницы, открытой в браузере закупок
(вкладка «Продажи»); в конец добавляется стандартный блок условий продажи.
Категория Meshok: автоматически (Монеты → Континент → Страна → лист).
Фото загружаются на Google Drive (публично) → параметр pictures метода listItem.
"""
import logging
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QFormLayout, QLineEdit,
                               QDoubleSpinBox, QMessageBox, QFileDialog,
                               QApplication, QTextEdit, QRadioButton,
                               QButtonGroup, QComboBox, QCheckBox)

from gui.widgets.coin_scanner import coin_scanner
from gui.widgets.coin_scanner.meshok_lister import MeshokLister
from utils.ucoin_description_finder import STANDARD_DESCRIPTION_HTML

# Области скана: доли планшета сканера (x, y, w, h)
SCAN_AREAS = {
    '¼ листа — верх слева': (0.0, 0.0, 0.5, 0.5),
    '¼ листа — верх справа': (0.5, 0.0, 0.5, 0.5),
    '¼ листа — низ слева': (0.0, 0.5, 0.5, 0.5),
    '¼ листа — низ справа': (0.5, 0.5, 0.5, 0.5),
    '½ листа — верх': (0.0, 0.0, 1.0, 0.5),
    '½ листа — низ': (0.0, 0.5, 1.0, 0.5),
    'Весь лист (A4)': (0.0, 0.0, 1.0, 1.0),
}
# Поле автокропа монеты (мм) — как в панели редактирования: +1 мм
CROP_MARGIN_MM = 1.0

BTN_STYLE = """
QPushButton {
    background-color: #262640; color: #e4e4ef;
    border: 1px solid #3d3d5c; border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover { background-color: #6c63ff; color: #ffffff; }
QPushButton:disabled { color: #5a5a7a; border-color: #2a2a4a; }
"""


class _PublishThread(QThread):
    """Публикация лота в фоновом потоке (не блокирует UI)."""
    finished = Signal(bool, str, object, str)   # ok, message, item_id, edit_url

    def __init__(self, lister, lot, sale_type, currency='RUB'):
        super().__init__()
        self.lister = lister
        self.lot = lot
        self.sale_type = sale_type
        self.currency = currency

    def run(self):
        ok, msg, item_id, edit_url = self.lister.publish_via_api(
            self.lot, category_id=None, sale_type=self.sale_type,
            city_id=None, currency=self.currency,
            country_name=self.lot.get('country', ''))
        self.finished.emit(ok, msg, item_id, edit_url or '')


class ScanAndListDialog(QDialog):
    """Сканирование монеты + выставление лота на Meshok."""

    def __init__(self, coin, db_manager, main_window, parent=None,
                 source=None, web_view=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.ScanList')
        self.coin = coin
        self.source = source or {}
        self.db = db_manager
        self.main_window = main_window
        self._web_view = web_view
        self.backend = coin_scanner.get_backend()
        self.dpi = 600
        self.images = {'obverse': None, 'reverse': None}
        self._scan_numbers = {}   # сторона → номер сканирования (для имён файлов)
        self._publish_thread = None
        self.setWindowTitle('Сканирование монеты и публикация на Meshok')
        self.resize(820, 700)
        self._build_ui()
        self._fill_lot_fields()
        self._parse_from_browser()

    # ================= UI =================
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"Сканер: <b>{self.backend.name}</b> | "
            f"Разрешение: {self.dpi} dpi | Автокроп: +{CROP_MARGIN_MM:.0f} мм"))

        # ===== ВЕРХНЯЯ КОМПАКТНАЯ ПАНЕЛЬ: область скана + кнопки фото =====
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        top_row.addWidget(QLabel('Область скана:'))
        self.area_combo = QComboBox()
        for name in SCAN_AREAS:
            self.area_combo.addItem(name)
        self.area_combo.setCurrentText('¼ листа — верх слева')
        self.area_combo.setToolTip(
            'Часть планшета для сканирования: четверть листа сканируется '
            'в ~4 раза быстрее. Кладите монеты в выбранный квартал.')
        top_row.addWidget(self.area_combo)
        top_row.addSpacing(8)

        # Кнопки поворота стороны 1
        self.rot_obv_ccw = QPushButton('↺')
        self.rot_obv_ccw.setFixedSize(30, 26)
        self.rot_obv_ccw.setStyleSheet(BTN_STYLE)
        self.rot_obv_ccw.setToolTip('Сторона 1: повернуть против часовой')
        self.rot_obv_ccw.clicked.connect(lambda: self._rotate_side('obverse', -90))
        top_row.addWidget(self.rot_obv_ccw)
        self.rot_obv_cw = QPushButton('↻')
        self.rot_obv_cw.setFixedSize(30, 26)
        self.rot_obv_cw.setStyleSheet(BTN_STYLE)
        self.rot_obv_cw.setToolTip('Сторона 1: повернуть по часовой')
        self.rot_obv_cw.clicked.connect(lambda: self._rotate_side('obverse', 90))
        top_row.addWidget(self.rot_obv_cw)

        # Обмен сторон местами
        self.swap_btn = QPushButton('🔄 A⇄R')
        self.swap_btn.setFixedSize(52, 26)
        self.swap_btn.setStyleSheet(BTN_STYLE)
        self.swap_btn.setToolTip('Поменять местами аверс и реверс')
        self.swap_btn.clicked.connect(self._swap_sides)
        top_row.addWidget(self.swap_btn)

        # Кнопки поворота стороны 2
        self.rot_rev_ccw = QPushButton('↺')
        self.rot_rev_ccw.setFixedSize(30, 26)
        self.rot_rev_ccw.setStyleSheet(BTN_STYLE)
        self.rot_rev_ccw.setToolTip('Сторона 2: повернуть против часовой')
        self.rot_rev_ccw.clicked.connect(lambda: self._rotate_side('reverse', -90))
        top_row.addWidget(self.rot_rev_ccw)
        self.rot_rev_cw = QPushButton('↻')
        self.rot_rev_cw.setFixedSize(30, 26)
        self.rot_rev_cw.setStyleSheet(BTN_STYLE)
        self.rot_rev_cw.setToolTip('Сторона 2: повернуть по часовой')
        self.rot_rev_cw.clicked.connect(lambda: self._rotate_side('reverse', 90))
        top_row.addWidget(self.rot_rev_cw)
        top_row.addStretch()
        lay.addLayout(top_row)

        # ===== БЛОК СКАНИРОВАНИЯ =====
        scan_group = QGroupBox('1. Отсканируйте две стороны монеты')
        gl = QHBoxLayout(scan_group)
        for side, title in (('obverse', 'Сторона 1 (аверс)'),
                            ('reverse', 'Сторона 2 (реверс)')):
            box = QVBoxLayout()
            prev = QLabel('Нет изображения')
            prev.setFixedSize(260, 260)
            prev.setAlignment(Qt.AlignCenter)
            prev.setStyleSheet(
                'border: 1px solid #555; background: #222; color: #aaa;')
            setattr(self, f'_prev_{side}', prev)
            box.addWidget(prev)
            btn = QPushButton(f'📷 Сканировать: {title}')
            btn.clicked.connect(lambda _, s=side: self._scan_side(s))
            box.addWidget(btn)
            fb = QPushButton('📁 Выбрать файл…')
            fb.clicked.connect(lambda _, s=side: self._pick_file(s))
            box.addWidget(fb)
            gl.addLayout(box)
        lay.addWidget(scan_group)

        # ===== БЛОК ДАННЫХ ЛОТА =====
        lot_group = QGroupBox('2. Данные лота')
        fl = QFormLayout(lot_group)
        self.title_edit = QLineEdit()
        fl.addRow('Название лота:', self.title_edit)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMinimumHeight(140)
        self.desc_edit.setMaximumHeight(220)
        fl.addRow('Описание:', self.desc_edit)
        ctrl_row = QHBoxLayout()
        self.parse_btn = QPushButton('📄 Описание со страницы')
        self.parse_btn.setToolTip(
            'Перечитать описание со страницы, открытой в браузере закупок')
        self.parse_btn.clicked.connect(self._parse_from_browser)
        ctrl_row.addWidget(self.parse_btn)
        self.preview_check = QCheckBox('👁 Предпросмотр (вид на Meshok)')
        self.preview_check.setChecked(True)
        self.preview_check.toggled.connect(self._toggle_preview)
        ctrl_row.addWidget(self.preview_check)
        ctrl_row.addStretch()
        fl.addRow('', ctrl_row)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 10_000_000)
        self.price_spin.setDecimals(0)
        self.price_spin.setSuffix(' ₽')
        fl.addRow('Цена:', self.price_spin)

        type_row = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        self.type_auction = QRadioButton('🔨 Аукцион')
        self.type_auction.setChecked(True)
        self.type_group.addButton(self.type_auction, 0)
        type_row.addWidget(self.type_auction)
        self.type_fixed = QRadioButton('💰 Фикс. цена')
        self.type_group.addButton(self.type_fixed, 1)
        type_row.addWidget(self.type_fixed)
        type_row.addStretch()
        fl.addRow('Тип продажи:', type_row)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(['RUB', 'USD', 'EUR'])
        self.currency_combo.setCurrentText('RUB')
        fl.addRow('Валюта:', self.currency_combo)
        lay.addWidget(lot_group)

        lay.addWidget(QLabel(
            '📄 Описание берётся со страницы монеты в браузере закупок; '
            'в конец добавляются условия продажи.\n'
            '📂 Категория Meshok: автоматически (Монеты → Континент → '
            'Страна → лист). 📤 Фото загружаются на Google Drive.'))

        bl = QHBoxLayout()
        self.next_btn = QPushButton('Далее →')
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next)
        bl.addWidget(self.next_btn)
        self.publish_btn = QPushButton('🚀 Опубликовать через API Meshok')
        self.publish_btn.setEnabled(False)
        self.publish_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "font-weight: bold; padding: 6px 12px; border-radius: 4px; }"
            "QPushButton:disabled { background-color: #555; }"
            "QPushButton:hover:!disabled { background-color: #2ecc71; }")
        self.publish_btn.clicked.connect(self._on_publish)
        bl.addWidget(self.publish_btn)
        self.fallback_btn = QPushButton('📄 Форма вручную')
        self.fallback_btn.setEnabled(False)
        self.fallback_btn.clicked.connect(self._on_fallback)
        bl.addWidget(self.fallback_btn)
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.reject)
        bl.addWidget(close_btn)
        lay.addLayout(bl)

        self.status = QLabel(
            'Положите монету на стекло сканера и нажмите «Сканировать».')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)


    # ================= ЛОКАЛЬНЫЕ КОПИИ ФОТО (obmen_image_meshok) =================
    def _get_meshok_image_dir(self):
        """Каталог локальных копий фото лотов: data/temp/obmen_image_meshok/"""
        from utils.paths import paths
        d = paths.get_data_dir() / 'temp' / 'obmen_image_meshok'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _place_part(self):
        """МЕСТО из данных закупки (или монеты) → безопасная часть имени файла."""
        s = self.source or {}
        place = str(s.get('location_found') or '').strip()
        if not place and self.coin is not None:
            place = str(getattr(self.coin, 'location_found', '') or '').strip()
        place = re.sub(r'[\\/:*?"<>|]', '', place)
        place = re.sub(r'\s+', '_', place)
        return place or 'scan'

    def _next_scan_number(self, place):
        """Следующий свободный номер сканирования для данного МЕСТА
        (максимум существующих номеров в каталоге + 1)."""
        d = self._get_meshok_image_dir()
        nums = []
        try:
            for p in d.iterdir():
                if not p.is_file():
                    continue
                m = re.match(re.escape(place) + r'_(\d+)', p.name, re.I)
                if m:
                    nums.append(int(m.group(1)))
        except Exception:
            pass
        return (max(nums) + 1) if nums else 1

    def _save_local_copy(self, side, src_path):
        """Сохраняет копию фото стороны в obmen_image_meshok/МЕСТО_номер.jpg.
        Номер выдаётся один раз на сторону в этой сессии: повторный скан
        той же стороны перезаписывает её файл, а не плодит новые."""
        try:
            place = self._place_part()
            num = self._scan_numbers.get(side)
            if num is None:
                num = self._next_scan_number(place)
                self._scan_numbers[side] = num
            out = self._get_meshok_image_dir() / f"{place}_{num}.jpg"
            from PIL import Image
            im = Image.open(src_path)
            if im.mode != 'RGB':
                im = im.convert('RGB')
            im.save(out, quality=92, subsampling=0)
            self.logger.info(f"💾 Локальная копия фото: {out}")
            return out
        except Exception as e:
            self.logger.warning(f"Не удалось сохранить локальную копию фото: {e}")
            return None

    # ================= РАБОТА С ФОТО =================
    def _update_preview(self, side):
        """Обновляет превью стороны из текущего файла на диске."""
        label = getattr(self, f'_prev_{side}')
        path = self.images.get(side)
        if path and Path(path).exists():
            pm = QPixmap(str(path)).scaled(
                250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(pm)
        else:
            label.clear()
            label.setText('Нет изображения')

    def _rotate_side(self, side, angle):
        """Поворачивает сторону на ±90° И СОХРАНЯЕТ ФАЙЛ НА ДИСКЕ,
        чтобы на Meshok загружалось именно повёрнутое фото."""
        path = self.images.get(side)
        if not path or not Path(path).exists():
            self.status.setText('⚠️ Сначала отсканируйте или выберите файл '
                                'для этой стороны.')
            return
        try:
            from PIL import Image
            im = Image.open(path)
            im = im.rotate(-angle, expand=True)   # angle>0 → по часовой
            im.save(path)                          # <-- СОХРАНЕНИЕ В ФАЙЛ
            self._update_preview(side)
            self.status.setText(f'✅ Сторона повёрнута на {angle}° '
                                f'(сохранено в файл).')
        except Exception as e:
            self.status.setText(f'❌ Ошибка поворота: {e}')
            self.logger.error(f"Ошибка поворота: {e}")

    def _swap_sides(self):
        """Меняет местами аверс и реверс (пути файлов + превью)."""
        if not (self.images.get('obverse') or self.images.get('reverse')):
            self.status.setText('⚠️ Нет изображений для обмена местами.')
            return
        self.images['obverse'], self.images['reverse'] = (
            self.images['reverse'], self.images['obverse'])
        self._update_preview('obverse')
        self._update_preview('reverse')
        self.status.setText('✅ Аверс и реверс поменяны местами.')

    # ================= ОПИСАНИЕ =================
    def _set_description(self, text):
        self._desc_source = text
        if self.preview_check.isChecked():
            self.desc_edit.setReadOnly(True)
            self.desc_edit.setHtml(text)
        else:
            self.desc_edit.setReadOnly(False)
            self.desc_edit.setPlainText(text)

    def _toggle_preview(self, checked):
        if checked:
            if not self.desc_edit.isReadOnly():
                self._desc_source = self.desc_edit.toPlainText()
            self.desc_edit.setReadOnly(True)
            self.desc_edit.setHtml(getattr(self, '_desc_source', ''))
        else:
            self.desc_edit.setReadOnly(False)
            self.desc_edit.setPlainText(getattr(self, '_desc_source', ''))

    def _fill_lot_fields(self):
        if self.coin is not None:
            c = self.coin
            country = getattr(getattr(c, 'country', None), 'name', '') or ''
            denom = getattr(c, 'denomination_value', '') or ''
            currency = (getattr(c, 'currency', '') or
                        getattr(getattr(c, 'currency_obj', None), 'name', '') or '')
            year = getattr(c, 'year', '') or ''
            desc = getattr(c, 'description', '') or ''
            price = (getattr(c, 'market_price', None)
                     or getattr(c, 'sale_price', None)
                     or getattr(c, 'purchase_price', None) or 0)
        else:
            s = self.source
            country = s.get('country', '') or ''
            denom = s.get('denomination', '') or ''
            currency = s.get('currency', '') or ''
            year = s.get('year', '') or ''
            desc = s.get('description', '') or ''
            price = s.get('price', 0) or 0
        parts = [str(x) for x in (country, denom, currency, year)
                 if x not in (None, '')]
        self.title_edit.setText(', '.join(parts))
        try:
            self.price_spin.setValue(float(price))
        except Exception:
            self.price_spin.setValue(0)
        # Сохраняем артикул для последующей вставки в описание
        self._internal_id = ''
        if self.coin is not None:
            pass  # у монеты коллекции артикула нет
        else:
            self._internal_id = str(self.source.get('internal_id') or '').strip()
        self._set_description(desc or '')

    def _find_browser_view(self):
        try:
            et = getattr(self.main_window, 'exchange_tab', None)
            eb = getattr(et, 'embedded_browser', None)
            if eb is not None and hasattr(eb, 'get_current_web_view'):
                wv = eb.get_current_web_view()
                if wv is not None:
                    return wv
        except Exception:
            pass
        try:
            bt = getattr(self.main_window, 'browser_tab', None)
            if bt is not None and hasattr(bt, 'get_current_web_view'):
                return bt.get_current_web_view()
        except Exception:
            pass
        return None

    def _request_html(self, wv, callback):
        if hasattr(wv, 'toHtml'):
            try:
                wv.toHtml(callback)
                return True
            except Exception as e:
                self.logger.warning(f"toHtml у view не сработал: {e}")
        page = None
        try:
            p = getattr(wv, 'page', None)
            page = p() if callable(p) else p
        except Exception:
            page = None
        if page is not None and hasattr(page, 'toHtml'):
            try:
                page.toHtml(callback)
                return True
            except Exception as e:
                self.logger.warning(f"page().toHtml не сработал: {e}")
        if page is not None and hasattr(page, 'runJavaScript'):
            try:
                page.runJavaScript(
                    "document.documentElement.outerHTML", callback)
                return True
            except Exception as e:
                self.logger.warning(f"page().runJavaScript не сработал: {e}")
        if hasattr(wv, 'runJavaScript'):
            try:
                wv.runJavaScript(
                    "document.documentElement.outerHTML", callback)
                return True
            except Exception as e:
                self.logger.warning(f"runJavaScript у view не сработал: {e}")
        for attr in ('web_view', 'view', '_web_view', '_view',
                     'engine_view', '_engine_view', 'wv'):
            inner = getattr(wv, attr, None)
            if inner is not None and inner is not wv:
                return self._request_html(inner, callback)
        return False

    def _parse_from_browser(self):
        wv = self._web_view
        if wv is None:
            wv = self._find_browser_view()
            self._web_view = wv
        if wv is None:
            self.status.setText('⚠️ Браузер закупок не найден — '
                                'откройте страницу монеты и нажмите '
                                '«📄 Описание со страницы».')
            return
        self.status.setText('📄 Читаю описание с открытой страницы браузера…')
        QApplication.processEvents()
        if not self._request_html(wv, self._on_browser_html):
            self.logger.warning(
                f"Не удалось получить HTML: неподдерживаемый тип "
                f"web view: {type(wv).__name__}")
            self.status.setText('⚠️ Не удалось прочитать HTML страницы '
                                '(неподдерживаемый тип браузера).')

    def _on_browser_html(self, html):
        if not html:
            self.status.setText('⚠️ Страница пуста — описание не распарсено.')
            return
        from utils.ucoin_description_finder import (parse_coin_page,
                                                    build_description)
        data = {}
        try:
            data = parse_coin_page(html) or {}
        except Exception as e:
            self.logger.warning(f"Ошибка парсинга страницы: {e}")
        if not data or not (data.get('metal') or data.get('title')):
            self.status.setText('⚠️ На открытой странице нет данных монеты. '
                                'Откройте страницу монеты UCOIN в браузере '
                                'закупок и повторите.')
            return
        s = self.source or {}
        coin_country = (getattr(getattr(self.coin, 'country', None), 'name', '')
                        if self.coin else '')
        desc_html = build_description(
            data,
            fallback_country=s.get('country') or coin_country,
            fallback_year=s.get('year') or getattr(self.coin, 'year', ''),
            fallback_denomination=s.get('denomination') or
            getattr(self.coin, 'denomination_value', ''),
            internal_id=self.source.get('internal_id') if self.source else '')
        self._set_description(desc_html)
        if not self.title_edit.text().strip():
            parts = [str(x) for x in (data.get('country') or coin_country,
                                      data.get('denomination') or '',
                                      data.get('year') or '') if x]
            self.title_edit.setText(', '.join(parts))
        self.logger.info("✅ Описание распарсено со страницы браузера закупок")
        self.status.setText('✅ Описание взято с открытой страницы браузера.')

    # ================= СКАНИРОВАНИЕ =================
    def _scan_side(self, side):
        rect = SCAN_AREAS.get(self.area_combo.currentText())
        self.status.setText(
            f'⏳ Сканирование ({self.area_combo.currentText()})… '
            f'положите монету в выбранную область и закройте крышку.')
        QApplication.processEvents()
        try:
            raw = Path(tempfile.gettempdir()) / f'coin_scan_{side}.png'
            self.backend.scan_to_file(str(raw), dpi=self.dpi, rect=rect)
            out = Path(tempfile.gettempdir()) / f'coin_{side}_cropped.png'
            # Автокроп первой монеты: квадрат по контуру + 1 мм (как в панели редактирования)
            coin_scanner.crop_coin(str(raw), str(out), dpi=self.dpi,
                                   margin_mm=CROP_MARGIN_MM)
            self.images[side] = str(out)
            self._update_preview(side)
            # Локальная копия в obmen_image_meshok (МЕСТО_номер сканирования)
            local = self._save_local_copy(side, str(out))
            if local:
                self.status.setText(
                    f'✅ {side}: монета обрезана (+{CROP_MARGIN_MM:.0f} мм). '
                    f'Копия: {local.name}')
            else:
                self.status.setText(
                    f'✅ {side}: монета обрезана (+{CROP_MARGIN_MM:.0f} мм).')
        except Exception as e:
            self.status.setText(f'❌ Ошибка сканирования: {e}')
            self.logger.error(f"Ошибка сканирования: {e}")
        self._update_buttons()

    def _pick_file(self, side):
        src, _ = QFileDialog.getOpenFileName(
            self, 'Фото стороны монеты', '',
            'Изображения (*.png *.jpg *.jpeg *.bmp)')
        if not src:
            return
        out = Path(tempfile.gettempdir()) / f'coin_{side}_cropped.png'
        try:
            # Тот же автокроп +1 мм и для импортированного файла
            coin_scanner.crop_coin(src, str(out), dpi=self.dpi,
                                   margin_mm=CROP_MARGIN_MM)
        except Exception:
            out = Path(src)
        self.images[side] = str(out)
        self._update_preview(side)
        self._save_local_copy(side, str(out))
        self._update_buttons()
        
    def _update_buttons(self):
        ready = bool(self.images.get('obverse')) and bool(self.images.get('reverse'))
        self.next_btn.setEnabled(ready)

    def _on_next(self):
        self.publish_btn.setEnabled(True)
        self.fallback_btn.setEnabled(True)
        self.status.setText(
            '✅ Данные готовы. Нажмите «🚀 Опубликовать через API Meshok» '
            'или «📄 Форма вручную».')

    # ================= ПУБЛИКАЦИЯ =================
    def _on_publish(self):
        if self._publish_thread and self._publish_thread.isRunning():
            return
        if self.preview_check.isChecked():
            desc = getattr(self, '_desc_source', '')
        else:
            desc = self.desc_edit.toPlainText()
        title = self.title_edit.text().strip()
        if not desc.strip():
            desc = (f"<b>Продаю монету: {title}.</b>" if title else '') \
                + STANDARD_DESCRIPTION_HTML
            self._set_description(desc)
        elif not any(kw in desc for kw in ('Спасибо за внимание',
                                           'Оплату можно произвести')):
            desc += STANDARD_DESCRIPTION_HTML
            self._set_description(desc)
        lister = MeshokLister(self.main_window)
        lot = lister.prepare_lot(
            coin=self.coin,
            title=title,
            price=int(self.price_spin.value()),
            description=desc,
            obverse=self.images['obverse'],
            reverse=self.images['reverse'],
            source=self.source,
        )
        sale_type = ('auction' if self.type_auction.isChecked() else 'fixed')
        currency = self.currency_combo.currentText() or 'RUB'

        self.publish_btn.setEnabled(False)
        self.fallback_btn.setEnabled(False)
        self.status.setText('⏳ Публикация лота через API Meshok…')
        QApplication.processEvents()

        self._publish_thread = _PublishThread(lister, lot, sale_type, currency)
        self._publish_thread.finished.connect(self._on_publish_finished)
        self._publish_thread.start()

    def _on_publish_finished(self, ok, msg, item_id, edit_url):
        self.publish_btn.setEnabled(True)
        self.fallback_btn.setEnabled(True)
        if ok and item_id:
            self.status.setText(f'✅ Лот #{item_id} опубликован!')
            lister = MeshokLister(self.main_window)
            lister.open_edit_page(item_id)
            try:
                QApplication.clipboard().setText(
                    f'https://meshok.net/item/{item_id}')
            except Exception:
                pass
            QMessageBox.information(
                self, '✅ Лот опубликован на Meshok',
                f'{msg}\n\n'
                f'📋 Ссылка на лот скопирована в буфер.\n\n'
                f'📷 Фото сохранены локально:\n'
                f'• {self.images["obverse"]}\n'
                f'• {self.images["reverse"]}\n\n'
                f'Страница редактирования открыта во встроенном браузере — '
                f'прикрепите оба фото и опубликуйте лот.')
            self.accept()
        else:
            self.status.setText(f'❌ Публикация не удалась: {msg[:80]}…')
            QMessageBox.warning(
                self, 'Публикация не удалась',
                f'{msg}\n\n'
                f'Вы можете открыть форму создания лота вручную '
                f'(кнопка «📄 Форма вручную»).\n\n'
                f'Фото сохранены локально:\n'
                f'• {self.images["obverse"]}\n'
                f'• {self.images["reverse"]}')

    def _on_fallback(self):
        try:
            QApplication.clipboard().setText(self.title_edit.text().strip())
        except Exception:
            pass
        lister = MeshokLister(self.main_window)
        lister.open_create_page()
        QMessageBox.information(
            self, 'Форма создания лота',
            'Название лота скопировано в буфер обмена.\n\n'
            f'Фото сохранены локально:\n'
            f'• {self.images["obverse"]}\n'
            f'• {self.images["reverse"]}\n\n'
            '1) Вставьте название (Ctrl+V)\n'
            '2) Прикрепите оба фото\n'
            '3) Укажите цену и опубликуйте лот')
        self.accept()