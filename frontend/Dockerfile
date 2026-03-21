FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json .
RUN npm install

COPY . .
RUN npm run build

# Production image: nginx serving static files
FROM nginx:1.25-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config: SPA routing (redirect all 404 to index.html)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
