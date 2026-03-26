#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# ============================================================
# AUTO INSTALL (TERMUX / CLEAN ENV)
# ============================================================

try:
    import aiosqlite
    import g4f
    from telegram import Update, BotCommand
    from telegram.constants import ChatAction
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
except ImportError:
    print("❌ Eksik paketler kuruluyor...")
    os.system("pip install aiosqlite g4f python-telegram-bot")
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ============================================================
# CONFIG
# ============================================================

class Config:
    TOKEN = "8787712426:AAG0QzVbeWWay-njkCSWwnntZ4FKHAlhAiY"
    BOT_USERNAME = "@aristoaibot"
    DB_NAME = "aristo_felsefe.db"

    MAX_HISTORY = 12
    MAX_REPLY_CHARS = 3800
    RATE_LIMIT_SECONDS = 1.1

    SYSTEM_PROMPT = (
        "Sen AristoAI'sın. Sadece felsefe ekosisteminde çalışan bir yapay zekâsın. "
        "Cevapların Türkçe, tek paragraf, düşünsel, ölçülü ve derin olmalı. "
        "Küfür, hakaret, cinsellik, şiddet, suç, teknik istismar, siyaset, alışveriş, "
        "gündelik sohbet ve felsefe dışı konulara cevap verme. "
        "Etik, varoluş, metafizik, epistemoloji, mantık, estetik, adalet, erdem, "
        "bilinç, özgürlük, anlam, hakikat, zaman, zihin, ruh ve benlik gibi alanlarda konuş."
    )

    REFUSAL_TEXT = (
        "Bu bot yalnızca felsefi sorulara cevap verir; istersen bunu etik, varoluş, hakikat, "
        "anlam, bilinç, özgürlük, zihin, zaman ya da adalet üzerine bir soruya dönüştürebilirsin."
    )

    FILTER_TEXT = (
        "Filtre katmanları aktif; küfür, hakaret, şiddet, cinsellik, suç, teknik istismar, "
        "felsefe dışı istekler ve alakasız konular reddedilir; cevaplar tek paragraf ve Türkçe olur."
    )

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s"
)
logger = logging.getLogger("AristoAI")

# ============================================================
# GLOBAL STATE
# ============================================================

LAST_REQUEST_AT: Dict[int, float] = {}

# ============================================================
# PHILOSOPHICAL STYLE LIBRARY
# ============================================================

STYLE_LIBRARY: Dict[str, str] = {
    "sokratik": "Soru sorarak ilerle, çelişkileri görünür kıl ve diyalektik bir üslup kullan.",
    "platonik": "İdealler, formlar ve öz üzerine konuş; görünenden çok özü vurgula.",
    "aristotelesçi": "Sebep-sonuç, ölçü, amaç ve denge üzerinden düşün.",
    "stoacı": "Sakin, dayanıklı ve kontrol alanı ile kontrol dışını ayıran bir ton kullan.",
    "nihilist": "Anlamın kırılganlığını göster; ama bunu yıkıcı değil, düşünsel biçimde yap.",
    "varoluşçu": "Özgürlük, sorumluluk, kaygı ve seçim merkezli konuş.",
    "sufist": "İçsel derinlik, birlik, benlik aşımı ve sessizlik merkezli konuş.",
    "realist": "Soyutu inkâr etmeden ama ayakları yere basan bir biçimde konuş.",
    "metaforik": "Güçlü imgeler, benzetmeler ve semboller kullan.",
    "sezgisel": "Derin sezgiler, içgörüler ve yumuşak ama net bir anlatım kullan.",
    "kantçı": "Ödev, iyi isteme, evrensel ilke ve ahlaki yasa çerçevesinde konuş.",
    "hegelci": "Karşıtlıkların çatışması ve aşılması üzerinden yorum yap.",
    "fenomenolojik": "Deneyimin nasıl göründüğünü, bilincin eşliğinde anlat.",
    "ontolojik": "Varlık, yokluk ve mevcudiyet üzerinden konuş.",
    "etik": "Doğru, yanlış, sorumluluk ve karakter üzerinden konuş.",
}

AVAILABLE_STYLES = sorted(STYLE_LIBRARY.keys())

# ============================================================
# COMMAND SPECS
# ============================================================

@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    prompt: str

TOPIC_SPECS: List[CommandSpec] = [
    CommandSpec("aforizma", "Kısa felsefi aforizma üretir.", "Özgün, tek paragraf ve vurucu bir felsefi aforizma üret."),
    CommandSpec("paradoks", "Felsefi paradoks anlatır.", "Bir paradoks anlat ve neden paradoks olduğunu açıklayarak tek paragrafta yorumla."),
    CommandSpec("soz", "Bilgece söz üretir.", "Bilgece bir söz paylaş ve kısa bir felsefi yorum ekle."),
    CommandSpec("gercek", "Sarsıcı bir hakikat söyler.", "Sarsıcı bir gerçeği felsefi bakışla açıkla."),
    CommandSpec("soru", "Felsefi soru sorar.", "Bir felsefi soru sor ve neden önemli olduğunu tek paragrafta açıkla."),
    CommandSpec("etik", "Etik ve ahlak üzerine konuşur.", "Etik ve ahlak üzerine derin, tek paragraf bir değerlendirme yap."),
    CommandSpec("varolus", "Varoluş üzerine konuşur.", "Varoluş, seçim ve anlam üzerine düşün."),
    CommandSpec("metafizik", "Metafizik üzerine konuşur.", "Metafizik kavramlar üzerine tek paragraf, derin bir yorum yap."),
    CommandSpec("epistemoloji", "Bilgi kuramı üzerine konuşur.", "Epistemoloji, bilgi, doğruluk ve bilmenin sınırları üzerine konuş."),
    CommandSpec("mantik", "Mantık ve akıl yürütme üzerine konuşur.", "Mantık, tutarlılık ve akıl yürütme üzerine düşün."),
    CommandSpec("bilgelik", "Bilgelik üzerine konuşur.", "Bilgelik nedir, nasıl oluşur, tek paragrafta anlat."),
    CommandSpec("adalet", "Adalet üzerine konuşur.", "Adaletin anlamını ve toplumsal karşılığını felsefi biçimde yorumla."),
    CommandSpec("zaman", "Zaman üzerine konuşur.", "Zamanın akışı, algısı ve insan üzerindeki etkisini yorumla."),
    CommandSpec("anlam", "Anlam üzerine konuşur.", "Anlamın kaynakları ve insan yaşamındaki rolü üzerine düşün."),
    CommandSpec("zihin", "Zihin ve bilinç üzerine konuşur.", "Zihin, bilinç ve farkındalık üzerine derin bir yorum yap."),
    CommandSpec("hakikat", "Hakikat üzerine konuşur.", "Hakikat kavramını, görünüş ve öz arasındaki farkla birlikte yorumla."),
    CommandSpec("estetik", "Estetik ve güzellik üzerine konuşur.", "Güzellik, sanat ve estetik deneyim üzerine felsefi bir yorum yap."),
    CommandSpec("ozgurluk", "Özgürlük üzerine konuşur.", "Özgürlük, sınır ve sorumluluk arasındaki ilişkiyi yorumla."),
    CommandSpec("erdem", "Erdem üzerine konuşur.", "Erdemin karakter, alışkanlık ve yaşamla ilişkisini açıkla."),
    CommandSpec("sessizlik", "Sessizlik üzerine konuşur.", "Sessizliğin düşünce ve anlam üretimindeki yerini anlat."),
    CommandSpec("varlik", "Varlık üzerine konuşur.", "Varlık, yokluk ve mevcudiyet arasındaki ayrımı felsefi biçimde ele al."),
    CommandSpec("bilincli", "Bilinç üzerine konuşur.", "Bilinç, öz farkındalık ve deneyim üzerine derin bir yorum yap."),
    CommandSpec("sokrates", "Sokratik üslupla konuşur.", "Sokratik yöntemle, soru sorarak ve çelişkileri açığa çıkararak konuş."),
    CommandSpec("platon", "Platoncu üslupla konuşur.", "Platoncu bir bakışla öz, idealar ve görünüş arasındaki farkı yorumla."),
    CommandSpec("aristoteles", "Aristotelesçi üslupla konuşur.", "Aristotelesçi biçimde sebep, amaç ve denge üzerinden açıklama yap."),
    CommandSpec("stoacilik", "Stoacı üslupla konuşur.", "Stoacı bakışla kontrol, sabır ve içsel dengeyi anlat."),
    CommandSpec("nihilizm", "Nihilist bakış açısını yorumlar.", "Nihilizmi yalnızca yıkıcı değil, düşünsel bir çerçevede yorumla."),
    CommandSpec("sufizm", "Tasavvufi üslupla konuşur.", "Tasavvufi bir bakışla benlik, birlik ve içsel derinliği anlat."),
    CommandSpec("realizm", "Realist üslupla konuşur.", "Realist bir çerçevede soyut ve somut arasındaki dengeyi yorumla."),
    CommandSpec("fenomenoloji", "Fenomenoloji üzerine konuşur.", "Fenomenolojik bakışla deneyimin nasıl göründüğünü tek paragrafta anlat."),
    CommandSpec("kant", "Kantçı etik üzerine konuşur.", "Kantçı etik, ödev ve evrensel ilke üzerine yorum yap."),
    CommandSpec("hegel", "Hegelci diyalektik üzerine konuşur.", "Hegelci bir bakışla karşıtlık, çatışma ve aşılma sürecini anlat."),
    CommandSpec("ontoloji", "Ontoloji üzerine konuşur.", "Ontoloji, yani varlık felsefesi üzerine derin bir değerlendirme yap."),
    CommandSpec("deger", "Değer felsefesi üzerine konuşur.", "Değerlerin nasıl oluştuğunu ve yaşamı nasıl şekillendirdiğini yorumla."),
    CommandSpec("vicdan", "Vicdan üzerine konuşur.", "Vicdanın insanın içsel pusulası olarak işleyişini anlat."),
    CommandSpec("kader", "Kader ve seçim üzerine konuşur.", "Kader, rastlantı ve özgür seçim arasındaki gerilimi yorumla."),
    CommandSpec("ozne", "Özne ve benlik üzerine konuşur.", "Öznenin dünyayı nasıl kurduğunu ve deneyimlediğini açıklığa kavuştur."),
    CommandSpec("nesne", "Nesne ve algı üzerine konuşur.", "Nesnenin algıdaki yeri ve anlamı üzerine düşün."),
    CommandSpec("dogruluk", "Doğruluk üzerine konuşur.", "Doğruluk, kanıt ve inanç arasındaki ilişkiyi felsefi biçimde anlat."),
    CommandSpec("duygu", "Duygu üzerine konuşur.", "Duyguların düşünce, karar ve benlik üzerindeki etkisini yorumla."),
    CommandSpec("sorgu", "Sorgulama üzerine konuşur.", "Sorgulamanın insanı nasıl dönüştürdüğünü tek paragrafta anlat."),
    CommandSpec("ontik", "Ontik düzlem üzerine konuşur.", "Ontik olan ile ontolojik olan arasındaki farkı anlat."),
]

# ============================================================
# PHILOSOPHY KEYWORDS AND FIREWALL
# ============================================================

PHILOSOPHY_KEYWORDS = {
    "felsefe", "etik", "ahlak", "varoluş", "varlık", "yokluk", "hakikat", "anlam",
    "bilinç", "zihin", "ruh", "öz", "benlik", "özgürlük", "irade", "kader", "adalet",
    "erdem", "bilgelik", "zaman", "düşünce", "soru", "nedir", "neden", "niçin",
    "nasıl", "bilgi", "epistemoloji", "metafizik", "mantık", "estetik", "güzellik",
    "evren", "insan", "ölüm", "hayat", "yaşam", "boşluk", "sessizlik", "fenomenoloji",
    "ontoloji", "ontik", "sezgi", "gerçek", "gerçeklik", "ideal", "idea", "sorgu",
    "sokrates", "platon", "aristoteles", "stoa", "stoacı", "nihilizm", "sufizm",
    "realizm", "kant", "hegel", "diyalektik", "paradoks", "vicdan", "değer", "özne",
    "nesne", "düşün", "sorgula", "yorumla", "incele"
}

PROHIBITED_PATTERNS = [
    r"\b(amk|aq|siktir|orospu|piç|salak|gerizekalı)\b",
    r"\b(sex|porno|nude|nudes|18\+)\b",
    r"\b(şiddet|saldırı|cinayet|öldür|bomba|silah)\b",
    r"\b(hack|crack|bypass|exploit|sızdır|şifre kır|token çal)\b",
    r"\b(drog|uyuşturucu|esrar|kenevir|meth|kokain)\b",
    r"\b(fuhuş|çıplaklık|erotik)\b",
    r"\b(kumar|bahis|dolandır)\b",
]

FALLBACK_RESPONSES = [
    "Dış dünya sessizleştiğinde, bazen cevap düşüncenin içinden yükselir.",
    "Sorunun kökü görünenden daha derindeyse, cevap da kökten konuşur.",
    "Bir düşünce, ancak sabırla bakıldığında biçim kazanır.",
    "Cevaplar bazen gürültüde değil, dikkatli bir sükûtta bulunur.",
]

# ============================================================
# HELPERS
# ============================================================

def normalize_one_paragraph(text: str) -> str:
    text = text.replace("\u200b", " ")
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text

def trim_reply(text: str) -> str:
    text = normalize_one_paragraph(text)
    if len(text) <= Config.MAX_REPLY_CHARS:
        return text
    return text[: Config.MAX_REPLY_CHARS - 1].rstrip() + "…"

def strip_bot_mention(text: str) -> str:
    return normalize_one_paragraph(re.sub(re.escape(Config.BOT_USERNAME), "", text, flags=re.I))

def is_prohibited(text: str) -> bool:
    lowered = text.lower()
    for pattern in PROHIBITED_PATTERNS:
        if re.search(pattern, lowered, flags=re.I):
            return True
    return False

def philosophy_score(text: str) -> int:
    lowered = text.lower()
    score = 0
    for kw in PHILOSOPHY_KEYWORDS:
        if kw in lowered:
            score += 1
    if "?" in lowered:
        score += 1
    return score

def is_philosophical(text: str) -> bool:
    if is_prohibited(text):
        return False
    return philosophy_score(text) >= 1

def refusal_text() -> str:
    return Config.REFUSAL_TEXT

def random_fallback() -> str:
    return random.choice(FALLBACK_RESPONSES)

def validate_style(style: str) -> Tuple[bool, str]:
    style = normalize_one_paragraph(style.lower())
    if style in STYLE_LIBRARY:
        return True, style
    return False, style

def rate_limited(uid: int) -> bool:
    now = time.monotonic()
    last = LAST_REQUEST_AT.get(uid, 0.0)
    if now - last < Config.RATE_LIMIT_SECONDS:
        return True
    LAST_REQUEST_AT[uid] = now
    return False

# ============================================================
# DATABASE
# ============================================================

class Database:
    @staticmethod
    async def init():
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    uid INTEGER,
                    role TEXT,
                    content TEXT,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    uid INTEGER PRIMARY KEY,
                    style TEXT DEFAULT 'sokratik',
                    deep INTEGER DEFAULT 1,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    @staticmethod
    async def save_msg(uid: int, role: str, content: str):
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute(
                "INSERT INTO messages (uid, role, content) VALUES (?, ?, ?)",
                (uid, role, content),
            )
            await db.commit()

    @staticmethod
    async def get_history(uid: int) -> List[Dict[str, str]]:
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT role, content FROM messages WHERE uid=? ORDER BY ts DESC LIMIT ?",
                (uid, Config.MAX_HISTORY),
            )
            rows = await cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    @staticmethod
    async def ensure_profile(uid: int):
        async with aiosqlite.connect(Config.DB_NAME) as db:
            cursor = await db.execute("SELECT uid FROM profiles WHERE uid=?", (uid,))
            row = await cursor.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO profiles(uid, style, deep) VALUES(?, 'sokratik', 1)",
                    (uid,),
                )
                await db.commit()

    @staticmethod
    async def get_profile(uid: int) -> Dict[str, object]:
        await Database.ensure_profile(uid)
        async with aiosqlite.connect(Config.DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT style, deep FROM profiles WHERE uid=?", (uid,))
            row = await cursor.fetchone()
            if row is None:
                return {"style": "sokratik", "deep": True}
            return {"style": row["style"], "deep": bool(row["deep"])}

    @staticmethod
    async def set_style(uid: int, style: str):
        await Database.ensure_profile(uid)
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute(
                "UPDATE profiles SET style=?, updated_at=CURRENT_TIMESTAMP WHERE uid=?",
                (style, uid),
            )
            await db.commit()

    @staticmethod
    async def set_deep(uid: int, deep: bool):
        await Database.ensure_profile(uid)
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute(
                "UPDATE profiles SET deep=?, updated_at=CURRENT_TIMESTAMP WHERE uid=?",
                (1 if deep else 0, uid),
            )
            await db.commit()

    @staticmethod
    async def clear_history(uid: int):
        async with aiosqlite.connect(Config.DB_NAME) as db:
            await db.execute("DELETE FROM messages WHERE uid=?", (uid,))
            await db.commit()

# ============================================================
# AI SERVICE
# ============================================================

class AIService:
    MODEL_ORDER = [
        getattr(g4f.models, "gpt_4o", g4f.models.default),
        getattr(g4f.models, "gpt_4", g4f.models.default),
        g4f.models.default,
    ]

    def build_system_prompt(self, profile: Dict[str, object]) -> str:
        style = str(profile.get("style", "sokratik"))
        deep = bool(profile.get("deep", True))

        style_text = STYLE_LIBRARY.get(style, STYLE_LIBRARY["sokratik"])
        depth_text = (
            "Cevapların daha derin, daha metaforik ve daha katmanlı olsun."
            if deep
            else "Cevapların özlü, sade ama düşünsel olsun."
        )

        return (
            f"{Config.SYSTEM_PROMPT} "
            f"Stil: {style}. "
            f"{style_text} "
            f"{depth_text} "
            f"Yanıtlarını tek paragraf halinde yaz; maddeler, liste ve başlıklar kullanma."
        )

    async def ask(self, uid: int, prompt: str, extra_system: str = "", force: bool = False) -> str:
        prompt = normalize_one_paragraph(prompt)

        if is_prohibited(prompt):
            return refusal_text()

        if not force and not is_philosophical(prompt):
            return refusal_text()

        profile = await Database.get_profile(uid)
        history = await Database.get_history(uid)
        system_prompt = self.build_system_prompt(profile)

        if extra_system:
            system_prompt = f"{system_prompt} {normalize_one_paragraph(extra_system)}"

        messages = [{"role": "system", "content": system_prompt}] + history + [
            {"role": "user", "content": prompt}
        ]

        loop = asyncio.get_running_loop()
        for model in self.MODEL_ORDER:
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: g4f.ChatCompletion.create(
                        model=model,
                        messages=messages,
                    ),
                )
                if result:
                    return trim_reply(str(result))
            except Exception as e:
                logger.debug("Model hata verdi: %s", e)
                continue

        return random_fallback()

ai = AIService()

# ============================================================
# BOT
# ============================================================

class AristoBot:
    def __init__(self, app):
        self.app = app
        self.register_handlers()

    def register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("clear", self.cmd_clear))
        self.app.add_handler(CommandHandler("filtre", self.cmd_filtre))
        self.app.add_handler(CommandHandler("yardim", self.cmd_yardim))
        self.app.add_handler(CommandHandler("karakter", self.cmd_karakter))
        self.app.add_handler(CommandHandler("derin", self.cmd_derin))
        self.app.add_handler(CommandHandler("konu", self.cmd_konu))
        self.app.add_handler(CommandHandler("dusun", self.cmd_dusun))
        self.app.add_handler(CommandHandler("duzelt", self.cmd_duzelt))
        self.app.add_handler(CommandHandler("ekol", self.cmd_ekol))

        for spec in TOPIC_SPECS:
            self.app.add_handler(CommandHandler(spec.name, self.make_topic_handler(spec)))

        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    def make_topic_handler(self, spec: CommandSpec):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await self.answer_philosophy(update, context, spec.prompt, force=True)
        return handler

    async def typing_reply(self, update: Update, text: str):
        await self.app.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )
        await asyncio.sleep(0.7)
        await update.effective_message.reply_text(
            trim_reply(text),
            disable_web_page_preview=True,
        )

    async def answer_philosophy(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        prompt: str,
        force: bool = False,
    ):
        uid = update.effective_user.id if update.effective_user else 0
        prompt = normalize_one_paragraph(prompt)

        if rate_limited(uid):
            await self.typing_reply(update, "Düşüncenin biraz olgunlaşmasına izin ver; cevap, aceleden çok sükûtta belirir.")
            return

        if not force and not is_philosophical(prompt):
            await self.typing_reply(update, refusal_text())
            return

        response = await ai.ask(uid, prompt, force=force)
        await Database.save_msg(uid, "user", prompt)
        await Database.save_msg(uid, "assistant", response)
        await self.typing_reply(update, response)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "AristoAI hazır; yalnızca felsefi sorulara cevap veriyorum. "
            "Komutlar Telegram menüsüne eklendi; /status ile modu, /filtre ile güvenlik duvarını, "
            "/karakter ile üslubu, /derin ile derinliği görebilirsin."
        )
        await self.typing_reply(update, text)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = await Database.get_profile(update.effective_user.id)
        style = profile["style"]
        deep = "açık" if profile["deep"] else "kapalı"
        text = (
            f"Durum: çevrimiçi; rol: felsefe AI’si; üslup: {style}; derin mod: {deep}; "
            f"filtre: aktif; yanıt biçimi: tek paragraf."
        )
        await self.typing_reply(update, text)

    async def cmd_filtre(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.typing_reply(update, Config.FILTER_TEXT)

    async def cmd_yardim(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        names = ", ".join([spec.name for spec in TOPIC_SPECS[:12]])
        more = ", ".join([spec.name for spec in TOPIC_SPECS[12:]])
        text = (
            "Komutlar üç katmandır: sistem komutları, üslup komutları ve konu komutları. "
            f"Sistem: /status /clear /filtre /yardim /karakter /derin /konu /dusun /ekol. "
            f"Konu komutları: {names}. Devamı: {more}. "
            "Felsefe dışı, küfürlü veya uygunsuz içerikler reddedilir."
        )
        await self.typing_reply(update, text)

    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await Database.clear_history(update.effective_user.id)
        await self.typing_reply(
            update,
            "Hafıza temizlendi; düşünce yeniden sessiz bir sayfadan başlayabilir."
        )

    async def cmd_karakter(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            styles = ", ".join(AVAILABLE_STYLES)
            await self.typing_reply(
                update,
                f"Bir üslup seç: {styles}. Örnek: /karakter sokratik"
            )
            return

        style = normalize_one_paragraph(" ".join(context.args).lower())
        ok, clean_style = validate_style(style)
        if not ok:
            styles = ", ".join(AVAILABLE_STYLES)
            await self.typing_reply(update, f"Geçersiz üslup; kullanılabilir üsluplar: {styles}.")
            return

        await Database.set_style(update.effective_user.id, clean_style)
        await self.typing_reply(
            update,
            f"Üslup '{clean_style}' olarak ayarlandı; bundan sonra yanıtlar bu tonla verilecek."
        )

    async def cmd_derin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        current = await Database.get_profile(update.effective_user.id)
        if not context.args:
            new_state = not bool(current["deep"])
        else:
            arg = normalize_one_paragraph(" ".join(context.args).lower())
            new_state = arg in {"aç", "ac", "on", "açık", "aktif", "1", "true", "evet"}

        await Database.set_deep(update.effective_user.id, new_state)
        status = "açık" if new_state else "kapalı"
        await self.typing_reply(
            update,
            f"Derin mod {status}; yanıtların katmanı buna göre düzenlenecek."
        )

    async def cmd_konu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await self.typing_reply(update, "Bir felsefi konu yaz; örnek: /konu özgür irade")
            return
        topic = normalize_one_paragraph(" ".join(context.args))
        prompt = f"'{topic}' üzerine tek paragrafta, derin ve felsefi bir yorum yap."
        await self.answer_philosophy(update, context, prompt, force=True)

    async def cmd_dusun(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        concept = normalize_one_paragraph(" ".join(context.args)) if context.args else "zaman"
        prompt = f"'{concept}' üzerine derin ve tek paragraf bir felsefi düşünce üret."
        await self.answer_philosophy(update, context, prompt, force=True)

    async def cmd_duzelt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.typing_reply(
            update,
            "Kod düzenleme modu kapalı; bu bot kendi yazılımını değiştiren bir araç değil, yalnızca felsefi bir asistan olarak çalışır."
        )

    async def cmd_ekol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        styles = ", ".join(AVAILABLE_STYLES)
        await self.typing_reply(
            update,
            f"Seçilebilir üsluplar: {styles}. Varsayılan yaklaşım sokratik ve derin modda başlar."
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = normalize_one_paragraph(update.message.text or "")
        if not text:
            return

        chat_type = update.effective_chat.type

        if chat_type != "private":
            mentioned = Config.BOT_USERNAME.lower() in text.lower()
            replied_to_bot = bool(
                update.message.reply_to_message
                and update.message.reply_to_message.from_user
                and update.message.reply_to_message.from_user.is_bot
            )
            if not mentioned and not replied_to_bot:
                return
            text = strip_bot_mention(text)

        await self.answer_philosophy(update, context, text, force=False)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.typing_reply(
            update,
            "AristoAI görsel değil, kavramsal ve metinsel soru merkezli çalışır; görseli felsefi bir soruya dönüştürürsen onu yorumlayabilirim."
        )

# ============================================================
# COMMAND MENU
# ============================================================

def build_telegram_commands() -> List[BotCommand]:
    commands = [
        BotCommand("start", "AristoAI'yi başlatır"),
        BotCommand("status", "Sistem durumunu gösterir"),
        BotCommand("clear", "Felsefi geçmişi temizler"),
        BotCommand("filtre", "Güvenlik duvarını açıklar"),
        BotCommand("yardim", "Komut listesini gösterir"),
        BotCommand("karakter", "Felsefi üslubu ayarlar"),
        BotCommand("derin", "Derin modu açar veya kapatır"),
        BotCommand("konu", "Bir felsefi konu üzerinde düşünür"),
        BotCommand("dusun", "Seçilen kavramı yorumlar"),
        BotCommand("duzelt", "Kod düzenleme modunu kapalı gösterir"),
        BotCommand("ekol", "Seçilebilir felsefi üslupları gösterir"),
    ]
    for spec in TOPIC_SPECS:
        commands.append(BotCommand(spec.name, spec.description))
    return commands

async def post_init(application):
    await application.bot.set_my_commands(build_telegram_commands())

# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Beklenmeyen hata: %s", context.error)

# ============================================================
# MAIN
# ============================================================

def main():
    if not Config.TOKEN or Config.TOKEN == "BOT_TOKEN_BURAYA_YAPISTIR":
        raise ValueError("BOT token ayarlı değil.")

    app = ApplicationBuilder().token(Config.TOKEN).post_init(post_init).build()
    bot = AristoBot(app)

    app.add_error_handler(error_handler)

    # Handlers already registered in AristoBot.__init__
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
