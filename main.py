import logging
import sqlite3
import time
import threading
from datetime import datetime
from dateparser import parse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import openai

# === CONFIGURATION ===
TELEGRAM_TOKEN = "8162515380:AAFWl-vVNYscz3gagi8zT2_xXz8Y6dTPJnI"
OPENAI_API_KEY = "sk-proj-O3vpuQAYV3iGZlzT6KS7T3BlbkFJuloQKCXJKRlqU0hKdoND"
openai.api_key = OPENAI_API_KEY
DB_PATH = "tasks.db"

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === DB SETUP ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        task TEXT,
        remind_time TEXT
    )''')
    conn.commit()
    conn.close()

# === GPT PARSER ===
def parse_task(text):
    prompt = f"Извлеки из этой строки задание и время напоминания: '{text}'. Ответь в формате: TASK: ...\nTIME: ..."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response['choices'][0]['message']['content']
    task, time_str = None, None
    for line in content.splitlines():
        if line.startswith("TASK:"):
            task = line[5:].strip()
        elif line.startswith("TIME:"):
            time_str = line[5:].strip()
    remind_time = parse(time_str)
    return task, remind_time

# === TASK MANAGER ===
def add_task(user_id, task, remind_time):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, task, remind_time) VALUES (?, ?, ?)",
              (user_id, task, remind_time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def get_due_tasks():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("SELECT id, user_id, task FROM tasks WHERE remind_time <= ?", (now,))
    tasks = c.fetchall()
    c.execute("DELETE FROM tasks WHERE remind_time <= ?", (now,))
    conn.commit()
    conn.close()
    return tasks

# === REMINDER LOOP ===
async def reminder_loop(app):
    while True:
        tasks = get_due_tasks()
        for task_id, user_id, task in tasks:
            try:
                await app.bot.send_message(chat_id=user_id, text=f"🔔 Напоминание: {task}")
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания: {e}")
        time.sleep(30)

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Напиши, что мне напомнить и когда."
Пример: 'Напомни завтра в 9 утра купить кофе'")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    try:
        task, remind_time = parse_task(user_text)
        if task and remind_time:
            add_task(user_id, task, remind_time)
            await update.message.reply_text(f"✅ Задача сохранена: {task} — {remind_time.strftime('%d.%m %H:%M')}")
        else:
            await update.message.reply_text("Не удалось понять, когда напомнить. Попробуй переформулировать.")
    except Exception as e:
        logger.error(f"Ошибка при обработке: {e}")
        await update.message.reply_text("Что-то пошло не так при разборе задачи.")

# === MAIN ===
def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    thread = threading.Thread(target=lambda: app.run_polling(), daemon=True)
    thread.start()

    import asyncio
    asyncio.run(reminder_loop(app))

if __name__ == "__main__":
    main()
