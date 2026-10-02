import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import csv
import dataclasses
import re

import onde
from monta import CONECTADOS, CSS_POPUP, cor_da_zona, monta

import desenho_dos_lancadores as dl

# colorway no texto e (2) o `--plastico:` cravado.
#      `border-color:`. Sem nome e sem `--plastico:`, ele passa pelas duas —
_PROSA = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)

#: for um `id` do mapa — `--plastico:#fff` cai fora daqui e é acusado à parte.
_TABELA_DO_ESQUELETO = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})")

_COM_COLORWAY = re.compile(r"<[a-zA-Z][^>]*\bdata-colorway\s*=[^>]*>")


def _mapa_das_cores() -> list[dict[str, str]]:
    """As 233 linhas de `docs/data/cores-do-dualsense.csv`: 28 modelos, 10 zonas."""
    linhas = [ln for ln in (onde.RAIZ / "docs/data/cores-do-dualsense.csv")
              .read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    return list(csv.DictReader(linhas))


def identidade_congelada(doc: str) -> list[str]:
    """As cores de APARELHO cravadas nesta página, uma frase por achado."""
    mapa = _mapa_das_cores()
    nomes = sorted({(ln.get("nome") or "").strip() for ln in mapa} - {""})
    apelidos = sorted({(ln.get("id") or "").strip() for ln in mapa} - {""})
    tons = sorted({(ln.get("hex") or "").strip().lower() for ln in mapa} - {""})

    limpo = _PROSA.sub(lambda m: "".join(c if c == "\n" else " " for c in m.group(0)), doc)
    achados: list[str] = []

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

    achados += [f"nome de colorway na página: {nome!r}. A identidade do controle "
                f"vem da FITA, que lê do APARELHO — um nome de modelo escrito "
                f"aqui é o desenho mandando na tela do produto."
                for nome in nomes if len(nome) >= 4 and nome in limpo]

    if re.search(r"--plastico\s*:", limpo):
        achados.append(
            "voltou um `--plastico:` cravado à página. A cor do plástico é "
            "leitura de aparelho — quem a escreve é o pacote, nunca o gerador.")

    for apelido in apelidos:
        agulha = rf"(?<![A-Za-z0-9_-]){re.escape(apelido)}(?![A-Za-z0-9_-])"
        achados += [f"apelido de modelo do mapa na página: {apelido!r}. É o que "
                    f"vai num `data-colorway` ou numa classe, e a régua por NOME "
                    f"não o enxerga — nenhum 'Cosmic Red' aparece num "
                    f"`data-colorway=\"cosmic-red\"`."
                    for m in re.finditer(agulha, limpo) if _fora_da_tabela(m.start())]

    achados += [f"a página usa `var(--{apelido})`. Aquelas cinco são a paleta do "
                f"DESENHO, congelada no esqueleto: elas respondem por 5 dos 28 "
                f"modelos do mapa, e quem tiver o sexto vê a cor de outro "
                f"aparelho. A cor do controle DELA vem do pacote, no tique."
                for apelido in apelidos if f"var(--{apelido})" in limpo]

    for tom in tons:
        achados += [f"hexadecimal do mapa cravado na página: {tom}. Ele não tem "
                    f"nome nem `--plastico:` e por isso atravessa as duas réguas "
                    f"que já havia — e é a cor de um modelo que pode não ser o "
                    f"dela."
                    for m in re.finditer(re.escape(tom), limpo, re.I)
                    if _fora_da_tabela(m.start())]

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


N_CTRL = len(CONECTADOS)
N_USB = sum(1 for c in CONECTADOS if c["via"] == "USB")
N_BT = sum(1 for c in CONECTADOS if c["via"] == "BT")

CHEGAM = f"Os {N_CTRL} controles chegam."

CSS = """
  /* ---------- Lançadores ---------- */
  /* A GRADE ROLA POR DENTRO, E O `.miolo` PARA DE ROLAR — ROLAGEM-01, 09/09/2026.
     Achado dela em 08/09: *"duas paginas ficaram com barra de navegação  (noqa-acento: citação dela)
     vertical. tipo a gatilhos e lançadores."*

     A CAUSA, MEDIDA NO WEBKIT VIVO com os quatro na mesa e o daemon dela:
     `DIV.miolo 668>564`. O `.miolo` tem 564px de caixa; o conteúdo desta aba
     pediu **668**. Não é a `.janela`, que fecha em 775/775 nas dez — é o filho.

     E O CONTEÚDO NÃO TEM TETO, que é o que decide o desenho. Medido duas vezes
     na MESMA sessão, com meia hora de intervalo: `.lancadores` foi de **493 a
     534px** sozinha, porque o cartão da Steam saiu de «CHEGAM» para «NÃO
     CHEGAM» com um jogo pendente — e a lista de pendências (`.lanc-fora`) tem o
     tamanho que os jogos DELA tiverem. Some-se «Adicionar novo Lançador», que
     cria cartão. *Quantos lançadores ela tem, e quantos jogos com pendência, é
     dela — e a caixa não pode crescer com eles.*

     É a mesma frase que declara o `DIV.rolo` da `10-perfis` em `POR_DESENHO`
     (`scripts/ensaios/a_janela_cabe_no_que_ela_ve.py`), e por isso a cura é a
     mesma: o `.quadro` vira `estica`, a GRADE ganha a barra, e o que fica
     pregado acima dela é o que ela precisa ler sem rolar — o título, a conta
     («N localizados · N com impedimentos») e os três botões. Hoje o inverso
     acontecia: a página inteira rolava e a conta saía de vista.

     O QUE FOI MEDIDO E NÃO SERVIU — três hipóteses derrubadas na bancada, para
     ninguém as repetir:
       * **três colunas** em vez de duas: `.miolo` foi de 627 para **669**. A
         coluna estreita faz a prosa quebrar em mais linhas do que a fileira que
         se economiza;
       * **o caminho do lançador numa linha só** (`.lanc-diz code` com
         reticências): **668**, pior — `display:inline-block` joga o `<code>`
         para uma linha de caixa própria;
       * **espremer** (prosa cortada em 2 linhas, botões à direita da prosa,
         a fileira de botões subindo para o título): o melhor par chegou a
         **592**, ainda 28px acima — e ainda assim quebraria no dia seguinte,
         porque o teto não existe.

     `align-content:start` é o que impede a grade de esticar as fileiras quando
     sobra espaço: sem ele, com poucos cartões, cada um viraria um retângulo
     alto e vazio — o defeito que o `.quadro.estica` já teve em 27/08. */
  /* `minmax(0,1fr)` E NÃO `1fr` — a coluna da direita saía PELA BORDA, e a foto
     de 09/09 mostra que ela já saía antes desta sprint. `1fr` é
     `minmax(auto,1fr)`, e o mínimo `auto` de uma coluna de grade é o
     **min-content** do que há dentro. Dentro há o caminho do lançador num
     `<code>`, e um caminho não tem espaço onde quebrar:
     `/home/…/flatpak/exports/share/applications/net.lutris.Lutris.desktop`
     mede ~470px de min-content, a coluna se recusa a encolher, e as duas somam
     mais do que a caixa — o cartão da direita ficava cortado ao meio, sem borda
     e com a prosa decepada.
     `minmax(0,…)` deixa a coluna encolher, e o `overflow-wrap:anywhere` do
     `<code>` dá ao caminho onde quebrar. As duas juntas: sem a segunda, o
     caminho vazaria do cartão em vez de vazar da grade. */
  .lancadores{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;
              flex:1;min-height:0;overflow-y:auto;scrollbar-gutter:stable;
              align-content:start}
  .lanc-diz code{overflow-wrap:anywhere}
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
  /* O VERDE DO «LOCALIZADO» — 11/09/2026, LANCADOR-LOCALIZAR-01, e ele nasceu
     de uma queixa dela: *"não aparece verde os localizados"*.

     MEDIDO NA PÁGINA VIVA antes da cura, com a grade pintada como o pacote a
     pinta (`blocos` -> `cartoes_html`): o selo da Steam saía
     `background: rgb(80,250,123)` e os CINCO `LOCALIZADO` saíam
     `background: rgba(0,0,0,0)` — transparente. Não era um verde fraco: era
     verde NENHUM. A pílula não existia, e o selo caía como texto branco solto
     ao lado do nome do cartão.

     A CAUSA É DE 09/09: `SELOS` ganhou a chave `localizado` no Python
     (LANCADORES-ZERO-01 §5.2) e `MOLDURA` ganhou o `chega` junto — mas a FOLHA
     nunca soube da classe nova. O gerador emitia
     `<span class="lanc-selo localizado">`, e nenhuma regra casava: sobrava só
     a `.lanc-selo` base, que dá tamanho e fonte e não dá cor.

     ELE DIVIDE O ESTILO COM `ok`, e é a mesma decisão que `off`/`nao_sei` já
     tinham tomado do outro lado: as duas dizem *"este está aqui e não há
     impedimento a agir"* — é a razão escrita em `MOLDURA`, que já dá a mesma
     moldura `chega` aos dois. Um quinto tom só acrescentaria uma cor para ela
     decodificar; quem separa CHEGAM de LOCALIZADO é a PALAVRA, que é o que o
     selo existe para dizer.

     E ESTE VERDE É ESTADO, NÃO RESPOSTA A GESTO. A piscada de deu-certo tem
     outro dono (`hef-deu-certo`) e não passa por aqui: este cartão está verde
     desde que a página pinta, e continua verde sem ninguém clicar em nada. */
  .lanc-selo.ok,.lanc-selo.localizado{background:var(--green);color:var(--app-bg)}
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
  /* AS DUAS PORTAS DO «ONDE ELE ESTÁ» — 10/09/2026, decisão dela (a opção C):
     o campo que ela digita e o botão que abre o seletor do sistema. A linha é
     `flex` e o campo é quem estica (`flex:1`), porque o rótulo do botão tem
     tamanho FIXO e o caminho não tem: dividir a largura ao meio deixaria o
     campo curto para um `/home/…/.local/share/flatpak/exports/…` e o botão com
     folga que ele não usa.
     O `white-space:nowrap` no botão é o que impede a reticência de cair sozinha
     na segunda linha quando a caixa encolhe — o `.tn-cx` do `CSS_POPUP` já tem
     largura máxima, e um botão de duas linhas ficaria mais alto que o campo ao
     lado, que é a costura à vista que a regra do `--h-acao` acima evita.
     E O `text-decoration:none` ENTRA AQUI porque o `CSS_POPUP` só o desliga em
     `.tn-rod .btn` — o rodapé da caixa. Este botão é do CORPO, e sem esta linha
     ele sairia SUBLINHADO ao lado do «Adicionar» que não sai: a mesma quebra
     que a foto de 08/09 mostrou na fileira dos cartões, duas regras abaixo. */
  .lanc-novo-linha{display:flex;gap:8px;align-items:center}
  .lanc-novo-linha input{flex:1;min-width:0}
  .lanc-novo-linha a.btn{white-space:nowrap;flex:none;text-decoration:none;
    display:inline-flex;align-items:center;justify-content:center}
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
""" + CSS_POPUP + dl.CSS_DA_EXCLUSAO

QUADRO = dl.Quadro(lancadores=dl.cartoes(None))
CARTOES = dl.cartoes_html(QUADRO.lancadores)

MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo">De onde os seus jogos vêm</span>
        <span class="ajuda">?<span class="dica">
          Esta aba procura os lançadores instalados nesta máquina. O perfil casa pelo
          <b>nome do processo</b> e pela <b>janela</b> — o jogo pode vir de qualquer um deles.<br><br>
          O que impede um jogo de receber o controle é do <b>lançador</b>, nunca do controle.<br><br>
          <b>Detectar o jogo aberto</b> é o caminho curto: abra o jogo, volte aqui e clique.
        </span></span>
        <span class="conta" data-campo="lanc-conta" data-hef-alvo="html">{dl.conta_html(QUADRO.achados, QUADRO.impedidos)}</span>
      </div>
      <div class="quadro-corpo">

        <div class="acoes" style="margin-top:0;margin-bottom:12px">
          <button class="btn roxo" data-gesto="detectar">Detectar o jogo aberto</button>
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
    <li><b>A antiga era "Emulação" de <i>gamepad</i></b> (<code>uinput</code>) — termo técnico que ninguém entende. O conteúdo dela foi para os donos certos: diagnóstico e "Testar o controle virtual" para a <b>Sistema</b>, os combos para a <b>Navegação</b>, o microfone para a <b>Conexões</b>, modo e máscara para a <b>Jogar</b> e os <b>Perfis</b>.</li>
    <li><b>A nova é sobre de onde o jogo vem</b> — e existe para fechar uma lacuna medida: o produto tem <b>zero</b> menção a RetroArch, Dolphin ou mGBA no código, e o Orpheus depende de um emulador de GBC. Heroic e Lutris só aparecem em <b>comentário</b> (<code>hotkey.py:37</code>, <code>lifecycle.py:1407</code> — era <code>:2250</code>, e a linha andou).</li>
    <li><b>A interface diz "Steam" 689 vezes</b> para um motor que já casa por <code>process_name</code> e <code>window_class</code>. É aqui que o jogo de fora da Steam ganha porta de entrada.</li>
  </ul>

  <h2>02/09/2026 — a aba saiu do desenho, e três números dela caíram</h2>
  <ul>
    <li><b>Nenhuma caixa andou.</b> A grade, o CSS, os textos de ajuda e o lugar de cada botão são os que ela aprovou (<i>"lançadores perfeito parabéns"</i>). O que mudou é <b>de onde vem o que está escrito dentro deles</b>.</li>
    <li><b>Os cartões deixaram de contar controle.</b> Eles diziam <i>"Os N controles chegam"</i>, com o N saindo da <code>MESA</code>. A aba responde por <b>lançador</b>, e isto já estava medido no próprio arquivo: nenhuma função de <code>prontuario_dos_jogos.py</code> recebe controle, <code>MAC</code>, device ou transporte — os cinco impedimentos (<code>:139-143</code>) e as duas curas (<code>:878</code>) são fatos do <b>jogo em disco</b>. Contar controle aqui era responder com um número que a pergunta não tem. A régua do gerador virou o inverso: ela reprova se um cartão voltar a prometer para um número.</li>
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
    <li><b>"Criar perfil" LIGOU</b> — 21/09/2026 (OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01). Ele abre a escolha do jogo daquele lançador, e o perfil nasce pelo <b>gravador da aba Perfis</b> (<code>a10_perfis.criar_para_o_jogo</code>): um gravador, dois caminhos de chegada — a razão de antes, cumprida em vez de contornada.</li>
    <li><b>A lista de exclusão</b> — 21/09/2026. O jogo escolhido vê o controle como se o Hefesto não estivesse instalado, e o pé do cartão só aparece quando há jogo na lista. Os quatro botões dos cartões localizados cabem numa linha — palavra dela.</li>
    <li><b>Quem mede Heroic, Lutris e os emuladores?</b> Ninguém, ainda. É varredura nova, não é ligar o que existe — e por isso os cinco cartões dizem <code>NÃO SEI</code> em vez de escolher um selo.</li>
  </ul>
</div>

</body>
</html>
'''

_PROMESSAS = re.findall(r"[Oo]s (\d+) controles chegam", MIOLO)
if _PROMESSAS:
    raise SystemExit(
        f"ERRO: {len(_PROMESSAS)} cartão(ões) voltaram a prometer para um NÚMERO "
        f"de controles {sorted(_PROMESSAS)}. Esta aba responde por LANÇADOR: "
        "nenhum dos cinco impedimentos de `prontuario_dos_jogos` recebe "
        "controle, MAC, device ou transporte. Um número aqui é uma promessa que "
        "o produto não tem como conferir.")

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

# quatro DualSense dela na mesa foi esse: o lugar vazio saía por um ramo
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

if __name__ == "__main__":
    import os
    import pathlib
    import shutil
    import tempfile

    _real = onde.saida()
    _prova = pathlib.Path(tempfile.mkdtemp(prefix="hefesto-prova-07-"))
    for _vizinha in _real.glob("*.html"):
        shutil.copy2(_vizinha, _prova / _vizinha.name)
    os.environ[onde._DESVIO] = str(_prova)
    n = monta("07-lancadores", "Lançadores", MIOLO, CSS, legenda=LEGENDA)

    # esses dois chips inteiros: dois `--plastico`, dois nomes de colorway no texto
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
        _MARCA, dl.tela_do_registro_html().strip() + "\n\n"
        + dl.tela_da_escolha_html().strip() + "\n\n" + _MARCA, 1)
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

    _CRAVADAS = identidade_congelada(onde.pagina("07-lancadores.html").read_text())
    if _CRAVADAS:
        raise SystemExit("ERRO: " + "\nERRO: ".join(_CRAVADAS))

    _MODELOS = sorted({(ln.get("id") or "").strip() for ln in _mapa_das_cores()} - {""})

    print(f"07-lancadores: OK, {n} divs · mesa {N_CTRL} ({N_USB} USB/{N_BT} BT) · "
          f"{QUADRO.achados} encontrados, {QUADRO.impedidos} com impedimento · "
          f"{len(_ESPERADOS) * len(dl.SUFIXOS)} endereços em {len(_ESPERADOS)} cartões · "
          f"{len(_CONGELADOS)} chip(s) do desenho fora da fita, "
          f"0 dos {len(_MODELOS)} modelos do mapa cravados na página")
    shutil.copyfile(_prova / "07-lancadores.html", _real / "07-lancadores.html")
    shutil.rmtree(_prova)
