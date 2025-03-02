import nest_asyncio
nest_asyncio.apply()

from dotenv import load_dotenv
import os
load_dotenv("secret.env")

from telegram import Update, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, PreCheckoutQueryHandler
import requests

# Загружаем токены из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CARFAX_API_KEY = os.getenv("CARFAX_API_KEY")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
CARFAX_PRICE = 500

# ✅ Проверяем VIN
async def check_vin(update: Update, context: CallbackContext) -> None:
    vin = update.message.text.strip().upper()
    if len(vin) != 17:
        await update.message.reply_text("❌ Ошибка! VIN должен содержать **17 символов**.")
        return
    await update.message.reply_text("🔍 Проверяю VIN...")
    url = f"https://carfax-report.online/api.php?vin={vin}"
    response = requests.get(url)
    if response.status_code == 200:
        await update.message.reply_text(
            f"✅ VIN найден! 🚗\n\n💰 Стоимость отчёта: **$5.00**\n\nНажми /buy, чтобы купить."
        )
        context.user_data["vin"] = vin  # Сохраняем VIN для оплаты
    else:
        await update.message.reply_text("❌ VIN не найден. Проверь данные и попробуй снова.")

# 💳 Покупка отчёта
async def buy(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    vin = context.user_data.get("vin")
    if not vin:
        await update.message.reply_text("⚠️ Сначала отправь VIN для проверки!")
        return
    title = "Carfax Отчёт"
    description = f"Отчёт по VIN {vin}"
    payload = f"carfax_payment_{chat_id}_{vin}"
    currency = "USD"
    prices = [LabeledPrice("Carfax Отчёт", CARFAX_PRICE)]
    await context.bot.send_invoice(
        chat_id, title, description, payload,
        PAYMENT_PROVIDER_TOKEN, currency, prices
    )

# ✅ Финальная проверка перед оплатой
async def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("carfax_payment"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Ошибка платежа, попробуйте позже.")

# 🛠️ Получение отчёта после оплаты
async def successful_payment(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    vin = context.user_data.get("vin")
    if not vin:
        await update.message.reply_text("⚠️ Ошибка: VIN не найден. Попробуйте снова.")
        return
    await update.message.reply_text("📑 Генерирую отчёт...")
    report_url = f"https://api.carfax.shop/report/getreport?key={CARFAX_API_KEY}&vin={vin}"
    response = requests.get(report_url)
    if response.status_code == 200:
        report_filename = f"carfax_report_{vin}.html"
        with open(report_filename, "w", encoding="utf-8") as file:
            file.write(response.text)
        with open(report_filename, "rb") as file:
            await context.bot.send_document(chat_id, file, caption=f"🚗 **Отчёт Carfax по VIN {vin}**")
    else:
        await update.message.reply_text("❌ Ошибка получения отчёта. Свяжитесь с поддержкой.")

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Привет! 🚗 Отправь мне VIN номер, и я проверю его. После этого ты сможешь купить Carfax-отчёт.")

async def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_vin))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # Удаляем любой установленный вебхук, чтобы избежать конфликта
    await application.bot.delete_webhook()

    print("🚀 Бот запущен!")
    # Запускаем polling; close_loop=False, чтобы не закрывать event loop (мы будем использовать nest_asyncio)
    await application.run_polling(close_loop=False)

if __name__ == "__main__":
    import asyncio
    print("🚀 Запуск бота...")
    asyncio.run(main())
