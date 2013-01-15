#  framework/modules/run_procedure.py
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
from binascii import unhexlify
from c1219.constants import C1219_PROCEDURE_NAMES, C1219_PROC_RESULT_CODES

class Module(optical_module_template):
	def __init__(self, *args, **kwargs):
		optical_module_template.__init__(self, *args, **kwargs)
		self.version = 2
		self.author = [ 'Spencer McIntyre <smcintyre@securestate.net>' ]
		self.description = 'Initiate A Custom Procedure'
		self.detailed_description = 'This module executes a user defined procedure and returns the response. This is achieved by writing to the Procedure Initiate Table (#7) and then reading the result from the Procedure Response Table (#8).'
		self.options.addInteger('PROCNBR', 'procedure number to execute')
		self.options.addString('PARAMS', 'parameters to pass to the executed procedure', default = '')
		self.options.addBoolean('USEHEX', 'specifies that the \'PARAMS\' option is represented in hex', default = True)
		self.advanced_options.addBoolean('STDVSMFG', 'if true, specifies that this procedure is defined by the manufacturer', default = False)
	
	def run(self):
		conn = self.frmwk.serial_connection
		if not self.frmwk.serial_login():	# don't alert on failed logins
			self.logger.warning('meter login failed')
			self.frmwk.print_error('Meter login failed, procedure may fail')
		
		data = self.options['PARAMS']
		if self.options['USEHEX']:
			data = unhexlify(data)
		
		self.frmwk.print_status('Initiating procedure ' + (C1219_PROCEDURE_NAMES.get(self.options['PROCNBR']) or '#' + str(self.options['PROCNBR'])))
		
		errCode, data = conn.runProcedure(self.options['PROCNBR'], self.advanced_options['STDVSMFG'], data)
		conn.stop()
		
		self.frmwk.print_status('Finished running procedure #' + str(self.options['PROCNBR']))
		self.frmwk.print_status('Received respose from procedure: ' + (C1219_PROC_RESULT_CODES.get(errCode) or 'UNKNOWN'))
		if len(data):
			self.frmwk.print_status('Received data output from procedure: ')
			self.frmwk.print_hexdump(data)
		return
