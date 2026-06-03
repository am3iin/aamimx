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
    
    # Drop old tables
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
    btn_forcesub = types.InlineKeyboardButton("📢 القنوات الإجبارية" if lang=='ar' else "📢 Force Subscribe", callback_data="adm_forcesub")
    btn_payments = types.InlineKeyboardButton("💳 طرق الدفع" if lang=='ar' else "💳 Payment Methods", callback_data="adm_payments")
    btn_broadcast = types.InlineKeyboardButton("📢 إذاعة رسالة / Broadcast" if lang=='ar' else "📢 Broadcast Message", callback_data="adm_broadcast")
    
    markup.add(btn_stats, btn_users, btn_add_accts, btn_services, btn_cats, btn_forcesub, btn_payments)
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
    return markup

def admin_payments_markup(methods):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for m in methods:
        btn_name = types.InlineKeyboardButton(f"💳 {m['name']}", callback_data="none")
        btn_del = types.InlineKeyboardButton("❌ حذف", callback_data=f"adm_del_pay_ask_{m['id']}")
        markup.row(btn_name, btn_del)
    
    markup.add(types.InlineKeyboardButton("➕ إضافة طريقة دفع جديدة", callback_data="adm_new_payment"))
    markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel"))
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
    return markup

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
                "الرجاء اختيار أحد الخيارات أدناه:"
            ) if lang == 'ar' else (
                f"🙋‍♂️ Welcome to the Main Menu!\n\n"
                f"💵 Your Current Balance: {format_balance(user['balance'])}\n\n"
                "Please select one of the options below:"
            )
            bot.send_message(call.message.chat.id, welcome_text, reply_markup=main_menu_keyboard(lang, is_admin))
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك في القنوات بعد! يرجى الاشتراك أولاً.", show_alert=True)
        return

    if not is_subscribed(telegram_id):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_force_sub_message(call.message.chat.id, telegram_id, lang)
        return
        
    if data == "home":
        welcome_text = (
            f"🙋‍♂️ أهلاً بك في القائمة الرئيسية للحسابات!\n\n"
            f"💵 رصيدك الحالي: {format_balance(user['balance'])}\n\n"
            "الرجاء اختيار أحد الخيارات أدناه:"
        ) if lang == 'ar' else (
            f"🙋‍♂️ Welcome to the Main Menu!\n\n"
            f"💵 Your Current Balance: {format_balance(user['balance'])}\n\n"
            "Please select one of the options below:"
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=welcome_text,
            reply_markup=main_menu_keyboard(lang, is_admin)
        )
        
    elif data == "services":
        conn = get_db_connection()
        categories = conn.execute("SELECT * FROM categories").fetchall()
        conn.close()
        
        msg_text = "📁 الأقسام المتاحة لدينا:" if lang == 'ar' else "📁 Available Categories:"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=categories_markup(categories, lang)
        )
        
    elif data.startswith("cat_"):
        cat_id = int(data.split("_")[1])
        
        conn = get_db_connection()
        category = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
        services = conn.execute("SELECT * FROM services WHERE category_id = ?", (cat_id,)).fetchall()
        conn.close()
        
        if not category:
            bot.answer_callback_query(call.id, "Category not found!")
            return
            
        msg_text = f"🛍️ الخدمات المتاحة في قسم: {category['name']}" if lang == 'ar' else f"🛍️ Available services in: {category['name']}"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=subcategories_markup([], services, lang, telegram_id)
        )
        
    elif data.startswith("ser_"):
        service_id = int(data.split("_")[1])
        
        conn = get_db_connection()
        service = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        stock = conn.execute("SELECT COUNT(*) FROM accounts WHERE service_id = ? AND is_sold = 0", (service_id,)).fetchone()[0]
        conn.close()
        
        if not service:
            bot.answer_callback_query(call.id, "Service not found!")
            return
            
        msg_text = (
            f"ℹ️ تفاصيل الخدمة:\n\n"
            f"🏷️ الاسم: {service['name']}\n"
            f"💵 السعر: {format_balance(service['price'])}\n"
            f"📦 المخزون المتوفر: {stock} حساب\n\n"
            f"⚠️ عند الضغط على زر الشراء، سيتم خصم القيمة وتسليمك الحساب تلقائياً."
        ) if lang == 'ar' else (
            f"ℹ️ Service Details:\n\n"
            f"🏷️ Name: {service['name']}\n"
            f"💵 Price: {format_balance(service['price'])}\n"
            f"📦 Available Stock: {stock} accounts\n\n"
            f"⚠️ Clicking the purchase button will deduct the price and deliver the account details instantly."
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=service_details_markup(service_id, lang)
        )
        
    elif data.startswith("buy_"):
        service_id = int(data.split("_")[1])
        
        conn = get_db_connection()
        service = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        
        if not service:
            conn.close()
            bot.answer_callback_query(call.id, "الخدمة غير متوفرة / Service not found!")
            return
            
        price = service['price']
        user_balance = user['balance']
        
        if user_balance < price:
            conn.close()
            msg = "❌ رصيدك غير كافٍ لشراء هذا الحساب. يرجى شحن رصيدك." if lang == 'ar' else "❌ Insufficient balance to buy this account. Please recharge."
            bot.answer_callback_query(call.id, msg, show_alert=True)
            return
            
        account = conn.execute("SELECT * FROM accounts WHERE service_id = ? AND is_sold = 0 LIMIT 1", (service_id,)).fetchone()        
        if not account:
            conn.close()
            msg = "❌ نعتذر، نفذت الكمية الخاصة بهذه الخدمة حالياً." if lang == 'ar' else "❌ Sorry, this service is currently out of stock."
            bot.answer_callback_query(call.id, msg, show_alert=True)
            return
            
        try:
            conn.execute("BEGIN TRANSACTION")
            
            conn.execute("UPDATE users SET balance = balance - ? WHERE telegram_id = ?", (price, telegram_id))
            
            conn.execute(
                "UPDATE accounts SET is_sold = 1, sold_to = ?, sold_at = CURRENT_TIMESTAMP WHERE id = ?",
                (telegram_id, account['id'])
            )
            
            conn.execute(
                "INSERT INTO orders (user_id, service_id, account_id, price) VALUES (?, ?, ?, ?)",
                (telegram_id, service_id, account['id'], price)
            )
            
            conn.commit()
            
            delivery_msg = (
                f"✅ تم الشراء بنجاح!\n\n"
                f"📦 اسم الخدمة: {service['name']}\n"
                f"💵 السعر المخصوم: {format_balance(price)}\n"
                f"🔑 تفاصيل حسابك المستلم:\n"
                f"<code>{account['account_data']}</code>\n\n"
                f"شكراً لتعاملك معنا!"
            ) if lang == 'ar' else (
                f"✅ Purchase Successful!\n\n"
                f"📦 Service Name: {service['name']}\n"
                f"💵 Deducted Price: {format_balance(price)}\n"
                f"🔑 Your Account Details:\n"
                f"<code>{account['account_data']}</code>\n\n"
                f"Thank you for choosing us!"
            )
            
            bot.answer_callback_query(call.id, "✅ تم الشراء بنجاح!" if lang == 'ar' else "✅ Purchase Successful!")
            bot.send_message(call.message.chat.id, delivery_msg, parse_mode="HTML")
            
            updated_user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
            welcome_text = (
                f"🙋‍♂️ أهلاً بك في القائمة الرئيسية للحسابات!\n\n"
                f"💵 رصيدك الحالي: {format_balance(updated_user['balance'])}\n\n"
                "الرجاء اختيار أحد الخيارات أدناه:"
            ) if lang == 'ar' else (
                f"🙋‍♂️ Welcome to the Main Menu!\n\n"
                f"💵 Your Current Balance: {format_balance(updated_user['balance'])}\n\n"
                "Please select one of the options below:"
            )
            bot.send_message(call.message.chat.id, welcome_text, reply_markup=main_menu_keyboard(lang, is_admin))
            
        except Exception as e:
            conn.rollback()
            bot.answer_callback_query(call.id, "حدث خطأ أثناء المعالجة / Error during processing.", show_alert=True)
            print("Transaction Error:", e)
        finally:
            conn.close()
            
    elif data == "profile":
        msg_text = (
            f"👤 حسابي الشخصي:\n\n"
            f"🆔 معرف التلغرام: <code>{user['telegram_id']}</code>\n"
            f"💵 رصيدك الحالي: {format_balance(user['balance'])}\n"
            f"🌐 لغة البوت الحالية: {'العربية' if lang == 'ar' else 'English'}"
        ) if lang == 'ar' else (
            f"👤 My Profile:\n\n"
            f"🆔 Telegram ID: <code>{user['telegram_id']}</code>\n"
            f"💵 Current Balance: {format_balance(user['balance'])}\n"
            f"🌐 Bot Language: {'Arabic' if lang == 'ar' else 'English'}"
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=profile_keyboard(lang),
            parse_mode="HTML"
        )
        
    elif data == "my_orders":
        conn = get_db_connection()
        orders = conn.execute(
            "SELECT o.price, o.ordered_at, s.name, a.account_data "
            "FROM orders o JOIN services s ON o.service_id = s.id "
            "JOIN accounts a ON o.account_id = a.id "
            "WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 10",
            (telegram_id,)
        ).fetchall()
        conn.close()
        
        if not orders:
            msg_text = "📦 ليس لديك أي طلبات سابقة حتى الآن." if lang == 'ar' else "📦 You don't have any past orders yet."
        else:
            msg_text = "📦 آخر 10 طلبات لك:\n\n" if lang == 'ar' else "📦 Your last 10 orders:\n\n"
            for o in orders:
                msg_text += (
                    f"🔹 <b>{o['name']}</b> ({format_balance(o['price'])})\n"
                    f"📅 التاريخ: {o['ordered_at']}\n"
                    f"🔑 الحساب: <code>{o['account_data']}</code>\n"
                    f"--------------------\n"
                ) if lang == 'ar' else (
                    f"🔹 <b>{o['name']}</b> ({format_balance(o['price'])})\n"
                    f"📅 Date: {o['ordered_at']}\n"
                    f"🔑 Account: <code>{o['account_data']}</code>\n"
                    f"--------------------\n"
                )
                
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=back_keyboard(lang),
            parse_mode="HTML"
        )
        
    elif data == "deposit":
        conn = get_db_connection()
        methods = conn.execute("SELECT * FROM payment_methods").fetchall()
        conn.close()
        
        if not methods:
            msg_text = (
                f"💰 شحن رصيد الحساب:\n\n"
                f"لشحن رصيدك، يرجى التواصل مع الدعم الفني مباشرة.\n\n"
                f"🆔 معرف حسابك: <code>{telegram_id}</code>"
            ) if lang == 'ar' else (
                f"💰 Recharge Balance:\n\n"
                f"To top up your balance, please contact support.\n\n"
                f"🆔 Your Telegram ID: <code>{telegram_id}</code>"
            )
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg_text,
                reply_markup=back_keyboard(lang),
                parse_mode="HTML"
            )
        else:
            msg_text = (
                f"💰 **شحن الرصيد التلقائي**\n\n"
                f"الرجاء اختيار طريقة الدفع:"
            ) if lang == 'ar' else (
                f"💰 **Recharge Balance**\n\n"
                f"Please select your payment method:"
            )
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=msg_text,
                reply_markup=user_deposit_methods_markup(methods, lang),
                parse_mode="Markdown"
            )

    elif data.startswith("dep_method_"):
        method_id = int(data.split("_")[2])
        
        conn = get_db_connection()
        method = conn.execute("SELECT * FROM payment_methods WHERE id = ?", (method_id,)).fetchone()
        conn.close()
        
        if not method:
            bot.answer_callback_query(call.id, "طريقة الدفع غير متوفرة!")
            return
            
        msg_text = (
            f"💳 **طريقة الدفع: {method['name']}**\n\n"
            f"يرجى التحويل إلى:\n"
            f"<code>{method['details']}</code>\n\n"
            f"📝 **تعليمات:**\n"
            f"1. نسخ العنوان أعلاه\n"
            f"2. التقط صورة الإيصال\n"
            f"3. أرسل الصورة للبوت"
        ) if lang == 'ar' else (
            f"💳 **Payment Method: {method['name']}**\n\n"
            f"Transfer to:\n"
            f"<code>{method['details']}</code>\n\n"
            f"📝 **Instructions:**\n"
            f"1. Copy the address above\n"
            f"2. Take a screenshot\n"
            f"3. Send the screenshot to the bot"
        )
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
            
        msg = bot.send_message(
            call.message.chat.id,
            msg_text,
            reply_markup=user_deposit_method_details_markup(method_id, lang),
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_user_deposit_screenshot, method['name'], lang)
        
    elif data == "developer":
        msg_text = (
            "👨‍💻 مطور البوت:\n\n"
            "تم برمجة هذا البوت بواسطة AMIN AL KING.\n"
            "للاستفسار: @oldamin"
        ) if lang == 'ar' else (
            "👨‍💻 Developer:\n\n"
            "This bot is developed by AMIN AL KING.\n"
            "Contact: @oldamin"
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=back_keyboard(lang)
        )
        
    elif data == "set_lang":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🌐 اختر اللغة / Select Language:",
            reply_markup=language_selection_markup(lang)
        )
        
    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        conn = get_db_connection()
        conn.execute("UPDATE users SET lang = ? WHERE telegram_id = ?", (new_lang, telegram_id))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم التحديث!" if new_lang == 'ar' else "✅ Updated!")
        
        welcome_text = (
            f"🙋‍♂️ أهلاً بك!\n\n"
            f"💵 رصيدك: {format_balance(user['balance'])}"
        ) if new_lang == 'ar' else (
            f"🙋‍♂️ Welcome!\n\n"
            f"💵 Balance: {format_balance(user['balance'])}"
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=welcome_text,
            reply_markup=main_menu_keyboard(new_lang, is_admin)
        )
        
    elif data == "set_curr":
        bot.answer_callback_query(call.id, "USD فقط / USD only", show_alert=True)
    
    # ============ ADMIN PANEL ============
    elif data == "admin_panel":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🛠️ لوحة تحكم الإدارة:",
            reply_markup=admin_menu_keyboard(lang)
        )
        
    elif data == "adm_stats":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        conn = get_db_connection()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_services = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        total_accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        unsold_accounts = conn.execute("SELECT COUNT(*) FROM accounts WHERE is_sold = 0").fetchone()[0]
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        revenue = conn.execute("SELECT SUM(price) FROM orders").fetchone()[0] or 0.0
        conn.close()
        
        stats_text = (
            f"📊 الإحصائيات:\n\n"
            f"👥 الأعضاء: {total_users}\n"
            f"🛍️ الخدمات: {total_services}\n"
            f"🔑 الحسابات: {total_accounts}\n"
            f"📦 المتاحة: {unsold_accounts}\n"
            f"📦 المبيعات: {total_orders}\n"
            f"💵 الإيرادات: {format_balance(revenue)}"
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=stats_text,
            reply_markup=types.InlineKeyboardMarkup().row(
                types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel")
            )
        )
        
    elif data == "adm_users" or data.startswith("adm_users_page_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        page = 1
        if data.startswith("adm_users_page_"):
            page = int(data.split("_")[3])
            
        conn = get_db_connection()
        offset = (page - 1) * 8
        users_list = conn.execute("SELECT * FROM users LIMIT 8 OFFSET ?", (offset,)).fetchall()
        conn.close()
        
        if not users_list and page > 1:
            bot.answer_callback_query(call.id, "لا توجد صفحات إضافية")
            return
            
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="👥 المستخدمون:",
            reply_markup=admin_users_list_markup(users_list, page)
        )
        
    elif data.startswith("adm_view_user_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        target_id = int(data.split("_")[3])
        target_user = get_user(target_id)
        
        if not target_user:
            bot.answer_callback_query(call.id, "المستخدم غير موجود")
            return
            
        user_info = (
            f"👤 معلومات العضو:\n\n"
            f"🆔 المعرف: <code>{target_user['telegram_id']}</code>\n"
            f"🏷️ الاسم: {target_user['first_name']}\n"
            f"👤 اليوزر: @{target_user['username'] or 'لا يوجد'}\n"
            f"💵 الرصيد: {format_balance(target_user['balance'])}\n"
            f"🛡️ مشرف: {'نعم' if target_user['is_admin'] == 1 else 'لا'}"
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=user_info,
            reply_markup=admin_user_view_markup(target_id),
            parse_mode="HTML"
        )
        
    elif data.startswith("adm_toggle_admin_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        target_id = int(data.split("_")[3])
        target_user = get_user(target_id)
        
        if target_id == telegram_id:
            bot.answer_callback_query(call.id, "لا يمكنك تنزيل رتبتك!", show_alert=True)
            return
            
        new_status = 0 if target_user['is_admin'] == 1 else 1
        conn = get_db_connection()
        conn.execute("UPDATE users SET is_admin = ? WHERE telegram_id = ?", (new_status, target_id))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم التحديث!")
        call.data = f"adm_view_user_{target_id}"
        callback_listener(call)
        
    elif data.startswith("adm_edit_bal_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        target_id = int(data.split("_")[3])
        msg = bot.send_message(call.message.chat.id, "✍️ أرسل القيمة (إضافة موجب، خصم سالب):")
        bot.register_next_step_handler(msg, process_admin_balance_edit, target_id)
        
    elif data.startswith("adm_user_ords_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        target_id = int(data.split("_")[3])
        conn = get_db_connection()
        orders = conn.execute(
            "SELECT o.price, o.ordered_at, s.name, a.account_data "
            "FROM orders o JOIN services s ON o.service_id = s.id "
            "JOIN accounts a ON o.account_id = a.id "
            "WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 15",
            (target_id,)
        ).fetchall()
        conn.close()
        
        if not orders:
            info = "📦 لا يوجد مشتريات"
        else:
            info = f"📜 مشتريات العضو {target_id}:\n\n"
            for o in orders:
                info += f"🔹 {o['name']} ({format_balance(o['price'])})\n"
                
        bot.send_message(call.message.chat.id, info, parse_mode="HTML")
    
    # ============ CATEGORIES MANAGEMENT ============
    elif data == "adm_cats":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        conn = get_db_connection()
        categories = conn.execute("SELECT * FROM categories").fetchall()
        conn.close()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📁 الأقسام:",
            reply_markup=admin_categories_markup(categories)
        )
    
    elif data.startswith("adm_cat_view_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        cat_id = int(data.split("_")[3])
        conn = get_db_connection()
        cat = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
        conn.close()
        
        if not cat:
            bot.answer_callback_query(call.id, "القسم غير موجود!")
            return
        
        msg_text = f"📁 القسم: <b>{cat['name']}</b>"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=admin_category_view_markup(cat_id),
            parse_mode="HTML"
        )
    
    elif data == "adm_new_cat":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        msg = bot.send_message(call.message.chat.id, "✍️ اسم القسم الجديد:")
        bot.register_next_step_handler(msg, process_admin_create_category)
    
    elif data.startswith("adm_edit_cat_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        cat_id = int(data.split("_")[3])
        msg = bot.send_message(call.message.chat.id, "✍️ الاسم الجديد للقسم:")
        bot.register_next_step_handler(msg, process_admin_edit_category, cat_id)
    
    elif data.startswith("adm_del_cat_ask_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        cat_id = int(data.split("_")[4])
        conn = get_db_connection()
        cat = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
        conn.close()
        
        if not cat:
            bot.answer_callback_query(call.id, "القسم غير موجود!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔥 نعم، احذف", callback_data=f"adm_del_cat_confirm_{cat_id}"),
            types.InlineKeyboardButton("⬅️ إلغاء", callback_data="adm_cats")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ هل تريد حذف القسم: <b>{cat['name']}</b>؟\n\nسيتم حذف جميع الخدمات والحسابات فيه!",
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    elif data.startswith("adm_del_cat_confirm_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        cat_id = int(data.split("_")[4])
        conn = get_db_connection()
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم الحذف!")
        call.data = "adm_cats"
        callback_listener(call)
    
    # ============ SERVICES MANAGEMENT ============
    elif data == "adm_services":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        conn = get_db_connection()
        categories = conn.execute("SELECT * FROM categories").fetchall()
        conn.close()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📝 اختر القسم:",
            reply_markup=admin_services_categories_markup(categories)
        )
    
    elif data.startswith("adm_manage_services_under_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        cat_id = int(data.split("_")[5])
        
        conn = get_db_connection()
        cat = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
        services = conn.execute("SELECT * FROM services WHERE category_id = ?", (cat_id,)).fetchall()
        conn.close()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📝 خدمات قسم ({cat['name']}):",
            reply_markup=admin_services_list_markup(services, cat_id)
        )
    
    elif data.startswith("adm_ser_view_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ser_id = int(data.split("_")[3])
        conn = get_db_connection()
        service = conn.execute("SELECT * FROM services WHERE id = ?", (ser_id,)).fetchone()
        conn.close()
        
        if not service:
            bot.answer_callback_query(call.id, "الخدمة غير موجودة!")
            return
        
        msg_text = f"🛍️ الخدمة: <b>{service['name']}</b>\n💵 السعر: {format_balance(service['price'])}"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=admin_service_view_markup(ser_id),
            parse_mode="HTML"
        )
    
    elif data.startswith("adm_new_service_under_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        cat_id = int(data.split("_")[4])
        msg = bot.send_message(
            call.message.chat.id,
            "✍️ أرسل: اسم الخدمة | السعر\n\nمثال: Netflix | 4.99"
        )
        bot.register_next_step_handler(msg, process_admin_create_service, cat_id)
    
    elif data.startswith("adm_edit_ser_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ser_id = int(data.split("_")[3])
        msg = bot.send_message(
            call.message.chat.id,
            "✍️ أرسل: اسم الخدمة | السعر\n\nمثال: Netflix | 4.99"
        )
        bot.register_next_step_handler(msg, process_admin_edit_service, ser_id)
    
    elif data.startswith("adm_del_ser_ask_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ser_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        service = conn.execute("SELECT * FROM services WHERE id = ?", (ser_id,)).fetchone()
        conn.close()
        
        if not service:
            bot.answer_callback_query(call.id, "غير موجودة!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔥 نعم، احذف", callback_data=f"adm_del_ser_confirm_{ser_id}"),
            types.InlineKeyboardButton("⬅️ إلغاء", callback_data=f"adm_ser_view_{ser_id}")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ هل تريد حذف الخدمة: <b>{service['name']}</b>؟",
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    elif data.startswith("adm_del_ser_confirm_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ser_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        service = conn.execute("SELECT category_id FROM services WHERE id = ?", (ser_id,)).fetchone()
        conn.execute("DELETE FROM services WHERE id = ?", (ser_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم!")
        call.data = f"adm_manage_services_under_{service['category_id']}"
        callback_listener(call)
    
    # ============ ACCOUNTS MANAGEMENT ============
    elif data.startswith("adm_accounts_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ser_id = int(data.split("_")[2])
        conn = get_db_connection()
        accounts = conn.execute("SELECT * FROM accounts WHERE service_id = ?", (ser_id,)).fetchall()
        conn.close()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🔑 الحسابات:",
            reply_markup=admin_accounts_markup(accounts, ser_id)
        )
    
    elif data.startswith("adm_acc_view_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        acc_id = int(data.split("_")[3])
        conn = get_db_connection()
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (acc_id,)).fetchone()
        conn.close()
        
        if not account:
            bot.answer_callback_query(call.id, "الحساب غير موجود!")
            return
        
        msg_text = f"🔹 البيانات: <code>{account['account_data']}</code>\n📊 الحالة: {'مباع' if account['is_sold'] == 1 else 'متاح'}"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg_text,
            reply_markup=admin_account_view_markup(acc_id),
            parse_mode="HTML"
        )
    
    elif data.startswith("adm_new_acc_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ser_id = int(data.split("_")[3])
        msg = bot.send_message(call.message.chat.id, "✍️ أرسل بيانات الحساب (user:pass):")
        bot.register_next_step_handler(msg, process_admin_add_single_account, ser_id)
    
    elif data.startswith("adm_edit_acc_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        acc_id = int(data.split("_")[3])
        msg = bot.send_message(call.message.chat.id, "✍️ البيانات الجديدة (user:pass):")
        bot.register_next_step_handler(msg, process_admin_edit_account, acc_id)
    
    elif data.startswith("adm_del_acc_ask_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        acc_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        account = conn.execute("SELECT * FROM accounts WHERE id = ?", (acc_id,)).fetchone()
        conn.close()
        
        if not account:
            bot.answer_callback_query(call.id, "الحساب غير موجود!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔥 نعم، احذف", callback_data=f"adm_del_acc_confirm_{acc_id}"),
            types.InlineKeyboardButton("⬅️ إلغاء", callback_data=f"adm_acc_view_{acc_id}")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ هل تريد حذف الحساب: <code>{account['account_data']}</code>؟",
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    elif data.startswith("adm_del_acc_confirm_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        acc_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        account = conn.execute("SELECT service_id FROM accounts WHERE id = ?", (acc_id,)).fetchone()
        conn.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم!")
        call.data = f"adm_accounts_{account['service_id']}"
        callback_listener(call)
    
    # ============ FORCE SUBSCRIBE CHANNELS ============
    elif data == "adm_forcesub":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        conn = get_db_connection()
        channels = conn.execute("SELECT * FROM force_subscribe_channels").fetchall()
        conn.close()
        
        if not channels:
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="adm_new_forcesub_ch"))
            markup.row(types.InlineKeyboardButton("⬅️ رجوع", callback_data="admin_panel"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📢 لا توجد قنوات مضافة",
                reply_markup=markup
            )
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📢 القنوات الإجبارية:",
                reply_markup=admin_forcesub_channels_markup(channels)
            )
    
    elif data == "adm_new_forcesub_ch":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        msg = bot.send_message(call.message.chat.id, "✍️ أرسل معرف القناة (مثال: @MyChannel):")
        bot.register_next_step_handler(msg, process_admin_add_forcesub_channel)
    
    elif data.startswith("adm_del_ch_ask_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ch_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        channel = conn.execute("SELECT * FROM force_subscribe_channels WHERE id = ?", (ch_id,)).fetchone()
        conn.close()
        
        if not channel:
            bot.answer_callback_query(call.id, "القناة غير موجودة!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔥 نعم، احذف", callback_data=f"adm_del_ch_confirm_{ch_id}"),
            types.InlineKeyboardButton("⬅️ إلغاء", callback_data="adm_forcesub")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ هل تريد حذف القناة: <code>{channel['channel_id']}</code>؟",
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    elif data.startswith("adm_del_ch_confirm_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        ch_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        conn.execute("DELETE FROM force_subscribe_channels WHERE id = ?", (ch_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم!")
        call.data = "adm_forcesub"
        callback_listener(call)
    
    # ============ PAYMENTS ============
    elif data == "adm_payments":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        conn = get_db_connection()
        methods = conn.execute("SELECT * FROM payment_methods").fetchall()
        conn.close()
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="💳 طرق الدفع:",
            reply_markup=admin_payments_markup(methods)
        )
        
    elif data == "adm_new_payment":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
            
        msg = bot.send_message(call.message.chat.id, "✍️ اسم طريقة الدفع:")
        bot.register_next_step_handler(msg, process_admin_payment_name)
        
    elif data.startswith("adm_del_pay_ask_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        method_id = int(data.split("_")[4])
        conn = get_db_connection()
        method = conn.execute("SELECT * FROM payment_methods WHERE id = ?", (method_id,)).fetchone()
        conn.close()
        
        if not method:
            bot.answer_callback_query(call.id, "غير موجودة!")
            return
            
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ هل تريد حذف: ({method['name']})؟",
            reply_markup=admin_payment_delete_confirm_markup(method_id)
        )
        
    elif data.startswith("adm_del_pay_confirm_"):
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        method_id = int(data.split("_")[4])
        
        conn = get_db_connection()
        conn.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ تم!")
        call.data = "adm_payments"
        callback_listener(call)
    
    # ============ BROADCAST ============
    elif data == "adm_broadcast":
        if not is_admin:
            bot.answer_callback_query(call.id, "غير مصرح!", show_alert=True)
            return
        
        msg = bot.send_message(
            call.message.chat.id,
            "📢 أرسل الرسالة للجميع:"
        )
        bot.register_next_step_handler(msg, process_admin_broadcast)

# ========== PROCESS FUNCTIONS ==========
def process_admin_balance_edit(message, target_id):
    try:
        amount = float(message.text.strip())
        conn = get_db_connection()
        conn.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, target_id))
        conn.commit()
        
        updated_user = conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (target_id,)).fetchone()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم!\n\n💵 الرصيد الجديد: {format_balance(updated_user['balance'])}"
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ رقم غير صحيح!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_create_category(message):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم إضافة القسم: {name}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_edit_category(message, cat_id):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    try:
        conn = get_db_connection()
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, cat_id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم تحديث القسم!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_create_service(message, category_id):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 2:
            raise ValueError()
            
        name, price_str = parts[0], parts[1]
        price = float(price_str)
        
        conn = get_db_connection()
        conn.execute("INSERT INTO services (category_id, name, price) VALUES (?, ?, ?)", (category_id, name, price))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم إضافة الخدمة!\n\n🏷️ {name}\n💵 {format_balance(price)}"
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ صيغة خاطئة! استخدم: الاسم | السعر")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_edit_service(message, ser_id):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 2:
            raise ValueError()
            
        name, price_str = parts[0], parts[1]
        price = float(price_str)
        
        conn = get_db_connection()
        conn.execute("UPDATE services SET name = ?, price = ? WHERE id = ?", (name, price, ser_id))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم تحديث الخدمة!\n\n🏷️ {name}\n💵 {format_balance(price)}"
        )
    except ValueError:
        bot.send_message(message.chat.id, "❌ صيغة خاطئة! استخدم: الاسم | السعر")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_add_single_account(message, service_id):
    account_data = message.text.strip()
    if not account_data:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO accounts (service_id, account_data, is_sold) VALUES (?, ?, 0)",
            (service_id, account_data)
        )
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم إضافة الحساب!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_edit_account(message, acc_id):
    account_data = message.text.strip()
    if not account_data:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    try:
        conn = get_db_connection()
        conn.execute("UPDATE accounts SET account_data = ? WHERE id = ?", (account_data, acc_id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم تحديث الحساب!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_add_forcesub_channel(message):
    channel = message.text.strip()
    if not channel:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    if not (channel.startswith("@") or channel.startswith("-100")):
        channel = "@" + channel
        
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO force_subscribe_channels (channel_id) VALUES (?)", (channel,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم إضافة القناة: {channel}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_payment_name(message):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    msg = bot.send_message(message.chat.id, "✍️ التفاصيل (محفظة، حساب، إلخ):")
    bot.register_next_step_handler(msg, process_admin_payment_details, name)

def process_admin_payment_details(message, name):
    details = message.text.strip()
    if not details:
        bot.send_message(message.chat.id, "❌ خطأ!")
        return
        
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO payment_methods (name, details) VALUES (?, ?)", (name, details))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم!\n\n💳 {name}\n🔑 {details}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_user_deposit_screenshot(message, method_name, lang):
    if message.text and message.text.startswith('/'):
        send_welcome(message)
        return
        
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ أرسل صورة!")
        bot.register_next_step_handler(msg, process_user_deposit_screenshot, method_name, lang)
        return
        
    photo_file_id = message.photo[-1].file_id
    user_id = message.from_user.id
    
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO deposit_requests (user_id, method_name, screenshot_file_id, status) VALUES (?, ?, ?, ?)",
            (user_id, method_name, photo_file_id, 'pending')
        )
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ تم استلام الصورة! سيتم التحقق قريباً.")
                
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {e}")

def process_admin_broadcast(message):
    conn = get_db_connection()
    users = conn.execute("SELECT telegram_id FROM users").fetchall()
    conn.close()
    
    if not users:
        bot.send_message(message.chat.id, "❌ لا يوجد مستخدمين!")
        return
        
    admin_chat_id = message.chat.id
    msg_id = message.message_id
    
    status_msg = bot.send_message(admin_chat_id, "⏳ جاري الإرسال...")
    
    success = 0
    fail = 0
    
    for u in users:
        try:
            bot.copy_message(chat_id=u['telegram_id'], from_chat_id=admin_chat_id, message_id=msg_id)
            success += 1
        except Exception:
            fail += 1
            
    bot.edit_message_text(
        chat_id=admin_chat_id,
        message_id=status_msg.message_id,
        text=f"📢 اكتمل!\n\n✅ نجح: {success}\n❌ فشل: {fail}"
    )

print("✅ البوت يعمل الآن!")
bot.infinity_polling()
