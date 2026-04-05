"""
Мониторинг доступности веб-сайтов.
Проверяет список сайтов каждые 5 минут.
При недоступности или восстановлении — отправляет уведомление в Telegram.
Список сайтов хранится в config.json.
"""

import os
import json
import time
import logging
import asyncio
from datetime import datetime
from pathlib import Path

import httpx
import schedule
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Файлы конфигурации и состояния
CONFIG_FILE = Path("config.json")
STATE_FILE = Path("sites_state.json")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("monitor.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Таймаут для проверки сайта в секундах
CHECK_TIMEOUT = 10

# Допустимые HTTP-статусы (считаем сайт рабочим)
OK_STATUSES = {200, 201, 301, 302, 304, 403}


def load_config() -> dict:
    """
    Загружает конфигурацию из config.json.
    Возвращает словарь с настройками и списком сайтов.
    """
    if not CONFIG_FILE.exists():
        # Создаём конфигурацию по умолчанию
        default_config = {
            "check_interval_minutes": 5,
            "sites": [
                {"name": "Google", "url": "https://www.google.com"},
                {"name": "GitHub", "url": "https://github.com"},
                {"name": "Telegram", "url": "https://telegram.org"},
            ],
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        logger.info(f"Создан файл конфигурации: {CONFIG_FILE}")
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    """
    Загружает текущее состояние сайтов из файла.
    Состояние: {url: {"is_up": bool, "last_check": str, "down_since": str|None}}
    """
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    """Сохраняет текущее состояние сайтов в файл."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


async def check_site(url: str) -> dict:
    """
    Проверяет доступность сайта и измеряет время ответа.

    Возвращает словарь:
        is_up: bool         — доступен ли сайт
        response_time: float — время ответа в миллисекундах
        status_code: int    — HTTP статус код
        error: str          — описание ошибки (если есть)
    """
    start_time = time.time()

    try:
        async with httpx.AsyncClient(
            timeout=CHECK_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            elapsed = (time.time() - start_time) * 1000  # переводим в мс

            is_up = response.status_code in OK_STATUSES

            return {
                "is_up": is_up,
                "response_time": round(elapsed, 1),
                "status_code": response.status_code,
                "error": "" if is_up else f"HTTP {response.status_code}",
            }

    except httpx.TimeoutException:
        elapsed = (time.time() - start_time) * 1000
        return {
            "is_up": False,
            "response_time": round(elapsed, 1),
            "status_code": 0,
            "error": "Timeout — сайт не отвечает",
        }
    except httpx.ConnectError:
        return {
            "is_up": False,
            "response_time": 0,
            "status_code": 0,
            "error": "Ошибка подключения",
        }
    except Exception as e:
        return {
            "is_up": False,
            "response_time": 0,
            "status_code": 0,
            "error": str(e)[:100],
        }


async def send_telegram(message: str) -> None:
    """Отправляет уведомление в Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"Ошибка отправки в Telegram: {resp.text}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление: {e}")


def format_response_time(ms: float) -> str:
    """Форматирует время ответа с цветовым индикатором."""
    if ms < 500:
        speed = "🟢"
    elif ms < 1500:
        speed = "🟡"
    else:
        speed = "🔴"
    return f"{speed} {ms:.0f} мс"


async def run_checks() -> None:
    """
    Выполняет проверку всех сайтов из конфигурации.
    Сравнивает с предыдущим состоянием и отправляет уведомления при изменениях.
    """
    config = load_config()
    sites = config.get("sites", [])

    if not sites:
        logger.warning("Список сайтов пуст. Добавьте сайты в config.json")
        return

    state = load_state()
    now = datetime.now().isoformat()

    logger.info(f"Проверяем {len(sites)} сайтов...")

    # Проверяем все сайты параллельно для скорости
    tasks = [check_site(site["url"]) for site in sites]
    results = await asyncio.gather(*tasks)

    for site, result in zip(sites, results):
        name = site["name"]
        url = site["url"]
        is_up = result["is_up"]
        response_time = result["response_time"]
        error = result["error"]

        # Предыдущее состояние сайта
        prev_state = state.get(url, {"is_up": True, "down_since": None})
        was_up = prev_state.get("is_up", True)

        status_icon = "✅" if is_up else "❌"
        logger.info(
            f"{status_icon} {name}: {'UP' if is_up else 'DOWN'} "
            f"({response_time:.0f} мс)"
            f"{' | ' + error if error else ''}"
        )

        # Определяем, изменилось ли состояние
        if is_up and not was_up:
            # Сайт восстановился
            down_since = prev_state.get("down_since", "")
            downtime_str = ""

            if down_since:
                try:
                    down_dt = datetime.fromisoformat(down_since)
                    downtime_secs = (datetime.now() - down_dt).total_seconds()
                    minutes = int(downtime_secs // 60)
                    downtime_str = f"⏱️ Простой: {minutes} мин.\n"
                except Exception:
                    pass

            message = (
                f"✅ *Сайт восстановлен!*\n\n"
                f"🌐 {name}\n"
                f"🔗 {url}\n"
                f"{downtime_str}"
                f"⚡ Время ответа: {response_time:.0f} мс\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            await send_telegram(message)
            logger.info(f"Уведомление: {name} восстановлен")

        elif not is_up and was_up:
            # Сайт упал
            message = (
                f"🚨 *Сайт недоступен!*\n\n"
                f"🌐 {name}\n"
                f"🔗 {url}\n"
                f"❌ Ошибка: {error}\n"
                f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            await send_telegram(message)
            logger.warning(f"Уведомление: {name} недоступен ({error})")

        # Обновляем состояние
        state[url] = {
            "name": name,
            "is_up": is_up,
            "response_time": response_time,
            "status_code": result["status_code"],
            "last_check": now,
            "error": error,
            "down_since": None if is_up else (prev_state.get("down_since") or now),
        }

    # Сохраняем обновлённое состояние
    save_state(state)


def show_status() -> None:
    """Выводит текущий статус всех сайтов в консоль."""
    state = load_state()

    if not state:
        print("Нет данных о проверках. Запустите мониторинг.")
        return

    print("\n" + "=" * 60)
    print(f"{'Сайт':<20} {'Статус':<10} {'Время':<12} {'Последняя проверка'}")
    print("=" * 60)

    for url, info in state.items():
        name = info.get("name", url)[:20]
        is_up = info.get("is_up", False)
        rt = info.get("response_time", 0)
        last = info.get("last_check", "")

        status = "✅ UP" if is_up else "❌ DOWN"
        rt_str = f"{rt:.0f} мс" if rt > 0 else "—"

        if last:
            dt = datetime.fromisoformat(last)
            last_str = dt.strftime("%d.%m %H:%M")
        else:
            last_str = "—"

        print(f"{name:<20} {status:<10} {rt_str:<12} {last_str}")

    print("=" * 60 + "\n")


def main() -> None:
    """Запускает мониторинг с интервалом из config.json."""
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        raise ValueError("Заполните TELEGRAM_TOKEN и TELEGRAM_CHAT_ID в .env")

    config = load_config()
    interval = config.get("check_interval_minutes", 5)
    sites = config.get("sites", [])

    print(f"🔍 Мониторинг сайтов запущен")
    print(f"📋 Сайтов в списке: {len(sites)}")
    for site in sites:
        print(f"   • {site['name']}: {site['url']}")
    print(f"⏱️  Интервал проверки: {interval} мин.\n")

    # Первая проверка сразу при запуске
    asyncio.run(run_checks())
    show_status()

    # Планируем повторные проверки
    schedule.every(interval).minutes.do(lambda: asyncio.run(run_checks()))

    while True:
        schedule.run_pending()
        time.sleep(30)  # проверяем расписание каждые 30 секунд


if __name__ == "__main__":
    main()
