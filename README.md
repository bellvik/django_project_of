ЕкбТранспорт+ – Планировщик поездок по Екатеринбургу
Интеллектуальный сервис для построения маршрутов по Екатеринбургу с использованием общественного транспорта, автомобиля, велосипеда и пеших прогулок. Интегрируется с 2GIS Public Transport API и TomTom Routing API для получения актуальных данных о маршрутах и пробках. Включает административный дашборд аналитики для отслеживания использования сервиса.

Демо-версия: (https://django-project-of.onrender.com/) 

Технологии
Backend: Python 3.10, Django 5.2

База данных: PostgreSQL

Внешние API: 2GIS Public Transport API, TomTom Routing API, TomTom Search API

Аналитика и визуализация: Pandas, Matplotlib, NumPy

Frontend: Bootstrap 5, JavaScript (с использованием 2GIS Maps API)

Кэширование: Встроенное кэширование Django + собственная модель кэша маршрутов

Веб-карты: 2GIS Maps API (DGis)

Скриншоты
Главная страница с поиском маршрутов
https://github.com/bellvik/django\_project\_of/blob/main/home\_page1.png

https://github.com/bellvik/django\_project\_of/blob/main/home\_page2.png
Интерфейс поиска маршрутов с фильтрами по типам транспорта

Карта с построенным маршрутом и деталями по нему
https://github.com/bellvik/django\_project\_of/blob/main/map.png

https://github.com/bellvik/django\_project\_of/blob/main/details.png
Интерактивная карта с отображением маршрута 

Дашборд аналитики
https://github.com/bellvik/django\_project\_of/blob/main/dashboard.png
Панель аналитики с графиками и статистикой использования сервиса

Как запустить проект локально

1. Клонируйте репозиторий
   git clone https://github.com/bellvik/django_project_of.git
   cd transport_planner
2. Создайте и активируйте виртуальное окружение

python -m venv venv

Для Linux/Mac:

source venv/bin/activate

Для Windows:

venv\\Scripts\\activate
3. Установите зависимости
pip install -r requirements.txt
4. Настройте переменные окружения
Создайте файл .env в корне проекта:

TOMTOM\_API\_KEY=ваш\_ключ\_tomtom
TWOGIS\_PUBLIC\_TRANSPORT\_API\_KEY=ваш\_ключ\_2gis

SECRET\_KEY=ваш\_секретный\_ключ
DEBUG=True
Для получения API ключей:

TomTom Developer Portal

2GIS Developer Portal

5. Примените миграции базы данных
   python manage.py migrate
6. Создайте суперпользователя для доступа к админке
   python manage.py createsuperuser
7. Соберите статические файлы
   python manage.py collectstatic --noinput
8. Запустите сервер разработки
   python manage.py runserver
9. Откройте проект в браузере
   Перейдите по адресу: http://127.0.0.1:8000

Админ-панель доступна по адресу: http://127.0.0.1:8000/admin

Дашборд аналитики: http://127.0.0.1:8000/admin/analytics/

Очистить кеш: http://127.0.0.1:8000/admin/clear-cache/


