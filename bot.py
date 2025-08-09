# bot.py
import os
import logging
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
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN:
    raise ValueError("Missing TOKEN environment variable")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /connect command - only in private chats"""
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
    """Forward messages to connected group - only in private chats"""
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
    """Send welcome message - only in private chats"""
    if update.message.chat.type != "private":
        return
    
    await update.message.reply_text(
        "🤖 Forward Bot is running!\n"
        "Use /connect <group_id> in private chat to start forwarding messages\n\n"
        "⚠️ Note: I only respond to commands in private messages, not in groups."
    )

def main():
    """Start the bot"""
    application = Application.builder().token(TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("connect", connect_command))
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VIDEO,
        handle_message
    ))
    
    # Webhook configuration for Render
    if WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
            allowed_updates=Update.ALL_TYPES
        )
        logger.info(f"Running in WEBHOOK mode at {WEBHOOK_URL}/{TOKEN}")
    else:
        application.run_polling()
        logger.info("Running in POLLING mode")

if __name__ == "__main__":
    main()
