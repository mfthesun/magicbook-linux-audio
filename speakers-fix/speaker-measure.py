#!/usr/bin/env python3
"""
speaker-measure.py — objective speaker measurement for HONOR DRA-XX (ALC256).

Plays test tones and records them with the laptop's internal microphones,
switching the speaker pins one at a time with hda-verb:
  both   — pins 0x14 and 0x1b on (normal state)
  top    — only 0x14 (top speakers next to the keyboard, tweeters)
  bottom — only 0x1b (bottom speakers, woofers)
For each configuration and frequency (80 Hz, 1 kHz, 6 kHz) it reports the
level of that frequency in the recording (dBFS) and its distance from the
noise floor. It also snapshots the codec state during playback.

Run as your normal user (NOT with sudo): PipeWire lives in your session.
The script calls `sudo` itself only for hda-verb (codec pin switching),
so it asks for your password once.

Changes only codec RAM (pins) and PipeWire volumes; everything is restored at
the end, and a reboot resets the codec in any case.
Before running: unplug headphones, quit EasyEffects, keep the room quiet.
"""
import json, math, os, re, struct, subprocess, sys, tempfile, time, wave, glob

HERE = os.path.dirname(os.path.abspath(__file__))
HDA_VERB = os.path.join(HERE, "..", "headset-mic", "hda-verb.py")
OUTDIR = os.path.join(HERE, "runs")
RATE = 48000
FREQS = [80, 1000, 6000]
TONE_SEC = 1.6
REC_SEC = 3.2
PLAY_DELAY = 0.8
SINK_VOL = 0.40          # fixed output volume for the test
REPEATS = 2
CONFIGS = {              # pin -> pin-ctl value
    "both":   {0x14: 0x40, 0x1b: 0x40},
    "top":    {0x14: 0x40, 0x1b: 0x00},
    "bottom": {0x14: 0x00, 0x1b: 0x40},
}

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def verb(nid, v, param=0):
    r = run(["sudo", "python3", HDA_VERB, hex(nid), hex(v), hex(param)])
    m = re.search(r"-> (0x[0-9a-fA-F]+)", r.stdout)
    if r.returncode != 0 or not m:
        raise RuntimeError(f"hda-verb {nid:#x} {v:#x} {param:#x} failed: {r.stdout}{r.stderr}")
    return int(m.group(1), 16)

def get_pinctl(nid):
    return verb(nid, 0xf07) & 0xff

def set_pinctl(nid, val):
    verb(nid, 0x707, val)

def module_param(name):
    for f in glob.glob(f"/sys/module/snd_hda_codec_alc269/parameters/{name}"):
        try:
            return open(f).read().strip()
        except OSError:
            pass
    return "?"

def pick_source():
    if os.environ.get("MEAS_SOURCE"):
        return os.environ["MEAS_SOURCE"]
    names = [l.split("\t")[1] for l in run(["pactl", "list", "short", "sources"]).stdout.splitlines()
             if "\t" in l and ".monitor" not in l.split("\t")[1]]
    for key in ("Mic1", "dmic", "DMIC", "Digital"):
        for n in names:
            if key in n:
                return n
    return run(["pactl", "get-default-source"]).stdout.strip()

def get_vol(target):
    m = re.search(r"Volume:\s*([0-9.]+)", run(["wpctl", "get-volume", target]).stdout)
    return m.group(1) if m else None

def make_tone(path, freq):
    n = int(RATE * TONE_SEC); fade = int(RATE * 0.02); amp = 0.5
    frames = bytearray()
    for i in range(n):
        g = min(1.0, i / fade, (n - 1 - i) / fade)
        v = int(32767 * amp * g * math.sin(2 * math.pi * freq * i / RATE)) if freq else 0
        frames += struct.pack("<hh", v, v)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(bytes(frames))

def record_and_play(src, tone, rec, snap=None):
    p = subprocess.Popen(["pw-record", "--target", src, "--rate", str(RATE), "--channels", "1",
                          "--format", "s16", rec], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(PLAY_DELAY)
    pl = None
    if tone:
        pl = subprocess.Popen(["pw-play", tone], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if snap:
            time.sleep(TONE_SEC / 2)
            snap()
        pl.wait()
    time.sleep(max(0.0, REC_SEC - PLAY_DELAY - (TONE_SEC if tone else 0)))
    p.terminate(); p.wait()

def read_mono(path):
    with wave.open(path, "rb") as w:
        ch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise RuntimeError(f"unexpected sample width {sw}")
    vals = struct.unpack("<%dh" % (len(raw) // 2), raw)
    return [sum(vals[i:i + ch]) / ch for i in range(0, len(vals), ch)]

def goertzel_dbfs(x, freq):
    n = len(x); k = 2 * math.cos(2 * math.pi * freq / RATE)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + k * s1 - s2; s2, s1 = s1, s0
    power = s1 * s1 + s2 * s2 - k * s1 * s2
    amp = 2 * math.sqrt(max(power, 0.0)) / n / 32768
    return 20 * math.log10(amp) if amp > 0 else -200.0

def level(path, freq):
    x = read_mono(path)
    blk = int(RATE * 0.1)
    vals = sorted((goertzel_dbfs(x[i:i + blk], freq) for i in range(0, len(x) - blk, blk)), reverse=True)
    top = vals[:8] if len(vals) >= 8 else vals
    return sum(top) / len(top)

def codec_snapshot():
    out = []
    for f in glob.glob("/proc/asound/card*/codec#*"):
        try:
            t = open(f).read()
        except OSError:
            continue
        if "Realtek" not in t:
            continue
        node = None
        for line in t.splitlines():
            if line.startswith("Node "):
                node = line.split()[1]
            elif node in ("0x02", "0x03") and "Converter:" in line:
                out.append(f"{node} {line.strip()}")
            elif node in ("0x14", "0x1b") and ("Pin-ctls" in line or "Amp-Out vals" in line):
                out.append(f"{node} {line.strip()}")
    return out

def main():
    if subprocess.run(["pgrep", "-x", "easyeffects"], capture_output=True).returncode == 0:
        sys.exit("EasyEffects is running: quit it first (it changes the output).")
    if not os.path.exists(HDA_VERB):
        sys.exit(f"hda-verb not found: {HDA_VERB}")
    os.makedirs(OUTDIR, exist_ok=True)
    print("sudo is needed for hda-verb (codec pin switching):")
    subprocess.run(["sudo", "-v"], check=True)

    if verb(0x21, 0xf09) & 0x80000000:
        sys.exit("Headphones are plugged in: unplug them and run again.")

    src = pick_source()
    sink = "@DEFAULT_AUDIO_SINK@"
    orig = {nid: get_pinctl(nid) for nid in (0x14, 0x1b)}
    orig_sink_vol = get_vol(sink)
    share_dac = module_param("honor_dra_share_dac")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(OUTDIR, f"speaker-measure-dac{share_dac}-{stamp}")

    info = {"time": stamp, "honor_dra_share_dac": share_dac,
            "honor_dra_mic": module_param("honor_dra_mic"), "source": src,
            "sink_volume_set": SINK_VOL, "sink_volume_orig": orig_sink_vol,
            "source_volume": get_vol(src), "pinctl_orig": {hex(k): hex(v) for k, v in orig.items()}}
    print(json.dumps(info, ensure_ascii=False, indent=1))

    tmp = tempfile.mkdtemp(prefix="spkmeas-")
    tones = {}
    for f in FREQS:
        tones[f] = os.path.join(tmp, f"tone{f}.wav"); make_tone(tones[f], f)

    results, snaps = [], {}
    try:
        run(["wpctl", "set-volume", sink, str(SINK_VOL)])
        print("\nMeasuring the noise floor (silence, do not make noise)...")
        rec = os.path.join(tmp, "noise.wav")
        record_and_play(src, None, rec)
        noise = {f: level(rec, f) for f in FREQS}
        print("  noise:", {f: round(v, 1) for f, v in noise.items()})

        for name, pins in CONFIGS.items():
            for nid, val in pins.items():
                set_pinctl(nid, val)
            for f in FREQS:
                for rep in range(REPEATS):
                    rec = os.path.join(tmp, f"{name}-{f}-{rep}.wav")
                    def snap(name=name, f=f, rep=rep):
                        if f == 1000 and rep == 0:
                            snaps[name] = codec_snapshot()
                    record_and_play(src, tones[f], rec, snap)
                    pc = {hex(n): hex(get_pinctl(n)) for n in (0x14, 0x1b)}
                    lv = level(rec, f)
                    results.append({"config": name, "freq": f, "rep": rep,
                                    "dbfs": round(lv, 1), "above_noise": round(lv - noise[f], 1),
                                    "pinctl_after": pc})
                    print(f"  {name:6s} {f:5d} Hz  rep{rep}: {lv:6.1f} dBFS "
                          f"({lv - noise[f]:+5.1f} dB above noise)  pins {pc}")
    finally:
        for nid, val in orig.items():
            try:
                set_pinctl(nid, val)
            except Exception as e:
                print(f"WARNING: could not restore pin {nid:#x}: {e}")
        if orig_sink_vol:
            run(["wpctl", "set-volume", sink, orig_sink_vol])
        print("\nPins and volume restored:", {hex(n): hex(get_pinctl(n)) for n in orig})

    lines = ["config  freq    mean dBFS  above noise"]
    for name in CONFIGS:
        for f in FREQS:
            rs = [r for r in results if r["config"] == name and r["freq"] == f]
            m = sum(r["dbfs"] for r in rs) / len(rs)
            a = sum(r["above_noise"] for r in rs) / len(rs)
            lines.append(f"{name:6s} {f:5d} Hz  {m:7.1f}     {a:+6.1f}")
    table = "\n".join(lines)
    print("\n" + table)

    with open(base + ".txt", "w") as fh:
        fh.write(json.dumps(info, ensure_ascii=False, indent=1) + "\n\n")
        fh.write("noise floor (dBFS): " + json.dumps({f: round(v, 1) for f, v in noise.items()}) + "\n\n")
        fh.write(table + "\n\n")
        for r in results:
            fh.write(json.dumps(r) + "\n")
        fh.write("\ncodec state during 1 kHz playback:\n")
        for name, lines_ in snaps.items():
            fh.write(f"[{name}]\n" + "\n".join(lines_) + "\n")
    print(f"\nSaved: {base}.txt")

if __name__ == "__main__":
    main()
