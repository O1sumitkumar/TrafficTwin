# Arabic edition of the films (pass 8)

Every narrated film also exists with an Arabic voice-over and Arabic subtitles:
`movies/<film>.mp4` is English, `movies/<film>.ar.mp4` is Arabic (plus `.ar.srt`, `.ar.json`,
`.ar.gif`, `.ar.poster.png`), and `movies/showreel.ar.mp4` is cut from the Arabic films. Both
editions show the same frames, the same bilingual HUD and labels, and the same figures; only the
voice, the subtitles and the narration timing differ. Every film still says **synthetic demand,
uncalibrated**: «طلب اصطناعي، غير معاير» is the closing line of every Arabic film.

```bash
make voice-setup-ar                       # once: .venv-tts-ar (Chatterbox) + the reference voice clip
make movie FILM=loop LANG=ar              # one film -> movies/loop.ar.mp4
make movies-ar                            # every Arabic film, then movies/showreel.ar.mp4
uv run python -m scripts.movies.narrate validate              # English and Arabic scripts
uv run python -m scripts.movies.narrate speak loop --lang ar  # speak one film, print the timing
```

The Arabic edition is the same pipeline with `--lang ar` (`scripts/movies/narrate.py`,
`render.py`, `showreel.py`), not a fork: narration YAML -> TTS -> timing (shots stretch to fit
speech) -> voice track at -16 LUFS -> mux with a mov_text subtitle track. The English films and
their caches are untouched (the English WAV cache keys are unchanged; Arabic work files live in
`runs/movies/<film>.ar/`, Arabic speech in `runs/movies/_voice_ar/`).

## RA-001: the Arabic voice is Chatterbox Multilingual with a ClArTTS reference voice

**Decision.** Chatterbox Multilingual (Resemble AI, `chatterbox-tts` 0.1.7, model
`ResembleAI/chatterbox` revision `5bb1f6ee`, MIT licence for code and weights, language id `ar`),
cloning the voice of one 10.7 s clip of the ClArTTS corpus (utterance
`ch_02_arabic_tts_dataset_417`, one male reader, MBZUAI, CC-BY-4.0, recorded from a LibriVox
audiobook). It runs offline on the Mac's CPU in its own venv `.venv-tts-ar` (torch 2.6.0; the
English `.venv-tts` is untouched), one thread per worker process, two workers in parallel (four swapped on the 18 GB Mac).
Settings: `voice.ar` in `scripts/movies/settings.yaml` (seed 1, exaggeration 0.9, cfg weight 0.4,
no time-stretch). Chatterbox embeds Resemble's inaudible Perth watermark in every output.

**Why.** It is the only candidate that is open-weight, permissively licensed, offline and reads
fully vowelised MSA correctly: an offline Whisper large-v3-turbo transcript of each sample (MLX,
`scripts/movies/tts_ar_eval.py`) matches the text with 0 % character error on the short and the
long test lines, and gives back the number line's figures exactly (8.7 %, 178,909).

### Candidates and checks

Test lines (fully vowelised): (1) short «طَلَبٌ اصْطِنَاعِيٌّ، غَيْرُ مُعَايَرٍ.»; (2) numbers
«خَفَّضَ العَمَلُ عَنْ بُعْدٍ سَاعَاتِ المَرْكَبَاتِ بِنِسْبَةِ 8.7 فِي المِئَةِ، أَيْ نَحْوَ 178,909
سَاعَةٍ فِي اليَوْمِ.» once with digits (2d) and once with the numbers in words (2w); (3) a long
sentence through Jeddah's place names (الكورنيش الشمالي، طريق الملك عبدالعزيز، طريق التحلية، شرم
أبحر، جامعة الملك عبدالعزيز, 76 syllables). Samples: `runs/movies/_voice_ar/samples/<model>-<n>.wav`
(not in git). "Syllables/s" counts the short-vowel and tanween marks of the vowelised text, so it
overstates the spoken rate by about 10 % (pausal forms drop the final vowel). Silence = the longest
pause inside the line (20 ms RMS below -45 dBFS); CER = character error rate of the Whisper
transcript against the text without diacritics (the number lines score high only because Whisper
writes the numbers as digits; their transcripts are quoted instead).

| candidate | licence | line | length | syl/s | peak | longest silence | Whisper transcript / CER |
|---|---|---|---|---|---|---|---|
| Chatterbox, built-in voice, whole line | MIT | 1 | 2.14 s | 6.1 | 0.89 | 0.04 s | «بلب استناعي غير معاير», 0.167: ط and ص come out as ب and س |
| | | 2d | 12.18 s | 2.7 | 0.92 | 0.74 s | digits misread: «80-7% … 87.1%» |
| | | 2w | 10.24 s | 6.7 | 1.00 | 0.14 s | «… بنسبة 8.7% أي نحو 178909 ساعة في اليوم»: correct |
| | | 3 | 35.36 s | 2.2 | 1.00 (clipped) | 0.78 s | correct, then 20 s of babble after the last word; CER 1.32 |
| Chatterbox, built-in voice, clause by clause | MIT | 1 | 2.08 s | 6.3 | 0.89 | 0.04 s | «طلب استناعي غير معاير», 0.111 |
| | | 2w | 12.84 s | 5.4 | 1.00 | 0.96 s | correct figures |
| | | 3 | 16.36 s | 4.7 | 0.99 | 0.60 s | «… عبدالعزيزي … كروها …», 0.033 (2 retries) |
| **Chatterbox, ClArTTS voice, clause by clause** | MIT + CC-BY-4.0 | 1 | 4.12 s | 3.2 | 0.59 | 0.82 s | «طلب إصطناعي غير معاير», **0.000** |
| | | 2w | 11.80 s | 5.9 | 0.76 | 0.34 s | «… بنسبة 8.7% أي نحو 178909 ساعات في اليوم»: correct |
| | | 3 | 19.46 s | 3.9 | 0.57 | 0.94 s | **0.000** |
| same, exaggeration 0.9, cfg 0.4 (chosen) | | 3 | 16.60 s | 4.6 | 0.51 | 0.62 s | **0.000**, no retries |
| same, exaggeration 0.7 | | 3 | 20.16 s | 3.8 | 0.70 | 1.20 s | «الرهلة» for الرحلة, 4 retries |
| same, exaggeration 0.7, cfg 0.3 | | 3 | 18.44 s | 4.1 | 0.67 | 0.68 s | «الرهلة», 2 retries |
| same, cfg 0.7 | | 3 | 20.04 s | 3.8 | 0.86 | 1.36 s | correct, 2 retries |
| Piper `ar_JO-kareem-medium` | MIT model; training data "see URL" (unclear) | 1 | 3.15 s | 4.1 | 1.00 (clipped) | 0.08 s | «طلب نصطناعي غير معاير», 0.056 |
| | | 2w | 16.50 s | 4.2 | 1.00 (clipped) | 0.80 s | «قفض العمل …» (خ as ق), figures correct |
| | | 3 | 18.79 s | 4.1 | 1.00 (clipped) | 0.58 s | 0.000 |
| Fish Audio OpenAudio S1-mini | CC-BY-NC-SA-4.0, gated download | - | - | - | - | - | not tested: non-commercial and needs a Hugging Face login |
| Coqui XTTS-v2 | Coqui Public Model Licence (non-commercial) | - | - | - | - | - | not tested: non-commercial; Chatterbox passed first |

What the checks showed:
- **Digits.** Chatterbox misreads Western digits ("8.7" became "80-7"); written as Arabic words the
  same figures come back exactly. So every Arabic line has a `say` text with the numbers in words,
  and the subtitle `text` keeps the digits (see "Scripts" below).
- **Long lines.** On a 76-syllable line Chatterbox ran on past the end into 20 s of babble. The
  worker (`scripts/movies/tts_ar.py`) therefore speaks each line clause by clause (split after
  ، ؛ . ؟ !, clauses under 10 syllables join the next), trims each clause's silence, joins them with
  0.22 s (comma) or 0.38 s (full stop) pauses, and speaks a clause again with the next seed if it
  lasts longer than 0.32 s per syllable + 1 s or holds a silence over 1 s (at most 3 retries, the
  shortest take is kept).
- **Accent.** The built-in voice (an English reference) softens the emphatic consonants: Whisper
  hears ط and ص as ب and س. Cloning an Arabic reader fixes it (0 % CER).
- **Piper** is fast (3 s for all three lines) and intelligible, but it clips (peak 1.0), outputs
  22.05 kHz (below the 24-48 kHz asked for), sounds robotic, and its training-data licence is not
  stated. Kept as the fallback, not installed by `make voice-setup-ar`.
- **Speed.** Chatterbox on the CPU takes about 8 s per second of speech in one thread (MPS about
  6.7 s/s but its take of line 3 held a 2.1 s silence); two one-thread workers in parallel make
  up for it. Every sample is 24 kHz mono, no truncation (the last word is in each transcript).
- **Rate.** The chosen settings speak about 4.6 counted syllables/s on the long line (about 4.2
  spoken), a little above the 2.5-4 asked for; slower settings made the films longer than the
  +25 % budget allows and were not cleaner (retries, «الرهلة»).
- **Determinism.** Same text, seed and settings give byte-identical WAVs in separate processes, on
  the CPU and on MPS (checked by SHA-1; `tests/test_narration_ar.py` repeats it on the CPU). CPU
  and MPS give different takes, so the device is part of the cache key (`--device cpu`).

## Scripts

`movies/specs/<film>.narration.ar.yaml` has the same lines as the English script, in the same
order with the same `shot` / `film` / `at` / `sim_t` anchors, in Modern Standard Arabic (broadcast
register, not dialect). Each line has:
- `text`: the subtitle, without diacritics, numbers as Western digits exactly as in the English
  line (route letters and the corridor id stay Latin: "المسار A", "C1", as on the HUD);
- `say`: the fully vowelised text the voice speaks, hand-written, numbers in words, pausal sukun on
  clause ends (for example «مِئَةً وَثَمَانِيَةً وَسَبْعِينَ أَلْفًا وَتِسْعَمِئَةٍ وَتِسْعَ» for 178,909).

Place names: شرم أبحر، طريق الملك عبدالعزيز، طريق التحلية، جامعة الملك عبدالعزيز، الكورنيش
الشمالي، طريق المدينة المنورة، حي السلامة، أبحر الشمالية / الجنوبية، برج جدة.

`narrate validate` (and `tests/test_narration_ar.py`) check every Arabic script against its
English counterpart instead of the docs: same number of lines and the same anchors; the sorted
numbers in the subtitle equal the English line's; `say` has no digits; every one of those numbers
is spoken in `say` (an Arabic number-word reader, `narrate.ar_numbers`, turns «اثنين فاصلة خمسة
وثمانين» back into 2.85 and «ستمئة وأربعمئة» into 600 and 400); and the last line carries
«طلب اصطناعي، غير معاير». The English scripts are still checked against the docs, so every
Arabic figure is a documented figure.

## What is and is not translated

- Translated: the voice-over and the subtitles (the HUD draws them in the frame; the MP4 also
  carries them as a soft `mov_text` track tagged `ara`, and `movies/<film>.ar.srt` sits beside it).
  The subtitle line is set with `dir="auto"` (`web/src/cinema/hud.ts`), so the browser lays out the
  Arabic right to left; the strings are stored in logical order, never reversed.
- Not translated: the title cards, captions, KPI labels and legend come from the specs and are
  English, and the map labels stay bilingual (English with the Arabic name below) as in the
  English edition. The showreel's title cards (Pillow) keep the English film titles. Making them
  Arabic would need Arabic fields in the film specs and a re-layout; not done in pass 8.

## Films

Filled in after the renders (pass 8).

## Credits

Voice: Chatterbox Multilingual by Resemble AI (MIT). Reference voice: ClArTTS, Kulkarni et al.,
"ClArTTS: An Open-Source Classical Arabic Text-to-Speech Corpus", Interspeech 2023 (MBZUAI,
CC-BY-4.0; audio from LibriVox). Sample checks: Whisper large-v3-turbo (MIT) via mlx-whisper (MIT).
