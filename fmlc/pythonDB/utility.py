#! /usr/bin/env python

'''
This module is part of the FMLC package.
https://github.com/LBNL-ETA/FMLC
'''

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
import traceback

SLEEP_TIME = 2   # seconds
MAX_ATTEMPTS = 4 # max attempts to start database

def write_db(dict, add_db):
    try:
        return requests.put('http://'+add_db+'/write', data=str(json.dumps(dict, sort_keys=True, separators=(',', ': '))))
    except Exception as e:
        return f'ERROR: {e}.\n\n{traceback.format_exc()}'

def read_db(add_db):
    try:
        return json.loads(requests.get('http://'+add_db+'/read', verify=False).text.encode('ascii','ignore'))
    except Exception as e:
        return f'ERROR: {e}'
    
class PythonDB_wrapper(object):
    def __init__ (self, name, mode='pythonDB', path=''):
        self.root_dir = os.path.dirname(os.path.realpath(__file__))
        self.name = name
        self.mode = mode
        self.filepath = path
        self.error = ''
        self.start_db()

    def start_db(self):
        # Determine Python command
        for pcmd in ['python', 'python3', 'python2']:
            try:
                sp.call([pcmd, '-c', 'exit()'])
                break
            except:
                pass
        i = 0		
        while i < MAX_ATTEMPTS:
            self.port = random.randint(10000, 60000)
            sp.Popen('{} {}.py {} {} {}'.format(pcmd, self.root_dir+'/'+self.mode, self.name, str(self.port), self.filepath), shell=True)
            sleep(SLEEP_TIME)
            i += self.test_db()
        sleep(SLEEP_TIME/2)
        if self.test_db() != 999:
            self.port = 0
            self.error += 'Cannot find open port for '+self.name

    def test_db(self):
        try:
            response = urlopen('http://127.0.0.1:'+str(self.port)+'/status', timeout=1).read()
            response = json.loads(response)
            if response['dev_nodename'] == self.name:
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
            if line[1].decode() == self.name:
                sp.call(f'echo "Closing {self.mode} for {self.name}."', shell=True)
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
