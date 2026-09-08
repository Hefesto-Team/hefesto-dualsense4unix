# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
# que por sua vez lia um `topo.html` de /tmp parado às 10:59. Três das dez
# abas vinham de um montador e de um esqueleto de ontem, e nenhuma correção
# no topo.html desta pasta as alcançava. Achado em 27/08.
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import csv
import dataclasses
import re

import onde
# `MESA` SAIU DO IMPORT em 02/09/2026, e a razão é a mesma que mudou a régua da
# promessa: os cartões deixaram de contar controle. `CONECTADOS` FICA, e agora
# só como ESTADO DE PARTIDA: o texto do "?" ("a resposta vale igual para os N")
# ganhou endereço em 03/09/2026 e o pacote o repinta com a mesa VIVA a cada
# tique — ver `dl.quantos_html`. Enquanto o número saía daqui e ficava, a tela
# dela dizia "os 2 (1 no cabo, 1 no rádio)" a dois centímetros de um cabeçalho
# que dizia "1 controle: 1 USB · 0 BT".
#
# `cor_da_zona` entrou em 03/09/2026 e serve à RÉGUA, não ao desenho: é ele que
# transforma a isenção das cinco variáveis do esqueleto numa MEDIÇÃO. Ver
# `identidade_congelada`.
# `CSS_POPUP` ENTROU EM 08/09/2026, com a tela de registro — e a AUSÊNCIA dele
# era um defeito que régua nenhuma via e a FOTO viu na primeira olhada: sem as
# regras `.tela-nova{display:none}` / `:target{display:flex}`, a caixa de
# registro renderiza SEMPRE, embaixo da janela, aberta e sem moldura. A página
# publicada saiu assim, com os 49 portões verdes e 60 testes passando.
#
# O DONO É O `monta.py` desde 29/08, e é justamente o caso que ele existe para
# cobrir: a segunda aba com pop-up não copia as 49 linhas da primeira — ela
# IMPORTA. A `aba06` já fazia; esta faltava.
from monta import CONECTADOS, CSS_POPUP, cor_da_zona, monta

# O DESENHO DOS CARTÕES TEM UM DONO SÓ, e ele é o mesmo que o pacote
# `pacotes/a07_lancadores.py` usa em tempo de execução. Enquanto os cartões
# moravam AQUI, os números eram digitados — `412 jogos`, `28 jogos`, `3 jogos já
# sabem por onde entrar` — e o produto não tinha por onde contradizê-los.
# Medido em 02/09/2026 na máquina dela: 23 jogos instalados, 63 appids com o
# atalho no vdf, 0 pontes confirmadas. Quatro números, quatro contradições.
#
# `cartoes(None)` é o estado da PRIMEIRA MEIA VOLTA — o que a tela mostra antes
# de a leitura de disco voltar. É o único desenho honesto para uma página
# estática: ela não sabe nada da biblioteca dela até o produto abrir.
import desenho_dos_lancadores as dl

# ---------------------------------------------------------------------------
# A RÉGUA DA IDENTIDADE DESTA ABA — CINCO FORMAS, e três delas cegas em toda a
# casa até 03/09/2026.
#
# A LEI, e ela é dela:
#
#     "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
#      players com cada controle — tudo isso muda de acordo com o controle
#      identificado no canto superior. é white no p1, mas a borda de tudo é
#      cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"
#
# O QUE JÁ HAVIA, e cobre DUAS formas: `scripts/check_identidade_vem_de_cima.py`
# e `tests/unit/test_a_aba_07_usa_o_controle_da_fita.py` pegam (1) o NOME de um
# colorway no texto e (2) o `--plastico:` cravado.
#
# O QUE NENHUMA DAS DUAS ENXERGA, medido nesta árvore em 03/09/2026 injetando
# cada forma na `07-lancadores.html` e rodando as duas réguas — as três saíram
# VERDES sobre a página envenenada:
#
#   3. o APELIDO do modelo (`cosmic-red`), que é o que vai num
#      `data-colorway="…"` ou numa classe. Nenhum "Cosmic Red" aparece: o
#      apelido não é o nome, e a régua por nome não o vê. É exatamente a forma
#      que a frase dela nomeia — *"os svgs não são os que o meu mapa cataloga"*;
#   4. o HEXADECIMAL do mapa (`#A51C48`) solto num `fill=` ou num
#      `border-color:`. Sem nome e sem `--plastico:`, ele passa pelas duas —
#      e é a forma de *"a borda de tudo é cosmic red"*;
#   5. o `var(--cosmic-red)`, que empresta a tabela de CINCO plásticos do
#      esqueleto. É a mais silenciosa das três: não há nome, nem apelido em
#      posição de valor, nem hexadecimal — só uma referência.
#
# A TABELA DO ESQUELETO NÃO É ISENTA POR DECRETO. O `topo.html` declara
# `--cosmic-red`, `--nova-pink`, `--starlight-blue`, `--galactic-purple` e
# `--midnight-black` no `:root` das DEZ páginas, e `monta.monta()` reescreve o
# valor de cada uma com `cor_da_zona`, que lê o mapa dela. A régua CONFERE isso
# em vez de acreditar: se um sexto plástico for digitado à mão no esqueleto, ou
# se um dos cinco divergir do CSV, ela acusa. Isenção sem razão é ponto cego com
# nome bonito; isenção MEDIDA é régua.
#
# `--conferir <arquivo>` roda só esta régua sobre um HTML qualquer, sem gerar
# nada. É por essa porta que a mordida entra
# (`tests/unit/test_aba07_a_cor_do_aparelho_nao_se_crava.py`): sem ela o teste
# teria de reescrever a regra, e duas escritas da mesma regra é o defeito que
# esta casa mais paga.
# ---------------------------------------------------------------------------
#: A prosa não conta: `<!-- -->` e `/* */` falam DE cor sem pintar nenhuma.
#: Contá-los inflaria o número, e número inflado é o que esta casa mais derruba.
_PROSA = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)

#: A tabela do esqueleto, na forma `--<apelido>:#hex`. O `<apelido>` só vale se
#: for um `id` do mapa — `--plastico:#fff` cai fora daqui e é acusado à parte.
_TABELA_DO_ESQUELETO = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})")

#: Um elemento com `data-colorway`. O CONTRATO do alvo novo (frente irmã,
#: 03/09/2026) é `data-hef-alvo="atributo"` + `data-hef-atributo="data-colorway"`
#: no MESMO elemento — o par em atributos separados, como o alvo `classe` já faz.
_COM_COLORWAY = re.compile(r"<[a-zA-Z][^>]*\bdata-colorway\s*=[^>]*>")


def _mapa_das_cores() -> list[dict[str, str]]:
    """As 233 linhas de `docs/data/cores-do-dualsense.csv`: 28 modelos, 10 zonas.

    Digitar aqui um nome, um apelido ou um hexadecimal criaria a segunda lista
    que o CSV existe para não ter — e ela envelheceria calada no dia em que ela
    mapear o vigésimo nono modelo.
    """
    linhas = [ln for ln in (onde.RAIZ / "docs/data/cores-do-dualsense.csv")
              .read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    return list(csv.DictReader(linhas))


def identidade_congelada(doc: str) -> list[str]:
    """As cores de APARELHO cravadas nesta página, uma frase por achado.

    Devolve lista vazia quando a página está limpa — que é o estado da
    `07-lancadores` desde 03/09/2026, e o que esta régua existe para manter.
    """
    mapa = _mapa_das_cores()
    nomes = sorted({(ln.get("nome") or "").strip() for ln in mapa} - {""})
    apelidos = sorted({(ln.get("id") or "").strip() for ln in mapa} - {""})
    tons = sorted({(ln.get("hex") or "").strip().lower() for ln in mapa} - {""})

    # As quebras de linha sobrevivem ao apagador de prosa: sem isso um
    # comentário de vinte linhas vira uma só e todo número depois dele erra.
    limpo = _PROSA.sub(lambda m: "".join(c if c == "\n" else " " for c in m.group(0)), doc)
    achados: list[str] = []

    # 0. A TABELA DO ESQUELETO, conferida contra o mapa antes de ser isentada.
    vaos: list[tuple[int, int]] = []
    for m in _TABELA_DO_ESQUELETO.finditer(limpo):
        apelido, tom = m.group(1), m.group(2)
        if apelido not in apelidos:
            continue
        vaos.append(m.span())
        do_mapa = cor_da_zona(apelido) or ""
        if tom.lower() != do_mapa.lower():
            achados.append(
                f"a página traz `--{apelido}:{tom}` e o mapa dela diz "
                f"`{do_mapa or 'nada'}`. As cinco variáveis de plástico do "
                f"esqueleto são REESCRITAS por `monta.cor_da_zona`; um valor "
                f"que diverge é hexadecimal digitado à mão, não leitura do CSV.")

    def _fora_da_tabela(i: int) -> bool:
        return not any(a <= i < b for a, b in vaos)

    # 1. O NOME do modelo no que a tela mostra.
    achados += [f"nome de colorway na página: {nome!r}. A identidade do controle "
                f"vem da FITA, que lê do APARELHO — um nome de modelo escrito "
                f"aqui é o desenho mandando na tela do produto."
                for nome in nomes if len(nome) >= 4 and nome in limpo]

    # 2. A COR do plástico cravada.
    if re.search(r"--plastico\s*:", limpo):
        achados.append(
            "voltou um `--plastico:` cravado à página. A cor do plástico é "
            "leitura de aparelho — quem a escreve é o pacote, nunca o gerador.")

    # 3. O APELIDO do modelo em posição de valor (`data-colorway`, classe…).
    for apelido in apelidos:
        agulha = rf"(?<![A-Za-z0-9_-]){re.escape(apelido)}(?![A-Za-z0-9_-])"
        achados += [f"apelido de modelo do mapa na página: {apelido!r}. É o que "
                    f"vai num `data-colorway` ou numa classe, e a régua por NOME "
                    f"não o enxerga — nenhum 'Cosmic Red' aparece num "
                    f"`data-colorway=\"cosmic-red\"`."
                    for m in re.finditer(agulha, limpo) if _fora_da_tabela(m.start())]

    # 3b. A TABELA DE CINCO DO ESQUELETO, emprestada por esta aba.
    achados += [f"a página usa `var(--{apelido})`. Aquelas cinco são a paleta do "
                f"DESENHO, congelada no esqueleto: elas respondem por 5 dos 28 "
                f"modelos do mapa, e quem tiver o sexto vê a cor de outro "
                f"aparelho. A cor do controle DELA vem do pacote, no tique."
                for apelido in apelidos if f"var(--{apelido})" in limpo]

    # 4. O HEXADECIMAL do mapa solto — a forma de "a borda de tudo é cosmic red".
    for tom in tons:
        achados += [f"hexadecimal do mapa cravado na página: {tom}. Ele não tem "
                    f"nome nem `--plastico:` e por isso atravessa as duas réguas "
                    f"que já havia — e é a cor de um modelo que pode não ser o "
                    f"dela."
                    for m in re.finditer(re.escape(tom), limpo, re.I)
                    if _fora_da_tabela(m.start())]

    # 5. O `data-colorway` SEM o endereço que deixa o produto reescrevê-lo.
    achados += [f"`data-colorway` sem endereço em {' '.join(m.group(0).split())[:90]!r}. "
                f"O contrato é `data-hef-alvo=\"atributo\"` com "
                f"`data-hef-atributo=\"data-colorway\"` no mesmo elemento; sem "
                f"eles o SVG fica com o colorway do desenho para sempre."
                for m in _COM_COLORWAY.finditer(limpo)
                if 'data-hef-alvo="atributo"' not in m.group(0)
                or 'data-hef-atributo="data-colorway"' not in m.group(0)]

    return achados


if "--conferir" in sys.argv:
    _ALVO = pathlib.Path(sys.argv[sys.argv.index("--conferir") + 1])
    _PROBLEMAS = identidade_congelada(_ALVO.read_text(encoding="utf-8"))
    for _p in _PROBLEMAS:
        print(f"ERRO: {_p}", file=sys.stderr)
    print(f"{_ALVO.name}: {len(_PROBLEMAS)} cor(es) de aparelho cravada(s)")
    raise SystemExit(1 if _PROBLEMAS else 0)


# ---------------------------------------------------------------------------
# A MESA RESPONDE PELO NÚMERO — aqui não se escreve "quatro".
#
# Pedido dela, 27/08: cada aba reescrita para quatro controles conectados. Nesta
# aba o que muda NÃO é o desenho (ela fechou: *"lançadores perfeito parabéns"*) e
# não é feature nova (ela: *"essa aba em si só vamos desenhar e deixar placeholder
# mesmo"*). O que muda é o ALCANCE DA PROMESSA: a aba dizia "o controle chega", no
# singular, com quatro na mesa — e a primeira pergunta de quem lê passa a ser
# *"qual deles?"*.
#
# A resposta é: os quatro, e por uma razão medida — nenhum dos cinco impedimentos
# desta aba depende de controle. `integrations/prontuario_dos_jogos.py` não tem
# UMA função que receba controle, MAC, device ou transporte: `SEM_WRAPPER`,
# `LINHA_INTOCAVEL`, `EXCECAO_INERTE`, `PONTE_DIVERGENTE` e `SEM_EXECUTAVEL` são
# fatos do jogo em disco (`:139-143`), e as duas curas de `_CURAS` (`:878`) mexem
# na linha de inicialização e na exceção do Steam Input. É o mesmo motivo pelo
# qual a fita desta aba nasce esmaecida (fora de `monta.ABAS_QUE_ESCOLHEM`).
#
# Por isso o número sai de `MESA` e não do teclado: no dia em que a mesa mudar, o
# texto dos cartões muda junto com o cabeçalho, que já sai de lá.
# QUEM CONTA CONTROLE CONTA QUEM ESTÁ NA MESA — 31/08/2026. A `MESA` passou a ter
# um campo `conectado`, e com ele dois lugares vazios: esta aba prometia que "os 4
# controles chegam" com dois deles fora, em QUATRO cartões de lançador. A promessa
# não era pouca — ela é o que a aba existe para dizer.
#
# `MESA` continua sendo a lista dos quatro LUGARES; `CONECTADOS` é quem está neles.
N_CTRL = len(CONECTADOS)
N_USB = sum(1 for c in CONECTADOS if c["via"] == "USB")
N_BT = sum(1 for c in CONECTADOS if c["via"] == "BT")

#: A promessa de um cartão que não impede nada, no plural da mesa.
CHEGAM = f"Os {N_CTRL} controles chegam."

CSS = """
  /* ---------- Lançadores ---------- */
  .lancadores{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .lanc{border:1px solid var(--border-sutil);border-radius:8px;background:var(--app-bg);padding:11px 13px}
  .lanc.chega{border-color:rgba(80,250,123,.28)}
  .lanc.impede{border-color:var(--orange)}
  /* O CARTÃO "não achei" DEIXOU DE USAR `opacity` — 30/08/2026, mesma cura da
     `.fita.inerte` (topo.html) e pelo mesmo motivo medido: com `opacity:.5` o
     corpo caía a 2,55:1, o selo NÃO ACHEI a 1,95:1 e os dois botões a 3,37 e
     3,55:1 — e nenhuma régua que leia `color` enxergava, porque a opacidade
     estava no PAI. Este cartão não é controle desabilitado: ele é informação
     viva ("instale e clique em Procurar de novo"), e informação se lê. */
  .lanc.ausente{background:transparent}
  .lanc.ausente .lanc-nome{color:var(--texto-suave)}
  .lanc.ausente .lanc-diz,
  .lanc.ausente .lanc-jogos{color:var(--comment)}
  .lanc-topo{display:flex;align-items:center;gap:9px;margin-bottom:7px}
  .lanc-nome{font-size:12.5px;font-weight:600;color:var(--fg)}
  .lanc-selo{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600;
             font-family:'JetBrains Mono',monospace}
  .lanc-selo.ok{background:var(--green);color:var(--app-bg)}
  .lanc-selo.warn{background:var(--orange);color:var(--app-bg)}
  /* o selo apagado ficava a 3,47:1 sobre o próprio fundo — o texto claro
     dá 9,3:1 e o selo continua lendo como "desligado" pelo fundo cinza. */
  /* `nao_sei` DIVIDE O ESTILO COM `off`, e é decisão: as duas dizem "não há o
     que agir aqui", e um terceiro tom só acrescentaria uma cor para ela
     decodificar. O selo nasceu em 02/09/2026, quando a medição mostrou que
     `CHEGAM` e `NÃO CHEGAM` eram as duas afirmações que o produto NÃO pode
     fazer sobre Heroic, Lutris, RetroArch, Dolphin e mGBA — ele não tem uma
     função sequer que olhe para eles. */
  .lanc-selo.off,.lanc-selo.nao_sei{background:var(--border-forte);color:var(--texto-suave)}
  .lanc-jogos{margin-left:auto;font-size:11px;color:var(--texto-mudo);
              font-family:'JetBrains Mono',monospace}
  /* DUAS LINHAS CRAVADAS, e é `height` — não `min-height`.
     Com `min-height:32px` o corpo de uma linha dava 32px e o de duas 33,3px, e a
     fileira de botões dos dois cartões de uma mesma linha nascia 1,3px torta. A
     escala do esqueleto tropeçou nisto uma vez (LEIA-ME, cicatriz 2): min-height
     não encolhe, e aqui também não ESTICA — quem alinha é a altura fixa.
     2,9em = 1,45 (line-height) × 2 linhas, então o número acompanha a fonte. */
  /* A ALTURA FIXA CAIU — 02/09/2026, e foi a FOTO que a derrubou.
     Aqui morava `height:2.9em` ("duas linhas cravadas"), e ela existia para
     alinhar a fileira de botões dos dois cartões de uma mesma linha da grade:
     com `min-height` o corpo de uma linha dava 32px e o de duas 33,3px, e a
     fileira nascia 1,3px torta.
     Ela só funcionava porque o texto era ESCRITO À MÃO e cabia em duas linhas.
     Com o corpo vindo do produto isso acabou: a frase da sentinela — que
     nomeia o jogo e diz o que vai acontecer — tem CINCO linhas, e na primeira
     foto da aba viva ela atravessou os botões por cima. Um transbordo de 3
     linhas é muitas ordens de grandeza pior que 1,3px de desalinho.
     O ALINHAMENTO NÃO SE PERDEU, e é o ponto: quem alinha agora é o cartão,
     não o parágrafo. `.lanc` vira coluna flex, a grade já iguala a ALTURA dos
     cartões irmãos (é `grid`), e `.acoes{margin-top:auto}` empurra a fileira
     para o pé — os dois cartões da mesma linha ficam com os botões na MESMA
     altura, exatos, com corpos de tamanhos diferentes. O `min-height` continua
     para o caso curto, que é o que reservava a segunda linha. */
  .lanc{display:flex;flex-direction:column}
  .lanc-diz{font-size:11.5px;color:var(--texto-mudo);min-height:2.9em;line-height:1.45}
  .lanc-diz b{color:var(--orange)}
  .lanc-diz b.roxo-txt{color:var(--purple)}
  /* `margin-top:auto` E NÃO `8px`: é ele que empurra a fileira para o PÉ do
     cartão, e é o que substitui a altura fixa do corpo (ver acima). O vão de
     8px vira `padding-top`, para o caso do cartão curto em que o `auto` não
     tem folga para consumir. */
  .lanc .acoes{margin-top:auto;padding-top:8px;gap:6px}
  /* O BOTÃO DENTRO DO CARTÃO NÃO ENCOLHE. Aqui morava
     `.lanc .btn{font-size:11px;padding:0 11px}`, e era a ÚNICA quebra de "mesma
     família, mesma largura" das dez abas: `Procurar de novo` — o MESMO texto, a
     MESMA classe `btn` — media **130,5px** na fileira do quadro e **114,2px**  (noqa-acento: verbo medir, imperfeito)
     dentro do cartão do `Dolphin · mGBA`, porque a regra trocava a fonte (12,5
     → 11px) e o vão lateral (13 → 11px) só de um lado. Dois botões iguais em
     tamanhos diferentes na mesma tela é o que faz a janela parecer montada por
     pessoas diferentes.
     A altura já vinha certa (34px, do `--h-acao` do esqueleto): a regra não a
     tocava, e por isso a régua de alinhamento passava verde — ela mede altura,
     não largura. Sem a regra, o `.btn` do `topo.html` responde pelos onze
     botões da aba, e a fileira mais larga (o RetroArch, com `Aplicar o estilo
     Retrô/Emulador`) continua cabendo no cartão sem quebrar linha — o que
     importa porque `.acoes` tem `flex-wrap:wrap` e uma quebra devolveria a
     altura que o carimbo acabou de economizar. */
  /* O CARIMBO MORA NA FILEIRA DOS BOTÕES, à direita — e não numa linha própria
     acima dela. Medido em 28/08: como linha própria ele custava 21px (6 de
     margem + 13 de altura + 2 de arredondamento) que SÓ o cartão do Steam
     pagava, e a fileira dele nascia em y=370,3 contra y=349,3 do Heroic, ao
     lado. Os outros dois pares batiam exato, o que provava que era defeito.
     A cura é a dela: ENCOLHER O MAIS ALTO. Reservar a linha vazia nos outros
     cinco cartões alinharia igual, mas engordando a aba em 63px — o inverso da
     regra, e numa aba que já passa da dobra.
     Aqui ele também casa com `.lanc-jogos`, que é o outro texto à direita do
     cartão: um no alto, um no pé. `nowrap` porque `.acoes` quebra linha, e uma
     quebra devolveria os 21px pela porta dos fundos. */
  .carimbo{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;color:var(--green);
           margin-left:auto;white-space:nowrap}
  /* A LISTA DE JOGOS DENTRO DO CARTÃO — 02/09/2026, e ela NASCE VAZIA.
     Na máquina dela, hoje, os 63 jogos com o atalho estão todos em ordem e a
     lista não ocupa um pixel: `linhas_de_jogos([])` devolve string vazia, e o
     bloco fica com altura zero. Ela só aparece quando há o que dizer — que é a
     mesma regra do carimbo, e o motivo de o cartão não engordar por existir.
     Sem ela não haveria onde pôr o "tirar/voltar a usar" POR JOGO, e a lista
     `jogos_sem_wrapper.txt` continuaria sendo um arquivo que só se edita à mão. */
  .lanc-fora:not(:empty){margin-top:8px;border-top:1px solid var(--border-sutil);padding-top:7px;
                         display:flex;flex-direction:column;gap:5px}
  .lanc-jogo{display:flex;align-items:center;gap:8px;font-size:11px}
  .lanc-jogo-nome{color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .lanc-jogo-porque{color:var(--texto-mudo);margin-left:auto;white-space:nowrap}
  /* O `mini` é o ÚNICO botão menor da aba, e a razão é diferente da que fez o
     `.lanc .btn` ser removido: lá dois botões IGUAIS mediam diferente por
     acidente de CSS; aqui a linha de jogo é uma fileira densa, e um botão de
     34px por jogo empurraria a lista para fora do cartão. */
  .lanc-fora .btn.mini{height:24px;font-size:10.5px;padding:0 9px;flex:0 0 auto}
  .lanc-vazio{font-size:11px;color:var(--comment)}
  /* A LINHA DE INICIALIZAÇÃO À MOSTRA — 04/09/2026, decisão `07[01]` do PO.
     Ela NASCE AUSENTE: `desenho_dos_lancadores.linha_do_wrapper_html` devolve
     string vazia sempre que não há jogo com a linha intocável, e o bloco não
     ocupa um pixel — a mesma regra do carimbo e da lista de jogos.
     `word-break:break-all` E NÃO `pre`: são 143 caracteres sem um espaço onde
     caiba a quebra, e um `<pre>` empurraria barra de rolagem lateral para
     dentro de um cartão de meia largura. Aqui ela ocupa três linhas e o cartão
     continua no lugar.
     AS CORES SÃO AS DO ESQUELETO, e foram CONFERIDAS antes de escritas:
     `--elevated`, `--border-sutil` e `--texto-suave` existem no `:root` do
     `topo.html` (`:14`, `:15`, `:33`). O `--elevated` é o tom que sobe UM
     degrau sobre o `--app-bg` do cartão — é o que separa o bloco do corpo sem
     acrescentar cor nova à paleta.
     `user-select` NÃO É DECLARADO AQUI, e a razão foi medida: o `topo.html`
     não desliga a seleção em lugar nenhum (`grep user-select` devolve ZERO),
     então o padrão do WebKit já deixa o Ctrl+C funcionar — que é a SEGUNDA
     saída desta decisão. Declarar o que já vale seria regra que ninguém
     consegue provar. */
  .linha-do-wrapper{margin-top:7px;padding:6px 8px;border-radius:6px;
    background:var(--elevated);border:1px solid var(--border-sutil)}
  .linha-do-wrapper code{font-family:'JetBrains Mono',monospace;font-size:10px;
    line-height:1.5;color:var(--texto-suave);word-break:break-all}
  /* A TELA DE REGISTRO — 08/09/2026, o registro de lançador que ela pediu.
     A CAIXA, o topo, o corpo e o rodapé vêm do `monta.CSS_POPUP`, que é o dono
     da `.tela-nova` desde 29/08 e existe justamente para a segunda aba com
     pop-up não copiar as 49 linhas da primeira. O que é DESTA tela — e só
     dela — são as três regras abaixo, pela mesma razão que deixou a `.tn-vel`
     no `aba06.py`: CSS de uma tela só num arquivo comum é a mesma doença pelo
     avesso.
     A LINHA DE CIMA É A QUE RESPONDE «PARA QUAL?», e por isso ela é a única com
     endereço: quem abre a tela pelo botão de um cartão precisa ver de que
     cartão se trata antes de digitar. */
  .lanc-novo-para{font-size:11.5px;color:var(--texto-mudo);margin-bottom:12px}
  /* `flex-direction:column` e não uma linha: com o rótulo à esquerda os dois
     campos ficariam com larguras diferentes (os textos têm tamanhos
     diferentes), e dois campos de texto desalinhados numa caixa de 660px é o
     que faz a tela parecer montada por pessoas diferentes. */
  .lanc-novo-campo{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
  .lanc-novo-campo > span{font-size:11px;color:var(--texto-suave)}
  /* A ALTURA É A DO `--h-acao` do esqueleto, que é a dos botões do rodapé desta
     mesma caixa — um campo mais baixo que o botão que o guarda é a costura à
     vista. `font-family` monoespaçada porque o que se digita aqui é caminho e
     comando, e num `l` contra um `1` a diferença decide se o Hefesto acha. */
  .lanc-novo-campo input{height:var(--h-acao);border-radius:7px;padding:0 10px;
    background:var(--app-bg);border:1px solid var(--border-forte);color:var(--fg);
    font-family:'JetBrains Mono',monospace;font-size:11.5px}
  .lanc-novo-campo input:focus{outline:none;border-color:var(--purple)}
  /* O BOTÃO QUE É ÂNCORA TEM DE PARECER BOTÃO — 08/09/2026, e foi a FOTO que
     mostrou. Dois dos botões desta aba são `<a class="btn">` porque só uma
     âncora abre a `.tela-nova` pelo `:target` (ver `desenho_dos_lancadores.
     Acao.href`); o `.btn` do esqueleto não desliga o sublinhado, que é
     `text-decoration` padrão de `<a>`. Resultado medido na primeira foto: o
     botão global e o do cartão que não localizou saíam
     SUBLINHADOS ao lado de irmãos idênticos que não saíam — a mesma quebra de
     "mesma família, mesma largura" que fez o `.lanc .btn` cair em 02/09.
     O `.tn-rod .btn` do `monta.CSS_POPUP` já resolve isto DENTRO da pop-up, e
     pela mesma razão; esta regra é a mesma lição, na fileira da aba. */
  .acoes a.btn,.lanc a.btn{text-decoration:none;display:inline-flex;
    align-items:center;justify-content:center}
""" + CSS_POPUP

# OS CARTÕES SAEM DO DESENHO, e a lista deixou de ser digitada. Ela era seis
# dicionários com os selos e as contagens escritos à mão; agora é o que
# `dl.cartoes(None)` devolve — os mesmos seis cartões que o produto monta, no
# estado "ainda não li o disco".
#
# A CONTAGEM DO QUADRO CONTINUA DERIVADA, e agora de uma fonte que o produto
# também usa: `Quadro.achados` conta os cartões cujo selo AFIRMA algo (`ok` ou
# `warn`), e os cinco `NÃO SEI` ficam de fora pelo mesmo motivo pelo qual o
# `NÃO ACHEI` já ficava — em nenhum dos dois a aba pode dizer que o lançador
# está aqui.
QUADRO = dl.Quadro(lancadores=dl.cartoes(None))
CARTOES = dl.cartoes_html(QUADRO.lancadores)

MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">De onde os seus jogos vêm</span>
        <span class="ajuda">?<span class="dica">
          O Hefesto não é só para a Steam. Ele casa o perfil pelo <b>nome do processo</b> e pela
          <b>janela</b> — o jogo pode vir de onde quiser.<br><br>
          Esta aba procura os lançadores e emuladores instalados, diz <b>se os controles chegam
          lá</b>, o que impede quando não chegam, e conserta o que dá para consertar sozinho.<br><br>
          O que impede é do <b>lançador</b>, nunca do controle — é a linha de inicialização, a
          exceção do Steam Input, a permissão de aparelho. Por isso a resposta vale igual para
          <span data-campo="{dl.QUANTOS}" data-hef-alvo="html">{dl.quantos_html(N_CTRL, N_USB, N_BT)}</span>, e por isso a fita lá em cima está
          esmaecida aqui: não há o que escolher por controle.<br><br>
          <b>Detectar o jogo que está aberto</b> é o caminho curto: abra o jogo de onde for,
          volte aqui e clique — o perfil nasce com a regra certa, sem digitar nada.
        </span></span>
        <span class="conta" data-campo="lanc-conta" data-hef-alvo="html">{dl.conta_html(QUADRO.achados, QUADRO.impedidos)}</span>
      </div>
      <div class="quadro-corpo">

        <div class="acoes" style="margin-top:0;margin-bottom:12px">
          <button class="btn roxo" data-gesto="detectar">Detectar o jogo que está aberto</button>
          <button class="btn" data-gesto="procurar">Procurar de novo</button>
          <a class="btn" href="#{dl.TELA_DO_NOVO}" data-gesto="{dl.ADICIONAR}">{dl.ADICIONAR_NOVO_ROTULO}</a>
        </div>

        <div class="{dl.CLASSE_DA_GRADE}">
{CARTOES}
        </div>

      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>A aba mudou de assunto inteiro</h2>
  <ul>
    <li><b>A antiga era "Emulação" de <i>gamepad</i></b> (uinput) — termo técnico que ninguém entende. O conteúdo dela foi para os donos certos: diagnóstico e "Testar o controle virtual" para a <b>Sistema</b>, os combos para a <b>Navegação</b>, o microfone para a <b>Conexões</b>, modo e máscara para a <b>Jogar</b> e os <b>Perfis</b>.</li>
    <li><b>A nova é sobre de onde o jogo vem</b> — e existe para fechar uma lacuna medida: o produto tem <b>zero</b> menção a RetroArch, Dolphin ou mGBA no código, e o Orpheus depende de um emulador de GBC. Heroic e Lutris só aparecem em <b>comentário</b> (<code>hotkey.py:56</code>, <code>lifecycle.py:2271</code> — era <code>:2250</code>, e a linha andou).</li>
    <li><b>A interface diz "Steam" 689 vezes</b> para um motor que já casa por <code>process_name</code> e <code>window_class</code>. É aqui que o jogo de fora da Steam ganha porta de entrada.</li>
  </ul>

  <h2>02/09/2026 — a aba saiu do desenho, e três números dela caíram</h2>
  <ul>
    <li><b>Nenhuma caixa andou.</b> A grade, o CSS, os textos de ajuda e o lugar de cada botão são os que ela aprovou (<i>"lançadores perfeito parabéns"</i>). O que mudou é <b>de onde vem o que está escrito dentro deles</b>.</li>
    <li><b>Os cartões deixaram de contar controle.</b> Eles diziam <i>"Os N controles chegam"</i>, com o N saindo da <code>MESA</code>. A aba responde por <b>lançador</b>, e isto já estava medido no próprio arquivo: nenhuma função de <code>prontuario_dos_jogos.py</code> recebe controle, MAC, device ou transporte — os cinco impedimentos (<code>:139-143</code>) e as duas curas (<code>:878</code>) são fatos do <b>jogo em disco</b>. Contar controle aqui era responder com um número que a pergunta não tem. A régua do gerador virou o inverso: ela reprova se um cartão voltar a prometer para um número.</li>
    <li><b>Os números do cartão da Steam eram digitados, e o produto contradiz os quatro.</b> Medido na máquina dela em 02/09 com <code>censo_do_wrapper</code> e <code>prontuario_dos_jogos</code>: <i>412 jogos</i> → <b>23 instalados</b>; <i>3 jogos já sabem por onde entrar</i> → <b>0 pontes confirmadas</b>; <i>5 encontrados · 1 com impedimento</i> → <b>1 lançador medível</b>; e o <i>Heroic · 28 jogos · NÃO CHEGAM</i> era afirmação sobre um lançador que o produto <b>nunca olhou</b>.</li>
    <li><b>Nasceu o selo <code>NÃO SEI</code>, e ele é a cura disso.</b> Heroic, Lutris, Flatpak, RetroArch e Dolphin·mGBA passam a dizer que o produto ainda não sabe olhá-los — <code>CHEGAM</code> e <code>NÃO CHEGAM</code> seriam as duas afirmações que ele não pode fazer. Há régua que reprova no dia em que um deles ganhar fonte e continuar com o <code>NÃO SEI</code>.</li>
    <li><b>O cartão da Steam ganhou a lista dos jogos que perderam o atalho</b>, com o nome de cada um e o botão de tirar/devolver. Ela <b>nasce vazia</b> e não ocupa um pixel quando não há o que dizer — a mesma regra do carimbo.</li>
    <li><b>A contagem do quadro continua derivada</b> — hoje <b>{QUADRO.achados}</b> —, e agora dos mesmos cartões que o produto monta.</li>
  </ul>

  <h2>08/09/2026 — o que ela decidiu olhando a aba</h2>
  <ul>
    <li><b>O selo diz <code>NÃO LOCALIZADO</code></b>, e não mais <code>NÃO ACHEI</code> — palavra dela. O valor mudou num lugar só (<code>desenho_dos_lancadores.SELOS</code>); as dezenas de menções em comentário ficaram, porque contam o que aconteceu num dia. E as réguas que digitavam a palavra passaram a <b>ler</b> o selo.</li>
    <li><b>Todo cartão que não localizou oferece <code>{dl.ADICIONAR_ROTULO}</code></b> — os seis, a Steam inclusive. Ele não instala nada: ele abre a tela onde <b>você diz onde o lançador está</b>, que é o que faz o cartão acender. No cartão que <i>achou</i>, o botão continua sendo <code>Abrir o lançador</code>: são dois estados, dois botões.</li>
    <li><b>E há um botão para acrescentar o que o Hefesto não conhece</b> — <code>{dl.ADICIONAR_NOVO_ROTULO}</code>, pedido dela <i>"pra devs mais experimentais"</i>. Ele é o outro ato, e por isso a outra palavra: <i>localizar</i> é para o cartão que já está na tela, <i>adicionar novo</i> é para o que não tem cartão nenhum. O que você declara mora no <code>maquina.json</code> e passa pelo <b>mesmo procurador</b> dos de fábrica; o que não está no disco <b>não é guardado</b>, e o recado diz o que foi procurado. O que se acrescenta se tira, pelo <code>{dl.REMOVER_ROTULO}</code>.</li>
    <li><b>A Epic e a GOG ficam dentro do Heroic</b> — palavra dela, e o rótulo daquele cartão já dizia <code>Heroic (Epic · GOG)</code> desde que ele nasceu. É por ali que o jogo das duas lojas entra nesta máquina.</li>
  </ul>

  <h2>O que estava no código e nunca teve tela — agora tem</h2>
  <ul>
    <li><b>"Ver o que impede"</b> — <code>prontuario_dos_jogos.levantar_censo</code> nomeia cinco impedimentos e <b>não tinha chamador em <code>src/</code></b>. O botão é o chamador. Ele leva <b>13,4 s</b> (examina o executável de cada jogo), por isso é gesto e não pintura.</li>
    <li><b>"Consertar"</b> — <code>sentinela_do_wrapper.reparar_ou_adiar</code>, com os portões dele intactos: jogo aberto antes de tudo, Steam aberta depois, e só então a escrita. A recusa vai para a tela com a frase que <b>nomeia o jogo</b>.</li>
    <li><b>"Não usar neste jogo" / "Voltar a usar"</b> — o <code>jogos_sem_wrapper.txt</code> existia e <b>nenhuma tela o escrevia</b>: a única forma de tirar um jogo era editar o arquivo à mão.</li>
    <li><b>"Detectar o jogo que está aberto"</b> — <code>steam_game_running_appid</code>, a mesma fonte do lembrete do wrapper. Ele diz <b>qual</b> jogo e se ele abre pelo atalho; <b>criar o perfil continua sendo da aba Perfis</b>.</li>
  </ul>

  <h2>Ainda aberto</h2>
  <ul>
    <li><b>Os cinco botões de Steam da Sistema vêm para cá?</b> <b>RESPONDIDA — ficam na Sistema</b> (D-A-ABA-LANCADORES-NASCE-PLACEHOLDER). Não reabrir.</li>
    <li><b>"Abrir o lançador" LIGOU</b> — decisão dela, 03/09/2026. O cartão da Steam chama <code>steam_launch_options.reopen_steam</code>, que existia desde 23/08 com os dois caminhos (o binário <code>steam</code> e o <code>steam://open/main</code> de quem a instalou por Flatpak ou Snap) e <b>zero chamadores vindos da interface</b>. Nos outros cinco o botão <b>recusa dizendo</b>: o produto sabe ONDE eles estão e não sabe abri-los — não há função que abra o Heroic, o Lutris, o RetroArch ou os emuladores, e o Flatpak não é aplicativo. O gesto está em <code>hefesto_vivo.PERIGOSOS</code>, para que a prova automática nunca abra a Steam na tela dela.</li>
    <li><b>"Criar perfil para um jogo" continua sem endereço</b>, e é decisão: criar perfil é da aba Perfis — dois caminhos para o mesmo disco é como duas telas passam a discordar.</li>
    <li><b>Quem mede Heroic, Lutris e os emuladores?</b> Ninguém, ainda. É varredura nova, não é ligar o que existe — e por isso os cinco cartões dizem <code>NÃO SEI</code> em vez de escolher um selo.</li>
  </ul>
</div>

</body>
</html>
'''

# ---------------------------------------------------------------------------
# A RÉGUA DA PROMESSA — 31/08/2026, REFEITA em 02/09/2026.
#
# O QUE ELA COBRAVA: que o "Os N controles chegam" dos cartões batesse com a
# `MESA`. Ela nasceu de um defeito real — com dois lugares vazios, cinco cartões
# prometiam a QUATRO controles.
#
# O QUE MUDOU, e é por isso que ela mudou de forma: **os cartões deixaram de
# contar controle.** O próprio arquivo já tinha medido a razão, no comentário do
# topo: nenhuma função de `prontuario_dos_jogos` recebe controle, MAC, device ou
# transporte — os cinco impedimentos são fatos do JOGO EM DISCO. Contar
# controles nesta aba era responder com um número que a pergunta não tem, e foi
# exatamente esse número que a régua velha existia para corrigir.
#
# A régua nova cobra o que sobrou, e cobra dos dois lados:
#   1. NENHUM cartão promete um número de controles (a recaída da velha);
#   2. os seis cartões existem, e cada um tem os quatro endereços que o pacote
#      pinta — um cartão sem endereço fica com o desenho para sempre, e é
#      invisível na tela.
#
# ELA LÊ O MIOLO, e não as variáveis que o escreveram: comparar o produto com
# ele mesmo é como uma régua irmã, na aba Conexões, passou por uma mordida.
# ---------------------------------------------------------------------------
_PROMESSAS = re.findall(r"[Oo]s (\d+) controles chegam", MIOLO)
if _PROMESSAS:
    raise SystemExit(
        f"ERRO: {len(_PROMESSAS)} cartão(ões) voltaram a prometer para um NÚMERO "
        f"de controles {sorted(_PROMESSAS)}. Esta aba responde por LANÇADOR: "
        "nenhum dos cinco impedimentos de `prontuario_dos_jogos` recebe "
        "controle, MAC, device ou transporte. Um número aqui é uma promessa que "
        "o produto não tem como conferir.")

# A CONTA SUBIU PARA SETE E VOLTOU PARA SEIS no mesmo dia — 08/09/2026. A Epic
# ganhou cartão a pedido dela e o perdeu por decisão dela; a razão inteira está
# em `desenho_dos_lancadores.SEM_FONTE`, e o que sobra aqui é a conta.
#
# ELA CONTINUA CRAVADA, e o número cravado é o ponto: esta régua lê a página
# ESTÁTICA, que é o desenho de referência. Um cartão que apareça ou suma daqui
# sem alguém mexer neste número é um cartão que ninguém decidiu — e o desenho
# desta aba é dela. O que ela NÃO conta são os declarados: aqueles só existem na
# máquina de quem os declarou, e chegam pela troca da grade inteira
# (`a07_lancadores._pintura`), nunca pelo HTML publicado.
_ESPERADOS = [x.chave for x in QUADRO.lancadores]
if len(_ESPERADOS) != 6:
    raise SystemExit(f"ERRO: {len(_ESPERADOS)} cartões, e o desenho dela tem "
                     "SEIS. Se um lançador ganhou fonte, ele sai do `SEM_FONTE` "
                     "e entra com cartão próprio — a conta continua fechando.")
_FALTAM = [f"{k}{s}" for k in _ESPERADOS for s in dl.SUFIXOS
           if f'data-campo="{k}{s}"' not in MIOLO]
if _FALTAM:
    raise SystemExit(
        f"ERRO: {len(_FALTAM)} endereço(s) que o pacote pinta não existem no "
        f"miolo: {_FALTAM}. Um valor escrito num endereço que a página não tem "
        "é pintura perdida — `querySelector` devolve `null`, a pintura conta "
        "zero, e zero passa por 'nada mudou'.")

# ---------------------------------------------------------------------------
# O ENDEREÇO NÃO DEPENDE DO ESTADO — 07/09/2026.
#
# ESTA ABA NÃO TEM LUGAR VAZIO, e por isso esta régua não é a das irmãs. Nas
# abas 01-06 e 08 o cartão é POR CONTROLE, e o defeito medido hoje com os
# quatro DualSense dela na mesa foi esse: o lugar vazio saía por um ramo
# separado, SEM `data-campo` nenhum, e o dado dos dois controles que chegaram
# depois não tinha onde pousar — a tela mostrava dois de quatro. Aqui o cartão
# é por LANÇADOR (`data-lancador`, seis), não por controle: `grep data-controle`
# neste gerador e na página publicada dá ZERO, e a razão está no comentário do
# topo — nenhuma função de `prontuario_dos_jogos` recebe controle.
#
# MAS O DEFEITO TEM O MESMO EIXO, e ele existe aqui: *um cartão num estado
# carrega endereço que o mesmo cartão noutro estado não tem.* Lá o eixo é
# conectado/vazio; aqui é o `selo` — `ok`, `warn`, `off`, `nao_sei`.
#
# E A RÉGUA DE CIMA NÃO ALCANÇA ISSO, medido: o `_FALTAM` lê o `MIOLO`, e o
# `MIOLO` sai de `cartoes(None)`, que é o estado de PARTIDA — os seis cartões
# nascem `nao_sei`, e a página publicada tem `class="lanc ausente"` SEIS vezes
# e nenhuma outra. Um ramo que largasse um endereço no estado `ok` passaria
# verde por aqui e quebraria exatamente na máquina dela, que é onde os
# lançadores são ACHADOS. A régua que só vê um estado mede um instante.
#
# O CONTRATO: os quatro `SUFIXOS` estão em todo cartão em TODO estado, e o
# quinto (`-fora`, só onde há lista) não pode variar com o `selo` — ele
# responde a `tem_lista`, que é fato do lançador, não do estado.
# ---------------------------------------------------------------------------
_ESTADOS = tuple(dl.MOLDURA)
_POR_ESTADO: dict[str, dict[str, set[str]]] = {}
for _lanc in QUADRO.lancadores:
    _POR_ESTADO[_lanc.chave] = {
        _selo: set(re.findall(
            r'data-campo="([^"]+)"',
            dl.um_cartao(dataclasses.replace(_lanc, selo=_selo))))
        for _selo in _ESTADOS
    }

_INSTAVEIS = [
    f"{_k}: {_selo} tem {sorted(_c)} e {_ESTADOS[0]} tem {sorted(_ref)}"
    for _k, _mapa in _POR_ESTADO.items()
    for _ref in [_mapa[_ESTADOS[0]]]
    for _selo, _c in _mapa.items() if _c != _ref
]
if _INSTAVEIS:
    raise SystemExit(
        f"ERRO: {len(_INSTAVEIS)} cartão(ões) mudam de ENDEREÇO conforme o "
        f"estado: {_INSTAVEIS}. O `selo` decide a classe e o TEXTO, nunca o "
        "conjunto de `data-campo` — um endereço que só existe num estado é "
        "pintura perdida no outro, que é o defeito medido nas abas por "
        "controle em 07/09/2026.")

_SEM_OBRIGATORIOS = [
    f"{_k} ({_selo}): falta {sorted(set(_k + _s for _s in dl.SUFIXOS) - _c)}"
    for _k, _mapa in _POR_ESTADO.items()
    for _selo, _c in _mapa.items()
    if not set(_k + _s for _s in dl.SUFIXOS) <= _c
]
if _SEM_OBRIGATORIOS:
    raise SystemExit(
        f"ERRO: {len(_SEM_OBRIGATORIOS)} cartão(ões) sem os {len(dl.SUFIXOS)} "
        f"endereços que o pacote pinta: {_SEM_OBRIGATORIOS}. Os seis cartões "
        "carregam o MESMO conjunto — o que muda entre eles é o texto.")

# ---------------------------------------------------------------------------
# O GERADOR SÓ ESCREVE QUANDO ALGUÉM O RODA — 06/09/2026.
#
# ATÉ HOJE ELE ESCREVIA NO IMPORT. Tudo daqui para baixo corria no NÍVEL DO
# MÓDULO, e `import aba07` bastava para reescrever `mockup/07-lancadores.html`
# no disco — a bancada DELA, o arquivo que ela abre para olhar o desenho.
# Medido na costura desta leva com a irmã `aba05`: bastou o `pytest` COLETAR
# um teste que a importava no topo para o mockup mudar em disco, com o estado
# vivo da mesa dentro. Oito dos dez geradores estavam assim; `aba01.py` e
# `aba02.py` já tinham a guarda, e é a forma delas que está aqui.
#
# A MORDIDA é `test_a_palavra_do_transporte_tem_um_dono_so.py::
# test_o_gerador_nao_escreve_a_bancada_como_efeito_de_import`, que importa o
# módulo e cobra que o arquivo não tenha mudado.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    n = monta("07-lancadores", "Lançadores", MIOLO, CSS, legenda=LEGENDA)

    # ---------------------------------------------------------------------------
    # A FITA NÃO NOMEIA UM CONTROLE QUE NÃO ESTÁ NA MESA — 03/09/2026
    #
    # A LEI, e ela é dela:
    #
    #     "se no topo tá mostrando controle white player 1, então cada aba vai usar
    #     os controles lá de cima. Não mistura com a info dos mockups."
    #
    # O QUE ESTAVA NA TELA, medido nesta máquina com os dois controles dela na mesa
    # (foto em `docs/process/`), na `07-lancadores`:
    #
    #     cabeçalho   2 controles: 1 USB · 1 BT      ← certo, lido do aparelho
    #     fita        P1 · Cosmic Red · USB          ← o MOCKUP; ela não tem esse
    #                 P2 · Starlight Blue · BT       ← o MOCKUP
    #
    # `monta()` injeta a fita com `fita(inerte=True)` e SEM `mesa`, e nesse caminho
    # ela cai nos `CONECTADOS` do desenho. Os seis valores que a
    # `scripts/check_identidade_vem_de_cima.py --bancada --aba 07` acusava eram
    # esses dois chips inteiros: dois `--plastico`, dois nomes de colorway no texto
    # e dois no `title`.
    #
    # POR QUE OS CHIPS SAEM DAQUI EM VEZ DE GANHAREM ENDEREÇO: a página estática não
    # sabe NADA dos controles dela, e a regra é a dela — *campo sem informação não
    # mostra nada*. Um `data-campo` no chip do desenho zeraria a régua e deixaria a
    # tela dizendo a mesma coisa errada até o produto chegar; e o produto pode nem
    # chegar a este endereço, porque `hefesto_vivo.pintar` troca `.fita` INTEIRA
    # (`p.fita`) antes de visitar campo nenhum — quando essa troca acontece, todo
    # `data-campo` que estivesse dentro da fita deixa de existir no DOM.
    #
    # QUEM ESCREVE OS CHIPS, e sem ele isto seria maquiagem: o pacote da aba,
    # `pacotes/a07_lancadores.fita_html()`, emitido em `blocos[".fita"]`. O
    # `blocos` corre DEPOIS do `p.fita` e reconsulta o documento pela classe, então
    # ele acerta o alvo com ou sem a troca do bloco inteiro.
    #
    # O QUE FICA: o `Selecionar:` e o chip `Todos`, que são ESTRUTURA — não nomeiam
    # aparelho nenhum e o `Todos` é o alvo desta aba (fora de `monta.ABAS_QUE_ESCOLHEM`).
    # ---------------------------------------------------------------------------
    # O CHIP É `<label>` DESDE 05/09/2026 (`monta.fita`), para poder clicar nas
    # três abas que escolhem controle. Nesta, que não escolhe, ele nasce sem
    # `data-gesto` e sai daqui inteiro — mas a ÂNCORA tinha de acompanhar: com
    # `<span>` ela deixaria de casar e este bloco ficaria verde sem apagar nada.
    # ---------------------------------------------------------------------------
    # A TELA DE REGISTRO ENTRA IRMÃ DA JANELA, FORA DO MIOLO — 08/09/2026.
    #
    # É a mesma injeção que o `aba06.py` faz com as quatro pop-ups dele, e a
    # razão é a mesma: a `.tela-nova` é `position:fixed` e não pertence ao
    # `.miolo` que as réguas varrem. Pôr o bloco dentro do `MIOLO` faria a régua
    # de estados contar dois campos de texto vazios como conteúdo da aba.
    #
    # A MARCA É CONFERIDA ANTES, e a recusa é dura: um `replace` que não casa
    # não levanta — ele devolve o texto igual, e a página sairia SEM a tela com
    # o gerador imprimindo sucesso. É o silêncio que esta casa já nomeou.
    # ---------------------------------------------------------------------------
    _MARCA = "<!-- ================= LEGENDA DO MOCKUP ================= -->"
    _PAG = onde.pagina("07-lancadores.html")
    _DOC = _PAG.read_text()
    if _MARCA not in _DOC:
        raise SystemExit(
            "ERRO: a marca da legenda mudou no `fim.html` e a tela de registro "
            f"não tem onde entrar. Sem ela os botões «{dl.ADICIONAR_ROTULO}» e "
            f"«{dl.ADICIONAR_NOVO_ROTULO}» abrem NADA — o "
            f"`href=\"#{dl.TELA_DO_NOVO}\"` aponta para um `id` que não existe, "
            "e o clique some sem uma palavra.")
    _DOC = _DOC.replace(
        _MARCA, dl.tela_do_registro_html().strip() + "\n\n" + _MARCA, 1)
    onde.gravar("07-lancadores.html", _DOC)

    _CHIP_DE_CONTROLE = re.compile(r'^[ \t]*<label class="chip plastico"[^\n]*\n', re.M)
    _DOC = onde.pagina("07-lancadores.html").read_text()
    _CONGELADOS = _CHIP_DE_CONTROLE.findall(_DOC)
    if not _CONGELADOS:
        raise SystemExit(
            "ERRO: não achei um único `<label class=\"chip plastico\">` na página "
            "recém-gerada. Ou `monta.fita()` mudou de forma, ou a fita saiu vazia — "
            "e nos dois casos esta troca ficaria VERDE sem fazer nada, que é como a "
            "fita viva morreu calada em 27/08.")
    onde.gravar("07-lancadores.html", _CHIP_DE_CONTROLE.sub("", _DOC))

    # ---------------------------------------------------------------------------
    # A RÉGUA DA IDENTIDADE roda sobre o HTML JÁ GRAVADO, que é a última coisa que a
    # página é. Ler o `MIOLO` deixaria de fora justamente a fita, que vem do
    # esqueleto e é onde o defeito morava.
    #
    # A REGRA MORA EM `identidade_congelada`, lá em cima, com as cinco formas e a
    # razão de cada uma. Aqui só se aplica — e a mesma função responde ao
    # `--conferir`, que é por onde o teste a morde.
    # ---------------------------------------------------------------------------
    _CRAVADAS = identidade_congelada(onde.pagina("07-lancadores.html").read_text())
    if _CRAVADAS:
        raise SystemExit("ERRO: " + "\nERRO: ".join(_CRAVADAS))

    _MODELOS = sorted({(ln.get("id") or "").strip() for ln in _mapa_das_cores()} - {""})

    print(f"07-lancadores: OK, {n} divs · mesa {N_CTRL} ({N_USB} USB/{N_BT} BT) · "
          f"{QUADRO.achados} encontrados, {QUADRO.impedidos} com impedimento · "
          f"{len(_ESPERADOS) * len(dl.SUFIXOS)} endereços em {len(_ESPERADOS)} cartões · "
          f"{len(_CONGELADOS)} chip(s) do desenho fora da fita, "
          f"0 dos {len(_MODELOS)} modelos do mapa cravados na página")
