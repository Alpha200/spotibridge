import click
from spotipy import util


@click.command()
@click.option("--username", prompt=True)
@click.option("--client-id", prompt=True)
@click.option("--client-secret", prompt=True)
@click.option("--redirect_uri", default="http://localhost:17382/redirect")
def get_token(username, client_id, client_secret, redirect_uri):
    token = util.prompt_for_user_token(
        username,
        "user-read-playback-state",
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    click.echo("Aquired token: ")
    click.echo(token)


if __name__ == "__main__":
    get_token()
