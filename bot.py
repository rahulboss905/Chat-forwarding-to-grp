import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
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

@app.route('/')
def health_check():
    return "🤖 Bot is running! I only respond to private messages.", 200

def run_flask():
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Flask health check on port {port}")
    app.run(host='0.0.0.0', port=port)

# Initialize Telegram application
application = Application.builder().token(TOKEN).build()

# Command handlers
async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /connect command"""
    if update.message.chat.type != "private":
        return
    
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
            "Send any message to me (in private) and I'll forward it there."
        )
    except ValueError:
        await update.message.reply_text("Invalid group ID. Must be an integer.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    if update.message.chat.type != "private":
        return
    
    user_id = update.message.from_user.id
    group_id = get_connection(user_id)
    
    if not group_id:
        await update.message.reply_text(
            "⚠️ You're not connected to any group! "
            "Use /connect <group_id> first."
        )
        return
    
    try:
        # Handle stickers specifically
        if update.message.sticker:
            await context.bot.send_sticker(
                chat_id=group_id,
                sticker=update.message.sticker.file_id
            )
        # Handle all other media types
        else:
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
    """Handle /start command"""
    if update.message.chat.type != "private":
        return
    
    await update.message.reply_text(
        "🤖 Forward Bot is running!\n"
        "Use /connect <group_id> in private chat to start forwarding messages\n\n"
        "⚠️ Note: I only respond to commands in private messages, not in groups."
    )

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("connect", connect_command))

# CORRECTED FILTERS: Use proper filter instances
application.add_handler(MessageHandler(
    filters.TEXT | 
    filters.PHOTO | 
    filters.Document.ALL() |  # Note: ALL is a method that returns a filter
    filters.AUDIO | 
    filters.VIDEO |
    filters.Sticker.ALL |  # Correct filter instance
    filters.VOICE |
    filters.ANIMATION,
    handle_message
))

def start_bot():
    """Start Telegram bot in polling mode"""
    logger.info("Starting Telegram bot in polling mode...")
    application.run_polling()

if __name__ == "__main__":
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start bot in main thread
    logger.info("Starting bot...")
    start_bot()
