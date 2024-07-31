import logging
import random
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, 
    InputMediaPhoto
)
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = '7294713269:AAFwKEXMbLFMwKMDe6likn7NEbKEuLbVtxE'
VERIFY_GROUP_ID = '-1002070732383'
GROUP_INVITE_LINK = 'https://t.me/tamilchattingu'

game_data = {}

async def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in game_data:
        game_data[chat_id] = {
            'status': 'waiting',
            'teams': {'A': [], 'B': []},
            'captains': {'A': None, 'B': None},
            'players': {},
            'scores': {'A': {}, 'B': {}},
            'batting_order': {'A': [], 'B': []},
            'bowling_order': {'A': [], 'B': []},
            'current_batting_team': None,
            'current_bowling_team': None,
            'turn': None,
            'scoreboard_message_id': None,
            'captain_message_id': None
        }
        await update.message.reply_text('Game initialized. Use /join to join a team.')

async def join(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    if chat_id not in game_data:
        await update.message.reply_text('Game not initialized. Use /start to initialize the game.')
        return

    if user_id in game_data[chat_id]['players']:
        await update.message.reply_text('You have already joined a team.')
        return

    if await is_user_in_group(user_id, context):
        keyboard = [
            [InlineKeyboardButton("Join Team A", callback_data=f'join_team_A_{user_id}')],
            [InlineKeyboardButton("Join Team B", callback_data=f'join_team_B_{user_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Choose your team:', reply_markup=reply_markup)
    else:
        await update.message.reply_text(f'Please join the group first: {GROUP_INVITE_LINK}')

async def is_user_in_group(user_id: int, context: CallbackContext) -> bool:
    try:
        chat_member = await context.bot.get_chat_member(chat_id=VERIFY_GROUP_ID, user_id=user_id)
        return chat_member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.error(f'Error checking user status: {e}')
        return False

async def verify_join(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = int(query.data.split('_')[2])
    team = query.data.split('_')[1]

    if user_id in game_data[chat_id]['players']:
        await query.edit_message_text('You have already joined a team.')
        return

    game_data[chat_id]['players'][user_id] = {'username': query.from_user.username, 'team': team}
    game_data[chat_id]['teams'][team].append(user_id)

    await query.edit_message_text(f'{query.from_user.username} joined Team {team}.')
    await update_team_list(chat_id, context)

async def update_team_list(chat_id: int, context: CallbackContext) -> None:
    team_list = 'Team A:\n' + '\n'.join([game_data[chat_id]['players'][player]['username'] for player in game_data[chat_id]['teams']['A']]) + '\n\n'
    team_list += 'Team B:\n' + '\n'.join([game_data[chat_id]['players'][player]['username'] for player in game_data[chat_id]['teams']['B']])
    message = await context.bot.send_message(chat_id=chat_id, text=team_list)

    if game_data[chat_id]['scoreboard_message_id']:
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=game_data[chat_id]['scoreboard_message_id'])

    game_data[chat_id]['scoreboard_message_id'] = message.message_id
    await context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)

async def set_captain(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    team_a_players = [game_data[chat_id]['players'][player]['username'] for player in game_data[chat_id]['teams']['A']]
    team_b_players = [game_data[chat_id]['players'][player]['username'] for player in game_data[chat_id]['teams']['B']]

    keyboard = [[InlineKeyboardButton(player, callback_data=f'vote_captain_A_{player}') for player in team_a_players]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Vote for Team A captain:', reply_markup=reply_markup)

    keyboard = [[InlineKeyboardButton(player, callback_data=f'vote_captain_B_{player}') for player in team_b_players]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Vote for Team B captain:', reply_markup=reply_markup)

async def vote_captain(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    team = query.data.split('_')[2]
    player = query.data.split('_')[3]

    game_data[chat_id]['captains'][team] = player
    await query.edit_message_text(f'{player} is the captain of Team {team}.')

    if game_data[chat_id]['captains']['A'] and game_data[chat_id]['captains']['B']:
        await context.bot.send_message(chat_id=chat_id, text='Captains are set. Use /toss to start the toss.')

async def coin_toss(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in game_data or game_data[chat_id]['status'] != 'waiting':
        await update.message.reply_text('Game is not ready or already in progress.')
        return

    result = random.choice(['A', 'B'])
    game_data[chat_id]['toss_winner'] = result
    await update.message.reply_text(f'Team {result} won the toss. Do you want to bat or bowl?', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Bat", callback_data=f'bat_{result}')],
        [InlineKeyboardButton("Bowl", callback_data=f'bowl_{result}')]
    ]))

async def toss_decision(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    decision = query.data.split('_')[0]
    team = query.data.split('_')[1]

    if decision == 'bat':
        game_data[chat_id]['current_batting_team'] = team
        game_data[chat_id]['current_bowling_team'] = 'A' if team == 'B' else 'B'
    else:
        game_data[chat_id]['current_batting_team'] = 'A' if team == 'B' else 'B'
        game_data[chat_id]['current_bowling_team'] = team

    game_data[chat_id]['status'] = 'playing'
    await query.edit_message_text(f'Team {game_data[chat_id]["current_batting_team"]} is batting and Team {game_data[chat_id]["current_bowling_team"]} is bowling.')

    await set_batting_order(update, context, chat_id)
    await set_bowling_order(update, context, chat_id)

async def set_batting_order(update: Update, context: CallbackContext, chat_id: int) -> None:
    current_batting_team = game_data[chat_id]['current_batting_team']
    captain_id = game_data[chat_id]['captains'][current_batting_team]

    keyboard = []
    for player_id in game_data[chat_id]['teams'][current_batting_team]:
        username = game_data[chat_id]['players'][player_id]['username']
        keyboard.append([InlineKeyboardButton(username, callback_data=f"batting_order_{player_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=captain_id, text='Set your batting order:', reply_markup=reply_markup)

async def set_bowling_order(update: Update, context: CallbackContext, chat_id: int) -> None:
    current_bowling_team = game_data[chat_id]['current_bowling_team']
    captain_id = game_data[chat_id]['captains'][current_bowling_team]

    keyboard = []
    for player_id in game_data[chat_id]['teams'][current_bowling_team]:
        username = game_data[chat_id]['players'][player_id]['username']
        keyboard.append([InlineKeyboardButton(username, callback_data=f"bowling_order_{player_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=captain_id, text='Set your bowling order:', reply_markup=reply_markup)

async def batting_order(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    player_id = int(query.data.split('_')[2])
    current_batting_team = game_data[chat_id]['current_batting_team']

    game_data[chat_id]['batting_order'][current_batting_team].append(player_id)
    await query.edit_message_text(f'{game_data[chat_id]["players"][player_id]["username"]} added to batting order.')

    if len(game_data[chat_id]['batting_order'][current_batting_team]) == len(game_data[chat_id]['teams'][current_batting_team]):
        await context.bot.send_message(chat_id=chat_id, text='Batting order is set. You can now start the game.')

async def bowling_order(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    player_id = int(query.data.split('_')[2])
    current_bowling_team = game_data[chat_id]['current_bowling_team']

    game_data[chat_id]['bowling_order'][current_bowling_team].append(player_id)
    await query.edit_message_text(f'{game_data[chat_id]["players"][player_id]["username"]} added to bowling order.')

    if len(game_data[chat_id]['bowling_order'][current_bowling_team]) == len(game_data[chat_id]['teams'][current_bowling_team]):
        await context.bot.send_message(chat_id=chat_id, text='Bowling order is set. The game can start now.')

async def ball(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    if chat_id not in game_data or game_data[chat_id]['status'] != 'playing':
        await update.message.reply_text('The game is not in progress.')
        return

    current_bowling_team = game_data[chat_id]['current_bowling_team']
    current_bowler = game_data[chat_id]['bowling_order'][current_bowling_team][0]

    if user_id != current_bowler:
        await update.message.reply_text('It is not your turn to bowl.')
        return

    try:
        ball_result = int(update.message.text)
        if ball_result < 0 or ball_result > 6:
            raise ValueError()
    except ValueError:
        await update.message.reply_text('Please enter a valid number between 0 and 6.')
        return

    current_batting_team = game_data[chat_id]['current_batting_team']
    current_batsman = game_data[chat_id]['batting_order'][current_batting_team][0]

    if ball_result == 0:
        game_data[chat_id]['batting_order'][current_batting_team].pop(0)
        await update.message.reply_text(f'{game_data[chat_id]["players"][current_batsman]["username"]} is out!')
        if not game_data[chat_id]['batting_order'][current_batting_team]:
            await update.message.reply_text('All out! Game over.')
            game_data[chat_id]['status'] = 'finished'
            await pin_results(chat_id, context)
            return
    else:
        if current_batsman in game_data[chat_id]['scores'][current_batting_team]:
            game_data[chat_id]['scores'][current_batting_team][current_batsman] += ball_result
        else:
            game_data[chat_id]['scores'][current_batting_team][current_batsman] = ball_result

    await update_scoreboard(chat_id, context)

async def update_scoreboard(chat_id: int, context: CallbackContext) -> None:
    score_text = 'Current Scores:\n'
    for team in ['A', 'B']:
        score_text += f'Team {team}:\n'
        for player_id, score in game_data[chat_id]['scores'][team].items():
            score_text += f'{game_data[chat_id]["players"][player_id]["username"]}: {score}\n'
        score_text += '\n'

    if game_data[chat_id]['scoreboard_message_id']:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=game_data[chat_id]['scoreboard_message_id'], text=score_text)
    else:
        message = await context.bot.send_message(chat_id=chat_id, text=score_text)
        game_data[chat_id]['scoreboard_message_id'] = message.message_id

    if game_data[chat_id]['scoreboard_message_id']:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=game_data[chat_id]['scoreboard_message_id'])

async def pin_results(chat_id: int, context: CallbackContext) -> None:
    winner_team = max(game_data[chat_id]['scores'], key=lambda team: sum(game_data[chat_id]['scores'][team].values()))
    loser_team = 'A' if winner_team == 'B' else 'B'

    winner_captain_id = next(iter(game_data[chat_id]['teams'][winner_team]))
    loser_captain_id = next(iter(game_data[chat_id]['teams'][loser_team]))

    winner_profile_pic = (await context.bot.get_user_profile_photos(user_id=winner_captain_id)).photos[0][0].file_id
    loser_profile_pic = (await context.bot.get_user_profile_photos(user_id=loser_captain_id)).photos[0][0].file_id

    await context.bot.send_photo(chat_id=chat_id, photo=winner_profile_pic, caption=f'Team {winner_team} wins!')
    await context.bot.send_photo(chat_id=chat_id, photo=loser_profile_pic, caption=f'Team {loser_team} loses.')

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('join', join))
    application.add_handler(CommandHandler('set_captain', set_captain))
    application.add_handler(CommandHandler('toss', coin_toss))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ball))
    application.add_handler(CallbackQueryHandler(verify_join, pattern='^join_team_'))
    application.add_handler(CallbackQueryHandler(vote_captain, pattern='^vote_captain_'))
    application.add_handler(CallbackQueryHandler(toss_decision, pattern='^bat_|^bowl_'))
    application.add_handler(CallbackQueryHandler(batting_order, pattern='^batting_order_'))
    application.add_handler(CallbackQueryHandler(bowling_order, pattern='^bowling_order_'))

    application.run_polling()

if __name__ == '__main__':
    main()
