"""Run inside the existing Frigate container for private hardware qualification.

Read-only except FFmpeg's transient decoder allocations. Never save images or
video; output contains hashes instead of camera names, paths or credentials.
Keep hardware observations private rather than publishing them as CI fixtures.
An operator may prepend BASELINE from its prior private JSON observation.
"""
import concurrent.futures
import glob
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.request
import yaml

BASELINE = None
DECODE = False

def digest(value):
    if not isinstance(value,bytes):value=str(value).encode()
    return hashlib.sha256(value).hexdigest()

def api(path):
    with urllib.request.urlopen('http://127.0.0.1:5000/api/'+path,timeout=15) as response:
        return json.load(response)

config=api('config');stats=api('stats');now=time.time()
saved_path=next(p for p in (Path('/config/config.yml'),Path('/config/config.yaml')) if p.is_file())
saved=saved_path.read_bytes();policy=yaml.safe_load(saved)
db=sqlite3.connect('file:/config/frigate.db?mode=ro',uri=True);db.execute('PRAGMA query_only=ON')
rows=[];active=[]
for key,camera in stats['cameras'].items():
    if camera.get('camera_fps',0)>0 and Path('/proc/'+str(camera.get('capture_pid'))).exists():
        active.append(digest(key))
        row=db.execute('SELECT id,path,end_time FROM recordings WHERE camera=? AND end_time<? AND duration>=2 ORDER BY start_time DESC LIMIT 1',(key,now-10)).fetchone()
        if row and Path(row[1]).is_file():rows.append((digest(key),row))
files=[]
for cam,(identifier,path,end) in rows:
    files.append({'camera_hash':cam,'id_hash':digest(identifier),'path_hash':digest(path),
                  'file_sha256':digest(Path(path).read_bytes()),'end_time':end})
preserved=[]
if BASELINE:
    wanted={item['id_hash']:item for item in BASELINE.get('recording_samples',[])}
    for identifier,path in db.execute('SELECT id,path FROM recordings ORDER BY end_time DESC LIMIT 100000'):
        old=wanted.get(digest(identifier))
        if old:
            preserved.append({'id_hash':digest(identifier),'same_bytes':Path(path).is_file() and digest(Path(path).read_bytes())==old['file_sha256']})
    assert len(preserved)==len(wanted) and all(item['same_bytes'] for item in preserved),'Prior recording bytes were not preserved'
    assert digest(saved)==BASELINE['saved_config_sha256'],'Saved configuration changed during image-only update'

result={'observed_at':now,'version':stats['service']['version'],'uptime':stats['service']['uptime'],
 'saved_config_sha256':digest(saved),'camera_identity_sha256':digest(json.dumps(sorted(config['cameras']))),
 'capture_camera_hashes':sorted(active),'fresh_recordings':sum(now-f['end_time']<90 for f in files),
 'recording_samples':files,'preserved_samples':preserved,
 'database_quick_check':db.execute('PRAGMA quick_check').fetchone()[0],
 'record_policy_sha256':digest(json.dumps(policy.get('record'),sort_keys=True)),
 'detector_devices':{k:{'type':v.get('type'),'device':v.get('device')} for k,v in config.get('detectors',{}).items()},
 'detectors':{k:{'inference_speed':v.get('inference_speed'),'process_exists':Path('/proc/'+str(v.get('pid'))).exists()} for k,v in stats.get('detectors',{}).items()},
 'detection_fps':stats.get('detection_fps'), 'hwaccel_args':config.get('ffmpeg',{}).get('hwaccel_args'),
 'patched_source_sha256':digest(Path('/opt/frigate/frigate/video/ffmpeg.py').read_bytes())}
if DECODE:
    executable=sorted(glob.glob('/usr/lib/ffmpeg/*/bin/ffmpeg'))[-1]
    def decode(item):
        cam,row=item
        r=subprocess.run([executable,'-v','error','-nostdin','-threads','1','-i',row[1],'-map','0:v:0','-frames:v','5','-f','null','-'],capture_output=True,timeout=25)
        return {'camera_hash':cam,'success':r.returncode==0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:result['decode_checks']=list(pool.map(decode,rows))
db.close();print(json.dumps(result))
