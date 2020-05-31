from datetime import datetime, timedelta
from io import BytesIO
from typing import Tuple

import requests
from PIL import Image
from apscheduler.schedulers.blocking import BlockingScheduler
from packaging.version import Version
from spotipy import util, Spotify

from colorfinder import ColorFinder, color_filter_hue, color_filter_hue_brightness
from config import Config
from homie import HomieDevice, HomieNode, HomieProperty, HomieDataType
import paho.mqtt.client as mqtt


def format_seconds(seconds):
    minutes = int(seconds / 60)
    num_seconds = round(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return "{:02}:{:02}:{:03}".format(minutes, num_seconds, milliseconds)


class ColorScheduler:
    mqttc: mqtt.Client
    homie_device: HomieDevice

    def __init__(self):
        self.scheduler = BlockingScheduler()
        # self.color_finder = ColorFinder(color_filter_hue)
        self.color_finder = ColorFinder(color_filter_hue_brightness)
        self.current_track = None

        self.init_mqtt()
        self.init_homie_device()

        self.scheduler.add_job(
            self.update_job,
            'interval',
            (),
            id='job_updater',
            seconds=5
        )

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.homie_device.publish_config()

    def init_mqtt(self):
        self.mqttc = mqtt.Client()

        if Config.MQTT_USER is not None:
            self.mqttc.username_pw_set(Config.MQTT_USER, Config.MQTT_PASSWORD)

        self.mqttc.on_connect = self.on_connect

        self.mqttc.connect(Config.MQTT_HOST)
        self.mqttc.loop_start()

    def init_homie_device(self):
        homie_device = HomieDevice("spotibridge", self.mqttc)
        homie_device.name = "Spotibridge"
        homie_device.implementation = "SpotiBridge"
        homie_device.version = Version("4.0.0")
        homie_device.extensions = set()

        node = HomieNode("player", homie_device, True)
        node.name = "Player"
        node.type = "player"

        is_playing_property = HomieProperty("is-playing", node, True)
        is_playing_property.name = "Is Playing"
        is_playing_property.datatype = HomieDataType.BOOLEAN
        is_playing_property.value = False

        current_track_property = HomieProperty("track", node, True)
        current_track_property.name = "Track"
        current_track_property.datatype = HomieDataType.STRING
        current_track_property.value = ""

        dominant_album_color_property = HomieProperty("dominant-album-color", node, True)
        dominant_album_color_property.name = "Dominant album color"
        dominant_album_color_property.datatype = HomieDataType.COLOR
        dominant_album_color_property.format = "rgb"
        dominant_album_color_property.value = (0, 0, 0)

        self.homie_device = homie_device

    def start(self):
        self.scheduler.start()

    def update_job(self):
        def update_color_caller():
            self.set_color((0, 0, 0))

        token = util.prompt_for_user_token(
            Config.SPOTIFY_USERNAME,
            'user-read-playback-state',
            client_id=Config.SPOTIFY_CLIENT_ID,
            client_secret=Config.SPOTIFY_CLIENT_SECRET,
            redirect_uri=Config.SPOTIFY_REDIRECT_URI
        )

        sp = Spotify(auth=token)

        current_track = sp.current_user_playing_track()

        if current_track is None or not current_track['is_playing'] or current_track['item'] is None:
            job = self.scheduler.get_job('color_updater')

            if job is not None:
                job.remove()

            if job is not None or self.current_track is not None:
                self.set_color((0, 0, 0))
                self.set_is_playing(False)
                self.set_current_track_title("")

            return

        track_id = current_track['item']['id']

        if self.current_track is None:
            self.set_is_playing(True)

        if self.current_track != track_id:
            self.current_track = track_id

            cover_urls = current_track['item']['album']['images']
            cover_url = cover_urls[0]['url']

            response = requests.get(cover_url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))

            self.set_color(self.color_finder.get_most_prominent_color(image))
            self.set_current_track_title(current_track['item']['name'])

        # One cannot use this as this is not correct
        # now = datetime.fromtimestamp(current_track['timestamp'] / 1000)

        now = datetime.now()

        start_of_track = now - timedelta(milliseconds=current_track['progress_ms'])
        next_change = start_of_track + timedelta(milliseconds=current_track['item']['duration_ms'])

        self.scheduler.add_job(
            update_color_caller,
            'date',
            (),
            id="color_updater",
            run_date=next_change,
            replace_existing=True
        )

    def set_color(self, color: Tuple[int, int, int]) -> None:
        color_property = self.homie_device.nodes["player"].properties["dominant-album-color"]

        if color_property.value != color:
            color_property.value = color
            color_property.publish_value()

    def set_is_playing(self, is_playing: bool):
        is_playing_property = self.homie_device.nodes["player"].properties["is-playing"]

        if is_playing_property.value != is_playing:
            is_playing_property.value = is_playing
            is_playing_property.publish_value()

    def set_current_track_title(self, current_track_title: str):
        current_track_property = self.homie_device.nodes["player"].properties["track"]

        if current_track_property.value != current_track_title:
            current_track_property.value = current_track_title
            current_track_property.publish_value()


def main():
    color_scheduler = ColorScheduler()
    color_scheduler.start()


if __name__ == '__main__':
    main()
