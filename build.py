#!/usr/bin/python
import sys
import glob
import os.path
import subprocess
import re
import zipfile

TOP=os.path.dirname(__file__)
AMK="/home/phlip/smwhack/AddmusicK_1.0.11"

def init():
	os.chdir(TOP)
	if not os.path.exists("build"):
		os.mkdir("build")

def get_songs():
	os.chdir(TOP)
	return sorted(os.path.basename(i) for i in glob.glob("txt/*.txt"))

def build_songs(songs):
	os.chdir(AMK)
	subprocess.check_call(["wine", "AddmusicK.exe", "-v", "-noblock", "-norom", *(f"eternalchampions/{i}" for i in songs)])
	os.chdir(TOP)

def read_stats(songs):
	os.chdir(AMK)
	stats = {}
	for song in songs:
		stats[song] = read_stats_file(song)
	return stats

def read_stats_file(song):
	stats = {}
	with open(f"stats/{song}") as fp:
		for line in fp:
			if line.strip():
				key, val = line.split(":")
				stats[key.strip()] = val.strip()
	lengths = [int(stats[f"CHANNEL {i} TICKS"]) for i in range(8)]
	lengths_set = set(lengths)
	if 0 in lengths_set:
		lengths_set.remove(0)
	if len(lengths_set) != 1:
		raise ValueError(f"Conflicting track lengths for {song}: {lengths}")
	length, = lengths_set
	return int(stats["SONG TOTAL DATA SIZE"], 16), int(stats["SAMPLES SIZE"], 16), length

def write_stats(songs, stats):
	os.chdir(TOP)
	do_write_stats(songs, stats, sys.stdout)
	with open("build/stats.txt", "w") as fp:
		do_write_stats(songs, stats, fp)

def do_write_stats(songs, stats, fp):
	for song in songs:
		insert, samples, length = stats[song]
		print(song, file=fp)
		print(f"  Insert size: 0x{insert:04X} ({insert:,})", file=fp)
		print(f"  Samples size: 0x{samples:04X} ({samples:,})", file=fp)
		print(f"  Length: {length}", file=fp)
		print(file=fp)

def get_instrument_data():
	os.chdir(TOP)
	ret = subprocess.check_output(["./inst.py", "--skip"]).decode("utf-8")
	return set(i.strip() for i in ret.split("\n") if i.strip())

def write_zips(songs, inst_dat):
	os.chdir(TOP)
	for song in songs:
		assert song.endswith(".txt")
		zipfn = f"build/eternalchampions-{song[:-4]}.zip"
		insts = get_instruments(song, inst_dat)
		with zipfile.ZipFile(zipfn, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zfp:
			zfp.write(f"txt/{song}", f"eternalchampions-{song}")
			zfp.write(f"{AMK}/SPCs/{song[:-4]}.spc", f"eternalchampions-{song[:-4]}.spc")
			for inst in insts:
				zfp.write(f"inst/{inst}", f"eternalchampions/{inst}")

re_samples = re.compile(r"\#samples\s*\{\s*([^{}]*?)\s*\}", re.IGNORECASE | re.DOTALL)
re_instruments = re.compile(r"\#instruments\s*\{\s*([^{}]*?)\s*\}", re.IGNORECASE | re.DOTALL)
def get_instruments(song, inst_dat):
	with open(f"txt/{song}") as fp:
		dat = fp.read()

	match = re_samples.search(dat)
	assert match
	samples = match.group(1)
	samples = [i.strip() for i in samples.split("\n") if i.strip()]
	samples.remove("#optimized")
	assert all(i.startswith('"') and i.endswith('"') for i in samples)
	samples = [i[1:-1] for i in samples]

	match = re_instruments.search(dat)
	assert match
	instruments = match.group(1)
	for i in instruments.split("\n"):
		i = i.strip()
		if not i or i.startswith('"square') or ";" in i:
			continue
		if i not in inst_dat:
			raise ValueError(f"Incorrect values for {song} instrument {i}")

	return samples

def main():
	init()
	songs = get_songs()
	build_songs(songs)
	stats = read_stats(songs)
	write_stats(songs, stats)
	inst_dat = get_instrument_data()
	write_zips(songs, inst_dat)

if __name__ == "__main__":
	main()
