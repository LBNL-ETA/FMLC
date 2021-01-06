#! /usr/bin/env python

try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen
import os
import signal
from time import sleep
import subprocess as sp
import random
import requests
import json

def write_db(dict, add_db):
    try: return requests.put('http://'+add_db+'/write', data=str(json.dumps(dict, sort_keys=True, separators=(',', ': '))))
    except:	return []

def read_db(add_db):
    try: return json.loads(requests.get('http://'+add_db+'/read', verify=False).text.encode('ascii','ignore'))
    except:	return {}
    
class PythonDB_wrapper(object):
    def __init__ (self, name, mode='pythonDB', path=''):
        self.root_dir = os.path.dirname(os.path.realpath(__file__))
        self.name = name
        self.mode = mode
        self.filepath = path
        self.error = ''
        self.start_db()
        self.test_db()

    def start_db(self):
        i = 0		
        while i < 4:
            self.port = random.randint(10000,60000)
            sp.Popen('python {}.py {} {} {}'.format(self.root_dir+'/'+self.mode, self.name, str(self.port), self.filepath), shell=True)
            sleep(2)
            i += self.test_db()
        if self.test_db() != 999:
            self.port = 0
            self.error += 'Cannot find open port for '+self.name

    def test_db(self):
        try:
            response = urlopen('http://127.0.0.1:'+str(self.port)+'/status', timeout=1).read()
            if 'ok' in str(response):
                return 999
            else:
                return 1
        except:
            return 1

    def kill_db(self):
        # Works only on Linux environment
        pids = sp.Popen("ps aux | grep '"+self.name+"' | awk '{print $2, $13}'", shell=True, stdout=sp.PIPE)
        out, err = pids.communicate()
        for line in out.splitlines():
            line = line.split(b' ')
            if line[1] == self.name:
                os.kill(int(line[0]), signal.SIGKILL)

if __name__ == '__main__':
    from time import time
    name = 'Zone1_db_test'
    mode = 'pythonDB'
    testdb = PythonDB_wrapper(name, mode)
    print(testdb.port)
    time_st = time()
    print('Request', time())
    response = urlopen('http://127.0.0.1:'+str(testdb.port)+'/read', timeout=10).read()
    print('Latency:', time()-time_st)
    testdb.kill_db()
