"""Refresh the public Kiaasa catalogue from its sitemap and product pages.

Run from the project root: backend/venv/Scripts/python.exe backend/refresh_catalogue.py
No login, private API or API key is used. Collection membership comes from the
published occasion and season attributes; new arrivals use the newest season.
"""
import concurrent.futures
import hashlib
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from contextlib import contextmanager
import xml.etree.ElementTree as ET
from collections import Counter
from catalogue_overrides import apply_catalogue_overrides
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'backend/data/catalogue-pages'
SOURCE = 'https://www.kiaasa.in/sitemap/products.xml'
USE_CACHE = '--cached' in sys.argv
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c,Node) else c for c in self.children).split())
    def find(self, tag=None, cls=None):
        found=[]
        if (tag is None or self.tag==tag) and (cls is None or cls in self.attrs.get('class','').split()): found.append(self)
        for c in self.children:
            if isinstance(c,Node): found.extend(c.find(tag,cls))
        return found

class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.root=Node(); self.stack=[self.root]; self.feed(html)
    def handle_starttag(self, tag, attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in VOID:self.stack.append(n)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,data):self.stack[-1].children.append(data)

def allowed_source(url):
    parsed=urllib.parse.urlsplit(url)
    return (parsed.scheme=='https' and parsed.hostname in {'www.kiaasa.in','kiaasa.in'}
            and parsed.port in {None,443} and not parsed.username and not parsed.password)

class SourceRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not allowed_source(newurl):raise ValueError('Unexpected catalogue redirect host.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url):
    if not allowed_source(url):raise ValueError('Unexpected catalogue source host.')
    for attempt in range(3):
        try:
            opener=urllib.request.build_opener(SourceRedirect())
            request=urllib.request.Request(url,headers={'User-Agent':'Kiaasa-Catalogue-Sync/1.0'})
            with opener.open(request, timeout=30) as response:
                content=response.read(5*1024*1024+1)
                if len(content)>5*1024*1024:raise ValueError('Catalogue response is too large.')
                return content
        except Exception:
            if attempt==2:raise
            time.sleep(attempt+1)

@contextmanager
def refresh_lock():
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    with (CACHE.parent/'catalogue-sync.lock').open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if sys.platform=='win32':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            handle.seek(0)
            if sys.platform=='win32':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

def parse_product(html,url,rank):
    root=Page(html).root
    meta={n.attrs.get('property',n.attrs.get('name','')):n.attrs.get('content','') for n in root.find('meta')}
    name=meta.get('og:title') or meta.get('title')
    prices=root.find(cls='proprice')
    if not name or not prices:raise ValueError('Missing product name or published price')
    price_text=prices[0].text()
    amounts=[float(n.replace(',','')) for n in re.findall(r'\u20b9\s*([\d,]+(?:\.\d+)?)',price_text)]
    if not amounts:raise ValueError('No published numeric price')
    specs={}
    for group in root.find(cls='specification-cover'):
        for li in group.find('li'):
            spans=li.find('span')
            if len(spans)>=2:specs[spans[0].text().strip(' :')]=spans[1].text()
    links=[n for n in root.find('a') if n.attrs.get('href','').startswith('/products/')]
    category=links[0].text() if links else 'Ethnic Wear'
    size_groups=root.find(cls='size_chart_list')
    sizes=list(dict.fromkeys(n.text() for g in size_groups[:1] for n in g.find('li') if n.text()))
    occasion=specs.get('Occasion','')
    description=meta.get('description','')
    collections=[]
    # The website also labels products in titles (some occasions say "Core Basic").
    labels=occasion+' '+category+' '+name
    if re.search(r'festiv|party|wedding|celebration',labels,re.I):collections.append('festive')
    if re.search(r'casual|daily|everyday|office|work wear|core basic',labels,re.I):collections.append('everyday')
    # Use the published description when neither field specifies an occasion.
    if not collections:
        if re.search(r'festiv|party|wedding',description,re.I):collections.append('festive')
        if re.search(r'casual|daily|everyday|office',description,re.I):collections.append('everyday')
    unavailable=bool(re.search(r'(?:sold out|out of stock)',price_text,re.I))
    return {'name':name,'category':category,'price':amounts[0],
        'original_price':max(amounts) if len(amounts)>1 else None,
        'color':specs.get('Primary Color',specs.get('Top Colour')),
        'style':specs.get('Dress Shape',specs.get('Style')),
        'fabric':specs.get('Primary Material',specs.get('Top Fabric')),
        'features':list(dict.fromkeys(specs[k] for k in ['Pattern','Type Of Work','Technique Embellishment','Neck Type'] if specs.get(k))),
        'occasion':[x.strip() for x in re.split(r'[,/]',occasion) if x.strip()],
        'sizes':sizes,'stock':'unavailable' if unavailable else 'unknown',
        'url':url,'image_url':meta.get('og:image'),'image_source_url':meta.get('og:image'),
        'description':description,'season':specs.get('Season'),'specifications':specs,
        'latest_collection_rank':rank,'collection_source_url':SOURCE,'collections':collections}

def get_product(item, use_cache=False):
    rank,url=item
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
    raw=path.read_bytes() if use_cache and path.exists() else fetch(url);path.write_bytes(raw)
    return parse_product(raw.decode('utf-8',errors='replace'),url,rank)

def season_key(value):
    s=(value or '').upper();m=re.search(r'(\d{2,4})',s)
    if not m:return (0,0)
    year=int(m.group(1));year=year+2000 if year<100 else year
    return (year,2 if re.search(r'AW|FW|WINTER|AUTUMN',s) else 1)

def import_snapshot(use_cache=None):
    if use_cache is None: use_cache = USE_CACHE
    CACHE.mkdir(parents=True,exist_ok=True)
    sitemap_path=ROOT/'backend/data/products-sitemap.xml'
    sitemap=sitemap_path.read_bytes() if use_cache and sitemap_path.exists() else fetch(SOURCE)
    sitemap_path.write_bytes(sitemap)
    urls=list(dict.fromkeys(n.text for n in ET.fromstring(sitemap).iter() if n.tag.endswith('loc')))
    if not urls or len(urls)>10000 or any(not allowed_source(url) or not urllib.parse.urlsplit(url).path.startswith('/product/') for url in urls):
        raise ValueError('Invalid product sitemap; existing catalogue preserved.')
    products=[];errors=[]
    print('Fetching',len(urls),'public product pages',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        future_map={pool.submit(get_product,(rank,url),use_cache):url for rank,url in enumerate(urls)}
        for count,future in enumerate(concurrent.futures.as_completed(future_map),1):
            try:products.append(future.result())
            except Exception as error:errors.append({'url':future_map[future],'error':str(error)})
            if count%25==0:print('Processed',count,'of',len(urls),flush=True)
    if errors:
        (ROOT/'backend/data/catalogue-refresh-errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
        raise RuntimeError(f'{len(errors)} products failed. Existing catalogue was preserved.')
    products.sort(key=lambda p:p['latest_collection_rank'])
    women=[p for p in products if p['specifications'].get('Gender','Women').lower() in {'women','female'} and p['specifications'].get('Age Group','Adults').lower() not in {'kids','children','girls'}]
    newest=max((season_key(p['season']) for p in women),default=(0,0))
    for p in women:
        if newest!=(0,0) and season_key(p['season'])==newest:p['collections'].insert(0,'new_arrivals')
    women=apply_catalogue_overrides(women)
    counts=Counter(c for p in women for c in p['collections'])
    if any(counts[c]==0 for c in ['new_arrivals','festive','everyday']):raise RuntimeError('A collection is empty; inspect source classifications before replacing catalogue.')
    file=ROOT/'backend/data/products.json'
    backup=ROOT/'backend/data/products-before-refresh.json'
    if file.exists() and not backup.exists():backup.write_bytes(file.read_bytes())
    temp=file.with_suffix('.tmp');temp.write_text(json.dumps(women,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(file)
    report={'source':SOURCE,'refreshed_at':datetime.now(timezone.utc).isoformat(),'sitemap_products':len(urls),'imported_products':len(women),'collection_counts':dict(counts),'new_arrivals_rule':'Newest season published in product specifications','newest_season_key':newest,'season_counts':dict(Counter(p['season'] for p in women)),'stock_note':'Store-specific inventory is not available in this public snapshot.','live_fetch':not use_cache}
    report_file=ROOT/'backend/data/catalogue-refresh.json'
    report_temp=report_file.with_suffix('.tmp')
    report_temp.write_text(json.dumps(report,indent=2),encoding='utf-8');report_temp.replace(report_file)
    print(json.dumps(report,indent=2),flush=True)
    return report

def main(use_cache=None):
    with refresh_lock():
        return import_snapshot(use_cache)

if __name__=='__main__':main()
