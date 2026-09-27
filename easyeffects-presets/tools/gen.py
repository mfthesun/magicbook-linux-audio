#!/usr/bin/env python3
"""Generate EasyEffects 8.x output presets for Denis' devices."""
import json, re, copy, os, pathlib

# deps: git clone https://github.com/jaakkopasanen/AutoEq and https://github.com/droidwayin/GentleDynamics into tools/deps
ROOT = pathlib.Path(os.environ.get("DEPS", pathlib.Path(__file__).resolve().parent / "deps"))
OUT = pathlib.Path(__file__).resolve().parent.parent / "output"
OUT.mkdir(parents=True, exist_ok=True)
AUTOEQ = ROOT / "AutoEq/results"

SOURCES = {
    "xm5": AUTOEQ / "oratory1990/over-ear/Sony WH-1000XM5/Sony WH-1000XM5 ParametricEQ.txt",
    "xm5_rtings": AUTOEQ / "Rtings/Bruel & Kjaer 5128 over-ear/Sony WH-1000XM5/Sony WH-1000XM5 ParametricEQ.txt",
    "realme_anc_on": AUTOEQ / "Regan Cipher/in-ear/realme Buds Air 7 Pro (ANC on)/realme Buds Air 7 Pro (ANC on) ParametricEQ.txt",
    "realme_anc_off": AUTOEQ / "Regan Cipher/in-ear/realme Buds Air 7 Pro (ANC off)/realme Buds Air 7 Pro (ANC off) ParametricEQ.txt",
}
APO_TYPE = {"PK": "Bell", "LSC": "Lo-shelf", "HSC": "Hi-shelf", "LS": "Lo-shelf", "HS": "Hi-shelf"}


def parse_apo(path):
    preamp, bands = 0.0, []
    for line in pathlib.Path(path).read_text().splitlines():
        m = re.match(r"Preamp:\s*([-\d.]+)", line)
        if m:
            preamp = float(m.group(1))
        m = re.match(r"Filter \d+: ON (\w+) Fc ([\d.]+) Hz Gain ([-\d.]+) dB Q ([\d.]+)", line)
        if m:
            bands.append((APO_TYPE[m.group(1)], float(m.group(2)), float(m.group(3)), float(m.group(4))))
    return preamp, bands


ROUTING = {k: -80.01 for k in ("input-to-sidechain", "input-to-link", "sidechain-to-input",
                                  "sidechain-to-link", "link-to-input", "link-to-sidechain")}

# ---------------------------------------------------------------- plugins
def equalizer(bands, input_gain=0.0, output_gain=0.0, apo=True):
    """bands: list of (type, freq, gain, q)."""
    ch = {}
    for i, (t, f, g, q) in enumerate(bands):
        ch[f"band{i}"] = {
            "type": t, "mode": "APO (DR)" if apo else "RLC (BT)", "slope": "x1",
            "solo": False, "mute": False, "gain": g, "frequency": f, "q": q, "width": 4.0,
        }
    return {
        "bypass": False, "input-gain": input_gain, "output-gain": output_gain,
        "mode": "IIR", "decramp": "Off", "split-channels": False, "balance": 0.0,
        "pitch-left": 0.0, "pitch-right": 0.0, "num-bands": len(bands),
        "left": copy.deepcopy(ch), "right": copy.deepcopy(ch),
    }


def limiter(threshold=-1.0, oversampling="Full x2/24 bit", release=20.0):
    return {
        "bypass": False, "input-gain": 0.0, "output-gain": 0.0, "mode": "Herm Thin",
        "oversampling": oversampling, "dithering": "None", "sidechain-type": "Internal",
        "lookahead": 5.0, "attack": 2.0, "release": release, "threshold": threshold,
        "gain-boost": False, "sidechain-preamp": 0.0, "stereo-link": 100.0,
        "alr": False, "alr-attack": 5.0, "alr-release": 50.0, "alr-knee": 0.0, "alr-knee-smooth": -5.0, **ROUTING,
    }


def hpf(freq, slope="x2"):
    return {
        "bypass": False, "input-gain": 0.0, "output-gain": 0.0, "type": "High-pass",
        "equal-mode": "IIR", "mode": "BWC (BT)", "slope": slope, "frequency": freq,
        "width": 4.0, "quality": 0.0, "gain": 0.0, "balance": 0.0, "decramp": "Off",
    }


def compressor(threshold, ratio, attack, release, makeup, knee=-6.0, mode="Downward",
               sc_mode="RMS", hpf_freq=None, boost_threshold=-72.0, boost_amount=6.0):
    return {
        "bypass": False, "input-gain": 0.0, "output-gain": 0.0, "dry": -80.01, "wet": 0.0,
        "mode": mode, "attack": attack, "release": release, "release-threshold": -80.01,
        "threshold": threshold, "ratio": ratio, "knee": knee, "makeup": makeup,
        "boost-threshold": boost_threshold, "boost-amount": boost_amount, "stereo-split": False,
        "sidechain": {"type": "Feed-forward", "mode": sc_mode, "source": "Middle",
                      "stereo-split-source": "Left/Right", "preamp": 0.0,
                      "reactivity": 10.0, "lookahead": 0.0},
        # sidechain HPF: stops bass from pumping the compressor
        "hpf-mode": "12 dB/oct" if hpf_freq else "Off", "hpf-frequency": hpf_freq or 10.0,
        "lpf-mode": "Off", "lpf-frequency": 20000.0, **ROUTING,
    }


def bass_enhancer(amount, scope=120.0, harmonics=7.0, blend=0.0):
    return {"bypass": False, "input-gain": 0.0, "output-gain": 0.0, "amount": amount,
            "harmonics": harmonics, "scope": scope, "floor": 20.0, "blend": blend, "floor-active": False}


def stereo_tools(stereo_base=0.0):
    return {"bypass": False, "input-gain": 0.0, "output-gain": 0.0, "balance-in": 0.0, "balance-out": 0.0,
            "softclip": False, "mutel": False, "muter": False, "phasel": False, "phaser": False,
            "mode": "LR > LR (Stereo Default)", "side-level": 0.0, "side-balance": 0.0,
            "middle-level": 0.0, "middle-panorama": 0.0, "stereo-base": stereo_base, "delay": 0.0,
            "sc-level": 1.0, "stereo-phase": 0.0, "dry": -100.0, "wet": 0.0}


def crosstalk(delay_us=200.0, decay_db=-4.0):
    return {"bypass": False, "input-gain": 0.0, "output-gain": 0.0,
            "delay-us": delay_us, "decay-db": decay_db, "phantom-center-only": False}


def crossfeed(fcut=700, feed=4.5):
    return {"bypass": False, "input-gain": 0.0, "output-gain": 0.0, "fcut": fcut, "feed": feed}


def autogain(target=-18.0):
    return {"bypass": False, "input-gain": 0.0, "output-gain": 0.0, "target": target,
            "silence-threshold": -70.0, "maximum-history": 15, "reference": "Geometric Mean (MSI)",
            "force-silence": False}


def gentledynamics_mbc():
    """8-band Bark-scale MBC from droidwayin/GentleDynamics (GPL-3.0) + its 18 Hz HPF."""
    gd = json.load(open(ROOT / "GentleDynamics/GentleDynamics.json"))["output"]
    f, mbc = gd["filter#0"], gd["multiband_compressor#0"]
    f["decramp"] = "Off"
    mbc["dry"] = -80.01          # EE 8 minimum (= fully dry-muted)
    mbc.update(ROUTING)
    return f, mbc


def preset(chain, section="output"):
    """chain: list of (plugin_type, settings)."""
    out, order, counts = {"blocklist": []}, [], {}
    for ptype, s in chain:
        n = counts.get(ptype, 0)
        counts[ptype] = n + 1
        key = f"{ptype}#{n}"
        out[key] = s
        order.append(key)
    out["plugins_order"] = order
    return {section: out}


OUT_IN = OUT.parent / "input"
OUT_IN.mkdir(parents=True, exist_ok=True)


def save(name, p):
    if "input" in p:
        (OUT_IN / f"{name}.json").write_text(json.dumps(p, indent=4, ensure_ascii=False) + "\n")
        return
    (OUT / f"{name}.json").write_text(json.dumps(p, indent=4, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- headphones
def headphone_set(prefix, src, label):
    pre, bands = parse_apo(src)
    eq = equalizer(bands, input_gain=pre)

    # 1) Music — clean AutoEQ correction to Harman target
    save(f"{prefix} - Music{label}", preset([("equalizer", eq), ("limiter", limiter(-1.0))]))

    # 2) Music+ — GentleDynamics MBC before the correction (author's recommended order)
    f, mbc = gentledynamics_mbc()
    save(f"{prefix} - Music+ GentleDynamics{label}",
         preset([("filter", f), ("multiband_compressor", mbc), ("equalizer", eq), ("limiter", limiter(-1.0))]))

    # 3) Movie — dialogue levelling + crossfeed (less "sound inside the head")
    save(f"{prefix} - Movie{label}", preset([
        ("compressor", compressor(-26.0, 2.5, 15.0, 250.0, 5.0, knee=-8.0, hpf_freq=120.0)),
        ("equalizer", eq),
        ("crossfeed", crossfeed(700, 4.5)),
        ("limiter", limiter(-1.0, release=20.0)),
    ]))


headphone_set("Sony WH-1000XM5", SOURCES["xm5"], "")
headphone_set("Realme Buds Air 7 Pro", SOURCES["realme_anc_on"], " (ANC on)")
headphone_set("Realme Buds Air 7 Pro", SOURCES["realme_anc_off"], " (ANC off)")
# alternative XM5 correction from a different rig (Rtings, B&K 5128) — plain music only
pre, bands = parse_apo(SOURCES["xm5_rtings"])
save("Sony WH-1000XM5 - Music (alt Rtings)", preset([("equalizer", equalizer(bands, input_gain=pre)),
                                                       ("limiter", limiter(-1.0))]))

# ---------------------------------------------------------------- laptop: factory tuning (6 speakers)
# Decoded from the Honor Windows driver package (RealtekAudio 6.0.9721.1), Awinic SKTune APO
# config "awinic_SKTune_config.bin" (project "Darwin" = DRA-XX). Record = [enable, type, Fc, gain, Q, slope]
# with type 0=HPF 1=LPF 2=peak 3=shelf(high) 5=gain-less (phase) band - the latter are skipped.
# Section B ("base") stays active even in the driver's Bypass mode -> speaker correction.
FACTORY_BASE = [
    ("Bell", 500.0, -5.0, 6.0), ("Bell", 880.0, -3.0, 6.0), ("Bell", 1000.0, -3.0, 6.0),
    ("Bell", 2200.0, -4.0, 6.0), ("Bell", 9000.0, 4.0, 2.0), ("Hi-shelf", 13000.0, -6.0, 0.707),
]
FACTORY_MODE = {  # section A, per sound mode
    "Standard": [("Bell", 200.0, -3.0, 6.0), ("Bell", 450.0, -2.0, 1.0), ("Bell", 500.0, -2.5, 6.0),
                 ("Bell", 600.0, -4.0, 15.0), ("Bell", 4800.0, -6.0, 6.0)],
    "Movie":    [("Bell", 200.0, -3.0, 6.0), ("Bell", 320.0, -3.5, 3.0), ("Bell", 450.0, -4.0, 1.0),
                 ("Bell", 600.0, -4.0, 15.0), ("Bell", 4500.0, -8.0, 6.0)],
    "Voice":    [("Bell", 160.0, 3.0, 2.0), ("Bell", 350.0, -3.0, 5.0), ("Bell", 450.0, -5.0, 1.0),
                 ("Bell", 4500.0, -3.0, 3.0), ("Bell", 5000.0, -5.0, 5.0), ("Lo-pass", 15000.0, 0.0, 0.707)],
}
LF = "Honor MagicBook Pro 16 Factory"

def factory_eq(mode):
    ch = equalizer([("Hi-pass", 90.0, 0.0, 1.2)] + FACTORY_MODE[mode] + FACTORY_BASE,
                   input_gain=-6.0, apo=False)
    for side in ("left", "right"):
        ch[side]["band0"]["slope"] = "x2"      # 24 dB/oct, as in the factory config
    return ch

save(f"{LF} - Standard", preset([
    ("bass_enhancer", bass_enhancer(3.0, scope=120.0, harmonics=7.0)),
    ("equalizer", factory_eq("Standard")),
    ("compressor", compressor(-20.0, 2.0, 10.0, 100.0, 5.0, knee=-6.0, hpf_freq=100.0)),
    ("limiter", limiter(-1.0, oversampling="Full x4/24 bit")),
]))
save(f"{LF} - Movie", preset([
    ("bass_enhancer", bass_enhancer(3.0, scope=120.0, harmonics=7.0)),
    ("compressor", compressor(-26.0, 3.0, 10.0, 200.0, 6.0, knee=-8.0, hpf_freq=150.0)),
    ("equalizer", factory_eq("Movie")),
    ("crosstalk_canceller", crosstalk(200.0, -5.0)),
    ("limiter", limiter(-1.0, oversampling="Full x4/24 bit", release=20.0)),
]))
save(f"{LF} - Voice", preset([
    ("equalizer", factory_eq("Voice")),
    ("compressor", compressor(-30.0, 4.0, 8.0, 150.0, 8.0, knee=-6.0, hpf_freq=150.0)),
    ("autogain", autogain(-16.0)),
    ("limiter", limiter(-1.0, release=20.0)),
]))


# ---------------------------------------------------------------- built-in microphone (input)
def rnnoise():
    return {"bypass": False, "input-gain": 0.0, "output-gain": 0.0, "model-name": "",
            "use-standard-model": True, "enable-vad": True, "vad-thres": 50.0, "wet": 0.0, "release": 20.0}

save("Honor MagicBook Pro 16 Mic - Calls", preset([
    ("filter", hpf(90.0)),                              # rumble, keyboard thumps, fan
    ("rnnoise", rnnoise()),                             # neural noise suppression
    ("equalizer", equalizer([
        ("Bell", 250.0, -2.0, 1.0),                     # boxy laptop-chassis sound
        ("Bell", 3500.0, 3.0, 1.0),                     # speech presence
        ("Hi-shelf", 10000.0, -2.0, 0.7),               # hiss
    ], apo=False)),
    ("compressor", compressor(-24.0, 3.0, 5.0, 120.0, 6.0, knee=-6.0, hpf_freq=100.0)),
    ("limiter", limiter(-1.0, release=20.0)),
], section="input"))
