# Contrato — API Fake de Multas (Fonte 2)

**Branch**: `feature/001-fontes-dados-simuladas` | **Date**: 2026-07-14

Contrato do endpoint HTTP servido por `fake_api/main.py` (FastAPI, decisão D5). O pipeline
(spec 003) consome este endpoint como a Fonte 2 (multas). O JSON servido é gerado por
`data/gerador_dados.py` e persistido em `fake_api/multas.json`; a API apenas o serve (não
gera dados on-the-fly — ver `research.md` R5).

## Base URL

```
http://localhost:8000
```

Configurável via variável de ambiente `FAKE_API_PORT` (default `8000`). Em Docker Compose
(spec 007), o serviço se chamará `fake_api` e será acessível em `http://fake_api:8000`.

## Endpoints

### `GET /multas`

Retorna a lista completa de multas simuladas.

**Resposta 200** — `application/json`:

```json
[
  {
    "placa": "abc1234",
    "data": "2026-05-20",
    "valor": 130.16,
    "condutor": "COND-042",
    "cnh": "01234567890",
    "situacao": "pendente",
    "codigo_infracao": "7455-1"
  }
]
```

**Schema do item** (ver `data-model.md` § Fonte 2 para detalhes das inconsistências):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `placa` | string | sim | Placa em **minúsculas, sem hífen** (inconsistência propositais; o pipeline normaliza para `AAA9999`) |
| `data` | string (`aaaa-mm-dd`) | sim | Data da infração |
| `valor` | number (float) | sim | Valor da multa em BRL (ponto decimal) |
| `condutor` | string | sim | Pseudônimo `COND-NNN` (LGPD — nenhum nome real) |
| `cnh` | string (11 dígitos) | sim | CNH sintética não-real (checksum inválido; espelha Bloco 3 do AIT — Portaria SENATRAN 354/2022). **Descartada pelo pipeline na carga consolidada.** |
| `situacao` | string | sim | `pendente` \| `paga` |
| `codigo_infracao` | string | sim | Código de enquadramento (Bloco 5 do AIT) |

**Erros**:
- `500` — erro ao ler `multas.json` (arquivo ausente ou malformado). O pipeline (spec 003)
  trata falhas de fonte isoladamente (constitution VI: "falha de uma fonte não derruba o
  ciclo").

---

### `GET /multas/{placa}`

Retorna as multas filtradas por placa. Conveniência para testes do extrator (spec 003); não
é requisito funcional da spec 001, mas nasce sem custo extra.

**Parâmetro de path**: `placa` — string, comparada em minúsculas (espelha o formato da fonte).

**Resposta 200** — `application/json`: lista (possivelmente vazia) de itens com o mesmo
schema do `GET /multas`.

**Erros**: `404` não se aplica (lista vazia → `200` com `[]`); `500` como acima.

---

### `GET /health`

Health check para o scheduler/pipeline verificar disponibilidade antes de consumir.

**Resposta 200**:

```json
{ "status": "ok" }
```

## Como subir

```bash
uvicorn fake_api.main:app --reload --port 8000
```

Documentado em `fake_api/README.md`. Em Docker Compose (spec 007), sobe automaticamente.

## Notas de conformidade

- **LGPD (constitution IV)**: o campo `cnh` é sintético e não-real (ver `research.md` R2).
  O pipeline (spec 003) descarta `cnh` na carga consolidada; a tabela `MULTA` persiste
  apenas `condutor_pseudo`. A presença do campo na fonte é **evidência do desafio LGPD**
  (fontes reais carregam dado pessoal — o sistema trata minimizando na carga).
- **Rastreabilidade (constitution II)**: o extrator (spec 003) registra `fonte_origem`
  apontando para o endpoint (`http://fake_api:8000/multas`) e o carimbo de carga no
  staging. Este contrato documenta o endpoint para que o `fonte_origem` seja estável e
  reproduzível.
