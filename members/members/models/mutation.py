from sqlalchemy import Column, Integer, Float, Unicode, ForeignKey, DateTime, Date, Enum
from sqlalchemy.orm import relationship, backref
from base import Base
from transactions import Transaction
from members.models.upload import Upload

__author__ = 'diederick'

class Mutation(Base):

    __tablename__ = 'mutations'

    id                      = Column('id',              Integer,    primary_key=True)
    upload_id               = Column('upload_id',       Integer,    ForeignKey('uploads.id', ),     nullable=True)
    transaction_id          = Column('tx_id',           Integer,    ForeignKey('transactions.id'),  nullable=True)
    created                 = Column('created',         DateTime,   nullable=True)
    processed               = Column('processed',       DateTime,   nullable=True)
    transfer_date           = Column('transferred',     DateTime,   nullable=True)
    transfer_account        = Column('account',         DateTime,   nullable=True)
    transfer_contra_account = Column('contra_account',  DateTime,   nullable=True)
    transfer_amount         = Column('amount',          Float)
    transfer_type           = Column('type',            Enum(['debet','credit']))
    transfer_name           = Column('name',            Unicode(255))
    transfer_code           = Column('code',            Unicode(255))
    transfer_desc           = Column('description',     Unicode(255))


