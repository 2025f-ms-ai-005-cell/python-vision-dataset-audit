"""Offline dataset inventory with exact-byte duplicate and split-overlap checks."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
from PIL import Image

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff'}


def inventory(root, min_size=64, max_pixels=20_000_000):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Input must be an existing directory')
    if min_size < 1 or max_pixels < 1:
        raise ValueError('Limits must be positive')
    rows, hashes = [], {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        relative = path.relative_to(root)
        row = dict(path=relative.as_posix(), split=relative.parts[0] if len(relative.parts)>1 else 'unspecified',
                   width=None, height=None, mode=None, sha256=None, flags=[], error=None)
        try:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(65536), b''):
                    digest.update(block)
            row['sha256'] = digest.hexdigest()
            with Image.open(path) as image:
                row.update(width=image.width, height=image.height, mode=image.mode)
                if image.width * image.height > max_pixels:
                    raise ValueError('Image exceeds configured pixel limit')
                image.verify()
            with Image.open(path) as image:
                image.load()  # verify structure AND decode pixels
            if min(row['width'], row['height']) < min_size:
                row['flags'].append('small_image')
            hashes.setdefault(row['sha256'], []).append(row)
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            row['flags'].append('unreadable')
            row['error'] = ('Image exceeds configured pixel limit' if isinstance(exc, ValueError)
                            else f'{type(exc).__name__}: image could not be validated')
        rows.append(row)
    duplicates = []
    for digest, group in hashes.items():
        if len(group) < 2:
            continue
        overlap = len({row['split'] for row in group}) > 1
        duplicates.append(dict(sha256=digest, paths=[row['path'] for row in group], cross_split=overlap))
        for row in group:
            row['flags'].append('exact_duplicate')
            if overlap:
                row['flags'].append('cross_split_overlap')
    return dict(schema_version=1, settings=dict(min_size=min_size, max_pixels=max_pixels),
                summary=dict(images=len(rows), unreadable=sum('unreadable' in r['flags'] for r in rows),
                             flagged=sum(bool(r['flags']) for r in rows), duplicate_groups=len(duplicates),
                             cross_split_groups=sum(d['cross_split'] for d in duplicates)),
                images=rows, duplicates=duplicates)


def export(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (output/'inventory.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['path','split','width','height','mode','sha256','flags','error'])
        writer.writeheader()
        for row in report['images']:
            writer.writerow({**row, 'flags': ';'.join(row['flags'])})
    cards = ''.join(f'<article><span>{html.escape(key.replace("_"," "))}</span><strong>{value}</strong></article>'
                    for key, value in report['summary'].items())
    rows = ''.join('<tr>'+''.join(f'<td>{html.escape(str(value))}</td>' for value in
                    [r['path'],r['split'],f"{r['width']} × {r['height']}",', '.join(r['flags']) or 'OK',r['error'] or '—'])+'</tr>'
                    for r in report['images'])
    page = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    page += '<title>Vision Dataset Audit</title><style>body{background:#11172b;color:#eef2ff;font:16px system-ui;margin:0;padding:5vw}h1{font-size:48px;margin:8px 0}p{color:#b4bed8}header small{color:#ffbb70;letter-spacing:3px}section{display:flex;gap:16px;flex-wrap:wrap;margin:40px 0}article{background:#202a46;border:1px solid #37466b;border-radius:16px;padding:24px;min-width:130px}article span{display:block;text-transform:capitalize;color:#b4bed8}strong{display:block;font-size:40px;color:#8be0b4}table{border-collapse:collapse;width:100%;background:#19233b}td,th{text-align:left;padding:16px;border-bottom:1px solid #344261}th{color:#ffbb70}footer{margin-top:24px;color:#a8b5d1} .scroll{overflow:auto}</style>'
    page += '<header><small>COMPUTER VISION • DATA QUALITY</small><h1>Vision Dataset Audit</h1><p>Know your inputs before training. Offline, read-only, reproducible.</p></header><section>'+cards+'</section>'
    page += '<div class="scroll"><table><tr><th>Image</th><th>Split</th><th>Dimensions</th><th>Flags</th><th>Error</th></tr>'+rows+'</table></div><footer>Exact-byte hashes only. Cross-split overlap is a review signal, not proof of invalid evaluation. No input images are uploaded or modified.</footer>'
    (output/'index.html').write_text(page, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--min-size', type=int, default=64)
    parser.add_argument('--max-pixels', type=int, default=20_000_000)
    args = parser.parse_args()
    try:
        # Keep reports outside input to prevent feedback in later scans.
        if args.output.resolve().is_relative_to(args.input.resolve()):
            raise ValueError('Output must be outside the input directory')
        report = inventory(args.input, args.min_size, args.max_pixels)
        export(report, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Error: {exc}\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
