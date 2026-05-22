FROM nginx:alpine

# Tighten Server header (small touch — players who fingerprint headers will see this)
RUN sed -i 's/^.*server_tokens.*$/    server_tokens off;/' /etc/nginx/nginx.conf || true

COPY html/ /usr/share/nginx/html/

EXPOSE 80
