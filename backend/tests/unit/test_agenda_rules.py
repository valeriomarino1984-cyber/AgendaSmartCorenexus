"""Regole dell'agenda senza database: festività, ora legale, calcolo degli orari liberi."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.modules.agenda.holidays import easter_sunday, holiday_name, italian_holidays
from app.modules.agenda.slots import (
    WeeklyRule,
    free_slots,
    local_to_utc,
    merge,
    open_windows,
    subtract,
    within,
)

ROME = ZoneInfo("Europe/Rome")
M = timedelta(minutes=1)


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


@pytest.mark.parametrize(
    ("year", "easter"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),
    ],
)
def test_easter(year: int, easter: date) -> None:
    assert easter_sunday(year) == easter


def test_italian_holidays() -> None:
    h = italian_holidays(2026)
    assert h[date(2026, 4, 6)] == "Lunedì dell'Angelo"
    assert h[date(2026, 10, 4)] == "San Francesco d'Assisi"
    assert len(h) == 13
    assert date(2025, 10, 4) not in italian_holidays(2025)
    assert holiday_name(date(2026, 12, 25)) == "Natale"
    assert holiday_name(date(2026, 12, 24)) is None


def test_local_hours_stay_local_across_dst() -> None:
    # 09:00 a Roma: 08:00 UTC d'inverno, 07:00 UTC d'estate (cambio il 29/03/2026 e il 25/10/2026).
    assert local_to_utc(date(2026, 3, 28), time(9), ROME) == dt("2026-03-28T08:00")
    assert local_to_utc(date(2026, 3, 29), time(9), ROME) == dt("2026-03-29T07:00")
    assert local_to_utc(date(2026, 10, 24), time(9), ROME) == dt("2026-10-24T07:00")
    assert local_to_utc(date(2026, 10, 25), time(9), ROME) == dt("2026-10-25T08:00")
    # 02:30 del 29 marzo non esiste: si va avanti (03:30 locali = 01:30 UTC).
    assert local_to_utc(date(2026, 3, 29), time(2, 30), ROME) == dt("2026-03-29T01:30")


def test_dst_weekend_slots_have_same_local_times() -> None:
    sunday = WeeklyRule(7, time(9), time(11))
    for day in (date(2026, 3, 29), date(2026, 10, 25)):
        windows = open_windows(first=day, last=day, tz=ROME, rules=[sunday])
        starts = free_slots(windows, [], duration=60 * M, preparation=0 * M, step=30 * M)
        local = [
            t.replace(tzinfo=ZoneInfo("UTC")).astimezone(ROME).strftime("%H:%M") for t in starts
        ]
        assert local == ["09:00", "09:30", "10:00"], day


def test_merge_and_subtract() -> None:
    a, b, c, d = (
        dt("2026-01-01T09:00"),
        dt("2026-01-01T10:00"),
        dt("2026-01-01T11:00"),
        dt("2026-01-01T12:00"),
    )
    assert merge([(c, d), (a, b), (b, c)]) == [(a, d)]
    assert subtract([(a, d)], [(b, c)]) == [(a, b), (c, d)]
    assert subtract([(a, b)], [(a, b)]) == []
    assert within([(a, d)], (b, c)) and not within([(a, b)], (a, c))


def test_holidays_closed_unless_extra_opening() -> None:
    rule = WeeklyRule(1, time(9), time(13))  # lunedì
    easter_monday = date(2026, 4, 6)
    assert open_windows(first=easter_monday, last=easter_monday, tz=ROME, rules=[rule]) == []
    extra = (dt("2026-04-06T08:00"), dt("2026-04-06T10:00"))
    windows = open_windows(
        first=easter_monday, last=easter_monday, tz=ROME, rules=[rule], extras=[extra]
    )
    assert windows == [extra]


def test_free_slots_respect_busy_preparation_and_window_end() -> None:
    windows = [(dt("2026-11-23T08:00"), dt("2026-11-23T11:00"))]
    busy = [(dt("2026-11-23T09:00"), dt("2026-11-23T09:45"))]  # visita 30' + 15' preparazione
    starts = free_slots(windows, busy, duration=30 * M, preparation=10 * M, step=15 * M)
    hhmm = [t.strftime("%H:%M") for t in starts]
    # 08:15: visita fino alle 08:45 + 10' = 08:55, prima delle 09:00: va bene.
    # 08:30: arriverebbe alle 09:10 e si sovrappone. Dalle 09:45 si torna liberi.
    assert hhmm == ["08:00", "08:15", "09:45", "10:00", "10:15", "10:30"]
    late = free_slots(
        windows,
        [],
        duration=30 * M,
        preparation=0 * M,
        step=15 * M,
        not_before=dt("2026-11-23T10:20"),
    )
    assert [t.strftime("%H:%M") for t in late] == ["10:30"]


def test_vacation_blocks_and_validity_period() -> None:
    rule = WeeklyRule(1, time(9), time(12), valid_from=date(2026, 11, 30))
    assert (
        open_windows(first=date(2026, 11, 23), last=date(2026, 11, 23), tz=ROME, rules=[rule]) == []
    )
    vacation = (dt("2026-11-30T00:00"), dt("2026-12-01T00:00"))
    assert (
        open_windows(
            first=date(2026, 11, 30),
            last=date(2026, 11, 30),
            tz=ROME,
            rules=[rule],
            blocks=[vacation],
        )
        == []
    )
