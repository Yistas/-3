# -*- coding: utf-8 -*-

"""Диалоги для Coin Collector"""

from .add_country_dialog import AddCountryDialog
from .column_selector import ColumnSelectorDialog
from .backup_dialog import BackupDialog
from .currency_dialog import CurrencyDialog
from .mint_dialog import MintDialog
from .references_dialog import ReferencesDialog

# Импорт диалога печати из widgets/holder_label
try:
    from gui.widgets.holder_label import HolderLabelPreviewDialog
except ImportError:
    # Если модуль еще не создан, создаем заглушку
    HolderLabelPreviewDialog = None

__all__ = [
    'AddCountryDialog',
    'ColumnSelectorDialog',
    'BackupDialog',
    'CurrencyDialog',
    'MintDialog',
    'ReferencesDialog',
    'HolderLabelPreviewDialog'
]