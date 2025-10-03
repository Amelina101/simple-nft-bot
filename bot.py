import os
import sqlite3
import telebot
from telebot import types
import time
import random
import string

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 6540509823  # ВАШ РЕАЛЬНЫЙ ID

bot = telebot.TeleBot(BOT_TOKEN)

# Генератор уникальных ID для сделок
def generate_trade_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# База данных
def init_db():
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    # Таблица сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_unique_id TEXT UNIQUE,
            seller_id INTEGER,
            seller_username TEXT,
            buyer_id INTEGER,
            buyer_username TEXT,
            nft_url TEXT,
            description TEXT,
            price REAL,
            currency TEXT,
            status TEXT DEFAULT 'waiting_payment',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица пользователей (балансы)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance_rub REAL DEFAULT 0,
            balance_usd REAL DEFAULT 0,
            balance_byn REAL DEFAULT 0,
            balance_kzt REAL DEFAULT 0,
            balance_uah REAL DEFAULT 0,
            stars INTEGER DEFAULT 0,
            card_number TEXT,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            user_id INTEGER,
            amount REAL,
            currency TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем администратора
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, is_admin)
        VALUES (?, 'admin', TRUE)
    ''', (ADMIN_ID,))
    
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
    user_id = message.from_user.id
    
    # Регистрируем пользователя если его нет
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                   (user_id, f"@{message.from_user.username}" if message.from_user.username else "Без username"))
    conn.commit()
    conn.close()
    
    if len(message.text.split()) > 1:
        command = message.text.split()[1]
        if command.startswith('join_'):
            trade_unique_id = command.split('_')[1]
            join_trade(message, trade_unique_id)
            return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if message.from_user.id == ADMIN_ID:
        markup.row('🎁 Создать сделку', '💼 Мои сделки')
        markup.row('🛠️ Админ панель', '💳 Баланс')
    else:
        markup.row('🎁 Создать сделку', '💼 Мои сделки')
        markup.row('💳 Баланс')
    
    bot.send_message(message.chat.id, 
                    f"👋 Привет, {message.from_user.first_name}!\n"
                    "Добро пожаловать в NFT Trade Bot!",
                    reply_markup=markup)

# Баланс пользователя
@bot.message_handler(func=lambda message: message.text == '💳 Баланс')
def show_balance(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        user_id, username, rub, usd, byn, kzt, uah, stars, card, is_admin = user
        
        balance_text = (
            f"💰 *Ваш баланс:*\n\n"
            f"⭐ Звезды: `{stars}`\n"
            f"🇷🇺 RUB: `{rub}`\n"
            f"🇺🇸 USD: `{usd}`\n"
            f"🇧🇾 BYN: `{byn}`\n"
            f"🇰🇿 KZT: `{kzt}`\n"
            f"🇺🇦 UAH: `{uah}`\n\n"
        )
        
        if card:
            balance_text += f"💳 Привязанная карта: `{card}`\n\n"
        
        if is_admin:
            balance_text += "👑 *Статус: АДМИНИСТРАТОР*\n💎 Баланс: Безлимитный"
        else:
            balance_text += "💡 Для пополнения баланса используйте команду /deposit"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton('💳 Привязать карту', callback_data='bind_card'),
            types.InlineKeyboardButton('⭐ Пополнить звезды', callback_data='add_stars')
        )
        
        bot.send_message(message.chat.id, balance_text, reply_markup=markup, parse_mode='Markdown')

# Привязка карты
@bot.callback_query_handler(func=lambda call: call.data == 'bind_card')
def bind_card_start(call):
    msg = bot.send_message(call.message.chat.id, "💳 Введите номер вашей банковской карты (16 цифр):")
    bot.register_next_step_handler(msg, process_card_number)

def process_card_number(message):
    user_id = message.from_user.id
    card_number = message.text.replace(' ', '')
    
    if len(card_number) != 16 or not card_number.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Неверный номер карты. Введите 16 цифр:")
        bot.register_next_step_handler(msg, process_card_number)
        return
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET card_number = ? WHERE user_id = ?', (card_number, user_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ Карта успешно привязана!")

# Создание сделки
@bot.message_handler(func=lambda message: message.text == '🎁 Создать сделку')
def start_create_trade(message):
    user_id = message.from_user.id
    user_data[user_id] = {'step': 'creating_trade'}
    
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
                    "🎁 Выберите валюту для оплаты:",
                    reply_markup=markup)

# Обработка выбора валюты
@bot.callback_query_handler(func=lambda call: call.data.startswith('currency_'))
def handle_currency_selection(call):
    user_id = call.from_user.id
    currency_code = call.data.split('_')[1]
    
    user_data[user_id]['currency'] = currency_code
    user_data[user_id]['currency_display'] = CURRENCIES[currency_code]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    msg = bot.send_message(call.message.chat.id,
                         f"✅ Валюта: {CURRENCIES[currency_code]}\n"
                         "📎 Отправьте ссылку на NFT подарок:")
    
    bot.register_next_step_handler(msg, process_nft_url)

# Обработка ссылки на NFT
def process_nft_url(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    user_data[user_id]['nft_url'] = message.text
    
    msg = bot.send_message(message.chat.id, "📝 Напишите описание для сделки:")
    bot.register_next_step_handler(msg, process_description)

# Обработка описания
def process_description(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново /start")
        return
    
    user_data[user_id]['description'] = message.text
    
    currency_display = user_data[user_id]['currency_display']
    msg = bot.send_message(message.chat.id, f"💰 Укажите цену в {currency_display}:")
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
        "🎁 *Превью сделки:*\n\n"
        f"📎 NFT: {trade_data['nft_url']}\n"
        f"📝 Описание: {trade_data['description']}\n"
        f"💰 Цена: {trade_data['price']} {trade_data['currency_display']}\n\n"
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
        trade_unique_id = generate_trade_id()
        user_data[user_id]['trade_unique_id'] = trade_unique_id
        
        # Сохраняем сделку
        save_trade_to_db(user_id, user_data[user_id])
        
        trade_link = f"https://t.me/{bot.get_me().username}?start=join_{trade_unique_id}"
        
        success_text = (
            "✅ *Сделка создана!*\n\n"
            f"🔗 *Ссылка для присоединения:*\n`{trade_link}`\n\n"
            "Отправьте эту ссылку покупателю"
        )
        
        bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
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
        INSERT INTO trades (trade_unique_id, seller_id, seller_username, nft_url, description, price, currency)
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
    
    trade_id, trade_unique_id, seller_id, seller_username, buyer_id, buyer_username, nft_url, description, price, currency, status, created_at = trade
    
    if user_id == seller_id:
        bot.send_message(message.chat.id, "❌ Нельзя присоединиться к своей сделке")
        conn.close()
        return
    
    if buyer_id is not None:
        bot.send_message(message.chat.id, "❌ В этой сделке уже есть покупатель")
        conn.close()
        return
    
    # Обновляем сделку с покупателем
    cursor.execute('UPDATE trades SET buyer_id = ?, buyer_username = ?, status = ? WHERE id = ?',
                  (user_id, username, 'waiting_payment', trade_id))
    
    conn.commit()
    conn.close()
    
    # Уведомление покупателю
    bot.send_message(user_id,
                    f"✅ *Вы присоединились к сделке!*\n\n"
                    f"👤 Продавец: {seller_username}\n"
                    f"🎁 NFT: {nft_url}\n"
                    f"📝 Описание: {description}\n"
                    f"💰 Цена: {price} {CURRENCIES[currency]}\n\n"
                    f"💡 *Для завершения сделки необходимо:*\n"
                    f"1. Привязать карту или указать username для оплаты звездами\n"
                    f"2. Перевести средства\n"
                    f"3. Подтвердить оплату",
                    parse_mode='Markdown')
    
    # Уведомление продавцу
    bot.send_message(seller_id,
                    f"🎉 *Покупатель присоединился к вашей сделке!*\n\n"
                    f"👤 Покупатель: {username}\n"
                    f"💰 Сумма: {price} {CURRENCIES[currency]}\n\n"
                    f"⏳ *Ожидайте перевода от покупателя...*\n"
                    f"Как только покупатель подтвердит оплату, вы получите уведомление.",
                    parse_mode='Markdown')
    
    # Показываем кнопку оплаты покупателю
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('💳 Перейти к оплате', callback_data=f'payment_{trade_id}'))
    
    bot.send_message(user_id, "Нажмите кнопку ниже для перевода средств:", reply_markup=markup)

# Обработка оплаты
@bot.callback_query_handler(func=lambda call: call.data.startswith('payment_'))
def handle_payment(call):
    trade_id = int(call.data.split('_')[1])
    user_id = call.from_user.id
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
    trade = cursor.fetchone()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not trade or not user:
        bot.answer_callback_query(call.id, "❌ Ошибка")
        conn.close()
        return
    
    trade_id, trade_unique_id, seller_id, seller_username, buyer_id, buyer_username, nft_url, description, price, currency, status, created_at = trade
    user_id_db, username, rub, usd, byn, kzt, uah, stars, card, is_admin = user
    
    if user_id != buyer_id:
        bot.answer_callback_query(call.id, "❌ Вы не участник этой сделки")
        conn.close()
        return
    
    conn.close()
    
    # Проверяем баланс (кроме админа)
    if not is_admin:
        if currency == 'stars' and stars < price:
            bot.send_message(user_id, f"❌ Недостаточно звезд. На вашем балансе: {stars}⭐")
            return
        elif currency == 'rub' and rub < price:
            bot.send_message(user_id, f"❌ Недостаточно рублей. На вашем балансе: {rub}₽")
            return
        elif currency == 'usd' and usd < price:
            bot.send_message(user_id, f"❌ Недостаточно долларов. На вашем балансе: {usd}$")
            return
        elif currency == 'byn' and byn < price:
            bot.send_message(user_id, f"❌ Недостаточно BYN. На вашем балансе: {byn} BYN")
            return
        elif currency == 'kzt' and kzt < price:
            bot.send_message(user_id, f"❌ Недостаточно тенге. На вашем балансе: {kzt}₸")
            return
        elif currency == 'uah' and uah < price:
            bot.send_message(user_id, f"❌ Недостаточно гривен. На вашем балансе: {uah}₴")
            return
    
    # Показываем методы оплаты
    payment_text = (
        f"💳 *Оплата сделки*\n\n"
        f"💰 Сумма: {price} {CURRENCIES[currency]}\n"
        f"👤 Продавец: {seller_username}\n\n"
    )
    
    markup = types.InlineKeyboardMarkup()
    
    if currency == 'stars':
        payment_text += "⭐ *Оплата звездами:*\nУбедитесь что у вас достаточно звезд на балансе"
        markup.row(types.InlineKeyboardButton('⭐ Я оплатил(а) звездами', callback_data=f'confirm_stars_{trade_id}'))
    else:
        payment_text += f"💳 *Оплата {CURRENCIES[currency]}:*\nУбедитесь что у вас привязана карта и достаточно средств"
        markup.row(types.InlineKeyboardButton('💳 Я оплатил(а) картой', callback_data=f'confirm_card_{trade_id}'))
    
    if not is_admin:
        if currency != 'stars' and not card:
            payment_text += "\n\n❌ *У вас не привязана карта!*"
            markup.row(types.InlineKeyboardButton('💳 Привязать карту', callback_data='bind_card'))
    
    bot.edit_message_text(payment_text, call.message.chat.id, call.message.message_id, 
                         reply_markup=markup, parse_mode='Markdown')

# Подтверждение оплаты
@bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_stars_', 'confirm_card_')))
def handle_payment_confirmation(call):
    trade_id = int(call.data.split('_')[2])
    payment_method = call.data.split('_')[1]
    user_id = call.from_user.id
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
    trade = cursor.fetchone()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not trade or not user:
        bot.answer_callback_query(call.id, "❌ Ошибка")
        conn.close()
        return
    
    trade_id, trade_unique_id, seller_id, seller_username, buyer_id, buyer_username, nft_url, description, price, currency, status, created_at = trade
    user_id_db, username, rub, usd, byn, kzt, uah, stars, card, is_admin = user
    
    if user_id != buyer_id:
        bot.answer_callback_query(call.id, "❌ Вы не участник этой сделки")
        conn.close()
        return
    
    # Для НЕ-админов списываем средства
    if not is_admin:
        if currency == 'stars':
            if stars < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно звезд")
                conn.close()
                return
            cursor.execute('UPDATE users SET stars = stars - ? WHERE user_id = ?', (price, user_id))
        elif currency == 'rub':
            if rub < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно рублей")
                conn.close()
                return
            cursor.execute('UPDATE users SET balance_rub = balance_rub - ? WHERE user_id = ?', (price, user_id))
        elif currency == 'usd':
            if usd < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно долларов")
                conn.close()
                return
            cursor.execute('UPDATE users SET balance_usd = balance_usd - ? WHERE user_id = ?', (price, user_id))
        elif currency == 'byn':
            if byn < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно BYN")
                conn.close()
                return
            cursor.execute('UPDATE users SET balance_byn = balance_byn - ? WHERE user_id = ?', (price, user_id))
        elif currency == 'kzt':
            if kzt < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно тенге")
                conn.close()
                return
            cursor.execute('UPDATE users SET balance_kzt = balance_kzt - ? WHERE user_id = ?', (price, user_id))
        elif currency == 'uah':
            if uah < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно гривен")
                conn.close()
                return
            cursor.execute('UPDATE users SET balance_uah = balance_uah - ? WHERE user_id = ?', (price, user_id))
    
    # Обновляем статус сделки
    cursor.execute('UPDATE trades SET status = ? WHERE id = ?', ('waiting_delivery', trade_id))
    
    # Записываем транзакцию
    cursor.execute('INSERT INTO transactions (trade_id, user_id, amount, currency, status) VALUES (?, ?, ?, ?, ?)',
                  (trade_id, user_id, price, currency, 'completed' if is_admin else 'pending'))
    
    conn.commit()
    conn.close()
    
    # Уведомление покупателю
    bot.edit_message_text(
        "✅ *Оплата подтверждена!*\n\n"
        "💰 Средства зарезервированы\n"
        "⏳ Ожидайте передачи NFT от продавца\n\n"
        "💡 Продавец получил уведомление и скоро передаст вам подарок",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )
    
    # Уведомление продавцу
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton('🎁 Я передал(а) NFT', callback_data=f'delivered_{trade_id}'))
    
    bot.send_message(seller_id,
                    f"🎉 *Покупатель подтвердил оплату!*\n\n"
                    f"👤 Покупатель: {buyer_username}\n"
                    f"💰 Сумма: {price} {CURRENCIES[currency]}\n"
                    f"🎁 NFT: {nft_url}\n\n"
                    f"📦 *Теперь вам нужно:*\n"
                    f"1. Передать NFT подарок на аккаунт покупателя\n"
                    f"2. Сделать скриншот подтверждения\n"
                    f"3. Нажать кнопку 'Я передал(а) NFT'\n\n"
                    f"💡 *Внимание!* Без подтверждения передачи NFT средства не поступят на ваш счет!",
                    reply_markup=markup, parse_mode='Markdown')

# Подтверждение передачи NFT
@bot.callback_query_handler(func=lambda call: call.data.startswith('delivered_'))
def handle_delivery_confirmation(call):
    trade_id = int(call.data.split('_')[1])
    user_id = call.from_user.id
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
    trade = cursor.fetchone()
    
    if not trade or user_id != trade[2]:  # seller_id
        bot.answer_callback_query(call.id, "❌ Ошибка")
        conn.close()
        return
    
    trade_id, trade_unique_id, seller_id, seller_username, buyer_id, buyer_username, nft_url, description, price, currency, status, created_at = trade
    
    # Запрашиваем скриншот
    msg = bot.send_message(user_id, 
                          "📸 *Прикрепите скриншот подтверждения передачи NFT:*\n\n"
                          "На скриншоте должно быть видно:\n"
                          "• Передачу подарка\n"
                          "• Аккаунт получателя\n"
                          "• Дату и время\n\n"
                          "💡 Это необходимо для защиты обеих сторон сделки",
                          parse_mode='Markdown')
    
    user_data[user_id] = {'step': 'waiting_screenshot', 'trade_id': trade_id}
    conn.close()

# Обработка скриншота
@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('step') != 'waiting_screenshot':
        return
    
    trade_id = user_data[user_id]['trade_id']
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
    trade = cursor.fetchone()
    
    if trade:
        trade_id, trade_unique_id, seller_id, seller_username, buyer_id, buyer_username, nft_url, description, price, currency, status, created_at = trade
        
        # Завершаем сделку
        cursor.execute('UPDATE trades SET status = ? WHERE id = ?', ('completed', trade_id))
        
        # Зачисляем средства продавцу (если не админ)
        cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (buyer_id,))
        buyer_is_admin = cursor.fetchone()[0]
        
        if not buyer_is_admin:
            if currency == 'stars':
                cursor.execute('UPDATE users SET stars = stars + ? WHERE user_id = ?', (price, seller_id))
            elif currency == 'rub':
                cursor.execute('UPDATE users SET balance_rub = balance_rub + ? WHERE user_id = ?', (price, seller_id))
            elif currency == 'usd':
                cursor.execute('UPDATE users SET balance_usd = balance_usd + ? WHERE user_id = ?', (price, seller_id))
            elif currency == 'byn':
                cursor.execute('UPDATE users SET balance_byn = balance_byn + ? WHERE user_id = ?', (price, seller_id))
            elif currency == 'kzt':
                cursor.execute('UPDATE users SET balance_kzt = balance_kzt + ? WHERE user_id = ?', (price, seller_id))
            elif currency == 'uah':
                cursor.execute('UPDATE users SET balance_uah = balance_uah + ? WHERE user_id = ?', (price, seller_id))
        
        conn.commit()
        conn.close()
        
        # Уведомление продавцу
        bot.send_message(seller_id,
                        "✅ *Сделка завершена!*\n\n"
                        f"💰 Средства зачислены на ваш баланс\n"
                        f"🎁 NFT успешно передан\n"
                        f"👤 Покупатель: {buyer_username}\n\n"
                        "Спасибо за сделку! 🎉",
                        parse_mode='Markdown')
        
        # Уведомление покупателю
        bot.send_message(buyer_id,
                        "✅ *Сделка завершена!*\n\n"
                        f"🎁 Вы получили NFT подарок\n"
                        f"👤 Продавец: {seller_username}\n"
                        f"📎 NFT: {nft_url}\n\n"
                        "Спасибо за покупку! 🎉",
                        parse_mode='Markdown')
        
        del user_data[user_id]

# Мои сделки
@bot.message_handler(func=lambda message: message.text == '💼 Мои сделки')
def my_trades(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    # Сделки где пользователь продавец
    cursor.execute('SELECT * FROM trades WHERE seller_id = ? ORDER BY created_at DESC', (user_id,))
    seller_trades = cursor.fetchall()
    
    # Сделки где пользователь покупатель
    cursor.execute('SELECT * FROM trades WHERE buyer_id = ? ORDER BY created_at DESC', (user_id,))
    buyer_trades = cursor.fetchall()
    
    conn.close()
    
    if not seller_trades and not buyer_trades:
        bot.send_message(message.chat.id, "📭 У вас пока нет сделок")
        return
    
    if seller_trades:
        bot.send_message(message.chat.id, "🏪 *Сделки где вы продавец:*", parse_mode='Markdown')
        for trade in seller_trades:
            show_trade_info(message.chat.id, trade, 'seller')
    
    if buyer_trades:
        bot.send_message(message.chat.id, "🛒 *Сделки где вы покупатель:*", parse_mode='Markdown')
        for trade in buyer_trades:
            show_trade_info(message.chat.id, trade, 'buyer')

def show_trade_info(chat_id, trade, role):
    trade_id, trade_unique_id, seller_id, seller_username, buyer_id, buyer_username, nft_url, description, price, currency, status, created_at = trade
    
    status_emoji = {
        'waiting_payment': '⏳',
        'waiting_delivery': '📦', 
        'completed': '✅',
        'cancelled': '❌'
    }
    
    text = (
        f"🎁 *Сделка #{trade_id}*\n"
        f"💰 {price} {CURRENCIES[currency]}\n"
        f"📊 Статус: {status_emoji.get(status, '⚡')} {status}\n"
        f"🕐 {created_at[:16]}"
    )
    
    if role == 'seller' and buyer_username:
        text += f"\n👤 Покупатель: {buyer_username}"
    elif role == 'buyer':
        text += f"\n👤 Продавец: {seller_username}"
    
    bot.send_message(chat_id, text, parse_mode='Markdown')

# Админ панель
@bot.message_handler(func=lambda message: message.text == '🛠️ Админ панель' and message.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('📊 Статистика', callback_data='admin_stats'),
        types.InlineKeyboardButton('👥 Пользователи', callback_data='admin_users')
    )
    markup.row(
        types.InlineKeyboardButton('💼 Все сделки', callback_data='admin_trades'),
        types.InlineKeyboardButton('💰 Балансы', callback_data='admin_balances')
    )
    
    bot.send_message(message.chat.id, 
                    "🛠️ *Панель администратора*\n\n"
                    "👑 Статус: АДМИНИСТРАТОР\n"
                    "💎 Баланс: Безлимитный\n"
                    "⚡ Привилегии: Все операции",
                    reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['test'])
def send_test(message):
    bot.reply_to(message, "✅ Бот работает!")

# Запуск бота
if __name__ == "__main__":
    print("🤖 Бот запущен с полной системой сделок!")
    bot.infinity_polling()

