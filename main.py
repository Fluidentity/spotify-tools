import os 
import time
import asyncio
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
#from concurrent.futures import ThreadPoolExecuter

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

client_id = 'f6933e657b4b4a538a2dce4502e9e9a4'

client_secret = '4fe640c3af47480caa70d7e4d5b03715'

redirect_uri='http://localhost:5000/callback'

scope = 'playlist-read-private, streaming, user-modify-playback-state, user-read-playback-state'

global ab_repeat_active
ab_repeat_active = False

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
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    return render_template('index.html')
    

@app.route('/get_track_info', methods=['GET'])
def get_track_info():
    # Get current track information
    playback = sp.current_playback()
    if playback and playback['is_playing']:
        track_name = playback['item']['name']
        track_duration = playback['item']['duration_ms'] / 1000  # Convert ms to seconds
        return jsonify({
            'track_name': track_name,
            'track_duration': track_duration
        })
    return jsonify({'error': 'No track playing'})

@app.route('/stop_ab_repeat', methods=['POST'])
def stop_ab_repeat():
    # Logic to stop the A-B repeat
    # This could involve resetting state variables, stopping playback, etc.
    global ab_repeat_active
    ab_repeat_active = False
    sp.pause_playback()
    return render_template('index.html')

@app.route('/reset', methods=['POST'])
def reset():
    global ab_repeat_active
    ab_repeat_active = False
    return render_template('index.html')

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
    data = request.get_json()
    start_time = int(float(data['start_time']) * 1000)  # Convert to ms
    end_time = int(float(data['end_time']) * 1000)     # Convert to ms

    # Validate times and start A-B repeat
    playback = sp.current_playback()
    print("Start")
    print(start_time) 
    print(end_time)
    print(playback['progress_ms'])

    while ab_repeat_active:
        playback = sp.current_playback()
        if not playback['is_playing']:
            sp.start_playback()
        if playback and playback['progress_ms']:
            playback_time = playback['progress_ms']
            #print(playback_time)
        if playback_time >= end_time:
            sp.seek_track(start_time, device_id=device_id)
            print(playback_time)
            playback_time = start_time                
        if not playback['is_playing']:
            print("playback lost")
            ab_repeat_active = False
        time.sleep(1)
    return jsonify({'status': f"A-B Repeat from {start_time} to {end_time} complete."})

async def sync_current_playback():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sp.current_playback)


@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return render_template('index.html')

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
    app.run(debug=True)

    