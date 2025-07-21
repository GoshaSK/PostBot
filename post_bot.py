import telebot
from dotenv import load_dotenv
import os
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
from datetime import datetime

load_dotenv()
ADMIN_IDS = [837587233, 1074444081, 810752125]
CHANNEL_ID = '-1002636786440'

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
user_state = {}
scheduled_posts = []
pending_idea_users = {}


def safe_send_message(chat_id, text, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        print(f"[send_message] Ошибка: {e}")


@bot.message_handler(commands=['start'])
def handle_start(message):
    text = (
        "👋 Привет! Добро пожаловать в нашего Telegram-бота для публикации товаров.\n\n"
        "🛍️ Здесь ты можешь добавить свою карточку товара — она пройдёт модерацию и появится в нашем канале!\n\n"
        "📩 По вопросам сотрудничества, рекламы или если хочешь бота любого вида — пиши @idhxjsnd 💼"
    )
    safe_send_message(message.chat.id, text)


@bot.message_handler(commands=['user'])
def handle_user_menu(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Добавить товар", callback_data='user_add_product'))
    safe_send_message(message.chat.id, "🧾 Меню пользователя:\nВы можете добавить товар (после модерации).",reply_markup=markup)


@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if message.from_user.id in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Добавить товар", callback_data='add_product'))
        markup.add(InlineKeyboardButton("👕 Добавить аутфит", callback_data='add_outfit'))
        markup.add(InlineKeyboardButton("📅 Запланированные карточки", callback_data='scheduled_cards'))
        safe_send_message(message.chat.id, "🔐 Админ-панель:", reply_markup=markup)
    else:
        safe_send_message(message.chat.id, "⛔ У вас нет доступа к админ-панели.")


@bot.message_handler(commands=['idea'])
def handle_idea_command(message):
    user_id = message.from_user.id
    pending_idea_users[user_id] = True
    safe_send_message(message.chat.id, "💡 Напишите свою идею, предложение или замечание по работе бота. Мы обязательно рассмотрим каждое сообщение!")


@bot.message_handler(func=lambda m: m.from_user.id in pending_idea_users)
def handle_idea_message(message):
    user_id = message.from_user.id
    idea_text = message.text

    main_admin_id = ADMIN_IDS[0] if ADMIN_IDS else None
    if main_admin_id:
        safe_send_message(main_admin_id, f"📥 Новая идея от @{message.from_user.username or user_id}:\n\n{idea_text}")
        safe_send_message(message.chat.id, "✅ Спасибо! Ваша идея отправлена администрации.")
    else:
        safe_send_message(message.chat.id, "⚠️ Ошибка: администратор не настроен.")

    pending_idea_users.pop(user_id, None)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id

    if call.data == 'add_product':
        if user_id in ADMIN_IDS:
            if user_id in user_state and user_state[user_id].get('step') != 'done':
                return
            else:
                user_state[user_id] = {'step': 'title'}
                safe_send_message(call.message.chat.id, "📝 Введите <b>название товара</b>:", parse_mode='HTML')
        else:
            safe_send_message(call.message.chat.id, "⛔ У вас нет доступа.")

    elif call.data == 'user_add_product':
        if user_id in user_state and user_state[user_id].get('step') != 'done':
            return
        else:
            user_state[user_id] = {'step': 'user_title', 'is_user': True}
            safe_send_message(call.message.chat.id, "📝 Введите <b>название товара</b>:", parse_mode='HTML')

    elif call.data == 'user_finish_photos':
        state = user_state.get(user_id)
        if not state or state.get('step') != 'user_photo':
            return bot.answer_callback_query(call.id, "⏳ Сейчас нельзя завершить")

        if 'photos' not in state or not state['photos']:
            return bot.answer_callback_query(call.id, "⚠️ Сначала отправьте хотя бы одно фото.")

        caption = (
            f"<b>{state['title']}</b>\n"
            f"💰 Цена: <b>{state['price']}</b>\n"
            f"⭐ Рейтинг: <b>{state['rating']}</b>\n"
            f"🔢 Артикул: <code>{state['sku']}</code>\n"
            f"🏷️ Теги: {state.get('tags', '')}\n"
            f"🔗 <a href=\"{state['link']}\">Ссылка на товар</a>"
        )
        media = [types.InputMediaPhoto(p) for p in state['photos']]
        media[0].caption = caption
        media[0].parse_mode = 'HTML'

        admin_id = ADMIN_IDS[0]
        mod_markup = InlineKeyboardMarkup()
        mod_markup.add(
            InlineKeyboardButton("✅ Одобрить", callback_data=f'mod_approve_{user_id}'),
            InlineKeyboardButton("❌ Отклонить", callback_data=f'mod_reject_{user_id}')
        )
        bot.send_media_group(admin_id, media)
        safe_send_message(admin_id, "🔎 Новая карточка на модерации:", reply_markup=mod_markup)

        safe_send_message(call.message.chat.id, "🕵️‍♀️ Карточка отправлена на модерацию. Мы сообщим, когда её одобрят.")
        user_state.pop(user_id, None)
        bot.answer_callback_query(call.id)

    elif call.data.startswith('mod_approve_'):
        target_user_id = int(call.data.split('_')[-1])
        state = user_state.get(target_user_id)
        if state:
            caption = (
                f"<b>{state['title']}</b>\n"
                f"💰 Цена: <b>{state['price']}</b>\n"
                f"⭐ Рейтинг: <b>{state['rating']}</b>\n"
                f"🔢 Артикул: <code>{state['sku']}</code>\n"
                f"🏷️ Теги: {state.get('tags', '')}\n"
                f"🔗 <a href=\"{state['link']}\">Ссылка на товар</a>"
            )
            media = [types.InputMediaPhoto(p) for p in state['photos']]
            media[0].caption = caption
            media[0].parse_mode = 'HTML'
            bot.send_media_group(CHANNEL_ID, media)
            safe_send_message(target_user_id, "✅ Ваша карточка одобрена и опубликована!")
            user_state.pop(target_user_id, None)
        bot.answer_callback_query(call.id)

    elif call.data.startswith('mod_reject_'):
        target_user_id = int(call.data.split('_')[-1])
        safe_send_message(target_user_id, "❌ Ваша карточка была отклонена модератором.")
        user_state.pop(target_user_id, None)
        bot.answer_callback_query(call.id)

    elif call.data == 'add_outfit':
        if user_id in ADMIN_IDS:
            current_step = user_state.get(user_id, {}).get('step')
            if current_step and current_step.startswith('outfit') and current_step != 'done':
                return
            user_state[user_id] = {'step': 'outfit_count', 'outfit_items': []}
            safe_send_message(call.message.chat.id, "👗 Сколько вещей в аутфите? (от 1 до 10)")
        else:
            safe_send_message(call.message.chat.id, "⛔ У вас нет доступа.")

    elif call.data == 'scheduled_cards':
        if not scheduled_posts:
            safe_send_message(call.message.chat.id, "📭 Нет запланированных карточек.")
            return

        for i, post in enumerate(scheduled_posts):
            preview = post['media'][0].caption[:80] + '...'
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Удалить", callback_data=f'delete_scheduled_{i}'))
            safe_send_message(call.message.chat.id, f"📅 Время: <b>{post['time']}</b>\n📝 {preview}", parse_mode='HTML', reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith('delete_scheduled_'):
        try:
            index = int(call.data.split('_')[-1])
            if 0 <= index < len(scheduled_posts):
                deleted = scheduled_posts.pop(index)
                bot.send_message(call.message.chat.id, f"🗑 Удалена публикация на {deleted['time']}")
            else:
                bot.send_message(call.message.chat.id, "⚠️ Элемент не найден.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Ошибка удаления: {e}")
        bot.answer_callback_query(call.id)

    elif call.data == 'delete_card':
        user_state.pop(user_id, None)
        safe_send_message(call.message.chat.id, "🗑 Карточка удалена.")
        bot.answer_callback_query(call.id)

    elif call.data == 'delete_outfit':
        user_state.pop(user_id, None)
        safe_send_message(call.message.chat.id, "🗑 Аутфит удалён.")
        bot.answer_callback_query(call.id)

    elif call.data == 'finish_photos':
        state = user_state.get(user_id)
        if not state or state.get('step') != 'photo':
            return bot.answer_callback_query(call.id, "⏳ Сейчас нельзя завершить")

        if 'photos' not in state or not state['photos']:
            return bot.answer_callback_query(call.id, "⚠️ Сначала отправьте хотя бы одно фото.")

        caption = (
            f"<b>{state['title']}</b>\n"
            f"💰 Цена: <b>{state['price']}</b>\n"
            f"⭐ Рейтинг: <b>{state['rating']}</b>\n"
            f"🔢 Артикул: <code>{state['sku']}</code>\n"
            f"🏷️ Теги: {state.get('tags', '')}\n"
            f"🔗 <a href=\"{state['link']}\">Ссылка на товар</a>"
        )

        media = [types.InputMediaPhoto(p) for p in state['photos']]
        media[0].caption = caption
        media[0].parse_mode = 'HTML'
        state['product_caption'] = caption

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📤 Опубликовать сейчас", callback_data='publish_now'),
            InlineKeyboardButton("⏰ Запланировать", callback_data='schedule_later'),
            InlineKeyboardButton("🗑 Удалить", callback_data='delete_card')
        )

        bot.send_media_group(call.message.chat.id, media)
        safe_send_message(call.message.chat.id, "✅ Карточка товара создана. Что дальше?", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data == 'finish_outfit':
        state = user_state.get(user_id)
        if not state or state.get('step') != 'outfit_photo':
            return bot.answer_callback_query(call.id, "⏳ Невозможно завершить сейчас.")

        if 'photos' not in state or not state['photos']:
            return bot.answer_callback_query(call.id, "⚠️ Добавьте хотя бы одно фото.")

        outfit_text = "✨ <b>СТИЛЬНЫЙ АУТФИТ</b> ✨\n\n"
        for i, item in enumerate(state['outfit_items'], 1):
            outfit_text += (
                f"🧥 <b>#{i}</b> — <a href=\"{item['link']}\">{item['title']}</a>\n"
                f"💸 Цена: <b>{item['price']}</b>\n"
                f"⭐ Рейтинг: <b>{item['rating']}</b>\n"
                f"🔢 Артикул: <code>{item['sku']}</code>\n\n"
            )
        tags = state.get('tags', '')
        if tags:
            outfit_text += f"🏷️ {tags}"

        media = [types.InputMediaPhoto(p) for p in state['photos']]
        media[0].caption = outfit_text
        media[0].parse_mode = 'HTML'
        state['outfit_caption'] = outfit_text

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📤 Опубликовать сейчас", callback_data='publish_now_outfit'),
            InlineKeyboardButton("⏰ Запланировать", callback_data='schedule_outfit'),
            InlineKeyboardButton("🗑 Удалить", callback_data='delete_outfit')
        )

        bot.send_media_group(call.message.chat.id, media)
        safe_send_message(call.message.chat.id, "✅ Аутфит готов. Что дальше?", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data == 'publish_now':
        state = user_state.get(user_id)
        if not state:
            return bot.answer_callback_query(call.id, "❌ Нет данных")
        media = [types.InputMediaPhoto(p) for p in state['photos']]
        media[0].caption = state['product_caption']
        media[0].parse_mode = 'HTML'
        bot.send_media_group(CHANNEL_ID, media)
        safe_send_message(call.message.chat.id, "✅ Опубликовано в канал.")
        user_state.pop(user_id, None)
        bot.answer_callback_query(call.id)

    elif call.data == 'publish_now_outfit':
        state = user_state.get(user_id)
        if not state:
            return bot.answer_callback_query(call.id, "❌ Нет данных")
        media = [types.InputMediaPhoto(p) for p in state['photos']]
        media[0].caption = state['outfit_caption']
        media[0].parse_mode = 'HTML'
        bot.send_media_group(CHANNEL_ID, media)
        safe_send_message(call.message.chat.id, "✅ Аутфит опубликован в канал.")
        user_state.pop(user_id, None)
        bot.answer_callback_query(call.id)

    elif call.data == 'schedule_later':
        user_state[user_id]['step'] = 'schedule_time'
        safe_send_message(call.message.chat.id, "🕒 Введите время публикации в формате <code>HH:MM</code>", parse_mode='HTML')
        bot.answer_callback_query(call.id)

    elif call.data == 'schedule_outfit':
        user_state[user_id]['step'] = 'schedule_time_outfit'
        safe_send_message(call.message.chat.id, "🕒 Введите время публикации аутфита в формате <code>HH:MM</code>", parse_mode='HTML')
        bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: m.from_user.id in user_state and m.content_type == 'text')
def handle_steps(message):
    user_id = message.from_user.id
    state = user_state[user_id]

    if state.get('is_user') and state['step'] == 'user_title':
        state['title'] = message.text
        state['step'] = 'user_price'
        safe_send_message(message.chat.id, "💰 Введите <b>цену</b> товара:\n (например: 1347 руб.)", parse_mode='HTML')

    elif state.get('is_user') and state['step'] == 'user_price':
        state['price'] = message.text
        state['step'] = 'user_rating'
        safe_send_message(message.chat.id, "⭐ Введите <b>рейтинг</b> товара от 1 до 5:\n (например: 4.6)", parse_mode='HTML')

    elif state.get('is_user') and state['step'] == 'user_rating':
        state['rating'] = message.text
        state['step'] = 'user_sku'
        safe_send_message(message.chat.id, "🔢 Введите <b>артикул</b>:", parse_mode='HTML')

    elif state.get('is_user') and state['step'] == 'user_sku':
        state['sku'] = message.text
        state['step'] = 'user_link'
        safe_send_message(message.chat.id, "🔗 Введите <b>ссылку</b> на товар:\n (например: https://www.wildberries.ru/catalog/4534556/detail.aspx)", parse_mode='HTML')

    elif state.get('is_user') and state['step'] == 'user_link':
        state['link'] = message.text
        state['step'] = 'user_tags'
        safe_send_message(message.chat.id, "🏷️ Введите теги (например: #лето #стиль):")

    elif state.get('is_user') and state['step'] == 'user_tags':
        state['tags'] = message.text
        state['step'] = 'user_photo'
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Готово", callback_data='user_finish_photos'))
        safe_send_message(message.chat.id, "📸 Отправьте <b>фото</b> и нажмите <b>Готово</b>", parse_mode='HTML', reply_markup=markup)

    if state['step'] == 'title':
        state['title'] = message.text
        state['step'] = 'price'
        safe_send_message(message.chat.id, "💰 Введите <b>цену</b> товара:", parse_mode='HTML')

    elif state['step'] == 'price':
        state['price'] = message.text
        state['step'] = 'rating'
        safe_send_message(message.chat.id, "⭐ Введите <b>рейтинг</b> товара:", parse_mode='HTML')

    elif state['step'] == 'rating':
        state['rating'] = message.text
        state['step'] = 'sku'
        safe_send_message(message.chat.id, "🔢 Введите <b>артикул</b> товара:", parse_mode='HTML')

    elif state['step'] == 'sku':
        state['sku'] = message.text
        state['step'] = 'link'
        safe_send_message(message.chat.id, "🔗 Введите <b>ссылку на товар</b>:", parse_mode='HTML')

    elif state['step'] == 'link':
        state['link'] = message.text
        state['step'] = 'tags'
        safe_send_message(message.chat.id, "🏷️ Введите теги через пробел (например: #лето #новинка):")

    elif state['step'] == 'tags':
        state['tags'] = message.text
        state['step'] = 'photo'
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Готово", callback_data='finish_photos'))
        safe_send_message(message.chat.id, "📸 Отправьте <b>фото</b> товара и нажмите <b>Готово</b>", parse_mode='HTML', reply_markup=markup)

    elif state['step'] == 'schedule_time':
        try:
            datetime.strptime(message.text.strip(), '%H:%M')
            media = [types.InputMediaPhoto(p) for p in state['photos']]
            media[0].caption = state['product_caption']
            media[0].parse_mode = 'HTML'
            scheduled_posts.append({'time': message.text.strip(), 'media': media})
            bot.send_message(message.chat.id, f"✅ Карточка товара запланирована на {message.text.strip()}")
            user_state.pop(user_id, None)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Неверный формат. Используйте HH:MM")

    elif state['step'] == 'schedule_time_outfit':
        try:
            datetime.strptime(message.text.strip(), '%H:%M')
            media = [types.InputMediaPhoto(p) for p in state['photos']]
            media[0].caption = state['outfit_caption']
            media[0].parse_mode = 'HTML'
            scheduled_posts.append({'time': message.text.strip(), 'media': media})
            bot.send_message(message.chat.id, f"✅ Аутфит запланирован на {message.text.strip()}")
            user_state.pop(user_id, None)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Неверный формат. Используйте HH:MM")

    elif state['step'] == 'outfit_count':
        try:
            count = int(message.text)
            if 1 <= count <= 10:
                state['outfit_total'] = count
                state['step'] = 'outfit_title'
                state['current_index'] = 0
                safe_send_message(message.chat.id, "🧥 Вещь 1: Введите <b>название</b>:", parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "⚠️ Введите число от 1 до 10.")
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Введите число.")

    elif state['step'] == 'outfit_title':
        state.setdefault('current_item', {})['title'] = message.text
        state['step'] = 'outfit_price'
        safe_send_message(message.chat.id, "💰 Введите <b>цену</b> этой вещи:", parse_mode='HTML')

    elif state['step'] == 'outfit_price':
        state['current_item']['price'] = message.text
        state['step'] = 'outfit_sku'
        safe_send_message(message.chat.id, "🔢 Введите <b>артикул</b> этой вещи:", parse_mode='HTML')

    elif state['step'] == 'outfit_sku':
        state['current_item']['sku'] = message.text
        state['step'] = 'outfit_rating'
        safe_send_message(message.chat.id, "⭐ Введите <b>рейтинг</b> этой вещи:", parse_mode='HTML')

    elif state['step'] == 'outfit_rating':
        state['current_item']['rating'] = message.text
        state['step'] = 'outfit_link'
        safe_send_message(message.chat.id, "🔗 Введите <b>ссылку</b> на вещь:", parse_mode='HTML')

    elif state['step'] == 'outfit_link':
        state['current_item']['link'] = message.text
        state['outfit_items'].append(state['current_item'])
        state['current_index'] += 1
        state['current_item'] = {}
        if state['current_index'] < state['outfit_total']:
            safe_send_message(message.chat.id, f"👥 Вещь {state['current_index'] + 1}: Введите <b>название</b>:", parse_mode='HTML')
            state['step'] = 'outfit_title'
        else:
            state['step'] = 'outfit_tags'
            safe_send_message(message.chat.id, "🍿 Введите теги для аутфита (например: #лето #стиль):")

    elif state['step'] == 'outfit_tags':
        state['tags'] = message.text
        state['step'] = 'outfit_photo'
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Готово", callback_data='finish_outfit'))
        bot.send_message(message.chat.id, "📸 Отправьте <b>фото</b> для аутфита и нажмите <b>Готово</b>", parse_mode='HTML', reply_markup=markup)


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_id in user_state:
        step = user_state[user_id].get('step')
        if step in ['photo', 'outfit_photo']:
            photo_id = message.photo[-1].file_id
            user_state[user_id].setdefault('photos', []).append(photo_id)
        elif step == 'user_photo':
            photo_id = message.photo[-1].file_id
            user_state[user_id].setdefault('photos', []).append(photo_id)


def scheduler_loop():
    while True:
        now = datetime.now().strftime('%H:%M')
        for post in scheduled_posts[:]:
            if post['time'] == now:
                try:
                    bot.send_media_group(CHANNEL_ID, post['media'])
                    scheduled_posts.remove(post)
                except Exception as e:
                    print("Ошибка при публикации:", e)
        time.sleep(30)


threading.Thread(target=scheduler_loop, daemon=True).start()


while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(5)

