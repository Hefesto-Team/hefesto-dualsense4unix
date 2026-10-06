#!/usr/bin/env python3
"""A QUINTA PERGUNTA — até onde a prova de cada feature da tela CHEGOU."""
from __future__ import annotations

import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from check_cabo_bt_perfil_controle import (
    DO_APARELHO,
    gestos_da_tela,
    tabela as quatro_respostas,
)
from check_paridade_transporte import (
    DEGRAU_POR_VALOR,
    DIRECAO_POR_CANAL,
    ESCADA,
    GRAU_JOGO_RECEBEU,
    GRAU_JOGO_REAGIU,
    VALORES_DA_ESCADA,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]
MAPA = RAIZ / "docs/data/mapa-controles.csv"

#: `não` em quase tudo. A tela é dos quatro DualSense (decisão de 06/09).
_O_APARELHO_DELA = "dualsense"

SEM_REGISTRO = "—"

NAO_SE_APLICA = "n/a"

_ORDEM = (SEM_REGISTRO, *VALORES_DA_ESCADA)

_FIM_DA_DIRECAO: dict[str, str] = {
    degrau.direcao: degrau.valor for degrau in ESCADA
}

CUSTOS = {
    "horas": "conserto de horas — o caminho existe e falta acionar ou registrar",
    "médio": "bancada com ela, ou um campo a criar depois da medição",
    "grande": "bloqueio de transporte, ou um degrau que ninguém sabe fechar",
}

A_PROVA_QUE_FALTA: dict[str, tuple[str, str, str]] = {
    "mira": (
        "médio",
        "2026-09-06-MESA-DE-QUATRO-01-quatro-dualsense-por-cabo-e-por-radio-com-ela.md",
        "a Mira Virtual lê o giro, e `movimento.giroscopio@dualsense` está em MONTOU "
        "nos dois transportes. A matriz da A-MIRA-POR-MOVIMENTO-NA-TELA-02 (24/09) "
        "provou o analógico direito saindo dos dois controles virtuais (uhid e "
        "uinput), no USB e no BT, do P1 ao P4, com o fd real; falta o jogo aberto "
        "virar a câmera com o controle na mão dela, e a sensibilidade e o eixo "
        "(yaw ou roll) que só a mão decide. É da MESA-DE-QUATRO-01",
    ),
    "inclinacao": (
        "médio",
        "2026-09-27-NO-MODO-XBOX-TUDO-FUNCIONA-01.md",
        "a Inclinação lê o acelerômetro, e `movimento.acelerometro@dualsense` está em "
        "MONTOU nos dois transportes. A régua da E12b leva o clique ao perfil no disco e "
        "de volta à tela com o Daemon de verdade, P1 a P4, no USB e no BT; falta o jogo "
        "aberto andar com o controle inclinado na mão dela, que é a prova da sprint",
    ),
    "toque": (
        "médio",
        "2026-09-27-NO-MODO-XBOX-TUDO-FUNCIONA-01.md",
        "o «Cursor | Botões» lê o touchpad, e `toque.touchpad.cursor` e "
        "`toque.touchpad.dedos` estão em MONTOU nos dois transportes. A régua da E12b "
        "grava e relê o arranjo por controle; falta o dedo dela mover o cursor e "
        "apertar o direcional, o L1 e o L2 num jogo aberto, que é a prova da sprint",
    ),
    "haptica": (
        "médio",
        "2026-09-29-O-GANHO-DA-HAPTICA-TEM-DONO-01.md",
        "o ganho de 0 a 200% por controle chega aos traseiros da placa daquele "
        "controle no cabo e ao conversor da ponte antes do int8 no rádio, com as "
        "réguas da sprint mordendo nos dois transportes; falta o passo 0 da sprint "
        "(o tremor pelo nível) e a mão dela nos Caminhos da Forja a 100, 150 e 200",
    ),
    "ganho-mic": (
        "médio",
        "2026-09-20-O-GANHO-DO-MIC-TEM-DONO-01.md",
        "`audio.microfone.ganho@dualsense` está em MONTOU no cabo e o rádio "
        "não se aplica (não há placa ALSA onde o elemento exista — é o "
        "aparelho, não dívida). O caminho de escrita existe desde 20/09 e a "
        "suíte o sustenta; o que falta é o ARRASTO com a orelha dela, que é o "
        "único jeito de o degrau `O APARELHO OBEDECEU` deixar de ser "
        "inferência. **A leitura já foi medida** e é o que sustenta o MONTOU: "
        "o `scontents` do que está no cabo responde `[100%] [48.00dB]`. É da "
        "O-GANHO-DO-MIC-TEM-DONO-01",
    ),
    "mascara": (
        "grande",
        "2026-09-08-SENSORES-NO-JOGO-01-o-giroscopio-e-o-acelerometro-provados-ate-o-jogo.md",
        "o destino da máscara é o JOGO, não o plástico: quem lê `057E:2009` é "
        "quem abre o vpad. `plataforma.vpad@dualsense` está em MONTOU nos dois "
        "transportes, com `de_onde_sei = inferido-do-codigo` e `provado_por` "
        "vazio — o report é montado e ninguém viu um jogo abrir o nó. É a "
        "cicatriz de 04/09 (a máscara que nunca gravou um byte) no degrau "
        "seguinte. O degrau que vem primeiro — `O JOGO RECEBEU` — espera o "
        "instrumento que a SENSORES-NO-JOGO-01 precisa escrever para o degrau "
        "3 dela; o destino, um andar acima, só a mão dela fecha",
    ),
    "sensor": (
        "grande",
        "2026-09-06-MESA-DE-QUATRO-01-quatro-dualsense-por-cabo-e-por-radio-com-ela.md",
        "`movimento.giroscopio@dualsense` está em MONTOU nos dois. Medido em 13/09: o zero "
        "em Modo Virtual era da libSDL2 2.30.0 do sistema; nas bibliotecas dos runtimes da "
        "Steam o vpad expõe os dois sensores, e o SDL pareia o nó «Motion Sensors» pelo "
        "`uniq` (SENSORES-NO-JOGO-02, §1). Falta o jogo aberto receber e reagir, e é da "
        "MESA-DE-QUATRO-01; o touchpad explica por que o destino é o degrau de CIMA: lá o "
        "repasse está íntegro e o jogo não reage, sem causa desde 16/08",
    ),
    "brilho-luzes": (
        "médio",
        "2026-09-24-O-BRILHO-DAS-LUZES-DE-NUMERO-01.md",
        "`luz.led_jogador.brilho@dualsense` está em MONTOU nos dois: a régua pergunta "
        "ao report montado pelo bit do degrau (o `flag2` bit0 e o `common[42]`), no "
        "USB com e sem o nó do kernel e no BT, do P1 ao P4. O que falta é o olho dela "
        "nas lâmpadas nos três degraus, nas células `mapa-luz.led_jogador.brilho-cabo` "
        "e `-radio` da bancada (25/09); ninguém viu ainda qual degrau o firmware "
        "acende ao ligar",
    ),
    "mudo": (
        "horas",
        "2026-09-06-MESA-DE-QUATRO-01-quatro-dualsense-por-cabo-e-por-radio-com-ela.md",
        "`audio.microfone.mudo@dualsense` está em MONTOU nos dois, e no rádio "
        "o `aciona` é `parcial`. O negativo do mudo por rádio JÁ foi medido em "
        "07/09 (`mic-radio-negativo-do-mudo-0907`) e a célula não subiu: o que "
        "falta é o registro do degrau, não o comportamento. É a linha 20 do "
        "roteiro da mesa",
    ),
    "custo-mic": (
        "horas",
        "2026-09-06-MESA-DE-QUATRO-01-quatro-dualsense-por-cabo-e-por-radio-com-ela.md",
        "é o MESMO ato do `mudo` da aba 02 — o gesto dela, chamado pela linha do "
        "controle na seção do rádio —, e para na mesma célula "
        "`audio.microfone.mudo@dualsense` (MONTOU nos dois). O que falta é o "
        "registro do degrau, e é a linha 20 do roteiro da mesa, como a do `mudo`",
    ),
    "volume": (
        "horas",
        "2026-09-09-MIC-VOLUME-02-o-byte-do-aparelho-medido-e-ligado-ao-campo.md",
        "o gesto tem dois donos e responde pelo pior: `audio.alto_falante."
        "volume` está em MONTOU nos dois, e `audio.microfone.volume` diz `não` "
        "nos dois. O trilho MEXE hoje — na fonte do PipeWire —, e o que não é "
        "escrito é o byte do aparelho (output 0x02, `common[6]`). A bancada "
        "decide, e a regra é a das sprints de byte: byte que o aparelho não "
        "obedece não ganha campo",
    ),
    "volume-padrao": (
        "médio",
        "2026-10-03-O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01.md",
        "o «Padrão» do alto-falante escreve o volume nominal pelo mesmo caminho do "
        "trilho (`audio.alto_falante.volume`, MONTOU nos dois transportes): falta a "
        "orelha dela na bancada da 1.5, de P1 a P4, no cabo e no rádio",
    ),
    "rota": (
        "grande",
        "2026-08-31-A-BANCADA-QUE-O-RADIO-PEDE-INDICE.md",
        "`audio.alto_falante.rota@dualsense` OBEDECEU no cabo (16/08, com a "
        "orelha dela) e está em MONTOU no rádio. O bloqueio é de transporte e "
        "tem endereço: o kernel só escreve `audio_control` quando "
        "`plugged_state` muda, e `plugged_state` só é escrito no ramo USB "
        "(`hid-playstation.c:1647-1661`). É o ensaio 13 do índice do rádio",
    ),
}

_DONA_NA_RAZAO = re.compile(r"[Éé] da ([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{2})\b")


def dona_que_a_razao_nomeia(razao: str) -> str | None:
    """A sprint que a razão diz ser dona do resto («é da X»), ou ``None``."""
    achado = _DONA_NA_RAZAO.search(razao)
    return achado.group(1) if achado else None


def a_dona_e_a_sprint(dona: str, sprint: str) -> bool:
    """O arquivo da dona é o da sprint: ``AAAA-MM-DD-<SPRINT>-…md``."""
    forma = rf"\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(sprint)}(?:-|\.md$)"
    return re.match(forma, dona) is not None

CELULAS_QUE_CHEGARAM_AO_JOGO = 0


def _linhas_do_mapa() -> dict[str, list[dict[str, str]]]:
    with MAPA.open(newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    fora: dict[str, list[dict[str, str]]] = {}
    for linha in linhas:
        fora.setdefault(linha.get("chave", ""), []).append(linha)
    return fora


def _degrau(linha: dict[str, str], lado: str) -> str:
    """O degrau declarado por aquele lado, ou :data:`SEM_REGISTRO`."""
    valor = (linha.get(f"{lado}_ate_onde_foi") or "").strip()
    if not valor:
        return SEM_REGISTRO
    if valor not in DEGRAU_POR_VALOR:
        raise SystemExit(
            f"ERRO: `{linha.get('chave')}` declara `{lado}_ate_onde_foi = "
            f"{valor!r}`, que não é degrau da escada. O domínio desta coluna "
            f"é do `check_paridade_transporte`; rode-o antes."
        )
    return valor


def _pior(degraus: list[str]) -> str:
    return min(degraus, key=_ORDEM.index) if degraus else SEM_REGISTRO


def _nada_a_acionar(linha: dict[str, str], lado: str) -> bool:
    """Este lado tem alguma coisa a provar? `True` = não tem, e não conta.

    **NÃO SE COBRA PROVA DE UM TRANSPORTE EM QUE A FEATURE NÃO EXISTE.** A
    regra nasceu em 20/09/2026, com o `ganho-mic` — o primeiro gesto de tela
    que é **só cabo por APARELHO**, e não por dívida nossa: pelo rádio o
    microfone do DualSense chega como som já digitalizado, por nó da nossa
    ponte, e não há placa ALSA onde o elemento de ganho exista. A tela não
    esconde isso: o trilho fica cinza com a razão ao lado.

    Sem esta linha, :func:`ate_onde_foi` respondia pelo PIOR incluindo um lado
    vazio que nunca vai deixar de ser vazio — e a feature caía para
    `SEM_REGISTRO` com o cabo já em `O APARELHO OBEDECEU`. A saída seria
    declará-la em :data:`A_PROVA_QUE_FALTA` para sempre, e a lista das faltas
    **deixaria de ser uma fila**: uma entrada que nunca sai é propaganda ao
    contrário.

    **A CONDIÇÃO É DUPLA DE PROPÓSITO**, e é o que a impede de virar uma porta
    dos fundos: não basta `aciona = não`. A causa tem de ser `nada-a-acionar`,
    que no vocabulário do mapa quer dizer *não há o que mexer deste lado* — e
    NÃO `divida` (falta trabalho nosso), nem `nao-medido` (falta medição), nem
    `o-aparelho-recusa` (há o que mexer, e ele recusou). Essas três continuam
    derrubando o degrau, que é o trabalho desta régua.
    """
    aciona = (linha.get(f"{lado}_aciona") or "").strip().lower()
    causa = (linha.get(f"{lado}_por_que_nao_aciona") or "").strip().lower()
    sem_acento = "n" + "ao"  # noqa-acento: é VALOR de coluna, não texto de tela
    return aciona in ("não", sem_acento) and causa == "nada-a-acionar"


def ate_onde_foi(chaves: tuple[str, ...],
                 mapa: dict[str, list[dict[str, str]]]) -> tuple[str, str]:
    """`(cabo, rádio)` — o degrau de um gesto, pela PIOR das chaves dele."""
    fora = []
    for lado in ("cabo", "radio"):
        degraus = []
        for chave in chaves:
            minhas = [linha for linha in mapa.get(chave, [])
                      if linha.get("controle") == _O_APARELHO_DELA]
            vivas = [linha for linha in minhas
                     if not _nada_a_acionar(linha, lado)]
            degraus.extend(_degrau(linha, lado) for linha in vivas)
            if not minhas:
                degraus.append(SEM_REGISTRO)
        fora.append(NAO_SE_APLICA if minhas and not degraus
                    else _pior(degraus))
    return fora[0], fora[1]


def _canais(chaves: tuple[str, ...],
            mapa: dict[str, list[dict[str, str]]]) -> list[tuple[str, str]]:
    """`(id da célula, canal)` de cada lado de cada chave do gesto."""
    fora: list[tuple[str, str]] = []
    for chave in chaves:
        minhas = [linha for linha in mapa.get(chave, [])
                  if linha.get("controle") == _O_APARELHO_DELA]
        if not minhas:
            raise SystemExit(
                f"ERRO: `{chave}@{_O_APARELHO_DELA}` não tem linha no mapa, e "
                "sem ela não há canal — logo não há como saber até onde a "
                "prova desta feature TEM de chegar. Escreva a linha no "
                "`docs/data/mapa-controles.csv` ou tire a chave do "
                "`DO_APARELHO`."
            )
        for linha in minhas:
            for lado in ("cabo", "radio"):
                fora.append(
                    (f"{linha.get('id') or chave} ({lado})",
                     (linha.get(f"{lado}_canal") or "").strip())
                )
    return fora


def destino_de(chaves: tuple[str, ...],
               mapa: dict[str, list[dict[str, str]]]) -> str:
    """Até onde a prova daquela feature TEM de chegar — perguntado ao MAPA."""
    destinos = []
    for onde, canal in _canais(chaves, mapa):
        if not canal:
            raise SystemExit(
                f"ERRO: `{onde}` não diz o `canal`, e o canal é o que decide "
                "onde a escada desta feature termina. Escreva-o no mapa; o "
                "domínio da coluna é do `check_paridade_transporte`."
            )
        direcao = DIRECAO_POR_CANAL.get(canal)
        if direcao is None:
            raise SystemExit(
                f"ERRO: `{onde}` declara `canal = {canal!r}`, que não tem "
                "direção declarada em `check_paridade_transporte."
                "DIRECAO_POR_CANAL`. Um canal que não diz por onde o dado anda "
                "não decide destino nenhum — declare a direção dele lá, no "
                "mesmo gesto em que o valor entrar no domínio."
            )
        destinos.append(_FIM_DA_DIRECAO[direcao])
    return max(destinos, key=_ORDEM.index)


def chegou(degrau: str, destino: str) -> bool:
    """A prova alcançou o destino daquela feature?"""
    return degrau == NAO_SE_APLICA or _ORDEM.index(degrau) >= _ORDEM.index(destino)


def celulas_no_jogo(mapa: dict[str, list[dict[str, str]]]) -> list[str]:
    """As células do mapa INTEIRO que declaram um degrau de entrada."""
    fora = []
    for chave, linhas in mapa.items():
        for linha in linhas:
            for lado in ("cabo", "radio"):
                if _degrau(linha, lado) in (GRAU_JOGO_RECEBEU, GRAU_JOGO_REAGIU):
                    fora.append(f"{chave}@{linha.get('controle')} ({lado})")
    return sorted(fora)


def inventario() -> list[tuple[str, str, str, str, str, bool]]:
    """`(gesto, abas, cabo, rádio, destino, chegou)` para as features da tela."""
    mapa = _linhas_do_mapa()
    fora = []
    for gesto, abas in sorted(gestos_da_tela().items()):
        chaves = DO_APARELHO.get(gesto)
        if chaves is None:
            continue
        cabo, radio = ate_onde_foi(chaves, mapa)
        destino = destino_de(chaves, mapa)
        alcancou = chegou(cabo, destino) and chegou(radio, destino)
        fora.append((gesto, ",".join(abas), cabo, radio, destino, alcancou))
    return fora


def _imprimir_o_inventario(linhas: list[tuple[str, str, str, str, str, bool]]) -> None:
    """A LISTA «o que NÃO funciona», com as CINCO colunas — e não seis réguas."""
    quatro = {linha[0]: linha for linha in quatro_respostas()}
    print(f"{'gesto':12} {'aba':4} | {'cabo':12} {'rádio':12} {'perfil':15} "
          f"{'ctrl':8} | {'prova cabo':19} {'prova rádio':19} {'chegou':6} "
          f"{'custo':6}")
    print("-" * 128)
    for gesto, abas, cabo, radio, _destino, alcancou in linhas:
        _g, _a, q_cabo, q_radio, q_perfil, q_ctrl, _falta = quatro.get(
            gesto, ("", "", "?", "?", "?", "?", ""))
        custo = A_PROVA_QUE_FALTA.get(gesto, ("—", "", ""))[0]
        print(f"{gesto:12} {abas:4} | {q_cabo:12} {q_radio:12} {q_perfil:15} "
              f"{q_ctrl:8} | {cabo:19} {radio:19} "
              f"{'sim' if alcancou else 'NÃO':6} {custo:6}")
    print()
    print("as quatro primeiras colunas são do `check_cabo_bt_perfil_controle` "
          "(«o Hefesto MEXE nisso?»); as duas da prova são desta régua «até "
          "onde a prova chegou?». Elas NÃO se substituem.")
    print()


def main() -> int:
    linhas = inventario()
    mapa = _linhas_do_mapa()
    conhecidos = {linha[0] for linha in linhas}

    if "--tabela" in sys.argv:
        _imprimir_o_inventario(linhas)

    orfas = sorted(set(A_PROVA_QUE_FALTA) - conhecidos)
    if orfas:
        print(f"VERMELHO: {len(orfas)} falta(s) declarada(s) para gesto que a "
              f"tela já não oferece como feature de aparelho:")
        for gesto in orfas:
            print(f"  {gesto} — tire a linha de `A_PROVA_QUE_FALTA`")
        return 1

    ruins = []
    for gesto, (custo, dona, razao) in sorted(A_PROVA_QUE_FALTA.items()):
        if custo not in CUSTOS:
            ruins.append(f"  {gesto}: custo {custo!r} fora do vocabulário "
                         f"({', '.join(CUSTOS)})")
        nomeada = dona_que_a_razao_nomeia(razao)
        if nomeada is not None and not a_dona_e_a_sprint(dona, nomeada):
            ruins.append(f"  {gesto}: a razão diz que o resto é da {nomeada}, "
                         f"e a dona é `{dona}`")
    if ruins:
        print(f"VERMELHO: {len(ruins)} declaração(ões) sem custo válido, sem "
              f"dona no disco ou com dona que a razão não nomeia:")
        print("\n".join(ruins))
        return 1

    paradas = {linha[0]: linha for linha in linhas if not linha[5]}
    novas = {g: l for g, l in paradas.items() if g not in A_PROVA_QUE_FALTA}
    if novas:
        print(f"VERMELHO: {len(novas)} feature(s) da tela cuja prova parou "
              f"antes do destino, e nenhuma delas está declarada:")
        for gesto, (_g, abas, cabo, radio, destino, _ok) in sorted(novas.items()):
            print(f"  [{abas}] {gesto}: cabo {cabo} · rádio {radio} · "
                  f"o destino é {destino}")
        print()
        print("A tela oferecer já é o selo forte — ela não confessa dívida "
              "nossa (ordem dela de 07/09). Então a falta mora aqui, com "
              "CUSTO e DONA, ou a prova sobe o degrau no mapa.")
        return 1

    chegaram = [g for g in A_PROVA_QUE_FALTA if g not in paradas]
    if chegaram:
        print(f"VERMELHO: {len(chegaram)} falta(s) declarada(s) cuja prova já "
              f"chegou ao destino — a declaração ficou velha:")
        for gesto in sorted(chegaram):
            _custo, dona, _razao = A_PROVA_QUE_FALTA[gesto]
            print(f"  {gesto}: tire a linha de `A_PROVA_QUE_FALTA` e feche a "
                  f"{dona}")
        return 1

    no_jogo = celulas_no_jogo(mapa)
    if len(no_jogo) != CELULAS_QUE_CHEGARAM_AO_JOGO:
        print(f"VERMELHO: o mapa tem {len(no_jogo)} célula(s) no degrau de "
              f"entrada e esta régua guarda {CELULAS_QUE_CHEGARAM_AO_JOGO}:")
        for celula in no_jogo:
            print(f"  {celula}")
        print()
        print("Se subiu, é notícia: escreva o número novo em "
              "`CELULAS_QUE_CHEGARAM_AO_JOGO` e diga na entrega qual ensaio "
              "fechou o degrau. Régua com folga acumulada dá verde sobre o "
              "defeito seguinte.")
        return 1

    print(f"VERDE: {len(linhas)} feature(s) de aparelho na tela · "
          f"{len(linhas) - len(paradas)} com a prova no destino · "
          f"{len(paradas)} com a prova parada e declarada · "
          f"{len(no_jogo)} célula(s) do mapa no degrau do JOGO")
    print()
    print("O QUE FALTA, POR CUSTO — e os custos NÃO se somam: duas horas de "
          "trabalho e um bloqueio de transporte não são a mesma falta.")
    for custo, oque in CUSTOS.items():
        desta = sorted(g for g in paradas if A_PROVA_QUE_FALTA[g][0] == custo)
        if not desta:
            continue
        print(f"  {custo} ({oque}): {len(desta)}")
        for gesto in desta:
            _custo, dona, razao = A_PROVA_QUE_FALTA[gesto]
            _g, abas, cabo, radio, destino, _ok = paradas[gesto]
            print(f"    [{abas}] {gesto}: cabo {cabo} · rádio {radio} · "
                  f"destino {destino}")
            print(f"      {razao}")
            print(f"      dona: {dona}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
