# Reefy Frigate Apps

Reefy app manifests for Frigate NVR hardware variants.

## Apps

- `nvidia/` - `Frigate NVR (NVIDIA GPU)`, using the Frigate TensorRT image.
- `intel/` - `Frigate NVR (Intel GPU)`, using the default Frigate image with Intel VAAPI and OpenVINO acceleration.

Each directory contains an `app.json` manifest and icon that can be published into the Reefy app catalog with `reefy-deploy admin app-publish`.
