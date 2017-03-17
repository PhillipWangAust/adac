'''Run with flask as an HTTP server to communicate starting points of CloudK-SVD and Consensus
'''
import json
import logging
import sys
import traceback
import uuid
from configparser import ConfigParser
from multiprocessing import Process, Value
from urllib.parse import urlparse
import numpy as np
import adac.consensus.iterative as consensus
import adac.nettools as nettools
from adac.communicator import Communicator
import requests
from flask import Flask, request
from mpi4py import MPI as OMPI

class IDFilter(logging.Filter):
    def __init__(self, id):
        self.id = id
    def filter(self, record):
        record.id = self.id
        return True
APP = Flask(__name__)
TASK_RUNNING = Value('i', 0, lock=True)  # 0 == False, 1 == True
CONF_FILE = 'params.conf'
idfilt = IDFilter('0000-0000')
logger = logging.getLogger(__name__)
MPI = False


def data_loader(filename):
    '''Reads in data line by line from file. and stores in Numpy array

    Each line of the file is a new vector with the format 1 2 3 ... n where n is the length of the
    vector. The numbers are separated by spaces.

    Args:
        str: name of data file

    Returns:
        Numpy array: vectors read from each line of file

    '''

    vectors = []
    with open(filename, 'r') as f:
        for line in f:
            v = list(map(lambda x: int(x), line.split(' ')))
            vectors.append(v)
        data = np.array(vectors)

    return data


def get_neighbors():
    '''Gets IP addresses of neigbors for given node

    Args:
            N/A

    Returns:
            (iterable): list of IP addresses of neighbors. None if no neighbors were found. Check
            logs for additional information if you keep getting "None".
    '''

    global CONF_FILE
    con = ConfigParser()
    con.read(CONF_FILE)
    v = json.loads(con['graph']['nodes'])
    e = json.loads(con['graph']['edges'])
    ip = None
    try:
        ip = nettools.get_ip_address(con['network']['iface'])
    except OSError as err:
        logger.warning('Could not retrieve ip address: %s', err)
        ip = nettools.get_ip_address('wifi0') # Bash on Windows default wlan device
        logger.info('Successfully retrieved IP address')

    if ip is None:
        raise OSError('Could not retrieve our IP address. Make sure your connection is "wlan0" or "wifi0"')

    logger.debug('IP of wlan0/wifi0 is %s', ip)

    try:
        i = v.index(ip)
    except ValueError as err:
        logger.warning('IP %s was not found in neighbor list', ip)
        return None
    n = []
    for x in range(len(v)):
        if e[i][x] == 1 and x != i:
            n.append(v[x])

    return n
def get_indexAndEdges():
    '''Gets index and edge lists to be passed into OMPI.COMM_WORLD.Create_graph

    Args:
            N/A

    Returns:
            (iterable): list of indexes
            (iterable): list of edges
    '''
    global CONF_FILE
    con = ConfigParser()
    con.read(CONF_FILE)
    graph = json.loads(con['graph']['edges'])
    edges = []
    index = []
    index_count = 0
    for i in range(len(graph)):
        for j in range (len(graph[i])):
            if graph[i][j]==1:
                if i != j:
                    edges.append(j+1)
                    index_count += 1
        index.append(index_count)
        if edges ==[]:
            edges.append(1);                                                                                                                                                                                                                                                                                                                                                                                                                                     
    return index, edges

@APP.route("/start/consensus")
def run():
    '''Start running distributed consensus on a
    separate process.

    The server will not kick off a new consensus
     job unless the current consensus has already completed.

    Args:
        N/A

    Returns:
        str: A message detailing whether or not the consensus
         job was started.
    '''
    msg = ""
    global TASK_RUNNING
    logger.debug('Attempting to kickoff task')

    #open config file set mpi to true or false
    global CONF_FILE
    global MPI
    config = ConfigParser()
    config.read(CONF_FILE)
    MPI = config['consensus'].getboolean('MPI')

    if TASK_RUNNING.value != 1:
        iterations = 50
        try:
            iterations = int(request.args.get('tc'))
        except:
            iterations = 50

        cid = request.args.get('id')
        if cid is None:
            # ID not present - generate one and pass is on
            cid = uuid.uuid4()
        idfilt.id = cid

        logger.debug('Setting consensus iterations to {}'.format(iterations))
        p = Process(target=kickoff, args=(TASK_RUNNING,iterations,cid))
        p.daemon = True
        p.start()
        logger.debug('Started new process')
        msg = "Started Running Consensus"
        with TASK_RUNNING.get_lock():
            TASK_RUNNING.value = 1
    else:
        logger.debug('Task already running')
        msg = "Consensus Already Running. Please check logs"

    return msg

def kickoff(task, tc, consensus_id):
    '''The worker method for running distributed consensus.

        Args:
            task (int): The process-shared value denoting whether the taks is running or not.

        Returns
            N/A
    '''
    # This the where we would need to do some node discovery, or use a pre-built graph
    # in order to notify all nodes they should begin running
    global CONF_FILE
    c = None
    neighs = None
    try:
        config = ConfigParser()
        logger.debug('Task was kicked off.')
        config.read(CONF_FILE)
        port = config['consensus']['port']
        logger.debug('Communicating on port {}'.format(port))
        if MPI:
            c = OMPI.COMM_WORLD
            comm = OMPI.Intracomm(c)
             #index and edges returned from function that converts adjacency matrix to MPI syntax
            index, edges = get_indexAndEdges()
            graph = comm.Create_graph(index, edges)
            rank = c.Get_rank()
            neighs = graph.Get_neighbors(rank)
            #populate neighs with ranks of neghbor nodes using Graphcomm.get_neighbors()
        else:
            c = Communicator('tcp', int(port))
            c.listen()
            logger.debug('Now listening on new TCP port %s', port)
            neighs = get_neighbors()
        ####### Notify Other Nodes to Start #######
        port = config['node_runner']['port']
        logger.debug('Attempting to tell all other nodes in my vicinity to start')

        if neighs is None:
            logger.warning("No neighbors found - consensus finished")
        else:
            for node in neighs:
                req_url = 'http://{}:{}/start/consensus?tc={}&id={}'.format(node, port, tc, consensus_id)
                logger.info('Kickoff URL for node {} is {}'.format(node, req_url))
                try:
                    logger.debug("MAKING REUQEST")
                    requests.get(req_url, timeout=0.1)
                    logger.debug('Made kickoff request')
                except:
                    logger.warning("Could not hit node {} at {}".format(node, req_url))
        ########### Run Consensus Here ############
        # Load parameters:
        # Load original data
        # get neighbors and weights get_weights()
        # Pick a tag ID (doesn't matter) --> 1
        # communicator already created
        logger.debug('My neighbors {}'.format(neighs))
        weights = consensus.get_weights(neighs)
        logger.debug('Neighbor weights {}'.format(weights))
        data = data_loader(config['data']['file'])
        logger.debug('Loaded data')
        try:
            #set MPI to true or false
            consensus.MPI = MPI
            consensus_data = consensus.run(data, tc, 1, weights, c)
            logger.info("~~~~~~~~~~~~~~ CONSENSUS DATA ~~~~~~~~~~~~~~~~")
            logger.info('{}'.format(consensus_data))
            logger.info("~~~~~~~~~~~~~~ CONSENSUS DATA ~~~~~~~~~~~~~~~~")
            logger.debug('Ran consensus')
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            # logger.error("Error: {}".format(e))
            logger.error('Consensus exception %s', repr(traceback.format_tb(exc_traceback)))
    except BaseException as err:
        logger.error('Error while running consensus: %s', err)
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # logger.error("Error: {}".format(e))
        logger.error('Consensus exception %s', repr(traceback.format_tb(exc_traceback)))
    finally:
        if isinstance(c, Communicator):
            c.close()

    try:
        logger.debug('parsing and sending logs as json')
        global config_file
        config = ConfigParser()
        config.read(CONF_FILE)
        f = config['logging']['log_file']
        post_url = config['collector']['url']
        content = []
        with open(f, 'r') as fhandle:
            content = fhandle.readlines()
        stats = []
        events = []
        for line in content:
            line = line.strip()
            if 'psutil' in line:
                fields = line.split(' | ')
                datadict = {'timestamp': fields[0],
                            'iteration': fields[3],
                            'statistic_type': fields[4][:fields[4].index('(')],
                            'statistic_value': fields[4][fields[4].index('(')+1:-1],
                            'experiment_id': fields[5]}

                stats.append(datadict)
            else:
                pass # event
        requests.post(post_url + '/statistics', json=json.dumps(stats))

    except BaseException as err:
        logger.info('error when processing log file: %s', str(err))

    with task.get_lock():
        task.value = 0


@APP.route('/degree')
def get_degree():
    '''Get the degree of connections for this node.
    We assume the node is always connected to itself, so the number should always be atleast 1.
    '''
    global CONF_FILE
    c = ConfigParser()
    c.read(CONF_FILE)
    host = request.args.get('host')
    a = json.loads(c['graph']['nodes'])
    e = json.loads(c['graph']['edges'])
    host_index = a.index(host)
    cnt = 0
    for j in e[host_index]:
        cnt += j

    cnt -= 1
    # minus one to exlude no self-loops from count
    return str(cnt)


def start():
    # Use a different config other than the default if user specifies
    global config_file
    config = ConfigParser()
    if len(sys.argv) > 1:
        CONF_FILE = sys.argv[1]
    else:
        CONF_FILE = "params.conf"
    config.read(CONF_FILE)

    log_fmt = '%(asctime)s | %(name)s | %(levelname)s | %(message)s | %(id)s'
    root_level = int(config['logging']['level'])
    fh = logging.FileHandler(config['logging']['log_file'], mode='w')
    fh.setLevel(root_level)
    fh.setFormatter(logging.Formatter(log_fmt))
    fh.addFilter(idfilt)
    logging.basicConfig(handlers=[fh])
    root = logging.getLogger()
    root.setLevel(root_level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(root_level)
    formatter = logging.Formatter(log_fmt)
    ch.setFormatter(formatter)
    ch.addFilter(idfilt)
    root.addHandler(ch)

    nr = config['node_runner']
    APP.run(nr['host'], nr['port'])

if __name__ == "__main__":
    start()





