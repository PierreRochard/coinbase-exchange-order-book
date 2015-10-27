from pprint import pformat
from datetime import date
from coinbase.wallet.client import Client
import requests
from dateutil.parser import parse
import time
from trading import file_logger
from trading.exchange import CoinbaseExchangeAuthentication, exchange_api_url
from trading.treasury_config import (DEPOSIT_KEY, DEPOSIT_SECRET, PAYMENT_METHOD,
                                     EXCHANGE_KEY, EXCHANGE_SECRET, EXCHANGE_PASSPHRASE)

client = Client(DEPOSIT_KEY, DEPOSIT_SECRET)

hours = 24

exchange_auth = CoinbaseExchangeAuthentication(EXCHANGE_KEY, EXCHANGE_SECRET, EXCHANGE_PASSPHRASE)


def view_payment_methods():
    payment_methods = client.get_payment_methods()['data']
    print(pformat(payment_methods))


def nostro_transfer():
    for account in client.get_accounts()['data']:
        if account['name'] == 'USD Wallet':
            deposits = account.get_deposits()['data']
            if parse(deposits[0]['created_at']).date() < date.today():
                account.deposit(payment_method=PAYMENT_METHOD, amount='50', currency='USD')
            if account['balance']['amount'] >= 50:
                transfer = {'type': 'deposit',
                            'amount': '50',
                            'coinbase_account_id': account['id']}
                response = requests.post(exchange_api_url + 'orders', json=transfer, auth=exchange_auth)
                if response.status_code != 200:
                    file_logger.error('Nostro transfer failed: {0}'.format(response.json()))
    time.sleep(24 * 60 * 60)


if __name__ == '__main__':
    view_payment_methods()
