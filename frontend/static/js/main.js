/**
 * EMPRESA EXEMPLO — Sistema de Frota
 * main.js — scripts globais
 */

(function () {
  'use strict';

  /* ── BUSCA GLOBAL ──────────────────────────────────────── */
  const searchInput   = document.getElementById('searchInput');
  const searchResults = document.getElementById('searchResults');
  const searchWrap    = document.getElementById('searchWrap');

  if (searchInput) {
    let searchTimer;

    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      const q = searchInput.value.trim();
      if (q.length < 2) {
        searchResults.classList.remove('open');
        return;
      }
      searchTimer = setTimeout(() => fetchBusca(q), 280);
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        searchResults.classList.remove('open');
        searchInput.blur();
      }
    });

    document.addEventListener('click', (e) => {
      if (!searchWrap.contains(e.target)) {
        searchResults.classList.remove('open');
      }
    });

    async function fetchBusca(q) {
      try {
        const res  = await fetch('/api/busca?q=' + encodeURIComponent(q));
        const data = await res.json();
        renderBusca(data);
      } catch (_) { /* silencia erros de rede */ }
    }

    function renderBusca(data) {
      let html = '';

      if (data.veiculos && data.veiculos.length) {
        html += '<div class="search-group"><div class="search-group-label">Veículos</div>';
        data.veiculos.forEach(v => {
          html += `<a class="search-result-item" href="/veiculos/${v.id}">
            <span class="mono" style="color:var(--laranja);font-weight:600;">${escHtml(v.placa)}</span>
            <span style="color:var(--cinza-500)">${escHtml(v.nome)}</span>
          </a>`;
        });
        html += '</div>';
      }

      if (data.motoristas && data.motoristas.length) {
        html += '<div class="search-group"><div class="search-group-label">Motoristas</div>';
        data.motoristas.forEach(m => {
          html += `<a class="search-result-item" href="/motoristas/${m.id}/editar">
            <span>${escHtml(m.nome)}</span>
          </a>`;
        });
        html += '</div>';
      }

      if (data.os && data.os.length) {
        html += '<div class="search-group"><div class="search-group-label">Ordens de Serviço</div>';
        data.os.forEach(o => {
          html += `<a class="search-result-item" href="/os/${o.id}">
            <span class="mono" style="font-weight:600;">${escHtml(o.numero)}</span>
            <span style="color:var(--cinza-500)">${escHtml(o.status)}</span>
          </a>`;
        });
        html += '</div>';
      }

      if (!html) {
        html = '<div style="padding:16px;font-size:13px;color:var(--cinza-400);text-align:center;">Nenhum resultado para "' + escHtml(searchInput.value) + '"</div>';
      }

      searchResults.innerHTML = html;
      searchResults.classList.add('open');
    }
  }

  /* ── PROTEÇÃO CONTRA SUBMIT DUPLO ───────────────────────── */
  document.addEventListener('submit', (e) => {
    const form = e.target;
    const btn  = form.querySelector('button[type=submit]:not([data-no-guard])');
    if (!btn || btn.dataset.submitting) return;

    btn.dataset.submitting = '1';
    const originalHtml = btn.innerHTML;
    btn.innerHTML  = '<span class="spinner"></span> Salvando…';
    btn.disabled   = true;

    // Segurança: libera após 10s caso a página não recarregue
    setTimeout(() => {
      btn.innerHTML = originalHtml;
      btn.disabled  = false;
      delete btn.dataset.submitting;
    }, 10000);
  });

  /* ── CONFIRMAÇÃO EM AÇÕES DESTRUTIVAS ────────────────────── */
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-confirm]');
    if (!el) return;
    const msg = el.dataset.confirm || 'Tem certeza?';
    if (!confirm(msg)) e.preventDefault();
  });

  /* ── AUTO-REFRESH DE STATS (alertas a cada 60s) ─────────── */
  async function refreshStats() {
    try {
      const res  = await fetch('/api/stats');
      const data = await res.json();

      const badge = document.querySelector('.badge-alerta');
      if (data.alertas_criticos > 0) {
        if (badge) {
          badge.textContent = data.alertas_criticos;
          badge.style.display = '';
        }
      } else if (badge) {
        badge.style.display = 'none';
      }
    } catch (_) { /* silencia */ }
  }
  setInterval(refreshStats, 60000);

  /* ── FLASH MESSAGES AUTO-DISMISS ────────────────────────── */
  const flashItems = document.querySelectorAll('.flash-item.flash-success, .flash-item.flash-info');
  flashItems.forEach(item => {
    setTimeout(() => {
      item.style.transition = 'opacity .4s, max-height .4s';
      item.style.opacity = '0';
      item.style.maxHeight = '0';
      item.style.overflow = 'hidden';
      item.style.padding = '0';
      item.style.margin = '0';
      setTimeout(() => item.remove(), 450);
    }, 4000);
  });

  /* ── SIDEBAR MOBILE TOGGLE ───────────────────────────────── */
  const hamburger = document.getElementById('hamburger');
  const sidebar   = document.querySelector('.sidebar');
  if (hamburger && sidebar) {
    hamburger.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !hamburger.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  /* ── TOOLTIPS SIMPLES ────────────────────────────────────── */
  // Já resolvidos via CSS [data-tip]::after

  /* ── FORMATAÇÃO DE INPUTS ────────────────────────────────── */
  // Máscara de placa (ABC1234 ou ABC1D23)
  const placaInputs = document.querySelectorAll('input[name=placa]');
  placaInputs.forEach(input => {
    input.addEventListener('input', () => {
      input.value = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 7);
    });
  });

  // Máscara de CPF
  const cpfInputs = document.querySelectorAll('input[name=cpf]');
  cpfInputs.forEach(input => {
    input.addEventListener('input', () => {
      let v = input.value.replace(/\D/g, '').slice(0, 11);
      if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{0,2})/, '$1.$2.$3-$4');
      else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{0,3})/, '$1.$2.$3');
      else if (v.length > 3) v = v.replace(/(\d{3})(\d{0,3})/, '$1.$2');
      input.value = v;
    });
  });

  // Máscara de CNPJ
  const cnpjInputs = document.querySelectorAll('input[name=cnpj]');
  cnpjInputs.forEach(input => {
    input.addEventListener('input', () => {
      let v = input.value.replace(/\D/g, '').slice(0, 14);
      if (v.length > 12) v = v.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, '$1.$2.$3/$4-$5');
      else if (v.length > 8) v = v.replace(/(\d{2})(\d{3})(\d{3})(\d{0,4})/, '$1.$2.$3/$4');
      else if (v.length > 5) v = v.replace(/(\d{2})(\d{3})(\d{0,3})/, '$1.$2.$3');
      else if (v.length > 2) v = v.replace(/(\d{2})(\d{0,3})/, '$1.$2');
      input.value = v;
    });
  });

  /* ── CONFIRMAÇÃO EM FORMS COM data-confirm ───────────────── */
  // Já tratado no listener acima

  /* ── UTILITÁRIO: escape de HTML ──────────────────────────── */
  function escHtml(str) {
    return String(str || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  /* ── HIGHLIGHT DE LINHA DA TABELA AO CLICAR ─────────────── */
  document.querySelectorAll('tbody tr[data-href]').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => {
      window.location.href = row.dataset.href;
    });
  });

  /* ── KM: formata número com pontos ao sair do campo ─────── */
  document.querySelectorAll('input[name=km_atual], input[name=km_novo], input[name=km_abertura], input[name=km_conclusao]').forEach(input => {
    input.addEventListener('keypress', (e) => {
      if (!/[0-9]/.test(e.key)) e.preventDefault();
    });
  });

  /* ── COPIAR PARA ÁREA DE TRANSFERÊNCIA ───────────────────── */
  document.querySelectorAll('[data-copy]').forEach(el => {
    el.addEventListener('click', () => {
      const text = el.dataset.copy;
      navigator.clipboard.writeText(text).then(() => {
        const orig = el.textContent;
        el.textContent = 'Copiado!';
        setTimeout(() => { el.textContent = orig; }, 1500);
      });
    });
  });

  console.log('%cEmpresa Exemplo — Sistema de Frota', 'color:#F7931E;font-weight:600;font-size:13px;');

})();
