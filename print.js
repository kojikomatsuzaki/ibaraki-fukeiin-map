'use strict';
(function () {
  const search = document.getElementById('list-search');
  const region = document.getElementById('list-region');
  const rows = [...document.querySelectorAll('#list-body tr')];
  const count = document.getElementById('list-count');
  const filters = AtlasData.readFilters(location.search);
  search.value = filters.query;
  region.value = filters.region;
  AtlasData.setStatuses(filters.statuses);
  let visibleRecords = [];
  let selection;
  let records = [];
  function draw() {
    const current = {query:search.value, region:region.value, statuses:AtlasData.checkedStatuses()};
    let visible = 0;
    for (const row of rows) {
      row.hidden = !AtlasData.matches({
        searchText:row.dataset.search,
        region:row.dataset.region,
        historical:row.dataset.historical === 'true',
        statusKey:row.dataset.status
      }, current);
      if (!row.hidden) visible++;
    }
    count.textContent = visible + '件を表示';
    const ids = new Set(rows.filter(row => !row.hidden).map(row => row.dataset.id));
    visibleRecords = records.filter(record => ids.has(record.id));
    selection?.update();
    const summary = document.getElementById('filter-summary');
    if (summary) summary.textContent = [
      current.query ? '検索：' + current.query : '',
      current.region === 'all' ? '全地域' : current.region,
      current.statuses.map(key => AtlasData.statusLabels[key]).join('・') || '取扱状況の選択なし',
      visible + '件'
    ].filter(Boolean).join(' / ');
    const printLink = document.getElementById('list-print');
    if (printLink) printLink.href = '../print/' + (AtlasData.params(current) ? '?' + AtlasData.params(current) : '');
  }
  search.addEventListener('input', draw);
  region.addEventListener('change', draw);
  document.querySelectorAll('[data-status-filter]').forEach(input => input.addEventListener('change', draw));
  document.getElementById('print-now')?.addEventListener('click', () => window.print());
  draw();
  if (document.getElementById('selected-count')) {
    fetch('../data.json', {cache:'no-store'}).then(response => {
      if (!response.ok) throw new Error('Data unavailable');
      return response.json();
    }).then(data => {
      records = data.records;
      selection = AtlasExport.create(records, () => visibleRecords);
      draw();
    }).catch(() => {document.getElementById('selected-count').textContent = '書き出しデータを読み込めません。再読み込みしてください。';});
  }
})();
