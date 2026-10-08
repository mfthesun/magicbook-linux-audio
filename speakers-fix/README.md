# HONOR MagicBook Pro 16 2024 (DRA-XX): все динамики и микрофон гарнитуры в Linux

**EN:** On the DRA-XX (ALC256, SSID `1ee7:204e`) the BIOS leaves the tweeter pin `0x14` (top speakers, next to the keyboard) and the headset-mic pin `0x19` unconfigured: only the bottom speakers play and the microphone of a wired headset is invisible to the system. This fix configures `0x14` as a speaker and `0x19` as a headset microphone (`0x03a1113c`, the value used by the HONOR MRB-XXX M1020 and VAIO quirks), and enables the kernel's headset mode (CTIA/OMTP auto-detection) for the combo jack, which is what actually connects the microphone to the codec (the BIOS leaves `coef 0x45` in the TRS state). Both changes are accepted upstream. The DKMS build also contains a DAC override for pin `0x1b` from the first upstream patch; it turned out to change nothing and has been dropped upstream (commit `5cc1749b5`) (`honor_dra_share_dac=0` gives the same result). `./install.sh` builds the patched Realtek HDA codec module for the running kernel on any distribution (kernel sources are fetched to match; both the ≥ 6.17 and older source layouts are supported), registers it with DKMS when available and signs it for Secure Boot. `./uninstall.sh` reverts. Upstream patches: `patch/`.

## Проблема

Кодек Realtek ALC256 (подсистема `1ee7:204e`), две пары динамиков:

| Пин | Динамики | BIOS | В штатном Linux |
|---|---|---|---|
| `0x1b` | нижние (вуферы: низкие и средние частоты) | `0x90170110`, настроен | играют |
| `0x14` | верхние, по бокам клавиатуры (твитеры) | `0x411111f0`, не подключён | молчат |

Исправление: объявить `0x14` внутренним динамиком (`0x90170111`). После этого обе пары играют один стереопоток.

Роли пар проверены 05.10.2026 замером встроенными микрофонами, по одному включённому пину: на 1 кГц верхние на 33–36 дБ тише нижних, на 6 кГц обе пары громкие. Скрипт замера: `speaker-measure.py` (запуск от обычного пользователя, наушники выдернуты, EasyEffects закрыт; логи в `runs/`).

> **Поправка.** В первом апстрим-патче и в прежних версиях этого README роли были перепутаны: `0x14` называли вуферами («bass speakers»), `0x1b` — твитерами. Имя регулятора «Bass Speaker» в ALSA даёт общий парсер ядра второму динамику, физического смысла у него нет: этот регулятор управляет верхними динамиками.

**Привязка к DAC.** Первый патч дополнительно ограничивал пин `0x1b` DAC `0x02` (на этот DAC может работать только `0x14`), чтобы обе пары гарантированно получали один стереопоток. Оказалось, что это ничего не меняет: без ограничения `0x1b` и так подключён к DAC `0x02`, маршрут в кодеке одинаковый, звук тоже (проверено без наушников, с наушниками, с гарнитурой, после сна, замером микрофоном). Исправление принято в ядро 06.10.2026 (коммит `5cc1749b5` в `for-next`). В DKMS-сборке ограничение пока осталось и выключается параметром `honor_dra_share_dac=0` (`set-dac-share.sh`); результат одинаковый в обоих режимах.

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

Сравнить с верхними динамиками и без них, пока играет музыка (регулятор называется «Bass Speaker», но управляет верхними твитерами; разница слышна на высоких частотах):

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

Одного объявления пина `0x19` мало: BIOS оставляет аналоговый ключ разъёма (`coef 0x45 = 0xc089`) в режиме «TRS», и микрофон гарнитуры отрезан. Измерено на железе (02.10.2026, EarPods, CTIA): `coef 0x45 = 0xd489` даёт голос (разница речь/тишина 33-36 дБ), `0xc489` (TRS) даёт ноль, а `coef 0x1b` на результат не влияет. Режим выбирается параметром модуля `honor_dra_mic` (по умолчанию 4). Режимы 1 и 4 проверены на железе 03.10.2026: холодный старт и горячая вставка, SNR 29-34 дБ; режим 4 без привязки к DAC — 05.10.2026, SNR 29.7 дБ:

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

| Файл в `patch/` | Что | Статус |
|---|---|---|
| `0001-...-Enable-bass-speakers-...patch` | пин `0x14` (верхние динамики) + привязка `0x1b` к DAC `0x02` | принят 28.09.2026, коммит `1e3e378d63be` в `for-next` дерева sound. Заголовок и описание ролей в нём неверны (см. поправку выше) |
| `0002-...-Enable-headset-mic-...patch` | пин `0x19` + headset mode | принят 04.10.2026 (v2 с тегом `Fixes:`), коммит `af53cdc10` в `for-next` |
| `0003-...-Drop-unneeded-DAC-override-...patch` | убирает привязку к DAC, исправляет комментарий к пину `0x14` | принят 06.10.2026, коммит `5cc1749b5` в `for-next` |

Мейнтейнер — Takashi Iwai, рассылка linux-sound. В ядре дистрибутива исправления появятся с ближайшими релизами; после этого выполните `./uninstall.sh`.

## Файлы

| Файл | Назначение |
|---|---|
| `honor_dra_fix.py` | вносит исправление в исходник драйвера (любой версии ядра) |
| `build.sh` | скачивает исходники под ядро, патчит, собирает модуль |
| `install.sh` / `uninstall.sh` | установка (DKMS или вручную) и откат |
| `dkms.conf` | описание DKMS-пакета `honor-dra-fix/2.2` |
| `set-mic-mode.sh` | выбор режима микрофона гарнитуры (`honor_dra_mic`) |
| `speaker-measure.py` | объективный замер динамиков встроенными микрофонами: тоны 80 Гц / 1 кГц / 6 кГц, по одной паре и обе |
| `set-dac-share.sh` | тестовый переключатель привязки `0x1b` к DAC `0x02` (`honor_dra_share_dac`); на звук не влияет |
| `patch/` | патчи, отправленные в ядро |
