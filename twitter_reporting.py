from datetime import datetime
import threading

from dateutil.parser import parse
from dateutil.tz import tzlocal
import requests
from twython import Twython

from trading.exchange import exchange_api_url, exchange_auth
from twitter_config import APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET


twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

minutes = 3.14


def run():
    tweet = ''
    accounts = requests.get(exchange_api_url + 'accounts', auth=exchange_auth).json()

    last_matches = []
    for account in accounts:
        ledger = requests.get(exchange_api_url + 'accounts/{0}/ledger'.format(account['id']), auth=exchange_auth).json()
        last_matches += [parse(ledger[0]['created_at'])]
    last_match = max(last_matches)
    time_since = round((datetime.now(tzlocal()) - last_match).seconds/60, 2)
    if time_since > 1:
        tweet += '{0} mins\n'.format(time_since)
    else:
        tweet += '{0} min\n'.format(time_since)

    open_orders = requests.get(exchange_api_url + 'orders', auth=exchange_auth).json()

    try:
        open_bid_price = [order['price'] for order in open_orders if order['side'] == 'buy'][0]
    except IndexError:
        open_bid_price = None

    try:
        open_ask_price = [order['price'] for order in open_orders if order['side'] == 'sell'][0]
    except IndexError:
        open_ask_price = None

    if not open_ask_price and not open_bid_price:
        tweet += 'No open bids or asks\n'
    elif not open_ask_price:
        tweet += 'You: {0:.2f} bid\n'.format(float(open_bid_price))
    elif not open_bid_price:
        tweet += 'You: {0:.2f} ask\n'.format(float(open_ask_price))
    else:
        tweet += 'You: {0:.2f} ask {1:.2f} bid {2:.2f} spread\n'.format(float(open_ask_price), float(open_bid_price),
                                                                        float(open_ask_price)-float(open_bid_price))

    level_1 = requests.get('http://api.exchange.coinbase.com/products/BTC-USD/book', params={'level': 1}).json()
    best_ask = level_1['asks'][0][0]
    best_bid = level_1['bids'][0][0]

    tweet += 'Mkt: {0:.2f} ask {1:.2f} bid {2:.2f} spread\n'.format(float(best_ask), float(best_bid),
                                                                  float(best_ask)-float(best_bid))

    balance = 0
    for account in accounts:
        if account['currency'] == 'BTC':
            balance += float(account['balance'])*float(best_bid)
        elif account['currency'] == 'USD':
            balance += float(account['balance'])
        tweet += '{0:.2f} {1} '.format(float(account['available']), account['currency'])

    tweet += '\n{0:.2f} USD'.format(balance)

    print(tweet)

    twitter.update_status(status=tweet)
    threading.Timer(60 * minutes, run).start()


if __name__ == '__main__':
    threading.Timer(1, run).start()
