from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import sqlite3
import secrets
import os

# =======================
# ENVIRONMENT VARIABLES
# =======================
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("Set the TOKEN environment variable on Railway!")

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # ID-ul tău Telegram ca env var

# =======================
# DATABASE
# =======================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    telegram_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS codes(
    code TEXT PRIMARY KEY,
    used INTEGER DEFAULT 0,
    used_by INTEGER
)
""")

conn.commit()

# =======================
# HELPERS
# =======================
def generate_code():
    return secrets.token_hex(4).upper()

# =======================
# ADMIN COMMANDS
# =======================
async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return
    code = generate_code()
    cursor.execute("INSERT INTO codes(code) VALUES(?)", (code,))
    conn.commit()
    await update.message.reply_text(f"New code:\n{code}")

async def code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Folosire:\n/code add COD\n/code del COD")
        return
    action = context.args[0].lower()
    code_value = context.args[1].strip().upper()
    if action == "add":
        cursor.execute("INSERT OR IGNORE INTO codes(code) VALUES(?)", (code_value,))
        conn.commit()
        await update.message.reply_text(f"Cod adăugat: {code_value}")
    elif action == "del":
        cursor.execute("DELETE FROM codes WHERE code=?", (code_value,))
        conn.commit()
        await update.message.reply_text(f"Cod șters: {code_value}")
    else:
        await update.message.reply_text("Acțiune necunoscută. Folosește `add` sau `del`.")

# =======================
# USER MANAGEMENT
# =======================
async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Folosire: /adduser TELEGRAM_ID")
        return
    user_id = int(context.args[0])
    cursor.execute("INSERT OR IGNORE INTO users(telegram_id) VALUES(?)", (user_id,))
    conn.commit()
    await update.message.reply_text(f"User {user_id} a primit acces. Foloseste /configurare pentru a continua")

async def deluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Folosire: /deluser TELEGRAM_ID")
        return
    user_id = int(context.args[0])
    cursor.execute("DELETE FROM users WHERE telegram_id=?", (user_id,))
    conn.commit()
    await update.message.reply_text(f"Accesul userului {user_id} a fost șters.")

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return
    cursor.execute("SELECT telegram_id FROM users")
    users = cursor.fetchall()
    if users:
        msg = "\n".join(str(u[0]) for u in users)
        await update.message.reply_text(f"Useri cu acces:\n{msg}")
    else:
        await update.message.reply_text("Nu sunt useri cu acces.")

async def listcodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return
    cursor.execute("SELECT code, used, used_by FROM codes")
    codes = cursor.fetchall()
    if codes:
        msg = "\n".join(f"{c[0]} - {'folosit' if c[1] else 'nefolosit'} (by {c[2]})" for c in codes)
        await update.message.reply_text(f"Lista codurilor:\n{msg}")
    else:
        await update.message.reply_text("Nu sunt coduri în baza de date.")

# =======================
# START + CONFIGURARE
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or user_id
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()
    if user:
        # Inline button pentru /configurare
        keyboard = [[InlineKeyboardButton("Configurare", switch_inline_query_current_chat="/configurare")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Deja ai acces! Apasă butonul de mai jos pentru configurare:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"Pentru a continua trebuie sa platiti suma de 150 lei [APASAND AICI](https://mia-qr.bnm.md/1/m/BNM/AGRe6b17ca4125e415eb6d912b73ffbd45d)\n\n"
            f"La achitare, in rubrica \"notite\" sau \"descriere\" introduceti user-ul dvs. ({username})\n\n"
            "Dupa achitare, veti primi un cod cu care veti avea acces la restul serviciului",
            parse_mode="Markdown"
        )

async def configurare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await update.message.reply_text("Acces respins. Nu ai cod valid. Foloseste /start pentru a incepe")
        return

    mesaj = (
        "Acceseaza programarile tale [AICI](https://eservicii.gov.md/asp/dimtcca/APO/my-appointments) sau pe link-ul oferit de asp pe posta elctronica\n"
        "Introdu datele tale si apasa pe butonul de 'EDITARE' pentru programarea dorita.\n"
        "Copiaza link-ul pe care esti redirectionat si trimite-l aici.\n\n"
        "In caz de neclaritati, puteti viziona acest video demonstrativ."
    )

    video_url = "https://drive.google.com/uc?export=download&id=1ULs-9fEw2erDFT8X4I-6KuXpmC3_BMpx"

    await update.message.reply_video(video=video_url, caption=mesaj, parse_mode="Markdown")

# =======================
# CHECK CODE
# =======================
async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    cursor.execute("SELECT * FROM codes WHERE code=?", (text,))
    code = cursor.fetchone()
    if code and code[1] == 0:
        cursor.execute("UPDATE codes SET used=1, used_by=? WHERE code=?", (user_id, text))
        cursor.execute("INSERT INTO users(telegram_id) VALUES(?)", (user_id,))
        conn.commit()
        await update.message.reply_text(
            "Acces acordat. Acum poți folosi comenzile botului.\n"
            "Pentru a începe configurarea, apasă butonul de mai jos sau scrie /configurare"
        )
    else:
        cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
        user = cursor.fetchone()
        if user:
            await update.message.reply_text(
                "Mesajul primit. Dacă dorești să începi configurarea, apasă /configurare."
            )
        else:
            await update.message.reply_text("Cod invalid sau folosit.")

# =======================
# SECRET COMMAND (example)
# =======================
async def secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await update.message.reply_text("Access respins.")
        return
    await update.message.reply_text("Secret command executed.")

# =======================
# HANDLERS
# =======================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("adduser", adduser))
app.add_handler(CommandHandler("deluser", deluser))
app.add_handler(CommandHandler("listusers", listusers))
app.add_handler(CommandHandler("listcodes", listcodes))
app.add_handler(CommandHandler("code", code))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("generate", generate))
app.add_handler(CommandHandler("configurare", configurare))
app.add_handler(CommandHandler("secret", secret))
app.add_handler(MessageHandler(filters.TEXT, check_code))

# =======================
# RUN BOT
# =======================
app.run_polling()
