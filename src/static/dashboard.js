'use strict';
const notice = document.querySelector('#notice');
function announce(message, error = false) {
  notice.textContent = message;
  notice.dataset.error = String(error);
  notice.setAttribute('role', error ? 'alert' : 'status');
}
async function post(path, body, button) {
  button.disabled = true;
  announce('Saving local changes…');
  try {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      body: JSON.stringify(body)
    });
    const payload = await response.json();
    if (!response.ok) {
      const message = typeof payload.detail === 'string' ? payload.detail : 'Check the supplied fields and try again.';
      throw new Error(message);
    }
    window.location.reload();
  } catch (error) {
    announce(error.message || 'Unable to save. Check the local server and retry.', true);
    button.disabled = false;
  }
}
document.querySelector('#refresh').addEventListener('click', event => post('/api/refresh', {}, event.currentTarget));
for (const id of ['assign-form', 'status-form']) {
  const form = document.getElementById(id);
  if (!form) continue;
  form.addEventListener('submit', event => {
    event.preventDefault();
    const fields = new FormData(form);
    const body = {revision: Number(form.dataset.revision)};
    if (id === 'assign-form') {
      body.action = 'assign'; body.owner = fields.get('owner');
    } else {
      body.action = fields.get('action');
      body.rationale = fields.get('rationale');
      body.confirmed = fields.get('confirmed') === 'on';
      if (['resolved', 'dismissed', 'accepted_risk', 'archive'].includes(body.action) && !body.confirmed) {
        announce('Confirm this completion or archive action before applying it.', true); return;
      }
      if (['resolved', 'dismissed', 'accepted_risk', 'archive', 'reopen'].includes(body.action) && !body.rationale.trim()) {
        announce('Add a rationale for this status change.', true); return;
      }
    }
    post('/api/findings/' + encodeURIComponent(form.dataset.fingerprint) + '/actions', body, form.querySelector('button'));
  });
}
const stale = document.querySelector('#stale-indicator');
function updateStaleness() {
  if (!stale.dataset.refreshed) return;
  if (Date.now() - Date.parse(stale.dataset.refreshed) > 15 * 60 * 1000) {
    stale.textContent = '· Snapshot may be stale; refresh to import changes.';
  }
}
updateStaleness();
setInterval(updateStaleness, 60000);
