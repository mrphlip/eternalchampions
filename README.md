# Eternal Champions music porting

If you're just after the actual songs, don't bother trying to figure any of this out, they're all over on SMWCentral in the usual way:
* https://www.smwcentral.net/?p=section&a=details&id=40978
* https://www.smwcentral.net/?p=section&a=details&id=40979
* https://www.smwcentral.net/?p=section&a=details&id=40980
* https://www.smwcentral.net/?p=section&a=details&id=40981
* https://www.smwcentral.net/?p=section&a=details&id=40982
* https://www.smwcentral.net/?p=section&a=details&id=40983
* https://www.smwcentral.net/?p=section&a=details&id=40984
* https://www.smwcentral.net/?p=section&a=details&id=40985
* https://www.smwcentral.net/?p=section&a=details&id=40986
* https://www.smwcentral.net/?p=section&a=details&id=40987
* https://www.smwcentral.net/?p=section&a=details&id=40988
* https://www.smwcentral.net/?p=section&a=details&id=40989
* https://www.smwcentral.net/?p=section&a=details&id=40990
* https://www.smwcentral.net/?p=section&a=details&id=40991
* https://www.smwcentral.net/?p=section&a=details&id=40992
* https://www.smwcentral.net/?p=section&a=details&id=40993

This repository is mostly for my personal record-keeping of the process of porting this Genesis soundtrack to SNES (and SMW), in case I ever have the daft idea to do this again.

I rather doubt that this repository will be actually useful for anyone at all. A lot of the scripts are pretty narrow in focus to the quirks of these specific songs, and would require work to be useful for a different game's soundtrack. Also, these scripts are full of hardcoded paths to where I have random tools installed, and such annoyances. I make no apologies for any of this.

## [go.py](go.py)
This is the main script where it starts, that does a bunch of the setup work. It:
* Parses the `.vgm` files, and extracts all the data for:
	* What notes are played when, on both the YM2612 (FM synth) and the SN76489 (PSG square-wave synth)
	* And also what the synth settings are, essentially the instrument details, for the FM synth
	* Parsing the bare minimum of the VGM fileformat in order to make this possible, there are a _lot_ of sections and opcodes which these tracks aren't using
* Groups all the notes together by what instrument they're played on
	* The EC soundtracks have the individual voices of the song bounce around wildly between the different synth channels
	* I assume the EC engine just has a big list of notes to play, and dynamically assigns them to channels based on what's available
	* So, I worked on the assumption that they wouldn't bother having instruments where the FM settings were dynamically changed per note, but rather just had one set of FM settings for each instrument, which seemed to be mostly true across the soundtrack. Each song had some small fixed list of instruments, which were kept the same throughout the song.
	* So by treating the FM settings as an instrument fingerprint and grouping notes by that, we can mostly recover the details about the individual music voices.
* From this, it outputs:
	* Recordings of the song, both tne entire song together, and also each individual FM/PSG channel in isolation, using [VGMPlay](https://vgmrips.net/wiki/VGMPlay/in_vgm)
		* I planned to generate these myself, rather than using the external utilities, but while the documentation I found for the PSG was very precise as to how the waveforms were generated, the documentation for the FM clip was not... it gave a lot of information about "oh, this register controls the volume, or the pitch, or this other register controls how the synths feed into each other to do modulation" but not by, like, how much. I'd essentially have to reverse-engineer the output of the actual chip to end up with any sort of usable result, and at that point, may as well use an existing emulator that's done that work already.
	* Recordings of each FM instrument used in the track, playing a single note, made by generating a new `.vgm` file that sets up the FM registers appropriately and then just plays one note for several seconds, and then passing that to VGMPlay. These isolated recordings would then be used to make the samples for the SMW tracks (since the SNES soundchip uses samples rather than a synth).
	* A MIDI file (using a MIDI file library I'd written before for a different project), with all of the decoded note data, one track per instrument. The generation for this also takes in details about the song's tempo, so it can convert the timescale in the VGM file (which is measured in realtime) into logical time in the MIDI (measured in beats). And also timesignature information for good measure.
		* Initially, I had it output a MIDI file where the notes were being played on different MIDI channels, according to which FM/PSG channel was being used. This let me encode details like pitch bends accurately, and have each pitch bend affect just the note on that channel.
		* However, the MIDI software I am using, Rosegarden, can't handle having multiple MIDI channels on a single track, so it would split up each track per-channel... so I'd end up with a track for all the notes of the first instrument that were played on FM channel 1, then all the notes of the first instrument that were played on FM channel 2, etc. It worked but it was a pain to work with.
		* So now it also outputs a second MIDI file that doesn't do any channel info, just shoves everything onto the same MIDI channel. Which means it's not that useful for playback, all the pitchbends and whatnot will be broken, but it's so much nicer to look at the notes in Rosegarden.

## [inst.py](inst.py)
This is the script that generates the instrument samples from the notes generated on the FM chip
* For each instrument, I looked at the sample in Audacity and picked out where the sample seemed to either end, or loop.
	* Most of the looping samples would have some sort of initial attack transient, that would then settle down into a simpler steady state, depending on the ADSR envelopes of the different modulation synths that I don't really understand still. So for these I would play the sound from the beginning, and then pick a loop point somewhere after it settled, so that the sample would capture that timbre change.
	* A small handful of the instruments kept the exact same timbre throughout... usually some form of basic sine wave or suchlike. For those, I just captured a loop in isolation from the middle of the sample, and used the ADSR settings on the SMW side to mimic the attack envelope of the instrument.
	* There were also a bunch of samples that didn't loop at all, mostly percussion effects, these I just captured in their entirety as a single sample.
* For each instrument, I also picked a rough sample rate it should be played at. I didn't really have any good science here for this, but in general, instruments with higher frequency components would need higher sample rates, but samples that are played for longer would need lower sample rates (to fit in the filesize limits). This was mostly just a process of increasing the number if it sounded too muffled, and decreasing the number if the output size got too big for a track.
* The script then does some mangling of the numbers... the BRR file format can only loop in a multiple of 16 samples, so the script adjust the output sample rate to the nearest value where the length of the loop we want to do fits that restriction. That done, we also adjust the loop start/end points to individually be multiples of 16, on the theory that moving both the start and end points of the loop forward or backward by a few samples, should still loop cleanly, if they both move by the same amount.
* All of that done, we use [SoX](https://en.wikipedia.org/wiki/SoX) to chop up the sound file, first by processing it to the target sample rate, and then by chopping out all the individual pieces - the intro before the loop, the first loop, and also the second loop right afterward, and then uses some crossfade magic to assemble a result that should loop cleanly even if the sample endpoints don't quite line up perfectly.
* This end result is passed to [brr-encoder](https://www.smwcentral.net/?p=section&a=details&id=31093) to generate the BRR file, and the loop information is appended to it.
	* It also runs it _back_ through brr-decoder, so I have a wav file I can listen to, to see how the final sample sounds, confirm the sample rate is good enough, and if the loop works.
* The script then calculates the appropriate tuning values that need to be given to AddMusicK to make the instrument play correctly, based on what note the recording is, and what sample rate it was resampled to.
	* However, for the tuneless percussion instruments, I instead generate tuning values to make the sound play back correctly at `o3c`, intead of whatever note it was originally generated at, just to make my life easier.
	* The script spits out to stdout the instrument definition ready to be copied directly into the song text file.
* The script also performs some sanity checks: that the sound doesn't clip when we crank up the volume a bit (all the original samples recorded rather quiet, so cranking up the volume gives the BRR encoder more range to work with, but we don't want it to clip).
* It also checks that the sample rate is compatible with the actual notes we want to play... the SPC plays higher notes by increasing the playback sample rate, and there's a maximum sample rate it can play at before the registers overflow... the upshot of which is that, at a given sample rate, there's a maximum playback pitch that can be reached (or, conversely, to reach a certain pitch, there's a maximum sample rate we can use for the sample), and the script will flag any violations of this constraint.
	* There is one instrument that we actually have two copies of, at different sample rates... a high-sample-rate one for lower notes, and a low-sample-rate copy for high notes... the former is so high-rate that the higher notes are not playable, but the latter is so low-rate that the lower notes sound too muffled, so we burn more sample storage space on the duplication instead.

## [psg_chords.py](psg_chords.py)
This is the script that generates the instrument samples from the notes generated on the PSG chip
* In theory this would be very simple... the PSG chip can only play square waves, so really all I should need is a simple square wave brr and we'd be done.
* Unfortunately, when you add them up... the Genesis is capable of playing 10 sounds at once (6 FM channels, 3 PSG square wave channels, 1 PSG noise channel). The SNES can play 8 (and ideally we want to leave a channel or two underutilised to make room for sound effects too). So if a song is using that full capability, we have to get Creative to get things to fit.
* One of the ways I did this was by generating compound instruments: a single sample that's playing multiple notes at once. Then on playback this can result in multiple notes being played in a single track.
* Downside: this can only really be used if there are multiple notes being played at the same time, the right distance apart. This rarely happened with the FM instruments... there is one instrument that was used in a couple of songs on two tracks in perfect parallel fifths, so I could generate a sample of playing two notes a fifth apart and pack that into one track.
* But did happen a lot more frequently on the PSG tracks, which frequently used the three square waves to play chords.
* Upside: making a sample that plays all three notes of the chord at once lets me pack all three PSG tracks into a single SNES track, saving a ton of polyphony space.
* Downside: we need to have a new sample file for every distinct chord shape... chords are playing a major triad, followed by a minor triad, followed by an augmented chord, followed by a minor triad that's been inverted, followed by... well, all of those are separate instruments.
* Upside: because it's all square waves, all of those samples are individually very simple, and quite small, so even having multiple o fthem doesn't add up to much. The worst offender is track 11, Midknight's theme, which uses 14 distinct chord shape instruments, but all added up these only amount to just under 5kB. That's only as much as one or two of the samples I was making for the FM instruments.
* So, I have this script, which generates combinations of square waves as BRR files. You give it a list of semitone offsets, eg a major triad would be `[0, 4, 7]`. And it calculates:
	* How long does the sample need to be? Equal temperament scales are annoyingly irrational, so if we just play each note perfectly and wait for all of them to loop together, we'll be waiting forever. Instead, we pick a length, and play eacn note _as close_ as we can get it to the target pitch, such that it still loops perfectly at the end of the sample. And then we keep increasing the length until all the notes are within a tolerable error of the target note.
	* For example, for our major triad, we end up with an output that's 960 samples long. The three notes are played at freqencies such that they each have 30, 38 and 45 cycles during that time.
	* This means that the intervals are actually `[0, 4.09, 7.02]` instead of `[0, 4, 7]`, which is not quite perfect but is tolerable.
	* I picked a threshold of 10 cents as being acceptably off-tune.
		* As a rough rule of thumb, my understanding is that most people can hear anything around 15-20 cents off as out-of-tune, for trained musicians musicians down to about 10 cents, and then down further to 5 cents if you hear the two notes side-by-side. So I think this is a reasonble spot to put the threshold.
* Since the actual waveforms are so simple, I just output the BRR files directly, rather than generating a wave file and passing it to brr-encoder.

## The actual text files
From here, the long process of actually building the text files for the songs. This was mostly all done by hand, looking at the music roll from the MIDI in Rosegarden, and then transcribing it in the text editor.

After doing the first couple of songs, I realised I needed to be planning all my work ahead of time... so I started making [plans](plans) for each song, figuring out what each of the instruments was doing, and how they could all be fit into the 8 tracks I had available. What instruments needed to be combined, or interleaved, onto a single track, and which tracks I should leave for `#6` and `#7` (which have a tendency to be replaced by ingame sound effects).

## [09-gen.py](09-gen.py)
The one exception to doing everything by hand is track 9, Trident's theme.

I'm pretty damn sure that when they made this track, they just hooked up an RNG directly into the sequencer and recorded whatever fell out. There's no rhyme or reason to any of it, none of the notes are on-pitch, they're all just random frequencies played at random times for random durations.

There was nothing to be gained from trying to do this by hand... if a track is melodically sane, there's efficiencies to be had by making sure it's all quantised properly, and recognising loops and repeated sections, and the like. But there's none of that here.

And so, I made a script to pull out the note data and directly generate the text representation of it. Every note in the song becomes a pitch bend offset and a note at whatever pitch and duration make sense.

It's not particularly efficient, but it works, and I doubt I could do any better by hand.

Though, after the fact I did realise there are actually some loops in there... it looks like they generated 8 bars of random nonsense, and then looped that 3 times, to make the full 24-bar track... but then after that, they decided to replace bars 9-14 with new random nonsense instead. So the end result is that the first 14 bars of nonsense are all unique, but then bars 15-16 are a copy of 7-8, and then 17-24 are a copy of 1-8. Yeah, I don't get it either, but putting in those loops cut the insert size of this track by almost half, so huzzah.

## [audiolevel.py](audiolevel.py)
As a final pass through the songs, after I'd got them all sounding just how I wanted them, was to set the master volume level for each song to equalise everything. To this end, another script:
* Runs all the songs through [AddMusicK](https://www.smwcentral.net/?p=section&a=details&id=37906) to generate the SPC files for playback.
* Runs those SPC files through [mpv](https://mpv.io/) which can apparently play back SPC files, to convert them to wave files
* Runs those wave files through [wavegain](https://github.com/MestreLion/wavegain) to determine how loud they are
* Also, runs the wave files of the source songs, recorded from the VGMs, to get the original volume levels from the source game
* From these, we calculate the volume adjustment needed, with the goal being:
	* Overall, the average volume level of the entire soundtrack is comparable to the volume level of the original level music from SMW
	* The individual tracks, relative to each other, have the same relative volume differences as in the original EC.
* So, for example, most of the individual "Stage" tracks should have roughly the same volume as an SMW level track, give or take. But the Main Menu track is quite a bit louder than an SMW level track, since that song is quite a bit louder in the original game.
* I then adjust the global volume `w###` number in the text files and rerun it, and repeat until they're all as close as they're going to get to the target.

## [build.py](build.py)
The final step, this builds the final ZIP files that I need to upload to SMWCentral. One for each track, which includes the text file and the SPC from AddMusicK, along with the appropriate sample files (only the ones used by that particular track).

It also scrapes numbers from the `stats` files generated by AddMusicK, to give me information about: the insert size of each song (since I need this information for the upload form on SMWCentral), the total size of the samples (to make sure I'm within budget), and the length of each song.

Finally, it does a couple of last-minute sanity checks, to ensure that:
* All the individual tracks of the song are the same length (otherwise the looping can be messed up)
* All of the settings for the instruments are correct (to catch when, eg, I change the sample rate of an instrument and forget to update the tuning data in one of the text files)
