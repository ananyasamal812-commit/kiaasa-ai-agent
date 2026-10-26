// Verified store coordinates and addresses are loaded from the official directory snapshot.
let stores = [], visibleStores = [], userLocation = null, map = null, markers = null;
let locationRequest = 0;
const status = document.getElementById('store-status');
const results = document.getElementById('store-results');
const locationButton = document.getElementById('use-location');
const queryInput = document.getElementById('store-query');
function distanceKm(origin, point) {
 const rad = n => n * Math.PI / 180;
 const a = Math.sin(rad(point.lat-origin.lat)/2)**2 + Math.cos(rad(origin.lat))*Math.cos(rad(point.lat))*Math.sin(rad(point.lng-origin.lng)/2)**2;
 return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}
function directions(store) {
 const url = new URL('https://www.google.com/maps/dir/');
 url.searchParams.set('api','1');
 url.searchParams.set('destination',`${store.cname}, ${store.address}`);
 if(userLocation) url.searchParams.set('origin',`${userLocation.lat},${userLocation.lng}`);
 return url.href;
}
function element(tag, className, text) {
 const node=document.createElement(tag); if(className)node.className=className;
 if(text!=null)node.textContent=text; return node;
}
function externalLink(text, href) {
 const link=element('a','',text);link.href=href;link.target='_blank';link.rel='noopener noreferrer';return link;
}
function popup(store) {
 const box=element('div');box.append(element('strong','',store.cname),element('p','',store.address),element('p','',`Hours: ${store.openuntil}`),externalLink('Get Directions',directions(store)));return box;
}
function render() {
 const sorted=[...visibleStores].sort(document.getElementById('store-sort').value==='distance' && userLocation ? (a,b)=>a.distance-b.distance : (a,b)=>a.cname.localeCompare(b.cname));
 document.getElementById('results-title').textContent=`${userLocation && !queryInput.value.trim() ? 'Closest stores' : 'Stores found'} (${sorted.length})`;
 results.replaceChildren();if(markers)markers.clearLayers();
 if(!sorted.length)results.append(element('p','empty','No stores match this search. Try a nearby city, area or another pincode.'));
 const points=[];
 sorted.forEach(store=>{
  const card=element('article','store-card');
  const pin=document.createElementNS('http://www.w3.org/2000/svg','svg');pin.setAttribute('viewBox','0 0 32 44');pin.setAttribute('class','store-pin');pin.setAttribute('aria-hidden','true');
  pin.innerHTML='<path d="M16 1C7 1 1 7 1 16c0 11 15 27 15 27s15-16 15-27C31 7 25 1 16 1Zm0 9a6 6 0 1 1 0 12 6 6 0 0 1 0-12Z"/>';
  const body=element('div');const title=element('button','store-title',store.cname);title.type='button';body.append(title,element('p','locality',store.locality),element('p','',store.address));
  if(userLocation)body.append(element('p','distance',`${store.distance.toFixed(1)} km away · straight-line distance`));
  body.append(element('p','',`Hours: ${store.openuntil}`),externalLink('Get Directions',directions(store)));
  if(store.phone){const phone=element('a','',store.phone.trim());phone.href='tel:'+store.phone.replace(/[^+\d]/g,'');body.append(phone);}
  card.append(pin,body);results.append(card);
  let marker=null;
  if(map){const point=[store.latlng.lat,store.latlng.lng];points.push(point);marker=L.marker(point,{icon:L.divIcon({className:'',html:'<div class="kiaasa-marker"></div>',iconSize:[30,30],iconAnchor:[15,30]})}).addTo(markers).bindPopup(popup(store));marker.on('click',()=>select());}
  function select(){results.querySelectorAll('.selected').forEach(n=>n.classList.remove('selected'));card.classList.add('selected');if(marker){map.setView(marker.getLatLng(),14);marker.openPopup();} }
  title.addEventListener('click',()=>{select();if(map && innerWidth<701)document.querySelector('.map-panel').scrollIntoView({behavior:'smooth'});});
 });
 if(map && points.length)map.fitBounds(points,{padding:[35,35],maxZoom:13});
}
function search() {
 // Manual search supersedes any outstanding location request.
 locationRequest++;locationButton.disabled=false;
 const query=queryInput.value.trim().toLowerCase();
 visibleStores=stores.filter(s=>`${s.cname} ${s.address} ${s.locality}`.toLowerCase().includes(query));
 if(!query && userLocation) return showNearest();
 status.textContent=query ? `Matching stores for “${queryInput.value.trim()}”.` : 'Search your city or use your location to find nearby stores.';
 render();
}
function showNearest() {
 stores.forEach(s=>s.distance=distanceKm(userLocation,s.latlng));
 const nearby=stores.filter(s=>s.distance<=50);
 visibleStores=nearby.length ? nearby : [...stores].sort((a,b)=>a.distance-b.distance).slice(0,10);
 status.textContent=nearby.length ? 'Stores within 50 km of your location. Distances are approximate.' : 'No listed stores within 50 km. Showing the 10 closest stores; some may be far away.';
 render();
}
function useLocation() {
 if(!stores.length)return;
 if(!navigator.geolocation || !window.isSecureContext){status.textContent='Location access requires HTTPS or localhost. Please search by city, area or pincode.';return;}
 const request=++locationRequest;locationButton.disabled=true;status.textContent='Allow location access in your browser to find nearby stores…';
 navigator.geolocation.getCurrentPosition(position=>{
  if(request!==locationRequest)return;locationButton.disabled=false;
  userLocation={lat:position.coords.latitude,lng:position.coords.longitude};queryInput.value='';showNearest();
 },error=>{
  if(request!==locationRequest)return;locationButton.disabled=false;
  status.textContent=error.code===1 ? 'Location access was denied. Enter your city, area or pincode instead.' : 'Could not get your location. Please try again or search by city or pincode.';
 },{enableHighAccuracy:true,timeout:12000,maximumAge:60000});
}
document.getElementById('store-search').addEventListener('submit',event=>{event.preventDefault();search();});
document.getElementById('store-sort').addEventListener('change',render);
locationButton.addEventListener('click',useLocation);
async function init() {
 try {
  const response=await fetch('stores.json');if(!response.ok)throw new Error('Store data unavailable');
  const data=await response.json();stores=data.stores.filter(s=>Number.isFinite(s.latlng?.lat)&&Number.isFinite(s.latlng?.lng));visibleStores=stores;
  document.getElementById('data-date').textContent=`Directory snapshot: ${data.updated}.`;
  if(window.L){map=L.map('store-map').setView([22.8,79],5);markers=L.layerGroup().addTo(map);const tiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);tiles.on('tileerror',()=>document.getElementById('map-fallback').hidden=false);}
  else document.getElementById('map-fallback').hidden=false;
  search();useLocation();
 } catch(error){status.textContent='Could not load store locations. Refresh to try again.';results.append(externalLink('Open Kiaasa’s official store directory','https://stores.kiaasaretail.com/'));locationButton.disabled=true;}
}
init();
