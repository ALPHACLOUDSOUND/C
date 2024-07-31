import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Replace with your group ID and bot's ID
VERIFY_GROUP_ID = -1002070732383# Example group ID (make sure it's a negative number for group IDs)
BOT_OWNER_ID = 7049798779
GROUP_INVITE_LINK = "https://t.me/tamilchattingu"  # Replace with your group's invite link

# Dictionary to hold game state and scores
game_data = {}

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Play Human Match", callback_data="mode_human")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome to Hand Cricket! Choose a game mode:', reply_markup=reply_markup)

async def set_game_mode(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "mode_human":
        game_data[chat_id] = {
            'players': {},
            'scores': {},
            'turn': None,
            'status': 'waiting',  # Can be 'waiting', 'playing', 'ended'
            'scoreboard_message_id': None,
            'mode': 'human',
            'teams': {'A': [], 'B': []}
        }
        await query.edit_message_text("Game mode set to play Human Match. Use /join to join the game.")

async def join(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Player"

    if chat_id not in game_data:
        await update.message.reply_text("Please select a game mode first using /start.")
        return

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

    # Prompt player to select a team
    keyboard = [
        [InlineKeyboardButton("Join Team A", callback_data=f"join_team_A_{user_id}")],
        [InlineKeyboardButton("Join Team B", callback_data=f"join_team_B_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(f'{username} has joined the game! Choose a team to join:', reply_markup=reply_markup)

async def join_team(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = int(query.data.split("_")[3])
    team = query.data.split("_")[2]

    if user_id not in game_data[chat_id]['players']:
        await query.edit_message_text('You need to join the game first using /join.')
        return

    # Remove player from any existing team
    for t in ['A', 'B']:
        if user_id in game_data[chat_id]['teams'][t]:
            game_data[chat_id]['teams'][t].remove(user_id)
            break

    # Add player to selected team
    game_data[chat_id]['teams'][team].append(user_id)

    # Update message with new team status
    team_names = {'A': 'Team A', 'B': 'Team B'}
    team_list = ', '.join(game_data[chat_id]['players'][p] for p in game_data[chat_id]['teams'][team])
    await query.edit_message_text(f'Player added to {team_names[team]}!\nCurrent {team_names[team]} members: {team_list}')

async def list_teams(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in game_data:
        await update.message.reply_text('No game mode set. Use /start to set up a game.')
        return

    teams = game_data[chat_id]['teams']
    team_a = ', '.join(game_data[chat_id]['players'].get(p, 'Unknown') for p in teams['A'])
    team_b = ', '.join(game_data[chat_id]['players'].get(p, 'Unknown') for p in teams['B'])

    await update.message.reply_text(f"Teams:\nTeam A: {team_a}\nTeam B: {team_b}")

async def admin_commands(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id != BOT_OWNER_ID:
        await update.message.reply_text("You are not authorized to use admin commands.")
        return

    chat_id = update.message.chat_id
    command = update.message.text.split(" ")

    if command[0] == '/addplayer':
        user_id = int(command[1])
        team = command[2].upper()
        if team not in ['A', 'B']:
            await update.message.reply_text('Invalid team. Use "A" or "B".')
            return

        if user_id not in game_data[chat_id]['players']:
            await update.message.reply_text('Player not found. Ensure the player has joined the game.')
            return

        # Add player to the selected team
        game_data[chat_id]['teams'][team].append(user_id)

        # Remove player from any existing team
        for t in ['A', 'B']:
            if t != team and user_id in game_data[chat_id]['teams'][t]:
                game_data[chat_id]['teams'][t].remove(user_id)
                break

        await update.message.reply_text(f'Player added to {team} team.')

    elif command[0] == '/removeplayer':
        user_id = int(command[1])
        team = command[2].upper()
        if team not in ['A', 'B']:
            await update.message.reply_text('Invalid team. Use "A" or "B".')
            return

        if user_id in game_data[chat_id]['teams'][team]:
            game_data[chat_id]['teams'][team].remove(user_id)
            await update.message.reply_text(f'Player removed from {team} team.')
        else:
            await update.message.reply_text('Player not found in the team.')

async def start_game(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in game_data or len(game_data[chat_id]['players']) < 2:
        await update.message.reply_text('Need at least two players to start the game.')
        return

    if not all(game_data[chat_id]['teams']['A']) or not all(game_data[chat_id]['teams']['B']):
        await update.message.reply_text('Both teams must have at least one player. Please add players to both teams.')
        return

    game_data[chat_id]['status'] = 'playing'
    game_data[chat_id]['turn'] = game_data[chat_id]['teams']['A'][0]

    await update.message.reply_text(
        f"Game started! Teams are:\n"
        f"Team A: {', '.join(game_data[chat_id]['players'][p] for p in game_data[chat_id]['teams']['A'])}\n"
        f"Team B: {', '.join(game_data[chat_id]['players'][p] for p in game_data[chat_id]['teams']['B'])}\n"
        f"It's {game_data[chat_id]['players'][game_data[chat_id]['turn']]}\'s turn. Use /ball to play your turn."
    )

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
    game_data[chat_id]['scores'][user_id] = game_data[chat_id]['scores'].get(user_id, 0) + run

    # Switch turn to next player
    current_team = 'A' if user_id in game_data[chat_id]['teams']['A'] else 'B'
    next_team = 'B' if current_team == 'A' else 'A'
    current_team_players = game_data[chat_id]['teams'][current_team]
    next_team_players = game_data[chat_id]['teams'][next_team]

    current_index = current_team_players.index(user_id)
    if current_index + 1 < len(current_team_players):
        next_player = current_team_players[current_index + 1]
    else:
        next_player = next_team_players[0] if next_team_players else current_team_players[0]

    game_data[chat_id]['turn'] = next_player

    await update.message.reply_text(f'You scored {run} runs! It\'s now {game_data[chat_id]["players"][game_data[chat_id]["turn"]]}\'s turn.')

    # Update and pin scoreboard
    await update_scoreboard(update, context, chat_id)

async def update_scoreboard(update: Update, context: CallbackContext, chat_id: int) -> None:
    scores = game_data[chat_id]['scores']
    scoreboard = 'Scoreboard:\n'
    for user_id, score in scores.items():
        username = game_data[chat_id]['players'][user_id]
        scoreboard += f'{username}: {score} runs\n'

    message = await update.message.reply_text(scoreboard)
    if game_data[chat_id]['scoreboard_message_id']:
        try:
            await context.bot.unpin_chat_message(chat_id=chat_id, message_id=game_data[chat_id]['scoreboard_message_id'])
        except Exception as e:
            logger.error(f"Error unpinning message: {e}")

    game_data[chat_id]['scoreboard_message_id'] = message.message_id
    await context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)

async def is_user_in_group(user_id: int, context: CallbackContext) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=VERIFY_GROUP_ID, user_id=user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        return False

def main() -> None:
    application = Application.builder().token("7294713269:AAFwKEXMbLFMwKMDe6likn7NEbKEuLbVtxE").build()

    # Command Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('join', join))
    application.add_handler(CommandHandler('startgame', start_game))
    application.add_handler(CommandHandler('listteams', list_teams, filters=filters.TEXT & ~filters.COMMAND))

    # Inline Query Handlers
    application.add_handler(CallbackQueryHandler(set_game_mode, pattern='^mode_'))
    application.add_handler(CallbackQueryHandler(verify_join, pattern='^verify_'))
    application.add_handler(CallbackQueryHandler(join_team, pattern='^join_team_'))
    
    # Admin Commands
    application.add_handler(CommandHandler('addplayer', admin_commands, filters=filters.TEXT & ~filters.COMMAND))
    application.add_handler(CommandHandler('removeplayer', admin_commands, filters=filters.TEXT & ~filters.COMMAND))
    
    # Ball command
    application.add_handler(CommandHandler('ball', ball))

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
