#  c1218/connection.py
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

from binascii import hexlify, unhexlify
from struct import pack, unpack
from random import randint
from time import sleep
import logging
import serial
from c1218.data import *
from c1218.utils import find_strings, data_chksum_str
from c1218.errors import C1218NegotiateError, C1218IOError, C1218ReadTableError, C1218WriteTableError
from c1219.data import C1219ProcedureInit
from c1219.errors import C1219ProcedureError

ERROR_CODE_DICT = {1:'err (Error)', 2:'sns (Service Not Supported)', 3:'isc (Insufficient Security Clearance)', 4:'onp (Operation Not Possible)', 5:'iar (Inappropriate Action Requested)', 6:'bsy (Device Busy)', 7:'dnr (Data Not Ready)', 8:'dlk (Data Locked)', 9:'rno (Renegotiate Request)', 10:'isss (Invalid Service Sequence State)'}

class Connection:
	def __init__(self, device, c1218_settings = {}, serial_settings = None, toggle_control = True, enable_cache = True):
		"""
		This is a C12.18 driver for serial connections.  It relies on PySerial
		to communicate with an ANSI Type-2 Optical probe to communciate
		with a device (presumably a smart meter).
		
		@type device: String
		@param device: A connection string to be passed to the PySerial
		library.  If PySerial is new enough, the serial_for_url function
		will be used to allow the user to use a rfc2217 bridge.
		
		@type c1218_settings: Dictionary
		@param settings: A settings dictionary to configure the C1218 
		parameters of 'nbrpkts' and 'pktsize'  If not provided the default
		settings of 2 (nbrpkts) and 512 (pktsize) will be used.
		
		@type serial_settings: Dictionary
		@param settings: A PySerial settings dictionary to be applied to
		the serial connection instance.
		
		@type toggle_control: Boolean
		@param toggle_control: Enables or diables automatically settings
		the toggle bit in C12.18 frames.
		
		@type enable_cache: Boolean
		@param enable_cache: Cache specific, read only tables in memory,
		the first time the table is read it will be stored for retreival
		on subsequent requests.  This is enabled only for specific tables
		(currently only 0 and 1).
		"""
		self.logger = logging.getLogger('c1218.connection')
		self.loggerio = logging.getLogger('c1218.connection.io')
		self.toggle_control = toggle_control
		self.__toggle_bit__ = False
		if hasattr(serial, 'serial_for_url'):
			self.serial_h = serial.serial_for_url(device)
		else:
			self.logger.warning('serial library does not have serial_for_url functionality, it\'s not the latest version')
			self.serial_h = serial.Serial(device)
		self.logger.debug('successfully opened serial device: ' + device)
		self.device = device
		
		self.c1218_pktsize = (c1218_settings.get('pktsize') or 512)
		self.c1218_nbrpkts = (c1218_settings.get('nbrpkts') or 2)
		
		if serial_settings:
			self.logger.debug('applying pySerial settings dictionary')
			self.serial_h.parity = serial_settings['parity']
			self.serial_h.baudrate = serial_settings['baudrate']
			self.serial_h.bytesize = serial_settings['bytesize']
			self.serial_h.xonxoff = serial_settings['xonxoff']
			self.serial_h.interCharTimeout = serial_settings['interCharTimeout']
			self.serial_h.rtscts = serial_settings['rtscts']
			self.serial_h.timeout = serial_settings['timeout']
			self.serial_h.stopbits = serial_settings['stopbits']
			self.serial_h.dsrdtr = serial_settings['dsrdtr']
			self.serial_h.writeTimeout = serial_settings['writeTimeout']
		
		self.serial_h.setRTS(True)
		self.logger.debug('set RTS to True')
		self.serial_h.setDTR(False)
		self.logger.debug('set DTR to False')
		self.logged_in = False
		self.__initialized__ = False
		self.c1219_endian = '<'
		self.caching_enabled = enable_cache
		self.__cacheable_tbls__ = [0, 1]
		self.__tbl_cache__ = {}
		if enable_cache:
			self.logger.info('selective table caching has been enabled')
	
	def __repr__(self):
		return '<' + self.__class__.__name__ + ' Device: ' + self.device + ' >'
	
	def send(self, data):
		"""
		This sends a raw C12.18 frame and waits checks for an ACK response.
		In the event that a NACK is received, this function will attempt
		to resend the frame up to 3 times.
		
		@type data: either a raw string of bytes which will be placed into
		a c1218.data.C1218Packet or a c1218.data.C1218Packet instance to
		be sent
		@param: the data to be transmitted
		"""
		if not isinstance(data, C1218Packet):
			data = C1218Packet(data)
		if self.toggle_control:	# bit wise, fuck yeah
			if self.__toggle_bit__:
				data.control = chr(ord(data.control) | 0x20)
				self.__toggle_bit__ = False
			elif not self.__toggle_bit__:
				if ord(data.control) & 0x20:
					data.control = chr(ord(data.control) ^ 0x20)
				self.__toggle_bit__ = True
		elif self.toggle_control and not isinstance(data, C1218Packet):
			self.loggerio.warning('toggle bit is on but the data is not a C1218Packet instance')
		data = str(data)
		self.loggerio.debug("sending frame,  length: {0:<3} data: {1}".format(len(data), hexlify(data)))
		for pktcount in xrange(0, 3):
			self.write(data)
			response = self.serial_h.read(1)
			if response == NACK:
				self.loggerio.warning('received a NACK after writing data')
				sleep(0.10)
			elif response == '':
				self.loggerio.error('received empty response after writing data')
				sleep(0.10)
			elif response != ACK:
				self.loggerio.error('received unknown response: ' + hex(ord(response)) + ' after writing data')
			else:
				return
		self.loggerio.critical('failed 3 times to correctly send a frame')
		raise C1218IOError('failed 3 times to correctly send a frame')
	
	def recv(self):
		"""
		Receive a C1218Packet, the payload data is returned.
		"""
		payloadbuffer = ''
		tries = 3
		while tries:
			tmpbuffer = self.serial_h.read(1)
			if tmpbuffer != '\xee':
				self.loggerio.error('did not receive \\xee as the first byte of the frame')
				self.loggerio.debug('received \\x' + tmpbuffer.encode('hex') + ' instead')
				tries -= 1
				continue
			tmpbuffer += self.serial_h.read(3)
			sequence = ord(tmpbuffer[-1])
			length = self.serial_h.read(2)
			tmpbuffer += length
			length = unpack('>H', length)[0]
			payload = self.serial_h.read(length)
			tmpbuffer += payload
			chksum = self.serial_h.read(2)
			if chksum == crc_str(tmpbuffer):
				self.serial_h.write(ACK)
				data = tmpbuffer + chksum
				self.loggerio.debug("received frame, length: {0:<3} data: {1}".format(len(data), hexlify(data)))
				payloadbuffer += payload
				if sequence == 0:
					return payloadbuffer
				else:
					tries = 3
			else:
				self.serial_h.write(NACK)
				self.loggerio.warning('crc does not match on received frame')
				tries -= 1
		self.loggerio.critical('failed 3 times to correctly receive a frame')
		raise C1218IOError('failed 3 times to correctly receive a frame')
	
	def write(self, data):
		"""
		Write raw data to the serial connection. The CRC must already be
		included at the end. This function is not meant to be called
		directly.
		
		@type data: String
		@param data: The raw data to write to the serial connection.
		"""
		return self.serial_h.write(data)
	
	def read(self, size):
		"""
		Read raw data from the serial connection. This function is not
		meant to be called directly.
		
		@type size: Integer
		@param size: The number of bytes to read from the serial connection.
		"""
		data = self.serial_h.read(size)
		self.logger.debug('read data, length: ' + str(len(data)) + ' data: ' + hexlify(data))
		self.serial_h.write(ACK)
		return data
		
	def close(self):
		"""
		Send a terminate request and then disconnect from the serial device.
		"""
		if self.__initialized__:
			self.stop()
		self.logged_in = False
		return self.serial_h.close()
		
###===###===### Functions Below This Are Non-Critical ###===###===###
###===###===### Convenience Functions                 ###===###===###

	def flushTableCache(self):
		self.logger.info('flushing all cached tables')
		self.__tbl_cache__ = {}

	def setTableCachePolicy(self, cache_policy):
		if self.caching_enabled == cache_policy:
			return
		self.caching_enabled = cache_policy
		if cache_policy:
			self.logger.info('selective table caching has been enabled')
		else:
			self.flushTableCache()
			self.logger.info('selective table caching has been disabled')
		return

	def start(self):
		"""
		Send an identity request and then a negotiation request.
		"""
		self.send(C1218IdentRequest())	# identity
		data = self.recv()
		if data[0] != '\x00':
			self.logger.error('received incorrect response to identification service request')
			return False

		self.__initialized__ = True
		self.send(C1218NegotiateRequest(self.c1218_pktsize, self.c1218_nbrpkts, baudrate = 9600))
		data = self.recv()
		if data[0] != '\x00':
			self.logger.error('received incorrect response to negotiate service request')
			self.stop()
			raise C1218NegotiateError('received incorrect response to negotiate service request', ord(data[0]))
		return True
	
	def stop(self):
		"""
		Send a terminate request.
		"""
		if self.__initialized__ == True:
			self.send(C1218TerminateRequest())
			data = self.recv()
			if data == '\x00':
				self.__initialized__ = False
				self.__toggle_bit__ = False
				return True
		return False
	
	def login(self, username = '0000', userid = 0, password = None):
		"""
		Log into the connected device.
		
		@type username: String (len(username) <= 10)
		@param username: the username to log in with
		
		@type userid: Integer (0x0000 <= userid <= 0xffff)
		@param userid: the userid to log in with
		
		@type password: String (len(password) <= 20)
		@param password: password to log in with
		"""
		if password != None and len(password) > 20:
			self.logger.error('password longer than 20 characters received')
			raise Exception('password longer than 20 characters, login failed')
		
		self.send(C1218LogonRequest(username, userid))
		data = self.recv()
		if data != '\x00':
			self.logger.error('login failed, user name and user id rejected')
			return False
		
		if password != None:
			self.send(C1218SecurityRequest(password))
			data = self.recv()
			if data != '\x00':
				self.logger.error('login failed, password rejected')
				return False
		
		self.logged_in = True
		return True
	
	def logoff(self):
		"""
		Send a logoff request.
		"""
		self.send(C1218LogoffRequest())
		data = self.recv()
		if data == '\x00':
			self.__initialized__ = False
			return True
		return False
	
	def getTableData(self, tableid, octetcount = None, offset = None):
		"""
		Read data from a table. If successful, all of the data from the 
		requested table will be returned.
		
		@type tableid: Integer (0x0000 <= tableid <= 0xffff)
		@param tableid: The table number to read from
		
		@type octetcount: Integer (0x0000 <= tableid <= 0xffff)
		@param octetcount: Limit the amount of data read, only works if 
		the meter supports this type of reading.
		
		@type offset: Integer (0x000000 <= octetcount <= 0xffffff)
		@param offset: The offset at which to start to read the data from.		
		"""
		if self.caching_enabled and tableid in self.__cacheable_tbls__ and tableid in self.__tbl_cache__.keys():
			self.logger.info('returning cached table #' + str(tableid))
			return self.__tbl_cache__[tableid]
		self.send(C1218ReadRequest(tableid, offset, octetcount))
		data = self.recv()
		status = data[0]
		if status != '\x00':
			status = ord(status)
			details = (ERROR_CODE_DICT.get(status) or 'unknown response code')
			self.logger.error('could not read table id: ' + str(tableid) + ', error: ' + details)
			raise C1218ReadTableError('could not read table id: ' + str(tableid) + ', error: ' + details, status)
		if len(data) < 4:
			if len(data) == 0:
				self.logger.error('could not read table id: ' + str(tableid) + ', error: no data was returned')
				raise C1218ReadTableError('could not read table id: ' + str(tableid) + ', error: no data was returned')
			self.logger.error('could not read table id: ' + str(tableid) + ', error: data read was corrupt, invalid length (less than 4)')
			raise C1218ReadTableError('could not read table id: ' + str(tableid) + ', error: data read was corrupt, invalid length (less than 4)')
		length = unpack('>H', data[1:3])[0]
		chksum = data[-1]
		data = data[3:-1]
		if len(data) != length:
			self.logger.error('could not read table id: ' + str(tableid) + ', error: data read was corrupt, invalid length')
			raise C1218ReadTableError('could not read table id: ' + str(tableid) + ', error: data read was corrupt, invalid length')
		if data_chksum_str(data) != chksum:
			self.logger.error('could not read table id: ' + str(tableid) + ', error: data read was corrupt, invalid check sum')
			raise C1218ReadTableError('could not read table id: ' + str(tableid) + ', error: data read was corrupt, invalid checksum')
		if self.caching_enabled and tableid in self.__cacheable_tbls__ and not tableid in self.__tbl_cache__.keys():
			self.logger.info('cacheing table #' + str(tableid))
			self.__tbl_cache__[tableid] = data
		return data

	def setTableData(self, tableid, data, offset = None):
		"""
		Write data to a table.
		
		@type tableid: Integer (0x0000 <= tableid <= 0xffff)
		@param tableid: The table number to write to
		
		@type data: String
		@param data: The data to write into the table.
		
		@type offset: Integer (0x000000 <= octetcount <= 0xffffff)
		@param offset: The offset at which to start to write the data.	
		"""
		self.send(C1218WriteRequest(tableid, data, offset))
		data = self.recv()
		if data[0] != '\x00':
			status = ord(data[0])
			details = (ERROR_CODE_DICT.get(status) or 'unknown response code')
			self.logger.error('could not write data to the table, error: ' + details)
			raise C1218WriteTableError('could not write data to the table, error: ' + details, status)
		return None

	def runProcedure(self, process_number, std_vs_mfg, params = ''):
		"""
		Initiate a C1219 procedure, the request is written to table 7 and
		the response is read from table 8.
		
		@type process_number: Integer (0 <= process_number <= 2047)
		@param process_number: The numeric procedure identifier.
		
		@type std_vs_mfg: Boolean
		@param std_vs_mfg: Whether the procedure is manufacturer specified
		or not.  True is manufacturer specified.
		
		@type params: String
		@param params: The parameters to pass to the procedure initiation
		request.
		"""
		seqnum = randint(2, 254)
		self.logger.info('starting procedure: ' + str(process_number) + ' (' + hex(process_number) + ') sequence number: ' + str(seqnum) + ' (' + hex(seqnum) + ')')
		procedure_request = str(C1219ProcedureInit(self.c1219_endian, process_number, std_vs_mfg, 0, seqnum, params))
		self.setTableData(7, procedure_request)
		
		response = self.getTableData(8)
		if response[:3] == procedure_request[:3]:
			return ord(response[3]), response[4:]
		else:
			self.logger.error('invalid response from procedure response table (table #8)')
			raise C1219ProcedureError('invalid response from procedure response table (table #8)')
