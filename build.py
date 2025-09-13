#!/usr/bin/python
import glob
import os.path
import subprocess
import re
import zipfile

TOP=os.path.dirname(__file__)
AMK="/home/phlip/smwhack/AddmusicK_1.0.6"

def init():
	os.chdir(TOP)
	if not os.path.exists("build"):
		os.mkdir("build")

def get_songs():
	os.chdir(TOP)
	return sorted(os.path.basename(i) for i in glob.glob("txt/*.txt"))

re_songline = re.compile(r"^(.*\.txt) total size: (0x[0-9A-F]*) bytes", re.IGNORECASE)
re_sampleline = re.compile(r"Space used by samples: (0x[0-9A-F]*) bytes", re.IGNORECASE)
def build_and_get_sizes(songs):
	os.chdir(AMK)
	ret = subprocess.check_output(["wine", "AddmusicK.exe", "-v", "-noblock", "-norom", *(f"eternalchampions/{i}" for i in songs)]).decode("utf-8")
	lastsong = None
	songdata = {}
	for line in ret.split("\n"):
		if match := re_songline.search(line):
			lastsong = match.group(1)
			songdata[lastsong] = [match.group(2), None]
		elif match := re_sampleline.search(line):
			assert lastsong is not None
			songdata[lastsong][1] = match.group(1)
			lastsong = None
	songdata = {os.path.basename(k): v for k, v in songdata.items() if k.startswith("eternalchampions/")}
	assert all(i in songdata and songdata[i][1] for i in songs)
	return songdata

def write_sizes(songs, sizes):
	os.chdir(TOP)
	with open("build/sizes.txt", "w") as fp:
		for song in songs:
			insert, samples = sizes[song]
			print(song, file=fp)
			print(f"  Insert size: {insert}", file=fp)
			print(f"  Samples size: {samples}", file=fp)
			print(file=fp)

def write_zips(songs):
	os.chdir(TOP)
	for song in songs:
		assert song.endswith(".txt")
		zipfn = f"build/{song[:-4]}.zip"
		insts = get_instruments(song)
		with zipfile.ZipFile(zipfn, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zfp:
			zfp.write(f"txt/{song}", song)
			zfp.write(f"{AMK}/SPCs/{song[:-4]}.spc", f"{song[:-4]}.spc")
			for inst in insts:
				instfn = "square.brr" if inst == "square.brr" else f"inst/{inst}"
				zfp.write(instfn, f"eternalchampions/{inst}")

re_samples = re.compile(r"\#samples\s*\{\s*(.*?)\s*\}", re.IGNORECASE | re.DOTALL)
def get_instruments(song):
	with open(f"txt/{song}") as fp:
		dat = fp.read()
	match = re_samples.search(dat)
	assert match
	dat = match.group(1)
	dat = dat.split()
	dat.remove("#optimized")
	assert all(i.startswith('"') and i.endswith('"') for i in dat)
	return [i[1:-1] for i in dat]

def main():
	init()
	songs = get_songs()
	#sizes = build_and_get_sizes(songs)
	#write_sizes(songs, sizes)
	write_zips(songs)

if __name__ == "__main__":
	main()
