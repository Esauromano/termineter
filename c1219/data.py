#  c1219/data.py
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

import time
from struct import pack, unpack
from c1219.constants import *

def formatLTime(endianess, tm_format, data):
	if tm_format == 0:
		return ''
	elif tm_format == 1 or tm_format == 2:	# I can't find solid documentation on the BCD data-type
		y = ord(data[0])
		year = '????'
		if 90 <= y <= 99:
			year = '19' + str(y)
		elif 0 <= y <= 9:
			year = '200' + str(y)
		elif 10 <= y <= 89:
			year = '20' + str(y)
		month = ord(data[1])
		day = ord(data[2])
		hour = ord(data[3])
		minute = ord(data[4])
		second = ord(data[5])
	elif tm_format == 3 or tm_format == 4:
		if tm_format == 3:
			u_time = float(unpack(endianess + 'I', data[0:4])[0])
			second = float(data[4])
			final_time = time.gmtime((u_time * 60) + second)
		elif tm_format == 4:
			final_time = time.gmtime(float(unpack(endianess + 'I', data[0:4])[0]))
		year = str(final_time.tm_year)
		month = str(final_time.tm_mon)
		day = str(final_time.tm_mday)
		hour = str(final_time.tm_hour)
		minute = str(final_time.tm_min)
		second = str(final_time.tm_sec)
	
	return "{} {} {} {}:{}:{}".format((MONTHS.get(month) or 'UNKNOWN'), day, year, hour, minute, second)

def getHistoryEntryRcd(endianess, hist_date_time_flag, tm_format, event_number_flag, hist_seq_nbr_flag, data):
	rcd = {}
	if hist_date_time_flag:
		tmstmp = formatLTime(endianess, tm_format, data[0:LTIME_LENGTH.get(tm_format)])
		if tmstmp:
			rcd['Time'] = tmstmp
		data = data[LTIME_LENGTH.get(tm_format):]
	if event_number_flag:
		rcd['Event Number'] = unpack(endianess + 'H', data[:2])[0]
		data = data[2:]
	if hist_seq_nbr_flag:
		rcd['History Sequence Number'] = unpack(endianess + 'H', data[:2])[0]
		data = data[2:]
	rcd['User ID'] = unpack(endianess + 'H', data[:2])[0]
	rcd['Procedure Number'], rcd['Std vs Mfg'] = getTableIDBBFLD(endianess, data[2:4])
	rcd['Arguments'] = data[4:]
	return rcd

def getTableIDBBFLD(endianess, data):
	bfld = unpack(endianess + 'H', data[:2])[0]
	proc_nbr = bfld & 2047
	std_vs_mfg = bool(bfld & 2048)
	return (proc_nbr, std_vs_mfg)

def getTableIDCBFLD(endianess, data):
	bfld = unpack(endianess + 'H', data[:2])[0]
	proc_nbr = bfld & 2047
	std_vs_mfg = bool(bfld & 2048)
	proc_flag = bool(bfld & 4096)
	flag1 = bool(bfld & 8192)
	flag2 = bool(bfld & 16384)
	flag3 = bool(bfld & 32768)
	return (proc_nbr, std_vs_mfg, proc_flag, flag1, flag2, flag3)
	

class c1219ProcedureInit:
	def __init__(self, endianess, table_proc_nbr, std_vs_mfg, selector, seqnum, params = ''):
		mfg_defined = 0
		if std_vs_mfg:
			mfg_defined = 1
		mfg_defined = mfg_defined << 11
		selector = selector << 4
		
		self.table_idb_bfld = pack(endianess + 'H', (table_proc_nbr | mfg_defined | selector))
		self.seqnum = chr(seqnum)
		self.params = params
	
	def __str__(self):
		return self.table_idb_bfld + self.seqnum + self.params


	
