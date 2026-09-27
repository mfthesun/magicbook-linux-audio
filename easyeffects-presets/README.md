# Пресеты EasyEffects 8.x — Honor MagicBook Pro 16 (2024), Sony WH-1000XM5, Realme Buds Air 7 Pro

Формат пресетов проверен по исходникам EasyEffects **8.2.9** (последний релиз на 27.09.2026): ключи, названия режимов и диапазоны значений сверены с `*_preset.cpp` и `.kcfg` из репозитория wwmm/easyeffects. **EasyEffects 7.x эти файлы не загрузит** — форматы 7 и 8 несовместимы.

## Что внутри

| Пресет | Цепочка | Для чего |
|---|---|---|
| **Honor MagicBook Pro 16 Factory - Standard / Movie / Voice** | HPF 90 Гц 24 дБ/окт → заводской EQ из драйвера Honor → компрессор → Limiter | **основной вариант** для всех 6 динамиков после установки фикса |
| **Honor MagicBook Pro 16 Mic - Calls** (вход) | HPF 90 Гц → RNNoise → EQ (разборчивость) → компрессор → Limiter | встроенный микрофон: созвоны, пары |
| **Sony WH-1000XM5 - Music** | AutoEQ (oratory1990, цель Harman) → Limiter | эталонное звучание |
| **Sony WH-1000XM5 - Music (alt Rtings)** | AutoEQ (Rtings, B&K 5128) → Limiter | альтернативная коррекция по другому стенду — сравните с основной |
| **Sony WH-1000XM5 - Music+ GentleDynamics** | 18 Гц HPF → 8-полосный MBC GentleDynamics → AutoEQ → Limiter | «живее» и детальнее на тихой громкости |
| **Sony WH-1000XM5 - Movie** | компрессор диалогов → AutoEQ → Crossfeed → Limiter | фильмы: ровная громкость речи, меньше «звука внутри головы» |
| **Realme Buds Air 7 Pro - Music / Music+ / Movie (ANC on)** | то же, AutoEQ по замеру с ANC | с включённым шумодавом |
| **Realme Buds Air 7 Pro - Music / Music+ / Movie (ANC off)** | то же, AutoEQ по замеру без ANC | с выключенным шумодавом / прозрачностью |

Источники коррекции: AutoEq — `oratory1990/Sony WH-1000XM5`, `Rtings/Sony WH-1000XM5`, `Regan Cipher/realme Buds Air 7 Pro (ANC on|off)`. Предусилитель (Preamp) из AutoEq стоит в Input gain эквалайзера, фильтры — в режиме `APO (DR)`, как делает встроенный импорт EasyEffects.
MBC в «Music+» взят из [GentleDynamics](https://github.com/droidwayin/GentleDynamics) (GPL-3.0) и поставлен **перед** AutoEQ, как рекомендует автор.

**Про ANC у XM5.** В AutoEq есть только замеры XM5 в стандартном режиме (с шумоподавлением). У накладных XM5 разница ANC on/off в АЧХ заметно меньше, чем у внутриканальных, поэтому отдельного пресета «ANC off» нет — если без ANC покажется меньше баса, просто используйте «Music+».

## Установка (Ubuntu 26.04)

1. Проверьте версию: `easyeffects --version` (или `apt policy easyeffects`). Нужна **8.x**. Если в репозитории 7.x — поставьте Flatpak: `flatpak install flathub com.github.wwmm.easyeffects`.
2. Для полного набора плагинов: `sudo apt install lsp-plugins-lv2 calf-plugins zam-plugins mda-lv2` (в EE 8 большая часть эффектов уже встроена, но лишним не будет).
3. Распакуйте архив и запустите `./install.sh` — он скопирует пресеты (`output` и `input`) в папки EasyEffects (нативную и/или Flatpak). Можно и вручную: *Presets → Import*.
4. В настройках EasyEffects включите **Launch at startup / Background service**, иначе после закрытия окна обработка остановится.

## Автозагрузка по устройству

*Presets → Autoload*: привяжите «Honor … Factory - Standard» к встроенным динамикам, «Sony WH-1000XM5 - Music» — к XM5, «Realme … (ANC on)» — к Realme, а на вкладке Input — «Honor … Mic - Calls» к встроенному микрофону. Сценарии (Movie/Voice) переключайте вручную или через GNOME-расширение *EasyEffects Preset Selector*.

## Настройки самих устройств

- **Sony XM5**: в Sony Sound Connect выключите эквалайзер (Off/Flat), выключите DSEE Extreme и «Adaptive Sound Control» (он сам переключает ANC и сбивает сценарий). Кодек в Linux: в GNOME → Звук или `pactl` выберите профиль **LDAC** (A2DP); для созвонов — HFP/mSBC, AutoEQ в этом режиме смысла почти не имеет.
- **Realme Buds Air 7 Pro**: в Realme Link поставьте звуковой профиль по умолчанию (без баса/«Dynamic»), иначе коррекция наложится на заводской EQ. Кодек — LDAC, если PipeWire его предложит.
- Громкость: коррекция снижает общий уровень на 2–6 дБ (запас от клиппинга) — это нормально, прибавьте громкость в системе.

## Встроенный микрофон

- Пресет «Mic - Calls» — универсальная обработка для 2 цифровых микрофонов (DMIC, работают только с драйвером SOF).
- В SOF есть встроенное формирование луча: `alsamixer` → F6 → sof-hda-dsp → F4 → включите `Dmic0 Capture TDFB beam switch` — меньше шума сбоку.
- Уровень — регулятор `Dmic0` там же. В Windows за шумоподавление отвечает закрытый модуль Fortemedia; RNNoise в EasyEffects — его замена.

## Пресеты Honor Factory

Эквалайзер в пресетах «Honor MagicBook Pro 16 Factory» извлечён из Windows-драйвера Honor (конфиг Awinic SKTune), подробности — `../research/windows-driver/README.md`. Рассчитаны на работу всех 6 динамиков, то есть с установленным фиксом из `../speakers-fix/`. Если басы хрипят на громкости — поднимите частоту первой полосы (Hi-pass 90 Гц) до 110–120 Гц.

## Пересборка пресетов

`tools/gen.py` генерирует все JSON, `tools/validate.py` проверяет их по исходникам EasyEffects. Зависимости: склонируйте AutoEq, GentleDynamics и easyeffects в `tools/deps/` (или укажите `DEPS=`/`EE_SRC=`).
