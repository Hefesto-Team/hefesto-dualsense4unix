"""A chave de uma opção da extensão obedece ao que a tela mostra, e a janela acompanha o disco.

Medido em 25/11/2026 no ``interface.log`` e no diário de uma extensão: o ``opcoes.json`` foi gravado
por fora com a janela «Configurar» aberta; a janela seguiu mostrando a chave desligada, e o clique
para ligar gravou «desligada», porque o gesto invertia o que estava no disco e não o que se lia.

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- o ``_o_pedido_da_chave`` voltando a inverter o guardado reprova
  ``test_o_clique_na_chave_grava_o_contrario_do_que_a_tela_mostrava``;
- o ``pedido_da_chave`` devolvendo vazio reprova
  ``test_toda_chave_de_ligado_leva_o_pedido_escrito``;
- a marca do disco tirada do ``_redesenhar_se_mudou`` reprova
  ``test_a_janela_aberta_se_repinta_quando_a_opcao_muda_por_fora``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from hefesto_dualsense4unix.interface.desenho_da_experimental import janela_pintada, pedido_da_chave
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)

MOD = "toque"
PADRAO = "padrao"  # (noqa-acento)
OPCOES = [
    {"id": "brinquedos", "rotulo": "Brinquedos", "tipo": "ligado", "grupo": "Brinquedos",
     PADRAO: True},
    {"id": "controle", "rotulo": "Controle", "tipo": "ligado", "grupo": "Controle", PADRAO: True},
    {"id": "vibrar", "rotulo": "Vibrar os controles", "tipo": "ligado", "grupo": "Controle",
     PADRAO: False},
]
CHAVE = re.compile(r'<(?:span|i|div)\b([^>]*\bdata-gesto="guardar-opcao-da-modificacao"[^>]*)>')


def _atributo(atributos: str, nome: str) -> str | None:
    achado = re.search(rf'\b{nome}="([^"]*)"', atributos)
    return achado.group(1) if achado else None


def _chaves(html: str) -> dict[str, str]:
    """``{id da opção: o data-ligado que a chave traz}`` de cada chave pintada na janela."""
    return {str(_atributo(m.group(1), "data-v")).split(":")[1]:
            str(_atributo(m.group(1), "data-ligado")) for m in CHAVE.finditer(html)}


def _guardado(a07: Any) -> dict[str, Any]:
    from hefesto_dualsense4unix.mods import opcoes

    arquivo = opcoes.caminho(MOD, a07._lugares())
    return dict(json.loads(arquivo.read_text(encoding="utf-8"))) if arquivo.exists() else {}


def _gravar_por_fora(a07: Any, opcao_id: str, valor: bool) -> None:
    from hefesto_dualsense4unix.mods import opcoes

    opcoes.guardar(a07._a_instalada(MOD).manifesto, opcao_id, valor, a07._lugares())


def test_toda_chave_de_ligado_leva_o_pedido_escrito(janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2511-A-CHAVE-DA-EXTENSAO-OBEDECE-AO-QUE-A-TELA-MOSTRA.

    A chave da aba, a da linha e a que nasce desligada trazem o contrário do que mostram.
    """
    _a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    html = janela_pintada(abrir(_Ponte(VIVO))["blocos"])
    assert _chaves(html) == {"brinquedos": "0", "controle": "0", "vibrar": "1"}
    assert pedido_da_chave(True) == ' data-ligado="0"'
    assert pedido_da_chave(False) == ' data-ligado="1"'


def test_o_clique_na_chave_grava_o_contrario_do_que_a_tela_mostrava(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2511-A-CHAVE-DA-EXTENSAO-OBEDECE-AO-QUE-A-TELA-MOSTRA.

    A tela mostra a chave desligada, o disco muda por fora para ligada, e o clique liga.
    """
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:brinquedos", "evento": "click", "ligado": "0"}, ponte)
    assert _guardado(a07)["brinquedos"] is False
    mostrado = _chaves(janela_pintada(abrir(ponte)["blocos"]))["brinquedos"]
    assert mostrado == "1"
    _gravar_por_fora(a07, "brinquedos", True)
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:brinquedos", "evento": "click", "ligado": mostrado}, ponte)
    assert _guardado(a07)["brinquedos"] is True


def test_o_clique_sem_o_pedido_ainda_inverte_o_guardado(janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2511-A-CHAVE-DA-EXTENSAO-OBEDECE-AO-QUE-A-TELA-MOSTRA.

    A página que ainda não manda o pedido segue ligando e desligando.
    """
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.guardar_opcao_da_modificacao(ctx, {"v": f"{MOD}:vibrar", "evento": "click"}, ponte)
    assert _guardado(a07)["vibrar"] is True
    a07.guardar_opcao_da_modificacao(ctx, {"v": f"{MOD}:vibrar", "evento": "click"}, ponte)
    assert _guardado(a07)["vibrar"] is False


def test_a_janela_aberta_se_repinta_quando_a_opcao_muda_por_fora(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2511-A-CHAVE-DA-EXTENSAO-OBEDECE-AO-QUE-A-TELA-MOSTRA.

    No tique seguinte à gravação de fora, a chave pintada já pede o contrário do valor novo.
    """
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    abrir(_Ponte(VIVO))
    assert _chaves(a07._MEXIDA.html_mod)["vibrar"] == "1"
    _gravar_por_fora(a07, "vibrar", True)
    a07._redesenhar_se_mudou(a07._ler_as_instaladas())
    assert _chaves(a07._MEXIDA.html_mod)["vibrar"] == "0"
    visto = a07._MEXIDA.html_mod
    a07._redesenhar_se_mudou(a07._ler_as_instaladas())
    assert a07._MEXIDA.html_mod is visto
