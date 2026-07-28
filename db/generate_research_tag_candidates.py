"""
Generate draft kandidat research_tags per dosen dari judul+abstract publikasi
yang sudah di-crawl (exports/*_openalex.json). HASIL INI DRAFT UNTUK DIREVIEW
MANUSIA -- bukan langsung di-insert ke lecturer_research_tags.

Cara jalan:
    python db/generate_research_tag_candidates.py

Input:
    exports/lecturers_openalex.json
    exports/publications_openalex.json
    exports/lecturer_publications_openalex.json
    db/research_tag_keywords.py (TAG_KEYWORDS)

Output:
    exports/lecturer_research_tags_candidates.csv
    kolom: full_name, tag_slug
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from research_tag_keywords import TAG_KEYWORDS

BASE = Path(__file__).resolve().parent.parent
EXPORTS = BASE / "exports"

TOP_N_TAGS_PER_LECTURER = 6


def load_json(name):
    with open(EXPORTS / name, encoding="utf-8") as f:
        return json.load(f)


def compile_patterns():
    # word-boundary match, case-insensitive; keyword bisa multi-kata (mis. "machine learning")
    patterns = {}
    for slug, keywords in TAG_KEYWORDS.items():
        patterns[slug] = [
            re.compile(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])")
            for kw in keywords
        ]
    return patterns


def main():
    lecturers = load_json("lecturers_openalex.json")
    publications = load_json("publications_openalex.json")
    lecturer_publications = load_json("lecturer_publications_openalex.json")

    pub_by_id = {p["id"]: p for p in publications}
    lecturer_by_row_ref = {l["row_ref"]: l for l in lecturers}

    pub_ids_by_lecturer_row_ref = defaultdict(list)
    for link in lecturer_publications:
        pub_ids_by_lecturer_row_ref[link["lecturer_row_ref"]].append(link["publication_id"])

    patterns = compile_patterns()

    rows = []
    lecturers_with_tags = set()
    for row_ref, lecturer in lecturer_by_row_ref.items():
        pub_ids = pub_ids_by_lecturer_row_ref.get(row_ref, [])
        if not pub_ids:
            continue

        tag_score = defaultdict(int)

        for pub_id in pub_ids:
            pub = pub_by_id.get(pub_id)
            if not pub:
                continue
            title = pub.get("title") or ""
            abstract = pub.get("abstract") or ""
            text = f"{title} {abstract}".lower()

            for slug, regex_list in patterns.items():
                hits = sum(1 for rgx in regex_list if rgx.search(text))
                if hits:
                    tag_score[slug] += hits

        if not tag_score:
            continue

        ranked = sorted(tag_score.items(), key=lambda kv: kv[1], reverse=True)
        top_tags = ranked[:TOP_N_TAGS_PER_LECTURER]

        lecturers_with_tags.add(row_ref)
        for slug, _score in top_tags:
            rows.append({
                "full_name": lecturer["full_name"],
                "tag_slug": slug,
            })

    out_path = EXPORTS / "lecturer_research_tags_candidates.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["full_name", "tag_slug"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Ditulis {len(rows)} baris kandidat tag untuk {len(lecturers_with_tags)} dosen -> {out_path}")
    no_match = [l["full_name"] for row_ref, l in lecturer_by_row_ref.items() if row_ref not in lecturers_with_tags]
    if no_match:
        print(f"{len(no_match)} dosen TANPA kandidat tag (perlu ditentukan manual):")
        for name in no_match:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
