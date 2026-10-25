# Gestor SEBRAETEC

Sistema de acompanhamento de consultorias Sebraetec: painel, fluxo das 21 etapas, mapa da Paraíba,
análises por cidade/fornecedor/cliente, agenda, lembretes e relatórios em PDF.
Feito em Streamlit, com banco no Supabase.

## Telas

| Tela | O que tem |
|---|---|
| **Painel** | Indicadores, alertas (prazos, consultorias paradas, etapas que dependem do gestor, lembretes), próximos 14 dias, consultorias por etapa e cronograma |
| **Consultorias** | Lista ou quadro (kanban por fase), filtros por cidade e fase, nota de risco, ficha com linha do tempo das 21 etapas, botão *Avançar etapa* (grava data no histórico) e ficha em PDF |
| **Agenda e lembretes** | Calendário do mês (ou lista no celular) com compromissos, início/fim das consultorias e lembretes |
| **Inteligência** | Radar com alertas automáticos, matriz e ranking de risco, previsão de pagamentos por mês, fluxo área → fornecedor → cidade, composição do portfólio, benchmark de R$/hora e scorecard de fornecedores |
| **Mapa da Paraíba** | 223 municípios (malha do IBGE); cidades atendidas em azul, coloridas por quantidade, valor, média de horas ou R$/hora. Clicar no ponto de uma cidade abre as consultorias dela |
| **Análises** | Filtros no topo da página; visões por cidade, fornecedor (inclui tempo médio em cada etapa), cliente e financeiro; exportação CSV |
| **Relatórios em PDF** | Relatório para impressão com as seções escolhidas, respeitando os filtros |
| **Dados e cadastros** | Editor em planilha de tudo: consultorias, clientes, fornecedores, compromissos, lembretes, histórico de etapas e nomes das etapas (editar, acrescentar e excluir). Importação da planilha Excel e exportação no formato original |
| **Configurações** | Aparência (modo claro/escuro, paletas prontas ou cores próprias, plano de fundo, fonte, cantos), limites dos alertas do Painel, nome da plataforma, logo da instituição (ex.: Sebrae, mostrada na barra lateral, no login e nos PDFs), situação do banco |

**Nota de risco (0–100)** de cada consultoria ativa: prazo vencido (+50), termina em até 7 dias (+25) ou 15 dias (+10),
parada na mesma etapa fora da execução há mais de 30 dias (+25) ou 15 dias (+10), início já passou sem entrar em execução
(+30), em execução com mais de 90% do prazo consumido (+15). Até 19 = baixo, 20–49 = médio, 50+ = alto. As regras ficam em
`core/insights.py`.

**Fases** do fluxo: Articulação (1–6), Proposta (7–9), Contratação (10–14), Execução (15–16) e Encerramento (17–21).

Aparência e alertas ficam na tela **Configurações** e valem para todos os usuários (salvas na tabela
`configuracoes`). O tema é gerado em `.streamlit/config.toml` (não edite à mão) e a logo em `assets/`.

Funciona em computador, tablet e celular (no celular os indicadores ficam em duas colunas, a agenda vira lista
e as tabelas mostram só as colunas principais).

## Rodar no computador (modo local, sem Supabase)

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
.venv\Scripts\streamlit run streamlit_app.py
```

Sem a seção `[supabase]` no `secrets.toml`, o app usa um banco local (`data/local.db`) e os usuários de
`[local_users]`. Depois de entrar, importe a planilha em **Cadastros e importação → Importar planilha**.

## Ligar ao Supabase

1. Crie um projeto em [supabase.com](https://supabase.com).
2. Em **SQL Editor**, rode o arquivo [`supabase/schema.sql`](supabase/schema.sql). Ele cria as tabelas e libera
   leitura/escrita só para usuários logados.
3. Em **Authentication → Users**, crie o usuário do gestor (e-mail e senha). Em **Authentication → Sign In / Providers**
   pode desligar o cadastro público, já que só vocês vão criar usuários.
4. Em **Project Settings → API**, copie a *Project URL* e a chave *anon public* para o `.streamlit/secrets.toml`:

   ```toml
   [supabase]
   url = "https://SEU-PROJETO.supabase.co"
   key = "SUA-CHAVE-ANON"
   ```

5. Copie para o Supabase o que já está no banco local (consultorias, histórico, agenda, configurações):

   ```bash
   .venv\Scripts\python scripts\migrar_para_supabase.py
   ```

   O script pede o e-mail e a senha do usuário criado no passo 3. Pode rodar de novo sem duplicar nada.
   (Sem dados locais, basta entrar no app e importar a planilha em **Dados e cadastros**.)
6. Rode o app e entre com o mesmo e-mail e senha. A partir daí tudo é salvo no Supabase.

## Publicar na internet (Streamlit Community Cloud)

1. Suba esta pasta para um repositório no GitHub (o `.gitignore` já deixa de fora `secrets.toml`, o banco local,
   `.venv/`, `plugins/` e `skills/`).
2. Em [share.streamlit.io](https://share.streamlit.io), crie o app apontando para `streamlit_app.py`.
3. Em **Advanced settings → Secrets**, cole o conteúdo da seção `[supabase]`.

## Estrutura

```
streamlit_app.py        login + navegação
app_pages/              uma página por tela
core/db.py              acesso ao banco (Supabase ou SQLite local)
core/data.py            carga, cache, etapas e gravação
core/ui.py              filtros, formatação e gráficos
core/importer.py        leitura da planilha Excel
core/insights.py        nota de risco, alertas, previsão e benchmark
core/config_app.py      configurações, tema, plano de fundo e logo
assets/                 logo do app (gerada com as cores das Configurações) e logo da instituição (logo_instituicao.png/.svg)
core/pdf.py             relatórios em PDF
data/                   malha e lista de municípios da PB (IBGE)
supabase/schema.sql     tabelas do banco
tests/                  testes (pytest)
```

## Testes

```bash
.venv\Scripts\python -m pytest -q tests
```

Os testes usam um banco temporário semeado com a planilha da pasta: abrem todas as páginas, avançam e voltam uma
etapa e geram os PDFs.

## Observações

- Com **Manter conectado neste aparelho** marcado, o login vale por 7 dias, mesmo recarregando a página ou
  fechando o navegador. **Sair** encerra a sessão e apaga o cookie. No Supabase, o cookie guarda o refresh token
  da sessão, renovado a cada acesso. No modo local, guarda um token assinado (veja `[auth]` no `secrets.toml.example`).
- O histórico de etapas começa a contar a partir do uso do sistema. As consultorias importadas entram com a etapa
  da planilha, e as que estão em *Execução do projeto* contam desde a data de início da proposta.
- Para mudar as etapas, edite a lista `ETAPAS` em `core/data.py` (e a tabela `etapas_status` no banco).
