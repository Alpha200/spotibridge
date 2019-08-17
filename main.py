import math
import os

from colorsys import hsv_to_rgb, rgb_to_hsv
from datetime import datetime, timedelta
from io import BytesIO

import requests
from PIL import Image
from apscheduler.schedulers.blocking import BlockingScheduler
import paho.mqtt.client as mqtt
from spotipy import util, Spotify

from colorfinder import ColorFinder, color_filter_hue

username = os.environ['SPOTIFY_USERNAME']
client_id = os.environ['SPOTIFY_CLIENT_ID']
client_secret = os.environ['SPOTIFY_CLIENT_SECRET']
redirect_uri = os.environ['SPOTIFY_REDIRECT_URI']
mqtt_host = os.environ['MQTT_HOST']
mqtt_topic = os.environ['MQTT_TOPIC']


def format_seconds(seconds):
    minutes = int(seconds / 60)
    num_seconds = round(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return "{:02}:{:02}:{:03}".format(minutes, num_seconds, milliseconds)


class ColorScheduler:
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.color_finder = ColorFinder(color_filter_hue)
        self.analysis = None
        self.mqttc = mqtt.Client()
        self.current_hue = 0
        self.current_s = 0

        self.mqttc.connect(mqtt_host)
        self.mqttc.loop_start()

        def update_job_caller():
            self.update_job()

        self.scheduler.add_job(
            update_job_caller,
            'interval',
            (),
            id='job_updater',
            seconds=5
        )

    def start(self):
        self.scheduler.start()

    def update_job(self):
        def update_color_caller(section):
            self.update_color(section)

        token = util.prompt_for_user_token(
            username,
            'user-read-playback-state',
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri
        )

        sp = Spotify(auth=token)

        before = datetime.now()
        current_track = sp.current_user_playing_track()
        now = datetime.now()
        difference = (now - before) / 2
        now = before + difference

        if current_track is None or not current_track['is_playing']:
            job = self.scheduler.get_job('color_updater')

            if job is not None:
                job.remove()
                self.mqttc.publish(mqtt_topic, "0,0,0", qos=1)

                print("No track playing")

            return

        track_id = current_track['item']['id']

        if self.analysis is None or self.analysis[1] != track_id:
            self.analysis = (sp.audio_analysis(track_id), track_id)

            cover_urls = current_track['item']['album']['images']
            cover_url = cover_urls[len(cover_urls) - 1]['url']

            response = requests.get(cover_url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))

            r, g, b = self.color_finder.get_most_prominent_color(image)
            h, s, v = rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            self.current_hue = h
            self.current_s = s

            print("H: {}, S: {}, V: {}".format(h, s, v))

            self.update_color(self.analysis[0]['sections'][0])

        start_of_track = now - timedelta(milliseconds=current_track['progress_ms'])
        progress_in_seconds = current_track['progress_ms'] / 1000

        sections = self.analysis[0]['sections']

        next_section = next((section for section in sections if progress_in_seconds < section['start']), None)

        if next_section is not None:
            next_change = start_of_track + timedelta(seconds=next_section['start'])
        else:
            next_change = start_of_track + timedelta(seconds=self.analysis[0]['track']['duration'])

        print('Next change: {}'.format(next_change))

        self.scheduler.add_job(
            update_color_caller,
            'date',
            (next_section,),
            id="color_updater",
            run_date=next_change,
            replace_existing=True
        )

    def update_color(self, section):
        if section is not None:
            brightness = max(0.1, min(1.0, (15.0 - (section['loudness'] * -1 - 5.0)) / 15))
        else:
            brightness = 0.1

        print("New brightness: {}".format(brightness))
        r, g, b = tuple(int(x * 255) for x in hsv_to_rgb(self.current_hue, math.sqrt(self.current_s), brightness))

        color = "{},{},{}".format(r, g, b)
        self.mqttc.publish(mqtt_topic, color, qos=1)


def main():
    color_scheduler = ColorScheduler()
    color_scheduler.start()


if __name__ == '__main__':
    main()
