
# Build Angular application
FROM node:24-alpine AS build

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci

COPY frontend/ ./

RUN npm run build -- --configuration production

# Serve Angular using Nginx
FROM nginx:stable-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build \
    /app/dist/frontend/browser/ \
    /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1/"]
