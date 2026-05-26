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

# ═══════════════════════════════════════════════════════════════════════
#                          НАСТРОЙКИ — ЗАПОЛНИТЕ ЗДЕСЬ
# ═══════════════════════════════════════════════════════════════════════
# ❗ Внимание: эти значения становятся публичными если репозиторий открытый.
#    Рекомендуется сделать репо ПРИВАТНЫМ в настройках GitHub.

# Токен бота от @BotFather — обязательно
BOT_TOKEN = "8983513295:AAHr1rfUWMijC_doOaklqoNwF9F6qLTCr_8"

# Ваш Telegram ID (узнать у @userinfobot) — обязательно
ADMIN_ID = 5062414502  # например: 5062414502

# URL сайта и секретный ключ для API
API_URL    = "https://tgleadwareon.ru"
API_SECRET = "tglw_bot_secret_2026"  # значение из /var/www/lead-combine/.env на VPS

# Публичный канал
CHANNEL_PUBLIC      = "@tgleadwareon"
CHANNEL_PUBLIC_URL  = "https://t.me/tgleadwareon"

# Приватный канал — оставьте CHANNEL_PRIVATE пустым,
# добавьте бота админом в канал, бот пришлёт ID в личку → впишите сюда.
CHANNEL_PRIVATE     = "-1003069533163"             # например: -1002345678901
CHANNEL_PRIVATE_URL = "https://t.me/+NlvOoOBd5Gs0NWNi"

# Картинка в приветственном сообщении — необязательно.
# Можно: прямой URL (https://...) ИЛИ file_id (если уже загружали в Telegram).
# Если пусто — бот отправит только текст.
WELCOME_IMAGE = ""  # например: "https://tgleadwareon.ru/static/welcome.jpg"

# ═══════════════════════════════════════════════════════════════════════
# Если env-переменные всё-таки заданы И не пустые — переопределят значения выше:
BOT_TOKEN  = (os.environ.get('BOT_TOKEN')  or BOT_TOKEN  or '').strip().strip('"').strip("'")
API_URL    = (os.environ.get('API_URL')    or API_URL    or 'https://tgleadwareon.ru').strip().rstrip('/')
API_SECRET = (os.environ.get('API_SECRET') or API_SECRET or '').strip().strip('"').strip("'")
try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID') or ADMIN_ID or 0)
except (ValueError, TypeError):
    ADMIN_ID = 0
CHANNEL_PUBLIC      = (os.environ.get('CHANNEL_PUBLIC')      or CHANNEL_PUBLIC      or '').strip()
CHANNEL_PUBLIC_URL  = (os.environ.get('CHANNEL_PUBLIC_URL')  or CHANNEL_PUBLIC_URL  or '').strip()
CHANNEL_PRIVATE     = (os.environ.get('CHANNEL_PRIVATE')     or CHANNEL_PRIVATE     or '').strip()
CHANNEL_PRIVATE_URL = (os.environ.get('CHANNEL_PRIVATE_URL') or CHANNEL_PRIVATE_URL or '').strip()
WELCOME_IMAGE       = (os.environ.get('WELCOME_IMAGE')       or WELCOME_IMAGE       or '').strip()

# Валидация перед запуском
import re
if not BOT_TOKEN or 'ВСТАВЬТЕ' in BOT_TOKEN or not re.match(r'^\d{6,}:[A-Za-z0-9_-]{30,}$', BOT_TOKEN):
    print(f'❌ BOT_TOKEN неверный или плейсхолдер. Текущее значение: {BOT_TOKEN!r}')
    print('   Откройте https://github.com/dzalil206-commits/lead-guide-bot/blob/main/bot.py')
    print('   В строке BOT_TOKEN = "..." впишите реальный токен от @BotFather')
    import sys; sys.exit(1)
# ═══════════════════════════════════════════════════════════════════════

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
    keyboard = subscribe_keyboard(REQUIRED_CHANNELS)

    # С картинкой, если задано WELCOME_IMAGE; иначе обычный текст
    if WELCOME_IMAGE:
        try:
            await message.answer_photo(
                photo=WELCOME_IMAGE,
                caption=text,
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            log.warning(f'Не удалось отправить фото ({WELCOME_IMAGE}): {e}. Шлю текст.')
    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


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
