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
WC2026_ID = 1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

(
    PART1_1ST, PART1_2ND, PART1_3RD, PART1_4TH, PART1_SCORER,
    ADMIN_ADD_NAME, ADMIN_ADD_USERNAME, ADMIN_ADD_EMAIL,
    ADMIN_RESULT_MATCH, ADMIN_RESULT_HOME, ADMIN_RESULT_AWAY,
    ADMIN_SET_TEAMS_HOME, ADMIN_SET_TEAMS_AWAY,
    ADMIN_PART1_RESULTS,
) = range(14)

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
    1: "11 июня", 2: "12 июня", 3: "13 июня", 4: "14 июня",
    5: "15 июня", 6: "16 июня", 7: "17 июня", 8: "18 июня",
    9: "19 июня", 10: "20 июня", 11: "21 июня", 12: "22 июня",
    13: "23 июня", 14: "24 июня", 15: "25 июня", 16: "26 июня",
    17: "27 июня", 18: "29 июня", 19: "30 июня", 20: "1 июля",
    21: "2 июля", 22: "3 июля", 23: "4 июля", 24: "5 июля",
    25: "6 июля", 26: "7 июля", 27: "8 июля", 28: "9 июля",
    29: "10 июля", 30: "11 июля", 31: "12 июля", 32: "14 июля",
    33: "15 июля", 35: "18 июля", 36: "19 июля",
}

STAGE_LABELS = {
    "group1": "1 тур группового этапа",
    "group2": "2 тур группового этапа",
    "group3": "3 тур группового этапа",
    "r32": "1/16 финала",
    "r16": "1/8 финала",
    "qf": "1/4 финала",
    "sf": "Полуфинал",
    "3rd": "Матч за 3-е место",
    "final": "Финал",
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
    **{d: "qf" for d in range(28, 30)},
    **{d: "sf" for d in range(30, 32)},
    33: "3rd", 35: "final", 36: "final",
}

STAGES_ORDER = ["group1", "group2", "group3", "r32", "r16", "qf", "sf", "3rd", "final"]
DIRECT_STAGES = {"sf", "3rd", "final"}
NO_DOUBLE_STAGES = {"3rd", "final"}

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

def format_time_cet(kickoff_str):
    dt = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
    dt_cet = dt.astimezone(timezone(timedelta(hours=2)))
    return dt_cet.strftime("%d.%m %H:%M")

def is_day_finished(matches):
    if not matches:
        return False
    now = datetime.now(timezone.utc)
    last_kickoff = max(
        datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00"))
        for m in matches
    )
    return now >= last_kickoff + timedelta(hours=3)

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
        nav.append(InlineKeyboardButton("◀️ Другие команды", callback_data=f"page:{page-1}"))
    if start + per_page < len(TEAMS):
        nav.append(InlineKeyboardButton("Другие команды ▶️", callback_data=f"page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)

def score_keyboard(match_id, home_score=None, away_score=None, is_double=False, no_double=False):
    digits = [str(i) for i in range(8)]
    home_row = [InlineKeyboardButton("✅" if str(home_score) == d else d, callback_data=f"sh:{match_id}:{d}") for d in digits]
    away_row = [InlineKeyboardButton("✅" if str(away_score) == d else d, callback_data=f"sa:{match_id}:{d}") for d in digits]
    buttons = [home_row, away_row]
    if home_score is not None and away_score is not None:
        if not no_double:
            double_label = "🔥 X2 — ВКЛ (нажми чтобы выкл)" if is_double else "🔥 Сделать этот матч X2"
            buttons.append([InlineKeyboardButton(double_label, callback_data=f"double_toggle:{match_id}")])
        buttons.append([InlineKeyboardButton(f"✅ Сохранить {home_score}:{away_score}", callback_data=f"save_pred:{match_id}")])
    return InlineKeyboardMarkup(buttons)

def main_menu_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("🏆 Прогноз на ТОП-4 ЧМ 2026", callback_data="menu:part1")],
        [InlineKeyboardButton("⚽ Прогнозы на матчи", callback_data="menu:matches")],
        [InlineKeyboardButton("📊 Таблица лидеров", callback_data="menu:leaderboard:0")],
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
            "Если ты уже оплатил — напиши нам, мы исправим ошибку и подключим тебя к боту!."
        )
        return
    await update.message.reply_text(
        f"👋 Привет, {participant['name']}!\n\nДобро пожаловать на конкурс прогнозов Чемпионата Мира 2026!\n\n"
        "Мы отлично проведем ближайшие месяц! Выбери дальнейшие действия в меню.\n\n"
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
# ЧАСТЬ 1
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
            text += f"🥇 1 место: {p['team_1st'] or '—'} {'✅' if p.get('pts_1st') else '❌'} +{p.get('pts_1st', 0)}\n"
            text += f"🥈 2 место: {p['team_2nd'] or '—'} {'✅' if p.get('pts_2nd') else '❌'} +{p.get('pts_2nd', 0)}\n"
            text += f"🥉 3 место: {p['team_3rd'] or '—'} {'✅' if p.get('pts_3rd') else '❌'} +{p.get('pts_3rd', 0)}\n"
            text += f"4️⃣ 4 место: {p['team_4th'] or '—'} {'✅' if p.get('pts_4th') else '❌'} +{p.get('pts_4th', 0)}\n"
            text += f"⚽ Бомбардир: {p['top_scorer'] or '—'} {'✅' if p.get('pts_scorer') else '❌'} +{p.get('pts_scorer', 0)}\n"
            total = sum([p.get('pts_1st', 0), p.get('pts_2nd', 0), p.get('pts_3rd', 0), p.get('pts_4th', 0), p.get('pts_scorer', 0)])
            text += f"\n💰 Итого: {total} очков"
        else:
            text += f"🥇 1 место: {p['team_1st'] or '—'}\n"
            text += f"🥈 2 место: {p['team_2nd'] or '—'}\n"
            text += f"🥉 3 место: {p['team_3rd'] or '—'}\n"
            text += f"4️⃣ 4 место: {p['team_4th'] or '—'}\n"
            text += f"⚽ Бомбардир: {p['top_scorer'] or '—'}\n\n"
        if locked and not p.get("points_calculated"):
            text += "\n🔒 Прогноз заблокирован — турнир начался."
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
        elif not locked:
            text += "\nМожешь изменить прогноз до старта турнира."
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Изменить прогноз", callback_data="part1:edit")],
                [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
            ]))
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]]))
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
        await query.edit_message_text("🥇 Кто станет чемпионом мира?:", reply_markup=teams_keyboard())
        return PART1_1ST

async def part1_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page:"):
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
# ЧАСТЬ 2 — Этапы и матчи
# ============================================

async def show_stages_menu(query, context):
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    if not days:
        await query.edit_message_text(
            "⚽ Расписание матчей ещё не добавлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")]])
        )
        return
    stages_present = set()
    for day in days:
        stage = DAY_STAGE.get(day["day_number"], "group1")
        stages_present.add(stage)
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

    # Для полуфинала, матча за 3-е и финала — сразу показываем матчи
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
        matches = sb_get("matches", {"game_day_id": f"eq.{day['id']}", "select": "id,is_finished,kickoff_at"})
        total = len(matches)
        finished = sum(1 for m in matches if m["is_finished"])
        finished_auto = is_day_finished(matches)
        if finished_auto or finished == total and total > 0:
            status = "✅"
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
        f"{STAGE_EMOJI.get(stage, '📁')} {STAGE_LABELS.get(stage, '')}\n\n📝 открыт  🔒 заблокирован  ✅ сыгран",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_direct_stage_matches(query, context, stage):
    """Для полуфинала, 3-го места и финала — сразу показываем матчи"""
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
    deadline = datetime.fromisoformat(
        sb_get("game_days", {"id": f"eq.{all_matches[0]['game_day_id']}", "select": "deadline"})[0]["deadline"].replace("Z", "+00:00")
    )
    locked = now >= deadline

    text = f"{STAGE_EMOJI.get(stage)} {STAGE_LABELS.get(stage)}\n"
    if no_double:
        text += "ℹ️ X2 в этом матче недоступен\n"
    if finished_auto:
        text += "✅ День завершён\n\n"
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
        if not locked and not m["is_finished"] and m["home_team"] != "TBD":
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
                    base_pts = pts // 2
                    pts_str = f"+{base_pts} 🔥×2 = {pts}"
                elif pred["is_double"]:
                    pts_str = "+0 🔥×2 = 0"
                else:
                    pts_str = f"+{pts}"
                result_icon = "✅" if pts > 0 else "❌"
                text += f"{m['home_team']} {real} {m['away_team']}\nТвой прогноз: {pred_score} {result_icon} {pts_str}\n\n"
            else:
                text += f"{m['home_team']} {real} {m['away_team']}\nПрогноза не было\n\n"
        text += f"⚡️ Итого за день: {day_total} баллов"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"stage:{stage}")]])
        )
        return

    if locked:
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
        if not locked and not m["is_finished"] and m["home_team"] != "TBD":
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
        f"{match['home_team']}:\n\n"
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

    existing = sb_get("predictions", {
        "participant_id": f"eq.{participant['id']}",
        "match_id": f"eq.{match_id}",
        "select": "*"
    })
    if existing:
        p = existing[0]
        context.user_data[f"home_{match_id}"] = p["home_score_pred"]
        context.user_data[f"away_{match_id}"] = p["away_score_pred"]
        context.user_data[f"double_{match_id}"] = p["is_double"]

    await show_prediction_screen(
        query, context, match_id,
        context.user_data.get(f"home_{match_id}"),
        context.user_data.get(f"away_{match_id}"),
        context.user_data.get(f"double_{match_id}", False),
        no_double
    )

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

    text = f"📋 Мои прогнозы\n\n💰 Всего очков: {total}\n"
    if part1 > 0:
        text += f"  └ За Топ-4 и бомбардира: {part1}\n"
    text += f"  └ За матчи: {part2}\n"

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

    if stage_key == "playoff":
        stages = ["r32", "r16", "qf", "sf", "3rd", "final"]
    else:
        stages = [stage_key]

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
            text += f"✅ {m['home_team']} {pred_score} {m['away_team']} → {m['home_score']}:{m['away_score']} +{pts}{double}\n"
        else:
            time_str = format_time_cet(m["kickoff_at"])
            text += f"📝 {m['home_team']} {pred_score} {m['away_team']} {time_str}{double}\n"

    text += f"\n⚡️ Очков за этот раздел: {total}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu:my_predictions")]]))

# ============================================
# ТАБЛИЦА ЛИДЕРОВ
# ============================================

async def show_leaderboard(query, context, page=0):
    per_page = 10
    offset = page * per_page
    lb = sb_get("leaderboard", {
        "select": "total_points,participants(name,telegram_id)",
        "order": "total_points.desc",
        "limit": str(per_page),
        "offset": str(offset),
    })
    total_count_res = sb_get("leaderboard", {"select": "id"})
    total_count = len(total_count_res)

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
        pts = entry["total_points"]
        text += f"{medal} {name} — {pts} очков\n"

    text += f"\n👤 Твоё место: {my_rank} из {total_count} — {my_pts} очков"

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:leaderboard:{page-1}"))
    if end_num < total_count:
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"menu:leaderboard:{page+1}"))

    buttons = []
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ============================================
# АВТОМАТИЧЕСКОЕ ПОЛУЧЕНИЕ РЕЗУЛЬТАТОВ
# ============================================

async def fetch_and_update_results(app):
    """Фоновая задача — каждые 15 минут проверяет результаты матчей"""
    while True:
        try:
            await check_match_results()
        except Exception as e:
            logger.error(f"Ошибка при получении результатов: {e}")
        await asyncio.sleep(15 * 60)

async def check_match_results():
    now = datetime.now(timezone.utc)
    # Берём незавершённые матчи которые начались более 2 часов назад
    matches = sb_get("matches", {
        "select": "*",
        "is_finished": "eq.false",
        "home_team": "neq.TBD",
    })
    for match in matches:
        kickoff = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00"))
        if now < kickoff + timedelta(hours=2):
            continue
        await try_fetch_result(match)

async def try_fetch_result(match):
    """Получаем результат матча через API-Football"""
    try:
        date_str = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        r = httpx.get(
            "https://v3.football.api-sports.io/fixtures",
            headers=headers,
            params={"league": WC2026_ID, "season": 2026, "date": date_str}
        )
        data = r.json()
        fixtures = data.get("response", [])

        home_name = match["home_team"].split(" ", 1)[-1].strip()
        away_name = match["away_team"].split(" ", 1)[-1].strip()

        for fixture in fixtures:
            status = fixture["fixture"]["status"]["short"]
            if status not in ["FT", "AET", "PEN"]:
                continue
            h = fixture["teams"]["home"]["name"]
            a = fixture["teams"]["away"]["name"]
            if (home_name.lower() in h.lower() or h.lower() in home_name.lower()) and \
               (away_name.lower() in a.lower() or a.lower() in away_name.lower()):
                home_score = fixture["score"]["fulltime"]["home"]
                away_score = fixture["score"]["fulltime"]["away"]
                if home_score is None or away_score is None:
                    continue
                sb_patch("matches", {"id": f"eq.{match['id']}"}, {
                    "home_score": home_score,
                    "away_score": away_score,
                    "is_finished": True,
                })
                sb_rpc("calculate_match_points", {"p_match_id": match["id"]})
                logger.info(f"✅ Результат матча #{match['match_number']}: {home_score}:{away_score}")
                return
    except Exception as e:
        logger.error(f"Ошибка API для матча #{match['match_number']}: {e}")

# ============================================
# АДМИН
# ============================================

async def show_admin_panel(query, context):
    if not is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.edit_message_text("🔧 Админ-панель", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить участника", callback_data="admin:add_user")],
        [InlineKeyboardButton("⚽ Ввести результат матча", callback_data="admin:add_result")],
        [InlineKeyboardButton("🏆 Заполнить команды матча", callback_data="admin:set_teams_stage")],
        [InlineKeyboardButton("🥇 Ввести итоги Топ-4", callback_data="admin:part1_results")],
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

    elif action == "set_teams_stage":
        # Показываем только плей-офф стадии
        buttons = [
            [InlineKeyboardButton("🔥 1/16 финала", callback_data="setteams_stage:r32")],
            [InlineKeyboardButton("🔥 1/8 финала", callback_data="setteams_stage:r16")],
            [InlineKeyboardButton("🔥 1/4 финала", callback_data="setteams_stage:qf")],
            [InlineKeyboardButton("🔥 Полуфинал", callback_data="setteams_stage:sf")],
            [InlineKeyboardButton("🥉 Матч за 3-е место", callback_data="setteams_stage:3rd")],
            [InlineKeyboardButton("🏆 Финал", callback_data="setteams_stage:final")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")],
        ]
        await query.edit_message_text("Выбери стадию:", reply_markup=InlineKeyboardMarkup(buttons))

    elif action == "part1_results":
        await query.edit_message_text(
            "🥇 Введи итоги турнира в формате:\n\n"
            "Команда1\nКоманда2\nКоманда3\nКоманда4\nИмя бомбардира1, Имя бомбардира2\n\n"
            "Пример:\n🇪🇸 Испания\n🇫🇷 Франция\n🇩🇪 Германия\n🇵🇹 Португалия\nКилиан Мбаппе, Мбаппе"
        )
        return ADMIN_PART1_RESULTS

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

async def show_setteams_stage_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stage = query.data.split(":")[1]
    days = sb_get("game_days", {"select": "*", "order": "day_number"})
    buttons = []
    for day in days:
        if DAY_STAGE.get(day["day_number"]) != stage:
            continue
        matches = sb_get("matches", {"game_day_id": f"eq.{day['id']}", "select": "*", "order": "kickoff_at"})
        for m in matches:
            date_str = DAY_DATES.get(day["day_number"], "")
            label = f"#{m['match_number']} {m['home_team']} — {m['away_team']} · {date_str}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"setteams_match:{m['id']}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="admin:set_teams_stage")])
    await query.edit_message_text(f"Выбери матч для заполнения команд:", reply_markup=InlineKeyboardMarkup(buttons))

async def setteams_match_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split(":")[1]
    match = sb_get("matches", {"id": f"eq.{match_id}", "select": "*"})[0]
    context.user_data["set_teams_match"] = match
    await query.edit_message_text(
        f"Матч #{match['match_number']}: {match['home_team']} — {match['away_team']}\n\nВведи название первой команды:"
    )
    return ADMIN_SET_TEAMS_HOME

async def admin_set_teams_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["set_teams_home"] = update.message.text.strip()
    await update.message.reply_text("Введи название второй команды:")
    return ADMIN_SET_TEAMS_AWAY

async def admin_set_teams_away(update: Update, context: ContextTypes.DEFAULT_TYPE):
    away = update.message.text.strip()
    home = context.user_data["set_teams_home"]
    match = context.user_data["set_teams_match"]
    sb_patch("matches", {"id": f"eq.{match['id']}"}, {"home_team": home, "away_team": away})
    await update.message.reply_text(
        f"✅ Команды обновлены!\nМатч #{match['match_number']}: {home} — {away}",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

async def admin_part1_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = update.message.text.strip().split("\n")
    if len(lines) < 5:
        await update.message.reply_text("Нужно 5 строк: 4 команды и бомбардиры. Попробуй ещё раз:")
        return ADMIN_PART1_RESULTS

    team_1st = lines[0].strip()
    team_2nd = lines[1].strip()
    team_3rd = lines[2].strip()
    team_4th = lines[3].strip()
    scorers = [s.strip() for s in lines[4].split(",")]

    preds = sb_get("part1_predictions", {"select": "*"})
    for pred in preds:
        pts_1st = 10 if team_1st.lower() in (pred["team_1st"] or "").lower() or (pred["team_1st"] or "").lower() in team_1st.lower() else 0
        pts_2nd = 8 if team_2nd.lower() in (pred["team_2nd"] or "").lower() or (pred["team_2nd"] or "").lower() in team_2nd.lower() else 0
        pts_3rd = 6 if team_3rd.lower() in (pred["team_3rd"] or "").lower() or (pred["team_3rd"] or "").lower() in team_3rd.lower() else 0
        pts_4th = 4 if team_4th.lower() in (pred["team_4th"] or "").lower() or (pred["team_4th"] or "").lower() in team_4th.lower() else 0
        pts_scorer = 8 if fuzzy_match(pred["top_scorer"] or "", scorers) else 0
        total_part1 = pts_1st + pts_2nd + pts_3rd + pts_4th + pts_scorer

        sb_patch("part1_predictions", {"id": f"eq.{pred['id']}"}, {
            "pts_1st": pts_1st, "pts_2nd": pts_2nd,
            "pts_3rd": pts_3rd, "pts_4th": pts_4th,
            "pts_scorer": pts_scorer, "points_calculated": True,
        })
        sb_patch("leaderboard", {"participant_id": f"eq.{pred['participant_id']}"}, {
            "part1_points": total_part1,
        })

    # Пересчитываем total и ранги
    all_lb = sb_get("leaderboard", {"select": "*"})
    for entry in all_lb:
        sb_patch("leaderboard", {"id": f"eq.{entry['id']}"}, {
            "total_points": entry["part1_points"] + entry["part2_points"]
        })

    await update.message.reply_text(
        f"✅ Итоги Топ-4 сохранены!\n\n"
        f"🥇 {team_1st}\n🥈 {team_2nd}\n🥉 {team_3rd}\n4️⃣ {team_4th}\n"
        f"⚽ Бомбардиры: {', '.join(scorers)}\n\n"
        f"Очки начислены {len(preds)} участникам.",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END

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
        await update.message.reply_text(f"Матч #{num}: {m['home_team']} — {m['away_team']}\nВведи голы первой команды:")
        return ADMIN_RESULT_HOME
    except ValueError:
        await update.message.reply_text("Введи число:")
        return ADMIN_RESULT_MATCH

async def admin_result_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["result_home"] = int(update.message.text.strip())
        await update.message.reply_text("Введи голы второй команды:")
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

async def post_init(app):
    asyncio.create_task(fetch_and_update_results(app))

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

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

    admin_set_teams_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(setteams_match_selected, pattern="^setteams_match:")],
        states={
            ADMIN_SET_TEAMS_HOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_teams_home)],
            ADMIN_SET_TEAMS_AWAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_teams_away)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_part1_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin:part1_results$")],
        states={
            ADMIN_PART1_RESULTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_part1_results)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(part1_conv)
    app.add_handler(admin_add_conv)
    app.add_handler(admin_result_conv)
    app.add_handler(admin_set_teams_conv)
    app.add_handler(admin_part1_conv)
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu:"))
    app.add_handler(CallbackQueryHandler(show_stage_days, pattern="^stage:"))
    app.add_handler(CallbackQueryHandler(show_game_day, pattern="^gameday:"))
    app.add_handler(CallbackQueryHandler(start_prediction, pattern="^predict:"))
    app.add_handler(CallbackQueryHandler(handle_score_home, pattern="^sh:"))
    app.add_handler(CallbackQueryHandler(handle_score_away, pattern="^sa:"))
    app.add_handler(CallbackQueryHandler(handle_double_toggle, pattern="^double_toggle:"))
    app.add_handler(CallbackQueryHandler(handle_save_pred, pattern="^save_pred:"))
    app.add_handler(CallbackQueryHandler(show_setteams_stage_matches, pattern="^setteams_stage:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin:"))
    app.add_handler(CallbackQueryHandler(show_my_predictions_stage, pattern="^mypred:"))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back:"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
