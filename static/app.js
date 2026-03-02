async function getJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
}

function el(tag, attrs, children) {
  const n = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else n.setAttribute(k, v);
    }
  }
  (children || []).forEach(c => n.appendChild(c));
  return n;
}

function fmtTime(iso) {
  if (!iso) return 'n/a';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function renderEvent(e) {
  const badge = el('span', { class: 'badge', text: `${e.source}:${e.kind}` });
  const title = el('div', { class: 'title', text: e.title || '(no title)' });

  const top = el('div', { class: 'row' }, [title, badge]);

  const bits = [];
  bits.push(el('span', { text: `published: ${fmtTime(e.published_at)}` }));
  bits.push(el('span', { text: `fetched: ${fmtTime(e.fetched_at)}` }));

  if (e.url) {
    const a = el('a', { href: e.url, target: '_blank', rel: 'noreferrer' });
    a.textContent = e.url;
    bits.push(a);
  }

  const meta = el('div', { class: 'meta2' }, bits);

  const card = el('div', { class: 'card' }, [top, meta]);
  if (e.kind === 'source_error') card.classList.add('err');
  return card;
}

async function refresh() {
  const status = document.getElementById('status');
  const wrap = document.getElementById('events');
  status.textContent = 'Loading events...';

  try {
    const data = await getJSON('/api/events?limit=50');
    const events = data.events || [];

    wrap.innerHTML = '';
    if (events.length === 0) {
      wrap.appendChild(el('div', { class: 'card' }, [
        el('div', { class: 'title', text: 'No events yet.' }),
        el('div', { class: 'meta2', text: 'Click “Poll now” to fetch sources.' }),
      ]));
    } else {
      for (const e of events) wrap.appendChild(renderEvent(e));
    }

    status.textContent = `provider=${events[0]?.provider || 'deepseek'}; events=${events.length}`;
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  }
}

async function pollNow() {
  const btn = document.getElementById('pollBtn');
  btn.disabled = true;
  btn.textContent = 'Polling...';
  try {
    await getJSON('/api/poll', { method: 'POST' });
  } catch (err) {
    // Let refresh show source_error events if any
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Poll now';
    await refresh();
  }
}

document.getElementById('pollBtn').addEventListener('click', pollNow);
refresh();
