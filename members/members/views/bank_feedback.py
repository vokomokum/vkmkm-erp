from members.models.mutation import Mutation
from members.utils.mutations import process_upload
from pyramid.security import has_permission

__author__ = 'diederick'

from pyramid.view import (
    view_config,
    view_defaults
)
from members.views.base import BaseView
from members.utils.misc import get_settings
from members.models.upload import Upload
from members.models.base import DBSession
import os
import uuid

@view_defaults(renderer = 'json', permission = 'view')
class JsonHandler(BaseView):

    def __init__(self, context, request):
        BaseView.__init__(self, context, request)
        self.request    = request
        self.dict       = request.matchdict
        self.settings = get_settings()


    @view_config(route_name = 'bank_get_upload_data', request_method = 'GET')
    def bank_get_upload_data(self):
        upload_id       = self.request.GET['upload_id']
        page_nr         = int(self.request.GET['page_nr'] ) if 'page_nr'  in self.request.GET else 0
        per_page        = int(self.request.GET['per_page']) if 'per_page' in self.request.GET else 10
        amount_filter   = self.request.GET['amount_filter'] if 'amount_filter' in self.request.GET else None
        name_filter     = self.request.GET['name_filter']   if 'name_filter' in self.request.GET else None
        offset          = page_nr * per_page
        session = DBSession()
        query = session.query(Mutation).filter(Mutation.upload_id == upload_id).order_by(Mutation.id)

        if amount_filter:
            query = query.filter(Mutation.amount == amount_filter )
            print 'amount_filter:'+str(amount_filter)
        if name_filter:
            query = query.filter(Mutation.name.like('%'+name_filter+'%'))
            print 'name_filter:'+name_filter

        total = query.count()
        mutations = query.limit(per_page).offset(offset).all()
        result = dict((i, x.json) for i, x in enumerate(mutations)) #dict((x.id, x.json) for x in mutations)
        page_nr = page_nr if page_nr * per_page < total else 0
        result[-1]=dict(total=total, this_page=len(mutations), page_nr=page_nr, per_page=per_page)
        return result



@view_defaults(renderer = '../templates/tridios.pt', permission = 'view')
class IndexView(BaseView):

    def __init__(self, context, request):
        BaseView.__init__(self, context, request)
        self.request    = request
        self.dict       = request.matchdict
        self.settings = get_settings()


    def match(self, key):
        value = self.dict[key] if key in self.dict else None
        return None if value == ' ' else value


    @view_config(route_name = 'bank_feedback_index', request_method = 'GET')
    def bank_feedback(self):
        session = DBSession()
        uploads = session.query(Upload).order_by(Upload.id).all()
        return { 'uploads': uploads, 'id_': '${id}', 'amount_': '${amount}', 'contra_account_': '${contra_account}',
                 'description_': '${description}', 'name_': '${name}', 'type_': '${type}' }


    @view_config(route_name = 'bank_feedback_upload', request_method = 'POST')
    def bank_feedback_upload(self):
        filename        = self.request.POST['file'].filename
        input_file      = self.request.POST['file'].file
        target_folder   = self.settings['vokomokum.upload_folder']
        file_path       = os.path.join(str(target_folder), '%s.csv' % uuid.uuid4())
        temp_file_path = file_path + '~'
        output_file = open(temp_file_path, 'wb')
        # Finally write the data to a temporary file
        input_file.seek(0)
        while True:
            data = input_file.read(2<<16)
            if not data:
                break
            output_file.write(data)
        # If your data is really critical you may want to force it to disk first
        # using output_file.flush(); os.fsync(output_file.fileno())
        output_file.flush()
        output_file.close()
        # Now that we know the file has been fully saved to disk move it into place.
        os.rename(temp_file_path, file_path)
        session = DBSession()
        #self.m.mem_id or self.user.mem_admin
        upload = Upload(member_id = self.user.mem_id, file = str(file_path))
        session.add(upload)
        session.flush()
        process_upload(upload, session)
        return self.bank_feedback()

# class UploadProcessor():
#     @view_config(renderer = 'json', route_name = 'bank_feedback_upload', name = 'upload.json')
#     def bank_feedback_upload(self, request):
#         filename    = request.POST['file'].filename
#         print 'uploaded: '+ str(filename)
#         return [1,2,3]
#         #input_file  = request.POST['file'].file
