FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code (excluding node_modules via .dockerignore)
COPY . .

# Ensure node_modules/.bin has execute permissions
RUN chmod -R +x node_modules/.bin/ || true

# Build for production
RUN npm run build

# ----- Production Stage -----
FROM nginx:alpine AS production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user and fix permissions
RUN addgroup -g 1001 -S pstrag && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G pstrag pstrag && \
    chown -R pstrag:pstrag /var/cache/nginx /var/log/nginx /etc/nginx/conf.d && \
    touch /run/nginx.pid && \
    chown pstrag:pstrag /run/nginx.pid

# Switch to non-root user
USER pstrag

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
