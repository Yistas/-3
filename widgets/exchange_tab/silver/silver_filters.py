# -*- coding: utf-8 -*-

"""
Фильтрация для вкладки продажи серебра
"""

from .silver_model import STATUS_NAMES


class SilverFiltersMixin:
    """Примесь с методами фильтрации для серебра"""

    def _apply_filters(self):
        """Применяет фильтры и обновляет отображение"""
        if self._updating:
            return
        self._updating = True
        try:
            # Сохраняем состояние раскрытия
            expanded_id = self.expanded_purchase_id
            # Применяем фильтры к каждой закупке
            self._filtered_purchases = []
            for purchase in self.purchases:
                filtered_coins = self._get_filtered_coins_for_purchase(purchase)
                if filtered_coins:
                    purchase['_filtered_coins'] = filtered_coins
                    self._filtered_purchases.append(purchase)
                else:
                    purchase['_filtered_coins'] = []
            # Перестраиваем UI
            self._rebuild_ui()
            # Восстанавливаем раскрытую закупку
            if expanded_id:
                self._expand_purchase(expanded_id)
            self._update_stats()
            # Безопасный доступ к виджетам (могут отсутствовать)
            filter_text = "Все"
            combo = getattr(self, 'filter_combo', None)
            if combo is not None:
                filter_text = combo.currentText()
            status = getattr(self, 'status_label', None)
            if status is not None:
                status.setText(f"📊 Закупок: {len(self._filtered_purchases)} | Фильтр: {filter_text}")
        finally:
            self._updating = False

    def _get_filtered_coins_for_purchase(self, purchase):
        """
        Возвращает список монет для закупки с учётом фильтра статуса и поиска.
        """
        filtered_coins = []

        for coin in purchase['coins']:
            # Фильтр по статусу
            if self.status_filter != "all" and coin['status'] != self.status_filter:
                continue

            # Поиск по тексту
            if self.search_text:
                search_lower = self.search_text.lower()
                match = False
                for field in ['country', 'denomination', 'notes']:
                    value = str(coin.get(field, ''))
                    if search_lower in value.lower():
                        match = True
                        break
                if not match and coin.get('year'):
                    if search_lower in str(coin['year']):
                        match = True
                if not match and coin.get('number'):
                    if search_lower in str(coin['number']):
                        match = True
                if not match:
                    continue

            filtered_coins.append(coin)

        return filtered_coins

    def _on_filter_changed(self):
        """Обработчик изменения фильтра статуса"""
        combo = getattr(self, 'filter_combo', None)
        if combo is None:
            return
        self.status_filter = combo.currentData()
        self._apply_filters()

    def _on_search_changed(self, text):
        """Обработчик изменения поиска"""
        self.search_text = text.strip().lower()
        self._apply_filters()

    def _clear_search(self):
        """Очищает поиск"""
        edit = getattr(self, 'search_edit', None)
        if edit is not None:
            edit.clear()
            edit.setFocus()
        self.search_text = ""
        self._apply_filters()

    def _on_show_archive_changed(self, state):
        """Обработчик переключения чекбокса 'Показать архив'"""
        self._show_archive = (state == Qt.Checked)
        self._apply_filters()