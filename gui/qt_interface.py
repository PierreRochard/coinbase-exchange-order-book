import asyncio
from pprint import pformat

import matplotlib.pyplot as plt
import pandas as pd
from dateutil.tz import tzlocal
from decimal import Decimal
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.dates import DateFormatter
from matplotlib.ticker import ScalarFormatter, FormatStrFormatter
from matplotlib.figure import Figure
from quamash import QtGui, QtCore


class MatchesCanvas(FigureCanvasQTAgg):
    """Ultimately, this is a QWidget (as well as a FigureCanvasQTAggAgg, etc.)."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        # We want the axes cleared every time plot() is called
        self.axes.hold(False)
        FigureCanvasQTAgg.__init__(self, fig)
        self.setParent(parent)
        FigureCanvasQTAgg.setSizePolicy(self,
                                   QtGui.QSizePolicy.Expanding,
                                   QtGui.QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    @asyncio.coroutine
    def update_figure(self, messages):
        if len(messages) < 2:
            return True
        messages = pd.DataFrame(messages)
        messages = messages.sort_values('time')
        self.axes.plot(messages['time'], messages['price'])
        self.axes.get_xaxis().set_major_formatter(DateFormatter('%H:%M:%S', tzlocal()))
        plt.setp(self.axes.get_xticklabels(), rotation=45, horizontalalignment='right')
        self.axes.get_yaxis().set_major_formatter(FormatStrFormatter('%.2f'))
        self.draw()


class OrderbookCanvas(FigureCanvasQTAgg):
    """Ultimately, this is a QWidget (as well as a FigureCanvasQTAggAgg, etc.)."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        # We want the axes cleared every time plot() is called
        self.axes.hold(False)
        FigureCanvasQTAgg.__init__(self, fig)
        self.setParent(parent)
        FigureCanvasQTAgg.setSizePolicy(self,
                                   QtGui.QSizePolicy.Expanding,
                                   QtGui.QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    @asyncio.coroutine
    def update_figure(self, order_book):
        bids = []
        best_bid = order_book.bids.price_tree.max_key()
        for price, orders in order_book.bids.price_map.items():
            if price > (best_bid - best_bid*Decimal('0.02')):
                bids += [{'price': price, 'quantity': sum(order['size'] for order in orders)}]

        asks = []
        best_ask = order_book.asks.price_tree.min_key()
        for price, orders in order_book.asks.price_map.items():
            if price < (best_ask + best_ask*Decimal('0.02')):
                asks += [{'price': price, 'quantity': sum(order['size'] for order in orders)}]
        bids = pd.DataFrame(bids)
        asks = pd.DataFrame(asks)
        bids = bids.sort_values('price', ascending=False)
        bids['cumulative_quantity'] = bids['quantity'].cumsum()
        bids = bids.sort_values('price', ascending=True)
        asks = asks.sort_values('price')
        asks['cumulative_quantity'] = asks['quantity'].cumsum()
        self.axes.plot(bids['price'], bids['cumulative_quantity'], 'g', asks['price'], asks['cumulative_quantity'], 'r')
        self.axes.get_xaxis().set_major_formatter(FormatStrFormatter('%.2f'))
        self.axes.get_yaxis().set_major_formatter(FormatStrFormatter('%.2f'))
        self.draw()


class ApplicationWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("application main window")

        self.file_menu = QtGui.QMenu('&File', self)
        self.file_menu.addAction('&Quit', self.fileQuit,
                                 QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)

        self.help_menu = QtGui.QMenu('&Help', self)
        self.menuBar().addSeparator()
        self.menuBar().addMenu(self.help_menu)

        self.help_menu.addAction('&About', self.about)

        self.main_widget = QtGui.QWidget(self)

        l = QtGui.QVBoxLayout(self.main_widget)
        self.matches = MatchesCanvas(self.main_widget)
        self.orderbook = OrderbookCanvas(self.main_widget)
        l.addWidget(self.matches)
        l.addWidget(self.orderbook)

        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

        self.statusBar().showMessage("All hail matplotlib!", 2000)

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()

    def about(self):
        QtGui.QMessageBox.about(self, "About", "about")

