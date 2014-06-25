import json
from sqlalchemy import Column, Integer, Float, Unicode, ForeignKey, DateTime, Date, Enum
from sqlalchemy.orm import relationship, backref
from base import Base
from transactions import Transaction
from members.models.upload import Upload

__author__ = 'diederick'

def to_json(inst, cls):
    """
    Jsonify the sql alchemy query result.
    """
    convert = dict()
    # add your coversions for things like datetime's
    # and what-not that aren't serializable.
    d = dict()
    for c in cls.__table__.columns:
        v = getattr(inst, c.name)
        if c.type in convert.keys() and v is not None:
            try:
                d[c.name] = convert[c.type](v)
            except:
                d[c.name] = "Error:  Failed to covert using ", str(convert[c.type])
        elif v is None:
            d[c.name] = str()
        else:
            d[c.name] = str(v)
    return json.dumps(d)

class Mutation(Base):

    __tablename__ = 'mutations'

    id                      = Column('id',              Integer,    primary_key=True)
    upload_id               = Column('upload_id',       Integer,    ForeignKey('uploads.id', ),     nullable=True)
    tx_id                   = Column('tx_id',           Integer,    ForeignKey('transactions.id'),  nullable=True)
    created                 = Column('created',         DateTime,   nullable=True)
    processed               = Column('processed',       DateTime,   nullable=True)
    transferred             = Column('transferred',     DateTime,   nullable=True)          #transfer_date
    account                 = Column('account',         Unicode(34),   nullable=True)       #transfer_account
    contra_account          = Column('contra_account',  Unicode(34),   nullable=True)       #transfer_contra_account
    amount                  = Column('amount',          Float)                              #transfer_amount
    type                    = Column('type',            Enum(['debet','credit']))           #transfer_type
    name                    = Column('name',            Unicode(255))                       #transfer_name
    code                    = Column('code',            Unicode(255))                       #transfer_code
    description             = Column('description',     Unicode(255))                       #transfer_desc

    #def to_json(self):  # new special method
    #    return "{u'id': %r}" % 'blaat' #id.decode('utf-8')

    @property
    def json(self):
        return to_json(self, self.__class__)



