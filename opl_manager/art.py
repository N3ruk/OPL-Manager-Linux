"""OPL Manager V6 SOAP art client, without Windows code or personal telemetry."""
import io
from pathlib import Path
import tempfile
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from .core import require_id,cancelled,import_art,ART_TYPES

ENDPOINT='https://oplmanager.com/API/V6/OplManagerService.asmx'
NS='http://oplmanager.no-ip.info/'
SOAP='http://schemas.xmlsoap.org/soap/envelope/'
ART_LABELS={'COV':'Portada','COV2':'Contraportada','ICO':'Disco / icono','LAB':'Lomo',
            'LGO':'Logo','BG':'Fondo','SCR':'Captura 1','SCR2':'Captura 2'}
MAX_IMAGE=12*1024*1024

class ArtClient:
    def __init__(self):self.user_id=None;self.lock=threading.Lock()
    def soap(self,method,params,cancel=None):
        cancelled(cancel)
        env=ET.Element('{'+SOAP+'}Envelope');body=ET.SubElement(env,'{'+SOAP+'}Body');op=ET.SubElement(body,'{'+NS+'}'+method)
        for key,value in params.items():ET.SubElement(op,'{'+NS+'}'+key).text=str(value)
        req=urllib.request.Request(ENDPOINT,data=ET.tostring(env,encoding='utf-8',xml_declaration=True),
            headers={'Content-Type':'text/xml; charset=utf-8','SOAPAction':'"'+NS+method+'"','User-Agent':'OPL-Manager-Linux/1.2'})
        with urllib.request.urlopen(req,timeout=25) as r:data=r.read(2*1024*1024+1)
        cancelled(cancel)
        if len(data)>2*1024*1024 or b'<!DOCTYPE' in data.upper():raise ValueError('Respuesta del servicio de arte no válida.')
        root=ET.fromstring(data)
        fault=next((e for e in root.iter() if e.tag.rsplit('}',1)[-1]=='Fault'),None)
        if fault is not None:raise ValueError('El servicio de arte ha devuelto un error SOAP.')
        return root
    def catalog(self,game,cancel=None):
        require_id(game.game_id)
        with self.lock:
            if not self.user_id:
                response=self.soap('ServiceStatus',{'userID':'NEW','versionid':37},cancel)
                self.user_id=next((e.text for e in response.iter() if e.tag.rsplit('}',1)[-1]=='userID'),None)
                if not self.user_id:raise ValueError('El servicio no ha proporcionado un identificador de sesión.')
        response=self.soap('ArtSearchSingle',{'type':'POPS' if game.kind=='VCD' else 'PS2',
            'userID':self.user_id,'gameId':game.game_id},cancel)
        return parse_catalog(response)

def parse_catalog(response):
    result=next((e for e in response.iter() if e.tag.rsplit('}',1)[-1]=='ArtSearchSingleResult'),None)
    if result is None:raise ValueError('El servicio no devolvió un catálogo de arte. Vuelve a intentarlo más tarde.')
    catalog={k:[] for k in ART_LABELS}
    for e in result:
        kind=e.tag.rsplit('}',1)[-1]
        if kind not in catalog:continue
        urls=[c.text for c in e] if list(e) else [e.text]
        catalog[kind]=list(dict.fromkeys(safe_art_url(u) for u in urls if u and u.strip()))
    catalog['SCR2']=list(catalog['SCR'])
    return catalog

def safe_art_url(url):
    parsed=urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ('http','https') or parsed.hostname not in ('static.oplmanager.com','static2.oplmanager.com','oplmanager.com') or parsed.username or parsed.password or parsed.port not in (None,80,443):
        raise ValueError('El servicio ha devuelto una URL de imagen no reconocida.')
    return urllib.parse.urlunsplit(('https',parsed.netloc.replace(':80',''),parsed.path,parsed.query,''))

def fetch_image(url,cancel=None):
    from PIL import Image
    cancelled(cancel)
    req=urllib.request.Request(safe_art_url(url),headers={'User-Agent':'OPL-Manager-Linux/1.2'})
    with urllib.request.urlopen(req,timeout=25) as response:
        safe_art_url(response.geturl());data=response.read(MAX_IMAGE+1)
    cancelled(cancel)
    if len(data)>MAX_IMAGE:raise ValueError('La imagen supera 12 MiB.')
    with Image.open(io.BytesIO(data)) as image:
        if image.width*image.height>32_000_000:raise ValueError('Imagen excesivamente grande.')
        image.verify()
    return data

def save_art_bytes(game,data,kind,overwrite=False):
    with tempfile.NamedTemporaryFile(suffix='.image') as f:
        f.write(data);f.flush();return import_art(game,Path(f.name),kind,overwrite)

def download_art_batch(games,kinds,overwrite=False,progress=None,cancel=None,client=None):
    client=client or ArtClient();saved=0;missing=0;errors=[];seen=set()
    games=[g for g in games if g.game_id];total=len(games)*len(kinds);done=0
    for game in games:
        cancelled(cancel)
        key=(str(game.root),game.game_id,game.kind=='VCD')
        if key in seen:continue
        seen.add(key)
        wanted=[k for k in kinds if overwrite or not game.art_path(k)]
        try:catalog=client.catalog(game,cancel) if wanted else {}
        except Exception as e:
            cancelled(cancel);errors.append(f'{game.game_id}: {e}');done+=len(kinds)
            if progress:progress(done,total,game.title)
            continue
        for kind in kinds:
            cancelled(cancel);done+=1
            if kind in wanted:
                urls=catalog.get(kind,[])
                if not urls:missing+=1
                else:
                    try:
                        # Use a distinct second screenshot when available.
                        pos=1 if kind=='SCR2' and len(urls)>1 else 0
                        data=fetch_image(urls[pos],cancel);cancelled(cancel)
                        save_art_bytes(game,data,kind,overwrite);saved+=1
                    except Exception as e:
                        cancelled(cancel);errors.append(f'{game.game_id} {kind}: {e}')
            if progress:progress(done,total,game.title+' · '+kind)
    return saved,missing,errors
