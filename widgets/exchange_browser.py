# -*- coding: utf-8 -*-
"""
Браузер для вкладки закупок — ПКМ открывает ссылку в фоновой вкладке
"""
import logging
import re
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (QApplication, QMessageBox, QMenu,
                               QToolBar, QPushButton, QLineEdit)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor

from gui.widgets.embedded_browser import (EmbeddedBrowser, CustomWebView,
                                          CustomWebEnginePage, WEBENGINE_AVAILABLE)
from utils.paths import paths

# Импорт WebEngine
if WEBENGINE_AVAILABLE:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import (QWebEngineSettings,
                                         QWebEngineDownloadRequest,
                                         QWebEngineProfile)


class ExchangeWebView(CustomWebView):
    """WebView для браузера обмена.
    ПКМ по любой ячейке строки с монетой → фоновая вкладка, меню НЕ показывается.
    ПКМ в любом другом месте → стандартное контекстное меню."""

    def contextMenuEvent(self, event):
        if not getattr(self, 'browser', None):
            super().contextMenuEvent(event)
            return

        pos = event.pos()
        global_pos = event.globalPos()
        # Коррекция координат с учётом масштаба (zoomFactor=0.8)
        zoom = self.zoomFactor() or 1.0
        css_x = pos.x() / zoom
        css_y = pos.y() / zoom

        js = """
        (function() {
            function absUrl(u) {
                try { return new URL(u, window.location.href).toString(); }
                catch (e) { return u; }
            }
            function isCoinLink(url) {
                if (!url) return false;
                return url.indexOf('/coin/') !== -1;
            }
            function isEditable(el) {
                if (!el) return false;
                var tag = el.tagName ? el.tagName.toLowerCase() : '';
                return tag === 'input' || tag === 'textarea' ||
                       tag === 'select' || el.isContentEditable;
            }
            var el = document.elementFromPoint(%f, %f);
            if (!el || isEditable(el)) return '';
            var node = el;
            for (var i = 0; i < 8 && node; i++) {
                if (node.tagName === 'A' && node.getAttribute('href') &&
                    isCoinLink(node.href)) {
                    return absUrl(node.href);
                }
                if (node.querySelectorAll) {
                    var links = node.querySelectorAll('a[href*="/coin/"]');
                    if (links.length) return absUrl(links[0].href);
                }
                if (node.tagName === 'TABLE') break;
                node = node.parentElement;
            }
            return '';
        })();
        """ % (css_x, css_y)

        def js_callback(url):
            if url:
                self.browser.logger.info(
                    f"🖱️ ПКМ по монете → фоновая вкладка: {url[:80]}")
                self.browser.add_new_tab_background(url)
            else:
                menu = self.createStandardContextMenu(global_pos)
                menu.exec(global_pos)

        self.page().runJavaScript(js, 0, js_callback)


class ExchangeBrowser(EmbeddedBrowser):
    """Браузер для вкладки закупок — ПКМ открывает ссылку в фоновой вкладке"""

    def __init__(self, parent=None, profile_name="exchange_tab"):
        super().__init__(parent, profile_name)
        self.logger = logging.getLogger('CoinCollector.ExchangeBrowser')
        self._parent_tab = parent
        self._pending_downloads = {}

    def setup_profile(self):
        """Настраивает профиль браузера закупок.
        Русский язык: базовый класс ставит Accept-Language (методом или
        свойством) + интерцептор; здесь дублируем свойством на случай
        сборок PySide6 без методов."""
        super().setup_profile()
        if not self.profile:
            return
        try:
            if hasattr(self.profile, 'setHttpAcceptLanguages'):
                self.profile.setHttpAcceptLanguages(["ru-RU", "ru", "en;q=0.5"])
            else:
                self.profile.httpAcceptLanguages = ["ru-RU", "ru", "en;q=0.5"]
            self.logger.info("✅ Accept-Language: ru-RU (exchange_tab)")
        except Exception as e:
            self.logger.debug(f"Accept-Language exchange_tab: {e}")

    def set_parent_tab(self, tab):
        self._parent_tab = tab

    def get_current_web_view(self):
        if hasattr(self, 'tab_widget') and self.tab_widget:
            current_index = self.tab_widget.currentIndex()
            if current_index >= 0:
                return self.tab_widget.widget(current_index)
        return None

    def load_in_current_tab(self, url):
        current_view = self.get_current_web_view()
        if current_view:
            # === ПРИНУДИТЕЛЬНЫЙ РУССКИЙ ЯЗЫК ДЛЯ MESHOK ===
            if 'meshok.net' in url and 'lang=' not in url:
                url = url + ('&' if '?' in url else '?') + 'lang=ru'
            current_view.setUrl(QUrl(url))
            self.logger.info(f"📑 Загружено в текущей вкладке: {url[:80]}")

    def create_web_view(self):
        """ВАЖНО: создаёт ExchangeWebView (а не QWebEngineView),
        чтобы работал перехват ПКМ. Плюс подсветка текста и диагностика
        битых картинок."""
        if not WEBENGINE_AVAILABLE:
            return None
        try:
            view = ExchangeWebView(self)
            view.browser = self
            if self.profile:
                page = CustomWebEnginePage(self.profile, self, view)
            else:
                page = CustomWebEnginePage(QWebEngineProfile.defaultProfile(), self, view)
            page.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            page.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            page.settings().setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)
            page.settings().setAttribute(QWebEngineSettings.AutoLoadImages, True)
            view.setPage(page)
            try:
                view.page().setBackgroundColor(QColor('#1a1a2e'))
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
            # === ПОДСВЕТКА: повторное применение после загрузки/SPA-рендера ===
            view.loadFinished.connect(
                lambda ok, v=view: self._reapply_highlight(ok, v))
            # === ДИАГНОСТИКА БИТЫХ КАРТИНОК (CC-IMG в логе) ===
            view.loadFinished.connect(
                lambda ok, v=view: self._log_broken_images(ok, v))
            try:
                view.page().profile().downloadRequested.disconnect()
            except Exception:
                pass
            view.page().profile().downloadRequested.connect(self._on_download_requested)
            self.web_views.append(view)
            self.logger.info("✅ Exchange WebView создан (ExchangeWebView)")
            return view
        except Exception as e:
            self.logger.error(f"Ошибка создания WebView: {e}")
            return None         

    def _log_broken_images(self, ok, view):
        """После загрузки страницы считает изображения, которые НЕ загрузились
        (complete=True, naturalWidth=0), и пишет их URL в лог приложения
        через console.log (перехватывается javaScriptConsoleMessage).
        По строкам CC-IMG видно, какой хост/причина мешает загрузке."""
        if not ok:
            return
        js = """
        (function() {
            var imgs = document.images;
            var broken = [];
            for (var i = 0; i < imgs.length; i++) {
                var im = imgs[i];
                if (im.complete && im.naturalWidth === 0 && im.src) {
                    broken.push(im.src);
                }
            }
            if (broken.length) {
                console.log('CC-IMG: битых картинок=' + broken.length +
                            ' | первые: ' + broken.slice(0, 5).join(' ; '));
            } else {
                console.log('CC-IMG: все картинки загружены (всего ' +
                            imgs.length + ')');
            }
            return broken.length;
        })();
        """
        try:
            view.page().runJavaScript(js, 0, lambda res: None)
        except Exception:
            pass

    def _inject_click_handler(self, web_view):
        """Внедряет JavaScript: перехват ПКМ (фоновая вкладка) +
        ПОДАВЛЕНИЕ hover-событий и всплывающего превью uCoin.
        ИСПРАВЛЕНО: MutationObserver вешается на document.body только если
        он существует; иначе — отложенная установка на DOMContentLoaded
        (убирает 'Failed to execute observe on MutationObserver')."""
        if not web_view:
            return
        if hasattr(web_view, '_handler_injected') and web_view._handler_injected:
            return
        js_code = """
(function() {
    if (window._exchangeClickHandler) return;
    window._exchangeClickHandler = true;

    // === 1) ПОДАВЛЕНИЕ HOVER-СОБЫТИЙ И ПРЕВЬЮ uCoin ===
    (function() {
        if (window.__ccHoverKilled) return;
        window.__ccHoverKilled = true;

        function inTarget(t) {
            if (!t || !t.closest) return false;
            return t.closest('table') ||
                   t.closest('a[href*="/coin/"]') ||
                   t.closest('a[href*="/catalog/"]');
        }
        var EVTS = ['mouseover', 'mouseout', 'mouseenter', 'mouseleave',
                    'pointerover', 'pointerout', 'pointerenter',
                    'pointerleave', 'mousemove'];
        for (var i = 0; i < EVTS.length; i++) {
            document.addEventListener(EVTS[i], function(e) {
                if (inTarget(e.target)) e.stopImmediatePropagation();
            }, true);
        }

        // Страховка: прячем всплывающее превью, если оно всё же появилось
        function hidePopup() {
            var nodes = document.querySelectorAll(
                'div[id*="preview"],div[class*="preview"],' +
                'div[id*="tooltip"],div[class*="tooltip"],' +
                'div[id*="popup"],div[class*="popup"]');
            for (var j = 0; j < nodes.length; j++) {
                var st = window.getComputedStyle(nodes[j]);
                if (st.position === 'absolute' || st.position === 'fixed') {
                    nodes[j].style.display = 'none';
                }
            }
        }
        if (window.MutationObserver) {
            var tid = null;
            var mo = new MutationObserver(function() {
                if (tid) return;
                tid = setTimeout(function() { tid = null; hidePopup(); }, 50);
            });
            var moOpts = {attributes: true, childList: true, subtree: true,
                          attributeFilter: ['style', 'class']};
            // === ИСПРАВЛЕНИЕ: body может ещё не существовать ===
            if (document.body) {
                mo.observe(document.body, moOpts);
            } else {
                document.addEventListener('DOMContentLoaded', function() {
                    if (document.body) {
                        mo.observe(document.body, moOpts);
                    }
                });
            }
        }
    })();

    // === 2) ПЕРЕХВАТ ПКМ → ФОНОВАЯ ВКЛАДКА ===
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
        var tag = el.tagName ? el.tagName.toLowerCase() : '';
        if (tag === 'button') return true;
        if (tag === 'input' && (el.type === 'submit' || el.type === 'button')) return true;
        return false;
    }
    function getAbsoluteUrl(url) {
        try { return new URL(url, window.location.href).toString(); }
        catch (e) { return url; }
    }
    function cleanUrl(url) {
        return url.replace(/\\s+/g, '').trim();
    }
    function isCoinLink(url) {
        if (!url) return false;
        return url.indexOf('/coin/') !== -1 || url.indexOf('/catalog/') !== -1;
    }
    function findLinkElement(el) {
        if (!el) return null;
        if (el.tagName === 'A' && el.href) return el;
        var parent = el.parentElement;
        for (var i = 0; i < 5 && parent; i++) {
            if (parent.tagName === 'A' && parent.href) return parent;
            var links = parent.querySelectorAll('a');
            if (links.length === 1 && links[0].href) return links[0];
            parent = parent.parentElement;
        }
        var innerLinks = el.querySelectorAll('a');
        for (var i = 0; i < innerLinks.length; i++) {
            if (innerLinks[i].href) return innerLinks[i];
        }
        return null;
    }
    document.addEventListener('contextmenu', function(event) {
        var target = event.target;
        if (isInputElement(target) || isEditableElement(target) ||
            isFormElement(target) || isButtonElement(target)) {
            return true;
        }
        var link = findLinkElement(target);
        if (link && link.href && isCoinLink(link.href)) {
            event.preventDefault();
            event.stopPropagation();
            var absoluteUrl = getAbsoluteUrl(link.href);
            var cleanUrlStr = cleanUrl(absoluteUrl);
            var frame = document.createElement('iframe');
            frame.style.display = 'none';
            frame.src = 'coin-collector://click?button=2&url=' +
                        encodeURIComponent(cleanUrlStr);
            document.body.appendChild(frame);
            setTimeout(function() {
                if (frame.parentNode) frame.parentNode.removeChild(frame);
            }, 100);
            return false;
        }
        return true;
    }, true);
    console.log('✅ ExchangeBrowser: ПКМ + hover-подавление внедрены');
})();
"""
        try:
            web_view.page().runJavaScript(js_code)
            web_view._handler_injected = True
            self.logger.debug("ExchangeBrowser ПКМ + hover-подавление внедрены")
        except Exception as e:
            self.logger.debug(f"Не удалось инжектить обработчик: {e}")

    def _on_download_requested(self, download):
        try:
            url = download.url().toString()
            self.logger.info(f"📥 Запрос на скачивание: {url}")
            if 'export=csv' in url or 'swap-list' in url:
                download_dir = paths.get_obmen_dir()
                download_dir.mkdir(parents=True, exist_ok=True)
                nick = None
                deal_number = None
                if hasattr(self, '_parent_tab') and self._parent_tab:
                    nick = getattr(self._parent_tab, '_autofill_nickname', None)
                    deal_number = getattr(self._parent_tab, '_autofill_deal_number', None)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_nick = ""
                if nick:
                    safe_nick = "".join(c for c in nick if c.isalnum() or c in ' _-')
                if safe_nick and deal_number:
                    suggested_filename = f"obmen_{safe_nick}_{deal_number}.csv"
                elif safe_nick:
                    suggested_filename = f"obmen_{safe_nick}_{timestamp}.csv"
                elif deal_number:
                    suggested_filename = f"obmen_{deal_number}.csv"
                else:
                    suggested_filename = f"obmen_{timestamp}.csv"
                full_path = download_dir / suggested_filename
                self.logger.info(f"📁 Сохранение в: {full_path}")
                download.setDownloadDirectory(str(download_dir))
                download.setDownloadFileName(suggested_filename)
                download.accept()
                self.status_label.setText(f"📥 Скачивание: {suggested_filename}")

                def on_state_changed(state):
                    try:
                        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                            self.logger.info(f"✅ Файл скачан: {full_path}")
                            self.status_label.setText(f"✅ Файл сохранён: {suggested_filename}")
                            if full_path.exists():
                                if hasattr(self, '_parent_tab') and self._parent_tab:
                                    if hasattr(self._parent_tab, '_on_file_downloaded'):
                                        self._parent_tab._on_file_downloaded(
                                            str(full_path),
                                            getattr(self._parent_tab, '_autofill_nickname', None),
                                            getattr(self._parent_tab, '_autofill_deal_number', None))
                        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
                            self.status_label.setText("⚠️ Скачивание отменено")
                        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
                            self.status_label.setText("⚠️ Скачивание прервано")
                    except Exception as e:
                        self.logger.error(f"Ошибка в on_state_changed: {e}")

                download.stateChanged.connect(on_state_changed)
                QTimer.singleShot(30000, lambda: self._check_downloaded_file(
                    download_dir, suggested_filename, download))
            else:
                download.accept()
                self.logger.info(f"📥 Стандартное скачивание: {url}")
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании: {e}")
            import traceback
            traceback.print_exc()

    def _check_downloaded_file(self, download_dir, filename, download=None):
        file_path = download_dir / filename
        if file_path.exists():
            if file_path.stat().st_size > 0:
                self.logger.info(f"✅ Файл скачан (таймер): {file_path}")
                if hasattr(self, '_parent_tab') and self._parent_tab:
                    if hasattr(self._parent_tab, '_on_file_downloaded'):
                        self._parent_tab._on_file_downloaded(
                            str(file_path),
                            getattr(self._parent_tab, '_autofill_nickname', None),
                            getattr(self._parent_tab, '_autofill_deal_number', None))
                return
        if download:
            state = download.state()
            if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                if file_path.exists() and file_path.stat().st_size > 0:
                    if hasattr(self, '_parent_tab') and self._parent_tab:
                        if hasattr(self._parent_tab, '_on_file_downloaded'):
                            self._parent_tab._on_file_downloaded(
                                str(file_path),
                                getattr(self._parent_tab, '_autofill_nickname', None),
                                getattr(self._parent_tab, '_autofill_deal_number', None))
            elif state == QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
                QTimer.singleShot(5000, lambda: self._check_downloaded_file(
                    download_dir, filename, download))

    def add_new_tab_background(self, url=None):
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

    # Остальные методы (меню вкладок, тёмная тема) — без изменений
    def show_tab_context_menu(self, position):
        if not hasattr(self, 'tab_widget') or not self.tab_widget:
            return
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
        for i in range(self.tab_widget.count() - 1, -1, -1):
            if i != current_index:
                self.close_tab(i)

    def close_tabs_to_right(self, current_index):
        for i in range(self.tab_widget.count() - 1, current_index, -1):
            self.close_tab(i)

    def close_tabs_to_left(self, current_index):
        for i in range(current_index - 1, -1, -1):
            self.close_tab(i)

    def duplicate_tab(self, index):
        web_view = self.tab_widget.widget(index)
        if web_view:
            current_url = web_view.url().toString()
            if current_url and current_url != "about:blank":
                self.add_new_tab_background(current_url)
            else:
                self.add_new_tab()

    def _inject_dark_theme(self, web_view):
        try:
            web_view.page().runJavaScript(self.DARK_WEB_JS)
        except Exception as e:
            self.logger.debug(f"Ошибка инъекции тёмной темы: {e}")

    def _get_theme(self):
        w = self.parent()
        while w is not None:
            tm = getattr(w, 'theme_manager', None)
            if tm is not None:
                return tm.current_theme
            w = w.parent()
        return {}

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_dark_style)

    def _apply_dark_style(self):
        t = self._get_theme()
        if t.get('type', 'dark') != 'dark':
            return
        btn_style = (
            "QPushButton { background-color: " + t.get('button', '#16213e') +
            "; color: " + t.get('text', '#e4e4ef') +
            "; border: 1px solid " + t.get('border', '#2a2a4a') +
            "; border-radius: 6px; }"
            "QPushButton:hover { background-color: " + t.get('accent', '#6c63ff') +
            "; color: #ffffff; border-color: " + t.get('accent', '#6c63ff') + "; }"
        )
        for tb in self.findChildren(QToolBar):
            tb.setStyleSheet(
                "QToolBar { background-color: " + t.get('base', '#1a1a2e') +
                "; border: none; border-bottom: 1px solid " + t.get('border', '#2a2a4a') +
                "; padding: 2px; spacing: 3px; }"
            )
        for b in self.findChildren(QPushButton):
            b.setStyleSheet(btn_style)
        for le in self.findChildren(QLineEdit):
            le.setStyleSheet(
                "QLineEdit { background-color: " + t.get('input_bg', '#16213e') +
                "; color: " + t.get('text', '#e4e4ef') +
                "; border: 1px solid " + t.get('border', '#2a2a4a') +
                "; border-radius: 6px; padding: 3px 8px; }"
                "QLineEdit:focus { border-color: " + t.get('accent', '#6c63ff') + "; }"
            )
            
