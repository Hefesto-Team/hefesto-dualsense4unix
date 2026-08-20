"""QUEM-SEGURA-O-NOSSO-NÓ-01 — o produto declara qual nó do kernel ele é.

O defeito: o `daemon.state_full` publica ~20 contadores por vpad e **nenhum
deles diz em que dispositivo do kernel olhar**. Quem precisa da resposta —
todo instrumento que queira medir se um jogo abriu o NOSSO nó — a reimplementa,
e hoje há três réguas para o mesmo fato:

* `scripts/ensaios/quem_o_jogo_abre.py` casa por **regex de caminho**;
* `app/actions/emulation_actions.py` casa por prefixo de **nome**;
* `scripts/identidade_do_vpad.py` casa pelo **uevent do pai**.

Três leituras do mesmo dado são três réguas, e a lição desta casa é que uma
delas envelhece calada. E o `game_open` é o caso extremo: ele existe em
`integrations/uhid_gamepad.py` desde a NUMA-02, o daemon o agrega em
`_any_game_session_open` e ele **nunca saiu por IPC** — a casa sabendo e o
produto não fazendo.

A MORDIDA de cada teste está dita na docstring dele. As três mais duras:

1. arrancar a escolha por nome exato faz a régua devolver o nó do **touchpad**
   (o menor `eventN` do aparelho é dele nesta árvore, que é a de verdade);
2. arrancar a confirmação pelo `uevent` faz a régua afirmar o `hidraw` de um
   aparelho que **não é nosso**;
3. arrancar a re-conferência por inode do cache faz o payload publicar por até
   2 s um caminho que já é de outro device — a renumeração que o inode existe
   para impedir, reintroduzida pelo cache.

ESTA SUÍTE NÃO TOCA O `/sys` VIVO. Toda árvore aqui é forjada em `tmp_path`, e
os "nós de /dev" são arquivos comuns — nada é aberto, nada é criado no kernel
(TEMPESTADE-DE-TECLADOS-01). O default da suíte inteira é a fixture
`_nenhum_sysfs_vivo_na_varredura_de_vpad`, do `conftest`.

ENDEREÇOS: nada de MAC real. Os vpads usam a faixa localmente administrada que
o próprio produto carimba (`02:fe:…`, de `uhid_gamepad.player_mac`) e os
físicos, a faixa forjada da casa (`aa:bb:cc:…`).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ipc_mod
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations import no_do_vpad as no_mod
from hefesto_dualsense4unix.integrations.no_do_vpad import (
    NO_DESCONHECIDO,
    no_ainda_vale,
    resolver_no_do_vpad,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    VPAD_HID_PHYS,
    UhidDualSense,
    player_mac,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

#: O físico dela, na faixa FORJADA da casa (`check_anonymity.sh`).
P1_FISICO = "aabbcc000001"
P2_FISICO = "aabbcc000002"


def _nome_do_vpad(jogador: int) -> str:
    """O nome que o `UhidDualSense.name` monta — copiado de propósito.

    Se ele mudar de novo (já mudou uma vez, na BT-E-VPAD-01), este arquivo tem
    de mudar junto: o nome é a régua de desempate entre os três nós do mesmo
    aparelho, e um teste que se auto-atualiza pela property não veria a troca.
    """
    return f"DualSense Wireless Controller (Hefesto P{jogador})"


# ---------------------------------------------------------------------------
# A bancada forjada: uma árvore de sysfs igual à de verdade, em tmp_path
# ---------------------------------------------------------------------------


class Bancada:
    """Uma árvore `/sys` + `/dev` de mentira, no formato exato do kernel.

    `/sys/class/input/eventN/device` é um symlink para `<HID>/input/inputM`, e
    é subindo por ele que a régua acha o device HID e o `hidraw` dele. É a
    topologia que importa aqui, não o conteúdo — por isso ela é reproduzida em
    vez de simplificada.
    """

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.class_input = raiz / "sys" / "class" / "input"
        self.devices = raiz / "sys" / "devices"
        self.dev_input = raiz / "dev" / "input"
        self.dev = raiz / "dev"
        for pasta in (self.class_input, self.devices, self.dev_input, self.dev):
            pasta.mkdir(parents=True, exist_ok=True)

    def aparelho(
        self,
        *,
        id_hid: str,
        hid_uniq: str,
        hid_phys: str,
        hidraw: str | None,
    ) -> Path:
        """Um device HID no sysfs, com `uevent` e (talvez) um nó `hidraw`."""
        dir_hid = self.devices / "virtual" / "misc" / "uhid" / id_hid
        dir_hid.mkdir(parents=True, exist_ok=True)
        (dir_hid / "uevent").write_text(
            "DRIVER=playstation\n"
            f"HID_ID=0003:0000054C:00000DF2\n"
            f"HID_NAME=DualSense Wireless Controller\n"
            f"HID_PHYS={hid_phys}\n"
            f"HID_UNIQ={hid_uniq}\n",
            encoding="utf-8",
        )
        if hidraw is not None:
            (dir_hid / "hidraw" / hidraw).mkdir(parents=True, exist_ok=True)
            (self.dev / hidraw).write_text("", encoding="utf-8")
        return dir_hid

    def no_de_entrada(
        self,
        *,
        dir_hid: Path,
        input_n: str,
        event_n: str,
        nome: str,
        uniq: str,
    ) -> None:
        """Um `inputM` sob o device HID, publicado em `/sys/class/input`."""
        dir_input = dir_hid / "input" / input_n
        dir_input.mkdir(parents=True, exist_ok=True)
        (dir_input / "name").write_text(nome + "\n", encoding="utf-8")
        (dir_input / "uniq").write_text(uniq + "\n", encoding="utf-8")
        pasta_event = self.class_input / event_n
        pasta_event.mkdir(parents=True, exist_ok=True)
        os.symlink(dir_input, pasta_event / "device")
        (self.dev_input / event_n).write_text("", encoding="utf-8")

    def no_de_uinput(self, *, event_n: str, nome: str) -> None:
        """Um nó de uinput: evdev puro, sem `uniq` e sem device HID acima."""
        dir_input = self.devices / "virtual" / "input" / f"input{event_n[5:]}"
        dir_input.mkdir(parents=True, exist_ok=True)
        (dir_input / "name").write_text(nome + "\n", encoding="utf-8")
        (dir_input / "uniq").write_text("\n", encoding="utf-8")
        pasta_event = self.class_input / event_n
        pasta_event.mkdir(parents=True, exist_ok=True)
        os.symlink(dir_input, pasta_event / "device")
        (self.dev_input / event_n).write_text("", encoding="utf-8")

    def vpad(self, jogador: int, *, event_gamepad: str, hidraw: str) -> None:
        """Um vpad COMPLETO: os três nós de entrada que um DualSense publica.

        A ordem é a que o kernel produz de verdade e é ela que dá a mordida do
        desempate: aqui o **touchpad** fica com o menor `eventN`.
        """
        base = int(event_gamepad[len("event") :])
        dir_hid = self.aparelho(
            id_hid=f"0003:054C:0DF2.000{jogador}",
            hid_uniq=player_mac(jogador),
            hid_phys=VPAD_HID_PHYS,
            hidraw=hidraw,
        )
        nome = _nome_do_vpad(jogador)
        self.no_de_entrada(
            dir_hid=dir_hid,
            input_n=f"input{base}0",
            event_n=f"event{base - 2}",
            nome=f"{nome} Touchpad",
            uniq=player_mac(jogador),
        )
        self.no_de_entrada(
            dir_hid=dir_hid,
            input_n=f"input{base}1",
            event_n=f"event{base - 1}",
            nome=f"{nome} Motion Sensors",
            uniq=player_mac(jogador),
        )
        self.no_de_entrada(
            dir_hid=dir_hid,
            input_n=f"input{base}2",
            event_n=event_gamepad,
            nome=nome,
            uniq=player_mac(jogador),
        )

    def resolver(self, uniq: str | None, nome: str | None) -> dict[str, Any]:
        """`resolver_no_do_vpad` apontado para ESTA árvore, nunca para `/sys`."""
        return resolver_no_do_vpad(
            uniq=uniq,
            nome=nome,
            raiz_class_input=str(self.class_input),
            raiz_dev_input=str(self.dev_input),
            raiz_dev=str(self.dev),
        )


@pytest.fixture()
def bancada(tmp_path: Path) -> Bancada:
    return Bancada(tmp_path)


def _trocar_o_no_por_outro(caminho: Path) -> None:
    """Põe OUTRO arquivo no lugar deste, com inode garantidamente diferente.

    `unlink` + recriar não serve: o `tmpfs` do `/tmp` recicla o inode na hora,
    e o teste passaria a medir a sorte do alocador em vez da régua. Criar o
    substituto ANTES (os dois vivos ao mesmo tempo) e trocar por `os.replace`
    garante inodes distintos — e essa garantia é o que este teste precisa
    afirmar, não a política de alocação de nenhum sistema de arquivos.
    """
    novo = caminho.with_name(caminho.name + ".substituto")
    novo.write_text("outro nó", encoding="utf-8")
    assert os.stat(novo).st_ino != os.stat(caminho).st_ino
    os.replace(novo, caminho)


# ---------------------------------------------------------------------------
# A régua: qual nó é o nosso
# ---------------------------------------------------------------------------


class TestARegua:
    def test_entre_os_tres_nos_do_aparelho_sai_o_gamepad(
        self, bancada: Bancada
    ) -> None:
        """MORDIDA 1: o menor `eventN` do aparelho é o do TOUCHPAD.

        Um DualSense publica três nós de entrada com o MESMO `uniq` — gamepad,
        `… Touchpad` e `… Motion Sensors` (`ps_allocate_input_dev`). Arrancar a
        escolha por nome exato e ficar com "o primeiro que casou o `uniq`"
        entrega `event20`, o touchpad: um nó que existe, responde e **não é o
        que o jogo lê para mover o personagem**.
        """
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")

        no = bancada.resolver(player_mac(1), _nome_do_vpad(1))

        assert no["evdev"] == str(bancada.dev_input / "event22")
        assert no["hidraw"] == str(bancada.dev / "hidraw5")

    def test_o_uniq_forjado_e_a_regua_nunca_o_vid_pid(
        self, bancada: Bancada
    ) -> None:
        """Um DualSense Edge de VERDADE na mesa não pode ser confundido.

        O vpad forja `054c:0df2` (Edge) no barramento `0003` de propósito e
        forja bem — nesta árvore os dois aparelhos têm o mesmo `HID_ID`. Quem
        casasse por vid/pid e barramento acharia os dois e escolheria o de
        menor `eventN`, que aqui é o FÍSICO dela.
        """
        edge = bancada.aparelho(
            id_hid="0003:054C:0DF2.0009",
            hid_uniq="aa:bb:cc:00:00:01",
            hid_phys="usb-0000:00:14.0-3/input0",
            hidraw="hidraw3",
        )
        bancada.no_de_entrada(
            dir_hid=edge,
            input_n="input10",
            event_n="event10",
            nome="DualSense Edge Wireless Controller",
            uniq="aa:bb:cc:00:00:01",
        )
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")

        no = bancada.resolver(player_mac(1), _nome_do_vpad(1))

        assert no["evdev"] == str(bancada.dev_input / "event22")
        assert no["hidraw"] == str(bancada.dev / "hidraw5")

    def test_hidraw_so_sai_quando_o_uevent_do_pai_confirma(
        self, bancada: Bancada
    ) -> None:
        """MORDIDA 2: duas rotas que discordam não viram afirmação.

        O nó de entrada diz o nosso `uniq`, e o `uevent` do device HID dono
        dele diz outra coisa — sem carimbo `hefesto-vpad` e com outro
        `HID_UNIQ`. Arrancar a confirmação faz a régua publicar
        `/dev/hidraw9`, o hidraw de um aparelho que não é nosso; e é por um
        hidraw errado que um instrumento escreve no controle errado.
        """
        estranho = bancada.aparelho(
            id_hid="0005:054C:0CE6.000F",
            hid_uniq="aa:bb:cc:00:00:02",
            hid_phys="aa:bb:cc:00:00:99",
            hidraw="hidraw9",
        )
        bancada.no_de_entrada(
            dir_hid=estranho,
            input_n="input40",
            event_n="event40",
            nome=_nome_do_vpad(1),
            uniq=player_mac(1),
        )

        no = bancada.resolver(player_mac(1), _nome_do_vpad(1))

        assert no["evdev"] == str(bancada.dev_input / "event40"), (
            "o nó de entrada casou pelo uniq — isso a régua mediu"
        )
        assert no["hidraw"] is None, "discordância vira 'não sei', nunca palpite"
        assert no["hidraw_ino"] is None

    def test_o_inode_vem_do_mesmo_instante_que_o_caminho(
        self, bancada: Bancada
    ) -> None:
        """O par caminho+inode é o ponto todo desta peça.

        `/dev/input/eventN` é um número de fila: entre publicar o caminho e
        quem lê fazer o `stat` dele cabe a renumeração inteira. Publicar o
        inode lido no MESMO instante fecha essa janela — e `os.stat` não abre
        o nó, que é o que permite medir sem disparar `UHID_OPEN`.
        """
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")

        no = bancada.resolver(player_mac(1), _nome_do_vpad(1))

        assert no["ino"] == os.stat(bancada.dev_input / "event22").st_ino
        assert no["hidraw_ino"] == os.stat(bancada.dev / "hidraw5").st_ino

    def test_o_vpad_de_uinput_nao_inventa_um_hidraw(
        self, bancada: Bancada
    ) -> None:
        """O uinput é evdev puro: casa pelo nome e NÃO tem hidraw.

        Dizer um seria inventar — e é exatamente por não ter hidraw que o SDL
        não faz o vpad de uinput vibrar. Um `hidraw` publicado aqui mandaria
        quem depura procurar a vibração no lugar onde ela não pode existir.
        """
        bancada.no_de_uinput(event_n="event31", nome=_nome_do_vpad(1))

        no = bancada.resolver(None, _nome_do_vpad(1))

        assert no["evdev"] == str(bancada.dev_input / "event31")
        assert no["hidraw"] is None
        assert no["ino"] == os.stat(bancada.dev_input / "event31").st_ino

    def test_sem_uniq_e_sem_nome_nao_ha_chute(self, bancada: Bancada) -> None:
        """MORDIDA 3: "pega o primeiro gamepad que achar" é proibido.

        Com a mesa montada, um fallback desses devolveria um nó — e com um
        vpad dublado (sem `mac` nem `name`) o payload do produto passaria a
        AFIRMAR um caminho sobre o controle físico dela. Quatro `None` é a
        resposta certa: "não sei" vale mais que um palpite plausível.
        """
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")

        assert bancada.resolver(None, None) == NO_DESCONHECIDO
        assert bancada.resolver("", "  ") == NO_DESCONHECIDO

    def test_mesa_vazia_devolve_quatro_nones_e_nao_explode(
        self, bancada: Bancada
    ) -> None:
        """Sysfs sem nó nenhum (e sysfs inexistente) é caso NORMAL aqui."""
        assert bancada.resolver(player_mac(1), _nome_do_vpad(1)) == NO_DESCONHECIDO
        assert resolver_no_do_vpad(
            uniq=player_mac(1),
            nome=_nome_do_vpad(1),
            raiz_class_input=str(bancada.raiz / "nao-existe"),
            raiz_dev_input=str(bancada.dev_input),
            raiz_dev=str(bancada.dev),
        ) == NO_DESCONHECIDO

    def test_dois_vpads_nao_se_misturam(self, bancada: Bancada) -> None:
        """Co-op: cada jogador tem o SEU nó, e o `uniq` é quem separa."""
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")
        bancada.vpad(2, event_gamepad="event27", hidraw="hidraw6")

        um = bancada.resolver(player_mac(1), _nome_do_vpad(1))
        dois = bancada.resolver(player_mac(2), _nome_do_vpad(2))

        assert um["evdev"] == str(bancada.dev_input / "event22")
        assert dois["evdev"] == str(bancada.dev_input / "event27")
        assert um["hidraw"] == str(bancada.dev / "hidraw5")
        assert dois["hidraw"] == str(bancada.dev / "hidraw6")
        assert um["ino"] != dois["ino"]


class TestOInodeReprovaOCaminhoVelho:
    def test_no_ainda_vale_reprova_quando_o_no_e_recriado(
        self, bancada: Bancada
    ) -> None:
        """O vpad morreu e voltou no mesmo `eventN` — outro inode, outro nó."""
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")
        no = bancada.resolver(player_mac(1), _nome_do_vpad(1))
        assert no_ainda_vale(no) is True

        _trocar_o_no_por_outro(bancada.dev_input / "event22")

        assert no_ainda_vale(no) is False

    def test_no_ainda_vale_reprova_quando_o_hidraw_troca(
        self, bancada: Bancada
    ) -> None:
        """A conferência olha o PAR: o evdev intacto não absolve o hidraw."""
        bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")
        no = bancada.resolver(player_mac(1), _nome_do_vpad(1))

        _trocar_o_no_por_outro(bancada.dev / "hidraw5")

        assert no_ainda_vale(no) is False

    def test_bloco_sem_no_nao_gasta_stat_e_deixa_o_ttl_mandar(self) -> None:
        """Quem não afirma caminho não tem caminho a envelhecer.

        MORDIDA ao contrário: fazer `no_ainda_vale` reprovar aqui parece mais
        seguro e é o defeito — a varredura inteira de `/sys/class/input`
        passaria a rodar a 10 Hz no caso MAIS COMUM (vpad de uinput, vpad
        nascendo, máquina sem controle), que é exatamente o custo que o cache
        existe para não pagar. O nó que APARECEU é problema do TTL.
        """
        assert no_ainda_vale(dict(NO_DESCONHECIDO)) is True


class TestASuiteNaoOlhaOSysfsDela:
    def test_a_varredura_da_suite_aponta_para_o_vazio(self) -> None:
        """A fixture de sessão do `conftest` é parte da cura, não conforto.

        MORDIDA: tirar `_nenhum_sysfs_vivo_na_varredura_de_vpad` faz dezenas de
        testes que chamam `_handle_daemon_state_full` varrerem o `/sys` VIVO —
        e a máquina de desenvolvimento é a máquina dela, com vpads de verdade
        ali dentro. O payload sob teste passaria a depender de quantos
        controles estavam ligados, e um teste que casasse com o `event22` de
        verdade estaria afirmando sobre o aparelho dela (TEMPESTADE-DE-
        TECLADOS-01, a mesma raiz).
        """
        assert not no_mod.RAIZ_CLASS_INPUT.startswith("/sys")
        assert not no_mod.RAIZ_DEV_INPUT.startswith("/dev")
        assert not no_mod.RAIZ_DEV.startswith("/dev")
        assert resolver_no_do_vpad(
            uniq=player_mac(1), nome=_nome_do_vpad(1)
        ) == NO_DESCONHECIDO


class TestOCarimboTemUmDonoSo:
    def test_o_phys_publicado_e_o_mesmo_que_o_create2_escreve(self) -> None:
        """A régua confere o que o produto CARIMBA — e são o mesmo objeto.

        MORDIDA: alguém trocar a palavra no `_create2_event` e deixar a
        constante para trás. Aí `no_do_vpad` procuraria um carimbo que o
        kernel não recebeu mais, `hidraw` sairia `None` para sempre, e nada
        reprovaria — o modo de falha "duas réguas, uma envelhece calada" que
        esta peça inteira existe para fechar. Este teste lê os bytes do evento
        que vai ao `/dev/uhid`, não a constante.
        """
        evento = UhidDualSense(player=1)._create2_event(b"\x05\x01")

        # Layout do UHID_CREATE2: u32 tipo + name[128] + phys[64] + uniq[64].
        phys = evento[4 + 128 : 4 + 128 + 64].rstrip(b"\0").decode("ascii")

        assert phys == VPAD_HID_PHYS
        uniq = evento[4 + 128 + 64 : 4 + 128 + 128].rstrip(b"\0").decode("ascii")
        assert uniq == player_mac(1), "o outro lado da régua, no mesmo evento"


# ---------------------------------------------------------------------------
# O fato chega ao estado publicado
# ---------------------------------------------------------------------------


class _Handlers(IpcHandlersMixin):
    """Só as três dependências que o `state_full` consome (molde do JOGO-01)."""

    def __init__(self, daemon: Any, store: Any, controller: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]
        self.store = store
        self.controller = controller


class _VpadDublado:
    """O que o `per_vpad` lê de um vpad: identidade, backend e `game_open`."""

    def __init__(
        self, jogador: int, *, backend: str = "uhid", game_open: bool = False
    ) -> None:
        self.backend = backend
        self.player = jogador
        self.mac = player_mac(jogador) if backend == "uhid" else None
        self.name = _nome_do_vpad(jogador)
        self.game_open = game_open


@pytest.fixture()
def config_em_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp: este teste NUNCA toca a config dela."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


@pytest.fixture()
def sysfs_da_bancada(
    bancada: Bancada, monkeypatch: pytest.MonkeyPatch
) -> Bancada:
    """Aponta a régua do produto para a árvore forjada, e só para ela.

    Por cima da fixture de sessão do `conftest`, que aponta a suíte inteira
    para o vazio. A troca é nas constantes do módulo — que `resolver_no_do_vpad`
    resolve na hora da chamada, e não no `def`, exatamente para isto.
    """
    monkeypatch.setattr(no_mod, "RAIZ_CLASS_INPUT", str(bancada.class_input))
    monkeypatch.setattr(no_mod, "RAIZ_DEV_INPUT", str(bancada.dev_input))
    monkeypatch.setattr(no_mod, "RAIZ_DEV", str(bancada.dev))
    return bancada


def _daemon_com_dois_vpads(*, game_open_do_p2: bool = False) -> Any:
    """Daemon real (o `state_full` pede muito mais que um dublê) + co-op de 2."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon.controller.primary_uniq = P1_FISICO  # type: ignore[attr-defined]
    daemon.controller._evdev = SimpleNamespace(  # type: ignore[attr-defined]
        _device_path="/dev/input/event20"
    )
    daemon.config.coop_enabled = True
    daemon._gamepad_device = _VpadDublado(1)  # type: ignore[assignment]
    mgr = CoopManager(daemon)
    mgr._players[P2_FISICO] = _SecondaryPlayer(
        identity=P2_FISICO,
        evdev_path="/dev/input/event21",
        reader=SimpleNamespace(grab_state="held"),  # type: ignore[arg-type]
        player_index=2,
        vpad=_VpadDublado(2, game_open=game_open_do_p2),
    )
    daemon._coop_manager = mgr  # type: ignore[assignment]
    return daemon


def _bloco(cheio: dict[str, Any], jogador: int) -> dict[str, Any]:
    return next(
        b for b in cheio["rumble_ff"]["per_vpad"] if b["player"] == jogador
    )


def _blocos(cheio: dict[str, Any]) -> list[dict[str, Any]]:
    blocos = cheio["rumble_ff"]["per_vpad"]
    assert isinstance(blocos, list) and blocos, "sem bloco não há o que afirmar"
    return blocos


class TestOStateFullDeclaraONo:
    async def test_per_vpad_diz_evdev_hidraw_inode_e_sessao_aberta(
        self, config_em_tmp: Path, sysfs_da_bancada: Bancada
    ) -> None:
        """A MORDIDA do contrato publicado.

        Arrancar = voltar a publicar só contadores. Aí a pergunta *"o jogo
        abriu o NOSSO nó?"* volta a não ter resposta observável, e o próximo
        instrumento inventa a quarta régua para "quem é o nosso nó" — que é o
        estado de 20/08/2026.
        """
        sysfs_da_bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")
        sysfs_da_bancada.vpad(2, event_gamepad="event27", hidraw="hidraw6")
        daemon = _daemon_com_dois_vpads(game_open_do_p2=True)
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})

        um, dois = _bloco(cheio, 1), _bloco(cheio, 2)
        assert um["evdev"] == str(sysfs_da_bancada.dev_input / "event22")
        assert um["hidraw"] == str(sysfs_da_bancada.dev / "hidraw5")
        assert um["ino"] == os.stat(sysfs_da_bancada.dev_input / "event22").st_ino
        assert um["hidraw_ino"] == os.stat(sysfs_da_bancada.dev / "hidraw5").st_ino
        assert dois["evdev"] == str(sysfs_da_bancada.dev_input / "event27")
        assert um["game_open"] is False
        assert dois["game_open"] is True, (
            "existia no objeto desde a NUMA-02 e nunca saía por IPC"
        )
        json.dumps(_blocos(cheio))

    async def test_o_no_casa_com_a_identidade_publicada_no_mesmo_bloco(
        self, config_em_tmp: Path, sysfs_da_bancada: Bancada
    ) -> None:
        """O `vpad_uniq` do bloco é o que resolveu o nó do bloco.

        Duas descrições do mesmo vpad se afastam na primeira mudança: o nó sai
        do `identidade_do_vpad` que o próprio bloco publica, nunca de uma
        segunda leitura do objeto.
        """
        sysfs_da_bancada.vpad(2, event_gamepad="event27", hidraw="hidraw6")
        daemon = _daemon_com_dois_vpads()
        h = _Handlers(daemon, daemon.store, daemon.controller)

        dois = _bloco(await h._handle_daemon_state_full({}), 2)

        assert dois["vpad_uniq"] == player_mac(2)
        assert dois["evdev"] == str(sysfs_da_bancada.dev_input / "event27")

    async def test_as_chaves_existem_mesmo_sem_no_resolvido(
        self, config_em_tmp: Path, sysfs_da_bancada: Bancada
    ) -> None:
        """Shape estável: `None`, nunca chave ausente.

        Senão "daemon antigo" e "o daemon não sabe" chegam iguais em quem lê —
        e é exatamente esse silêncio que fazia o `game_open` não existir para
        ninguém de fora.
        """
        daemon = _daemon_com_dois_vpads()  # sysfs vazio de propósito
        h = _Handlers(daemon, daemon.store, daemon.controller)

        um = _bloco(await h._handle_daemon_state_full({}), 1)

        for campo in ("evdev", "hidraw", "ino", "hidraw_ino"):
            assert campo in um and um[campo] is None
        assert um["game_open"] is False

    async def test_vpad_dublado_nao_afirma_sessao_aberta(
        self, config_em_tmp: Path, sysfs_da_bancada: Bancada
    ) -> None:
        """MORDIDA: `bool(MagicMock())` é `True`.

        O `state_full` roda a 10 Hz sobre objetos que nem sempre são vpads de
        verdade. Trocar o `is True` por `bool()` faz o painel afirmar "há
        sessão de jogo aberta neste vpad" para um dublê — a medição confiante
        e falsa que é a armadilha nº 1 desta casa.
        """
        daemon = _daemon_com_dois_vpads()
        daemon._gamepad_device = MagicMock()  # type: ignore[assignment]
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})

        assert all(b["game_open"] is False for b in _blocos(cheio))
        json.dumps(_blocos(cheio))

    async def test_o_cache_nao_publica_o_caminho_velho(
        self, config_em_tmp: Path, sysfs_da_bancada: Bancada
    ) -> None:
        """MORDIDA 3: o cache de 2 s não pode reintroduzir a renumeração.

        O vpad muda de `eventN` — cai e volta, o co-op recria, a Steam abre uma
        janela. Arrancar a re-conferência por inode (`no_ainda_vale`) e confiar
        só no TTL faz este teste ler `event22` na segunda chamada: um caminho
        que já não é o nosso, publicado pelo produto com toda a confiança.
        """
        sysfs_da_bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")
        daemon = _daemon_com_dois_vpads()
        h = _Handlers(daemon, daemon.store, daemon.controller)
        primeiro = _bloco(await h._handle_daemon_state_full({}), 1)
        assert primeiro["evdev"] == str(sysfs_da_bancada.dev_input / "event22")

        for pasta in sorted(sysfs_da_bancada.class_input.iterdir()):
            (pasta / "device").unlink()
            pasta.rmdir()
        (sysfs_da_bancada.dev_input / "event22").unlink()
        sysfs_da_bancada.vpad(1, event_gamepad="event42", hidraw="hidraw5")

        segundo = _bloco(await h._handle_daemon_state_full({}), 1)

        assert segundo["evdev"] == str(sysfs_da_bancada.dev_input / "event42"), (
            "dentro do TTL, e ainda assim o caminho novo — quem manda é o inode"
        )
        assert segundo["ino"] == os.stat(
            sysfs_da_bancada.dev_input / "event42"
        ).st_ino

    async def test_o_cache_poupa_a_varredura_quando_nada_mudou(
        self,
        config_em_tmp: Path,
        sysfs_da_bancada: Bancada,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """O TTL existe porque isto roda a 10-20 Hz — e ele tem de valer.

        Sem cache seriam dezenas de `listdir` por segundo para responder a
        mesma pergunta. Aqui: duas chamadas seguidas, UMA varredura.
        """
        sysfs_da_bancada.vpad(1, event_gamepad="event22", hidraw="hidraw5")
        daemon = _daemon_com_dois_vpads()
        h = _Handlers(daemon, daemon.store, daemon.controller)
        await h._handle_daemon_state_full({})

        chamadas: list[str] = []
        original = ipc_mod.resolver_no_do_vpad

        def _contando(**kwargs: Any) -> dict[str, Any]:
            chamadas.append(str(kwargs.get("uniq")))
            return original(**kwargs)

        monkeypatch.setattr(ipc_mod, "resolver_no_do_vpad", _contando)
        await h._handle_daemon_state_full({})

        assert chamadas == [], "dentro do TTL e com o inode intacto: nada a rever"
