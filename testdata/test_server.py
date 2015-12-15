import asyncio
from datetime import datetime
import time

from models import Level3s
from sqlalchemy import create_engine, MetaData, Table, Column, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
import websockets
try:
    import ujson as json
except ImportError:
    import json

from db_config import DEV_URI

def row2dict(row):
    d = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if value:
            if isinstance(value, datetime):
                d[column.name] = value.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            else:
                d[column.name] = str(value)
    return d

engine = create_engine(DEV_URI)
metadata = MetaData(bind=engine)
Base = declarative_base()


class Messages(Base):
    __table__ = Table('messages', metadata,
                      Column('sequence', Integer, primary_key=True),
                      autoload=True)

session = scoped_session(sessionmaker(bind=engine))


@asyncio.coroutine
def hello(websocket, path):
    message = yield from websocket.recv()
    message = json.loads(message)
    if 'type' in message and 'product_id' in message:
        if message['type'] == 'subscribe' and message['product_id'] == 'BTC-USD':
            first_sequence, = session.query(Level3s.sequence).order_by(Level3s.sequence).first()
            first_sequence -= 50
            first_message = (session.query(Messages).order_by(Messages.sequence)
                             .filter(Messages.sequence >= first_sequence).first())
            first_message_dict = row2dict(first_message)
            yield from websocket.send(json.dumps(first_message_dict))
            next_message = (session.query(Messages).order_by(Messages.sequence)
                            .filter(Messages.sequence > first_message.sequence).first())
            time.sleep((next_message.time - first_message.time).seconds+1)
            while True:
                previous_message = next_message
                next_message = (session.query(Messages).order_by(Messages.sequence)
                                .filter(Messages.sequence > previous_message.sequence).first())
                next_message_dict = row2dict(next_message)
                time.sleep((next_message.time - previous_message.time).seconds+1)
                yield from websocket.send(json.dumps(next_message_dict))

if __name__ == '__main__':
    start_server = websockets.serve(hello, 'localhost', 8765)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
