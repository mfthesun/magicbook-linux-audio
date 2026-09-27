import struct,sys
b=open(sys.argv[2] if len(sys.argv) > 2 else "raw/rtk2/awinic/awinic/awinic_SKTune_config.bin",'rb').read()
base=0x410; size=6496
names="Bypass Game Moive Music SpaceDefaut SpaceMoive SpaceVedio SpaceVoice Standard Voice".split()
def I(blk,o): return struct.unpack_from('<i',blk,o)[0]
def F(blk,o): return struct.unpack_from('<f',blk,o)[0]
def recs(p):
    blk=b[base+p*size: base+(p+1)*size]; out=[]
    for o in range(0,len(blk)-24,4):
        if I(blk,o+20) in (12,24,36,48) and I(blk,o) in (0,1) and 0<=I(blk,o+4)<=10 and 10<=F(blk,o+8)<=24000 and -40<=F(blk,o+12)<=40 and 0<F(blk,o+16)<=50:
            out.append((o,I(blk,o),I(blk,o+4),F(blk,o+8),round(F(blk,o+12),2),round(F(blk,o+16),3),I(blk,o+20)))
    return out
if __name__=="__main__":
    p=names.index(sys.argv[1])
    for r in recs(p): print(r)
