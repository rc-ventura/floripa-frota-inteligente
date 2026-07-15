# ADR-001: Placa canônica aceita os dois formatos brasileiros (antigo `AAA9999` e Mercosul `AAA9A99`)

**Status**: Proposta — ratifica com o merge deste MR em `dev`
**Data**: 2026-07-14
**Spec relacionada**: [001-fontes-dados-simuladas](../../specs/001-fontes-dados-simuladas/spec.md)
**Altera**: `wiki/arquitetura_tecnica_desafio13_v2.md` (§2, §3.1, D7), constitution v1.0.1 (princípio III)

---

## Contexto

A arquitetura v1 e a constitution definem a placa canônica como `AAA9999` (3 letras + 4
números, maiúsculas, sem hífen) — o formato **antigo** de emplacamento brasileiro. Desde a
Resolução CONTRAN que implantou o padrão Mercosul (nacional a partir de 2018–2020), todo
veículo 0 km, transferido de proprietário/município ou reemplacado recebe placa no formato
`AAA9A99` (ex.: `ABC1D23`). Uma frota municipal em 2026, com veículos adquiridos nos últimos
~7 anos, seria **majoritariamente Mercosul** — um dataset simulado só com placas antigas é um
anacronismo que a banca pode notar de imediato, e um pipeline cuja regex canônica rejeita
placas Mercosul falharia no primeiro dado real da Prefeitura.

O custo da mudança é mínimo neste momento: nada foi implementado ainda (a spec 001 é o ponto
de partida do projeto).

## Decisão

A **placa canônica passa a aceitar os dois formatos vigentes no Brasil**:

- Antigo: `AAA9999` (3 letras + 4 dígitos)
- Mercosul: `AAA9A99` (3 letras + 1 dígito + 1 letra + 2 dígitos)

A **normalização não muda**: maiúsculas, sem hífen e sem espaços. A validação canônica usa uma
única regex que cobre ambos:

```regex
^[A-Z]{3}\d[A-Z\d]\d{2}$
```

O gerador de dados (spec 001) produz o cadastro com **~70% de placas Mercosul e ~30% no
formato antigo**, refletindo a composição plausível de uma frota renovada gradualmente.
Placa fora dos dois formatos continua sendo rejeitada pelo pipeline com motivo
`placa_invalida` (constitution II).

## Alternativas consideradas

### Alternativa A: manter apenas `AAA9999`

Manter o formato antigo como único canônico, documentando como simplificação de PoC.

**Por que não foi escolhida**:
- Anacronismo visível na demo (placas antigas não são mais emitidas desde ~2018);
- A regex canônica rejeitaria a maioria das placas de uma frota real — a PoC nasceria
  incompatível com o dado que pretende um dia receber;
- O custo de aceitar os dois formatos é uma regex, decidida antes de qualquer implementação.

**Vantagens** (não aproveitadas):
- Zero alteração em documentos já escritos.

### Alternativa B: somente Mercosul

**Por que não foi escolhida**:
- Frotas públicas mantêm veículos antigos por muitos anos; placas `AAA9999` seguem válidas
  em circulação (a troca só é obrigatória em transferência/reemplacamento) — excluí-las
  seria o erro inverso.

## Consequências

### Aceitas

- Realismo imediato do dataset e compatibilidade futura com dados reais da Prefeitura;
- A normalização (upper + strip de hífen/espaço) permanece idêntica — nenhuma complexidade
  adicional no transform da spec 003.

### Trade-offs

- Documentos que citavam `AAA9999` literalmente exigiram atualização coordenada — feita
  neste mesmo MR: arquitetura (v2), constitution (PATCH 1.0.1), CLAUDE.md, README, kanban
  (task F0-t3) e specs 001/002/003 (a regex canônica é o contrato).

### Condições que invalidam esta decisão

Esta decisão deve ser **revisitada** se:

1. O CONTRAN alterar novamente o padrão de emplacamento;
2. A amostra real da Prefeitura (se surgir) revelar identificador de reconciliação melhor
   que a placa (ver D7 — chassi/RENAVAM como desempate).

### Caminho de migração

1. Ajustar a regex canônica em um único ponto do transform (spec 003);
2. Regenerar os datasets (spec 001 é determinística — 1 comando).

## Referências

- [Ambito Jurídico — obrigatoriedade da placa Mercosul na transferência](https://ambitojuridico.com.br/e-obrigatorio-trocar-a-placa-para-mercosul-na-transferencia/)
- [CNH Simulado — formato da placa Mercosul (ABC1D23)](https://cnhsimulado.com.br/blog/placa-dos-veiculos-mercosul)
- [Jornal Contábil — o novo modelo de placa padrão Mercosul](https://jornalcontabil.com.br/noticia/tudo-que-voce-precisa-saber-sobre-o-novo-modelo-de-placa-padrao-mercosul/)
- Arquitetura v2: `wiki/arquitetura_tecnica_desafio13_v2.md` (§2, D7)
- ADRs relacionados: [ADR-002](ADR-002-persistir-km-hodometro-abastecimento.md), [ADR-003](ADR-003-calibracao-realismo-fontes-simuladas.md)
