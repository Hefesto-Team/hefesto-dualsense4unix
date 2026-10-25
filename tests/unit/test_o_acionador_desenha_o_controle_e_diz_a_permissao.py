"""O-ACIONADOR-DESENHA-O-CONTROLE-QUE-ESTA-NA-MAO-E-DIZ-A-PERMISSAO-01 — a recusa diz o que fazer.

Numa máquina em que o usuário não está no grupo ``input``, abrir o ``/dev/input/event*`` de um
teclado ou de um pedal falha com ``PermissionError``. O dono da recusa é
``utils.maquina.abrir_o_aparelho_de_entrada``: ela vira UMA frase, que ensina a liberar. O gesto
«Esperar a próxima tecla» da 08 falha o clique com essa frase (o botão pisca, a frase vai ao
diário), e a ponte do daemon a registra em ``warning``, uma vez por aparelho, em vez de um
``info`` a cada procura.

A régua nunca abre o ``/dev/input`` da máquina: o evdev é trocado por um que recusa, e o
``/sys/class/input`` é uma pasta de mentira.

MORDIDAS: a abertura crua (sem o ``try`` em ``abrir_o_aparelho_de_entrada``) reprova o primeiro
caso; o gesto com a frase velha reprova o segundo; a ponte com o ``info`` de antes, ou sem a
lembrança do que já foi dito, reprova o terceiro.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import evdev
import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.utils import maquina
from tests.unit.test_os_acionadores_usb_entram_como_botoes import (
    CHAVE,
    NOME,
    _cena,
    _declarado,
    _sys_de_mentira,
)

FRASE = maquina.FRASE_SEM_PERMISSAO_DE_LER


def _recusar(caminho: str, *_: Any, **__: Any) -> Any:
    raise PermissionError(13, "Permission denied", caminho)


@pytest.fixture
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes._RASCUNHO = None
    yield a08_conexoes
    a08_conexoes._RASCUNHO = None


def test_a_frase_diz_o_que_fazer() -> None:
    """A frase nomeia o grupo e o passo que falta: entrar nele e sair da sessão."""
    assert "grupo input" in FRASE and "saia da sessão" in FRASE
    assert "usermod -aG input" in FRASE


def test_abrir_sem_permissao_levanta_a_frase(monkeypatch: pytest.MonkeyPatch) -> None:
    """O ``PermissionError`` do evdev sai como ``SemPermissaoDeLerError``, ainda um
    ``PermissionError``, e o texto dele é a frase do que fazer."""
    monkeypatch.setattr(evdev, "InputDevice", _recusar)
    with pytest.raises(maquina.SemPermissaoDeLerError) as erro:
        maquina.abrir_o_aparelho_de_entrada("event7")
    assert isinstance(erro.value, PermissionError)
    assert str(erro.value) == FRASE
    assert erro.value.filename == "/dev/input/event7"


def test_o_gesto_falha_o_clique_com_a_frase_do_dono(
        a08: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """O «Esperar a próxima tecla» recusa com a frase do dono, pela abertura real e por um
    ``PermissionError`` cru de quem abre no lugar dela."""
    _cena(a08, monkeypatch, _declarado())
    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(_sys_de_mentira(tmp_path / "input")))
    monkeypatch.setattr(evdev, "InputDevice", _recusar)
    a08.usar_como_botoes(None, {"alvo": CHAVE}, None)
    for abrir in (None, lambda evento: _recusar(f"/dev/input/{evento}")):
        monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", abrir)
        with pytest.raises(RuntimeError) as erro:
            a08.acionador_nova_tecla(None, {}, None)
        assert str(erro.value) == FRASE
        assert a08._o_rascunho().esperando is False


def _ponte(tmp_path: Path, abrir: Any) -> gp.PonteDosAcionadores:
    agora = iter(float(n) * 60 for n in range(100))
    return gp.PonteDosAcionadores(raiz=_sys_de_mentira(tmp_path / "input"), abrir=abrir,
                                  relogio=lambda: next(agora))


def _declarados() -> dict[str, Any]:
    return dict(_declarado().acionadores)


def test_a_ponte_diz_a_frase_em_warning_uma_vez_por_aparelho(tmp_path: Path) -> None:
    """Três procuras sem permissão: um ``warning`` com a frase e o aparelho, e nenhum ``info``
    de «não abriu» por cima."""
    ponte = _ponte(tmp_path, lambda evento: _recusar(f"/dev/input/{evento}"))
    with structlog.testing.capture_logs() as diario:
        for _ in range(3):
            ponte.andar(_declarados(), lambda: False)
    ponte.parar()
    avisos = [d for d in diario if d.get("event") == "acionador_sem_permissao"]
    assert len(avisos) == 1, diario
    assert avisos[0]["log_level"] == "warning"
    assert avisos[0]["frase"] == FRASE and avisos[0]["nome"] == NOME
    assert not [d for d in diario if d.get("event") == "acionador_nao_abriu"]


def test_a_ponte_volta_a_dizer_depois_que_o_aparelho_abriu(tmp_path: Path) -> None:
    """Liberado, o aparelho abre e a lembrança se apaga: se ele sai da porta e volta sem
    permissão, a frase volta ao diário. O que não é permissão continua em ``info``."""
    estado: dict[str, Any] = {"recusa": PermissionError(13, "Permission denied"), "saiu": False}

    class _Aberto:
        def read_one(self) -> Any:
            if estado["saiu"]:
                raise OSError(19, "No such device")
            return None

        def close(self) -> None:
            pass

    def abrir(evento: str) -> Any:
        if estado["recusa"] is not None:
            raise estado["recusa"]
        return _Aberto()

    ponte = _ponte(tmp_path, abrir)
    passos: tuple[tuple[dict[str, Any], str], ...] = (
        ({"recusa": None}, "acionador_aberto"),
        ({"saiu": True, "recusa": PermissionError(13, "Permission denied")}, "acionador_saiu"),
        ({}, "acionador_sem_permissao"),
        ({"recusa": OSError(19, "No such device")}, "acionador_nao_abriu"),
    )
    with structlog.testing.capture_logs() as diario:
        ponte.andar(_declarados(), lambda: False)
        for muda, _ in passos:
            estado.update(muda)
            ponte.andar(_declarados(), lambda: False)
    ponte.parar()
    eventos = [d["event"] for d in diario]
    assert eventos == ["acionador_sem_permissao", *(e for _, e in passos)], eventos
