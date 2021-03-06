'''Run a set of commands across many computer in parallel

Note: Passworldess SSH is required from the machine that you're running on

'''
import sys
import subprocess
import random
USER = 'pi'
HOSTS = ['10.0.0.1',
         '10.0.0.2',
         '10.0.0.3',
         '10.0.0.4',
         '10.0.0.5',
         '10.0.0.6']

def generate_vec(vec_size, seed=None):
    random.seed(seed)
    v = []
    for i in range(vec_size):
        v.append(random.randint(0, 250))
    return v

def generate_data(user, machines, remote_loc, vec_size, seed=None):
    '''Generate and distribute random vectors to use for consensus machines is the list of host
    machines

    Returns a tuple of the average vector and a dictionary of all the vectors generated
    (avg_vec, dict)
    '''
    random.seed(seed)
    vectors = {} # Dict
    avg_vec = [0] * vec_size

    # generate the random vectors
    for host in machines:
        vectors[host] = generate_vec(vec_size, seed)
        avg_vec = [avg_vec[x] + vectors[host][x] for x in range(vectors[host])]
        run(user, host, ['echo "{}" > {}'.format(' '.join([str(x) for x in vectors[host]]), remote_loc)])

    avg_vec = [x/len(machines) for x in avg_vec]
    return (avg_vec, vectors)

def run(user, host, cmds):
    '''Run a command on a remot machine via SSH'''
    for cmd in cmds:
        args = ['ssh', '{}@{}'.format(user, host)]
        args.append(cmd)
        print(args)
        out = subprocess.Popen(args, shell=False,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(out.stdout.readlines())

def distcp(user, host, filename, remote_location):
    '''Uses SCP to copy a file to a remote machine'''
    args = ['scp', '-r', filename, '{}@{}:{}'.format(user, host, remote_location)]
    print(' '.join(args))
    out = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, err = out.communicate()
    print('Out: {}'.format(stdout))
    print('Err: {}'.format(err))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        CMDARGS = sys.argv[1:]
    if CMDARGS[0] == 'copy':
        print('Running distcp')
        for addr in HOSTS:
            distcp(USER, addr, CMDARGS[1], CMDARGS[2])
    else:
        for addr in HOSTS:
            run(USER, addr, CMDARGS)
