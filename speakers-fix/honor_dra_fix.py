#!/usr/bin/env python3
"""Add the HONOR MagicBook Pro 16 2024 (DRA-XX, ALC256 1ee7:204e) speaker + headset-mic fix (headset mode selectable by module parameter) to a kernel HDA source tree.

Works with both source layouts:
  * Linux >= 6.17: sound/hda/codecs/realtek/alc269.c
  * Linux <  6.17: sound/pci/hda/patch_realtek.c
Usage: honor_dra_fix.py <path/to/alc269.c or patch_realtek.c>
Exit code 0 = patched, 2 = already supported upstream (nothing to do), 1 = error.
"""
import re
import sys

FUNC = """/* test knob: 1 = route Speaker (0x1b) to DAC 0x02 (default), 0 = leave the parser default (pins only, like HONOR MRB-XXX) */
static int honor_dra_share_dac = 1;
module_param(honor_dra_share_dac, int, 0444);
MODULE_PARM_DESC(honor_dra_share_dac, "HONOR DRA-XX: 1=route Speaker 0x1b to DAC 0x02 (default), 0=parser default (test only)");

/* HONOR DRA-XX: route Speaker (0x1b) to DAC 0x02, the only DAC reachable from Bass Speaker (0x14) */
static void alc256_fixup_honor_dra_xx_share_dac(struct hda_codec *codec,
\t\t\t\t\t\tconst struct hda_fixup *fix, int action)
{
\tif (action == HDA_FIXUP_ACT_PRE_PROBE) {
\t\tstatic const hda_nid_t conn[] = { 0x02 };

\t\tcodec_info(codec, "HONOR DRA-XX: share DAC %d\\n", honor_dra_share_dac);
\t\tif (honor_dra_share_dac)
\t\t\tsnd_hda_override_conn_list(codec, 0x1b, ARRAY_SIZE(conn), conn);
\t}
}

/*
 * HONOR DRA-XX: the BIOS leaves the combo jack in the "TRS" mode (coef 0x45 = 0xc089), which cuts the
 * headset microphone off. Selectable by the module parameter (takes effect on the next boot):
 *   0 - pin configuration only (microphone stays dead, for comparison)
 *   1 - kernel headset mode with a fallback for the headset mic pin
 *   2 - force CTIA (coef 0x45 = 0xd489, 0x1b = 0x0e6b) at init
 *   3 - like the HONOR BRB-X quirk (hardware auto switch via coef 0x45)
 *   4 - kernel headset mode: CTIA/OMTP is detected on every jack event (default, same as the upstream patch)
 */
static int honor_dra_mic = 4;
module_param(honor_dra_mic, int, 0444);
MODULE_PARM_DESC(honor_dra_mic, "HONOR DRA-XX headset mic: 0=pins only, 1=auto CTIA/OMTP with pin fallback, 2=force CTIA, 3=BRB-X style, 4=auto CTIA/OMTP (default)");

static void alc256_fixup_honor_dra_xx_headset(struct hda_codec *codec,
\t\t\t\t\t      const struct hda_fixup *fix, int action)
{
\tstruct alc_spec *spec = codec->spec;

\tif (action == HDA_FIXUP_ACT_PRE_PROBE)
\t\tcodec_info(codec, "HONOR DRA-XX: headset mic mode %d\\n", honor_dra_mic);

\tswitch (honor_dra_mic) {
\tcase 1:
\tcase 4:
\t\talc_fixup_headset_mode(codec, fix, action);
\t\tif (action == HDA_FIXUP_ACT_PROBE) {
\t\t\tif (honor_dra_mic == 1 && !spec->headset_mic_pin) {
\t\t\t\tcodec_info(codec, "HONOR DRA-XX: parser left headset_mic_pin unset, using 0x19\\n");
\t\t\t\tspec->headset_mic_pin = 0x19;
\t\t\t}
\t\t\tcodec_info(codec, "HONOR DRA-XX: headset_mic_pin=0x%02x\\n", spec->headset_mic_pin);
\t\t}
\t\tbreak;
\tcase 2:
\t\tif (action == HDA_FIXUP_ACT_INIT) {
\t\t\talc_write_coef_idx(codec, 0x45, 0xd489);
\t\t\talc_write_coef_idx(codec, 0x1b, 0x0e6b);
\t\t}
\t\tbreak;
\tcase 3:
\t\tif (action == HDA_FIXUP_ACT_PRE_PROBE) {
\t\t\talc_update_coef_idx(codec, 0x45, 0xf << 12 | 1 << 10, 5 << 12);
\t\t\tspec->parse_flags |= HDA_PINCFG_HEADSET_MIC;
\t\t}
\t\tbreak;
\t}
}

"""
FIXUPS = """\t[ALC256_FIXUP_HONOR_DRA_XX_SPEAKERS] = {
\t\t.type = HDA_FIXUP_PINS,
\t\t.v.pins = (const struct hda_pintbl[]) {
\t\t\t{ 0x14, 0x90170111 }, /* bass speakers */
\t\t\t{ 0x19, 0x03a1113c }, /* headset mic, without its own jack detect */
\t\t\t{ }
\t\t},
\t\t.chained = true,
\t\t.chain_id = ALC256_FIXUP_HONOR_DRA_XX_SHARE_DAC
\t},
\t[ALC256_FIXUP_HONOR_DRA_XX_SHARE_DAC] = {
\t\t.type = HDA_FIXUP_FUNC,
\t\t.v.func = alc256_fixup_honor_dra_xx_share_dac,
\t\t.chained = true,
\t\t.chain_id = ALC256_FIXUP_HONOR_DRA_XX_HEADSET
\t},
\t[ALC256_FIXUP_HONOR_DRA_XX_HEADSET] = {
\t\t.type = HDA_FIXUP_FUNC,
\t\t.v.func = alc256_fixup_honor_dra_xx_headset,
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
               "\tALC256_FIXUP_HONOR_DRA_XX_SHARE_DAC,\n"
               "\tALC256_FIXUP_HONOR_DRA_XX_HEADSET,\n", after=True)
    s = insert(s, r"^static const struct hda_fixup alc269_fixups\[\] = \{", FUNC)
    s = insert(s, r"^\t\[ALC285_FIXUP_SPEAKER2_TO_DAC1\] = \{", FIXUPS)
    s = insert(s, r"^static const struct (hda_quirk|snd_pci_quirk) alc269_fixup_tbl\[\] = \{\n", QUIRK, after=True)
    open(path, "w", encoding="utf-8").write(s)
    print(f"patched {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
