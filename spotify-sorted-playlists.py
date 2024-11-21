#!/usr/bin/env python3

import sys
import os
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime

from config import *

################################################################################

class SpotifyApp:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, scope: str, open_browser: bool = True):
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                                            client_secret=client_secret,
                                                            redirect_uri=redirect_uri,
                                                            scope=scope,
                                                            open_browser=open_browser))

    def get_artist(self, artist_id: str):
        artist = self.cached(self.sp.artist, 'spotify:artist:' + artist_id)
        #print(artist)
        return artist

    def get_artist_albums(self, artist_id: str, album_type: str = 'album'):
        albums = self.cached(self.sp.artist_albums, 'spotify:artist:' + artist_id, album_type=album_type, limit=50)
        #print(albums)
        return albums

    def get_album_tracks(self, album_id: str):
        tracks = self.cached(self.sp.album_tracks, 'spotify:album:' + album_id, limit=50)
        #print(tracks)
        return tracks

    def get_track_features(self, track_id: str):
        features = self.cached(self.sp.audio_features, 'spotify:track:' + track_id)
        #print(features)
        return features

    def clear_playlist(self, playlist_id):
        playlist = self.sp.playlist_replace_items('spotify:playlist:' + playlist_id, [])
        #print(playlist)

    def add_to_playlist(self, playlist_id: str, items: list):
        playlist = self.sp.playlist_add_items('spotify:playlist:' + playlist_id, items)
        #print(playlist)

    def update_playlist(self, playlist_id: str, items: list, name: str, description: str = "", public: bool = True):
        self.clear_playlist(playlist_id)
        for chunk_items in self.__chunks(items, 50):  # Break this down into chunks to avoid API error
            self.add_to_playlist(playlist_id, chunk_items)

        playlist = self.sp.playlist_change_details('spotify:playlist:' + playlist_id, name=name, description=description, public=public)
        #print(playlist)
        return playlist

    @staticmethod
    def __chunks(lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def cached(self, functor, id, *args, **kwargs):
        call_hash = hash(args) + hash(frozenset(kwargs.items()))  # Also include arguments in filename hash
        file_name = os.path.join(CACHE_PATH, f'{id}-{call_hash}.json'.replace(':', '_'))

        #print(file_name)
        if os.path.exists(file_name):
            with open(file_name, 'r') as f:
                return json.load(f)

        result = functor(id, *args, **kwargs)
        with open(file_name, 'w') as f:
            json.dump(result, f)
        return result

################################################################################

def is_in_blacklist(name):
    for word in BLACKLIST_WORDS:
        if word.lower() in name.lower():
            return True
    return False

if __name__ == "__main__":

    now_date = datetime.now().strftime('%Y-%m-%d')

    ### Create app

    app = SpotifyApp(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, scope='playlist-modify-public')

    ### Get artist's information

    artist = app.get_artist(ARTIST_ID)

    artist_name = artist['name']
    print(f"==> Found artist: {artist_name}")

    ### Get artist's albums

    albums = app.get_artist_albums(ARTIST_ID)
    album_list = dict()

    print(f"==> Found {len(albums['items'])} albums:")
    for album_number, album in enumerate(albums['items']):
        album_name = album['name']
        if is_in_blacklist(album_name): continue
        print(f"\t{album_name}")

        # Extend album data
        album_id = album['id']
        album['album_number'] = album_number
        album_list[album_id] = album

    # ### Get album tracks

    track_list = dict()

    for album_id, album in album_list.items():
        album_name = album['name']
        album_tracks = app.get_album_tracks(album_id)

        print(f"==> Found {len(album_tracks['items'])} tracks on album <{album_name}>:")
        for track_number, track in enumerate(album_tracks['items']):
            track_name = track['name']
            if is_in_blacklist(track_name): continue
            print(f"\t{album_name} - {track_name}")

            track_id = track['id']
            track_list[track_id] = track

            # Extend track data
            track['album'] = album
            track['track_number'] = track_number
            track['features'] = app.get_track_features(track_id)  # Includes info like tempo, danceability


    # ### Sort list of all tracks, for each playlist

    for playlist_type, (playlist_id, sort_fn, filter_fn) in PLAYLIST_IDS.items():

        sorted_tracks = list(filter(filter_fn, track_list.values()))
        if sort_fn:
            sorted_tracks.sort(key=sort_fn)

        print()
        print(f"** Track list: {playlist_type} **")
        total_length = 0
        for index, track in enumerate(sorted_tracks, start=1):
            track_name = track['name']
            album_name = album_list[track['album']['id']]['name']

            track_length = track['duration_ms'] / 1000.
            total_length += track_length
            mins, secs = divmod(track_length, 60)
            print(f"  {index}. {track_name} ~ {mins:.0f}:{secs:02.0f} mins")

        playlist_items = [ f"spotify:track:{track['id']}" for track in sorted_tracks ]

        hours, _rem = divmod(total_length, 3660)
        mins, secs = divmod(_rem, 60)

        playlist_name = f"{artist_name} {playlist_type} *auto-generated*"
        playlist_info = f"All album tracks by {artist_name}, {playlist_type}. {len(album_list)} albums, {len(sorted_tracks)} tracks, {hours:.0f}:{mins:02.0f}:{secs:02.0f} hours runtime. Updated {now_date}."

        app.update_playlist(playlist_id, items=playlist_items, name=playlist_name, description=playlist_info)

        print(f"==> Updated playlist <{playlist_name}>: {playlist_info}")
