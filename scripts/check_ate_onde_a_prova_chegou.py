#!/usr/bin/env python3
"""A QUINTA PERGUNTA — até onde a prova de cada feature da tela CHEGOU.

**A cobrança dela, 08/09/2026:**

    "mas aí me quebra. pq o programa de dias a fio é de brinquedo? uma prova de
     conceito? por favor. ele tem que funcionar em tudo. tudo realmente. é essa
     a ideia."

E a resposta que ela recebeu era imprecisa: uma frase só somava faltas de
custos diferentes — duas horas de trabalho e um bloqueio de transporte ditos
como se fossem a mesma coisa. **Esta régua existe para que essa frase nunca
mais precise ser dita de cabeça** (TUDO-FUNCIONA-01).

POR QUE ELA NÃO É A SEXTA CÓPIA DA MESMA PERGUNTA
--------------------------------------------------

As QUATRO perguntas dela — cabo? BT? no perfil? por controle? — já têm dono:
:mod:`check_cabo_bt_perfil_controle` (CABO-BT-PERFIL-CONTROLE-01). Elas leem
`*_aciona` do mapa, que responde **"o Hefesto MEXE nisso?"**.

A QUINTA é outra pergunta, e nenhuma régua desta casa a fazia: **até onde a
PROVA chegou?** É a coluna `*_ate_onde_foi`, a escada de
:data:`check_paridade_transporte.ESCADA` — e o critério do primeiro degrau diz,
com estas palavras, o preço de confundir as duas:

    MONTOU — o byte existe na memória do produto e a suíte o lê. Nada saiu do
    processo. *Tratar MONTOU como `funciona` é a mentira mais cara desta casa.*

O mapa já cruzava as duas réguas **linha a linha**
(`check_paridade_transporte`, 14 regras). O que ninguém cruzava é a TELA com a
escada: *isto aqui a tela oferece — até onde foi provado que funciona?*

E é por isso que a dívida tem de morar aqui: **a tela não confessa dívida
nossa** (ordem dela de 07/09/2026, com portão em
`scripts/check_a_tela_nao_confessa.py`). Se a tela não pode dizer, e o oferecer
já é o selo forte, então alguma coisa tem de cobrar que a falta esteja escrita
com CUSTO e com DONA — senão o selo é desenho fingindo ser produto.

O QUE ESTA RÉGUA LÊ, E O QUE ELA NÃO DIGITA
--------------------------------------------

=====================  =====================================================
a lista de features    :func:`check_cabo_bt_perfil_controle.gestos_da_tela` e
                       o `DO_APARELHO` de lá — **um dono só** para "quais são
                       as features e qual linha do mapa responde por elas"
o vocabulário da       :data:`check_paridade_transporte.ESCADA` — **um dono
escada                 só** para os cinco degraus e a direção de cada um
até onde foi           `docs/data/mapa-controles.csv`, `cabo_ate_onde_foi` e
                       `radio_ate_onde_foi`, da linha do `dualsense`
o DESTINO de cada      `docs/data/mapa-controles.csv`, `cabo_canal` e
feature                `radio_canal`, pela
                       :data:`check_paridade_transporte.DIRECAO_POR_CANAL`
=====================  =====================================================

O que se ESCREVE é a falta: custo, dona e razão. *A lista se lê, a razão se
escreve* — a mesma disciplina do `_NAO_E_PROMESSA` do `casa-sabe`.

O DESTINO NÃO SE ESCREVE, E A LIÇÃO É DE 09/09/2026
----------------------------------------------------

Esta régua nasceu com o destino de cada feature guardado DENTRO da própria
`A_PROVA_QUE_FALTA` — a mesma tabela em que se declara a falta. Quem declarava
a falta escolhia junto a linha de chegada dela, e o preço estava impresso na
saída: arrancar a declaração do `sensor` fazia a régua responder *"o destino é
O APARELHO OBEDECEU"* para uma feature cuja prova só termina no jogo. **A trava
era medida contra a própria saída** — a mesma família do defeito que a casa
nomeou em 07/09, quando a régua do CSV comparava o arquivo novo com ele mesmo e
passou enquanto o mapa perdia 50 colunas.

A cura é de endereço, não de texto: o destino vem do **mapa** — a coluna
`*_canal` da linha —, traduzido pela direção que o dono da `ESCADA` declara. Um
canal que anda para o aparelho (`hidraw`, `sysfs`, `dbus`, `alsa-pipewire`)
termina em `O APARELHO OBEDECEU`; um que anda para o jogo (`evdev`, `uhid`)
termina em `O JOGO REAGIU`. Mexer nesta régua não move mais a linha de chegada
de coisa alguma; mexer no mapa move — e é para mover mesmo.

    scripts/check_ate_onde_a_prova_chegou.py            # reprova o que falta
    scripts/check_ate_onde_a_prova_chegou.py --tabela   # o inventário honesto
"""
from __future__ import annotations

import csv
import pathlib
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
SPRINTS = RAIZ / "docs/process/sprints"

#: O CONTROLE DESTA CASA — a mesma escolha do portão irmão, e pela mesma razão:
#: o mapa tem uma linha por (chave, controle), e as do `pro` e do `sn30` dizem
#: `não` em quase tudo. A tela é dos quatro DualSense (decisão dela de 06/09).
_O_APARELHO_DELA = "dualsense"

#: SEM DEGRAU REGISTRADO. Não é um degrau da escada: é a ausência dela, e ela
#: fica ABAIXO de `MONTOU` de propósito — uma célula vazia não afirma nada, e
#: lê-la como "montou" seria inventar o degrau mais barato.
SEM_REGISTRO = "—"

#: A ORDEM, do pior para o melhor. Derivada de `ESCADA`, nunca redigitada: o
#: dia em que a escada ganhar um sexto degrau, esta régua o herda.
_ORDEM = (SEM_REGISTRO, *VALORES_DA_ESCADA)

#: O FIM DE CADA DIREÇÃO — o último degrau que a `ESCADA` declara para ela.
#: DERIVADO, e a derivação é o ponto: a `ESCADA` está em ordem, então o último
#: de cada direção ganha. Hoje dá `saída → O APARELHO OBEDECEU` e
#: `entrada → O JOGO REAGIU`; no dia em que a escada ganhar um sexto degrau,
#: o destino o herda sem ninguém redigitar nada aqui.
#:
#: **POR QUE O FIM, e não a entrada da direção:** `O JOGO RECEBEU` diz que o
#: processo do jogo abriu o nó — não que o jogo fez alguma coisa com o que
#: recebeu. Parar ali é o mesmo erro que a escada nomeia no primeiro degrau,
#: um andar acima: *tratar MONTOU como «funciona» é a mentira mais cara desta
#: casa*. O touchpad é o precedente — o repasse íntegro e o jogo sem reagir,
#: sem causa desde 16/08/2026.
_FIM_DA_DIRECAO: dict[str, str] = {
    degrau.direcao: degrau.valor for degrau in ESCADA
}

#: O VOCABULÁRIO DO CUSTO, e ele é fechado de propósito.
#:
#: **A regra que esta sprint deixa:** *nunca some faltas de custos diferentes
#: numa frase só.* Duas horas de trabalho e um bloqueio de transporte não são
#: "não funciona" — e dizer que são faz dias de trabalho parecerem uma prova de
#: conceito. Por isso o relatório imprime AGRUPADO por custo e **nunca soma**.
CUSTOS = {
    "horas": "conserto de horas — o caminho existe e falta acionar ou registrar",
    "médio": "bancada com ela, ou um campo a criar depois da medição",
    "grande": "bloqueio de transporte, ou um degrau que ninguém sabe fechar",
}

#: A PROVA QUE FALTA — a feature da tela cuja prova parou antes do destino,
#: com o CUSTO, a DONA e a razão. **E MAIS NADA.**
#:
#: O DESTINO NÃO MORA AQUI, e a ausência é a cura de 09/09/2026. Enquanto ele
#: morava, esta tabela decidia as duas metades da mesma conta — a falta e a
#: linha de chegada contra a qual ela é medida —, e apagar uma linha daqui
#: MUDAVA o destino da feature que ela descrevia. Quem responde onde a escada
#: de cada feature termina é o MAPA, por :func:`destino_de`; escrever um degrau
#: nesta tabela não muda a opinião da régua sobre coisa nenhuma.
#:
#: **MORDE NOS DOIS SENTIDOS**, como a `A_DIVIDA_CONHECIDA` da irmã:
#:
#: * falta NOVA (a prova parou e ninguém declarou) reprova;
#: * falta que CHEGOU (declarada aqui e a escada já alcança o destino) reprova
#:   também, pedindo que a linha saia. Sem isso a lista vira propaganda no dia
#:   seguinte à primeira cura.
A_PROVA_QUE_FALTA: dict[str, tuple[str, str, str]] = {
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
        "2026-09-08-SENSORES-NO-JOGO-01-o-giroscopio-e-o-acelerometro-provados-ate-o-jogo.md",
        "`movimento.giroscopio@dualsense` está em MONTOU nos dois, e o degrau "
        "que decide é o terceiro: em Virtual o jogo abre o vpad por evdev e a "
        "hipótese mais forte é que NÃO recebe giroscópio, apesar de os bytes "
        "certos viajarem no report HID. O touchpad é o precedente no mesmo "
        "caminho, e é ele que explica por que o destino é o degrau de CIMA: "
        "lá o repasse está íntegro e o jogo não reage, sem causa desde 16/08",
    ),
    "mic-modo": (
        "médio",
        "2026-09-08-MIC-OS-QUATRO-01-os-quatro-microfones-funcionando.md",
        "`audio.microfone@dualsense` está em SAIU NO FIO nos dois: o canal "
        "abriu, e o degrau de obedecer não foi registrado. No rádio a voz SAI "
        "com a ponte de pé — medido 07/09, um controle de cada vez "
        "(`mic-radio-a-voz-sai-0907`) —, e é justamente o «um de cada vez» que "
        "falta: quatro fontes com nome estável, uma por controle",
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
    "rota": (
        "grande",
        "2026-08-31-A-BANCADA-QUE-O-RADIO-PEDE-INDICE.md",
        "`audio.alto_falante.rota@dualsense` OBEDECEU no cabo (16/08, com a "
        "orelha dela) e está em MONTOU no rádio. O bloqueio é de transporte e "
        "tem endereço: o kernel só escreve `audio_control` quando "
        "`plugged_state` muda, e `plugged_state` só é escrito no ramo USB "
        "(`hid-playstation.c:1647-1661`). É o ensaio 13 do índice do rádio",
    ),
    # `player` e `auto-cores` SAÍRAM DAQUI EM 09/09/2026, e quem as tirou foi
    # ELA. As duas paravam na mesma célula — `luz.led_jogador.escrita_hefesto@
    # dualsense`, escada VAZIA nos dois transportes —, e a pergunta que sobrava
    # era de procedência, não de comportamento: ela VÊ as lâmpadas acenderem, e
    # ninguém tinha registrado o degrau. A resposta dela foi «Sobe com o meu
    # olho», com os quatro na mesa (dois cabo, dois rádio). A célula subiu a
    # `O APARELHO OBEDECEU` nos dois lados com `provado_por = olho-dela`, os
    # ensaios `led-jogador-escrita-hefesto-obedece-{cabo,radio}-0909` entraram
    # no caderno, e a régua cobrou a saída destas duas linhas na mesma corrida —
    # que é a mordida 2 fazendo o trabalho dela.
}

#: QUANTAS CÉLULAS DO MAPA INTEIRO JÁ CHEGARAM AO JOGO — medido em 09/09/2026,
#: nas 311 linhas × 2 transportes: **ZERO**.
#:
#: É o item 1 da TUDO-FUNCIONA-01 preso onde ele está. A sprint dizia *"a
#: coluna que falta no mapa é «chega ao JOGO»"* — e a medição derrubou a
#: metade da frase que dizia «falta»: a coluna EXISTE desde 19/08 (os degraus
#: `O JOGO RECEBEU` e `O JOGO REAGIU`), com critério escrito e domínio
#: guardado. O que falta é a MEDIÇÃO, e ela é zero de 622.
#:
#: **O teto não pode sobrar**: no dia em que a primeira célula subir, esta
#: constante reprova pedindo o número novo — é a cicatriz de 03/09, *régua com
#: folga acumulada dá verde sobre o defeito seguinte*.
CELULAS_QUE_CHEGARAM_AO_JOGO = 0


def _linhas_do_mapa() -> dict[str, list[dict[str, str]]]:
    with MAPA.open(newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    fora: dict[str, list[dict[str, str]]] = {}
    for linha in linhas:
        fora.setdefault(linha.get("chave", ""), []).append(linha)
    return fora


def _degrau(linha: dict[str, str], lado: str) -> str:
    """O degrau declarado por aquele lado, ou :data:`SEM_REGISTRO`.

    Um valor fora da escada NÃO vira `SEM_REGISTRO` em silêncio — quem guarda
    o domínio da coluna é o `check_paridade_transporte`, e engolir aqui um
    degrau com outra tipografia faria esta régua dar verde sobre o que a irmã
    reprova.
    """
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


def ate_onde_foi(chaves: tuple[str, ...],
                 mapa: dict[str, list[dict[str, str]]]) -> tuple[str, str]:
    """`(cabo, rádio)` — o degrau de um gesto, pela PIOR das chaves dele.

    Um gesto com dois atos no aparelho só chegou quando os DOIS chegaram: o
    `auto-cores` governa a paleta e a numeração, e a paleta obedece desde 12/08
    enquanto a numeração não tem degrau registrado. Responder pela melhor
    metade é a família do número que envelhece calado.
    """
    fora = []
    for lado in ("cabo", "radio"):
        degraus = []
        for chave in chaves:
            minhas = [linha for linha in mapa.get(chave, [])
                      if linha.get("controle") == _O_APARELHO_DELA]
            degraus.extend(_degrau(linha, lado) for linha in minhas)
            if not minhas:
                degraus.append(SEM_REGISTRO)
        fora.append(_pior(degraus))
    return fora[0], fora[1]


def _canais(chaves: tuple[str, ...],
            mapa: dict[str, list[dict[str, str]]]) -> list[tuple[str, str]]:
    """`(id da célula, canal)` de cada lado de cada chave do gesto.

    Chave que não tem linha no mapa, ou lado sem `canal` escrito, levanta
    `SystemExit` em vez de devolver lista curta: o destino é o que decide se a
    feature chegou, e adivinhá-lo por ausência de dado é escolher o degrau mais
    barato — a mesma recusa do :data:`SEM_REGISTRO`.
    """
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
    """Até onde a prova daquela feature TEM de chegar — perguntado ao MAPA.

    A resposta sai de `*_canal` (do mapa) traduzida por
    :data:`check_paridade_transporte.DIRECAO_POR_CANAL` (do dono da escada), e
    **nada nesta régua a move**: era esse o defeito de 09/09/2026, quando o
    destino morava dentro da `A_PROVA_QUE_FALTA` e apagar uma declaração
    mudava a linha de chegada da feature declarada.

    Gesto com chaves de direções diferentes responde pelo destino mais LONGE,
    pela mesma razão de :func:`ate_onde_foi` responder pelo pior degrau: uma
    feature com dois atos só chegou quando o que anda mais longe chegou.
    """
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
    return _ORDEM.index(degrau) >= _ORDEM.index(destino)


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
            continue  # não é feature de aparelho — a irmã responde por ele
        cabo, radio = ate_onde_foi(chaves, mapa)
        destino = destino_de(chaves, mapa)
        alcancou = chegou(cabo, destino) and chegou(radio, destino)
        fora.append((gesto, ",".join(abas), cabo, radio, destino, alcancou))
    return fora


def _sprint_existe(arquivo: str) -> bool:
    return (SPRINTS / arquivo).exists()


def _imprimir_o_inventario(linhas: list[tuple[str, str, str, str, str, bool]]) -> None:
    """A LISTA «o que NÃO funciona», com as CINCO colunas — e não seis réguas.

    O critério de pronto dela de 08/09 pede as quatro colunas (cabo · BT · no
    perfil · por controle) nesta lista. Elas não são redigitadas aqui: vêm de
    :func:`check_cabo_bt_perfil_controle.tabela`, que é a dona delas. Esta
    régua só acrescenta a quinta — *até onde a prova chegou* — e o custo.
    """
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

    # 1. a declaração que não descreve feature nenhuma da tela
    orfas = sorted(set(A_PROVA_QUE_FALTA) - conhecidos)
    if orfas:
        print(f"VERMELHO: {len(orfas)} falta(s) declarada(s) para gesto que a "
              f"tela já não oferece como feature de aparelho:")
        for gesto in orfas:
            print(f"  {gesto} — tire a linha de `A_PROVA_QUE_FALTA`")
        return 1

    # 2. o vocabulário do custo, e a dona que tem de existir
    ruins = []
    for gesto, (custo, dona, _razao) in sorted(A_PROVA_QUE_FALTA.items()):
        if custo not in CUSTOS:
            ruins.append(f"  {gesto}: custo {custo!r} fora do vocabulário "
                         f"({', '.join(CUSTOS)})")
        if not _sprint_existe(dona):
            ruins.append(f"  {gesto}: a dona `{dona}` não está em "
                         f"docs/process/sprints/")
    if ruins:
        print(f"VERMELHO: {len(ruins)} declaração(ões) sem custo válido ou sem "
              f"dona no disco:")
        print("\n".join(ruins))
        return 1

    # 3. a prova que parou e ninguém declarou
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

    # 4. a falta que CHEGOU, e que vira propaganda se ficar
    chegaram = [g for g in A_PROVA_QUE_FALTA if g not in paradas]
    if chegaram:
        print(f"VERMELHO: {len(chegaram)} falta(s) declarada(s) cuja prova já "
              f"chegou ao destino — a declaração ficou velha:")
        for gesto in sorted(chegaram):
            _custo, dona, _razao = A_PROVA_QUE_FALTA[gesto]
            print(f"  {gesto}: tire a linha de `A_PROVA_QUE_FALTA` e feche a "
                  f"{dona}")
        return 1

    # 5. o teto do degrau de entrada, que só desce
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
