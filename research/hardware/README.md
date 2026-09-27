# Аппаратные данные HONOR MagicBook Pro 16 2024 (DRA-XX)

- DMI: `HONOR` / `DRA-XX`, плата `DRA_XX-M1020-DRA_XX_PCB`, BIOS 1.14, Intel Core Ultra 5 125H (Meteor Lake-P).
- Звук: SOF (`sof-audio-pci-intel-mtl`), топология `sof-hda-generic-2ch.tplg`, NHLT: BT на SSP2 + 2 DMIC.
- Кодек Realtek ALC256, `0x10ec0256`, подсистема `0x1ee7204e`.

| Пин | BIOS Pin Default | Что это | Связи |
|---|---|---|---|
| 0x14 | 0x411111f0 (не подключён) | **4 вуфера** | только DAC 0x02 |
| 0x1b | 0x90170110 | 2 твитера | DAC 0x02 / 0x03 |
| 0x21 | 0x04211020 | разъём наушников | DAC 0x02 / 0x03 |
| 0x19 | 0x411111f0 | микрофон гарнитуры (?) — не проверен | |

- ACPI: блоки `10EC1308` (RT1308) и `INT34C2` в DSDT — шаблон эталонного BIOS Intel, включаются только при `I2SC = 1/2`; у Honor `I2SC = 0`, реального усилителя нет.
- `TXNW3643` — вспышка камеры (LM3643), к звуку не относится.

> Полные дампы (`alsa-info.txt`, `dmesg.txt`, `dsdt.dsl`, `nhlt.bin`) храните в `raw/` (исключено из git).
> **Не публикуйте `msdm.dat`/`acpi.dat`**: таблица MSDM содержит ключ лицензии Windows.
