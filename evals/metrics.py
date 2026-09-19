"""
Deterministic scorers for generated episode summaries.

Design rule: every metric in here is computable from the transcript and the
model output alone, with no second model call, and every one of them can be
argued for in a review. An LLM judge is available as an *extra* signal in live
mode (see ``harness.judge_case``) but it is never part of the gated score,
because a judge that drifts silently is worse than no judge at all.

Each scorer returns a ``MetricResult`` with a score in [0, 1] and a one-line
human-readable detail string. A scorer returns ``score=None`` when the metric
is genuinely not applicable to a case (for example, grounding when the source
transcript contains no extractable entities at all). ``None`` is dropped from
the weighted mean rather than counted as zero - scoring an inapplicable metric
as a failure would punish the near-empty case for the harness's own limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# The pipeline's own narration-speed assumption.
#
# media/media_utils.py::create_silent_audio_fallback estimates runtime as
# ``word_count / 2.5`` and its comment names the figure: "~150 WPM reading
# speed". Length adherence is measured against that number rather than an
# invented one, so this metric tracks what the renderer will actually do with
# the script.
# ---------------------------------------------------------------------------
WORDS_PER_MINUTE = 150.0

# Within this fraction of target, length is considered on-spec; beyond
# FAIL_BAND it scores zero, with a linear ramp between the two.
LENGTH_OK_BAND = 0.35
LENGTH_FAIL_BAND = 1.0

# Instructions the summarisation prompt actually issues, which the rubric then
# checks the model for obeying. Kept next to the checks so that the prompt
# contract and the scorers cannot drift apart unnoticed - see
# ``check_prompt_contract``.
REQUIRED_PROMPT_DIRECTIVES = (
    "ask watchers to Like, Comment, and subscribe",
    "Do not do an introduction",
)

CTA_TERMS = {
    "like": re.compile(r"\blik(?:e|ing)\b", re.IGNORECASE),
    "comment": re.compile(r"\bcomment(?:s|ing)?\b", re.IGNORECASE),
    "subscribe": re.compile(r"\bsubscrib(?:e|ing|ers?)\b", re.IGNORECASE),
}

# Openers that mean the model ignored "Do not do an introduction". Matched only
# against the first ~200 characters, because a "welcome back" in the middle of a
# recap is narration, not an introduction.
INTRO_PATTERNS = (
    re.compile(r"\b(?:hey|hi|hello|yo)\b[, ]+(?:guys|everyone|folks|there|all)", re.IGNORECASE),
    re.compile(r"\bwelcome (?:back|to)\b", re.IGNORECASE),
    re.compile(r"\bwhat'?s up\b", re.IGNORECASE),
    re.compile(r"\bin (?:this|today'?s) video\b", re.IGNORECASE),
    re.compile(r"\btoday (?:we'?re|we are|we'?ll|i'?m)\b", re.IGNORECASE),
    re.compile(r"\bbefore we (?:get )?(?:start|begin|dive)", re.IGNORECASE),
    re.compile(r"\b(?:it'?s your boy|my name is|this is) .{0,30}\bTLDR\b", re.IGNORECASE),
    re.compile(r"\bTLDR Media\b.{0,40}\b(?:here|back)\b", re.IGNORECASE),
)

REFUSAL_PATTERNS = (
    re.compile(r"\bi'?m sorry\b", re.IGNORECASE),
    re.compile(r"\bi (?:can'?t|cannot|am unable to)\b", re.IGNORECASE),
    re.compile(r"\bas an ai\b", re.IGNORECASE),
    re.compile(r"\bi don'?t have (?:access|enough)\b", re.IGNORECASE),
    re.compile(r"\bunable to (?:summar|generate|provide)", re.IGNORECASE),
    re.compile(r"\bno (?:transcript|content) (?:was )?(?:provided|available)\b", re.IGNORECASE),
)

MIN_SCRIPT_WORDS = 20

# Capitalised tokens that are never entities. Deliberately short: over-filtering
# hides real misses, and the "not at sentence start" rule below already removes
# most of the noise.
_ENTITY_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can could did do does for from had has have he her hers him
    his how i if in into is it its me my no not of on or our she should so some that the their them
    then there these they this those to too us was we were what when where which who why will with
    would you your not don't episode season show transcript scene end cut int ext sfx vo v.o narrator
    captain marshal mr mrs ms dr sir madam yes okay ok well now here just still then thing things
    one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
    seventeen eighteen nineteen twenty thirty forty fifty hundred thousand first second third
    """.split()
)

_SPEAKER_RE = re.compile(r"^[\s>*\-|0-9:.\[\]]*([A-Za-z][A-Za-z'\-. ]{1,28}?)\s*:", re.MULTILINE)
_SPEAKER_PREFIX_RE = re.compile(r"^[\s>*\-|0-9:.\[\]]*[A-Za-z][A-Za-z'\-. ]{1,28}?\s*:\s*")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|[a-zA-Z]+);")


@dataclass
class MetricResult:
    """One scored metric for one case."""

    name: str
    score: float | None
    detail: str
    weight: float = 0.0
    # Only set by the grounding scorer; feeds the hallucination cap below.
    invented_fraction: float = 0.0

    @property
    def applicable(self) -> bool:
        return self.score is not None


@dataclass
class CaseScore:
    """Every metric for one case, plus the weighted aggregate."""

    case_id: str
    metrics: list[MetricResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cap: float = 1.0
    cap_reason: str = ""

    @property
    def weighted_score(self) -> float:
        applicable = [m for m in self.metrics if m.applicable and m.weight > 0]
        total_weight = sum(m.weight for m in applicable)
        if total_weight == 0:
            return 0.0
        return sum((m.score or 0.0) * m.weight for m in applicable) / total_weight

    @property
    def score(self) -> float:
        return min(self.weighted_score, self.cap)

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "score": round(self.score, 4),
            "weighted_score": round(self.weighted_score, 4),
            "cap": round(self.cap, 4),
            "cap_reason": self.cap_reason,
            "metrics": {
                m.name: {
                    "score": None if m.score is None else round(m.score, 4),
                    "weight": m.weight,
                    "detail": m.detail,
                }
                for m in self.metrics
            },
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def canonical(token: str) -> str:
    """Lowercase a token and drop possessives and edge punctuation, so that
    ``Bardo's`` and ``Bardo`` are the same entity. Without this the grounding
    check reports every possessive in the output as an invented name."""
    key = token.lower().strip("'’-.")
    for suffix in ("'s", "’s"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    return key


def normalise(text: str) -> str:
    """Strip the formatting noise case 04 is built out of, so entity extraction
    sees words rather than markup."""
    text = _HTML_ENTITY_RE.sub(" ", text)
    text = re.sub(r"\d{2}:\d{2}:\d{2}", " ", text)
    text = re.sub(r"[<>/*=|\[\]]+", " ", text)
    return text


def extract_entities(transcript: str) -> dict[str, int]:
    """
    Pull named entities out of a transcript deterministically.

    Two sources, both cheap and both explainable:

    1. Speaker labels - ``NAME:`` at the start of a line. These are the most
       reliable entity signal a transcript has.
    2. Capitalised tokens that are *not* the first word of a sentence. A word
       that is capitalised mid-sentence is a proper noun far more often than
       not, and the sentence-start rule removes the bulk of false positives
       without needing a POS tagger or a model.

    Returns ``{lowercased entity: occurrence count}``. No NER model, no network,
    no nondeterminism - which is the whole point.
    """
    text = normalise(transcript)
    counts: dict[str, int] = {}

    def bump(token: str) -> None:
        key = canonical(token)
        if len(key) < 3 or key in _ENTITY_STOPWORDS or not key[0].isalpha():
            return
        counts[key] = counts.get(key, 0) + 1

    for raw_speaker in _SPEAKER_RE.findall(text):
        for token in _WORD_RE.findall(raw_speaker):
            # A speaker label is an entity even when it is shouted in caps.
            if token[0].isupper() or token.isupper():
                bump(token)

    for line in text.splitlines():
        # Drop the "NAME:" prefix first, otherwise the real first word of the
        # line sits at index 1 and gets read as a mid-sentence proper noun.
        body = _SPEAKER_PREFIX_RE.sub("", line, count=1)
        for sentence in _SENTENCE_SPLIT_RE.split(body):
            tokens = _WORD_RE.findall(sentence)
            for index, token in enumerate(tokens):
                if index == 0:
                    continue  # sentence-initial capitalisation carries no signal
                # Title case only: ALL-CAPS tokens are shouting and scene
                # headers, which the speaker-label pass already covers.
                if token[0].isupper() and not token.isupper():
                    bump(token)

    return counts


def mentions_any(text: str, entities: list[str]) -> list[str]:
    """Entities from ``entities`` that appear in ``text`` on a word boundary."""
    lowered = text.lower()
    hits = []
    for entity in entities:
        if re.search(rf"\b{re.escape(entity)}", lowered):
            hits.append(entity)
    return hits


def word_count(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------


def score_schema_validity(
    summary: dict | None, case: dict, parse_error: str | None
) -> MetricResult:
    """
    Did the call produce something that satisfies ``Episode_Summary_Schema``,
    and does it describe the episode we asked about?

    Split into four equal parts rather than a single boolean, so a partial
    failure (right shape, wrong episode number) is visible as a partial score
    instead of collapsing to zero alongside a total parse failure.
    """
    if parse_error is not None:
        return MetricResult("schema_validity", 0.0, f"did not parse: {parse_error}", weight=0.20)
    if summary is None:
        return MetricResult("schema_validity", 0.0, "no output", weight=0.20)

    checks = {
        "parsed": True,
        "show_matches": str(summary.get("show", "")).strip().lower()
        == case["show"].strip().lower(),
        "season_matches": str(summary.get("season", "")).strip().lstrip("0")
        == case["season"].strip().lstrip("0"),
        "episode_matches": str(summary.get("episode", "")).strip().lstrip("0")
        == case["episode"].strip().lstrip("0"),
    }
    failed = [name for name, ok in checks.items() if not ok]
    score = sum(checks.values()) / len(checks)
    detail = (
        "schema ok, identity fields match" if not failed else f"mismatched: {', '.join(failed)}"
    )
    return MetricResult("schema_validity", score, detail, weight=0.20)


def score_output_present(summary: dict | None) -> MetricResult:
    """
    Refusal / empty-output rate.

    Three things have to hold: a narration script long enough to be worth
    rendering, at least one plot point, and no refusal boilerplate. Refusals are
    scored as failures *here* on purpose - a refusal may be the honest answer
    (see the near_empty case), but it is still an episode the pipeline cannot
    render, so the number has to show it. The docs say so explicitly.
    """
    if summary is None:
        return MetricResult("output_present", 0.0, "no output", weight=0.10)

    script = str(summary.get("youtube_transcript") or "")
    points = [p for p in (summary.get("plot_points") or []) if str(p).strip()]
    words = word_count(script)

    refusals = [p.pattern for p in REFUSAL_PATTERNS if p.search(script)]
    parts = {
        "script_long_enough": words >= MIN_SCRIPT_WORDS,
        "has_plot_points": bool(points),
        "no_refusal": not refusals,
    }
    score = sum(parts.values()) / len(parts)
    bits = [f"{words} words", f"{len(points)} plot points"]
    if refusals:
        bits.append("refusal language detected")
    return MetricResult("output_present", score, ", ".join(bits), weight=0.10)


def source_vocabulary(transcript: str) -> set[str]:
    """Every word that appears anywhere in the transcript, lowercased. Used as
    the negative check: a name absent from this set appears nowhere in the
    source, so a plot point asserting it invented it."""
    return {canonical(w) for w in _WORD_RE.findall(normalise(transcript))}


def score_plot_point_grounding(summary: dict | None, transcript: str) -> MetricResult:
    """
    Plot-point grounding: is each generated plot point anchored in the source?

    The closest deterministic proxy for hallucination that does not need a
    second model. Each plot point is graded on two deterministic signals:

    * **supported** - it names at least one entity extracted from the transcript.
    * **unsupported names** - it introduces a capitalised name that appears
      *nowhere* in the transcript text (checked against the full source
      vocabulary, not just the extracted entities, so paraphrase of a lowercase
      noun is not punished).

    Scoring per plot point:

    ==========================================  =====
    supported, no invented names                1.0
    generic - names nothing either way          0.5
    introduces a name absent from the source    0.0
    ==========================================  =====

    The middle rung is what makes the near-empty case work. When the transcript
    is empty, an honest "no content was available" plot point scores 0.5 while a
    confident invented cast scores 0.0 - so a fluent hallucination scores
    strictly worse than an honest shrug, which is the behaviour we want to
    reward and the reason this case is in the golden set at all.
    """
    if summary is None:
        return MetricResult("plot_point_grounding", 0.0, "no output", weight=0.20)

    points = [str(p) for p in (summary.get("plot_points") or []) if str(p).strip()]
    if not points:
        return MetricResult("plot_point_grounding", 0.0, "no plot points", weight=0.20)

    entities = list(extract_entities(transcript))
    vocabulary = source_vocabulary(transcript)

    grounded = generic = invented = 0
    invented_names: list[str] = []
    for point in points:
        names = set(extract_entities(point))
        foreign = sorted(n for n in names if n not in vocabulary)
        if foreign:
            invented += 1
            invented_names.extend(foreign)
        elif entities and mentions_any(point, entities):
            grounded += 1
        else:
            generic += 1

    score = (grounded + 0.5 * generic) / len(points)
    detail = f"{grounded} grounded / {generic} generic / {invented} invented, of {len(points)}"
    if invented_names:
        unique = sorted(set(invented_names))[:5]
        detail += f" (not in source: {', '.join(unique)})"
    result = MetricResult("plot_point_grounding", score, detail, weight=0.30)
    result.invented_fraction = invented / len(points)
    return result


def score_entity_coverage(summary: dict | None, transcript: str, top_n: int = 5) -> MetricResult:
    """
    The recall half of grounding: of the ``top_n`` most frequent entities in the
    transcript, how many appear anywhere in the generated output?

    Grounding alone is satisfiable by a summary that names one character and
    ignores the rest, which is the ensemble-episode failure mode. This catches
    that. Frequency-ranked rather than hand-labelled, so adding a case does not
    mean hand-writing an answer key.
    """
    counts = extract_entities(transcript)
    if not counts:
        return MetricResult(
            "entity_coverage", None, "n/a: no entities in source transcript", weight=0.10
        )
    ranked = sorted(counts, key=lambda k: (-counts[k], k))[:top_n]
    if summary is None:
        return MetricResult("entity_coverage", 0.0, "no output", weight=0.10)

    haystack = " ".join(
        [str(summary.get("youtube_transcript") or "")]
        + [str(p) for p in (summary.get("plot_points") or [])]
    )
    hits = mentions_any(haystack, ranked)
    missed = [e for e in ranked if e not in hits]
    detail = f"{len(hits)}/{len(ranked)} top entities mentioned"
    if missed:
        detail += f" (missed: {', '.join(missed)})"
    return MetricResult("entity_coverage", len(hits) / len(ranked), detail, weight=0.10)


def score_length_adherence(summary: dict | None, target_minutes: float) -> MetricResult:
    """
    Does the narration script imply a runtime near the case's target?

    Target word count is ``target_minutes * 150``, taken from the pipeline's own
    words-per-minute assumption rather than a number picked here. Full marks
    inside +/-35%, zero at half or double, linear in between.

    Worth stating plainly: the episode prompt in
    ``WorkflowOrchestrator.generate_structured_summary`` never tells the model a
    target length, so this metric is measuring an unconstrained variable. That
    is a finding about the prompt, not a defect in the metric, and it is why
    this carries a modest weight.
    """
    if summary is None:
        return MetricResult("length_adherence", 0.0, "no output", weight=0.10)

    target = target_minutes * WORDS_PER_MINUTE
    actual = word_count(str(summary.get("youtube_transcript") or ""))
    deviation = abs(actual - target) / target

    if deviation <= LENGTH_OK_BAND:
        score = 1.0
    elif deviation >= LENGTH_FAIL_BAND:
        score = 0.0
    else:
        score = 1.0 - (deviation - LENGTH_OK_BAND) / (LENGTH_FAIL_BAND - LENGTH_OK_BAND)

    return MetricResult(
        "length_adherence",
        score,
        f"{actual} words vs {target:.0f} target ({target_minutes:g} min @ "
        f"{WORDS_PER_MINUTE:g} wpm), {deviation:+.0%} off",
        weight=0.10,
    )


def score_cta_compliance(summary: dict | None) -> MetricResult:
    """
    The prompt says: "Make sure to ask watchers to Like, Comment, and subscribe
    somewhere in the video." One point per term actually present in the script.

    Checking whether the model obeyed an instruction its own prompt issued is
    the cheapest high-signal eval available for a generation system: it is
    unambiguous, it needs no reference output, and it regresses loudly when a
    prompt edit drops a requirement.
    """
    if summary is None:
        return MetricResult("cta_compliance", 0.0, "no output", weight=0.10)
    script = str(summary.get("youtube_transcript") or "")
    found = [term for term, pattern in CTA_TERMS.items() if pattern.search(script)]
    missing = [t for t in CTA_TERMS if t not in found]
    detail = (
        "like/comment/subscribe all present" if not missing else f"missing: {', '.join(missing)}"
    )
    return MetricResult("cta_compliance", len(found) / len(CTA_TERMS), detail, weight=0.10)


def score_no_intro_compliance(summary: dict | None) -> MetricResult:
    """
    The prompt says: "Do not do an introduction." Checks the opening ~200
    characters of the script for channel-intro boilerplate.

    Binary on purpose. An introduction either is or is not there, and a partial
    credit scheme here would only blur the signal.
    """
    if summary is None:
        return MetricResult("no_intro_compliance", 0.0, "no output", weight=0.10)
    opening = str(summary.get("youtube_transcript") or "")[:200]
    hits = [p.pattern for p in INTRO_PATTERNS if p.search(opening)]
    if hits:
        return MetricResult(
            "no_intro_compliance",
            0.0,
            f"opened with an introduction ({len(hits)} pattern(s) matched)",
            weight=0.10,
        )
    return MetricResult("no_intro_compliance", 1.0, "no introduction in the opening", weight=0.10)


# A summary that asserts invented named entities is not a usable output, no
# matter how well-formed the rest of it is. Six of the seven metrics score form
# rather than truth, so without this the weighted mean would hand a fluent
# hallucination ~0.70. The cap makes the case score fall with the fraction of
# invented plot points, floored so the number stays comparable run to run.
HALLUCINATION_CAP_FLOOR = 0.25


def score_case(
    summary: dict | None, case: dict, transcript: str, parse_error: str | None
) -> CaseScore:
    """Run the whole rubric against one case."""
    result = CaseScore(case_id=case["id"])
    result.metrics = [
        score_schema_validity(summary, case, parse_error),
        score_output_present(summary),
        score_plot_point_grounding(summary, transcript),
        score_entity_coverage(summary, transcript),
        score_length_adherence(summary, float(case["target_minutes"])),
        score_cta_compliance(summary),
        score_no_intro_compliance(summary),
    ]

    invented = next(
        (m.invented_fraction for m in result.metrics if m.name == "plot_point_grounding"), 0.0
    )
    if invented > 0:
        result.cap = max(HALLUCINATION_CAP_FLOOR, 1.0 - invented)
        result.cap_reason = (
            f"{invented:.0%} of plot points name entities absent from the source; "
            f"case score capped at {result.cap:.2f}"
        )

    if parse_error:
        result.errors.append(parse_error)
    return result


# ---------------------------------------------------------------------------
# Prompt contract
# ---------------------------------------------------------------------------


def check_prompt_contract(rendered_prompt: str) -> tuple[bool, list[str]]:
    """
    Assert the prompt the pipeline actually renders still issues the
    instructions this rubric scores the model for obeying.

    This is what stops offline mode from being a tautology. The recorded
    fixtures cannot react to a prompt change, but *this* check can: delete "Do
    not do an introduction" from ``generate_structured_summary`` and the offline
    run fails, because the harness is now scoring obedience to an instruction
    nobody is issuing.
    """
    missing = [d for d in REQUIRED_PROMPT_DIRECTIVES if d.lower() not in rendered_prompt.lower()]
    return (not missing, missing)
