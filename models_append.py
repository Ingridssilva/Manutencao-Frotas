
# ──────────────────────────────────────────────────────────
#  TROCA DE FLUIDOS (óleo, água, etc.)
# ──────────────────────────────────────────────────────────
class TrocaFluido(db.Model):
    __tablename__ = 'trocas_fluido'
    id               = db.Column(db.Integer, primary_key=True)
    veiculo_id       = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    tipo_fluido      = db.Column(db.String(30), nullable=False)  # oleo_motor, agua, oleo_caixa, etc.
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
            if km_rest <= 0:
                return 'vencido'
            if km_rest <= 500:
                return 'critico'
            if km_rest <= 1000:
                return 'atencao'
        if self.proxima_data:
            dias = (self.proxima_data - date.today()).days
            if dias <= 0:
                return 'vencido'
            if dias <= 7:
                return 'critico'
            if dias <= 30:
                return 'atencao'
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
    tipo            = db.Column(db.String(20), default='novo')   # novo, recapado
    dot             = db.Column(db.String(20))
    km_inicial      = db.Column(db.Integer, default=0)
    km_limite       = db.Column(db.Integer, default=80000)
    status          = db.Column(db.String(20), default='ativo')  # ativo, baixado, recapando
    vezes_recapado  = db.Column(db.Integer, default=0)
    custo_aquisicao = db.Column(db.Numeric(10, 2))
    fornecedor_id   = db.Column(db.Integer, db.ForeignKey('fornecedores.id'))
    observacoes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=now)
    updated_at      = db.Column(db.DateTime, default=now, onupdate=now)

    fornecedor  = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])
    posicoes    = db.relationship('PneuVeiculo',   back_populates='pneu', lazy='dynamic')
    recapagens  = db.relationship('PneuRecapagem', back_populates='pneu', cascade='all, delete-orphan')

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
        'DE': 'Dianteiro Esquerdo',
        'DD': 'Dianteiro Direito',
        'TE': 'Traseiro Esquerdo',
        'TD': 'Traseiro Direito',
        'TEE': 'Traseiro Externo Esquerdo',
        'TEI': 'Traseiro Interno Esquerdo',
        'TDE': 'Traseiro Externo Direito',
        'TDI': 'Traseiro Interno Direito',
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
    status        = db.Column(db.String(20), default='enviado')  # enviado, concluido, reprovado
    observacoes   = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=now)

    pneu       = db.relationship('Pneu',       back_populates='recapagens')
    fornecedor = db.relationship('Fornecedor', foreign_keys=[fornecedor_id])
