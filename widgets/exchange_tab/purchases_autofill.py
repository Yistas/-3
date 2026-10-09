# -*- coding: utf-8 -*-

"""
Автозаполнение закупок из UCOIN
"""

import re
import csv
import time
import shutil
from pathlib import Path
from math import gcd
from fractions import Fraction
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QMessageBox, QApplication, QListWidget, 
    QGroupBox, QFormLayout, QLineEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer, QUrl
from datetime import datetime
from database.models import Purchase, ImportCountry
from utils.paths import paths


class PurchasesAutofillMixin:
    """Примесь с методами автозаполнения из UCOIN"""
    
    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С ДРОБЯМИ И ЧИСЛАМИ ==========
    
    def _fraction_to_decimal(self, text):
        """Преобразует дробь вида '1/2', '3/4' в десятичное число"""
        if not text:
            return None
        
        text = str(text).strip()
        
        # Проверяем формат "число/число"
        match = re.match(r'^(\d+)/(\d+)$', text)
        if match:
            numerator = float(match.group(1))
            denominator = float(match.group(2))
            if denominator != 0:
                return numerator / denominator
        
        # Проверяем формат "число число/число" (например "1 1/2")
        match = re.match(r'^(\d+)\s+(\d+)/(\d+)$', text)
        if match:
            whole = float(match.group(1))
            numerator = float(match.group(2))
            denominator = float(match.group(3))
            if denominator != 0:
                return whole + (numerator / denominator)
        
        return None
    
    def _decimal_to_fraction(self, decimal_value):
        """Преобразует десятичную дробь в обычную (например 0.5 -> '1/2')"""
        if decimal_value is None:
            return None
        
        # Словарь соответствий десятичных дробей и обычных
        fraction_map = {
            0.5: "1/2",
            0.25: "1/4",
            0.75: "3/4",
            0.333333333333: "1/3",
            0.666666666667: "2/3",
            0.2: "1/5",
            0.4: "2/5",
            0.6: "3/5",
            0.8: "4/5",
            0.166666666667: "1/6",
            0.833333333333: "5/6",
            0.125: "1/8",
            0.375: "3/8",
            0.625: "5/8",
            0.875: "7/8",
        }
        
        # Проверяем точное совпадение
        for dec, frac in fraction_map.items():
            if abs(decimal_value - dec) < 0.001:
                return frac
        
        # Пробуем найти простую дробь
        frac = Fraction(decimal_value).limit_denominator(10)
        if frac.numerator != 0 and frac.denominator != 1:
            g = gcd(frac.numerator, frac.denominator)
            if g > 1:
                return f"{frac.numerator // g}/{frac.denominator // g}"
            return f"{frac.numerator}/{frac.denominator}"
        
        return str(decimal_value)
    
    def _parse_fraction_symbol(self, text):
        """Парсит символы дробей вида ½, ¼, ⅛ и т.д. в десятичное число"""
        fractions = {
            '½': 0.5,
            '¼': 0.25,
            '¾': 0.75,
            '⅓': 0.333333333333,
            '⅔': 0.666666666667,
            '⅕': 0.2,
            '⅖': 0.4,
            '⅗': 0.6,
            '⅘': 0.8,
            '⅙': 0.166666666667,
            '⅚': 0.833333333333,
            '⅛': 0.125,
            '⅜': 0.375,
            '⅝': 0.625,
            '⅞': 0.875,
            '¹⁄₂': 0.5,
            '¹⁄₄': 0.25,
            '³⁄₄': 0.75,
            '¹⁄₃': 0.333333333333,
            '²⁄₃': 0.666666666667,
        }
        
        for frac, value in fractions.items():
            if frac in text:
                return value
        
        return None
    
    def _parse_number_with_thousands_separator(self, text):
        """Парсит число с точкой как разделителем тысяч (например 50.000 -> 50000)"""
        if not text:
            return None
        
        text = str(text).strip()
        
        # Если есть точка и после неё ровно 3 цифры - это разделитель тысяч
        match = re.search(r'^(\d+)\.(\d{3})$', text)
        if match:
            whole = match.group(1)
            thousand = match.group(2)
            return float(f"{whole}{thousand}")
        
        # Если есть точка и после неё НЕ 3 цифры - возможно десятичный разделитель
        match = re.search(r'^(\d+)\.(\d+)$', text)
        if match:
            return float(text.replace('.', ','))
        
        # Обычное число
        try:
            cleaned = text.replace(' ', '').replace(',', '.')
            return float(cleaned)
        except:
            return None
    
    def _normalize_denomination_for_compare(self, text):
        """Нормализует номинал для сравнения"""
        if not text:
            return None
        
        text = str(text).strip()
        
        # Проверяем символы дробей
        fraction_symbol_value = self._parse_fraction_symbol(text)
        if fraction_symbol_value is not None:
            fraction = self._decimal_to_fraction(fraction_symbol_value)
            if fraction and '/' in fraction:
                return fraction
        
        # Если это десятичное число
        try:
            num = float(text)
            if num == int(num):
                return str(int(num))
            fraction = self._decimal_to_fraction(num)
            if fraction and '/' in fraction:
                return fraction
            return str(num)
        except:
            pass
        
        # Если это уже дробь
        if '/' in text:
            parts = text.split('/')
            if len(parts) == 2:
                try:
                    num = int(parts[0])
                    den = int(parts[1])
                    if den != 0:
                        g = gcd(num, den)
                        if g > 1:
                            return f"{num // g}/{den // g}"
                    return text
                except:
                    pass
            return text
        
        # Целое число
        try:
            num = int(text)
            return str(num)
        except:
            pass
        
        return text

    def _normalize_year(self, year_str):
        """Извлекает только 4 цифры года из строки ("2016 ★S" -> "2016")"""
        if not year_str:
            return None
        year_str = str(year_str).strip()
        match = re.search(r'(\d{4})', year_str)
        if match:
            return match.group(1)
        return year_str

    # ========== МЕТОДЫ ДЛЯ НЕЧЕТКОГО ПОИСКА ==========
    
    def _normalize_string(self, text):
        """Нормализует строку"""
        if not text:
            return ""
        
        text = str(text).lower().strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\-]', '', text)
        text = text.strip()
        
        return text
    
    def _get_word_root(self, word):
        """Извлекает корень слова"""
        if not word or len(word) < 2:
            return word
        
        russian_endings = [
            'ая', 'яя', 'ое', 'ее', 'ые', 'ие',
            'ой', 'ей', 'ый', 'ий', 'а', 'я', 'у', 'ю', 'о', 'е', 'ы', 'и',
            'ам', 'ям', 'ами', 'ями', 'ах', 'ях',
            'ов', 'ев', 'ёв', 'ин', 'ын', 'нин',
            'ок', 'ек', 'ик', 'чик', 'щик',
            'тель', 'арь', 'ар', 'ир', 'лог', 'граф',
            'ский', 'цкий', 'овой', 'евой',
            'ее', 'ие', 'ые', 'ое', 'ими', 'ыми', 'ему', 'ому',
            'ть', 'ти', 'чь', 'ся', 'сь',
            'л', 'ла', 'ло', 'ли',
            'н', 'на', 'но', 'ны',
            'в', 'ва', 'во', 'вы',
        ]
        
        root = word
        for ending in russian_endings:
            if root.endswith(ending) and len(root) > len(ending) + 1:
                root = root[:-len(ending)]
                break
        
        if len(root) < 2:
            return word
        
        return root
    
    def _levenshtein(self, s1, s2):
        """Расстояние Левенштейна"""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _fuzzy_match(self, text1, text2):
        """Нечеткое сравнение строк"""
        if not text1 or not text2:
            return False
        
        t1 = self._normalize_string(str(text1))
        t2 = self._normalize_string(str(text2))
        
        if not t1 or not t2:
            return False
        
        if t1 == t2:
            return True
        
        if t1 in t2 or t2 in t1:
            return True
        
        root1 = self._get_word_root(t1)
        root2 = self._get_word_root(t2)
        
        if root1 and root2:
            if root1 == root2:
                return True
            if len(root1) >= 3 and len(root2) >= 3:
                if root1 in root2 or root2 in root1:
                    return True
        
        min_len = min(len(t1), len(t2))
        compare_len = min(min_len, 5)
        
        if compare_len >= 3:
            if t1[:compare_len] == t2[:compare_len]:
                return True
        
        distance = self._levenshtein(t1[:8], t2[:8])
        max_len = max(len(t1[:8]), len(t2[:8]))
        similarity = 1 - (distance / max_len) if max_len > 0 else 0
        
        return similarity >= 0.7
    
    def _compare_currencies(self, currency1, currency2):
        """Сравнение валют"""
        if not currency1 or not currency2:
            return False
        
        c1 = self._normalize_string(str(currency1))
        c2 = self._normalize_string(str(currency2))
        
        if not c1 or not c2:
            return False
        
        if c1 == c2:
            return True
        
        if c1 in c2 or c2 in c1:
            return True
        
        min_len = min(len(c1), len(c2))
        compare_len = min(min_len, 4)
        
        if compare_len >= 3:
            if c1[:compare_len] == c2[:compare_len]:
                if c1[:2] == c2[:2]:
                    return True
        
        root1 = self._get_word_root(c1)
        root2 = self._get_word_root(c2)
        
        if root1 and root2:
            if root1 == root2:
                return True
            if len(root1) >= 3 and len(root2) >= 3:
                if root1 in root2 or root2 in root1:
                    return True
        
        currency_synonyms = {
            'рубль': ['руб', 'рублей', 'рубля', 'р', 'rur', 'rub'],
            'копейка': ['коп', 'копейки', 'копеек', 'к'],
            'доллар': ['долл', 'доллара', 'долларов', '$', 'usd'],
            'цент': ['цента', 'центов', 'c', 'cent'],
            'евро': ['евро', 'euro', '€', 'eur'],
            'фунт': ['фунта', 'фунтов', 'стерлингов', '£', 'gbp'],
            'марка': ['марки', 'марок', 'pfennig', 'пфенниг'],
            'крона': ['кроны', 'крон', 'krona', 'koruna'],
            'злотый': ['злотого', 'злотых', 'zloty', 'pln'],
            'гривна': ['гривны', 'гривен', 'hryvnia', 'uah'],
            'тенге': ['тенге', 'tenge', 'kzt'],
            'сум': ['сума', 'сумов', 'som', 'uzs'],
            'манат': ['маната', 'манатов', 'manat', 'azn', 'tmt'],
            'лей': ['лея', 'леев', 'leu', 'mdl', 'ron'],
            'лев': ['лева', 'левов', 'lev', 'bgn'],
            'динар': ['динара', 'динаров', 'dinar', 'rsd', 'kwd', 'bhd'],
            'реал': ['реала', 'реалов', 'real', 'brl'],
            'песо': ['песо', 'peso', 'mxn', 'php', 'ars', 'cop'],
            'рупия': ['рупии', 'рупий', 'rupee', 'inr', 'idr', 'pkr'],
            'ринггит': ['ринггита', 'ринггитов', 'ringgit', 'myr'],
            'бат': ['бата', 'батов', 'baht', 'thb'],
            'вона': ['воны', 'вон', 'won', 'kpw', 'krw'],
            'иена': ['иены', 'иен', 'yen', 'jpy'],
            'юань': ['юаня', 'юаней', 'yuan', 'cny', 'renminbi'],
            'донг': ['донга', 'донгов', 'dong', 'vnd'],
            'тугрик': ['тугрика', 'тугриков', 'tugrik', 'mnt'],
            'франк': ['франка', 'франков', 'franc', 'chf', 'bif', 'rwf'],
            'шиллинг': ['шиллинга', 'шиллингов', 'shilling', 'kes', 'tzs', 'ugs'],
            'седи': ['седи', 'cedi', 'ghs'],
            'наира': ['найры', 'найр', 'naira', 'ngn'],
            'ранд': ['ранда', 'рандов', 'rand', 'zar'],
        }
        
        c1_lower = c1.lower()
        c2_lower = c2.lower()
        
        for main_name, synonyms in currency_synonyms.items():
            if c1_lower == main_name or c1_lower in synonyms:
                if c2_lower == main_name or c2_lower in synonyms:
                    return True
            if c2_lower == main_name or c2_lower in synonyms:
                if c1_lower == main_name or c1_lower in synonyms:
                    return True
        
        if len(c1) <= 10 and len(c2) <= 10:
            distance = self._levenshtein(c1, c2)
            max_len = max(len(c1), len(c2))
            similarity = 1 - (distance / max_len) if max_len > 0 else 0
            if similarity >= 0.7:
                return True
        
        return False
    
    def _load_nicknames_from_deals(self):
        """Загружает ники ТОЛЬКО из НЕЗАКРЫТЫХ сделок"""
        try:
            from database.models import Deal
            
            # Только незакрытые сделки (без галочки ДОСТ)
            deals = self.db_manager.session.query(Deal).filter(
                Deal.buyer.isnot(None),
                Deal.buyer != "",
                Deal.number.isnot(None),
                Deal.number != "",
                (Deal.delivery.is_(None) | (Deal.delivery != '✅'))
            ).order_by(Deal.number.desc()).all()
            
            nick_list = []
            seen_nicks = set()
            
            for deal in deals:
                if deal.buyer and deal.buyer not in seen_nicks:
                    seen_nicks.add(deal.buyer)
                    try:
                        num_value = int(deal.number) if deal.number else 0
                    except (ValueError, TypeError):
                        num_value = 0
                    
                    nick_list.append({
                        'name': deal.buyer,
                        'number': deal.number,
                        'number_value': num_value,
                        'deal_id': deal.id
                    })
            
            nick_list.sort(key=lambda x: x['number_value'], reverse=True)
            self.logger.info(f"📋 Загружено {len(nick_list)} ников из незакрытых сделок")
            return nick_list
        except Exception as e:
            self.logger.error(f"Ошибка загрузки ников из сделок: {e}")
            return []
    
    def _get_current_browser_url(self):
        """Получает текущий URL из браузера вкладки закупок"""
        try:
            main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
            
            if not main_window or not hasattr(main_window, 'exchange_tab'):
                return None
            
            exchange_tab = main_window.exchange_tab
            if not hasattr(exchange_tab, 'embedded_browser') or not exchange_tab.embedded_browser:
                return None
            
            browser = exchange_tab.embedded_browser
            web_view = browser.get_current_web_view()
            
            if web_view:
                url = web_view.url().toString()
                if url and url != "about:blank":
                    return url
            return None
        except Exception as e:
            self.logger.error(f"Ошибка получения URL из браузера: {e}")
            return None
    
    def _show_autofill_dialog(self):
        """Диалог автозаполнения из UCOIN"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🔄 Автозаполнение из UCOIN")
        dialog.setMinimumWidth(500)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title = QLabel("📥 Заполнение поля «Продано» из обмена на UCOIN")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #4a6fa5;")
        title.setWordWrap(True)
        layout.addWidget(title)
        
        info = QLabel(
            "1. Выберите покупателя из списка (ники из сделок)\n"
            "2. URL автоматически подставится из открытой вкладки браузера\n"
            "3. Нажмите ОК, файл будет скачан и обработан\n"
            "4. Монеты будут найдены по стране, году, номиналу\n"
            "5. В поле «Продано» будет записан НИК покупателя\n"
            "6. № из сделки будет записан в колонку №Пок закупки"
        )
        info.setStyleSheet("color: #666; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Никнейм
        layout.addWidget(QLabel("Покупатель (НИК):"))
        
        nick_layout = QHBoxLayout()
        self.autofill_nickname = QComboBox()
        self.autofill_nickname.setEditable(True)
        self.autofill_nickname.setMinimumHeight(30)
        self.autofill_nickname.setMinimumWidth(200)
        
        # Загружаем ники из сделок
        nick_list = self._load_nicknames_from_deals()
        self._nick_data = {}
        added_nicks = set()
        
        for item in nick_list:
            if item['name'] not in added_nicks:
                display_text = f"{item['name']} (№{item['number']})"
                self.autofill_nickname.addItem(display_text, item['name'])
                self._nick_data[item['name']] = {
                    'number': item['number'],
                    'deal_id': item['deal_id']
                }
                added_nicks.add(item['name'])
        
        # Загружаем сохранённые ники
        saved_nicks = self.settings.value('autofill_nicknames', [])
        if isinstance(saved_nicks, str):
            saved_nicks = [saved_nicks]
        if not isinstance(saved_nicks, list):
            saved_nicks = []
        
        for nick in saved_nicks:
            if nick and nick not in added_nicks:
                deal_number = None
                for item in nick_list:
                    if item['name'] == nick:
                        deal_number = item['number']
                        break
                
                display_text = f"{nick} (№{deal_number})" if deal_number else nick
                self.autofill_nickname.addItem(display_text, nick)
                self._nick_data[nick] = {
                    'number': deal_number,
                    'deal_id': None
                }
                added_nicks.add(nick)
                self.logger.info(f"📋 Добавлен сохранённый ник: {nick}")
        
        if self.autofill_nickname.count() > 0:
            self.autofill_nickname.setCurrentIndex(0)
        self.autofill_nickname.setPlaceholderText("выберите покупателя")
        
        nick_layout.addWidget(self.autofill_nickname, 1)
        
        clear_history_btn = QPushButton("🗑️")
        clear_history_btn.setFixedSize(30, 30)
        clear_history_btn.setToolTip("Очистить историю ников")
        clear_history_btn.clicked.connect(self._clear_nick_history)
        nick_layout.addWidget(clear_history_btn)
        
        layout.addLayout(nick_layout)
        
        # Ссылка на обмен
        layout.addWidget(QLabel("Ссылка на обмен UCOIN (авто из браузера):"))
        
        url_layout = QHBoxLayout()
        self.autofill_url = QLineEdit()
        self.autofill_url.setMinimumHeight(30)
        self.autofill_url.setMinimumWidth(200)
        self.autofill_url.setReadOnly(True)
        
        current_url = self._get_current_browser_url()
        if current_url:
            self.autofill_url.setText(current_url)
            self.autofill_url.setStyleSheet("background-color: #e8f0fe; color: #4a6fa5;")
        else:
            self.autofill_url.setPlaceholderText("❌ Не удалось получить URL из браузера. Откройте страницу обмена.")
            self.autofill_url.setStyleSheet("background-color: #ffe0e0; color: #dc3545;")
        
        url_layout.addWidget(self.autofill_url, 1)
        
        refresh_url_btn = QPushButton("🔄")
        refresh_url_btn.setFixedSize(30, 30)
        refresh_url_btn.setToolTip("Обновить URL из браузера")
        refresh_url_btn.clicked.connect(self._refresh_url_from_browser)
        url_layout.addWidget(refresh_url_btn)
        
        layout.addLayout(url_layout)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("✅ ОК")
        ok_btn.setMinimumHeight(32)
        ok_btn.setMinimumWidth(100)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 3px;")
        
        if not current_url:
            ok_btn.setEnabled(False)
            ok_btn.setToolTip("Сначала откройте страницу обмена в браузере")
        
        ok_btn.clicked.connect(lambda checked, dlg=dialog: self._start_autofill(dlg))
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _refresh_url_from_browser(self):
        """Обновляет URL из браузера"""
        current_url = self._get_current_browser_url()
        if current_url:
            self.autofill_url.setText(current_url)
            self.autofill_url.setStyleSheet("background-color: #e8f0fe; color: #4a6fa5;")
            if hasattr(self, 'save_status_label'):
                self.save_status_label.setText(f"✅ URL обновлён: {current_url[:60]}...")
        else:
            QMessageBox.warning(self, "Предупреждение", 
                "Не удалось получить URL из браузера.\n"
                "Убедитесь, что в браузере открыта страница UCOIN.")
            self.autofill_url.setPlaceholderText("❌ Не удалось получить URL")
            self.autofill_url.setStyleSheet("background-color: #ffe0e0; color: #dc3545;")
    
    def _start_autofill(self, dialog):
        """Запускает автозаполнение"""
        # Получаем ник из комбобокса
        selected_nick = self.autofill_nickname.currentData()
        if not selected_nick:
            selected_nick = self.autofill_nickname.currentText().strip()
        
        # Получаем URL из QLineEdit
        url = self.autofill_url.text().strip()
        
        deal_number = None
        if selected_nick in self._nick_data:
            deal_number = self._nick_data[selected_nick]['number']
        
        if not selected_nick:
            QMessageBox.warning(self, "Предупреждение", "Выберите покупателя")
            return
        
        if not url:
            QMessageBox.warning(self, "Предупреждение", "Введите ссылку на обмен")
            return
        
        # Закрываем диалог
        dialog.accept()
        
        # Сохраняем ник в историю
        self._save_nick_to_history(selected_nick)
        
        self._autofill_nickname = selected_nick
        self._autofill_deal_number = deal_number
        
        self.logger.info(f"🔄 Автозаполнение для {selected_nick} (№{deal_number or 'новая сделка'})")
        
        # Формируем URL для скачивания CSV
        if '?' in url:
            download_url = url + '&export=csv'
        else:
            download_url = url + '?export=csv'
        
        if hasattr(self, 'embedded_browser') and self.embedded_browser:
            web_view = self.embedded_browser.get_current_web_view()
            if web_view:
                web_view.setUrl(QUrl(download_url))
                self.logger.info("📑 URL загружен в браузере")
                
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.setText("⏳ Скачивание...")
                    self.save_status_label.setStyleSheet("color: #ffc107; font-size: 11px;")
                
                # Запускаем watcher
                self._start_file_watcher(selected_nick, deal_number)
                
                QMessageBox.information(
                    self,
                    "Скачивание файла",
                    f"Файл обмена скачивается автоматически.\n"
                    f"👤 {selected_nick}\n"
                    f"📦 № сделки: {deal_number or 'будет создана'}\n\n"
                    f"Если скачивание не началось, проверьте:\n"
                    f"• Открыта ли страница обмена UCOIN\n"
                    f"• Есть ли доступ к сети"
                )
            else:
                QMessageBox.warning(self, "Ошибка", "Нет активной вкладки браузера")
        else:
            QMessageBox.warning(self, "Ошибка", "Браузер не доступен")
    
    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С WATCHER ==========

    def _start_file_watcher(self, nick, deal_number):
        """Запускает watcher для отслеживания скачанного файла"""
        # Проверяем, не запущен ли уже watcher
        if hasattr(self, '_watcher_running') and self._watcher_running:
            self.logger.warning("⚠️ Watcher уже запущен")
            return
        
        # Проверяем, не обработан ли уже файл для этой сделки
        watcher_key = f"{nick}_{deal_number}"
        if hasattr(self, '_processed_watcher_keys') and watcher_key in self._processed_watcher_keys:
            self.logger.info(f"⏭️ Сделка {watcher_key} уже обработана, пропускаем")
            return
        
        self.logger.info(f"📂 Запуск watcher (сделка №{deal_number})")
        self._watcher_running = True
        self._watcher_nick = nick
        self._watcher_deal_number = deal_number
        self._watcher_processed = False
        self._watcher_key = watcher_key
        
        if not hasattr(self, '_processed_watcher_keys'):
            self._processed_watcher_keys = set()
        
        if hasattr(self, 'save_status_label'):
            self.save_status_label.setText("⏳ Ожидание файла...")
            self.save_status_label.setStyleSheet("color: #ffc107; font-size: 11px;")
        
        # Используем таймер для проверки папки
        self._watcher_timer = QTimer()
        self._watcher_timer.setSingleShot(False)
        self._watcher_timer.timeout.connect(self._check_obmen_folder)
        self._watcher_timer.start(1000)
        self._watcher_start_time = datetime.now()
    
    def _stop_watcher(self):
        """Останавливает watcher и отмечает сделку как обработанную"""
        if hasattr(self, '_watcher_timer') and self._watcher_timer is not None:
            self._watcher_timer.stop()
            self._watcher_timer = None
        
        if hasattr(self, '_watcher_key') and self._watcher_key:
            if not hasattr(self, '_processed_watcher_keys'):
                self._processed_watcher_keys = set()
            self._processed_watcher_keys.add(self._watcher_key)
            self.logger.info(f"✅ Watcher остановлен для {self._watcher_key}")
        
        self._watcher_running = False
        self._watcher_processed = True
    
    def _check_obmen_folder(self):
        """Проверяет папку obmen на наличие новых файлов"""
        try:
            if self._watcher_processed:
                self._stop_watcher()
                return
            
            nick = getattr(self, '_watcher_nick', None)
            deal_number = getattr(self, '_watcher_deal_number', None)
            
            obmen_dir = paths.get_obmen_dir()
            if not obmen_dir.exists():
                return
            
            current_time = datetime.now().timestamp()
            csv_files = list(obmen_dir.glob("*.csv"))
            csv_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            for file_path in csv_files:
                try:
                    if current_time - file_path.stat().st_mtime < 10:
                        self.logger.info(f"✅ Файл найден: {file_path.name}")
                        
                        # Останавливаем watcher
                        self._stop_watcher()
                        
                        # Обрабатываем файл
                        self._process_downloaded_file(str(file_path), nick, deal_number)
                        return
                except:
                    pass
            
            # Таймаут
            if hasattr(self, '_watcher_start_time'):
                elapsed = (datetime.now() - self._watcher_start_time).total_seconds()
                if elapsed > 60:
                    self._stop_watcher()
                    self.logger.warning("⏱️ Таймаут watcher'а")
                    if hasattr(self, 'save_status_label'):
                        self.save_status_label.setText("⚠️ Файл не найден")
                        self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
                    
        except Exception as e:
            self.logger.error(f"Ошибка в _check_obmen_folder: {e}")
            self._stop_watcher()
    
    def _process_downloaded_file(self, file_path, nick, deal_number):
        """Обрабатывает скачанный CSV файл"""
        try:
            self.logger.info(f"📂 Обработка файла: {Path(file_path).name}")
            
            # Проверяем, не обработан ли уже этот файл
            if hasattr(self, '_processed_files') and file_path in self._processed_files:
                self.logger.info(f"⏭️ Файл уже обработан: {Path(file_path).name}")
                return
            
            if not hasattr(self, '_processed_files'):
                self._processed_files = set()
            self._processed_files.add(file_path)
            
            # Пробуем разные кодировки (строго, без errors='ignore',
            # чтобы cp1251 не читался как битый utf-8)
            encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'latin-1']
            content = None
            used_encoding = None
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    self.logger.info(f"Файл прочитан с кодировкой {encoding}")
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception:
                    continue
            # Если строго не открылось — читаем с игнорированием ошибок
            if content is None:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    used_encoding = 'utf-8 (ignore)'
                    self.logger.info("Файл прочитан с кодировкой utf-8 (errors=ignore)")
                except Exception as e:
                    self.logger.error(f"❌ Не удалось прочитать файл: {e}")
            
            if content is None:
                self.logger.error("❌ Не удалось прочитать файл")
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.setText("❌ Не удалось прочитать файл")
                return
            
            lines = content.split('\n')
            if not lines:
                self.logger.error("❌ Файл пуст")
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.setText("❌ Файл пуст")
                return
            
            # Определяем разделитель
            delimiter = '\t' if '\t' in lines[0] else ','
            
            from io import StringIO
            reader = csv.DictReader(StringIO(content), delimiter=delimiter)
            
            fieldnames = reader.fieldnames if reader.fieldnames else []
            self.logger.info(f"Заголовки CSV: {fieldnames}")
            
            # Маппинг заголовков
            header_map = {}
            for header in fieldnames:
                header_lower = header.lower().strip()
                if header_lower in ['страна', 'country', 'страна-эмитент']:
                    header_map['country'] = header
                elif header_lower in ['год', 'year', 'год чекана', 'годы']:
                    header_map['year'] = header
                elif header_lower in ['номинал', 'denomination', 'достоинство']:
                    header_map['denomination'] = header
                elif header_lower in ['валюта', 'currency']:
                    header_map['currency'] = header
                elif header_lower in ['цена, rub', 'цена', 'price', 'стоимость']:
                    header_map['price'] = header
            
            if 'country' not in header_map:
                self.logger.error("❌ Не найден заголовок 'Страна'")
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.setText("❌ Не найден заголовок 'Страна'")
                return
            
            # Парсим данные
            coins_data = []
            for row in reader:
                country = row.get(header_map.get('country', ''), '').strip()
                if not country or country in ['nan', 'None', '']:
                    continue
                
                country = country.strip('"\'')
                
                year_str = row.get(header_map.get('year', ''), '').strip()
                year = None
                if year_str:
                    match = re.search(r'(\d{4})', str(year_str))
                    if match:
                        year = int(match.group(1))
                
                # Парсим номинал и валюту
                denomination_raw = row.get(header_map.get('denomination', ''), '').strip()
                denomination_raw = denomination_raw.strip('"\'')
                
                denomination = None
                currency = None
                
                # Пытаемся разделить номинал и валюту
                if denomination_raw:
                    # Паттерн: число + валюта (например "1 рубль", "2 евро", "10 копеек")
                    match = re.match(r'^([\d\s\/½¼¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]+)\s*(.+)$', denomination_raw)
                    if match:
                        denomination = match.group(1).strip()
                        currency = match.group(2).strip()
                    else:
                        # Если не разделилось, пробуем найти валюту в конце
                        currency_match = re.search(r'\s+([а-яА-Яa-zA-Z]+)$', denomination_raw)
                        if currency_match:
                            currency = currency_match.group(1)
                            denomination = denomination_raw[:currency_match.start()].strip()
                        else:
                            denomination = denomination_raw
                
                # Если валюта не найдена, пробуем взять из отдельного поля
                if not currency:
                    currency_raw = row.get(header_map.get('currency', ''), '').strip()
                    currency = currency_raw.strip('"\'') if currency_raw else None
                
                price_str = row.get(header_map.get('price', ''), '').strip()
                price = None
                if price_str:
                    try:
                        price_clean = re.sub(r'[^\d.,-]', '', str(price_str))
                        price_clean = price_clean.replace(',', '.')
                        price = float(price_clean)
                    except (ValueError, TypeError):
                        pass
                
                if price is None:
                    continue
                
                coins_data.append({
                    'country': country,
                    'year': year,
                    'denomination': denomination,
                    'currency': currency,
                    'price': price,
                })
            
            self.logger.info(f"📊 Распарсено монет: {len(coins_data)}")
            
            if not coins_data:
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.setText("❌ Не удалось распарсить данные")
                return
            
            # Обрабатываем данные
            self._process_parsed_data(coins_data, nick, deal_number)
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки файла: {e}")
            import traceback
            traceback.print_exc()
            if hasattr(self, 'save_status_label'):
                self.save_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
    
    def _process_parsed_data(self, coins_data, nickname, deal_number):
        """Обрабатывает распарсенные данные и обновляет закупки.

        В продаже может быть НЕСКОЛЬКО ОДИНАКОВЫХ монет — каждая строка CSV
        сопоставляется СВОЕЙ закупке (без повторного использования),
        совпадения выбираются по возрастанию №Зак (id).
        """
        if not coins_data:
            if hasattr(self, 'save_status_label'):
                self.save_status_label.setText("❌ Монеты не найдены")
            return

        self.logger.info(f"🔍 Поиск монет. CSV: {len(coins_data)}, в таблице: {len(self._all_purchases)}")

        # === ЗАЩИТА от ObjectDeletedError: перезагружаем список закупок из БД ===
        try:
            from database.models import Purchase
            self._all_purchases = self.db_manager.session.query(Purchase).all()
        except Exception as e:
            self.logger.error(f"Ошибка обновления списка закупок: {e}")

        filled = 0
        not_found = 0
        not_found_list = []
        total_sum = 0.0
        new_remainders = []

        # === Индекс закупок: (страна, год, номинал) -> список по возрастанию №Зак ===
        purchase_index = {}
        for purchase in self._all_purchases:
            try:
                batch = purchase.purchase_batch
                if batch and str(batch).strip() and str(batch).strip() != "0" and batch != "Т":
                    continue
                if not purchase.import_country:
                    continue
                country_name = purchase.import_country.name if purchase.import_country else ""
                year = str(purchase.year) if purchase.year else ""
                denom_normalized = self._normalize_denomination_for_compare(purchase.denomination_value) if purchase.denomination_value else None
                key = (country_name, year, denom_normalized)
                purchase_index.setdefault(key, []).append(purchase)
            except Exception:
                # Объект удалён из БД или откреплён от сессии — пропускаем
                continue

        # Сортировка каждой группы по возрастанию №Зак (id)
        for key in purchase_index:
            purchase_index[key].sort(key=lambda p: (p.id is None, p.id if p.id is not None else 0))

        used_set = set()  # id() уже использованных закупок (защита от дублей)

        # === Обработка каждой монеты из CSV ===
        for coin_info in coins_data:
            country_csv = (coin_info.get('country') or '').strip()
            year = self._normalize_year(coin_info.get('year'))
            denomination_csv = (coin_info.get('denomination') or '').strip()
            currency_csv = (coin_info.get('currency') or '').strip()
            price = coin_info.get('price')
            if price:
                total_sum += price

            if not country_csv:
                not_found += 1
                not_found_list.append(f"Пропущена (нет страны): {coin_info}")
                continue

            # Поиск ключа с fallback-вариантами
            denom_normalized = self._normalize_denomination_for_compare(denomination_csv) if denomination_csv else None
            base_key = (country_csv, year, denom_normalized)
            base_list = purchase_index.get(base_key)
            if base_list is None and denomination_csv:
                base_key = (country_csv, year, denomination_csv)
                base_list = purchase_index.get(base_key)
            if base_list is None:
                base_key = (country_csv, year, None)
                base_list = purchase_index.get(base_key)
            if base_list is None:
                base_list = []

            # Фильтр по валюте (если указан)
            candidates = base_list
            if currency_csv and currency_csv != '—' and base_list:
                filtered = [p for p in base_list if self._compare_currencies(currency_csv, p.currency)]
                if filtered:
                    candidates = filtered

            # Первая НЕиспользованная закупка по возрастанию №Зак
            selected = None
            for p in candidates:
                if id(p) in used_set:
                    continue
                selected = p
                break

            if selected:
                used_set.add(id(selected))
                remainder = self._fill_purchase(selected, nickname, deal_number, price)
                # Копия-остаток доступна для следующих одинаковых монет
                if remainder is not None:
                    base_list.append(remainder)
                    new_remainders.append(remainder)
                filled += 1
                self.logger.info(f"  ✅ Найдена монета: {country_csv} {denomination_csv} {year} -> №Зак={selected.id}")
            else:
                not_found += 1
                error_msg = f"{country_csv}| {denomination_csv}| {currency_csv}| {year}"
                not_found_list.append(error_msg)
                self.logger.debug(f"  ❌ Не найдена: {error_msg}")

        # === Сохраняем созданные копии-остатки ===
        try:
            self.db_manager.session.commit()
            self._all_purchases.extend(new_remainders)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения копий: {e}")

        self.logger.info(f"ИТОГО: заполнено={filled}, не найдено={not_found}, сумма={total_sum:.2f}")

        # === Результат ===
        if not_found_list:
            error_text = "\n".join(not_found_list[:50])
            if len(not_found_list) > 50:
                error_text += f"\n... и ещё {len(not_found_list) - 50} монет"
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("⚠️ Монеты не найдены")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(f"Не найдено монет: {not_found}\nОбщая сумма по CSV: {total_sum:.2f} ₽\n\nСкопируйте список для поиска:")
            msg_box.setDetailedText(error_text)
            msg_box.exec()

        if hasattr(self, 'save_status_label'):
            if not_found == 0:
                self.save_status_label.setText(f"✅ Все монеты найдены ({filled})")
                self.save_status_label.setStyleSheet("color: #28a745;")
            else:
                self.save_status_label.setText(f"⚠️ Найдено {filled}, не найдено {not_found}")
                self.save_status_label.setStyleSheet("color: #ffc107;")

        # Обновляем таблицу закупок
        try:
            if hasattr(self, '_apply_filters'):
                self._apply_filters()
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы: {e}")

    def _fill_purchase(self, purchase, nickname, deal_number, price):
        """Заполняет закупку данными продажи БЕЗ СУММЫ
        (сумма проставляется при закрытии сделки).

        Если КОЛ/Обмен > 1 — создаёт копию строки с уменьшением "Обмен" и "КОЛ"
        на 1 (остаток), а исходная строка становится проданной (КОЛ=1).
        Возвращает созданную копию-остаток или None.
        """
        from datetime import datetime as _dt
        remainder = None
        qty = purchase.quantity or 1
        exch = purchase.ucoin_exchange_count or 0
        if not exch:
            exch = 1 if purchase.ucoin_exchange else 0

        # === КОЛ/Обмен != 1: разделяем строку ===
        if qty > 1 or exch > 1:
            try:
                from database.models import Purchase
                from sqlalchemy import inspect as sa_inspect
                remainder = Purchase()
                mapper = sa_inspect(Purchase)
                for col in mapper.columns:
                    if col.name == 'id':
                        continue
                    try:
                        setattr(remainder, col.name, getattr(purchase, col.name))
                    except Exception:
                        pass
                # Копия-остаток: КОЛ и Обмен уменьшены на 1
                remainder.quantity = (qty - 1) if qty > 1 else qty
                new_exch = (exch - 1) if exch > 1 else exch
                remainder.ucoin_exchange_count = new_exch
                remainder.ucoin_exchange = bool(new_exch > 0)
                # Остаток НЕ продан
                remainder.sold_count = None
                remainder.sold_sum = None
                remainder.total = None
                remainder.purchase_batch = (purchase.purchase_batch or "0")
                remainder.updated_at = _dt.now()
                self.db_manager.session.add(remainder)
                # Исходная строка — проданная монета (1 шт)
                purchase.quantity = 1
                purchase.ucoin_exchange = False
                purchase.ucoin_exchange_count = 0
                self.logger.info(
                    f"  📑 Копия строки №Зак={purchase.id}: "
                    f"КОЛ/Обмен остатка = {remainder.quantity}/{new_exch}"
                )
            except Exception as e:
                self.logger.error(f"Ошибка создания копии строки: {e}")
                remainder = None

        # === Заполняем проданную строку (СУММУ НЕ ЗАПОЛНЯЕМ) ===
        purchase.sold_count = nickname          # колонка "Продано"
        purchase.purchase_batch = str(deal_number)  # колонка "№Пок"
        # sold_sum и total НЕ трогаем — их заполнит закрытие сделки
        purchase.updated_at = _dt.now()
        self._dirty_ids.add(purchase.id)
        return remainder

    def _create_duplicate_purchase(self, original, nickname, deal_number):
        """Создаёт копию закупки"""
        new_purchase = Purchase()
        for col in ['in_collection', 'collection_price', 'purchase_number',
                   'import_country_id', 'continent', 'denomination_value',
                   'currency', 'year', 'location_found', 'comments',
                   'ucoin_exchange', 'ucoin_exchange_count']:
            setattr(new_purchase, col, getattr(original, col, None))
        
        new_purchase.quantity = 1
        new_purchase.purchase_batch = str(deal_number) if deal_number else "0"
        new_purchase.sold_count = nickname
        new_purchase.sold_sum = original.sold_sum or 0
        new_purchase.total = original.total or 0
        return new_purchase
    
    def _apply_filter_by_nickname(self, nickname):
        """Применяет фильтр по колонке ПРОДАНО"""
        if not nickname:
            return
        
        col_index = 13  # Колонка "Продано"
        self._column_filters[col_index] = {nickname}
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
        
        if hasattr(self, 'save_status_label'):
            if not_found == 0:
                self.save_status_label.setText(f"✅ Все монеты найдены ({filled})")
                self.save_status_label.setStyleSheet("color: #28a745;")
            else:
                self.save_status_label.setText(f"⚠️ Найдено {filled}, не найдено {not_found}")
                self.save_status_label.setStyleSheet("color: #ffc107;")

        # Обновляем таблицу закупок
        try:
            if hasattr(self, '_apply_filters'):
                self._apply_filters()
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы: {e}")
    
    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С ИСТОРИЕЙ НИКОВ ==========

    def _save_nick_to_history(self, nick):
        """Сохраняет ник в историю (до 50 последних)"""
        if not nick:
            return
        
        saved_nicks = self.settings.value('autofill_nicknames', [])
        if isinstance(saved_nicks, str):
            saved_nicks = [saved_nicks]
        if not isinstance(saved_nicks, list):
            saved_nicks = []
        
        # Удаляем ник из списка, если он уже есть (чтобы обновить позицию)
        if nick in saved_nicks:
            saved_nicks.remove(nick)
        
        # Добавляем в начало
        saved_nicks.insert(0, nick)
        
        # Оставляем только последние 50
        if len(saved_nicks) > 50:
            saved_nicks = saved_nicks[:50]
        
        self.settings.setValue('autofill_nicknames', saved_nicks)
        self.logger.info(f"💾 Ник сохранён в историю: {nick}")
    
    def _clear_nick_history(self):
        """Очищает историю сохранённых ников"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Очистить историю сохранённых ников?\n\n"
            "Это удалит все ники, которые были добавлены вручную.\n"
            "Ники из активных сделок останутся в списке.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings.remove('autofill_nicknames')
            
            # Обновляем комбобокс
            if hasattr(self, 'autofill_nickname'):
                self.autofill_nickname.clear()
                
                # Перезагружаем ники из сделок
                nick_list = self._load_nicknames_from_deals()
                self._nick_data = {}
                added_nicks = set()
                
                for item in nick_list:
                    if item['name'] not in added_nicks:
                        display_text = f"{item['name']} (№{item['number']})"
                        self.autofill_nickname.addItem(display_text, item['name'])
                        self._nick_data[item['name']] = {
                            'number': item['number'],
                            'deal_id': item['deal_id']
                        }
                        added_nicks.add(item['name'])
                
                if self.autofill_nickname.count() > 0:
                    self.autofill_nickname.setCurrentIndex(0)
                
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.setText("🧹 История ников очищена")
                    self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                    QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
            
            QMessageBox.information(self, "Очищено", "История никнеймов очищена")