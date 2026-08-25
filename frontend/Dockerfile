# =====================================================================
# Frontend — React (CRA + CRACO) servido por Nginx con HTTPS
# Build multi-stage: 1) compila el bundle con yarn  2) lo sirve nginx
# =====================================================================

# ---------- Stage 1: build ----------
FROM node:20-bookworm-slim AS build

WORKDIR /app

# Instalar dependencias (cache por lockfile)
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000

# Copiar el resto del código
COPY . .

# ⚠️ CRA/CRACO baja las variables en BUILD TIME.
# Aquí se inyecta la URL PÚBLICA del backend/app.
ARG REACT_APP_BACKEND_URL=https://crm.tudominio.com
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}
# Evitar que warnings sean tratados como errores en el build de CI/Docker
ENV CI=false
# Margen de memoria para el build (la app es grande)
ENV NODE_OPTIONS=--max_old_space_size=4096

RUN yarn build

# ---------- Stage 2: serve (nginx + HTTPS) ----------
FROM nginx:1.27-alpine

# Config del sitio (SPA + reverse proxy /api -> backend + SSL)
COPY nginx-ssl.conf /etc/nginx/conf.d/default.conf

# Bundle compilado
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
