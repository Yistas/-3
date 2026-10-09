# -*- coding: utf-8 -*-
"""
Вкладка "📊 Статистика продаж" внутри "💱 Обмен/Продажа".
Срезы: ПО СТРАНАМ / ПО КОНТИНЕНТАМ / ПО ГОДАМ (подвкладки "По закупкам" нет).

Источники (соединение по ключу №Зак = №):
- закладка "Закупки":  №Зак, Страна, Континент, ГОД, КОЛ, Обмен, Продано, Сумма;
- закладка "Статистика": №, Кол-во, Затраты (автопоиск источника).
Читает АКТИВНЫЕ + АРХИВНЫЕ закупки.

Колонки срезов: Группа | Количество | Продано | На обмене | Продажи.
Колонка ПРИБЫЛЬ удалена; "Продажи" выводятся со знаком «+» и цветом.
Сортировка ПО ВОЗРАСТАНИЮ (страны/континенты — по продажам, годы — по году).
Фильтр AG по умолчанию: "Пусто (без серебра)".
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QTableView, QHeaderView, QAbstractItemView,
    QPushButton, QCheckBox, QComboBox
)
from PySide6.QtCore import (Qt, QAbstractTableModel, QSortFilterProxyModel,
                            QModelIndex, QTimer)
from PySide6.QtGui import QColor, QPalette, QKeyEvent

# === КАРТА ПОЛЕЙ МОДЕЛИ Purchase (сверена со схемой таблицы purchases) ===
FIELD_MAP = {
    'num':       ('purchase_number', 'number', 'zak_number', 'num'),
    'country':   ('country', 'country_name'),
    'continent': ('continent',),
    'year':      ('year',),
    'kol':       ('quantity', 'kol', 'kolichestvo', 'pieces', 'coins_count'),
    'exchange':  ('ucoin_exchange_count', 'exchange_count', 'obmen_count',
                  'exchange_qty', 'obmen_kol', 'ucoin_exchange', 'exchange',
                  'obmen', 'na_obmene'),
    'sold':      ('sold_count', 'prodano', 'sold_qty', 'count_sold', 'sold'),
    'sale_sum':  ('sold_sum', 'sale_sum', 'sales_sum', 'summa_prodazh',
                  'sale_amount', 'prodan_sum'),
    'buy_sum':   ('total', 'purchase_sum', 'sum', 'amount', 'price',
                  'costs', 'zatrati'),
}


class SalesGroupModel(QAbstractTableModel):
    """Срез статистики (страны / континенты / годы):
    [группа, количество, продано, на обмене, продажи].
    Колонки ПРИБЫЛЬ нет; "Продажи" — со знаком «+» и цветом."""

    HEADERS = ["Группа", "Количество", "Продано", "На обмене", "Продажи"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows or []
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return str(row[0] if row[0] not in (None, '') else '—')
            if col in (1, 2, 3):
                return str(int(row[col] or 0))
            if col == 4:
                return f"{float(row[4] or 0):+,.0f}"
        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignLeft | Qt.AlignVCenter
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.ForegroundRole:
            if col == 4:
                return QColor('#90ee90') if float(row[4] or 0) > 0 \
                    else QColor('#ff9090')
            return None
        if role == Qt.UserRole:
            if col == 0:
                return str(row[0] or '').lower()
            if col in (1, 2, 3):
                return float(int(row[col] or 0))
            if col == 4:
                return float(row[4] or 0)
        return None


class SalesStatsProxy(QSortFilterProxyModel):
    """Сортировка по любой колонке."""

    def lessThan(self, left, right):
        ld = left.data(Qt.UserRole)
        rd = right.data(Qt.UserRole)
        try:
            return float(ld) < float(rd)
        except (TypeError, ValueError):
            return str(ld).lower() < str(rd).lower()


class SalesStatsTab(QWidget):
    """Статистика продаж: Закупки ⋈ Статистика (№Зак = №),
    срезы по странам / континентам / годам."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.SalesStatsTab')
        self._last_load = None
        self._stats_source = '—'
        self.init_ui()
        QTimer.singleShot(200, self.load_data)

    # ================= UI =================
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.addWidget(self._create_chips())
        # === ПАНЕЛЬ УПРАВЛЕНИЯ ===
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.active_only_check = QCheckBox("Только активные (без архива)")
        self.active_only_check.setChecked(False)
        self.active_only_check.setStyleSheet("color: #a8a8d0; font-size: 11px;")
        self.active_only_check.stateChanged.connect(lambda: self.load_data())
        bar.addWidget(self.active_only_check)
        # === ФИЛЬТР ПО КОЛОНКЕ AG (по умолчанию — пусто) ===
        ag_label = QLabel("AG:")
        ag_label.setStyleSheet("color: #a8a8d0; font-size: 11px;")
        bar.addWidget(ag_label)
        self.ag_filter_combo = QComboBox()
        self.ag_filter_combo.addItem("Пусто (без серебра)", 'empty')
        self.ag_filter_combo.addItem("Отмечено (только серебро)", 'ag')
        self.ag_filter_combo.addItem("Все (игнорировать AG)", 'all')
        self.ag_filter_combo.setCurrentIndex(0)
        self.ag_filter_combo.setToolTip(
            "Фильтр по колонке AG закупок:\n"
            "• Пусто — только закупки БЕЗ метки AG (по умолчанию)\n"
            "• Отмечено — только закупки с меткой AG (серебро)\n"
            "• Все — метка AG игнорируется")
        self.ag_filter_combo.setStyleSheet("""
            QComboBox {
                background-color: #16213e; color: #e4e4ef;
                border: 1px solid #2a2a4a; border-radius: 6px;
                padding: 2px 8px; font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a2e; color: #e4e4ef;
                border: 1px solid #3d3d5c;
                selection-background-color: #6c63ff;
                selection-color: #ffffff;
            }
        """)
        self.ag_filter_combo.currentIndexChanged.connect(lambda: self.load_data())
        bar.addWidget(self.ag_filter_combo)
        bar.addStretch()
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.setFixedSize(110, 28)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #16213e; color: #e4e4ef;
                border: 1px solid #2a2a4a; border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #6c63ff; color: #ffffff;
                border-color: #6c63ff;
            }
        """)
        refresh_btn.clicked.connect(self.load_data)
        bar.addWidget(refresh_btn)
        bar_wrap = QWidget()
        bar_wrap.setLayout(bar)
        layout.addWidget(bar_wrap)
        # === ТРИ СРЕЗА ===
        self.tables_tab = QTabWidget()
        self.country_model = SalesGroupModel(self)
        self.continent_model = SalesGroupModel(self)
        self.year_model = SalesGroupModel(self)
        self.country_table = self._make_table(self.country_model)
        self.continent_table = self._make_table(self.continent_model)
        self.year_table = self._make_table(self.year_model)
        self.country_table.horizontalHeader().setToolTip(
            "Количество = сумма КОЛ (всего монет)\n"
            "Продажи = сумма проданного в ₽ (со знаком «+»)\n"
            "Сортировка по возрастанию; клик по заголовку — своя сортировка")
        self.tables_tab.addTab(self.country_table, "🌍 По странам")
        self.tables_tab.addTab(self.continent_table, "🗺 По континентам")
        self.tables_tab.addTab(self.year_table, "📅 По годам")
        self.tables_tab.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2a2a4a;
                background-color: #1a1a2e;
            }
            QTabBar::tab {
                background-color: #0f0f1a; color: #8888aa;
                padding: 5px 14px; min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: #16213e; color: #e4e4ef;
                border-bottom: 2px solid #6c63ff;
            }
            QTabBar::tab:hover:!selected { background-color: #1f2b47; }
        """)
        layout.addWidget(self.tables_tab, 1)
        # === СТАТУС ===
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        layout.addWidget(self.status_label)

    def _create_chips(self):
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
            val.setStyleSheet(
                "color: #e4e4ef; font-size: 13px; font-weight: bold;")
            box.addWidget(cap)
            box.addWidget(val)
            row.addLayout(box)
            return val

        self.chip_purchases = chip("ЗАКУПОК (шт)")
        self.chip_qty = chip("МОНЕТ (шт)")
        self.chip_sold = chip("ПРОДАНО (шт)")
        self.chip_exchange = chip("НА ОБМЕНЕ (шт)")
        self.chip_ag = chip("ИЗ НИХ AG")
        self.chip_sale = chip("ПРОДАЖИ (₽)")
        self.chip_costs = chip("ЗАТРАТЫ (₽)")
        row.addStretch()
        return frame

    def _make_table(self, model):
        proxy = SalesStatsProxy(self)
        proxy.setSourceModel(model)
        proxy.setSortRole(Qt.UserRole)
        table = QTableView()
        table.setModel(proxy)
        table._stats_proxy = proxy          # защита от GC
        table.setSortingEnabled(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSortIndicatorShown(True)
        pal = table.palette()
        pal.setColor(QPalette.Base, QColor('#1a1a2e'))
        pal.setColor(QPalette.AlternateBase, QColor('#16213e'))
        pal.setColor(QPalette.Text, QColor('#e4e4ef'))
        pal.setColor(QPalette.ButtonText, QColor('#e4e4ef'))
        pal.setColor(QPalette.Highlight, QColor('#6c63ff'))
        pal.setColor(QPalette.HighlightedText, QColor('#ffffff'))
        pal.setColor(QPalette.Window, QColor('#1a1a2e'))
        table.setPalette(pal)
        table.setStyleSheet("")
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
        widths = [220, 110, 90, 110, 140]
        for i, w in enumerate(widths):
            table.setColumnWidth(i, w)
        return table

    # ================= ВСПОМОГАТЕЛЬНЫЕ =================
    @staticmethod
    def _is_archived(p):
        for attr in ('is_archived', 'archived', 'in_archive', 'archive'):
            v = getattr(p, attr, None)
            if v is not None:
                return bool(v)
        status = str(getattr(p, 'status', '') or '').lower()
        return ('archiv' in status) or ('архив' in status)

    @staticmethod
    def _first(obj, names, default=None):
        for n in names:
            v = getattr(obj, n, None)
            if v is not None:
                return v
        return default

    @staticmethod
    def _parse_int(v):
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        if not s:
            return 0
        if '/' in s:
            s = s.split('/')[0]
        digits = ''
        for ch in s:
            if ch.isdigit():
                digits += ch
            elif digits:
                break
        return int(digits) if digits else 0

    @staticmethod
    def _float(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _norm(v):
        return str(v if v is not None else '').strip()

    def _stats_keys(self, num):
        keys = {self._norm(num)}
        try:
            keys.add(str(int(float(self._norm(num)))))
        except (TypeError, ValueError):
            pass
        return keys

    def _country_name(self, p):
        rel = getattr(p, 'import_country', None)
        if rel is not None:
            name = getattr(rel, 'name', None)
            if name:
                return str(name)
        for attr in ('country', 'country_name'):
            v = getattr(p, attr, None)
            if v:
                return str(v)
        return '—'

    def _exchange_count(self, p):
        """Монет НА ОБМЕНЕ: ucoin_exchange_count; если счётчик пуст,
        но флаг ucoin_exchange стоит — считаем 1 (как «✅» в закупках)."""
        count = self._parse_int(self._first(
            p, ('ucoin_exchange_count', 'exchange_count', 'obmen_count',
                'exchange_qty', 'obmen_kol')))
        if count > 0:
            return count
        flag = self._first(p, ('ucoin_exchange', 'exchange', 'obmen'))
        return 1 if bool(flag) else 0

    def _dump_schema(self, Purchase):
        """Один раз за сессию пишет схему Purchase в logs/sales_stats_schema.log."""
        if getattr(self, '_schema_dumped', False):
            return
        self._schema_dumped = True
        try:
            cols = [c.name for c in Purchase.__table__.columns]
            self.logger.info(f"Purchase columns: {cols}")
            log_dir = Path(__file__).resolve().parent.parent.parent / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / 'sales_stats_schema.log', 'w',
                      encoding='utf-8') as f:
                f.write("Purchase columns:\n")
                for c in cols:
                    f.write(f"  - {c}\n")
                f.write("\nSample rows (5):\n")
                for p in self.db_manager.session.query(Purchase).limit(5):
                    row = {c: getattr(p, c) for c in cols}
                    f.write(json.dumps(row, ensure_ascii=False,
                                       default=str) + "\n")
        except Exception as e:
            self.logger.debug(f"Не удалось записать схему: {e}")

    def _iter_all_purchases(self, Purchase):
        """Все закупки: АКТИВНЫЕ + АРХИВНЫЕ (таблицы с archive/arhiv в имени).
        Возвращает список кортежей (закупка, флаг_архива)."""
        rows = []
        try:
            for p in self.db_manager.session.query(Purchase).all():
                rows.append((p, self._is_archived(p)))
        except Exception as e:
            self.logger.error(f"Ошибка чтения Purchase: {e}")
            return rows
        seen = {getattr(p, 'id', None) for p, _ in rows}
        try:
            from database import models as db_models
            for attr in dir(db_models):
                cls = getattr(db_models, attr, None)
                if not (isinstance(cls, type) and hasattr(cls, '__table__')):
                    continue
                low = attr.lower()
                tlow = cls.__table__.name.lower()
                if not ('archive' in low or 'arhiv' in low or
                        'archive' in tlow or 'arhiv' in tlow):
                    continue
                cols = {c.name.lower() for c in cls.__table__.columns}
                if not (cols & {'number', 'purchase_number', 'zak_number',
                                'num', 'total', 'purchase_sum', 'sum'}):
                    continue
                try:
                    added = 0
                    for rec in self.db_manager.session.query(cls).all():
                        rid = getattr(rec, 'id', None)
                        if rid in seen:
                            continue
                        rows.append((rec, True))
                        seen.add(rid)
                        added += 1
                    if added:
                        self.logger.info(
                            f"📦 Архив: {added} закупок из {cls.__name__}")
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug(f"Поиск архивных таблиц: {e}")
        return rows

    # ================= ИСТОЧНИК ЗАТРАТ =================
    @staticmethod
    def _stat_from_dict(rec):
        """Извлекает (№, кол-во, затраты) из словаря/ORM-строки статистики."""
        if not isinstance(rec, dict):
            return None
        num = qty = costs = None
        for k, v in rec.items():
            lk = str(k).lower().strip()
            if num is None and lk in ('№', '№зак', 'number', 'num', 'zak',
                                      'purchase_number', 'zak_number'):
                num = v
            if qty is None and lk in ('кол-во', 'кол', 'quantity',
                                      'count', 'qty', 'kolvo'):
                qty = v
            if costs is None and lk in ('затраты', 'costs', 'cost',
                                        'expenses', 'zatrati'):
                costs = v
        for k, v in rec.items():
            lk = str(k).lower()
            if num is None and ('№' in str(k) or 'зак' in lk or
                                'number' in lk):
                num = v
            if costs is None and ('затрат' in lk or 'cost' in lk or
                                  'expense' in lk):
                costs = v
            if qty is None and (('кол' in lk and 'коллекц' not in lk) or
                                lk in ('count', 'quantity', 'qty')):
                qty = v
        if num is None or costs is None:
            return None
        return (SalesStatsTab._norm(num),
                SalesStatsTab._parse_int(qty),
                SalesStatsTab._float(costs))

    def _load_statistics_map(self):
        """Автопоиск данных вкладки "Статистика" (№, Кол-во, Затраты):
        1) явные модели; 2) интроспекция моделей БД с колонкой затрат
        (КРОМЕ Purchase/Coin); 3) кэш-JSON в data/ и data/cache/;
        иначе — фолбэк «затраты = сумма закупки» (флаг use_fallback)."""
        result = {}
        try:
            from database import models as db_models
            candidates = []
            for name in ('Statistics', 'Statistic', 'PurchaseStatistics',
                         'PurchaseStat', 'StatsCache', 'StatCache'):
                cls = getattr(db_models, name, None)
                if cls is not None and hasattr(cls, '__table__'):
                    candidates.append(cls)
            if not candidates:
                for attr in dir(db_models):
                    cls = getattr(db_models, attr, None)
                    if not (isinstance(cls, type) and hasattr(cls, '__table__')):
                        continue
                    if attr.lower() in ('purchase', 'purchasearchive',
                                        'silverpurchase', 'coin', 'silvercoin'):
                        continue
                    cols = [c.name.lower() for c in cls.__table__.columns]
                    if any(('затрат' in c or 'cost' in c or 'expense' in c)
                           for c in cols):
                        candidates.append(cls)
            for cls in candidates:
                try:
                    rows = self.db_manager.session.query(cls).all()
                except Exception:
                    continue
                for rec in rows:
                    try:
                        d = {c.name: getattr(rec, c.name)
                             for c in cls.__table__.columns}
                    except Exception:
                        continue
                    extracted = self._stat_from_dict(d)
                    if extracted is None:
                        continue
                    num, qty, costs = extracted
                    for k in self._stats_keys(num):
                        result[k] = {'quantity': qty, 'costs': costs}
                if result:
                    self._stats_source = f'БД: {cls.__name__}'
                    return result
        except Exception as e:
            self.logger.debug(f"Статистика из БД недоступна: {e}")
        try:
            from utils.paths import paths_instance as paths
            candidates = [
                paths.get_data_dir() / 'statistics_cache.json',
                paths.get_data_dir() / 'statistics.json',
                paths.get_data_dir() / 'cache' / 'statistics.json',
                paths.get_root_dir() / 'data' / 'statistics_cache.json',
            ]
            for folder in (paths.get_data_dir(),
                           paths.get_data_dir() / 'cache'):
                try:
                    for path in sorted(Path(folder).glob('*.json')):
                        if path not in candidates:
                            candidates.append(path)
                except Exception:
                    pass
            for path in candidates:
                if path is None or not Path(path).exists():
                    continue
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                records = data if isinstance(data, list) else \
                    data.get('records', data.get('statistics',
                                                 data.get('data', [])))
                if not isinstance(records, list):
                    continue
                for rec in records:
                    extracted = self._stat_from_dict(rec)
                    if extracted is None:
                        continue
                    num, qty, costs = extracted
                    for k in self._stats_keys(num):
                        result[k] = {'quantity': qty, 'costs': costs}
                if result:
                    self._stats_source = f'кэш: {Path(path).name}'
                    return result
        except Exception as e:
            self.logger.debug(f"Статистика из кэша недоступна: {e}")
        self._stats_source = 'Purchase: затраты = сумма закупки'
        return result

    # ================= СБОРКА СРЕЗОВ =================
    def load_data(self):
        """Строит срезы по странам / континентам / годам.
        Агрегат строки: [количество, продано, на обмене, продажи].
        Читает активные + архив; фильтр AG по умолчанию 'empty'."""
        try:
            from database.models import Purchase
        except Exception as e:
            self.status_label.setText(f"❌ Модель Purchase недоступна: {e}")
            return
        self._dump_schema(Purchase)
        active_only = self.active_only_check.isChecked()
        ag_mode = 'empty'
        if getattr(self, 'ag_filter_combo', None) is not None:
            ag_mode = self.ag_filter_combo.currentData() or 'empty'
        stats = self._load_statistics_map()
        use_fallback_costs = stats == {}
        country_agg = {}
        continent_agg = {}
        year_agg = {}
        tot_p = tot_qty = tot_sold = tot_exch = tot_arch = tot_ag = 0
        tot_sale = tot_costs = 0.0
        no_stats_count = 0
        try:
            all_rows = self._iter_all_purchases(Purchase)
            for p, archived in all_rows:
                if active_only and archived:
                    continue
                ag_val = bool(getattr(p, 'ag', False) or False)
                if ag_mode == 'empty' and ag_val:
                    continue
                if ag_mode == 'ag' and not ag_val:
                    continue
                num = self._norm(self._first(p, FIELD_MAP['num']))
                country = self._country_name(p)
                continent = str(self._first(p, FIELD_MAP['continent'], '') or '—')
                year = str(self._first(p, FIELD_MAP['year'], '') or '—')
                kol = self._parse_int(self._first(p, FIELD_MAP['kol']))
                exchange = self._exchange_count(p)
                sold = self._parse_int(self._first(p, FIELD_MAP['sold']))
                sale_sum = self._float(self._first(p, FIELD_MAP['sale_sum']))
                buy_sum = self._float(self._first(p, FIELD_MAP['buy_sum']))
                # === ЗАТРАТЫ (только для чипа «ЗАТРАТЫ (₽)») ===
                costs_total = 0.0
                st = None
                for k in self._stats_keys(num):
                    if k in stats:
                        st = stats[k]
                        break
                if st is not None:
                    costs_total = float(st.get('costs') or 0)
                elif use_fallback_costs:
                    costs_total = buy_sum
                else:
                    no_stats_count += 1
                tot_costs += costs_total
                # === АГРЕГАЦИЯ: [количество, продано, на обмене, продажи] ===
                for key, store in ((country, country_agg),
                                   (continent, continent_agg),
                                   (year, year_agg)):
                    a = store.setdefault(key, [0, 0, 0, 0.0])
                    a[0] += kol
                    a[1] += sold
                    a[2] += exchange
                    a[3] += sale_sum
                tot_p += 1
                tot_qty += kol
                tot_sold += sold
                tot_exch += exchange
                tot_arch += 1 if archived else 0
                tot_ag += 1 if ag_val else 0
                tot_sale += sale_sum
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка загрузки статистики продаж: {e}")
            self.status_label.setText(f"❌ Ошибка загрузки: {str(e)[:60]}")
            return
        # === ЗАПОЛНЯЕМ МОДЕЛИ (сортировка ВОЗРАСТАЮЩАЯ) ===
        self.country_model.set_rows(self._agg_rows(country_agg))
        self.continent_model.set_rows(self._agg_rows(continent_agg))
        self.year_model.set_rows(self._agg_rows(year_agg, by_year=True))
        # === ЧИПЫ ===
        self.chip_purchases.setText(str(tot_p))
        self.chip_qty.setText(str(tot_qty))
        self.chip_sold.setText(str(tot_sold))
        self.chip_exchange.setText(str(tot_exch))
        self.chip_ag.setText(str(tot_ag))
        self.chip_sale.setText(f"{tot_sale:,.0f}")
        self.chip_costs.setText(f"{tot_costs:,.0f}")
        self._last_load = datetime.now()
        mode = "только активные" if active_only else "активные + архив"
        ag_names = {'empty': 'AG пусто', 'ag': 'AG отмечено', 'all': 'AG все'}
        warn = f" | ⚠️ без затрат: {no_stats_count}" if no_stats_count else ""
        self.status_label.setText(
            f"✅ Закупок: {tot_p} (архив: {tot_arch}, AG: {tot_ag}) | "
            f"{mode} | фильтр: {ag_names.get(ag_mode, ag_mode)} | "
            f"Затраты из: {self._stats_source}{warn}")

    @staticmethod
    def _sort_num(v):
        try:
            return float(str(v).strip())
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _agg_rows(store, by_year=False):
        """Сортировка ВОЗРАСТАЮЩАЯ: страны/континенты — по продажам,
        годы — по году. Клик по заголовку даёт свою сортировку."""
        rows = [[name] + list(a) for name, a in store.items()]
        if by_year:
            rows.sort(key=lambda r: SalesStatsTab._sort_num(r[0]))
        else:
            rows.sort(key=lambda r: r[4])
        return rows

    # ================= СОБЫТИЯ =================
    def showEvent(self, event):
        """Автообновление при открытии вкладки (если данные старше 2 мин)."""
        super().showEvent(event)
        if self._last_load is None or \
                (datetime.now() - self._last_load).total_seconds() > 120:
            QTimer.singleShot(100, self.load_data)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F5:
            self.load_data()
            event.accept()
            return
        super().keyPressEvent(event)