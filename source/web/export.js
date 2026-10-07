'use strict';
(function () {
  const title = window.ATLAS_CONFIG.title;
  const fields = [['name','郵便局名'],['address','住所'],['lat','緯度'],['lng','経度'],['status','取扱状況'],['detailUrl','公式紹介URL'],['verifiedAt','データ確認日'],['coordinateNote','位置注記']];
  const xml = value => String(value ?? '').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c])).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
  function offices(records, selected) {
    const grouped = new Map();
    for (const record of records) {
      if (selected && !selected.has(record.officeId)) continue;
      if (!grouped.has(record.officeId)) grouped.set(record.officeId, []);
      grouped.get(record.officeId).push(record);
    }
    return [...grouped.values()].map(group => {
      const priority = {temporary:0, active:1, ended:2};
      const sorted = [...group].sort((a,b) => priority[AtlasData.statusKey(a)] - priority[AtlasData.statusKey(b)] || Number(b.id) - Number(a.id));
      const record = sorted[0];
      const urls = [...new Set(sorted.map(r => r.detailUrl))];
      return {officeId:record.officeId, name:record.name, address:record.displayAddress, lat:record.lat, lng:record.lng,
        status:record.displayStatus || AtlasData.statusLabels[AtlasData.statusKey(record)],
        detailUrl:urls.join('\n'), urls, verifiedAt:record.verifiedAt,
        coordinateNote:[record.addressLabel, record.coordinatesApproximate ? '概算位置' : '', record.coordinateNote].filter(Boolean).join('：')};
    });
  }
  const description = office => fields.map(([key,label]) => label + '：' + office[key]).join('\n');
  const header = '<?xml version="1.0" encoding="UTF-8"?>\n';
  const kmlText = points => header + '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>' + xml(title) + '</name>\n' + points.map(p =>
    '<Placemark><name>' + xml(p.name) + '</name><description>' + xml(description(p)) + '</description><ExtendedData>' +
    fields.map(([key,label]) => '<Data name="' + key + '"><displayName>' + xml(label) + '</displayName><value>' + xml(p[key]) + '</value></Data>').join('') +
    '</ExtendedData><Point><coordinates>' + p.lng + ',' + p.lat + ',0</coordinates></Point></Placemark>'
  ).join('\n') + '\n</Document></kml>\n';
  const gpxText = points => header + '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:atlas="https://kojikomatsuzaki.github.io/ibaraki-fukeiin-map/ns/1" version="1.1" creator="Ibaraki Scenic Postmarks Map"><metadata><name>' + xml(title) + '</name></metadata>\n' + points.map(p =>
    '<wpt lat="' + p.lat + '" lon="' + p.lng + '"><name>' + xml(p.name) + '</name><desc>' + xml(description(p)) + '</desc>' +
    p.urls.map(url => '<link href="' + xml(url) + '"><text>日本郵便の風景印紹介</text><type>text/html</type></link>').join('') +
    '<extensions>' + fields.map(([key]) => '<atlas:' + key + '>' + xml(p[key]) + '</atlas:' + key + '>').join('') + '</extensions></wpt>'
  ).join('\n') + '\n</gpx>\n';
  const csvCell = value => {
    let text = String(value ?? '');
    if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
    return /[",\r\n]/.test(text) ? '"' + text.replaceAll('"','""') + '"' : text;
  };
  const csvText = points => '\ufeff' + [fields.map(([,label]) => csvCell(label)).join(','), ...points.map(p => fields.map(([key]) => csvCell(p[key])).join(','))].join('\r\n') + '\r\n';
  const appleUrl = record => 'https://maps.apple.com/?' + new URLSearchParams({ll:record.lat + ',' + record.lng, q:record.name}).toString();
  function create(records, visibleRecords) {
    const selected = new Set();
    const count = document.getElementById('selected-count');
    const update = () => {
      const visible = new Set(visibleRecords().map(r => r.officeId));
      const hidden = [...selected].filter(id => !visible.has(id)).length;
      count.textContent = selected.size + '局を選択' + (hidden ? '（絞り込み外 ' + hidden + '局を含む）' : '');
      document.querySelectorAll('[data-select-office]').forEach(input => {input.checked = selected.has(input.dataset.selectOffice);});
      document.querySelectorAll('[data-export-format], #clear-selection').forEach(button => {button.disabled = !selected.size;});
      document.getElementById('select-visible').disabled = !visible.size;
    };
    document.addEventListener('change', event => {
      const input = event.target.closest('[data-select-office]');
      if (!input) return;
      if (input.checked) selected.add(input.dataset.selectOffice); else selected.delete(input.dataset.selectOffice);
      update();
    });
    document.getElementById('select-visible').addEventListener('click', () => {visibleRecords().forEach(r => selected.add(r.officeId));update();});
    document.getElementById('clear-selection').addEventListener('click', () => {selected.clear();update();});
    document.querySelectorAll('[data-export-format]').forEach(button => button.addEventListener('click', () => {
      const format = button.dataset.exportFormat;
      const points = offices(records, selected);
      if (!points.length) return;
      const content = {kml:kmlText, gpx:gpxText, csv:csvText}[format](points);
      const type = {kml:'application/vnd.google-earth.kml+xml',gpx:'application/gpx+xml',csv:'text/csv'}[format];
      const url = URL.createObjectURL(new Blob([content], {type:type + ';charset=utf-8'}));
      const link = document.createElement('a');
      link.href = url;link.download = 'ibaraki-fukeiin-selected.' + format;
      document.body.append(link);link.click();link.remove();setTimeout(() => URL.revokeObjectURL(url), 1000);
    }));
    update();
    return {selected, update};
  }
  window.AtlasExport = {offices, kmlText, gpxText, csvText, appleUrl, create};
})();
