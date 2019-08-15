from colorsys import hsv_to_rgb
from datetime import datetime, timedelta
from random import random

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
import paho.mqtt.client as mqtt
from spotipy import util, Spotify

client_id = '***REMOVED***'
client_secret = '***REMOVED***'
redirect_uri = 'http://localhost:17382/redirect'
mqtt_host = "192.168.178.206"


def format_seconds(seconds):
    minutes = int(seconds / 60)
    num_seconds = round(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return "{:02}:{:02}:{:03}".format(minutes, num_seconds, milliseconds)


class ColorScheduler:
    def __init__(self, token):
        self.sp = Spotify(auth=token)
        self.scheduler = BlockingScheduler()
        self.analysis = None
        self.mqttc = mqtt.Client()

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
        def update_color_caller():
            self.update_color()

        current_track = self.sp.current_user_playing_track()

        now = datetime.now()

        if current_track is None or not current_track['is_playing']:
            job = self.scheduler.get_job('color_updater')

            if job is not None:
                job.remove()

            print("No track playing")

            return

        track_id = current_track['item']['id']

        if self.analysis is None or self.analysis[1] != track_id:
            self.analysis = (self.sp.audio_analysis(track_id), track_id)

        start_of_track = now - timedelta(milliseconds=current_track['progress_ms'])
        progress_in_seconds = current_track['progress_ms'] / 1000

        sections = self.analysis[0]['sections']

        next_section = next((section for section in sections if progress_in_seconds < section['start']), None)

        if next_section is not None:
            print("Updating job!")

            next_change = start_of_track + timedelta(seconds=next_section['start'])
            self.scheduler.add_job(
                update_color_caller,
                'date',
                (),
                id="color_updater",
                run_date=next_change,
                replace_existing=True
            )

    def update_color(self):
        r, g, b = tuple(int(x * 255) for x in hsv_to_rgb(random(), 1.0, 1.0))
        color = "{},{},{}".format(r, g, b)
        self.mqttc.publish("homie/ledring/ring/color/set", color, qos=1)


def main():
    token = util.prompt_for_user_token(
        '***REMOVED***',
        'user-read-playback-state',
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri
    )

    color_scheduler = ColorScheduler(token)
    color_scheduler.start()


if __name__ == '__main__':
    main()
