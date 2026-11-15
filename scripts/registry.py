"""Small GHCR client; credentials stay in process memory and never in URLs."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

PACKAGE='reefyai/reefy-frigate'
ACCEPT='application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'

class Registry:
    def __init__(self,write=False):
        scope='repository:'+PACKAGE+':pull'+(',push' if write else '')
        url='https://ghcr.io/token?'+urllib.parse.urlencode({'service':'ghcr.io','scope':scope})
        headers={}
        if os.environ.get('GITHUB_TOKEN'):
            credential=os.environ['GITHUB_ACTOR']+':'+os.environ['GITHUB_TOKEN']
            headers['Authorization']='Basic '+base64.b64encode(credential.encode()).decode()
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as r:self.token=json.load(r)['token']

    def request(self,path,method='GET',data=None,media=None):
        headers={'Authorization':'Bearer '+self.token,'Accept':ACCEPT}
        if media:headers['Content-Type']=media
        req=urllib.request.Request('https://ghcr.io/v2/'+PACKAGE+'/'+path,headers=headers,data=data,method=method)
        return urllib.request.urlopen(req,timeout=60)

    def manifest(self,tag):
        try:
            with self.request('manifests/'+tag) as r:return r.read(),r.headers['Content-Type'],r.headers['Docker-Content-Digest']
        except urllib.error.HTTPError as e:
            if e.code==404:return None
            raise

    def labels(self,raw):
        manifest=json.loads(raw)
        if 'manifests' in manifest:
            image=self.manifest(amd64_image(manifest)['digest'])
            if not image:raise ValueError('Candidate platform manifest missing')
            manifest=json.loads(image[0])
        with self.request('blobs/'+manifest['config']['digest']) as r:config=json.load(r)
        return config['config'].get('Labels',{})


def verify_labels(labels,source,manifest,base):
    expected={'org.opencontainers.image.revision':source,'org.opencontainers.image.version':manifest['version'],
              'org.opencontainers.image.base.name':base['image'],'org.opencontainers.image.base.digest':base['digest']}
    for key,value in expected.items():
        if labels.get(key)!=value:raise ValueError('Candidate provenance mismatch: '+key)


def amd64_image(index):
    images=[item for item in index['manifests'] if item.get('platform',{}).get('os')!='unknown']
    if len(images)!=1 or images[0].get('platform')!={'architecture':'amd64','os':'linux'}:
        raise ValueError('Only the qualified linux/amd64 image may be promoted')
    return images[0]
