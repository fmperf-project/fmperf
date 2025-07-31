
## Base layer ##################################################################
# Use the watson-core base python image that comes in a variety of fun flavors
ARG BASE_UBI_IMAGE_TAG=9.3-1610
ARG PYTHON_TAG=py311
ARG PYTHON_VERSION=3.11
ARG SOURCE_DIR="fmperf"

FROM registry.access.redhat.com/ubi9/ubi:${BASE_UBI_IMAGE_TAG} as base
ARG PYTHON_VERSION=3.11

RUN dnf remove -y --disableplugin=subscription-manager \
        subscription-manager \
        # we install newer version of requests via pip
    python${PYTHON_VERSION}-requests \
    && dnf install -y make git \
        # to help with debugging
        procps \
    && dnf clean all

# install python
RUN dnf install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-pip && \
    dnf clean all && \
    ln -fs /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 && \
    ln -s /usr/bin/python${PYTHON_VERSION} /usr/local/bin/python && ln -s /usr/bin/pip${PYTHON_VERSION} /usr/local/bin/pip


# Set default working dir
WORKDIR /app

## Dev Dependencies Layer ######################################################
FROM base as dev_dependencies

COPY requirements.txt requirements-dev.txt /app/

# speed up pip installs by caching a directory across builds
# https://pythonspeed.com/articles/docker-cache-pip-downloads/
RUN --mount=type=cache,target=/root/.cache \
    true \
    && pip install -r /app/requirements.txt \
    && pip install -r /app/requirements-dev.txt \
    && true

# Install kustomize
RUN curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh"  | bash && \
    mv kustomize /usr/local/bin

## Build Layer #################################################################
FROM dev_dependencies as build
ARG PYTHON_TAG
ARG SOURCE_DIR

# install TGIS protobufs
RUN git clone https://github.com/IBM/text-generation-inference.git && \
    cd text-generation-inference && \
    git checkout 9b4aea86846a5131bc6f672023cae5064bf9645c && \
    cd integration_tests && \
    make gen-client && \
    pip install . --no-cache-dir

# Build the wheel
# Pull in source files
COPY ${SOURCE_DIR} /app/${SOURCE_DIR}
COPY setup.py /app/setup.py
RUN python setup.py bdist_wheel --python-tag ${PYTHON_TAG} clean --all

# And install it
RUN pip install --no-cache-dir /app/dist/*.whl

## Release Layer ###############################################################
FROM base as release
ARG SOURCE_DIR

# copy installed python dependencies
# Should include the wheel install + anything in requirements.txt
COPY --from=build /usr/local/ /usr/local/

# Create fmperf user
RUN adduser --uid 12345 --gid 0 fmperf 
USER fmperf
WORKDIR /home/fmperf

# Set permissions for openshift
RUN chmod -R g+rwx /home/fmperf

ENV REQUESTS_DIR=/requests
# Sanity check: We can import the installed wheel
RUN python -c "import ${SOURCE_DIR}"
