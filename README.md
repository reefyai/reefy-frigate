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

## Maintained 0.18.2 backport

The derivative packages apply upstream Frigate PR
[24663](https://github.com/blakeblackshear/frigate/pull/24663), merged as
`15da89e`, to prevent raw FFmpeg stdout accumulating in the capture watchdog
while a stalled decoder exits. The existing 30-second termination timeout,
force-kill, reap, and replacement behavior remain intact. This backport does
not introduce external recovery of an already-dead capture process.

`upstream-lock.json` pins each official amd64 base image by digest. The original
patch and input/output file hashes are recorded under `patches/`. Builds reject
unexpected upstream files or changed patch context. Intel retains VAAPI and
OpenVINO GPU/NPU access; NVIDIA retains the official TensorRT base. Existing
volume names, paths, storage classes, seed behavior and user settings remain.

### Qualification

Pull requests from this repository and manual checks run on self-hosted
runners. Fork PRs do not execute on trusted runners. Docker tests run in a
privileged disposable job container with its own daemon, private credentials,
anonymous storage, private cgroup namespace and verified memory/PID limits.
They never use the shared host Docker socket. The private-Docker harness is
adapted from the qualified Reefy CamAdmiral harness at
`a3a6a0da502f89a920953d2c3922ed378615d369`.

For each variant the committed checks:

1. Build from the pinned official base and verify the exact patched file hash.
2. Run the same reset contracts on baseline and fixed images. Exactly two
   buffering contracts must fail on baseline; all four must pass when fixed.
3. Exercise the installed reset method with a real subprocess that ignores
   SIGTERM, emits 256 MiB of raw data and continues writing. Baseline must fail
   specifically from excess memory or its enforced container OOM. The fixed
   worker must remain below 32 MiB RSS growth, preserve the 30-second bound,
   reap the old child and verify output from its replacement.
4. Boot real Frigate through 0.17.0, unmodified 0.18.2 and the derivative with
   persistent synthetic camera configuration, database markers and recordings.
   Every stage must save and decode fresh video and preserve prior media.

Commands inside the disposable Actions Docker lab:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_variant.py intel
python3 tests/e2e/run_reset_memory.py intel
python3 tests/upgrade_e2e.py intel
```

Repeat the variant commands with `nvidia`. Logs, measured memory, source hashes
and upgrade evidence are retained as normal Actions artifacts. Hardware
acceleration is qualified separately on dev devices with their existing apps,
configuration and recordings preserved.

### Publication and promotion

Successful per-variant gates publish source-addressed candidate images to
`ghcr.io/reefyai/reefy-frigate`. The publication workflow requires the complete
successful gate for the exact merged source commit and verifies candidate OCI
source/version/base labels. It promotes the already-tested manifest digest to
the immutable package tag, without rebuilding or moving an existing tag.

Package versions use `<upstream-image-tag>-reefy.<YYYY-MM-DD-NN>`. The manifest,
release image, exact-source Git tag and OCI version agree. Publish the tagged
Intel and NVIDIA manifests to the dev catalog with the existing
`reefy-deploy admin app-publish <slug> --ref <package-tag>`, update the existing
dev instances and verify acceleration, fresh recordings, preserved database
and configuration. Then publish the same tags to prod and perform normal app
updates. Catalog source pins must advance alongside the release; no backend
or firmware modification is needed to run the images.

For the next upstream version, check whether the upstream fix is already
included. Remove the backport once included and qualify the official image;
do not reapply it blindly or keep a diverging full source fork. Existing
published versions and rollback history remain immutable.
