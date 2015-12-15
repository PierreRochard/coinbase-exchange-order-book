import asyncio
from datetime import datetime

from dateutil.tz import tzlocal


@asyncio.coroutine
def monitor(order_book, open_orders):
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