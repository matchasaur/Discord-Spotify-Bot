import requests
from urllib.parse import quote, urlencode
import os
from dotenv import load_dotenv


def spotifyInit() -> None:
    # Spotify API credentials
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    redirect_uri = 'http://localhost:3000/callback'  # This should match the redirect URI you specified in the Spotify Developer Dashboard
    print(redirect_uri)

    # URL for Spotify authorization
    auth_url = 'https://accounts.spotify.com/authorize'
    scope = 'playlist-modify-private playlist-modify-public'  # Scopes needed for creating a playlist

    # Generate the authorization URL
    auth_params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': scope
    }
    auth_url = 'https://accounts.spotify.com/authorize?' + urlencode(auth_params)

    print(f"Please authorize the application by visiting the following URL:\n{auth_url}")

    # After authorization, the user will be redirected to the redirect_uri with a code
    authorization_code = input("Enter the code from the redirect URL: ")

    # Spotify URL for obtaining access token
    token_url = 'https://accounts.spotify.com/api/token'

    # Parameters for requesting access token
    token_data = {
        'grant_type': 'authorization_code',
        'code': authorization_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }

    # Requesting access token
    response = requests.post(token_url, data=token_data)
    response_data = response.json()
    #print(response_data)


    # Extract access token and refresh token
    access_token = response_data['access_token']
    refresh_token = response_data['refresh_token']
    os.environ['SPOT_AUTH'] = access_token
    os.environ['SPOT_REFRESH'] = refresh_token

    print("Access Token:", access_token)
    print("Refresh Token:", refresh_token)

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

    if response.status_code == 200:
        print("Playlist created successfully!")
        return (playlist_url)
    else:
        print("Error creating playlist:", response.json())
        return False