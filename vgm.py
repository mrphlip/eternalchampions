import struct
from dataclasses import dataclass

# https://vgmrips.net/wiki/VGM_Specification

@dataclass
class Header:
	ident: bytes
	eof: int
	version: int
	sn76489: int
	ym2413: int
	gd3: int
	samplelen: int
	loopofs: int
	loopsample: int
	rate: int
	snfb: int
	snw: int
	sf: int
	ym2612: int
	ym2151: int
	vgmofs: int
	pcm: int
	spcm: int

@dataclass
class GD3:
	track_english: str
	track_orig: str
	game_english: str
	game_orig: str
	system_english: str
	system_orig: str
	artist_english: str
	artist_orig: str
	date: str
	converter: str
	notes: str

@dataclass
class YMEvent:
	page: int
	reg: int
	value: int

@dataclass
class PSGEvent:
	page: int
	op: int

@dataclass
class Frame:
	num: int
	ym: list[YMEvent]
	psg: list[PSGEvent]

def read_header(fp):
	ofs = fp.tell()
	hdr = Header(*struct.unpack("<4sLLLLLLLLLHBBLLLLL", fp.read(0x40)))
	assert hdr.ident == b"Vgm "
	assert hdr.version == 0x150
	assert hdr.ym2612 == 7670453
	# for some reason offsets are relative to the location of _that field_... make them releative to the whole file
	hdr.eof += 0x04 + ofs
	if hdr.gd3:
		hdr.gd3	+= 0x14 + ofs
	if hdr.loopofs:
		hdr.loopofs += 0x1C + ofs
	return hdr

def read_gd3(fp):
	hdr, ver, length = struct.unpack("<4sLL", fp.read(12))
	assert hdr == b"Gd3 "
	assert ver == 0x100
	dat = fp.read(length).decode("utf-16-le")
	dat = dat.split("\0")
	assert len(dat) == 12 and not dat[-1]
	return GD3(*dat[:-1])

def read_commands(fp, hdr):
	framenum = 0
	cur_frame = Frame(0, [], [])
	frames = [cur_frame]
	have_looped = False

	def newframe(delay):
		nonlocal framenum, cur_frame, frames
		framenum += delay
		cur_frame = Frame(framenum, [], [])
		frames.append(cur_frame)

	while True:
		if not have_looped and hdr.loopofs and hdr.loopofs <= fp.tell():
			assert framenum == hdr.samplelen - hdr.loopsample
			have_looped = True
		op = ord(fp.read(1))
		match op:
			case 0x52 | 0x53: # YM2612 FM data
				cur_frame.ym.append(YMEvent(op & 1, *fp.read(2)))
			case 0x4F | 0x50: # SN76489 PSG data
				cur_frame.psg.append(PSGEvent(op & 1, *fp.read(1)))
			case 0x70 | 0x71 | 0x72 | 0x73 | 0x74 | 0x75 | 0x76 | 0x77 | 0x78 | 0x79 | 0x7A | 0x7B | 0x7C | 0x7D | 0x7E | 0x7F: # short delay
				newframe(op - 0x6F)
			case 0x61: # long delay
				newframe(struct.unpack("<H", fp.read(2))[0])
			case 0x62: # delay one 60Hz frame
				newframe(735)
			case 0x63: # delay one 50Hz frame
				newframe(882)
			case 0x66: # EOF
				break
			case _:
				raise ValueError(f"Unhandled opcode {op:02X}")
	assert framenum == hdr.samplelen
	return frames

def read_file(fp):
	ofs = fp.tell()
	hdr = read_header(fp)
	if hdr.gd3:
		fp.seek(hdr.gd3)
		gd3 = read_gd3(fp)
	else:
		gd3 = None
	fp.seek(ofs + 0x40)
	return hdr, gd3, read_commands(fp, hdr)
