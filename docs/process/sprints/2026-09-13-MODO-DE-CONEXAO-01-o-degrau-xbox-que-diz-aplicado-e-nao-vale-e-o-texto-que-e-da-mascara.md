---
sprint: MODO-DE-CONEXAO-01
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  MODO-DE-CONEXAO-01:
    # PROVISÓRIA — o ESTUDO escreve a posse real antes de qualquer implementação.
    - src/hefesto_dualsense4unix/interface/aba01.py
    - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
    - src/hefesto_dualsense4unix/app/actions/jogar/painel.py
    - docs/process/sprints/2026-09-13-MODO-DE-CONEXAO-01-o-degrau-xbox-que-diz-aplicado-e-nao-vale-e-o-texto-que-e-da-mascara.md
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/interface/topo.html
---

# MODO-DE-CONEXAO-01 — o degrau Xbox que diz «aplicado» e não vale, e o texto que é da máscara

## A palavra dela — 13/09/2026, à tarde

> *"o modo de conexão do conexão da aba jogar nao ta funcionando.  o texto do modo do xbox tá errado aquilo é o texto da mascara do xbox"* <!-- noqa-acento: citação literal dela -->

Chegou com a onda 3 da [terceira lista](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)
em voo, e segue o processo dela (§0 do índice): esta sprint nasce antes de
qualquer agente, e são no máximo três agentes.

## A regra dela — 13/09/2026, minutos depois (DECIDIDA)

Três mensagens seguidas, com o estudo já em voo:

> *"o modo é base (ele o ps + r3) aí ap´os o modo de conexão, independente do escolhido anteriormente temos a máscara que é como o jogo se apresenta em termos de inputs apesar do modo de conexão escolhido. pode executar ela enquanto os demais trampam ali."* <!-- noqa-acento: citação literal dela -->
>
> *"eles precisam funcionar durante o jogo tá bom?"*
>
> *"inclusive o ps +r3 e isso fica setado no perfil"*

A regra que sai delas, e o estudo não escolhe mais:

1. **O MODO é a base:** o caminho de conexão (Sony DualSense · Xbox · Steam
   Input · Navegação). O chip e o **PS + R3** são o MESMO modo, um pela tela e o
   outro pelo controle.
2. **A MÁSCARA vem por cima, independente do modo:** é como o jogo vê a
   entrada, qualquer que seja o modo. O chip de modo não escreve nem lê a
   máscara, e o texto do modo não fala de como o jogo desenha os botões.
3. **Os dois valem DURANTE O JOGO**, com o jogo aberto, inclusive o PS + R3.
4. **O que o PS + R3 escolhe fica gravado no perfil**, como o clique no chip.

E a ordem de execução também é dela: esta sprint roda **junto com a onda 3**,
não depois.

## §E — O que quem coordena já leu e mediu (só leitura)

1. **O diário da janela instalada** (`~/.local/state/hefesto-dualsense4unix/interface.log`,
   a janela aberta às 13:44): sete `modo-xbox → aplicado`, o relato
   `pendente: ● Vai mudar para: Xbox`, e `aplicar` e `salvar` aplicados. O
   gesto diz que aplicou; ela diz que o modo não mudou.
2. **O que o degrau faz:** o «Xbox» é `Ponte(KIND_GAMEPAD, MASCARA_XBOX)` em
   `painel.CHIPS_DA_ESCADA`. O gesto `modo_xbox` despacha
   `_plano(MODE_GAMEPAD, "xbox")` e grava a escolha no perfil ativo
   (`_gravar_o_modo_do_chip`).
3. **A ordem da máscara** (`external_mask.mascara_efetiva`, MASCARA-NO-PERFIL-01,
   08/09): primeiro `controllers[uniq].mascara` do perfil ativo, depois
   `mode.gamepad_flavor`, depois o padrão. **Hipótese, ainda não medida:** o
   degrau escreve o segundo, e a máscara escolhida no cartão vence.
4. **A luz da fileira** (`modo-aceso` em `a01_jogar`) lê
   `mascara_do_aparelho(state)`, a máscara do aparelho: com o cartão em
   DualSense, o «Xbox» nunca acende.
5. **O texto:** `aba01.MODOS` dá ao «Xbox» *«O jogo desenha os botões do Xbox —
   o formato que todo jogo entende.»* e ao «Sony DualSense» *«O jogo desenha os
   botões do PlayStation.»*. As duas dizem como o jogo desenha os botões, que é o
   assunto dos chips de máscara dos cartões. O comentário acima de `MODOS` diz
   que a ordem em que o Hefesto tenta «mora na dica de cada modo», e nenhuma das
   quatro dicas publicadas a diz.
6. **A decisão dela de 31/08**, citada em `aba01.py`: *«Modo Hefesto se Ligado
   Abre as seções de Modo, Steam Input, Xbox, Sony DualSense, Point And Click.
   (…) E em Baixo temos a parte das Mascaras dos Controles.»* <!-- noqa-acento: citação literal dela -->
   Na tela dela, modo e máscara são duas camadas.
7. **A tela e o painel confessam o defeito na própria prosa:** a dica do Estilo
   Navegação em `aba01.py` e o cabeçalho de `painel.py` dizem que escolher
   DualSense, Xbox ou Steam Input «não muda nada no daemon — quem muda é o PS +
   R3». O chip e o atalho, que pela regra dela são o mesmo modo, hoje são dois
   caminhos diferentes. O atalho mora em `daemon/subsystems/hotkey.py`
   (`build_next_bridge_callback`) e percorre `integrations/ponte_escada.ESCADA`,
   cujo degrau «Xbox» é `Ponte(gamepad, xbox)`: um degrau de modo que carrega
   uma máscara dentro.

## §2 — As perguntas do ESTUDO, nesta ordem

1. **O que o clique e o atalho mudam de verdade.** Com dublê de perfil e de
   daemon, sem tocar no dela: o que o chip muda, com e sem máscara escolhida no
   cartão; o que o PS + R3 muda, e se hoje grava no perfil; e se cada troca —
   chip, atalho e máscara — vale com o vpad já aberto por um jogo.
2. **O que hoje contradiz a regra dela**, com endereço: onde o modo lê ou
   escreve máscara (em especial o degrau «Xbox» da escada), e o que o modo
   «Xbox» passa a ser como caminho de conexão com a máscara separada. As
   decisões antigas que concordam ou caducam ganham nota datada, não somem:
   * a D-5 de 14–15/08 (máscara do jogador, com a do jogo como padrão herdado);
   * a de 03/09, «É uma máscara por controle»;
   * a MASCARA-NO-PERFIL-01;
   * a de 31/08, citada acima;
   * as decisões da aba Jogar de 04/09.
3. **O texto de cada modo:** o caminho que o Hefesto usa, sem repetir o que a
   máscara diz. Nenhuma frase de aviso, e nada que as decisões e o produto não
   sustentem.
4. **A cura, a posse real e as réguas:** a cura cobre o chip, o PS + R3, a
   gravação no perfil e a troca com o jogo aberto. Uma régua troca o modo com
   a máscara do cartão escolhida e confere que a máscara não mudou; outra
   confere que o PS + R3 grava no perfil; outra impede o texto da máscara na
   dica do modo. A posse cresce para o daemon e o perfil; o estudo diz arquivo
   por arquivo e aponta colisão com a onda 3.

## §0 — O processo

ESTUDO (só leitura) → quem coordena escreve aqui a rota e a posse → IMPLEMENTA →
VALIDA/CORRIGE. Nada de botão novo; tirar e enxugar pode.
