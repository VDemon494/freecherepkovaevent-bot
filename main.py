import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from dotenv import load_dotenv

# -------- конфиг --------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL", "@cherepkovaevent")
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "").lstrip("@")  # freecherepkovaevent_bot

if not BOT_TOKEN:
    raise SystemExit("Не задан BOT_TOKEN")

ASSETS_FILE = Path("assets.json")
ASSETS: Dict[str, Any] = {}

TITLES = {
    "venues": "Загородные площадки без аренды (Екатеринбург)",
    "hidden_costs": "Скрытые расходы свадьбы",
    "vs_diy": "Свадьба «под ключ» vs самостоятельная подготовка",
    "checklist": "Бесплатный чек-лист: «Как подготовить свадьбу и ничего не забыть»",
    "budget_calc": "Как рассчитать свадебный бюджет",
    "venue_questions": "Какие вопросы задать площадке перед бронированием?"
}


MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏡 Площадки без аренды"), KeyboardButton(text="💸 Скрытые расходы")],
        [KeyboardButton(text="⚖️ Под ключ vs DIY"),   KeyboardButton(text="🧮 Бюджет свадьбы")],
        [KeyboardButton(text="🧾 Чек-лист"),          KeyboardButton(text="❓ Вопросы площадке")],
        [KeyboardButton(text="ℹ️ О нас")]
    ],
    resize_keyboard=True
)


# -------- утилиты --------
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

def get_url(key: str) -> Optional[str]:
    return (ASSETS.get(key) or {}).get("url")

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
    def row(key, label):
        url = get_url(key)
        if url:
            rows.append([InlineKeyboardButton(text=label, url=url)])
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


# -------- бот --------
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else None
    if payload in TITLES:
        url = get_url(payload)
        if url:
            await message.answer(f"{TITLES[payload]}\nНажмите кнопку ниже:", reply_markup=link_kb_single(payload))
        else:
            await message.answer("Ссылка ещё не настроена. Сообщите администратору.")
        return
    await message.answer("Привет! Я отправлю нужные ссылки. Выберите:", reply_markup=MAIN_KB)
    await message.answer("Быстрые ссылки:", reply_markup=link_kb_all())

@dp.message(Command("docs"))
async def docs(message: types.Message):
    await message.answer("Выберите материал:", reply_markup=link_kb_all())

@dp.message(F.text == "🧾 Чек-лист")
async def checklist(message: types.Message):
    if get_url("checklist"):
        await message.answer(TITLES["checklist"], reply_markup=link_kb_single("checklist"))
    else:
        await message.answer("Ссылка на чек-лист ещё не настроена.")

@dp.message(F.text == "📘 Гайд")
async def guide(message: types.Message):
    if get_url("guide"):
        await message.answer(TITLES["guide"], reply_markup=link_kb_single("guide"))
    else:
        await message.answer("Ссылка на гайд ещё не настроена.")

@dp.message(F.text == "ℹ️ О нас")
async def about(message: types.Message):
    await message.answer(
        "Мы — Cherepkova Event: свадьба под ключ по фиксированной цене и личный кабинет пары.\n"
        "Подробнее: https://cherepkovaevent.ru"
    )

@dp.message(Command("seturl"))
async def seturl(message: types.Message):
    try:
        _, key, url = (message.text or "").split(maxsplit=2)
    except ValueError:
        await message.reply("Формат: /seturl <checklist|guide> <URL>")
        return
    if key not in ("checklist", "guide"):
        await message.reply("Ключ должен быть checklist или guide")
        return
    ASSETS.setdefault(key, {})
    ASSETS[key]["url"] = url
    save_assets()
    await message.reply(f"URL для {key} сохранён ✅")

@dp.message(Command("post"))
async def post(message: types.Message):
    username = BOT_USERNAME or (await bot.get_me()).username
    text = (
        "Готовитесь к свадьбе? Забирайте полезные материалы 👇\n"
        "• 🧾 Чек-лист подготовки\n"
        "• 📘 Гайд «100 шагов»"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧾 Чек-лист", url=f"https://t.me/{username}?start=checklist")],
            [InlineKeyboardButton(text="📘 Гайд",     url=f"https://t.me/{username}?start=guide")]
        ]
    )
    await bot.send_message(CHANNEL, text, reply_markup=kb)
    await message.reply("Пост отправлен в канал ✅")

@dp.message(Command("post_direct"))
async def post_direct(message: types.Message):
    c_url = get_url("checklist")
    g_url = get_url("guide")
    if not (c_url or g_url):
        await message.reply("Не заданы ссылки в assets.json (/seturl).")
        return
    text = "Полезные материалы по подготовке к свадьбе 👇"
    rows = []
    if c_url: rows.append([InlineKeyboardButton(text="🧾 Открыть Чек-лист", url=c_url)])
    if g_url: rows.append([InlineKeyboardButton(text="📘 Открыть Гайд", url=g_url)])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await bot.send_message(CHANNEL, text, reply_markup=kb)
    await message.reply("Пост с прямыми ссылками отправлен в канал ✅")
# ==============================
# Обработчики кнопок меню
# ==============================

@dp.message(F.text == "🏡 Площадки без аренды")
async def kb_venues(m: types.Message):
    await m.answer(TITLES["venues"], reply_markup=link_kb_single("venues"))

@dp.message(F.text == "💸 Скрытые расходы")
async def kb_hidden(m: types.Message):
    await m.answer(TITLES["hidden_costs"], reply_markup=link_kb_single("hidden_costs"))

@dp.message(F.text == "⚖️ Под ключ vs DIY")
async def kb_vs(m: types.Message):
    await m.answer(TITLES["vs_diy"], reply_markup=link_kb_single("vs_diy"))

@dp.message(F.text == "🧮 Бюджет свадьбы")
async def kb_budget(m: types.Message):
    await m.answer(TITLES["budget_calc"], reply_markup=link_kb_single("budget_calc"))

@dp.message(F.text == "🧾 Чек-лист")
async def kb_checklist(m: types.Message):
    await m.answer(TITLES["checklist"], reply_markup=link_kb_single("checklist"))

@dp.message(F.text == "❓ Вопросы площадке")
async def kb_questions(m: types.Message):
    await m.answer(TITLES["venue_questions"], reply_markup=link_kb_single("venue_questions"))

@dp.message(F.text == "ℹ️ О нас")
async def kb_about(m: types.Message):
    await m.answer("Агентство Cherepkova Event 💍\nОрганизация свадеб под ключ.\nhttps://cherepkovaevent.ru")


async def main():
    load_assets()
    print("Bot is running…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
