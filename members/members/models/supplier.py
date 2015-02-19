from sqlalchemy import Column, Boolean, Integer, Unicode

from pyramid.security import Allow, DENY_ALL

from base import Base, VokoValidationError


class Supplier(Base):
    __tablename__ = 'suppliers'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100))
    website = Column(Unicode(50))
    email = Column(Unicode(50))
    telnr = Column(Unicode(20))
    comment = Column(Unicode(500))
    active = Column(Boolean(), default=True)
    

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:members', 'view'),
               DENY_ALL]

    def __init__(self, name):
        self.name = name
        self.exists = False

    def __repr__(self):
        return self.name

    @property
    def balance(self):
        balance = 0
        for t in self.transactions:
            balance += t.amount
        return balance

    def validate(self):
        # check missing fields
        missing = []
        for f in ('website', 'name'):
            if not f in self.__dict__ or self.__dict__[f] == '':
                missing.append(f)
        if len(missing) > 0:
            raise VokoValidationError('We still require you to fill in: %s'\
                                    % ', '.join([m[4:] for m in missing]))

def get_supplier(session, request):
    '''
    Make a Supplier object, use supplier ID from request if possible.
    Will return an empty object when no information is in the request.
    '''
    supplier = Supplier(name=u'')
    s_id = None
    if 's_id' in request.matchdict:
        m_id = request.matchdict['s_id']
    if 's_id' in request.params:
        m_id = request.params['s_id']
    if m_id:
        if m_id == 'new':
            return supplier
        try:
            s_id = int(s_id)
        except ValueError:
            raise Exception("No supplier with ID {0}".format(m_id))
        supplier = session.query(Supplier).get(m_id)
        if supplier:
            supplier.exists = True
        else:
            raise Exception("No supplier with ID {0}".format(m_id))
    return supplier
