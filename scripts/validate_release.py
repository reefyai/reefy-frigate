import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def validate(manifest,variant):
    tag='0.18.2'+('-tensorrt' if variant=='nvidia' else '')
    assert manifest['upstream_image']=='ghcr.io/blakeblackshear/frigate:'+tag
    assert re.fullmatch(re.escape(tag)+r'-reefy\.\d{4}-\d{2}-\d{2}-\d{2}',manifest['version'])
    assert manifest['image']=='ghcr.io/reefyai/reefy-frigate:'+manifest['version']
    assert manifest['slug']==('frigate-intel' if variant=='intel' else 'frigate')
    for name,storage,mount in [('config','state','/config'),('models','state','/models'),('media','bulk','/media/frigate')]:
        assert manifest['volumes'][name]['storage_class']==storage
        assert manifest['volumes'][name]['mount']==mount
    lock=json.loads((ROOT/'upstream-lock.json').read_text())[variant]
    assert lock['image']==manifest['upstream_image'] and re.fullmatch('sha256:[a-f0-9]{64}',lock['digest'])
    if variant=='intel':assert set(manifest['devices'])=={'intel.com/gpu=all','intel.com/npu=all'}
    return lock

if __name__=='__main__':
    for variant in ['intel','nvidia']:validate(json.loads((ROOT/variant/'app.json').read_text()),variant)
