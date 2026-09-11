# A PASTA, não /tmp: o `monta` e o `topo.html` vivem aqui, e é daqui que esta
# aba os lê. Ver o cabeçalho do aba09.py para o defeito que isso curou.
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import collections
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
# O QUADRO "MODO" SAIU DAQUI — 11/09/2026, ordem dela:
#
#     "em perfis ainda aparece modo. Isso deve aparecer só na aba jogar."
#
# ELE NASCEU EM 06/09 (PERFIL-MODO-01) e viveu cinco dias. O que morre junto: o
# leitor `_lista_de_pares`, que ia buscar os quatro rótulos em
# `app/actions/profiles_actions._MODE_KIND_ITEMS` sem importar GTK; a constante
# `MODOS`; o `botoes_do_modo()`; a regra `.campo.modo` do CSS; e o gesto
# `a10_perfis.editor_modo`, que é quem gravava.
#
# O QUE **NÃO** MORRE, e a distinção é o assunto inteiro: `Profile.mode`
# continua no esquema e no disco. Um perfil que já diz «Jogar pelo Hefesto»
# continua dizendo, e o `ativar` continua aplicando. O que sai é quem EDITA —
# e a aba onde se edita é a **Jogar**, que não é desta sprint.
#
# O PERFIL NOVO NASCE SEM SEÇÃO `mode` — decisão desta sprint, registrada em
# `a10_perfis.novo`: é o padrão vivo («Não mexer no modo», o perfil sem
# opinião), e é o único valor que preserva o comportamento de hoje para quem
# nunca tocou no quadro nos cinco dias em que ele existiu.
#
# E A RETIRADA TEM UM PREÇO MEDIDO A FAVOR — os números estão no bloco da
# `.guarda`, lá embaixo: a fileira do Modo custava **36px** de uma coluna em que
# a tabela «Ajuste próprio» já disputava cada pixel com a tira do desfecho, e
# era ela que deixava a linha do P4 fora do quadro a cada gesto dela.

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
#
# A SÉTIMA NASCEU EM 08/09/2026, com a decisão dela: *"pode entrar sim"* — a
# máscara por controle entrou em `ControllerOverrides` (MASCARA-NO-PERFIL-01), e
# a régua `test_a_coluna_de_ajuste_proprio_mostra_o_disco_inteiro` cobra na hora
# toda seção do esquema que a página não mostre. A `mascara` é a primeira que
# NÃO é uma seção — é um valor só (`"xbox"`, `"dualsense"`, `"nintendo"`) —, e
# para a coluna isso não muda nada: ela sempre teve dois estados, e `!!` de um
# valor é o mesmo `!!` de um objeto.
#
# O GLIFO É PROVISÓRIO — decisão dela. A máscara não tem peça de plástico: as
# outras seis acendem a peça que elas mexem (a barra de luz, o L2, o motor), e
# esta responde *"como este controle inteiro aparece no jogo"*. Escolhi o botão
# `ps` porque é o botão que carrega a marca do console, e é o mais próximo de
# "de que console este controle diz ser". Se ela preferir outro glifo, muda-se
# esta linha e a página se regenera — nada mais depende dela.
SECOES = [
    ("leds", ("lightbar", "led-jogador")),
    ("triggers", ("l2", "r2")),
    ("rumble", ("rumble_esquerdo", "rumble_direito")),
    ("speaker", ("alto-falante",)),
    ("mic", ("mic",)),
    ("sensores", ("giroscopio", "acelerometro")),
    ("mascara", ("ps",)),
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
    # "máscara" é a palavra que a aba Jogar já usa no chip de cada cartão
    # (`data-gesto="mascara"`) — não é vocabulário novo de tela.
    "mascara": "máscara",
}


def _lista_das_secoes() -> str:
    """`luz, gatilhos, vibração, alto-falante, microfone e sensores`."""
    nomes = [NOME_DA_SECAO[campo] for campo, _pecas in SECOES]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}" if len(nomes) > 1 else nomes[0]


#: O NÚMERO POR EXTENSO, para a tela nunca discordar da lista. As frases da aba
#: dizem "os seis ajustes"; escrever a palavra à mão em três lugares é como a
#: contagem de `NAO_PINTAVEIS` divergiu no primeiro dia. Sai daqui, de
#: `len(SECOES)`, e muda sozinha quando a lista mudar.
_EXTENSO = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis",
            7: "sete"}
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
    # A `mascara` entra no P3 pela MESMA regra do `sensores`: acesa em um,
    # apagada em três. E no P3, e não no P2, para as duas colunas novas não
    # empilharem na mesma linha — a pedagogia é "quem não tem opinião herda".
    "p3": {"leds", "mascara"},
    "p4": set(),
}

# O ID DA PEÇA é o endereço de rádio normalizado — a MESMA chave que o
# `_validate_controllers_keys` aceita e canoniza (`profiles/schema.py:1661`), e
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
  /* O REALCE DA ESCOLHIDA NÃO PODE SER A COR DO `:hover` — 05/09/2026, e a
     queixa é dela: *"caso eu clicasse em outro perfil dos disponíveis ele não
     tinha nada selecionado em termo visual pra divergir dos demais e do
     ativo"*.

     MEDIDO: o dado estava CERTO. O produto escreve `aria-selected="true"` na
     linha clicada e `false` nas outras — conferido chamando `selecionar` e
     lendo o `<tbody>` que o pacote emite. O que estava errado era a COR: a
     linha escolhida e a linha sob o mouse usavam as duas `var(--sel-bg)`, a
     mesma `rgba(189,147,249,.16)`. Ela passa o mouse pela lista e toda linha
     acende igual à escolhida; a marca existia e não marcava nada.

     OS TRÊS ESTADOS PASSAM A SER TRÊS COISAS DIFERENTES:

       passando o mouse   um véu BRANCO fraco — "estou por cima", nada mais
       escolhida          roxo FORTE, negrito, e a barra roxa de 3px
       ativa              verde no texto e barra verde (a cor não muda aqui)

     O roxo da escolhida dobrou (.16 -> .30). Ele não é gosto: com o `:hover`
     por cima ele ainda precisa ler como "esta é OUTRA coisa", e .16 sobre um
     véu branco de .06 é indistinguível a olho nu. */
  .tab tbody tr[aria-selected="true"] td{background:rgba(189,147,249,.30);
          color:var(--fg);font-weight:600}
  .tab tbody tr[aria-selected="true"] td:first-child{box-shadow:inset 3px 0 0 var(--purple)}
  .tab tbody tr.ativo[aria-selected="true"] td{color:var(--green)}
  .tab tbody tr.ativo[aria-selected="true"] td:first-child{
          box-shadow:inset 3px 0 0 var(--green),inset 6px 0 0 var(--purple)}
  .tab tbody tr:hover:not(.ativo):not([aria-selected="true"]) td{
          background:rgba(255,255,255,.06)}
  /* E a linha ATIVA também responde ao mouse, sem virar a escolhida: ela não
     entrava em regra de `:hover` nenhuma e ficava morta sob o cursor. */
  .tab tbody tr.ativo:hover:not([aria-selected="true"]) td{
          background:rgba(255,255,255,.06)}
  /* `Pri.` VIROU `Priorização` — 31/08/2026, pedido dela. Os 46px do valor
     antigo JÁ NÃO ERAM VERDADE: `table-layout` é `auto`, então `width` é
     sugestão, e o Chrome media 86px para caber o cabeçalho. O número aqui passa  # (noqa-acento) id
     a ser o medido; escrever 46 embaixo de uma coluna de 86 é deixar no CSS uma
     afirmação que a tela desmente. */
  .tab .pri{font-family:'JetBrains Mono',monospace;width:96px;text-align:right}
  .tab .quando{color:var(--texto-mudo);font-weight:400}
  /* ------------------------------------------------------------------
     A LUPA, OS DOIS ÍCONES, A SETA E A DIVISA — PERFIS-LIMPA-01, 11/09/2026.

     O ALVO DO CLIQUE TEM TAMANHO, e o desenho NÃO É O ALVO. O SVG mede 11px
     (o mesmo do CADEADO, que era o único ícone desta aba), e 11px é desenho
     — ela clica isto com o mouse. Os 24x24 são o mínimo de alvo, e eles cabem
     na linha de 15px do `.sec-rot` porque o botão é `align-self:center` com
     `margin` negativa vertical: ele SOBRA para cima e para baixo sem empurrar
     nada. É assim que os dois ícones entram em linhas que já existem sem
     acrescentar um pixel de altura — que é o que a ordem dela pedia.

     ELES SÃO `<button>` E NÃO HERDAM NADA DE `.btn`: o botão desta casa tem
     borda, fundo e 11,5px de texto, e é justamente o que sai de cena aqui. */
  .icone-rot{-webkit-appearance:none;appearance:none;border:none;background:none;
             padding:0;margin:-5px 0;width:24px;height:24px;flex:0 0 24px;
             display:inline-flex;align-items:center;justify-content:center;
             color:inherit;cursor:pointer;border-radius:5px;align-self:center}
  .icone-rot:hover{background:rgba(255,255,255,.09)}
  .icone-rot:active{background:rgba(255,255,255,.15)}
  .icone-rot.on{background:var(--sel-bg,rgba(189,147,249,.30))}
  /* O CAMPO DA LUPA NASCE FECHADO — decisão dela em uma frase: *"Temos que  (noqa-acento) citação
     deixar o layout mais limpo"*. Um campo de busca sempre visível ACRESCENTA  (noqa-acento) citação
     uma linha ao bloco em vez de tirar; ele nasce do clique na lupa e some no
     clique seguinte. `width:0` em vez de `display:none` para a abertura ter
     movimento — e `padding:0` junto, senão o campo fechado continua com 12px
     de folga ocupando a linha. */
  .procura{-webkit-appearance:none;appearance:none;width:0;padding:0;border:none;
           background:var(--panel);color:var(--fg);font:inherit;font-weight:400;
           font-size:11px;border-radius:5px;min-width:0;
           transition:width .12s ease,padding .12s ease}
  .procura.on{width:150px;padding:3px 7px;border:1px solid var(--border-forte)}
  .procura::placeholder{color:var(--comment)}
  /* QUANTOS A LUPA ESCONDEU. Ela nasce vazia e o `ligado()` do piloto lê o
     vazio como apagado — sem filtro, nada aparece. */
  .fora-da-busca{font-size:10.5px;color:var(--comment);font-weight:400;
                 letter-spacing:0;text-transform:none;display:none}
  .fora-da-busca.on{display:inline}
  /* A SETA DA COLUNA ORDENADA — do tamanho do ícone, e sem texto novo.

     `pointer-events:none` NÃO É ENFEITE, É A TRAVA DO DUPLO CLIQUE: este
     `<span>` é o elemento que carrega `data-hef-gesto="ordenar"`, e o ouvinte
     do piloto despacha no PRIMEIRO clique. Sem esta linha, um clique simples
     no cabeçalho ordenaria — e o cabeçalho é `position:sticky` a um pixel da
     célula do nome, que é o gesto `selecionar` e troca o perfil aberto no
     editor. Com ela, mouse nenhum alcança este nó; quem o aciona é o roteiro
     da página, no `dblclick`, por `.click()`. Ela pediu duplo clique. */
  /* O GLIFO VEM DO CSS, E NÃO DO PILOTO — 11/09/2026, e o defeito era duplo.
     A seta nasceu com `data-hef-alvo="classe"`, e o ramo `classe` do
     `escrever()` (`hefesto_vivo.py:636`) só liga classe e RETORNA: nunca
     escreve texto. Medido na conferência: com `perfis.ordem.nome = "↑"` o
     span ficava `class="ordena on"`, `opacity:1`, `textContent:""` e
     **0px de largura** — a seta que diz qual coluna ordena NÃO EXISTIA na
     tela, nos três estados. E o alvo `texto` não servia: com valor vazio o
     `escrever()` põe o travessão do lugar vazio (`:382`), e as duas colunas
     não ordenadas mostrariam «—».
     O alvo é `atributo`, que é o único que APAGA quando o valor é vazio
     (`hefesto_vivo.py:804`). O glifo é `content` do CSS; o Python só diz
     qual, pelo `data-ordem`.

     E A MARGEM SÓ EXISTE QUANDO HÁ SETA. Os 4px de um span vazio cortaram
     «Priorização» para «Priorizaçã…» — medido em duas larguras de janela,
     scrollWidth 90 num clientWidth 86. Sem a seta, o mesmo `<th>` mede 86/86.

     `pointer-events:none` NÃO É ENFEITE — a razão inteira está no bloco de
     comentário acima desta regra. */
  .ordena{pointer-events:none;font-size:10px;line-height:1;color:var(--purple)}
  .ordena[data-ordem]{margin-left:4px}
  .ordena[data-ordem="↑"]::after{content:"↑"}
  .ordena[data-ordem="↓"]::after{content:"↓"}
  /* A DIVISA QUE ELA ARRASTA. O cursor muda quando ela chega perto — é
     literalmente o que ela descreveu: *"quando o cursor muda e permite  (noqa-acento) citação
     alterar a largura da coluna"*. 9px de faixa, metade para cada lado da
     borda, é o que a mão acha sem procurar. */
  .puxador{position:absolute;top:0;bottom:0;right:0;width:9px;z-index:3;
           cursor:col-resize;background:none}
  .puxador:hover{background:linear-gradient(90deg,transparent 3px,
                 var(--purple) 3px,var(--purple) 5px,transparent 5px)}
  .arrastando,.arrastando *{cursor:col-resize !important;user-select:none}
  /* A LARGURA DA COLUNA SÓ MANDA COM `table-layout:fixed` — MEDIDO, e é a
     armadilha que o próprio arquivo já registrava: `.tab .pri` dizia 46px e o
     navegador media 86px  (noqa-acento: verbo medir, imperfeito), porque com
     `auto` a `width` é SUGESTÃO. Uma largura
     arrastada sobre `auto` é uma largura que o navegador reescreve no repinte
     seguinte, e a coluna volta sozinha ao que o texto mandar.

     O PREÇO, declarado: com `fixed` o texto mais largo que a coluna não a
     ESTICA mais — ele precisa de onde parar, e é por isso que as três células
     ganham reticência aqui embaixo. É o que torna o arraste útil: ela alarga a
     coluna para ler o nome inteiro do jogo, em vez de a coluna decidir por ela.

     O `<colgroup>` É QUEM CARREGA O NÚMERO, e não a `width` da `<th>`: é o
     único elemento da tabela que existe para isso, ele não é reescrito pelo
     `blocos` do piloto (que só troca o `<tbody>`), e um `<col>` por coluna dá
     ao roteiro um lugar só para escrever. */
  .tab{table-layout:fixed}
  /* AS LARGURAS DE PARTIDA, e as duas foram REMEDIDAS no motor certo em
     11/09/2026. Elas nasceram de uma medição feita no CHROME, e o produto
     renderiza no `WebKit2.WebView`: medido nos dois motores, o `Nome` de 255px
     tirava 69px do `Quando usar` numa janela de 1280px (ontem, com `auto`:
     185·86·294; com os 255 cravados: 255·86·225). **O `Quando usar` é onde mora
     o nome do jogo, e foi ele que ela pediu para achar rápido** — então quem
     devolve o espaço é o `Nome`, não ele.

     `Nome` 255 → 185: é o que o `auto` dava a 1280. `Priorização` 86 → 96: é a
     largura do rótulo MAIS a seta da ordem (6,2px de glifo + 4px de margem) —
     sem os 10px o cabeçalho da coluna ORDENADA media  (noqa-acento: verbo medir,
     imperfeito) 96 num espaço de 86 e
     saía «Priorizaçã…», que é o defeito que a conferência fotografou. Uma
     coluna que se ordena tem de caber no próprio rótulo com a marca de ordem.

     E O `QUANDO USAR` NÃO GANHA `<col>` DE PROPÓSITO: sem largura escrita ele
     fica com o resto, que é o único jeito de uma tabela `fixed` ter uma coluna
     elástica. A 1600px isso lhe dá 444px, mais que os 392 de ontem.

     O `<colgroup>` é quem carrega o número e não a `width` da `<th>`; quem
     arrastar ganha um `style` inline no mesmo `<col>`, e inline vence folha. */
  .tab col[data-coluna="nome"]{width:185px}
  .tab col[data-coluna="prioridade"]{width:96px}
  .tab td,.tab th{overflow:hidden;text-overflow:ellipsis}
  .tab .quando{white-space:nowrap}
  .tab tbody td{white-space:nowrap}
  .conta-perfis{font-size:10.5px;color:var(--comment);margin-left:auto;text-transform:none;
                letter-spacing:0}
  /* 3 botões e 3 botões, todos da mesma largura */
  .botoes{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:auto;padding-top:12px}
  .botoes .btn{width:100%;justify-content:center;padding:0 8px;font-size:11.5px}
  /* UM BOTÃO SÓ, e a grade de três o deixaria com um terço da largura e dois
     vãos vazios ao lado — que é mais sujo do que os três eram. 11/09/2026. */
  .botoes.um-so{grid-template-columns:1fr}
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
  /* `minmax(0,1fr)` E NÃO `1fr`, e a diferença é MEDIDA — 06/09/2026. Uma pista
     `1fr` é `minmax(auto,1fr)`, e o mínimo `auto` de uma pista de grade é o
     MIN-CONTENT do que está dentro: a pista CRESCE para caber o conteúdo, em
     vez de apertá-lo. Enquanto os campos eram `<input>` e `<select>` isso não
     aparecia — nenhum dos dois cresce com o valor. O rótulo do jogo (10-Q4) é
     TEXTO, e cresce: medido no Chrome com um nome de 300 caracteres, a segunda
     coluna passou de 412px para **1990px** dentro de uma página de 1180px, e o
     `Detectar` saiu do quadro junto com ela. O `min-width:0` dos filhos não
     alcança isto — ele deixa o FLEX apertar, e aqui quem não apertava era a
     GRADE. */
  .campo{display:grid;grid-template-columns:var(--rot-p) minmax(0,1fr);align-items:center;gap:12px;
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
  /* ---------- O QUADRO "MODO" NÃO MORA MAIS AQUI ----------
     11/09/2026, ordem dela: *"em perfis ainda aparece modo. Isso deve aparecer
     só na aba jogar."* Saíram com ele as três regras que a PERFIL-MODO-01
     escrevera em 06/09 para a fileira dos quatro botões — a altura solta, a
     fileira que não quebra, e os 11,5px do rótulo em duas linhas dentro do
     botão.

     O SELETOR NÃO SE ESCREVE NESTE COMENTÁRIO, e isso não é asseio: a régua
     `_conferir` reprova a página em que ele reaparecer, e um comentário CSS
     viaja INTEIRO para dentro do HTML. Escrevê-lo aqui faria o aviso virar a
     primeira ocorrência do defeito que ele descreve — que é uma armadilha já
     paga nesta casa, três vezes em três dias.

     O QUE A RETIRADA DEVOLVE, medido no WebKit em 11/09/2026 a 1212x809, com a
     tabela pintada como o PRODUTO a pinta (dois lugares vazios e o travessão no
     ID da peça), e não como o desenho a congela:

       a fileira do Modo             36px
       ANTES, sem a tira            115px de espaço · 107 pedidos · sobra  +8
       ANTES, com a tira acesa       78px de espaço · 107 pedidos · sobra -29
       DEPOIS, sem a tira           155px de espaço · 107 pedidos · sobra +48
       DEPOIS, com a tira acesa     118px de espaço · 107 pedidos · sobra +11

     A LINHA DE -29 É A QUEIXA DELA. Com a tira do desfecho acesa — e ela acende
     a cada gesto, por 30 segundos — a tabela rolava 36px e a linha do P4 ficava
     **15px FORA** do quadro. Os 36px da fileira do Modo eram exatamente os 37
     que a tira pede: as duas queixas dela eram uma. */
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
     num `_toast_profile` no rodapé (`profiles_actions.py:4648`): "Perfil
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
     duas passam de 280. O que sumia era exatamente o *"sem ela, o jogo tende a
     não enxergar controle nenhum"*.

     O `~200` DE ESTIMATIVA VIROU MEDIDA — 06/09/2026: as duas linhas comportam
     413 caracteres, medidos por bissecção no Chrome. O número tem dono
     (`CABEM_NA_TIRA`, no alto deste arquivo) e a régua o lê de lá.

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

  /* ---------- O RÓTULO DO JOGO, ao lado do campo — decisão 10-Q4 dela --------
     *"Rótulo ao lado, ao vivo: à direita do campo aparece o nome do jogo
     enquanto você digita, ou «não está nesta máquina», ou «não reconheci este
     endereço»."* Ela recusou a opção que o produto tinha construído em 04/09
     (a resposta só na tira, depois do `change`) — e a escolha ACRESCENTA: o
     campo continua se corrigindo sozinho, o que nasce é o rótulo.

     ELE SE ESCONDE QUANDO NÃO HÁ O QUE DIZER, e essa é a razão de o endereço
     `editor.jogo.rotulo` aparecer DUAS vezes. `escrever()` troca vazio por
     `'—'` ANTES de escolher o ramo (`hefesto_vivo.py`), então um rótulo vazio
     não fica vazio: fica um travessão solto entre o campo e o "Detectar". A
     forma é a MESMA da tira do desfecho, nesta página, quatro blocos acima —
     o `classe` acende, o `<span>` de dentro escreve.

     A TINTA É O TERCEIRO `<span>`, e ele existe porque `data-hef-alvo` é UM por
     elemento: a visibilidade é um fato ("há rótulo?"), o alerta é outro ("é
     erro ou é rotina?"), e os dois têm de ser escritos ao mesmo tempo. É a
     mesma razão pela qual `marca_com_dica` tem dois endereços em vez de um.

     LARANJA SÓ NO ERRO: *"não instalado aqui (o número vale)"* é o jogo que ela
     ainda vai comprar, e pintá-lo de alerta seria a tela chamando de problema o
     que o dono da frase chama de normal (`jogos_locais.frase_do_campo_do_jogo`).

     ELE TEM TETO, e o `<input>` encolhe para caber — que é o que a opção dela
     diz. Nome de jogo é dado DELA e pode ser longo ("ORPHEUS: TO HELL AND
     BACK"): sem `flex:0 1 auto` e sem reticência, o rótulo empurraria o
     "Detectar" para fora do quadro. `text-overflow` e não `-webkit-line-clamp`
     porque aqui é UMA linha de propósito — a fileira do campo tem 30px, e a
     tira de baixo é quem tem duas.

     O `max-width:45%` É MEDIDO, e nasceu de um defeito que a régua achou depois
     de a primeira cura já estar escrita. Com `minmax(0,1fr)` na grade e sem
     teto, a fileira parou de crescer — e o rótulo passou a comer o CAMPO: com
     um nome de 60 caracteres o `<input>` ficava com **24px**, e ela não veria o
     que digitou. Com 45%, o rótulo para em 185px, o campo fica com ~112px (uns
     dez caracteres, mais que um appid) e a reticência entra a partir de ~38
     caracteres de nome — que é onde o nome deixa de caber de qualquer jeito.
     Duas guardas, dois defeitos: a grade impede a fileira de estourar, o teto
     impede o rótulo de tomar o campo. */
  .campo .rot{display:none;flex:0 1 auto;min-width:0;max-width:45%;
              font-size:11.5px;
              color:var(--texto-mudo);white-space:nowrap;overflow:hidden;
              text-overflow:ellipsis}
  .campo .rot.on{display:block}
  .campo .rot .al.alerta{color:var(--orange)}

  /* ---------- as QUATRO configurações que cabem dentro deste perfil ----------
     O editor mostrava CINCO campos e gravava vinte, e a única frase que dizia
     isso vivia escondida na dica do "Perfil ativo": *"cada controle guarda a sua
     configuração aqui dentro, pelo ID da peça"*. Com um controle na mesa dava
     para não reparar; com quatro, a tela que promete e não mostra vira a pergunta
     "então o que exatamente eu salvei?".

     Fica no MESMO quadro, embaixo dos campos, separado por uma linha — e não num
     quadro novo: não é outra tela, é o resto DESTE perfil. E é LEITURA: quem
     escolhe o alvo de um ajuste é a fita, que aqui continua esmaecida. */
  /* A BARRA DE VERDADE, PELA MESMA RAZÃO DO `.rolo` — 06/09/2026, e ela é a
     cura de um CORTE EM SILÊNCIO que o quadro Modo revelou.

     O que estava aqui era `overflow:hidden`, e o `.guarda` é `flex:1` — ele
     ABSORVE o que sobra da coluna. Medido a 1212x809: a folga era de 41px, e a
     tira do desfecho (`.desfecho.on`, decisão 10-Q5 dela) come **37** quando
     acende. Com a fileira do Modo (36px) a conta virou negativa, e as linhas do
     P3 e do P4 sumiam por 30 segundos a cada gesto — sem barra, sem reticência,
     sem nada que dissesse que faltava algo.

     **A DOUTRINA É DA PRÓPRIA RÉGUA** (`test_a_janela_estreita_nao_engole_o_
     desenho`): *"Rolar é aceitável; reticências com `title` também. Cortar em
     silêncio não: quem olha não vê que falta nada, e não há gesto que devolva o
     que foi cortado."*

     E O ARGUMENTO É O QUE O `.rolo` já escreveu logo acima: *"barra de verdade
     porque ela nasce só quando há o que rolar (…) os estados em que a lista
     cabe não pagam nada por ela"*. No tamanho do desenho, sem tira, ela não
     nasce — as quatro linhas cabem inteiras.

     A BARRA DEIXOU DE NASCER NO ESTADO EM QUE ELA A VIU — 11/09/2026. Com o
     quadro Modo fora do editor, a conta desta coluna passou a fechar **com a
     tira acesa**: 118px de espaço para 107 pedidos, sobra +11. Os números dos
     quatro estados estão no bloco do Modo, lá em cima. A barra fica: ela
     continua sendo a rede para a janela que ela arrastar, e no tamanho do
     desenho não custa um pixel. */
  .guarda{flex:1;min-height:0;display:flex;flex-direction:column;
          overflow-y:auto;overflow-x:hidden;
          margin-top:7px;padding-top:7px;border-top:1px solid var(--linha)}
  .guarda::-webkit-scrollbar{width:10px}
  .guarda::-webkit-scrollbar-track{background:transparent}
  .guarda::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .guarda::-webkit-scrollbar-thumb:hover{background:var(--comment)}
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
  /* O NOME VOLTOU A SER CÉLULA DE TABELA — 11/09/2026, e esta é a SEGUNDA
     metade da queixa dela: *"em perfis as linhas dos controles e ajustes
     proprios quebram"*.

     O QUE ESTAVA AQUI: `display:flex;align-items:center;gap:8px`. Um `<td>` com
     `display:flex` deixa de ser célula de tabela — e perde o
     `vertical-align:middle` que as outras duas colunas têm de graça. O texto do
     nome passa a pousar no TOPO da linha enquanto o glifo e o ID se centram
     nela.

     E O FLEX NÃO REPARTIA NADA. Os filhos do `<td>` são dois: a barra da cor
     (`.pl`) e o `<span>` do nome. A barra é `position:absolute`, logo está FORA
     do fluxo — em flex também. Sobrava UM item, e o `gap:8px` entre um item só
     e ninguém. O respiro à esquerda sempre foi o `padding:1px 8px` do `<td>`.

     MEDIDO NO WEBKIT, a 1212x809, com a tabela pintada como o produto a pinta —
     o espalhamento vertical entre os centros de texto das três colunas da mesma
     linha:

       linhas apertadas (21,25px, com o quadro Modo ainda lá)   3,13px
       linhas soltas    (31,25px, com o Modo já fora)           8,13px
       com esta regra                                           1,50px

     A SEGUNDA LINHA É O PONTO, e é por isso que as duas queixas vinham juntas:
     **tirar o Modo devolve altura às linhas e a altura ESCANCARA o desalinho.**
     Curar só a primeira metade teria piorado a segunda de 3,13 para 8,13px — a
     cura de uma queixa dela agravando a outra, na mesma tela.

     O 1,50px QUE SOBRA é o glifo, não o texto: o `.gls` é SVG com
     `vertical-align:-3px` (o deslocamento ótico que a coluna do meio pede), e o
     nome fecha EXATO com o ID da peça — 16,13 contra 16,13. */
  .gd-nome{vertical-align:middle;white-space:nowrap;font-size:11px}
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
  /* O NÚMERO É MEDIDO, e ele mudou de dono em 11/09/2026. Com `table-layout`
     em `auto` esta coluna media  (noqa-acento: verbo medir, imperfeito) 255px
     na tela (a fileira de glifos pede 239 e a
     folga da célula 16), e o `150px` escrito aqui era SUGESTÃO que o navegador
     ignorava. Com `fixed` a sugestão virou ordem: mantido o 150, a fileira de
     glifos era CORTADA — fotografado. O valor agora é o que a tela
     media.  (noqa-acento: verbo medir, imperfeito) */
  .gd-pecas{width:255px}
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
  /* MESMA CURA, MESMO DIA: o endereço de rádio mede 118px em JetBrains Mono de
     10px mais a folga, e o `112` cortava o último octeto com reticências. */
  .gd-id{width:118px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:10px;
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
  /* O GLIFO SOME NO LUGAR SEM CONTROLE — 05/09/2026, palavra dela.
     `visibility` e não `display`: a fileira guarda a altura da linha, e um
     `display:none` faria as quatro linhas da tabela mudarem de altura conforme
     a mesa — a tabela inteira pulando quando um controle entra ou sai. */
  .tab.miuda tr.fora .gr{visibility:hidden}
"""

# O CADEADO, EM DOIS TRAÇOS — decisão [01] do PO, 04/09/2026. Ver o bloco
# `.trava` no CSS para a razão de ser SVG e não um caractere. `currentColor` nos
# dois traços é o que deixa a cor morar no CSS, como em todo glifo desta casa.
#: QUANTOS CARACTERES CABEM NAS DUAS LINHAS DA TIRA — MEDIDO, 06/09/2026.
#:
#: Medido no Chrome sobre `mockup/10-perfis.html`, acendendo a `.desfecho` e
#: procurando por bissecção o maior texto com `scrollHeight <= clientHeight`.
#: A tira mede **1140px** (o `.pagina` do `topo.html` é `width:1180px` menos os
#: `padding:0 14px` daqui e a folga do quadro), a 11px, com `line-height:15px` e
#: `-webkit-line-clamp:2` — e cabem **413 caracteres**; o 414º reticencia.
#:
#: ELE NÃO É DIGITADO NO COMENTÁRIO DE CIMA, e essa é a razão de existir: o
#: bloco da `.desfecho` dizia *"a linha de 1.180px a 11px comporta ~200"*, e o
#: `~200` era estimativa — dobrada, dava 400, e foi com esse número que a sprint
#: 10-Q5 declarou que DUAS frases do produto passavam do teto. **Medidas, elas
#: não passavam**: a carona reposta de UM jogo dá 227 caracteres com a frase de
#: ativação grudada, e a regressão de UM jogo dá 364. Quem estoura é o NÚMERO DE
#: JOGOS — a lista não tem teto (`steam_launch_options.lista_de_jogos`) —, e a
#: metade curta da 10-Q5 empurra a fronteira de TRÊS jogos para CINCO.
#:
#: É O TETO NA LARGURA DO DESENHO, e portanto o melhor caso: o `.pagina` é
#: `max-width:100%`, então uma janela mais estreita comporta menos.
CABEM_NA_TIRA = 413

CADEADO = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
           '<path d="M3.6 5.2V3.9a2.4 2.4 0 0 1 4.8 0v1.3" fill="none" '
           'stroke="currentColor" stroke-width="1.2"/>'
           '<rect x="2.3" y="5.2" width="7.4" height="5.4" rx="1.1" '
           'fill="currentColor"/></svg>')


# ---------------------------------------------------------------------------
# OS TRÊS DESENHOS DE 11/09/2026 — PERFIS-LIMPA-01, e os três são ordem dela:
#
#     "Na tabela do perfil tem que terum svg dde lupa no titulo da tabela.  # (noqa-acento) citação literal dela
#      Temos que remover esse botão voltar a de ontem ??? e o botão  # (noqa-acento) citação literal dela
#      recarregar vira um svg clicável ao lado de Perfis Salvos que irá  # (noqa-acento) citação literal dela
#      fazer essa função. Temos que deixar o layout mais limpo.."  # (noqa-acento) citação literal dela
#
# O TAMANHO DO DESENHO É O DO `CADEADO` — 11px. É o único ícone que esta aba já
# tinha, e um segundo tamanho ao lado dele seria a tela com dois vocabulários de
# desenho na mesma linha. **O ALVO DO CLIQUE NÃO É O DESENHO**: quem lhe dá os
# 24x24 é a regra `.icone-rot` do CSS, e a razão está escrita lá.
#
# `currentColor` EM TODOS: os três nascem dentro do `.sec-rot`, que é verde por
# decisão dela. Um hexadecimal aqui seria o ícone discordando do título ao lado
# no dia em que a cor do bloco mudar.
LUPA = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
        '<circle cx="5.2" cy="5.2" r="3.4" fill="none" stroke="currentColor" '
        'stroke-width="1.3"/>'
        '<path d="M7.8 7.8 L10.6 10.6" stroke="currentColor" stroke-width="1.3" '
        'stroke-linecap="round"/></svg>')

RECARREGA = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
             '<path d="M9.8 6a3.8 3.8 0 1 1-1.2-2.8" fill="none" '
             'stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
             '<path d="M9.4 1.3v2.6H6.8" fill="none" stroke="currentColor" '
             'stroke-width="1.3" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')

DESFAZ = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
          '<path d="M2.2 6a3.8 3.8 0 1 0 1.2-2.8" fill="none" '
          'stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
          '<path d="M2.6 1.3v2.6h2.6" fill="none" stroke="currentColor" '
          'stroke-width="1.3" stroke-linecap="round" '
          'stroke-linejoin="round"/></svg>')


def icone_do_rotulo(gesto: str, desenho: str, dica: str) -> str:
    """Um ícone clicável no título de um bloco — o invólucro novo de um botão.

    **O NOME DO GESTO NÃO MUDA, e é a metade que a §3 da sprint cobra.**
    `data-hef-gesto="recarregar"` e `data-hef-gesto="voltar-a-de-ontem"` são os
    mesmos de quando eram botões: o `recarregar` levou até 31/08 para ganhar
    dono e não vai perdê-lo por troca de invólucro.

    **A DICA VAI JUNTO, PALAVRA POR PALAVRA.** Um ícone sem dica é uma função
    que ninguém acha — é o custo inteiro de trocar palavra por desenho, e ele se
    paga assim.

    `<button>` E NÃO `<span>`: ele recebe foco pelo teclado e o leitor de tela o
    anuncia como botão, que é o que ele é. O `aria-label` repete a dica porque
    `title` não é nome acessível confiável, e o desenho é `aria-hidden`.
    """
    return (f'<button type="button" class="icone-rot" '
            f'data-hef-gesto="{gesto}" title="{dica}" '
            f'aria-label="{dica}">{desenho}</button>')


def icone_da_lupa() -> str:
    """A lupa do título da tabela dos perfis. Ela ABRE o campo, e nada mais.

    ORDEM DELA: *"Na tabela do perfil tem que terum svg dde lupa no titulo da  # (noqa-acento) citação literal dela
    tabela"*, e *"Procura nome de perfil, e demais configs dos perfis, a ideia é  # (noqa-acento) citação literal dela
    acharmos rápido o nome de um jogo"*.  # (noqa-acento) citação literal dela

    **ELA NÃO TEM GESTO, e é a única coisa clicável desta aba que não tem.**
    Abrir e fechar um campo não é trabalho do Python: é um `classList.toggle`
    que não toca o disco, não fala com o daemon e não muda uma letra do que a
    tela AFIRMA. Mandá-lo a Python custaria uma travessia de fronteira e 100 ms
    de espera para acender uma borda. Quem procura de verdade é o campo ao lado,
    e esse tem dono (`procurar`).

    **E O ENDEREÇO DELA É A CLASSE, e isso foi MEDIDO em 11/09/2026.** A
    primeira versão usava `data-papel="abrir-a-lupa"`, e `data-papel` está na
    lista de atributos que o ouvinte do piloto casa (`manda_do_alvo`): cada
    clique na lupa chegava ao Python como um gesto sem dono e imprimia
    `[gesto sem dono] 10-perfis.html · abrir-a-lupa` no stdout de quem lançou a
    janela — exatamente o defeito que o `recarregar` levou até 31/08 para
    perder. A classe `.lupa` não está em lista nenhuma do piloto, e o roteiro a
    acha pelo mesmo seletor.
    """
    return ('<button type="button" class="icone-rot lupa" '
            'title="Procurar um perfil pelo nome, pela prioridade ou pelo jogo." '
            f'aria-label="Procurar um perfil">{LUPA}</button>')


def campo_da_lupa() -> str:
    """O campo que a lupa abre — fechado no desenho, e é decisão dela.

    **SEM CAMPO NA TELA ATÉ ELA CLICAR**: um campo de busca sempre visível
    ACRESCENTA uma linha ao bloco em vez de tirar, e a ordem era *"deixar o  # (noqa-acento) citação literal dela
    layout mais limpo"*.  # (noqa-acento) citação literal dela

    `data-hef-vivo` E NÃO `data-hef-gesto`: a quarta porta do piloto é a única
    que dispara a cada TECLA, e ela é de LEITURA por contrato. As outras três
    despacham no clique, no `change` e no `blur` — nenhuma delas serve a quem
    digita e quer ver a lista encolher enquanto digita.

    `data-hef-alvo="valor"` PARA O CAMINHO DE VOLTA: o produto reescreve aqui o
    termo que ele está aplicando. Ele nunca atropela o que ela está digitando —
    o `escrever()` do piloto devolve 0 para o elemento que tem o foco
    (`sob_o_dedo`) —, e é isso que faz o campo e a lista dizerem a mesma coisa
    depois de um repinte.
    """
    return ('<input type="text" class="procura" data-hef="perfis.procura" '
            'data-hef-alvo="valor" data-hef-vivo="procurar" '
            'placeholder="procurar" aria-label="Procurar um perfil" value="">')


def puxador(coluna: str, tabela: str) -> str:
    """A divisa arrastável no canto direito de um `<th>`.

    **ELE É O ELEMENTO DO GESTO, e não um irmão dele.** Arrastar termina num
    `mouseup` sobre este mesmo nó, e é dele que o roteiro atualiza o `data-px`
    antes de chamar `.click()` — um segundo elemento escondido para levar o
    número seria um nó a mais para envelhecer separado.

    **E UM CLIQUE SEM ARRASTE É INÓCUO POR CONSTRUÇÃO**: em repouso o `data-px`
    carrega a largura que a coluna JÁ tem, então o clique regrava o que já
    estava no disco. É o que autoriza este gesto a não declarar `grava=` e a
    continuar sendo provado botão a botão — a mesma medição que isenta os três
    `machine.declare` idempotentes da régua de 03/09.

    A ÚLTIMA COLUNA NÃO GANHA DIVISA: arrastar a borda direita da tabela não
    tem o que redistribuir, e uma alça ali some junto com a barra de rolagem.
    """
    return (f'<span class="puxador" data-hef-gesto="largura-da-coluna" '
            f'data-tabela="{tabela}" data-coluna="{coluna}" data-px="0" '
            f'role="separator" aria-label="Arraste para mudar a largura da coluna"></span>')


def cabeca(coluna: str, rotulo_visivel: str, tabela: str, classe: str = "",
           divisa: bool = True) -> str:
    """Um `<th>` da lista de perfis: o nome, a seta da ordem e a divisa.

    ORDEM DELA: *"essa tabela precisa permitir que eu escolha a ordenação dando  # (noqa-acento) citação literal dela
    duplo clique no nome das colunas."*  # (noqa-acento) citação literal dela

    **A SETA É QUEM CARREGA O GESTO, e ela é `pointer-events:none`** — ver a
    regra `.ordena` no CSS, que tem a razão inteira. Em uma linha: o ouvinte do
    piloto despacha no PRIMEIRO clique, e o cabeçalho está a um pixel da célula
    do nome, que troca o perfil aberto no editor. Nenhum mouse alcança este nó;
    quem o aciona é o roteiro, no `dblclick`, e é o que faz o duplo clique que
    ela pediu ser duplo de verdade.

    O `title` DIZ O GESTO. Um cabeçalho que ordena e não avisa é uma função que
    ninguém acha — o mesmo custo que a §3 cobra dos dois ícones.
    """
    cls = f' class="{classe}"' if classe else ""
    return (f'<th{cls} data-coluna="{coluna}" '
            f'title="Duplo clique para ordenar por esta coluna; de novo, inverte.">'
            f'{rotulo_visivel}'
            f'<span class="ordena" data-hef="perfis.ordem.{coluna}" '
            f'data-hef-alvo="atributo" data-hef-atributo="data-ordem" '
            f'data-hef-gesto="ordenar" data-coluna="{coluna}"></span>'
            f'{puxador(coluna, tabela) if divisa else ""}</th>')


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


def rotulo_do_jogo() -> str:
    """O nome do jogo à direita do campo — decisão 10-Q4 dela, 06/09/2026.

    TRÊS `<span>` E DOIS ENDEREÇOS, e cada casca faz UMA coisa porque
    `data-hef-alvo` é UM por elemento:

    * o de fora ACENDE (`editor.jogo.rotulo`, alvo `classe`) — sem ele, um
      rótulo vazio vira um travessão solto entre o campo e o "Detectar", porque
      `escrever()` troca `''` por `'—'` antes de escolher o ramo;
    * o do meio PINTA (`editor.jogo.alerta`, alvo `classe`, classe `alerta`) —
      é o booleano que `frase_do_campo_do_jogo` devolve e que
      `_jogo_reconhecido` jogava fora até hoje, e é ele que separa *"não
      instalado aqui (o número vale)"*, que é rotina, de *"não reconheci este
      endereço"*, que é erro;
    * o de dentro ESCREVE (`editor.jogo.rotulo`, alvo padrão).

    O ENDEREÇO REPETIDO É A FORMA DA CASA, e não uma invenção deste rótulo: a
    tira do desfecho desta MESMA página faz exatamente isto — o `classe` acende,
    o `<span>` de dentro escreve —, e há régua cobrando as duas ocorrências.

    NASCE VAZIO, pela mesma razão da `.dica` de `marca_com_dica`: o desenho não
    sabe que jogo é o dela, e um exemplo aqui seria a tela afirmando um jogo que
    o perfil não tem.
    """
    return ('<span class="rot" data-hef="editor.jogo.rotulo"'
            ' data-hef-alvo="classe">'
            '<span class="al" data-hef="editor.jogo.alerta"'
            ' data-hef-alvo="classe" data-hef-classe="alerta">'
            '<span data-hef="editor.jogo.rotulo"></span></span></span>')


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

#: AS OPÇÕES DO "Funciona em". Todas menos "Estilo de Jogo" têm preset atrás em
#: `perfis_web.AMBIENTE_DO_PRESET` — e a régua
#: `test_toda_forma_que_o_produto_escreve_tem_rotulo_nas_duas_telas` cobra os
#: dois sentidos, para nenhuma forma nova nascer órfã de rótulo.
#:
#: **A SEXTA NASCEU EM 06/09/2026** — "Jogo (pela janela)", a ONDA5-10-01. Ela é
#: o que o botão "Detectar" produz quando o jogo NÃO é da Steam: uma classe de
#: janela só. Sem esta linha, gravar a forma nova abriria o perfil com o seletor
#: travado — a tela ganhando uma regra que não sabe mostrar, que é o estrago que
#: a própria recusa do "Detectar" previa.
AMBIENTES = ["Todos","Steam","Estilo de Jogo","Jogo","Jogo da Steam",
             "Jogo (pela janela)"]
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
    # A CLASSE `fora` PASSA A SER PINTÁVEL — 05/09/2026, palavra dela: *"os svgs
    # não deveriam aparecer prós demais controles desconectados"*.
    #
    # ATÉ AQUI ELA ERA SÓ DO DESENHO. O piloto não repintava a classe da `<tr>`,
    # então uma linha que o MOCKUP desenhou como conectada continuava sem `fora`
    # com a mesa vazia — e a fileira de glifos daquele lugar ficava na tela,
    # apagada mas DESENHADA, ao lado de um nome que já dizia `—`. O produto
    # mostrando um controle que não está aqui.
    #
    # O ENDEREÇO É PRÓPRIO (`guarda.vazio`) E O ALVO É `classe`, com
    # `data-hef-classe="fora"` — o pintor liga UMA classe por elemento, e é esta.
    # Quem manda o valor é `a10_perfis`, que agora emite as QUATRO linhas em vez
    # de só as da mesa: sem as quatro, o `forEach` do bootstrap escreveria `''`
    # no que sobra e a linha vazia voltaria a não ser marcada.
    return f'''                  <tr data-hef-uniq="{endereco}" data-hef="guarda.vazio" data-hef-alvo="classe" data-hef-classe="fora"{'' if na_mesa else ' class="fora"'}{dica}>
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
       `[data-gesto],[data-hef-gesto],[data-papel],…` (`hefesto_vivo.py:1000`), e
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


# ---------------------------------------------------------------------------
# O ROTEIRO DA PÁGINA — PERFIS-LIMPA-01, 11/09/2026, e ele é a primeira linha de
# JavaScript que uma página desta casa emite.
#
# ONDE ELE VIVE, e a decisão foi MEDIDA duas vezes:
#
# 1. **a colisão.** As outras duas casas possíveis estavam ocupadas nesta mesma
#    leva — o `BOOTSTRAP` (`hefesto_vivo.py`, posse da MIC-SEM-FONTE-01) e um
#    `js_extra` no `monta()` (posse da VAO-DO-ESQUELETO-01). Sobrou a terceira,
#    e ela é melhor que as duas: `monta` insere o `miolo` VERBATIM dentro do
#    `<p class="miolo">` (`monta.py`, o `doc = t + …`), então a aba emite o que
#    quiser ali sem tocar em arquivo de ninguém. O comportamento da aba 10 fica
#    COM a aba 10, e o piloto continua genérico — que é o que ele é por desenho;
# 2. **o WebKit executa.** Medido em 11/09/2026 no `WebKit2.WebView` montado
#    como o piloto o monta (`gui.ponte_da_tela.PonteDaTela`), com a página vinda
#    de `file://`: um `<script>` inline roda, e roda com `document.readyState`
#    em `"loading"` — ou seja, ANTES do `LoadEvent.FINISHED` em que o piloto
#    instala o `BOOTSTRAP`. É por isso que este roteiro não pode CONTAR com o
#    `window.__hef`: quando ele corre, o piloto ainda não chegou.
#
# O QUE ELE FAZ, e são só três coisas — **nenhuma delas decide o que a lista
# mostra**:
#
#     abrir e fechar o campo da lupa
#     traduzir o DUPLO clique do cabeçalho num clique no elemento do gesto
#     arrastar a divisa entre duas colunas
#
# FILTRAR E ORDENAR NÃO ESTÃO AQUI, e isso é uma linha da sprint que caiu por
# medição — a razão inteira está em `pacotes/a10_perfis`, no bloco da lupa. Em
# uma frase: o pintor distribui as três colunas da lista pela ordem do
# DOCUMENTO, então reordenar as `<tr>` no DOM põe o nome de um perfil na linha
# de outro no tique seguinte.
#
# E É POR ISSO QUE ELE NÃO PRECISA DE REAPLICADOR. A armadilha que a §6 da
# sprint descreve — *"filtro aplicado ao DOM, ordem aplicada ao DOM e largura
# aplicada ao DOM morrem no primeiro repinte"* — alcança duas das três, e as
# duas saíram do DOM. A que sobrou, a largura, mora no `<colgroup>`, e o
# `blocos` desta aba troca o `<tbody>` e o `<datalist>` — nunca o `<colgroup>`.
# **O que muda a largura de fora é o ATRIBUTO `data-larguras`**, escrito pelo
# pintor, e é nele que este roteiro observa. Medido, não suposto.
#
# NADA DE `<` SOLTO AQUI DENTRO: o balanço de `<p>` do `monta()` conta
# SUBSTRING no documento inteiro, e um `a < b` em JavaScript não o atrapalha,
# mas um `'<p'` numa string, sim. Use `>` ao contrário quando precisar comparar.
ROTEIRO = """
  <script>
  (function(){
    'use strict';
    var PISO = 48, TETO = 900;

    // ---- a lupa: abre, fecha e limpa --------------------------------------
    // FECHAR LIMPA, e é decisão: um campo fechado com termo dentro é uma lista
    // curta sem nada na tela dizendo por quê. O `input` sintético é o que avisa
    // o Python — é o mesmo evento que a digitação dispara, pela mesma porta.
    function oCampo(){ return document.querySelector('.procura'); }
    document.addEventListener('click', function(ev){
      var b = ev.target.closest ? ev.target.closest('.icone-rot.lupa') : null;
      if(!b) return;
      var campo = oCampo();
      if(!campo) return;
      var abrindo = !campo.classList.contains('on');
      campo.classList.toggle('on', abrindo);
      b.classList.toggle('on', abrindo);
      if(abrindo){ campo.focus(); return; }
      if(campo.value !== ''){
        campo.value = '';
        campo.dispatchEvent(new Event('input', {bubbles: true}));
      }
    }, false);

    // ---- o duplo clique do cabeçalho --------------------------------------
    // ELE NÃO ORDENA: ele CLICA no elemento que carrega o gesto, e quem ordena
    // é o Python. A seta é `pointer-events:none`, então este `.click()` é o
    // único caminho até ela — um clique simples no cabeçalho não chega lá, que
    // é exatamente o que ela pediu ao dizer DUPLO clique.
    document.addEventListener('dblclick', function(ev){
      var th = ev.target.closest ? ev.target.closest('th[data-coluna]') : null;
      if(!th) return;
      var seta = th.querySelector('.ordena[data-hef-gesto]');
      if(seta) seta.click();
    }, false);

    // ---- a divisa arrastada -----------------------------------------------
    // O CURSOR MUDA PORQUE A ALÇA EXISTE (`cursor:col-resize` no `.puxador`), e
    // é o que ela descreveu. Enquanto arrasta, quem desenha é este roteiro, no
    // `<col>`; ao soltar, o número vai para o Python, que o apara pelo piso e o
    // grava. O piso está nos DOIS lados de propósito: aqui para o desenho não
    // passar dele durante o arraste, e lá porque o disco é para sempre.
    var voo = null;
    function colDe(pux){
      var tab = pux.closest('table');
      var col = tab ? tab.querySelector('col[data-coluna="' + pux.dataset.coluna + '"]') : null;
      return {tabela: tab, col: col};
    }
    document.addEventListener('mousedown', function(ev){
      var pux = ev.target.closest ? ev.target.closest('.puxador') : null;
      if(!pux) return;
      var alvo = colDe(pux);
      if(!alvo.col) return;
      var th = pux.closest('th');
      voo = {pux: pux, col: alvo.col, x: ev.clientX,
             largura: th ? th.getBoundingClientRect().width : 0};
      document.body.classList.add('arrastando');
      ev.preventDefault();
    }, false);
    document.addEventListener('mousemove', function(ev){
      if(!voo) return;
      var px = Math.round(voo.largura + (ev.clientX - voo.x));
      if(px < PISO) px = PISO;
      if(px > TETO) px = TETO;
      voo.col.style.width = px + 'px';
      voo.pux.dataset.px = String(px);
    }, false);
    document.addEventListener('mouseup', function(){
      if(!voo) return;
      var pux = voo.pux;
      voo = null;
      document.body.classList.remove('arrastando');
      pux.click();
    }, false);

    // ---- as larguras que voltam do disco ----------------------------------
    // O FORMATO É `coluna:px` separado por `·`, e o travessão é o VAZIO — o
    // `escrever()` do piloto escreve `—` no lugar de um valor em branco, e ler
    // isso como uma largura poria a coluna em zero em toda janela de quem nunca
    // arrastou nada.
    function espalhar(tab){
      var bruto = tab.getAttribute('data-larguras') || '';
      if(!bruto || bruto === '\\u2014') return;
      bruto.split('\\u00b7').forEach(function(par){
        var pedaco = par.split(':');
        if(pedaco.length !== 2) return;
        var px = parseInt(pedaco[1], 10);
        if(!isFinite(px)) return;
        if(px < PISO) px = PISO;
        if(px > TETO) px = TETO;
        var col = tab.querySelector('col[data-coluna="' + pedaco[0] + '"]');
        if(col) col.style.width = px + 'px';
        var pux = tab.querySelector('.puxador[data-coluna="' + pedaco[0] + '"]');
        if(pux) pux.dataset.px = String(px);
      });
    }
    // E AS QUE NUNCA SAÍRAM DO DISCO: em repouso o `data-px` da alça tem de
    // dizer a largura que a coluna JÁ tem, senão o primeiro clique sem arraste
    // gravaria zero. É o que torna o gesto idempotente, e é o que autoriza a
    // régua de clique a acioná-lo.
    function medir(tab){
      tab.querySelectorAll('.puxador').forEach(function(pux){
        var th = pux.closest('th');
        if(!th) return;
        var px = Math.round(th.getBoundingClientRect().width);
        if(px > 0 && (pux.dataset.px || '0') === '0') pux.dataset.px = String(px);
      });
    }
    function tabelas(){ return document.querySelectorAll('table[data-tabela]'); }
    function assentar(){ tabelas().forEach(function(t){ espalhar(t); medir(t); }); }
    // O OBSERVADOR VIGIA O ATRIBUTO, e só ele. Uma largura que volta do disco
    // chega por `data-larguras` (o pintor escreve o atributo), e é o único
    // caminho de fora para dentro — o `blocos` desta aba não toca o
    // `<colgroup>`. Vigiar o `<tbody>` seria acordar dez vezes por segundo
    // para não fazer nada.
    tabelas().forEach(function(t){
      new MutationObserver(function(){ espalhar(t); }).observe(
        t, {attributes: true, attributeFilter: ['data-larguras']});
    });
    if(document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', assentar);
    } else { assentar(); }
  })();
  </script>
"""


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
              <div class="sec-rot">Perfis Salvos{icone_da_lupa()}{campo_da_lupa()}{icone_do_rotulo(
                  "recarregar", RECARREGA,
                  "Relê a lista do disco. Não descarta o que está no editor ao lado.")}<span class="fora-da-busca" data-hef="perfis.procura.conta" data-hef-alvo="classe"><span data-hef="perfis.procura.conta"></span></span></div>
              <div class="lista">
              <div class="rolo">
              <table class="tab" data-hef="perfis.larguras" data-hef-alvo="atributo"
                     data-hef-atributo="data-larguras" data-tabela="10-perfis.lista"
                     data-larguras="">
                <colgroup><col data-coluna="nome"><col data-coluna="prioridade"><col data-coluna="quando"></colgroup>
                <thead><tr>{cabeca("nome", "Nome", "10-perfis.lista")}{cabeca(
                    "prioridade", "Priorização", "10-perfis.lista", classe="pri")}{cabeca(
                    "quando", "Quando usar", "10-perfis.lista", divisa=False)}</tr></thead>
                <tbody data-hef="perfis.lista">
{chr(10).join(linha_do_perfil(n, p, q, a, escolhido=n == PERFIL_DO_EDITOR) for n,p,q,a in PERFIS)}
                </tbody>
              </table>
              </div>
              </div>
              <div class="botoes">
                <button class="btn" data-hef-gesto="duplicar" title="Copia o perfil inteiro para o editor, com &quot;(cópia)&quot; no nome.">Duplicar</button>
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
              <div class="sec-rot">Definições{icone_do_rotulo(
                  "voltar-a-de-ontem", DESFAZ,
                  "Desfaz um perfil salvo por engano: cada gravação já guarda a anterior.")}</div>
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
                  <!-- A LISTA DOS JOGOS DESTA MÁQUINA — PERFIL-MODO-01, Passo 3
                       (06/09/2026). A janela GTK tem `Gtk.EntryCompletion` sobre
                       este mesmo campo (`profiles_actions._instalar_lista_de_
                       jogos_do_pc`), alimentada por `integrations/jogos_locais.
                       catalogo_de_jogos()`; aqui o campo era texto LIVRE, e
                       criar um perfil de jogo exigia saber o appid de cor.

                       `<datalist>` E NÃO UM `<select>`, e a escolha é a do
                       enunciado dela: *"uma lista que recusa o que ela sabe que
                       existe é pior que campo livre"*. O `<datalist>` OFERECE
                       sem fechar — o `<input>` continua aceitando qualquer
                       texto, inclusive o appid de um jogo que ela ainda vai
                       comprar (`MSG_FORA_DA_MAQUINA` existe para esse caso).

                       ELE NASCE VAZIO NO DESENHO, e é a mesma disciplina do
                       `title=""` da linha da lista e da `.dica` do cadeado: o
                       conteúdo é a biblioteca DELA, e um exemplo cravado aqui
                       seria a tela afirmando que ela tem um jogo que talvez não
                       tenha. Quem o enche é `a10_perfis`, pelo `blocos` — o
                       mesmo caminho da lista de perfis, e pelo mesmo motivo: um
                       bloco cujo número de filhos muda com o dado não tem
                       endereço para o filho que ainda não existe. -->
                  <input type="text" data-hef="editor.jogo" data-hef-gesto="editor.jogo"
                         data-hef-alvo="valor" list="jogos-desta-maquina"
                         value="Mortal Kombat 1">{marca_com_dica(
                           "exige", "editor.jogo.exige", "editor.jogo.exigencia")}
                  <datalist id="jogos-desta-maquina" data-hef="editor.jogo.lista"></datalist>
                  {rotulo_do_jogo()}
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
                <table class="tab miuda" data-hef="guarda.larguras" data-hef-alvo="atributo"
                       data-hef-atributo="data-larguras" data-tabela="10-perfis.guarda"
                       data-larguras="">
                  <colgroup><col data-coluna="controle"><col data-coluna="status"><col data-coluna="id"></colgroup>
                  <thead><tr>
                    <th title="O perfil não guarda uma configuração: guarda uma por controle. Esta tabela mostra, para cada controle, quais ajustes ele tem só para si e quais usa do perfil.">Controle{puxador("controle", "10-perfis.guarda")}</th>
                    <th class="gd-pecas" title="Aceso: este perfil guarda um ajuste só deste controle. Apagado: ele usa o do perfil, igual aos outros. São os {QUANTAS_SECOES} ajustes que o perfil sabe guardar por controle — {_lista_das_secoes()}.">Status{puxador("status", "10-perfis.guarda")}</th>
                    <th class="gd-id" title="O endereço de rádio do controle. É por ele que o perfil reconhece a peça — e ele não muda quando você troca o cabo pelo rádio, então o que você deixou hoje volta amanhã.">ID da peça</th>
                  </tr></thead>
                  <tbody data-hef="guarda.linhas">
{chr(10).join(linha_do_controle(c) for c in MESA)}
                  </tbody>
                </table>
              </div>

              </div>
              <!-- OS TRÊS VIRARAM UM — 11/09/2026, ordem dela. O `Recarregar` foi
                   para o rótulo `Perfis Salvos` (ele relê a LISTA, e a lista é a
                   tabela da esquerda) e o `Voltar à de ontem` para o rótulo
                   `Definições` — *"tem que arrumar outro canto pra deixar ele ao  (noqa-acento) citação
                   invés de botão como os demais"*. Sobrou UM botão neste canto, e  (noqa-acento) citação
                   a classe `um-so` o faz ocupar a largura inteira em vez de um
                   terço com dois vãos vazios ao lado.

                   QUEM FICA NELE É O `Ativar`, E FOI ELA QUEM TROCOU — 11/09,
                   depois de ver: *"trocar o botão do novo Duplicar que ficou  (noqa-acento) citação
                   gigante pelo ativar e deixar ele verde"*. O `Duplicar` desceu  (noqa-acento) citação
                   para a fileira da esquerda, no lugar que o `Ativar` deixou —
                   os quatro gestos continuam na tela, nenhum se perdeu na troca.

                   E A TROCA TEM RAZÃO DE PRODUTO, não só de tamanho: o botão
                   largo é o da AÇÃO PRINCIPAL desta aba, e a ação principal de
                   um perfil é passar a usá-lo. Duplicar é o gesto raro; ele
                   cabe na fileira com o `Novo` e o `Remover`, que são os outros
                   dois que mexem na LISTA da esquerda. O `Ativar` fica verde
                   (`btn verde`) — a mesma classe que ele já tinha à esquerda,
                   para a cor não mudar de significado ao mudar de lugar. -->
              <div class="botoes um-so">
                <button class="btn verde" data-hef-gesto="ativar" title="Passa a usar este perfil agora, em todas as abas.">Ativar</button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
{ROTEIRO}
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
  <h2>O que mudou com quatro controles ligados</h2>
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
      <code>a10_perfis</code>, com o que leu dos controles — a mesma leitura da fita do topo.
      Sem cor lida, a barra <b>some</b>: campo sem informação não mostra nada.</li>
    <li><b>O cabeçalho conta os controles</b>: {len(PERFIS)} perfis e
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
    <li><b>O quadro "Modo"</b>, com os quatro botões — fora: <span class="marca">isso está na aba Jogar</span>, palavra sua.
      O que este perfil já guarda continua guardado — nenhum botão desta aba mexe nisso.
      <span class="marca">Quem escreve o modo é a Jogar, e ela escreve no perfil que está valendo</span>.</li>
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
    <li><b>"O jogo vê o controle como" não está desenhado aqui.</b> Ele mora hoje na
      <b>Jogar</b>; se vem também para cá, é decisão sua, e a tela não decide por você.
      <span class="marca">O "Modo que liga" saiu desta lista</span> — você já decidiu, e
      ele está no bloco de cima.</li>
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
    # O CABEÇALHO POR EXTENSO — e a régua passou a ler o ELEMENTO, não a
    # colagem `class="pri">Priorização<`. Ela quebrou em 11/09/2026 quando o
    # `<th>` ganhou `data-coluna` e `title`: a palavra continuava na tela e a
    # régua acusava abreviação. É a forma que esta casa nomeia — *a régua digita
    # o que devia LER* —, e a cura é olhar o `<th>` da coluna inteira.
    th_pri = re.search(r'<th class="pri"[^>]*>([^<]*)', html)
    exigir(th_pri is not None, "o cabeçalho da Priorização sumiu da tabela")
    if th_pri:
        exigir(th_pri.group(1).strip() == "Priorização",
               f"o cabeçalho voltou a ser abreviado: {th_pri.group(1)!r}")

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

    # OS QUATRO LUGARES TÊM O MESMO CONJUNTO DE ENDEREÇOS — 07/09/2026, e esta
    # régua nasce de um defeito MEDIDO em outras abas, não nesta.
    #
    # O QUE ACONTECEU LÁ, com os quatro DualSense dela na mesa: o daemon publica
    # quatro controles, a carga chega com os quatro em `colunas`/`mesa`, e a tela
    # mostra DOIS. A causa é sempre a mesma forma — o gerador tem um ramo
    # SEPARADO para o lugar vazio, que devolve um cartão sem nenhum endereço por
    # dentro. O dado dela chega e não tem onde pousar: o pintor procura o
    # endereço DENTRO do bloco daquele controle (`hefesto_vivo.achar`), e um
    # bloco sem endereço come a carga em silêncio. Dois ramos que duplicam
    # estrutura envelhecem separados, e foi um deles que envelheceu.
    #
    # AQUI O DEFEITO NÃO EXISTE, e a razão é de construção: `linha_do_controle`
    # é UMA função só, com UM `return`, e `na_mesa` decide apenas o TEXTO
    # (`nome`), a cor (`plastico`), a dica e a classe `fora` — nunca a
    # estrutura. Os quatro lugares saem com os mesmos dez endereços.
    #
    # ENTÃO POR QUE A RÉGUA: porque nada segurava isso. A ausência do defeito
    # era um efeito colateral de a função ter um `return` só, e o primeiro `if
    # na_mesa:` que alguém escrevesse em volta do miolo o traria de volta sem
    # reprovar nada — as réguas acima contam `Desconectado`, `class="fora"`,
    # `guarda.plastico` e `guarda.secao`, e TODAS continuariam verdes com o
    # `guarda.nome` e o `guarda.id` do lugar vazio arrancados. É a lei desta
    # casa: quando a cura conhece a causa, ela vira régua, senão volta.
    #
    # ELA COBRA A CONTAGEM, E NÃO SÓ O CONJUNTO. `guarda.secao` aparece seis
    # vezes por linha, uma por seção, e o pintor distribui a lista pela ordem do
    # documento (`hefesto_vivo.py`, `alvos.forEach`): um lugar com cinco células
    # em vez de seis não perde um endereço — ele DESLOCA todas as células
    # seguintes de todos os lugares seguintes, e a tela passa a acender a seção
    # errada no controle errado. Um conjunto igual com contagens diferentes é o
    # pior dos dois defeitos, porque não deixa buraco: deixa mentira.
    blocos_por_lugar = {
        m.group(1): re.findall(r'data-(?:campo|papel|hef)="([^"]+)"', m.group(0))
        for m in re.finditer(r'<tr data-hef-uniq="(p\d)".*?</tr>', html, re.S)
    }
    exigir(len(blocos_por_lugar) == len(MESA),
           f"não são {len(MESA)} lugares endereçados na tabela por controle, "
           f"e sim {len(blocos_por_lugar)}")
    if len(blocos_por_lugar) == len(MESA):
        assinaturas = {pref: tuple(sorted(collections.Counter(campos).items()))
                       for pref, campos in blocos_por_lugar.items()}
        modelo = assinaturas[MESA[0]["pref"]]
        divergentes = sorted(p for p, a in assinaturas.items() if a != modelo)
        exigir(not divergentes,
               f"os lugares {divergentes} não têm os MESMOS endereços do "
               f"{MESA[0]['pref']} — um lugar com endereço a menos come a carga "
               f"dela em silêncio, e um com contagem diferente desloca as "
               f"células de `guarda.secao` de todos os lugares seguintes. "
               f"Endereços por lugar: "
               f"{ {p: sum(c for _k, c in a) for p, a in assinaturas.items()} }")

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

    # O RÓTULO DO JOGO — decisão 10-Q4 dela, 06/09/2026. As três coisas que o
    # fazem funcionar, e as três somem caladas: os DOIS `editor.jogo.rotulo` (o
    # `classe` acende, o `<span>` escreve — sem o primeiro ele mostra um
    # travessão em todo perfil que não é da Steam), a tinta do alerta, e o
    # NASCER VAZIO.
    exigir(html.count('data-hef="editor.jogo.rotulo"') == 2,
           "o rótulo do jogo perdeu um dos dois endereços — sem o `classe` ele "
           "fica aceso com um travessão solto ao lado do campo; sem o `<span>` "
           "ele nunca escreve o nome do jogo")
    exigir('<span class="rot" data-hef="editor.jogo.rotulo"'
           ' data-hef-alvo="classe">' in html,
           "o rótulo do jogo perdeu o alvo `classe` — ele apareceria em todo "
           "perfil, inclusive nos que não têm jogo nenhum a nomear")
    exigir('data-hef="editor.jogo.alerta" data-hef-alvo="classe"'
           ' data-hef-classe="alerta"' in html,
           "o rótulo do jogo perdeu a tinta do alerta — «não reconheci este "
           "endereço» sairia da mesma cor de «não instalado aqui», e o erro "
           "ficaria com a cara da rotina")
    exigir('<span data-hef="editor.jogo.rotulo"></span>' in html,
           "o rótulo do jogo não nasce VAZIO no desenho — um exemplo aqui é a "
           "tela afirmando um jogo que o perfil dela não tem")
    # E ELE TEM TETO: sem a reticência, um nome longo empurra o "Detectar" para
    # fora do quadro. As três metades da mesma cura, e cada uma sozinha não faz
    # nada — `white-space:nowrap` sem `overflow:hidden` vaza, e as duas sem
    # `text-overflow` cortam no meio da letra.
    regra_rot = re.search(r"\.campo \.rot\{[^}]*\}", html)
    exigir(regra_rot is not None, "a regra do rótulo do jogo sumiu do CSS")
    if regra_rot:
        corpo_rot = regra_rot.group(0)
        for peca in ("white-space:nowrap", "overflow:hidden",
                     "text-overflow:ellipsis", "display:none", "min-width:0",
                     "max-width:45%"):
            exigir(peca in corpo_rot,
                   f"o rótulo do jogo perdeu `{peca}` — nome de jogo é dado "
                   f"dela e pode ser longo; sem as seis peças o rótulo empurra "
                   f"o `Detectar` para fora do quadro, come o campo, ou nasce "
                   f"visível")
    # A GRADE DO CAMPO NÃO PODE CRESCER COM O TEXTO — MEDIDO no Chrome em
    # 06/09/2026, e o defeito nasceu com o rótulo. `1fr` é `minmax(auto,1fr)`, e
    # o mínimo `auto` de uma pista é o MIN-CONTENT do que está dentro: com um
    # nome de 300 caracteres a segunda coluna foi de 412px a **1990px** numa
    # página de 1180px, levando o `Detectar` para fora do quadro. Enquanto os
    # campos eram `<input>` e `<select>` ninguém via — nenhum dos dois cresce
    # com o valor.
    exigir("grid-template-columns:var(--rot-p) minmax(0,1fr)" in html,
           "a fileira do campo voltou a `1fr` — uma pista de grade cresce com o "
           "MIN-CONTENT, e o rótulo do jogo é texto: a segunda coluna estoura a "
           "página e leva o `Detectar` junto")

    # O QUADRO DO MODO NÃO VOLTA — 11/09/2026, e estas quatro exigências são as
    # de 06/09 INVERTIDAS. Ordem dela, literal:
    #
    #     "em perfis ainda aparece modo. Isso deve aparecer só na aba jogar."
    #
    # AS DE 06/09 COBRAVAM O CONTRÁRIO, e cobravam com razão: elas nasceram para
    # impedir que o quadro sumisse calado depois de a PERFIL-MODO-01 o trazer.
    # A ordem dela as revoga; o que fica é a mesma vigilância virada — uma régua
    # que some é dívida, uma régua que inverte com a decisão registrada é o
    # contrato novo.
    #
    # POR QUE QUATRO E NÃO UMA: cada peça do quadro morria por um caminho
    # diferente, e cada caminho pode voltar sozinho. O `<div class="campo modo">`
    # volta com um `git revert`; o `data-modo` volta se alguém reaproveitar o
    # componente `.seg` nesta aba; o `data-hef="editor.modo"` volta se o pacote
    # for religado; e a regra `.campo.modo` volta num `merge` de CSS. As quatro
    # são a mesma decisão dela vista de quatro lados.
    exigir('<div class="campo modo">' not in html,
           "o quadro Modo voltou ao editor de Perfis — ele sai por ordem dela "
           "de 11/09/2026, e a aba onde o modo se escolhe é a Jogar")
    exigir('data-modo="' not in html,
           "um botão desta aba voltou a carregar `data-modo` — o atributo é do "
           "quadro que saiu; se for outro controle reusando o nome, ele precisa "
           "de nome próprio, porque a régua de ponteiros da casa o lê como modo")
    exigir('data-hef="editor.modo"' not in html,
           "o endereço `editor.modo` voltou à página — o gesto que o gravava "
           "saiu de `a10_perfis` junto com o quadro, e um endereço sem gesto é "
           "um botão que responde calado")
    exigir(".campo.modo" not in html,
           "a regra `.campo.modo` voltou ao CSS — ela reservava a altura solta "
           "da fileira de quatro botões, e era essa fileira (36px) que deixava "
           "a linha do P4 fora do quadro sempre que a tira do desfecho acendia")

    # E O QUE O PERFIL GUARDA CONTINUA GUARDADO: a legenda tem de dizer QUEM
    # escreve o modo agora. Sem esta linha a retirada vira sumiço — a tela
    # perderia o quadro e não diria para onde ele foi.
    exigir("O quadro &quot;Modo&quot;" in html or 'O quadro "Modo"' in html,
           "a legenda parou de dizer que o quadro Modo saiu e onde ele mora — "
           "quem abrir a aba depois de 11/09 procuraria um quadro que a versão "
           "anterior tinha, sem nada na tela que o mande à Jogar")

    # E A FRASE TEM DE DIZER O ALCANCE — 11/09/2026, achado da conferência.
    #
    # A primeira redação desta legenda dizia que quem ESCOLHE o modo é a Jogar,
    # sem qualificar o perfil, e isso é FALSO medido: quem escreve é
    # `pacotes/perfil.gravar_o_modo_no_ativo`, que resolve o alvo por
    # `nome_do_ativo(state)` — logo a Jogar grava a seção `mode` do perfil que
    # está VALENDO, e só dele. Para um perfil que ela seleciona na lista e não
    # ativou, nenhuma tela escolhe modo nenhum.
    #
    # A retirada do quadro é ordem dela e continua de pé; o que não pode ficar
    # de pé é a tela AFIRMANDO alcance que o produto não tem. Esta exigência é o
    # que impede a frase larga de voltar — e ela pede o ALCANCE escrito, não a
    # confissão de dívida: o que falta mora no mapa da paridade, nunca aqui.
    exigir("no perfil que está valendo" in html,
           "a legenda perdeu o ALCANCE do que a aba Jogar escreve — sem ele a "
           "frase promete que a Jogar escolhe o modo de QUALQUER perfil, e o "
           "escritor (`pacotes/perfil.gravar_o_modo_no_ativo`) só alcança o "
           "perfil ativo")
    exigir("quem o escolhe é a Jogar" not in html,
           "a frase larga voltou à legenda — ela afirma que a Jogar escolhe o "
           "modo de qualquer perfil, e a Jogar grava só no que está valendo")

    # A COLUNA DO NOME SE CENTRA NA LINHA — 11/09/2026, a segunda metade da
    # queixa dela. Um `<td>` com `display:flex` deixa de ser célula de tabela e
    # perde o `vertical-align:middle`: o nome pousa no TOPO da linha enquanto o
    # glifo e o ID se centram nela. Medido no WebKit: 3,13px de espalhamento com
    # as linhas apertadas, **8,13px** quando a saída do Modo lhes devolve
    # altura, 1,50px com esta regra. A cura da primeira queixa AGRAVAVA a
    # segunda; as duas fecham juntas ou nenhuma fecha.
    regra_nome = re.search(r"\.gd-nome\{[^}]*\}", html)
    exigir(regra_nome is not None, "a regra `.gd-nome` sumiu do CSS")
    if regra_nome:
        exigir("display:flex" not in regra_nome.group(0),
               "o `<td>` do nome voltou a `display:flex` — ele deixa de ser "
               "célula de tabela e o nome desalinha do glifo e do ID em 8px, "
               "que é a linha «quebrada» que ela fotografou")
        exigir("vertical-align:middle" in regra_nome.group(0),
               "o `<td>` do nome perdeu o `vertical-align:middle` — sem ele o "
               "texto pousa no topo da linha e as três colunas deixam de "
               "alinhar assim que a linha ganha altura")

    # A LISTA DOS JOGOS DESTA MÁQUINA — PERFIL-MODO-01, Passo 3. As duas metades
    # e cada uma sozinha não faz nada: o `<datalist>` sem o `list=` no campo é um
    # elemento invisível que ninguém consulta, e o `list=` sem o `<datalist>` é
    # um atributo que aponta para um id que não existe.
    exigir('<datalist id="jogos-desta-maquina" data-hef="editor.jogo.lista">'
           '</datalist>' in html,
           "a lista dos jogos desta máquina sumiu, ou deixou de nascer VAZIA — "
           "um exemplo cravado aqui é a tela afirmando um jogo que ela talvez "
           "não tenha")
    campo_do_jogo = re.search(r'<input[^>]*data-hef="editor\.jogo"[^>]*>', html)
    exigir(campo_do_jogo is not None, "o campo do jogo sumiu do editor")
    if campo_do_jogo:
        exigir('list="jogos-desta-maquina"' in campo_do_jogo.group(0),
               "o campo do jogo perdeu o `list=` — a lista continua no HTML e "
               "nenhum campo a consulta, que é o silêncio que esta casa lê "
               "como sucesso")

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

    # AS CINCO DE 11/09/2026 — PERFIS-LIMPA-01, e cada uma guarda uma ordem
    # dela. Elas moram aqui, e não só no pytest, porque o gerador é quem pode
    # RECUSAR de escrever: uma decisão dela desfeita não chega ao disco.

    # §1 — A LUPA. As três metades, e cada uma sozinha não faz nada: o ícone
    # (sem ele não há como abrir), o campo com o endereço da QUARTA PORTA (sem
    # `data-hef-vivo` digitar não manda nada a lugar nenhum) e o campo NASCENDO
    # FECHADO, que é o que cumpre *"deixar o layout mais limpo"*.
    exigir('class="icone-rot lupa"' in html,
           "a lupa sumiu do título da tabela dos perfis — ela é ordem dela de "
           "11/09/2026 e é por onde o campo de busca aparece")
    exigir('data-papel="abrir-a-lupa"' not in html,
           "a lupa voltou a endereçar por `data-papel` — o ouvinte do piloto "
           "casa esse atributo, e cada clique nela chegaria ao Python como um "
           "gesto SEM DONO, imprimindo no stdout de quem lançou a janela")
    campo = re.search(r'<input[^>]*class="procura"[^>]*>', html)
    exigir(campo is not None, "o campo da lupa sumiu da página")
    if campo:
        exigir('data-hef-vivo="procurar"' in campo.group(0),
               "o campo da lupa perdeu o `data-hef-vivo` — sem a quarta porta "
               "do piloto, digitar nele não manda nada a lugar nenhum: as três "
               "outras portas despacham no clique, no `change` e no `blur`")
        exigir('data-hef-alvo="valor"' in campo.group(0),
               "o campo da lupa perdeu o alvo `valor` — a pintura escreveria o "
               "termo como TEXTO dentro de um `<input>`, que não aparece")
        exigir('value=""' in campo.group(0),
               "o campo da lupa nasce com termo dentro — o desenho passaria a "
               "afirmar uma busca que ela não fez")
    exigir('class="procura on"' not in html,
           "o campo da lupa nasce ABERTO — um campo de busca sempre visível "
           "acrescenta uma linha ao bloco em vez de tirar, e a ordem dela era "
           "de limpeza")

    # §2 — A ORDENAÇÃO POR DUPLO CLIQUE. A trava inteira é uma linha de CSS, e
    # sem ela o clique SIMPLES no cabeçalho ordena — a um pixel da célula do
    # nome, que troca o perfil aberto no editor. Ela pediu duplo clique.
    regra_seta = re.search(r"\.ordena\{[^}]*\}", html)
    exigir(regra_seta is not None, "a regra da seta da ordem sumiu do CSS")
    if regra_seta:
        exigir("pointer-events:none" in regra_seta.group(0),
               "a seta da ordem perdeu o `pointer-events:none` — ela carrega o "
               "gesto `ordenar`, e sem esta linha um clique "
               "SIMPLES no cabeçalho passa a ordenar. Ela pediu DUPLO clique, "
               "e a razão está na regra: o cabeçalho é `sticky` a um pixel da "
               "célula que troca o perfil aberto no editor")
    for coluna in ("nome", "prioridade", "quando"):
        seta = re.search(rf'<span class="ordena" data-hef="perfis\.ordem\.{coluna}"[^>]*>',
                         html)
        exigir(seta is not None,
               f"a coluna `{coluna}` não tem seta de ordem — ela é o que diz "
               f"qual coluna ordena e para onde, sem texto novo")
        if seta:
            exigir('data-hef-gesto="ordenar"' in seta.group(0)
                   and f'data-coluna="{coluna}"' in seta.group(0),
                   f"a seta da coluna `{coluna}` perdeu o gesto ou o nome da "
                   f"coluna — o duplo clique chegaria ao Python sem dizer por "
                   f"qual coluna ordenar")
            # A SETA TEM DE CHEGAR À TELA, e o alvo é o que decide isso. O ramo
            # `classe` do `escrever()` só liga classe e RETORNA — com ele o
            # glifo que o Python calcula é jogado fora e a seta fica 0px, que é
            # o defeito que a conferência de 11/09 fotografou. O ramo `texto`
            # tampouco serve: com valor vazio ele escreve o travessão do lugar
            # vazio, e as duas colunas não ordenadas mostrariam «—».
            exigir('data-hef-alvo="atributo"' in seta.group(0)
                   and 'data-hef-atributo="data-ordem"' in seta.group(0),
                   f"a seta da coluna `{coluna}` mudou de alvo — só o "
                   f"`atributo` chega à tela nos TRÊS estados: ele é o único "
                   f"que APAGA quando o valor é vazio. Com `classe` a seta "
                   f"fica vazia e invisível; com `texto`, as colunas não "
                   f"ordenadas ganham um «—»")

    # A MARGEM SÓ EXISTE QUANDO HÁ SETA — 11/09/2026, e é o defeito que a régua
    # velha desta seção não pegava porque comparava TEXTO DE FONTE. Os 4px de um
    # span vazio cortaram «Priorização» para «Priorizaçã…» na tela (scrollWidth
    # 90 num clientWidth 86, medido em duas larguras de janela), com a palavra
    # INTEIRA no HTML — é por isso que a régua tem de ser sobre a REGRA, e não
    # sobre a colagem do rótulo.
    regra_base = re.search(r"\.ordena\{[^}]*\}", html)
    exigir(regra_base is not None and "margin-left" not in regra_base.group(0),
           "a regra `.ordena` voltou a ter margem incondicional — um span vazio "
           "com margem empurra o rótulo e abrevia o cabeçalho na tela, com a "
           "palavra inteira no HTML. A margem mora em `.ordena[data-ordem]`")
    exigir(re.search(r"\.ordena\[data-ordem\]\{[^}]*margin-left", html) is not None,
           "a seta ORDENADA perdeu a margem — ela encosta no rótulo da coluna")
    # A COLUNA QUE SE ORDENA TEM DE CABER NO PRÓPRIO RÓTULO MAIS A SETA, e as
    # duas larguras da `Priorização` têm de andar JUNTAS. São dois números para
    # a mesma coluna — a `width` da célula e a do `<col>` —, e mexer num só
    # deixa a folha discordando de si mesma sem nada acusar. Medido em
    # 11/09/2026 no WebKit: com 86px o cabeçalho da coluna ORDENADA pedia 96px
    # num espaço de 86, e a tela mostrava «Priorizaçã…».
    larg_col = re.search(r'\.tab col\[data-coluna="prioridade"\]\{width:(\d+)px\}', html)
    larg_cel = re.search(r"\.tab \.pri\{[^}]*width:(\d+)px", html)
    exigir(larg_col is not None and larg_cel is not None,
           "sumiu uma das duas larguras da coluna `Priorização` — a da célula "
           "ou a do `<col>`")
    if larg_col and larg_cel:
        exigir(larg_col.group(1) == larg_cel.group(1),
               f"as duas larguras da `Priorização` discordam: `<col>` diz "
               f"{larg_col.group(1)}px e `.pri` diz {larg_cel.group(1)}px")
        exigir(int(larg_col.group(1)) >= 96,
               f"a coluna `Priorização` voltou a {larg_col.group(1)}px — o "
               f"rótulo mede 86px e a seta da ordem custa 10 (6,2 de glifo + 4 "
               f"de margem). Abaixo de 96 o cabeçalho da coluna ORDENADA sai "
               f"abreviado na tela, com a palavra inteira no HTML")

    for seta_glifo in ("↑", "↓"):
        exigir(f'.ordena[data-ordem="{seta_glifo}"]::after{{content:"{seta_glifo}"}}' in html,
               f"o glifo `{seta_glifo}` sumiu do CSS — quem desenha a seta é o "
               f"`content`, porque o piloto não escreve texto no alvo "
               f"`atributo`. Sem esta regra a seta some da tela e nada diz "
               f"qual coluna ordena")

    # §3 — OS DOIS BOTÕES VIRARAM ÍCONE, e cada um no seu canto. A régua cobra
    # as TRÊS coisas que a §3 da sprint nomeia: o gesto com o MESMO nome, a
    # dica palavra por palavra, e o ícone fora da fileira de botões.
    for gesto_, canto, dica_ in (
            ("recarregar", "Perfis Salvos",
             "Relê a lista do disco. Não descarta o que está no editor ao lado."),
            ("voltar-a-de-ontem", "Definições",
             "Desfaz um perfil salvo por engano: cada gravação já guarda a anterior.")):
        icone = re.search(rf'<button type="button" class="icone-rot" '
                          rf'data-hef-gesto="{gesto_}"[^>]*>', html)
        exigir(icone is not None,
               f"o gesto `{gesto_}` não é um ícone do rótulo — ele virou ícone "
               f"por ordem dela em 11/09/2026, e o nome do gesto não muda por "
               f"troca de invólucro")
        if icone:
            exigir(f'title="{dica_}"' in icone.group(0),
                   f"o ícone de `{gesto_}` perdeu a dica, palavra por palavra. "
                   f"Um ícone sem dica é uma função que ninguém acha — é o "
                   f"custo inteiro de trocar palavra por desenho")
        bloco = html.split(f'class="sec-rot">{canto}')
        exigir(len(bloco) == 2 and f'data-hef-gesto="{gesto_}"' in bloco[1][:700],
               f"o ícone de `{gesto_}` não está no rótulo `{canto}` — ela disse "
               f"onde cada um vai, e são cantos diferentes de propósito")
    exigir(html.count('class="btn" data-hef-gesto="voltar-a-de-ontem"') == 0
           and html.count('class="btn" data-hef-gesto="recarregar"') == 0,
           "um dos dois voltou a ser botão na fileira do rodapé — a fileira de "
           "TRÊS virou UM, e é isso que faz o layout ficar mais limpo sem "
           "acrescentar altura nenhuma")
    # O ALVO DO CLIQUE TEM TAMANHO. Um `<svg>` de 11px é o DESENHO; ela clica
    # isto com o mouse, e 11px de alvo é um alvo que ela erra.
    regra_icone = re.search(r"\.icone-rot\{[^}]*\}", html)
    exigir(regra_icone is not None, "a regra do ícone do rótulo sumiu do CSS")
    if regra_icone:
        exigir("width:24px" in regra_icone.group(0)
               and "height:24px" in regra_icone.group(0),
               "o ícone do rótulo perdeu o alvo de 24x24 — o desenho tem 11px, "
               "e 11px é o DESENHO, não a área clicável")

    # §4 — «Ajuste próprio» VIROU «Status», e SÓ O NOME MUDOU.
    th_status = re.search(r'<th class="gd-pecas"[^>]*>([^<]*)', html)
    exigir(th_status is not None, "o cabeçalho da coluna do meio sumiu")
    if th_status:
        exigir(th_status.group(1).strip() == "Status",
               f"o rótulo da coluna não é `Status`: {th_status.group(1)!r}. "
               f"Ela mandou trocar o nome em 11/09/2026, e SÓ o nome")
    # E A PROSA CONTINUA NOMEANDO A COISA. A frase morre se ela for junto:
    # *"3 de 4 controles com status neste perfil"* não quer dizer nada.
    exigir("controles com ajuste próprio neste perfil" in html,
           "o contador do cabeçalho virou `status` — a troca é do RÓTULO da "
           "coluna, e a prosa continua nomeando a coisa")
    exigir("guarda um ajuste só deste controle" in html,
           "a dica do `<th>` mudou — ela é quem explica o que os ícones acesos "
           "querem dizer, e encurtar o rótulo só funciona porque a explicação "
           "tem outro dono")

    # §5 — A LARGURA ARRASTADA. As TRÊS metades, e a primeira é a armadilha que
    # o próprio arquivo já registrava: com `table-layout:auto` a `width` é
    # SUGESTÃO, e a largura arrastada volta sozinha no repinte seguinte.
    regra_tab = re.search(r"\.tab\{[^}]*\}", html)
    exigir(regra_tab is not None, "a regra da tabela sumiu do CSS")
    exigir("table-layout:fixed" in html,
           "a tabela voltou a `table-layout:auto` — nele a `width` é SUGESTÃO, "
           "e a largura que ela arrastar é reescrita pelo navegador no próximo "
           "repinte. Está medido neste arquivo desde 31/08: `.tab .pri` dizia "
           "46px e o Chrome media 86px")  # (noqa-acento) verbo medir
    exigir(html.count('<col data-coluna=') == 6,
           "não são 6 `<col>` nas duas tabelas — o `<colgroup>` é quem carrega "
           "a largura, e é o único elemento da tabela que o `blocos` do piloto "
           "não reescreve")
    puxadores = re.findall(r'<span class="puxador"[^>]*>', html)
    exigir(len(puxadores) == 4,
           f"não são 4 divisas arrastáveis, e sim {len(puxadores)} — duas por "
           f"tabela, porque a última coluna não tem o que redistribuir")
    for pux in puxadores:
        exigir('data-hef-gesto="largura-da-coluna"' in pux
               and 'data-tabela="' in pux and 'data-px="' in pux,
               "uma divisa perdeu o gesto, a tabela ou o número — soltar o "
               "arraste deixaria de gravar, e a coluna voltaria ao que era na "
               "próxima abertura")
    regra_pux = re.search(r"\.puxador\{[^}]*\}", html)
    exigir(regra_pux is not None, "a regra da divisa sumiu do CSS")
    if regra_pux:
        exigir("cursor:col-resize" in regra_pux.group(0),
               "a divisa perdeu o `cursor:col-resize` — «quando o cursor muda "
               "e permite alterar a largura da coluna» é a descrição dela do "
               "gesto, e sem o cursor não há gesto a achar")

    # §6 — O ROTEIRO, e ele é a primeira linha de JS que uma página desta casa
    # emite. As três coisas que ele faz somem caladas se ninguém as cobrar.
    roteiro = re.search(r"<script>.*?</script>", html, re.S)
    exigir(roteiro is not None,
           "o roteiro da página sumiu — sem ele a lupa não abre, o duplo "
           "clique não ordena e a divisa não arrasta")
    if roteiro:
        corpo = roteiro.group(0)
        for peca, queixa in (
                ("icone-rot.lupa", "o roteiro parou de abrir o campo da lupa"),
                ("dblclick", "o roteiro parou de ouvir o DUPLO clique — e um "
                             "clique simples no cabeçalho é vizinho de um "
                             "gesto que troca o perfil aberto no editor"),
                ("col-resize", "o roteiro perdeu o arraste da divisa"),
                ("MutationObserver", "o roteiro parou de vigiar o "
                                     "`data-larguras` — a largura que volta do "
                                     "disco chega por ali, e só por ali")):
            exigir(peca in corpo, queixa)

    if falhas:
        raise SystemExit("ERRO em 10-perfis — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


# A ESCRITA MORA DEBAIXO DO `__main__`, e isto é cura de defeito MEDIDO em
# 06/09/2026: `import aba10` REESCREVIA a bancada dela como efeito de um
# import. `interface/perfis_vivos.py:78` faz esse import no TOPO do módulo,
# então toda execução dele reescrevia o desenho aprovado — e bastava o pytest
# COLETAR qualquer teste que importasse o gerador para o mesmo acontecer, com o
# estado VIVO da mesa dentro do arquivo (`1 USB · 1 BT` virando `0 USB · 0 BT`
# porque os controles não estavam na tomada naquele instante). A régua do
# desenho aprovado passava a reprovar por causa do que estava ligado.
#
# A `aba01` e a `aba02` já tinham esta guarda desde que `jogar_vivo.py` e
# `controles_vivos.py` passaram a importá-las; a `aba04` e a `aba05` a ganharam
# na costura do mesmo dia, e esta é a irmã delas.
if __name__ == "__main__":
    n = monta("10-perfis", "Perfis", MIOLO, CSS, legenda=LEGENDA)
    _conferir(onde.pagina("10-perfis.html").read_text(encoding="utf-8"))
    # O NÚMERO SAI DO CSS, não de um literal aqui: ele já mentiu duas vezes hoje —
    # a coluna mudou de 82 para 87 e para 86 enquanto ela ajustava os rótulos, e a
    # linha de saída continuou anunciando o valor velho. O que tem dono não se digita.
    ROT_P = re.search(r"--rot-p:(\d+)px", CSS).group(1)
    FORA = sum(1 for c in MESA if not c.get("conectado", True))
    print(f"10-perfis: OK, {n} divs · rótulo à esquerda com dois pontos, coluna de {ROT_P}px, "
          f"zero divisórias no editor · Perfis Salvos e Definições · {FORA} lugar(es) Desconectado")
