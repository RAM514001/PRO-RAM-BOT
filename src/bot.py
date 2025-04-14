import os
import asyncio
import json
import aiohttp
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Dummy HTTP Server using aiohttp to satisfy Render's port binding requirement
async def handle_root(request):
    return web.Response(text="ProSciffoniBot is running!")

async def start_dummy_server():
    app = web.Application()
    app.add_routes([web.get('/', handle_root)])
    port = int(os.getenv("PORT", 8000))  # Use Render's PORT if available, else fallback to 8000
    print(f"Attempting to start dummy server on port {port}...")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Dummy server successfully started on port {port}")
    # Small delay to ensure Render detects the port
    await asyncio.sleep(5)

# Environment variables
BOT_TOKEN = "7962541121:AAHIfmC8ikd7eQKdAkYV9X8dyjr8OfeLs9E"
HELIUS_API_KEY = "3d72e580-c00c-4e00-ab2b-92f31d94b37a"
HELIUS_WS_URL = f"wss://ws-mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"  # Pump.fun program ID

# Default filters (user-specific filters will override these)
DEFAULT_FILTERS = {
    "min_cost": 0.0000000023,
    "max_cost": 0.006,
    "max_dev_holding": 10.0,  # Max dev holding percentage
    "require_mint_revoked": True,
    "require_freeze_revoked": True,
    "require_links": True,
    "pools": ["pumpfun"]
}

# Store user-specific filters and subscription status (in-memory for now)
USER_FILTERS = {}
USER_SUBSCRIPTIONS = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Received /start command")
    keyboard = [
        [InlineKeyboardButton("Set Filters ⚙️", callback_data="filters")],
        [InlineKeyboardButton("View Alerts 📩", callback_data="alerts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to ProSciffoniBot! 🚀\n\nI’m a pro-level sniping bot for Pump.fun meme coins. Set your filters and get real-time alerts! 🎯",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    print("Sent welcome message with buttons")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if query.data == "filters":
        print("Set Filters button clicked")
        keyboard = [
            [InlineKeyboardButton("Set Min Cost 💸", callback_data="set_min_cost")],
            [InlineKeyboardButton("Set Max Cost 💰", callback_data="set_max_cost")],
            [InlineKeyboardButton("Set Max Dev Holding 👨‍💻", callback_data="set_max_dev_holding")],
            [InlineKeyboardButton("Toggle Mint Revoked ✅", callback_data="toggle_mint_revoked")],
            [InlineKeyboardButton("Toggle Freeze Revoked ❄️", callback_data="toggle_freeze_revoked")],
            [InlineKeyboardButton("Toggle Require Links 🔗", callback_data="toggle_require_links")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        user_filters = USER_FILTERS.get(chat_id, DEFAULT_FILTERS)
        filter_summary = (
            f"🎯 <b>Current Filter Settings:</b>\n\n"
            f"💸 <b>Min Cost:</b> {user_filters['min_cost']} SOL\n"
            f"💰 <b>Max Cost:</b> {user_filters['max_cost']} SOL\n"
            f"👨‍💻 <b>Max Dev Holding:</b> {user_filters['max_dev_holding']}%\n"
            f"✅ <b>Mint Revoked:</b> {'Yes' if user_filters['require_mint_revoked'] else 'No'}\n"
            f"❄️ <b>Freeze Revoked:</b> {'Yes' if user_filters['require_freeze_revoked'] else 'No'}\n"
            f"🔗 <b>Require Links:</b> {'Yes' if user_filters['require_links'] else 'No'}\n\n"
            f"Select an option to update your filters:"
        )
        await query.edit_message_text(filter_summary, reply_markup=reply_markup, parse_mode="HTML")
    elif query.data == "alerts":
        print("View Alerts button clicked")
        if chat_id in USER_SUBSCRIPTIONS:
            await query.edit_message_text("You are subscribed to meme coin alerts! 📡\n\nUse /unsubscribe to stop receiving alerts.")
        else:
            await query.edit_message_text("You are not subscribed to alerts. 📢\n\nUse /register to start receiving meme coin alerts!")
    elif query.data.startswith("set_"):
        # Handle filter setting inputs
        setting = query.data.replace("set_", "")  # e.g., "min_cost", "max_cost", "max_dev_holding"
        await query.edit_message_text(f"Please enter the {setting.replace('_', ' ')} ({'SOL' if 'cost' in setting else '%'}):")
        context.user_data["setting"] = setting
    elif query.data.startswith("toggle_"):
        # Handle toggle settings
        setting = query.data.replace("toggle_", "")  # e.g., "mint_revoked", "freeze_revoked", "require_links"
        user_filters = USER_FILTERS.get(chat_id, DEFAULT_FILTERS.copy())
        user_filters[f"require_{setting}"] = not user_filters.get(f"require_{setting}", DEFAULT_FILTERS[f"require_{setting}"])
        USER_FILTERS[chat_id] = user_filters
        print(f"Updated {setting} for chat {chat_id}: {user_filters[f'require_{setting}']}")
        # Show updated filters
        keyboard = [
            [InlineKeyboardButton("Set Min Cost 💸", callback_data="set_min_cost")],
            [InlineKeyboardButton("Set Max Cost 💰", callback_data="set_max_cost")],
            [InlineKeyboardButton("Set Max Dev Holding 👨‍💻", callback_data="set_max_dev_holding")],
            [InlineKeyboardButton("Toggle Mint Revoked ✅", callback_data="toggle_mint_revoked")],
            [InlineKeyboardButton("Toggle Freeze Revoked ❄️", callback_data="toggle_freeze_revoked")],
            [InlineKeyboardButton("Toggle Require Links 🔗", callback_data="toggle_require_links")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        filter_summary = (
            f"🎯 <b>Current Filter Settings:</b>\n\n"
            f"💸 <b>Min Cost:</b> {user_filters['min_cost']} SOL\n"
            f"💰 <b>Max Cost:</b> {user_filters['max_cost']} SOL\n"
            f"👨‍💻 <b>Max Dev Holding:</b> {user_filters['max_dev_holding']}%\n"
            f"✅ <b>Mint Revoked:</b> {'Yes' if user_filters['require_mint_revoked'] else 'No'}\n"
            f"❄️ <b>Freeze Revoked:</b> {'Yes' if user_filters['require_freeze_revoked'] else 'No'}\n"
            f"🔗 <b>Require Links:</b> {'Yes' if user_filters['require_links'] else 'No'}\n\n"
            f"Select an option to update your filters:"
        )
        await query.edit_message_text(filter_summary, reply_markup=reply_markup, parse_mode="HTML")

async def handle_filter_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if "setting" not in context.user_data:
        return
    setting = context.user_data["setting"]
    try:
        value = float(update.message.text)
        user_filters = USER_FILTERS.get(chat_id, DEFAULT_FILTERS.copy())
        user_filters[setting] = value
        USER_FILTERS[chat_id] = user_filters
        unit = "SOL" if "cost" in setting else "%"
        print(f"Updated {setting} for chat {chat_id}: {value}")
        await update.message.reply_text(f"{setting.replace('_', ' ').title()} updated to {value} {unit}!")
    except ValueError:
        await update.message.reply_text(f"Please enter a valid number ({'SOL' if 'cost' in setting else '%'}).")
    finally:
        # Show updated filters
        keyboard = [
            [InlineKeyboardButton("Set Min Cost 💸", callback_data="set_min_cost")],
            [InlineKeyboardButton("Set Max Cost 💰", callback_data="set_max_cost")],
            [InlineKeyboardButton("Set Max Dev Holding 👨‍💻", callback_data="set_max_dev_holding")],
            [InlineKeyboardButton("Toggle Mint Revoked ✅", callback_data="toggle_mint_revoked")],
            [InlineKeyboardButton("Toggle Freeze Revoked ❄️", callback_data="toggle_freeze_revoked")],
            [InlineKeyboardButton("Toggle Require Links 🔗", callback_data="toggle_require_links")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        user_filters = USER_FILTERS.get(chat_id, DEFAULT_FILTERS)
        filter_summary = (
            f"🎯 <b>Current Filter Settings:</b>\n\n"
            f"💸 <b>Min Cost:</b> {user_filters['min_cost']} SOL\n"
            f"💰 <b>Max Cost:</b> {user_filters['max_cost']} SOL\n"
            f"👨‍💻 <b>Max Dev Holding:</b> {user_filters['max_dev_holding']}%\n"
            f"✅ <b>Mint Revoked:</b> {'Yes' if user_filters['require_mint_revoked'] else 'No'}\n"
            f"❄️ <b>Freeze Revoked:</b> {'Yes' if user_filters['require_freeze_revoked'] else 'No'}\n"
            f"🔗 <b>Require Links:</b> {'Yes' if user_filters['require_links'] else 'No'}\n\n"
            f"Select an option to update your filters:"
        )
        await update.message.reply_text(filter_summary, reply_markup=reply_markup, parse_mode="HTML")
        del context.user_data["setting"]

async def check_missed_tokens(app, session):
    try:
        print("Checking missed tokens via Helius API...")
        async with session.get(
            f"https://api.helius.xyz/v0/transactions?api-key={HELIUS_API_KEY}",
            params={"programId": PUMP_PROGRAM_ID, "type": "CREATE"}
        ) as resp:
            if resp.status != 200:
                print(f"Helius API error: {resp.status} - {await resp.text()}")
                return
            txs = await resp.json()
            print(f"Found {len(txs)} transactions in missed tokens check.")
            for tx in txs[-5:]:
                coin_data = await parse_pumpfun_data({"params": {"result": tx}}, session)
                if coin_data:
                    for chat_id in USER_SUBSCRIPTIONS:
                        user_filters = USER_FILTERS.get(chat_id, DEFAULT_FILTERS)
                        if apply_filters(coin_data, user_filters):
                            text = format_coin_alert(coin_data)
                            await app.bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                parse_mode="HTML"
                            )
                            print(f"Missed token alert sent to chat {chat_id}: {text}")
                        else:
                            print(f"Coin rejected for chat {chat_id} due to filters.")
                else:
                    print("No coin data matched filters in missed tokens check.")
    except Exception as e:
        print(f"Error checking missed tokens: {e}")

async def detect_meme_coins(app):
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await check_missed_tokens(app, session)
                print(f"Connecting to WebSocket: {HELIUS_WS_URL}")
                async with session.ws_connect(HELIUS_WS_URL, timeout=30) as ws:
                    subscription = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "logsSubscribe",
                        "params": [{"mentions": [PUMP_PROGRAM_ID]}, {"commitment": "confirmed"}]
                    }
                    await ws.send_json(subscription)
                    print("WebSocket subscription sent, waiting for messages...")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if "result" in data:
                                print("Received subscription confirmation.")
                                continue
                            print("Received WebSocket message, parsing data...")
                            coin_data = await parse_pumpfun_data(data, session)
                            if coin_data:
                                for chat_id in USER_SUBSCRIPTIONS:
                                    user_filters = USER_FILTERS.get(chat_id, DEFAULT_FILTERS)
                                    if apply_filters(coin_data, user_filters):
                                        text = format_coin_alert(coin_data)
                                        try:
                                            await app.bot.send_message(
                                                chat_id=chat_id,
                                                text=text,
                                                parse_mode="HTML"
                                            )
                                            print(f"Alert sent to chat {chat_id}: {text}")
                                        except Exception as e:
                                            print(f"Error sending to {chat_id}: {e}")
                                    else:
                                        print(f"Coin rejected for chat {chat_id} due to filters.")
                            else:
                                print("No coin data matched filters in WebSocket message.")
                        await asyncio.sleep(0.1)
        except Exception as e:
            print(f"WebSocket error: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)

async def parse_pumpfun_data(data, session):
    try:
        logs = data.get("params", {}).get("result", {}).get("value", {}).get("logs", [])
        signature = data.get("params", {}).get("result", {}).get("value", {}).get("signature", "unknown_signature")
        for log in logs:
            if "Instruction: Create" in log:
                mint_address = None
                for subsequent_log in logs[logs.index(log):]:
                    if "Program data:" in subsequent_log:
                        parts = subsequent_log.split()
                        if len(parts) > 2:
                            mint_address = parts[-1]
                        break
                if not mint_address:
                    mint_address = "unknown_mint_address"
                    print(f"No mint address found in logs for signature {signature}")
                print(f"Fetching metadata for mint address: {mint_address}")
                async with session.get(
                    f"https://api.helius.xyz/v0/tokens/metadata?api-key={HELIUS_API_KEY}",
                    params={"mintAccounts": [mint_address]}
                ) as resp:
                    if resp.status != 200:
                        print(f"Helius metadata API error: {resp.status} - {await resp.text()}")
                        return None
                    metadata = await resp.json()
                    if metadata and isinstance(metadata, list) and len(metadata) > 0:
                        metadata = metadata[0]
                        # Parse dev_holding as a float (remove '%' if present)
                        dev_holding_str = metadata.get("topHolders", [{}])[0].get("percentage", "0%")
                        dev_holding = float(dev_holding_str.replace("%", "")) if isinstance(dev_holding_str, str) else float(dev_holding_str)
                        coin_data = {
                            "name": metadata.get("name", "Unknown"),
                            "symbol": metadata.get("symbol", "UNK"),
                            "address": mint_address,
                            "liquidity": metadata.get("liquidity", "0 SOL"),
                            "market_cap": metadata.get("marketCap", "$0"),
                            "cost": metadata.get("price", 0.0),
                            "dev_holding": dev_holding,
                            "mint_revoked": metadata.get("mintAuthority", None) is None,
                            "freeze_revoked": metadata.get("freezeAuthority", None) is None,
                            "links": metadata.get("socials", []),
                            "bonding_curve": "linear",
                            "chart_url": f"https://dexscreener.com/solana/{mint_address}"
                        }
                        print(f"Parsed coin data: {coin_data}")
                        return coin_data
        print(f"No relevant logs found for coin creation in signature {signature}.")
        return None
    except Exception as e:
        print(f"Error parsing data: {e}")
        return None

def apply_filters(coin_data, filters):
    if not coin_data:
        return False
    if coin_data["cost"] < filters["min_cost"] or coin_data["cost"] > filters["max_cost"]:
        print(f"Coin rejected: Cost {coin_data['cost']} outside range {filters['min_cost']}-{filters['max_cost']}")
        return False
    if coin_data["dev_holding"] > filters["max_dev_holding"]:
        print(f"Coin rejected: Dev holding {coin_data['dev_holding']}% exceeds max {filters['max_dev_holding']}%")
        return False
    if filters["require_mint_revoked"] and not coin_data["mint_revoked"]:
        print("Coin rejected: Mint not revoked")
        return False
    if filters["require_freeze_revoked"] and not coin_data["freeze_revoked"]:
        print("Coin rejected: Freeze not revoked")
        return False
    if filters["require_links"] and not coin_data["links"]:
        print("Coin rejected: No links provided")
        return False
    print("Coin passed all filters!")
    return True

def format_coin_alert(data):
    return (
        f"🎯 <b>New Meme Coin Snipe: {data['name']} ({data['symbol']})</b> 🎯\n\n"
        f"📍 <b>CA:</b> <code>{data['address']}</code>\n"
        f"💧 <b>Liquidity:</b> {data['liquidity']}\n"
        f"📈 <b>Market Cap:</b> {data['market_cap']}\n"
        f"💸 <b>Cost:</b> {data['cost']} SOL\n"
        f"👨‍💻 <b>Dev Holding:</b> {data['dev_holding']}%\n"
        f"📉 <b>Bonding Curve:</b> {data['bonding_curve']}\n"
        f"✅ <b>Mint Revoked:</b> {'Yes' if data['mint_revoked'] else 'No'}\n"
        f"❄️ <b>Freeze Revoked:</b> {'Yes' if data['freeze_revoked'] else 'No'}\n"
        f"🔗 <b>Links:</b> {' | '.join(data['links']) if data['links'] else 'None'}\n"
        f"📊 <a href='{data['chart_url']}'>View Chart on Dexscreener</a>\n\n"
        f"🚀 Snipe this coin now!"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    USER_SUBSCRIPTIONS.add(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Registered for alerts! 📢\n\nYou will now receive notifications for new meme coins on Pump.fun! 🚀",
        parse_mode="HTML"
    )
    print(f"User registered for alerts, chat ID: {chat_id}")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in USER_SUBSCRIPTIONS:
        USER_SUBSCRIPTIONS.remove(chat_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text="Unsubscribed from alerts. 📢\n\nYou will no longer receive notifications. Use /register to subscribe again!",
            parse_mode="HTML"
        )
        print(f"User unsubscribed, chat ID: {chat_id}")
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="You are not subscribed to alerts. 📢\n\nUse /register to start receiving meme coin alerts!",
            parse_mode="HTML"
        )

async def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Clear any existing webhook to ensure polling works
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("Cleared any existing webhook to avoid conflicts.")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_filter_input))
    
    pr
