import os


class Config:
    MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
    MQTT_USER = os.getenv("MQTT_USER", None)
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)

    SPOTIFY_USERNAME = os.getenv('SPOTIFY_USERNAME', None)
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', None)
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', None)
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', "http://localhost:17382/redirect")
