#  c1219/access/general.py
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

#  This library contains classes to facilitate retreiving complex C1219
#  tables from a target device.  Each parser expects to be passed a
#  connection object.  Right now the connection object is a
#  c1218.connection.Connection instance, but anythin implementing the basic
#  methods should work.

from struct import pack, unpack
from c1219.constants import *
from c1219.errors import C1219ParseError
from c1218.data import Write
from c1218.errors import C1218ReadTableError
from c1218.utils import find_strings

class C1219GeneralAccess(object):		# Corresponds To Decade 0x
	def __init__(self, conn):
		self.conn = conn
		general_config_table = conn.getTableData(GEN_CONFIG_TBL)
		general_mfg_table = conn.getTableData(GENERAL_MFG_ID_TBL)
		mode_status_table = conn.getTableData(ED_MODE_STATUS_TBL)
		ident_table = conn.getTableData(DEVICE_IDENT_TBL)
		
		if len(general_config_table) < 19:
			raise C1219ParseError('expected to read more data from GEN_CONFIG_TBL', GEN_CONFIG_TBL)
		if len(general_mfg_table) < 17:
			raise C1219ParseError('expected to read more data from GENERAL_MFG_ID_TBL', GENERAL_MFG_ID_TBL)
		if len(mode_status_table) < 5:
			raise C1219ParseError('expected to read more data from ED_MODE_STATUS_TBL', ED_MODE_STATUS_TBL)
		
		### Parse GEN_CONFIG_TBL ###
		self.__char_format__ = {1:'ISO/IEC 646 (7-bit)', 2:'ISO 8859/1 (Latin 1)', 3:'UTF-8', 4:'UTF-16', 5:'UTF-32'}.get((ord(general_config_table[0]) & 14) >> 1) or 'Unknown'
		self.__nameplate_type__ = {0:'Gas', 1:'Water', 2:'Electric'}.get(ord(general_config_table[7])) or 'Unknown'
		self.__id_form__ = ord(general_config_table[1]) & 32
		self.__std_version_no__ = ord(general_config_table[11])
		self.__std_revision_no__ = ord(general_config_table[12])
		
		### Parse GENERAL_MFG_ID_TBL ###
		self.__manufacturer__ = general_mfg_table[0:4].rstrip()
		self.__ed_model__ = general_mfg_table[4:12].rstrip()
		self.__hw_version_no__ = ord(general_mfg_table[12])
		self.__hw_revision_no__ = ord(general_mfg_table[13])
		self.__fw_version_no__ = ord(general_mfg_table[14])
		self.__fw_revision_no__ = ord(general_mfg_table[15])
		self.__mfg_serial_no__ = general_mfg_table[16:].strip()
		
		### Parse ED_MODE_STATUS_TBL ###
		self.__ed_mode__ = ord(mode_status_table[0])
		self.__std_status__ = unpack(conn.c1219_endian + 'H', mode_status_table[1:3])[0]
		
		### Parse DEVICE_IDENT_TBL ###
		if self.__id_form__ == 0 and len(ident_table) != 20:
			raise C1219ParseError('expected to read more data from DEVICE_IDENT_TBL', DEVICE_IDENT_TBL)
		elif self.__id_form__ != 0 and len(ident_table) != 10:
			raise C1219ParseError('expected to read more data from DEVICE_IDENT_TBL', DEVICE_IDENT_TBL)
		self.__device_id__ = ident_table.strip()
	
	def set_device_id(self, newid):
		if self.__id_form__ == 0:
			self.conn.setTableData(5, (newid + (' ' * (20 - len(newid)))))
		else:
			self.conn.setTableData(5, (newid + (' ' * (10 - len(newid)))))
		
		self.conn.send(Write(7, '\x46\x08\x1c\x03\x0b\x0c\x09\x0f\x12'))	# same with this
		data = self.conn.recv()
		if data != '\x00':
			pass
		
		try:
			ident_table = self.conn.getTableData(5)
		except C1218ReadTableError:
			return 1
		
		if self.__id_form__ == 0 and len(ident_table) != 20:
			raise C1219ParseError('expected to read more data from DEVICE_IDENT_TBL', DEVICE_IDENT_TBL)
		elif self.__id_form__ != 0 and len(ident_table) != 10:
			raise C1219ParseError('expected to read more data from DEVICE_IDENT_TBL', DEVICE_IDENT_TBL)
		if not ident_table.startswith(newid):
			return 2
		self.__device_id__ = newid
		return 0

	@property
	def char_format(self):
		return self.__char_format__
	
	@property
	def nameplate_type(self):
		return self.__nameplate_type__
	
	@property
	def id_form(self):
		return self.__id_form__
	
	@property
	def std_version_no(self):
		return self.__std_version_no__
	
	@property
	def std_revision_no(self):
		return self.__std_revision_no__
	
	@property
	def manufacturer(self):
		return self.__manufacturer__
	
	@property
	def ed_model(self):
		return self.__ed_model__
	
	@property
	def hw_version_no(self):
		return self.__hw_version_no__
	
	@property
	def hw_revision_no(self):
		return self.__hw_revision_no__
	
	@property
	def fw_version_no(self):
		return self.__fw_version_no__
	
	@property
	def fw_revision_no(self):
		return self.__fw_revision_no__
	
	@property
	def mfg_serial_no(self):
		return self.__mfg_serial_no__
	
	@property
	def ed_mode(self):
		return self.__ed_mode__
	
	@property
	def std_status(self):
		return self.__std_status__
	
	@property
	def device_id(self):
		return self.__device_id__
