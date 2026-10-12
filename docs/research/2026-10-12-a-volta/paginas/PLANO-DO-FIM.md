# O plano do fim: todas as sprints abertas, em ondas

12/10/2026, ~16h. Feito só lendo: o `dev` dela (`0044399e9`), as worktrees, o `git cherry` e as fichas da mesa.
Nada foi mudado em árvore nenhuma. **Conferido e corrigido por um advogado do diabo às ~16h20**: o que ele mudou, e
por quê, está na última seção.

**A conta, de uma vez:** a pasta de sprints tem 371 fichas. 148 estão fechadas, 182 abertas e 41 esperam ela.
Das 223 que faltam:

| onde está | quantas | o que falta |
| --- | --- | --- |
| código já no `dev` | 29 | só o carimbo (19 agora, 10 depois do olho dela na foto) |
| costuradas na fds-1, fora do `dev` | 16 | entrar na fds-2 e no fecho A |
| cortadas na metade (12 conjuntos) | 43 | retomar pelo diff, conferir, costurar |
| por fazer, em conjunto (args prontos ou a montar) | 86 | ondas 4 a 15 |
| esperam ela (palavra, bancada, gesto) | 49 | a bancada e as perguntas dela (39), as 5 da casa (gesto), a aprovação das instruções da casa (1) e 4 de bancada sem agente |
| novas, ainda sem ficha | ~10 | a onda 0 escreve (a cura do Sackboy primeiro) |

**O que muda no caminho:** a `integra/fds-1` não entra mais no `dev` por avanço simples. O push de 12/10 reescreveu
135 commits, e a fds-1 nasceu antes disso (`git merge-base` = `04f1cc352`; ela tem 167 commits além dele, o `dev`
tem 135). O `git cherry dev integra/fds-1` dá 49 `+`: 10 são commits da 1-11 com o hash velho (o assunto já está
no `dev`) e **39 são só da fds**. A integração nova, `integra/fds-2`, nasce do `dev` de agora e recebe os 39 por
`cherry-pick`. A lista em ordem está em `os-39-da-fds-em-ordem.txt`, ao lado deste arquivo.

**A3 caducou do jeito que estava escrita.** As 7 curas (`7436f0fb0 afc733ec7 561d08264 5a2bc8c60 df334d9f9
7d5c686a6 0044399e9`) já estão no `dev`. O passo certo agora é a fds-2 (onda 0).

---

## 1. Concluídas e no `dev`

- **Fechadas:** 148 fichas (`feita`, `absorvida`, `caducou`). Só em 12/10 o `sprint.py fechar` carimbou 80. A
  lista está em «Sprints fechadas» de `docs/process/estudos/2026-10-12-a-volta/ANDAMENTO.md`.
- **Integrações já dentro do `dev`** (ancestrais, +0): `integra/1-6-5`, `1-7`, `1-8`, `1-9`, `1-10`, `1-11` e
  `janela-ci`.
- **O fecho da 1-11** (12/10 ~14h05): portões 72/72, suíte 24/24, merge ff, install, push
  `12c1060dd..0044399e9`. A guarda do `dev` velho é a branch `guarda/antes-da-reescrita-1-11` (`29d620816`), e o
  mapa velho→novo está em `leva-1-11/mapa-da-reescrita-1210.txt`. **Falta o CI e o `--so publicar`.**
- **Código no `dev`, só falta o carimbo:** 29. Os commits estão no `dev` (conferido pelo assunto).
  - **Carimbo agora** (19): A-BANCADA-DE-MENTIRA, O-CAMINHO-DO-BLUEZ, A-CRUA-SO-ANDA, AS-CITACOES-CURTAS,
    A-PONTE-PAUSADA, O-CARTAO-DO-EXTERNO, AS-FERRAMENTAS-DA-LEVA, O-COSTURAR-ACEITA, A-JANELA-ABERTA-CABE,
    A-GRAVACAO-DO-YML, O-REGISTRO-DO-YML, AS-FERRAMENTAS-DE-MANUTENCAO, A-SONDA-DO-BLUEZ, A-CASA-NAO-DEIXA,
    O-DUBLE-DO-CONTROLE, A-WIKI-NASCE, O-ESTILO-DO-PERFIL-LIGA-O-MOTOR, O-PAD-CEDIDO-CALA, e
    A-SUITE-NAO-ACORDA-A-PLACA (`bdd548da0`).
  - **Como se carimba:** 28 das 29 estão `costurada`, e o `sprint.py fechar` mede a prova pelo `git cherry
    <integração> voo/<dir>`, não pelo `integra=` gravado. O hash velho da 1-11 não atrapalha: a reescrita só mudou
    mensagem, e o patch é o mesmo. Rodar com `LEVA` apontando para uma integração que já tem o código (a fds-2).
    **A exceção é a A-SUITE-NAO-ACORDA-A-PLACA:** a ficha diz `aberta`, não `costurada`, e o `fechar` recusa
    (rc=4). O código está no `dev` (`bdd548da0` é ancestral). Ela fecha à mão, com a linha datada.
  - **Carimbo depois do olho dela** (10, são de tela; a página de fotos da conferência já está no `dev`):
    A-LINHA-DO-EXTERNO-VOLTA-AOS-30-PX, AS-QUATRO-LINHAS-DA-08, O-NOME-DO-JOGADOR, O-PADRAO-DO-ALTO-FALANTE,
    A-TELA-PERGUNTA-AO-DONO, A-TELA-SEM-O-QUE-A-REGUA-ACEITA, O-PERFIL-ANTIGO-DE-VIBRACAO, TODO-TEXTO-QUE-ABRE,
    SO-A-PRIMEIRA-LETRA, e O-SELECIONAR-ACENDE (item T4 da bancada).
  - **Fora da conta, também só carimbo:** A-FORJA-NAO-TRAVA-NO-APT (forja-fds) já subiu no `origin/main` da
    Forja (`c2644c4`). O ciclo da ficha ainda diz `em-voo`: falta o `sprint.py costurar` com `--integra-repo`
    apontando para a Forja (o ramo não mora aqui), e só então o `fechar`.

## 2. Costuradas na integração, ainda fora do `dev`

16 sprints, todas na `integra/fds-1` (`d64dec414`). Entram no `dev` pela fds-2 (onda 0) e fecham no fecho A.

| conjunto | sprints |
| --- | --- |
| vibracao-fds | A-COR-E-O-NUMERO-DO-PERFIL, O-EM-TODOS-DO-GATILHO, A-FORCA-DA-VIBRACAO…FUNIL |
| perfis-fds | O-EDITOR-DA-ABA-PERFIS, O-ESTILO-CHEGA-AO-GATILHO, O-PERSONALIZADO-DESLIGA, A-RECEITA-DO-TATO, AS-MARCAS-VISUAL-NOVEL |
| mods-fds | AS-MODIFICACOES-RODAM-FORA-DO-DAEMON (12 commits, mais `d64dec414`, o censo dos contatos) |
| ferramentas-fora | A-CITACAO-CURTA-DO-DIFF, O-LOTE-DE-TESTES-ISOLA-O-WEBKIT, O-MOLDE-DA-SPRINT, O-NUMERO-DA-BARRA (o ciclo ainda diz `em-voo`; os 6 commits são equivalentes na fds-1) |
| regras-fora | A-DIVIDA-DA-BASE, AS-REGUAS-DO-RAMO-INTEIRO, O-COMENTARIO-COM-DOIS-PONTOS (o `0dc3625aa` entrou resolvido à mão como `cdd56d1d4`) |

- **O último `--rapido` da fds-1** (`e31c48a4a`) deu 4 vermelhos de 53: `contrato-ipc`, `citacoes-de-linha`,
  `contratos-de-fora` (curado em `d64dec414`, sem medida nova) e `comentario-cortado`. A fds-2 mede de novo.
- **Os achados dos conferentes** da mods e da perfis (`leva-fds/ACHADOS-PARA-SPRINT.md`) já viraram as sprints da
  volta P12 (seção 4, setor Perfis).

## 3. Cortadas na metade: 12 conjuntos, 75 commits fora da fds-1

As worktrees estão limpas, em `/mnt/Apate/Desenvolvimento/hefesto-voo/<dir>`. A conta é do `git cherry
integra/fds-1 voo/<dir>` (nunca `rev-list`). Nenhum par toca o mesmo arquivo, e cada uma faz merge limpo contra a
fds-1 e contra a 1-11. **Nunca retomar pelo `resumeFromRunId`**: os runs são de outra sessão. A retomada é pelo
diff.

| conjunto | `+` | topo | args | falta | run cortado |
| --- | --- | --- | --- | --- | --- |
| portoes | 12 | `d20c41696` | `portoes-ci.json` | conferir + final; a sprint 4 (O-VERMELHO-NOVO) mora só nos ignorados da worktree: `vermelhos_do_rapido.py`, um teste, 6 scripts e o `COMO-COORDENAR`; copiar antes | wf_84301b53-610 |
| ipc | 7 | `e4eb31011` | `q8-ipc.json` | conferir + final; o `agentes/ipc-fds/tudo.sh` nunca rodou | wf_1ab4f835-190 |
| parar | 7 | `01e35e596` | `q4-parar.json` | conferir | wf_2a589397-439 |
| solta | 7 | `a97dd9f09` | `q10-solta.json` | conferir | wf_e221eafc-88f |
| fora | 7 | `7cf31a548` | `q11-fora.json` | conferir; o topo é um `wip` a refazer (a catraca `.json` foi barrada pelo `rastro-no-ato.py`) | wf_24e6b95d-3d1 |
| pad | 5 | `06e3ec1be` | `q9-pad-virtual.json` | conferir; o `/tmp/padf/tudo.sh` está em `salvo-1010/tmp-dos-agentes.tar.zst` | wf_09b3024f-34c |
| som | 6 | `b1b8c3876` | `q3-som.json` | fechar o implementa pelo diff, depois conferir | wf_d251c4e4-05b (o implementa não fechou) |
| radio | 5 | `ad39557dc` | `q12-radio-vibra.json` | idem | wf_e57caa34-2fd (idem) |
| carga | 3 | `1aaf6038d` | `q6-carga.json` | idem | wf_aaeb55a1-e15 (idem) |
| lancadores | 5 | `cecdace53` | `lancadores-e-conexoes.json` | idem; o args traz a A-ABA-LANCADORES-GANHA-AS-MODIFICACOES, que espera ela: tirar antes de retomar | wf_52549f43-f1b (idem) |
| kyty | 4 | `5637dcc9f` | `kyty.json` | idem | wf_84617539-b50 (idem) |
| dsx | 7 | `b6c6c389b` | `q7-dsx-jogador.json` | idem; 3 das 4 fichas ainda dizem `estado: aberta` | wf_8a529d5b-c36 (idem) |

As bases são quatro: som, parar e fora em `681e3810a`; radio em `949147e58`; portoes, solta, ipc e pad em
`563243b1d`; carga, lancadores, kyty e dsx em `e31c48a4a`.

**A retomada de cada um** (`<x>` é o diretório, `<json>` o args, `<base>` a base da tabela acima; a mesa é só
leitura, as ferramentas se leem de lá):

```bash
F=/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix/docs/process/ferramentas-da-leva
C=~/.local/state/hefesto-casa/leva-fds/conjuntos
cat ~/.local/state/hefesto-casa/leva-fds/ONDA          # tem de dizer 2 (a onda 0 troca); o leva.env deriva INT e BRANCH daqui
cd /mnt/Apate/Desenvolvimento/hefesto-voo/<x>-fds
git status --short                                    # tem de sair vazio; se não, commit `wip(...)`
git cherry integra/fds-2 voo/<x>-fds | grep -c '^+'   # o que ainda falta na integração nova
git rebase --onto integra/fds-2 <base> voo/<x>-fds    # leva SÓ os commits do conjunto (os da tabela)
# NUNCA `git rebase integra/fds-2` sozinho: o merge-base com o dev é 04f1cc352, e ele reaplicaria
# de 146 a 169 commits, entre eles os 10 da 1-11 com hash velho, com conflito
# os args apontam para a fds-1: regerar com integra e base da fds-2 (ver a onda 0)
LEVA=fds python3 $F/inverter-depois-de.py --conjunto <x> <ids das sprints>   # lê; depois --escrever --backup
LEVA=fds python3 $F/retomar-conjunto.py --args $C/<json> --quem 'o limite, 10/10' --escrever
# lança um workflow NOVO com o molde (moldes/tema-da-onda.js) e o JSON de retomada
# quando o conferente voltar:
LEVA=fds bash $F/costurar-conjunto.sh $C/<json> <run-novo>             # só imprime
LEVA=fds bash $F/costurar-conjunto.sh $C/<json> <run-novo> --aplicar   # costura na fds-2 e roda o --rapido
```

**Os `depois_de` dos cortados apontam para a frente.** Os 12 conjuntos já têm código, mas as fichas deles ainda
esperam sprints que nunca voaram: o dsx espera 15 (do laco, do legado, do tato, do dsu, do diario, da F2-controle e
da O-SUBSYSTEM), a carga 5, o ipc 4, o lancadores 2, o kyty 2, o pad e o radio 1 cada. Todos são de posse (o mesmo
arquivo), nenhum é de dado. O caminho da casa é inverter, não esperar: o `inverter-depois-de.py` antes de cada
retomada, e a colisão em `rc=0` depois. Quem fica para depois passa a esperar o conjunto que já tem código. Os dois
genéricos (O-CODIGO-SEM-NARRADOR-02 e AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA) entram na mesma inversão.

**Falsos «em-voo», sem nada no disco desde 06/10:** A-ARVORE-TEM-UMA-SESSAO-SO, A-GUARDA-FECHA-A-PORTA,
A-SENHA-SO-PASSA-PELO-ASKPASS, O-DESPACHANTE-DAS-REGRAS-DA-CASA, O-ENDERECO-NUNCA-CHEGA-A-CONVERSA. São da casa (os
ganchos do zsh, fora do repo) e dependem do gesto dela pelo `promover-travas.sh`. Voltam a `espera-ela` na onda 0.
**O-REPOSITORIO-NASCE-VIVO** (github-completo) está pela metade e tem «O que foi feito»; entra na onda 15.

## 4. Por fazer: todas as 223, por setor

Cada linha diz o que passa a funcionar. **[tela]** espera o mockup escolhido; **[bancada]** pede a mão dela. Entre
parênteses, o destino: o conjunto (ver a seção 5) ou o que espera.

### Controle, entrada e pad virtual (34)

- `A-INTERFACE-INTEIRA-SE-ALCANCA-PELO…` — A interface inteira se alcança pelo controle e pelo teclado. [bancada] *(conjunto F2-acessibilidade)*
- `O-BOTAO-ALTERNA-REPETE-E-ENTENDE…` — O botão alterna, repete e entende toque longo e duplo. [bancada] *(conjunto F2-acessibilidade)*
- `O-CURSOR-GANHA-PRECISAO-PERMANENCIA-E…` — O cursor ganha precisão, permanência e clique travado. [bancada] *(conjunto F2-acessibilidade)*
- `O-ESTILO-NATIVO-DEIXA-O-JOGO…` — O estilo Nativo deixa o jogo decidir. [bancada] *(conjunto F2-acessibilidade)*
- `O-MOUSE-EMULADO-TEM-UM-DONO…` — O mouse emulado tem um dono só. *(conjunto F2-acessibilidade)*
- `O-POINT-AND-CLICK-SERVE-A…` — O point-and-click serve a visual novel. [bancada] *(conjunto F2-acessibilidade)*
- `O-SUBSYSTEM-SOBE-E-DESCE-POR…` — O subsystem sobe e desce por uma lista só. *(conjunto subsystem, onda 9: defeito de produto, não espera desenho)*
- `O-TREMOR-E-O-APERTO-JUNTO…` — O tremor e o aperto junto não decidem o botão. [bancada] *(conjunto F2-acessibilidade)*
- `OS-ANALOGICOS-DO-JOGO-GANHAM-ZONA…` — Os analógicos do jogo ganham zona morta, curva e uma mão. [bancada] *(conjunto F2-acessibilidade)*
- `O-ANALOGICO-CHEGA-AO-JOGO-NO…` — O analógico chega ao jogo no ritmo do controle. [bancada] *(conjunto F2-controle)*
- `O-CURSOR-DA-MIRA-ANDA-DEVAGAR…` — O cursor da Mira anda devagar logo acima da zona morta. [bancada] *(conjunto F2-controle)*
- `O-PAD-QUE-NASCE-NAO-PARA…` — O pad que nasce não para o tique dos outros. [bancada] *(conjunto F2-controle)*
- `O-TIQUE-DE-30-S-SO…` — O tique de 30 s só repinta a luz que o kernel perdeu. [bancada] *(conjunto F2-controle)*
- `A-TROCA-PELA-JANELA-NAO-PARA…` — A troca pela janela não para o laço do controle. *(conjunto carga)*
- `O-APARELHO-QUE-VIRA-P1-SEGUE…` — O aparelho que vira P1 segue escondido do jogo. *(conjunto dsx)*
- `A-FAIXA-NA-MESA-FORA-DE…` — A faixa da O-ASSENTO-04 também na mesa fora de ordem. *(espera ela)*
- `A-LUZ-DO-CONTROLE-NUNCA-SAI…` — A luz do controle nunca sai preta. [bancada] *(espera ela)*
- `A-MIRA-NA-NAVEGACAO` — Na Navegação, o giro move o cursor. *(espera ela)*
- `HIDE-SO-O-HIDRAW-02` — O físico segue alcançável por quatro nós de entrada. *(espera ela)*
- `NO-MODO-XBOX-TUDO-FUNCIONA` — No modo Xbox, tudo funciona. [bancada] *(espera ela)*
- `O-ASSENTO-GUARDADO-NAO-ANDA` — Enquanto o lugar está guardado, ninguém troca de número. *(espera ela)*
- `O-ASSENTO-GUARDADO-NAO-ANDA-02` — O jogo também espera, e o prazo sobrevive à suspensão. *(espera ela)*
- `O-ASSENTO-GUARDADO-NAO-ANDA-03` — Passado o prazo, o jogo fecha o buraco junto com a tela. *(espera ela)*
- `O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER…` — A regra do Hefesto é a última a falar do hidraw físico. [bancada] *(espera ela)*
- `O-MODO-QUE-NAO-SAI-DO…` — Ela clica no Modo e a tela não muda. [bancada] *(espera ela)*
- `A-PERDA-DE-AMOSTRAS-DO-MOVIMENTO…` — A perda de amostras do movimento se conta pelo contador do report. *(conjunto ipc)*
- `O-CONTROLE-E-O-VPAD-DELE…` — O controle e o vpad dele se casam pelo endereço. *(conjunto ipc)*
- `O-TIQUE-TEM-ORCAMENTO-E-A…` — O tique tem orçamento e a manutenção não para a entrada. *(conjunto legado)*
- `OS-NUMEROS-DA-SONY-E-OS…` — Os números da Sony e os ajudantes copiados têm um dono só. *(conjunto legado)*
- `A-MASCARA-DO-PAD-SE-DECIDE…` — A máscara do pad se decide só na fábrica. *(conjunto pad)*
- `O-ARQUIVO-DE-MASCARAS-ILEGIVEL-NAO…` — O arquivo de máscaras ilegível não se sobrescreve calado. *(conjunto pad)*
- `A-SETA-SEGURADA-SE-SOLTA-QUANDO…` — A seta segurada se solta quando o perfil troca. *(conjunto solta)*
- `O-MODIFICADOR-SEGURADO-POR-OUTRO-BOTAO…` — O modificador segurado por outro botão não se solta. *(conjunto solta)*
- `O-TOQUE-LIGADO-OU-DESLIGADO-POR…` — O toque é Ligado ou Desligado em cada controle, e o Desligado cala o touchpad dentro do jogo. [bancada] *(conjunto v-toque)*

### Vibração, gatilho e tato (23)

- `O-ESTILO-DO-PERFIL-LIGA-O…` — O estilo do perfil liga o motor do tato. *(no dev: falta o carimbo)*
- `O-PAD-CEDIDO-CALA-O-GATILHO…` — O pad cedido cala o gatilho e a luz também. *(no dev: falta o carimbo)*
- `O-PERFIL-ANTIGO-DE-VIBRACAO-POR…` — O perfil antigo de vibração por posição carrega no piso. *(no dev: fecha com o olho dela na foto)*
- `A-VOLTA-DOS-ACESSORIOS-SE-SENTE…` — A volta dos acessórios se sente no controle e na luz. [bancada] *(conjunto F2-acessorios)*
- `O-JOGO-DOS-ACESSORIOS-CHEGA-A…` — O jogo dos acessórios chega à aba Vibração e às janelas. *(conjunto F2-acessorios)*
- `O-TOUCHPAD-VIRA-FONTE-DE-VIBRACAO` — O touchpad vira fonte de vibração. [bancada] *(conjunto F2-acessorios)*
- `OS-GESTOS-DO-PS-COMANDAM-OS…` — Os gestos do PS comandam os acessórios. [bancada] *(conjunto F2-acessorios)*
- `OS-MEUS-TOQUES-VIBRAM-O-CONTROLE…` — Os meus toques vibram o controle a cada entrada. [bancada] *(conjunto F2-acessorios)*
- `QUEM-SOLTA-O-CONTROLE-SOLTA-O…` — Quem solta o controle solta o gatilho de todos. [bancada] *(conjunto F2-controle)*
- `A-FORCA-DA-VIBRACAO-DE-CADA…` — A força da vibração de cada controle sai de um funil só, com a bateria dele e o teto. *(costurada na fds-1: entra na fds-2)*
- `A-RECEITA-DO-TATO-SE-LE…` — A receita do tato se lê sem semear nem varrer. *(costurada na fds-1: entra na fds-2)*
- `O-EM-TODOS-DO-GATILHO-CHEGA…` — O «Em todos» do gatilho chega a cada controle da mesa. *(costurada na fds-1: entra na fds-2)*
- `O-GATILHO-QUE-O-CONTROLE-NAO…` — O gatilho que o controle não aceita não derruba o perfil. *(conjunto carga)*
- `O-DESLIGADO-DEIXA-O-JOGO-DECIDIR` — O «Desligado» deixa o jogo decidir. [bancada] *(espera ela)*
- `A-VIBRACAO-DO-CONTROLE-CHEGA-AOS…` — A vibração do controle chega aos acessórios pelo Buttplug. [bancada] *(conjunto evento)*
- `O-GATILHO-E-A-HAPTICA-DO…` — O gatilho e a háptica do jogo viram eventos para as extensões. [bancada] *(conjunto evento)*
- `O-TEXTO-DO-GATILHO-DIZ-O…` — O texto do gatilho diz o que o código faz hoje. *(conjunto ipc)*
- `O-TOQUE-CURTO-DO-JOGO-CHEGA…` — O toque curto do jogo chega ao controle mesmo entre dois tiques. *(conjunto pad)*
- `O-PARAR-CALA-O-TESTE-QUE…` — O «Parar» cala o teste que ainda estava no ar. *(conjunto parar)*
- `A-HAPTICA-DO-RADIO-SE-CONVERTE…` — A háptica do rádio se converte sem pesar na ponte. *(conjunto radio)*
- `O-MAPA-DA-VIBRACAO-DIZ-O…` — O mapa da vibração diz o que o código faz. *(conjunto radio)*
- `A-VIBRACAO-DO-JOGO-NAO-ESPERA…` — A vibração do jogo não espera o sono da volta. [bancada] *(conjunto tato)*
- `O-CONTROLE-VIBRA-NO-MODO-DO…` — O controle vibra no modo do firmware dele. [bancada] *(conjunto tato)*

### Som e microfone (8)

- `O-PADRAO-DO-ALTO-FALANTE-DESLIGA…` — O «Padrão» do alto-falante desliga sem perfil ativo. *(no dev: fecha com o olho dela na foto)*
- `O-NO-DE-SOM-FICA-QUANDO…` — O nó de som fica quando o controle sai. [bancada] *(conjunto F2-no-de-som)*
- `SOM-CABO-QUALIDADE` — A queixa que o codec não explica. *(espera ela)*
- `A-LUZ-DO-MIC-SEGUE-O…` — A luz do mic segue o botão quando não sabe quem ouve. *(conjunto som)*
- `O-MICROFONE-DO-RADIO-DESLIGA-NO…` — O microfone do rádio desliga no stop, mesmo com a volta em curso. *(conjunto som)*
- `O-NO-E-A-PONTE-DO…` — O nó e a ponte do som não nascem depois do stop. *(conjunto som)*
- `O-NO-LIGA-A-ROTA-INTEIRA…` — O nó liga a rota inteira e segue a saída padrão. *(conjunto som)*
- `O-SOM-QUE-O-JOGO-MANDA…` — O som que o jogo manda ao controle toca também pelo rádio. [bancada] *(conjunto tato)*

### Rádio, conexões e USB (18)

- `A-PONTE-PAUSADA-DIZ-A-VERDADE…` — A ponte pausada diz a verdade na Conexões. *(no dev: falta o carimbo)*
- `A-SONDA-DO-BLUEZ-PERGUNTA-SO…` — A sonda do BlueZ pergunta só ao dono, e o ensaio do rádio passa no tipo. *(no dev: falta o carimbo)*
- `O-CAMINHO-DO-BLUEZ-SO-NO…` — O caminho do BlueZ só no dono. *(no dev: falta o carimbo)*
- `O-CARTAO-DO-EXTERNO-MOSTRA-O…` — O cartão do controle externo mostra a cor e os glifos que ela declarou. *(no dev: falta o carimbo)*
- `O-DEGRAU-DO-MEIO-E-A…` — O degrau do meio e a frase da faixa se ligam depois da B9. [bancada] *(conjunto F2-degrau)*
- `A-BANCADA-QUE-O-RADIO-PEDE…` — A BANCADA QUE O RÁDIO PEDE — o índice. [bancada] *(espera ela)*
- `A-REPORT-THREAD-SAI-ANTES-DO…` — A report_thread sai antes de o handle fechar. [bancada] *(espera ela)*
- `AS-FAIXAS-DIZEM-QUEM-BRIGA-COM…` — As faixas dizem quem briga com cada aparelho. [bancada] *(espera ela)*
- `O-CONTROLE-JA-PAREADO-SE-PAREIA…` — O controle já pareado se pareia de novo num clique. [bancada] *(espera ela)*
- `O-CONTROLE-QUE-PEDE-PARA-PAREAR…` — O controle que pede para parear aparece, mesmo já conhecido. [bancada] *(espera ela)*
- `O-RECEPTOR-2-4G-SE-RECONHECE…` — O receptor 2.4G se reconhece e diz quando sofre. [bancada] *(espera ela)*
- `O-WIFI-SE-LE-NAS-DUAS…` — O Wi-Fi se lê nas duas bandas e troca o USB pela banda. [bancada] *(espera ela)*
- `STORM-USB` — O storm de USB que o doctor conta e ninguém cura. *(espera ela)*
- `O-VIGIA-DO-RADIO-SO-TOCA…` — O vigia do rádio só toca os controles do Hefesto. *(conjunto github)*
- `O-ACESSORIO-SEM-TIPO-GANHA-CATEGORIA…` — O acessório sem tipo ganha categoria e sinal na Conexões. [bancada] *(conjunto lancadores)*
- `O-VIGIA-DE-ZUMBI-PERGUNTA-E…` — O vigia de zumbi pergunta e avisa uma vez por episódio. *(conjunto radio)*
- `O-DUALSENSE-PELO-RADIO-NO-WINE…` — O DualSense pelo rádio no Wine se explica, sem o Hefesto no caminho. [bancada] *(só bancada, sem agente)*
- `A-CADEIA-USB-SE-RECONHECE-EM…` — A cadeia USB se reconhece em qualquer PC, e cada mudança vai ao registro. [bancada] *(conjunto v-usb)*

### Perfis e modificações (17)

- `A-COR-E-O-NUMERO-DO…` — A cor e o número do perfil chegam por toda rota. *(costurada na fds-1: entra na fds-2)*
- `AS-MARCAS-VISUAL-NOVEL-E-ADULTO…` — As marcas Visual novel e Adulto se somam ao estilo. *(costurada na fds-1: entra na fds-2)*
- `AS-MODIFICACOES-RODAM-FORA-DO-DAEMON` — As modificações rodam fora do daemon, com manifesto, permissão e versão. *(costurada na fds-1: entra na fds-2)*
- `O-EDITOR-DA-ABA-PERFIS-SO…` — O editor da aba Perfis só grava no perfil que mostra. *(costurada na fds-1: entra na fds-2)*
- `O-ESTILO-CHEGA-AO-GATILHO-E…` — O estilo chega ao gatilho e à vibração de cada controle. *(costurada na fds-1: entra na fds-2)*
- `O-PERSONALIZADO-DESLIGA-A-RECEITA-DO…` — O Personalizado desliga a receita do estilo anterior. *(costurada na fds-1: entra na fds-2)*
- `A-FABRICA-NOVA-DO-FREESTYLE-ALCANCA…` — A fábrica nova do Freestyle alcança a cópia de fábrica de ontem. *(conjunto carga)*
- `O-SALVAR-E-O-APLICAR-LEEM…` — O Salvar e o Aplicar leem o perfil, e só ele (item 1 da auditoria de 26/09). [bancada] *(espera ela)*
- `O-PLUGIN-RECARREGA-SEM-PERDER-OS…` — O plugin recarrega sem perder os plugins. *(conjunto ipc)*
- `O-RECARREGAR-DOS-PLUGINS-NAO-APAGA…` — O recarregar dos plugins não apaga os plugins. *(conjunto ipc)*
- `O-BRANCO-DA-TROCA-DE-PERFIL…` — O branco da troca de perfil pisca sem gravar. *(conjunto solta)*
- `O-PERFIL-DO-JOGO-ENTRA-SEM…` — O perfil do jogo entra sem ler a janela. *(conjunto terminal)*
- `O-PERFIL-FEITO-FORA-DA-JANELA…` — O perfil feito fora da janela vale inteiro. *(conjunto terminal)*
- `A-GUARDA-DO-EDITOR-ACHA-O…` — A guarda do editor acha o ajuste de cada controle. *(conjunto v-perfis)*
- `AS-MODIFICACOES-MARCAM-O-GESTO-ESPERAM…` — As modificações marcam o gesto, esperam parar e saem no uninstall. *(conjunto v-perfis)*
- `O-ATIVAR-DA-ABA-PERFIS-AGE…` — O «Ativar» da aba Perfis age sobre o perfil que o editor mostra. *(conjunto v-perfis)*
- `O-CONTROLLERS-JSON-ILEGIVEL-NAO-SE…` — O controllers.json ilegível não se sobrescreve calado. *(conjunto v-perfis)*

### Jogos, lançadores e emuladores (21)

- `A-GRAVACAO-DO-YML-QUE-FALHA…` — A gravação do `.yml` que falha depois da anotação vai ao diário. *(no dev: falta o carimbo)*
- `O-REGISTRO-DO-YML-ANDA-ANTES…` — O registro do `.yml` anda antes da carona, e a recusa calada ganha a linha no CSV. *(no dev: falta o carimbo)*
- `O-SHADPS4-QUE-JA-MORA-AQUI` — O jogo de PS4 que ela já tem instalado recebe touchpad, giroscópio e vibração pelo controle virtual. [bancada] *(conjunto F2-emuladores)*
- `O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO` — O jogo de Vita recebe o toque na frente e atrás, e o giroscópio, pelo controle virtual. [bancada] *(conjunto F2-emuladores)*
- `O-SERVIDOR-DSU-LEVA-O-TOQUE…` — O touchpad vira a tela de baixo do 3DS, e o giro chega por um caminho que não depende do SDL. [bancada] *(conjunto dsu)*
- `O-DSX-PINTA-COMO-JOGO-E…` — O DSX pinta como jogo, e o reset devolve o perfil. *(conjunto dsx)*
- `O-LIMIAR-DO-GATILHO-DO-DSX…` — O limiar do gatilho do DSX vale para cada jogador. *(conjunto dsx)*
- `O-PAR-DO-GESTO-DO-PS…` — O par do gesto do PS não chega ao jogo. *(conjunto dsx)*
- `A-ABA-LANCADORES-GANHA-AS-MODIFICACOES` — A aba Lançadores ganha as Modificações. [bancada] *(espera ela)*
- `O-ENGASGO-DO-JOGO-LEVE-SE…` — O engasgo do jogo leve se separa em ABBA. [bancada] *(espera ela)*
- `O-FIXAR-PROTON-DESINSTALA-AS-VERSOES…` — O «Fixar Proton» desinstala as versões que sobram. [bancada] *(espera ela)*
- `O-JOGO-LEVE-ACORDA-A-PLACA` — O jogo leve acorda a placa. [bancada] *(espera ela)*
- `STEAM-INPUT` — O chip que nunca acende, e a escrita que já estava pronta. *(espera ela)*
- `O-PS-ABRE-A-STEAM-PELO…` — O PS abre a Steam pelo dono que já sabe reabrir. *(conjunto fora)*
- `O-LANCADOR-DO-KYTYPS5-VEM-DA…` — O lançador do KytyPS5 vem da modificação. [bancada] *(conjunto kyty)*
- `O-DSX-ACENDE-O-JOGADOR-QUE…` — O DSX acende o jogador que o mod pede. *(conjunto laco)*
- `O-BIG-PICTURE-SE-PROVA-NA…` — O Big Picture se prova na Steam, e o mapa de canais ganha as linhas dele e dos dois modos. [bancada] *(só bancada, sem agente)*
- `AS-CONFIGURACOES-CHEGAM-AO-JOGO-NOVO…` — As configurações chegam sozinhas a cada jogo novo, no instante em que a Steam fecha. [bancada] *(conjunto v-jogos)*
- `O-JOGO-QUE-PEDE-RECEITA-DE…` — O jogo que só abre com uma receita de ambiente a recebe pelo wrapper, para toda a família dele. [bancada] *(conjunto v-jogos)*
- `O-JOGO-SE-DECLARA-NO-PRONTUARIO…` — O prontuário diz o que cada jogo declara sobre controle, e explica a capa da Steam. *(conjunto v-jogos)*
- `O-REAPLICAR-NUNCA-APAGA-O-QUE…` — Reaplicar nos lançadores nunca apaga o que o usuário escreveu na opção de lançamento. *(conjunto v-jogos)*

### Janela e interface (37)

- `A-LINHA-DO-EXTERNO-VOLTA-AOS…` — A linha do externo volta aos 30 px, e a cor fora da lista se escolhe. *(no dev: fecha com o olho dela na foto)*
- `A-TELA-PERGUNTA-AO-DONO` — A tela pergunta ao dono. *(no dev: fecha com o olho dela na foto)*
- `A-TELA-SEM-O-QUE-A…` — A tela sem o que a régua aceita. *(no dev: fecha com o olho dela na foto)*
- `AS-QUATRO-LINHAS-DA-08-SEM…` — As quatro linhas da 08 sem dono ganham dono ou saem do desenho. *(no dev: fecha com o olho dela na foto)*
- `O-NOME-DO-JOGADOR-TEM-UM…` — O nome do jogador tem um dono só. *(no dev: fecha com o olho dela na foto)*
- `O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO` — O Selecionar acende quem está escolhido. [bancada] *(no dev: fecha com o olho dela na foto)*
- `SO-A-PRIMEIRA-LETRA-E-MAIUSCULA…` — Só a primeira letra é maiúscula em toda aba. *(no dev: fecha com o olho dela na foto)*
- `TODO-TEXTO-QUE-ABRE-UMA-LINHA…` — Todo texto que abre uma linha começa com maiúscula. *(no dev: fecha com o olho dela na foto)*
- `O-POINT-AND-CLICK-E-A…` — O point-and-click e a acessibilidade se definem na Navegação. [tela] [bancada] *(conjunto F2-acessibilidade; a ficha diz `espera-ela`: só voa com a palavra dela)*
- `OS-ALVOS-E-A-LETRA-CRESCEM…` — Os alvos e a letra crescem, e a interface ganha tamanho. [tela] [bancada] *(conjunto F2-acessibilidade; a ficha diz `espera-ela`: só voa com a palavra dela)*
- `O-NUMERO-DA-BARRA-NAO-CONGELA…` — O número da barra não congela no valor velho. *(costurada na fds-1: entra na fds-2)*
- `A-HAPTICA-MORA-EM-VIBRACAO-E…` — A háptica mora em Vibração, e o ícone do app volta. *(espera ela)*
- `A-PALETA-MARCA-A-COR-DE…` — A paleta marca a cor de cada controle. [bancada] *(espera ela)*
- `AS-DICAS-SAO-CARTOES-COM-UM…` — As dicas são cartões com um gesto. *(espera ela)*
- `I18N-DA-TELA-NOVA` — As strings da tela nova não têm endereço. *(espera ela)*
- `O-APARELHO-SE-CORRIGE-ONDE-SE…` — O aparelho se corrige onde se clica. *(espera ela)*
- `O-TOUCHPAD-MOSTRA-AS-ZONAS-QUE…` — O touchpad mostra as zonas que ele aperta. [bancada] *(espera ela)*
- `A-BANDEJA-TEM-UM-DONO-SO` — A bandeja tem um dono só. *(conjunto fora)*
- `A-CASCATA-DO-WAYLAND-SO-PERGUNTA…` — A cascata do Wayland só pergunta a quem responde. *(conjunto fora)*
- `O-TEMA-DE-CORES-ENTRA-PELA…` — O tema de cores entra pela folha de usuário. *(conjunto lancadores)*
- `FECHAR-A-JANELA-DEVOLVE-O-QUE…` — Fechar a janela devolve o que as abas seguravam. *(conjunto parar)*
- `OS-CORACOES-DA-VIBRACAO-NAO-SEGURAM…` — Os corações da vibração não seguram a janela. *(conjunto parar)*
- `A-SAIDA-DE-UM-CONTROLE-NAO…` — A saída de um controle não trava a aba Sistema. *(conjunto radio)*
- `A-ABA-NAVEGACAO-TEM-OS-DOIS…` — A aba Navegação tem os dois point and click e a velocidade que funciona. [tela] *(conjunto tela-a)*
- `A-CAPTURA-DE-TECLA-SE-FAZ…` — A captura de tecla se faz sobre o mapa do controle. [tela] [bancada] *(conjunto tela-a)*
- `A-FUNCAO-DO-TECLADO-GANHA-O…` — A Função do teclado ganha o «Sempre». [tela] *(conjunto tela-a)*
- `O-POINT-AND-CLICK-FICA-NO…` — O point and click fica no Ligado e a navegação no Desligado. [tela] *(conjunto tela-a)*
- `O-TOUCHPAD-LIGA-E-DESLIGA-NA…` — O touchpad liga e desliga na aba Controles. [tela] *(conjunto tela-a)*
- `A-ABA-SISTEMA-FICA-COM-SEIS…` — A aba Sistema fica com seis linhas e o registro cabe na janela. [tela] *(conjunto tela-b)*
- `O-BOTAO-DIREITO-ABRE-O-MENU…` — O botão direito abre o menu do Hefesto em toda aba. [tela] *(conjunto tela-b)*
- `O-PERFIL-GUARDA-A-DATA-EM…` — O perfil guarda a data em que nasceu e a da última mudança. [tela] *(conjunto tela-b)*
- `O-PERFIL-SE-ACHA-PELO-NOME…` — O perfil se acha pelo nome do jogo e se aplica em quatro alvos. [tela] *(conjunto tela-b)*
- `CADA-FEATURE-TEM-UM-DONO-SO…` — Cada feature tem um dono só na interface. [tela] *(conjunto tela-c)*
- `O-MAPA-DAS-CONEXOES-MOSTRA-A…` — O Mapa das Conexões mostra a cadeia USB e o registro dela. [tela] *(conjunto tela-c)*
- `A-ALTURA-E-A-LARGURA-DA…` — A altura e a largura da janela não pulsam. [bancada] *(conjunto v-janela)*
- `A-JANELA-DO-INICIO-DA-SESSAO…` — A janela que abre no início da sessão não morre junto com o serviço que a abriu. [bancada] *(conjunto v-janela)*
- `A-JANELA-REGISTRA-O-PROPRIO-TAMANHO…` — A janela registra o próprio tamanho, o monitor e o motivo de fechar. [bancada] *(conjunto v-janela)*

### Serviço, linha de comando e install (17)

- `A-CHAVE-E-A-PERMISSAO-DIZEM…` — A chave e a permissão dizem o que são. *(conjunto diario)*
- `O-DIARIO-AVISA-UMA-VEZ-E…` — O diário avisa uma vez, e a configuração ilegível não se perde. *(conjunto diario)*
- `O-NIX-LEVA-AS-REGRAS-DO…` — O Nix leva as regras do host. *(espera ela)*
- `O-PRODUTO-EM-QUALQUER-MAQUINA` — O produto em qualquer máquina: as lacunas e a prova em máquina limpa. [bancada] *(espera ela)*
- `A-TELA-E-DEPENDENCIA-DURA` — A interface declara o WebKit em todo lugar onde o produto se instala. *(conjunto install)*
- `AS-REGRAS-DO-SOM-VALEM-NO…` — As regras do som valem no WirePlumber que a distro traz. *(conjunto install)*
- `O-BLUEZ-DA-CASA-NAO-CONGELA…` — O BlueZ da distro ganha recado, e o da casa não congela a segurança. *(conjunto install)*
- `O-BROKER-SERVE-QUEM-ESTA-NA…` — O broker serve quem está na frente da máquina. [bancada] *(conjunto install)*
- `O-INSTALL-EM-QUALQUER-DISTRO` — O install reconhece a distro somente leitura. *(conjunto install)*
- `O-PERFIL-DE-FABRICA-E-O…` — O perfil de fábrica e o serviço chegam em todo formato. *(conjunto install)*
- `O-QUE-E-DA-BANCADA-FICA…` — O que é da bancada fica na bancada. *(conjunto install)*
- `A-LINHA-DE-COMANDO-ESPERA-O…` — A linha de comando espera o que o serviço precisa. *(conjunto ipc)*
- `A-TROCA-DE-DAEMON-ESPERA-O…` — A troca de daemon espera o desligamento inteiro. *(conjunto laco)*
- `AS-METRICAS-CONTAM-O-QUE-A…` — As métricas contam o que a página promete. *(conjunto laco)*
- `O-ERRO-DO-LACO-DE-60…` — O erro do laço de 60 Hz vai ao diário e não derruba a mesa. *(conjunto laco)*
- `A-LINHA-DE-COMANDO-NAO-TRAVA…` — A linha de comando não trava e não anuncia o que não fez. *(conjunto terminal)*
- `O-QUE-SO-A-JANELA-LIGAVA…` — O que só a janela ligava tem verbo no terminal. *(conjunto terminal)*

### Ferramentas da leva, portões e CI (24)

- `A-BANCADA-DE-MENTIRA-TEM-EXTERNO…` — A bancada de mentira tem externo, e a sonda lê a dica. *(no dev: falta o carimbo)*
- `A-CASA-NAO-DEIXA-PASSAR-COMENTARIO…` — A casa não deixa passar comentário cortado, import relativo nem posse de arquivo que não existe. *(no dev: falta o carimbo)*
- `A-CRUA-SO-ANDA-COM-PROVA…` — A crua só anda com prova de verdade, e o rc do reapontar diz o que falta. *(no dev: falta o carimbo)*
- `A-JANELA-ABERTA-CABE-NA-PARTE` — Um arquivo de teste não passa da parte ideal. *(no dev: falta o carimbo)*
- `A-SUITE-NAO-ACORDA-A-PLACA…` — A suíte não acorda a placa de verdade. *(no dev: falta o carimbo)*
- `AS-CITACOES-CURTAS-DO-CSV-ANDAM…` — As citações curtas do CSV andam com a inteira, e a troca é pelo lugar onde a curta está. *(no dev: falta o carimbo)*
- `AS-FERRAMENTAS-DA-LEVA-NAO-CALAM…` — As ferramentas da leva não calam, e a base de testes delas fica verde. *(no dev: falta o carimbo)*
- `AS-FERRAMENTAS-DE-MANUTENCAO-NAO-REESCREVEM…` — O `--aceitar` e o neutralizador mexem só no que provam. *(no dev: falta o carimbo)*
- `O-COSTURAR-ACEITA-O-COMMIT-RESOLVIDO…` — O costurar aceita o commit resolvido à mão, se o patch fora dos gerados já está na integração. *(no dev: falta o carimbo)*
- `O-DUBLE-DO-CONTROLE-FICA-DESPLUGADO…` — O dublê do controle fica desplugado, e o teste do daemon espera a condição. *(no dev: falta o carimbo)*
- `A-CITACAO-CURTA-DO-DIFF-LE…` — A citação curta do diff lê a célula, e a segunda chance não desfaz a correção. *(costurada na fds-1: entra na fds-2)*
- `A-DIVIDA-DA-BASE-DESCE-POR…` — A dívida da base desce por arquivo e por quem toca. *(costurada na fds-1: entra na fds-2)*
- `AS-REGUAS-DO-RAMO-INTEIRO-E…` — As réguas do ramo «inteiro» e das quatro respostas mordem. *(costurada na fds-1: entra na fds-2)*
- `O-COMENTARIO-COM-DOIS-PONTOS-SO…` — O `#:` só vale colado em cima de uma atribuição. *(costurada na fds-1: entra na fds-2)*
- `O-LOTE-DE-TESTES-DO-AGENTE…` — O lote de testes do agente isola o WebKit como a suíte isola. *(costurada na fds-1: entra na fds-2)*
- `O-MOLDE-DA-SPRINT-LISTA-TODO…` — O molde da sprint lista todo campo que o portão lê. *(costurada na fds-1: entra na fds-2)*
- `A-CATRACA-DA-ORIGEM-CONTA-O…` — A catraca da origem conta o `suppress` que só engole. *(conjunto fora)*
- `O-CI-NAO-TRAVA-NO-APT…` — O CI não trava no apt nem espera seis horas. *(conjunto papeis)*
- `A-CITACAO-NOVA-DE-LINHA-PROMETE…` — A citação nova de linha promete o nome. *(conjunto portoes)*
- `NADA-QUE-O-GITIGNORE-EXCLUI-ENTRA…` — Nada que o `.gitignore` exclui entra no repositório. *(conjunto portoes)*
- `O-CI-CHAMA-OS-PORTOES-PELO…` — O CI chama os portões pelo nome, e o comando de cada um mora num lugar só. *(conjunto portoes)*
- `O-RAPIDO-SO-REPETE-O-QUE…` — O `--rapido` só repete o que mudou, e os dois portões mais caros ficam rápidos por dentro. *(conjunto portoes)*
- `O-VERMELHO-NOVO-DA-COSTURA-NAO…` — O vermelho novo da costura não se esconde no herdado, e o despacho leva só o que se lê. *(conjunto portoes)*
- `OS-COMANDOS-E-OS-TESTES-NAO…` — Os comandos e os testes não sabem o caminho desta máquina. *(conjunto portoes)*

### Repositório, GitHub e documentos (13)

- `A-WIKI-NASCE-DO-QUE-O…` — A Wiki nasce do que o repositório já sabe: uma fonte só, gerada a cada push, e nunca escrita à mão. *(no dev: falta o carimbo)*
- `A-DOCSTRING-DIZ-O-CONTRATO-E…` — A docstring diz o contrato e a história mora no documento. *(conjunto diario)*
- `A-AUTORIA-SE-MEDE-PELA-LISTA…` — A autoria se mede pela lista de quem pode. *(espera ela)*
- `TRADUZIR-O-PROJETO` — O projeto legível por quem não é desta casa. *(espera ela)*
- `A-FORJA-SEM-RASTRO` — A Forja sem rastro: a ponta limpa agora, a história na mesma janela do Hefesto. *(conjunto github)*
- `A-HISTORIA-REESCRITA-UMA-VEZ-SO` — A história reescrita uma vez só, e o chamado ao suporte uma vez só. *(conjunto github)*
- `AS-CITACOES-DE-COMMIT-SEGUEM-O…` — As citações de commit seguem o mapa. *(conjunto github)*
- `O-GITHUB-SEM-RASTRO-FORA-DO…` — O GitHub sem rastro, no que não é git. *(conjunto github)*
- `O-REPOSITORIO-NASCE-VIVO` — O repositório nasce vivo: todas as funções do GitHub, declaradas no código e aplicadas por script. *(conjunto github)*
- `RELEASE-NO-CLONE-LIMPO` — A esteira dos pacotes cai por uma pasta que não viaja. *(conjunto github)*
- `O-CODIGO-SEM-NARRADOR-02` — O resto do narrador sai à mão, arquivo por arquivo: as falas citadas e o «dela» que o padrão não alcança. *(conjunto narrador)*
- `A-CANONICA-RECEBE-O-QUE-AS…` — A canônica recebe o que as reimplementações abertas dizem do som e do toque. *(conjunto papeis)*
- `A-PAGINA-DAS-PORTAS-CONTA-A…` — A página das portas conta a ponte do som e da vibração. *(conjunto papeis)*

### Bancada e medição (5)

- `A-BANCADA-DOS-EXTERNOS` — A bancada dos controles EXTERNOS — adiada pela D-0609-EXTERNOS-DEPOIS. [bancada] *(espera ela)*
- `MESA-DE-QUATRO` — Quatro DualSense, por cabo e por rádio, com ela. [bancada] *(espera ela)*
- `OS-GESTOS-QUE-SO-ELA-PODE…` — OS GESTOS QUE SÓ ELA PODE FAZER — a fila da bancada, 10/09/2026. [bancada] *(espera ela)*
- `O-BASICO-MEDIDO` — O básico se mede por um instrumento que diz o que mexe e devolve o que mexeu. [bancada] *(só bancada, sem agente)*
- `O-FORJA-E-O-BANCO-DE…` — O Forja é o banco de prova do Hefesto. [bancada] *(só bancada, sem agente)*

### A casa (o assistente) (6)

- `O-CONTEXTO-CHEGA-CERTO-A-QUEM-ABRE…` — O contexto chega certo a quem abre a sessão, parte 2: a lei estável nas instruções da casa e a memória auditada. *(espera a aprovação dela)*
- `A-ARVORE-TEM-UMA-SESSAO-SO` — A árvore tem uma sessão só, e o /tmp também. *(falso em voo: gesto dela)*
- `A-GUARDA-FECHA-A-PORTA` — A guarda fecha a porta: o assistente não desliga a trava que o segura. *(falso em voo: gesto dela)*
- `A-SENHA-SO-PASSA-PELO-ASKPASS` — A senha só passa pelo askpass, e nunca pela conversa. *(falso em voo: gesto dela)*
- `O-DESPACHANTE-DAS-REGRAS-DA-CASA` — O despachante das regras da casa: o que a memória só lembrava passa a barrar. *(falso em voo: gesto dela)*
- `O-ENDERECO-NUNCA-CHEGA-A-CONVERSA` — O endereço do controle nunca chega à conversa nem à tela dela. *(falso em voo: gesto dela)*

## 5. As levas até o fim

**As regras de toda onda** (o método de 02/10): um conjunto por setor; no máximo três agentes por conjunto
(implementa, conferente que corrige, final só em conjunto grande); posse disjunta medida pelo
`check_colisao_de_sprints.py` antes do despacho; costura por conjunto assim que o conferente dele volta
(`git cherry`); portões completos a cada costura; suíte inteira, merge ff, install e push só no fecho.

**O modelo por papel:** o fim de semana só com Opus acabou hoje às 10h. Volta o padrão: implementa o que está bem
escrito em **Sonnet `high`**; a retomada pelo diff e a causa difícil (Sackboy, pad, ipc, som, subsystem) em **Opus
`high`**; conferente e final em **Opus `high`**. O molde **já** lê `A.esforco_confere || 'high'` e
`parte.modelo || 'sonnet'`, e o `montar-conjunto.py` já sai em Sonnet: não há o que mudar neles. **O que tem de
mudar é o `leva-fds/regerar-conjuntos.py`**, que grava `--modelo opus` e `esforco_confere: "xhigh"` fixos: na
onda 0, tirar os dois (ou acertar os JSON à mão) antes de regerar.

**O ritmo:** 3 a 5 conjuntos por onda, 3 vagas de pytest (`vez-do-pytest.sh`). Cada conjunto leva de 1h30 a 2h30.
Um fecho leva ~2 h. **A onda seguinte sai por conjunto, não pela onda inteira:** um conjunto da onda N+1 voa assim
que os conjuntos com quem ele colide (a coluna «por que aqui») costuraram. É o que mantém o passo com ondas menores.

**Por que mais ondas que antes:** a onda 4 antiga (laco, legado, terminal, diario, evento) tinha 15 colisões de
posse entre os próprios conjuntos (o `lifecycle.py`, o `gamepad.py`, o `launch_env.py`, o `cmd_doctor.py`…). Medido
agora: legado, laco, diario, dsu e v-usb tocam todos o `daemon/lifecycle.py`, dois a dois. São cinco conjuntos que
não podem voar juntos, então pedem cinco ondas, uma para cada. Os outros se encaixam ao lado deles.

| onda | conjuntos (agentes) | por que aqui | portão de saída | agentes |
| --- | --- | --- | --- | --- |
| **0** a base nova | sem conjunto. Sem agente: CI do `0044399e9` e `--so publicar`; nascer a `integra/fds-2` do `dev` (`git worktree add -b integra/fds-2 /mnt/Apate/Desenvolvimento/hefesto-voo/_integra-fds-2 dev`); **`echo 2 > ~/.local/state/hefesto-casa/leva-fds/ONDA`** (o `leva.env` da fds tira INT e BRANCH desse número, que hoje diz 1); copiar o `docs/process`, os ignorados (`copiar-ignorados.sh`) e as instruções da casa; `cherry-pick` dos 39 em ordem (conflito só em gerado: regera, nunca escolhe lado); acertar o `regerar-conjuntos.py` (Sonnet e `high`) e regerar os args dos 12 cortados contra a fds-2; carimbo das 28 costuradas e a A-SUITE à mão; as 5 da casa voltam a `espera-ela`; as 10 absorvidas saem da fila do `SPRINT_ORDER` (o `sprint.py validar --todas` as acusa); criar `leva-volta/leva.env` e `leva-volta/conjuntos/` (seção 6). **Agentes:** escrever as sprints novas (escritor + crítico, Opus) e, se a fds-2 ficar vermelha, 1 Opus que cura a base | — | `rapido-na-integracao.sh` verde na fds-2; colisão `rc=0` com as novas | 2 (+1) |
| **1** o que a rodada do Sackboy espera, e as ferramentas | pad (1), som (2, fecha o implementa), portoes (2, com final), ipc (2, com final) | pad e som tocam os arquivos do Sackboy (`uhid_gamepad.py`, `alto_falante.py`, `alto_falante_bt.py`) e têm de costurar antes dele; portoes traz o `--rapido` novo | cada costura com `--rapido` verde; portões completos no fim da onda | 7 |
| **2** o Sackboy | **sackboy (2, Opus; sprint da onda 0)**, parar (1), solta (1), fora (1, refaz o `wip`), radio (2) | nenhum colide com o sackboy; o sackboy sai assim que pad e som costurarem | idem; o sackboy só fecha com a rodada D1 medida | 7 |
| **3** o resto da fds | carga (2), lancadores (2), kyty (2), dsx (2) | nenhum par colide; os `depois_de` para a frente se invertem (seção 3) | idem | 8 |
| **FECHO A** | `integra/fds-2` → `dev`: portões 72, suíte 24, merge ff, install, push, CI | ondas 0–3 | **o `dev` dela recebe 16 + 43 + Sackboy de uma vez** | — |
| **4** a FILA 1 que nunca voou | legado (2), install (3, com final), papeis (2: P11 a canônica, a página das portas, o CI que não trava no apt) | nova `integra/volta-1` do `dev`; legado primeiro: é o que mais colide (com laco, terminal, diario, evento, dsu, v-usb, v-toque, v-jogos) | portões completos | 7 |
| **5** | laco (2), tato-do-jogo (2), v-perfis (2: Ativar, guarda do editor, modificações, `controllers.json`) | laco e legado tocam o `lifecycle.py` | idem | 6 |
| **6** | diario (2), terminal (2), v-janela (2: P6–P8) | diario × laco e terminal × laco | idem | 6 |
| **7** | dsu (2; curar o frontmatter antes), evento (2: a do Buttplug e a P10 dos eventos), v-jogos (2: P2–P5) | dsu × diario; evento × terminal; v-jogos × legado e terminal (`launch_env.py`) | idem | 6 |
| **8** | v-usb (2: a cadeia USB), v-toque (2: P1) | v-usb × dsu (`lifecycle.py`); v-toque depende de v-jogos (dado, não posse: não se inverte) | idem | 4 |
| **FECHO B** | `integra/volta-1` → `dev` | ondas 4–8 | suíte 24, install, push, CI | — |
| **9** subsystem e o que pede bancada | **subsystem (2, Opus: O-SUBSYSTEM-SOBE-E-DESCE, defeito de produto, sai sem esperar desenho nem ela)**, F2-no-de-som (2; resposta 0.1), F2-degrau (2; respostas A3, C1, N2), F2-emuladores (2), tela-b (2: T4, T5, T6). Mais 4 só de bancada, sem agente (rádio no Wine, Big Picture, básico medido, Forja) | `integra/volta-2`; o subsystem toca os mesmos arquivos do clique de cinco (vem depois dele) e tem de vir antes da F2-controle, que o espera; tela-b só com os mockups do todo escolhidos | cada F2 fecha no item dela da bancada; tela com foto, clique e mordida em lar de mentira | 10 |
| **10** | tela-a (3, com final: T1, T2, T3, a captura, a Função do teclado e a ordem das 14h40) | tela-a × tela-b (`profiles/schema.py`) e tela-a × subsystem (`lifecycle.py`, `mouse.py`) | idem; `--publicar` no fecho | 3 |
| **11** | F2-controle-com-ela (2), tela-c (2: T7, T8 tela) | F2-controle × subsystem; tela-c depende de tela-a, tela-b (dado) e v-usb | idem | 4 |
| **FECHO C** | `integra/volta-2` → `dev` | ondas 9–11 | idem | — |
| **12** | F2-acessibilidade (3, com final; 10 fichas, a O-MOUSE-EMULADO sai como `absorvida`; as duas de tela esperam a palavra dela) | `integra/volta-3`; colide com F2-controle, tela-a, tela-b e tela-c | idem | 3 |
| **13** | narrador (3, com final: O-CODIGO-SEM-NARRADOR-02), sozinho | toca quase todo arquivo | idem | 3 |
| **14** | F2-jogo-dos-acessorios (3, com final) | F2-acessibilidade e narrador | idem | 3 |
| **FECHO D** | `integra/volta-3` → `dev` | ondas 12–14 | idem | — |
| **15** a janela do GitHub | github (2, Opus: A-HISTORIA-REESCRITA, O-GITHUB-SEM-RASTRO, AS-CITACOES-DE-COMMIT, RELEASE-NO-CLONE-LIMPO, A-FORJA-SEM-RASTRO, O-REPOSITORIO-NASCE-VIVO, O-VIGIA-DO-RADIO). A reescrita da história é a última | `integra/volta-4`; tudo antes | release no clone limpo, CI verde | 2 |
| **FECHO E** | o último | — | **zero sprint aberta** | — |

**Total:** 16 ondas (0 a 15), 39 conjuntos (o subsystem saiu da F2-acessibilidade), **81 agentes** (82 se a base da
fds-2 pedir cura). Perto de metade em Sonnet. A fds gastou 68 Opus em 31 conjuntos.

**Tempo:** as ondas 0 a 8 e os fechos A e B andam sozinhas. Com a saída por conjunto, são ~34 h corridas (as ondas
5 a 8 são menores, de 4 a 6 agentes). As ondas 9 a 11 dependem da bancada e da escolha dos mockups por ela (só o
subsystem não espera). As ondas 12 a 15, mais os fechos C a E, somam ~20 h. Com a mão dela em dia, são **4 dias
corridos**.

## 6. Como se controla

1. **Um estado só:** a primeira seção do `docs/process/estudos/2026-10-12-a-volta/ANDAMENTO.md` (onda em voo,
   runs, próximo passo) e o arquivo da onda. Nas ondas 1 a 3 é o `leva-fds/ONDA` (com `LEVA=fds`, valor 2). Da
   onda 4 em diante é o `leva-volta/ONDA`, que **ainda não existe**: antes da onda 4, copiar o
   `ferramentas-da-leva/leva.env.exemplo` para `~/.local/state/hefesto-casa/leva-volta/leva.env`, com
   `INT=$VOO/_integra-volta-$ONDA` e `BRANCH=integra/volta-$ONDA`, criar `leva-volta/conjuntos/` e gravar `1` no
   `ONDA`. As integrações da volta são quatro: `volta-1` (ondas 4 a 8), `volta-2` (9 a 11), `volta-3` (12 a 14) e
   `volta-4` (15); cada uma nasce do `dev` do fecho anterior. O `estado-de-agora.py --uma-linha` lê o estado.
2. **Antes de cada onda:** o `inverter-depois-de.py` de cada conjunto (primeiro sem `--escrever`, ler a lista,
   depois com `--escrever --backup`): no plano há 119 `depois_de` que apontam para uma onda posterior, todos de
   posse, mais 203 dos dois genéricos; nenhum fica dentro da mesma onda. O único de dado é o v-toque → v-jogos (e as
   telas), e esses estão em série. Depois, `check_colisao_de_sprints.py` com `rc=0`; os args por
   `montar-conjunto.py`; commit de tudo (agente roda `reset --hard`); dizer a ela quantos agentes voam.
3. **Durante:** o `vigia-das-levas.sh` só como tarefa de fundo; `estado-das-levas.py wf_…` para o painel; todo
   pytest pelo `vez-do-pytest.sh`, com TMPDIR curto em `/tmp`.
4. **Quando o limite cortar:** commit `wip` em cada worktree, `retomar-conjunto.py`, workflow novo. Nunca
   `resumeFromRunId` numa pipeline.
5. **Costura:** por conjunto, assim que o conferente dele voltar; conta pelo `git cherry`; portões completos a
   cada costura (`fecho-portoes.sh`); suíte só no fecho, com o `fecho-quando-livre.sh` enquanto o semáforo prender
   vaga parcial.
6. **Nunca costurar das `voo/*` da 1-11:** elas têm os hashes de antes da reescrita.
7. **Lista fechada:** ideia nova vira ficha para a onda seguinte. Depois de cada onda, pedir a % da semana e
   ajustar o tamanho da próxima.
8. **Reapontar citações é a última coisa** de cada fecho (`reapontar-citacoes.py`).

### Os itens soltos

- **A3 (as 7 curas na fds-1):** caducou. As 7 já estão no `dev`, e a fds-1 não fecha mais. Vira a onda 0: a
  fds-2 nasce do `dev` e recebe os 39 da fds.
- **A folha da bancada D2 a D8:** a folha se monta, sem agente, a partir da tabela de `SPRINTS-DA-VOLTA.md`
  (D2–D8 mais D-toque, D-jogo-novo, D-login, D-envelope, D-touch-tela, D-registro, D-captura, D-usb). Vai na aba
  Bancada da página em 127.0.0.1:8766. As respostas dela gravam em `bancada/respostas.json`. Cada resposta fecha
  uma ficha ou vira correção na onda seguinte. A fila antiga da fds (`leva-fds/BANCADA-PLANO.md`) segue valendo
  para as 39 que esperam ela.
- **O HANDOFF:** reescrever em `docs/process/estudos/2026-10-12-a-volta/HANDOFF.md`, apontando para este plano e
  para a onda 0, com a frase de abertura da sessão nova. É o último passo desta sessão.
- **A ficha da MeowSystem:** em voo (`wf_dc595d13-a6e`), fora do Hefesto (`/mnt/Apate/Desenvolvimento/specs/`,
  porta 8768). Não entra nas ondas.
- **O Sackboy (D1):** as rodadas já rodaram sozinhas e mediram. A `d1-volta-1210-d-dois` mostrou que a cura do
  gadget não curou o engasgo. A `d1-a-quem-varre` (15h38 a 15h44) reproduziu a corrida. **A causa ainda é
  proposta, não provada.** Os dois estudos (`leva-volta/d1-sackboy/`) propõem curas diferentes:
  - **Estudo A:** o pad do Controle 1 nasce no gadget antes do registro de identidade
    (`uhid_gamepad.py:2431/2471`), então o som dele fica sem par; e o próprio gadget passa no filtro de «controle da
    mesa» (`alto_falante.py:596`), o que cria saídas a mais. O jogo vê 4 saídas para 2 controles.
  - **Estudo B:** o crescimento segue a conta «varreduras por segundo × dispositivos × ~1,13 KiB». A poda é em
    `endpoint_de_haptica.py`, `alto_falante_bt.py`, `audio_ks_dualsense.py`, `daemon/launch_env.py`,
    `assets/hefesto-launch.sh` e nas regras do WirePlumber.
  - **A rodada com pads virtuais** (`bancada-do-jogo/d1-vpads-1210`, 15h59 a 16h05) pôs dois pads de mentira dentro
    do jogo, apertando X, e mediu 5 minutos: **nenhum quadro acima de 33 ms**, mediana de 16,7 ms. Ela não
    reproduziu o engasgo, então ainda não decide entre A e B.
  - A sprint da onda 0 escreve as duas hipóteses e a régua que separa uma da outra. O conjunto sackboy só implementa
    a que a rodada provar. A cura corta só o que é órfão ou duplicado, sem perder nada, no cabo e nos três
    adaptadores BT, em todo modo e máscara, com os quatro controles. A posse dele cruza com pad e som (onda 1), tato
    (onda 5), legado, terminal e v-jogos (`launch_env.py`).
  - **A medida do engasgo roda sozinha, e o P2 entra pelo pad virtual. O clique dela no jogo fica só para o
    veredito final: sente ou não sente.**
- **As 12 «esquecidas»** que o `sprint.py validar --todas` acusa: 10 já estão `absorvida` mas seguem na fila do
  `SPRINT_ORDER` (PODA-DO-DATADO, PARIDADE-NO-JOGO-BANCADA, TESTAR-O-MICROFONE, O-REPO-QUE-SE-LE, O-ENGASGO-SE-CURA,
  A-VOLTA-DO-MICROFONE, O-BOTAO-DO-MIC, O-JOGO-COM-O-DETECTOR-DA-SONY, A-ILUMINACAO-GANHA-A-REACAO,
  OS-TRES-CONTROLES-DE-FREQUENCIA). Saem da fila na onda 0. As outras duas: A-SUITE-NAO-ACORDA-A-PLACA (o `cria` já
  existe, porque o código está no `dev`: fecha à mão) e A-FORJA-SEM-RASTRO (o `cria` já existe: o conjunto github
  confere a posse antes de voar).
- **O-BASICO-MEDIDO segura 17 fichas.** Ela é «só bancada, sem agente», mas 17 sprints têm `depois_de` nela
  (5 do ipc, 3 do install, 2 do tato, 2 da F2-controle e outras). Entra na inversão de cada despacho.
- **Ainda sem ficha (a onda 0 escreve):** a cura do Sackboy; o pad USB (os gadgets enumeram em série a ~5,5 s, o
  terceiro e o quarto passam dos 15 s e caem no uhid; todos saem com o mesmo endereço; 22.155 `ENOMEM`); o
  semáforo pedir as três vagas de uma vez; o `fecho-ate-verde.sh` não repetir vermelho determinístico; o
  `test_os_atalhos_na_espera` sem o `sleep(0.15)` fixo; `hci1` × `hci2`; o resíduo do alto-falante; os fatos
  errados (`install.sh:3381` diz `interface.hefesto_vivo:main`, o certo é `interface.abrir:entrada`;
  `a03_gatilhos.py` diz «6 barras/73», o certo é 4/71); a ordem de tela das 14h40 (um botão só, «Modo
  Automático», nas abas 01 a 05; botões bonitos; a guia de controles na 05; o espaçamento vertical da 05), que vai
  para os mockups do todo; e a foto do estado das 20 mudanças que ficaram fora da foto.

## O que o advogado mudou

Conferido contra o git e as fichas, só lendo: as 223 linhas da seção 4 (todas, não amostra), os 12 conjuntos
cortados (`git cherry` e base de cada um), a colisão (`check_colisao_de_sprints.py`: `rc=0`, 392 anotadas, 9 avisos
de caminho que não existe) e a posse de cada onda, conjunto contra conjunto.

**O que estava certo e ficou:** a conta (371 fichas; 148 fechadas; 223 faltam, e os blocos somam 29 + 16 + 43 + 86
+ 49); os 49 `+` do `git cherry dev integra/fds-1`, 10 da 1-11 com hash velho e 39 só da fds; os 75 commits dos 12
cortados, com as quatro bases; nenhum par de cortados toca o mesmo arquivo; as ondas 1, 2, 3, 5 e 6 antigas sem colisão de posse
dentro delas.

**O que estava errado e mudou:**

1. **A retomada reaplicaria a história velha.** O `git rebase integra/fds-2` levaria de 146 a 169 commits, entre
   eles os 10 da 1-11 com hash velho, e daria conflito. Agora é `git rebase --onto integra/fds-2 <base>`, com a
   base de cada conjunto.
2. **O ONDA e os args.** O `leva-fds/leva.env` tira a integração do arquivo `leva-fds/ONDA`, que diz 1: sem trocar
   para 2, toda ferramenta aponta para a `_integra-fds-1`. O `regerar-conjuntos.py` grava Opus e `xhigh` fixos e
   numera as integrações pelo plano velho da fds. Os args dos 9 conjuntos que nunca voaram são rascunho contra a
   `_integra-1-11`. A onda 0 agora troca o ONDA, acerta o regerar e regera.
3. **O molde não precisa mudar.** Ele já lê `esforco_confere || 'high'` e `modelo || 'sonnet'`. Quem precisa
   mudar é o regerar.
4. **Não existia `leva-volta/leva.env` nem `leva-volta/ONDA`.** A seção 6 diz como nascem, e dá nome às quatro
   integrações da volta.
5. **A onda 4 antiga não podia voar:** 15 colisões de posse entre laco, legado, terminal, diario e evento. Legado,
   laco, diario, dsu e v-usb tocam todos o `lifecycle.py`: são cinco ondas, uma para cada. As ondas 4 a 8 novas têm
   de 2 a 3 conjuntos, e a seguinte sai por conjunto, assim que quem colide costurou.
6. **A onda 8 antiga também colidia:** tela-a × tela-b (`profiles/schema.py`), e tela-c dependia das duas na mesma
   onda. Agora é tela-b (9) → tela-a (10) → tela-c (11). O mesmo valia para v-toque → v-jogos na onda 6: o v-toque
   foi para a 8.
7. **`depois_de` para a frente.** O plano velho tinha 136 `depois_de` (fora os dois genéricos) que apontavam para a
   mesma onda ou depois. O novo tem 119 para a frente e nenhum dentro da mesma onda. Todos são de posse, e o
   `inverter-depois-de.py` antes de cada despacho entrou nas regras (seção 3 e item 2 da seção 6).
8. **Prioridade do defeito.** Pad e som subiram para a onda 1, porque tocam os arquivos do Sackboy, e o Sackboy
   subiu da onda 3 para a 2.
9. **O defeito de produto não espera desenho.** A O-SUBSYSTEM-SOBE-E-DESCE estava na F2-acessibilidade, atrás «dos
   desenhos T2/T3». Ela não é de tela: virou o conjunto subsystem, na onda 9, sem esperar desenho nem ela. Ela também
   tem de vir antes da F2-controle, que a espera (no plano velho vinha depois).
10. **A causa do Sackboy estava escrita como achada.** Os estudos A e B propõem curas diferentes, e a rodada com pads
    virtuais (15h59 a 16h05) não reproduziu o engasgo: nenhum quadro acima de 33 ms. Agora o plano diz «proposta», e
    o conjunto só implementa o que a rodada provar.
11. **O carimbo das 29.** O `fechar` mede pelo `git cherry`, então o hash velho não atrapalha. Mas a
    A-SUITE-NAO-ACORDA-A-PLACA está `aberta`, e o `fechar` a recusa: ela fecha à mão. A forja-fds precisa do
    `costurar` com a Forja antes.
12. **O que o plano não via:** os run IDs de som, radio, carga, lancadores, kyty e dsx existem (o implementa não
    fechou); o args do lancadores traz uma ficha que espera ela; duas fichas de tela da F2-acessibilidade esperam
    ela; as 12 «esquecidas»; a O-BASICO-MEDIDO segura 17 fichas.

**Os números de agora:** 148 concluídas (mais 29 no `dev` à espera do carimbo); 16 costuradas fora do `dev`; 43
cortadas na metade (12 conjuntos, 75 commits); 86 por fazer; 49 esperam ela; ~10 novas sem ficha. **16 ondas
(0 a 15), 5 fechos, 39 conjuntos, 81 agentes** (82 com a cura da base).

