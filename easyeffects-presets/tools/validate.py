import json,re,glob,pathlib,xml.etree.ElementTree as ET
import os
# EE_SRC: path to a checkout of https://github.com/wwmm/easyeffects src/ (preset format reference)
SRC=pathlib.Path(os.environ.get("EE_SRC","deps/easyeffects/src"))
BASE=pathlib.Path(__file__).resolve().parent.parent
def kcfg(name):
    t=ET.parse(SRC/f"contents/kcfg/easyeffects_db_{name}.kcfg").getroot(); d={}
    for e in t.iter():
        if e.tag.endswith('entry'):
            g=lambda s:[c.text for c in e if c.tag.endswith(s)]
            d[e.get('name')]={'def':g('default'),'min':g('min'),'max':g('max'),'type':e.get('type')}
    return d
def lf(s): return s[0].lower()+s[1:]
errs=0
for f in sorted(glob.glob(str(BASE/"output/*.json"))+glob.glob(str(BASE/"input/*.json"))):
    jj=json.load(open(f)); j=jj.get("output") or jj.get("input")
    for key in j["plugins_order"]:
        assert key in j, key
        ptype=key.split('#')[0]; s=j[key]; k=kcfg(ptype)
        code=(SRC/f"{ptype}_preset.cpp").read_text(); load=code[code.find('::load('):]
        known=set()
        for m in re.finditer(r'UPDATE_(ENUM_LIKE_)?PROPERTY(_INSIDE_SUBSECTION)?\(([^)]*)\)',load):
            args=[a.strip().strip('"') for a in m.group(3).split(',')]
            if m.group(2): sub,jk,prop=args; val=s.get(sub,{}).get(jk,None); known.add(sub)
            else: jk,prop=args; val=s.get(jk,None); known.add(jk)
            if val is None: print(f"  missing {f.split('/')[-1]} {key}.{jk}"); continue
            e=k.get(lf(prop))
            if m.group(1):
                labels=k[lf(prop)+'Labels']['def'][0].split(',')
                if val not in labels: print("ENUM ERR",f,key,jk,val,labels); errs+=1
            elif e and e['min'] and isinstance(val,(int,float)) and not isinstance(val,bool):
                if not(float(e['min'][0])<=val<=float(e['max'][0])): print("RANGE ERR",f,key,jk,val,e['min'],e['max']); errs+=1
        extra=set(s)-known-{'left','right','blocklist'}-{f'band{i}' for i in range(8)}
        if extra: print("  unknown keys",f.split('/')[-1],key,extra)
        if ptype=='equalizer':
            ch=kcfg('equalizer_channel'); T=ch['bandTypeLabels']['def'][0].split(','); M=ch['bandModeLabels']['def'][0].split(',')
            for side in ('left','right'):
                for i in range(s['num-bands']):
                    b=s[side][f'band{i}']
                    if b['type'] not in T or b['mode'] not in M or not(10<=b['frequency']<=24000) or not(-36<=b['gain']<=36):
                        print("EQ ERR",f,b); errs+=1
print("errors:",errs)
