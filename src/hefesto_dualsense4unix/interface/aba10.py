import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import collections
import re
import onde
from monta import monta, glifo, cor_da_zona, rotulo, CSS_GLIFO, MESA, SEPARADOR, R

sys.path.insert(0, str(R.parents[1]))
from hefesto_dualsense4unix.profiles.estilos_de_jogo import (  # noqa: E402
    ESTILOS as ESTILOS_DO_MOTOR,
)
from hefesto_dualsense4unix.profiles.schema import PRIORIDADE_MAXIMA  # noqa: E402
from hefesto_dualsense4unix.profiles.simple_match import (  # noqa: E402
    ROTULO_SO_QUANDO_ESCOLHER,
    SEPARADOR_DA_PROCEDENCIA,
)


# eles. Medido com o disco do usuário: `_secoes_do_controle` devolvia SEIS chaves e a
SECOES = [
    ("leds", ("lightbar", "led-jogador")),
    ("triggers", ("l2", "r2")),
    ("rumble", ("rumble_esquerdo", "rumble_direito")),
    ("speaker", ("alto-falante",)),
    ("mic", ("mic",)),
    ("sensores", ("giroscopio", "acelerometro")),
    ("mascara", ("ps",)),
    ("movimento", ("stick_r",)),
    ("ativacao", ("cross",)),  # (noqa-acento) identificador ASCII
    ("analogicos", ("stick_l",)),  # (noqa-acento) identificador ASCII
]

NOME_DA_SECAO = {
    "leds": "luz",
    "triggers": "gatilhos",
    "rumble": "vibração",
    "speaker": "alto-falante",
    "mic": "microfone",
    "sensores": "sensores",
    "mascara": "máscara",
    "movimento": "comandos virtuais",
    "ativacao": "ativação dos botões",  # (noqa-acento) identificador ASCII
    "analogicos": "curva dos analógicos",  # (noqa-acento) identificador ASCII
}


def _lista_das_secoes() -> str:
    """`luz, gatilhos, vibração, alto-falante, microfone e sensores`."""
    nomes = [NOME_DA_SECAO[campo] for campo, _pecas in SECOES]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}" if len(nomes) > 1 else nomes[0]


_EXTENSO = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis",
            7: "sete", 8: "oito", 9: "nove", 10: "dez", 11: "onze", 12: "doze",
            13: "treze", 14: "catorze", 15: "quinze", 16: "dezesseis",
            17: "dezessete", 18: "dezoito", 19: "dezenove", 20: "vinte"}
QUANTAS_SECOES = _EXTENSO[len(SECOES)]

GUARDA = {
    "p1": {"leds", "triggers", "rumble", "mic", "movimento"},
    "p2": {"leds", "rumble", "sensores"},
    "p3": {"leds", "mascara"},
    "p4": set(),
}

NAO_DIZ = "—"
AGORA = {
    "p1": {"triggers": NAO_DIZ, "mic": ""},
    "p2": {"triggers": NAO_DIZ, "leds": "", "movimento": ""},
    "p3": {"triggers": NAO_DIZ},
    "p4": {"triggers": NAO_DIZ},
}
DICA_DO_NAO_DIZ = "O controle não diz"
DICA_DA_MASCARA = "Máscara: {mascara}"
MASCARA_QUE_ACENDE = "DualSense"
DICA_DO_STATUS = "Aceso: ligado agora; o ponto: só deste controle"

# DualSense — medido nesta casa e escrito no esquema (`:1002`).
ID_DA_PECA = {"p1": "AA:BB:CC:00:00:01", "p2": "AA:BB:CC:00:00:02",
              "p3": "AA:BB:CC:00:00:03", "p4": "AA:BB:CC:00:00:04"}

CSS = CSS_GLIFO + """
  /* ---------- Perfis ---------- */
  /* UM FUNDO SÓ, com os dois blocos dentro. Eles continuam sendo dois — mesma
     largura, mesma altura, cada um com o seu título e os seus três botões — mas
     a moldura é uma, e o vão entre eles vira uma divisória fina. Pedido em
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
  /* E `min-width:0` PELA MESMA RAZÃO, no outro eixo — 11/09/2026. O piso
     da tabela por controle (`.tab.miuda{min-width:524px}`) é conteúdo, e
     um item de grade com `min-width:auto` NÃO encolhe abaixo do próprio
     conteúdo: a coluna da direita empurrava 4px para fora do quadro e
     levava junto o rótulo «Definições» e o botão «Ativar». Com o zero a
     coluna cede e quem rola é a `.guarda`, que é quem tem a barra. */
  .perfis > div{display:flex;flex-direction:column;padding:10px 14px;min-height:0;min-width:0}
  .perfis > div:first-child{padding-right:7px}
  .perfis > div:last-child{padding-left:7px}

  .perfis > div > .moldura{flex:1;min-height:0;display:flex;flex-direction:column}
  .moldura{border:none;background:none;padding:0}
  /* A CAIXA ALTA SAIU — 30/08/2026. A regra desta casa sobre maiúscula é a
     PRIMEIRA LETRA, e o usuário confirmou: *"a maiúscula a regra é sobre a primeira
     letra a ser capitalizada, é o padrão do projeto"*. O `text-transform:
     uppercase` a violava calado, e ainda cobrava o preço de legibilidade que
     o usuário apontou (*"essa fonte tem um contraste horrível"*): caixa alta a 11px
     é a forma mais difícil de ler que existe.
     O `letter-spacing` sai junto — ele existia para abrir a caixa alta.
     O texto-fonte já está em caixa de frase ("Força da vibração", "Selecione o
     player"), então nada precisou ser reescrito. */
  /* O TÍTULO DE BLOCO CONTINUA VERDE — 31/08/2026, o usuário decidiu no mesmo turno
     em que mandou tirar o verde dos nomes: *"coloca essa na cor ver[de] e o
     Definições também"*. E é coerente com a regra que ela desenhou: o verde
     saiu de quem NOMEIA UMA LINHA (rótulo de campo, cabeçalho de coluna) e
     ficou em quem ABRE UM BLOCO — são dois, `Perfis salvos` e `Editar`, e
     eles é que dizem onde a pessoa está. (Os dois rótulos mudaram de caixa e
     de palavra em 11/09/2026, A5-033 e A5-041; a decisão do VERDE é a mesma.) */
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
     que o usuário pediu em 27/08, e que a moldura de dentro desfazia. */
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
     queixa, 04/09/2026: *"quando clica em algum nome do perfis salvos nada
     indica que tal coisa tá selecionado"*.

       VALENDO       o perfil que o daemon está aplicando agora  → `class="ativo"`
       ABERTO        a linha em que o editor ao lado está aberto → `aria-selected`
       VALENDO+ABERTO os dois na mesma linha — é o estado em que a aba ABRE,
                     porque `a10_perfis._escolhido` sincroniza o escolhido com o
                     ativo enquanto ela não clicou em nada.

     A janela GTK antiga já tinha os dois separados — `Gtk.TreeSelection` para a
     seleção e `Pango.AttrList` para o ativo (`profiles_actions.py`, sprint
     `2026-08-10-PERFIL-ATUAL-01`) —, e o HTML tinha implementado só o segundo:
     clicar num perfil mudava o alvo de nove botões e a tela não dizia uma letra.

     A COR DIZ *VALENDO*, O FUNDO DIZ *ABERTO*, e por isso os dois se somam sem se
     apagar: verde é o plástico do "está no ar" em toda esta casa, e o par
     `--purple`/`--sel-bg` é o "isto está escolhido" das dez abas (o `.chip.on` do
     topo, o `.rota button.on`, o `.mm-ap.on`). Quem está nos dois estados mostra
     a barra DUPLA — 3px de verde por cima de 6px de roxo.

     O ESTADO MORA NUM ATRIBUTO E NÃO NUMA SEGUNDA CLASSE, e a razão é medida:
     `test_a_lista_de_perfis_cabe_inteira.py:159` procura a SUBSTRING
     `class="ativo"`, e um `class="ativo escolhido"` a apaga — a régua do realce
     ficaria verde sobre uma linha que ela não acha mais. `aria-selected` é o que
     o papel `row` já define para isto, é uma verdade só, e leitor de tela lê.

     `tbody` NOS SELETORES NÃO É ENFEITE: sem ele a regra empata com
     `.tab tbody tr:nth-child(even) td` (0,2,3) e a zebra come o fundo da linha
     escolhida nas posições pares — metade das linhas sem marca. */
  .tab tr.ativo td{color:var(--green);font-weight:600}
  .tab tr.ativo td:first-child{box-shadow:inset 3px 0 0 var(--green)}
  /* O REALCE DA ESCOLHIDA NÃO PODE SER A COR DO `:hover` — 05/09/2026, e a
     queixa é do usuário: *"caso eu clicasse em outro perfil dos disponíveis ele não
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
  /* ------------------------------------------------------------------
     A LUPA, OS DOIS ÍCONES, A SETA E A DIVISA — PERFIS-LIMPA-01, 11/09/2026.

     O ALVO DO CLIQUE TEM TAMANHO, e o desenho NÃO É O ALVO. O SVG mede 11px
     (o mesmo do CADEADO, que era o único ícone desta aba), e 11px é desenho
     — ela clica isto com o mouse. Os 24x24 são o mínimo de alvo, e eles cabem
     na linha de 15px do `.sec-rot` porque o botão é `align-self:center` com
     `margin` negativa vertical: ele SOBRA para cima e para baixo sem empurrar
     nada. É assim que os dois ícones entram em linhas que já existem sem
     acrescentar um pixel de altura — que é o que a ordem de produto pedia.

     ELES SÃO `<button>` E NÃO HERDAM NADA DE `.btn`: o botão desta casa tem
     borda, fundo e 11,5px de texto, e é justamente o que sai de cena aqui. */
  .icone-rot{-webkit-appearance:none;appearance:none;border:none;background:none;
             padding:0;margin:-5px 0;width:24px;height:24px;flex:0 0 24px;
             display:inline-flex;align-items:center;justify-content:center;
             color:inherit;cursor:pointer;border-radius:5px;align-self:center}
  .icone-rot:hover{background:rgba(255,255,255,.09)}
  .icone-rot:active{background:rgba(255,255,255,.15)}
  .icone-rot.on{background:var(--sel-bg,rgba(189,147,249,.30))}
  /* O CAMPO DA LUPA NASCE FECHADO — decisão de produto em uma frase: *"Temos que  (noqa-acento) citação
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
  .procura::placeholder{color:var(--fg)}
  /* QUANTOS A LUPA ESCONDEU. Ela nasce vazia e o `ligado()` do piloto lê o
     vazio como apagado — sem filtro, nada aparece. */
  .fora-da-busca{font-size:10.5px;color:var(--fg);font-weight:400;
                 letter-spacing:0;text-transform:none;display:none}
  .fora-da-busca.on{display:inline}
  /* A SETA DA COLUNA ORDENADA — do tamanho do ícone, e sem texto novo.

     `pointer-events:none` NÃO É ENFEITE, É A TRAVA DO DUPLO CLIQUE: este
     `<span>` é o elemento que carrega `data-hef-gesto="ordenar"`, e o ouvinte
     do piloto despacha no PRIMEIRO clique. Sem esta linha, um clique simples
     no cabeçalho ordenaria — e o cabeçalho é `position:sticky` a um pixel da
     célula do nome, que é o gesto `selecionar` e troca o perfil aberto no
     editor. Com ela, mouse nenhum alcança este nó; quem o aciona é o roteiro
     da página, no `dblclick`, por `.click()`. O usuário pediu duplo clique. */
  /* O GLIFO VEM DO CSS, E NÃO DO PILOTO — 11/09/2026, e o defeito era duplo.
     A seta nasceu com `data-hef-alvo="classe"`, e o ramo `classe` do
     `escrever()` (`hefesto_vivo.py:458`) só liga classe e RETORNA: nunca
     escreve texto. Medido na conferência: com `perfis.ordem.nome = "↑"` o
     span ficava `class="ordena on"`, `opacity:1`, `textContent:""` e
     **0px de largura** — a seta que diz qual coluna ordena NÃO EXISTIA na
     tela, nos três estados. E o alvo `texto` não servia: com valor vazio o
     `escrever()` põe o travessão do lugar vazio (`:382`), e as duas colunas
     não ordenadas mostrariam «—».
     O alvo é `atributo`, que é o único que APAGA quando o valor é vazio
     (`hefesto_vivo.py:626`). O glifo é `content` do CSS; o Python só diz
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
  /* AS LARGURAS DE PARTIDA. As duas datas levam 104px (o rótulo mais a seta da ordem: uma coluna
     que se ordena tem de caber no próprio rótulo com a marca) e o `Nome` NÃO ganha `<col>` de
     propósito: sem largura escrita ele fica com o resto, o único jeito de uma tabela `fixed` ter
     uma coluna elástica. Com os 185px que o `Nome` tinha, a soma dava menos que a tabela e o
     motor esticava as TRÊS colunas em proporção: as datas saíam com 151px, e a largura que ela
     gravava deixava de ser a que se via (o rótulo «Criado em» tinha 69 num cabeçalho de 68).

     O `<colgroup>` é quem carrega o número e não a `width` da `<th>`; quem
     arrastar ganha um `style` inline no mesmo `<col>`, e inline vence folha. */
  .tab td,.tab th{overflow:hidden;text-overflow:ellipsis}
  .tab tbody td{white-space:nowrap}
  .conta-perfis{font-size:10.5px;color:var(--fg);margin-left:auto;text-transform:none;
                letter-spacing:0}
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
  /* O RÓTULO ALINHA À ESQUERDA — 31/08/2026, pedido olhando a aba:
     *"alinha os nomes a esquerda e trás os slicers pra iniciarem deles"*.
     Ele alinhava à direita, como nas outras nove; aqui não alinha mais, e a
     divergência é a que o usuário pediu.
     `nowrap` porque a coluna passou a ser JUSTA: sem ele um rótulo que crescer
     vira duas linhas e estoura a altura do campo, que nesta aba é medida contra
     o `overflow` do quadro. */
  /* MENOS VERDE — 31/08/2026, pedido olhando a aba: *"acho que tem muito
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
         height:var(--h-escolha);font-size:12px;color:var(--fg);margin-bottom:4px}

  /* AS DIVISÓRIAS SAÍRAM DESTE TRECHO — 31/08/2026, pedido olhando a aba:
     *"remove as linhas horizontais desse trecho"*.
     Elas nasceram de um pedido de 30/08 — *"as linhas divisórias em todas
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
  .campo .btn{flex:0 0 auto;white-space:nowrap}
  /* ---------- O QUADRO "MODO" NÃO MORA MAIS AQUI ----------
     11/09/2026, ordem de produto: *"em perfis ainda aparece modo. Isso deve aparecer
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

     A LINHA DE -29 É A QUEIXA DE USO. Com a tira do desfecho acesa — e ela acende
     a cada gesto, por 30 segundos — a tabela rolava 36px e a linha do P4 ficava
     **15px FORA** do quadro. Os 36px da fileira do Modo eram exatamente os 37
     que a tira pede: as duas queixas de uso eram uma. */
  /* A COLUNA DO RÓTULO É JUSTA — remedida no Chrome em 31/08/2026, DEPOIS que o usuário
     pediu os dois pontos e a maiúscula — com a preposição minúscula, que foi a
     segunda palavra de produto: `Nome:` 36px · `Prioridade:` 63 · `Funciona em:` 77 ·
     `Estilo de jogo:` 85 · `Nome do jogo:` **86** — que trocou de dono, era o
     `Estilo de jogo` com 82 antes dos dois pontos.
     Os 104 antigos deixavam 17px de vão morto à direita de todo rótulo — e é
     esse vão que os campos ganharam.
     NÃO dá para usar `max-content`: cada `.campo` é um grid PRÓPRIO, então a
     coluna se resolveria linha a linha e as cinco desalinhariam. Quem mudar o
     texto de um rótulo tem de remedir no Chrome e trazer o número para cá. */
  :root{--rot-p:86px}

  /* ---------- A TIRA DO DESFECHO — o toast que esta janela não tinha ----------
     PARIDADE COM A JANELA ESTÁVEL, 03/09/2026. Lá, TODO gesto desta aba termina
     num `_toast_profile` no rodapé (`profiles_actions.py:420`): "Perfil
     removido: X", "Lista recarregada", `mensagem_de_ativacao`. Aqui só a
     RECUSA falava — `RuntimeError` vira tarja no piloto — e o SUCESSO era
     silêncio. Para os NOVE gestos desta aba que ESCREVEM NO DISCO DO USUÁRIO,
     silêncio no sucesso é o botão que responde calado.

     O ESPAÇO ERA RESERVADO SEMPRE, E O USUÁRIO VIU — 05/09/2026: *"a aba dez tem um
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
     gesto. É o preço que o usuário escolheu ao chamar a banda de bizarra, e ele é
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

  /* ---------- O PONTO DE ALERTA do campo do jogo ----------
     O ponto laranja acende quando o produto recusa o que se digitou (o
     Freestyle, desenho de 19/10/2026), com a frase na `.dica` que a página já
     tem. Nasce escondido e o PRODUTO o acende, pelo alvo `classe`. */
  .campo .exige{
    display:none;flex:0 0 13px;width:13px;height:13px;position:relative;
    cursor:help;color:var(--orange);align-items:center;justify-content:center}
  .campo .exige.on{display:inline-flex}
  .campo .exige:hover .dica{display:block}
  .campo .exige::after{content:"";width:7px;height:7px;border-radius:50%;
                       background:currentColor}
  /* A DICA ABRE PARA A ESQUERDA: o ponto mora no fim de um campo
     que já encosta na borda direita do quadro, e uma caixa de 330px a 22px
     para a direita sairia da janela. É a mesma cura que o `.tn-cx .dica` do
     `monta` já faz na aba Conexões. */
  .campo .exige .dica{left:auto;right:20px;width:300px}

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
          /* ROLA DE LADO EM VEZ DE ENGOLIR — 11/09/2026. Era
             `overflow-x:hidden`, e com o `table-layout:fixed` que a
             PERFIS-LIMPA-01 deu ao `.tab` isso virou perda de dado: as
             duas colunas de largura CRAVADA (`.gd-pecas` 255px e
             `.gd-id` 118px) somam 373 dos 374px que a tabela tem numa
             janela de 940px, e sobrava **1px** para o nome do controle.
             Medido, não estimado. `title` aqui não serve — o `<td>` é
             estático e quem pinta o nome é o `guarda.nome` de dentro,
             então a dica ficaria com o nome do MOCKUP sobre o controle
             da bancada. Rolar é a afordância que
             `test_a_janela_estreita_nao_engole_o_desenho` nomeia, e na
             vista do usuário (1918x840) nada muda: a tabela cabe e não rola. */
          overflow-y:auto;overflow-x:auto;
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

  /* UM FUNDO POR COLUNA — 31/08/2026, pedido: *"deixa o background do nome
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
     é a metade *"suspiro"* do pedido. */
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
     metade da queixa de uso: *"em perfis as linhas dos controles e ajustes
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
     cura de uma queixa de uso agravando a outra, na mesma tela.

     O 1,50px QUE SOBRA é o glifo, não o texto: o `.gls` é SVG com
     `vertical-align:-3px` (o deslocamento ótico que a coluna do meio pede), e o
     nome fecha EXATO com o ID da peça — 16,13 contra 16,13. */
  /* O NOME DO CONTROLE QUEBRA EM VEZ DE SUMIR — 11/09/2026. A PERFIS-LIMPA-01
     deu `table-layout:fixed` ao `.tab` para a divisa arrastável valer, e com ele
     a `.tab tbody td{white-space:nowrap}` passou a CORTAR esta célula: a 940px
     de janela «P1 • Cosmic Red • USB» sobrava 119px para fora e virava
     reticências, sem `title` que devolvesse o nome. Um nome de controle cortado
     é a informação que esta tabela existe para dar.
     `title` AQUI NÃO SERVE, e a razão é de dono: o `<td>` é estático e quem
     pinta é o `guarda.nome` de dentro — um `title` cravado no desenho ficaria
     com o nome do MOCKUP enquanto o texto traz o da bancada, que é o defeito
     que `test_aba10_a_dica_da_linha_nao_e_do_mockup` caça. Quebrar a linha não
     tem dono nenhum: ela cabe inteira, em duas linhas, quando a janela aperta.
     Na vista do usuário (1918x840) nada muda — o nome cabe numa linha só. */
  .gd-nome{vertical-align:middle;white-space:nowrap;font-size:11px}
  /* O PISO DA TABELA POR CONTROLE. 151px para o nome mais longo do
     desenho («P2 • Starlight Blue • BT», medido a 11px com os 16px de
     padding) mais os 255 e os 118 cravados das outras duas. Sem ele o
     `overflow-x:auto` acima não tem o que rolar: a tabela encolhe até
     caber e a coluna do nome é a única que cede. */
  .tab.miuda{min-width:524px}
  /* O DESENHO DE 32px SAIU, e a barrinha de plástico ficou com o trabalho.
     Ele existia para dizer QUAL controle é a linha, e não dizia: medido em
     28/08 no 1x da tela do usuário, com os quatro desenhos comparados pixel a pixel,
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
  /* AS OITO SEÇÕES TÊM DE SE LER COMO OITO. Com o mesmo vão entre todos os
     glifos, eles viravam um borrão só e ninguém achava onde a luz acaba e o
     gatilho começa: 2px DENTRO de uma seção, 6px ENTRE elas. Eram 11px até
     02/10/2026, e com a máscara (08/09) e os comandos virtuais (24/09) a
     fileira passou a pedir 265px numa coluna de 255: o oitavo grupo ficava
     inteiro fora da célula, nas quatro linhas (a foto dela de 29/09). Com 6px
     ela pede 230 (os doze glifos de 15px com os vãos de dentro, 188, e sete
     vãos de 6), e cabe nos 235 que a folga de 20 deixa. */
  /* O NÚMERO É MEDIDO, e ele mudou de dono em 11/09/2026. Com `table-layout`
     em `auto` esta coluna media  (noqa-acento: verbo medir, imperfeito) 255px
     na tela (a fileira de glifos pede 239 e a
     folga da célula 16), e o `150px` escrito aqui era SUGESTÃO que o navegador
     ignorava. Com `fixed` a sugestão virou ordem: mantido o 150, a fileira de
     glifos era CORTADA — fotografado. O valor agora é o que a tela
     media.  (noqa-acento: verbo medir, imperfeito) */
  .gd-pecas{width:271px}
  /* 16/10/2026: com a ativação dos botões e a curva dos analógicos são DEZ seções, e com 6px a
     última passava 3px da célula. O vão entre seções desceu a 5px (o de dentro segue 2px).
     19/10/2026: a fileira pede 271px (catorze glifos de 15px, quatro vãos de 2px e nove de 5px), e a
     coluna de 255px só a continha a 1272 px porque a folga da tabela a alargava: a 940 px a última
     seção passava 16px da célula. A coluna passa a 271px; a tabela já rola na horizontal ali. */
  .gd-pecas .gls{gap:5px}
  /* O GLIFO DIZ O CONTROLE AGORA, E O PONTO EMBAIXO DIZ O DISCO — 02/10/2026,
     decidido pelo usuário em 29/09 («Ponto embaixo»): aceso = ligado agora neste
     controle · apagado = desligado · tracejado = o controle não diz · o ponto
     = o perfil aberto no editor guarda esta seção só para ele. O ponto mora
     FORA do `.gr`, e por isso não herda a cor nem o halo do aceso: as duas
     camadas não se confundem. */
  .gc{position:relative;display:inline-flex}
  .gq{display:inline-flex;align-items:center;gap:2px;border-radius:3px}
  .gq.nd{outline:1px dashed var(--comment);outline-offset:1px}
  .gp{position:absolute;left:50%;bottom:-6px;width:4px;height:4px;margin-left:-2px;
      border-radius:50%;background:var(--fg);visibility:hidden}
  .gp.on{visibility:visible}
  /* O APAGADO PASSOU DE `--border-forte` PARA `--comment` — 30/08/2026.
     #44475a sobre o painel dá **1,56:1**: não era glifo apagado, era glifo
     INVISÍVEL — e um estado que não se vê não comunica estado nenhum, só
     ausência. #8896c4 dá 4,89:1 e continua nitidamente mais fosco que o
     aceso (roxo #bd93f9 com o halo do `drop-shadow`), que é o que separa os
     dois. Ela: *"sobe também"*. */
  .gr{display:inline-flex;align-items:center;gap:2px;color:var(--fg)}
  .gr.on{color:var(--purple);filter:drop-shadow(0 0 4px rgba(189,147,249,.45))}
  .gr .gl{vertical-align:-3px}
  /* MESMA CURA, MESMO DIA: o endereço de rádio mede 118px em JetBrains Mono de
     10px mais a folga, e o `112` cortava o último octeto com reticências. */
  .gd-id{width:118px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:10px;
         color:var(--fg)}
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
     SOME. Campo sem informação não mostra nada — regra de produto.

     A CAIXA É A MESMA: `inset 3px 0 0` pinta os 3px da esquerda da caixa de borda
     da célula, e é exatamente o que `position:absolute;left:0;top:0;bottom:0` dá
     num `<td>` posicionado, que não tem borda. Zero pixel de diferença. */
  .tab.miuda td:first-child{position:relative}
  .gd-nome .pl{position:absolute;left:0;top:0;bottom:0;width:3px;
               background:currentColor;color:transparent}
  /* O LUGAR SEM CONTROLE — a cor é a do `.vazio` da Gatilhos (`--comment`), que é
     a página que o usuário mandou copiar. O contraste está medido no comentário da
     régua: aqui o fundo é `--panel`, não o `--app-bg` da Jogar, e foi por olhar
     só o token — e não o CONTRASTE contra o fundo de CADA aba — que o lugar
     vazio da Jogar saiu mais aceso que o controle na mesa, em 31/08. */
  .tab.miuda tr.fora .gd-nome{color:var(--fg)}
  /* O GLIFO SOME NO LUGAR SEM CONTROLE — 05/09/2026, palavra de produto.
     `visibility` e não `display`: a fileira guarda a altura da linha, e um
     `display:none` faria as quatro linhas da tabela mudarem de altura conforme
     a mesa — a tabela inteira pulando quando um controle entra ou sai. */
  .tab.miuda tr.fora .gr,.tab.miuda tr.fora .gp{visibility:hidden}

  /* ---------- A Perfis do todo (15/10/2026) ---------- */
  /* Os quatro botões ficam NO FIM DO QUADRO, sob as duas colunas, todos da mesma largura. */
  .barra-quatro{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:14px 0 2px}
  .barra-quatro .btn{width:100%;height:36px;justify-content:center;font-size:12.5px}
  /* O «Ativar» é a ação principal: sólido, como o «Aplicar» do rodapé. */
  .barra-quatro .btn.verde,.barra-quatro .btn.verde:hover{background:var(--green);
      color:var(--app-bg);border-color:var(--green);font-weight:700}
  .perfis > div{padding:12px 16px}
  .perfis > div:first-child{padding-right:8px}
  .perfis > div:last-child{padding-left:8px}
  /* A LISTA ROLA DENTRO DO `.rolo`, com a barra de verdade lá de cima: na janela baixa as linhas de
     baixo descem para fora do quadro, e um corte as sumia sem barra nenhuma
     (D-1710-A-JANELA-ESTREITA-NAO-ENGOLE-O-DESENHO). No tamanho do desenho a lista cabe e a barra não nasce. */
  .rolo .tab tbody td{height:26px;padding-top:0;padding-bottom:0}
  .rolo .tab thead th[data-coluna]{cursor:pointer;user-select:none}
  .quadro-titulo[data-dica],.cab[data-dica]{cursor:help}
  .tab col[data-coluna="criado"],.tab col[data-coluna="modificado"]{width:104px}
  /* O campo do renomear ocupa a célula do nome, na altura da linha. */
  .tab td .renome{width:100%;box-sizing:border-box;height:22px;font:inherit;padding:0 6px;
                  border:1px solid var(--purple);border-radius:5px;background:var(--app-bg);color:var(--fg)}
  .tab td.data{font-family:'JetBrains Mono',monospace;color:var(--fg);font-weight:400;
               white-space:nowrap}
  .tab th.data{white-space:nowrap}
  .campos{gap:4px}
  /* «Aplicar em»: quatro botões de escolha na largura do campo */
  .campo .seg.alvos{flex-wrap:nowrap;gap:6px;flex:1;min-width:0}
  .campo .seg.alvos button{flex:1 1 0;min-width:0;height:var(--h-escolha);padding:0 8px}
  /* «Quando» só existe com «Eventos»; a classe `on` vem do botão (pintura) ou do roteiro (desenho) */
  .campo.so-eventos{display:none}
  .campo.so-eventos.on{display:grid}
  .ev-val{display:flex;gap:10px;align-items:center;min-width:0}
  /* O comando é do «Meu comando» e só dele (19/10/2026): a linha abaixo do «Quando» aparece quando o
     momento escolhido é esse, e some em qualquer outro. O `:has` lê o `<option>` marcado, então o
     desenho responde sozinho e a pintura do produto (que só escolhe o `<option>`) faz o mesmo. */
  .campo.so-comando{display:none}
  .campo.so-eventos.on:has(option[value="meu_comando"]:checked) + .campo.so-comando{display:grid}
  .campo select.estreito{flex:1 1 auto;width:100%}
  /* «Qual vale primeiro»: só aparece com dois perfis do mesmo jogo */
  .ordem-vale{margin:4px 0 8px;display:none}
  /* a classe vem do pacote: o `:has(ol:empty)` não se recalcula no WebKitGTK quando o `<ol>` enche */
  .ordem-vale.on{display:block}
  .ordem-vale .cab{font-size:11.5px;font-weight:700;color:var(--fg);margin:0 0 4px}
  .ordem-vale ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
  .ordem-vale li{display:flex;align-items:center;gap:8px;height:28px;padding:0 10px;font-size:12px;
                 border:1px solid var(--linha);border-radius:7px;background:var(--app-bg);
                 color:var(--fg);cursor:grab}
  .ordem-vale li.ativo{border-color:var(--purple)}
  .ordem-vale li.arrastando-este{opacity:.45}
  .ordem-vale .pos{flex:0 0 18px;font-family:'JetBrains Mono',monospace;color:var(--fg);
                   text-align:right}
  .ordem-vale .pega{color:var(--fg);letter-spacing:-2px}
  /* a tabela por controle: três colunas fixas, o endereço em fonte miúda */
  .guarda table{table-layout:fixed;width:100%;min-width:0 !important}
  .guarda col[data-coluna="controle"]{width:136px}
  .guarda col[data-coluna="id"]{width:114px}
  .guarda td.gd-id,.guarda th.gd-id{font-size:10px;letter-spacing:-.2px;padding-left:6px;
                                    padding-right:6px}
  /* o ID da peça cede a partir daqui — 20/10/2026. A 1212px o Status de 271px e o respiro não
     deixam lugar para os 114px do ID, e a guarda rolava 14px de lado cortando a coluna. A escolha de
     20/10 foi esconder o ID nessa largura, em vez de encolher o respiro ou quebrar as seções. O dado
     segue no pacote (`guarda.id`); só a coluna some, o `<col>` junto, e a tabela divide o que sobra.
     O corte não é 1212: medido no Chrome, a guarda com o ID ainda rola 13px a 1213 e só cabe a partir de
     1240 (1px a cada 2px de largura). A regra vale até 1259, com folga para a letra do WebKit. */
  @media (max-width:1259px){
    .guarda col[data-coluna="id"],.guarda th.gd-id,.guarda td.gd-id{display:none}
  }
  @media (max-height:860px){
    .campo{height:32px}
    .campo input,.campo select,.campo .seg button{height:32px !important;min-height:0}
    .ordem-vale li{height:26px}
    .ordem-vale{margin:0 0 6px}
  }
  @media (max-height:780px){
    .campos{padding:8px 12px}
    .campo{height:28px;margin-bottom:3px}
    .campo input,.campo select,.campo .seg button{height:28px !important}
    .ordem-vale li{height:24px}
    .ordem-vale ol{gap:3px}
    .ordem-vale .cab{margin-bottom:3px}
    .tab.miuda thead th{padding:3px 8px}
  }
"""

CABEM_NA_TIRA = 413

CADEADO = ('<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true">'
           '<path d="M3.6 5.2V3.9a2.4 2.4 0 0 1 4.8 0v1.3" fill="none" '
           'stroke="currentColor" stroke-width="1.2"/>'
           '<rect x="2.3" y="5.2" width="7.4" height="5.4" rx="1.1" '
           'fill="currentColor"/></svg>')


#     "Na tabela do perfil tem que terum svg dde lupa no titulo da tabela.  # (noqa-acento) citação literal
#      Temos que remover esse botão voltar a de ontem ??? e o botão  # (noqa-acento) citação literal
#      recarregar vira um svg clicável ao lado de Perfis Salvos que irá  # (noqa-acento) citação literal
#      fazer essa função. Temos que deixar o layout mais limpo.."  # (noqa-acento) citação literal
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

#     "e o botao atualizar tá aparecendo duplicado na interface"  # (noqa-acento) citação literal


def icone_do_rotulo(gesto: str, desenho: str, dica: str, aria: str = "") -> str:
    """Um ícone clicável no título de um bloco; a dica é `data-dica`, o `aria` é a frase longa."""
    return (f'<button type="button" class="icone-rot" '
            f'data-hef-gesto="{gesto}" data-dica="{dica}" '
            f'aria-label="{aria or dica}">{desenho}</button>')


def icone_da_lupa() -> str:
    """A lupa do título da tabela dos perfis. Ela ABRE o campo, e nada mais."""
    return ('<button type="button" class="icone-rot lupa" '
            'data-dica="Procura pelo nome ou pelo jogo" '
            f'aria-label="Procurar um perfil">{LUPA}</button>')


def campo_da_lupa() -> str:
    """O campo que a lupa abre — fechado no desenho, e é decisão de produto."""
    return ('<input type="text" class="procura" data-hef="perfis.procura" '
            'data-hef-alvo="valor" data-hef-vivo="procurar" '
            'placeholder="procurar" aria-label="Procurar um perfil" value="">')


def puxador(coluna: str, tabela: str) -> str:
    """A divisa arrastável no canto direito de um `<th>`."""
    return (f'<span class="puxador" data-hef-gesto="largura-da-coluna" '
            f'data-tabela="{tabela}" data-coluna="{coluna}" data-px="0" '
            f'role="separator" aria-label="Arraste para mudar a largura da coluna"></span>')


def cabeca(coluna: str, rotulo_visivel: str, tabela: str, classe: str = "",
           divisa: bool = True, dica: str = "Duplo clique ordena") -> str:
    """Um `<th>` da lista de perfis: o nome, a seta da ordem e a divisa."""
    cls = f' class="{classe}"' if classe else ""
    return (f'<th{cls} data-coluna="{coluna}" data-dica="{dica}">'
            f'{rotulo_visivel}'
            f'<span class="ordena" data-hef="perfis.ordem.{coluna}" '
            f'data-hef-alvo="atributo" data-hef-atributo="data-ordem" '
            f'data-hef-gesto="ordenar" data-coluna="{coluna}"></span>'
            f'{puxador(coluna, tabela) if divisa else ""}</th>')


def marca_com_dica(classe: str, campo_estado: str, campo_frase: str,
                   miolo: str = "") -> str:
    """O cadeado (ou o ponto) que só aparece quando o produto tem o que dizer."""
    return (f'<span class="{classe}" data-hef="{campo_estado}"'
            f' data-hef-alvo="classe">{miolo}'
            f'<span class="dica" data-hef="{campo_frase}"'
            f' data-hef-alvo="html"></span></span>')


ESTILOS = [e.rotulo for e in ESTILOS_DO_MOTOR]
#: (foto 9): aparece o nome e o código, não só o código, e não aparece o nome do programa.
PERFIS = [("Mortal Kombat", 90, "Steam · Mortal Kombat 1 · 1971870", True),
          ("Mortal Kombat online", 88, "Steam · Mortal Kombat 1 · 1971870", False),
          ("Elden Ring", 85, "Steam · Elden Ring · 1245620", False),
          ("Orpheus", 82, "RetroArch · Orpheus: To Hell and Back", False),
          ("Pragmata", 80, "Steam · Pragmata · 1358160", False),
          ("Don't Scream", 78, "Steam · Don't Scream · 2380050", False),
          ("Reanimal", 76, "Heroic · Reanimal", False),
          ("Faith", 74, "Instalado aqui · faith.exe", False),
          ("Wendigo Blue", 72, "Lutris · Wendigo Blue", False),
          ("Duskfade", 70, "Heroic · Duskfade", False),
          ("Mina the Hollower", 68, "Instalado aqui · mina.exe", False),
          ("Terror (os dez)", 60, "Só neste programa", False),
          ("Luta", 58, "Só neste programa", False),
          ("Navegação", 40, ROTULO_SO_QUANDO_ESCOLHER, False),
          ("Universal", 0, ROTULO_SO_QUANDO_ESCOLHER, False)]

PROCEDENCIA_DO_DESENHO = PERFIS[0][2].split(SEPARADOR_DA_PROCEDENCIA)[0]

# As datas do desenho: (criado, modificado). Perfil de antes das datas mostra «—» nas duas.
SEM_DATA = ("—", "—")
DATAS_DO_DESENHO = {
    "Mortal Kombat": ("03/09/2026", "11/10/2026"),
    "Mortal Kombat online": ("10/10/2026", "10/10/2026"),
    "Elden Ring": ("21/08/2026", "02/10/2026"),
    "Orpheus": ("14/09/2026", "14/09/2026"),
    "Pragmata": ("18/09/2026", "07/10/2026"),
    "Faith": ("26/09/2026", "01/10/2026"),
    "Duskfade": ("30/09/2026", "30/09/2026"),
    "Mina the Hollower": ("02/10/2026", "09/10/2026"),
}
ORDEM_DO_DESENHO = ["Mortal Kombat", "Mortal Kombat online"]

# «Aplicar em» e «Quando»: os valores são os do esquema (`AlvoDoPerfil`, `EventoDoPerfil`).
ALVOS_DO_DESENHO = [
    ("jogos", "Jogos", "Vale quando o jogo abre"),
    ("navegacao", "Navegação", "Vale fora do jogo, no computador"),
    ("programas", "Programas", "Vale com o programa na frente"),
    ("eventos", "Eventos", "Um momento do jogo, do sistema ou o seu comando"),
]
MOMENTOS_DO_DESENHO = [
    ("No jogo", [("cena", "Cena"), ("menu", "Menu"), ("pausa", "Pausa")]),
    ("No sistema", [("controle_conectado", "Controle conectado"),
                    ("programa_aberto", "Programa aberto"), ("hora_marcada", "Hora marcada")]),
    ("Meu", [("meu_comando", "Meu comando")]),
]
DICAS_DOS_ESTILOS = {"Nativo": "O jogo decide"}

PRI_DO_DESENHO = PERFIS[0][1]
PERFIL_DO_EDITOR = PERFIS[0][0]
PCT_DO_DESENHO = round(PRI_DO_DESENHO * 100 / PRIORIDADE_MAXIMA)

TRAVESSAO = "—"


def opts(lista, escolhido, vazio=False, travessao=False):
    """As opções de um `<select>` do desenho."""
    linhas = []
    if vazio:
        linhas.append('                <option value="" disabled selected>—</option>')
    if travessao:
        linhas.append(f'                <option value="{TRAVESSAO}" disabled>'
                      f'{TRAVESSAO}</option>')
    linhas += [f'                <option{" selected" if (o == escolhido and not vazio) else ""}'
               f'{f" data-dica={chr(34)}{DICAS_DOS_ESTILOS[o]}{chr(34)}" if o in DICAS_DOS_ESTILOS else ""}>{o}</option>'
               for o in lista]
    return "\n".join(linhas)


from pacotes.a11_calibrar_sensores import bloco_de_nascenca as _mira_de_nascenca  # noqa: E402
from pacotes.a11_calibrar_sensores import resumo_da_mira as _resumo_da_mira  # noqa: E402

_RESUMO_DA_MIRA_NA_CENA = _resumo_da_mira(_mira_de_nascenca()) or ""


def _celula_de_agora(c, campo, agora):
    """`(aceso, não_diz, dica)` de uma célula do cenário `AGORA`.

    A máscara é a da `MESA` (`c["mascara"]`), com a regra do pacote
    (`a10_perfis._mascara_agora`): acesa só na DualSense.
    """
    if campo == "mascara" and campo not in agora:
        mascara = str(c.get("mascara") or "")
        if mascara in ("", NAO_DIZ):
            return False, True, DICA_DO_NAO_DIZ
        if mascara != MASCARA_QUE_ACENDE:
            return False, False, DICA_DA_MASCARA.format(mascara=mascara)
        return True, False, ""
    valor = agora.get(campo, "sim")
    if valor == NAO_DIZ:
        return False, True, DICA_DO_NAO_DIZ
    # os «comandos virtuais» dizem os ajustes da Mira na dica: a cena leva os de nascença da Calibrar
    return valor == "sim", False, (_RESUMO_DA_MIRA_NA_CENA
                             if campo == "movimento" and c.get("conectado", True) else "")


def linha_do_controle(c, tem=None, id_da_peca=None, uniq=None, agora=None):
    """Uma linha da tabela de baixo: o controle, o que é só dele, e o ID da peça."""
    na_mesa = c.get("conectado", True)
    tem = GUARDA[c["pref"]] if tem is None else tem
    agora = AGORA.get(c["pref"], {}) if agora is None else agora
    id_visivel = ID_DA_PECA[c["pref"]] if id_da_peca is None else id_da_peca
    endereco = uniq if uniq is not None else c["pref"]
    grupos = []
    # `SECOES`. O `data-hef-alvo="classe"` é o que deixa o PRODUTO acender e
    for campo, pecas in SECOES:
        on, nao_diz, dica_da_celula = _celula_de_agora(c, campo, agora)
        gs = "".join(glifo(p, ativo=on, tam=15) for p in pecas)
        titulo = f' data-dica="{dica_da_celula}"' if dica_da_celula else ""
        grupos.append(
            f'<span class="gc" data-hef="guarda.dica" data-hef-alvo="atributo"'
            f' data-hef-atributo="data-dica"{titulo}>'
            f'<span class="gr{" on" if on else ""}" data-hef="guarda.secao"'
            f' data-hef-alvo="classe" data-hef-secao="{campo}">'
            f'<span class="gq{" nd" if nao_diz else ""}" data-hef="guarda.incerto"'
            f' data-hef-alvo="classe" data-hef-classe="nd">{gs}</span></span>'
            f'<span class="gp{" on" if campo in tem else ""}" data-hef="guarda.proprio"'
            f' data-hef-alvo="classe"></span></span>')
    # (IDENTIDADE-VEM-DE-CIMA): o `--plastico` estava no `<tr>`, sem endereço, e
    # a cor do plástico fala no lugar de «P3»: o vazio traz a cor do controle que ficou guardado
    nome = SEPARADOR.join([c["nome"], c["via"]]) if na_mesa else c["nome"]
    plastico = cor_da_zona(c['cor'])
    dica = ("" if na_mesa else
            '\n                      data-dica="Quando ele voltar, encontra o que você deixou"')
    return f'''                  <tr data-hef-uniq="{endereco}" data-hef="guarda.vazio" data-hef-alvo="classe" data-hef-classe="fora"{'' if na_mesa else ' class="fora"'}{dica}>
                    <td class="gd-nome">
                      <span class="pl" data-hef="guarda.plastico" data-hef-alvo="cor"
                            style="color:{plastico}"></span>
                      <span data-hef="guarda.nome">{nome}</span>
                    </td>
                    <td class="gd-pecas"><span class="gls">{"".join(grupos)}</span></td>
                    <td class="gd-id" data-hef="guarda.id">{id_visivel}</td>
                  </tr>'''


def linha_do_perfil(nome, criado, modificado, ativo, dica="", escolhido=False):
    """Uma linha da lista de perfis salvos, a MESMA para o mockup e para a viva.

    O dono da forma é este gerador; a linha viva (`a10_perfis._linha_da_lista`) a repete e uma
    régua compara as duas caractere a caractere. O clique em QUALQUER célula sobe até a `<tr>`
    (`data-hef-gesto="selecionar"`), que ativa o perfil e o abre no editor. O nome viaja no
    `data-hef-perfil`, não no texto. `escolhido` é a linha aberta no editor e sai sempre em
    `aria-selected` (`true` ou `false`), para o `<tbody>` assentar a cada tique. O parâmetro
    `dica` fica por compatibilidade: a dica da linha é fixa e nasce em `data-dica`.
    """
    return (f'                <tr tabindex="0" data-dica="Clique: ativa e abre no editor" '
            f'class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{nome}" data-hef-gesto="selecionar" '
            f'aria-selected="{"true" if escolhido else "false"}">'
            f'<td data-hef="perfis.linha.nome" data-dica="Clique abre no editor; duplo clique renomeia">{nome}</td>'
            f'<td class="data" data-hef="perfis.linha.criado">{criado}</td>'
            f'<td class="data" data-hef="perfis.linha.modificado">{modificado}</td></tr>')


def botao_do_alvo(valor, rotulo_visivel, dica):
    """Um dos quatro botões de «Aplicar em»; só o do jogo nasce aceso (a classe `on`)."""
    ligado = ' class="on"' if valor == "jogos" else ""
    return (f'                  <button{ligado} '
            f'data-hef="editor.alvo.{valor}" data-hef-alvo="classe" data-hef-classe="on" '
            f'data-hef-gesto="editor.alvo" data-v="{valor}" data-dica="{dica}">'
            f'{rotulo_visivel}</button>')


def opcoes_do_quando():
    """O `<select>` de «Quando»: o travessão (sem momento) e os sete momentos, em três grupos."""
    grupos = [f'                  <option value="{TRAVESSAO}" disabled selected>{TRAVESSAO}</option>']
    for nome_do_grupo, itens in MOMENTOS_DO_DESENHO:
        grupos.append(f'                  <optgroup label="{nome_do_grupo}">'
                      + "".join(f'<option value="{v}">{r}</option>' for v, r in itens)
                      + "</optgroup>")
    return "\n".join(grupos)


def item_da_ordem(nome, posicao, ativo):
    """Um `<li>` de «Qual vale primeiro»: o mesmo que `a10_perfis._html_da_ordem` escreve."""
    return (f'                  <li class="{"ativo" if ativo else ""}" draggable="true" tabindex="0" '
            f'data-hef-gesto="editor.ordem" data-hef-perfil="{nome}">'
            f'<span class="pos">{posicao}</span><span class="pega">⋮⋮</span>{nome}</li>')


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
    // é exatamente o que o usuário pediu ao dizer DUPLO clique.
    document.addEventListener('dblclick', function(ev){
      var nome = ev.target.closest ? ev.target.closest('td[data-hef="perfis.linha.nome"]') : null;
      if(nome){ renomear(nome); return; }
      var th = ev.target.closest ? ev.target.closest('th[data-coluna]') : null;
      if(!th) return;
      var seta = th.querySelector('.ordena[data-hef-gesto]');
      if(seta) seta.click();
    }, false);

    // ---- o duplo clique no nome renomeia (19/10/2026) -------------------------
    // A célula vira campo; Enter ou sair dele grava (o `change` leva o gesto
    // `perfis.renomear` com o nome velho no `data-hef-perfil`), Esc desiste. O
    // nome velho fica num `<span hidden>` ao lado: o `textContent` da célula
    // segue igual ao que o Python pinta, e o tique não apaga o campo no meio da
    // digitação. Renomeado, o `<tbody>` novo chega e leva o campo junto.
    function renomear(td){
      if(td.querySelector('input')) return;
      var tr = td.closest('tr[data-hef-perfil]');
      if(!tr) return;
      var era = tr.dataset.hefPerfil;
      var guarda = document.createElement('span');
      guarda.hidden = true;
      guarda.textContent = td.textContent;
      var campo = document.createElement('input');
      campo.type = 'text';
      campo.className = 'renome';
      campo.value = era;
      campo.setAttribute('aria-label', 'Novo nome do perfil');
      campo.dataset.hefGesto = 'perfis.renomear';
      campo.dataset.hefPerfil = era;
      td.textContent = '';
      td.appendChild(guarda);
      td.appendChild(campo);
      campo.focus();
      campo.select();
      campo.addEventListener('keydown', function(e){
        e.stopPropagation();
        if(e.key === 'Enter'){ e.preventDefault(); campo.blur(); }
        else if(e.key === 'Escape'){ e.preventDefault(); campo.value = era; campo.blur(); }
      });
      campo.addEventListener('blur', function(){
        setTimeout(function(){ if(td.contains(campo)) td.textContent = guarda.textContent; }, 0);
      });
    }

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

    // ---- o piso de cada coluna é o rótulo dela ------------------------------
    // A-LINHA-INTEIRA-ABRE-O-PERFIL-01, 02/10/2026. Com a coluna nos 48 px que
    // ela gravou, o cabeçalho saía «Pri…»: o `PISO` é um número só, e o rótulo
    // pedia 80. O piso passa a ser o maior entre o `PISO` e o próprio rótulo
    // (o `scrollWidth` do `<th>`: o texto, a seta da ordem e o preenchimento),
    // medido no motor que pinta. O disco não muda; quem sobe é a tela.
    // Mede de novo depois de cada acréscimo: a tabela é `width:100%` em layout fixo, então a soma
    // das colunas menor que a tela as estica em proporção, e o `<th>` rende mais que o `<col>`.
    // Uma medida só deixava o rótulo «Criado em» 1 px curto (69 num cabeçalho de 68).
    function caber(th, col, px){
      col.style.width = px + 'px';
      for(var i = 0; th && i < 8; i++){
        var falta = th.scrollWidth - th.clientWidth;
        if(falta <= 0) break;
        px = px + falta;
        col.style.width = px + 'px';
      }
      return px;
    }
    function ajustar(tab){
      tab.querySelectorAll('th[data-coluna]').forEach(function(th){
        var col = tab.querySelector('col[data-coluna="' + th.dataset.coluna + '"]');
        if(!col || th.clientWidth >= th.scrollWidth) return;
        var px = caber(th, col, Math.round(th.getBoundingClientRect().width));
        var pux = th.querySelector('.puxador');
        if(pux) pux.dataset.px = String(px);
      });
    }
    document.addEventListener('mousedown', function(ev){
      var pux = ev.target.closest ? ev.target.closest('.puxador') : null;
      if(!pux) return;
      var alvo = colDe(pux);
      if(!alvo.col) return;
      var th = pux.closest('th');
      voo = {pux: pux, col: alvo.col, th: th, x: ev.clientX,
             largura: th ? th.getBoundingClientRect().width : 0};
      document.body.classList.add('arrastando');
      ev.preventDefault();
    }, false);
    document.addEventListener('mousemove', function(ev){
      if(!voo) return;
      var px = Math.round(voo.largura + (ev.clientX - voo.x));
      if(px < PISO) px = PISO;
      if(px > TETO) px = TETO;
      px = caber(voo.th, voo.col, px);
      voo.pux.dataset.px = String(px);
    }, false);
    document.addEventListener('mouseup', function(){
      if(!voo) return;
      var pux = voo.pux;
      voo = null;
      document.body.classList.remove('arrastando');
      pux.click();
    }, false);
    // O TECLADO ANDA A DIVISA (A-INTERFACE-INTEIRA-SE-ALCANCA-…-01): a alça tem parada no Tab
    // (a base comum põe o `tabindex` em todo `data-hef-gesto`), e ← e → mudam a largura 8 px por
    // vez, com o mesmo piso e teto do arraste. O gesto vai ao Python pelo mesmo `.click()`.
    document.addEventListener('keydown', function(ev){
      if(ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
      var pux = ev.target.closest ? ev.target.closest('.puxador') : null;
      if(!pux) return;
      var alvo = colDe(pux);
      var th = pux.closest('th');
      if(!alvo.col || !th) return;
      var px = Math.round(th.getBoundingClientRect().width) + (ev.key === 'ArrowRight' ? 8 : -8);
      px = caber(th, alvo.col, Math.max(PISO, Math.min(TETO, px)));
      pux.dataset.px = String(px);
      ev.preventDefault();
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
        var th = tab.querySelector('th[data-coluna="' + pedaco[0] + '"]');
        if(col) px = caber(th, col, px);
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
    function assentar(){ tabelas().forEach(function(t){ espalhar(t); medir(t); ajustar(t); }); }
    // O OBSERVADOR VIGIA O ATRIBUTO, e só ele. Uma largura que volta do disco
    // chega por `data-larguras` (o pintor escreve o atributo), e é o único
    // caminho de fora para dentro — o `blocos` desta aba não toca o
    // `<colgroup>`. Vigiar o `<tbody>` seria acordar dez vezes por segundo
    // para não fazer nada.
    //
    // E A SETA DA ORDEM, que alarga o rótulo: o `data-ordem` que o pintor põe
    // na seta faz a coluna estreita caber de novo no próprio rótulo (02/10).
    tabelas().forEach(function(t){
      new MutationObserver(function(){ espalhar(t); }).observe(
        t, {attributes: true, attributeFilter: ['data-larguras']});
      var cabeca = t.querySelector('thead');
      if(cabeca) new MutationObserver(function(){ ajustar(t); }).observe(
        cabeca, {attributes: true, subtree: true, attributeFilter: ['data-ordem']});
    });
    // ---- «Aplicar em»: só o quarto lugar abre o «Quando» ------------------
    // No produto quem acende os botões e a linha é a pintura (`editor.alvo.<lugar>`); aqui o
    // desenho faz o mesmo no clique, e a pintura seguinte diz a mesma coisa (idempotente).
    document.addEventListener('click', function(ev){
      var b = ev.target.closest ? ev.target.closest('.seg.alvos button') : null;
      if(!b) return;
      b.parentNode.querySelectorAll('button').forEach(function(o){
        o.classList.toggle('on', o === b);
      });
      var quando = document.querySelector('.so-eventos');
      if(quando) quando.classList.toggle('on', b.dataset.v === 'eventos');
      // Perfil de evento não tem jogo, então não tem «Qual vale primeiro»: o produto apaga o bloco
      // pelo `editor.ordem.ha`, e o desenho faz o mesmo para a tela não ganhar uma linha de rolagem.
      var ordem = document.querySelector('.ordem-vale');
      if(ordem) ordem.classList.toggle('on', b.dataset.v !== 'eventos');
    }, false);

    // ---- «Qual vale primeiro»: arrastar um perfil acima ou abaixo do outro -----
    // O roteiro só MEXE NO DOM e avisa: ao soltar, a posição nova (de 1) vai em `posNova` e o
    // `click` leva o gesto `editor.ordem` ao Python, que regrava as preferências. O `<ol>` é
    // reescrito pelo `blocos` só quando o texto do Python muda, então a ordem arrastada fica
    // até a gravação confirmar.
    var puxado = null;
    document.addEventListener('dragstart', function(ev){
      var li = ev.target.closest ? ev.target.closest('.ordem-vale li') : null;
      if(!li) return;
      puxado = li;
      li.classList.add('arrastando-este');
      if(ev.dataTransfer){
        ev.dataTransfer.effectAllowed = 'move';
        try { ev.dataTransfer.setData('text/plain', li.getAttribute('data-hef-perfil') || ''); }
        catch(e) { /* o WebKit antigo recusa dado vazio */ }
      }
    }, false);
    document.addEventListener('dragover', function(ev){
      if(!puxado) return;
      var alvo = ev.target.closest ? ev.target.closest('.ordem-vale li') : null;
      if(!alvo || alvo === puxado || alvo.parentNode !== puxado.parentNode) return;
      ev.preventDefault();
      var r = alvo.getBoundingClientRect();
      alvo.parentNode.insertBefore(puxado, ev.clientY < r.top + r.height / 2 ? alvo : alvo.nextSibling);
    }, false);
    document.addEventListener('dragend', function(){
      if(!puxado) return;
      var li = puxado;
      puxado = null;
      li.classList.remove('arrastando-este');
      var itens = Array.prototype.slice.call(li.parentNode.children);
      itens.forEach(function(x, i){
        var pos = x.querySelector('.pos');
        if(pos) pos.textContent = String(i + 1);
      });
      li.dataset.posNova = String(itens.indexOf(li) + 1);
      li.click();
    }, false);

    if(document.readyState === 'loading'){
      document.addEventListener('DOMContentLoaded', assentar);
    } else { assentar(); }
  })();
  </script>
"""


MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo" data-dica="Um perfil guarda tudo que você ajustou nas abas">Perfis</span>
      </div>
      <!-- O DESFECHO DO ÚLTIMO GESTO — ver `.desfecho` no CSS. A caixa usa o alvo `classe` (acende
           a tira quando há notícia) e o texto de dentro escreve a frase. NÃO se escreve a tag de
           caixa por extenso em comentário: o balanço do `monta` conta SUBSTRING no documento. -->
      <div class="desfecho" data-hef="perfis.desfecho" data-hef-alvo="classe"><span data-hef="perfis.desfecho"></span></div>
      <div class="quadro-corpo">
        <div class="perfis">

          <div>
            <div class="moldura">
              <div class="sec-rot">Perfis salvos{icone_da_lupa()}{campo_da_lupa()}{icone_do_rotulo(
                  "recarregar", RECARREGA, "Relê a lista",
                  "Relê a lista de perfis. Não mexe no editor ao lado.")}<span class="fora-da-busca" data-hef="perfis.procura.conta" data-hef-alvo="classe"><span data-hef="perfis.procura.conta"></span></span></div>
              <div class="lista">
              <div class="rolo">
              <table class="tab" data-hef="perfis.larguras" data-hef-alvo="atributo"
                     data-hef-atributo="data-larguras" data-tabela="10-perfis.lista"
                     data-larguras="">
                <colgroup><col data-coluna="nome"><col data-coluna="criado"><col data-coluna="modificado"></colgroup>
                <thead><tr>{cabeca("nome", "Nome", "10-perfis.lista", dica="Duplo clique ordena")}{cabeca(
                    "criado", "Criado em", "10-perfis.lista", classe="data", dica="Quando o perfil nasceu")}{cabeca(
                    "modificado", "Modificado em", "10-perfis.lista", classe="data",
                    divisa=False, dica="A última vez que você salvou")}</tr></thead>
                <tbody data-hef="perfis.lista">
{chr(10).join(linha_do_perfil(n, *DATAS_DO_DESENHO.get(n, SEM_DATA), a, escolhido=n == PERFIL_DO_EDITOR) for n,_p,_q,a in PERFIS)}
                </tbody>
              </table>
              </div>
              </div>
            </div>
          </div>

          <div>
            <div class="moldura">
              <!-- OS CAMPOS PEDEM `data-hef-alvo="valor"`: sem ele o `textContent` apagaria as
                   opções de um `select` e não apareceria num `input` (medido em 01/09/2026). -->
              <div class="sec-rot">Editar</div>
              <div class="campos">

              <div class="campo">
                <span>Nome do jogo:</span>
                <span class="val">
                  <input type="text" data-hef="editor.jogo" data-hef-gesto="editor.jogo"
                         data-hef-alvo="valor" list="jogos-desta-maquina"
                         data-dica="Escolha um jogo desta máquina; o perfil leva o nome dele"
                         value="Mortal Kombat 1">{marca_com_dica(
                           "exige", "editor.jogo.exige", "editor.jogo.exigencia")}
                  <datalist id="jogos-desta-maquina" data-hef="editor.jogo.lista"></datalist>
                </span>
              </div>
              <div class="campo">
                <span>Aplicar em:</span>
                <span class="val"><span class="seg alvos">
{chr(10).join(botao_do_alvo(v, r, d) for v, r, d in ALVOS_DO_DESENHO)}
                </span></span>
              </div>
              <div class="campo so-eventos" data-hef="editor.alvo.eventos" data-hef-alvo="classe">
                <span data-dica="Quando o perfil entra">Quando:</span>
                <span class="val ev-val"><select class="estreito" data-hef="editor.evento" data-hef-gesto="editor.quando" data-hef-alvo="valor" aria-label="Quando o perfil entra">
{opcoes_do_quando()}
                </select></span>
              </div>
              <div class="campo so-comando">
                <span data-dica="O perfil entra quando o comando termina sem erro">Comando:</span>
                <span class="val"><input type="text" class="ev-cmd" data-hef="editor.evento.comando" data-hef-gesto="editor.quando" data-que="comando" data-hef-alvo="valor" aria-label="Comando ou arquivo .sh" placeholder="Comando ou arquivo .sh"
                  data-dica="Um comando de terminal ou um arquivo .sh" value=""></span>
              </div>
              <div class="campo">
                <span data-dica="O estilo decide o automático: gatilho, vibração e luz">Estilo de jogo:</span>
                <span class="val"><select class="destaque estreito" data-hef="editor.estilo" data-hef-gesto="editor.estilo" data-hef-alvo="valor">
{opts(ESTILOS, "", vazio=True)}
                </select></span>
              </div>
              <div class="ordem-vale on" data-hef="editor.ordem.ha" data-hef-alvo="classe" data-hef-classe="on">
                <div class="cab" data-dica="Arraste: o de cima vale quando os dois servem">Qual vale primeiro</div>
                <ol data-hef="editor.ordem">
{chr(10).join(item_da_ordem(n, i, n == PERFIL_DO_EDITOR) for i, n in enumerate(ORDEM_DO_DESENHO, 1))}
                </ol>
              </div>
              <div class="guarda">
                <table class="tab miuda" data-hef="guarda.larguras" data-hef-alvo="atributo"
                       data-hef-atributo="data-larguras" data-tabela="10-perfis.guarda"
                       data-larguras="">
                  <colgroup><col data-coluna="controle"><col data-coluna="status"><col data-coluna="id"></colgroup>
                  <thead><tr>
                    <th data-dica="Um ajuste por controle, guardado no perfil">Controle{puxador("controle", "10-perfis.guarda")}</th>
                    <th class="gd-pecas" data-dica="{DICA_DO_STATUS}">Status{puxador("status", "10-perfis.guarda")}</th>
                    <th class="gd-id" data-dica="Por este endereço o perfil reconhece o controle">ID da peça</th>
                  </tr></thead>
                  <tbody data-hef="guarda.linhas">
{chr(10).join(linha_do_controle(c) for c in MESA)}
                  </tbody>
                </table>
              </div>

              </div>
            </div>
          </div>

        </div>
        <div class="barra-quatro-onde"><div class="barra-quatro">
          <button class="btn" data-hef-gesto="duplicar" data-dica="Copia o perfil, com «(cópia)» no nome">Duplicar</button>
          <button class="btn" data-hef-gesto="novo" data-dica="Perfil em branco; com jogo aberto, nasce para ele">Novo</button>
          <button class="btn vermelho" data-hef-gesto="remover" data-hef="perfis.remover" data-dica="Apaga o perfil; pergunta antes">Remover</button>
          <button class="btn verde" data-hef-gesto="ativar" data-dica="Passa a usar este perfil agora">Ativar</button>
        </div></div>
      </div>
    </div>
{ROTEIRO}
'''

# máscara existe e o perfil a guarda — com TRÊS opções (DualSense · Xbox 360 ·
LEGENDA = '''<div class="nota">
  <h2>O que mudou na Perfis do todo (15/10/2026)</h2>
  <ul>
    <li><b>A lista conta quando o perfil nasceu e quando você o mudou.</b> Colunas
      <b>Nome</b>, <b>Criado em</b> e <b>Modificado em</b>; perfil de antes das datas mostra
      <b>—</b>. O duplo clique no cabeçalho ordena (datas: o mais novo primeiro; o <b>—</b> fica
      sempre embaixo). Um clique na linha <b>ativa e abre</b> o perfil, e o <b>Perfil ativo</b>
      do topo e o editor mostram o mesmo nome.</li>
    <li><b>O editor procura o perfil pelo nome do jogo.</b> <b>Nome do jogo</b> (a lista é a dos jogos
      desta máquina), <b>Aplicar em</b> (Jogos, Navegação, Programas, Eventos) e, só em
      Eventos, o <b>Quando</b> (um momento do jogo, do sistema ou o seu comando). Saíram o
      Nome, a Preferência (o controle deslizante), o Funciona em e o Detectar.</li>
    <li><b>Qual vale primeiro.</b> Com dois perfis do mesmo jogo, arrastar um acima do outro
      decide qual entra quando os dois servem. O perfil que o Hefesto criou sozinho cede a vez
      ao seu.</li>
    <li><b>O estilo ganhou três.</b> <b>Nativo</b> (o jogo decide: gatilho, vibração e luz em
      Automático), <b>Visual novel</b> e <b>Adulto</b>; o <b>Point and click</b> trouxe a tabela
      de botões do jogo de clicar. O seletor abre em <b>—</b>.</li>
    <li><b>Quatro botões embaixo</b>, do mesmo tamanho: Duplicar, Novo, Remover e Ativar (verde).
      O botão largo sozinho saiu.</li>
    <li><b>A tabela por controle fala pela cor do plástico</b> (<b>Galactic Purple</b>, <b>White</b>),
      também nos lugares vazios, e as dicas viram <code>data-dica</code>.</li>
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
    <li><b>"Voltar à de ontem"</b> — cada gravação já guarda a anterior e nenhuma tela oferecia isso (<code>profiles/loader.py:1864</code>).</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>"O jogo vê o controle como" não está desenhado aqui.</b> Ele mora hoje na
      <b>Jogar</b>; se vem também para cá, é decisão sua, e a tela não decide por você.
      <span class="marca">O "Modo que liga" saiu desta lista</span> — você já decidiu, e
      ele está no bloco de cima.</li>
    <li><b>O conteúdo dos estilos de jogo</b> continua em aberto: a lista está aqui, o que
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
    """Lê o HTML que acabou de sair e reprova se uma decisão de produto cair."""
    falhas = []

    def exigir(cond, queixa):
        if not cond:
            falhas.append(queixa)

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

    r = re.search(r"\.tab thead th\{[^}]*\}", html)
    exigir(r is not None, "a regra dos cabeçalhos de coluna sumiu do CSS")
    if r:
        exigir("color:var(--fg)" in r.group(0),
               "os cabeçalhos de coluna voltaram ao verde — verde é de ESTADO, não de nome")
        exigir("font-weight:700" in r.group(0),
               "o negrito dos cabeçalhos saiu — sem ele o nome vira dado")

    r = re.search(r"\.sec-rot\{[^}]*\}", html)
    exigir(r is not None, "a regra do título de bloco sumiu do CSS")
    if r:
        exigir("color:var(--rot-campo)" in r.group(0),
               "o título de bloco perdeu o verde que ela pediu")
    for titulo in ("Perfis salvos", "Editar"):
        exigir(f'class="sec-rot">{titulo}<' in html,
               f"o título de bloco '{titulo}' não está na tela")

    for rot in ("Nome do jogo:", "Aplicar em:", "Quando:", "Estilo de jogo:"):
        exigir(f">{rot}</span>" in html, f"o rótulo '{rot}' não está na tela")
    for velho in ("Nome:", "Preferência:", "Funciona em:"):
        exigir(f">{velho}</span>" not in html,
               f"o rótulo '{velho}' voltou — o editor da Perfis do todo não o tem")
    for coluna, rot in (("nome", "Nome"), ("criado", "Criado em"), ("modificado", "Modificado em")):
        th = re.search(rf'<th[^>]*data-coluna="{coluna}"[^>]*>{rot}<', html)
        exigir(th is not None, f"o cabeçalho '{rot}' sumiu da lista de perfis")
    exigir('data-coluna="prioridade"' not in html and 'data-coluna="quando"' not in html,
           "a lista voltou às colunas Preferência e Funciona em — a Perfis do todo mostra "
           "Nome, Criado em e Modificado em")

    fundos = re.findall(r"\.tab thead th:nth-child\(\d\)\{background-image:([^}]*)\}", html)
    exigir(len(fundos) == 3, f"não são 3 fundos de coluna no CSS, e sim {len(fundos)}")
    exigir(len(set(fundos)) == 3, "os fundos das três colunas não são cores diferentes")

    fora = [c for c in MESA if not c.get("conectado", True)]
    exigir("Desconectado</span>" not in html,
           "voltou o «Desconectado» ao lugar vazio — ele fala pela cor do plástico (sem P3)")
    for c in MESA:
        esperado = (SEPARADOR.join([c["nome"], c["via"]]) if c.get("conectado", True)
                    else c["nome"])
        exigir(f'<span data-hef="guarda.nome">{esperado}</span>' in html,
               f"o nome do lugar de {c['nome']} não é «{esperado}»")
        exigir(rotulo(c, "curta") not in html,
               f"o rótulo de mesa «Pn • …» de {c['nome']} continua na tela — a cor do plástico "
               f"fala no lugar do número do jogador")
    exigir(html.count('class="fora"') == len(fora),
           "os lugares desconectados perderam a classe que os apaga")

    # o alvo é o idempotente, e nenhum `--plastico` cravado voltou ao miolo.
    exigir(html.count('data-hef="guarda.plastico"') == len(MESA),
           f"não são {len(MESA)} barras com endereço `guarda.plastico` na tabela por controle")
    exigir(html.count('data-hef-alvo="cor"') == len(MESA),
           "a barra do plástico perdeu o alvo `cor` — o `fundo` soma uma pintura por tique")
    exigir("--plastico:" not in html.split('class="miolo"')[-1],
           "voltou um `--plastico` cravado no miolo — identidade de aparelho sem endereço")

    linhas = re.findall(r"<tr data-hef-uniq=\"[^\"]+\"[^>]*>", html)
    exigir(len(linhas) == len(MESA),
           f"não são {len(MESA)} linhas na tabela por controle, e sim {len(linhas)}")
    na_mesa_com_dica = [t for c, t in zip(MESA, linhas, strict=True)
                        if c.get("conectado", True) and "data-dica=" in t]
    exigir(not na_mesa_com_dica,
           f"{len(na_mesa_com_dica)} linha(s) de controle NA MESA voltaram a ter "
           f"dica — ela congela o nome do modelo do desenho por cima de um "
           f"aparelho que é outro")
    fora_sem_dica = [c["pref"] for c, t in zip(MESA, linhas, strict=True)
                     if not c.get("conectado", True) and "data-dica=" not in t]
    exigir(not fora_sem_dica,
           f"o lugar vazio {fora_sem_dica} perdeu a dica que explica por que ele "
           f"continua na tabela — ela não fala de aparelho nenhum")

    # O QUE ACONTECEU LÁ, com os quatro DualSense do usuário na mesa: o daemon publica
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

    exigir(".campos > .campo::after" not in html,
           "as linhas horizontais voltaram ao editor de perfil")

    celulas = re.findall(r'<span class="gr[^"]*" data-hef="guarda\.secao"[^>]*>', html)
    exigir(len(celulas) == len(MESA) * len(SECOES),
           f"não são {len(MESA) * len(SECOES)} células de `guarda.secao` "
           f"({len(MESA)} controles x {len(SECOES)} seções), e sim {len(celulas)}")
    com_dica = [c for c in celulas if "data-dica=" in c]
    exigir(not com_dica,
           f"{len(com_dica)} célula(s) de `Ajuste próprio` voltaram a ter dica — "
           f'ela mandou as oito saírem: "Auto falante é auto falante, gatilho é gatilho"')

    for endereco in ("guarda.dica", "guarda.incerto", "guarda.proprio"):
        quantas = html.count(f'data-hef="{endereco}"')
        exigir(quantas == len(MESA) * len(SECOES),
               f"não são {len(MESA) * len(SECOES)} células de `{endereco}`, e sim "
               f"{quantas}")
    dicas_das_celulas = re.findall(
        r'<span class="gc" data-hef="guarda\.dica"[^>]*?data-dica="([^"]*)"', html)
    estranhas = [d for d in dicas_das_celulas
                 if d not in (DICA_DO_NAO_DIZ, _RESUMO_DA_MIRA_NA_CENA)
                 and not re.fullmatch(re.escape(DICA_DA_MASCARA).replace(
                     re.escape("{mascara}"), ".+"), d)]
    exigir(not estranhas,
           f"a célula da coluna «Status» ganhou uma dica que o pacote não "
           f"escreve: {estranhas}")

    sem_alvo = [c for c in celulas if 'data-hef-alvo="classe"' not in c]
    exigir(not sem_alvo,
           f"{len(sem_alvo)} célula(s) de `guarda.secao` sem "
           f'`data-hef-alvo="classe"` — pintá-las apagaria o glifo')

    exigir('data-hef-secao="mic"' in html,
           "a coluna do microfone sumiu da linha `Ajuste próprio` (decisão nº20)")
    sem_nome = [campo for campo, _ in SECOES if campo not in NOME_DA_SECAO]
    exigir(not sem_nome,
           f"a(s) seção(ões) {sem_nome} não têm nome em `NOME_DA_SECAO` — a dica "
           f"do cabeçalho não saberia como chamá-la na tela")

    exigir(html.count('data-hef="perfis.desfecho"') == 2,
           "a tira do desfecho perdeu um dos dois endereços — sem o `classe` "
           "ela fica acesa com um travessão; sem o `<span>` ela nunca escreve")
    exigir('class="desfecho" data-hef="perfis.desfecho" data-hef-alvo="classe"' in html,
           "a tira do desfecho perdeu o alvo `classe` — ela acenderia sempre")
    exigir("visibility:hidden" in html,
           "a tira do desfecho perdeu o `visibility:hidden` — ela apareceria "
           "vazia em toda tela sem recado")

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

    for classe, estado, frase in (
            ("exige", "editor.jogo.exige", "editor.jogo.exigencia"),):
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

    exigir('data-hef="editor.jogo.rotulo"' not in html and "gesto=\"detectar\"" not in html,
           "o rótulo do jogo ou o Detectar voltou ao editor — o campo «Nome do jogo» é o único "
           "caminho, e o perfil leva o nome do jogo escolhido")
    exigir("grid-template-columns:var(--rot-p) minmax(0,1fr)" in html,
           "a fileira do campo voltou a `1fr` — uma pista de grade cresce com o "
           "MIN-CONTENT e estoura a página")

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

    exigir("O quadro &quot;Modo&quot;" in LEGENDA or 'O quadro "Modo"' in LEGENDA,
           "a legenda (nota de revisão, fora da página) parou de dizer que o quadro Modo saiu e onde ele mora — "
           "quem abrir a aba depois de 11/09 procuraria um quadro que a versão "
           "anterior tinha, sem nada na tela que o mande à Jogar")

    # `Daemon.gravar_o_modo_escolhido`, que resolve o alvo por
    exigir("no perfil que está valendo" in LEGENDA,
           "a legenda perdeu o ALCANCE do que a aba Jogar escreve — sem ele a "
           "frase promete que a Jogar escolhe o modo de QUALQUER perfil, e o "
           "escritor (`Daemon.gravar_o_modo_escolhido`) só alcança o perfil "
           "ativo")
    exigir("quem o escolhe é a Jogar" not in LEGENDA,
           "a frase larga voltou à legenda — ela afirma que a Jogar escolhe o "
           "modo de qualquer perfil, e a Jogar grava só no que está valendo")

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

    exigir("editor.prioridade" not in html and 'class="trilho"' not in html,
           "a Preferência (o slider) voltou à tela — a ordem entre perfis do mesmo jogo agora se "
           "arrasta em «Qual vale primeiro»")
    exigir("editor.ambiente" not in html and "editor.nome\"" not in html,
           "o «Funciona em» ou o «Nome:» voltou à tela — «Aplicar em» e «Nome do jogo» os "
           "substituem")

    for e in ESTILOS_DO_MOTOR:
        exigir(f">{e.rotulo}</option>" in html,
               f"o estilo '{e.rotulo}' está no motor e não está no `<select>` "
               f"— o gesto saberia aplicá-lo e ela não teria como pedir")
    exigir('<option value="" disabled selected>—</option>' in html,
           "a opção vazia do estilo de jogo saiu — o campo voltaria a abrir "
           "afirmando um estilo que perfil nenhum guarda")
    exigir('data-dica="O estilo decide o automático: gatilho, vibração e luz">Estilo de jogo:' in html,
           "a dica do estilo de jogo mudou — ela é a frase curta do desenho")
    opcoes = re.search(r'<select class="destaque estreito"[^>]*>(.*?)</select>', html, re.S)
    exigir(opcoes is not None, "o select do estilo sumiu")
    if opcoes:
        rotulos = re.findall(r">([^<]+)</option>", opcoes.group(1))
        exigir(rotulos[:2] == ["—", "Nativo"] and rotulos[-1] == "Personalizado",
               f"o estilo abre em «—», depois «Nativo», e fecha em «Personalizado»: {rotulos}")
        exigir('<option data-dica="O jogo decide">Nativo</option>' in opcoes.group(1),
               "o Nativo perdeu a dica «O jogo decide»")
    exigir("Criar perfil de point and click" not in html and "Criar perfil de point-and-click"
           not in html,
           "voltou o botão «Criar perfil de point and click» — o estilo Point and click do "
           "select já faz o perfil")
    exigir("um-so" not in html and 'class="botoes' not in html,
           "voltou o botão largo sozinho (`.um-so`) — o Ativar fica na barra de quatro")
    exigir(not re.search(r'\bclass="[^"]*\bajuda\b', html),
           "voltou o «?» do título da Perfis — a dica agora mora no próprio título")

    barra = re.search(r'<div class="barra-quatro">(.*?)</div></div>', html, re.S)
    exigir(barra is not None, "a barra dos quatro botões sumiu")
    if barra:
        gestos = re.findall(r'data-hef-gesto="([^"]+)"', barra.group(1))
        exigir(gestos == ["duplicar", "novo", "remover", "ativar"],
               f"a barra de baixo não é Duplicar, Novo, Remover, Ativar: {gestos}")
    alvos = re.findall(r'data-hef-gesto="editor\.alvo" data-v="([^"]+)"', html)
    exigir(alvos == ["jogos", "navegacao", "programas", "eventos"],
           f"«Aplicar em» não tem os quatro lugares na ordem: {alvos}")
    exigir('class="campo so-eventos"' in html and 'hidden' not in
           re.search(r'<div class="campo so-eventos"[^>]*>', html).group(0),
           "o «Quando» perdeu a classe `so-eventos` ou ganhou `hidden` (quem esconde é o CSS)")
    exigir('data-hef="editor.ordem"' in html and 'class="ordem-vale on"' in html,
           "o bloco «Qual vale primeiro» sumiu")
    exigir(".ordem-vale.on{display:block}" in html and 'data-hef="editor.ordem.ha"' in html,
           "«Qual vale primeiro» deixou de sumir com menos de dois perfis no jogo")

    exigir("--rot-p:86px" in html,
           "a coluna do rótulo não é mais a medida do rótulo mais largo (86px)")
    exigir("--rot-p:104px" not in html,
           "a coluna do rótulo voltou aos 104px — 22px de vão morto por rótulo")


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

    regra_seta = re.search(r"\.ordena\{[^}]*\}", html)
    exigir(regra_seta is not None, "a regra da seta da ordem sumiu do CSS")
    if regra_seta:
        exigir("pointer-events:none" in regra_seta.group(0),
               "a seta da ordem perdeu o `pointer-events:none` — ela carrega o "
               "gesto `ordenar`, e sem esta linha um clique "
               "SIMPLES no cabeçalho passa a ordenar. Ela pediu DUPLO clique, "
               "e a razão está na regra: o cabeçalho é `sticky` a um pixel da "
               "célula que troca o perfil aberto no editor")
    for coluna in ("nome", "criado", "modificado"):
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
            exigir('data-hef-alvo="atributo"' in seta.group(0)
                   and 'data-hef-atributo="data-ordem"' in seta.group(0),
                   f"a seta da coluna `{coluna}` mudou de alvo — só o "
                   f"`atributo` chega à tela nos TRÊS estados: ele é o único "
                   f"que APAGA quando o valor é vazio. Com `classe` a seta "
                   f"fica vazia e invisível; com `texto`, as colunas não "
                   f"ordenadas ganham um «—»")

    regra_base = re.search(r"\.ordena\{[^}]*\}", html)
    exigir(regra_base is not None and "margin-left" not in regra_base.group(0),
           "a regra `.ordena` voltou a ter margem incondicional — um span vazio "
           "com margem empurra o rótulo e abrevia o cabeçalho na tela, com a "
           "palavra inteira no HTML. A margem mora em `.ordena[data-ordem]`")
    exigir(re.search(r"\.ordena\[data-ordem\]\{[^}]*margin-left", html) is not None,
           "a seta ORDENADA perdeu a margem — ela encosta no rótulo da coluna")
    exigir('.tab col[data-coluna="criado"],.tab col[data-coluna="modificado"]{width:104px}' in html,
           "as colunas de data perderam a largura que cabe «dd/mm/aaaa» com a seta da ordem")

    for seta_glifo in ("↑", "↓"):
        exigir(f'.ordena[data-ordem="{seta_glifo}"]::after{{content:"{seta_glifo}"}}' in html,
               f"o glifo `{seta_glifo}` sumiu do CSS — quem desenha a seta é o "
               f"`content`, porque o piloto não escreve texto no alvo "
               f"`atributo`. Sem esta regra a seta some da tela e nada diz "
               f"qual coluna ordena")

    for gesto_, canto, dica_ in (
            ("recarregar", "Perfis salvos", "Relê a lista"),):
        icone = re.search(rf'<button type="button" class="icone-rot" '
                          rf'data-hef-gesto="{gesto_}"[^>]*>', html)
        exigir(icone is not None,
               f"o gesto `{gesto_}` não é um ícone do rótulo — ele virou ícone "
               f"por ordem dela em 11/09/2026, e o nome do gesto não muda por "
               f"troca de invólucro")
        if icone:
            exigir(f'data-dica="{dica_}"' in icone.group(0),
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
    exigir('data-hef-gesto="voltar-a-de-ontem"' not in html,
           "o `voltar-a-de-ontem` voltou à tela — a ordem dela de 11/09 foi "
           "removê-lo, e o ícone dele ao lado de «Editar» era lido como o "
           "recarregar duplicado")
    regra_icone = re.search(r"\.icone-rot\{[^}]*\}", html)
    exigir(regra_icone is not None, "a regra do ícone do rótulo sumiu do CSS")
    if regra_icone:
        exigir("width:24px" in regra_icone.group(0)
               and "height:24px" in regra_icone.group(0),
               "o ícone do rótulo perdeu o alvo de 24x24 — o desenho tem 11px, "
               "e 11px é o DESENHO, não a área clicável")

    th_status = re.search(r'<th class="gd-pecas"[^>]*>([^<]*)', html)
    exigir(th_status is not None, "o cabeçalho da coluna do meio sumiu")
    if th_status:
        exigir(th_status.group(1).strip() == "Status",
               f"o rótulo da coluna não é `Status`: {th_status.group(1)!r}. "
               f"Ela mandou trocar o nome em 11/09/2026, e SÓ o nome")
    exigir("controles com ajuste próprio" not in html,
           "o contador «controles com ajuste próprio» voltou ao título — a Perfis do todo não o tem")
    exigir(DICA_DO_STATUS in html,
           "a dica do `<th>` não diz as duas camadas — ela é quem explica o que "
           "o glifo aceso e o ponto embaixo querem dizer, e encurtar o rótulo só "
           "funciona porque a explicação tem outro dono")
    exigir("guarda um ajuste só deste controle" not in html,
           "a frase do significado de antes voltou à página — a coluna pinta o "
           "controle agora, e o disco é o ponto")

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


if __name__ == "__main__":
    import os
    import pathlib
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-10-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("10-perfis", "Perfis", MIOLO, CSS)
    _conferir(onde.pagina("10-perfis.html").read_text(encoding="utf-8"))
    shutil.copyfile(_prova / "10-perfis.html", _real / "10-perfis.html")
    shutil.rmtree(_prova)
    ROT_P = re.search(r"--rot-p:(\d+)px", CSS).group(1)
    FORA = sum(1 for c in MESA if not c.get("conectado", True))
    print(f"10-perfis: OK, {n} divs · rótulo à esquerda com dois pontos, coluna de {ROT_P}px, "
          f"zero divisórias no editor · Perfis salvos e Editar · {FORA} lugar(es) vazio(s)")
