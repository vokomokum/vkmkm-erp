'''
Code to generate interesting data to be graphed and the graph configuration
with it, while we're on it.
The graphs are meant to be shown using highcharts, an open source library. 
Here is an example how to put such a graph in a template:

window.onload = function(){ //$ is not known yet (bottom of page)
                    $('#graph').highcharts(${graph});
                };

where ${graph} is a view variabl containing the content of the graph files
written by this module.
'''

import json

from members.models.base import DBSession
from members.models.member import Member
from members.models.orders import Order, MemberOrder
from members.utils.misc import get_settings


def orders_money_and_people():
    '''
    Count money and number of people who ordered for each order cycle.
    A more straightforward way to do this might be transactions, but we have 
    lots of legacy data without them at Vokomokum and this also works okay.
    '''
    # 1. preparing the data
    session = DBSession()
    orders = session.query(Order).order_by(Order.completed).all()
    members = session.query(Member).all()
    money_list = []
    people_list = []
    max_money = 0
    max_people = 0

    for o in orders:
        money = 0
        people = 0
        for m in members:
            mo = MemberOrder(m, o)
            if mo.amount > 0:
                money += mo.amount
                people += 1
        money_list.append(round(money, 1))
        max_money = max(money, max_money)
        max_people = max(people, max_people)
        people_list.append(people)

    # 2. writing graph configuration
    graph = dict(title=dict(text='Order history'), credits=dict(enabled=False))
    graph['series'] = []
    graph['series'].append(dict(name='money', data=money_list))
    graph['series'].append(dict(name='people', data=people_list, yAxis=1))
    graph['xAxis'] = dict(categories=[o.label for o in orders],
                          tickPositions=[0, len(orders)/2, len(orders)-1])
    graph['yAxis'] = [dict(title=dict(text='money'), min=0, max=max_money*1.1),
                      dict(title=dict(text='people'), min=0, max=max_people*1.1,
                           opposite=True)]

    # 3. write to file 
    settings = get_settings()
    gf = settings['vokomokum.graph_folder']
    json.dump(graph, open('{}/orders_money_and_people.json'.format(gf), 'w')) 
    

