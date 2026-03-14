from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import secrets
import psycopg2
import os

# =======================
# ENVIRONMENT VARIABLES
# =======================
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("Set the TOKEN environment variable on Railway!")

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# =======================
# DATABASE
# =======================
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    telegram_id BIGINT PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS codes(
    code TEXT PRIMARY KEY,
    used INTEGER DEFAULT 0,
    used_by BIGINT
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

    cursor.execute(
        "INSERT INTO codes(code) VALUES(%s) ON CONFLICT DO NOTHING",
        (code,)
    )
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
        cursor.execute(
            "INSERT INTO codes(code) VALUES(%s) ON CONFLICT DO NOTHING",
            (code_value,)
        )
        conn.commit()
        await update.message.reply_text(f"Cod adăugat: {code_value}")

    elif action == "del":
        cursor.execute(
            "DELETE FROM codes WHERE code=%s",
            (code_value,)
        )
        conn.commit()
        await update.message.reply_text(f"Cod șters: {code_value}")

    else:
        await update.message.reply_text("Folosește `add` sau `del`.")


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

    cursor.execute(
        "INSERT INTO users(telegram_id) VALUES(%s) ON CONFLICT DO NOTHING",
        (user_id,)
    )
    conn.commit()

    await update.message.reply_text(
        f"User {user_id} a primit acces. Folosește /configurare pentru a continua"
    )


async def deluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Nu ai permisiunea.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Folosire: /deluser TELEGRAM_ID")
        return

    user_id = int(context.args[0])

    cursor.execute(
        "DELETE FROM users WHERE telegram_id=%s",
        (user_id,)
    )
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
        msg = "\n".join(
            f"{c[0]} - {'folosit' if c[1] else 'nefolosit'} (by {c[2]})"
            for c in codes
        )
        await update.message.reply_text(f"Lista codurilor:\n{msg}")
    else:
        await update.message.reply_text("Nu sunt coduri în baza de date.")


# =======================
# START
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    username = update.effective_user.username or user_id

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id=%s",
        (user_id,)
    )
    user = cursor.fetchone()

    if user:

        keyboard = [[
            InlineKeyboardButton(
                "Configurare",
                switch_inline_query_current_chat="/configurare"
            )
        ]]

        await update.message.reply_text(
            "Deja ai acces! Apasă butonul pentru configurare.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:

        await update.message.reply_text(
            f"Pentru a continua trebuie sa platiti suma de 150 lei "
            f"[APASAND AICI](https://mia-qr.bnm.md/1/m/BNM/AGRe6b17ca4125e415eb6d912b73ffbd45d)\n\n"
            f"La achitare introdu user-ul tau ({username}) in descriere.\n\n"
            "După plată vei primi un cod de acces.",
            parse_mode="Markdown"
        )


# =======================
# CONFIGURARE
# =======================
async def configurare(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id=%s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text(
            "Acces respins. Folosește /start."
        )
        return

    mesaj = (
        "Acceseaza programarile tale "
        "[AICI](https://eservicii.gov.md/asp/dimtcca/APO/my-appointments)\n\n"
        "Apasa EDITARE la programare.\n"
        "Copiaza linkul unde esti redirectionat si trimite-l aici.\n\n"
        "Vezi video demonstrativ mai jos."
    )

    video_url = "https://drive.google.com/uc?export=download&id=1hwIXrMvc7IQQsO_65D00kxujWFsK53h3"

    await update.message.reply_video(
        video=video_url,
        caption=mesaj,
        parse_mode="Markdown"
    )


# =======================
# CHECK CODE
# =======================
async def check_code(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    cursor.execute(
        "SELECT * FROM codes WHERE code=%s",
        (text,)
    )
    code = cursor.fetchone()

    if code and code[1] == 0:

        cursor.execute(
            "UPDATE codes SET used=1, used_by=%s WHERE code=%s",
            (user_id, text)
        )

        cursor.execute(
            "INSERT INTO users(telegram_id) VALUES(%s) ON CONFLICT DO NOTHING",
            (user_id,)
        )

        conn.commit()

        await update.message.reply_text(
            "Acces acordat!\n"
            "Scrie /configurare pentru a continua."
        )

    else:

        cursor.execute(
            "SELECT * FROM users WHERE telegram_id=%s",
            (user_id,)
        )
        user = cursor.fetchone()

        if user:
            await update.message.reply_text(
                "Mesajul a fost primit si va fi verificat."
            )
        else:
            await update.message.reply_text(
                "Cod invalid sau deja folosit."
            )


# =======================
# SECRET
# =======================
async def secret(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    cursor.execute(
        "SELECT * FROM users WHERE telegram_id=%s",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("Access respins.")
        return

    await update.message.reply_text("Secret command executed.")


# =======================
# HANDLERS
# =======================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("configurare", configurare))
app.add_handler(CommandHandler("generate", generate))
app.add_handler(CommandHandler("code", code))

app.add_handler(CommandHandler("adduser", adduser))
app.add_handler(CommandHandler("deluser", deluser))
app.add_handler(CommandHandler("listusers", listusers))
app.add_handler(CommandHandler("listcodes", listcodes))

app.add_handler(CommandHandler("secret", secret))

app.add_handler(MessageHandler(filters.TEXT, check_code))

# =======================
# RUN BOT
# =======================
app.run_polling()
