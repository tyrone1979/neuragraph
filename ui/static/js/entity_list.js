window.createEntityListPage = function createEntityListPage(config) {
    const {
        $grid,
        $noResults,
        $searchInput,
        $versionsModal,
        $versionsModalBody,
        $versionsModalLabel,
        apiListUrl,
        entityLabel,
        editUrl,
        copyUrl,
        deleteUrl,
        versionsUrl,
        compareUrl,
        renderCardExtra,
    } = config;

    const versionsModal = new bootstrap.Modal($versionsModal[0]);
    let items = [];
    let activeModalEntityId = null;
    const compareLeftByEntity = {};
    let modalVersions = [];

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

    function getItem(entityId) {
        return items.find((item) => item.id === entityId) || null;
    }

    function renderVersionOptions(selectedId) {
        return modalVersions
            .map((version) => {
                const note = version.change_note ? ` | ${version.change_note}` : '';
                const label = `${version.version}${note ? note : ''} (${formatTimestamp(version.created_at)})`;
                const selected = version.version === selectedId ? ' selected' : '';
                return `<option value="${escHtml(version.version)}"${selected}>${escHtml(label)}</option>`;
            })
            .join('');
    }

    async function loadCompareDiff(entityId, leftId, rightId) {
        const $diff = $(`#entity-diff-${entityId}`);
        if (!$diff.length) return;
        if (!leftId || !rightId) {
            $diff.html('<span class="text-muted">Select two versions to compare.</span>');
            return;
        }
        if (leftId === rightId) {
            $diff.html('<span class="text-muted">Select two different versions.</span>');
            return;
        }
        $diff.text('Loading diff...');
        try {
            const res = await fetch(compareUrl(entityId), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ left: leftId, right: rightId }),
            });
            const data = await res.json();
            if (!res.ok) {
                $diff.text(`Compare failed: ${data.error || 'unknown error'}`);
                return;
            }
            $diff.html(renderDiffHtml(data.diff || ''));
        } catch (err) {
            $diff.text(`Compare failed: ${err.message || err}`);
        }
    }

    function renderModalContent(entityId) {
        const item = getItem(entityId);
        const rightId = (modalVersions[0] || {}).version;
        const leftId = compareLeftByEntity[entityId] || (modalVersions[1] || modalVersions[0] || {}).version;
        const versionList = modalVersions
            .map((version) => {
                const note = version.change_note ? version.change_note : '';
                return `
                    <div class="wf-version-item static">
                        <div class="d-flex justify-content-between align-items-start gap-2">
                            <div>
                                <div class="wf-version-label">${escHtml(version.version)}</div>
                                <div class="wf-version-id">${escHtml(note || version.source || '')}</div>
                            </div>
                            <div class="wf-version-meta text-end">
                                <div>${escHtml(version.created_by || '')}</div>
                                <div>${escHtml(formatTimestamp(version.created_at))}</div>
                            </div>
                        </div>
                    </div>`;
            })
            .join('');

        return `
            <div class="wf-modal-family-meta mb-3">
                <div><strong>ID:</strong> <code>${escHtml(entityId)}</code></div>
                ${item && item.description ? `<div class="text-muted small mt-1">${escHtml(item.description)}</div>` : ''}
            </div>
            <div class="wf-section-title">Versions</div>
            <div class="wf-version-list mb-3">${versionList || '<p class="small text-muted mb-0 px-2 py-2">No version history yet.</p>'}</div>
            <div class="wf-diff-panel">
                <div class="wf-section-title">Compare versions</div>
                <div class="row g-2 mb-2">
                    <div class="col-md-6">
                        <label class="form-label small mb-1">Left</label>
                        <select class="form-select form-select-sm entity-compare-left"
                                data-entity-id="${escHtml(entityId)}">
                            ${renderVersionOptions(leftId)}
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small mb-1">Right</label>
                        <select class="form-select form-select-sm entity-compare-right"
                                data-entity-id="${escHtml(entityId)}">
                            ${renderVersionOptions(rightId)}
                        </select>
                    </div>
                </div>
                <div class="wf-section-title">Unified diff</div>
                <pre id="entity-diff-${escHtml(entityId)}" class="wf-diff-pre mb-0"></pre>
            </div>`;
    }

    async function openVersionsModal(entityId) {
        const item = getItem(entityId);
        if (!item) return;
        activeModalEntityId = entityId;
        $versionsModalLabel.text(`${item.name || entityId} — Versions`);
        $versionsModalBody.html('<p class="text-muted mb-0">Loading versions...</p>');
        versionsModal.show();
        try {
            const res = await fetch(versionsUrl(entityId));
            const data = await res.json();
            modalVersions = data.versions || [];
            if (!compareLeftByEntity[entityId]) {
                compareLeftByEntity[entityId] = (modalVersions[1] || modalVersions[0] || {}).version;
            }
            $versionsModalBody.html(renderModalContent(entityId));
            const leftId = $versionsModalBody.find('.entity-compare-left').val();
            const rightId = $versionsModalBody.find('.entity-compare-right').val();
            if (leftId && rightId) {
                loadCompareDiff(entityId, leftId, rightId);
            }
        } catch (err) {
            $versionsModalBody.html(`<p class="text-danger mb-0">Failed to load versions: ${escHtml(err.message || err)}</p>`);
        }
    }

    function renderCardFooter(item) {
        const title = item.name || item.id;
        return `
            <div class="card-footer bg-transparent d-flex justify-content-between">
                <a href="${editUrl(item.id)}"
                   class="btn btn-sm btn-outline-primary">Edit</a>
                <div class="d-flex gap-1">
                    <button class="btn btn-sm btn-outline-secondary copy-btn"
                            data-id="${escHtml(item.id)}"
                            data-name="${escHtml(title)}">Copy</button>
                    <button class="btn btn-sm btn-outline-danger delete-btn"
                            data-id="${escHtml(item.id)}"
                            data-name="${escHtml(title)}">Delete</button>
                </div>
            </div>`;
    }

    function renderVersionBadge(item) {
        const versionCount = Number(item.version_count || 0);
        if (versionCount <= 0) return '';
        const label = versionCount > 1
            ? `${versionCount} versions`
            : (item.latest_version || '1 version');
        return `<button type="button"
                       class="badge bg-info ms-2 wf-versions-badge"
                       data-entity-id="${escHtml(item.id)}"
                       title="View versions">${escHtml(label)}</button>`;
    }

    function renderCard(item) {
        const title = item.name || item.id || 'Unnamed';
        const versionBadge = renderVersionBadge(item);
        const extra = renderCardExtra ? renderCardExtra(item, escHtml) : '';

        return `
            <div class="col">
                <div class="card h-100 shadow-sm wf-family-card" data-entity-id="${escHtml(item.id)}">
                    <div class="card-body d-flex flex-column">
                        <div class="wf-card-header mb-2">
                            <h5 class="card-title">${escHtml(title)}${versionBadge}</h5>
                            <div class="wf-family-meta">
                                <div><strong>ID:</strong> <code>${escHtml(item.id)}</code></div>
                                ${extra}
                            </div>
                        </div>
                    </div>
                    ${renderCardFooter(item)}
                </div>
            </div>`;
    }

    async function refreshItems() {
        try {
            const res = await fetch(apiListUrl);
            if (res.ok) {
                items = await res.json();
            }
        } catch (_err) {
            // Keep current items if refresh fails.
        }
    }

    function renderGroupHeader(groupKey, count) {
        const label = (config.groupLabels && config.groupLabels[groupKey]) || groupKey;
        const badge = (config.groupBadges && config.groupBadges[groupKey]) || 'bg-secondary';
        return `
            <div class="col-12">
                <div class="entity-group-header border-bottom pb-2 mb-1 mt-2">
                    <span class="badge ${badge} me-2">${escHtml(label)}</span>
                    <span class="text-muted small">${count} agent${count === 1 ? '' : 's'}</span>
                </div>
            </div>`;
    }

    function groupKeyForItem(item) {
        if (!config.groupByField) return '';
        const raw = item[config.groupByField];
        return String(raw || config.groupDefaultKey || 'Other');
    }

    function loadItems(query = '') {
        const q = (query || '').toLowerCase().trim();
        const filtered = items.filter((item) => {
            if (!q) return true;
            const haystack = [
                item.name,
                item.id,
                item.description,
                item.type,
                item.model,
            ].join(' ').toLowerCase();
            return haystack.includes(q);
        });

        $grid.empty();
        if (!filtered.length) {
            $noResults.removeClass('d-none');
            return;
        }
        $noResults.addClass('d-none');

        if (config.groupByField) {
            const buckets = new Map();
            filtered.forEach((item) => {
                const key = groupKeyForItem(item);
                if (!buckets.has(key)) buckets.set(key, []);
                buckets.get(key).push(item);
            });
            const order = Array.isArray(config.groupOrder) ? config.groupOrder : [];
            const extraKeys = [...buckets.keys()]
                .filter((key) => !order.includes(key))
                .sort((a, b) => a.localeCompare(b));
            [...order, ...extraKeys].forEach((groupKey) => {
                const groupItems = buckets.get(groupKey);
                if (!groupItems || !groupItems.length) return;
                groupItems.sort((a, b) => String(a.id || '').localeCompare(String(b.id || '')));
                $grid.append(renderGroupHeader(groupKey, groupItems.length));
                groupItems.forEach((item) => {
                    $grid.append(renderCard(item));
                });
            });
            return;
        }

        filtered.forEach((item) => {
            $grid.append(renderCard(item));
        });
    }

    $grid.on('click', '.wf-versions-badge', function () {
        openVersionsModal($(this).data('entity-id'));
    });

    $versionsModalBody.on('change', '.entity-compare-left', function () {
        const entityId = $(this).data('entity-id');
        compareLeftByEntity[entityId] = $(this).val();
        const rightId = $versionsModalBody.find(`.entity-compare-right[data-entity-id="${entityId}"]`).val();
        loadCompareDiff(entityId, $(this).val(), rightId);
    });

    $versionsModalBody.on('change', '.entity-compare-right', function () {
        const entityId = $(this).data('entity-id');
        const leftId = $versionsModalBody.find(`.entity-compare-left[data-entity-id="${entityId}"]`).val();
        loadCompareDiff(entityId, leftId, $(this).val());
    });

    $versionsModal.on('hidden.bs.modal', function () {
        activeModalEntityId = null;
        modalVersions = [];
    });

    $grid.on('click', '.delete-btn', function () {
        const entityId = $(this).data('id');
        const entityName = $(this).data('name');
        if (!confirm(`Sure to delete ${entityLabel} "${entityName}" (ID: ${entityId})?`)) return;

        $.ajax({
            url: deleteUrl(entityId),
            type: 'DELETE',
            success: async function () {
                items = items.filter((item) => item.id !== entityId);
                delete compareLeftByEntity[entityId];
                if (activeModalEntityId === entityId) {
                    versionsModal.hide();
                }
                loadItems($searchInput.val().trim());
            },
            error: function (xhr) {
                alert('Delete failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            },
        });
    });

    $grid.on('click', '.copy-btn', function () {
        const entityId = $(this).data('id');
        const entityName = $(this).data('name');
        const suggested = `${entityId}_copy`;
        const newId = (prompt(`Copy ${entityLabel} "${entityName}"\nNew ID:`, suggested) || '').trim();
        if (!newId) return;

        $.ajax({
            url: copyUrl(entityId),
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ id: newId }),
            success: async function () {
                await refreshItems();
                loadItems($searchInput.val().trim());
                window.location.href = editUrl(newId);
            },
            error: function (xhr) {
                alert('Copy failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            },
        });
    });

    $searchInput.on('input', function () {
        loadItems($(this).val().trim());
    });

    return {
        async init(initialItems) {
            items = Array.isArray(initialItems) ? initialItems : [];
            if (!items.length) {
                await refreshItems();
            }
            loadItems();
        },
        reload: refreshItems,
    };
};
