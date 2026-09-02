"""Desligar o botão do mic DEVOLVE a luz ao kernel — a prosa vira ato.

ACHADO DA AUDITORIA DE 02/09/2026. O comentário de `mic_button_toggles_system`
em `daemon/lifecycle.py` prometia, na versão da onda:

    *"Desligado, não elegemos e não acendemos: o kernel segue dono do mudo E da
    luz do próprio controle, que é o contrato de fábrica."*

A segunda metade era FALSA depois da primeira eleição. A posse do `common[8]`
é grudenta — ela só cai por `set_microphone_led(None)` —, e o ramo do
interruptor desligado (`hotkey.mic_button_loop`) fazia `continue`, sem devolver
nada. Medido sobre o `_build_common` desta árvore, antes da cura:

    1. de fabrica                   : flag1&0x01=0  common[8]=0  -> kernel
    2. depois de UMA eleicao ok     : flag1&0x01=1  common[8]=1  -> hefesto
    3. perfil desliga o interruptor : flag1&0x01=1  common[8]=1  -> hefesto
    4. so `mic led-release`         : flag1&0x01=0  common[8]=0  -> kernel

E o caminho é reentrante em RUNTIME: `daemon/ipc_draft_applier.py` escreve o
campo sem restart. A cena é real — ela joga, aperta o mic (LED aceso, posse
nossa), depois carrega um perfil de gravação com `mic.button_toggles_system:
false`. Daí em diante o botão físico não mexe mais na luz, e a luz fica
congelada no que a última eleição deixou. Havia porta de emergência
(`hefesto-dualsense4unix mic led-release`), mas ela é comando de terminal, e a
prosa prometia que não precisava dela.

DAS DUAS CURAS QUE SERVIAM — devolver a posse, ou reescrever a prosa — esta leva
fez as duas, e nesta ordem: o applier passou a devolver na transição
ligado -> desligado, e o comentário passou a dizer o que o código faz.
"""

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
    """CURA A ARRANCAR: o `devolver_a_luz_ao_kernel` do applier.

    Sem ele a luz fica congelada no que a última eleição deixou, e o botão
    físico já não a alcança.
    """
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
    """A metade que prova que a cura não é "devolve sempre".

    Ligar é o gesto de TOMAR o botão; devolver a posse ali apagaria a luz que a
    eleição seguinte vai acender, e por um instante o plástico mentiria ao
    contrário.
    """
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
    """O dublê/backend antigo sem `uniq` cai para a chamada global — e loga.

    "Degradou calado" é como esta casa fabrica o LED do controle errado; aqui a
    degradação existe, é declarada, e a posse ainda assim é devolvida.
    """
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import devolver_a_luz_ao_kernel

    backend = _Backend((_J1, _J2), com_endereco=False)
    daemon = _Daemon(backend)

    quantos = devolver_a_luz_ao_kernel(daemon)  # type: ignore[arg-type]

    assert quantos == 2
    assert backend.posse == [(None, None), (None, None)]


def test_a_prosa_do_interruptor_nao_promete_o_que_o_codigo_nao_faz() -> None:
    """A frase corrigida não pode voltar à versão que a auditoria derrubou.

    Esta régua guarda a PROSA porque foi a prosa que estava errada — e a casa
    trata fato errado como coisa que se substitui, não que se deixe ao lado do
    certo.

    Ela guarda pelo PONTEIRO, não por proibir a frase velha: o comentário
    corrigido CITA a frase derrubada para dizer que ela era falsa, e uma régua
    de substring negativa reprovaria justamente porque alguém explicou bem —
    a forma das onze réguas que caíram nesta casa em 26/08.

    CURA A ARRANCAR: tirar a chamada de `devolver_a_luz_ao_kernel` do applier —
    reprova aqui, e nas quatro réguas de comportamento acima.
    """
    import inspect

    from hefesto_dualsense4unix.daemon import ipc_draft_applier, lifecycle

    prosa = inspect.getsource(lifecycle)
    assert "devolver_a_luz_ao_kernel" in prosa, (
        "o comentário de `mic_button_toggles_system` perdeu o ponteiro para "
        "quem cumpre a promessa — sem ele a frase volta a ser fé"
    )

    codigo = ipc_draft_applier.DraftApplier._apply_mic.__code__
    assert "devolver_a_luz_ao_kernel" in codigo.co_names, (
        "o applier parou de devolver a posse ao desligar o interruptor — o "
        "comentário do `lifecycle.py` virou promessa falsa de novo"
    )


@pytest.mark.parametrize("valor", ["sim", 1, 0])
def test_valor_que_nao_e_booleano_continua_recusado(valor: Any) -> None:
    """A cura não pode ter afrouxado a validação do campo.

    E a recusa vem ANTES de qualquer conversa com o aparelho: um rascunho
    inválido não pode apagar a luz de ninguém no caminho de ser rejeitado.
    """
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
