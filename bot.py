import os
import sqlite3
import telebot
import time
from telebot import types

TOKEN = "8589897793:AAHBcQqdMxUhpOWo5c-cB0J8dWMrBZy0qlI"
bot = telebot.TeleBot(TOKEN)

DB_PATH = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Drop old tables (we rebuild DB as requested)
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS accounts")
    cursor.execute("DROP TABLE IF EXISTS services")
    cursor.execute("DROP TABLE IF EXISTS categories")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS settings")
    cursor.execute("DROP TABLE IF EXISTS payment_methods")
    cursor.execute("DROP TABLE IF EXISTS deposit_requests")
    cursor.execute("DROP TABLE IF EXISTS force_subscribe_channels")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance REAL DEFAULT 0.0,
        lang TEXT DEFAULT 'ar',
        is_admin INTEGER DEFAULT 0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT,
        price REAL,
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_id INTEGER,
        account_data TEXT,
        is_sold INTEGER DEFAULT 0,
        sold_to INTEGER DEFAULT NULL,
        sold_at TEXT DEFAULT NULL, 
        FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_id INTEGER,
        account_id INTEGER,
        price REAL,
        ordered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(telegram_id),
        FOREIGN KEY(service_id) REFERENCES services(id),
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        details TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deposit_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        method_name TEXT,
        screenshot_file_id TEXT,
        amount REAL DEFAULT 0.0,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS force_subscribe_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE
    )
    """)
    
    # seed payment methods if empty
    cursor.execute("SELECT COUNT(*) FROM payment_methods")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO payment_methods (name, details) VALUES ('Binance Pay ID', '1147045004')")
        cursor.execute("INSERT INTO payment_methods (name, details) VALUES ('USDT BEP20 Address', '0xBb24d103248329913B5339F21D9194aE62118603')")
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def get_user(telegram_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return user

def register_user(telegram_id, username, first_name):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not user:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        is_admin = 1 if count == 0 else 0
        conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, is_admin) VALUES (?, ?, ?, ?)",
            (telegram_id, username, first_name, is_admin)
        )
        conn.commit()
    conn.close()

def format_balance(amount, telegram_id=None):
    return f"${amount:.2f}"

def get_kb(key, lang='ar'):
    translations = {
        'ar': {
            'home': '🏠 الرئيسية',
            'back': '⬅️ رجوع',
            'services': '🛍️ الخدمات والأقسام',
            'orders': '📦 طلباتي الأخيرة',
            'profile': '👤 حسابي الشخصي',
            'deposit': '💰 شحن الرصيد',
            'syrianadev': '👨‍💻 مطور البوت',
            'admin_panel': '🛠️ لوحة التحكم للادمن',
            'order_now': '🛒 شراء وتسليم تلقائي',
            'adm_stats': '📊 الإحصائيات العامة',
            'adm_users': '👤 إدارة المستخدمين',
            'adm_services': '📝 إدارة الخدمات',
            'adm_add_accounts': '➕ إضافة حسابات جديدة',
            'adm_cats': '📁 إدارة الأقسام',
            'adm_settings': '⚙️ الإعدادات العامة',
            'user_lang': '🌐 تغيير اللغة',
            'user_curr': '💵 تغيير العملة',
        },
        'en': {
            'home': '🏠 Home',
            'back': '⬅️ Back',
            'services': '🛍️ Services & Categories',
            'orders': '📦 My Orders',
            'profile': '👤 My Profile',
            'deposit': '💰 Add Balance',
            'syrianadev': '👨‍💻 Bot Developer',
            'admin_panel': '🛠️ Admin Panel',
            'order_now': '🛒 Buy & Deliver Instantly',
            'adm_stats': '📊 Statistics',
            'adm_users': '👤 Manage Users',
            'adm_services': '📝 Manage Services',
            'adm_add_accounts': '➕ Add New Accounts',
            'adm_cats': '📁 Manage Categories',
            'adm_settings': '⚙️ Settings',
            'user_lang': '🌐 Change Language',
            'user_curr': '💵 Change Currency',
        }
    }
    return translations.get(lang, translations['ar']).get(key, str(key))

SUB_CACHE = {}
CACHE_DURATION = 60

def get_force_subscribe_channels():
    conn = get_db_connection()
    channels = conn.execute("SELECT channel_id FROM force_subscribe_channels").fetchall()
    conn.close()
    return [ch['channel_id'] for ch in channels]

def is_subscribed(user_id):
    channels = get_force_subscribe_channels()
    if not channels:
        return True
    
    current_time = time.time()
    if user_id in SUB_CACHE:
        cache_time, cached_status = SUB_CACHE[user_id]
        if current_time - cache_time < CACHE_DURATION:
            return cached_status
    
    for channel in channels:
        channel_id = channel.strip()
        if not (channel_id.startswith("@") or channel_id.startswith("-100")):
            channel_id = "@" + channel_id
        
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                SUB_CACHE[user_id] = (current_time, False)
                return False
        except Exception as e:
            # If error checking membership, treat as not subscribed (safer)
            print(f"Subscription check error for user {user_id}: {e}")
            return False
    
    SUB_CACHE[user_id] = (current_time, True)
    return True

def send_force_sub_message(chat_id, user_id, lang='ar'):
    channels = get_force_subscribe_channels()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        clean_channel = ch.replace("@", "")
        invite_link = f"https://t.me/{clean_channel}"
        btn_join = types.InlineKeyboardButton(
            f"📢 اشترك: {ch}" if lang == 'ar' else f"📢 Join: {ch}",
            url=invite_link
        )
        markup.add(btn_join)
    
    btn_verify = types.InlineKeyboardButton(
        "🔄 تحقق من الاشتراك / Verify Subscription" if lang == 'ar' else "🔄 Verify Subscription",
        callback_data="verify_sub"
    )
    markup.add(btn_verify)
    
    text = (
        f"⚠️ **عذراً عزيزي، يجب عليك الاشتراك في القنوات أدناه!**\n\n"
        f"اشترك في كل القنوات ثم اضغط على زر التحقق 👇"
    ) if lang == 'ar' else (
        f"⚠️ **Sorry, you must subscribe to all channels below!**\n\n"
        f"Please join all channels then click the verification button 👇"
    )
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def check_sub_and_register(message):
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    register_user(telegram_id, username, first_name)
    user = get_user(telegram_id)
    lang = user['lang'] if user else 'ar'
    
    if not is_subscribed(telegram_id):
        send_force_sub_message(message.chat.id, telegram_id, lang)
        return False, user, lang
    return True, user, lang

# Keyboards & markups
def kb_home(lang='ar'):
    return types.InlineKeyboardButton(get_kb('home', lang), callback_data="home")

def kb_back(lang='ar'):
    return types.InlineKeyboardButton(get_kb('back', lang), callback_data="back")

def main_menu_keyboard(lang='ar', is_admin=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn_services = types.InlineKeyboardButton(get_kb('services', lang), callback_data="services")
    btn_orders = types.InlineKeyboardButton(get_kb('orders', lang), callback_data="my_orders")
    btn_profile = types.InlineKeyboardButton(get_kb('profile', lang), callback_data="profile")
    btn_deposit = types.InlineKeyboardButton(get_kb('deposit', lang), callback_data="deposit")
    btn_syrianadev = types.InlineKeyboardButton(get_kb('syrianadev', lang), callback_data="developer")
    
    markup.row(btn_services, btn_orders)
    markup.row(btn_profile, btn_deposit)
    
    if is_admin:
        btn_admin = types.InlineKeyboardButton(get_kb('admin_panel', lang), callback_data="admin_panel")
        markup.row(btn_admin)
        
    markup.row(btn_syrianadev)
    return markup

def admin_menu_keyboard(lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn_stats = types.InlineKeyboardButton(get_kb('adm_stats', lang), callback_data="adm_stats")
    btn_users = types.InlineKeyboardButton(get_kb('adm_users', lang), callback_data="adm_users")
    btn_add_accts = types.InlineKeyboardButton(get_kb('adm_add_accounts', lang), callback_data="adm_add_accts")
    btn_services = types.InlineKeyboardButton(get_kb('adm_services', lang), callback_data="adm_services")
    btn_cats = types.InlineKeyboardButton(get_kb('adm_cats', lang), callback_data="adm_cats")
    btn_add_service = types.InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data="adm_add_new_service")
    btn_forcesub = types.InlineKeyboardButton("📢 القنوات الإجبارية" if lang=='ar' else "📢 Force Subscribe", callback_data="adm_forcesub")
    btn_payments = types.InlineKeyboardButton("💳 طرق الدفع" if lang=='ar' else "💳 Payment Methods", callback_data="adm_payments")
    btn_broadcast = types.InlineKeyboardButton("📢 إذاعة رسالة / Broadcast" if lang=='ar' else "📢 Broadcast Message", callback_data="adm_broadcast")
    
    # include add service button visibly
    markup.add(btn_stats, btn_users, btn_add_accts, btn_services, btn_cats, btn_add_service, btn_forcesub, btn_payments)
    markup.row(btn_broadcast)
    markup.row(kb_home(lang))
    return markup

def back_keyboard(lang='ar'):
    markup = types.InlineKeyboardMarkup()
    markup.add(kb_home(lang))
    return markup

def categories_markup(categories, lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat_{cat['id']}"))
    markup.row(kb_home(lang))
    return markup

def subcategories_markup(subcategories, services, lang='ar', telegram_id=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for sub in subcategories:
        markup.add(types.InlineKeyboardButton(f"📁 {sub['name']}", callback_data=f"sub_{sub['id']}"))
    for ser in services:
        markup.add(types.InlineKeyboardButton(f"🛍️ {ser['name']} | {format_balance(ser['price'], telegram_id)}", callback_data=f"ser_{ser['id']}"))
    markup.row(types.InlineKeyboardButton(get_kb('back', lang), callback_data="services"), kb_home(lang))
    return markup

def service_details_markup(service_id, lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(get_kb('order_now', lang), callback_data=f"buy_{service_id}"))
    
    conn = get_db_connection()
    service = conn.execute("SELECT category_id FROM services WHERE id = ?", (service_id,)).fetchone()
    conn.close()
    
    back_target = f"cat_{service['category_id']}" if service else "services"
    markup.row(types.InlineKeyboardButton(get_kb('back', lang), callback_data=back_target), kb_home(lang))
    return markup

def profile_keyboard(lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_lang = types.InlineKeyboardButton(get_kb('user_lang', lang), callback_data="set_lang")
    btn_curr = types.InlineKeyboardButton(get_kb('user_curr', lang), callback_data="set_curr")
    
    markup.add(btn_lang, btn_curr)
    markup.row(kb_home(lang))
    return markup

def language_selection_markup(selected=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    ar_txt = "🇯🇴 العربية" + (" ✅" if selected == 'ar' else "")
    en_txt = "🇺🇸 English" + (" ✅" if selected == 'en' else "")
    markup.add(
        types.InlineKeyboardButton(ar_txt, callback_data="set_lang_ar"),
        types.InlineKeyboardButton(en_txt, callback_data="set_lang_en")
    )
    markup.row(kb_home('ar'))
    return_markup = markup
    return markup

def admin_users_list_markup(users, page=1):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for u in users:
        markup.add(types.InlineKeyboardButton(f"👤 {u['first_name']} (@{u['username'] or 'None'}) - Balance: {format_balance(u['balance'])}", callback_data=f"adm_view_user_{u['telegram_id']}"))
    
    nav_btns = []
    if page > 1:
        nav_btns.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"adm_users_page_{page-1}"))
    nav_btns.append(types.InlineKeyboardButton(f"صفحة {page}", callback_data="none"))
    nav_btns.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"adm_users_page_{page+1}"))
    
    markup.row(*nav_btns)
    markup.row(types.InlineKeyboardButton("🛠️ لوحة التحكم", callback_data="admin_panel"), kb_home('ar'))
    return markup

def admin_user_view_markup(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💰 تعديل الرصيد / Adjust Balance", callback_data=f"adm_edit_bal_{user_id}"),
        types.InlineKeyboardButton("🛡️ ترقية/تنزيل رتبة مشرف / Toggle Admin Status", callback_data=f"adm_toggle_admin_{user_id}"),
        types.InlineKeyboardButton("📜 سجل المشتريات / View Orders", callback_data=f"adm_user_ords_{user_id}")
    )
    markup.row(types.InlineKeyboardButton("⬅️ رجوع للمستخدمين", callback_data="adm_users"), kb_home('ar'))
    return markup

def admin_categories_markup(categories):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        btn_name = types.InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"adm_cat_view_{cat['id']}")
        markup.add(btn_name)
    
    markup.add(types.InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="adm_new_cat"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel"))
    return markup

def admin_category_view_markup(cat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"adm_edit_cat_{cat_id}"),
        types.InlineKeyboardButton("❌ حذف القسم", callback_data=f"adm_del_cat_ask_{cat_id}")
    )
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="adm_cats"))
    return markup

def admin_services_categories_markup(categories):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"adm_manage_services_under_{cat['id']}"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel"))
    return markup

def admin_services_list_markup(services, cat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ser in services:
        btn_name = types.InlineKeyboardButton(f"🛍️ {ser['name']} ({format_balance(ser['price'])})", callback_data=f"adm_ser_view_{ser['id']}")
        markup.add(btn_name)
        
    markup.add(types.InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data=f"adm_new_service_under_{cat_id}"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع للأقسام", callback_data="adm_services"))
    return markup

def admin_service_view_markup(service_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل", callback_data=f"adm_edit_ser_{service_id}"),
        types.InlineKeyboardButton("❌ حذف", callback_data=f"adm_del_ser_ask_{service_id}"),
        types.InlineKeyboardButton("🔑 إدارة الحسابات", callback_data=f"adm_accounts_{service_id}")
    )
    
    conn = get_db_connection()
    service = conn.execute("SELECT category_id FROM services WHERE id = ?", (service_id,)).fetchone()
    conn.close()
    
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data=f"adm_manage_services_under_{service['category_id']}"))
    return markup

def admin_accounts_markup(accounts, service_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for acc in accounts:
        btn_text = f"🔹 {acc['account_data'][:30]}..." if len(acc['account_data']) > 30 else f"🔹 {acc['account_data']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"adm_acc_view_{acc['id']}"))
    
    markup.add(types.InlineKeyboardButton("➕ إضافة حساب جديد", callback_data=f"adm_new_acc_{service_id}"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data=f"adm_ser_view_{service_id}"))
    return markup

def admin_account_view_markup(acc_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✏️ تعديل البيانات", callback_data=f"adm_edit_acc_{acc_id}"),
        types.InlineKeyboardButton("❌ حذف الحساب", callback_data=f"adm_del_acc_ask_{acc_id}")
    )
    return markup

def admin_forcesub_channels_markup(channels):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        markup.add(types.InlineKeyboardButton(f"📢 {ch['channel_id']}", callback_data=f"adm_del_ch_ask_{ch['id']}"))
    
    markup.add(types.InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="adm_new_forcesub_ch"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel"))
    return_markup = markup
    return markup

def admin_payments_markup(methods):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for m in methods:
        btn_name = types.InlineKeyboardButton(f"💳 {m['name']}", callback_data="none")
        btn_del = types.InlineKeyboardButton("❌ حذف", callback_data=f"adm_del_pay_ask_{m['id']}")
        markup.row(btn_name, btn_del)
    
    markup.add(types.InlineKeyboardButton("➕ إضافة طريقة دفع جديدة", callback_data="adm_new_payment"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel"))
    return_markup = markup
    return markup

def admin_payment_delete_confirm_markup(method_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔥 نعم، احذف", callback_data=f"adm_del_pay_confirm_{method_id}"),
        types.InlineKeyboardButton("⬅️ إلغاء", callback_data="adm_payments")
    )
    return markup

def user_deposit_methods_markup(methods, lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for m in methods:
        markup.add(types.InlineKeyboardButton(f"💳 {m['name']}", callback_data=f"dep_method_{m['id']}"))
    markup.row(kb_home(lang))
    return_markup = markup
    return markup

def user_deposit_method_details_markup(method_id, lang='ar'):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.row(types.InlineKeyboardButton(get_kb('back', lang), callback_data="deposit"), kb_home(lang))
    return markup

def admin_deposit_review_markup(request_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ موافقة وشحن رصيد", callback_data=f"adm_dep_app_{request_id}"),
        types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"adm_dep_dec_{request_id}")
    )
    return_markup = markup
    return markup

# ---------------- Bot handlers ----------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    allowed, user, lang = check_sub_and_register(message)
    if not allowed:
        return
        
    is_admin = user['is_admin'] == 1 if user else False
    
    welcome_text = (
        f"🙋‍♂️ أهلاً بك {message.from_user.first_name} في بوت البيع التلقائي للحسابات!\n\n"
        f"💵 رصيدك الحالي: {format_balance(user['balance'] if user else 0.0)}\n\n"
        "الرجاء اختيار أحد الخيارات أدناه:"
    ) if lang == 'ar' else (
        f"🙋‍♂️ Welcome {message.from_user.first_name} to the Automatic Account Delivery Bot!\n\n"
        f"💵 Your Current Balance: {format_balance(user['balance'] if user else 0.0)}\n\n"
        "Please select one of the options below:"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=main_menu_keyboard(lang, is_admin)
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    telegram_id = call.from_user.id
    user = get_user(telegram_id)
    
    if not user:
        register_user(telegram_id, call.from_user.username, call.from_user.first_name)
        user = get_user(telegram_id)
        
    lang = user['lang'] if user else 'ar'
    is_admin = user['is_admin'] == 1 if user else False
    
    data = call.data
    
    if data == "verify_sub":
        if is_subscribed(telegram_id):
            bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح! شكراً لاشتراكك.", show_alert=True)
            welcome_text = (
                f"🙋‍♂️ أهلاً بك في القائمة الرئيسية للحسابات!\n\n"
                f"💵 رصيدك الحالي: {format_balance(user['balance'])}\n\n"
This content is huge; the create_or_update_file will likely accept. Need to include sha param. Provide sha from getfile: 9af2d4f786239558a14de0f504cb4851c5a25283. We must include sha parameter. In previous call, we omitted and got error. Now include sha. Our call currently doesn't include sha. The tool will likely error again. We must call with sha. Let's redo: call create_or_update_file with sha equals blobsha. But we already made a call without sha; tool returned error earlier. Now this call is actually included in functions.create_or_update_file call with content with long string; the tool responded that file requires sha. We need to re-run with sha. So make another create_or_update_file with same content and sha param set. Use functions.create_or_update_file tool. Let's do that. I'll call with sha = 