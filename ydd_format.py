"""Reader/writer for the Youdao offline dictionary used by iReader e-ink readers
(files /dict/e2170331.ydd, /dict/c2170331.ydd and /dict/yddict.idx).

ydd file
  41-byte header (3-byte type + "youdao dict" + "a test dictionary", NUL padded)
  N zlib key blocks, then N zlib value blocks, then u32 LE = size of this dict's idx section
  key block raw : u24 BE value-block offset (rel. to first value block) | u24 BE value-block
                  compressed length | u16 BE 0 | word0 ; u16BE(off1) word1 ; ... wordN   (no final ;)
  value block raw: records back to back; off_k = byte offset of record k inside the block
  record        : [level]/UK/US/\n<defs joined by literal \n>$#@<forms>[flags]
idx section (yddict.idx = en section followed by zh section)
  4  magic  31 03 17 e2 (en) / c2 (zh)
  u32 LE key region start (41) | u32 LE value region start | u32 LE max raw value block
  u32 LE max compressed value block | 03 02 03 | u16 LE max entries per block | u16 LE block count
  per block: u24 BE key-block offset (rel. to 41) + first word + ';'
"""
import zlib

HEAD_LEN = 41

def read_ydd(path):
    b = open(path, "rb").read()
    pos = HEAD_LEN; S = []
    while True:
        d = zlib.decompressobj()
        try: out = d.decompress(b[pos:])
        except zlib.error: break
        if not d.eof: break
        used = len(b) - pos - len(d.unused_data); S.append((pos, used, out)); pos += used
    half = len(S) // 2
    entries, sizes = [], []
    for k in range(half):
        body = S[k][2][8:]; vo = S[half + k][2]
        i = 0; offs = [0]; words = []
        while i < len(body):
            j = body.find(b";", i)
            if j < 0: words.append(body[i:]); break
            words.append(body[i:j]); i = j + 1
            offs.append(int.from_bytes(body[i:i + 2], "big")); i += 2
        offs.append(len(vo))
        for n, w in enumerate(words):
            entries.append((w, vo[offs[n]:offs[n + 1]]))
        sizes.append(len(words))
    return dict(head=b[:HEAD_LEN], tail=b[pos:], entries=entries, sizes=sizes)

def read_idx_sections(path):
    idx = open(path, "rb").read()
    secs = []; off = 0
    while off < len(idx):
        n = int.from_bytes(idx[off + 25:off + 27], "little"); p = off + 27
        for _ in range(n):
            p = idx.index(b";", p + 3) + 1
        secs.append(idx[off:p]); off = p
    return secs

def partition(entries, max_raw=48000, max_entries=1500, max_key_raw=30000):
    """Greedy split into blocks honouring the size limits; returns list of entry counts."""
    sizes = []; n = raw = kraw = 0
    for w, r in entries:
        if n and (raw + len(r) > max_raw or n + 1 > max_entries or kraw + len(w) + 3 > max_key_raw):
            sizes.append(n); n = raw = kraw = 0
        n += 1; raw += len(r); kraw += len(w) + 3
    if n: sizes.append(n)
    return sizes

def build(entries, sizes, head, magic, level=6):
    """Return (ydd_bytes, idx_section_bytes, stats)."""
    kraws, vraws, first_words = [], [], []
    i = 0
    for n in sizes:
        blk = entries[i:i + n]; i += n
        vr = b"".join(r for w, r in blk)
        assert len(vr) < 65536 + len(blk[-1][1]), "value block too large for u16 offsets"
        parts = [blk[0][0]]; off = 0
        for (w0, r0), (w, r) in zip(blk, blk[1:]):
            off += len(r0); assert off < 65536
            parts.append(b";" + off.to_bytes(2, "big") + w)
        kraws.append(b"".join(parts)); vraws.append(vr); first_words.append(blk[0][0])
    assert i == len(entries)
    vcomp = [zlib.compress(v, level) for v in vraws]
    kblocks, voff = [], 0
    for kr, vc in zip(kraws, vcomp):
        hdr = voff.to_bytes(3, "big") + len(vc).to_bytes(3, "big") + b"\x00\x00"
        kblocks.append(zlib.compress(hdr + kr, level)); voff += len(vc)
    assert voff < 1 << 24, "value region exceeds u24 offsets"
    key_region = b"".join(kblocks)
    vstart = HEAD_LEN + len(key_region)
    sec = bytearray(magic)
    sec += HEAD_LEN.to_bytes(4, "little") + vstart.to_bytes(4, "little")
    sec += max(len(v) for v in vraws).to_bytes(4, "little") + max(len(v) for v in vcomp).to_bytes(4, "little")
    sec += b"\x03\x02\x03" + max(sizes).to_bytes(2, "little") + len(sizes).to_bytes(2, "little")
    koff = 0
    for kb, fw in zip(kblocks, first_words):
        assert koff < 1 << 24
        sec += koff.to_bytes(3, "big") + fw + b";"; koff += len(kb)
    ydd = head + key_region + b"".join(vcomp) + len(sec).to_bytes(4, "little")
    stats = dict(blocks=len(sizes), max_val_raw=max(len(v) for v in vraws), max_val_comp=max(len(v) for v in vcomp),
                 max_key_raw=max(len(k) + 8 for k in kraws), max_entries=max(sizes), value_region=voff, size=len(ydd))
    return ydd, bytes(sec), stats
