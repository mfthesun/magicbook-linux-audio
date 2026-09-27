#!/usr/bin/env python3
"""Add the HONOR MagicBook Pro 16 2024 (DRA-XX, ALC256 1ee7:204e) speaker fix to a kernel HDA source tree.

Works with both source layouts:
  * Linux >= 6.17: sound/hda/codecs/realtek/alc269.c
  * Linux <  6.17: sound/pci/hda/patch_realtek.c
Usage: honor_dra_fix.py <path/to/alc269.c or patch_realtek.c>
Exit code 0 = patched, 2 = already supported upstream (nothing to do), 1 = error.
"""
import re
import sys

FUNC = """/* HONOR DRA-XX: route Speaker (0x1b) to DAC 0x02, the only DAC reachable from Bass Speaker (0x14) */
static void alc256_fixup_honor_dra_xx_share_dac(struct hda_codec *codec,
\t\t\t\t\t\tconst struct hda_fixup *fix, int action)
{
\tif (action == HDA_FIXUP_ACT_PRE_PROBE) {
\t\tstatic const hda_nid_t conn[] = { 0x02 };

\t\tsnd_hda_override_conn_list(codec, 0x1b, ARRAY_SIZE(conn), conn);
\t}
}

"""
FIXUPS = """\t[ALC256_FIXUP_HONOR_DRA_XX_SPEAKERS] = {
\t\t.type = HDA_FIXUP_PINS,
\t\t.v.pins = (const struct hda_pintbl[]) {
\t\t\t{ 0x14, 0x90170111 }, /* bass speakers */
\t\t\t{ }
\t\t},
\t\t.chained = true,
\t\t.chain_id = ALC256_FIXUP_HONOR_DRA_XX_SHARE_DAC
\t},
\t[ALC256_FIXUP_HONOR_DRA_XX_SHARE_DAC] = {
\t\t.type = HDA_FIXUP_FUNC,
\t\t.v.func = alc256_fixup_honor_dra_xx_share_dac,
\t},
"""
QUIRK = '\tSND_PCI_QUIRK(0x1ee7, 0x204e, "HONOR DRA-XX M1020", ALC256_FIXUP_HONOR_DRA_XX_SPEAKERS),\n'


def main(path):
    s = open(path, encoding="utf-8").read()
    if re.search(r"SND_PCI_QUIRK\(0x1ee7,\s*0x204e", s):
        print("1ee7:204e is already handled by this kernel source - nothing to patch")
        return 2

    def insert(s, pattern, text, after=False):
        m = re.search(pattern, s, re.M)
        if not m:
            raise SystemExit(f"anchor not found: {pattern}")
        i = m.end() if after else m.start()
        return s[:i] + text + s[i:]

    s = insert(s, r"^\tALC285_FIXUP_SPEAKER2_TO_DAC1,\n", "\tALC256_FIXUP_HONOR_DRA_XX_SPEAKERS,\n"
               "\tALC256_FIXUP_HONOR_DRA_XX_SHARE_DAC,\n", after=True)
    s = insert(s, r"^static const struct hda_fixup alc269_fixups\[\] = \{", FUNC)
    s = insert(s, r"^\t\[ALC285_FIXUP_SPEAKER2_TO_DAC1\] = \{", FIXUPS)
    s = insert(s, r"^static const struct (hda_quirk|snd_pci_quirk) alc269_fixup_tbl\[\] = \{\n", QUIRK, after=True)
    open(path, "w", encoding="utf-8").write(s)
    print(f"patched {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
