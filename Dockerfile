FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build
WORKDIR /app
COPY package.json tsconfig.json ./
# This repository intentionally does not track package-lock.json.
RUN npm install --package-lock=false
COPY src ./src
RUN npm run build && node dist/src/test_tool_registry.js
RUN npm prune --omit=dev --package-lock=false

FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402
WORKDIR /app
ENV NODE_ENV=production PORT=80
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
EXPOSE 80
CMD ["node", "dist/src/index_server.js"]
