# gui/widgets/plotly_loader.py

import os
from pathlib import Path


class PlotlyLoader:
    """Класс для загрузки Plotly (только локально)"""
    
    @staticmethod
    def get_plotly_js():
        """Возвращает JavaScript код Plotly из локального файла"""
        # Определяем путь к файлу plotly.min.js относительно этого файла
        current_dir = Path(__file__).parent
        plotly_path = current_dir / "plotly" / "plotly.min.js"
        
        # Проверяем существование файла
        if not plotly_path.exists():
            print(f"❌ Файл не найден: {plotly_path}")
            print("   Скачайте plotly.min.js с https://cdn.plot.ly/plotly-3.4.0.min.js")
            return None
        
        try:
            with open(plotly_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"✅ Файл загружен: {plotly_path} ({len(content)} байт)")
                return content
        except Exception as e:
            print(f"❌ Ошибка чтения Plotly: {e}")
            return None
    
    @staticmethod
    def write_fig(fig, file_path):
        """Сохраняет график в HTML (только локально)"""
        plotly_js = PlotlyLoader.get_plotly_js()
        
        if plotly_js is None:
            # Если файл не найден, показываем сообщение об ошибке
            error_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
        }
        .error {
            text-align: center;
            padding: 30px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h2 { color: #dc3545; }
        p { color: #666; }
    </style>
</head>
<body>
    <div class="error">
        <h2>❌ Ошибка загрузки Plotly</h2>
        <p>Не найден файл plotly.min.js</p>
        <p>Путь: gui/widgets/plotly/plotly.min.js</p>
        <p>Скачайте его с <a href="https://cdn.plot.ly/plotly-3.4.0.min.js">https://cdn.plot.ly/plotly-3.4.0.min.js</a></p>
    </div>
</body>
</html>"""
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(error_html)
            print(f"❌ Создан файл с ошибкой: {file_path}")
            return False
        
        try:
            fig_json = fig.to_json()
            
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: white;
        }}
        .plotly-graph-div {{
            width: 100%;
            height: 100%;
            min-height: 400px;
        }}
    </style>
    <script>
        {plotly_js}
    </script>
</head>
<body>
    <div id="plotly-div" class="plotly-graph-div"></div>
    <script>
        var data = {fig_json};
        Plotly.newPlot('plotly-div', data.data, data.layout, {{responsive: true}});
    </script>
</body>
</html>"""
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"✅ График сохранён: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении графика: {e}")
            return False