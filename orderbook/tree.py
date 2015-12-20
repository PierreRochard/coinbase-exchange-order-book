from bintrees import FastRBTree


class Tree(object):
    def __init__(self):
        self.price_tree = FastRBTree()
        self.price_map = {}
        self.size_map = {}
        self.order_map = {}
        self.received_orders = {}

    def receive(self, order_id, size):
        self.received_orders[order_id] = size

    def create_price(self, price):
        new_list = []
        self.price_tree.insert(price, new_list)
        self.price_map[price] = new_list
        self.size_map[price] = 0

    def remove_price(self, price):
        self.price_tree.remove(price)
        del self.price_map[price]

    def insert_order(self, order_id, size, price, initial=False):
        if not initial:
            del self.received_orders[order_id]
        if price not in self.price_map:
            self.create_price(price)
        order = {'order_id': order_id, 'size': size, 'price': price, 'price_map': self.price_map[price]}
        self.price_map[price].append(order)
        self.order_map[order_id] = order
        self.size_map[price] += size

    def match(self, maker_order_id, match_size, match_price):
        order = self.order_map[maker_order_id]
        original_size = order['size']
        new_size = original_size - match_size
        order['size'] = new_size
        self.size_map[match_price] -= match_size

    def change(self, order_id, new_size, old_size, price):
        order = self.order_map[order_id]
        order['size'] = new_size
        change = new_size - old_size
        self.size_map[price] += change

    def remove_order(self, order_id):
        if order_id in self.order_map:
            order = self.order_map[order_id]
            self.price_map[order['price']] = [o for o in self.price_map[order['price']] if o['order_id'] != order_id]
            if not self.price_map[order['price']]:
                self.remove_price(order['price'])
            del self.order_map[order_id]
        else:
            del self.received_orders[order_id]