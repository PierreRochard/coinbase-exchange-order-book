import asyncio

from copy import deepcopy
from pprint import pformat
from datetime import datetime, timedelta
from decimal import Decimal
import time

from trading.exchange import exchange_api_url, exchange_auth

try:
    import ujson as json
except ImportError:
    import json
import requests
import pandas as pd
import pytz

from dateutil.tz import tzlocal
from orderbook.tree import Tree
from trading import file_logger


class Book(object):
    def __init__(self):
        self.matches = []
        self.bids = Tree()
        self.asks = Tree()

        self.level3_sequence = 0
        self.first_sequence = 0
        self.last_sequence = 0
        self.last_time = datetime.now(tzlocal())
        self.average_rate = 0.0
        self.fastest_rate = 0.0
        self.slowest_rate = 0.0

        self._vwap = None

    def populate_matches(self):
        for match in requests.get('https://api.exchange.coinbase.com/products/BTC-USD/trades').json():
            match['time'] = datetime.strptime(match['time'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
            self.matches += [{'price': float(match['price']), 'size': float(match['size']), 'time': match['time']}]

    def get_level3(self, json_doc=None, fake_test=False, last_sequence=None):
        if fake_test:
            print('getting level 3')
            from testdata.models import session, Level3s
            sequence, = (session.query(Level3s.sequence).filter(Level3s.sequence > last_sequence)
                        .order_by(Level3s.sequence).first())
            print(sequence, last_sequence)
            orders = (session.query(Level3s.price, Level3s.size, Level3s.order_id, Level3s.side)
                      .filter(Level3s.sequence == sequence).distinct())
            [self.bids.insert_order(bid[2], Decimal(bid[1]), Decimal(bid[0]), initial=True)
                for bid in orders if bid[3] == 'bid']
            [self.asks.insert_order(ask[2], Decimal(ask[1]), Decimal(ask[0]), initial=True)
                for ask in orders if ask[3] == 'ask']
            self.level3_sequence = sequence
        else:
            if not json_doc:
                json_doc = requests.get('http://api.exchange.coinbase.com/products/BTC-USD/book',
                                        params={'level': 3}).json()
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
        message['time'] = datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
        self.last_time = message['time']
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
            self.matches += [
                {'price': float(message['price']), 'size': float(message['size']), 'time': message['time']}]
            self.clean_matches()
            return True

        elif message_type == 'match' and side == 'sell':
            self.asks.match(message['maker_order_id'], Decimal(message['size']))
            self.matches += [
                {'price': float(message['price']), 'size': float(message['size']), 'time': message['time']}]
            self.clean_matches()
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

    def clean_matches(self):
        newest_match = self.matches[-1]['time']
        oldest = newest_match - timedelta(minutes=60)
        self.matches = [match for match in self.matches if match['time'] >= oldest]

    @property
    def vwap(self):
        return self._vwap

    @vwap.setter
    def vwap(self, minutes):
        # if not self._vwap:
        #     trades = requests.get(exchange_api_url + 'products/BTC-USD/trades', auth=exchange_auth).json()
        #     for trade in trades:
        #         trade['time'] = datetime.strptime(trade['time'],
        #                                           '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
        #         self.matches += [trade]
        #     self.clean_matches()
        start_time = time.time()
        matches = deepcopy(self.matches)
        df = pd.DataFrame(matches)
        df['size'] = pd.to_numeric(df['size'])
        df['price'] = pd.to_numeric(df['price'])
        df['product'] = df[["price", "size"]].product(axis=1)
        window = str(minutes) + 'min'
        df.index = df['time']
        del df['time']
        product_resample = df['product'].resample(window, how='sum')
        volume_resample = df['size'].resample(window, how='sum')
        vwap = product_resample / volume_resample
        self._vwap = round(Decimal(vwap[0]), 2)
        print("\n--- %s seconds ---\n" % (time.time() - start_time))
