import argparse, asyncio, json
from pathlib import Path
from parser import parse_file
from carousel import make_deck
from renderer import render


def main():
    ap=argparse.ArgumentParser(description="Lossless-ish six-slide Instagram carousel generator for normalized job TXT files")
    ap.add_argument("--input","-i",required=True)
    ap.add_argument("--output","-o",default="../output_carousel")
    args=ap.parse_args()
    facts=parse_file(args.input)
    deck=make_deck(facts)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    (out/"facts.json").write_text(facts.model_dump_json(indent=2,exclude={"raw_sections"}),encoding="utf-8")
    (out/"carousel.json").write_text(json.dumps(deck,ensure_ascii=False,indent=2),encoding="utf-8")
    asyncio.run(render(deck,str(out)))
    print(f"Generated {out}/slide_1.png ... slide_6.png")
    if facts.conflicts:
        print("FACT CONFLICTS:")
        for x in facts.conflicts: print("-",x)

if __name__=="__main__": main()
