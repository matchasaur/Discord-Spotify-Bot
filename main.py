from typing import Final
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, utils, CategoryChannel, ui, ButtonStyle, Interaction, Embed
import discord
from responses import get_response
from discord.ext import commands
from api import spotifyInit, create_playlist, delete_playlist
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import spotipy
from spotipy.oauth2 import SpotifyOAuth

#Start by connecting to our database
load_dotenv()
mongopw = os.getenv('MONGOPW')
uri = f"mongodb+srv://jtanu45:{mongopw}@snoopster.uudikfw.mongodb.net/?retryWrites=true&w=majority&appName=Snoopster"
# Create a new client and connect to the server
dbclient = MongoClient(uri, server_api=ServerApi('1'))
database = dbclient.dev
# Send a ping to confirm a successful connection
try:
    dbclient.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

#Now lets connect and authorize with spotify
scope = 'playlist-modify-private playlist-modify-public user-library-read'  # Scopes needed for creating a playlist
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
spuser = sp.current_user() #This is the spotify bot account, use for spotipy methods for crud operations
spuserID = spuser['id']
if sp:
    print('Successfully authenticated with Spotify')
else:
    print('Unaable to authenticate with Spotify')
    
#Then lets initialize our discord bot/client
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
async def createP(ctx, *args):
    guild = ctx.guild
    author = ctx.author
    
    playlist_name = args[0]
    #playlist_url = await create_playlist(playlist_name)
    new_playlist = sp.user_playlist_create(spuserID, playlist_name, description='')
    
    
    if not new_playlist:
        await ctx.send('Unable to create new playlist')
        return

    # Check if the category exists
    category_name = "Collab Playlists"
    category = utils.get(guild.categories, name=category_name)
    
    if not category:
        # If category doesn't exist, create the category
        category = await guild.create_category(category_name)
    
    # Create the text channel within the category
    playlist_url = new_playlist['external_urls']['spotify']
    new_channel = await category.create_text_channel(name=playlist_name)
    await ctx.send(f"Text channel `{playlist_name}` created successfully in category `{category_name}`.")    
    await new_channel.send(f'@here Here is your new playlist!{playlist_url}')
    
    #now create an instance in the database

    playlist_id = playlist_url.split('/')[-1]

    print("Playlist ID:", playlist_id)
    
    userlist = []
    userlist.append(str(author.id))
    
    collection = database.playlists_info
    
    doc = {
        'name': playlist_name,
        'guildid': str(guild.id),
        'channelid': str(new_channel.id),
        'playlistid': playlist_id,
        'ownerid': str(author.id),
        'ownername': author.global_name,
        'users': userlist,
    }
    
    result = collection.insert_one(doc)
    print(f"Document inserted with id: {result.inserted_id}")

#delete playlist within text-channel
@bot.command()
async def deleteP(ctx):
    class Menu(ui.View):
        def __init__(self, channelid: str, guildid: str, ownerid: str, channel: discord.channel):
            super().__init__()
            self.value = None
            self.channelid = channelid
            self.guildid = guildid
            self.ownerid = ownerid
            self.channel = channel
            
        @ui.button(label='Cancel', style=ButtonStyle.grey)
        async def option1(self, interaction: Interaction, button: ui.Button):
            await interaction.response.send_message('Did not delete')
            self.value = False
            self.stop()
            
        @ui.button(label='Delete', style=ButtonStyle.danger)
        async def option2(self, interaction: Interaction, button: ui.Button):
            guild = self.guildid
            channelid = self.channelid
            owner = self.ownerid
            channel = self.channel
            name = await deleteplaylist(channel_id=channelid, guild_id=guild, owner_id=owner, channel=channel)
            if name:
                await interaction.response.send_message(f'{name} has been deleted')
            else:
                await interaction.response.send_message(f'Ran into an error while attempting to delete the playlist...')
            #debug
            #print('guild: ', guild, '\nchannel: ', channel)
            self.value = False
            self.stop()
            
    user = ctx.author
    guild = str(ctx.guild.id)
    channel = ctx.channel
    owner_id = str(user.id)
    channel_id = str(channel.id)
    
    #If the author is not the owner of the playlist then return
    if not check_owner(owner_id=owner_id, channel_id=channel_id):
        await ctx.reply('You do not have permission to delete this channel')
        return
    
    embed = Embed(color=discord.Color.red())
    embed.add_field(name='', value='Are you sure you want to order the eggroll?')
    view = Menu(channelid=channel_id, guildid=guild, ownerid=owner_id, channel=channel)
    await user.send(embed=embed, view=view)

#Helper functions-----------------------------------------

#check if author is owner of playlist/channel
def check_owner(owner_id: str, channel_id: str):
    collection = database.playlists_info
    print(f'Checking if {owner_id} owns channel: {channel_id}')
    result = collection.find_one({'ownerid': owner_id, 'channelid': channel_id})
    print(f'The reuslt is: {result}')
    return result

async def deleteplaylist(channel_id: str, guild_id: str, owner_id: str, channel: discord.channel):
    collection = database.playlists_info
    doc = collection.find_one({'ownerid': owner_id, 'channelid': channel_id})
    name = doc.get('name', None)
    id = doc.get('playlistid', None)
    print('Playlist ID: ', id)
    # res = await delete_playlist(id)
    res = sp.user_playlist_unfollow(spuserID, id)
    #Fix this? For some reason its deleting but return false
    
    if not res:
        print('Unable to delete playlist through spotify')
        return False
    
    result = collection.delete_one({'ownerid': owner_id, 'channelid': channel_id, 'guildid': guild_id})
    
    if result.deleted_count > 0:
        print(f'Document with guildid: {guild_id}, channelid: {channel_id}, and ownerid: {owner_id} has been deleted')  # Document was found and deleted
        await channel.delete()
        return name
    else:
        print('Document not found')  # Document was not found
        return False
    
    

def main() -> None:
    #spotifyInit()
    # client.run(token=TOKEN)
    bot.run(token=TOKEN)
    
    
if __name__ == '__main__':
    main()
