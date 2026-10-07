'use strict';
(function () {
  const config = window.ATLAS_CONFIG || {};
  const normalize = value => String(value ?? '').normalize('NFKC').toLowerCase().replace(/[\s　]/g, '');
  const statusKeys = ['active', 'ended', 'temporary'];
  const statusLabels = {active:'取扱中', ended:'取扱終了（廃止・閉鎖）', temporary:'一時閉鎖'};
  const statusKey = record => record.statusKey || (record.officeStatus === 'temporarily-closed' ? 'temporary' : record.historical || record.abolished || record.officeStatus === 'closed' ? 'ended' : 'active');
  const readFilters = search => {
    const params = new URLSearchParams(search);
    const candidate = params.get('region') || 'all';
    return {
      query: params.get('q') || '',
      region: (config.regions || []).includes(candidate) ? candidate : 'all',
      history: params.get('history') === 'true',
      statuses: params.has('status') ? [...new Set(params.get('status').split(',').filter(value => statusKeys.includes(value)))] : params.get('history') === 'true' ? [...statusKeys] : ['active']
    };
  };
  const matches = (record, filters) =>
    (filters.statuses ? filters.statuses.includes(statusKey(record)) : filters.history || !record.historical) &&
    (filters.region === 'all' || record.region === filters.region) &&
    (!filters.query || normalize(record.searchText).includes(normalize(filters.query)));
  const params = filters => {
    const p = new URLSearchParams();
    if (filters.query) p.set('q', filters.query);
    if (filters.region && filters.region !== 'all') p.set('region', filters.region);
    if (filters.statuses) {
      const selected = statusKeys.filter(key => filters.statuses.includes(key));
      if (selected.join(',') !== 'active') p.set('status', selected.join(','));
    } else if (filters.history) p.set('history', 'true');
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
  const checkedStatuses = () => [...document.querySelectorAll('[data-status-filter]:checked')].map(input => input.value);
  const setStatuses = statuses => document.querySelectorAll('[data-status-filter]').forEach(input => {input.checked = statuses.includes(input.value);});
  window.AtlasData = {normalize, readFilters, matches, params, csvText, downloadCsv, statusKeys, statusLabels, statusKey, checkedStatuses, setStatuses};
})();
