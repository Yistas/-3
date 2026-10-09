# -*- coding: utf-8 -*-

"""
Сортировка продаж (заглушка)
"""


class SalesSortingMixin:
    """Примесь с методами сортировки продаж"""
    
    def _sort_sales(self, sales, sort_key):
        return sales
    
    def _natural_sort_key(self, value):
        return value