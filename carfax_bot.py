import nest_asyncio
nest_asyncio.apply()

from dotenv import load_dotenv
import os
load_dotenv("secret.env")

from telegram import Update, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, PreCheckoutQueryHandler
import requests

# Load tokens from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CARFAX_API_KEY = os.getenv("CARFAX_API_KEY")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
CARFAX_PRICE = 299

# ✅ VIN Check
async def check_vin(update: Update, context: CallbackContext) -> None:
    vin = update.message.text.strip().upper()
    if len(vin) != 17:
        await update.message.reply_text("❌ Error! VIN must be **17 characters** long.")
        return
    await update.message.reply_text("🔍 Checking VIN...")
    url = f"https://carfax-report.online/api.php?vin={vin}"
    response = requests.get(url)
    if response.status_code == 200:
        await update.message.reply_text(
            f"✅ VIN found! 🚗\n\n💰 Report price: **$2.99**\n\nPress /buy to purchase."
        )
        context.user_data["vin"] = vin  # Save VIN for payment
    else:
        await update.message.reply_text("❌ VIN not found. Please check and try again.")

# 💳 Report Purchase
async def buy(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    vin = context.user_data.get("vin")
    if not vin:
        await update.message.reply_text("⚠️ Please send a VIN for verification first!")
        return
    title = "Carfax Report"
    description = f"Report for VIN {vin}"
    payload = f"carfax_payment_{chat_id}_{vin}"
    currency = "USD"
    prices = [LabeledPrice("Carfax Report", CARFAX_PRICE)]
    await context.bot.send_invoice(
        chat_id, title, description, payload,
        PAYMENT_PROVIDER_TOKEN, currency, prices
    )

# ✅ Pre-payment Verification
async def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("carfax_payment"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Payment error, please try again later.")

# 🛠️ Retrieve Report After Payment
async def successful_payment(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    vin = context.user_data.get("vin")
    if not vin:
        await update.message.reply_text("⚠️ Error: VIN not found. Please try again.")
        return
    await update.message.reply_text("📑 Generating report...")
    report_url = f"https://api.carfax.shop/report/getreport?key={CARFAX_API_KEY}&vin={vin}"
    response = requests.get(report_url)
    if response.status_code == 200:
        report_filename = f"carfax_report_{vin}.html"
        with open(report_filename, "w", encoding="utf-8") as file:
            file.write(response.text)
        with open(report_filename, "rb") as file:
            await context.bot.send_document(chat_id, file, caption=f"🚗 **Carfax Report for VIN {vin}**")
    else:
        await update.message.reply_text("❌ Report retrieval error. Please contact support.")

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Hello! 🚗 Send me a VIN number, and I will check it. After that, you can purchase a Carfax report.")

async def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_vin))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # Remove any set webhook to avoid conflicts
    await application.bot.delete_webhook()

    print("🚀 Bot is running!")
    # Start polling; close_loop=False to keep the event loop open (we are using nest_asyncio)
    await application.run_polling(close_loop=False)

if __name__ == "__main__":
    import asyncio
    print("🚀 Starting bot...")
    asyncio.run(main())