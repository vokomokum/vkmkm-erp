from datetime import datetime
from sqlalchemy import Column, Integer, Unicode, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from base import Base
#from members.models.member import Member

__author__ = 'diederick'

class Upload(Base):

    __tablename__ = 'uploads'

    id          = Column('id',          Integer, primary_key=True)
    created     = Column('datetime',    DateTime, default = datetime.now())
    member_id   = Column('member_id',   Integer, ForeignKey('members.mem_id'), nullable=True) #Column(Integer, ForeignKey('members.mem_id')) #relationship(Member,  backref('Upload', order_by='desc(Uploads.id)'))
    file        = Column('file',        Unicode(512))

    mutations = relationship("Mutation", backref="uploads")

    #mutations  = relationship("Mutation", backref="uploads")

