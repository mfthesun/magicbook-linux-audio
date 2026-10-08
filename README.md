# MagicBook Linux Audio

**EN:** Linux audio for the HONOR MagicBook Pro 16 2024 (DRA-XX, Intel Meteor Lake, Realtek ALC256 `1ee7:204e`): a driver fix for the top speakers (tweeters) that stay silent under Linux and for the wired headset microphone (DKMS, any distro, Secure Boot aware; both fixes are accepted upstream, see below), EasyEffects 8.x presets (factory speaker EQ extracted from the Windows driver, built-in mic, Sony WH-1000XM5 and Realme Buds Air 7 Pro via AutoEq) and notes on the Windows audio stack.

Звук в Linux на HONOR MagicBook Pro 16 2024 (DRA-XX) и пресеты EasyEffects.

| Папка | Что внутри |
|---|---|
| `speakers-fix/` | исправление драйвера: верхние динамики (твитеры) и микрофон проводной гарнитуры; установка через DKMS или вручную на любом дистрибутиве, поддержка Secure Boot, патчи для ядра |
| `headset-mic/` | микрофон гарнитуры: причина, проверка, скрипты замеров |
| `easyeffects-presets/` | пресеты EasyEffects 8.x: динамики ноутбука (заводской EQ Honor), встроенный микрофон, Sony WH-1000XM5, Realme Buds Air 7 Pro (AutoEQ) |
| `research/` | разбор Windows-драйвера Honor и аппаратные данные (сырые файлы — в `raw/`, не в git) |

Порядок: сначала `speakers-fix/install.sh`, затем `easyeffects-presets/install.sh`.

## Статус в ядре Linux

| Патч | Статус |
|---|---|
| верхние динамики (пин `0x14`) | принят: коммит `1e3e378d63be` в `for-next` дерева sound, 28.09.2026 ([тред](https://lore.kernel.org/all/20260927210455.13938-1-mfthesun@vivaldi.net/)) |
| микрофон гарнитуры (пин `0x19` + headset mode) | принят: коммит `af53cdc10` в `for-next`, 04.10.2026 ([тред](https://lore.kernel.org/linux-sound/20261003133325.97507-1-mfthesun@vivaldi.net/)) |
| исправление первого патча: лишняя привязка к DAC, перепутанные роли динамиков | принят: коммит `5cc1749b5` в `for-next`, 06.10.2026 ([тред](https://lore.kernel.org/linux-sound/20261005203836.11074-1-mfthesun@vivaldi.net/)) |

Когда исправления попадут в ядро вашего дистрибутива, DKMS-модуль не нужен: `speakers-fix/uninstall.sh`.

## Лицензии

- `speakers-fix/` — GPL-2.0 (код для ядра Linux).
- `easyeffects-presets/` — GPL-3.0 (использует многополосный компрессор из [GentleDynamics](https://github.com/droidwayin/GentleDynamics), GPL-3.0); коррекции наушников — из [AutoEq](https://github.com/jaakkopasanen/AutoEq) (MIT).
- `research/` — только собственные заметки и скрипты; файлы Windows-драйвера (Realtek, Honor, Awinic, DTS) не публикуются.
