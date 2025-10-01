#!/usr/bin/env python3
"""HR Onboarding Telegram Bot

Improved, production-ready single-file bot using python-telegram-bot v20.x
- Conversation flow for onboarding
- Writes service-account JSON from env var to a temp file (only if provided)
- Writes data into a Google Sheet
- Webhook-ready (configure APP_URL, BOT_TOKEN, PORT)

Required environment variables:
  - BOT_TOKEN
  - SPREADSHEET_ID
  - GOOGLE_CREDS_JSON_CONTENT (service account JSON content)
  - APP_URL

Optional:
  - HR_TELEGRAM_USERNAME
  - ONBOARDING_IMAGE_URL
  - PORT (default 8080)

Run mode: executed as a webhook in __main__ block; change if you prefer polling.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
import gspread
from google.oauth2.service_account import Credentials

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- Conversation states ----------
(
    ASK_NAME,
    ASK_GENDER,
    ASK_PHONE,
    ASK_EMAIL,
    ASK_WHATSAPP,
    ASK_TELE_ID,
    ASK_ACCOUNT,
    ASK_IFSC,
    ASK_BANK,
    CONFIRM,
) = range(10)

# ---------- Env vars ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HR_TELEGRAM_USERNAME = os.getenv("HR_TELEGRAM_USERNAME")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ONBOARDING_IMAGE_URL = os.getenv("ONBOARDING_IMAGE_URL")
GOOGLE_CREDS_JSON_CONTENT = os.getenv("GOOGLE_CREDS_JSON_CONTENT")
APP_URL = os.getenv("APP_URL")  # public URL for webhook
PORT = int(os.getenv("PORT", "8080"))

required = ["BOT_TOKEN", "SPREADSHEET_ID", "GOOGLE_CREDS_JSON_CONTENT", "APP_URL"]
missing = [name for name in required if not globals().get(name)]
if missing:
    logger.error("Missing required environment variables: %s", missing)
    sys.exit(1)

# ---------- Write service account json to a temp file securely ----------
SERVICE_ACCOUNT_PATH: Optional[str] = None
try:
    # Parse JSON to ensure it's valid
    json.loads(GOOGLE_CREDS_JSON_CONTENT)
    fd, SERVICE_ACCOUNT_PATH = tempfile.mkstemp(suffix="-gcred.json")
    with os.fdopen(fd, "w") as f:
        f.write(GOOGLE_CREDS_JSON_CONTENT)
    logger.info("Wrote Google service account JSON to temp file")
except Exception:
    logger.exception("Invalid GOOGLE_CREDS_JSON_CONTENT; must be a valid JSON string")
    sys.exit(1)

# ---------- Google Sheets helper ----------
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.sheet1

# ---------- Utils ----------
def generate_emp_code(phone: str) -> str:
    digits = "".join([c for c in (phone or "") if c.isdigit()])
    last4 = digits[-4:] if len(digits) >= 4 else digits.zfill(4)
    return f"CHEGG{last4}"

def is_valid_phone(phone: str) -> bool:
    digits = "".join([c for c in (phone or "") if c.isdigit()])
    return len(digits) >= 7

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    context.user_data["collected"] = {}
    await update.message.reply_text(
        "Welcome to the Onboarding Bot! Let's start with a few questions.\n\n"
        "First — what's your full name?"
    )
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not update.message.text:
        return ASK_NAME
    name = update.message.text.strip()
    context.user_data.setdefault("collected", {})["name"] = name
    kb = ReplyKeyboardMarkup([["Male", "Female", "Other"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("What's your gender?", reply_markup=kb)
    return ASK_GENDER

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return ASK_GENDER
    context.user_data.setdefault("collected", {})["gender"] = update.message.text.strip()
    await update.message.reply_text("Please enter your Phone Number (digits only, e.g. 9876543210)", reply_markup=ReplyKeyboardRemove())
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not update.message.text:
        await update.message.reply_text("Please send a valid phone number.")
        return ASK_PHONE
    phone = update.message.text.strip()
    if not is_valid_phone(phone):
        await update.message.reply_text("Invalid phone number. Please send digits (e.g. 9876543210)." )
        return ASK_PHONE
    context.user_data.setdefault("collected", {})["phone"] = phone
    await update.message.reply_text("Enter your Email address:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not update.message.text:
        await update.message.reply_text("Please send a valid email address.")
        return ASK_EMAIL
    context.user_data.setdefault("collected", {})["email"] = update.message.text.strip()
    await update.message.reply_text("WhatsApp Number (or type 'same' if same as phone):")
    return ASK_WHATSAPP

async def ask_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not update.message.text:
        await update.message.reply_text("Please send WhatsApp number or 'same'.")
        return ASK_WHATSAPP
    whats = update.message.text.strip()
    if whats.lower() == "same":
        whats = context.user_data.setdefault("collected", {}).get("phone", "")
    context.user_data.setdefault("collected", {})["whatsapp"] = whats
    await update.message.reply_text("Send your Telegram UserId (or @username):")
    return ASK_TELE_ID

async def ask_tele_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not update.message.text:
        await update.message.reply_text("Please send Telegram UserId or @username.")
        return ASK_TELE_ID
    context.user_data.setdefault("collected", {})["telegram_user"] = update.message.text.strip()
    await update.message.reply_text("Enter your Account Number:")
    return ASK_ACCOUNT

async def ask_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return ASK_ACCOUNT
    context.user_data.setdefault("collected", {})["account_number"] = update.message.text.strip()
    await update.message.reply_text("Enter your Bank IFSC code (e.g., HDFC0001234):")
    return ASK_IFSC

async def ask_ifsc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return ASK_IFSC
    context.user_data.setdefault("collected", {})["ifsc"] = update.message.text.strip().upper()
    await update.message.reply_text("Enter your Bank Name:")
    return ASK_BANK

async def ask_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return ASK_BANK
    context.user_data.setdefault("collected", {})["bank_name"] = update.message.text.strip()
    c = context.user_data.get("collected", {})
    summary = ( 
        f"Summary:\nName: {c.get('name')}\nGender: {c.get('gender')}\nPhone: {c.get('phone')}\n"
        f"Email: {c.get('email')}\nWhatsApp: {c.get('whatsapp')}\nTelegram: {c.get('telegram_user')}\n"
        f"Account: {c.get('account_number')}\nIFSC: {c.get('ifsc')}\nBank: {c.get('bank_name')}\n\n"
        "Send 'confirm' to submit or 'cancel' to abort."
    )
    await update.message.reply_text(summary)
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or not update.message.text:
        await update.message.reply_text("Please type 'confirm' to submit or 'cancel' to abort.")
        return CONFIRM

    if update.message.text.strip().lower() not in ("confirm", "yes"):
        await update.message.reply_text("Onboarding canceled. Send /start to retry.")
        return ConversationHandler.END

    c = context.user_data.get("collected", {})
    emp_code = generate_emp_code(c.get("phone", ""))
    c["employee_code"] = emp_code
    c["created_at"] = datetime.utcnow().isoformat()

    # Save to Google Sheet
    try:
        sheet = get_sheet()
        header = [
            "Employee Code",
            "Name",
            "Gender",
            "Phone",
            "Email",
            "WhatsApp",
            "Telegram User",
            "Account Number",
            "IFSC",
            "Bank Name",
            "Timestamp",
        ]
        existing_header = sheet.row_values(1)
        if existing_header != header:
            # Insert header (replace if different length)
            try:
                sheet.insert_row(header, index=1)
            except Exception:
                # If header already exists but different, continue
                logger.info("Header insertion skipped or failed; proceeding to append row")

        row = [
            c.get("employee_code"),
            c.get("name"),
            c.get("gender"),
            c.get("phone"),
            c.get("email"),
            c.get("whatsapp"),
            c.get("telegram_user"),
            c.get("account_number"),
            c.get("ifsc"),
            c.get("bank_name"),
            c.get("created_at"),
        ]
        # Use user-entered value option so that timestamps/dates are handled nicely
        sheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception:
        logger.exception("Failed to write to Google Sheet")
        await update.message.reply_text("Error saving details. Try again later.")
        return ConversationHandler.END

    await update.message.reply_text(f"Your Employee Code: *{emp_code}*", parse_mode="Markdown")
    if ONBOARDING_IMAGE_URL:
        try:
            await update.message.reply_photo(photo=ONBOARDING_IMAGE_URL)
        except Exception:
            logger.exception("Failed to send onboarding image")
            await update.message.reply_text("(Could not send image)")

    if HR_TELEGRAM_USERNAME:
        await update.message.reply_text(f"Share your Employee Code with HR: https://t.me/{HR_TELEGRAM_USERNAME}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Onboarding canceled. Send /start to retry.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ---------- Build app & handlers ----------
app = ApplicationBuilder().token(BOT_TOKEN).build()
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
        ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
        ASK_WHATSAPP: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_whatsapp)],
        ASK_TELE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tele_id)],
        ASK_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_account)],
        ASK_IFSC: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ifsc)],
        ASK_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_bank)],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
app.add_handler(conv_handler)

# ---------- Run webhook ----------
if __name__ == "__main__":
    logger.info("Starting HR onboarding bot (webhook mode) on port %s", PORT)
    # Use bot token as url_path for simple security; ensure APP_URL matches your domain
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=BOT_TOKEN, webhook_url=f"{APP_URL}/{BOT_TOKEN}")
