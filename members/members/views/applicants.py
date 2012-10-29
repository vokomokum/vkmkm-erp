from __future__ import unicode_literals

from pyramid.view import view_config
#from sqlalchemy import asc, desc

from datetime import datetime

from members.models.applicant import Applicant
from members.models.member import Member
from members.models.base import DBSession
from members.models.base import VokoValidationError
from members.views.base import BaseView
from members.views.pwdreset import send_pwdreset_request
from members.models.transactions import Transaction
from members.models.transactions import TransactionType
from members.models.transactions import get_ttypeid_by_name


def get_applicants(session):
    return session.query(Applicant)\
            .order_by(Applicant.month)\
            .all()

 
def get_applicant(session, a_id):
    return session.query(Applicant).get(a_id)


@view_config(renderer='../templates/applicants.pt',
             route_name='applicant-new',
             permission='edit')
class NewApplicant(BaseView):

    tab = 'members'

    def __call__(self):
        fname = self.request.params['fname']
        lname = self.request.params['lname']
        now = datetime.now()
        month = "{}/{}".format(unicode(now.month).rjust(2, '0'),
                               unicode(now.year)[-2:])
        comment = self.request.params['comment']
        email = self.request.params['email']
        telnr = self.request.params['telnr']
        hsize = int(self.request.params['household_size'])
        applicant = Applicant(None, fname, lname, month, comment, email,
                              telnr, hsize)
        applicant.validate()
        session = DBSession()
        session.add(applicant)
        session.flush()
        return dict(applicants=get_applicants(session),
                    msg="Applicant has been added to the list.")


@view_config(renderer='../templates/applicants.pt',
             route_name='applicant-delete',
             permission='edit')
class DeleteApplicant(BaseView):

    tab = 'members'

    def __call__(self):
        session = DBSession()
        a_id = self.request.matchdict['a_id']
        applicant = get_applicant(session, a_id)
        session.delete(applicant)
        session.flush()
        return dict(applicants=get_applicants(session),
                    msg="Applicant has been removed from list.")


@view_config(renderer='../templates/applicants.pt',
             route_name='applicant-mkmember',
             permission='edit')
class Applicant2Member(BaseView):

    tab = 'members'

    def __call__(self):
        session = DBSession()
        a_id = self.request.matchdict['a_id']
        applicant = get_applicant(session, a_id)
        # copy over our knowledge of him/her
        member = Member(self.request, applicant.fname, '', applicant.lname)
        now = datetime.now()
        txt = "Joined orientation in {}, became member in {}/{}.".format(\
                applicant.month, now.month, now.year)
        member.mem_adm_comment = "{}\n{}".format(txt, applicant.comment)
        member.mem_email = applicant.email
        member.mem_home_tel = applicant.telnr
        member.validate()
        session.add(member)
        # charge membership fee
        if applicant.household_size < 1:
            raise VokoValidationError('Please specify the household size.')
        t = Transaction(amount = applicant.household_size * 10 * -1,
                        comment = 'automatically charged for {} people in the '\
                                  'household'.format(applicant.household_size)
        )
        ttype = session.query(TransactionType)\
                       .get(get_ttypeid_by_name('Membership Fee'))
        t.ttype = ttype
        t.member = member
        t.validate()
        session.add(t)
        session.delete(applicant)
        session.flush()
        send_pwdreset_request(member, self.request.application_url, first=True)
        return self.redirect("/member/{}?msg=Applicant has been made "\
                            "into new Member and got an email to set "\
                            "up a password.".format(member.mem_id))


@view_config(renderer='../templates/applicants.pt',
             route_name='applicant-list',
             permission='edit')
class ApplicantList(BaseView):

    tab = 'members'

    def __call__(self):
        return dict(applicants=get_applicants(DBSession()), msg="")


