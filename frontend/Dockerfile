FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
ENV PORT=3400
EXPOSE 3400
CMD ["npm", "run", "start"]
