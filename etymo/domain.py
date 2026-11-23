"""Domain types shared by all stages: plain data, no I/O, no stage logic.

A ``Word`` is one node of the graph (ADR 0001), an ``EtymLink`` is one piece of link evidence
after resolution (ADR 0003). Both are immutable and check their own invariants when they are
created, so a broken record fails where it is made, not three stages later.

Not here yet: ``Language`` (unit catalog.py), the merged link with ``evidence_count`` and
``has_parallel`` (build stage), ``ImportRun`` (build/export stage).
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

# ASCII "unit separator" between the parts of a hashed id. It cannot occur in a Wiktionary page
# title or a language code, so ("a", "bc") and ("ab", "c") never produce the same input bytes.
SEP = "\x1f"


class WordStatus(StrEnum):
    """Where a word node comes from (ADR 0001, data contract `words.status`)."""

    ENTRY = "entry"  # built from a loaded kaikki lemma entry
    STUB = "stub"  # a link target with no entry
    AMBIGUOUS = "ambiguous"  # page node for a target that matches several homographs


class StubReason(StrEnum):
    """Why a stub has no entry (only for ``WordStatus.STUB``)."""

    NO_ENTRY = "no_entry"  # the language file is loaded, but has no such entry
    NO_FILE = "no_file"  # the language file is not part of the build


class LinkType(StrEnum):
    """The four link types of ADR 0003. The raw template name is kept separately."""

    INH = "inh"
    BOR = "bor"
    DER = "der"
    CALQUE = "calque"


class Syntax(StrEnum):
    """Which template syntax the link came from (ADR 0003)."""

    CLASSIC = "classic"  # {{inh|de|gmh|hërze}}
    ETY = "ety"  # {{ety|de|:inh|gmh:hërze}} and {{etymon|...}}


class Extraction(StrEnum):
    """How the link was found (ADR 0003)."""

    TEMPLATE = "template"  # the template names this link explicitly
    CHAIN = "chain"  # inferred from "From X, from Y" order


class Resolution(StrEnum):
    """Outcome of resolving the link target (ADR 0001, table "Resolving a link target")."""

    RESOLVED = "resolved"
    RESOLVED_BY_ID = "resolved_by_id"
    AMBIGUOUS = "ambiguous"
    STUB = "stub"


def parse_etym_no(raw: str | None) -> int:
    """Turn kaikki's ``etymology_number`` into ``etym_no``; absent means 0 (ADR 0001).

    kaikki numbers sections from 1, so "0" or any other format raises ``ValueError``.
    """
    if raw is None:
        return 0
    # isascii: isdigit alone also accepts digits such as "٢". startswith: rejects "0" and "01".
    if not raw.isascii() or not raw.isdigit() or raw.startswith("0"):
        raise ValueError(f"invalid etymology_number: {raw!r}")
    return int(raw)


def _short_hash(*parts: str) -> str:
    """First 16 hex digits of SHA-256 over the parts joined with ``SEP`` (ADR 0006)."""
    data = SEP.join(parts).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def word_id(lang: str, key: str, etym_no: int) -> str:
    """Stable id of a word, computed only from its identity triple (ADR 0006)."""
    return "w_" + _short_hash(lang, key, str(etym_no))


def link_id(src_word_id: str, dst_word_id: str, link_type: LinkType) -> str:
    """Stable id of a merged link: one per (derived word, etymon, type), ADR 0003."""
    return "l_" + _short_hash(src_word_id, dst_word_id, link_type.value)


def _is_sorted_unique(values: tuple[str, ...]) -> bool:
    """True if the values are sorted and contain no duplicates."""
    return list(values) == sorted(set(values))


@dataclass(frozen=True)
class Word:
    """One word node. Identity is (``lang``, ``key``, ``etym_no``), ADR 0001.

    Tuples instead of lists keep the object immutable and hashable.
    """

    lang: str
    key: str
    etym_no: int
    form: str
    is_reconstruction: bool
    status: WordStatus
    stub_reason: StubReason | None
    pos: tuple[str, ...]
    ety_ids: tuple[str, ...]
    gloss: str | None
    source_file: str | None

    def __post_init__(self) -> None:
        """Reject a word that breaks the contract (ADR 0001, data contract section 5)."""
        self._check(bool(self.lang), "lang is empty")
        self._check(bool(self.key), "key is empty")
        self._check(bool(self.form), "form is empty")
        # Only check NFC here: normalizing is the extract stage's job.
        self._check(unicodedata.is_normalized("NFC", self.form), "form is not NFC")
        self._check(unicodedata.is_normalized("NFC", self.key), "key is not NFC")
        self._check(self.etym_no >= 0, "etym_no is negative")
        self._check_asterisk()
        self._check_status()
        self._check(_is_sorted_unique(self.pos), "pos is not sorted and unique")
        self._check(_is_sorted_unique(self.ety_ids), "ety_ids is not sorted and unique")

    def _check(self, condition: bool, rule: str) -> None:
        """Raise ``ValueError`` naming the word and the broken rule."""
        if not condition:
            raise ValueError(f"invalid Word {self.lang}:{self.key!r}: {rule}")

    def _check_asterisk(self) -> None:
        """A reconstruction has exactly one leading "*", in both ``form`` and ``key``."""
        form_has_asterisk = self.form.startswith("*")
        self._check(
            self.is_reconstruction == form_has_asterisk,
            "is_reconstruction does not match the asterisk in form",
        )
        self._check(
            self.key.startswith("*") == form_has_asterisk,
            "key and form disagree on the asterisk",
        )
        self._check(not self.form.startswith("**"), "form starts with two asterisks")
        self._check(not self.key.startswith("**"), "key starts with two asterisks")

    def _check_status(self) -> None:
        """Entries describe real data; stub and page nodes only describe a link target."""
        self._check(
            (self.stub_reason is not None) == (self.status == WordStatus.STUB),
            "stub_reason must be set exactly for stubs",
        )
        if self.status == WordStatus.ENTRY:
            self._check(self.source_file is not None, "entry has no source_file")
            self._check(bool(self.pos), "entry has no pos")
        else:
            self._check(self.etym_no == 0, "stub or page node has etym_no")
            self._check(self.source_file is None, "stub or page node has source_file")
            self._check(not self.pos, "stub or page node has pos")
            self._check(not self.ety_ids, "stub or page node has ety_ids")

    @property
    def id(self) -> str:
        """``word_id`` of this word."""
        return word_id(self.lang, self.key, self.etym_no)

    @property
    def identity(self) -> tuple[str, str, int]:
        """The identity triple (lang, key, etym_no)."""
        return (self.lang, self.key, self.etym_no)


def _target_word(
    lang: str, key: str, form: str, status: WordStatus, reason: StubReason | None
) -> Word:
    """A node that describes a link target, not a loaded entry."""
    return Word(
        lang=lang,
        key=key,
        etym_no=0,
        form=form,
        is_reconstruction=form.startswith("*"),
        status=status,
        stub_reason=reason,
        pos=(),
        ety_ids=(),
        gloss=None,
        source_file=None,
    )


def stub_word(lang: str, key: str, form: str, reason: StubReason) -> Word:
    """Stub node for a link target without an entry (ADR 0001, resolution table, rows 4-5)."""
    return _target_word(lang, key, form, WordStatus.STUB, reason)


def page_word(lang: str, key: str, form: str) -> Word:
    """Page node for an ambiguous target (ADR 0001, resolution table, row 3).

    ``etym_no`` 0 cannot collide with homographs, which are numbered from 1.
    """
    return _target_word(lang, key, form, WordStatus.AMBIGUOUS, None)


# Confidence by extraction class (ADR 0003): heuristic values from the probe, not probabilities.
TEMPLATE_CONFIDENCE = 0.9
CHAIN_CONFIDENCE = 0.6


@dataclass(frozen=True)
class EtymLink:
    """One piece of link evidence after resolution: derived word -> etymon (ADR 0003).

    Records with the same (src, dst, type) are merged into one link in the build stage.
    """

    src_word_id: str
    dst_word_id: str
    type: LinkType
    source_entry: str
    source_file: str
    template: str
    keyword: str | None
    syntax: Syntax
    extraction: Extraction
    hop: int
    target_lang_raw: str
    target_form: str
    target_sense_id: str | None
    resolution: Resolution
    raw_template: str

    def __post_init__(self) -> None:
        """Reject broken evidence (ADR 0003). Self-loops are allowed: build drops them."""
        self._check(self.hop >= 0, "hop is negative")
        if self.extraction == Extraction.CHAIN:
            self._check(self.hop >= 1, "chain link has hop 0")
        if self.syntax == Syntax.CLASSIC:
            self._check(self.keyword is None, "classic template has a keyword")
        self._check(bool(self.template), "template is empty")
        self._check(bool(self.target_lang_raw), "target_lang_raw is empty")
        self._check(bool(self.target_form), "target_form is empty")
        self._check(unicodedata.is_normalized("NFC", self.target_form), "target_form is not NFC")

    def _check(self, condition: bool, rule: str) -> None:
        """Raise ``ValueError`` naming the template and the broken rule."""
        if not condition:
            raise ValueError(f"invalid EtymLink {self.raw_template!r}: {rule}")

    @property
    def id(self) -> str:
        """``link_id`` of the link this evidence belongs to."""
        return link_id(self.src_word_id, self.dst_word_id, self.type)

    @property
    def confidence(self) -> float:
        """Heuristic confidence of this extraction class (ADR 0003)."""
        if self.extraction == Extraction.TEMPLATE:
            return TEMPLATE_CONFIDENCE
        return CHAIN_CONFIDENCE
