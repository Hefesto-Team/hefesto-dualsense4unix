"""O-BOTAO-ENTREGA-O-QUE-PROMETE-01 — a camada 1 tem caminho até o aparelho.

**O DEFEITO QUE ESTE ARQUIVO EXISTE PARA MATAR, medido com o ouvido dela** —
20/09/2026, 04:30. Os quatro DualSense estavam com o botão do meio da fileira
da saída de som aceso, e um tom contínuo no sink padrão saiu **só na TV**:

    TEM SOM  0.349976  alsa_output.pci-....hdmi-stereo.monitor
    (as quatro pontes `hefesto_som_*`, os quatro endpoints de háptica,
     o sink USB do controle no cabo: 0,000000)

Palavra dela: *"so saiu na tv."*

A CAUSA NÃO ERA O APARELHO. O botão gravava `speaker.fonte = "mix"` no PERFIL,
e o único leitor daquela escolha no daemon é
`AltoFalanteSubsystem._fontes_do_perfil`, que lê o perfil **ATIVO**. Sem perfil
ativo — ou antes de o "Salvar" acontecer — a resposta honesta dele é `{}`, cada
nó fica com `FONTE_PADRAO`, e o clique dela não move uma nota de som.

A CURA É UM CAMINHO NOVO, NÃO UM SEGUNDO DONO: `speaker.set` passou a aceitar
`fonte`, o subsystem guarda a escolha VIVA e ela vence o perfil. O perfil
continua sendo onde a escolha DURA — as duas gravações não competem, porque a
de sessão é memória e a de disco é registro.

O QUE ESTE ARQUIVO NÃO MEDE: o ouvido. Nenhuma linha daqui fala com o servidor
de som — o subsystem roda sem thread, sem `pactl` e sem backend.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    FONTE_MIX,
    FONTE_PADRAO,
    FONTE_SFX,
)

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


class _Backend:
    """Backend de papel: só o que `_handle_speaker_set` toca."""

    def __init__(self) -> None:
        self.escritas: list[dict[str, Any]] = []

    def set_speaker_volume(self, volume: Any, **k: Any) -> bool:
        self.escritas.append({"volume": volume, **k})
        return True

    def speaker_state_for(self, uniq: Any) -> dict[str, Any]:
        return {"volume": 102, "muted": False}


class _Handlers(IpcHandlersMixin):
    """O bastante do mixin para chamar `_handle_speaker_set`."""

    def __init__(self, sub: Any) -> None:
        self.controller = _Backend()  # type: ignore[assignment]
        self.store = SimpleNamespace(active_profile=None)  # type: ignore[assignment]
        self.daemon = SimpleNamespace(_alto_falante_subsystem=sub)  # type: ignore[assignment]


@pytest.fixture
def sub() -> AltoFalanteSubsystem:
    """O subsystem SEM subir nada: a escolha da fonte não precisa de thread."""
    return AltoFalanteSubsystem()


def _pedir(h: _Handlers, **params: Any) -> dict[str, Any]:
    return asyncio.run(h._handle_speaker_set(params))


def test_o_ipc_leva_a_fonte_ao_dono_do_no(sub: AltoFalanteSubsystem) -> None:
    """`speaker.set {uniq, fonte}` muda o que o nó DAQUELE controle vai ouvir."""
    h = _Handlers(sub)
    assert sub.fonte_escolhida(P1) == FONTE_PADRAO

    corpo = _pedir(h, uniq=P1, fonte=FONTE_MIX)

    assert corpo["status"] == "ok"
    assert corpo["fonte"] == FONTE_MIX
    assert sub.fonte_escolhida(P1) == FONTE_MIX


def test_a_fonte_e_de_um_controle_so(sub: AltoFalanteSubsystem) -> None:
    """Escolher para o P1 não põe o som da máquina no ouvido do P2."""
    h = _Handlers(sub)
    _pedir(h, uniq=P1, fonte=FONTE_MIX)

    assert sub.fonte_escolhida(P1) == FONTE_MIX
    assert sub.fonte_escolhida(P2) == FONTE_PADRAO


def test_sem_endereco_ninguem_escolhe(sub: AltoFalanteSubsystem) -> None:
    """`fonte` sem `uniq` não vira uma escolha no primário."""
    h = _Handlers(sub)
    corpo = _pedir(h, fonte=FONTE_MIX)

    assert corpo["status"] == "sem_controle"
    assert "fonte" not in corpo
    assert sub.fonte_escolhida(P1) == FONTE_PADRAO


def test_um_pedido_so_de_fonte_nao_toma_a_posse(sub: AltoFalanteSubsystem) -> None:
    """A camada 1 não escreve byte nenhum no aparelho — é a armadilha 1 da SOM-02."""
    h = _Handlers(sub)
    _pedir(h, uniq=P1, fonte=FONTE_MIX)

    assert h.controller.escritas == [], (
        f"a fonte escreveu no aparelho: {h.controller.escritas}")


def test_a_fonte_viaja_junto_do_volume(sub: AltoFalanteSubsystem) -> None:
    """Pedir os dois no mesmo payload faz os dois — e a resposta diz os dois."""
    h = _Handlers(sub)
    corpo = _pedir(h, uniq=P1, fonte=FONTE_MIX, volume=102)

    assert corpo["status"] == "ok" and corpo["fonte"] == FONTE_MIX
    assert h.controller.escritas and h.controller.escritas[0]["volume"] == 102


@pytest.mark.parametrize("valor", ["hdmi", "", "MIX", 2, True, None.__class__])
def test_valor_que_o_no_nao_sabe_tratar_nao_passa(
    sub: AltoFalanteSubsystem, valor: Any
) -> None:
    """Só `mix` e `sfx`, e o erro é de VALIDAÇÃO, não clamp."""
    h = _Handlers(sub)
    with pytest.raises(ValueError, match="'fonte' precisa ser"):
        _pedir(h, uniq=P1, fonte=valor)


def test_a_lista_fechada_sai_do_dono_e_nao_da_regua(sub: AltoFalanteSubsystem) -> None:
    """Os dois nomes que o IPC aceita são os do `alto_falante_bt`, não literais."""
    h = _Handlers(sub)
    for nome in (FONTE_MIX, FONTE_SFX):
        assert _pedir(h, uniq=P1, fonte=nome)["fonte"] == nome


def test_release_nao_se_mistura_com_fonte(sub: AltoFalanteSubsystem) -> None:
    """"Pare de mandar E escolha isto" não tem significado honesto."""
    h = _Handlers(sub)
    with pytest.raises(ValueError, match="release"):
        _pedir(h, uniq=P1, release=True, fonte=FONTE_MIX)


def test_a_escolha_viva_vence_o_perfil(
    sub: AltoFalanteSubsystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com o perfil dizendo `sfx`, o clique de agora vale `mix`."""
    chave = P1.replace(":", "")
    monkeypatch.setattr(sub, "_fontes_do_perfil", lambda: {chave: FONTE_SFX})
    assert sub.fonte_escolhida(P1) == FONTE_SFX

    h = _Handlers(sub)
    _pedir(h, uniq=P1, fonte=FONTE_MIX)

    assert sub.fonte_escolhida(P1) == FONTE_MIX


def test_sem_escolha_viva_o_perfil_continua_mandando(
    sub: AltoFalanteSubsystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caminho novo não atropela o antigo: quem não clicou lê o perfil."""
    chave = P2.replace(":", "")
    monkeypatch.setattr(sub, "_fontes_do_perfil", lambda: {chave: FONTE_MIX})

    h = _Handlers(sub)
    _pedir(h, uniq=P1, fonte=FONTE_SFX)

    assert sub.fonte_escolhida(P2) == FONTE_MIX


def test_um_daemon_sem_o_subsystem_responde_em_vez_de_quebrar() -> None:
    """Ausência é resposta — a mesma disciplina de todo o bloco de áudio."""
    h = _Handlers(None)
    corpo = _pedir(h, uniq=P1, fonte=FONTE_MIX)

    assert corpo["status"] == "sem_controle" and "fonte" not in corpo


class _SemVolumeConhecido(_Backend):
    """O controle que nunca recebeu um `speaker.set` de volume."""

    def speaker_state_for(self, uniq: Any) -> dict[str, Any] | None:
        return None


def test_a_recusa_da_posse_nao_leva_a_escolha_da_camada_1_junto(
    sub: AltoFalanteSubsystem,
) -> None:
    """Ela escolhe a fonte e o mudo no mesmo clique; o mudo é recusado."""
    h = _Handlers(sub)
    h.controller = _SemVolumeConhecido()  # type: ignore[assignment]

    with pytest.raises(ValueError, match="sem volume conhecido"):
        _pedir(h, uniq=P1, fonte=FONTE_MIX, muted=True)

    assert sub.fonte_escolhida(P1) == FONTE_MIX, (
        "a recusa da posse do volume levou a escolha da camada 1 junto")
    assert h.controller.escritas == [], (
        f"o pedido recusado escreveu no aparelho assim mesmo: "
        f"{h.controller.escritas}")


def test_o_byte_recusado_tambem_nao_leva_a_fonte(
    sub: AltoFalanteSubsystem,
) -> None:
    """O firmware diz não; o nó continua ouvindo o que ela escolheu."""

    class _Recusa(_Backend):
        def set_speaker_volume(self, volume: Any, **k: Any) -> bool:
            self.escritas.append({"volume": volume, **k})
            return False

    h = _Handlers(sub)
    h.controller = _Recusa()  # type: ignore[assignment]

    corpo = _pedir(h, uniq=P1, fonte=FONTE_MIX, volume=102, rota=3)

    assert corpo["status"] == "sem_controle", "a cena não reproduz a recusa"
    assert corpo["fonte"] == FONTE_MIX, (
        f"a resposta escondeu a camada 1 que ficou valendo: {corpo}")
    assert sub.fonte_escolhida(P1) == FONTE_MIX


def test_um_valor_de_fonte_recusado_para_antes_de_tocar_o_aparelho(
    sub: AltoFalanteSubsystem,
) -> None:
    """A validação da `fonte` é ANTES de qualquer escrita, e não depois."""
    h = _Handlers(sub)

    with pytest.raises(ValueError, match="'fonte' precisa ser"):
        _pedir(h, uniq=P1, fonte="hdmi", volume=102)

    assert h.controller.escritas == [], (
        f"o volume foi aplicado sob um pedido que o handler recusou: "
        f"{h.controller.escritas}")
