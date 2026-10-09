# -*- coding: utf-8 -*-

"""
Делегат для редактирования ячеек таблицы сделок
"""

import logging
from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit, QCheckBox, QApplication, QStyle, QAbstractItemDelegate
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor


class DealsDelegate(QStyledItemDelegate):
    """Делегат для редактирования ячеек таблицы сделок"""

    # Колонки, которые являются чекбоксами
    CHECKBOX_COLUMNS = {
        5: 'reserve',   # Резерв
        6: 'collect',   # Собр
        7: 'scan',      # СКАН
        8: 'send',      # Отосл
        9: 'approve',   # Согл
        10: 'payment',  # Оплата
        11: 'check',    # Пров
        12: 'pack',     # Упак
        13: 'post',     # Почта
        14: 'arrived',  # ДОШЛО
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_tab = None
        self.logger = logging.getLogger('CoinCollector.GUI.DealsDelegate')

        # Флаг для предотвращения рекурсии
        self._editing = False

    def set_parent_tab(self, tab):
        """Устанавливает ссылку на родительскую вкладку"""
        self._parent_tab = tab

    def createEditor(self, parent, option, index):
        """Создаёт редактор для ячейки"""
        col = index.column()

        # Для чекбоксов создаём QCheckBox
        if col in self.CHECKBOX_COLUMNS:
            checkbox = QCheckBox(parent)
            checkbox.stateChanged.connect(lambda state: self.commitData.emit(checkbox))
            return checkbox

        # Для остальных полей — QLineEdit
        editor = QLineEdit(parent)

        # Получаем текущее значение
        current_text = index.data(Qt.DisplayRole) or ""

        # Устанавливаем текст без потери данных
        editor.setText(current_text)

        # Выделяем весь текст для удобства редактирования
        editor.selectAll()

        # Подключаем сигнал завершения редактирования
        editor.editingFinished.connect(lambda: self._commit_on_finish(editor, index))

        # Устанавливаем фокус
        editor.setFocus(Qt.OtherFocusReason)

        self.logger.debug(f"createEditor: col={col}, text='{current_text}'")
        return editor

    def _commit_on_finish(self, editor, index):
        """Обработчик завершения редактирования"""
        if not editor or self._editing:
            return

        self._editing = True
        try:
            self.logger.debug(f"_commit_on_finish: index={index.row()},{index.column()}")

            # Проверяем, что редактор всё ещё принадлежит таблице
            if not editor.parent() or editor.parent() != self._parent_tab.table:
                self.logger.debug("  Редактор уже не принадлежит таблице, пропускаем")
                return

            # Получаем новое значение
            new_value = editor.text().strip()
            old_value = index.data(Qt.DisplayRole) or ""

            self.logger.debug(f"  old='{old_value}', new='{new_value}'")

            if new_value != old_value:
                self.logger.debug("  Значение изменилось, фиксируем")
                # Сначала сохраняем данные через модель
                self.commitData.emit(editor)
            else:
                self.logger.debug("  Значение не изменилось")

            # Закрываем редактор ПОСЛЕ сохранения
            self._close_editor_after_save(editor, index)

        except Exception as e:
            self.logger.error(f"Ошибка в _commit_on_finish: {e}")
        finally:
            self._editing = False

    def _close_editor_after_save(self, editor, index):
        """Закрывает редактор после сохранения"""
        try:
            if editor and not editor.isHidden():
                self.closeEditor.emit(editor, QAbstractItemDelegate.EditFinished)
        except RuntimeError:
            pass
        except Exception as e:
            self.logger.debug(f"Ошибка при закрытии редактора: {e}")

    def setEditorData(self, editor, index):
        """Устанавливает данные в редактор из модели"""
        col = index.column()

        if col in self.CHECKBOX_COLUMNS:
            value = index.data(Qt.DisplayRole)
            editor.setChecked(value == "✅")
            return

        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
        self.logger.debug(f"setEditorData: col={col}, text='{text}'")

    def setModelData(self, editor, model, index):
        """Сохраняет данные из редактора в модель"""
        if self._editing:
            return

        col = index.column()
        self.logger.debug(f"setModelData: col={col}")

        if col in self.CHECKBOX_COLUMNS:
            new_value = "✅" if editor.isChecked() else "❌"
            self.logger.debug(f"  checkbox value='{new_value}'")
            model.setData(index, new_value, Qt.EditRole)
            return

        new_value = editor.text().strip()
        old_value = index.data(Qt.DisplayRole) or ""

        self.logger.debug(f"  new='{new_value}', old='{old_value}'")

        if new_value != old_value:
            model.setData(index, new_value if new_value else None, Qt.EditRole)

    def paint(self, painter, option, index):
        """Отрисовка ячеек с учетом чекбоксов"""
        col = index.column()

        if col in self.CHECKBOX_COLUMNS:
            value = index.data(Qt.DisplayRole)

            painter.save()

            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())

            if value == "✅":
                painter.setPen(QColor("#28a745"))
                font = painter.font()
                font.setPointSize(14)
                painter.setFont(font)
                painter.drawText(option.rect, Qt.AlignCenter, "✅")
            elif value == "❌":
                painter.setPen(QColor("#dc3545"))
                font = painter.font()
                font.setPointSize(14)
                painter.setFont(font)
                painter.drawText(option.rect, Qt.AlignCenter, "❌")
            else:
                painter.setPen(QColor("#999"))
                painter.drawText(option.rect, Qt.AlignCenter, "☐")

            painter.restore()
            return

        super().paint(painter, option, index)

    def sizeHint(self, option, index):
        col = index.column()
        if col in self.CHECKBOX_COLUMNS:
            return option.rect.size()
        return super().sizeHint(option, index)