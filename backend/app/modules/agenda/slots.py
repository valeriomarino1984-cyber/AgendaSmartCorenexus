"""Calcolo degli orari liberi. Funzioni pure (nessun accesso al database), facili da testare.

Convenzioni:
- tutti gli istanti sono datetime UTC senza fuso (come nel database);
- gli orari settimanali sono "ora locale" della sede e si convertono giorno per giorno, così
  09:00 resta 09:00 anche dopo il cambio dell'ora legale;
- gli intervalli sono semiaperti [inizio, fine).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.agenda.holidays import holiday_name

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class WeeklyRule:
    weekday: int  # ISO: 1 = lunedì
    start: time
    end: time
    valid_from: date | None = None
    valid_to: date | None = None

    def applies(self, day: date) -> bool:
        return (
            day.isoweekday() == self.weekday
            and (self.valid_from is None or day >= self.valid_from)
            and (self.valid_to is None or day <= self.valid_to)
        )


def local_to_utc(day: date, at: time, tz: ZoneInfo) -> datetime:
    """Ora locale → UTC. Un'ora che non esiste (salto dell'ora legale) slitta in avanti."""
    local = datetime.combine(day, at, tzinfo=tz)
    return local.astimezone(UTC).replace(tzinfo=None)


def utc_to_local(at: datetime, tz: ZoneInfo) -> datetime:
    return at.replace(tzinfo=UTC).astimezone(tz)


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for start, end in sorted(i for i in intervals if i[1] > i[0]):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def subtract(base: Sequence[Interval], cuts: Iterable[Interval]) -> list[Interval]:
    result = merge(base)
    for c_start, c_end in merge(cuts):
        nxt: list[Interval] = []
        for start, end in result:
            if c_end <= start or c_start >= end:
                nxt.append((start, end))
                continue
            if start < c_start:
                nxt.append((start, c_start))
            if c_end < end:
                nxt.append((c_end, end))
        result = nxt
    return result


def overlaps(a: Interval, b: Interval) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def days_between(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def open_windows(
    *,
    first: date,
    last: date,
    tz: ZoneInfo,
    rules: Sequence[WeeklyRule],
    blocks: Iterable[Interval] = (),
    extras: Iterable[Interval] = (),
    skip_holidays: bool = True,
) -> list[Interval]:
    """Finestre di lavoro (UTC) tra due giorni locali inclusi.

    Orari settimanali, meno festività e blocchi (ferie, indisponibilità, chiusure), più le
    aperture straordinarie (che valgono anche nei giorni festivi).
    """
    base: list[Interval] = []
    holidays: list[Interval] = []
    for day in days_between(first, last):
        for rule in rules:
            if rule.applies(day):
                base.append((local_to_utc(day, rule.start, tz), local_to_utc(day, rule.end, tz)))
        if skip_holidays and holiday_name(day):
            nxt = day + timedelta(days=1)
            holidays.append((local_to_utc(day, time(0), tz), local_to_utc(nxt, time(0), tz)))
    windows = subtract(base, [*holidays, *blocks])
    return merge([*windows, *extras])


def free_slots(
    windows: Sequence[Interval],
    busy: Iterable[Interval],
    *,
    duration: timedelta,
    preparation: timedelta,
    step: timedelta,
    not_before: datetime | None = None,
) -> list[datetime]:
    """Inizi possibili: la visita sta dentro una finestra di lavoro e la visita più la
    preparazione non si sovrappone a impegni già presi (che includono la loro preparazione).
    """
    busy_list = merge(busy)
    starts: list[datetime] = []
    for w_start, w_end in merge(windows):
        t = w_start
        while t + duration <= w_end:
            occupied = (t, t + duration + preparation)
            if (not_before is None or t >= not_before) and not any(
                overlaps(occupied, b) for b in busy_list
            ):
                starts.append(t)
            t += step
    return starts


def within(windows: Sequence[Interval], interval: Interval) -> bool:
    return any(w[0] <= interval[0] and interval[1] <= w[1] for w in merge(windows))
