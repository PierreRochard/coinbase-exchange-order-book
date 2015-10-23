import asyncio
from datetime import datetime
from decimal import Decimal
from trading import file_logger
from concurrent.futures import ThreadPoolExecutor
import argparse

try:
    import ujson as json
except ImportError:
    import json

import logging
from pprint import pformat
import random
from socket import gaierror
import time

from dateutil.tz import tzlocal
import requests
import websockets

from trading.exchange import exchange_api_url, exchange_auth
from trading.openorders import OpenOrders
from trading.spreads import Spreads
from orderbook.book import Book


ARGS = argparse.ArgumentParser(description='Coinbase Exchange bot.')
ARGS.add_argument('--c', action='store_true', dest='command_line', default=False, help='Command line output')
ARGS.add_argument('--t', action='store_true', dest='trading', default=False, help='Trade')

args = ARGS.parse_args()

order_book = Book()
open_orders = OpenOrders()
open_orders.cancel_all()
spreads = Spreads()


@asyncio.coroutine
def websocket_to_order_book():

    try:
        coinbase_websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
    except gaierror:
        file_logger.error('socket.gaierror - had a problem connecting to Coinbase feed')
        return

    yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')

    messages = []
    while True:
        message = yield from coinbase_websocket.recv()
        message = json.loads(message)
        messages += [message]
        if len(messages) > 20:
            break

    order_book.get_level3()
    open_orders.get_open_orders()

    [order_book.process_message(message) for message in messages if message['sequence'] > order_book.level3_sequence]

    while True:
        message = yield from coinbase_websocket.recv()
        if message is None:
            file_logger.error('Websocket message is None.')
            return False
        try:
            message = json.loads(message)
        except TypeError:
            file_logger.error('JSON did not load, see ' + str(message))
            return False
        if not order_book.process_message(message):
            print(pformat(message))
            return False
        if args.trading:
            if 'order_id' in message and message['order_id'] == open_orders.open_ask_order_id:
                if message['type'] == 'done':
                    open_orders.open_ask_order_id = None
                    open_orders.open_ask_price = None
                    open_orders.open_ask_status = None
                    open_orders.open_ask_rejections = 0.0
                else:
                    open_orders.open_ask_status = message['type']
            elif 'order_id' in message and message['order_id'] == open_orders.open_bid_order_id:
                if message['type'] == 'done':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    open_orders.open_bid_status = None
                    open_orders.open_bid_rejections = 0.0
                else:
                    open_orders.open_bid_status = message['type']
        elif args.command_line:
            max_bid = Decimal(order_book.bids.price_tree.max_key())
            min_ask = Decimal(order_book.asks.price_tree.min_key())
            print('Latency: {0:.6f} secs, '
                  'Min ask: {1:.2f}, Max bid: {2:.2f}, Spread: {3:.2f}'.format(
                ((datetime.now(tzlocal()) - order_book.last_time).microseconds * 1e-6),
                min_ask, max_bid, min_ask - max_bid), end='\r')


def manage_orders():
    time.sleep(10)
    while True:
        time.sleep(0.005)
        if order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key() < 0:
            file_logger.warn('Negative spread: {0}'.format(order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key()))
            continue
        if args.command_line:
            print('Last message: {0:.6f} secs, '
                  'Min ask: {1:.2f}, Max bid: {2:.2f}, Spread: {3:.2f}, '
                  'Your ask: {4:.2f}, Your bid: {5:.2f}, Your spread: {6:.2f}'.format(
                ((datetime.now(tzlocal()) - order_book.last_time).microseconds * 1e-6),
                order_book.asks.price_tree.min_key(), order_book.bids.price_tree.max_key(),
                order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key(),
                open_orders.float_open_ask_price, open_orders.float_open_bid_price,
                                  open_orders.float_open_ask_price - open_orders.float_open_bid_price), end='\r')

        if not open_orders.open_bid_order_id:
            size = Decimal(0.01)
            spreads.bid_spread = Decimal(round((random.randrange(15) + 6) / 100, 2))
            open_bid_price = Decimal(round(order_book.asks.price_tree.min_key() - Decimal(spreads.bid_spread)
                                           - Decimal(open_orders.open_bid_rejections), 2))
            if size*open_bid_price < open_orders.accounts['USD']['available']:
                order = {'size': str(size),
                         'price': str(open_bid_price),
                         'side': 'buy',
                         'product_id': 'BTC-USD',
                         'post_only': True}
                response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
                if 'status' in response.json() and response.json()['status'] == 'pending':
                    open_orders.open_bid_order_id = response.json()['id']
                    open_orders.open_bid_price = open_bid_price
                    open_orders.open_bid_rejections = 0.0
                    file_logger.info('new bid @ {0}'.format(open_bid_price))
                elif 'status' in response.json() and response.json()['status'] == 'rejected':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    open_orders.open_bid_rejections += 0.04
                    file_logger.warn('rejected: new bid @ {0}'.format(open_bid_price))
                elif 'message' in response.json() and response.json()['message'] == 'Insufficient funds':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    file_logger.warn('Insufficient USD')
                else:
                    file_logger.error('Unhandled response: {0}'.format(pformat(response.json())))
                continue

        if not open_orders.open_ask_order_id:
            size = Decimal(0.01)
            spreads.ask_spread = Decimal(round((random.randrange(15) + 6) / 100, 2))
            open_ask_price = Decimal(round(order_book.bids.price_tree.max_key() + Decimal(spreads.ask_spread)
                                           + Decimal(open_orders.open_ask_rejections), 2))
            if size*open_ask_price < open_orders.accounts['BTC']['available']:
                order = {'size': str(size),
                         'price': str(open_ask_price),
                         'side': 'sell',
                         'product_id': 'BTC-USD',
                         'post_only': True}
                response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
                if 'status' in response.json() and response.json()['status'] == 'pending':
                    open_orders.open_ask_order_id = response.json()['id']
                    open_orders.open_ask_price = open_ask_price
                    file_logger.info('new ask @ {0}'.format(open_ask_price))
                    open_orders.open_ask_rejections = 0
                elif 'status' in response.json() and response.json()['status'] == 'rejected':
                    open_orders.open_ask_order_id = None
                    open_orders.open_ask_price = None
                    open_orders.open_ask_rejections += 0.04
                    file_logger.warn('rejected: new ask @ {0}'.format(open_ask_price))
                elif 'message' in response.json() and response.json()['message'] == 'Insufficient funds':
                    open_orders.open_ask_order_id = None
                    open_orders.open_ask_price = None
                    file_logger.warn('Insufficient BTC')
                else:
                    file_logger.error('Unhandled response: {0}'.format(pformat(response.json())))
                continue

        if (open_orders.open_bid_order_id
            and not open_orders.open_bid_cancelled
            and Decimal(open_orders.open_bid_price) < round(order_book.asks.price_tree.min_key() -
                                                                Decimal(spreads.bid_adjustment_spread), 2)):
            file_logger.info('CANCEL: open bid {0} threshold {1} diff {2}'.format(
                Decimal(open_orders.open_bid_price),
                round(order_book.asks.price_tree.min_key() - Decimal(spreads.bid_adjustment_spread), 2),
                Decimal(open_orders.open_bid_price) - round(order_book.asks.price_tree.min_key() -
                                                            Decimal(spreads.bid_adjustment_spread), 2)))
            open_orders.cancel('bid')
            continue

        if (open_orders.open_ask_order_id
            and not open_orders.open_ask_cancelled
            and Decimal(open_orders.open_ask_price) > round(order_book.bids.price_tree.max_key() +
                                                                Decimal(spreads.ask_adjustment_spread), 2)):
            file_logger.info('CANCEL: open ask {0} threshold {1} diff {2}'.format(
                Decimal(open_orders.open_ask_price),
                round(order_book.bids.price_tree.max_key() - Decimal(spreads.ask_adjustment_spread), 2),
                Decimal(open_orders.open_ask_price) - round(order_book.bids.price_tree.max_key() +
                                                            Decimal(spreads.ask_adjustment_spread), 2)))
            open_orders.cancel('ask')
            continue


def update_balances():
    while True:
        open_orders.get_balances()
        time.sleep(30)


if __name__ == '__main__':
    if args.command_line:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('\n%(asctime)s, %(levelname)s, %(message)s'))
        stream_handler.setLevel(logging.INFO)
        file_logger.addHandler(stream_handler)
        command_line = True

    loop = asyncio.get_event_loop()
    if args.trading:
        executor = ThreadPoolExecutor(4)
        loop.run_in_executor(executor, manage_orders)
        loop.run_in_executor(executor, update_balances)
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
