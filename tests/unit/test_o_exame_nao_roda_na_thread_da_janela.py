"""O exame da mesa sai da thread do GTK, e o resultado volta por ela."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("o exame fora da thread do GTK")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_CERTO,
    Item,
)

ITENS = [
    Item(
        chave="daemon",
        rotulo="O Hefesto está de pé",
        estado=ESTADO_CERTO,
        porque=None,
        cura=None,
    )
]


class _ExecutorAdiado:
    """Anota o que foi submetido e **não roda nada**."""

    def __init__(self) -> None:
        self.submetidos: list[Any] = []

    def submit(self, funcao: Any, *args: Any, **kwargs: Any) -> None:
        self.submetidos.append(lambda: funcao(*args, **kwargs))


class _Bancada:
    """O painel, o executor adiado e as duas espiãs, montados juntos."""


    def rodar_o_worker(self) -> None:
        """Roda o que foi para o executor — o que a thread de verdade faria."""
        for trabalho in list(self.executor.submetidos):
            trabalho()


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Bancada:
    return _Bancada(monkeypatch)


class TestOExameVaiParaOWorker:
    def test_reexaminar_submete_e_nao_examina_na_hora(self, bancada: _Bancada) -> None:
        """A asserção que morde: o executor FOI CHAMADO, e o exame não rodou."""
        bancada.painel.reexaminar()

        assert len(bancada.executor.submetidos) == 1, (
            "o exame não foi entregue ao worker — se ele rodou, rodou na thread "
            "da janela, e a janela congela até o `busctl` responder"
        )
        assert bancada.exames == [], (
            "o exame rodou dentro de `reexaminar`, isto é, na thread do GTK"
        )

    def test_o_que_foi_submetido_e_o_exame_de_verdade(
        self, bancada: _Bancada
    ) -> None:
        """A régua contra si mesma: submeter qualquer coisa não basta."""
        bancada.painel.reexaminar()
        bancada.rodar_o_worker()

        assert bancada.exames == ["exame"]


class TestOResultadoVoltaPelaThreadDoGtk:
    def test_o_worker_posta_o_resultado_no_idle_add(self, bancada: _Bancada) -> None:
        """O worker NÃO escreve widget: ele pede à thread do GTK que escreva."""
        bancada.painel.reexaminar()
        bancada.rodar_o_worker()

        assert bancada.postados, (
            "o resultado do exame não passou pelo `GLib.idle_add` — o worker "
            "escreveu widget de fora da thread do GTK"
        )
        funcao, args = bancada.postados[0]
        assert funcao == bancada.painel.aplicar
        assert args[0] == ITENS
        assert args[1] == ESTADO_CERTO

    def test_o_worker_nao_chama_aplicar_por_conta_propria(
        self, bancada: _Bancada
    ) -> None:
        """A outra metade, e ela é a que a mutação derruba."""
        bancada.painel.reexaminar()
        bancada.rodar_o_worker()

        assert bancada.aplicados == [], (
            "`aplicar` rodou dentro do worker — os `Gtk.Label` da seção foram "
            "escritos de fora da thread do GTK"
        )
