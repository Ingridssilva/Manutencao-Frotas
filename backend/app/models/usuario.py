"""
Modelos SQLAlchemy — Sistema de Manutenção de Frota
Empresa Exemplo — versão corrigida e completa
"""
import uuid
from datetime import datetime, date, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


def new_uuid():
    return str(uuid.uuid4())

def now():
    return datetime.utcnow()


# ──────────────────────────────────────────────────────────
#  PERFIS E USUÁRIOS
# ──────────────────────────────────────────────────────────
class PerfilAcesso(db.Model):
    __tablename__ = 'perfis_acesso'
    id           = db.Column(db.Integer, primary_key=True)
    nome         = db.Column(db.String(50), nullable=False, unique=True)
    descricao    = db.Column(db.Text)
    pode_aprovar = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=now)
    usuarios     = db.relationship('Usuario', back_populates='perfil')


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id            = db.Column(db.String(36), primary_key=True, default=new_uuid)
    nome          = db.Column(db.String(150), nullable=False)
    email         = db.Column(db.String(150), nullable=False, unique=True)
    senha_hash    = db.Column(db.Text)
    azure_oid     = db.Column(db.String(100), unique=True)
    perfil_id     = db.Column(db.Integer, db.ForeignKey('perfis_acesso.id'), nullable=False)
    ativo         = db.Column(db.Boolean, default=True)
    ultimo_acesso = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=now)
    updated_at    = db.Column(db.DateTime, default=now, onupdate=now)

    perfil = db.relationship('PerfilAcesso', back_populates='usuarios')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        if not self.senha_hash:
            return False
        return check_password_hash(self.senha_hash, senha)

    @property
    def pode_aprovar(self):
        return self.perfil.pode_aprovar if self.perfil else False

    @property
    def is_admin(self):
        return self.perfil.nome == 'admin' if self.perfil else False

    def __repr__(self):
        return f'<Usuario {self.email}>'


# ──────────────────────────────────────────────────────────
#  CATEGORIAS
# ──────────────────────────────────────────────────────────
class CategoriaServico(db.Model):
    __tablename__ = 'categorias_servico'
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(100), nullable=False, unique=True)
    descricao  = db.Column(db.Text)
    ativo      = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now)
    servicos   = db.relationship('CatalogoServico', back_populates='categoria')


class CategoriaMaterial(db.Model):
    __tablename__ = 'categorias_material'
    id             = db.Column(db.Integer, primary_key=True)
    nome           = db.Column(db.String(100), nullable=False, unique=True)
    descricao      = db.Column(db.Text)
    unidade_padrao = db.Column(db.String(20))
    ativo          = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=now)
    materiais      = db.relationship('CatalogoMaterial', back_populates='categoria')


# ──────────────────────────────────────────────────────────
#  CATÁLOGOS
# ──────────────────────────────────────────────────────────
class CatalogoServico(db.Model):
    __tablename__ = 'catalogo_servicos'
    id               = db.Column(db.Integer, primary_key=True)
    categoria_id     = db.Column(db.Integer, db.ForeignKey('categorias_servico.id'), nullable=False)
    nome             = db.Column(db.String(200), nullable=False)
    descricao        = db.Column(db.Text)
    tempo_estimado_h = db.Column(db.Numeric(6, 2))
    valor_referencia = db.Column(db.Numeric(12, 2))
    ativo            = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)
    categoria        = db.relationship('CategoriaServico', back_populates='servicos')


class CatalogoMaterial(db.Model):
    __tablename__ = 'catalogo_materiais'
    id               = db.Column(db.Integer, primary_key=True)
    categoria_id     = db.Column(db.Integer, db.ForeignKey('categorias_material.id'), nullable=False)
    codigo           = db.Column(db.String(50))
    nome             = db.Column(db.String(200), nullable=False)
    descricao        = db.Column(db.Text)
    unidade          = db.Column(db.String(20), nullable=False)
    valor_referencia = db.Column(db.Numeric(12, 2))
    ativo            = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)
    categoria        = db.relationship('CategoriaMaterial', back_populates='materiais')


class CategoriaImplemento(db.Model):
    __tablename__ = 'categorias_implemento'
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(100), nullable=False, unique=True)
    descricao   = db.Column(db.Text)
    ativo       = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=now)
    implementos = db.relationship('CatalogoImplemento', back_populates='categoria')


class CatalogoImplemento(db.Model):
    __tablename__ = 'catalogo_implementos'
    id               = db.Column(db.Integer, primary_key=True)
    categoria_id     = db.Column(db.Integer, db.ForeignKey('categorias_implemento.id'), nullable=False)
    codigo           = db.Column(db.String(50))
    nome             = db.Column(db.String(200), nullable=False)
    descricao        = db.Column(db.Text)
    fabricante       = db.Column(db.String(150))
    valor_referencia = db.Column(db.Numeric(12, 2))
    ativo            = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)
    categoria        = db.relationship('CategoriaImplemento', back_populates='implementos')


# ──────────────────────────────────────────────────────────
#  FORNECEDORES
# ──────────────────────────────────────────────────────────
class Fornecedor(db.Model):
    __tablename__ = 'fornecedores'
    id            = db.Column(db.Integer, primary_key=True)
    razao_social  = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj          = db.Column(db.String(18), unique=True)
    tipo          = db.Column(db.String(50))
    telefone      = db.Column(db.String(20))
    email         = db.Column(db.String(150))
    endereco      = db.Column(db.Text)
    municipio     = db.Column(db.String(100))
    uf            = db.Column(db.String(2), default='PA')
    observacoes   = db.Column(db.Text)
    ativo         = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=now)
    updated_at    = db.Column(db.DateTime, default=now, onupdate=now)

    contratos_veiculo = db.relationship('ContratoVeiculo', back_populates='fornecedor')
    orcamentos        = db.relationship('Orcamento',       back_populates='fornecedor')
    ordens_servico    = db.relationship('OrdemServico',    back_populates='fornecedor')


# ──────────────────────────────────────────────────────────
#  VEÍCULOS
# ──────────────────────────────────────────────────────────
class Veiculo(db.Model):
    __tablename__ = 'veiculos'
    id                    = db.Column(db.Integer, primary_key=True)
    placa                 = db.Column(db.String(10), nullable=False, unique=True)
    descricao             = db.Column(db.String(200))
    marca                 = db.Column(db.String(80))
    modelo                = db.Column(db.String(100))
    ano_fabricacao        = db.Column(db.SmallInteger)
    ano_modelo            = db.Column(db.SmallInteger)
    cor                   = db.Column(db.String(50))
    chassi                = db.Column(db.String(50), unique=True)
    renavam               = db.Column(db.String(20))
    tipo_veiculo          = db.Column(db.String(80))
    tipo_propriedade      = db.Column(db.String(20), default='proprio')
    fornecedor_locacao_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    municipio_base        = db.Column(db.String(100))
    km_atual              = db.Column(db.Integer, default=0)
    status                = db.Column(db.String(30), default='ativo')
    foto_path             = db.Column(db.String(300))   # NOVO: foto do veículo
    observacoes           = db.Column(db.Text)
    created_at            = db.Column(db.DateTime, default=now)
    updated_at            = db.Column(db.DateTime, default=now, onupdate=now)
    created_by            = db.Column(db.String(36), db.ForeignKey('usuarios.id'))

    fornecedor_locacao = db.relationship('Fornecedor', foreign_keys=[fornecedor_locacao_id])
    contratos          = db.relationship('ContratoVeiculo',    back_populates='veiculo',   lazy='dynamic')
    crlv               = db.relationship('CRLV',               back_populates='veiculo',   uselist=False)
    laudos             = db.relationship('LaudoAcustico',      back_populates='veiculo',   lazy='dynamic')
    tacografos         = db.relationship('Tacografo',          back_populates='veiculo',   lazy='dynamic')
    seguros            = db.relationship('SeguroVeiculo',      back_populates='veiculo',   lazy='dynamic')
    planos             = db.relationship('PlanoManutencao',    back_populates='veiculo',   lazy='dynamic')
    ordens_servico     = db.relationship('OrdemServico',       back_populates='veiculo',   lazy='dynamic')
    multas             = db.relationship('Multa',              back_populates='veiculo',   lazy='dynamic')
    disponibilidades   = db.relationship('DisponibilidadeDiaria', back_populates='veiculo', lazy='dynamic')
    checklists         = db.relationship('Checklist',          back_populates='veiculo',   lazy='dynamic')
    log_km             = db.relationship('LogKm',              back_populates='veiculo',   lazy='dynamic')
    motoristas         = db.relationship('Motorista',          back_populates='veiculo_principal', lazy='dynamic')
    alertas            = db.relationship('Alerta',             back_populates='veiculo',   lazy='dynamic')

    @property
    def laudo_atual(self):
        return self.laudos.order_by(LaudoAcustico.data_emissao.desc()).first()

    @property
    def tacografo_atual(self):
        return self.tacografos.order_by(Tacografo.data_proxima_calibracao.desc()).first()

    @property
    def seguro_ativo(self):
        return self.seguros.filter_by(status='ativo').order_by(SeguroVeiculo.data_vencimento.desc()).first()

    @property
    def nome_display(self):
        return self.descricao or f'{self.marca or ""} {self.modelo or ""}'.strip() or self.placa

    def __repr__(self):
        return f'<Veiculo {self.placa}>'


# ──────────────────────────────────────────────────────────
#  CONTRATOS DOS VEÍCULOS
# ──────────────────────────────────────────────────────────
class ContratoVeiculo(db.Model):
    __tablename__ = 'contratos_veiculo'
    id              = db.Column(db.Integer, primary_key=True)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    fornecedor_id   = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    tipo_contrato   = db.Column(db.String(50), nullable=False)
    numero_contrato = db.Column(db.String(100))
    descricao       = db.Column(db.Text)
    data_inicio     = db.Column(db.Date, nullable=False)
    data_fim        = db.Column(db.Date)
    valor_mensal    = db.Column(db.Numeric(12, 2))
    valor_total     = db.Column(db.Numeric(12, 2))
    link_contrato   = db.Column(db.Text)
    status          = db.Column(db.String(20), default='ativo')
    observacoes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)
    created_by      = db.Column(db.String(36), db.ForeignKey('usuarios.id'))

    veiculo    = db.relationship('Veiculo',    back_populates='contratos')
    fornecedor = db.relationship('Fornecedor', back_populates='contratos_veiculo')


# ──────────────────────────────────────────────────────────
#  MOTORISTAS
# ──────────────────────────────────────────────────────────
class Motorista(db.Model):
    __tablename__ = 'motoristas'
    id                   = db.Column(db.Integer, primary_key=True)
    nome                 = db.Column(db.String(150), nullable=False)
    cpf                  = db.Column(db.String(14), unique=True)
    matricula            = db.Column(db.String(30))
    telefone             = db.Column(db.String(20))
    email                = db.Column(db.String(150))
    municipio            = db.Column(db.String(100))
    cnh_numero           = db.Column(db.String(30))
    cnh_categoria        = db.Column(db.String(10))
    cnh_validade         = db.Column(db.Date)
    cnh_primeira_hab     = db.Column(db.Date)
    cnh_pontos           = db.Column(db.SmallInteger, default=0)
    cnh_status           = db.Column(db.String(20), default='regular')
    veiculo_principal_id = db.Column(db.Integer, db.ForeignKey('veiculos.id'))
    ativo                = db.Column(db.Boolean, default=True)
    # Apto a dirigir — toggle independente de "ativo" (ex: motorista ativo no quadro,
    # mas temporariamente inapto por exame médico, suspensão, etc.)
    apto_dirigir         = db.Column(db.Boolean, default=True, nullable=False)
    apto_motivo          = db.Column(db.String(200))   # motivo quando marcado como inapto
    apto_atualizado_em   = db.Column(db.DateTime)
    apto_atualizado_por  = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    observacoes          = db.Column(db.Text)
    created_at           = db.Column(db.DateTime, default=now)
    updated_at           = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo_principal = db.relationship('Veiculo', back_populates='motoristas')
    ordens_servico    = db.relationship('OrdemServico', back_populates='motorista', lazy='dynamic')
    multas            = db.relationship('Multa',        back_populates='motorista', lazy='dynamic')
    checklists        = db.relationship('Checklist',    back_populates='motorista', lazy='dynamic')
    documentos        = db.relationship('MotoristaDocumento', back_populates='motorista',
                                         cascade='all, delete-orphan')

    @property
    def cnh_vencida(self):
        if self.cnh_validade:
            return self.cnh_validade < date.today()
        return False

    @property
    def cnh_dias_restantes(self):
        if self.cnh_validade:
            return (self.cnh_validade - date.today()).days
        return None

    def documento(self, tipo):
        """Retorna o documento anexado de um tipo específico (ou None)."""
        for d in self.documentos:
            if d.tipo == tipo:
                return d
        return None


# ──────────────────────────────────────────────────────────
#  DOCUMENTOS DO MOTORISTA (CNH, termos, etc. — anexo único por tipo)
# ──────────────────────────────────────────────────────────
class MotoristaDocumento(db.Model):
    __tablename__ = 'motoristas_documentos'
    __table_args__ = (db.UniqueConstraint('motorista_id', 'tipo', name='uq_motorista_doc_tipo'),)

    TIPOS = {
        'cnh':               'CNH',
        'termo_defensiva':   'Termo de Direção Defensiva',
        'termo_uso_veiculo': 'Termo de Uso de Veículos da Empresa',
    }

    id             = db.Column(db.Integer, primary_key=True)
    motorista_id   = db.Column(db.Integer, db.ForeignKey('motoristas.id'), nullable=False)
    tipo           = db.Column(db.String(30), nullable=False)   # cnh | termo_defensiva | termo_uso_veiculo
    nome_arquivo   = db.Column(db.String(180))
    url_sharepoint = db.Column(db.Text)
    sharepoint_id  = db.Column(db.String(150))
    uploaded_by    = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at     = db.Column(db.DateTime, default=now)

    motorista = db.relationship('Motorista', back_populates='documentos')

    @property
    def tipo_display(self):
        return self.TIPOS.get(self.tipo, self.tipo)


# ──────────────────────────────────────────────────────────
#  DOCUMENTAÇÃO
# ──────────────────────────────────────────────────────────
class CRLV(db.Model):
    __tablename__ = 'crlv'
    id              = db.Column(db.Integer, primary_key=True)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False, unique=True)
    exercicio       = db.Column(db.SmallInteger, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    emplacamento    = db.Column(db.String(50))
    proprietario    = db.Column(db.String(200))
    link_documento  = db.Column(db.Text)
    status          = db.Column(db.String(20), default='regular')
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo = db.relationship('Veiculo', back_populates='crlv')

    @property
    def dias_para_vencer(self):
        return (self.data_vencimento - date.today()).days


class LaudoAcustico(db.Model):
    __tablename__ = 'laudos_acusticos'
    id               = db.Column(db.Integer, primary_key=True)
    veiculo_id       = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    data_emissao     = db.Column(db.Date, nullable=False)
    data_vencimento  = db.Column(db.Date, nullable=False)
    empresa_emissora = db.Column(db.String(200))
    numero_laudo     = db.Column(db.String(100))
    resultado        = db.Column(db.String(50))
    link_documento   = db.Column(db.Text)
    observacoes      = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo = db.relationship('Veiculo', back_populates='laudos')


class Tacografo(db.Model):
    __tablename__ = 'tacografos'
    id                      = db.Column(db.Integer, primary_key=True)
    veiculo_id              = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    numero_serie            = db.Column(db.String(100))
    marca                   = db.Column(db.String(80))
    modelo                  = db.Column(db.String(80))
    data_instalacao         = db.Column(db.Date)
    data_ultima_calibracao  = db.Column(db.Date)
    data_proxima_calibracao = db.Column(db.Date, nullable=False)
    empresa_calibradora     = db.Column(db.String(200))
    link_certificado        = db.Column(db.Text)
    status                  = db.Column(db.String(20), default='regular')
    created_at              = db.Column(db.DateTime, default=now)
    updated_at              = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo = db.relationship('Veiculo', back_populates='tacografos')


class SeguroVeiculo(db.Model):
    __tablename__ = 'seguros_veiculo'
    id              = db.Column(db.Integer, primary_key=True)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    fornecedor_id   = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    numero_apolice  = db.Column(db.String(100))
    tipo_cobertura  = db.Column(db.String(100))
    data_inicio     = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    valor_premio    = db.Column(db.Numeric(12, 2))
    franquia        = db.Column(db.Numeric(12, 2))
    link_apolice    = db.Column(db.Text)
    status          = db.Column(db.String(20), default='ativo')
    observacoes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo    = db.relationship('Veiculo',    back_populates='seguros')
    fornecedor = db.relationship('Fornecedor')


# ──────────────────────────────────────────────────────────
#  PLANOS DE MANUTENÇÃO
# ──────────────────────────────────────────────────────────
class PlanoManutencao(db.Model):
    __tablename__ = 'planos_manutencao'
    id               = db.Column(db.Integer, primary_key=True)
    veiculo_id       = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    servico_id       = db.Column(db.Integer, db.ForeignKey('catalogo_servicos.id'), nullable=False)
    tipo             = db.Column(db.String(20), nullable=False)
    gatilho_tipo     = db.Column(db.String(10), nullable=False)
    intervalo_km     = db.Column(db.Integer)
    intervalo_dias   = db.Column(db.Integer)
    km_referencia    = db.Column(db.Integer)
    data_referencia  = db.Column(db.Date)
    proximo_km       = db.Column(db.Integer)
    proxima_data     = db.Column(db.Date)
    alerta_km_antes  = db.Column(db.Integer, default=500)
    alerta_dias_antes= db.Column(db.Integer, default=15)
    ativo            = db.Column(db.Boolean, default=True)
    observacoes      = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)
    created_by       = db.Column(db.String(36), db.ForeignKey('usuarios.id'))

    veiculo = db.relationship('Veiculo',         back_populates='planos')
    servico = db.relationship('CatalogoServico')

    @property
    def status_display(self):
        hoje = date.today()
        km_veiculo = self.veiculo.km_atual if self.veiculo else 0
        if self.proximo_km and km_veiculo and km_veiculo >= self.proximo_km:
            return 'vencido'
        if self.proxima_data and self.proxima_data < hoje:
            return 'vencido'
        if self.proximo_km and km_veiculo and km_veiculo >= (self.proximo_km - self.alerta_km_antes):
            return 'atencao'
        if self.proxima_data and self.proxima_data <= hoje + timedelta(days=self.alerta_dias_antes):
            return 'atencao'
        return 'ok'


# ──────────────────────────────────────────────────────────
#  ORÇAMENTOS
# ──────────────────────────────────────────────────────────
class Orcamento(db.Model):
    __tablename__ = 'orcamentos'
    id                   = db.Column(db.Integer, primary_key=True)
    numero               = db.Column(db.String(30), unique=True)
    veiculo_id           = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    fornecedor_id        = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    tipo_os              = db.Column(db.String(20), nullable=False)
    tipo_solicitacao     = db.Column(db.String(30), default='aquisicao_servico')
    # aquisicao_servico | aquisicao_peca_os | compra_peca_sem_os
    os_vinculada_id      = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'))
    descricao            = db.Column(db.Text, nullable=False)
    valor_total_estimado = db.Column(db.Numeric(12, 2))
    status               = db.Column(db.String(30), default='rascunho')
    solicitado_por       = db.Column(db.String(36), db.ForeignKey('usuarios.id'), nullable=False)
    data_solicitacao     = db.Column(db.DateTime, default=now)
    aprovado_por         = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    data_aprovacao       = db.Column(db.DateTime)
    motivo_rejeicao      = db.Column(db.Text)
    observacoes          = db.Column(db.Text)
    aprovacao_token      = db.Column(db.String(100), unique=True)
    aprovacao_token_exp  = db.Column(db.DateTime)
    created_at           = db.Column(db.DateTime, default=now)
    updated_at           = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo       = db.relationship('Veiculo',    foreign_keys=[veiculo_id])
    fornecedor    = db.relationship('Fornecedor', back_populates='orcamentos')
    solicitante   = db.relationship('Usuario',    foreign_keys=[solicitado_por])
    aprovador     = db.relationship('Usuario',    foreign_keys=[aprovado_por])
    # os_vinculada: este orçamento aponta para uma OS (FK os_vinculada_id no orçamento)
    os_vinculada  = db.relationship('OrdemServico', foreign_keys='Orcamento.os_vinculada_id')
    # ordens_servico: OS que foram geradas a partir deste orçamento (FK orcamento_id na OS)
    ordens_servico= db.relationship('OrdemServico', foreign_keys='OrdemServico.orcamento_id', back_populates='orcamento')
    itens         = db.relationship('OrcamentoItem',    back_populates='orcamento', cascade='all, delete-orphan')
    cotacoes      = db.relationship('OrcamentoCotacao', back_populates='orcamento', cascade='all, delete-orphan')
    ordens_compra = db.relationship('OrdemCompra',      back_populates='orcamento')


class OrcamentoItem(db.Model):
    __tablename__ = 'orcamento_itens'
    id              = db.Column(db.Integer, primary_key=True)
    orcamento_id    = db.Column(db.Integer, db.ForeignKey('orcamentos.id', ondelete='CASCADE'), nullable=False)
    tipo_item       = db.Column(db.String(20), nullable=False)
    servico_id      = db.Column(db.Integer, db.ForeignKey('catalogo_servicos.id'))
    material_id     = db.Column(db.Integer, db.ForeignKey('catalogo_materiais.id'))
    descricao_livre = db.Column(db.Text)
    quantidade      = db.Column(db.Numeric(10, 3), default=1)
    valor_unitario  = db.Column(db.Numeric(12, 2), nullable=False)
    created_at      = db.Column(db.DateTime, default=now)

    orcamento = db.relationship('Orcamento', back_populates='itens')
    servico   = db.relationship('CatalogoServico')
    material  = db.relationship('CatalogoMaterial')

    @property
    def valor_total(self):
        if self.quantidade and self.valor_unitario:
            return float(self.quantidade) * float(self.valor_unitario)
        return 0

    @property
    def descricao_display(self):
        if self.servico:
            return self.servico.nome
        if self.material:
            return self.material.nome
        return self.descricao_livre or '—'


# ──────────────────────────────────────────────────────────
#  ORDENS DE SERVIÇO
# ──────────────────────────────────────────────────────────
class OrdemServico(db.Model):
    __tablename__ = 'ordens_servico'
    id                  = db.Column(db.Integer, primary_key=True)
    numero              = db.Column(db.String(30), unique=True)
    orcamento_id        = db.Column(db.Integer, db.ForeignKey('orcamentos.id'))
    veiculo_id          = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    tipo_os             = db.Column(db.String(20), nullable=False)
    tipo_manutencao     = db.Column(db.String(20), nullable=False)
    plano_id            = db.Column(db.Integer, db.ForeignKey('planos_manutencao.id'))  # CORRIGIDO
    fornecedor_id       = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    responsavel_id      = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    motorista_id        = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    km_abertura         = db.Column(db.Integer)
    descricao_problema  = db.Column(db.Text)
    data_abertura       = db.Column(db.Date, default=date.today)
    data_prevista       = db.Column(db.Date)
    data_conclusao      = db.Column(db.Date)
    data_entrada        = db.Column(db.DateTime)   # quando o carro chegou (OS aberta/criada)
    data_em_execucao    = db.Column(db.DateTime)   # quando entrou em manutenção
    data_aguardando_peca= db.Column(db.DateTime)   # quando foi para aguardando peça
    km_conclusao        = db.Column(db.Integer)
    status              = db.Column(db.String(30), default='aberta')
    aprovacao_status    = db.Column(db.String(20), default='pendente')   # pendente | aprovada | rejeitada
    aprovacao_token     = db.Column(db.String(120), unique=True, nullable=True)   # token do link de e-mail
    aprovacao_token_exp = db.Column(db.DateTime, nullable=True)                  # expira em 7 dias
    aprovacao_obs       = db.Column(db.Text, nullable=True)                       # obs do aprovador via e-mail
    aprovado_por        = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    aprovado_em         = db.Column(db.DateTime)
    motivo_rejeicao     = db.Column(db.Text)
    baixada             = db.Column(db.Boolean, default=False)
    baixada_em          = db.Column(db.DateTime)
    baixada_por         = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    custo_total         = db.Column(db.Numeric(12, 2))
    observacoes         = db.Column(db.Text)
    created_at          = db.Column(db.DateTime, default=now)
    updated_at          = db.Column(db.DateTime, default=now, onupdate=now)
    created_by          = db.Column(db.String(36), db.ForeignKey('usuarios.id'))

    veiculo        = db.relationship('Veiculo',         back_populates='ordens_servico')
    orcamento      = db.relationship('Orcamento', foreign_keys='OrdemServico.orcamento_id', back_populates='ordens_servico')
    fornecedor     = db.relationship('Fornecedor',      back_populates='ordens_servico')
    responsavel    = db.relationship('Usuario',         foreign_keys=[responsavel_id])
    criador        = db.relationship('Usuario',         foreign_keys=[created_by])
    aprovador      = db.relationship('Usuario',         foreign_keys=[aprovado_por])
    baixador       = db.relationship('Usuario',         foreign_keys=[baixada_por])
    motorista      = db.relationship('Motorista',       back_populates='ordens_servico')
    plano          = db.relationship('PlanoManutencao')
    itens_servico  = db.relationship('OSItemServico',    back_populates='os', cascade='all, delete-orphan')
    itens_material = db.relationship('OSItemMaterial',   back_populates='os', cascade='all, delete-orphan')
    itens_implemento = db.relationship('OSItemImplemento', back_populates='os', cascade='all, delete-orphan')
    pagamentos     = db.relationship('OSPagamento',      back_populates='os', cascade='all, delete-orphan')

    @property
    def custo_calculado(self):
        s = sum(i.valor_total for i in self.itens_servico)
        m = sum(i.valor_total for i in self.itens_material)
        i = sum(i.valor_total for i in self.itens_implemento)
        return s + m + i

    STATUS_LABELS = {
        'aberta': 'Aberta',
        'em_execucao': 'Em execução',
        'aguardando_peca': 'Aguardando peça',
        'concluida': 'Concluída',
        'cancelada': 'Cancelada',
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)


class OSItemServico(db.Model):
    __tablename__ = 'os_itens_servico'
    id              = db.Column(db.Integer, primary_key=True)
    os_id           = db.Column(db.Integer, db.ForeignKey('ordens_servico.id', ondelete='CASCADE'), nullable=False)
    servico_id      = db.Column(db.Integer, db.ForeignKey('catalogo_servicos.id'))
    descricao_livre = db.Column(db.Text)
    quantidade      = db.Column(db.Numeric(10, 3), default=1)
    valor_unitario  = db.Column(db.Numeric(12, 2))
    executado_por   = db.Column(db.String(150))
    created_at      = db.Column(db.DateTime, default=now)

    os      = db.relationship('OrdemServico', back_populates='itens_servico')
    servico = db.relationship('CatalogoServico')

    @property
    def valor_total(self):
        if self.quantidade and self.valor_unitario:
            return float(self.quantidade) * float(self.valor_unitario)
        return 0

    @property
    def descricao_display(self):
        return self.servico.nome if self.servico else (self.descricao_livre or '—')


class OSItemMaterial(db.Model):
    __tablename__ = 'os_itens_material'
    id              = db.Column(db.Integer, primary_key=True)
    os_id           = db.Column(db.Integer, db.ForeignKey('ordens_servico.id', ondelete='CASCADE'), nullable=False)
    material_id     = db.Column(db.Integer, db.ForeignKey('catalogo_materiais.id'))
    descricao_livre = db.Column(db.Text)
    quantidade      = db.Column(db.Numeric(10, 3), default=1)
    valor_unitario  = db.Column(db.Numeric(12, 2))
    created_at      = db.Column(db.DateTime, default=now)

    os       = db.relationship('OrdemServico', back_populates='itens_material')
    material = db.relationship('CatalogoMaterial')

    @property
    def valor_total(self):
        if self.quantidade and self.valor_unitario:
            return float(self.quantidade) * float(self.valor_unitario)
        return 0

    @property
    def descricao_display(self):
        return self.material.nome if self.material else (self.descricao_livre or '—')


class OSItemImplemento(db.Model):
    __tablename__ = 'os_itens_implemento'
    id              = db.Column(db.Integer, primary_key=True)
    os_id           = db.Column(db.Integer, db.ForeignKey('ordens_servico.id', ondelete='CASCADE'), nullable=False)
    implemento_id   = db.Column(db.Integer, db.ForeignKey('catalogo_implementos.id'))
    descricao_livre = db.Column(db.Text)
    numero_serie    = db.Column(db.String(100))
    quantidade      = db.Column(db.Numeric(10, 3), default=1)
    valor_unitario  = db.Column(db.Numeric(12, 2))
    created_at      = db.Column(db.DateTime, default=now)

    os         = db.relationship('OrdemServico', back_populates='itens_implemento')
    implemento = db.relationship('CatalogoImplemento')

    @property
    def valor_total(self):
        if self.quantidade and self.valor_unitario:
            return float(self.quantidade) * float(self.valor_unitario)
        return 0

    @property
    def descricao_display(self):
        return self.implemento.nome if self.implemento else (self.descricao_livre or '—')


class OSPagamento(db.Model):
    __tablename__ = 'os_pagamentos'
    id              = db.Column(db.Integer, primary_key=True)
    os_id           = db.Column(db.Integer, db.ForeignKey('ordens_servico.id', ondelete='CASCADE'), nullable=False)
    numero_nf       = db.Column(db.String(50))
    valor           = db.Column(db.Numeric(12, 2), nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento  = db.Column(db.Date)
    forma_pagamento = db.Column(db.String(50))
    status          = db.Column(db.String(20), default='pendente')
    observacoes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)

    os = db.relationship('OrdemServico', back_populates='pagamentos')

    @property
    def vencido(self):
        return self.status == 'pendente' and self.data_vencimento < date.today()


# ──────────────────────────────────────────────────────────
#  MULTAS
# ──────────────────────────────────────────────────────────
class Multa(db.Model):
    __tablename__ = 'multas'
    id              = db.Column(db.Integer, primary_key=True)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    motorista_id    = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    auto_infracao   = db.Column(db.String(50))
    data_infracao   = db.Column(db.Date, nullable=False)
    local_infracao  = db.Column(db.Text)
    municipio       = db.Column(db.String(100))
    descricao       = db.Column(db.Text)
    pontos          = db.Column(db.SmallInteger, default=0)
    valor_original  = db.Column(db.Numeric(10, 2), nullable=False)
    valor_desconto  = db.Column(db.Numeric(10, 2))
    valor_pago      = db.Column(db.Numeric(10, 2))
    data_vencimento = db.Column(db.Date)
    data_pagamento  = db.Column(db.Date)
    status          = db.Column(db.String(20), default='pendente')
    responsavel     = db.Column(db.String(20), default='empresa')
    observacoes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)
    created_by      = db.Column(db.String(36), db.ForeignKey('usuarios.id'))

    veiculo   = db.relationship('Veiculo',   back_populates='multas')
    motorista = db.relationship('Motorista', back_populates='multas')

    @property
    def valor_efetivo(self):
        if self.valor_desconto:
            return float(self.valor_original) - float(self.valor_desconto)
        return float(self.valor_original)


# ──────────────────────────────────────────────────────────
#  DISPONIBILIDADE DIÁRIA
# ──────────────────────────────────────────────────────────
class DisponibilidadeDiaria(db.Model):
    __tablename__ = 'disponibilidade_diaria'
    id                       = db.Column(db.Integer, primary_key=True)
    veiculo_id               = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    data                     = db.Column(db.Date, nullable=False)
    disponivel               = db.Column(db.Boolean, default=True)
    motivo_indisponibilidade = db.Column(db.String(100))
    os_id                    = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'))
    upe_impacto              = db.Column(db.Numeric(8, 3))
    observacoes              = db.Column(db.Text)
    lancado_por              = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at               = db.Column(db.DateTime, default=now)
    updated_at               = db.Column(db.DateTime, default=now, onupdate=now)

    __table_args__ = (db.UniqueConstraint('veiculo_id', 'data'),)

    veiculo = db.relationship('Veiculo', back_populates='disponibilidades')


# ──────────────────────────────────────────────────────────
#  CHECKLIST
# ──────────────────────────────────────────────────────────
class ChecklistItemConfig(db.Model):
    __tablename__ = 'checklist_itens_config'
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(100), nullable=False)
    obrigatorio = db.Column(db.Boolean, default=True)
    ordem       = db.Column(db.SmallInteger, default=0)
    ativo       = db.Column(db.Boolean, default=True)


class Checklist(db.Model):
    __tablename__ = 'checklists'
    id             = db.Column(db.Integer, primary_key=True)
    veiculo_id     = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    motorista_id   = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    data_checklist = db.Column(db.Date, default=date.today)
    km_atual       = db.Column(db.Integer)
    turno          = db.Column(db.String(20), default='manha')
    status_geral   = db.Column(db.String(30), default='aprovado')
    observacoes    = db.Column(db.Text)
    realizado_por  = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at     = db.Column(db.DateTime, default=now)

    veiculo   = db.relationship('Veiculo',   back_populates='checklists')
    motorista = db.relationship('Motorista', back_populates='checklists')
    respostas = db.relationship('ChecklistResposta', back_populates='checklist', cascade='all, delete-orphan')


class ChecklistResposta(db.Model):
    __tablename__ = 'checklist_respostas'
    id           = db.Column(db.Integer, primary_key=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey('checklists.id', ondelete='CASCADE'), nullable=False)
    item_id      = db.Column(db.Integer, db.ForeignKey('checklist_itens_config.id'), nullable=False)
    conforme     = db.Column(db.Boolean, nullable=False)
    observacao   = db.Column(db.Text)

    checklist = db.relationship('Checklist', back_populates='respostas')
    item      = db.relationship('ChecklistItemConfig')


# ──────────────────────────────────────────────────────────
#  LOG DE KM
# ──────────────────────────────────────────────────────────
class LogKm(db.Model):
    __tablename__ = 'log_km'
    id             = db.Column(db.Integer, primary_key=True)
    veiculo_id     = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    km_anterior    = db.Column(db.Integer)
    km_novo        = db.Column(db.Integer, nullable=False)
    origem         = db.Column(db.String(30), default='manual')
    referencia_id  = db.Column(db.Integer)
    data_registro  = db.Column(db.Date, default=date.today)
    registrado_por = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at     = db.Column(db.DateTime, default=now)

    veiculo = db.relationship('Veiculo', back_populates='log_km')


# ──────────────────────────────────────────────────────────
#  ALERTAS
# ──────────────────────────────────────────────────────────
class Alerta(db.Model):
    __tablename__ = 'alertas'
    id           = db.Column(db.Integer, primary_key=True)
    tipo         = db.Column(db.String(50), nullable=False)
    veiculo_id   = db.Column(db.Integer, db.ForeignKey('veiculos.id'))
    motorista_id = db.Column(db.Integer, db.ForeignKey('motoristas.id'))
    titulo       = db.Column(db.String(200), nullable=False)
    mensagem     = db.Column(db.Text)
    nivel        = db.Column(db.String(20), default='info')
    lido         = db.Column(db.Boolean, default=False)
    lido_por     = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    lido_em      = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=now)

    veiculo = db.relationship('Veiculo', back_populates='alertas')
# ──────────────────────────────────────────────────────────
#  TROCA DE FLUIDOS (óleo, água, etc.)
# ──────────────────────────────────────────────────────────
class TrocaFluido(db.Model):
    __tablename__ = 'trocas_fluido'
    id               = db.Column(db.Integer, primary_key=True)
    veiculo_id       = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    tipo_fluido      = db.Column(db.String(30), nullable=False)
    data_troca       = db.Column(db.Date, nullable=False, default=date.today)
    km_troca         = db.Column(db.Integer)
    km_proxima_troca = db.Column(db.Integer)
    intervalo_km     = db.Column(db.Integer, default=5000)
    intervalo_dias   = db.Column(db.Integer)
    proxima_data     = db.Column(db.Date)
    marca_produto    = db.Column(db.String(100))
    viscosidade      = db.Column(db.String(20))
    quantidade_litros= db.Column(db.Numeric(6, 2))
    custo            = db.Column(db.Numeric(10, 2))
    fornecedor_id    = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    os_id            = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'))
    observacoes      = db.Column(db.Text)
    created_by       = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo    = db.relationship('Veiculo',    foreign_keys=[veiculo_id])
    fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])

    TIPOS = {
        'oleo_motor':       'Óleo do Motor',
        'agua':             'Água / Aditivo',
        'oleo_caixa':       'Óleo da Caixa',
        'oleo_diferencial': 'Óleo do Diferencial',
        'fluido_freio':     'Fluido de Freio',
        'oleo_direcao':     'Óleo da Direção',
    }

    @property
    def tipo_display(self):
        return self.TIPOS.get(self.tipo_fluido, self.tipo_fluido)

    @property
    def km_restante(self):
        if self.km_proxima_troca and self.veiculo and self.veiculo.km_atual:
            return self.km_proxima_troca - self.veiculo.km_atual
        return None

    @property
    def status_alerta(self):
        km_rest = self.km_restante
        if km_rest is not None:
            if km_rest <= 0:   return 'vencido'
            if km_rest <= 500: return 'critico'
            if km_rest <= 1000:return 'atencao'
        if self.proxima_data:
            dias = (self.proxima_data - date.today()).days
            if dias <= 0:  return 'vencido'
            if dias <= 7:  return 'critico'
            if dias <= 30: return 'atencao'
        return 'ok'


# ──────────────────────────────────────────────────────────
#  PNEUS
# ──────────────────────────────────────────────────────────
class Pneu(db.Model):
    __tablename__ = 'pneus'
    id              = db.Column(db.Integer, primary_key=True)
    codigo          = db.Column(db.String(50))
    marca           = db.Column(db.String(80))
    modelo          = db.Column(db.String(80))
    dimensao        = db.Column(db.String(30))
    tipo            = db.Column(db.String(20), default='novo')
    dot             = db.Column(db.String(20))
    km_inicial      = db.Column(db.Integer, default=0)
    km_limite       = db.Column(db.Integer, default=80000)
    status          = db.Column(db.String(20), default='ativo')
    vezes_recapado  = db.Column(db.Integer, default=0)
    custo_aquisicao = db.Column(db.Numeric(10, 2))
    fornecedor_id   = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    observacoes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)

    fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])
    posicoes   = db.relationship('PneuVeiculo',   back_populates='pneu', lazy='dynamic')
    recapagens = db.relationship('PneuRecapagem', back_populates='pneu', cascade='all, delete-orphan')

    @property
    def posicao_atual(self):
        return self.posicoes.filter_by(ativo=True).first()

    @property
    def km_rodado(self):
        pos = self.posicao_atual
        if pos and pos.km_inicio and pos.veiculo:
            return (pos.veiculo.km_atual or 0) - pos.km_inicio
        return 0

    @property
    def pct_vida(self):
        if self.km_limite and self.km_limite > 0:
            return min(100, round(self.km_rodado / self.km_limite * 100, 1))
        return 0

    @property
    def status_desgaste(self):
        pct = self.pct_vida
        if pct >= 100: return 'vencido'
        if pct >= 85:  return 'critico'
        if pct >= 70:  return 'atencao'
        return 'ok'

    @property
    def nome_display(self):
        partes = [self.marca, self.modelo, self.dimensao]
        return ' '.join(p for p in partes if p) or f'Pneu #{self.id}'


class PneuVeiculo(db.Model):
    __tablename__ = 'pneus_veiculo'
    id          = db.Column(db.Integer, primary_key=True)
    pneu_id     = db.Column(db.Integer, db.ForeignKey('pneus.id'), nullable=False)
    veiculo_id  = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    posicao     = db.Column(db.String(30), nullable=False)
    data_inicio = db.Column(db.Date, default=date.today)
    km_inicio   = db.Column(db.Integer)
    data_fim    = db.Column(db.Date)
    km_fim      = db.Column(db.Integer)
    ativo       = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=now)

    pneu    = db.relationship('Pneu',    back_populates='posicoes')
    veiculo = db.relationship('Veiculo', foreign_keys=[veiculo_id])

    POSICOES = {
        'DE':   'Dianteiro Esquerdo',
        'DD':   'Dianteiro Direito',
        'TE':   'Traseiro Esquerdo',
        'TD':   'Traseiro Direito',
        'TEE':  'Traseiro Externo Esquerdo',
        'TEI':  'Traseiro Interno Esquerdo',
        'TDE':  'Traseiro Externo Direito',
        'TDI':  'Traseiro Interno Direito',
        'STEP': 'Estepe',
    }

    @property
    def posicao_display(self):
        return self.POSICOES.get(self.posicao, self.posicao)


class PneuRecapagem(db.Model):
    __tablename__ = 'pneus_recapagem'
    id            = db.Column(db.Integer, primary_key=True)
    pneu_id       = db.Column(db.Integer, db.ForeignKey('pneus.id'), nullable=False)
    data_envio    = db.Column(db.Date, nullable=False)
    data_retorno  = db.Column(db.Date)
    km_envio      = db.Column(db.Integer)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    custo         = db.Column(db.Numeric(10, 2))
    status        = db.Column(db.String(20), default='enviado')
    observacoes   = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=now)

    pneu       = db.relationship('Pneu',       back_populates='recapagens')
    fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])

"""
Modelo para fotos de OS — adicionar ao final de backend/app/models/usuario.py
"""

# Cole no final de usuario.py:

class OSFoto(db.Model):
    __tablename__ = 'os_fotos'
    id              = db.Column(db.Integer, primary_key=True)
    os_id           = db.Column(db.Integer, db.ForeignKey('ordens_servico.id', ondelete='CASCADE'), nullable=False)
    nome_arquivo    = db.Column(db.String(200), nullable=False)
    url_sharepoint  = db.Column(db.Text)           # link de visualização
    sharepoint_id   = db.Column(db.String(200))    # ID do item no Graph para deletar
    descricao       = db.Column(db.String(200))
    tipo            = db.Column(db.String(30), default='foto')  # foto, nf, comprovante
    uploaded_by     = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at      = db.Column(db.DateTime, default=now)

    os      = db.relationship('OrdemServico', backref=db.backref('fotos', lazy='dynamic', cascade='all, delete-orphan'))
    uploader= db.relationship('Usuario', foreign_keys=[uploaded_by])

class OSStatusLog(db.Model):
    """Histórico de mudanças de status de uma OS."""
    __tablename__ = 'os_status_log'
    id         = db.Column(db.Integer, primary_key=True)
    os_id      = db.Column(db.Integer, db.ForeignKey('ordens_servico.id', ondelete='CASCADE'), nullable=False)
    status_de  = db.Column(db.String(30))
    status_para= db.Column(db.String(30), nullable=False)
    usuario_id = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    obs        = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=now)

    os      = db.relationship('OrdemServico', backref=db.backref('status_log', lazy='dynamic', cascade='all, delete-orphan'))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])


# ──────────────────────────────────────────────────────────
#  COTAÇÕES DE ORÇAMENTO
# ──────────────────────────────────────────────────────────
class OrcamentoCotacao(db.Model):
    """Cotação de um fornecedor para um orçamento."""
    __tablename__ = 'orcamento_cotacoes'
    id               = db.Column(db.Integer, primary_key=True)
    orcamento_id     = db.Column(db.Integer, db.ForeignKey('orcamentos.id', ondelete='CASCADE'), nullable=False)
    fornecedor_id    = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    valor            = db.Column(db.Numeric(12, 2), nullable=False)
    prazo_dias       = db.Column(db.Integer)               # prazo de entrega/execução em dias
    condicoes        = db.Column(db.Text)                  # condições comerciais (ex: 50% à vista)
    observacoes      = db.Column(db.Text)
    anexo_url        = db.Column(db.String(500))           # link PDF da proposta
    status           = db.Column(db.String(20), default='pendente')  # pendente | aprovada | recusada
    aprovada_por     = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    aprovada_em      = db.Column(db.DateTime)
    justificativa    = db.Column(db.Text)                  # obrigatória quando não é a mais barata
    cadastrada_por   = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)

    orcamento  = db.relationship('Orcamento',  back_populates='cotacoes')
    fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])
    aprovador  = db.relationship('Usuario',    foreign_keys=[aprovada_por])
    cadastrador= db.relationship('Usuario',    foreign_keys=[cadastrada_por])
    itens      = db.relationship('OrcamentoCotacaoItem', back_populates='cotacao',
                                 cascade='all, delete-orphan', order_by='OrcamentoCotacaoItem.id')


class OrcamentoCotacaoItem(db.Model):
    """Item detalhado de uma cotacao — valor real negociado por peca."""
    __tablename__ = 'orcamento_cotacao_itens'
    id                = db.Column(db.Integer, primary_key=True)
    cotacao_id        = db.Column(db.Integer, db.ForeignKey('orcamento_cotacoes.id', ondelete='CASCADE'), nullable=False)
    orcamento_item_id = db.Column(db.Integer, db.ForeignKey('orcamento_itens.id', ondelete='SET NULL'))
    descricao         = db.Column(db.Text, nullable=False)
    quantidade        = db.Column(db.Numeric(10, 3), nullable=False, default=1)
    valor_unitario    = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    created_at        = db.Column(db.DateTime, default=now)

    cotacao        = db.relationship('OrcamentoCotacao', back_populates='itens')
    orcamento_item = db.relationship('OrcamentoItem',    foreign_keys=[orcamento_item_id])

    @property
    def valor_total(self):
        return float(self.quantidade or 1) * float(self.valor_unitario or 0)


# ──────────────────────────────────────────────────────────
#  ORDENS DE COMPRA
# ──────────────────────────────────────────────────────────
class OrdemCompra(db.Model):
    """Ordem de Compra gerada automaticamente ao aprovar uma cotação."""
    __tablename__ = 'ordens_compra'
    id               = db.Column(db.Integer, primary_key=True)
    numero           = db.Column(db.String(30), unique=True, nullable=False)
    orcamento_id     = db.Column(db.Integer, db.ForeignKey('orcamentos.id'), nullable=False)
    cotacao_id       = db.Column(db.Integer, db.ForeignKey('orcamento_cotacoes.id'), nullable=False)
    os_id            = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'))   # vínculo opcional
    fornecedor_id    = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    valor_total      = db.Column(db.Numeric(12, 2), nullable=False)
    prazo_dias       = db.Column(db.Integer)
    condicoes        = db.Column(db.Text)
    observacoes      = db.Column(db.Text)
    status           = db.Column(db.String(30), default='gerada')
    # gerada | enviada_fornecedor | em_aquisicao | finalizada | cancelada
    gerada_por       = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    gerada_em        = db.Column(db.DateTime, default=now)
    enviada_em                   = db.Column(db.DateTime)
    finalizada_em                = db.Column(db.DateTime)
    comprovante_url              = db.Column(db.String(500))
    # Nota Fiscal (upload de PDF, armazenado no SharePoint)
    nota_fiscal_url              = db.Column(db.String(500))
    nota_fiscal_sharepoint_id    = db.Column(db.String(200))
    nota_fiscal_nome             = db.Column(db.String(200))
    created_at                   = db.Column(db.DateTime, default=now)
    updated_at                   = db.Column(db.DateTime, default=now, onupdate=now)

    orcamento  = db.relationship('Orcamento',        back_populates='ordens_compra')
    cotacao    = db.relationship('OrcamentoCotacao')
    os         = db.relationship('OrdemServico',     foreign_keys=[os_id])
    fornecedor = db.relationship('Fornecedor',       foreign_keys=[fornecedor_id])
    gerador    = db.relationship('Usuario',          foreign_keys=[gerada_por])

    STATUS_LABELS = {
        'gerada':             'Gerada',
        'enviada_fornecedor': 'Enviada ao Fornecedor',
        'em_aquisicao':       'Em Aquisição',
        'finalizada':         'Finalizada',
        'cancelada':          'Cancelada',
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)


# ──────────────────────────────────────────────────────────
#  RESERVA DE VEÍCULO (requisição pública)
# ──────────────────────────────────────────────────────────
class ReservaVeiculo(db.Model):
    __tablename__ = 'reservas_veiculo'
    id              = db.Column(db.Integer, primary_key=True)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=True)
    # Dados do solicitante (sem login)
    nome_solicitante = db.Column(db.String(120), nullable=False)
    setor_solicitante= db.Column(db.String(100))
    contato          = db.Column(db.String(80))
    # Dados da reserva
    data_inicio      = db.Column(db.Date, nullable=False)
    data_fim         = db.Column(db.Date, nullable=False)
    destino          = db.Column(db.String(200), nullable=False)
    finalidade       = db.Column(db.Text)
    n_passageiros    = db.Column(db.SmallInteger, default=1)
    tipo_veiculo_pref= db.Column(db.String(80))   # preferência (opcional)
    # Ciclo de vida
    status           = db.Column(db.String(30), default='pendente')
    # pendente | aprovada | rejeitada | cancelada | concluida
    obs_admin        = db.Column(db.Text)
    aprovado_por     = db.Column(db.String(36), db.ForeignKey('usuarios.id'))
    aprovado_em      = db.Column(db.DateTime)
    created_at       = db.Column(db.DateTime, default=now)
    updated_at       = db.Column(db.DateTime, default=now, onupdate=now)

    veiculo   = db.relationship('Veiculo',  foreign_keys=[veiculo_id])
    aprovador = db.relationship('Usuario',  foreign_keys=[aprovado_por])

    STATUS_LABELS = {
        'pendente':  'Pendente',
        'aprovada':  'Aprovada',
        'rejeitada': 'Rejeitada',
        'cancelada': 'Cancelada',
        'concluida': 'Concluída',
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)
