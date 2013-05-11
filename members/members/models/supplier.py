from sqlalchemy import Table, Column, Boolean, Integer, Unicode

from pyramid.security import Allow, DENY_ALL

from base import Base, VokoValidationError


class VersSupplier(Base):
    __tablename__ = 'vers_suppliers'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100))
    website = Column(Unicode(50))
    email = Column(Unicode(50))
    telnr = Column(Unicode(20))
    faxnr = Column(Unicode(20))
    comment = Column(Unicode(500))
    active = Column(Boolean(), default=True)
    

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:members', 'view'),
               DENY_ALL]

    def __repr__(self):
        return self.name


class Wholesaler(Base):
    __tablename__ = 'wholesaler'

    wh_id = Column(Integer, primary_key=True)
    wh_name = Column(Unicode(100))
    wh_addr1 = Column(Unicode(100))
    wh_addr2 = Column(Unicode(100))
    wh_addr3 = Column(Unicode(100))
    wh_city = Column(Unicode(100), default=u'Amsterdam')
    wh_postcode = Column(Unicode(10))
    wh_tel = Column(Unicode(20))
    wh_fax = Column(Unicode(20))
    wh_active = Column(Boolean(), default=True)
    
    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:members', 'view'),
               DENY_ALL]

    def __repr__(self):
        return self.wh_name

