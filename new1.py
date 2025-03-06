import telebot
from telebot import types
import requests
import time
from datetime import datetime, timedelta
import pytz
import json
import os
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot with your token (you'll get this from BotFather)
BOT_TOKEN = "7370436558:AAFkPrbh5MISxk_EOPmlcsRlExqR4ez9d7E"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# Database setup
def setup_database():
    conn = sqlite3.connect('ramadan_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        city TEXT,
        language TEXT
    )
    ''')
    conn.commit()
    conn.close()

# User preferences
def get_user_preference(user_id):
    conn = sqlite3.connect('ramadan_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT city, language FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'city': result[0], 'language': result[1]}
    else:
        return {'city': 'Toshkent', 'language': 'uz'}

def save_user_preference(user_id, city=None, language=None):
    conn = sqlite3.connect('ramadan_bot.db')
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        # Update existing preferences
        if city:
            cursor.execute('UPDATE users SET city = ? WHERE user_id = ?', (city, user_id))
        if language:
            cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
    else:
        # Create new user with defaults
        cursor.execute('INSERT INTO users (user_id, city, language) VALUES (?, ?, ?)', 
                      (user_id, city or 'Toshkent', language or 'uz'))
    
    conn.commit()
    conn.close()

# Cities in Uzbekistan with Uzbek names
CITIES = {
    "Toshkent": {"lat": 41.2995, "lng": 69.2401, "ru": "Ташкент", "en": "Tashkent"},
    "Samarqand": {"lat": 39.6542, "lng": 66.9597, "ru": "Самарканд", "en": "Samarkand"},
    "Buxoro": {"lat": 39.7747, "lng": 64.4286, "ru": "Бухара", "en": "Bukhara"},
    "Namangan": {"lat": 41.0011, "lng": 71.6725, "ru": "Наманган", "en": "Namangan"},
    "Andijon": {"lat": 40.7833, "lng": 72.3333, "ru": "Андижан", "en": "Andijan"},
    "Nukus": {"lat": 42.4600, "lng": 59.6200, "ru": "Нукус", "en": "Nukus"},
    "Farg'ona": {"lat": 40.3842, "lng": 71.7836, "ru": "Фергана", "en": "Fergana"},
    "Qarshi": {"lat": 38.8667, "lng": 65.8000, "ru": "Карши", "en": "Qarshi"},
    "Urganch": {"lat": 41.5500, "lng": 60.6333, "ru": "Ургенч", "en": "Urgench"},
    "Jizzax": {"lat": 40.1167, "lng": 67.8500, "ru": "Джизак", "en": "Jizzakh"}
}

# Day name translations
DAY_TRANSLATIONS = {
    "Monday": {
        "uz": "Dushanba",
        "ru": "Понедельник",
        "en": "Monday"
    },
    "Tuesday": {
        "uz": "Seshanba",
        "ru": "Вторник",
        "en": "Tuesday"
    },
    "Wednesday": {
        "uz": "Chorshanba",
        "ru": "Среда",
        "en": "Wednesday"
    },
    "Thursday": {
        "uz": "Payshanba",
        "ru": "Четверг",
        "en": "Thursday"
    },
    "Friday": {
        "uz": "Juma",
        "ru": "Пятница",
        "en": "Friday"
    },
    "Saturday": {
        "uz": "Shanba",
        "ru": "Суббота",
        "en": "Saturday"
    },
    "Sunday": {
        "uz": "Yakshanba",
        "ru": "Воскресенье",
        "en": "Sunday"
    }
}

# Translations dictionary with enhanced emojis
TRANSLATIONS = {
    "welcome": {
        "uz": "🌙 Assalomu alaykum! O'zbekiston Ramazon taqvimi botiga xush kelibsiz! 🕌\n\nUshbu bot O'zbekistondagi shaharlar uchun saharlik va iftorlik vaqtlarini taqdim etadi.\nIltimos, shahringizni tanlang:",
        "ru": "🌙 Ассаламу алейкум! Добро пожаловать в бот Календарь Рамадана Узбекистана! 🕌\n\nЭтот бот предоставляет время сухура и ифтара для городов Узбекистана.\nПожалуйста, выберите ваш город:",
        "en": "🌙 Assalamu alaikum! Welcome to the Uzbekistan Ramadan Calendar Bot! 🕌\n\nThis bot provides Suhoor and Iftar times for cities in Uzbekistan.\nPlease select your city:"
    },
    "ramadan_calendar": {
        "uz": "🌙 *{city} uchun Ramazon taqvimi* 🕌",
        "ru": "🌙 *Календарь Рамадана для {city}* 🕌",
        "en": "🌙 *Ramadan Calendar for {city}* 🕌"
    },
    "date": {
        "uz": "📅 *Sana:* {date}",
        "ru": "📅 *Дата:* {date}",
        "en": "📅 *Date:* {date}"
    },
    "suhoor_ends": {
        "uz": "🌄 *Saharlik tugashi (Bomdod):* {time}",
        "ru": "🌄 *Конец сухура (Фаджр):* {time}",
        "en": "🌄 *Suhoor ends (Fajr):* {time}"
    },
    "iftar_begins": {
        "uz": "🌅 *Iftorlik boshlanishi (Shom):* {time}",
        "ru": "🌅 *Начало ифтара (Магриб):* {time}",
        "en": "🌅 *Iftar begins (Maghrib):* {time}"
    },
    "to_see_other_days": {
        "uz": "📆 Boshqa kunlar uchun vaqtlarni ko'rish uchun quyidagi tugmalardan foydalaning:",
        "ru": "📆 Чтобы увидеть время для других дней, используйте кнопки ниже:",
        "en": "📆 To see times for other days, use buttons below:"
    },
    "today": {
        "uz": "📅 Bugun",
        "ru": "📅 Сегодня",
        "en": "📅 Today"
    },
    "tomorrow": {
        "uz": "📆 Ertaga",
        "ru": "📆 Завтра",
        "en": "📆 Tomorrow"
    },
    "week": {
        "uz": "🗓️ Butun hafta",
        "ru": "🗓️ Вся неделя",
        "en": "🗓️ Full week"
    },
    "change_city": {
        "uz": "🏙️ Shaharni o'zgartirish",
        "ru": "🏙️ Изменить город",
        "en": "🏙️ Change city"
    },
    "change_language": {
        "uz": "🌐 Tilni o'zgartirish",
        "ru": "🌐 Изменить язык",
        "en": "🌐 Change language"
    },
    "select_language": {
        "uz": "🌐 Iltimos, tilni tanlang:",
        "ru": "🌐 Пожалуйста, выберите язык:",
        "en": "🌐 Please select language:"
    },
    "language_set": {
        "uz": "✅ Til o'zbekchaga o'zgartirildi.",
        "ru": "✅ Язык изменен на русский.",
        "en": "✅ Language changed to English."
    },
    "todays_times": {
        "uz": "🌙 *{city} uchun bugungi Ramazon vaqtlari* 🕌",
        "ru": "🌙 *Сегодняшнее время Рамадана для {city}* 🕌",
        "en": "🌙 *Today's Ramadan Times for {city}* 🕌"
    },
    "tomorrows_times": {
        "uz": "🌙 *{city} uchun ertangi Ramazon vaqtlari* 🕌",
        "ru": "🌙 *Завтрашнее время Рамадана для {city}* 🕌",
        "en": "🌙 *Tomorrow's Ramadan Times for {city}* 🕌"
    },
    "week_schedule": {
        "uz": "🌙 *{city} uchun Ramazon haftalik jadvali* 🕌",
        "ru": "🌙 *Еженедельное расписание Рамадана для {city}* 🕌",
        "en": "🌙 *Ramadan Week Schedule for {city}* 🕌"
    },
    "help": {
        "uz": "🌙 *Ramazon taqvimi bot yordami* 🕌\n\n*Mavjud buyruqlar:*\n/start - Botni ishga tushiring va shahringizni tanlang\n/today - Bugungi saharlik va iftorlik vaqtlarini oling\n/tomorrow - Ertangi saharlik va iftorlik vaqtlarini oling\n/week - Butun hafta jadvalini oling\n/help - Ushbu yordam xabarini ko'rsating\n\nShuningdek, joriy vaqtlarni olish uchun istalgan shahar nomini bosishingiz mumkin.",
        "ru": "🌙 *Справка по боту Календарь Рамадана* 🕌\n\n*Доступные команды:*\n/start - Запустить бота и выбрать город\n/today - Получить сегодняшнее время сухура и ифтара\n/tomorrow - Получить завтрашнее время сухура и ифтара\n/week - Получить расписание на всю неделю\n/help - Показать это справочное сообщение\n\nВы также можете просто нажать на любое название города, чтобы получить текущее время.",
        "en": "🌙 *Ramadan Calendar Bot Help* 🕌\n\n*Available Commands:*\n/start - Start the bot and select your city\n/today - Get today's Suhoor and Iftar times\n/tomorrow - Get tomorrow's Suhoor and Iftar times\n/week - Get the full week's schedule\n/help - Show this help message\n\nYou can also simply tap on any city name to get current times."
    },
    "error": {
        "uz": "❌ Kechirasiz, namoz vaqtlarini olishda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
        "ru": "❌ Извините, произошла ошибка при получении времени молитвы. Пожалуйста, повторите попытку позже.",
        "en": "❌ Sorry, couldn't retrieve prayer times. Please try again later."
    },
    "processing": {
        "uz": "⏳ Iltimos kuting...",
        "ru": "⏳ Пожалуйста, подождите...",
        "en": "⏳ Please wait..."
    }
}

# Get text in the user's language
def get_text(key, language, **kwargs):
    if key in TRANSLATIONS and language in TRANSLATIONS[key]:
        return TRANSLATIONS[key][language].format(**kwargs)
    return TRANSLATIONS[key]["en"].format(**kwargs)  # Fallback to English

# Translate day name to user's language
def translate_day(day_name, language):
    if day_name in DAY_TRANSLATIONS and language in DAY_TRANSLATIONS[day_name]:
        return DAY_TRANSLATIONS[day_name][language]
    return day_name  # Fallback

# Prayer time calculation method - 2 is for Islamic Society of North America
# You may want to adjust this based on preferred calculation method in Uzbekistan
CALCULATION_METHOD = 2

# Cache for prayer times
prayer_times_cache = {}

# Helper function for API calls with retry
def get_api_response(url, max_retries=3):
    """Retry API calls with exponential backoff"""
    for retry in range(max_retries):
        try:
            logger.info(f"API request attempt {retry+1}/{max_retries}: {url}")
            
            # Add timeout to prevent hanging
            response = requests.get(url, timeout=10)
            
            # Check if the response is valid JSON
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            # Parse the JSON response
            data = response.json()
            
            # Validate the response contains the expected structure
            if not data or "code" not in data or data["code"] != 200:
                logger.warning(f"Invalid API response: {data}")
                if retry < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    wait_time = (2 ** retry)  # 1, 2, 4... seconds
                    logger.info(f"Waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"API returned invalid response: {data}")
            
            logger.info(f"API request successful")
            return data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if retry < max_retries - 1:
                # Wait before retrying (exponential backoff)
                wait_time = (2 ** retry)  # 1, 2, 4... seconds
                logger.info(f"Waiting {wait_time} seconds before retry")
                time.sleep(wait_time)
            else:
                raise Exception("Maximum retries exceeded. Could not fetch data.")
    
    # If we've exhausted our retries
    raise Exception("Maximum retries exceeded. Could not fetch data.")

def get_prayer_times(city, date):
    """Fetch prayer times for a city on a specific date with adjusted Iftar time"""
    cache_key = f"{city}_{date.strftime('%Y-%m-%d')}"
    
    # Return cached results if available
    if cache_key in prayer_times_cache:
        return prayer_times_cache[cache_key]
    
    # Get coordinates for the city
    if city not in CITIES:
        return None
    
    lat = CITIES[city]["lat"]
    lng = CITIES[city]["lng"]
    
    # Format date for API request
    date_str = date.strftime("%d-%m-%Y")
    
    # Call prayer times API with 3 retries
    url = f"http://api.aladhan.com/v1/timings/{date_str}?latitude={lat}&longitude={lng}&method={CALCULATION_METHOD}"
    
    try:
        data = get_api_response(url)
        
        if not data or "data" not in data or "timings" not in data["data"]:
            logger.error(f"Invalid API response format: {data}")
            return None
            
        # Extract relevant prayer times
        timings = data["data"]["timings"]
        
        if "Fajr" not in timings or "Maghrib" not in timings:
            logger.error(f"Missing required prayer times in response: {timings}")
            return None
            
        fajr = timings["Fajr"]      # Suhoor time (ends at Fajr)
        maghrib = timings["Maghrib"] # Iftar time (starts at Maghrib)
        
        # Format the date for display (use readable format)
        readable_date = f"{date.day}/{date.month}/{date.year}"
        if "date" in data["data"] and "readable" in data["data"]["date"]:
            readable_date = data["data"]["date"]["readable"]
        
        # Add day name to the date
        day_name = date.strftime("%A")
        
        result = {
            "city": city,
            "date": f"{translate_day(day_name, 'uz')}, {readable_date}",
            "suhoor_ends": fajr,
            "iftar_begins": maghrib
        }
        
        # Cache the result
        prayer_times_cache[cache_key] = result
        return result
        
    except Exception as e:
        logger.error(f"Error fetching prayer times: {e}")
        return None

def create_main_menu_keyboard(language):
    """Create main menu keyboard with buttons in the user's language"""
    # Create a keyboard with 2 buttons per row max
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Create buttons with explicit callback_data values (keep them short)
    today_btn = types.InlineKeyboardButton(
        text=get_text("today", language), 
        callback_data="today"
    )
    tomorrow_btn = types.InlineKeyboardButton(
        text=get_text("tomorrow", language),
        callback_data="tomorrow"
    )
    week_btn = types.InlineKeyboardButton(
        text=get_text("week", language),
        callback_data="week"
    )
    change_city_btn = types.InlineKeyboardButton(
        text=get_text("change_city", language),
        callback_data="change_city"
    )
    change_language_btn = types.InlineKeyboardButton(
        text=get_text("change_language", language),
        callback_data="change_language"
    )
    
    # Add buttons in rows
    keyboard.add(today_btn, tomorrow_btn)  # First row
    keyboard.row(week_btn)  # Second row
    keyboard.row(change_city_btn)  # Third row
    keyboard.row(change_language_btn)  # Fourth row
    
    return keyboard

def create_cities_keyboard():
    """Create keyboard with city buttons"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Add buttons for each city
    buttons = []
    for city in CITIES.keys():
        # Keep callback data short: "city_" + city
        cb_data = f"city_{city}"
        # Ensure callback data isn't too long
        if len(cb_data) > 64:  # Telegram's callback_data limit
            cb_data = cb_data[:60]  # Truncate if needed
        buttons.append(types.InlineKeyboardButton(text=city, callback_data=cb_data))
    
    # Add all buttons
    keyboard.add(*buttons)
    return keyboard

def create_language_keyboard():
    """Create keyboard with language options"""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    
    uz_btn = types.InlineKeyboardButton(text="O'zbek 🇺🇿", callback_data="lang_uz")
    ru_btn = types.InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru")
    en_btn = types.InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en")
    
    keyboard.add(uz_btn, ru_btn, en_btn)
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Welcome message when user starts the bot"""
    user_id = message.from_user.id
    
    # Set default preferences for new user
    save_user_preference(user_id)
    prefs = get_user_preference(user_id)
    
    # Send welcome message in user's language
    welcome_text = get_text("welcome", prefs["language"])
    
    # Send message with city selection keyboard
    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=create_cities_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['today'])
def cmd_today(message):
    user_id = message.from_user.id
    prefs = get_user_preference(user_id)
    city = prefs["city"]
    language = prefs["language"]
    
    # Send a processing message
    processing_msg = bot.send_message(
        message.chat.id,
        get_text("processing", language),
        parse_mode="Markdown"
    )
    
    # Get today's date in Uzbekistan timezone
    uzbekistan_tz = pytz.timezone('Asia/Tashkent')
    today = datetime.now(uzbekistan_tz).date()
    
    times = get_prayer_times(city, today)
    if times:
        response = f"{get_text('todays_times', language, city=city)}\n" \
                  f"{get_text('date', language, date=times['date'])}\n\n" \
                  f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                  f"{get_text('iftar_begins', language, time=times['iftar_begins'])}"
        
        # Delete processing message and send the actual response
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.send_message(
            message.chat.id,
            response,
            reply_markup=create_main_menu_keyboard(language),
            parse_mode="Markdown"
        )
    else:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            text=get_text("error", language)
        )

@bot.message_handler(commands=['tomorrow'])
def cmd_tomorrow(message):
    user_id = message.from_user.id
    prefs = get_user_preference(user_id)
    city = prefs["city"]
    language = prefs["language"]
    
    # Send a processing message
    processing_msg = bot.send_message(
        message.chat.id,
        get_text("processing", language),
        parse_mode="Markdown"
    )
    
    # Get tomorrow's date in Uzbekistan timezone
    uzbekistan_tz = pytz.timezone('Asia/Tashkent')
    tomorrow = (datetime.now(uzbekistan_tz) + timedelta(days=1)).date()
    
    times = get_prayer_times(city, tomorrow)
    if times:
        response = f"{get_text('tomorrows_times', language, city=city)}\n" \
                  f"{get_text('date', language, date=times['date'])}\n\n" \
                  f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                  f"{get_text('iftar_begins', language, time=times['iftar_begins'])}"
        
        # Delete processing message and send the actual response
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.send_message(
            message.chat.id,
            response,
            reply_markup=create_main_menu_keyboard(language),
            parse_mode="Markdown"
        )
    else:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            text=get_text("error", language)
        )

@bot.message_handler(commands=['week'])
def cmd_week(message):
    user_id = message.from_user.id
    prefs = get_user_preference(user_id)
    city = prefs["city"]
    language = prefs["language"]
    
    # Send a processing message
    processing_msg = bot.send_message(
        message.chat.id,
        get_text("processing", language),
        parse_mode="Markdown"
    )
    
    # Create and send the week schedule
    send_week_schedule(message.chat.id, city, language, processing_msg.message_id)

def send_week_schedule(chat_id, city, language, message_id=None):
    """Generate and send the week schedule"""
    uzbekistan_tz = pytz.timezone('Asia/Tashkent')
    today = datetime.now(uzbekistan_tz).date()
    
    response = f"✨ {get_text('week_schedule', language, city=city)} ✨\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        times = get_prayer_times(city, date)
        
        if times:
            # Format the date more attractively
            day_name = date.strftime("%A")  # Get the day name
            day_name_translated = translate_day(day_name, language)
            
            if i == 0:
                day_prefix = "🟢 "  # Today
            elif i == 1:
                day_prefix = "⏭️ "  # Tomorrow
            else:
                day_prefix = "📆 "  # Other days
                
            response += f"{day_prefix}*{day_name_translated}, {times['date']}*\n" \
                       f"🌄 Suhoor: *{times['suhoor_ends']}* | 🌅 Iftar: *{times['iftar_begins']}*\n\n"
    
    # If message_id is provided, edit that message. Otherwise, send a new one
    if message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=response,
                reply_markup=create_main_menu_keyboard(language),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error editing message: {e}")
            # If message is too long or other error, send as new message
            bot.delete_message(chat_id, message_id)
            bot.send_message(
                chat_id,
                response,
                reply_markup=create_main_menu_keyboard(language),
                parse_mode="Markdown"
            )
    else:
        bot.send_message(
            chat_id,
            response,
            reply_markup=create_main_menu_keyboard(language),
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['help'])
def send_help(message):
    """Send help information"""
    user_id = message.from_user.id
    prefs = get_user_preference(user_id)
    language = prefs["language"]
    
    help_text = get_text("help", language)
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    try:
        # Always immediately answer the callback query to stop the loading animation
        # This is crucial to prevent the button from appearing stuck
        bot.answer_callback_query(call.id)
        
        # Log the callback data for debugging
        logger.info(f"Callback received: {call.data} from user {call.from_user.id}")
        
        # Check if callback data is empty
        if not call.data:
            logger.warning("Empty callback data received")
            return
            
        # Then direct to the appropriate handler
        if call.data.startswith('city_'):
            logger.info(f"Handling city selection: {call.data}")
            handle_city_selection(call)
        elif call.data == 'change_city':
            logger.info("Handling change city")
            handle_change_city(call)
        elif call.data == 'change_language':
            logger.info("Handling change language")
            handle_change_language(call)
        elif call.data.startswith('lang_'):
            logger.info(f"Handling language selection: {call.data}")
            handle_language_selection(call)
        elif call.data == 'today':
            logger.info("Handling today button")
            handle_today(call)
        elif call.data == 'tomorrow':
            logger.info("Handling tomorrow button")
            handle_tomorrow(call)
        elif call.data == 'week':
            logger.info("Handling week button")
            handle_week(call)
        else:
            logger.warning(f"Unknown callback data: {call.data}")
            bot.send_message(
                call.message.chat.id,
                "Sorry, I didn't understand that command. Please try again.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in callback handler: {e}", exc_info=True)
        try:
            # Always answer the callback query even in case of error
            bot.answer_callback_query(call.id, "An error occurred. Please try again.")
            # Notify the user
            bot.send_message(
                call.message.chat.id, 
                "An error occurred. Please try again by sending /start",
                parse_mode="Markdown"
            )
        except Exception as ex:
            logger.error(f"Failed to notify user about error: {ex}")

# Individual callback handlers
def handle_city_selection(call):
    """Handle city selection from inline keyboard"""
    user_id = call.from_user.id
    city = call.data.replace('city_', '')
    
    # Save user's city preference
    save_user_preference(user_id, city=city)
    prefs = get_user_preference(user_id)
    language = prefs["language"]
    
    # Get today's date in Uzbekistan timezone
    uzbekistan_tz = pytz.timezone('Asia/Tashkent')
    today = datetime.now(uzbekistan_tz).date()
    
    # Show processing message
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_text("processing", language),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    # Get prayer times for today
    times = get_prayer_times(city, today)
    
    if times:
        response = f"{get_text('ramadan_calendar', language, city=city)}\n" \
                  f"{get_text('date', language, date=times['date'])}\n\n" \
                  f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                  f"{get_text('iftar_begins', language, time=times['iftar_begins'])}\n\n" \
                  f"{get_text('to_see_other_days', language)}"
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                reply_markup=create_main_menu_keyboard(language),
                parse_mode="Markdown"
            )
        except Exception:
            bot.send_message(
                chat_id=call.message.chat.id,
                text=response,
                reply_markup=create_main_menu_keyboard(language),
                parse_mode="Markdown"
            )
    else:
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id,
                text=get_text("error", language)
            )
        except Exception:
            bot.send_message(
                chat_id=call.message.chat.id, 
                text=get_text("error", language)
            )

def handle_change_city(call):
    """Handle city change request"""
    user_id = call.from_user.id
    prefs = get_user_preference(user_id)
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_text("welcome", prefs["language"]),
            reply_markup=create_cities_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(
            chat_id=call.message.chat.id,
            text=get_text("welcome", prefs["language"]),
            reply_markup=create_cities_keyboard(),
            parse_mode="Markdown"
        )

def handle_change_language(call):
    """Handle language change request"""
    user_id = call.from_user.id
    prefs = get_user_preference(user_id)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=get_text("select_language", prefs["language"]),
        reply_markup=create_language_keyboard(),
        parse_mode="Markdown"
    )

def handle_language_selection(call):
    """Handle language selection"""
    user_id = call.from_user.id
    language = call.data.replace('lang_', '')
    
    # Save user's language preference
    save_user_preference(user_id, language=language)
    prefs = get_user_preference(user_id)
    city = prefs["city"]
    
    # Get today's date in Uzbekistan timezone
    uzbekistan_tz = pytz.timezone('Asia/Tashkent')
    today = datetime.now(uzbekistan_tz).date()
    
    # Get prayer times for today
    times = get_prayer_times(city, today)
    
    if times:
        response = f"{get_text('ramadan_calendar', language, city=city)}\n" \
                  f"{get_text('date', language, date=times['date'])}\n\n" \
                  f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                  f"{get_text('iftar_begins', language, time=times['iftar_begins'])}\n\n" \
                  f"{get_text('to_see_other_days', language)}"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response,
            reply_markup=create_main_menu_keyboard(language),
            parse_mode="Markdown"
        )
    else:
        bot.answer_callback_query(
            call.id, 
            get_text("language_set", language)
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id,
            text=get_text("error", language)
        )

def handle_today(call):
    """Handle today button press"""
    try:
        user_id = call.from_user.id
        prefs = get_user_preference(user_id)
        city = prefs["city"]
        language = prefs["language"]
        
        # Show processing message first
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=get_text("processing", language),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not edit message to show processing: {e}")
        
        # Get today's date in Uzbekistan timezone
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        today = datetime.now(uzbekistan_tz).date()
        
        # Fetch the prayer times
        logger.info(f"Fetching prayer times for city: {city}, date: {today}")
        times = get_prayer_times(city, today)
        
        if times:
            logger.info(f"Successfully retrieved prayer times for today: {times}")
            response = f"{get_text('todays_times', language, city=city)}\n" \
                      f"{get_text('date', language, date=times['date'])}\n\n" \
                      f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                      f"{get_text('iftar_begins', language, time=times['iftar_begins'])}"
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=response,
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to edit message with today's times: {e}")
                # If edit fails, try sending a new message
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=response,
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
        else:
            logger.error(f"Failed to get prayer times for {city} on {today}")
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=get_text("error", language),
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to edit message with error: {e}")
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=get_text("error", language),
                    parse_mode="Markdown"
                )
    except Exception as e:
        logger.error(f"Error in handle_today: {e}", exc_info=True)
        try:
            bot.send_message(
                call.message.chat.id,
                "An error occurred. Please try again by sending /start",
                parse_mode="Markdown"
            )
        except Exception:
            pass

def handle_tomorrow(call):
    """Handle tomorrow button press"""
    try:
        user_id = call.from_user.id
        prefs = get_user_preference(user_id)
        city = prefs["city"]
        language = prefs["language"]
        
        # Show processing message first
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=get_text("processing", language),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not edit message to show processing: {e}")
        
        # Get tomorrow's date in Uzbekistan timezone
        uzbekistan_tz = pytz.timezone('Asia/Tashkent')
        tomorrow = (datetime.now(uzbekistan_tz) + timedelta(days=1)).date()
        
        # Fetch the prayer times
        logger.info(f"Fetching prayer times for city: {city}, date: {tomorrow}")
        times = get_prayer_times(city, tomorrow)
        
        if times:
            logger.info(f"Successfully retrieved prayer times for tomorrow: {times}")
            response = f"{get_text('tomorrows_times', language, city=city)}\n" \
                      f"{get_text('date', language, date=times['date'])}\n\n" \
                      f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                      f"{get_text('iftar_begins', language, time=times['iftar_begins'])}"
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=response,
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to edit message with tomorrow's times: {e}")
                # If edit fails, try sending a new message
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=response,
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
        else:
            logger.error(f"Failed to get prayer times for {city} on {tomorrow}")
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=get_text("error", language),
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to edit message with error: {e}")
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=get_text("error", language),
                    parse_mode="Markdown"
                )
    except Exception as e:
        logger.error(f"Error in handle_tomorrow: {e}", exc_info=True)
        try:
            bot.send_message(
                call.message.chat.id,
                "An error occurred. Please try again by sending /start",
                parse_mode="Markdown"
            )
        except Exception:
            pass

def handle_week(call):
    """Handle week button press"""
    user_id = call.from_user.id
    prefs = get_user_preference(user_id)
    city = prefs["city"]
    language = prefs["language"]
    
    uzbekistan_tz = pytz.timezone('Asia/Tashkent')
    today = datetime.now(uzbekistan_tz).date()
    
    response = f"{get_text('week_schedule', language, city=city)}\n\n"
    
    for i in range(7):
        date = today + timedelta(days=i)
        times = get_prayer_times(city, date)
        
        if times:
            response += f"*{times['date']}*\n" \
                       f"Suhoor: {times['suhoor_ends']} | Iftar: {times['iftar_begins']}\n\n"
    
    # If message is too long, split it
    if len(response) > 4096:
        first_part = response[:4000] + "..."
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=first_part,
            reply_markup=create_main_menu_keyboard(language),
            parse_mode="Markdown"
        )
        bot.send_message(
            call.message.chat.id,
            response[4000:],
            parse_mode="Markdown"
        )
    else:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response,
            reply_markup=create_main_menu_keyboard(language),
            parse_mode="Markdown"
        )

# Handle any text message as a city request (for backward compatibility)
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all text messages"""
    user_id = message.from_user.id
    text = message.text
    
    
    # Check if text is a city name
    for city in CITIES:
        if text == city or text == CITIES[city]["ru"] or text == CITIES[city]["en"]:
            save_user_preference(user_id, city=city)
            prefs = get_user_preference(user_id)
            language = prefs["language"]
            
            # Get today's date in Uzbekistan timezone
            uzbekistan_tz = pytz.timezone('Asia/Tashkent')
            today = datetime.now(uzbekistan_tz).date()
            
            # Get prayer times for today
            times = get_prayer_times(city, today)
            
            if times:
                response = f"{get_text('ramadan_calendar', language, city=city)}\n" \
                          f"{get_text('date', language, date=times['date'])}\n\n" \
                          f"{get_text('suhoor_ends', language, time=times['suhoor_ends'])}\n" \
                          f"{get_text('iftar_begins', language, time=times['iftar_begins'])}\n\n" \
                          f"{get_text('to_see_other_days', language)}"
                
                bot.send_message(
                    message.chat.id,
                    response,
                    reply_markup=create_main_menu_keyboard(language),
                    parse_mode="Markdown"
                )
                return
            else:
                bot.reply_to(message, get_text("error", language))
                return
    
    # If not a city, send help menu
    send_help(message)

# Start the bot
if __name__ == "__main__":
    setup_database()
    logger.info("Improved Ramadan Calendar Bot is running...")
    try:
        # Use regular polling instead of infinity_polling
        bot.polling(none_stop=True, timeout=10)
    except Exception as e:
        logger.error(f"Error in bot polling: {e}", exc_info=True)