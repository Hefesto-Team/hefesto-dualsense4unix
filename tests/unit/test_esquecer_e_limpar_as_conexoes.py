"""Esquecer e limpar as conexões — ESQUECER-E-LIMPAR-AS-CONEXOES-01.

O que ela disse em 30/09/2026, ~01h30, com os quatro DualSense no rádio:
*«opção esquecer ali. Esse dualsense fantasma ali não faz sentido.»*
<!-- noqa-acento: citação literal dela -->
E às ~03h, sobre o «Limpar Conexões»:
*«limpar com frequencia a cada troca <!-- noqa-acento: citação literal dela -->
ou ao desligar os controles, algo nessa linha»*.

MEDIDO antes da cura (02/10, sobre ``2fd24c009``, o mesmo instrumento antes e
depois): o «Conectar» anônimo que acabou fazia a linha «DualSense · Não
Conectou» sem aparelho, com a caixa laranja; a linha de quem não chegou ficava
com ele já no ar noutro adaptador; o X que a tirava morava na janela e ela
voltava ao reabrir; o teclado no ar não tinha como ser esquecido e o fone fora
do ar nem aparecia; a dobra do controle que desligou ficava; e a chave tirada
por outro programa, com o serviço vivo, ficava sem lápide.

As decisões (quem coordena, 30/09/2026, a validar por ela):
D-3009-A-LINHA-TEM-APARELHO, D-3009-O-ESQUECER-TEM-NOME,
D-3009-A-CASA-SE-LIMPA-SOZINHA (pela resposta dela; os momentos e as guardas de
quem coordena) e D-3009-TODO-ESQUECER-TEM-LAPIDE.

A central é a ``CentralDoRadio`` de verdade, com o ``DonoVivo`` de verdade por
cima do rádio de mentira com física, e todo pedido da tela atravessa o
tratador real do daemon. **A pergunta é sempre ao mundo e à central** — as
chamadas ao BlueZ, as lápides da ponte de mentira, os movimentos publicados —;
quando uma régua precisa de um botão, ela o acha no HTML da cena e o clica.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any


from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit.radio_de_mentira import AZUL, VERMELHO

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = "08-conexoes.html"
TECLADO = "aa:bb:cc:00:00:e1"
JOHNATHAN, ANDRE = VERMELHO, AZUL


class PonteDeTudo:
    """O ``ponte.resultado`` com o tratador REAL do daemon, para qualquer método"""

    def __init__(self, central: cr.CentralDoRadio) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Daemon(IpcHandlersMixin):
            pass

        self.eu = _Daemon()
        self.eu.daemon = SimpleNamespace(_central_do_radio=central)  # type: ignore[attr-defined]
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        tratador = getattr(self.eu, "_handle_" + metodo.replace(".", "_"), None)
        assert tratador is not None, f"método que o daemon não atende: {metodo}"
        self.chamadas.append((metodo, dict(params)))
        return asyncio.run(tratador(params))


def esperar(condicao: Any, teto: float = 5.0) -> bool:
    """Espera, no relógio de verdade, a condição valer. Não levanta."""
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


def nao_conectou(cena: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in cena["aparelhos"] if a.get("nao_conectou")]


def do_diario(caminho: Path, o_que: str) -> list[dict[str, Any]]:
    if not caminho.exists():
        return []
    linhas = [json.loads(x) for x in caminho.read_text(encoding="utf-8").splitlines() if x]
    return [x for x in linhas if x.get("o_que") == o_que]


def movimento(aparelho: str, destino: str, estado: str = cr.NAO_CHEGOU, *,
              motivo: str = cr.MOTIVO_SEM_GESTO, idade: float = 5.0) -> cr.Movimento:
    return cr.Movimento(aparelho, destino, estado, cr.PASSO_FIM if estado != cr.ESPERANDO
                        else cr.PASSO_GESTO, motivo=motivo, quando=time.time() - idade)


def test_o_desenho_nao_tem_linha_sem_aparelho() -> None:
    """A cena do desenho (a mesma que gera o mockup) mostra um «Não Conectou»"""
    from hefesto_dualsense4unix.interface import aba08

    linhas = [a for a in aba08.CENA_DO_RADIO["aparelhos"] if a.get("nao_conectou")]
    assert linhas, "o desenho perdeu o «Não Conectou»"
    assert [a["id"] for a in linhas if not a.get("aparelho")] == []
    assert all(a.get("nome") and a.get("cor") for a in linhas), linhas
    mockup = (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")
    assert "Não Conectou" in mockup
