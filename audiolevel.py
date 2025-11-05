#!/usr/bin/python
import glob
import subprocess
import math
import sys
import os
import re
from build import build_songs, AMK

TARGET_SCALE = 1/1.7871  # from running wavegain --album on the original SMW music
ADJ_SCALE = 1/1.0320  # from running wavegain --album on the out/*/full.wav files

def measure_vol(fn):
	ret = subprocess.check_output(["wavegain", "--calculate", "--scale", fn])
	# the scale value is what the sound should be _multiplied by_ to reach some target volume
	# so if we invert it, it'll be a number that represents the current volume
	# ie higher = louder
	# easier to reason about later
	return 1 / float(ret.decode("ascii"))

def record_song(fnin, fnout):
	subprocess.check_call(["mpv", "--ao=pcm", f"--ao-pcm-file={fnout}", fnin])

def measure_src_vols(target=None):
	res = {}
	for fn in sorted(glob.glob("out/*/full.wav")):
		ix = int(fn[4:6])
		if target is not None and ix not in target:
			continue
		res[ix] = measure_vol(fn)
	return res

def get_w_lvl(fn):
	with open(fn) as fp:
		dat = fp.read()
	match = re.search(r"w(\d+)", dat)
	return int(match.group(1))

def measure_dst_vols(target=None):
	songs = {}
	for fn in sorted(glob.glob("txt/*.txt")):
		ix = int(fn[4:6])
		if target is not None and ix not in target:
			continue
		songs[ix] = os.path.basename(fn)
	build_songs(songs.values())
	res = {}
	for ix, fn in songs.items():
		tmpfn = f"tmp/full_{ix:02d}.wav"
		record_song(f"{AMK}/SPCs/{fn[:-4]}.spc", tmpfn)
		vol = measure_vol(tmpfn)
		w_lvl = get_w_lvl(f"txt/{fn}")
		res[ix] = vol, w_lvl
	return res

def calc_adjustments(target=None):
	src = measure_src_vols(target)
	dst = measure_dst_vols(target)
	return {
		ix: (scale, w_lvl, dst[ix][1])
		for ix in src.keys()
		for scale in [TARGET_SCALE * (src[ix] / ADJ_SCALE) / dst[ix][0]]
		for w_lvl in [min(round(dst[ix][1] * math.sqrt(scale)), 255)]
	}

def to_db(scale):
	return math.log10(scale) * 20

def main(target=None):
	vals = calc_adjustments(target)
	print()
	print("=====")
	print()
	for ix, (scale, w_lvl, old_w_lvl) in sorted(vals.items()):
		print(f"{ix:02d}: {to_db(scale):+.3f}dB  x{scale:.3f}  w{w_lvl:d}{'  GOOD' if w_lvl == old_w_lvl else ''}")

if __name__ == "__main__":
	target = {int(i) for i in sys.argv[1:]} if len(sys.argv) > 1 else None
	main(target)
