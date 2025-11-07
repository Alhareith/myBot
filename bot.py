import logging
import random
import asyncio
import sqlite3 
import os 
from telegram import Update, Poll
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    PollAnswerHandler
)

# -------------------------------------------------------------------
# ⚠️⚠️⚠️ انتبه جداً ⚠️⚠️⚠️
# اذهب إلى @BotFather، اضغط /revoke واحصل على توكن "جديد"
# هذا يقرأ التوكن من "متغيرات البيئة" في السيرفر
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("خطأ: لم يتم العثور على التوكن! تأكد من إضافته كـ TELEGRAM_TOKEN")
    exit()
# -------------------------------------------------------------------

# --- إعداد قاعدة البيانات ---
DB_FILE = os.path.join(os.path.dirname(__file__), "quiz_bot.db")

def initialize_db():
    """تهيئة قاعدة البيانات مع النظام الجديد (الذي كتبته أنت)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # الجداول الجديدة
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS public_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        created_by INTEGER,
        is_public BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        is_private BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        is_admin BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()
    logger.info(f"✅ قاعدة البيانات الجديدة جاهزة: {DB_FILE}")

# (اللوجر)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- نظام المستخدمين الجديد ---
async def register_user(user_id, username, first_name):
    """تسجيل مستخدم جديد (من الكود الخاص بك)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

# --- نظام الأسئلة الشخصية ---
async def save_user_question(user_id, question_data):
    """حفظ سؤال شخصي للمستخدم (من الكود الخاص بك)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_questions (user_id, question_text, options, correct_answer) VALUES (?, ?, ?, ?)",
        (user_id, question_data["question"], question_data["options_text"], question_data["correct_answer"])
    )
    question_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return question_id

# --- دالة التحليل (من الكود الخاص بك) ---
def parse_smart_question(message_text):
    try:
        lines = [line.strip() for line in message_text.strip().split('\n')]
        lines = [line for line in lines if line]
        
        if len(lines) < 3:
            return None, "يحتاج السؤال إلى سؤال واختيارين على الأقل مع إجابة صحيحة"
            
        question_lines = []
        i = 0
        while i < len(lines) and not any(line.startswith(('*', '- ', '1.', '2.', '3.', '4.')) for line in [lines[i]]):
            if lines[i]:
                question_lines.append(lines[i])
            i += 1
        
        if not question_lines:
            return None, "لم يتم العثور على نص السؤال"
            
        question = '\n'.join(question_lines)
        
        options = []
        correct_answer_text = None
        
        for j in range(i, len(lines)):
            line = lines[j]
            if line.startswith('*'):
                correct_answer_text = line[1:].strip()
                options.append(correct_answer_text)
            elif line and not line.startswith('#'):
                # تنظيف الخيارات من البادئات
                if line.startswith('- '):
                    line = line[2:]
                elif len(line) > 2 and line[1] == '.' and line[0].isdigit():
                    line = line[2:].strip()
                options.append(line.strip())
        
        if not question or not correct_answer_text or len(options) < 2:
            return None, "يحتاج السؤال إلى إجابة صحيحة واختيارين على الأقل"
            
        if len(set(options)) != len(options):
            return None, "يوجد خيارات مكررة"
            
        options_text = "|~|".join(options)
        return {
            "question": question,
            "options_text": options_text,
            "correct_answer": correct_answer_text
        }, None
        
    except Exception as e:
        logger.error(f"خطأ في التحليل: {e}")
        return None, f"خطأ في تحليل السؤال: {str(e)}"

# --- أمر /start محسن (من الكود الخاص بك) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    
    if update.message.chat.type == 'private':
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(id) FROM user_questions WHERE user_id = ?", (user.id,))
        user_questions_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(id) FROM public_questions")
        public_questions_count = cursor.fetchone()[0]
        conn.close()
        
        welcome_text = f"""
أهلاً بك يا {user.mention_html()}! 🤖

📊 **إحصاءاتك الشخصية:**
• أسئلتك الشخصية: {user_questions_count}
• الأسئلة العامة: {public_questions_count}

🎮 **كيفية الاستخدام:**

📝 **إضافة أسئلة:**
• أرسل سؤالاً مباشرة → يضاف لأسئلتك الشخصية
• /my_questions → عرض أسئلتك
• /delete_question [رقم] → حذف سؤال

🎯 **المسابقات (في المجموعات):**
• `/start_quiz` (لبدء جولة بأسئلتك الشخصية)
• `/start_quiz public` (لبدء جولة بالأسئلة العامة)
"""
        await update.message.reply_html(welcome_text)
    else:
        await update.message.reply_html(
            "أهلاً! أنا بوت المسابقات. أضفني كمدير ثم اكتب <code>/start_quiz</code> لبدء جولة."
        )

# --- معالج إضافة الأسئلة الجديد (من الكود الخاص بك) ---
async def handle_new_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة سؤال شخصي تلقائياً"""
    if update.message.chat.type != 'private':
        return
        
    user = update.effective_user
    message_text = update.message.text
    parsed_data, error_message = parse_smart_question(message_text)
    
    if not parsed_data:
        await update.message.reply_text(f"❌ {error_message}")
        return

    try:
        question_id = await save_user_question(user.id, parsed_data)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(id) FROM user_questions WHERE user_id = ?", (user.id,))
        user_questions_count = cursor.fetchone()[0]
        conn.close()
        
        success_message = f"""
✅ **تم حفظ السؤال في مجموعتك الشخصية!**

🆔 رقم السؤال: {question_id}
📊 أسئلتك الشخصية: {user_questions_count}

💡 لعرض كل أسئلتك: /my_questions
"""
        await update.message.reply_text(success_message)
        
    except Exception as e:
        logger.error(f"فشل حفظ السؤال الشخصي: {e}")
        await update.message.reply_text("❌ حدث خطأ في حفظ السؤال.")

# --- أمر عرض الأسئلة الشخصية (من الكود الخاص بك) ---
async def my_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        await update.message.reply_text("❌ هذا الأمر للخاص فقط.")
        return
        
    user = update.effective_user
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, question_text FROM user_questions WHERE user_id = ? ORDER BY id DESC",
            (user.id,)
        )
        questions = cursor.fetchall()
        conn.close()
        
        if not questions:
            await update.message.reply_text("📝 لا توجد أسئلة في مجموعتك الشخصية بعد.")
            return
        
        questions_text = "📋 **أسئلتك الشخصية:**\n\n"
        for q_id, question in questions:
            short_question = question.split('\n')[0] # السطر الأول فقط
            short_question = short_question[:50] + "..." if len(short_question) > 50 else short_question
            questions_text += f"🆔 <code>{q_id}</code>: {short_question}\n"
        
        questions_text += "\n🔧 لحذف سؤال: /delete_question [رقم]"
        await update.message.reply_html(questions_text)
        
    except Exception as e:
        logger.error(f"خطأ في عرض الأسئلة الشخصية: {e}")
        await update.message.reply_text("❌ حدث خطأ في جلب الأسئلة.")

# --- أمر حذف سؤال (من كود المرحلة 6) ---
async def delete_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(للمدير فقط) يحذف سؤالاً باستخدام الـ ID"""
    if update.message.chat.type != 'private':
        return
    
    user_id = update.effective_user.id
        
    try:
        question_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("الرجاء إرسال الأمر هكذا: /delete_question [ID]")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # التأكد أن السؤال موجود "ويخص" هذا المستخدم
        cursor.execute(
            "SELECT * FROM user_questions WHERE id = ? AND user_id = ?", 
            (question_id, user_id)
        )
        question = cursor.fetchone()
        
        if not question:
            await update.message.reply_text(f"لم يتم العثور على سؤال بالـ ID: {question_id} (أو أنه لا يخصك).")
            conn.close()
            return

        cursor.execute("DELETE FROM user_questions WHERE id = ? AND user_id = ?", (question_id, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ تم حذف السؤال (ID: {question_id}) بنجاح.")

    except Exception as e:
        logger.error(f"فشل حذف السؤال {question_id}: {e}")
        await update.message.reply_text("حدث خطأ أثناء حذف السؤال.")


# --- ⭐️⭐️⭐️ (هذا هو "المحرك" من المرحلة 5 - مضمون) ⭐️⭐️⭐️ ---
async def run_quiz_round(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    chat_data = context.application.chat_data[chat_id]
    try:
        while chat_data.get('questions_remaining') and chat_data.get('quiz_active'):
            question_data = chat_data['questions_remaining'].pop(0)
            question = question_data["question"]
            options = question_data["options_text"].split("|~|")
            correct_answer = question_data["correct_answer"]
            
            random.shuffle(options)
            correct_option_id = options.index(correct_answer)
            quiz_time = chat_data.get('quiz_time', 15)

            message = await context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_option_id,
                open_period=quiz_time,
                is_anonymous=False
            )
            
            if "poll_to_chat" not in context.bot_data:
                context.bot_data["poll_to_chat"] = {}
            context.bot_data["poll_to_chat"][message.poll.id] = chat_id
            if "polls" not in context.bot_data:
                context.bot_data["polls"] = {}
            context.bot_data["polls"][message.poll.id] = correct_option_id
            
            logger.info(f"أرسل السؤال {question} إلى المجموعة {chat_id}")
            await asyncio.sleep(quiz_time + 2)
            
        if chat_data.get('quiz_active', False):
            logger.info(f"المسابقة انتهت للمجموعة {chat_id}")
            await context.bot.send_message(chat_id, "🏁 انتهت جولة المسابقة!")
            await show_leaderboard(context=context, chat_id=chat_id)
        
        chat_data.clear()
    except Exception as e:
        logger.error(f"حدث خطأ فادح في جولة المسابقة للمجموعة {chat_id}: {e}")
        if chat_id in context.application.chat_data:
            context.application.chat_data[chat_id].clear()

# --- ⭐️⭐️⭐️ (أمر /start_quiz محسن - من الكود الخاص بك) ⭐️⭐️⭐️ ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == 'private':
        await update.message.reply_text("❌ ابدأ المسابقة في مجموعة.")
        return

    if context.chat_data.get('quiz_active'):
        await update.message.reply_text("⚠️ هناك جولة نشطة! /stop_quiz")
        return

    # تحديد نوع الأسئلة
    quiz_type = "user" # افتراضي: أسئلة المستخدم الشخصية
    if context.args and context.args[0].lower() in ["public", "all", "user"]:
        quiz_type = context.args[0].lower()
    
    quiz_time = 15
    num_questions_limit = None

    try:
        # /start_quiz [type] [time] [num]
        if len(context.args) >= 2:
            quiz_time = int(context.args[1])
            quiz_time = max(5, min(quiz_time, 60))
        if len(context.args) >= 3:
            num_questions_limit = int(context.args[2])
            num_questions_limit = max(1, num_questions_limit)
    except (ValueError, TypeError):
        await update.message.reply_text("⚠️ خطأ في النسق. استخدم: /start_quiz [public/all/user] [الوقت] [العدد]")
        return
        
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        questions_from_db = []
        quiz_title = ""
        
        if quiz_type == "public":
            cursor.execute("SELECT question_text, options, correct_answer FROM public_questions")
            questions_from_db = [{"question": row[0], "options_text": row[1], "correct_answer": row[2]} for row in cursor.fetchall()]
            quiz_title = "عامة"
        else: # (user or all)
            # جلب أسئلة المستخدم الذي بدأ الجولة
            user_id = update.effective_user.id
            cursor.execute("SELECT question_text, options, correct_answer FROM user_questions WHERE user_id = ?", (user_id,))
            questions_from_db = [{"question": row[0], "options_text": row[1], "correct_answer": row[2]} for row in cursor.fetchall()]
            quiz_title = "شخصية"
            
            if quiz_type == "all":
                cursor.execute("SELECT question_text, options, correct_answer FROM public_questions")
                public_questions = [{"question": row[0], "options_text": row[1], "correct_answer": row[2]} for row in cursor.fetchall()]
                questions_from_db.extend(public_questions)
                quiz_title = "شاملة"
        
        conn.close()
        
        if not questions_from_db:
            await update.message.reply_text(f"❌ لا توجد أسئلة {quiz_title} متاحة!")
            return
            
    except Exception as e:
        logger.error(f"فشل قراءة الأسئلة: {e}")
        await update.message.reply_text("❌ خطأ في قاعدة البيانات.")
        return

    # تحديد عدد الأسئلة
    if num_questions_limit:
        num_questions = min(num_questions_limit, len(questions_from_db))
    else:
        num_questions = len(questions_from_db)

    shuffled_questions = random.sample(questions_from_db, num_questions)
    
    context.chat_data.update({
        'questions_remaining': shuffled_questions,
        'quiz_time': quiz_time,
        'scores': {},
        'quiz_active': True
    })
    
    await update.message.reply_text(
        f"🎯 **بدء جولة مسابقة {quiz_title}!**\n\n"
        f"📝 عدد الأسئلة: {num_questions}\n"
        f"⏰ وقت كل سؤال: {quiz_time} ثانية\n"
        f"🔜 الجولة ستبدأ خلال 3 ثوانٍ..."
    )
    
    await asyncio.sleep(3)
    asyncio.create_task(run_quiz_round(context, chat.id))

# --- ⭐️⭐️⭐️ (معالج تسجيل النقاط - من المرحلة 5 - مضمون) ⭐️⭐️⭐️ ---
async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id
    user = poll_answer.user
    
    if "polls" not in context.bot_data or poll_id not in context.bot_data["polls"]:
        return
    correct_option_id = context.bot_data["polls"][poll_id]

    if "poll_to_chat" not in context.bot_data or poll_id not in context.bot_data["poll_to_chat"]:
        return
    chat_id = context.bot_data["poll_to_chat"][poll_id]

    if correct_option_id in poll_answer.option_ids:
        if chat_id in context.application.chat_data:
            chat_data = context.application.chat_data[chat_id]
            if chat_data.get('quiz_active', False):
                if 'scores' not in chat_data:
                     chat_data['scores'] = {}
                user_id = user.id
                chat_data['scores'][user_id] = chat_data['scores'].get(user_id, 0) + 1
                logger.info(f"المستخدم {user.id} أجاب صح في المجموعة {chat_id}! النقاط: {chat_data['scores'][user_id]}")

# --- ⭐️⭐️⭐️ (دالة عرض النتائج - من المرحلة 6 - مضمونة) ⭐️⭐️⭐️ ---
async def show_leaderboard(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if chat_id not in context.application.chat_data:
        chat_data = {}
    else:
        chat_data = context.application.chat_data[chat_id]
    scores = chat_data.get('scores', {})
    if not scores:
        await context.bot.send_message(chat_id, "📊 لا توجد نقاط مسجلة بعد في هذه الجولة.")
        return
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    leaderboard_text = "🏆 **النتائج النهائية** 🏆\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, score) in enumerate(sorted_scores):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        try:
            user_chat = await context.bot.get_chat(user_id)
            user_name = user_chat.first_name or f"المستخدم {user_id}"
        except Exception:
            user_name = f"المستخدم {user_id}"
        leaderboard_text += f"{medal} {user_name} - *{score} نقطة*\n"
    await context.bot.send_message(chat_id, leaderboard_text, parse_mode="Markdown")

# --- ⭐️⭐️⭐️ (أمر /stop_quiz - من المرحلة 5 - مضمون) ⭐️⭐️⭐️ ---
async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.chat_data.get('quiz_active', False):
        await update.message.reply_text("لا توجد جولة مسابقة شغالة أصلاً.")
        return
    context.chat_data['quiz_active'] = False 
    logger.info(f"تم إيقاف الجولة يدوياً في المجموعة {chat_id}")
    await update.message.reply_text("🛑 تم إيقاف الجولة.\nعرض النتائج الحالية...")
    await show_leaderboard(context=context, chat_id=chat_id)
    context.chat_data.clear()

# --- ⭐️⭐️⭐️ (الدالة الرئيسية - مدمجة ومُصلحة) ⭐️⭐️⭐️ ---
async def main():
    initialize_db()
    application = Application.builder().token(TOKEN).build()

    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("my_questions", my_questions))
    application.add_handler(CommandHandler("delete_question", delete_question))
    application.add_handler(CommandHandler("start_quiz", start_quiz))
    application.add_handler(CommandHandler("stop_quiz", stop_quiz))
    
    # (هذا المعالج كان مفقوداً في الكود الذي أرسلته أنت)
    application.add_handler(PollAnswerHandler(receive_poll_answer))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
        handle_new_question
    ))
    
    logger.info("البوت قيد التشغيل (وضع async)...")
    print("✅ البوت يعمل! أرسل /start")
    
    try:
        await application.initialize() 
        await application.start()
        await application.updater.start_polling()
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("إيقاف البوت...")
    finally:
        if application.updater:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("تم إيقاف البوت.")

if __name__ == "__main__":
    # ⭐️ (هذه هي الطريقة الصحيحة للتشغيل) ⭐️
    asyncio.run(main())