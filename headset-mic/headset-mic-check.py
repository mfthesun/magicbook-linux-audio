#!/usr/bin/env python3
"""Фаза 2: проверка микрофона гарнитуры ПОСЛЕ перезагрузки с DKMS 2.2. В кодек ничего не пишет (только чтение).

Показывает: режим honor_dra_mic, сообщения драйвера, значения регистров, вердикт автоопределения типа
гарнитуры (из dmesg), и измеряет микрофон так же, как фаза 1 (явный источник, тишина/речь, SNR).

  sudo ./headset-mic-check.py             # холодный тест: гарнитура вставлена с загрузки
  sudo ./headset-mic-check.py --hotplug   # горячая вставка: скрипт попросит вынуть и вставить гарнитуру

Для вердикта автоопределения скрипт включает dynamic debug модуля snd_hda_codec_realtek (debugfs, не кодек);
при холодном тесте сообщение уже могло пройти до этого, его ловит --hotplug.
Параметры окружения: SRC=<имя PipeWire-узла>. Рядом должны лежать hda-verb.py и headset-factorial.py.
"""
import array
import importlib.util
import os
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("hf", os.path.join(HERE, "headset-factorial.py"))
hf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hf)


def sense(S):
    return bool(S.hv.send(0x21, 0xF09, 0) & 0x80000000)


def wait_sense(S, want, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if sense(S) == want:
            return True
        time.sleep(0.2)
    return False


def read_param():
    for m in ("snd_hda_codec_alc269", "snd_hda_codec_realtek"):
        p = f"/sys/module/{m}/parameters/honor_dra_mic"
        if os.path.exists(p):
            return m, open(p).read().strip()
    return None, None


def dmesg_lines():
    r = subprocess.run(["dmesg"], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if "HONOR DRA-XX" in l or "iPhone-style" in l]


def main():
    if os.geteuid() != 0:
        print("Нужен root: sudo ./headset-mic-check.py")
        return 1
    hotplug = "--hotplug" in sys.argv
    S = hf.Session()
    mod, val = read_param()
    S.log("########## фаза 2: проверка микрофона гарнитуры ##########")
    S.log(f"модуль {mod}: honor_dra_mic = {val if val is not None else 'нет параметра (старая версия DKMS?)'}")
    if val is None:
        S.log("Установите DKMS 2.2 (./install.sh) и перезагрузитесь.")
        return 1

    dd = "/sys/kernel/debug/dynamic_debug/control"
    try:
        with open(dd, "w") as f:
            f.write("module snd_hda_codec_realtek +p\n")
        S.log("dynamic debug snd_hda_codec_realtek: включён")
    except OSError as e:
        S.log(f"dynamic debug включить не удалось ({e}); вероятно, lockdown при Secure Boot. Вердикт автоопределения судим по регистрам")

    if hotplug:
        S.log("")
        S.log(">>> ВЫНЬТЕ гарнитуру из разъёма (жду до 60 с)...")
        if not wait_sense(S, False):
            S.log("Гарнитура не вынута, отмена.")
            return 1
        S.log("    вынута. Ждём 3 с...")
        time.sleep(3)
        S.log(">>> ВСТАВЬТЕ гарнитуру до упора (жду до 60 с)...")
        if not wait_sense(S, True):
            S.log("Гарнитура не вставлена, отмена.")
            return 1
        S.log("    вставлена. Ждём 4 с, пока драйвер определит тип...")
        time.sleep(4)
    elif not sense(S):
        S.log("Гарнитура не определяется в разъёме 0x21. Вставьте EarPods и повторите.")
        return 1

    S.log("")
    for l in dmesg_lines():
        S.log("  dmesg: " + l)
    S.log("регистры сейчас (только чтение): " + S.regs_text())
    S.log("  (после загрузки без драйверного режима было 0x45=0xc089; CTIA = 0xd489, OMTP = 0xe489, TRS = 0xc489)")
    v45, v49, v5703 = S.cr(0x45), S.cr(0x49), S.cr(0x03, 0x57)
    kind = {0xD489: "CTIA", 0xE489: "OMTP", 0xC489: "TRS (наушники без микрофона)", 0xC089: "TRS, как оставил BIOS (режим драйвера не применён)",
            0xD089: "режим 'unplugged/проверка типа' (детект не завершён?)"}.get(v45, "нестандартное значение")
    S.log(f"  по coef 0x45 = 0x{v45:04x}: {kind}")
    if v49 == 0x0149 and v5703 == 0x0DA3:
        S.log("  0x49=0x0149 и 0x57/03=0x0da3 - следы работы alc_determine_headset_type (автоопределение типа отработало)")

    src = S.find_source()
    if not src:
        S.log("!!! источник не выбран однозначно, запустите: sudo SRC=<node.name> ./headset-mic-check.py")
        return 1
    S.log(f"источник записи: {src}")

    wav = f"/tmp/hs-check-{int(time.time())}.wav"
    open(wav, "w").close()
    os.chmod(wav, 0o666)
    total = hf.LEAD + hf.RUN_LEN + 2
    print("\nРуки не на кнопках пульта. Микрофон EarPods у рта (~5-10 см).")
    input("Нажмите Enter, когда готовы... ")
    S.start_recording(src, total, wav)
    time.sleep(hf.LEAD)
    t_run = S.now()
    hf.cue("МОЛЧИТЕ...")
    while S.now() - t_run < hf.SPEECH_CUE:
        time.sleep(0.05)
    hf.cue(">>> ГОВОРИТЕ (считайте вслух) <<<", bell=True)
    while S.now() - t_run < hf.RUN_LEN:
        time.sleep(0.05)
    S.proc.wait(timeout=total + 20)

    w = wave.open(wav, "rb")
    rate, nfr = w.getframerate(), w.getnframes()
    a = array.array("h")
    a.frombytes(w.readframes(nfr))
    w.close()
    shift = max(0.0, total - nfr / rate)
    m = hf.run_metrics(a, rate, t_run, shift)
    S.log("")
    S.log("регистры после записи (только чтение): " + S.regs_text())
    for l in dmesg_lines():
        if "iPhone-style" in l:
            S.log("  вердикт автоопределения ядра: " + l)
    if not m:
        S.log("!!! замер не удался")
        return 1
    S.log(f"тишина p90 {m['sil_p90']:.1f} dBFS   речь p90 {m['sp_p90']:.1f} dBFS   SNR {m['snr']:.1f} дБ   пик {m['peak']}")
    ok = m["snr"] >= hf.VOICE_SNR_DB
    S.log(f"РЕЗУЛЬТАТ: {'ГОЛОС ЕСТЬ' if ok else 'ГОЛОСА НЕТ'} (порог {hf.VOICE_SNR_DB:.0f} дБ), режим honor_dra_mic={val}"
          f"{', горячая вставка' if hotplug else ', холодный старт'}")
    if m["peak"] >= 32767:
        S.log("(пик упирается в 32767: клиппинг из-за Mic Boost 30 дБ; в ядре это не чинится, снижайте Mic Boost/усиление)")
    outdir = os.path.join(HERE, "runs")
    os.makedirs(outdir, exist_ok=True)
    name = os.path.join(outdir, f"headset-check-mode{val}-{'hot' if hotplug else 'cold'}-{time.strftime('%Y%m%d-%H%M%S')}.txt")
    with open(name, "w") as f:
        f.write("\n".join(S.log_lines) + "\n")
    subprocess.run(["chown", "-R", f"{S.user}:", outdir])
    os.remove(wav)
    S.log(f"\nлог: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
