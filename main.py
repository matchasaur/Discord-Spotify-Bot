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
from datetime import datetime

#Start by connecting to our database
load_dotenv()
mongopw = os.getenv('MONGOPW')
uri = os.getenv('MONGOURI')
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
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, open_browser=False))
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
intents.members = True
client: Client = Client(intents=intents)

#Helper functions-----------------------------------------

#check if author is owner of playlist/channel

def check_owner(owner_id: str, channel_id: str):
    collection = database.playlists_info
    print(f'Checking if {owner_id} owns channel: {channel_id}')
    result = collection.find_one({'ownerid': owner_id, 'channelid': channel_id})
    print(f'The reuslt is: {result}')
    return result

async def is_owner(ctx):
    user = str(ctx.author.id)
    channelid = str(ctx.channel.id)
    collection = database.playlists_info
    print(f'Checking if {user} owns channel: {channelid}')
    result = collection.find_one({'ownerid': user, 'channelid': channelid})
    if result:
        return True
    else:
        await ctx.reply('You do not have permission', ephemeral=True)
        return False

async def deleteplaylist(channel_id: str, guild_id: str, owner_id: str, channel: discord.channel):
    collection = database.playlists_info
    doc = collection.find_one({'ownerid': owner_id, 'channelid': channel_id})
    name = doc.get('name', None)
    id = doc.get('playlistid', None)
    print('Playlist ID: ', id)
    # res = await delete_playlist(id)
    res = sp.user_playlist_unfollow(spuserID, id)
    #Fix this? For some reason its deleting but return false
    print('Del response: ', res)
    
    #FIX THIS: Currently there is no way to check if the playlist has successfully been deleted on spotify
    # if not res:
    #     print('Unable to delete playlist through spotify')
    #     return False
    
    result = collection.delete_one({'ownerid': owner_id, 'channelid': channel_id, 'guildid': guild_id})
    collection = database.tracks
    collection.delete_many({'channelid': channel_id, 'guildid': guild_id, 'playlistid': id})
    
    if result.deleted_count > 0:
        print(f'Document with guildid: {guild_id}, channelid: {channel_id}, and ownerid: {owner_id} has been deleted')  # Document was found and deleted
        await channel.delete()
        return name
    else:
        print('Document not found')  # Document was not found
        return False

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
        

#CREATE COMMANDS----------------------------------
bot = commands.Bot(command_prefix="sb!", intents=intents)

#bot startup
@bot.event
async def on_ready():
    print(f'{bot.user} is now running!')
    await bot.tree.sync()

#Handle Incoming Messages
@bot.event
async def on_message(message: Message):
    if message.author == client.user:
        return
    
    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)
    
    print(f'[{channel}] {username}: "{user_message}"')
    # await send_message(message, user_message)
    await bot.process_commands(message)

@bot.hybrid_command()
async def hello(ctx):
    await ctx.send('Hello! I am snoopy.')
    
    
@bot.hybrid_command(description="Creates a private text channel and spotify playlist", name="newplaylist")
async def createP(ctx, arg1: str):
    guild = ctx.guild
    author = ctx.author
    
    playlist_name = arg1
    #playlist_url = await create_playlist(playlist_name)
    new_playlist = sp.user_playlist_create(spuserID, playlist_name, description='', public=False)
    
    
    if not new_playlist:
        await ctx.send('Unable to create new playlist')
        return

    # Check if the category exists
    category_name = "Collab Playlists"
    category = utils.get(guild.categories, name=category_name)
    
    if not category:
        # If category doesn't exist, create the category
        category = await guild.create_category(category_name)
        
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        author: discord.PermissionOverwrite(read_messages=True)
    }
    
    # Create the text channel within the category
    playlist_url = new_playlist['external_urls']['spotify']
    new_channel = await category.create_text_channel(name=playlist_name, overwrites=overwrites)
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
        'guildname': str(guild.name),
        'guildid': str(guild.id),
        'channelid': str(new_channel.id),
        'playlistid': playlist_id,
        'ownerid': str(author.id),
        'ownername': author.global_name,
        'users': userlist,
        "createdAt": datetime.now()
    }
    
    result = collection.insert_one(doc)
    print(f"Document inserted with id: {result.inserted_id}")

#delete playlist within text-channel
@bot.hybrid_command(description="Deletes text-channel and spotify playlist", name="deleteplaylist")
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
    embed.add_field(name='', value=f'Are you sure you want to delete {str(channel.name)} in {str(ctx.guild.name)}?\n*Note: While the playlists remain available for your listening pleasure, please be aware that the associated database information will be deleted. Additionally, all bot functionalities related to these playlists will no longer be active.*')
    view = Menu(channelid=channel_id, guildid=guild, ownerid=owner_id, channel=channel)
    await user.send(embed=embed, view=view)

@bot.hybrid_command(description="Add track to associated spotify playlist", name="addtrack")
async def addsong(ctx, arg1: str):
    userid = str(ctx.author.id)
    guildid = str(ctx.guild.id)
    channelid = str(ctx.channel.id)

    track = arg1.split('?')[0]
    print('Track url: ', track)
    
    collection = database.playlists_info
    doc = collection.find_one({'channelid': channelid, 'guildid': guildid})
    playlistid = doc.get('playlistid', None)
    playlistname = doc.get('name', None)
    res = sp.user_playlist_add_tracks(spuserID, playlistid, [track], position=None)
    trackinfo = sp.track(track_id=track)
    # print(trackinfo)
    trackartist = trackinfo['artists'][0]['name']
    trackname = trackinfo['name']

    #Fix this: Need a safeguard incase the track was unable to be added
    # if not res:
    #     print('Could not add track to playlist')
    #     await ctx.send('Could not add track to playlist')
    #     return
    
    collection = database.tracks
    
    doc = {
        "user": userid,
        "guildid": guildid,
        "playlistid": playlistid,
        "channelid": channelid,
        "track": track,
        "createdAt": datetime.now()
    }
    
    collection.insert_one(doc)

    print('Track added to playlist')
    await ctx.send(f'```{trackname} by {trackartist} added to {playlistname}!```')

@bot.hybrid_command(description="Remove track from associated spotify playlist", name="removetrack")
async def removesong(ctx, arg1: str):
    userid = str(ctx.author.id)
    guildid = str(ctx.guild.id)
    channelid = str(ctx.channel.id)

    track = arg1.split('?')[0]
    print('Track url: ', track)
    
    collection1 = database.playlists_info
    doc1 = collection1.find_one({'channelid': channelid, 'guildid': guildid})
    owner = doc1.get('ownerid', None)
    playlistid = doc1.get('playlistid', None)
    playlistname = doc1.get('name', None)
    
    collection2 = database.tracks
    doc2 = collection2.find_one({'playlistid': playlistid, 'channelid': channelid, 'guildid': guildid, 'playlistid': playlistid, 'track': track})
    trackinfo = sp.track(track_id=track)
    trackname = trackinfo['name']
    trackartist = trackinfo['artists'][0]['name']
    
    if doc2:
        user = doc2.get('user')
        if userid == user or userid == owner:
            # trackid = track.split('/')[-1]
            # uri = f'spotify:track:{trackid}'
            sp.user_playlist_remove_all_occurrences_of_tracks(spuserID, playlistid, [track], snapshot_id=None)
            collection2.delete_one(doc2)
            print(f'Successfully removed track')
            await ctx.send(f'```{trackname} by {trackartist} removed from {playlistname}!```')
        else:
            print(f'Unauthorized access. User has not added this track.')
            await ctx.send(f'Unauthorized access. User has not added this track.')
    else:
        print(f'Track({track}) does not exist in playlist{playlistid}')
        await ctx.send('Unable to remove track. This track does not exist in the playlist.')

@bot.hybrid_command(description="Invites a user to collaborate on a playlist", name="invite")
@commands.check(is_owner)
async def invite(ctx, arg1: str):
    class Menu(ui.View):
        def __init__(self, channelid: str, guildid: str, channel: discord.channel, user: discord.user, playlistname: str, guildname: str):
            super().__init__()
            self.value = None
            self.channelid = channelid
            self.guildid = guildid
            self.channel = channel
            self.user = user
            self.playlistname = playlistname
            self.guildname = guildname
            
        @ui.button(label='Accept', style=ButtonStyle.green)
        async def acceptinvite(self, interaction: Interaction, button: ui.Button):
            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = True
            overwrite.send_messages = True
            await self.channel.set_permissions(self.user, overwrite=overwrite)
            
            #add user to playlistinfo users
            collection = database.playlists_info
            query = {'guildid':self.guildid, 'channelid': self.channelid}
            userid = self.user.id
            update = {'$push': {'users': str(userid)}}
            collection.update_one(query, update)
            
            await interaction.response.send_message(f'You have been added to {self.playlistname} in {self.guildname}')
            
    user = await ctx.guild.fetch_member(int(arg1))
    members = ctx.channel.members
    print('members: ', members)
    
    #Check if this user is still in the server
    if not user:
        await ctx.reply('This user does not exist in this server')
        return
    elif user in ctx.channel.members:
        await ctx.reply(f'This user already exists in {ctx.channel.name}')
        return
    
    author = ctx.author.global_name
    guild = str(ctx.guild.id)
    channel = ctx.channel
    channel_id = str(channel.id)
    collection = database.playlists_info
    doc = collection.find_one({'channelid': channel_id, 'guildid': guild})
    playlistname = doc.get('name', None)
    guildname = ctx.guild.name
    
    embed = Embed(color=discord.Color.purple())
    embed.add_field(name='Playlist Invite', value=f'{author} has invnited you to collaborate on {playlistname} in {guildname}\n*Note: This invitation will expire in 120 seconds*')
    view = Menu(channelid=channel_id, guildid=guild, channel=channel, user=user, playlistname=playlistname, guildname=guildname)
    await ctx.reply(f'An invite has been sent to {user.global_name}')
    await user.send(embed=embed, view=view)
    
@bot.hybrid_command(description="Removes a user from the playlist/channel", name="kick")
@commands.check(is_owner)
async def kick(ctx, arg1: str):
    class Menu(ui.View):
        def __init__(self, channelid: str, guildid: str, channel: discord.channel, user: discord.user, playlistname: str, guildname: str):
            super().__init__()
            self.value = None
            self.channelid = channelid
            self.guildid = guildid
            self.channel = channel
            self.user = user
            self.playlistname = playlistname
            self.guildname = guildname
            
        @ui.button(label='Cancel', style=ButtonStyle.grey)
        async def cancel(self, interaction: Interaction, button: ui.Button):
            await interaction.response.send_message(f'Request has been canceled')
            self.value = False
            self.stop()
            
        @ui.button(label='Kick', style=ButtonStyle.danger)
        async def kick(self, interaction: Interaction, button: ui.Button):
            overwrite = discord.PermissionOverwrite()
            overwrite.read_messages = False
            overwrite.send_messages = False
            await self.channel.set_permissions(self.user, overwrite=overwrite)
            
            #Remove user from playlistinfo users
            collection = database.playlists_info
            query = {'guildid':self.guildid, 'channelid': self.channelid}
            userid = self.user.id
            update = {'$pull': {'users': str(userid)}}
            collection.update_one(query, update)
            
            await interaction.response.send_message(f'{self.user.name} has been removed from {playlistname}')
            self.value = True
            self.stop()
    
    user = await ctx.guild.fetch_member(int(arg1))
    members = ctx.channel.members
    print('members: ', members)
    
    #Check if this user is still in the server
    if not user:
        await ctx.reply('This user does not exist in this server')
        return
    elif user not in ctx.channel.members:
        await ctx.reply(f'This user does not exist in {ctx.channel.name}')
        return
    
    author = ctx.author.global_name
    guild = str(ctx.guild.id)
    channel = ctx.channel
    channel_id = str(channel.id)
    collection = database.playlists_info
    doc = collection.find_one({'channelid': channel_id, 'guildid': guild})
    playlistname = doc.get('name', None)
    guildname = ctx.guild.name
    
    embed = Embed(color=discord.Color.purple())
    embed.add_field(name='Playlist Invite', value=f'Are you sure you want to kick {user.name} from {playlistname}?')
    view = Menu(channelid=channel_id, guildid=guild, channel=channel, user=user, playlistname=playlistname, guildname=guildname)
    await ctx.reply(embed=embed, view=view, ephemeral=True)
    

def main() -> None:
    #spotifyInit()
    # client.run(token=TOKEN)
    bot.run(token=TOKEN)
    
    
if __name__ == '__main__':
    main()
