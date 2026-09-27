#!/usr/bin/env bash
# Enables the 4 woofers of HONOR MagicBook Pro 16 2024 (DRA-XX) on any Linux distribution.
#  * with DKMS (Ubuntu, Debian, Fedora, ALT, Arch...): registers a DKMS package -> auto-rebuild on kernel updates
#  * without DKMS: builds and installs the module for the running kernel (re-run after kernel updates)
# Secure Boot: the module is signed with a MOK key (DKMS key or our own), enrollment is requested once.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG=honor-dra-fix; VER=2.0; KREL="$(uname -r)"
FORCE=0; SIGN_MODE=auto   # auto | yes | no
for a in "$@"; do case "$a" in
  --force) FORCE=1;; --sign) SIGN_MODE=yes;; --no-sign) SIGN_MODE=no;;
  -h|--help) echo "Usage: $0 [--force] [--sign|--no-sign]"; exit 0;;
  *) echo "Unknown option $a"; exit 1;; esac; done

# Secure Boot state: enabled | disabled | unknown (legacy BIOS / no mokutil)
sb_state() {
  local out
  if command -v mokutil >/dev/null; then
    out=$(mokutil --sb-state 2>&1 || true)
    case "$out" in *"SecureBoot enabled"*) echo enabled; return;; *"SecureBoot disabled"*) echo disabled; return;; esac
  fi
  local v; v=$(ls /sys/firmware/efi/efivars/SecureBoot-* 2>/dev/null | head -1)
  if [ -n "$v" ]; then [ "$(od -An -t u1 -j4 -N1 "$v" | tr -d ' ')" = 1 ] && echo enabled || echo disabled
  else echo unknown; fi
}
SB=$(sb_state)
case "$SIGN_MODE:$SB" in
  auto:enabled) SIGN=1; echo "Secure Boot is ON: the module will be signed (required, otherwise it will not load).";;
  no:enabled)   echo "Secure Boot is ON: an unsigned module would be rejected by the kernel. Use --sign or disable Secure Boot."; exit 1;;
  yes:*)        SIGN=1;;
  no:*)         SIGN=0;;
  auto:*)
    SIGN=0
    if [ -t 0 ]; then
      read -r -p "Secure Boot is $SB. Sign the module anyway (only needed if you plan to turn Secure Boot on)? [y/N] " a
      case "$a" in y|Y) SIGN=1;; esac
    fi;;
esac

sub=$(cat /sys/class/sound/hwC0D0/subsystem_id 2>/dev/null || true)
vid=$(cat /sys/class/sound/hwC0D0/vendor_id 2>/dev/null || true)
if [ $FORCE -eq 0 ] && { [ "$sub" != "0x1ee7204e" ] || [ "$vid" != "0x10ec0256" ]; }; then
  echo "Codec is vendor=$vid subsystem=$sub, expected ALC256 1ee7:204e (HONOR DRA-XX). Use --force to override."; exit 1
fi
for t in python3 make git; do command -v $t >/dev/null || { echo "Missing tool: $t"; exit 1; }; done
[ -f "/lib/modules/$KREL/build/Makefile" ] || {
  echo "Kernel headers for $KREL are missing. Install them first, e.g.:"
  echo "  Ubuntu/Debian: sudo apt install linux-headers-$KREL build-essential"
  echo "  ALT Linux:     sudo apt-get install kernel-headers-modules-\$(uname -r | sed 's/^.*-\([a-z]*-def\)-.*/\1/') gcc make"
  echo "  Fedora:        sudo dnf install kernel-devel-$KREL gcc make"
  echo "  Arch:          sudo pacman -S linux-headers base-devel"
  exit 1; }

# migrate from the old Ubuntu-only package
sudo dkms remove honor-dra-xx-audio/1.0 --all >/dev/null 2>&1 || true
sudo rm -rf /usr/src/honor-dra-xx-audio-1.0
sudo rm -f /etc/modprobe.d/honor-woofers-test.conf /etc/modprobe.d/honor-woofers.conf /lib/firmware/hda-jack-retask.fw

KEYPUB=""; KEYPRIV=""
if command -v dkms >/dev/null; then
  echo "== DKMS mode"
  sudo dkms remove "$PKG/$VER" --all >/dev/null 2>&1 || true
  sudo rm -rf "/usr/src/$PKG-$VER"; sudo mkdir -p "/usr/src/$PKG-$VER"
  sudo cp "$HERE/build.sh" "$HERE/honor_dra_fix.py" "$HERE/dkms.conf" "/usr/src/$PKG-$VER/"
  sudo dkms install "$PKG/$VER" -k "$KREL"
  for k in /var/lib/dkms/mok.pub /var/lib/shim-signed/mok/MOK.der; do [ -f "$k" ] && { KEYPUB=$k; break; }; done
else
  echo "== Manual mode (no DKMS: re-run this script after every kernel update)"
  "$HERE/build.sh" "$KREL" "$HERE/out/$KREL"
  KO=$(ls "$HERE/out/$KREL"/*.ko); KB=/lib/modules/$KREL/build
  if [ "$SIGN" = 1 ]; then
    KEYDIR=/var/lib/$PKG; KEYPRIV=$KEYDIR/MOK.priv; KEYPUB=$KEYDIR/MOK.der
    if [ ! -f "$KEYPRIV" ]; then
      sudo mkdir -p "$KEYDIR"
      sudo openssl req -new -x509 -newkey rsa:2048 -nodes -days 36500 -subj "/CN=$PKG module signing/" \
        -outform DER -keyout "$KEYPRIV" -out "$KEYPUB" 2>/dev/null
    fi
    HASH=$(grep '^CONFIG_MODULE_SIG_HASH=' "$KB/.config" | cut -d'"' -f2); HASH=${HASH:-sha256}
    SIGNTOOL=""; for s in "$KB/scripts/sign-file" /usr/lib/linux-kbuild-*/scripts/sign-file; do [ -x "$s" ] && { SIGNTOOL=$s; break; }; done
    if [ -n "$SIGNTOOL" ]; then sudo "$SIGNTOOL" "$HASH" "$KEYPRIV" "$KEYPUB" "$KO"
    elif command -v kmodsign >/dev/null; then sudo kmodsign "$HASH" "$KEYPRIV" "$KEYPUB" "$KO"
    else echo "WARNING: no sign-file tool found, module left unsigned"; fi
  fi
  sudo install -D -m644 "$KO" "/lib/modules/$KREL/updates/$PKG/$(basename "$KO")"
fi

MOD=$(basename "$(ls /lib/modules/"$KREL"/updates/*/snd-hda-codec-{alc269,realtek}.ko* 2>/dev/null | head -1)" | sed 's/\.ko.*//')
[ -n "$MOD" ] && echo "override $MOD * updates" | sudo tee /etc/depmod.d/$PKG.conf >/dev/null
sudo depmod -a "$KREL"
if command -v update-initramfs >/dev/null; then sudo update-initramfs -u -k "$KREL"
elif command -v dracut >/dev/null; then sudo dracut -f --kver "$KREL"
elif command -v make-initrd >/dev/null; then sudo make-initrd -k "$KREL"; fi
echo "Installed: $(modinfo -k "$KREL" -n "$MOD" 2>/dev/null)"

key_enrolled() { local out; out=$(mokutil --test-key "$1" 2>&1 || true); case "$out" in *"already enrolled"*) return 0;; *) return 1;; esac; }
if [ "$SIGN" = 1 ] && [ -n "$KEYPUB" ] && command -v mokutil >/dev/null; then
  if key_enrolled "$KEYPUB"; then
    echo "Signing key is already enrolled - just reboot."
  else
    echo "Enroll the signing key once (choose a one-time password, latin letters/digits)."
    sudo mokutil --import "$KEYPUB"
    echo "Reboot -> MOK Manager -> Enroll MOK -> Continue -> Yes -> password -> Reboot."
  fi
elif [ "$SIGN" = 1 ] && [ -z "$KEYPUB" ]; then
  echo "WARNING: no signing key found (DKMS did not create one). With Secure Boot on the module will not load."
else
  echo "Reboot to activate."
fi
