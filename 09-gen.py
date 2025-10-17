#!/usr/bin/python
import midifile
from pprint import pprint

SCALE = 4
BARLINES = 0xC0
WHEEL_THRESHOLD = 16

def load_midi():
	with open("out/09 - Trident's Stage/output.mid", "rb") as fp:
		mid = midifile.parse_midi_file(fp)
	events = [ev for trk in mid.tracks[-4:-1] for ev in trk]
	events.sort(key=lambda ev: ev.time)
	return events

def gen_notes():
	notes = []

	wheel = {6:0, 7:0, 8:0}
	cur_ch = None

	def end_note(time):
		if notes:
			notes[-1][1] = round(time / SCALE)
	def add_note(time, note, wheel):
		end_note(time)
		if wheel < 0 and note is not None:
			wheel += 256
			note -= 1
		notes.append([round(time / SCALE), None, note, wheel])

	for ev in load_midi():
		if isinstance(ev.event, midifile.NoteOn):
			add_note(ev.time, ev.event.key, wheel[ev.event.channel])
			cur_ch = ev.event.channel
		elif isinstance(ev.event, midifile.NoteOff):
			if ev.event.channel == cur_ch:
				add_note(ev.time, None, wheel[ev.event.channel])
				cur_ch = None
		elif isinstance(ev.event, midifile.Wheel):
			wheel[ev.event.channel] = round((ev.event.wheel - 8192) / 8192 * 256)
		elif isinstance(ev.event, midifile.MetaEvent) and ev.event.event == midifile.Events.END_OF_TRACK:
			end_note(ev.time)
			break
	return notes

def split_barlines():
	for startts, endts, note, wheel in gen_notes():
		if endts // BARLINES > startts // BARLINES:
			yield startts, (endts // BARLINES) * BARLINES, note, wheel, False
			yield (endts // BARLINES) * BARLINES, endts, None if note is None else -1, wheel, True
		else:
			yield startts, endts, note, wheel, False

def filter_notes():
	carry_newline = True
	for startts, endts, note, wheel, newline in split_barlines():
		carry_newline = carry_newline or newline
		if startts != endts:
			yield startts, endts, note, wheel, carry_newline
			carry_newline = False

def gen_output(fp):
	cur_wheel = -10
	for startts, endts, note, wheel, newline in filter_notes():
		if newline:
			fp.write("\n")
		else:
			fp.write(" ")
		if note is not None and abs(wheel - cur_wheel):
			fp.write(f"$EE ${wheel:02X} ")
			cur_wheel = wheel
		if note is None:
			fp.write("r")
		elif note == -1:
			fp.write("^")
		else:
			octave, note = divmod(note, 12)
			note = ["c", "c+", "d", "d+", "e", "f", "f+", "g", "g+", "a", "a+", "b"][note]
			fp.write(f"o{octave-3}{note}")
		fp.write(f"={endts - startts}")
	fp.write("\n")

def main():
	with open("out/09 - Trident's Stage/psg.txt", "w")  as fp:
		gen_output(fp)

if __name__ == "__main__":
	main()
