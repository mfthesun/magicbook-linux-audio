# HONOR MagicBook Pro 16 2024 (DRA-XX): все 6 динамиков в Linux

**EN:** On the DRA-XX (ALC256, SSID `1ee7:204e`) the BIOS leaves the woofer pin `0x14` unconfigured, so only the two tweeters play. This fix configures `0x14` as a speaker and routes the tweeter pin `0x1b` to the same DAC (`0x02`), so all six speakers play the stereo stream, as on Windows. `./install.sh` builds the patched Realtek HDA codec module for the running kernel on any distribution (kernel sources are fetched to match; both the ≥ 6.17 and older source layouts are supported), registers it with DKMS when available and signs it for Secure Boot. `./uninstall.sh` reverts. Upstream submission: `patch/`.

## Проблема

Кодек Realtek ALC256 (подсистема `1ee7:204e`). 2 твитера висят на пине `0x1b`, 4 вуфера — на пине `0x14`, который BIOS оставляет неподключённым (`0x411111f0`). Поэтому в Linux играют только твитеры.

Пин `0x14` может брать звук только из DAC `0x02`. Исправление: объявить `0x14` динамиком и посадить `0x1b` на тот же DAC, как в Windows: обе пары динамиков получают одно стерео с общей громкостью. Появляется регулятор «Bass Speaker».

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

## Апстрим

`patch/0001-ALSA-hda-realtek-Enable-bass-speakers-on-HONOR-Magic.patch` — патч для основной ветки ядра (рассылка linux-sound, мейнтейнер Takashi Iwai). Когда он попадёт в ядро вашего дистрибутива, выполните `./uninstall.sh`.

## Файлы

| Файл | Назначение |
|---|---|
| `honor_dra_fix.py` | вносит исправление в исходник драйвера (любой версии ядра) |
| `build.sh` | скачивает исходники под ядро, патчит, собирает модуль |
| `install.sh` / `uninstall.sh` | установка (DKMS или вручную) и откат |
| `dkms.conf` | описание DKMS-пакета `honor-dra-fix/2.0` |
| `patch/` | патч для отправки в ядро |
