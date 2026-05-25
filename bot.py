"""
TG Lead Wareon — Guide Bot

Бот выдаёт бонусную ссылку на 3 дня Miner-триала
после подписки пользователя на 2 канала.

Архитектура:
  /start  → приветствие + кнопки подписки на каналы
  callback "check" → проверяет подписку, дёргает API сайта, возвращает ссылку
  ChatMember update → когда бота добавляют в канал, шлёт админу chat_id
  /myid → возвращает Telegram ID пользователя (хелпер)

Развёртывание:
  - BotHost / Railway / Render / VPS
  - Один процесс, polling
  - Зависимости — requirements.txt
"""
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ChatMemberHandler, ContextTypes,
)
from telegram.error import TelegramError, BadRequest
from dotenv import load_dotenv

load_dotenv()

# ── Конфиг ───────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get('BOT_TOKEN', '')
ADMIN_ID   = int(os.environ.get('ADMIN_ID', '0') or 0)
API_URL    = os.environ.get('API_URL', 'https://tgleadwareon.ru').rstrip('/')
API_SECRET = os.environ.get('API_SECRET', '')  # = BOT_MAIN_SECRET сайта

# Каналы для обязательной подписки.
# Для приватного канала — числовой ID (-100xxxxx), для публичного можно @username.
CHANNEL_PUBLIC      = os.environ.get('CHANNEL_PUBLIC', '@tgleadwareon')
CHANNEL_PUBLIC_URL  = os.environ.get('CHANNEL_PUBLIC_URL', 'https://t.me/tgleadwareon')
CHANNEL_PRIVATE     = os.environ.get('CHANNEL_PRIVATE', '')
CHANNEL_PRIVATE_URL = os.environ.get('CHANNEL_PRIVATE_URL', 'https://t.me/+NlvOoOBd5Gs0NWNi')

REQUIRED_CHANNELS = [
    {'title': 'TG Lead Wareon',  'chat': CHANNEL_PUBLIC,  'url': CHANNEL_PUBLIC_URL},
    {'title': 'Закрытый канал',  'chat': CHANNEL_PRIVATE, 'url': CHANNEL_PRIVATE_URL},
]

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ── Вспомогательные ──────────────────────────────────────────
async def is_subscribed(context, user_id: int, chat_id) -> bool:
    """True если пользователь подписан на канал."""
    if not chat_id:
        return False
    try:
        cid = int(chat_id) if str(chat_id).lstrip('-').isdigit() else chat_id
        member = await context.bot.get_chat_member(chat_id=cid, user_id=user_id)
        return member.status in ('member', 'administrator', 'creator', 'restricted')
    except (TelegramError, BadRequest) as e:
        log.warning(f'get_chat_member({chat_id}, {user_id}) failed: {e}')
        return False


def request_bonus_url(telegram_id: int):
    """Запрашивает у сайта бонусную ссылку для пользователя."""
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
    """Клавиатура: ссылки на каналы + кнопка проверки."""
    btns = [[InlineKeyboardButton(f"📢 {c['title']}", url=c['url'])] for c in channels]
    btns.append([InlineKeyboardButton("✅ Я подписался — проверить", callback_data='check')])
    return InlineKeyboardMarkup(btns)


# ── Хендлеры ─────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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
    await update.message.reply_text(
        text,
        reply_markup=subscribe_keyboard(REQUIRED_CHANNELS),
        parse_mode='Markdown',
        disable_web_page_preview=True,
    )


async def cb_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    not_subbed = [c for c in REQUIRED_CHANNELS
                  if not await is_subscribed(context, user_id, c['chat'])]

    if not_subbed:
        text = (
            "❌ **Вы пока не подписаны на:**\n\n" +
            '\n'.join(f"▸ {c['title']}" for c in not_subbed) +
            "\n\nПодпишитесь и нажмите кнопку ещё раз."
        )
        try:
            await query.edit_message_text(
                text,
                reply_markup=subscribe_keyboard(not_subbed),
                parse_mode='Markdown',
            )
        except BadRequest:
            pass
        return

    # Все подписаны → запрашиваем ссылку у сайта
    url = request_bonus_url(user_id)
    if not url:
        await query.edit_message_text(
            "⚠️ Не удалось сгенерировать ссылку. Попробуйте через минуту "
            "или напишите в поддержку @TGLeadSupportBot.",
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
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        disable_web_page_preview=True,
    )


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Хелпер: показать ID пользователя и чата."""
    user = update.effective_user
    chat = update.effective_chat
    await update.message.reply_text(
        f"Ваш ID: `{user.id}`\n"
        f"ID этого чата: `{chat.id}` (тип: {chat.type})",
        parse_mode='Markdown',
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Команды:**\n\n"
        "/start — получить бонусную ссылку\n"
        "/myid — узнать ваш Telegram ID\n"
        "/help — эта справка",
        parse_mode='Markdown',
    )


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Срабатывает при добавлении/удалении бота из чата.
    Шлёт админу chat_id канала — удобно для настройки CHANNEL_PRIVATE.
    """
    if not update.my_chat_member or not ADMIN_ID:
        return
    new_status = update.my_chat_member.new_chat_member.status
    chat = update.my_chat_member.chat
    if new_status in ('administrator', 'member'):
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🤖 **Бот добавлен**\n\n"
                    f"ID чата: `{chat.id}`\n"
                    f"Тип: `{chat.type}`\n"
                    f"Название: {chat.title or '—'}\n"
                    f"Username: @{chat.username if chat.username else '—'}\n\n"
                    "💡 Скопируйте ID в `.env` бота "
                    "(`CHANNEL_PRIVATE=` или `CHANNEL_PUBLIC=`) и перезапустите."
                ),
                parse_mode='Markdown',
            )
        except Exception as e:
            log.error(f'cant DM admin: {e}')


# ── Entry point ──────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        log.error('BOT_TOKEN не задан в .env — бот не запустится')
        return
    if not API_SECRET:
        log.warning('API_SECRET не задан — бот не сможет запросить бонусные ссылки')

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('help',  cmd_help))
    app.add_handler(CommandHandler('myid',  cmd_myid))
    app.add_handler(CallbackQueryHandler(cb_check, pattern='^check$'))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    log.info('🚀 Guide-bot started, polling...')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
