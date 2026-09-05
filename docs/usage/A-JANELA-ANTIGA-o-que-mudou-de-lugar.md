# A janela antiga — o que mudou de lugar

**05/09/2026.** Este documento existe para uma pessoa só: **quem lê um texto
antigo do Hefesto, procura na janela o que ele descreve, e não acha.**

A janela tinha **onze abas**. Hoje tem **dez**, e a aba **Emulação** foi a que
morreu — não porque o que ela fazia tenha sumido, mas porque o assunto dela se
espalhou por cinco donos. Nada do que estava lá ficou sem endereço.

- A lista viva das abas é `ABAS`, em
  `src/hefesto_dualsense4unix/interface/monta.py:137-140`.
- A decisão que matou a Emulação é a `D-A-EMULACAO-MORRE`, de 26/08/2026, em
  [O redesenho da janela — as dez abas](../process/2026-08-26-O-REDESENHO-as-dez-abas.md).
- O que cada aba de hoje faz está em
  [As dez abas — o que cada uma faz](AS-DEZ-ABAS-o-que-cada-uma-faz.md).
- A descrição da janela antiga, inteira, continua em
  [interface.md](interface.md), com a nota que diz que ela é a janela
  aposentada.

---

## As onze abas antigas, e onde procurar hoje

| Aba antiga | Onde ela está hoje | O que mudou no caminho |
|---|---|---|
| **Início** | **Jogar** (1) | Os três modos ("Controlar o PC · Jogar pelo Hefesto · Conexão Nativa") viraram o **Modo** de cinco degraus: Sony DualSense · Xbox · Steam Input · Navegação · Modo Nativo. A máscara deixou de ser da mesa e passou a ser **por controle**, com **Nintendo Pro** como terceira opção. "Reconciliar jogadores" chama-se **Reconectar Controles**. |
| **Status** | **Controles** (2) | O mesmo painel ao vivo, agora em linha por controle: a escolhida abre, as outras resumem. Ganhou o **Calibrar Sensores de Movimento** e o **Mapa do Controle**. |
| **No jogo** | **Controles** (2) | Deixou de ser aba. O que atravessa para o jogo entrou no cartão de cada controle — e **deixou de depender de um jogo da Steam aberto** para existir. |
| **Gatilhos** | **Gatilhos** (3) | Mesmo assunto. As colunas L2/R2 de um controle viraram **uma coluna por controle**, com os quatro na tela; os dois "Aplicar em L2 / em R2" saíram; nasceram **Meus efeitos** e **Guardar esse efeito**. |
| **Lightbar** | **Iluminação** (4) | Só mudou de nome, mais o desenho das cinco luzinhas, que **saiu** — quem troca o desenho troca o **número**. E a escolha do número, que brotava no cabeçalho, mora aqui. |
| **Rumble** | **Vibração** (5) | Nome em português. "Intensidade global" virou **Força da vibração**; "Vibração leve / forte" viraram **Motor direito / esquerdo**, com o punho dito na tela. |
| **Perfis** | **Perfis** (10) | O **Modo avançado** e os três campos crus (`window_class`, `title_regex`, `process_name`) saíram da tela; o motor continua usando-os. Nasceram o **Estilo de Jogo** (catorze mais o Personalizado), o **Detectar** e o **Voltar à de ontem**. |
| **Sistema** | **Sistema** (9) | Ganhou o diagnóstico da Emulação e o **Restaurar de fábrica**, que estava no rodapé como "Restaurar Default". O "Orçamento" da Configurações chegou como **Perfil de Bateria**. |
| **Emulação** | **morreu** — ver a seção abaixo | O **nome** foi para a aba **Lançadores** (7), com assunto novo: de onde os seus jogos vêm. |
| **Navegação** | **Navegação** (6) | Recebeu da Emulação o quadro que ensina os combos e os dois botões do modo jogo. A tabela "Mapeamento", que era só leitura, virou as **21 linhas** que se editam. |
| **Configurações** | **Conexões** (8) | Virou a aba do ambiente: entradas, rádio, adaptadores e declaração por controle. O número do jogador saiu para a **Iluminação** e o "Orçamento" para a **Sistema**. |

> **A ordem da tira não é a do documento de redesenho.** Lá a Sistema era a
> sétima e a Lançadores a décima; ela mandou trocá-las em 28/08/2026, e o
> produto renumerou — hoje a sétima é **Lançadores** e a nona é **Sistema**
> (`monta.py:128-140`). Um documento que cite "a sétima aba" pode estar falando
> da Sistema.

---

## A aba Emulação, pedaço por pedaço

A Emulação misturava quatro assuntos: diagnóstico da máquina, modo e máscara,
os combos do controle e o microfone. Cada um foi para o dono certo. A lista
abaixo é a da `D-A-EMULACAO-MORRE`, e a própria página da aba Lançadores a
repete no rodapé dela (`interface/paginas/07-lancadores.html`).

| O que havia na Emulação | Para onde foi |
|---|---|
| **Desligado / DualSense (PS) / Xbox 360** | **Jogar** (1) e **Perfis** (10). Eram os mesmos três botões da aba Início, chamando o mesmo código com outro vocabulário. |
| **Gamepad para os jogos** | **Jogar** (1) — é a máscara, e ela hoje é por controle. |
| **UINPUT · Device · Código do fabricante · Controles detectados** | **Sistema** (9), como diagnóstico da máquina. |
| **Testar o controle virtual** | **Sistema** (9) — é autoteste de instalação, não ajuste de jogo. |
| **Atualizar** | **Sistema** (9), fundido com o "Atualizar" que já existia lá. |
| **Modo jogo: Suspender mouse e teclado · Sair do modo jogo** | **Navegação** (6), junto do gesto que os liga. |
| **O quadro dos combos (PS + Options, PS + cima, PS + baixo)** | **Navegação** (6), como "Os gestos do controle", desenhados no controle e com o **PS + R3** finalmente na tela. |
| **Buffer: 150** | **Navegação** (6), virou a frase *"apertar os dois botões em até 0,15 s conta como combo"*. |
| **Passthrough em emulação** | **saiu**: era decisão travada de propósito, não ajuste — um número exibido que gesto nenhum editava. |
| **Steam Input: Verificar** | **saiu como botão**: mede o mesmo que a linha de Steam Input do exame da **Sistema** (9), que ainda nomeia os jogos. |
| **Steam Input: Desligar** | **saiu como botão**: virou parte do conserto automático da **Sistema** (9). |
| **Microfone do DualSense: Ligar / Desligar** | **Conexões** (8) — se o microfone existe para esta máquina. O **volume** e o **mudo** ficaram na **Controles** (2), que é onde se pergunta quanto ele capta agora. |
| **O parágrafo de ajuda no meio da aba** | virou dica no ícone de interrogação, ao lado do título de cada quadro. |

---

## O cabeçalho e o rodapé também mudaram

| Antes | Hoje |
|---|---|
| **"Ajustes vão para:"** com um chip por controle | **"Selecionar:"** com `Todos` e um chip por controle, com número, cor do plástico e transporte |
| **"Número deste controle: 1 2 3 4"**, que brotava no cabeçalho | a coluna **Jogador** da aba **Iluminação** (4) |
| **"Editando: Controle N"** | saiu — a fita já diz de quem são os ajustes |
| nada sobre o perfil no cabeçalho | **Perfil ativo**, com o nome do perfil que está valendo |
| rodapé: Aplicar · Salvar Perfil · Importar · **Restaurar Default** | rodapé: Aplicar · Salvar Perfil · Importar · **Exportar**. O restaurar virou **Restaurar de fábrica**, na aba **Sistema** (9) |

A regra dos dois tempos continua a mesma, e é a que mais custa quando se
esquece: **Aplicar vale agora e não grava; Salvar Perfil grava.**

---

## O que não está em tela nenhuma hoje

Medido em 05/09/2026 por busca literal nas dez páginas de
`src/hefesto_dualsense4unix/interface/paginas/`. A ausência da frase não prova a
ausência do gesto — prova que **nenhuma das dez abas o oferece com esse nome**.

| O que era | Estado |
|---|---|
| **"Este jogo não funciona"** (aba Sistema) e **"Esconder os controles físicos neste jogo"** (aba Perfis) | fora das dez páginas. A aba Perfis registra, na própria página, que a caixinha saiu por decisão dela. |
| **"Tamanho do texto"** e **"Ambiente: COSMIC / GNOME / Outro"** (a seção "A janela" da antiga Configurações) | fora das dez páginas. A `D-A-ABA-DO-AMBIENTE-CHAMA-SE-CONEXOES` mandou-as para a Sistema; elas ainda não chegaram. |
| **"Desenho do P1 / P2 / P3 / P4 · Todas acesas · Todas apagadas · Aplicar o desenho"** | saíram por decisão — quem troca o desenho troca o número, na **Iluminação** (4). |
| **"Modo avançado"** e os campos `window_class` · `title_regex` · `process_name` | saíram da tela; o motor continua usando-os por baixo. |
| **"Passthrough em emulação"** e **"Buffer"** como número | saíram; o buffer virou frase em português na **Navegação** (6). |
| **"Voltar todos ao automático"** | virou o **Automático** de cada coluna da **Iluminação** (4). |

Se você achar uma delas viva na sua janela, é a janela que está certa e este
documento que envelheceu — abra uma linha dizendo isso.
