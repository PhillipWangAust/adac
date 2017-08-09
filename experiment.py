#! /usr/bin/env python3
import os
import json
import requests
import sys
import time

activator = os.path.dirname(os.path.realpath(__file__)) + '/env/bin/activate_this.py'
with open(activator) as f:
    exec(f.read(), {'__file__':activator})

import adac.util as u

username = 'pi'
data_loc = './data.txt'
hosts = ['10.0.0.1',
         '10.0.0.2',
         '10.0.0.3',
         '10.0.0.4',
         '10.0.0.5',
         '10.0.0.6',]

args = [ 'test', 'start', 'kill', 'restart', 'code', 'params', 'vector', 'gen', 'wait']

def kill_sessions():
    '''Kill the any tmux sessions running consensus server'''
    for host in hosts:
        u.run(username, host, ["tmux kill-session -t run_session"])

def start_sessions():        
    '''Start tmux sessions to run servers'''
    for host in hosts:
        u.run(username, host, ["cd ~/adac/; tmux new-session -d -s run_session 'python3 -m adac'"])
        
def restart_sessions():
    '''Restarts the tmux sessions'''
    kill_sessions()
    start_sessions()



if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("At least one argument required\n\n Try one of: {}".format(args))    
    for arg in sys.argv[1:]:
        if arg not in args:
            print("Command {} not recognized. Try one of {}".format(sys.argv[1], args))
        elif arg == 'test':
            print("Testing connection to all hosts")
            for host in hosts:
                try:
                    print('{} from {}'.format( requests.get('http://{}:9090/'.format(host)).status_code, host))
                except:
                    print("Error connecting to {}".format(host))
        elif arg == 'restart':
            print("Restarting all sessions")
            restart_sessions()
        elif arg == 'wait':
            time.sleep(5)
        elif arg == 'start':
            print("Starting all host servers")
            start_sessions()
        elif arg == 'kill':
            print("Killing all sessions")
            kill_sessions()
        elif arg == 'code':
            print("Updating code repository")
            for host in hosts:
                u.distcp(username, host, "adac/", "/home/pi/adac/")
        elif arg == 'params':
            print("Updating params files")
            for host in hosts:
                u.distcp(username, host, "params.conf", "/home/pi/adac/params.conf")
        elif arg == 'gen':
            print("generating random vector")
            vec = u.generate_vec(50)
            print(vec)
            with open('data.txt', 'w') as f:
                f.write(' '.join([str(x) for x in vec]))
                f.write('\n')
        elif arg == 'vector':
            avg_vec, vecs = (u.generate_data(username, hosts, data_loc, 50))
            with open('avg_data.txt', 'w') as f:
                f.write(str(avg_vec))
                f.write("\n")
                f.write(json.dumps(vecs))
