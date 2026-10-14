/* Project save state and explicit protection before replacing local work. */
(function () {
    'use strict';
    const S = window.SmartEditStudio;
    let saved = '', allowUnload = false, pendingChoice = null, pendingSave = null;
    const indicator = document.createElement('span');
    indicator.id = 'project-save-status'; indicator.className = 'editor-help'; indicator.setAttribute('role', 'status');
    indicator.style.cssText = 'font-size:10px;white-space:nowrap;margin:0';
    document.querySelector('#view-editor .topbar').append(indicator);
    function signature(p) {
        return JSON.stringify(p, (key,value) => ['rendered_asset','production_notes'].includes(key) ? undefined : value);
    }
    function isDirty() { return !!S.getProject() && signature(S.collect()) !== saved; }
    function update() { indicator.textContent = !S.getProject() ? '' : isDirty() ? 'Unsaved changes' : 'Saved'; }
    function markSaved(snapshot) { saved = signature(snapshot || S.collect()); update(); }
    async function save() {
        if (S.hasActiveJob()) throw new Error('Wait for the current job before saving.');
        while (pendingSave) { await pendingSave; if (!isDirty()) return true; }
        if (!S.getProject()) throw new Error('Import a video or plan scenes first.');
        const snapshot = structuredClone(S.collect());
        pendingSave = (async () => {
            await S.api('/projects/' + snapshot.id, 'PUT', snapshot);
            if (S.getProject()?.id === snapshot.id) markSaved(snapshot);
            toast('Project saved.');
            window.refreshStudioProjects?.();
            return true;
        })();
        try { return await pendingSave; } finally { pendingSave = null; }
    }
    function confirmReplacement() {
        if (pendingChoice) return pendingChoice;
        if (!isDirty()) return pendingSave ? pendingSave.then(confirmReplacement, confirmReplacement) : Promise.resolve(true);
        pendingChoice = new Promise(resolve => {
            const focus = document.activeElement;
            const overlay = document.createElement('div'); overlay.id = 'unsaved-project-dialog'; overlay.className = 'modal-overlay open';
            overlay.style.zIndex = '100001';
            const box = document.createElement('div'); box.className = 'modal-box'; box.setAttribute('role','dialog'); box.setAttribute('aria-modal','true'); box.setAttribute('aria-labelledby','unsaved-project-title');
            const heading = document.createElement('h3'); heading.id = 'unsaved-project-title'; heading.textContent = 'Save your changes?';
            const description = document.createElement('p'); description.textContent = 'This project has unsaved edits. Save them before continuing, or discard them.';
            const error = document.createElement('p'); error.setAttribute('role','alert'); error.style.color = 'var(--red)';
            const controls = document.createElement('div'); controls.style.cssText = 'display:flex;gap:10px;flex-wrap:wrap;margin-top:20px';
            const buttons = [];
            const finish = value => { overlay.remove(); document.removeEventListener('keydown',key,true); pendingChoice = null; focus?.focus(); resolve(value); };
            const key = event => {
                event.stopImmediatePropagation();
                if (event.key === 'Escape') { event.preventDefault(); if (!pendingSave) finish(false); }
                if (event.key === 'Tab') {
                    const enabled = buttons.filter(b => !b.disabled), index = enabled.indexOf(document.activeElement);
                    if (enabled.length) { event.preventDefault(); enabled[(index + (event.shiftKey ? -1 : 1) + enabled.length) % enabled.length].focus(); }
                }
            };
            for (const [id,label,value] of [['keep','Keep editing',false],['discard','Discard changes',true],['save','Save and continue','save']]) {
                const button = document.createElement('button'); button.id = 'unsaved-' + id; button.textContent = label; button.className = 'btn ' + (id === 'save' ? 'btn-primary' : 'btn-secondary');
                button.onclick = async () => {
                    if (value !== 'save') return finish(value);
                    buttons.forEach(b => b.disabled = true); error.textContent = '';
                    try { await save(); if (isDirty()) throw new Error('New edits arrived while saving. Save again before continuing.'); finish(true); }
                    catch (e) { error.textContent = 'Could not save: ' + e.message; buttons.forEach(b => b.disabled = false); button.focus(); }
                };
                buttons.push(button); controls.append(button);
            }
            box.append(heading,description,error,controls); overlay.append(box); document.body.append(overlay);
            document.addEventListener('keydown',key,true); buttons[0].focus();
        });
        return pendingChoice;
    }
    window.addEventListener('studio:changed', update);
    window.addEventListener('beforeunload', event => { if (!allowUnload && (isDirty() || pendingSave)) { event.preventDefault(); event.returnValue = ''; } });
    window.SmartEditSafety = {isDirty,markSaved,save,confirmReplacement,
        requestClose: async () => { const ok = await confirmReplacement(); if (ok) allowUnload = true; return ok; }};
    if (S.getProject()) markSaved(); else update();
})();
