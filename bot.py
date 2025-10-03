import os
from telegram import Update
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.getenv('BOT_TOKEN')

async def start(update: Update, context):
    await update.message.reply_text("🎉 Бот работает! Привет!")

async def test(update: Update, context):
    await update.message.reply_text("✅ Тестовая команда работает!")

def main():
    print("🚀 Запуск простого бота...")
    
    if not BOT_TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    
    print("✅ Бот запущен и готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
