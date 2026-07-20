type Demo = { presets: any[] };

const escapeHtml = (value: unknown) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const prettyJson = (value: unknown) => JSON.stringify(value, null, 2);

const copyText = async (value: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const fallback = document.createElement('textarea');
  fallback.value = value;
  fallback.style.position = 'fixed';
  fallback.style.opacity = '0';
  document.body.append(fallback);
  fallback.select();
  document.execCommand('copy');
  fallback.remove();
};

document.querySelectorAll<HTMLElement>('[data-router-demo]').forEach((root) => {
  const payload = root.querySelector<HTMLScriptElement>('[data-demo-payload]');
  if (!payload) return;

  const demo = JSON.parse(payload.textContent || '{}') as Demo;
  const locale = root.dataset.locale || 'en';
  const localized = locale === 'zh-TW'
    ? {
        noGraph: '此情境沒有工作圖。',
        copy: '複製 JSON',
        copied: '已複製',
        request: 'REQUEST',
        response: 'RESPONSE',
        hostRequired: '需要已驗證 Host 能力',
        localBoundary: '此 Runtime 未提供排程能力；結果未被偽造。',
      }
    : {
        noGraph: 'No work graph for this scenario.',
        copy: 'Copy JSON',
        copied: 'Copied',
        request: 'REQUEST',
        response: 'RESPONSE',
        hostRequired: 'Requires verified host capabilities',
        localBoundary: 'This runtime has no scheduler capability; no result was fabricated.',
      };

  let preset = demo.presets.find((item) => item.id === root.dataset.initial) || demo.presets[0];
  let branchId = preset.branches[0].branch_id;

  const selectBranch = () => (
    preset.branches.find((item: any) => item.branch_id === branchId) || preset.branches[0]
  );
  const text = (selector: string, value: string) => {
    const node = root.querySelector<HTMLElement>(selector);
    if (node) node.textContent = value;
  };

  const renderMcpTrace = () => {
    const target = root.querySelector<HTMLElement>('[data-demo-mcp]');
    if (!target) return;
    target.innerHTML = preset.mcp_calls.map((call: any, index: number) => {
      const response = preset.mcp_results[index];
      const status = response.ok ? 'OK' : response.error.code.toUpperCase();
      const resultDocument = response.ok ? response.result : response.error;
      return `
        <details class="router-demo-mcp-step" data-testid="demo-mcp-step">
          <summary>
            <span>${String(index + 1).padStart(2, '0')}</span>
            <code data-testid="demo-mcp-tool">${escapeHtml(call.tool)}</code>
            <b class="${response.ok ? 'is-ok' : 'is-error'}" data-testid="demo-mcp-result">${escapeHtml(status)}</b>
          </summary>
          <div class="router-demo-json-grid">
            <section>
              <header><span>${localized.request}</span><button type="button" data-testid="demo-copy-json" data-copy-json data-copy-step="${index}" data-copy-kind="call">${localized.copy}</button></header>
              <pre tabindex="0"><code>${escapeHtml(prettyJson(call.arguments))}</code></pre>
            </section>
            <section>
              <header><span>${localized.response}</span><button type="button" data-testid="demo-copy-json" data-copy-json data-copy-step="${index}" data-copy-kind="result">${localized.copy}</button></header>
              <pre tabindex="0"><code>${escapeHtml(prettyJson(resultDocument))}</code></pre>
            </section>
          </div>
        </details>`;
    }).join('');

    target.querySelectorAll<HTMLButtonElement>('[data-copy-json]').forEach((button) => {
      button.addEventListener('click', async () => {
        const index = Number(button.dataset.copyStep);
        const value = button.dataset.copyKind === 'call'
          ? preset.mcp_calls[index].arguments
          : preset.mcp_results[index];
        try {
          await copyText(prettyJson(value));
          button.textContent = localized.copied;
          window.setTimeout(() => { button.textContent = localized.copy; }, 1200);
        } catch {
          button.textContent = localized.copy;
        }
      });
    });
  };

  const renderEvidence = () => {
    const target = root.querySelector<HTMLElement>('[data-demo-evidence]');
    if (!target) return;
    const unavailable = preset.mcp_results.find(
      (result: any) => !result.ok && result.error?.code === 'capability-unavailable',
    );
    target.innerHTML = `
      <dl class="router-demo-evidence-grid">
        <div><dt>RUNTIME PROFILE</dt><dd data-testid="demo-runtime-profile">${escapeHtml(preset.runtime_profile)}</dd></div>
        <div><dt>EVIDENCE CLASS</dt><dd data-testid="demo-evidence-class">${escapeHtml(preset.evidence_class)}</dd></div>
        <div><dt>TRACE SOURCE</dt><dd>${escapeHtml(preset.trace_source)}</dd></div>
        <div><dt>TRACE STATUS</dt><dd>${escapeHtml(preset.trace_status)}</dd></div>
      </dl>
      ${preset.requires_host_capabilities ? `<div class="router-demo-boundary is-fixture">${localized.hostRequired}</div>` : ''}
      ${unavailable ? `<div class="router-demo-boundary is-unavailable" data-testid="demo-capability-unavailable"><b>${escapeHtml(unavailable.error.code)}</b><span>${localized.localBoundary}</span><small>${escapeHtml(unavailable.error.fallback_action)}</small></div>` : ''}`;
  };

  const renderEvaluation = () => {
    const target = root.querySelector<HTMLElement>('[data-demo-evaluation]');
    if (!target) return;
    if (!preset.evaluation) {
      target.innerHTML = '';
      return;
    }
    target.innerHTML = `
      <div class="router-demo-eval">
        <span>REAL MODEL EVALUATION</span>
        <dl>
          <div><dt>STATUS</dt><dd data-testid="demo-evaluation-status">${escapeHtml(preset.evaluation.status)}</dd></div>
          <div><dt>PUBLICATION GATE</dt><dd data-testid="demo-evaluation-gate">${escapeHtml(preset.evaluation.publication_gate)}</dd></div>
          <div><dt>EVIDENCE CLASS</dt><dd data-testid="demo-evaluation-class">${escapeHtml(preset.evaluation.evidence_class)}</dd></div>
        </dl>
        <p>${preset.evaluation.limitations.map((item: string) => escapeHtml(item)).join(' ')}</p>
      </div>`;
  };

  const render = () => {
    const branch = selectBranch();
    text('[data-demo-request]', preset.request[locale]);
    text('[data-demo-envelope]', preset.decision.envelope);
    text('[data-testid="demo-status"]', branch.status[locale]);
    text('[data-testid="demo-explicit-coverage"]', `explicit coverage · ${branch.explicit_skill_coverage.status}`);

    const route = root.querySelector<HTMLElement>('[data-demo-route]');
    if (route) {
      route.innerHTML = `
        <p><span>PRIMARY</span><b>${escapeHtml(branch.route.primary_selection)}</b><small>${escapeHtml(branch.route.primary_selection_source)}</small></p>
        ${branch.route.support_selections.map((id: string) => `<p data-testid="demo-active-support"><span>SUPPORT</span><b>${escapeHtml(id)}</b><small>router-approved</small></p>`).join('')}`;
    }

    const events = root.querySelector<HTMLOListElement>('[data-demo-events]');
    if (events) {
      events.innerHTML = branch.events.map((event: any, index: number) => {
        const testId = event.event_type === 'SUPPORT_SKILL_PROPOSED'
          ? 'demo-audit-proposal'
          : event.event_type === 'CAPABILITY_ACTIVATION_OBSERVED'
            ? 'demo-activation-event'
            : 'demo-audit-event';
        const detail = event.payload.capability_id || event.payload.envelope || '';
        return `<li data-testid="${testId}"><span>${String(index + 1).padStart(2, '0')}</span><b>${escapeHtml(event.event_type)}</b><small>${escapeHtml(detail)}${event.payload.origin ? ` · ${escapeHtml(event.payload.origin)}` : ''}</small></li>`;
      }).join('');
    }

    const graph = root.querySelector<HTMLElement>('[data-demo-graph]');
    if (graph) {
      graph.innerHTML = preset.work_items.length
        ? preset.work_items.map((item: any) => `<div class="router-demo-work-item" data-testid="goal-work-item"><b>${escapeHtml(item.id)}</b><span data-testid="work-item-envelope">${escapeHtml(item.envelope)}</span></div>`).join('')
        : `<p class="router-demo-empty">${localized.noGraph}</p>`;
    }

    renderMcpTrace();
    renderEvidence();
    renderEvaluation();

    const consent = root.querySelector<HTMLElement>('[data-demo-consent]');
    if (consent) consent.hidden = preset.branches.length < 2;
    root.querySelectorAll<HTMLButtonElement>('[data-branch]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.branch === branch.branch_id));
    });
    root.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach((button) => {
      const selected = button.dataset.preset === preset.id;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
    });
  };

  root.querySelectorAll<HTMLButtonElement>('[data-preset]').forEach((button) => {
    button.addEventListener('click', () => {
      preset = demo.presets.find((item) => item.id === button.dataset.preset);
      branchId = preset.branches[0].branch_id;
      render();
    });
  });
  root.querySelectorAll<HTMLButtonElement>('[data-branch]').forEach((button) => {
    button.addEventListener('click', () => {
      branchId = button.dataset.branch || branchId;
      render();
    });
  });
  root.querySelector('[role="tablist"]')?.addEventListener('keydown', (event) => {
    if (!(event instanceof KeyboardEvent) || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...root.querySelectorAll<HTMLButtonElement>('[data-preset]')];
    const focused = tabs.findIndex((tab) => tab === event.target);
    const selected = tabs.findIndex((tab) => tab.getAttribute('aria-selected') === 'true');
    const current = focused >= 0 ? focused : selected;
    const next = (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].click();
    tabs[next].focus();
  });

  render();
});
