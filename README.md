# Spotibrige

Bridge that publishes some infos about the current running Spotify track as homie device.

## Requirements

* A Spotify premium account
* An app, registered at `https://developer.spotify.com/dashboard/`
* A MQTT server

## Usage

1. Use the `get_token.py` to aquire a token for your spotify account
which is needed to request infos about the current running track. This will
generate a file with the name `.cache-<you-email>` in the working directory.

2. You have to mount this file into the docker container. Look into `docker-compose.example.yml`
to see an example how to run the container.

## Homie device structure

The exposed homie device is structured as follows:

* player
  * is-playing - Flag that is true if some track is playing
  * track - The name of the current playing track
  * dominant-album-color - The dominant color of the album cover of the current playing track, chosen based on hue and brightness.
