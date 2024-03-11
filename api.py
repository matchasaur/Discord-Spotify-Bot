import requests
from urllib.parse import quote, urlencode
import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth



def spotifyInit() -> None:
    scope = 'playlist-modify-private playlist-modify-public user-library-read'  # Scopes needed for creating a playlist
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
    if sp:
        print('Successfully authenticated with Spotify')
        return sp
    else:
        print('Unable to authenticated with Spotify')

async def create_playlist(title: str):
    playlist_name = title
    
    access_token = os.getenv('SPOT_AUTH')

    create_playlist_url = 'https://api.spotify.com/v1/me/playlists'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        'name': playlist_name,
        'public': False  # Set to True if you want the playlist to be public
    }

    response = requests.post(create_playlist_url, headers=headers, json=data)
    print("response status code: ", response.status_code)
    response_data = response.json()
    print(response_data['external_urls']['spotify'])
    playlist_url = response_data['external_urls']['spotify']

    if response.status_code == 200 or response.status_code == 201:
        print("Playlist created successfully!")
        return (playlist_url)
    else:
        print("Error creating playlist:", response.json())
        return False
    
async def delete_playlist(id: str):
    playlist_id = id
    access_token = os.getenv('SPOT_AUTH')
    headers = {
        "Authorization": f"Bearer {access_token}"
    }   

    response = requests.delete(f"https://api.spotify.com/v1/playlists/{playlist_id}/followers", headers=headers)

    if response.status_code == 200:
        print("Playlist deleted successfully")
        return True
    else:
        print("Failed to delete playlist:", response.status_code, response.text)
        return False