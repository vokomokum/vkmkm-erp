'''
Display HTML and Text documents which lie in /docs
For now, we allow for one level of subdirectories.

We also provide simple upload capabilities for members of the docs
group.
'''

import os
import urllib
import shutil
from pyramid.view import view_config
from webob import Response
import magic

from members.views.base import BaseView
from members.utils.misc import get_settings


allowed_mime_types = [
    "text/plain",
    "text/html",
    "application/pdf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword"
]

def is_probably_doc_file(filename):
    """Guess based on filename if file is a doc file."""
    return filename.endswith('.html')\
            or filename.endswith('.txt')\
            or filename.endswith('.doc')\
            or filename.endswith('.docx')\
            or filename.endswith('.odt')\
            or filename.endswith('.pdf')


def upload_file(request, path):
    """Handle file upload"""
    try:
        if request.POST.get('new_doc', '') == '':
            raise Exception("No file given.")
        
        filename = request.POST['new_doc'].filename
        file_path = os.path.join(path, filename)
        
        # first check for filetype
        file_content = request.POST['new_doc'].file
        mime_type = magic.from_buffer(file_content.read(1024), mime=True)
        if mime_type not in allowed_mime_types:
            raise Exception("Mime type %s is not allowed for upload." %
                            mime_type)

        # We first write to a temporary file to prevent incomplete files from
        # being used.
        temp_file_path = file_path + '~'
        file_content.seek(0)
        with open(temp_file_path, 'wb') as output_file:
            shutil.copyfileobj(file_content, output_file)

        # Now that we know the file has been fully saved to disk move it into place.
        os.rename(temp_file_path, file_path)
    except Exception, e:
        return "There was a problem with uploading the file: %s" % str(e)

    return "The file was successfully uploaded."


@view_config(renderer='../templates/docs.pt',
             route_name='docs')
class DocsListView(BaseView):

    '''
    List available documents in selected subfolder of the general docs folder.
    Also handle Uploads.
    '''

    tab = 'docs'

    def __call__(self):
        msg = ''
        folder = '/'.join(self.request.matchdict['folder'])
        settings = get_settings()
        docs_folder = settings['vokomokum.docs_folder']
        folder_full_path = '{}/{}'.format(docs_folder, folder)
        
        # Check directory exists
        if not os.path.exists(folder_full_path):
            return dict(cur_folder=folder, folders=[], files=[],
                    msg='The folder {} does not exist'.format(folder_full_path))

        # Handle eventual upload
        if 'new_doc' in self.request.POST:
            if "Docs" in [wg.name for wg in self.user.workgroups]:
                msg = upload_file(self.request, folder_full_path)
            else:
                msg = "Only members of the Docs wokgroup can upload documents!"

        # Build a dict with filenames in each subdirectory
        files = [urllib.quote(f) for f in os.listdir(folder_full_path)\
                 if is_probably_doc_file(f)]
        files.sort()
        files.reverse() # assuming file names often start with date
        folders = [d for d in os.listdir(folder_full_path)\
                   if os.path.isdir('{}/{}'.format(folder_full_path, d))]
        folders.sort()

        return dict(cur_folder=folder, folders=folders, files=files, msg=msg)


@view_config(route_name='doc-view')
class DocView(BaseView):

    '''
    This reads in a document and streams it out as response.
    Documents are identifiable by their path such that they can be linked to.
    '''

    def __call__(self):
        if not self.logged_in:
            return self.redirect('/login') # not sure why this view needs this
        doc_path = self.request.matchdict['doc_path']
        doc_path = '/'.join(doc_path)
        doc_path = urllib.unquote(doc_path)
            
        settings = get_settings()
        docs_folder = settings['vokomokum.docs_folder']
        file_path = '{}/{}'.format(docs_folder, doc_path) 
        mime_type = magic.from_file(file_path, mime=True)
        with open(file_path, 'r') as f:
           data = f.read()
        return Response(data, content_type=mime_type)


@view_config(renderer='../templates/docs-upload-form.pt',
             route_name='doc-upload-form')
class DocsUploadFormView(BaseView):
    '''Display form for uploading a document'''

    tab = 'docs'

    def __call__(self):
        return dict(cur_folder=self.request.params.get("path"), msg='')
