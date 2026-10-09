# -*- coding: utf-8 -*-

"""
Справочник по определению дат на монетах
Работает офлайн, содержит правила конвертации для разных стран
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QComboBox, QLineEdit,
                               QTextEdit, QTabWidget, QGridLayout, QFrame,
                               QScrollArea, QSplitter, QMessageBox, QApplication)
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QFont


class DateConverterTab(QWidget):
    """Вкладка для конвертации дат с монет (офлайн-справочник)"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📅 Справочник по определению дат на монетах")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        title.setFixedHeight(40)
        layout.addWidget(title)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - список стран
        left_panel = self.create_country_list()
        splitter.addWidget(left_panel)
        
        # Правая панель - информация и калькулятор
        right_panel = self.create_info_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([220, 780])
        layout.addWidget(splitter)
        
        # Показать первую страну
        if self.all_country_buttons:
            self.all_country_buttons[0][0].click()
    
    def create_country_list(self):
        """Создает список стран с закладками"""
        panel = QWidget()
        panel.setFixedWidth(220)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("🌍 Календари")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #e0e0e0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск...")
        self.search_input.textChanged.connect(self.filter_countries)
        layout.addWidget(self.search_input)
        
        # Список с скроллом
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        self.country_list = QWidget()
        self.country_layout = QVBoxLayout()
        self.country_layout.setSpacing(1)
        self.country_layout.setContentsMargins(2, 2, 2, 2)
        self.country_layout.addStretch()
        self.country_list.setLayout(self.country_layout)
        
        scroll.setWidget(self.country_list)
        layout.addWidget(scroll)
        
        # Наполняем список
        self.all_country_buttons = []
        for country_data in COUNTRY_DATE_RULES:
            btn = QPushButton(f"{country_data['flag']} {country_data['name']}")
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    background-color: #fafafa;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border-color: #4a6fa5;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, d=country_data: self.show_country_info(d))
            self.country_layout.insertWidget(self.country_layout.count() - 1, btn)
            self.all_country_buttons.append((btn, country_data))
        
        return panel
    
    def create_info_panel(self):
        """Создает панель с информацией и калькулятором"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        panel.setLayout(layout)
        
        # Заголовок
        self.info_title = QLabel()
        self.info_title.setStyleSheet("""
            font-weight: bold;
            font-size: 18px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        self.info_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_title)
        
        # Контент с прокруткой
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)
        content.setLayout(content_layout)
        
        # Группа: Информация
        info_group = QGroupBox("📖 Система летоисчисления")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; padding-top: 10px; }")
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMinimumHeight(150)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        content_layout.addWidget(info_group)
        
        # Группа: Примеры
        examples_group = QGroupBox("📝 Примеры дат на монетах")
        examples_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; padding-top: 10px; }")
        self.examples_text = QTextEdit()
        self.examples_text.setReadOnly(True)
        self.examples_text.setMinimumHeight(120)
        self.examples_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        examples_layout = QVBoxLayout()
        examples_layout.addWidget(self.examples_text)
        examples_group.setLayout(examples_layout)
        content_layout.addWidget(examples_group)
        
        # Группа: Калькулятор
        calc_group = QGroupBox("🔢 Калькулятор перевода дат")
        calc_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; padding-top: 10px; }")
        calc_layout = QGridLayout()
        calc_layout.setSpacing(8)
        
        calc_layout.addWidget(QLabel("Дата на монете:"), 0, 0)
        
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("Введите дату...")
        self.date_input.setMinimumHeight(35)
        calc_layout.addWidget(self.date_input, 0, 1)
        
        # Панель с символами (всегда видна)
        self.symbol_panel = QFrame()
        self.symbol_panel.setFrameShape(QFrame.StyledPanel)
        self.symbol_panel.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        self.symbol_panel_layout = QVBoxLayout()
        self.symbol_panel_layout.setSpacing(3)
        self.symbol_panel.setLayout(self.symbol_panel_layout)
        calc_layout.addWidget(self.symbol_panel, 1, 1)
        
        calc_layout.addWidget(QLabel("Результат:"), 2, 0)
        self.result_label = QLabel("—")
        self.result_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #28a745;
            padding: 8px;
            background-color: #f0fff0;
            border: 1px solid #28a745;
            border-radius: 3px;
        """)
        self.result_label.setMinimumHeight(40)
        self.result_label.setAlignment(Qt.AlignCenter)
        calc_layout.addWidget(self.result_label, 2, 1)
        
        convert_btn = QPushButton("🔄 Перевести")
        convert_btn.clicked.connect(self.convert_date)
        convert_btn.setMinimumHeight(40)
        convert_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 3px; font-size: 14px;")
        calc_layout.addWidget(convert_btn, 3, 0, 1, 2)
        
        calc_group.setLayout(calc_layout)
        content_layout.addWidget(calc_group)
        
        # Ссылка на онлайн-сервис
        self.online_link = QPushButton("🌐 Открыть онлайн-конвертер")
        self.online_link.clicked.connect(self.open_online_converter)
        self.online_link.setMinimumHeight(40)
        self.online_link.setStyleSheet("background-color: #4a6fa5; color: white; font-weight: bold; border-radius: 3px; font-size: 13px;")
        self.online_link.setVisible(False)
        content_layout.addWidget(self.online_link)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return panel
    
    def filter_countries(self, text):
        """Фильтрует список по поисковому запросу"""
        search_text = text.lower()
        for btn, country_data in self.all_country_buttons:
            if search_text in country_data['name'].lower():
                btn.show()
            else:
                btn.hide()
    
    def show_country_info(self, country_data):
        """Показывает информацию о выбранном календаре"""
        self.current_country = country_data
        
        self.info_title.setText(f"{country_data['flag']} {country_data['name']}")
        self.info_text.setText(country_data.get('info', 'Нет информации'))
        self.examples_text.setText(country_data.get('examples', 'Нет примеров'))
        
        self.date_input.setText("")
        self.result_label.setText("—")
        
        self.current_formula = country_data.get('formula')
        self.current_offset = country_data.get('offset', 0)
        self.current_is_reverse = country_data.get('is_reverse', False)
        
        if country_data.get('online_url'):
            self.online_link.setVisible(True)
            self.online_url = country_data['online_url']
        else:
            self.online_link.setVisible(False)
        
        self.update_symbol_panel(country_data)
    
    def update_symbol_panel(self, country_data):
        """Обновляет панель символов"""
        while self.symbol_panel_layout.count():
            child = self.symbol_panel_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        symbols = country_data.get('symbols', [])
        
        if not symbols:
            label = QLabel("Для этого календаря используются обычные цифры (0-9)")
            label.setStyleSheet("font-size: 11px; color: #666; padding: 5px;")
            self.symbol_panel_layout.addWidget(label)
            return
        
        label = QLabel("Нажмите для вставки:")
        label.setStyleSheet("font-size: 10px; color: #666; margin-bottom: 3px;")
        self.symbol_panel_layout.addWidget(label)
        
        for row_symbols in symbols:
            row_widget = QWidget()
            row_layout = QHBoxLayout()
            row_layout.setSpacing(3)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_widget.setLayout(row_layout)
            
            for symbol_data in row_symbols:
                if isinstance(symbol_data, tuple):
                    symbol, value = symbol_data
                else:
                    symbol = symbol_data
                    value = symbol_data
                
                btn = QPushButton(symbol)
                btn.setFixedSize(42, 35)
                btn.setToolTip(f"Значение: {value}")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        border: 1px solid #ccc;
                        border-radius: 3px;
                        font-size: 18px;
                    }
                    QPushButton:hover {
                        background-color: #4a6fa5;
                        color: white;
                        border-color: #2c4a75;
                    }
                """)
                btn.clicked.connect(lambda checked, v=value: self.insert_symbol(str(v)))
                row_layout.addWidget(btn)
            
            row_layout.addStretch()
            self.symbol_panel_layout.addWidget(row_widget)
    
    def insert_symbol(self, symbol):
        """Вставляет символ в поле ввода"""
        current_text = self.date_input.text()
        cursor_pos = self.date_input.cursorPosition()
        new_text = current_text[:cursor_pos] + symbol + current_text[cursor_pos:]
        self.date_input.setText(new_text)
        self.date_input.setCursorPosition(cursor_pos + len(symbol))
        self.date_input.setFocus()
    
    def convert_date(self):
        """Конвертирует дату по формуле"""
        if not hasattr(self, 'current_country'):
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите календарь")
            return
        
        date_text = self.date_input.text().strip()
        if not date_text:
            QMessageBox.warning(self, "Предупреждение", "Введите дату")
            return
        
        try:
            year = int(date_text)
            
            if self.current_is_reverse:
                result = year + self.current_offset
                self.result_label.setText(f"{result} год")
            elif self.current_formula:
                result = eval(self.current_formula, {"year": year, "x": year})
                self.result_label.setText(f"{result} г. н.э. (примерно)")
            else:
                result = year - self.current_offset
                self.result_label.setText(f"{result} г. н.э. (примерно)")
                
        except ValueError:
            QMessageBox.warning(self, "Предупреждение", "Введите корректное число")
        except Exception as e:
            QMessageBox.warning(self, "Предупреждение", f"Ошибка при расчете: {e}")
    
    def open_online_converter(self):
        """Открывает онлайн-конвертер в браузере"""
        if hasattr(self, 'online_url') and self.online_url:
            import webbrowser
            webbrowser.open(self.online_url)


# ===== ДАННЫЕ ПО КАЛЕНДАРЯМ =====

COUNTRY_DATE_RULES = [
    
    # ===== БЛИЖНИЙ ВОСТОК =====
    {
        "name": "Афганский (солнечная хиджра)",
        "flag": "🇦🇫",
        "info": """<b>Солнечная хиджра (Solar Hijri)</b>

Формула: <b>Год хиджры + 621 = год н.э.</b>

Используется в Афганистане с 1919 года.""",
        "examples": """• 1298 г.х. ≈ 1919 г.н.э.
• 1352 г.х. ≈ 1973 г.н.э.
• 1402 г.х. ≈ 2023 г.н.э.""",
        "offset": 621,
        "symbols": [
            [("۰", "0"), ("۱", "1"), ("۲", "2"), ("۳", "3"), ("۴", "4")],
            [("۵", "5"), ("۶", "6"), ("۷", "7"), ("۸", "8"), ("۹", "9")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=afghanistan.php&lang=ru"
    },
    
    {
        "name": "Персидский (солнечная хиджра)",
        "flag": "🇮🇷",
        "info": """<b>Солнечная хиджра (Solar Hijri)</b>

Формула: <b>Год хиджры + 621 = год н.э.</b>

Используется в Иране с 1925 года.
Год начинается 20-21 марта.""",
        "examples": """• 1347 г.х. ≈ 1968 г.н.э.
• 1358 г.х. ≈ 1979 г.н.э.
• 1402 г.х. ≈ 2023 г.н.э.
• 1403 г.х. ≈ 2024 г.н.э.""",
        "offset": 621,
        "symbols": [
            [("۰", "0"), ("۱", "1"), ("۲", "2"), ("۳", "3"), ("۴", "4")],
            [("۵", "5"), ("۶", "6"), ("۷", "7"), ("۸", "8"), ("۹", "9")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=iran.php&lang=ru"
    },
    
    {
        "name": "Исламский (лунная хиджра)",
        "flag": "☪️",
        "info": """<b>Лунная хиджра (Islamic Hijri)</b>

Формула: <b>Год хиджры × 0.97 + 622 ≈ год н.э.</b>

Используется в Саудовской Аравии, странах Персидского залива, Северной Африки.
Год короче григорианского на ≈11 дней.""",
        "examples": """• 1200 г.х. ≈ 1786 г.н.э.
• 1300 г.х. ≈ 1883 г.н.э.
• 1400 г.х. ≈ 1980 г.н.э.
• 1440 г.х. ≈ 2019 г.н.э.
• 1446 г.х. ≈ 2024 г.н.э.""",
        "formula": "int(year * 0.97 + 622)",
        "symbols": [
            [("٠", "0"), ("١", "1"), ("٢", "2"), ("٣", "3"), ("٤", "4")],
            [("٥", "5"), ("٦", "6"), ("٧", "7"), ("٨", "8"), ("٩", "9")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=islamic.php&lang=ru"
    },
    
    {
        "name": "Еврейский (иудейский)",
        "flag": "🇮🇱",
        "info": """<b>Еврейский календарь (Hebrew Calendar, AM)</b>

Формула: <b>Еврейский год - 3760 = год н.э.</b>

Начало летоисчисления: 3761 г. до н.э. (сотворение мира).
Используется в Израиле. Год начинается в сентябре-октябре.
Часто указываются только три последние цифры.""",
        "examples": """• 5700 ≈ 1940 г.
• 5708 ≈ 1948 г. (создание Израиля)
• 5760 ≈ 2000 г.
• 5780 ≈ 2020 г.
• 5784 ≈ 2024 г.
• Дата "784" = 5784 = 2024 г.""",
        "offset": 3760,
        "symbols": [
            [("א", "1"), ("ב", "2"), ("ג", "3"), ("ד", "4"), ("ה", "5")],
            [("ו", "6"), ("ז", "7"), ("ח", "8"), ("ט", "9"), ("י", "10")],
            [("כ", "20"), ("ל", "30"), ("מ", "40"), ("נ", "50"), ("ס", "60")],
            [("ע", "70"), ("פ", "80"), ("צ", "90")],
            [("ק", "100"), ("ר", "200"), ("ש", "300"), ("ת", "400")],
            [("תק", "500"), ("תר", "600"), ("תש", "700"), ("תת", "800")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=israel.php&lang=ru"
    },
    
    # ===== АЗИЯ =====
    {
        "name": "Тайский (буддийский)",
        "flag": "🇹🇭",
        "info": """<b>Буддийский календарь (Buddhist Era, B.E.)</b>

Формула: <b>Буддийский год - 543 = год н.э.</b>

Используется в Таиланде с 1913 года.
На монетах дата тайскими цифрами.
2567 B.E. = 2024 г.н.э.""",
        "examples": """• 2500 B.E. ≈ 1957 г.
• 2510 B.E. ≈ 1967 г.
• 2540 B.E. ≈ 1997 г.
• 2560 B.E. ≈ 2017 г.
• 2567 B.E. ≈ 2024 г.
• "๕๐" = 50 → 2550 B.E.""",
        "offset": 543,
        "symbols": [
            [("๐", "0"), ("๑", "1"), ("๒", "2"), ("๓", "3"), ("๔", "4")],
            [("๕", "5"), ("๖", "6"), ("๗", "7"), ("๘", "8"), ("๙", "9")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=thailand.php&lang=ru"
    },
    
    {
        "name": "Бангладеш (бенгальский)",
        "flag": "🇧🇩",
        "info": """<b>Бенгальский календарь (Bangla San)</b>

Формула: <b>Бенгальский год + 593 = год н.э.</b>

Используется в Бангладеш и Западной Бенгалии (Индия).
Новый год — 14-15 апреля.""",
        "examples": """• 1380 B.S. ≈ 1973 г.
• 1400 B.S. ≈ 1993 г.
• 1410 B.S. ≈ 2003 г.
• 1430 B.S. ≈ 2023 г.""",
        "offset": -593,
        "formula": "year + 593",
        "symbols": [
            [("০", "0"), ("১", "1"), ("২", "2"), ("৩", "3"), ("৪", "4")],
            [("৫", "5"), ("৬", "6"), ("৭", "7"), ("৮", "8"), ("৯", "9")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=bangladesh.php&lang=ru"
    },
    
    {
        "name": "Индийский (сака)",
        "flag": "🇮🇳",
        "info": """<b>Календарь Сака (Saka Era)</b>

Формула: <b>Год Сака + 78 = год н.э.</b>

Национальный календарь Индии с 1957 года.
1946 год Сака = 2024 год н.э.""",
        "examples": """• 1870 г.Сака ≈ 1948 г.
• 1900 г.Сака ≈ 1978 г.
• 1925 г.Сака ≈ 2003 г.
• 1946 г.Сака ≈ 2024 г.""",
        "offset": -78,
        "formula": "year + 78",
        "symbols": [
            [("०", "0"), ("१", "1"), ("२", "2"), ("३", "3"), ("४", "4")],
            [("५", "5"), ("६", "6"), ("७", "7"), ("८", "8"), ("९", "9")],
        ],
    },
    
    {
        "name": "Непальский (бикрам самбат)",
        "flag": "🇳🇵",
        "info": """<b>Непальский календарь (Bikram Sambat, B.S.)</b>

Формула: <b>B.S. - 57 ≈ год н.э.</b>

Официальный календарь Непала.
Новый год — 13-14 апреля.""",
        "examples": """• 2000 B.S. ≈ 1943 г.
• 2040 B.S. ≈ 1983 г.
• 2060 B.S. ≈ 2003 г.
• 2080 B.S. ≈ 2023 г.""",
        "offset": 57,
        "symbols": [
            [("०", "0"), ("१", "1"), ("२", "2"), ("३", "3"), ("४", "4")],
            [("५", "5"), ("६", "6"), ("७", "7"), ("८", "8"), ("९", "9")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=nepal.php&lang=ru"
    },
    
    {
        "name": "Камбоджийский (кхмерский)",
        "flag": "🇰🇭",
        "info": """<b>Кхмерский календарь</b>

В Камбодже используется буддийское летоисчисление (Buddhist Era),
аналогичное тайскому.

Формула: <b>Буддийский год - 543 = год н.э.</b>

Также используется кхмерская разновидность цифр.
Цифры похожи на тайские, но имеют отличия в начертании.""",
        "examples": """• 2500 B.E. ≈ 1957 г.
• 2510 B.E. ≈ 1967 г.
• 2540 B.E. ≈ 1997 г.
• 2560 B.E. ≈ 2017 г.""",
        "offset": 543,
        "symbols": [
            [("០", "0"), ("១", "1"), ("២", "2"), ("៣", "3"), ("៤", "4")],
            [("៥", "5"), ("៦", "6"), ("៧", "7"), ("៨", "8"), ("៩", "9")],
        ],
    },
    
    {
        "name": "Китайский (циклический)",
        "flag": "🇨🇳",
        "info": """<b>Китайский циклический календарь</b>

Дата на монетах Китая указывается по годам правления императора.

<b>Династия Цин (1644–1912):</b>
• Гуансюй (光緒): 1875–1908
• Сюаньтун (宣統): 1908–1912

После 1912 года используется григорианский календарь.
Для точного перевода рекомендуется онлайн-конвертер.""",
        "examples": """• Гуансюй 1 = 1875 г.
• Гуансюй 30 = 1904 г.
• Гуансюй 34 = 1908 г.
• Сюаньтун 3 = 1911 г.""",
        "symbols": [
            [("零", "0"), ("一", "1"), ("二", "2"), ("三", "3"), ("四", "4")],
            [("五", "5"), ("六", "6"), ("七", "7"), ("八", "8"), ("九", "9")],
            [("十", "10"), ("百", "100"), ("千", "1000"), ("萬", "10000")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=china.php&lang=ru"
    },
    
    {
        "name": "Японский (по эрам)",
        "flag": "🇯🇵",
        "info": """<b>Система эр (нэнго)</b>

<b>Эры:</b>
• Рэйва (令和): с 2019 — Рэйва 1 = 2019
• Хэйсэй (平成): 1989-2019
• Сёва (昭和): 1926-1989
• Тайсё (大正): 1912-1926
• Мэйдзи (明治): 1868-1912""",
        "examples": """• Мэйдзи 30 = 1897 г.
• Сёва 40 = 1965 г.
• Сёва 64 = 1989 г.
• Хэйсэй 1 = 1989 г.
• Рэйва 1 = 2019 г.
• Рэйва 6 = 2024 г.""",
        "symbols": [
            [("一", "1"), ("二", "2"), ("三", "3"), ("四", "4"), ("五", "5")],
            [("六", "6"), ("七", "7"), ("八", "8"), ("九", "9"), ("十", "10")],
        ],
        "online_url": "https://creounity.com/apps/time_machine/?go=japan.php&lang=ru"
    },
    
    {
        "name": "Северокорейский (чучхе)",
        "flag": "🇰🇵",
        "info": """<b>Календарь Чучхе (Juche Era)</b>

Формула: <b>Год Чучхе + 1911 = год н.э.</b>

Отсчет от рождения Ким Ир Сена (1912 г.).
Используется с 1997 года.""",
        "examples": """• Чучхе 1 = 1912 г.
• Чучхе 50 = 1961 г.
• Чучхе 80 = 1991 г.
• Чучхе 100 = 2011 г.
• Чучхе 113 = 2024 г.""",
        "offset": -1911,
        "formula": "year + 1911",
        "symbols": [],
    },
    
    # ===== АФРИКА =====
    {
        "name": "Эфиопский",
        "flag": "🇪🇹",
        "info": """<b>Эфиопский календарь (Ethiopian Calendar)</b>

Формула: <b>Эфиопский год + 8 ≈ год н.э.</b>

Отстает от григорианского на 7-8 лет.
13 месяцев в году. Новый год — 11 сентября.""",
        "examples": """• 1890 г.э.к. ≈ 1898 г.
• 1920 г.э.к. ≈ 1928 г.
• 1960 г.э.к. ≈ 1968 г.
• 2000 г.э.к. ≈ 2008 г.
• 2010 г.э.к. ≈ 2018 г.""",
        "offset": -8,
        "formula": "year + 8",
        "symbols": [],
    },
    
    # ===== ЕВРОПА =====
    {
        "name": "Кириллистический (старый стиль)",
        "flag": "🇷🇺",
        "info": """<b>Юлианский календарь / Кириллическая запись</b>

Использовался в России до 1918 года. На монетах Российской Империи
дата часто записывалась буквами кириллицы (церковнославянские цифры).

<b>Разница с григорианским:</b>
• XVIII в.: +11 дней
• XIX в.: +12 дней
• XX в. (до 1918): +13 дней""",
        "examples": """• АΨПА = 1701 г.
• АΨПЕ = 1705 г.
• АΨЧI = 1790 г.
• Примечание: Ψ (пси) = 700""",
        "symbols": [
            [("А=1", "1"), ("В=2", "2"), ("Г=3", "3"), ("Д=4", "4"), ("Е=5", "5")],
            [("Ѕ=6", "6"), ("З=7", "7"), ("И=8", "8"), ("Ѳ=9", "9"), ("I=10", "10")],
            [("К=20", "20"), ("Л=30", "30"), ("М=40", "40"), ("Н=50", "50"), ("Ѯ=60", "60")],
            [("О=70", "70"), ("П=80", "80"), ("Ч=90", "90")],
            [("Р=100", "100"), ("С=200", "200"), ("Т=300", "300"), ("У=400", "400"), ("Ф=500", "500")],
            [("Х=600", "600"), ("Ѱ=700", "700"), ("Ѡ=800", "800"), ("Ц=900", "900")],
        ],
    },
    
    # ===== ЕВРОПА =====
    {
        "name": "Римский",
        "flag": "🏛️",
        "info": """<b>Римские цифры</b>

Часто встречаются на монетах европейских стран для обозначения
года выпуска (до XVIII века).

<b>Основные символы:</b>
• I = 1, V = 5, X = 10, L = 50
• C = 100, D = 500, M = 1000

Правила чтения:
• Если меньшая цифра стоит перед большей — вычитается
• Если меньшая после большей — складывается""",
        "examples": """• MDCXCII = 1692 г.
• MDCCXLVIII = 1748 г.
• MDCCCXII = 1812 г.
• MCMXVII = 1917 г.
• MMXXIV = 2024 г.""",
        "symbols": [
            [("I=1", "1"), ("V=5", "5"), ("X=10", "10"), ("L=50", "50")],
            [("C=100", "100"), ("D=500", "500"), ("M=1000", "1000")],
        ],
    },
    
    # ===== УНИВЕРСАЛЬНЫЕ =====
    {
        "name": "Григорианский (европейский)",
        "flag": "🇪🇺",
        "info": """<b>Григорианский календарь</b>

Стандартный календарь, используемый в большинстве стран мира.
Введен в 1582 году папой Григорием XIII.

Не требует конвертации. На монетах дата указывается арабскими цифрами.
Иногда год указывается не полностью (например, "89" вместо "1989").

Для дат с сокращенным годом:
• если число < 50 — вероятно, 20XX год
• если 50-99 — вероятно, 19XX год""",
        "examples": """• 1780 = 1780 г.
• 1825 = 1825 г.
• 1900 = 1900 г.
• 1961 = 1961 г.
• 2000 = 2000 г.
• 2024 = 2024 г.
• "46" = 1946 г.
• "08" = 2008 г.""",
        "formula": "year",
        "symbols": [
            [("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")],
            [("5", "5"), ("6", "6"), ("7", "7"), ("8", "8"), ("9", "9")],
        ],
    },
]


# Функция для создания вкладки из main_window.py
def get_date_converter_tab(db_manager, parent=None):
    return DateConverterTab(db_manager, parent)