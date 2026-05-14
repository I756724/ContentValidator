/**
 * UA Content Validator - Structured results with proper table format
 */

document.addEventListener('DOMContentLoaded', () => {
    checkServiceStatus();
    setupToggle();
});

function setupToggle() {
    const cards = document.querySelectorAll('.type-card');
    const elRow = document.getElementById('elementTypeRow');
    cards.forEach(card => {
        card.addEventListener('click', () => {
            cards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            card.querySelector('input').checked = true;
            elRow.style.display = card.dataset.type === 'ui_label' ? 'flex' : 'none';
        });
    });
}

async function checkServiceStatus() {
    try {
        const r = await fetch('/status');
        const d = await r.json();
        const st = document.getElementById('saptermStatus');
        const ai = document.getElementById('aiStatus');
        st.className = 'service-indicator ' + (d.sapterm?.status === 'connected' ? 'connected' : 'disconnected');
        ai.className = 'service-indicator ' + (d.ai?.status === 'connected' ? 'connected' : 'disconnected');
    } catch(e) {}
}

async function validate() {
    const text = document.getElementById('inputText').value.trim();
    if (!text) return alert('Please enter text to validate');

    const contentType = document.querySelector('input[name="content_type"]:checked').value;
    const elementType = document.getElementById('elementType').value;
    const context = document.getElementById('inputContext').value.trim();

    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('loading').style.display = 'block';
    document.getElementById('validateBtn').disabled = true;

    try {
        const res = await fetch('/validate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ text, content_type: contentType, element_type: elementType, context })
        });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        renderResults(data);
    } catch(e) {
        alert('Failed: ' + e.message);
    } finally {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('validateBtn').disabled = false;
    }
}

function renderResults(data) {
    document.getElementById('resultsSection').style.display = 'block';
    renderSummary(data.summary, data.ai_analysis);
    renderTable(data);
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function renderSummary(summary, ai) {
    const el = document.getElementById('resultSummary');
    const complexity = ai?.complexity || 'Unknown';
    const cClass = 'complexity-' + complexity.toLowerCase();
    
    const totalIssues = summary.counts.errors + summary.counts.warnings;
    const aiIssues = (ai?.grammar_issues?.length || 0) + (ai?.german_issues?.length || 0);
    const total = totalIssues + aiIssues;
    
    let badge = '';
    if (total > 0) {
        badge = `<span class="summary-badge badge-review">${total} finding${total>1?'s':''} to review</span>`;
    } else {
        badge = `<span class="summary-badge badge-good">No issues found</span>`;
    }

    el.innerHTML = `${badge}<span class="complexity-indicator ${cClass}">🇩🇪 Translation Complexity: <strong>${complexity}</strong></span>`;
}

function renderTable(data) {
    const tbody = document.getElementById('resultsTableBody');
    let rows = '';
    const ai = data.ai_analysis || {};
    const elementType = data.input?.type || 'field';

    // 1. SAPterm (only if it has useful data)
    rows += buildSAPtermRow(data.terminology);

    // 2. Fiori Guidelines — ONLY show violations (not "Compliant")
    const guidelineIssues = data.guidelines || [];
    if (guidelineIssues.length > 0) {
        rows += buildGuidelinesRow(guidelineIssues);
    }

    // 3. DE Length — ONLY show if risk is medium or high
    if (data.german_readiness?.length_expansion?.risk === 'high' || data.german_readiness?.length_expansion?.risk === 'medium') {
        const le = data.german_readiness.length_expansion;
        rows += tableRow('DE Length',
            `${le.english_chars} chars → ~${le.estimated_german_chars} chars in German (+${le.expansion_percent}%)`,
            le.risk === 'high' ? 'Shorten text — German translation will likely overflow UI space' : 'Monitor — may be tight in constrained UI areas'
        );
    }

    // 4. German Translation Issues (from rule-based + AI combined)
    rows += buildGermanRow(data.german_readiness, ai, elementType);

    // 5. Grammar (consolidated from AI)
    if (ai.grammar_issues?.length > 0) {
        rows += buildGrammarRow(ai.grammar_issues);
    }

    // 6. AI Suggestions (integrated into table)
    if (ai.suggestions?.length > 0) {
        rows += buildSuggestionsRow(ai.suggestions);
    }

    // 7. Note (only if context is missing and AI has something to say)
    if (ai.note) {
        rows += tableRow('💡 Note', ai.note, '');
    }

    tbody.innerHTML = rows;

    // Hide separate AI section since we integrated it into the table
    document.getElementById('aiSection').style.display = 'none';
}

function buildSAPtermRow(term) {
    if (term.sapterm) {
        const st = term.sapterm;
        if (st.error) {
            return tableRow('SAPterm', 'Service currently unavailable', 'SAPterm cookie needs to be refreshed');
        }
        if (st.found && st.results?.length) {
            const r = st.results[0];
            let finding = `"${r.term}" — found in SAPterm`;
            if (r.german) finding += `<br>• German: <strong>${r.german}</strong>`;
            if (r.component) finding += `<br>• Component: ${r.component}`;
            if (r.definition) finding += `<br>• Definition: ${r.definition}`;
            if (st.results.length > 1) {
                finding += `<br>• ⚠️ Found in ${st.results.length} components`;
            }
            const action = st.results.length > 1 ? 'Multiple contexts exist — verify which applies to your product' : 'Term verified in SAPterm';
            return tableRow('SAPterm', finding, action);
        }
        return tableRow('SAPterm', `"${st.searched}" — not found in SAPterm`, 'Add term to SAPterm or verify if an alternative approved term exists');
    }
    return '';
}

function buildGuidelinesRow(issues) {
    let findings = issues.map((g, i) => `${i+1}. ${g.message}`).join('<br>');
    let actions = issues.map((g, i) => g.suggestion ? `${i+1}. ${g.suggestion}` : '').filter(Boolean).join('<br>');
    if (!actions) actions = '—';
    // Add guideline reference link
    actions += '<br><br><a href="https://www.sap.com/design-system/fiori-design-web/v1-145/foundations/writing-and-wording/ux-writing/ui-text-guidelines-for-sap-fiori" target="_blank" style="font-size:11px;color:#0070F2;">📖 Fiori UI Text Guidelines</a>';
    return tableRow('Fiori Guidelines', findings, actions);
}

function buildGermanRow(german, ai, elementType) {
    let findings = [];
    let actions = [];

    // German issues from AI (these are the valuable ones)
    if (ai.german_issues?.length > 0) {
        ai.german_issues.forEach((issue, i) => {
            findings.push(`${findings.length + 1}. ${issue.issue || issue.text || ''}`);
            actions.push(`${actions.length + 1}. ${issue.explanation || issue.suggestion || ''}`);
        });
    }

    // Rule-based issues (only add if not redundant with AI)
    const ruleIssues = [
        ...(german?.compound_issues || []),
        ...(german?.compound_nouns || []),
        ...(german?.issues || [])
    ];

    // Skip compound noun warning for app names (too obvious)
    const filteredIssues = ruleIssues.filter(issue => {
        if (elementType === 'app_name' && issue.type === 'compound_noun') return false;
        return true;
    });

    // Only add rule-based if AI didn't already cover it
    if (findings.length === 0 && filteredIssues.length > 0) {
        filteredIssues.forEach(issue => {
            findings.push(`${findings.length + 1}. ${issue.message}`);
            if (issue.suggestion) actions.push(`${actions.length + 1}. ${issue.suggestion}`);
        });
    }

    if (findings.length === 0) return '';

    return tableRow('German Translation', findings.join('<br>'), actions.join('<br>') || '—');
}

function buildGrammarRow(grammarIssues) {
    let findings = grammarIssues.map((g, i) => 
        `${i+1}. <strong>"${g.text}"</strong> — ${g.issue}`
    ).join('<br>');
    
    let actions = grammarIssues.map((g, i) => 
        g.fix ? `${i+1}. ${g.fix}` : ''
    ).filter(Boolean).join('<br>');

    return tableRow('Grammar & Style', findings, actions || '—');
}

function buildSuggestionsRow(suggestions) {
    let findings = suggestions.map((s, i) => {
        const text = s.text || s.improved || '';
        return `${i+1}. <strong>"${text}"</strong>`;
    }).join('<br>');

    let actions = suggestions.map((s, i) => {
        return `${i+1}. ${s.reason || ''}`;
    }).join('<br>');

    return tableRow('Suggested Alternatives', findings, actions);
}

function tableRow(check, finding, action) {
    return `<tr>
        <td><span class="check-name">${check}</span></td>
        <td><div class="finding-text">${finding}</div></td>
        <td><div class="finding-action">${action}</div></td>
    </tr>`;
}