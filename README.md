# Reefy Frigate Apps

Reefy app manifests for Frigate NVR hardware variants.

## Apps

- `nvidia/` - `Frigate NVR (NVIDIA GPU)`, using the Frigate TensorRT image.
- `intel/` - `Frigate NVR (Intel GPU)`, using the default Frigate image with Intel GPU CDI and a VAAPI default for video decode, plus Intel NPU CDI for OpenVINO detection. Existing Frigate configuration is preserved during upgrades.

Each directory contains an `app.json` manifest and icon that can be published into the Reefy app catalog with `reefy-deploy admin app-publish`.

## Storage classes

Both variants declare media as `bulk`, and config/models as `state`. On
firmware advertising `bulk_storage_quotas: 1`, Reefy limits media growth using
real thin-pool pressure while leaving the config database outside that quota.
Frigate uses its normal low-space recording cleanup. Existing recording and
backup settings are preserved. Publish the compatible backend before these
manifests so older firmware can retain its previous class-free definition.
