import os
import telebot

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 6540509823  # ЗАМЕНИТЕ НА ВАШ ID

bot = telebot.TeleBot(BOT_TOKEN)

# Главное меню
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if message.from_user.id == ADMIN_ID:
        markup.row('🎁 Магазин NFT', '💼 Сделки')
        markup.row('🛠️ Админ панель')
    else:
        markup.row('🎁 Магазин NFT', '💼 Мои сделки')
    
    bot.send_message(message.chat.id, "👋 Выберите действие:", reply_markup=markup)

# Админ панель
@bot.message_handler(func=lambda message: message.text == '🛠️ Админ панель' and message.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton('📊 Статистика', callback_data='stats'),
        telebot.types.InlineKeyboardButton('🎁 Управление NFT', callback_data='manage_nft')
    )
    markup.row(
        telebot.types.InlineKeyboardButton('👥 Пользователи', callback_data='users'),
        telebot.types.InlineKeyboardButton('💼 Все сделки', callback_data='all_trades')
    )
    
    bot.send_message(message.chat.id, 
                    "🛠️ *Панель администратора*\n\n"
                    "📊 Ваша статистика:\n"
                    "• Сделок: 1423\n"
                    "• Рейтинг: 5.0/5 ⭐⭐⭐⭐⭐\n"
                    "💎 Баланс: Безлимитный\n\n"
                    "Выберите раздел:",
                    reply_markup=markup, parse_mode='Markdown')

# Обработка кнопок админки
@bot.callback_query_handler(func=lambda call: True)
def handle_admin_buttons(call):
    if call.data == 'stats':
        bot.edit_message_text(
            "📊 *Статистика системы*\n\n"
            "👥 Пользователей: 15\n"
            "🎁 NFT товаров: 7\n"
            "💼 Активных сделок: 3\n"
            "💰 Общий оборот: 12,450₽\n\n"
            "🛠️ Управление через админ панель",
            call.message.chat.id, call.message.message_id, parse_mode='Markdown'
        )
    elif call.data == 'manage_nft':
        bot.edit_message_text(
            "🎁 *Управление NFT товарами*\n\n"
            "Добавьте новый NFT товар командой:\n"
            "`/add_nft название цена описание`\n\n"
            "Пример:\n"
            "`/add_nft Золотой_медальон 1500 Эксклюзивный_NFT`",
            call.message.chat.id, call.message.message_id, parse_mode='Markdown'
        )
    else:
        bot.answer_callback_query(call.id, "⚙️ Функция в разработке")

# Команда для добавления NFT (только для админа)
@bot.message_handler(commands=['add_nft'])
def add_nft(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Только администратор может добавлять NFT")
        return
    
    # Здесь будет логика добавления NFT
    bot.reply_to(message, "✅ NFT товар добавлен в магазин!")

@bot.message_handler(commands=['test'])
def send_test(message):
    bot.reply_to(message, "✅ Тестовая команда работает!")

if __name__ == "__main__":
    print("🚀 Бот запущен с админ панелью!")
    print("✅ Админ ID:", ADMIN_ID)
    bot.infinity_polling()