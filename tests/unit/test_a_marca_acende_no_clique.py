"""A marca "há escolhas por aplicar" acende no CLIQUE, não só na troca de aba."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real()

from typing import Any

from hefesto_dualsense4unix.app.actions.config import (
    secao_controles,
    secao_mesa,
    secao_orcamento,
)


class _Seletor:
    """O dublê do `SegmentedSelector`: só o que `_ao_escolher` pergunta."""

    def __init__(self, escolha: str) -> None:
        self._escolha = escolha

    def get_active_id(self) -> str:
        return self._escolha


class _HostQueConta:
    """O mínimo: guarda a declaração e conta quantas vezes a marca foi pedida."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self.marcas = 0

    def _marcar_declaracao_por_aplicar(self) -> None:
        self.marcas += 1

    def _orcamento_lido(self) -> str | None:
        return None


def test_as_tres_secoes_pedem_a_marca() -> None:
    """O portão do padrão: quem escreve a declaração TEM de acender a marca."""
    import inspect

    for modulo in (secao_orcamento, secao_controles, secao_mesa):
        fonte = inspect.getsource(modulo)
        assert "_marcar_declaracao_por_aplicar" in fonte, (
            f"{modulo.__name__} escreve `_maquina_pendente` e NÃO acende a "
            "marca do rodapé: a pessoa declara e nada na tela diz que há "
            "escolha por aplicar"
        )
