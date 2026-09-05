# A PASTA, não /tmp: o `monta` e o `topo.html` vivem aqui, e é daqui que esta
# aba os lê. Ver o cabeçalho do aba09.py para o defeito que isso curou.
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import re
import onde
from monta import monta, glifo, cor_da_zona, rotulo, CSS_GLIFO, MESA, SEPARADOR, R

# OS DOIS DONOS QUE ESTA PÁGINA PERGUNTA EM VEZ DE DIGITAR — 03/09/2026.
#
# A FAIXA DA PRIORIDADE sai de `profiles/schema.py`, que é onde o teto mora
# desde a UNIFICA-CONSTANTE-01 e tem portão próprio
# (`test_teto_da_prioridade_tem_uma_fonte_so.py`). O `<input type=range>` desta
# aba nasce com `min`/`max` de lá: o dia em que o teto sair de 200 e o desenho
# continuar oferecendo 0..200 é o dia em que o slider dela para de alcançar os
# números que o produto aceita — e ninguém veria.
#
# OS RÓTULOS DOS ESTILOS saem de `profiles/estilos_de_jogo.py`, o motor que
# nasceu em 03/09/2026 com as quinze receitas que ela aprovou. Eram QUINZE
# palavras digitadas aqui, e a lista só concordava com o motor por coincidência:
# um estilo novo lá, ou um rótulo corrigido, e o `<select>` passaria a oferecer
# uma opção que o gesto não sabe aplicar — a tarja diria "não é um estilo" sobre
# uma palavra que a própria página escreveu.
#
# O `R` É A PASTA `interface/`, então o `src/` é dois acima. O `insert` é a
# trava para quem rodar o gerador sem `PYTHONPATH`; com ele posto, o import é o
# mesmo que o `aba03.py` já faz com o `trigger_specs`.
sys.path.insert(0, str(R.parents[1]))
from hefesto_dualsense4unix.profiles.estilos_de_jogo import (  # noqa: E402
    ESTILOS as ESTILOS_DO_MOTOR,
)
from hefesto_dualsense4unix.profiles.schema import (  # noqa: E402
    PRIORIDADE_MAXIMA,
    PRIORIDADE_MINIMA,
)

# ---------------------------------------------------------------------------
# O QUE O PERFIL GUARDA DE CADA CONTROLE — e isto NÃO é escolha de desenho.
#
# `Profile.controllers` é um mapa `{ID da peça: ControllerOverrides}`
# (`profiles/schema.py:1008`), e a classe tem QUATRO campos HOJE
# (`profiles/schema.py:961-964`):
#
#     leds  ·  triggers  ·  rumble  ·  speaker
#
# E A TELA MOSTRA CINCO — decisão dela, 03/09/2026, decisão nº20:
# **o microfone vira o quinto ajuste por controle.** A razão é dela e é o canal:
# é o `Virtual` que faz o mic soar igual no cabo e no rádio, ou seja, é o ajuste
# que faz o CANAL daquele controle funcionar — e com "4 controles, 4 canais"
# (`2026-09-03-CANAL-POR-CONTROLE-01`) ele vira por-controle por necessidade,
# porque um controle no cabo e outro no rádio precisam de tratamentos
# diferentes.
#
# FATO SUBSTITUÍDO. Aqui estava escrito que o `mic` era do perfil INTEIRO
# *"porque o interruptor `mic_button_toggles_system` é UM por máquina"*. O
# interruptor continua um só e a frase morreu assim mesmo: o que a coluna mostra
# não é o interruptor da mesa, é o que o PERFIL guarda daquela peça. A própria
# `ControllerOverrides` já põe o `mic` em primeiro lugar na fila do que falta, e
# diz que o caminho por peça **já existe inteiro** — as três primitivas de pé
# (`EventTopic.MIC_DA_MESA` com `uniq`, `fonte_de_captura_do_uniq`,
# `set_microphone_mute(uniq=…)`), faltando três costuras. *"O item mais caro da
# lista virou o mais barato."*
#
# O QUINTO NASCE APAGADO EM TODO PERFIL REAL, e isso não é defeito: enquanto
# `ControllerOverrides.mic` não existir, `perfis_web._secoes_do_controle` não
# devolve a chave, o pacote lê `None` e a coluna fica no estado "herda" — que é
# a verdade. A tela está pronta para o campo; ela não o inventa.
#
# Campo `None` = **sem opinião**: aquele controle herda a seção global do perfil
# (merge POR CAMPO, PERFIL-01). É por isso que a coluna tem dois estados e não
# um: aceso é "este perfil guarda um ajuste só deste controle", apagado é
# "ele usa o do perfil, igual aos outros" — e apagado é a resposta certa para a
# maioria dos controles na maioria dos perfis.
#
# A lista abaixo é uma TRADUÇÃO da classe mais a decisão nº20, não uma segunda
# verdade: quem a compara com o esquema é
# `tests/unit/test_a_coluna_de_ajuste_proprio_da_aba10_e_dado.py`, que exige que
# toda seção desenhada exista em `perfis_web.SECOES_POR_CONTROLE` — com o `mic`
# isento ENQUANTO o esquema não o tiver, e cobrado no dia em que tiver.
#
# NÃO HÁ MAIS DICA POR CÉLULA — decisão dela, 03/09/2026, decisão nº4:
# *"Meu Deus melhor nenhuma assim. Auto falante é auto falante, gatilho é
# gatilho."* Eram oito frases (quatro pares, uma por estado), e as oito saíram:
# a dica do CABEÇALHO já explica o conceito uma vez, e o glifo já diz o nome da
# peça. Por isso esta lista tem DOIS termos, e não três — o terceiro era o texto
# que saiu, e deixá-lo aqui sem uso o faria voltar no primeiro descuido.
#
# A SEXTA NASCEU EM 05/09/2026, e ela é a queixa dela: *"a aba 10 tá com o mesmo
# problema de antes. nada mudou."* O `sensores` entrou em `ControllerOverrides`
# em 04/09 (`8f9589ba`, SENSOR-DE-VERDADE-01) e esta lista ficou nos cinco — o
# perfil passou a guardar giroscópio e acelerômetro POR PEÇA e a tabela que
# existe para mostrar o que cada controle tem de próprio não tinha célula para
# eles. Medido com o disco dela: `_secoes_do_controle` devolvia SEIS chaves e a
# página tinha CINCO endereços, então a dica da linha dizia *"3 de 6 ajustes só
# deste controle"* enquanto o cabeçalho ao lado dizia *"os cinco ajustes"*.
# Um controle cujo único ajuste próprio fosse o sensor entrava na conta do
# cabeçalho ("1 de 2 controles com ajuste próprio") com a fileira toda apagada.
SECOES = [
    ("leds", ("lightbar", "led-jogador")),
    ("triggers", ("l2", "r2")),
    ("rumble", ("rumble_esquerdo", "rumble_direito")),
    ("speaker", ("alto-falante",)),
    ("mic", ("mic",)),
    ("sensores", ("giroscopio", "acelerometro")),
]

#: COMO CADA SEÇÃO SE CHAMA NA DICA DO CABEÇALHO, e por que ela não é digitada
#: na frase: a dica listava *"luz, gatilhos, vibração, alto-falante e
#: microfone"* à mão, e foi ela que sobreviveu intacta à chegada do `sensores` —
#: a mesma família de defeito que o `QUANTAS_SECOES` abaixo já tinha matado para
#: o NÚMERO e ninguém tinha matado para os NOMES. A frase agora se monta desta
#: tabela, na ordem de `SECOES`, e `monta` reprova a seção que não tiver nome.
NOME_DA_SECAO = {
    "leds": "luz",
    "triggers": "gatilhos",
    "rumble": "vibração",
    "speaker": "alto-falante",
    "mic": "microfone",
    "sensores": "sensores",
}


def _lista_das_secoes() -> str:
    """`luz, gatilhos, vibração, alto-falante, microfone e sensores`."""
    nomes = [NOME_DA_SECAO[campo] for campo, _pecas in SECOES]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}" if len(nomes) > 1 else nomes[0]


#: O NÚMERO POR EXTENSO, para a tela nunca discordar da lista. As frases da aba
#: dizem "os seis ajustes"; escrever a palavra à mão em três lugares é como a
#: contagem de `NAO_PINTAVEIS` divergiu no primeiro dia. Sai daqui, de
#: `len(SECOES)`, e muda sozinha quando a lista mudar.
_EXTENSO = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis"}
QUANTAS_SECOES = _EXTENSO[len(SECOES)]

# O ESTADO DESTE PERFIL, controle a controle. Um mockup que acende TODAS as
# seções nos quatro controles ensina que o normal é cada peça ter tudo próprio —
# e o normal é o contrário: quem não tem opinião herda. Aqui aparecem quatro
# gradações, inclusive a de baixo, que é a mais comum.
#
# O `mic` ENTRA ACESO NUM SÓ, e é de propósito: uma coluna nova apagada nas
# quatro linhas leria como "esta coluna nunca acende", que é o oposto da decisão
# nº20. Aceso em um, apagado em três, é a mesma pedagogia dos outros quatro — e
# o `sensores`, que chegou em 05/09, entra pela mesma regra, no P2 para não
# empilhar as duas colunas novas na mesma linha.
GUARDA = {
    "p1": {"leds", "triggers", "rumble", "mic"},
    "p2": {"leds", "rumble", "sensores"},
    "p3": {"leds"},
    "p4": set(),
}

# O ID DA PEÇA é o endereço de rádio normalizado — a MESMA chave que o
# `_validate_controllers_keys` aceita e canoniza (`profiles/schema.py:1527`), e
# a mesma que a dica do "Perfil ativo" promete no esqueleto: *"pelo ID da peça —
# amanhã, em outra porta ou no rádio, ele traz de volta o que você deixou hoje"*.
# A promessa é verdadeira porque o endereço é ESTÁVEL entre USB e BT no
# DualSense — medido nesta casa e escrito no esquema (`:1002`).
#
# `AA:BB:` é o endereço DIDÁTICO da casa: nada de endereço real em arquivo
# versionado (CLAUDE.md, e os dois portões que a regra tem).
ID_DA_PECA = {"p1": "AA:BB:CC:00:00:01", "p2": "AA:BB:CC:00:00:02",
              "p3": "AA:BB:CC:00:00:03", "p4": "AA:BB:CC:00:00:04"}

CSS = CSS_GLIFO + """
  /* ---------- Perfis ---------- */
  /* UM FUNDO SÓ, com os dois blocos dentro. Eles continuam sendo dois — mesma
     largura, mesma altura, cada um com o seu título e os seus três botões — mas
     a moldura é uma, e o vão entre eles vira uma divisória fina. Pedido dela em
     27/08: "deixa um só, pra causar a ilusão de um único bloco". */
  /* A CORRENTE DA ALTURA: o quadro `estica` cresce até o rodapé, e daí para baixo
     cada elo precisa passar a altura adiante — corpo, grade, coluna, moldura,
     lista. Faltando um elo, a lista volta a parar no tamanho do conteúdo.
     `flex:1;min-height:0` e NÃO `height:100%`: a porcentagem se resolve contra a
     altura do pai, que aqui é automática — a conta fica circular, o navegador cai
     no `auto`, e o quadro cresceu 116px além do miolo levando a fileira de botões
     para fora da janela. */
  .perfis{flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;align-items:stretch;
          border:1px solid var(--linha);border-radius:7px;background:var(--app-bg);
          overflow:hidden}
  /* `min-height:0` em cada elo: por padrão um filho de flex não encolhe abaixo do
     próprio conteúdo. Sem ele, a lista sem teto empurrou a coluna para baixo e a
     fileira `Ativar · Novo · Remover` saiu pela borda do quadro — sumiu da tela. */
  .perfis > div{display:flex;flex-direction:column;padding:10px 14px;min-height:0}
  .perfis > div:first-child{padding-right:7px}
  .perfis > div:last-child{padding-left:7px}

  .perfis > div > .moldura{flex:1;min-height:0;display:flex;flex-direction:column}
  .moldura{border:none;background:none;padding:0}
  /* A CAIXA ALTA SAIU — 30/08/2026. A regra desta casa sobre maiúscula é a
     PRIMEIRA LETRA, e ela confirmou: *"a maiúscula a regra é sobre a primeira
     letra a ser capitalizada, é o padrão do projeto"*. O `text-transform:
     uppercase` a violava calado, e ainda cobrava o preço de legibilidade que
     ela apontou (*"essa fonte tem um contraste horrível"*): caixa alta a 11px
     é a forma mais difícil de ler que existe.
     O `letter-spacing` sai junto — ele existia para abrir a caixa alta.
     O texto-fonte já está em caixa de frase ("Força da vibração", "Selecione o
     player"), então nada precisou ser reescrito. */
  /* O TÍTULO DE BLOCO CONTINUA VERDE — 31/08/2026, ela decidiu no mesmo turno
     em que mandou tirar o verde dos nomes: *"coloca essa na cor ver[de] e o
     Definições também"*. E é coerente com a regra que ela desenhou: o verde
     saiu de quem NOMEIA UMA LINHA (rótulo de campo, cabeçalho de coluna) e
     ficou em quem ABRE UM BLOCO — são dois, `Perfis Salvos` e `Definições`, e
     eles é que dizem onde a pessoa está. */
  .sec-rot{font-size:12px;font-weight:700;color:var(--rot-campo);
           margin-bottom:10px;display:flex;align-items:center;gap:6px;height:15px}
  /* A LISTA LÊ COMO TABELA: cabeçalho com fundo próprio e linhas zebradas. Quem
     diz que há mais perfis abaixo é a barra de rolagem de verdade (ver abaixo). */
  /* SEM `max-height`. Ela tinha teto de 236px: a lista parava em sete perfis e
     meio — a linha `Faith` ficava cortada ao meio — com o bloco inteiro sobrando
     embaixo. Ela, 27/08: "pq esse bloco aqui é super capado assim? ... aqui tem
     literalmente zero necessidade de não usar ele". Agora ela ocupa o que o bloco
     tem, e o bloco ocupa até o rodapé. */
  .lista{position:relative;flex:1;display:flex;min-height:0}
  /* A ROLAGEM ENCOSTA EM LINHA INTEIRA — 30/08/2026.
     A barra de verdade (cura de 28/08) funciona: 12px, e os 3 perfis de baixo
     são alcançáveis. O que sobrava era a FRAÇÃO: a caixa mede 363px e a linha
     32, então a 12ª aparecia com 11px — a faixa acima da linha de base, ou
     seja, uma tira VAZIA. Meia linha com meio texto diz "tem mais abaixo";
     meia linha sem texto nenhum lê como quebrada, que foi o que a medição
     apontou.
     `scroll-snap` não muda a altura de nada e não esconde perfil nenhum: ele só
     faz a rolagem PARAR em fronteira de linha. `proximity` e não `mandatory` —
     o mandatory sequestra o gesto e brigaria com a barra que ela acabou de
     ganhar. */
  .rolo{scroll-snap-type:y proximity}
  .rolo tr{scroll-snap-align:start}
  /* A BARRA É A DE VERDADE, CLÁSSICA, E OCUPA ESPAÇO — a mesma cura que a 02 já
     aplicou no `.quadro-corpo`.
     O QUE ESTAVA AQUI ESCONDIA A LISTA. `.rolo` trazia `scrollbar-width:none` e
     `::-webkit-scrollbar{display:none}`, e no lugar da barra real vinha uma
     DESENHADA — `.nav-trilho` + `.nav-polegar`, um par de spans com
     `position:absolute` e um polegar de altura fixa em `46%`. Medido em 28/08:
     dos 14 perfis a lista mostrava 11; **116px** ficavam fora (≈3,6 linhas),
     atrás de 2px que eram a BORDA do `.rolo`, não uma barra — a barra media  (noqa-acento: verbo medir, imperfeito)
     zero. E o polegar desenhado mentia duas vezes: não andava ao rolar e os
     46% não tinham relação com a proporção real (359 de 475 = 75,6%).
     As regras de `width:9px` logo abaixo eram letra morta: `display:none` já
     tinha vindo antes, e `width` não desfaz `display`.
     Barra de verdade porque ela nasce só quando há o que rolar, mede a
     proporção sozinha e anda junto — os estados em que a lista cabe não pagam
     nada por ela. É por isso que ela vale mais que `scrollbar-gutter:stable`,
     que reservaria a faixa em toda tela. */
  /* SEM MOLDURA — 31/08/2026. `.rolo` e `.campos` moram DENTRO do `.perfis`,
     que já é uma moldura, e cada um tem o fundo `--panel` sobre o `--app-bg`
     dela. A borda era a terceira linha do mesmo contorno, e é metade do que
     ela chamou de *"borda dupla"*: *"os campos ... com borda dura em volta de
     cada um, e a caixa que os contém com outra borda por fora"*. O que separa
     os dois blocos é o fundo e o vão — que é a *"ilusão de um único bloco"*
     que ela pediu em 27/08, e que a moldura de dentro desfazia. */
  .rolo{flex:1;overflow-y:auto;border-radius:6px;
        background:var(--panel)}
  .rolo::-webkit-scrollbar{width:10px}
  .rolo::-webkit-scrollbar-track{background:transparent}
  .rolo::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .rolo::-webkit-scrollbar-thumb:hover{background:var(--comment)}
  .tab{width:100%;border-collapse:collapse;font-size:11.5px}
  .tab thead th{position:sticky;top:0;z-index:2;text-align:left;font-weight:700;font-size:10px;
          color:var(--fg);
          padding:7px 10px;background:var(--elevated);
          border-bottom:1px solid var(--linha)}
  .tab td{padding:8px 10px;color:var(--texto-suave);cursor:pointer;
          border-bottom:1px solid var(--linha)}
  .tab tbody tr:nth-child(even) td{background:rgba(255,255,255,.018)}
  .tab tbody tr:last-child td{border-bottom:none}
  /* OS TRÊS ESTADOS DA LINHA, e são TRÊS porque são duas verdades diferentes —
     queixa dela, 04/09/2026: *"quando clica em algum nome do perfis salvos nada
     indica que tal coisa tá selecionado"*.

       VALENDO       o perfil que o daemon está aplicando agora  → `class="ativo"`
       ABERTO        a linha em que o editor ao lado está aberto → `aria-selected`
       VALENDO+ABERTO os dois na mesma linha — é o estado em que a aba ABRE,
                     porque `a10_perfis._escolhido` sincroniza o escolhido com o
                     ativo enquanto ela não clicou em nada.

     A janela GTK antiga já tinha os dois separados — `Gtk.TreeSelection` para a
     seleção e `Pango.AttrList` para o ativo (`profiles_actions.py:1400`, sprint
     `2026-08-10-PERFIL-ATUAL-01`) —, e o HTML tinha implementado só o segundo:
     clicar num perfil mudava o alvo de nove botões e a tela não dizia uma letra.

     A COR DIZ *VALENDO*, O FUNDO DIZ *ABERTO*, e por isso os dois se somam sem se
     apagar: verde é o plástico do "está no ar" em toda esta casa, e o par
     `--purple`/`--sel-bg` é o "isto está escolhido" das dez abas (o `.chip.on` do
     topo, o `.rota button.on`, o `.mm-ap.on`). Quem está nos dois estados mostra
     a barra DUPLA — 3px de verde por cima de 6px de roxo.

     O ESTADO MORA NUM ATRIBUTO E NÃO NUMA SEGUNDA CLASSE, e a razão é medida:
     `test_a_lista_de_perfis_cabe_inteira.py:195` procura a SUBSTRING
     `class="ativo"`, e um `class="ativo escolhido"` a apaga — a régua do realce
     ficaria verde sobre uma linha que ela não acha mais. `aria-selected` é o que
     o papel `row` já define para isto, é uma verdade só, e leitor de tela lê.

     `tbody` NOS SELETORES NÃO É ENFEITE: sem ele a regra empata com
     `.tab tbody tr:nth-child(even) td` (0,2,3) e a zebra come o fundo da linha
     escolhida nas posições pares — metade das linhas sem marca. */
  .tab tr.ativo td{color:var(--green);font-weight:600}
  .tab tr.ativo td:first-child{box-shadow:inset 3px 0 0 var(--green)}
  .tab tbody tr[aria-selected="true"] td{background:var(--sel-bg);color:var(--fg);
          font-weight:600}
  .tab tbody tr[aria-selected="true"] td:first-child{box-shadow:inset 3px 0 0 var(--purple)}
  .tab tbody tr.ativo[aria-selected="true"] td{color:var(--green)}
  .tab tbody tr.ativo[aria-selected="true"] td:first-child{
          box-shadow:inset 3px 0 0 var(--green),inset 6px 0 0 var(--purple)}
  .tab tbody tr:hover:not(.ativo):not([aria-selected="true"]) td{background:var(--sel-bg)}
  /* `Pri.` VIROU `Priorização` — 31/08/2026, pedido dela. Os 46px do valor
     antigo JÁ NÃO ERAM VERDADE: `table-layout` é `auto`, então `width` é
     sugestão, e o Chrome media 86px para caber o cabeçalho. O número aqui passa  # (noqa-acento) id
     a ser o medido; escrever 46 embaixo de uma coluna de 86 é deixar no CSS uma
     afirmação que a tela desmente. */
  .tab .pri{font-family:'JetBrains Mono',monospace;width:86px;text-align:right}
  .tab .quando{color:var(--texto-mudo);font-weight:400}
  .conta-perfis{font-size:10.5px;color:var(--comment);margin-left:auto;text-transform:none;
                letter-spacing:0}
  /* 3 botões e 3 botões, todos da mesma largura */
  .botoes{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:auto;padding-top:12px}
  .botoes .btn{width:100%;justify-content:center;padding:0 8px;font-size:11.5px}
  /* os campos do editor, todos na mesma grade */
  /* os campos ficam sobre o MESMO fundo da tabela ao lado, e assim os três botões
     de baixo nascem na mesma base nos dois blocos. */
  /* `min-height:0` aqui é o que impede a coluna da direita de EMPURRAR a fileira
     de botões para fora da moldura: sem ele um filho de flex não encolhe abaixo do
     próprio conteúdo, e a tabela de baixo levou `Duplicar · Voltar · Recarregar`
     19px além da borda do quadro — que tem `overflow:hidden`, então os três
     simplesmente sumiam da tela. Medido em 27/08, no primeiro desenho desta tabela. */
  .campos{flex:1;min-height:0;border-radius:6px;
          background:var(--panel);
          padding:10px 12px;display:flex;flex-direction:column;justify-content:flex-start}
  /* `flex-start` e não `center`: com a lista limitada a 236px o bloco era baixo e
     centrar não aparecia. Solto o teto, os campos passaram a flutuar no meio, com
     um vão em cima e a lista da esquerda começando bem mais acima. */
  /* O RÓTULO ALINHA À ESQUERDA — 31/08/2026, pedido dela olhando a aba:
     *"alinha os nomes a esquerda e trás os slicers pra iniciarem deles"*.
     Ele alinhava à direita, como nas outras nove; aqui não alinha mais, e a
     divergência é a que ela pediu.
     `nowrap` porque a coluna passou a ser JUSTA: sem ele um rótulo que crescer
     vira duas linhas e estoura a altura do campo, que nesta aba é medida contra
     o `overflow` do quadro. */
  /* MENOS VERDE — 31/08/2026, pedido dela olhando a aba: *"acho que tem muito
     verde na página. Talvez alterar com um branco com negrito ativado em alguns
     cantos"*.
     A REGRA QUE ESCOLHI, e ela é o que decide QUAIS cantos: **o verde fica onde
     significa ESTADO; o que só NOMEIA vira branco em negrito.** Havia 20 pedaços
     verdes na janela e a maior parte só dava nome a uma coisa — cabeçalho de
     coluna, título de bloco, rótulo de campo —, então o verde tinha deixado de
     querer dizer alguma coisa: quando tudo é verde, o perfil ATIVO em verde não
     salta.
     Continuam verdes, e cada um por um motivo: a linha do perfil ativo (é o
     estado da lista), o botão `Ativar` (a ação primária) e o cabeçalho do topo
     (que é do `topo.html` e vale para as dez).
     O NEGRITO É QUEM PAGA O CONTRASTE PERDIDO: `--fg` sobre `--elevated` é mais
     claro que o verde, mas sem peso um cabeçalho de coluna vira dado. */
  .campo > span:first-child{color:var(--fg);font-weight:700;text-align:left;
                            white-space:nowrap}
  .campo{display:grid;grid-template-columns:var(--rot-p) 1fr;align-items:center;gap:12px;
         height:var(--h-escolha);font-size:12px;color:var(--texto-mudo);margin-bottom:4px}

  /* AS DIVISÓRIAS SAÍRAM DESTE TRECHO — 31/08/2026, pedido dela olhando a aba:
     *"remove as linhas horizontais desse trecho"*.
     Elas nasceram de um pedido dela de 30/08 — *"as linhas divisórias em todas
     as páginas (…) a primeira coluna serve como nome da linha e a divisória
     entre eles tem que estar clara. pra todas as abas"* — e esse pedido CONTINUA
     valendo nas outras nove: o molde está no `aba04.py`, com a razão escrita lá.
     O que mudou foi o TRABALHO da divisória. Ela separava duas colunas distantes:
     o rótulo terminava a 22px do campo, alinhado à direita. Com o rótulo à
     esquerda e a coluna justa, o nome já encosta no campo — e a linha deixou de
     separar para virar mais uma borda ao lado das cinco que os campos já têm. */
  .campo .val{display:flex;align-items:center;gap:10px}
  .campo input[type=text],.campo select{
    flex:1;min-width:0;height:var(--h-escolha);border-radius:7px;font-size:12.5px;font-family:inherit;
    padding:0 11px;border:1px solid var(--linha);background:var(--app-bg);color:var(--fg);
  }
  .campo select{cursor:pointer}
  .campo select.destaque{border-color:var(--purple);background:var(--sel-bg);font-weight:600}
  /* A PRIORIDADE É SLIDER — pedido dela em 27/08 (*"prioridade é slicer"*, em
     CORRECOES-DELA.md) e reconfirmado em 03/09/2026: *"Slider, como você
     pediu"*. Até aqui o desenho tinha uma BARRA, que não se arrasta: era o
     único campo do editor sem nenhum caminho de escrita na interface nova.

     O TRILHO E O CHEIO FICAM, e continuam sendo quem MOSTRA — o produto escreve
     a largura do cheio a cada tique. O que nasce é o `<input type=range>` por
     cima: transparente, do tamanho do trilho, e é ele quem ACEITA o arrasto.

     O PUNHO MUDOU DE DONO, e essa é a única coisa que se perde do desenho
     antigo: ele era o `::after` do cheio — pintado pelo produto, logo com meio
     segundo de atraso — e passou a ser o `::-webkit-slider-thumb` do range, que
     segue o dedo dela no mesmo quadro. Enquanto ela arrasta, o cheio fica para
     trás (ele só sabe o que o disco diz); no `change` o gesto grava e a resposta
     do próprio gesto repinta os dois na hora, sem esperar o tique.

     `-webkit-` E NÃO `-moz-`: a janela é um `WebKit2.WebView`, e o Chrome que a
     bancada usa para fotografar é a mesma família. Um `::-moz-range-thumb` aqui
     seria regra que nenhum dos dois lê. */
  .campo .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .campo .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .campo .desliza{position:absolute;left:0;top:50%;transform:translateY(-50%);
    width:100%;height:14px;margin:0;padding:0;background:transparent;border:0;
    -webkit-appearance:none;appearance:none;cursor:pointer}
  .campo .desliza:focus{outline:none}
  .campo .desliza::-webkit-slider-runnable-track{height:14px;background:transparent;border:0}
  .campo .desliza::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:12px;height:12px;border-radius:50%;background:var(--purple);
    border:2px solid var(--app-bg);margin-top:1px}
  .campo .n{flex:0 0 40px;text-align:right;font-family:'JetBrains Mono',monospace;color:var(--fg)}
  .campo .btn{flex:0 0 auto;white-space:nowrap}
  /* A COLUNA DO RÓTULO É JUSTA — remedida no Chrome em 31/08/2026, DEPOIS que ela
     pediu os dois pontos e a maiúscula — com a preposição minúscula, que foi a
     segunda palavra dela: `Nome:` 36px · `Prioridade:` 63 · `Funciona em:` 77 ·
     `Estilo de Jogo:` 85 · `Nome do Jogo:` **86** — que trocou de dono, era o
     `Estilo de Jogo` com 82 antes dos dois pontos.
     Os 104 antigos deixavam 17px de vão morto à direita de todo rótulo — e é
     esse vão que os campos ganharam.
     NÃO dá para usar `max-content`: cada `.campo` é um grid PRÓPRIO, então a
     coluna se resolveria linha a linha e as cinco desalinhariam. Quem mudar o
     texto de um rótulo tem de remedir no Chrome e trazer o número para cá. */
  :root{--rot-p:86px}

  /* ---------- A TIRA DO DESFECHO — o toast que esta janela não tinha ----------
     PARIDADE COM A JANELA ESTÁVEL, 03/09/2026. Lá, TODO gesto desta aba termina
     num `_toast_profile` no rodapé (`profiles_actions.py:4579`): "Perfil
     removido: X", "Lista recarregada", `mensagem_de_ativacao`. Aqui só a
     RECUSA falava — `RuntimeError` vira tarja no piloto — e o SUCESSO era
     silêncio. Para os NOVE gestos desta aba que ESCREVEM NO DISCO DELA,
     silêncio no sucesso é o botão que responde calado.

     O ESPAÇO ERA RESERVADO SEMPRE, E ELA VIU — 05/09/2026: *"a aba dez tem um
     espaço vertical bizarro desnecessário no título"*. A tira mora entre o
     `.quadro-topo` e o `.quadro-corpo`, e reservada com `height:30px` +
     `margin-top:7px` ela punha **37px de banda morta logo abaixo do título
     "Perfis"** — medido no Chrome nas dez páginas publicadas, e a aba 10 era a
     ÚNICA das dez com vão entre topo e corpo (as outras nove: 0px). O custo
     estava sendo pago em toda a vida da tela para poupar um pulo que acontece
     nove vezes por sessão, e nas outras nove abas o recado do piloto
     (`.hef-recado`) já não paga nada: ele nasce quando há notícia.

     A CAIXA COLAPSA VAZIA E ABRE CHEIA. `visibility` continua no lugar de
     `display` — quem some é a ALTURA, não o elemento —, e a razão é o alvo
     `classe` do piloto: ele acha a tira por `querySelectorAll` e alterna `on`,
     e um `display:none` faria o `-webkit-line-clamp` recalcular do zero a cada
     clique. Vazia ela mede **zero**; acesa ela volta aos MESMOS 30px de duas
     linhas mais os 7px de folga — a frase longa chega igual à de antes.

     O QUE ISSO DEVOLVE, e está declarado: o pulo de 37px na primeira notícia do
     gesto. É o preço que ela escolheu ao chamar a banda de bizarra, e ele é
     pago por clique, não por segundo de tela aberta.

     VERDE porque é desfecho BOM: a recusa já tem cor e lugar próprios (a tarja
     do piloto). Dois canais, duas cores, nenhuma dúvida sobre qual é qual.

     DUAS LINHAS, E A SEGUNDA É A QUE AVISA — decisão [05] do PO, 04/09/2026.
     Aqui estava escrito *"UMA LINHA SÓ, com reticências"*, e o preço estava
     medido do lado errado: o que a reticência come é o FIM da frase, e o fim é
     sempre a metade que avisa. A carona da Steam sozinha tem 218 caracteres
     («Reposta a Opção de Inicialização … Sem ela, no Bluetooth o jogo tende a
     não enxergar controle nenhum»), vem grudada na frase de ativação, e as
     duas passam de 280; a linha de 1.180px a 11px comporta ~200. O que sumia
     era exatamente o *"sem ela, o jogo tende a não enxergar controle nenhum"*.

     AS DUAS LINHAS CONTINUAM FIXAS — o que mudou em 05/09 foi só o repouso.
     Uma tira que crescesse com o tamanho da frase daria um pulo DIFERENTE a
     cada clique, que é a quarta opção que o PO recusou; a altura de ACESA
     continua uma só, 30px, e a frase longa para na segunda linha como antes.

     `-webkit-line-clamp` E NÃO `text-overflow`: a reticência de `text-overflow`
     é de UMA linha só. A janela é um `WebKit2.WebView` e o Chrome da bancada é
     a mesma família, então o prefixo `-webkit-` é o que os dois leem — a mesma
     razão do `::-webkit-slider-thumb` da Prioridade, logo acima.

     A ALTURA E A FOLGA MORAM NA REGRA `.on`, e não na de repouso: é o que faz a
     banda vazia medir zero sem tirar um pixel da tira quando há recado. */
  .desfecho{padding:0 14px;margin-top:0;height:0;line-height:15px;
            font-size:11px;color:var(--green);
            display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
            overflow:hidden;
            visibility:hidden}
  .desfecho.on{visibility:visible;margin-top:7px;height:30px}

  /* ---------- O CADEADO E O PONTO DE ALERTA — decisão [01] do PO ----------
     *"Cadeado no campo, frase no hover."* Sete dos nove perfis de fábrica casam
     por uma regra que o "Funciona em" não sabe descrever (cinco por título de
     janela, dois por lista de classes), e até aqui o seletor ficava IDÊNTICO a
     um destravado: só reclamava DEPOIS do clique. O irmão é o campo do jogo —
     o Pragmata exigia também `PRAGMATA.exe` e a tela mostrava só o número.

     OS DOIS SÃO `.ajuda` POR DENTRO, e isso não é economia de CSS: é o canal de
     hover que esta página JÁ tem (`.ajuda:hover .dica{display:block}`, do
     `topo.html`), o mesmo que o `?` do quadro usa. Inventar um segundo
     mecanismo de dica seria a segunda gramática que esta casa persegue.

     O QUE MUDA É SÓ A CARA: sem a bolinha e sem borda, na cor do alerta. O
     `.ajuda` mede 17px e é `flex:0 0 17px` — aqui vira 13px, para caber ao lado
     de um campo de 30px sem empurrar nada.

     O CADEADO É SVG INLINE, e não um caractere: nenhuma das dez páginas usa
     emoji (medido: zero fora do latim acentuado, do travessão e do `·`), e um
     glifo que depende da fonte do sistema é um glifo que some na máquina
     seguinte. São dois traços — o arco e o corpo —, em `currentColor`, como
     todo glifo de `assets/glyphs/`.

     O PONTO DE ALERTA É UM PONTO, literalmente: `border-radius:50%` de 7px na
     cor laranja. A decisão diz *"ponto de alerta"*, e um ponto é o que ele é.

     OS DOIS NASCEM ESCONDIDOS e o PRODUTO os acende, pelo alvo `classe` — o
     desenho não sabe se a regra deste perfil é travada, e cravar visível faria
     a tela afirmar um cadeado sobre um perfil que não tem nenhum. */
  .campo .trava,.campo .exige{
    display:none;flex:0 0 13px;width:13px;height:13px;position:relative;
    cursor:help;color:var(--orange);align-items:center;justify-content:center}
  .campo .trava.on,.campo .exige.on{display:inline-flex}
  .campo .trava:hover .dica,.campo .exige:hover .dica{display:block}
  .campo .exige::after{content:"";width:7px;height:7px;border-radius:50%;
                       background:currentColor}
  /* A DICA ABRE PARA A ESQUERDA: os dois marcadores moram no fim de um campo
     que já encosta na borda direita do quadro, e uma caixa de 330px a 22px
     para a direita sairia da janela. É a mesma cura que o `.tn-cx .dica` do
     `monta` já faz na aba Conexões. */
  .campo .trava .dica,.campo .exige .dica{left:auto;right:20px;width:300px}

  /* ---------- as QUATRO configurações que cabem dentro deste perfil ----------
     O editor mostrava CINCO campos e gravava vinte, e a única frase que dizia
     isso vivia escondida na dica do "Perfil ativo": *"cada controle guarda a sua
     configuração aqui dentro, pelo ID da peça"*. Com um controle na mesa dava
     para não reparar; com quatro, a tela que promete e não mostra vira a pergunta
     "então o que exatamente eu salvei?".

     Fica no MESMO quadro, embaixo dos campos, separado por uma linha — e não num
     quadro novo: não é outra tela, é o resto DESTE perfil. E é LEITURA: quem
     escolhe o alvo de um ajuste é a fita, que aqui continua esmaecida. */
  .guarda{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden;
          margin-top:7px;padding-top:7px;border-top:1px solid var(--linha)}
  /* `height:100%` na tabela e as quatro linhas dividem a altura que sobra — a
     cura do vão é na ALTURA, nunca `space-between`, que ela reprovou com todas
     as letras. Aqui o vão nem chega a nascer: se sobrar espaço, ele vira altura
     de linha, distribuída igual entre os quatro. */
  .guarda table{height:100%}
  /* A TABELA DE BAIXO É MIÚDA POR CONTA: o que manda no tamanho dela é a altura
     que sobra do editor, e ela tem de caber INTEIRA — quatro linhas e o cabeçalho —
     sem empurrar a fileira de botões nem um pixel. Cada valor aqui foi medido
     contra o `overflow` do quadro, não escolhido. */
  .tab.miuda thead th{padding:5px 8px;background-color:var(--panel);border-bottom:1px solid var(--linha)}

  /* UM FUNDO POR COLUNA — 31/08/2026, pedido dela: *"deixa o background do nome
     das 3 colunas com outras cores, pra diferenciar e ajudar no suspiro ali
     dessa seção"*.
     AS DUAS TABELAS DESTA ABA TÊM TRÊS COLUNAS e são lidas juntas, então as duas
     recebem a mesma escala: 1ª cyan · 2ª roxo · 3ª laranja. Dar a uma só faria a
     outra parecer quebrada — a mesma cicatriz da aba que nasceu sem `Gtk.Frame`
     em 22/08 e foi lida como defeito.
     `color-mix` E NÃO UM HEXADECIMAL DIGITADO: a cor sai das mesmas variáveis da
     casa, então quem trocar a paleta troca isto junto. Baixa o suficiente para o
     fundo separar a coluna sem competir com o dado — o texto continua `--fg` em
     negrito.
     O `padding` subiu de 3 para 5px porque fundo sem respiro é mancha, não faixa:
     é a metade *"suspiro"* do pedido dela. */
  /* A COR VEM COMO `background-image`, E ISSO NÃO É ESTILO — É O QUE IMPEDE UM
     DEFEITO: o cabeçalho é `position:sticky` e a lista de perfis ROLA por baixo
     dele. Uma cor translúcida em `background-color` deixaria os nomes dos perfis
     aparecerem ATRAVÉS do cabeçalho ao rolar. Como `background-image` ela se
     empilha sobre a cor opaca da base (`--elevated` na lista, `--panel` na
     tabela por controle), e o resultado é opaco. */
  .tab thead th:nth-child(1){background-image:linear-gradient(color-mix(in srgb, var(--cyan) 14%, transparent),color-mix(in srgb, var(--cyan) 14%, transparent))}
  .tab thead th:nth-child(2){background-image:linear-gradient(color-mix(in srgb, var(--purple) 20%, transparent),color-mix(in srgb, var(--purple) 20%, transparent))}
  .tab thead th:nth-child(3){background-image:linear-gradient(color-mix(in srgb, var(--orange) 14%, transparent),color-mix(in srgb, var(--orange) 14%, transparent))}
  .tab.miuda td{padding:1px 8px;cursor:default}
  .gd-nome{display:flex;align-items:center;gap:8px;white-space:nowrap;font-size:11px}
  /* O DESENHO DE 32px SAIU, e a barrinha de plástico ficou com o trabalho.
     Ele existia para dizer QUAL controle é a linha, e não dizia: medido em
     28/08 no 1x da tela dela, com os quatro desenhos comparados pixel a pixel,
     o par mais próximo — Cosmic Red × Galactic Purple — se distinguia em
     **33 pixels de 736**, 4,5% do desenho. Os quatro liam como quatro cinzas.

     A causa é que a cor do plástico neste desenho é um TRAÇO, não um
     preenchimento: a 32px o traço vale um terço de pixel e some no
     antisserrilhado. Crescer não estava disponível — a 64px, onde o par pior
     chega a 9,1%, as quatro linhas passam a pedir 209px de altura, e a tabela
     tem 132px (o editor acima já está cheio: sobram 11px até a fileira de
     botões). Um desenho que não cabe no tamanho em que se lê não é escolha de
     layout; é um desenho que esta linha não comporta.

     Quem identifica a peça agora são as duas coisas que JÁ funcionavam e foram
     medidas: a barra de 3px na primeira célula (cor cheia, sem
     antisserrilhado) e o rótulo curto do controle. Se ela quiser o
     desenho de volta, é esta regra e a linha do `svg()` em `linha_do_controle`.

     Foi junto o que o desenho carregava e ninguém via: as cinco lâmpadas do
     jogador mediam **0,5 × 0,2 px** — e vinham com a classe `led-on` CERTA e
     SEM regra que a pintasse, então acesa e apagada tinham o mesmo
     `fill: rgb(107,115,133)`. É o defeito que a `aba04.py` cura com
     `.ctrl .led-on{fill:var(--led-aceso)}` e que esta aba não tinha. */
  /* AS QUATRO SEÇÕES TÊM DE SE LER COMO QUATRO. Com o mesmo vão entre todos os
     glifos, os sete viravam um borrão só e ninguém achava onde a luz acaba e o
     gatilho começa: 2px DENTRO de uma seção, 11px ENTRE elas. */
  .gd-pecas{width:150px}
  .gd-pecas .gls{gap:11px}
  /* aceso = tem ajuste só dele · apagado = usa o do perfil, como os outros */
  /* O APAGADO PASSOU DE `--border-forte` PARA `--comment` — 30/08/2026.
     #44475a sobre o painel dá **1,56:1**: não era glifo apagado, era glifo
     INVISÍVEL — e um estado que não se vê não comunica estado nenhum, só
     ausência. #8896c4 dá 4,89:1 e continua nitidamente mais fosco que o
     aceso (roxo #bd93f9 com o halo do `drop-shadow`), que é o que separa os
     dois. Ela: *"sobe também"*. */
  .gr{display:inline-flex;align-items:center;gap:2px;color:var(--comment)}
  .gr.on{color:var(--purple);filter:drop-shadow(0 0 4px rgba(189,147,249,.45))}
  .gr .gl{vertical-align:-3px}
  .gd-id{width:112px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:10px;
         color:var(--comment)}
  /* A COR DO PLÁSTICO NA BORDA DA LINHA, pela mesma razão do chip da fita: num
     desenho de 32px o modelo mal se distingue, e é a cor que identifica a peça.
     A cor vem de `cor_da_zona()` — do `<style>` que o gerador escreveu no SVG —,
     nunca de um hexadecimal digitado. É a mesma gramática do `tr.ativo` da tabela
     ao lado: uma barra fina à esquerda diz de quem é a linha.

     ELA DEIXOU DE SER `box-shadow` NA CÉLULA — 03/09/2026, IDENTIDADE-VEM-DE-CIMA.
     O `--plastico` morava no `<tr>`, **sem endereço nenhum**, e por isso ficava com
     a cor do DESENHO enquanto o nome ao lado já vinha do aparelho: a linha dizia
     `P1 • White • USB` com a barra do controle do mockup. Agora a barra é um
     elemento PRÓPRIO e endereçado por `guarda.plastico`, e quem escreve a cor é
     o pacote `a10_perfis`, com o que leu da mesa.

     O ENDEREÇO NÃO SE ESCREVE NESTE COMENTÁRIO: a régua do gerador conta as
     ocorrências do atributo na página, e um comentário que o soletra some com a
     conta. (Custou uma reprovação, e ela estava certa.)

     O ALVO É `cor`, E NÃO `fundo`, e a escolha é medida: o `escrever()` do piloto
     guarda `#ae335a` em `style.background` e lê `rgb(174, 51, 90)` de volta —
     a comparação nunca casa e o contador soma uma pintura por tique, para sempre
     (é o defeito que já tirou a `largura` do travessão). O ramo `cor` ESCREVE e
     depois COMPARA, então é o único idempotente para hexadecimal.

     `background:currentColor` COM `color:transparent` NO PADRÃO: sem cor lida, o
     piloto escreve `''`, o inline cai, o `transparent` da classe volta e a barra
     SOME. Campo sem informação não mostra nada — regra dela.

     A CAIXA É A MESMA: `inset 3px 0 0` pinta os 3px da esquerda da caixa de borda
     da célula, e é exatamente o que `position:absolute;left:0;top:0;bottom:0` dá
     num `<td>` posicionado, que não tem borda. Zero pixel de diferença. */
  .tab.miuda td:first-child{position:relative}
  .gd-nome .pl{position:absolute;left:0;top:0;bottom:0;width:3px;
               background:currentColor;color:transparent}
  /* O LUGAR SEM CONTROLE — a cor é a do `.vazio` da Gatilhos (`--comment`), que é
     a página que ela mandou copiar. O contraste está medido no comentário da
     régua: aqui o fundo é `--panel`, não o `--app-bg` da Jogar, e foi por olhar
     só o token — e não o CONTRASTE contra o fundo de CADA aba — que o lugar
     vazio da Jogar saiu mais aceso que o controle na mesa, em 31/08. */
  .tab.miuda tr.fora .gd-nome{color:var(--comment)}
"""

# O CADEADO, EM DOIS TRAÇOS — decisão [01] do PO, 04/09/2026. Ver o bloco
# `.trava` no CSS para a razão de ser SVG e não um caractere. `currentColor` nos
# dois traços é o que deixa a cor morar no CSS, como em todo glifo desta casa.
CADEADO = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
           '<path d="M3.6 5.2V3.9a2.4 2.4 0 0 1 4.8 0v1.3" fill="none" '
           'stroke="currentColor" stroke-width="1.2"/>'
           '<rect x="2.3" y="5.2" width="7.4" height="5.4" rx="1.1" '
           'fill="currentColor"/></svg>')


def marca_com_dica(classe: str, campo_estado: str, campo_frase: str,
                   miolo: str = "") -> str:
    """O cadeado (ou o ponto) que só aparece quando o produto tem o que dizer.

    SÃO DOIS ENDEREÇOS PARA UM FATO, e a divergência é impossível por
    construção: quem os emite é `a10_perfis`, na MESMA linha, do MESMO valor —
    a marca acende quando a frase existe, e some quando ela some. A régua que
    cobra a equivalência é
    `tests/unit/test_a_aba_10_perfis_fecha_as_linhas.py`, e ela morde nos dois
    sentidos (marca sem frase, frase sem marca).

    POR QUE NÃO UM CAMPO SÓ, como o `monta.botao_cinza` faz: aquele elemento é o
    BOTÃO, que já existe na tela e só muda de cor — aqui a marca NASCE ou não
    nasce, e o alvo que a faz nascer (`classe`) é o mesmo que teria de carregar
    a frase (`html`). `data-hef-alvo` é UM por elemento; com um campo só, ou a
    marca aparece sem explicar, ou a explicação existe sem marca que a alcance.

    SEM `data-hef-atributo` JUNTO, e a razão é que o único atributo que caberia
    aqui diria o CONTRÁRIO: o alvo `classe` veste o atributo com `true` quando
    ACENDE, e um `aria-hidden="true"` no instante em que a marca passa a ter o
    que dizer esconderia de quem não enxerga justamente o aviso que nasceu.

    A `.dica` NASCE VAZIA no desenho, de propósito: a frase é DADO (a regra
    daquele perfil, a exigência escondida daquele `match`), e o mockup não tem
    nenhum. Um texto de exemplo aqui viraria a tela afirmando uma regra que o
    perfil dela não tem — a mesma razão do `title=""` da linha da lista.
    """
    return (f'<span class="{classe}" data-hef="{campo_estado}"'
            f' data-hef-alvo="classe">{miolo}'
            f'<span class="dica" data-hef="{campo_frase}"'
            f' data-hef-alvo="html"></span></span>')


#: A FRASE DA PRIORIDADE QUE ELA APROVOU — 02/09/2026, decisão nº11 dela.
#:
#: ELA NUNCA TINHA CHEGADO À TELA, e o motivo era estrutural: o lugar onde ela
#: escreveria é o `<span>` que segura o TRILHO e o NÚMERO, e o pintor termina em
#: `el.textContent = t` — escrever ali apagaria os dois. Por isso
#: `editor.prioridade.dica` vive em `a10_perfis.NAO_PINTAVEIS`, e o que ela lia
#: ao parar o rato era o texto que ficou no desenho, que não é nem a frase velha
#: nem a nova.
#:
#: O PO DECIDIU [03] EM 04/09: **a frase dela entra no DESENHO — e vão as DUAS**,
#: a dela primeiro, seguida da explicação do Universal em zero, que o texto de
#: hoje tem e o dela não. O produto para de tentar mandá-la: a frase é
#: CONSTANTE (`perfis_web._pacote_do_editor` a devolve igual para todo perfil, e
#: está escrito lá que é de propósito), e uma constante mora no desenho.
#:
#: **O LITERAL FICA NUM LUGAR SÓ, e quem o amarra ao produto é uma régua**:
#: `test_a_aba_10_perfis_fecha_as_linhas.py` compara esta constante com o
#: `prioridade_dica` de `perfis_web` e reprova se as duas divergirem. Sem ela,
#: mudar a frase do produto deixaria o desenho recitando a versão velha — que é
#: a forma de defeito que esta seção inteira existe para curar.
FRASE_DA_PRIORIDADE_DELA = (
    "Quando dois perfis servem ao mesmo tempo, o de número maior entra.")
#: A SEGUNDA METADE, que o texto de hoje tem e o dela não. Ela responde a única
#: pergunta que a frase dela deixa aberta — *"e o perfil que vale para tudo,
#: que número tem?"* —, e o PO mandou as duas, nesta ordem.
FRASE_DO_UNIVERSAL = (
    "O Universal fica em zero, para nunca atropelar ninguém e nunca deixar o "
    "controle sem nada.")
DICA_DA_PRIORIDADE = f"{FRASE_DA_PRIORIDADE_DELA} {FRASE_DO_UNIVERSAL}"

AMBIENTES = ["Todos","Steam","Estilo de Jogo","Jogo","Jogo da Steam"]
#: OS RÓTULOS SAEM DO MOTOR — ver o comentário do import, no alto. Eram quinze
#: palavras digitadas aqui, e a coincidência com o motor não era construção.
ESTILOS = [e.rotulo for e in ESTILOS_DO_MOTOR]
PERFIS = [("Mortal Kombat", 90, "Jogo · mk1.exe", True),
          ("Elden Ring", 85, "Jogo da Steam · 1245620", False),
          ("Orpheus", 82, "Jogo · mgba", False),
          ("Pragmata", 80, "Jogo da Steam · 1358160", False),
          ("Don't Scream", 78, "Jogo da Steam · 2380050", False),
          ("Reanimal", 76, "Jogo · reanimal.exe", False),
          ("Faith", 74, "Jogo · faith.exe", False),
          ("Wendigo Blue", 72, "Jogo · wendigo.exe", False),
          ("Duskfade", 70, "Jogo · duskfade.exe", False),
          ("Mina the Hollower", 68, "Jogo · mina.exe", False),
          ("Terror (os dez)", 60, "Estilo de Jogo · Terror", False),
          ("Luta", 58, "Estilo de Jogo · Luta", False),
          ("Navegação", 40, "Todos — 4 disputam", False),
          ("Universal", 0, "Todos — quando nenhum casa", False)]

#: A PRIORIDADE DO PERFIL QUE O EDITOR DO DESENHO ABRE — o primeiro da lista.
#: Ela é o número ao lado do trilho E a largura do cheio, e os dois saem daqui
#: em vez de serem digitados: enquanto o `90` era escrito duas vezes, a barra
#: cravava `width:90%` e a legenda dizia `90` — o que só fecharia se o teto
#: fosse 100. O teto é 200 (`schema.PRIORIDADE_MAXIMA`), então a barra do
#: desenho anunciava "quase no máximo" um perfil que está em 90 de 200.
PRI_DO_DESENHO = PERFIS[0][1]
#: O PERFIL QUE O EDITOR DO DESENHO ABRE, pelo NOME — e é o mesmo primeiro da
#: lista de onde sai o `PRI_DO_DESENHO` logo acima. Ele existe para a linha da
#: esquerda e o editor da direita nunca discordarem: marcar `Elden Ring` como
#: escolhido enquanto o editor mostra a prioridade do `Mortal Kombat` seria o
#: desenho afirmando que há dois perfis abertos ao mesmo tempo.
#:
#: E O DESENHO MOSTRA O ESTADO COMBINADO de propósito — `ativo` E `escolhido` na
#: mesma linha —, porque é o estado em que a aba ABRE: `a10_perfis._escolhido`
#: sincroniza o escolhido com o ativo enquanto ela não clicou em nada. Os outros
#: dois estados (só ativo, só escolhido) nascem do CLIQUE, e quem os prova é
#: `tests/unit/test_a10_a_linha_escolhida_tem_marca.py` — um desenho estático não
#: tem como mostrar os três sem inventar uma tela que o produto nunca produz.
PERFIL_DO_EDITOR = PERFIS[0][0]
#: E A LARGURA É A CONTA, não um número: a mesma que
#: `perfis_web._pacote_do_editor` faz para o produto.
PCT_DO_DESENHO = round(PRI_DO_DESENHO * 100 / PRIORIDADE_MAXIMA)

#: O VALOR QUE O `escrever()` DO PILOTO MANDA quando não há o que mostrar. Ele
#: troca vazio por este travessão ANTES de escolher o ramo, e é por isso que ele
#: precisa EXISTIR como opção: um `<select>` só aceita o que ele oferece.
TRAVESSAO = "—"


def opts(lista, escolhido, vazio=False, travessao=False):
    """As opções de um `<select>` do desenho.

    `travessao=True` põe na frente a opção `—`, DESABILITADA — e ela é a cura de
    uma tela que afirmava o que não é, medida no DOM vivo em 04/09/2026.

    O QUE ACONTECIA, e é o irmão exato do defeito que o cadeado veio marcar: um
    perfil que casa por título de janela vem de `perfis_web` com
    `ambiente: None`. O `escrever()` do piloto troca `None` por `—`, e num
    `<select>` ele só escreve se alguma opção CASAR — nenhuma casava, então ele
    devolvia 0 e **o campo ficava com o "Jogo" do MOCKUP**. Medido, com o
    cadeado já aceso ao lado:

        trava.acesa      true        ← "esta tela não sabe mostrar a regra"
        editor.ambiente  "Jogo"      ← o desenho, afirmando uma regra que não é

    O cadeado dizia a verdade e o campo ao lado dizia outra, na mesma linha.

    `value="—"` E NÃO `value=""`: com o valor vazio, `el.value = '—'` não casa
    nada (a atribuição olha o VALUE, não o texto), o `selectedIndex` cai para
    -1, o campo renderiza EM BRANCO e — porque `el.value` nunca volta igual ao
    escrito — o contador de pinturas soma +1 por tique, para sempre. É a
    medição que segura o `editor.estilo` em `NAO_PINTAVEIS`, e aqui ela é o que
    escolhe o valor. Com `value="—"` a escrita é idempotente.

    `disabled` PORQUE ELA NÃO É UMA ESCOLHA: "não sei mostrar" é um estado que o
    produto relata, não uma regra que o perfil saiba guardar. Se ela pudesse
    escolhê-lo, o gesto recusaria dizendo (`editor_ambiente` levanta para todo
    rótulo fora de `PRESET_DO_ROTULO`) — melhor não oferecer.

    `vazio=True` põe NA FRENTE a opção que ela decidiu em 02/09/2026:
    `value=""`, texto travessão, marcada — e aí nenhuma das outras nasce
    marcada. Sem ela o "Estilo de Jogo" abria em `Luta` para os 33 perfis dela,
    um valor que ninguém escreveu: o perfil não tem campo de Estilo
    (`perfis_web` devolve `estilo: None`), e a pintura não alcança um `<select>`
    com valor vazio — ver `a10_perfis.NAO_PINTAVEIS`. É a regra dela dita no
    mesmo dia, *"campo sem informação não mostra nada"*, aplicada ao desenho.
    """
    linhas = []
    if vazio:
        linhas.append('                <option value="" selected>—</option>')
    if travessao:
        linhas.append(f'                <option value="{TRAVESSAO}" disabled>'
                      f'{TRAVESSAO}</option>')
    linhas += [f'                <option{" selected" if (o == escolhido and not vazio) else ""}>{o}</option>'
               for o in lista]
    return "\n".join(linhas)


def linha_do_controle(c, tem=None, id_da_peca=None, uniq=None):
    """Uma linha da tabela de baixo: o controle, o que é só dele, e o ID da peça.

    O rótulo é o encurtado — `P1 • Cosmic Red • USB` —, na ordem dela de 26/08:
    marca • player • plástico • transporte, sem a marca onde aperta. O mesmo
    rótulo do chip da fita, para os dois nunca discordarem.

    E agora ele SAI DE `monta.rotulo(c, "curta")`, não daqui. O texto era montado
    à mão nesta função com os mesmos três campos e o mesmo separador — igual ao
    do chip por coincidência, não por construção. Duas cópias da mesma gramática
    concordam até o dia em que uma muda; a fita já tinha morrido em silêncio
    assim, quando o texto do chip mudou e a âncora que o procurava deixou de
    casar. Uma fonte só, e as duas mudam juntas.

    OS TRÊS PARÂMETROS NASCERAM EM 29/08/2026, e nenhum deles muda um pixel do
    mockup: os três caem nos `GUARDA`/`ID_DA_PECA` fixos quando ninguém os passa.
    Eles existem porque a aba VIVA (`perfis_vivos.py`) usa este gerador como
    BIBLIOTECA — o que o perfil dela guarda por controle é dado de tempo de
    EXECUÇÃO, e a mesa também. Reproduzir esta linha à mão no piloto criaria a
    segunda verdade sobre o desenho, que é o defeito que esta casa mais paga.
    """
    na_mesa = c.get("conectado", True)
    tem = GUARDA[c["pref"]] if tem is None else tem
    id_visivel = ID_DA_PECA[c["pref"]] if id_da_peca is None else id_da_peca
    endereco = uniq if uniq is not None else c["pref"]
    grupos = []
    # SEM `title=` NA CÉLULA — decisão dela nº4, 03/09/2026. Ver o bloco do
    # `SECOES`. O `data-hef-alvo="classe"` é o que deixa o PRODUTO acender e
    # apagar esta célula: sem ele o pintor cai no ramo do texto e o
    # `textContent` apaga o glifo SVG que mora dentro do `<span>`.
    for campo, pecas in SECOES:
        on = campo in tem
        gs = "".join(glifo(p, ativo=on, tam=15) for p in pecas)
        grupos.append(f'<span class="gr{" on" if on else ""}" data-hef="guarda.secao"'
                      f' data-hef-alvo="classe" data-hef-secao="{campo}">{gs}</span>')
    # O LUGAR DE QUEM NÃO ESTÁ NA MESA — 31/08/2026, decisão dela, e ela vale para
    # TODA página que eu tocar: *"o espaço fica, mas o nome do canto muda: agora o
    # p3 e o p4 será P3 bolinha Desconectado, igual página gatilhos"*.
    #
    # O TEXTO COPIA A GATILHOS — `P3 • Desconectado`, com o mesmo `SEPARADOR` que
    # todo rótulo desta casa usa. Não é o rótulo curto com campos vazios: um lugar
    # sem controle não tem plástico nem transporte para mostrar, e inventar um
    # travessão em cada campo diria que ali FALTA dado, quando o que falta é o
    # controle.
    #
    # O QUE FICA ACESO, e é a decisão dela de mais cedo: o que o PERFIL guarda
    # daquela peça, e o ID. O perfil guarda por ID da peça, que é estável entre
    # cabo e rádio — logo ele conhece o P3 mesmo com o P3 fora da mesa, e apagar
    # isso apagaria a resposta à pergunta que a tabela existe para responder.
    #
    # A BARRA DA COR DO PLÁSTICO SAI. Ela identifica a peça que está ali; sem
    # peça, ela afirmaria uma cor que ninguém pode conferir na tela.
    #
    # ELA MORA NUM ELEMENTO PRÓPRIO E ENDEREÇADO desde 03/09/2026
    # (IDENTIDADE-VEM-DE-CIMA): o `--plastico` estava no `<tr>`, sem endereço, e
    # a linha ficava com a cor do DESENHO enquanto o `guarda.nome` ao lado já
    # trazia o aparelho — a fita dizia `P1 · White · USB` e a barra continuava
    # vermelha. Quem escreve `guarda.plastico` é `pacotes/a10_perfis.py`; o valor
    # daqui é só o desenho, e o produto o cobre no primeiro tique.
    # A DICA DA LINHA NÃO NOMEIA MAIS O APARELHO — 03/09/2026, e é a MESMA lei
    # da barra logo acima, aplicada ao único lugar desta aba que ela ainda não
    # tinha alcançado.
    #
    # O QUE ESTAVA NA TELA DELA, medido em 03/09 com P1 White no cabo e P2
    # Galactic Purple no rádio: a primeira célula da linha dizia
    # `P1 • White • USB` — viva, pelo `guarda.nome` — e o `title` da MESMA linha
    # respondia `Cosmic Red — 4 de 5 ajustes só deste controle.` As duas metades
    # da frase eram do desenho, e as duas estavam erradas: o perfil dela guarda
    # ZERO ajustes por controle, e o painel ao lado já dizia `0 de 2`.
    #
    # POR QUE NÃO SE PINTA, e é estrutural: o `escrever()` do piloto e o
    # `LER_CAMPOS` conhecem os alvos `texto`, `largura`, `valor`, `cor` e
    # `classe`, e nenhum deles escreve ATRIBUTO. O alvo `atributo` que nasceu
    # nesta leva também não alcança: a guarda `atributo_escrevivel` só aceita
    # nome `data-*`/`aria-*`, e `title` fica de fora por construção — a razão
    # dela é o selo `data-hef-visto`, que decide medição desta casa. Um `title`
    # emitido pelo gerador é, portanto, congelado no arquivo para sempre.
    #
    # TIRAR É A CURA, E NÃO PERDE NADA: o modelo está na PRÓPRIA célula que o
    # cursor toca (`guarda.nome`, vivo) e a conta está na coluna ao lado
    # (`guarda.secao`, alvo `classe`, vivo, uma célula por seção). A dica só
    # repetia — errado — o que a linha já mostra certo. É a decisão nº4 dela
    # deste mesmo dia, sobre esta mesma tabela: *"Meu Deus melhor nenhuma assim.
    # Auto falante é auto falante, gatilho é gatilho."*
    #
    # A DICA DO LUGAR VAZIO FICA, e a assimetria é o ponto: `P3` é um LUGAR, não
    # uma peça. Aquela frase não afirma nada sobre aparelho nenhum, então não
    # envelhece quando a mesa muda — é o oposto exato do que saiu daqui.
    nome = rotulo(c, "curta") if na_mesa else f'P{c["jogador"]}{SEPARADOR}Desconectado'
    plastico = cor_da_zona(c['cor']) if na_mesa else "transparent"
    dica = ("" if na_mesa else
            f'\n                      title="Nenhum controle neste lugar. O perfil '
            f"guarda o que está aqui pelo ID da peça: quando o P{c['jogador']} "
            f'voltar, ele encontra o que você deixou."')
    return f'''                  <tr data-hef-uniq="{endereco}"{'' if na_mesa else ' class="fora"'}{dica}>
                    <td class="gd-nome">
                      <span class="pl" data-hef="guarda.plastico" data-hef-alvo="cor"
                            style="color:{plastico}"></span>
                      <span data-hef="guarda.nome">{nome}</span>
                    </td>
                    <td class="gd-pecas"><span class="gls">{"".join(grupos)}</span></td>
                    <td class="gd-id" data-hef="guarda.id">{id_visivel}</td>
                  </tr>'''


def linha_do_perfil(nome, prioridade, quando, ativo, dica="", escolhido=False):
    """Uma linha da lista de perfis salvos — a MESMA para o mockup e para a viva.

    Ela era uma compreensão de lista embutida no `MIOLO`; virou função pelo mesmo
    motivo da `linha_do_controle`: a aba viva precisa do desenho, não de uma
    cópia dele. O `title` nasce vazio no mockup porque a dica é a DISPUTA, e
    disputa é dado — o mockup não tem nenhum, e um texto inventado aqui viraria
    a tela afirmando uma disputa que não existe.

    O ENDEREÇO DO CLIQUE MORA NA CÉLULA DO NOME, e não na `<tr>` — 01/09/2026,
    ao ligar os botões. A razão é medida, e são duas:

    1. **O ouvinte do piloto não enxerga a linha.** Ele casa
       `[data-gesto],[data-hef-gesto],[data-papel],…` (`hefesto_vivo.py:190`), e
       a `<tr>` só tinha `data-hef-perfil`, que não está na lista. Clicar num
       perfil não mandava nada a lugar nenhum.
    2. **O nome VIVO só existe na célula.** O clique leva
       `texto: alvo.textContent` — na `<tr>` isso seria "Ação90Jogo", os três
       campos colados; na célula é o nome, e é o nome que o `profile.switch`
       quer. E o `data-hef-perfil` da linha é do MOCKUP: a pintura escreve o
       texto das células e nunca reescreve o atributo, então quem lesse o
       atributo leria o perfil do desenho, não o do disco.

    `data-hef-gesto` e não `data-gesto`: esta aba já tem 77 endereços nesse
    vocabulário, e o despachante aceita os três — inventar um quarto aqui seria
    a segunda verdade que esta casa persegue.

    `escolhido` É A LINHA ABERTA NO EDITOR, e não o perfil que está valendo —
    04/09/2026, queixa dela: *"quando clica em algum nome do perfis salvos nada
    indica que tal coisa tá selecionado"*. Ele sai em `aria-selected` e não numa
    segunda classe; a razão inteira está no CSS, junto das três regras que o
    leem.

    ELE É SEMPRE EMITIDO, `true` ou `false`, e não só quando é verdade: o
    `blocos` do piloto compara a MINHA string com a serialização que o navegador
    devolve, e um atributo que aparece e desaparece muda o comprimento da linha
    a cada clique. Um valor constante no lugar constante é o que deixa o
    `<tbody>` assentar.
    """
    return (f'                <tr class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{nome}" '
            f'aria-selected="{"true" if escolhido else "false"}" title="{dica}">'
            f'<td data-hef="perfis.linha.nome" data-hef-gesto="selecionar">{nome}</td>'
            f'<td class="pri" data-hef="perfis.linha.prioridade">{prioridade}</td>'
            f'<td class="quando" data-hef="perfis.linha.quando">{quando}</td></tr>')


COM_AJUSTE = sum(1 for c in MESA if GUARDA[c["pref"]])

MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo">Perfis</span>
        <!-- A DICA DO QUADRO ENCOLHEU — 30/08/2026, pedido dela: *"olha esse tooltip
             quilométrico. ao invés de estar tudo em Perfis deveria estar em cada
             seção"*. Ela estava certa por dois motivos: o bloco tinha quatro
             parágrafos e cobria meia tela ao abrir, e cada assunto dele JÁ tinha
             dono na tela — Prioridade, Estilo de Jogo e a tabela por controle têm
             `title` próprio, a poucos pixels de onde a pessoa está olhando.
             Aqui fica só o que nenhum campo diz: o que É um perfil. -->
        <span class="ajuda">?<span class="dica">
          Um perfil guarda <b>tudo</b> o que você ajustou nas outras abas — gatilho, luz,
          vibração, som, sensores e máscara — e o traz de volta quando aquele jogo abre.
        </span></span>
        <span class="conta"><span data-hef="perfis.conta">{len(PERFIS)} perfis</span> <span class="sep">·</span>
          <span data-hef="perfis.com-ajuste">{COM_AJUSTE} de {len(MESA)} controles com ajuste próprio neste perfil</span></span>
      </div>
      <!-- O DESFECHO DO ÚLTIMO GESTO — ver `.desfecho` no CSS para a razão.
           SÃO DOIS ENDEREÇOS PARA UM VALOR, e não é redundância: a CAIXA usa o
           alvo `classe` (acende a tira quando há notícia — o `ligado()` do
           piloto lê o travessão do campo vazio como APAGADO) e o TEXTO de
           dentro escreve a frase. É o mesmo par que a coluna "Ajuste próprio"
           já usa, e é o que faz a tira sumir sozinha quando o desfecho vence os
           trinta segundos, em vez de deixar um "—" pendurado na tela dela.

           E NÃO SE ESCREVE A TAG DE CAIXA POR EXTENSO NESTE COMENTÁRIO: o
           balanço do `monta` conta SUBSTRING no documento inteiro, comentário
           incluído, e uma abertura solta aqui derruba o gerador com
           "desbalanceado". Custou duas execuções; fica escrito. -->
      <div class="desfecho" data-hef="perfis.desfecho" data-hef-alvo="classe"><span data-hef="perfis.desfecho"></span></div>
      <div class="quadro-corpo">
        <div class="perfis">

          <div>
            <div class="moldura">
              <div class="sec-rot">Perfis Salvos</div>
              <div class="lista">
              <div class="rolo">
              <table class="tab">
                <thead><tr><th>Nome</th><th class="pri">Priorização</th><th>Quando usar</th></tr></thead>
                <tbody data-hef="perfis.lista">
{chr(10).join(linha_do_perfil(n, p, q, a, escolhido=n == PERFIL_DO_EDITOR) for n,p,q,a in PERFIS)}
                </tbody>
              </table>
              </div>
              </div>
              <div class="botoes">
                <button class="btn verde" data-hef-gesto="ativar" title="Passa a usar este perfil agora, em todas as abas.">Ativar</button>
                <button class="btn" data-hef-gesto="novo" title="Perfil em branco, já com a regra do jogo aberto agora — venha ele de onde vier.">Novo</button>
                <button class="btn vermelho" data-hef-gesto="remover" data-hef="perfis.remover" title="Apaga do disco. Pergunta antes.">Remover</button>
              </div>
            </div>
          </div>

          <div>
            <div class="moldura">
              <!-- OS QUATRO CAMPOS DESTE BLOCO PEDEM `data-hef-alvo="valor"`, e sem ele
                   o editor era a única parte da tela que MENTIA sozinha. Medido em
                   01/09/2026, num Chrome de verdade, injetando o `BOOTSTRAP` do piloto
                   sobre o `src/hefesto_dualsense4unix/interface/paginas/10-perfis.html` publicado (`hefesto_vivo.py:100-115`):

                     editor.ambiente   5 opções → 0     `select.textContent = "Jogo da
                     editor.estilo    15 opções → 0      Steam"` APAGA a lista inteira
                     editor.nome      value fica "Mortal Kombat"   ← o do MOCKUP
                     editor.jogo      value fica "Mortal Kombat 1" ← o do MOCKUP

                   Nos dois `<select>` o estrago é destrutivo: a primeira pintura
                   esvazia o campo de escolha e ele não volta. Nos dois `<input>` é
                   invisível: `textContent` num campo de texto não aparece, então a
                   tela seguia mostrando o jogo do desenho qualquer que fosse o perfil.
                   É a mesma cura que a aba Gatilhos já tinha aplicado nos seus cinco
                   `<select>` (`aba03.py:502`).

                   E É O QUE TORNA OS GESTOS HONESTOS: sem isto, ligar o campo Nome
                   faria ela renomear um perfil olhando para o nome de outro. -->
              <div class="sec-rot">Definições</div>
              <div class="campos">

              <div class="campo">
                <span>Nome:</span>
                <span class="val"><input type="text" data-hef="editor.nome" data-hef-gesto="editor.nome"
                       data-hef-alvo="valor" value="Mortal Kombat"></span>
              </div>
              <div class="campo">
                <span>Prioridade:</span>
                <span class="val" data-hef="editor.prioridade.dica" title="{DICA_DA_PRIORIDADE}">
                  <!-- `data-hef-alvo="largura"` — 02/09/2026, e sem ele a barra
                       MENTIA de duas formas ao mesmo tempo. O pintor cai no
                       ramo padrão (`el.textContent = t`, `hefesto_vivo.py:170`)
                       quando o alvo não é declarado: o `"0%"` que o pacote
                       manda vira TEXTO dentro de uma barra de 5px, e a
                       LARGURA fica nos 90% do desenho — uma barra quase cheia
                       para um perfil que está em 1 de 200.
                       É a mesma cura que os quatro campos do editor logo
                       abaixo já tinham recebido com `alvo="valor"`.
                       FATO SUBSTITUÍDO — 02/09/2026. Aqui estava escrito que,
                       "enquanto esta página não for PUBLICADA por ela",
                       `a10_perfis.NAO_PINTAVEIS` segurava a emissão do
                       `editor.prioridade`. As duas metades caíram: a página FOI
                       publicada (commit `70b58116`) e `editor.prioridade` saiu
                       de `NAO_PINTAVEIS` no `1f6e356b`. A barra recebe a
                       largura; o número ao lado (`editor.prioridade.n`) é um
                       `<span>` sem filhos e recebe o valor pelo mesmo tique. -->
                  <!-- O `<input type=range>` — 03/09/2026, e é o que fez este
                       campo deixar de ser leitura. Ele fica DENTRO do trilho,
                       absoluto e transparente: o desenho que ela aprovou
                       continua sendo o trilho + o cheio, e o range só empresta
                       o punho e o arrasto.
                       `min`/`max` SAEM DO ESQUEMA (`PRIORIDADE_MINIMA`/`MAXIMA`)
                       — ver o comentário do import. `step="1"` porque
                       `Profile.priority` é `int`: um slider que oferecesse
                       meio número faria a tela prometer o que o esquema recusa.
                       O ENDEREÇO É PRÓPRIO (`editor.prioridade.escolha`) e não
                       o `.n` do vizinho: o pacote pinta este UMA VEZ por perfil
                       escolhido (ver `a10_perfis.CAMPOS_QUE_ELA_DIGITA`) para
                       não devolver o punho ao valor do disco no meio do arrasto
                       dela, enquanto o número ao lado continua repintando a
                       cada tique. -->
                  <span class="trilho"><span class="cheio" data-hef="editor.prioridade" data-hef-alvo="largura" style="width:{PCT_DO_DESENHO}%"></span><input type="range" class="desliza" min="{PRIORIDADE_MINIMA}" max="{PRIORIDADE_MAXIMA}" step="1" value="{PRI_DO_DESENHO}" aria-label="Prioridade" data-hef="editor.prioridade.escolha" data-hef-alvo="valor" data-hef-gesto="editor.prioridade"></span>
                  <span class="n" data-hef="editor.prioridade.n">{PRI_DO_DESENHO}</span>
                </span>
              </div>
              <!-- O CADEADO — decisão [01] do PO, 04/09/2026: *"Cadeado no
                   campo, frase no hover."* Sete dos nove perfis de fábrica
                   casam por uma regra que este seletor não sabe descrever, e
                   até aqui ele ficava IDÊNTICO a um destravado: a marca de
                   travado e a frase que a explica já saíam do produto
                   (`perfis_web._ambiente_do_perfil`) e caíam no vazio, porque
                   endereço para elas não existia nesta página. Só depois do
                   clique é que a tela reclamava. -->
              <div class="campo">
                <span>Funciona em:</span>
                <span class="val"><select data-hef="editor.ambiente" data-hef-gesto="editor.ambiente" data-hef-alvo="valor">
{opts(AMBIENTES, "Jogo", travessao=True)}
                </select>{marca_com_dica("trava", "editor.ambiente.travado",
                                        "editor.ambiente.recado", CADEADO)}</span>
              </div>
              <!-- O PONTO DE ALERTA — a outra metade da mesma decisão. O caso
                   é o do Pragmata: o editor mostrava "Jogo da Steam · 3357650"
                   e o arquivo exigia TAMBÉM `PRAGMATA.exe`; o `matches` é AND,
                   o campo invisível era o que decidia, e o perfil não entrava
                   sozinho — medido seis vezes em dois minutos com ela jogando.
                   A frase que conta isso já existia
                   (`simple_match.exigencia_invisivel`) e nunca tinha chegado a
                   esta tela. -->
              <div class="campo">
                <span>Nome do Jogo:</span>
                <span class="val">
                  <input type="text" data-hef="editor.jogo" data-hef-gesto="editor.jogo"
                         data-hef-alvo="valor" value="Mortal Kombat 1">{marca_com_dica(
                           "exige", "editor.jogo.exige", "editor.jogo.exigencia")}
                  <button class="btn roxo" data-hef-gesto="detectar" title="Pega o jogo que está rodando atrás desta janela e monta a regra — funciona com jogo de qualquer lugar, não só da Steam.">Detectar</button>
                </span>
              </div>
              <div class="campo">
                <span title="Pré-aplica um perfil inteiro: escolhendo FPS, o gatilho, a luz, a vibração e a máscara já vêm resolvidos. Os catorze de fábrica não se editam; o Personalizado usa o que você ajustou nas abas.">Estilo de Jogo:</span>
                <span class="val"><select class="destaque" data-hef="editor.estilo" data-hef-gesto="editor.estilo" data-hef-alvo="valor">
{opts(ESTILOS, "", vazio=True)}
                </select></span>
              </div>

              <div class="guarda">
                <table class="tab miuda">
                  <thead><tr>
                    <th title="O perfil não guarda uma configuração: guarda uma por controle. Esta tabela mostra, para cada controle, quais ajustes ele tem só para si e quais usa do perfil.">Controle</th>
                    <th class="gd-pecas" title="Aceso: este perfil guarda um ajuste só deste controle. Apagado: ele usa o do perfil, igual aos outros. São os {QUANTAS_SECOES} ajustes que o perfil sabe guardar por controle — {_lista_das_secoes()}.">Ajuste próprio</th>
                    <th class="gd-id" title="O endereço de rádio do controle. É por ele que o perfil reconhece a peça — e ele não muda quando você troca o cabo pelo rádio, então o que você deixou hoje volta amanhã.">ID da peça</th>
                  </tr></thead>
                  <tbody data-hef="guarda.linhas">
{chr(10).join(linha_do_controle(c) for c in MESA)}
                  </tbody>
                </table>
              </div>

              </div>
              <div class="botoes">
                <button class="btn" data-hef-gesto="duplicar" title="Copia o perfil inteiro para o editor, com &quot;(cópia)&quot; no nome.">Duplicar</button>
                <button class="btn" data-hef-gesto="voltar-a-de-ontem" title="Desfaz um perfil salvo por engano: cada gravação já guarda a anterior.">Voltar à de ontem</button>
                <button class="btn" data-hef-gesto="recarregar" title="Relê a lista do disco. Não descarta o que está no editor ao lado.">Recarregar</button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
'''

# A LINHA DA MÁSCARA AUTOMÁTICA SAIU DA LEGENDA — 29/08/2026.
#
# A lista "O que estava no código e nunca teve tela" anunciava, como entrega
# desta aba: «A máscara "Automático" — o produto lê a API de entrada do
# executável e decide por jogo, em vez de você escolher no escuro». Ela decidiu
# em 29/08 que essa quarta opção SAI, e a razão é a medição: a heurística que a
# moveria (`integrations/api_de_entrada.py:12-49`) erra em 13 dos 14 jogos do
# censo dela. Um automatismo que erra quase sempre é PIOR que escolher à mão,
# porque erra em silêncio — quem escolhe errado sabe que escolheu.
#
# ERAM DOIS MOCKUPS APROVADOS DISCORDANDO, e por isso isto não é ajuste de
# texto: a aba Jogar já dizia o contrário (`src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:2311` e
# `:2321` — "sem Automático", com a medição junto) enquanto esta ainda o
# anunciava como entrega. A Jogar venceu, palavra dela. A decisão antiga
# (`D-A-MASCARA-GANHA-O-AUTOMATICO`, 26/08) continua em
# `docs/data/decisoes-dela.csv` com a lápide datada de 29/08 — nesta casa não se
# apaga decisão medida, e quem for executar precisa saber por que a de 26/08
# caducou em vez de tropeçar nela.
#
# O QUE NÃO SAIU, E É DE PROPÓSITO: a palavra "máscara" continua nas duas dicas
# do quadro Perfis (o que o perfil guarda; o que o Estilo de Jogo pré-aplica). A
# máscara existe e o perfil a guarda — com TRÊS opções (DualSense · Xbox 360 ·
# Nintendo Pro). O que morreu foi a quarta, não a máscara.
#
# Este comentário fica no gerador, e não como `<!-- -->` no HTML, de propósito:
# um comentário HTML manteria a palavra viva no mockup e faria o `grep` do
# mockup continuar acusando o que já saiu.
LEGENDA = f'''<div class="nota">
  <h2>O que mudou com quatro controles na mesa</h2>
  <ul>
    <li><b>O editor mostrava cinco campos e gravava vinte.</b> A tabela de baixo mostra o
      resto: <span class="marca">"cada controle guarda a sua configuração aqui dentro, pelo
      ID da peça"</span> era uma promessa que só existia na dica do <b>Perfil ativo</b>. Agora
      ela está desenhada, e são <b>{len(MESA)} configurações dentro do mesmo perfil</b>.</li>
    <li><b>Os {QUANTAS_SECOES} ajustes da linha não são escolha minha.</b> São os campos de
      <code>ControllerOverrides</code> — {_lista_das_secoes()} —, nem um a mais.
      O <b>microfone</b> entrou por decisão dela em 03/09 e os <b>sensores</b> em 04/09,
      quando o giroscópio e o acelerômetro passaram a desligar de verdade por peça
      (<code>manager.apply_controller_sensores</code>). A lista da tela sai da mesma
      ordem do esquema: um campo novo lá aparece aqui, em vez de ficar guardado no
      disco e invisível na tabela. Modo, mouse e teclado continuam sendo do
      perfil inteiro, e a classe escreve o motivo de cada um.</li>
    <li><b>Apagado não é falta, é herança.</b> Campo vazio quer dizer "sem opinião": aquele
      controle usa a seção global do perfil. O <b>P4</b> está assim de propósito —
      é o caso mais comum, e uma tela que acende tudo nos quatro ensinaria o contrário.</li>
    <li><b>O desenho do controle saiu da linha, e a cor ficou.</b> Ele tinha 32px e
      <span class="marca">os quatro liam como quatro cinzas</span>: medido no 1x desta tela,
      o par de cores mais próximo se distinguia em <b>33 pixels de
      736</b>. A cor do plástico aqui é um traço fino, e a 32px o traço vale um terço de
      pixel. Crescer não cabia: no tamanho em que a cor se lê, as quatro linhas pedem 209px
      de altura e a tabela tem 132px. Quem diz de quem é a linha agora é a <b>barra de 3px
      na cor do plástico</b> e o <b>rótulo curto</b> do controle — os dois já estavam lá.
      A cor continua saindo do <code>&lt;style&gt;</code> que o
      <code>gerar_cores_do_dualsense.py</code> escreveu, por <code>cor_da_zona()</code>:
      <b>nenhum hexadecimal digitado aqui</b>. Os glifos são os mesmos
      <code>assets/glyphs/</code> das outras abas.</li>
    <li><b>A barra e o rótulo dizem o controle DELA, não o do desenho.</b> A barra virou um
      elemento endereçado (<code>guarda.plastico</code>) e quem escreve a cor é
      <code>a10_perfis</code>, com o que leu da mesa — a mesma leitura da fita do topo.
      Sem cor lida, a barra <b>some</b>: campo sem informação não mostra nada.</li>
    <li><b>O cabeçalho conta a mesa</b>: {len(PERFIS)} perfis e
      {COM_AJUSTE} de {len(MESA)} controles com ajuste próprio neste perfil.</li>
    <li><b>A linha diz DUAS coisas, e elas não são a mesma.</b> A <b>cor verde e a barra
      verde</b> dizem <b>está valendo agora</b>; o <b>fundo roxo e a barra roxa</b> dizem
      <b>é esta que o editor ao lado está mostrando</b> — a que os nove botões vão mexer.
      Quando são a mesma linha, a barra vem <b>dupla</b>: verde e roxa, lado a lado. É o
      estado desenhado aqui, porque é o estado em que a aba abre.
      <span class="marca">Antes disto, clicar num nome não mudava um pixel</span> — palavra
      sua: "quando clica em algum nome do perfis salvos nada indica que tal coisa tá
      selecionado".</li>
  </ul>

  <h2>O que você mandou tirar, e continua fora</h2>
  <ul>
    <li><b>"◆ 2 perfis nunca vão entrar — veja quais"</b>, com o <b>?</b> — fora.</li>
    <li><b>"Salvar este perfil"</b> — fora.</li>
    <li><b>"Esconder os controles físicos neste jogo"</b> — fora.</li>
    <li><b>"◆ este jogo já sabe por onde entra"</b> — fora: <span class="marca">isso está na aba Jogar</span>, palavra sua.</li>
  </ul>

  <h2>O que estava no código e nunca teve tela</h2>
  <ul>
    <li><b>Os ajustes por controle</b> — <code>Profile.controllers</code> existe desde
      16/07 e gravava calado: nenhuma tela dizia quais controles têm ajuste próprio.
      Era a pergunta <b>4</b> do contrato desta aba, e a tabela é a resposta.</li>
    <li><b>"Voltar à de ontem"</b> — cada gravação já guarda a anterior e nenhuma tela oferecia isso (<code>profiles/loader.py:1224</code>).</li>
    <li><b>"Detectar"</b> — abra o jogo de onde for, volte e clique; o perfil nasce com a regra certa.</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>"Modo que liga" e "O jogo vê o controle como" não estão desenhados aqui.</b>
      <span class="marca">A legenda anterior dizia que ficaram, e era falso</span> — nenhum dos
      dois estava na tela. Eles moram hoje na <b>Jogar</b>; se vêm também para cá, é decisão
      sua, e a tela não decide por você.</li>
    <li><b>O conteúdo dos Estilos de Jogo</b> continua em aberto: a lista está aqui, o que
      cada um liga não.</li>
    <li><b>A tabela é leitura</b>, como a fita esmaecida diz. Se você quiser mudar o ajuste de
      um controle a partir daqui — em vez de ir à aba da peça com aquele controle escolhido
      na fita —, isso é tela nova, e eu não a inventei.</li>
  </ul>
</div>

</body>
</html>
'''

def _conferir(html: str) -> None:
    """Lê o HTML que acabou de sair e reprova se uma decisão dela cair.

    O QUE ELA MEDE, E O QUE NÃO: ela lê o CSS escrito, não a tela pintada — o
    gerador não abre navegador, e abrir um a cada execução custaria segundos a
    cada regeração. A TELA foi medida no Chrome em 31/08/2026, e o número está no
    comentário de cada regra: os cinco rótulos começam no mesmo x, os cinco
    campos começam no mesmo x, e os campos foram de 394 para 416px de largura.
    Quem mudar estas regras remede lá, não aqui.

    E ela olha a REGRA INTEIRA, nunca um token solto no meio da página — a
    armadilha que o `COMO-OLHAR-A-TELA.md` chama de *"régua que casa um token em
    qualquer lugar do texto, em vez do campo que o significa"*, e que já reprovou
    três rótulos certos nesta casa porque a legenda os citava.
    """
    falhas = []

    def exigir(cond, queixa):
        if not cond:
            falhas.append(queixa)

    # A REGRA DO RÓTULO, extraída inteira: casar `text-align:left` na página
    # solta acharia qualquer outra regra que o use.
    regra = re.search(r"\.campo > span:first-child\{[^}]*\}", html)
    exigir(regra is not None, "a regra do rótulo do campo sumiu do CSS")
    if regra:
        exigir("text-align:left" in regra.group(0),
               "o rótulo do campo não alinha mais à esquerda")
        exigir("text-align:right" not in regra.group(0),
               "o rótulo do campo voltou a alinhar à direita")
        exigir("white-space:nowrap" in regra.group(0),
               "o `nowrap` saiu — um rótulo que crescer vira duas linhas e estoura a altura")

        exigir("var(--fg)" in regra.group(0),
               "o rótulo do campo voltou ao verde — o verde é de ESTADO, não de nome")
        exigir("font-weight:700" in regra.group(0),
               "o negrito do rótulo saiu — sem ele o nome vira dado")

    # O VERDE SÓ ONDE É ESTADO — e a régua olha REGRA A REGRA, não a página.
    # A primeira versão desta linha procurava `color:var(--rot-campo)` no HTML
    # inteiro e reprovou na hora: quem casava era `.linha-rot`, do `topo.html`
    # compartilhado, que esta aba nem usa. A régua estava medindo o CSS das dez
    # abas para julgar uma. Mesmo defeito que já reprovou três rótulos certos
    # nesta casa: *casar um token em qualquer lugar do texto*.
    r = re.search(r"\.tab thead th\{[^}]*\}", html)
    exigir(r is not None, "a regra dos cabeçalhos de coluna sumiu do CSS")
    if r:
        exigir("color:var(--fg)" in r.group(0),
               "os cabeçalhos de coluna voltaram ao verde — verde é de ESTADO, não de nome")
        exigir("font-weight:700" in r.group(0),
               "o negrito dos cabeçalhos saiu — sem ele o nome vira dado")

    # O TÍTULO DE BLOCO é a exceção que ela mesma abriu: verde, e são só dois.
    r = re.search(r"\.sec-rot\{[^}]*\}", html)
    exigir(r is not None, "a regra do título de bloco sumiu do CSS")
    if r:
        exigir("color:var(--rot-campo)" in r.group(0),
               "o título de bloco perdeu o verde que ela pediu")
    for titulo in ("Perfis Salvos", "Definições"):
        exigir(f'class="sec-rot">{titulo}<' in html,
               f"o título de bloco '{titulo}' não está na tela")

    # OS RÓTULOS COM DOIS PONTOS, e o cabeçalho por extenso.
    for rot in ("Nome:", "Prioridade:", "Funciona em:", "Nome do Jogo:", "Estilo de Jogo:"):
        exigir(f">{rot}</span>" in html, f"o rótulo '{rot}' não está na tela")
    exigir('class="pri">Priorização<' in html, "o cabeçalho voltou a ser abreviado")

    # O FUNDO POR COLUNA — três regras, três cores. Se as três virarem uma só, a
    # coluna deixa de se distinguir e o pedido dela caiu.
    fundos = re.findall(r"\.tab thead th:nth-child\(\d\)\{background-image:([^}]*)\}", html)
    exigir(len(fundos) == 3, f"não são 3 fundos de coluna no CSS, e sim {len(fundos)}")
    exigir(len(set(fundos)) == 3, "os fundos das três colunas não são cores diferentes")

    # O LUGAR DE QUEM NÃO ESTÁ NA MESA — um por controle desconectado, com o
    # texto da Gatilhos. E a régua cobra as DUAS metades: que o nome novo esteja
    # lá, e que o rótulo curto do controle NÃO esteja — foi assim que uma cura
    # desta casa passou pela metade, tirando o texto e levando o dado junto.
    fora = [c for c in MESA if not c.get("conectado", True)]
    exigir(html.count("Desconectado</span>") == len(fora),
           f"não são {len(fora)} lugares 'Desconectado' na tabela por controle")
    for c in fora:
        exigir(rotulo(c, "curta") not in html,
               f"o rótulo de mesa do P{c['jogador']} continua na tela — ele não está na mesa")
    exigir(html.count('class="fora"') == len(fora),
           "os lugares desconectados perderam a classe que os apaga")

    # A IDENTIDADE VEM DE CIMA — 03/09/2026. A cor do plástico da linha tem de
    # ter ENDEREÇO: sem ele a barra fica com a cor do DESENHO enquanto o
    # `guarda.nome` ao lado já traz o aparelho, e a linha passa a dizer duas
    # coisas ao mesmo tempo. A régua cobra as três metades — o endereço existe,
    # o alvo é o idempotente, e nenhum `--plastico` cravado voltou ao miolo.
    exigir(html.count('data-hef="guarda.plastico"') == len(MESA),
           f"não são {len(MESA)} barras com endereço `guarda.plastico` na tabela por controle")
    exigir(html.count('data-hef-alvo="cor"') == len(MESA),
           "a barra do plástico perdeu o alvo `cor` — o `fundo` soma uma pintura por tique")
    exigir("--plastico:" not in html.split('class="miolo"')[-1],
           "voltou um `--plastico` cravado no miolo — identidade de aparelho sem endereço")

    # E A DICA DA LINHA NÃO PODE NOMEAR O APARELHO. Um `title` no `<tr>` é
    # congelado no arquivo — alvo nenhum do piloto escreve atributo —, então o
    # nome do modelo ali fica sendo o do MOCKUP enquanto a célula ao lado já
    # traz o do aparelho. A régua olha o ELEMENTO, e não a frase: proibir os
    # nomes um a um deixaria o 29º modelo do CSV entrar livre.
    linhas = re.findall(r"<tr data-hef-uniq=\"[^\"]+\"[^>]*>", html)
    exigir(len(linhas) == len(MESA),
           f"não são {len(MESA)} linhas na tabela por controle, e sim {len(linhas)}")
    na_mesa_com_dica = [t for c, t in zip(MESA, linhas, strict=True)
                        if c.get("conectado", True) and "title=" in t]
    exigir(not na_mesa_com_dica,
           f"{len(na_mesa_com_dica)} linha(s) de controle NA MESA voltaram a ter "
           f"dica — ela congela o nome do modelo do desenho por cima de um "
           f"aparelho que é outro")
    # E a do lugar VAZIO fica: ela fala de um LUGAR, não de uma peça, e some com
    # a mesma facilidade com que a outra voltaria.
    fora_sem_dica = [c["pref"] for c, t in zip(MESA, linhas, strict=True)
                     if not c.get("conectado", True) and "title=" not in t]
    exigir(not fora_sem_dica,
           f"o lugar vazio {fora_sem_dica} perdeu a dica que explica por que ele "
           f"continua na tabela — ela não fala de aparelho nenhum")

    # A DIVISÓRIA HORIZONTAL, que ela mandou remover DESTE trecho.
    exigir(".campos > .campo::after" not in html,
           "as linhas horizontais voltaram ao editor de perfil")

    # AS OITO DICAS DAS CÉLULAS — decisão dela nº4, 03/09/2026. A régua olha o
    # ELEMENTO inteiro, e não a frase: proibir os textos um a um deixaria a nona
    # dica entrar livre. Um `<span class="gr…" data-hef="guarda.secao">` com
    # `title=` é o defeito, escreva ele o que escrever.
    celulas = re.findall(r'<span class="gr[^"]*" data-hef="guarda\.secao"[^>]*>', html)
    exigir(len(celulas) == len(MESA) * len(SECOES),
           f"não são {len(MESA) * len(SECOES)} células de `guarda.secao` "
           f"({len(MESA)} controles x {len(SECOES)} seções), e sim {len(celulas)}")
    com_dica = [c for c in celulas if "title=" in c]
    exigir(not com_dica,
           f"{len(com_dica)} célula(s) de `Ajuste próprio` voltaram a ter dica — "
           f'ela mandou as oito saírem: "Auto falante é auto falante, gatilho é gatilho"')

    # O ALVO QUE DEIXA O PRODUTO ACENDER A CÉLULA. Sem ele o pintor escreve
    # `textContent` e apaga o glifo SVG de dentro do `<span>` — é o defeito que
    # ela fotografou em 02/09 na coluna ao lado, e que `NAO_PINTAVEIS` segurava.
    sem_alvo = [c for c in celulas if 'data-hef-alvo="classe"' not in c]
    exigir(not sem_alvo,
           f"{len(sem_alvo)} célula(s) de `guarda.secao` sem "
           f'`data-hef-alvo="classe"` — pintá-las apagaria o glifo')

    # O QUINTO AJUSTE — decisão dela nº20. A coluna do microfone existe na tela
    # ANTES de o campo existir no esquema, e é a decisão que manda.
    exigir('data-hef-secao="mic"' in html,
           "a coluna do microfone sumiu da linha `Ajuste próprio` (decisão nº20)")
    exigir(f"São os {QUANTAS_SECOES} ajustes" in html,
           f"a dica do cabeçalho não diz mais `{QUANTAS_SECOES}` ajustes por controle")
    # E A DICA NOMEIA AS SEIS, uma a uma — 05/09/2026. O número já saía de
    # `len(SECOES)` e a LISTA DE NOMES continuava digitada: quando o `sensores`
    # chegou ao esquema, a frase seguiu dizendo "luz, gatilhos, vibração,
    # alto-falante e microfone" sem que nada reprovasse. Cobrar nome a nome é o
    # que impede a próxima seção de entrar calada.
    sem_nome = [campo for campo, _ in SECOES if campo not in NOME_DA_SECAO]
    exigir(not sem_nome,
           f"a(s) seção(ões) {sem_nome} não têm nome em `NOME_DA_SECAO` — a dica "
           f"do cabeçalho não saberia como chamá-la na tela")
    fora_da_dica = [NOME_DA_SECAO[campo] for campo, _ in SECOES
                    if NOME_DA_SECAO[campo] not in html]
    exigir(not fora_da_dica,
           f"a dica do cabeçalho não nomeia {fora_da_dica} — a coluna existe na "
           f"tabela e a frase que a explica não a menciona")

    # A TIRA DO DESFECHO — 03/09/2026. As duas coisas que a fazem funcionar, e
    # cada uma some sem sintoma se ninguém a cobrar: os DOIS endereços (o
    # `classe` acende, o `<span>` escreve).
    exigir(html.count('data-hef="perfis.desfecho"') == 2,
           "a tira do desfecho perdeu um dos dois endereços — sem o `classe` "
           "ela fica acesa com um travessão; sem o `<span>` ela nunca escreve")
    exigir('class="desfecho" data-hef="perfis.desfecho" data-hef-alvo="classe"' in html,
           "a tira do desfecho perdeu o alvo `classe` — ela acenderia sempre")
    # A RÉGUA SE INVERTEU — 05/09/2026. Ela exigia `height:30px` na regra de
    # REPOUSO ("a tira do desfecho deixou de reservar o espaço"), e era ela que
    # guardava os 37px de banda morta que ela chamou de bizarros. Uma régua que
    # cobra o que saiu não se apaga: passa a guardar a REMOÇÃO. Agora ela cobra
    # que a tira em repouso não tenha altura nem folga, e que as duas voltem na
    # `.on` — a medição em pixels está em
    # `tests/unit/test_a_aba10_nao_reserva_banda_morta_no_titulo.py`.
    exigir("visibility:hidden" in html,
           "a tira do desfecho perdeu o `visibility:hidden` — ela apareceria "
           "vazia em toda tela sem recado")

    # A SEGUNDA LINHA DA TIRA — decisão [05] do PO, 04/09/2026. As três metades,
    # e cada uma some sem sintoma: a ALTURA (uma linha volta a cortar), o
    # `line-clamp` (sem ele a frase de 280 caracteres vaza para fora da caixa em
    # vez de reticenciar) e a AUSÊNCIA do `nowrap`, que sozinho desfaz as outras
    # duas — com ele a frase continua numa linha só dentro de uma caixa de duas.
    regra = re.search(r"\.desfecho\{[^}]*\}", html)
    exigir(regra is not None, "a regra da tira do desfecho sumiu do CSS")
    acesa = re.search(r"\.desfecho\.on\{[^}]*\}", html)
    exigir(acesa is not None, "a regra `.desfecho.on` sumiu do CSS")
    if regra and acesa:
        corpo = regra.group(0)
        exigir("height:0" in corpo and "margin-top:0" in corpo,
               "a tira do desfecho voltou a reservar espaço em REPOUSO — são "
               "37px de banda morta debaixo do título, e ela os chamou de "
               "bizarros em 05/09")
        exigir("height:30px" in acesa.group(0),
               "a tira do desfecho voltou a UMA linha — o fim da frase, que é "
               "a metade que avisa, some com reticências")
        exigir("margin-top:7px" in acesa.group(0),
               "a tira acesa perdeu a folga de 7px que a separa do título")
        exigir("-webkit-line-clamp:2" in corpo,
               "a tira perdeu o `-webkit-line-clamp:2` — a frase longa vaza "
               "para fora da caixa em vez de parar na segunda linha")
        exigir("white-space:nowrap" not in corpo,
               "o `nowrap` voltou à tira — com ele a frase continua numa linha "
               "só, e as duas linhas reservadas viram espaço morto")

    # O CADEADO E O PONTO DE ALERTA — decisão [01] do PO. A régua cobra as TRÊS
    # coisas que os fazem funcionar, e as três somem caladas: os DOIS endereços
    # de cada marca (a `classe` que a acende, o `html` que escreve a frase), e a
    # `.dica` VAZIA — um texto de exemplo aqui seria a tela afirmando uma regra
    # que o perfil dela não tem.
    for classe, estado, frase in (
            ("trava", "editor.ambiente.travado", "editor.ambiente.recado"),
            ("exige", "editor.jogo.exige", "editor.jogo.exigencia")):
        marca = re.search(rf'<span class="{classe}"[^>]*>', html)
        exigir(marca is not None,
               f"a marca `{classe}` sumiu do editor — o campo volta a ficar "
               f"idêntico a um destravado e só reclama depois do clique")
        if marca:
            exigir(f'data-hef="{estado}"' in marca.group(0)
                   and 'data-hef-alvo="classe"' in marca.group(0),
                   f"a marca `{classe}` perdeu o endereço que a acende "
                   f"(`{estado}`, alvo `classe`) — ela ficaria escondida para "
                   f"sempre, ou visível para sempre")
        exigir(f'<span class="dica" data-hef="{frase}" data-hef-alvo="html">'
               f'</span>' in html,
               f"a dica de `{classe}` não é um `{frase}` VAZIO no desenho — ou "
               f"o endereço sumiu, ou o mockup passou a cravar uma frase que é "
               f"dado do perfil dela")

    # A FRASE DA PRIORIDADE, E A ORDEM DAS DUAS — decisão [03] do PO. A dela
    # PRIMEIRO: é a que ela aprovou, e a do Universal responde a pergunta que a
    # dela deixa aberta.
    dica = re.search(r'data-hef="editor\.prioridade\.dica" title="([^"]*)"', html)
    exigir(dica is not None, "a dica da Prioridade perdeu o `title` do desenho")
    if dica:
        exigir(dica.group(1) == DICA_DA_PRIORIDADE,
               f"a dica da Prioridade não é a frase decidida:\n"
               f"    tem  {dica.group(1)!r}\n"
               f"    quer {DICA_DA_PRIORIDADE!r}")
        exigir(dica.group(1).startswith(FRASE_DA_PRIORIDADE_DELA),
               "a frase DELA deixou de vir primeiro na dica da Prioridade")

    # A PRIORIDADE É SLIDER — 03/09/2026, decisão dela (*"Slider, como você
    # pediu"*). A régua cobra as QUATRO metades, e cada uma some sem sintoma:
    # o campo existe e ARRASTA; ele tem gesto (senão arrastar é silêncio); a
    # faixa é a do ESQUEMA, e não uma digitada; e o valor de partida é o mesmo
    # número que a legenda ao lado mostra.
    faixa = re.search(r'<input type="range" class="desliza"[^>]*>', html)
    exigir(faixa is not None,
           "a Prioridade voltou a ser uma barra que não se arrasta — era o "
           "único campo do editor sem caminho de escrita")
    if faixa:
        campo = faixa.group(0)
        exigir(f'min="{PRIORIDADE_MINIMA}"' in campo
               and f'max="{PRIORIDADE_MAXIMA}"' in campo,
               f"a faixa do slider não é a do esquema "
               f"({PRIORIDADE_MINIMA}..{PRIORIDADE_MAXIMA}) — ela passou a ser "
               f"digitada, e envelhece no dia em que o teto mudar")
        exigir('data-hef-gesto="editor.prioridade"' in campo,
               "o slider da Prioridade perdeu o gesto — arrastar volta a ser "
               "silêncio no stdout de quem lançou a janela")
        exigir(f'value="{PRI_DO_DESENHO}"' in campo,
               f"o slider abre num número que não é o do desenho "
               f"({PRI_DO_DESENHO}) — o punho e a legenda discordariam")
    # E O CHEIO É A CONTA, não os 90% de antes: com o teto em 200, `width:90%`
    # dizia "quase no máximo" sobre um perfil que está em 90 de 200.
    exigir(f'data-hef-alvo="largura" style="width:{PCT_DO_DESENHO}%"' in html,
           f"a barra do cheio não mostra {PCT_DO_DESENHO}% — a largura do "
           f"desenho voltou a ser digitada em vez de sair do teto do esquema")

    # OS ESTILOS SÃO OS DO MOTOR, e a régua pergunta ao motor. Uma contagem
    # (`== 15`) envelheceria na primeira receita nova; o que se cobra é o
    # CONJUNTO, e que a opção vazia dela continue na frente.
    for e in ESTILOS_DO_MOTOR:
        exigir(f">{e.rotulo}</option>" in html,
               f"o estilo '{e.rotulo}' está no motor e não está no `<select>` "
               f"— o gesto saberia aplicá-lo e ela não teria como pedir")
    exigir('<option value="" selected>—</option>' in html,
           "a opção vazia do Estilo de Jogo saiu — o campo voltaria a abrir "
           "afirmando um estilo que perfil nenhum guarda")

    # O TRAVESSÃO DO "FUNCIONA EM" — 04/09/2026, medido no DOM vivo. Sem esta
    # opção o `escrever()` não tem onde pousar o `—` de um perfil cuja regra a
    # tela não sabe mostrar, e o campo fica com o "Jogo" do MOCKUP — o cadeado
    # ao lado dizendo "não sei mostrar" e o campo dizendo "Jogo".
    exigir(f'<option value="{TRAVESSAO}" disabled>{TRAVESSAO}</option>' in html,
           "a opção `—` do 'Funciona em' saiu — o perfil de regra fina volta a "
           "mostrar a opção que o DESENHO trazia")

    # A COLUNA JUSTA. O `104px` é o valor antigo, e o vão morto de 22px é ele.
    exigir("--rot-p:86px" in html,
           "a coluna do rótulo não é mais a medida do rótulo mais largo (86px)")
    exigir("--rot-p:104px" not in html,
           "a coluna do rótulo voltou aos 104px — 22px de vão morto por rótulo")

    if falhas:
        raise SystemExit("ERRO em 10-perfis — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


n = monta("10-perfis", "Perfis", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
_conferir(onde.pagina("10-perfis.html").read_text(encoding="utf-8"))
# O NÚMERO SAI DO CSS, não de um literal aqui: ele já mentiu duas vezes hoje —
# a coluna mudou de 82 para 87 e para 86 enquanto ela ajustava os rótulos, e a
# linha de saída continuou anunciando o valor velho. O que tem dono não se digita.
ROT_P = re.search(r"--rot-p:(\d+)px", CSS).group(1)
FORA = sum(1 for c in MESA if not c.get("conectado", True))
print(f"10-perfis: OK, {n} divs · rótulo à esquerda com dois pontos, coluna de {ROT_P}px, "
      f"zero divisórias no editor · Perfis Salvos e Definições · {FORA} lugar(es) Desconectado")
