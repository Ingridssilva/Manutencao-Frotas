/**
 * mobile.js — Frota Empresa Exemplo
 * Sidebar mobile + Upload de fotos com preview
 * Adicionar: <script src="{{ url_for('static', filename='js/mobile.js') }}" defer></script>
 */

(function () {
  'use strict';

  /* ── SIDEBAR MOBILE ──────────────────────────────────── */
  function initSidebar() {
    const sidebar  = document.querySelector('.sidebar');
    const btnMenu  = document.querySelector('.btn-menu');
    if (!sidebar || !btnMenu) return;

    // Cria overlay
    const overlay  = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    function abrir() {
      sidebar.classList.add('open');
      overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    function fechar() {
      sidebar.classList.remove('open');
      overlay.classList.remove('open');
      document.body.style.overflow = '';
    }

    btnMenu.addEventListener('click', () => {
      sidebar.classList.contains('open') ? fechar() : abrir();
    });
    overlay.addEventListener('click', fechar);

    // Fecha ao navegar
    sidebar.querySelectorAll('.nav-item').forEach(a =>
      a.addEventListener('click', fechar)
    );

    // Swipe para fechar
    let startX = 0;
    sidebar.addEventListener('touchstart', e => { startX = e.touches[0].clientX; }, {passive: true});
    sidebar.addEventListener('touchend', e => {
      if (startX - e.changedTouches[0].clientX > 60) fechar();
    }, {passive: true});
  }

  /* ── UPLOAD DE FOTOS ─────────────────────────────────── */
  function initFotoUpload() {
    const zone    = document.getElementById('uploadZone');
    const input   = document.getElementById('fotoInput');
    const grid    = document.getElementById('fotosGrid');
    const osId    = zone?.dataset.osId;
    if (!zone || !input || !grid || !osId) return;

    // Drag & drop
    zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      [...e.dataTransfer.files].forEach(f => uploadArquivo(f, osId));
    });

    // Click / câmera no mobile
    input.addEventListener('change', () => {
      [...input.files].forEach(f => uploadArquivo(f, osId));
      input.value = '';
    });

    // Carrega fotos existentes
    carregarFotos(osId);
  }

  async function carregarFotos(osId) {
    const grid = document.getElementById('fotosGrid');
    try {
      const resp = await fetch(`/os/${osId}/fotos`);
      const list = await resp.json();
      grid.innerHTML = '';
      list.forEach(f => grid.appendChild(criarCard(f, osId)));
      atualizarContador(list.length);
    } catch (e) {
      console.error('Erro ao carregar fotos:', e);
    }
  }

  async function uploadArquivo(file, osId) {
    const grid      = document.getElementById('fotosGrid');
    const MAX_SIZE  = 10 * 1024 * 1024;

    if (file.size > MAX_SIZE) {
      mostrarToast('Arquivo maior que 10 MB.', 'erro');
      return;
    }

    // Placeholder com progresso
    const placeholder = document.createElement('div');
    placeholder.className = 'foto-card';
    placeholder.innerHTML = `
      <div class="foto-card-doc">
        <div class="foto-upload-progress"><div class="foto-upload-progress-bar" style="width:30%"></div></div>
        <div class="foto-card-doc-nome" style="margin-top:8px;">Enviando...</div>
      </div>`;
    grid.prepend(placeholder);

    const fd = new FormData();
    fd.append('file', file);
    fd.append('descricao', '');
    fd.append('tipo', file.type.startsWith('image/') ? 'foto' : 'documento');

    try {
      const resp = await fetch(`/os/${osId}/fotos`, {
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN || '' },
        body: fd,
      });
      const data = await resp.json();

      placeholder.remove();

      if (data.ok) {
        grid.prepend(criarCard(data, osId));
        atualizarContador(grid.querySelectorAll('.foto-card').length);
        mostrarToast('Foto enviada ✓', 'ok');
      } else {
        mostrarToast('Erro: ' + data.erro, 'erro');
      }
    } catch (e) {
      placeholder.remove();
      mostrarToast('Falha no envio.', 'erro');
    }
  }

  function criarCard(foto, osId) {
    const card = document.createElement('div');
    card.className = 'foto-card';
    card.dataset.id = foto.id;

    const isImagem = foto.url && (
      foto.nome.match(/\.(jpg|jpeg|png|gif|webp|heic|heif)$/i)
    );

    if (isImagem) {
      card.innerHTML = `
        <img src="${foto.url}" alt="${foto.descricao || foto.nome}"
             loading="lazy" onerror="this.style.display='none'">`;
    } else {
      const ext = foto.nome.split('.').pop().toUpperCase();
      card.innerHTML = `
        <div class="foto-card-doc">
          <div class="foto-card-doc-icon">${ext === 'PDF' ? '📄' : '📎'}</div>
          <div class="foto-card-doc-nome">${foto.nome}</div>
        </div>`;
    }

    card.innerHTML += `
      <div class="foto-card-overlay">
        <a href="${foto.url}" target="_blank" title="Abrir">↗</a>
        <button onclick="deletarFoto(${foto.id}, ${osId})" title="Deletar">🗑</button>
      </div>`;

    return card;
  }

  window.deletarFoto = async function (fotoId, osId) {
    if (!confirm('Deletar esta foto?')) return;
    try {
      const resp = await fetch(`/os/${osId}/fotos/${fotoId}`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN || '' },
      });
      const data = await resp.json();
      if (data.ok) {
        document.querySelector(`.foto-card[data-id="${fotoId}"]`)?.remove();
        const grid = document.getElementById('fotosGrid');
        atualizarContador(grid.querySelectorAll('.foto-card').length);
        mostrarToast('Foto removida.', 'ok');
      }
    } catch (e) {
      mostrarToast('Erro ao deletar.', 'erro');
    }
  };

  function atualizarContador(n) {
    const el = document.getElementById('fotoContador');
    if (el) el.textContent = n;
  }

  /* ── TOAST ───────────────────────────────────────────── */
  function mostrarToast(msg, tipo) {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position:fixed;bottom:80px;right:20px;z-index:9999;
      padding:12px 18px;border-radius:10px;font-size:14px;font-weight:500;
      color:#fff;box-shadow:0 4px 16px rgba(0,0,0,.2);
      background:${tipo === 'ok' ? '#30D158' : '#FF453A'};
      animation:slideIn .25s ease;
    `;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  /* ── BOTÃO EXPORTAR EXCEL ───────────────────────────── */
  function initExportButtons() {
    document.querySelectorAll('[data-export]').forEach(btn => {
      btn.addEventListener('click', function () {
        const modulo = this.dataset.export;
        const params = new URLSearchParams(window.location.search);
        window.location.href = `/export/${modulo}?${params.toString()}`;
      });
    });
  }

  /* ── INIT ────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initFotoUpload();
    initExportButtons();
  });

  // Animação do toast
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to   { transform: translateX(0);   opacity: 1; }
    }
  `;
  document.head.appendChild(style);

})();
