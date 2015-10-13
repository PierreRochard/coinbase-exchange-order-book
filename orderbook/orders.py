class Order(object):
    def __init__(self, order_id, size, price, order_list):
        self.order_id = order_id
        self.size = size
        self.price = price
        self.order_list = order_list

        self.next_order = None
        self.previous_order = None

    def next_order(self):
        return self.next_order

    def previous_order(self):
        return self.previous_order

    def update_size(self, new_size):
        self.order_list.volume -= self.size - new_size
        self.size = new_size

    def __str__(self):
        return "%s\t@\t%.4f" % (self.size, self.price)


class OrderList(object):
    def __init__(self):
        self.head_order = None
        self.tail_order = None
        self.length = 0
        self.volume = 0  # Total share volume
        self.last = None

    def __len__(self):
        return self.length

    def __iter__(self):
        self.last = self.head_order
        return self

    def next(self):
        if self.last is None:
            raise StopIteration
        else:
            return_value = self.last
            self.last = self.last.next_order
            return return_value

    def append_order(self, order):
        """

        :param order:
        :type order: Order
        :return:
        """
        if len(self) == 0:
            order.next_order = None
            order.previous_order = None
            self.head_order = order
            self.tail_order = order
        else:
            order.previous_order = self.tail_order
            order.next_order = None
            self.tail_order.next_order = order
            self.tail_order = order
        self.length += 1
        self.volume += order.size

    def remove_order(self, order):
        self.volume -= order.size
        self.length -= 1
        if len(self) == 0:
            return
        # Remove from list of orders
        next_order = order.next_order
        previous_order = order.previous_order
        if next_order is not None and previous_order is not None:
            next_order.previous_order = previous_order
            previous_order.next_order = next_order
        elif next_order is not None:
            next_order.previous_order = None
            self.head_order = next_order
        elif previous_order is not None:
            previous_order.next_order = None
            self.tail_order = previous_order

    def move_tail(self, order):
        if order.previous_order is not None:
            order.previous_order.next_order = self.next_order
        else:
            # Update the head order
            self.head_order = order.next_order
        order.next_order.previous_order = order.previous_order
        # Set the previous tail order's next order to this order
        self.tail_order.next_order = order
        self.tail_order = order
        order.previous_order = self.tail_order
        order.next_order = None
