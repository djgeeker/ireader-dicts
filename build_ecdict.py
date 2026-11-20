"""Build a compact Kindle-format (.mobi source) English-Chinese dictionary with IPA from ECDICT (MIT).
Usage: python build_ecdict.py <ecdict.csv> <out_dir>
Then:  kindlegen <out_dir>/ecdict.opf -c1 -dont_append_source
"""
import csv, html, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
csv.field_size_limit(10**8)
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

FREQ_LIMIT = 60000      # keep words ranked within top-N in BNC or COCA
MAX_EN_LINES = 3        # cap English definitions to keep the popup short
PER_FILE = 10000
BS = chr(92)            # backslash

def num(x):
    try: return int(x)
    except ValueError: return 0

def keep(r):
    return (num(r["collins"]) > 0 or r["oxford"].strip() == "1" or r["tag"].strip()
            or 0 < num(r["bnc"]) <= FREQ_LIMIT or 0 < num(r["frq"]) <= FREQ_LIMIT)

def ipa(p):
    p = p.strip()
    if not p: return ""
    p = (p.replace("\u04d9", "\u0259")   # Cyrillic schwa -> IPA schwa
          .replace("'", "\u02c8").replace(",", "\u02cc").replace(":", "\u02d0"))
    return p

TAGS = {"zk": "中考", "gk": "高考", "cet4": "四级", "cet6": "六级", "ky": "考研",
        "toefl": "托福", "ielts": "雅思", "gre": "GRE"}

rows = [r for r in csv.DictReader(open(src, encoding="utf-8", newline="")) if keep(r) and r["word"].strip()]
rows.sort(key=lambda r: (r["word"].lower(), r["word"]))
print("entries:", len(rows), "| with IPA:", sum(1 for r in rows if r["phonetic"].strip()))

HEAD = ('<html xmlns:mbp="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
        'xmlns:idx="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf">'
        '<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head><body><mbp:frameset>\n')
TAIL = '</mbp:frameset></body></html>\n'

def entry(r, n):
    w = r["word"].strip()
    e = html.escape
    forms = []
    for part in r["exchange"].split("/"):
        if ":" in part:
            k, v = part.split(":", 1)
            if k in "pdi3rts" and v and v != w and v not in forms:
                forms.append(v)
    infl = ("<idx:infl>" + "".join(f'<idx:iform value="{e(f, True)}"/>' for f in forms) + "</idx:infl>") if forms else ""
    p = ipa(r["phonetic"])
    head = f'<idx:orth value="{e(w, True)}"><b>{e(w)}</b>{infl}</idx:orth>'
    meta = []
    if p: meta.append(f"/{e(p)}/")
    stars = num(r["collins"])
    if stars: meta.append("★" * stars)
    if r["oxford"].strip() == "1": meta.append("牛津3000")
    tags = [TAGS[t] for t in r["tag"].split() if t in TAGS]
    if tags: meta.append(" ".join(tags))
    # ECDICT stores line breaks as a literal backslash + "n"
    zh = [x.strip() for x in r["translation"].split(BS + "n") if x.strip()]
    en = [x.strip() for x in r["definition"].split(BS + "n") if x.strip()][:MAX_EN_LINES]
    body = " ".join([head, "&#160;" + " · ".join(meta) if meta else ""])
    body += "".join(f"<br/>{e(x)}" for x in zh)
    if en:
        body += '<br/><span style="font-size:0.85em">' + "<br/>".join(e(x) for x in en) + "</span>"
    return f'<idx:entry name="default" scriptable="yes" spell="yes"><a id="e{n}"></a>{body}</idx:entry><hr/>\n'

files = []
for i in range(0, len(rows), PER_FILE):
    name = f"content{i // PER_FILE + 1:02d}.html"
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        f.write(HEAD)
        for j, r in enumerate(rows[i:i + PER_FILE]):
            f.write(entry(r, i + j))
        f.write(TAIL)
    files.append(name)

manifest = "\n".join(f'    <item id="c{k}" href="{fn}" media-type="application/xhtml+xml"/>' for k, fn in enumerate(files))
spine = "\n".join(f'    <itemref idref="c{k}"/>' for k in range(len(files)))
opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package unique-identifier="uid" version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata>
    <dc-metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:Title>ECDICT 英汉词典（音标）</dc:Title>
      <dc:Language>en</dc:Language>
      <dc:Creator>ECDICT (skywind3000, MIT)</dc:Creator>
      <dc:Identifier id="uid">ecdict-ireader-compact-2026</dc:Identifier>
    </dc-metadata>
    <x-metadata>
      <DictionaryInLanguage>en</DictionaryInLanguage>
      <DictionaryOutLanguage>zh</DictionaryOutLanguage>
      <DefaultLookupIndex>default</DefaultLookupIndex>
    </x-metadata>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine>
{spine}
  </spine>
</package>
'''
open(os.path.join(out, "ecdict.opf"), "w", encoding="utf-8").write(opf)
print("files:", files)
