import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
)
from dotenv import load_dotenv

# =========================
# Конфиг и хранилища
# =========================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@cherepkova_event")
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "").lstrip("@")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")  # provider token от @BotFather (/setpayment)
PRICE_RUB = int(os.getenv("PRICE_RUB", "990"))

if not BOT_TOKEN:
    raise SystemExit("Не задан BOT_TOKEN")

ASSETS_FILE = Path("assets.json")     # ссылки на материалы
UNLOCKED_FILE = Path("unlocked.json") # кто оплатил

ASSETS: Dict[str, Any] = {}
UNLOCKED_CHATS: set[int] = set()      # оплаченные чаты
ONLY_MODE_CHATS: set[int] = set()     # чаты, пришедшие по only:<key>

def load_assets():
    global ASSETS
    if ASSETS_FILE.exists():
        try:
            ASSETS = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            ASSETS = {}
    else:
        ASSETS = {}

def save_assets():
    ASSETS_FILE.write_text(json.dumps(ASSETS, ensure_ascii=False, indent=2), encoding="utf-8")

def load_unlocked():
    global UNLOCKED_CHATS
    if UNLOCKED_FILE.exists():
        try:
            UNLOCKED_CHATS = set(json.loads(UNLOCKED_FILE.read_text(encoding="utf-8")))
        except Exception:
            UNLOCKED_CHATS = set()
    else:
        UNLOCKED_CHATS = set()

def save_unlocked():
    UNLOCKED_FILE.write_text(json.dumps(list(UNLOCKED_CHATS)), encoding="utf-8")

# =========================
# Материалы и клавиатуры
# =========================
TITLES = {
    "venues":           "Загородные площадки без аренды (Екатеринбург)",
    "hidden_costs":     "Скрытые расходы свадьбы",
    "vs_diy":           "Свадьба «под ключ» vs самостоятельная подготовка",
    "checklist":        "Бесплатный чек-лист: «Как подготовить свадьбу и ничего не забыть»",
    "budget_calc":      "Как рассчитать свадебный бюджет",
    "venue_questions":  "Какие вопросы задать площадке перед бронированием?"
}

def get_url(key: str) -> Optional[str]:
    data = ASSETS.get(key)
    if isinstance(data, dict):
        return data.get("url")
    if isinstance(data, str):
        return data
    return None

def link_kb_single(key: str) -> InlineKeyboardMarkup:
    url = get_url(key)
    if url:
        btn = InlineKeyboardButton(text=f"Открыть: {TITLES.get(key, key)}", url=url)
    else:
        fallback = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me"
        btn = InlineKeyboardButton(text="Ссылка не настроена", url=fallback)
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])

def link_kb_all() -> InlineKeyboardMarkup:
    rows = []
    def row(k, label):
        u = get_url(k)
        if u:
            rows.append([InlineKeyboardButton(text=label, url=u)])

    row("venues",          "🏡 Площадки без аренды")
    row("hidden_costs",    "💸 Скрытые расходы")
    row("vs_diy",          "⚖️ Под ключ vs DIY")
    row("checklist",       "🧾 Чек-лист")
    row("budget_calc",     "🧮 Бюджет свадьбы")
    row("venue_questions", "❓ Вопросы площадке")

    if not rows:
        fallback = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me"
        rows = [[InlineKeyboardButton(text="Ссылки не настроены", url=fallback)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def paywall_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔓 Открыть доступ ко всем материалам — {PRICE_RUB} ₽",
            callback_data="buy_all"
        )]
    ])

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏡 Площадки без аренды"), KeyboardButton(text="💸 Скрытые расходы")],
        [KeyboardButton(text="⚖️ Под ключ vs DIY"),    KeyboardButton(text="🧮 Бюджет свадьбы")],
        [KeyboardButton(text="🧾 Чек-лист"),           KeyboardButton(text="❓ Вопросы площадке")],
        [KeyboardButton(text="ℹ️ О нас")]
    ],
    resize_keyboard=True
)

# =========================
# Бот и диспетчер
# =========================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# =========================
# Старт + deeplink логика
# =========================
@dp.message(CommandStart())
async def start(message: types.Message):
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else None

    # Жёсткий режим: ?start=only:<key> — показать только один материал + paywall
    if payload and payload.startswith("only:"):
        key = payload.split(":", 1)[1]
        if key in TITLES and get_url(key):
            ONLY_MODE_CHATS.add(message.chat.id)
            await message.answer(TITLES[key], reply_markup=link_kb_single(key))
            await message.answer("Хочешь доступ ко всем материалам?", reply_markup=paywall_kb())
            return
        else:
            await message.answer("Ссылка пока не настроена. Сообщите администратору.")
            return

    # Если чат уже разблокирован — полное меню
    if message.chat.id in UNLOCKED_CHATS:
        await message.answer("Полный доступ активен. Выберите раздел:", reply_markup=MAIN_KB)
        await message.answer("Быстрые ссылки:", reply_markup=link_kb_all())
        return

    # Обычный deeplink ?start=<key> — один материал + предложение оплатить
    if payload in TITLES and get_url(payload):
        await message.answer(TITLES[payload], reply_markup=link_kb_single(payload))
        await message.answer("Хочешь доступ ко всем материалам?", reply_markup=paywall_kb())
        return

    # Базовый старт
    await message.answer("Привет! Я отправлю нужные ссылки. Выберите:", reply_markup=MAIN_KB)
    await message.answer("Быстрые ссылки:", reply_markup=link_kb_all())
    await message.answer("Можно открыть доступ ко всем материалам:", reply_markup=paywall_kb())

# =========================
# Кнопки меню (с блокировкой в only-режиме)
# =========================
def locked(m: types.Message) -> bool:
    return (m.chat.id in ONLY_MODE_CHATS) and (m.chat.id not in UNLOCKED_CHATS)

@dp.message(F.text == "🏡 Площадки без аренды")
async def kb_venues(m: types.Message):
    if locked(m):
        await m.answer("Этот раздел доступен после оплаты полного доступа.", reply_markup=paywall_kb())
        return
    await m.answer(TITLES["venues"], reply_markup=link_kb_single("venues"))

@dp.message(F.text == "💸 Скрытые расходы")
async def kb_hidden(m: types.Message):
    if locked(m):
        await m.answer("Этот раздел доступен после оплаты полного доступа.", reply_markup=paywall_kb())
        return
    await m.answer(TITLES["hidden_costs"], reply_markup=link_kb_single("hidden_costs"))

@dp.message(F.text == "⚖️ Под ключ vs DIY")
async def kb_vs(m: types.Message):
    if locked(m):
        await m.answer("Этот раздел доступен после оплаты полного доступа.", reply_markup=paywall_kb())
        return
    await m.answer(TITLES["vs_diy"], reply_markup=link_kb_single("vs_diy"))

@dp.message(F.text == "🧮 Бюджет свадьбы")
async def kb_budget(m: types.Message):
    if locked(m):
        await m.answer("Этот раздел доступен после оплаты полного доступа.", reply_markup=paywall_kb())
        return
    await m.answer(TITLES["budget_calc"], reply_markup=link_kb_single("budget_calc"))

@dp.message(F.text == "🧾 Чек-лист")
async def kb_checklist(m: types.Message):
    if locked(m):
        await m.answer("Этот раздел доступен после оплаты полного доступа.", reply_markup=paywall_kb())
        return
    await m.answer(TITLES["checklist"], reply_markup=link_kb_single("checklist"))

@dp.message(F.text == "❓ Вопросы площадке")
async def kb_questions(m: types.Message):
    if locked(m):
        await m.answer("Этот раздел доступен после оплаты полного доступа.", reply_markup=paywall_kb())
        return
    await m.answer(TITLES["venue_questions"], reply_markup=link_kb_single("venue_questions"))

@dp.message(F.text == "ℹ️ О нас")
async def kb_about(m: types.Message):
    await m.answer("Агентство Cherepkova Event 💍\nОрганизация свадеб под ключ.\nhttps://cherepkovaevent.ru")

# =========================
# Команда для оперативной смены ссылок
# =========================
@dp.message(Command("seturl"))
async def seturl(message: types.Message):
    # /seturl budget_calc https://new-link
    try:
        _, key, url = (message.text or "").split(maxsplit=2)
    except ValueError:
        await message.reply("Формат: /seturl <venues|hidden_costs|vs_diy|checklist|budget_calc|venue_questions> <URL>")
        return

    if key not in TITLES:
        await message.reply("Неверный ключ. Используйте один из: " + ", ".join(TITLES.keys()))
        return

    ASSETS.setdefault(key, {})
    if isinstance(ASSETS[key], dict):
        ASSETS[key]["url"] = url
    else:
        ASSETS[key] = {"url": url}
    save_assets()
    await message.reply(f"URL для {key} сохранён ✅")

# =========================
# Пост в канал с deeplink-кнопками
# =========================
@dp.message(Command("post"))
async def post(message: types.Message):
    username = BOT_USERNAME or (await bot.get_me()).username
    text = (
        "Подборка материалов от Cherepkova Event 👇\n"
        "• 🏡 Площадки без аренды\n"
        "• 💸 Скрытые расходы\n"
        "• 🧾 Чек-лист подготовки\n"
        "• 🧮 Бюджет свадьбы\n"
        "• ❓ Вопросы площадке\n"
        "• ⚖️ Под ключ vs DIY"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏡 Площадки",          url=f"https://t.me/{username}?start=venues")],
            [InlineKeyboardButton(text="💸 Скрытые расходы",   url=f"https://t.me/{username}?start=hidden_costs")],
            [InlineKeyboardButton(text="🧾 Чек-лист",          url=f"https://t.me/{username}?start=checklist")],
            [InlineKeyboardButton(text="🧮 Бюджет свадьбы",    url=f"https://t.me/{username}?start=budget_calc")],
            [InlineKeyboardButton(text="❓ Вопросы площадке",  url=f"https://t.me/{username}?start=venue_questions")],
            [InlineKeyboardButton(text="⚖️ Под ключ vs DIY",  url=f"https://t.me/{username}?start=vs_diy")]
        ]
    )
    await bot.send_message(CHANNEL, text, reply_markup=kb)
    await message.reply("Пост отправлен в канал ✅")

# =========================
# Пост с прямыми ссылками (без бота)
# =========================
@dp.message(Command("post_direct"))
async def post_direct(message: types.Message):
    def btn(label, key):
        u = get_url(key)
        return [InlineKeyboardButton(text=label, url=u)] if u else None

    rows = []
    for label, key in [
        ("🏡 Площадки без аренды", "venues"),
        ("💸 Скрытые расходы",     "hidden_costs"),
        ("🧾 Чек-лист",            "checklist"),
        ("🧮 Бюджет свадьбы",      "budget_calc"),
        ("❓ Вопросы площадке",    "venue_questions"),
        ("⚖️ Под ключ vs DIY",     "vs_diy"),
    ]:
        r = btn(label, key)
        if r: rows.append(r)

    if not rows:
        await message.reply("Не заданы ссылки в assets.json (/seturl).")
        return

    text = "Полезные материалы от Cherepkova Event 👇"
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await bot.send_message(CHANNEL, text, reply_markup=kb)
    await message.reply("Пост с прямыми ссылками отправлен в канал ✅")

# =========================
# Оплата и разблокировка
# =========================
@dp.callback_query(F.data == "buy_all")
async def buy_all(cb: types.CallbackQuery):
    await cb.answer()
    if not PAYMENT_TOKEN:
        await cb.message.answer("Оплата временно недоступна. Напишите нам — вышлем материалы вручную.")
        return

    prices = [LabeledPrice(label="Полный доступ ко всем материалам", amount=PRICE_RUB * 100)]  # в копейках
    await bot.send_invoice(
        chat_id=cb.message.chat.id,
        title="Cherepkova Event — полный доступ",
        description="Доступ ко всем материалам и ссылкам внутри бота.",
        payload="unlock_all",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=prices,
    )

@dp.pre_checkout_query()
async def on_pre_checkout(pre: types.PreCheckoutQuery):
    # Можно добавить собственные проверки (например, лимиты, чёрный список и т.п.)
    await bot.answer_pre_checkout_query(pre.id, ok=True)

@dp.message(F.successful_payment)
async def on_success_payment(message: types.Message):
    UNLOCKED_CHATS.add(message.chat.id)
    save_unlocked()
    ONLY_MODE_CHATS.discard(message.chat.id)  # снимаем жёсткий режим, если был

    await message.answer("Оплата прошла успешно! Полный доступ открыт ✅")
    await message.answer("Выберите раздел:", reply_markup=MAIN_KB)
    await message.answer("Быстрые ссылки:", reply_markup=link_kb_all())

# =========================
# Запуск
# =========================
async def main():
    load_assets()
    load_unlocked()
    print("Bot is running…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
