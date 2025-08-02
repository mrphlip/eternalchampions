from enum import Enum
from io import BytesIO
import struct
import sys
from typing import Iterable, NamedTuple, Optional, Protocol, TextIO
import warnings

# References
# https://www.music.mcgill.ca/~ich/classes/mumt306/StandardMIDIfileformat.html
# http://www.philrees.co.uk/nrpnq.htm

class _Constants:
	_revmapping: dict[int, str] = {}

	@classmethod
	def repr(cls, val: int) -> str:
		if not cls._revmapping:
			cls._revmapping = {v: k for k, v in vars(cls).items() if not k.startswith("_") and k not in ("repr") and isinstance(v, int)}
		if val in cls._revmapping:
			return f"{cls.__name__}.{cls._revmapping[val]}"
		else:
			return str(val)


class NoteOff(NamedTuple):
	channel: int
	key: int
	velocity: int

	def __repr__(self):
		return f"NoteOff({self.channel}, {self.key}, {self.velocity})"

class NoteOn(NamedTuple):
	channel: int
	key: int
	velocity: int

	def __repr__(self):
		return f"NoteOn({self.channel}, {self.key}, {self.velocity})"

class NoteAftertouch(NamedTuple):
	channel: int
	key: int
	pressure: int

	def __repr__(self):
		return f"NoteAftertouch({self.channel}, {self.key}, {self.pressure})"

class Control(NamedTuple):
	channel: int
	control: int
	value: int

	def __repr__(self):
		return f"Control({self.channel}, {Controls.repr(self.control)}, {self.value})"

class Controls(_Constants):
	# GM controls
	MODULATION = 1
	VOLUME = 7
	PAN = 10
	SUSTAIN = 64
	RESET_ALL = 121
	LOCAL_CONTROL = 122
	ALL_NOTES_OFF = 123
	OMNI_MODE_OFF = 124
	OMNI_MODE_ON = 125
	MONO_MODE = 126
	POLY_MODE = 127

	# Special param messages
	REGISTERED_PARAM_MSB = 101
	REGISTERED_PARAM_LSB = 100
	UNREGISTERED_PARAM_MSB = 99
	UNREGISTERED_PARAM_LSB = 98
	PARAM_VALUE_MSB = 6
	PARAM_VALUE_LSB = 38

class Params(_Constants):
	PARAM_PITCH_BEND_SENSITIVITY = 0  # param_value_high is in semitones, param_value_low is in cents (or 1/128ths)
	PARAM_FINE_TUNING = 1  # param_value is 14-bit number in range from -1 to 1 semitone, 0x4000 = no change
	PARAM_COARSE_TUNING = 2  # param_value_high is tuning in semitones, low unused
	PARAM_TUNING_PROGRAM = 3
	PARAM_TUNING_BANK = 4

def param_change(channel: int, param_num: int, param_value_high: int, param_value_low: Optional[int] = None, registered: bool = True, terminal: bool = True) -> list[Control]:
	res = []
	res.append(Control(channel, Controls.REGISTERED_PARAM_MSB if registered else Controls.UNREGISTERED_PARAM_MSB, (param_num & 0x3F80) >> 7))
	res.append(Control(channel, Controls.REGISTERED_PARAM_LSB if registered else Controls.UNREGISTERED_PARAM_LSB, param_num & 0x007F))
	res.append(Control(channel, Controls.PARAM_VALUE_MSB, param_value_high))
	if param_value_low is not None:
		res.append(Control(channel, Controls.PARAM_VALUE_LSB, param_value_low))
	if terminal:
		res.append(Control(channel, Controls.REGISTERED_PARAM_MSB if registered else Controls.UNREGISTERED_PARAM_MSB, 0x7F))
		res.append(Control(channel, Controls.REGISTERED_PARAM_LSB if registered else Controls.UNREGISTERED_PARAM_LSB, 0x7F))
	return res

class Program(NamedTuple):
	channel: int
	program: int

	def __repr__(self):
		return f"Program({self.channel}, {self.program})"

class Aftertouch(NamedTuple):
	channel: int
	pressure: int

	def __repr__(self):
		return f"Aftertouch({self.channel}, {self.pressure})"

class Wheel(NamedTuple):
	channel: int
	wheel: int

	def __repr__(self):
		return f"Wheel({self.channel}, {self.wheel})"

class SysEx(NamedTuple):
	device_id: int
	message: bytes
	terminal: bool

	def __repr__(self):
		return f"SysEx({self.device_id}, {self.message!r}, {self.terminal})"

class MetaEvent(NamedTuple):
	event: int
	data: bytes

	def __repr__(self):
		return f"MetaEvent({Events.repr(self.event)}, {self.data!r})"

class Events(_Constants):
	SEQUENCE_NUMBER = 0  # data: two bytes, 14-bit int
	TEXT_EVENT = 1
	COPYRIGHT = 2
	TRACK_NAME = 3
	INSTRUMENT_NAME = 4
	LYRIC = 5
	MARKER = 6
	CUE_POINT = 7
	MIDI_CHANNEL = 0x20  # data: one byte, 0-15
	END_OF_TRACK = 0x2F  # no data
	TEMPO = 0x51  # data: three bytes, 24-bit int big endian, in usec per quarter note
	SMTPE_STAMP = 0x54  # data: five bytes, [hour, minute, second, frame, centi-frame]
	TIME_SIG = 0x58  # data: four bytes, [numerator, log_2(denominator), ticks per metronome, something weird just put 8]
	KEY_SIG = 0x59  # data two bytes [num sharps, major=0 minor=1] - first value is negative for flats (two's complement & 0x7F)
	SEQUENCER_SPECIFIC = 0x7F  # data: byte device id + data, or '\x0' + two byte device id + data

MidiEvent = NoteOff | NoteOn | NoteAftertouch | Control | Program | Aftertouch | Wheel | SysEx | MetaEvent

class TimedMidiEvent(NamedTuple):
	time: int
	event: MidiEvent

MidiTrack = list[TimedMidiEvent]

class MidiFileType(Enum):
	SINGLETRACK = 0
	MULTITRACK = 1
	MULTIPATTERN = 2

class SMPTE(NamedTuple):
	fps: int
	tpf: int

class MidiFile(NamedTuple):
	type: MidiFileType
	rate: int | SMPTE  # int = ticks per quarter note, SMPTE = ticks per frame, frames per second
	tracks: list[MidiTrack]

	def pprint(self, fp: Optional[TextIO] = None, indent: int = 0) -> None:
		if fp is None:
			fp = sys.stdout
		indentstr = "  " * indent
		print(f"{indentstr}MidiFile(", file=fp)
		print(f"{indentstr}  MidiFileType.{self.type.name},", file=fp)
		if isinstance(self.rate, int):
			print(f"{indentstr}  {self.rate},", file=fp)
		elif isinstance(self.rate, SMPTE):
			print(f"{indentstr}  SMPTE({self.rate.fps}, {self.rate.tpf}),", file=fp)
		print(f"{indentstr}  [", file=fp)
		for track in self.tracks:
			print(f"{indentstr}    [", file=fp)
			for event in track:
				print(f"{indentstr}      TimedMidiEvent({event.time}, {event.event}),", file=fp)
			print(f"{indentstr}    ],", file=fp)
		print(f"{indentstr}  ],", file=fp)
		print(f"{indentstr})", file=fp)


class BinaryReader(Protocol):
	def read(self, size: int = -1) -> bytes:
		...
	def seek(self, offset: int, whence: int = 0) -> None:
		...
	def tell(self) -> int:
		...

class BinaryWriter(Protocol):
	def write(self, data: bytes) -> None:
		...
	def seek(self, offset: int, whence: int = 0) -> None:
		...
	def tell(self) -> int:
		...

def _read(fp: BinaryReader, n: int = -1) -> bytes:
	res = []
	if n < 0:
		while True:
			a = fp.read()
			if not a:
				break
			res.append(a)
	else:
		while n > 0:
			a = fp.read(n)
			if not a:
				raise EOFError()
			res.append(a)
			n -= len(a)
	return b"".join(res)

class _ChunkReader:
	def __init__(self, fp: BinaryReader, length: int):
		self.fp = fp
		self.startpos = fp.tell()
		self.endpos = self.startpos + length
		self.remaining = length

	def __enter__(self):
		return self
	def __exit__(self, exc_type, exc_value, exc_tb):
		self.seek(0, 2)

	def read(self, n: int = -1) -> bytes:
		if n < 0 or n > self.remaining:
			n = self.remaining
		res = self.fp.read(n)
		self.remaining -= len(res)
		return res
	def seek(self, offset: int, whence: int = 0) -> None:
		match whence:
			case 0:
				target = self.startpos + offset
			case 1:
				target = self.fp.tell() + offset
			case 2:
				target = self.endpos + offset
		if target < self.startpos:
			target = self.startpos
		if target > self.endpos:
			target = self.endpos
		self.fp.seek(target)
		self.remaining = self.endpos - target
	def tell(self) -> int:
		return self.fp.tell() - self.startpos

def _get_chunk(fp: BinaryReader, littleend: bool = False) -> tuple[bytes, int, _ChunkReader]:
	chunk_hdr = fp.read(4)
	chunk_len, = struct.unpack("<L" if littleend else ">L", fp.read(4))
	return chunk_hdr, chunk_len, _ChunkReader(fp, chunk_len)

CHUNK_HEADER = b"MThd"
CHUNK_TRACK = b"MTrk"

def parse_midi_file(fp: BinaryReader) -> MidiFile:
	chunk_hdr, chunk_len, chunk_fp = _get_chunk(fp)
	if chunk_hdr != CHUNK_HEADER:
		raise ValueError("Does not start with MIDI header chunk")
	if chunk_len != 6:
		raise ValueError("MIDI header is wrong length")
	with chunk_fp:
		type, ntracks, rate = struct.unpack(">HHH", _read(chunk_fp))
	if rate < 0:
		rate = SMPTE(((-rate) & 0xFF00) >> 8, rate & 0xFF)
	midi_file = MidiFile(MidiFileType(type), rate, [])

	for i in range(ntracks):
		chunk_hdr, chunk_len, chunk_fp = _get_chunk(fp)
		if chunk_hdr != CHUNK_TRACK:
			raise ValueError("Does not have expected MIDI track chunk")
		with chunk_fp:
			midi_file.tracks.append(list(parse_midi_track(chunk_fp)))

	return midi_file

def _parse_variable_length(fp: BinaryReader) -> int:
	n = 0
	while True:
		c, = _read(fp, 1)
		n = n << 7 | (c & 0x7F)
		if not c & 0x80:
			break
	return n

def _write_variable_length(n: int) -> bytes:
	if n == 0:
		return b"\0"
	res = []
	while n > 0:
		res.append((n & 0x7F) | 0x80)
		n >>= 7
	res.reverse()
	res[-1] = res[-1] & 0x7F
	return bytes(res)

def parse_midi_track(fp: BinaryReader) -> Iterable[TimedMidiEvent]:
	timer = 0
	last_event = None
	while True:
		try:
			offset = _parse_variable_length(fp)
		except EOFError:
			break
		timer += offset

		event, = _read(fp, 1)
		if not event & 0x80:
			if last_event is None:
				raise ValueError("No event to continue from")
			fp.seek(-1, 1)
			event = last_event

		if event < 0xF0:
			last_event = event
		else:
			last_event = None

		if 0x80 <= event < 0xC0 or 0xE0 <= event < 0xF0:
			p1, p2 = _read(fp, 2)
			yield TimedMidiEvent(timer, decode_midi_event(event, p1, p2))
		elif 0xC0 <= event < 0xE0:
			p1, = _read(fp, 1)
			yield TimedMidiEvent(timer, decode_midi_event(event, p1, None))
		elif event == 0xF0 or event == 0xF7:
			length = _parse_variable_length(fp)
			if length == 0:
				raise ValueError("Zero-length system-exclusive")
			data = _read(fp, length)
			device_id = data[0]
			terminal = length > 1 and data[-1] == 0xF7
			if terminal:
				data = data[1:-1]
			else:
				data = data[1:]
			yield TimedMidiEvent(timer, SysEx(device_id, data, terminal))
		elif event == 0xFF:
			type, = _read(fp, 1)
			length, = _read(fp, 1)
			data = _read(fp, length)
			yield TimedMidiEvent(timer, MetaEvent(type, data))
			if type == Events.END_OF_TRACK:
				break
		else:
			raise ValueError("Unrecognised event")

def write_midi_file(fp: BinaryWriter, midi: MidiFile) -> None:
	if isinstance(midi.rate, int):
		rate = midi.rate
	elif isinstance(midi.rate, SMPTE):
		rate = ((-midi.rate.fps) & 0xFF) << 8 | (midi.rate.tpf & 0xFF)
	header = struct.pack(">HHH", midi.type.value, len(midi.tracks), rate)
	_write_chunk(fp, CHUNK_HEADER, [header])
	for track in midi.tracks:
		_write_chunk(fp, CHUNK_TRACK, write_midi_track(track))

def _write_chunk(fp: BinaryWriter, chunk_type: bytes, chunk_data: Iterable[bytes], littleend: bool = False) -> None:
	fp.write(chunk_type)
	chunk_len_loc = fp.tell()
	fp.write(b"\0\0\0\0")
	chunk_len = 0
	for dat in chunk_data:
		fp.write(dat)
		chunk_len += len(dat)
	chunk_end_loc = fp.tell()
	fp.seek(chunk_len_loc)
	fp.write(struct.pack("<L" if littleend else ">L", chunk_len))
	fp.seek(chunk_end_loc)

def write_midi_track(track: MidiTrack, abbrev: bool = True) -> Iterable[bytes]:
	offset = 0
	track = list(track)
	track.sort(key=lambda event: event.time)
	last_event = None
	sysex_cont = False
	saw_end_of_track = False
	for i, event in enumerate(track):
		yield _write_variable_length(event.time - offset)
		offset = event.time

		if isinstance(event.event, SysEx):
			last_event = None
			yield b"\xF7" if sysex_cont else b"\xF0"
			next_event = track[i+1].event if i+1 < len(track) else None
			sysex_cont = event.event.terminal or not isinstance(next_event, SysEx) or next_event.device_id != event.event.device_id
			payload = bytes([event.event.device_id]) + event.event.message
			if not sysex_cont:
				payload += b"\xF7"
			yield bytes([len(payload)])
			yield payload
		elif isinstance(event.event, MetaEvent):
			last_event = None
			yield b"\xFF"
			yield bytes([event.event.event, len(event.event.data)])
			yield event.event.data
			if event.event.event == Events.END_OF_TRACK:
				saw_end_of_track = True
		else:
			ev, p1, p2 = encode_midi_event(event.event)
			if ev != last_event or not abbrev:
				yield bytes([ev])
			last_event = ev
			yield bytes([p1])
			if p2 is not None:
				yield bytes([p2])
	if not saw_end_of_track:
		yield b"\x00\xFF\x2F\x00"

def decode_midi_event(ev: int, p1: int, p2: Optional[int]) -> MidiEvent:
	channel = ev & 0xF
	ev &= 0xF0
	match ev:
		case 0x80:
			if p1 & 0x80 or p2 is None or p2 & 0x80:
				raise ValueError("Not enough parameters for note-off")
			return NoteOff(channel, p1, p2)
		case 0x90:
			if p1 & 0x80 or p2 is None or p2 & 0x80:
				raise ValueError("Not enough parameters for note-on")
			return NoteOn(channel, p1, p2)
		case 0xA0:
			if p1 & 0x80 or p2 is None or p2 & 0x80:
				raise ValueError("Not enough parameters for note-aftertouch")
			return NoteAftertouch(channel, p1, p2)
		case 0xB0:
			if p1 & 0x80 or p2 is None or p2 & 0x80:
				raise ValueError("Not enough parameters for control change")
			return Control(channel, p1, p2)
		case 0xC0:
			if p1 & 0x80:
				raise ValueError("Not enough parameters for program change")
			return Program(channel, p1)
		case 0xD0:
			if p1 & 0x80:
				raise ValueError("Not enough parameters for aftertouch")
			return Aftertouch(channel, p1)
		case 0xE0:
			if p1 & 0x80 or p2 is None or p2 & 0x80:
				raise ValueError("Not enough parameters for wheel")
			return Wheel(channel, p2 << 7 | p1)

def encode_midi_event(event: MidiEvent) -> tuple[int, int, Optional[int]]:
	if isinstance(event, NoteOff):
		return 0x80 | event.channel, event.key, event.velocity
	elif isinstance(event, NoteOn):
		return 0x90 | event.channel, event.key, event.velocity
	elif isinstance(event, NoteAftertouch):
		return 0xA0 | event.channel, event.key, event.pressure
	elif isinstance(event, Control):
		return 0xB0 | event.channel, event.control, event.value
	elif isinstance(event, Program):
		return 0xC0 | event.channel, event.program, None
	elif isinstance(event, Aftertouch):
		return 0xD0 | event.channel, event.pressure, None
	elif isinstance(event, Wheel):
		return 0xE0 | event.channel, event.wheel & 0x7F, (event.wheel >> 7) & 0x7F
	else:
		raise ValueError("Unexpected event type")

def parse_mds_file(fp: BinaryReader) -> MidiFile:
	chunk_hdr, chunk_len, chunk_fp = _get_chunk(fp, True)
	if chunk_hdr != b"RIFF":
		raise ValueError("Not a RIFF file")
	with chunk_fp:
		file_hdr = _read(chunk_fp, 4)
		if file_hdr != b"MIDS":
			raise ValueError("Not a MIDS file")
		subchunk_hdr, subchunk_len, subchunk_fp = _get_chunk(chunk_fp, True)
		if subchunk_hdr != b"fmt ":
			raise ValueError("Did not find MIDS header")
		if subchunk_len != 12:
			raise ValueError("Unexpected header length")
		with subchunk_fp:
			rate, _, _ = struct.unpack("<LLL", _read(subchunk_fp))
		track = []
		subchunk_hdr, subchunk_len, subchunk_fp = _get_chunk(chunk_fp, True)
		if subchunk_hdr != b"data":
			print(subchunk_hdr)
			raise ValueError("Did not find MIDS body")
		with subchunk_fp:
			num_blocks, = struct.unpack("<L", _read(subchunk_fp, 4))
			offet = 0
			for i in range(num_blocks):
				offset, block_len = struct.unpack("<LL", _read(subchunk_fp, 8))
				with _ChunkReader(subchunk_fp, block_len) as block_fp:
					while True:
						try:
							delta, streamid, event = struct.unpack("<Ll4s", _read(block_fp, 12))
						except EOFError:
							break
						offset += delta
						if event[3] == 0:
							track.append(TimedMidiEvent(offset, decode_midi_event(*event[:3])))
						elif event[3] == 1:
							track.append(TimedMidiEvent(offset, MetaEvent(Events.TEMPO, event[2::-1])))
						else:
							raise ValueError("Unrecognised event type")
			track.append(TimedMidiEvent(offset, MetaEvent(Events.END_OF_TRACK, b"")))
	return MidiFile(MidiFileType.SINGLETRACK, rate, [track])
