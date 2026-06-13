(function () {
    const $ = window.django && window.django.jQuery ? window.django.jQuery : window.jQuery;
    if (!$) return;

    let draggedColumn = null;

    const ICON_PATHS = {
        addFilter: '/static/superfilter/icons/add-filter.svg',
        columns: '/static/superfilter/icons/columns.svg',
        reload: '/static/superfilter/icons/reload.svg',
        trash: '/static/superfilter/icons/trash.svg',
        close: '/static/superfilter/icons/x-close.svg',
    };

    function iconButtonContent(iconName, label) {
        const fragment = document.createDocumentFragment();
        fragment.appendChild(el('img', {
            src: ICON_PATHS[iconName],
            alt: '',
            class: `superfilter-icon superfilter-icon-${iconName}`,
            'aria-hidden': 'true'
        }));
        if (label) {
            fragment.appendChild(el('span', { class: 'superfilter-visually-hidden' }, label));
        }
        return fragment;
    }

    function joinUrl(base, suffix) {
        return (base.endsWith("/") ? base : base + "/") + suffix;
    }

    function getChangeListBasePath() {
        const path = window.location.pathname;
        return path.endsWith("/") ? path : path + "/";
    }

    function el(tag, attrs, text) {
        const elem = document.createElement(tag);
        if (attrs) Object.keys(attrs).forEach(k => elem.setAttribute(k, attrs[k]));
        if (text !== undefined && text !== null) elem.textContent = text;
        return elem;
    }

    function getMountTarget() {
        return document.querySelector("#changelist");
    }

    function renderLoadingShell() {
        const target = getMountTarget();
        if (!target || document.querySelector('.superfilter-container.superfilter-loading')) return;
        const container = el('div', { class: 'superfilter-container superfilter-loading' });
        const bar = el('div', { class: 'superfilter-searchbar superfilter-searchbar-loading' });
        const addBtn = el('button', { type: 'button', class: 'superfilter-add-btn', disabled: 'disabled', title: 'Ajouter un filtre', 'aria-label': 'Ajouter un filtre' });
        addBtn.appendChild(iconButtonContent('addFilter', 'Ajouter un filtre'));
        const hint = el('span', { class: 'superfilter-empty-hint' }, 'Chargement des filtres...');
        const actions = el('div', { class: 'superfilter-actions' });
        const applyBtn = el('button', { type: 'button', class: 'superfilter-btn primary superfilter-split-main', disabled: 'disabled' }, 'Appliquer');
        const menuBtn = el('button', { type: 'button', class: 'superfilter-btn primary superfilter-split-toggle' }, '▾');
        const resetBtn = el('button', { type: 'button', class: 'superfilter-btn superfilter-icon-btn', title: 'Réinitialiser', 'aria-label': 'Réinitialiser' });
        resetBtn.appendChild(iconButtonContent('reload', 'Réinitialiser'));
        const split = el('div', { class: 'superfilter-split-btn' });
        split.appendChild(applyBtn);
        split.appendChild(menuBtn);
        actions.appendChild(split);
        actions.appendChild(resetBtn);
        bar.appendChild(addBtn);
        bar.appendChild(hint);
        bar.appendChild(actions);
        const columnsToggle = el('button', { type: 'button', class: 'superfilter-columns-toggle-link', disabled: 'disabled', title: 'Colonnes', 'aria-label': 'Colonnes' });
        columnsToggle.appendChild(iconButtonContent('columns', 'Colonnes'));
        bar.appendChild(columnsToggle);
        container.appendChild(bar);
        target.before(container);
    }

    function removeLoadingShell() {
        document.querySelectorAll('.superfilter-container.superfilter-loading').forEach(node => node.remove());
    }

    function normalizeRules(rules) {
        return JSON.stringify(Array.isArray(rules) ? rules : []);
    }

    function normalizeColumns(columns) {
        return JSON.stringify(Array.isArray(columns) ? columns : []);
    }

    function getOperatorLabel(op) {
        const labels = {
            set: "est défini",
            not_set: "n'est pas défini",
            eq: "est égal à",
            neq: "est différent de",
            contains: "contient",
            not_contains: "ne contient pas",
            gt: ">",
            lt: "<",
            gte: ">=",
            lte: "<=",
            true: "est vrai",
            false: "est faux",
            empty: "vide",
            in: "égal à (multiple)",
            not_in: "différent de (multiple)",
            before: "est avant",
            after: "est après",
            between: "est entre",
        };
        return labels[op] || op;
    }

    function formatBadgeValue(field, rule) {
        const op = rule.op;
        const value = rule.value;

        if (["set", "not_set", "true", "false", "empty"].includes(op)) return null;
        if (field.kind === "choice") return null;
        if (field.kind === "fk" && Array.isArray(value)) return `(${value.length})`;
        if (["in", "not_in"].includes(op) && Array.isArray(value)) return `(${value.length})`;
        if (["date", "datetime"].includes(field.kind) && op === "between" && Array.isArray(value)) {
            return `${value[0] || "-"} -> ${value[1] || "-"}`;
        }
        if (typeof value === "string" && value.length > 30) return value.substring(0, 27) + "...";
        return value ? String(value) : null;
    }

    const NO_VALUE_OPERATORS = ["set", "not_set", "true", "false", "empty"];
    const SAVED_FILTERS_VISIBLE_COUNT = 5;

    class SuperFilterUI {
        constructor(meta) {
            this.meta = meta;
            this.rules = Array.isArray(meta.rules) ? [...meta.rules] : [];
            this.defaultColumns = Array.isArray(meta.columns) ? meta.columns.map(col => ({ ...col })) : [];
            this.initialSelectedCount = Array.isArray(meta.selectedColumns) && meta.selectedColumns.length
                ? meta.selectedColumns.filter(path => this.getDefaultColumns().includes(path)).length
                : this.getDefaultColumns().length;
            this.columnOrder = this.buildColumnOrder(Array.isArray(meta.selectedColumns) ? meta.selectedColumns : []);
            this.lastAppliedRules = normalizeRules(this.rules);
            this.lastAppliedColumns = normalizeColumns(this.getSelectedColumns());
            this.savedFilters = Array.isArray(meta.savedFilters) ? [...meta.savedFilters] : [];
            this.columnsExpanded = this.shouldColumnsStartExpanded();
            this.mount();
        }

        shouldColumnsStartExpanded() {
            return this.isColumnCustomizationApplied();
        }

        isColumnCustomizationApplied() {
            const defaultColumns = this.getDefaultColumns();
            const currentColumns = this.getSelectedColumns();
            return normalizeColumns(currentColumns) !== normalizeColumns(defaultColumns);
        }

        refreshColumnsVisibility() {
            if (this.columnsContainer) {
                this.columnsContainer.style.display = this.columnsExpanded ? '' : 'none';
            }
            if (this.columnsToggleLink) {
                this.columnsToggleLink.innerHTML = '';
                this.columnsToggleLink.appendChild(iconButtonContent('columns', 'Colonnes'));
                this.columnsToggleLink.classList.toggle('active', !!this.columnsExpanded);
            }
        }

        mount() {
            const target = getMountTarget();
            if (!target) return;

            removeLoadingShell();
            this.container = el("div", { class: "superfilter-container" });
            this.buildSearchBar();
            target.before(this.container);
        }

        buildSearchBar() {
            const searchbar = el("div", { class: "superfilter-searchbar" });

            const addWrapper = el("div", { class: "superfilter-add-wrapper" });
            const addBtn = el("button", { type: "button", class: "superfilter-add-btn", title: 'Ajouter un filtre', 'aria-label': 'Ajouter un filtre' });
            addBtn.appendChild(iconButtonContent('addFilter', 'Ajouter un filtre'));
            const dropdown = el("div", { class: "superfilter-dropdown", style: "display:none;" });

            addBtn.addEventListener("click", (e) => {
                e.preventDefault();
                dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
            });

            this.meta.fields.forEach(field => {
                const item = el("button", { type: "button", class: "superfilter-dropdown-item" });
                const content = el("div", { class: "superfilter-dropdown-item-content" });
                content.appendChild(el("span", { class: "superfilter-dropdown-item-label" }, field.label));
                content.appendChild(el("span", { class: "superfilter-dropdown-item-hint" }, `(${field.path})`));
                item.appendChild(content);

                const submenu = el("div", { class: "superfilter-operator-submenu" });
                field.operators.forEach(op => {
                    const opBtn = el("button", { type: "button", class: "superfilter-operator-item" });
                    opBtn.appendChild(el("span", { class: "superfilter-operator-item-field" }, field.label));
                    opBtn.appendChild(el("span", { class: "superfilter-operator-item-op" }, getOperatorLabel(op) + (NO_VALUE_OPERATORS.includes(op) ? "" : " ...")));
                    opBtn.addEventListener("click", (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        dropdown.style.display = "none";
                        if (NO_VALUE_OPERATORS.includes(op)) {
                            this.rules.push({ field: field.path, op, value: null });
                            this.refreshUI();
                        } else {
                            this.openModal(field, op);
                        }
                    });
                    submenu.appendChild(opBtn);
                });
                item.appendChild(submenu);

                dropdown.appendChild(item);
            });

            document.addEventListener("click", (e) => {
                if (!addWrapper.contains(e.target)) dropdown.style.display = "none";
                if (this.applyDropdown && !this.applySplit?.contains(e.target)) this.applyDropdown.style.display = "none";
                if (this.savedMoreMenu && !this.savedMoreWrap?.contains(e.target)) this.savedMoreMenu.style.display = 'none';
            });

            addWrapper.appendChild(addBtn);
            addWrapper.appendChild(dropdown);
            searchbar.appendChild(addWrapper);

            const badgesContainer = el("div", { style: "display:flex; gap:8px; flex-wrap:wrap; flex-grow:1;" });
            this.renderBadges(badgesContainer);
            searchbar.appendChild(badgesContainer);

            this.emptyHint = el("span", { class: "superfilter-empty-hint" }, "Aucun filtre");
            if (this.rules.length === 0) {
                searchbar.appendChild(this.emptyHint);
            }

            const actions = el("div", { class: "superfilter-actions" });
            const applySplit = el("div", { class: "superfilter-split-btn" });
            const applyBtn = el("button", { type: "button", class: "superfilter-btn primary superfilter-split-main", disabled: 'disabled' }, "Appliquer");
            const menuBtn = el("button", { type: "button", class: "superfilter-btn primary superfilter-split-toggle", }, "▾");
            const applyDropdown = el("div", { class: "superfilter-apply-menu", style: "display:none;" });
            const saveBtn = el("button", { type: "button", class: "superfilter-apply-menu-item" }, "Enregistrer");
            const resetBtn = el('button', { type: 'button', class: 'superfilter-btn superfilter-icon-btn', title: 'Réinitialiser', 'aria-label': 'Réinitialiser' });
            resetBtn.appendChild(iconButtonContent('reload', 'Réinitialiser'));

            applyBtn.addEventListener("click", () => this.apply());
            menuBtn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                applyDropdown.style.display = applyDropdown.style.display === "none" ? "block" : "none";
            });
            saveBtn.addEventListener("click", (e) => {
                e.preventDefault();
                applyDropdown.style.display = "none";
                this.openSaveModal();
            });
            resetBtn.addEventListener("click", () => this.reset());

            applyDropdown.appendChild(saveBtn);
            applySplit.appendChild(applyBtn);
            applySplit.appendChild(menuBtn);
            applySplit.appendChild(applyDropdown);
            actions.appendChild(applySplit);
            actions.appendChild(resetBtn);
            searchbar.appendChild(actions);

            this.container.appendChild(searchbar);
            this.badgesContainer = badgesContainer;
            this.applySplit = applySplit;
            this.applyDropdown = applyDropdown;
            this.applyBtn = applyBtn;
            this.resetBtn = resetBtn;

            this.columnsToggleLink = el('button', { type: 'button', class: 'superfilter-columns-toggle-link', title: 'Colonnes', 'aria-label': 'Colonnes' });
            this.columnsToggleLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.columnsExpanded = !this.columnsExpanded;
                this.refreshColumnsVisibility();
            });
            searchbar.appendChild(this.columnsToggleLink);

            this.columnsContainer = el('div', { class: 'superfilter-columns-row' });
            searchbar.appendChild(this.columnsContainer);
            this.renderColumnsRow();
            this.refreshColumnsVisibility();

            this.savedFiltersContainer = el('div', { class: 'superfilter-saved-list' });
            this.container.appendChild(this.savedFiltersContainer);
            this.renderSavedFilters();
            this.updateApplyButtonState();
        }

        createSavedTag(saved, compact = false) {
            const tag = el('div', { class: `superfilter-saved-tag-wrap${compact ? ' compact' : ''}` });
            const applyBtn = el('button', { type: 'button', class: `superfilter-saved-tag${compact ? ' compact' : ''}` }, saved.name);
            const deleteBtn = el('button', { type: 'button', class: 'superfilter-saved-tag-remove', title: 'Supprimer', 'aria-label': 'Supprimer' });
            deleteBtn.appendChild(iconButtonContent('trash', 'Supprimer'));

            applyBtn.addEventListener('click', () => {
                this.rules = Array.isArray(saved.rules) ? [...saved.rules] : [];
                this.columnOrder = this.buildColumnOrder(Array.isArray(saved.columns) ? saved.columns : []);
                this.columnsExpanded = this.isColumnCustomizationApplied();
                this.refreshUI();
            });
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.openDeleteSavedFilterDialog(saved);
            });

            tag.appendChild(applyBtn);
            tag.appendChild(deleteBtn);
            return tag;
        }

        renderSavedFilters() {
            if (!this.savedFiltersContainer) return;
            this.savedFiltersContainer.innerHTML = '';
            if (!this.savedFilters.length) return;

            const visible = this.savedFilters.slice(0, SAVED_FILTERS_VISIBLE_COUNT);
            const hidden = this.savedFilters.slice(SAVED_FILTERS_VISIBLE_COUNT);

            visible.forEach(saved => {
                this.savedFiltersContainer.appendChild(this.createSavedTag(saved));
            });

            if (hidden.length) {
                const moreWrap = el('div', { class: 'superfilter-saved-more-wrap' });
                const moreBtn = el('button', { type: 'button', class: 'superfilter-saved-more-link' }, 'More ...');
                const moreMenu = el('div', { class: 'superfilter-saved-more-menu', style: 'display:none;' });
                hidden.forEach(saved => {
                    moreMenu.appendChild(this.createSavedTag(saved, true));
                });
                moreBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    moreMenu.style.display = moreMenu.style.display === 'none' ? 'block' : 'none';
                });
                moreWrap.appendChild(moreBtn);
                moreWrap.appendChild(moreMenu);
                this.savedFiltersContainer.appendChild(moreWrap);
                this.savedMoreWrap = moreWrap;
                this.savedMoreMenu = moreMenu;
            }
        }

        getDefaultColumns() {
            return this.defaultColumns.map(col => col.path);
        }

        buildColumnOrder(selectedColumns) {
            const defaultPaths = this.getDefaultColumns();
            const selected = Array.isArray(selectedColumns) && selectedColumns.length
                ? selectedColumns.filter(path => defaultPaths.includes(path))
                : [...defaultPaths];
            const selectedSet = new Set(selected);
            const disabled = defaultPaths.filter(path => !selectedSet.has(path));
            this.selectedCount = selected.length || defaultPaths.length;
            return [...selected, ...disabled];
        }

        getSelectedCount() {
            return Math.max(1, Math.min(this.selectedCount || this.initialSelectedCount || this.getDefaultColumns().length, this.columnOrder.length));
        }

        getOrderedColumns() {
            const byPath = new Map(this.defaultColumns.map(col => [col.path, col]));
            return this.columnOrder
                .map(path => byPath.get(path))
                .filter(Boolean);
        }

        getSelectedColumns() {
            const selectedCount = this.getSelectedCount();
            return this.columnOrder.slice(0, selectedCount);
        }

        isColumnEnabled(path) {
            const selectedCount = this.getSelectedCount();
            const index = this.columnOrder.indexOf(path);
            return index !== -1 && index < selectedCount;
        }

        toggleColumn(path) {
            const selected = this.getSelectedColumns();
            const selectedSet = new Set(selected);
            if (selectedSet.has(path)) {
                if (selected.length <= 1) return;
                this.columnOrder = [...this.columnOrder.filter(col => col !== path), path];
                this.selectedCount = selected.length - 1;
            } else {
                const currentWithout = this.columnOrder.filter(col => col !== path);
                const disabledStart = selected.length;
                this.columnOrder = [
                    ...currentWithout.slice(0, disabledStart),
                    path,
                    ...currentWithout.slice(disabledStart),
                ];
                this.selectedCount = selected.length + 1;
            }
            this.refreshUI();
        }

        moveColumn(draggedPath, targetPath, placeAfter = false) {
            const selected = this.getSelectedColumns();
            if (!draggedPath || !targetPath || draggedPath === targetPath) return;
            if (!selected.includes(draggedPath) || !selected.includes(targetPath)) return;
            const selectedOnly = [...selected];
            const draggedIndex = selectedOnly.indexOf(draggedPath);
            const targetIndex = selectedOnly.indexOf(targetPath);
            if (draggedIndex === -1 || targetIndex === -1) return;
            const [moved] = selectedOnly.splice(draggedIndex, 1);
            let insertIndex = targetIndex;
            if (draggedIndex < targetIndex) {
                insertIndex = placeAfter ? targetIndex : targetIndex - 1;
            } else if (placeAfter) {
                insertIndex = targetIndex + 1;
            }
            selectedOnly.splice(Math.max(0, insertIndex), 0, moved);
            const disabled = this.columnOrder.filter(path => !selected.includes(path));
            this.columnOrder = [...selectedOnly, ...disabled];
            this.selectedCount = selectedOnly.length;
            this.refreshUI();
        }

        renderColumnsRow() {
            if (!this.columnsContainer) return;
            this.columnsContainer.innerHTML = '';

            const label = el('span', { class: 'superfilter-columns-label' }, 'Colonnes :');
            const bullets = el('span', { class: 'superfilter-columns-bullets' });
            const selectedColumns = this.getSelectedColumns();
            const selectedSet = new Set(selectedColumns);

            const clearDragStyles = () => {
                this.columnsContainer.querySelectorAll('.superfilter-column-bullet').forEach(node => {
                    node.classList.remove('drag-over-before');
                    node.classList.remove('drag-over-after');
                    node.classList.remove('drag-target-end');
                    node.classList.remove('dragging');
                });
                bullets.classList.remove('drag-target-end');
            };

            this.getOrderedColumns().forEach(column => {
                const enabled = selectedSet.has(column.path);
                const bullet = el('button', {
                    type: 'button',
                    class: `superfilter-column-bullet${enabled ? ' enabled' : ''}`,
                    draggable: enabled ? 'true' : 'false',
                    'data-path': column.path,
                    title: enabled ? 'Cliquer pour masquer, glisser pour réordonner' : 'Cliquer pour afficher',
                });
                const handle = el('span', { class: 'superfilter-column-handle', title: enabled ? 'Glisser pour réordonner' : '' }, '⋮⋮');
                const text = el('span', { class: 'superfilter-column-text' }, column.label);
                bullet.appendChild(handle);
                bullet.appendChild(text);

                bullet.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.toggleColumn(column.path);
                });

                bullet.addEventListener('dragstart', (e) => {
                    if (!enabled) {
                        e.preventDefault();
                        return;
                    }
                    draggedColumn = column.path;
                    bullet.classList.add('dragging');
                    if (e.dataTransfer) {
                        e.dataTransfer.effectAllowed = 'move';
                        e.dataTransfer.setData('text/plain', column.path);
                    }
                });
                bullet.addEventListener('dragend', () => {
                    clearDragStyles();
                    window.setTimeout(() => {
                        draggedColumn = null;
                    }, 0);
                });
                bullet.addEventListener('dragover', (e) => {
                    if (!enabled || !draggedColumn || draggedColumn === column.path || !selectedSet.has(draggedColumn)) return;
                    e.preventDefault();
                    clearDragStyles();
                    const rect = bullet.getBoundingClientRect();
                    const placeAfter = e.clientX > rect.left + rect.width / 2;
                    bullet.classList.add(placeAfter ? 'drag-over-after' : 'drag-over-before');
                });
                bullet.addEventListener('dragleave', () => {
                    bullet.classList.remove('drag-over-before');
                    bullet.classList.remove('drag-over-after');
                });
                bullet.addEventListener('drop', (e) => {
                    if (!enabled || !draggedColumn || draggedColumn === column.path || !selectedSet.has(draggedColumn)) return;
                    e.preventDefault();
                    const rect = bullet.getBoundingClientRect();
                    const placeAfter = e.clientX > rect.left + rect.width / 2;
                    clearDragStyles();
                    this.moveColumn(draggedColumn, column.path, placeAfter);
                });

                bullets.appendChild(bullet);
            });

            bullets.addEventListener('dragover', (e) => {
                if (!draggedColumn || !selectedSet.has(draggedColumn)) return;
                e.preventDefault();
                const enabledBulletNodes = [...bullets.querySelectorAll('.superfilter-column-bullet.enabled')];
                if (!enabledBulletNodes.length) return;
                const lastBullet = enabledBulletNodes[enabledBulletNodes.length - 1];
                const lastRect = lastBullet.getBoundingClientRect();
                clearDragStyles();
                if (e.clientX > lastRect.right) {
                    bullets.classList.add('drag-target-end');
                    lastBullet.classList.add('drag-target-end');
                }
            });
            bullets.addEventListener('drop', (e) => {
                if (!draggedColumn || !selectedSet.has(draggedColumn)) return;
                e.preventDefault();
                const enabledBulletNodes = [...bullets.querySelectorAll('.superfilter-column-bullet.enabled')];
                if (!enabledBulletNodes.length) return;
                const lastBullet = enabledBulletNodes[enabledBulletNodes.length - 1];
                const lastRect = lastBullet.getBoundingClientRect();
                const dropAtEnd = e.clientX > lastRect.right;
                clearDragStyles();
                if (dropAtEnd) {
                    this.moveColumn(draggedColumn, lastBullet.getAttribute('data-path'), true);
                }
            });

            this.columnsContainer.appendChild(label);
            this.columnsContainer.appendChild(bullets);
        }

        renderBadges(container) {
            container.innerHTML = "";
            this.rules.forEach((rule, idx) => {
                const field = this.meta.fields.find(f => f.path === rule.field);
                if (!field) return;

                const badge = el("div", { class: "superfilter-badge", style: "cursor:pointer;" });
                badge.appendChild(el("span", { class: "superfilter-badge-label" }, field.label));
                badge.appendChild(el("span", { class: "superfilter-badge-op" }, getOperatorLabel(rule.op)));

                const valueText = formatBadgeValue(field, rule);
                if (valueText) {
                    badge.appendChild(el("span", { class: "superfilter-badge-value" }, valueText));
                }

                const removeBtn = el("button", { type: 'button', class: "superfilter-badge-remove", title: 'Supprimer ce filtre', 'aria-label': 'Supprimer ce filtre' });
                removeBtn.appendChild(iconButtonContent('close', 'Supprimer ce filtre'));
                removeBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    this.rules.splice(idx, 1);
                    this.refreshUI();
                });

                badge.addEventListener("click", () => this.openModal(field, rule.op, idx));
                badge.appendChild(removeBtn);
                container.appendChild(badge);
            });
        }

        openDeleteSavedFilterDialog(saved) {
            const overlay = el('div', { class: 'superfilter-overlay' });
            const modal = el('div', { class: 'superfilter-modal superfilter-save-modal' });
            const header = el('div', { class: 'superfilter-modal-header' });
            header.appendChild(el('div', { class: 'superfilter-modal-title' }, 'Supprimer le filtre'));
            const closeBtn = el('button', { type: 'button', class: 'superfilter-modal-close', title: 'Fermer', 'aria-label': 'Fermer' });
            closeBtn.appendChild(iconButtonContent('close', 'Fermer'));

            const body = el('div', { class: 'superfilter-modal-body' });
            body.appendChild(el('div', {}, `Supprimer "${saved.name}" ?`));

            const footer = el('div', { class: 'superfilter-modal-footer' });
            const cancelBtn = el('button', { type: 'button', class: 'superfilter-btn' }, 'Annuler');
            const deleteBtn = el('button', { type: 'button', class: 'superfilter-btn primary' }, 'Supprimer');
            footer.appendChild(cancelBtn);
            footer.appendChild(deleteBtn);

            modal.appendChild(header);
            modal.appendChild(body);
            modal.appendChild(footer);
            overlay.appendChild(modal);

            const close = () => overlay.remove();
            closeBtn.addEventListener('click', close);
            cancelBtn.addEventListener('click', close);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
            deleteBtn.addEventListener('click', () => this.deleteSavedFilter(saved.id, close));

            document.body.appendChild(overlay);
        }

        openSaveModal() {
            const overlay = el('div', { class: 'superfilter-overlay' });
            const modal = el('div', { class: 'superfilter-modal superfilter-save-modal' });
            const header = el('div', { class: 'superfilter-modal-header' });
            header.appendChild(el('div', { class: 'superfilter-modal-title' }, 'Enregistrer le filtre'));
            const closeBtn = el('button', { type: 'button', class: 'superfilter-modal-close', title: 'Fermer', 'aria-label': 'Fermer' });
            closeBtn.appendChild(iconButtonContent('close', 'Fermer'));

            const body = el('div', { class: 'superfilter-modal-body' });
            const nameInput = el('input', { type: 'text', class: 'superfilter-input', placeholder: 'Nom du filtre' });
            body.appendChild(nameInput);

            const footer = el('div', { class: 'superfilter-modal-footer' });
            const cancelBtn = el('button', { type: 'button', class: 'superfilter-btn' }, 'Annuler');
            const saveBtn = el('button', { type: 'button', class: 'superfilter-btn primary' }, 'Enregistrer');
            footer.appendChild(cancelBtn);
            footer.appendChild(saveBtn);

            modal.appendChild(header);
            modal.appendChild(body);
            modal.appendChild(footer);
            overlay.appendChild(modal);

            const setSavingState = (isSaving) => {
                saveBtn.disabled = isSaving;
                nameInput.disabled = isSaving;
                cancelBtn.disabled = isSaving;
                saveBtn.textContent = isSaving ? 'Enregistrement...' : 'Enregistrer';
            };
            const submit = () => this.saveCurrentFilter(nameInput.value, close, setSavingState);
            const close = () => overlay.remove();
            closeBtn.addEventListener('click', close);
            cancelBtn.addEventListener('click', close);
            overlay.addEventListener('click', (e) => { if (e.target === overlay && !saveBtn.disabled) close(); });
            saveBtn.addEventListener('click', submit);
            nameInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submit();
                }
            });

            document.body.appendChild(overlay);
            nameInput.focus();
        }

        saveCurrentFilter(name, onDone, setSavingState = null) {
            const trimmedName = (name || '').trim();
            if (!trimmedName || !this.meta.saveUrl) return;

            const saveUrl = joinUrl(getChangeListBasePath(), this.meta.saveUrl);
            const payload = new URLSearchParams();
            payload.append('name', trimmedName);
            payload.append(this.meta.param, JSON.stringify(this.rules));
            payload.append(this.meta.columnsParam, JSON.stringify(this.getSelectedColumns()));
            if (setSavingState) setSavingState(true);

            $.ajax({
                url: saveUrl,
                method: 'POST',
                data: payload.toString(),
                contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
                headers: { 'X-CSRFToken': this.getCsrfToken() },
                success: (data) => {
                    this.savedFilters = Array.isArray(data.savedFilters) ? data.savedFilters : this.savedFilters;
                    this.renderSavedFilters();
                    if (onDone) onDone();
                },
                error: () => {
                    if (setSavingState) setSavingState(false);
                }
            });
        }

        deleteSavedFilter(id, onDone) {
            if (!this.meta.deleteUrlTemplate) return;
            const deleteUrl = joinUrl(getChangeListBasePath(), this.meta.deleteUrlTemplate.replace('__ID__', String(id)));
            $.ajax({
                url: deleteUrl,
                method: 'POST',
                headers: { 'X-CSRFToken': this.getCsrfToken() },
                success: (data) => {
                    this.savedFilters = Array.isArray(data.savedFilters) ? data.savedFilters : [];
                    this.renderSavedFilters();
                    if (onDone) onDone();
                }
            });
        }

        getCsrfToken() {
            const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
            return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
        }

        openModal(field, preSelectedOp, editIdx = null) {
            const existingRule = editIdx !== null ? this.rules[editIdx] : null;

            const overlay = el("div", { class: "superfilter-overlay" });
            const modal = el("div", { class: "superfilter-modal" });

            const header = el("div", { class: "superfilter-modal-header" });
            header.appendChild(el("div", { class: "superfilter-modal-title" }, `Filtrer: ${field.label}`));
            const closeBtn = el("button", { type: "button", class: "superfilter-modal-close" }, "x");
            closeBtn.appendChild(iconButtonContent('close', 'Fermer'));

            const body = el("div", { class: "superfilter-modal-body" });

            const opGroup = el("div", { class: "superfilter-form-group" });
            const opSelect = el("select", { class: "superfilter-select" });
            field.operators.forEach(op => {
                const opt = el("option", { value: op }, getOperatorLabel(op));
                if (preSelectedOp && op === preSelectedOp) opt.selected = true;
                opSelect.appendChild(opt);
            });
            if (preSelectedOp && opSelect.value !== preSelectedOp) opSelect.value = preSelectedOp;
            opGroup.appendChild(opSelect);
            body.appendChild(opGroup);

            const valueContainer = el("div", { class: "superfilter-form-group" });
            body.appendChild(valueContainer);

            let getEditorValue = () => null;
            let setEditorValue = (_v) => {};

            const updateValueEditor = (initialValue = undefined) => {
                const op = opSelect.value;
                valueContainer.innerHTML = "";
                getEditorValue = () => null;
                setEditorValue = (_v) => {};

                if (NO_VALUE_OPERATORS.includes(op)) {
                    valueContainer.appendChild(el("div", { style: "color:#999; font-size:12px; padding:4px 0;" }, "Aucune valeur requise"));
                    return;
                }

                if (field.kind === "choice") {
                    const select = el("select", { class: "superfilter-select", multiple: "multiple" });
                    (field.choices || []).forEach(choice => {
                        select.appendChild(new Option(choice.label, String(choice.value), false, false));
                    });
                    valueContainer.appendChild(select);
                    if ($.fn.select2) $(select).select2({ width: "100%", dropdownParent: $(modal) });
                    getEditorValue = () => $(select).val() || [];
                    setEditorValue = (v) => {
                        if (!Array.isArray(v)) return;
                        [...select.options].forEach(o => { o.selected = v.includes(o.value); });
                        if ($.fn.select2) $(select).trigger("change");
                    };
                    if (initialValue !== undefined) setEditorValue(initialValue);
                    return;
                }

                if (["date", "datetime"].includes(field.kind)) {
                    const inputType = field.inputType || (field.kind === "datetime" ? "datetime-local" : "date");
                    if (op === "between") {
                        const col = el("div", { style: "display:flex;flex-direction:column;gap:8px;" });
                        const start = el("input", { type: inputType, class: "superfilter-input" });
                        const end = el("input", { type: inputType, class: "superfilter-input" });
                        col.appendChild(start);
                        col.appendChild(end);
                        valueContainer.appendChild(col);
                        getEditorValue = () => [start.value, end.value];
                        setEditorValue = (v) => {
                            if (Array.isArray(v) && v.length >= 2) {
                                start.value = v[0] || "";
                                end.value = v[1] || "";
                            }
                        };
                    } else {
                        const input = el("input", { type: inputType, class: "superfilter-input" });
                        valueContainer.appendChild(input);
                        getEditorValue = () => input.value;
                        setEditorValue = (v) => { if (v != null) input.value = String(v); };
                    }
                    if (initialValue !== undefined) setEditorValue(initialValue);
                    return;
                }

                if (field.kind === "fk") {
                    const select = el("select", { class: "superfilter-select", multiple: "multiple" });
                    valueContainer.appendChild(select);

                    const tools = el("div", { style: "margin-top:10px; display:flex; gap:8px;" });
                    const selectAllBtn = el("button", { type: "button", class: "superfilter-btn" }, "Tout selectionner");
                    const clearBtn = el("button", { type: "button", class: "superfilter-btn" }, "Vider");
                    tools.appendChild(selectAllBtn);
                    tools.appendChild(clearBtn);
                    valueContainer.appendChild(tools);

                    const fkUrl = joinUrl(getChangeListBasePath(), this.meta.fkOptionsUrl);
                    if ($.fn.select2) {
                        $(select).select2({
                            width: "100%",
                            dropdownParent: $(modal),
                            ajax: {
                                url: fkUrl,
                                delay: 200,
                                data: params => ({ field: field.path, q: params.term || "", page: params.page || 1 }),
                                processResults: data => ({
                                    results: data.results || [],
                                    pagination: data.pagination || { more: false }
                                })
                            }
                        });
                    }

                    selectAllBtn.addEventListener("click", () => {
                        $.getJSON(fkUrl, { field: field.path, all: 1 }, data => {
                            const existing = new Set($(select).val() || []);
                            (data.results || []).forEach(item => {
                                if (!existing.has(String(item.id))) {
                                    select.appendChild(new Option(item.text, String(item.id), true, true));
                                }
                            });
                            if ($.fn.select2) $(select).trigger("change");
                        });
                    });

                    clearBtn.addEventListener("click", () => { $(select).val([]).trigger("change"); });
                    getEditorValue = () => $(select).val() || [];
                    setEditorValue = (v) => {
                        if (!Array.isArray(v)) return;
                        v.forEach(id => {
                            if (!select.querySelector(`option[value="${id}"]`)) {
                                select.appendChild(new Option(String(id), String(id), true, true));
                            }
                        });
                        if ($.fn.select2) $(select).trigger("change");
                    };
                    if (initialValue !== undefined) setEditorValue(initialValue);
                    return;
                }

                if (["in", "not_in"].includes(op)) {
                    const textarea = el("textarea", {
                        class: "superfilter-input",
                        style: "min-height:80px; resize:vertical;",
                        placeholder: "Une valeur par ligne (ou séparée par virgule)"
                    });
                    valueContainer.appendChild(textarea);
                    getEditorValue = () => textarea.value.split(/[\n,]/).map(s => s.trim()).filter(s => s.length > 0);
                    setEditorValue = (v) => {
                        if (Array.isArray(v)) textarea.value = v.join("\n");
                        else if (v != null) textarea.value = String(v);
                    };
                    if (initialValue !== undefined) setEditorValue(initialValue);
                    return;
                }

                const input = el("input", { type: "text", class: "superfilter-input", placeholder: "Entrez une valeur" });
                valueContainer.appendChild(input);
                getEditorValue = () => input.value;
                setEditorValue = (v) => { if (v != null) input.value = String(v); };
                if (initialValue !== undefined) setEditorValue(initialValue);
            };

            opSelect.addEventListener("change", () => updateValueEditor());
            updateValueEditor(existingRule ? existingRule.value : undefined);

            const footer = el("div", { class: "superfilter-modal-footer" });
            const cancelBtn = el("button", { type: "button", class: "superfilter-btn" }, "Annuler");
            const addBtn = el("button", { type: "button", class: "superfilter-btn primary" },
                             editIdx !== null ? "Modifier" : "Ajouter");

            cancelBtn.addEventListener("click", () => overlay.remove());
            addBtn.addEventListener("click", () => {
                const op = opSelect.value;
                let value = null;
                if (!NO_VALUE_OPERATORS.includes(op)) {
                    value = getEditorValue();
                }
                const newRule = { field: field.path, op, value };
                if (editIdx !== null) {
                    this.rules[editIdx] = newRule;
                } else {
                    this.rules.push(newRule);
                }
                this.refreshUI();
                overlay.remove();
            });

            footer.appendChild(cancelBtn);
            footer.appendChild(addBtn);
            modal.appendChild(header);
            modal.appendChild(body);
            modal.appendChild(footer);
            overlay.appendChild(modal);

            closeBtn.addEventListener("click", () => overlay.remove());
            overlay.addEventListener("click", (e) => {
                if (e.target === overlay) overlay.remove();
            });

            document.body.appendChild(overlay);
        }

        updateApplyButtonState() {
            if (!this.applyBtn) return;
            const rulesDirty = normalizeRules(this.rules) !== this.lastAppliedRules;
            const columnsDirty = normalizeColumns(this.getSelectedColumns()) !== this.lastAppliedColumns;
            const isDirty = rulesDirty || columnsDirty;
            this.applyBtn.disabled = !isDirty;
            if (this.resetBtn) {
                this.resetBtn.disabled = !isDirty && !this.rules.length && !this.isColumnCustomizationApplied();
            }
        }

        refreshUI() {
            this.renderBadges(this.badgesContainer);
            this.renderColumnsRow();
            this.refreshColumnsVisibility();
            if (this.emptyHint) {
                this.emptyHint.style.display = this.rules.length === 0 ? '' : 'none';
            }
            this.updateApplyButtonState();
        }

        apply() {
            const form = document.querySelector("#changelist-search") ||
                         document.querySelector("form#changelist-form") ||
                         document.querySelector("#changelist-form") ||
                         document.querySelector("form");
            if (!form) return;

            let hidden = form.querySelector(`input[name='${this.meta.param}']`);
            if (!hidden) {
                hidden = el("input", { type: "hidden", name: this.meta.param });
                form.appendChild(hidden);
            }
            hidden.value = JSON.stringify(this.rules);

            let columnsHidden = form.querySelector(`input[name='${this.meta.columnsParam}']`);
            if (!columnsHidden) {
                columnsHidden = el("input", { type: "hidden", name: this.meta.columnsParam });
                form.appendChild(columnsHidden);
            }
            columnsHidden.value = JSON.stringify(this.getSelectedColumns());

            this.lastAppliedRules = normalizeRules(this.rules);
            this.lastAppliedColumns = normalizeColumns(this.getSelectedColumns());
            this.updateApplyButtonState();
            form.submit();
        }

        reset() {
            const form = document.querySelector("#changelist-search") ||
                         document.querySelector("form#changelist-form") ||
                         document.querySelector("#changelist-form") ||
                         document.querySelector("form");
            if (!form) return;

            this.rules = [];
            this.selectedCount = this.getDefaultColumns().length;
            this.columnOrder = this.getDefaultColumns();
            this.columnsExpanded = false;

            let hidden = form.querySelector(`input[name='${this.meta.param}']`);
            if (!hidden) {
                hidden = el("input", { type: "hidden", name: this.meta.param });
                form.appendChild(hidden);
            }
            hidden.value = "[]";

            let columnsHidden = form.querySelector(`input[name='${this.meta.columnsParam}']`);
            if (!columnsHidden) {
                columnsHidden = el("input", { type: "hidden", name: this.meta.columnsParam });
                form.appendChild(columnsHidden);
            }
            columnsHidden.value = JSON.stringify(this.getDefaultColumns());
            form.submit();
        }
    }

    $(function () {
        renderLoadingShell();
        const metaUrl = new URL(joinUrl(getChangeListBasePath(), "superfilter/meta/"), window.location.origin);
        const currentParams = new URLSearchParams(window.location.search);
        currentParams.forEach((value, key) => {
            metaUrl.searchParams.append(key, value);
        });

        $.getJSON(metaUrl.toString(), meta => {
            removeLoadingShell();
            if ((meta.fields && meta.fields.length > 0) || (meta.columns && meta.columns.length > 0)) {
                new SuperFilterUI(meta);
            }
        }).fail(() => {
            removeLoadingShell();
        });
    });
})();
