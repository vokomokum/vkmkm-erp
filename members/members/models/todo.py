'''
TODO items
'''

class Todo(object):
    '''
    Each Todo has a descriptive text, a possible follow-up action link
    (relative route within the system), and for the link both a display text
    and a hover-over title for the link to that action.
    Finally, wg denotes whch workgroup this Todo belongs to.
    '''    

    msg = ''
    link_act = ''
    link_txt = ''
    link_title = ''
    wg = ''

    def __init__(self, msg='', link_act='', link_txt='', link_title='', wg=''):
        self.msg = msg
        self.link_act = link_act
        self.link_txt = link_txt
        self.link_title = link_title
        self.wg = wg

    def __repr__(self):
        return "[Todo - msg:{} act:{}]".format(self.msg, self.link_act)
