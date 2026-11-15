"""Publish the tested image once, under an immutable source-addressed tag."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
variant=sys.argv[1];manifest=json.loads((ROOT/variant/'app.json').read_text());sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
image='ghcr.io/reefyai/reefy-frigate:sha-'+sha+'-'+variant
subprocess.run(['docker','login','ghcr.io','-u',os.environ['GITHUB_ACTOR'],'--password-stdin'],input=os.environ['GITHUB_TOKEN'],text=True,check=True)
subprocess.run(['docker','tag',manifest['image'],image],check=True)
subprocess.run(['docker','push',image],check=True)
print(json.dumps({'candidate_image':image,'source':sha,'release_version':manifest['version']}))
