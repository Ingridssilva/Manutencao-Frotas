# Frotas & Manutenção

> Versão genérica/sanitizada, sem dados ou identidade de nenhuma empresa real. Todos os e-mails e domínios de exemplo usam `empresaexemplo.com.br`.

Sistema completo de gestão de frota de veículos: manutenção (ordens de serviço), orçamentos e cotações com aprovação por alçada de valor, controle de pneus e fluidos, documentos e vencimentos (CRLV, CNH, seguro, tacógrafo, laudo), multas, disponibilidade/reservas de veículos, checklists, relatórios/BI e exportação para Excel — com notificações por e-mail (Microsoft Graph) e WhatsApp, e upload de comprovantes para o SharePoint.

## Funcionalidades

- Ordens de serviço (OS) com fluxo de aprovação por alçada (valor da OS define quem aprova)
- Orçamentos/cotações com aprovação por token, sem precisar logar (link enviado por e-mail)
- Geração automática de PDF (De Acordo, Ordem de Compra, plano de manutenção)
- Controle de pneus (montagem, rodízio, recapagem) e fluidos por veículo
- Gestão de documentos e alertas de vencimento (CRLV, CNH, seguro, tacógrafo, laudo)
- Controle de multas
- Disponibilidade e reservas de veículos, com página pública de solicitação
- Checklists configuráveis
- Dashboard, relatórios de custo por veículo e exportação em Excel
- Login corporativo via Microsoft Entra ID (Azure AD), restrito a uma lista de e-mails
- Notificações por e-mail (Microsoft Graph) e WhatsApp (UltraMsg) para aprovações de alto valor
- Upload de fotos/comprovantes para o SharePoint (Microsoft Graph API)
- Geração de orçamento assistida por IA (opcional, via API da Anthropic)

## Stack

- **Backend:** Flask + SQLAlchemy + PostgreSQL (via `psycopg`), Flask-Login, MSAL
- **Frontend:** Templates Jinja2 + CSS/JS puro (com camada mobile dedicada e PWA)
- **Integrações:** Microsoft Graph API / OAuth2 (login SSO, e-mail, SharePoint), UltraMsg (WhatsApp), Anthropic API (opcional)
- **Deploy:** Render (`Procfile`, `render_cron.sh` para tarefas agendadas)

## Configuração

1. Instale as dependências:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Copie `backend/.env.example` para `backend/.env` e preencha com seus próprios valores.
3. Rode as migrações/scripts `add_*.py` necessários (ou use `flask db upgrade` se estiver usando Flask-Migrate).
4. Inicie o servidor:
   ```bash
   python run.py
   ```

## Estrutura do projeto

```
backend/    → app Flask (models, rotas, serviços de integração), scripts de migração
frontend/   → templates Jinja2 e assets estáticos (CSS/JS/PWA)
```

## Variáveis de ambiente

Veja `backend/.env.example` para a lista completa (banco de dados, Azure AD, SharePoint, e-mail, WhatsApp, IA).

## Licença

Projeto pessoal para fins de portfólio.
