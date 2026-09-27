#!/usr/bin/env bash
set -uo pipefail
PKG=honor-dra-fix; VER=2.0; KREL="$(uname -r)"
command -v dkms >/dev/null && { sudo dkms remove "$PKG/$VER" --all; sudo dkms remove honor-dra-xx-audio/1.0 --all; } 2>/dev/null
sudo rm -rf "/usr/src/$PKG-$VER" /usr/src/honor-dra-xx-audio-1.0 /lib/modules/*/updates/$PKG /etc/depmod.d/$PKG.conf
sudo depmod -a "$KREL"
if command -v update-initramfs >/dev/null; then sudo update-initramfs -u
elif command -v dracut >/dev/null; then sudo dracut -f
elif command -v make-initrd >/dev/null; then sudo make-initrd; fi
echo "Removed. Reboot to return to the stock driver."
