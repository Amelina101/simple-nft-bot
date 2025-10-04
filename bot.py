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
    
    # ПРОВЕРЯЕМ ССЫЛКУ ПРИСОЕДИНЕНИЯ
    if len(message.text.split()) > 1:
        command_parts = message.text.split()
        if len(command_parts) >= 2:
            param = command_parts[1]
            if param.startswith('join_'):
                trade_unique_id = param.replace('join_', '')
                print(f"🔗 Попытка присоединения к сделке: {trade_unique_id}")
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
    
    print(f"🔄 Обработка присоединения: пользователь {user_id} к сделке {trade_unique_id}")
    
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Находим сделку
        cursor.execute('SELECT * FROM trades WHERE trade_unique_id = ?', (trade_unique_id,))
        trade = cursor.fetchone()
        
        if not trade:
            print(f"❌ Сделка {trade_unique_id} не найдена")
            bot.send_message(message.chat.id, "❌ Сделка не найдена или устарела")
            conn.close()
            return
        
        # Распаковываем данные сделки
        (trade_id, trade_unique_id_db, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        print(f"📊 Найдена сделка: ID {trade_id}, продавец {seller_id}, покупатель {buyer_id}")
        
        # Проверяем не является ли пользователь продавцом
        if user_id == seller_id:
            print(f"❌ Пользователь {user_id} пытается присоединиться к своей сделке")
            bot.send_message(message.chat.id, 
                           "❌ Вы не можете присоединиться к своей собственной сделке!\n\n"
                           "💡 Отправьте эту ссылку другому человеку для покупки.")
            conn.close()
            return
        
        # Проверяем нет ли уже покупателя
        if buyer_id is not None:
            print(f"❌ В сделке {trade_id} уже есть покупатель {buyer_id}")
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
        
        print(f"✅ Пользователь {user_id} успешно присоединился к сделке {trade_id}")
        
        # УВЕДОМЛЕНИЕ ДЛЯ ПОКУПАТЕЛЯ
        buyer_message = (
            "✅ Вы присоединились к сделке!\n\n"
            f"👤 Продавец: {seller_username}\n"
            f"🎁 NFT: {nft_url}\n"
            f"📝 Описание: {description}\n"
            f"💰 Цена: {price} {CURRENCIES[currency]}\n\n"
            "💡 Для завершения сделки необходимо перейти к оплате"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton('💳 Перейти к оплате', callback_data=f'start_payment_{trade_id}'))
        markup.row(types.InlineKeyboardButton('❌ Отменить сделку', callback_data=f'cancel_trade_buyer_{trade_id}'))
        
        bot.send_message(user_id, buyer_message, reply_markup=markup)
        
        # УВЕДОМЛЕНИЕ ДЛЯ ПРОДАВЦА
        seller_message = (
            "🎉 Покупатель присоединился к вашей сделке!\n\n"
            f"👤 Покупатель: {username}\n"
            f"💰 Сумма: {price} {CURRENCIES[currency]}\n\n"
            "⏳ Ожидайте оплаты от покупателя..."
        )
        
        markup_seller = types.InlineKeyboardMarkup()
        markup_seller.row(types.InlineKeyboardButton('❌ Отменить сделку', callback_data=f'cancel_trade_seller_{trade_id}'))
        
        bot.send_message(seller_id, seller_message, reply_markup=markup_seller)
        
    except Exception as e:
        print(f"❌ Ошибка присоединения: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка присоединения к сделке")

# ФУНКЦИЯ ОТМЕНЫ СДЕЛКИ
@bot.callback_query_handler(func=lambda call: call.data.startswith(('cancel_trade_seller_', 'cancel_trade_buyer_')))
def handle_trade_cancellation(call):
    data_parts = call.data.split('_')
    user_type = data_parts[2]  # seller или buyer
    trade_id = int(data_parts[3])
    user_id = call.from_user.id
    
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Получаем информацию о сделке
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена")
            conn.close()
            return
        
        (trade_id, trade_unique_id, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        # Проверяем права пользователя на отмену
        if user_type == 'seller' and user_id != seller_id:
            bot.answer_callback_query(call.id, "❌ Только продавец может отменить сделку")
            conn.close()
            return
        elif user_type == 'buyer' and user_id != buyer_id:
            bot.answer_callback_query(call.id, "❌ Только покупатель может отменить сделку")
            conn.close()
            return
        
        # Обновляем статус сделки
        cursor.execute('UPDATE trades SET status = ? WHERE id = ?', ('cancelled', trade_id))
        conn.commit()
        conn.close()
        
        # Уведомление об отмене
        if user_type == 'seller':
            cancel_reason = "продавцом"
            # Уведомляем покупателя
            if buyer_id:
                bot.send_message(buyer_id, 
                               f"❌ Сделка отменена продавцом\n\n"
                               f"🎁 Сделка #{trade_id}\n"
                               f"💰 {price} {CURRENCIES[currency]}\n\n"
                               f"💡 Продавец отменил сделку. Средства не были списаны.")
        else:  # buyer
            cancel_reason = "покупателем"
            # Уведомляем продавца
            bot.send_message(seller_id, 
                           f"❌ Сделка отменена покупателем\n\n"
                           f"🎁 Сделка #{trade_id}\n"
                           f"💰 {price} {CURRENCIES[currency]}\n\n"
                           f"💡 Покупатель отменил сделку.")
        
        # Уведомление инициатору отмены
        bot.edit_message_text(
            f"✅ Сделка успешно отменена\n\n"
            f"🎁 Сделка #{trade_id}\n"
            f"💰 {price} {CURRENCIES[currency]}\n\n"
            f"💡 Сделка отменена {cancel_reason}",
            call.message.chat.id, call.message.message_id
        )
        
        print(f"✅ Сделка {trade_id} отменена {user_type} {user_id}")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка отмены сделки")
        print(f"❌ Ошибка отмены сделки: {e}")

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
                f"💰 Ваш баланс:\n\n"
                f"⭐ Звезды: {stars}\n"
                f"🇷🇺 RUB: {rub}\n"
                f"🇺🇸 USD: {usd}\n"
                f"🇧🇾 BYN: {byn}\n"
                f"🇰🇿 KZT: {kzt}\n"
                f"🇺🇦 UAH: {uah}\n\n"
            )
            
            if card:
                balance_text += f"💳 Привязанная карта: {card}\n\n"
            
            if is_admin:
                balance_text += "👑 Статус: АДМИНИСТРАТОР\n💎 Баланс: Безлимитный"
            else:
                balance_text += "💡 Для пополнения баланса используйте команду /deposit"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton('💳 Привязать карту', callback_data='bind_card'),
                types.InlineKeyboardButton('⭐ Пополнить звезды', callback_data='add_stars')
            )
            
            bot.send_message(message.chat.id, balance_text, reply_markup=markup)
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
                    "🎁 Создание новой сделки\n\n"
                    "💵 Выберите валюту для оплаты:",
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
                         f"✅ Валюта: {CURRENCIES[currency_code]}\n\n"
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
        "🎁 Превью сделки:\n\n"
        f"📎 NFT: {trade_data['nft_url']}\n"
        f"📝 Описание: {trade_data['description']}\n"
        f"💰 Цена: {trade_data['price']} {trade_data['currency_display']}\n\n"
        "Всё верно?"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('✅ Подтвердить', callback_data='confirm_trade'),
        types.InlineKeyboardButton('❌ Отменить', callback_data='cancel_trade_creation')
    )
    
    bot.send_message(chat_id, preview_text, reply_markup=markup)

# Отмена создания сделки
@bot.callback_query_handler(func=lambda call: call.data == 'cancel_trade_creation')
def cancel_trade_creation(call):
    user_id = call.from_user.id
    bot.edit_message_text("❌ Создание сделки отменено", call.message.chat.id, call.message.message_id)
    if user_id in user_data:
        del user_data[user_id]

# Подтверждение сделки
@bot.callback_query_handler(func=lambda call: call.data == 'confirm_trade')
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
            "✅ Сделка успешно создана!\n\n"
            f"🎁 Ссылка для присоединения:\n"
            f"{join_link}\n\n"
            f"📎 NFT: {user_data[user_id]['nft_url']}\n"
            f"💰 Цена: {user_data[user_id]['price']} {user_data[user_id]['currency_display']}\n\n"
            f"💡 Отправьте эту ссылку покупателю\n"
            f"❌ Вы не можете присоединиться к своей сделке"
        )
        
        bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id)
        
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
            INSERT INTO trades (trade_unique_id, seller_id, seller_username, nft_url, description, price, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (trade_data['trade_unique_id'], user_id, username,
              trade_data['nft_url'], trade_data['description'], 
              trade_data['price'], trade_data['currency']))
        
        conn.commit()
        conn.close()
        print(f"✅ Сделка сохранена: {trade_data['trade_unique_id']}")
    except Exception as e:
        print(f"❌ Ошибка сохранения сделки: {e}")

# НОВАЯ ФУНКЦИЯ: Проверка и списание звезд
def process_stars_payment(trade_id, buyer_id):
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Получаем информацию о сделке и покупателе
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (buyer_id,))
        user = cursor.fetchone()
        
        if not trade or not user:
            conn.close()
            return False, "❌ Ошибка данных"
        
        (trade_id, trade_unique_id, seller_id, seller_username, 
         buyer_id_db, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        user_id_db, username, rub, usd, byn, kzt, uah, stars, card, is_admin = user
        
        # Проверяем что покупатель совпадает
        if buyer_id != buyer_id_db:
            conn.close()
            return False, "❌ Несоответствие пользователя"
        
        # Если пользователь не админ - проверяем и списываем звезды
        if not is_admin:
            if stars < price:
                conn.close()
                return False, f"❌ Недостаточно звезд. На вашем балансе: {stars}⭐"
            
            # Списание звезд у покупателя
            new_stars = stars - price
            cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_stars, buyer_id))
            
            # Начисление звезд продавцу (если продавец не админ)
            cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (seller_id,))
            seller_is_admin = cursor.fetchone()[0]
            
            if not seller_is_admin:
                cursor.execute('SELECT stars FROM users WHERE user_id = ?', (seller_id,))
                seller_stars = cursor.fetchone()[0]
                new_seller_stars = seller_stars + price
                cursor.execute('UPDATE users SET stars = ? WHERE user_id = ?', (new_seller_stars, seller_id))
        
        # Обновляем статус сделки
        cursor.execute('UPDATE trades SET status = ? WHERE id = ?', ('waiting_delivery', trade_id))
        
        conn.commit()
        conn.close()
        
        return True, "✅ Оплата прошла успешно!"
        
    except Exception as e:
        print(f"❌ Ошибка обработки оплаты: {e}")
        return False, "❌ Ошибка обработки оплаты"

# Начало оплаты
@bot.callback_query_handler(func=lambda call: call.data.startswith('start_payment_'))
def handle_payment_start(call):
    trade_id = int(call.data.split('_')[2])
    user_id = call.from_user.id
    
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not trade or not user:
            bot.answer_callback_query(call.id, "❌ Ошибка")
            conn.close()
            return
        
        (trade_id, trade_unique_id, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
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
            f"💳 Оплата сделки\n\n"
            f"💰 Сумма: {price} {CURRENCIES[currency]}\n"
            f"👤 Продавец: {seller_username}\n\n"
        )
        
        markup = types.InlineKeyboardMarkup()
        
        if currency == 'stars':
            if is_admin:
                payment_text += "👑 АДМИН ОПЛАТА:\nУ вас безлимитные звезды!"
            else:
                payment_text += f"⭐ Оплата звездами:\nНа вашем балансе: {stars}⭐\nБудет списано: {price}⭐"
            
            markup.row(types.InlineKeyboardButton('⭐ Я оплатил(а) звездами', callback_data=f'confirm_payment_{trade_id}'))
        else:
            payment_text += f"💳 Оплата {CURRENCIES[currency]}:\nУбедитесь что у вас привязана карта и достаточно средств"
            markup.row(types.InlineKeyboardButton('💳 Я оплатил(а) картой', callback_data=f'confirm_payment_{trade_id}'))
        
        markup.row(types.InlineKeyboardButton('❌ Отменить сделку', callback_data=f'cancel_trade_buyer_{trade_id}'))
        
        bot.edit_message_text(payment_text, call.message.chat.id, call.message.message_id, 
                             reply_markup=markup)
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка оплаты")

# НОВЫЙ ОБРАБОТЧИК: Подтверждение оплаты звездами
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_payment_'))
def handle_payment_confirmation(call):
    trade_id = int(call.data.split('_')[2])
    user_id = call.from_user.id
    
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена")
            conn.close()
            return
        
        (trade_id, trade_unique_id, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        if user_id != buyer_id:
            bot.answer_callback_query(call.id, "❌ Вы не участник этой сделки")
            conn.close()
            return
        
        conn.close()
        
        # Обрабатываем оплату
        if currency == 'stars':
            success, message = process_stars_payment(trade_id, user_id)
            
            if success:
                # Уведомление покупателю
                buyer_message = (
                    "✅ Оплата прошла успешно!\n\n"
                    f"💰 Сумма: {price} {CURRENCIES[currency]}\n"
                    f"👤 Продавец: {seller_username}\n\n"
                    "⏳ Ожидайте получения NFT подарка от продавца"
                )
                
                bot.edit_message_text(buyer_message, call.message.chat.id, call.message.message_id)
                
                # УВЕДОМЛЕНИЕ ПРОДАВЦУ О ПОЛУЧЕНИИ ОПЛАТЫ
                seller_message = (
                    "💰 Получена оплата за сделку!\n\n"
                    f"👤 Покупатель: {buyer_username}\n"
                    f"🎁 NFT: {nft_url}\n"
                    f"📝 Описание: {description}\n"
                    f"💰 Сумма: {price} {CURRENCIES[currency]}\n\n"
                    "💡 Пожалуйста, переведите NFT подарок покупателю и подтвердите доставку"
                )
                
                markup_seller = types.InlineKeyboardMarkup()
                markup_seller.row(
                    types.InlineKeyboardButton('✅ Я перевел(а) подарок', callback_data=f'confirm_delivery_{trade_id}')
                )
                
                bot.send_message(seller_id, seller_message, reply_markup=markup_seller)
                
            else:
                bot.answer_callback_query(call.id, message)
                bot.send_message(user_id, message)
        
        else:
            # Для других валют (пока заглушка)
            bot.answer_callback_query(call.id, "⏳ Оплата другими валютами в разработке")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка подтверждения оплаты")
        print(f"❌ Ошибка подтверждения оплаты: {e}")

# НОВЫЙ ОБРАБОТЧИК: Подтверждение доставки подарка продавцом
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delivery_'))
def handle_delivery_confirmation(call):
    trade_id = int(call.data.split('_')[2])
    user_id = call.from_user.id
    
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена")
            conn.close()
            return
        
        (trade_id, trade_unique_id, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        if user_id != seller_id:
            bot.answer_callback_query(call.id, "❌ Только продавец может подтвердить доставку")
            conn.close()
            return
        
        # Обновляем статус сделки на завершенный
        cursor.execute('UPDATE trades SET status = ? WHERE id = ?', ('completed', trade_id))
        conn.commit()
        conn.close()
        
        # Уведомление продавцу
        seller_message = (
            "✅ Сделка завершена!\n\n"
            f"🎁 Сделка #{trade_id} успешно завершена\n"
            f"💰 Вы получили: {price} {CURRENCIES[currency]}\n"
            f"👤 Покупатель: {buyer_username}\n\n"
            "💖 Спасибо за использование нашего сервиса!"
        )
        
        bot.edit_message_text(seller_message, call.message.chat.id, call.message.message_id)
        
        # Уведомление покупателю
        buyer_message = (
            "🎉 Сделка завершена!\n\n"
            f"🎁 Сделка #{trade_id} успешно завершена\n"
            f"👤 Продавец: {seller_username}\n"
            f"📎 NFT: {nft_url}\n\n"
            "💖 Наслаждайтесь вашим NFT подарком!\n"
            "⭐ Спасибо за использование нашего сервиса!"
        )
        
        bot.send_message(buyer_id, buyer_message)
        
        print(f"✅ Сделка {trade_id} завершена")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка подтверждения доставки")
        print(f"❌ Ошибка подтверждения доставки: {e}")

# Мои сделки - ОБНОВЛЕННАЯ ВЕРСИЯ С КНОПКАМИ ОТМЕНЫ
@bot.message_handler(func=lambda message: message.text == '💼 Мои сделки')
def my_trades(message):
    user_id = message.from_user.id
    try:
        conn = sqlite3.connect('trades.db', check_same_thread=False)
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
            bot.send_message(message.chat.id, "🏪 Сделки где вы продавец:")
            for trade in seller_trades:
                show_trade_info(message.chat.id, trade, 'seller', user_id)
        
        if buyer_trades:
            bot.send_message(message.chat.id, "🛒 Сделки где вы покупатель:")
            for trade in buyer_trades:
                show_trade_info(message.chat.id, trade, 'buyer', user_id)
                
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки сделок")

def show_trade_info(chat_id, trade, role, user_id):
    try:
        (trade_id, trade_unique_id, seller_id, seller_username, 
         buyer_id, buyer_username, nft_url, description, price, 
         currency, status, created_at) = trade
        
        status_emoji = {
            'waiting_buyer': '⏳',
            'waiting_payment': '💳',
            'waiting_delivery': '📦',
            'completed': '✅',
            'cancelled': '❌'
        }
        
        text = (
            f"🎁 Сделка #{trade_id}\n"
            f"💰 {price} {CURRENCIES[currency]}\n"
            f"📊 Статус: {status_emoji.get(status, '⚡')} {status}\n"
            f"🕐 {created_at[:16]}"
        )
        
        if role == 'seller' and buyer_username:
            text += f"\n👤 Покупатель: {buyer_username}"
        elif role == 'buyer':
            text += f"\n👤 Продавец: {seller_username}"
        
        markup = types.InlineKeyboardMarkup()
        
        # Добавляем кнопки в зависимости от статуса и роли
        if status == 'waiting_delivery' and role == 'seller':
            markup.row(types.InlineKeyboardButton('✅ Я перевел(а) подарок', callback_data=f'confirm_delivery_{trade_id}'))
        elif status in ['waiting_buyer', 'waiting_payment']:
            if role == 'seller':
                markup.row(types.InlineKeyboardButton('❌ Отменить сделку', callback_data=f'cancel_trade_seller_{trade_id}'))
            elif role == 'buyer':
                markup.row(types.InlineKeyboardButton('❌ Отменить сделку', callback_data=f'cancel_trade_buyer_{trade_id}'))
        
        # Если это продавец и сделка ожидает покупателя, показываем ссылку
        if role == 'seller' and status == 'waiting_buyer':
            join_link = f"https://t.me/{bot.get_me().username}?start=join_{trade_unique_id}"
            text += f"\n🔗 Ссылка: {join_link}"
        
        bot.send_message(chat_id, text, reply_markup=markup)
    except Exception as e:
        print(f"❌ Ошибка показа сделки: {e}")

# Админ панель
@bot.message_handler(func=lambda message: message.text == '🛠️ Админ панель' and message.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('📊 Статистика', callback_data='admin_stats'),
        types.InlineKeyboardButton('👥 Пользователи', callback_data='admin_users')
    )
    
    bot.send_message(message.chat.id, 
                    "🛠️ Панель администратора\n\n"
                    "👑 Статус: АДМИНИСТРАТОР\n"
                    "💎 Баланс: Безлимитный\n"
                    "⚡ Привилегии: Все операции",
                    reply_markup=markup)

@bot.message_handler(commands=['test'])
def send_test(message):
    bot.reply_to(message, "✅ Бот работает!")

# Запуск бота
if __name__ == "__main__":
    print("🤖 Запуск NFT Trade Bot...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    
    # Инициализируем БД
    if init_db():
        print("✅ Бот запущен!")
        
        # Останавливаем предыдущие соединения
        try:
            bot.remove_webhook()
            time.sleep(1)
        except:
            pass
        
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    else:
        print("❌ Не удалось запустить бота")


