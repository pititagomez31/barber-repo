# +58 BarberStudio — PRD

## Problem Statement
Refactor scheduling from "per weekday" to allow "per specific date" exceptions so the barber can change the hours of one concrete day (e.g. Wed Sep 16) without affecting every Wednesday. The described app did not exist in the workspace, so the full booking app was built fresh around this two-layer schedule system.

## Architecture
- **Backend:** FastAPI + MongoDB (Motor). All routes prefixed `/api`.
- **Frontend:** React (CRA/craco), Tailwind + shadcn/ui, dark barbershop theme (gold on near-black, Bebas Neue + Manrope).
- **No auth** (single barber, per requirements).

## Two-Layer Schedule
- **Layer 1 — weekly base:** `working_hours` doc id `default`, keys `0`-`6` (Mon-Sun).
- **Layer 2 — overrides:** `schedule_overrides` collection, one doc per date `{date, enabled, start, end, reason}`, unique index on `date`.
- **Priority:** override for the date wins, else weekly base. `_compute_slots()` checks overrides first, then subtracts existing appointments and blockers.

## Implemented (2026-09-14)
- Backend: services (seeded), working-hours GET/PUT, schedule-overrides CRUD + range list + single-date GET(404), `/day-schedule/{date}`, `/availability`, appointments (book with 409 guard, list, delete), blockers CRUD, startup seed + unique index.
- Frontend client `/`: service pick → month calendar → available slots (reflects overrides) → booking dialog → success.
- Frontend admin `/admin`: Agenda tab (appointments per date) + Horario tab = SchedulePanel with weekly base editor + date-exceptions calendar (gold dot markers, closed markers) + override create/edit/delete dialog.
- Verified E2E: 08:00 override on one Wednesday shows for client that date only; other days keep base; deleting override reverts. 11/11 backend tests + frontend E2E passed.

## Core Requirements (static)
- Single-date override beats weekly base for availability and client booking.
- Past overrides kept as history (no auto-cleanup).
- Blockers remain an additional layer over overrides.

## Backlog
- P2: Date-range overrides (e.g. "closed Dec 20–25").
- P2: Optional auto-cleanup of old overrides.
- P2: Barber auth/login.
- P2: WhatsApp confirmation (out of scope now).
