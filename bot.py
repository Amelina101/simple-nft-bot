import os
import sqlite3
import telebot
from telebot import types
import time
import random
import string

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 6540509823# ВАШ РЕАЛЬНЫЙ ID

bot = telebot.TeleBot(BOT_TOKEN)

# Генератор уникальных ID для сделок
def generate_trade_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# База данных для хранения сделок
def init_db():
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_unique_id TEXT UNIQUE,
            user_id INTEGER,
            user_username TEXT,
            nft_url TEXT,
            description TEXT,
            price REAL,
            currency TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            user_id INTEGER,
            user_username TEXT,
            status TEXT DEFAULT 'joined',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Словарь для временного хранения данных
user_data = {}

# Доступные валюты
CURRENCIES = {
    'stars': '⭐ Звезды',
    'rub': '🇷🇺 RUB (Рубли)',
    'usd': '🇺🇸 USD (Доллары)',
    'byn': '🇧🇾 BYN (Белорусские рубли)',
    'kzt': '🇰🇿 KZT (Тенге)',
    'uah': '🇺🇦 UAH (Гривны)'
}

# Главное меню
@bot.message_handler(commands=['start'])
def send_welcome(message):
    init_db()
    
    if len(message.text.split()) > 1:
        command = message.text.split()[1]
        if command.startswith('join_'):
            trade_unique_id = command.split('_')[1]
            join_trade(message, trade_unique_id)
            return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if message.from_user.id == ADMIN_ID:
        markup.row('🎁 Создать сделку', '💼 Мои сделки')
        markup.row('🛠️ Админ панель')
    else:
        markup.row('🎁 Создать сделку', '💼 Мои сделки')
    
    bot.send_message(message.chat.id, 
                    f"👋 Привет, {message.from_user.first_name}!\n"
                    "Добро пожаловать в NFT Trade Bot!",
                    reply_markup=markup)

# Создание сделки
@bot.message_handler(func=lambda message: message.text == '🎁 Создать сделку')
def start_create_trade(message):
    user_id = message.from_user.id
    user_data[user_id] = {}
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(CURRENCIES['stars'], callback_data='currency_stars'),
        types.InlineKeyboardButton(CURRENCIES['rub'], callback_data='currency_rub')
    )
    markup.row(
        types.InlineKeyboardButton(CURRENCIES['usd'], callback_data='currency_usd'),
        types.InlineKeyboardButton(CURRENCIES['byn'], callback_data='currency_byn')
    )
    
    bot.send_message(message.chat.id,
                    "🎁 Выберите валюту для оплаты:",
                    reply_markup=markup)

# Обработка выбора валюты
@bot.callback_query_handler(func=lambda call: call.data.startswith('currency_'))
def handle_currency_selection(call):
    user_id = call.from_user.id
    currency_code = call.data.split('_')[1]
    
    user_data[user_id]['currency'] = CURRENCIES[currency_code]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    msg = bot.send_message(call.message.chat.id,
                         f"✅ Валюта: {user_data[user_id]['currency']}\n"
                         "📎 Отправьте ссылку на NFT:")
    
    bot.register_next_step_handler(msg, process_nft_url)

# Обработка ссылки на NFT
def process_nft_url(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    user_data[user_id]['nft_url'] = message.text
    
    msg = bot.send_message(message.chat.id, "📝 Напишите описание:")
    bot.register_next_step_handler(msg, process_description)

# Обработка описания
def process_description(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    user_data[user_id]['description'] = message.text
    
    currency_display = user_data[user_id]['currency']
    msg = bot.send_message(message.chat.id, f"💰 Цена в {currency_display}:")
    bot.register_next_step_handler(msg, process_price)

# Обработка цены
def process_price(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    try:
        price = float(message.text)
        user_data[user_id]['price'] = price
        show_trade_preview(message.chat.id, user_id)
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Неверный формат цены. Введите цифры:")
        bot.register_next_step_handler(msg, process_price)

# Показ превью сделки
def show_trade_preview(chat_id, user_id):
    trade_data = user_data[user_id]
    
    preview_text = (
        "🎁 Превью сделки:\n\n"
        f"📎 NFT: {trade_data['nft_url']}\n"
        f"📝 Описание: {trade_data['description']}\n"
        f"💰 Цена: {trade_data['price']} {trade_data['currency']}\n\n"
        "Всё верно?"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('✅ Подтвердить', callback_data='confirm_trade'),
        types.InlineKeyboardButton('❌ Отменить', callback_data='cancel_trade')
    )
    
    bot.send_message(chat_id, preview_text, reply_markup=markup)

# Подтверждение сделки
@bot.callback_query_handler(func=lambda call: call.data in ['confirm_trade', 'cancel_trade'])
def handle_trade_confirmation(call):
    user_id = call.from_user.id
    
    if call.data == 'confirm_trade':
        trade_unique_id = generate_trade_id()
        user_data[user_id]['trade_unique_id'] = trade_unique_id
        
        # Сохраняем сделку
        save_trade_to_db(user_id, user_data[user_id])
        
        trade_link = f"https://t.me/{bot.get_me().username}?start=join_{trade_unique_id}"
        
        success_text = (
            "✅ Сделка создана!\n\n"
            f"🔗 Ссылка для присоединения:\n`{trade_link}`"
        )
        
        bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id)
        
        if user_id in user_data:
            del user_data[user_id]
            
    else:
        bot.edit_message_text("❌ Создание отменено", call.message.chat.id, call.message.message_id)
        if user_id in user_data:
            del user_data[user_id]

# Сохранение сделки в базу
def save_trade_to_db(user_id, trade_data):
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    username = f"@{bot.get_chat(user_id).username}" if bot.get_chat(user_id).username else "Без username"
    
    cursor.execute('''
        INSERT INTO trades (trade_unique_id, user_id, user_username, nft_url, description, price, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (trade_data['trade_unique_id'], user_id, username,
          trade_data['nft_url'], trade_data['description'], 
          trade_data['price'], trade_data['currency']))
    
    conn.commit()
    conn.close()

# Присоединение к сделке
def join_trade(message, trade_unique_id):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Без username"
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE trade_unique_id = ?', (trade_unique_id,))
    trade = cursor.fetchone()
    
    if not trade:
        bot.send_message(message.chat.id, "❌ Сделка не найдена")
        conn.close()
        return
    
    trade_id, trade_unique_id, creator_id, creator_username, nft_url, description, price, currency, status, created_at = trade
    
    if user_id == creator_id:
        bot.send_message(message.chat.id, "❌ Нельзя присоединиться к своей сделке")
        conn.close()
        return
    
    cursor.execute('SELECT * FROM trade_participants WHERE trade_id = ? AND user_id = ?', (trade_id, user_id))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ Вы уже присоединились")
        conn.close()
        return
    
    cursor.execute('INSERT INTO trade_participants (trade_id, user_id, user_username) VALUES (?, ?, ?)',
                  (trade_id, user_id, username))
    
    conn.commit()
    conn.close()
    
    # Уведомления
    bot.send_message(message.chat.id,
                    f"✅ Вы присоединились к сделке!\n\n"
                    f"👤 Создатель: {creator_username}\n"
                    f"💰 Цена: {price} {currency}")
    
    bot.send_message(creator_id,
                    f"🎉 Новый участник: {username}\n"
                    f"🆔 ID: {user_id}")

# Мои сделки
@bot.message_handler(func=lambda message: message.text == '💼 Мои сделки')
def my_trades(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE user_id = ?', (user_id,))
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        bot.send_message(message.chat.id, "📭 У вас нет сделок")
        return
    
    for trade in trades:
        trade_id, trade_unique_id, user_id, username, nft_url, description, price, currency, status, created_at = trade
        
        trade_text = (
            f"🎁 Сделка #{trade_id}\n"
            f"💰 {price} {currency}\n"
            f"🕐 {created_at[:16]}"
        )
        
        bot.send_message(message.chat.id, trade_text)

# Админ панель
@bot.message_handler(func=lambda message: message.text == '🛠️ Админ панель' and message.from_user.id == ADMIN_ID)
def admin_panel(message):
    bot.send_message(message.chat.id, "🛠️ Админ панель\n\nСделок: 1423\nРейтинг: 5.0")

@bot.message_handler(commands=['test'])
def send_test(message):
    bot.reply_to(message, "✅ Бот работает!")

# Запуск бота
if __name__ == "__main__":
    print("🤖 Бот запущен!")
    bot.infinity_polling()