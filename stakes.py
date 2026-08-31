"""How much is at stake in a story, from what the reporting itself says.

WHY THIS EXISTS. Until 31/08/2026 the score was coverage x diversity x recency x
novelty, and none of those can tell a mass-casualty event from a scheduled one.
On 31/08 a NASA launch led on 0.180 while a ferry carrying 267 people capsized
off Cyprus and came second on 0.166 - with a THIRD more outlets. The launch won
on recency and diversity, which is exactly the failure mode: a launch is a diary
event every desk plans for, so its coverage is broad, well-spread and punctual,
while deaths at sea get whoever picks up the wire. Coverage was doing duty as a
proxy for consequence and it is a bad one.

WHAT IT IS NOT. It is not a model call and not an editorial judgement about which
subjects matter. It reads the cluster's own headlines and snippets for the two
things wire copy states plainly when they are true: that people were harmed, and
how many. A story that does not say so scores the floor, and the floor is high -
this dimension is meant to break a tie between a disaster and a launch, not to
bury everything that is not a disaster.

THE FLOOR IS THE SAFETY PROPERTY. The overall score is multiplicative, so a
stakes of 0 would delete a story rather than rank it. Nothing here may return
below FLOOR.
"""
from __future__ import annotations

import math
import re

#: Words wire copy uses for people harmed. Deliberately narrow: every one of
#: these is a direct statement about human beings, not a metaphor. "Devastated",
#: "crisis" and "tragedy" are absent on purpose - they are editorial colour and
#: including them would make this a subject-matter preference rather than a
#: reading of the facts reported.
#: "death" SINGULAR is here because the tests went looking and it was absent:
#: "Death toll nears 800" then matched nothing at all, so the single most
#: common phrasing in disaster reporting scored the floor.
VICTIM = ("killed|dead|death|deaths|died|die|dies|fatalities|missing|injured|"
          "wounded|casualties|unaccounted|bodies")

_WORDNUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "hundreds": 100,
    "thousand": 1000, "thousands": 1000, "dozens": 24,
}
_SCALE = {"hundred": 100, "thousand": 1000, "million": 1_000_000}

#: The digit run must not END on a comma. It did until this was written, so
#: "Woman, 22, killed" parsed as twenty-two dead and a single shooting scored the
#: same as a ferry disaster. Thousands separators still work: "3,000 missing".
_NUM = (r"(?:(\d(?:[\d,]*\d)?)|(" + "|".join(_WORDNUM) + r"))"
        r"(?:\s+(hundred|thousand|million))?")

#: "Eight killed", "at least 17 missing", "eight people died".
_LEAD = re.compile(
    _NUM + r"(?:\s+(?:people|passengers|others|persons|residents|civilians))?"
    r"\s+(?:" + VICTIM + r")\b", re.I)
#: "death toll rises to 762", "kills 1".
_TRAIL = re.compile(
    r"(?:death toll|toll)\s+(?:\w+\s+){0,3}?" + _NUM
    + r"|\bkill(?:s|ed)\s+(?:at least\s+)?" + _NUM, re.I)
#: An age in apposition, which reads exactly like a body count and is not one.
_AGE = re.compile(r"\b(?:man|woman|boy|girl|child|teenager|worker|driver|student|"
                  r"officer|soldier|victim|italian|briton)\s*,\s*(\d{1,2})\b", re.I)
_HAS_VICTIM = re.compile(r"\b(?:" + VICTIM + r")\b", re.I)
#: "no one injured", "nobody was killed" - the whole point of the sentence is
#: that nothing happened, and "one" would otherwise be read as a body count.
_NEGATED = re.compile(r"\b(?:no ?one|nobody|none|no)\s+(?:\w+\s+){0,2}?(?:"
                      + VICTIM + r")\b", re.I)

#: A story that reports no harm is not worthless, so this is well above zero. It
#: is the score for most days' politics, sport and business.
FLOOR = 0.55
#: Where the log curve tops out. Set at 2,000 because that is roughly where a
#: reader stops distinguishing magnitudes - 2,000 dead and 20,000 dead are both
#: simply enormous - and because clusters above it are rare enough that the
#: curve's shape there is untestable.
_SATURATE = 2000


def _value(digits: str | None, word: str | None, scale: str | None) -> float:
    if digits:
        try:
            v = float(digits.replace(",", ""))
        except ValueError:
            return 0.0
    elif word:
        v = float(_WORDNUM[word.lower()])
    else:
        return 0.0
    return v * _SCALE[scale.lower()] if scale else v


def casualties(text: str) -> float:
    """The largest number of people the text says were harmed.

    The MAXIMUM across outlets, not a consensus: early wire copy undercounts and
    the figure climbs all day, so taking the highest is taking the freshest.
    """
    text = _NEGATED.sub(" ", text)
    ages = {m.group(1) for m in _AGE.finditer(text)}
    best = 0.0
    for pattern in (_LEAD, _TRAIL):
        for m in pattern.finditer(text):
            groups = m.groups()
            for i in range(0, len(groups), 3):
                digits, word, scale = groups[i], groups[i + 1], groups[i + 2]
                if digits and digits in ages:
                    continue
                if digits and not scale and "," not in digits \
                        and 1900 <= _value(digits, None, None) <= 2100:
                    continue                      # a year, not a body count
                v = _value(digits, word, scale)
                if 1 <= v <= 5_000_000:
                    best = max(best, v)
    return best


def text_of(members: list[dict]) -> str:
    return " ".join((m.get("title") or "") + " " + (m.get("snippet") or "")
                    for m in members)


def stakes(members: list[dict]) -> tuple[float, float]:
    """Return (score in [FLOOR, 1], the casualty figure found)."""
    text = text_of(members)
    if not _HAS_VICTIM.search(_NEGATED.sub(" ", text)):
        return FLOOR, 0.0
    n = casualties(text)
    # Log-scaled. One death is not one eight-hundredth of eight hundred, but it
    # is not the same either, and a linear scale would let one enormous event
    # flatten every other story for days.
    frac = math.log10(max(n, 1.0) + 1) / math.log10(_SATURATE + 1)
    return FLOOR + (1 - FLOOR) * min(1.0, 0.25 + 0.75 * frac), n
