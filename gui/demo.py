from collections import OrderedDict
import tkinter
import asyncio
from functools import wraps
import websockets
try:
    import ujson as json
except ImportError:
    import json


def run_loop(func):
    '''
    This decorator converts a coroutine into a function which, when called,
    runs the underlying coroutine to completion in the asyncio event loop.
    '''
    func = asyncio.coroutine(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))

    return wrapper


@asyncio.coroutine
def run_tk(root, interval=0.05):
    try:
        while True:
            root.update()
            yield from asyncio.sleep(interval)
    except tkinter.TclError as e:
        if "application has been destroyed" not in e.args[0]:
            raise


@asyncio.coroutine
def listen_websocket(output):
    coinbase_websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
    yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')
    messages = []
    while True:
        message = yield from coinbase_websocket.recv()
        message = json.loads(message)
        message = OrderedDict(sorted(message.items(), key=lambda t: t[0]))
        messages += [message]
        output.insert(tkinter.END, str(dict(message)) + '\r')
        output.see(tkinter.END)


@run_loop
def main():
    root = tkinter.Tk()
    root.attributes("-topmost", True)
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry("%dx%d+0+0" % (w, h))
    output = tkinter.Text(font=("Helvetica", 12))
    output.grid()
    output.pack(expand=1, fill=tkinter.BOTH)

    asyncio.ensure_future(listen_websocket(output))

    yield from run_tk(root)


if __name__ == "__main__":
    main()
