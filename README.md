# 🔍 Site Monitor — Мониторинг доступности сайтов

## Описание

Скрипт проверяет список веб-сайтов каждые 5 минут.
При падении сайта или его восстановлении — отправляет уведомление в Telegram.
Показывает время ответа для каждого сайта. Список сайтов настраивается в `config.json`.

## Технологии

- **Python 3.11+**
- `httpx` — async HTTP-запросы с таймаутами
- `asyncio` — параллельные проверки всех сайтов
- `schedule` — планировщик проверок
- `python-dotenv` — конфигурация

## Установка

```bash
cd site_monitor
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка

1. Заполните `.env`:

```env
TELEGRAM_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=123456789
```

2. Отредактируйте `config.json`:

```json
{
  "check_interval_minutes": 5,
  "sites": [
    {"name": "Мой сайт", "url": "https://mysite.com"},
    {"name": "API сервер", "url": "https://api.mysite.com/health"},
    {"name": "Админка", "url": "https://admin.mysite.com"}
  ]
}
```

## Запуск

```bash
python monitor.py
```

## Примеры использования

Консольный вывод:
```
🔍 Мониторинг сайтов запущен
📋 Сайтов в списке: 3
   • Google: https://www.google.com
   • GitHub: https://github.com
   • Telegram: https://telegram.org
⏱️  Интервал проверки: 5 мин.

============================================================
Сайт                 Статус     Время        Последняя проверка
============================================================
Google               ✅ UP      145 мс       04.04 15:30
GitHub               ✅ UP      312 мс       04.04 15:30
Telegram             ✅ UP      198 мс       04.04 15:30
============================================================
```

Уведомления в Telegram:

```
🚨 Сайт недоступен!

🌐 Мой сайт
🔗 https://mysite.com
❌ Ошибка: Timeout — сайт не отвечает
🕐 04.04.2026 15:35

✅ Сайт восстановлен!

🌐 Мой сайт
🔗 https://mysite.com
⏱️ Простой: 12 мин.
⚡ Время ответа: 187 мс
🕐 04.04.2026 15:47
```

> **Скриншот:** `[screenshot placeholder]`
