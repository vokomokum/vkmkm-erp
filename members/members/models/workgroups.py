import re

from sqlalchemy import Table, Column, Integer, Unicode, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

from base import Base, VokoValidationError
from member import Member


membership = Table(
    'wg_membership', Base.metadata,
    Column('wg_id', Integer, ForeignKey('workgroups.id')),
    Column('mem_id', Integer, ForeignKey('members.mem_id'))
    )

leadership = Table(
    'wg_leadership', Base.metadata,
    Column('wg_id', Integer, ForeignKey('workgroups.id')),
    Column('mem_id', Integer, ForeignKey('members.mem_id'))
    )


class Workgroup(Base):
    __tablename__ = 'workgroups'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255), unique=True)
    desc = Column(Unicode(255))

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:wg-leaders', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, name='', desc=''):
        ''' receiving request makes this class a factory for views '''
        self.exists = False
        self.name = name
        self.desc = desc

    def __repr__(self):
        return self.name

    @property
    def mailing_list_address(self):
        ''' return the email address used as mailing list in this group '''
        name = self.name.strip()
        name = re.sub(r'\s+', '-', name)
        name = re.sub(r'[\'"@,:;]', "", name)
        name = name.lower()
        return "{}@vokomokum.nl".format(name)

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.name == '':
            raise VokoValidationError('A workgroup needs a name.')
        if self.desc == '':
            raise VokoValidationError('A workgroup needs a description.')
        if len(self.leaders) == 0:
            raise VokoValidationError('A workgroup needs at least '\
                                      'one coordinator.')

    @property
    def headcount(self):
        return len(self.members)

Workgroup.members = relationship('Member', secondary=membership)
Member.workgroups = relationship('Workgroup', secondary=membership)
Workgroup.leaders = relationship('Member', secondary=leadership)
Member.led_workgroups = relationship('Workgroup', secondary=leadership)


def get_wg(session, request):
    ''' make a Workgroup object, use ID from request if possible '''
    wg = Workgroup('', '')
    if 'wg_id' in request.matchdict:
        wg_id = request.matchdict['wg_id']
        if wg_id == 'new':
            return wg
        try:
            wg_id = int(wg_id)
        except ValueError:
            raise Exception("No workgroup with ID %s" % wg_id)
        wg = session.query(Workgroup).get(wg_id)
        if wg:
            wg.exists = True
        else:
            raise Exception("No workgroup with ID %s" % wg_id)
    return wg
