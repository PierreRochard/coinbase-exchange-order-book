import asyncio
from datetime import datetime, timedelta

try:
    import ujson as json
except ImportError:
    import json
import pytz

from dateutil.tz import tzlocal
import requests
import websockets


minutes = 30
begin = datetime.now(tzlocal())
end = begin + timedelta(minutes=minutes)


def get_beginning_level_3():
    global beginning_level_3
    beginning_level_3 = requests.get('https://api.exchange.coinbase.com/products/BTC-USD/book?level=3').json()


def get_ending_level_3():
    global ending_level_3
    ending_level_3 = requests.get('https://api.exchange.coinbase.com/products/BTC-USD/book?level=3').json()


@asyncio.coroutine
def get_websocket_data():
    coinbase_websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
    yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')
    global messages
    global latencies
    messages = []
    latencies = {}
    while True:
        message = yield from coinbase_websocket.recv()
        message = json.loads(message)
        messages += [message]
        latencies[message['sequence']] = int((datetime.now(tzlocal()) -
                                              datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                              .replace(tzinfo=pytz.UTC)).microseconds)
        if datetime.now(tzlocal()) > end:
            return


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.call_later(10, get_beginning_level_3)
    loop.call_later(minutes*60-10, get_ending_level_3)
    loop.run_until_complete(get_websocket_data())
    global messages
    global beginning_level_3
    global ending_level_3
    global latencies

    first_sequence = beginning_level_3['sequence']
    last_sequence = ending_level_3['sequence']

    messages = [message for message in messages if first_sequence < message['sequence'] <= last_sequence]
    messages = sorted(messages, key=lambda k: k['sequence'])
    for message in messages:
        assert message['sequence'] == first_sequence + 1
        first_sequence = message['sequence']

    with open('latencies.json', 'w') as json_file:
        json.dump(latencies, json_file, indent=4, sort_keys=True)
    with open('messages.json', 'w') as json_file:
        json.dump(messages, json_file, indent=4, sort_keys=True)
    with open('beginning_level_3.json', 'w') as json_file:
        json.dump(beginning_level_3, json_file, indent=4, sort_keys=True)
    with open('ending_level_3.json', 'w') as json_file:
        json.dump(ending_level_3, json_file, indent=4, sort_keys=True)
