/**
 * SEARCHABLE SELECT — componente global
 * ----------------------------------------------------------------------
 * Substitui <select> por um campo de texto com busca + dropdown, para
 * qualquer lista vinda de cadastro (veículos, motoristas, fornecedores,
 * serviços, materiais, implementos, categorias, usuários, etc).
 *
 * Uso (markup gerado pela macro Jinja components/searchable_select.html):
 *
 * <div class="ss-wrap" data-ss data-catalog="veiculos"
 *      data-hidden-name="veiculo_id" data-selected="12"
 *      data-required="true" data-placeholder="Buscar veículo...">
 *   <input type="hidden" name="veiculo_id" value="12">
 *   <div class="ss-input-row">
 *     <span class="ss-icon">🔍</span>
 *     <input class="ss-input" type="text" autocomplete="off" placeholder="...">
 *     <button type="button" class="ss-clear" tabindex="-1">×</button>
 *   </div>
 *   <div class="ss-error-msg">Campo obrigatório</div>
 * </div>
 *
 * Catálogos: cada página registra suas listas em window.SS_CATALOGS antes
 * do DOMContentLoaded, ex:
 *   Object.assign(window.SS_CATALOGS, {
 *     veiculos: [{id:"1", nome:"ABC-1234 — Fiorino"}, ...],
 *     fornecedores: [{id:"3", nome:"Posto XYZ"}, ...]
 *   });
 *
 * Cada item pode ter: id, nome, sub (texto secundário, ex. unidade),
 * val (valor de referência, usado com data-val-target), un (unidade,
 * usado com data-un-target).
 *
 * Atributos de dados suportados no wrapper:
 *   data-catalog       nome do catálogo em window.SS_CATALOGS (obrigatório)
 *   data-hidden-name   name do input hidden enviado no form
 *   data-selected      id pré-selecionado (edição)
 *   data-required      "true" para exigir seleção no submit
 *   data-placeholder   texto do placeholder
 *   data-val-target    name de outro input da mesma .item-row/form a
 *                       preencher com item.val ao selecionar (opcional)
 *   data-un-target     idem, com item.un (opcional)
 *   data-submit        "true" para dar submit no form ao selecionar/limpar
 *                       (equivalente a onchange="this.form.submit()")
 */
(function () {
  window.SS_CATALOGS = window.SS_CATALOGS || {};

  let _dd, _ddActive = null;

  function ensureDropdown() {
    if (_dd) return _dd;
    _dd = document.createElement('div');
    _dd.className = 'ss-dropdown';
    document.body.appendChild(_dd);

    document.addEventListener('mousedown', e => {
      if (!_dd.contains(e.target) && (!_ddActive || !_ddActive.wrap.contains(e.target))) {
        ddClose();
      }
    });
    window.addEventListener('scroll', () => {
      if (_ddActive && _dd.classList.contains('open')) _ddActive.reposition();
    }, true);
    window.addEventListener('resize', () => {
      if (_ddActive && _dd.classList.contains('open')) _ddActive.reposition();
    });
    return _dd;
  }

  function ddClose() {
    if (!_dd) return;
    _dd.classList.remove('open');
    _dd.innerHTML = '';
    _ddActive = null;
  }

  function highlight(text, query) {
    if (!query) return text;
    const safe = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(text).replace(new RegExp('(' + safe + ')', 'gi'), '<em>$1</em>');
  }

  function initSearchableSelect(wrap, opts) {
    if (wrap.dataset.ssInit) return;
    wrap.dataset.ssInit = '1';
    ensureDropdown();
    opts = opts || {};

    const catalogName = wrap.dataset.catalog || '';
    const catalog      = opts.catalog || window.SS_CATALOGS[catalogName] || [];
    const onSelect      = opts.onSelect || null;
    const hidName       = wrap.dataset.hiddenName || (catalogName + '_id');
    const valTarget     = wrap.dataset.valTarget || null;
    const unTarget      = wrap.dataset.unTarget || null;
    const required      = wrap.dataset.required === 'true';
    const submitOnPick  = wrap.dataset.submit === 'true';
    const placeholder   = wrap.dataset.placeholder || 'Digite para buscar...';
    const preSelectedId = wrap.dataset.selected || '';

    // Monta o markup interno se ainda não existir (permite markup já pronto no HTML)
    let hiddenInput = wrap.querySelector('input[type=hidden]');
    let textInput   = wrap.querySelector('.ss-input');
    let clearBtn    = wrap.querySelector('.ss-clear');

    if (!textInput) {
      wrap.innerHTML = `
        ${hiddenInput ? '' : `<input type="hidden" name="${hidName}" value="${preSelectedId}">`}
        <div class="ss-input-row">
          <span class="ss-icon">🔍</span>
          <input class="ss-input" type="text" autocomplete="off" placeholder="${placeholder}">
          <button type="button" class="ss-clear" tabindex="-1">×</button>
        </div>
        <div class="ss-error-msg">Campo obrigatório</div>
      `;
      hiddenInput = wrap.querySelector('input[type=hidden]');
      textInput   = wrap.querySelector('.ss-input');
      clearBtn    = wrap.querySelector('.ss-clear');
    }

    let selectedId = hiddenInput.value || preSelectedId || '';
    let focusedIdx = -1;
    let dropItems  = [];

    const inst = {
      wrap,
      reposition() {
        const rect = textInput.getBoundingClientRect();
        _dd.style.top   = (rect.bottom + 4) + 'px';
        _dd.style.left  = rect.left + 'px';
        _dd.style.width = rect.width + 'px';
      }
    };

    function labelFor(item) {
      return item.nome + (item.sub ? ' (' + item.sub + ')' : '');
    }

    // Prefill (edição) — mostra o texto do item já selecionado
    if (selectedId) {
      const found = catalog.find(it => String(it.id) === String(selectedId));
      if (found) {
        textInput.value = labelFor(found);
        clearBtn.classList.add('visible');
      }
      hiddenInput.value = selectedId;
    }

    function renderDropdown(query) {
      const q = (query || '').trim().toLowerCase();
      const words = q.split(/\s+/).filter(Boolean);

      dropItems = catalog.map(item => {
        const name = String(item.nome).toLowerCase();
        if (!words.length) return { item, score: 0 };
        if (!words.every(w => name.includes(w))) return null;
        const score = name.startsWith(q) ? 2 : (name.includes(q) ? 1 : 0);
        return { item, score };
      }).filter(Boolean).sort((a, b) => b.score - a.score);

      focusedIdx = -1;
      _ddActive = inst;
      inst.reposition();

      _dd.innerHTML = '';
      if (!dropItems.length) {
        _dd.innerHTML = '<div class="ss-empty">Nenhum item encontrado</div>';
      } else {
        dropItems.forEach(({ item }) => {
          const div = document.createElement('div');
          div.className = 'ss-opt' + (String(item.id) === String(selectedId) ? ' selected' : '');
          let nameHtml = highlight(item.nome, q);
          if (item.sub) nameHtml += '<span class="ss-badge">(' + item.sub + ')</span>';
          div.innerHTML = '<span>' + nameHtml + '</span><span class="ss-press">Enter para selecionar</span>';
          div.addEventListener('mousedown', e => { e.preventDefault(); selectItem(item); });
          _dd.appendChild(div);
        });
      }
      _dd.classList.add('open');
    }

    function selectItem(item) {
      selectedId = item.id;
      hiddenInput.value = item.id;
      textInput.value   = labelFor(item);
      clearBtn.classList.add('visible');
      wrap.classList.remove('ss-invalid');
      ddClose();

      const row = wrap.closest('.item-row') || wrap.closest('form') || document;
      if (valTarget && item.val !== undefined && item.val !== null) {
        const vEl = row.querySelector('[name="' + valTarget + '"]');
        if (vEl) vEl.value = item.val;
      }
      if (unTarget && item.un) {
        const uEl = row.querySelector('[name="' + unTarget + '"]');
        if (uEl) uEl.value = item.un;
      }

      wrap.dispatchEvent(new CustomEvent('ss:change', { detail: item, bubbles: true }));
      if (onSelect) onSelect(item);

      if (submitOnPick) {
        const form = wrap.closest('form');
        if (form) form.submit();
      }
    }

    function moveFocus(dir) {
      const opts = _dd.querySelectorAll('.ss-opt');
      if (!opts.length) return;
      opts.forEach(o => o.classList.remove('focused'));
      focusedIdx = Math.max(0, Math.min(opts.length - 1, focusedIdx + dir));
      opts[focusedIdx].classList.add('focused');
      opts[focusedIdx].scrollIntoView({ block: 'nearest' });
    }

    textInput.addEventListener('input', () => {
      selectedId = '';
      hiddenInput.value = '';
      clearBtn.classList.toggle('visible', textInput.value.length > 0);
      renderDropdown(textInput.value);
    });

    textInput.addEventListener('focus', () => {
      renderDropdown(textInput.value === labelForSelected() ? '' : textInput.value);
    });

    function labelForSelected() {
      const found = catalog.find(it => String(it.id) === String(selectedId));
      return found ? labelFor(found) : '';
    }

    textInput.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (!_dd.classList.contains('open')) renderDropdown(textInput.value); else moveFocus(1); }
      if (e.key === 'ArrowUp')   { e.preventDefault(); moveFocus(-1); }
      if (e.key === 'Enter') {
        e.preventDefault();
        const opts = _dd.querySelectorAll('.ss-opt');
        if (focusedIdx >= 0 && opts[focusedIdx]) {
          opts[focusedIdx].dispatchEvent(new Event('mousedown'));
        } else if (dropItems[0]) {
          selectItem(dropItems[0].item);
        }
      }
      if (e.key === 'Escape') ddClose();
    });

    textInput.addEventListener('blur', () => {
      setTimeout(() => {
        if (_ddActive === inst) ddClose();
        // se saiu sem selecionar nada válido, restaura o texto do item selecionado (ou limpa)
        if (!selectedId) {
          textInput.value = '';
        } else {
          textInput.value = labelForSelected();
        }
      }, 200);
    });

    clearBtn.addEventListener('click', () => {
      selectedId = '';
      hiddenInput.value = '';
      textInput.value   = '';
      clearBtn.classList.remove('visible');
      wrap.classList.remove('ss-invalid');
      textInput.focus();
      if (submitOnPick) {
        const form = wrap.closest('form');
        if (form) form.submit();
      }
    });

    // Validação "required" no submit do form — sempre vinculada, pois
    // data-required pode mudar dinamicamente (ex: campo condicional)
    const form = wrap.closest('form');
    if (form && !form.dataset.ssValidateBound) {
      form.dataset.ssValidateBound = '1';
      form.addEventListener('submit', e => {
        const invalidWraps = form.querySelectorAll('.ss-wrap[data-required="true"]');
        let firstInvalid = null;
        invalidWraps.forEach(w => {
          const hid = w.querySelector('input[type=hidden]');
          const ok = hid && hid.value;
          w.classList.toggle('ss-invalid', !ok);
          if (!ok && !firstInvalid) firstInvalid = w;
        });
        if (firstInvalid) {
          e.preventDefault();
          firstInvalid.scrollIntoView({ block: 'center', behavior: 'smooth' });
          const inp = firstInvalid.querySelector('.ss-input');
          if (inp) inp.focus();
        }
      });
    }
  }

  function initAllSearchableSelects(root) {
    (root || document).querySelectorAll('.ss-wrap:not([data-ss-init])').forEach(initSearchableSelect);
  }

  // Auto-init inicial
  function boot() { initAllSearchableSelects(document); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // Auto-init para conteúdo inserido dinamicamente (ex: novas linhas de peça/serviço)
  const mo = new MutationObserver(mutations => {
    for (const m of mutations) {
      m.addedNodes.forEach(node => {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches('.ss-wrap')) initSearchableSelect(node);
        if (node.querySelectorAll) initAllSearchableSelects(node);
      });
    }
  });
  if (document.body) {
    mo.observe(document.body, { childList: true, subtree: true });
  } else {
    document.addEventListener('DOMContentLoaded', () => mo.observe(document.body, { childList: true, subtree: true }));
  }

  window.SSInit = { init: initSearchableSelect, initAll: initAllSearchableSelects };
})();
