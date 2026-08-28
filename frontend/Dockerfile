# -------- Build stage --------
FROM node:20-alpine AS build

WORKDIR /app

# Copy package.json first for cache. yarn.lock may not exist in repo — yarn install will generate one.
COPY package.json ./
RUN yarn install --network-timeout 300000

# React build-time env vars (Railway passes as build ARGs)
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

COPY . ./
RUN yarn build

# -------- Runtime stage --------
FROM node:20-alpine

WORKDIR /app

RUN yarn global add serve

COPY --from=build /app/build ./build

CMD ["sh", "-c", "serve -s build -l ${PORT:-3000}"]
