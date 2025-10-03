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

# База данных для хранения сделок
def init_db():
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    # Таблица сделок
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
    
    # Таблица участников сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            user_id INTEGER,
            user_username TEXT,
            status TEXT DEFAULT 'joined',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trade_id) REFERENCES trades (id)
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
                    "👥 Приглашайте участников по ссылкам\n"
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
        # Генерируем уникальный ID для сделки
        trade_unique_id = generate_trade_id()
        user_data[user_id]['trade_unique_id'] = trade_unique_id
        
        # Сохраняем сделку в базу данных
        save_trade_to_db(user_id, user_data[user_id])
        
        # Создаем ссылку для присоединения
        trade_link = f"https://t.me/{bot.get_me().username}?start=join_{trade_unique_id}"
        
        trade_data = user_data[user_id]
        success_text = (
            "✅ *Сделка успешно создана!*\n\n"
            f"🎁 NFT: {trade_data['nft_url']}\n"
            f"📝 Описание: {trade_data['description']}\n"
            f"💰 Цена: {trade_data['price']} {trade_data['currency']}\n\n"
            f"🔗 *Ссылка для присоединения:*\n`{trade_link}`\n\n"
            "Отправьте эту ссылку участнику для присоединения к сделке!"
        )
        
        bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        # Очищаем временные данные
        if user_id in user_data:
            del user_data[user_id]
            
    else:  # cancel_trade
        bot.edit_message_text("❌ Создание сделки отменено", call.message.chat.id, call.message.message_id)
        if user_id in user_data:
            del user_data[user_id]

# Сохранение сделки в базу данных
def save_trade_to_db(user_id, trade_data):
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO trades (trade_unique_id, user_id, user_username, nft_url, description, price, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (trade_data['trade_unique_id'], user_id, 
          f"@{bot.get_chat(user_id).username}" if bot.get_chat(user_id).username else "Без username",
          trade_data['nft_url'], trade_data['description'], 
          trade_data['price'], trade_data['currency']))
    
    conn.commit()
    conn.close()

# Обработка ссылок для присоединения
@bot.message_handler(commands=['start'])
def handle_start_with_join(message):
    if len(message.text.split()) > 1:
        command = message.text.split()[1]
        if command.startswith('join_'):
            trade_unique_id = command.split('_')[1]
            join_trade(message, trade_unique_id)
        else:
            send_welcome(message)
    else:
        send_welcome(message)

# Присоединение к сделке
def join_trade(message, trade_unique_id):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Без username"
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    # Находим сделку
    cursor.execute('SELECT * FROM trades WHERE trade_unique_id = ?', (trade_unique_id,))
    trade = cursor.fetchone()
    
    if not trade:
        bot.send_message(message.chat.id, "❌ Сделка не найдена или устарела")
        conn.close()
        return
    
    trade_id, trade_unique_id, creator_id, creator_username, nft_url, description, price, currency, status, created_at = trade
    
    # Проверяем не является ли пользователь создателем
    if user_id == creator_id:
        bot.send_message(message.chat.id, "❌ Вы не можете присоединиться к своей собственной сделке")
        conn.close()
        return
    
    # Проверяем не присоединился ли уже
    cursor.execute('SELECT * FROM trade_participants WHERE trade_id = ? AND user_id = ?', (trade_id, user_id))
    existing_participant = cursor.fetchone()
    
    if existing_participant:
        bot.send_message(message.chat.id, "❌ Вы уже присоединились к этой сделке")
        conn.close()
        return
    
    # Добавляем участника
    cursor.execute('''
        INSERT INTO trade_participants (trade_id, user_id, user_username)
        VALUES (?, ?, ?)
    ''', (trade_id, user_id, username))
    
    conn.commit()
    conn.close()
    
    # Уведомление для присоединившегося
    bot.send_message(message.chat.id,
                    f"✅ *Вы присоединились к сделке!*\n\n"
                    f"🎁 NFT: {nft_url}\n"
                    f"📝 Описание: {description}\n"
                    f"💰 Цена: {price} {currency}\n\n"
                    f"👤 *Создатель сделки:* {creator_username}\n\n"
                    "Ожидайте подтверждения от создателя сделки!")
    
    # Уведомление для создателя сделки
    bot.send_message(creator_id,
                    f"🎉 *Новый участник присоединился к вашей сделке!*\n\n"
                    f"👤 *Участник:* {username}\n"
                    f"🆔 ID: `{user_id}`\n\n"
                    f"🎁 *Детали сделки:*\n"
                    f"• NFT: {nft_url}\n"
                    f"• Описание: {description}\n"
                    f"• Цена: {price} {currency}\n\n"
                    "✅ *Подтвердите, что это правильный участник:*",
                    parse_mode='Markdown')
    
    # Кнопки подтверждения для создателя
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('✅ Подтвердить участника', callback_data=f'confirm_participant_{trade_id}_{user_id}'),
        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_participant_{trade_id}_{user_id}')
    )
    
    bot.send_message(creator_id, f"Подтверждаете участника {username}?", reply_markup=markup)

# Подтверждение участника создателем сделки
@bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_participant_', 'reject_participant_')))
def handle_participant_confirmation(call):
    data_parts = call.data.split('_')
    action = data_parts[1]
    trade_id = int(data_parts[2])
    participant_id = int(data_parts[3])
    
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    # Получаем информацию об участнике
    cursor.execute('SELECT user_username FROM trade_participants WHERE trade_id = ? AND user_id = ?', 
                   (trade_id, participant_id))
    participant = cursor.fetchone()
    
    if not participant:
        bot.answer_callback_query(call.id, "❌ Участник не найден")
        conn.close()
        return
    
    participant_username = participant[0]
    
    if action == 'confirm':
        # Обновляем статус участника
        cursor.execute('UPDATE trade_participants SET status = ? WHERE trade_id = ? AND user_id = ?',
                      ('confirmed', trade_id, participant_id))
        
        conn.commit()
        conn.close()
        
        # Уведомление для создателя
        bot.edit_message_text(f"✅ Участник {participant_username} подтвержден!",
                            call.message.chat.id, call.message.message_id)
        
        # Уведомление для участника
        bot.send_message(participant_id,
                        f"🎉 *Ваше участие в сделке подтверждено!*\n\n"
                        f"👤 Создатель сделки подтвердил вас как участника.\n\n"
                        "Теперь вы можете переходить к оплате и завершению сделки!")
        
    else:  # reject
        # Удаляем участника
        cursor.execute('DELETE FROM trade_participants WHERE trade_id = ? AND user_id = ?',
                      (trade_id, participant_id))
        
        conn.commit()
        conn.close()
        
        # Уведомление для создателя
        bot.edit_message_text(f"❌ Участник {participant_username} отклонен",
                            call.message.chat.id, call.message.message_id)
        
        # Уведомление для участника
        bot.send_message(participant_id,
                        "❌ Создатель сделки отклонил ваше участие.\n"
                        "Возможно, это ошибка или сделка уже закрыта.")

# Мои сделки (созданные)
@bot.message_handler(func=lambda message: message.text == '💼 Мои сделки')
def my_trades(message):
    conn = sqlite3.connect('trades.db')
    cursor = conn.cursor()
    
    # Сделки созданные пользователем
    cursor.execute('SELECT * FROM trades WHERE user_id = ? ORDER BY created_at DESC', (message.from_user.id,))
    created_trades = cursor.fetchall()
    
    # Сделки где пользователь участник
    cursor.execute('''
        SELECT t.* FROM trades t
        JOIN trade_participants tp ON t.id = tp.trade_id
        WHERE tp.user_id = ? ORDER BY tp.joined_at DESC
    ''', (message.from_user.id,))
    joined_trades = cursor.fetchall()
    
    conn.close()
    
    if not created_trades and not joined_trades:
        bot.send_message(message.chat.id, "📭 У вас пока нет сделок")
        return
    
    # Показываем созданные сделки
    if created_trades:
        bot.send_message(message.chat.id, "🏪 *Созданные вами сделки:*", parse_mode='Markdown')
        
        for trade in created_trades:
            trade_id, trade_unique_id, user_id, username, nft_url, description, price, currency, status, created_at = trade
            
            # Получаем количество участников
            conn = sqlite3.connect('trades.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM trade_participants WHERE trade_id = ?', (trade_id,))
            participants_count = cursor.fetchone()[0]
            conn.close()
            
            trade_link = f"https://t.me/{bot.get_me().username}?start=join_{trade_unique_id}"
            
            trade_text = (
                f"🎁 *Сделка #{trade_id}*\n\n"
                f"📎 NFT: {nft_url}\n"
                f"📝 Описание: {description}\n"
                f"💰 Цена: {price} {currency}\n"
                f"👥 Участников: {participants_count}\n"
                f"📊 Статус: {status}\n"
                f"🔗 Ссылка: `{trade_link}`\n"
                f"🕐 Создана: {created_at[:16]}"
            )
            
            bot.send_message(message.chat.id, trade_text, parse_mode='Markdown')
    
    # Показываем сделки где пользователь участник
    if joined_trades:
        bot.send_message(message.chat.id, "🤝 *Сделки где вы участник:*", parse_mode='Markdown')
        
        for trade in joined_trades:
            trade_id, trade_unique_id, creator_id, creator_username, nft_url, description, price, currency, status, created_at = trade
            
            # Получаем статус участника
            conn = sqlite3.connect('trades.db')
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM trade_participants WHERE trade_id = ? AND user_id = ?', 
                          (trade_id, message.from_user.id))
            participant_status = cursor.fetchone()[0]
            conn.close()
            
            trade_text = (
                f"🎁 *Сделка #{trade_id}*\n\n"
                f"📎 NFT: {nft_url}\n"
                f"📝 Описание: {description}\n"
                f"💰 Цена: {price} {currency}\n"
                f"👤 Создатель: {creator_username}\n"
                f"✅ Ваш статус: {participant_status}\n"
                f"🕐 Присоединились: {created_at[:16]}"
            )
            
            bot.send_message(message.chat.id, trade_text, parse_mode='Markdown')

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




