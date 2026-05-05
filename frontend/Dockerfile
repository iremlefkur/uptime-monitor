FROM alpine:latest AS stage1
WORKDIR /app
COPY . .

FROM nginx:alpine

COPY --from=stage1 /app /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
