"""O gatilho de um controle só vibra ele (O-GATILHO-DE-UM-CONTROLE-SO-VIBRA-ELE-01).

Quatro DualSense, o estilo souls com o Eco e o Ressoar em todos. O motor do
tato vivo lê o gatilho de cada um pelo leitor dele. Com jogo, o R2 de um
controle escreve só nos motores dele; sem jogo, o tato não escreve em nenhum
outro. No Modo Xbox e no Modo DualSense, de P1 a P4 e com dois apertos ao
mesmo tempo.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import formas_de_haptica
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

QUATRO = ("aa:bb:cc:00:00:41", "aa:bb:cc:00:00:42", "02:fe:00:00:00:43", "02:fe:00:00:00:44")
_QUADROS = 40
_APERTO = range(8, 28)


class Gravador:
    """Anota cada escrita por controle que o motor faz no backend e no alto-falante."""

    def __init__(self, primary_uniq: str | None = None) -> None:
        self.primary_uniq = primary_uniq
        self.escritas: list[tuple[str, str]] = []

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith("_"):
            raise AttributeError(nome)

        def escrever(uniq: str, *_a: Any, **_k: Any) -> bool:
            self.escritas.append((nome, uniq))
            return True

        return escrever


class Mesa:
    """O daemon com quatro controles: P1 pelo estado do primário, P2 a P4 pelo co-op."""

    def __init__(self, backend: str, jogo: bool) -> None:
        self.controller = Gravador(QUATRO[0])
        self.alto_falante = Gravador()
        self.alto_falante.rota_do_padrao = lambda _uniq: "motor"
        self.gatilhos = {u: SimpleNamespace(l2_raw=0, r2_raw=0) for u in QUATRO}
        pads = {u: SimpleNamespace(backend=backend, game_open=False, visto_ha_s={})
                for u in QUATRO}
        jogadores = {
            u: SimpleNamespace(
                reader=SimpleNamespace(snapshot=lambda u=u: self.gatilhos[u]),
                vpad=pads[u], motion_reader=None)
            for u in QUATRO[1:]
        }
        self.daemon = SimpleNamespace(
            controller=self.controller,
            _last_state=self.gatilhos[QUATRO[0]],
            _gamepad_device=pads[QUATRO[0]],
            _motion_reader=None,
            _coop_manager=SimpleNamespace(_players=jogadores),
            store=SimpleNamespace(active_profile="Souls"),
            display_authority="game" if jogo else "unknown",
            _alto_falante_subsystem=self.alto_falante,
        )
        self.motor = tv.TatoVivo(tv.atuadores_de_producao(self.daemon))
        self.daemon._tato_vivo = self.motor
        self.passo = tv.Passo(self.daemon, self.motor)

    def apertar_o_r2(self, *quem: str) -> set[str]:
        agora = 0.0
        for quadro in range(_QUADROS):
            for uniq in quem:
                self.gatilhos[uniq].r2_raw = 255 if quadro in _APERTO else 0
            self.passo(agora)
            agora += tv.INTERVALO_S
        return {uniq for canal, uniq in self.controller.escritas + self.alto_falante.escritas
                if not canal.startswith("resolved_")}

    def com_motor(self) -> set[str]:
        return {uniq for canal, uniq in self.controller.escritas if canal == "set_rumble_for"}


@pytest.fixture(autouse=True)
def _perfil_souls(monkeypatch: pytest.MonkeyPatch) -> None:
    receita = tv.receita_do_estilo(POR_CHAVE["souls"])
    macs = [norm_mac(u) or u for u in QUATRO]
    monkeypatch.setattr(tv, "receita_ativa", lambda _d: receita)
    monkeypatch.setattr(tv, "estilo_ativo", lambda _d: "souls")
    monkeypatch.setattr(tv, "escolhas_ativas",
                        lambda _d: dict.fromkeys(macs, formas_de_haptica.ECO))
    monkeypatch.setattr(tv, "escolhas_de_imersao_ativas", lambda _d: dict.fromkeys(macs, "ressoar"))


_MODOS = pytest.mark.parametrize("backend", ["uinput", "uhid"], ids=["xbox", "dualsense"])
_QUEM = pytest.mark.parametrize("quem", range(4), ids=["p1", "p2", "p3", "p4"])


@_MODOS
@_QUEM
def test_com_jogo_o_r2_de_um_vibra_so_ele(backend: str, quem: int) -> None:
    mesa = Mesa(backend, jogo=True)
    escritos = mesa.apertar_o_r2(QUATRO[quem])
    assert mesa.com_motor() == {QUATRO[quem]}
    assert escritos == {QUATRO[quem]}


@_MODOS
@_QUEM
def test_sem_jogo_o_r2_de_um_nao_toca_os_outros(backend: str, quem: int) -> None:
    mesa = Mesa(backend, jogo=False)
    assert mesa.apertar_o_r2(QUATRO[quem]) <= {QUATRO[quem]}


@_MODOS
def test_dois_apertos_ao_mesmo_tempo_vibram_so_os_dois(backend: str) -> None:
    mesa = Mesa(backend, jogo=True)
    apertados = {QUATRO[1], QUATRO[3]}
    assert mesa.apertar_o_r2(*apertados) == apertados
    assert mesa.com_motor() == apertados


def test_o_gatilho_de_cada_controle_se_le_do_leitor_dele() -> None:
    mesa = Mesa("uinput", jogo=True)
    mesa.gatilhos[QUATRO[2]].r2_raw = 200
    lidos = {c.uniq: c.r2 for c in tv.controles_do_daemon(mesa.daemon)}
    assert lidos == {QUATRO[0]: 0, QUATRO[1]: 0, QUATRO[2]: 200, QUATRO[3]: 0}
