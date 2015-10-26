from pprint import pformat
from datetime import date
from coinbase.wallet.client import Client
from dateutil.parser import parse
import time
from trading.treasury_config import DEPOSIT_KEY, DEPOSIT_SECRET, PAYMENT_METHOD

client = Client(DEPOSIT_KEY, DEPOSIT_SECRET)

hours = 24


def view_payment_methods():
    payment_methods = client.get_payment_methods()['data']
    print(pformat(payment_methods))


def nostro_transfer():
    for account in client.get_accounts()['data']:
        if account['currency'] == 'USD':
            print(pformat(account))
            deposits = account.get_deposits()['data']
            print(pformat(deposits))
            if parse(deposits[0]['created_at']).date() < date.today():
                account.deposit(payment_method=PAYMENT_METHOD, amount='50', currency='USD')
    time.sleep(24*60*60)


if __name__ == '__main__':
    view_payment_methods()
