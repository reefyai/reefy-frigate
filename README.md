# Reefy Frigate Apps

Reefy app manifests for Frigate NVR hardware variants.

## Apps

- `nvidia/` - `Frigate NVR (NVIDIA GPU)`, using the Frigate TensorRT image.
- `intel/` - `Frigate NVR (Intel GPU)`, using the default Frigate image with Intel GPU CDI and a VAAPI default for video decode, plus Intel NPU CDI for OpenVINO detection. Existing Frigate configuration is preserved during upgrades.

Each directory contains an `app.json` manifest and icon that can be published into the Reefy app catalog with `reefy-deploy admin app-publish`.

## Intel initial configuration

Fresh Intel installations use VAAPI video decoding and OpenVINO detection on
the Intel NPU with the bundled YOLO-NAS model. An Intel NPU is required for this
detector configuration; it does not fall back to CPU detection.

The initial configuration enables detection of people, cars, cats, and dogs,
three-day continuous and motion recording retention, and three-day retention
of motion segments for alerts and detections. Cameras start empty and can be
added through Frigate or CamAdmiral. MQTT starts disabled.

Reefy writes this seed only when `config.yml` is absent. Existing configurations
are not overwritten during upgrades. NVIDIA defaults are unchanged.
