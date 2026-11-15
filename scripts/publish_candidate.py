"""Publish the tested image once, under an immutable source-addressed tag."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
from registry import Registry, verify_labels
ROOT=Path(__file__).resolve().parents[1]
variant=sys.argv[1];manifest=json.loads((ROOT/variant/'app.json').read_text());sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
image='ghcr.io/reefyai/reefy-frigate:sha-'+sha+'-'+variant
try:
    registry=Registry()
    existing=registry.manifest('sha-'+sha+'-'+variant)
except urllib.error.HTTPError as error:
    if error.code not in (401,403,404):raise
    existing=None
if existing:
    verify_labels(registry.labels(existing[0]),sha,manifest,json.loads((ROOT/'upstream-lock.json').read_text())[variant])
    print(json.dumps({'candidate_image':image,'source':sha,'digest':existing[2],'reused_existing_tested_candidate':True}))
    raise SystemExit(0)
subprocess.run(['docker','login','ghcr.io','-u',os.environ['GITHUB_ACTOR'],'--password-stdin'],input=os.environ['GITHUB_TOKEN'],text=True,check=True)
subprocess.run(['docker','tag',manifest['image'],image],check=True)
subprocess.run(['docker','push',image],check=True)
print(json.dumps({'candidate_image':image,'source':sha,'release_version':manifest['version']}))
