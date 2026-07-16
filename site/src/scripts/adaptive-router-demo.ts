type Demo = { presets: any[] };

document.querySelectorAll<HTMLElement>('[data-router-demo]').forEach((root) => {
  const payload = root.querySelector<HTMLScriptElement>('[data-demo-payload]');
  if (!payload) return;
  const demo = JSON.parse(payload.textContent || '{}') as Demo;
  const locale = root.dataset.locale || 'en';
  let preset = demo.presets.find((item) => item.id === root.dataset.initial) || demo.presets[0];
  let branchId = preset.branches[0].branch_id;
  const selectBranch = () => preset.branches.find((item: any) => item.branch_id === branchId) || preset.branches[0];
  const text = (selector: string, value: string) => { const node = root.querySelector<HTMLElement>(selector); if (node) node.textContent = value; };
  const render = () => {
    const branch = selectBranch();
    text('[data-demo-request]', preset.request[locale]);
    text('[data-demo-envelope]', preset.decision.envelope);
    text('[data-testid="demo-status"]', branch.status[locale]);
    text('[data-testid="demo-explicit-coverage"]', `explicit coverage · ${branch.explicit_skill_coverage.status}`);
    const route = root.querySelector<HTMLElement>('[data-demo-route]');
    if (route) route.innerHTML = `<p><span>PRIMARY</span><b>${branch.route.primary_selection}</b></p>${branch.route.support_selections.map((id: string) => `<p data-testid="demo-active-support"><span>SUPPORT</span><b>${id}</b></p>`).join('')}`;
    const events = root.querySelector<HTMLOListElement>('[data-demo-events]');
    if (events) events.innerHTML = branch.events.map((event: any, index: number) => `<li data-testid="${event.event_type === 'SUPPORT_SKILL_PROPOSED' ? 'demo-audit-proposal' : event.event_type === 'CAPABILITY_ACTIVATION_OBSERVED' ? 'demo-activation-event' : 'demo-audit-event'}"><span>${String(index + 1).padStart(2, '0')}</span><b>${event.event_type}</b><small>${event.payload.capability_id || event.payload.envelope || ''}${event.payload.origin ? ` · ${event.payload.origin}` : ''}</small></li>`).join('');
    const graph = root.querySelector<HTMLElement>('[data-demo-graph]');
    if (graph) graph.innerHTML = preset.work_items.map((item: any) => `<div class="router-demo-work-item" data-testid="goal-work-item"><b>${item.id}</b><span data-testid="work-item-envelope">${item.envelope}</span></div>`).join('');
    const evaluation = root.querySelector<HTMLElement>('[data-demo-evaluation]');
    if (evaluation) evaluation.innerHTML = preset.evaluation ? `<div class="router-demo-eval"><span>${preset.evaluation.evidence_class}</span><b>${preset.evaluation.status}</b><p>${preset.evaluation.limitations.join(' ')}</p></div>` : '';
    const consent = root.querySelector<HTMLElement>('[data-demo-consent]'); if (consent) consent.hidden = preset.branches.length < 2;
    root.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach((button) => { const selected = button.dataset.preset === preset.id; button.setAttribute('aria-selected', String(selected)); button.tabIndex = selected ? 0 : -1; });
  };
  root.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach((button) => button.addEventListener('click', () => { preset = demo.presets.find((item) => item.id === button.dataset.preset); branchId = preset.branches[0].branch_id; render(); }));
  root.querySelectorAll<HTMLButtonElement>('[data-branch]').forEach((button) => button.addEventListener('click', () => { branchId = button.dataset.branch || branchId; render(); }));
  root.querySelector('[role="tablist"]')?.addEventListener('keydown', (event) => {
    if (!(event instanceof KeyboardEvent) || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const tabs = [...root.querySelectorAll<HTMLButtonElement>('[data-preset]')]; const current = tabs.findIndex((tab) => tab.getAttribute('aria-selected') === 'true');
    tabs[(current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length].click(); tabs[(current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length].focus();
  });
  render();
});
