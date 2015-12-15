import asyncio
from pprint import pformat
from decimal import Decimal

import functools

import requests

from trading import file_logger
from trading.exchange import exchange_api_url, exchange_auth


class OpenOrders(object):
    def __init__(self):
        self.accounts = {}

        self.open_bid_order_id = None
        self.open_bid_price = None
        self.open_bid_status = None
        self.open_bid_cancelled = False
        self.open_bid_rejections = Decimal('0.0')

        self.open_ask_order_id = None
        self.open_ask_price = None
        self.open_ask_status = None
        self.open_ask_cancelled = False
        self.open_ask_rejections = Decimal('0.0')

    def cancel_all(self):
        if self.open_bid_order_id:
            self.cancel('bid')
        if self.open_ask_order_id:
            self.cancel('ask')

    @asyncio.coroutine
    def cancel(self, loop, side):
        if side == 'bid':
            order_id = self.open_bid_order_id
            price = self.open_bid_price
            self.open_bid_cancelled = True
        elif side == 'ask':
            order_id = self.open_ask_order_id
            price = self.open_ask_price
            self.open_ask_cancelled = True
        else:
            return False
        future = loop.run_in_executor(None, functools.partial(requests.delete, exchange_api_url + 'orders/' + str(order_id), auth=exchange_auth))
        response = yield from future
        if response.status_code == 200:
            file_logger.info('canceled {0} {1} @ {2}'.format(side, order_id, price))
        elif 'message' in response.json() and response.json()['message'] == 'order not found':
            file_logger.info('{0} already canceled: {1} @ {2}'.format(side, order_id, price))
        elif 'message' in response.json() and response.json()['message'] == 'Order already done':
            file_logger.info('{0} already filled: {1} @ {2}'.format(side, order_id, price))
        else:
            file_logger.error('Unhandled response: {0}'.format((pformat(response.json()))))

    @asyncio.coroutine
    def get_open_orders(self, loop):
        future = loop.run_in_executor(None, functools.partial(requests.get, exchange_api_url + 'orders', auth=exchange_auth))
        open_orders = yield from future
        open_orders = open_orders.json()

        try:
            self.open_bid_order_id = [order['id'] for order in open_orders if order['side'] == 'buy'][0]
            self.open_bid_price = [Decimal(order['price']) for order in open_orders if order['side'] == 'buy'][0]
        except IndexError:
            self.open_bid_order_id = None
            self.open_bid_price = None
            self.open_bid_status = None
            self.open_bid_cancelled = False
            self.open_bid_rejections = Decimal('0.0')

        try:
            self.open_ask_order_id = [order['id'] for order in open_orders if order['side'] == 'sell'][0]
            self.open_ask_price = [Decimal(order['price']) for order in open_orders if order['side'] == 'sell'][0]
        except IndexError:
            self.open_ask_order_id = None
            self.open_ask_price = None
            self.open_ask_status = None
            self.open_ask_cancelled = False
            self.open_ask_rejections = Decimal('0.0')

    @property
    def decimal_open_bid_price(self):
        if self.open_bid_price:
            return self.open_bid_price
        else:
            return Decimal('0.0')

    @property
    def decimal_open_ask_price(self):
        if self.open_ask_price:
            return self.open_bid_price
        else:
            return Decimal('0.0')
