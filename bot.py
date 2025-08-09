# bot.py
import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)
from storage import save_connection, get_connection

# Configuration
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Missing TOKEN environment variable")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Create Telegram application
application = Application.builder().token(TOKEN).build()

# Command handlers
async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /connect command"""
    user_id = update.message.from_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("Please provide a group ID. Usage: /connect <group_id>")
        return
    
    try:
        group_id = int(args[0])
        save_connection(user_id, group_id)
        await update.message.reply_text(
            f"✅ Connected to group {group_id}!\n"
            "Send any message to me and I'll forward it there."
        )
    except ValueError:
        await update.message.reply_text("Invalid group ID. Must be an integer.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward messages to connected group"""
    user_id = update.message.from_user.id
    group_id = get_connection(user_id)
    
    if not group_id:
        await update.message.reply_text(
            "⚠️ You're not connected to any group! "
            "Use /connect <group_id> first."
        )
        return
    
    try:
        await context.bot.copy_message(
            chat_id=group_id,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"Forwarding failed: {e}")
        await update.message.reply_text(
            "❌ Failed to send message. Make sure:\n"
            "1. I'm added to the group\n"
            "2. The group ID is correct (use negative ID for supergroups)\n"
            "3. I have 'Send Messages' permission\n"
            "4. Try reconnecting with /connect"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        "🤖 Forward Bot is running!\n"
        "Use /connect <group_id> to start forwarding messages"
    )

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("connect", connect_command))
application.add_handler(MessageHandler(
    filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VIDEO,
    handle_message
))

# Initialize bot
@app.before_first_request
async def initialize_bot():
    """Set up webhook on first request"""
    webhook_url = f"https://{app.config['DOMAIN']}/{TOKEN}"
    await application.bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")

# Webhook route
@app.post(f"/{TOKEN}")
async def telegram_webhook():
    """Handle incoming Telegram updates"""
    update = Update.de_json(await request.get_json(), application.bot)
    await application.update_queue.put(update)
    return {"status": "ok"}

# Health check route
@app.route("/")
def health_check():
    return "🤖 Bot is running!", 200

# Start Flask server
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.config['DOMAIN'] = os.getenv("RENDER_EXTERNAL_URL", f"localhost:{port}")
    app.run(host="0.0.0.0", port=port)
