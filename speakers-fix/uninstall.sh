#!/usr/bin/env bash
set -uo pipefail
PKG=honor-dra-fix; KREL="$(uname -r)"
if command -v dkms >/dev/null; then
  # удалить ВСЕ версии пакета (2.0, 2.1, 2.2...), иначе DKMS пересоберёт модуль при обновлении ядра
  for v in $(dkms status "$PKG" 2>/dev/null | sed -n "s|^$PKG/\([^,]*\),.*|\1|p" | sort -u); do
    sudo dkms remove "$PKG/$v" --all >/dev/null 2>&1
  done
  sudo dkms remove honor-dra-xx-audio/1.0 --all >/dev/null 2>&1
fi
sudo rm -rf /usr/src/"$PKG"-* /usr/src/honor-dra-xx-audio-1.0 /lib/modules/*/updates/$PKG /etc/depmod.d/$PKG.conf /etc/modprobe.d/honor-dra-mic.conf
sudo depmod -a "$KREL"
if command -v update-initramfs >/dev/null; then sudo update-initramfs -u
elif command -v dracut >/dev/null; then sudo dracut -f
elif command -v make-initrd >/dev/null; then sudo make-initrd; fi
echo "Removed. Reboot to return to the stock driver."
