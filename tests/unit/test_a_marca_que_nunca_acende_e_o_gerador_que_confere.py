#!/usr/bin/env python3
"""A MARCA QUE NUNCA ACENDE e O GERADOR QUE CONFERE ANTES — A-MARCA-DA-DEGRADACAO-01.

Duas réguas de uma sprint de 13/09/2026, e cada uma guarda um achado medido
pela validação da RESTOS-DA-ONDA-DOIS-01:

1. **A MARCA DA EMULAÇÃO DEGRADADA SAIU.** O cartão da 01 (`degradou-cartao`) e
   a máscara da 02 (`mascara-degradou`) tinham um `<sup>*</sup>` que a folha só
   mostrava por `.degradou[title]`. A camada de dicas do piloto leva o `title`
   para `data-hef-dica` e o tira do elemento, então no WebKit o asterisco nunca
   acendeu; e aceso seria frase de aviso numa dica, que a terceira lista dela
   tira da tela. As réguas cobram a ausência nos DOIS lados — o pacote e a
   página —, e que nenhuma folha das dez decida pintura por `[title]`.

2. **O GERADOR CONFERE ANTES DE ESCREVER.** Com a autoconferência do `aba06.py`
   reprovando, o `mockup/06` já estava escrito, e o `--publicar` seguinte
   publicou a página recusada. Os dez geradores passaram a escrever numa
   bancada provisória e só copiar para a de verdade depois de conferir. A régua
   sabota a primeira escrita de cada um e exige a bancada com o mesmo md5.

ONDE ELA ESCREVE: numa cópia do `mockup/` em `tmp_path`, pelo desvio
`HEFESTO_BANCADA` que `interface/onde.py` documenta. A bancada não é tocada.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto, a01_jogar, a02_controles

#: AS DUAS PÁGINAS QUE TINHAM A MARCA, e o endereço que cada uma carregava.
MARCADAS = {"01-jogar.html": "degradou-cartao", "02-controles.html": "mascara-degradou"}

#: UM CONTROLE QUE DEGRADA DE VERDADE: backend `uinput` E motivo. Era a única
#: combinação em que a marca acendia. Faixa forjada da casa (`aa:bb:cc`).
DEGRADADO: dict[str, Any] = {
    "uniq": "aa:bb:cc:00:00:01", "connected": True, "player_slot": 1, "player": 1,
    "transport": "usb", "battery_pct": 50, "is_primary": True,
    "inputs": {"buttons": []},
    "vpad_backend": "uinput", "vpad_motivo": "uhid_indisponivel",
}

#: OS GERADORES, DERIVADOS DO DISCO — o gerador número onze nasce coberto.
GERADORES = sorted(p.name for p in INTERFACE.glob("aba[0-9][0-9].py"))


def _folhas(doc: str) -> str:
    """Todas as folhas `<style>` da página, sem os comentários de CSS."""
    blocos = "".join(re.findall(r"<style[^>]*>(.*?)</style>", doc, re.S))
    return re.sub(r"/\*.*?\*/", "", blocos, flags=re.S)


# ===========================================================================
# 1. A MARCA SAIU — do pacote e da página
# ===========================================================================
def test_o_controle_de_prova_degrada_de_verdade() -> None:
    """Sem isto as duas réguas do pacote passariam por AUSÊNCIA.

    O dono da frase continua sendo `controller_card.texto_degradacao`, e para
    esta entrada ele ainda responde. Se deixar de responder, a régua de baixo
    mediria um controle inteiro e ficaria verde sobre qualquer pacote.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import texto_degradacao

    assert texto_degradacao(DEGRADADO), (
        "o controle de prova deixou de degradar para o dono da frase — escolha "
        "outra combinação de `vpad_backend` e `vpad_motivo`")


def test_o_cartao_da_01_nao_emite_a_marca() -> None:
    """MORDE: devolva `"degradou-cartao": ...` ao `a01_jogar.pacote` e reprova."""
    estado = {"connected": True, "native_mode": False, "paused": False,
              "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
              "controllers": [DEGRADADO]}
    ctx = Contexto(state=estado, mesa=[], conectados=[DEGRADADO], estados={})
    cartao = a01_jogar.pacote(ctx)["cartoes"][DEGRADADO["uniq"]]
    assert "degradou-cartao" not in cartao, (
        "o cartão da 01 voltou a emitir a marca da emulação degradada")
    assert "degradou-cartao" not in a01_jogar.POR_CARTAO


def test_o_card_da_02_nao_emite_a_marca() -> None:
    """MORDE: devolva `"mascara-degradou": ...` ao card da 02 e reprova.

    O ENDEREÇO ENTRA NA LISTA À FORÇA: `_so_se_a_pagina_tiver` descarta o que a
    página não tem, e sem isto um campo devolvido ao pacote sumiria no filtro e
    a régua passaria por ausência.
    """
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    a02_controles._ENDERECOS = (
        frozenset(re.findall(r'data-campo="([^"]+)"', doc)) | {"mascara-degradou"})
    try:
        fora = a02_controles.pacote(
            Contexto(state={}, mesa=[], conectados=[DEGRADADO], estados={}))
    finally:
        a02_controles._ENDERECOS = None
    assert "mascara-degradou" not in fora["cards"][DEGRADADO["uniq"]], (
        "o card da 02 voltou a emitir a marca da emulação degradada")


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
@pytest.mark.parametrize("nome", sorted(MARCADAS))
def test_a_pagina_nao_tem_a_marca(nome: str, publicado: bool) -> None:
    """MORDE: devolva o `<sup>` ou a regra `.degradou` ao gerador, regere e publique.

    O comentário HTML sai antes de procurar: a nota datada que explica a saída
    cita o endereço morto, e nota não é tela.
    """
    doc = onde.pagina(nome, publicado=publicado).read_text(encoding="utf-8")
    sem_nota = re.sub(r"<!--.*?-->", "", doc, flags=re.S)
    assert 'class="degradou"' not in sem_nota, f"{nome}: o `<sup>` da marca voltou"
    assert f'data-campo="{MARCADAS[nome]}"' not in sem_nota, (
        f"{nome}: o endereço `{MARCADAS[nome]}` voltou")
    assert ".degradou" not in _folhas(doc), f"{nome}: a regra `.degradou` voltou"


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_nenhuma_folha_das_dez_decide_pintura_por_title(publicado: bool) -> None:
    """Seletor `[title]` numa folha é pintura que nunca acontece no WebKit.

    A camada de dicas do piloto (`hefesto_vivo.py`) leva todo `title` para
    `data-hef-dica` e o remove do elemento. Foi assim com a guarda do
    alto-falante (curada com `data-apagado`) e com a marca da degradação.

    MORDE: ponha `.x[title]{display:none}` no CSS de qualquer gerador, regere e
    publique.
    """
    paginas = [p for p in onde.paginas(publicado=publicado)
               if re.match(r"\d\d-", p.name)]
    assert len(paginas) >= 10, f"achei {len(paginas)} páginas — a régua mediria o vazio"
    achados = [p.name for p in paginas if "[title" in _folhas(p.read_text(encoding="utf-8"))]
    assert not achados, (
        f"folha que decide pintura por `[title]` em {achados}: a camada de dicas "
        "tira o atributo, e o seletor não casa. Use um atributo próprio escrito "
        "pelo alvo `atributo`, como o `data-apagado`")


# ===========================================================================
# 2. O GERADOR CONFERE ANTES DE ESCREVER — nos dez
# ===========================================================================
#: A SABOTAGEM: a primeira escrita de página grava um documento DIFERENTE e
#: logo recusa, que é exatamente o que um gerador na forma antiga fazia quando a
#: autoconferência reprovava. Os dois nomes do módulo são trocados porque o
#: `monta.py` o importa por `import onde`.
SABOTAGEM = """
import pathlib, runpy, sys
gerador = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(gerador.parent))
import onde as por_nome
from hefesto_dualsense4unix.interface import onde as por_pacote
for alvo in {id(por_nome): por_nome, id(por_pacote): por_pacote}.values():
    def gravar_e_recusar(nome, doc, original=alvo.gravar):
        original(nome, doc + "\\n<!-- escrita sabotada pela régua -->")
        raise SystemExit("sabotagem da régua: a conferência recusou " + nome)
    alvo.gravar = gravar_e_recusar
sys.argv = [str(gerador)]
runpy.run_path(str(gerador), run_name="__main__")
"""


def _bancada(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Uma bancada de mentira com as páginas de hoje, e um TMPDIR só dela."""
    bancada = tmp_path / "bancada"
    bancada.mkdir()
    for p in (RAIZ / "mockup").glob("*.html"):
        shutil.copy2(p, bancada / p.name)
    provisorio = tmp_path / "tmp"
    provisorio.mkdir()
    return bancada, provisorio


def _ambiente(bancada: pathlib.Path, provisorio: pathlib.Path) -> dict[str, str]:
    ambiente = dict(os.environ)
    ambiente["HEFESTO_BANCADA"] = str(bancada)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    ambiente["TMPDIR"] = str(provisorio)
    return ambiente


def _md5(pasta: pathlib.Path) -> dict[str, str]:
    return {p.name: hashlib.md5(p.read_bytes()).hexdigest()
            for p in sorted(pasta.glob("*.html"))}


def _pagina_do(gerador: str) -> str:
    achadas = sorted(p.name for p in (RAIZ / "mockup").glob(f"{gerador[3:5]}-*.html"))
    assert len(achadas) == 1, f"{gerador}: esperava uma página, achei {achadas}"
    return achadas[0]


@pytest.mark.parametrize("gerador", GERADORES)
def test_a_recusa_nao_chega_a_bancada(gerador: str, tmp_path: pathlib.Path) -> None:
    """A escrita sabotada recusa, e a bancada sai com o mesmo md5 de antes.

    MORDE: devolva a forma antiga ao `__main__` de qualquer gerador (`monta()`
    direto na bancada, `_conferir()` depois) e o caso dele reprova no md5.
    """
    bancada, provisorio = _bancada(tmp_path)
    antes = _md5(bancada)
    r = subprocess.run(
        [sys.executable, "-c", SABOTAGEM, str(INTERFACE / gerador)],
        capture_output=True, text=True, timeout=300,
        env=_ambiente(bancada, provisorio), cwd=str(RAIZ))
    assert r.returncode != 0 and "sabotagem da régua" in r.stderr, (
        f"`{gerador}` não passou pela escrita sabotada (rc={r.returncode}) — a "
        f"régua não mediu nada:\n{r.stderr.strip()[-800:]}")
    assert _md5(bancada) == antes, (
        f"`{gerador}` recusou a página e a bancada MUDOU: a escrita veio antes "
        "da conferência, e o `--publicar` seguinte levaria a página recusada")
    # E A SAÍDA RECUSADA FICA NO PROVISÓRIO, para quem quiser olhar.
    recusadas = list(provisorio.glob(f"hefesto-prova-*/{_pagina_do(gerador)}"))
    assert any("escrita sabotada" in p.read_text(encoding="utf-8") for p in recusadas), (
        f"`{gerador}` recusou e a saída não ficou em `$TMPDIR/hefesto-prova-*`")


@pytest.mark.parametrize("gerador", GERADORES)
def test_o_gerador_que_passa_escreve_a_bancada(gerador: str, tmp_path: pathlib.Path) -> None:
    """Sem sabotagem, a página chega à bancada e o provisório é apagado.

    A BANCADA COMEÇA ENVENENADA, e é de propósito: uma cópia do `mockup/` já é
    igual ao que o gerador produz, e um gerador que parasse de copiar passaria
    por ausência.
    """
    bancada, provisorio = _bancada(tmp_path)
    pagina = bancada / _pagina_do(gerador)
    pagina.write_text(pagina.read_text(encoding="utf-8") + "\n<!-- velha -->",
                      encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(INTERFACE / gerador)],
        capture_output=True, text=True, timeout=300,
        env=_ambiente(bancada, provisorio), cwd=str(RAIZ))
    assert r.returncode == 0, f"`{gerador}` não roda:\n{r.stderr.strip()[-1200:]}"
    assert pagina.read_bytes() == (RAIZ / "mockup" / pagina.name).read_bytes(), (
        f"`{gerador}` conferiu e não copiou a página para a bancada")
    assert not list(provisorio.glob("hefesto-prova-*")), (
        f"`{gerador}` deixou a bancada provisória para trás depois de passar")
