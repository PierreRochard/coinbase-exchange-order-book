import asyncio
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import argparse

import functools
import pytz
import requests
import sys
from quamash import QApplication, QEventLoop, QThreadExecutor

from aws_config import second_tier_connection
from gui.qt_interface import ApplicationWindow, MatchesCanvas, OrderbookCanvas
from information import monitor
from trading import file_logger as trading_file_logger, file_logger
from orderbook import file_logger as order_book_file_logger
import numpy
from trading.exchange import exchange_api_url, exchange_auth
from trading.strategies import vwap_buyer_strategy

try:
    import ujson as json
except ImportError:
    import json

import logging
from pprint import pformat
import random
import time

from dateutil.tz import tzlocal
import websockets

from trading.openorders import OpenOrders
from trading.spreads import Spreads
from orderbook.book import Book
# from trading.strategies import vwap_buyer_strategy



@asyncio.coroutine
def websocket_to_order_book():
    if args.fake_test:
        feed = "ws://localhost:8765"
    elif args.second_tier_feed:
        feed = second_tier_connection
    else:
        feed = "wss://ws-feed.exchange.coinbase.com"

    coinbase_websocket = yield from websockets.connect(feed)

    if args.second_tier_feed:
        yield from coinbase_websocket.send('subscribe')
    else:
        yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')

    messages = []
    while True:
        message = yield from coinbase_websocket.recv()
        message = json.loads(message)
        messages += [message]
        if len(messages) > 20 and not args.second_tier_feed:
            break
        elif len(messages) > 200 and args.second_tier_feed:
            break

    order_book.get_level3(fake_test=args.fake_test, last_sequence=int(messages[-1]['sequence']))

    [order_book.process_message(message) for message in messages if int(message['sequence']) > order_book.level3_sequence]
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
            raise Exception
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
            yield from vwap_buyer_strategy(order_book, open_orders)
        if args.command_line:
            yield from monitor(order_book, open_orders)
        if args.qt:
            yield from application_window.matches.update_figure(order_book.matches)
            # yield from application_window.orderbook.update_figure(order_book)
            with QThreadExecutor() as exec:
                yield from loop.run_in_executor(exec, functools.partial(OrderbookCanvas.update_figure,
                                                                        application_window.orderbook,
                                                                        deepcopy(order_book)))


@asyncio.coroutine
def update_balances():
    open_orders.cancel_all()
    future = loop.run_in_executor(None, functools.partial(requests.get, exchange_api_url + 'accounts', auth=exchange_auth))
    accounts_query = yield from future
    for account in accounts_query.json():
        open_orders.accounts[account['currency']] = account
    loop.call_later(180, asyncio.ensure_future, update_balances())


@asyncio.coroutine
def update_orders():
    yield from open_orders.get_open_orders(loop)
    loop.call_later(60, asyncio.ensure_future, update_orders())


@asyncio.coroutine
def update_vwap():
    order_book.vwap = 20
    loop.call_later(60, asyncio.ensure_future, update_vwap())


if __name__ == '__main__':
    ARGS = argparse.ArgumentParser(description='Coinbase Exchange bot.')
    ARGS.add_argument('--c', action='store_true', dest='command_line', default=False, help='Command line output')
    ARGS.add_argument('--t', action='store_true', dest='trading', default=False, help='Trade')
    ARGS.add_argument('--d', action='store_true', dest='debug', default=False, help='Debugging')
    ARGS.add_argument('--f', action='store_true', dest='fake_test', default=False, help='Fake test')
    ARGS.add_argument('-2', action='store_true', dest='second_tier_feed', default=False, help='Second tier feed')
    ARGS.add_argument('--q', action='store_true', dest='qt', default=False, help='QT')

    args = ARGS.parse_args()

    order_book = Book()
    order_book.populate_matches()
    open_orders = OpenOrders()
    open_orders.cancel_all()
    spreads = Spreads()

    if args.command_line:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('\n%(asctime)s, %(levelname)s, %(message)s'))
        stream_handler.setLevel(logging.INFO)
        trading_file_logger.addHandler(stream_handler)
        order_book_file_logger.addHandler(stream_handler)
        command_line = True

    if args.qt:
        app = QApplication(sys.argv)
        application_window = ApplicationWindow()
        application_window.show()
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    loop.set_debug(args.debug)

    if args.trading:
        loop.call_soon(asyncio.ensure_future, update_balances())
        loop.call_soon(asyncio.ensure_future, update_orders())
        loop.call_soon(asyncio.ensure_future, update_vwap())
    else:
        n = 0
        while True:
            start_time = loop.time()
            try:
                loop.run_until_complete(websocket_to_order_book())
            except:
                pass
            end_time = loop.time()
            seconds = end_time - start_time
            if seconds < 2:
                n += 1
                sleep_time = (2 ** n) + (random.randint(0, 1000) / 1000)
                order_book_file_logger.error('Websocket connectivity problem, going to sleep for {0}'.format(sleep_time))
                time.sleep(sleep_time)
                if n > 6:
                    n = 0
