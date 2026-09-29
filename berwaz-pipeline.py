#!/usr/bin/env python3
"""
Berwaz metadata pipeline
========================
Turns raw GIFs in content/ into fully-described, filterable frames.
Safe to re-run any time: it only touches frames that are missing something.

    python3 berwaz-pipeline.py status        # what's missing
    python3 berwaz-pipeline.py scan          # add new GIFs to the data (keeps everything existing)
    python3 berwaz-pipeline.py pixels        # palette / aspect / brightness / temperature from the image itself
    python3 berwaz-pipeline.py prepare       # write pipeline/ files for frames needing prompts or craft fields
    python3 berwaz-pipeline.py classify      # fill craft fields with Claude (needs ANTHROPIC_API_KEY) or from filled files
    python3 berwaz-pipeline.py describe      # write AI prompts with Claude vision (needs ANTHROPIC_API_KEY)
    python3 berwaz-pipeline.py merge         # merge pipeline/*_filled.jsonl back into the data
    python3 berwaz-pipeline.py all           # scan → pixels → prepare → describe → classify → merge (API mode)

Data lives in berwaz-config.json (source of truth for the admin) and frames-data.js (what the
site loads). Both are kept in sync. Existing prompts, names and hand edits are never overwritten.
"""
import json, os, re, sys, math, unicodedata, io, base64, time
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(ROOT, 'berwaz-config.json')
DATA = os.path.join(ROOT, 'frames-data.js')
CONTENT = os.path.join(ROOT, 'content')
PIPE = os.path.join(ROOT, 'pipeline')

# ── Craft taxonomy (the site's filters are built from these exact values) ──
TAXONOMY = {
    "shotSize":    ["extreme-close-up", "close-up", "medium", "wide", "extreme-wide"],
    "angle":       ["eye-level", "low", "high", "top-down", "dutch"],
    "lighting":    ["daylight", "golden-hour", "blue-hour", "night", "low-key", "high-key", "silhouette", "practical", "studio"],
    "timeOfDay":   ["day", "golden-hour", "dusk-dawn", "night", "n-a"],
    "setting":     ["interior", "exterior", "n-a"],
    "environment": ["desert", "urban", "coastal", "heritage", "domestic", "office", "studio", "sports", "vehicle", "nature", "abstract"],
    "movement":    ["static", "handheld", "tracking", "aerial", "unknown"],
    "subject":     ["people", "crowd", "product", "landscape", "architecture", "vehicle", "animal", "graphic"],
    "mood":        ["dramatic", "warm", "playful", "tense", "serene", "epic", "intimate", "melancholic", "energetic", "nostalgic", "mysterious"],
}
MOOD_MAX = 2  # up to two moods per frame

# ═══════════════════════════════════════════════════════════════════
# IO
# ═══════════════════════════════════════════════════════════════════
def load():
    cfg = json.load(open(CONFIG, encoding='utf-8'))
    return cfg

def save(cfg):
    tmp = CONFIG + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, CONFIG)
    # site data mirrors the config's frames
    with open(DATA + '.tmp', 'w', encoding='utf-8') as f:
        f.write('const FRAMES_DATA = ' + json.dumps(slim_for_site(cfg['frames']), separators=(',', ':'), ensure_ascii=False) + ';')
    os.replace(DATA + '.tmp', DATA)
    stamp_data_version()

def slim_for_site(frames):
    """What the website actually loads: full data stays in berwaz-config.json."""
    out = []
    for f in frames:
        g = dict(f)
        px = f.get('pixels')
        if px:
            g['pixels'] = {'temp': px.get('temp'), 'tone': px.get('tone')}
        out.append(g)
    return out

def stamp_data_version():
    """Cache-bust: write frames-data.js?v=<hash> into the pages so browsers refetch new data."""
    import hashlib, re as _re
    try:
        h = hashlib.md5(open(DATA, 'rb').read()).hexdigest()[:10]
    except Exception:
        return
    for page in ('index.html', 'profile.html', os.path.join('directors', 'index.html')):
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            continue
        html = open(path, encoding='utf-8').read()
        new = _re.sub(r'(src=")((?:\.\./)?frames-data\.js)(?:\?v=[0-9a-f]+)?(")', lambda m: m.group(1) + m.group(2) + '?v=' + h + m.group(3), html)
        # same for the cloud files, so config changes are never stuck in a browser cache
        for jsname in ('cloud-config.js', 'berwaz-cloud.js'):
            jp = os.path.join(ROOT, jsname)
            if os.path.exists(jp):
                hj = hashlib.md5(open(jp, 'rb').read()).hexdigest()[:8]
                new = _re.sub(r'(src=")(' + jsname.replace('.', '\\.') + r')(?:\?v=[0-9a-f]+)?(")', lambda m, hj=hj: m.group(1) + m.group(2) + '?v=' + hj + m.group(3), new)
        if new != html:
            open(path, 'w', encoding='utf-8').write(new)

def N(s): return unicodedata.normalize('NFC', s or '').strip()

def derive_source(filename):
    s = re.sub(r'\.gif$', '', filename, flags=re.I)
    s = re.sub(r'_(?:\d+s\d+|scene\d+)$', '', s)
    s = re.sub(r'\s*\((?:1080p|720p|2160p|4k)\)\s*$', '', s, flags=re.I)
    return re.sub(r'\s+', ' ', s.replace('_', ' ')).strip()

def needs_prompt(f):   return not (f.get('prompt') or '').strip()
def needs_pixels(f):   return not f.get('pixels')
def needs_craft(f):    return not f.get('craft')

# ═══════════════════════════════════════════════════════════════════
# scan — add new GIFs, never touch existing records
# ═══════════════════════════════════════════════════════════════════
def cmd_scan(cfg):
    existing = {f['file'] for f in cfg['frames']}
    max_id = max((int(f['id']) for f in cfg['frames']), default=0)
    on_disk = []
    for d, _, files in os.walk(CONTENT):
        for fn in files:
            if fn.lower().endswith('.gif'):
                on_disk.append(os.path.relpath(os.path.join(d, fn), CONTENT).replace(os.sep, '/'))
    on_disk.sort()
    new = [p for p in on_disk if p not in existing]
    gone = [f['file'] for f in cfg['frames'] if f['file'] not in set(on_disk)]
    print(f"on disk {len(on_disk)} | in data {len(cfg['frames'])} | new {len(new)} | missing on disk {len(gone)}")
    if gone:
        print("  ! these frames reference files that are no longer on disk (remove them in the admin if intentional):")
        for g in gone[:10]: print("    -", g)
    # inherit Arabic name / credits from an existing frame of the same project
    by_src = {}
    for f in cfg['frames']:
        by_src.setdefault(N(f['source']), f)
    added = []
    for i, rel in enumerate(new, 1):
        parts = rel.split('/')
        director, filename = parts[0], parts[-1]
        source = derive_source(parts[1]) if len(parts) > 2 else derive_source(filename)
        twin = by_src.get(N(source))
        ym = re.search(r'\b(20\d{2})\b', rel)
        rec = {
            "id": str(max_id + i),
            "title": re.sub(r'\.gif$', '', filename, flags=re.I),
            "source": twin['source'] if twin else source,
            "sourceAr": twin.get('sourceAr', '') if twin else '',
            "year": int(ym.group(1)) if ym else 2024,
            "director": director,
            "dp": "", "tags": [],
            "mood": "", "lighting": "",
            "color": [], "aspect": "",
            "file": rel,
        }
        if twin and twin.get('credits'): rec['credits'] = dict(twin['credits'])
        added.append(rec)
    if added:
        cfg['frames'].extend(added)
        # make sure every director folder is in the directors list
        known = {d['name'] for d in cfg['directors']}
        for d in sorted({a['director'] for a in added} - known):
            cfg['directors'].append({"id": d.lower().replace(' ', '-'), "name": d, "nameAr": "", "bio": "", "vimeo": "", "instagram": "", "twitter": ""})
            print(f"  + new director added: {d}  (fill in the Arabic name and bio in the admin)")
        save(cfg)
        print(f"added {len(added)} frames across {len({a['director'] for a in added})} director(s), {len({a['source'] for a in added})} project(s)")
    return added

# ═══════════════════════════════════════════════════════════════════
# pixels — palette, aspect, brightness, contrast, colour temperature
# ═══════════════════════════════════════════════════════════════════
def middle_frame(path):
    from PIL import Image
    im = Image.open(path)
    n = getattr(im, 'n_frames', 1)
    im.seek(n // 2)
    return im.convert('RGB'), n

def analyse_pixels(path):
    import numpy as np
    from PIL import Image
    im, nframes = middle_frame(path)
    W, H = im.size
    small = im.resize((160, max(1, int(160 * H / W))))
    arr = np.asarray(small, dtype=np.float32) / 255.0
    px = arr.reshape(-1, 3)
    # luminance / contrast
    lum = 0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]
    brightness = float(lum.mean()); contrast = float(lum.std())
    dark_ratio = float((lum < 0.12).mean())
    # colour temperature proxy: mean R - B on non-dark pixels
    lit = px[lum > 0.08] if (lum > 0.08).any() else px
    warmth = float((lit[:, 0] - lit[:, 2]).mean())         # >0 warm, <0 cool
    sat = float((lit.max(1) - lit.min(1)).mean())          # 0 grey → 1 vivid
    # palette: quantise to 10, drop near-duplicates, keep the 5 most frequent —
    # but guarantee the most saturated colour makes it in (a dark frame's one
    # warm practical light is what a filmmaker wants to see, not five blacks)
    q = small.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:48]; counts = sorted(q.getcolors(), reverse=True)
    cands = []
    for cnt, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        if any(abs(r - r2) + abs(g - g2) + abs(b - b2) < 30 for _, (r2, g2, b2) in cands):
            continue
        cands.append((cnt, (r, g, b)))
    def satur(c): return (max(c) - min(c)) / 255.0
    accent = max(cands, key=lambda x: satur(x[1]) * (x[0] ** 0.2)) if cands else None
    chosen = cands[:5]
    if accent and accent not in chosen:
        chosen = chosen[:4] + [accent]
    palette = ['#%02X%02X%02X' % c for _, c in chosen]
    temp = 'warm' if warmth > 0.06 else 'cool' if warmth < -0.06 else 'neutral'
    tone = 'dark' if brightness < 0.22 else 'bright' if brightness > 0.6 else 'mid'
    ratio = W / H
    aspect = ('9:16' if ratio < 0.7 else '1:1' if ratio < 1.2 else '4:3' if ratio < 1.38 else
              '1.43:1' if ratio < 1.6 else '16:9' if ratio < 1.9 else '2:1' if ratio < 2.1 else
              '2.20:1' if ratio < 2.3 else '2.39:1' if ratio < 2.6 else '2.76:1' if ratio < 3.0 else '3.2:1')
    return {
        "w": W, "h": H, "frames": nframes,
        "brightness": round(brightness, 3), "contrast": round(contrast, 3), "darkRatio": round(dark_ratio, 3),
        "warmth": round(warmth, 3), "saturation": round(sat, 3),
        "temp": temp, "tone": tone,
    }, palette, aspect

def cmd_pixels(cfg, force=False):
    todo = [f for f in cfg['frames'] if force or needs_pixels(f)]
    print(f"pixels: {len(todo)} frames to analyse")
    for i, f in enumerate(todo, 1):
        path = os.path.join(CONTENT, f['file'])
        if not os.path.exists(path):
            continue
        try:
            px, palette, aspect = analyse_pixels(path)
            f['pixels'] = px; f['color'] = palette; f['aspect'] = aspect
        except Exception as e:
            print(f"  ! {f['file']}: {e}")
        if i % 200 == 0:
            print(f"  {i}/{len(todo)}"); save(cfg)
    save(cfg)
    print("pixels done")

# ═══════════════════════════════════════════════════════════════════
# prepare — write work files for anything an AI (or a human) must fill
# ═══════════════════════════════════════════════════════════════════
def contact_sheets(frames, outdir, per=6):
    """Labelled 3x2 sheets of middle frames, for vision models / humans."""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(outdir, exist_ok=True)
    try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    except Exception: font = ImageFont.load_default()
    COLS, CW, CH, LH = 3, 560, 315, 26
    sheets = []
    for si in range(0, len(frames), per):
        group = frames[si:si + per]
        rows = math.ceil(len(group) / COLS)
        sheet = Image.new('RGB', (COLS * CW, rows * (CH + LH)), (12, 12, 12)); d = ImageDraw.Draw(sheet)
        for ci, f in enumerate(group):
            r, c = divmod(ci, COLS); x0, y0 = c * CW, r * (CH + LH)
            try:
                img, _ = middle_frame(os.path.join(CONTENT, f['file'])); img.thumbnail((CW, CH))
                sheet.paste(img, (x0 + (CW - img.width) // 2, y0 + LH + (CH - img.height) // 2))
            except Exception as e:
                d.text((x0 + 10, y0 + LH + 10), f'ERR {e}', fill=(255, 80, 80), font=font)
            d.rectangle([x0, y0, x0 + CW, y0 + LH], fill=(212, 168, 83)); d.text((x0 + 8, y0 + 3), f"#{f['id']}", fill=(0, 0, 0), font=font)
        name = f'sheet_{si // per:04d}.jpg'; sheet.save(os.path.join(outdir, name), quality=82)
        sheets.append({"sheet": name, "ids": [f['id'] for f in group]})
    return sheets

def cmd_prepare(cfg):
    os.makedirs(PIPE, exist_ok=True)
    np_ = [f for f in cfg['frames'] if needs_prompt(f)]
    nc = [f for f in cfg['frames'] if needs_craft(f) and not needs_prompt(f)]
    if np_:
        sheets = contact_sheets(np_, os.path.join(PIPE, 'sheets'))
        json.dump(sheets, open(os.path.join(PIPE, 'describe_todo.json'), 'w'), indent=1)
        print(f"describe: {len(np_)} frames need a prompt → pipeline/sheets/ ({len(sheets)} sheets) + describe_todo.json")
    else:
        print("describe: nothing to do")
    with open(os.path.join(PIPE, 'classify_todo.jsonl'), 'w', encoding='utf-8') as fh:
        for f in nc:
            fh.write(json.dumps({"id": f['id'], "prompt": f['prompt']}, ensure_ascii=False) + '\n')
    print(f"classify: {len(nc)} frames need craft fields → pipeline/classify_todo.jsonl")
    print("\nFill pipeline/describe_filled.jsonl  ({\"id\":..,\"prompt\":..}) and pipeline/classify_filled.jsonl "
          "({\"id\":..,\"craft\":{...}}), or run `describe` / `classify` with ANTHROPIC_API_KEY set. Then `merge`.")

# ═══════════════════════════════════════════════════════════════════
# Claude API helpers (optional — only used when ANTHROPIC_API_KEY is set)
# ═══════════════════════════════════════════════════════════════════
CLASSIFY_SYSTEM = f"""You classify film frames from a short cinematic description. Return ONLY a JSON object per line.
Taxonomy (use EXACT values):
{json.dumps(TAXONOMY, indent=1)}
Rules: mood is a list of 1-{MOOD_MAX} values. If a field cannot be determined from the description choose the most likely; use "n-a"/"unknown" only where the taxonomy offers it.
Output format, one line per input id: {{"id":"<id>","craft":{{"shotSize":..,"angle":..,"lighting":..,"timeOfDay":..,"setting":..,"environment":..,"movement":..,"subject":..,"mood":[..]}}}}"""

DESCRIBE_SYSTEM = """You write AI image-generation prompts that recreate the look of film frames. For each labelled frame on the contact sheet (gold bar shows #id) write ONE prompt: 45-80 words, one paragraph, concrete and visual: subject + action → setting/era → shot type & composition → lighting → colour palette → mood → camera/lens/film feel. Use cinematography vocabulary. Ignore on-screen text and logos; do not name real people or brands; Saudi cultural specificity is good when visible. End with a style tag like 'cinematic still, 35mm film look, ultra-detailed'.
Output ONLY JSON lines: {"id":"<id>","prompt":"..."}"""

def claude(messages, system, max_tokens=4000):
    import urllib.request
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY not set — run `prepare` and fill the files manually, or export the key.")
    body = json.dumps({"model": os.environ.get('BERWAZ_MODEL', 'claude-sonnet-4-5'), "max_tokens": max_tokens, "system": system, "messages": messages}).encode()
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, headers={
        'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return ''.join(b.get('text', '') for b in json.load(r)['content'])
        except Exception as e:
            if attempt == 3: raise
            time.sleep(3 * (attempt + 1))

def parse_jsonl(text):
    out = []
    for line in text.splitlines():
        line = line.strip().strip('`')
        if not line.startswith('{'): continue
        try: out.append(json.loads(line))
        except Exception: pass
    return out

def cmd_classify(cfg):
    todo = [f for f in cfg['frames'] if needs_craft(f) and not needs_prompt(f)]
    print(f"classify: {len(todo)} frames")
    if not todo: return
    os.makedirs(PIPE, exist_ok=True)
    out = open(os.path.join(PIPE, 'classify_filled.jsonl'), 'a', encoding='utf-8')
    for i in range(0, len(todo), 40):
        batch = todo[i:i + 40]
        user = '\n'.join(json.dumps({"id": f['id'], "prompt": f['prompt']}, ensure_ascii=False) for f in batch)
        rows = parse_jsonl(claude([{"role": "user", "content": user}], CLASSIFY_SYSTEM))
        for r in rows: out.write(json.dumps(r, ensure_ascii=False) + '\n')
        out.flush(); print(f"  {min(i + 40, len(todo))}/{len(todo)}")
    out.close(); cmd_merge(cfg)

def cmd_describe(cfg):
    todo = [f for f in cfg['frames'] if needs_prompt(f)]
    print(f"describe: {len(todo)} frames")
    if not todo: return
    sheets = contact_sheets(todo, os.path.join(PIPE, 'sheets'))
    out = open(os.path.join(PIPE, 'describe_filled.jsonl'), 'a', encoding='utf-8')
    for k, sh in enumerate(sheets, 1):
        b64 = base64.b64encode(open(os.path.join(PIPE, 'sheets', sh['sheet']), 'rb').read()).decode()
        msg = [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": f"Frame ids on this sheet, in order: {', '.join(sh['ids'])}. Write one prompt per id."}]}]
        rows = parse_jsonl(claude(msg, DESCRIBE_SYSTEM))
        for r in rows: out.write(json.dumps(r, ensure_ascii=False) + '\n')
        out.flush(); print(f"  sheet {k}/{len(sheets)}")
    out.close(); cmd_merge(cfg)

# ═══════════════════════════════════════════════════════════════════
# merge — validate and write filled files into the data
# ═══════════════════════════════════════════════════════════════════
def validate_craft(c):
    if not isinstance(c, dict): return None
    out = {}
    for k, allowed in TAXONOMY.items():
        v = c.get(k)
        if k == 'mood':
            vals = v if isinstance(v, list) else [v] if v else []
            vals = [x for x in vals if x in allowed][:MOOD_MAX]
            if not vals: return None
            out[k] = vals
        else:
            if v not in allowed: return None
            out[k] = v
    return out

def cmd_merge(cfg):
    by = {f['id']: f for f in cfg['frames']}
    n_p = n_c = bad = 0
    p = os.path.join(PIPE, 'describe_filled.jsonl')
    if os.path.exists(p):
        for r in parse_jsonl(open(p, encoding='utf-8').read()):
            f = by.get(str(r.get('id')))
            if f and needs_prompt(f) and isinstance(r.get('prompt'), str) and len(r['prompt'].split()) >= 20:
                f['prompt'] = r['prompt'].strip(); n_p += 1
    p = os.path.join(PIPE, 'classify_filled.jsonl')
    if os.path.exists(p):
        for r in parse_jsonl(open(p, encoding='utf-8').read()):
            f = by.get(str(r.get('id')))
            c = validate_craft(r.get('craft'))
            if f and c and needs_craft(f):
                f['craft'] = c
                # keep the legacy display fields meaningful
                f['mood'] = ', '.join(x.capitalize() for x in c['mood'])
                f['lighting'] = c['lighting'].replace('-', ' ').title()
                f['tags'] = sorted({c['shotSize'], c['lighting'], c['environment'], c['setting'], *c['mood']} - {'n-a', 'unknown'})
                n_c += 1
            elif r.get('craft') is not None and not c:
                bad += 1
    save(cfg)
    print(f"merged: {n_p} prompts, {n_c} craft records{f', {bad} rejected (invalid taxonomy)' if bad else ''}")
    # Consumed files get archived so a re-run can't double-apply them
    os.makedirs(os.path.join(PIPE, 'done'), exist_ok=True)
    for name in ('describe_filled.jsonl', 'classify_filled.jsonl'):
        src = os.path.join(PIPE, name)
        if os.path.exists(src):
            os.replace(src, os.path.join(PIPE, 'done', f"{int(time.time())}_{name}"))
    # Newly described frames now need craft fields — regenerate that work file immediately
    nc = [f for f in cfg['frames'] if needs_craft(f) and not needs_prompt(f)]
    if nc:
        os.makedirs(PIPE, exist_ok=True)
        with open(os.path.join(PIPE, 'classify_todo.jsonl'), 'w', encoding='utf-8') as fh:
            for f in nc: fh.write(json.dumps({"id": f['id'], "prompt": f['prompt']}, ensure_ascii=False) + '\n')
        print(f"next: {len(nc)} frames now need craft fields → pipeline/classify_todo.jsonl (fill classify_filled.jsonl, then merge again)")

# ═══════════════════════════════════════════════════════════════════
def cmd_status(cfg):
    fr = cfg['frames']
    print(f"frames: {len(fr)} | directors: {len(cfg['directors'])} | projects: {len({f['source'] for f in fr})}")
    print(f"  missing prompt : {sum(needs_prompt(f) for f in fr)}")
    print(f"  missing pixels : {sum(needs_pixels(f) for f in fr)}")
    print(f"  missing craft  : {sum(needs_craft(f) for f in fr)}")
    no_ar = sum(1 for f in fr if not f.get('sourceAr'))
    if no_ar: print(f"  missing Arabic project name: {no_ar}")
    if any(needs_craft(f) for f in fr) is False:
        for k in ('shotSize', 'lighting', 'environment'):
            print(f"  {k}: {dict(Counter(f['craft'][k] for f in fr))}")

def main():
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'status')
    cfg = load()
    if cmd == 'status': cmd_status(cfg)
    elif cmd == 'scan': cmd_scan(cfg)
    elif cmd == 'pixels': cmd_pixels(cfg, force='--force' in sys.argv)
    elif cmd == 'prepare': cmd_prepare(cfg)
    elif cmd == 'classify': cmd_classify(cfg)
    elif cmd == 'describe': cmd_describe(cfg)
    elif cmd == 'merge': cmd_merge(cfg)
    elif cmd == 'all':
        cmd_scan(cfg); cmd_pixels(cfg); cmd_describe(cfg); cmd_classify(cfg); cmd_status(cfg)
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
