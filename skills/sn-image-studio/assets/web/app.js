import { getLanguage, localizeDocument, setLanguage, t } from './i18n.js';
import { caseCopy, casePrompt, inputRoleLabel, originalPromptLabel } from './case-copy.js';
import { createDraft, draftKey, restoreSavedDrafts, commitDraft, undoDraft, restoreDraft, promptSnapshot, receiveRewrite } from './drafts.js';

const paths = {
  left:'<path d="m14 6-6 6 6 6"/>', right:'<path d="m10 6 6 6-6 6"/>',
  upRight:'<path d="M6 18 18 6M6 6h12v12"/>', check:'<path d="m5 12 4 4L19 6"/>',
  plus:'<path d="M12 5v14M5 12h14"/>', close:'<path d="m6 6 12 12M6 18 18 6"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 0 1 4.8 1c0 1.6-2.4 1.9-2.4 3.3M12 16.5h.01"/>',
  imagePlus:'<rect x="3" y="4" width="15" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m3 16 4-4 5 5 3-3 3 3M20 3v6M17 6h6"/>',
  ratio:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 5v14"/>',
  canvas:'<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M8 1v6M16 1v6M8 17v6M16 17v6M1 8h6M17 8h6M1 16h6M17 16h6"/>',
  expand:'<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6"/>',
  columns:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
  copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  undo:'<path d="M4 10h10a6 6 0 1 1 0 12M4 10l5-5M4 10l5 5"/>',
  sparkles:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4"/>',
  download:'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ''}</svg>`;
document.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));

const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]));
const ht = (...args) => escapeHTML(t(...args));
const nameOf = item => item.generated ? t('yourWork', { revision: item.revision }) : caseCopy(item).name;
const languageButtons = document.querySelectorAll('[data-language]');
let renderLocalizedState = () => {};
function renderPageLanguage() {
  localizeDocument(document);
  languageButtons.forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.language === getLanguage()));
  });
  renderLocalizedState();
}
languageButtons.forEach(button => button.addEventListener('click', () => {
  if (button.dataset.language === getLanguage()) return;
  if (promptLibrary) commitCurrent();
  setLanguage(button.dataset.language);
  renderPageLanguage();
}));
renderPageLanguage();

function newId() {
  // getRandomValues is available on HTTP pages served over the LAN.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

let promptLibrary, catalog, generation, edits;
try {
  const response = await fetch('/api/catalog');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  promptLibrary = data.templates;
  catalog = Object.entries(promptLibrary).filter(([, item]) => !item.archived).map(([id, item]) => ({ ...item, id }));
  generation = catalog.filter(item => item.mode === 'generate');
  edits = catalog.filter(item => item.mode === 'edit');
  if (!catalog.length) throw { error_code: 'caseCatalogEmpty' };
} catch (error) {
  renderLocalizedState = () => {
    $('#draft-status').textContent = t('catalogLoadFailed', {
      detail: error.error_code ? t(error.error_code) : error.message,
    });
  };
  renderLocalizedState();
  for (const id of ['generate-button', 'rewrite-button', 'rewrite-generate-button']) $('#' + id).disabled = true;
  throw error;
}

let selected = catalog[0], displayed = selected, uploads = [], lastTask = null, toastTimer;
let drafts = {}, sessionId = newId();
let serviceConnected = false, agentState = {}, rewriteBusy = false, pollTimer;
let configuration = { configured: false, image_ready: false }, imageResults = {};
const viewed = [];
const storageKey = 'sensenova-image-studio-design-v2';
const defaultInputRole = index => selected.recipe.inputRoles[index] || '补充参考图';
const galleries = {
  generation: { id: 'generation-gallery', cases: generation },
  editing: { id: 'editing-gallery', cases: edits }
};
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

function currentDraftKey() {
  return draftKey(selected.id, getLanguage());
}
function taskDraftKey(task) {
  const submittedLanguage = lastTask?.request_id === task.request_id ? lastTask.prompt_language : null;
  return draftKey(task.sample_id, task.prompt_language || submittedLanguage || promptLibrary[task.sample_id]?.promptLocalization?.sourceLanguage || 'zh-CN');
}
function currentDraft() {
  return drafts[currentDraftKey()] ||= createDraft(casePrompt(promptLibrary[selected.id]));
}
function save() {
  try {
    const savedUploads = uploads.filter(x => x.assetId).map(x => ({ assetId: x.assetId, role: x.role, roleIsDefault: x.roleIsDefault,
      file: { name: x.file.name, type: x.file.type, size: x.file.size }, url: `/api/assets/${x.assetId}/file` }));
    localStorage.setItem(storageKey, JSON.stringify({ sessionId, selected: selected.id, displayed: displayed.id, drafts, ratio: $('#ratio').value, viewed, lastTask, imageResults, uploads: savedUploads }));
    return true;
  } catch { return false; }
}
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3200);
}
function exampleOriginals(example) {
  if (!example?.before) return [];
  const inputs = example.inputImages?.filter(path => typeof path === 'string' && path.startsWith('assets/'));
  return inputs?.includes(example.before) ? inputs : [example.before];
}
function sampleVisual(item, index) {
  const name = nameOf(item);
  const loading = index < 3 ? 'eager' : 'lazy';
  const tick = `<span class="selected-tick">${icon('check')}</span>`;
  const preview = escapeHTML(item.preview);
  const originals = exampleOriginals(item);
  if (!originals.length) {
    return `<img src="${preview}" alt="${ht('effectAlt', { name })}" loading="${loading}" draggable="false"><span class="sample-number">${String(index + 1).padStart(2, '0')}</span>${tick}`;
  }
  const label = originals.length > 1 ? t('originalCount', { count: originals.length }) : caseCopy(item).beforeLabel(item);
  return `<div class="edit-pair">
    <div class="edit-half"><img src="${escapeHTML(item.before)}" alt="${ht('beforeAlt', { name })}" loading="${loading}" draggable="false"><span class="edit-label">${escapeHTML(label)}</span></div>
    <span class="edit-arrow" aria-hidden="true">${icon('right')}</span>
    <div class="edit-half"><img src="${preview}" alt="${ht('afterAlt', { name })}" loading="${loading}" draggable="false"><span class="edit-label after">${ht('after')}</span></div>
  </div>${tick}`;
}
function renderGallery(items, id) {
  const gallery = document.getElementById(id);
  const position = gallery.scrollLeft;
  gallery.closest('.gallery-section').hidden = items.length === 0;
  gallery.innerHTML = items.map((item, index) => {
    const { name, category } = caseCopy(item);
    return `<article class="sample-card">
      <button type="button" class="sample-select" data-sample="${item.id}" aria-pressed="${item.id === selected.id}" aria-label="${ht('selectCase', { name, category })}">
        <div class="sample-visual">${sampleVisual(item, index)}</div>
        <div class="sample-caption"><span class="sample-title" title="${escapeHTML(name)}">${escapeHTML(name)}</span><span class="sample-category">${escapeHTML(category)}</span></div>
      </button>
    </article>`;
  }).join('');
  gallery.scrollLeft = position;
}
function renderGalleries() {
  for (const { id, cases } of Object.values(galleries)) renderGallery(cases, id);
}
function showExample() {
  const originals = exampleOriginals(displayed);
  const root = $('#case-originals');
  root.replaceChildren();
  root.hidden = !originals.length;
  $('#canvas-edit-arrow').hidden = !originals.length;
  $('#canvas-image-wrap').classList.toggle('has-originals', originals.length > 0);
  $('#case-result-label').hidden = !originals.length;
  originals.forEach((path, index) => {
    const label = originals.length > 1 ? t('originalIndex', { index: index + 1 }) : caseCopy(displayed).beforeLabel(displayed);
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', t('expandLabel', { label }));
    const image = document.createElement('img');
    image.src = path;
    image.alt = `${nameOf(displayed)} · ${label}`;
    const caption = document.createElement('span');
    caption.className = 'edit-label';
    caption.textContent = label;
    button.append(image, caption);
    button.addEventListener('click', () => expandImage(image, image.alt));
    root.append(button);
  });
  const image = $('#result-image');
  image.src = displayed.preview || displayed.src;
  image.alt = displayed.generated ? t('generatedAlt', { name: nameOf(displayed), model: displayed.model })
    : `${nameOf(displayed)} · ${originals.length ? t('after') : t('samplePreview')}`;
  $('#result-dimensions').textContent = '';
  updateImageDimensions();
}
function renderEditor({ replaceText = true } = {}) {
  const draft = currentDraft();
  const original = casePrompt(promptLibrary[selected.id]);
  const dirty = draft.text !== draft.committed;
  if (replaceText) $('#prompt-editor').value = draft.text;
  const labels = { original: 'originalTemplate', manual: 'manualEdit', restore: 'restoreOriginal', undo: 'undone', ai: 'aiRewrite' };
  $('#draft-revision').textContent = `v${draft.version} · ${t(dirty ? 'editingDraft' : labels[draft.source] || 'draftCurrent')}`;
  $('#draft-status').textContent = [
    t('characterCount', { count: draft.text.length.toLocaleString(getLanguage()) }),
    draft.text === original ? originalPromptLabel(original) : t('modified'),
    save() ? t('savedLocally') : t('notSaved'),
  ].join(' · ');
  $('#undo-prompt').disabled = !dirty && !draft.history.length;
  $('#restore-prompt').disabled = draft.text === original;
}
function commitCurrent() {
  drafts[currentDraftKey()] = commitDraft(currentDraft());
  renderEditor({ replaceText: false });
}
function renderReferenceCopy() {
  const copy = caseCopy(selected);
  $('#reference-name').textContent = copy.name;
  $('#workspace-kind').textContent = t(selected.mode === 'edit' ? 'editing' : 'generation');
  const count = selected.requiredInputs;
  $('#input-hint').textContent = count ? t('requiredInputHint', { count }) : t('optionalInputHint');
  $('#case-guidance').textContent = copy.guidance;
}
function updateReference() {
  $('#reference-thumb').src = selected.preview;
  renderReferenceCopy();
  renderUploads();
  $('#prompt-input').value = currentDraft().request;
  $('#preserve-style').checked = currentDraft().preserveStyle;
  document.querySelectorAll('[data-sample]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.sample === selected.id)));
}
function showResult(item, { persist = true } = {}) {
  displayed = item;
  showExample();
  renderResultCopy();
  if (item.generated && !viewed.includes(item.id)) viewed.push(item.id);
  while (viewed.length > 8) viewed.shift();
  renderFilmstrip();
  if (persist) save();
}
function renderResultCopy() {
  const item = displayed;
  const copy = item.generated ? null : caseCopy(item);
  $('.result-panel .preview-badge').textContent = t(item.generated ? 'generatedResult' : 'samplePreview');
  const details = $('#view-details');
  details.firstElementChild.textContent = t(item.generated ? 'generationDetails' : 'details');
  details.title = t(item.generated ? 'generationDetails' : 'exampleDetails');
  $('#result-title').textContent = nameOf(item);
  $('#result-subtitle').textContent = copy?.category || item.model;
  $('#canvas-caption').textContent = copy?.name || t('generatedCaption');
}
function renderFilmstrip() {
  $('#result-filmstrip').innerHTML = viewed.map(id => {
    const x = imageResults[id];
    const name = nameOf(x);
    return `<button class="filmstrip-item ${id === displayed.id ? 'active' : ''}" data-view="${id}" aria-label="${ht('viewResult', { name })}" aria-pressed="${id === displayed.id}"><img src="${escapeHTML(x.src)}" alt="${escapeHTML(name)}"></button>`;
  }).join('');
}
function selectSample(id) {
  const item = catalog.find(x => x.id === id);
  if (!item) return;
  commitCurrent();
  selected = item;
  updateReference(); renderEditor(); renderMessages(); showResult(item);
  toast(t('loadedCase', { name: nameOf(item) }));
}
function renderMessages() {
  const root = $('#messages');
  root.replaceChildren();
  const draft = currentDraft();
  if (!draft.messages.length) {
    const p = document.createElement('p'); p.className = 'rewrite-welcome';
    p.textContent = t('messagesWelcome'); root.append(p);
    const ideas = document.createElement('div'); ideas.className = 'idea-chips';
    [caseCopy(selected).suggestion, t('warmerColors')].forEach(text => {
      const b = document.createElement('button'); b.className = 'idea-chip'; b.textContent = text;
      b.addEventListener('click', () => { $('#prompt-input').value = text; currentDraft().request = text; save(); $('#prompt-input').focus(); });
      ideas.append(b);
    });
    root.append(ideas);
  } else {
    for (const message of draft.messages) {
      const el = document.createElement('div'); el.className = `chat-message ${message.role === 'user' ? 'user' : 'assistant'}`;
      if (message.role !== 'user') { const label = document.createElement('span'); label.className = 'message-role'; label.textContent = message.role === 'assistant' ? t('aiMessageLabel') : 'STUDIO'; el.append(label); }
      const messageText = message.issue ? errorMessage(message.issue) : message.text;
      el.append(document.createTextNode(message.conflict ? `${messageText}\n\n${t('conflictNotice')}` : messageText));
      root.append(el);
    }
    root.scrollTop = root.scrollHeight;
  }
  $('#rewrite-candidate').hidden = !draft.candidate;
}
function renderUploads() {
  const root = $('#upload-list'); root.replaceChildren();
  uploads.forEach((asset, index) => {
    const tile = document.createElement('div'); tile.className = 'upload-tile';
    const img = document.createElement('img'); img.src = asset.url; img.alt = t('inputImage', { index: index + 1 });
    const name = document.createElement('span'); name.textContent = `${index + 1}. ${asset.file.name}`; name.title = asset.file.name;
    const role = document.createElement('input'); role.className = 'upload-role'; role.maxLength = 200;
    role.value = asset.roleIsDefault ? inputRoleLabel(asset.role) : asset.role || '';
    role.placeholder = inputRoleLabel(defaultInputRole(index));
    role.setAttribute('aria-label', t('inputImagePurpose', { index: index + 1 }));
    role.addEventListener('input', () => { asset.role = role.value; asset.roleIsDefault = false; save(); });
    const move = document.createElement('button'); move.className = 'mini-button'; move.textContent = '←';
    move.title = t('moveImage'); move.setAttribute('aria-label', t('moveInputImage', { index: index + 1 })); move.disabled = index === 0;
    move.addEventListener('click', () => { [uploads[index - 1], uploads[index]] = [uploads[index], uploads[index - 1]]; renderUploads(); save(); });
    const remove = document.createElement('button'); remove.className = 'mini-button'; remove.innerHTML = icon('close'); remove.setAttribute('aria-label', t('removeInputImage', { index: index + 1 }));
    remove.addEventListener('click', () => { URL.revokeObjectURL(asset.url); uploads.splice(index, 1); renderUploads(); save(); });
    const detail = document.createElement('div'); detail.append(name, role);
    tile.append(img, detail, move, remove); root.append(tile);
  });
}
function taskEnvelope(operation) {
  commitCurrent();
  const draft = currentDraft();
  return {
    schema_version: 1, session_id: sessionId, request_id: newId(), operation,
    sample_id: selected.id, prompt_language: getLanguage(), case_revision: selected.revision, creation_mode: selected.mode,
    ...promptSnapshot(draft),
    parameters: { aspect_ratio: $('#ratio').value },
    input_images: [], input_image_roles: uploads.map((x, index) => x.role || defaultInputRole(index)),
    sample_image_role: 'preview_only',
    status: 'prepared',
  };
}
function renderReceipt() {
  const image = lastTask?.operation === 'generate_image' || lastTask?.phase === 'generating' || Boolean(lastTask?.image);
  const statuses = {
    uploading: 'preparingImages', queued: 'taskQueued', cancelled: 'taskCancelled', unknown: 'taskUnknown',
    running: image ? 'generatingImage' : lastTask?.phase === 'connecting' ? 'connectingAgent' : 'agentRewriting',
    succeeded: image ? 'imageGenerated' : lastTask?.disposition === 'kept_current' ? 'draftKept'
      : lastTask?.conflict ? 'conflictStatus' : 'rewriteApplied',
  };
  const status = lastTask?.status === 'failed'
    ? t(image ? 'generationFailed' : 'rewriteFailed', { detail: errorMessage(lastTask) })
    : t(statuses[lastTask?.status] || 'taskPrepared');
  $('#task-status').textContent = lastTask
    ? t('taskReceipt', { status, revision: lastTask.base_revision }) : t('taskEmpty');
  $('#export-task').hidden = !lastTask;
  $('#cancel-task').hidden = !lastTask || !['queued','running'].includes(lastTask.status) || lastTask.phase === 'generating';
  renderAgent();
}

function errorMessage(issue) {
  const { error, error_code, error_params } = issue;
  if (/HTTP (401|403)\b/.test(error || '')) return t('modelUnauthorized');
  if (error_code) {
    const message = t(error_code, error_params);
    if (message !== error_code) {
      if (error && error !== message && ['configFailed', 'uploadFailed', 'rewriteSubmitFailed',
        'generationSubmitFailed', 'cancelFailed', 'agentFailed', 'imageFailed'].includes(error_code)) {
        return `${message} (${error})`;
      }
      return message;
    }
  }
  return error || t('tryAgain');
}
function apiError(value, fallback) {
  return { error: value?.error, error_code: value?.error_code || fallback, error_params: value?.error_params };
}

function setRewriteBusy(value) {
  rewriteBusy = value;
  $('#rewrite-button').disabled = value;
  $('#rewrite-button').textContent = t(value && lastTask?.operation === 'rewrite_prompt' ? 'waitingRewrite' : 'rewriteOnly');
  $('#rewrite-generate-button').disabled = value;
  $('#generate-label').textContent = t(value && lastTask?.operation === 'generate_image' ? 'waitingGeneration' : 'generateCurrent');
  $('#new-session').disabled = value;
  $('#generate-button').disabled = value;
}

async function connectAgent() {
  try {
    const response = await fetch('/api/health', { signal: AbortSignal.timeout(3000) });
    const health = response.ok ? await response.json() : null;
    serviceConnected = health?.service === 'sn-image-studio' && health.api_version === 4;
    agentState = health?.agent || {};
    if (health?.configuration) configuration = health.configuration;
  } catch { serviceConnected = false; }
  renderAgent();
  renderConfigurationCopy();
  if (serviceConnected && !configuration.configured) openConfiguration();
  if (serviceConnected && lastTask && !lastTask.handled && ['queued','running','unknown','succeeded','failed','cancelled'].includes(lastTask.status)) {
    setRewriteBusy(true);
    pollRewrite(lastTask.request_id);
  }
}

let configurationIssue;
function renderConfigurationCopy() {
  $('#service-note').textContent = configuration.configured
    ? t('configReady', { model: configuration.model === 'sensenova-u1.5-lite' ? 'SenseNova U1.5 Lite' : configuration.model }) : t('configNeeded');
  $('#config-key').placeholder = t(configuration.has_key ? 'keepKeyPlaceholder' : 'keyPlaceholder');
  $('#config-error').textContent = configurationIssue ? errorMessage(configurationIssue) : '';
}
function openConfiguration() {
  $('#config-base-url').value = configuration.base_url || 'https://token.sensenova.cn/v1';
  $('#config-model').value = configuration.model || 'sensenova-u1.5-lite';
  $('#config-key').value = '';
  $('#config-key').required = !configuration.has_key;
  configurationIssue = undefined;
  renderConfigurationCopy();
  if (!$('#configuration-dialog').open) $('#configuration-dialog').showModal();
}
function ensureConfigured() {
  if (!serviceConnected) { toast(t('startLocalService')); return false; }
  if (!configuration.configured) { openConfiguration(); return false; }
  return true;
}
$('#model-settings').addEventListener('click', openConfiguration);
$('#configuration-form').addEventListener('submit', async e => {
  e.preventDefault(); $('#save-configuration').disabled = true;
  try {
    const response = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Image-Studio': '1' }, body: JSON.stringify({ api_key: $('#config-key').value, base_url: $('#config-base-url').value, model: $('#config-model').value }) });
    const value = await response.json();
    if (!response.ok) {
      configurationIssue = apiError(value, 'configFailed');
      return renderConfigurationCopy();
    }
    configuration = value; configurationIssue = undefined;
    $('#config-key').value = ''; $('#configuration-dialog').close();
    renderConfigurationCopy();
    toast(t('configSaved'));
  } catch (error) {
    configurationIssue = { error_code: 'configFailed', error: error.message };
    renderConfigurationCopy();
  }
  finally { $('#save-configuration').disabled = false; }
});

function renderAgent() {
  const actual = (lastTask?.harness === agentState.harness ? lastTask?.agent_info : null) || agentState.agent_info;
  $('#agent-connection').textContent = !serviceConnected ? t('startLocalService') : !agentState.harness ? t('noAgent') :
    `${agentState.label} · ${actual?.name ? `${actual.name} ${actual.version || ''}`.trim() : t(agentState.available ? 'agentConnectOnRun' : 'agentUnavailable')}`;
}

function applyTaskRewrite(task) {
  if (lastTask?.request_id !== task.request_id || lastTask.rewriteApplied || !task.response?.new_prompt) return;
  const draft = drafts[taskDraftKey(task)];
  if (!draft || task.session_id !== sessionId) return;
  drafts[taskDraftKey(task)] = receiveRewrite(draft, task, task.response);
  const conflict = Boolean(drafts[taskDraftKey(task)].candidate);
  const message = task.response.summary + (task.response.changes.length ? '\n' + task.response.changes.map(x => `• ${x}`).join('\n') : '');
  drafts[taskDraftKey(task)].messages.push({ role: 'assistant', text: message, conflict });
  lastTask = { ...lastTask, ...task, rewriteApplied: true, conflict, disposition: conflict ? 'candidate' : 'applied' };
  if (currentDraftKey() === taskDraftKey(task)) { renderEditor(); renderMessages(); }
}

function displayGeneratedImage(task, response) {
  if (!/^\/api\/assets\/[A-Za-z0-9_-]+\/file$/.test(response?.image_url || '')) return false;
  const item = { id: task.request_id, generated: true, src: response.image_url, model: response.model, revision: task.base_revision,
    submittedPrompt: response.submitted_prompt, sampleId: task.sample_id };
  imageResults[item.id] = item;
  showResult(item);
  return true;
}

function finishTask(task) {
  if (lastTask?.request_id !== task.request_id || lastTask.handled) return;
  const rewrite = task.operation === 'rewrite_prompt';
  if (rewrite) applyTaskRewrite(task);
  if (task.status === 'succeeded') {
    if (task.operation === 'generate_image' || task.generate_after_rewrite) {
      if (displayGeneratedImage(task, rewrite ? task.image : task.response)) toast(t('imageGenerated'));
      else task = { ...task, status: 'failed', error_code: 'imageMissing' };
    } else toast(t(lastTask.conflict ? 'compareFirst' : 'rewriteApplied'));
  }
  if (task.status === 'failed' || task.status === 'cancelled') {
    const issue = task.status === 'cancelled' ? { error_code: 'taskCancelled' }
      : apiError(task, rewrite && task.phase !== 'generating' ? 'agentFailed' : 'imageFailed');
    const text = errorMessage(issue);
    if (rewrite && drafts[taskDraftKey(task)]) drafts[taskDraftKey(task)].messages.push({ role: 'notice', text, issue });
    toast(text);
    task = { ...task, ...issue };
  }
  lastTask = { ...lastTask, ...task, handled: true };
  if (rewrite && drafts[taskDraftKey(task)]) drafts[taskDraftKey(task)].messages = drafts[taskDraftKey(task)].messages.slice(-8);
  setRewriteBusy(false); renderReceipt(); renderMessages(); save();
}

async function pollRewrite(requestId) {
  clearTimeout(pollTimer);
  if (lastTask?.request_id !== requestId || lastTask.handled) return;
  try {
    const response = await fetch(`/api/tasks/${encodeURIComponent(requestId)}`, { signal: AbortSignal.timeout(5000) });
    const task = await response.json();
    if (!response.ok) {
      if (response.status === 404) return finishTask({ ...lastTask, status: 'failed', error_code: 'taskNotFound' });
      throw new Error(errorMessage(apiError(task, 'readTaskFailed')));
    }
    if (task.request_id !== requestId || task.session_id !== sessionId || task.sample_id !== lastTask.sample_id) throw new Error(t('taskMismatch'));
    if (task.operation === 'rewrite_prompt') applyTaskRewrite(task);
    if (['succeeded','failed','cancelled'].includes(task.status)) return finishTask(task);
    lastTask = { ...lastTask, ...task }; renderReceipt(); save();
  } catch {
    if (lastTask?.request_id !== requestId) return;
    lastTask.status = 'unknown'; renderReceipt(); save();
  }
  pollTimer = setTimeout(() => pollRewrite(requestId), 1200);
}

function compareTexts(left, right, title, leftLabel, rightLabel, summary) {
  $('#original-prompt').value = left; $('#current-prompt').value = right;
  $('#compare-title').textContent = title;
  $('#compare-left-label').textContent = leftLabel; $('#compare-right-label').textContent = rightLabel;
  $('#compare-summary').textContent = summary;
  $('#compare-dialog').showModal();
}
function downloadJSON(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$('#prompt-editor').addEventListener('input', () => { currentDraft().text = $('#prompt-editor').value; renderEditor({ replaceText: false }); });
$('#prompt-editor').addEventListener('blur', commitCurrent);
$('#undo-prompt').addEventListener('click', () => { drafts[currentDraftKey()] = undoDraft(currentDraft()); renderEditor(); toast(t('undoToast')); });
$('#restore-prompt').addEventListener('click', () => { drafts[currentDraftKey()] = restoreDraft(currentDraft(), casePrompt(promptLibrary[selected.id])); renderEditor(); toast(t('restoreToast')); });
$('#copy-prompt').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(currentDraft().text); toast(t('copyToast')); }
  catch { $('#prompt-editor').focus(); $('#prompt-editor').select(); toast(t('manualCopyToast')); }
});
$('#compare-prompt').addEventListener('click', () => {
  commitCurrent();
  compareTexts(casePrompt(promptLibrary[selected.id]), currentDraft().text, t('compareTitle'), originalPromptLabel(casePrompt(promptLibrary[selected.id]), 'exampleOriginal'), t('draftCurrent'), t('compareDraftVersion', { name: nameOf(selected), revision: currentDraft().version }));
});
$('#compare-candidate').addEventListener('click', () => {
  const candidate = currentDraft().candidate;
  if (candidate) compareTexts(currentDraft().text, candidate.response.new_prompt, t('candidateCompareTitle'), t('draftCurrent'), t('candidateLabel'), t('compareCandidateVersion', { name: nameOf(selected), revision: candidate.task.base_revision }));
});
$('#apply-candidate').addEventListener('click', () => {
  const candidate = currentDraft().candidate;
  if (!candidate) return;
  commitCurrent();
  drafts[currentDraftKey()] = { ...commitDraft({ ...currentDraft(), text: candidate.response.new_prompt }, 'ai'), candidate: null };
  if (lastTask?.request_id === candidate.task.request_id) { lastTask.conflict = false; lastTask.disposition = 'applied'; }
  renderEditor(); renderMessages(); renderReceipt(); save(); toast(t('rewriteUsed'));
});
$('#dismiss-candidate').addEventListener('click', () => {
  const candidate = currentDraft().candidate;
  if (candidate && lastTask?.request_id === candidate.task.request_id) { lastTask.conflict = false; lastTask.disposition = 'kept_current'; }
  currentDraft().candidate = null; renderMessages(); renderReceipt(); save();
});
$('#prompt-input').addEventListener('input', () => { currentDraft().request = $('#prompt-input').value; save(); });
$('#preserve-style').addEventListener('change', () => { currentDraft().preserveStyle = $('#preserve-style').checked; save(); });
$('#prompt-input').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) $('#prompt-form').requestSubmit(); });
function canGenerate() {
  if (!configuration.image_ready) { toast(t('installImageDependencies')); return false; }
  const needed = selected.requiredInputs;
  if (uploads.length < needed) { toast(t('needMoreImages', { needed, added: uploads.length })); $('#file-input').click(); return false; }
  return true;
}
async function uploadInputs(items) {
  const ids = [];
  for (const upload of items) {
    if (!upload.assetId) {
      const dataUrl = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject({ error_code: 'readImageFailed' }); reader.readAsDataURL(upload.file); });
      const response = await fetch('/api/assets', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Image-Studio': '1' }, body: JSON.stringify({ data_url: dataUrl, file_name: upload.file.name }), signal: AbortSignal.timeout(30000) });
      const asset = await response.json();
      if (!response.ok) throw apiError(asset, 'uploadFailed');
      upload.assetId = asset.asset_id;
    }
    ids.push(upload.assetId);
  }
  return ids;
}
$('#prompt-form').addEventListener('submit', async e => {
  e.preventDefault();
  if (rewriteBusy || !ensureConfigured()) return;
  if (!agentState.available) { toast(t('configureAgent')); return; }
  const generateAfter = e.submitter?.id === 'rewrite-generate-button';
  if (generateAfter && !canGenerate()) return;
  const request = $('#prompt-input').value.trim();
  if (!request) { $('#prompt-input').focus(); toast(t('tellUsYourChange')); return; }
  if (!currentDraft().text.trim()) { toast(t('enterPrompt')); return; }
  const inputSnapshot = [...uploads];
  lastTask = { ...taskEnvelope('rewrite_prompt'), user_request: request, preserve_style: $('#preserve-style').checked,
    generate_after_rewrite: generateAfter, status: 'uploading' };
  // The server owns this immutable submission, including generation.
  const submitted = lastTask;
  currentDraft().messages.push({ role: 'user', text: request });
  currentDraft().messages = currentDraft().messages.slice(-8);
  setRewriteBusy(true); renderMessages(); renderReceipt(); save();
  let posted = false;
  try {
    submitted.input_images = await uploadInputs(inputSnapshot);
    submitted.status = 'queued';
    save();
    posted = true;
    const response = await fetch('/api/rewrites', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Image-Studio': '1' }, body: JSON.stringify(submitted), signal: AbortSignal.timeout(10000) });
    const task = await response.json();
    if (!response.ok) return finishTask({ ...submitted, status: 'failed', ...apiError(task, 'rewriteSubmitFailed') });
    lastTask = { ...submitted, ...task }; renderReceipt(); save();
  } catch (error) {
    if (!posted) return finishTask({ ...submitted, status: 'failed', ...apiError(error.error_code ? error : { error: error.message }, 'uploadFailed') });
    lastTask.status = 'unknown'; renderReceipt(); save();
  }
  pollRewrite(submitted.request_id);
});
async function submitGeneration() {
  if (rewriteBusy || !ensureConfigured() || !canGenerate()) return;
  if (!currentDraft().text.trim()) { $('#prompt-editor').focus(); toast(t('enterPrompt')); return; }
  const inputSnapshot = [...uploads];
  lastTask = { ...taskEnvelope('generate_image'), status: 'uploading' }; setRewriteBusy(true); renderReceipt(); save();
  const submitted = lastTask;
  let generationPosted = false;
  try {
    submitted.input_images = await uploadInputs(inputSnapshot);
    submitted.status = 'queued';
    save();
    generationPosted = true;
    const response = await fetch('/api/generations', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Image-Studio': '1' }, body: JSON.stringify(submitted), signal: AbortSignal.timeout(10000) });
    const task = await response.json();
    if (!response.ok) return finishTask({ ...submitted, status: 'failed', ...apiError(task, 'generationSubmitFailed') });
    lastTask = { ...submitted, ...task }; renderReceipt(); save(); pollRewrite(submitted.request_id);
  } catch (error) {
    if (generationPosted) { lastTask.status = 'unknown'; renderReceipt(); save(); pollRewrite(submitted.request_id); }
    else finishTask({ ...submitted, status: 'failed', ...apiError(error.error_code ? error : { error: error.message }, 'uploadFailed') });
  }
}
$('#generate-button').addEventListener('click', submitGeneration);
$('#cancel-task').addEventListener('click', async () => {
  if (!lastTask) return;
  try {
    const response = await fetch(`/api/tasks/${encodeURIComponent(lastTask.request_id)}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Image-Studio': '1' }, body: '{}' });
    const task = await response.json();
    if (!response.ok) return toast(errorMessage(apiError(task, 'cancelFailed')));
    finishTask(task);
  } catch (error) { toast(errorMessage({ error: error.message, error_code: 'cancelFailed' })); }
});
$('#export-task').addEventListener('click', () => { if (lastTask) { downloadJSON(lastTask, `image-studio-${lastTask.operation}-v${lastTask.base_revision}.json`); toast(t('exportedTask')); } });
$('#ratio').addEventListener('change', save);
$('#upload-button').addEventListener('click', () => $('#file-input').click());
$('#file-input').addEventListener('change', e => {
  const files = [...e.target.files];
  if (uploads.length + files.length > 10) { toast(t('tooManyImages')); e.target.value = ''; return; }
  for (const file of files) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 20 * 1024 * 1024) { toast(t('fileTypeLimit')); continue; }
    uploads.push({ file, url: URL.createObjectURL(file), role: defaultInputRole(uploads.length), roleIsDefault: true });
  }
  e.target.value = ''; renderUploads(); save();
});
function updateImageDimensions() {
  const image = $('#result-image');
  if (image.complete && image.naturalWidth) $('#result-dimensions').textContent = `${image.naturalWidth} × ${image.naturalHeight}`;
}
$('#result-image').addEventListener('load', updateImageDimensions);
$('#result-image').addEventListener('error', event => {
  if (event.target.hasAttribute('src')) $('#result-dimensions').textContent = t('imageLoadFailed');
});
function setOriginalSize(original) {
  $('#image-viewport').classList.toggle('original-size', original);
  $('#image-size-toggle').setAttribute('aria-pressed', String(original));
  $('#image-size-toggle').textContent = t(original ? 'fitWindow' : 'fullSize');
  $('#image-viewport').scrollTo(0, 0);
}
$('#image-size-toggle').addEventListener('click', () => setOriginalSize(!$('#image-viewport').classList.contains('original-size')));
$('#expanded-image').addEventListener('load', () => {
  const image = $('#expanded-image');
  $('#expanded-dimensions').textContent = `${image.naturalWidth} × ${image.naturalHeight}`;
});
function expandImage(image, caption) {
  setOriginalSize(false);
  $('#expanded-dimensions').textContent = image.naturalWidth ? `${image.naturalWidth} × ${image.naturalHeight}` : '';
  $('#expanded-image').src = image.src;
  $('#expanded-image').alt = image.alt;
  $('#expanded-caption').textContent = caption;
  $('#image-dialog').showModal();
}
function expandResult() {
  expandImage($('#result-image'), `${nameOf(displayed)} · ${displayed.generated ? displayed.model : t('samplePreview')}`);
}
$('#expand-result').addEventListener('click', expandResult);
$('#result-image').addEventListener('click', expandResult);
$('#download-result').addEventListener('click', () => {
  const link = document.createElement('a');
  link.href = $('#result-image').src;
  link.download = `SenseNova-${displayed.id}${displayed.generated ? '.png' : '-sample.webp'}`;
  document.body.append(link);
  link.click();
  link.remove();
  toast(t('downloading'));
});
function showInfo(title, paragraphs) { $('#info-title').textContent = title; $('#info-content').replaceChildren(); for (const text of paragraphs) { const p = document.createElement('p'); p.textContent = text; $('#info-content').append(p); } $('#info-dialog').showModal(); }
$('#view-details').addEventListener('click', () => {
  if (displayed.generated) {
    showInfo(nameOf(displayed), [
      t('modelUsed', { model: displayed.model }),
      t('submittedPrompt', { revision: displayed.revision, prompt: displayed.submittedPrompt || t('promptNotSaved') }),
    ]);
    return;
  }
  const copy = caseCopy(displayed);
  showInfo(copy.name, [
    copy.style, copy.effect, copy.editable,
    t('caseInputs', { roles: copy.inputRoles.join(' → ') || t('optionalInputHint') }),
  ].filter(Boolean));
});
$('[data-action="help"]').addEventListener('click', () => showInfo(t('helpTitle'), [t('helpStep1'), t('helpStep2'), t('helpStep3')]));
$('#new-session').addEventListener('click', () => {
  if (rewriteBusy) return;
  commitCurrent();
  try { localStorage.setItem(`${storageKey}-previous`, localStorage.getItem(storageKey)); } catch {}
  uploads.forEach(x => URL.revokeObjectURL(x.url)); uploads = []; drafts = {}; lastTask = null; sessionId = newId(); selected = catalog[0];
  viewed.splice(0, viewed.length); $('#ratio').value = 'auto'; renderUploads(); updateReference(); renderEditor(); renderMessages(); showResult(selected); renderReceipt(); save(); toast(t('newSessionToast'));
});

document.addEventListener('click', e => {
  const sample = e.target.closest('[data-sample]'); if (sample) selectSample(sample.dataset.sample);
  const view = e.target.closest('[data-view]'); if (view && imageResults[view.dataset.view]) showResult(imageResults[view.dataset.view]);
  const close = e.target.closest('[data-close-dialog]'); if (close) document.getElementById(close.dataset.closeDialog).close();
});
for (const [name, { id }] of Object.entries(galleries)) {
  const rail = document.getElementById(id), buttons = [...document.querySelectorAll(`[data-carousel="${name}"]`)];
  function update() {
    const cards = rail.querySelectorAll('.sample-card');
    const max = rail.scrollWidth - rail.clientWidth;
    buttons[0].disabled = !cards.length || rail.scrollLeft < 5;
    buttons[1].disabled = !cards.length || rail.scrollLeft >= max - 5;
    const gap = parseFloat(getComputedStyle(rail).gap) || 0;
    const index = cards.length ? Math.min(cards.length, Math.floor((rail.scrollLeft + 4) / (cards[0].getBoundingClientRect().width + gap)) + 1) : 0;
    $(`#${name}-count`).textContent = `${String(index).padStart(2, '0')} — ${String(cards.length).padStart(2, '0')}`;
  }
  buttons.forEach(b => b.addEventListener('click', () => rail.scrollBy({ left: Number(b.dataset.step) * rail.clientWidth * .72, behavior: reducedMotion ? 'instant' : 'smooth' })));
  rail.addEventListener('scroll', update, { passive: true }); addEventListener('resize', update);
  rail.addEventListener('keydown', e => { if (e.target === rail && ['ArrowRight','ArrowLeft'].includes(e.key)) { e.preventDefault(); rail.scrollBy({ left: (e.key === 'ArrowRight' ? 1 : -1) * 250, behavior: reducedMotion ? 'instant' : 'smooth' }); } });
  let dragging = false, startX = 0, startScroll = 0, distance = 0;
  rail.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' || e.button !== 0) return; dragging = true; startX = e.clientX; startScroll = rail.scrollLeft; distance = 0; });
  addEventListener('pointermove', e => { if (!dragging) return; distance = Math.abs(e.clientX - startX); if (distance > 6) { rail.classList.add('dragging'); rail.scrollLeft = startScroll - (e.clientX - startX); e.preventDefault(); } });
  addEventListener('pointerup', () => { dragging = false; rail.classList.remove('dragging'); });
  rail.addEventListener('click', e => { if (distance > 6) { e.preventDefault(); e.stopPropagation(); } distance = 0; }, true);
  rail.addEventListener('dragstart', e => e.preventDefault()); requestAnimationFrame(update);
}
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } }));
 document.querySelectorAll('.nav-link').forEach(link => link.addEventListener('click', () => document.querySelectorAll('.nav-link').forEach(x => x.classList.toggle('active', x === link))));

try {
  const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
  if (saved) {
    for (const [id, item] of Object.entries(saved.imageResults || {})) if (item?.generated && /^\/api\/assets\/[A-Za-z0-9_-]+\/file$/.test(item.src || '')) imageResults[id] = item;
    selected = catalog.find(x => x.id === saved.selected) || catalog[0]; displayed = catalog.find(x => x.id === saved.displayed) || imageResults[saved.displayed] || selected;
    if (typeof saved.sessionId === 'string') sessionId = saved.sessionId;
    if (Array.isArray(saved.uploads)) uploads = saved.uploads.filter(x => /^[A-Za-z0-9_-]{1,80}$/.test(x?.assetId || '')
      && typeof x.file?.name === 'string').slice(0, 10).map(x => ({ ...x, url: `/api/assets/${x.assetId}/file` }));
    drafts = restoreSavedDrafts(saved.drafts, promptLibrary);
    if (['auto','1:1','3:4','16:9'].includes(saved.ratio)) $('#ratio').value = saved.ratio;
    if (Array.isArray(saved.viewed)) viewed.splice(0, viewed.length, ...saved.viewed.filter(id => imageResults[id]?.generated).slice(-8));
    if (saved.lastTask?.schema_version === 1 && ['rewrite_prompt','generate_image'].includes(saved.lastTask.operation)) lastTask = saved.lastTask;
  }
} catch {}
renderGalleries();
updateReference(); renderEditor(); renderMessages(); showResult(displayed, { persist: false }); renderReceipt();
renderLocalizedState = () => {
  renderGalleries();
  updateReference();
  renderEditor();
  renderMessages();
  renderUploads();
  showExample();
  renderResultCopy();
  renderFilmstrip();
  renderReceipt();
  setRewriteBusy(rewriteBusy);
  renderConfigurationCopy();
  $('#toast').classList.remove('visible');
};
connectAgent();
addEventListener('beforeunload', () => { uploads.forEach(x => URL.revokeObjectURL(x.url)); });
