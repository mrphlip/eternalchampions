#!/usr/bin/python
import glob
import struct
import os
import subprocess

from constants import RATE
from vgm import read_file
from ym import process_ym, render_ym, ym_to_midi
from psg import process_psg, render_psg, psg_to_midi
from extract import extract_channels
import midifile

# seconds per quarter note
SONGSPEED = [None] * 17
SONGSPEED[1] = 1893362 / RATE / 6 / 16
SONGSPEED[2] = 4839967 / RATE / 14 / 16
SONGSPEED[3] = 73.942 / 6.5 / 4 / 4
SONGSPEED[12] = 4961985 / RATE / 16 / 16
TIMESIG = [(4,2)] * 17
MIDI_TICKRATE = 192 # 96

ALLFILES = False

def process_songdata(hdr, commands):
	ym = list(process_ym(hdr, commands))
	psg = list(process_psg(hdr, commands))
	return ym, psg

def process_file(fn, dn, songnum):
	with open(fn, "rb") as fp:
		hdr, gd3, commands = read_file(fp)
	#print(hdr)
	ym, psg = process_songdata(hdr, commands)
	#render_psg(hdr, psg, dn)
	render_ym(hdr, ym, dn, ALLFILES)
	render_midi(hdr, gd3, ym, psg, dn, songnum)

def render_midi(hdr, gd3, ym, psg, dn, songnum):
	track0 = [
		midifile.TimedMidiEvent(0, midifile.MetaEvent(midifile.Events.TRACK_NAME, f"{gd3.track_english} - {gd3.game_english}".encode("utf-8"))),
		midifile.TimedMidiEvent(0, midifile.MetaEvent(midifile.Events.COPYRIGHT, gd3.artist_english.encode("utf-8"))),
		midifile.TimedMidiEvent(0, midifile.MetaEvent(midifile.Events.TIME_SIG, bytes([TIMESIG[songnum][0], TIMESIG[songnum][1], MIDI_TICKRATE, 8]))),
		midifile.TimedMidiEvent(hdr.samplelen - hdr.loopsample, midifile.MetaEvent(midifile.Events.MARKER, "Loop start".encode("utf-8"))),
		midifile.TimedMidiEvent(hdr.samplelen, midifile.MetaEvent(midifile.Events.MARKER, "Loop end".encode("utf-8"))),
		midifile.TimedMidiEvent(hdr.samplelen, midifile.MetaEvent(midifile.Events.END_OF_TRACK, b"")),
	]
	tracks = [track0]
	tracks.extend(ym_to_midi(hdr, ym))
	tracks.extend(psg_to_midi(hdr, psg))
	speed = SONGSPEED[songnum]
	if speed is None:
		print(f"{songnum} - {hdr.loopsample}")
		speed = 0.5
	tracks = retime_midi(hdr, tracks, speed)
	midi = midifile.MidiFile(midifile.MidiFileType.MULTITRACK, MIDI_TICKRATE, tracks)
	#midi.pprint()
	fn = os.path.join(dn, "output.mid")
	with open(fn, "wb") as fp:
		midifile.write_midi_file(fp, midi)

def retime_midi(hdr, tracks, songspeed):
	#samp_per_note = hdr.loopsample / songlen
	#samp_per_tick = samp_per_note / MIDI_TICKRATE
	#usec_per_note = samp_per_note * 1e6 / RATE
	samp_per_note = songspeed * RATE
	samp_per_tick = samp_per_note / MIDI_TICKRATE
	usec_per_note = round(songspeed * 1e6)
	newtracks = [
		[
			midifile.TimedMidiEvent(round(ev.time / samp_per_tick), ev.event)
			for ev in track
		]
		for track in tracks
	]
	newtracks[0].insert(0, midifile.TimedMidiEvent(0, midifile.MetaEvent(midifile.Events.TEMPO, struct.pack(">L", round(usec_per_note))[1:])))
	return newtracks

def dofile(fn):
	dn = os.path.join("out", fn[:-4] if fn.endswith(".vgm") else fn)
	if not os.path.exists("out"):
		os.mkdir("out")
	if not os.path.exists(dn):
		os.mkdir(dn)
	songnum = int(fn[:2])
	process_file(fn, dn, songnum)
	extract_channels(fn, dn)

def main():
	if ALLFILES:
		for i in sorted(glob.glob("[0-9][0-9]*.vgm")):
			print(i)
			dofile(i)
	else:
		#dofile("01 - Main Theme.vgm")
		dofile("02 - Menu Theme.vgm")
		#dofile("03 - Character Bios.vgm")
		#dofile("12 - Larcen's Stage.vgm")

if __name__ == "__main__":
	main()
