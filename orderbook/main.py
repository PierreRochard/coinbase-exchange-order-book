import asyncio
from collections import deque
from dateutil.parser import parse
from decimal import Decimal
import json
import logging
from logging.handlers import RotatingFileHandler
from pprint import pformat
from orderbook.exchange import exchange_api_url, exchange_auth
import random
from socket import gaierror
import time

import requests
import websockets

from orderbook.tree import Tree


class Book(object):
    def __init__(self):
        self.matches = deque(maxlen=100)
        self.bids = Tree()
        self.asks = Tree()


file_logger = logging.getLogger('file_log')
file_handler = RotatingFileHandler('log.csv', 'a', 10 * 1024 * 1024, 100)
file_handler.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
file_handler.setLevel(logging.INFO)
file_logger.addHandler(file_handler)

quote_book = Book()


@asyncio.coroutine
def websocket_to_order_book():
    try:
        websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
    except gaierror:
        file_logger.error('socket.gaierror - had a problem connecting to Coinbase feed')
        return
    yield from websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')

    last_sequence = None
    level_3 = None

    open_bid_order_id = None
    open_bid_price = None

    open_ask_order_id = None
    open_ask_price = None

    insufficient_btc = False
    insufficient_usd = False

    r = requests.get(exchange_api_url + 'orders', auth=exchange_auth)
    orders = r.json()
    try:
        open_bid_order_id = [order['id'] for order in orders if order['side'] == 'buy'][0]
        open_bid_price = [order['price'] for order in orders if order['side'] == 'buy'][0]
    except IndexError:
        pass
    try:
        open_ask_order_id = [order['id'] for order in orders if order['side'] == 'sell'][0]
        open_ask_price = [order['price'] for order in orders if order['side'] == 'sell'][0]
    except IndexError:
        pass

    while True:
        message = yield from websocket.recv()

        if not level_3:
            level_3 = requests.get('http://api.exchange.coinbase.com/products/BTC-USD/book',
                                   params={'level': 3}).json()
            for bid in level_3['bids']:
                quote_book.bids.insert(bid[2], Decimal(bid[1]), Decimal(bid[0]))
            for ask in level_3['asks']:
                quote_book.asks.insert(ask[2], Decimal(ask[1]), Decimal(ask[0]))

        if message is None:
            file_logger.error('Websocket message is None!')
            raise Exception()

        try:
            message = json.loads(message)
        except TypeError:
            file_logger.error('JSON did not load, see ' + str(message))
            continue

        new_sequence = int(message['sequence'])
        if not last_sequence:
            last_sequence = int(message['sequence'])
        else:
            if (new_sequence - last_sequence - 1) != 0:
                print('sequence gap: {0}'.format(new_sequence - last_sequence))
            last_sequence = new_sequence

        message_type = message['type']

        if message_type == 'received':
            continue

        message_time = parse(message['time'])
        side = message['side']
        if 'order_id' in message:
            order_id = message['order_id']
        if 'maker_order_id' in message:
            maker_order_id = message['maker_order_id']
        if 'price' in message:
            price = Decimal(message['price'])
        if 'remaining_size' in message:
            remaining_size = Decimal(message['remaining_size'])
        if 'size' in message:
            size = Decimal(message['size'])
        if 'new_size' in message:
            new_size = Decimal(message['new_size'])

        if message_type == 'open' and side == 'buy':
            quote_book.bids.insert(order_id, remaining_size, price)
        elif message_type == 'open' and side == 'sell':
            quote_book.asks.insert(order_id, remaining_size, price)

        elif message_type == 'match' and side == 'buy':
            quote_book.bids.match(maker_order_id, size)
            quote_book.matches.appendleft((message_time, side, size, price))
        elif message_type == 'match' and side == 'sell':
            quote_book.asks.match(maker_order_id, size)
            quote_book.matches.appendleft((message_time, side, size, price))

        elif message_type == 'done' and side == 'buy':
            quote_book.bids.remove_order(order_id)
            if order_id == open_bid_order_id:
                open_bid_order_id = None
                insufficient_btc = False
        elif message_type == 'done' and side == 'sell':
            quote_book.asks.remove_order(order_id)
            if order_id == open_ask_order_id:
                open_ask_order_id = None
                insufficient_usd = False

        elif message_type == 'change' and side == 'buy':
            quote_book.bids.change(order_id, new_size)
        elif message_type == 'change' and side == 'sell':
            quote_book.asks.change(order_id, new_size)

        else:
            print(pformat(message))

        if not open_bid_order_id and not insufficient_usd:
            if insufficient_btc:
                size = 0.03
            else:
                size = 0.01
            open_bid_price = round(quote_book.asks.max() - Decimal(0.04), 2)
            order = {'size': size,
                     'price': str(open_bid_price),
                     'side': 'buy',
                     'product_id': 'BTC-USD',
                     'post_only': True}
            response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
            response = response.json()
            print(pformat(response))
            if 'id' in response:
                open_bid_order_id = response['id']
                if response['status'] == 'rejected':
                    open_bid_order_id = None
            elif 'message' in response:
                if response['message'] == 'Insufficient funds':
                    insufficient_usd = True

        if not open_ask_order_id and not insufficient_btc:
            if insufficient_usd:
                size = 0.03
            else:
                size = 0.01
            open_ask_price = round(quote_book.bids.min() + Decimal(0.04), 2)
            order = {'size': size,
                     'price': str(open_ask_price),
                     'side': 'sell',
                     'product_id': 'BTC-USD',
                     'post_only': True}
            response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
            response = response.json()
            print(pformat(response))
            if 'id' in response:
                open_ask_order_id = response['id']
                if response['status'] == 'rejected':
                    open_ask_order_id = None
            elif 'message' in response:
                if response['message'] == 'Insufficient funds':
                    insufficient_btc = True

        if Decimal(open_bid_price) < round(quote_book.asks.max() - Decimal(0.06), 2) and open_bid_order_id:
            response = requests.delete(exchange_api_url + 'orders/' + open_bid_order_id, auth=exchange_auth)
            if response.status_code == 200:
                open_bid_order_id = None
            else:
                response = response.json()
                if 'message' in response:
                    if response['message'] == 'Order already done':
                        open_bid_order_id = None
                else:
                    print(pformat(response.json()))

        if Decimal(open_ask_price) > round(quote_book.bids.min() + Decimal(0.06), 2) and open_ask_order_id:
            response = requests.delete(exchange_api_url + 'orders/' + open_ask_order_id, auth=exchange_auth)
            if response.status_code == 200:
                open_ask_order_id = None
            else:
                response = response.json()
                if 'message' in response:
                    if response['message'] == 'Order already done':
                        open_ask_order_id = None
                else:
                    print(pformat(response.json()))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    n = 0
    while True:
        start_time = loop.time()
        loop.run_until_complete(websocket_to_order_book())
        end_time = loop.time()
        seconds = end_time - start_time
        if seconds < 2:
            n += 1
            sleep_time = (2 ** n) + (random.randint(0, 1000) / 1000)
            file_logger.error('Websocket connectivity problem, going to sleep for {0}'.format(sleep_time))
            time.sleep(sleep_time)
            if n > 6:
                n = 0
