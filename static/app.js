/**
 * UA Content Validator - Frontend logic
 */

const LANG_NAMES = {
    "de-DE": "German (DE)", "fr-FR": "French (FR)", "es-ES": "Spanish (ES)",
    "it-IT": "Italian (IT)", "nl-NL": "Dutch (NL)", "pt-BR": "Portuguese BR",
    "ja-JP": "Japanese (JA)", "zh-CN": "Chinese Simplified (ZH)", "ko-KR": "Korean (KO)"
};

let _lastValidationData = null;

document.addEventListener('DOMContentLoaded', () => {
    checkServiceStatus();
    setInterval(checkServiceStatus, 120000); // refresh every 2 min
    setupToggle();
    setupCharCounter();
    setupCtrlEnter();
});

function setupToggle() {
    const cards = document.querySelectorAll('.type-card');
    const elRow = document.getElementById('elementTypeRow');
    cards.forEach(card => {
        card.addEventListener('click', () => {
            cards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            card.querySelector('input').checked = true;
            const isUI = card.dataset.type === 'ui_label';
            elRow.style.display = isUI ? 'flex' : 'none';
            updateCharCounter(); // update limit hint when mode changes
        });
    });
}

function setupCtrlEnter() {
    document.getElementById('inputText').addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'Enter') validate();
    });
    document.getElementById('inputContext').addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'Enter') validate();
    });
}

function setupCharCounter() {
    document.getElementById('inputText').addEventListener('input', updateCharCounter);
}

function updateCharCounter() {
    const text = document.getElementById('inputText').value;
    const len = text.length;
    const isUI = document.querySelector('input[name="content_type"]:checked').value === 'ui_label';
    const limit = isUI ? 300 : 3000;
    const el = document.getElementById('charCount');
    const hint = document.getElementById('charLimitHint');

    el.textContent = `${len} chars`;
    el.className = 'char-count'
        + (len > limit * 0.85 ? ' char-count-warn' : '')
        + (len > limit ? ' char-count-over' : '');

    hint.textContent = isUI
        ? `UI Text: max 300 · Ctrl+Enter to validate`
        : `Documentation: max 3000 · Ctrl+Enter to validate`;
}

async function checkServiceStatus() {
    try {
        const r = await fetch('/status');
        const d = await r.json();
        setIndicator('saptermStatus', d.sapterm?.status);
        setIndicator('aiStatus',      d.ai?.status);
        setIndicator('wikiStatus',    d.wiki?.status);
    } catch(e) {}
}

function setIndicator(id, status) {
    const el = document.getElementById(id);
    if (!el) return;
    const cls = status === 'connected' ? 'connected'
              : status === 'expired'   ? 'expired'
              : 'disconnected';
    el.className = 'service-indicator ' + cls;
}

async function validate() {
    const text = document.getElementById('inputText').value.trim();
    if (!text) return alert('Please enter text to validate');

    const contentType = document.querySelector('input[name="content_type"]:checked').value;
    const isUI = contentType === 'ui_label';
    const limit = isUI ? 300 : 3000;
    if (text.length > limit) {
        return alert(`Text is ${text.length} chars — maximum is ${limit} for ${isUI ? 'UI Text' : 'Documentation'} mode`);
    }

    const elementType   = document.getElementById('elementType').value;
    const targetLang    = document.getElementById('targetLanguage')?.value || 'de-DE';
    const context       = document.getElementById('inputContext').value.trim();

    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('loading').style.display = 'block';
    document.getElementById('validateBtn').disabled = true;

    // Refresh service status alongside the validation call
    checkServiceStatus();

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 35000);

    try {
        const res = await fetch('/validate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ text, content_type: contentType, element_type: elementType,
                                   target_language: targetLang, context }),
            signal: controller.signal
        });
        clearTimeout(timeout);
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        renderResults(data);
    } catch(e) {
        clearTimeout(timeout);
        if (e.name === 'AbortError') {
            alert('Validation timed out (35 s). The AI service may be slow — try again or check the AI Engine indicator.');
        } else {
            alert('Validation failed: ' + e.message);
        }
    } finally {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('validateBtn').disabled = false;
    }
}

function renderResults(data) {
    _lastValidationData = data;
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('exportBar').style.display = 'flex';
    renderSummary(data.summary, data.ai_analysis);
    renderTable(data);
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function renderSummary(summary, ai) {
    const el = document.getElementById('resultSummary');
    // Use rule-based complexity from summary (always present); AI value already merged server-side
    const complexity = summary.complexity || ai?.complexity || 'Unknown';
    const cClass = 'complexity-' + complexity.toLowerCase();

    const fioriErrors   = summary.counts.errors;
    const fioriWarnings = summary.counts.warnings + summary.counts.info;
    const aiIssues = (ai?.grammar_issues?.length || 0) + (ai?.german_issues?.length || 0);
    const reviewCount = fioriWarnings + aiIssues;

    let badge = '';
    if (fioriErrors > 0) {
        badge = `<span class="summary-badge badge-issues">${fioriErrors} issue(s) to fix</span>`;
        if (reviewCount > 0)
            badge += `<span class="summary-badge badge-review">${reviewCount} finding(s) to review</span>`;
    } else if (reviewCount > 0) {
        badge = `<span class="summary-badge badge-review">${reviewCount} finding(s) to review</span>`;
    } else {
        badge = `<span class="summary-badge badge-good">No issues found</span>`;
    }

    // target_language now comes from summary (server-side fix)
    const langCode = summary.target_language || 'de-DE';
    const langShort = (LANG_NAMES[langCode] || langCode).split(' ')[0];
    const translationBadge = summary.translation_available
        ? `<span class="summary-badge badge-info">${langShort} Translation: Live</span>`
        : `<span class="summary-badge badge-info">${langShort} Translation: Estimate</span>`;

    el.innerHTML = `${badge}${translationBadge}<span class="complexity-indicator ${cClass}">Translation Complexity: <strong>${complexity}</strong></span>`;
}

function renderTable(data) {
    const tbody = document.getElementById('resultsTableBody');
    const ai = data.ai_analysis || {};
    const elementType = data.input?.type || 'field_label';
    const translation = data.translation || {};
    const targetLang = data.input?.target_language || 'de-DE';
    const langName = LANG_NAMES[targetLang] || targetLang;
    const aiUnavailable = ai.error && (ai.grammar_issues?.length === 0 || !ai.grammar_issues);

    let rows = '';

    // 1. SAPterm + Glossary
    rows += buildTerminologyRow(data.terminology);

    // 2. Fiori Guidelines — errors and warnings only
    const guidelineIssues = data.guidelines || [];
    if (guidelineIssues.length > 0) rows += buildGuidelinesRow(guidelineIssues);

    // 3. Abbreviations (new)
    if (data.abbreviations?.length > 0) rows += buildAbbreviationsRow(data.abbreviations);

    // 4. SAP Standard Terminology / Consistency (new)
    if (data.consistency?.length > 0) rows += buildConsistencyRow(data.consistency);

    // 5. Translation — live MT Portal result or length estimate
    rows += buildTranslationRow(translation, data.input?.text || '', langName);

    // 6. German/Target Language Readiness — BOTH AI issues AND rule issues shown
    rows += buildReadinessRow(data.german_readiness, ai, elementType, langName);

    // 7. Grammar (from AI)
    if (ai.grammar_issues?.length > 0) rows += buildGrammarRow(ai.grammar_issues);

    // 8. Suggested Alternatives (with copy button)
    if (ai.suggestions?.length > 0) rows += buildSuggestionsRow(ai.suggestions);

    // 9. AI unavailable notice — shown only when AI failed, replaces raw error
    if (aiUnavailable) {
        rows += tableRow('AI Engine',
            'AI analysis not available (key expired)',
            'Refresh Hai proxy key to enable grammar suggestions &amp; SAPterm drafts');
    }

    // 10. Note
    if (ai.note) rows += tableRow('Note', ai.note, '');

    tbody.innerHTML = rows;
    document.getElementById('aiSection').style.display = 'none';
}

// ── Row builders ──────────────────────────────────────────────────────────────

function buildTerminologyRow(term) {
    if (!term) return '';
    let rows = '';

    // SAPterm
    if (term.sapterm) {
        const st = term.sapterm;
        if (st.error) {
            rows += tableRow('SAPterm',
                `Service unavailable — ${st.error}`,
                'Authenticate via sap-auth-mcp or refresh cookies');
        } else if (st.found && st.results?.length) {
            const r = st.results[0];
            let finding = `"${r.term}" found in SAPterm`;
            if (r.german) finding += `<br>Official translation: <strong>${r.german}</strong>`;
            if (r.component) finding += `<br>Component: ${r.component}`;
            if (r.definition) finding += `<br>Definition: ${r.definition}`;
            if (st.results.length > 1)
                finding += `<br><span style="color:var(--warning)">Found in ${st.results.length} components — verify which applies</span>`;
            const action = st.results.length > 1
                ? 'Multiple contexts — confirm the correct product component'
                : 'Term verified in SAPterm';
            rows += tableRow('SAPterm', finding, action);
        } else if (st.searched) {
            const esc = (st.searched || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            const draftBtn = `<br><button class="draft-entry-btn" onclick="draftSAPtermEntry('${esc}')">Draft SAPterm Entry</button>`;
            rows += tableRow('SAPterm',
                `"${st.searched}" not found in SAPterm`,
                `Not in SAPterm — consider adding it${draftBtn}`);
        }
    }

    // Glossary (only when found — it adds value without noise)
    const gl = term.glossary;
    if (gl?.found && gl.entries?.length) {
        const e = gl.entries[0];
        let finding = `"${e.term}" found in SAP Glossary`;
        if (e.definition && e.definition !== 'Found in SAP Glossary (check link for details)')
            finding += `<br>${e.definition}`;
        if (e.component) finding += `<br>Component: ${e.component}`;
        const link = gl.link
            ? `<a href="${gl.link}" target="_blank" style="font-size:11px;color:var(--blue)">View in Glossary</a>`
            : 'Glossary definition available';
        rows += tableRow('SAP Glossary', finding, link);
    }

    return rows;
}

function buildAbbreviationsRow(items) {
    const findings = items.map((a, i) =>
        `${i + 1}. <strong>"${a.abbreviation}"</strong> — ${a.message.split('—')[1]?.trim() || a.message}`
    ).join('<br>');
    const actions = items.map((a, i) =>
        `${i + 1}. ${a.suggestion}`
    ).join('<br>');
    const link = '<br><a href="https://wiki.one.int.sap/wiki/spaces/styleguide" target="_blank" style="font-size:11px;color:var(--blue)">SAP Style Guide — Abbreviations</a>';
    return tableRow('Abbreviations', findings, actions + link);
}

function buildConsistencyRow(items) {
    const findings = items.map((c, i) =>
        `${i + 1}. <strong>"${c.wrong_term}"</strong> → SAP standard: <strong>"${c.correct_term}"</strong>`
    ).join('<br>');
    const actions = items.map((c, i) =>
        `${i + 1}. ${c.suggestion}`
    ).join('<br>');
    return tableRow('SAP Terminology Consistency', findings, actions);
}

function buildGuidelinesRow(issues) {    const findings = issues.map((g, i) => {
        const icon = g.severity === 'error' ? '[Error]' : '[Warning]';
        return `${i + 1}. ${icon} ${g.message}`;
    }).join('<br>');

    const actions = issues.map((g, i) =>
        g.suggestion ? `${i + 1}. ${g.suggestion}` : ''
    ).filter(Boolean).join('<br>');

    const link = '<br><br><a href="https://www.sap.com/design-system/fiori-design-web/v1-145/foundations/writing-and-wording/ux-writing/ui-text-guidelines-for-sap-fiori" target="_blank" style="font-size:11px;color:var(--blue)">Fiori UI Text Guidelines</a>';

    return tableRow('Fiori Guidelines', findings, (actions || 'Review the guideline link') + link);
}

function buildTranslationRow(translation, inputText, langName) {
    if (!translation) return '';
    const lang = langName || 'Target Language';

    if (translation.source === 'mt_portal' && translation.translated) {
        const risk = translation.risk || 'low';
        const riskColor = risk === 'high' ? '#CC1919' : risk === 'medium' ? '#DF6E0C' : '#107E3E';
        const expansion = translation.expansion_percent >= 0
            ? `+${translation.expansion_percent}%`
            : `${translation.expansion_percent}%`;
        const finding = `<strong style="color:${riskColor}">${translation.translated}</strong>`
            + `<br><span style="color:#6A6D70;font-size:12px;">EN: ${translation.english_chars} chars &rarr; ${lang.split(' ')[0]}: ${translation.german_chars} chars (${expansion}) &bull; Risk: ${risk.toUpperCase()}</span>`;
        const action = risk === 'high'
            ? `${lang.split(' ')[0]} translation will likely overflow UI space — shorten the English source`
            : risk === 'medium'
            ? 'Monitor — may be tight in constrained UI areas'
            : 'Length acceptable';
        return tableRow(`${lang.split(' ')[0]} Translation (SAP MT)`, finding, action);
    }

    if (translation.source === 'unavailable' && translation.note) {
        return tableRow(`${lang.split(' ')[0]} Translation`,
            translation.note, 'Connect MT Portal to enable live translation for this language');
    }

    if (translation.fallback) {
        const fb = translation.fallback;
        if (fb.risk === 'low') return ''; // suppress low-risk estimates
        const finding = `~${fb.estimated_german_chars} chars in ${lang.split(' ')[0]} (+${fb.expansion_percent}%) — Risk: ${fb.risk.toUpperCase()}`;
        const action = fb.risk === 'high'
            ? 'Shorten — translation will likely overflow UI space'
            : 'Monitor in constrained UI areas';
        return tableRow('DE Length (Estimate)', finding, action);
    }

    return '';
}

function buildReadinessRow(german, ai, elementType, langName) {
    let findings = [];
    let actions = [];

    // Always show AI german issues when present
    if (ai?.german_issues?.length > 0) {
        ai.german_issues.forEach(issue => {
            findings.push(`${findings.length + 1}. ${issue.issue || issue.text || ''}`);
            actions.push(`${actions.length + 1}. ${issue.explanation || issue.suggestion || ''}`);
        });
    }

    // Always show rule-based issues too (they complement AI, not duplicate)
    const ruleIssues = [
        ...(german?.compound_issues || []),
        ...(german?.compound_nouns || []),
        ...(german?.passive_voice || []),
        ...(german?.vague_pronouns || []),
        ...(german?.long_sentences || []),
        ...(german?.issues || [])
    ].filter(issue => !(elementType === 'app_title' && issue.type === 'compound_noun'));

    ruleIssues.forEach(issue => {
        findings.push(`${findings.length + 1}. ${issue.message}`);
        if (issue.suggestion) actions.push(`${actions.length + 1}. ${issue.suggestion}`);
    });

    if (findings.length === 0) return '';

    const label = langName ? `${langName.split(' ')[0]} Readiness` : 'Translation Readiness';
    return tableRow(label, findings.join('<br>'), actions.join('<br>') || '—');
}

function buildGrammarRow(grammarIssues) {
    const findings = grammarIssues.map((g, i) =>
        `${i + 1}. <strong>"${g.text}"</strong> — ${g.issue}`
    ).join('<br>');

    const actions = grammarIssues.map((g, i) =>
        g.fix ? `${i + 1}. ${g.fix}` : ''
    ).filter(Boolean).join('<br>');

    return tableRow('Grammar & Style', findings, actions || '—');
}

function buildSuggestionsRow(suggestions) {
    const findings = suggestions.map((s, i) => {
        const text = s.text || s.improved || '';
        const escaped = text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        return `${i + 1}. <strong>"${text}"</strong> `
             + `<button class="copy-btn" onclick="copyToClipboard('${escaped}', this)" title="Copy to clipboard">⎘</button>`;
    }).join('<br>');

    const actions = suggestions.map((s, i) =>
        `${i + 1}. ${s.reason || ''}`
    ).join('<br>');

    return tableRow('Suggested Alternatives', findings, actions);
}

function tableRow(check, finding, action) {
    return `<tr>
        <td><span class="check-name">${check}</span></td>
        <td><div class="finding-text">${finding}</div></td>
        <td><div class="finding-action">${action}</div></td>
    </tr>`;
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = '✓';
        btn.classList.add('copy-btn-done');
        setTimeout(() => {
            btn.textContent = '⎘';
            btn.classList.remove('copy-btn-done');
        }, 2000);
    }).catch(() => {
        alert('Copy failed — select and copy manually');
    });
}

// ── SAPterm Draft Entry ───────────────────────────────────────────────────────

let _draftPlainText = '';

async function draftSAPtermEntry(term) {
    const context     = document.getElementById('inputContext').value.trim();
    const elementType = document.getElementById('elementType').value;

    const section = document.getElementById('saptermDraftSection');
    const content = document.getElementById('draftContent');
    section.style.display = 'block';
    content.innerHTML = '<div class="draft-loading"><div class="spinner"></div><p>Drafting SAPterm entry for "' + term + '"…</p></div>';
    section.scrollIntoView({ behavior: 'smooth' });

    try {
        const res = await fetch('/draft-sapterm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ term, context, element_type: elementType })
        });
        const data = await res.json();
        if (data.error) {
            content.innerHTML = `<p class="draft-error">Error: ${data.error}</p>`;
            return;
        }
        renderDraftPanel(data);
    } catch (e) {
        content.innerHTML = `<p class="draft-error">Request failed: ${e.message}</p>`;
    }
}

function renderDraftPanel(d) {
    _draftPlainText = d.plain_text || '';

    const confidence = d.confidence || 'medium';
    const confClass = confidence === 'high' ? 'badge-good' : confidence === 'low' ? 'badge-issues' : 'badge-review';
    const confLabel = confidence.charAt(0).toUpperCase() + confidence.slice(1) + ' Confidence';

    const warnings = (d.warnings || []).map(w =>
        `<li>${w}</li>`
    ).join('');
    const warningBlock = warnings
        ? `<div class="draft-warnings"><strong>Warnings:</strong><ul>${warnings}</ul></div>`
        : '';

    const fields = [
        ['Term',                  d.term || ''],
        ['Part of Speech',        (d.part_of_speech || '').charAt(0).toUpperCase() + (d.part_of_speech || '').slice(1)],
        ['Definition',            d.definition || ''],
        ['Context',               d.context_field || ''],
        ['Product',               d.product || ''],
        ['Application Component', d.application_component || ''],
        ['Source',                d.source || ''],
    ];

    const rows = fields.map(([label, value]) =>
        `<tr><td class="draft-field-label">${label}</td><td class="draft-field-value">${value}</td></tr>`
    ).join('');

    document.getElementById('draftContent').innerHTML = `
        <div class="draft-confidence">
            <span class="summary-badge ${confClass}">${confLabel}</span>
            <span class="draft-disclaimer-inline">AI-generated — verify with a terminology specialist before adding to SAPterm</span>
        </div>
        ${warningBlock}
        <table class="draft-table"><tbody>${rows}</tbody></table>`;
}

function copyDraftText() {
    if (!_draftPlainText) return;
    navigator.clipboard.writeText(_draftPlainText).then(() => {
        const btn = document.getElementById('copyDraftBtn');
        btn.textContent = 'Copied ✓';
        setTimeout(() => btn.textContent = 'Copy as SAPterm Text', 2000);
    }).catch(() => alert('Copy failed — use the Download button instead'));
}

function downloadDraftText() {
    if (!_draftPlainText) return;
    const blob = new Blob([_draftPlainText], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'sapterm-draft-entry.txt';
    a.click();
    URL.revokeObjectURL(a.href);
}

function closeDraftPanel() {
    document.getElementById('saptermDraftSection').style.display = 'none';
    _draftPlainText = '';
}

// ── Export: Copy / Download Findings ─────────────────────────────────────────

function buildExportText(data) {
    const SEP  = '='.repeat(56);
    const DASH = '-'.repeat(56);
    const lines = [];
    const ai     = data.ai_analysis || {};
    const german = data.german_readiness || {};
    const trans  = data.translation || {};

    lines.push('UA CONTENT VALIDATOR — FINDINGS REPORT');
    lines.push(`Generated: ${new Date().toLocaleString()}`);
    lines.push(SEP);
    lines.push(`Input:    ${data.input?.text || ''}`);
    const elLabel = (data.input?.type || '').replace(/_/g, ' ');
    if (elLabel) lines.push(`Element:  ${elLabel}`);
    lines.push(`Language: ${LANG_NAMES[data.input?.target_language] || data.input?.target_language || 'de-DE'}`);
    if (data.input?.context) lines.push(`Context:  ${data.input.context}`);
    lines.push(SEP);
    lines.push('SUMMARY');

    const counts = data.summary?.counts || {};
    lines.push(`Status:     ${data.summary?.status_text || data.summary?.status || ''}`);
    lines.push(`Complexity: ${data.summary?.complexity || 'Unknown'}`);
    lines.push(`Errors: ${counts.errors || 0}  Warnings: ${counts.warnings || 0}  Info: ${counts.info || 0}`);
    lines.push('');
    lines.push('FINDINGS');
    lines.push(DASH);

    // SAPterm
    const st = data.terminology?.sapterm;
    if (st) {
        lines.push('SAPterm');
        if (st.error) {
            lines.push(`  Service unavailable: ${st.error}`);
        } else if (st.found && st.results?.length) {
            const r = st.results[0];
            lines.push(`  "${r.term}" found in SAPterm`);
            if (r.german)    lines.push(`  Official translation: ${r.german}`);
            if (r.component) lines.push(`  Component: ${r.component}`);
            if (r.definition) lines.push(`  Definition: ${r.definition}`);
            if (st.results.length > 1)
                lines.push(`  Multiple contexts (${st.results.length}) — confirm the correct product component`);
        } else if (st.searched) {
            lines.push(`  "${st.searched}" not found — consider adding to SAPterm`);
        }
        lines.push('');
    }

    // Guidelines
    const guidelines = data.guidelines || [];
    if (guidelines.length) {
        lines.push('Fiori Guidelines');
        guidelines.forEach((g, i) => {
            const icon = g.severity === 'error' ? '[Error]' : '[Warning]';
            lines.push(`  ${i + 1}. ${icon} ${g.message}`);
            if (g.suggestion) lines.push(`     Action: ${g.suggestion}`);
        });
        lines.push('');
    }

    // Abbreviations
    if (data.abbreviations?.length) {
        lines.push('Abbreviations');
        data.abbreviations.forEach((a, i) => {
            lines.push(`  ${i + 1}. ${a.message}`);
            lines.push(`     Action: ${a.suggestion}`);
        });
        lines.push('');
    }

    // SAP Terminology Consistency
    if (data.consistency?.length) {
        lines.push('SAP Terminology Consistency');
        data.consistency.forEach((c, i) => {
            lines.push(`  ${i + 1}. "${c.wrong_term}" -> SAP standard: "${c.correct_term}"`);
            lines.push(`     Action: ${c.suggestion}`);
        });
        lines.push('');
    }

    // Translation
    if (trans.source === 'mt_portal' && trans.translated) {
        const langShort = (LANG_NAMES[data.input?.target_language] || 'Target').split(' ')[0];
        lines.push(`${langShort} Translation (SAP MT)`);
        lines.push(`  ${trans.translated}`);
        lines.push(`  Expansion: +${trans.expansion_percent}%  Risk: ${(trans.risk || '').toUpperCase()}`);
        lines.push('');
    } else if (trans.fallback && trans.fallback.risk !== 'low') {
        lines.push('Translation Length (Estimate)');
        lines.push(`  ~${trans.fallback.estimated_german_chars} chars (+${trans.fallback.expansion_percent}%)  Risk: ${trans.fallback.risk.toUpperCase()}`);
        lines.push('');
    }

    // German/Translation Readiness
    const ruleIssues = [
        ...(german.compound_issues || []),
        ...(german.compound_nouns  || []),
        ...(german.passive_voice   || []),
        ...(german.vague_pronouns  || []),
        ...(german.long_sentences  || []),
        ...(german.issues          || [])
    ];
    if (ai.german_issues?.length || ruleIssues.length) {
        const langName = LANG_NAMES[data.input?.target_language || 'de-DE'] || 'German';
        lines.push(`${langName.split(' ')[0]} Readiness`);
        let idx = 1;
        (ai.german_issues || []).forEach(issue => {
            lines.push(`  ${idx++}. ${issue.issue || issue.text || ''}`);
            const detail = issue.explanation || issue.suggestion;
            if (detail) lines.push(`     Action: ${detail}`);
        });
        ruleIssues.forEach(issue => {
            lines.push(`  ${idx++}. ${issue.message}`);
            if (issue.suggestion) lines.push(`     Action: ${issue.suggestion}`);
        });
        lines.push('');
    }

    // Grammar
    if (ai.grammar_issues?.length) {
        lines.push('Grammar & Style');
        ai.grammar_issues.forEach((g, i) => {
            lines.push(`  ${i + 1}. "${g.text}" — ${g.issue}`);
            if (g.fix) lines.push(`     Fix: ${g.fix}`);
        });
        lines.push('');
    }

    // Suggested Alternatives
    if (ai.suggestions?.length) {
        lines.push('Suggested Alternatives');
        ai.suggestions.forEach((s, i) => {
            const text = s.text || s.improved || '';
            lines.push(`  ${i + 1}. "${text}"`);
            if (s.reason) lines.push(`     Reason: ${s.reason}`);
        });
        lines.push('');
    }

    lines.push(SEP);
    lines.push('Generated by UA Content Validator');
    return lines.join('\n');
}

function copyResults() {
    if (!_lastValidationData) return;
    const text = buildExportText(_lastValidationData);
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copyResultsBtn');
        const orig = btn.textContent;
        btn.textContent = 'Copied ✓';
        setTimeout(() => btn.textContent = orig, 2000);
    }).catch(() => alert('Copy failed — use Download Report instead'));
}

function downloadReport() {
    if (!_lastValidationData) return;
    const text = buildExportText(_lastValidationData);
    const blob = new Blob([text], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    const slug = (_lastValidationData.input?.text || 'report')
        .replace(/[^a-zA-Z0-9]/g, '-').replace(/-+/g, '-').slice(0, 30).replace(/-$/, '');
    a.download = `ua-validator-${slug}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
}
