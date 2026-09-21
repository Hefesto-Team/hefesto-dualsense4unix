"""A `wm_class` que um jogo VAI anunciar — e o «não sei», que é resposta.

**POR QUE ESTE MÓDULO EXISTE, e a razão é uma derivação que caiu.**

`censo_dos_lancadores.JogoDoLancador.classe_de_janela` respondia, desde
10/09/2026, com o **basename do `install.executable`**: `retail/gotg.exe` virava
`gotg.exe`. A nota de 11/09 que morava lá declarava, com todas as letras, que
aquilo nunca fora medido:

    *"A IGUALDADE ACIMA É DERIVAÇÃO, E NÃO MEDIÇÃO (…) ninguém abriu Guardiões
    da Galáxia e leu a classe da janela viva."*

E escrevia o degrau que fecharia, com as duas respostas possíveis. **Em
21/09/2026 ela abriu o jogo pelo Heroic e a resposta foi a segunda:**

    $ xprop -id <a janela do GotG> WM_CLASS
    WM_CLASS(STRING) = "steam_app_1088850", "steam_app_1088850"

A derivação caiu, e com ela o perfil dela: `window_class: ["gotg.exe"]` é uma
regra que **nunca casa**. Nenhum perfil ativava, nenhuma feature chegava ao
jogo, e a leitura dela foi a certa — *"o Hefesto não é identificado e não
funciona lá"*.

POR QUE A JANELA DIZ «STEAM» NUM JOGO DA EPIC
=============================================

O Heroic não chama o `.exe`. Ele chama o **umu**, que monta a MESMA pilha da
Steam (pressure-vessel + GE-Proton) e exporta `SteamAppId`. Medido no ambiente
dos processos vivos dela:

    GAMEID=umu-1088850     STORE=egs     SteamAppId=1088850
    UMU_ID=umu-1088850     PROTONPATH=…/GE-Proton10-34

O Proton batiza a janela de `steam_app_<SteamAppId>`. Ou seja: **todo jogo
lançado por umu — Heroic, Lutris, Bottles — anuncia-se com a forma da Steam**, e
o produto já sabe ler essa forma desde a UNIFICA-PREDICADO-01.

E O NÚMERO NÃO PRECISA DO JOGO ABERTO
======================================

O Heroic o guarda em `store_cache/umu.json`, casado com o `app_name` da
biblioteca. É isto que ela chamou de *"ser inteligente por default"*: a chave
está no disco, legível, antes de ela abrir o jogo uma única vez.

O «NÃO SEI» É ENTREGA, TANTO QUANTO OS OUTROS DOIS DEGRAUS
===========================================================

A derivação de 11/09 falhou porque **chutava onde devia dizer «não sei»**. Uma
chave que nunca casa é pior que nenhuma chave: a tela promete um casamento que
não existe, o perfil nasce morto, e ela perde a tarde procurando o defeito no
lugar errado — que foi exatamente o que aconteceu entre 10 e 21/09.

Por isso :func:`classe_de_janela` devolve `""` quando não sabe, e quem chama não
oferece a linha. Quem não tem chave tem o «Detectar», que pergunta ao
compositor e nunca erra.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

__all__ = [
    "PREFIXO_UMU",
    "classe_de_janela",
    "classe_do_umu_id",
    "umu_por_chave_do_heroic",
]

#: O que o umu põe em `GAMEID`/`UMU_ID`: `umu-<N>`, onde `<N>` é o appid da
#: Steam daquele jogo **mesmo quando ele não veio da Steam**. É esse número que
#: vira o `SteamAppId` e, por ele, o nome da janela.
PREFIXO_UMU = "umu-"

#: `umu-1088850` -> `1088850`. Só dígitos: o umu também usa ids não-numéricos
#: (`umu-default`), e derivar `steam_app_default` daria uma chave que nunca
#: casa — o defeito que este módulo existe para não repetir.
_UMU_RE = re.compile(rf"^{re.escape(PREFIXO_UMU)}(\d+)$", re.IGNORECASE)


def classe_do_umu_id(umu_id: str) -> str:
    """`umu-1088850` -> `steam_app_1088850`. `""` quando não é um id numérico.

    **A FORMA É A DA STEAM, e não é acaso nem gambiarra:** quem batiza a janela
    é o Proton, a partir do `SteamAppId` que o umu exporta. Um jogo da Epic
    rodando por umu é, do ponto de vista da janela, indistinguível de um jogo da
    Steam — e é por isso que o produto já sabe casá-lo.

    `umu-default` e outros ids não-numéricos devolvem `""`: o `SteamAppId` que
    o umu exporta nesse caso não é o texto do id, e inventar
    `steam_app_default` seria a mesma classe de defeito que a derivação pelo
    executável.
    """
    achado = _UMU_RE.match(str(umu_id or "").strip())
    return f"steam_app_{achado.group(1)}" if achado else ""


def umu_por_chave_do_heroic(cache: Path) -> dict[str, str]:
    """`{app_name: "umu-<N>"}` lido do `store_cache/umu.json` do Heroic.

    O arquivo guarda as chaves PREFIXADAS PELO RUNNER
    (`legendary_63a665088eb1480298f1e57943b225d8`), e o censo conhece o jogo
    pelo `app_name` cru. O prefixo é recortado aqui, num lugar só: recortá-lo em
    cada chamador seria a segunda grafia do mesmo fato.

    **`__timestamp` NÃO É JOGO.** O Heroic guarda, no mesmo dicionário, um
    `__timestamp` cujo valor é outro dicionário. Passá-lo adiante poria uma
    entrada com id impossível na lista — e o `str()` de um dicionário é uma
    string, então o erro não apareceria como erro.

    Queda vazia e calada: sem o arquivo (Heroic nunca aberto, ou nenhum jogo
    que o umu conheça), ninguém tem umu-id — que é um estado legítimo, não uma
    falha. Um `erro` aqui poria uma frase de defeito sobre uma biblioteca sã.
    """
    try:
        dado = json.loads((cache / "umu.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dado, dict):
        return {}
    mapa: dict[str, str] = {}
    for chave, valor in dado.items():
        if not isinstance(valor, str) or str(chave).startswith("__"):
            continue
        crua = str(chave)
        # `legendary_<app_name>` / `gog_<id>` / `nile_<id>` -> o id cru.
        nua = crua.split("_", 1)[1] if "_" in crua else crua
        mapa[nua] = valor
    return mapa


#: A extensão que denuncia o Windows. Um `.exe` **nunca** roda nativo no Linux:
#: ele vai por Proton/wine, e quem batiza a janela nesse caminho é o Proton (a
#: partir do `SteamAppId`), não o nome do arquivo. Foi exatamente aqui que a
#: derivação de 10/09 errou — `retail/gotg.exe` virava `gotg.exe` e a janela
#: dizia `steam_app_1088850`.
_EXTENSAO_DE_WINDOWS = ".exe"


def _palpite_do_executavel(executavel: str) -> str:
    """O basename do executável, **só quando ele não é um `.exe`**.

    **ESTE É O TERCEIRO DEGRAU, E ELE É UM PALPITE DECLARADO.** Ele existe para
    o jogo NATIVO Linux — o que o Lutris lança direto, sem Proton: aí o toolkit
    batiza a janela e o basename do binário é um candidato razoável.

    **O `.exe` SAI, e é a metade medida da cura.** Um `.exe` vai por
    Proton/wine em qualquer lançador, e nesse caminho quem nomeia a janela é o
    Proton. Deixar o `.exe` cair aqui seria reescrever a derivação que a janela
    viva do GotG derrubou em 21/09/2026 — com o mesmo resultado: uma chave que
    nunca casa.

    Continua sendo palpite, e por isso é o ÚLTIMO: os dois degraus acima leem
    um identificador que o lançador escreveu; este lê um nome de arquivo e
    torce. Quando ele errar, o «Detectar» conserta em um clique — e o que ele
    poupa é o clique no caso comum.
    """
    nome = str(executavel or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not nome or nome.lower().endswith(_EXTENSAO_DE_WINDOWS):
        return ""
    return nome


def classe_de_janela(
    *, umu_id: str = "", appid_da_steam: str = "", executavel: str = "",
) -> str:
    """A `wm_class` que este jogo vai anunciar — ou `""` quando não se sabe.

    **OS TRÊS DEGRAUS, e o terceiro é tão entrega quanto os outros dois:**

    ===  =============================================  ======================
    #    fonte                                          resposta
    ===  =============================================  ======================
    1    o `umu-<N>` do lançador (Heroic, Lutris…)      ``steam_app_<N>``
    2    o appid da Steam                               ``steam_app_<appid>``
    3    o executável, **se não for `.exe`**            o basename (palpite)
    4    nada disso                                     ``""`` — «não sei»
    ===  =============================================  ======================

    O degrau 3 é o jogo NATIVO Linux, e é palpite declarado — ver
    :func:`_palpite_do_executavel`, que diz por que o `.exe` fica de fora.

    **O UMU VEM PRIMEIRO, e a ordem é medida.** Um jogo pode estar nas duas
    bibliotecas (o GotG dela está na Epic e existe na Steam), e quem decide o
    nome da janela é **quem o lançou**. O umu-id vem do lançador que ela usou;
    o appid da Steam é o que a Steam usaria se fosse ela a lançar. Preferir o
    segundo poria a chave do lançador errado num jogo que ela abre pelo outro.

    Na prática os dois números coincidem quando o umu conhece o jogo — foi
    medido: `umu-1088850` e o appid 1088850 são o mesmo jogo. A ordem importa
    para o dia em que não coincidirem.
    """
    do_umu = classe_do_umu_id(umu_id)
    if do_umu:
        return do_umu
    numero = str(appid_da_steam or "").strip()
    if numero.isdigit():
        return f"steam_app_{numero}"
    return _palpite_do_executavel(executavel)
