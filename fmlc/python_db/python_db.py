# Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""
Framework for Multi Layer Control
PythonDB module.
"""

from json import dumps, loads
from datetime import datetime
from os import path
import csv
import sys
from time import time, gmtime, mktime
from socketserver import TCPServer
from http.server import BaseHTTPRequestHandler

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

db = {}
db_name = ''  # pylint: disable=invalid-name

def status(self):
    """Send device status as a JSON response."""
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.end_headers()

    temp = {}
    temp['dev_status'] = db['dev_status']
    temp['dev_time'] = db['dev_time']
    temp['dev_debug'] = str(db['dev_debug'])
    temp['dev_nodename'] = db['dev_nodename']
    temp['dev_error'] = db['dev_error']
    json_file = dumps(temp, sort_keys=True, separators=(',', ': ')).encode()
    self.wfile.write(json_file)

def write(self, new=True, store=True):
    """Write or update device data, and optionally store it to a CSV file."""
    if new:
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        # read new data and update dict
        length = int(self.headers['Content-Length'])
        payload = loads(self.rfile.read(length))
        db.update(payload)
    # store in csv file
    if store:
        with open(db_name, 'wb') as csv_fh:
            for key in sorted(db.keys()):
                csv.writer(csv_fh).writerow([key, db[key]])

def read(self):
    """Read the entire database and send it as a JSON response."""
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.end_headers()
    # send full db as json file
    json_file = dumps(db, sort_keys=True, separators=(',', ': ')).encode()
    self.wfile.write(json_file)

class MyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the PythonDB server."""

    def log_message(self, fmt, *args):  # pylint: disable=arguments-differ
        """Log an HTTP request."""
        if db['dev_debug']:
            sys.stderr.write(
                f"{self.address_string()} - - [{self.log_date_time_string()}] {fmt % args}\n"
            )
        else:
            pass

    # pylint: disable=invalid-name
    def do_GET(self):
        """Handle HTTP GET requests."""
        db['dev_time'] = datetime.now().strftime(DATE_FORMAT)
        if self.path == '/read':
            read(self)
        elif self.path == '/status':
            status(self)
        else:
            if db['dev_debug']:
                self.send_error(404)
            else:
                pass
        write(self, new=False, store=False)

    # pylint: disable=invalid-name
    def do_PUT(self):
        """Handle HTTP PUT requests."""
        db['dev_time'] = datetime.now().strftime(DATE_FORMAT)
        if self.path == '/write':
            write(self, store=False)
        else:
            if db['dev_debug']:
                self.send_error(404)
            else:
                pass

if __name__ == '__main__':
    # load database
    db = {}
    db['dev_nodename'] = sys.argv[1]
    db_name = db['dev_nodename'] + '.csv'
    if len(sys.argv) > 3:
        db_name = sys.argv[3] + '/' + db_name
    if path.isfile(db_name):
        with open(db_name, 'rb') as csv_file:
            for row in csv.reader(csv_file):
                try:
                    db[row[0]] = row[1]
                except (IndexError, ValueError):
                    pass
    db['dev_nodename'] = sys.argv[1]
    db['dev_port'] = sys.argv[2]
    db['dev_debug'] = False
    db['dev_status'] = "starting"
    db['dev_error'] = 'NA'
    db['timezone'] = int(int(mktime(gmtime()) - time()) / 60 / 60) * -1
    print(
        "Starting Python_db for "
        + db['dev_nodename']
        + ' on port '
        + str(db['dev_port'])
        + '...'
    )
    httpd = TCPServer(("", int(db['dev_port'])), MyHandler)
    db['dev_status'] = "ok"
    print(db['dev_status'])
    db['dev_time'] = datetime.now().strftime(DATE_FORMAT)
    httpd.serve_forever()
