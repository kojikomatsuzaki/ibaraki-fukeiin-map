'use strict';
(function () {
  const config = window.ATLAS_CONFIG || {};
  const normalize = value => String(value ?? '').normalize('NFKC').toLowerCase().replace(/[\s　]/g, '');
  const readFilters = search => {
    const params = new URLSearchParams(search);
    const candidate = params.get('region') || 'all';
    return {
      query: params.get('q') || '',
      region: (config.regions || []).includes(candidate) ? candidate : 'all',
      history: params.get('history') === 'true'
    };
  };
  const matches = (record, filters) =>
    (filters.history || !record.historical) &&
    (filters.region === 'all' || record.region === filters.region) &&
    (!filters.query || normalize(record.searchText).includes(normalize(filters.query)));
  const params = filters => {
    const p = new URLSearchParams();
    if (filters.query) p.set('q', filters.query);
    if (filters.region && filters.region !== 'all') p.set('region', filters.region);
    if (filters.history) p.set('history', 'true');
    return p.toString();
  };
  const fields = config.csvFields || [];
  const text = value => value === null || value === undefined ? '' : String(value);
  const csvCell = value => {
    let result = text(value);
    if (/^[=+\-@\t\r]/.test(result)) result = "'" + result;
    return /[",\r\n]/.test(result) ? '"' + result.replaceAll('"', '""') + '"' : result;
  };
  const csvText = records => '\ufeff' + [
    fields.map(field => csvCell(field[1])).join(','),
    ...records.map(record => fields.map(field => csvCell(record[field[0]])).join(','))
  ].join('\r\n') + '\r\n';
  const downloadCsv = records => {
    const url = URL.createObjectURL(new Blob([csvText(records)], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ibaraki-fukeiin.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  window.AtlasData = {normalize, readFilters, matches, params, csvText, downloadCsv};
})();
