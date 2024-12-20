import os 
import time
import asyncio
import threading
import requests
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
#from concurrent.futures import ThreadPoolExecuter
ab_repeat_active_event = threading.Event()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

client_id = 'f6933e657b4b4a538a2dce4502e9e9a4'

client_secret = '4fe640c3af47480caa70d7e4d5b03715'

redirect_uri='http://192.168.1.9:5000/callback'

scope = 'playlist-read-private, streaming, user-modify-playback-state, user-read-playback-state'

global ab_repeat_active
ab_repeat_active = False
GETSONGBPM_API_KEY = "YOUR_API_KEY"
GETSONGBPM_BASE_URL = "https://api.getsong.co"

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler, 
    requests_timeout=20,
    show_dialog=True
)
sp = Spotify(auth_manager=sp_oauth)

@app.route('/')
def home():
    #print("Authorizing")
    cached_token = cache_handler.get_cached_token()
    if not cached_token:
        print("Could not Authorize")
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    print("Authorized, render html")
    return render_template('index.html')

@app.route('/callback')
def callback():
    auth_code = request.args.get('code')
    if not auth_code:
        print("No authorization code provided in callback")
        return redirect('/')
    access_token = sp_oauth.get_access_token(auth_code)
    cache_handler.save_token_to_cache(access_token)

    return redirect('/')
    

@app.route('/get_track_info', methods=['GET'])
def get_track_info():
    print("Getting track info")
    playback = sp.current_playback()
    if playback and playback['is_playing']:
        track_name = playback['item']['name']
        track_duration = playback['item']['duration_ms'] / 1000  # Convert ms to seconds
        album_art_url = playback['item']['album']['images'][0]['url']  # Get album art URL
        album_name = playback['item']['album']['name']
        artist_name = playback['item']['artists'][0]['name'] 
        track_id = playback['item']['id']  # Get track ID
        
        search_url = f"{GETSONGBPM_BASE_URL}/search/"
        params = {
            "api_key": GETSONGBPM_API_KEY,
            "type": "song",
            "lookup": f"{track_name} {artist_name}"
        }
        
        response = requests.get(search_url, params=params)
        if response.status_code == 200:
            search_results = response.json().get("search", [])
            if search_results:
                song_id = search_results[0]["id"]  # Take the first result's ID
                
                # Fetch song details by ID
                song_url = f"{GETSONGBPM_BASE_URL}/song/"
                song_params = {
                    "api_key": GETSONGBPM_API_KEY,
                    "id": song_id
                }
                
                song_response = requests.get(song_url, params=song_params)
                if song_response.status_code == 200:
                    song_data = song_response.json().get("song", {})
                    tempo = song_data.get("tempo", None)
                    key_of = song_data.get("key_of", None)
                    
                    return jsonify({
                        'track_name': track_name,
                        'track_duration': track_duration,
                        'album_art_url': album_art_url,
                        'tempo': tempo,
                        'key': key_of,
                        'mode': 'Major' if 'M' in key_of else 'Minor' if key_of else None
                    })
        # Fetch additional audio features for the track
        #audio_features = sp.audio_features([track_id])[0]  # Spotify API returns a list

        # Extract key, tempo, and mode
        #key = audio_features.get('key', None)  # Key (0=C, 1=C#/Db, ..., 11=B)
        #tempo = audio_features.get('tempo', None)  # Tempo (BPM)
        #mode = audio_features.get('mode', None)  # Mode (1=Major, 0=Minor)
        return jsonify({
            'track_name': track_name,
            'track_duration': track_duration,
            'album_art_url': album_art_url,
            'tempo': None,
            'key': None,
            'mode': None
        })
    return jsonify({'error': 'No track playing'})

@app.route('/stop_ab_repeat', methods=['POST', 'GET'])
def stop_ab_repeat():
    # Logic to stop the A-B repeat
    # This could involve resetting state variables, stopping playback, etc.
    global ab_repeat_active
    ab_repeat_active = False
    ab_repeat_active_event.clear()
    sp.pause_playback()
    return #render_template('index.html')

@app.route('/reset', methods=['POST', 'GET'])
def reset():
    global ab_repeat_active
    ab_repeat_active = False
    ab_repeat_active_event.clear()
    return #render_template('index.html')

@app.route('/get-playback_time', methods=['GET'])
def get_playback_time():
    playback = sp.current_playback()
    if playback and playback['progress_ms']:
        return playback['progress_ms']
    else:
        return


@app.route('/track_progress', methods=['GET'])
def track_progress():
    return jsonify({'progress_ms': get_playback_time()})



@app.route('/set_ab_repeat', methods=['POST'])
def set_ab_repeat():
    # Get start and end time from the request
    devices = sp.devices()
    if devices['devices']:
        for device in devices['devices']:
            print(f"Device ID: {device['id']} - Name: {device['name']} - Active: {device['is_active']}")
    else:
        print("No active devices found.")
    if devices['devices']:
        device_id = devices['devices'][0]['id']

    global ab_repeat_active
    ab_repeat_active = True
    ab_repeat_active_event.set() 
    data = request.get_json()
    start_time = int(float(data['start_time']) * 1000)  # Convert to ms
    end_time = int(float(data['end_time']) * 1000)     # Convert to ms
    delay_factor = float(data['repeat_delay']) 
    delay_time = delay_factor*(end_time-start_time)/1000
    # Validate times and start A-B repeat
    playback = sp.current_playback()
    print("Start")
    print(start_time) 
    print(end_time)
    print(playback['progress_ms'])

    while ab_repeat_active_event.is_set():
        playback = sp.current_playback()
        if not playback['is_playing']:
            sp.start_playback()
        if playback and playback['progress_ms']:
            playback_time = get_playback_time()
        if playback_time >= end_time:
            if delay_factor:
                sp.pause_playback() 
            sp.seek_track(start_time, device_id=device_id)
            if delay_factor:
                time.sleep(delay_time-1) 
            print(playback_time)
            playback_time = start_time
        if playback_time >= end_time and not playback['is_playing']:
            print("playback lost")
            ab_repeat_active_event.clear()
        if not delay_time:
            time.sleep(1)

    return jsonify({'status': f"A-B Repeat from {start_time} to {end_time} complete."})

async def sync_current_playback():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sp.current_playback)




@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    playlists = sp.current_user_playlists()
    playlists_info = [(pl['name'],pl['external_urls']['spotify']) for pl in playlists['items']]
    playlists_html = '<br>'.join([f'{name}: {url}' for name, url in playlists_info])

    return playlists_html



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

    