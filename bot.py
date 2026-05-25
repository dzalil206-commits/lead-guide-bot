"""
TG Lead Wareon — Guide Bot (aiogram 3)

Выдаёт бонусную ссылку на 3 дня Miner-триала после подписки
пользователя на 2 канала.

Команды:
  /start  — приветствие + кнопки подписки
  /myid   — Telegram ID пользователя
  /help   — справка

Auto-handler:
  При добавлении бота в чат/канал админу присылается chat_id —
  удобно для настройки CHANNEL_PRIVATE.
"""
import os
import asyncio
import logging
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberUpdated,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from dotenv import load_dotenv

load_dotenv()

# ── Конфиг ───────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get('BOT_TOKEN', '')
ADMIN_ID   = int(os.environ.get('ADMIN_ID', '0') or 0)
API_URL    = os.environ.get('API_URL', 'https://tgleadwareon.ru').rstrip('/')
API_SECRET = os.environ.get('API_SECRET', '')

CHANNEL_PUBLIC      = os.environ.get('CHANNEL_PUBLIC',      '@tgleadwareon')
CHANNEL_PUBLIC_URL  = os.environ.get('CHANNEL_PUBLIC_URL',  'https://t.me/tgleadwareon')
CHANNEL_PRIVATE     = os.environ.get('CHANNEL_PRIVATE',     '')
CHANNEL_PRIVATE_URL = os.environ.get('CHANNEL_PRIVATE_URL', 'https://t.me/+NlvOoOBd5Gs0NWNi')

REQUIRED_CHANNELS = [
    {'title': 'TG Lead Wareon',  'chat': CHANNEL_PUBLIC,  'url': CHANNEL_PUBLIC_URL},
    {'title': 'Закрытый канал',  'chat': CHANNEL_PRIVATE, 'url': CHANNEL_PRIVATE_URL},
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher()


# ── Утилиты ──────────────────────────────────────────────────
async def is_subscribed(user_id: int, chat_id) -> bool:
    """True если пользователь подписан на канал."""
    if not chat_id:
        return False
    try:
        cid = int(chat_id) if str(chat_id).lstrip('-').isdigit() else chat_id
        m = await bot.get_chat_member(chat_id=cid, user_id=user_id)
        return m.status in ('member', 'administrator', 'creator', 'restricted')
    except (TelegramBadRequest, TelegramAPIError) as e:
        log.warning(f'get_chat_member({chat_id}, {user_id}) failed: {e}')
        return False


def request_bonus_url(telegram_id: int):
    """Запрашивает у сайта бонусную ссылку на триал."""
    if not API_SECRET:
        log.error('API_SECRET не задан')
        return None
    try:
        r = requests.post(
            f'{API_URL}/api/bot/generate_bonus',
            headers={
                'X-Bot-Secret': API_SECRET,
                'Content-Type': 'application/json',
            },
            json={'telegram_id': str(telegram_id)},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get('url')
        log.error(f'generate_bonus → HTTP {r.status_code}: {r.text[:200]}')
    except Exception as e:
        log.error(f'generate_bonus exception: {e}')
    return None


def subscribe_keyboard(channels):
    btns = [[InlineKeyboardButton(text=f"📢 {c['title']}", url=c['url'])] for c in channels]
    btns.append([InlineKeyboardButton(text="✅ Я подписался — проверить", callback_data='check')])
    return InlineKeyboardMarkup(inline_keyboard=btns)


# ── Хендлеры ─────────────────────────────────────────────────
@dp.message(Command('start'))
async def cmd_start(message: Message):
    user = message.from_user
    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я выдаю **3 дня бесплатного доступа к Miner** — инструменту для "
        "анализа Telegram-аудитории и сбора активной базы лидов.\n\n"
        "**Что внутри:**\n"
        "▸ Сбор активной аудитории из чатов и каналов\n"
        "▸ Фильтры: Premium, фото, активность, пол\n"
        "▸ Экспорт в CSV / TXT / JSON\n"
        "▸ Статистика собранной базы\n\n"
        "**Условие — подписаться на оба канала ниже и получить бонусную ссылку:**"
    )
    await message.answer(
        text,
        reply_markup=subscribe_keyboard(REQUIRED_CHANNELS),
        disable_web_page_preview=True,
    )


@dp.callback_query(F.data == 'check')
async def cb_check(query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id

    not_subbed = [c for c in REQUIRED_CHANNELS
                  if not await is_subscribed(user_id, c['chat'])]

    if not_subbed:
        text = (
            "❌ **Вы пока не подписаны на:**\n\n" +
            '\n'.join(f"▸ {c['title']}" for c in not_subbed) +
            "\n\nПодпишитесь и нажмите кнопку ещё раз."
        )
        try:
            await query.message.edit_text(text, reply_markup=subscribe_keyboard(not_subbed))
        except TelegramBadRequest:
            pass
        return

    url = request_bonus_url(user_id)
    if not url:
        await query.message.edit_text(
            "⚠️ Не удалось сгенерировать ссылку. Попробуйте через минуту "
            "или напишите в поддержку @TGLeadSupportBot."
        )
        return

    text = (
        "🎉 **Подписка подтверждена!**\n\n"
        "Ваша бонусная ссылка на **3 дня Miner бесплатно**:\n\n"
        f"🔗 {url}\n\n"
        "**Что делать дальше:**\n"
        "1️⃣ Открыть ссылку\n"
        "2️⃣ Зарегистрироваться (email + пароль)\n"
        "3️⃣ Триал активируется автоматически\n\n"
        "💡 Ссылка работает один раз. Поделитесь с тем, кому нужен Miner — "
        "пусть подпишется на каналы и получит свою."
    )
    await query.message.edit_text(text, disable_web_page_preview=True)


@dp.message(Command('myid'))
async def cmd_myid(message: Message):
    await message.answer(
        f"Ваш ID: `{message.from_user.id}`\n"
        f"ID этого чата: `{message.chat.id}` (тип: {message.chat.type})"
    )


@dp.message(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        "📖 **Команды:**\n\n"
        "/start — получить бонусную ссылку\n"
        "/myid — узнать ваш Telegram ID\n"
        "/help — эта справка"
    )


@dp.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated):
    """Срабатывает когда бота добавляют/удаляют из чата/канала.
    Шлёт админу chat_id канала — удобно для настройки CHANNEL_PRIVATE.
    """
    if not ADMIN_ID:
        return
    new_status = event.new_chat_member.status
    chat = event.chat
    if new_status in ('administrator', 'member'):
        try:
            await bot.send_message(
                ADMIN_ID,
                "🤖 **Бот добавлен в чат/канал**\n\n"
                f"ID чата: `{chat.id}`\n"
                f"Тип: `{chat.type}`\n"
                f"Название: {chat.title or '—'}\n"
                f"Username: @{chat.username if chat.username else '—'}\n\n"
                "💡 Скопируйте ID в переменные окружения бота "
                "(`CHANNEL_PRIVATE=` или `CHANNEL_PUBLIC=`) и перезапустите."
            )
        except Exception as e:
            log.error(f'cant DM admin: {e}')


# ── Entry point ──────────────────────────────────────────────
async def main():
    if not BOT_TOKEN:
        log.error('BOT_TOKEN не задан')
        return
    if not API_SECRET:
        log.warning('API_SECRET не задан — бонусные ссылки не будут выдаваться')

    log.info('🚀 Guide-bot started, polling...')
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    asyncio.run(main())
