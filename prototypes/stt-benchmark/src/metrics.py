from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Sequence


NUMBER_PATTERN = re.compile(r"(?<!\w)-?\d+(?:[.,]\d+)?(?!\w)")
WHITESPACE_PATTERN = re.compile(r"\s+")
UNAMBIGUOUS_ENGLISH_WORDS = {
    "actually", "anyway", "because", "computer", "hello", "maybe", "okay",
    "please", "sorry", "thanks", "the", "today", "tomorrow", "well", "yes",
}
SMALL_DUTCH_NUMBERS = {
    0: "nul", 1: "een", 2: "twee", 3: "drie", 4: "vier", 5: "vijf",
    6: "zes", 7: "zeven", 8: "acht", 9: "negen", 10: "tien",
    11: "elf", 12: "twaalf", 13: "dertien", 14: "veertien", 15: "vijftien",
    16: "zestien", 17: "zeventien", 18: "achttien", 19: "negentien", 20: "twintig",
}
DUTCH_TENS = {
    20: "twintig", 30: "dertig", 40: "veertig", 50: "vijftig",
    60: "zestig", 70: "zeventig", 80: "tachtig", 90: "negentig",
}


def _number_to_dutch(match: re.Match[str]) -> str:
    token = match.group(0).replace(",", ".")
    try:
        from num2words import num2words

        value: int | float = float(token) if "." in token else int(token)
        return str(num2words(value, lang="nl"))
    except (ImportError, NotImplementedError, ValueError):
        try:
            number = int(token)
            if number in SMALL_DUTCH_NUMBERS:
                return SMALL_DUTCH_NUMBERS[number]
            if number in DUTCH_TENS:
                return DUTCH_TENS[number]
            if 20 < number < 100:
                ones, tens = number % 10, number - number % 10
                return f"{SMALL_DUTCH_NUMBERS[ones]}en{DUTCH_TENS[tens]}"
            return token
        except ValueError:
            return token


def normalize_text(text: str) -> str:
    """Shared normalization: Dutch number words, lowercase, no punctuation."""
    value = unicodedata.normalize("NFKC", text).lower()
    value = NUMBER_PATTERN.sub(_number_to_dutch, value)
    characters: list[str] = []
    for char in value:
        category = unicodedata.category(char)
        characters.append(" " if category.startswith(("P", "S")) else char)
    return WHITESPACE_PATTERN.sub(" ", "".join(characters)).strip()


@dataclass(frozen=True)
class EditCounts:
    substitutions: int
    deletions: int
    insertions: int
    hits: int

    @property
    def reference_length(self) -> int:
        return self.substitutions + self.deletions + self.hits

    @property
    def error_rate(self) -> float:
        denominator = self.reference_length
        errors = self.substitutions + self.deletions + self.insertions
        return errors / denominator if denominator else float(errors > 0)


def edit_counts(reference: Sequence[str], hypothesis: Sequence[str]) -> EditCounts:
    """Levenshtein alignment with operation counts and stable tie-breaking."""
    rows = len(reference) + 1
    columns = len(hypothesis) + 1
    # cell: (cost, substitutions, deletions, insertions, hits)
    matrix: list[list[tuple[int, int, int, int, int]]] = [
        [(0, 0, 0, 0, 0) for _ in range(columns)] for _ in range(rows)
    ]
    for row in range(1, rows):
        matrix[row][0] = (row, 0, row, 0, 0)
    for column in range(1, columns):
        matrix[0][column] = (column, 0, 0, column, 0)
    for row in range(1, rows):
        for column in range(1, columns):
            diagonal = matrix[row - 1][column - 1]
            if reference[row - 1] == hypothesis[column - 1]:
                match = (diagonal[0], diagonal[1], diagonal[2], diagonal[3], diagonal[4] + 1)
                matrix[row][column] = match
                continue
            substitution = (
                diagonal[0] + 1,
                diagonal[1] + 1,
                diagonal[2],
                diagonal[3],
                diagonal[4],
            )
            deletion_source = matrix[row - 1][column]
            deletion = (
                deletion_source[0] + 1,
                deletion_source[1],
                deletion_source[2] + 1,
                deletion_source[3],
                deletion_source[4],
            )
            insertion_source = matrix[row][column - 1]
            insertion = (
                insertion_source[0] + 1,
                insertion_source[1],
                insertion_source[2],
                insertion_source[3] + 1,
                insertion_source[4],
            )
            matrix[row][column] = min(
                (substitution, deletion, insertion),
                key=lambda cell: (cell[0], cell[2] + cell[3], cell[1]),
            )
    _, substitutions, deletions, insertions, hits = matrix[-1][-1]
    return EditCounts(substitutions, deletions, insertions, hits)


def _critical_recall(critical_words: list[str], hypothesis: str) -> tuple[int, int, float | None]:
    if not critical_words:
        return 0, 0, None
    padded_hypothesis = f" {hypothesis} "
    found = sum(
        1 for term in critical_words if f" {normalize_text(term)} " in padded_hypothesis
    )
    return found, len(critical_words), found / len(critical_words)


def measure(reference: str, hypothesis: str, critical_words: list[str] | None = None) -> dict[str, Any]:
    normalized_reference = normalize_text(reference)
    normalized_hypothesis = normalize_text(hypothesis)
    word_edits = edit_counts(normalized_reference.split(), normalized_hypothesis.split())
    character_edits = edit_counts(list(normalized_reference), list(normalized_hypothesis))
    critical_found, critical_total, critical_recall = _critical_recall(
        critical_words or [], normalized_hypothesis
    )
    hypothesis_words = normalized_hypothesis.split()
    english_words = [word for word in hypothesis_words if word in UNAMBIGUOUS_ENGLISH_WORDS]
    reference_words = max(1, word_edits.reference_length)
    return {
        "reference_normalized": normalized_reference,
        "transcript_normalized": normalized_hypothesis,
        "wer": word_edits.error_rate,
        "cer": character_edits.error_rate,
        "substitutions": word_edits.substitutions,
        "deletions": word_edits.deletions,
        "insertions": word_edits.insertions,
        "hits": word_edits.hits,
        "reference_words": word_edits.reference_length,
        "character_errors": (
            character_edits.substitutions + character_edits.deletions + character_edits.insertions
        ),
        "reference_characters": character_edits.reference_length,
        "omitted_word_rate": word_edits.deletions / reference_words,
        "critical_words_found": critical_found,
        "critical_words_total": critical_total,
        "critical_word_recall": critical_recall,
        "hallucinated_words": len(hypothesis_words) if not normalized_reference else 0,
        "english_intrusions": english_words,
        "sentence_boundary_count": len(re.findall(r"[.!?]+", hypothesis)),
        "starts_with_capital": bool(hypothesis and hypothesis.lstrip()[:1].isupper()),
    }

