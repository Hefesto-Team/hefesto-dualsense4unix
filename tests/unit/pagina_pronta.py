"""A página do desenho se espera pelos sinais de desenhada, nunca pela rede quieta.

Medido em 02/11/2026: nenhuma página do ``mockup/`` nem das publicadas pede nada à rede depois
do ``load`` (três pedidos, todos antes: o HTML e as duas fontes). O ``networkidle`` só somava
500 ms de silêncio por página, e com a máquina carregada estourava os 30 s calado. Os sinais são
o ``load`` do documento, o ``document.fonts.ready`` e dois quadros pintados (o que o motor da
página ainda faz depois do ``load``, o ``ResizeObserver`` da 08, roda antes do quadro); a régua
que lê um seletor pode exigir que ele esteja no DOM. Cada sinal tem prazo, e o erro diz qual faltou.
"""
from __future__ import annotations

import pathlib
from typing import Any

PRAZO_MS = 20_000

AS_FONTES = "() => document.fonts.ready.then(() => true)"
DOIS_QUADROS = ("() => new Promise(r => requestAnimationFrame("
                "() => requestAnimationFrame(() => r(true))))")


def _endereco(alvo: pathlib.Path | str) -> str:
    if isinstance(alvo, pathlib.Path):
        return alvo.resolve().as_uri()
    return alvo if "://" in alvo else pathlib.Path(alvo).resolve().as_uri()


def abrir(pg: Any, alvo: pathlib.Path | str, *, seletor: str | None = None,
          prazo_ms: int = PRAZO_MS) -> None:
    """Abre ``alvo`` em ``pg`` e só volta com a página desenhada; senão, diz o sinal que faltou."""
    from playwright.sync_api import TimeoutError as Estourou

    endereco = _endereco(alvo)
    passos: list[tuple[str, Any]] = [
        ("o load do documento",
         lambda: pg.goto(endereco, wait_until="load", timeout=prazo_ms)),
        ("o document.fonts.ready",
         lambda: pg.wait_for_function(AS_FONTES, timeout=prazo_ms)),
        ("dois quadros pintados",
         lambda: pg.wait_for_function(DOIS_QUADROS, timeout=prazo_ms)),
    ]
    if seletor is not None:
        passos.append((f"o seletor {seletor!r} no DOM",
                       lambda: pg.wait_for_selector(seletor, state="attached",
                                                    timeout=prazo_ms)))
    for sinal, esperar in passos:
        try:
            esperar()
        except Estourou:
            raise AssertionError(
                f"{endereco}: a página não deu {sinal} em {prazo_ms} ms") from None
