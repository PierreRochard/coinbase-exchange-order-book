import time
try:
    import ujson as json
except ImportError:
    import json

from orderbook.book import Book


def dict_compare(new_dictionary, old_dictionary, price_map=False, order_map=False):
    d1_keys = set(new_dictionary.keys())
    d2_keys = set(old_dictionary.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = []
    # for key in intersect_keys:
    #     if price_map:
    #         try:
                # print(len(new_dictionary[key]))
                # print(len(old_dictionary[key]))
                # assert len(new_dictionary[key]) == len(old_dictionary[key])
                # assert len(new_dictionary[key]) == old_dictionary[key]

                # assert new_dictionary[key].length == old_dictionary[key].length
                # assert new_dictionary[key].volume == old_dictionary[key].volume
                #
                # assert new_dictionary[key].head_order.order_id == old_dictionary[key].head_order.order_id
                # assert new_dictionary[key].head_order.size == old_dictionary[key].head_order.size
                # assert new_dictionary[key].head_order.price == old_dictionary[key].head_order.price
                #
                # assert new_dictionary[key].tail_order.order_id == old_dictionary[key].tail_order.order_id
                # assert new_dictionary[key].tail_order.size == old_dictionary[key].tail_order.size
                # assert new_dictionary[key].tail_order.price == old_dictionary[key].tail_order.price

            # except AssertionError:
            #     pass
                # raise Exception()
                # modified += (new_dictionary[key], old_dictionary[key])
    modified = {o: (new_dictionary[o], old_dictionary[o]) for o in intersect_keys if new_dictionary[o] != old_dictionary[o]}

    same = set(o for o in intersect_keys if new_dictionary[o] == old_dictionary[o])
    return added, removed, modified, same


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

    # assert variable_order_book.asks.price_map == control_order_book.asks.price_map

    added, removed, modified, same = dict_compare(variable_order_book.asks.price_map, control_order_book.asks.price_map,
                                                  price_map=True)
    if added:
        print('superfluous entries: {0}'.format(added))
    if removed:
        print('missing entries: {0}'.format(removed))
    # if modified:
    #     print('modified entries: {0}'.format(modified))
    #

if __name__ == '__main__':
    test_orderbook()
