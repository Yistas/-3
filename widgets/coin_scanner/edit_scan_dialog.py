# -*- coding: utf-8 -*-
"""
Диалог сканирования монеты из панели редактирования.
Не трогает разметку боковой панели: область скана, превью, повороты и
обмен сторон живут в отдельном окне. Автокроп первой монеты: +1 мм.
"""
import logging
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QComboBox, QApplication,
                               QGridLayout)

from gui.widgets.coin_scanner import coin_scanner

LOGGER = logging.getLogger('CoinCollector.EditScanDialog')

SCAN_AREAS = {
    '¼ листа — верх слева': (0.0, 0.0, 0.5, 0.5),
    '¼ листа — верх справа': (0.5, 0.0, 0.5, 0.5),
    '¼ листа — низ слева': (0.0, 0.5, 0.5, 0.5),
    '¼ листа — низ справа': (0.5, 0.5, 0.5, 0.5),
    '½ листа — верх': (0.0, 0.0, 1.0, 0.5),
    '½ листа — низ': (0.0, 0.5, 1.0, 0.5),
    'Весь лист (A4)': (0.0, 0.0, 1.0, 1.0),
}


class CoinEditScanDialog(QDialog):
    """Скан аверса/реверса с автокропом +1 мм; результат передаётся в форму."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = LOGGER
        self.images = {'obverse': None, 'reverse': None}
        self.setWindowTitle('Сканирование монеты (автокроп +1 мм)')
        self.setModal(True)
        self.resize(560, 460)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel('Область скана:'))
        self.area_combo = QComboBox()
        for name in SCAN_AREAS:
            self.area_combo.addItem(name)
        self.area_combo.setCurrentText('¼ листа — верх слева')
        self.area_combo.setToolTip('Часть планшета: четверть листа сканируется ~в 4 раза быстрее')
        top.addWidget(self.area_combo)
        top.addStretch()
        lay.addLayout(top)

        grid = QGridLayout()
        self.previews = {}
        for col, side in enumerate(('obverse', 'reverse')):
            title = QLabel('Аверс' if side == 'obverse' else 'Реверс')
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet('font-weight: bold; color: #4a6fa5;')
            grid.addWidget(title, 0, col)
            prev = QLabel('Нет изображения')
            prev.setFixedSize(220, 220)
            prev.setAlignment(Qt.AlignCenter)
            prev.setStyleSheet(
                'border: 1px solid #555; background: #222; color: #aaa;')
            self.previews[side] = prev
            grid.addWidget(prev, 1, col)
            row = QHBoxLayout()
            scan_btn = QPushButton('📷 Скан')
            scan_btn.clicked.connect(lambda _, s=side: self._scan(s))
            row.addWidget(scan_btn)
            rot_l = QPushButton('↺')
            rot_l.setFixedWidth(34)
            rot_l.setToolTip('Повернуть против часовой')
            rot_l.clicked.connect(lambda _, s=side: self._rotate(s, -90))
            row.addWidget(rot_l)
            rot_r = QPushButton('↻')
            rot_r.setFixedWidth(34)
            rot_r.setToolTip('Повернуть по часовой')
            rot_r.clicked.connect(lambda _, s=side: self._rotate(s, 90))
            row.addWidget(rot_r)
            grid.addLayout(row, 2, col)
        lay.addLayout(grid)

        mid = QHBoxLayout()
        swap_btn = QPushButton('🔄 Поменять местами')
        swap_btn.clicked.connect(self._swap)
        mid.addWidget(swap_btn)
        mid.addStretch()
        lay.addLayout(mid)

        self.status = QLabel('Положите монету на стекло и нажмите «📷 Скан».')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch()
        ok = QPushButton('✅ Применить к форме')
        ok.clicked.connect(self.accept)
        btns.addWidget(ok)
        cancel = QPushButton('❌ Отмена')
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    def _scan(self, side):
        rect = SCAN_AREAS.get(self.area_combo.currentText())
        self.status.setText(f'⏳ Сканирование ({self.area_combo.currentText()})… '
                            f'закройте крышку.')
        QApplication.processEvents()
        try:
            raw = Path(tempfile.gettempdir()) / f'edit_scan_{side}.png'
            backend = coin_scanner.get_backend()
            backend.scan_to_file(str(raw), dpi=600, rect=rect)
            out = Path(tempfile.gettempdir()) / f'edit_{side}_cropped.png'
            coin_scanner.crop_coin(str(raw), str(out), dpi=600, margin_mm=1.0)
            self.images[side] = str(out)
            self._update_preview(side)
            self.status.setText(f'✅ Сторона отсканирована и обрезана (+1 мм).')
        except Exception as e:
            self.status.setText(f'❌ Ошибка сканирования: {e}')
            self.logger.error(f"Ошибка сканирования ({side}): {e}")

    def _rotate(self, side, angle):
        path = self.images.get(side)
        if not path or not Path(path).exists():
            return
        try:
            from PIL import Image
            im = Image.open(path)
            im = im.rotate(-angle, expand=True)
            im.save(path)
            self._update_preview(side)
        except Exception as e:
            self.status.setText(f'❌ Ошибка поворота: {e}')

    def _swap(self):
        self.images['obverse'], self.images['reverse'] = (
            self.images['reverse'], self.images['obverse'])
        self._update_preview('obverse')
        self._update_preview('reverse')

    def _update_preview(self, side):
        path = self.images.get(side)
        lbl = self.previews[side]
        if path and Path(path).exists():
            pm = QPixmap(str(path)).scaled(210, 210, Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation)
            lbl.setPixmap(pm)
        else:
            lbl.clear()
            lbl.setText('Нет изображения')

    def get_results(self):
        """Возвращает (путь_аверса, путь_реверса) или None для пустых сторон."""
        return self.images.get('obverse'), self.images.get('reverse')