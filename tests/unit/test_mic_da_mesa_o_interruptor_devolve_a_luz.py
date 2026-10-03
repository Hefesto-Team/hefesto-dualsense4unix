"""Desligar o botão do mic DEVOLVE a luz ao kernel — a prosa vira ato."""

from __future__ import annotations

from typing import Any

import pytest


class _Backend:
    """Backend da mesa: guarda o que lhe pediram no `common[8]`, por controle."""

    def __init__(self, uniqs: tuple[str, ...], *, com_endereco: bool = True) -> None:
        self._uniqs = uniqs
        self._com_endereco = com_endereco
        self.posse: list[tuple[Any, Any]] = []

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u} for u in self._uniqs]

    def set_microphone_led(self, aceso: bool | None, *, uniq: str | None = None) -> None:
        if not self._com_endereco and uniq is not None:
            raise TypeError("backend antigo não aceita `uniq`")
        self.posse.append((aceso, uniq))


class _Config:
    mic_button_toggles_system = True


class _Daemon:
    def __init__(self, backend: _Backend) -> None:
        self.controller = backend
        self.config = _Config()


_J1 = "aabbcc000011"
_J2 = "aabbcc000022"


def test_desligar_o_interruptor_devolve_a_posse_de_cada_controle() -> None:
    """CURA A ARRANCAR: o `devolver_a_luz_ao_kernel` do applier."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    backend = _Backend((_J1, _J2))
    daemon = _Daemon(backend)
    applier = DraftApplier.__new__(DraftApplier)
    applier.daemon = daemon  # type: ignore[assignment]

    applier._apply_mic({"button_toggles_system": False})

    assert daemon.config.mic_button_toggles_system is False
    assert backend.posse == [(None, _J1), (None, _J2)], (
        "desligar o interruptor tem de devolver o `common[8]` de TODOS os "
        f"controles da mesa ao kernel: {backend.posse}"
    )


def test_ligar_o_interruptor_nao_devolve_nada() -> None:
    """A metade que prova que a cura não é "devolve sempre"."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    backend = _Backend((_J1,))
    daemon = _Daemon(backend)
    daemon.config.mic_button_toggles_system = False
    applier = DraftApplier.__new__(DraftApplier)
    applier.daemon = daemon  # type: ignore[assignment]

    applier._apply_mic({"button_toggles_system": True})

    assert daemon.config.mic_button_toggles_system is True
    assert backend.posse == []


def test_desligar_o_que_ja_estava_desligado_nao_mexe_no_aparelho() -> None:
    """Só a TRANSIÇÃO devolve. Um perfil que repete o valor não fala com o mic."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    backend = _Backend((_J1,))
    daemon = _Daemon(backend)
    daemon.config.mic_button_toggles_system = False
    applier = DraftApplier.__new__(DraftApplier)
    applier.daemon = daemon  # type: ignore[assignment]

    applier._apply_mic({"button_toggles_system": False})

    assert backend.posse == []


def test_backend_sem_endereco_degrada_declarado_e_nao_calado() -> None:
    """O dublê/backend antigo sem `uniq` cai para a chamada global — e loga."""
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import devolver_a_luz_ao_kernel

    backend = _Backend((_J1, _J2), com_endereco=False)
    daemon = _Daemon(backend)

    quantos = devolver_a_luz_ao_kernel(daemon)  # type: ignore[arg-type]

    assert quantos == 2
    assert backend.posse == [(None, None), (None, None)]


def test_o_applier_devolve_a_luz_ao_kernel_ao_desligar_o_interruptor() -> None:
    """O applier chama `devolver_a_luz_ao_kernel`: a promessa do interruptor."""
    from hefesto_dualsense4unix.daemon import ipc_draft_applier

    codigo = ipc_draft_applier.DraftApplier._apply_mic.__code__
    assert "devolver_a_luz_ao_kernel" in codigo.co_names, (
        "o applier parou de devolver a posse ao desligar o interruptor"
    )


@pytest.mark.parametrize("valor", ["sim", 1, 0])
def test_valor_que_nao_e_booleano_continua_recusado(valor: Any) -> None:
    """A cura não pode ter afrouxado a validação do campo."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    backend = _Backend((_J1,))
    daemon = _Daemon(backend)
    applier = DraftApplier.__new__(DraftApplier)
    applier.daemon = daemon  # type: ignore[assignment]

    with pytest.raises(ValueError, match="booleano"):
        applier._apply_mic({"button_toggles_system": valor})
    assert backend.posse == []


def test_a_secao_sem_opiniao_sobre_o_botao_nao_mexe_em_nada() -> None:
    """`None` é "o rascunho não fala do campo" — nem config, nem aparelho."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

    backend = _Backend((_J1,))
    daemon = _Daemon(backend)
    applier = DraftApplier.__new__(DraftApplier)
    applier.daemon = daemon  # type: ignore[assignment]

    applier._apply_mic({})

    assert daemon.config.mic_button_toggles_system is True
    assert backend.posse == []


def test_backend_sem_o_metodo_recusa_dizendo_em_vez_de_sair_calado() -> None:
    """MEDIDO na auditoria: o dublê da suíte NÃO tem `set_microphone_led`.

    Nem `core/controller.IController` nem
    `testing/fake_controller.FakeController` declaram o método — só o
    `PyDualSenseController`. Num daemon dublado a devolução simplesmente não
    acontece, e sair calado daqui faria o log dizer que a luz voltou ao kernel
    quando ela não voltou. O aviso `mic_da_mesa_posse_sem_backend` é o que
    separa "não havia o que devolver" de "não consegui devolver".

    Isto NÃO conserta a divergência interface/dublê — ela é dívida ANOTADA na
    auditoria de 02/09/2026, e fechá-la muda a assinatura de `set_mic_led` em
    três arquivos. Esta régua fixa o que é verdade hoje e reprova quando alguém
    mudar, para a próxima pessoa reencontrar a dívida em vez de tropeçar nela.
    """
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import devolver_a_luz_ao_kernel
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    assert not hasattr(IController, "set_microphone_led"), (
        "a interface ganhou o método — reveja esta régua e a dívida que ela cita"
    )
    assert not hasattr(FakeController, "set_microphone_led")

    class _Mudo:
        def describe_controllers(self) -> list[dict[str, Any]]:
            return [{"uniq": _J1}]

    daemon = _Daemon(_Mudo())  # type: ignore[arg-type]
    assert devolver_a_luz_ao_kernel(daemon) == 0  # type: ignore[arg-type]
