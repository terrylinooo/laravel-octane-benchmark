# Minimal wrk load generator. wrk 4.x is in the Alpine community repo, so no
# compiling. The Lua reporter is baked in at /report.lua.
FROM alpine:3.20

RUN apk add --no-cache wrk

COPY report.lua /report.lua

# Default to wrk so `docker compose run --rm wrk -t4 -c8 -d10s ...` works.
ENTRYPOINT ["wrk"]
