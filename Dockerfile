ARG UPSTREAM_IMAGE
FROM ${UPSTREAM_IMAGE}
ARG UPSTREAM_IMAGE
ARG UPSTREAM_NAME
ARG UPSTREAM_DIGEST
ARG PACKAGE_VERSION
ARG SOURCE_REVISION
LABEL org.opencontainers.image.source="https://github.com/reefyai/reefy-frigate" \
      org.opencontainers.image.version="${PACKAGE_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.base.name="${UPSTREAM_NAME}" \
      org.opencontainers.image.base.digest="${UPSTREAM_DIGEST}"
COPY patches/ /opt/reefy-frigate/patches/
COPY scripts/apply_backport.py /opt/reefy-frigate/scripts/apply_backport.py
RUN python3 /opt/reefy-frigate/scripts/apply_backport.py /opt/reefy-frigate
