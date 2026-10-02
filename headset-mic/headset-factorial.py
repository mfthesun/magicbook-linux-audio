#!/usr/bin/env python3
"""Фаза 1: факторный тест "что именно включает микрофон гарнитуры" (ALC256, HONOR DRA-XX).

Вопрос: сигнал появляется из-за coef 0x45 (режим джека), из-за coef 0x1b, из-за обоих или ни из-за одного.
Раньше обе переменные менялись одновременно (0x45 и 0x1b шли парой), поэтому их эффект нельзя было разделить.

Схема 2x2:   coef 0x45 in {0xc489 (TRS), 0xd489 (CTIA)}  x  coef 0x1b in {0x0e4b, 0x0e6b}
Каждая ячейка - REPS повторов в случайном порядке. Остальные регистры не трогаем.

Что исправлено по сравнению с прошлыми скриптами:
  * запись и чтение пишутся прямыми HDA-verb'ами один раз, с правильным NID для coefex (0x57, а не 0x20);
  * ОДИН непрерывный захват на весь сеанс: кодек не засыпает и не просыпается между пробами, а смена
    регистров делается "на лету", как это делал бы драйвер при событии джека;
  * источник задаётся явно (--target), EasyEffects и DMIC в измерении не участвуют;
  * фон (тишина) и речь измеряются В КАЖДОЙ пробе, в том же состоянии регистров;
  * после каждой смены и в конце пробы значения регистров читаются обратно (ловим сброс/перезапись);
  * в конце регистры возвращаются к значениям, прочитанным в начале сеанса;
  * отрицательный контроль: заглушённый микрофон гарнитуры.

Запуск (EarPods вставлены, руки не на кнопках пульта):   sudo ./headset-factorial.py
Параметры окружения: REPS=3  SRC=<имя PipeWire-узла>  SEED=<число>  KEEP_WAV=1
Рядом должен лежать hda-verb.py. Полный сброс состояния кодека - перезагрузка.
"""
import array
import atexit
import datetime
import importlib.util
import json
import math
import os
import random
import signal
import statistics
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- тайминг одной пробы (секунды от момента записи коэффициентов) ----
SETTLE = 3.0          # пауза после записи регистров, ключ джека должен успеть
SIL = (3.0, 6.0)      # окно тишины (молчим)
SPEECH_CUE = 6.5      # момент подсказки "говорите"
SPEECH = (7.5, 12.0)  # окно речи
RUN_LEN = 13.0
LEAD = 2.0            # запас в начале записи
VOICE_SNR_DB = 12.0   # речь считается "есть", если p90 речи выше p90 тишины на столько
DEAD_PEAK = 4         # пик в отсчётах: меньше - цифровой ноль

CELLS = [(0xC489, 0x0E4B), (0xC489, 0x0E6B), (0xD489, 0x0E4B), (0xD489, 0x0E6B)]
# (nid, индекс). 0x20 - обычные coef, 0x57 - coefex (в ядре WRITE_COEFEX(0x57, idx, val) пишет в NID 0x57)
REGS = [(0x20, 0x45), (0x20, 0x1B), (0x20, 0x06), (0x20, 0x49), (0x20, 0x46), (0x57, 0x03), (0x57, 0x05)]
READ_ONLY = {(0x20, 0x46)}


def load_verb():
    spec = importlib.util.spec_from_file_location("hdaverb", os.path.join(HERE, "hda-verb.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- анализ (без железа)
def frame_levels(samples, rate, frame_s=0.02):
    fr = int(frame_s * rate)
    out = []
    for i in range(0, len(samples) - fr, fr):
        seg = samples[i:i + fr]
        rms = math.sqrt(sum(x * x for x in seg) / fr)
        out.append(20 * math.log10(max(rms, 0.5) / 32768.0))
    return out


def pctl(vals, p):
    if not vals:
        return float("nan")
    s = sorted(vals)
    k = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
    return s[k]


def analyze_window(samples, rate, t0, t1, shift):
    """Окно [t0,t1] в секундах от начала процесса записи; shift - задержка старта первого отсчёта."""
    a = int(max(0, (t0 - shift)) * rate)
    b = int(max(0, (t1 - shift)) * rate)
    seg = samples[a:b]
    if len(seg) < rate // 2:
        return None
    lv = frame_levels(seg, rate)
    return {
        "p50": pctl(lv, 0.5), "p90": pctl(lv, 0.9),
        "peak": max(abs(x) for x in seg),
    }


def run_metrics(samples, rate, t_run, shift):
    sil = analyze_window(samples, rate, t_run + SIL[0], t_run + SIL[1], shift)
    sp = analyze_window(samples, rate, t_run + SPEECH[0], t_run + SPEECH[1], shift)
    if not sil or not sp:
        return None
    return {
        "sil_p90": round(sil["p90"], 1), "sp_p90": round(sp["p90"], 1),
        "snr": round(sp["p90"] - sil["p90"], 1), "peak": sp["peak"],
        "dead": sp["peak"] < DEAD_PEAK,
    }


def summarize(runs):
    """runs: список dict с ключами cell=(r45,r1b), snr. Возвращает текст-итог и словарь эффектов."""
    by = {}
    for r in runs:
        if r["kind"] != "cell" or r.get("snr") is None:
            continue
        by.setdefault((r["r45"], r["r1b"]), []).append(r["snr"])
    lines, mean = [], {}
    for c in CELLS:
        v = by.get(c, [])
        if v:
            mean[c] = statistics.mean(v)
            lines.append(f"  0x45=0x{c[0]:04x}  0x1b=0x{c[1]:04x}   SNR ср. {mean[c]:6.1f} дБ  "
                         f"(мин {min(v):5.1f}, макс {max(v):5.1f}, n={len(v)})")
    eff = {}
    if len(mean) == 4:
        e45 = ((mean[(0xD489, 0x0E4B)] + mean[(0xD489, 0x0E6B)]) -
               (mean[(0xC489, 0x0E4B)] + mean[(0xC489, 0x0E6B)])) / 2
        e1b = ((mean[(0xC489, 0x0E6B)] + mean[(0xD489, 0x0E6B)]) -
               (mean[(0xC489, 0x0E4B)] + mean[(0xD489, 0x0E4B)])) / 2
        inter = (mean[(0xD489, 0x0E6B)] - mean[(0xD489, 0x0E4B)]) - (mean[(0xC489, 0x0E6B)] - mean[(0xC489, 0x0E4B)])
        eff = {"effect_0x45": round(e45, 1), "effect_0x1b": round(e1b, 1), "interaction": round(inter, 1)}
        lines.append("")
        lines.append(f"  главный эффект 0x45 (CTIA минус TRS):      {e45:+6.1f} дБ")
        lines.append(f"  главный эффект 0x1b (0x0e6b минус 0x0e4b): {e1b:+6.1f} дБ")
        lines.append(f"  взаимодействие:                            {inter:+6.1f} дБ")
        best = max(mean.values())
        lines.append("")
        lines.append("  ВЫВОД (эвристика, пороги ~10/6 дБ):")
        if best < VOICE_SNR_DB - 4:
            lines.append("   * Ни одна ячейка не даёт голоса. Гипотеза про 0x45/0x1b не подтверждена: смотрим "
                         "источник, уровни, bias, пины. Патч не писать.")
        elif abs(e1b) >= 10 and abs(e45) < 6 and abs(inter) < 6:
            lines.append("   * Решает coef 0x1b, а не 0x45. Прежняя трактовка 'режим джека' неверна.")
        elif abs(e45) >= 10 and abs(e1b) < 6 and abs(inter) < 6:
            lines.append("   * Решает coef 0x45 (режим джека), 0x1b не важен. Исходная гипотеза подтверждена.")
        elif abs(e45) >= 6 and abs(e1b) >= 6 or abs(inter) >= 10:
            lines.append("   * Нужны оба регистра (как и пишет ядро для CTIA: 0x45=0xd489 + 0x1b=0x0e6b).")
        else:
            lines.append("   * Картина неоднозначна, нужно больше повторов (REPS=5).")
    ctl = [r for r in runs if r["kind"] == "control" and r.get("snr") is not None]
    for r in ctl:
        lines.append(f"  контроль '{r['label']}': SNR {r['snr']:.1f} дБ")
    return "\n".join(lines), eff


# ---------------------------------------------------------------- железо / PipeWire
class Session:
    def __init__(self):
        self.hv = load_verb()
        self.user = os.environ.get("SUDO_USER") or "mfthesun"
        uid = subprocess.run(["id", "-u", self.user], capture_output=True, text=True).stdout.strip()
        self.xdg = f"/run/user/{uid}"
        self.snapshot = {}
        self.proc = None
        self.log_lines = []

    def log(self, s=""):
        print(s, flush=True)
        self.log_lines.append(s)

    def as_user(self, cmd):
        return ["runuser", "-u", self.user, "--", "env", f"XDG_RUNTIME_DIR={self.xdg}"] + cmd

    # --- HDA
    def cw(self, idx, val, nid=0x20):
        self.hv.send(nid, 0x500, idx)
        self.hv.send(nid, 0x400, val)

    def cr(self, idx, nid=0x20):
        self.hv.send(nid, 0x500, idx)
        return self.hv.send(nid, 0xC00, 0) & 0xFFFF

    def regs_text(self):
        return " ".join(f"{n:02x}/{i:02x}=0x{self.cr(i, n):04x}" for n, i in REGS)

    def take_snapshot(self):
        for n, i in REGS:
            self.snapshot[(n, i)] = self.cr(i, n)

    def restore(self):
        if not self.snapshot:
            return
        try:
            for (n, i), v in self.snapshot.items():
                if (n, i) in READ_ONLY:
                    continue
                self.cw(i, v, n)
            self.log("  регистры возвращены к значениям из начала сеанса: " + self.regs_text())
        except Exception as e:  # noqa: BLE001
            print(f"  !!! не удалось вернуть регистры: {e}", flush=True)

    # --- PipeWire
    def find_source(self):
        env = os.environ.get("SRC")
        if env:
            return env
        r = subprocess.run(self.as_user(["pw-dump"]), capture_output=True, text=True)
        try:
            objs = json.loads(r.stdout)
        except Exception:  # noqa: BLE001
            return None
        cands = []
        for o in objs:
            if o.get("type") != "PipeWire:Interface:Node":
                continue
            p = o.get("info", {}).get("props", {})
            nm = str(p.get("node.name", ""))
            if p.get("media.class") == "Audio/Source" and nm.startswith("alsa_input"):
                cands.append((nm, str(p.get("node.description", ""))))
        self.log("  найденные ALSA-источники:")
        for nm, ds in cands:
            self.log(f"    {nm}   [{ds}]")
        pick = [c for c in cands if "Mic2" in c[0] or "Headset" in c[1] or "Stereo Microphone" in c[1]]
        if len(pick) == 1:
            return pick[0][0]
        return None

    def start_recording(self, src, total, path):
        cmd = self.as_user(["timeout", "-s", "INT", str(int(total)), "pw-record", "--target", src,
                            "--rate", "48000", "--channels", "1", "--format", "s16", path])
        self.t_popen = time.monotonic()
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def now(self):
        return time.monotonic() - self.t_popen


def cue(s, bell=False):
    print(("\a" if bell else "") + s, flush=True)


def main():
    if os.geteuid() != 0:
        print("Нужен root: sudo ./headset-factorial.py")
        return 1
    S = Session()
    reps = int(os.environ.get("REPS", "3"))
    seed = int(os.environ.get("SEED", str(int(time.time()) % 100000)))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = os.path.join(HERE, "runs")
    os.makedirs(outdir, exist_ok=True)
    tmpdir = f"/tmp/hs-factorial-{stamp}"
    os.makedirs(tmpdir, exist_ok=True)
    os.chmod(tmpdir, 0o777)
    wav = os.path.join(tmpdir, "session.wav")

    atexit.register(S.restore)
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(130))

    S.log("########## фаза 1: факторный тест 0x45 x 0x1b ##########")
    S.log(f"время {stamp}, seed={seed}, повторов на ячейку: {reps}")
    try:
        sense = S.hv.send(0x21, 0xF09, 0)
    except Exception as e:  # noqa: BLE001
        S.log(f"!!! нет доступа к кодеку: {e}")
        return 1
    S.log(f"джек наушников 0x21: pin sense = 0x{sense:08x}  (бит 31 = вставлен: {'ДА' if sense & 0x80000000 else 'НЕТ'})")
    S.log(f"пин 0x19: pin-ctl = 0x{S.hv.send(0x19, 0xF07, 0):02x}, config (аппаратное, не override драйвера) = 0x{S.hv.send(0x19, 0xF1C, 0):08x}")
    for pth in ("/sys/module/snd_hda_intel/parameters/power_save", "/sys/module/snd_hda_codec/parameters/power_save"):
        try:
            S.log(f"{pth} = {open(pth).read().strip()}")
        except OSError:
            pass
    if not sense & 0x80000000:
        S.log("Гарнитура не определяется в разъёме 0x21. Вставьте EarPods до упора и повторите.")
        return 1
    S.take_snapshot()
    S.log("регистры при старте (nid/idx=значение): " + S.regs_text())
    S.log("  (запишите это: это исходное состояние кодека после загрузки/предыдущих экспериментов)")

    src = S.find_source()
    if not src:
        S.log("!!! не удалось однозначно выбрать источник. Выберите имя из списка выше и запустите так:")
        S.log("    sudo SRC=<node.name> ./headset-factorial.py")
        return 1
    S.log(f"источник записи (явный --target): {src}")
    for c in (["pactl", "get-source-volume", src], ["pactl", "get-source-mute", src]):
        r = subprocess.run(S.as_user(c), capture_output=True, text=True)
        S.log("  " + (r.stdout.strip() or r.stderr.strip()).replace("\n", " | "))
    r = subprocess.run(["amixer", "-c", "0", "sget", "Mic Boost"], capture_output=True, text=True)
    S.log("  Mic Boost: " + " ".join(l.strip() for l in r.stdout.splitlines() if "Front" in l or "Mono" in l or "Limits" in l))

    plan = [("cell", c) for c in CELLS] * reps
    random.Random(seed).shuffle(plan)
    n_ctrl = 2
    total = LEAD + RUN_LEN * (len(plan) + n_ctrl) + 3
    S.log("")
    S.log(f"Сеанс будет идти около {int(total)} с. Правила: руки НЕ на кнопках пульта; микрофон EarPods (пульт на кабеле)")
    S.log("у рта на одном расстоянии (~5-10 см); в окно тишины молчите и не двигайте кабель; в окно речи говорите")
    S.log("ровно и громко одну и ту же фразу (например, считайте 'раз, два, три...').")
    input("Нажмите Enter, когда готовы... ")

    S.start_recording(src, total, wav)
    time.sleep(LEAD)
    runs = []
    t_runs = []

    def one_run(kind, label, r45=None, r1b=None, gentle=None):
        t_run = S.now()
        if kind == "cell":
            S.cw(0x45, r45)
            S.cw(0x1B, r1b)
        rec = {"kind": kind, "label": label, "r45": r45, "r1b": r1b, "t": round(t_run, 2)}
        cue(f"[{len(runs) + 1}/{len(plan) + n_ctrl}] {label}  ->  МОЛЧИТЕ (ждём {SETTLE:.0f} с, затем тишина)...")
        while S.now() - t_run < SETTLE - 0.1:
            time.sleep(0.05)
        rec["regs_mid"] = S.regs_text()
        if gentle:
            cue(f"      {gentle}")
        while S.now() - t_run < SPEECH_CUE:
            time.sleep(0.05)
        cue("      >>> ГОВОРИТЕ <<<", bell=True)
        while S.now() - t_run < RUN_LEN - 0.4:
            time.sleep(0.05)
        rec["regs_end"] = S.regs_text()
        if kind == "cell":
            ok = (S.cr(0x45) == r45) and (S.cr(0x1B) == r1b)
            rec["regs_kept"] = ok
            if not ok:
                cue("      !!! значения 0x45/0x1b изменились во время пробы (драйвер/питание перезаписали)")
        while S.now() - t_run < RUN_LEN:
            time.sleep(0.05)
        runs.append(rec)
        t_runs.append(t_run)

    for kind, c in plan:
        one_run("cell", f"0x45=0x{c[0]:04x} 0x1b=0x{c[1]:04x}", c[0], c[1])
    # отрицательный и положительный контроль в лучшем (по построению: CTIA+0x0e6b, как делает ядро) состоянии
    S.cw(0x45, 0xD489)
    S.cw(0x1B, 0x0E6B)
    one_run("control", "контроль +: CTIA 0x0e6b, микрофон у рта (повтор)", 0xD489, 0x0E6B)
    runs[-1]["kind"] = "control"
    one_run("control", "контроль -: микрофон ЗАГЛУШЁН (зажмите пульт в кулаке, накройте одеждой), говорите у ноутбука",
            None, None, gentle="микрофон пульта заглушите прямо сейчас и говорите громко рядом с ноутбуком")
    runs[-1]["kind"] = "control"

    S.proc.wait(timeout=total + 20)
    S.restore()

    # ---- анализ
    try:
        w = wave.open(wav, "rb")
        rate, nfr = w.getframerate(), w.getnframes()
        samples = array.array("h")
        samples.frombytes(w.readframes(nfr))
        w.close()
    except Exception as e:  # noqa: BLE001
        S.log(f"!!! запись не прочиталась: {e}")
        return 1
    dur = nfr / rate
    shift = max(0.0, total - dur)  # сколько секунд от старта процесса прошло до первого отсчёта (грубо)
    S.log("")
    S.log(f"записано {dur:.1f} с при ожидаемых {total:.0f} с; оценка задержки старта захвата {shift:.2f} с")
    if shift > 3.0:
        S.log("!!! задержка старта слишком велика, окна могли сместиться - результаты ненадёжны")
    for rec, t in zip(runs, t_runs):
        m = run_metrics(samples, rate, t, shift)
        rec.update(m or {"snr": None})
    S.log("")
    S.log("---- по пробам (в порядке выполнения) ----")
    prev = "-"
    for k, rec in enumerate(runs, 1):
        tag = f"0x45=0x{rec['r45']:04x} 0x1b=0x{rec['r1b']:04x}" if rec["r45"] is not None else rec["label"][:30]
        if rec.get("snr") is None:
            S.log(f"  {k:2d}. {tag:28s} замер не удался")
        else:
            S.log(f"  {k:2d}. {tag:28s} тишина p90 {rec['sil_p90']:6.1f}  речь p90 {rec['sp_p90']:6.1f}  "
                  f"SNR {rec['snr']:5.1f} дБ  пик {rec['peak']:5d}{'  [цифровой ноль]' if rec['dead'] else ''}"
                  f"{'' if rec.get('regs_kept', True) else '  [регистры изменились]'}   (до этого: {prev})")
        prev = tag
    S.log("")
    S.log("---- ИТОГ ----")
    text, eff = summarize(runs)
    S.log(text)
    S.log("")
    S.log("Как читать: SNR = (громкость речи p90) - (громкость тишины p90) в одном состоянии регистров;")
    S.log(f"голос в пробе есть, если SNR >= {VOICE_SNR_DB:.0f} дБ. Контроль '-' должен быть заметно ниже контроля '+'; если он")
    S.log("высокий, то сигнал идёт не от микрофона гарнитуры (утечка/не тот источник), и выводы по ячейкам ненадёжны.")

    base = os.path.join(outdir, f"headset-factorial-{stamp}")
    with open(base + ".json", "w") as f:
        json.dump({"seed": seed, "reps": reps, "source": src, "snapshot_start":
                   {f"{n:02x}/{i:02x}": v for (n, i), v in S.snapshot.items()},
                   "effects": eff, "runs": runs}, f, ensure_ascii=False, indent=1)
    with open(base + ".txt", "w") as f:
        f.write("\n".join(S.log_lines) + "\n")
    if os.environ.get("KEEP_WAV") == "1":
        os.replace(wav, base + ".wav")
    subprocess.run(["chown", "-R", f"{S.user}:", outdir])
    S.log(f"\nлоги: {base}.txt / .json  (пришлите .txt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
