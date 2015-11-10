import asyncio
from datetime import datetime
from decimal import Decimal
import argparse

import functools
import pytz
from trading import file_logger as trading_file_logger
from orderbook import file_logger as order_book_file_logger
import numpy

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
import websockets

from trading.openorders import OpenOrders
from trading.spreads import Spreads
from orderbook.book import Book
from trading.strategies import vwap_buyer_strategy

ARGS = argparse.ArgumentParser(description='Coinbase Exchange bot.')
ARGS.add_argument('--c', action='store_true', dest='command_line', default=False, help='Command line output')
ARGS.add_argument('--t', action='store_true', dest='trading', default=False, help='Trade')
args = ARGS.parse_args()

order_book = Book()
order_book.populate_matches()
open_orders = OpenOrders()
open_orders.cancel_all()
spreads = Spreads()


@asyncio.coroutine
def websocket_to_order_book():
    try:
        coinbase_websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
    except gaierror:
        order_book_file_logger.error('socket.gaierror - had a problem connecting to Coinbase feed')
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

    [order_book.process_message(message) for message in messages if message['sequence'] > order_book.level3_sequence]
    messages = []
    while True:
        message = yield from coinbase_websocket.recv()
        if message is None:
            order_book_file_logger.error('Websocket message is None.')
            return False
        try:
            message = json.loads(message)
        except TypeError:
            order_book_file_logger.error('JSON did not load, see ' + str(message))
            return False
        if args.command_line:
            messages += [datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)]
            messages = [message for message in messages if (datetime.now(tzlocal()) - message).seconds < 60]
            if len(messages) > 2:
                diff = numpy.diff(messages)
                diff = [float(sec.microseconds) for sec in diff]
                order_book.average_rate = numpy.mean(diff)
                order_book.fastest_rate = min(diff)
                order_book.slowest_rate = max(diff)
        if not order_book.process_message(message):
            print(pformat(message))
            return False
        if args.trading:
            if 'order_id' in message and message['order_id'] == open_orders.open_ask_order_id:
                if message['type'] == 'done':
                    open_orders.open_ask_order_id = None
                    open_orders.open_ask_price = None
                    open_orders.open_ask_status = None
                    open_orders.open_ask_rejections = Decimal('0.0')
                    open_orders.open_ask_cancelled = False
                else:
                    open_orders.open_ask_status = message['type']
            elif 'order_id' in message and message['order_id'] == open_orders.open_bid_order_id:
                if message['type'] == 'done':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    open_orders.open_bid_status = None
                    open_orders.open_bid_rejections = Decimal('0.0')
                    open_orders.open_bid_cancelled = False
                else:
                    open_orders.open_bid_status = message['type']


def update_balances():
    while True:
        open_orders.get_balances()
        time.sleep(30)


def update_orders():
    time.sleep(5)
    open_orders.cancel_all()
    while True:
        open_orders.get_open_orders()
        time.sleep(60*5)


def monitor():
    time.sleep(5)
    while True:
        time.sleep(1)
        vwap = order_book.vwap(20)
        print('Last message: {0:.6f} secs, '
              'Min ask: {1:.2f}, Max bid: {2:.2f}, Spread: {3:.2f}, '
              'VWAP: {4:.2f}, Bid: {5:.2f}, Spread: {6:.2f}, '
              'Avg: {7:.10f} Min: {8:.10f} Max: {9:.10f}'.format(
            ((datetime.now(tzlocal()) - order_book.last_time).microseconds * 1e-6),
            order_book.asks.price_tree.min_key(),
            order_book.bids.price_tree.max_key(),
            order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key(),
            vwap,
            open_orders.decimal_open_bid_price,
            open_orders.decimal_open_bid_price - vwap,
            order_book.average_rate*1e-6,
            order_book.fastest_rate*1e-6,
            order_book.slowest_rate*1e-6), end='\r')


if __name__ == '__main__':
    if args.command_line:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('\n%(asctime)s, %(levelname)s, %(message)s'))
        stream_handler.setLevel(logging.INFO)
        trading_file_logger.addHandler(stream_handler)
        order_book_file_logger.addHandler(stream_handler)
        command_line = True

    loop = asyncio.get_event_loop()
    if args.trading:
        loop.run_in_executor(None, functools.partial(vwap_buyer_strategy, order_book, open_orders))
        loop.run_in_executor(None, update_balances)
        loop.run_in_executor(None, update_orders)
    if args.command_line:
        loop.run_in_executor(None, monitor)
    n = 0
    while True:
        start_time = loop.time()
        loop.run_until_complete(websocket_to_order_book())
        end_time = loop.time()
        seconds = end_time - start_time
        if seconds < 2:
            n += 1
            sleep_time = (2 ** n) + (random.randint(0, 1000) / 1000)
            order_book_file_logger.error('Websocket connectivity problem, going to sleep for {0}'.format(sleep_time))
            time.sleep(sleep_time)
            if n > 6:
                n = 0
