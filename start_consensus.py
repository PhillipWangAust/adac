import os
import sys
from multiprocessing import Process

if __name__ == "__main__":
    pid = os.fork()
    if pid != 0:
        os._exit(0)
    f = open('/dev/null', 'w')
    sys.stdout = f
    sys.stderr = f
    file_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(file_dir)
    activator = "env/bin/activate_this.py"
    with open(activator) as f:
        exec(f.read(), {'__file__': activator})
    from adac import runner
    p = Process(target=runner.start)
    p.start()
