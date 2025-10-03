import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

BOT_TOKEN = os.getenv('BOT_TOKEN')

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🎉 Бот работает! Привет!")

def test(update: Update, context: CallbackContext):
    update.message.reply_text("✅ Тестовая команда работает!")

def main():
    print("🚀 Запуск простого бота...")
    
    if not BOT_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден")
        return
    
    # Используем Updater для версии 13.15
    updater = Updater(BOT_TOKEN, use_context=True)
    
    # Получаем диспетчер
    dp = updater.dispatcher
    
    # Регистрируем команды
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("test", test))
    
    # Запускаем бота
    print("✅ Бот запущен и готов к работе!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()