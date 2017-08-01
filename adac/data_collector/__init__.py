<<<<<<< HEAD
'''Upload data from experiments where the logs can be viewed and stored
'''
import json
from urllib.parse import urlparse
from flask import Flask, request
from peewee import SqliteDatabase, OperationalError

def set_db(db_name):
    '''Set the app database'''
    return SqliteDatabase(db_name)

APP = Flask(__name__)
DB = set_db('dc.db')

@APP.before_request
def db_connect():
    try:
        DB.connect()
    except OperationalError as err:
        pass

@APP.after_request
def db_disconnect(response):
    try:
        DB.close()
    except:
        pass
    return response

from adac.data_collector.models import Statistic, Event, ConsensusData

@APP.route('/logs/<node>', methods=['GET', 'POST'])
def logs(node):
    '''Upload or download the run logs '''
    if request.method is 'GET':
        results = Event.select().where(Event.node_name == node)
        return json.dumps(results)
    elif request.method is 'POST':
        data = request.get_json()
        for d in data:
            Event.create(node_name=d['node_name'],
                         timestamp=d['timestamp'],
                         event_name=d['event_name'],
                         event_data=d['event_data'])
        return json.dumps({'msg': "Success"})


@APP.route('/statistics/<node>', methods=['GET', 'POST'])
def statistics(node):
    '''Upload or download statistics froma specific node
    Args:
        node (str): The name of the node
    '''
    if request.method is 'GET':
        results = Statistic.select().where(Statistic.node_name == node)
        return json.dumps(results)
    elif request.method is 'POST':
        data = request.get_json()
        for d in data:
            Statistic.create(node_name=request.remote_addr,
                             timestamp=d['timestamp'],
                             statistic_type=d['statistic_type'],
                             statistic_value=d['statistic_value'])
        return json.dumps({'msg': "Success"})
@APP.route('/statistics', methods=['POST'])
def post_stats():
    '''Upload statistics froma specific node'''
    data = request.get_json()
    data = json.loads(data)
    for d in data:
        Statistic.create(node_name=request.remote_addr,
                         timestamp=d['timestamp'],
                         statistic_type=d['statistic_type'],
                         statistic_value=d['statistic_value'],
                         iteration=int(d['iteration']),
                         experiment_id=d['experiment_id'])
    return json.dumps({'msg': "Success"})

@APP.route('/message', methods=['POST', 'GET'])
def show_message():
    '''Display a message from a node'''
    data = request.get_json()
    print('HOST: {} - msg {}'.format(request.remote_addr, data))
    return json.dumps({'msg': 'success'})

@APP.route("/consensusdata", methods=["POST"])
def consensus_data():
    '''Upload Consensus Data'''
    data = request.get_json()
    data = json.loads(data)
    for d in data:
        ConsensusData.create(node_name=request.remote_addr,
                             timestamp=d['timestamp'],
                             data=d['data'],
                             experiment_id=d['exp_id'])
    return json.dumps({'msg': 'success'})

def run():
    Statistic.create_table(fail_silently=True)
    Event.create_table(fail_silently=True)
    ConsensusData.create_table(fail_silently=True)
    APP.run('0.0.0.0', 5000)