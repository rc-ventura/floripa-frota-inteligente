# Checkpoint 1 — Entender, planejar e fundamentar

**Desafio 13 — Gestão Inteligente da Frota Municipal** · 1ª Jornada Incubintech

**Prazo de entrega:** 08/07/2026 às 23h59

**Situação:** Apta

---

## 1. Reformulação do problema

Hoje, um gestor de frota na Prefeitura de Florianópolis não sabe, com uma única consulta, se uma ambulância está com a revisão em dia, se há uma multa pendente ou se o licenciamento venceu. Essas informações moram em planilhas e sistemas separados que não conversam entre si, e a única forma de descobrir que algo está errado é quando o veículo já quebrou em serviço. Nesse momento, uma manutenção que custaria uma fração do valor se feita a tempo já virou uma emergência de custo três a cinco vezes maior, com o veículo parado e o serviço que ele prestava — coleta de resíduos, atendimento de emergência, transporte escolar — interrompido.

Esse problema afeta diretamente os servidores da Secretaria Municipal de Administração e das secretarias-fim que operam a frota, que hoje perdem tempo cruzando informações manualmente e descobrem falhas tarde demais para agir. Mas afeta, de forma ainda mais concreta, os cidadãos de Florianópolis: quem depende de uma ambulância disponível, de uma rua limpa ou de um ônibus escolar pontual sente o efeito de uma frota mal gerida, mesmo sem nunca ver uma planilha de manutenção.

O problema importa porque ele é evitável e caro ao mesmo tempo. Não falta tecnologia para resolvê-lo — falta um lugar único onde os dados já existentes conversem entre si e avisem, antes do vencimento, que uma revisão precisa acontecer. Sem isso, a administração pública continua pagando a conta mais cara — a da manutenção corretiva — por um problema de organização de informação, não de disponibilidade de recursos.

*(≈ 255 palavras — limite: 300)*

---

## 2. Visão geral da solução

Estamos construindo uma plataforma web que reúne, em um único painel, a situação de cada veículo da frota municipal — abastecimento, manutenção, multas e licenciamento — hoje espalhados em sistemas e planilhas isolados. Ao lado do painel, um motor de alertas monitora automaticamente a quilometragem rodada e o tempo decorrido desde a última manutenção de cada veículo, e avisa o gestor antes que o prazo da próxima revisão vença, em vez de esperar o problema aparecer.

Na prática, o gestor abre o painel e vê, de imediato, quais veículos precisam de atenção esta semana — revisão vencendo, documento a expirar, consumo fora do padrão — sem precisar consultar quatro fontes diferentes para montar esse quadro. Quando um veículo se aproxima do limite de quilometragem ou do prazo configurado para um tipo de manutenção, o sistema dispara um alerta visível no painel, permitindo que a intervenção seja programada com antecedência, em vez de feita às pressas depois de uma falha. Um terceiro bloco do painel consolida os custos da frota por veículo, período e tipo de despesa, dando ao gestor uma visão comparativa de onde o dinheiro está sendo gasto — útil, por exemplo, para identificar um veículo antigo cujo custo de manutenção já não compensa frente à compra de um veículo novo.

O diferencial da nossa abordagem está em resolver primeiro o problema de integração das fontes administrativas que já existem — abastecimento, multas, licenciamento — usando a placa do veículo como chave comum entre elas, sem depender de hardware de rastreamento instalado nos veículos (telemetria), que é caro e está fora do alcance da maioria dos municípios. Isso torna a solução mais barata de implantar e mais aderente à realidade de uma prefeitura, em comparação com soluções comerciais do mercado que dependem de equipamento embarcado.

*(≈ 296 palavras — limite: 500, mais 1 diagrama simples)*

---

## 3. Prova de Conceito (PoC) realista

Vamos apresentar um protótipo web funcional com dados fictícios, mas com estrutura idêntica à de uma frota real. A demo ao vivo mostrará: (1) um painel único listando os veículos da amostra com sua situação de manutenção, multas e licenciamento; (2) o motor de alertas disparando, em tempo real durante a apresentação, um aviso de manutenção preventiva para um veículo previamente configurado para estar próximo do limite de quilometragem ou de tempo; e (3) um painel de custos consolidando os gastos simulados por veículo e por categoria, com pelo menos uma comparação entre veículos.

A demonstração será feita ao vivo, com um roteiro ensaiado: a equipe mostrará o veículo antes do alerta (situação normal), alterará um parâmetro de teste (quilometragem ou data) e mostrará o alerta aparecendo no painel, comprovando que o disparo acontece antes do vencimento da revisão, não depois. Um vídeo gravado do mesmo cenário servirá como plano B, caso algo falhe tecnicamente na hora da apresentação.

O que ainda não estará pronto: a integração com sistemas legados reais da Prefeitura (usaremos dados simulados com estrutura representativa, já que o acesso a sistemas reais depende de disponibilização pela organização); notificação por canal externo (SMS/e-mail) além do alerta visual no painel; telemetria veicular, que o próprio desafio trata como opcional e fora do escopo prioritário; e refinamentos de usabilidade que dependeriam de testes mais extensos com usuários reais do perfil de gestor público. O foco do protótipo é validar que a integração de dados dispersos e o motor de alertas preventivos funcionam de ponta a ponta.

*(≈ 257 palavras — limite: 300)*

---

## 4. Composição da equipe

| **Nome completo** | **Papel na equipe** | **Principais habilidades** | **LinkedIn** | **Instagram** |
| --- | --- | --- | --- | --- |
| Rafael Ventura | Líder | — | [preencher] | [preencher] |
| Mauricio Telles Silva Bichels | — | — | [preencher] | [preencher] |
| Julio Barbosa de Souza | — | — | [preencher] | [preencher] |
| Michael Torres Faleiro | — | — | [preencher] | [preencher] |
| João Victor Duarte | — | — | [preencher] | [preencher] |

> **Pendência conhecida:** LinkedIn e Instagram dos integrantes ainda pendentes de preenchimento.

---

## 5. Termo de compromisso

Item de processo, não de conteúdo — não é redigido pela equipe, apenas assinado e anexado.

**Checklist:**

- [x] Acessar o termo em tech.floripa.br/termo-de-compromisso/
- [x] Ler o documento por completo
- [x] Assinar digitalmente com Gov.br, nível prata ou ouro
- [x] Fazer upload do PDF assinado junto com este checkpoint

> **Atenção: sem o termo assinado, a equipe não prossegue para o próximo checkpoint, independentemente da qualidade do restante do conteúdo.**
