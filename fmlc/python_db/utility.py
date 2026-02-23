# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
PythonDB utility module.
"""

import json
import os
import random
import signal
import subprocess as sp
import traceback
import socket
import urllib.error
from time import sleep, time
from urllib.request import urlopen

import requests

SLEEP_TIME = 2   # seconds
MAX_ATTEMPTS = 4 # max attempts to start database
TIMEOUT = 5      # database timeout
MODE_MAP = {'pythonDB': 'python_db'}

def write_db(data, add_db):
    '''write to db'''
    try:
        data = json.dumps(data, sort_keys=True, separators=(',', ': '))
        return requests.put('http://' + add_db + '/write',
                            data=str(data),
                            timeout=TIMEOUT)
    except (TypeError, requests.exceptions.RequestException) as e:
        return f'ERROR: {e}.\n\n{traceback.format_exc()}'

def read_db(add_db):
    '''read from db'''
    try:
        resp = requests.get('http://' + add_db + '/read',
                            verify=False,
                            timeout=TIMEOUT)
        return json.loads(resp.text.encode('ascii', 'ignore'))
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        return f'ERROR: {e}'

class PythonDBWrapper:
    ''' The Python DB main class.'''

    def __init__ (self, name, mode='pythonDB', path=''):
        '''initialize'''
        self.root_dir = os.path.dirname(os.path.realpath(__file__))
        self.name = name
        self.mode = mode
        self.filepath = path
        self.error = ''
        self.start_db()

    def start_db(self):
        '''start python db'''
        # Determine Python command
        for pcmd in ['python', 'python3', 'python2']:
            try:
                sp.call([pcmd, '-c', 'exit()'])
                break
            except FileNotFoundError:
                pass
        i = 0
        while i < MAX_ATTEMPTS:
            self.port = random.randint(10000, 60000)
            db_path = f'{self.root_dir}/{MODE_MAP[self.mode]}.py'
            cmd = f'{pcmd} {db_path} {self.name} {self.port} {self.filepath}'
            sp.Popen(cmd, shell=True) # pylint: disable=consider-using-with
            sleep(SLEEP_TIME)
            i += self.test_db()
        sleep(SLEEP_TIME / 2)
        if self.test_db() != 999:
            self.port = 0
            self.error += 'Cannot find open port for ' + self.name

    def test_db(self):
        '''test if python db reachable'''
        try:
            link = f'http://127.0.0.1:{self.port}/status'
            with urlopen(link, timeout=1) as resp:
                data = resp.read()
            status = json.loads(data)
            if status['dev_nodename'] == self.name:
                return 999
            return 1
        except (urllib.error.URLError, socket.timeout, json.JSONDecodeError):
            return 1

    def kill_db(self):
        '''shutdown python db'''
        # Works only on Linux environment
        cmd = f"ps aux | grep '{self.name}'"
        cmd += " | awk '{print $2, $13}'"
        with sp.Popen(cmd, shell=True, stdout=sp.PIPE) as pids:
            out, _ = pids.communicate()
        for line in out.splitlines():
            parts = line.split(b' ')
            if parts[1].decode() == self.name:
                sp.call(
                    f'echo "Closing {self.mode} for {self.name}."',
                    shell=True,
                )
                os.kill(int(parts[0]), signal.SIGKILL)

if __name__ == '__main__':
    NAME = 'Zone1_db_test'
    MODE = 'pythonDB'
    testdb = PythonDBWrapper(NAME, MODE)
    print(testdb.port)
    time_st = time()
    print('Request', time())
    with urlopen(f'http://127.0.0.1:{testdb.port}/read', timeout=10) as read_resp:
        _ = read_resp.read()
    print('Latency:', time() - time_st)
    testdb.kill_db()
