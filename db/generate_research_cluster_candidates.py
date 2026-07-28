"""
Generate draft kandidat primary_research_cluster_id per dosen, diturunkan dari
tag riset dengan skor keyword-match TERTINGGI milik dosen tsb (lihat
db/generate_research_tag_candidates.py untuk cara skor tag dihitung).
Aturan: 1 dosen = 1 cluster (bukan many-to-many). HASIL INI DRAFT UNTUK
DIREVIEW MANUSIA -- bukan langsung di-insert/update ke lecturers.

Cara jalan:
    python db/generate_research_cluster_candidates.py

Input:
    exports/lecturers_openalex.json
    exports/publications_openalex.json
    exports/lecturer_publications_openalex.json
    db/research_tag_keywords.py (TAG_KEYWORDS)
    db/research_tag_cluster_map.py (TAG_TO_CLUSTER)

Output:
    exports/lecturer_research_clusters_candidates.csv
    kolom: full_name, cluster_slug
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from research_tag_keywords import TAG_KEYWORDS
from research_tag_cluster_map import TAG_TO_CLUSTER

BASE = Path(__file__).resolve().parent.parent
EXPORTS = BASE / "exports"


def load_json(name):
    with open(EXPORTS / name, encoding="utf-8") as f:
        return json.load(f)


def compile_patterns():
    patterns = {}
    for slug, keywords in TAG_KEYWORDS.items():
        patterns[slug] = [
            re.compile(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])")
            for kw in keywords
        ]
    return patterns


def score_tags_for_lecturer(pub_ids, pub_by_id, patterns):
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
    return tag_score


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
    lecturers_with_cluster = set()
    for row_ref, lecturer in lecturer_by_row_ref.items():
        pub_ids = pub_ids_by_lecturer_row_ref.get(row_ref, [])
        if not pub_ids:
            continue

        tag_score = score_tags_for_lecturer(pub_ids, pub_by_id, patterns)
        if not tag_score:
            continue

        top_tag_slug, _score = max(tag_score.items(), key=lambda kv: kv[1])
        cluster_slug = TAG_TO_CLUSTER[top_tag_slug]

        lecturers_with_cluster.add(row_ref)
        rows.append({
            "full_name": lecturer["full_name"],
            "cluster_slug": cluster_slug,
        })

    out_path = EXPORTS / "lecturer_research_clusters_candidates.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["full_name", "cluster_slug"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Ditulis {len(rows)} baris kandidat cluster untuk {len(lecturers_with_cluster)} dosen -> {out_path}")
    no_match = [l["full_name"] for row_ref, l in lecturer_by_row_ref.items() if row_ref not in lecturers_with_cluster]
    if no_match:
        print(f"{len(no_match)} dosen TANPA kandidat cluster (perlu ditentukan manual):")
        for name in no_match:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
