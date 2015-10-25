from decimal import Decimal

from trading import file_logger

try:
    import ujson as json
except ImportError:
    import json

from pprint import pformat
import time

import requests

from trading.exchange import exchange_api_url, exchange_auth


def market_maker_strategy(open_orders, order_book, spreads):
    time.sleep(10)
    open_orders.get_open_orders()
    open_orders.cancel_all()
    while True:
        time.sleep(0.005)
        if order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key() < 0:
            file_logger.warn('Negative spread: {0}'.format(
                order_book.asks.price_tree.min_key() - order_book.bids.price_tree.max_key()))
            continue
        if not open_orders.open_bid_order_id:
            open_bid_price = order_book.asks.price_tree.min_key() - spreads.bid_spread - open_orders.open_bid_rejections
            if 0.01 * float(open_bid_price) < float(open_orders.accounts['USD']['available']):
                order = {'size': '0.01',
                         'price': str(open_bid_price),
                         'side': 'buy',
                         'product_id': 'BTC-USD',
                         'post_only': True}
                response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
                if 'status' in response.json() and response.json()['status'] == 'pending':
                    open_orders.open_bid_order_id = response.json()['id']
                    open_orders.open_bid_price = open_bid_price
                    open_orders.open_bid_rejections = Decimal('0.0')
                    file_logger.info('new bid @ {0}'.format(open_bid_price))
                elif 'status' in response.json() and response.json()['status'] == 'rejected':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    open_orders.open_bid_rejections += Decimal('0.04')
                    file_logger.warn('rejected: new bid @ {0}'.format(open_bid_price))
                elif 'message' in response.json() and response.json()['message'] == 'Insufficient funds':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    file_logger.warn('Insufficient USD')
                else:
                    file_logger.error('Unhandled response: {0}'.format(pformat(response.json())))
                continue

        if not open_orders.open_ask_order_id:
            open_ask_price = order_book.bids.price_tree.max_key() + spreads.ask_spread + open_orders.open_ask_rejections
            if 0.01 < float(open_orders.accounts['BTC']['available']):
                order = {'size': '0.01',
                         'price': str(open_ask_price),
                         'side': 'sell',
                         'product_id': 'BTC-USD',
                         'post_only': True}
                response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
                if 'status' in response.json() and response.json()['status'] == 'pending':
                    open_orders.open_ask_order_id = response.json()['id']
                    open_orders.open_ask_price = open_ask_price
                    file_logger.info('new ask @ {0}'.format(open_ask_price))
                    open_orders.open_ask_rejections = Decimal('0.0')
                elif 'status' in response.json() and response.json()['status'] == 'rejected':
                    open_orders.open_ask_order_id = None
                    open_orders.open_ask_price = None
                    open_orders.open_ask_rejections += Decimal('0.04')
                    file_logger.warn('rejected: new ask @ {0}'.format(open_ask_price))
                elif 'message' in response.json() and response.json()['message'] == 'Insufficient funds':
                    open_orders.open_ask_order_id = None
                    open_orders.open_ask_price = None
                    file_logger.warn('Insufficient BTC')
                else:
                    file_logger.error('Unhandled response: {0}'.format(pformat(response.json())))
                continue

        if open_orders.open_bid_order_id and not open_orders.open_bid_cancelled:
            bid_too_far_out = open_orders.open_bid_price < (order_book.asks.price_tree.min_key()
                                                            - spreads.bid_too_far_adjustment_spread)
            bid_too_close = open_orders.open_bid_price > (order_book.bids.price_tree.max_key()
                                                          - spreads.bid_too_close_adjustment_spread)
            cancel_bid = bid_too_far_out or bid_too_close
            if cancel_bid:
                if bid_too_far_out:
                    file_logger.info('CANCEL: open bid {0} too far from best ask: {1} spread: {2}'.format(
                        open_orders.open_bid_price,
                        order_book.asks.price_tree.min_key(),
                        open_orders.open_bid_price - order_book.asks.price_tree.min_key()))
                if bid_too_close:
                    file_logger.info('CANCEL: open bid {0} too close to best bid: {1} spread: {2}'.format(
                        open_orders.open_bid_price,
                        order_book.bids.price_tree.max_key(),
                        open_orders.open_bid_price - order_book.bids.price_tree.max_key()))
                open_orders.cancel('bid')
                continue

        if open_orders.open_ask_order_id and not open_orders.open_ask_cancelled:
            ask_too_far_out = open_orders.open_ask_price > (order_book.bids.price_tree.max_key() +
                                                            spreads.ask_too_far_adjustment_spread)

            ask_too_close = open_orders.open_ask_price < (order_book.asks.price_tree.min_key() -
                                                          spreads.ask_too_close_adjustment_spread)

            cancel_ask = ask_too_far_out or ask_too_close

            if cancel_ask:
                if ask_too_far_out:
                    file_logger.info('CANCEL: open ask {0} too far from best bid: {1} spread: {2}'.format(
                        open_orders.open_ask_price,
                        order_book.bids.price_tree.max_key(),
                        open_orders.open_ask_price - order_book.bids.price_tree.max_key()))
                if ask_too_close:
                    file_logger.info('CANCEL: open ask {0} too close to best ask: {1} spread: {2}'.format(
                        open_orders.open_ask_price,
                        order_book.asks.price_tree.min_key(),
                        open_orders.open_ask_price - order_book.asks.price_tree.min_key()))
                open_orders.cancel('ask')
                continue


def buyer_strategy(order_book, open_orders, spreads):
    time.sleep(10)
    while True:
        time.sleep(0.001)
        if not open_orders.open_bid_order_id:
            open_bid_price = order_book.bids.price_tree.max_key() - spreads.bid_spread
            if 0.01 * float(open_bid_price) < float(open_orders.accounts['USD']['available']):
                order = {'size': '0.01',
                         'price': str(open_bid_price),
                         'side': 'buy',
                         'product_id': 'BTC-USD',
                         'post_only': True}
                response = requests.post(exchange_api_url + 'orders', json=order, auth=exchange_auth)
                if 'status' in response.json() and response.json()['status'] == 'pending':
                    open_orders.open_bid_order_id = response.json()['id']
                    open_orders.open_bid_price = open_bid_price
                    open_orders.open_bid_rejections = Decimal('0.0')
                    file_logger.info('new bid @ {0}'.format(open_bid_price))
                elif 'status' in response.json() and response.json()['status'] == 'rejected':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    open_orders.open_bid_rejections += Decimal('0.04')
                    file_logger.warn('rejected: new bid @ {0}'.format(open_bid_price))
                elif 'message' in response.json() and response.json()['message'] == 'Insufficient funds':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    file_logger.warn('Insufficient USD')
                elif 'message' in response.json() and response.json()['message'] == 'request timestamp expired':
                    open_orders.open_bid_order_id = None
                    open_orders.open_bid_price = None
                    file_logger.warn('Request timestamp expired')
                else:
                    file_logger.error('Unhandled response: {0}'.format(pformat(response.json())))
                continue

        if open_orders.open_bid_order_id and not open_orders.open_bid_cancelled:
            bid_too_far_out = open_orders.open_bid_price < (order_book.asks.price_tree.min_key()
                                                            - spreads.bid_too_far_adjustment_spread)
            bid_too_close = open_orders.open_bid_price > (order_book.bids.price_tree.max_key()
                                                          - spreads.bid_too_close_adjustment_spread)
            cancel_bid = bid_too_far_out or bid_too_close
            if cancel_bid:
                if bid_too_far_out:
                    file_logger.info('CANCEL: open bid {0} too far from best ask: {1} spread: {2}'.format(
                        open_orders.open_bid_price,
                        order_book.asks.price_tree.min_key(),
                        open_orders.open_bid_price - order_book.asks.price_tree.min_key()))
                if bid_too_close:
                    file_logger.info('CANCEL: open bid {0} too close to best bid: {1} spread: {2}'.format(
                        open_orders.open_bid_price,
                        order_book.bids.price_tree.max_key(),
                        order_book.bids.price_tree.max_key() - open_orders.open_bid_price))
                open_orders.cancel('bid')
                continue
