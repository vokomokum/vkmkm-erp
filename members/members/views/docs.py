'''
Display HTML and Text documents which lie in /docs
For now, we allow for one level of subdirectories.
'''

import os
import urllib
from pyramid.view import view_config
from webob import Response

from members.views.base import BaseView
from members.utils.misc import get_settings


def is_doc_file(filename):
    return filename.endswith('.html') or filename.endswith('.txt')


@view_config(renderer='../templates/docs.pt',
             route_name='docs')
class DocsListView(BaseView):

    '''
    List available documents in selected subfolder of the general docs folder.
    '''

    tab = 'docs'

    def __call__(self):
        settings = get_settings()
        folder = self.request.matchdict['folder']
        docs_folder = settings['vokomokum.docs_folder']
        if not os.path.exists(docs_folder):
            return dict(cur_folder=folder, folders=[], files=[],
                    msg='The folder {} does not exist'.format(docs_folder))
        folder = '/'.join(folder)
        folder_full_path = '{}/{}'.format(docs_folder, folder)
        # a dict with filenames in each subdirectory
        files = [urllib.quote(f) for f in os.listdir(folder_full_path)\
                 if is_doc_file(f)]
        folders = [d for d in os.listdir(folder_full_path)\
                   if os.path.isdir('{}/{}'.format(folder_full_path, d))]
        return dict(cur_folder=folder, folders=folders, files=files, msg='')


@view_config(route_name='doc')
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
        file_format = doc_path.split('.')[-1]
        if file_format not in ('txt', 'html'):
            data = 'Unknown filetype: {}'.format(doc_path.split('.')[-1])
            content_type = 'text'
        else:
            if file_format == 'html':
                content_type = 'text/html'
            else:
                content_type = 'text'
            settings = get_settings()
            docs_folder = settings['vokomokum.docs_folder']
            with open('{}/{}'.format(docs_folder, doc_path), 'r') as f:
                data = f.read()
                f.close()
        return Response(data, content_type=content_type)
