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
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# База данных
def init_db():
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
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
                status TEXT DEFAULT 'waiting_buyer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance_rub REAL DEFAULT 1000,
                balance_usd REAL DEFAULT 100,
                balance_byn REAL DEFAULT 500,
                balance_kzt REAL DEFAULT 50000,
                balance_uah REAL DEFAULT 4000,
                stars INTEGER DEFAULT 50,
                card_number TEXT,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Создаем администратора
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, is_admin)
            VALUES (?, 'admin', TRUE)
        ''', (ADMIN_ID,))
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

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
    if not init_db():
        bot.send_message(message.chat.id, "❌ Ошибка системы. Попробуйте позже.")
        return
    
    user_id = message.from_user.id
    
    # Регистрируем пользователя
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                       (user_id, f"@{message.from_user.username}" if message.from_user.username else "Без username"))
        conn.commit()
        conn.close()
    except:
        pass
    
    # Проверяем ссылку присоединения
    if len(message.text.split()) > 1:
        command = message.text.split()[1]
        if command.startswith('join_'):
            trade_unique_id = command[5:]  # Убираем 'join_'
            process_join_trade(message, trade_unique_id)
            return
    
    # Показываем главное меню
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

# Процесс присоединения к сделке
def process_join_trade(message, trade_unique_id):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Без username"
    
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Находим сделку
        cursor.execute('SELECT * FROM trades WHERE trade_unique_id = ?', (trade_unique_id,))
        trade = cursor.fetchone()
        
        if not trade:
            bot.send_message(message.chat.id, "❌ Сделка не найдена или устарела")
            conn.close()
            return
        
        # Распаковываем данные сделки
        (trade_id, trade_unique_id_db, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        # Проверяем не является ли пользователь продавцом
        if user_id == seller_id:
            bot.send_message(message.chat.id, 
                           "❌ Вы не можете присоединиться к своей собственной сделке!\n\n"
                           "💡 Отправьте эту ссылку другому человеку для покупки.")
            conn.close()
            return
        
        # Проверяем нет ли уже покупателя
        if buyer_id is not None:
            bot.send_message(message.chat.id, "❌ В этой сделке уже есть покупатель")
            conn.close()
            return
        
        # Обновляем сделку с покупателем
        cursor.execute('''
            UPDATE trades 
            SET buyer_id = ?, buyer_username = ?, status = ? 
            WHERE id = ?
        ''', (user_id, username, 'waiting_payment', trade_id))
        
        conn.commit()
        conn.close()
        
        # УВЕДОМЛЕНИЕ ДЛЯ ПОКУПАТЕЛЯ
        buyer_message = (
            f"✅ *Вы присоединились к сделке!*\n\n"
            f"👤 **Продавец:** {seller_username}\n"
            f"🎁 **NFT:** {nft_url}\n"
            f"📝 **Описание:** {description}\n"
            f"💰 **Цена:** {price} {CURRENCIES[currency]}\n\n"
            f"💡 *Для завершения сделки необходимо:*\n"
            f"1. Перейти к оплате\n"
            f"2. Подтвердить перевод средств\n"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('💳 Перейти к оплате', callback_data=f'start_payment_{trade_id}'))
        
        bot.send_message(user_id, buyer_message, reply_markup=markup, parse_mode='Markdown')
        
        # УВЕДОМЛЕНИЕ ДЛЯ ПРОДАВЦА
        seller_message = (
            f"🎉 *Покупатель присоединился к вашей сделке!*\n\n"
            f"👤 **Покупатель:** {username}\n"
            f"💰 **Сумма:** {price} {CURRENCIES[currency]}\n\n"
            f"⏳ *Ожидайте оплаты от покупателя...*\n"
            f"Вы получите уведомление, когда покупатель подтвердит перевод."
        )
        
        bot.send_message(seller_id, seller_message, parse_mode='Markdown')
        
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка присоединения к сделке")
        print(f"❌ Ошибка присоединения: {e}")

# Баланс пользователя
@bot.message_handler(func=lambda message: message.text == '💳 Баланс')
def show_balance(message):
    user_id = message.from_user.id
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
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
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки баланса")

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
                    "🎁 *Создание новой сделки*\n\n"
                    "💵 Выберите валюту для оплаты:",
                    reply_markup=markup, parse_mode='Markdown')

# Обработка выбора валюты
@bot.callback_query_handler(func=lambda call: call.data.startswith('currency_'))
def handle_currency_selection(call):
    user_id = call.from_user.id
    currency_code = call.data.split('_')[1]
    
    user_data[user_id]['currency'] = currency_code
    user_data[user_id]['currency_display'] = CURRENCIES[currency_code]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    msg = bot.send_message(call.message.chat.id,
                         f"✅ Валюта: {CURRENCIES[currency_code]}\n\n"
                         "📎 Отправьте ссылку на NFT подарок:",
                         parse_mode='Markdown')
    
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
    msg = bot.send_message(message.chat.id, f"💰 Укажите цену в {currency_display} (только цифры):")
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
        
        # СОЗДАЕМ ССЫЛКУ ДЛЯ ПРИСОЕДИНЕНИЯ
        join_link = f"https://t.me/{bot.get_me().username}?start=join_{trade_unique_id}"
        
        success_text = (
            "✅ *Сделка успешно создана!*\n\n"
            f"🎁 **Ссылка для присоединения:**\n"
            f"`{join_link}`\n\n"
            f"📎 **NFT:** {user_data[user_id]['nft_url']}\n"
            f"💰 **Цена:** {user_data[user_id]['price']} {user_data[user_id]['currency_display']}\n\n"
            f"💡 *Отправьте эту ссылку покупателю*\n"
            f"❌ *Вы не можете присоединиться к своей сделке*"
        )
        
        bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        # Очищаем временные данные
        if user_id in user_data:
            del user_data[user_id]
            
    else:
        bot.edit_message_text("❌ Создание сделки отменено", call.message.chat.id, call.message.message_id)
        if user_id in user_data:
            del user_data[user_id]

# Сохранение сделки в базу
def save_trade_to_db(user_id, trade_data):
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        username = f"@{bot.get_chat(user_id).username}" if bot.get_chat(user_id).username else "Без username"
        
        cursor.execute('''
                       INSERT INTO trades (trade INSERT INTO trades (trade_unique_unique_id, seller_id_id, seller_id,, seller_username, n seller_username, nftft_url, description, price_url, description, price,, currency)
            VALUES (?, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? ?, ?)
        ''',)
        ''', (trade (trade_data['trade_unique_data['trade_unique_id'],_id'], user_id, username user_id, username,
             ,
              trade_data['n trade_data['nft_urlft_url'], trade_data['description'], 
              trade_data'], trade_data['description'], 
              trade_data['price['price'], trade_data[''], trade_data['currency']))
        
currency']))
        
        conn        conn.commit()
        conn.commit()
        conn.close()
.close()
        print(f"        print(f"✅ С✅ Сделка сохранделка сохранена:ена: {trade_data[' {trade_data['trade_uniquetrade_unique_id']}")
   _id']}")
    except Exception except Exception as e as e:
        print(f:
        print(f"❌ О"❌ Ошибкашибка сохранения сделки сохранения сделки: {: {e}")

#e}")

# На Началочало оплаты
@bot.callback_query оплаты
@bot.callback_query_handler(func_handler(func=lambda call: call=lambda call: call.data.start.data.startswith('start_payment_'))
defswith('start_payment_'))
def handle_payment handle_payment_start(call):
    trade_start(call):
    trade_id = int(call_id = int(call.data.split('_')[2])
.data.split('_')[2])
    user_id = call.from_user    user_id = call.from_user.id
    
    try:
        conn = sqlite3.id
    
    try:
        conn = sqlite3.connect('t.connect('trades.dbrades.db',', check check_s_same_thread=False)
ame_thread=False)
        cursor = conn.cursor        cursor = conn.cursor()
        
        cursor.execute()
        
        cursor.execute('SELECT * FROM('SELECT * FROM trades WHERE trades WHERE id = ?', id = ?', (trade (trade_id,))
       _id,))
        trade = trade = cursor.fetchone()
 cursor.fetchone()
               cursor.execute('SELECT * FROM cursor.execute('SELECT * FROM users WHERE user_id = ? users WHERE user_id = ?', (user_id', (user_id,))
        user = cursor,))
        user = cursor.fetchone()
        
        if not trade.fetchone()
        
        if not trade or not user:
            bot or not user:
            bot.answer_callback.answer_callback_query_query(call.id, "(call.id, "❌❌ Ошибка")
 Ошибка")
            conn            conn.close()
            return
        
.close()
            return
        
               (trade_id, (trade_id, trade_unique trade_unique_id, seller_id, seller_id, seller_id, seller_username, 
_username, 
         buyer_id, buyer_username         buyer_id, buyer_username,, nft_url, description, nft_url, description, price, 
         price, 
         currency, status, created_at currency, status, created_at) = trade) = trade
        

        
        user_id        user_id_db, username, rub, us_db, username, rub, usd, byn, kd, byn, kzt, uah, starszt, uah, stars, card, is_admin =, card, is_admin = user
        
        if user_id user
        
        if user_id != buyer_id != buyer_id:
           :
            bot.answer_callback_query(c bot.answer_callback_query(call.idall.id, "❌ Вы не участник, "❌ Вы не участник этой сде этой сделки")
            connлки")
            conn.close()
            return
        
        conn.close.close()
            return
        
        conn.close()
        
        # Проверяем баланс (кроме адми()
        
        # Проверяем баланс (кроме админа)
       на)
        if if not is_admin:
            if not is_admin:
            if currency == 'stars' and stars currency == 'stars' and stars < price:
                bot.send_message < price:
                bot.send_message(user(user_id, f"_id, f"❌ Недостаточно звез❌ Недостаточно звезд. На вашем баланд. На вашем балансесе: {stars}⭐: {stars}⭐")
")
                return
            elif                return
            elif currency currency == 'rub' and == 'rub' and rub rub < price:
 < price:
                               bot.send_message(user_id, f"❌ Не bot.send_message(user_id, f"❌ Недодостаточно рублей. На вашем балансестаточно рублей. На вашем балансе:: {rub}₽")
                return
            elif {rub}₽")
                return
            elif currency currency == 'usd' and usd == 'usd' and usd < price:
                bot < price:
                bot.send_message.send_message(user_id, f"(user_id, f"❌ Недостаточно дол❌ Недостаточно долларов. На валаров. На вашемшем балансе: { балансе: {usdusd}$")
                return}$")
                return

            elif currency == '            elif currency == 'bbyn' and byyn' and bynn < price:
                bot < price:
                bot.send_message.send_message(user_id, f(user_id, f""❌ Недоста❌ Недостаточно BYточно BYN. На ваN. На вашем баланшем балансе: {bсе: {byn}yn} BYN")
                BYN")
                return
            elif currency return
            elif currency == 'kzt' and k == 'kzt' and kzt < price:
                botzt < price:
                bot.send_message(user_id.send_message(user_id,, f"❌ f"❌ Недостаточно тенге Недостаточно тенге.. На вашем балан На вашем балансе:се: {kzt} {kzt}₸₸")
                return
")
                return
                       elif currency == 'u elif currency == 'uahah' and uah' and uah < < price:
 price:
                bot.send                bot.send_message(user_id, f"_message(user_id, f"❌❌ Недостаточно гри Недостаточно гривен. На вавен. На вашем балансешем балансе: {uah}: {uah}₴")
                return
        
        # Показываем методы оплаты
        payment_text₴")
                return
        
        # Показываем методы оплаты
        payment_text = (
            f"💳 = (
            f"💳 *Оплата сделки *Оплата сделки*\n\n"
            f"💰*\n\n"
            f Сумма: {price"💰 Сумма: {price} {CURRENCI} {CURRENCIES[currency]}\nES[currency]}\n"
            f"👤"
            f"👤 Продавец: {seller_ Продавец: {seller_username}\n\n"
        )
        
username}\n\n"
        )
        
               markup = types.Inline markup = types.InlineKeyboardMarkKeyboardMarkup()
        
up()
        
               if currency == 'stars':
            payment_text += " if currency == 'stars':
            payment_text += "⭐ *⭐ *Оплата звездамиОплата звездами:*\:*\nУбедитеnУбедитесь чтось что у вас достаточно звез у вас достаточно звезд над на балансе"
            балансе"
            markup.row markup.row(types.InlineKeyboardButton('⭐(types.InlineKeyboardButton('⭐ Я оплати Я оплатил(а) звездами',л(а) звездами', callback_data=f callback_data=f'confirm_payment_{trade_id}'))
'confirm_payment_{trade_id}'))
        else:
                   else:
            payment_text += f" payment_text += f"💳💳 *Оплата { *Оплата {CCURRENCIESURRENCIES[[currency]}:*\nУcurrency]}:*\nУбедитесь что у васбедитесь что у вас привязана карта привязана карта и достаточно средств"
            markup и достаточно средств"
            markup.row(types.Inline.row(types.InlineKeyboardButton('💳 ЯKeyboardButton('💳 Я оплатил(а) оплатил(а) картой', callback_data=f картой', callback_data=f'confirm_payment_{trade'confirm_payment_{trade_id}'))
        
        bot_id}'))
        
        bot.edit_message_text(payment_text.edit_message_text(payment_text,, call.message.chat call.message.chat.id.id, call.message.message_id, call.message.message_id,, 
                             reply 
                             reply_markup=markup, parse_markup=markup, parse_mode='Markdown')
        
_mode='Markdown')
        
    except Exception as e:
    except Exception as e:
        bot.answer_callback        bot.answer_callback_query(c_query(call.id, "❌ Ошибка оплаall.id, "❌ Ошибка оплаты")

# Мои сдеты")

# Мои сделки
@bot.message_handlerлки
@bot.message_handler(func=lambda message: message.text == '💼 Мои(func=lambda message: message.text == '💼 Мои сделки')
def my_trades(message сделки')
def my_trades(message):
    user_id = message.from_user):
    user_id = message.from_user.id
.id
    try:
           try:
        conn = conn = sqlite3 sqlite3.connect('trades.connect('trades.db',.db', check_same check_same_thread=False_thread=False)
        cursor =)
        cursor = conn.cursor conn.cursor()
        
        #()
        
        # Сде Сделки гделки где пользователь продаве пользователь продавец
        cursorц
        cursor.execute.execute('SELECT * FROM trades WHERE('SELECT * FROM trades WHERE seller_id = seller_id = ? ORDER BY created_at DESC', ? ORDER BY created_at DESC', (user_id (user_id,))
        seller,))
        seller_trades = cursor_trades = cursor.fetchall()
        
.fetchall()
        
        # Сде        # Сделки гделки где пользователь покупатель пользователь покупатель
       
        cursor.execute('SELECT cursor.execute('SELECT * FROM * FROM trades WHERE buyer_id trades WHERE buyer_id = ? = ? ORDER BY created_at ORDER BY created_at DESC', DESC', (user_id, (user_id,))
       ))
        buyer_trades = buyer_trades = cursor.fetch cursor.fetchall()
        
        connall()
        
        conn.close()
.close()
        
        if not seller_trades and        
        if not seller_trades and not buyer not buyer_trades:
            bot.send_message(message.chat.id, "📭 У вас_trades:
            bot.send_message(message.chat.id, "📭 У вас пока нет пока нет сделок")
            return сделок")
            return
        

        
        if seller        if seller_trades:
_trades:
            bot.send_message            bot.send_message(message(message.chat.id, ".chat.id, "🏪🏪 *Сделки *Сделки где вы где вы продавец:* продавец:*", parse_mode='Markdown", parse_mode='Markdown')
            for trade in seller_trades')
            for trade in seller:
                show_t_trades:
                show_trade_info(message.chat.idrade_info(message.chat.id,, trade, 'seller')
 trade, 'seller')
        
        
        if buyer        if buyer_trades:
            bot.send_message(message_trades:
            bot.send_message(message.chat.id,.chat.id, "🛒 "🛒 *Сделки *Сделки где вы где вы покупатель покупатель:*", parse_mode='Markdown')
           :*", parse_mode='Markdown')
            for trade for trade in buyer_trades in buyer_trades:
                show_trade_info(message.ch:
                show_trade_info(message.chat.id, trade, 'buyer')
                
    except Exception as e:
        bot.send_message(message.chatat.id, trade, 'buyer')
                
    except Exception as e:
        bot.send_message(message.chat.id, "❌.id, " Ошибка загрузки сде❌ Ошибка загрузки сделок")

def show_tradeлок")

def show_trade_info(_info(chat_id, tradechat_id, trade, role, role):
    try:
        (trade_id,):
    try:
        (trade_id, trade_unique_id trade_unique_id, seller_id,, seller_id, seller_ seller_username, 
        username, 
         buyer buyer_id,_id, buyer buyer_username_username, nft_url, description, price,, nft_url, description, price, 
         
         currency, status, created_at) currency, status, created_at) = trade = trade
        
        status_
        
        status_emoemoji = {
ji            'waiting_buyer': '⏳',
 = {
            'waiting_buyer':            'waiting_payment': '⏳',
            'waiting_payment': '💳',
            'completed': '💳',
            'completed': '✅',
            '✅',
            'c 'cancelled': 'ancelled': '❌❌'
        }
        
'
        }
        
        text        text = (
            f = (
            f""🎁 *Сде🎁 *Сделка #{лка #{trade_id}*\trade_id}*\n"
n"
            f"💰            f"💰 {price {price} {} {CURRENCIES[CURRENCIES[currency]}\n"
            f"📊currency]}\n"
            f"📊 Стату Статус: {status_с: {status_emoji.getemoji.get(status,(status, '⚡') '⚡')} {status} {status}\n"
}\n"
            f"            f"🕐🕐 {created_at[: {created_at[:1616]}"
       ]}"
        )
        
        if )
        
        if role == role == 'seller' and 'seller' and buyer_username buyer_username:
            text:
            text += += f"\n👤 f"\n👤 Поку Покупатель: {buyпатель: {buyerer_username}"
_username}"
        elif role ==        elif role == 'buyer':
            text 'buyer':
            text += f"\n👤 Пр += f"\n👤 Продавец: {seller_одавец: {seller_username}"
        
        #username}"
        
        # Если это Если это прода продавец ивец и сделка ожидает сделка ожидает покупателя, покупателя, показываем показываем ссылку ссылку
        if role == 'seller' and
        if role == 'seller' and status == 'waiting_buyer':
            join_link = f"https://t.me/{bot.get_me(). status == 'waiting_buyer':
            join_link = f"https://t.me/{bot.get_me().usernameusername}?start=join}?start=join_{_{trade_unique_id}"
           trade_unique_id}"
            text text += f"\n += f"\n🔗🔗 Ссылка: ` Ссылка: `{{joinjoin_link_link}`"
        
        bot.send}`"
        
        bot.send_message_message(chat_id, text, parse_mode='Mark(chat_id, text, parse_mode='Markdowndown')
    except Exception as e:
')
    except Exception as e:
        print(f"❌ Ошиб        print(f"❌ Ошибка показа сделки: {ка показа сделки: {e}")

# Адe}")

# Админ панель
@мин панель
@bot.message_handler(func=lambda messagebot.message_handler(func=lambda message: message.text ==: message.text == ' '🛠️ А🛠️ Админдмин панель' панель' and message and message.from_user.id ==.from_user.id == ADMIN_ID ADMIN_ID)
def admin_p)
def admin_panel(messageanel(message):
    markup =):
    markup = types.In types.InlineKeyboardMarkuplineKeyboardMarkup()
   ()
    markup.row(
        markup.row(
        types.In types.InlineKeyboardButtonlineKeyboardButton('📊('📊 Статисти Статистика', callback_data='admin_statsка', callback_data='admin_stats'),
        types.InlineKeyboardButton(''),
        types.InlineKeyboardButton('👥 Пользователи', callback_data='admin👥 Пользователи', callback_data='admin_users')
_users')
    )
    
    bot    )
    
    bot.send_message(message.chat.id.send_message(message.chat.id,, 
                    " 
                    "🛠🛠️ *Панель️ *Панель администра администратора*\n\n"
тора*\n\n"
                                       "👑 Стату "👑 Статус: АДМИНИс: АДМИНИСТРАСТРАТОР\n"
ТОР\n"
                    "                    "💎 Балан💎 Баланс:с: Безлими Безлимитныйтный\n"
                    "\n"
                    "⚡ Привилегии:⚡ Привилегии: Все операции",
                    reply_m Все операции",
                    reply_markuparkup=markup,=markup, parse_mode='Mark parse_mode='Markdown')

@bot.message_handler(commands=['testdown')

@bot.message_handler(commands'])
def send_test=['test'])
def send_test(message):
    bot(message):
    bot.reply_to(message.reply_to(message, "✅ Б, "✅ Бот работаетот работает!")

# За!")

# Запускпуск бота
if __name__ == "__main бота
if __name__ == "__main__":
   __":
    print("🤖 Запуск NFT Trade print("🤖 Запуск NFT Trade Bot...")
    print(f Bot...")
    print(f"👑 Админ"👑 Админ ID: { ID: {ADMIN_IDADMIN_ID}")
    
}")
    
    # Ини    # Инициализируциализируем БД
    if initем БД
    if init_db():
_db():
        print("✅        print("✅ Бот Бот запущен!")
        
 запущен!")
        
        # Останавливаем        # Останавливаем предыду предыдущие соединения
        tryщие соединения
        try:
            bot.remove:
            bot.remove_web_webhook()
            time.sleephook()
            time.sleep(1)
        except:
           (1)
        except:
            pass
        
        try:
 pass
        
        try:
                       bot.infinity_p bot.infinity_pollingolling()
        except Exception()
        except Exception as e as e:
           :
            print print(f"❌(f"❌ Ошибка: {e}")
    else Ошибка: {e}")
    else:
        print:
        print("❌ Не удалось запустить("❌ Не удалось запустить бота бота")


