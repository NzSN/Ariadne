(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('report-data').textContent);
  const select = document.getElementById('path-select');
  const range = document.getElementById('step-range');
  const tbody = document.getElementById('path-rows');
  let pathIndex = 0;
  let step = 0;
  const label = frame => `${data.frames[frame].name} · frame ${frame}`;

  data.paths.forEach((path, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `Path ${index + 1} · ${path.nodes.length} instruction nodes`;
    select.appendChild(option);
  });

  function renderRows() {
    tbody.replaceChildren();
    const path = data.paths[pathIndex];
    const counts = new Map();
    path.nodes.forEach((key, index) => {
      const node = data.nodes[key];
      const visit = (counts.get(key) || 0) + 1;
      counts.set(key, visit);
      const tr = document.createElement('tr');
      tr.dataset.step = String(index);
      const values = [index, node.frame, node.site, node.opcode,
        index ? path.kinds[index - 1] : 'start anchor', visit];
      values.forEach((value, column) => {
        const td = document.createElement('td');
        if (column === 2 || column === 3) {
          const code = document.createElement('code');
          code.textContent = String(value);
          td.appendChild(code);
        } else {
          td.textContent = String(value);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function renderStep() {
    const path = data.paths[pathIndex];
    step = Math.max(0, Math.min(path.nodes.length - 1, step));
    const key = path.nodes[step];
    const node = data.nodes[key];
    range.max = String(path.nodes.length - 1);
    range.value = String(step);
    document.getElementById('step-label').textContent = `Step ${step + 1} of ${path.nodes.length}`;
    document.getElementById('current-frame').textContent = label(node.frame);
    document.getElementById('current-site').textContent = node.site;
    document.getElementById('current-opcode').textContent = node.opcode;
    document.getElementById('current-bytes').textContent = node.bytes;
    document.getElementById('incoming-edge').textContent = step ? path.kinds[step - 1] : 'start anchor';
    const visits = path.nodes.slice(0, step + 1).filter(id => id === key).length;
    document.getElementById('current-visits').textContent = `${visits} / ${data.loopVisitCap}`;
    document.getElementById('path-id').textContent = path.id;
    document.getElementById('first-step').disabled = step === 0;
    document.getElementById('prev-step').disabled = step === 0;
    document.getElementById('next-step').disabled = step === path.nodes.length - 1;
    document.getElementById('last-step').disabled = step === path.nodes.length - 1;
    document.querySelectorAll('[data-frame-card]').forEach(card => {
      card.classList.toggle('active-frame', Number(card.dataset.frameCard) === node.frame);
    });
    tbody.querySelectorAll('tr').forEach(row => {
      const active = Number(row.dataset.step) === step;
      row.classList.toggle('selected-step', active);
      if (active) row.setAttribute('aria-current', 'step');
      else row.removeAttribute('aria-current');
    });
    const row = tbody.children[step];
    const box = document.getElementById('path-table-scroll');
    if (row) box.scrollTop = row.offsetTop - tbody.offsetTop - box.clientHeight / 2 + row.clientHeight / 2;
    document.getElementById('path-status').textContent = `Path ${pathIndex + 1}, step ${step + 1}, frame ${node.frame}, ${node.opcode}. Structural alternative under premises.`;
  }

  select.addEventListener('change', () => {
    pathIndex = Number(select.value);
    step = 0;
    renderRows();
    renderStep();
  });
  range.addEventListener('input', () => { step = Number(range.value); renderStep(); });
  document.getElementById('first-step').addEventListener('click', () => { step = 0; renderStep(); });
  document.getElementById('prev-step').addEventListener('click', () => { step -= 1; renderStep(); });
  document.getElementById('next-step').addEventListener('click', () => { step += 1; renderStep(); });
  document.getElementById('last-step').addEventListener('click', () => { step = data.paths[pathIndex].nodes.length - 1; renderStep(); });
  renderRows();
  renderStep();
  document.documentElement.dataset.explorerReady = 'true';
})();
