# -*- coding: utf-8 -*-
"""
Встроенный браузер
Левая кнопка - открывает ссылки в текущей вкладке
Поддержка контекстного меню с пунктом "Добавить в Коллекцию"
"""
import os
import sys
import logging
import webbrowser
import re
import json
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QTabWidget, QToolBar, QMessageBox,
                               QLabel, QProgressBar, QApplication, QDialog,
                               QTableWidget, QTableWidgetItem, QAbstractItemView,
                               QMenu, QStyle, QFrame)
from PySide6.QtCore import Qt, QUrl, QSettings, QTimer, QEvent, QSize, QEventLoop, Signal
from PySide6.QtGui import QAction, QMouseEvent, QContextMenuEvent, QFont, QIcon, QPixmap
from utils.paths import paths

# Импорт WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import (QWebEngineProfile, QWebEnginePage,
                                         QWebEngineSettings, QWebEngineScript)
    WEBENGINE_AVAILABLE = True
except ImportError as e:
    WEBENGINE_AVAILABLE = False
    print(f"⚠️ WebEngine не загружен: {e}")

# Старая видеокарта (GF210 и т.п.): полноэкранный CSS-фильтр тёмной темы сайтов
# отключён по умолчанию — программная растеризация не тянет его без рывков.
# Флаг выставляется в main.py после определения видеокарты.
# ВАЖНО: строка стоит ПОСЛЕ блока try/except, на нулевом отступе!
LEGACY_GPU = os.environ.get('COIN_COLLECTOR_LEGACY_GPU', '0') == '1'

# === ПРИНУДИТЕЛЬНЫЙ РУССКИЙ ЯЗЫК ДЛЯ MESHOK / UCOIN ===
if WEBENGINE_AVAILABLE:
    try:
        from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

        class RussianLanguageInterceptor(QWebEngineUrlRequestInterceptor):
            """Добавляет заголовок Accept-Language: ru-RU ко всем запросам
            к meshok.net и ucoin.net.
            ВАЖНО: редирект на ru.ucoin.net выполняется ТОЛЬКО для главных
            документов с хостов ucoin.net / www.ucoin.net / en.ucoin.net.
            Поддомены (static., coin., img. и т.п.) НЕ трогаем — иначе
            ломаются картинки и статика (static.ru.ucoin.net не существует)."""

            # Хосты, с которых разрешён редирект на ru.ucoin.net
            _UCOIN_MAIN_HOSTS = ('ucoin.net', 'www.ucoin.net', 'en.ucoin.net')

            def __init__(self, parent=None):
                super().__init__(parent)
                self.logger = logging.getLogger('CoinCollector.RussianInterceptor')

            def interceptRequest(self, info):
                try:
                    qurl = info.requestUrl()
                    host = qurl.host()
                    url = qurl.toString()

                    # 1) Заголовок Accept-Language — для всех запросов meshok/ucoin
                    if 'meshok.net' in host or 'ucoin.net' in host:
                        info.setHttpHeader(b'Accept-Language',
                                           b'ru-RU,ru;q=0.9,en;q=0.5')

                    # 2) Редирект на ru.ucoin.net — ТОЛЬКО главный документ
                    #    и ТОЛЬКО с точных хостов из белого списка
                    if host in self._UCOIN_MAIN_HOSTS:
                        main_frame = True
                        try:
                            rt = info.resourceType()
                            RT = QWebEngineUrlRequestInterceptor.ResourceType
                            main_frame = (rt == RT.ResourceTypeMainFrame)
                        except Exception:
                            main_frame = True
                        if main_frame:
                            new_url = url
                            for bad in ('//ucoin.net', '//www.ucoin.net',
                                        '//en.ucoin.net'):
                                new_url = new_url.replace(bad, '//ru.ucoin.net', 1)
                            if new_url != url:
                                info.redirect(QUrl(new_url))
                except Exception as e:
                    self.logger.debug(f"interceptRequest: {e}")
    except ImportError:
        QWebEngineUrlRequestInterceptor = None
else:
    QWebEngineUrlRequestInterceptor = None

# === JS ПОДСВЕТКИ ТЕКСТА НА СТРАНИЦЕ ===
# ccHighlight(term) — оборачивает все вхождения термина в жёлтые метки;
# ccClearHighlight() — снимает метки, восстанавливая исходные текстовые узлы.
# Метки учитывают CSS-инверсию тёмной темы (класс cc-inv компенсирует фильтр).
HIGHLIGHT_JS = """
window.ccClearHighlight = function() {
    var marks = document.querySelectorAll('span.cc-highlight');
    for (var i = 0; i < marks.length; i++) {
        var m = marks[i];
        var parent = m.parentNode;
        if (!parent) continue;
        parent.replaceChild(document.createTextNode(m.textContent), m);
        parent.normalize();
    }
    return marks.length;
};
window.ccHighlight = function(term) {
    window.ccClearHighlight();
    if (!term) return 0;
    if (!document.body) return 0;
    if (!document.getElementById('cc-highlight-style')) {
        var st = document.createElement('style');
        st.id = 'cc-highlight-style';
        st.textContent =
            '.cc-highlight { background: #ffeb3b; color: #000; ' +
            'border-radius: 2px; padding: 0 1px; font-weight: bold; } ' +
            '.cc-highlight.cc-inv { filter: invert(1) hue-rotate(180deg); }';
        (document.head || document.documentElement).appendChild(st);
    }
    var inverted = false;
    try {
        inverted = getComputedStyle(document.body).filter.indexOf('invert') !== -1;
    } catch (e) {}
    var lower = term.toLowerCase();
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    var count = 0;
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var text = node.nodeValue || '';
        var low = text.toLowerCase();
        var idx = low.indexOf(lower);
        if (idx === -1) continue;
        var parent = node.parentNode;
        if (!parent) continue;
        if (parent.nodeName === 'SCRIPT' || parent.nodeName === 'STYLE') continue;
        var frag = document.createDocumentFragment();
        var last = 0;
        while (idx !== -1) {
            if (idx > last) {
                frag.appendChild(document.createTextNode(text.slice(last, idx)));
            }
            var mark = document.createElement('span');
            mark.className = 'cc-highlight' + (inverted ? ' cc-inv' : '');
            mark.textContent = text.substr(idx, term.length);
            frag.appendChild(mark);
            count++;
            last = idx + term.length;
            idx = low.indexOf(lower, last);
        }
        if (last < text.length) {
            frag.appendChild(document.createTextNode(text.slice(last)));
        }
        parent.replaceChild(frag, node);
    }
    console.log('CC-HL: подсвечено вхождений: ' + count + ' («' + term + '»)');
    return count;
};
"""

class CustomWebEnginePage(QWebEnginePage):
    """Кастомная страница для перехвата навигации (ЛКМ) + тёмный фон без вспышки"""

    # Тёмный (светлее прежнего) фон применяется ДО отрисовки сайта
    DARK_BG_JS = """
(function() {
    function applyDark() {
        if (document.documentElement) {
            document.documentElement.style.setProperty('background-color', '#262640', 'important');
        }
        if (document.body) {
            document.body.style.setProperty('background-color', '#262640', 'important');
        }
    }
    applyDark();
    if (document.addEventListener) {
        document.addEventListener('DOMContentLoaded', applyDark);
        window.addEventListener('load', applyDark);
    }
})();
"""

    def __init__(self, profile, browser, parent=None):
        super().__init__(profile, parent)
        self.browser = browser
        # === НЕТ «БЕЛОЙ ВСПЫШКИ»: фон страницы тёмный с самого начала ===
        try:
            from PySide6.QtGui import QColor
            if self._is_dark_theme():
                self.setBackgroundColor(QColor('#262640'))
                self._install_dark_background_script()
            else:
                self.setBackgroundColor(QColor('#ffffff'))
        except Exception:
            pass

    # Уровни JS-консоли Chromium → уровни logging
    _JS_LEVEL_MAP = {0: logging.DEBUG, 1: logging.WARNING, 2: logging.ERROR}
    # Безобидный спам сайтов/Chromium — пишем только в DEBUG, не засоряя лог
    _JS_NOISE = ('webgl', 'blocklisted', 'woff', 'contenttype', 'preload',
                 'z-index for modal', 'deprecation', 'autocomplete')

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Перехватывает console.log/warn/error со ВСЕХ страниц и пишет в лог
        приложения (Uncaught TypeError, ошибки сайтов, маркеры CC-RU и т.д.)."""
        try:
            lvl = self._JS_LEVEL_MAP.get(int(level), logging.INFO)
            low = (message or '').lower()
            if any(k in low for k in self._JS_NOISE):
                lvl = logging.DEBUG          # WebGL/WOFF/preload — не спамим
            if (message or '').startswith(('CC-', '✅', '⚠️', '❌', '🚀', '️')):
                lvl = logging.INFO           # маркеры наших скриптов — всегда видно
            self.browser.logger.log(
                lvl, f"js[{int(level)}] {sourceID or ''}:{lineNumber} {message}")
        except Exception:
            pass

class CustomWebView(QWebEngineView):
    """Кастомный WebView для перехвата ПКМ через сигналы"""
    
    # Сигнал, который отправляет найденную ссылку
    link_found = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = parent
        self._context_pos = None
        self._global_pos = None
        self._pending_menu = None
        self._context_url = None
        self._is_waiting = False
        self._timeout_timer = None
        
        # Подключаем сигнал к обработчику
        self.link_found.connect(self._on_link_found)

    def contextMenuEvent(self, event):
        """Перехват контекстного меню: ПКМ на ссылке монеты — ищет ссылку через JS.
        На ЛЮБОЙ странице ucoin.net — СРАЗУ добавляет "🚀 Массовое добавление"
        (независимо от того, попал ли ПКМ на ссылку)."""
        if not hasattr(self, 'browser') or not self.browser:
            super().contextMenuEvent(event)
            return
        
        self._is_waiting = True
        self._context_pos = event.pos()
        self._global_pos = event.globalPos()
        self._pending_menu = QMenu(self)
        
        # === СОХРАНЯЕМ URL ТЕКУЩЕЙ СТРАНИЦЫ ===
        try:
            self._current_page_url = self.url().toString()
        except Exception:
            self._current_page_url = ""
        
        # === МАССОВОЕ ДОБАВЛЕНИЕ: добавляем СРАЗУ на ЛЮБОЙ странице ucoin.net ===
        # Делается ДО поиска ссылки — появляется даже если ПКМ на пустом месте
        try:
            page_url = self._current_page_url or ""
            # Максимально гибкая проверка — любое упоминание ucoin.net
            is_ucoin = 'ucoin.net' in page_url
            if is_ucoin:
                mass_action = QAction("🚀 Массовое добавление в коллекцию (до 24 монет)", self)
                mass_action.triggered.connect(
                    lambda checked, u=page_url: self.browser._mass_add_to_collection(u)
                )
                font = mass_action.font()
                font.setBold(True)
                mass_action.setFont(font)
                self._pending_menu.addAction(mass_action)
                self._pending_menu.addSeparator()
                self.browser.logger.info(f"🚀 Массовое добавление доступно на: {page_url[:80]}")
        except Exception as e:
            self.browser.logger.error(f"Ошибка создания пункта массового добавления: {e}")
        
        # === Стандартный поиск ссылки под курсором через JS ===
        js_get_link = """
        (function() {
            function isInputElement(el) {
                if (!el) return false;
                var tag = el.tagName ? el.tagName.toLowerCase() : '';
                return tag === 'input' || tag === 'textarea' || tag === 'select';
            }
            function isEditableElement(el) {
                if (!el) return false;
                if (el.getAttribute && (el.getAttribute('contenteditable') === 'true' ||
                    el.getAttribute('contenteditable') === '')) return true;
                return false;
            }
            function isFormElement(el) {
                if (!el) return false;
                var parent = el;
                for (var i = 0; i < 10 && parent; i++) {
                    if (parent.tagName && parent.tagName.toLowerCase() === 'form') return true;
                    parent = parent.parentElement;
                }
                return false;
            }
            function isButtonElement(el) {
                if (!el) return false;
                if (el.tagName && el.tagName.toLowerCase() === 'button') return true;
                return false;
            }
            
            var el = document.elementFromPoint(%d, %d);
            if (!el) return null;
            
            if (isInputElement(el) || isEditableElement(el) || 
                isFormElement(el) || isButtonElement(el)) {
                return null;
            }
            
            function findLink(element) {
                var parent = element;
                for (var i = 0; i < 5 && parent; i++) {
                    if (parent.href) return parent;
                    if (parent.tagName === 'A' && parent.getAttribute('href')) return parent;
                    parent = parent.parentElement;
                }
                return null;
            }
            
            var link = findLink(el);
            if (link && link.href) {
                try {
                    return new URL(link.href, window.location.href).toString();
                } catch (e) {
                    return link.href;
                }
            }
            return null;
        })();
        """ % (event.pos().x(), event.pos().y())
        
        def js_callback(result):
            url = None
            if result and isinstance(result, str) and result.strip():
                url = result.strip()
                self.browser.logger.info(f"✅ URL из JS: {url}")
            else:
                self.browser.logger.info("⏭️ Ссылка на монету не найдена под курсором")
            self.link_found.emit(url or "")
        
        self.page().runJavaScript(js_get_link, 0, js_callback)
        
        # Таймаут на случай, если JS не вернёт результат
        self._timeout_timer = QTimer()
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._timeout_timer.start(1500)

    def _get_link_url_async(self):
        """Асинхронно получает URL ссылки под курсором (с учётом масштаба)"""
        if not self._context_pos:
            self.link_found.emit("")
            return
        
        # Получаем позицию в пикселях viewport
        pos = self._context_pos
        viewport_x = float(pos.x())
        viewport_y = float(pos.y())
        
        self.browser.logger.info(f"  Асинхронный поиск ссылки: viewport_x={viewport_x}, viewport_y={viewport_y}")
        
        # JavaScript с коррекцией координат
        js_get_link = f"""
        (function() {{
            var viewportX = {viewport_x};
            var viewportY = {viewport_y};
            
            // === КОРРЕКЦИЯ КООРДИНАТ ===
            // Получаем масштаб страницы
            var scaleX = window.innerWidth / document.documentElement.clientWidth;
            var scaleY = window.innerHeight / document.documentElement.clientHeight;
            
            // Корректируем координаты с учётом масштаба
            var x = viewportX * scaleX;
            var y = viewportY * scaleY;
            
            console.log('CoinCollector: viewport=(' + viewportX + ',' + viewportY + 
                       '), scale=(' + scaleX + ',' + scaleY + 
                       '), corrected=(' + x.toFixed(1) + ',' + y.toFixed(1) + ')');
            
            function isCoinLink(url) {{
                if (!url) return false;
                return url.indexOf('/coin/') !== -1 && url.indexOf('ucid=') !== -1;
            }}
            
            // === ПОЛУЧАЕМ ТЕКСТ ПОД КУРСОРОМ ===
            var cursorElement = document.elementFromPoint(x, y);
            var cursorText = '';
            
            if (cursorElement) {{
                cursorText = cursorElement.textContent.trim();
                console.log('CoinCollector: Под курсором: "' + cursorText + '" (' + cursorElement.tagName + ')');
            }}
            
            // === СОБИРАЕМ ВСЕ ССЫЛКИ НА МОНЕТЫ ===
            var allLinks = document.querySelectorAll('a[href]');
            var candidates = [];
            
            for (var i = 0; i < allLinks.length; i++) {{
                var link = allLinks[i];
                var href = link.href;
                if (!href || !isCoinLink(href)) continue;
                
                var rect = link.getBoundingClientRect();
                
                // Проверяем, видима ли ссылка
                var style = window.getComputedStyle(link);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                if (rect.width === 0 || rect.height === 0) continue;
                
                // Вычисляем расстояние до ссылки (с учётом масштаба)
                var closestX = Math.max(rect.left, Math.min(x, rect.right));
                var closestY = Math.max(rect.top, Math.min(y, rect.bottom));
                var distance = Math.sqrt(Math.pow(x - closestX, 2) + Math.pow(y - closestY, 2));
                
                // Получаем текст ссылки
                var linkText = link.textContent.trim();
                
                // Вычисляем совпадение текста
                var textScore = 0;
                if (cursorText && linkText) {{
                    if (linkText === cursorText) {{
                        textScore = 100;
                    }} else if (cursorText.indexOf(linkText) !== -1) {{
                        textScore = 70;
                    }} else if (linkText.indexOf(cursorText) !== -1) {{
                        textScore = 50;
                    }} else {{
                        var cursorWords = cursorText.split(/\\s+/);
                        var linkWords = linkText.split(/\\s+/);
                        var matchCount = 0;
                        for (var j = 0; j < cursorWords.length; j++) {{
                            if (cursorWords[j].length < 2) continue;
                            for (var k = 0; k < linkWords.length; k++) {{
                                if (linkWords[k].length < 2) continue;
                                if (cursorWords[j] === linkWords[k] || 
                                    cursorWords[j].indexOf(linkWords[k]) !== -1 ||
                                    linkWords[k].indexOf(cursorWords[j]) !== -1) {{
                                    matchCount++;
                                    break;
                                }}
                            }}
                        }}
                        if (matchCount > 0) {{
                            textScore = 20 + matchCount * 10;
                        }}
                    }}
                }}
                
                candidates.push({{
                    href: href,
                    distance: distance,
                    textScore: textScore,
                    linkText: linkText.substring(0, 50),
                    rect: rect
                }});
            }}
            
            if (candidates.length === 0) {{
                console.log('CoinCollector: ❌ Ссылки на монеты не найдены');
                return '';
            }}
            
            // === СОРТИРОВКА ===
            candidates.sort(function(a, b) {{
                // Сначала по расстоянию (чем меньше, тем лучше)
                if (a.distance < 10 && b.distance >= 10) return -1;
                if (b.distance < 10 && a.distance >= 10) return 1;
                
                // Потом по тексту
                if (Math.abs(a.textScore - b.textScore) > 20) {{
                    return b.textScore - a.textScore;
                }}
                // Потом по расстоянию
                return a.distance - b.distance;
            }});
            
            // Выводим топ-3 кандидатов
            var top = candidates.slice(0, 3);
            for (var i = 0; i < top.length; i++) {{
                var c = top[i];
                console.log('CoinCollector: Кандидат ' + (i+1) + ': dist=' + c.distance.toFixed(1) + 
                           ', score=' + c.textScore + 
                           ', text="' + c.linkText + '"');
            }}
            
            var best = candidates[0];
            console.log('CoinCollector: ✅ Выбран: dist=' + best.distance.toFixed(1) + 
                       ', score=' + best.textScore);
            return best.href;
            
        }})();
        """
        
        def js_callback(result):
            url = None
            if result and isinstance(result, str) and result.strip():
                url = result.strip()
                self.browser.logger.info(f"  ✅ URL из JS: {url}")
            else:
                self.browser.logger.info("  ❌ Ссылка на монету с ucid не найдена")
            
            # Отправляем сигнал с результатом
            self.link_found.emit(url or "")
        
        # Запускаем JavaScript
        self.page().runJavaScript(js_get_link, 0, js_callback)


    def _on_link_found(self, url):
        """Обработчик найденной ссылки.
        Массовое добавление уже добавлено в contextMenuEvent — здесь только одиночное."""
        if not self._is_waiting:
            return
        self._is_waiting = False
        self._context_url = url if url else None
        
        # Останавливаем таймер
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer = None
        
        # === ОДИНОЧНОЕ ДОБАВЛЕНИЕ (только для ссылок на монеты с ucid) ===
        if url and self._pending_menu:
            if '/coin/' in url and 'ucid=' in url:
                self.browser.logger.info(f"✅ Добавляем одиночный пункт для: {url}")
                add_action = QAction("➕ Добавить в Коллекцию", self)
                add_action.triggered.connect(
                    lambda checked, u=url: self.browser._add_to_collection(u)
                )
                font = add_action.font()
                font.setBold(True)
                add_action.setFont(font)
                # Вставляем ПОСЛЕ разделителя массового добавления (если он есть)
                actions = self._pending_menu.actions()
                if actions:
                    # Находим первый separator и вставляем после него
                    sep_idx = None
                    for i, act in enumerate(actions):
                        if act.isSeparator():
                            sep_idx = i
                            break
                    if sep_idx is not None:
                        # Вставляем после разделителя
                        if sep_idx + 1 < len(actions):
                            self._pending_menu.insertAction(actions[sep_idx + 1], add_action)
                        else:
                            self._pending_menu.addAction(add_action)
                    else:
                        # Разделителя нет (не каталог) — вставляем первым
                        self._pending_menu.insertAction(actions[0], add_action)
                else:
                    self._pending_menu.addAction(add_action)
            else:
                self.browser.logger.info(f"⏭️ Пропускаем (не ссылка на монету с ucid): {url}")
        
        # Показываем меню
        if self._pending_menu and self._global_pos:
            self._pending_menu.exec(self._global_pos)
            self._pending_menu = None
         
    def _on_timeout(self):
        """Обработчик таймаута"""
        if not self._is_waiting:
            return
        
        self._is_waiting = False
        self.browser.logger.warning("  ⏱️ Таймаут поиска ссылки, показываем меню без неё")
        
        # Показываем меню без пункта "Добавить в коллекцию"
        if self._pending_menu and self._global_pos:
            self._pending_menu.exec(self._global_pos)
            self._pending_menu = None
        
        self._timeout_timer = None
    
    def _on_copy_link(self):
        """Обработчик копирования ссылки"""
        url = self._context_url
        if url:
            self.browser.logger.info(f"  Копирование ссылки: {url}")
            self.browser._copy_url(url)
        else:
            self.browser.logger.warning("  ❌ Нет ссылки для копирования")
    
    def _on_open_in_new_tab(self):
        """Обработчик открытия в новой вкладке"""
        url = self._context_url
        if url:
            self.browser.logger.info(f"  Открытие в новой вкладке: {url}")
            self.browser.add_new_tab(url)
        else:
            self.browser.logger.warning("  ❌ Нет ссылки для открытия")
    
    def _on_open_in_system(self):
        """Обработчик открытия в системном браузере"""
        url = self._context_url
        if url:
            self.browser.logger.info(f"  Открытие в системном браузере: {url}")
            self.browser._open_in_system_browser(url)
        else:
            self.browser.logger.warning("  ❌ Нет ссылки для открытия")


class SimplePasswordManager:
    """Упрощенный менеджер паролей для браузера"""
    
    def __init__(self, storage_path):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.passwords_file = self.storage_path / "passwords.json"
        self.logger = logging.getLogger('CoinCollector.PasswordManager')
        self.load_passwords()
    
    def load_passwords(self):
        if self.passwords_file.exists():
            try:
                with open(self.passwords_file, 'r', encoding='utf-8') as f:
                    self.passwords = json.load(f)
                    return self.passwords
            except Exception as e:
                self.logger.error(f"Ошибка загрузки паролей: {e}")
        self.passwords = {}
        return self.passwords
    
    def save_passwords(self):
        try:
            with open(self.passwords_file, 'w', encoding='utf-8') as f:
                json.dump(self.passwords, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения паролей: {e}")
            return False
    
    def save_password(self, url, username, password):
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain not in self.passwords:
                self.passwords[domain] = []
            for i, entry in enumerate(self.passwords[domain]):
                if entry.get('username') == username:
                    self.passwords[domain][i] = {
                        'username': username,
                        'password': password,
                        'url': url,
                        'updated_at': datetime.now().isoformat()
                    }
                    break
            else:
                self.passwords[domain].append({
                    'username': username,
                    'password': password,
                    'url': url,
                    'created_at': datetime.now().isoformat()
                })
            self.save_passwords()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения пароля: {e}")
            return False
    
    def get_password(self, url):
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain in self.passwords:
                return self.passwords[domain]
        except Exception as e:
            self.logger.error(f"Ошибка получения пароля: {e}")
        return []
    
    def delete_password(self, domain, username):
        try:
            if domain in self.passwords:
                self.passwords[domain] = [e for e in self.passwords[domain] if e.get('username') != username]
                if not self.passwords[domain]:
                    del self.passwords[domain]
                self.save_passwords()
                return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления пароля: {e}")
            return False


class EmbeddedBrowser(QWidget):
    """Встроенный браузер"""
    
    def __init__(self, parent=None, profile_name="coin_collector"):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.Browser')
        self.profile_name = profile_name
        self.settings = QSettings('CoinCollector', 'Browser')
        
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent.parent.parent
        
        self.storage_path = paths.get_data_dir() / "browser_data" / profile_name
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        if not os.access(self.storage_path, os.W_OK):
            self.storage_path = Path.home() / ".coin_collector" / "browser_data" / profile_name
            self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"📁 Папка профиля браузера: {self.storage_path}")
        
        self.password_manager = SimplePasswordManager(self.storage_path)
        self.profile = None
        self.tab_widget = None
        self.url_bar = None
        self.progress_bar = None
        self.web_views = []
        self._initialized = False
        self._current_web_view = None
        
        self.init_ui()
        
        if WEBENGINE_AVAILABLE:
            QTimer.singleShot(500, self._delayed_init)
        
        from PySide6.QtCore import Signal
        self.download_finished = Signal(str)

    # CSS-инверсия: фильтр на BODY — покрывает всю высоту страницы при прокрутке
    DARK_WEB_JS = """
(function() {
    if (document.getElementById('cc-dark-theme')) { return; }
    var style = document.createElement('style');
    style.id = 'cc-dark-theme';
    style.textContent =
        'html { background-color: #1a1a2e !important; } ' +
        'body { filter: invert(0.9) hue-rotate(180deg) contrast(0.9) brightness(0.95) saturate(0.9) !important; } ' +
        'img, video, iframe, svg, canvas, [style*="background-image"] { ' +
        'filter: invert(1) hue-rotate(180deg) !important; }';
    (document.head || document.documentElement).appendChild(style);
})();
"""

    def _inject_dark_theme(self, web_view):
        """Инжект тёмной темы в загруженную страницу с учётом LEGACY_GPU."""
        enabled = getattr(self, '_dark_web_enabled', not LEGACY_GPU)
        if not enabled:
            return
        js = ("(function(){ window.__ccDarkEnabled = true;"
              "if (window.__ccSetBg) window.__ccSetBg();"
              "if (window.__ccApplyDark) window.__ccApplyDark(); })();")
        try:
            web_view.page().runJavaScript(js)
        except Exception as e:
            self.logger.debug(f"Ошибка инъекта тёмной темы: {e}")

    def toggle_web_dark_theme(self):
        """Переключает тёмную тему сайтов во всех вкладках.
        На старых GPU включение помечается как ручное (_dark_web_forced):
        новые вкладки снова получат фильтр, пользователь осознанно принял
        возможные рывки. Выключение возвращает плавный режим."""
        current = getattr(self, '_dark_web_enabled', not LEGACY_GPU)
        self._dark_web_enabled = not current
        if self._dark_web_enabled:
            if LEGACY_GPU:
                self._dark_web_forced = True
                self.logger.warning(
                    "⚠️ Тёмная тема сайтов включена вручную на старом GPU — "
                    "возможны рывки прокрутки")
            js = ("(function(){ window.__ccDarkEnabled = true;"
                  "if (window.__ccSetBg) window.__ccSetBg();"
                  "if (window.__ccApplyDark) window.__ccApplyDark(); })();")
        else:
            self._dark_web_forced = False
            js = ("(function(){ window.__ccDarkEnabled = false;"
                  "var a = document.getElementById('cc-dark-filter'); if (a) a.remove();"
                  "var b = document.getElementById('cc-dark-theme'); if (b) b.remove();"
                  "})();")
        for view in self.web_views:
            try:
                view.page().runJavaScript(js)
            except Exception:
                pass
        if hasattr(self, 'dark_web_btn'):
            try:
                self.dark_web_btn.setChecked(self._dark_web_enabled)
            except RuntimeError:
                pass
        self.logger.info(f"🌙 Тёмная тема сайтов: "
                         f"{'включена' if self._dark_web_enabled else 'выключена'}")

    def _get_theme(self):
        """Возвращает словарь текущей темы (поднимаясь к главному окну)"""
        w = self.parent()
        while w is not None:
            tm = getattr(w, 'theme_manager', None)
            if tm is not None:
                return tm.current_theme
            w = w.parent()
        return {}

    def showEvent(self, event):
        """При показе вкладки применяем тёмную тему ко всем элементам браузера"""
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_dark_style)

    def _apply_dark_style(self):
        """Перекрашивает навигацию, адресную строку и вкладки под тёмную тему"""
        t = self._get_theme()
        btn_style = f"""
            QPushButton {{
                background-color: {t.get('button', '#16213e')};
                color: {t.get('text', '#e4e4ef')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {t.get('accent', '#6c63ff')};
                color: #ffffff;
                border-color: {t.get('accent', '#6c63ff')};
            }}
        """
        # Кнопки навигации (создаются в init_ui, используем getattr для безопасности)
        for btn in (getattr(self, 'back_btn', None),
                    getattr(self, 'forward_btn', None),
                    getattr(self, 'reload_btn', None),
                    getattr(self, 'home_btn', None),
                    getattr(self, 'new_tab_btn', None),
                    getattr(self, 'ucoin_btn', None),
                    getattr(self, 'price_btn', None),
                    getattr(self, 'passwords_btn', None),
                    getattr(self, 'copy_url_btn', None)):
            if btn is not None:
                btn.setStyleSheet(btn_style)
        # Адресная строка
        if getattr(self, 'url_bar', None) is not None:
            self.url_bar.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {t.get('input_bg', '#16213e')};
                    color: {t.get('text', '#e4e4ef')};
                    border: 1px solid {t.get('border', '#2a2a4a')};
                    border-radius: 6px;
                    padding: 3px 8px;
                }}
                QLineEdit:focus {{
                    border-color: {t.get('accent', '#6c63ff')};
                }}
            """)
        # Вкладки браузера
        if getattr(self, 'tab_widget', None) is not None:
            self.tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: 1px solid {t.get('border', '#2a2a4a')};
                    background-color: {t.get('base', '#1a1a2e')};
                }}
                QTabBar::tab {{
                    background-color: {t.get('tab_bg', '#0f0f1a')};
                    color: {t.get('tab_text', '#8888aa')};
                    padding: 5px 10px;
                    min-width: 100px;
                    max-width: 200px;
                }}
                QTabBar::tab:selected {{
                    background-color: {t.get('tab_selected', '#16213e')};
                    color: {t.get('tab_selected_text', '#e4e4ef')};
                    border-bottom: 2px solid {t.get('accent', '#6c63ff')};
                }}
                QTabBar::tab:hover:!selected {{
                    background-color: {t.get('surface_hover', '#1f2b47')};
                }}
            """)
        # Контейнер веб-вью — тёмный фон вместо белого
        if getattr(self, 'webview_container', None) is not None:
            self.webview_container.setStyleSheet(
                f"background-color: {t.get('base', '#1a1a2e')};"
            )
        # Прогресс-бар
        if getattr(self, 'progress_bar', None) is not None:
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: none;
                    background-color: {t.get('input_bg', '#16213e')};
                }}
                QProgressBar::chunk {{
                    background-color: {t.get('accent', '#6c63ff')};
                }}
            """) 
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        self.create_navigation_bar(layout)
        # === ПАНЕЛЬ ПОДСВЕТКИ ТЕКСТА НА СТРАНИЦЕ ===
        hl_wrap = QWidget()
        hl_wrap.setStyleSheet(
            "background-color: #16213e; border-bottom: 1px solid #2a2a4a;")
        hl_bar = QHBoxLayout(hl_wrap)
        hl_bar.setContentsMargins(6, 3, 6, 3)
        hl_bar.setSpacing(6)
        hl_label = QLabel("🔆 Подсветка:")
        hl_label.setStyleSheet("color: #a8a8d0; font-size: 11px;")
        hl_bar.addWidget(hl_label)
        self.highlight_edit = QLineEdit()
        self.highlight_edit.setPlaceholderText(
            "Текст для подсветки на странице (регистр не важен)…")
        self.highlight_edit.setClearButtonEnabled(True)
        self.highlight_edit.setMinimumHeight(26)
        self.highlight_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a2e;
                color: #e4e4ef;
                border: 1px solid #2a2a4a;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #ffeb3b; }
        """)
        self.highlight_edit.textChanged.connect(self._on_highlight_edit_changed)
        hl_bar.addWidget(self.highlight_edit, 1)
        hl_clear_btn = QPushButton("✖ Снять")
        hl_clear_btn.setFixedSize(70, 26)
        hl_clear_btn.setToolTip("Убрать всю подсветку на страницах")
        hl_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #16213e;
                color: #e4e4ef;
                border: 1px solid #2a2a4a;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #6c63ff;
                color: #ffffff;
                border-color: #6c63ff;
            }
        """)
        hl_clear_btn.clicked.connect(self._clear_highlight_clicked)
        hl_bar.addWidget(hl_clear_btn)
        layout.addWidget(hl_wrap)
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet(
            "color: #666; padding: 2px 5px; background-color: #f5f5f5; "
            "border-top: 1px solid #ddd;")
        self.status_label.setMaximumHeight(25)
        if WEBENGINE_AVAILABLE:
            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximumHeight(3)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background-color: #e0e0e0;
                }
                QProgressBar::chunk {
                    background-color: #4a6fa5;
                }
            """)
            layout.addWidget(self.progress_bar)
            self.tab_widget = QTabWidget()
            self.tab_widget.setTabsClosable(True)
            self.tab_widget.tabCloseRequested.connect(self.close_tab)
            self.tab_widget.currentChanged.connect(self.on_tab_changed)
            self.tab_widget.setDocumentMode(True)
            self.tab_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tab_widget.customContextMenuRequested.connect(self.show_tab_context_menu)
            self.tab_widget.tabBar().setExpanding(True)
            self.tab_widget.tabBar().setDocumentMode(True)
            self.tab_widget.setElideMode(Qt.ElideRight)
            self.tab_widget.setStyleSheet("""
                QTabWidget::pane { border: none; }
                QTabBar::tab { min-width: 100px; max-width: 200px; padding: 5px 10px; }
                QTabBar::tab:!selected { background-color: #e0e0e0; }
                QTabBar::tab:selected { background-color: #4a6fa5; color: white; }
                QTabBar::tab:hover { background-color: #5a7fb5; color: white; }
            """)
            layout.addWidget(self.tab_widget)
        else:
            info_label = QLabel(
                "🌐 Встроенный браузер\n\nДля работы установите:\n"
                "pip install PySide6-WebEngine")
            info_label.setAlignment(Qt.AlignCenter)
            info_label.setWordWrap(True)
            layout.addWidget(info_label)  

    def create_navigation_bar(self, layout):
        """Создает панель навигации браузера (тёмная тема)"""
        # Получаем текущую тему
        t = {}
        w = self.parent()
        while w is not None:
            tm = getattr(w, 'theme_manager', None)
            if tm is not None:
                t = tm.current_theme
                break
            w = w.parent()

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {t.get('base', '#1a1a2e')};
                border: none;
                border-bottom: 1px solid {t.get('border', '#2a2a4a')};
                padding: 2px;
                spacing: 3px;
            }}
        """)

        nav_btn_style = f"""
            QPushButton {{
                background-color: {t.get('button', '#16213e')};
                color: {t.get('text', '#e4e4ef')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {t.get('accent', '#6c63ff')};
                color: #ffffff;
                border-color: {t.get('accent', '#6c63ff')};
            }}
        """

        back_btn = QPushButton("◀")
        back_btn.setFixedSize(32, 28)
        back_btn.setToolTip("Назад")
        back_btn.setStyleSheet(nav_btn_style)
        back_btn.clicked.connect(self.go_back)
        toolbar.addWidget(back_btn)

        forward_btn = QPushButton("▶")
        forward_btn.setFixedSize(32, 28)
        forward_btn.setToolTip("Вперёд")
        forward_btn.setStyleSheet(nav_btn_style)
        forward_btn.clicked.connect(self.go_forward)
        toolbar.addWidget(forward_btn)

        self.reload_btn = QPushButton("🔄")
        self.reload_btn.setFixedSize(32, 28)
        self.reload_btn.setToolTip("Обновить")
        self.reload_btn.setStyleSheet(nav_btn_style)
        self.reload_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.reload_btn)

        home_btn = QPushButton("🏠")
        home_btn.setFixedSize(32, 28)
        home_btn.setToolTip("Домой")
        home_btn.setStyleSheet(nav_btn_style)
        home_btn.clicked.connect(self.go_home)
        toolbar.addWidget(home_btn)

        toolbar.addSeparator()

        ucoin_btn = QPushButton("🔑 UCOIN")
        ucoin_btn.setFixedSize(70, 28)
        ucoin_btn.clicked.connect(self.login_to_ucoin)
        ucoin_btn.setToolTip("Автоматический вход на UCOIN.net")
        ucoin_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        toolbar.addWidget(ucoin_btn)

        price_btn = QPushButton("📥 Прайс")
        price_btn.setFixedSize(70, 28)
        price_btn.clicked.connect(self.download_price_list)
        price_btn.setToolTip("Скачать прайс")
        price_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
        """)
        toolbar.addWidget(price_btn)

        passwords_btn = QPushButton("🔐")
        passwords_btn.setFixedSize(32, 28)
        passwords_btn.setToolTip("Менеджер паролей")
        passwords_btn.setStyleSheet(nav_btn_style)
        passwords_btn.clicked.connect(self.show_password_manager)
        toolbar.addWidget(passwords_btn)

        toolbar.addSeparator()

        copy_url_btn = QPushButton("📋")
        copy_url_btn.setFixedSize(32, 28)
        copy_url_btn.clicked.connect(self.copy_current_url)
        copy_url_btn.setToolTip("Копировать ссылку")
        copy_url_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        toolbar.addWidget(copy_url_btn)

        toolbar.addSeparator()

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Введите URL...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setMinimumHeight(28)
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('input_bg', '#16213e')};
                color: {t.get('text', '#e4e4ef')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 6px;
                padding: 3px 8px;
            }}
            QLineEdit:focus {{
                border-color: {t.get('accent', '#6c63ff')};
            }}
        """)
        toolbar.addWidget(self.url_bar)

        toolbar.addSeparator()

        if WEBENGINE_AVAILABLE:
            new_tab_btn = QPushButton("➕")
            new_tab_btn.setFixedSize(32, 28)
            new_tab_btn.setToolTip("Новая вкладка")
            new_tab_btn.setStyleSheet(nav_btn_style)
            new_tab_btn.clicked.connect(lambda: self.add_new_tab())
            toolbar.addWidget(new_tab_btn)

        layout.addWidget(toolbar)
  
    def load_in_current_tab(self, url):
        """Загружает URL в текущей вкладке"""
        current_view = self.get_current_web_view()
        if current_view:
            clean_url = url
            clean_url = re.sub(r'[?&]mode=print', '', clean_url)
            clean_url = re.sub(r'[?&]mode=pdf', '', clean_url)
            clean_url = re.sub(r'[?&]export=\w+(?=&|$)', '', clean_url)
            clean_url = re.sub(r'[?&]$', '', clean_url)
            # === ПРИНУДИТЕЛЬНЫЙ РУССКИЙ ЯЗЫК ДЛЯ MESHOK ===
            if 'meshok.net' in clean_url and 'lang=' not in clean_url:
                clean_url = clean_url + ('&' if '?' in clean_url else '?') + 'lang=ru'
            current_view.setUrl(QUrl(clean_url))
            self.logger.info(f"📑 Загружено в текущей вкладке: {clean_url[:80]}")
            QTimer.singleShot(500, lambda: self._inject_click_handler(current_view))
    
    def show_tab_context_menu(self, position):
        """Показывает контекстное меню для вкладок"""
        tab_bar = self.tab_widget.tabBar()
        tab_index = tab_bar.tabAt(position)
        
        menu = QMenu(self)
        
        if tab_index >= 0:
            close_action = QAction("❌ Закрыть вкладку", self)
            close_action.triggered.connect(lambda: self.close_tab(tab_index))
            menu.addAction(close_action)
            
            menu.addSeparator()
            
            close_others_action = QAction("📌 Закрыть все кроме этой", self)
            close_others_action.triggered.connect(lambda: self.close_other_tabs(tab_index))
            menu.addAction(close_others_action)
            
            close_left_action = QAction("⬅️ Закрыть вкладки слева", self)
            close_left_action.triggered.connect(lambda: self.close_tabs_to_left(tab_index))
            menu.addAction(close_left_action)
            
            close_right_action = QAction("➡️ Закрыть вкладки справа", self)
            close_right_action.triggered.connect(lambda: self.close_tabs_to_right(tab_index))
            menu.addAction(close_right_action)
            
            menu.addSeparator()
            
            duplicate_action = QAction("📋 Дублировать вкладку", self)
            duplicate_action.triggered.connect(lambda: self.duplicate_tab(tab_index))
            menu.addAction(duplicate_action)
        else:
            new_tab_action = QAction("➕ Новая вкладка", self)
            new_tab_action.triggered.connect(lambda: self.add_new_tab())
            menu.addAction(new_tab_action)
        
        menu.exec(tab_bar.mapToGlobal(position))
    
    def close_other_tabs(self, current_index):
        """Закрывает все вкладки кроме указанной"""
        for i in range(self.tab_widget.count() - 1, -1, -1):
            if i != current_index:
                self.close_tab(i)
    
    def close_tabs_to_right(self, current_index):
        """Закрывает вкладки справа от указанной"""
        for i in range(self.tab_widget.count() - 1, current_index, -1):
            self.close_tab(i)
    
    def close_tabs_to_left(self, current_index):
        """Закрывает вкладки слева от указанной"""
        for i in range(current_index - 1, -1, -1):
            self.close_tab(i)
    
    def duplicate_tab(self, index):
        """Дублирует вкладку"""
        web_view = self.tab_widget.widget(index)
        if web_view:
            current_url = web_view.url().toString()
            if current_url and current_url != "about:blank":
                self.add_new_tab(current_url)
            else:
                self.add_new_tab()

    def setup_profile(self):
        if not WEBENGINE_AVAILABLE:
            return
        try:
            profile_path = str(self.storage_path / self.profile_name)
            Path(profile_path).mkdir(parents=True, exist_ok=True)
            self.profile = QWebEngineProfile(self.profile_name, self)
            self.profile.setPersistentStoragePath(profile_path)
            self.profile.setPersistentCookiesPolicy(
                QWebEngineProfile.ForcePersistentCookies)
            self.profile.settings().setAttribute(QWebEngineSettings.AutoLoadImages, True)
            self.profile.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.profile.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            self.profile.downloadRequested.connect(self.on_download_requested)
            cache_path = Path(profile_path) / "cache"
            cache_path.mkdir(exist_ok=True)
            self.profile.setCachePath(str(cache_path))

            # === РУССКИЙ ЯЗЫК, СПОСОБ 1: методы (если есть в сборке PySide6) ===
            if hasattr(self.profile, 'setHttpAcceptLanguages'):
                try:
                    self.profile.setHttpAcceptLanguages(["ru-RU", "ru", "en;q=0.5"])
                    self.logger.info("✅ Accept-Language: ru-RU "
                                     "(метод setHttpAcceptLanguages)")
                except Exception as e:
                    self.logger.debug(f"setHttpAcceptLanguages: {e}")
            else:
                # === СПОСОБ 2: Qt-СВОЙСТВА (PySide6 6.6+: методов нет,
                #     но свойства httpAcceptLanguages / urlRequestInterceptor есть) ===
                try:
                    self.profile.httpAcceptLanguages = ["ru-RU", "ru", "en;q=0.5"]
                    self.logger.info("✅ Accept-Language: ru-RU "
                                     "(свойство httpAcceptLanguages)")
                except Exception as e:
                    self.logger.warning(f"⚠️ httpAcceptLanguages недоступен: {e}")

            # === ИНТЕРЦЕПТОР: метод ИЛИ свойство (держим ссылку, чтобы не съел GC) ===
            if QWebEngineUrlRequestInterceptor:
                try:
                    self._russian_interceptor = RussianLanguageInterceptor(self)
                    if hasattr(self.profile, 'setRequestInterceptor'):
                        self.profile.setRequestInterceptor(self._russian_interceptor)
                    elif hasattr(self.profile, 'setUrlRequestInterceptor'):
                        self.profile.setUrlRequestInterceptor(self._russian_interceptor)
                    else:
                        self.profile.urlRequestInterceptor = self._russian_interceptor
                    self.logger.info("✅ Интерцептор Accept-Language установлен")
                except Exception as e:
                    self.logger.warning(f"⚠️ Не удалось установить интерцептор: {e}")

            self.logger.info(f"✅ Профиль браузера настроен: {profile_path}")
        except Exception as e:
            self.logger.error(f"Ошибка настройки профиля: {e}")

    def on_download_requested(self, download):
        download_dir = paths.get_price_dir()
        download_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_filename = f"price_{timestamp}.xls"
        download.setDownloadDirectory(str(download_dir))
        download.setDownloadFileName(suggested_filename)
        download.accept()
        self.status_label.setText(f"📥 Скачивание: {suggested_filename}")
        QTimer.singleShot(3000, lambda: self.status_label.setText(f"✅ Прайс сохранён: {suggested_filename}"))

    # JS: убирает белую вспышку и затемняет СВЕТЛЫЕ страницы (тёмные не трогает).
    # ВАЖНО: фильтр вешается на BODY (не на html) — body растянут на всю высоту
    # документа, поэтому тёмная тема покрывает страницу целиком, включая прокрутку.
    DARK_PAGE_JS = """
(function() {
    if (window.__ccDarkInstalled) return;
    window.__ccDarkInstalled = true;
    var DARK = '#1a1a2e';

    // Сразу тёмный фон — убирает белую вспышку
    if (document.documentElement) {
        document.documentElement.style.backgroundColor = DARK;
    }

    function isLight(r, g, b) { return (0.299 * r + 0.587 * g + 0.114 * b) > 120; }

    function pageIsLight() {
        try {
            var el = document.body || document.documentElement;
            var c = getComputedStyle(el).backgroundColor;
            var m = c && c.match(/rgba?\\(\\s*(\\d+),\\s*(\\d+),\\s*(\\d+)/);
            if (!m) return true;
            if (c.indexOf('rgba') === 0 && m[1] === '0' && m[2] === '0' && m[3] === '0') return true;
            return isLight(+m[1], +m[2], +m[3]);
        } catch (e) { return true; }
    }

    function applyDark() {
        if (document.getElementById('cc-dark-filter')) return;
        if (!pageIsLight()) return;
        var s = document.createElement('style');
        s.id = 'cc-dark-filter';
        s.textContent =
            'html{background:' + DARK + '!important;}' +
            'body{filter:invert(0.9) hue-rotate(180deg) contrast(0.9) brightness(0.95) saturate(0.9)!important;}' +
            'img,video,iframe,svg,canvas,[class*="logo"]{filter:invert(1) hue-rotate(180deg)!important;}';
        (document.head || document.documentElement).appendChild(s);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyDark);
    } else {
        applyDark();
    }
    window.addEventListener('load', applyDark);
})();
"""

    def create_web_view(self):
        if not WEBENGINE_AVAILABLE:
            return None
        try:
            view = CustomWebView(self)
            view.browser = self
            if self.profile:
                page = CustomWebEnginePage(self.profile, self, view)
                page.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
                page.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
                page.settings().setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
                view.setPage(page)
            try:
                from PySide6.QtGui import QColor
                view.page().setBackgroundColor(QColor('#262640'))
            except Exception:
                pass
            self._install_dark_page_script(view)
            self._install_russian_redirect_script(view)
            # === ПОДСВЕТКА ТЕКСТА: функции доступны с момента создания документа ===
            self._install_highlight_script(view)
            view.setZoomFactor(0.8)
            view.urlChanged.connect(self.on_url_changed)
            view.titleChanged.connect(self.on_title_changed)
            view.loadProgress.connect(self.on_load_progress)
            view.loadFinished.connect(lambda ok, v=view: self._log_load_finished(ok, v))
            view.urlChanged.connect(lambda u, v=view: self._log_url_change(u, v))
            # === ПОДСВЕТКА: повторное применение после загрузки/SPA-рендера ===
            view.loadFinished.connect(
                lambda ok, v=view: self._reapply_highlight(ok, v))
            self._inject_click_handler(view)
            self.web_views.append(view)
            self.logger.info("✅ WebView создан")
            return view
        except Exception as e:
            self.logger.error(f"Ошибка создания WebView: {e}")
            return None

    def _log_load_finished(self, ok, view):
        """Логирует успех/провал загрузки страницы."""
        url = view.url().toString()
        if ok:
            self.logger.info(f"✅ Страница загружена: {url[:110]}")
        else:
            self.logger.error(f"❌ Страница НЕ загрузилась: {url[:110]}")

    def _log_url_change(self, url, view):
        """Логирует увод на /en/ и возврат на русскую версию."""
        u = url.toString()
        prev = getattr(view, '_cc_prev_url', '')
        view._cc_prev_url = u
        if not prev or u == prev:
            return
        if '/en/' in u and '/en/' not in prev:
            self.logger.warning(f"🌐 УВОД НА /en/: {prev[:80]} → {u[:110]}")
        elif '/en/' in prev and '/en/' not in u:
            self.logger.info(f"🌐 ВОЗВРАТ с /en/ на русскую версию: {u[:110]}")

    def _install_dark_page_script(self, view):
        """Ставит скрипт тёмной темы сайтов.
        НА СТАРЫХ GPU (LEGACY_GPU) полноэкранный CSS-фильтр НЕ ставится:
        программная растеризация не успевает пересчитывать фильтр на каждый
        кадр прокрутки → рывки. Тёмными остаются фон страницы, навигация и
        интерфейс программы; фильтр можно включить вручную кнопкой темы
        (тогда self._dark_web_forced = True)."""
        if LEGACY_GPU and not getattr(self, '_dark_web_forced', False):
            self.logger.info(
                "ℹ️ Тёмная тема сайтов отключена (старый GPU): полноэкранный "
                "CSS-фильтр вызывает рывки прокрутки. Включить вручную: кнопка темы")
            return
        try:
            from PySide6.QtWebEngineCore import QWebEngineScript
            script = QWebEngineScript()
            script.setName("cc_dark_page")
            try:
                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
                script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            except AttributeError:
                script.setInjectionPoint(QWebEngineScript.DocumentCreation)
                script.setWorldId(QWebEngineScript.MainWorld)
            script.setRunsOnSubFrames(True)
            script.setSourceCode(self.DARK_PAGE_JS)
            view.page().scripts().insert(script)
        except Exception as e:
            self.logger.error(f"Ошибка установки тёмного фона страницы: {e}")

    def _install_russian_redirect_script(self, view):
        """Принудительный русский язык Meshok/UCOIN БЕЗ петли редиректов.
        ГЛАВНОЕ ИСПРАВЛЕНИЕ: счётчик редиректов БОЛЬШЕ НЕ СБРАСЫВАЕТСЯ на
        русской странице и добавлен кулдаун 10 сек — бесконечный цикл
        / <-> /en/ (который грузил CPU до 60%) невозможен физически.
        После исчерпания лимита сторож останавливается (clearInterval)."""
        try:
            from PySide6.QtWebEngineCore import QWebEngineScript
            script = QWebEngineScript()
            script.setName("cc_russian_redirect")
            try:
                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
                script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            except AttributeError:
                script.setInjectionPoint(QWebEngineScript.DocumentCreation)
                script.setWorldId(QWebEngineScript.MainWorld)
            script.setRunsOnSubFrames(False)
            script.setSourceCode("""
(function() {
    if (window.__ccRussianRedirect) return;
    window.__ccRussianRedirect = true;
    console.log('CC-RU: скрипт установлен на ' + window.location.href);

    // === 0) navigator.language = ru-RU до запуска JS сайта ===
    try {
        Object.defineProperty(Navigator.prototype, 'language', {
            get: function() { return 'ru-RU'; }, configurable: true });
        Object.defineProperty(Navigator.prototype, 'languages', {
            get: function() { return ['ru-RU', 'ru']; }, configurable: true });
    } catch (e) {}

    function isMeshok() {
        return window.location.hostname.indexOf('meshok.net') !== -1;
    }

    function setCookies() {
        try {
            var cookies = ['lang=ru', 'i18n_redirected=ru', 'locale=ru', 'meshok_lang=ru'];
            for (var i = 0; i < cookies.length; i++) {
                var name = cookies[i].split('=')[0] + '=';
                if (document.cookie.indexOf(name) === -1) {
                    document.cookie = cookies[i] +
                        '; path=/; domain=.meshok.net; max-age=31536000; SameSite=Lax';
                    console.log('CC-RU: cookie установлена: ' + cookies[i]);
                }
            }
            localStorage.setItem('lang', 'ru');
            localStorage.setItem('locale', 'ru');
            localStorage.setItem('i18n_redirected', 'ru');
        } catch (e) {}
    }

    // === ЗАЩИТА ОТ ПЕТЛИ: максимум 2 редиректа на вкладку, не чаще раза в 10 сек ===
    var MAX_REDIRECTS = 2;
    var COOLDOWN_MS = 10000;
    var timerId = null;

    function stopWatchdog() {
        if (timerId !== null) {
            clearInterval(timerId);
            timerId = null;
        }
    }

    function fixLang() {
        if (!isMeshok()) return;
        setCookies();
        var path = window.location.pathname;
        if (path.indexOf('/en/') === 0 || path === '/en') {
            var cnt = 0, last = 0, now = Date.now();
            try { cnt = parseInt(sessionStorage.getItem('cc_ru_redir_count') || '0', 10) || 0; } catch (e) {}
            try { last = parseInt(sessionStorage.getItem('cc_ru_redir_last') || '0', 10) || 0; } catch (e) {}
            if (cnt < MAX_REDIRECTS && (now - last) > COOLDOWN_MS) {
                try {
                    sessionStorage.setItem('cc_ru_redir_count', String(cnt + 1));
                    sessionStorage.setItem('cc_ru_redir_last', String(now));
                } catch (e) {}
                var newPath = path.replace(/^\\/en/, '') || '/';
                var newUrl = window.location.origin + newPath +
                             window.location.search + window.location.hash;
                console.log('CC-RU: редирект /en/ -> ' + newUrl +
                            ' (попытка ' + (cnt + 1) + '/' + MAX_REDIRECTS + ')');
                window.location.replace(newUrl);
            } else {
                // НЕ воюем с сервером/роутером: остаёмся и ОСТАНАВЛИВАЕМ сторож,
                // чтобы не жечь CPU постоянными проверками
                console.log('CC-RU: лимит редиректов исчерпан — остаёмся на текущем URL, сторож остановлен');
                stopWatchdog();
            }
        }
        // ВАЖНО: на русской странице счётчик НЕ сбрасываем —
        // именно сброс раньше вызывал бесконечный цикл / <-> /en/
    }

    fixLang();
    timerId = setInterval(fixLang, 1000);
    window.addEventListener('popstate', fixLang);
    try {
        var origPush = history.pushState;
        history.pushState = function() {
            var r = origPush.apply(this, arguments);
            setTimeout(fixLang, 0);
            return r;
        };
        var origReplace = history.replaceState;
        history.replaceState = function() {
            var r = origReplace.apply(this, arguments);
            setTimeout(fixLang, 0);
            return r;
        };
    } catch (e) {}

    // === UCOIN: en.ucoin.net / ucoin.net -> ru.ucoin.net ===
    if (window.location.hostname === 'ucoin.net' ||
        window.location.hostname.indexOf('en.ucoin.net') !== -1) {
        window.location.replace('https://ru.ucoin.net' +
                                window.location.pathname + window.location.search);
    }
})();
""")
            view.page().scripts().insert(script)
            self.logger.info("✅ JS-редирект русского языка установлен "
                             "(лимитами без петли + остановка сторожа)")
        except Exception as e:
            self.logger.error(f"Не удалось установить JS-редирект: {e}")

    def _inject_click_handler(self, web_view):
        """Внедряет JavaScript для перехвата ПКМ и ЛКМ на ссылках монет +
        функцию collectAllCoinLinks для массового добавления."""
        if not web_view:
            return
        if hasattr(web_view, '_handler_injected') and web_view._handler_injected:
            return
        js_code = """
(function() {
    if (window._ccHandlerInstalled) return;
    window._ccHandlerInstalled = true;

    // === УТИЛИТЫ ===
    function getAbsoluteUrl(href) {
        try { return new URL(href, window.location.href).toString(); }
        catch (e) { return href; }
    }
    function cleanUrl(url) {
        return url.replace(/\\s+/g, '').trim();
    }
    function isCoinLink(url) {
        if (!url) return false;
        return url.indexOf('/coin/') !== -1 && url.indexOf('ucid=') !== -1;
    }
    function findLink(el) {
        var parent = el;
        for (var i = 0; i < 5 && parent; i++) {
            if (parent.href) return parent;
            if (parent.tagName === 'A' && parent.getAttribute('href')) return parent;
            parent = parent.parentElement;
        }
        return null;
    }

    // === ПЕРЕХВАТ ЛКМ (как было) ===
    document.addEventListener('click', function(event) {
        var target = event.target;
        var link = findLink(target);
        if (link && link.href) {
            var button = event.button;
            if (button !== 0) return;
            console.log('CoinCollector: LEFT CLICK intercepted for ' + link.href);
            event.preventDefault();
            event.stopPropagation();
            var absoluteUrl = getAbsoluteUrl(link.href);
            var cleanUrlStr = cleanUrl(absoluteUrl);
            var frame = document.createElement('iframe');
            frame.style.display = 'none';
            frame.src = 'coin-collector://click?button=' + button + '&url=' + encodeURIComponent(cleanUrlStr);
            document.body.appendChild(frame);
            setTimeout(function() { document.body.removeChild(frame); }, 10);
            return false;
        }
    }, true);

    // === МАССОВОЕ ДОБАВЛЕНИЕ: функция сбора всех ссылок на монеты ===
    window.collectAllCoinLinks = function() {
        var results = [];
        var allLinks = document.querySelectorAll('a[href]');
        var seen = {};
        for (var i = 0; i < allLinks.length; i++) {
            var a = allLinks[i];
            var href = a.href || '';
            if (!href) continue;
            if (href.indexOf('/coin/') === -1 || href.indexOf('ucid=') === -1) continue;
            try {
                var absUrl = new URL(href, window.location.href).toString();
            } catch (e) { continue; }
            if (seen[absUrl]) continue;
            seen[absUrl] = true;
            results.push(absUrl);
            if (results.length >= 24) break;
        }
        return results;
    };
})();
"""
        try:
            web_view.page().runJavaScript(js_code)
            web_view._handler_injected = True
        except Exception as e:
            self.logger.debug(f"Не удалось инжектить JS-обработчик: {e}")

    def _delayed_init(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            self.setup_profile()
            urls = self.settings.value('open_tabs', [])
            if urls and isinstance(urls, list):
                for url in urls[:5]:
                    if url and isinstance(url, str):
                        self.add_new_tab(url, switch_to=False)
            if self.tab_widget.count() == 0:
                self.add_new_tab()
            self.logger.info("✅ Браузер полностью инициализирован")
        except Exception as e:
            self.logger.error(f"Ошибка инициализации браузера: {e}")
            self._initialized = False
    
    def add_new_tab(self, url=None, switch_to=True):
        if not WEBENGINE_AVAILABLE:
            return None
        if not self._initialized:
            QTimer.singleShot(100, lambda: self.add_new_tab(url, switch_to))
            return None
        if not self.tab_widget:
            return None
        try:
            web_view = self.create_web_view()
            if not web_view:
                return None
            if url:
                clean_url = url
                clean_url = re.sub(r'[?&]mode=print', '', clean_url)
                clean_url = re.sub(r'[?&]mode=pdf', '', clean_url)
                clean_url = re.sub(r'[?&]export=\w+(?=&|$)', '', clean_url)
                clean_url = re.sub(r'[?&]$', '', clean_url)
                # === ПРИНУДИТЕЛЬНЫЙ РУССКИЙ ЯЗЫК ДЛЯ MESHOK ===
                if 'meshok.net' in clean_url and 'lang=' not in clean_url:
                    clean_url = clean_url + ('&' if '?' in clean_url else '?') + 'lang=ru'
                web_view.setUrl(QUrl(clean_url))
                short_title = self._get_short_title(clean_url)
                index = self.tab_widget.addTab(web_view, short_title)
                self.logger.info(f"📑 Новая вкладка: {clean_url[:80]}")
            else:
                web_view.setUrl(QUrl("about:blank"))
                index = self.tab_widget.addTab(web_view, "Новая вкладка")
            if switch_to:
                self.tab_widget.setCurrentIndex(index)
            QTimer.singleShot(500, lambda: self._inject_click_handler(web_view))
            return web_view
        except RuntimeError as e:
            self.logger.error(f"Ошибка при создании вкладки: {e}")
            return None
   
    def add_new_tab_background(self, url=None):
        """Добавляет новую фоновую вкладку и сразу начинает загрузку"""
        if not WEBENGINE_AVAILABLE:
            return None
        if not self._initialized:
            QTimer.singleShot(100, lambda: self.add_new_tab_background(url))
            return None
        if not self.tab_widget:
            return None
        try:
            web_view = self.create_web_view()
            if not web_view:
                return None
            if url:
                clean_url = url
                clean_url = re.sub(r'[?&]mode=print', '', clean_url)
                clean_url = re.sub(r'[?&]mode=pdf', '', clean_url)
                clean_url = re.sub(r'[?&]export=\w+(?=&|$)', '', clean_url)
                clean_url = re.sub(r'[?&]$', '', clean_url)
                # === ПРИНУДИТЕЛЬНЫЙ РУССКИЙ ЯЗЫК ДЛЯ MESHOK ===
                if 'meshok.net' in clean_url and 'lang=' not in clean_url:
                    clean_url = clean_url + ('&' if '?' in clean_url else '?') + 'lang=ru'
                web_view.setUrl(QUrl(clean_url))
                short_title = self._get_short_title(clean_url)
                index = self.tab_widget.addTab(web_view, short_title)
                self.logger.info(f"📑 Фоновая вкладка (загружается): {clean_url[:80]}")
            else:
                web_view.setUrl(QUrl("about:blank"))
                index = self.tab_widget.addTab(web_view, "Новая вкладка")
            return web_view
        except RuntimeError as e:
            self.logger.error(f"Ошибка при создании фоновой вкладки: {e}")
            return None
 
    def get_current_web_view(self):
        if not WEBENGINE_AVAILABLE or not self._initialized:
            return None
        if hasattr(self, 'tab_widget') and self.tab_widget:
            current_index = self.tab_widget.currentIndex()
            if current_index >= 0:
                return self.tab_widget.widget(current_index)
        return None
    
    def _get_short_title(self, url):
        if not url or url == "about:blank":
            return "Новая вкладка"
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        
        parts = domain.split('.')
        if len(parts) >= 2:
            domain = parts[-2]
        
        if domain:
            return domain[:20]
        
        if len(url) > 25:
            return url[:22] + "..."
        return url
    
    def navigate_to_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text:
            return
        if not url_text.startswith(('http://', 'https://')):
            url_text = 'https://' + url_text
        # === ПРИНУДИТЕЛЬНЫЙ РУССКИЙ ЯЗЫК ДЛЯ MESHOK ===
        if 'meshok.net' in url_text and 'lang=' not in url_text:
            url_text = url_text + ('&' if '?' in url_text else '?') + 'lang=ru'
        if WEBENGINE_AVAILABLE:
            web_view = self.get_current_web_view()
            if web_view:
                web_view.setUrl(QUrl(url_text))
        else:
            webbrowser.open(url_text)
    
    def go_back(self):
        """Назад по истории"""
        if WEBENGINE_AVAILABLE:
            web_view = self.get_current_web_view()
            if web_view and web_view.history().canGoBack():
                web_view.back()

    def go_forward(self):
        """Вперёд по истории"""
        if WEBENGINE_AVAILABLE:
            web_view = self.get_current_web_view()
            if web_view and web_view.history().canGoForward():
                web_view.forward()

    def go_home(self):
        """Домой (about:blank)"""
        if WEBENGINE_AVAILABLE:
            web_view = self.get_current_web_view()
            if web_view:
                web_view.setUrl(QUrl("about:blank"))

    def refresh(self):
        """Обновить текущую страницу"""
        if WEBENGINE_AVAILABLE:
            web_view = self.get_current_web_view()
            if web_view:
                web_view.reload()
 
    # ================= ПОДСВЕТКА ТЕКСТА НА СТРАНИЦЕ =================
    def _install_highlight_script(self, view):
        """Ставит функции ccHighlight/ccClearHighlight на стадию
        DocumentCreation — они доступны сразу после загрузки страницы."""
        try:
            from PySide6.QtWebEngineCore import QWebEngineScript
            script = QWebEngineScript()
            script.setName("cc_highlight")
            try:
                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
                script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            except AttributeError:
                script.setInjectionPoint(QWebEngineScript.DocumentCreation)
                script.setWorldId(QWebEngineScript.MainWorld)
            script.setRunsOnSubFrames(False)
            script.setSourceCode(HIGHLIGHT_JS)
            view.page().scripts().insert(script)
        except Exception as e:
            self.logger.error(f"Ошибка установки скрипта подсветки: {e}")

    def set_highlight_text(self, term):
        """Устанавливает термин подсветки во ВСЕХ вкладках этого браузера."""
        self._highlight_term = (term or '').strip()
        for view in self.web_views:
            self._apply_highlight(view)
        if self._highlight_term:
            self.logger.info(f"🔆 Подсветка текста: «{self._highlight_term}»")

    def clear_highlight(self):
        """Снимает подсветку во всех вкладках."""
        self.set_highlight_text('')

    def _apply_highlight(self, view):
        """Применяет текущий термин подсветки к одной вкладке."""
        term = getattr(self, '_highlight_term', '')
        js = f"if (window.ccHighlight) {{ ccHighlight({json.dumps(term)}); }}"
        try:
            view.page().runJavaScript(js)
        except Exception:
            pass

    def _reapply_highlight(self, ok, view):
        """После успешной загрузки страницы повторно применяем подсветку
        (SPA-рендер или перезагрузка могли стереть метки)."""
        if not ok:
            return
        if getattr(self, '_highlight_term', ''):
            QTimer.singleShot(300, lambda v=view: self._apply_highlight(v))

    def _on_highlight_edit_changed(self, text):
        """Дебаунс ввода строки подсветки 300 мс — не дёргаем DOM
        на каждый символ."""
        if not hasattr(self, '_highlight_timer'):
            self._highlight_timer = QTimer()
            self._highlight_timer.setSingleShot(True)
            self._highlight_timer.timeout.connect(
                lambda: self.set_highlight_text(self.highlight_edit.text()))
        self._highlight_timer.start(300)

    def _clear_highlight_clicked(self):
        """Кнопка «✖ Снять»: очищает строку и убирает метки."""
        if getattr(self, 'highlight_edit', None) is not None:
            self.highlight_edit.blockSignals(True)
            self.highlight_edit.clear()
            self.highlight_edit.blockSignals(False)
        self.clear_highlight()
 
    def on_url_changed(self, url):
        self.url_bar.setText(url.toString())
    
    def on_title_changed(self, title):
        self.update_title(title)
    
    def on_load_progress(self, progress):
        if self.progress_bar:
            self.progress_bar.setValue(progress)
            if progress >= 100:
                QTimer.singleShot(500, lambda: self.progress_bar.setValue(0) if self.progress_bar else None)
    
    def update_title(self, title):
        if not WEBENGINE_AVAILABLE:
            return
        
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            short_title = title if len(title) <= 40 else title[:37] + "..."
            self.tab_widget.setTabText(current_index, short_title)
            self.status_label.setText(f"🌐 {short_title}")
    
    def on_tab_changed(self, index):
        """Обработчик смены вкладки"""
        if index < 0:
            return
        
        web_view = self.tab_widget.widget(index)
        if web_view:
            current_url = web_view.url().toString()
            if current_url and current_url != "about:blank":
                self.url_bar.setText(current_url)
            else:
                self.url_bar.clear()
            
            title = web_view.title()
            if title:
                short_title = title if len(title) <= 40 else title[:37] + "..."
                self.status_label.setText(f"🌐 {short_title}")
            else:
                self.status_label.setText("Готов")
            
            QTimer.singleShot(500, lambda: self._inject_click_handler(web_view))
    
    def close_tab(self, index):
        if not WEBENGINE_AVAILABLE or not self._initialized:
            return
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            if widget in self.web_views:
                self.web_views.remove(widget)
            self.tab_widget.removeTab(index)
            widget.deleteLater()
        else:
            web_view = self.tab_widget.widget(index)
            if web_view:
                web_view.setUrl(QUrl("about:blank"))
                self.tab_widget.setTabText(index, "Новая вкладка")
    
    def login_to_ucoin(self):
        """Автоматический вход на UCOIN.net"""
        if not WEBENGINE_AVAILABLE:
            QMessageBox.warning(self, "Ошибка", "WebEngine не доступен")
            return
        
        from utils.password_manager import PasswordManager
        password_manager = PasswordManager()
        username, password = password_manager.get_password('ucoin')
        
        if not username or not password:
            from gui.dialogs.ucoin_settings_dialog import UcoinSettingsDialog
            dialog = UcoinSettingsDialog(password_manager, self)
            if dialog.exec():
                username, password = password_manager.get_password('ucoin')
            else:
                return
        
        if not username or not password:
            QMessageBox.warning(self, "Предупреждение", "Не указаны логин и пароль для UCOIN")
            return
        
        login_url = "https://ru.ucoin.net/login/"
        web_view = self.get_current_web_view()
        if not web_view:
            web_view = self.add_new_tab(login_url, switch_to=True)
        
        if not web_view:
            QMessageBox.warning(self, "Ошибка", "Не удалось создать вкладку браузера")
            return
        
        web_view.setUrl(QUrl(login_url))
        
        autofill_js = f"""
        (function() {{
            function waitForPage() {{
                var emailInput = document.querySelector('input[name="email"]') || 
                                 document.querySelector('input[type="email"]') ||
                                 document.querySelector('#email');
                var passInput = document.querySelector('input[name="password"]') || 
                                document.querySelector('input[type="password"]') ||
                                document.querySelector('#password');
                var loginBtn = document.querySelector('button[type="submit"]') ||
                               document.querySelector('input[type="submit"]') ||
                               document.querySelector('.login-button');
                
                if (emailInput && passInput) {{
                    emailInput.value = "{username}";
                    passInput.value = "{password}";
                    
                    emailInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    passInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    
                    setTimeout(function() {{
                        if (loginBtn) {{
                            loginBtn.click();
                        }} else {{
                            var form = emailInput.closest('form');
                            if (form) form.submit();
                        }}
                    }}, 1000);
                    return true;
                }}
                return false;
            }}
            
            if (document.readyState === 'complete') {{
                waitForPage();
            }} else {{
                window.addEventListener('load', function() {{
                    setTimeout(waitForPage, 500);
                }});
            }}
        }})();
        """
        
        def inject_js(ok):
            if ok:
                web_view.page().runJavaScript(autofill_js)
            try:
                web_view.loadFinished.disconnect(inject_js)
            except:
                pass
        
        web_view.loadFinished.connect(inject_js)
        
        self.status_label.setText(f"🔑 Автоматический вход для {username}...")
        self.logger.info(f"Автоматический вход на UCOIN для {username}")
    
    def download_price_list(self):
        """Вставляет ссылку на прайс в адресную строку и нажимает Enter"""
        if not WEBENGINE_AVAILABLE:
            QMessageBox.warning(self, "Ошибка", "WebEngine не доступен")
            return
        
        url = "https://ru.ucoin.net/uid2498?export=xls"
        
        web_view = self.get_current_web_view()
        if not web_view:
            web_view = self.add_new_tab(url)
        else:
            self.url_bar.setText(url)
            web_view.setUrl(QUrl(url))
        
        self.status_label.setText(f"📥 Загрузка прайса: {url}")
        self.logger.info(f"Загрузка прайса: {url}")
    
    def copy_current_url(self):
        """Копирует URL текущей страницы в буфер обмена"""
        if not WEBENGINE_AVAILABLE:
            QMessageBox.warning(self, "Ошибка", "WebEngine не доступен")
            return
        
        web_view = self.get_current_web_view()
        if not web_view:
            QMessageBox.warning(self, "Предупреждение", "Нет активной вкладки")
            return
        
        url = web_view.url().toString()
        if url and url != "about:blank":
            clipboard = QApplication.clipboard()
            clipboard.setText(url)
            self.status_label.setText(f"📋 URL скопирован: {url[:50]}...")
            self.logger.info(f"Скопирован URL: {url}")
        else:
            QMessageBox.warning(self, "Предупреждение", "Текущая страница не имеет URL")
    
    def show_password_manager(self):
        """Показывает диалог управления паролями"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Менеджер паролей")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Сайт", "Логин", "Пароль"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)
        
        def refresh_table():
            table.setRowCount(0)
            row = 0
            for domain, entries in self.password_manager.passwords.items():
                for entry in entries:
                    table.insertRow(row)
                    table.setItem(row, 0, QTableWidgetItem(domain))
                    table.setItem(row, 1, QTableWidgetItem(entry.get('username', '')))
                    table.setItem(row, 2, QTableWidgetItem("••••••••"))
                    row += 1
        
        refresh_table()
        
        btn_layout = QHBoxLayout()
        delete_btn = QPushButton("🗑️ Удалить выбранный")
        
        def delete_selected():
            current_row = table.currentRow()
            if current_row < 0:
                QMessageBox.warning(dialog, "Предупреждение", "Выберите запись для удаления")
                return
            domain = table.item(current_row, 0).text()
            username = table.item(current_row, 1).text()
            reply = QMessageBox.question(dialog, "Подтверждение", f"Удалить пароль для {domain} (логин: {username})?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.password_manager.delete_password(domain, username)
                refresh_table()
        
        delete_btn.clicked.connect(delete_selected)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        dialog.exec()
    
    def closeEvent(self, event):
        if WEBENGINE_AVAILABLE and self.tab_widget:
            urls = []
            for i in range(self.tab_widget.count()):
                web_view = self.tab_widget.widget(i)
                if web_view:
                    url = web_view.url().toString()
                    if url and url != "about:blank":
                        urls.append(url)
            self.settings.setValue('open_tabs', urls[:10])
        
        for web_view in self.web_views:
            try:
                web_view.deleteLater()
            except:
                pass
        
        super().closeEvent(event)

    def _add_to_collection(self, url):
        """Обработчик пункта 'Добавить в Коллекцию'"""
        if not url:
            self.logger.warning("URL пустой")
            return
        
        self.logger.info(f"➕ Добавление в коллекцию: {url}")
        
        # Копируем URL в буфер обмена
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(url)
        self.logger.debug("URL скопирован в буфер обмена")
        
        # Ищем главное окно
        from PySide6.QtWidgets import QApplication
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break
        
        if main_window:
            self.logger.debug("Главное окно найдено")
            if hasattr(main_window, '_add_coin_from_ucoin'):
                self.logger.debug(f"Вызываем _add_coin_from_ucoin с URL: {url}")
                main_window._add_coin_from_ucoin(url)
            else:
                self.logger.error("Метод _add_coin_from_ucoin не найден в главном окне")
                QMessageBox.warning(self, "Ошибка", "Функция временно недоступна")
                return
            
            self.status_label.setText("✅ Создается монета из UCOIN...")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))
        else:
            self.logger.error("Главное окно не найдено")
            QMessageBox.warning(self, "Ошибка", "Главное окно не найдено")

    # ================= МАССОВОЕ ДОБАВЛЕНИЕ В КОЛЛЕКЦИЮ =================

    def _mass_add_to_collection(self, page_url):
        """Запуск массового добавления: читает HTML страницы (toHtml),
        собирает ссылки на монеты и запускает последовательную обработку.
        
        Алгоритм:
        1. Читаем HTML страницы через toHtml (надёжно, без проблем JS-сериализации)
        2. Регулярным выражением извлекаем ссылки на монеты uCoin
        3. Показываем окно выбора с галочками (все выбраны по умолчанию)
        4. Пользователь снимает галочки с ненужных монет
        5. Запускается обработка только выбранных ссылок
        
        Работает на ЛЮБОЙ странице ucoin.net (каталоги, галереи, поиск, профили).
        """
        view = self.get_current_web_view()
        if not view:
            self.logger.error("❌ WebView не найден")
            return
        
        try:
            from collections import deque
            self.logger.info(f"🚀 Массовое добавление со страницы: {page_url}")
            self.status_label.setText("🔍 Чтение HTML страницы...")
            self.status_label.setStyleSheet("color: #4a6fa5;")

            # === ИНИЦИАЛИЗАЦИЯ ОЧЕРЕДИ ===
            self._mass_queue = deque()
            self._mass_total = 0
            self._mass_added = 0
            self._mass_errors = 0
            self._mass_current_view = None
            
            # === ЗАПОМИНАЕМ КОЛИЧЕСТВО ВКЛАДОК ДО НАЧАЛА ===
            # Лишние вкладки будем закрывать после каждой монеты
            self._mass_initial_tabs = len(self.web_views)

            # === ЗАПОМИНАЕМ ДОНОРА (выделенная курсором или первая с галочкой) ===
            self._mass_donor_id = None
            try:
                from PySide6.QtWidgets import QApplication
                for widget in QApplication.topLevelWidgets():
                    if widget.__class__.__name__ == 'MainWindow':
                        # Приоритет 1: выделенная курсором монета
                        if hasattr(widget, 'detail_panel') and widget.detail_panel.current_coin:
                            self._mass_donor_id = widget.detail_panel.current_coin.id
                            self.logger.info(f"🎯 Донор: выделенная курсором монета ID {self._mass_donor_id}")
                        # Приоритет 2: первая монета с галочкой
                        if not self._mass_donor_id and hasattr(widget, 'table_panel'):
                            try:
                                ids = widget.table_panel.get_selected_coin_ids()
                                if ids:
                                    self._mass_donor_id = ids[0]
                                    self.logger.info(f"🎯 Донор: монета с галочкой ID {self._mass_donor_id}")
                            except Exception:
                                pass
                        break
            except Exception as e:
                self.logger.error(f"Ошибка определения донора: {e}")
            
            if self._mass_donor_id:
                self.logger.info(f"🎯 Донор для массового добавления: ID {self._mass_donor_id}")
            else:
                self.logger.warning("⚠️ Донор не определён — будет использована последняя монета")

            # === ПОЛНОЕ ПОДАВЛЕНИЕ ДИАЛОГОВ НА ВРЕМЯ МАССОВОГО ДОБАВЛЕНИЯ ===
            self._mass_suppress_dialogs()

            # === ЧТЕНИЕ HTML СТРАНИЦЫ НАПРЯМУЮ ===
            # toHtml возвращает полный HTML — надёжнее чем JS (нет проблем с сериализацией)
            view.page().toHtml(lambda html: self._parse_mass_links_from_html(html, page_url))
            
        except Exception as e:
            self.logger.error(f"Ошибка массового добавления: {e}")
            import traceback
            traceback.print_exc()
            # Восстанавливаем диалоги при ошибке
            self._mass_restore_dialogs()

    def _mass_suppress_dialogs(self):
        """Полностью отключает все QMessageBox на время массового добавления"""
        try:
            from PySide6.QtWidgets import QMessageBox
            if getattr(self, '_mass_qmb_patched', False):
                return
            self._mass_orig_qmb = {
                'information': QMessageBox.information,
                'warning': QMessageBox.warning,
                'critical': QMessageBox.critical,
                'question': QMessageBox.question,
                'about': QMessageBox.about,
            }
            QMessageBox.information = lambda *a, **k: QMessageBox.Ok
            QMessageBox.warning = lambda *a, **k: QMessageBox.Ok
            QMessageBox.critical = lambda *a, **k: QMessageBox.Ok
            QMessageBox.question = lambda *a, **k: QMessageBox.Yes
            QMessageBox.about = lambda *a, **k: None
            self._mass_qmb_patched = True
            self.logger.info("🔇 Все диалоги подавлены на время массового добавления")
        except Exception as e:
            self.logger.error(f"Ошибка подавления диалогов: {e}")

    def _mass_restore_dialogs(self):
        """Восстанавливает все QMessageBox"""
        try:
            from PySide6.QtWidgets import QMessageBox
            if not getattr(self, '_mass_qmb_patched', False):
                return
            for name, orig in getattr(self, '_mass_orig_qmb', {}).items():
                setattr(QMessageBox, name, orig)
            self._mass_qmb_patched = False
            self.logger.info("🔔 Диалоги восстановлены")
        except Exception as e:
            self.logger.error(f"Ошибка восстановления диалогов: {e}")

    def _parse_mass_links_from_html(self, html, page_url):
        """Парсит HTML страницы и извлекает ссылки на монеты uCoin.
        Каждая монета на странице встречается несколько раз (фото аверса,
        реверса, описание) — дубли убираются."""
        import re
        if not html:
            self.status_label.setText("⚠️ Не удалось прочитать HTML страницы")
            self.status_label.setStyleSheet("color: #dc3545;")
            self.logger.warning("🚀 toHtml вернул пустой результат")
            return

        # Ищем все href, содержащие /coin/ и ucid= (формат ссылок на монеты uCoin)
        raw_links = re.findall(r'href="([^"]*?/coin/[^"]*?ucid=\d+)"', html)
        self.logger.info(f"🔎 Найдено сырых ссылок на монеты: {len(raw_links)}")

        urls = []
        seen = set()
        for href in raw_links:
            # Раскодируем HTML-сущности (&amp; -> &)
            href = href.replace('&amp;', '&')
            # Относительные ссылки делаем абсолютными
            if href.startswith('/'):
                href = 'https://ru.ucoin.net' + href
            elif not href.startswith('http'):
                continue
            # Убираем дубли (одна монета = несколько ссылок на странице)
            if href in seen:
                continue
            seen.add(href)
            urls.append(href)
            # Максимум 24 монеты за одну операцию
            if len(urls) >= 24:
                break

        self.logger.info(f"📋 Уникальных монет на странице: {len(urls)}")
        for u in urls:
            self.logger.info(f"   • {u}")

        self._show_mass_selection_dialog(urls)

    def _pretty_coin_name(self, url):
        """Человекочитаемое название монеты из URL:
        /coin/isle_of_man-1-crown-2012/ -> 'isle of man 1 crown 2012'"""
        try:
            from urllib.parse import urlparse, unquote
            path = unquote(urlparse(url).path).strip('/')
            if path.startswith('coin/'):
                path = path[5:]
            name = path.replace('-', ' ').replace('_', ' ').strip()
            return name or url
        except Exception:
            return url

    def _show_mass_selection_dialog(self, urls):
        """Показывает окно со списком найденных монет (галочки, все выбраны).
        OK — продолжить обработку выбранных, Отмена — отменить всё."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                       QListWidget, QListWidgetItem,
                                       QPushButton, QLabel)
        from PySide6.QtCore import Qt
        
        if not urls:
            self._start_mass_processing([])
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🚀 Массовое добавление — выбор монет")
        dialog.setMinimumSize(560, 620)
        layout = QVBoxLayout(dialog)
        
        title = QLabel(f"📋 Найдено монет на странице: {len(urls)}\n"
                       f"Снимите галочки с тех, которые НЕ нужно добавлять:")
        layout.addWidget(title)
        
        # === Список с галочками (все выбраны по умолчанию) ===
        list_widget = QListWidget()
        for url in urls:
            item = QListWidgetItem(self._pretty_coin_name(url))
            item.setData(Qt.UserRole, url)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            list_widget.addItem(item)
        layout.addWidget(list_widget, 1)
        
        # === Кнопки ===
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("✅ Выбрать всё")
        deselect_all_btn = QPushButton("⬜ Снять всё")
        ok_btn = QPushButton("✅ OK")
        cancel_btn = QPushButton("❌ Отмена")
        ok_btn.setDefault(True)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(deselect_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
        
        def set_all(state):
            for i in range(list_widget.count()):
                list_widget.item(i).setCheckState(state)
        select_all_btn.clicked.connect(lambda: set_all(Qt.Checked))
        deselect_all_btn.clicked.connect(lambda: set_all(Qt.Unchecked))
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        result = dialog.exec()
        
        # === Отмена ===
        if result != QDialog.Accepted:
            self.logger.info("🚫 Массовое добавление отменено пользователем")
            self.status_label.setText("🚫 Массовое добавление отменено")
            self.status_label.setStyleSheet("color: #ffc107;")
            self._mass_restore_dialogs()
            self._mass_queue = None
            return
        
        # === Собираем выбранные ===
        selected = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        self.logger.info(f"☑ Выбрано пользователем: {len(selected)} из {len(urls)}")
        
        if not selected:
            self.status_label.setText("⚠️ Ни одна монета не выбрана — добавление отменено")
            self.status_label.setStyleSheet("color: #ffc107;")
            self._mass_restore_dialogs()
            self._mass_queue = None
            return
        
        # === Продолжаем обработку только выбранных ===
        self._start_mass_processing(selected)

    def _on_mass_links_found(self, result):
        """Обработчик результата сбора ссылок"""
        # Подробное логирование результата (поможет понять, что вернул JS)
        self.logger.info(f"🚀 JS вернул результат типа: {type(result).__name__}")
        self.logger.info(f"🚀 Значение: {result}")
        
        urls = []
        if result is None:
            self.logger.warning("🚀 JS вернул None (возможно, страница не загрузилась или JS не выполнен)")
        elif isinstance(result, list):
            urls = [u for u in result if u and isinstance(u, str)]
        elif isinstance(result, dict):
            # На случай если JS всё же вернул словарь
            urls = result.get('urls', [])
            if isinstance(urls, list):
                urls = [u for u in urls if u and isinstance(u, str)]
        elif isinstance(result, str):
            # Иногда WebEngine возвращает строку
            urls = [result] if result else []
        
        if not urls:
            self.status_label.setText("⚠️ На странице не найдено ссылок на монеты. Откройте DevTools (F12 → Console) для отладки")
            self.status_label.setStyleSheet("color: #dc3545;")
            self.logger.warning("🚀 Пустой список URL — остановка")
            # Подсказка пользователю
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Массовое добавление",
                "На странице не найдено ссылок на монеты.\n\n"
                "Попробуйте:\n"
                "1. Подождать полной загрузки страницы\n"
                "2. Обновить страницу (F5) и повторить\n"
                "3. Открыть DevTools (F12 → Console) — там будет подробная информация\n\n"
                "Если проблема сохраняется — пришлите скриншот консоли браузера."
            )
            return
        
        self.logger.info(f"📋 Найдено ссылок на монеты: {len(urls)}")
        self._start_mass_processing(urls)
    def _start_mass_processing(self, urls):
        """Начинает обработку очереди URL после сбора ссылок"""
        if not urls:
            self.status_label.setText("⚠️ На странице не найдено ссылок на монеты (проверьте, что это каталог/галерея uCoin)")
            self.status_label.setStyleSheet("color: #ffc107;")
            self.logger.warning("🚀 Пустой список URL — остановка")
            return
        from collections import deque
        from PySide6.QtCore import QTimer
        
        self._mass_queue = deque(urls)
        self._mass_total = len(urls)
        self._mass_added = 0
        self._mass_errors = 0
        self.logger.info(f"📋 Найдено ссылок на монеты: {self._mass_total}")
        self.status_label.setText(
            f"🚀 Массовое добавление: найдено {self._mass_total} монет..."
        )
        self.status_label.setStyleSheet("color: #4a6fa5;")
        
        # Первая монета через 500мс (даём странице время на прогрузку)
        QTimer.singleShot(500, self._process_mass_queue)

    def _process_mass_queue(self):
        """Открывает следующую ссылку: выбирает донора, запускает штатный поток
        добавления, продлевает таймаут парсинга и ждёт флаг завершения."""
        if not getattr(self, '_mass_queue', None) or not self._mass_queue:
            self._finish_mass_processing()
            return
        url = self._mass_queue[0]
        idx = self._mass_total - len(self._mass_queue) + 1
        self.status_label.setText(f"🚀 Монета {idx}/{self._mass_total}: загрузка страницы...")
        self.status_label.setStyleSheet("color: #4a6fa5;")
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QTimer
            main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
            if not main_window or not hasattr(main_window, '_add_coin_from_ucoin'):
                self._mass_errors += 1
                self._mass_queue.popleft()
                QTimer.singleShot(300, self._process_mass_queue)
                return
            # Выбираем исходного донора
            if getattr(self, '_mass_donor_id', None):
                try:
                    main_window.select_coin_by_id(self._mass_donor_id)
                except Exception:
                    pass
            # Штатный поток: копия донора -> вкладка -> парсинг -> заполнение формы
            main_window._add_coin_from_ucoin(url)
            # Продлеваем внутренний таймаут UCOIN (страница может грузиться долго)
            QTimer.singleShot(1200, self._mass_extend_ucoin_timeout)
            # Опрашиваем флаг завершения парсинга (старт через 3 сек)
            QTimer.singleShot(3000, lambda: self._mass_poll_fill_done(url, 0))
        except Exception as e:
            self.logger.error(f"Ошибка массового добавления: {e}")
            self._mass_errors += 1
            self._mass_queue.popleft()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, self._process_mass_queue)

    def _mass_extend_ucoin_timeout(self):
        """Продлевает внутренний таймаут загрузки UCOIN до 30 секунд,
        чтобы страница успела загрузиться и данные успели распарситься"""
        try:
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    coin_tab = getattr(getattr(widget, 'detail_panel', None), 'coin_tab', None)
                    timer = getattr(coin_tab, '_ucoin_timeout_timer', None) if coin_tab else None
                    if timer is not None:
                        try:
                            if timer.isActive():
                                timer.start(30000)  # 30 секунд вместо стандартного
                                self.logger.info("⏱️ Таймаут парсинга UCOIN продлён до 30 сек")
                        except Exception:
                            pass
                    break
        except Exception as e:
            self.logger.debug(f"Не удалось продлить таймаут: {e}")

    def _mass_poll_fill_done(self, url, attempts):
        """Ждёт флаг coin_tab._ucoin_load_processed == True (парсинг завершён,
        форма заполнена). Увеличенные таймауты: до 45 сек ожидания +
        4 сек на дозапись данных в форму перед сохранением."""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break
        if not main_window:
            self._mass_errors += 1
            self._mass_queue.popleft()
            QTimer.singleShot(300, self._process_mass_queue)
            return
        coin_tab = getattr(getattr(main_window, 'detail_panel', None), 'coin_tab', None)
        processed = bool(getattr(coin_tab, '_ucoin_load_processed', False)) if coin_tab else False
        if processed:
            # Парсинг завершён — даём 4 СЕКУНДЫ на полную запись данных в форму
            self.status_label.setText(
                f"🚀 Монета {self._mass_total - len(self._mass_queue) + 1}/{self._mass_total}: сохранение..."
            )
            QTimer.singleShot(4000, lambda: self._mass_save_and_next(url))
        elif attempts >= 90:  # таймаут ~45 секунд
            self.logger.warning(f"⏱️ Таймаут парсинга: {url}")
            self._mass_errors += 1
            self._mass_queue.popleft()
            self._mass_close_extra_tabs()
            QTimer.singleShot(300, self._process_mass_queue)
        else:
            QTimer.singleShot(500, lambda: self._mass_poll_fill_done(url, attempts + 1))

    def _mass_save_and_next(self, url):
        """Сохраняет заполненную монету, ждёт завершения сохранения и переходит к следующей"""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        try:
            main_window = None
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    main_window = widget
                    break
            coin_tab = getattr(getattr(main_window, 'detail_panel', None), 'coin_tab', None)
            if main_window and coin_tab and getattr(coin_tab, 'edit_mode', False):
                old_suppress = getattr(main_window, '_suppress_messages', False)
                main_window._suppress_messages = True
                coin_tab.save_changes()
                main_window._suppress_messages = old_suppress
                self._mass_added += 1
                self.logger.info(f"✅ Монета сохранена ({self._mass_added}/{self._mass_total}): {url}")
            else:
                self.logger.warning(f"⚠️ Форма не в режиме редактирования: {url}")
                self._mass_errors += 1
        except Exception as e:
            self.logger.error(f"Ошибка сохранения: {e}")
            self._mass_errors += 1
        
        # Удаляем обработанную ссылку из очереди
        self._mass_queue.popleft()
        
        # === ЖДЁМ 4 СЕКУНДЫ перед закрытием вкладки ===
        # Это даёт время на:
        # 1. Сохранение всех данных в БД
        # 2. Сохранение изображений (если есть)
        # 3. Commit транзакции
        QTimer.singleShot(4000, lambda: self._mass_close_and_next(url))
    
    def _mass_close_and_next(self, url):
        """Закрывает вкладку и переходит к следующей монете (вызывается после задержки)"""
        from PySide6.QtCore import QTimer
        # Закрываем вкладку с монетой, освобождаем память
        self._mass_close_extra_tabs()
        # Пауза 1.5 сек перед следующей монетой
        QTimer.singleShot(1500, self._process_mass_queue)

    def _mass_close_extra_tabs(self):
        """Закрывает вкладки браузера, открытые сверх исходного количества"""
        try:
            initial = getattr(self, '_mass_initial_tabs', 1)
            while len(self.web_views) > initial:
                self.close_tab(len(self.web_views) - 1, force=True)
            # Сбрасываем прогресс-бар, чтобы не висела надпись ЗАГРУЗКА
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setValue(0)
                self.progress_bar.hide()
        except Exception as e:
            self.logger.debug(f"Не удалось закрыть лишние вкладки: {e}")

    def _on_mass_tab_loaded(self, ok, url):
        """Страница монеты загрузилась — запускаем стандартный парсинг через главное окно"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        # Отключаемся от сигнала (чтобы не было повторных вызовов)
        try:
            if self._mass_current_view:
                try:
                    self._mass_current_view.loadFinished.disconnect()
                except (RuntimeError, TypeError):
                    pass
        except Exception:
            pass

        if not ok:
            self.logger.warning(f"❌ Не загрузилась страница: {url}")
            self._mass_errors += 1
            self._mass_queue.popleft()
            QTimer.singleShot(300, self._process_mass_queue)
            return

        # Находим главное окно и вызываем стандартное добавление монеты
        main_window = None
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                main_window = widget
                break

        if not main_window or not hasattr(main_window, '_add_coin_from_ucoin'):
            self.logger.error("Главное окно или _add_coin_from_ucoin не найдены")
            self._mass_errors += 1
            self._mass_queue.popleft()
            QTimer.singleShot(300, self._process_mass_queue)
            return

        try:
            # Даём странице 500мс на прогрузку JS-данных (mintage, изображения)
            QTimer.singleShot(500, lambda u=url, mw=main_window: self._invoke_add_coin(u, mw))
        except Exception as e:
            self.logger.error(f"Ошибка вызова добавления: {e}")
            self._mass_errors += 1
            self._mass_queue.popleft()
            QTimer.singleShot(300, self._process_mass_queue)

    def _invoke_add_coin(self, url, main_window):
        """Вызывает _add_coin_from_ucoin с полным подавлением всех диалогов"""
        from PySide6.QtCore import QTimer
        try:
            # === ПОЛНОЕ ПОДАВЛЕНИЕ ВСЕХ ДИАЛОГОВ ===
            if not hasattr(main_window, '_dialogs_suppressed'):
                main_window._suppress_all_dialogs()
                main_window._dialogs_suppressed = True
            
            # Вызываем стандартный парсер uCoin
            main_window._add_coin_from_ucoin(url)
            
            # Даём время на заполнение формы (парсинг страницы)
            QTimer.singleShot(2500, lambda: self._auto_save_mass_coin(main_window))
            
            self.logger.info(f"🚀 Парсинг запущен для: {url}")
        except Exception as e:
            self.logger.error(f"Ошибка вызова добавления: {e}")
            self._mass_errors += 1
            self._mass_queue.popleft()
            QTimer.singleShot(300, self._process_mass_queue)

    def _auto_save_mass_coin(self, main_window):
        """Автоматически сохраняет монету без показа каких-либо окон"""
        from PySide6.QtCore import QTimer
        try:
            # Находим активную вкладку монеты
            coin_tab = None
            if hasattr(main_window, 'detail_panel') and hasattr(main_window.detail_panel, 'coin_tab'):
                coin_tab = main_window.detail_panel.coin_tab
            
            if not coin_tab:
                self.logger.warning("⚠️ coin_tab не найден")
                self._mass_errors += 1
                self._mass_queue.popleft()
                QTimer.singleShot(300, self._process_mass_queue)
                return
            
            # Проверяем, что монета в режиме редактирования
            if not hasattr(coin_tab, 'edit_mode') or not coin_tab.edit_mode:
                self.logger.warning("⚠️ Монета не в режиме редактирования")
                self._mass_errors += 1
                self._mass_queue.popleft()
                QTimer.singleShot(300, self._process_mass_queue)
                return
            
            # === АВТОСОХРАНЕНИЕ БЕЗ ДИАЛОГОВ ===
            # Подавляем все QMessageBox внутри save_changes
            old_show_info = None
            old_show_warning = None
            old_show_critical = None
            try:
                from PySide6.QtWidgets import QMessageBox
                old_show_info = QMessageBox.information
                old_show_warning = QMessageBox.warning
                old_show_critical = QMessageBox.critical
                QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok
                QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok
                QMessageBox.critical = lambda *args, **kwargs: QMessageBox.Ok
            except Exception:
                pass
            
            try:
                # Вызываем сохранение
                if hasattr(coin_tab, 'save_changes'):
                    coin_tab.save_changes()
                    self._mass_added += 1
                    self.logger.info(f"✅ Монета автоматически сохранена ({self._mass_added}/{self._mass_total})")
                else:
                    self.logger.warning("⚠️ Метод save_changes не найден")
                    self._mass_errors += 1
            finally:
                # Восстанавливаем QMessageBox
                try:
                    if old_show_info:
                        QMessageBox.information = old_show_info
                    if old_show_warning:
                        QMessageBox.warning = old_show_warning
                    if old_show_critical:
                        QMessageBox.critical = old_show_critical
                except Exception:
                    pass
            
        except Exception as e:
            self.logger.error(f"Ошибка автосохранения: {e}")
            self._mass_errors += 1
        
        # Удаляем обработанную ссылку из очереди
        self._mass_queue.popleft()
        
        # Закрываем фоновую вкладку
        try:
            if self._mass_current_view:
                idx = None
                for i, v in enumerate(self.web_views):
                    if v is self._mass_current_view:
                        idx = i
                        break
                if idx is not None:
                    self.close_tab(idx, force=True)
                self._mass_current_view = None
        except Exception as e:
            self.logger.debug(f"Не удалось закрыть фоновую вкладку: {e}")
        
        # Пауза перед следующей монетой
        QTimer.singleShot(800, self._process_mass_queue)

    def _finish_mass_processing(self):
        """Завершение массовой обработки — итоги + восстановление диалогов.
        Порядок: закрыть вкладки -> восстановить диалоги ->
        пауза 5 сек (последняя монета до сохраняется и изображения записываются) ->
        обновить таблицу -> пауза 2 сек -> итоговое окно."""
        self._mass_close_extra_tabs()
        # Восстанавливаем диалоги ДО показа итога
        self._mass_restore_dialogs()
        self.logger.info("⏳ Очередь пуста — жду 5 сек сохранения последней монеты и изображений...")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(5000, self._refresh_and_show_finish)

    def _refresh_and_show_finish(self):
        """Обновляет таблицу монет и через 2 сек показывает итоговое окно"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        self.logger.info("🔄 Обновляю таблицу монет перед итоговым окном...")
        for widget in QApplication.topLevelWidgets():
            if widget.__class__.__name__ == 'MainWindow':
                if hasattr(widget, 'load_coins'):
                    try:
                        widget.load_coins()
                    except Exception as e:
                        self.logger.error(f"Ошибка обновления таблицы: {e}")
                break
        # Даём таблице 2 сек на перерисовку, затем показываем итог
        QTimer.singleShot(2000, self._show_mass_finish_dialog)

    def _show_mass_finish_dialog(self):
        """Показывает итоговое окно массового добавления (таблица уже обновлена)"""
        self.logger.info(
            f"🏁 Массовое добавление завершено: "
            f"добавлено={self._mass_added}, ошибок={self._mass_errors}, всего={self._mass_total}"
        )
        msg = f"✅ Массовое добавление завершено!\n\nДобавлено монет: {self._mass_added} из {self._mass_total}"
        if self._mass_errors:
            msg += f"\n⚠️ Ошибок: {self._mass_errors}"
        self.status_label.setText(msg.replace("\n", " "))
        self.status_label.setStyleSheet("color: #28a745;")
        # Единственное итоговое окно (таблица УЖЕ обновлена и видна)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "🚀 Массовое добавление", msg)
        self._mass_queue = None
    


    def _copy_url(self, url):
        """Копирует URL в буфер обмена"""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(url)
        self.status_label.setText("📋 URL скопирован в буфер обмена")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))
    
    def _open_in_system_browser(self, url):
        """Открывает URL в системном браузере"""
        import webbrowser
        webbrowser.open(url)
        
    def acceptNavigationRequest(self, url, _type, isMainFrame):
        """Перехватывает навигацию (ЛКМ/ПКМ через iframe-трюк)"""
        url_str = url.toString()
        if url_str in ["about:blank", "", "#"]:
            return True
        if url_str.startswith('coin-collector://click'):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url_str)
            params = parse_qs(parsed.query)
            button = int(params.get('button', [0])[0])
            target_url = params.get('url', [''])[0]
            if target_url:
                if button == 2:  # Правая кнопка - фоновая вкладка
                    self.browser.add_new_tab_background(target_url)
                else:  # Левая кнопка - текущая вкладка
                    self.browser.load_in_current_tab(target_url)
                return False
        return True
        


# ============================================================================
# === ГАРАНТИЙНЫЕ МЕТОДЫ НАВИГАЦИИ ДЛЯ EmbeddedBrowser =======================
# === Самопочинка: методы определены НА ВЕРХНЕМ УРОВНЕ модуля и              ===
# === привязываются к классу, только если класс их не имеет                  ===
# === (защищает от «утонувших» в чужом теле def после ручных вставок).        ===
# === ExchangeBrowser наследует их автоматически.                            ===
# ============================================================================
def _cc_go_back(self):
    """Назад по истории"""
    if WEBENGINE_AVAILABLE:
        web_view = self.get_current_web_view()
        if web_view and web_view.history().canGoBack():
            web_view.back()


def _cc_go_forward(self):
    """Вперёд по истории"""
    if WEBENGINE_AVAILABLE:
        web_view = self.get_current_web_view()
        if web_view and web_view.history().canGoForward():
            web_view.forward()


def _cc_go_home(self):
    """Домой (about:blank)"""
    if WEBENGINE_AVAILABLE:
        web_view = self.get_current_web_view()
        if web_view:
            web_view.setUrl(QUrl("about:blank"))


def _cc_refresh(self):
    """Обновить текущую страницу"""
    if WEBENGINE_AVAILABLE:
        web_view = self.get_current_web_view()
        if web_view:
            web_view.reload()


for _cc_name, _cc_fn in (
        ('go_back', _cc_go_back),
        ('go_forward', _cc_go_forward),
        ('go_home', _cc_go_home),
        ('refresh', _cc_refresh),
):
    if not hasattr(EmbeddedBrowser, _cc_name):
        setattr(EmbeddedBrowser, _cc_name, _cc_fn)
del _cc_name, _cc_fn