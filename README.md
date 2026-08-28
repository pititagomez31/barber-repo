# +58 BarberStudio

Web app de reservas para barbería en Tenerife. Frontend React + Backend FastAPI + MongoDB.

## Deploy en Railway

Este repo tiene **dos servicios** separados. Al desplegar en Railway, crea **dos servicios** en el mismo proyecto y configura cada uno con su Root Directory correspondiente:

### 1. Servicio Backend (FastAPI + Python)
- **Root Directory**: `backend`
- Railway detecta el `railway.json` y `nixpacks.toml` de la carpeta backend automáticamente
- Configura estas variables de entorno:

```
MONGO_URL=mongodb+srv://USUARIO:PASSWORD@CLUSTER.mongodb.net/?retryWrites=true&w=majority
DB_NAME=barberstudio
JWT_SECRET=<frase-aleatoria-larga>
ADMIN_EMAIL=pititagomez31@gmail.com
ADMIN_PASSWORD=58Barber2025!
BUSINESS_NAME=+58 BarberStudio
BUSINESS_PHONE=+34600000058
BUSINESS_WHATSAPP=34600000058
BUSINESS_ADDRESS=Av. Los Majuelos 51 (dentro de Multitienda Veloz), Tenerife
BUSINESS_BARBER_NAME=Heber
BUSINESS_REVIEWS_URL=
CORS_ORIGINS=<url-del-frontend-en-railway>
```

- Después, en Settings → Networking → Generate Domain. Anota la URL.

### 2. Servicio Frontend (React)
- **Root Directory**: `frontend`
- Variables de entorno:

```
REACT_APP_BACKEND_URL=<url-del-backend-en-railway>
```

- Networking → Generate Domain. Anota la URL.

### 3. Cerrar el círculo
- Vuelve al **Backend** → cambia `CORS_ORIGINS` a la URL del frontend.
- Railway redespliega solo.

### 4. MongoDB Atlas — Permitir Railway
En cloud.mongodb.com → Network Access → Add IP → **Allow access from anywhere** (0.0.0.0/0).

### 5. Login del panel del barbero
- URL: `<frontend>/admin/login`
- Email: `pititagomez31@gmail.com`
- Contraseña: `58Barber2025!` (cámbiala luego)

## Desarrollo local
```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# frontend
cd frontend && yarn install && yarn start
```
