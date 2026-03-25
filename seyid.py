#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import asyncio
import logging
import aiosqlite
import g4f

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, filters
)

# ---------------- CONFIG ----------------
TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "@aristoaibot"
DB_NAME = "aristoai.db"
ADMIN_ID = 123456789  # Kendinle değiştir

SYSTEM_BASE = (
    "Sen AristoAI'sin. Derin, metaforik, bilge ve felsefi konuşursun. "
    "Tüm cevaplarını TÜRKÇE ver."
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AristoAI")

# ---------------- DATABASE ----------------
class DB:
    @staticmethod
    async def init():
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uid INTEGER PRIMARY KEY,
                character TEXT DEFAULT 'default',
                deep INTEGER DEFAULT 0
            )""")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                uid INTEGER,
                role TEXT,
                content TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")

            await db.commit()

    @staticmethod
    async def save(uid, role, content):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO messages (uid, role, content) VALUES (?, ?, ?)",
                (uid, role, content)
            )
            await db.commit()

    @staticmethod
    async def history(uid):
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(
                "SELECT role, content FROM messages WHERE uid=? ORDER BY ts DESC LIMIT 15",
                (uid,)
            )
            rows = await cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    @staticmethod
    async def get_user(uid):
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT character, deep FROM users WHERE uid=?", (uid,))
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users(uid) VALUES(?)", (uid,))
                await db.commit()
                return "default", 0
            return row

    @staticmethod
    async def set_character(uid, char):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET character=? WHERE uid=?", (char, uid))
            await db.commit()

    @staticmethod
    async def set_deep(uid, deep):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET deep=? WHERE uid=?", (1 if deep else 0, uid))
            await db.commit()

# ---------------- AI ----------------
class AI:
    @staticmethod
    def fallback():
        return random.choice([
            "Bağlantı yok, düşünceler sessizce bekliyor.",
            "Cevap bazen gecikir, çünkü soru büyüyordur.",
            "Zihin sustuğunda, hakikat konuşur."
        ])

    @staticmethod
    async def ask(uid, prompt, chat_type):
        try:
            char, deep = await DB.get_user(uid)
            history = await DB.history(uid)

            system = SYSTEM_BASE

            # karakter modu
            if char != "default":
                system += f" Stil: {char}"

            # derin mod
            if deep:
                system += " Daha metaforik ve derin konuş."

            # grup vs özel
            if chat_type == "private":
                system += " Daha kişisel cevap ver."
            else:
                system += " Kısa cevap ver."

            messages = [{"role": "system", "content": system}] + history + [
                {"role": "user", "content": prompt}
            ]

            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: g4f.ChatCompletion.create(
                    model=g4f.models.default,
                    messages=messages
                )
            )

            return str(res)

        except Exception as e:
            logger.error(e)
            return AI.fallback()

# ---------------- BOT ----------------
class Bot:
    def __init__(self):
        self.app = ApplicationBuilder().token(TOKEN).build()
        self.handlers()

    def handlers(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("karakter", self.karakter))
        self.app.add_handler(CommandHandler("derin", self.derin))
        self.app.add_handler(CommandHandler("aforizma", self.aforizma))
        self.app.add_handler(CommandHandler("paradoks", self.paradoks))
        self.app.add_handler(CommandHandler("gunluk", self.gunluk))
        self.app.add_handler(CommandHandler("tartis", self.tartis))
        self.app.add_handler(CommandHandler("clear", self.clear))

        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text))

    # -------- COMMANDS --------
    async def start(self, u, c):
        await u.message.reply_text("🧠 AristoAI aktif.")

    async def karakter(self, u, c):
        mode = " ".join(c.args)
        await DB.set_character(u.effective_user.id, mode)
        await u.message.reply_text(f"🎭 Karakter: {mode}")

    async def derin(self, u, c):
        state = " ".join(c.args).lower() == "aç"
        await DB.set_deep(u.effective_user.id, state)
        await u.message.reply_text("🌌 Derin mod: Açık" if state else "Kapalı")

    async def aforizma(self, u, c):
        res = await AI.ask(u.effective_user.id, "Özgün bir aforizma üret.", u.effective_chat.type)
        await u.message.reply_text(res)

    async def paradoks(self, u, c):
        res = await AI.ask(u.effective_user.id, "Bir paradoks anlat.", u.effective_chat.type)
        await u.message.reply_text(res)

    async def gunluk(self, u, c):
        res = await AI.ask(None, "Derin bir felsefi soru sor.", "private")
        await u.message.reply_text("🧠 Günün sorusu:\n" + res)

    async def tartis(self, u, c):
        text = " ".join(c.args)
        res = await AI.ask(u.effective_user.id, f"Bu fikre karşı çık: {text}", u.effective_chat.type)
        await u.message.reply_text(res)

    async def clear(self, u, c):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM messages WHERE uid=?", (u.effective_user.id,))
            await db.commit()
        await u.message.reply_text("🧠 Hafıza temizlendi.")

    # -------- TEXT --------
    async def text(self, u, c):
        uid = u.effective_user.id
        text = u.message.text

        # grup kontrolü
        if u.effective_chat.type != "private":
            if BOT_USERNAME not in text:
                return

        logger.info(f"{uid}: {text}")

        res = await AI.ask(uid, text, u.effective_chat.type)

        await DB.save(uid, "user", text)
        await DB.save(uid, "assistant", res)

        await u.message.reply_text(res)

# ---------------- MAIN ----------------
async def main():
    await DB.init()
    bot = Bot()

    cmds = [
        BotCommand("start", "Başlat"),
        BotCommand("karakter", "Karakter değiştir"),
        BotCommand("derin", "Derin mod"),
        BotCommand("aforizma", "Aforizma"),
        BotCommand("paradoks", "Paradoks"),
        BotCommand("gunluk", "Günün sorusu"),
        BotCommand("tartis", "Tartış"),
        BotCommand("clear", "Hafıza temizle")
    ]

    await bot.app.bot.set_my_commands(cmds)
    await bot.app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
