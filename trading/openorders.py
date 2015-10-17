from pprint import pformat

import requests

from trading import file_logger
from trading.exchange import exchange_api_url, exchange_auth


class OpenOrders(object):
    def __init__(self):
        self.open_bid_order_id = None
        self.open_bid_price = None

        self.open_ask_order_id = None
        self.open_ask_price = None

        self.insufficient_btc = False
        self.insufficient_usd = False

        self.open_ask_rejections = 0.0
        self.open_bid_rejections = 0.0

    def cancel_all(self):
        if self.open_bid_order_id:
            self.cancel('bid')
        if self.open_ask_order_id:
            self.cancel('ask')

    def cancel(self, side):
        if side == 'bid':
            order_id = self.open_bid_order_id
            price = self.open_bid_price
            self.open_bid_order_id = None
            self.open_bid_price = None
        elif side == 'ask':
            order_id = self.open_ask_order_id
            price = self.open_ask_price
            self.open_ask_order_id = None
            self.open_ask_price = None
        else:
            return False
        response = requests.delete(exchange_api_url + 'orders/' + str(order_id), auth=exchange_auth)
        if response.status_code == 200:
            file_logger.info('canceled {0} {1} @ {2}'.format(side, order_id, price))
        elif 'message' in response.json() and response.json()['message'] == 'order not found':
            file_logger.info('{0} already canceled: {1} @ {2}'.format(side, order_id, price))
        elif 'message' in response.json() and response.json()['message'] == 'Order already done':
            file_logger.info('{0} already filled: {1} @ {2}'.format(side, order_id, price))
        else:
            file_logger.error('Unhandled response: {0}'.format((pformat(response.json()))))
            raise Exception()

    def get_open_orders(self):
        open_orders = requests.get(exchange_api_url + 'orders', auth=exchange_auth).json()

        try:
            self.open_bid_order_id = [order['id'] for order in open_orders if order['side'] == 'buy'][0]
            self.open_bid_price = [order['price'] for order in open_orders if order['side'] == 'buy'][0]
        except IndexError:
            pass

        try:
            self.open_ask_order_id = [order['id'] for order in open_orders if order['side'] == 'sell'][0]
            self.open_ask_price = [order['price'] for order in open_orders if order['side'] == 'sell'][0]
        except IndexError:
            pass

    @property
    def float_open_bid_price(self):
        if self.open_bid_price:
            return float(self.open_bid_price)
        else:
            return 0.0

    @property
    def float_open_ask_price(self):
        if self.open_ask_price:
            return float(self.open_ask_price)
        else:
            return 0.0