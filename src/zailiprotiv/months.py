"""The months in Serbian, in one place: the names as the Assembly's pages and the site write a date ("5. novembar
2025."), the same after a day in a sentence ("5. novembra 2025"), and the names in Cyrillic, as the Assembly's
Cyrillic pages write them. Each a tuple in the year's order, January first."""

from __future__ import annotations

NAMES = ("januar", "februar", "mart", "april", "maj", "jun", "jul", "avgust", "septembar", "oktobar", "novembar",
         "decembar")
OF = ("januara", "februara", "marta", "aprila", "maja", "juna", "jula", "avgusta", "septembra", "oktobra",
      "novembra", "decembra")
CYR = ("јануар", "фебруар", "март", "април", "мај", "јун", "јул", "август", "септембар", "октобар", "новембар",
       "децембар")


def day(iso: str | None) -> str:
    """"2025-11-04" → "4. novembar 2025."; "" for no day."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {NAMES[int(m) - 1]} {y}."


def day_of(iso: str | None) -> str:
    """"2025-11-04" → "4. novembra 2025": the date after "od", "do", in a sentence, without the final dot."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)}. {OF[int(m) - 1]} {y}"
