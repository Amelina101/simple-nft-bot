import os
import sqlite3
import telebot
from telebot import types
import time

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 6540509823  # ЗАМЕНИТЕ НА ВАШ ID

bot = telebot.TeleBot(BOT_TOKEN)

# База данных для хранения сделок
def init_db():
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nft_url TEXT,
            description TEXT,
            price REAL,
            currency TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Словарь для временного хранения данных о создаваемых сделках
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
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if message.from_user.id == ADMIN_ID:
        markup.row('🎁 Создать сделку', '💼 Мои сделки')
        markup.row('🛠️ Админ панель', '📊 Статистика')
    else:
        markup.row('🎁 Создать сделку', '💼 Мои сделки')
        markup.row('🛠️ Магазин NFT')
    
    bot.send_message(message.chat.id, 
                    f"👋 Привет, {message.from_user.first_name}!\n"
                    "Добро пожаловать в NFT Trade Bot!\n\n"
                    "🎁 Создавайте сделки с NFT подарками\n"
                    "💵 Мультивалютная система оплаты",
                    reply_markup=markup)

# Начало создания сделки
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
    markup.row(
        types.InlineKeyboardButton(CURRENCIES['kzt'], callback_data='currency_kzt'),
        types.InlineKeyboardButton(CURRENCIES['uah'], callback_data='currency_uah')
    )
    
    bot.send_message(message.chat.id,
                    "🎁 *Создание новой сделки*\n\n"
                    "💵 Выберите валюту для оплаты:",
                    reply_markup=markup, parse_mode='Markdown')

# Обработка выбора валюты
@bot.callback_query_handler(func=lambda call: call.data.startswith('currency_'))
def handle_currency_selection(call):
    user_id = call.from_user.id
    currency_code = call.data.split('_')[1]
    
    user_data[user_id]['currency'] = CURRENCIES[currency_code]
    user_data[user_id]['currency_code'] = currency_code
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    msg = bot.send_message(call.message.chat.id,
                         f"✅ Валюта оплаты: {user_data[user_id]['currency']}\n\n"
                         "📎 Отправьте ссылку на NFT подарок:")
    
    bot.register_next_step_handler(msg, process_nft_url)

# Обработка ссылки на NFT
def process_nft_url(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    user_data[user_id]['nft_url'] = message.text
    
    msg = bot.send_message(message.chat.id,
                         "📝 Напишите описание для вашей сделки:")
    
    bot.register_next_step_handler(msg, process_description)

# Обработка описания
def process_description(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    user_data[user_id]['description'] = message.text
    
    currency_display = user_data[user_id]['currency']
    msg = bot.send_message(message.chat.id,
                         f"💰 Укажите цену в {currency_display} (только цифры):")
    
    bot.register_next_step_handler(msg, process_price)

# Обработка цены
def process_price(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError("Цена должна быть больше 0")
        
        user_data[user_id]['price'] = price
        show_trade_preview(message.chat.id, user_id)
        
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Неверный формат цены. Введите только цифры:")
        bot.register_next_step_handler(msg, process_price)

# Показ превью сделки
def show_trade_preview(chat_id, user_id):
    trade_data = user_data[user_id]
    
    preview_text = (
        "🎁 *Превью сделки*\n\n"
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
    
    bot.send_message(chat_id, preview_text, reply_markup=markup, parse_mode='Markdown')

# Подтверждение сделки
@bot.callback_query_handler(func=lambda call: call.data in ['confirm_trade', 'cancel_trade'])
def handle_trade_confirmation(call):
    user_id = call.from_user.id
    
    if call.data == 'confirm_trade':
        save_trade_to_db(user_id, user_data[user_id])
        
        trade_data = user_data[user_id]
        success_text = (
            "✅ *Сделка успешно создана!*\n\n"
            f"🎁 NFT: {trade_data['nft_url']}\n"
            f"📝 Описание: {trade_data['description']}\n"
            f"💰 Цена: {trade_data['price']} {trade_data['currency']}\n\n"
            "Теперь другие пользователи могут увидеть вашу сделку!"
        )
        
        bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        if user_id in user_data:
            del user_data[user_id]
            
    else:
        bot.edit_message_text("❌ Создание сделки отменено", call.message.chat.id, call.message.message_id)
        if user_id in user_data:
            del user_data[user_id]

# Сохранение сделки в базу данных
def save_trade_to_db(user_id, trade_data):
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO trades (user_id, nft_url, description, price, currency)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, trade_data['nft_url'], trade_data['description'], 
          trade_data['price'], trade_data['currency']))
    
    conn.commit()
    conn.close()

# Админ панель
@bot.message_handler(func=lambda message: message.text == '🛠️ Админ панель' and message.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('📊 Статистика', callback_data='stats'),
        types.InlineKeyboardButton('🎁 Все сделки', callback_data='all_trades')
    )
    
    bot.send_message(message.chat.id, 
                    "🛠️ *Панель администратора*\n\n"
                    "📊 Ваша статистика:\n"
                    "• Сделок: 1423\n"
                    "• Рейтинг: 5.0/5 ⭐⭐⭐⭐⭐\n"
                    "💎 Баланс: Безлимитный",
                    reply_markup=markup, parse_mode='Markdown')

# Мои сделки
@bot.message_handler(func=lambda message: message.text == '💼 Мои сделки')
def my_trades(message):
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE user_id = ? ORDER BY created_at DESC', (message.from_user.id,))
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        bot.send_message(message.chat.id, "📭 У вас пока нет созданных сделок")
        return
    
    for trade in trades:
        trade_id, user_id, nft_url, description, price, currency, status, created_at = trade
        
        trade_text = (
            f"🎁 *Сделка #{trade_id}*\n\n"
            f"📎 NFT: {nft_url}\n"
            f"📝 Описание: {description}\n"
            f"💰 Цена: {price} {currency}\n"
            f"📊 Статус: {status}\n"
            f"🕐 Создана: {created_at[:16]}"
        )
        
        bot.send_message(message.chat.id, trade_text, parse_mode='Markdown')

@bot.message_handler(commands=['test'])
def send_test(message):
    bot.reply_to(message, "✅ Бот работает!")

# Улучшенный запуск с обработкой ошибок
def start_bot():
    print("🚀 Попытка запуска бота...")
    
    try:
        # Останавливаем любые предыдущие соединения
        bot.remove_webhook()
        time.sleep(1)
        
        print("✅ Бот запускается...")
        bot.infinity_polling()
        
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        time.sleep(10)
        start_bot()

if __name__ == "__main__":
    print("🤖 NFT Trade Bot инициализирован")
    print(f"💵 Доступные валюты: {list(CURRENCIES.values())}")
    print(f"👑 Админ ID: {ADMIN_ID}")
    
    start_bot()