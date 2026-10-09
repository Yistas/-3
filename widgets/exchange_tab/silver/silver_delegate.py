# -*- coding: utf-8 -*-

"""
Делегат для таблицы монет серебра
"""

from PySide6.QtWidgets import QStyledItemDelegate, QComboBox, QCheckBox, QLineEdit, QStyle
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QColor

from .silver_model import STATUS_NAMES, STATUS_COMBO_COLORS


class SilverDelegate(QStyledItemDelegate):
    """Делегат для таблицы монет серебра"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_tab = None

    def set_parent_tab(self, tab):
        self._parent_tab = tab

    def createEditor(self, parent, option, index):
        col = index.column()
        # Статус - комбобокс
        if col == 0:
            combo = QComboBox(parent)
            combo.addItems(["В продаже", "Продана", "В коллекции"])
            # === ТЕКСТ БЕЗ ОБРЕЗКИ: ни в поле комбобокса, ни в выпадающем списке ===
            combo.view().setTextElideMode(Qt.ElideNone)
            combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            combo.currentIndexChanged.connect(lambda: self.commitData.emit(combo))
            return combo
        # Чекбоксы для колонок 8, 9, 10, 11 (Авито, LAVE, Мешок, UCOIN)
        if col in [8, 9, 10, 11]:
            checkbox = QCheckBox(parent)
            checkbox.stateChanged.connect(lambda: self.commitData.emit(checkbox))
            return checkbox
        # Остальные поля - текстовое поле
        editor = QLineEdit(parent)
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
        editor.selectAll()
        editor.setFocus()
        return editor

    def setEditorData(self, editor, index):
        col = index.column()

        if col == 0:
            value = index.data(Qt.DisplayRole) or "В продаже"
            editor.setCurrentText(value)
            return

        if col in [8, 9, 10, 11]:
            value = index.data(Qt.DisplayRole)
            editor.setChecked(value == "✅")
            return

        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)

    def setModelData(self, editor, model, index):
        col = index.column()

        if col == 0:
            value = editor.currentText()
            model.setData(index, value, Qt.EditRole)
            return

        if col in [8, 9, 10, 11]:
            value = editor.isChecked()
            model.setData(index, value, Qt.EditRole)
            return

        value = editor.text().strip()
        model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """Геометрия редакторов.
        ДЛЯ СТАТУСА (колонка 0): редактор-комбобокс расширяется до ширины
        самого длинного пункта («В коллекции») + стрелка/рамка — текст в поле
        и в выпадающем списке виден ПОЛНОСТЬЮ при ЛЮБОЙ ширине колонки.
        Остальные редакторы — по размеру ячейки."""
        if index.column() == 0 and isinstance(editor, QComboBox):
            fm = editor.fontMetrics()
            needed = 0
            for i in range(editor.count()):
                needed = max(needed, fm.horizontalAdvance(editor.itemText(i)))
            needed += 40   # стрелка, рамка, внутренние отступы
            extra = needed - option.rect.width()
            if extra > 0:
                editor.setGeometry(option.rect.adjusted(0, 0, extra, 0))
            else:
                editor.setGeometry(option.rect)
            return
        super().updateEditorGeometry(editor, option, index)

    def paint(self, painter, option, index):
        """Отрисовка с учетом цветов:
        - площадки (8–11): ОДИН индикатор ✅/❌ по центру;
        - статус (0): контрастная «таблетка» с тёмным текстом;
        - остальное: стандартная отрисовка с фоном строки.
        БЕЗ reentrancy-флагов: вложенная отрисовка не должна оставлять
        пустые ячейки."""
        col = index.column()
        # === ЧЕКБОКСЫ ПЛОЩАДОК: только эмодзи ===
        if col in [8, 9, 10, 11]:
            value = index.data(Qt.DisplayRole)
            painter.save()
            try:
                if option.state & QStyle.State_Selected:
                    painter.fillRect(option.rect, option.palette.highlight())
                else:
                    bg = index.data(Qt.BackgroundRole)
                    if bg:
                        painter.fillRect(option.rect, bg)
                font = painter.font()
                font.setPointSize(12)
                painter.setFont(font)
                if value == "✅":
                    painter.setPen(QColor("#28a745"))
                    painter.drawText(option.rect, Qt.AlignCenter, "✅")
                elif value == "❌":
                    painter.setPen(QColor("#dc3545"))
                    painter.drawText(option.rect, Qt.AlignCenter, "❌")
            except Exception:
                pass
            finally:
                painter.restore()
            return
        # === СТАТУС: яркая таблетка + чёрный текст ===
        if col == 0:
            value = index.data(Qt.DisplayRole) or "В продаже"
            color_hex = STATUS_COMBO_COLORS.get(value, "#ffffff")
            painter.save()
            try:
                if option.state & QStyle.State_Selected:
                    painter.fillRect(option.rect, option.palette.highlight())
                else:
                    bg = index.data(Qt.BackgroundRole)
                    if bg:
                        painter.fillRect(option.rect, bg)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(color_hex))
                rect = option.rect.adjusted(4, 3, -4, -3)
                painter.drawRoundedRect(rect, 4, 4)
                painter.setPen(QColor("#000000"))
                painter.drawText(rect, Qt.AlignCenter, value)
            except Exception:
                pass
            finally:
                painter.restore()
            return
        # === ОСТАЛЬНЫЕ КОЛОНКИ: стандарт + защита от исключений ===
        try:
            super().paint(painter, option, index)
        except Exception:
            painter.save()
            try:
                if option.state & QStyle.State_Selected:
                    painter.fillRect(option.rect, option.palette.highlight())
                    painter.setPen(option.palette.highlightedText().color())
                else:
                    bg = index.data(Qt.BackgroundRole)
                    if bg:
                        painter.fillRect(option.rect, bg)
                    painter.setPen(option.palette.text().color())
                text = str(index.data(Qt.DisplayRole) or "")
                painter.drawText(option.rect, Qt.AlignVCenter | Qt.AlignLeft,
                                 "  " + text)
            except Exception:
                pass
            finally:
                painter.restore()