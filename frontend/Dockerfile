FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
ARG NPM_REGISTRY=https://registry.npmjs.org/
ENV npm_config_registry=${NPM_REGISTRY}

RUN npm --version \
    && npm config set fund false \
    && npm config set audit false \
    && npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set maxsockets 1 \
    && success=0 \
    && for i in 1 2 3 4 5; do \
        if npm ci --no-audit --no-fund; then success=1; break; fi; \
        echo "npm ci failed, retry $i/5"; \
        npm cache clean --force; \
        sleep $((i * 5)); \
      done \
    && [ "$success" -eq 1 ]

COPY . .

ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build


FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/docker-entrypoint.sh"]
