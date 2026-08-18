"""QUEM-É-QUEM-01 — o produto diz qual vpad é alimentado por qual controle.

O defeito, medido na bancada de 15/08/2026 com os QUATRO controles dela na
mesa: o `state_full` publicava `coop.players` como um NÚMERO (4), e a pergunta
*"o vpad do jogador 2 é alimentado por qual controle físico?"* não tinha
resposta observável. Respondê-la custava apertar botão em cada controle —
quatro vezes, à mão. Está escrito com todas as letras em
`scripts/ensaios/quem_e_quem.py`: *"Nenhum arquivo de /sys carrega essa
ligação"*.

E o daemon SABIA o tempo todo: é o `CoopManager` que cria o vpad de cada
jogador a partir de um físico, e o par mora em `_SecondaryPlayer`. Era a casa
sabendo e o produto não fazendo — o defeito mais caro daqui.

A MORDIDA de cada teste está dita na docstring dele. A geral, e é a que o
título deste arquivo promete: **arrancar a lista e deixar só o número reprova
aqui**, em três níveis — no manager, no estado publicado e na tela.

ENDEREÇOS: nada de MAC real neste arquivo. Os físicos usam a faixa forjada da
casa (`aa:bb:cc`) e os vpads, a faixa localmente administrada que o próprio
produto carimba (`02:fe:...`, de `uhid_gamepad.player_mac`).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

#: Os quatro da mesa dela, na faixa FORJADA da casa (`check_anonymity.sh`) e
#: no formato REAL do payload: `norm_mac`, 12 dígitos hex sem separador — o
#: MESMO de `controllers[].uniq`. Escrevê-los com dois-pontos aqui esconderia
#: o fato que sustenta esta cura: é por a chave do `coop` sair no formato
#: idêntico ao do `controllers` que a GUI consegue casar card↔vpad.
P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"


class _VpadDublado:
    """Só o que a tabela lê de um vpad: backend, `mac` forjado, nome e o
    `player` de ALOCAÇÃO — o inteiro que o produto congela dentro dos dois."""

    def __init__(self, jogador: int, backend: str = "uhid") -> None:
        self.backend = backend
        self.player = jogador
        self.mac = player_mac(jogador) if backend == "uhid" else None
        self.name = f"DualSense Wireless Controller (Hefesto P{jogador})"


def _jogador(mac: str, indice: int, *, vpad: Any) -> _SecondaryPlayer:
    """Um secundário já sentado — o `reader` é dublê (nada aqui o consulta)."""
    return _SecondaryPlayer(
        identity=mac,
        evdev_path=f"/dev/input/event{20 + indice}",
        reader=SimpleNamespace(grab_state="held"),  # type: ignore[arg-type]
        player_index=indice,
        vpad=vpad,
    )


def _daemon_dublado(vpad_p1: Any = None) -> Any:
    return SimpleNamespace(
        controller=SimpleNamespace(
            primary_uniq=P1,
            _evdev=SimpleNamespace(_device_path="/dev/input/event20"),
        ),
        _gamepad_device=vpad_p1,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
    )


def _mesa_de_quatro() -> CoopManager:
    """O retrato da bancada: P1 primário + três secundários promovidos."""
    mgr = CoopManager(_daemon_dublado(_VpadDublado(1)))  # type: ignore[arg-type]
    for indice, mac in enumerate((P2, P3, P4), start=2):
        mgr._players[mac] = _jogador(mac, indice, vpad=_VpadDublado(indice))
    return mgr


# ---------------------------------------------------------------------------
# O manager responde a pergunta que só o botão respondia
# ---------------------------------------------------------------------------


class TestOManagerSabeDizerQuemAlimentaQuem:
    def test_cada_jogador_traz_o_mac_do_fisico_e_o_endereco_do_vpad(self) -> None:
        """A MORDIDA central: o par físico↔vpad, sem apertar botão nenhum.

        Arrancada a cura (`mesa` de volta a um número), não há de
        onde tirar estas quatro linhas — que é exatamente o estado de 15/08.
        """
        itens = _mesa_de_quatro().mesa()

        assert isinstance(itens, list), "número não responde 'quem'; lista responde"
        assert len(itens) == 4, "quatro na mesa, quatro linhas"
        pares = {item["uniq"]: item["vpad_uniq"] for item in itens}
        assert pares == {
            P1: player_mac(1),
            P2: player_mac(2),
            P3: player_mac(3),
            P4: player_mac(4),
        }, "cada físico ligado ao SEU vpad — a ligação que não era observável"

    def test_o_primario_sai_marcado_e_vem_do_vpad_do_daemon(self) -> None:
        """O P1 não é secundário do co-op: o vpad dele é o `_gamepad_device`.

        Sem esta linha, a tabela responderia só por P2+ — e a pergunta dela é
        sobre a mesa inteira.
        """
        itens = _mesa_de_quatro().mesa()

        primarios = [item for item in itens if item["is_primary"]]
        assert len(primarios) == 1
        assert primarios[0]["uniq"] == P1
        assert primarios[0]["player"] == 1
        assert primarios[0]["vpad_nome"].endswith("(Hefesto P1)")

    def test_jogador_sem_vpad_aparece_declarando_que_aguarda_o_grab(self) -> None:
        """O físico já está na mesa e o vpad ainda não nasceu — e isso é FATO.

        Omitir a linha esconderia justamente o desequilíbrio (mais um físico,
        nenhum vpad novo) que o BUG-COOP-GRAB-PENDING-VPAD-01 existe para
        tornar visível.
        """
        mgr = CoopManager(_daemon_dublado(_VpadDublado(1)))  # type: ignore[arg-type]
        mgr._players[P2] = _jogador(P2, 2, vpad=None)

        item = next(i for i in mgr.mesa() if i["uniq"] == P2)
        assert item["aguardando_grab"] is True
        assert item["vpad_backend"] is None
        assert item["vpad_uniq"] is None

    def test_o_numero_do_jogador_vem_da_fonte_unica_da_mesa(self) -> None:
        """MESA-CHEIA-12: o inteiro sai de `numeros_de_jogador`, não do
        `player_index` cru — senão o card mostraria a telemetria do vpad de
        OUTRO controle. Aqui a fila de chegada inverte P2 e P4."""
        mgr = _mesa_de_quatro()
        fila = {P1: 1, P2: 4, P3: 3, P4: 2}
        mgr._daemon.identity_registry = SimpleNamespace(  # type: ignore[attr-defined]
            slot_for=lambda mac, assign=False: fila.get(mac)
        )

        numeros = {i["uniq"]: i["player"] for i in mgr.mesa()}
        assert numeros == fila, "a lâmpada e o rótulo são a MESMA função"

    def test_vpad_uinput_nao_inventa_endereco(self) -> None:
        """O uinput é evdev puro e não tem `uniq`. Dizer um seria inventar."""
        mgr = CoopManager(_daemon_dublado(_VpadDublado(1)))  # type: ignore[arg-type]
        mgr._players[P2] = _jogador(P2, 2, vpad=_VpadDublado(2, backend="uinput"))

        item = next(i for i in mgr.mesa() if i["uniq"] == P2)
        assert item["vpad_backend"] == "uinput"
        assert item["vpad_uniq"] is None

    def test_identidade_sem_mac_nao_vira_pseudo_endereco(self) -> None:
        """Fallback por path (`path:/dev/input/eventN`) não é MAC: `uniq` sai
        None em vez de publicar um identificador que não casa com nada."""
        mgr = CoopManager(_daemon_dublado(_VpadDublado(1)))  # type: ignore[arg-type]
        chave = "path:/dev/input/event30"
        mgr._players[chave] = _jogador(chave, 2, vpad=_VpadDublado(2))

        item = next(i for i in mgr.mesa() if not i["is_primary"])
        assert item["uniq"] is None
        assert item["vpad_uniq"] == player_mac(2), "o vpad existe e tem endereço"

    def test_a_divergencia_entre_fila_e_alocacao_e_dita(self) -> None:
        """MORDIDA 2 da sprint — a que impede a E1 de virar mentira nova.

        Desde a MESA-CHEIA-12 o `player` publicado é a FILA DE CHEGADA, e o
        nome/`uniq` do vpad carregam o índice de ALOCAÇÃO. Nesta mesa (a dela,
        de 15/08) o controle que a fila numera **2** tem o vpad **P4**.

        Arrancar = derivar o `vpad_uniq` do `player` em vez de perguntar ao
        objeto. Aí o estado diria `02:fe:00:00:00:02`, e o dispositivo que
        existe de verdade é o `…:04`.
        """
        mgr = CoopManager(_daemon_dublado(_VpadDublado(1)))  # type: ignore[arg-type]
        mgr._players[P2] = _jogador(P2, 4, vpad=_VpadDublado(4))
        mgr._daemon.identity_registry = SimpleNamespace(  # type: ignore[attr-defined]
            slot_for=lambda mac, assign=False: {P1: 1, P2: 2}.get(mac)
        )

        item = next(i for i in mgr.mesa() if i["uniq"] == P2)
        assert item["player"] == 2, "o número publicado é o da fila"
        assert item["vpad_uniq"] == player_mac(4), (
            "o endereço vem do OBJETO, nunca derivado do número publicado"
        )
        assert item["vpad_indice"] == 4
        assert item["nome_divergente"] is True, "divergir calado é o defeito"

        primario = next(i for i in mgr.mesa() if i["is_primary"])
        assert primario["nome_divergente"] is False, (
            "alarme que acende sempre não é alarme"
        )

    def test_o_fisico_calado_pelo_grab_nao_vira_controle_ausente(self) -> None:
        """MORDIDA 3 da sprint — a de MÉTODO.

        Com o co-op ativo o daemon faz EVIOCGRAB nos nós FÍSICOS: um leitor
        externo mede ZERO evento neles e um instrumento ingênuo conclui "o
        aparelho está calado". A mesa publicada tem de continuar afirmando o
        controle presente e com vpad vivo — é o que grava no código a
        armadilha que custou o passo manual de 15/08.
        """
        mgr = _mesa_de_quatro()
        for jogador in mgr._players.values():
            jogador.reader.grab_state = "held"  # o físico está mudo AGORA

        for item in mgr.mesa():
            assert item["aguardando_grab"] is False
            assert item["vpad_backend"] == "uhid"
            assert item["vpad_uniq"] is not None

    def test_lixo_em_memoria_nao_derruba_a_serializacao(self) -> None:
        """O `state_full` roda a 10 Hz e termina em `json.dumps`: um vpad
        dublado por objeto qualquer não pode virar payload não-serializável."""
        mgr = CoopManager(_daemon_dublado(object()))  # type: ignore[arg-type]
        mgr._players[P2] = _jogador(P2, 2, vpad=object())

        json.dumps(mgr.mesa())


# ---------------------------------------------------------------------------
# O fato chega ao estado publicado
# ---------------------------------------------------------------------------


class _Handlers(IpcHandlersMixin):
    """Só as três dependências que o `state_full` consome (molde do JOGO-01)."""

    def __init__(self, daemon: Any, store: Any, controller: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]
        self.store = store
        self.controller = controller


@pytest.fixture()
def config_em_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp: este teste NUNCA toca a config dela."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def _daemon_real_com_a_mesa() -> Any:
    """Daemon de verdade (o `state_full` pede muito mais que um dublê) com o
    `CoopManager` REAL — é a tabela dele que está sob teste."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon.controller.primary_uniq = P1  # type: ignore[attr-defined]
    daemon.controller._evdev = SimpleNamespace(  # type: ignore[attr-defined]
        _device_path="/dev/input/event20"
    )
    daemon.config.coop_enabled = True
    daemon._gamepad_device = _VpadDublado(1)  # type: ignore[assignment]
    mgr = CoopManager(daemon)
    for indice, mac in enumerate((P2, P3, P4), start=2):
        mgr._players[mac] = _jogador(mac, indice, vpad=_VpadDublado(indice))
    daemon._coop_manager = mgr  # type: ignore[assignment]
    return daemon


class TestOStateFullPublicaATabela:
    async def test_coop_traz_a_lista_ao_lado_do_numero(
        self, config_em_tmp: Path
    ) -> None:
        """A MORDIDA do contrato publicado: sem `coop.mesa` a GUI, a CLI e
        quem depurar continuam com um NÚMERO e nenhuma resposta.

        `players` fica ao lado de propósito — ele é lido pela CLI e pelo applet
        desde a FEAT-DSX-COOP-LOCAL-01, e a chave nova não substitui a velha.
        """
        daemon = _daemon_real_com_a_mesa()
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})

        assert cheio["coop"]["players"] == 4, "a contagem barata continua de pé"
        jogadores = cheio["coop"]["mesa"]
        assert isinstance(jogadores, list) and len(jogadores) == 4, (
            "voltar a ser só um número é exatamente o defeito de 15/08"
        )
        assert {j["uniq"]: j["vpad_uniq"] for j in jogadores} == {
            P1: player_mac(1),
            P2: player_mac(2),
            P3: player_mac(3),
            P4: player_mac(4),
        }
        json.dumps(cheio["coop"])

    async def test_a_chave_existe_mesmo_com_a_mesa_vazia(
        self, config_em_tmp: Path
    ) -> None:
        """Shape estável: lista vazia, nunca chave ausente — assim a GUI não
        precisa distinguir "daemon antigo" de "ninguém na mesa"."""
        daemon = Daemon(controller=FakeController(transport="usb"))
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})

        assert isinstance(cheio["coop"]["mesa"], list)

    async def test_nenhum_endereco_de_vpad_foge_da_faixa_forjada(
        self, config_em_tmp: Path
    ) -> None:
        """PRIVACIDADE: o `vpad_uniq` é forjado pelo produto (faixa localmente
        administrada `02:fe:…`) e não identifica hardware nenhum. O MAC do
        FÍSICO vai inteiro — e não é exposição nova: ele já viaja neste mesmo
        payload em `controllers[].uniq` desde a FEAT-STATE-PER-CONTROLLER-01,
        e a GUI casa card↔vpad por ele. Mascarar aqui criaria um segundo
        endereço incapaz de casar com o primeiro."""
        daemon = _daemon_real_com_a_mesa()
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})

        for jogador in cheio["coop"]["mesa"]:
            assert jogador["vpad_uniq"].startswith("02:fe:")

    async def test_per_vpad_passa_a_carregar_a_identidade_do_no(
        self, config_em_tmp: Path
    ) -> None:
        """E2 da sprint: até aqui o `per_vpad` tinha o inteiro `player` e mais
        nada que dissesse EM QUE DISPOSITIVO do kernel olhar — o objeto sabia
        `uniq` e nome desde sempre e não os publicava.

        Arrancar = voltar a publicar só `player`/`backend`. Aí a única ponte
        entre esta lista e `controllers[]` volta a ser um inteiro, e quem
        estiver fora da janela refaz o passo manual de 15/08.
        """
        daemon = _daemon_real_com_a_mesa()
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})

        blocos = cheio["rumble_ff"]["per_vpad"]
        assert len(blocos) == 4
        for bloco in blocos:
            numero = bloco["player"]
            assert bloco["vpad_uniq"] == player_mac(numero)
            assert bloco["vpad_nome"].endswith(f"(Hefesto P{numero})")
            assert bloco["vpad_indice"] == numero
        json.dumps(cheio["rumble_ff"])


# ---------------------------------------------------------------------------
# E chega na tela (regra dela, 09/08): a dica do título do card
# ---------------------------------------------------------------------------


class TestADicaDoCardDizQualVpad:
    def _estado(self) -> dict[str, Any]:
        return {
            "coop": {
                "players": 4,
                "mesa": [
                    {
                        "player": 2,
                        "uniq": P2,
                        "is_primary": False,
                        "vpad_backend": "uhid",
                        "vpad_uniq": player_mac(2),
                        "vpad_nome": "DualSense Wireless Controller (Hefesto P2)",
                        "vpad_indice": 2,
                        "aguardando_grab": False,
                        "nome_divergente": False,
                    }
                ],
            }
        }

    def test_o_card_do_controle_diz_qual_vpad_ele_alimenta(self) -> None:
        """A MORDIDA da tela: sem a dica, o card diz "Controle 2 — USB ·
        Jogador 2" e não há como conferir QUAL vpad é esse."""
        from hefesto_dualsense4unix.app.widgets.controller_card import dica_do_titulo

        dica = dica_do_titulo({"uniq": P2, "index": 1}, self._estado())

        assert dica is not None
        assert "Jogador 2" in dica
        assert player_mac(2) in dica, "é o endereço que casa com o /sys e o ensaio"

    def test_controle_fora_da_mesa_de_jogadores_nao_ganha_dica(self) -> None:
        """Cura exagerada reprova: quem não alimenta vpad nenhum não recebe
        par inventado — a dica some."""
        from hefesto_dualsense4unix.app.widgets.controller_card import dica_do_titulo

        assert dica_do_titulo({"uniq": P4, "index": 3}, self._estado()) is None

    def test_daemon_antigo_sem_a_lista_cala(self) -> None:
        """Sem `coop.mesa` no payload, nada a dizer — e nada quebra."""
        from hefesto_dualsense4unix.app.widgets.controller_card import dica_do_titulo

        assert dica_do_titulo({"uniq": P2}, {"coop": {"players": 4}}) is None

    def test_aguardando_grab_tem_frase_propria(self) -> None:
        """"Ainda não" e "não sei" são respostas diferentes."""
        from hefesto_dualsense4unix.app.widgets.controller_card import (
            DICA_TITULO_SEM_VPAD,
            dica_do_titulo,
        )

        estado = self._estado()
        estado["coop"]["mesa"][0].update(
            {"vpad_backend": None, "vpad_uniq": None, "aguardando_grab": True}
        )

        assert dica_do_titulo({"uniq": P2}, estado) == DICA_TITULO_SEM_VPAD

    def test_a_divergencia_de_nome_aparece_na_dica(self) -> None:
        """E3 na tela: quem for conferir card↔dispositivo procura pelo NOME, e
        desde a MESA-CHEIA-12 o nome pode não trazer o número da fila. Sem esta
        frase ela procura "Hefesto P2" e acha "Hefesto P4" sem saber por quê."""
        from hefesto_dualsense4unix.app.widgets.controller_card import dica_do_titulo

        estado = self._estado()
        estado["coop"]["mesa"][0].update(
            {
                "vpad_uniq": player_mac(4),
                "vpad_nome": "DualSense Wireless Controller (Hefesto P4)",
                "vpad_indice": 4,
                "nome_divergente": True,
            }
        )

        dica = dica_do_titulo({"uniq": P2}, estado)
        assert dica is not None
        assert "Jogador 2" in dica, "o número da mesa continua sendo o da fila"
        assert "Hefesto P4" in dica, "e o nome real do dispositivo é DITO"
