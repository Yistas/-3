# ===== gui/widgets/exchange_tab/balance_chart_tab.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Вкладка "График баланса" для визуализации накопленного баланса по ID
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
    QFrame, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QColor

# Импорт для WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

import plotly.graph_objects as go

from database.models import Sale
from gui.widgets.plotly_loader import PlotlyLoader


class BalanceChartTab(QWidget):
    """Вкладка "График баланса" для визуализации накопленного баланса по ID"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.BalanceChartTab')
        
        # Кэш графика
        self._cached_html = None
        self._last_modified = None
        self._cache_key = None
        
        # Текущий HTML файл
        self.current_html_file = None
        
        self.init_ui()
        QTimer.singleShot(100, self.load_chart)

    def _get_theme(self):
        """Возвращает словарь текущей темы (поднимаясь по родителям)"""
        w = self.parent()
        while w is not None:
            tm = getattr(w, 'theme_manager', None)
            if tm is not None:
                return tm.current_theme
            w = w.parent()
        return {}

    def _is_dark(self):
        """Возвращает True, если текущая тема тёмная"""
        return self._get_theme().get('type', 'dark') == 'dark'
    
    def init_ui(self):
        """Инициализация интерфейса"""
        t = self._get_theme()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)

        # Заголовок
        title = QLabel("📈 График баланса")
        title.setStyleSheet(f"""
            font-weight: bold;
            font-size: 16px;
            padding: 8px;
            background-color: {t.get('accent', '#6c63ff')};
            color: #ffffff;
            border-radius: 6px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Панель управления
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)

        # График
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(450)
            self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.web_view.page().setBackgroundColor(Qt.transparent)
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            layout.addWidget(self.web_view)
            layout.setStretchFactor(self.web_view, 1)
        else:
            warning_label = QLabel(
                "⚠️ PySide6-WebEngine не установлен.\n"
                "Графики Plotly не будут отображаться.\n"
                "Установите: pip install PySide6-WebEngine"
            )
            warning_label.setAlignment(Qt.AlignCenter)
            warning_label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(warning_label)

        # Статус бар
        self.status_bar = QFrame()
        self.status_bar.setFrameShape(QFrame.StyledPanel)
        self.status_bar.setFixedHeight(30)
        self.status_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('base', '#1a1a2e')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 4px;
            }}
        """)
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(5, 2, 5, 2)
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet(f"color: {t.get('tab_text', '#8888aa')};")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {t.get('tab_text', '#8888aa')};")
        status_layout.addWidget(self.stats_label)
        self.status_bar.setLayout(status_layout)
        layout.addWidget(self.status_bar)


    def _create_control_panel(self):
        """Создает панель управления"""
        t = self._get_theme()
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('base', '#1a1a2e')};
                border: 1px solid {t.get('border', '#2a2a4a')};
                border-radius: 6px;
                padding: 5px;
            }}
        """)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 5, 8, 5)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_chart)
        self.refresh_btn.setMinimumHeight(30)
        main_layout.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("💾 Экспорт")
        self.export_btn.clicked.connect(self.save_chart)
        self.export_btn.setMinimumHeight(30)
        main_layout.addWidget(self.export_btn)

        main_layout.addStretch()
        panel.setLayout(main_layout)
        return panel

    def _get_cache_key(self):
        """Возвращает ключ кэша на основе последней записи в таблице"""
        try:
            # Получаем последнюю запись по ID
            last_sale = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).first()
            if last_sale:
                timestamp = None
                if last_sale.updated_at:
                    timestamp = last_sale.updated_at.isoformat()
                elif last_sale.created_at:
                    timestamp = last_sale.created_at.isoformat()
                else:
                    timestamp = datetime.now().isoformat()
                
                return f"{last_sale.id}_{timestamp}"
            return None
        except Exception as e:
            self.logger.error(f"Ошибка получения ключа кэша: {e}")
            return None
    
    def load_chart(self):
        """Загружает график баланса с использованием кэша"""
        # Проверяем кэш
        cache_key = self._get_cache_key()
        
        if cache_key and cache_key == self._cache_key and self._cached_html:
            # Используем кэшированный график
            self._show_cached_html()
            self.logger.info("✅ График загружен из кэша")
            return
        
        # Загружаем данные и строим график
        self._build_chart()
    
    def refresh_chart(self):
        """Принудительно обновляет график"""
        self.logger.info("🔄 Принудительное обновление графика")
        self._cache_key = None
        self._cached_html = None
        self._build_chart()
        self.status_label.setText("✅ График обновлён")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
    
    def _build_chart(self):
        """Строит график баланса с ID по оси X, отображением года на пунктирных линиях"""
        try:
            self.status_label.setText("⏳ Загрузка данных...")
            QApplication.processEvents()
            
            # Получаем все записи, отсортированные по ID (по возрастанию)
            sales = self.db_manager.session.query(Sale).order_by(Sale.id.asc()).all()
            
            if not sales:
                self._show_empty_chart("Нет данных для отображения")
                self.status_label.setText("📭 Нет данных")
                return
            
            # Собираем данные для графика
            ids = []
            balances = []
            years = []
            year_change_points = []  # Точки смены года
            
            last_year = None
            for sale in sales:
                ids.append(sale.id)
                balances.append(sale.balance if sale.balance is not None else 0)
                current_year = sale.year if sale.year is not None else None
                years.append(current_year)
                
                # Отслеживаем точки смены года для пунктирных линий
                if current_year != last_year and last_year is not None:
                    year_change_points.append({
                        'x': sale.id - 0.5,
                        'year': current_year
                    })
                last_year = current_year
            
            if not ids:
                self._show_empty_chart("Нет данных для отображения")
                self.status_label.setText("📭 Нет данных")
                return
            
            # Строим график
            fig = go.Figure()
            
            # Основная линия баланса
            fig.add_trace(go.Scatter(
                x=ids,
                y=balances,
                mode='lines+markers',
                name='Баланс',
                showlegend=False,  # Убираем легенду
                line=dict(color='#4a6fa5', width=2.5),
                marker=dict(size=6, color='#4a6fa5', line=dict(color='white', width=1)),
                hovertemplate='<b>ID: %{x}</b><br>' +
                              'Год: %{customdata[0]}<br>' +
                              'Баланс: %{y:,.2f} ₽<extra></extra>',
                customdata=list(zip(years))
            ))
            
            # === ПУНКТИРНЫЕ ЛИНИИ ДЛЯ РАЗДЕЛЕНИЯ ПО ГОДАМ ===
            # Собираем уникальные года и их позиции (первое появление года)
            year_positions = {}
            for i, sale in enumerate(sales):
                year = sale.year
                if year and year not in year_positions:
                    year_positions[year] = sale.id
            
            # Добавляем вертикальные пунктирные линии на границах годов
            for year, x_pos in year_positions.items():
                fig.add_vline(
                    x=x_pos,
                    line_dash="dash",
                    line_color="#4a6fa5",  # Синий цвет, пожирнее
                    line_width=2.5,
                    opacity=0.7,
                    annotation_text=str(year),
                    annotation_position="top",
                    annotation_font_size=14,
                    annotation_font_color="#4a6fa5",
                    annotation_font_family="Arial, sans-serif",
                    annotation_font_weight="bold"
                )
            
            # Настройка оформления - УБИРАЕМ ОТОБРАЖЕНИЕ ID С ОСИ X
            fig.update_layout(
                title=dict(
                    text=f'📈 Баланс<br><sup>Финальный баланс: {balances[-1]:,.2f} ₽</sup>',
                    x=0.5,
                    font=dict(size=14)
                ),
                xaxis=dict(
                    title='',  # Убираем заголовок оси X
                    tickmode='array',
                    tickvals=[],  # Убираем все метки с оси X
                    showticklabels=False,  # Скрываем подписи
                    showgrid=False,  # Убираем сетку
                    zeroline=False,
                    showline=True,
                    linecolor='lightgray'
                ),
                yaxis=dict(
                    title='Баланс (₽)',
                    tickformat=',.0f',
                    gridcolor='lightgray',
                    gridwidth=0.5
                ),
                hovermode='x unified',
                template='plotly_white',
                height=450,
                margin=dict(l=60, r=60, t=80, b=40),  # Уменьшили bottom margin
                showlegend=False  # Убираем легенду полностью
            )
            
            # Сохраняем в кэш
            self._cached_html = self._fig_to_html(fig)
            self._cache_key = self._get_cache_key()
            self._last_modified = datetime.now()
            
            # Отображаем
            self._show_fig(fig)
            
            self.status_label.setText(f"✅ График построен. Всего точек: {len(ids)}")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.logger.error(f"Ошибка при построении графика: {e}")
            import traceback
            traceback.print_exc()
            self._show_empty_chart(f"Ошибка: {str(e)[:50]}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def _fig_to_html(self, fig):
        """Преобразует фигуру Plotly в HTML строку"""
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                PlotlyLoader.write_fig(fig, f.name)
                with open(f.name, 'r', encoding='utf-8') as html_f:
                    html_content = html_f.read()
                try:
                    os.unlink(f.name)
                except:
                    pass
                return html_content
        except Exception as e:
            self.logger.error(f"Ошибка преобразования в HTML: {e}")
            return None
    
    def _show_fig(self, fig):
        """Отображает график в WebView (с поддержкой тёмной темы)"""
        if self._is_dark():
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='#1a1a2e',
                plot_bgcolor='#16213e',
                font=dict(color='#e4e4ef'),
            )
            fig.update_xaxes(gridcolor='#2a2a4a', linecolor='#3a3a5a')
            fig.update_yaxes(gridcolor='#2a2a4a', linecolor='#3a3a5a')

        for file in getattr(self, '_temp_html_files', []):
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass
        if hasattr(self, '_temp_html_files'):
            self._temp_html_files.clear()

        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except:
                pass

        bg_css_color = '#1a1a2e' if self._is_dark() else '#ffffff'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            PlotlyLoader.write_fig(fig, f.name)
            self.current_html_file = f.name

        with open(self.current_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        css_to_add = f"""
<style>
html, body {{ margin: 0; padding: 0; overflow: hidden !important; height: 100%; width: 100%; background-color: {bg_css_color}; }}
.plotly-graph-div {{ height: 100%; width: 100%; position: absolute; top: 0; left: 0; }}
.main-svg {{ height: 100% !important; width: 100% !important; }}
</style>
"""
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', css_to_add + '</head>')
        else:
            html_content = css_to_add + html_content

        with open(self.current_html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.web_view.setUrl(QUrl.fromLocalFile(self.current_html_file))

    def _show_cached_html(self):
        """Отображает кэшированный HTML"""
        if not self._cached_html:
            return
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(self._cached_html)
            self.current_html_file = f.name
        
        self.web_view.setUrl(QUrl.fromLocalFile(self.current_html_file))
    
    def _show_empty_chart(self, message):
        """Показывает пустой график с сообщением"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=14, color="#666")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            template='plotly_white',
            height=450
        )
        self._show_fig(fig)
    
    def export_chart(self):
        """Экспортирует график в PNG"""
        if not hasattr(self, '_cached_html') or not self._cached_html:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите график")
            return
        
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить график",
            f"balance_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG files (*.png)"
        )
        
        if file_path:
            try:
                import plotly.graph_objects as go
                fig = go.Figure()
                
                sales = self.db_manager.session.query(Sale).order_by(Sale.id.asc()).all()
                ids = []
                balances = []
                
                for sale in sales:
                    ids.append(sale.id)
                    balances.append(sale.balance if sale.balance is not None else 0)
                
                if ids:
                    fig.add_trace(go.Scatter(
                        x=ids,
                        y=balances,
                        mode='lines+markers',
                        name='Баланс',
                        line=dict(color='#4a6fa5', width=3),
                        marker=dict(size=10)
                    ))
                    fig.update_layout(
                        title='Накопленный баланс по ID',
                        xaxis=dict(title='ID'),
                        yaxis=dict(title='Баланс (₽)'),
                        template='plotly_white'
                    )
                    fig.write_image(file_path, width=1200, height=800, scale=2)
                    QMessageBox.information(self, "Успех", f"График сохранён:\n{file_path}")
                else:
                    QMessageBox.warning(self, "Предупреждение", "Нет данных для экспорта")
                    
            except Exception as e:
                self.logger.error(f"Ошибка экспорта: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить график:\n{e}")
    
    def closeEvent(self, event):
        """Обработчик закрытия - удаляем временные файлы"""
        if self.current_html_file and os.path.exists(self.current_html_file):
            try:
                os.unlink(self.current_html_file)
            except:
                pass
        super().closeEvent(event)
        
    def save_chart(self):
        """Сохраняет текущий график баланса в файл (HTML)"""
        # Если графика ещё нет — пытаемся построить
        if not getattr(self, 'current_html_file', None) or not os.path.exists(self.current_html_file):
            try:
                self._build_chart()
            except Exception as e:
                self.logger.error(f"Ошибка построения графика: {e}")

        src = getattr(self, 'current_html_file', None)
        if not src or not os.path.exists(src):
            QMessageBox.warning(self, "Предупреждение", "Нет графика для сохранения")
            return

        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить график баланса",
            "balance_chart.html",
            "HTML files (*.html)"
        )
        if not file_path:
            return

        try:
            import shutil
            if not file_path.lower().endswith('.html'):
                file_path += '.html'
            shutil.copyfile(src, file_path)
            QMessageBox.information(self, "Успех", f"График сохранён:\n{file_path}")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения графика: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить график:\n{e}")