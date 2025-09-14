#!/usr/bin/python
import shlex
import subprocess
from math import floor, ceil
import shutil
import struct
import os
import sys

ORIGRATE = 44100
VOL = "10dB"
MAXRATE = 16000

SKIPBUILD = False

def call(args):
	print(">", shlex.join(args))
	subprocess.check_call(args)

def doloop(inst, note, rate, start, loop, end, adsr=0xFFE0, suffix="", transpose=None, maxnote=None):
	# round rate so that the loop is a whole number of blocks
	looplen = (end - loop) / ORIGRATE
	loopsamp = looplen * rate
	loopblocks = round(loopsamp / 16)
	rate = (16 * loopblocks) / looplen
	loopatblocks = ceil((loop - start) / ORIGRATE * rate / 16)
	newloop = loopatblocks * 16
	newlooplen = loopblocks * 16

	if not os.path.exists(f"inst/ec-fm-{inst:02d}{suffix}.brr") and not SKIPBUILD:
		call(["sox", f"out/inst{inst:02d}_{note:02d}.wav", "tmp/tmp1.wav", "trim", f"{start}s", "channels", "1", "vol", VOL, "rate", f"{rate}"])
		call(["sox", "tmp/tmp1.wav", "tmp/tmp2.wav", "trim", "0s", f"{newloop+newlooplen}s"])
		#call(["sox", "tmp/tmp1.wav", "tmp/tmp3.wav", "trim", f"{newloop + newlooplen//4}s", f"{newlooplen*3//4}s"])
		#call(["sox", "tmp/tmp1.wav", "tmp/tmp4.wav", "trim", f"{newloop + newlooplen}s", f"{newlooplen*3//4}s"])
		#call(["sox", "tmp/tmp4.wav", "tmp/tmp3.wav", "tmp/tmp5.wav", "splice", f"{newlooplen//2}s,{newlooplen//4}s,0"])
		call(["sox", "tmp/tmp1.wav", "tmp/tmp3.wav", "trim", f"{newloop}s", f"{newlooplen}s", "fade", "h", f"{newlooplen}s"])
		call(["sox", "tmp/tmp1.wav", "tmp/tmp4.wav", "trim", f"{newloop + newlooplen}s", f"{newlooplen}s", "fade", "h", "0s", f"{newlooplen}s", f"{newlooplen}s"])
		call(["sox", "-M", "tmp/tmp3.wav", "tmp/tmp4.wav", "tmp/tmp5.wav", "remix", "1v1,2v1"])
		call(["sox", "tmp/tmp2.wav", "tmp/tmp5.wav", "tmp/tmp6.wav"])
		call(["wine", "../smwhack/brrtools/brr_encoder.exe", "-l", "tmp/tmp6.wav", "tmp/tmp.brr"])
		call(["wine", "../smwhack/brrtools/brr_decoder.exe", f"-s{rate}", "tmp/tmp.brr", f"tmp/out_{inst:02d}{suffix}.wav"])
		with open(f"inst/ec-fm-{inst:02d}{suffix}.brr", "wb") as fpout, open("tmp/tmp.brr", "rb") as fpin:
			fpout.write(struct.pack("<H", (loopatblocks + loopblocks + 1) * 9))
			shutil.copyfileobj(fpin, fpout)
		if not os.path.exists(f"/home/phlip/smwhack/AddmusicK_1.0.6/samples/eternalchampions/ec-fm-{inst:02d}{suffix}.brr"):
			os.symlink(f"/home/phlip/eternalchampions/inst/ec-fm-{inst:02d}{suffix}.brr", f"/home/phlip/smwhack/AddmusicK_1.0.6/samples/eternalchampions/ec-fm-{inst:02d}{suffix}.brr")

	notefreq = 440 * 2**(((transpose or note)-69)/12)
	tuning = rate / notefreq / 8
	tuninga = floor(tuning)
	tuningb = round((tuning - tuninga) * 256)

	if maxnote is not None:
		if transpose:
			maxnote += transpose - note
		highfreq = 440 * 2**((maxnote - 69)/12) * tuning
		if highfreq > MAXRATE:
			raise ValueError(f"Sample rate {rate} for {inst:02d}{suffix} is too high! Reduce to {rate*MAXRATE/highfreq}")

	print(f"\"ec-fm-{inst:02d}{suffix}.brr\" ${adsr>>8:02X} ${adsr&0xFF:02X} $00 ${tuninga:02X} ${tuningb:02X}")

def donoloop(inst, note, rate, start, end, adsr=0xFFE0, suffix="", transpose=None):
	fulllen = (end - start) / ORIGRATE
	samp = fulllen * rate
	blocks = round(samp / 16)
	rate = (16 * blocks) / fulllen
	newsamp = blocks * 16

	if not os.path.exists(f"inst/ec-fm-{inst:02d}{suffix}.brr") and not SKIPBUILD:
		call(["sox", f"out/inst{inst:02d}_{note:02d}.wav", "tmp/tmp1.wav", "trim", f"{start}s", "channels", "1", "vol", VOL, "rate", f"{rate}"])
		call(["sox", "tmp/tmp1.wav", "tmp/tmp2.wav", "trim", "0s", f"{newsamp}s"])
		call(["wine", "../smwhack/brrtools/brr_encoder.exe", "tmp/tmp2.wav", "tmp/tmp.brr"])
		call(["wine", "../smwhack/brrtools/brr_decoder.exe", f"-s{rate}", "tmp/tmp.brr", f"tmp/out_{inst:02d}{suffix}.wav"])
		with open(f"inst/ec-fm-{inst:02d}{suffix}.brr", "wb") as fpout, open("tmp/tmp.brr", "rb") as fpin:
			fpout.write(struct.pack("<H", 0))
			shutil.copyfileobj(fpin, fpout)
		if not os.path.exists(f"/home/phlip/smwhack/AddmusicK_1.0.6/samples/eternalchampions/ec-fm-{inst:02d}{suffix}.brr"):
			os.symlink(f"/home/phlip/eternalchampions/inst/ec-fm-{inst:02d}{suffix}.brr", f"/home/phlip/smwhack/AddmusicK_1.0.6/samples/eternalchampions/ec-fm-{inst:02d}{suffix}.brr")

	notefreq = 440 * 2**(((transpose or note)-69)/12)
	tuning = rate / notefreq / 8
	tuninga = floor(tuning)
	tuningb = round((tuning - tuninga) * 256)

	print(f"\"ec-fm-{inst:02d}{suffix}.brr\" ${adsr>>8:02X} ${adsr&0xFF:02X} $00 ${tuninga:02X} ${tuningb:02X}")

def main():
	donoloop(0, 36, 16384, 0, 7368, transpose=60)
	doloop(1, 43, 8192, 0, 26126, 29736, maxnote=51)
	doloop(2, 45, 16384, 0, 23269, 24872, maxnote=80)
	# duplicate of the instrument at a lower bitrate to use for higher notes
	doloop(2, 45, 9216, 0, 23269, 24872, maxnote=89, transpose=33, suffix="-8va")
	# No instruments 3 or 4 - are essentially the same as instrument 2
	donoloop(5, 38, 16384, 0, 10252, transpose=60)
	doloop(6, 45, 4096, 0, 36856, 43272, maxnote=58)
	doloop(7, 80, 8192, 0, 8822, 9775, 0xCFF1, maxnote=106)
	donoloop(8, 36, 8192, 0, 12000, transpose=60)
	donoloop(9, 53, 8192, 0, 5400, transpose=60)
	doloop(10, 71, 6144, 0, 11355, 12070, 0xCFF1, maxnote=75)
	doloop(11, 78, 8192, 0, 25796, 26749, 0xAFED, maxnote=87)
	doloop(12, 48, 8192, 0, 43819, 49218)
	doloop(13, 70, 16384, 0, 14276, 15036)
	doloop(14, 70, 16384, 0, 3027, 3406, 0xFFF0)
	donoloop(15, 58, 16384, 0, 4500, transpose=60)
	doloop(16, 69, 16384, 72369, 72369, 73170, 0xC9C0)
	doloop(17, 67, 16384, 0, 1124, 2024)
	doloop(18, 64, 16384, 0, 3278, 4349, 0xFFEE)
	doloop(19, 36, 4096, 0, 6744, 17520)
	doloop(20, 57, 16384, 0, 7715, 8518, 0xFFEE)
	donoloop(21, 38, 16384, 0, 7150, transpose=60)

if __name__ == "__main__":
	if "--skip" in sys.argv:
		SKIPBUILD = True
	main()
