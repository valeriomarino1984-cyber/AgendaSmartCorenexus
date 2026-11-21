"""Numeri dello studio per la dashboard: appuntamenti, disdette, mancati, clienti nuovi,
prenotazioni online, valore e occupazione dell'agenda in un periodo.

Il periodo è in giorni di calendario nel fuso della sede principale. Il professionista vede
solo i propri numeri; titolare e segreteria vedono tutto lo studio e possono filtrare per
professionista. Gli appuntamenti si contano per data di inizio.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import Database
from app.models.agenda import Appointment
from app.models.catalog import Professional, Service
from app.modules.agenda import service as agenda
from app.modules.agenda import slots as sl
from app.modules.agenda.service import InvalidDataError

if TYPE_CHECKING:
    from app.modules.accounts.service import AuthContext

MAX_DAYS = 366
DAILY_UP_TO = 62  # oltre, l'andamento si raggruppa per mese
CANCELLED = ("cancelled_by_client", "cancelled_by_staff")
UPCOMING = ("pending", "confirmed")
HELD = ("pending", "confirmed", "completed", "no_show")  # tengono occupata l'agenda


@dataclass
class _Bucket:
    total: int = 0
    by_status: Counter[str] = field(default_factory=Counter)
    online: int = 0
    value_done: Decimal = Decimal(0)
    value_expected: Decimal = Decimal(0)
    booked_minutes: int = 0

    def add(self, a: Appointment, booked: int) -> None:
        self.total += 1
        self.by_status[a.status] += 1
        if a.source == "public_booking":
            self.online += 1
        price = a.price or Decimal(0)
        if a.status == "completed":
            self.value_done += price
        elif a.status in UPCOMING:
            self.value_expected += price
        if a.status in HELD:
            self.booked_minutes += booked


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _money(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01'))}"


def _summary(b: _Bucket, available_minutes: int | None) -> dict[str, object]:
    st = b.by_status
    cancelled = st["cancelled_by_client"] + st["cancelled_by_staff"]
    closed = st["completed"] + st["no_show"]
    return {
        "appointments": b.total,
        "completed": st["completed"],
        "upcoming": st["pending"] + st["confirmed"],
        "pending": st["pending"],
        "cancelled": cancelled,
        "cancelled_by_client": st["cancelled_by_client"],
        "cancelled_by_staff": st["cancelled_by_staff"],
        "no_show": st["no_show"],
        "cancellation_rate": _rate(cancelled, b.total),
        "no_show_rate": _rate(st["no_show"], closed),
        "online": b.online,
        "online_rate": _rate(b.online, b.total),
        "value_done": _money(b.value_done),
        "value_expected": _money(b.value_expected),
        "booked_minutes": b.booked_minutes,
        "available_minutes": available_minutes,
        "occupancy": (
            round(min(b.booked_minutes / available_minutes, 1.0), 4) if available_minutes else None
        ),
    }


def _available_minutes(
    s: Session, prof_ids: list[uuid.UUID], first: date, last: date
) -> dict[uuid.UUID, int]:
    loc = agenda._default_location(s)
    out: dict[uuid.UUID, int] = {}
    for pid in prof_ids:
        windows = agenda._windows(s, pid, loc, first, last)
        out[pid] = sum(int((e - b).total_seconds() // 60) for b, e in windows)
    return out


def stats(
    db: Database,
    ctx: AuthContext,
    *,
    first: date,
    last: date,
    professional_id: uuid.UUID | None,
) -> dict[str, object]:
    if last < first or (last - first).days + 1 > MAX_DAYS:
        raise InvalidDataError("Periodo non valido (massimo un anno).", code="periodo_non_valido")
    with db.tenant_session(ctx.tenant_id) as s:
        loc = agenda._default_location(s)
        tz = ZoneInfo(loc.timezone)
        start = sl.local_to_utc(first, time(0), tz)
        end = sl.local_to_utc(last + timedelta(days=1), time(0), tz)

        if ctx.role == "professional":
            mine = agenda._my_professional_id(s, ctx)
            if mine is None:
                return _empty(first, last, loc.timezone, scope="own")
            if professional_id is not None and professional_id != mine:
                raise InvalidDataError(
                    "Puoi vedere solo i tuoi numeri.", code="professionista_non_valido"
                )
            professional_id, scope = mine, "own"
        else:
            scope = "studio"
            if professional_id is not None and s.get(Professional, professional_id) is None:
                raise InvalidDataError(
                    "Professionista non valido.", code="professionista_non_valido"
                )

        stmt = select(Appointment).where(Appointment.start_at >= start, Appointment.start_at < end)
        if professional_id is not None:
            stmt = stmt.where(Appointment.professional_id == professional_id)
        appts = list(s.scalars(stmt))

        profs = {
            p.id: p
            for p in s.scalars(select(Professional).order_by(Professional.name))
            if professional_id is None or p.id == professional_id
        }
        active = [pid for pid, p in profs.items() if p.status == "active"]
        available = _available_minutes(s, active, first, last)

        total = _Bucket()
        per_prof: dict[uuid.UUID, _Bucket] = defaultdict(_Bucket)
        per_service: dict[uuid.UUID, _Bucket] = defaultdict(_Bucket)
        monthly = (last - first).days + 1 > DAILY_UP_TO
        trend: dict[str, _Bucket] = defaultdict(_Bucket)
        for a in appts:
            booked = int((a.end_at - a.start_at).total_seconds() // 60)
            total.add(a, booked)
            per_prof[a.professional_id].add(a, booked)
            per_service[a.service_id].add(a, booked)
            local = sl.utc_to_local(a.start_at, tz).date()
            trend[local.strftime("%Y-%m") if monthly else local.isoformat()].add(a, booked)

        # Clienti nuovi: il loro primo appuntamento non disdetto nello studio cade nel periodo.
        seen = {a.client_id for a in appts if a.status in HELD}
        new_clients = 0
        if seen:
            firsts = s.execute(
                select(Appointment.client_id, func.min(Appointment.start_at))
                .where(Appointment.client_id.in_(seen), Appointment.status.in_(HELD))
                .group_by(Appointment.client_id)
            ).all()
            new_clients = sum(1 for _, first_at in firsts if first_at >= start)

        services = {sv.id: sv for sv in s.scalars(select(Service))}

        total_available = sum(available.values()) if active else None
        return {
            "from": first.isoformat(),
            "to": last.isoformat(),
            "timezone": loc.timezone,
            "scope": scope,
            "professional_id": str(professional_id) if professional_id else None,
            "summary": {
                **_summary(total, total_available),
                "clients_seen": len(seen),
                "new_clients": new_clients,
            },
            "trend": {
                "granularity": "month" if monthly else "day",
                "points": _trend_points(first, last, monthly, trend),
            },
            "services": sorted(
                (
                    {
                        "id": str(sid),
                        "name": services[sid].name if sid in services else "—",
                        "appointments": b.total,
                        "completed": b.by_status["completed"],
                        "value_done": _money(b.value_done),
                        "value_expected": _money(b.value_expected),
                    }
                    for sid, b in per_service.items()
                ),
                key=lambda x: (-int(str(x["appointments"])), str(x["name"])),
            ),
            "professionals": [
                {
                    "id": str(pid),
                    "name": p.name,
                    "color": p.color,
                    **_summary(per_prof.get(pid, _Bucket()), available.get(pid)),
                }
                for pid, p in profs.items()
                if pid in per_prof or pid in available
            ],
        }


def _trend_points(
    first: date, last: date, monthly: bool, trend: dict[str, _Bucket]
) -> list[dict[str, object]]:
    keys: list[str] = []
    d = first
    while d <= last:
        k = d.strftime("%Y-%m") if monthly else d.isoformat()
        if not keys or keys[-1] != k:
            keys.append(k)
        d += timedelta(days=1)
    out: list[dict[str, object]] = []
    for k in keys:
        b = trend.get(k, _Bucket())
        out.append(
            {
                "key": k,
                "appointments": b.total,
                "completed": b.by_status["completed"],
                "cancelled": sum(b.by_status[c] for c in CANCELLED),
                "no_show": b.by_status["no_show"],
            }
        )
    return out


def _empty(first: date, last: date, tz: str, *, scope: str) -> dict[str, object]:
    monthly = (last - first).days + 1 > DAILY_UP_TO
    return {
        "from": first.isoformat(),
        "to": last.isoformat(),
        "timezone": tz,
        "scope": scope,
        "professional_id": None,
        "summary": {**_summary(_Bucket(), None), "clients_seen": 0, "new_clients": 0},
        "trend": {
            "granularity": "month" if monthly else "day",
            "points": _trend_points(first, last, monthly, {}),
        },
        "services": [],
        "professionals": [],
    }


def default_period(today: date) -> tuple[date, date]:
    """Mese in corso."""
    first = today.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


def local_today(db: Database, ctx: AuthContext) -> date:
    with db.tenant_session(ctx.tenant_id) as s:
        tz = ZoneInfo(agenda._default_location(s).timezone)
    return datetime.now(tz).date()
