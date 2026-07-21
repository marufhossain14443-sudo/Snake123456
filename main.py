import os
import pytz
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Union, Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- LOGGING CONFIGURATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION CONSTANTS ---
BOT_TOKEN = "8228002569:AAH7otCILVYaW2oe3szFwbXJkjQBGpMo4cw"  
ADMIN_ID = 8515307600              
PHOTO_FILE_ID = "AgACAgUAAxkBAAN-alXXQJrtBa1u9qMdD6iK9EC-a1UAAvEPaxve0rFWKXzgVqo1WbcBAAMCAAN5AAM9BA"  
UPI_ID = "mdmaruf009@fam"
FAMPAY_API_KEY = "FAM_53079e898dd64bfb8f30f4346456b218bb9a31dd72c717a7"

# --- IN-MEMORY DATABASE ---
db_users: Dict[int, dict] = {}
db_resellers: List[int] = []
db_keys: Dict[str, Dict[str, Dict[str, List[str]]]] = {} 
db_prices: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
db_files: Dict[str, dict] = {}

# প্রোডাক্ট ও গেম ম্যাট্রিক্স
GAMES_MATRIX = {
    "snake": ["🎱8 Ball", "🎯Carrom", "⚽Soccer"],
    "kos": ["🎱8 Ball", "🎯Carrom", "🐦‍🔥Free Fire"],
    "aim": ["🎱Ak Leodar", "🎯Aim Carrom"],
    "drip": ["⚡Free Fire", "🎱8 Ball"],
    "brmod": ["📱Br Mod (FF)", "💻Br Mod (FF)"]
}

for role in ["customer", "reseller"]:
    db_prices[role] = {k: {g: {} for g in v} for k, v in GAMES_MATRIX.items()}

# --- FSM STATES ---
class BotStates(StatesGroup):
    waiting_for_usdt_tx = State()
    waiting_for_usdt_amount = State()
    waiting_for_price_value = State()
    waiting_for_keys_input = State()
    waiting_for_reseller_add = State()
    waiting_for_reseller_cancel = State()
    waiting_for_update_file = State()
    waiting_for_update_version = State()
    waiting_for_broadcast_msg = State()
    waiting_for_manage_bal_uid = State()
    waiting_for_manage_bal_amount = State()
    waiting_for_find_user_uid = State()

# --- INITIALIZE CORE OBJECTS ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- HELPER FUNCTIONS ---
def get_current_time_matrix() -> tuple:
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    return now.strftime("%H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")

def fetch_user_record(user_id: int, username: str) -> dict:
    role = "Reseller" if user_id in db_resellers else "Customer"
    if user_id not in db_users:
        db_users[user_id] = {
            "username": username if username else "User",
            "balance": 0.0,
            "role": role,
            "last_purchase": "No purchases yet",
            "total_orders": 0,
            "order_history": []
        }
    else:
        db_users[user_id]["role"] = role
        if username:
            db_users[user_id]["username"] = username
    return db_users[user_id]

# --- UI RENDER ENGINE ---
async def unified_render_frame(target: Union[Message, CallbackQuery], text: str, keyboard: InlineKeyboardMarkup):
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_media(
                media=InputMediaPhoto(media=PHOTO_FILE_ID, caption=text, parse_mode="HTML"),
                reply_markup=keyboard
            )
        except Exception:
            try:
                await target.message.delete()
            except Exception:
                pass
            await target.message.answer_photo(photo=PHOTO_FILE_ID, caption=text, parse_mode="HTML", reply_markup=keyboard)
        await target.answer()
    else:
        await target.answer_photo(photo=PHOTO_FILE_ID, caption=text, parse_mode="HTML", reply_markup=keyboard)

# --- UI PAYLOAD GENERATOR ---
def generate_main_menu_payload(user_id: int, username: str) -> tuple:
    profile = fetch_user_record(user_id, username)
    ctime, cdate = get_current_time_matrix()
    
    red_html_name = f'<u><b><a href="tg://user?id={user_id}">{profile["username"]}</a></b></u>'
    
    text = f"""━━━━━━━━━━━━━━━━━━━━
🎮 𝗪𝗘𝗟𝗖𝗢𝗠𝗘, {red_html_name}!
━━━━━━━━━━━━━━━━━━━━

👤 <i>𝗨𝗦𝗘𝗥 𝗗𝗘𝗧𝗔𝗜𝗟𝗦:</i>
🆔 <i>𝗨𝘀𝗲𝗿 𝗜𝗗:</i> <code>{user_id}</code>
💰 <i><b>𝗕𝗮𝗹𝗮𝗻𝗰𝗲:</b></i> ₹{profile['balance']:.2f}
🎖️ <i>𝗦𝘁𝗮𝘁𝘂𝘀:</i> {profile['role']}

📊 <i><b>𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗛𝗜𝗦𝗧𝗢𝗥𝗬:</b></i>
⏱️ <i>𝗟𝗮𝘀𝘁 𝗣𝘂𝗿𝗰𝗵𝗮𝘀𝗲:</i> {profile['last_purchase']}
🛒 <i><b>𝗧𝗼𝘁𝗮𝗹 𝗢𝗿𝗱𝗲𝗿𝘀:</b></i> {profile['total_orders']}

📅 <i>𝗦𝗘𝗦𝗦𝗜𝗢𝗡 𝗜𝗡𝗙𝗢:</i>
⏰ <i>𝗧𝗶𝗺𝗲:</i> {ctime} | 📅 <i>𝗗𝗮𝘁𝗲:</i> {cdate}

━━━━━━━━━━━━━━━━━━━━
💥 𝗔𝗣𝗘𝗫 𝗚𝗔𝗠𝗜𝗡𝗚 𝗦𝗛𝗢𝗣
━━━━━━━━━━━━━━━━━━━━"""

    kb = [
        [InlineKeyboardButton(text="🔑 𝗕𝘂𝘆 𝗞𝗲𝘆", callback_data="root_buy_key", style="success")],
        [
            InlineKeyboardButton(text="💳 𝗗𝗲𝗽𝗼𝘀𝗶𝘁", callback_data="root_deposit", style="primary"),
            InlineKeyboardButton(text="📦 𝗢𝗿𝗱𝗲𝗿𝘀", callback_data="root_orders_history", style="primary")
        ],
        [InlineKeyboardButton(text="📊 𝗦𝘁𝗼𝗰𝗸", callback_data="root_stock_view", style="danger")],
        [InlineKeyboardButton(text="📥 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱", callback_data="root_download", style="success")]
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ 𝘼𝘿𝙈𝙄𝙉 𝙋𝘼𝙉𝙀𝙇", callback_data="admin_root", style="danger")])
        
    return text, InlineKeyboardMarkup(inline_keyboard=kb)

# --- START COMMAND ---
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text, kb = generate_main_menu_payload(message.from_user.id, message.from_user.full_name)
    await unified_render_frame(message, text, kb)

@dp.callback_query(F.data == "go_home")
async def callback_go_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = generate_main_menu_payload(callback.from_user.id, callback.from_user.full_name)
    await unified_render_frame(callback, text, kb)

# =====================================================================
#                          USER: BUY KEY FLOW
# =====================================================================
@dp.callback_query(F.data == "root_buy_key")
async def buy_key_root(callback: CallbackQuery):
    text = "━━━━━━━━━━━━━━━━━━━━\n🔑 𝗦𝗘𝗟𝗘𝗖𝗧 𝗜𝗡𝗝𝗘𝗖𝗧𝗢𝗥\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Choose the client injector to view available keys:</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐍 𝗦𝗻𝗮𝗸𝗲 𝗞𝗲𝘆", callback_data="buy_inj:snake", style="primary")],
        [InlineKeyboardButton(text="🕹️ 𝗞𝗼𝘀 𝗞𝗲𝘆", callback_data="buy_inj:kos", style="primary")],
        [InlineKeyboardButton(text="🎯 𝗔𝗶𝗺 𝗔𝘀𝘀𝗶𝘀𝘁", callback_data="buy_inj:aim", style="primary")],
        [InlineKeyboardButton(text="👾 𝗗𝗿𝗶𝗽 𝗞𝗲𝘆", callback_data="buy_inj:drip", style="primary")],
        [InlineKeyboardButton(text="🔥 𝗕𝗿 𝗠𝗼𝗱", callback_data="buy_inj:brmod", style="primary")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="go_home", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("buy_inj:"))
async def buy_key_games(callback: CallbackQuery):
    inj = callback.data.split(":")[1]
    text = f"━━━━━━━━━━━━━━━━━━━━\n🎮 𝗦𝗘𝗟𝗘𝗖𝗧 𝗚𝗔𝗠𝗘 ({inj.upper()})\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Select your targeted game ecosystem:</i>"
    kb = []
    for game in GAMES_MATRIX[inj]:
        kb.append([InlineKeyboardButton(text=f"{game}", callback_data=f"buy_gam:{inj}:{game}", style="primary")])
    kb.append([InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="root_buy_key", style="danger")])
    await unified_render_frame(callback, text, InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_gam:"))
async def buy_key_duration(callback: CallbackQuery):
    _, inj, game = callback.data.split(":")
    text = f"━━━━━━━━━━━━━━━━━━━━\n⏳ 𝗦𝗘𝗟𝗘𝗖𝗧 𝗗𝗨𝗥𝗔𝗧𝗜𝗢𝗡\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Injector: {inj.upper()}\nGame: {game}\n\nSelect plans:</i>"
    
    if inj == "snake":
        durations = ["3 Days", "10 Days", "30 Days", "90 Days"]
    elif inj == "kos":
        durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "aim":
        durations = ["3 Days", "7 Days", "30 Days", "90 Days"]
    elif inj == "drip" and game == "⚡Free Fire":
        durations = ["1 Days", "3 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "drip" and game == "🎱8 Ball":
        durations = ["1 Days", "7 Days", "30 Days"]
    elif inj == "brmod" and game == "📱Br Mod (FF)":
        durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "brmod" and game == "💻Br Mod (FF)":
        durations = ["1 Days", "10 Days", "30 Days"]
    else:
        durations = ["1 Days", "7 Days", "30 Days"]

    role = "reseller" if callback.from_user.id in db_resellers else "customer"
    kb = []
    for dur in durations:
        price = db_prices[role].get(inj, {}).get(game, {}).get(dur, 0.0)
        kb.append([InlineKeyboardButton(text=f"⛅ {dur} - (₹{price:.2f})", callback_data=f"buy_plan:{inj}:{game}:{dur}", style="primary")])
    
    kb.append([InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data=f"buy_inj:{inj}", style="danger")])
    await unified_render_frame(callback, text, InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_plan:"))
async def buy_key_quantity_check(callback: CallbackQuery):
    _, inj, game, dur = callback.data.split(":")
    user_id = callback.from_user.id
    
    if user_id in db_resellers:
        text = f"━━━━━━━━━━━━━━━━━━━━\n🔢 𝗦𝗘𝗟𝗘𝗖𝗧 𝗤𝗨𝗔𝗡𝗧𝗜𝗧𝗬\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Select how many keys you want to purchase for {inj.upper()} - {game} ({dur}):</i>"
        kb = [
            [
                InlineKeyboardButton(text="1x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:1", style="primary"),
                InlineKeyboardButton(text="2x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:2", style="primary"),
                InlineKeyboardButton(text="3x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:3", style="primary")
            ],
            [
                InlineKeyboardButton(text="4x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:4", style="primary"),
                InlineKeyboardButton(text="5x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:5", style="primary"),
                InlineKeyboardButton(text="6x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:6", style="primary")
            ],
            [
                InlineKeyboardButton(text="7x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:7", style="primary"),
                InlineKeyboardButton(text="8x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:8", style="primary"),
                InlineKeyboardButton(text="9x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:9", style="primary")
            ],
            [InlineKeyboardButton(text="10x", callback_data=f"buy_qnt:{inj}:{game}:{dur}:10", style="primary")],
            [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data=f"buy_gam:{inj}:{game}", style="danger")]
        ]
        await unified_render_frame(callback, text, InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        
        # কাস্টমারদের জন্য সরাসরি ১ পিসের কনফার্মেশন স্ক্রিন লোড হবে
        # Pydantic Frozen এরর এড়াতে model_copy দিয়ে ডেটা আপডেট করা হলো, আপনার বাকি সব লজিক একই থাকবে
        new_callback = callback.model_copy(
            update={"data": f"buy_qnt:{inj}:{game}:{dur}:1"}
        )
        await buy_key_confirm(new_callback)

@dp.callback_query(F.data.startswith("buy_qnt:"))
async def buy_key_confirm(callback: CallbackQuery):
    _, inj, game, dur, qty = callback.data.split(":")
    qty = int(qty)
    role = "reseller" if callback.from_user.id in db_resellers else "customer"
    single_price = db_prices[role].get(inj, {}).get(game, {}).get(dur, 0.0)
    total_price = single_price * qty
    
    text = f"━━━━━━━━━━━━━━━━━━━━\n🛒 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘\n━━━━━━━━━━━━━━━━━━━━\n\n🎮 <b>𝗚𝗮𝗺𝗲:</b> {inj.upper()} - {game}\n⏳ <b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻:</b> {dur}\n🔢 <b>𝗤𝘂𝗮𝗻𝘁𝗶𝘁𝘆:</b> {qty}x\n💰 <b>𝗔𝗺𝗼𝘂𝗻𝘁:</b> (₹{total_price:.2f})\n\n<i>Are you sure you want to purchase this license key?</i>"
    
    # আপনার আগের স্টাইলগুলো (success, danger) এখানে একদম অক্ষত রাখা হয়েছে
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ 𝗖𝗼𝗻𝗳𝗶𝗿𝗺 𝗕𝘂𝘆", callback_data=f"buy_exec:{inj}:{game}:{dur}:{qty}", style="success")],
        [InlineKeyboardButton(text="❌ 𝗖𝗮𝗻𝗰𝗲𝗹", callback_data="root_buy_key", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("buy_exec:"))
async def buy_key_execute(callback: CallbackQuery):
    _, inj, game, dur, qty = callback.data.split(":")
    qty = int(qty)
    user_id = callback.from_user.id
    role = "reseller" if user_id in db_resellers else "customer"
    single_price = db_prices[role].get(inj, {}).get(game, {}).get(dur, 0.0)
    total_price = single_price * qty
    profile = fetch_user_record(user_id, callback.from_user.full_name)
    
    if profile["balance"] < total_price:
        await callback.answer("⚠️ Insufficient balance! Please deposit money.", show_alert=True)
        return

    stock_list = db_keys.get(inj, {}).get(game, {}).get(dur, [])
    if len(stock_list) < qty:
        await callback.answer(f"❌ Stock Empty or Insufficient! Total available: {len(stock_list)} keys.", show_alert=True)
        return
    
    delivered_keys = []
    for _ in range(qty):
        delivered_keys.append(stock_list.pop(0))
        
    profile["balance"] -= total_price
    profile["total_orders"] += qty
    profile["last_purchase"] = f"{inj.upper()} {dur} ({qty}x)"
    _, timestamp = get_current_time_matrix()
    
    formatted_keys_text = "\n".join([f"<code>{k}</code>" for k in delivered_keys])
    profile["order_history"].append(f"📦 Keys ({qty}x) Delivered | Plan: {inj.upper()}-{dur} | Cost: ₹{total_price} | Date: {timestamp}")
    
    success_text = f"━━━━━━━━━━━━━━━━━━━━\n🎉 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟\n━━━━━━━━━━━━━━━━━━━━\n\n🗝️ <b>𝗬𝗼𝘂𝗿 𝗟𝗶𝗰𝗲𝗻𝘀𝗲 𝗞𝗲𝘆(𝘀):</b>\n{formatted_keys_text}\n\n📌 <i>Click on the keys to copy instantly.</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏎ 𝗠𝗮𝗶𝗻 𝗠𝗲𝗻𝘂", callback_data="go_home", style="success")]])
    await unified_render_frame(callback, success_text, kb)
    
    admin_log = f"""━━━━━━━━━━━━━━
🛒 𝗡𝗘𝗪 𝗦𝗔𝗟𝗘 𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗
━━━━━━━━━━━━━━

👤 𝗖𝘂𝘀𝘁𝗼𝗺𝗲𝗿 𝗗𝗲𝘁𝗮𝗶𝗹𝘀
➥ 🧑 𝗡𝗮𝗺𝗲 : {profile['username']}

💸 𝗢𝗿𝗱𝗲𝗿 𝗗𝗲𝘁𝗮𝗶𝗹𝘀
➥ 🎮 𝗚𝗮𝗺𝗲 : {inj.upper()}
➥ 📦 𝗣𝗮𝗰𝗸 : {game}
➥ ⏳ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 : {dur}
➥ 🔢 𝗤𝘂𝗮𝗻𝘁𝗶𝘁𝘆 : {qty}x
➥ 💰 𝗔𝗺𝗼𝘂𝗻𝘁 : ₹{total_price:.2f}
➥ 🛍 𝗧𝘆𝗽𝗲 : 👤 {profile['role']}
➥ 🕒 𝗧𝗶𝗺𝗲 : {timestamp} IST

━━━━━━━━━━━━━━"""
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_log)
    except Exception:
        pass

# =====================================================================
#                          USER: DEPOSIT SYSTEM (INR & USDT)
# =====================================================================
@dp.callback_query(F.data == "root_deposit")
async def root_deposit_menu(callback: CallbackQuery):
    text = "━━━━━━━━━━━━━━━━━━━━\n💳 𝗗𝗘𝗣𝗢𝗦𝗜𝗧 𝗠𝗘𝗧𝗛𝗢𝗗𝗦\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Choose your transaction terminal currency type:</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="₹", callback_data="dep_inr_gate", style="danger"),
            InlineKeyboardButton(text="$", callback_data="dep_usdt_gate", style="danger")
        ],
        [InlineKeyboardButton(text="📦 𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗛𝗶𝘀𝘁𝗼𝗿𝘆", callback_data="root_tx_history", style="success")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="go_home", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "dep_inr_gate")
async def dep_inr_gate(callback: CallbackQuery):
    qr_endpoint = f"https://fampay.anujbots.xyz/qr.php?upi={UPI_ID}&amount=0"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(qr_endpoint) as resp:
                if resp.status == 200:
                    res_data = await resp.json()
                    if res_data.get("status") == "success":
                        order_id = res_data["data"]["order_id"]
                        qr_url = res_data["data"]["qr_url"]
                        text = f"━━━━━━━━━━━━━━━━━━━━\n📥 𝗦𝗖𝗔𝗡 𝗔𝗡𝗗 𝗣𝗔𝗬 (𝗜𝗡𝗥)\n━━━━━━━━━━━━━━━━━━━━\n\n📌 <b>𝗜𝗻𝘀𝘁𝗿𝘂𝗰𝘁𝗶𝗼𝗻𝘀:</b>\n1️⃣ Scan the QR image above using any UPI App.\n2️⃣ Enter your desired deposit amount manually and pay.\n3️⃣ Once completed, press the <b>𝗩𝗲𝗿𝗶𝗳𝘆 𝗣𝗮𝘆𝗺𝗲𝗻𝘁</b> button.\n\n🆔 <b>𝗢𝗿𝗱𝗲𝗿 𝗜𝗗:</b> <code>{order_id}</code>"
                        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 𝗩𝗲𝗿𝗶𝗳𝘆 𝗣𝗮𝘆𝗺𝗲𝗻𝘁", callback_data=f"v_inr:{order_id}", style="success")]])
                        await callback.message.delete()
                        await callback.message.answer_photo(photo=qr_url, caption=text, parse_mode="HTML", reply_markup=kb)
                        await callback.answer()
                        return
        except Exception:
            pass
    await callback.answer("❌ Payment Gateway error. Contact admin.", show_alert=True)

@dp.callback_query(F.data.startswith("v_inr:"))
async def verify_inr_gate(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    verify_url = f"https://fampay.anujbots.xyz/verify.php?order_id={order_id}&api_key={FAMPAY_API_KEY}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(verify_url) as resp:
                res_data = await resp.json()
                if res_data.get("status") == "success":
                    amount = float(res_data["data"]["amount"])
                    profile = fetch_user_record(callback.from_user.id, callback.from_user.full_name)
                    profile["balance"] += amount
                    _, timestamp = get_current_time_matrix()
                    profile["order_history"].append(f"💳 Deposited INR: +₹{amount} | Date: {timestamp}")
                    await callback.message.delete()
                    await callback.message.answer("🎉 Payment successfully verified! Money added to your wallet.")
                    text, kb = generate_main_menu_payload(callback.from_user.id, callback.from_user.full_name)
                    await unified_render_frame(callback, text, kb)
                    return
        except Exception:
            pass
            
    await callback.message.delete()
    await callback.message.answer("⚠️ You haven't sent the money yet. Verification incomplete!")
    text, kb = generate_main_menu_payload(callback.from_user.id, callback.from_user.full_name)
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "dep_usdt_gate")
async def dep_usdt_gate(callback: CallbackQuery):
    text = """━━━━━━━━━━━━━━━━━━━━
💳 𝗕𝗶𝗻𝗮𝗻𝗰𝗲 𝗣𝗮𝘆𝗺𝗲𝗻𝘁
━━━━━━━━━━━━━━━━━━━━

• <i>Please complete your payment using the Binance ID below!</i> •

👤 <b>Binance NAME:</b> Apex GMR
🆔 <b>Binance ID:</b> <code>1174850757</code>

<b>USDT BEP20 Address:</b> <code>0x9a4f2b1de6cb3fa871b2a39485717e089aa2bcee</code>
<b>USDT TRC20 Address:</b> <code>TWs7VRM4XWsTdv93ZBcdKedpY2pQxNdkWq</code>
<b>USDT ERC20 Address:</b> <code>0x9a4f2b1de6cb3fa871b2a39485717e089aa2bcee</code>
<b>USDT POLYGON:</b> <code>0x0fbe30d1450a194da46d99645e3aa9f82e98a9e8</code>

💰 <b>Balance Convert:</b> 1$ = ₹87

━━━━━━━━━━━━━━━━━━━━
📌 <b>Instructions:</b>
1️⃣ Open your Binance App
2️⃣ Send the payment to the Binance ID above
3️⃣ After successful payment, copy the order ID / transaction ID
4️⃣ Paste the order ID / transaction ID here.
5️⃣ Then send your USDT amount. Example: $1
━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Important:</b>
• <i>If you try to verify with the wrong order ID/transaction ID, you will be banned.</i>"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚡ Submit Transaction Details", callback_data="submit_usdt_proof", style="success")]])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "submit_usdt_proof")
async def submit_usdt_proof(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📝 𝘗𝘭𝘦𝘢𝘴𝘦 𝘴𝘦𝘯𝘥 𝘺𝘰𝘶𝘳 𝘉𝘪𝘯𝘢𝘯𝘤𝘦 / 𝘜𝘚𝘋𝘛 𝘖𝘳𝘥𝘦𝘳 𝘐𝘋 𝘰𝘳 𝘛𝘳𝘢𝘯𝘴𝘢𝘤𝘵𝘪𝘰𝘯 𝘐𝘋:")
    await state.set_state(BotStates.waiting_for_usdt_tx)

@dp.message(BotStates.waiting_for_usdt_tx)
async def process_usdt_tx(message: Message, state: FSMContext):
    await state.update_data(tx_id=message.text)
    await message.answer("💰 𝘕𝘰𝘸 𝘴𝘦𝘯𝘥 𝘺𝘰𝘶𝘳 𝘦𝘹𝘢𝘤𝘵 𝘜𝘚𝘋𝘛 𝘢𝘮𝘰𝘶𝘯𝘵 𝘥𝘦𝘱𝘰𝘴𝘪𝘵𝘦𝘥 (𝘦.𝘨., 10):")
    await state.set_state(BotStates.waiting_for_usdt_amount)

@dp.message(BotStates.waiting_for_usdt_amount)
async def process_usdt_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("❌ <i>Invalid amount. Enter numbers only.</i>")
        return
        
    data = await state.get_data()
    await state.clear()
    calc_inr = amount * 87.0
    await message.answer("⏳ 𝘠𝘰𝘶𝘳 𝘥𝘦𝘱𝘰𝘴𝘪𝘵 𝘳𝘦𝘲𝘶𝘦𝘴𝘵 𝘩𝘢𝘴 𝘣𝘦𝘦𝘯 𝘴𝘶𝘣𝘮𝘪𝘵𝘵𝘦𝘥 𝘵𝘰 𝘵𝘩𝘦 𝘈𝘥𝘮𝘪𝘯 𝘧𝘰𝘳 𝘷𝘦𝘳𝘪𝘧𝘪𝘤𝘢𝘵𝘪𝘰𝘯. 𝘗𝘭𝘦𝘢𝘴𝘦 𝘸𝘢𝘪𝘵 𝘸𝘩𝘪𝘭𝘦 𝘺𝘰𝘶𝘳 𝘱𝘢𝘺𝘮𝘦𝘯𝘵 𝘪𝘴 𝘳𝘦𝘷𝘪𝘦𝘸𝘦𝘥.")
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"adm_v_usdt:approve:{message.from_user.id}:{calc_inr}", style="success"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"adm_v_usdt:reject:{message.from_user.id}:0", style="danger")
        ]
    ])
    
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"⚠️ <b>𝗡𝗘𝗪 𝗨𝗦𝗗𝗧 𝗗𝗘𝗣𝗢𝗦𝗜𝗧 𝗥𝗘𝗤𝗨𝗘𝗦𝗧</b>\n\n👤 <b>User:</b> {message.from_user.full_name} (<code>{message.from_user.id}</code>)\n🆔 <b>TX ID:</b> <code>{data['tx_id']}</code>\n💰 <b>USDT:</b> ${amount}\n📈 <b>Estimated INR:</b> ₹{calc_inr:.2f}",
        parse_mode="HTML",
        reply_markup=admin_kb
    )

@dp.callback_query(F.data.startswith("adm_v_usdt:"))
async def admin_verify_usdt(callback: CallbackQuery):
    _, action, uid, inr_val = callback.data.split(":")
    uid = int(uid)
    inr_val = float(inr_val)
    
    if action == "approve":
        profile = fetch_user_record(uid, "User")
        profile["balance"] += inr_val
        _, timestamp = get_current_time_matrix()
        profile["order_history"].append(f"🟢 Added USDT (Converted): +₹{inr_val} | Date: {timestamp}")
        try:
            await bot.send_message(chat_id=uid, text=f"🎉 <b>𝗨𝗦𝗗𝗧 𝗗𝗲𝗽𝗼𝘀𝗶𝘁 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱!</b>\n\n₹{inr_val:.2f} has been added successfully to your wallet.", parse_mode="HTML")
        except Exception: pass
        await callback.message.edit_text(f"✅ Approved deposit for user <code>{uid}</code>.", parse_mode="HTML")
    else:
        try:
            await bot.send_message(chat_id=uid, text="❌ <i>Your USDT deposit proof was rejected by the administrator.</i>", parse_mode="HTML")
        except Exception: pass
        await callback.message.edit_text(f"❌ Rejected deposit for user <code>{uid}</code>.", parse_mode="HTML")
    await callback.answer()

# --- USER TRANSACTION HISTORY & ORDERS ---
@dp.callback_query(F.data == "root_tx_history")
async def view_tx_history(callback: CallbackQuery):
    profile = fetch_user_record(callback.from_user.id, callback.from_user.full_name)
    history = profile["order_history"]
    text = "━━━━━━━━━━━━━━━━━━━━\n💳 𝗧𝗥𝗔𝗡𝗦𝗔𝗖𝗧𝗜𝗢𝗡 𝗛𝗶𝘀𝘁𝗼𝗿𝘆\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not history:
        text += "<i>No records found.</i>"
    else:
        text += "\n".join(history[-10:])
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Clear Logs", callback_data="clear_tx_logs", style="danger")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="root_deposit", style="primary")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "clear_tx_logs")
async def clear_tx_logs(callback: CallbackQuery):
    profile = fetch_user_record(callback.from_user.id, callback.from_user.full_name)
    profile["order_history"] = []
    await callback.answer("Logs cleared successfully!")
    await view_tx_history(callback)

@dp.callback_query(F.data == "root_orders_history")
async def view_orders_history(callback: CallbackQuery):
    profile = fetch_user_record(callback.from_user.id, callback.from_user.full_name)
    history = profile["order_history"]
    text = "━━━━━━━━━━━━━━━━━━━━\n📦 𝗬𝗢𝗨𝗥 𝗞𝗘𝗬𝗦 𝗛𝗜𝗦𝗧𝗢𝗥𝗬\n━━━━━━━━━━━━━━━━━━━━\n\n"
    keys_bought = [item for item in history if "Key:" in item or "Keys" in item]
    if not keys_bought:
        text += "<i>No key purchase records found.</i>"
    else:
        text += "\n\n".join(keys_bought[-5:])
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Clear History", callback_data="clear_order_logs", style="danger")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="go_home", style="primary")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "clear_order_logs")
async def clear_order_logs(callback: CallbackQuery):
    profile = fetch_user_record(callback.from_user.id, callback.from_user.full_name)
    profile["order_history"] = [item for item in profile["order_history"] if "Key:" not in item and "Keys" not in item]
    await callback.answer("Order history refreshed!")
    await view_orders_history(callback)

# =====================================================================
#                          USER: STOCK & DOWNLOAD
# =====================================================================
@dp.callback_query(F.data == "root_stock_view")
async def stock_root(callback: CallbackQuery):
    text = "━━━━━━━━━━━━━━━━━━━━\n📊 𝗦𝗧𝗢𝗖𝗞 𝗟𝗜𝗩𝗘 𝗠𝗢𝗡𝗜𝗧𝗢𝗥\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Select Injector ecosystem to check live stock availability:</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐍 Snake Stock", callback_data="stock_inj:snake", style="primary")],
        [InlineKeyboardButton(text="🕹️ Kos Stock", callback_data="stock_inj:kos", style="primary")],
        [InlineKeyboardButton(text="🎯 Aim Assist Stock", callback_data="stock_inj:aim", style="primary")],
        [InlineKeyboardButton(text="👾 Drip Key Stock", callback_data="stock_inj:drip", style="primary")],
        [InlineKeyboardButton(text="🔥 Br Mod Stock", callback_data="stock_inj:brmod", style="primary")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="go_home", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("stock_inj:"))
async def stock_game_view(callback: CallbackQuery):
    inj = callback.data.split(":")[1]
    text = f"━━━━━━━━━━━━━━━━━━━━\n📊 𝗟𝗜𝗩𝗘 𝗦𝗧𝗢𝗖𝗞 ({inj.upper()})\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for game in GAMES_MATRIX[inj]:
        text += f"🎮 <b>{game}:</b>\n"
        if inj == "snake": durations = ["3 Days", "10 Days", "30 Days", "90 Days"]
        elif inj == "kos": durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
        elif inj == "aim": durations = ["3 Days", "7 Days", "30 Days", "90 Days"]
        elif inj == "drip" and game == "⚡Free Fire": durations = ["1 Days", "3 Days", "7 Days", "15 Days", "30 Days"]
        elif inj == "drip" and game == "🎱8 Ball": durations = ["1 Days", "7 Days", "30 Days"]
        elif inj == "brmod" and game == "📱Br Mod (FF)": durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
        elif inj == "brmod" and game == "💻Br Mod (FF)": durations = ["1 Days", "10 Days", "30 Days"]
        else: durations = ["1 Days", "7 Days", "30 Days"]
        
        for d in durations:
            count = len(db_keys.get(inj, {}).get(game, {}).get(d, []))
            text += f"  ├ ⛅ {d}: {count} Left\n"
        text += "\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="root_stock_view", style="danger")]])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "root_download")
async def download_root(callback: CallbackQuery):
    text = "━━━━━━━━━━━━━━━━━━━━\n📥 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗 𝗙𝗜𝗟𝗘𝗦\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Download latest application updates below:</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗃️ 𝗦𝗻𝗮𝗸𝗲 𝗙𝗶𝗹𝗲", callback_data="dl:snake_file", style="primary"),
            InlineKeyboardButton(text="🗃️ 𝗞𝗼𝘀 𝗙𝗶𝗹𝗲", callback_data="dl:kos_file", style="primary")
        ],
        [
            InlineKeyboardButton(text="🗃️ 𝗗𝗿𝗶𝗽 𝗙𝗙", callback_data="dl:drip_ff", style="primary"),
            InlineKeyboardButton(text="🗃️ 𝗗𝗿𝗶𝗽 𝟴𝗕𝗣", callback_data="dl:drip_8bp", style="primary")
        ],
        [
            InlineKeyboardButton(text="🗃️ 𝗕𝗿 𝗺𝗼𝗱 𝗠𝗼𝗯𝗶𝗹𝗲", callback_data="dl:br_mobile", style="primary"),
            InlineKeyboardButton(text="🗃️ 𝗕𝗿 𝗺𝗼𝗱 𝗣𝗖", callback_data="dl:br_pc", style="primary")
        ],
        [
            InlineKeyboardButton(text="🗃️ 𝗔𝗶𝗺 𝗖𝗮𝗿𝗿𝗼𝗺", callback_data="dl:aim_carrom", style="primary"),
            InlineKeyboardButton(text="🗃️ 𝗔𝗸 𝗟𝗲𝗼𝗱𝗮𝗿", callback_data="dl:ak_leodar", style="primary")
        ],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="go_home", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("dl:"))
async def process_download_execute(callback: CallbackQuery):
    fid = callback.data.split(":")[1]
    fdata = db_files.get(fid)
    if not fdata:
        await callback.answer("❌ File not updated by Administrator yet.", show_alert=True)
        return
        
    await callback.message.reply_document(
        document=fdata["file_id"],
        caption=f"📦 <b>𝗙𝗶𝗹𝗲:</b> {fid.replace('_',' ').upper()}\n⚙️ <b>𝗩𝗲𝗿𝘀𝗶𝗼𝗻:</b> {fdata['version']}\n⏰ <b>𝗨𝗽𝗱𝗮𝘁𝗲𝗱:</b> {fdata['time']}",
        parse_mode="HTML"
    )
    await callback.answer()

# =====================================================================
#                          ADMIN CONTROL PANEL
# =====================================================================
@dp.callback_query(F.data == "admin_root")
async def admin_root(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    text = "━━━━━━━━━━━━━━━━━━━━\n⚙️ 𝗔𝗗𝗠𝗜𝗡 𝗣𝗔𝗡𝗘𝗟 𝗠𝗘𝗡𝗨\n━━━━━━━━━━━━━━━━━━━━\n\n<i>Administrative management command center:</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 𝗔𝗱𝗱 𝗡𝗲𝘄 𝗞𝗲𝘆", callback_data="adm_add_key_root", style="success")],
        [
            InlineKeyboardButton(text="💰 𝗖𝗵𝗮𝗻𝗴𝗲 𝗣𝗿𝗶𝗰𝗲", callback_data="adm_price_root", style="primary"),
            InlineKeyboardButton(text="➕ 𝗠𝗮𝗻𝗮𝗴𝗲 𝗕𝗮𝗹𝗮𝗻𝗰𝗲", callback_data="adm_manage_bal", style="primary")
        ],
        [
            InlineKeyboardButton(text="🔍 𝗙𝗶𝗻𝗱 𝗨𝘀𝗲𝗿", callback_data="adm_find_user", style="primary"),
            InlineKeyboardButton(text="👥 𝗠𝗮𝗻𝗮𝗴𝗲 𝗥𝗲𝘀𝗲𝗹𝗹𝗲𝗿", callback_data="adm_reseller_root", style="primary")
        ],
        [
            InlineKeyboardButton(text="📢 𝗕𝗿𝗼𝗮𝗱𝗰𝗮𝘀𝘁", callback_data="adm_broadcast", style="primary"),
            InlineKeyboardButton(text="🗃️ 𝗖𝗵𝗮𝗻𝗴𝗲 𝗙𝗶𝗹𝗲", callback_data="adm_change_file_root", style="primary")
        ],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="go_home", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "adm_manage_bal")
async def adm_manage_bal_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await callback.message.answer("📝 𝘗𝘭𝘦𝘢𝘴𝘦 𝘴𝘦𝘯𝘥 𝘵𝘩𝘦 𝘛𝘦𝘭𝘦𝘨𝘳𝘢𝘮 𝘜𝘴𝘦𝘳 𝘐𝘋 𝘰𝘧 𝘵𝘩𝘦 𝘶𝘴𝘦𝘳 𝘸𝘩𝘰𝘴𝘦 𝘣𝘢𝘭𝘢𝘯𝘤𝘦 𝘺𝘰𝘶 𝘸𝘢𝘯𝘵 𝘵𝘰 𝘮𝘰𝘥𝘪𝘧𝘺:", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_manage_bal_uid)

@dp.message(BotStates.waiting_for_manage_bal_uid)
async def adm_manage_bal_uid_received(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        target_uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ 𝘐𝘋 𝘮𝘶𝘴𝘵 𝘤𝘰𝘯𝘵𝘢𝘪𝘯 𝘰𝘯𝘭𝘺 𝘯𝘶𝘮𝘣𝘦𝘳𝘴. 𝘗𝘭𝘦𝘢𝘴𝘦 𝘴𝘦𝘯𝘥 𝘢 𝘷𝘢𝘭𝘪𝘥 𝘛𝘦𝘭𝘦𝘨𝘳𝘢𝘮 𝘜𝘴𝘦𝘳 𝘐𝘋 𝘢𝘨𝘢𝘪𝘯:", parse_mode="HTML")
        return
        
    profile = db_users.get(target_uid)
    username_display = f"@{profile['username']}" if profile and profile.get("username") else f"User ({target_uid})"
    
    await state.update_data(target_uid=target_uid, username_display=username_display)
    await message.answer(f"💰𝘏𝘰𝘸 𝘮𝘶𝘤𝘩 𝘸𝘰𝘶𝘭𝘥 𝘺𝘰𝘶 𝘭𝘪𝘬𝘦 𝘵𝘰 𝘢𝘥𝘥 𝘰𝘳 𝘴𝘶𝘣𝘵𝘳𝘢𝘤𝘵 𝘧𝘳𝘰𝘮 {username_display}'𝘴 𝘸𝘢𝘭𝘭𝘦𝘵?𝘚𝘦𝘯𝘥 𝘢 𝘱𝘰𝘴𝘪𝘵𝘪𝘷𝘦 𝘯𝘶𝘮𝘣𝘦𝘳 (𝘦.𝘨. <code>100</code>) 𝘵𝘰 𝘢𝘥𝘥 𝘣𝘢𝘭𝘢𝘯𝘤𝘦, 𝘰𝘳 𝘢 𝘯𝘦𝘨𝘢𝘵𝘪𝘷𝘦 𝘯𝘶𝘮𝘣𝘦𝘳 (𝘦.𝘨. <code>-50</code>) 𝘵𝘰 𝘥𝘦𝘥𝘶𝘤𝘵 𝘣𝘢𝘭𝘢𝘯𝘤𝘦.", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_manage_bal_amount)

@dp.message(BotStates.waiting_for_manage_bal_amount)
async def adm_manage_bal_amount_received(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌𝘗𝘭𝘦𝘢𝘴𝘦 𝘴𝘦𝘯𝘥 𝘢 𝘷𝘢𝘭𝘪𝘥 𝘯𝘶𝘮𝘦𝘳𝘪𝘤 𝘢𝘮𝘰𝘶𝘯𝘵.", parse_mode="HTML")
        return
        
    data = await state.get_data()
    target_uid = data["target_uid"]
    username_display = data["username_display"]
    await state.clear()
    
    profile = fetch_user_record(target_uid, None)
    if amount >= 0:
        profile["balance"] += amount
        action_text = f"credited ₹{amount}"
        log_text = f"🟢 Added by Admin: +₹{amount}"
    else:
        profile["balance"] = max(0.0, profile["balance"] + amount)
        action_text = f"debited ₹{abs(amount)}"
        log_text = f"🔴 Subtracted by Admin: -₹{abs(amount)}"
        
    _, timestamp = get_current_time_matrix()
    profile["order_history"].append(f"{log_text} | Date: {timestamp}")
    
    await message.answer(f"✅ Successfully {action_text} to {username_display}! New Balance: ₹{profile['balance']:.2f}")
    try:
        await bot.send_message(chat_id=target_uid, text=f"💰 Admin {action_text} to your wallet matrix balance!")
    except Exception:
        pass
        
    text, kb = generate_main_menu_payload(ADMIN_ID, message.from_user.full_name)
    await unified_render_frame(message, text, kb)

@dp.callback_query(F.data == "adm_find_user")
async def adm_find_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.answer()
    await callback.message.answer("🔍𝘗𝘭𝘦𝘢𝘴𝘦 𝘴𝘦𝘯𝘥 𝘵𝘩𝘦 𝘛𝘦𝘭𝘦𝘨𝘳𝘢𝘮 𝘜𝘴𝘦𝘳 𝘐𝘋 𝘰𝘧 𝘵𝘩𝘦 𝘶𝘴𝘦𝘳 𝘺𝘰𝘶 𝘸𝘢𝘯𝘵 𝘵𝘰 𝘷𝘪𝘦𝘸:", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_find_user_uid)

@dp.message(BotStates.waiting_for_find_user_uid)
async def adm_process_find_user(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        target_uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌𝘗𝘭𝘦𝘢𝘴𝘦 𝘴𝘦𝘯𝘥 𝘢 𝘷𝘢𝘭𝘪𝘥 𝘯𝘶𝘮𝘦𝘳𝘪𝘤 𝘛𝘦𝘭𝘦𝘨𝘳𝘢𝘮 𝘜𝘴𝘦𝘳 𝘐𝘋.", parse_mode="HTML")
        return
        
    await state.clear()
    if target_uid in db_users:
        p = db_users[target_uid]
        username_str = f"@{p['username']}" if p.get("username") else "Not Set"
        history_snippet = "\n".join(p['order_history'][-3:]) if p['order_history'] else "No transaction history recorded."
        
        info_text = f"""━━━━━━━━━━━━━━━━━━━━
🔍 𝗨𝗦𝗘𝗥 𝗙𝗢𝗨𝗡𝗗 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘
━━━━━━━━━━━━━━━━━━━━

👤 <i>𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲:</i> {username_str}
🆔 <i>𝗨𝘀𝗲𝗿 𝗜𝗗:</i> <code>{target_uid}</code>
💰 <i><b>𝗕𝗮𝗹𝗮𝗻𝗰𝗲:</b></i> ₹{p['balance']:.2f}
🎖️ <i>𝗥𝗼𝗹𝗲 𝗦𝘁𝗮𝘁𝘂𝘀:</i> {p['role']}
🛒 <i><b>𝗧𝗼𝘁𝗮𝗹 𝗢𝗿𝗱𝗲𝗿𝘀:</b></i> {p['total_orders']}
⏱️ <i>𝗟𝗮𝘀𝘁 𝗣𝘂𝗿𝗰𝗵𝗮𝘀𝗲:</i> {p['last_purchase']}

📋 <i><b>Recent Activity Logs:</b></i>
{history_snippet}
━━━━━━━━━━━━━━━━━━━━"""
    else:
        info_text = f"❌ <i>User map ID <code>{target_uid}</code> data structure was not found inside the active framework storage.</i>"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏎ Admin Menu", callback_data="admin_root", style="danger")]])
    await message.answer(info_text, parse_mode="HTML", reply_markup=kb)

# --- ADMIN: ADD KEY BACKEND ---
@dp.callback_query(F.data == "adm_add_key_root")
async def adm_add_key_root(callback: CallbackQuery):
    text = "🔑 [𝗔𝗗𝗠𝗜𝗡] Select target injector client to input licenses:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐍 Snake Key", callback_data="adm_addk_inj:snake", style="primary")],
        [InlineKeyboardButton(text="🕹️ Kos Key", callback_data="adm_addk_inj:kos", style="primary")],
        [InlineKeyboardButton(text="🎯 Aim Assist", callback_data="adm_addk_inj:aim", style="primary")],
        [InlineKeyboardButton(text="👾 Drip Key", callback_data="adm_addk_inj:drip", style="primary")],
        [InlineKeyboardButton(text="🔥 Br Mod", callback_data="adm_addk_inj:brmod", style="primary")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="admin_root", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("adm_addk_inj:"))
async def adm_add_key_game(callback: CallbackQuery):
    inj = callback.data.split(":")[1]
    kb = []
    for g in GAMES_MATRIX[inj]:
        kb.append([InlineKeyboardButton(text=f"{g}", callback_data=f"adm_addk_gam:{inj}:{g}", style="primary")])
    kb.append([InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="adm_add_key_root", style="danger")])
    await unified_render_frame(callback, f"🔑 Select Game for {inj.upper()}:", InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_addk_gam:"))
async def adm_add_key_dur(callback: CallbackQuery):
    _, inj, game = callback.data.split(":")
    
    if inj == "snake": durations = ["3 Days", "10 Days", "30 Days", "90 Days"]
    elif inj == "kos": durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "aim": durations = ["3 Days", "7 Days", "30 Days", "90 Days"]
    elif inj == "drip" and game == "⚡Free Fire": durations = ["1 Days", "3 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "drip" and game == "🎱8 Ball": durations = ["1 Days", "7 Days", "30 Days"]
    elif inj == "brmod" and game == "📱Br Mod (FF)": durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "brmod" and game == "💻Br Mod (FF)": durations = ["1 Days", "10 Days", "30 Days"]
    else: durations = ["1 Days", "7 Days", "30 Days"]

    kb = []
    for d in durations:
        kb.append([InlineKeyboardButton(text=f"⛅ {d}", callback_data=f"adm_addk_run:{inj}:{game}:{d}", style="primary")])
    kb.append([InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data=f"adm_addk_inj:{inj}", style="danger")])
    await unified_render_frame(callback, f"🔑 Select plan pack duration:", InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_addk_run:"))
async def adm_add_key_trigger(callback: CallbackQuery, state: FSMContext):
    _, inj, game, dur = callback.data.split(":")
    await callback.answer()
    await callback.message.answer(f"📝 <i>Send your keys for <b>{inj.upper()} - {game} ({dur})</b>.\n⚠️ Paste one key per line!</i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_keys_input)
    await state.update_data(target_addk=(inj, game, dur))

@dp.message(BotStates.waiting_for_keys_input)
async def adm_process_keys_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    inj, game, dur = data["target_addk"]
    await state.clear()
    
    input_keys = [line.strip() for line in message.text.split("\n") if line.strip()]
    if inj not in db_keys: db_keys[inj] = {}
    if game not in db_keys[inj]: db_keys[inj][game] = {}
    if dur not in db_keys[inj][game]: db_keys[inj][game][dur] = []
    
    db_keys[inj][game][dur].extend(input_keys)
    await message.answer(f"✅ Successfully added {len(input_keys)} keys to {inj.upper()} ({game} - {dur}) stock!")
    text, kb = generate_main_menu_payload(ADMIN_ID, message.from_user.full_name)
    await unified_render_frame(message, text, kb)

# --- ADMIN: CHANGE PRICE BACKEND ---
@dp.callback_query(F.data == "adm_price_root")
async def adm_price_root(callback: CallbackQuery):
    text = "💰 【𝗣𝗥𝗜𝗖𝗘 𝗠𝗔𝗡𝗔𝗚𝗘𝗥】 𝘗𝘭𝘦𝘢𝘴𝘦 𝘤𝘩𝘰𝘰𝘴𝘦 𝘵𝘩𝘦 𝘱𝘳𝘪𝘤𝘪𝘯𝘨 𝘵𝘪𝘦𝘳 𝘺𝘰𝘶 𝘸𝘢𝘯𝘵 𝘵𝘰 𝘮𝘢𝘯𝘢𝘨𝘦."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Customer Pricing", callback_data="adm_p_tier:customer", style="primary")],
        [InlineKeyboardButton(text="👥 Reseller Pricing", callback_data="adm_p_tier:reseller", style="primary")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="admin_root", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("adm_p_tier:"))
async def adm_p_inj(callback: CallbackQuery):
    tier = callback.data.split(":")[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐍 Snake Pricing", callback_data=f"adm_pinj:{tier}:snake", style="primary")],
        [InlineKeyboardButton(text="🕹️ Kos Pricing", callback_data=f"adm_pinj:{tier}:kos", style="primary")],
        [InlineKeyboardButton(text="🎯 Aim Pricing", callback_data=f"adm_pinj:{tier}:aim", style="primary")],
        [InlineKeyboardButton(text="👾 Drip Pricing", callback_data=f"adm_pinj:{tier}:drip", style="primary")],
        [InlineKeyboardButton(text="🔥 Br Mod Pricing", callback_data=f"adm_pinj:{tier}:brmod", style="primary")],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="adm_price_root", style="danger")]
    ])
    await unified_render_frame(callback, f"💰 Select Injector for {tier.upper()} tier:", kb)

@dp.callback_query(F.data.startswith("adm_pinj:"))
async def adm_p_game(callback: CallbackQuery):
    _, tier, inj = callback.data.split(":")
    kb = []
    for g in GAMES_MATRIX[inj]:
        kb.append([InlineKeyboardButton(text=f"{g}", callback_data=f"adm_pgam:{tier}:{inj}:{g}", style="primary")])
    kb.append([InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data=f"adm_p_tier:{tier}", style="danger")])
    await unified_render_frame(callback, f"💰 Select Game mapping for {inj.upper()}:", InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_pgam:"))
async def adm_p_dur(callback: CallbackQuery):
    _, tier, inj, game = callback.data.split(":")
    
    if inj == "snake": durations = ["3 Days", "10 Days", "30 Days", "90 Days"]
    elif inj == "kos": durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "aim": durations = ["3 Days", "7 Days", "30 Days", "90 Days"]
    elif inj == "drip" and game == "⚡Free Fire": durations = ["1 Days", "3 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "drip" and game == "🎱8 Ball": durations = ["1 Days", "7 Days", "30 Days"]
    elif inj == "brmod" and game == "📱Br Mod (FF)": durations = ["1 Days", "7 Days", "15 Days", "30 Days"]
    elif inj == "brmod" and game == "💻Br Mod (FF)": durations = ["1 Days", "10 Days", "30 Days"]
    else: durations = ["1 Days", "7 Days", "30 Days"]

    kb = []
    for d in durations:
        kb.append([InlineKeyboardButton(text=f"⛅ {d}", callback_data=f"adm_prun:{tier}:{inj}:{game}:{d}", style="primary")])
    kb.append([InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data=f"adm_pinj:{tier}:{inj}", style="danger")])
    await unified_render_frame(callback, f"💰 Select Duration segment mapping:", InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_prun:"))
async def adm_p_trigger(callback: CallbackQuery, state: FSMContext):
    _, tier, inj, game, dur = callback.data.split(":")
    await callback.answer()
    await callback.message.answer(f"💰 <i>Enter new price matrix for:\n<b>{tier.upper()} -> {inj.upper()} -> {game} ({dur})</b></i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_price_value)
    await state.update_data(target_price=(tier, inj, game, dur))

@dp.message(BotStates.waiting_for_price_value)
async def adm_process_price_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    tier, inj, game, dur = data["target_price"]
    await state.clear()
    
    try:
        new_price = float(message.text.strip())
    except ValueError:
        await message.answer("❌ <i>Numerical validation failed. Process aborted.</i>", parse_mode="HTML")
        return
        
    db_prices[tier][inj][game][dur] = new_price
    await message.answer(f"✅ Price updated successfully to ₹{new_price:.2f}!")
    text, kb = generate_main_menu_payload(ADMIN_ID, message.from_user.full_name)
    await unified_render_frame(message, text, kb)

# --- ADMIN: RESELLER MANAGEMENT ---
@dp.callback_query(F.data == "adm_reseller_root")
async def adm_reseller_root(callback: CallbackQuery):
    text = "👥 [𝗠𝗔𝗡𝗔𝗚𝗘 𝗥𝗘𝗦𝗘𝗟𝗟𝗘𝗥] Administrative peer tier configuration menu:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add Reseller", callback_data="adm_r_add", style="success"),
            InlineKeyboardButton(text="❌ Cancel Reseller", callback_data="adm_r_cancel", style="danger")
        ],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="admin_root", style="primary")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data == "adm_r_add")
async def adm_r_add_trigger(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📝 <i>Send Telegram User ID to promote to Reseller class:</i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_reseller_add)

@dp.message(BotStates.waiting_for_reseller_add)
async def adm_process_reseller_add(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid ID format.")
        return
        
    if uid in db_resellers:
        await message.answer("⚠️ This user is already structured inside the Reseller database framework.")
        return
        
    db_resellers.append(uid)
    fetch_user_record(uid, None) 
    await message.answer(f"✅ User <code>{uid}</code> has been updated to Reseller status safely.", parse_mode="HTML")

@dp.callback_query(F.data == "adm_r_cancel")
async def adm_r_cancel_trigger(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📝 <i>Send Telegram User ID to degrade back to Customer status:</i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_reseller_cancel)

@dp.message(BotStates.waiting_for_reseller_cancel)
async def adm_process_reseller_cancel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid ID.")
        return
        
    if uid not in db_resellers:
        await message.answer("⚠️ User is not a structured Reseller.")
        return
        
    db_resellers.remove(uid)
    fetch_user_record(uid, None)
    await message.answer(f"✅ User <code>{uid}</code> demoted safely to basic Customer profile.", parse_mode="HTML")

# --- ADMIN: CHANGE DOWNLOADABLE FILE ---
@dp.callback_query(F.data == "adm_change_file_root")
async def adm_change_file_root(callback: CallbackQuery):
    text = "🗃️ [𝗙𝗜𝗟𝗘 𝗠𝗔𝗡𝗔𝗚𝗘𝗥] Select virtual file terminal button asset node to overwrite:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🐍 Snake File", callback_data="adm_chf:snake_file", style="primary"),
            InlineKeyboardButton(text="🗃️ Kos File", callback_data="adm_chf:kos_file", style="primary")
        ],
        [
            InlineKeyboardButton(text="🗃️ Drip FF", callback_data="adm_chf:drip_ff", style="primary"),
            InlineKeyboardButton(text="🗃️ Drip 8BP", callback_data="adm_chf:drip_8bp", style="primary")
        ],
        [
            InlineKeyboardButton(text="🗃️ Br Mobile", callback_data="adm_chf:br_mobile", style="primary"),
            InlineKeyboardButton(text="🗃️ Br PC", callback_data="adm_chf:br_pc", style="primary")
        ],
        [
            InlineKeyboardButton(text="🗃️ Aim Carrom", callback_data="adm_chf:aim_carrom", style="primary"),
            InlineKeyboardButton(text="🗃️ Ak Leodar", callback_data="adm_chf:ak_leodar", style="primary")
        ],
        [InlineKeyboardButton(text="⏎ 𝗕𝗮𝗰𝗸", callback_data="admin_root", style="danger")]
    ])
    await unified_render_frame(callback, text, kb)

@dp.callback_query(F.data.startswith("adm_chf:"))
async def adm_change_file_trigger(callback: CallbackQuery, state: FSMContext):
    fid = callback.data.split(":")[1]
    await callback.answer()
    await callback.message.answer(f"📥 <i>Please send/upload the NEW file binary document for <b>{fid.upper()}</b>:</i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_update_file)
    await state.update_data(target_fid=fid)

@dp.message(BotStates.waiting_for_update_file)
async def adm_process_file_binary(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.document:
        await message.answer("❌ File structural verification failed. Please send a valid document file asset.")
        return
    await state.update_data(file_id=message.document.file_id)
    await message.answer("📝 <i>Now send the version name/tag for this build string (e.g., v1.4.2):</i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_update_version)

@dp.message(BotStates.waiting_for_update_version)
async def adm_process_file_version(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    fid = data["target_fid"]
    file_id = data["file_id"]
    await state.clear()
    
    _, timestamp = get_current_time_matrix()
    db_files[fid] = {
        "file_id": file_id,
        "version": message.text.strip(),
        "time": timestamp
    }
    await message.answer(f"✅ File asset <b>{fid.upper()}</b> successfully updated globally inside storage framework!")

# --- ADMIN: BROADCAST SYSTEM ---
@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_trigger(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📢 <i>Send the message text you want to broadcast to ALL bot users globally:</i>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_broadcast_msg)

@dp.message(BotStates.waiting_for_broadcast_msg)
async def adm_process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    bc_text = message.text
    count = 0
    for target_uid in db_users.keys():
        try:
            await bot.send_message(chat_id=target_uid, text=f"📢 <b>𝗚𝗟𝗢𝗕𝗔𝗟 𝗔𝗡𝗡𝗢𝗨𝗡𝗖𝗘𝗠𝗘𝗡𝗧</b>\n\n<i>{bc_text}</i>", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05) 
        except Exception:
            pass
    await message.answer(f"✅ Broadcast transmission completed successfully! Dispatched to {count} active user sessions.")

# --- CORE MAIN LOOP TRIGGER RUNTIME ---
async def main():
    logger.info("Initializing Application Polling Subsystem Context under Bot API 9.4 Parameters...")
    
    # Railway Port Binding Protection
    port = int(os.environ.get("PORT", 8080))
    async def dummy_server():
        try:
            server = await asyncio.start_server(lambda r, w: None, '0.0.0.0', port)
            async with server:
                await server.serve_forever()
        except Exception as e:
            logger.warning(f"Dummy port binding server error: {e}")

    # রান পোলিং এবং ডমি সার্ভার একসাথে ব্যাকগ্রাউন্ডে চলবে
    await asyncio.gather(
        dp.start_polling(bot),
        dummy_server()
    )

if __name__ == '__main__':
    asyncio.run(main())