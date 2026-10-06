"""A-MESMA-LINGUA-01 — o número da carta é o número que vai no nome do vpad.

Decisão, 07/09/2026, em cinco palavras: *"precisamos que falem a mesma
língua."*

O DEFEITO, medido na bancada no mesmo dia com os QUATRO DualSense na mesa
(`daemon.state_full`, os quatro itens de `coop.mesa`) — e era **4 de 4**,
nenhum acerto por sorte:

    | aparelho                | carta | nome do vpad | nome_divergente |
    |-------------------------|-------|--------------|-----------------|
    | Cosmic Red (cabo, P1)   | 2     | `Hefesto P1` | true            |
    | Starlight Blue (rádio)  | 4     | `Hefesto P3` | true            |
    | Galactic Purple (rádio) | 1     | `Hefesto P4` | true            |
    | White (cabo)            | 3     | `Hefesto P2` | true            |

O `state_full` publicava o alarme nos quatro desde a QUEM-É-QUEM-01/E3: a casa
SABIA e o produto não fazia.

A MORDIDA GERAL, e ela é a de todo teste daqui: **devolver o `player_index` ao
lugar do número da carta reprova**. Cada teste diz a sua na docstring.

O QUE ESTE ARQUIVO NÃO PROMETE, e está escrito para ninguém concluir demais:
o nome não se corrige VIVO. O nó uhid recebe o nome em `UHID_CREATE2` e o ABI
do kernel não tem operação de renomear; o uinput leva o nome no `UI_DEV_SETUP`
antes do `UI_DEV_CREATE`. Renomear é derrubar e recriar o nó — e é por isso que
o `nome_divergente` continua existindo, agora significando uma coisa só: *a
fila andou depois que este vpad nasceu*.

ENDEREÇOS: nada de MAC real. Os físicos usam a faixa forjada da casa
(`aa:bb:cc`) e os vpads, a faixa localmente administrada do próprio produto
(`02:fe:...`).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac, vpad_mac

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"

FILA = {P1: 2, P2: 4, P3: 1, P4: 3}


class _VpadDublado:
    """Só o que a mesa lê de um vpad. `player` é o inteiro que o produto"""

    def __init__(self, jogador: int, identidade: str | None = None) -> None:
        self.backend = "uhid"
        self.player = jogador
        self.flavor = "dualsense"
        self.mac = vpad_mac(identidade, jogador)
        self.name = f"DualSense Wireless Controller (Hefesto P{jogador})"


def _jogador(mac: str, indice: int, *, vpad: Any = None) -> _SecondaryPlayer:
    return _SecondaryPlayer(
        identity=mac,
        evdev_path=f"/dev/input/event{20 + indice}",
        reader=SimpleNamespace(grab_state="held"),  # type: ignore[arg-type]
        player_index=indice,
        vpad=vpad,
    )


def _daemon_dublado(vpad_p1: Any = None, *, fila: dict[str, int] | None = None) -> Any:
    registro = (
        SimpleNamespace(slot_for=lambda mac, assign=False: (fila or {}).get(mac))
        if fila is not None
        else None
    )
    return SimpleNamespace(
        controller=SimpleNamespace(
            primary_uniq=P1,
            _evdev=SimpleNamespace(_device_path="/dev/input/event20"),
        ),
        _gamepad_device=vpad_p1,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        identity_registry=registro,
    )


def _mesa_de_quatro(*, fila: dict[str, int] | None = FILA) -> CoopManager:
    """A bancada: o primário + três secundários já sentados, com o"""
    mgr = CoopManager(_daemon_dublado(_VpadDublado(1, P1), fila=fila))  # type: ignore[arg-type]
    for indice, mac in enumerate((P2, P3, P4), start=2):
        mgr._players[mac] = _jogador(mac, indice)
    return mgr


class TestONomeDoVpadPerguntaAFila:
    def test_o_numero_do_nome_e_o_da_carta_nos_quatro(self) -> None:
        """A MORDIDA CENTRAL, e ela é a bancada inteira."""
        mgr = _mesa_de_quatro()

        nomes = {
            mac: mgr.numero_para_o_nome(mac, jogador.player_index)
            for mac, jogador in mgr._players.items()
        }
        assert nomes == {P2: 4, P3: 1, P4: 3}, "o nome fala a língua da carta"

    def test_o_numero_do_nome_e_o_mesmo_inteiro_que_a_carta_publica(self) -> None:
        """Não basta acertar por fora: tem de ser a MESMA função."""
        mgr = _mesa_de_quatro()
        publicado = {i["uniq"]: i["player"] for i in mgr.mesa() if not i["is_primary"]}
        no_nome = {
            mac: mgr.numero_para_o_nome(mac, j.player_index)
            for mac, j in mgr._players.items()
        }

        assert no_nome == publicado

    def test_sem_fila_o_historico_fica_intacto(self) -> None:
        """FakeController, backend legado, dublê: sem registro de identidade"""
        mgr = _mesa_de_quatro(fila=None)

        nomes = {
            mac: mgr.numero_para_o_nome(mac, j.player_index)
            for mac, j in mgr._players.items()
        }
        assert nomes == {P2: 2, P3: 3, P4: 4}

    def test_fila_que_responde_lixo_cai_no_fallback(self) -> None:
        """Um registro que devolve `None`, `0`, `True` ou texto não pode"""
        for resposta in (None, 0, -1, True, "2", 2.0):
            mgr = _mesa_de_quatro(fila=None)
            mgr._daemon.identity_registry = SimpleNamespace(  # type: ignore[attr-defined]
                slot_for=lambda mac, assign=False, _r=resposta: _r
            )
            assert mgr.numero_para_o_nome(P2, 2) == 2, f"resposta {resposta!r}"


class TestAPromocaoNasceComONomeCerto:
    def _promover(self, mgr: CoopManager, mac: str, monkeypatch: Any) -> dict[str, Any]:
        """Promove UM jogador e devolve os kwargs que a factory recebeu."""
        capturado: dict[str, Any] = {}

        def _factory(flavor: str, **kwargs: Any) -> Any:
            capturado.update(kwargs)
            capturado["flavor"] = flavor
            return _VpadDublado(kwargs["player"], kwargs.get("identity"))

        import hefesto_dualsense4unix.integrations.virtual_pad as vp

        monkeypatch.setattr(vp, "make_virtual_pad", _factory)
        monkeypatch.setattr(mgr, "_calibration_pronta", lambda _i: (True, None))
        monkeypatch.setattr(mgr, "_start_player_motion_reader", lambda _p: None)
        monkeypatch.setattr(mgr, "_materialize_launch_env", lambda: None)
        monkeypatch.setattr(mgr, "_broker_hide_player", lambda _p: None)
        mgr._promote_player(mgr._players[mac])
        return capturado

    def test_o_vpad_nasce_com_o_numero_da_carta(self, monkeypatch: Any) -> None:
        """A MORDIDA do caminho de produção: não é a função auxiliar que"""
        mgr = _mesa_de_quatro()
        kwargs = self._promover(mgr, P2, monkeypatch)

        assert kwargs["player"] == 4, "o inteiro que vira o nome é o da carta"
        assert mgr._players[P2].vpad is not None
        assert mgr._players[P2].vpad.name.endswith("(Hefesto P4)")

    def test_o_indice_de_alocacao_sobrevive_inteiro(self, monkeypatch: Any) -> None:
        """CURA EXAGERADA REPROVA AQUI. O `player_index` não podia morrer: ele"""
        mgr = _mesa_de_quatro()
        self._promover(mgr, P2, monkeypatch)

        assert mgr._players[P2].player_index == 2, "a alocação não se mexe"
        assert sorted(p.player_index for p in mgr._players.values()) == [2, 3, 4]
        assert mgr._next_player_index() == 5, "o poço continua contíguo"

    def test_o_endereco_do_vpad_nao_se_move_com_o_numero(self, monkeypatch: Any) -> None:
        """A prova de que esta cura troca o NOME **e mais nada**."""
        mgr = _mesa_de_quatro()
        kwargs = self._promover(mgr, P2, monkeypatch)

        assert kwargs["identity"] == P2
        assert vpad_mac(P2, 4) == vpad_mac(P2, 2), "o endereço segue o APARELHO"
        assert mgr._players[P2].vpad.mac == vpad_mac(P2, 4)
        assert mgr._players[P2].vpad.mac != player_mac(4), "não é o do número"


class TestOPrimarioTambemFalaALingua:
    """*"Quando a cura conhece a causa, ela cobre TODOS os chamadores."*"""

    def test_o_numero_do_primario_e_o_da_carta(self) -> None:
        """A fila desta mesa põe o primário em 2 — ser primário é função da"""
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            numero_do_nome_do_primario,
        )

        mgr = _mesa_de_quatro()
        mgr._daemon._coop_manager = mgr

        assert numero_do_nome_do_primario(mgr._daemon) == 2

    def test_o_inteiro_chega_a_factory_do_p1(self, monkeypatch: Any) -> None:
        """A MORDIDA DO CALL SITE, e ela existe porque a primeira versão deste"""
        from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            start_gamepad_emulation,
        )

        chamadas: list[dict[str, Any]] = []

        def _factory(flavor: str | None, **kwargs: Any) -> Any:
            chamadas.append({"flavor": flavor, **kwargs})
            return _VpadDublado(kwargs["player"], kwargs.get("identity"))

        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            _factory,
        )
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        monkeypatch.setattr(gamepad_mod, "_materialize_launch_env", lambda *_a: None)
        monkeypatch.setattr(gamepad_mod, "start_motion_reader", lambda *_a: None)
        monkeypatch.setattr(gamepad_mod, "read_primary_calibration", lambda *_a: None)

        mgr = _mesa_de_quatro()
        daemon = mgr._daemon
        daemon._coop_manager = mgr
        daemon._gamepad_device = None
        daemon._mouse_device = None
        daemon.store = None
        daemon.config.gamepad_emulation_enabled = False
        daemon.config.rumble_active = None
        daemon.controller._desired = SimpleNamespace(player_leds=None)
        daemon.controller.set_player_leds = lambda _bits: None
        daemon.controller.hidraw_path = lambda uniq=None: "/dev/hidraw4"

        start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")

        assert len(chamadas) == 1, "o P1 nasceu uma vez"
        assert chamadas[0]["player"] == 2, "o nó do P1 nasce `Hefesto P2`"
        assert daemon._gamepad_device.name.endswith("(Hefesto P2)")

    def test_sem_manager_ou_sem_mac_a_resposta_e_o_valor_de_sempre(self) -> None:
        """O ENCAIXE QUE TORNA A CURA SEGURA, e ele merece um teste próprio."""
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            numero_do_nome_do_primario,
        )

        assert numero_do_nome_do_primario(_daemon_dublado(fila=FILA)) == 1

        mgr = _mesa_de_quatro()
        mgr._daemon.controller.primary_uniq = None
        mgr._daemon._coop_manager = mgr
        assert numero_do_nome_do_primario(mgr._daemon) == 1

    def test_manager_que_explode_nao_derruba_a_partida_do_vpad(self) -> None:
        """Um rótulo não pode impedir o controle de nascer."""
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            numero_do_nome_do_primario,
        )

        mgr = _mesa_de_quatro()
        mgr._daemon._coop_manager = mgr
        mgr._daemon.identity_registry = SimpleNamespace(  # type: ignore[attr-defined]
            slot_for=lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        assert numero_do_nome_do_primario(mgr._daemon) == 1


class TestOAlarmeDeNomeVelho:
    def test_com_o_nome_nascido_certo_o_alarme_cala(self) -> None:
        """Alarme que acende sempre não é alarme."""
        mgr = _mesa_de_quatro()
        mgr._daemon._gamepad_device = _VpadDublado(FILA[P1], P1)
        for mac, jogador in mgr._players.items():
            jogador.vpad = _VpadDublado(FILA[mac], mac)

        assert [i["nome_divergente"] for i in mgr.mesa()] == [False] * 4

    def test_o_alarme_acende_quando_a_fila_anda_depois_do_nascimento(self) -> None:
        """O QUE A CURA NÃO ALCANÇA, dito em voz alta."""
        mgr = _mesa_de_quatro()
        for mac, jogador in mgr._players.items():
            jogador.vpad = _VpadDublado(FILA[mac], mac)
        mgr._daemon.identity_registry = SimpleNamespace(  # type: ignore[attr-defined]
            slot_for=lambda mac, assign=False: {P1: 1, P2: 3, P3: 2, P4: 4}.get(mac)
        )

        item = next(i for i in mgr.mesa() if i["uniq"] == P3)
        assert item["player"] == 2, "a carta já anda"
        assert item["vpad_indice"] == 1, "o nome ficou no nascimento"
        assert item["nome_divergente"] is True
