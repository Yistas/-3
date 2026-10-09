# -*- coding: utf-8 -*-

"""
Методы MainWindow для загрузки монет и CRUD операций
"""

import traceback
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer
from sqlalchemy import or_
from database.models import Coin, Country, Currency, Mint, StandardReference


class CoinsMixin:
    """Примесь с методами загрузки и CRUD монет"""
    
    def load_coins(self):
        """Оптимизированная загрузка монет:
        - joinedload всех связей
        - фильтр по выбору в дереве стран
        - ЗАМОРАЖИВАНИЕ всех атрибутов в словари (защита от DetachedInstanceError)
        - БЕЗ тяжёлой статистики и двойного рендера (нет задержки при выборе страны)
        """
        if getattr(self, '_loading_coins', False):
            return
        self._loading_coins = True
        try:
            from database.models import Coin, Country, Metal, Currency, Mint, Edge, Period
            from sqlalchemy.orm import joinedload
            from sqlalchemy import inspect as sa_inspect

            self.logger.info("📥 Загрузка монет из БД (joinedload + freeze)...")

            # === Динамический список существующих relationship ===
            mapper = sa_inspect(Coin)
            rel_names = {rel.key for rel in mapper.relationships}
            wanted = ['country', 'currency', 'metal', 'metal_obj', 'mint', 'edge',
                      'condition_ref', 'rarity_ref', 'status_ref', 'shape_ref',
                      'issue_type_ref', 'avrev_ref', 'acquisition_type_ref',
                      'storage_location_ref', 'purchase_country_obj', 'period_ref', 'period']
            options = [joinedload(getattr(Coin, name)) for name in wanted if name in rel_names]

            query = self.db_manager.session.query(Coin).options(*options)

            # === ФИЛЬТР ПО ВЫБОРУ В ДЕРЕВЕ ===
            country_id = getattr(self, 'current_filter_country_id', None)
            folder_ids = getattr(self, 'current_folder_country_ids', None)

            if country_id:
                query = query.filter(Coin.country_id == country_id)
                self.logger.info(f"🔎 Фильтр: страна ID={country_id}")
            elif folder_ids:
                query = query.filter(Coin.country_id.in_(folder_ids))
                self.logger.info(f"🔎 Фильтр: список стран ({len(folder_ids)})")
            else:
                self.logger.info("🔎 Фильтр: вся коллекция")

            coins = query.all()
            session = self.db_manager.session

            # === Универсальный поиск связанного объекта по нескольким именам ===
            def rel_obj(obj, names):
                for n in names:
                    try:
                        v = getattr(obj, n, None)
                        if v is not None:
                            return v
                    except Exception:
                        continue
                return None

            # === ЗАМОРАЖИВАНИЕ: читаем ВСЕ атрибуты, пока объекты привязаны к сессии ===
            frozen = []
            for coin in coins:
                try:
                    d = {'_coin': coin, '_id': coin.id}

                    # Скалярные поля
                    for attr in ['id', 'catalog_number', 'denomination_value', 'currency',
                                 'year', 'century', 'weight', 'diameter', 'thickness',
                                 'mintage', 'shape', 'issue_type', 'avrev', 'description',
                                 'coin_info', 'notes', 'ucoin_url', 'meshok_url',
                                 'purchase_price', 'sale_price', 'market_price',
                                 'purchase_date', 'purchase_place', 'purchase_where',
                                 'quantity', 'selected', 'in_collection', 'status',
                                 'status_id', 'country_id', 'currency_id', 'mint_id',
                                 'metal_id', 'edge_id', 'period_id', 'condition_id',
                                 'rarity_id', 'shape_id', 'issue_type_id', 'avrev_id',
                                 'acquisition_type_id', 'storage_location_id',
                                 'obverse_image', 'reverse_image', 'mint_mark']:
                        try:
                            d[attr] = getattr(coin, attr, None)
                        except Exception:
                            d[attr] = None

                    # === Страна ===
                    country_obj = rel_obj(coin, ('country', 'country_obj'))
                    d['country_name'] = getattr(country_obj, 'name', None) if country_obj else None
                    d['continent'] = getattr(country_obj, 'continent', None) if country_obj else None
                    # Код страны (uCoin/ISO) и путь к иконке флага — для колонки FR
                    d['country_code'] = (
                        getattr(country_obj, 'code', None) or
                        getattr(country_obj, 'ucoin_code', None) or
                        getattr(country_obj, 'slug', None) or
                        getattr(country_obj, 'iso_code', None)
                    )
                    d['country_icon_path'] = (
                        getattr(country_obj, 'icon_path', None) or
                        getattr(country_obj, 'flag_path', None) or
                        getattr(country_obj, 'icon', None)
                    )
                    # === МЕТАЛЛ (metal_obj / metal / запрос по ID) ===
                    metal_obj = rel_obj(coin, ('metal_obj', 'metal'))
                    if metal_obj is None and d.get('metal_id'):
                        try:
                            metal_obj = session.get(Metal, d['metal_id'])
                        except Exception:
                            metal_obj = None
                    d['metal_name'] = getattr(metal_obj, 'name', None) if metal_obj else None

                    # === Валюта ===
                    currency_obj = rel_obj(coin, ('currency', 'currency_obj'))
                    if currency_obj is None and d.get('currency_id'):
                        try:
                            currency_obj = session.get(Currency, d['currency_id'])
                        except Exception:
                            currency_obj = None
                    d['currency_name'] = getattr(currency_obj, 'name', None) if currency_obj else None

                    # === Монетный двор ===
                    mint_obj = rel_obj(coin, ('mint', 'mint_obj'))
                    if mint_obj is None and d.get('mint_id'):
                        try:
                            mint_obj = session.get(Mint, d['mint_id'])
                        except Exception:
                            mint_obj = None
                    d['mint_name'] = getattr(mint_obj, 'name', None) if mint_obj else None

                    # === Гурт ===
                    edge_obj = rel_obj(coin, ('edge', 'edge_obj'))
                    if edge_obj is None and d.get('edge_id'):
                        try:
                            edge_obj = session.get(Edge, d['edge_id'])
                        except Exception:
                            edge_obj = None
                    d['edge_name'] = getattr(edge_obj, 'name', None) if edge_obj else None

                    # === Период ===
                    period_obj = rel_obj(coin, ('period_ref', 'period'))
                    if period_obj is None and d.get('period_id'):
                        try:
                            period_obj = session.get(Period, d['period_id'])
                        except Exception:
                            period_obj = None
                    d['period_name'] = getattr(period_obj, 'name', None) if period_obj else None

                    # === ВСЕ СТАНДАРТНЫЕ СПРАВОЧНИКИ (StandardReference) ===
                    for ref_key in ['condition', 'rarity', 'status', 'shape',
                                    'issue_type', 'avrev', 'acquisition_type',
                                    'storage_location']:
                        ref_obj = rel_obj(coin, (f'{ref_key}_ref', ref_key))
                        d[f'{ref_key}_name'] = (
                            getattr(ref_obj, 'name', None) if ref_obj else None
                        ) or d.get(ref_key)

                    frozen.append(d)
                except Exception as e:
                    self.logger.debug(f"Пропущена монета при замораживании: {e}")
                    continue

            self.current_coins = coins
            self._frozen_coins = {d['_id']: d for d in frozen}
            self.logger.info(f"✅ Загружено и заморожено монет: {len(frozen)}")

            # === Кэш справочников ===
            try:
                from database.models import StandardReference
                refs = session.query(StandardReference).all()
                self._standard_refs_cache = {(r.field_key, r.id): r.name for r in refs}
            except Exception as e:
                self.logger.debug(f"Кэш справочников не создан: {e}")

            # === Обновляем таблицу (БЕЗ тяжёлой статистики и двойного рендера) ===
            if hasattr(self, 'table_panel'):
                self.table_panel._all_coins = self.current_coins
                self.table_panel._frozen_coins = self._frozen_coins
                self.table_panel._frozen_list = [
                    self._frozen_coins[c.id] for c in coins if c.id in self._frozen_coins
                ]
                if hasattr(self.table_panel, '_column_filter') and self.table_panel._column_filter:
                    self.table_panel._clear_column_filter()
                self.table_panel.rebuild_table(self.current_coins)
                self.table_panel.update_info_label(self.current_coins)
                # ВАЖНО: show_collection_stats() и set_pagination() здесь НЕ вызываем —
                # они давали задержку при выборе страны; панель деталей обновляет
                # сам обработчик дерева (show_country_info_by_id / show_dashboard)

        except Exception as e:
            self.logger.error(f"Ошибка загрузки монет: {e}")
            import traceback
            traceback.print_exc()
            try:
                from database.models import Coin
                self.current_coins = self.db_manager.session.query(Coin).all()
                if hasattr(self, 'table_panel'):
                    self.table_panel._all_coins = self.current_coins
                    self.table_panel.rebuild_table(self.current_coins)
            except Exception as e2:
                self.logger.error(f"Запасной вариант тоже не сработал: {e2}")
        finally:
            self._loading_coins = False

    def add_coin(self):
        """Открывает диалог добавления монеты"""
        self.table_panel.save_state()
        
        from gui.add_coin_dialog import AddCoinDialog
        dialog = AddCoinDialog(self.db_manager, self)
        if dialog.exec():
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
            QTimer.singleShot(100, self.table_panel.restore_state)
            self.status_bar.showMessage("✅ Монета добавлена", 3000)
    
    def edit_coin(self):
        """Открывает диалог редактирования монеты"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монету для редактирования")
            return
        
        current_item = self.table.currentItem()
        if not current_item:
            return
        
        coin_id = current_item.data(Qt.UserRole)
        if not coin_id:
            return
        
        self.table_panel.save_state()
        
        from gui.add_coin_dialog import AddCoinDialog
        dialog = AddCoinDialog(self.db_manager, self, coin_id)
        if dialog.exec():
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
            QTimer.singleShot(100, self.table_panel.restore_state)
            self.status_bar.showMessage("✅ Монета обновлена", 3000)
    
    def delete_coin(self):
        """Удаляет выбранную монету"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монету для удаления")
            return
        
        current_item = self.table.currentItem()
        if not current_item:
            return
        
        coin_id = current_item.data(Qt.UserRole)
        if not coin_id:
            return
        
        coin = self.db_manager.get_coin(coin_id)
        if not coin:
            QMessageBox.warning(self, "Ошибка", "Монета не найдена")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы уверены, что хотите удалить монету?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.table_panel.save_state()
            self.db_manager.delete_coin(coin_id)
            self.load_coins()
            self.load_country_tree(preserve_expanded=True)
            QTimer.singleShot(100, self.table_panel.restore_state)
            self.status_bar.showMessage("✅ Монета удалена", 3000)