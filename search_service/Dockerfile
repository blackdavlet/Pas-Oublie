services:
  nginx:
    image: nginx:1.27-alpine
    container_name: ip_nginx
    restart: always
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - images_data:/var/www/images:ro
    depends_on:
      - frontend
      - backend
    networks:
      - appnet
  frontend:
    build: ./frontend
    container_name: ip_frontend
    restart: always
    networks:
      - appnet
  backend:
    build: ./backend
    container_name: ip_backend
    restart: always
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres:5432/pastebin
      REDIS_URL: redis://redis:6379/0