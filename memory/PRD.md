# PRD — +58 BarberStudio

## Problem statement original
App web existente (React + FastAPI + MongoDB, deploy en Railway: https://barber-repo-production.up.railway.app, repo `pititagomez31/barber-repo` rama main). Lote de 5 cambios de frontend: (1) verificar acceso admin /admin/login sin enlace visible en footer (decisión del usuario: oculto, solo por URL); (2) imágenes responsive sin deformación (mixto: cover en hero/galería, contain donde sea crítico — foto del barbero); (3) eliminar botón flotante de llamada y todo rastro de tel:; (4) nueva dirección "Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife" en todo el frontend + mapa; (5) eliminar sección de opiniones/testimonios de la home. Restricciones: no tocar flujo de reserva 4 pasos, anti doble reserva, cancelación 12h, CRUD admin, ni look grafito+dorado.

## Arquitectura
- Frontend React (craco, Tailwind, shadcn) en /app/frontend — páginas: Home, Booking, AdminLogin, AdminDashboard.
- Backend FastAPI en /app/backend/server.py — rutas /api/*, JWT auth (ADMIN_EMAIL/ADMIN_PASSWORD env), MongoDB vía motor.
- Info de negocio centralizada en GET /api/business (BUSINESS_* env vars; default de dirección actualizado en código).
- Deploy: usuario hace Save to GitHub → Railway redeploy (frontend con Clear build cache). Pendiente: actualizar BUSINESS_ADDRESS en variables de Railway.

## Personas
- Cliente: reserva cita en 4 pasos, cancela hasta 12h antes.
- Barbero (Heber): admin en /admin (Agenda, Servicios, Horario, Bloqueos, Clientes). Credenciales en /app/memory/test_credentials.md.

## Implementado (2026-08-28)
- Repo importado a /app vía git clone (GitHub linking del usuario aún pendiente en su cuenta Emergent).
- Admin verificado: /admin/login devuelve JWT, panel con 5 pestañas operativo. Sin enlace en footer (decisión: oculto).
- Imágenes: regla base `img{max-width:100%;height:auto}` en index.css; hero/galería con object-cover; foto del barbero en contenedor aspect-[4/5] con object-contain; fix de grid bento móvil (auto-rows-[150px], antes colapsaba a tiras de 82/35px — verificado 360/390/768px).
- Botón teléfono eliminado de FloatingContact + enlace tel: del AdminDashboard convertido a texto + fila de teléfono quitada de #ubicacion. Cero rastro tel: verificado por grep y tests.
- Dirección nueva como default en /api/business; se propaga a Ubicación, footer, iframe de Maps y enlace "Abrir en Maps".
- Sección opiniones eliminada de Home, ancla #opiniones quitada del Navbar, array TESTIMONIALS borrado. Sin hueco vertical.
- Bug crítico encontrado y corregido en testing: crash de AdminDashboard (useEffect con función async que retorna Promise) al salir de la pestaña Bloqueos.
- Botón flotante WhatsApp ahora se oculta si BUSINESS_WHATSAPP está vacío.
- Testing: backend 12/12 pytest, frontend verificado en 360/390/768/1024/1920px, reserva e2e OK. Reporte: /app/test_reports/iteration_11.json.

## Bug fix (2026-08-29)
- Crash producción móvil "removeChild on Node" (ErrorBoundary "Algo se ha torcido") en admin y flujo de reserva: causa raíz = `<html lang="en">` con contenido ES → Chrome móvil auto-traducía y Google Translate envolvía text nodes en `<font>`, rompiendo el DOM de React 19. Fix en frontend/public/index.html: `lang="es" class="notranslate"` + `<meta name="google" content="notranslate">` + title propio. Verificado por testing agent (iteration_12): 0 ErrorBoundary, 0 errores JS en Home/reserva e2e/admin (15 cambios de pestaña, 390px).
- Fix adicional: overflow horizontal del TabsList del admin en móvil (scrollWidth 576→390) envolviéndolo en div con overflow-x-auto. Auto-verificado con screenshot 390px.

## Feature WhatsApp + email (2026-08-29)
- Sistema de confirmación/recordatorios wa.me: POST /api/appointments devuelve whatsapp_links {cliente, barbero} (barbero null si BUSINESS_WHATSAPP vacío); booking muestra botones "Confirmar mi cita por WhatsApp" y "Notificar al barbero por WhatsApp"; nuevo campo email opcional en reserva (client_email).
- Admin Agenda: badge Estado Confirmada/Pendiente + botón Confirmar (PUT /api/appointments/{id}/confirmar) + botón Recordatorio (POST /api/appointments/{id}/recordatorio → abre wa.me).
- Cron diario 10:00 Atlantic/Canary (.emergent/crons.yml → POST /api/cron/recordatorios, Bearer WEBHOOK_CRON_SECRET): procesa citas de mañana con recordatorio_enviado=false, las marca y envía email con el enlace wa.me vía Resend gestionado (EMERGENT_EMAIL_KEY). Para Railway: cron-job.org con el mismo endpoint+Bearer.
- Mapa: /api/business expone maps_query="Multitienda Veloz 24hr, Avenida de Los Majuelos 51C..." usado por iframe y "Abrir en Maps" (fix Western Union).
- Pendiente usuario en Railway: BUSINESS_WHATSAPP (número del barbero), WEBHOOK_CRON_SECRET, BUSINESS_ADDRESS, y cron externo.
- Fixes post-testing (iter13): iframe de Maps remonta con key al cargar maps_query (ya muestra Multitienda Veloz 24hr, verificado con screenshot); run_recordatorios con claim atómico find_one_and_update (doble cron simultáneo → 1 y 0 procesadas, sin emails duplicados).
- Fix 405 (iter14): /api/cron/recordatorios ahora acepta GET y POST (api_route) porque cron-job.org llama con GET por defecto. Verificado 8/8: 401 sin/con mal Bearer en ambos métodos, 200 con Bearer correcto en ambos, e2e con email OK.

## Backlog priorizado
- P0: Usuario debe actualizar BUSINESS_ADDRESS en Railway (backend) y hacer redeploy del frontend con Clear build cache tras Save to GitHub.
- P0 (seguridad, aplazado por el usuario): repo público con credenciales en historial — poner privado y rotar Mongo password, ADMIN_PASSWORD, JWT_SECRET.
- P1: Notificaciones WhatsApp solicitadas por el usuario (confirmación al reservar, recordatorio 24h, informe diario al barbero). wa.me no envía automático — opciones: botones wa.me pre-rellenados en admin/confirmación, o integración Twilio/Meta WhatsApp Business API para envío real.
- P2: Reemplazar date input nativo de Admin>Bloqueos por shadcn Calendar; deshabilitar domingos (día cerrado) en calendario de reserva.

## Siguientes tareas
1. Confirmar con el usuario si quiere implementar las notificaciones wa.me (versión manual con botones) o integración WhatsApp Business API.
2. Verificar deploy en Railway tras el push.
