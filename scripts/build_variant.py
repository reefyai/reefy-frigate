import json
from pathlib import Path
import subprocess
import sys
from validate_release import validate
from ci_image_retry import pull_image

ROOT=Path(__file__).resolve().parents[1]
variant=sys.argv[1];manifest=json.loads((ROOT/variant/'app.json').read_text());lock=validate(manifest,variant)
pull_image(['docker'],lock['image']+'@'+lock['digest'])
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
args=['docker','build','--build-arg','UPSTREAM_IMAGE='+lock['image']+'@'+lock['digest'],
      '--build-arg','UPSTREAM_NAME='+lock['image'],'--build-arg','UPSTREAM_DIGEST='+lock['digest'],
      '--build-arg','PACKAGE_VERSION='+manifest['version'],'--build-arg','SOURCE_REVISION='+source,
      '-t',manifest['image'],'.']
subprocess.run(args,check=True,cwd=ROOT)
