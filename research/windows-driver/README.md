# Разбор Windows-драйвера Honor (RealtekAudio 6.0.9721.1)

Источник: honor.com/cn → «Загрузка драйверов», модель DRA-54, раздел «Звуковая карта», `RTKAudioUpdateAPO 6.0.9721.1_Firmware.zip` (608 МБ, 13.02.2026).
Распаковка: zip → NSIS `RealtekAudio_6.0.9721.1.exe` → NSIS внутри → `7z x` (549 файлов).

> Исходные файлы драйвера закрытые — храните их в `raw/` (исключено из git), не публикуйте.

## Что где

| Путь внутри пакета | Что это |
|---|---|
| `Realtek/Codec_9721.1/HDXHONOR.inf` | базовый драйвер Realtek, ID `SUBSYS_1EE7204E` |
| `Realtek/ExtRtk_9721.1/HDX_HonorExt_XPERI4_Awinic_Honor_FORTE.inf` | какие APO висят на каких выходах |
| `Realtek/Codec_9721.1/RTAIODAT.DAT` | 60 МБ, зашифрованные настройки Realtek (не разбирались) |
| `awinic/awinic/awinic_SKTune_config*.bin` | **настройки звука динамиков** — частично расшифрованы |
| `honorApo/honorApo/*.xml, *.bin` | Honor Histen/Xisten: пространственный звук, HRTF, реверберация (массивы параметров без описания) |
| `DTS/DTS_Honor_EXT/Honor1EE7204E/` | DTS APO4 — только для наушников |
| `FM/` | Fortemedia: шумодав и формирование луча для микрофонов (модели GNA/OpenVINO) |

## Цепочки обработки (из Ext-INF)

- Динамики (`SysCustomizedFx_6`): Mode Effect = Honor Pre APO, Endpoint Effect = **Awinic SKTune MEC APO**.
- Наушники (`SysCustomizedHpFx_6`): DTS (Xperi) SFX/MFX/EFX + Honor Post APO.
- Микрофоны: Realtek SFX + Fortemedia MFX/EFX.

## Awinic SKTune (`awinic_SKTune_config.bin`)

- Заголовок: проект «Darwin» (= DRA-XX), 10 профилей по 6496 байт с 0x410: Bypass, Game, Moive, Music, SpaceDefaut, SpaceMoive, SpaceVedio, SpaceVoice, Standard, Voice.
- Запись фильтра — 24 байта: `int32 enable, int32 type, float Fc, float gain_dB, float Q, int32 slope(12/24)`.
  Типы: 0 = HPF, 1 = LPF, 2 = Peak, 3 = High-shelf (предположительно), 4 = Low-shelf (?), 5 = без усиления (all-pass/фаза?), 7 = ? (350 Гц).
- Разбор: `python3 awinic_sktune_parse.py Standard [путь к .bin]`.
- Секция B (смещение ~6008, работает даже в Bypass) — коррекция динамиков: Peak 500 −5 Q6, 880 −3 Q6, 1000 −3 Q6, 2200 −4 Q6, 9000 +4 Q2, shelf 13 кГц −6.
- Секция A (~3404, зависит от режима): Standard — HPF 90 Гц 24 дБ/окт, Peak 200 −3 Q6, 450 −2 Q1, 500 −2.5 Q6, 600 −4 Q15, 4800 −6 Q6; Movie и Voice — см. `easyeffects-presets/tools/gen.py`.
- Не расшифровано: таблицы DRC (пороги −15…−120 дБ, ~4380–5300), виртуальный бас (HPF 50/60, LPF 80, Peak 110/130 — ~1776), тип 7, секции 2036–3016.

## Идеи на будущее

- Дорасшифровать DRC и виртуальный бас по структуре записей.
- Чёрный ящик: прогнать APO-DLL под Wine через свой хост (тестовые сигналы → АЧХ, поведение DRC) или записать выход в Windows.
- Honor Histen: параметры — безымянные массивы, без кода почти не разобрать.
