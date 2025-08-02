from dataclasses import dataclass
import math
import os
import struct

import midifile
from extract import extract_channel
from constants import RATE, MAX_BEND

@dataclass
class NoteOn:
	frame: int
	channel: int
	inst: tuple
	freq: int
	stereo: int

@dataclass
class NoteOff:
	frame: int
	channel: int

@dataclass
class ChInst:
	frame: int
	channel: int
	inst: tuple

@dataclass
class ChFreq:
	frame: int
	channel: int
	freq: int

def process_ym(hdr, commands):
	regs = [[0] * 256, [0] * 256]
	enabled = [0]*6
	prev_enabled = [0]*6
	prev_inst = [None]*6
	prev_freq = [None]*6

	def instrument(ch):
		page, ch = divmod(ch, 3)
		instr = []
		instr.extend(regs[page][i + ch] for i in range(0x30, 0xA0, 4))
		instr.extend(regs[page][i + ch] for i in range(0xB0, 0xB8, 4))
		instr[29] |= 0xC0 # remove stereo bits
		#instr.append(regs[0][0x22])
		instr.append(enabled[page*3 + ch])
		if ch == 2 and regs[0][0x27] & 0xC0:
			raise ValueError("Using fancy channel 3")
			instr.append(regs[0][0x27] & 0xC0)
			instr.extend(regs[page][0xA8:0xB0])
		if page == 1 and ch == 2 and regs[0][0x2B] & 0x80:
			raise ValueError("Using DAC")
		return tuple(instr)
	def frequency(ch):
		page, ch = divmod(ch, 3)
		return regs[page][0xA4 + ch] << 8 | regs[page][0xA0 + ch]

	for frame in commands:
		for event in frame.ym:
			if event.page == 0 and event.reg == 0x28:
				# TODO note on/off
				ch = event.value & 3
				if event.value & 4:
					ch += 3
				enabled[ch] = event.value >> 4
				#assert enabled[ch] in (0, 15)
			else:
				regs[event.page][event.reg] = event.value
		for ch in range(6):
			inst = instrument(ch)
			freq = frequency(ch)
			if prev_enabled[ch] and enabled[ch]:
				if inst != prev_inst[ch]:
					yield ChInst(frame.num, ch, inst)
					prev_inst[ch] = inst
				if freq != prev_freq[ch]:
					yield ChFreq(frame.num, ch, freq)
					prev_freq[ch] = freq
			elif prev_enabled[ch]:
				yield NoteOff(frame.num, ch)
			elif enabled[ch]:
				stereo = (regs[event.page][0xB8 + ch] & 0xC0) >> 6
				yield NoteOn(frame.num, ch, inst, freq, stereo)
				prev_inst[ch] = inst
				prev_freq[ch] = freq
			prev_enabled[ch] = enabled[ch]
	for ch in range(6):
		if prev_enabled[ch]:
			yield NoteOff(frame.num, ch)

all_instrumentmap = {}
song_instrumentmap = {}
song_instrumentlist = []
song_instrumentnotes = {}
def reset_imap():
	song_instrumentmap.clear()
	del song_instrumentlist[:]
def imap(inst):
	if inst not in all_instrumentmap:
		all_instrumentmap[inst] = len(all_instrumentmap)
	if inst not in song_instrumentmap:
		song_instrumentmap[inst] = len(song_instrumentmap)
		song_instrumentlist.append(inst)
		song_instrumentnotes[inst] = []
	return song_instrumentmap[inst]

def render_ym(hdr, ym, dn):
	reset_imap()
	for event in ym:
		if isinstance(event, NoteOn):
			imap(event.inst)
			song_instrumentnotes[event.inst].append(note(event.freq))

	write_instruments(dn)

def write_instruments(dn):
	with open(os.path.join(dn, "instruments.txt"), "w") as fp:
		for i, inst in enumerate(song_instrumentlist):
			write_instrument(fp, i, inst, dn)

def write_instrument(fp, ix, inst, dn):
	print(f"Instrument {ix}: {inst!r}", file=fp)
	print(f"Global count: {all_instrumentmap[inst]}", file=fp)
	notes = song_instrumentnotes[inst]
	l = len(notes)
	notes.sort()
	print(f"Note count: {l}", file=fp)
	print(f"Note spread: {notes[0]}..{notes[l//4]}..{notes[l//2]}..{notes[(l*3)//4]}..{notes[-1]}", file=fp)
	print(f"Note mean: {sum(notes)/l:.2f}", file=fp)
	any_am = False
	for op in range(4):
		dt = (inst[op] & 0x70) >> 4
		if dt & 3:
			print(f"Detune {op}: {'-' if dt & 4 else '+'}{dt & 3}", file=fp)
		mul = inst[op] & 0x0F
		if mul != 1:
			print(f"Multiplier {op}: {'1/2' if mul == 0 else mul}x", file=fp)
		tl = inst[op + 4] & 0x7F
		print(f"Volume {op}: {tl}", file=fp)
		rs = (inst[op + 8] & 0xC0) >> 6
		if rs:
			print(f"Rate scaling {op}: {rs}", file=fp)
		ar = inst[op + 8] & 0x1F
		print(f"Attack {op}: {ar}", file=fp)
		am = inst[op + 12] & 0x80
		if am:
			print(f"Modulation enabled {op}", file=fp)
			any_am = True
		dr1 = inst[op + 12] & 0x1F
		print(f"Decay {op}: {dr1}", file=fp)
		dr2 = inst[op + 16] & 0x1F
		print(f"Sustain {op}: {dr2}", file=fp)
		dl1 = (inst[op + 20] & 0xF0) >> 4
		print(f"Sustain level {op}: {dl1}", file=fp)
		rr = inst[op + 20] & 0x0F
		print(f"Release {op}: {rr}", file=fp)
		ssg = inst[op + 24]
		assert ssg == 0
	fb = (inst[28] & 0x38) >> 3
	if fb:
		print(f"Feedback 0: {fb}", file=fp)
	alg = inst[28] & 0x07
	print(f"Algorithm: {alg}", file=fp)
	#l = inst[29] & 0x80
	#r = inst[29] & 0x40
	#print(f"Stereo: {'L' if l else ''}{'R' if r else ''}", file=fp)
	ams = (inst[29] & 0x38) >> 3
	fms = inst[29] & 0x03
	#lfo = inst[30] & 0x08
	#lfof = inst[30] * 0x07
	if any_am: # and lfo:
		print(f"AM sensitivity {ams}", file=fp)
		print(f"FM sensitivity {fms}", file=fp)
		#print(f"LFO frequency {lfof}", file=fp)
	ops = inst[30]
	print(f"Ops enabled: {ops:01X}", file=fp)
	print(file=fp)

	gen_instrument_wav(all_instrumentmap[inst], inst, dn)

SLOTS = [[3], [3], [3], [3], [1,3], [1,2,3], [1,2,3], [0,1,2,3]]

def gen_instrument_wav(ix, inst, dn):
	with open("__tmpinst.vgm", "wb") as fp:
		noteval = round(sum(song_instrumentnotes[inst])/len(song_instrumentnotes[inst]))
		fp.write(struct.pack("<4sLLLLLLLLLHBBLLLLL", b"Vgm ", 0, 0x150, 0, 0, 0, RATE * 7, 0, 0, 0, 0, 0, 0, 7670453, 0, 0, 0, 0))
		# Reset
		fp.write(bytes((0x52, 0x22, 0x00)))
		fp.write(bytes((0x52, 0x27, 0x00)))
		fp.write(bytes((0x52, 0x28, 0x00)))
		fp.write(bytes((0x52, 0x28, 0x01)))
		fp.write(bytes((0x52, 0x28, 0x02)))
		fp.write(bytes((0x52, 0x28, 0x04)))
		fp.write(bytes((0x52, 0x28, 0x05)))
		fp.write(bytes((0x52, 0x28, 0x06)))
		fp.write(bytes((0x52, 0x2B, 0x00)))
		# Set up instrument
		for i in range(28):
			fp.write(bytes((0x52, 0x30 + 4*i, inst[i])))
		fp.write(bytes((0x52, 0xB0, inst[28])))
		fp.write(bytes((0x52, 0xB4, inst[29])))
		# Set up frequency
		#freq = round(BASE_NOTE)
		#octave = 4
		#fp.write(bytes((0x52, 0xA4, (freq & 0x300)>>8 | octave<<3)))
		#fp.write(bytes((0x52, 0xA0, freq&0x0FF)))
		freq = from_note(noteval)
		fp.write(bytes((0x52, 0xA4, (freq & 0x3F00)>>8)))
		fp.write(bytes((0x52, 0xA0, freq&0x0FF)))
		# Play note
		fp.write(bytes((0x52, 0x28, inst[30] << 4)))
		fp.write(struct.pack("<bH", 0x61, RATE))
		fp.write(struct.pack("<bH", 0x61, RATE))
		fp.write(struct.pack("<bH", 0x61, RATE))
		fp.write(bytes((0x52, 0x28, 0x00)))
		fp.write(struct.pack("<bH", 0x61, RATE))
		# Reset ADSR to peak volume only
		alg = inst[28] & 0x07
		voladjust = max(min(inst[4+i] & 0x7F for i in range(4) if i in SLOTS[alg]) - 0x10, 0)
		for i in range(4):
			vol = inst[4+i]
			if i in SLOTS[alg]:
				vol -= voladjust
			fp.write(bytes((0x52, 0x40 + 4*i, vol)))
		fp.write(bytes((0x52, 0x50, 0x1F)))
		fp.write(bytes((0x52, 0x54, 0x1F)))
		fp.write(bytes((0x52, 0x58, 0x1F)))
		fp.write(bytes((0x52, 0x5C, 0x1F)))
		fp.write(bytes((0x52, 0x60, 0x1F)))
		fp.write(bytes((0x52, 0x64, 0x1F)))
		fp.write(bytes((0x52, 0x68, 0x1F)))
		fp.write(bytes((0x52, 0x6C, 0x1F)))
		fp.write(bytes((0x52, 0x70, 0x00)))
		fp.write(bytes((0x52, 0x74, 0x00)))
		fp.write(bytes((0x52, 0x78, 0x00)))
		fp.write(bytes((0x52, 0x7C, 0x00)))
		fp.write(bytes((0x52, 0x80, 0x2F)))
		fp.write(bytes((0x52, 0x84, 0x2F)))
		fp.write(bytes((0x52, 0x88, 0x2F)))
		fp.write(bytes((0x52, 0x8C, 0x2F)))
		# Play note
		fp.write(bytes((0x52, 0x28, inst[30] << 4)))
		fp.write(struct.pack("<bH", 0x61, RATE))
		fp.write(bytes((0x52, 0x28, 0x00)))
		fp.write(struct.pack("<bH", 0x61, RATE))
		# Set volume to sustain level
		voladjust = max(min((inst[20+i] & 0xF0)>>1 for i in range(4) if i in SLOTS[alg]) - 0x10, 0)
		for i in range(4):
			vol = (inst[20+i] & 0xF0)>>1
			if i in SLOTS[alg]:
				vol -= voladjust
			fp.write(bytes((0x52, 0x40 + 4*i, vol)))
		# Play note
		fp.write(bytes((0x52, 0x28, inst[30] << 4)))
		fp.write(struct.pack("<bH", 0x61, RATE))
		fp.write(bytes((0x52, 0x28, 0x00)))
		# EOF
		fp.write(bytes((0x66,)))
		flen = fp.tell()
		fp.seek(4)
		fp.write(struct.pack("<L", flen - 4))
	extract_channel("__tmpinst.vgm", dn, f"../inst{ix:02d}_{noteval}", 1, 0)
	os.unlink("__tmpinst.vgm")

BASE_NOTE = 643.833003155359

def note(freq):
	octave = (freq & 0x3800) >> 11
	freq &= 0x7FF
	note = (math.log2(freq / BASE_NOTE) + octave) * 12
	return note + 12
def from_note(note):
	octave, note = divmod(note - 12, 12)
	freq = round(BASE_NOTE * 2**(note/12))
	return int(octave) << 11 | freq

def ym_to_midi(hdr, ym):
	tracks = []
	for tr in range(len(song_instrumentmap)):
		tracks.append([
			midifile.TimedMidiEvent(0, midifile.MetaEvent(midifile.Events.TRACK_NAME, f"FM {tr}".encode("utf-8"))),
		])
	for ch in range(6):
		tracks[0].extend(midifile.TimedMidiEvent(0, ev) for ev in midifile.param_change(6, midifile.Params.PARAM_PITCH_BEND_SENSITIVITY, MAX_BEND, 0))
	curr_note = [None] * 6
	for ev in ym:
		if isinstance(ev, NoteOn):
			assert not curr_note[ev.channel]
			tr = song_instrumentmap[ev.inst]
			n = note(ev.freq)
			rn = round(n)
			nofs = n - rn
			tracks[tr].append(midifile.TimedMidiEvent(ev.frame, midifile.Wheel(ev.channel, round((nofs/MAX_BEND + 1) * 8192))))
			tracks[tr].append(midifile.TimedMidiEvent(ev.frame, midifile.Program(ev.channel, tr)))
			tracks[tr].append(midifile.TimedMidiEvent(ev.frame, midifile.Control(ev.channel, 10, [64, 127, 0, 64][ev.stereo])))
			tracks[tr].append(midifile.TimedMidiEvent(ev.frame, midifile.NoteOn(ev.channel, rn, 64)))
			curr_note[ev.channel] = tr, rn
		elif isinstance(ev, NoteOff):
			tr, rn = curr_note[ev.channel]
			tracks[tr].append(midifile.TimedMidiEvent(ev.frame, midifile.NoteOff(ev.channel, rn, 64)))
			curr_note[ev.channel] = None
		elif isinstance(ev, ChFreq):
			tr, rn = curr_note[ev.channel]
			nofs = note(ev.freq) - rn
			assert -MAX_BEND < nofs < MAX_BEND, f"bend to {nofs}"
			tracks[tr].append(midifile.TimedMidiEvent(ev.frame, midifile.Wheel(ev.channel, round((nofs/MAX_BEND + 1) * 8192))))
		elif isinstance(ev, ChInst):
			raise ValueError("Do something about ChInst?")
		else:
			raise ValueError("something wacky is going on")
	for tr in tracks:
		tr.append(midifile.TimedMidiEvent(hdr.samplelen, midifile.MetaEvent(midifile.Events.END_OF_TRACK, b"")))
	return tracks
