# -*- coding: utf-8 -*-

"""
Сортировка и естественная сортировка для таблицы закупок
"""

import re


class PurchasesSortingMixin:
    """Примесь с методами сортировки закупок"""
    
    def _sort_purchases(self, purchases, sort_key):
        """Сортирует список закупок по указанному ключу"""
        if sort_key == "batch_asc":
            purchases.sort(key=lambda p: self._natural_sort_key(p.purchase_batch))
        elif sort_key == "batch_desc":
            purchases.sort(key=lambda p: self._natural_sort_key(p.purchase_batch), reverse=True)
        elif sort_key == "number_asc":
            purchases.sort(key=lambda p: self._natural_sort_key(p.purchase_number))
        elif sort_key == "number_desc":
            purchases.sort(key=lambda p: self._natural_sort_key(p.purchase_number), reverse=True)
        elif sort_key == "country_asc":
            purchases.sort(key=lambda p: (p.import_country.name or "").lower())
        elif sort_key == "country_desc":
            purchases.sort(key=lambda p: (p.import_country.name or "").lower(), reverse=True)
        elif sort_key == "continent_asc":
            purchases.sort(key=lambda p: (p.continent or "").lower())
        elif sort_key == "continent_desc":
            purchases.sort(key=lambda p: (p.continent or "").lower(), reverse=True)
        elif sort_key == "denom_asc":
            purchases.sort(key=lambda p: (p.denomination_value or "").lower())
        elif sort_key == "denom_desc":
            purchases.sort(key=lambda p: (p.denomination_value or "").lower(), reverse=True)
        elif sort_key == "currency_asc":
            purchases.sort(key=lambda p: (p.currency or "").lower())
        elif sort_key == "currency_desc":
            purchases.sort(key=lambda p: (p.currency or "").lower(), reverse=True)
        elif sort_key == "year_asc":
            purchases.sort(key=lambda p: p.year or 0)
        elif sort_key == "year_desc":
            purchases.sort(key=lambda p: p.year or 0, reverse=True)
        elif sort_key == "price_asc":
            purchases.sort(key=lambda p: p.collection_price or 0)
        elif sort_key == "price_desc":
            purchases.sort(key=lambda p: p.collection_price or 0, reverse=True)
        elif sort_key == "sum_asc":
            purchases.sort(key=lambda p: p.sold_sum or 0)
        elif sort_key == "sum_desc":
            purchases.sort(key=lambda p: p.sold_sum or 0, reverse=True)
        elif sort_key == "qty_asc":
            purchases.sort(key=lambda p: p.quantity or 0)
        elif sort_key == "qty_desc":
            purchases.sort(key=lambda p: p.quantity or 0, reverse=True)
        elif sort_key == "in_collection":
            purchases = [p for p in purchases if p.in_collection]
            purchases.sort(key=lambda p: p.collection_price or 0, reverse=True)
        elif sort_key == "on_exchange":
            purchases = [p for p in purchases if p.ucoin_exchange]
        return purchases
    
    def _natural_sort_key(self, value):
        """Естественная сортировка: 1, 2, 10, 100"""
        if value is None:
            return (1, 0, "", "")
        s = str(value).strip()
        if not s:
            return (1, 0, "", "")
        
        parts = re.split(r'(\d+)', s)
        
        result = []
        for part in parts:
            if part == '':
                continue
            if part.isdigit():
                result.append((0, int(part), '', ''))
            else:
                result.append((1, 0, part.lower(), part))
        
        if not result:
            return (1, 0, s.lower(), s)
        
        return result[0] if result else (1, 0, s.lower(), s)
    
    def _get_natural_sort_key(self, value):
        """Алиас для _natural_sort_key для обратной совместимости"""
        return self._natural_sort_key(value)