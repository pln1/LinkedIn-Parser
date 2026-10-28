# LinkedIn Two-Stage Job Scraper (Django + PostgreSQL)

Масштабируемое приложение для сбора вакансий и данных о компаниях с LinkedIn через внутренние HTTP-эндпоинты без использования Selenium.

## 1. Подготовка окружения и базы данных PostgreSQL

1. Создайте виртуальное окружение и установите зависимости:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Для Linux/macOS (или venv\Scripts\activate для Windows)
   pip install -r requirements.txt