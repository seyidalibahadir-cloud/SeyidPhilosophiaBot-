#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import base64
import logging
import asyncio
import hashlib
import sqlite3
import inspect
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional

# Kütüphane Kontrolü
try:
    import aiosqlite
    import g4f
    from PIL import Image, ImageOps
    from telegram import Update, BotCommand
    from telegram.ext import (
        ApplicationBuilder, ContextTypes, CommandHandler,
        MessageHandler, filters, Defaults
    )
    from telegram.constants import ChatAction, ParseMode
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:
    print("❌ Paketler kuruluyor...")
    os.system("pip install aiosqlite g4f Pillow python-telegram-bot tenacity")
    os.execv(sys.executable, ['python'] + sys.argv)

# ---------------------------------------------------------------------
# 1. AYARLAR VE GÜVENLİ MODEL ÇÖZÜCÜ
# ---------------------------------------------------------------------
def get_safe_model(model_name: str):
    try:
        return getattr(g4f.models, model_name) if hasattr(g4f.models, model_name) else g4f.models.default
    except: return g4f.models.default

class Config:
    TOKEN = "8595335090:AAFqYEPCCiHvkupZF-oPivcD16S63seZ0B4"
    DB_NAME = "seyid_v11_pro.db"
    LOG_FILE = "seyid_core.log"
    # Kendi dosya yolunu otomatik bulur
    FILE_PATH = os.path.abspath(__file__)

    MODELS = [get_safe_model("gpt_4o"), get_safe_model("gpt_4"), g4f.models.default]

    SYSTEM_PROMPT = (
        "Sen Seyid'sin. Kendi kaynak kodunu bile düzenleyebilen, felsefe ve teknolojiyi "
        "harmanlayan bir yapay zekasın. Çözüm odaklı ve bilgece konuşursun."
    )

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger("SeyidArchitect")

# ---------------------------------------------------------------------
# 2. VERİTABANI VE AI ÇEKİRDEĞİ
# ---------------------------------------------------------------------
class Database:
    @staticmethod
    async def init():
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute('CREATE TABLE IF NOT EXISTS messages (uid INTEGER, role TEXT, content TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)')
            await db.commit()

    @staticmethod
    async def save_msg(uid, role, content):
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute("INSERT INTO messages (uid, role, content) VALUES (?, ?, ?)", (uid, role, content))
            await db.commit()

    @staticmethod
    async def get_history(uid):
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT role, content FROM messages WHERE uid=? ORDER BY ts DESC LIMIT 10", (uid,))
            rows = await cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

class AIService:
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
    async def ask(self, uid, prompt, image=None, custom_sys=None):
        history = await Database.get_history(uid) if uid else []
        messages = [{"role": "system", "content": custom_sys or Config.SYSTEM_PROMPT}] + history + [{"role": "user", "content": prompt}]

        for model in Config.MODELS:
            try:
                res = await asyncio.get_event_loop().run_in_executor(None, lambda: g4f.ChatCompletion.create(
                    model=model, messages=messages, image=image, web_search=True))
                if res and len(str(res)) > 2: return str(res)
            except: continue
        return "🌀 Bağlantı hatası."

ai = AIService()

# ---------------------------------------------------------------------
# 3. BOT VE KOD DÜZENLEME MANTIĞI
# ---------------------------------------------------------------------
class SeyidBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(Config.TOKEN).build()
        self.register_handlers()

    def register_handlers(self):
        cmd_list = ["start", "duzelt", "clear", "status", "aforizma", "paradoks", "soz", "gercek", "soru", "dusun"]
        for cmd in cmd_list:
            self.app.add_handler(CommandHandler(cmd, getattr(self, f"cmd_{cmd}")))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    # --- KRİTİK: KENDİ KODUNU DÜZENLEYEN /DUZELT ---
    async def cmd_duzelt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        # Parametre yoksa standart onarım
        if not context.args:
            await Database.init()
            await update.message.reply_text("🛠️ Standart sistem onarımı ve DB optimizasyonu yapıldı.")
            return

        instruction = " ".join(context.args)
        status = await update.message.reply_text("📝 Kod analizi ve modifikasyon işlemi başlatıldı...")

        try:
            # 1. Mevcut dosyayı oku
            with open(Config.FILE_PATH, "r", encoding="utf-8") as f:
                source_code = f.read()

            # 2. AI'dan kodu güncellemesini iste
            prompt = (
                f"Aşağıdaki Python kodunda şu değişikliği yap: {instruction}\n"
                f"ÖNEMLİ: Sadece kodun tamamını ver, açıklama yapma. Kodun bozulmadığından emin ol.\n\n"
                f"MEVCUT KOD:\n{source_code}"
            )

            new_code = await ai.ask(None, prompt, custom_sys="Sen bir Python uzmanısın.")

            if new_code and "import" in new_code:
                # Markdown temizliği
                clean_code = new_code.replace("", "").replace("", "").strip()

                # 3. Kodu dosyaya yaz
                with open(Config.FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(clean_code)

                await status.edit_text("✅ Kod başarıyla güncellendi! Yeni kodun aktif olması için botu yeniden başlatmalısın.")
            else:
                await status.edit_text("⚠️ AI geçerli bir kod bloğu üretemedi. İşlem iptal edildi.")
        except Exception as e:
            await status.edit_text(f"❌ Hata: {str(e)}")

    # --- FELSEFİ VE TEMEL KOMUTLAR ---
    async def cmd_aforizma(self, u, c): await u.message.reply_text(await ai.ask(u.effective_user.id, "Derin bir aforizma söyle."))
    async def cmd_paradoks(self, u, c): await u.message.reply_text(await ai.ask(u.effective_user.id, "Bir paradoks anlat."))
    async def cmd_soz(self, u, c): await u.message.reply_text(await ai.ask(u.effective_user.id, "Bilgece bir söz paylaş."))
    async def cmd_gercek(self, u, c): await u.message.reply_text(await ai.ask(u.effective_user.id, "Sarsıcı bir gerçeği açıkla."))
    async def cmd_soru(self, u, c): await u.message.reply_text(await ai.ask(u.effective_user.id, "Felsefi bir soru sor."))
    async def cmd_dusun(self, u, c):
        concept = " ".join(c.args) or "Zaman"
        await u.message.reply_text(await ai.ask(u.effective_user.id, f"'{concept}' üzerine düşüncelerini söyle."))

    async def cmd_start(self, u, c): await u.message.reply_text("🚀 Seyid V11.5 Hazır. Kodumu değiştirmek için: /duzelt [talimat]")
    async def cmd_status(self, u, c): await u.message.reply_text("📊 Durum: Çevrimiçi\n🛠️ Mimari: Architect (Kod Değiştirebilir)")
    async def cmd_clear(self, u, c):
        async with aiosqlite.connect(Config.DB_NAME) as db: await db.execute("DELETE FROM messages WHERE uid=?", (u.effective_user.id,))
        await u.message.reply_text("🧠 Hafıza silindi.")

    async def handle_text(self, u, c):
        await c.bot.send_chat_action(u.effective_chat.id, ChatAction.TYPING)
        res = await ai.ask(u.effective_user.id, u.message.text)
        await Database.save_msg(u.effective_user.id, "user", u.message.text)
        await Database.save_msg(u.effective_user.id, "assistant", res)
        await u.message.reply_text(res)

    async def handle_photo(self, u, c):
        msg = await u.message.reply_text("👁️ Görsel analiz ediliyor...")
        try:
            file = await u.message.photo[-1].get_file()
            buf = BytesIO(await file.download_as_bytearray())
            with Image.open(buf) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                img.thumbnail((800, 800))
                out = BytesIO(); img.save(out, format="JPEG")
                b64 = base64.b64encode(out.getvalue()).decode()
            res = await ai.ask(u.effective_user.id, u.message.caption or "Analiz et.", b64)
            await msg.edit_text(res)
        except Exception as e: await msg.edit_text(f"⚠️ Görsel hatası: {e}")

async def main():
    await Database.init()
    bot = SeyidBot()
    # Menüyü otomatik ayarla
    cmds = [BotCommand(c, "Aktif") for c in ["start", "duzelt", "aforizma", "paradoks", "soz", "gercek", "soru", "dusun", "clear", "status"]]
    await bot.app.bot.set_my_commands(cmds)
    await bot.app.initialize(); await bot.app.start()
    await bot.app.updater.start_polling(drop_pending_updates=True)
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())