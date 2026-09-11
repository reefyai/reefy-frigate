# Reefy Frigate Apps

Reefy app manifests for Frigate NVR hardware variants.

## Apps

- `nvidia/` - `Frigate NVR (NVIDIA GPU)`, using the Frigate TensorRT image.
- `intel/` - `Frigate NVR (Intel GPU)`, using the default Frigate image with Intel GPU CDI and a VAAPI default for video decode, plus Intel NPU CDI for OpenVINO detection. Existing Frigate configuration is preserved during upgrades.

Each directory contains an `app.json` manifest and icon that can be published into the Reefy app catalog with `reefy-deploy admin app-publish`.

## Storage policy

These manifests require Reefy firmware supporting storage pressure quotas.
Configuration and the database use `state`; recordings, recording scratch, and
downloadable models use `bulk`. Scratch is mounted separately at `/tmp/cache`,
so it shares the media pressure policy. Reefy must preserve pending scratch
segments when migrating an existing container to that mount. Frigate continues
to use its own low-space cleanup; no Frigate code changes are required.
