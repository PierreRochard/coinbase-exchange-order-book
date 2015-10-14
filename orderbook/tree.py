from orderbook.orders import Order, OrderList

from bintrees import FastRBTree


class Tree(object):
    def __init__(self):
        self.price_tree = FastRBTree()
        self.price_map = {}  # Map from price -> order_list object
        self.order_map = {}  # Order ID to Order object

    def __len__(self):
        return len(self.order_map)

    def get_price(self, price):
        return self.price_map[price]

    def get_order(self, order_id):
        return self.order_map[order_id]

    def create_price(self, price):
        new_list = OrderList()
        self.price_tree.insert(price, new_list)
        self.price_map[price] = new_list

    def remove_price(self, price):
        self.price_tree.remove(price)
        del self.price_map[price]

    def price_exists(self, price):
        return price in self.price_map

    def order_exists(self, order_id):
        return order_id in self.order_map

    def insert(self, order_id, size, price):
        if price not in self.price_map:
            self.create_price(price)
        order = Order(order_id, size, price, self.price_map[price])
        self.price_map[order.price].append_order(order)
        self.order_map[order.order_id] = order

    def match(self, maker_order_id, size):
        try:
            order = self.order_map[maker_order_id]
        except KeyError:
            return
        original_size = order.size
        new_size = original_size - size
        if new_size == 0:
            self.remove_order(maker_order_id)
            return
        order.update_size(new_size)

    def change(self, order_id, new_size):
        try:
            order = self.order_map[order_id]
        except KeyError:
            return
        order.update_size(new_size)

    def remove_order(self, order_id):
        if order_id in self.order_map:
            order = self.order_map[order_id]
        else:
            return
        order.order_list.remove_order(order)
        if len(order.order_list) == 0:
            self.remove_price(order.price)
        del self.order_map[order_id]
