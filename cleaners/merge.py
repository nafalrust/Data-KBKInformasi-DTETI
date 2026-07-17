"""Deduplikasi lintas sumber. Untuk tahap mono-source OpenAlex ini hanya dipakai
untuk dedup DOI global (constraint UNIQUE doi di schema_staging.sql) dan
title+year fallback untuk publikasi tanpa DOI. Aturan lengkap: §6 Contract.
"""
from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz

from models.schemas import PublicationSchema

TITLE_SIMILARITY_THRESHOLD = 90


def _normalize_title_for_matching(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _is_same_publication(a: PublicationSchema, b: PublicationSchema) -> bool:
    if a.doi and b.doi:
        return a.doi == b.doi
    if a.doi or b.doi:
        return False

    ta, tb = _normalize_title_for_matching(a.title), _normalize_title_for_matching(b.title)
    similarity = fuzz.token_sort_ratio(ta, tb)
    if similarity < TITLE_SIMILARITY_THRESHOLD:
        return False

    if a.year is None or b.year is None:
        return False
    return abs(a.year - b.year) <= 1


def _merge_pair(existing: PublicationSchema, new: PublicationSchema) -> PublicationSchema:
    """Gabung dua baris yang dianggap publikasi sama, sesuai §6.2."""
    merged_external_ids = {**existing.external_ids, **new.external_ids}
    merged_citation_count = existing.citation_count
    if new.citation_count is not None:
        if merged_citation_count is None or new.citation_count > merged_citation_count:
            merged_citation_count = new.citation_count

    merged_abstract = existing.abstract
    if new.abstract and (not merged_abstract or len(new.abstract) > len(merged_abstract)):
        merged_abstract = new.abstract

    return existing.model_copy(update={
        "external_ids": merged_external_ids,
        "citation_count": merged_citation_count,
        "abstract": merged_abstract,
    })


def dedup_publications(publications: list[PublicationSchema]) -> tuple[list[PublicationSchema], list[tuple[PublicationSchema, PublicationSchema]]]:
    """Dedup satu daftar publikasi (mis. hasil gabungan semua dosen dari satu sumber).

    Return (hasil_dedup, pasangan_yang_digabung) — pasangan dicatat untuk audit log.
    """
    result: list[PublicationSchema] = []
    merged_pairs: list[tuple[PublicationSchema, PublicationSchema]] = []

    for pub in publications:
        match_idx: Optional[int] = None
        for i, existing in enumerate(result):
            if _is_same_publication(existing, pub):
                match_idx = i
                break

        if match_idx is None:
            result.append(pub)
        else:
            merged_pairs.append((result[match_idx], pub))
            result[match_idx] = _merge_pair(result[match_idx], pub)

    return result, merged_pairs
