# TG Lead Wareon — Guide Bot

Бот выдаёт пользователям **3 дня бесплатного доступа к Miner** после подписки на 2 канала.

## Как работает

1. Пользователь жмёт `/start`
2. Бот показывает 2 канала и кнопку «Проверить подписку»
3. После подписки бот запрашивает у сайта бонусную ссылку через API
4. Возвращает пользователю `https://tgleadwareon.ru/?bonus=XYZ`
5. По переходу: автоматический редирект на форму регистрации → после регистрации триал активируется

---

## Быстрый старт (локально)

```bash
git clone https://github.com/<your_user>/lead-guide-bot.git
cd lead-guide-bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# заполнить .env
python bot.py
```

---

## Настройка `.env`

| Переменная | Что | Где взять |
|---|---|---|
| `BOT_TOKEN` | Токен бота | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `ADMIN_ID` | Ваш Telegram ID | [@userinfobot](https://t.me/userinfobot) или `/myid` в этом боте |
| `API_URL` | URL сайта | `https://tgleadwareon.ru` |
| `API_SECRET` | Секрет для API | Значение `BOT_MAIN_SECRET` из `.env` сайта |
| `CHANNEL_PUBLIC` | Публичный канал | `@tgleadwareon` |
| `CHANNEL_PUBLIC_URL` | Ссылка | `https://t.me/tgleadwareon` |
| `CHANNEL_PRIVATE` | ID приватного канала | См. ниже |
| `CHANNEL_PRIVATE_URL` | Invite-ссылка | `https://t.me/+NlvOoOBd5Gs0NWNi` |

### Как узнать `CHANNEL_PRIVATE`

1. Запустите бота с пустым `CHANNEL_PRIVATE`
2. Добавьте бота как **администратора** в приватный канал
3. Бот автоматически пришлёт вам в личку числовой ID канала (`-100xxxxx`)
4. Вставьте этот ID в `.env` и перезапустите бота

---

## Деплой

### BotHost / Railway / Render

1. Залейте репозиторий на GitHub
2. Подключите репо в панели хостинга
3. Укажите все переменные окружения из `.env`
4. `Procfile` уже настроен — хостинг подхватит автоматически

### VPS (systemd)

```ini
# /etc/systemd/system/guide-bot.service
[Unit]
Description=TG Lead Wareon Guide Bot
After=network.target

[Service]
WorkingDirectory=/opt/guide-bot
ExecStart=/usr/bin/python3 /opt/guide-bot/bot.py
Restart=always
RestartSec=5
User=root
EnvironmentFile=/opt/guide-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now guide-bot
```

---

## Команды бота

- `/start` — приветствие, кнопки подписки
- `/help` — справка
- `/myid` — узнать свой Telegram ID
