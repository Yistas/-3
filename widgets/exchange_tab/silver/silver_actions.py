# -*- coding: utf-8 -*-

"""
Действия для вкладки продажи серебра
"""

from datetime import datetime
from PySide6.QtWidgets import QMessageBox, QInputDialog, QDialog
from PySide6.QtCore import QTimer

from database.models import SilverPurchase, SilverCoin


class SilverActionsMixin:
    """Примесь с методами действий для серебра"""

    def add_purchase(self):
        """Добавляет новую закупку с автоматическим созданием монет"""
        # Находим следующий номер для №ЗакAG
        max_ag_number = 0
        for p in self.purchases:
            ag_num = p.get('number_ag', '')
            if ag_num and ag_num.startswith('AG'):
                try:
                    num = int(ag_num[2:])
                    if num > max_ag_number:
                        max_ag_number = num
                except (ValueError, TypeError):
                    pass

        next_ag_number = max_ag_number + 1
        next_ag_str = f"AG{next_ag_number:03d}"

        from gui.dialogs.add_purchase_dialog import AddPurchaseDialog
        dialog = AddPurchaseDialog(self)
        dialog.number_ag_edit.setText(next_ag_str)

        if dialog.exec() != QDialog.Accepted:
            return

        data = dialog.get_data()

        zak_number = data['number']
        if not zak_number:
            QMessageBox.warning(self, "Предупреждение", "№Зак обязателен для заполнения")
            return

        for p in self.purchases:
            if p.get('number') == zak_number:
                QMessageBox.warning(self, "Предупреждение", f"№Зак {zak_number} уже существует")
                return

        try:
            # Создаем закупку
            purchase = SilverPurchase(
                date=data['date'],
                number_ag=data['number_ag'],
                number=data['number'],
                source=data['source'],
                purchase_sum=data['purchase_sum'],
                quantity=data['quantity'],
                min_price=data['min_price']
            )
            self.db_manager.session.add(purchase)
            self.db_manager.session.flush()

            # Создаем монеты
            for i in range(data['quantity']):
                coin_number = f"{data['number_ag']}-{data['number']}-{i+1:04d}"
                coin = SilverCoin(
                    purchase_id=purchase.id,
                    status='in_sale',
                    number=coin_number,
                    min_price=data['min_price']
                )
                self.db_manager.session.add(coin)

            self.db_manager.session.commit()

            # Обновляем данные
            purchase_data = {
                'id': purchase.id,
                'date': purchase.date,
                'number_ag': purchase.number_ag,
                'number': purchase.number,
                'source': purchase.source,
                'purchase_sum': purchase.purchase_sum,
                'quantity': purchase.quantity,
                'min_price': purchase.min_price,
                'coins': []
            }

            # Получаем созданные монеты
            coins = self.db_manager.session.query(SilverCoin).filter_by(purchase_id=purchase.id).all()
            for coin in coins:
                purchase_data['coins'].append({
                    'id': coin.id,
                    'status': coin.status,
                    'country': coin.country,
                    'denomination': coin.denomination,
                    'year': coin.year,
                    'notes': coin.notes,
                    'number': coin.number,
                    'collection_price': coin.collection_price,
                    'sale_price': coin.sale_price,
                    'min_price': coin.min_price,
                    'plan_price': coin.plan_price,
                    'avito': coin.avito,
                    'lave': coin.lave,
                    'meshok': coin.meshok,
                    'ucoin': coin.ucoin
                })

            self.purchases.append(purchase_data)
            self._apply_filters()

            # Раскрываем новую закупку
            self._expand_purchase(purchase.id)

            QMessageBox.information(
                self,
                "Успех",
                f"✅ Закупка создана!\n"
                f"№ЗакAG: {data['number_ag']}\n"
                f"№Зак: {data['number']}\n"
                f"💰 Сумма закупки: {data['purchase_sum']:.2f} ₽\n"
                f"🔢 Монет: {data['quantity']}\n"
                f"💰 MIN цена: {data['min_price']:.2f} ₽"
            )

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def delete_selected_purchase(self):
        """Удаляет выбранную закупку"""
        if not self.expanded_purchase_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите закупку для удаления (раскройте её)")
            return

        purchase = None
        for p in self.purchases:
            if p['id'] == self.expanded_purchase_id:
                purchase = p
                break

        if not purchase:
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить закупку №{purchase['number']} с {len(purchase['coins'])} монетами?\n\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Удаляем монеты
                self.db_manager.session.query(SilverCoin).filter_by(purchase_id=purchase['id']).delete()
                # Удаляем закупку
                self.db_manager.session.query(SilverPurchase).filter_by(id=purchase['id']).delete()
                self.db_manager.session.commit()

                self.purchases = [p for p in self.purchases if p['id'] != purchase['id']]
                self.expanded_purchase_id = None
                self._apply_filters()

                QMessageBox.information(self, "Успех", f"✅ Закупка №{purchase['number']} удалена!")

            except Exception as e:
                self.db_manager.session.rollback()
                self.logger.error(f"Ошибка удаления: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")