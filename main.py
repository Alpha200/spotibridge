from spotipy import util, Spotify

client_id = '***REMOVED***'
client_secret = '***REMOVED***'
redirect_uri = 'http://localhost:17382/redirect'


def format_seconds(seconds):
    minutes = int(seconds / 60)
    num_seconds = round(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return "{:02}:{:02}:{:03}".format(minutes, num_seconds, milliseconds)


def main():
    token = util.prompt_for_user_token(
        '***REMOVED***',
        'user-read-playback-state',
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri
    )

    sp = Spotify(auth=token)

    current_track = sp.current_user_playing_track()

    if current_track is None:
        print("No track is being played!")
        return

    print("Track: {}".format(current_track['item']['name']))

    track_id = current_track['item']['id']

    analysis = sp.audio_analysis(track_id)

    print("Duration: {}".format(format_seconds(analysis['track']['duration'])))
    print("Fade In: {}".format(format_seconds(analysis['track']['end_of_fade_in'])))
    print("Fade Out: {}".format(format_seconds(analysis['track']['start_of_fade_out'])))
    print()

    for section in analysis['sections']:
        print("Start: {}".format(format_seconds(section['start'])))
        print("Confidence: {}".format(section['confidence']))
        print("Loudness: {}".format(section['loudness']))
        print("Tempo: {}".format(section['tempo']))
        print()


if __name__ == '__main__':
    main()
