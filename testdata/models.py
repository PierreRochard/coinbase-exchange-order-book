import logging
import traceback
from sqlalchemy import create_engine, func, UniqueConstraint
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, Integer, Numeric, String

from db_config import DEV_URI

engine = create_engine(DEV_URI)

session = scoped_session(sessionmaker(bind=engine))
rds_session = session
Base = declarative_base()
Base.query = session.query_property()


class Messages(Base):
    __tablename__ = 'coinbase_messages'
    __table_args__ = (UniqueConstraint('availability_zone', 'sequence', name='unique_message'),)

    id = Column(Integer, primary_key=True)

    availability_zone = Column(String, nullable=False)
    latency = Column(Integer)

    sequence = Column(Integer)
    type = Column(String)
    time = Column(DateTime(timezone=True))
    product_id = Column(String)
    order_id = Column(String)
    taker_order_id = Column(String)
    maker_order_id = Column(String)
    reason = Column(String)
    trade_id = Column(Integer)
    funds = Column(Numeric)
    old_funds = Column(Numeric)
    new_funds = Column(Numeric)
    size = Column(Numeric)
    new_size = Column(Numeric)
    old_size = Column(Numeric)
    remaining_size = Column(Numeric)
    price = Column(Numeric)
    side = Column(String)
    order_type = Column(String)
    client_oid = Column(String)


class Level3s(Base):
    __tablename__ = 'level3s'
    __table_args__ = (UniqueConstraint('availability_zone', 'sequence', 'order_id', name='unique_level3'),)

    id = Column(Integer, primary_key=True)
    availability_zone = Column(String, nullable=False)
    sequence = Column(Integer, nullable=False)
    side = Column(String, nullable=False)
    price = Column(Numeric, nullable=False)
    size = Column(Numeric, nullable=False)
    order_id = Column(String, nullable=False)
