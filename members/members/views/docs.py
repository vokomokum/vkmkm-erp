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
    List available documents.
    TODO: pass a local path parameter to navigate folders (default: '')
    '''

    tab = 'docs'

    def __call__(self):
        settings = get_settings()
        docs_folder = settings['vokomokum.docs_folder']
        if not os.path.exists(docs_folder):
            return dict(files=[], msg='The folder {} does not exist'\
                       .format(docs_folder))
        # a dict with filenames in each subdirectory
        files = {'': [urllib.quote(f) for f in os.listdir(docs_folder)\
                      if is_doc_file(f)]}
        for d in [d for d in os.listdir(docs_folder)\
                  if os.path.isdir('{}/{}'.format(docs_folder, d))]:
            files[d] = [urllib.quote('{}/{}'.format(d, f))\
                        for f in os.listdir('{}/{}'.format(docs_folder, d))\
                        if is_doc_file(f)]
        return dict(files=files, msg='')


@view_config(route_name='doc')
class DocView(BaseView):

    '''
    This reads in a document and streams it out as response.
    Documents are identifiable by their path such that they can be linked to.
    
    '''

    def __call__(self):
        doc_id = urllib.unquote(self.request.matchdict['doc_id'])
        file_format = doc_id.split('.')[-1]
        if file_format not in ('txt', 'html'):
            data = 'Unknown filetype: {}'.format(doc_id.split('.')[-1])
            content_type = 'text'
        else:
            if file_format == 'html':
                content_type = 'text/html'
            else:
                content_type = 'text'
            settings = get_settings()
            docs_folder = settings['vokomokum.docs_folder']
            with open('{}/{}'.format(docs_folder, doc_id), 'r') as f:
                data = f.read()
                f.close()
        return Response(data, content_type=content_type)
