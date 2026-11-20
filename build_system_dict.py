"""Enrich iReader's built-in Youdao English->Chinese dictionary with ECDICT (MIT).
Keeps every Youdao headword, phonetic, word form and flag; only appends extra senses.
Usage: python build_system_dict.py <orig_dict_dir> <ecdict.csv> <out_dir> [max_en_lines]
"""
import csv, os, re, sys, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ydd_format as F
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
csv.field_size_limit(10**8)
src, ecsv, out = sys.argv[1], sys.argv[2], sys.argv[3]
MAX_EN_CORE = int(sys.argv[4]) if len(sys.argv) > 4 else 3    # English lines for common words
MAX_EN_OTHER = int(sys.argv[5]) if len(sys.argv) > 5 else 1   # English lines for rare words
FREQ_LIMIT = 60000
NL = chr(92) + "n"                     # literal backslash-n used as line break in records
os.makedirs(out, exist_ok=True)

POS = {"a.": "adj.", "ad.": "adv.", "s.": "adj.", "r.": "adv.", "art.": "art."}
TAGS = {"zk": "中考", "gk": "高考", "cet4": "四级", "cet6": "六级", "ky": "考研", "toefl": "托福", "ielts": "雅思", "gre": "GRE"}

def norm_pos(line):
    m = re.match(r"^([a-z]{1,5}\.)\s*(.*)$", line)
    if m and m.group(1) in POS: return POS[m.group(1)] + " " + m.group(2)
    m = re.match(r"^([nvasr])\s+(.*)$", line)          # WordNet style "n something"
    if m: return {"n": "n.", "v": "v.", "a": "adj.", "s": "adj.", "r": "adv."}[m.group(1)] + " " + m.group(2)
    return line

def num(x):
    try: return int(x)
    except ValueError: return 0

ec = {}
for r in csv.DictReader(open(ecsv, encoding="utf-8", newline="")):
    ec.setdefault(r["word"], r)

def enrich(word, rec):
    w = word.decode("utf-8", "replace"); r = ec.get(w)
    if not r: return rec, False
    text = rec.decode("utf-8")
    if "$#@" not in text: return rec, False
    main, suffix = text.split("$#@", 1)
    head, _, defs = main.partition(NL)          # head = [level]/UK/US/
    extra = []
    # meta line
    meta = []
    if num(r["collins"]): meta.append("柯林斯" + "★" * num(r["collins"]))
    if r["oxford"].strip() == "1": meta.append("牛津3000")
    t = [TAGS[x] for x in r["tag"].split() if x in TAGS]
    if t: meta.append(" ".join(t))
    # extra Chinese senses not already in Youdao text
    zh_new = []
    for line in [x.strip() for x in r["translation"].split(NL) if x.strip()]:
        line = norm_pos(line)
        m = re.match(r"^([a-z]{1,6}\.)\s*(.*)$", line)
        pos, body = (m.group(1) + " ", m.group(2)) if m else ("", line)
        senses = [s.strip() for s in re.split(r"[,，;；]\s*", body) if s.strip()]
        new = [s for s in senses if s not in defs]
        if new:
            zh_new.append(pos + "；".join(new))
    core = (num(r["collins"]) > 0 or r["oxford"].strip() == "1" or r["tag"].strip()
            or 0 < num(r["bnc"]) <= FREQ_LIMIT or 0 < num(r["frq"]) <= FREQ_LIMIT)
    en = [norm_pos(x.strip()) for x in r["definition"].split(NL) if x.strip()][:MAX_EN_CORE if core else MAX_EN_OTHER]
    if not (meta or zh_new or en): return rec, False
    if meta: extra.append(" ".join(meta))
    if zh_new: extra.append("【补充】" + zh_new[0]); extra += zh_new[1:]
    if en: extra.append("【英释】" + en[0]); extra += en[1:]
    new_main = main + NL + NL.join(extra)
    return (new_main + "$#@" + suffix).encode("utf-8"), True

y = F.read_ydd(os.path.join(src, "e2170331.ydd"))
secs = F.read_idx_sections(os.path.join(src, "yddict.idx"))
entries = []; changed = 0
for w, r in y["entries"]:
    nr, ch = enrich(w, r); entries.append((w, nr)); changed += ch
raw_before = sum(len(r) for w, r in y["entries"]); raw_after = sum(len(r) for w, r in entries)
print(f"entries {len(entries)}, enriched {changed}, raw values {raw_before/1e6:.1f} MB -> {raw_after/1e6:.1f} MB")

max_raw = 48000
while True:
    sizes = F.partition(entries, max_raw=max_raw, max_entries=1500, max_key_raw=30000)
    ydd, sec, st = F.build(entries, sizes, y["head"], secs[0][:4])
    if st["max_val_comp"] <= 19666: break
    max_raw -= 2000
print("block raw cap", max_raw, "|", st)
open(os.path.join(out, "e2170331.ydd"), "wb").write(ydd)
open(os.path.join(out, "yddict.idx"), "wb").write(sec + secs[1])
