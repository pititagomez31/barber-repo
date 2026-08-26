# Deployment Notes - +58 BarberStudio

## MongoDB Atlas (para Railway deploy)
- **User**: pititagomez31_db_user
- **Password**: CMiNLVLeMhBiOJlt
- Cuando configures Railway, la MONGO_URL será algo como:
  `mongodb+srv://pititagomez31_db_user:CMiNLVLeMhBiOJlt@<cluster>.mongodb.net/?retryWrites=true&w=majority`
  (falta el `<cluster>` que te da MongoDB Atlas al crear el cluster)

## Railway env vars necesarias (BACKEND)
- MONGO_URL=<url Atlas completa>
- DB_NAME=barberstudio
- JWT_SECRET=<generar aleatorio 64 chars>
- ADMIN_EMAIL=pititagomez31@gmail.com
- ADMIN_PASSWORD=58Barber2025!
- BUSINESS_NAME=+58 BarberStudio
- BUSINESS_PHONE=+34600000058 (poner el real)
- BUSINESS_WHATSAPP=34600000058 (poner el real, sin +)
- BUSINESS_ADDRESS=Av. Los Majuelos 51 (dentro de Multitienda Veloz), Tenerife
- BUSINESS_BARBER_NAME=Heber
- BUSINESS_REVIEWS_URL=<vacío hasta que tengas Google Reviews>
- CORS_ORIGINS=<URL del frontend en Railway>

## Railway env vars (FRONTEND)
- REACT_APP_BACKEND_URL=<URL del backend en Railway>
