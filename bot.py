import os
import telebot

BOT_TOKEN = os.getenv('BOT_TOKEN')

# Создаем бота
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎉 Бот работает! Привет!")

@bot.message_handler(commands=['test'])
def send_test(message):
    bot.reply_to(message, "✅ Тестовая команда работает!")

@bot.message_handler(commands=['admin'])
def send_admin(message):
    if message.from_user.id == 6540509823:  # ЗАМЕНИТЕ НА ВАШ ID
        bot.reply_to(message, "🛠️ Панель администратора открыта!")
    else:
        bot.reply_to(message, "❌ Нет доступа к админ панели")

if __name__ == "__main__":
    print("🚀 Запуск бота на pyTelegramBotAPI...")
    print("✅ Бот запущен и слушает сообщения...")
    bot.infinity_polling()