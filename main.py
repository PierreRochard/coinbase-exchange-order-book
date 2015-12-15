import asyncio
from datetime import datetime
from decimal import Decimal
import argparse

import aiohttp

import functools
import pytz
import requests
from trading import file_logger as trading_file_logger, file_logger
from orderbook import file_logger as order_book_file_logger
import numpy
from trading.exchange import exchange_api_url, exchange_auth

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

ARGS = argparse.ArgumentParser(description='Coinbase Exchange bot.')
ARGS.add_argument('--c', action='store_true', dest='command_line', default=False, help='Command line output')
ARGS.add_argument('--t', action='store_true', dest='trading', default=False, help='Trade')
ARGS.add_argument('--d', action='store_true', dest='debug', default=False, help='Debugging')
ARGS.add_argument('--f', action='store_true', dest='fake_test', default=False, help='Fake test')

args = ARGS.parse_args()

order_book = Book()
order_book.populate_matches()
open_orders = OpenOrders()
open_orders.cancel_all()
spreads = Spreads()


@asyncio.coroutine
def websocket_to_order_book():
    if args.fake_test:
        feed = "ws://localhost:8765"
    else:
        feed = "wss://ws-feed.exchange.coinbase.com"

    coinbase_websocket = yield from websockets.connect(feed)

    yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')

    messages = []
    while True:
        message = yield from coinbase_websocket.recv()
        message = json.loads(message)
        messages += [message]
        if len(messages) > 20:
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
            yield from vwap_buyer_strategy()
        if args.command_line:
            yield from monitor()


@asyncio.coroutine
def update_balances():
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


@asyncio.coroutine
def monitor():
    vwap = order_book.vwap
    print('Last message: {0:.6f} secs, '
          'Min ask: {1:.2f}, Max bid: {2:.2f}, Spread: {3:.2f}, '
          'VWAP: {4:.2f}, Bid: {5:.2f}, Spread: {6:.2f}, '
          'Avg: {7:.4f}'.format(
        ((datetime.now(tzlocal()) - order_book.last_time).microseconds * 1e-6),
        order_book.asks.price_tree.min_key(),
        order_book.bids.price_tree.max_key(),
        order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key(),
        vwap,
        open_orders.decimal_open_bid_price,
        open_orders.decimal_open_bid_price - vwap,
        order_book.average_rate*1e-6), end='\r')


@asyncio.coroutine
def vwap_buyer_strategy():
    if not open_orders.open_bid_order_id:
        vwap = order_book.vwap
        best_bid = order_book.bids.price_tree.max_key()
        vwap_bid = round(vwap * Decimal('0.99') - open_orders.open_bid_rejections, 2)
        if vwap_bid <= best_bid and 0.01 * float(vwap_bid) < float(open_orders.accounts['USD']['available']):
            order = {'size': '0.01',
                     'price': str(vwap_bid),
                     'side': 'buy',
                     'product_id': 'BTC-USD',
                     'post_only': True}
            future = loop.run_in_executor(None, functools.partial(requests.post, exchange_api_url + 'orders',
                                                                  json=order, auth=exchange_auth))
            response = yield from future
            try:
                response = response.json()
            except ValueError:
                file_logger.error('Unhandled response: {0}'.format(pformat(response)))
            if 'status' in response and response['status'] == 'pending':
                open_orders.open_bid_order_id = response['id']
                open_orders.open_bid_price = vwap_bid
                open_orders.open_bid_rejections = Decimal('0.0')
                file_logger.info('new bid @ {0}'.format(vwap_bid))
            elif 'status' in response and response['status'] == 'rejected':
                open_orders.open_bid_order_id = None
                open_orders.open_bid_price = None
                open_orders.open_bid_rejections += Decimal('0.04')
                file_logger.warn('rejected: new bid @ {0}'.format(vwap_bid))
            elif 'message' in response and response['message'] == 'Insufficient funds':
                open_orders.open_bid_order_id = None
                open_orders.open_bid_price = None
                file_logger.warn('Insufficient USD')
            elif 'message' in response and response['message'] == 'request timestamp expired':
                open_orders.open_bid_order_id = None
                open_orders.open_bid_price = None
                file_logger.warn('Request timestamp expired')
            else:
                file_logger.error('Unhandled response: {0}'.format(pformat(response)))

    if open_orders.open_bid_order_id and not open_orders.open_bid_cancelled:
        vwap = order_book.vwap
        vwap_adj = round(vwap * Decimal('0.985'), 2)
        bid_too_far_out = open_orders.open_bid_price < vwap_adj
        if bid_too_far_out:
            file_logger.info('CANCEL: open bid {0} too far from best bid: {1} spread: {2}'.format(
                open_orders.open_bid_price,
                order_book.bids.price_tree.max_key(),
                order_book.bids.price_tree.max_key() - open_orders.open_bid_price))
            yield from open_orders.cancel(loop, 'bid')


if __name__ == '__main__':
    if args.command_line:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('\n%(asctime)s, %(levelname)s, %(message)s'))
        stream_handler.setLevel(logging.INFO)
        trading_file_logger.addHandler(stream_handler)
        order_book_file_logger.addHandler(stream_handler)
        command_line = True

    loop = asyncio.get_event_loop()
    loop.set_debug(args.debug)

    if args.trading:
        loop.call_soon(asyncio.ensure_future, update_balances())
        loop.call_soon(asyncio.ensure_future, update_orders())
        loop.call_soon(asyncio.ensure_future, update_vwap())

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
