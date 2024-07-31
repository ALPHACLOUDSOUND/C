import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler, filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Replace with your group ID where players should be verified
VERIFY_GROUP_ID = -1002070732383 # Example group ID (make sure it's a negative number for group IDs)
BOT_OWNER_ID = 7049798779
GROUP_INVITE_LINK = "https://t.me/tamilchattingu"  # Replace with your group's invite link

# Dictionary to hold game state and scores
game_data = {}

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Welcome to Hand Cricket! Use /join to join the game and /startgame to begin.')

async def join(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Player"

    if chat_id not in game_data:
        game_data[chat_id] = {
            'players': {},
            'scores': {},
            'turn': None,
            'status': 'waiting',  # Can be 'waiting', 'playing', 'ended'
            'scoreboard_message_id': None
        }

    if user_id in game_data[chat_id]['players']:
        await update.message.reply_text('You are already in the game.')
        return

    keyboard = [
        [InlineKeyboardButton("Join Group", url=GROUP_INVITE_LINK)],
        [InlineKeyboardButton("I have joined the group", callback_data=f"verify_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Please join the verification group and then click the button below.', reply_markup=reply_markup)

async def verify_join(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])

    if not await is_user_in_group(user_id, context):
        await query.edit_message_text('You are not a member of the verification group. Please join the group and try again.')
        return

    chat_id = query.message.chat_id
    username = query.from_user.username or "Player"

    game_data[chat_id]['players'][user_id] = username
    game_data[chat_id]['scores'][user_id] = 0

    await query.edit_message_text(f'{username} has joined the game!')

async def is_user_in_group(user_id: int, context: CallbackContext) -> bool:
    try:
        chat_member = await context.bot.get_chat_member(chat_id=VERIFY_GROUP_ID, user_id=user_id)
        return chat_member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.CREATOR]
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        return False

async def start_game(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in game_data or len(game_data[chat_id]['players']) < 2:
        await update.message.reply_text('Need at least two players to start the game.')
        return

    game_data[chat_id]['status'] = 'playing'
    players = list(game_data[chat_id]['players'].keys())
    game_data[chat_id]['turn'] = players[0]

    await update.message.reply_text(f'Game started! It\'s {game_data[chat_id]["players"][game_data[chat_id]["turn"]]}\'s turn.')

async def ball(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        await update.message.reply_text('No game is currently running or the game has ended.')
        return

    user_id = update.message.from_user.id
    if user_id != game_data[chat_id]['turn']:
        await update.message.reply_text('It\'s not your turn.')
        return

    run = random.randint(0, 6)
    game_data[chat_id]['scores'][user_id] += run

    # Switch turn
    players = list(game_data[chat_id]['players'].keys())
    current_index = players.index(user_id)
    next_index = (current_index + 1) % len(players)
    game_data[chat_id]['turn'] = players[next_index]

    await update.message.reply_text(f'You scored {run} runs! It\'s now {game_data[chat_id]["players"][game_data[chat_id]["turn"]]}\'s turn.')

    # Update and pin scoreboard
    await update_scoreboard(update, context, chat_id)

async def update_scoreboard(update: Update, context: CallbackContext, chat_id: int) -> None:
    scores = game_data[chat_id]['scores']
    scoreboard = 'Scoreboard:\n'
    for user_id, score in scores.items():
        username = game_data[chat_id]['players'][user_id]
        scoreboard += f'{username}: {score}\n'

    # Delete previous scoreboard message if it exists
    if game_data[chat_id]['scoreboard_message_id']:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=game_data[chat_id]['scoreboard_message_id'])
        except Exception as e:
            logger.warning(f'Failed to delete message: {e}')

    # Send new scoreboard and pin it
    message = await context.bot.send_message(chat_id=chat_id, text=scoreboard, parse_mode="MarkdownV2")
    await context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
    game_data[chat_id]['scoreboard_message_id'] = message.message_id

async def end_game(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        await update.message.reply_text('No game is currently running or the game has ended.')
        return

    if user_id not in [BOT_OWNER_ID, *await get_group_admin_ids(context, chat_id)]:
        await update.message.reply_text('Only the bot owner or group admins can end the game.')
        return

    game_data[chat_id]['status'] = 'ended'
    await update.message.reply_text('Game ended.')
    await update_scoreboard(update, context, chat_id)  # Update scoreboard one last time

async def add_score(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        await update.message.reply_text('No game is currently running or the game has ended.')
        return

    if user_id not in [BOT_OWNER_ID, *await get_group_admin_ids(context, chat_id)]:
        await update.message.reply_text('Only the bot owner or group admins can give extra scores.')
        return

    try:
        target_user = int(context.args[0])
        additional_score = int(context.args[1])
        if target_user not in game_data[chat_id]['scores']:
            await update.message.reply_text('Player not found in the game.')
            return

        game_data[chat_id]['scores'][target_user] += additional_score
        await update.message.reply_text(f'Added {additional_score} runs to player {target_user}.')
        await update_scoreboard(update, context, chat_id)
    except (IndexError, ValueError):
        await update.message.reply_text('Usage: /addscore <user_id> <score>')

async def ban_player(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        await update.message.reply_text('No game is currently running or the game has ended.')
        return

    if user_id not in [BOT_OWNER_ID, *await get_group_admin_ids(context, chat_id)]:
        await update.message.reply_text('Only the bot owner or group admins can ban players.')
        return

    try:
        target_user = int(context.args[0])
        if target_user not in game_data[chat_id]['players']:
            await update.message.reply_text('Player not found in the game.')
            return

        del game_data[chat_id]['players'][target_user]
        del game_data[chat_id]['scores'][target_user]
        await update.message.reply_text(f'Player {target_user} has been banned from the game.')
        await update_scoreboard(update, context, chat_id)
    except IndexError:
        await update.message.reply_text('Usage: /ban <user_id>')

async def get_group_admin_ids(context: CallbackContext, chat_id: int) -> list:
    admin_ids = []
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in admins]
    except Exception as e:
        logger.error(f"Error retrieving group admins: {e}")
    return admin_ids

async def handle_message(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Use /start to start and /join to join the game. Use /startgame to begin the game and /ball to play.')

def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("7294713269:AAFwKEXMbLFMwKMDe6likn7NEbKEuLbVtxE").build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("endgame", end_game))
    application.add_handler(CommandHandler("addscore", add_score))
    application.add_handler(CommandHandler("ban", ban_player))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("ball", ball))
    application.add_handler(CallbackQueryHandler(verify_join, pattern=r'^verify_\d+$'))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
