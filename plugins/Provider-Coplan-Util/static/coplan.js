async function fetchJson(url, options) {
  const resp = await fetch(url, options);
  if (!resp.ok) throw new Error(resp.status + ' ' + resp.statusText);
  return resp.json();
}

async function refresh() {
  const status = await fetchJson('/v1/coplan/status');
  document.getElementById('status').textContent = JSON.stringify(status, null, 2);

  const groups = await fetchJson('/v1/coplan/strategy-groups');
  const list = document.getElementById('groups');
  list.innerHTML = '';
  (groups.groups || []).forEach(function (g) {
    const li = document.createElement('li');
    li.textContent = g.name + ' (' + (g.keys || []).length + ' keys)';
    list.appendChild(li);
  });

  const market = await fetchJson('/v1/coplan/market/templates');
  const marketEl = document.getElementById('market');
  marketEl.innerHTML = '';
  (market.templates || []).forEach(function (t) {
    const li = document.createElement('li');
    li.textContent = t.name + ' — ' + t.description;
    marketEl.appendChild(li);
  });
}

document.getElementById('createGroup').addEventListener('click', async function () {
  const name = document.getElementById('groupName').value.trim();
  if (!name) return;
  await fetchJson('/v1/coplan/strategy-groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name }),
  });
  document.getElementById('groupName').value = '';
  await refresh();
});

refresh().catch(function (err) {
  document.getElementById('status').textContent = String(err);
});
