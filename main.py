from typing import Final
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message
from responses import get_response
from discord.ext import commands

#load token
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')
print(TOKEN)

intents: Intents = Intents.default()
intents.message_content = True # NOQA
client: Client = Client(intents=intents)

#message func
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(Message was empty because intents were not enabled probably...)')
        return
    
    if is_private := user_message[0] == '?':
        user_message = user_message[1:]
        
    try:
        response: str = get_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)
    except Exception as e:
        print(e)
        
#bot startup
@client.event
async def on_ready() -> None:
    print(f'{client.user} is now running!')

#Handle Incoming Messages
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return
    
    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)
    
    print(f'[{channel}] {username}: "{user_message}"')
    await send_message(message, user_message)
    await bot.process_commands(message)
    
    
#CREATE COMMANDS----------------------------------
bot = commands.Bot(command_prefix="sb!", intents=intents)

@bot.command()
async def hello(ctx):
    await ctx.send('Hello! I am snoopy.')
    
    
@bot.command()
async def createP(ctx):
    await ctx.send('Should')


client.run(token=TOKEN)
bot.run(token=TOKEN)


# def main() -> None:
#     client.run(token=TOKEN)
#     bot.run(token=TOKEN)
    
# if __name__ == '__main__':
#     main()
