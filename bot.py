import os
import logging
import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY")
WC2026_ID = 1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

(
    PART1_1ST, PART1_2ND, PART1_3RD, PART1_4TH, PART1_SCORER,
    ADMIN_ADD_NAME, ADMIN_ADD_USERNAME, ADMIN_ADD_EMAIL,
    ADMIN_RESULT_AWAY,
    ADMIN_SET_TEAMS_HOME, ADMIN_SET_TEAMS_AWAY,
    ADMIN_PART1_1ST, ADMIN_PART1_2ND, ADMIN_PART1_3RD, ADMIN_PART1_4TH, ADMIN_PART1_SCORER,
    SETTEAMS_HOME, SETTEAMS_AWAY,
    FAV_TEAM,
) = range(19)

TEAMS = [
    "🇫🇷 Франция", "🇪🇸 Испания", "🇦🇷 Аргентина", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Англия",
    "🇵🇹 Португалия", "🇧🇷 Бразилия", "🇳🇱 Нидерланды", "🇲🇦 Марокко",
    "🇧🇪 Бельгия", "🇩🇪 Германия", "🇭🇷 Хорватия", "🇺🇸 США",
    "🇺🇾 Уругвай", "🇨🇴 Колумбия", "🇦🇹 Австрия", "🇨🇭 Швейцария",
    "🇯🇵 Япония", "🇸🇳 Сенегал", "🇪🇨 Эквадор", "🇵🇦 Панама",
    "🇲🇽 Мексика", "🇰🇷 Ю. Корея", "🇳🇴 Норвегия", "🇹🇷 Турция",
    "🇦🇺 Австралия", "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Шотландия", "🇮🇷 Иран", "🇩🇿 Алжир",
    "🇪🇬 Египет", "🇸🇦 Саудовская Аравия", "🇨🇦 Канада", "🇶🇦 Катар",
    "🇯🇴 Иордания", "🇺🇿 Узбекистан", "🇨🇮 Кот-д'Ивуар", "🇹🇳 Тунис",
    "🇵🇾 Парагвай", "🇮🇶 Ирак", "🇿🇦 ЮАР", "🇬🇭 Гана",
    "🇧🇦 Босния", "🇸🇪 Швеция", "🇨🇿 Чехия", "🇳🇿 Н. Зеландия",
    "🇨🇩 ДР Конго", "🇨🇻 Кабо-Верде", "🇭🇹 Гаити", "🇨🇼 Кюрасао",
]

DAY_DATES = {
    # Групповой этап
    1: "11 июня", 2: "12 июня", 3: "13 июня", 4: "14 июня",
    5: "15 июня", 6: "16 июня", 7: "17 июня", 8: "18 июня",
    9: "19 июня", 10: "20 июня", 11: "21 июня", 12: "22 июня",
    13: "23 июня", 14: "24 июня", 15: "25 июня", 16: "26 июня",
    17: "27 июня",
    # 1/16 финала (28 июня — 3 июля)
    18: "28 июня", 19: "29 июня", 20: "30 июня",
    21: "1 июля", 22: "2 июля", 23: "3 июля",
    # 1/8 финала (4-7 июля)
    24: "4 июля", 25: "5 июля", 26: "6 июля", 27: "7 июля",
    # 1/4 финала (9-11 июля)
    28: "9 июля", 29: "10 июля", 30: "11 июля",
    # Полуфиналы (14-15 июля)
    31: "14 июля", 32: "15 июля",
    # Матч за 3-е место (18 июля)
    33: "18 июля",
    # Финал (19 июля)
    34: "19 июля",
}

STAGE_LABELS = {
    "group1": "1 тур группового этапа",
    "group2": "2 тур группового этапа",
    "group3": "3 тур группового этапа",
    "r32": "1/16 финала", "r16": "1/8 финала",
    "qf": "1/4 финала", "sf": "Полуфинал",
    "3rd": "Матч за 3-е место", "final": "Финал",
}
STAGE_SHORT = {
    "group1": "1 тур", "group2": "2 тур", "group3": "3 тур",
    "r32": "1/16", "r16": "1/8", "qf": "1/4",
    "sf": "1/2", "3rd": "3-е место", "final": "Финал",
}
STAGE_EMOJI = {
    "group1": "⚽", "group2": "⚽", "group3": "⚽",
    "r32": "🔥", "r16": "🔥", "qf": "🔥",
    "sf": "🔥", "3rd": "🥉", "final": "🏆",
}
DAY_STAGE = {
    **{d: "group1" for d in range(1, 8)},
    **{d: "group2" for d in range(8, 14)},
    **{d: "group3" for d in range(14, 18)},
    **{d: "r32" for d in range(18, 24)},
    **{d: "r16" for d in range(24, 28)},
    **{d: "qf" for d in range(28, 31)},
    31: "sf", 32: "sf",
    33: "3rd",
    34: "final",
}
STAGES_ORDER = ["group1", "group2", "group3", "r32", "r16", "qf", "sf", "3rd", "final"]
DIRECT_STAGES = {"sf", "3rd", "final"}
NO_DOUBLE_STAGES = {"3rd", "final"}
PLAYOFF_STAGES = {"r32", "r16", "qf", "sf", "3rd", "final"}

def format_points(n):
    if 11 <= n % 100 <= 19:
        return f"{n} очков"
    r = n % 10
    if r == 1:
        return f"{n} очко"
    elif 2 <= r <= 4:
        return f"{n} очка"
    else:
        return f"{n} очков"

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

def sb_delete(table, params):
    r = httpx.delete(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), params=params)
    r.raise_for_status()

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

def format_time_cet(kickoff_str):
    dt = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
    dt_cet = dt.astimezone(timezone(timedelta(hours=2)))
    return dt_cet.strftime("%d.%m %H:%M")

def is_day_finished(matches):
    if not matches:
        return False
    now = datetime.now(timezone.utc)
    last_kickoff = max(datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00")) for m in matches)
    return now >= last_kickoff + timedelta(hours=3)

def has_tbd(matches):
    return any(m["home_team"] == "TBD" or m["away_team"] == "TBD" for m in matches)

def fuzzy_match(pred, actual_list):
    pred_clean = pred.lower().strip()
    for actual in actual_list:
        actual_clean = actual.lower().strip()
        if pred_clean in actual_clean or actual_clean in pred_clean:
            return True
    return False

def num_emoji(n):
    emojis = ["0️⃣","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣"]
    return emojis[n] if 0 <= n < len(emojis) else str(n)

def teams_keyboard(selected=None, page=0, prefix="team"):
    per_page = 16
    start = page * per_page
    chunk = TEAMS[start:start + per_page]
    buttons = []
    row = []
    for team in chunk:
        mark = "✅ " if team == selected else ""
        row.append(InlineKeyboardButton(mark + team, callback_data=f"{prefix}:{team}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Другие команды", callback_data=f"{prefix}_page:{page-1}"))
    if start + per_page < len(TEAMS):
        nav.append(InlineKeyboardButton("Другие команды ▶️", callback_data=f"{prefix}_page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)

def score_keyboard(match_id, home_score=None, away_score=None, is_double=False, no_double=False, admin_mode=False):
    digits = [str(i) for i in range(8)]
    home_row = [InlineKeyboardButton("✅" if str(home_score) == d else d,
        callback_data=f"{'ash' if admin_mode else 'sh'}:{match_id}:{d}") for d in digits]
    away_row = [InlineKeyboardButton("✅" if str(away_score) == d else d,
        callback_data=f"{'asa' if admin_mode else 'sa'}:{match_id}:{d}") for d in digits]
    buttons = [home_row, away_row]
    if home_score is not None and away_score is not None:
        if admin_mode:
            buttons.append([InlineKeyboardButton(f"✅ Сохранить результат {home_score}:{away_score}", callback_data=f"asave:{match_id}")])
        else:
            if not no_double:
                double_label = "🔥 X2 — ВКЛ (нажми чтобы выкл)" if is_double else "🔥 Сделать этот матч X2"
                buttons.append([InlineKeyboardButton(double_label, callback_data=f"double_toggle:{match_id}")])
            buttons.append([InlineKeyboardButton(f"✅ Сохранить {home_score}:{away_score}", callback_data=f"save_pred:{match_id}")])
    return InlineKeyboardMarkup(buttons)

def main_menu_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("🧪 Тест-турнир (9 мая)", callback_data="goto:test")],
        [InlineKeyboardButton("🏆 Прогноз на ТОП-4 ЧМ 2026", callback_data="menu:part1")],
        [InlineKeyboardButton("⚽ Прогнозы на матчи", callback_data="menu:matches")],
        [InlineKeyboardButton("📊 Таблица лидеров", callback_data="menu:leaderboard:0")],
        [InlineKeyboardButton("📋 Мои прогнозы", callback_data="menu:my_predictions")],
    ]
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="menu:admin")])
    return InlineKeyboardMarkup(buttons)

# ============================================
# /start + выбор любимой команды
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    participant = get_participant(str(user.id))
    if not participant or participant["payment_status"] != "paid":
        await update.message.reply_text(
            "👋 Привет! Это бот WAF Predictor — конкурс прогнозов на Чемпионат мира 2026.\n\n"
            "Чтобы участвовать, нужно оплатить взнос 25€.\n"
            "Если ты уже оплатил — напиши нам, мы исправим ошибку и подключим тебя к боту!"
        )
        return
    if not participant.get("favorite_team"):
        await update.message.reply_text(
            f"👋 Привет, {participant['name']}!\n\nДобро пожаловать на конкурс прогнозов Чемпионата Мира 2026!\n\n"
            "Прежде чем начать — выбери сборную за которую будешь болеть на турнире! "
            "Это нужно для командной таблицы.",
            reply_markup=teams_keyboard(prefix="fav")
        )
        return
    await update.message.reply_text(
        f"👋 Привет, {participant['name']}!\n\nДобро пожаловать на конкурс прогнозов Чемпионата Мира 2026!\n\n"
        "Мы отлично проведем ближайшие 6 недель! Выбери дальнейшие действия в меню.\n\n"
        "Советуем начать с прогноза на ТОП-4 чемпионата. Сделать его можно только до старта турнира.",
        reply_markup=main_menu_keyboard(user.id)
    )

async def fav_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("fav_page:"):
        page = int(query.data.split(":")[1])
        await query.edit_message_text(
            "Выбери сборную за которую будешь болеть:",
            reply_markup=teams_keyboard(prefix="fav", page=page)
        )
        return
    team = query.data.split(":", 1)[1]
    user = query.from_user
    participant = get_participant(str(user.id))
    sb_patch("participants", {"id": f"eq.{participant['id']}"}, {"favorite_team": team})
    await query.edit_message_text(
        f"🎉 Отлично! Ты болеешь за {team}!\n\n"
        "Мы отлично проведем ближайшие 6 недель! Выбери дальнейшие действия в меню.\n\n"
        "Советуем начать с прогноза на ТОП-4 чемпионата. Сделать его можно только до старта турнира.",
        reply_markup=main_menu_keyboard(user.id)
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    if action == "part1":
        await show_part1_menu(query, context)
    elif action == "matches":
        await show_stages_menu(query, context)
    elif action == "leaderboard":
        page = int(parts[2]) if len(parts) > 2 else 0
        await show_leaderboard(query, context, page)
    elif action == "my_predictions":
        await show_my_predictions_menu(query, context)
    elif action == "admin":
        await show_admin_panel(query, context)

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]
    if action == "main":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard(query.from_user.id))
    elif action == "stages":
        await show_stages_menu(query, context)

# ============================================
# ЧАСТЬ 1 — ТОП-4
# ============================================

async def show_part1_menu(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    locked = is_part1_locked()
    pred = sb_get("part1_predictions", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    if pred:
        p = pred[0]
        text = "🏆 Твой прогноз на Топ-4 и бомбардира:\n\n"
        if p.get("points_calculated"):
            text += f"🥇 1 место: {p['team_1st'] or '—'} {'✅' if p.get('pts_1st') else '❌'} +{format_points(p.get('pts_1st',0))}\n"
            text += f"🥈 2 место: {p['team_2nd'] or '—'} {'✅' if p.get('pts_2nd') else '❌'} +{format_points(p.get('pts_2nd',0))}\n"
            text += f"🥉 3 место: {p['team_3rd'] or '—'} {'✅' if p.get('pts_3rd') else '❌'} +{format_points(p.get('pts_3rd',0))}\n"
            text += f"4️⃣ 4 место: {p['team_4th'] or '—'} {'✅' if p.get('pts_4th') else '❌'} +{format_points(p.get('pts_4th',0))}\n"
            text += f"⚽ Бомбардир: {p['top_scorer'] or '—'} {'✅' if p.get('pts_scorer') else '❌'} +{format_points(p.get('pts_scorer',0))}\n"
            total = sum([p.get(f'pts_{k}',0) for k in ['1st','2nd','3rd','4th','scorer']])
            text += f"\n💰 Итого: {format_points(total)}"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
        else:
            text += f"🥇 1 место: {p['team_1st'] or '—'}\n"
            text += f"🥈 2 место: {p['team_2nd'] or '—'}\n"
            text += f"🥉 3 место: {p['team_3rd'] or '—'}\n"
            text += f"4️⃣ 4 место: {p['team_4th'] or '—'}\n"
            text += f"⚽ Бомбардир: {p['top_scorer'] or '—'}\n\n"
            if locked:
                text += "🔒 Прогноз заблокирован — турнир начался."
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
            else:
                text += "Можешь изменить прогноз до старта турнира."
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Изменить прогноз", callback_data="part1:edit")],
                    [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
                ]))
    else:
        if locked:
            await query.edit_message_text("🔒 Прогноз на Топ-4 недоступен — турнир уже начался.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
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
        await query.edit_message_text("🥇 Кто станет чемпионом мира?:", reply_markup=teams_keyboard())
        return PART1_1ST

async def part1_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("team_page:"):
        page = int(query.data.split(":")[1])
        await query.edit_message_text("Выбери команду:", reply_markup=teams_keyboard(page=page))
        return PART1_1ST
    team = query.data.split(":", 1)[1]
    step = context.user_data.get("part1_step")
    context.user_data["part1"][step] = team
    next_steps = {
        "1st": ("2nd", "🥈 Кто займет 2 место?"),
        "2nd": ("3rd", "🥉 Кто займет 3 место?"),
        "3rd": ("4th", "4️⃣ Кто займет 4 место?"),
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

# ============================================
# МАТЧИ
# ============================================

async def show_stages_menu(query, context):
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    if not days:
        await query.edit_message_text("⚽ Расписание матчей ещё не добавлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
        return
    stages_present = set(DAY_STAGE.get(d["day_number"], "group1") for d in days)
    buttons = []
    for stage in STAGES_ORDER:
        if stage not in stages_present:
            continue
        emoji = STAGE_EMOJI.get(stage, "📁")
        buttons.append([InlineKeyboardButton(f"{emoji} {STAGE_LABELS[stage]}", callback_data=f"stage:{stage}")])
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    await query.edit_message_text("⚽ Выбери этап турнира:", reply_markup=InlineKeyboardMarkup(buttons))

async def show_stage_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stage = query.data.split(":")[1]
    if stage in DIRECT_STAGES:
        await show_direct_stage_matches(query, context, stage)
        return
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    now = datetime.now(timezone.utc)
    buttons = []
    for day in days:
        if DAY_STAGE.get(day["day_number"]) != stage:
            continue
        deadline = datetime.fromisoformat(day["deadline"].replace("Z", "+00:00"))
        locked = now >= deadline
        matches = sb_get("matches", {"game_day_id": f"eq.{day['id']}", "select": "id,is_finished,kickoff_at,home_team,away_team"})
        total = len(matches)
        finished = sum(1 for m in matches if m["is_finished"])
        finished_auto = is_day_finished(matches)
        tbd = has_tbd(matches) and stage in PLAYOFF_STAGES
        if finished_auto or (finished == total and total > 0):
            status = "✅"
        elif tbd:
            status = "❓"
        elif locked:
            status = "🔒"
        else:
            status = "📝"
        date_str = DAY_DATES.get(day["day_number"], "")
        short = STAGE_SHORT.get(stage, "")
        label = f"{status} День {day['day_number']} — {date_str} ({finished}/{total}) · {short}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"gameday:{day['id']}")])
    buttons.append([InlineKeyboardButton("◀️ К другим этапам", callback_data="back:stages")])
    await query.edit_message_text(
        f"{STAGE_EMOJI.get(stage,'📁')} {STAGE_LABELS.get(stage,'')}\n\n📝 открыт  🔒 заблокирован  ✅ сыгран  ❓ команды не определены",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_direct_stage_matches(query, context, stage):
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    user = query.from_user
    participant = get_participant(str(user.id))
    now = datetime.now(timezone.utc)
    no_double = stage in NO_DOUBLE_STAGES
    all_matches = []
    for day in days:
        if DAY_STAGE.get(day["day_number"]) != stage:
            continue
        matches = sb_get("matches", {"game_day_id": f"eq.{day['id']}", "select": "*", "order": "kickoff_at"})
        all_matches.extend(matches)
    if not all_matches:
        await query.edit_message_text(
            f"{STAGE_EMOJI.get(stage)} {STAGE_LABELS.get(stage)}\n\nМатчи ещё не определены.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К другим этапам", callback_data="back:stages")]])
        )
        return
    match_ids = [m["id"] for m in all_matches]
    preds_res = sb_get("predictions", {
        "participant_id": f"eq.{participant['id']}",
        "match_id": f"in.({','.join(match_ids)})",
        "select": "*"
    })
    preds = {p["match_id"]: p for p in preds_res}
    finished_auto = is_day_finished(all_matches)
    tbd = has_tbd(all_matches)
    deadline = datetime.fromisoformat(
        sb_get("game_days", {"id": f"eq.{all_matches[0]['game_day_id']}", "select": "deadline"})[0]["deadline"].replace("Z", "+00:00")
    )
    locked = now >= deadline
    text = f"{STAGE_EMOJI.get(stage)} {STAGE_LABELS.get(stage)}\n"
    if no_double:
        text += "ℹ️ X2 в этом матче недоступен\n"
    if finished_auto:
        text += "✅ День завершён\n\n"
    elif tbd:
        text += "❓ Команды не определены\n\n"
    elif locked:
        text += "🔒 Прогнозы закрыты\n\n"
    else:
        text += "📝 Открыт для прогнозов\n\n"
    buttons = []
    for m in all_matches:
        pred = preds.get(m["id"])
        time_str = format_time_cet(m["kickoff_at"])
        if pred:
            score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
            double_mark = " 🔥×2" if pred["is_double"] and not no_double else ""
            label = f"📝 {m['home_team']} {score} {m['away_team']} {time_str}{double_mark}"
        else:
            label = f"{m['home_team']} — : — {m['away_team']} {time_str}"
        if not locked and not m["is_finished"] and not tbd:
            buttons.append([InlineKeyboardButton(label, callback_data=f"predict:{m['id']}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
    buttons.append([InlineKeyboardButton("◀️ К другим этапам", callback_data="back:stages")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

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
    date_str = DAY_DATES.get(day["day_number"], "")
    stage = DAY_STAGE.get(day["day_number"], "group1")
    stage_label = STAGE_LABELS.get(stage, "")
    finished_auto = is_day_finished(matches)
    tbd = has_tbd(matches) and stage in PLAYOFF_STAGES
    text = f"📅 День {day['day_number']} — {date_str}\n{stage_label}\n"
    if finished_auto:
        text += "✅ День завершён\n\n"
        day_total = 0
        for m in matches:
            pred = preds.get(m["id"])
            real = f"{m['home_score']}:{m['away_score']}" if m["is_finished"] else "—:—"
            if pred:
                pred_score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
                pts = pred["points_earned"]
                day_total += pts
                if pred["is_double"] and pts > 0:
                    pts_str = f"+{pts//2} 🔥×2 = {format_points(pts)}"
                elif pred["is_double"]:
                    pts_str = "+0 🔥×2 = 0"
                else:
                    pts_str = f"+{format_points(pts)}"
                result_icon = "✅" if pts > 0 else "❌"
                text += f"{m['home_team']} {real} {m['away_team']}\nТвой прогноз: {pred_score} {result_icon} {pts_str}\n\n"
            else:
                text += f"{m['home_team']} {real} {m['away_team']}\nПрогноза не было\n\n"
        text += f"⚡️ Итого за день: {format_points(day_total)}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"stage:{stage}")]]))
        return
    if tbd:
        text += "❓ Команды не определены\n\n"
    elif locked:
        text += "🔒 Прогнозы закрыты\n\n"
    else:
        text += "Начало матчей по Центральноевропейскому времени (UTC+2)\n📝 Открыт для прогнозов\n\n"
    buttons = []
    for m in matches:
        pred = preds.get(m["id"])
        time_str = format_time_cet(m["kickoff_at"])
        if pred:
            score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
            double_mark = " 🔥×2" if pred["is_double"] else ""
            label = f"📝 {m['home_team']} {score} {m['away_team']} {time_str}{double_mark}"
        else:
            label = f"{m['home_team']} — : — {m['away_team']} {time_str}"
        if not locked and not m["is_finished"] and not tbd:
            buttons.append([InlineKeyboardButton(label, callback_data=f"predict:{m['id']}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data=f"stage:{stage}")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_prediction_screen(query, context, match_id, home_score=None, away_score=None, is_double=False, no_double=False):
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    time_str = format_time_cet(match["kickoff_at"])
    h = num_emoji(home_score) if home_score is not None else "—"
    a = num_emoji(away_score) if away_score is not None else "—"
    double_text = " 🔥×2" if is_double and not no_double else ""
    text = (
        f"⚽ {match['home_team']} vs {match['away_team']}\n"
        f"🕐 {time_str} (UTC+2)\n\n"
        f"{match['home_team']}:\n"
        f"{match['away_team']}:\n\n"
        f"Счёт: {h} : {a}{double_text}"
    )
    await query.edit_message_text(text, reply_markup=score_keyboard(match_id, home_score, away_score, is_double, no_double))

async def start_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "noop":
        return
    match_id = query.data.split(":")[1]
    user = query.from_user
    participant = get_participant(str(user.id))
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    day = sb_get("game_days", {"id": f"eq.{match['game_day_id']}", "select": "day_number"})[0]
    stage = DAY_STAGE.get(day["day_number"], "group1")
    no_double = stage in NO_DOUBLE_STAGES
    context.user_data[f"no_double_{match_id}"] = no_double
    existing = sb_get("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match_id}", "select": "*"})
    if existing:
        p = existing[0]
        context.user_data[f"home_{match_id}"] = p["home_score_pred"]
        context.user_data[f"away_{match_id}"] = p["away_score_pred"]
        context.user_data[f"double_{match_id}"] = p["is_double"]
    await show_prediction_screen(query, context, match_id,
        context.user_data.get(f"home_{match_id}"),
        context.user_data.get(f"away_{match_id}"),
        context.user_data.get(f"double_{match_id}", False), no_double)

async def handle_score_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"home_{match_id}"] = int(digit)
    await show_prediction_screen(query, context, match_id,
        context.user_data.get(f"home_{match_id}"),
        context.user_data.get(f"away_{match_id}"),
        context.user_data.get(f"double_{match_id}", False),
        context.user_data.get(f"no_double_{match_id}", False))

async def handle_score_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"away_{match_id}"] = int(digit)
    await show_prediction_screen(query, context, match_id,
        context.user_data.get(f"home_{match_id}"),
        context.user_data.get(f"away_{match_id}"),
        context.user_data.get(f"double_{match_id}", False),
        context.user_data.get(f"no_double_{match_id}", False))

async def handle_double_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    context.user_data[f"double_{match_id}"] = not context.user_data.get(f"double_{match_id}", False)
    await show_prediction_screen(query, context, match_id,
        context.user_data.get(f"home_{match_id}"),
        context.user_data.get(f"away_{match_id}"),
        context.user_data.get(f"double_{match_id}", False),
        context.user_data.get(f"no_double_{match_id}", False))

async def handle_save_pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    home_score = context.user_data.get(f"home_{match_id}")
    away_score = context.user_data.get(f"away_{match_id}")
    is_double = context.user_data.get(f"double_{match_id}", False)
    no_double = context.user_data.get(f"no_double_{match_id}", False)
    if no_double:
        is_double = False
    if home_score is None or away_score is None:
        await query.answer("Выбери счёт для обеих команд!", show_alert=True)
        return
    user = query.from_user
    participant = get_participant(str(user.id))
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    if is_double:
        day_matches = sb_get("matches", {"game_day_id": f"eq.{match['game_day_id']}", "select": "id"})
        day_ids = ",".join(m["id"] for m in day_matches)
        sb_patch("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"in.({day_ids})"}, {"is_double": False})
    data = {
        "participant_id": participant["id"], "match_id": match_id,
        "home_score_pred": home_score, "away_score_pred": away_score,
        "is_double": is_double, "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_calculated": False, "points_earned": 0,
    }
    existing = sb_get("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match_id}", "select": "id"})
    if existing:
        sb_patch("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match_id}"}, data)
    else:
        sb_post("predictions", data)
    double_text = " 🔥×2" if is_double else ""
    await query.edit_message_text(
        f"✅ Прогноз сохранён!\n\n⚽ {match['home_team']} {home_score}:{away_score} {match['away_team']}{double_text}\n\nМожешь изменить до начала матча.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад к матчам", callback_data=f"gameday:{match['game_day_id']}")]])
    )

# ============================================
# МОИ ПРОГНОЗЫ
# ============================================

async def show_my_predictions_menu(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    lb = sb_get("leaderboard", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    total = lb[0]["total_points"] if lb else 0
    part1 = lb[0]["part1_points"] if lb else 0
    part2 = lb[0]["part2_points"] if lb else 0
    text = f"📋 Мои прогнозы\n\n💰 Всего: {format_points(total)}\n"
    if part1 > 0:
        text += f"  └ За Топ-4 и бомбардира: {format_points(part1)}\n"
    text += f"  └ За матчи: {format_points(part2)}\n"
    buttons = [
        [InlineKeyboardButton("⚽ 1 тур", callback_data="mypred:group1")],
        [InlineKeyboardButton("⚽ 2 тур", callback_data="mypred:group2")],
        [InlineKeyboardButton("⚽ 3 тур", callback_data="mypred:group3")],
        [InlineKeyboardButton("🔥 Плей-офф", callback_data="mypred:playoff")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_my_predictions_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stage_key = query.data.split(":")[1]
    user = query.from_user
    participant = get_participant(str(user.id))
    stages = ["r32", "r16", "qf", "sf", "3rd", "final"] if stage_key == "playoff" else [stage_key]
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    day_ids = [d["id"] for d in days if DAY_STAGE.get(d["day_number"]) in stages]
    if not day_ids:
        await query.edit_message_text("Нет данных.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:my_predictions")]]))
        return
    all_matches = []
    for day_id in day_ids:
        matches = sb_get("matches", {"game_day_id": f"eq.{day_id}", "select": "*", "order": "kickoff_at"})
        all_matches.extend(matches)
    if not all_matches:
        await query.edit_message_text("Матчей пока нет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:my_predictions")]]))
        return
    match_ids = [m["id"] for m in all_matches]
    preds = sb_get("predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"in.({','.join(match_ids)})", "select": "*"})
    preds_map = {p["match_id"]: p for p in preds}
    label = "Плей-офф" if stage_key == "playoff" else STAGE_LABELS.get(stage_key, "")
    text = f"📋 {label}\n\n"
    total = 0
    for m in all_matches:
        pred = preds_map.get(m["id"])
        if not pred:
            continue
        double = " 🔥×2" if pred["is_double"] else ""
        pred_score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
        if m["is_finished"]:
            pts = pred["points_earned"]
            total += pts
            text += f"✅ {m['home_team']} {pred_score} {m['away_team']} → {m['home_score']}:{m['away_score']} +{format_points(pts)}{double}\n"
        else:
            time_str = format_time_cet(m["kickoff_at"])
            text += f"📝 {m['home_team']} {pred_score} {m['away_team']} {time_str}{double}\n"
    text += f"\n⚡️ Очков за этот этап: {format_points(total)}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:my_predictions")]]))

# ============================================
# ТАБЛИЦА ЛИДЕРОВ
# ============================================

async def show_leaderboard(query, context, page=0):
    per_page = 10
    offset = page * per_page
    lb = sb_get("leaderboard", {
        "select": "total_points,rank,participants(name,favorite_team)",
        "order": "total_points.desc",
        "limit": str(per_page),
        "offset": str(offset),
    })
    total_count = len(sb_get("leaderboard", {"select": "id"}))
    user = query.from_user
    participant = get_participant(str(user.id))
    my_lb = sb_get("leaderboard", {"participant_id": f"eq.{participant['id']}", "select": "total_points,rank"})
    my_rank = my_lb[0]["rank"] if my_lb else "—"
    my_pts = my_lb[0]["total_points"] if my_lb else 0
    if not lb:
        await query.edit_message_text("Таблица лидеров пока пуста.")
        return
    start_num = offset + 1
    end_num = offset + len(lb)
    text = f"📊 Таблица лидеров ({start_num}-{end_num} из {total_count})\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, entry in enumerate(lb, start_num):
        medal = medals.get(i, f"{i}.")
        name = entry["participants"]["name"]
        fav = entry["participants"].get("favorite_team", "")
        # Извлекаем только флаг из названия типа "🇧🇷 Бразилия"
        flag = fav.split(" ")[0] if fav else ""
        pts = entry["total_points"]
        text += f"{medal} {name} {flag} — {format_points(pts)}\n"
    text += f"\n👤 Твоё место: {my_rank} из {total_count} — {format_points(my_pts)}"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:leaderboard:{page-1}"))
    if end_num < total_count:
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"menu:leaderboard:{page+1}"))
    buttons = []
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("📊 Таблица сборных", callback_data="leaderboard:teams:0")])
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_teams_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2]) if len(query.data.split(":")) > 2 else 0
    per_page = 10
    offset = page * per_page
    # Получаем всех участников с их любимыми командами и очками
    all_lb = sb_get("leaderboard", {
        "select": "total_points,participants(name,favorite_team)",
        "order": "total_points.desc",
    })
    # Группируем по командам
    teams = {}
    for entry in all_lb:
        fav = entry["participants"].get("favorite_team", "")
        if not fav:
            continue
        if fav not in teams:
            teams[fav] = {"points": 0, "count": 0}
        teams[fav]["points"] += entry["total_points"]
        teams[fav]["count"] += 1
    # Сортируем по очкам
    sorted_teams = sorted(teams.items(), key=lambda x: x[1]["points"], reverse=True)
    total_teams = len(sorted_teams)
    chunk = sorted_teams[offset:offset + per_page]
    text = f"📊 Таблица сборных ({offset+1}-{min(offset+per_page, total_teams)} из {total_teams})\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, (team, data) in enumerate(chunk, offset + 1):
        medal = medals.get(i, f"{i}.")
        text += f"{medal} {team} — {format_points(data['points'])} ({data['count']} болельщиков)\n"
    text += "\n🏆 Сборная-чемпион по версии WAF Predictor!"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"leaderboard:teams:{page-1}"))
    if offset + per_page < total_teams:
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"leaderboard:teams:{page+1}"))
    buttons = []
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("👤 Личная таблица", callback_data="menu:leaderboard:0")])
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ============================================
# АВТО-РЕЗУЛЬТАТЫ
# ============================================

async def fetch_and_update_results(app):
    while True:
        try:
            await check_match_results()
            await check_test_match_results()
        except Exception as e:
            logger.error(f"Ошибка при получении результатов: {e}")
        await asyncio.sleep(15 * 60)

async def check_match_results():
    now = datetime.now(timezone.utc)
    matches = sb_get("matches", {"select": "*", "is_finished": "eq.false", "home_team": "neq.TBD"})
    for match in matches:
        if match.get("manual_result"):
            continue
        kickoff = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00"))
        if now < kickoff + timedelta(hours=2):
            continue
        await try_fetch_result(match)

async def try_fetch_result(match):
    try:
        date_str = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
        r = httpx.get(
            "https://api.football-data.org/v4/matches",
            headers=headers,
            params={"competitions": "WC", "dateFrom": date_str, "dateTo": date_str}
        )
        data = r.json()
        home_name = match["home_team"].split(" ", 1)[-1].strip()
        away_name = match["away_team"].split(" ", 1)[-1].strip()
        for fixture in data.get("matches", []):
            if fixture.get("status") != "FINISHED":
                continue
            h = fixture["homeTeam"]["name"]
            a = fixture["awayTeam"]["name"]
            if (home_name.lower() in h.lower() or h.lower() in home_name.lower()) and \
               (away_name.lower() in a.lower() or a.lower() in away_name.lower()):
                ft = fixture.get("score", {}).get("fullTime", {})
                home_score = ft.get("home")
                away_score = ft.get("away")
                if home_score is None or away_score is None:
                    continue
                sb_patch("matches", {"id": f"eq.{match['id']}"}, {
                    "home_score": home_score, "away_score": away_score, "is_finished": True,
                })
                sb_rpc("calculate_match_points", {"p_match_id": match["id"]})
                logger.info(f"✅ Авто-результат #{match['match_number']}: {home_score}:{away_score}")
                return
    except Exception as e:
        logger.error(f"Ошибка API матч #{match['match_number']}: {e}")

# ============================================
# АДМИН
# ============================================

async def show_admin_panel(query, context):
    if not is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.edit_message_text("🔧 Админ-панель", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить участника", callback_data="admin:add_user")],
        [InlineKeyboardButton("⚽ Ввести результат матча", callback_data="admin:result_stage")],
        [InlineKeyboardButton("🏆 Заполнить команды матча", callback_data="admin:set_teams_stage")],
        [InlineKeyboardButton("🥇 Ввести итоги Топ-4", callback_data="admin:part1_results")],
        [InlineKeyboardButton("🔄 Обнулить итоги Топ-4", callback_data="admin:part1_reset")],
        [InlineKeyboardButton("📋 Список участников", callback_data="admin:list_users")],
        [InlineKeyboardButton("🗑 Удалить участника", callback_data="admin:delete_user")],
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
    elif action == "result_stage" or action == "set_teams_stage":
        is_result = action == "result_stage"
        context.user_data["admin_mode"] = "result" if is_result else "setteams"
        title = "⚽ Выбери стадию для ввода результата:" if is_result else "🏆 Выбери стадию для заполнения команд:"
        days = sb_get("game_days", {"select": "*", "order": "day_number"})
        stages_present = set(DAY_STAGE.get(d["day_number"], "group1") for d in days)
        # Для заполнения команд — только плей-офф
        allowed_stages = STAGES_ORDER if is_result else ["r32", "r16", "qf", "sf", "3rd", "final"]
        buttons = []
        for stage in allowed_stages:
            if stage not in stages_present:
                continue
            emoji = STAGE_EMOJI.get(stage, "📁")
            buttons.append([InlineKeyboardButton(f"{emoji} {STAGE_LABELS[stage]}", callback_data=f"admin_stage:{stage}")])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")])
        await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(buttons))
    elif action == "part1_results":
        # Начинаем выбор через кнопки
        context.user_data["admin_part1"] = {}
        context.user_data["admin_part1_step"] = "1st"
        await query.edit_message_text(
            "🥇 Выбери команду — 1 место (чемпион):",
            reply_markup=teams_keyboard(prefix="ap1")
        )
        return ADMIN_PART1_1ST
    elif action == "list_users":
        users = sb_get("participants", {"select": "*", "order": "created_at"})
        if not users:
            await query.edit_message_text("Участников пока нет.")
            return
        text = "📋 Участники:\n\n"
        for u in users:
            method = "💳" if u["payment_method"] == "stripe" else "🤝"
            tg = f"@{u['telegram_username']}" if u.get("telegram_username") else "нет username"
            fav = u.get("favorite_team", "—")
            text += f"{method} {u['name']} ({tg}) {fav}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")]]))
    elif action == "part1_reset":
        preds = sb_get("part1_predictions", {"select": "id,participant_id"})
        for pred in preds:
            sb_patch("part1_predictions", {"id": f"eq.{pred['id']}"}, {
                "pts_1st": 0, "pts_2nd": 0, "pts_3rd": 0,
                "pts_4th": 0, "pts_scorer": 0, "points_calculated": False,
            })
            lb = sb_get("leaderboard", {"participant_id": f"eq.{pred['participant_id']}", "select": "part2_points"})
            part2 = lb[0]["part2_points"] if lb else 0
            sb_patch("leaderboard", {"participant_id": f"eq.{pred['participant_id']}"}, {
                "part1_points": 0, "total_points": part2,
            })
        await query.edit_message_text(
            f"✅ Итоги Топ-4 обнулены для {len(preds)} участников.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")]])
        )

    elif action == "delete_user":
        users = sb_get("participants", {"select": "id,name,telegram_username", "order": "name"})
        if not users:
            await query.edit_message_text("Участников нет.")
            return
        buttons = []
        for u in users:
            tg = f"@{u['telegram_username']}" if u.get("telegram_username") else "нет username"
            buttons.append([InlineKeyboardButton(f"🗑 {u['name']} ({tg})", callback_data=f"admin_delete:{u['id']}")])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")])
        await query.edit_message_text("Выбери участника для удаления:", reply_markup=InlineKeyboardMarkup(buttons))

async def admin_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    user_id = query.data.split(":")[1]
    user = sb_get("participants", {"id": f"eq.{user_id}", "select": "name"})[0]
    sb_delete("participants", {"id": f"eq.{user_id}"})
    await query.edit_message_text(
        f"✅ Участник {user['name']} удалён.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")]])
    )

# Выбор команды для итогов Топ-4 в админке
async def admin_part1_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ap1_page:"):
        page = int(query.data.split(":")[1])
        step = context.user_data.get("admin_part1_step", "1st")
        steps_text = {"1st": "🥇 1 место (чемпион)", "2nd": "🥈 2 место", "3rd": "🥉 3 место", "4th": "4️⃣ 4 место"}
        await query.edit_message_text(f"Выбери команду — {steps_text.get(step, '')}:", reply_markup=teams_keyboard(prefix="ap1", page=page))
        return ADMIN_PART1_1ST
    team = query.data.split(":", 1)[1]
    step = context.user_data.get("admin_part1_step", "1st")
    context.user_data["admin_part1"][step] = team
    next_steps = {
        "1st": ("2nd", "🥈 Выбери команду — 2 место:"),
        "2nd": ("3rd", "🥉 Выбери команду — 3 место:"),
        "3rd": ("4th", "4️⃣ Выбери команду — 4 место:"),
    }
    if step == "4th":
        await query.edit_message_text("⚽ Введи имя лучшего бомбардира (или несколько через запятую):")
        return ADMIN_PART1_SCORER
    next_step, next_text = next_steps[step]
    context.user_data["admin_part1_step"] = next_step
    await query.edit_message_text(next_text, reply_markup=teams_keyboard(prefix="ap1"))
    return ADMIN_PART1_1ST

async def admin_part1_scorer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scorer = update.message.text.strip()
    p = context.user_data["admin_part1"]
    t1, t2, t3, t4 = p["1st"], p["2nd"], p["3rd"], p["4th"]
    scorers = [s.strip() for s in scorer.split(",")]
    preds = sb_get("part1_predictions", {"select": "*"})
    for pred in preds:
        pts_1st = 10 if fuzzy_match(pred["team_1st"] or "", [t1]) else 0
        pts_2nd = 8 if fuzzy_match(pred["team_2nd"] or "", [t2]) else 0
        pts_3rd = 6 if fuzzy_match(pred["team_3rd"] or "", [t3]) else 0
        pts_4th = 4 if fuzzy_match(pred["team_4th"] or "", [t4]) else 0
        pts_scorer = 8 if fuzzy_match(pred["top_scorer"] or "", scorers) else 0
        total_part1 = pts_1st + pts_2nd + pts_3rd + pts_4th + pts_scorer
        sb_patch("part1_predictions", {"id": f"eq.{pred['id']}"}, {
            "pts_1st": pts_1st, "pts_2nd": pts_2nd, "pts_3rd": pts_3rd,
            "pts_4th": pts_4th, "pts_scorer": pts_scorer, "points_calculated": True,
        })
        lb = sb_get("leaderboard", {"participant_id": f"eq.{pred['participant_id']}", "select": "part2_points"})
        part2 = lb[0]["part2_points"] if lb else 0
        sb_patch("leaderboard", {"participant_id": f"eq.{pred['participant_id']}"}, {
            "part1_points": total_part1, "total_points": total_part1 + part2,
        })
    await update.message.reply_text(
        f"✅ Итоги Топ-4 сохранены!\n\n🥇 {t1}\n🥈 {t2}\n🥉 {t3}\n4️⃣ {t4}\n⚽ {', '.join(scorers)}\n\nОчки начислены {len(preds)} участникам.",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

async def admin_stage_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stage = query.data.split(":")[1]
    context.user_data["admin_stage"] = stage
    mode = context.user_data.get("admin_mode", "result")
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    buttons = []
    for day in days:
        if DAY_STAGE.get(day["day_number"]) != stage:
            continue
        date_str = DAY_DATES.get(day["day_number"], "")
        matches = sb_get("matches", {"game_day_id": f"eq.{day['id']}", "select": "id"})
        label = f"📅 День {day['day_number']} — {date_str} ({len(matches)} матчей)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_day:{day['id']}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data=f"admin:{'result_stage' if mode == 'result' else 'set_teams_stage'}")])
    title = "⚽ Выбери день:" if mode == "result" else "🏆 Выбери день:"
    await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(buttons))

async def admin_day_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_day_id = query.data.split(":")[1]
    context.user_data["admin_day_id"] = game_day_id
    mode = context.user_data.get("admin_mode", "result")
    matches = sb_get("matches", {"game_day_id": f"eq.{game_day_id}", "select": "*", "order": "kickoff_at"})
    buttons = []
    for m in matches:
        time_str = format_time_cet(m["kickoff_at"])
        if mode == "result":
            finished = "✅ " if m["is_finished"] else ""
            score = f" ({m['home_score']}:{m['away_score']})" if m["is_finished"] else ""
            label = f"{finished}{m['home_team']} — {m['away_team']} {time_str}{score}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"admin_match_result:{m['id']}")])
        else:
            label = f"{m['home_team']} — {m['away_team']} {time_str}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"admin_match_teams:{m['id']}")])
    stage = context.user_data.get("admin_stage", "group1")
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data=f"admin_stage:{stage}")])
    title = "⚽ Выбери матч:" if mode == "result" else "🏆 Выбери матч:"
    await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(buttons))

async def admin_match_result_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    context.user_data["admin_result_match"] = match
    context.user_data[f"admin_home_{match_id}"] = match.get("home_score")
    context.user_data[f"admin_away_{match_id}"] = match.get("away_score")
    h = num_emoji(match["home_score"]) if match.get("home_score") is not None else "—"
    a = num_emoji(match["away_score"]) if match.get("away_score") is not None else "—"
    time_str = format_time_cet(match["kickoff_at"])
    text = (f"⚽ {match['home_team']} vs {match['away_team']}\n🕐 {time_str} (UTC+2)\n\n"
            f"{match['home_team']}:\n{match['away_team']}:\n\nСчёт: {h} : {a}")
    await query.edit_message_text(text, reply_markup=score_keyboard(match_id, match.get("home_score"), match.get("away_score"), admin_mode=True))

async def handle_admin_score_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"admin_home_{match_id}"] = int(digit)
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    away = context.user_data.get(f"admin_away_{match_id}")
    h = num_emoji(int(digit))
    a = num_emoji(away) if away is not None else "—"
    time_str = format_time_cet(match["kickoff_at"])
    text = (f"⚽ {match['home_team']} vs {match['away_team']}\n🕐 {time_str} (UTC+2)\n\n"
            f"{match['home_team']}:\n{match['away_team']}:\n\nСчёт: {h} : {a}")
    await query.edit_message_text(text, reply_markup=score_keyboard(match_id, int(digit), away, admin_mode=True))

async def handle_admin_score_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"admin_away_{match_id}"] = int(digit)
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    home = context.user_data.get(f"admin_home_{match_id}")
    h = num_emoji(home) if home is not None else "—"
    a = num_emoji(int(digit))
    time_str = format_time_cet(match["kickoff_at"])
    text = (f"⚽ {match['home_team']} vs {match['away_team']}\n🕐 {time_str} (UTC+2)\n\n"
            f"{match['home_team']}:\n{match['away_team']}:\n\nСчёт: {h} : {a}")
    await query.edit_message_text(text, reply_markup=score_keyboard(match_id, home, int(digit), admin_mode=True))

async def handle_admin_save_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    home = context.user_data.get(f"admin_home_{match_id}")
    away = context.user_data.get(f"admin_away_{match_id}")
    if home is None or away is None:
        await query.answer("Выбери счёт!", show_alert=True)
        return
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    sb_patch("matches", {"id": f"eq.{match_id}"}, {
        "home_score": home, "away_score": away, "is_finished": True, "manual_result": True,
    })
    sb_rpc("calculate_match_points", {"p_match_id": match_id})
    day_id = context.user_data.get("admin_day_id", match["game_day_id"])
    matches = sb_get("matches", {"game_day_id": f"eq.{day_id}", "select": "*", "order": "kickoff_at"})
    buttons = []
    for m in matches:
        time_str = format_time_cet(m["kickoff_at"])
        finished = "✅ " if m["is_finished"] else ""
        score = f" ({m['home_score']}:{m['away_score']})" if m["is_finished"] else ""
        label = f"{finished}{m['home_team']} — {m['away_team']} {time_str}{score}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_match_result:{m['id']}")])
    stage = context.user_data.get("admin_stage", "group1")
    buttons.append([InlineKeyboardButton("◀️ К стадиям", callback_data=f"admin_stage:{stage}")])
    day_id = context.user_data.get("admin_day_id", match["game_day_id"])
    stage = context.user_data.get("admin_stage", "group1")
    buttons_with_back = buttons + [[InlineKeyboardButton("◀️ К этапу", callback_data=f"admin_stage:{stage}")]]
    await query.edit_message_text(
        f"✅ {match['home_team']} {home}:{away} {match['away_team']}\nОчки пересчитаны!\n\nВыбери следующий матч:",
        reply_markup=InlineKeyboardMarkup(buttons_with_back)
    )

async def admin_match_teams_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    context.user_data["set_teams_match"] = match
    await query.edit_message_text(
        f"Матч #{match['match_number']}\nСейчас: {match['home_team']} — {match['away_team']}\n\nВыбери первую команду:",
        reply_markup=teams_keyboard(prefix="st")
    )
    return SETTEAMS_HOME

async def handle_setteams_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("st_page:"):
        page = int(query.data.split(":")[1])
        await query.edit_message_text("Выбери первую команду:", reply_markup=teams_keyboard(prefix="st", page=page))
        return SETTEAMS_HOME
    team = query.data.split(":", 1)[1]
    context.user_data["set_teams_home"] = team
    await query.edit_message_text(f"Первая: {team}\n\nВыбери вторую команду:", reply_markup=teams_keyboard(prefix="st2"))
    return SETTEAMS_AWAY

async def handle_setteams_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("st2_page:"):
        page = int(query.data.split(":")[1])
        home = context.user_data.get("set_teams_home", "")
        await query.edit_message_text(f"Первая: {home}\n\nВыбери вторую команду:", reply_markup=teams_keyboard(prefix="st2", page=page))
        return SETTEAMS_AWAY
    team = query.data.split(":", 1)[1]
    home = context.user_data["set_teams_home"]
    match = context.user_data["set_teams_match"]
    sb_patch("matches", {"id": f"eq.{match['id']}"}, {"home_team": home, "away_team": team})
    day_id = match["game_day_id"]
    matches = sb_get("matches", {"game_day_id": f"eq.{day_id}", "select": "*", "order": "kickoff_at"})
    buttons = []
    for m in matches:
        time_str = format_time_cet(m["kickoff_at"])
        label = f"{m['home_team']} — {m['away_team']} {time_str}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_match_teams:{m['id']}")])
    stage = context.user_data.get("admin_stage", "r32")
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data=f"admin_stage:{stage}")])
    await query.edit_message_text(
        f"✅ #{match['match_number']}: {home} — {team}\n\nВыбери следующий матч:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ConversationHandler.END

async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_user_name"] = update.message.text.strip()
    await update.message.reply_text("Telegram username (без @) или 'нет':")
    return ADMIN_ADD_USERNAME

async def admin_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["new_user_username"] = None if val.lower() == "нет" else val
    await update.message.reply_text(
        "Введи Telegram ID участника (число)\n\nПопроси его написать @userinfobot в Telegram — бот ответит его ID:"
    )
    return ADMIN_ADD_EMAIL

async def admin_add_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    telegram_id = None if val.lower() == "нет" else val
    name = context.user_data["new_user_name"]
    username = context.user_data.get("new_user_username")
    sb_post("participants", {
        "name": name, "telegram_username": username,
        "telegram_id": telegram_id, "email": None,
        "payment_status": "paid", "payment_method": "manual",
        "paid_at": datetime.now(timezone.utc).isoformat(),
    })
    await update.message.reply_text(
        f"✅ Участник добавлен!\n{name} (@{username or '—'})\nTelegram ID: {telegram_id or '—'}\n\nПопроси его написать боту /start",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def post_init(app):
    asyncio.create_task(fetch_and_update_results(app))

# ============================================
# ТЕСТ-ТУРНИР
# ============================================

TEST_TEAMS_EPL = [
    "Liverpool", "Chelsea", "Brighton", "Wolves",
    "Fulham", "Bournemouth", "Sunderland", "Man United",
    "Man City", "Brentford",
]

TEST_TEAMS_BUN = [
    "Hoffenheim", "Werder Bremen", "Augsburg", "M'gladbach",
    "Stuttgart", "Leverkusen", "RB Leipzig", "St. Pauli",
    "Wolfsburg", "Bayern Munich",
]

TEST_TOURNAMENTS = {
    "EPL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Английская Премьер-лига",
    "BUN": "🇩🇪 Бундеслига",
}

def get_test_menu_kb(user_id):
    buttons = [
        [InlineKeyboardButton("🏆 Топ-4 дня", callback_data="test:part1")],
        [InlineKeyboardButton("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Премьер-лига", callback_data="test:matches:EPL")],
        [InlineKeyboardButton("🇩🇪 Бундеслига", callback_data="test:matches:BUN")],
        [InlineKeyboardButton("📊 Таблица лидеров", callback_data="test:leaderboard:0")],
        [InlineKeyboardButton("📋 Мои прогнозы", callback_data="test:my_preds")],
    ]
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton("🔧 Ввести результат", callback_data="test:admin_result")])
        buttons.append([InlineKeyboardButton("🥇 Итоги Топ-4", callback_data="test:admin_part1")])
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    return InlineKeyboardMarkup(buttons)

def test_teams_keyboard(teams, prefix="ttest", page=0):
    per_page = 10
    start = page * per_page
    chunk = teams[start:start + per_page]
    buttons = []
    row = []
    for team in chunk:
        row.append(InlineKeyboardButton(team, callback_data=f"{prefix}:{team}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Другие", callback_data=f"{prefix}_page:{page-1}"))
    if start + per_page < len(teams):
        nav.append(InlineKeyboardButton("Другие ▶️", callback_data=f"{prefix}_page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)

def test_score_keyboard(match_id, home_score=None, away_score=None, is_double=False):
    digits = [str(i) for i in range(8)]
    home_row = [InlineKeyboardButton("✅" if str(home_score) == d else d, callback_data=f"tsh:{match_id}:{d}") for d in digits]
    away_row = [InlineKeyboardButton("✅" if str(away_score) == d else d, callback_data=f"tsa:{match_id}:{d}") for d in digits]
    buttons = [home_row, away_row]
    if home_score is not None and away_score is not None:
        double_label = "🔥 X2 — ВКЛ (нажми чтобы выкл)" if is_double else "🔥 Сделать этот матч X2"
        buttons.append([InlineKeyboardButton(double_label, callback_data=f"tdouble:{match_id}")])
        buttons.append([InlineKeyboardButton(f"✅ Сохранить {home_score}:{away_score}", callback_data=f"tsave:{match_id}")])
    return InlineKeyboardMarkup(buttons)

def test_admin_score_keyboard(match_id, home_score=None, away_score=None):
    digits = [str(i) for i in range(8)]
    home_row = [InlineKeyboardButton("✅" if str(home_score) == d else d, callback_data=f"tash:{match_id}:{d}") for d in digits]
    away_row = [InlineKeyboardButton("✅" if str(away_score) == d else d, callback_data=f"tasa:{match_id}:{d}") for d in digits]
    buttons = [home_row, away_row]
    if home_score is not None and away_score is not None:
        buttons.append([InlineKeyboardButton(f"✅ Сохранить результат {home_score}:{away_score}", callback_data=f"tasave:{match_id}")])
    return InlineKeyboardMarkup(buttons)

async def test_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🧪 Тест-турнир 9 мая\n\n"
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Премьер-лига (13:30 UTC+2):\n"
        "Liverpool-Chelsea, Brighton-Wolves,\nFulham-Bournemouth, Sunderland-Man Utd,\nMan City-Brentford\n\n"
        "🇩🇪 Бундеслига (13:30 и 16:30 UTC+2):\n"
        "Hoffenheim-Werder, Augsburg-M'gladbach,\nStuttgart-Leverkusen, Leipzig-St.Pauli,\nWolfsburg-Bayern (16:30)",
        reply_markup=get_test_menu_kb(query.from_user.id)
    )

async def tmenu_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🧪 Тест-турнир 9 мая", reply_markup=get_test_menu_kb(query.from_user.id))

async def test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    if action == "part1":
        await test_show_part1(query, context)
    elif action == "matches":
        tournament = parts[2] if len(parts) > 2 else "EPL"
        await test_show_matches(query, context, tournament)
    elif action == "leaderboard":
        page = int(parts[2]) if len(parts) > 2 else 0
        await test_show_leaderboard(query, context, page)
    elif action == "my_preds":
        await test_show_my_preds(query, context)
    elif action == "admin_result":
        await test_show_admin_matches(query, context)
    elif action == "admin_part1":
        context.user_data["tadmin_part1"] = {}
        context.user_data["tadmin_part1_step"] = "1st"
        all_teams = TEST_TEAMS_EPL + TEST_TEAMS_BUN
        await query.edit_message_text(
            "🥇 Выбери команду — 1 место:",
            reply_markup=test_teams_keyboard(all_teams, prefix="tap1")
        )

# ---- ТОП-4 ----

async def test_show_part1(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    pred = sb_get("test_part1_predictions", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    now = datetime.now(timezone.utc)
    deadline = datetime(2026, 5, 9, 11, 15, tzinfo=timezone.utc)  # 13:15 UTC+2
    locked = now >= deadline
    if pred:
        p = pred[0]
        text = "🏆 Топ-4 дня — твой прогноз:\n\n"
        if p.get("points_calculated"):
            text += f"🥇 {p['team_1st'] or '—'} {'✅' if p.get('pts_1st') else '❌'} +{format_points(p.get('pts_1st',0))}\n"
            text += f"🥈 {p['team_2nd'] or '—'} {'✅' if p.get('pts_2nd') else '❌'} +{format_points(p.get('pts_2nd',0))}\n"
            text += f"🥉 {p['team_3rd'] or '—'} {'✅' if p.get('pts_3rd') else '❌'} +{format_points(p.get('pts_3rd',0))}\n"
            text += f"4️⃣ {p['team_4th'] or '—'} {'✅' if p.get('pts_4th') else '❌'} +{format_points(p.get('pts_4th',0))}\n"
            text += f"⚽ {p['top_scorer'] or '—'} {'✅' if p.get('pts_scorer') else '❌'} +{format_points(p.get('pts_scorer',0))}\n"
            total = sum([p.get(f'pts_{k}',0) for k in ['1st','2nd','3rd','4th','scorer']])
            text += f"\n💰 Итого: {format_points(total)}"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))
        else:
            text += f"🥇 {p['team_1st'] or '—'}\n🥈 {p['team_2nd'] or '—'}\n🥉 {p['team_3rd'] or '—'}\n4️⃣ {p['team_4th'] or '—'}\n⚽ {p['top_scorer'] or '—'}\n"
            if not locked:
                text += "\nМожешь изменить до 13:15 (UTC+2)"
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Изменить прогноз", callback_data="tpart1:edit")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")],
                ]))
            else:
                await query.edit_message_text(text + "\n🔒 Заблокирован", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))
    else:
        if locked:
            await query.edit_message_text("🔒 Прогноз заблокирован.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))
        else:
            all_teams = TEST_TEAMS_EPL + TEST_TEAMS_BUN
            await query.edit_message_text(
                "🏆 Угадай топ-4 команды дня!\n\n"
                "🥇 1 место — 10 очков\n🥈 2 место — 8 очков\n"
                "🥉 3 место — 6 очков\n4️⃣ 4 место — 4 очка\n⚽ Лучший бомбардир — 8 очков\n\n"
                "Дедлайн: 13:15 (UTC+2)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Сделать прогноз", callback_data="tpart1:edit")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")],
                ])
            )

async def tpart1_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["tpart1"] = {}
    context.user_data["tpart1_step"] = "1st"
    all_teams = TEST_TEAMS_EPL + TEST_TEAMS_BUN
    await query.edit_message_text("🥇 Кто займет 1 место?", reply_markup=test_teams_keyboard(all_teams, prefix="ttest"))

async def ttest_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    team = query.data.split(":", 1)[1]
    all_teams = TEST_TEAMS_EPL + TEST_TEAMS_BUN

    # Режим админа
    if context.user_data.get("tadmin_part1_step"):
        step = context.user_data["tadmin_part1_step"]
        context.user_data["tadmin_part1"][step] = team
        next_steps = {
            "1st": ("2nd", "🥈 2 место:"),
            "2nd": ("3rd", "🥉 3 место:"),
            "3rd": ("4th", "4️⃣ 4 место:"),
        }
        if step == "4th":
            await query.edit_message_text("⚽ Лучший бомбардир (напиши имя в чат):")
            context.user_data["tadmin_waiting_scorer"] = True
            return
        next_step, next_text = next_steps[step]
        context.user_data["tadmin_part1_step"] = next_step
        await query.edit_message_text(next_text, reply_markup=test_teams_keyboard(all_teams, prefix="ttest"))
        return

    # Режим пользователя
    step = context.user_data.get("tpart1_step", "1st")
    if "tpart1" not in context.user_data:
        context.user_data["tpart1"] = {}
    context.user_data["tpart1"][step] = team
    next_steps = {
        "1st": ("2nd", "🥈 Кто займет 2 место?"),
        "2nd": ("3rd", "🥉 Кто займет 3 место?"),
        "3rd": ("4th", "4️⃣ Кто займет 4 место?"),
    }
    if step == "4th":
        await query.edit_message_text("⚽ Лучший бомбардир дня (напиши имя в чат):")
        context.user_data["tpart1_waiting_scorer"] = True
        return
    next_step, next_text = next_steps[step]
    context.user_data["tpart1_step"] = next_step
    await query.edit_message_text(next_text, reply_markup=test_teams_keyboard(all_teams, prefix="ttest"))

async def tap1_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор команды для админского ввода Топ-4"""
    query = update.callback_query
    await query.answer()
    team = query.data.split(":", 1)[1]
    all_teams = TEST_TEAMS_EPL + TEST_TEAMS_BUN
    step = context.user_data.get("tadmin_part1_step", "1st")
    context.user_data["tadmin_part1"][step] = team
    next_steps = {
        "1st": ("2nd", "🥈 2 место:"),
        "2nd": ("3rd", "🥉 3 место:"),
        "3rd": ("4th", "4️⃣ 4 место:"),
    }
    if step == "4th":
        await query.edit_message_text("⚽ Лучший бомбардир (напиши имя в чат):")
        context.user_data["tadmin_waiting_scorer"] = True
        return
    next_step, next_text = next_steps[step]
    context.user_data["tadmin_part1_step"] = next_step
    await query.edit_message_text(next_text, reply_markup=test_teams_keyboard(all_teams, prefix="tap1"))

async def tpart1_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Бомбардир от пользователя
    if context.user_data.get("tpart1_waiting_scorer"):
        context.user_data["tpart1_waiting_scorer"] = False
        scorer = update.message.text.strip()
        user = update.effective_user
        participant = get_participant(str(user.id))
        p = context.user_data.get("tpart1", {})
        if not all(k in p for k in ["1st", "2nd", "3rd", "4th"]):
            await update.message.reply_text("Что-то пошло не так. Начни заново.")
            return
        data = {
            "participant_id": participant["id"],
            "team_1st": p["1st"], "team_2nd": p["2nd"],
            "team_3rd": p["3rd"], "team_4th": p["4th"],
            "top_scorer": scorer,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = sb_get("test_part1_predictions", {"participant_id": f"eq.{participant['id']}", "select": "id"})
        if existing:
            sb_patch("test_part1_predictions", {"participant_id": f"eq.{participant['id']}"}, data)
        else:
            sb_post("test_part1_predictions", data)
        await update.message.reply_text(
            f"✅ Прогноз сохранён!\n\n🥇 {p['1st']}\n🥈 {p['2nd']}\n🥉 {p['3rd']}\n4️⃣ {p['4th']}\n⚽ {scorer}",
            reply_markup=get_test_menu_kb(user.id)
        )
        return

    # Бомбардир от админа
    if context.user_data.get("tadmin_waiting_scorer"):
        context.user_data["tadmin_waiting_scorer"] = False
        scorer = update.message.text.strip()
        p = context.user_data.get("tadmin_part1", {})
        if not all(k in p for k in ["1st", "2nd", "3rd", "4th"]):
            await update.message.reply_text("Что-то пошло не так.")
            return
        t1, t2, t3, t4 = p["1st"], p["2nd"], p["3rd"], p["4th"]
        scorers = [s.strip() for s in scorer.split(",")]
        preds = sb_get("test_part1_predictions", {"select": "*"})
        for pred in preds:
            pts_1st = 10 if fuzzy_match(pred["team_1st"] or "", [t1]) else 0
            pts_2nd = 8 if fuzzy_match(pred["team_2nd"] or "", [t2]) else 0
            pts_3rd = 6 if fuzzy_match(pred["team_3rd"] or "", [t3]) else 0
            pts_4th = 4 if fuzzy_match(pred["team_4th"] or "", [t4]) else 0
            pts_scorer = 8 if fuzzy_match(pred["top_scorer"] or "", scorers) else 0
            total_part1 = pts_1st + pts_2nd + pts_3rd + pts_4th + pts_scorer
            sb_patch("test_part1_predictions", {"id": f"eq.{pred['id']}"}, {
                "pts_1st": pts_1st, "pts_2nd": pts_2nd, "pts_3rd": pts_3rd,
                "pts_4th": pts_4th, "pts_scorer": pts_scorer, "points_calculated": True,
            })
            lb = sb_get("test_leaderboard", {"participant_id": f"eq.{pred['participant_id']}", "select": "part2_points"})
            part2 = lb[0]["part2_points"] if lb else 0
            sb_patch("test_leaderboard", {"participant_id": f"eq.{pred['participant_id']}"}, {
                "part1_points": total_part1, "total_points": total_part1 + part2,
            })
        await update.message.reply_text(
            f"✅ Итоги сохранены!\n🥇 {t1}\n🥈 {t2}\n🥉 {t3}\n4️⃣ {t4}\n⚽ {scorer}",
            reply_markup=get_test_menu_kb(update.effective_user.id)
        )

# ---- МАТЧИ ----

async def test_show_matches(query, context, tournament="EPL"):
    user = query.from_user
    participant = get_participant(str(user.id))
    now = datetime.now(timezone.utc)
    day = sb_get("test_game_days", {"tournament": f"eq.{tournament}", "select": "*"})
    if not day:
        await query.edit_message_text("Матчи не найдены.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))
        return
    day = day[0]
    deadline = datetime.fromisoformat(day["deadline"].replace("Z", "+00:00"))
    locked = now >= deadline
    matches = sb_get("test_matches", {"game_day_id": f"eq.{day['id']}", "select": "*", "order": "match_number"})
    match_ids = [m["id"] for m in matches]
    preds_res = sb_get("test_predictions", {
        "participant_id": f"eq.{participant['id']}",
        "match_id": f"in.({','.join(match_ids)})",
        "select": "*"
    }) if match_ids else []
    preds = {p["match_id"]: p for p in preds_res}
    finished_auto = is_day_finished(matches)
    trn_label = TEST_TOURNAMENTS.get(tournament, tournament)
    text = f"{trn_label}\n📅 9 мая 2026\n"
    if finished_auto:
        text += "✅ День завершён\n\n"
        day_total = 0
        for m in matches:
            pred = preds.get(m["id"])
            real = f"{m['home_score']}:{m['away_score']}" if m["is_finished"] else "—:—"
            if pred:
                pred_score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
                pts = pred["points_earned"]
                day_total += pts
                if pred["is_double"] and pts > 0:
                    pts_str = f"+{pts//2} 🔥×2 = {format_points(pts)}"
                elif pred["is_double"]:
                    pts_str = "+0 🔥×2 = 0"
                else:
                    pts_str = f"+{format_points(pts)}"
                icon = "✅" if pts > 0 else "❌"
                text += f"{m['home_team']} {real} {m['away_team']}\nПрогноз: {pred_score} {icon} {pts_str}\n\n"
            else:
                text += f"{m['home_team']} {real} {m['away_team']}\nПрогноза не было\n\n"
        text += f"⚡️ Итого: {format_points(day_total)}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))
        return
    kickoff_str = "13:30" if tournament == "EPL" else "13:30 / 16:30"
    if locked:
        text += "🔒 Прогнозы закрыты\n\n"
    else:
        text += f"Начало в {kickoff_str} (UTC+2)\n📝 Открыт для прогнозов\n\n"
    buttons = []
    for m in matches:
        pred = preds.get(m["id"])
        time_str = format_time_cet(m["kickoff_at"])
        if pred:
            score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
            double_mark = " 🔥×2" if pred["is_double"] else ""
            label = f"📝 {m['home_team']} {score} {m['away_team']}{double_mark}"
        else:
            label = f"{m['home_team']} — : — {m['away_team']} {time_str}"
        if not locked and not m["is_finished"]:
            buttons.append([InlineKeyboardButton(label, callback_data=f"tpredict:{m['id']}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def test_start_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    user = query.from_user
    participant = get_participant(str(user.id))
    existing = sb_get("test_predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match_id}", "select": "*"})
    if existing:
        p = existing[0]
        context.user_data[f"th_{match_id}"] = p["home_score_pred"]
        context.user_data[f"ta_{match_id}"] = p["away_score_pred"]
        context.user_data[f"td_{match_id}"] = p["is_double"]
    await test_show_pred_screen(query, context, match_id)

async def test_show_pred_screen(query, context, match_id):
    match = sb_get("test_matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    home_score = context.user_data.get(f"th_{match_id}")
    away_score = context.user_data.get(f"ta_{match_id}")
    is_double = context.user_data.get(f"td_{match_id}", False)
    h = num_emoji(home_score) if home_score is not None else "—"
    a = num_emoji(away_score) if away_score is not None else "—"
    double_text = " 🔥×2" if is_double else ""
    time_str = format_time_cet(match["kickoff_at"])
    trn_label = TEST_TOURNAMENTS.get(match["tournament"], "")
    text = (
        f"{trn_label}\n⚽ {match['home_team']} vs {match['away_team']}\n"
        f"🕐 {time_str} (UTC+2)\n\n"
        f"{match['home_team']}:\n{match['away_team']}:\n\n"
        f"Счёт: {h} : {a}{double_text}"
    )
    await query.edit_message_text(text, reply_markup=test_score_keyboard(match_id, home_score, away_score, is_double))

async def test_score_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"th_{match_id}"] = int(digit)
    await test_show_pred_screen(query, context, match_id)

async def test_score_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"ta_{match_id}"] = int(digit)
    await test_show_pred_screen(query, context, match_id)

async def test_double_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    context.user_data[f"td_{match_id}"] = not context.user_data.get(f"td_{match_id}", False)
    await test_show_pred_screen(query, context, match_id)

async def test_save_pred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    home_score = context.user_data.get(f"th_{match_id}")
    away_score = context.user_data.get(f"ta_{match_id}")
    is_double = context.user_data.get(f"td_{match_id}", False)
    if home_score is None or away_score is None:
        await query.answer("Выбери счёт!", show_alert=True)
        return
    user = query.from_user
    participant = get_participant(str(user.id))
    match = sb_get("test_matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    if is_double:
        day_matches = sb_get("test_matches", {"game_day_id": f"eq.{match['game_day_id']}", "select": "id"})
        day_ids = ",".join(m["id"] for m in day_matches)
        sb_patch("test_predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"in.({day_ids})"}, {"is_double": False})
    data = {
        "participant_id": participant["id"], "match_id": match_id,
        "home_score_pred": home_score, "away_score_pred": away_score,
        "is_double": is_double, "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_calculated": False, "points_earned": 0,
    }
    existing = sb_get("test_predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match_id}", "select": "id"})
    if existing:
        sb_patch("test_predictions", {"participant_id": f"eq.{participant['id']}", "match_id": f"eq.{match_id}"}, data)
    else:
        sb_post("test_predictions", data)
    double_text = " 🔥×2" if is_double else ""
    await query.edit_message_text(
        f"✅ Прогноз сохранён!\n\n⚽ {match['home_team']} {home_score}:{away_score} {match['away_team']}{double_text}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад к матчам", callback_data=f"test:matches:{match['tournament']}")]])
    )

# ---- ТАБЛИЦА И МОИ ПРОГНОЗЫ ----

async def test_show_leaderboard(query, context, page=0):
    per_page = 10
    offset = page * per_page
    lb = sb_get("test_leaderboard", {
        "select": "total_points,rank,participants(name)",
        "order": "total_points.desc",
        "limit": str(per_page),
        "offset": str(offset),
    })
    total_count = len(sb_get("test_leaderboard", {"select": "id"}))
    user = query.from_user
    participant = get_participant(str(user.id))
    my_lb = sb_get("test_leaderboard", {"participant_id": f"eq.{participant['id']}", "select": "total_points,rank"})
    my_rank = my_lb[0]["rank"] if my_lb else "—"
    my_pts = my_lb[0]["total_points"] if my_lb else 0
    if not lb:
        await query.edit_message_text("Таблица пока пуста.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))
        return
    start_num = offset + 1
    end_num = offset + len(lb)
    text = f"📊 Тест-турнир ({start_num}-{end_num} из {total_count})\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, entry in enumerate(lb, start_num):
        text += f"{medals.get(i, f'{i}.')} {entry['participants']['name']} — {format_points(entry['total_points'])}\n"
    text += f"\n👤 Твоё место: {my_rank} из {total_count} — {format_points(my_pts)}"
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"test:leaderboard:{page-1}"))
    if end_num < total_count:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"test:leaderboard:{page+1}"))
    buttons = []
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def test_show_my_preds(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    lb = sb_get("test_leaderboard", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    total = lb[0]["total_points"] if lb else 0
    part1 = lb[0]["part1_points"] if lb else 0
    part2 = lb[0]["part2_points"] if lb else 0
    text = f"📋 Мои прогнозы (тест)\n\n💰 Всего: {format_points(total)}\n"
    if part1 > 0:
        text += f"  └ За Топ-4: {format_points(part1)}\n"
    text += f"  └ За матчи: {format_points(part2)}\n\n"
    preds = sb_get("test_predictions", {"participant_id": f"eq.{participant['id']}", "select": "*"})
    for p in preds:
        match = sb_get("test_matches", {"id": f"eq.{p['match_id']}", "select": "*"})[0]
        double = " 🔥×2" if p["is_double"] else ""
        pred_score = f"{p['home_score_pred']}:{p['away_score_pred']}"
        if match["is_finished"]:
            pts = p["points_earned"]
            text += f"✅ {match['home_team']} {pred_score} {match['away_team']} → {match['home_score']}:{match['away_score']} +{format_points(pts)}{double}\n"
        else:
            time_str = format_time_cet(match["kickoff_at"])
            text += f"📝 {match['home_team']} {pred_score} {match['away_team']} {time_str}{double}\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")]]))

# ---- АДМИН РЕЗУЛЬТАТ ----

async def test_show_admin_matches(query, context):
    matches = sb_get("test_matches", {"select": "*", "order": "match_number"})
    buttons = []
    for m in matches:
        trn = "🏴󠁧󠁢󠁥󠁮󠁧󠁿" if m["tournament"] == "EPL" else "🇩🇪"
        score = f" ({m['home_score']}:{m['away_score']})" if m["is_finished"] else ""
        label = f"{trn} {m['home_team']} — {m['away_team']}{score}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"tadmin_match:{m['id']}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")])
    await query.edit_message_text("⚽ Выбери матч:", reply_markup=InlineKeyboardMarkup(buttons))

async def test_admin_match_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    match = sb_get("test_matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    context.user_data["tadmin_match_id"] = match_id
    context.user_data[f"tah_{match_id}"] = match.get("home_score")
    context.user_data[f"taa_{match_id}"] = match.get("away_score")
    h = num_emoji(match["home_score"]) if match.get("home_score") is not None else "—"
    a = num_emoji(match["away_score"]) if match.get("away_score") is not None else "—"
    text = f"⚽ {match['home_team']} vs {match['away_team']}\n\n{match['home_team']}:\n{match['away_team']}:\n\nСчёт: {h} : {a}"
    await query.edit_message_text(text, reply_markup=test_admin_score_keyboard(match_id, match.get("home_score"), match.get("away_score")))

async def test_admin_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"tah_{match_id}"] = int(digit)
    match = sb_get("test_matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    away = context.user_data.get(f"taa_{match_id}")
    h = num_emoji(int(digit))
    a = num_emoji(away) if away is not None else "—"
    text = f"⚽ {match['home_team']} vs {match['away_team']}\n\n{match['home_team']}:\n{match['away_team']}:\n\nСчёт: {h} : {a}"
    await query.edit_message_text(text, reply_markup=test_admin_score_keyboard(match_id, int(digit), away))

async def test_admin_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, match_id, digit = query.data.split(":")
    context.user_data[f"taa_{match_id}"] = int(digit)
    match = sb_get("test_matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    home = context.user_data.get(f"tah_{match_id}")
    h = num_emoji(home) if home is not None else "—"
    a = num_emoji(int(digit))
    text = f"⚽ {match['home_team']} vs {match['away_team']}\n\n{match['home_team']}:\n{match['away_team']}:\n\nСчёт: {h} : {a}"
    await query.edit_message_text(text, reply_markup=test_admin_score_keyboard(match_id, home, int(digit)))

async def test_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    home = context.user_data.get(f"tah_{match_id}")
    away = context.user_data.get(f"taa_{match_id}")
    if home is None or away is None:
        await query.answer("Выбери счёт!", show_alert=True)
        return
    match = sb_get("test_matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    sb_patch("test_matches", {"id": f"eq.{match_id}"}, {
        "home_score": home, "away_score": away, "is_finished": True, "manual_result": True
    })
    sb_rpc("calculate_test_match_points", {"p_match_id": match_id})
    matches = sb_get("test_matches", {"select": "*", "order": "match_number"})
    buttons = []
    for m in matches:
        trn = "🏴󠁧󠁢󠁥󠁮󠁧󠁿" if m["tournament"] == "EPL" else "🇩🇪"
        score = f" ({m['home_score']}:{m['away_score']})" if m["is_finished"] else ""
        label = f"{trn} {m['home_team']} — {m['away_team']}{score}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"tadmin_match:{m['id']}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tmenu:back")])
    buttons.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="tmenu:back")])
    await query.edit_message_text(
        f"✅ {match['home_team']} {home}:{away} {match['away_team']}\n\nВыбери следующий матч:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ---- АВТОПОДТЯЖКА ----

async def check_test_match_results():
    logger.info(f"DEBUG: FOOTBALL_DATA_KEY = {FOOTBALL_DATA_KEY[:5] if FOOTBALL_DATA_KEY else None}")
    now = datetime.now(timezone.utc)
    matches = sb_get("test_matches", {"select": "*", "is_finished": "eq.false"})
    for match in matches:
        if match.get("manual_result"):
            continue
        kickoff = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00"))
        if now < kickoff + timedelta(hours=2):
            continue
        await try_fetch_test_result(match)

async def try_fetch_test_result(match):
    try:
        date_str = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        competition = "PL" if match["tournament"] == "EPL" else "BL1"
        headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
        r = httpx.get(
            "https://api.football-data.org/v4/matches",
            headers=headers,
            params={"competitions": competition, "dateFrom": date_str, "dateTo": date_str}
        )
        data = r.json()
        home_name = match.get("api_home_team", match["home_team"])
        away_name = match.get("api_away_team", match["away_team"])
        matches_list = data.get("matches", [])
        logger.info(f"football-data.org вернул {len(matches_list)} матчей для {competition} {date_str}")
        for fixture in matches_list:
            if fixture.get("status") != "FINISHED":
                continue
            h = fixture["homeTeam"]["name"]
            a = fixture["awayTeam"]["name"]
            if (home_name.lower() in h.lower() or h.lower() in home_name.lower()) and \
               (away_name.lower() in a.lower() or a.lower() in away_name.lower()):
                ft = fixture.get("score", {}).get("fullTime", {})
                home_score = ft.get("home")
                away_score = ft.get("away")
                if home_score is None or away_score is None:
                    continue
                sb_patch("test_matches", {"id": f"eq.{match['id']}"}, {
                    "home_score": home_score, "away_score": away_score, "is_finished": True,
                })
                sb_rpc("calculate_test_match_points", {"p_match_id": match["id"]})
                logger.info(f"✅ Тест-результат #{match['match_number']}: {home_score}:{away_score}")
                return
        teams_in_api = [(f["homeTeam"]["name"], f["awayTeam"]["name"]) for f in matches_list]
        logger.warning(f"⚠️ Матч #{match['match_number']} ({home_name} vs {away_name}) не найден. Матчи в API: {teams_in_api[:5]}")
    except Exception as e:
        import traceback
        logger.error(f"Ошибка тест-API #{match['match_number']}: {e}\n{traceback.format_exc()}")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    part1_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(part1_callback, pattern="^part1:")],
        states={
            PART1_1ST: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|team_page:)")],
            PART1_2ND: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|team_page:)")],
            PART1_3RD: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|team_page:)")],
            PART1_4TH: [CallbackQueryHandler(part1_team_selected, pattern="^(team:|team_page:)")],
            PART1_SCORER: [MessageHandler(filters.TEXT & ~filters.COMMAND, part1_scorer)],
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

    admin_part1_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin:part1_results$")],
        states={
            ADMIN_PART1_1ST: [CallbackQueryHandler(admin_part1_team, pattern="^(ap1:|ap1_page:)")],
            ADMIN_PART1_2ND: [CallbackQueryHandler(admin_part1_team, pattern="^(ap1:|ap1_page:)")],
            ADMIN_PART1_3RD: [CallbackQueryHandler(admin_part1_team, pattern="^(ap1:|ap1_page:)")],
            ADMIN_PART1_4TH: [CallbackQueryHandler(admin_part1_team, pattern="^(ap1:|ap1_page:)")],
            ADMIN_PART1_SCORER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_part1_scorer)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    setteams_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_match_teams_selected, pattern="^admin_match_teams:")],
        states={
            SETTEAMS_HOME: [CallbackQueryHandler(handle_setteams_home, pattern="^(st:|st_page:)")],
            SETTEAMS_AWAY: [CallbackQueryHandler(handle_setteams_away, pattern="^(st2:|st2_page:)")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(part1_conv)
    app.add_handler(admin_add_conv)
    app.add_handler(admin_part1_conv)
    app.add_handler(setteams_conv)

    # Тест-турнир
    app.add_handler(CallbackQueryHandler(test_menu, pattern="^goto:test$"))
    app.add_handler(CallbackQueryHandler(tpart1_start, pattern="^tpart1:edit$"))
    app.add_handler(CallbackQueryHandler(ttest_team, pattern="^ttest:"))
    app.add_handler(CallbackQueryHandler(tap1_team, pattern="^tap1:"))
    app.add_handler(CallbackQueryHandler(test_handler, pattern="^test:"))
    app.add_handler(CallbackQueryHandler(tmenu_back, pattern="^tmenu:back$"))
    app.add_handler(CallbackQueryHandler(test_start_prediction, pattern="^tpredict:"))
    app.add_handler(CallbackQueryHandler(test_score_home, pattern="^tsh:"))
    app.add_handler(CallbackQueryHandler(test_score_away, pattern="^tsa:"))
    app.add_handler(CallbackQueryHandler(test_double_toggle, pattern="^tdouble:"))
    app.add_handler(CallbackQueryHandler(test_save_pred, pattern="^tsave:"))
    app.add_handler(CallbackQueryHandler(test_admin_match_selected, pattern="^tadmin_match:"))
    app.add_handler(CallbackQueryHandler(test_admin_home, pattern="^tash:"))
    app.add_handler(CallbackQueryHandler(test_admin_away, pattern="^tasa:"))
    app.add_handler(CallbackQueryHandler(test_admin_save, pattern="^tasave:"))

    # Основные хэндлеры
    app.add_handler(CallbackQueryHandler(fav_team_selected, pattern="^(fav:|fav_page:)"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu:"))
    app.add_handler(CallbackQueryHandler(show_stage_days, pattern="^stage:"))
    app.add_handler(CallbackQueryHandler(show_game_day, pattern="^gameday:"))
    app.add_handler(CallbackQueryHandler(start_prediction, pattern="^predict:"))
    app.add_handler(CallbackQueryHandler(handle_score_home, pattern="^sh:"))
    app.add_handler(CallbackQueryHandler(handle_score_away, pattern="^sa:"))
    app.add_handler(CallbackQueryHandler(handle_double_toggle, pattern="^double_toggle:"))
    app.add_handler(CallbackQueryHandler(handle_save_pred, pattern="^save_pred:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin:"))
    app.add_handler(CallbackQueryHandler(admin_stage_selected, pattern="^admin_stage:"))
    app.add_handler(CallbackQueryHandler(admin_day_selected, pattern="^admin_day:"))
    app.add_handler(CallbackQueryHandler(admin_match_result_selected, pattern="^admin_match_result:"))
    app.add_handler(CallbackQueryHandler(handle_admin_score_home, pattern="^ash:"))
    app.add_handler(CallbackQueryHandler(handle_admin_score_away, pattern="^asa:"))
    app.add_handler(CallbackQueryHandler(handle_admin_save_result, pattern="^asave:"))
    app.add_handler(CallbackQueryHandler(show_teams_leaderboard, pattern="^leaderboard:teams:"))
    app.add_handler(CallbackQueryHandler(show_my_predictions_stage, pattern="^mypred:"))
    app.add_handler(CallbackQueryHandler(admin_delete_user, pattern="^admin_delete:"))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back:"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, tpart1_text_handler))

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
