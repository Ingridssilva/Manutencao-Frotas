/**
 * EMPRESA EXEMPLO — Sistema de Frota
 * forms.js — lógica dinâmica dos formulários (OS, Orçamentos)
 */

/* ── ITENS DINÂMICOS DE OS / ORÇAMENTO ─────────────────────
   Gerencia adição/remoção de linhas de serviço, material e pagamento
   ─────────────────────────────────────────────────────────── */

/* Adiciona linha de item de serviço */
function addServicoRow() {
  const tbody = document.getElementById('tbody-servico');
  if (!tbody) return;
  const idx   = tbody.querySelectorAll('tr').length;
  const tr    = document.createElement('tr');
  tr.innerHTML = `
    <td>
      <select name="servico_id[]" class="svc-select" style="width:100%;" onchange="preencherValorSvc(this,${idx})">
        <option value="">— livre —</option>
        ${window._servicos ? window._servicos.map(s => `<option value="${s.id}" data-val="${s.valor||0}">${esc(s.nome)}</option>`).join('') : ''}
      </select>
      <input type="text" name="svc_desc[]" placeholder="Descrição livre..." style="margin-top:6px;" oninput="sincDesc(this,'svc')">
    </td>
    <td><input type="number" name="svc_qty[]" value="1" min="0.01" step="0.01" style="width:80px;" oninput="calcTotal('servico')"></td>
    <td><input type="number" name="svc_val[]" value="0" min="0" step="0.01" style="width:110px;" id="svc_val_${idx}" oninput="calcTotal('servico')"></td>
    <td><input type="text" name="svc_exec[]" placeholder="Técnico / Oficina" style="width:140px;"></td>
    <td><button type="button" class="btn btn-danger btn-sm btn-icon" onclick="remRow(this)" title="Remover">✕</button></td>
  `;
  tbody.appendChild(tr);
  calcTotal('servico');
}

/* Adiciona linha de item de material */
function addMaterialRow() {
  const tbody = document.getElementById('tbody-material');
  if (!tbody) return;
  const idx   = tbody.querySelectorAll('tr').length;
  const tr    = document.createElement('tr');
  tr.innerHTML = `
    <td>
      <select name="material_id[]" class="mat-select" style="width:100%;" onchange="preencherValorMat(this,${idx})">
        <option value="">— livre —</option>
        ${window._materiais ? window._materiais.map(m => `<option value="${m.id}" data-val="${m.valor||0}" data-un="${m.unidade||'un'}">${esc(m.nome)} (${m.unidade||'un'})</option>`).join('') : ''}
      </select>
      <input type="text" name="mat_desc[]" placeholder="Descrição livre..." style="margin-top:6px;">
    </td>
    <td><input type="number" name="mat_qty[]" value="1" min="0.01" step="0.01" style="width:80px;" oninput="calcTotal('material')"></td>
    <td><input type="number" name="mat_val[]" value="0" min="0" step="0.01" style="width:110px;" id="mat_val_${idx}" oninput="calcTotal('material')"></td>
    <td><button type="button" class="btn btn-danger btn-sm btn-icon" onclick="remRow(this)" title="Remover">✕</button></td>
  `;
  tbody.appendChild(tr);
  calcTotal('material');
}

/* Adiciona linha de parcela de pagamento */
function addPagamentoRow() {
  const tbody = document.getElementById('tbody-pagamento');
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" name="pag_nf[]" placeholder="Nº NF" style="width:110px;"></td>
    <td><input type="number" name="pag_val[]" value="0" min="0" step="0.01" style="width:120px;" oninput="calcTotalPag()"></td>
    <td><input type="date" name="pag_venc[]" required style="width:140px;"></td>
    <td>
      <select name="pag_forma[]" style="width:130px;">
        <option value="">Selecione</option>
        <option value="pix">PIX</option>
        <option value="boleto">Boleto</option>
        <option value="transferencia">Transferência</option>
        <option value="dinheiro">Dinheiro</option>
        <option value="cheque">Cheque</option>
      </select>
    </td>
    <td><button type="button" class="btn btn-danger btn-sm btn-icon" onclick="remRow(this)" title="Remover">✕</button></td>
  `;
  tbody.appendChild(tr);
}

/* Remove linha */
function remRow(btn) {
  const tr = btn.closest('tr');
  const tbody = tr.parentElement;
  tr.style.opacity = '0';
  tr.style.transition = 'opacity .2s';
  setTimeout(() => {
    tr.remove();
    calcTotal('servico');
    calcTotal('material');
    calcTotalPag();
  }, 200);
}

/* Retorna o elemento container da linha (tr ou div pai com classe *-row) */
function _getRow(sel) {
  return sel.closest('tr') || sel.closest('.svc-row') || sel.closest('.mat-row') || sel.parentElement;
}

/* Preenche valor do serviço ao selecionar do catálogo */
function preencherValorSvc(sel, idx) {
  const opt = sel.options[sel.selectedIndex];
  const val = parseFloat(opt.dataset.val || 0);
  const input = (idx !== undefined ? document.getElementById('svc_val_' + idx) : null) ||
                _getRow(sel).querySelector('input[name="svc_val[]"]');
  if (input && val > 0) input.value = val.toFixed(2);
  calcTotal('servico');
}

/* Preenche valor do material ao selecionar do catálogo */
function preencherValorMat(sel, idx) {
  const opt = sel.options[sel.selectedIndex];
  const val = parseFloat(opt.dataset.val || 0);
  const un  = opt.dataset.un || '';
  const row = _getRow(sel);
  const input = (idx !== undefined ? document.getElementById('mat_val_' + idx) : null) ||
                row.querySelector('input[name="mat_val[]"]');
  if (input && val > 0) input.value = val.toFixed(2);
  const unInput = row.querySelector('input[name="mat_un[]"]');
  if (unInput && un) unInput.value = un;
  calcTotal('material');
}

/* Calcula subtotal de serviços ou materiais */
function calcTotal(tipo) {
  const prefix  = tipo === 'servico' ? 'svc' : 'mat';
  const tbody   = document.getElementById('tbody-' + tipo);
  if (!tbody) return;
  const rows    = tbody.querySelectorAll('tr');
  let subtotal  = 0;
  rows.forEach(row => {
    const qty = parseFloat(row.querySelector(`input[name="${prefix}_qty[]"]`)?.value || 1);
    const val = parseFloat(row.querySelector(`input[name="${prefix}_val[]"]`)?.value || 0);
    subtotal  += qty * val;
  });
  const el = document.getElementById('subtotal-' + tipo);
  if (el) el.textContent = fmtBRL(subtotal);
  calcTotalGeral();
}

/* Calcula total de pagamentos */
function calcTotalPag() {
  const tbody = document.getElementById('tbody-pagamento');
  if (!tbody) return;
  let total = 0;
  tbody.querySelectorAll('input[name="pag_val[]"]').forEach(input => {
    total += parseFloat(input.value || 0);
  });
  const el = document.getElementById('total-pagamentos');
  if (el) el.textContent = fmtBRL(total);
}

/* Calcula total geral (serviços + materiais) */
function calcTotalGeral() {
  let total = 0;

  ['servico', 'material'].forEach(tipo => {
    const prefix = tipo === 'servico' ? 'svc' : 'mat';
    const tbody  = document.getElementById('tbody-' + tipo);
    if (!tbody) return;
    tbody.querySelectorAll('tr').forEach(row => {
      const qty = parseFloat(row.querySelector(`input[name="${prefix}_qty[]"]`)?.value || 1);
      const val = parseFloat(row.querySelector(`input[name="${prefix}_val[]"]`)?.value || 0);
      total    += qty * val;
    });
  });

  const el = document.getElementById('total-geral');
  if (el) el.textContent = fmtBRL(total);

  // Preenche campo hidden de custo total se existir
  const hidden = document.getElementById('custo_total_hidden');
  if (hidden) hidden.value = total.toFixed(2);
}

/* ── ORÇAMENTO: itens genéricos ─────────────────────────── */
function addItemRow() {
  const tbody = document.getElementById('tbody-itens');
  if (!tbody) return;
  const idx   = tbody.querySelectorAll('tr').length;
  const tr    = document.createElement('tr');
  tr.innerHTML = `
    <td>
      <select name="item_tipo[]" style="width:110px;" onchange="toggleItemTipo(this)">
        <option value="servico">Serviço</option>
        <option value="material">Material</option>
      </select>
    </td>
    <td>
      <select name="item_servico_id[]" style="width:200px;" class="tipo-servico">
        <option value="">— catálogo —</option>
        ${window._servicos ? window._servicos.map(s => `<option value="${s.id}" data-val="${s.valor||0}">${esc(s.nome)}</option>`).join('') : ''}
      </select>
      <select name="item_material_id[]" style="width:200px;display:none;" class="tipo-material">
        <option value="">— catálogo —</option>
        ${window._materiais ? window._materiais.map(m => `<option value="${m.id}" data-val="${m.valor||0}">${esc(m.nome)}</option>`).join('') : ''}
      </select>
      <input type="text" name="item_desc[]" placeholder="Descrição livre..." style="margin-top:6px;width:200px;">
    </td>
    <td><input type="number" name="item_qty[]" value="1" min="0.01" step="0.01" style="width:80px;" oninput="calcTotalItens()"></td>
    <td><input type="number" name="item_val[]" value="0" min="0" step="0.01" style="width:110px;" oninput="calcTotalItens()"></td>
    <td style="font-weight:600;" class="item-subtotal">R$ 0,00</td>
    <td><button type="button" class="btn btn-danger btn-sm btn-icon" onclick="remRow(this)">✕</button></td>
  `;
  tbody.appendChild(tr);
  // Preenche valor ao selecionar serviço/material
  tr.querySelector('.tipo-servico').addEventListener('change', function () {
    const val = parseFloat(this.options[this.selectedIndex]?.dataset.val || 0);
    if (val > 0) tr.querySelector('input[name="item_val[]"]').value = val.toFixed(2);
    calcTotalItens();
  });
  tr.querySelector('.tipo-material').addEventListener('change', function () {
    const val = parseFloat(this.options[this.selectedIndex]?.dataset.val || 0);
    if (val > 0) tr.querySelector('input[name="item_val[]"]').value = val.toFixed(2);
    calcTotalItens();
  });
}

function toggleItemTipo(sel) {
  const row = sel.closest('tr');
  const isSvc = sel.value === 'servico';
  row.querySelector('.tipo-servico').style.display  = isSvc ? '' : 'none';
  row.querySelector('.tipo-material').style.display = isSvc ? 'none' : '';
}

function calcTotalItens() {
  const tbody = document.getElementById('tbody-itens');
  if (!tbody) return;
  let total = 0;
  tbody.querySelectorAll('tr').forEach(row => {
    const qty  = parseFloat(row.querySelector('input[name="item_qty[]"]')?.value || 1);
    const val  = parseFloat(row.querySelector('input[name="item_val[]"]')?.value || 0);
    const sub  = qty * val;
    total     += sub;
    const subEl = row.querySelector('.item-subtotal');
    if (subEl) subEl.textContent = fmtBRL(sub);
  });
  const el = document.getElementById('total-itens');
  if (el) el.textContent = fmtBRL(total);
}

/* ── UTILITÁRIOS ─────────────────────────────────────────── */
function fmtBRL(value) {
  return 'R$ ' + Number(value || 0).toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function esc(str) {
  return String(str || '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

/* ── CARREGAR CATÁLOGOS VIA API ──────────────────────────── */
async function carregarCatalogos() {
  try {
    const [svcs, mats] = await Promise.all([
      fetch('/api/servicos').then(r => r.json()),
      fetch('/api/materiais').then(r => r.json()),
    ]);
    window._servicos  = svcs;
    window._materiais = mats;
  } catch (e) {
    console.warn('Catálogos não carregados:', e);
  }
}

// Inicializa ao carregar
document.addEventListener('DOMContentLoaded', () => {
  // Carrega catálogos se houver formulário de OS ou orçamento
  if (document.getElementById('tbody-servico') ||
      document.getElementById('tbody-itens')) {
    carregarCatalogos();
  }
  // Calcula totais iniciais (para formulários de edição)
  calcTotal('servico');
  calcTotal('material');
  calcTotalItens();
  calcTotalPag();
});
