import os
import logging
import httpx
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

(
    PART1_1ST, PART1_2ND, PART1_3RD, PART1_4TH, PART1_SCORER,
    PRED_HOME, PRED_AWAY,
    ADMIN_ADD_NAME, ADMIN_ADD_USERNAME, ADMIN_ADD_EMAIL,
    ADMIN_RESULT_MATCH, ADMIN_RESULT_HOME, ADMIN_RESULT_AWAY,
) = range(13)

TEAMS = [
  "Испания", "Франция", "Англия", "Германия", "Португалия",
    "Нидерланды", "Бельгия", "Австрия", "Швейцария", "Норвегия",
    "Шотландия", "Хорватия", "Турция", "Босния и Герцеговина",
    "Швеция", "Чехия",
    "Аргентина", "Бразилия", "Уругвай", "Колумбия", "Эквадор", "Парагвай",
    "США", "Мексика", "Канада", "Панама", "Гаити", "Кюрасао",
    "Марокко", "Сенегал", "Кот-д'Ивуар", "Египет", "Алжир",
    "ЮАР", "Тунис", "Кабо-Верде", "ДР Конго", "Гана",
    "Япония", "Южная Корея", "Иран", "Саудовская Аравия",
    "Австралия", "Иордания", "Узбекистан", "Ирак",
    "Катар", "Новая Зеландия",
]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def sb_get(table, params=None):
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), params=params)
    r.raise_for_status()
    return r.json()

def sb_post(table, data):
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=data)
    r.raise_for_status()
    return r.json()

def sb_patch(table, params, data):
    r = httpx.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), params=params, json=data)
    r.raise_for_status()
    return r.json()

def sb_rpc(func, data):
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/rpc/{func}", headers=sb_headers(), json=data)
    r.raise_for_status()
    return r.json()

def get_participant(telegram_id):
    res = sb_get("participants", {"telegram_id": f"eq.{telegram_id}", "select": "*"})
    return res[0] if res else None

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_part1_locked():
    matches = sb_get("matches", {"select": "kickoff_at", "order": "kickoff_at", "limit": "1"})
    if matches:
        kickoff = datetime.fromisoformat(matches[0]["kickoff_at"].replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= kickoff
    return False

def teams_keyboard(selected=None, page=0):
    per_page = 16
    start = page * per_page
    chunk = TEAMS[start:start + per_page]
    buttons = []
    row = []
    for team in chunk:
        mark = "✅ " if team == selected else ""
        row.append(InlineKeyboardButton(mark + team, callback_data=f"team:{team}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Другие команды", callback_data=f"page:{page-1}"))
    if start + per_page < len(TEAMS):
        nav.append(InlineKeyboardButton("Другие команды ➡️", callback_data=f"page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)

def score_keyboard(side):
    scores = ["0", "1", "2", "3", "4", "5+"]
    return InlineKeyboardMarkup([[InlineKeyboardButton(s, callback_data=f"score:{side}:{s}") for s in scores]])

def main_menu_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("🏆 Прогноз Топ-4 и бомбардир", callback_data="menu:part1")],
        [InlineKeyboardButton("⚽ Прогнозы на матчи", callback_data="menu:matches")],
        [InlineKeyboardButton("📊 Таблица лидеров", callback_data="menu:leaderboard")],
        [InlineKeyboardButton("📋 Мои прогнозы", callback_data="menu:my_predictions")],
    ]
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="menu:admin")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    participant = get_participant(str(user.id))
    if not participant or participant["payment_status"] != "paid":
        await update.message.reply_text(
            "👋 Привет! Это бот конкурса прогнозов на Чемпионат мира 2026.\n\n"
            "Чтобы участвовать, нужно оплатить взнос 25€.\n"
            "Если ты уже оплатил — напиши организаторам, мы все проверим и дадим доступ к боту."
        )
        return
    await update.message.reply_text(
        f"👋 Привет, {participant['name']}!\n\nЧто хочешь сделать?",
        reply_markup=main_menu_keyboard(user.id)
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]
    if action == "part1":
        await show_part1_menu(query, context)
    elif action == "matches":
        await show_matches_menu(query, context)
    elif action == "leaderboard":
        await show_leaderboard(query, context)
    elif action == "my_predictions":
        await show_my_predictions(query, context)
    elif action == "admin":
        await show_admin_panel(query, context)

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard(query.from_user.id))

async def show_part1_menu(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    locked = is_part1_locked()
    pred = sb_get("part1_predictions", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    if pred:
        p = pred[0]
        text = (
            "🏆 Твой прогноз на Топ-4 и бомбардира:\n\n"
            f"🥇 1 место: {p['team_1st'] or '—'}\n"
            f"🥈 2 место: {p['team_2nd'] or '—'}\n"
            f"🥉 3 место: {p['team_3rd'] or '—'}\n"
            f"4️⃣ 4 место: {p['team_4th'] or '—'}\n"
            f"⚽ Бомбардир: {p['top_scorer'] or '—'}\n\n"
        )
        if locked:
            text += "🔒 Прогноз заблокирован — турнир начался."
            await query.edit_message_text(text)
        else:
            text += "Можешь изменить прогноз до старта турнира."
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Изменить прогноз", callback_data="part1:edit")],
                [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
            ]))
    else:
        if locked:
            await query.edit_message_text("🔒 Прогноз на Топ-4 недоступен — турнир уже начался.")
        else:
            await query.edit_message_text(
                "🏆 Сделай прогноз на Топ-4 и лучшего бомбардира!\n\n"
                "🥇 1 место — 10 очков\n🥈 2 место — 8 очков\n"
                "🥉 3 место — 6 очков\n4️⃣ 4 место — 4 очка\n⚽ Бомбардир — 8 очков",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Сделать прогноз", callback_data="part1:edit")],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
                ])
            )

async def part1_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "part1:edit":
        context.user_data["part1"] = {}
        context.user_data["part1_step"] = "1st"
        await query.edit_message_text("🥇 Выбери команду — чемпион мира (1 место):", reply_markup=teams_keyboard())
        return PART1_1ST

async def part1_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page:"):
        page = int(query.data.split(":")[1])
        await query.edit_message_text("Выбери команду:", reply_markup=teams_keyboard(page=page))
        return PART1_1ST
    team = query.data.split(":")[1]
    step = context.user_data.get("part1_step")
    context.user_data["part1"][step] = team
    next_steps = {
        "1st": ("2nd", "🥈 Выбери команду — 2 место:"),
        "2nd": ("3rd", "🥉 Выбери команду — 3 место:"),
        "3rd": ("4th", "4️⃣ Выбери команду — 4 место:"),
    }
    if step == "4th":
        await query.edit_message_text("⚽ Напиши имя лучшего бомбардира турнира\n(например: Килиан Мбаппе):")
        return PART1_SCORER
    next_step, next_text = next_steps[step]
    context.user_data["part1_step"] = next_step
    await query.edit_message_text(next_text, reply_markup=teams_keyboard())
    return PART1_1ST

async def part1_scorer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scorer = update.message.text.strip()
    user = update.effective_user
    participant = get_participant(str(user.id))
    p = context.user_data["part1"]
    data = {
        "participant_id": participant["id"],
        "team_1st": p["1st"], "team_2nd": p["2nd"],
        "team_3rd": p["3rd"], "team_4th": p["4th"],
        "top_scorer": scorer,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    existing = sb_get("part1_predictions", {"participant_id": f"eq.{participant['id']}", "select": "id"})
    if existing:
        sb_patch("part1_predictions", {"participant_id": f"eq.{participant['id']}"}, data)
    else:
        sb_post("part1_predictions", data)
    await update.message.reply_text(
        f"✅ Прогноз сохранён!\n\n🥇 {p['1st']}\n🥈 {p['2nd']}\n🥉 {p['3rd']}\n4️⃣ {p['4th']}\n⚽ {scorer}",
        reply_markup=main_menu_keyboard(user.id)
    )
    return ConversationHandler.END

async def show_matches_menu(query, context):
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    if not days:
        await query.edit_message_text("⚽ Расписание матчей ещё не добавлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
        return
    now = datetime.now(timezone.utc)
    buttons = []
    for day in days:
        deadline = datetime.fromisoformat(day["deadline"].replace("Z", "+00:00"))
        locked = now >= deadline
        matches = sb_get("matches", {"game_day_id": f"eq.{day['id']}", "select": "id,is_finished"})
        total = len(matches)
        finished = sum(1 for m in matches if m["is_finished"])
        status = "✅" if (finished == total and total > 0) else ("🔒" if locked else "📝")
        buttons.append([InlineKeyboardButton(f"{status} День {day['day_number']} ({finished}/{total})", callback_data=f"gameday:{day['id']}")])
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    await query.edit_message_text("⚽ Выбери игровой день:\n\n📝 открыт  🔒 заблокирован  ✅ сыгран",
        reply_markup=InlineKeyboardMarkup(buttons))

async def show_game_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_day_id = query.data.split(":")[1]
    user = query.from_user
    participant = get_participant(str(user.id))
    day = sb_get("game_days", {"id": f"eq.{game_day_id}", "select": "*"})[0]
    deadline = datetime.fromisoformat(day["deadline"].replace("Z", "+00:00"))
    locked = datetime.now(timezone.utc) >= deadline
    matches = sb_get("matches", {"game_day_id": f"eq.{game_day_id}", "select": "*", "order": "kickoff_at"})
    match_ids = [m["id"] for m in matches]
    preds_res = sb_get("predictions", {
        "participant_id": f"eq.{participant['id']}",
        "match_id": f"in.({','.join(match_ids)})",
        "select": "*"
    }) if match_ids else []
    preds = {p["match_id"]: p for p in preds_res}
    text = f"📅 День {day['day_number']}\n" + ("🔒 Прогнозы заблокированы\n\n" if locked else "📝 Открыт для прогнозов\n\n")
    buttons = []
    for m in matches:
        pred = preds.get(m["id"])
        kickoff = datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00"))
        time_str = kickoff.strftime("%d.%m %H:%M")
        if pred:
            score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
            double_mark = " 🔥×2" if pred["is_double"] else ""
            if m["is_finished"]:
                label = f"✅ {m['home_team']} {score} {m['away_team']} (факт: {m['home_score']}:{m['away_score']}, +{pred['points_earned']}){double_mark}"
            else:
                label = f"📝 {m['home_team']} {score} {m['away_team']} {time_str}{double_mark}"
        else:
            label = f"❓ {m['home_team']} — {m['away_team']} {time_str}"
        if not locked and not m["is_finished"]:
            buttons.append([InlineKeyboardButton(label, callback_data=f"predict:{m['id']}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="menu:matches")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def start_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "noop":
        return
    match = sb_get("matches", {"id": f"eq.{query.data.split(':')[1]}", "select": "*"})[0]
    context.user_data["pred_match"] = match
    await query.edit_message_text(
        f"⚽ {match['home_team']} — {match['away_team']}\n\nСколько голов забьёт {match['home_team']}?",
        reply_markup=score_keyboard("home")
    )
    return PRED_HOME

async def pred_home_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    score = query.data.split(":")[2]
    context.user_data["pred_home"] = 5 if score == "5+" else int(score)
    match = context.user_data["pred_match"]
    await query.edit_message_text(
        f"⚽ {match['home_team']} — {match['away_team']}\nХозяева: {score}\n\nСколько голов забьёт {match['away_team']}?",
        reply_markup=score_keyboard("away")
    )
    return PRED_AWAY

async def pred_away_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    score = query.data.split(":")[2]
    away_val = 5 if score == "5+" else int(score)
    context.user_data["pred_away"] = away_val
    match = context.user_data["pred_match"]
    home_val = context.user_data["pred_home"]
    await query.edit_message_text(
        f"⚽ {match['home_team']} {home_val}:{away_val} {match['away_team']}\n\n"
        "🔥 Сделать этот матч своим X2?\nОчки удвоятся. Только один X2 на день!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 Да, X2!", callback_data="double:yes"),
            InlineKeyboardButton("Нет", callback_data="double:no"),
        ]])
    )
    return PRED_AWAY

async def pred_double(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_double = query.data == "double:yes"
    user = query.from_user
    participant = get_participant(str(user.id))
    match = context.user_data["pred_match"]
    home_score = context.user_data["pred_home"]
    away_score = context.user_data["pred_away"]
    if is_double:
        day_matches = sb_get("matches", {"game_day_id": f"eq.{match['game_day_id']}", "select": "id"})
        day_ids = ",".join(m["id"] for m in day_matches)
        sb_patch("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"in.({day_ids})"}, {"is_double": False})
    data = {
        "participant_id": participant["id"], "match_id": match["id"],
        "home_score_pred": home_score, "away_score_pred": away_score,
        "is_double": is_double, "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_calculated": False, "points_earned": 0,
    }
    existing = sb_get("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match['id']}", "select": "id"})
    if existing:
        sb_patch("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match['id']}"}, data)
    else:
        sb_post("predictions", data)
    double_text = " 🔥×2" if is_double else ""
    await query.edit_message_text(
        f"✅ Прогноз сохранён!\n\n⚽ {match['home_team']} {home_score}:{away_score} {match['away_team']}{double_text}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад к матчам", callback_data=f"gameday:{match['game_day_id']}")]])
    )
    return ConversationHandler.END

async def show_my_predictions(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    preds = sb_get("predictions", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    if not preds:
        await query.edit_message_text("У тебя пока нет прогнозов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
        return
    text = "📋 Твои прогнозы:\n\n"
    total = 0
    for p in preds:
        match = sb_get("matches", {"id": f"eq.{p['match_id']}", "select": "*"})[0]
        double = " 🔥×2" if p["is_double"] else ""
        pred_score = f"{p['home_score_pred']}:{p['away_score_pred']}"
        if match["is_finished"]:
            pts = p["points_earned"]
            total += pts
            text += f"✅ {match['home_team']} {pred_score} {match['away_team']} (факт: {match['home_score']}:{match['away_score']}, +{pts}){double}\n"
        else:
            kickoff = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00"))
            text += f"📝 {match['home_team']} {pred_score} {match['away_team']} {kickoff.strftime('%d.%m %H:%M')}{double}\n"
    text += f"\n💰 Очков за матчи: {total}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))

async def show_leaderboard(query, context):
    lb = sb_get("leaderboard", {"select": "total_points,participants(name)", "order": "total_points.desc", "limit": "20"})
    if not lb:
        await query.edit_message_text("Таблица лидеров пока пуста.")
        return
    text = "📊 Таблица лидеров (топ-20):\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, entry in enumerate(lb, 1):
        text += f"{medals.get(i, f'{i}.')} {entry['participants']['name']} — {entry['total_points']} очков\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))

async def show_admin_panel(query, context):
    if not is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.edit_message_text("🔧 Админ-панель", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить участника", callback_data="admin:add_user")],
        [InlineKeyboardButton("⚽ Ввести результат матча", callback_data="admin:add_result")],
        [InlineKeyboardButton("📋 Список участников", callback_data="admin:list_users")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
    ]))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    action = query.data.split(":")[1]
    if action == "add_user":
        await query.edit_message_text("➕ Введи имя участника:")
        return ADMIN_ADD_NAME
    elif action == "add_result":
        await query.edit_message_text("⚽ Введи номер матча (match_number):")
        return ADMIN_RESULT_MATCH
    elif action == "list_users":
        users = sb_get("participants", {"select": "*", "order": "created_at"})
        if not users:
            await query.edit_message_text("Участников пока нет.")
            return
        text = "📋 Участники:\n\n"
        for u in users:
            method = "💳" if u["payment_method"] == "stripe" else "🤝"
            tg = f"@{u['telegram_username']}" if u.get("telegram_username") else "нет username"
            text += f"{method} {u['name']} ({tg})\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")]]))

async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_user_name"] = update.message.text.strip()
    await update.message.reply_text("Telegram username (без @) или 'нет':")
    return ADMIN_ADD_USERNAME

async def admin_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["new_user_username"] = None if val.lower() == "нет" else val
    await update.message.reply_text("Email участника (или 'нет'):")
    return ADMIN_ADD_EMAIL

async def admin_add_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    email = None if val.lower() == "нет" else val
    name = context.user_data["new_user_name"]
    username = context.user_data.get("new_user_username")
    sb_post("participants", {
        "name": name, "telegram_username": username, "email": email,
        "payment_status": "paid", "payment_method": "manual",
        "paid_at": datetime.now(timezone.utc).isoformat(),
    })
    await update.message.reply_text(
        f"✅ Участник добавлен!\n{name} (@{username or '—'})\n\nПопроси его написать боту /start",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

async def admin_result_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        num = int(update.message.text.strip())
        match = sb_get("matches", {"match_number": f"eq.{num}", "select": "*"})
        if not match:
            await update.message.reply_text("Матч не найден. Попробуй ещё раз:")
            return ADMIN_RESULT_MATCH
        context.user_data["result_match"] = match[0]
        m = match[0]
        await update.message.reply_text(f"Матч #{num}: {m['home_team']} — {m['away_team']}\nВведи голы хозяев:")
        return ADMIN_RESULT_HOME
    except ValueError:
        await update.message.reply_text("Введи число:")
        return ADMIN_RESULT_MATCH

async def admin_result_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["result_home"] = int(update.message.text.strip())
        await update.message.reply_text("Введи голы гостей:")
        return ADMIN_RESULT_AWAY
    except ValueError:
        await update.message.reply_text("Введи число:")
        return ADMIN_RESULT_HOME

async def admin_result_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        away = int(update.message.text.strip())
        match = context.user_data["result_match"]
        home = context.user_data["result_home"]
        sb_patch("matches", {"id": f"eq.{match['id']}"}, {"home_score": home, "away_score": away, "is_finished": True})
        sb_rpc("calculate_match_points", {"p_match_id": match["id"]})
        await update.message.reply_text(
            f"✅ Результат сохранён!\n{match['home_team']} {home}:{away} {match['away_team']}\nОчки пересчитаны.",
            reply_markup=main_menu_keyboard(update.effective_user.id)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Введи число:")
        return ADMIN_RESULT_AWAY

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    part1_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(part1_callback, pattern="^part1:")],
        states={
            PART1_1ST: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|page:)")],
            PART1_2ND: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|page:)")],
            PART1_3RD: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|page:)")],
            PART1_4TH: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|page:)")],
            PART1_SCORER: [MessageHandler(filters.TEXT & ~filters.COMMAND, part1_scorer)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    pred_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_prediction, pattern="^predict:")],
        states={
            PRED_HOME: [CallbackQueryHandler(pred_home_score, pattern="^score:home:")],
            PRED_AWAY: [
                CallbackQueryHandler(pred_away_score, pattern="^score:away:"),
                CallbackQueryHandler(pred_double, pattern="^double:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin:add_user$")],
        states={
            ADMIN_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_name)],
            ADMIN_ADD_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_username)],
            ADMIN_ADD_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_result_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin:add_result$")],
        states={
            ADMIN_RESULT_MATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_result_match)],
            ADMIN_RESULT_HOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_result_home)],
            ADMIN_RESULT_AWAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_result_away)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(part1_conv)
    app.add_handler(pred_conv)
    app.add_handler(admin_add_conv)
    app.add_handler(admin_result_conv)
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu:"))
    app.add_handler(CallbackQueryHandler(show_game_day, pattern="^gameday:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin:list_users$"))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back:"))

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
