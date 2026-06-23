FROM node:22-alpine

WORKDIR /app

# Copy package files first (leverage Docker layer caching)
COPY package.json ./
RUN npm install

# Copy application code
COPY . .

# Expose the frontend port
EXPOSE 3000

# Dev mode with hot reload
CMD ["npm", "run", "dev"]
