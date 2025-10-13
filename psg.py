import struct
import os
from dataclasses import dataclass
from copy import deepcopy
from math import log2

from constants import RATE
import midifile

# https://www.smspower.org/Development/SN76489

@dataclass
class PSGState:
	volume: int
	value: int
	stereo_l: bool
	stereo_r: bool
	dirty: bool

def process_psg(hdr, commands):
	state = [PSGState(0, 0, True, True, False) for i in range(4)]
	dirty = True
	channel = field = 0
	def set(ch, fld, high, val):
		if fld:
			state[ch].volume = val & 0x0F
		elif ch == 3:
			state[ch].value = val & 0x07
			state[ch].dirty = True
		elif high:
			state[ch].value = val << 4 | (state[ch].value & 0x0F)
			state[ch].dirty = True
		else:
			state[ch].value = val | (state[ch].value & 0x3F0)
			state[ch].dirty = True

	for frame in commands:
		for event in frame.psg:
			if event.page:
				for i in range(4):
					state[i].stereo_l = bool(event.op & (16 << i))
					state[i].stereo_r = bool(event.op & (1 << i))
				dirty = True
				continue
			if event.op & 0x80:
				channel = (event.op & 0x60) >> 5
				field = (event.op & 0x10) >> 4
				set(channel, field, False, event.op & 0x0F)
			else:
				set(channel, field, True, event.op & 0x3F)
			dirty = True
		if dirty:
			yield frame.num, deepcopy(state)
			dirty = False
			for i in range(4):
				state[i].dirty = False
	yield frame.num, None

class PSGChannel:
	def __init__(self, rate):
		self.rate = rate // 16
		self.state = 0
		self.counter = 0
		self.active = 0

	def set_val(self, val):
		raise NotImplemented

	def get_resetval(self):
		raise NotImplemented

	def get_timer(self):
		if not self.active:
			return 1
		self.counter -= self.rate
		if self.counter <= 0:
			self.state = 1 - self.state
			self.counter += self.get_resetval()
			return self.state, True
		else:
			return self.state, False

class PSGTone(PSGChannel):
	def __init__(self, rate):
		super().__init__(rate)
		self.tone = 0

	def set_val(self, tone):
		if tone == 0 or tone == 1:
			self.active = 0
			self.tone = self.counter = 0
		else:
			self.active = 1
			self.tone = self.counter = tone * RATE

	def get_resetval(self):
		return self.tone

	def get_bit(self):
		return self.get_timer()[0]

class PSGNoise(PSGChannel):
	def __init__(self, rate, ch2):
		super().__init__(rate)
		self.ch2 = ch2
		self.active = 1
		self.set_val(0)

	def set_val(self, val):
		self.tone = val & 3
		self.noisetype = val & 4
		self.lfr = 0x8000
		self.last_bit = 0

	def get_resetval(self):
		if self.tone < 3:
			return RATE << (self.tone + 4)
		else:
			return self.ch2.get_resetval()

	def get_bit(self):
		bit, edge = self.get_timer()
		if bit and edge:
			self.last_bit = self.lfr & 1
			if self.noisetype:
				next_bit = (self.lfr & 1) ^ ((self.lfr & 8) >> 3)
			else:
				next_bit = self.last_bit
			self.lfr = self.lfr >> 1 | next_bit << 15
		return self.last_bit

PSG_VOLUMES = [
  32767, 26028, 20675, 16422, 13045, 10362,  8231,  6568,
   5193,  4125,  3277,  2603,  2067,  1642,  1304,     0,
]

def render_psg(hdr, psg, dn):
	state = []
	state.append(PSGTone(hdr.sn76489))
	state.append(PSGTone(hdr.sn76489))
	state.append(PSGTone(hdr.sn76489))
	state.append(PSGNoise(hdr.sn76489, state[2]))

	prev_framenum = 0
	prev_frame = None
	channeldata = [[] for i in range(4)]
	silent = [True for i in range(4)]
	for framenum, next_state in psg:
		for ch in range(4):
			for i in range(prev_framenum, framenum):
				sample = state[ch].get_bit()
				vol = PSG_VOLUMES[prev_frame[ch].volume]
				sample = vol if sample else -vol
				channeldata[ch].append(struct.pack("<hh", sample if prev_frame[ch].stereo_l else 0, sample if prev_frame[ch].stereo_r else 0))
				if (prev_frame[ch].stereo_l or prev_frame[ch].stereo_r) and sample:
					silent[ch] = False

		if next_state is not None:
			for ch in range(4):
				if next_state[ch].dirty:
					state[ch].set_val(next_state[ch].value)
		prev_framenum = framenum
		prev_frame = next_state

	for ch in range(4):
		if not silent[ch]:
			with open(os.path.join(dn, f"my_psg{ch}.wav"), "wb") as fp:
				samples = b"".join(channeldata[ch])
				fp.write(struct.pack("<4sL4s", b"RIFF", 36 + len(samples), b"WAVE"))
				fp.write(struct.pack("<4sLHHLLHH", b"fmt ", 16, 1, 2, RATE, RATE * 4, 4, 16))
				fp.write(struct.pack("<4sL", b"data", len(samples)))
				fp.write(samples)

MAX_VELOCITY = 64
PSG_VELOCITIES = [round((v/32767)**0.5*MAX_VELOCITY) for v in PSG_VOLUMES]
BASE_CHANNEL = 6
MIDI_INSTRUMENT = 80
DRUM_CHANNEL = 9
SNARE_DRUM = 40

MERGE_CHANNELS = False

def psg_to_midi(hdr, psg):
	if MERGE_CHANNELS:
		channels = [[] for ch in range(2)]
	else:
		channels = [[] for ch in range(4)]
	has_notes = [False] * len(channels)

	def add_event(ch, ev):
		if MERGE_CHANNELS:
			ch = 1 if ch == 3 else 0
		channels[ch].append(midifile.TimedMidiEvent(framenum, ev))
	def add_eof(ch):
		if MERGE_CHANNELS and ch in (1, 2):
			return
		add_event(ch, midifile.MetaEvent(midifile.Events.END_OF_TRACK, b""))
	def add_noteon(ch, tone, volume, stereo_l, stereo_r):
		midich, midinote, tune = key(ch, tone)
		add_event(ch, midifile.Control(midich, 10, [64, 127, 0, 64][stereo_r * 2 + stereo_l]))
		if tune != None:
			add_event(ch, midifile.Wheel(midich, round((tune + 1) * 8192)))
		add_event(ch, midifile.NoteOn(midich, midinote, PSG_VELOCITIES[volume]))
		has_notes[ch] = True
	def add_noteoff(ch, tone):
		midich, midinote, tune = key(ch, tone)
		add_event(ch, midifile.NoteOff(midich, midinote, 0))
	def add_volchange(ch, tone, volume):
		midich, midinote, tune = key(ch, tone)
		add_event(ch, midifile.NoteAftertouch(midich, midinote, PSG_VELOCITIES[volume]))
	def key(ch, tone):
		if ch == 3:
			return DRUM_CHANNEL, SNARE_DRUM, None
		else:
			freq = hdr.sn76489 / 32 / tone
			note = 12 * log2(freq / 440.0) + 69
			#if abs(note - round(note)) > 0.05:
			#	print(note)
			return BASE_CHANNEL + ch, round(note), note - round(note)

	framenum = 0
	if MERGE_CHANNELS:
		add_event(0, midifile.MetaEvent(midifile.Events.TRACK_NAME, "PSG Tone".encode("utf-8")))
		add_event(3, midifile.MetaEvent(midifile.Events.TRACK_NAME, "PSG Noise".encode("utf-8")))
	else:
		for ch in range(4):
			add_event(ch, midifile.MetaEvent(midifile.Events.TRACK_NAME, f"PSG {ch}".encode("utf-8")))
	for ch in range(3):
		add_event(ch, midifile.Program(BASE_CHANNEL + ch, MIDI_INSTRUMENT))
		for ev in midifile.param_change(BASE_CHANNEL + ch, midifile.Params.PARAM_PITCH_BEND_SENSITIVITY, 1, 0):
			add_event(ch, ev)

	prev_state = [PSGState(15, 0, True, True, False) for ch in range(4)]
	for framenum, state in psg:
		if state is None:
			for ch in range(4):
				if prev_state[ch].volume < 15:
					add_noteoff(ch, prev_state[ch].value)
				add_eof(ch)
			break

		for ch in range(4):
			if state[ch].volume == 15 and prev_state[ch].volume == 15:
				continue
			elif state[ch].volume == prev_state[ch].volume and state[ch].value == prev_state[ch].value:
				continue
			elif state[ch].volume == 15:
				add_noteoff(ch, prev_state[ch].value)
			elif prev_state[ch].volume == 15:
				add_noteon(ch, state[ch].value, state[ch].volume, state[ch].stereo_l, state[ch].stereo_r)
			elif state[ch].volume >= prev_state[ch].volume and state[ch].value == prev_state[ch].value:
				#add_volchange(ch, state[ch].value, state[ch].volume)
				pass
			else:
				add_noteoff(ch, prev_state[ch].value)
				add_noteon(ch, state[ch].value, state[ch].volume, state[ch].stereo_l, state[ch].stereo_r)
		prev_state = state

	return [channel for channel, enable in zip(channels, has_notes) if enable]
