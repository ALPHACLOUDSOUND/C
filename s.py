import telegram
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
import random

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# Dictionary to hold game state and scores
game_data = {}

# Replace with your group ID where players should be verified
VERIFY_GROUP_ID = -1002070732383  # Example group ID (make sure it's a negative number for group IDs)
BOT_OWNER_ID = 7049798779

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome to Hand Cricket! Use /join to join the game and /startgame to begin.')

def join(update: Update, context: CallbackContext):
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
        update.message.reply_text('You are already in the game.')
        return

    if not is_user_in_group(update.message.from_user.id):
        update.message.reply_text('You must be a member of the verification group to join the game.')
        return

    game_data[chat_id]['players'][user_id] = username
    game_data[chat_id]['scores'][user_id] = 0

    update.message.reply_text(f'{username} has joined the game!')

def is_user_in_group(user_id):
    try:
        chat_member = context.bot.get_chat_member(chat_id=VERIFY_GROUP_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Error checking user status: {e}")
        return False

def start_game(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id not in game_data or len(game_data[chat_id]['players']) < 2:
        update.message.reply_text('Need at least two players to start the game.')
        return

    game_data[chat_id]['status'] = 'playing'
    players = list(game_data[chat_id]['players'].keys())
    game_data[chat_id]['turn'] = players[0]

    update.message.reply_text(f'Game started! It\'s {game_data[chat_id]["players"][game_data[chat_id]["turn"]]}\'s turn.')

def ball(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        update.message.reply_text('No game is currently running or the game has ended.')
        return

    user_id = update.message.from_user.id
    if user_id != game_data[chat_id]['turn']:
        update.message.reply_text('It\'s not your turn.')
        return

    run = random.randint(0, 6)
    game_data[chat_id]['scores'][user_id] += run

    # Switch turn
    players = list(game_data[chat_id]['players'].keys())
    current_index = players.index(user_id)
    next_index = (current_index + 1) % len(players)
    game_data[chat_id]['turn'] = players[next_index]

    # Update and pin scoreboard
    update_scoreboard(update, chat_id)

def update_scoreboard(update: Update, chat_id):
    scores = game_data[chat_id]['scores']
    scoreboard = 'Scoreboard:\n'
    for user_id, score in scores.items():
        username = game_data[chat_id]['players'][user_id]
        scoreboard += f'{username}: {score}\n'
    
    context = update.message.bot
    # Delete previous scoreboard message if it exists
    if game_data[chat_id]['scoreboard_message_id']:
        try:
            context.delete_message(chat_id=chat_id, message_id=game_data[chat_id]['scoreboard_message_id'])
        except Exception as e:
            logging.warning(f'Failed to delete message: {e}')
    
    # Send new scoreboard and pin it
    message = context.send_message(chat_id=chat_id, text=scoreboard, parse_mode=ParseMode.MARKDOWN_V2)
    context.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
    game_data[chat_id]['scoreboard_message_id'] = message.message_id

def end_game(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        update.message.reply_text('No game is currently running or the game has ended.')
        return

    if user_id not in [BOT_OWNER_ID, *get_group_admin_ids(update.message.chat_id)]:
        update.message.reply_text('Only the bot owner or group admins can end the game.')
        return

    game_data[chat_id]['status'] = 'ended'
    update.message.reply_text('Game ended.')
    update_scoreboard(update, chat_id)  # Update scoreboard one last time

def add_score(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        update.message.reply_text('No game is currently running or the game has ended.')
        return

    if user_id not in [BOT_OWNER_ID, *get_group_admin_ids(update.message.chat_id)]:
        update.message.reply_text('Only the bot owner or group admins can give extra scores.')
        return

    try:
        target_user = int(context.args[0])
        additional_score = int(context.args[1])
        if target_user not in game_data[chat_id]['scores']:
            update.message.reply_text('Player not found in the game.')
            return

        game_data[chat_id]['scores'][target_user] += additional_score
        update.message.reply_text(f'Added {additional_score} runs to player {target_user}.')
        update_scoreboard(update, chat_id)
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /addscore <user_id> <score>')

def ban_player(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        update.message.reply_text('No game is currently running or the game has ended.')
        return

    if user_id not in [BOT_OWNER_ID, *get_group_admin_ids(update.message.chat_id)]:
        update.message.reply_text('Only the bot owner or group admins can ban players.')
        return

    try:
        target_user = int(context.args[0])
        if target_user not in game_data[chat_id]['players']:
            update.message.reply_text('Player not found in the game.')
            return

        del game_data[chat_id]['players'][target_user]
        del game_data[chat_id]['scores'][target_user]
        update.message.reply_text(f'Player {target_user} has been banned from the game.')
        update_scoreboard(update, chat_id)
    except IndexError:
        update.message.reply_text('Usage: /ban <user_id>')

def get_group_admin_ids(chat_id):
    admin_ids = []
    try:
        admins = context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in admins]
    except Exception as e:
        logging.error(f"Error retrieving group admins: {e}")
    return admin_ids

def handle_message(update: Update, context: CallbackContext):
    update.message.reply_text('Use /start to start and /join to join the game. Use /startgame to begin the game and /ball to play.')


def main():
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

    # Start the Bot
    application.run_polling()
    
if __name__ == '__main__':
    main()

    

    
