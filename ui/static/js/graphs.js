$(document).ready(function () {
    const $grid = $('#graphGrid');
    const $noResults = $('#noResults');
    const $searchInput = $('#searchInput');
    const $versionsModal = $('#versionsModal');
    const $versionsModalBody = $('#versionsModalBody');
    const $versionsModalLabel = $('#versionsModalLabel');
    const versionsModal = new bootstrap.Modal($versionsModal[0]);

    let families = Array.isArray(graphFamiliesData) ? graphFamiliesData.map(cloneFamily) : [];
    const selectedVersionByFamily = {};
    const compareLeftByFamily = {};
    let activeModalFamilyId = null;

    function cloneFamily(family) {
        return {
            ...family,
            versions: (family.versions || []).map((v) => ({ ...v })),
        };
    }

    function escHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatTimestamp(value) {
        const text = String(value || '').trim();
        if (!text) return '';
        const date = new Date(text);
        if (Number.isNaN(date.getTime())) return text.slice(0, 19).replace('T', ' ');
        return date.toLocaleString();
    }

    function familyMatchesQuery(family, query) {
        if (!query) return true;
        const haystack = [
            family.name,
            family.family_id,
            family.description,
            ...(family.versions || []).flatMap((v) => [
                v.id,
                v.name,
                v.variant_label,
                v.description,
            ]),
        ]
            .join(' ')
            .toLowerCase();
        return haystack.includes(query);
    }

    function getFamily(familyId) {
        return families.find((item) => item.family_id === familyId) || null;
    }

    function getSelectedVersion(family) {
        const versions = family.versions || [];
        if (!versions.length) return null;
        const selectedId = selectedVersionByFamily[family.family_id];
        return versions.find((v) => v.id === selectedId) || versions[versions.length - 1];
    }

    function getCompareLeftVersion(family, selected) {
        const versions = family.versions || [];
        if (!versions.length) return null;
        const leftId = compareLeftByFamily[family.family_id];
        if (leftId) {
            const found = versions.find((v) => v.id === leftId);
            if (found) return found;
        }
        const idx = versions.findIndex((v) => v.id === selected.id);
        return idx > 0 ? versions[idx - 1] : versions[0];
    }

    function renderDiffHtml(diffText) {
        if (!diffText) {
            return '<span class="text-muted">No differences.</span>';
        }
        return diffText
            .split('\n')
            .map((line) => {
                let cls = '';
                if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) {
                    cls = 'diff-hunk';
                } else if (line.startsWith('+')) {
                    cls = 'diff-add';
                } else if (line.startsWith('-')) {
                    cls = 'diff-del';
                }
                return cls
                    ? `<span class="${cls}">${escHtml(line)}</span>`
                    : escHtml(line);
            })
            .join('\n');
    }

    function renderAgentChanges(rows) {
        if (!rows || !rows.length) {
            return '<p class="small text-muted mb-0">No agent version changes.</p>';
        }
        const body = rows
            .map(
                (row) => `
                <tr>
                    <td><code>${escHtml(row.agent_id)}</code></td>
                    <td><code>${escHtml(row.left || 'current')}</code></td>
                    <td><code>${escHtml(row.right || 'current')}</code></td>
                </tr>`
            )
            .join('');
        return `
            <table class="table table-sm wf-agent-change-table mb-0">
                <thead>
                    <tr>
                        <th>Agent</th>
                        <th>Left</th>
                        <th>Right</th>
                    </tr>
                </thead>
                <tbody>${body}</tbody>
            </table>`;
    }

    async function loadCompareDiff(familyId, leftId, rightId) {
        const $diff = $(`#wf-diff-${familyId}`);
        const $agentChanges = $(`#wf-agent-changes-${familyId}`);
        if (!$diff.length) return;
        if (!leftId || !rightId) {
            $diff.html('<span class="text-muted">Select two versions to compare.</span>');
            $agentChanges.html('<p class="small text-muted mb-0">No agent version changes.</p>');
            return;
        }
        if (leftId === rightId) {
            $diff.html('<span class="text-muted">Select two different versions.</span>');
            $agentChanges.html('<p class="small text-muted mb-0">No agent version changes.</p>');
            return;
        }
        $diff.text('Loading diff...');
        $agentChanges.html('<p class="small text-muted mb-0">Loading...</p>');
        try {
            const res = await fetch('/graph/api/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ left: leftId, right: rightId }),
            });
            const data = await res.json();
            if (!res.ok) {
                $diff.text(`Compare failed: ${data.error || 'unknown error'}`);
                $agentChanges.html('<p class="small text-muted mb-0">Compare failed.</p>');
                return;
            }
            $diff.html(renderDiffHtml(data.diff || ''));
            $agentChanges.html(renderAgentChanges(data.agent_version_changes || []));
        } catch (err) {
            $diff.text(`Compare failed: ${err.message || err}`);
            $agentChanges.html('<p class="small text-muted mb-0">Compare failed.</p>');
        }
    }

    function renderVersionOptions(family, selectedId) {
        return (family.versions || [])
            .map((version) => {
                const label = `${version.variant_label || version.id} (${version.id})`;
                const selected = version.id === selectedId ? ' selected' : '';
                return `<option value="${escHtml(version.id)}"${selected}>${escHtml(label)}</option>`;
            })
            .join('');
    }

    function renderSelectedVersionSummary(selected) {
        const pins = Number(selected.pinned_agent_count || 0);
        const pinText = `${pins} pinned agent${pins === 1 ? '' : 's'}`;
        return `
            <div class="wf-selected-version">
                <div><strong>Version:</strong> <code>${escHtml(selected.variant_label || selected.id)}</code></div>
                <div class="wf-version-id"><code>${escHtml(selected.id)}</code></div>
                <div class="text-muted small">${escHtml(pinText)}</div>
            </div>`;
    }

    function renderCardFooter(family, selected) {
        return `
            <div class="card-footer bg-transparent d-flex justify-content-between">
                <a href="/graph/${encodeURIComponent(selected.id)}/edit"
                   class="btn btn-sm btn-outline-primary wf-edit-btn"
                   data-family-id="${escHtml(family.family_id)}">Edit</a>
                <div class="d-flex gap-1">
                    <button class="btn btn-sm btn-outline-secondary copy-btn"
                            data-id="${escHtml(selected.id)}"
                            data-name="${escHtml(family.name || selected.name || selected.id)}">Copy</button>
                    <button class="btn btn-sm btn-outline-danger delete-btn"
                            data-id="${escHtml(selected.id)}"
                            data-family-id="${escHtml(family.family_id)}"
                            data-name="${escHtml(family.name || selected.name || selected.id)}">Delete</button>
                </div>
            </div>`;
    }

    function renderFamilyCard(family) {
        const versions = family.versions || [];
        const selected = getSelectedVersion(family);
        const multiVersion = versions.length > 1;
        const versionBadge = multiVersion
            ? `<button type="button"
                       class="badge bg-info ms-2 wf-versions-badge"
                       data-family-id="${escHtml(family.family_id)}"
                       title="View versions">${versions.length} versions</button>`
            : '';
        const subgraphBadge = family.is_subgraph
            ? '<span class="badge bg-secondary ms-1">subgraph</span>'
            : '';

        return `
            <div class="col">
                <div class="card h-100 shadow-sm wf-family-card" data-family-id="${escHtml(family.family_id)}">
                    <div class="card-body d-flex flex-column">
                        <div class="wf-card-header mb-2">
                            <h5 class="card-title">${escHtml(family.name || family.family_id)}${versionBadge}${subgraphBadge}</h5>
                            <div class="wf-family-meta">
                                <div><strong>Family:</strong> <code>${escHtml(family.family_id)}</code></div>
                                <div class="wf-family-desc mt-1">${escHtml(family.description || '')}</div>
                            </div>
                        </div>
                        <div class="mt-auto">
                            ${renderSelectedVersionSummary(selected)}
                        </div>
                    </div>
                    ${renderCardFooter(family, selected)}
                </div>
            </div>`;
    }

    function renderModalContent(family) {
        const selected = getSelectedVersion(family);
        const compareLeft = getCompareLeftVersion(family, selected);
        const versionList = (family.versions || [])
            .map((version) => {
                const active = version.id === selected.id ? ' active' : '';
                const pins = Number(version.pinned_agent_count || 0);
                const pinText = pins ? `${pins} pinned agent${pins === 1 ? '' : 's'}` : 'no pinned agents';
                return `
                    <button type="button"
                            class="wf-version-item${active}"
                            data-family-id="${escHtml(family.family_id)}"
                            data-version-id="${escHtml(version.id)}">
                        <div class="d-flex justify-content-between align-items-start gap-2">
                            <div>
                                <div class="wf-version-label">${escHtml(version.variant_label || version.id)}</div>
                                <div class="wf-version-id"><code>${escHtml(version.id)}</code></div>
                            </div>
                            <div class="wf-version-meta text-end">
                                <div>${escHtml(pinText)}</div>
                                <div>${escHtml(formatTimestamp(version.created_at))}</div>
                            </div>
                        </div>
                    </button>`;
            })
            .join('');

        return `
            <div class="wf-modal-family-meta mb-3">
                <div><strong>Family:</strong> <code>${escHtml(family.family_id)}</code></div>
                <div class="text-muted small mt-1">${escHtml(family.description || '')}</div>
            </div>
            <div class="wf-section-title">Versions</div>
            <div class="wf-version-list mb-3">${versionList}</div>
            <div class="wf-diff-panel">
                <div class="wf-section-title">Compare versions</div>
                <div class="row g-2 mb-2">
                    <div class="col-md-6">
                        <label class="form-label small mb-1">Left</label>
                        <select class="form-select form-select-sm wf-compare-left"
                                data-family-id="${escHtml(family.family_id)}">
                            ${renderVersionOptions(family, compareLeft.id)}
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small mb-1">Right</label>
                        <select class="form-select form-select-sm wf-compare-right"
                                data-family-id="${escHtml(family.family_id)}">
                            ${renderVersionOptions(family, selected.id)}
                        </select>
                    </div>
                </div>
                <div class="wf-section-title">Agent version changes</div>
                <div id="wf-agent-changes-${escHtml(family.family_id)}" class="mb-2"></div>
                <div class="wf-section-title">Unified diff</div>
                <pre id="wf-diff-${escHtml(family.family_id)}" class="wf-diff-pre mb-0"></pre>
            </div>`;
    }

    function updateFamilyCard(familyId) {
        const family = getFamily(familyId);
        if (!family) return;
        const selected = getSelectedVersion(family);
        const $card = $(`.wf-family-card[data-family-id="${familyId}"]`);
        if (!$card.length) return;
        $card.find('.mt-auto').html(renderSelectedVersionSummary(selected));
        $card.find('.card-footer').replaceWith(renderCardFooter(family, selected));
    }

    function openVersionsModal(familyId) {
        const family = getFamily(familyId);
        if (!family || !(family.versions || []).length) return;
        activeModalFamilyId = familyId;
        $versionsModalLabel.text(`${family.name || family.family_id} — Versions`);
        $versionsModalBody.html(renderModalContent(family));
        versionsModal.show();
        const selected = getSelectedVersion(family);
        const compareLeft = getCompareLeftVersion(family, selected);
        if ((family.versions || []).length > 1) {
            loadCompareDiff(familyId, compareLeft.id, selected.id);
        }
    }

    async function refreshFamilies() {
        try {
            const res = await fetch('/graph/api/grouped');
            if (res.ok) {
                families = await res.json();
            }
        } catch (_err) {
            // Keep current in-memory families if refresh fails.
        }
    }

    function loadGraphs(query = '') {
        const q = (query || '').toLowerCase().trim();
        const filtered = families.filter((family) => familyMatchesQuery(family, q));

        $grid.empty();
        if (!filtered.length) {
            $noResults.removeClass('d-none');
            return;
        }
        $noResults.addClass('d-none');

        filtered.forEach((family) => {
            if (!selectedVersionByFamily[family.family_id]) {
                selectedVersionByFamily[family.family_id] = family.default_version_id;
            }
            $grid.append(renderFamilyCard(family));
        });
    }

    function setSelectedVersion(familyId, versionId, refreshModal = false) {
        selectedVersionByFamily[familyId] = versionId;
        updateFamilyCard(familyId);
        if (refreshModal && activeModalFamilyId === familyId) {
            const family = getFamily(familyId);
            if (family) {
                $versionsModalBody.html(renderModalContent(family));
                const selected = getSelectedVersion(family);
                const compareLeft = getCompareLeftVersion(family, selected);
                loadCompareDiff(familyId, compareLeft.id, selected.id);
            }
        }
    }

    $grid.on('click', '.wf-versions-badge', function () {
        openVersionsModal($(this).data('family-id'));
    });

    $versionsModalBody.on('click', '.wf-version-item', function () {
        const familyId = $(this).data('family-id');
        const versionId = $(this).data('version-id');
        setSelectedVersion(familyId, versionId, true);
    });

    $versionsModalBody.on('change', '.wf-compare-left', function () {
        const familyId = $(this).data('family-id');
        const leftId = $(this).val();
        compareLeftByFamily[familyId] = leftId;
        const $right = $versionsModalBody.find(`.wf-compare-right[data-family-id="${familyId}"]`);
        loadCompareDiff(familyId, leftId, $right.val());
    });

    $versionsModalBody.on('change', '.wf-compare-right', function () {
        const familyId = $(this).data('family-id');
        const rightId = $(this).val();
        setSelectedVersion(familyId, rightId, true);
    });

    $versionsModal.on('hidden.bs.modal', function () {
        activeModalFamilyId = null;
    });

    $grid.on('click', '.delete-btn', function () {
        const graphId = $(this).data('id');
        const familyId = $(this).data('family-id');
        const graphName = $(this).data('name');
        if (!confirm(`Sure to delete workflow "${graphName}" (ID: ${graphId})?`)) return;

        $.ajax({
            url: `/graph/api/${encodeURIComponent(graphId)}`,
            type: 'DELETE',
            success: async function () {
                const family = families.find((item) => item.family_id === familyId);
                if (family) {
                    family.versions = (family.versions || []).filter((v) => v.id !== graphId);
                    family.version_count = family.versions.length;
                    if (!family.versions.length) {
                        families = families.filter((item) => item.family_id !== familyId);
                        delete selectedVersionByFamily[familyId];
                        delete compareLeftByFamily[familyId];
                        if (activeModalFamilyId === familyId) {
                            versionsModal.hide();
                        }
                    } else if (selectedVersionByFamily[familyId] === graphId) {
                        selectedVersionByFamily[familyId] = family.versions[family.versions.length - 1].id;
                    }
                } else {
                    await refreshFamilies();
                }
                loadGraphs($searchInput.val());
                if (activeModalFamilyId === familyId) {
                    const family = getFamily(familyId);
                    if (family) {
                        $versionsModalBody.html(renderModalContent(family));
                        const selected = getSelectedVersion(family);
                        const compareLeft = getCompareLeftVersion(family, selected);
                        loadCompareDiff(familyId, compareLeft.id, selected.id);
                    }
                }
            },
            error: function (xhr) {
                alert('Delete failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            },
        });
    });

    $grid.on('click', '.copy-btn', function () {
        const graphId = $(this).data('id');
        const graphName = $(this).data('name');
        const suggested = `${graphId}_copy`;
        const newId = (prompt(`Copy workflow "${graphName}"\nNew workflow ID:`, suggested) || '').trim();
        if (!newId) return;

        $.ajax({
            url: `/graph/api/${encodeURIComponent(graphId)}/copy`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ id: newId }),
            success: async function () {
                await refreshFamilies();
                const family = families.find((item) =>
                    (item.versions || []).some((version) => version.id === newId)
                );
                if (family) {
                    selectedVersionByFamily[family.family_id] = newId;
                }
                loadGraphs($searchInput.val());
            },
            error: function (xhr) {
                alert('Copy failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            },
        });
    });

    $searchInput.on('input', function () {
        loadGraphs($(this).val().trim());
    });

    loadGraphs();
});
