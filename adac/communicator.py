'''Communicator which handles UDP/TCP communication

'''
import inspect
import json
import logging
import math
import socket
import struct
import threading
import collections


TAG_SIZE = 4
SEQ_SIZE = 2
UDP = 10
TCP = 20


def get_mtu():
    '''Attempts to return the MTU for the network by finding the min of the
    first hop MTU and 576 bytes. i.e min(MTU_fh, 576)

    Note that the 576 byte sized MTU does not account for the checksum/ip headers so
    when sending data we need to take the IP/protocol headers into account.

    The current implementation just assumes the default minimum of 576.
    We should try to implement something to actually calculate min(MTU_fh, 576)

    Returns:
        int: 576
    '''
    return 576


def check_port(port):
    '''Checks if a port is valid.

    A port is restricted to be a 16 bit integer which is in the range 0 < port < 65535.
    Typically most applications will use ports > ~5000

    Args:
        port (int): The port number. ValueError raised if it is not an int.

    Returns:
        bool: Only will return True. Anything invalid will result in a ValueError

    '''
    if isinstance(port, int) is not True:  # Ensure we're dealing with real ports
        raise TypeError("port must be an integer")
    elif port < 0 or port > 65535:
        raise ValueError("port must be between 0 and 65535")
    else:
        return True


def get_payload(payload):
    '''Take data payload and return a byte array of the object. Should be
    structured as a dict/list object. Note this method is slightly expensive
    because it encodes a dictionary as a JSON string in order to get the bytes

    We also set the separators to exclude spaces in the interest of saving
     data due to spaces being unnecessary. This is a primitive way to convert
    data into bytes and you can load it.

    Args:
        payload(obj): A JSON serializable object representing the payload data

    Returns:
        bytes: The object as a utf-8 encoded string
    '''
    data = json.dumps(payload, separators=[':', ',']).encode('utf-8')
    return data


def decode_payload(payload):
    '''Takes a byte array and converts it into an object using ``json.loads``

    Args:
        payload (bytearray): An array of bytes to decode and convert into an object.

    Returns:
        dict/list: A dictionary or list object depending on the JSON that was encoded
    '''

    data = json.loads(payload.decode('utf-8'), separator=([':', ',']))
    return data

def build_meta_packet(seq_num, seq_total, tag):
    '''Create a bytearray which returns a sequence of bytes based on the metadata

    Args:
        seq_num(int): The packet's sequence number
        seq_total(int): The total number of sequence packets to be sent
        tag (bytes): A string or bytes object to encode as the data tag

    Returns:
        bytearray: A bytearray with the metadata
    '''
    if isinstance(seq_total, int) is False or isinstance(seq_num, int) is False:
        raise TypeError("Sequence number and total must be integer")
    packet = bytearray()
    packet += struct.pack('H', seq_total)
    packet += struct.pack('H', seq_num)
    packet += tag[0:4]
    return packet

class Communicator:
    '''This is a threaded class interface designed to send and receive messages
     'asynchronously' via python's threading interface. It was designed mainly
      designed for use in communication for the algorithm termed 'Cloud K-SVD'.

    This class provides the following methods for users

    - listen: Starts the threaded listener
    - send: sends data via the open socket
    - get: retrieve data from the data-store
    - stop: stop listening on the thread

    The typical sequence will be something like the following:

    1. Take the object you wish to send. Encode it to bytes.
     i.e. ``my_bytes = str([1, 2, 3, 4, 5]).encode('utf-8')``
    2. After encoding to bytes and creating a communicator,
     use ``send()`` in order to send it to the listening host.
     The methods here will take care of packet fragmenting and
     makes sure messages are reassembled correctly. You
     must also add a 'tag' to the data. It should be a 4-byte
     long identifier. For strings this is limited to 4 characters.
      Anything longer than 4 is truncated

      - ``comm.send('IP_ADDRESS', my_bytes, 'tag1')``


    3. After sending, there's nothing else for the client to do'
    4. When the packet reaches the other end, each packet is received and
     catalogged. Once all of the pieces of a message are received,
    the message is transferred as a whole to the data store where it can
     be retrieved
    5. Use ``get()`` to retrieve the message from the sender and by tag. ``comm.get('ip', 'tag1')``

    As simple as that!

    Notes:

    - A limitation (dependent upon python implementation) is that there may only be a single python
    thread running at one time due to GIL (Global Interpreter Lock)

    - There is an intermediate step between receiving data and making it
     available to the user. The object must receive all packets in order to
     reconstruct the data into its original form in bytes. This is performed
     by the ``receive`` method.

    - Data segments which have not been reconstructed lie within
     ``self.tmp_data``. Reconstructed data is within ``self.data_store``

    Constructor Docs

    Args:
        protocol (str): A string. One of 'UDP' or 'TCP' (case insensistive)
        listen_port(int): A port between 0 and 65535
        send_port(int): (Optional) Defaults to value set for listen_port, otherwise
         must be set to a valid port number.

    '''

    def __init__(self, protocol, listen_port, send_port=None):
        '''Constructor'''
        protocol = protocol.upper()
        if protocol not in ['TCP', 'UDP']:
            raise ValueError('Protocol must be one of TCP or UDP')

        if protocol == 'TCP':
            self.protocol = TCP  # The protocol an upper case string 'TCP' or 'UDP'
        else:
            self.protocol = UDP

        # Check and create sockets
        if send_port is not None and check_port(send_port):
            self.send_port = send_port
            if self.protocol == TCP:
                self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            else:
                self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        if check_port(listen_port):
            self.listen_port = listen_port
            if self.protocol == TCP:
                self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            else:
                self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            self.send_port = self.listen_port
            if send_port is None and self.protocol == UDP:  # If the port and socket were not set

                self.send_sock = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM)
            elif send_port is None and self.protocol == TCP:  # If the port and socket were not set
                self.send_sock = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM)

        # Set to nonblocking in order to get our threaded server to work :) (We
        # should investigate the performance impact of this)
        self.listen_sock.setblocking(False)
        # Set the defaults for the thread and listening object
        self.is_open = True
        self.listen_thread = None
        # This tells the listening thread whether or not it need to continue
        # looping to receive messages
        self.connections = {}
        self.is_listening = False
        self.tmp_data = {}
        self.data_store = {}
        self.mtu = get_mtu()
        self.recv_callback = None
        self.conn_lock = threading.Lock()
        self.data_store_lock = threading.Lock()

    def register_recv_callback(self, callback):
        '''Allows one to register a callback function which is executed whenever a
        full message is received and decoded.

        The callback must have the signature of ``(str, bytes, bytes)`` where ``str`` is the sender
        address. The first ``bytes`` is the tag. The second ``bytes`` is the data.

        Args:
            callback (func): A function with arguments of (sender, tag, data)

        Returns:
            N/A
        '''
        if isinstance(callback, collections.Callable) is not True:
            raise TypeError("Callback must be a function")
        fullspec = inspect.getfullargspec(callback)
        n_args = len(fullspec[0])
        if n_args != 3:
            raise ValueError("Callback function did not have 3 arguments.")
        self.recv_callback = callback

    def close(self):
        '''Closes both listening sockets and the sending sockets

        The sockets may only be closed once. After closing a new object must be created.

        Args:
            N/A

        Returns:
            N/A

        Raises:
            BrokenPipeError: If close was already called previously.

        '''
        if self.is_open is True:
            self.stop_listen()
            self.listen_sock.close()
            self.send_sock.close()
            self.is_open = False
        else:
            raise BrokenPipeError(
                'Cannot close. Sockets were previously closed.')

    def listen(self):
        '''Start listening on port ``self.listen_port``. Creates a new thread where the socket will
        listen for incoming data

        Args:
            N/A

        Returns:
            N/A

        '''
        if self.is_open != True:
            raise BrokenPipeError(
                'Cannot listen. Sockets were previously closed.')

        if self.listen_thread is None:  # Create thread if not already created
            if self.protocol is UDP:
                self.listen_thread = threading.Thread(target=self.__run_listen__,
                                                      args=(self.listen_sock, '0.0.0.0',
                                                            self.listen_port))
            else:
                self.listen_thread = threading.Thread(target=self.__run_tcp__,
                                                      args=(self.listen_sock, '0.0.0.0',
                                                            self.listen_port))

            self.is_listening = True
            self.listen_thread.start()



    def __run_connect__(self, connection, addr):
        '''Worker methods which receive data from TCP connections.

        Args:
            connection (connection): A TCP connection from socket.accept()
            addr (str): The Inet(6) address representing the address of the client
        '''

        while self.is_listening:
            try:
                data = connection.recv(2048)
                if data is not None:
                    self.receive_tcp(data, addr)
            except:
                break

        self.conn_lock.acquire()
        connection.close()
        self.connections.pop(addr, None) # Remove the connection
        self.conn_lock.release()
        return

    def __run_tcp__(self, _sock, host, port):
        '''Method which accepts TCP connections and passes them off to run_connect


        Args:
            _sock (sockets.socket): A socket object to bind to
            host (str): The hostname/IP that we should bind the socket to. Use empty string '' for
            senders who wish to contact you outside the network.
            port (int): The port as an integer
        '''

        _sock.bind((host, port))
        _sock.listen(3) # Accept maximum of three un-accepted conns before refusing
        threads = []
        while self.is_listening:
            conn, addr = _sock.accept()
            self.conn_lock.acquire()
            self.connections[addr] = conn
            self.conn_lock.release()
            thd = threading.Thread(target=self.__run_connect__,
                                   args=(conn, addr))
            threads.append(thd)
            thd.start()



    def __run_listen__(self, _sock, host, port):
        '''Worker method for the threaded listener in order to retrieve incoming messages

        Args:
            _sock (sockets.socket): A socket object to bind to
            host (str): The hostname/IP that we should bind the socket to. Use empty string '' for
            senders who wish to contact you outside the network.
            port (int): The port as an integer

        Returns:
            N/A

        '''

        _sock.bind((host, port))

        while self.is_listening:
            try:
                data, addr = _sock.recvfrom(1024)  # Receive at max 1024 bytes
                # logging.debug('Received data from address {}'.format(addr))
                self.receive(data, addr[0])
            except BlockingIOError:
                pass

        _sock.close()

    def create_packets(self, data, tag):
        '''Segments a chunk of data (payload) into separate packets in order to send in sequence to
        the desired address.

        The messages sent using this class are simple byte arrays, which include metadata, so in
        order to segment into the correct number of packets we also need to calculate the size of
        the packet overhead (metadata) as well as subtract the IP headers in order to find the
        maximal amount of payload data we can send in a single packet.

        We need to use the MTU in this case which we'll take as typically a minimum of 576 bytes.
        According to RFC 791 the maximum IP header size is 60 bytes (typically 20), and according
        to RFC 768, the UDP header size is 8 bytes. This leaves the bare minimum payload size to be
        508 bytes. (576 - 60 - 8).

        We will structure packets as such (not including IP/UDP headers)

        +---------------------+--------------------+---------------+
        | Seq.Total (2 bytes) | Seq. Num (2 bytes) | Tag (4 bytes) |
        +---------------------+--------------------+---------------+
        |                      Data (500 Bytes)                    |
        +----------------------------------------------------------+

        A limitation is that we can only sequence a total of 2^16 packets which, given a max data
        size of 500 bytes gives us a maximum data transmission of (2^16)*500 ~= 33MB for a single
        request.

        Also note that the Seq Num. is zero-indexed so that the maximum sequence number (and the
        sequence total) will go up to ``len(packets) - 1``. Or in other words, 1 less than the
        number of packets.

        Args:
            data (bytes): The data as a string which is meant to be sent to its destination
            tag (bytes): A tag. Only the first 4 bytes are added as the tag.

        Returns
            list: A list containing the payload for the packets which should be sent to the
            destination.
        '''
        packets = []
        max_payload = self.mtu - 68  # conservative estimate to prevent IP fragmenting on UDP
        metadata_size = 8  # 8 bytes
        data_size = len(data)
        max_data = max_payload - metadata_size

        # TWO CASES
        # - We can send everything in 1 packet
        # - We must break into multiple packets which will require sequencing
        if data_size <= max_data:
            # Assemble the packet, no sequencing
            payload = build_meta_packet(0, 0, tag)
            payload += data
            packets.append(payload)
        else:
            total_packets = math.floor(data_size / max_payload)
            for i in range(total_packets):  # [0, total_packets-1]
                pkt1 = build_meta_packet(i, total_packets, tag)

                # Slice data into ~500 byte packs
                dat1 = data[i * max_data:(i + 1) * max_data]
                pkt1 += dat1
                packets.append(pkt1)
            # Build the  final packet
            pkt1 = build_meta_packet(total_packets, total_packets, tag)
            min_bound = (total_packets) * max_data
            dat1 = data[min_bound:]
            pkt1 += dat1
            packets.append(pkt1)

        return packets

    def tcp_send(self, addrs, data, tag):
        '''Sends data to the list of specified hosts

        Args:
            addrs (list): List of addresses to send to
            data (bytes): Data to send
            tag (bytes): Message identifier

        '''
        # Create the packet with tag at the top
        msg = bytearray()
        msg += tag
        msg += data
        for addr in addrs:
            if addr in self.connections:
                self.connections[addr].send(data)
            else:
                # Need to create a new connection and a listener thread
                conn = self.send_sock.connect((addr, self.send_port))
                conn_thread = threading.Thread(target=self.__run_connect__,
                                               args=(conn, addr))
                self.conn_lock.acquire()
                self.connections[addr] = conn # This is ok b/c thread doesn't start yet.
                self.conn_lock.release()
                conn.send(msg)
                conn_thread.start()


    def send(self, ip_addr, data, tag):
        '''Send a chunk of data with a specific tag to an ip address. The packet will be
        automatically chunked into N packets where N = ceil(bytes/(MTU-68))

        Args:
            ip (str): The hostname/ip to send to
            data (bytes): The bytes of data which will be sent to the other host.
            tag (str): An identifier for the message

        Returns:
            bool: True if all packets were created and sent successfully.
        '''

        # As simple as just creating the packets and sending each one
        # individually
        if self.is_open != True:
            raise BrokenPipeError('Socket was already closed by user')

        ret = True
        packets = self.create_packets(data, tag)
        # logging.debug("Sending {} packet(s) to {}".format(len(packets), ip))
        for packet in packets:
            # logging.debug('Sending packet to IP: {} on port {}'.format(ip, self.send_port))
            try:
                if self.send_sock.sendto(packet, (ip_addr, self.send_port)) < 0:
                    logging.debug("Some packets were not sent successfully")
                    ret = False

            except OSError as err:
                ret = False
                logging.warning(str(err))
                break
        return ret

    def get(self, ip_addr, tag):
        '''Get a key/tag value from the data store.

        The data is only going to be located in the data store if every single packet for the given
        tag was received and able to be reassembled. Otherwise the incomplete data will reside
        in ``self.tmp_data``.

        The ``self.data_store`` object has the following structure:

        .. code-block:: javascript

            {
                ip_address: {
                    tag_1: data,
                    tag_2: data2
                }
            }


        Args:
            ip (str): The ip address of the host we wish get data from
            tag (bytes/bytearray): The data tag for the message which is being received

        Returns:
            bytes: ``None`` if complete data is not found, Otherwise if found will return the data

        '''
        data = None
        tg_int = int.from_bytes(tag, byteorder='little')
        if ip_addr not in self.data_store:
            data = None
        elif tg_int not in self.data_store[ip_addr]:
            data = None
        else:
            self.data_store_lock.acquire()
            data = self.data_store[ip_addr][tg_int]
            self.data_store[ip_addr][tg_int] = None
            self.data_store_lock.release()
        return data

    def stop_listen(self):
        '''Stop listening for new messages and close the socket.

        This will terminate the thread and join it back in.

        Args:
            N/A

        Returns:
            N/A

        '''
        if self.listen_thread != None:
            self.is_listening = False
            self.listen_thread.join()
            self.listen_thread = None

    def receive_tcp(self, data, addr):
        '''Stores the TCP data reveived into the data store

        Args:
            data (bytes) : The data to store.
            addr (str): The ip address of the node.

        '''
        if len(data) < 4:
            # Log error on data
            return
        data_tag = int.from_bytes(data[:4], byteorder='little')

        if addr in self.data_store:
            self.data_store_lock.acquire()
            self.data_store[addr][data_tag] = data[4:]
            self.data_store_lock.release()
        else:
            self.data_store_lock.acquire()
            self.data_store[addr] = {}
            self.data_store[addr][data_tag] = data[4:]
            self.data_store_lock.release()
        return

    def receive(self, data, addr):
        '''Take a piece of data received over the socket and processes the data and attempt to
        combine packet sequences together, passing them to the data store when ready.

        ``self.tmp_data`` is an object with the structure

        .. code-block:: javascript

            {
                ip_address: {
                    tag_1: {
                        'seq_total': Max_num_packets,
                        'packets' = {
                            1: packet_data_1,
                            2: packet_data_2,
                            ...
                            ...
                        }
                    },
                    tag_2: {
                        ...
                    }
                },
                ip_address_2 : {
                    ...
                }
            }

        Args:
            data (bytes): a packet of data received over the socket to process
            addr (str): The ip address or hostname of the sending host

        Returns:
            N/A
        '''

        if addr not in self.tmp_data:
            self.tmp_data[addr] = {}

        # disassemble the packet
        seq_total = struct.unpack('H', data[0:2])[0]
        seq_num = struct.unpack('H', data[2:4])[0]
        data_tag = int.from_bytes(data[4:8], byteorder='little')
        dat = data[8:]

        # Create an entry for data_tag
        if data_tag not in self.tmp_data[addr]:
            self.tmp_data[addr][data_tag] = {}
            self.tmp_data[addr][data_tag]['packets'] = {}
            self.tmp_data[addr][data_tag]['seq_total'] = seq_total

        if (seq_total != self.tmp_data[addr][data_tag]['seq_total']
                or self.tmp_data[addr][data_tag]['seq_total'] is None):
            # If the tag existed, make sure the sequence total is equal to the
            # current, otherwise throw away any packets we've already collected
            self.tmp_data[addr][data_tag]['seq_total'] = seq_total
            self.tmp_data[addr][data_tag]['packets'] = {}

        self.tmp_data[addr][data_tag]['packets'][seq_num] = dat

        num_packets = len(self.tmp_data[addr][data_tag]['packets'])
        # print(self.tmp_data[addr][data_tag]['packets'].keys())
        # seq_total is max index of 0-index based list.
        if num_packets == seq_total + 1:
            # Reassmble the packets in order
            reassembled = bytes()
            for i in range(num_packets):
                reassembled += self.tmp_data[addr][data_tag]['packets'][i]
            if addr not in self.data_store:
                self.data_store[addr] = {}
            logging.debug("Adding reassmbled packet to data store with IP %s and tag %s",
                          addr, data_tag)
            self.data_store_lock.acquire()
            self.data_store[addr][data_tag] = reassembled
            self.data_store_lock.release()
            if self.recv_callback != None:
                # run a callback on the newly collected packets.
                self.recv_callback(addr, data_tag, reassembled)
            self.tmp_data[addr][data_tag]['packets'] = {}
            self.tmp_data[addr][data_tag]['seq_total'] = {}
