"""Specification for etymo/domain.py (ADR 0001, 0003, 0006; data contract v1).

Expected ids are copied from samples/de-pl-mini/, so they also check that the pipeline and the
team sample agree. Suggested order: parse_etym_no, word_id, link_id, Word, stub_word/page_word,
EtymLink.
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from etymo.domain import (
    CHAIN_CONFIDENCE,
    TEMPLATE_CONFIDENCE,
    EtymLink,
    Extraction,
    LinkType,
    Resolution,
    StubReason,
    Syntax,
    Word,
    WordStatus,
    link_id,
    page_word,
    parse_etym_no,
    stub_word,
    word_id,
)

# Real ids from samples/de-pl-mini/words.csv and links.csv.
HERZ_ID = "w_a93f12e74213d449"
HERZE_ID = "w_07cdc91011cf9eec"  # gmh:hërze
HERZA_ID = "w_28d1fc8fa68a82a1"  # goh:hërza


def nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


# --- builders: one valid word of each kind; tests change one field with dataclasses.replace ---


def entry(lang: str, key: str, form: str, etym_no: int = 0, **changes: Any) -> Word:
    word = Word(
        lang=lang,
        key=key,
        etym_no=etym_no,
        form=form,
        is_reconstruction=form.startswith("*"),
        status=WordStatus.ENTRY,
        stub_reason=None,
        pos=("noun",),
        ety_ids=(),
        gloss=None,
        source_file=lang,
    )
    return dataclasses.replace(word, **changes)


def herz() -> Word:
    return entry("de", "Herz", "Herz", gloss="heart")


def bank(etym_no: int) -> Word:
    ety_id = {1: "bench", 2: "institution"}[etym_no]
    return entry("de", "Bank", "Bank", etym_no, ety_ids=(ety_id,))


def tegula() -> Word:
    return entry("la", "tegula", "tēgula", ety_ids=("tile",))


def herze() -> Word:
    return entry("gmh", "herze", "hërze")  # gmh rule maps ë -> e in the key only


def kerd_stub() -> Word:
    return Word(
        lang="ine-pro",
        key="*ḱérd",
        etym_no=0,
        form="*ḱérd",
        is_reconstruction=True,
        status=WordStatus.STUB,
        stub_reason=StubReason.NO_ENTRY,
        pos=(),
        ety_ids=(),
        gloss=None,
        source_file=None,
    )


def bank_page() -> Word:
    return dataclasses.replace(
        kerd_stub(),
        lang="de",
        key="Bank",
        form="Bank",
        is_reconstruction=False,
        status=WordStatus.AMBIGUOUS,
        stub_reason=None,
    )


# --- parse_etym_no -------------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "expected"), [(None, 0), ("1", 1), ("2", 2), ("12", 12)])
def test_parse_etym_no(raw: str | None, expected: int) -> None:
    assert parse_etym_no(raw) == expected


@pytest.mark.parametrize("raw", ["", "0", "-1", "one", "1.0"])
def test_parse_etym_no_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_etym_no(raw)


# --- word_id / link_id ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lang", "key", "etym_no", "expected"),
    [
        ("de", "Bank", 1, "w_7c61e3be992e8c3b"),
        ("de", "Bank", 2, "w_4895899959ea6fba"),
        ("de", "Herz", 0, HERZ_ID),
        ("gmh", "herze", 0, HERZE_ID),
        ("la", "tegula", 0, "w_7cc76174e4d3a920"),
        ("pl", "cegła", 0, "w_5c0ca1fc9e7ec0f3"),
        ("zlw-opl", "cegła", 0, "w_e19e4af33605fad4"),
        ("ine-pro", "*ḱérd", 0, "w_4c5f4574310e11c4"),
    ],
)
def test_word_id_matches_team_sample(lang: str, key: str, etym_no: int, expected: str) -> None:
    assert word_id(lang, key, etym_no) == expected


def test_word_id_separator_keeps_parts_apart() -> None:
    # Without SEP both pairs would hash the same bytes: "deab" + "c" == "dea" + "bc".
    assert word_id("de", "ab", 0) != word_id("dea", "b", 0)
    assert word_id("x", "a", 10) != word_id("x", "a1", 0)


@given(lang=st.text(min_size=1), key=st.text(min_size=1), etym_no=st.integers(0, 50))
def test_word_id_is_deterministic_and_well_formed(lang: str, key: str, etym_no: int) -> None:
    first = word_id(lang, key, etym_no)
    assert first == word_id(lang, key, etym_no)
    assert re.fullmatch(r"w_[0-9a-f]{16}", first)
    assert first != word_id(lang, key, etym_no + 1)


def test_link_id_matches_team_sample() -> None:
    assert link_id(HERZ_ID, HERZE_ID, LinkType.INH) == "l_330077d6764802a8"
    cegla_pl, cegla_opl = "w_5c0ca1fc9e7ec0f3", "w_e19e4af33605fad4"
    assert link_id(cegla_pl, cegla_opl, LinkType.INH) == "l_c5312a93dc0ac03d"


def test_link_id_depends_on_type_and_direction() -> None:
    inh = link_id(HERZ_ID, HERZE_ID, LinkType.INH)
    assert inh != link_id(HERZ_ID, HERZE_ID, LinkType.DER)  # parallel links stay apart
    assert inh != link_id(HERZE_ID, HERZ_ID, LinkType.INH)


# --- Word: valid words (ADR 0001 and the diacritics policy) --------------------------------


def test_homographs_are_two_words() -> None:
    bench, institution = bank(1), bank(2)
    assert bench.identity == ("de", "Bank", 1)
    assert institution.identity == ("de", "Bank", 2)
    assert bench.id == "w_7c61e3be992e8c3b"
    assert institution.id == "w_4895899959ea6fba"


def test_form_keeps_marks_key_is_for_lookup() -> None:
    word = tegula()
    assert (word.form, word.key) == ("tēgula", "tegula")
    assert word.id == "w_7cc76174e4d3a920"  # the id uses the key, not the form
    assert (herze().form, herze().key) == ("hërze", "herze")


def test_polish_letters_are_never_changed() -> None:
    cegla = entry("pl", "cegła", "cegła", ety_ids=("brick",))
    assert cegla.form == cegla.key == "cegła"
    assert cegla.id == "w_5c0ca1fc9e7ec0f3"


def test_sala_and_szala_style_pairs_are_different_words() -> None:
    assert entry("sh", "šala", "šala").id != entry("sh", "sala", "sala").id
    assert entry("de", "Bär", "Bär").id != entry("de", "Bar", "Bar").id


def test_case_is_part_of_the_key() -> None:
    # Wiktionary titles are case-sensitive: de "Bank" and a lowercase "bank" are different pages.
    assert entry("de", "Bank", "Bank").id != entry("de", "bank", "bank").id


def test_reconstruction_entry() -> None:
    bankiz = entry("gem-pro", "*bankiz", "*bankiz")
    assert bankiz.is_reconstruction
    assert bankiz.id == word_id("gem-pro", "*bankiz", 0)


def test_word_is_immutable_and_hashable() -> None:
    word = herz()
    with pytest.raises(dataclasses.FrozenInstanceError):
        word.form = "herz"  # type: ignore[misc]
    assert len({bank(1), bank(1), bank(2)}) == 2


@given(
    st.text(min_size=1)
    .map(lambda text: unicodedata.normalize("NFC", text))
    .filter(lambda text: not text.startswith("*"))
)
def test_form_is_stored_exactly(form: str) -> None:
    assert entry("pl", form, form).form == form


# --- Word: each case breaks exactly one rule of Word.__post_init__ -------------------------


@pytest.mark.parametrize(
    ("make", "changes"),
    [
        pytest.param(herz, {"lang": ""}, id="1-empty-lang"),
        pytest.param(herz, {"key": ""}, id="1-empty-key"),
        pytest.param(herz, {"form": ""}, id="1-empty-form"),
        pytest.param(herze, {"form": nfd("hërze")}, id="2-form-not-nfc"),
        pytest.param(kerd_stub, {"key": nfd("*ḱérd")}, id="2-key-not-nfc"),
        pytest.param(herz, {"etym_no": -1}, id="3-negative-etym-no"),
        pytest.param(herz, {"is_reconstruction": True}, id="4-flag-without-asterisk"),
        pytest.param(kerd_stub, {"is_reconstruction": False}, id="4-asterisk-without-flag"),
        pytest.param(kerd_stub, {"key": "ḱérd"}, id="4-key-lost-asterisk"),
        pytest.param(kerd_stub, {"form": "**ḱérd", "key": "**ḱérd"}, id="4-two-asterisks"),
        pytest.param(herz, {"stub_reason": StubReason.NO_ENTRY}, id="5-entry-with-reason"),
        pytest.param(kerd_stub, {"stub_reason": None}, id="5-stub-without-reason"),
        pytest.param(kerd_stub, {"etym_no": 1}, id="6-stub-with-etym-no"),
        pytest.param(bank_page, {"etym_no": 2}, id="6-page-with-etym-no"),
        pytest.param(kerd_stub, {"source_file": "ine-pro"}, id="6-stub-with-file"),
        pytest.param(kerd_stub, {"pos": ("noun",)}, id="6-stub-with-pos"),
        pytest.param(bank_page, {"ety_ids": ("bench",)}, id="6-page-with-ety-ids"),
        pytest.param(herz, {"source_file": None}, id="7-entry-without-file"),
        pytest.param(herz, {"pos": ()}, id="7-entry-without-pos"),
        pytest.param(herz, {"pos": ("verb", "noun")}, id="8-pos-unsorted"),
        pytest.param(herz, {"pos": ("noun", "noun")}, id="8-pos-duplicate"),
        pytest.param(tegula, {"ety_ids": ("tile", "roof")}, id="8-ety-ids-unsorted"),
    ],
)
def test_invalid_word_is_rejected(make: Any, changes: dict[str, Any]) -> None:
    make()  # the base word itself is valid
    with pytest.raises(ValueError):
        dataclasses.replace(make(), **changes)


# --- stub_word / page_word -----------------------------------------------------------------


def test_stub_word_for_missing_reconstruction() -> None:
    # de:Herz chain ends at ine-pro:*ḱérd, but the real entry is *ḱḗr (team sample).
    stub = stub_word("ine-pro", "*ḱérd", "*ḱérd", StubReason.NO_ENTRY)
    assert stub == kerd_stub()
    assert stub.id == "w_4c5f4574310e11c4"


def test_stub_word_for_language_not_loaded() -> None:
    # la:tēgula borrows from grc τάγηνον; grc is not in the sample build.
    stub = stub_word("grc", "τάγηνον", "τάγηνον", StubReason.NO_FILE)
    assert (stub.status, stub.stub_reason) == (WordStatus.STUB, StubReason.NO_FILE)
    assert not stub.is_reconstruction
    assert stub.id == "w_1f916a673fc778bd"


def test_page_word_cannot_collide_with_homographs() -> None:
    page = page_word("de", "Bank", "Bank")
    assert page == bank_page()
    assert page.identity == ("de", "Bank", 0)
    assert page.id not in {bank(1).id, bank(2).id}


# --- EtymLink ------------------------------------------------------------------------------


def herz_to_herze() -> EtymLink:
    """de:Herz <- gmh:hërze from {{ety|de|:inh|gmh:hërze|tree=1}} (sample l_330077d6764802a8)."""
    return EtymLink(
        src_word_id=HERZ_ID,
        dst_word_id=HERZE_ID,
        type=LinkType.INH,
        source_entry=HERZ_ID,
        source_file="de",
        template="ety",
        keyword=":inh",
        syntax=Syntax.ETY,
        extraction=Extraction.TEMPLATE,
        hop=0,
        target_lang_raw="gmh",
        target_form="hërze",
        target_sense_id=None,
        resolution=Resolution.RESOLVED,
        raw_template="{{ety|de|:inh|gmh:hërze|tree=1}}",
    )


def herze_to_herza() -> EtymLink:
    """Second chain step on the de:Herz page: gmh:hërze <- goh:hërza from {{inh|de|goh|hërza}}."""
    return dataclasses.replace(
        herz_to_herze(),
        src_word_id=HERZE_ID,
        dst_word_id=HERZA_ID,
        template="inh",
        keyword=None,
        syntax=Syntax.CLASSIC,
        extraction=Extraction.CHAIN,
        hop=1,
        target_lang_raw="goh",
        target_form="hërza",
        raw_template="{{inh|de|goh|hërza}}",
    )


def test_link_keeps_target_form_as_written() -> None:
    link = herz_to_herze()
    assert link.target_form == "hërze"  # the etymon's key is "herze"; the link keeps the source
    assert link.id == "l_330077d6764802a8"
    assert link.confidence == TEMPLATE_CONFIDENCE


def test_chain_link() -> None:
    link = herze_to_herza()
    assert link.source_entry == HERZ_ID  # found on the Herz page, but links hërze -> hërza
    assert link.id == link_id(HERZE_ID, HERZA_ID, LinkType.INH)
    assert link.confidence == CHAIN_CONFIDENCE


@pytest.mark.parametrize(
    ("make", "changes"),
    [
        pytest.param(herz_to_herze, {"hop": -1}, id="1-negative-hop"),
        pytest.param(herze_to_herza, {"hop": 0}, id="2-chain-at-hop-0"),
        pytest.param(herze_to_herza, {"keyword": ":inh"}, id="3-classic-with-keyword"),
        pytest.param(herz_to_herze, {"template": ""}, id="4-empty-template"),
        pytest.param(herz_to_herze, {"target_lang_raw": ""}, id="4-empty-lang"),
        pytest.param(herz_to_herze, {"target_form": ""}, id="4-empty-form"),
        pytest.param(herz_to_herze, {"target_form": nfd("hërze")}, id="5-form-not-nfc"),
    ],
)
def test_invalid_link_is_rejected(make: Any, changes: dict[str, Any]) -> None:
    make()
    with pytest.raises(ValueError):
        dataclasses.replace(make(), **changes)


def test_self_loop_is_allowed_here() -> None:
    # SELF_LOOP is counted and dropped by the build stage (ADR 0003), not a ValueError.
    link = dataclasses.replace(herz_to_herze(), dst_word_id=HERZ_ID)
    assert link.src_word_id == link.dst_word_id
