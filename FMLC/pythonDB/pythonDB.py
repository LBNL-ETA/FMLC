#! /usr/bin/env python

try:
    # For Python 3.0 and later
    from socketserver import TCPServer
except ImportError:
    # Fall back to Python 2
    from SocketServer import TCPServer
    
try:
    # For Python 3.0 and later
    from http.server import BaseHTTPRequestHandler
except ImportError:
    # Fall back to Python 2
    from BaseHTTPServer import BaseHTTPRequestHandler

from json import dumps, loads
from datetime import datetime
from os import path
import csv
import sys
from time import sleep, time, gmtime, mktime

def status(self):
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
	if new:
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		#read new data and update dict
		try:
			# python 3        
			length = int(self.headers['Content-Length'])
		except:
			# python 2
			length = int(self.headers.getheader('content-length'))
		dict = loads(self.rfile.read(length))
		db.update(dict)
	#store in csv file
	if store:
		with open(db_name, 'wb') as f:
			for key in sorted(db.keys()):
				csv.writer(f).writerow([key, db[key]])
	
def read(self):
	self.send_response(200)
	self.send_header("Content-type", "text/html")
	self.end_headers()
	#print 'Header', time()
	#send full db as json file
	json_file = dumps(db, sort_keys=True, separators=(',', ': ')).encode()
	self.wfile.write(json_file)
	#print 'Payload', time()
	
class MyHandler(BaseHTTPRequestHandler):
	def log_message(self, format, *args):
		if db['dev_debug']:
			sys.stderr.write("%s - - [%s] %s\n" %
						 (self.address_string(),
						  self.log_date_time_string(),
						  format%args))
		else: pass
	def do_GET(self):
		#print 'Receive', time()
		db['dev_time'] = datetime.now().strftime(format)
		if self.path == '/read':
			read(self)
		elif self.path == '/status':
			status(self)			
		else:
			if db['dev_debug']: self.send_error(404)
			else: pass
		write(self, new=False, store=False)
	def do_PUT(self):
		db['dev_time'] = datetime.now().strftime(format)
		if self.path == '/write':
			write(self, store=False)
		else:
			if db['dev_debug']: self.send_error(404)
			else: pass

#load database
db = {}
db['dev_nodename'] = sys.argv[1]
db_name = db['dev_nodename']+'.csv'
format = '%Y-%m-%d %H:%M:%S'
if len(sys.argv) > 3: db_name = sys.argv[3]+'/'+db_name
if path.isfile(db_name):
	with open(db_name, 'rb') as f:
		for row in csv.reader(f):
			try: db[row[0]] = row[1]
			except: pass
db['dev_nodename'] = sys.argv[1]
db['dev_port'] = sys.argv[2]
db['dev_debug'] = False
db['dev_status'] = "starting"
db['dev_error'] = 'NA'
db['timezone'] = int(int(mktime(gmtime())-time())/60/60)*-1
print("Starting Python_db for "+db['dev_nodename']+' on port '+str(db['dev_port'])+'...')
httpd = TCPServer(("", int(db['dev_port'])), MyHandler)
db['dev_status'] = "ok"
print(db['dev_status'])
db['dev_time'] = datetime.now().strftime(format)
httpd.serve_forever()
