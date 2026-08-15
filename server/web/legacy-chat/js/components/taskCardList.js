import { renderTaskCard, escapeHtml } from './taskCard.js';

export class TaskCardList {
  constructor(container, {
    onCardClick = null,
    onCopyClick = null,
    itemHeight = 85, // estimated height of each task card in pixels
    pageSize = 50,
    emptyText = '下达任务，大脑会写卡',
  } = {}) {
    this.container = container;
    this.onCardClick = onCardClick;
    this.onCopyClick = onCopyClick;
    this.itemHeight = itemHeight;
    this.pageSize = pageSize;
    this.emptyText = emptyText;

    this.items = [];         // current list of all matching items
    this.visibleItems = [];  // matching filtered/paged items
    this.loading = false;
    this.error = null;

    // Pagination state
    this.currentPage = 1;
    this.totalPages = 1;
    this.onPageChange = null;

    // Virtual scrolling state
    this.useVirtualScroll = false;
    this.scrollTop = 0;
    this.containerHeight = 0;

    // Initialize DOM structure: split into scrolling list view and a fixed pagination footer
    this.container.innerHTML = `
      <div class="task-card-list-scroller" style="flex: 1; overflow-y: auto; position: relative;"></div>
      <div class="task-card-list-pagination" style="flex-shrink: 0;"></div>
    `;
    this.scroller = this.container.querySelector('.task-card-list-scroller');
    this.paginationContainer = this.container.querySelector('.task-card-list-pagination');

    // Bind scroll handler
    this.handleScroll = this.handleScroll.bind(this);
  }

  setItems(items) {
    this.loading = false;
    // 增量：关键字段未变则不重建 DOM（消 5s 刷新闪烁）
    const sig = items.map((i) => [
      i.id, i.board_column || i.state || i.status,
      i.tool_calls, i.audit_runs, i.audit_status || '', i.state,
    ].join(':')).join('|');
    this.items = items;
    this.visibleItems = items;
    if (sig === this._lastSig) return;
    this._lastSig = sig;
    this.render();
  }

  showLoading() {
    this.loading = true;
    this.error = null;
    this.render();
  }

  showError(err) {
    this.loading = false;
    this.error = err;
    this.render();
  }

  enableVirtualScroll(enable = true) {
    this.useVirtualScroll = enable;
    if (enable) {
      this.scroller.addEventListener('scroll', this.handleScroll);
    } else {
      this.scroller.removeEventListener('scroll', this.handleScroll);
    }
  }

  handleScroll() {
    if (!this.useVirtualScroll) return;
    this.scrollTop = this.scroller.scrollTop;
    this.containerHeight = this.scroller.clientHeight;
    this.renderVirtual();
  }

  setupPagination({ currentPage, totalPages, onPageChange }) {
    this.currentPage = currentPage;
    this.totalPages = totalPages;
    this.onPageChange = onPageChange;
    this.renderPagination();
  }

  render() {
    if (this.loading) {
      this.scroller.innerHTML = `<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>`;
      this.paginationContainer.innerHTML = '';
      return;
    }
    if (this.error) {
      this.scroller.innerHTML = `<div class="board-empty" style="color:#a33a2c;">加载失败: ${escapeHtml(this.error.message || String(this.error))}</div>`;
      this.paginationContainer.innerHTML = '';
      return;
    }
    if (!this.visibleItems || this.visibleItems.length === 0) {
      this.scroller.innerHTML = `<div class="board-empty">${escapeHtml(this.emptyText)}</div>`;
      this.paginationContainer.innerHTML = '';
      return;
    }

    if (this.useVirtualScroll) {
      this.scrollTop = this.scroller.scrollTop;
      this.containerHeight = this.scroller.clientHeight || 400;
      this.renderVirtual();
    } else {
      this.scroller.innerHTML = this.visibleItems.map(renderTaskCard).join('');
      this.bindEvents();
    }

    this.renderPagination();
  }

  renderVirtual() {
    const totalCount = this.visibleItems.length;
    const totalHeight = totalCount * this.itemHeight;

    // Calculate start and end indices to render
    const startIdx = Math.max(0, Math.floor(this.scrollTop / this.itemHeight) - 2);
    const endIdx = Math.min(totalCount, Math.ceil((this.scrollTop + this.containerHeight) / this.itemHeight) + 2);

    // Build virtual viewport
    this.scroller.innerHTML = `
      <div class="virtual-scroll-spacer" style="height: ${totalHeight}px; position: relative; width: 100%;">
        <div class="virtual-scroll-content" style="position: absolute; top: 0; left: 0; right: 0; transform: translateY(${startIdx * this.itemHeight}px); display: flex; flex-direction: column; gap: 4px;">
          ${this.visibleItems.slice(startIdx, endIdx).map(renderTaskCard).join('')}
        </div>
      </div>
    `;
    this.bindEvents();
  }

  renderPagination() {
    if (!this.totalPages || this.totalPages <= 1) {
      this.paginationContainer.innerHTML = '';
      return;
    }

    let buttons = [];
    const maxBtns = 5;
    let startPage = Math.max(1, this.currentPage - Math.floor(maxBtns / 2));
    let endPage = Math.min(this.totalPages, startPage + maxBtns - 1);
    if (endPage - startPage + 1 < maxBtns) {
      startPage = Math.max(1, endPage - maxBtns + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      buttons.push(`
        <button type="button" class="hub-btn pagination-page-btn ${i === this.currentPage ? 'primary' : ''}" data-page="${i}" style="padding: 2px 8px; font-size: 11px; min-width: 24px; border: 1px solid var(--ccc-border-subtle); background: ${i === this.currentPage ? 'var(--ccc-text-accent)' : 'var(--ccc-bg-layer)'}; color: ${i === this.currentPage ? '#fff' : 'var(--ccc-text-base)'}; border-radius: 3px; cursor: pointer;">
          ${i}
        </button>
      `);
    }

    this.paginationContainer.innerHTML = `
      <div class="board-pagination" style="display: flex; gap: 4px; justify-content: center; align-items: center; padding: 10px 4px; border-top: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-base);">
        <button type="button" class="hub-btn pagination-prev-btn" data-page="prev" ${this.currentPage <= 1 ? 'disabled' : ''} style="padding: 2px 8px; font-size: 11px; border: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-layer); color: var(--ccc-text-base); border-radius: 3px; cursor: ${this.currentPage <= 1 ? 'not-allowed' : 'pointer'}; opacity: ${this.currentPage <= 1 ? 0.5 : 1};">上一页</button>
        ${buttons.join('')}
        <button type="button" class="hub-btn pagination-next-btn" data-page="next" ${this.currentPage >= this.totalPages ? 'disabled' : ''} style="padding: 2px 8px; font-size: 11px; border: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-layer); color: var(--ccc-text-base); border-radius: 3px; cursor: ${this.currentPage >= this.totalPages ? 'not-allowed' : 'pointer'}; opacity: ${this.currentPage >= this.totalPages ? 0.5 : 1};">下一页</button>
      </div>
    `;

    // Bind pagination click events
    this.paginationContainer.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', (ev) => {
        ev.preventDefault();
        const pageAttr = btn.dataset.page;
        if (!pageAttr) return;

        let targetPage = this.currentPage;
        if (pageAttr === 'prev') {
          targetPage = Math.max(1, this.currentPage - 1);
        } else if (pageAttr === 'next') {
          targetPage = Math.min(this.totalPages, this.currentPage + 1);
        } else {
          targetPage = parseInt(pageAttr, 10);
        }

        if (targetPage !== this.currentPage && this.onPageChange) {
          this.onPageChange(targetPage);
        }
      });
    });
  }

  bindEvents() {
    // Card clicks
    this.scroller.querySelectorAll('.board-task-card').forEach(card => {
      card.addEventListener('click', (ev) => {
        if (ev.target.closest('.board-card-copy') || ev.target.closest('.card-copy-btn')) return;
        const id = card.dataset.id;
        if (this.onCardClick) {
          this.onCardClick(card, id);
        }
      });
    });

    // Copy clicks
    this.scroller.querySelectorAll('.board-card-copy, .card-copy-btn').forEach(btn => {
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        ev.preventDefault();
        const id = btn.dataset.id || btn.closest('.board-task-card')?.dataset.id;
        if (id && this.onCopyClick) {
          this.onCopyClick(btn, id);
        }
      });
    });

    // Check for pending detail ID and click it
    if (window.__PENDING_DETAIL_ID__) {
      const pendingId = window.__PENDING_DETAIL_ID__;
      const cardEl = this.scroller.querySelector(`.board-task-card[data-id="${pendingId}"]`);
      if (cardEl) {
        window.__PENDING_DETAIL_ID__ = null; // Clear it
        setTimeout(() => {
          cardEl.click();
        }, 50);
      } else {
        // Fallback: If not found in this list, but we have the modal in the DOM, let's open it directly!
        const modal = document.querySelector('#board-dm');
        if (modal) {
          window.__PENDING_DETAIL_ID__ = null; // Clear it
          import('../api.js').then(async (api) => {
            try {
              const r = await api.apiGet('/tasks/' + encodeURIComponent(pendingId));
              const titleEl = document.querySelector('#board-dti');
              const idEl = document.querySelector('#board-did');
              const ttEl = document.querySelector('#board-dtt');
              const mtEl = document.querySelector('#board-dmt');
              const accEl = document.querySelector('#board-dacc');

              if (titleEl) titleEl.textContent = '任务: ' + (r.id || pendingId);
              if (idEl) idEl.textContent = r.id || pendingId;
              if (ttEl) ttEl.textContent = r.title || '(无标题)';
              if (mtEl) {
                const esc = (s) => {
                  const d = document.createElement('div');
                  d.textContent = String(s || '');
                  return d.innerHTML;
                };
                const meta = [
                  `状态: ${esc(r.status || '—')}`,
                  r.executor ? `执行体: ${esc(r.executor)}` : '',
                  r.card_kind ? `类型: ${esc(r.card_kind)}` : '',
                  r.parent_id ? `父卡: ${esc(r.parent_id)}` : '',
                ].filter(Boolean).join(' · ');
                mtEl.innerHTML = meta;
              }
              if (accEl) {
                const detailMod = await import('./taskCardDetail.js');
                accEl.innerHTML = detailMod.renderTaskCardDetail(r);
              }
              modal.classList.add('open');
            } catch (err) {
              window.showToast?.(err?.message || '加载详情失败', 'error');
            }
          });
        }
      }
    }
  }
}
