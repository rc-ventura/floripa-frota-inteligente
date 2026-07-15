<!--
Sync Impact Report
- Version change: 1.0.0 → 1.0.1 (PATCH — clarificação do formato de placa canônica)
- Modified principles: III — placa canônica passa a aceitar os dois formatos vigentes
  (antigo AAA9999 e Mercosul AAA9A99), normalização inalterada. Decisão registrada em
  docs/decisoes/ADR-001 e arquitetura v2 (§2, D7). Ratifica com o merge do MR da
  feature/001-fontes-dados-simuladas em dev.

Histórico anterior (1.0.0):
- Version change: (template sem versão) → 1.0.0
- Modified principles: n/a (adoção inicial — template preenchido pela primeira vez)
- Added sections:
  - Princípios I–VII (derivados dos critérios de aceite/avaliação do briefing do Desafio 13)
  - Restrições Adicionais (stack e convenções)
  - Fluxo de Trabalho (gitflow + speckit)
  - Governance
- Removed sections: nenhuma (comentários de exemplo do template removidos)
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — gate "Constitution Check" é genérico e passa a
    avaliar os princípios I–VII em tempo de plan; nenhuma edição necessária
  - ✅ .specify/templates/spec-template.md — sem referência a princípios específicos; alinhado
  - ✅ .specify/templates/tasks-template.md — sem referência a constitution; alinhado
  - ✅ .claude/skills/speckit-*/SKILL.md — comandos genéricos, sem referência desatualizada
- Follow-up TODOs: nenhum
-->

# Constitution — Desafio 13: Gestão Inteligente da Frota Municipal

Derivada do briefing oficial do desafio (`Desafio13_briefingFrotaMunicipal.docx`, fonte de
desempate) e dos seus critérios de aceite/avaliação, conforme consolidados em
`wiki/wiki_desafio13_frota_municipal.md` (matriz de rastreabilidade, marco legal) e
`wiki/arquitetura_tecnica_desafio13_v2.md` (decisões D1–D8; versão vigente — a v1 permanece
no repositório como histórico).

## Core Principles

### I. O critério de sucesso binário manda (demo-crítico primeiro)

O critério de sucesso da PoC é binário: **frota unificada em painel único + alerta preventivo
disparado antes do vencimento, em demonstração ao vivo e reproduzível**. Toda decisão de
priorização MUST favorecer o caminho demo-crítico (as 15 tasks marcadas 🔴 no kanban) sobre
qualquer refinamento fora dele. Trabalho que não contribui para o disparo ao vivo nem para um
critério de avaliação do briefing MUST ser questionado antes de entrar em uma sprint.

*Racional*: a banca avalia um resultado binário; feature elegante que não sustenta a demo não
pontua.

### II. Rastreabilidade total da origem

Todo dado exibido no painel MUST ser rastreável até a fonte e a carga que o trouxeram
(briefing 4.1; Lei 14.133 art. 75 §7º). Concretamente: toda tabela consolidada MUST carregar
`fonte_origem`; todo registro de staging MUST carregar carimbo de carga e identificação do
arquivo/endpoint; nenhum registro rejeitado pode ser descartado silenciosamente — rejeição
MUST ir para `log_qualidade` com motivo explícito (`placa_invalida`, `data_ausente`,
`duplicado`, ...).

*Racional*: rastreabilidade é exigência do briefing e trilha de auditoria legal; o
`log_qualidade` é a evidência direta, para a banca, do tratamento de inconsistências.

### III. Dado inconsistente é requisito, não exceção

As fontes municipais são heterogêneas por natureza (risco nº 1 do briefing). O sistema MUST
tratar dado sujo como entrada esperada: placa normalizada para o formato canônico —
maiúsculas, sem hífen, nos dois formatos vigentes (`AAA9999` antigo e `AAA9A99` Mercosul;
regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`, ver ADR-001) — antes de
qualquer cruzamento; parsing tolerante de datas e decimais; vocabulário padronizado;
deduplicação por chave natural. Diante de dado impossível de avaliar, o comportamento MUST
ser explícito (rejeição com motivo, alerta `dados_insuficientes`) — nunca falha silenciosa
nem omissão de veículo.

*Racional*: o comportamento diante de dados inconsistentes é critério de avaliação explícito
(briefing 5).

### IV. Conformidade desde a concepção (LGPD · LAI · Lei 14.133)

Conformidade não é etapa final: o briefing trata a ausência de estratégia de proteção de
dados como possível critério de desclassificação. Nenhum dado pessoal real MUST existir no
dataset: condutores nascem pseudonimizados (`condutor_pseudo`, padrão `COND-NNN`) desde a
geração, sem tabela de-para na PoC. A visão pública (LAI) MUST exibir apenas agregados,
exportáveis para transparência; a tensão LGPD × LAI MUST estar resolvida e documentada. Base
legal: execução de política pública (LGPD art. 7º/23), não consentimento.

*Racional*: risco de desclassificação + marco legal obrigatório do setor público.

### V. Parametrização como dados, não código

Limiares de manutenção MUST viver em `LIMIAR_CONFIG` (tabela por tipo de veículo × tipo de
manutenção, com antecedências), alteráveis ao vivo sem deploy (briefing 4.3). Parâmetros
operacionais (ex.: intervalo do ciclo) MUST ser configuráveis por variável de ambiente.
Constantes de negócio no código são violação desta constitution.

*Racional*: exigência do briefing e momento planejado da demo (alterar limiar e ver o alerta
reagir).

### VI. Camadas isoladas, comunicação só via banco, idempotência

Ingestão, armazenamento, processamento e apresentação são camadas isoladas: o dashboard nunca
lê arquivos-fonte, o motor nunca lê o pipeline — todos MUST se comunicar exclusivamente pelo
banco. Tudo que roda em ciclo MUST ser idempotente: pipeline executado N vezes sobre os
mesmos dados produz o mesmo estado; motor executado N vezes não duplica alertas ativos;
criação de esquema é re-executável. Falha de uma fonte MUST NOT derrubar o ciclo das demais.

*Racional*: é o princípio central da arquitetura — permite desenvolvimento em paralelo pela
equipe e agendamento automático sem supervisão.

### VII. Simplicidade sobre sofisticação, aberto e sem lock-in

Dado correto e claro vale mais que gráfico elaborado (briefing 4.2). Soluções MUST preferir o
caminho simples que atende ao critério de aceite; complexidade adicional MUST ser justificada
por um requisito do briefing (registrar em Complexity Tracking do plano ou em ADR). Todos os
componentes MUST ser open source, mantíveis pela equipe da Prefeitura ou fornecedores locais,
sem lock-in proprietário (briefing, sustentabilidade tecnológica).

*Racional*: viabilidade de implantação e manutenção no setor público é critério diferenciado
de avaliação (briefing 11).

## Restrições Adicionais

- Stack e decisões técnicas seguem as decisões D1–D8 da versão vigente do documento de
  arquitetura (`wiki/arquitetura_tecnica_desafio13_vN.md`; vigente: v2); mudança de decisão
  arquitetural MUST incrementar a versão daquele documento e registrar a alteração (ADR em
  `docs/decisoes/` quando apropriado).
- Idioma de trabalho: português em documentos e no código de domínio (tabelas, variáveis de
  negócio), conforme convenções da wiki (§7).
- O briefing oficial é o documento de desempate: em conflito entre artefatos, vale o
  briefing, depois a arquitetura versionada, depois as specs.

## Fluxo de Trabalho

- Gitflow: branches permanentes `main` (estável/apresentação) e `dev` (integração); cada spec
  vira `feature/<numero-nome>`; todo MR aponta para `dev` com ≥1 revisão de outro membro;
  `dev` → `main` somente em release/demo.
- Speckit: cada pasta em `specs/` contém apenas `spec.md` até alguém assumi-la; quem assume
  aponta `.specify/feature.json` para sua spec e gera `plan.md`/`tasks.md` na própria pasta.
  O gate "Constitution Check" do plano MUST avaliar os princípios I–VII.
- Tasks de compliance (🟡) MUST NOT ficar para a última hora: entram na mesma sprint da
  funcionalidade que as origina.

## Governance

Esta constitution prevalece sobre qualquer outra prática do projeto. Emendas exigem: proposta
registrada (MR para `dev`), concordância da equipe e atualização da versão abaixo segundo
versionamento semântico (MAJOR: remoção/redefinição incompatível de princípio; MINOR: novo
princípio ou expansão material; PATCH: clarificações). Todo MR MUST verificar aderência aos
princípios — em especial II (rastreabilidade), IV (conformidade) e VI (idempotência), que são
os critérios com risco direto de desclassificação ou de quebra da demo. Violações
justificáveis MUST ser registradas no Complexity Tracking do plano da feature.

**Version**: 1.0.1 | **Ratified**: 2026-07-13 | **Last Amended**: 2026-07-14
