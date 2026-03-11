# Stage 1: Build Svelte dashboard
FROM node:22-slim AS build

WORKDIR /app

COPY brainbox/dashboard/package*.json ./
RUN npm ci

COPY brainbox/dashboard/ ./
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/brainbox-ui/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
