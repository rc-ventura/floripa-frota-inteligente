# Feature Specification: Demo, Empacotamento e Conformidade

**Feature Branch**: `feature/007-demo-empacotamento-conformidade`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Empacotar a aplicação para subir do zero em máquina limpa, documentar conformidade LGPD/LAI/Lei 14.133, quantificar impacto econômico e preparar o roteiro de demo ensaiado com vídeo plano B, conforme kanban Fase 4."

**Papel responsável**: ⚙️ Backend (empacotamento) + 📄 Docs (conformidade, impacto, pitch) + 👥 Todos (ensaio) · **Fases do kanban**: Fase 0 (task 5), Fase 4 (tasks 1–6) · **Depende de**: todas as anteriores (001–006) · 🔴 demo-crítico · 🟡 compliance

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sobe do zero em máquina limpa (Priority: P1)

Como avaliador (ou técnico da Prefeitura), quero subir a aplicação completa — banco, pipeline, agendador, motor e painel — com um único comando em uma máquina limpa, provando a viabilidade de implantação.

**Why this priority**: Demo-crítico: é o plano de contingência da apresentação (qualquer notebook serve) e argumento concreto de implantação (critério diferenciado do briefing, seção 11).

**Independent Test**: Em máquina sem nada do projeto instalado (além do runtime de containers), clonar o repositório e subir com um comando.

**Acceptance Scenarios**:

1. **Given** uma máquina limpa com o repositório clonado, **When** o comando único de subida é executado, **Then** banco e aplicação sobem, o ciclo agendado começa a rodar e o painel fica acessível.
2. **Given** a aplicação no ar, **When** o roteiro da demo é executado (depositar CSV de gatilho), **Then** o fluxo completo funciona idêntico ao ambiente de desenvolvimento.

---

### User Story 2 - Documento de conformidade LGPD/LAI/Lei 14.133 (Priority: P1)

Como responsável por conformidade, preciso do documento que consolida: base legal por campo com dado pessoal, pseudonimização adotada, resolução da tensão LGPD × LAI, política de retenção e a referência ao art. 75 §7º — partindo do mapeamento de campos pessoais feito na Fase 0.

**Why this priority**: O briefing trata ausência de estratégia de proteção de dados como possível critério de desclassificação; não pode ficar para a última hora (marcação 🟡 do kanban).

**Independent Test**: Revisar o documento contra o checklist do kanban (Fase 4 t2) e contra a tabela de conformidade da arquitetura (seção 10).

**Acceptance Scenarios**:

1. **Given** o modelo de dados final, **When** o documento é revisado, **Then** todo campo com dado pessoal está mapeado (Fase 0 t5) com sua base legal (execução de política pública — LGPD art. 7º/23, não consentimento).
2. **Given** o documento, **When** revisado, **Then** cobre: pseudonimização desde a origem, visão pública LAI com agregados, retenção/expurgo apoiado no carimbo de carga, e rastreabilidade Lei 14.133 via `fonte_origem` + `log_qualidade`.

---

### User Story 3 - Impacto econômico quantificado (Priority: P2)

Como jurado avaliando valor público, quero ver a estimativa de economia aplicada à frota simulada, usando benchmarks reconhecidos (manutenção corretiva 3–5× mais cara que preventiva; redução de 20–30% do custo com gestão preventiva).

**Why this priority**: Transforma a demo técnica em argumento de investimento; usa os custos consolidados da spec 006 como base.

**Independent Test**: Conferir que os números da análise derivam dos dados simulados + benchmarks citados com fonte.

**Acceptance Scenarios**:

1. **Given** os custos consolidados da frota simulada, **When** a análise é lida, **Then** apresenta estimativa quantificada de economia com os benchmarks aplicados e as fontes citadas.

---

### User Story 4 - Roteiro de demo ensaiado + plano B (Priority: P1)

Como equipe, precisamos do roteiro completo da apresentação ensaiado ≥3 vezes com o ciclo agendado real e cronometrado, mais um vídeo gravado do disparo do alerta como plano B.

**Why this priority**: Demo-crítico: a métrica de sucesso do hackathon é binária (alerta dispara ao vivo antes do vencimento); o vídeo é o seguro contra falha ao vivo.

**Independent Test**: Executar o roteiro do zero, cronometrar, e reproduzir o vídeo verificando que cobre o mesmo fluxo.

**Acceptance Scenarios**:

1. **Given** o roteiro escrito, **When** ensaiado, **Then** foram registrados ≥3 ensaios completos com o ciclo agendado em 1–2 min e tempo total dentro do limite da apresentação.
2. **Given** uma falha ao vivo, **When** o plano B é acionado, **Then** o vídeo mostra o roteiro completo do depósito do CSV até o alerta no painel.

---

### User Story 5 - Pitch e posicionamento (Priority: P3)

Como equipe, precisamos do discurso frente ao mercado: solução baseada em fontes administrativas sem hardware (sem rastreador/telemetria), baixo custo, open source e aderente ao setor público.

**Why this priority**: Fecha a apresentação, mas depende de tudo o mais existir para ter o que mostrar.

**Independent Test**: Pitch revisado pela equipe cobrindo os pontos de posicionamento definidos no kanban.

**Acceptance Scenarios**:

1. **Given** o material de pitch, **When** revisado, **Then** cobre: diferencial sem hardware, custo de implantação baixo, stack aberta mantível por equipe local e aderência a órgão público.

### Edge Cases

- Porta padrão ocupada na máquina da demo: subida documenta como remapear sem editar código.
- Máquina da demo sem internet: a subida não pode depender de downloads no momento da apresentação (imagens/dependências pré-baixadas ou instruções de preparo).
- Falha de qualquer componente ao vivo: roteiro define o ponto exato em que se aciona o vídeo plano B.
- Dados "sujos" acumulados de ensaios anteriores: procedimento de reset para estado inicial da demo em um passo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A aplicação completa MUST subir em máquina limpa com um único comando, do repositório clonado ao painel acessível com ciclo agendado rodando.
- **FR-002**: MUST existir procedimento de reset que devolve o ambiente ao estado inicial da demo (dados seeds, sem alertas de ensaios anteriores). O reset MUST regenerar os seeds com a **data-âncora do dia da apresentação** (`--data-ancora`, spec 001 FR-006) — sem isso o cenário determinístico se desloca no tempo (o veículo B estoura o limite de 180 dias e os licenciamentos "vencendo" já venceram).
- **FR-003**: O documento de conformidade MUST cobrir: mapeamento de campos com dado pessoal (Fase 0 t5), base legal por campo, pseudonimização, tensão LGPD × LAI e sua resolução, política de retenção e referência ao art. 75 §7º.
- **FR-004**: A análise de impacto econômico MUST aplicar benchmarks citados (corretiva 3–5× preventiva; redução 20–30%) aos custos da frota simulada, com memória de cálculo.
- **FR-005**: O roteiro da demo MUST estar escrito passo a passo, ensaiado ≥3 vezes com ciclo real e cronometrado; o primeiro passo do preparo é o reset com a data-âncora do dia (FR-002).
- **FR-006**: MUST existir vídeo gravado do roteiro completo (depósito do CSV → alerta no painel) como plano B.
- **FR-007**: O material de pitch MUST registrar o posicionamento de mercado definido no kanban (sem hardware, baixo custo, setor público).

### Key Entities

- **Roteiro de demo**: sequência de passos, tempos e responsáveis, incluindo ponto de acionamento do plano B.
- **Documento de conformidade**: artefato em `docs/` versionado no repositório.
- **Análise de impacto**: artefato em `docs/` com memória de cálculo sobre a frota simulada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Máquina limpa → aplicação completa no ar em ≤10 minutos com um único comando (medido em máquina que não é de nenhum dev do projeto).
- **SC-002**: ≥3 ensaios completos registrados, todos com o alerta disparando antes do vencimento simulado (métrica binária do briefing: 100% de sucesso nos ensaios).
- **SC-003**: Documento de conformidade cobre 100% dos campos com dado pessoal mapeados, cada um com base legal.
- **SC-004**: Reset do ambiente de demo em ≤1 comando e ≤2 minutos.

## Assumptions

- "Máquina limpa" = máquina com runtime de containers instalado e mais nada do projeto (decisão D6 da arquitetura).
- Na PoC todos os serviços de aplicação podem compartilhar um processo/container; a separação para produção fica documentada como evolução (arquitetura seção 8).
- O tempo-limite da apresentação será confirmado com a organização do hackathon; o roteiro deve caber com folga de ~20%.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 7-D6, 8 e 10)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 0 t5, Fase 4 t1–t6)
