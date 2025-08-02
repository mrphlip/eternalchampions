import os
import subprocess

def extract_channel(fn, dn, lbl, fmmask, psgmask):
	outfn = os.path.join(dn, lbl + ".wav")
	dummyfn = os.path.join(dn, lbl + ".silent")
	if os.path.exists(outfn) or os.path.exists(dummyfn):
		return
	tempfn = os.path.splitext(fn)[0] + ".wav"
	try:
		subprocess.check_call([
			"vgmplay/vgmplay",
			"--dump-wav",
			"-c", f"YM2612.MuteMask={fmmask ^ 255}",
			"-c", f"SN76496.MuteMask={psgmask ^ 255}",
			"-c", "General.MaxLoops=1",
			"-c", "General.FadeTime=0",
			"-c", "General.FadeTimePL=0",
			"-c", "General.JinglePause=0",
			"-c", "General.FadePause=0",
			fn,
		])
	except subprocess.CalledProcessError:
		if not os.path.exists(tempfn):
			raise
	os.rename(tempfn, outfn)
	if issilent(outfn):
		os.unlink(outfn)
		with open(dummyfn, "wb") as fp:
			pass

def issilent(fn):
	with open(fn, "rb") as fp:
		fp.read(0x2C)
		while True:
			dat = fp.read(4096)
			if not dat:
				return True
			if any(dat):
				return False

def extract_channels(fn, dn):
	extract_channel(fn, dn, "full", 255, 255)
	for i in range(6):
		extract_channel(fn, dn, f"fm{i}", 1<<i, 0)
	for i in range(4):
		extract_channel(fn, dn, f"psg{i}", 0, 1<<i)
