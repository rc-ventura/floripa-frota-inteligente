# API fake de multas (Fonte 2 — spec 001)

Mini-API FastAPI que simula a integração com um sistema externo de multas (ex.: DETRAN).
Ela **apenas serve** o `multas.json` gerado por `data/gerador_dados.py` — regenerar os
dados e reiniciar a API é o caminho para atualizar o payload.

## Como subir

```bash
# gerar os dados primeiro (na raiz do repositório)
python data/gerador_dados.py

# subir a API (porta padrão 8000; ajuste com --port / variável FAKE_API_PORT)
uvicorn fake_api.main:app --port "${FAKE_API_PORT:-8000}"
```

## Endpoints

| Endpoint | Resposta |
|---|---|
| `GET /multas` | lista completa de multas (JSON) |
| `GET /multas/{placa}` | multas da placa (comparação em **minúsculas**, espelhando a fonte) |
| `GET /health` | `{"status": "ok"}` — usado pelo pipeline/scheduler |

Contrato completo: `specs/001-fontes-dados-simuladas/contracts/api_multas.md`.

Observações LGPD: o campo `cnh` é sintético (dígito verificador propositalmente
inválido) e é **descartado pelo pipeline** na carga consolidada; `gravidade` e
`codigo_infracao` são fonte-apenas (ADR-003).
