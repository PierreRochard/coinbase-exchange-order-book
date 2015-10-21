from pprint import pformat
from collections import deque
from datetime import datetime
from decimal import Decimal
from dateutil.parser import parse

try:
    import ujson as json
except ImportError:
    import json

from dateutil.tz import tzlocal
from orderbook.tree import Tree
import requests
from trading import file_logger


class Book(object):
    def __init__(self):
        self.matches = deque(maxlen=100)
        self.bids = Tree()
        self.asks = Tree()

        self.level3_sequence = 0
        self.first_sequence = 0
        self.last_sequence = 0
        self.last_time = datetime.now(tzlocal())

    def get_level3(self, json_doc=None):
        if not json_doc:
            json_doc = requests.get('http://api.exchange.coinbase.com/products/BTC-USD/book', params={'level': 3}).json()
        [self.bids.insert_order(bid[2], Decimal(bid[1]), Decimal(bid[0]), initial=True) for bid in json_doc['bids']]
        [self.asks.insert_order(ask[2], Decimal(ask[1]), Decimal(ask[0]), initial=True) for ask in json_doc['asks']]
        self.level3_sequence = json_doc['sequence']

    def process_message(self, message):

        new_sequence = int(message['sequence'])

        if new_sequence <= self.level3_sequence:
            return True

        if not self.first_sequence:
            self.first_sequence = new_sequence
            self.last_sequence = new_sequence
            assert new_sequence - self.level3_sequence == 1
        else:
            if (new_sequence - self.last_sequence) != 1:
                file_logger.error('sequence gap: {0}'.format(new_sequence - self.last_sequence))
                return False
            self.last_sequence = new_sequence

        if 'order_type' in message and message['order_type'] == 'market':
            return True

        message_type = message['type']
        message_time = parse(message['time'])
        self.last_time = message_time
        side = message['side']

        if message_type == 'received' and side == 'buy':
            self.bids.receive(message['order_id'], message['size'])
            return True
        elif message_type == 'received' and side == 'sell':
            self.asks.receive(message['order_id'], message['size'])
            return True

        elif message_type == 'open' and side == 'buy':
            self.bids.insert_order(message['order_id'], Decimal(message['remaining_size']), Decimal(message['price']))
            return True
        elif message_type == 'open' and side == 'sell':
            self.asks.insert_order(message['order_id'], Decimal(message['remaining_size']), Decimal(message['price']))
            return True

        elif message_type == 'match' and side == 'buy':
            self.bids.match(message['maker_order_id'], Decimal(message['size']))
            self.matches.appendleft((message_time, side, Decimal(message['size']), Decimal(message['price'])))
            return True
        elif message_type == 'match' and side == 'sell':
            self.asks.match(message['maker_order_id'], Decimal(message['size']))
            self.matches.appendleft((message_time, side, Decimal(message['size']), Decimal(message['price'])))
            return True

        elif message_type == 'done' and side == 'buy':
            self.bids.remove_order(message['order_id'])
            return True
        elif message_type == 'done' and side == 'sell':
            self.asks.remove_order(message['order_id'])
            return True

        elif message_type == 'change' and side == 'buy':
            self.bids.change(message['order_id'], Decimal(message['new_size']))
            return True
        elif message_type == 'change' and side == 'sell':
            self.asks.change(message['order_id'], Decimal(message['new_size']))
            return True

        else:
            file_logger.error('Unhandled message: {0}'.format(pformat(message)))
            return False
