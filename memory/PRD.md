# +58 BarberStudio — PRD (feature: excepciones por fecha)

## Contexto
App real restaurada desde GitHub (pititagomez31/barber-repo): FastAPI + MongoDB + React, con reserva pública, panel del barbero (Agenda, Servicios, Horario, Bloqueos, Clientes), auth JWT usuario/contraseña, e integración WhatsApp (Meta) + backup por email. En este workspace de desarrollo la BD es `test_database` (las credenciales/keys reales viven en el hosting, no en el repo).

## Problema resuelto
El horario era solo "por día de la semana": cambiar el martes afectaba a todos los martes. Se añadió una **segunda capa de excepciones por fecha concreta** sin tocar el horario semanal base ni el resto del panel.

## Sistema de dos capas
- Capa 1 (existente): `working_hours` doc `default`, keys `0`-`6` (Lun-Dom).
- Capa 2 (NUEVA): colección `schedule_overrides`, un doc por fecha `{date, enabled, start, end, reason}`, índice único en `date`.
- Prioridad: si hay override para la fecha manda el override; si no, el horario semanal base. Bloqueos y citas se restan igual encima.

## Implementado (2026-09-14)
### Backend (`server.py`)
- Modelo `ScheduleOverrideIn`.
- Helper `_effective_schedule(date)` (override > base) y `_compute_slots()` refactorizado para usarlo.
- Endpoints: `GET/POST/DELETE /api/schedule-overrides`, `GET /api/schedule-overrides/{date}` (admin), `GET /api/day-schedule/{date}` (público).
- Índice único `schedule_overrides.date` al arrancar.
### Frontend (`AdminDashboard.jsx` → `SchedulePanel`)
- Sección A "Horario semanal base" (intacta, con nota aclaratoria).
- Sección B NUEVA "Excepciones por fecha": mini-calendario mensual, punto dorado = horario especial, punto rojo = cerrado; diálogo para crear/editar/eliminar la excepción de un día concreto.
- `Booking.jsx` sin cambios: `/api/availability` refleja los overrides automáticamente.

## Verificación (100% backend + frontend E2E, iteration_2.json)
Override 08:00 en un miércoles concreto → el cliente ve horas desde 08:00 solo ese día; el jueves sigue con base 10:00; día cerrado = sin horas; eliminar override vuelve al base. Resto de pestañas del panel intactas.

## Backlog (P2)
- Excepciones por rango de fechas (ej. "20-25 dic cerrado").
- Limpieza automática opcional de overrides antiguos (por ahora se guardan como historial).
- Fijar TZ Europe/Madrid en el gating de horas de "hoy" en `_compute_slots`.

## Credenciales (dev)
Admin `/admin/login`: usuario `+58BarberStudio` / contraseña `Y1129086F` (en `backend/.env`, temporales solo para dev).
