# +58 BarberStudio — PRD

## Problem Statement
Web app moderna para una barbería en Tenerife. Clientes reservan cita en 3 pasos desde móvil. El barbero entra a un panel privado en /admin y gestiona todo. Notificaciones por enlaces wa.me. Español, EUR, timezone Europe/Madrid, mobile-first, tema oscuro (grafito + dorado suave).

## Arquitectura
- **Frontend**: React 19 + React Router 7 + Tailwind + Shadcn UI + framer-motion + date-fns
- **Backend**: FastAPI + Motor (MongoDB async), JWT + bcrypt para auth admin
- **DB**: MongoDB — colecciones `users`, `services`, `appointments`, `blockers`, `clients`, `working_hours`
- **Rutas**: `/` (home), `/reservar` (wizard), `/admin/login`, `/admin` (protegida)

## User Personas
- **Cliente (móvil, no se registra)**: hombre en Tenerife que quiere corte/barba, quiere reservar en 3 toques.
- **Barbero (admin)**: no técnico, usa credenciales fijas para gestionar todo.

## Core Requirements (static)
- Reserva en 3-4 pasos con horas libres reales (anti doble reserva).
- Política del 50% (checkbox obligatorio, sin cobro real).
- Cancelación cliente hasta 12h antes.
- Panel admin con agenda día/semana/mes, horarios, bloqueos, servicios CRUD, clientes.
- wa.me con mensaje pre-escrito al confirmar.

## Implementado (2026-02)
- Backend completo: auth JWT (admin seed), servicios CRUD, availability con slots reales cada 15min, appointments create/cancel (12h rule, admin-cancel), blockers, working-hours, clientes con historial, /business info pública.
- Frontend público: Hero premium, servicios en cards, galería bento, sobre el barbero, testimonios, ubicación con Google Maps embed, botones flotantes (WhatsApp/Instagram/Phone), sticky "RESERVAR" en móvil.
- Wizard de reserva de 4 pasos con calendario en español y validaciones.
- Login admin + Dashboard con 5 tabs (Agenda, Servicios, Horario, Bloqueos, Clientes).
- Diseño: Playfair Display + Manrope, paleta grafito (#14141A) + oro suave (#D4B77A), neumorphism suave, noise texture, glassmorphism en navbar.
- Testing 100% pasado (backend + frontend end-to-end).

## Backlog (siguiente)
- **P0**: fotos reales del barbero, logo real, textos definitivos, dirección real de Tenerife.
- **P1**: Twilio WhatsApp Business (confirmación automática + recordatorio 24h).
- **P1**: Recordatorios email/SMS.
- **P2**: Cobro real 50% con Stripe (v2, requiere alta legal).
- **P2**: Multi-barbero, programa de fidelidad, cupones.
- **P2**: PWA / app instalable.

## Credenciales (test)
Ver `/app/memory/test_credentials.md`
