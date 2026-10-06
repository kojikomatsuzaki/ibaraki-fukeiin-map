'use strict';
(function () {
  const search = document.getElementById('list-search');
  const region = document.getElementById('list-region');
  const history = document.getElementById('list-history');
  const rows = [...document.querySelectorAll('#list-body tr')];
  const count = document.getElementById('list-count');
  const filters = AtlasData.readFilters(location.search);
  search.value = filters.query;
  region.value = filters.region;
  history.checked = filters.history;
  function draw() {
    const current = {query:search.value, region:region.value, history:history.checked};
    let visible = 0;
    for (const row of rows) {
      row.hidden = !AtlasData.matches({
        searchText:row.dataset.search,
        region:row.dataset.region,
        historical:row.dataset.historical === 'true'
      }, current);
      if (!row.hidden) visible++;
    }
    count.textContent = visible + '件を表示';
    const summary = document.getElementById('filter-summary');
    if (summary) summary.textContent = [
      current.query ? '検索：' + current.query : '',
      current.region === 'all' ? '全地域' : current.region,
      current.history ? '廃止・閉鎖・一時閉鎖を含む' : '廃止・閉鎖・一時閉鎖を除く',
      visible + '件'
    ].filter(Boolean).join(' / ');
    const printLink = document.getElementById('list-print');
    if (printLink) printLink.href = '../print/' + (AtlasData.params(current) ? '?' + AtlasData.params(current) : '');
  }
  search.addEventListener('input', draw);
  region.addEventListener('change', draw);
  history.addEventListener('change', draw);
  document.getElementById('print-now')?.addEventListener('click', () => window.print());
  draw();
})();
