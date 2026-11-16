"""n2c — novel-to-comic pipeline (stdlib only, one file).

Stages mirror the validated research pipeline, but every gate is a file + a
validator, so a bad stage stops the run instead of poisoning the render:

  plan   : storyboard shots (.jsonl) -> pages.json   (layout geometry fixed first)
  render : pages.json -> panel PNGs via ComfyUI     (--dry reuses/creates stubs)
  bind   : pages.json + panels -> page HTML -> CBZ (+ PDF if Chrome exists)

Design rules taken from the sources, not invented:
  - panels render separately at their own cell aspect; the page is composed later
  - geometry is an explicit intermediate variable, never implied by a prompt
  - lettering is HTML text, not pixels, so it stays crisp and editable
  - every stage is resumable: files are the state, nothing is in memory

Usage:
  python pipeline/n2c.py plan   exports/cnc_bunny/01_neru/v1/prompts.all.jsonl --out books/neru
  python pipeline/n2c.py render books/neru --workflow pipeline/workflows/anima_aesthetic_v11.json --dry
  python pipeline/n2c.py bind   books/neru --title "Neru — Bunny Stage"
  python pipeline/n2c.py selftest

Layouts are fractions of a 1000x1500 page, gutter included in each rect.
"""
import argparse
import hashlib
import html
import json
import pathlib
import shutil
import sys
import urllib.request
import zipfile

PAGE_W, PAGE_H = 1000, 1500
GUTTER = 14

# cell rects as (x, y, w, h) fractions; every preset fills the page exactly
LAYOUTS = {
    'A4': [(0, 0, .5, .5), (.5, 0, .5, .5), (0, .5, .5, .5), (.5, .5, .5, .5)],
    'B4': [(0, 0, 1, .42), (0, .42, 1 / 3, .58), (1 / 3, .42, 1 / 3, .58), (2 / 3, .42, 1 / 3, .58)],
    'C4': [(0, 0, .5, .58), (.5, 0, .5, .58), (0, .58, .5, .42), (.5, .58, .5, .42)],
    'D5': [(0, 0, 1, .34), (0, .34, .5, .33), (.5, .34, .5, .33), (0, .67, .5, .33), (.5, .67, .5, .33)],
}
ORDER = ['B4', 'A4', 'C4', 'D5']


def die(msg):
    sys.exit(f'n2c: {msg}')


def read_jsonl(p):
    return [json.loads(l) for l in pathlib.Path(p).read_text(encoding='utf-8').splitlines() if l.strip()]


def px(rect):
    x, y, w, h = rect
    g = GUTTER
    x0, y0 = x * PAGE_W + g / 2, y * PAGE_H + g / 2
    return (round(x0), round(y0), round(w * PAGE_W - g), round(h * PAGE_H - g))


def render_size(rect, megapixels=1.0):
    """cell aspect -> multiple-of-16 size near the target megapixel budget."""
    x, y, w, h = px(rect)
    ar = w / h
    H = max(16, round((megapixels * 1e6 / ar) ** .5 / 16) * 16)
    W = max(16, round(H * ar / 16) * 16)
    return W, H


def cmp_plan(args):
    shots = read_jsonl(args.jsonl)
    if args.act:
        shots = [s for s in shots if s['act'] == args.act]
    per = args.per_page
    pages = []
    for i in range(0, len(shots), per):
        chunk = shots[i:i + per]
        preset = ORDER[len(pages) % len(ORDER)]
        rects = LAYOUTS[preset][:len(chunk)]
        cells = []
        for j, (shot, rect) in enumerate(zip(chunk, rects)):
            W, H = render_size(rect)
            cells.append({
                'cell': j + 1, 'shot_key': shot['shot_key'], 'act': shot['act'],
                'beat': shot['beat'], 'camera': shot['camera'], 'focus': shot['focus'],
                'rect': px(rect), 'render': [W, H], 'image': None,
                'caption': shot.get('caption', ''),
                'balloons': shot.get('balloons', []),
                'prompt': shot['prompt'],
            })
        pages.append({'page': len(pages) + 1, 'layout': preset, 'cells': cells})
    for p in pages:  # geometry invariants, checked before any rendering happens
        for (x, y, w, h) in (c['rect'] for c in p['cells']):
            assert x >= 0 and y >= 0 and x + w <= PAGE_W and y + h <= PAGE_H, (p['page'], x, y, w, h)
        boxes = [(c['rect'], c['shot_key']) for c in p['cells']]
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                (ax, ay, aw, ah), ka = boxes[a]
                (bx, by, bw, bh), kb = boxes[b]
                assert ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay, (p['page'], ka, kb)
    out = pathlib.Path(args.out)
    (out / 'panels').mkdir(parents=True, exist_ok=True)
    (out / 'pages.json').write_text(json.dumps({'title': args.title or pathlib.Path(args.out).name,
                                                'source': str(args.jsonl), 'pages': pages},
                                               ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'plan: {len(pages)} pages, {sum(len(p["cells"]) for p in pages)} panels -> {out / "pages.json"}')


def load_book(d):
    p = pathlib.Path(d) / 'pages.json'
    if not p.exists():
        die(f'run plan first: {p} missing')
    return json.loads(p.read_text(encoding='utf-8'))


def save_book(d, book):
    (pathlib.Path(d) / 'pages.json').write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding='utf-8')


def panel_path(d, page, cell):
    return pathlib.Path(d) / 'panels' / f'p{page:03d}_c{cell}.png'


def cmp_render(args):
    book = load_book(args.out)
    if args.dry:
        src = pathlib.Path(args.dry_source) if args.dry_source else None
        for p in book['pages']:
            for c in p['cells']:
                dst = panel_path(args.out, p['page'], c['cell'])
                if src and src.exists():
                    shutil.copyfile(src, dst)
                else:
                    dst.write_bytes(b'\x89PNG\r\n\x1a\n')  # stub, replaced by real render
                c['image'] = str(dst.relative_to(args.out)).replace('\\', '/')
        save_book(args.out, book)
        print(f'render(dry): {sum(len(p["cells"]) for p in book["pages"])} stubs')
        return

    wf = json.loads(pathlib.Path(args.workflow).read_text(encoding='utf-8'))
    done = 0
    for p in book['pages']:
        for c in p['cells']:
            dst = panel_path(args.out, p['page'], c['cell'])
            if dst.exists() and dst.stat().st_size > 200 and not args.force:
                c['image'] = str(dst.relative_to(args.out)).replace('\\', '/')
                continue
            g = json.loads(json.dumps(wf))
            seed = int(hashlib.sha256(f'{p["page"]}:{c["shot_key"]}'.encode()).hexdigest()[:12], 16)
            for n in g.values():
                ct = n['class_type']
                if ct == 'CLIPTextEncode' and len(n['inputs'].get('text', '')) > 60:
                    n['inputs']['text'] = c['prompt']
                elif ct in ('EmptyFlux2LatentImage', 'EmptyLatentImage', 'EmptySD3LatentImage'):
                    n['inputs']['width'], n['inputs']['height'] = c['render']
                elif ct == 'KSampler':
                    n['inputs']['seed'] = seed
                elif ct == 'text_Splitter':
                    n['inputs']['text_input'] = c['prompt']
                elif ct == 'SaveImage':
                    n['inputs']['filename_prefix'] = f'n2c_p{p["page"]:03d}_c{c["cell"]}'
            submit_and_wait(args.endpoint, g, dst)
            c['image'] = str(dst.relative_to(args.out)).replace('\\', '/')
            save_book(args.out, book)
            done += 1
            print(f'  p{p["page"]:03d} c{c["cell"]} {c["render"][0]}x{c["render"][1]} ok')
    print(f'render: {done} new panels')


def submit_and_wait(endpoint, graph, dst):
    req = urllib.request.Request(endpoint.rstrip('/') + '/prompt',
                                 data=json.dumps({'prompt': graph, 'client_id': 'n2c'}).encode(),
                                 headers={'Content-Type': 'application/json'})
    pid = json.loads(urllib.request.urlopen(req, timeout=30).read())['prompt_id']
    import time
    for _ in range(600):
        h = json.loads(urllib.request.urlopen(f'{endpoint.rstrip("/")}/history/{pid}', timeout=30).read())
        if pid in h:
            outs = h[pid]['outputs']
            img = next(iter(outs.values()))['images'][0]
            q = urllib.parse.urlencode({'filename': img['filename'],
                                        'subfolder': img.get('subfolder', ''),
                                        'type': img.get('type', 'output')})
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(urllib.request.urlopen(f'{endpoint.rstrip("/")}/view?{q}', timeout=60).read())
            return
        time.sleep(1)
    die(f'comfyui timeout on {dst.name}')


def page_cells(p):
    cells = []
    for c in p['cells']:
        x, y, w, h = c['rect']
        img = c['image'] or ''
        cap = f'<div class="cap">{html.escape(c["caption"])}</div>' if c['caption'] else ''
        balloons = ''.join(
            f'<div class="balloon" style="left:{b.get("x", .1) * 100:.1f}%;top:{b.get("y", .06) * 100:.1f}%;'
            f'max-width:{b.get("w", .5) * 100:.1f}%">{html.escape(b.get("text", ""))}</div>'
            for b in c['balloons'])
        cells.append(
            f'<div class="cell" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">'
            f'<img src="{img}" alt="{html.escape(c["shot_key"])}">{cap}{balloons}</div>')
    return ''.join(cells)


CSS = f"""*{{box-sizing:border-box}} body{{margin:0;background:#fff;font:16px/1.35 "Segoe UI",system-ui,sans-serif}}
 .page{{position:relative;width:{PAGE_W}px;height:{PAGE_H}px;margin:0 auto;background:#111}}
 .cell{{position:absolute;overflow:hidden;background:#222}}
 .cell img{{width:100%;height:100%;object-fit:cover;display:block}}
 .cap{{position:absolute;left:6px;bottom:6px;background:rgba(255,255,255,.92);padding:3px 7px;font-size:13px;
       border:2px solid #111;border-radius:2px;max-width:92%}}
 .balloon{{position:absolute;background:#fff;border:3px solid #111;border-radius:14px;padding:6px 10px;
       font-size:15px;line-height:1.25}}
 @page{{size:{PAGE_W}px {PAGE_H}px;margin:0}}
 @media print{{body{{background:#fff}} .page{{break-after:page;margin:0}}}}"""


def page_html(title, p):
    return f"""<!doctype html><meta charset="utf-8"><title>{html.escape(title)} p{p['page']}</title>
<style>{CSS}</style>
<div class="page">{page_cells(p)}</div>"""


def cmp_bind(args):
    book = load_book(args.out)
    out = pathlib.Path(args.out)
    (out / 'html').mkdir(exist_ok=True)
    for p in book['pages']:
        (out / 'html' / f'page_{p["page"]:03d}.html').write_text(page_html(book['title'], p), encoding='utf-8')
    book_html = out / 'html' / 'book.html'
    book_html.write_text(
        '<!doctype html><meta charset="utf-8"><title>' + html.escape(book['title']) + '</title>'
        f'<style>{CSS}</style>'
        + ''.join(f'<div class="page">{page_cells(p)}</div>' for p in book['pages']),
        encoding='utf-8')
    cbz = out / f'{args.slug or "book"}.cbz'
    with zipfile.ZipFile(cbz, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in book['pages']:
            z.writestr(f'page_{p["page"]:03d}.html', (out / 'html' / f'page_{p["page"]:03d}.html').read_text(encoding='utf-8'))
            for c in p['cells']:
                f = out / c['image'] if c['image'] else None
                if f and f.exists() and f.stat().st_size > 200:
                    z.write(f, f'panels/{f.name}')
    pdf = out / f'{args.slug or "book"}.pdf'
    chrome = next((x for x in (shutil.which('chrome'), shutil.which('msedge'),
                               r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                               r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
                   if x and pathlib.Path(x).exists()), None)
    if chrome:
        import subprocess
        subprocess.run([chrome, '--headless', '--disable-gpu', f'--print-to-pdf={pdf.resolve()}',
                        '--no-pdf-header-footer', book_html.resolve().as_uri()], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f'bind: {len(book["pages"])} pages -> {cbz.name}' + (f', {pdf.name}' if pdf.exists() else ', pdf skipped'))
    print(f'  open {book_html}')


def fmt_selftest(_args):
    for name, rects in LAYOUTS.items():
        area = sum(w * h for _, _, w, h in rects)
        assert abs(area - 1.0) < 1e-9, (name, area)
        for r in rects:
            x, y, w, h = px(r)
            assert w > 0 and h > 0 and x + w <= PAGE_W and y + h <= PAGE_H, (name, r)
    assert render_size((0, 0, .5, .5))[0] % 16 == 0
    p = {'page': 1, 'layout': 'A4', 'cells': [
        {'cell': i + 1, 'shot_key': f'S00{i}', 'rect': px(r), 'image': '', 'caption': '',
         'balloons': [{'text': '<script>'}]} for i, r in enumerate(LAYOUTS['A4'])]}
    doc = page_html('t & t', p)
    assert '<script>' not in doc and '&lt;script&gt;' in doc
    print('selftest: layouts fill the page, cells stay in bounds, lettering is escaped')


def main():
    ap = argparse.ArgumentParser(prog='n2c')
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('plan')
    a.add_argument('jsonl')
    a.add_argument('--out', required=True)
    a.add_argument('--per-page', type=int, default=4)
    a.add_argument('--act', help='only shots of one act, e.g. A01')
    a.add_argument('--title')
    a.set_defaults(fn=cmp_plan)

    b = sub.add_parser('render')
    b.add_argument('out')
    b.add_argument('--workflow', default='pipeline/workflows/anima_aesthetic_v11.json')
    b.add_argument('--endpoint', default='http://127.0.0.1:8188')
    b.add_argument('--dry', action='store_true')
    b.add_argument('--dry-source', help='reuse this PNG for every panel')
    b.add_argument('--force', action='store_true')
    b.set_defaults(fn=cmp_render)

    c = sub.add_parser('bind')
    c.add_argument('out')
    c.add_argument('--title')
    c.add_argument('--slug')
    c.set_defaults(fn=cmp_bind)

    d = sub.add_parser('selftest')
    d.set_defaults(fn=fmt_selftest)

    args = ap.parse_args()
    if getattr(args, 'title', None) and args.cmd == 'bind':
        book = load_book(args.out)
        book['title'] = args.title
        save_book(args.out, book)
    args.fn(args)


if __name__ == '__main__':
    main()
