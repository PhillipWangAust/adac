import logging
import psutil

class psLogger(object):

    def __init__(self, name, delimiter='|'):
        self.logger = logging.getLogger(name)
        self.set_delimiter(str(delimiter))
        self.proc = psutil.Process()

    def set_delimiter(self, delim):
        self.delimiter = ' ' + delim + ' '

    def log_cpu_time(self, *args):
        '''Log process CPU time'''
        self.log(psutil.cpu_times(), *args)
        self.log(self.proc.cpu_times(), *args)

    def log_mem(self, *args):
        '''Log memory statistics for current process'''
        self.log(self.proc.memory_full_info(), *args)

    def log_network(self, *args):
        '''Log network activity'''
        self.log(psutil.net_io_counters(), *args)

    def log(self, info_str, *args):
        '''Log the info'''
        inf = '{}{}{}'.format(self.delimiter.join(list(args)), self.delimiter, info_str)
        self.logger.info('%s', inf)
