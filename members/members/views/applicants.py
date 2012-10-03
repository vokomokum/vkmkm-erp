from pyramid.view import view_config
#from sqlalchemy import asc, desc

from datetime import datetime

from members.models.applicant import Applicant
from members.models.member import Member
from members.models.base import DBSession
from members.views.base import BaseView


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

    tab = 'applicants'

    def __call__(self):
        fname = self.request.params['fname']
        lname = self.request.params['lname']
        now = datetime.now()
        month = "{}/{}".format(now.month, now.year)
        comment = self.request.params['comment']
        email = self.request.params['email']
        telnr = self.request.params['telnr']
        applicant = Applicant(None, fname, lname, month, comment, email, telnr)
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

    tab = 'applicants'

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

    tab = 'applicants'

    def __call__(self):
        session = DBSession()
        a_id = self.request.matchdict['a_id']
        applicant = get_applicant(session, a_id)
        member = Member(self.request, applicant.fname, '', applicant.lname)
        member.mem_adm_comment = applicant.comment
        member.mem_email = applicant.email
        member.mem_home_tel = applicant.telnr
        print "|{}|".format(member.mem_postcode)
        member.validate()
        session.add(member)
        session.delete(applicant)
        session.flush()
        return self.redirect("/member/{}?msg=Applicant has been made "\
                            "into new Member.".format(member.mem_id))


@view_config(renderer='../templates/applicants.pt',
             route_name='applicant-list',
             permission='edit')
class ApplicantList(BaseView):

    tab = 'applicants'

    def __call__(self):
        return dict(applicants=get_applicants(DBSession()), msg="")


