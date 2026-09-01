#!/usr/bin/env python3
"""Gera a aba JOGAR — `layout/01-jogar.html`.

POR QUE ELA PASSOU A TER GERADOR — 29/08/2026, e o custo foi MEDIDO nos dois
sentidos antes de escrever uma linha.

**O preço de não ter, e ele já foi pago quatro vezes.** A 01 era a única das dez
escrita à mão, e a divergência não é hipótese — está contada:

1. **A cura do logotipo de 28/08 chegou a UMA das dez páginas.** Ela mandou tirar
   os quatro `<title>` minúsculos do logo (passar o mouse na bolinha rosa escrevia
   "bolinha-rosa" na tela dela). Quem curou editou o arquivo que tinha na frente —
   a 01, à mão — e não o `topo.html`, que é a fonte das outras nove. Medido em
   29/08, antes desta volta: `grep -c` dos quatro rótulos dava **0 na 01-jogar e 4
   em cada uma das outras nove**. Trinta e seis instâncias vivas do defeito que ela
   mandou caçar.
2. **Trinta linhas do esqueleto compartilhado não existem na 01.** Contadas contra
   o `topo.html`: as outras abas deixam de fora 4 a 6 linhas (as que o `monta()`
   substitui — título, fita, tira); a 01 deixa **34**, e **30** delas estão nas
   outras nove.
3. **A folha de estilo tem duas cópias mantidas à mão, e elas divergiram em nove
   blocos** — 18 linhas do `topo.html` trocadas por 107 da 01. Duas dessas
   divergências não são inofensivas, porque a classe é COMPARTILHADA: `.pecas` é
   usada pela 01 e pela **10-perfis** (5 vezes), e `.cartao` pela 01 e pela
   **08-conexoes** (3 vezes). A mesma classe quer dizer duas coisas em dois
   arquivos, e quem corrigir uma corrige metade.
4. **O rodapé era declaradamente uma cópia gêmea.** O comentário dele dizia, com
   todas as letras: *"Esta aba é mantida à MÃO: a cópia gêmea está no
   `_ferramentas/fim.html`, e as duas mudam juntas."* Duas versões vivas, com o
   aviso escrito ao lado.

E um fato errado que a 01 carregava e o `topo.html` já tinha corrigido: o
comentário dos SVGs dizia *"32 peças nomeadas e as cinco cores de plástico"*.
Medido nos CSVs donos: **28 peças** (`docs/data/pecas-do-dualsense.csv`) e **28
modelos de cor** (`docs/data/cores-do-dualsense.csv`).

**O preço de ter, e ele é baixo.** O miolo da 01, com os nove `<svg>` trocados
por um marcador, tem **181 linhas** — os SVGs são 66% do arquivo e já eram
gerados (o `regerar.py` chamava `monta.svg()` para os quatro cartões). O que
sobra é: 83 linhas antes dos cartões, os quatro cartões (que viram um laço de
uma função de 14 linhas) e 32 depois. O `monta()` já escrevia o esqueleto, a
tira, a fita, a contagem do cabeçalho, o rodapé e a legenda — de graça, porque
as outras nove já o usam.

Este arquivo tem menos linhas que o `aba04.py` e mais que o `aba07.py`, que é o
menor dos nove (225).

**O que a `regerar.jogar()` fazia, e onde foi parar.** Ela existia para trocar
NA MÃO o que num gerador não precisa de troca: o desenho dos quatro cartões, a
caixa de máscara de cada um e a frase da legenda. As três coisas nascem aqui
agora, e a `jogar()` sai do `regerar.py` — remendar um arquivo escrito à mão era
o preço de ele ser escrito à mão.

Uso:  aba01.py
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402
import monta  # noqa: E402
from monta import MASCARAS, MESA, glifo, monta as montar, rotulo, svg  # noqa: E402

# ---------------------------------------------------------------------------
# A CENA
# ---------------------------------------------------------------------------
#: A bateria de cada controle — **o único dado inventado desta aba**, e a
#: legenda o declara desde 26/08. Tudo o mais sai da `monta.MESA` (quem está na
#: mesa, o número, a cor, o transporte, a máscara) ou do desenho (o hexadecimal
#: do plástico). Na mesa viva dela agora há DOIS controles, com 85% e 95%.
BATERIA = {"p1": 100, "p2": 64, "p3": 41, "p4": 87}

#: O aviso da coluna Atenção. Também cena, e também declarado na legenda: o
#: `state_full` não publica contagem nem texto de aviso, e a frase
#: *"Dois rádios da bancada estão em portas vizinhas"* é da aba Conexões
#: (`aba08.py`), não do produto.
AVISOS = [("RÁDIO", "Dois rádios da bancada estão em portas vizinhas.")]

#: O INTERRUPTOR — **HEFESTO LIGADO / DESLIGADO**, decisão dela de 31/08/2026.
#:
#: A PERGUNTA QUE ABRIU ISTO É DELA, e ela era boa: *"qual a diferença de nativo
#: pra dualsense?"*. A tela antiga punha os dois na MESMA fileira, como
#: alternativas do mesmo tipo — e não são. Um é **sem** o Hefesto no meio; o
#: outro é uma **cópia virtual** que ele controla. A resposta dela foi
#: redesenhar:
#:
#:   *"vamos desconfundir isso que tal? Hefesto Ligado/Desligado, Modo Navegação
#:   (Teclado e mouse), Modo Nativo (Dualsense da Forma como veio ao Mundo). Modo
#:   Hefesto se Ligado Abre as seções de Modo, Steam Input, Xbox, Sony DualSense,
#:   Point And Click. Esses 4 modos independente de tudo. Vão utilizar as
#:   features do hefesto. E em Baixo temos a parte das Mascaras dos Controles."*
#:
#: **CADA POSIÇÃO É UM MODO REAL DO PRODUTO, com leitor E escritor** — e é isso
#: que faz esta forma valer mais do que a fileira que ela substitui:
#:
#:   - **Ligado** = `mode_transition.MODE_GAMEPAD`. Lê por `mode_of_state`,
#:     escreve por `apply_mode('gamepad')` (`painel.ESCRITOR_DOS_MODOS`), e o que
#:     ele grava no disco é o `gamepad_disabled.flag` — a resposta à pergunta dela
#:     de 31/08, *"não sei se segue desativado"* (`painel.modo_lembrado`);
#:   - **Desligado** = `MODE_NATIVE`, que é também o **degrau 3** da
#:     `ponte_escada.ESCADA`. Também tem leitor e também tem escritor.
#:
#: **O BOTÃO SEM DONO MORREU AQUI, e não por eu ter tirado.** A fileira antiga
#: tinha um quarto botão "Desligado" que era um estado INVENTADO: `mode_of_state`
#: é o ponto único de leitura do modo vivo e devolve TRÊS valores, nunca um
#: quarto (`painel.MODOS_DA_TELA` declara o porquê, e a MIGRA-JOGAR-06 levava a
#: pergunta a ela). A decisão dela responde a pergunta **sem construir nada**:
#: "Desligado" passa a querer dizer **Modo Nativo**, que existe, lê e escreve.
#: Parar o Hefesto INTEIRO continua sendo "Parar o serviço", na aba Sistema.
#:
#: A PALAVRA É "PARAR", E FOI ESCOLHA DELA EM 31/08/2026. Esta linha dizia
#: "encerrar" e a aba Sistema passou a escrever "Parar o serviço" — contradição
#: no VERBO, criada no mesmo dia em que a do substantivo foi desfeita. Ela
#: escolheu "parar": é o que o `systemctl stop` faz, é o par natural de
#: "Ligado", e "encerrar" sugeria fim definitivo quando o serviço volta no
#: próximo login.
#:
#: A chave do meio é o `data-modo`, e ela casa com `mode_transition.MODES` —
#: é por ele que `controles_vivos.INTERRUPTOR` acende, trava e aplica.
INTERRUPTOR = [
    ("ligado", "gamepad", "Ligado",
     "O Hefesto fica no meio: ele acende as luzes, faz o controle vibrar, dá um "
     "jogador para cada controle e escolhe como o jogo vê o aparelho."),
    # O TEXTO ENCOLHEU — decisão dela, 31/08/2026, e ela deu a regra em duas frases:
    #
    #     "o modo nativo já existe ali (…) e se eu quiser desligar modo hefesto
    #      clico em desligado e o modo nativo fica online. Qualquer coisa fora
    #      isso tá incorreta."
    #
    # SAIU: *"os gatilhos ficam duros como no PS5. Alguns jogos derrubam o
    # controle no meio da partida assim."* — a segunda metade é AFIRMAÇÃO FORTE
    # sem régua: nenhum ensaio deste repositório mede "alguns jogos derrubam".
    # Alarme sem medição é o que esta casa cobra no `check_paridade_transporte`.
    ("desligado", "native", "Desligado",
     "Modo Nativo: o Hefesto sai do meio e o jogo fala direto com o controle."),
]
#: Em qual posição a cena nasce.
HEFESTO_LIGADO = True
#: O "AUTOMÁTICO" CONTINUA FORA — 31/08/2026, palavra dela: *"na aba jogar o
#: Botão Automático não existe."*, e a regra que a frase fixou
#: (`docs/process/2026-08-30-RETOMADA-o-estado-real-e-o-que-fazer.md` §1.2) é
#: **botão sem dono no produto não vai para a tela**. Ele não tinha os dois:
#: `painel.CHIPS_DA_ESCADA` o declara com `ponte=None`, e `degrau_vivo` acende
#: comparando pontes — nenhuma `Ponte` é igual a `None`, então nenhum estado do
#: produto podia acendê-lo; e não há IPC que fixe um degrau.
#: **O MECANISMO NÃO SAIU — só o botão:** "tenta na ordem e para quando acerta" é
#: o que `integrations/ponte_tentativa` faz sozinho, sempre, e está dito na dica.
#: (Não confundir com o "Automático" da MÁSCARA, que caducou em 29/08 por
#: ERRAR — 13 dos 14 jogos dela.)
#:
#: OS CINCO MODOS DE DENTRO DO HEFESTO LIGADO — decisão dela, 31/08/2026:
#: *"Modo Hefesto se Ligado Abre as seções de Modo, Steam Input, Xbox, Sony
#: DualSense, Point And Click"*, mais a **Navegação**, que ela pôs aqui dentro
#: respondendo à dúvida que sobrou: quem emula teclado e mouse é o daemon do
#: Hefesto, então com ele desligado não existe teclado nem mouse.
#:
#: O QUE A ESCADA PLANA DE QUATRO ESCONDIA, medido hoje contra
#: `integrations/ponte_escada.ESCADA`:
#:
#:   - o chip chamado **"Hefesto"** era `Ponte(KIND_GAMEPAD, MASCARA_DUALSENSE)`
#:     — o nome do PRODUTO no lugar do nome da máscara, numa tela em que os
#:     outros três também são o Hefesto. Vira **Sony DualSense**;
#:   - o degrau **Xbox** (`Ponte(KIND_GAMEPAD, MASCARA_XBOX)`), que é o
#:     **segundo** que o produto tenta, **nunca chegou à tela** — era o que
#:     `painel.degraus_sem_chip()` denunciava. Entra agora;
#:   - **"Teclado + Mouse"** não existe na `ESCADA` (`KIND_DESKTOP` é constante,
#:     e `indice_do_degrau` devolve -1). Vira **Navegação**;
#:   - **"Nativo"** sai da fileira: é o interruptor DESLIGADO.
#:
#: NÃO HÁ ALGARISMO — decisão dela, 31/08/2026, e ela resolveu uma contradição
#: de três pontas que a própria tela carregava:
#:
#:   a tela escrevia   ③ Steam Input
#:   o produto tenta   em QUARTO (`indice_do_degrau + 1` == 4)
#:   a legenda dizia   que o número É `indice_do_degrau + 1`
#:
#: Os três não podiam estar certos, e a causa era a decisão dela do mesmo dia: o
#: terceiro degrau é o **Nativo**, que saiu da fileira para virar a posição
#: DESLIGADO do interruptor. Sobravam três saídas — numerar 1·2·4 com um buraco
#: no 3, numerar pela posição na tela (e a legenda passar a mentir), ou tirar os
#: números. **Ela escolheu tirar.**
#:
#: A ORDEM NÃO SE PERDEU: ela mora na dica de cada modo ("é o primeiro que o
#: Hefesto tenta", "é o segundo", "é o último") e na dica do quadro "Quando o
#: jogo abrir" — que é para onde ela subiu quando o interruptor saiu do quadro
#: (31/08, à tarde); até ali ela morava no rótulo "Modo", lá dentro.
#: O que saiu foi o número, que era a única peça que podia divergir do produto
#: sem ninguém notar — e tinha divergido.
#:
#: `sem_dono` é o que a casa exige desde 30/08 (*botão sem dono no produto não
#: vai para a tela como se funcionasse*) casado com a ordem dela de MANTER os
#: dois: eles aparecem, e **dizem** que ainda não têm quem os atenda.
#: O POINT AND CLICK SAIU DA FILEIRA — decisão dela, 31/08/2026: *"nos mockups
#: tira o point and click e deixa só o navegação."* Confirmada no mesmo dia: sai
#: **só da fileira**. O perfil de fábrica `assets/profiles_default/point_and_click.json`
#: continua, e o `Estilo Point-and-click` da aba Navegação continua. É o MODO que sai.
#:
#: DE QUEBRA, `sem_dono` FICOU SEM USO: o `pointclick` era o único chip marcado
#: assim. A regra CSS `.degrau.sem-dono` fica de pé de propósito, e não é
#: esquecimento — ela é a gramática desta casa para *"botão que aparece e diz que
#: ainda não tem quem o atenda"*, e a próxima fileira que precisar dela não vai
#: ter de reinventá-la. O campo continua no dicionário pelo mesmo motivo.
#:
#: AS DICAS FORAM REESCRITAS — pedido dela, 31/08/2026, com estas palavras:
#:
#:     "independente do modo, todas as features vão funcionar. Então o tooltip
#:      falando o contrário é sem nexo."
#:     "todos os tooltips tem que ser corrigidos e simplificados."
#:
#: DUAS AFIRMAÇÕES CAÍRAM, e elas se sustentavam uma na outra:
#:
#:   o Xbox dizia        "sem giroscópio e sem touchpad para o jogo"
#:   o DualSense dizia   "dez linhas do mapa-controles.csv só chegam ao jogo por aqui"
#:
#: Se a feature chega em todo modo, "só por aqui" cai junto com "sem giroscópio".
#: O que sobra em cada dica é o que de fato MUDA entre os modos: **como o jogo
#: desenha os botões** e **em que ordem o Hefesto tenta**. Luz, vibração, gatilho,
#: giroscópio, áudio e o número do jogador seguem por conta do Hefesto nos quatro
#: — e isso se diz UMA vez, na dica do quadro, não quatro vezes aqui.
#:
#: E ELAS ENCOLHERAM: as cinco dicas somavam 1.147 caracteres e passaram a somar
#: 396. A dica que ocupa meia tela não é lida — é fechada.
MODOS = [
    {"chave": "dualsense", "rot": "Sony DualSense", "modo": "",
     "sem_dono": False,
     "dica": "O jogo desenha os botões do PlayStation. É o primeiro que o "
             "Hefesto tenta."},
    {"chave": "xbox", "rot": "Xbox", "modo": "",
     "sem_dono": False,
     "dica": "O jogo desenha os botões do Xbox — o formato que todo jogo "
             "entende. É o segundo que o Hefesto tenta."},
    {"chave": "steam", "rot": "Steam Input", "modo": "",
     "sem_dono": False,
     "dica": "A Steam entrega a entrada, e os seus ajustes vencem os do jogo. "
             "Trocar para cá exige reabrir a Steam e o jogo — por isso é o "
             "último que o Hefesto tenta."},
    {"chave": "navegacao", "rot": "Navegação", "modo": "desktop",
     "sem_dono": False,
     "dica": "O controle vira teclado e mouse do computador. O PS+R3 ainda não "
             "para aqui."},
]
#: O MODO ACESO. `ponte_escada.ESCADA[0]` é `Ponte(KIND_GAMEPAD,
#: MASCARA_DUALSENSE)`, que é este chip — a cena acende o que o produto acenderia.
MODO_ACESO = "dualsense"

#: A pendência da faixa de baixo — o que o **Aplicar** vai gravar.
#:
#: ELA ESTAVA CRAVADA E CONTRADIZIA A PRÓPRIA TELA. Ela viu, em 31/08/2026:
#: *"'Vai mudar para Modo Nativo quando você clicar em Aplicar' essa frase tá
#: errada também. viu?"* — e estava. A tela desenha o interruptor em **Ligado**
#: com **Sony DualSense** marcado, e a faixa anunciava **Modo Nativo**, que é a
#: posição **Desligado**. Os dois estados na mesma foto, um contradizendo o outro.
#:
#: A CURA NÃO É TROCAR O LITERAL: é DEIXAR DE TER UM. A frase passa a sair de
#: `MODO_ACESO`, que é o mesmo dado que acende o chip — então ela não tem como
#: discordar do que está desenhado. É a mesma cura que a `frase_das_mascaras()`,
#: o padrão das lâmpadas e a contagem do cabeçalho já receberam nesta casa.
PENDENTE = next(m["rot"] for m in MODOS if m["chave"] == MODO_ACESO)


# ---------------------------------------------------------------------------
# O CSS QUE É SÓ DESTA ABA
#
# Ele entra DEPOIS do `<style>` do esqueleto (é o que o `monta()` faz com o
# `css_extra`), então cada regra daqui vence a homônima de lá pela cascata — que
# é como as outras nove abas já fazem. A alternativa era editar o `topo.html`, e
# ela é o defeito: `.pecas` e `.cartao` são de mais de uma aba, e mudar a regra
# compartilhada para servir a esta mudaria a 10-perfis e a 08-conexoes junto.
# ---------------------------------------------------------------------------
CSS = """
  /* ---------- A ABA JOGAR ---------- */

  /* ---------- O INTERRUPTOR DO HEFESTO (31/08/2026) ----------
     SEM UMA LINHA DE JAVASCRIPT, como as outras nove abas: dois `radio` com o
     mesmo `name`, escondidos, e `<label for>` por cima. É o MESMO mecanismo do
     acordeão da Controles (`aba02`) e das seções que abrem da Conexões
     (`topo.html`) — o navegador já garante que ligar um desliga o outro. O
     mockup abre por duplo clique, e é regra desta casa que continue assim.

     POR QUE `label` E NÃO `button`: só o par `radio` + `label` muda de estado
     sem script. O preço está medido e declarado no relatório desta leva — a
     ponte viva (`controles_vivos.INTERRUPTOR`) chama `ev.preventDefault()` no
     clique, e num `label` isso IMPEDE o rádio de mudar. É uma linha lá, não
     aqui. */
  .hef-rd{position:absolute;width:0;height:0;opacity:0;pointer-events:none}

  /* ---------- ELE SUBIU PARA FORA DO QUADRO — 31/08/2026, à tarde ----------
     ENQUADRAMENTO, e o defeito era de significado, não de pixel: o interruptor
     nasceu DENTRO do quadro "Quando o jogo abrir", e um quadro é um escopo. Ali
     ele lia como *"ligar o Hefesto quando um jogo abrir"*, e não é isso — o
     Hefesto ligado ou desligado vale SEMPRE, com jogo aberto ou sem nenhum. O
     que é decidido no lançamento é o MODO, e só ele fica no quadro.

     ELE É FILHO DIRETO DO MIOLO, e o precedente é a FITA do `topo.html`
     ("Ajustes vão para: [Todos] [P1…]"): rótulo deitado + a fileira do que se
     escolhe, sem moldura, acima do que ela governa. A diferença é o escopo —
     a fita é da JANELA (fica acima da tira, nas dez abas) e este é da ABA, logo
     mora no miolo, que é onde a aba começa.

     O `padding-left` de 15px NÃO É MARGEM: é o que põe o "Hefesto" no MESMO x
     dos títulos dos dois quadros (o `.quadro-titulo` nasce em dx=15 — 1px de
     borda + os 14 do `--pad-quadro`, e a régua mede isso). Sem ele o rótulo
     ficava 15px à esquerda de "Quando o jogo abrir" e "Conectado agora", que é
     o desalinhamento que ela cobra desde 27/08. E tem de ser PADDING, não
     margem: a régua exige que todo filho direto do miolo comece no x do miolo e
     tenha a largura inteira — padding não move a caixa de borda, margem move. */
  .hef-topo{padding-left:15px}

  /* O RÓTULO FICA NA MESMA LINHA DO INTERRUPTOR — e continua deitado por uma
     razão que sobreviveu à mudança de lugar. Um `linha-rot` por cima custa 22px;
     deitado custa zero, e é a forma que ela desenhou: `HEFESTO [ Ligado ● /
     Desligado ○ ]`, tudo numa linha. O orçamento hoje é outro (a subida do
     interruptor DEVOLVEU 13px em vez de custar), mas a forma é dela. */
  .hef-linha{display:flex;align-items:center;gap:8px}
  .hef-linha .ajuda{margin-left:2px}
  .hef-linha .linha-rot{margin-bottom:0;flex:0 0 auto;margin-right:6px}
  .hef-pos{
    height:var(--h-escolha);display:inline-flex;align-items:center;gap:9px;
    padding:0 18px;border-radius:7px;font-size:12.5px;
    border:1px solid var(--linha);background:var(--app-bg);color:var(--texto-mudo);
    cursor:pointer;user-select:none;
  }
  .hef-pos:hover{border-color:var(--comment);color:var(--texto-suave)}
  /* ● / ○ — o marcador das duas posições, e é o `.pino` do interruptor que a
     Navegação (`aba06`) já usa: mesmo tamanho, mesmo verde, mesmo brilho. */
  .hef-pos .pino{width:9px;height:9px;border-radius:50%;flex:0 0 9px;
                 border:1px solid var(--linha);background:transparent}
  /* ACESO POR DOIS CAMINHOS, e os dois têm de existir. O `:checked` é o do
     MOCKUP — ela clica no arquivo, sem daemon nenhum. O `.on` é o da PINTURA
     VIVA: `controles_vivos.INTERRUPTOR` escreve `.on` em `[data-modo]` a partir
     do `mode_of_state`. Sem o segundo, a tela viva mostraria o DESENHO em vez do
     estado do daemon — o F7 desta casa, e foi exatamente o defeito medido em
     31/08: a tela mostrava "Jogar pelo Hefesto" aceso com o daemon em `desktop`.
     O ENDEREÇO NÃO SE ESCREVE NESTE COMENTÁRIO, e a razão é uma régua real: o
     `test_o_botao_de_ligar_funciona_e_se_lembra` lê os endereços do HTML por
     EXPRESSÃO REGULAR, e um exemplo citado dentro de um comentário entra na
     conta como se fosse botão. É a mesma armadilha que pôs o logotipo inteiro
     dentro de um comentário de CSS em 30/08 — o `replace` casou com a citação. */
  #hef-ligado:checked ~ .hef-linha .hef-pos.ligado,
  #hef-desligado:checked ~ .hef-linha .hef-pos.desligado,
  .hef-pos.on{border-color:var(--purple);background:var(--sel-bg);
              color:var(--fg);font-weight:600}
  #hef-ligado:checked ~ .hef-linha .hef-pos.ligado .pino,
  .hef-pos.ligado.on .pino{background:var(--green);border-color:var(--green);
                           box-shadow:0 0 7px var(--green)}
  #hef-desligado:checked ~ .hef-linha .hef-pos.desligado .pino,
  .hef-pos.desligado.on .pino{background:var(--texto-mudo);
                              border-color:var(--texto-mudo)}

  /* AS DUAS SEÇÕES SÃO EXCLUSIVAS, e é isso que ela pediu: *"Modo Hefesto se
     Ligado Abre as seções de Modo"*. Continua SEM UMA LINHA DE JAVASCRIPT.

     O COMBINADOR MUDOU DE `~` PARA `:has()`, e a troca é FORÇADA, não gosto.
     Com o interruptor fora do quadro, os rádios deixaram de ser irmãos das duas
     seções — o `~` só enxerga irmão POSTERIOR, e agora há uma borda de quadro no
     caminho. Havia duas saídas:

       a) pendurar os dois `<input>` direto no `.miolo`, e daí o `~` alcançaria
          (`#hef-ligado:checked ~ .quadro .so-ligado`). REPROVADA, e por uma
          régua real: `regua.py` exige que TODO filho direto do miolo comece no x
          do miolo e tenha a largura inteira, e um `input` de 0×0 é filho direto
          com largura própria. A cura teria custado um erro na régua da aba que
          É a referência das outras nove;
       b) `:has()` no invólucro, que é o que está aqui. NÃO É MECANISMO NOVO
          NESTA CASA: o `topo.html` já abre e fecha as seções da Conexões com
          `.quadro:has(> input.abre:not(:checked))`, e o WebKitGTK desta máquina
          é 2.52.3 — `:has()` entrou no WebKit em 2.38.

     A ESPECIFICIDADE FECHA: `:has()` vale o do argumento mais específico, então
     a regra que MOSTRA leva um `#id` e vence a que esconde, que é só classe. */
  .hef-topo ~ .quadro .so-ligado,
  .hef-topo ~ .quadro .so-desligado{display:none}
  .hef-topo:has(#hef-ligado:checked) ~ .quadro .so-ligado{display:block}
  .hef-topo:has(#hef-desligado:checked) ~ .quadro .so-desligado{display:block}
  /* E ELAS ABREM NO MESMO y E FECHAM NO MESMO y — 180 contra 176 foi o que se
     mediu quando divergiram, e "muda tudo ao clicar" é a queixa dela que fixou a
     altura única das dez abas; ela vale dentro de uma aba também.
     A CAUSA ORIGINAL SUMIU E A TRAVA FICOU, de propósito: o `?` que só a seção
     do LIGADO tinha subiu para o topo do quadro (ele passou a ser a ajuda do
     quadro inteiro, que agora só tem os modos dentro), então os dois rótulos são
     texto puro e já nasceriam iguais. A linha continua aqui porque é ela que
     GARANTE a igualdade — sem ela, o dia em que um dos dois ganhar um ícone a
     tela volta a pular, e ninguém vai lembrar por quê. A cura é na ALTURA. */
  .hef-modo > .linha-rot{display:flex;align-items:center;height:17px}

  /* O CHIP SEM DONO — a honestidade desta tela, e ela tem uma regra e uma ordem
     em cima. A regra é de 30/08 (*botão sem dono no produto não vai para a tela
     como se funcionasse*); a ordem dela, de 31/08, é MANTER o Point And Click e
     a Navegação. As duas convivem de um jeito só: eles aparecem e DIZEM que
     ainda não têm quem os atenda.
     NADA DE `opacity`, e a razão é medida (`topo.html`, a fita inerte): a
     opacidade mora no ancestral, o texto cai para ~2:1 e TODA régua de contraste
     que lê `color` fica cega a isso. Aqui é cor explícita, borda tracejada — que
     é como esta casa já escreve "isto ainda não vale" (`.avisos.vazio`,
     `.pendente`) — e o cursor de "não clique". O porquê está no `title`. */
  .degrau.sem-dono{border-style:dashed;color:var(--comment);cursor:not-allowed}
  .degrau.sem-dono:hover{border-color:var(--linha);color:var(--comment)}
  .degrau.sem-dono i{border-style:dashed}
  /* O TRAÇO NO LUGAR DO ALGARISMO. O círculo diz a ordem em que o Hefesto TENTA
     sozinho; quem não é degrau da `ponte_escada.ESCADA` não tem ordem nenhuma, e
     um número ali diria que o PS+R3 para naquele modo. É a mesma disciplina do
     `painel.SEM_LEITOR`: um traço, e não um zero. */
  .degrau i.tr{color:var(--comment);border-style:dashed}
  /* A FAIXA DO DESLIGADO não se clica: ela não é uma escolha, é o que o
     interruptor JÁ escolheu. Sem `cursor:pointer` e sem `:hover`. */
  .degrau.fixo{cursor:default;justify-content:flex-start;padding-left:14px}
  .degrau.fixo .mud{color:var(--texto-mudo);font-weight:400}

  /* OS QUATRO NUMA FILEIRA SÓ, E TODOS DA MESMA LARGURA. Era `flex`, e os dois
     cartões mediam 228.8 e 225.2 px — a largura vinha do nome do plástico. */
  .pecas{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}

  /* O CARTÃO VIROU COLUNA em 28/08, e o motivo é a decisão dela: a máscara
     passou a ser POR CONTROLE, e o seletor dela mora aqui dentro. Em cima a
     peça (desenho + rótulo), embaixo as três máscaras.
     A BORDA É A COR DO PLÁSTICO, E ELA VEM DO DESENHO
     (D-A-BORDA-E-A-IDENTIDADE-DA-PECA). Eram duas classes, `.c-red` e
     `.c-blue`, lendo dois hexadecimais do `:root`. Com quatro controles na mesa
     faltariam duas; com os 28 do CSV de cores, vinte e seis. O `--plastico` é o
     mesmo mecanismo do chip da fita, e o valor sai de `monta.cor_da_zona`, que
     lê o `<style>` que o gerador escreveu no SVG. */
  .cartao{
    display:flex;flex-direction:column;align-items:stretch;gap:7px;
    padding:5px 6px 6px;
    border-color:var(--plastico, var(--border-forte));
  }
  .peca-topo{display:flex;align-items:center;gap:6px}
  /* A ENTRELINHA É A CURA DO VÃO, e ela é na ALTURA — encolher o mais alto.
     Com `1.45` o cartão media 67,5px e a coluna de avisos ao lado, 55: doze e  # noqa-acento  (`media` é o verbo medir)
     meio de vão. Em pixel, e não em múltiplo, porque o rótulo tem três linhas
     e cada pixel aqui vale três. */
  .cartao .rotulo{color:var(--texto-mudo);line-height:15px;white-space:nowrap}
  .cartao .rotulo b{color:var(--fg);font-weight:500}
  .cartao .bat{color:var(--green);font-family:'JetBrains Mono',monospace;font-size:11px;
               display:inline-flex;align-items:center;gap:3px;
               line-height:1;vertical-align:-2px}
  /* o glifo da bateria é o MESMO arquivo da aba Controles: assets/glyphs/bateria.svg */
  .cartao .gl{display:inline-block;flex:0 0 auto}
  .cartao .ds-svg{width:62px;flex:0 0 62px}
  /* AS CINCO LÂMPADAS DO JOGADOR NÃO EXISTEM NESTE CARTÃO — decisão dela, 28/08:
     elas saem dos desenhos pequenos e ficam só nos grandes, da Iluminação. Aqui
     o desenho tem 62px e cada lâmpada media 1,06 × 0,36 px; passar de 1px de  # noqa-acento  (`media` é o verbo medir)
     altura pediria ~340px de desenho, um cartão de ~460px, e os quatro somariam
     1840px numa fileira que tem 1163px.
     Quem diz o número do jogador aqui é o rótulo: `Sony • Player 1 • …`.
     NÃO HÁ REGRA DE COR PORQUE NÃO HÁ O QUE PINTAR: o grupo inteiro sai do SVG
     por `svg(lampadas=False)`. A volta anterior parou no meio — deixou as vinte
     no DOM pintadas de `--border-forte` e chamou isso de remédio. Marcação sem
     tinta foi o defeito da Perfis; desenho sem função é este, e a cura das duas
     é a mesma: as duas metades andam juntas. */

  /* ---------- A MÁSCARA, POR CONTROLE ----------
     Decisão dela, 28/08/2026: a máscara vira por controle, na aba Jogar, com
     TRÊS opções e **sem "Automático"** — DualSense · Xbox 360 · Nintendo Pro.
     Era um seletor único no quadro de cima, e ele saiu de lá.

     POR QUE EM COLUNA, e não na fileira que o `.seg` usa em toda a janela: o
     cartão mede 208px, e só "Nintendo Pro" pede ~104px — três lado a lado
     precisariam de ~326px. A alternativa média era pôr dois cartões por fileira
     (423px cada), e o preço disso é desfazer "os quatro numa fileira só", que é
     o que deixa a mesa inteira num relance.

     O botão é `--panel` sobre o cartão `--app-bg` — o inverso do `.seg`, que é
     `--app-bg` sobre o quadro `--panel`. Nos dois casos o que se clica é o tom
     que se destaca do fundo em que está. */
  /* AS TRÊS MÁSCARAS EM 2+1 — 30/08/2026, e é PAGAMENTO DE ALTURA, não estética.
     Deitar a Atenção (acima) fez o quadro crescer 69px, e o miolo tinha 6px de
     folga: nasceu barra de rolagem por dentro, com o "Reconectar Controles" fora
     da tela. Ela autorizou o ajuste com uma condição — *"desde que não percamos
     as features"* —, então nenhuma máscara sai: elas mudam de arranjo.

     O QUE MUDOU DESDE O COMENTÁRIO ACIMA: ele diz que três lado a lado pediriam
     ~326px e o cartão tinha 208. Com a Atenção fora da fileira o cartão passou a
     272,8px, e dois por linha ficam com 126,4px cada — cabem. O "Nintendo Pro",
     que é o mais largo, vai sozinho na linha de baixo com 256,8px.
     TESTADA E REPROVADA a variante com os três numa fileira só: o "Nintendo Pro"
     quebra em duas linhas e o chip vai de 28 para 44px. */
  .mascara{display:grid;grid-template-columns:1fr 1fr;gap:4px}
  /* O DUALSENSE OCUPA A LINHA INTEIRA, e os outros dois dividem a de baixo.
     Era o contrário, e ela viu na hora: *"o DualSense é o foco do app e o
     Nintendo Pro tá roubando a cena"*. Estava certa — na primeira versão do 2+1
     eu pus o terceiro chip esticado só porque "Nintendo Pro" é o rótulo mais
     largo, e com isso dei ao menos importante o maior pedaço da tela.
     Cabe: "Xbox 360" e "Nintendo Pro" medem 47 e 74px de texto, e cada metade
     tem 126,4 — o mais largo sobra 52. */
  .mascara .chip:nth-child(1){grid-column:1/-1}
  /* É O CHIP, e não o botão de 36px — e a escolha tem preço medido dos dois lados.
     Com `.seg button` (o `--h-escolha` de 36px) as três máscaras somam 116px por
     cartão, o miolo pede 560px e a janela oferece 542: o quadro "Conectado agora"
     passava a rolar POR DENTRO, com 18px do "Reconectar Controles" fora da tela.
     O chip tem 28px, e a mesma conta fecha em 502 — 40px de folga.
     E ele não é uma altura NOVA nesta janela: o chip da fita, três linhas acima,
     JÁ é o seletor por controle desta casa, na mesma altura e com o mesmo
     `.on`. O que muda aqui é só a direção — a fita deita, o cartão empilha. */
  .mascara .chip{
    display:flex;align-items:center;justify-content:center;
    cursor:pointer;background:var(--panel);
  }
  .mascara .chip:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}

  /* O CARTÃO DO ALVO DA FITA. A fita desta aba está VIVA, e até 28/08 ela
     apontava para lugar nenhum — a legenda declarava a contradição em aberto.
     Com a máscara por controle ela tem alvo de verdade, e o cartão dele leva o
     MESMO realce do chip escolhido, para os dois lerem como a mesma escolha. */
  .cartao.alvo{background:var(--sel-bg)}

  /* ---------- O LUGAR VAZIO ----------
     Decisão dela, 31/08/2026: *"deixa os outros dois controles desconectados,
     só coloca algo como `-` nos campos que deveriam ter algo e escurece tudo."*

     NADA DE `opacity`, e a razão é medida — é a lição da `.fita.inerte`
     (`topo.html`, 30/08): `opacity` esconde o texto DUAS vezes ao mesmo tempo
     (o alfa some com o contraste E com o peso do traço), e o resultado deixa de
     comunicar o que ela desenhou. Aqui cada cor é explícita.

     O QUE O ESCURO TIRA, e é de propósito: a borda perde a cor do plástico, o
     rótulo cai para `--comment` e a bateria perde o verde. Isso NÃO fere a regra
     de "nunca toque na cor do plástico" — aquela regra protege a informação de
     QUAL controle é qual, e num lugar vazio não há controle a identificar. A cor
     continua dentro do SVG, intacta, para o dia em que ele conectar. */
  .cartao.off{border-color:var(--border-sutil);background:transparent}
  /* A COR É `--linha`, E NÃO `--comment`, e a escolha é medida. Sobre o
     `--app-bg` (#21222c) o `--comment` dá **5,42:1** contra os **5,98:1** do
     rótulo conectado — 9% de diferença, que a olho nenhum lê como "apagado".
     A primeira volta usou `--comment` (a cor da `.fita.inerte`) e a foto
     desmentiu: o lugar vazio saiu MAIS aceso que o controle na mesa, porque o
     `--comment` é mais SATURADO. `--linha` dá **2,23:1** — e aqui isso é certo,
     não descuido: o que está escrito é um travessão, um marcador de ausência.
     Não há texto a ler num lugar onde não há controle. */
  .cartao.off .rotulo,
  .cartao.off .bat{color:var(--linha)}
  /* O DESENHO CINZA PRECISA DE `!important` porque a cor da peça é `style=`
     INLINE dentro do SVG (o gerador de cores a escreve lá, para o arquivo abrir
     colorido sozinho). Regra externa não vence atributo inline sem isto — e o
     hex certo continua no arquivo, então `check_cores_do_dualsense.py` segue
     verde: o que muda é a pintura, não o dado. */
  /* `.corpo` ENTRA JUNTO, e foi a foto que o achou. A primeira volta escreveu
     só `.peca` e `.miolo`: o P3 continuou ROXO e o P4 BRANCO na ampliação. O
     chassi — a peça grande que carrega a cor do plástico — é `path.corpo`, uma
     classe que nenhuma régua desta aba nomeava. Medido no DOM:
     `path.corpo fill=rgb(116,88,142)`, o Galactic Purple inteiro. */
  .cartao.off .ds-svg .peca,
  .cartao.off .ds-svg .corpo,
  .cartao.off .ds-svg .miolo *{fill:var(--linha) !important}
  .cartao.off .ds-svg .corpo{stroke:var(--border-forte) !important}
  /* Os chips do lugar vazio não se clicam: não há controle para receber a
     máscara. Sem `on` em nenhum, e sem `:hover`. */
  .cartao.off .mascara .chip{border-color:var(--border-sutil);color:var(--linha);
                             background:transparent;cursor:default}
  .cartao.off .mascara .chip:hover{border-color:var(--border-sutil);color:var(--linha)}

  /* O CABEÇALHO DAS DUAS COLUNAS TEM UMA ALTURA SÓ. O da esquerda ganhou o
     ícone de ajuda (17px) e o da direita é só texto (14,4px): sem isto a
     fileira de cartões e a lista de avisos começariam 2,6px fora de registro.
     A cura é na ALTURA, e quem manda é o mais alto. */
  .cab-col{display:flex;align-items:center;height:17px;margin-bottom:7px}

  /* A MESA FICA COM A SOBRA. Eram `1fr 1fr`: metade para dois cartões, metade
     para um aviso de uma linha. Com quatro cartões a metade não cabe, e o
     aviso não precisa dela — a coluna de avisos vale o que o texto pede.
     A LARGURA TEM UM DONO SÓ, e é este `--col-avisos`: ela decide duas coisas
     — onde a mesa acaba e onde o botão da faixa de baixo começa —, e as duas
     têm de bater, senão a barra vertical da coluna de avisos desce e erra a
     borda do botão por 85px, que é o que aconteceu quando eram dois números. */
  .quadro-corpo{--col-avisos:245px}
  /* A `.dupla` SAIU DAQUI — 30/08/2026. Com a Atenção deitando (abaixo), a grade
     de duas colunas ficou sem segunda coluna. A regra do `topo.html` volta a ser
     a única — que é o que ela já era antes desta aba a redefinir. */

  /* A FAIXA FINAL VOLTOU AO `flex` DO `topo.html` — 30/08/2026, e são DOIS
     pedidos dela numa cura só: *"o reconectar controles vai pra direita enquanto
     o 'Vai mudar para Conexão Nativa (Sony)…' extendo pra chegar ao reconectar
     controles"*.

     A grade de duas colunas que vivia aqui existia para casar a borda do botão
     com a barra vertical da coluna de avisos. Essa barra deixou de existir (a
     Atenção deitou), e com ela o motivo. O `topo.html` já tem exatamente o que
     ela quer, e estava morto sob esta redefinição:
         .faixa-final{display:flex;align-items:center;gap:12px}
         .faixa-final .pendente{flex:1}
     O `flex:1` da barra tracejada é o "estende"; a ausência de segunda coluna é
     o "vai pra direita" — o botão passa a terminar no `right` do quadro, no
     mesmo x em que terminam a fileira de cartões e a fileira de modos.
     Medido: a barra vai de 853 para 940px e o botão de x=1271..1431 para
     x=1356..1516. */
  .faixa-final{border-top:1px solid var(--rot-linha);padding-top:6px;margin-top:8px}
  /* A ATENÇÃO DESCEU — 30/08/2026, pedido dela: *"esse atenção desce"*.
     Ela era a segunda coluna da `.dupla`, ao lado dos cartões, com a barra
     vertical à esquerda. Media 129px de VAZIO — 70% da própria coluna —, porque  # noqa-acento  (`media` é o verbo medir)
     a altura dela vinha do irmão (`align-self:stretch`) e o conteúdo era um
     aviso de uma linha.

     Deitada, ela é uma faixa de largura inteira entre os cartões e a faixa
     final, e a divisória troca de eixo: a barra vertical vira linha horizontal,
     que é a mesma gramática das outras nove abas.
     O RESERVADO DO P8 continua existindo — ele agora é o espaço que a faixa
     ganha ao receber o segundo aviso, e cresce para baixo em vez de ficar
     esperando em branco. */
  /* OS RESPIROS SÃO 8/6 E NÃO 12/10, e o motivo é o orçamento: com 12/10 o miolo
     pedia 556 de 542 e nascia barra de rolagem por dentro. Aqui cada pixel é
     disputado — ver o comentário do `--alt-janela` no `topo.html`. */
  .col-atencao{border-top:1px solid var(--rot-linha);margin-top:8px;padding-top:6px;
               display:flex;align-items:center;gap:12px}
  .col-atencao .cab-col{margin-bottom:0;flex:0 0 auto}
  .col-atencao .aviso-item{flex:1;min-width:0}
  .col-atencao .conta-avisos{margin-left:auto;flex:0 0 auto}
"""


# ---------------------------------------------------------------------------
# OS CARTÕES — um por controle da MESA
# ---------------------------------------------------------------------------
#: O GLIFO DA BATERIA VAI SEM `<title>`, e a linha existe para não desfazer
#: calado o que ela pediu. O `monta.glifo()` põe o nome da peça no `<title>` de
#: propósito (é como um SVG diz o nome dele, e foi a cura do `title="cross"` que
#: a Controles mostrava 64 vezes). Aqui ele sai, porque este glifo está DENTRO
#: da frase `100%` — o rótulo já diz o que é, e o tooltip repetiria "Bateria" em
#: cima de um número que se lê sozinho. Medido: nenhuma das dez páginas tem
#: `<title>Bateria</title>` hoje. **É decisão dela reverter**, não minha: pôr o
#: `<title>` de volta é apagar `.replace(...)` desta linha.
_BATERIA_GLIFO = glifo("bateria", tam=13).replace("<title>Bateria</title>", "")


def _desenho(c):
    """O desenho de um controle da MESA, pronto para o cartão.

    **O PRÓLOGO XML SAI.** `svg()` devolve o arquivo inteiro, e ele começa com
    `<?xml ...?>`; empilhado a cada volta ele dava quinze prólogos por cartão na
    versão à mão, e o navegador os engolia calado.

    **E O CARTÃO NÃO TEM AS CINCO LÂMPADAS DO JOGADOR** — decisão dela, 28/08,
    com o número no CSS acima.
    """
    return re.sub(r"<\?xml[^>]*\?>\s*", "",
                  svg(f'jg-{c["pref"]}', c["cor"], lampadas=False))


#: O MARCADOR DE CAMPO VAZIO, num lugar só. É o travessão, não o hífen: ela
#: escreveu *"algo como `-`"*, e o travessão é o que esta janela já usa para
#: "não há valor" (a tabela de bateria da própria aba escreve `— `).
_VAZIO = "—"


def cartao(c, bateria=None):
    """Um cartão da fileira: desenho na cor do plástico, rótulo e as máscaras.

    `bateria` é o único argumento, e existe porque a carga é o **único dado
    inventado** desta aba (a legenda o declara desde 26/08): no mockup ela vem
    da tabela `BATERIA`, e na aba viva vem do `state_full`. Sem este argumento
    a mesa viva de cinco controles levantaria `KeyError` no `p5` — no meio da
    remontagem, com a tela dela na frente.


    A MÁSCARA NÃO É DIGITADA. Ela sai de `monta.MESA[...]["mascara"]`, que é a
    mesma fonte que a Controles e a Conexões leem — e foi a divergência que a
    versão à mão criou: a 01 mostrava `P2 = DualSense` e `P3 = Xbox 360` contra
    o `P2 = Xbox 360` / `P3 = DualSense` da MESA, porque a fonte única existia e
    a tela de referência ficava de fora dela.

    OS ENDEREÇOS (29/08/2026, e o vocabulário é o do `aba02.py:484`)
    ----------------------------------------------------------------
    `data-controle` é o `uniq` do aparelho quando há um (a mesa viva) e o `pref`
    quando não há (o mockup, cuja mesa é escrita à mão) — a MESMA linha do
    `aba02.py:769`, e não uma segunda regra.

    **Os três `data-campo` do rótulo existem porque o rótulo TEM FILHOS.**
    Escrever `textContent` num elemento com filho apaga os filhos e força
    layout: era a armadilha medida do piloto da Controles. Cada valor que muda
    de segundo a segundo ganha aqui a sua própria FOLHA, e a folha é um `<span>`
    inline sem estilo — que é o que permite endereçar sem mover um pixel, que é
    a promessa desta mudança.
    """
    # O LUGAR VAZIO — decisão dela, 31/08/2026: *"Vamos deixar os outros dois
    # controles desconectados, só colocamos algo como `-` nos campos que deveriam
    # ter algo e escurecemos tudo."*
    #
    # O CARTÃO CONTINUA NA TELA, e é isso que ela comprou: um controle que SOME
    # não ensina nada — quem olha não sabe se a aba tem dois lugares ou quatro. O
    # lugar apagado ensina que ali cabe um e que ele não está.
    #
    # NENHUMA MÁSCARA FICA `on`: máscara é escolha por controle, e sem controle
    # não há escolha. Marcar uma seria desenhar um ajuste que não existe.
    if not c.get("conectado", True):
        chips = "\n".join(
            f'                  <span class="chip" data-mascara="{m}">{m}</span>'
            for m in MASCARAS)
        return f'''              <div class="cartao off"
                   data-controle="{c["pref"]}" data-conectado="nao"
                   title="Lugar vazio: nenhum controle conectado aqui.">
                <div class="peca-topo">
                {_desenho(c)}
                <span class="rotulo">{_VAZIO}<br>{_VAZIO}<br><span class="bat">{_BATERIA_GLIFO} <span>{_VAZIO}</span></span></span>
                </div>
                <div class="mascara">
{chips}
                </div>
              </div>'''

    chips = "\n".join(
        f'                  <span class="chip{" on" if m == c["mascara"] else ""}"'
        f' data-mascara="{m}">{m}</span>'
        for m in MASCARAS)
    return f'''              <div class="cartao{" alvo" if c["alvo"] else ""}" style="--plastico:{monta.cor_da_zona(c["cor"])}"
                   data-controle="{c.get("uniq") or c["pref"]}" data-conectado="sim"
                   title="{rotulo(c, "completa").replace('<span class="pt">•</span>', '•')}">
                <div class="peca-topo">
                {_desenho(c)}
                <span class="rotulo">Sony <span class="pt">•</span> <b data-campo="jogador">Player {c["jogador"]}</b><br><span data-campo="identidade">{c["nome"]} <span class="pt">•</span> {c["via"]}</span><br><span class="bat">{_BATERIA_GLIFO} <span data-campo="bateria">{bateria if bateria is not None else BATERIA.get(c["pref"], "— ")}%</span></span></span>
                </div>
                <div class="mascara">
{chips}
                </div>
              </div>'''


def frase_das_mascaras():
    """"P1 e P3 em DualSense, o P2 em Xbox 360 e o P4 em Nintendo Pro" — da MESA.

    A frase estava digitada na legenda e repetia o erro dos chips. Escrita aqui,
    ela não tem como discordar deles.
    """
    partes = []
    for m in MASCARAS:
        # SÓ OS CONECTADOS — 31/08/2026. Um lugar vazio não tem máscara
        # escolhida (o cartão dele não marca nenhuma), e listá-lo aqui faria a
        # legenda prometer um ajuste que a tela não mostra.
        ps = [f'P{c["jogador"]}' for c in monta.CONECTADOS if c["mascara"] == m]
        if not ps:
            continue
        quem = " e ".join([", ".join(ps[:-1]), ps[-1]] if len(ps) > 2 else ps)
        partes.append(f"{quem} em {m}" if len(ps) > 1 else f"o {quem} em {m}")
    return ", ".join(partes[:-1]) + " e " + partes[-1]


CARTOES = "\n".join(cartao(c) for c in MESA)

# AS DUAS POSIÇÕES DO INTERRUPTOR. O `for=` do `<label>` é o que muda o rádio no
# mockup; o `data-modo` é o endereço da pintura viva. São dois mecanismos com
# alvos diferentes no MESMO elemento, de propósito — a alternativa era a tela
# ter um estado no desenho e outro no daemon, que é o defeito que a pintura
# existe para não ter.
_INTERRUPTOR = "\n".join(
    f'        <label class="hef-pos {lado}" for="hef-{lado}" data-modo="{modo}"\n'
    f'               title="{dica}"><span class="pino"></span>{rot}</label>'
    for lado, modo, rot, dica in INTERRUPTOR)

# A CLASSE `auto` NÃO É MAIS ESCRITA (31/08): ela existia só para o algarismo "A"
# do "Automático" ganhar o ciano (`.degrau.auto i`, no `topo.html`). A regra órfã
# continua no esqueleto — ela é de lá, e tirá-la é mexer em arquivo de outro dono.


def _chip_do_modo(m):
    """Um dos cinco chips de dentro do Hefesto ligado.

    TRÊS ENDEREÇOS, e cada um responde a uma pergunta diferente:

    - ``data-degrau`` — a identidade na fileira que o PS+R3 gira. Todos têm;
    - ``data-modo`` — só quem É um modo de ``mode_transition.MODES``. Hoje é a
      **Navegação** e só ela (``desktop``): é ela que `apply_mode` sabe aplicar.
      Escrever este endereço nos outros quatro seria oferecer um escritor que
      não existe;
    - ``title`` — o que este modo é, em uma linha, e se ele tem quem o atenda.
    """
    classe = ("degrau"
              + (" on" if m["chave"] == MODO_ACESO else "")
              + (" sem-dono" if m["sem_dono"] else ""))
    modo = f' data-modo="{m["modo"]}"' if m["modo"] else ""
    # SEM `<i>`: os algarismos saíram em 31/08 (ver o comentário do `MODOS`).
    return (f'            <span class="{classe}" data-degrau="{m["chave"]}"{modo}\n'
            f'                  title="{m["dica"]}">{m["rot"]}</span>')


_MODOS = "\n".join(_chip_do_modo(m) for m in MODOS)


def aviso(selo, texto):
    """Uma linha da coluna Atenção.

    Ela vira FUNÇÃO em 29/08/2026 porque a coluna viva monta de zero a N: no
    mockup a cena tem um aviso, e na máquina dela o número muda a cada tique.
    O piloto chama esta mesma função, e por isso não há um segundo HTML de
    aviso escrito à mão em lugar nenhum.
    """
    return f'''            <div class="aviso-item" data-aviso>
              <span class="selo alerta" data-campo="aviso-selo">{selo}</span>
              <span data-campo="aviso-texto">{texto}</span>
            </div>'''


_AVISOS = "\n".join(aviso(selo, texto) for selo, texto in AVISOS)
_CONTA = f"{len(AVISOS)} aviso" + ("s" if len(AVISOS) != 1 else "")


MIOLO = f'''
    <!-- ---------- O INTERRUPTOR DO HEFESTO — FORA DE TUDO ----------
         DOIS NÍVEIS desde 31/08/2026 (manhã), decisão dela: em cima o
         interruptor do Hefesto, e o que ele abre embaixo. A pergunta que o
         motivou é dela — *"qual a diferença de nativo pra dualsense?"* — e a
         resposta é estrutural: Nativo é o Hefesto FORA do meio, e os outros são
         jeitos de ele estar no meio. Numa fileira só, os dois liam como irmãos.

         E ELE SUBIU PARA FORA DO QUADRO na mesma tarde, decisão dela ao ver a
         foto: dentro de "Quando o jogo abrir" o interruptor lia como *"ligar o
         Hefesto quando um jogo abrir"*, e não é isso — ligado ou desligado vale
         SEMPRE. O quadro fica com o que É decidido no lançamento: o modo.

         A GRAMÁTICA É A DA FITA do `topo.html` ("Ajustes vão para: [Todos]
         [P1…]"): rótulo deitado, a fileira do que se escolhe, sem moldura, acima
         do que ela governa. -->
    <div class="hef-topo">

      <!-- OS DOIS RÁDIOS VÊM PRIMEIRO porque o `~` de dentro desta caixa (o que
           acende a posição escolhida) só enxerga irmão POSTERIOR. Quem alcança
           as duas seções lá dentro do quadro é o `:has()` — ver o CSS. -->
      <input type="radio" name="hefesto" id="hef-ligado" class="hef-rd"{" checked" if HEFESTO_LIGADO else ""}>
      <input type="radio" name="hefesto" id="hef-desligado" class="hef-rd"{"" if HEFESTO_LIGADO else " checked"}>

      <div class="hef-linha">
        <span class="linha-rot">Status</span>
{_INTERRUPTOR}
        <span class="ajuda">?<span class="dica">
          <b>Ligado</b> — o Hefesto fica no meio: luz, vibração, gatilho e o número do jogador são por conta dele.<br><br>
          <b>Desligado</b> — o Hefesto sai do meio e o jogo fala direto com o controle.<br><br>
          Isto não encerra o serviço. Para isso, a aba <b>Sistema</b>.
        </span></span>
      </div>
    </div>

    <!-- ---------- QUANDO O JOGO ABRIR ----------
         O que sobra aqui é o que o lançamento decide de verdade. -->
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Modo</span>
        <!-- O `?` DOS MODOS SUBIU do rótulo "Modo" para cá em 31/08 à tarde, e é
             consequência do interruptor ter saído: com só os modos dentro, a
             ajuda do quadro É a ajuda dos modos, e dois `?` a três linhas um do
             outro diriam a mesma coisa duas vezes. De quebra, os rótulos das
             duas seções ficaram idênticos — texto puro dos dois lados. -->
        <span class="ajuda">?<span class="dica">
          Vale <b>quando o jogo abrir</b>. O que muda entre os quatro é <b>como o jogo desenha os botões</b> — luz, vibração, gatilho, giroscópio e áudio são por conta do Hefesto em todos.<br><br>
          Ele <b>tenta na ordem em que estão aqui e para quando acerta</b>; depois não pergunta mais para aquele jogo.<br><br>
          <b>Segurando PS + R3</b> você pula para o próximo sem largar o controle.
        </span></span>
      </div>
      <div class="quadro-corpo hef">

        <!-- O SELETOR DE MÁSCARA SAIU DAQUI em 28/08. Decisão dela: a máscara é
             POR CONTROLE, e o seletor mora dentro do cartão de cada um, no quadro
             "Conectado agora". O que fica aqui é o que é da MÁQUINA INTEIRA: o
             modo é estado do processo — existe um só (`app/actions/mode_transition.py`),
             e por isso ele não podia descer para o cartão junto com a máscara. -->

        <div class="hef-modo so-ligado" title="Esta seção só aparece com o Hefesto LIGADO.">
          <div class="escada">
{_MODOS}
          </div>
        </div>

        <!-- O OUTRO LADO DO INTERRUPTOR. Mesma altura da seção de cima (rótulo +
             36px), para a tela não pular quando ela vai e volta. -->
        <div class="hef-modo so-desligado" title="Esta seção só aparece com o Hefesto DESLIGADO.">
          <div class="escada">
            <span class="degrau on fixo"
                  title="O Hefesto sai do meio e o jogo fala direto com o controle. Vale no próximo jogo que abrir.">Modo Nativo <span class="sep">·</span> <span class="mud">o DualSense da forma como veio ao mundo</span></span>
          </div>
        </div>

      </div>
    </div>

    <!-- ---------- UM BLOCO SÓ: Conectado agora | Atenção ---------- -->
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">O Controle é visto como:</span>
        <!-- AS DUAS DICAS VIRARAM UMA — 31/08/2026, quando ela mandou o rótulo
             "O jogo vê cada controle como:" subir para o título. Com o rótulo
             fora, dois `?` a três linhas um do outro diriam a mesma coisa duas
             vezes: é o mesmo movimento que o `?` dos modos já tinha feito. -->
        <span class="ajuda">?<span class="dica">
          A máscara é <b>por controle</b>: cada um pode aparecer de um jeito para o jogo, e o que muda é <b>o desenho dos botões na tela</b>.<br><br>
          <b>DualSense</b> — △ ○ ✕ ▢. &nbsp; <b>Xbox 360</b> — Y B A X. &nbsp; <b>Nintendo Pro</b> — X A B Y, com ZL/ZR e − +.<br><br>
          O controle na sua mão continua o mesmo: luz, gatilho, giroscópio e áudio seguem por conta do Hefesto em qualquer máscara.<br><br>
          Clicar num cartão leva a fita de cima para ele. O detalhe de cada um está na aba <b>Controles</b>.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <div>
            <div class="pecas" data-lista="cartoes">
{CARTOES}
            </div>
          </div>

        <div class="col-atencao" data-lista="avisos">
          <div class="linha-rot cab-col">
            <b style="color:var(--orange)">Atenção</b>
          </div>
{_AVISOS}
          <span class="conta-avisos" data-campo="atencao-conta">{_CONTA}</span>
        </div>

        <div class="faixa-final">
          <!-- MAIÚSCULA NO COMEÇO — 28/08/2026. A frase é uma linha inteira,
               isolada na caixa tracejada, e o `●` que vem antes é MARCADOR, não
               palavra: a frase começa aqui. Era o mesmo defeito que ela apontou
               na Conexões ("• o rádio de cada adaptador, em fatias") e mandou
               procurar em todas as abas. O "quando você clicar em" continua
               minúsculo porque é meio da MESMA frase. -->
          <div class="pendente" data-campo="pendente">
            <span>●</span>
            <span>Vai mudar para <b data-campo="pendente-alvo">{PENDENTE}</b> quando você clicar em <b>Aplicar</b></span>
          </div>
          <button class="btn" data-gesto="reconectar">Reconectar Controles</button>
        </div>

      </div>
    </div>
'''


#: A LEGENDA. A frase das máscaras NÃO É DIGITADA — ela sai da `MESA`, pela
#: `frase_das_mascaras()`. Era escrita à mão aqui e repetia o erro dos chips:
#: quando a MESA passou a mandar na máscara de cada cartão, a legenda ficou
#: dizendo o contrário do que a tela mostrava.
LEGENDA = f'''<div class="nota">
  <h2>O que mudou, e por quê</h2>
  <ul>
    <li><b>A fileira plana virou DOIS NÍVEIS</b> — sua palavra, 31/08:
      <span class="marca">"vamos desconfundir isso que tal? Hefesto Ligado/Desligado (…) Modo
      Hefesto se Ligado Abre as seções de Modo"</span>. A pergunta que abriu isto também é sua
      — <span class="marca">"qual a diferença de nativo pra dualsense?"</span> —, e ela era
      boa: a tela punha os dois na <b>mesma</b> fileira, como alternativas do mesmo tipo. Não
      são. <b>Nativo é o Hefesto FORA do meio</b>; os outros são jeitos de ele <b>estar</b> no
      meio. Agora a tela mostra isso: em cima o interruptor, embaixo o que ele abre.</li>
    <li><b>E o interruptor SUBIU para fora do quadro</b> — sua decisão da tarde de 31/08,
      olhando a foto: ele tinha nascido <b>dentro</b> de "Quando o jogo abrir", e um quadro é um
      <b>escopo</b>. Ali ele lia como <i>"ligar o Hefesto quando um jogo abrir"</i>, e não é isso:
      <b>ligado ou desligado vale sempre</b>, com jogo aberto ou sem nenhum. O que o lançamento
      decide de verdade é o <b>modo</b>, e é só ele que fica no quadro.
      <br>A gramática é a da <b>fita</b> do topo da janela (<span class="marca">"Ajustes vão para:
      [Todos] [P1 · Cosmic Red · USB]…"</span>): rótulo deitado, a fileira do que se escolhe, sem
      moldura, acima do que ela governa. O "Hefesto" nasce no <b>mesmo x</b> de "Quando o jogo
      abrir" e "Conectado agora" — os três títulos da aba numa coluna só.
      <br><b>E ela DEVOLVEU altura em vez de custar</b>, que era o risco: o quadro perdeu a linha
      do interruptor e a divisória que a separava dos modos (63px), e o que subiu custa 50 (a
      fileira de 36 mais o passo de 14 do miolo). Saldo <b>−13px</b>: o miolo pedia <b>514</b> de
      542 e passou a pedir <b>501</b>; a folga foi de <b>28</b> para <b>41px</b>, nas duas
      posições do interruptor.</li>
    <li><b>"Desligado" deixou de ser um estado inventado, e isso fecha a MIGRA-JOGAR-06</b> —
      sem construir nada. O quarto botão da fileira antiga não tinha leitor:
      <code>mode_transition.mode_of_state</code> é o ponto único de leitura do modo vivo e
      devolve <b>três</b> valores, nunca um quarto. Com a sua decisão, <b>Desligado = Modo
      Nativo</b> (<code>MODE_NATIVE</code>), que <b>lê</b> (o mesmo <code>mode_of_state</code>)
      e <b>escreve</b> (<code>apply_mode('native')</code>, em <code>painel.ESCRITOR_DOS_MODOS</code>).
      Parar o Hefesto inteiro continua sendo <b>"Parar o serviço"</b>, na Sistema — e o verbo
      é escolha dela de 31/08: <i>parar</i> é o que o <code>systemctl stop</code> faz e é o par
      de <i>Ligado</i>; <i>encerrar</i> sugeria fim definitivo, e o serviço volta no próximo
      login.</li>
    <li><b>O chip que se chamava "Hefesto" virou "Sony DualSense"</b> — ele sempre foi
      <code>Ponte(gamepad, dualsense)</code>, o primeiro degrau de
      <code>integrations/ponte_escada.ESCADA</code>. Era o nome do <b>produto</b> no lugar do
      nome da <b>máscara</b>, numa fileira em que os outros também são o Hefesto.</li>
    <li><b>O Xbox chegou à tela pela primeira vez</b> — <code>Ponte(gamepad, xbox)</code> é o
      <b>segundo</b> degrau que o produto tenta, e nenhum chip o nomeava. Era exatamente o que
      <code>painel.degraus_sem_chip()</code> denunciava: <span class="marca">"um degrau real não
      tem chip na tela"</span>. Agora tem.</li>
    <li><b>Os algarismos saíram, e é decisão dela de 31/08</b> — a tela escrevia
      <b>③ Steam Input</b>, o produto o tenta em <b>quarto</b>
      (<code>ponte_escada.indice_do_degrau + 1</code> = 4) e esta legenda prometia que o número
      ERA esse índice. Os três não podiam estar certos, e a causa é a própria decisão dela do
      mesmo dia: o terceiro degrau é o <b>Nativo</b>, que saiu da fileira para virar o
      interruptor <b>Desligado</b>. Havia três saídas — numerar <i>1 · 2 · 4</i> com o buraco do
      3, numerar pela posição na tela (e esta linha passar a mentir), ou tirar os números. Ela
      tirou. <b>A ordem não se perdeu</b>: está na dica de cada modo e na do quadro
      <b>Quando o jogo abrir</b>.</li>
    <li><b>A máscara virou POR CONTROLE</b> — decisão sua, 28/08. Três opções e
      <b>sem "Automático"</b>: DualSense · Xbox 360 · Nintendo Pro. O seletor mora dentro
      do cartão de cada controle. O que era um seletor único lá em cima
      (<span class="marca">"O jogo vê o controle como:"</span>) saiu do quadro
      <b>Quando o jogo abrir</b> — e o rótulo veio junto, no plural.</li>
    <li><b>Nenhum aviso do que se perde</b> — não há "você perde giro", "perde touchpad"
      nem "perde microfone" em máscara nenhuma. A dica diz o que muda de verdade: a máscara
      muda <b>o que o jogo vê</b>, e por isso os botões que ele desenha. O controle na sua
      mão continua o mesmo — a luz, o gatilho e o giroscópio seguem por conta do Hefesto
      em qualquer máscara (<code>docs/usage/modos.md</code>). O microfone segue o
      <b>transporte</b>, não a máscara.</li>
    <li><b>"Automático" saiu da máscara</b> — substitui a <code>D-A-MASCARA-GANHA-O-AUTOMATICO</code>
      de 26/08, que o queria como terceira opção ligada. A heurística que o moveria
      (<code>api_de_entrada.py</code>) errou em <b>13 dos 14</b> jogos do seu censo.</li>
    <li><b>"Automático" saiu também do Modo de conexão</b> — sua palavra, 31/08:
      <span class="marca">"na aba jogar o Botão Automático não existe"</span>. E não existe
      mesmo: ele não tinha <b>leitor</b> (<code>painel.CHIPS_DA_ESCADA</code> o declara com
      <code>ponte=None</code>, e <code>degrau_vivo</code> só acende comparando pontes — nenhum
      estado do produto podia acendê-lo) nem <b>escritor</b> (não há método de IPC que fixe um
      degrau). <b>O mecanismo ficou</b>: tentar na ordem e parar quando acerta é o que o produto
      já faz sozinho, e está dito na dica.</li>
    <li><b>A fita ficou viva, e agora ela tem alvo</b> — era a contradição que esta legenda
      declarava em aberto: a fita dizia <span class="marca">"vai para o controle escolhido
      aqui"</span> numa aba em que nada era por controle. A máscara resolveu isso. O cartão
      do alvo leva o <b>mesmo realce do chip escolhido</b>, para os dois lerem como uma
      escolha só.</li>
    <li><b>O modo continua da máquina inteira</b>, e não desceu para o cartão junto com a
      máscara. Não é descuido: o modo é <b>estado do processo</b> — existe um só
      (<code>app/actions/mode_transition.py</code>), e duas peças pedindo modos diferentes
      não têm resposta. Máscara é do <b>aparelho</b>; modo é da <b>máquina</b>.</li>
    <li><b>Os DOIS que ainda não têm quem os atenda aparecem, e dizem isso</b> — é a sua ordem
      de 31/08 (manter <b>Point And Click</b> e <b>Navegação</b>) somada à regra que você fixou
      em 30/08 (<i>botão sem dono no produto não vai para a tela como se funcionasse</i>). Elas
      convivem de um jeito só: os dois entram <b>marcados</b>, e o porquê está no ponteiro do
      mouse. Nada de <code>opacity</code> — a lição da fita inerte é que a opacidade some com o
      texto e cega toda régua de contraste; aqui é <b>borda tracejada</b>, cor explícita e
      cursor de "não clique".
      <br><b>Point And Click</b> não é degrau da escada <b>nem</b> modo do produto: não tem nada.
      <br><b>Navegação</b> é o caso do meio, e é bom: o <b>modo</b> tem dono e funciona hoje
      (<code>apply_mode('desktop')</code>, o antigo "Controlar o PC"). O que ainda não existe é
      o <b>PS + R3</b> parar nela — a Navegação não é degrau. Por isso ela leva traço no
      dica que diz o que falta, mas <b>não</b> a borda tracejada.</li>
    <li><b>Quatro controles na mesa, um cartão cada</b> — a lista é a <code>MESA</code> do <code>monta.py</code>: não há "quatro" escrito num laço, e o número do jogador é campo, não a posição na fila. Continua sendo só a peça, com o <b>SVG pequeno na cor do plástico</b> — o card completo é da aba Controles.</li>
    <li><b>A borda e a cor vêm do mapa</b> — a cor do plástico sai do <code>cores-do-dualsense.csv</code> pela folha que o gerador escreveu dentro do desenho. Não está digitada aqui.</li>
    <li><b>As cinco lâmpadas do jogador ficam apagadas neste cartão</b> — medido de novo hoje,
      no 1× da sua tela: cada lâmpada mede <b>1,06 × 0,36 px</b> no desenho de 62px, e acender
      as dez mudava <b>de 2 a 7 pixels de 2666</b> por cartão. Para se lerem, o cartão
      precisaria de ~460px — os quatro somariam 1840px numa fileira que tem 1163px. Quem diz
      o número aqui é o rótulo <b>Player N</b>; o padrão das luzes, desenhado grande, está na
      <b>Iluminação</b>.</li>
    <li><b>A caixa "Não trocar de perfil sozinho" saiu</b> — o perfil ativo já diz isso.</li>
    <li><b>"Reconciliar jogadores" virou "Reconectar Controles"</b>.</li>
    <li><b>A área de avisos tem espaço reservado</b> e <b>conta quantos são</b>. Antes, três banners disputavam a linha e o primeiro escondia os outros. A barra vertical que a separa dos cartões agora vai até embaixo — era um toco de um terço, porque a coluna media a altura do único aviso.</li>  <!-- noqa-acento: `media` é o verbo medir -->
    <li><b>32 frases viraram 12</b> — o resto está nos três ícones <b>?</b>. Passe o mouse neles.</li>
  </ul>

  <h2>O que eu decidi por conta, e você pode derrubar</h2>
  <ul>
    <li><b>As três máscaras são chip, e não o botão de 36px do resto da janela</b>, e o preço
      está medido dos dois lados. Com o botão, as três somam 116px por cartão: o miolo pede
      <b>560px</b> e a janela oferece <b>542</b> — o quadro "Conectado agora" passava a rolar
      por dentro, com 18px do <b>Reconectar Controles</b> fora da tela. Com o chip a conta
      fecha em <b>502</b>. E não é uma altura nova: o <b>chip da fita</b>, três linhas acima,
      já é o seletor por controle desta casa, na mesma altura e com o mesmo destaque — o que
      muda é a direção, a fita deita e o cartão empilha.</li>
    <li><b>Empilhadas, e não lado a lado</b> — o cartão tem 208px e só "Nintendo Pro" pede
      ~104px; três na horizontal precisariam de ~326px. A saída seria dois cartões por
      fileira (423px cada), e o preço disso é desfazer <b>os quatro numa fileira só</b>, que é
      o que deixa a mesa inteira num relance. Se você preferir a horizontal, é esse o troco.</li>
    <li><b>As máscaras que aparecem escolhidas</b> — {frase_das_mascaras()}. É para você <b>ver</b> que a escolha é por controle; a sua mesa hoje
      é DualSense nos quatro.</li>
    <li><b>Clicar num cartão leva a fita para ele</b> — é a mesma gramática que você fixou hoje
      para o acordeão da Controles ("clicar num card muda a fita").</li>
    <li><b>A ordem dos cinco modos não é a ordem em que você os listou</b>, e é a única coisa
      em que me afastei do seu texto. Você escreveu <span class="marca">"Steam Input, Xbox, Sony
      DualSense, Point And Click"</span>; eu pus <b>Sony DualSense · Xbox · Steam Input</b>,
      que é a ordem <b>medida</b> em que o produto tenta
      (<code>ponte_escada.ESCADA</code>): a DualSense primeiro porque <b>dez</b> linhas do
      <code>mapa-controles.csv</code> só chegam ao jogo por ela, e o Steam Input por último
      porque é o único que exige <b>fechar a Steam, reabrir a Steam e reabrir o jogo</b>. Sem os
      algarismos, <b>a ordem da fileira é a única coisa que ainda diz o que o produto tenta
      primeiro</b> — trocá-la para a sua ordem passaria a afirmar que o Hefesto começa pelo Steam
      Input, e isso é falso e caro. <b>Se você preferir a sua ordem mesmo assim</b>, é uma linha
      no <code>MODOS</code>; mas então a dica de cada modo tem de deixar de dizer "é o primeiro
      que o Hefesto tenta", ou a tela volta a se contradizer.</li>
    <li><b>O rótulo "Hefesto" ficou DEITADO, ao lado do interruptor</b>, e não em cima como as
      outras linhas desta casa. Nasceu como pagamento de altura — o miolo tinha <b>2px</b> de
      folga em 542 antes do redesenho da manhã, e um rótulo por cima custa 22px. Esse aperto
      passou (a subida devolveu 13px, e a folga hoje é de 41), mas ele <b>continua deitado</b>
      porque é a forma que você desenhou (<span class="marca">"Hefesto Ligado/Desligado"</span>,
      tudo numa linha) — e porque é a da fita do topo da janela, que é o lugar de onde ele
      agora fala.</li>
    <li><b>O "?" dos modos subiu do rótulo "Modo" para o topo do quadro</b> — é consequência de
      o interruptor ter saído: com só os cinco modos dentro, a ajuda do quadro <b>é</b> a ajuda
      dos modos, e dois "?" a três linhas um do outro diriam a mesma coisa duas vezes. Nada de
      texto se perdeu — ele está inteiro no "?" do <b>Quando o jogo abrir</b>. De quebra os
      rótulos das duas posições ficaram idênticos (texto puro dos dois lados), que é o que já
      tinha custado <b>180 contra 176</b> quando divergiram.</li>
    <li><b>O nome da seção é "Modo", e não "Modo de conexão"</b> — é a sua palavra
      (<span class="marca">"Abre as seções de Modo"</span>). O quadro continua se chamando
      <b>Quando o jogo abrir</b>, e o de baixo <b>Conectado agora</b>: os dois títulos são seus,
      de 26 e 28/08, e não os troquei sem você pedir.</li>
    <li><b>Continua sem uma linha de JavaScript, mas o combinador mudou</b> — e a troca foi
      forçada, não gosto. Com o interruptor fora do quadro, os dois <code>radio</code> deixaram
      de ser irmãos das seções que abrem, e o <code>~</code> só enxerga irmão posterior. A saída
      óbvia — pendurar os dois <code>input</code> direto no miolo — <b>reprovou numa régua real</b>:
      o <code>regua.py</code> exige que todo filho direto do miolo comece no x do miolo e tenha a
      largura inteira, e um <code>input</code> de 0×0 é filho direto com largura própria; a cura
      teria custado um erro na régua da aba que <b>é a referência das outras nove</b>. O que
      está lá é <code>:has()</code>, que não é mecanismo novo aqui: o esqueleto já abre e fecha
      as seções da <b>Conexões</b> com ele.</li>
    <li><b>A linha laranja tracejada</b> é a prova de que o Aplicar ainda deve. Ela só aparece com escolha pendente — e o espaço dela é reservado, para a tela não pular.</li>
    <li><b>A carga de cada bateria é o único dado inventado desta aba</b> — 100, 64, 41 e 87%. Bateria é estado do momento, e o mockup mostra um momento; todo o resto (cor, nome, transporte, jogador, desenho) sai de arquivo.</li>
    <li><b>O recibo do rodapé nomeia o perfil</b> — é onde a mudança vai cair, que era a informação que faltava e te custou semanas.</li>
  </ul>

  <h2>O que isto encomenda ao código</h2>
  <ul>
    <li><b>O interruptor tem de ler DOIS modos como "Ligado"</b>. Hoje a pintura viva acende um
      botão comparando <code>data-modo</code> com o modo do daemon, um a um — e o Hefesto ligado
      é <b>gamepad</b> <i>ou</i> <b>desktop</b> (Navegação). Sem uma leitura derivada
      (<code>ligado = modo in {{gamepad, desktop}}</code>) o interruptor fica apagado dos dois
      lados quando você escolhe a Navegação: a tela não estaria mentindo, estaria muda — e mudo
      é pior, porque parece defeito.</li>
    <li><b>Fixar um modo pela tela ainda não existe</b>, e vale para os três degraus reais:
      <span class="marca">"a escada existe e SOBE sozinha, mas ninguém a fixa pela tela: não há
      método de IPC que diga 'use este degrau'"</span>. Clicar em <b>Sony DualSense</b>, <b>Xbox</b>
      ou <b>Steam Input</b> hoje não muda nada no daemon — quem muda é o <b>PS + R3</b> na sua
      mão. Os dois que faltam (Point And Click e Navegação como degrau) são mais um passo além
      disso.</li>
    <li><b>A máscara Nintendo Pro não existe hoje</b>, e entra assim mesmo — isto é mockup, e
      mockup desenha o produto que vai existir. O catálogo do produto
      (<code>integrations/uinput_gamepad.py</code>, <code>FLAVORS</code>) tem <b>duas</b>
      entradas: <code>dualsense</code> e <code>xbox</code>. A terceira nasce como
      <b>MÁSCARA-NINTENDO-01</b>, com um invariante duro: o PID <b>não</b> pode ser o
      <code>0x2009</code> do Pro físico (VPAD-04 — vpad e aparelho real com o mesmo VID/PID
      somem juntos da Steam, e o jogo fica com zero controles). Boa parte já está pronta:
      <code>mascaras_validas()</code> deriva do catálogo, então o terceiro sabor passa a valer
      no disco e no portão do IPC <b>sem uma linha de edição</b>.</li>
    <li><b>A máscara já é por aparelho no código</b> (<code>daemon/subsystems/external_mask.py</code>,
      desde 15/08) — o registro por MAC e a herança existem. O que falta é <b>passar a
      identidade</b> em três lugares: <code>virtual_pad.make_virtual_pad</code>,
      <code>coop.py</code> e <code>gamepad.py</code>. Hoje ninguém a passa, e por isso a
      máscara viva é uma só para a mesa toda — que é exatamente o que esta tela deixa de
      mostrar.</li>
    <li><b>Um fato do specs, para a sprint não prometer o que o aparelho não tem:</b> o
      Pro Controller <b>não tem</b> microfone, alto-falante, touchpad, lightbar RGB, gatilho
      adaptativo nem gatilho analógico (ZL/ZR são digitais) — 99 linhas do
      <code>mapa-controles.csv</code>. Nada disso é aviso para esta tela: máscara não é
      adoção. A máscara Nintendo Pro faz o <b>seu DualSense</b> aparecer como um Pro para o
      jogo; ela não faz o Hefesto adotar um Pro.</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>O microfone quando a máscara é Xbox 360 ou Nintendo Pro.</b> A ONDA-CONEXOES-06
      escreve que nessas máscaras o jogo não pergunta pelo microfone e por isso ele
      <b>some do jogo</b>, e cria o estado <b>Emulado</b> para tapar o buraco — uma fonte de
      captura virtual que qualquer jogo enxerga. É por isso que esta tela não escreve aviso
      nenhum. <b>Mas essa afirmação não tem medição</b>: não há uma linha de microfone ×
      máscara no <code>ensaios.csv</code>, e a régua que a provaria está escrita na própria
      sprint <b>sem dono</b>. Hoje quem entrega o mic ao jogo é a prioridade do WirePlumber,
      que é cega à máscara — o que <b>estreita</b> o buraco e ninguém sabe quanto. É uma
      sprint de bancada, e ela não está na fila.</li>
  </ul>
</div>

</body>
</html>
'''


def _conferir(doc):
    """As decisões dela de 31/08, conferidas NA SAÍDA. O gerador para se caírem.

    POR QUE NA SAÍDA, e não sobre as constantes: uma régua que lê `MODOS` prova
    que a LISTA está certa, não que a PÁGINA está. As duas já divergiram nesta
    casa — a fita viva morreu em silêncio quando o texto do chip mudou e o
    remendo deixou de casar, com o gerador imprimindo OK. Aqui a régua lê o HTML
    que acabou de ser escrito, que é o que ela vai abrir.

    E CADA UMA MORDE NOS DOIS SENTIDOS: além de exigir o que ela pediu, exigem
    que o que devia sair tenha saído. Uma régua que só confere presença dá verde
    sobre uma página onde nada foi removido.
    """
    # SÓ O MIOLO, e esta linha é a régua da régua. A primeira volta leu a página
    # INTEIRA e reprovou três rótulos que estavam certos: `>Hefesto</span>` casava
    # com o `<h1>` do cabeçalho — o NOME DO PRODUTO — e "Quando o jogo abrir" e
    # "Conectado agora" casavam **oito vezes cada** dentro da `<div class="nota">`,
    # que é a legenda contando a história da mudança. Citação não é rótulo, e
    # apagar a citação para calar a régua seria apagar o registro.
    #
    # É a armadilha nomeada no `COMO-OLHAR-A-TELA.md` — *"régua que casa um token
    # em QUALQUER lugar do texto, em vez do campo que o significa"* —, e ela
    # produziu aqui exatamente o sintoma que a página descreve: três alarmes
    # convincentes e falsos.
    #
    # E OS COMENTÁRIOS HTML SAEM JUNTO, pela mesma razão: comentário não é tela.
    # Achado na volta seguinte — o comentário que explica a fusão das dicas cita o
    # rótulo "O jogo vê cada controle como:", e a régua contou 2 e reprovou o
    # texto que ela mesma tinha acabado de exigir.
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo — o recorte mudou de forma. "
                         "Uma régua que mede 0 caractere passa com qualquer desenho.")

    falhas = []

    def exigir(cond, oquê):
        if not cond:
            falhas.append(oquê)

    # 1. O POINT AND CLICK SAIU DA FILEIRA — *"nos mockups tira o point and click
    #    e deixa só o navegação."* O `Point-and-click` da aba Navegação e o perfil
    #    de fábrica continuam: por isso a régua olha o DEGRAU, não a palavra solta.
    exigir('data-degrau="pointclick"' not in corpo, "o Point And Click voltou à fileira")
    exigir(corpo.count('class="degrau') >= 4, "a fileira perdeu degrau")

    # 2. NENHUM TOOLTIP NEGA FEATURE POR MODO — *"independente do modo, todas as
    #    features vão funcionar. Então o tooltip falando o contrário é sem nexo."*
    #    As duas frases que caíram, e elas se sustentavam uma na outra.
    for frase in ("sem giroscópio", "só chegam ao jogo por aqui",
                  "só chegam ao jogo pelo", "sem touchpad para o jogo"):
        exigir(frase not in corpo, f"um tooltip voltou a negar feature: {frase!r}")

    # 3. OS TRÊS RÓTULOS QUE ELA TROCOU, e o antigo não pode ter sobrado.
    for novo, velho in (("<span class=\"linha-rot\">Status</span>", ">Hefesto</span>"),
                        (">Modo</span>", ">Quando o jogo abrir<"),
                        (">O Controle é visto como:</span>", ">Conectado agora<")):
        exigir(novo in corpo, f"o rótulo novo sumiu: {novo!r}")
        exigir(velho not in corpo, f"o rótulo antigo voltou: {velho!r}")
    # e o rótulo interno não pode ter ficado junto com o título novo
    exigir(corpo.count("O Controle é visto como:") == 1,
           "o rótulo interno das máscaras voltou (o texto aparece 2×)")
    exigir("O jogo vê cada controle como" not in corpo,
           "o título anterior voltou — ela o trocou em 31/08")

    # 4. A MESA — dois na mesa, dois lugares vazios, e o cabeçalho contando os
    #    conectados. *"Todas as abas tem que ter só dois controles conectados."*
    exigir(corpo.count('data-conectado="sim"') == 2, "não são 2 controles conectados")
    exigir(corpo.count('data-conectado="nao"') == 2, "não são 2 lugares vazios")
    exigir(f"{len(monta.CONECTADOS)} controles:" in doc,
           "o cabeçalho não conta os conectados")

    # 5. LUGAR VAZIO NÃO TEM MÁSCARA ESCOLHIDA. Sem controle não há escolha, e
    #    marcar uma desenharia um ajuste que não existe.
    for pedaco in corpo.split('class="cartao off"')[1:]:
        exigir('class="chip on"' not in pedaco.split("</div>\n              </div>")[0],
               "um lugar vazio tem máscara marcada")

    # 6-bis. NENHUM ALARME SEM MEDIÇÃO. Ela, 31/08: *"qualquer coisa fora isso
    #    tá incorreta"* — a regra do Nativo é só "Desligado põe o Nativo online".
    #    As duas frases que caíram alarmavam sobre número que ensaio nenhum deste
    #    repositório mede.
    for frase in ("derrubam o controle", "resultado é ZERO", "duros como no PS5"):
        exigir(frase not in corpo, f"um texto voltou a alarmar sem medição: {frase!r}")

    # 6. A PENDÊNCIA DIZ O QUE ESTÁ MARCADO — ela viu a contradição: a tela em
    #    Ligado + Sony DualSense e a faixa anunciando Modo Nativo.
    exigir(f"<b data-campo=\"pendente-alvo\">{PENDENTE}</b>" in corpo,
           "a faixa de pendência não diz o modo marcado")
    exigir(PENDENTE != "Modo Nativo",
           "a pendência voltou a ser Modo Nativo com o interruptor em Ligado")

    if falhas:
        raise SystemExit("ERRO em 01-jogar — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


if __name__ == "__main__":
    n = montar("01-jogar", "Jogar", MIOLO, CSS, fita_viva=True, legenda=LEGENDA)
    _conferir(onde.pagina("01-jogar.html").read_text())
    print(f"01-jogar: OK, {n} divs · mesa de {len(monta.CONECTADOS)} conectado(s) "
          f"+ {len(MESA) - len(monta.CONECTADOS)} lugar(es) vazio(s) · "
          f"máscaras {frase_das_mascaras()} · as 5 decisões dela conferidas")
