# ===== gui/widgets/notebook/__init__.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""Модуль заметок и задач (органайзер)"""

from .notebook_tab import NotebookTab
from .note_list import NoteListWidget
from .note_editor import NoteEditor
from .task_item import TaskItem
from .category_manager import CategoryManagerDialog
from .reminder_dialog import ReminderDialog

__all__ = [
    'NotebookTab',
    'NoteListWidget',
    'NoteEditor',
    'TaskItem',
    'CategoryManagerDialog',
    'ReminderDialog'
]