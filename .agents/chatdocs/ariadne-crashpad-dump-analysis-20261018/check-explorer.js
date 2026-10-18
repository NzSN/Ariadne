const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const directory = process.argv[2];
const data = JSON.parse(fs.readFileSync(path.join(directory, 'graph-data.json'), 'utf8'));

// This exercises the actual report script against a small DOM fixture.
// It does not claim browser layout, rendering or native input-event coverage.
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.dataset = {}; this.textContent = '';
    this.value = ''; this.disabled = false; this.events = {}; this.attrs = {};
    this.offsetTop = 0; this.clientHeight = 24; this.scrollTop = 0;
    this.classes = new Set();
    this.classList = { toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name) };
  }
  appendChild(child) {
    child.offsetTop = this.children.length * 24;
    this.children.push(child);
    if (this.tag === 'select' && this.children.length === 1) this.value = child.value;
  }
  replaceChildren() { this.children = []; }
  querySelectorAll(tag) { return this.children.filter(child => child.tag === tag); }
  setAttribute(name, value) { this.attrs[name] = value; }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(name, handler) { this.events[name] = handler; }
  fire(name) { assert.equal(typeof this.events[name], 'function'); this.events[name]({target: this}); }
}
const ids = ['report-data', 'path-select', 'step-range', 'path-rows', 'step-label', 'current-frame',
  'current-site', 'current-opcode', 'current-bytes', 'incoming-edge', 'current-visits', 'path-id',
  'first-step', 'prev-step', 'next-step', 'last-step', 'path-table-scroll', 'path-status'];
const elements = Object.fromEntries(ids.map(id => [id, new Element(id === 'path-select' ? 'select' : 'div')]));
elements['report-data'].textContent = JSON.stringify(data);
elements['path-table-scroll'].clientHeight = 330;
const frameCards = Array.from({length: 6}, (_, frame) => {
  const el = new Element('g'); el.dataset.frameCard = String(frame); return el;
});
const document = {
  getElementById: id => { assert.ok(elements[id], id); return elements[id]; },
  createElement: tag => new Element(tag),
  querySelectorAll: selector => { assert.equal(selector, '[data-frame-card]'); return frameCards; },
  documentElement: {dataset: {}}
};
vm.runInNewContext(fs.readFileSync(path.join(directory, 'report.js'), 'utf8'), {document});
assert.equal(document.documentElement.dataset.explorerReady, 'true');
assert.equal(elements['path-select'].children.length, 9);
for (let i = 0; i < data.paths.length; i += 1) {
  const selected = data.paths[i];
  elements['path-select'].value = String(i);
  elements['path-select'].fire('change');
  assert.equal(elements['path-rows'].children.length, selected.nodes.length);
  assert.equal(elements['current-site'].textContent, data.nodes[selected.nodes[0]].site);
  assert.equal(elements['first-step'].disabled, true);
  assert.equal(elements['prev-step'].disabled, true);
  assert.equal(elements['path-id'].textContent, selected.id);
  elements['next-step'].fire('click');
  assert.equal(elements['current-site'].textContent, data.nodes[selected.nodes[1]].site);
  assert.equal(elements['incoming-edge'].textContent, 'call');
  elements['last-step'].fire('click');
  assert.equal(elements['current-site'].textContent, '0x00007ff724c93bd8');
  assert.equal(elements['current-opcode'].textContent, 'MOV32mi');
  assert.equal(elements['next-step'].disabled, true);
  assert.equal(elements['last-step'].disabled, true);
  assert.deepEqual(frameCards.filter(el => el.classes.has('active-frame')).map(el => el.dataset.frameCard), ['0']);
  assert.equal(elements['path-rows'].children.filter(el => el.attrs['aria-current'] === 'step').length, 1);
  elements['prev-step'].fire('click');
  assert.equal(elements['current-site'].textContent, data.nodes[selected.nodes.at(-2)].site);
  elements['step-range'].value = '6';
  elements['step-range'].fire('input');
  assert.equal(elements['current-site'].textContent, data.nodes[selected.nodes[6]].site);
  elements['first-step'].fire('click');
  assert.equal(elements['current-frame'].textContent, 'Recursive · frame 5');
}
console.log(JSON.stringify({passed: true, paths_exercised: 9,
  controls: ['path selection', 'next', 'previous', 'first', 'fault endpoint', 'range input', 'frame highlight', 'active table row', 'boundary button states'],
  environment: 'Node VM with simulated DOM; browser interactions and rendering unexercised'}));
