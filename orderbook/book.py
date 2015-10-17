from collections import deque
from datetime import datetime
from decimal import Decimal

from dateutil.tz import tzlocal
from orderbook.tree import Tree
import requests


class Book(object):
    def __init__(self):
        self.matches = deque(maxlen=100)
        self.bids = Tree()
        self.asks = Tree()

        self.level3_sequence = 0
        self.first_sequence = 0
        self.last_sequence = 0
        self.last_time = datetime.now(tzlocal())

    def get_level3(self):
        level_3 = requests.get('http://api.exchange.coinbase.com/products/BTC-USD/book', params={'level': 3}).json()
        [self.bids.insert_order(bid[2], Decimal(bid[1]), Decimal(bid[0]), initial=True) for bid in level_3['bids']]
        [self.asks.insert_order(ask[2], Decimal(ask[1]), Decimal(ask[0]), initial=True) for ask in level_3['asks']]
        self.level3_sequence = level_3['sequence']
