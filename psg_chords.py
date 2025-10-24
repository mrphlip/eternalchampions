#!/usr/bin/python3.13
import os
import math
import itertools

THRESHOLD=0.1  # let notes be 10 cents out of tune

def gen_squares(*pitches):
	if pitches == (0,):
		fn = "square.brr"
	else:
		strpitches = "-".join(map(str, pitches))
		fn = f"square-{strpitches}.brr"
	if os.path.exists(f"inst/{fn}"):
		return

	samples = gen_samples(pitches)
	brr = gen_brr(samples)
	with open(f"inst/{fn}", "wb") as fp:
		for dat in brr:
			fp.write(dat)

	if not os.path.exists(f"/home/phlip/smwhack/AddmusicK_1.0.11/samples/eternalchampions/{fn}"):
		os.symlink(f"/home/phlip/eternalchampions/inst/{fn}", f"/home/phlip/smwhack/AddmusicK_1.0.11/samples/eternalchampions/{fn}")

def gen_samples(pitches):
	samplen, periods = find_samplen(pitches)
	for i in range(samplen):
		v = 0
		for p in periods:
			if (i % p) * 2 < p:
				v += 1
			else:
				v -= 1
		yield round(v * 7 / len(pitches))

def find_samplen(pitches):
	# find a short length that's close enough to a multiple of the required pitches
	target_periods = [32/2**(i/12) for i in pitches]
	for samplen in itertools.count(32, 32):
		periods = [samplen/round(samplen/i) for i in target_periods]
		offsets = [math.log(32/p)/math.log(2)*12 - pitch for p, pitch in zip(periods, pitches)]
		if all(abs(i) < THRESHOLD for i in offsets):
			#print(pitches, samplen, offsets)
			return samplen, periods

def islast(seq):
	# not sure why this isn't in itertools tbh
	prev = None
	has_prev = False
	for i in seq:
		if has_prev:
			yield prev, False
		prev = i
		has_prev = True
	if has_prev:
		yield prev, True

def gen_brr(samples):
	yield b'\0\0'
	for block, last in islast(itertools.batched(samples, 16, strict=True)):
		yield b'\xB3' if last else b'\xB0'
		for a, b in itertools.batched(block, 2):
			yield bytes([(a & 0xF) << 4 | (b & 0xF)])

def main():
	# basic square wave
	gen_squares(0)
	gen_squares(12) # 8va
	# for 07 Jetta's Stage
	gen_squares(0, 5, 8)  # F# B D
	gen_squares(0, 4, 9)  # G B E
	gen_squares(0, 2, 4)  # A B C#
	gen_squares(0, 4, 4)  # G B B (doubled note = doubled volume in the chord)
	gen_squares(0, 5, 9)  # G C E
	gen_squares(0, 4, 7)  # F# A# C#
	# for 11 Midnight's Stage
	gen_squares(0, 4, 9)  # Eb G C
	gen_squares(0, 5, 9)  # Eb Ab C
	gen_squares(0, 4, 8)  # E Ab C
	gen_squares(0, 5, 7)  # F Bb C
	gen_squares(0, 4, 6)  # Gb Bb C
	gen_squares(0, 3, 6)  # Gb A C
	gen_squares(0, 4, 7)  # Bb D F
	gen_squares(0, 4, 9)  # Bb D G
	gen_squares(0, 3, 8)  # C Eb Ab
	gen_squares(0, 3, 12)  # C Eb C
	gen_squares(0, 2, 12)  # Db Eb Db
	gen_squares(0, 2, 11)  # Db Eb C
	gen_squares(0, 5, 12)  # Bb Eb Bb
	gen_squares(0, 4, 8)  # B Eb G
	gen_squares(0, 3, 7)  # C Eb G
	gen_squares(0, 3, 8)  # D F Bb
	gen_squares(0, 5, 9)  # Db Gb Bb
	gen_squares(0, 3, 10)  # C Eb Bb
	# for 12 Larcen's Stage
	gen_squares(0, 7)  # G D
	gen_squares(0, 8)  # G Eb
	gen_squares(0, 9)  # G E
	gen_squares(0, 5)  # Bb Eb

if __name__ == "__main__":
	main()
