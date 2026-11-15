"""Promote already-tested registry manifests and tag the exact qualified source."""
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from registry import Registry,verify_labels
ROOT=Path(__file__).resolve().parents[1]
SOURCE=os.environ['RELEASE_SOURCE']
assert re.fullmatch('[a-f0-9]{40}',SOURCE),'A full qualified source commit is required'
REPO=os.environ['GITHUB_REPOSITORY']

def github(path,data=None):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

runs=github('actions/workflows/release-check.yml/runs?head_sha='+SOURCE+'&status=success&per_page=50')['workflow_runs']
assert any(r['head_sha']==SOURCE and r['conclusion']=='success' for r in runs),'Exact source has no successful complete release gate'
registry=Registry(write=True)
for variant in ['intel','nvidia']:
    manifest=json.loads((ROOT/variant/'app.json').read_text());base=json.loads((ROOT/'upstream-lock.json').read_text())[variant]
    candidate=registry.manifest('sha-'+SOURCE+'-'+variant)
    assert candidate,'Qualified candidate image is missing'
    raw,media,digest=candidate;verify_labels(registry.labels(raw),SOURCE,manifest,base)
    existing=registry.manifest(manifest['version'])
    if existing and existing[2]!=digest:raise ValueError('Refusing to overwrite an immutable release image')
    try:
        tag=github('git/ref/tags/'+manifest['version'])
        assert tag['object']['sha']==SOURCE,'Release tag points to different source'
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        tag=None
    if not existing:
        with registry.request('manifests/'+manifest['version'],method='PUT',data=raw,media=media) as r:
            assert r.headers['Docker-Content-Digest']==digest
    if not tag:github('git/refs',{'ref':'refs/tags/'+manifest['version'],'sha':SOURCE})
    print(json.dumps({'variant':variant,'version':manifest['version'],'digest':digest,'source':SOURCE}))
