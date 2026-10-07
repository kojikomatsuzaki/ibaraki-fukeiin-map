'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const context = vm.createContext({window:{}, URLSearchParams});
for (const file of ['config.js','catalog-view.js','export.js']) {
  vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'), context);
  if (file === 'catalog-view.js') context.AtlasData = context.window.AtlasData;
}
const filters = context.window.AtlasData;
const api = context.window.AtlasExport;
const records = JSON.parse(fs.readFileSync(path.join(root,'data.json'),'utf8')).records;

test('three independent status filters partition every stamp and survive URL round trips', () => {
  const expected = {active:210,ended:13,temporary:1};
  for (const key of Object.keys(expected)) {
    const current = {query:'',region:'all',statuses:[key]};
    assert.equal(records.filter(r => filters.matches(r,current)).length,expected[key]);
    assert.equal(filters.readFilters('?' + filters.params(current)).statuses.join(','),key);
  }
  assert.equal(filters.readFilters('').statuses.join(','),'active');
  assert.equal(records.filter(r => filters.matches(r,filters.readFilters('?history=true'))).length,224);
  assert.equal(records.filter(r => filters.matches(r,filters.readFilters('?status='))).length,0);
  assert.equal(filters.readFilters('?status=temporary,temporary,unknown').statuses.join(','),'temporary');
});

test('selected offices deduplicate designs, prefer current location and retain every official URL', () => {
  assert.equal(api.offices(records).length,219);
  const selected = new Set([records.find(r => r.id === '4112').officeId]);
  const points = api.offices(records,selected);
  assert.equal(points.length,1);
  assert.equal(points[0].name,'大洗祝町郵便局');
  for (const p of api.offices(records)) {
    const group = records.filter(r => r.officeId === p.officeId);
    assert.deepEqual(new Set(p.urls),new Set(group.map(r => r.detailUrl)));
    if (group.some(r => !r.historical)) assert.equal(p.status,'取扱中');
  }
  assert.equal(api.offices(records,new Set()).length,0);
  const historic = api.offices(records,new Set([records.find(r => r.id === '12523').officeId]))[0];
  assert.ok(historic.coordinateNote.includes('旧所在地'));
  assert.ok(historic.status.includes('廃止'));
});

test('KML, GPX and CSV parse independently and preserve point metadata and coordinate order', () => {
  const record = {...records.find(r => r.id === '4112'),name:'大洗 & <祝町> "郵便局"',displayAddress:'住所,一行目\n二行目'};
  const points = api.offices([record]);
  const payload = {point:points[0],kml:api.kmlText(points),gpx:api.gpxText(points),csv:api.csvText(points)};
  execFileSync('python3',['-c',String.raw`
import sys,json,csv,io,xml.etree.ElementTree as E
p=json.load(sys.stdin); point=p['point']
k=E.fromstring(p['kml']); ns={'k':'http://www.opengis.net/kml/2.2'}
marks=k.findall('.//k:Placemark',ns); assert len(marks)==1
assert marks[0].find('k:name',ns).text==point['name']
coords=marks[0].find('k:Point/k:coordinates',ns).text.split(',')
assert list(map(float,coords[:2]))==[point['lng'],point['lat']]
data={d.attrib['name']:d.find('k:value',ns).text for d in marks[0].findall('k:ExtendedData/k:Data',ns)}
for key in ['address','status','detailUrl','verifiedAt','coordinateNote']: assert data[key]==point[key]
g=E.fromstring(p['gpx']); ns={'g':'http://www.topografix.com/GPX/1/1','a':'https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/ns/1'}
waypoints=g.findall('g:wpt',ns); assert len(waypoints)==1
w=waypoints[0]; assert float(w.attrib['lat'])==point['lat'] and float(w.attrib['lon'])==point['lng']
assert w.find('g:name',ns).text==point['name']
assert w.find('g:link',ns).attrib['href']==point['urls'][0]
for key in ['address','status','detailUrl','verifiedAt','coordinateNote']: assert w.find('g:extensions/a:'+key,ns).text==point[key]
assert not g.findall('g:rte',ns) and not g.findall('g:trk',ns)
rows=list(csv.reader(io.StringIO(p['csv'].lstrip('\ufeff')))); assert len(rows)==2
assert rows[1][:2]==[point['name'],point['address']]
assert rows[1][4:7]==[point['status'],point['detailUrl'],point['verifiedAt']]
`],{input:JSON.stringify(payload)});
});

test('Apple Maps link encodes the postal office name and WGS84 location', () => {
  const record = records.find(r => r.id === '4112');
  const url = new URL(api.appleUrl(record));
  assert.equal(url.origin,'https://maps.apple.com');
  assert.equal(url.searchParams.get('ll'),record.lat+','+record.lng);
  assert.equal(url.searchParams.get('q'),record.name);
});
