'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'source/web/catalog-view.js'), 'utf8');
function load(config) {
  const context = vm.createContext({window: {}, URLSearchParams});
  if (config) context.window.ATLAS_CONFIG = config;
  else vm.runInContext(fs.readFileSync(path.join(root, 'config.js'), 'utf8'), context);
  vm.runInContext(source, context, {filename: 'source/web/catalog-view.js'});
  return context.window.AtlasData;
}
// Parse CSV independently, retaining commas, quotes and embedded CR/LF in cells.
function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', quoted = false;
  text = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && c === ',') { row.push(cell); cell = ''; }
    else if (!quoted && (c === '\r' || c === '\n')) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); rows.push(row); row = []; cell = '';
    } else cell += c;
  }
  assert.equal(quoted, false, 'CSV must close every quoted cell');
  if (row.length || cell) { row.push(cell); rows.push(row); }
  return rows;
}

test('Japanese and reserved characters survive filter URL round trip', () => {
  const api = load();
  const filters = {query: '若栗 & 郵便局 + #? /「印」', region: '県南', history: true};
  const actual = api.readFilters('?' + api.params(filters));
  assert.equal(actual.query, filters.query);
  assert.equal(actual.region, filters.region);
  assert.equal(actual.history, true);
  assert.equal(api.readFilters('?history=false').history, false);
  assert.equal(api.readFilters('?history=1').history, false);
  assert.equal(api.readFilters('?region=unknown').region, 'all');
  assert.equal(api.params({query: '', region: 'all', history: false}), '');
  assert.equal(api.readFilters('').history, false);
});

test('CSV preserves Japanese, quotes and multiline cells and protects formulas', () => {
  const api = load({csvFields: [['value', '日本語の見出し']]});
  const values = ['若栗郵便局', '印, "筑波"', '一行目\r\n二行目',
    '=1+1', '+1', '-1', '@SUM(A1)', '\t式', '\r式', null, false];
  const csv = api.csvText(values.map(value => ({value})));
  assert.ok(csv.startsWith('\uFEFF日本語の見出し\r\n'));
  assert.ok(csv.includes('"印, ""筑波"""\r\n'));
  assert.ok(csv.includes('"一行目\r\n二行目"\r\n'));
  assert.ok(csv.endsWith('\r\n'));
  assert.deepEqual(parseCsv(csv), [['日本語の見出し'], ['若栗郵便局'],
    ['印, "筑波"'], ['一行目\r\n二行目'], ["'=1+1"], ["'+1"], ["'-1"],
    ["'@SUM(A1)"], ["'\t式"], ["'\r式"], [''], ['false']]);
});

test('browser CSV content exactly matches the generated full export', () => {
  const api = load();
  const records = JSON.parse(fs.readFileSync(path.join(root, 'data.json'), 'utf8')).records;
  assert.equal(api.csvText(records), fs.readFileSync(path.join(root, 'exports/stamps.csv'), 'utf8'));
});

test('Wakaguri history search exports exactly its one generated CSV row', () => {
  const api = load();
  const records = JSON.parse(fs.readFileSync(path.join(root, 'data.json'), 'utf8')).records;
  const filters = api.readFilters('?' + api.params({query: '若栗', region: 'all', history: true}));
  const selected = records.filter(record => api.matches(record, filters));
  assert.equal(selected.length, 1);
  assert.equal(selected[0].name, '若栗郵便局');
  assert.equal(selected[0].id, '12523');
  assert.equal(records.filter(record => api.matches(record, {...filters, statuses: ['active']})).length, 0);
  const exported = parseCsv(fs.readFileSync(path.join(root, 'exports/stamps.csv'), 'utf8'));
  const idColumn = exported[0].indexOf('風景印ID');
  assert.notEqual(idColumn, -1);
  const expectedRows = exported.slice(1).filter(row => row[idColumn] === '12523');
  assert.equal(expectedRows.length, 1);
  assert.deepEqual(parseCsv(api.csvText(selected)), [exported[0], ...expectedRows]);
});
