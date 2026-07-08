# CampusGuide AI — frontend (local/demo convenience only)
#
# Production frontend deployment is Vercel (static build via `npm run
# build`), NOT this Dockerfile — see the root README's Deployment section.
# This image is purely for `docker compose up` local multi-service demos.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
