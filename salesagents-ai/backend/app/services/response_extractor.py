"""Deterministic customer-response extractor (text MVP, no LLM).

Converts natural-language utterances into structured qualification fields.
Architecture: text -> extract() -> QualificationService -> EligibilityService.
"""

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.models.qualification import IncomeMode, OccupationType, OwnershipStatus, PropertyType

LAKH = Decimal("100000")
CRORE = Decimal("10000000")
MILLION = Decimal("1000000")

# --- control intents (same semantics as the former route keyword lists) ---
AFFIRMATIVE_WORDS = ("yes", "yeah", "yep", "sure", "okay", "this is", "speaking", "i am")
NEGATIVE_WORDS = ("no,", "no.", " not ", "wrong", "not me", "not interested")
BUSY_WORDS = ("busy", "meeting", "later", "call back", "callback", "not now")
TRANSFER_WORDS = (
    "existing loan",
    "already have",
    "balance transfer",
    "transfer",
    "reduce",
    "lower my",
    "top-up",
    "topup",
)


def _contains(text: str, words) -> bool:
    padded = f" {text.lower()} "
    return any(w in padded for w in words)


def is_affirmative(text: str) -> bool:
    return _contains(text, AFFIRMATIVE_WORDS)


def is_negative(text: str) -> bool:
    return _contains(text, NEGATIVE_WORDS)


def is_busy(text: str) -> bool:
    return _contains(text, BUSY_WORDS)


def is_transfer_request(text: str) -> bool:
    return _contains(text, TRANSFER_WORDS)


def _res(*patterns: str):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# --- ₹75L downgrade confirmation answers (dedicated, stricter than bare yes/no) ---
DOWNGRADE_DECLINE_RES = _res(
    r"^\s*no\b", r"\bnope\b", r"\bnah\b",
    r"don't want", r"do not want", r"not interested", r"not required",
    r"too much", r"too high", r"no thanks?", r"not proceed", r"don'?t proceed",
    r"\bcancel\b", r"\bdrop\b", r"no need", r"\bwrong\b", r" not ", r"\bno[,.]",
)
DOWNGRADE_ACCEPT_RES = _res(
    r"proceed", r"\bfine\b", r"\bworks?\b", r"\bok(ay)?\b", r"acceptable",
    r"\bagree", r"continue", r"\bdeal\b", r"sounds good", r"go ahead",
    r"\byes\b", r"\byeah\b", r"\byep\b", r"\bsure\b",
)


def downgrade_answer(text: str) -> Optional[bool]:
    """Resolve the pending ₹75L confirmation: True=accept, False=decline,
    None=unclear (re-ask). Decline patterns win on contradiction."""
    if any(rx.search(text) for rx in DOWNGRADE_DECLINE_RES):
        return False
    if any(rx.search(text) for rx in DOWNGRADE_ACCEPT_RES):
        return True
    return None


# --- qualification patterns (regex, word boundaries where it matters) ---


AGRICULTURAL_RES = _res(r"agricultur\w*", r"farmland", r"\bfarms?\b")
INDUSTRIAL_RES = _res(r"industr\w*", r"factor(?:y|ies)", r"warehouses?", r"godowns?", r"\bplants?\b")
COMMERCIAL_RES = _res(r"commercial", r"\bshops?\b", r"showrooms?", r"\boffices?\b")
RESIDENTIAL_RES = _res(
    r"residential", r"\bhouses?\b", r"\bhomes?\b", r"apartments?",
    r"\bflats?\b", r"villas?", r"\bresidence\b",
)
PROPERTY_BY_TYPE: List[Tuple[Any, list]] = [
    (PropertyType.AGRICULTURAL, AGRICULTURAL_RES),
    (PropertyType.INDUSTRIAL, INDUSTRIAL_RES),
    (PropertyType.COMMERCIAL, COMMERCIAL_RES),
    (PropertyType.RESIDENTIAL, RESIDENTIAL_RES),
]
# Mentioned the topic without a recognizable type -> ask, don't guess.
AMBIGUOUS_PROPERTY_RE = re.compile(r"\b(land|plot|site|premises)\b", re.IGNORECASE)

JOINT_RES = _res(
    r"joint", r"co-own", r"co own", r"co-?owners?",
    r"\bme and my\b", r"with my ",
    r"\bmy (wife|husband|brother|sister|father|mother|family|partner|son|daughter)\b",
    r"\bboth (of us|own|owners?)\b", r"\bour (house|home|property)\b", r"shared ownership",
    r"\bwe own\b", r"own .*together", r"together .*own",
    r"multiple (people|owners?|members?)", r"owned by .* and ",
)
SOLE_RES = _res(
    r"\bsole\b", r"solely", r"single owners?", r"single ownership",
    r"only owner", r"only mine", r"\bit'?s (only )?mine\b", r"\bit is (only )?mine\b",
    r"self owned", r"owned by me", r"\bi own\b", r"\bmy own\b",
    r"under my name", r"mine alone", r"i'?m the only",
)

DOCS_POS_RES = _res(r"originals?", r"original documents?", r"original deed", r"title deeds?", r"registr\w*")
DOCS_NEG_RES = _res(
    r"photocop\w*", r"photostat", r"xerox", r"\bcop(?:y|ies)\b", r"duplicates?",
    r"\blost\b", r"\bmissing\b", r"don't have", r"do not have",
    r"not available", r"\bunavailable\b", r"\bno documents?\b",
)

SELF_RES = _res(
    r"self[-\s]?employed", r"\bbusiness\b", r"businessm[ae]n", r"businesswoman",
    r"own business", r"run my own", r"my own business", r"freelanc\w*",
)
SALARIED_RES = _res(
    r"salaried", r"\bsalary\b", r"\bemployee\b", r"\bemployed\b",
    r"working for", r"\bworks? at\b", r"\bjobs?\b",
)

BANK_RES = _res(r"\bbank\b", r"accounts?", r"credited", r"direct deposit", r"bank transfer", r"\bneft\b", r"\brtgs\b", r"\bupi\b")
CASH_RES = _res(r"\bcash\b", r"in hand", r"paid in cash", r"cash income", r"\bby hand\b")

AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(lakhs?|crores?|million|l\b|cr\b)?",
    re.IGNORECASE,
)
MARKET_CTX_RES = _res(r"worth", r"\bvalue\b", r"market", r"\bcost", r"valued?", r"\bprice")
UNIT_MULTIPLIERS = {"lakh": LAKH, "lakhs": LAKH, "l": LAKH, "crore": CRORE, "crores": CRORE, "cr": CRORE, "million": MILLION}

TENURE_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", re.IGNORECASE)
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30,
}
TENURE_WORD_RE = re.compile(
    r"\b(" + "|".join(NUMBER_WORDS) + r")\s*(?:years?|yrs?)\b", re.IGNORECASE
)


def _last_match(text: str, patterns: list) -> Optional[re.Match]:
    best: Optional[re.Match] = None
    for rx in patterns:
        for m in rx.finditer(text):
            if best is None or m.start() >= best.start():
                best = m
    return best


def _extract_property(text: str) -> Optional[PropertyType]:
    hits: List[Tuple[int, Any]] = []
    for ptype, patterns in PROPERTY_BY_TYPE:
        for rx in patterns:
            for m in rx.finditer(text):
                hits.append((m.start(), ptype))
    if not hits:
        return None
    return max(hits, key=lambda h: h[0])[1]


def ambiguous_property(text: str) -> bool:
    """Topic mentioned ('land'/'plot') but no recognizable type: don't guess."""
    if _extract_property(text) is not None:
        return False
    return AMBIGUOUS_PROPERTY_RE.search(text) is not None


def _extract_binary(text: str, pos: list, neg: list) -> Optional[bool]:
    last_pos = _last_match(text, pos)
    last_neg = _last_match(text, neg)
    if last_pos is None and last_neg is None:
        return None
    if last_pos is None:
        return False
    if last_neg is None:
        return True
    return last_pos.start() >= last_neg.start()


LOAN_CTX_RES = _res(r"\bneed\b", r"\bwant\b", r"requir\w*", r"\bborrow", r"looking for", r"\bloan\b")

def _extract_amounts(text: str, prefer: Optional[str] = None) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Split amounts into (loan, market). Explicit context keywords win;
    context-free amounts follow `prefer` (current question), else loan."""
    loan: Optional[Decimal] = None
    market: Optional[Decimal] = None
    for m in AMOUNT_RE.finditer(text):
        num = m.group(1).replace(",", "")
        unit = (m.group(2) or "").lower()
        try:
            value = Decimal(num)
        except Exception:
            continue
        if unit:
            value = value * UNIT_MULTIPLIERS[unit]
        else:
            # Bare numbers: accept plausible loan figures only (5-8 digits),
            # so ages/phone numbers/tenures never become loan amounts.
            digits = len(num.split(".")[0])
            if digits < 5 or digits > 8:
                continue
        start, end = m.span()
        context = text[max(0, start - 25): end + 25]
        if any(rx.search(context) for rx in MARKET_CTX_RES):
            market = value
        elif any(rx.search(context) for rx in LOAN_CTX_RES):
            loan = value
        elif prefer == "market_value":
            market = value
        else:
            loan = value
    return loan, market


def _extract_tenure(text: str, prefer: Optional[str] = None) -> Optional[int]:
    found: Optional[int] = None
    for m in TENURE_YEARS_RE.finditer(text):
        try:
            found = int(float(m.group(1)))
        except ValueError:
            continue
    for m in TENURE_WORD_RE.finditer(text):
        found = NUMBER_WORDS[m.group(1).lower()]
    if found is not None or prefer != "tenure":
        return found
    # Bare short answers ("10", "ten") resolve against the active question.
    stripped = text.strip().lower().rstrip(" .!?")
    if re.fullmatch(r"\d{1,3}", stripped):
        return int(stripped)
    if stripped in NUMBER_WORDS:
        return NUMBER_WORDS[stripped]
    if any(m.group(2) for m in AMOUNT_RE.finditer(text)):
        return None  # unit amounts belong to loan/market routing
    m = re.search(r"(?<!\d)(\d{1,2})(?!\d)", text)
    if m:
        return int(m.group(1))
    if not re.search(r"\bno one\b", text, re.IGNORECASE):
        wm = re.search(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", text, re.IGNORECASE)
        if wm:
            return NUMBER_WORDS[wm.group(1).lower()]
    return None


def _extract_occupation(text: str) -> Optional[OccupationType]:
    self_spans = [m.span() for rx in SELF_RES for m in rx.finditer(text)]

    def _overlaps_self(span) -> bool:
        return any(span[0] < s[1] and s[0] < span[1] for s in self_spans)

    sal_matches = [
        m for rx in SALARIED_RES for m in rx.finditer(text) if not _overlaps_self(m.span())
    ]
    self_matches = [m for rx in SELF_RES for m in rx.finditer(text)]
    if not self_matches and not sal_matches:
        return None
    last_self = max(self_matches, key=lambda m: m.start(), default=None)
    last_sal = max(sal_matches, key=lambda m: m.start(), default=None)
    if last_self is None:
        return OccupationType.SALARIED
    if last_sal is None:
        return OccupationType.SELF_EMPLOYED
    return OccupationType.SELF_EMPLOYED if last_self.start() >= last_sal.start() else OccupationType.SALARIED


def _extract_income(text: str) -> Optional[IncomeMode]:
    last_bank = _last_match(text, BANK_RES)
    last_cash = _last_match(text, CASH_RES)
    if last_bank is None and last_cash is None:
        return None
    if last_bank is None:
        return IncomeMode.CASH
    if last_cash is None:
        return IncomeMode.BANK
    return IncomeMode.CASH if last_cash.start() >= last_bank.start() else IncomeMode.BANK


def _extract_ownership(text: str) -> Optional[OwnershipStatus]:
    # Joint cues (partner/family/co-owner language) are decisive: a generic
    # "I own it" after "my wife and I" must not flip the answer to sole.
    # Cross-message corrections still work via QualificationService latest-wins.
    if _last_match(text, JOINT_RES) is not None:
        return OwnershipStatus.JOINT
    if _last_match(text, SOLE_RES) is not None:
        return OwnershipStatus.SOLE
    return None


def extract(text: str, prefer: Optional[str] = None) -> Dict[str, Any]:
    """Return structured fields found in text. Absent keys = not mentioned.

    `prefer` ("loan_amount"/"market_value"/"tenure") routes context-free amounts
    and bare short numbers to the currently-asked question; explicit
    need/worth/years keywords always win.
    """
    out: Dict[str, Any] = {}
    prop = _extract_property(text)
    if prop is not None:
        out["property_type"] = prop
    own = _extract_ownership(text)
    if own is not None:
        out["ownership_status"] = own
    docs = _extract_binary(text, DOCS_POS_RES, DOCS_NEG_RES)
    if docs is not None:
        out["documents_available"] = docs
    loan, market = _extract_amounts(text, prefer=prefer)
    if loan is not None:
        out["loan_amount"] = loan
    if market is not None:
        out["market_value"] = market
    occ = _extract_occupation(text)
    if occ is not None:
        out["occupation"] = occ
    inc = _extract_income(text)
    if inc is not None:
        out["income_mode"] = inc
    tenure = _extract_tenure(text, prefer=prefer)
    if tenure is not None:
        out["tenure"] = tenure
    return out
