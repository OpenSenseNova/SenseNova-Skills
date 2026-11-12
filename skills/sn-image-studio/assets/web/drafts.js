export function createDraft(originalPrompt) {
  return { text: originalPrompt, committed: originalPrompt, version: 1, history: [], source: 'original', request: '', messages: [], preserveStyle: true };
}

export function draftKey(caseId, language) {
  return `${caseId}:${language}`;
}

// Old single-language drafts belong to the source language. Keep edits/history intact.
export function restoreSavedDrafts(saved, templates) {
  const drafts = {};
  for (const [key, value] of Object.entries(saved || {})) {
    const [id, storedLanguage] = key.split(':');
    const item = templates[id];
    const language = storedLanguage || item?.promptLocalization?.sourceLanguage || 'zh-CN';
    if (!item || !['zh-CN', 'en'].includes(language) || !value || typeof value.text !== 'string'
      || typeof value.committed !== 'string' || !Number.isSafeInteger(value.version) || value.version < 1) continue;
    const original = item.promptLocales?.[language] || item.originalPrompt;
    const draft = {
      ...createDraft(original), text: value.text, committed: value.committed, version: value.version,
      source: typeof value.source === 'string' ? value.source : 'manual',
      history: Array.isArray(value.history) ? value.history.filter(x => typeof x?.text === 'string').slice(-8) : [],
      request: typeof value.request === 'string' ? value.request : '',
      preserveStyle: value.preserveStyle !== false,
      candidate: value.candidate?.response?.new_prompt && value.candidate?.task ? value.candidate : null,
      messages: Array.isArray(value.messages) ? value.messages.filter(x => x && ['user', 'notice', 'assistant'].includes(x.role) && typeof x.text === 'string').slice(-8) : [],
    };
    const target = draftKey(id, language);
    if (storedLanguage || !drafts[target]) drafts[target] = refreshDefaultDraft(draft, original);
  }
  return drafts;
}

export function refreshDefaultDraft(draft, originalPrompt) {
  const followsTemplate = draft.source === 'original' || draft.source === 'restore';
  if (!followsTemplate || draft.text !== draft.committed || draft.text === originalPrompt) return draft;
  return { ...draft, text: originalPrompt, committed: originalPrompt, version: draft.version + 1 };
}

export function commitDraft(draft, source = 'manual') {
  if (draft.text === draft.committed) return draft;
  return {
    ...draft,
    committed: draft.text,
    version: draft.version + 1,
    source,
    history: [...draft.history, { text: draft.committed, source: draft.source }].slice(-8),
  };
}

export function undoDraft(draft) {
  const current = commitDraft(draft);
  if (!current.history.length) return current;
  const previous = current.history[current.history.length - 1];
  return { ...current, text: previous.text, committed: previous.text, version: current.version + 1, source: 'undo', history: current.history.slice(0, -1) };
}

export function restoreDraft(draft, originalPrompt) {
  const current = commitDraft(draft);
  return commitDraft({ ...current, text: originalPrompt }, 'restore');
}

export function promptSnapshot(draft) {
  if (draft.text !== draft.committed) throw new Error('Commit the current draft before creating a task.');
  return { base_revision: draft.version, current_prompt: draft.text };
}

export function canApplyRewrite(draft, task) {
  return draft.version === task.base_revision && draft.text === task.current_prompt;
}

export function receiveRewrite(draft, task, response) {
  if (!canApplyRewrite(draft, task)) {
    return { ...draft, candidate: { task, response } };
  }
  return { ...commitDraft({ ...draft, text: response.new_prompt }, 'ai'), candidate: null };
}
