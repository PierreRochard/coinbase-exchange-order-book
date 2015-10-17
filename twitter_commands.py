from datetime import datetime, timedelta
from pprint import pformat
import threading
from subprocess import call
import subprocess

from dateutil.parser import parse
from dateutil.tz import tzutc
import requests
from twython import Twython

from trading.exchange import exchange_api_url, exchange_auth
from twitter_config import APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET, AUTHORIZED_USER


twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

minutes = 7


def run():
    now = datetime.now(tzutc())
    period_beg = now - timedelta(minutes=minutes)

    direct_messages = twitter.get_direct_messages()
    direct_messages = [message for message in direct_messages if parse(message['created_at']) > period_beg
                       and message['sender_screen_name'] == AUTHORIZED_USER]
    for message in direct_messages:
        if message['text'] == 'restart' or message['text'] == 'r':
            command = "supervisorctl restart coinbase"
        else:
            command = message['text']
        result = subprocess.Popen(command, shell=True,
                                  stdout=subprocess.PIPE).stdout.read()
        twitter.send_direct_message(screen_name=AUTHORIZED_USER,
                                    text=result)
    threading.Timer(60 * minutes, run).start()

if __name__ == '__main__':
    threading.Timer(1, run).start()
