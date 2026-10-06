"""Abre uma página LOCAL no Chrome sem depender da rede — o ponto comum dos portões de página.

O DEFEITO, MEDIDO em 06/10/2026 (~04h), com a rede fora (`EAI_AGAIN`): as páginas
da interface pedem a fonte ao Google (`<link href="https://fonts.googleapis.com/…">`),
o `goto` de um `file://` esperava o evento `load` por 30 s e REPROVAVA; com a
rede de volta os mesmos portões passavam em 3,5 s. Um portão que reprova pela rede
mede a rede, não a página.

A CURA, NA ORIGEM: toda requisição que não é local é RECUSADA na hora (`route.abort`),
então o `load` não tem mais recurso externo a esperar e a medida deixa de depender de a
rede responder, de demorar ou de chegar no meio da medida; a fonte vem do sistema ou cai
no fallback, que é o que a pessoa sem internet também vê. A espera é pela condição que o
portão mede: o `load` (que agora é imediato), as fontes aplicadas e dois quadros de
layout, no lugar do `networkidle` e dos 250 ms fixos.

O que o portão MEDE não muda: a geometria que ele lê é a do desenho, não a de um CSS
que alguém serve de fora.
"""
from __future__ import annotations

from typing import Any

CHROME = "/usr/bin/google-chrome"

#: esquemas que moram nesta máquina; tudo o mais é rede.
_LOCAIS = ("file:", "data:", "blob:", "about:")

_ESPERA_O_DESENHO_ASSENTAR = """() => document.fonts.ready.then(
  () => new Promise((fim) => requestAnimationFrame(() => requestAnimationFrame(fim))))"""


def e_local(url: str) -> bool:
    """A URL se resolve sem sair da máquina?"""
    return url.startswith(_LOCAIS)


def recusar_a_rede(pagina: Any) -> list[str]:
    """Instala o bloqueio e devolve a lista VIVA do que foi recusado."""
    recusadas: list[str] = []

    def decide(rota: Any) -> None:
        url = rota.request.url
        if e_local(url):
            rota.continue_()
            return
        recusadas.append(url)
        rota.abort()

    pagina.route("**/*", decide)
    return recusadas


def abrir_sem_rede(
    navegador: Any,
    uri: str,
    *,
    largura: int,
    altura: int,
    bloquear: bool = True,
    espera_ms: int = 30_000,
    **opcoes: Any,
) -> tuple[Any, list[str]]:
    """Abre `uri` numa página nova e devolve `(página, recusadas)`.

    `navegador` é um `Browser` ou um `BrowserContext` (os dois têm `new_page`).

    `bloquear=False` existe só para a régua provar que o bloqueio é o que segura o
    portão: sem ele, uma rede que não responde volta a pendurar o `load`.
    """
    pagina = navegador.new_page(**opcoes)
    pagina.set_viewport_size({"width": largura, "height": altura})
    recusadas = recusar_a_rede(pagina) if bloquear else []
    pagina.goto(uri, wait_until="load", timeout=espera_ms)
    pagina.evaluate(_ESPERA_O_DESENHO_ASSENTAR)
    return pagina, recusadas
