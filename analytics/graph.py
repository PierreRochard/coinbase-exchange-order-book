import os
from pprint import pformat
from datetime import datetime, timedelta
from dateutil.parser import parse
from dateutil.tz import tzlocal
from matplotlib.dates import date2num
import pytz

import requests
from trading.exchange import exchange_api_url, exchange_auth
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.finance import candlestick_ohlc


def calculate_granularity(delta):
    return int(delta.total_seconds()/200)


def output_graph(interval, show_trades=False):
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)

    end = datetime.now(tzlocal())
    if interval == 'month':
        delta = timedelta(days=30)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-m - %-d'
        width = 0.008
    elif interval == 'week':
        delta = timedelta(days=7)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%a'
        width = 0.005
    elif interval == 'day':
        delta = timedelta(days=1)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-I:%M'
        width = 0.001
    elif interval == 'hour':
        delta = timedelta(minutes=60)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-I:%M'
        width = 0.00008
    else:
        return False
    params = {'granularity': granularity,
              'start': str(start),
              'end': str(end)}
    rates = requests.get(exchange_api_url + 'products/BTC-USD/candles', params=params).json()
    mkt_time = []
    mkt_low_price = []
    mkt_close_price = []
    mkt_high_price = []
    quotes = []
    for time, low, high, open_px, close, volume in rates:
        time = datetime.fromtimestamp(time, tz=pytz.utc).astimezone(tzlocal())
        mkt_time += [time]
        mkt_low_price += [float(low)]
        mkt_close_price += [float(close)]
        mkt_high_price += [float(high)]
        quotes += [(date2num(time), float(open_px), float(high), float(low), float(close))]

    # if show_trades:
    #     accounts = requests.get(exchange_api_url + 'accounts', auth=exchange_auth).json()
    #
    #     buy_time = []
    #     buy_price = []
    #     buy_size = []
    #
    #     for account in accounts:
    #         ledger = requests.get(exchange_api_url + 'accounts/{0}/ledger'.format(account['id']),
    #                               auth=exchange_auth).json()
    #         for transaction in ledger:
    #
    #             if transaction['type'] == 'match' and parse(transaction['created_at']) > hour_ago:
    #                 order = requests.get(exchange_api_url + 'orders/' + transaction['details']['order_id'], auth=exchange_auth).json()
    #                 print(pformat(order))
    #                 buy_time += [parse(order['done_at']).astimezone(tzlocal())]
    #                 buy_price += [float(order['price'])]
    #                 buy_size += [float(order['filled_size'])*10]
    #
    #     buy_size = [20*2**n for n in buy_size]
    #     plt.scatter(buy_time, buy_price, s=buy_size)

    plt.xlim(start, datetime.now(tzlocal()))

    candlestick_ohlc(ax1, quotes, width=width)

    myFmt = mdates.DateFormatter(datetime_format, tzlocal())
    plt.gca().xaxis.set_major_formatter(myFmt)
    plt.setp(plt.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
    save_directory = os.path.abspath('graphs/')
    file_name = os.path.join(save_directory, 'test_{0}.png'.format(interval))
    plt.savefig(file_name)

if __name__ == '__main__':
    for interval in ['month', 'week', 'day', 'hour']:
        output_graph(interval=interval)
