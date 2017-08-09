'''This file contains functions for using distributed consensus methods such as
 Corrective Consensus[1] and Accelerated Corrective Consensus[2]



- [1] <http://vision.jhu.edu/assets/consensus-cdc10.pdf>
- [2] <http://www.vision.jhu.edu/assets/ChenACC11.pdf>


'''
import math
import logging
import configparser
import time
from collections import deque
import requests
import adac.nettools as nettools
import numpy as np
from numpy import linalg as LA
import psutil
from adac.data_collector.util_logger import psLogger
from mpi4py import MPI as OMPI

# Consensus Functions
plogger = psLogger('.'.join([__name__, 'psutil']))
logger = logging.getLogger(__name__)
MPI = False

def get_weights(neighbors, config="params.conf", MPI_graph_comm=None):
    '''Calculate the Metropolis Hastings weights for the current node and its neighbors.

    Args:
            neighbors (iterable): An iterable of neighbor IP addresses to get degrees from

    Returns:
            dict: a dictionary mapping neighbors to Metropolis-Hastings Weights

    '''
    if neighbors is None:
        return {}
    weights = {}
    degs = {}
    conf = configparser.ConfigParser()
    conf.read(config)
    port = conf['node_runner']['port']
    my_deg = len(neighbors)
    for neigh in neighbors:

        if MPI_graph_comm is None:
            r_url = 'http://{}:{}/degree?host={}'.format(neigh, port, neigh)
            logger.debug('Attempting to get degree of node {}'.format(neigh))
            logger.debug('Degree request URL {}'.format(r_url))
            try:
                res = requests.get(r_url, timeout=0.5)

                if res.status_code == 200:
                    degs[neigh] = int(res.text)
                    weights[neigh] = 1 / (max(degs[neigh], my_deg) + 1)
                else:
                    weights[neigh] = 0
                    raise RuntimeError("One of the nodes could not be contacted")
            except:
                weights[neigh] = 0
        else:
            degs[neigh] = len(MPI_graph_comm.Get_neighbors(neigh))
            weights[neigh] = 1 / (max(degs[neigh], my_deg) + 1)

    return weights


def run(orig_data, tc, tag_id, neighbors, communicator):
    '''Run consensus v.s. a list of nodes in order to converge upon the network average.

    Args:
            orig_data (matrix): The data which we want to find a consensus with (numpy matrix)
            tc (int): Number of consensus iterations
            tag_id (num): A numbered id for this consensus run. Used when sending tag info
            neighbors (dict): an object outlining the neighbors of the current node and the weights
                         corresponding to each one.
            communicator (Communicator): The communicator object to send and receive messages.abs

    Returns:
            matrix: A numpy matrix with the agreed-upon consensus values.


    '''
    plogger.log_cpu_time("0")
    plogger.log_mem("0")
    plogger.log_network("0")
    logger.debug("tc: {}, tag_id: {}, num neighbors: {}, ".format(tc, tag_id, len(neighbors)))
    old_data = orig_data
    new_data = orig_data

    neigh_list = list(neighbors.keys())
    logger.debug("Old data before: {}".format(old_data))
    logger.debug("new data before: {}".format(new_data))
    missing_data = {}
    for n in neigh_list:
        missing_data[n] = deque()

    for i in range(tc):
        plogger.log_cpu_time('{}'.format(i+1))
        plogger.log_mem('{}'.format(i+1))
        plogger.log_network('{}'.format(i+1))
        logger.info('{} | Data: {}'.format(i+1, new_data))
        old_data = new_data

        # transfer data
        tag = build_tag(tag_id, i)
        b_data = nettools.matrix_to_bytes(new_data)
        transmit(b_data, tag, neighbors, communicator)
        data = receive(tag, neighbors, communicator)

        # Consensus
        tempsum = 0  # used for tracking 'mass' transmitted
        for j in neighbors:

            # Process any data which has arrived
            if data[j] != None:  # if data was received, then...
                t = nettools.matrix_from_bytes(data[j])
                diff = t - old_data
                logger.debug("diff from neighbor {} is {} ".format(j, diff))
                tempsum += neighbors[j] * diff  # 'mass' added to itself
            elif data[j] == None: # add to the missing queue
                missing_data[j].append(tag)
                logger.debug('Adding {} to missing packets of neighbor {}'.format(tag, j))

            # Attempt to get any missing data (Basically synchronization)
            # If I had to guess this is where performance issues stem from
            start = time.time()
            while len(missing_data[j]) > 0:
                if time.time() - start > 15:
                    logger.error('Consensus timed out while waiting for missing data')
                    return None
                tag1 = missing_data[j].popleft()
                # logger.debug('missing data tag: %s', tag1)
                d1 = communicator.get(j, tag1)
                if d1 != None:
                    logger.debug("Picked up old data on tag {}".format(tag1))
                    t = nettools.matrix_from_bytes(d1)
                    diff = t - old_data
                    logger.debug("diff from neighbor {} is {} ".format(j, diff))
                    tempsum += neighbors[j] * diff # weight * diff
                else:
                    missing_data[j].append(tag1)

            logger.debug("Tempsum iter {} is {}".format(i, tempsum))

        new_data = old_data + tempsum

    return new_data


def transmit(data, tag, neighbors, communicator):
    '''Send the data to every neighbor.

    Args:
            data (bytes): The bytes to transmit
            tag (bytes): The bytes representing the tag for the data
            neighbors (iterable): An iterable item containing the neighbors which we
                         want to send data to
            communicator (Communicator): The object used in sending and receiving data

    Returns:
            N/A
    '''
    if MPI:
        #  Send with MPI
        for n in neighbors:
            communicator.send(data, n, tag=int.from_bytes(tag, byteorder='little'))
    else:
        for n in neighbors:
            logger.debug('Consensus transmitting data to neighbor {} with tag {}'.format(n, tag))
            communicator.send(n, data, tag)


def receive(tag, neighbors, communicator):
    '''Attempt to retrieve the data from a set of neighbors

    Args:
            tag (bytes): a set of bytes identifying the data tag to retrieve
            neighbors (iterable): a list or dictionary of neighbors to retrieve data from
            communicator (Communicator): The communicator object which can access the data.

    Returns:
            dict: A dictionary mapping each neighbor to the data which is sent.
    '''
    data = {}
    if MPI:
        for n in neighbors:
            rectemp = communicator.recv(source=n, tag=int.from_bytes(tag, byteorder="little"))
            data[n] = rectemp
    else:
        for n in neighbors:
            tmp = communicator.get(n, tag)
            data[n] = tmp

    return data


def build_tag(tag_id, num):
    '''Creates a tag from tag_id and the iteration number

    Args:
        tag_id (int): identifier for consensus run
        num (int): The iteration number

    Returns:
        bytes: A unique tag in bytes.
    '''
    tag = (tag_id % 256).to_bytes(1, byteorder='little')
    if num > 0:
        bts = math.log(num, 2)  # number of bits required
        bts = math.ceil(bts / 8)  # number of bytes required
    else:
        bts = 3
    bts = max(3, bts)  # Should always give us at least 3 bytes to work with.
    tag += num.to_bytes(bts, byteorder='little')[0:3]
    return tag
