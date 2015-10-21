import time
try:
    import ujson as json
except ImportError:
    import json

from orderbook.book import Book


def dict_compare(variable_order_book, control_order_book, price_map=False, order_map=False):
    d1_keys = set(variable_order_book.keys())
    d2_keys = set(control_order_book.keys())

    intersect_keys = d1_keys.intersection(d2_keys)
    assert intersect_keys
    added = d1_keys - d2_keys
    assert not added
    removed = d2_keys - d1_keys
    assert not removed

    for key in intersect_keys:
        if price_map:
            assert len(variable_order_book[key]) == len(control_order_book[key])
            zipped = zip(variable_order_book[key], control_order_book[key])
            for order in zipped:
                assert order[0]['order_id'] == order[1]['order_id']
                assert order[0]['price'] == order[1]['price']
                assert order[0]['size'] == order[1]['size']
        if order_map:
            assert variable_order_book[key]['order_id'] == control_order_book[key]['order_id']
            assert variable_order_book[key]['price'] == control_order_book[key]['price']
            assert variable_order_book[key]['size'] == control_order_book[key]['size']


def test_orderbook():
    variable_order_book = Book()
    control_order_book = Book()

    with open('testdata/messages.json') as messages_json_file:
        messages = json.load(messages_json_file)

    with open('testdata/beginning_level_3.json') as begin_json_file:
        beginning_level_3 = json.load(begin_json_file)

    with open('testdata/ending_level_3.json') as end_json_file:
        ending_level_3 = json.load(end_json_file)

    try:
        assert beginning_level_3['sequence'] + 1 == messages[0]['sequence']
        assert ending_level_3['sequence'] == messages[-1]['sequence']
    except AssertionError:
        print("Problem with sample data sequences")

    variable_order_book.get_level3(beginning_level_3)

    start = time.time()
    [variable_order_book.process_message(message) for message in messages]
    end = time.time()
    print('messages per sec: {0}'.format(int(len(messages)/(end-start))))

    control_order_book.get_level3(ending_level_3)

    dict_compare(variable_order_book.asks.price_map, control_order_book.asks.price_map, price_map=True)
    dict_compare(variable_order_book.asks.order_map, control_order_book.asks.order_map, order_map=True)


if __name__ == '__main__':
    test_orderbook()
