# syntax=docker/dockerfile:1.6
# Sentinel-Z frontend — Next.js dashboard.
# Multi-stage: deps (npm ci) -> builder (next build) -> runtime (next start).

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

# Copy only production files
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

RUN addgroup --system --gid 1001 nextjs && \
    adduser --system --uid 1001 nextjs && \
    chown -R nextjs:nextjs /app
USER nextjs

EXPOSE 3000
CMD ["npm", "start"]
