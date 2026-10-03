# HONOR MagicBook Pro 16 2024 (DRA-XX): все 6 динамиков и микрофон гарнитуры в Linux

**EN:** On the DRA-XX (ALC256, SSID `1ee7:204e`) the BIOS leaves the woofer pin `0x14` and the headset-mic pin `0x19` unconfigured: only the two tweeters play and the microphone of a wired headset is invisible to the system. This fix configures `0x14` as a speaker, restricts the tweeter pin `0x1b` to DAC `0x02` (the only DAC the woofer pin `0x14` can use), so all speakers share one stereo stream, and configures `0x19` as a headset microphone (`0x03a1113c`, the value used by the HONOR MRB-XXX M1020 and VAIO quirks) and enables the kernel's headset mode (CTIA/OMTP auto-detection) for the combo jack, which is what actually connects the microphone to the codec (the BIOS leaves `coef 0x45` in the TRS state). The behaviour is selectable by the `honor_dra_mic` module parameter, see `set-mic-mode.sh`. `./install.sh` builds the patched Realtek HDA codec module for the running kernel on any distribution (kernel sources are fetched to match; both the ≥ 6.17 and older source layouts are supported), registers it with DKMS when available and signs it for Secure Boot. `./uninstall.sh` reverts. Upstream submission: `patch/`.

## Проблема

Кодек Realtek ALC256 (подсистема `1ee7:204e`). 2 твитера висят на пине `0x1b`, 4 вуфера — на пине `0x14`, который BIOS оставляет неподключённым (`0x411111f0`). Поэтому в Linux играют только твитеры.

Пин `0x14` может брать звук только из DAC `0x02`. Исправление: объявить `0x14` динамиком (в патче также ограничен выбор DAC для `0x1b`, он остаётся на `0x02`). В итоге обе пары динамиков получают один стереопоток с общей громкостью (регулятор «Speaker»); переключатель «Bass Speaker» появляется отдельно. Как маршрутизация устроена в Windows-драйвере, неизвестно: в INF-файлах Honor её нет, она внутри закрытых `RTKVHD64.sys` и `RTAIODAT.DAT`. Ограничение DAC для `0x1b` на слух ничего не меняет (проверено 03.10.2026, см. `../headset-mic/README.md`); вуферы оживляет именно переопределение пина `0x14`.

Вторая проблема того же кодека: пин `0x19` — микрофонный контакт разъёма 3,5 мм — BIOS тоже оставляет отключённым (`0x411111f0`). Поэтому микрофон проводной гарнитуры система не видит вообще: аналоговый вход пишет цифровую тишину, источников «Headset Mic» не появляется. Исправление: объявить `0x19` входом микрофона гарнитуры — значение `0x03a1113c` («headset mic, without its own jack detect»), то же, что применяют фиксапы HONOR MRB-XXX M1020 и VAIO. Пин `0x1a` (второй вход) не трогаем: данных о том, что он распаян на этой плате, нет.

## Установка (любой дистрибутив)

Нужны: заголовки ядра, `gcc`/`make`, `python3`, `git`. Если есть `dkms`, модуль будет пересобираться сам при обновлении ядра; без DKMS — перезапускайте `install.sh` после каждого обновления ядра.

```bash
./install.sh      # сборка, установка, подпись для Secure Boot
./uninstall.sh    # откат к штатному драйверу
```

- Исходники драйвера берутся под версию вашего ядра: из пакета исходников дистрибутива (`/usr/src/linux-source-*`), иначе из git-зеркала stable-ветки kernel.org (`git.kernel.org` → запасной `github.com/gregkh/linux`).
- Поддерживаются обе раскладки исходников: Linux ≥ 6.17 (`sound/hda/codecs/realtek/alc269.c`, модуль `snd-hda-codec-alc269`) и < 6.17 (`sound/pci/hda/patch_realtek.c`, модуль `snd-hda-codec-realtek`).
- Если ядро уже содержит исправление (строка `0x1ee7, 0x204e` в таблице), `build.sh` сообщит, что модуль не нужен.
- Secure Boot определяется автоматически. Если он включён, модуль обязательно подписывается (ключом DKMS, а без DKMS — собственным ключом `/var/lib/honor-dra-fix/`), ключ регистрируется один раз через MOK Manager. Если выключен — скрипт спросит, подписывать ли модуль «на будущее». Принудительно: `./install.sh --sign` или `--no-sign`.
- Проверено: Ubuntu 26.04, ядро 7.0.0-34 (upstream 7.0.14), SOF, Secure Boot. Установка на ALT Linux и другие дистрибутивы не проверялась, при проблеме пришлите вывод `install.sh`.

## Проверка после перезагрузки

```bash
modinfo -n snd_hda_codec_alc269          # путь должен вести в .../updates/...
amixer -c0 scontrols | grep -i "bass speaker"
```

Сравнить на слух с вуферами и без них, пока играет музыка:

```bash
amixer -c0 sset "Bass Speaker" off; sleep 5; amixer -c0 sset "Bass Speaker" on
```

Микрофон гарнитуры (гарнитура вставлена в разъём):

```bash
arecord -l                                   # должна появиться карта с аналоговым входом
amixer -c0 scontrols | grep -i headset       # вход микрофона гарнитуры
arecord -D hw:0,0 -f S16_LE -r 48000 -c 2 -d 5 /tmp/mic.wav   # говорите в микрофон
```

Одна тонкость: EasyEffects и PipeWire держат устройства открытыми, поэтому во время записи остановите пресет EasyEffects, если захват не открывается.

## Режимы микрофона гарнитуры (DKMS 2.2)

Одного объявления пина `0x19` мало: BIOS оставляет аналоговый ключ разъёма (`coef 0x45 = 0xc089`) в режиме «TRS», и микрофон гарнитуры отрезан. Измерено на железе (02.10.2026, EarPods, CTIA): `coef 0x45 = 0xd489` даёт голос (разница речь/тишина 33-36 дБ), `0xc489` (TRS) даёт ноль, а `coef 0x1b` на результат не влияет. Режим выбирается параметром модуля `honor_dra_mic` (по умолчанию 4). Режимы 1 и 4 проверены на железе 03.10.2026: холодный старт и горячая вставка, SNR 29-34 дБ:

| Значение | Что делает |
|---|---|
| `0` | только пины; микрофон не работает (для сравнения) |
| `1` | штатный headset mode ядра с подстраховкой по пину `0x19` (парсер сам выставляет пин, подстраховка не нужна) |
| `2` | принудительно CTIA при инициализации (`0x45=0xd489`, `0x1b=0x0e6b`); запасной вариант |
| `3` | как фикс HONOR BRB-X (аппаратное автопереключение через `coef 0x45`) |
| `4` | штатный headset mode ядра: тип гарнитуры (CTIA/OMTP) определяется при каждом событии джека; тот же код, что в апстрим-патче (по умолчанию) |

```bash
./set-mic-mode.sh 1        # выбрать режим (после этого перезагрузка)
./set-mic-mode.sh --status # что в конфиге и что загружено
sudo dmesg | grep "HONOR DRA-XX"   # режим и headset_mic_pin, которые увидел драйвер
```

## Апстрим

`patch/0001-ALSA-hda-realtek-Enable-bass-speakers-on-HONOR-Magic.patch` — патч вуферов для основной ветки ядра (рассылка linux-sound, мейнтейнер Takashi Iwai). **Принят 28.09.2026 в ветку `for-next` дерева sound (коммит `1e3e378d63be`)**; в ядре дистрибутива появится с ближайшим релизом.

`patch/0002-...-headset-mic-...patch` — follow-up с микрофоном гарнитуры, отправляется поверх уже принятого патча. Когда оба попадут в ядро вашего дистрибутива, выполните `./uninstall.sh`.

## Файлы

| Файл | Назначение |
|---|---|
| `honor_dra_fix.py` | вносит исправление в исходник драйвера (любой версии ядра) |
| `build.sh` | скачивает исходники под ядро, патчит, собирает модуль |
| `install.sh` / `uninstall.sh` | установка (DKMS или вручную) и откат |
| `dkms.conf` | описание DKMS-пакета `honor-dra-fix/2.2` |
| `set-mic-mode.sh` | выбор режима микрофона гарнитуры (`honor_dra_mic`) |
| `patch/` | патч для отправки в ядро |
