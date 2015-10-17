from orderbook.orders import Order, OrderList

from bintrees import FastRBTree


class Tree(object):
    def __init__(self):
        self.price_tree = FastRBTree()
        self.price_map = {}  # Map from price -> order_list object
        self.order_map = {}  # Order ID to Order object
        self.received_orders = {}

    def receive(self, order_id, size):
        self.received_orders[order_id] = size

    def create_price(self, price):
        new_list = OrderList()
        self.price_tree.insert(price, new_list)
        self.price_map[price] = new_list

    def remove_price(self, price):
        self.price_tree.remove(price)
        del self.price_map[price]

    def insert_order(self, order_id, size, price, initial=False):
        if not initial:
            del self.received_orders[order_id]
        if price not in self.price_map:
            self.create_price(price)
        order = Order(order_id, size, price, self.price_map[price])
        self.price_map[order.price].append_order(order)
        self.order_map[order.order_id] = order

    def match(self, maker_order_id, size):
        order = self.order_map[maker_order_id]
        original_size = order.size
        new_size = original_size - size
        order.update_size(new_size)

    def change(self, order_id, new_size):
        order = self.order_map[order_id]
        order.update_size(new_size)

    def remove_order(self, order_id):
        if order_id in self.order_map:
            order = self.order_map[order_id]
            order.order_list.remove_order(order)
            if len(order.order_list) == 0:
                self.remove_price(order.price)
            del self.order_map[order_id]
        else:
            del self.received_orders[order_id]