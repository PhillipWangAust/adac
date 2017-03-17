import pickle
import socket
import struct
import fcntl
import logging
import netifaces
import platform
logger = logging.getLogger(__name__)

def get_ip_address(ifname):
    '''Returns the IP Address

    Should be friendly with python2 and python3. Tested using a Raspberry Pi running Linux.
    Will not work with windows. Possibly with OS X/MacOS

    Args:
            ifname (str): Name of the network interface

    Returns:
            str: A string representing the 4x8 byte IPv4 address assigned to the interface.

    Throws:
            err: Will throw error if the interface doesn't exist. Use with method within try/catch.
    '''
    logger.debug('Getting IP address for interface %s', ifname)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if platform.system()=='Darwin':
        ip = netifaces.ifaddresses('en0')[2][0]['addr']
        pass
    else:
        ip = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname.encode('utf-8')))[20:24])
    return ip


def matrix_to_bytes(data):
    '''Convert a numpy matrix to an array of bytes to transfer
     over the network*

    *This is just a simple implementation. In production one should probably not use the pickle
    library. One reason against using pickle is that the process of unpickling data after it
    has been sent over the network can be maliciously modified to execute arbitrary code which
    inherntly presents a serious security hazard. Anyone using this code in a security-concious
    environment should replace the matrix_*_bytes pair of methods with a more suitable
    implementation.

    Args:
            data (obj): Data to convert to bytes

    Returns:
            bytes: The data in a byte representation
    '''
    pick = pickle.dumps(data)
    return pick


def matrix_from_bytes(data):
    '''Convert a byte array back into a numpy matrix.

    Please refer to the * note under ``nettools.matrix_to_bytes``
    about the security hazard that the pickling implementation
    leaves open.

    Args:
            data (bytes): An array of bytes to convert to a numpy
             matrix

    Returns:
            obj: An numpy matrix which was originally represented as bytes.

    '''
    return pickle.loads(data)
