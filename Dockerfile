FROM python:3.13-slim-bookworm AS base-libs

LABEL maintainer="mapproxy.org"

RUN apt-get update && apt-get -y install --no-install-recommends \
  libgeos-dev \
  libgdal-dev \
  libxml2-dev \
  libxslt-dev && \
  apt-get -y --purge autoremove && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

FROM base-libs AS builder

RUN mkdir /mapproxy
WORKDIR /mapproxy

COPY setup.py MANIFEST.in README.md CHANGES.txt AUTHORS.txt COPYING.txt LICENSE.txt ./
COPY mapproxy mapproxy

RUN rm -rf dist/* && \
    pip --no-cache-dir wheel . -w dist

###### base/plain image ######
FROM base-libs AS base

ARG MAPPROXY_VERSION=6.0.1
ENV MAPPROXY_VERSION=${MAPPROXY_VERSION}
ENV PATH="${PATH}:/mapproxy/.local/bin"

RUN mkdir /mapproxy && groupadd mapproxy && \
    useradd --home-dir /mapproxy -s /bin/bash -g mapproxy mapproxy && \
    chown -R mapproxy:mapproxy /mapproxy

WORKDIR /mapproxy
USER mapproxy:mapproxy

RUN mkdir mapproxy-dist
COPY --from=builder /mapproxy/dist/* mapproxy-dist/

# Installing optional packages and MapProxy afterwards
RUN pip install --no-cache-dir requests redis boto3 azure-storage-blob && \
  pip install --no-cache-dir --find-links=./mapproxy-dist --no-index MapProxy && \
  pip cache purge

COPY docker/app.py .
COPY docker/entrypoint.sh .
COPY docker/logging.ini ./config/logging.ini

ENTRYPOINT ["./entrypoint.sh"]

CMD ["echo", "no CMD given"]

LABEL org.opencontainers.image.authors="mapproxy.org"
LABEL org.opencontainers.image.created="$(date -u +%Y-%m-%dT%H:%M:%S%z)"
LABEL org.opencontainers.image.source="https://github.com/mapproxy/mapproxy"
LABEL org.opencontainers.image.title="MapProxy base image"
LABEL org.opencontainers.image.description="Docker image for MapProxy based on Debian bookworm and Python 3.13, including necessary dependencies for running MapProxy applications."
LABEL org.opencontainers.image.url=ghcr.io/mapproxy/mapproxy/mapproxy
LABEL org.opencontainers.image.version=${MAPPROXY_VERSION}

###### development image ######
FROM base AS development

ARG MAPPROXY_VERSION=6.0.1
ENV MAPPROXY_VERSION=${MAPPROXY_VERSION}

EXPOSE 8080

CMD ["mapproxy-util", "serve-develop", "-b", "0.0.0.0", "/mapproxy/config/mapproxy.yaml", "--log-config", "/mapproxy/config/logging.ini"]

LABEL org.opencontainers.image.authors="mapproxy.org"
LABEL org.opencontainers.image.created="$(date -u +%Y-%m-%dT%H:%M:%S%z)"
LABEL org.opencontainers.image.source="https://github.com/mapproxy/mapproxy"
LABEL org.opencontainers.image.title="MapProxy Development Server"
LABEL org.opencontainers.image.description="Docker image for MapProxy development server, based on Debian bookworm and Python 3.13."
LABEL org.opencontainers.image.url=ghcr.io/mapproxy/mapproxy/mapproxy
LABEL org.opencontainers.image.version=${MAPPROXY_VERSION}

##### nginx image ######
FROM base AS nginx

ARG MAPPROXY_VERSION=6.0.1
ARG NGINX_PKG_VERSION=${NGINX_VERSION}-1~bookworm
ARG NGINX_VERSION=1.29.8
ENV MAPPROXY_VERSION=${MAPPROXY_VERSION}
ENV NGINX_PKG_VERSION=${NGINX_PKG_VERSION}
ENV NGINX_VERSION=${NGINX_VERSION}

USER root:root

RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    ca-certificates \
    lsb-release \
    debian-archive-keyring \
    gcc \
    --no-install-recommends \
 && curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
      > /usr/share/keyrings/nginx-archive-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
      http://nginx.org/packages/mainline/debian bookworm nginx" \
      > /etc/apt/sources.list.d/nginx.list \
 && apt-get update \
 && apt-get install -y nginx=${NGINX_PKG_VERSION} --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

USER mapproxy:mapproxy

RUN pip install --no-cache-dir uwsgi && \
    pip cache purge

COPY docker/uwsgi.conf .
COPY docker/nginx-default.conf /etc/nginx/conf.d/default.conf
COPY docker/run-nginx.sh .

USER root:root

RUN chown -R mapproxy:mapproxy /var/log/nginx \
    && chown -R mapproxy:mapproxy /usr/share/nginx \
    && chown -R mapproxy:mapproxy /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R mapproxy:mapproxy /var/run/nginx.pid \
    && mkdir -p /var/cache/nginx/client_temp \
                /var/cache/nginx/proxy_temp \
                /var/cache/nginx/fastcgi_temp \
                /var/cache/nginx/uwsgi_temp \
                /var/cache/nginx/scgi_temp \
    && chown -R mapproxy:mapproxy /var/cache/nginx \
    && chown -R mapproxy:mapproxy /var/run

USER mapproxy:mapproxy

EXPOSE 9090

CMD ["./run-nginx.sh"]

LABEL org.opencontainers.image.authors="mapproxy.org"
LABEL org.opencontainers.image.created="$(date -u +%Y-%m-%dT%H:%M:%S%z)"
LABEL org.opencontainers.image.source="https://github.com/mapproxy/mapproxy"
LABEL org.opencontainers.image.title="MapProxy Docker Image with NGINX and uWSGI"
LABEL org.opencontainers.image.description="Docker image for MapProxy based on Debian bookworm, including NGINX and uWSGI for serving MapProxy applications in a production environment."
LABEL org.opencontainers.image.url=ghcr.io/mapproxy/mapproxy/mapproxy
LABEL org.opencontainers.image.version=${MAPPROXY_VERSION}
