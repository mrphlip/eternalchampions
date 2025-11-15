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
	notes = [], []
	ch_map = {6:0, 7:1, 8:0}

	wheel = {6:0, 7:0, 8:0}
	cur_ch = [None, None]

	def end_note(ch, time):
		if notes[ch] and notes[ch][-1][1] is None:
			notes[ch][-1][1] = round(time / SCALE)
	def add_note(ch, time, note, wheel):
		end_note(ch, time)
		if wheel < 0 and note is not None:
			wheel += 256
			note -= 1
		notes[ch].append([round(time / SCALE), None, note, wheel])

	add_note(0, 0, None, 0)
	add_note(1, 0, None, 0)

	for ev in load_midi():
		if isinstance(ev.event, midifile.NoteOn):
			ch = ch_map[ev.event.channel]
			add_note(ch, ev.time, ev.event.key, wheel[ev.event.channel])
			cur_ch[ch] = ev.event.channel
		elif isinstance(ev.event, midifile.NoteOff):
			ch = ch_map[ev.event.channel]
			if ev.event.channel == cur_ch[ch]:
				add_note(ch, ev.time, None, wheel[ev.event.channel])
				cur_ch[ch] = None
		elif isinstance(ev.event, midifile.Wheel):
			wheel[ev.event.channel] = round((ev.event.wheel - 8192) / 8192 * 256)
		elif isinstance(ev.event, midifile.MetaEvent) and ev.event.event == midifile.Events.END_OF_TRACK:
			end_note(0, ev.time)
			end_note(1, ev.time)
			break
	return notes

def split_barlines(notes):
	for startts, endts, note, wheel in notes:
		if endts // BARLINES > startts // BARLINES:
			yield startts, (endts // BARLINES) * BARLINES, note, wheel, False
			yield (endts // BARLINES) * BARLINES, endts, None if note is None else -1, wheel, True
		else:
			yield startts, endts, note, wheel, False

def filter_notes(notes):
	carry_newline = True
	for startts, endts, note, wheel, newline in notes:
		carry_newline = carry_newline or newline
		if startts != endts:
			yield startts, endts, note, wheel, carry_newline
			carry_newline = False

def gen_output(fp, notes):
	cur_wheel = -10
	first = True
	for startts, endts, note, wheel, newline in notes:
		if not first:
			if newline:
				fp.write("\n")
			else:
				fp.write(" ")
		first = False
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
		notes = gen_notes()
		for channel in notes:
			split = split_barlines(channel)
			filtered = filter_notes(split)
			gen_output(fp, filtered)
			fp.write("\n\n")

if __name__ == "__main__":
	main()
