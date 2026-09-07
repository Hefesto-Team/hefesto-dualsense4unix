"""LIGHTBAR-O-CABO-FICOU-DE-FORA-01 — a barra do cabo, e o sinal certo.

Achado por ela na bancada de 07/09/2026, com os quatro DualSense na mesa:
*"o lightbar azul tá nos dois controles. p1 e p2. cada controle deve ter um
lightbar da sua cor apenas"*.

Eram DOIS defeitos com o mesmo sintoma:

1. **O gatilho da cor só conhecia o rádio.** `reescrever_lightbar_por_hidraw`
   filtra por transporte `bt`, e está certo em filtrar — o report cru do 0x31
   é a única via que pinta por Bluetooth. Mas ninguém repintava o do CABO, que
   é pintado pela classe LED do kernel. O Cosmic Red foi adotado sozinho,
   ganhou o azul do lugar 1, virou o lugar 2 e ficou azul — ao lado do
   Galactic Purple, que é o lugar 1 de verdade.

2. **O gatilho era armado cedo demais.** Ele arma por CONEXÃO NOVA, e a
   conexão é o começo da mudança, não o fim: a pintura saiu com o Starlight
   Blue no lugar 2 (vermelho) e, quando a mesa assentou, ele era o lugar 4
   (rosa). O sinal certo é o RESULTADO — "o número de alguém é outro".

E o cache do `SysfsLeds` é agravante, não causa: ele pula a escrita idêntica à
última (GUERRA-01 item 3), e mede a COR. Quando a mesa se renumera, a cor que
o controle DEVE ter mudou sem que a cor que ele TEM mudasse — o cache acerta a
pergunta errada. Por isso o repintar do cabo invalida antes de reafirmar.

Herméticos: nenhum aparelho, nenhum `/sys`. Dublês com a forma medida no
socket dela.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.daemon.connection import (
    armar_gatilho_da_cor_por_numeracao,
)


class _NoDeSysfs:
    """O nó da classe LED, com o cache que o de verdade tem."""

    def __init__(self) -> None:
        self.invalidado = 0

    def invalidate_cache(self) -> None:
        self.invalidado += 1


def _backend_com(handles: dict[str, str]) -> tuple[Any, dict[str, _NoDeSysfs]]:
    """Um backend só com o que este teste toca — sem abrir aparelho nenhum."""
    b = PyDualSenseController.__new__(PyDualSenseController)
    import threading

    b._io_lock = threading.RLock()
    b._output_mute = False
    # UM OBJETO POR CHAVE, e não `dict.fromkeys(..., object())`: aquele dá o
    # MESMO objeto a todos, e o dublê do transporte devolvia sempre o primeiro
    # — o teste reprovava a cura por defeito próprio.
    class _Handle:
        def __init__(self, transporte: str) -> None:
            self.transporte = transporte

    b._handles = {k: _Handle(v) for k, v in handles.items()}
    nos = {k: _NoDeSysfs() for k in handles}
    b._sysfs = nos
    b._detect_transport = lambda h: h.transporte  # type: ignore[assignment]
    b.reassert_resolved_outputs = lambda: b.__dict__.__setitem__(  # type: ignore[assignment]
        "_reasserts", b.__dict__.get("_reasserts", 0) + 1)
    return b, nos


def test_o_do_cabo_e_repintado_e_o_cache_e_invalidado_antes() -> None:
    """O cabo entra no repintar, e o cache não pode calar a cor nova."""
    b, nos = _backend_com({"p1": "bt", "p2": "usb", "p3": "bt", "p4": "usb"})
    fora = b.repintar_o_cabo_por_sysfs()

    assert set(fora) == {"p2", "p4"}, (
        f"o repintar do cabo pegou {sorted(fora)} — tinha de pegar só os do cabo")
    assert nos["p2"].invalidado == 1 and nos["p4"].invalidado == 1, (
        "o cache do cabo não foi invalidado — a cor nova seria pulada por ser "
        "'igual à última', que é a pergunta errada quando o NÚMERO mudou")
    assert nos["p1"].invalidado == 0 and nos["p3"].invalidado == 0, (
        "o do rádio foi invalidado à toa — quem o pinta é o report cru")
    assert b.__dict__.get("_reasserts") == 1, (
        "o reassert não rodou; invalidar sem reafirmar deixa a barra como está")


def test_sem_ninguem_no_cabo_e_no_op() -> None:
    """Mesa só de rádio: nada a invalidar, e NENHUM reassert à toa."""
    b, _nos = _backend_com({"p1": "bt", "p2": "bt"})
    assert b.repintar_o_cabo_por_sysfs() == {}
    assert b.__dict__.get("_reasserts") is None, (
        "reafirmou sem ninguém no cabo — é escrita periódica disfarçada")


def test_modo_nativo_nao_pinta_nada() -> None:
    """Regra dela: no Modo Nativo o dono do LED é o jogo."""
    b, nos = _backend_com({"p1": "usb"})
    b._output_mute = True
    assert b.repintar_o_cabo_por_sysfs() == {}
    assert nos["p1"].invalidado == 0


class _Daemon(SimpleNamespace):
    pass


def _daemon_com(numeros: dict[str, int]) -> Any:
    d = _Daemon()
    d.identity_registry = SimpleNamespace(numeros_da_mesa=lambda: dict(numeros))
    d.armados: list[tuple[str, Any]] = []
    return d


def test_a_numeracao_arma_o_gatilho_e_a_primeira_volta_nao(monkeypatch) -> None:
    """Muda o número → arma. Primeira volta e número igual → não arma.

    A primeira volta não pode armar: sem numeração anterior não há mudança a
    afirmar, e armar ali faria TODA partida do daemon repintar por nada — a
    adoção já pinta.
    """
    import hefesto_dualsense4unix.daemon.connection as conn

    armados: list[dict[str, Any]] = []
    monkeypatch.setattr(conn, "registrar_gatilho_da_lightbar", lambda d: None)
    monkeypatch.setattr(
        conn, "armar_gatilho",
        lambda d, nome, **kw: armados.append({"nome": nome, **kw}))

    d = _daemon_com({"aa": 1, "bb": 2})
    assert armar_gatilho_da_cor_por_numeracao(d) is False, "a primeira volta armou"
    assert armados == []

    # mesma mesa, mesmos números: nada acontece
    assert armar_gatilho_da_cor_por_numeracao(d) is False
    assert armados == []

    # alguém chega e TODO MUNDO se desloca — é aqui que a barra ficava velha
    d.identity_registry = SimpleNamespace(
        numeros_da_mesa=lambda: {"aa": 1, "cc": 2, "bb": 3})
    assert armar_gatilho_da_cor_por_numeracao(d) is True, (
        "o número de 'bb' foi de 2 para 3 e o gatilho não armou")
    assert armados and armados[0]["evento"] == "numeracao_da_mesa_mudou"


def test_chegada_que_nao_muda_numero_nao_repinta(monkeypatch) -> None:
    """Cair e voltar no MESMO lugar não é motivo para repintar.

    É a diferença entre armar pela CAUSA e armar pelo RESULTADO: o
    `armar_gatilho_da_cor` arma por conexão nova e este arma por número
    diferente. Um controle que volta ao próprio lugar passa pelo primeiro e
    não pode passar por este.
    """
    import hefesto_dualsense4unix.daemon.connection as conn

    armados: list[Any] = []
    monkeypatch.setattr(conn, "registrar_gatilho_da_lightbar", lambda d: None)
    monkeypatch.setattr(conn, "armar_gatilho",
                        lambda d, nome, **kw: armados.append(nome))

    d = _daemon_com({"aa": 1, "bb": 2})
    armar_gatilho_da_cor_por_numeracao(d)          # primeira volta: guarda
    armar_gatilho_da_cor_por_numeracao(d)          # nada mudou
    assert armados == []


def test_daemon_sem_registro_de_identidade_nunca_arma() -> None:
    """Dublê enxuto: o laço segue idêntico ao de antes, sem estourar."""
    d = _Daemon()
    assert armar_gatilho_da_cor_por_numeracao(d) is False
    d.identity_registry = SimpleNamespace()
    assert armar_gatilho_da_cor_por_numeracao(d) is False
    # e um registro que LEVANTA não pode derrubar o laço
    def _explode() -> dict[str, int]:
        raise RuntimeError("o registro caiu")
    d.identity_registry = SimpleNamespace(numeros_da_mesa=_explode)
    with contextlib.suppress(Exception):
        assert armar_gatilho_da_cor_por_numeracao(d) is False
