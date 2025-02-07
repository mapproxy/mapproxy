FROM python:3.12-slim-bookworm AS base-libs

LABEL maintainer="mapproxy.org"

RUN apt update && apt -y install --no-install-recommends \
  python3-pil \
  python3-yaml \
  python3-pyproj \
  libgeos-dev \
  python3-lxml \
  libgdal-dev \
  python3-shapely \
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

RUN rm -rf dist/*
RUN pip wheel . -w dist


FROM base-libs AS base

RUN mkdir /mapproxy

RUN groupadd mapproxy && \
    useradd --home-dir /mapproxy -s /bin/bash -g mapproxy mapproxy && \
    chown -R mapproxy:mapproxy /mapproxy

USER mapproxy:mapproxy

WORKDIR /mapproxy

ENV PATH="${PATH}:/mapproxy/.local/bin"

RUN mkdir mapproxy-dist
COPY --from=builder /mapproxy/dist/* mapproxy-dist/

RUN pip install requests redis boto3 azure-storage-blob Shapely && \
  pip install --find-links=./mapproxy-dist --no-index MapProxy && \
  pip cache purge

COPY docker/app.py .

COPY docker/entrypoint.sh .

ENTRYPOINT ["./entrypoint.sh"]

CMD ["echo", "no CMD given"]

###### development image ######

FROM base AS development

EXPOSE 8080

CMD ["mapproxy-util", "serve-develop", "-b", "0.0.0.0", "/mapproxy/config/mapproxy.yaml"]

##### nginx image ######

FROM base AS nginx

USER root:root

RUN apt update && apt -y install --no-install-recommends nginx gcc \
  && apt-get -y --purge autoremove \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER mapproxy:mapproxy

RUN pip install uwsgi && \
    pip cache purge

COPY docker/uwsgi.conf .

COPY docker/nginx-default.conf /etc/nginx/sites-enabled/default

COPY docker/run-nginx.sh .

EXPOSE 80

USER root:root

RUN chown -R mapproxy:mapproxy /var/log/nginx \
    && chown -R mapproxy:mapproxy /var/lib/nginx \
    && chown -R mapproxy:mapproxy /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R mapproxy:mapproxy /var/run/nginx.pid

USER mapproxy:mapproxy

CMD ["./run-nginx.sh"]
