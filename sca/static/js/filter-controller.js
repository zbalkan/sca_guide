/** Review list filtering. */
class FilterController {
    constructor(checks, reviewPane) {
        this.checks = checks;
        this.reviewPane = reviewPane;
        this.activeFilters = {
            status: ['accepted', 'exception', 'not_applicable', 'unreviewed'],
            searchText: '',
            impactSearchText: '',
        };

        this.bindEvents();
        this.applyFilters();
    }

    bindEvents() {
        document.querySelectorAll('input[name="status"]').forEach(input => {
            input.addEventListener('change', () => {
                this.activeFilters.status = Array.from(
                    document.querySelectorAll('input[name="status"]:checked')
                ).map(item => item.value);
                this.applyFilters();
            });
        });

        const search = document.getElementById('search-input');
        const impact = document.getElementById('impact-search-input');
        const clear = document.getElementById('clear-filters-btn');
        search.addEventListener('input', () => {
            this.activeFilters.searchText = search.value.toLowerCase();
            this.applyFilters();
        });
        impact.addEventListener('input', () => {
            this.activeFilters.impactSearchText = impact.value.toLowerCase();
            this.applyFilters();
        });
        clear.addEventListener('click', () => this.clear());
        document.addEventListener('reviewDecisionChanged', () => this.applyFilters());
    }

    applyFilters() {
        const ids = this.checks.filter(check => {
            const decision = this.reviewPane.decisions[check.id];
            const status = decision ? decision.decision : 'unreviewed';
            if (!this.activeFilters.status.includes(status)) return false;
            if (this.activeFilters.impactSearchText &&
                !(check.impact || '').toLowerCase().includes(this.activeFilters.impactSearchText)) {
                return false;
            }
            if (this.activeFilters.searchText) {
                const text = [
                    check.id, check.title, check.description || '', check.rationale || '',
                    check.remediation || ''
                ].join(' ').toLowerCase();
                if (!text.includes(this.activeFilters.searchText)) return false;
            }
            return true;
        }).map(check => check.id);
        this.reviewPane.filterRows(ids);
    }

    clear() {
        document.querySelectorAll('input[name="status"]').forEach(input => {
            input.checked = true;
        });
        document.getElementById('search-input').value = '';
        document.getElementById('impact-search-input').value = '';
        this.activeFilters = {
            status: ['accepted', 'exception', 'not_applicable', 'unreviewed'],
            searchText: '',
            impactSearchText: '',
        };
        this.applyFilters();
    }
}

window.FilterController = FilterController;
