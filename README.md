# MagicBook Linux Audio

**EN:** Linux audio for the HONOR MagicBook Pro 16 2024 (DRA-XX, Intel Meteor Lake, Realtek ALC256 `1ee7:204e`): a driver fix that enables the 4 woofers silent under Linux (DKMS, any distro, Secure Boot aware; [patch sent upstream](https://lore.kernel.org/all/20260927210455.13938-1-mfthesun@vivaldi.net/)), EasyEffects 8.x presets (factory speaker EQ extracted from the Windows driver, built-in mic, Sony WH-1000XM5 and Realme Buds Air 7 Pro via AutoEq) and notes on the Windows audio stack.

Звук в Linux на HONOR MagicBook Pro 16 2024 (DRA-XX) и пресеты EasyEffects.

| Папка | Что внутри |
|---|---|
| `speakers-fix/` | исправление драйвера для 4 вуферов ноутбука: установка через DKMS или вручную на любом дистрибутиве, поддержка Secure Boot, патч для ядра |
| `easyeffects-presets/` | пресеты EasyEffects 8.x: динамики ноутбука (заводской EQ Honor), встроенный микрофон, Sony WH-1000XM5, Realme Buds Air 7 Pro (AutoEQ) |
| `research/` | разбор Windows-драйвера Honor и аппаратные данные (сырые файлы — в `raw/`, не в git) |

Порядок: сначала `speakers-fix/install.sh`, затем `easyeffects-presets/install.sh`.

## Лицензии

- `speakers-fix/` — GPL-2.0 (код для ядра Linux).
- `easyeffects-presets/` — GPL-3.0 (использует многополосный компрессор из [GentleDynamics](https://github.com/droidwayin/GentleDynamics), GPL-3.0); коррекции наушников — из [AutoEq](https://github.com/jaakkopasanen/AutoEq) (MIT).
- `research/` — только собственные заметки и скрипты; файлы Windows-драйвера (Realtek, Honor, Awinic, DTS) не публикуются.
