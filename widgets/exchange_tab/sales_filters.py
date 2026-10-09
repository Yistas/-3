# -*- coding: utf-8 -*-

"""
Фильтрация продаж (заглушка)
"""


class SalesFiltersMixin:
    """Примесь с методами фильтрации продаж"""
    
    def _show_header_filter_menu(self, position):
        pass
    
    def _update_filter_label(self):
        pass
    
    def _save_column_filters_to_json(self):
        pass
    
    def _load_column_filters_from_json(self):
        pass
    
    def _filter_by_value(self, col, value):
        pass
    
    def _filter_exclude_value(self, col, value):
        pass
    
    def _clear_all_filters(self):
        pass