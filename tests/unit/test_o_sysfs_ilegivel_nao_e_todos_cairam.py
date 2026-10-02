"""A terceira resposta de ``uniqs_no_radio``, e por que ela existe."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    ESPERA_PROCURANDO,
    EsperaPeloPS,
    uniqs_no_radio,
)
from hefesto_dualsense4unix.integrations.sinal_da_barra import Instancia

#: O DualSense da mesa de teste. Máscara da casa: octetos 4 e 5 zerados.
NO_RADIO = "aa:bb:cc:00:00:4f"

NO_CABO = "aa:bb:cc:00:00:6d"


def _instancia(uniq: str, transporte: str) -> Instancia:
    return Instancia(
        instancia="0031",
        uniq=uniq,
        adaptador="hci0",
        hw_version="0x00000100",
        input_n=42,
        hidraw="hidraw3",
        transporte=transporte,
    )


@pytest.fixture
def raiz_viva(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Uma raiz de uhid que EXISTE, para a guarda deixar a leitura acontecer."""
    raiz = tmp_path / "uhid"
    raiz.mkdir()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.sinal_da_barra.RAIZ_UHID", str(raiz)
    )
    return raiz


def _plantar(monkeypatch: pytest.MonkeyPatch, resposta: Any) -> None:
    """Troca a enumeração do sysfs por uma resposta de mentira, ou por uma falha."""

    def _falso(raiz_uhid: str = "", *_args: Any, **_kwargs: Any) -> Any:
        from hefesto_dualsense4unix.integrations import sinal_da_barra

        if not Path(raiz_uhid or sinal_da_barra.RAIZ_UHID).is_dir():
            return []
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.sinal_da_barra.instancias_dualsense",
        _falso,
    )


class TestAsTresRespostasDaSonda:
    def test_sem_a_raiz_do_uhid_a_resposta_e_nao_sei(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura em uma linha: raiz ausente devolve ``None``, nunca ``set()``."""
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.sinal_da_barra.RAIZ_UHID",
            str(tmp_path / "uhid-que-nao-existe"),
        )
        _plantar(monkeypatch, [_instancia(NO_RADIO, "bt")])

        assert uniqs_no_radio() is None

    def test_leitura_que_falha_no_meio_tambem_e_nao_sei(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raiz existe e a leitura estoura — continua sendo "não sei"."""
        _plantar(monkeypatch, OSError("permissão negada"))

        assert uniqs_no_radio() is None

    def test_com_a_raiz_viva_a_resposta_e_quem_esta_no_radio(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A régua contra si mesma: a sonda TEM de saber responder."""
        _plantar(
            monkeypatch,
            [_instancia(NO_RADIO, "bt"), _instancia(NO_CABO, "usb")],
        )

        assert uniqs_no_radio() == {NO_RADIO.replace(":", "")}

    def test_a_mesa_vazia_de_verdade_e_conjunto_vazio(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O outro lado do "não sei": com a raiz legível, vazio é vazio."""
        _plantar(monkeypatch, [])

        assert uniqs_no_radio() == set()


class TestAEsperaNaoAcusaQuedaQueNaoHouve:
    """A costura: a espera REAL, com a sonda REAL, sem sysfs para ler."""

    def test_sysfs_ilegivel_nao_marca_o_controle_como_caido(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.sinal_da_barra.RAIZ_UHID",
            str(tmp_path / "uhid-que-nao-existe"),
        )
        espera = EsperaPeloPS(NO_RADIO, total_s=3)

        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.caiu is False, (
            "a sonda cega foi lida como queda — a espera vai anunciar que o "
            "controle caiu sem nada ter caído"
        )

    def test_a_mesa_vazia_legivel_marca_a_queda(
        self, raiz_viva: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A régua contra si mesma, do lado da espera."""
        _plantar(monkeypatch, [])
        espera = EsperaPeloPS(NO_RADIO, total_s=3)

        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.caiu is True
