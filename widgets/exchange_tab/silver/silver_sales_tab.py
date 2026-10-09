# -*- coding: utf-8 -*-
"""
Вкладка "Продажа СЕРЕБРА" — полная версия с БД
Дизайн: вариант 1 «Мастер-деталь» — слева плоская таблица закупок,
справа таблица монет выбранной закупки (без аккордеона и скролл-простыни).
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QComboBox, QLineEdit, QScrollArea, QSizePolicy,
    QMessageBox, QApplication, QInputDialog, QDialog, QHeaderView,
    QTableView, QSplitter, QAbstractItemView, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle, QMenu, QDateEdit, QDoubleSpinBox,
    QFormLayout, QDialogButtonBox
)
from PySide6.QtCore import (Qt, QTimer, QUrl, Signal, QSettings,
                            QAbstractTableModel, QSortFilterProxyModel,
                            QModelIndex)
from PySide6.QtGui import QKeyEvent, QColor, QPalette, QBrush
from database.models import SilverPurchase, SilverCoin
from .silver_ui import SilverUIMixin
from .silver_actions import SilverActionsMixin
from .silver_filters import SilverFiltersMixin


class SilverPurchasesTableModel(QAbstractTableModel):
    """Модель левой таблицы закупок (плоский список, вариант 1).
    Колонки статистики по каждой закупке:
    Остаток (шт), Продано ₽, Коллекция ₽, Прибыль ₽, Прибыль %."""

    HEADERS = ["№AG", "№", "Дата", "Источник", "Сумма", "Кол-во",
               "Продано", "КОЛ", "ОСТ", "ПРОД ₽",
               "КОЛ ₽", "ПРИБ ₽", "ПРИБ %"]
    KEYS = ['number_ag', 'number', 'date', 'source', 'purchase_sum',
            'quantity', 'sold', 'collection', 'remaining', 'sold_sum',
            'collection_sum', 'profit', 'profit_percent']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []

    def set_data(self, data):
        self.beginResetModel()
        self._data = data or []
        self.endResetModel()

    def get_purchase(self, row):
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    @staticmethod
    def _stats(purchase):
        """Считает статистику по монетам закупки:
        (продано шт, коллекция шт, остаток шт, продано ₽, коллекция ₽)."""
        sold = 0
        coll = 0
        sold_sum = 0.0
        coll_sum = 0.0
        for coin in purchase.get('coins', []):
            st = coin.get('status')
            if st == 'sold':
                sold += 1
                try:
                    sold_sum += float(coin.get('sale_price') or 0)
                except (TypeError, ValueError):
                    pass
            elif st == 'in_collection':
                coll += 1
                try:
                    coll_sum += float(coin.get('collection_price') or 0)
                except (TypeError, ValueError):
                    pass
        total = len(purchase.get('coins', []))
        remaining = max(total - sold - coll, 0)
        return sold, coll, remaining, sold_sum, coll_sum

    @staticmethod
    def _purchase_sum(purchase):
        try:
            return float(purchase.get('purchase_sum') or 0)
        except (TypeError, ValueError):
            return 0.0

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._data):
            return None
        p = self._data[row]
        key = self.KEYS[col]
        sold, coll, remaining, sold_sum, coll_sum = self._stats(p)
        purchase_sum = self._purchase_sum(p)
        profit = (sold_sum + coll_sum) - purchase_sum
        profit_pct = (profit / purchase_sum * 100) if purchase_sum > 0 else 0.0

        if role == Qt.DisplayRole:
            if key == 'sold':
                return f"{sold}/{len(p.get('coins', []))}"
            if key == 'collection':
                return str(coll)
            if key == 'remaining':
                return str(remaining)
            if key == 'sold_sum':
                return f"{sold_sum:,.0f}" if sold_sum else ""
            if key == 'collection_sum':
                return f"{coll_sum:,.0f}" if coll_sum else ""
            if key == 'profit':
                return f"{profit:+,.0f}"
            if key == 'profit_percent':
                return f"{profit_pct:+.1f}%"
            value = p.get(key)
            if value is None:
                return ""
            if key == 'purchase_sum':
                try:
                    return f"{float(value):,.0f}"
                except (TypeError, ValueError):
                    return str(value)
            if key == 'date':
                try:
                    return value.strftime('%d.%m.%Y')
                except Exception:
                    return str(value)
            return str(value)
        if role == Qt.TextAlignmentRole:
            if col in (0, 1, 4, 5, 6, 7, 8, 9, 10, 11, 12):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.ForegroundRole:
            # Прибыль — зелёным/красным текстом
            if key in ('profit', 'profit_percent'):
                return QColor('#90ee90') if profit > 0 else QColor('#ff9090')
            return None
        if role == Qt.UserRole:
            if key in ('purchase_sum', 'quantity'):
                try:
                    return float(p.get(key) or 0)
                except (TypeError, ValueError):
                    return 0.0
            if key in ('number_ag', 'number'):
                try:
                    return float(p.get(key) or 0)
                except (TypeError, ValueError):
                    return str(p.get(key) or '').lower()
            if key == 'date':
                try:
                    return p.get(key).isoformat()
                except Exception:
                    return ''
            if key == 'sold':
                return float(sold)
            if key == 'collection':
                return float(coll)
            if key == 'remaining':
                return float(remaining)
            if key == 'sold_sum':
                return sold_sum
            if key == 'collection_sum':
                return coll_sum
            if key in ('profit', 'profit_percent'):
                return profit if key == 'profit' else profit_pct
            return str(p.get(key) or '').lower()
        if role == Qt.BackgroundRole:
            # Цвет строки: сумма 'цена продажи' монет > 'Сумма' закупки
            sale_sum = 0.0
            for coin in p.get('coins', []):
                try:
                    sale_sum += float(coin.get('sale_price') or 0)
                except (TypeError, ValueError):
                    pass
            if sale_sum > purchase_sum:
                return QColor('#173f1f')   # тёмно-зелёный (прибыль)
            return QColor('#4a1a1a')       # тёмно-красный (убыток)
        return None

class SilverPurchasesProxy(QSortFilterProxyModel):
    """Прокси сортировки левой таблицы закупок."""

    def lessThan(self, left, right):
        ld = left.data(Qt.UserRole)
        rd = right.data(Qt.UserRole)
        try:
            return float(ld) < float(rd)
        except (TypeError, ValueError):
            return str(ld).lower() < str(rd).lower()

class SilverRowColorDelegate(QStyledItemDelegate):
    """Заливка строк левой таблицы закупок.
    Приоритет цвета:
      1) ручная метка пользователя ('green'/'red' из ConfigDB);
      2) автоматика: сумма 'цена продажи' монет > 'Сумма' закупки → зелёный,
         иначе красный.
    Выделенная строка остаётся фиолетовой (не перекрашиваем)."""

    GREEN = QColor('#173f1f')
    RED = QColor('#4a1a1a')

    def _get_tab(self):
        """Находит вкладку SilverSalesTab подъёмом по родителям."""
        w = self.parent()
        while w is not None:
            if hasattr(w, '_load_row_color_overrides'):
                return w
            w = w.parent()
        return None

    def _get_purchase(self, index):
        model = index.model()
        if model is None:
            return None
        if hasattr(model, 'mapToSource'):
            src = model.mapToSource(index)
            model = model.sourceModel()
            index = src
        getter = getattr(model, 'get_purchase', None)
        if callable(getter):
            return getter(index.row())
        return None

    @staticmethod
    def _sums(purchase):
        sale_sum = 0.0
        for coin in purchase.get('coins', []):
            try:
                sale_sum += float(coin.get('sale_price') or 0)
            except (TypeError, ValueError):
                pass
        try:
            purchase_sum = float(purchase.get('purchase_sum') or 0)
        except (TypeError, ValueError):
            purchase_sum = 0.0
        return sale_sum, purchase_sum

    def row_color(self, index):
        purchase = self._get_purchase(index)
        if not purchase:
            return None
        # === 1) РУЧНАЯ МЕТКА ПОЛЬЗОВАТЕЛЯ ===
        tab = self._get_tab()
        if tab is not None:
            try:
                overrides = tab._load_row_color_overrides()
                ov = overrides.get(str(purchase.get('id')))
                if ov == 'green':
                    return self.GREEN
                if ov == 'red':
                    return self.RED
            except Exception:
                pass
        # === 2) АВТОМАТИКА: прибыль/убыток ===
        sale_sum, purchase_sum = self._sums(purchase)
        return self.GREEN if sale_sum > purchase_sum else self.RED

    def paint(self, painter, option, index):
        color = self.row_color(index)
        if color is not None and not (option.state & QStyle.State_Selected):
            # 1) Рисуем заливку сами — гарантированно видна
            painter.save()
            painter.fillRect(option.rect, color)
            painter.restore()
            # 2) Дублируем цвет в option и палитру, чтобы любой стиль
            #    при отрисовке текста не затёр фон своим
            option = QStyleOptionViewItem(option)
            option.backgroundBrush = QBrush(color)
            option.palette.setColor(QPalette.Base, color)
            option.palette.setColor(QPalette.AlternateBase, color)
            option.palette.setColor(QPalette.Window, color)
        super().paint(painter, option, index)

class SilverCoinDelegateWrapper(QStyledItemDelegate):
    """Делегат-обёртка для таблицы монет (правая панель):
    - СОХРАНЯЕТ редакторы исходного делегата (комбобокс статуса, чекбоксы);
    - выводит цены collection_price / sale_price ЦЕЛЫМИ, без копеек;
    - рисует заливку строки по статусу ПЕРЕД отрисовкой содержимого.
    БЕЗ reentrancy-флагов: вложенные paint-вызовы не оставляют пустых ячеек."""

    INT_PRICE_KEYS = ('collection_price', 'sale_price')

    def __init__(self, original, parent=None):
        super().__init__(parent)
        self._original = original

    def _is_price_column(self, index):
        model = index.model()
        keys = getattr(model, 'COLUMN_KEYS', None)
        if keys and 0 <= index.column() < len(keys):
            return keys[index.column()] in self.INT_PRICE_KEYS
        return False

    def initStyleOption(self, option, index):
        """Округляет цены до целого; пустые ячейки не трогает."""
        super().initStyleOption(option, index)
        if self._is_price_column(index):
            try:
                text = option.text
                if text is None or text == "":
                    return
                num = float(str(text).replace(' ', '').replace(',', '.'))
                option.text = f"{num:,.0f}".replace(',', ' ')
            except (ValueError, TypeError, AttributeError):
                pass

    def paint(self, painter, option, index):
        """СНАЧАЛА заливка строки цветом статуса (BackgroundRole модели),
        ПОТОМ отрисовка содержимого исходным делегатом (таблетка статуса,
        ✅/❌, текст). Выделенную строку не перекрашиваем."""
        bg = None
        try:
            bg = index.data(Qt.BackgroundRole)
        except Exception:
            bg = None
        if bg is not None and not (option.state & QStyle.State_Selected):
            painter.save()
            painter.fillRect(option.rect, bg)
            painter.restore()
            option = QStyleOptionViewItem(option)
            option.backgroundBrush = QBrush(bg)
            option.palette.setColor(QPalette.Base, bg)
            option.palette.setColor(QPalette.AlternateBase, bg)
            option.palette.setColor(QPalette.Window, bg)
        if self._original is not None:
            self._original.paint(painter, option, index)
        else:
            super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        if self._original is not None:
            return self._original.createEditor(parent, option, index)
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        if self._original is not None:
            self._original.setEditorData(editor, index)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if self._original is not None:
            self._original.setModelData(editor, model, index)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        if self._original is not None:
            self._original.updateEditorGeometry(editor, option, index)
        else:
            super().updateEditorGeometry(editor, option, index)

class SilverSalesTab(QWidget, SilverUIMixin, SilverActionsMixin, SilverFiltersMixin):
    """Вкладка "Продажа СЕРЕБРА" — полная версия с БД"""

    # Файл для сохранения настроек колонок
    COLUMN_SETTINGS_FILE = Path("data/silver_column_settings.json")

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.SilverSalesTab')

        self.purchases = []
        self._filtered_purchases = []
        self.purchase_widgets = {}
        self.expanded_purchase_id = None
        self.status_filter = "all"
        self.search_text = ""
        self._show_archive = False
        self._updating = False
        self._column_widths = {}  # {purchase_id: {col: width}}
        self._dirty_purchases = set()

        self.init_ui()
        self.load_data_from_db()
        self._load_column_settings()

    def init_ui(self):
        """Инициализация интерфейса (вариант 1: мастер-деталь)."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        # Шапка статистики (чипы в одну строку, липкая)
        stats_frame = self._create_stats_header()
        layout.addWidget(stats_frame)
        # Тулбар (штатный из SilverUIMixin)
        toolbar = self._create_toolbar()
        # === УБИРАЕМ КНОПКИ «Развернуть всё» / «Свернуть всё» ===
        # (в мастер-детали аккордеона нет, кнопки бессмысленны)
        for btn in toolbar.findChildren(QPushButton):
            txt = btn.text()
            if 'Развернуть' in txt or 'Свернуть' in txt:
                btn.hide()
                btn.deleteLater()
        layout.addWidget(toolbar)
        # Основной контейнер: сплиттер «закупки | монеты»
        self._create_main_container()
        layout.addWidget(self.splitter, 1)
        # Статус
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        layout.addWidget(self.status_label)

    # ========== УПРАВЛЕНИЕ РАСКРЫТИЕМ ==========

    def _expand_purchase(self, purchase_id):
        """Раскрывает закупку"""
        self._collapse_all_purchases()

        widget = self.purchase_widgets.get(purchase_id)
        if widget and hasattr(widget, 'coin_table') and widget.coin_table:
            widget.coin_table.show()
            if hasattr(widget, 'header') and hasattr(widget.header, 'btn'):
                widget.header.btn.setText("▼ Скрыть монеты")
            self.expanded_purchase_id = purchase_id
            self.scroll_area.updateGeometry()

    def _collapse_all_purchases(self):
        """Скрывает все таблицы"""
        for widget in self.purchase_widgets.values():
            if hasattr(widget, 'coin_table') and widget.coin_table:
                widget.coin_table.setVisible(False)
            if hasattr(widget, 'header') and hasattr(widget.header, 'btn'):
                widget.header.btn.setText("▶ Показать монеты")
        self.expanded_purchase_id = None

    def toggle_purchase(self, purchase_id):
        """Переключает состояние закупки"""
        if self.expanded_purchase_id == purchase_id:
            self._collapse_all_purchases()
        else:
            self._expand_purchase(purchase_id)

    def expand_all(self):
        """Раскрывает все отфильтрованные закупки"""
        self._collapse_all_purchases()

        for purchase in self._filtered_purchases:
            widget = self.purchase_widgets.get(purchase['id'])
            if widget and hasattr(widget, 'coin_table') and widget.coin_table:
                widget.coin_table.show()
                if hasattr(widget, 'header') and hasattr(widget.header, 'btn'):
                    widget.header.btn.setText("▼ Скрыть монеты")

        self.expanded_purchase_id = None

    def collapse_all(self):
        """Сворачивает все закупки"""
        self._collapse_all_purchases()

    def scroll_to_top(self):
        """Прокручивает к началу"""
        self.scroll_area.verticalScrollBar().setValue(0)

    def scroll_to_bottom(self):
        """Прокручивает к концу"""
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    # ========== ЗАГРУЗКА ДАННЫХ ==========

    def load_data_from_db(self):
        """Загружает данные из БД"""
        try:
            self.db_manager.session.rollback()

            purchases = self.db_manager.session.query(SilverPurchase).order_by(
                SilverPurchase.id.desc()
            ).all()

            self.purchases = []
            for p in purchases:
                coins = self.db_manager.session.query(SilverCoin).filter_by(purchase_id=p.id).all()

                purchase_data = {
                    'id': p.id,
                    'date': p.date,
                    'number_ag': p.number_ag,
                    'number': p.number,
                    'source': p.source,
                    'purchase_sum': p.purchase_sum,
                    'quantity': p.quantity,
                    'min_price': p.min_price,
                    'coins': []
                }

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
            self.status_label.setText(f"✅ Загружено из БД: {len(self.purchases)} закупок")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки из БД: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"❌ Ошибка загрузки: {str(e)[:50]}")

    def _rebuild_ui(self):
        """Перестраивает весь UI на основе отфильтрованных данных"""
        # Очищаем контейнер
        while self.main_layout.count() > 1:
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Создаем виджеты для каждой отфильтрованной закупки
        self.purchase_widgets = {}
        for purchase in self._filtered_purchases:
            container = self._create_purchase_container(purchase)
            self.main_layout.insertWidget(self.main_layout.count() - 1, container)
            self.purchase_widgets[purchase['id']] = container

        # Обновляем статистику
        self._update_stats()

        # Применяем глобальные настройки ко всем таблицам
        self._apply_global_settings_to_all_tables()

    # ========== СТАТИСТИКА ==========

    def _update_stats(self):
        """Обновляет статистику в шапке"""
        total_purchased = 0
        total_sold = 0
        total_collection = 0
        total_remaining = 0
        total_purchase_sum = 0
        sales_sum = 0
        collection_sum = 0

        for purchase in self.purchases:
            total_purchase_sum += purchase['purchase_sum']
            for coin in purchase['coins']:
                total_purchased += 1
                if coin['status'] == 'sold':
                    total_sold += 1
                    sales_sum += coin['sale_price']
                elif coin['status'] == 'in_collection':
                    total_collection += 1
                    collection_sum += coin['collection_price']
                else:
                    total_remaining += 1

        total_sales = sales_sum + collection_sum

        # Блок 1: Количество
        self.total_purchased_label.setText(str(total_purchased))
        self.total_remaining_label.setText(str(total_remaining))
        self.total_sold_count_label.setText(str(total_sold))

        # Блок 2: В коллекцию
        self.total_collection_count_label.setText(str(total_collection))
        self.total_collection_sum_label.setText(f"{collection_sum:,.2f} ₽")

        # Блок 3: Суммы
        self.total_purchase_sum_label.setText(f"{total_purchase_sum:,.2f} ₽")
        self.total_sales_sum_label.setText(f"{sales_sum:,.2f} ₽")

        # Блок 4: Проценты
        if total_purchase_sum > 0:
            sales_profit = ((sales_sum - total_purchase_sum) / total_purchase_sum) * 100
            total_profit = ((total_sales - total_purchase_sum) / total_purchase_sum) * 100
        else:
            sales_profit = 0
            total_profit = 0

        self.sales_percent_label.setText(f"{sales_profit:+.1f}%")
        self.sales_percent_label.setStyleSheet(
            f"font-weight: bold; font-size: 20px; color: {'#28a745' if sales_profit >= 0 else '#dc3545'};"
        )

        self.total_percent_label.setText(f"{total_profit:+.1f}%")
        self.total_percent_label.setStyleSheet(
            f"font-weight: bold; font-size: 20px; color: {'#28a745' if total_profit >= 0 else '#dc3545'};"
        )

        if total_sales > 0:
            collection_percent = (collection_sum / total_sales) * 100
        else:
            collection_percent = 0

        self.collection_percent_label.setText(f"{collection_percent:.1f}%")
        self.collection_percent_label.setStyleSheet(
            f"font-weight: bold; font-size: 20px; color: {'#ff9800' if collection_percent > 0 else '#6c757d'};"
        )

    # ========== ЕДИНАЯ СИСТЕМА СОХРАНЕНИЯ КОЛОНОК ТАБЛИЦЫ МОНЕТ ==========
    # Все ширины и порядок колонок хранятся в ConfigDB под ключом
    # 'silver_coin_table_settings' и применяются ОДИНАКОВО ко всем закупкам.

    def _load_coin_table_settings(self):
        """Загружает из ConfigDB ширины и порядок колонок таблицы монет."""
        if not hasattr(self, '_coin_tbl_settings'):
            try:
                from database.config_db import get_config_db
                data = get_config_db().get('silver_coin_table_settings') or {}
                self._coin_tbl_settings = {
                    'widths': data.get('widths', {}) or {},
                    'order': data.get('order', []) or [],
                }
            except Exception as e:
                self.logger.debug(f"Не удалось загрузить настройки таблицы монет: {e}")
                self._coin_tbl_settings = {'widths': {}, 'order': []}
        return self._coin_tbl_settings

    def _save_coin_table_settings(self):
        """Сохраняет ширины и порядок колонок активной таблицы монет в ConfigDB."""
        table = self._get_active_table()
        if table is None or table.model() is None:
            return
        header = table.horizontalHeader()
        count = table.model().columnCount()
        widths = {str(i): table.columnWidth(i) for i in range(count)}
        order = [header.logicalIndex(v) for v in range(count)]
        try:
            from database.config_db import get_config_db
            get_config_db().set('silver_coin_table_settings',
                                {'widths': widths, 'order': order}, 'columns')
            self._coin_tbl_settings = {'widths': widths, 'order': order}
            self.logger.debug("Настройки таблицы монет (ширины+порядок) сохранены")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек таблицы монет: {e}")

    def _on_coin_header_changed(self, *args):
        """Дебаунс-сохранение колонок таблицы монет.
        Во время программного применения настроек (_cc_applying_settings)
        игнорируем сигналы шапки — это разрывает петлю
        'применение → сигнал → сохранение → применение'."""
        if getattr(self, '_cc_applying_settings', False):
            return
        if not hasattr(self, '_coin_hdr_save_timer'):
            self._coin_hdr_save_timer = QTimer()
            self._coin_hdr_save_timer.setSingleShot(True)
            self._coin_hdr_save_timer.timeout.connect(
                self._save_coin_table_settings)
        self._coin_hdr_save_timer.start(500)

    def _apply_coin_table_settings(self, table):
        """Применяет сохранённые ширины и порядок колонок к таблице монет.
        ВАЖНО: блокирует сигналы шапки на время применения, чтобы setColumnWidth
        и moveSection не триггерили sectionResized/sectionMoved и не вызывали
        рекурсию."""
        if table is None or table.model() is None:
            return
        settings = self._load_coin_table_settings()
        header = table.horizontalHeader()
        count = table.model().columnCount()
        # === КРИТИЧНО: блокируем сигналы, чтобы не было рекурсии ===
        header.blockSignals(True)
        try:
            # 1) Ширины
            for col_str, width in settings.get('widths', {}).items():
                try:
                    col = int(col_str)
                    if 0 <= col < count and width and int(width) > 0:
                        table.setColumnWidth(col, int(width))
                except (TypeError, ValueError):
                    pass
            # 2) Порядок колонок
            order = settings.get('order', []) or []
            if len(order) == count and sorted(order) == list(range(count)):
                for visual_pos in range(count):
                    logical = order[visual_pos]
                    current_visual = header.visualIndex(logical)
                    if current_visual != visual_pos:
                        header.moveSection(current_visual, visual_pos)
        finally:
            header.blockSignals(False)

    # === Переопределения для совместимости с mixin silver_ui.py ===
    def _apply_column_settings(self, table, purchase_id):
        """Перенаправление: применяем единые настройки таблицы монет."""
        self._apply_coin_table_settings(table)

    def _apply_global_settings_to_all_tables(self):
        """Применяем единые настройки ко всем видимым таблицам монет."""
        for widget in self.purchase_widgets.values():
            table = getattr(widget, 'coin_table', None)
            if table is not None and table.isVisible():
                self._apply_coin_table_settings(table)

    def _save_column_settings(self):
        """Перенаправление: сохраняем единые настройки."""
        self._save_coin_table_settings()

    def _on_column_resized(self, *args, **kwargs):
        """Перенаправление: старый сигнал из mixin → новый дебаунс."""
        self._on_coin_header_changed()                 
    # ========== АВТОСОХРАНЕНИЕ ИЗМЕНЕНИЙ ==========

    def _on_silver_data_changed(self, purchase_id):
        """Обработчик изменения данных в таблице серебра"""
        # Сохраняем изменения с задержкой
        if not hasattr(self, '_silver_save_timer'):
            self._silver_save_timer = QTimer()
            self._silver_save_timer.setSingleShot(True)
            self._silver_save_timer.timeout.connect(self._save_dirty_purchases)

        self._dirty_purchases.add(purchase_id)
        self._silver_save_timer.start(1000)
        
        # Сохраняем ширину колонок при изменении данных
        if hasattr(self, '_column_save_timer'):
            self._column_save_timer.start(500)

    def _save_dirty_purchases(self):
        """Сохраняет все измененные закупки"""
        if not self._dirty_purchases:
            return

        try:
            saved_count = 0
            for purchase_id in list(self._dirty_purchases):
                # Находим закупку в данных
                purchase = None
                for p in self.purchases:
                    if p['id'] == purchase_id:
                        purchase = p
                        break

                if purchase:
                    if self._save_purchase(purchase):
                        saved_count += 1
                        self._dirty_purchases.remove(purchase_id)

            if saved_count > 0:
                self.db_manager.session.commit()
                self.status_label.setText(f"✅ Сохранено {saved_count} закупок")
                self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")

    # ========== СОХРАНЕНИЕ В БД ==========

    def _save_purchase(self, purchase_data):
        """Сохраняет закупку в БД (с обновлением цен продажи)"""
        try:
            db_purchase = self.db_manager.session.query(SilverPurchase).get(purchase_data['id'])
            if not db_purchase:
                self.logger.error(f"Закупка с ID {purchase_data['id']} не найдена в БД")
                return False

            # Обновляем поля закупки
            db_purchase.date = purchase_data['date']
            db_purchase.number_ag = purchase_data['number_ag']
            db_purchase.number = purchase_data['number']
            db_purchase.source = purchase_data.get('source', '')
            db_purchase.purchase_sum = purchase_data['purchase_sum']
            db_purchase.quantity = purchase_data['quantity']
            db_purchase.min_price = purchase_data['min_price']
            db_purchase.updated_at = datetime.now()

            # Получаем существующие монеты
            existing_coins = {c.id: c for c in self.db_manager.session.query(SilverCoin).filter_by(
                purchase_id=db_purchase.id
            ).all()}

            # Обновляем или создаем монеты
            for coin_data in purchase_data['coins']:
                coin_id = coin_data.get('id')

                if coin_id and coin_id in existing_coins:
                    # Обновляем существующую монету
                    db_coin = existing_coins[coin_id]
                    db_coin.status = coin_data['status']
                    db_coin.country = coin_data.get('country')
                    db_coin.denomination = coin_data.get('denomination')
                    db_coin.year = coin_data.get('year')
                    db_coin.notes = coin_data.get('notes')
                    db_coin.collection_price = coin_data.get('collection_price', 0)
                    db_coin.sale_price = coin_data.get('sale_price', 0)
                    db_coin.min_price = coin_data.get('min_price', 0)
                    db_coin.plan_price = coin_data.get('plan_price', 0)
                    db_coin.avito = coin_data.get('avito', False)
                    db_coin.lave = coin_data.get('lave', False)
                    db_coin.meshok = coin_data.get('meshok', False)
                    db_coin.ucoin = coin_data.get('ucoin', False)
                    del existing_coins[coin_id]
                else:
                    # Создаем новую монету
                    new_coin = SilverCoin(
                        purchase_id=db_purchase.id,
                        status=coin_data['status'],
                        country=coin_data.get('country'),
                        denomination=coin_data.get('denomination'),
                        year=coin_data.get('year'),
                        notes=coin_data.get('notes'),
                        number=coin_data['number'],
                        collection_price=coin_data.get('collection_price', 0),
                        sale_price=coin_data.get('sale_price', 0),
                        min_price=coin_data.get('min_price', 0),
                        plan_price=coin_data.get('plan_price', 0),
                        avito=coin_data.get('avito', False),
                        lave=coin_data.get('lave', False),
                        meshok=coin_data.get('meshok', False),
                        ucoin=coin_data.get('ucoin', False)
                    )
                    self.db_manager.session.add(new_coin)

            # Удаляем монеты, которых больше нет
            for coin_id, db_coin in existing_coins.items():
                self.db_manager.session.delete(db_coin)

            self.db_manager.session.commit()
            self.logger.info(f"✅ Сохранена закупка {purchase_data['number']}")
            return True

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            return False

    def _force_save_all(self):
        """Принудительно сохраняет все закупки"""
        if self._updating:
            return

        self.logger.info("💾 Принудительное сохранение всех закупок серебра...")

        try:
            saved_count = 0
            for purchase in self.purchases:
                try:
                    if self._save_purchase(purchase):
                        saved_count += 1
                except Exception as e:
                    self.logger.error(f"Ошибка сохранения закупки {purchase.get('number', '?')}: {e}")

            self.db_manager.session.commit()
            self.logger.info(f"✅ Сохранено закупок серебра: {saved_count}")

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка массового сохранения: {e}")
            raise

    # ========== КОПИРОВАНИЕ И ВСТАВКА ==========
    def keyPressEvent(self, event: QKeyEvent):
        """ЕДИНЫЙ обработчик клавиш вкладки:
        Ctrl+C / Ctrl+V / Delete / F5 / Ctrl+S.
        Дубли метода удалены — они переопределяли друг друга и
        участвовали в цикле повторных вызовов."""
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C:
            self._copy_selected_cells()
            event.accept()
            return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_V:
            self._paste_to_selected_cells()
            event.accept()
            return
        if event.key() == Qt.Key_F5:
            self.load_data_from_db()
            event.accept()
            return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_S:
            self._save_dirty_purchases()
            event.accept()
            return
        if event.key() == Qt.Key_Delete:
            self._clear_selected_cells()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_selected_cells(self):
        """Копирует выделенные ячейки в буфер обмена"""
        # Находим активную таблицу (раскрытую закупку)
        table = self._get_active_table()
        if not table:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        # Сортируем по строкам и колонкам
        rows = {}
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            if row not in rows:
                rows[row] = {}
            value = idx.data(Qt.DisplayRole) or ""
            rows[row][col] = value
        
        # Формируем текст для буфера обмена
        lines = []
        for row in sorted(rows.keys()):
            cols = rows[row]
            max_col = max(cols.keys()) if cols else 0
            line = []
            for col in range(max_col + 1):
                line.append(cols.get(col, ""))
            lines.append("\t".join(line))
        
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))
        
        self.status_label.setText(f"📋 Скопировано {len(selected_indexes)} ячеек")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _paste_to_selected_cells(self):
        """Вставляет данные из буфера обмена в выделенные ячейки"""
        # Находим активную таблицу
        table = self._get_active_table()
        if not table:
            return
        
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        # Разбираем буфер обмена
        rows_data = []
        for line in text.strip().split("\n"):
            if "\t" in line:
                row = line.split("\t")
            else:
                row = line.split(",")
            rows_data.append([cell.strip() for cell in row])
        
        if not rows_data:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            current = table.currentIndex()
            if current.isValid():
                selected_indexes = [current]
        
        if not selected_indexes:
            return
        
        # Сортируем по строкам и колонкам
        selected_indexes.sort(key=lambda x: (x.row(), x.column()))
        
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0
        
        if source_rows == 0 or source_cols == 0:
            return
        
        table.setUpdatesEnabled(False)
        
        try:
            # Получаем модель
            model = table.model()
            purchase_id = self._get_purchase_id_from_table(table)
            
            # Находим закупку
            purchase = None
            for p in self.purchases:
                if p['id'] == purchase_id:
                    purchase = p
                    break
            
            if not purchase:
                return
            
            changes_made = False
            
            for i, target_idx in enumerate(selected_indexes):
                source_row = i % source_rows
                source_col = (i // source_rows) % source_cols
                
                if source_row < len(rows_data) and source_col < len(rows_data[source_row]):
                    value = rows_data[source_row][source_col]
                else:
                    value = ""
                
                row = target_idx.row()
                col = target_idx.column()
                
                # Получаем ключ колонки
                if col < len(SilverTableModel.COLUMN_KEYS):
                    field_name = SilverTableModel.COLUMN_KEYS[col]
                    
                    # Обновляем данные
                    if row < len(purchase['coins']):
                        coin = purchase['coins'][row]
                        if field_name in coin:
                            old_value = coin[field_name]
                            if str(old_value) != value:
                                # Преобразуем значение в правильный тип
                                if field_name in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
                                    try:
                                        coin[field_name] = float(value) if value else 0
                                    except ValueError:
                                        coin[field_name] = 0
                                elif field_name in ['avito', 'lave', 'meshok', 'ucoin']:
                                    coin[field_name] = value in ['✅', 'True', 'true', '1', 'Да', 'yes']
                                elif field_name == 'status':
                                    status_map = {'В продаже': 'in_sale', 'Продана': 'sold', 'В коллекции': 'in_collection'}
                                    coin[field_name] = status_map.get(value, 'in_sale')
                                else:
                                    coin[field_name] = value if value else None
                                
                                changes_made = True
                                self._dirty_purchases.add(purchase_id)
            
            if changes_made:
                # Обновляем модель
                model.set_data(purchase['coins'])
                self._save_dirty_purchases()
                
                self.status_label.setText(f"📌 Вставлено в {len(selected_indexes)} ячеек")
                self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
        except Exception as e:
            self.logger.error(f"Ошибка вставки: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
        finally:
            table.setUpdatesEnabled(True)

    def _clear_selected_cells(self):
        """Очищает содержимое выделенных ячеек"""
        table = self._get_active_table()
        if not table:
            return
        
        selected_indexes = table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        # Получаем модель
        model = table.model()
        purchase_id = self._get_purchase_id_from_table(table)
        
        # Находим закупку
        purchase = None
        for p in self.purchases:
            if p['id'] == purchase_id:
                purchase = p
                break
        
        if not purchase:
            return
        
        changes_made = False
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            
            if col < len(SilverTableModel.COLUMN_KEYS):
                field_name = SilverTableModel.COLUMN_KEYS[col]
                
                if row < len(purchase['coins']):
                    coin = purchase['coins'][row]
                    if field_name in coin:
                        # Для статуса устанавливаем 'in_sale'
                        if field_name == 'status':
                            coin[field_name] = 'in_sale'
                        # Для чекбоксов устанавливаем False
                        elif field_name in ['avito', 'lave', 'meshok', 'ucoin']:
                            coin[field_name] = False
                        # Для числовых полей устанавливаем 0
                        elif field_name in ['collection_price', 'sale_price', 'min_price', 'plan_price']:
                            coin[field_name] = 0
                        # Для текстовых полей устанавливаем None
                        else:
                            coin[field_name] = None
                        
                        changes_made = True
                        self._dirty_purchases.add(purchase_id)
        
        if changes_made:
            model.set_data(purchase['coins'])
            self._save_dirty_purchases()
            
            self.status_label.setText(f"🧹 Очищено {len(selected_indexes)} ячеек")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _get_active_table(self):
        """Возвращает активную таблицу (раскрытую закупку)"""
        if not self.expanded_purchase_id:
            return None
        
        widget = self.purchase_widgets.get(self.expanded_purchase_id)
        if widget and hasattr(widget, 'coin_table') and widget.coin_table:
            if widget.coin_table.isVisible():
                return widget.coin_table
        return None

    def _get_purchase_id_from_table(self, table):
        """Получает ID закупки из таблицы"""
        for purchase_id, widget in self.purchase_widgets.items():
            if hasattr(widget, 'coin_table') and widget.coin_table == table:
                return purchase_id
        return None

    def closeEvent(self, event):
        """Обработчик закрытия - сохраняем настройки"""
        self._save_column_settings()
        self._save_purchases_table_settings()
        # Сохраняем все изменения
        if self._dirty_purchases:
            self._save_dirty_purchases()
        super().closeEvent(event)
        
    def toggle_purchase(self, purchase_id):
        """Переключает состояние закупки"""
        if self.expanded_purchase_id == purchase_id:
            self._collapse_all_purchases()
        else:
            self._expand_purchase(purchase_id)

    # ========== КЛАВИШИ ==========


        
    def _create_stats_header(self):
        """Компактная липкая строка-чип статистики.
        Имена label'ов СОВПАДАЮТ со старыми — _update_stats() работает без правок."""
        frame = QFrame()
        frame.setFixedHeight(52)
        frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
            }
            QLabel { background: transparent; border: none; }
        """)
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(14)

        def chip(caption):
            box = QVBoxLayout()
            box.setSpacing(0)
            cap = QLabel(caption)
            cap.setStyleSheet("color: #8888aa; font-size: 9px;")
            val = QLabel("0")
            val.setStyleSheet("color: #e4e4ef; font-size: 13px; font-weight: bold;")
            box.addWidget(cap)
            box.addWidget(val)
            row.addLayout(box)
            return val

        self.total_purchased_label = chip("КУПЛЕНО (шт)")
        self.total_remaining_label = chip("ОСТАЛОСЬ (шт)")
        self.total_sold_count_label = chip("ПРОДАНО (шт)")
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #2a2a4a;")
        row.addWidget(sep1)
        self.total_collection_count_label = chip("В КОЛЛЕКЦИЮ (шт)")
        self.total_collection_sum_label = chip("В КОЛЛЕКЦИЮ (₽)")
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #2a2a4a;")
        row.addWidget(sep2)
        self.total_purchase_sum_label = chip("ЗАКУПКА (₽)")
        self.total_sales_sum_label = chip("ПРОДАЖА (₽)")
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setStyleSheet("color: #2a2a4a;")
        row.addWidget(sep3)
        self.sales_percent_label = chip("SALES %")
        self.total_percent_label = chip("TOTAL %")
        self.collection_percent_label = chip("COLLECTION %")
        row.addStretch()
        return frame

    def _create_main_container(self):
        """Сплиттер: слева плоская таблица закупок со статистикой,
        контекстным меню, перетаскиванием колонок и сохранением
        порядка/ширин; справа монеты выбранной закупки."""
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(3)
        self.splitter.setChildrenCollapsible(False)

        # === ЛЕВАЯ ПАНЕЛЬ: закупки ===
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self.purchases_model = SilverPurchasesTableModel(self)
        self.purchases_proxy = SilverPurchasesProxy(self)
        self.purchases_proxy.setSourceModel(self.purchases_model)
        self.purchases_proxy.setSortRole(Qt.UserRole)
        self.purchases_table = QTableView()
        self.purchases_table.setModel(self.purchases_proxy)
        self.purchases_table.setAlternatingRowColors(False)
        self.purchases_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.purchases_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.purchases_table.setSortingEnabled(True)
        self.purchases_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.purchases_table.horizontalHeader().setSortIndicatorShown(True)
        self.purchases_table.verticalHeader().setVisible(False)
        # === КОНТЕКСТНОЕ МЕНЮ ЗАКУПОК ===
        self.purchases_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.purchases_table.customContextMenuRequested.connect(
            self._on_purchases_context_menu)
        # === ГАРАНТИРОВАННАЯ ЗАЛИВКА СТРОК (зелёный/красный) ===
        self.purchases_table.setItemDelegate(
            SilverRowColorDelegate(self.purchases_table))
        pal = self.purchases_table.palette()
        pal.setColor(QPalette.Base, QColor('#1a1a2e'))
        pal.setColor(QPalette.AlternateBase, QColor('#16213e'))
        pal.setColor(QPalette.Text, QColor('#e4e4ef'))
        pal.setColor(QPalette.ButtonText, QColor('#e4e4ef'))
        pal.setColor(QPalette.Highlight, QColor('#6c63ff'))
        pal.setColor(QPalette.HighlightedText, QColor('#ffffff'))
        pal.setColor(QPalette.Window, QColor('#1a1a2e'))
        self.purchases_table.setPalette(pal)
        self.purchases_table.setStyleSheet("")
        self.purchases_table.horizontalHeader().setStyleSheet("""
            QHeaderView {
                background-color: #16213e;
            }
            QHeaderView::section {
                background-color: #16213e;
                color: #a8a8d0;
                padding: 4px;
                border: none;
                border-right: 1px solid #2a2a4a;
                border-bottom: 2px solid #6c63ff;
                font-weight: bold;
            }
        """)
        widths = [60, 50, 80, 110, 80, 50, 60, 70, 60, 80, 80, 80, 60]
        for i, w in enumerate(widths):
            self.purchases_table.setColumnWidth(i, w)

        # === ПЕРЕТАСКИВАНИЕ КОЛОНОК МЫШКОЙ + СОХРАНЕНИЕ ПОРЯДКА/ШИРИН ===
        header = self.purchases_table.horizontalHeader()
        header.setSectionsMovable(True)                 # колонки таскаются мышкой
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.sectionMoved.connect(self._on_purchases_header_changed)
        header.sectionResized.connect(self._on_purchases_header_changed)
        # Загружаем и применяем сохранённые ширины и порядок
        self._load_purchases_table_settings()
        self._apply_purchases_table_settings()

        self.purchases_table.selectionModel().currentRowChanged.connect(
            self._on_purchase_row_changed)
        left_layout.addWidget(self.purchases_table)
        self.splitter.addWidget(left)

        # === ПРАВАЯ ПАНЕЛЬ: монеты выбранной закупки ===
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        self.coin_title_label = QLabel("🪙 Монеты закупки: —")
        self.coin_title_label.setStyleSheet(
            "color: #a8a8d0; font-size: 11px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(self.coin_title_label)
        self.coin_area_layout = QVBoxLayout()
        self.coin_area_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addLayout(self.coin_area_layout)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 3)

        # === АТРИБУТЫ СОВМЕСТИМОСТИ со старыми методами mixin ===
        self.scroll_area = None
        self.main_layout = None
        self.purchase_widgets = {}
        self._current_coin_container = None
        self._current_purchase_id = None

    # ========== НАСТРОЙКИ ЛЕВОЙ ТАБЛИЦЫ (ширины + порядок колонок) ==========
    def _load_purchases_table_settings(self):
        """Загружает из ConfigDB ширины и порядок колонок левой таблицы
        (ключ 'silver_purchases_table_settings')."""
        try:
            from database.config_db import get_config_db
            data = get_config_db().get('silver_purchases_table_settings') or {}
            self._pt_widths = data.get('widths', {}) or {}
            self._pt_order = data.get('order', []) or []
        except Exception as e:
            self.logger.debug(f"Не удалось загрузить настройки левой таблицы: {e}")
            self._pt_widths = {}
            self._pt_order = []

    def _save_purchases_table_settings(self):
        """Сохраняет текущие ширины и порядок колонок левой таблицы в ConfigDB."""
        table = getattr(self, 'purchases_table', None)
        if table is None or table.model() is None:
            return
        try:
            from database.config_db import get_config_db
            header = table.horizontalHeader()
            count = table.model().columnCount()
            widths = {str(i): table.columnWidth(i) for i in range(count)}
            # order[v] = логический индекс колонки, стоящей на визуальной позиции v
            order = [header.logicalIndex(v) for v in range(count)]
            get_config_db().set('silver_purchases_table_settings',
                                {'widths': widths, 'order': order}, 'columns')
            self.logger.debug("Настройки левой таблицы (ширины+порядок) сохранены")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек левой таблицы: {e}")

    def _on_purchases_header_changed(self, *args):
        """Дебаунс-сохранение: срабатывает на перемещение И изменение ширины
        колонки, пишет в ConfigDB через 500 мс после последнего действия."""
        if not hasattr(self, '_pt_save_timer'):
            self._pt_save_timer = QTimer()
            self._pt_save_timer.setSingleShot(True)
            self._pt_save_timer.timeout.connect(
                self._save_purchases_table_settings)
        self._pt_save_timer.start(500)

    def _apply_purchases_table_settings(self):
        """Применяет сохранённые ширины и порядок колонок к левой таблице.
        На время программного применения сигналы шапки блокируются,
        чтобы не сработало лишнее сохранение."""
        table = getattr(self, 'purchases_table', None)
        if table is None or table.model() is None:
            return
        header = table.horizontalHeader()
        count = table.model().columnCount()
        header.blockSignals(True)
        try:
            # 1) Ширины
            for col_str, width in getattr(self, '_pt_widths', {}).items():
                try:
                    col = int(col_str)
                    if 0 <= col < count and width and int(width) > 0:
                        table.setColumnWidth(col, int(width))
                except (TypeError, ValueError):
                    pass
            # 2) Порядок колонок
            order = getattr(self, '_pt_order', []) or []
            if len(order) == count and sorted(order) == list(range(count)):
                for visual_pos in range(count):
                    logical = order[visual_pos]
                    current_visual = header.visualIndex(logical)
                    if current_visual != visual_pos:
                        header.moveSection(current_visual, visual_pos)
        finally:
            header.blockSignals(False)

    def _on_purchase_row_changed(self, current, previous):
        """Клик/стрелки по левой таблице → показать монеты справа.
        Во время перестройки (_rebuilding) игнорируем — это и есть
        разрыв цепи рекурсии."""
        if getattr(self, '_rebuilding', False):
            return
        if not current.isValid():
            return
        src_row = self.purchases_proxy.mapToSource(current).row()
        if 0 <= src_row < len(self._filtered_purchases):
            self._show_purchase_coins(self._filtered_purchases[src_row])

    def _on_search_changed(self, text):
        """Поиск с ДЕБАУНСОМ 300 мс: перестройка UI запускается один раз
        после паузы ввода, а не на каждый символ (лечит подвисание).
        События во время перестройки игнорируются (защита от рекурсии)."""
        if getattr(self, '_rebuilding', False):
            return
        self.search_text = text.strip().lower()
        if not hasattr(self, '_search_debounce_timer'):
            self._search_debounce_timer = QTimer()
            self._search_debounce_timer.setSingleShot(True)
            self._search_debounce_timer.timeout.connect(self._apply_filters)
        self._search_debounce_timer.start(300)

    def _on_filter_changed(self):
        """Фильтр статуса с дебаунсом 300 мс + защита от рекурсии."""
        if getattr(self, '_rebuilding', False):
            return
        combo = getattr(self, 'filter_combo', None)
        if combo is None:
            return
        self.status_filter = combo.currentData()
        if not hasattr(self, '_filter_debounce_timer'):
            self._filter_debounce_timer = QTimer()
            self._filter_debounce_timer.setSingleShot(True)
            self._filter_debounce_timer.timeout.connect(self._apply_filters)
        self._filter_debounce_timer.start(300)

    def _clear_search(self):
        """Очищает поиск (с дебаунсом, как обычный ввод)."""
        edit = getattr(self, 'search_edit', None)
        if edit is not None:
            edit.clear()
            edit.setFocus()
        self.search_text = ""
        if not hasattr(self, '_search_debounce_timer'):
            self._search_debounce_timer = QTimer()
            self._search_debounce_timer.setSingleShot(True)
            self._search_debounce_timer.timeout.connect(self._apply_filters)
        self._search_debounce_timer.start(300)

    def _load_row_color_overrides(self):
        """Загружает ручные метки цвета строк из ConfigDB
        ({purchase_id: 'green'|'red'}). Кэширует в памяти."""
        if not hasattr(self, '_row_color_overrides'):
            try:
                from database.config_db import get_config_db
                data = get_config_db().get('silver_row_colors') or {}
                self._row_color_overrides = {str(k): v for k, v in data.items()}
            except Exception as e:
                self.logger.debug(f"Не удалось загрузить метки цвета: {e}")
                self._row_color_overrides = {}
        return self._row_color_overrides

    def _set_row_color_override(self, purchase_id, value):
        """Устанавливает ручную метку цвета строки левой таблицы:
        'green' | 'red' | None (авто по прибыли).
        Сохраняет в ConfigDB ('silver_row_colors') и сразу перерисовывает
        левую таблицу.
        ВАЖНО: в этой сборке PySide6 у QTableView.update() сломана
        сигнатура (ждёт QModelIndex) — перерисовываем через viewport(),
        у обычного QWidget update() без аргументов работает."""
        overrides = self._load_row_color_overrides()
        key = str(purchase_id)
        if value in ('green', 'red'):
            overrides[key] = value
        else:
            overrides.pop(key, None)
        try:
            from database.config_db import get_config_db
            get_config_db().set('silver_row_colors', overrides, 'ui')
        except Exception as e:
            self.logger.error(f"Ошибка сохранения цвета строки: {e}")
        # === БЕЗОПАСНАЯ ПЕРЕРИСОВКА ЛЕВОЙ ТАБЛИЦЫ ===
        table = getattr(self, 'purchases_table', None)
        if table is not None:
            try:
                table.viewport().update()
            except Exception:
                pass
            try:
                # Страховка: если viewport не перерисовался — просим view
                # пересчитать раскладку на следующем тике event loop
                QTimer.singleShot(0, lambda: table.viewport().update())
            except Exception:
                pass

    def _on_purchases_context_menu(self, pos):
        """Контекстное меню левой таблицы закупок:
        редактирование атрибутов, быстрый выбор цвета строки,
        добавление пустой монеты, удаление закупки."""
        index = self.purchases_table.indexAt(pos)
        if not index.isValid():
            return
        src_row = self.purchases_proxy.mapToSource(index).row()
        if not (0 <= src_row < len(self._filtered_purchases)):
            return
        purchase = self._filtered_purchases[src_row]
        menu = QMenu(self)
        edit_action = menu.addAction("✏️ Редактировать закупку…")
        # === БЫСТРЫЙ ЦВЕТ СТРОКИ ===
        color_menu = menu.addMenu("🎨 Цвет строки")
        green_action = color_menu.addAction("🟢 Зелёный")
        red_action = color_menu.addAction("🔴 Красный")
        auto_action = color_menu.addAction("⚪ Авто (по прибыли)")
        menu.addSeparator()
        add_coin_action = menu.addAction("➕ Добавить пустую монету")
        menu.addSeparator()
        delete_action = menu.addAction("🗑 Удалить закупку")
        chosen = menu.exec(self.purchases_table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self._edit_purchase_dialog(purchase)
        elif chosen == green_action:
            self._set_row_color_override(purchase['id'], 'green')
        elif chosen == red_action:
            self._set_row_color_override(purchase['id'], 'red')
        elif chosen == auto_action:
            self._set_row_color_override(purchase['id'], None)
        elif chosen == add_coin_action:
            self._add_empty_coin_to_purchase(purchase)
        elif chosen == delete_action:
            self._delete_purchase_by_id(purchase['id'])

    def _edit_purchase_dialog(self, purchase):
        """Диалог редактирования атрибутов закупки.
        Добавлен выбор ЦВЕТА СТРОКИ: Авто (по прибыли) / Зелёный / Красный.
        Количество монет здесь не меняется — монеты управляются
        в правой таблице."""
        dlg = QDialog(self)
        dlg.setWindowTitle(
            f"✏️ Закупка №AG {purchase.get('number_ag') or '—'} "
            f"(№ {purchase.get('number') or '—'})")
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)
        form.setSpacing(6)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        d = purchase.get('date')
        if d:
            date_edit.setDate(d)
        else:
            date_edit.setDate(datetime.now().date())
        form.addRow("Дата:", date_edit)

        ag_edit = QLineEdit(purchase.get('number_ag') or "")
        form.addRow("№AG:", ag_edit)

        num_edit = QLineEdit(str(purchase.get('number') or ""))
        form.addRow("№:", num_edit)

        source_edit = QLineEdit(purchase.get('source') or "")
        form.addRow("Источник:", source_edit)

        sum_edit = QDoubleSpinBox()
        sum_edit.setRange(0, 999999999)
        sum_edit.setDecimals(2)
        sum_edit.setValue(float(purchase.get('purchase_sum') or 0))
        form.addRow("Сумма, ₽:", sum_edit)

        min_edit = QDoubleSpinBox()
        min_edit.setRange(0, 999999999)
        min_edit.setDecimals(2)
        min_edit.setValue(float(purchase.get('min_price') or 0))
        form.addRow("Мин. цена, ₽:", min_edit)

        # === ЦВЕТ СТРОКИ: ручной выбор поверх автоматики ===
        color_combo = QComboBox()
        color_combo.addItem("Авто (по прибыли)", None)
        color_combo.addItem("🟢 Зелёный", 'green')
        color_combo.addItem("🔴 Красный", 'red')
        current_ov = self._load_row_color_overrides().get(
            str(purchase.get('id')))
        idx = color_combo.findData(current_ov)
        if idx >= 0:
            color_combo.setCurrentIndex(idx)
        color_combo.setToolTip(
            "Ручной цвет строки в левой таблице.\n"
            "'Авто' — зелёный, если сумма цен продажи больше суммы закупки.")
        form.addRow("Цвет строки:", color_combo)

        coins_label = QLabel(
            f"Монет в закупке: {len(purchase.get('coins', []))} "
            f"(управляются в правой таблице)")
        coins_label.setStyleSheet("color: #8888aa; font-size: 10px;")
        form.addRow(coins_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.Accepted:
            return
        purchase['date'] = date_edit.date().toPython()
        purchase['number_ag'] = ag_edit.text().strip() or None
        purchase['number'] = num_edit.text().strip() or None
        purchase['source'] = source_edit.text().strip() or None
        purchase['purchase_sum'] = sum_edit.value()
        purchase['min_price'] = min_edit.value()
        self._dirty_purchases.add(purchase['id'])
        self._save_purchase(purchase)
        # === СОХРАНЯЕМ РУЧНОЙ ЦВЕТ СТРОКИ ===
        self._set_row_color_override(purchase['id'], color_combo.currentData())
        self._rebuild_ui()
        self.status_label.setText(
            f"✅ Закупка №AG {purchase['number_ag'] or '—'} обновлена")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(
            2000,
            lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _add_empty_coin_to_purchase(self, purchase):
        """Добавляет пустую монету в закупку с автонумерацией
        AG-№-NNNN и сохраняет в БД."""
        coins = purchase.setdefault('coins', [])
        idx = len(coins) + 1
        number = (f"{purchase.get('number_ag') or 'AG'}-"
                  f"{purchase.get('number') or 0}-{idx:04d}")
        coins.append({
            'id': None,
            'status': 'in_sale',
            'country': None,
            'denomination': None,
            'year': None,
            'notes': None,
            'number': number,
            'collection_price': 0,
            'sale_price': 0,
            'min_price': purchase.get('min_price') or 0,
            'plan_price': 0,
            'avito': False,
            'lave': False,
            'meshok': False,
            'ucoin': False,
        })
        self._dirty_purchases.add(purchase['id'])
        self._save_purchase(purchase)
        self._rebuild_ui()
        self.status_label.setText(f"➕ Добавлена монета {number}")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(
            2000,
            lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _delete_purchase_by_id(self, purchase_id):
        """Удаляет закупку вместе с монетами из БД (с подтверждением)."""
        purchase = None
        for p in self.purchases:
            if p['id'] == purchase_id:
                purchase = p
                break
        if not purchase:
            return
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить закупку №AG {purchase.get('number_ag') or '—'} "
            f"(№ {purchase.get('number') or '—'}) с "
            f"{len(purchase.get('coins', []))} монетами?\n\n"
            f"Это действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            self.db_manager.session.query(SilverCoin).filter_by(
                purchase_id=purchase_id).delete()
            self.db_manager.session.query(SilverPurchase).filter_by(
                id=purchase_id).delete()
            self.db_manager.session.commit()
            self.purchases = [p for p in self.purchases if p['id'] != purchase_id]
            if self._current_purchase_id == purchase_id:
                self._current_purchase_id = None
            self._apply_filters()
            self.status_label.setText(
                f"🗑 Закупка №AG {purchase.get('number_ag') or '—'} удалена")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(
                2000,
                lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка удаления закупки: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")

    def _show_purchase_coins(self, purchase):
        """Строит справа таблицу монет выбранной закупки штатным
        _create_purchase_container. Монеты прижаты к ВЕРХУ, высота снята.
        ЗАЩИТА ОТ РЕКУРСИИ: флаг _showing_coins блокирует повторный вход.
        Настройки колонок применяются ОДИН раз внутри _configure_coin_table."""
        if not purchase:
            return
        if getattr(self, '_showing_coins', False):
            return
        pid = purchase.get('id')
        if pid == getattr(self, '_current_purchase_id', None) \
                and getattr(self, '_current_coin_container', None) is not None:
            return
        self._showing_coins = True
        try:
            # Убираем старый контейнер
            old = getattr(self, '_current_coin_container', None)
            self._current_coin_container = None
            if old is not None:
                try:
                    self.coin_area_layout.removeWidget(old)
                    old.deleteLater()
                except Exception:
                    pass
            # Новый контейнер
            self.purchase_widgets = {}
            container = self._create_purchase_container(purchase)
            self.purchase_widgets[pid] = container
            self._current_coin_container = container
            self._current_purchase_id = pid
            self.expanded_purchase_id = pid   # для _get_active_table()

            # === ФИКС ПОЗИЦИИ: монеты ВВЕРХУ, а не по центру ===
            lay = container.layout()
            if lay is not None:
                for i in reversed(range(lay.count())):
                    item = lay.itemAt(i)
                    if item is not None and item.widget() is None \
                            and item.layout() is None:
                        lay.takeAt(i)
                try:
                    lay.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                except Exception:
                    pass

            tbl = getattr(container, 'coin_table', None)

            # === ФИКС ВЫСОТЫ: контейнер и таблица НЕ выходят за панель ===
            for w in (container, tbl):
                if w is None:
                    continue
                try:
                    w.setMinimumHeight(0)
                    w.setMaximumHeight(16777215)
                    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                except Exception:
                    pass
            if tbl is not None:
                try:
                    tbl.setVisible(True)
                    tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                except Exception:
                    pass
            try:
                for child in container.findChildren(QTableView):
                    child.setMinimumHeight(0)
                    child.setMaximumHeight(16777215)
                    child.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    child.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            except Exception:
                pass

            hdr = getattr(container, 'header', None)
            if hdr is not None:
                try:
                    hdr.hide()
                except Exception:
                    pass
            self.coin_area_layout.addWidget(container, 1)
            # === ЕДИНСТВЕННОЕ применение настроек колонок ===
            self._configure_coin_table(tbl)
            # Заголовок правой панели
            ag = purchase.get('number_ag') or '—'
            num = purchase.get('number') or '—'
            self.coin_title_label.setText(
                f"🪙 Монеты закупки №AG {ag} (№ {num}) — "
                f"{len(purchase.get('coins', []))} шт.")
        finally:
            self._showing_coins = False

    def _configure_coin_table(self, table):
        """Настройка правой таблицы монет.
        Все манипуляции шапкой (скрытие MIN/PLAN, перенос №, ширина статуса)
        выполняются под blockSignals(True); применение сохранённых настроек
        вынесено ОТДЕЛЬНО (внутри него своя блокировка) — без вложенной
        разблокировки сигналов."""
        if not table:
            return
        try:
            table.verticalHeader().setVisible(False)
        except Exception:
            pass
        try:
            table.setStyleSheet("")
            pal = table.palette()
            pal.setColor(QPalette.Base, QColor('#1a1a2e'))
            pal.setColor(QPalette.AlternateBase, QColor('#16213e'))
            pal.setColor(QPalette.Text, QColor('#e4e4ef'))
            pal.setColor(QPalette.ButtonText, QColor('#e4e4ef'))
            pal.setColor(QPalette.Highlight, QColor('#6c63ff'))
            pal.setColor(QPalette.HighlightedText, QColor('#ffffff'))
            pal.setColor(QPalette.Window, QColor('#1a1a2e'))
            table.setPalette(pal)
        except Exception:
            pass
        model = table.model()
        if model is None:
            return
        headers = list(getattr(model, 'HEADERS', []) or [])
        if not headers:
            return
        new_headers = []
        for h in headers:
            low = str(h).lower()
            if 'цена' in low and 'коллекц' in low:
                new_headers.append('Цена К')
            elif 'цена' in low and 'продаж' in low:
                new_headers.append('Цена П')
            else:
                new_headers.append(str(h))
        try:
            model.HEADERS = new_headers
            model.headerDataChanged.emit(Qt.Horizontal, 0, len(new_headers) - 1)
        except Exception:
            pass
        header = table.horizontalHeader()
        # === МАНИПУЛЯЦИИ ШАПКОЙ — ПОД БЛОКИРОВКОЙ СИГНАЛОВ ===
        header.blockSignals(True)
        try:
            # Скрываем MIN/PLAN по началу заголовка
            for i, h in enumerate(new_headers):
                low = h.lower().strip()
                hide = low.startswith('мин') or low.startswith('min') or \
                       low.startswith('план') or low.startswith('plan')
                table.setColumnHidden(i, hide)
            # Перемещаем '№' сразу после колонки статуса
            status_idx = None
            num_idx = None
            for i, h in enumerate(new_headers):
                low = h.lower().strip()
                if low == '№':
                    num_idx = i
                elif 'статус' in low:
                    status_idx = i
            if num_idx is not None and status_idx is not None:
                target_visual = header.visualIndex(status_idx) + 1
                current_visual = header.visualIndex(num_idx)
                if current_visual != target_visual:
                    header.moveSection(current_visual, target_visual)
            # Ширина колонки статуса — комбобокс без обрезки
            if status_idx is not None:
                table.setColumnWidth(status_idx, 130)
        except Exception as e:
            self.logger.debug(f"Ошибка настройки шапки таблицы монет: {e}")
        finally:
            header.blockSignals(False)
        # === СОХРАНЁННЫЕ ШИРИНЫ/ПОРЯДОК — ОТДЕЛЬНО (своя блокировка внутри) ===
        self._apply_coin_table_settings(table)
        try:
            table.setEditTriggers(
                QAbstractItemView.DoubleClicked |
                QAbstractItemView.EditKeyPressed)
        except Exception:
            pass
        # Делегаты: SilverDelegate + обёртка (заливка + целые цены)
        try:
            from .silver_delegate import SilverDelegate
            current = table.itemDelegate()
            base = current
            if isinstance(current, SilverCoinDelegateWrapper):
                base = current._original
            if not isinstance(base, SilverDelegate):
                base = SilverDelegate(table)
                try:
                    base.set_parent_tab(self)
                except Exception:
                    pass
            if not isinstance(current, SilverCoinDelegateWrapper):
                table.setItemDelegate(SilverCoinDelegateWrapper(base, table))
            else:
                current._original = base
        except Exception as e:
            self.logger.debug(f"Не удалось установить SilverDelegate: {e}")
        try:
            current = table.itemDelegate()
            if not isinstance(current, SilverCoinDelegateWrapper):
                table.setItemDelegate(SilverCoinDelegateWrapper(current, table))
        except Exception as e:
            self.logger.debug(f"Не удалось установить делегат цен: {e}")
        try:
            table.horizontalHeader().setStyleSheet("""
                QHeaderView { background-color: #16213e; }
                QHeaderView::section {
                    background-color: #16213e;
                    color: #a8a8d0;
                    padding: 4px;
                    border: none;
                    border-right: 1px solid #2a2a4a;
                    border-bottom: 2px solid #6c63ff;
                    font-weight: bold;
                }
            """)
        except Exception:
            pass
        # Перетаскивание колонок + сохранение (подключаем ОДИН раз)
        try:
            header.setSectionsMovable(True)
            header.setSectionResizeMode(QHeaderView.Interactive)
            if not getattr(table, '_cc_hdr_connected', False):
                header.sectionMoved.connect(
                    lambda *a: self._on_coin_header_changed())
                header.sectionResized.connect(
                    lambda *a: self._on_coin_header_changed())
                table._cc_hdr_connected = True
        except Exception as e:
            self.logger.debug(f"Не удалось включить перетаскивание колонок: {e}")
        # Одиночный клик = переключение чекбокса площадки (один раз)
        if not getattr(table, '_cc_platform_click_connected', False):
            try:
                table.clicked.connect(
                    lambda idx, t=table: self._on_coin_table_clicked(t, idx))
                table._cc_platform_click_connected = True
            except Exception as e:
                self.logger.debug(f"Не удалось подключить клик по чекбоксам: {e}")

    def _on_coin_table_clicked(self, table, index):
        """Одиночный клик по ячейке площадки (Авито/LAVE/Мешок/UCOIN)
        переключает значение БЕЗ попадания в маленький чекбокс.
        Остальные колонки клик только выделяет (редактирование — dblclick/F2)."""
        if not index.isValid():
            return
        model = table.model()
        keys = getattr(model, 'COLUMN_KEYS', None)
        if not keys:
            return
        col = index.column()
        if col >= len(keys):
            return
        key = keys[col]
        if key not in ('avito', 'lave', 'meshok', 'ucoin'):
            return
        row = index.row()
        pid = self._get_purchase_id_from_table(table)
        purchase = None
        for p in self.purchases:
            if p['id'] == pid:
                purchase = p
                break
        if not purchase or not (0 <= row < len(purchase['coins'])):
            return
        coin = purchase['coins'][row]
        coin[key] = not bool(coin.get(key))
        self._dirty_purchases.add(pid)
        try:
            model.dataChanged.emit(
                model.index(row, col), model.index(row, col),
                [Qt.DisplayRole, Qt.EditRole])
        except Exception:
            pass
        # Автосохранение через штатный таймер
        self._on_silver_data_changed(pid)
        state = '✅' if coin[key] else '❌'
        self.status_label.setText(
            f"🔘 {key}: {state} (монета {coin.get('number') or row + 1})")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(
            2000,
            lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    # ========== НАСТРОЙКИ ПРАВОЙ ТАБЛИЦЫ: ШИРИНЫ + ПОРЯДОК КОЛОНОК ==========
    def _load_coin_table_settings(self):
        """Загружает из ConfigDB ('silver_coin_table_settings') ширины и
        порядок колонок таблицы монет. Настройки ОБЩИЕ для всех закупок."""
        if not hasattr(self, '_coin_tbl_settings'):
            try:
                from database.config_db import get_config_db
                data = get_config_db().get('silver_coin_table_settings') or {}
                self._coin_tbl_settings = {
                    'widths': data.get('widths', {}) or {},
                    'order': data.get('order', []) or [],
                }
            except Exception as e:
                self.logger.debug(f"Не удалось загрузить настройки таблицы монет: {e}")
                self._coin_tbl_settings = {'widths': {}, 'order': []}
        return self._coin_tbl_settings

    def _cc_log_recursion(self, where):
        """Пишет стек рекурсии в logs/recursion_debug.log.
        Для RecursionError стандартный трейсбек не печатается —
        снимаем стек вручную ДО выхода из except."""
        try:
            import traceback
            from pathlib import Path
            log_dir = Path(__file__).resolve().parent.parent.parent / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            stack = ''.join(traceback.format_stack()[-60:])
            with open(log_dir / 'recursion_debug.log', 'a', encoding='utf-8') as f:
                f.write(f"=== RecursionError in {where} ===\n{stack}\n")
        except Exception:
            pass

    def _save_coin_table_settings(self):
        """Сохраняет ширины и порядок колонок активной таблицы монет в ConfigDB."""
        table = self._get_active_table()
        if table is None or table.model() is None:
            return
        header = table.horizontalHeader()
        count = table.model().columnCount()
        widths = {str(i): table.columnWidth(i) for i in range(count)}
        # order[v] = логический индекс колонки на визуальной позиции v
        order = [header.logicalIndex(v) for v in range(count)]
        try:
            from database.config_db import get_config_db
            get_config_db().set('silver_coin_table_settings',
                                {'widths': widths, 'order': order}, 'columns')
            self._coin_tbl_settings = {'widths': widths, 'order': order}
            self.logger.debug("Настройки таблицы монет (ширины+порядок) сохранены")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек таблицы монет: {e}")

    def _on_coin_header_changed(self, *args):
        """Дебаунс-сохранение колонок таблицы монет (перемещение/ресайз):
        пишет в ConfigDB через 500 мс после последнего действия."""
        if not hasattr(self, '_coin_hdr_save_timer'):
            self._coin_hdr_save_timer = QTimer()
            self._coin_hdr_save_timer.setSingleShot(True)
            self._coin_hdr_save_timer.timeout.connect(
                self._save_coin_table_settings)
        self._coin_hdr_save_timer.start(500)

    def _apply_coin_table_settings(self, table):
        """Применяет сохранённые ширины и порядок колонок к таблице монет.
        ЗАЩИТА: reentrancy-флаг _cc_applying_settings (сигналы шапки во время
        применения игнорируются) + ловушка RecursionError со записью стека."""
        if table is None or table.model() is None:
            return
        if getattr(self, '_cc_applying_settings', False):
            return
        self._cc_applying_settings = True
        try:
            settings = self._load_coin_table_settings()
            header = table.horizontalHeader()
            count = table.model().columnCount()
            header.blockSignals(True)
            try:
                for col_str, width in settings.get('widths', {}).items():
                    try:
                        col = int(col_str)
                        if 0 <= col < count and width and int(width) > 0:
                            table.setColumnWidth(col, int(width))
                    except (TypeError, ValueError):
                        pass
                order = settings.get('order', []) or []
                if len(order) == count and sorted(order) == list(range(count)):
                    for visual_pos in range(count):
                        logical = order[visual_pos]
                        current_visual = header.visualIndex(logical)
                        if current_visual != visual_pos:
                            header.moveSection(current_visual, visual_pos)
            finally:
                header.blockSignals(False)
        except RecursionError:
            self._cc_log_recursion('_apply_coin_table_settings')
        except Exception as e:
            self.logger.debug(f"Ошибка применения настроек колонок: {e}")
        finally:
            self._cc_applying_settings = False
    # ========== СОВМЕСТИМОСТЬ СО СТАРЫМИ ИМЕНАМИ МЕТОДОВ ==========
    # Старые имена вызываются из __init__, closeEvent и mixin silver_ui.py.
    # Вместо восстановления старой логики перенаправляем их на новую
    # единую систему настроек колонок (ключ 'silver_coin_table_settings').
    def _load_column_settings(self):
        """Старое имя → загрузка единых настроек таблицы монет."""
        self._load_coin_table_settings()

    def _save_column_settings(self):
        """Старое имя → сохранение единых настроек (ширины + порядок)."""
        self._save_coin_table_settings()

    def _apply_column_settings(self, table, purchase_id=None):
        """Старое имя → применение единых настроек к таблице."""
        self._apply_coin_table_settings(table)

    def _apply_global_settings_to_all_tables(self):
        """Старое имя → применение единых настроек ко всем видимым таблицам."""
        for widget in getattr(self, 'purchase_widgets', {}).values():
            table = getattr(widget, 'coin_table', None)
            if table is not None and table.isVisible():
                self._apply_coin_table_settings(table)

    def _on_column_resized(self, *args, **kwargs):
        """Старое имя → дебаунс-сохранение единых настроек."""
        self._on_coin_header_changed()

    # --- Переопределяем методы mixin, чтобы хранилище настроек было ОДНО ---
    def _apply_column_settings(self, table, purchase_id):
        """Перенаправление: применяем единые настройки таблицы монет."""
        self._apply_coin_table_settings(table)

    def _apply_global_settings_to_all_tables(self):
        """Применяем единые настройки ко всем видимым таблицам монет."""
        for purchase_id, widget in self.purchase_widgets.items():
            table = getattr(widget, 'coin_table', None)
            if table is not None and table.isVisible():
                self._apply_coin_table_settings(table)

    def _save_column_settings(self):
        """Перенаправление: сохраняем единые настройки (ширины+порядок)."""
        self._save_coin_table_settings()

    def _on_column_resized(self, purchase_id, logical_index, old_width, new_width):
        """Ресайз колонки таблицы монет (штатный сигнал mixin) —
        перенаправляем в дебаунс-сохранение единых настроек."""
        self._on_coin_header_changed()

    def _select_purchase_row(self, purchase_id):
        """Подсвечивает строку закупки в левой таблице.
        Во время создания контейнера монет (_showing_coins) не работаем —
        исключаем цепочку selectRow → currentRowChanged → _show_purchase_coins."""
        if getattr(self, '_showing_coins', False):
            return
        for row in range(self.purchases_proxy.rowCount()):
            idx = self.purchases_proxy.index(row, 0)
            src = self.purchases_proxy.mapToSource(idx).row()
            if 0 <= src < len(self._filtered_purchases) \
                    and self._filtered_purchases[src].get('id') == purchase_id:
                self.purchases_table.selectRow(row)
                self.purchases_table.setCurrentIndex(idx)
                return

    def _rebuild_ui(self):
        """Перестройка UI: обновляем левую таблицу и показываем монеты
        текущей (или первой) закупки.
        ЗАЩИТА ОТ РЕКУРСИИ: флаг _rebuilding блокирует повторный вход —
        сброс модели дёргает selectionChanged → _on_purchase_row_changed →
        _show_purchase_coins, что раньше замыкалось в бесконечный цикл."""
        if getattr(self, '_rebuilding', False):
            return
        self._rebuilding = True
        try:
            self.purchases_model.set_data(self._filtered_purchases)
            pid = getattr(self, '_current_purchase_id', None)
            ids = [p.get('id') for p in self._filtered_purchases]
            if pid not in ids:
                pid = ids[0] if ids else None
            if pid is not None:
                purchase = next((p for p in self._filtered_purchases
                                 if p.get('id') == pid), None)
                if purchase:
                    self._current_purchase_id = None   # сброс для перестройки
                    self._show_purchase_coins(purchase)
                    self._select_purchase_row(pid)
            else:
                old = getattr(self, '_current_coin_container', None)
                if old is not None:
                    try:
                        self.coin_area_layout.removeWidget(old)
                        old.deleteLater()
                    except Exception:
                        pass
                self._current_coin_container = None
                self._current_purchase_id = None
                self.purchase_widgets = {}
                self.coin_title_label.setText("🪙 Монеты закупки: —")
            self._update_stats()
        finally:
            self._rebuilding = False
    # ===== СОВМЕСТИМОСТЬ: аккордеон больше не нужен =====
    def _expand_purchase(self, purchase_id):
        """В мастер-детали раскрытие не нужно — монеты всегда видны справа."""
        self._select_purchase_row(purchase_id)

    def _collapse_all_purchases(self):
        pass

    def toggle_purchase(self, purchase_id):
        self._select_purchase_row(purchase_id)

    def expand_all(self):
        pass

    def collapse_all(self):
        pass

    def scroll_to_top(self):
        if getattr(self, 'purchases_table', None) is not None:
            self.purchases_table.scrollToTop()

    def scroll_to_bottom(self):
        if getattr(self, 'purchases_table', None) is not None:
            self.purchases_table.scrollToBottom()