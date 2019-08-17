from spotipy import util

username = ""
client_id = ""
client_secret = ""
redirect_uri = ""

token = util.prompt_for_user_token(
    username,
    'user-read-playback-state',
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri
)

print(token)
