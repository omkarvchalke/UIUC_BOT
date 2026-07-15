FROM node:20-slim AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci


FROM node:20-slim AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build


FROM node:20-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production
# Docker sets HOSTNAME to the container ID; Next's standalone server binds to
# process.env.HOSTNAME when set, which would otherwise make it listen only on
# that internal address instead of all interfaces -- unreachable from the
# published port (and from localhost within the container, e.g. the
# HEALTHCHECK below) even though the process looks like it's running fine.
ENV HOSTNAME=0.0.0.0

COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=15s \
    CMD node -e "fetch('http://localhost:3000').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
