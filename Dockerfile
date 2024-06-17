FROM python:3.10-slim-bookworm AS builder

COPY . mapproxy/

WORKDIR mapproxy

RUN pip install -e .

RUN python setup.py egg_info -b "" -D bdist_wheel


FROM python:3.10-slim-bookworm AS base

LABEL maintainer="mapproxy.org"

# The MAPPROXY_VERSION argument can be used like this to overwrite the default:
# docker build --build-arg MAPPROXY_VERSION=1.15.1 [--target base|development|nginx] -t mapproxy:1.15.1 .
ARG MAPPROXY_VERSION=1.16.0

RUN apt update && apt -y install --no-install-recommends \
  python3-pil \
  python3-yaml \
  python3-pyproj \
  libgeos-dev \
  python3-lxml \
  libgdal-dev \
  python3-shapely \
  libxml2-dev libxslt-dev && \
  apt-get -y --purge autoremove && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN mkdir /mapproxy

WORKDIR /mapproxy

# fix potential issue finding correct shared library libproj (fixed in newer releases)
RUN ln -s /usr/lib/`uname -m`-linux-gnu/libproj.so /usr/lib/`uname -m`-linux-gnu/liblibproj.so

COPY --from=builder /mapproxy/dist/MapProxy-*.whl .

RUN ls

RUN ls ./MapProxy-*.whl

RUN pip install $(ls ./MapProxy-*.whl) && \
    pip cache purge && \
    rm MapProxy-*.whl

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

RUN apt update && apt -y install --no-install-recommends nginx gcc

# cleanup
RUN apt-get -y --purge autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uwsgi && \
    pip cache purge

COPY docker/uwsgi.conf .

COPY docker/nginx-default.conf /etc/nginx/sites-enabled/default

EXPOSE 80

CMD ["/usr/local/bin/uwsgi", "--ini", "/mapproxy/uwsgi.conf", "&&", "/usr/sbin/nginx", "-g", "daemon off;"]
