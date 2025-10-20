#!/usr/bin/python
import glob
import struct
import os
import subprocess
import sys

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
SONGSPEED[3] = 73.942 / 6.5 / 4 / 4 # can't use the beat count for this one b/c of the ritardando
SONGSPEED[4] = 3211212 / RATE / 8 / 16
SONGSPEED[5] = 2801090 / RATE / 9.5 / 12
SONGSPEED[6] = 2476961 / RATE / 12 / 8
SONGSPEED[7] = 2841502 / RATE / 14 / 8
SONGSPEED[8] = 2884115 / RATE / 38 / 4
SONGSPEED[9] = 1970535 / RATE / 24 / 4
SONGSPEED[10] = 3092158 / RATE / (22*6 + 8 + 7 + 3*6)
SONGSPEED[11] = 2199690 / RATE / ((3*11 + 2 + 3*11 + 2 + 7*8 + 8*8)/2)
SONGSPEED[12] = 4961985 / RATE / 16 / 16
TIMESIG = [[(4,2)]] * 17  # 4/4
TIMESIG[5] = [(3,2)]  # 3/4
TIMESIG[10] = [(6,2,22), (4,2,3), (3,2,1), (6,2)]  # 6/4 for 22 bars, then 3x 4/4, 1x 3/4 then back to 6/4
TIMESIG[11] = [(3,3,11), (2,3,1), (3,3,11), (2,3,1), (7,3,8), (4,2,8)]  # what a mess
MIDI_TICKRATE = 192 # 96
SONGDELAY = [0] * 17
SONGDELAY[8] = 23
SONGDELAY[9] = 23

ALLFILES = True

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
	tracks = retime_midi(hdr, tracks, speed, SONGDELAY[songnum])
	# add the timesig _after_ retiming, since we're calculating their position based on the new timescale
	tracks[0][3:3] = [
		midifile.TimedMidiEvent(ts, midifile.MetaEvent(midifile.Events.TIME_SIG, bytes([num, denom, MIDI_TICKRATE, 8])))
		for ts, num, denom in get_timesig(songnum)
	]
	midi = midifile.MidiFile(midifile.MidiFileType.MULTITRACK, MIDI_TICKRATE, tracks)
	#midi.pprint()
	fn = os.path.join(dn, "output.mid")
	with open(fn, "wb") as fp:
		midifile.write_midi_file(fp, midi)
	for track in tracks:
		track[:] = [ev._replace(event=ev.event._replace(channel=0)) if hasattr(ev.event, 'channel') else ev for ev in track]
	fn = os.path.join(dn, "output_noch.mid")
	with open(fn, "wb") as fp:
		midifile.write_midi_file(fp, midi)

def get_timesig(songnum):
	ts = 0
	for i in TIMESIG[songnum]:
		num = i[0]
		denom = i[1]
		yield ts, num, denom
		if len(i) >= 3:
			ts += (i[2] * MIDI_TICKRATE * 4 * num) >> denom

def retime_midi(hdr, tracks, songspeed, delay):
	#samp_per_note = hdr.loopsample / songlen
	#samp_per_tick = samp_per_note / MIDI_TICKRATE
	#usec_per_note = samp_per_note * 1e6 / RATE
	samp_per_note = songspeed * RATE
	samp_per_tick = samp_per_note / MIDI_TICKRATE
	usec_per_note = round(songspeed * 1e6)
	def newtime(ev):
		newtime = round(ev.time / samp_per_tick)
		if newtime > 0 or not isinstance(ev.event, midifile.MetaEvent):
			newtime += delay
		return newtime
	newtracks = [
		[
			midifile.TimedMidiEvent(newtime(ev), ev.event)
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
	args = sys.argv[1:]
	if not args:
		for i in sorted(glob.glob("[0-9][0-9]*.vgm")):
			print(i)
			dofile(i)
	else:
		global ALLFILES
		ALLFILES = False
		for i in args:
			print(i)
			dofile(i)

if __name__ == "__main__":
	main()
