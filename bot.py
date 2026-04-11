import os
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from supabase import create_client, Client

# ============================================
# НАСТРОЙКИ — сюда вставляешь свои ключи
# ============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]

# ============================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Состояния для диалогов
(
    PART1_1ST, PART1_2ND, PART1_3RD, PART1_4TH, PART1_SCORER,
    PRED_HOME, PRED_AWAY,
    ADMIN_ADD_NAME, ADMIN_ADD_USERNAME, ADMIN_ADD_EMAIL,
    ADMIN_RESULT_MATCH, ADMIN_RESULT_HOME, ADMIN_RESULT_AWAY,
) = range(13)

TEAMS = [
    "Аргентина", "Франция", "Бразилия", "Англия", "Испания", "Португалия",
    "Германия", "Нидерланды", "Бельгия", "Хорватия", "Уругвай", "Мексика",
    "США", "Канада", "Марокко", "Сенегал", "Япония", "Южная Корея",
    "Австралия", "Дания", "Швейцария", "Польша", "Сербия", "Венгрия",
    "Румыния", "Украина", "Турция", "Иран", "Саудовская Аравия", "Катар",
    "Эквадор", "Колумбия", "Чили", "Перу", "Венесуэла", "Боливия",
    "Камерун", "Нигерия", "Гана", "Кот-д'Ивуар", "Египет", "Алжир",
    "ЮАР", "Тунис", "Новая Зеландия", "Индонезия", "Узбекистан", "Ирак",
]


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_participant(telegram_id: str):
    """Получить участника по telegram_id"""
    res = supabase.table("participants").select("*").eq("telegram_id", telegram_id).execute()
    return res.data[0] if res.data else None


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_part1_locked() -> bool:
    """Проверяем заблокирован ли прогноз топ-4 (начался первый матч ЧМ)"""
    res = supabase.table("part1_predictions").select("is_locked").limit(1).execute()
    if res.data:
        return res.data[0]["is_locked"]
    # Проверяем по первому матчу в базе
    match = supabase.table("matches").select("kickoff_at").order("kickoff_at").limit(1).execute()
    if match.data:
        kickoff = datetime.fromisoformat(match.data[0]["kickoff_at"].replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= kickoff
    return False


def get_game_day_status(game_day_id: str):
    """Проверяем заблокирован ли игровой день"""
    res = supabase.table("game_days").select("*").eq("id", game_day_id).execute()
    if not res.data:
        return None
    day = res.data[0]
    deadline = datetime.fromisoformat(day["deadline"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return {**day, "is_past_deadline": now >= deadline}


def teams_keyboard(selected=None, page=0):
    """Клавиатура выбора команды постранично"""
    per_page = 16
    start = page * per_page
    chunk = TEAMS[start:start + per_page]
    buttons = []
    row = []
    for i, team in enumerate(chunk):
        mark = "✅ " if team == selected else ""
        row.append(InlineKeyboardButton(mark + team, callback_data=f"team:{team}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{page-1}"))
    if start + per_page < len(TEAMS):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page:{page+1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(buttons)


def score_keyboard(side: str):
    """Клавиатура выбора счёта (0–5+)"""
    scores = ["0", "1", "2", "3", "4", "5+"]
    buttons = [[InlineKeyboardButton(s, callback_data=f"score:{side}:{s}") for s in scores]]
    return InlineKeyboardMarkup(buttons)


# ============================================
# /start — главное меню
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = str(user.id)
    participant = get_participant(telegram_id)

    if not participant or participant["payment_status"] != "paid":
        await update.message.reply_text(
            "👋 Привет! Это бот конкурса прогнозов на Чемпионат мира 2026.\n\n"
            "Чтобы участвовать, нужно оплатить взнос 20€.\n"
            "👉 Перейди по ссылке: [ссылка на лендинг]\n\n"
            "Если уже оплатил переводом — напиши организатору."
        )
        return

    name = participant["name"]
    await update.message.reply_text(
        f"👋 Привет, {name}!\n\n"
        "Что хочешь сделать?",
        reply_markup=main_menu_keyboard(user.id)
    )


def main_menu_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton("🏆 Прогноз Топ-4 и бомбардир", callback_data="menu:part1")],
        [InlineKeyboardButton("⚽ Прогнозы на матчи", callback_data="menu:matches")],
        [InlineKeyboardButton("📊 Таблица лидеров", callback_data="menu:leaderboard")],
        [InlineKeyboardButton("📋 Мои прогнозы", callback_data="menu:my_predictions")],
    ]
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton("🔧 Админ-панель", callback_data="menu:admin")])
    return InlineKeyboardMarkup(buttons)


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


# ============================================
# ЧАСТЬ 1 — прогноз Топ-4 и бомбардир
# ============================================

async def show_part1_menu(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))
    locked = is_part1_locked()

    pred = supabase.table("part1_predictions").select("*").eq(
        "participant_id", participant["id"]
    ).execute()

    if pred.data:
        p = pred.data[0]
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
                "Баллы:\n"
                "🥇 1 место — 10 очков\n"
                "🥈 2 место — 8 очков\n"
                "🥉 3 место — 6 очков\n"
                "4️⃣ 4 место — 4 очка\n"
                "⚽ Бомбардир — 8 очков\n\n"
                "Прогноз можно менять до старта турнира.",
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
        await query.edit_message_text(
            "🥇 Выбери команду — чемпион мира (1 место):",
            reply_markup=teams_keyboard()
        )
        context.user_data["part1_step"] = "1st"
        return PART1_1ST


async def part1_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("page:"):
        page = int(query.data.split(":")[1])
        step = context.user_data.get("part1_step", "1st")
        labels = {"1st": "чемпион (1 место)", "2nd": "2 место", "3rd": "3 место", "4th": "4 место"}
        await query.edit_message_text(
            f"Выбери команду — {labels.get(step, '')}:",
            reply_markup=teams_keyboard(page=page)
        )
        return PART1_1ST

    team = query.data.split(":")[1]
    step = context.user_data.get("part1_step")

    steps = {
        "1st": ("2nd", "🥈 Выбери команду — 2 место:", PART1_2ND),
        "2nd": ("3rd", "🥉 Выбери команду — 3 место:", PART1_3RD),
        "3rd": ("4th", "4️⃣ Выбери команду — 4 место:", PART1_4TH),
        "4th": (None, None, PART1_SCORER),
    }

    context.user_data["part1"][step] = team

    if step == "4th":
        await query.edit_message_text(
            "⚽ Напиши имя лучшего бомбардира турнира\n"
            "(например: Килиан Мбаппе):"
        )
        return PART1_SCORER

    next_step, next_text, next_state = steps[step]
    context.user_data["part1_step"] = next_step
    await query.edit_message_text(next_text, reply_markup=teams_keyboard())
    return next_state


async def part1_scorer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scorer = update.message.text.strip()
    user = update.effective_user
    participant = get_participant(str(user.id))
    p = context.user_data["part1"]

    data = {
        "participant_id": participant["id"],
        "team_1st": p["1st"],
        "team_2nd": p["2nd"],
        "team_3rd": p["3rd"],
        "team_4th": p["4th"],
        "top_scorer": scorer,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = supabase.table("part1_predictions").select("id").eq(
        "participant_id", participant["id"]
    ).execute()

    if existing.data:
        supabase.table("part1_predictions").update(data).eq(
            "participant_id", participant["id"]
        ).execute()
    else:
        supabase.table("part1_predictions").insert(data).execute()

    await update.message.reply_text(
        f"✅ Прогноз сохранён!\n\n"
        f"🥇 {p['1st']}\n"
        f"🥈 {p['2nd']}\n"
        f"🥉 {p['3rd']}\n"
        f"4️⃣ {p['4th']}\n"
        f"⚽ {scorer}\n\n"
        "Можешь изменить прогноз в любой момент до старта турнира.",
        reply_markup=main_menu_keyboard(user.id)
    )
    return ConversationHandler.END


# ============================================
# ЧАСТЬ 2 — прогнозы на матчи
# ============================================

async def show_matches_menu(query, context):
    """Показываем доступные игровые дни"""
    now = datetime.now(timezone.utc)

    # Берём игровые дни где есть незавершённые матчи
    days = supabase.table("game_days").select("*").order("day_number").execute()

    if not days.data:
        await query.edit_message_text(
            "⚽ Расписание матчей ещё не добавлено.\nЖди ближе к старту турнира!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")
            ]])
        )
        return

    buttons = []
    for day in days.data:
        deadline = datetime.fromisoformat(day["deadline"].replace("Z", "+00:00"))
        locked = now >= deadline

        # Считаем матчи дня
        matches = supabase.table("matches").select("id,is_finished").eq(
            "game_day_id", day["id"]
        ).execute()
        total = len(matches.data)
        finished = sum(1 for m in matches.data if m["is_finished"])

        if finished == total and total > 0:
            status = "✅"
        elif locked:
            status = "🔒"
        else:
            status = "📝"

        label = f"{status} День {day['day_number']} ({finished}/{total} матчей)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"gameday:{day['id']}")])

    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")])
    await query.edit_message_text(
        "⚽ Выбери игровой день для прогнозов:\n\n"
        "📝 — открыт для прогнозов\n"
        "🔒 — заблокирован (матчи начались)\n"
        "✅ — все матчи сыграны",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def show_game_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_day_id = query.data.split(":")[1]
    user = query.from_user
    participant = get_participant(str(user.id))

    day_info = get_game_day_status(game_day_id)
    locked = day_info["is_past_deadline"]

    matches = supabase.table("matches").select("*").eq(
        "game_day_id", game_day_id
    ).order("kickoff_at").execute()

    if not matches.data:
        await query.edit_message_text("Матчи этого дня ещё не добавлены.")
        return

    # Получаем прогнозы участника на эти матчи
    match_ids = [m["id"] for m in matches.data]
    preds_res = supabase.table("predictions").select("*").eq(
        "participant_id", participant["id"]
    ).in_("match_id", match_ids).execute()
    preds = {p["match_id"]: p for p in preds_res.data}

    # Проверяем выбран ли X2 на этот день
    double_match_id = next(
        (p["match_id"] for p in preds_res.data if p["is_double"]), None
    )

    text = f"📅 День {day_info['day_number']}\n"
    if locked:
        text += "🔒 Прогнозы заблокированы\n\n"
    else:
        text += "📝 Открыт для прогнозов\n\n"

    buttons = []
    for m in matches.data:
        pred = preds.get(m["id"])
        kickoff = datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00"))
        time_str = kickoff.strftime("%d.%m %H:%M")

        if pred:
            score = f"{pred['home_score_pred']}:{pred['away_score_pred']}"
            double_mark = " 🔥×2" if pred["is_double"] else ""
            if m["is_finished"]:
                pts = pred["points_earned"]
                real = f"{m['home_score']}:{m['away_score']}"
                label = f"✅ {m['home_team']} {score} {m['away_team']} (факт: {real}, +{pts}){double_mark}"
            else:
                label = f"📝 {m['home_team']} {score} {m['away_team']} {time_str}{double_mark}"
        else:
            label = f"❓ {m['home_team']} — {m['away_team']} {time_str}"

        if not locked and not m["is_finished"]:
            buttons.append([InlineKeyboardButton(label, callback_data=f"predict:{m['id']}")])
        else:
            buttons.append([InlineKeyboardButton(label, callback_data="noop")])

    if not locked:
        text += "Нажми на матч чтобы поставить прогноз.\n"
        if double_match_id:
            text += "🔥 Матч с X2 уже выбран. Нажми на него чтобы сменить."

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="menu:matches")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def start_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "noop":
        return

    match_id = query.data.split(":")[1]
    context.user_data["pred_match_id"] = match_id

    match = supabase.table("matches").select("*").eq("id", match_id).execute().data[0]
    context.user_data["pred_match"] = match

    await query.edit_message_text(
        f"⚽ {match['home_team']} — {match['away_team']}\n\n"
        f"Сколько голов забьёт {match['home_team']}?",
        reply_markup=score_keyboard("home")
    )
    return PRED_HOME


async def pred_home_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    score = query.data.split(":")[2]
    score_val = 5 if score == "5+" else int(score)
    context.user_data["pred_home"] = score_val
    match = context.user_data["pred_match"]

    await query.edit_message_text(
        f"⚽ {match['home_team']} — {match['away_team']}\n"
        f"Хозяева: {score}\n\n"
        f"Сколько голов забьёт {match['away_team']}?",
        reply_markup=score_keyboard("away")
    )
    return PRED_AWAY


async def pred_away_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    score = query.data.split(":")[2]
    score_val = 5 if score == "5+" else int(score)
    context.user_data["pred_away"] = score_val
    match = context.user_data["pred_match"]
    home_score = context.user_data["pred_home"]

    await query.edit_message_text(
        f"⚽ {match['home_team']} {home_score}:{score_val} {match['away_team']}\n\n"
        "🔥 Хочешь сделать этот матч своим X2?\n"
        "Очки за этот матч удвоятся (в том числе 0 останется 0).\n"
        "На каждый игровой день — только один X2!",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔥 Да, X2!", callback_data="double:yes"),
                InlineKeyboardButton("Нет", callback_data="double:no"),
            ]
        ])
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

    # Если выбрал X2 — снимаем его с других матчей этого дня
    if is_double:
        day_matches = supabase.table("matches").select("id").eq(
            "game_day_id", match["game_day_id"]
        ).execute()
        day_match_ids = [m["id"] for m in day_matches.data]
        supabase.table("predictions").update({"is_double": False}).eq(
            "participant_id", participant["id"]
        ).in_("match_id", day_match_ids).execute()

    data = {
        "participant_id": participant["id"],
        "match_id": match["id"],
        "home_score_pred": home_score,
        "away_score_pred": away_score,
        "is_double": is_double,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_calculated": False,
        "points_earned": 0,
    }

    existing = supabase.table("predictions").select("id").eq(
        "participant_id", participant["id"]
    ).eq("match_id", match["id"]).execute()

    if existing.data:
        supabase.table("predictions").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("predictions").insert(data).execute()

    double_text = " 🔥×2" if is_double else ""
    await query.edit_message_text(
        f"✅ Прогноз сохранён!\n\n"
        f"⚽ {match['home_team']} {home_score}:{away_score} {match['away_team']}{double_text}\n\n"
        "Можешь изменить до начала матча.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад к матчам", callback_data=f"gameday:{match['game_day_id']}")
        ]])
    )
    return ConversationHandler.END


# ============================================
# МОИ ПРОГНОЗЫ
# ============================================

async def show_my_predictions(query, context):
    user = query.from_user
    participant = get_participant(str(user.id))

    preds = supabase.table("predictions").select(
        "*, matches(home_team, away_team, home_score, away_score, is_finished, kickoff_at)"
    ).eq("participant_id", participant["id"]).execute()

    if not preds.data:
        await query.edit_message_text(
            "У тебя пока нет прогнозов на матчи.\n"
            "Перейди в раздел 'Прогнозы на матчи'!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")
            ]])
        )
        return

    text = "📋 Твои прогнозы:\n\n"
    total = 0
    for p in preds.data:
        m = p["matches"]
        double = " 🔥×2" if p["is_double"] else ""
        pred_score = f"{p['home_score_pred']}:{p['away_score_pred']}"

        if m["is_finished"]:
            real = f"{m['home_score']}:{m['away_score']}"
            pts = p["points_earned"]
            total += pts
            text += f"✅ {m['home_team']} {pred_score} {m['away_team']} (факт: {real}, +{pts}){double}\n"
        else:
            kickoff = datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00"))
            time_str = kickoff.strftime("%d.%m %H:%M")
            text += f"📝 {m['home_team']} {pred_score} {m['away_team']} {time_str}{double}\n"

    text += f"\n💰 Очков за часть 2: {total}"

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")
        ]])
    )


# ============================================
# ТАБЛИЦА ЛИДЕРОВ
# ============================================

async def show_leaderboard(query, context):
    lb = supabase.table("leaderboard").select(
        "*, participants(name)"
    ).order("total_points", desc=True).limit(20).execute()

    if not lb.data:
        await query.edit_message_text("Таблица лидеров пока пуста.")
        return

    text = "📊 Таблица лидеров (топ-20):\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, entry in enumerate(lb.data, 1):
        medal = medals.get(i, f"{i}.")
        name = entry["participants"]["name"]
        pts = entry["total_points"]
        text += f"{medal} {name} — {pts} очков\n"

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")
        ]])
    )


# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================

async def show_admin_panel(query, context):
    if not is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return

    await query.edit_message_text(
        "🔧 Админ-панель\n\nЧто хочешь сделать?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить участника", callback_data="admin:add_user")],
            [InlineKeyboardButton("⚽ Ввести результат матча", callback_data="admin:add_result")],
            [InlineKeyboardButton("📋 Список участников", callback_data="admin:list_users")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="back:main")],
        ])
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    action = query.data.split(":")[1]

    if action == "add_user":
        await query.edit_message_text(
            "➕ Добавление участника\n\n"
            "Введи имя участника:"
        )
        return ADMIN_ADD_NAME

    elif action == "add_result":
        await query.edit_message_text(
            "⚽ Введи номер матча (match_number):"
        )
        return ADMIN_RESULT_MATCH

    elif action == "list_users":
        users = supabase.table("participants").select("*").order("created_at").execute()
        if not users.data:
            await query.edit_message_text("Участников пока нет.")
            return
        text = "📋 Участники:\n\n"
        for u in users.data:
            method = "💳" if u["payment_method"] == "stripe" else "🤝"
            tg = f"@{u['telegram_username']}" if u["telegram_username"] else "нет username"
            text += f"{method} {u['name']} ({tg})\n"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="menu:admin")
            ]])
        )


async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_user_name"] = update.message.text.strip()
    await update.message.reply_text("Введи Telegram username (без @), или напиши 'нет':")
    return ADMIN_ADD_USERNAME


async def admin_add_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["new_user_username"] = None if val.lower() == "нет" else val
    await update.message.reply_text("Введи email участника (или 'нет'):")
    return ADMIN_ADD_EMAIL


async def admin_add_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    email = None if val.lower() == "нет" else val
    name = context.user_data["new_user_name"]
    username = context.user_data.get("new_user_username")

    supabase.table("participants").insert({
        "name": name,
        "telegram_username": username,
        "email": email,
        "payment_status": "paid",
        "payment_method": "manual",
        "paid_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    await update.message.reply_text(
        f"✅ Участник добавлен!\n"
        f"Имя: {name}\n"
        f"Username: @{username or '—'}\n"
        f"Email: {email or '—'}\n\n"
        f"Попроси его написать боту /start",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END


async def admin_result_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        num = int(update.message.text.strip())
        match = supabase.table("matches").select("*").eq("match_number", num).execute()
        if not match.data:
            await update.message.reply_text("Матч не найден. Попробуй ещё раз:")
            return ADMIN_RESULT_MATCH
        context.user_data["result_match"] = match.data[0]
        m = match.data[0]
        await update.message.reply_text(
            f"Матч #{num}: {m['home_team']} — {m['away_team']}\n"
            f"Введи голы хозяев:"
        )
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

        # Сохраняем результат
        supabase.table("matches").update({
            "home_score": home,
            "away_score": away,
            "is_finished": True,
        }).eq("id", match["id"]).execute()

        # Пересчитываем очки через функцию в Supabase
        supabase.rpc("calculate_match_points", {"p_match_id": match["id"]}).execute()

        await update.message.reply_text(
            f"✅ Результат сохранён!\n"
            f"{match['home_team']} {home}:{away} {match['away_team']}\n\n"
            f"Очки всем участникам пересчитаны.",
            reply_markup=main_menu_keyboard(update.effective_user.id)
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Введи число:")
        return ADMIN_RESULT_AWAY


# ============================================
# НАВИГАЦИЯ НАЗАД
# ============================================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]
    if action == "main":
        user = query.from_user
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=main_menu_keyboard(user.id)
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отменено.",
        reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return ConversationHandler.END


# ============================================
# ЗАПУСК
# ============================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Диалог: прогноз Топ-4
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

    # Диалог: прогноз на матч
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

    # Диалог: добавление участника (админ)
    admin_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin:add_user$")],
        states={
            ADMIN_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_name)],
            ADMIN_ADD_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_username)],
            ADMIN_ADD_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Диалог: ввод результата (админ)
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
