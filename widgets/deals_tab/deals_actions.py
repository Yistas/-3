# -*- coding: utf-8 -*-

"""
Действия для вкладки "Сделки"
"""
import os
import re
import logging
import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtWidgets import QMessageBox, QProgressBar, QFileDialog, QApplication, QInputDialog, QAbstractItemView

from database.models import Deal, Purchase
from utils.paths import paths
 
 

class DealsActionsMixin:
    """Примесь с действиями для сделок"""

    def _add_deal(self):
        """Добавляет новую сделку"""
        self.logger.debug("_add_deal: добавление новой сделки")
        try:
            self.db_manager.session.rollback()
        except:
            pass

        max_number = 0
        for deal in self._all_deals:
            num_str = getattr(deal, 'number', '')
            if num_str:
                match = re.search(r'(\d+)', str(num_str))
                if match:
                    num_value = int(match.group(1))
                    if num_value > max_number:
                        max_number = num_value

        new_deal = Deal()
        new_number = max_number + 1
        setattr(new_deal, 'number', str(new_number))

        for key in self.CHECKBOX_COLUMNS.values():
            setattr(new_deal, key, "❌")

        self.db_manager.session.add(new_deal)
        self.db_manager.session.commit()

        new_deal_id = new_deal.id

        frozen = {'id': new_deal.id}
        for key in self.COLUMN_KEYS:
            if key != 'id':
                frozen[key] = getattr(new_deal, key, None)

        self._frozen_deals.append(frozen)
        self._all_deals.append(new_deal)

        sort_column = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self._refresh_all()

        if sort_column >= 0:
            self.table.sortByColumn(sort_column, sort_order)

        def select_new_deal():
            for i, deal in enumerate(self._filtered_deals):
                if deal.id == new_deal_id:
                    proxy_index = self.proxy_model.mapFromSource(self.model.index(i, 0))
                    if proxy_index.isValid():
                        self.table.selectRow(proxy_index.row())
                        self.table.setCurrentIndex(proxy_index)
                        self.table.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)
                    break

        QTimer.singleShot(200, select_new_deal)

        self.status_label.setText(f"✅ Сделка добавлена (ID: {new_deal_id}, №ПОК: {new_number})")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _delete_selected(self):
        """Удаляет выделенные строки"""
        self.logger.debug("_delete_selected: удаление выделенных строк")
        table = self.table
        if not table:
            return

        selected_rows = set()
        for idx in table.selectionModel().selectedRows():
            selected_rows.add(idx.row())

        if not selected_rows:
            for idx in table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())

        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для удаления")
            return

        source_rows = []
        for row in selected_rows:
            source_index = self.proxy_model.mapToSource(self.model.index(row, 0))
            source_rows.append(source_index.row())

        source_rows = sorted(set(source_rows), reverse=True)

        if not source_rows:
            return

        count = len(source_rows)

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить {count} строк(и)?\n\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        table.setUpdatesEnabled(False)

        try:
            deleted_ids = []
            for row in source_rows:
                if row < len(self._filtered_deals):
                    deal = self._filtered_deals[row]
                    if deal and deal.id:
                        db_deal = self.db_manager.session.query(Deal).get(deal.id)
                        if db_deal:
                            self.db_manager.session.delete(db_deal)
                            deleted_ids.append(deal.id)

            self.db_manager.session.commit()

            for row in sorted(source_rows, reverse=True):
                if row < len(self._filtered_deals):
                    deal = self._filtered_deals.pop(row)
                    if deal in self._all_deals:
                        self._all_deals.remove(deal)
                    if deal in self._frozen_deals:
                        self._frozen_deals.remove(deal)

            self.model.beginResetModel()
            self.model._data = self._filtered_deals
            self.model.endResetModel()

            self.load_nicknames_combo()
            self.update_statistics()

            self.status_label.setText(f"🗑️ Удалено {count} строк")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка удаления: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            table.setUpdatesEnabled(True)

    def _clear_all(self):
        """Удаляет все сделки"""
        self.logger.debug("_clear_all: очистка всех сделок")
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить ВСЕ сделки?\n\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.db_manager.session.query(Deal).delete()
                self.db_manager.session.commit()

                self._all_deals = []
                self._filtered_deals = []
                self._frozen_deals = []
                self.model.set_data([])
                self.count_label.setText("Сделок: 0")
                self.load_nicknames_combo()
                self.update_statistics()

                self.status_label.setText("🗑️ Все сделки удалены")
                self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
                QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

            except Exception as e:
                self.db_manager.session.rollback()
                self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def _force_reload(self):
        """Принудительная перезагрузка"""
        self.logger.debug("_force_reload: принудительная перезагрузка")
        reply = QMessageBox.question(
            self, "Перезагрузка",
            "Перезагрузить данные из базы? Несохранённые изменения будут потеряны.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.load_data()

    def _archive_purchases_by_number(self, purchase_number):
        """Архивирует закупки по номеру"""
        self.logger.debug(f"_archive_purchases_by_number: архивация закупок №{purchase_number}")

        if not purchase_number:
            QMessageBox.warning(self, "Предупреждение", "Не указан №ПОК")
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение архивации",
            f"Перенести в архив все закупки с №ПОК = {purchase_number}?\n\n"
            f"После переноса закупки будут удалены из основной таблицы закупок.\n"
            f"В колонке ИТОГ данной сделки появится значок 📦.\n\n"
            f"Это действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.setUpdatesEnabled(False)

        try:
            archived_count, message = self.db_manager.archive_purchases_by_batch(purchase_number)

            if archived_count > 0:
                current_index = self.table.currentIndex()
                if current_index.isValid():
                    source_index = self.proxy_model.mapToSource(current_index)
                    row = source_index.row()

                    if row < len(self._filtered_deals):
                        deal = self._filtered_deals[row]
                        if deal and getattr(deal, 'number', None) == purchase_number:
                            setattr(deal, 'total', "📦")
                            deal.updated_at = datetime.now()
                            self._on_deal_edited(deal, 'total', "📦")
                            model_index = self.model.index(row, self.COLUMN_KEYS.index('total'))
                            self.model.dataChanged.emit(model_index, model_index, [Qt.DisplayRole, Qt.ForegroundRole])

                main_window = None
                for widget in QApplication.topLevelWidgets():
                    if widget.__class__.__name__ == 'MainWindow':
                        main_window = widget
                        break

                if main_window and hasattr(main_window, 'exchange_tab'):
                    exchange_tab = main_window.exchange_tab
                    exchange_tab._full_reload()

                QMessageBox.information(
                    self,
                    "Архивация завершена",
                    f"✅ {message}\n\n"
                    f"Закупки с №ПОК {purchase_number} перенесены в архив.\n"
                    f"Сумма продажи сохранена, в колонке ИТОГ установлен значок 📦."
                )

                self._refresh_all()
            else:
                QMessageBox.warning(self, "Ошибка", f"❌ {message}")

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка архивации: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить архивацию:\n{e}")
        finally:
            self.setUpdatesEnabled(True)

    def _archive_multiple_deals(self):
        """Массовая архивация"""
        self.logger.debug("_archive_multiple_deals: массовая архивация")

        selected_rows = set()
        for idx in self.table.selectionModel().selectedRows():
            selected_rows.add(idx.row())

        if not selected_rows:
            for idx in self.table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())

        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите сделки для архивации")
            return

        deals_info = []
        purchase_numbers = set()

        for row in selected_rows:
            source_index = self.proxy_model.mapToSource(self.table.model().index(row, 0))
            source_row = source_index.row()

            if source_row < len(self._filtered_deals):
                deal = self._filtered_deals[source_row]
                if deal:
                    num = getattr(deal, 'number', None)
                    if num and str(num).strip():
                        if not (hasattr(deal, '_is_archived') and deal._is_archived):
                            deals_info.append((source_row, deal, str(num)))
                            purchase_numbers.add(str(num))

        if not deals_info:
            QMessageBox.warning(self, "Предупреждение",
                "Нет сделок с указанным №ПОК или все выбранные сделки уже архивированы")
            return

        total_deals = len(deals_info)
        unique_numbers = len(purchase_numbers)
        numbers_list = ", ".join(sorted(purchase_numbers)[:10])
        if len(purchase_numbers) > 10:
            numbers_list += f"... и ещё {len(purchase_numbers) - 10}"

        reply = QMessageBox.question(
            self,
            "Подтверждение массовой архивации",
            f"Перенести в архив закупки для {total_deals} сделок?\n\n"
            f"Уникальных №ПОК: {unique_numbers}\n"
            f"Номера: {numbers_list}\n\n"
            f"После переноса закупки будут удалены из основной таблицы закупок.\n"
            f"В колонке ИТОГ сделок появится значок 📦.\n\n"
            f"Это действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.setUpdatesEnabled(False)

        try:
            archived_total = 0
            errors = []
            updated_deal_ids = []

            for source_row, deal, num in deals_info:
                try:
                    archived_count, message = self.db_manager.archive_purchases_by_batch(num)

                    if archived_count > 0:
                        archived_total += archived_count
                        deal._is_archived = True
                        setattr(deal, 'total', "📦")
                        deal.updated_at = datetime.now()
                        self._on_deal_edited(deal, 'total', "📦")
                        updated_deal_ids.append(deal.id)
                    else:
                        errors.append(f"№{num}: {message}")

                except Exception as e:
                    errors.append(f"№{num}: {str(e)}")

            if updated_deal_ids:
                self.model.beginResetModel()
                self.model._data = self._filtered_deals
                self.model.endResetModel()

            main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break

            if main_window and hasattr(main_window, 'exchange_tab'):
                exchange_tab = main_window.exchange_tab
                exchange_tab._full_reload()

            result_msg = f"✅ Архивировано закупок: {archived_total}\n"
            result_msg += f"📦 Обновлено сделок: {len(updated_deal_ids)} из {total_deals}\n"

            if errors:
                result_msg += f"\n⚠️ Ошибки ({len(errors)}):\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    result_msg += f"\n... и ещё {len(errors) - 5}"

            QMessageBox.information(self, "Массовая архивация завершена", result_msg)
            self._refresh_all()

        except Exception as e:
            self.logger.error(f"Ошибка массовой архивации: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить массовую архивацию:\n{e}")
        finally:
            self.setUpdatesEnabled(True)

    def _close_deal(self, purchase_batch=None):
        """Закрывает сделку: обновляет закупки и сумму сделки в таблице сделок"""
        # ЗАЩИТА: если вызвано из сигнала triggered(checked=False) или без номера —
        # берём №ПОК из выделенной строки таблицы
        if purchase_batch is None or isinstance(purchase_batch, bool) \
                or not str(purchase_batch).strip():
            purchase_batch = self._get_selected_deal_number()
        if not purchase_batch or not str(purchase_batch).strip():
            QMessageBox.warning(self, "Предупреждение",
                                "Выделите сделку с указанным №ПОК")
            return
        try:
            obmen_dir = paths.get_obmen_dir()
            if not obmen_dir.exists():
                QMessageBox.warning(self, "Предупреждение",
                                    f"Папка обмена не найдена:\n{obmen_dir}")
                return

            # Ищем CSV-файл по маске *{номер_сделки}*.csv
            import glob
            pattern = str(obmen_dir / f"*{purchase_batch}*.csv")
            files = glob.glob(pattern)
            if not files:
                QMessageBox.warning(self, "Предупреждение",
                                    f"Файл обмена для сделки №{purchase_batch} не найден в:\n{obmen_dir}")
                return
            # Берём самый свежий файл
            csv_file = max(files, key=os.path.getmtime)
            self.logger.info(f"📄 Найден файл обмена: {csv_file}")

            # Читаем CSV
            coins_data = []
            encodings = ['utf-8-sig', 'utf-8', 'cp1251']
            content = None
            for encoding in encodings:
                try:
                    with open(csv_file, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            if content is None:
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

            import csv
            from io import StringIO
            reader = csv.DictReader(StringIO(content))
            for row in reader:
                country = (row.get('Страна') or '').strip().strip('"')
                nominal_raw = (row.get('Номинал') or '').strip().strip('"')
                year_raw = (row.get('Год') or '').strip().strip('"')
                # Нормализация года: только 4 цифры ("2016 ★S" -> "2016")
                year_match = re.search(r'(\d{4})', year_raw)
                year = year_match.group(1) if year_match else year_raw
                price_raw = (row.get('Цена, RUB') or '').strip().strip('"')
                price = None
                if price_raw:
                    try:
                        price = float(price_raw.replace(',', '.'))
                    except (ValueError, TypeError):
                        pass
                if country and year:
                    coins_data.append({
                        'country': country,
                        'year': year,
                        'denomination': nominal_raw,
                        'price': price,
                    })

            if not coins_data:
                QMessageBox.warning(self, "Предупреждение",
                                    "В файле не найдено монет")
                return

            # === ОБНОВЛЕНИЕ ЗАКУПОК ===
            updated_count = 0
            not_found_count = 0
            not_found_list = []

            for coin in coins_data:
                purchase = self._find_purchase_for_coin(
                    coin['country'], coin['year'], coin['denomination'],
                    purchase_batch
                )
                if purchase:
                    purchase.purchase_batch = str(purchase_batch)
                    purchase.sold_count = "1"
                    purchase.sold_sum = coin['price'] if coin['price'] else 0.0
                    purchase.total = coin['price'] if coin['price'] else 0.0
                    purchase.ucoin_exchange = False
                    purchase.ucoin_exchange_count = 0
                    purchase.updated_at = datetime.now()
                    self._dirty_ids.add(purchase.id)
                    updated_count += 1
                else:
                    not_found_count += 1
                    not_found_list.append(
                        f"{coin['country']} | {coin['denomination']} | {coin['year']}"
                    )

            self.db_manager.session.commit()

            # === ПЕРЕСЧЁТ СУММЫ СДЕЛКИ ===
            deal_total_sum = self._recalculate_deal_sum(purchase_batch)

            # === ОБНОВЛЕНИЕ ТАБЛИЦ ===
            main_window = self.window()
            if main_window and hasattr(main_window, 'exchange_tab'):
                exchange_tab = main_window.exchange_tab
                exchange_tab._full_reload()
                if hasattr(exchange_tab, 'deals_tab') and exchange_tab.deals_tab:
                    exchange_tab.deals_tab._refresh_all()
                    self.logger.info("🔄 Таблица сделок обновлена")

            # Результат
            result_msg = f"✅ Сделка №{purchase_batch} закрыта!\n"
            result_msg += f"📊 Обновлено закупок: {updated_count}\n"
            result_msg += f"💰 Сумма сделки: {deal_total_sum:,.2f} ₽\n"
            if not_found_count > 0:
                result_msg += f"⚠️ Не найдено цен: {not_found_count}\n"
                if len(not_found_list) <= 10:
                    result_msg += "\n".join(not_found_list)
                else:
                    result_msg += "\n".join(not_found_list[:10])
                    result_msg += f"\n... и ещё {len(not_found_list) - 10}"
            QMessageBox.information(self, "Закрытие сделки", result_msg)
            self._refresh_all()

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка закрытия сделки: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось закрыть сделку:\n{e}")

    def _find_purchase_for_coin(self, country, year, denomination, purchase_batch):
        """Ищет закупку для монеты из CSV файла обмена.
        Сначала среди закупок этой сделки, затем — среди помеченных на обмен."""
        try:
            # Нормализация года: только 4 цифры ("2016 ★S" -> "2016")
            year_str = str(year or '').strip()
            ym = re.search(r'(\d{4})', year_str)
            year_norm = ym.group(1) if ym else year_str
            # Нормализация номинала: число в начале строки ("1 флорин" -> "1")
            denom_raw = str(denomination or '').strip()
            dm = re.match(r'^(\d+(?:[.,]\d+)?)', denom_raw)
            denom_num = dm.group(1).replace(',', '.') if dm else None

            def matches(p):
                p_country = p.import_country.name if p.import_country else ''
                if p_country.strip().lower() != str(country or '').strip().lower():
                    return False
                p_year = str(p.year).strip() if p.year else ''
                if p_year != year_norm:
                    return False
                p_denom = str(p.denomination_value or '').strip()
                if denom_num is not None:
                    pm = re.match(r'^(\d+(?:[.,]\d+)?)', p_denom)
                    if pm:
                        try:
                            return abs(float(pm.group(1).replace(',', '.')) - float(denom_num)) < 1e-9
                        except (TypeError, ValueError):
                            return False
                    return p_denom.lower() == denom_raw.lower()
                return p_denom.lower() == denom_raw.lower()

            def not_sold(p):
                sc = str(p.sold_count or '').strip()
                return sc == '' or sc == '0'

            # 1) Ищем среди закупок этой сделки
            candidates = (self.db_manager.session.query(Purchase)
                          .filter(Purchase.purchase_batch == str(purchase_batch))
                          .all())
            found = [p for p in candidates if matches(p)]
            if found:
                found.sort(key=lambda p: 0 if not_sold(p) else 1)
                return found[0]

            # 2) Если в сделке нет — ищем среди помеченных на обмен
            candidates = (self.db_manager.session.query(Purchase)
                          .filter(Purchase.ucoin_exchange == True)
                          .all())
            found = [p for p in candidates if matches(p)]
            if found:
                found.sort(key=lambda p: 0 if not_sold(p) else 1)
                return found[0]

            return None
        except Exception as e:
            self.logger.error(f"Ошибка поиска закупки для монеты: {e}")
            return None

    def _get_selected_deal_number(self):
        """Возвращает №ПОК выделенной в таблице сделки"""
        try:
            current_index = self.table.currentIndex()
            if not current_index.isValid():
                return None
            source_index = self.proxy_model.mapToSource(current_index)
            row = source_index.row()
            if row < 0 or row >= len(self._filtered_deals):
                return None
            deal = self._filtered_deals[row]
            if not deal:
                return None
            if isinstance(deal, dict):
                return deal.get('number')
            return getattr(deal, 'number', None)
        except Exception as e:
            self.logger.error(f"Ошибка получения номера сделки: {e}")
            return None

    def _recalculate_deal_sum(self, purchase_batch):
        """Пересчитывает и сохраняет сумму сделки ТОЛЬКО в колонке 'Сумма' (amount)"""
        try:
            from database.models import Deal, Purchase
            purchases = (self.db_manager.session.query(Purchase)
                         .filter(Purchase.purchase_batch == str(purchase_batch))
                         .all())
            deal_total = 0.0
            for p in purchases:
                try:
                    if p.sold_sum:
                        deal_total += float(p.sold_sum)
                except (TypeError, ValueError):
                    pass

            deal = (self.db_manager.session.query(Deal)
                    .filter(Deal.number == str(purchase_batch))
                    .first())
            if deal:
                # ВАЖНО: сумму пишем ТОЛЬКО в amount (колонка "Сумма").
                # total НЕ трогаем — там хранится маркер архива "📦"
                deal.amount = deal_total
                deal.updated_at = datetime.now()
                self.db_manager.session.commit()
                self.logger.info(
                    f"💰 Сумма сделки №{purchase_batch} обновлена: "
                    f"{deal_total:.2f} ₽ (закупок: {len(purchases)})"
                )
            else:
                self.logger.warning(
                    f"⚠️ Сделка №{purchase_batch} не найдена в таблице deals"
                )
            return deal_total
        except Exception as e:
            self.logger.error(f"Ошибка пересчёта суммы сделки: {e}")
            return 0.0

    def _remove_duplicates(self):
        """Размножение монет (удаление дублей)"""
        self.logger.debug("_remove_duplicates: удаление дублей")

        from database.models import Purchase

        current_index = self.table.currentIndex()
        if not current_index.isValid():
            QMessageBox.warning(self, "Предупреждение", "Выделите сделку для удаления дублей")
            return

        source_index = self.proxy_model.mapToSource(current_index)
        row = source_index.row()

        if row < 0 or row >= len(self._filtered_deals):
            return

        deal = self._filtered_deals[row]
        if not deal:
            return

        purchase_batch = getattr(deal, 'number', None)

        if not purchase_batch or not str(purchase_batch).strip():
            QMessageBox.warning(self, "Предупреждение", "В этой сделке не указан №ПОК")
            return

        reply = QMessageBox.question(
            self,
            "Удаление дублей",
            f"Обработать дубликаты для сделки №{purchase_batch}?\n\n"
            f"Будут найдены все закупки с этим номером.\n"
            f"Для каждой позиции будет оставлен 1 экземпляр,\n"
            f"остальные будут перемещены в необработанные закупки (№Пок=0).\n\n"
            f"Поля КОЛ и Обмен обрабатываются вместе (они всегда равны).",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.setUpdatesEnabled(False)

        try:
            purchases = self.db_manager.session.query(Purchase).filter_by(
                purchase_batch=str(purchase_batch)
            ).all()

            if not purchases:
                QMessageBox.warning(self, "Предупреждение", f"Закупки с №Пок={purchase_batch} не найдены")
                return

            processed_count = 0
            total_duplicates = 0

            for purchase in purchases:
                count = purchase.quantity or 1

                if count > 1:
                    for i in range(count - 1):
                        duplicate = Purchase()
                        duplicate.in_collection = purchase.in_collection
                        duplicate.collection_price = purchase.collection_price
                        duplicate.purchase_number = purchase.purchase_number
                        duplicate.purchase_batch = "0"
                        duplicate.import_country_id = purchase.import_country_id
                        duplicate.continent = purchase.continent
                        duplicate.denomination_value = purchase.denomination_value
                        duplicate.currency = purchase.currency
                        duplicate.year = purchase.year
                        duplicate.location_found = purchase.location_found
                        duplicate.quantity = 1
                        duplicate.comments = purchase.comments
                        duplicate.ucoin_exchange = True
                        duplicate.ucoin_exchange_count = 1
                        duplicate.sold_count = None
                        duplicate.sold_sum = None
                        duplicate.total = None
                        self.db_manager.session.add(duplicate)
                        total_duplicates += 1

                    purchase.quantity = 1
                    purchase.ucoin_exchange = True
                    purchase.ucoin_exchange_count = 1
                    processed_count += 1

            self.db_manager.session.commit()

            main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break

            if main_window and hasattr(main_window, 'exchange_tab'):
                exchange_tab = main_window.exchange_tab
                exchange_tab._full_reload()

            QMessageBox.information(
                self,
                "Удаление дублей завершено",
                f"✅ Обработано закупок: {processed_count}\n"
                f"📦 Создано дубликатов: {total_duplicates}\n\n"
                f"Оригиналы остались в сделке №{purchase_batch}\n"
                f"Дубликаты перемещены в необработанные закупки (№Пок=0)\n\n"
                f"Поля КОЛ и Обмен приведены к 1"
            )

            self._refresh_all()

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка удаления дублей: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось обработать дубликаты:\n{e}")
        finally:
            self.setUpdatesEnabled(True)

    def _goto_purchase_by_number(self):
        """Переход к закупке по номеру"""
        self.logger.debug("_goto_purchase_by_number: переход к закупке")

        current = self.table.currentIndex()
        if not current.isValid():
            QMessageBox.warning(self, "Предупреждение", "Выделите строку со сделкой")
            return

        source_index = self.proxy_model.mapToSource(current)
        row = source_index.row()

        if row < 0 or row >= len(self._filtered_deals):
            return

        deal = self._filtered_deals[row]
        if not deal:
            return

        purchase_number = getattr(deal, 'number', None)

        if not purchase_number or not str(purchase_number).strip():
            QMessageBox.warning(self, "Предупреждение", "В этой сделке не указан №ПОК")
            return

        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break

        if not main_window:
            QMessageBox.warning(self, "Ошибка", "Не найдено главное окно")
            return

        if not hasattr(main_window, 'exchange_tab'):
            QMessageBox.warning(self, "Ошибка", "Вкладка закупок не найдена")
            return

        exchange_tab = main_window.exchange_tab

        if hasattr(exchange_tab, 'tab_widget'):
            for i in range(exchange_tab.tab_widget.count()):
                tab_text = exchange_tab.tab_widget.tabText(i)
                if "Закупки" in tab_text:
                    exchange_tab.tab_widget.setCurrentIndex(i)
                    break

        QTimer.singleShot(500, lambda: self._do_goto_purchase(exchange_tab, str(purchase_number)))

    def _do_goto_purchase(self, exchange_tab, purchase_number):
        """Выполняет переход к закупке"""
        self.logger.debug(f"_do_goto_purchase: переход к закупке №{purchase_number}")

        if hasattr(exchange_tab, '_goto_purchase_by_number'):
            exchange_tab._goto_purchase_by_number(purchase_number)
        else:
            QMessageBox.warning(self, "Ошибка", "Метод перехода не найден в вкладке закупок")