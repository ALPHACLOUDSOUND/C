from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import logging
import random

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# Dictionary to hold game state and scores
game_data = {}

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
            'inning': 1
        }
    
    if user_id in game_data[chat_id]['players']:
        update.message.reply_text('You are already in the game.')
        return

    game_data[chat_id]['players'][user_id] = username
    game_data[chat_id]['scores'][user_id] = 0

    update.message.reply_text(f'{username} has joined the game!')

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
    if 'scoreboard_message_id' in game_data[chat_id]:
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
    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        update.message.reply_text('No game is currently running or the game has ended.')
        return

    game_data[chat_id]['status'] = 'ended'
    update.message.reply_text('Game ended.')
    update_scoreboard(update, chat_id)  # Update scoreboard one last time

def handle_message(update: Update, context: CallbackContext):
    update.message.reply_text('Use /start to start and /join to join the game. Use /startgame to begin the game and /ball to play.')

def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN", use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("join", join))
    dp.add_handler(CommandHandler("startgame", start_game))
    dp.add_handler(CommandHandler("endgame", end_game))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CommandHandler("ball", ball))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you send a signal to stop
    updater.idle()

if __name__ == '__main__':
    main()
