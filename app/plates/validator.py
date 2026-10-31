import re

PLATE_RE = re.compile(r"^(0[1-9]|[1-7]\d|8[01])([A-PR-VYZ]{1,3})(\d{2,4})$")

TO_DIGIT = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1",
            "Z": "2", "S": "5", "G": "6", "B": "8"}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "8": "B"}

EDGE_JUNK = set("1ILJT")


class TurkishPlateValidator:
    @staticmethod
    def normalize(raw: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", raw.upper())

    @staticmethod
    def _fix_exact(s: str) -> tuple[str, int] | None:
        best, best_changes = None, 99
        for n_letters in (1, 2, 3):
            n_digits = len(s) - 2 - n_letters
            if not 2 <= n_digits <= 4:
                continue
            candidate, changes = [], 0
            for i, ch in enumerate(s):
                digit_pos = i < 2 or i >= 2 + n_letters
                if digit_pos and not ch.isdigit():
                    fixed = TO_DIGIT.get(ch, ch)
                elif not digit_pos and ch.isdigit():
                    fixed = TO_LETTER.get(ch, ch)
                else:
                    fixed = ch
                changes += fixed != ch
                candidate.append(fixed)
            candidate = "".join(candidate)
            if PLATE_RE.match(candidate) and changes < best_changes:
                best, best_changes = candidate, changes
        return (best, best_changes) if best else None

    def fix(self, raw: str) -> str | None:
        s = self.normalize(raw)
        exact = self._fix_exact(s)
        if exact:
            return exact[0]
        trimmed_variants = []
        if s and s[0] in EDGE_JUNK:
            trimmed_variants.append(s[1:])
        if s and s[-1] in EDGE_JUNK:
            trimmed_variants.append(s[:-1])
        best = None
        for trimmed in trimmed_variants:
            r = self._fix_exact(trimmed)
            if r and (best is None or r[1] < best[1]):
                best = r
        return best[0] if best else None

    @staticmethod
    def pretty(plate: str) -> str:
        m = PLATE_RE.match(plate)
        return f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else plate

    @staticmethod
    def province_code(plate: str) -> str | None:
        m = PLATE_RE.match(plate)
        return m.group(1) if m else None
