# -*- coding: utf-8 -*-
"""
Сканирование полного листа A4 по сделке: НЕСКОЛЬКО изображений на сделку.
Файлы: data/temp/obmen_image/НИК_№ПОК_1.jpg, _2.jpg, _3.jpg …
Номер добавляется автоматически (следующий свободный). В диалоге виден
список сохранённых изображений сделки: просмотр, добавление, удаление.
"""
import logging
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFileDialog, QApplication,
                               QListWidget, QMessageBox)

from gui.widgets.coin_scanner import coin_scanner
from utils.paths import paths

LOGGER = logging.getLogger('CoinCollector.DealSheetScanner')

IMG_EXTS = ('.jpg', '.jpeg', '.png')


def get_obmen_image_dir() -> Path:
    """Каталог хранения сканов листов сделок."""
    d = paths.get_data_dir() / 'temp' / 'obmen_image'
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_part(s):
    """Убирает недопустимые символы имени файла, пробелы → '_'."""
    s = re.sub(r'[\\/:*?"<>|]', '', str(s or ''))
    s = re.sub(r'\s+', '_', s.strip())
    return s


def build_deal_filename(deal):
    """Базовое имя файла: №ПОК_НИК (без номера копии).
    Итоговые файлы: №ПОК_НИК_1.jpg, №ПОК_НИК_2.jpg, …"""
    nick = sanitize_part(getattr(deal, 'buyer', None) or
                         getattr(deal, 'nick', None) or '')
    num = sanitize_part(getattr(deal, 'number', None) or
                        getattr(deal, 'deal_number', None) or '')
    if num and nick:
        return f"{num}_{nick}"
    if num:
        return num
    if nick:
        return nick
    return f"deal_{getattr(deal, 'id', 0) or 0}"


def _parse_index(filename, base):
    """Извлекает номер копии из имени 'BASE_N.ext'; None если не подходит."""
    m = re.match(re.escape(base) + r'_(\d+)', filename, re.I)
    return int(m.group(1)) if m else None


def list_deal_images(deal):
    """Список существующих изображений сделки: [(номер, Path), ...] по номеру."""
    base = build_deal_filename(deal)
    items = []
    try:
        for p in get_obmen_image_dir().iterdir():
            if not p.is_file() or p.suffix.lower() not in IMG_EXTS:
                continue
            idx = _parse_index(p.name, base)
            if idx is not None:
                items.append((idx, p))
    except Exception as e:
        LOGGER.warning(f"Ошибка чтения каталога изображений: {e}")
    items.sort(key=lambda t: t[0])
    return items


def get_next_index(deal):
    """Следующий свободный номер копии (макс + 1; после удаления — без дыр не остаётся)."""
    items = list_deal_images(deal)
    return (max(i for i, _ in items) + 1) if items else 1


def deal_image_path(deal, index):
    """Полный путь изображения сделки с номером: НИК_№ПОК_<index>.jpg"""
    return get_obmen_image_dir() / f"{build_deal_filename(deal)}_{index}.jpg"


def scan_deal_sheet(deal, dpi=600, index=None):
    """Сканирует ПОЛНЫЙ лист A4 (rect=None) и сохраняет как НИК_№ПОК_<N>.jpg."""
    backend = coin_scanner.get_backend()
    if index is None:
        index = get_next_index(deal)
    out_path = deal_image_path(deal, index)
    raw = (Path(tempfile.gettempdir()) /
           f"deal_sheet_{build_deal_filename(deal)}_{index}.png")
    backend.scan_to_file(str(raw), dpi=dpi, rect=None)
    from PIL import Image
    im = Image.open(raw)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    im.save(out_path, quality=92, subsampling=0)
    raw.unlink(missing_ok=True)
    LOGGER.info(f"💾 Лист сделки сохранён: {out_path}")
    return out_path


def save_image_as_deal_sheet(deal, src_path, index=None):
    """Импортирует выбранный файл как новое изображение сделки НИК_№ПОК_<N>.jpg."""
    if index is None:
        index = get_next_index(deal)
    out_path = deal_image_path(deal, index)
    from PIL import Image
    im = Image.open(src_path)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    im.save(out_path, quality=92, subsampling=0)
    LOGGER.info(f"💾 Файл сохранён как изображение сделки: {out_path}")
    return out_path


class DealSheetScanDialog(QDialog):
    """Диалог сканирования листов сделки: превью + список изображений +
    добавление (скан/импорт) + удаление."""

    def __init__(self, deal, parent=None):
        super().__init__(parent)
        self.deal = deal
        self.logger = LOGGER
        self.last_saved = None
        self.setWindowTitle(f"Скан листов сделки: {build_deal_filename(deal)}")
        self.resize(780, 860)
        self._build_ui()
        self._refresh_list(select_last=True)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        base = build_deal_filename(self.deal)
        info = QLabel(
            f"Сделка: <b>{base}</b><br>"
            f"Каталог: <code>{get_obmen_image_dir()}</code><br>"
            f"Файлы: <b>{base}_1.jpg, {base}_2.jpg, …</b> — "
            f"номер добавляется автоматически")
        info.setWordWrap(True)
        lay.addWidget(info)

        self.prev = QLabel('Нет изображения')
        self.prev.setAlignment(Qt.AlignCenter)
        self.prev.setMinimumHeight(340)
        self.prev.setStyleSheet(
            'border: 1px solid #555; background: #222; color: #aaa;')
        lay.addWidget(self.prev)

        lay.addWidget(QLabel('Сохранённые изображения сделки:'))
        self.img_list = QListWidget()
        self.img_list.setMaximumHeight(110)
        self.img_list.currentRowChanged.connect(self._on_list_selected)
        lay.addWidget(self.img_list)
        self.count_label = QLabel('Изображений: 0')
        self.count_label.setStyleSheet('color: #666; font-size: 11px;')
        lay.addWidget(self.count_label)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton('📷 Сканировать лист A4')
        self.scan_btn.setToolTip('Добавить НОВОЕ изображение (номер +1)')
        self.scan_btn.clicked.connect(self._scan)
        btn_row.addWidget(self.scan_btn)
        self.pick_btn = QPushButton('📁 Выбрать файл…')
        self.pick_btn.setToolTip('Импортировать файл как новое изображение')
        self.pick_btn.clicked.connect(self._pick)
        btn_row.addWidget(self.pick_btn)
        self.del_btn = QPushButton('🗑 Удалить выбранное')
        self.del_btn.setToolTip('Удалить выбранный в списке файл')
        self.del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self.status = QLabel('Положите лист на стекло и нажмите '
                             '«📷 Сканировать лист A4» — файл получит '
                             'следующий номер.')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        ok_row = QHBoxLayout()
        ok_row.addStretch()
        self.ok_btn = QPushButton('✅ Готово')
        self.ok_btn.clicked.connect(self.accept)
        ok_row.addWidget(self.ok_btn)
        cancel_btn = QPushButton('Закрыть')
        cancel_btn.clicked.connect(self.reject)
        ok_row.addWidget(cancel_btn)
        lay.addLayout(ok_row)

    # ================= СПИСОК ИЗОБРАЖЕНИЙ =================
    def _refresh_list(self, select_last=False):
        items = list_deal_images(self.deal)
        self.img_list.blockSignals(True)
        self.img_list.clear()
        for idx, p in items:
            self.img_list.addItem(f"#{idx}: {p.name}")
        self.img_list.blockSignals(False)
        self.count_label.setText(f'Изображений: {len(items)}')
        if items:
            row = (self.img_list.count() - 1) if select_last else 0
            self.img_list.setCurrentRow(row)
            self._show_preview(items[row][1])
        else:
            self.prev.clear()
            self.prev.setText('Нет изображения')

    def _on_list_selected(self, row):
        items = list_deal_images(self.deal)
        if 0 <= row < len(items):
            self._show_preview(items[row][1])

    def _show_preview(self, path):
        pm = QPixmap(str(path)).scaled(
            700, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.prev.setPixmap(pm)

    # ================= ДЕЙСТВИЯ =================
    def _scan(self):
        nxt = get_next_index(self.deal)
        self.status.setText(f'⏳ Сканирование листа #{nxt}… закройте крышку.')
        QApplication.processEvents()
        try:
            path = scan_deal_sheet(self.deal, index=nxt)
            self.last_saved = path
            self.status.setText(f'✅ Сохранено: {path.name}')
            self._refresh_list(select_last=True)
        except Exception as e:
            self.status.setText(f'❌ Ошибка сканирования: {e}')
            self.logger.error(f"Ошибка скана листа сделки: {e}")

    def _pick(self):
        src, _ = QFileDialog.getOpenFileName(
            self, 'Изображение листа сделки', '',
            'Изображения (*.png *.jpg *.jpeg *.bmp)')
        if not src:
            return
        try:
            path = save_image_as_deal_sheet(self.deal, src)
            self.last_saved = path
            self.status.setText(f'✅ Сохранено: {path.name}')
            self._refresh_list(select_last=True)
        except Exception as e:
            self.status.setText(f'❌ Ошибка сохранения: {e}')

    def _delete_selected(self):
        row = self.img_list.currentRow()
        items = list_deal_images(self.deal)
        if row < 0 or row >= len(items):
            self.status.setText('⚠️ Выберите изображение в списке для удаления.')
            return
        idx, path = items[row]
        reply = QMessageBox.question(
            self, 'Подтверждение', f'Удалить файл {path.name}?',
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            path.unlink(missing_ok=True)
            self.status.setText(f'🗑 Удалено: {path.name}')
            self._refresh_list(select_last=True)
        except Exception as e:
            self.status.setText(f'❌ Ошибка удаления: {e}')