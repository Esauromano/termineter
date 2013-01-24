#  framework/modules/enum_tables.py
#  
#  Copyright 2011 Spencer J. McIntyre <SMcIntyre [at] SecureState [dot] net>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

from framework.templates import optical_module_template
from time import sleep
from c1218.data import C1218ReadRequest, C1218_RESPONSE_CODES
from c1219.data import C1219_TABLES

class Module(optical_module_template):
	def __init__(self, *args, **kwargs):
		optical_module_template.__init__(self, *args, **kwargs)
		self.version = 3
		self.author = [ 'Spencer McIntyre <smcintyre@securestate.net>' ]
		self.description = 'Enumerate Readable C12.19 Tables From The Device'
		self.detailed_description = 'This module will enumerate the readable tables on the smart meter by attempting to transfer each one.'
		self.options.addInteger('LOWER', 'table id to start reading from', default = 0)
		self.options.addInteger('UPPER', 'table id to stop reading from', default = 256)
	
	def run(self):
		conn = self.frmwk.serial_connection
		logger = self.logger
		lower_boundary = self.options['LOWER']
		upper_boundary = self.options['UPPER']
		if not self.frmwk.serial_login():
			logger.warning('meter login failed')
		
		self.frmwk.print_status('Enumerating tables, please wait...')
		tables_found = 0
		for tableid in xrange(lower_boundary, (upper_boundary + 1)):
			data = self.getTableDataEx(conn, tableid, 4)
			if data[0] == '\x00':
				self.frmwk.print_status('Found readable table, ID: ' + str(tableid) + ' Name: ' + (C1219_TABLES.get(tableid) or 'UNKNOWN'))
				tables_found += 1
			else:
				error_code = ord(data[0])
				error_type = str(C1218_RESPONSE_CODES.get(error_code) or 'UNKNOWN')
				logger.info('received error code: ' + str(error_code) + ' type: ' + error_type)
			while not conn.stop():
				sleep(0.5)
			sleep(0.25)
			while not conn.start():
				sleep(0.5)
			sleep(0.25)
			while not conn.login():
				sleep(0.5)
			sleep(0.25)
		self.frmwk.print_status('Found ' + str(tables_found) + ' table(s).')
		return

	def getTableDataEx(self, conn, tableid, octetcount = 244):
		conn.send(C1218ReadRequest(tableid, 0, octetcount))
		data = conn.recv()
		return data
