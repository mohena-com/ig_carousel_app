import argparse
from pathlib import Path
import asyncio
from parser import parse_file
from carousel import make_deck
from renderer import render


def main():
    ap=argparse.ArgumentParser(description='Generate six-slide carousels for every TXT file in a folder')
    ap.add_argument('--input-dir',required=True)
    ap.add_argument('--output-dir',default='batch_output')
    args=ap.parse_args()
    src=Path(args.input_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    files=sorted(src.glob('*.txt'))
    if not files: raise SystemExit('No .txt files found')
    for p in files:
        try:
            facts=parse_file(p); deck=make_deck(facts)
            dest=out/p.stem; dest.mkdir(parents=True,exist_ok=True)
            (dest/'facts.json').write_text(facts.model_dump_json(indent=2,exclude={'raw_sections'}),encoding='utf-8')
            import json
            (dest/'carousel.json').write_text(json.dumps(deck,ensure_ascii=False,indent=2),encoding='utf-8')
            asyncio.run(render(deck,str(dest)))
            print(f'OK  {p.name} -> {dest}')
            for c in facts.conflicts: print('    WARNING:',c)
        except Exception as e:
            print(f'ERR {p.name}: {e}')

if __name__=='__main__': main()
