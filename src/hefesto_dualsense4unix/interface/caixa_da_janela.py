#!/usr/bin/env python3
"""A caixa da janela das abas, para as páginas que abrem POR FORA delas.

AS TRÊS PÁGINAS AVULSAS pedem a caixa a este arquivo: a Calibrar
(`calibrar.py`), o «Mapa do controle» (`mapa.py`) e o mapa das portas
(`pagina_do_mapa.py`). Ele lê do `topo.html` — o esqueleto das dez abas — o
recuo do corpo, a largura e a altura da `.janela`, e devolve a folha que dá a
mesma caixa a quem pedir.

A PALAVRA DELA, 24/09/2026, 02h03, na página da sessão dos desenhos, depois de
aprovar a Calibrar com a caixa da janela:

- o «Mapa do controle»: *«Sim, segue a caixa da janela»*;
- o mapa das portas: *«Vira caixa da janela, rolando por dentro»*.

POR QUE UM DONO SÓ, e o preço estava medido: a Calibrar tinha `width:1180px`,
a largura das abas antes de 08/09, e o «Mapa do controle» tinha
`.cx{width:1800px}` com `body{padding:22px}`. As duas eram CÓPIAS de um
tamanho que tem dono, e as duas ficaram para trás quando as abas passaram a
esticar. Medido no Chrome, na vista dela (1918x840):

    página                 a caixa antes            a `.janela` das abas
    calibrar-sensores      1180 x 499               1600 x 808 @ 159,16
    mapa-do-controle       1800 x 778 @ 59,22       idem
    mapa-das-portas        1180 x 2195, rolando     idem

POR QUE UM ARQUIVO PRÓPRIO, e não o `calibrar.py`, que era onde o leitor
morava: o `pagina_do_mapa` é importado pelo produto em tempo de execução
(`arranjo_desta_maquina`), pelo caminho do pacote. O `calibrar.py` importa o
`monta.py` inteiro — o logotipo, as tabelas de peças e o `led_control` — e
importa PLANO (`import onde`), o que só funciona com a pasta `interface/` no
`sys.path`. Este arquivo só lê um HTML ao lado dele, e por isso cabe nos dois
caminhos de importação.
"""
from __future__ import annotations

import pathlib
import re

#: O esqueleto das dez abas. É o mesmo arquivo que o `monta.TOPO` lê; o
#: `monta` só troca a âncora do logotipo, que mora fora do `<style>`.
TOPO = pathlib.Path(__file__).resolve().with_name("topo.html")

#: As variáveis do `:root` do `topo.html` que a `.janela` usa para se medir.
VARIAVEIS_DA_MOLDURA = ("--recuo-do-corpo", "--piso-da-vista", "--teto-da-vista",
                        "--alt-janela")

#: As propriedades da `.janela` que são TAMANHO. A borda, o raio e a sombra são
#: aparência, e cada página avulsa continua com a dela.
TAMANHO_DA_JANELA = ("width", "height", "max-width", "max-height")


def _folha_do_topo(topo: str) -> str:
    """O CSS do `<style>` do esqueleto das abas, sem os comentários.

    Sem comentário porque o `topo.html` CITA as próprias regras dentro deles —
    `clamp(--piso-da-vista, …)` está escrito num comentário ao lado da regra
    de verdade, e uma leitura que os visse acharia duas.
    """
    estilo = topo.split("<style>", 1)[1].split("</style>", 1)[0]
    return re.sub(r"/\*.*?\*/", "", estilo, flags=re.S)


def _regra(css: str, seletor: str) -> dict[str, str]:
    """As declarações da ÚNICA regra `seletor{…}` da folha, por propriedade.

    Zero ou duas é erro que PARA a geração: uma página que caísse num tamanho
    de reserva ficaria menor que as abas de novo, calada.
    """
    achadas = re.findall(rf"(?<=[}}\s]){re.escape(seletor)}\s*\{{([^{{}}]*)\}}", css)
    if len(achadas) != 1:
        raise SystemExit(f"ERRO: o topo.html tem {len(achadas)} regra(s) "
                         f"`{seletor}{{…}}`, e as páginas avulsas leem o tamanho "
                         f"das abas de UMA só.")
    declaracoes: dict[str, str] = {}
    for linha in achadas[0].split(";"):
        prop, sep, valor = linha.partition(":")
        if sep and prop.strip():
            declaracoes[prop.strip()] = " ".join(valor.split())
    return declaracoes


def moldura(topo: str | None = None, caixa: str = ".cx") -> str:
    """A folha que dá a ``caixa`` o recuo e o tamanho da `.janela` das dez abas.

    Lida do `topo.html` a cada geração. ``topo`` existe para a régua trocar o
    esqueleto e ver as páginas acompanharem; ``caixa`` é o seletor da caixa da
    página que pede — `.cx` no «Mapa do controle» e na Calibrar, `.pagina` no
    mapa das portas.
    """
    css = _folha_do_topo(TOPO.read_text(encoding="utf-8") if topo is None else topo)
    variaveis: list[str] = []
    for nome in VARIAVEIS_DA_MOLDURA:
        achados = re.findall(rf"{re.escape(nome)}\s*:\s*([^;]+);", css)
        if len(achados) != 1:
            raise SystemExit(f"ERRO: o topo.html declara `{nome}` {len(achados)} "
                             f"vez(es) — as páginas avulsas leem o tamanho das "
                             f"abas de lá.")
        variaveis.append(f"{nome}:{' '.join(achados[0].split())}")
    janela = _regra(css, ".janela")
    corpo = _regra(css, "body")
    faltam = [p for p in TAMANHO_DA_JANELA if p not in janela]
    if faltam or "padding" not in corpo:
        raise SystemExit(f"ERRO: o topo.html não diz mais {faltam or ['padding']} "
                         f"— as páginas avulsas não sabem o tamanho das abas.")
    tamanho = ";".join(f"{p}:{janela[p]}" for p in TAMANHO_DA_JANELA)
    return (f"  :root{{{';'.join(variaveis)}}}\n"
            f"  body{{padding:{corpo['padding']}}}\n"
            f"  {caixa}{{{tamanho}}}\n")
