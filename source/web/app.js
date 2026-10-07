'use strict';
const $=id=>document.getElementById(id);
const state={records:[],region:'all',query:'',statuses:['active'],markers:new Map(),filtered:[],applied:null,displayed:[]};
const norm=AtlasData.normalize;
const siteConfig=window.ATLAS_CONFIG||{};
const bounds=L.latLngBounds(siteConfig.bounds||[[35.735,139.68],[36.955,140.86]]);
const map=L.map('map',{zoomControl:false,minZoom:7,maxZoom:18,zoomSnap:.25,scrollWheelZoom:true});
L.control.zoom({position:'bottomright',zoomInTitle:'地図を拡大',zoomOutTitle:'地図を縮小'}).addTo(map);
L.control.scale({position:'bottomleft',imperial:false,maxWidth:100}).addTo(map);
const tiles=L.tileLayer(siteConfig.tileUrl||'https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png',{attribution:'<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">'+(siteConfig.tileAttribution||'地理院タイル')+'</a>',maxNativeZoom:18,maxZoom:18}).addTo(map);
let selection;
let tileErrors=0;tiles.on('tileerror',()=>{if(++tileErrors>=5){$('map-error').textContent='背景地図を読み込めません。風景印と県境はそのまま操作できます。';$('map-error').hidden=false;}});tiles.on('tileload',()=>{tileErrors=0;$('map-error').hidden=true;});
const fit=()=>map.fitBounds(bounds,{paddingTopLeft:[22,58],paddingBottomRight:[22,65],animate:false});fit();
fetch(siteConfig.boundaryAsset||'assets/ibaraki.geojson').then(r=>r.json()).then(data=>{L.geoJSON(data,{interactive:false,style:{color:'#407489',weight:.7,opacity:.7,fillColor:'#76aabe',fillOpacity:.13}}).addTo(map)}).catch(()=>{});
const group=L.layerGroup().addTo(map);
function external(a,r){a.href=r.detailUrl;a.target='_blank';a.rel='noopener noreferrer';}
function stampSize(){const z=map.getZoom();return z<9?32:z<10?38:z<11?46:z<13?57:72;}
function statusLabel(r){if(r.displayStatus!==undefined)return r.displayStatus;if(r.officeStatus==='temporarily-closed')return [r.officeStatusDate,'一時閉鎖'].filter(Boolean).join(' ');if(r.abolished)return [r.endDate,'風景印廃止'].filter(Boolean).join(' ');if(r.officeStatus==='closed')return [r.officeStatusDate,'郵便局閉鎖'].filter(Boolean).join(' ');return '';}
function makeIcon(r){const wrap=document.createElement('div');const a=document.createElement('a');a.className='stamp-link';external(a,r);const note=[statusLabel(r),r.coordinatesApproximate?'概算位置':''].filter(Boolean).join('・');a.setAttribute('aria-label',r.name+'の風景印を日本郵便で見る（新しいタブ）'+(note?'・'+note:''));const img=document.createElement('img');img.src=r.image;img.alt=r.name+'の風景印';img.draggable=false;a.append(img);wrap.append(a);const n=stampSize();return L.divIcon({className:'stamp-marker'+(r.historical?' historical':''),html:wrap.innerHTML,iconSize:[n,n],iconAnchor:[n/2,n/2]});}
function bindMarkerLink(marker,r){const a=marker.getElement()?.querySelector('a');if(a){L.DomEvent.disableClickPropagation(a);a.addEventListener('focus',()=>marker.setZIndexOffset(4000));a.addEventListener('blur',()=>marker.setZIndexOffset(r.historical?-100:0));}}
function addMarker(r){if(!Number.isFinite(r.lat)||!Number.isFinite(r.lng))return;const marker=L.marker([r.lat,r.lng],{icon:makeIcon(r),keyboard:false,riseOnHover:true,riseOffset:3000,zIndexOffset:r.historical?-100:0});const tooltip=document.createElement('span');tooltip.textContent=[r.name,statusLabel(r),r.coordinatesApproximate?'概算位置':''].filter(Boolean).join(' / ');marker.bindTooltip(tooltip,{direction:'top',offset:[0,-20]});marker.on('add',()=>bindMarkerLink(marker,r));marker.addTo(group);state.markers.set(r.id,marker);}
function card(r){const el=document.createElement('article');el.className='office';el.dataset.id=r.id;const a=document.createElement('a');a.className='office-image';external(a,r);a.setAttribute('aria-label',r.name+'の風景印紹介（新しいタブ）');const img=document.createElement('img');img.src=r.image;img.alt=r.name+'の風景印';img.loading='lazy';img.width=60;img.height=60;a.append(img);const body=document.createElement('div');body.className='office-body';const title=document.createElement('a');title.className='office-name';title.textContent=r.name;external(title,r);const meta=document.createElement('p');meta.className='office-meta';meta.textContent=[r.region,r.city].filter(Boolean).join(' / ');body.append(title,meta);const status=statusLabel(r);if(status){const label=document.createElement('div');label.className='abolished';label.textContent=status;body.append(label);}if(r.coordinatesApproximate||(['62','4137'].includes(r.id))){const note=document.createElement('p');note.className='coordinate-note';note.textContent=r.coordinatesApproximate?'概算位置（旧所在地から補完）':'現在の所在地に表示';note.title=r.coordinateNote;body.append(note);}const locate=document.createElement('button');locate.className='locate';locate.innerHTML='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 14s4.5-4.5 4.5-8A4.5 4.5 0 0 0 3.5 6C3.5 9.5 8 14 8 14Z"/><circle cx="8" cy="6" r="1.5"/></svg>地図で見る';locate.setAttribute('aria-label',r.name+'の位置を地図で見る');locate.addEventListener('click',()=>{document.querySelectorAll('.office.is-active').forEach(e=>e.classList.remove('is-active'));el.classList.add('is-active');if(Number.isFinite(r.lat)){if(!state.markers.has(r.id)){state.applied=new Set([r.officeId]);drawMap();} $('office-picker').close();const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;map.setView([r.lat,r.lng],14,{animate:!reduce});state.markers.get(r.id)?.openTooltip();if(innerWidth<641)$('map').scrollIntoView({behavior:reduce?'auto':'smooth',block:'center'});}});body.append(locate);const apple=document.createElement('a');apple.className='apple-link';apple.href=AtlasExport.appleUrl(r);apple.textContent='Apple Mapsで開く';apple.target='_blank';apple.rel='noopener noreferrer';apple.setAttribute('aria-label',r.name+'をApple Mapsで開く（新しいタブ）');body.append(apple);const label=document.createElement('label');label.className='office-select';const check=document.createElement('input');check.type='checkbox';check.dataset.selectOffice=r.officeId;check.checked=selection?.selected.has(r.officeId)||false;label.append(check,document.createTextNode('この局を選択'));body.append(label);el.append(a,body);return el;}
// List filters do not discard chosen offices. Applying takes a snapshot of the selection.
const regionOpen = new Map();
function representativeRecords(records) {
  const priority={temporary:0,active:1,ended:2};
  const sorted=[...records].sort((a,b)=>priority[AtlasData.statusKey(a)]-priority[AtlasData.statusKey(b)]||Number(b.id)-Number(a.id));
  const offices=new Map();for(const record of sorted)if(!offices.has(record.officeId))offices.set(record.officeId,record);
  return [...offices.values()];
}
function drawMap(move=false) {
  const list=state.applied ? representativeRecords(state.records.filter(r=>state.applied.has(r.officeId))) : state.filtered;
  state.displayed=list;group.clearLayers();state.markers.clear();list.forEach(addMarker);
  const count=new Set(list.map(r=>r.officeId)).size;
  $('display-summary').textContent=(state.applied?'選択した':'検索条件に合う')+count+'局を表示中';
  $('show-all').hidden=!state.applied && !state.query && state.region==='all' && state.statuses.join(',')==='active';
  $('map-count').textContent=list.length+'点の風景印';
  $('map-region').textContent=state.applied?'選択した郵便局':state.region==='all'?'茨城県全域':state.region+'エリア';
  if(move && list.length){const pts=list.filter(r=>Number.isFinite(r.lat)&&Number.isFinite(r.lng)).map(r=>[r.lat,r.lng]);if(pts.length)map.fitBounds(pts,{padding:[65,55],maxZoom:13,animate:false});}
}
function selectionChanged(selected) {
  const button=$('apply-selection');button.disabled=!selected.size;button.textContent='選択した'+selected.size+'局を地図に表示';
  for(const details of $('results').querySelectorAll('[data-picker-region]')){
    const ids=new Set(state.filtered.filter(r=>r.region===details.dataset.pickerRegion).map(r=>r.officeId));
    const chosen=new Set(state.records.filter(r=>r.region===details.dataset.pickerRegion&&selected.has(r.officeId)).map(r=>r.officeId));
    details.querySelector('.region-count').textContent=ids.size+'局'+(chosen.size?' / 選択'+chosen.size+'局':'');
  }
}
function render(move=false) {
  state.filtered=state.records.filter(r=>AtlasData.matches(r,state));
  const list=representativeRecords(state.filtered);
  $('count').textContent=list.length;
  $('reset').hidden=!state.query&&state.region==='all'&&state.statuses.join(',')==='active';
  const out=document.createDocumentFragment();
  for(const region of siteConfig.regions){
    const records=list.filter(r=>r.region===region);
    const details=document.createElement('details');details.className='region-accordion';details.dataset.pickerRegion=region;
    details.open=Boolean(regionOpen.get(region)||(norm(state.query)&&records.length)||(state.region===region));
    const summary=document.createElement('summary');const label=document.createElement('strong');label.textContent=region;
    const count=document.createElement('span');count.className='region-count';summary.append(label,count);details.append(summary);
    details.addEventListener('toggle',()=>regionOpen.set(region,details.open));
    if(records.length)records.forEach(r=>details.append(card(r)));else{const empty=document.createElement('p');empty.className='region-empty';empty.textContent='条件に合う郵便局はありません';details.append(empty);}
    out.append(details);
  }
  $('results').replaceChildren(out);
  const printLink=$('print-link');printLink.href='print/'+(AtlasData.params(state)?'?'+AtlasData.params(state):'');
  selection?.update();drawMap(move);
}
$('search').addEventListener('input',e=>{state.query=e.target.value;render(false);});
document.querySelectorAll('[data-status-filter]').forEach(input=>input.addEventListener('change',()=>{state.statuses=AtlasData.checkedStatuses();render(false);}));
function reset(){state.query='';state.region='all';state.statuses=['active'];state.applied=null;$('search').value='';AtlasData.setStatuses(state.statuses);render();fit();}
$('reset').addEventListener('click',reset);$('show-all').addEventListener('click',reset);$('fit').addEventListener('click',fit);
$('picker-open').addEventListener('click',()=>$('office-picker').showModal());
$('picker-close').addEventListener('click',()=>$('office-picker').close());
$('apply-selection').addEventListener('click',()=>{if(!selection?.selected.size)return;state.applied=new Set(selection.selected);drawMap(true);$('office-picker').close();});
if($('export-csv'))$('export-csv').addEventListener('click',()=>window.AtlasData?.downloadCsv(state.filtered));
map.on('zoomend',()=>{state.markers.forEach((m,id)=>{const r=state.records.find(r=>r.id===id);if(r){m.setIcon(makeIcon(r));bindMarkerLink(m,r);}});});
$('about-open').addEventListener('click',()=>$('about').showModal());$('about-close').addEventListener('click',()=>$('about').close());$('about').addEventListener('click',e=>{if(e.target===$('about')){const b=$('about').getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)$('about').close();}});
fetch('data.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('Data unavailable');return r.json()}).then(data=>{state.records=data.records;$('coverage').textContent=data.partial?'公式一覧を順次照合中です。':`公式一覧の全${data.sourceCount}件・${new Set(data.records.map(r=>r.officeId)).size}局を収録。旧図案や同じ郵便局の複数掲載も含みます。`;if(data.locationNote)$('location-note').textContent=data.locationNote;Object.assign(state,AtlasData.readFilters(location.search));$('search').value=state.query;AtlasData.setStatuses(state.statuses);selection=AtlasExport.create(state.records,()=>state.filtered,selectionChanged);if($('export-csv'))$('export-csv').disabled=false;render(Boolean(state.query||state.region!=='all'));}).catch(()=>{$('results').innerHTML='<div class="empty"><strong>風景印を読み込めませんでした</strong>ページを再読み込みしてください。</div>';$('map-count').textContent='データ読み込みエラー';});
window.stampAtlas={search(query='',region='all',includeAbolished=false){if(typeof query!=='string'||!['all',...siteConfig.regions].includes(region)||typeof includeAbolished!=='boolean')throw new Error('検索条件が正しくありません');state.applied=null;state.query=query;state.region=region;state.statuses=includeAbolished?[...AtlasData.statusKeys]:['active'];$('search').value=query;AtlasData.setStatuses(state.statuses);render(true);return state.filtered.map(r=>({id:r.id,name:r.name,city:r.city,detailUrl:r.detailUrl}));},getState(){return {region:state.region,query:state.query,statuses:[...state.statuses],includeAbolished:state.statuses.includes('ended'),count:state.displayed.length,selectedOffices:selection?.selected.size||0};}};
if(document.modelContext?.registerTool){try{Promise.resolve(document.modelContext.registerTool({name:'search_ibaraki_stamps',title:'茨城の風景印を検索',description:'郵便局名または市町村名と地域で地図と一覧を絞り込み、公式紹介URLを返します。includeAbolishedをtrueにすると廃止・一時閉鎖も含みます。',inputSchema:{type:'object',properties:{query:{type:'string'},region:{type:'string',enum:['all',...siteConfig.regions]},includeAbolished:{type:'boolean'}},additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:true},execute(input){if(!input||typeof input!=='object'||Object.keys(input).some(k=>!['query','region','includeAbolished'].includes(k)))throw new Error('検索条件が正しくありません');return window.stampAtlas.search(input.query??'',input.region??'all',input.includeAbolished??false);}})).catch(()=>{});}catch{}}
