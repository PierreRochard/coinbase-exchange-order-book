from decimal import Decimal


class Spreads(object):
    def __init__(self):
        # amount over the highest ask that you are willing to buy btc for
        self.bid_spread = Decimal('0.15')

        # amount below the lowest bid that you are willing to sell btc for
        self.ask_spread = Decimal('0.15')

    # spread at which your ask is cancelled
    @property
    def ask_too_far_adjustment_spread(self):
        return Decimal(self.ask_spread) + Decimal('0.08')

    @property
    def ask_too_close_adjustment_spread(self):
        return Decimal(self.ask_spread) - Decimal('0.06')

    # spread at which your bid is cancelled
    @property
    def bid_too_far_adjustment_spread(self):
        return Decimal(self.bid_spread) + Decimal('0.08')

    @property
    def bid_too_close_adjustment_spread(self):
        return Decimal(self.bid_spread) - Decimal('0.06')
