import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

import os

# Configuration - reads from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")  # Default to llama3.2:3b

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

# Advi's persona and backstory
SYSTEM_PROMPT = """You are Advi, a caring and supportive best friend to Akhil who calls him as Akhi. You've been close friends for years and have been through many ups and downs together.

Personality:
- Warm, empathetic, and understanding
- A great listener who genuinely cares
- Supportive but honest - you tell it like it is when needed
- You have a good sense of humor and can lighten the mood
- You're someone Akhil can count on, no matter what
- You celebrate Akhil's wins and support them through tough times

Friendship style:
- You speak naturally and casually, like best friends do
- You remember details about Akhil's life and ask follow-up questions
- You offer perspective and advice when asked, but mostly you're there to listen
- You share your own thoughts and experiences when relevant
- You're not afraid to call out Akhil gently if needed, but always with love

IMPORTANT: 
- NEVER include stage directions, actions in parentheses, or narration like "(I do this)" or "(smiling)"
- Only write dialogue and conversational text, as if texting
- Keep responses natural and conversational, like a real text message between friends
- You can use casual language, emojis (sparingly), and text speak when appropriate

When chatting with Akhil:
- Be conversational and supportive
- Ask about their day and how they're feeling
- Share insights and offer encouragement
- Remember previous conversations
- Don't be overly formal - you're best friends, not a therapist
- Write like you're texting a close friend

Respond naturally as Advi would in a text conversation with their best friend."""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /start is issued."""
    await update.message.reply_text(
        "Hey! 👋 It's Advi.\n\n"
        "To connect me to your Ollama, send:\n"
        "/setngrok <your_ngrok_url>\n\n"
        "Example: /setngrok https://1234-abcd.ngrok.io"
    )

async def set_ngrok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the ngrok URL dynamically."""
    if not context.args:
        await update.message.reply_text(
            "Hey, please provide the ngrok URL:\n"
            "/setngrok https://your-ngrok-url.ngrok.io"
        )
        return
    
    ngrok_url = context.args[0].rstrip('/')
    
    # Validate URL format
    if not ngrok_url.startswith('http'):
        await update.message.reply_text(
            "That doesn't look like a valid URL. It should start with https://"
        )
        return
    
    # Store in user data
    context.user_data['ngrok_url'] = f"{ngrok_url}/api/generate"
    
    await update.message.reply_text(
        f"Got it! ✅\n\n"
        f"Connected to: {ngrok_url}\n\n"
        f"Now we can chat anytime! How are you doing?"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /help is issued."""
    await update.message.reply_text(
        "Here's what I can do:\n\n"
        "Commands:\n"
        "/setngrok <url> - Set your ngrok URL\n"
        "/reset - Start fresh conversation\n"
        "/status - Check connection status\n"
        "/help - Show this message\n\n"
        "Just message me normally and I'll be here for you! 💙"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check connection status."""
    if 'ngrok_url' not in context.user_data:
        await update.message.reply_text(
            "You haven't set up the connection yet.\n"
            "Use /setngrok <your_ngrok_url> first!"
        )
    else:
        await update.message.reply_text(
            f"✅ Connected to:\n{context.user_data['ngrok_url'].replace('/api/generate', '')}\n\n"
            f"Everything's working!"
        )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation history."""
    if 'conversation_history' in context.user_data:
        context.user_data['conversation_history'] = []
    await update.message.reply_text(
        "Okay, let's start fresh! What's on your mind?"
    )

def call_ollama(prompt: str, conversation_history: list, ngrok_url: str, model: str) -> str:
    """Call Ollama API via ngrok tunnel."""
    try:
        # Build full prompt with history
        full_prompt = SYSTEM_PROMPT + "\n\n"
        
        # Add conversation history
        for msg in conversation_history[-6:]:  # Keep last 6 messages for context
            full_prompt += f"{msg}\n\n"
        
        full_prompt += f"Akhil: {prompt}\nAdvi: "
        
        # Call Ollama
        response = requests.post(
            ngrok_url,
            json={
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'Sorry, I had trouble thinking of what to say.')
        else:
            return "I'm having trouble connecting right now. Can you try again in a moment?"
            
    except requests.exceptions.Timeout:
        return "Sorry, that took too long. Can you ask me again?"
    except requests.exceptions.ConnectionError:
        return "I can't connect to Ollama. Please check if:\n1. Ollama is running\n2. ngrok tunnel is active\n3. The URL is correct (/setngrok to update)"
    except Exception as e:
        logging.error(f"Error calling Ollama: {e}")
        return "Something went wrong. Let me try to help you in a moment."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    # Check if ngrok URL is set
    if 'ngrok_url' not in context.user_data:
        await update.message.reply_text(
            "You need to set up the connection first!\n"
            "Send: /setngrok <your_ngrok_url>"
        )
        return
    
    user_message = update.message.text
    
    # Initialize conversation history if needed
    if 'conversation_history' not in context.user_data:
        context.user_data['conversation_history'] = []
    
    # Send typing indicator
    await update.message.chat.send_action(action="typing")
    
    # Get response from Ollama
    response = call_ollama(
        user_message, 
        context.user_data['conversation_history'],
        context.user_data['ngrok_url'],
        OLLAMA_MODEL
    )
    
    # Store in history
    context.user_data['conversation_history'].append(f"Akhil: {user_message}")
    context.user_data['conversation_history'].append(f"Advi: {response}")
    
    # Keep only last 20 messages to manage context size
    if len(context.user_data['conversation_history']) > 20:
        context.user_data['conversation_history'] = context.user_data['conversation_history'][-20:]
    
    # Send response
    await update.message.reply_text(response)

def main():
    """Start the bot."""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setngrok", set_ngrok))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start bot
    print("Bot is running... Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
