##############################################################################
# This is a multi-stage Dockerfile with three targets:
#   * libreg_local_db
#   * webapp_dev
#   * webapp_prod
# 
# For background on multi-stage builds, see:
#
#   https://docs.docker.com/develop/develop-images/multistage-build/
#
##############################################################################


##############################################################################
# Build target: libreg_local_db
FROM postgis/postgis:12-3.1 AS libreg_local_db

ENV POSTGRES_PASSWORD="password"
ENV POSTGRES_USER="postgres"

COPY ./docker/postgis_init.sh /docker-entrypoint-initdb.d/postgis-init.sh

EXPOSE 5432
##############################################################################


##############################################################################
# Intermediate target: builder
#
# This stage builds out the common pieces of the dev and prod images, and isn't
# meant to be used as a build target. Though feel free--I'm a docstring, not a
# cop. It does the following:
#
#  * Installs Nginx from source, mirroring the process used in the official
#    Nginx Docker images.
#  * Installs uWSGI and Supervisor from the Alpine system packages.
#  * Installs pipenv from PyPI, via the system pip from the base Python image
#  * Copies in the config files for uWSGI, Nginx, and Supervisor
#  * Sets the container entrypoint, which is a script that starts Supervisor

FROM python:3.9.2-alpine3.13 AS builder

EXPOSE 80

##### Install NGINX #####
# This is a simplified version of the offical Nginx Dockerfile for Alpine 3.13:
# https://github.com/nginxinc/docker-nginx/blob/dcaaf66e4464037b1a887541f39acf8182233ab8/mainline/alpine/Dockerfile
ENV NGINX_VERSION 1.19.8
ENV NJS_VERSION   0.5.2
ENV PKG_RELEASE   1

RUN set -x \
    && addgroup -g 101 -S nginx \
    && adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx \
    && nginxPackages=" \
        nginx=${NGINX_VERSION}-r${PKG_RELEASE} \
        nginx-module-xslt=${NGINX_VERSION}-r${PKG_RELEASE} \
        nginx-module-geoip=${NGINX_VERSION}-r${PKG_RELEASE} \
        nginx-module-image-filter=${NGINX_VERSION}-r${PKG_RELEASE} \
        nginx-module-njs=${NGINX_VERSION}.${NJS_VERSION}-r${PKG_RELEASE} \
    " \
    && KEY_SHA512="e7fa8303923d9b95db37a77ad46c68fd4755ff935d0a534d26eba83de193c76166c68bfe7f65471bf8881004ef4aa6df3e34689c305662750c0172fca5d8552a *stdin" \
    && apk add --no-cache --virtual .cert-deps openssl \
    && wget -O /tmp/nginx_signing.rsa.pub https://nginx.org/keys/nginx_signing.rsa.pub \
    && if [ "$(openssl rsa -pubin -in /tmp/nginx_signing.rsa.pub -text -noout | openssl sha512 -r)" = "$KEY_SHA512" ]; then \
        echo "key verification succeeded!"; \
        mv /tmp/nginx_signing.rsa.pub /etc/apk/keys/; \
    else \
        echo "key verification failed!"; \
        exit 1; \
    fi \
    && apk del .cert-deps \
    && apk add -X "https://nginx.org/packages/mainline/alpine/v$(egrep -o '^[0-9]+\.[0-9]+' /etc/alpine-release)/main" --no-cache $nginxPackages \
    && if [ -n "$tempDir" ]; then rm -rf "$tempDir"; fi \
    && if [ -n "/etc/apk/keys/abuild-key.rsa.pub" ]; then rm -f /etc/apk/keys/abuild-key.rsa.pub; fi \
    && if [ -n "/etc/apk/keys/nginx_signing.rsa.pub" ]; then rm -f /etc/apk/keys/nginx_signing.rsa.pub; fi \
    && apk add --no-cache --virtual .gettext gettext \
    && mv /usr/bin/envsubst /tmp/ \
    \
    && runDeps="$( \
        scanelf --needed --nobanner /tmp/envsubst \
            | awk '{ gsub(/,/, "\nso:", $2); print "so:" $2 }' \
            | sort -u \
            | xargs -r apk info --installed \
            | sort -u \
    )" \
    && apk add --no-cache $runDeps \
    && apk del .gettext \
    && mv /tmp/envsubst /usr/local/bin/ \
    && apk add --no-cache tzdata \
    && apk add --no-cache curl ca-certificates

##### Set up uWSGI, Nginx, and Supervisor #####

RUN apk add --no-cache uwsgi-python3 supervisor \
 && pip install pipenv

# This causes pipenv not to spam the build output with extra lines.
#   https://github.com/pypa/pipenv/issues/4052#issuecomment-588480867
ENV CI 1

COPY ./docker/uwsgi.ini /etc/uwsgi/libreg_uwsgi.ini
COPY ./docker/nginx.conf /etc/nginx/nginx.conf
COPY ./docker/supervisord-alpine.ini /etc/supervisord.conf
COPY ./docker/docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT ["sh", "/docker-entrypoint.sh"]

##############################################################################



##############################################################################
# Build target: libreg_dev
# 
# This target is meant for local development, and does a few things worth mentioning:
#
#   * During the image build, it installs the project's Python dependencies by
#     copying the current version of the Pipfile and Pipfile.lock into the image,
#     installing system build dependencies, then installing the Python packages
#     to a virtualenv linked to the /libreg_app directory.
#   * It doesn't get the project source from GitHub, instead relying on a Docker
#     bind mount when the container is started. That way, the running container
#     can do file watching of the project files as they exist on the host, and
#     none of your edits are lost when the container exits.
#
# To make that work, a directory is created at /libreg_app to be the eventual
# target of the bind mount. However since mounts are not available at build time,
# and the relationship between the virtualenv and the project directory is based
# on the location of the Pipfile at the time you run `pipenv install`, it's 
# necessary to copy the Pipfile and Pipfile.lock into /libreg_app during the
# build process, install the Python dependencies, then allow that directory to
# be overwritten at run time by the bind mount.
#
# All of which is to say this process is slightly delicate, and it's pipenv's fault.
# 
# Also, DANGER WILL ROBINSON, if you are going to install new packages to the dev
# env while it's running, be aware that you must do so from INSIDE the container,
# NOT from the host machine. If you run `pipenv install somepackage` on the host,
# it will end up in a virtualenv directory ON THE HOST, and your running code
# inside the container will not find it. Shell into the container, then install.
FROM builder AS libreg_dev

# This creates the /libreg_app directory without issuing a separate RUN directive.
WORKDIR /libreg_app

# Setting WORKON_HOME causes pipenv to put its virtualenv in a pre-determined, 
# OS-independent location. Note that /libreg_venv is NOT the virtualenv, it's 
# just the parent directory for virtualenvs created by pipenv. The actual venv
# is in a directory called something like
# /libreg_venv/libreg_app-QOci6oRN, which follows the pattern 
# '<name-of-project-dir>-<hashval>', where the hashval is deterministic and based on
# the path to the Pipfile. See this issue comment for a description of how that
# name is built:
#
#   https://github.com/pypa/pipenv/issues/1226#issuecomment-598487793
#
ENV WORKON_HOME /libreg_venv

# Install the system dependencies and the Python dependencies. Note that if 
# you want to be able to install new Python dependencies on the fly from
# within the container, you should remove the line below that deletes the
# build dependencies (`apk del --no-network .build-deps`), then rebuild
# the image.
RUN set -ex \
	&& apk add --no-cache --virtual .build-deps  \
		bluez-dev \
        build-base \
		bzip2-dev \
		coreutils \
		dpkg-dev dpkg \
		expat-dev \
		findutils \
		gcc \
		gdbm-dev \
        jpeg-dev \
		libc-dev \
		libffi-dev \
		libnsl-dev \
		libtirpc-dev \
        libxslt-dev \
		linux-headers \
		make \
		ncurses-dev \
		openssl-dev \
		pax-utils \
        postgresql-dev \
		readline-dev \
		sqlite-dev \
		tcl-dev \
		tk \
		tk-dev \
		util-linux-dev \
		xz-dev \
		zlib-dev 

# Copy the Pipfiles to the temporary app directory, so the install's virtualenv 
# path is still correct when the bind mount is applied at run time.
COPY ./Pipfile ./
COPY ./Pipfile.lock ./

RUN mkdir ${WORKON_HOME} \
 && cd /libreg_app \
 && pipenv install --dev --skip-lock
	#&& apk del --no-network .build-deps

##############################################################################


##############################################################################
FROM builder AS libreg_prod

##############################################################################