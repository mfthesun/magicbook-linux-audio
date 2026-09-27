#!/usr/bin/env bash
# Fetch the HDA driver sources matching a kernel, apply the HONOR DRA-XX fix, build the module.
# Distro-independent: needs only the kernel headers/build dir, python3, make, gcc (or clang), git or a source tarball.
# Usage: build.sh [KERNEL_RELEASE] [OUT_DIR]
# Env:   KBUILD_DIR   - kernel build dir (default /lib/modules/$KREL/build)
#        SRC_TARBALL  - kernel source tarball to take sound/ from (optional)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KREL="${1:-$(uname -r)}"
OUT="${2:-$HERE/out/$KREL}"
KB="${KBUILD_DIR:-/lib/modules/$KREL/build}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

[ -f "$KB/Makefile" ] || { echo "Kernel headers not found: $KB (install your distro's headers/devel package for $KREL)"; exit 1; }
KV="$(make -s -C "$KB" kernelversion 2>/dev/null | tail -1)"          # e.g. 7.0.12
MAJ="${KV%%.*}"; MIN="$(echo "$KV" | cut -d. -f2)"; SUB="$(echo "$KV" | cut -d. -f3)"
if [ "$MAJ" -gt 6 ] || { [ "$MAJ" -eq 6 ] && [ "$MIN" -ge 17 ]; }; then
  SUBDIR=sound/hda; MODDIR=sound/hda/codecs/realtek; SRCFILE=alc269.c; MOD=snd-hda-codec-alc269
else
  SUBDIR=sound/pci/hda; MODDIR=sound/pci/hda; SRCFILE=patch_realtek.c; MOD=snd-hda-codec-realtek
fi
echo "kernel $KREL (upstream $KV), module $MOD"

# 1) sources: distro tarball -> /usr/src tree -> kernel.org stable via git
got=""
for tb in "${SRC_TARBALL:-}" /usr/src/linux-source-"$MAJ.$MIN"*/linux-source-*.tar.* /usr/src/linux-source-"$MAJ.$MIN"*.tar.*; do
  [ -n "$tb" ] && [ -f "$tb" ] || continue
  echo "sources: $tb"
  tar -xf "$tb" -C "$WORK" --wildcards "*/$SUBDIR/*" 2>/dev/null && got=$(ls -d "$WORK"/*/ | head -1) && break
done
if [ -z "$got" ] && [ -d "/usr/src/linux-$KREL/$SUBDIR" ]; then got="/usr/src/linux-$KREL/"; echo "sources: $got"; fi
if [ -z "$got" ]; then
  TAG="v$MAJ.$MIN"; [ -n "$SUB" ] && [ "$SUB" != 0 ] && TAG="v$KV"
  for url in https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git https://github.com/gregkh/linux.git; do
    echo "sources: $url ($TAG)"
    if git -c advice.detachedHead=false clone -q --depth 1 --filter=blob:none --sparse -b "$TAG" "$url" "$WORK/git" 2>/dev/null; then
      git -C "$WORK/git" sparse-checkout set "$SUBDIR" && got="$WORK/git/" && break
    fi
    rm -rf "$WORK/git"
  done
fi
[ -n "$got" ] || { echo "Could not get kernel sources for $KV"; exit 1; }
mkdir -p "$WORK/src/$(dirname "$SUBDIR")"; cp -r "$got/$SUBDIR" "$WORK/src/$SUBDIR"

# 2) patch
set +e; python3 "$HERE/honor_dra_fix.py" "$WORK/src/$MODDIR/$SRCFILE"; rc=$?; set -e
[ $rc -eq 2 ] && { echo "This kernel already supports the speakers - no module needed."; exit 2; }
[ $rc -eq 0 ] || exit 1

# 3) build (match the compiler the kernel was built with)
extra=()
grep -q '^CONFIG_CC_IS_CLANG=y' "$KB/.config" 2>/dev/null && extra+=(LLVM=1)
make -C "$KB" M="$WORK/src/$MODDIR" "${extra[@]}" ${CC:+CC=$CC} modules >"$WORK/build.log" 2>&1 || { tail -30 "$WORK/build.log"; exit 1; }
mkdir -p "$OUT"; cp "$WORK/src/$MODDIR/$MOD.ko" "$OUT/"
echo "built: $OUT/$MOD.ko"
