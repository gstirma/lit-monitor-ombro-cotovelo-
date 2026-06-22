# Vigilância de Literatura — Ombro e Cotovelo

Agente automatizado, **sem servidor** (roda no GitHub Actions), que a cada **3 dias**
busca os artigos **novos** sobre **ombro e cotovelo** em revistas de ortopedia e
envia um **digest por e-mail**. Captura apenas a "chamada" de cada artigo — **título,
autores, periódico, data, abstract, DOI/URL** —, nunca o texto integral.

**Fontes:** PubMed (E-utilities), SciELO (OAI-PMH) e OpenAlex (REST).
**Extras:** deduplicação por DOI/título entre fontes e execuções, ranqueamento e
resumo de 1–2 frases em português via API da Anthropic (opcional), digest em HTML
limpo agrupado por subtema (Ombro / Cotovelo) e por fonte, e backup como *artifact*.

---

## Estrutura

```
.
├── main.py                  # orquestrador
├── article.py               # dataclass Article + dedup/classificação
├── config.py                # carrega config.yaml
├── store.py                 # histórico de artigos (dashboard + dedup entre execuções)
├── enrich.py                # ranqueamento + resumo PT via Anthropic (opcional)
├── digest.py                # monta o HTML do e-mail
├── emailer.py               # envio SMTP
├── sources/
│   ├── pubmed.py            # esearch + efetch
│   ├── scielo.py            # OAI-PMH (ListRecords / Dublin Core)
│   └── openalex.py          # /works + reconstrução de abstract
├── docs/                    # <- GitHub Pages (a interface web)
│   ├── index.html          # dashboard: busca + filtros (JavaScript puro)
│   └── data/
│       ├── articles.json   # histórico (atualizado pelo agente a cada run)
│       └── meta.json       # contadores / data da última atualização
├── config.yaml              # TODA a configuração editável
├── requirements.txt
├── .env.example             # variáveis para rodar localmente
└── .github/workflows/digest.yml   # cron a cada 3 dias + workflow_dispatch
```

Cada fonte expõe `fetch(since_date, cfg) -> list[Article]`.

---

## Passo a passo (GitHub Actions)

### 1. Fork / suba o repositório
Faça **fork** (ou crie um repositório novo e suba estes arquivos).

### 2. Configure os Secrets
Em **Settings → Secrets and variables → Actions → New repository secret**, crie:

| Secret             | Obrigatório? | Exemplo / observação                              |
|--------------------|--------------|---------------------------------------------------|
| `SMTP_HOST`        | sim          | `smtp.gmail.com`                                  |
| `SMTP_PORT`        | sim          | `465` (SSL) ou `587` (STARTTLS)                   |
| `SMTP_USER`        | sim          | seu e-mail de envio                               |
| `SMTP_PASS`        | sim          | **senha de app** (não a senha normal — ver abaixo)|
| `EMAIL_FROM`       | opcional     | remetente (default = `SMTP_USER`)                 |
| `EMAIL_TO`         | sim          | destinatário do digest                            |
| `ANTHROPIC_API_KEY`| opcional     | só se `anthropic.enabled: true` no config         |
| `NCBI_API_KEY`     | opcional     | aumenta o rate limit do PubMed                    |

> **Gmail — senha de app:** ative a verificação em 2 etapas e gere uma senha de app
> em <https://myaccount.google.com/apppasswords>. Use os 16 dígitos em `SMTP_PASS`.
> (A senha normal do Gmail não funciona em SMTP.)

### 3. Ajuste o `config.yaml`
- `email.to` / `openalex.mailto`: seu e-mail.
- `journals`: lista de periódicos (edite à vontade).
- `window_days`: janela em dias (default 3).
- `anthropic.enabled`: `true` para resumos/ranqueamento por IA; `false` para desligar.
- `pubmed.restrict_to_journals`: `true` restringe à lista de periódicos; `false` busca
  em todo o PubMed pelos termos (mais cobertura).

### 4. Ative o GitHub Pages (a interface web)
**Settings → Pages →** em *Source* escolha **Deploy from a branch**, *Branch* = `main`
e *Folder* = **`/docs`**, e clique em **Save**. Em ~1 minuto o dashboard fica no ar em:

```
https://SEU-USUARIO.github.io/NOME-DO-REPO/
```

A página já abre vazia ("o agente ainda não rodou"); assim que o workflow roda pela
primeira vez, os artigos aparecem com **busca, filtros por Ombro/Cotovelo, por fonte e
por periódico**, e link direto para o DOI. O agente atualiza o `docs/data/articles.json`
e faz commit sozinho a cada execução — o Pages atualiza automaticamente.

> Repositório **público** → o dashboard (apenas metadados abertos) fica visível na web.
> Quer privado? Use um repositório privado **e** GitHub Pages privado (requer plano pago),
> ou rode o dashboard só localmente (ver abaixo).

### 5. Ajuste o cron (opcional)
Em `.github/workflows/digest.yml`, a linha:
```yaml
- cron: "0 8 */3 * *"   # a cada 3 dias, 08:00 UTC
```
O cron do GitHub é em **UTC**. Ex.: para ~08:00 no horário de Brasília (UTC−3),
use `0 11 */3 * *`.

### 6. Rode manualmente para testar
Aba **Actions → lit-digest → Run workflow**. Veja os logs, confira o e-mail e abra o
dashboard. O *artifact* `digest-<run_id>` traz o HTML do e-mail e o `articles.json`.

---

## A interface (dashboard)

- **Online (GitHub Pages):** link fixo, abre no celular/computador, atualiza sozinho.
- **Local:** sirva a pasta `docs/` por HTTP (o `fetch` não funciona via `file://`):
  ```bash
  python -m http.server 8137 --directory docs
  # abra http://localhost:8137
  ```

Recursos: busca (título/autor/periódico/abstract, sem acento), filtros por subtema,
fonte e periódico, ordenação por relevância ou data, recorte por período, resumo da
IA em destaque e link para o DOI.

---

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # preencha SMTP_*, EMAIL_TO, ANTHROPIC_API_KEY
set -a; source .env; set +a # exporta as variáveis

# teste sem enviar e sem marcar artigos como vistos:
python main.py --dry-run

# execução real:
python main.py
```

Flags úteis: `--dry-run` (não envia/não persiste), `--no-email`, `--days N`
(sobrescreve a janela), `--config caminho.yaml`.

O HTML fica em `output/digest-AAAA-MM-DD.html` mesmo sem e-mail configurado.

---

## Como confirmar os `set`/ISSN do SciELO

O endpoint OAI-PMH atual é `https://oai.scielo.org/request` (o antigo
`www.scielo.br/oai/scielo-oai.php` foi desativado). Os `setSpec` são o **ISSN**
do periódico (ex.: `0102-3616`) ou coleções (`com_*`). Liste-os com:

```bash
curl -s "https://oai.scielo.org/request?verb=ListSets" | grep -oE "<setSpec>[^<]*</setSpec>"
```

Use o `<setSpec>` correspondente no `scielo_set` do `config.yaml`. Para testar a janela:

```bash
curl -s "https://oai.scielo.org/request?verb=ListRecords&metadataPrefix=oai_dc&from=2026-06-01&until=2026-06-22&set=0102-3616"
```

> Observação: a *Revista Brasileira de Ortopedia* migrou de plataforma em ~2016, então
> o SciELO concentra o acervo mais antigo; artigos muito recentes podem não aparecer
> por essa via — o OpenAlex/PubMed cobre o restante.

> Os ISSNs no `config.yaml` são um ponto de partida — **confirme-os** antes de
> confiar 100%. Periódicos não indexados no SciELO não precisam de `scielo_set`.

---

## Como funciona a persistência (não repetir artigos)

O histórico fica em `docs/data/articles.json`, **versionado no repositório** — é o
mesmo arquivo que alimenta o dashboard. A cada execução o agente carrega esse arquivo,
descarta o que já está lá e acrescenta só os artigos novos, e o workflow faz `commit`
de volta. Assim, uma execução sempre enxerga tudo o que as anteriores capturaram.
Dedup por **DOI** (normalizado) e, na falta dele, por **título normalizado**.
O teto de itens guardados é `dashboard.max_items` no `config.yaml` (default 5000).

---

## Notas

- **Apenas metadados abertos.** Nada de texto integral é baixado ou armazenado.
- **Resiliência:** se uma fonte falhar, as outras seguem normalmente.
- **IA opcional:** sem `ANTHROPIC_API_KEY` (ou com `anthropic.enabled: false`), o
  digest sai igual, só sem o resumo em PT e o ranqueamento (a classificação por
  subtema continua, via palavras-chave).
- **Google Acadêmico** foi deixado de fora de propósito: não tem API oficial,
  o scraping é bloqueado em IPs de datacenter (Actions) e não entrega
  abstract/DOI/data confiáveis. PubMed + OpenAlex cobrem o mesmo material com
  metadados muito melhores.
- Inspirado no projeto `keith-hazleton/lit-monitor` (agendamento, dedup,
  ranqueamento por IA e digest por e-mail), acrescentando SciELO e OpenAlex.
```
