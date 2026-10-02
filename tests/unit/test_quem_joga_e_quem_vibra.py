"""QUEM-JOGA-E-QUEM-VIBRA-01 — num jogo de um jogador, um controle vibra."""

from __future__ import annotations

import os
import pathlib
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.integrations.quem_o_jogo_le import (
    ENV_DO_JOGO,
    dono_do_vpad_pelo_coop,
    nos_abertos_por,
    pids_de_jogo,
    quem_o_jogo_le,
    uniq_por_evdev,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"
MESA = [P1, P2, P3, P4]


def _input_de_mentira(raiz: pathlib.Path, mapa: dict[str, str]) -> pathlib.Path:
    """`/sys/class/input` de mentira: um `eventN` por linha do mapa."""
    base = raiz / "input"
    for evento, uniq in mapa.items():
        d = base / evento / "device"
        d.mkdir(parents=True, exist_ok=True)
        (d / "uniq").write_text(uniq + "\n", encoding="utf-8")
    return base


def _proc_de_mentira(
    raiz: pathlib.Path, processos: dict[int, tuple[bool, list[str]]]
) -> pathlib.Path:
    """`/proc` de mentira: `{pid: (é_jogo, [eventN abertos])}`."""
    base = raiz / "proc"
    alvos = raiz / "dev" / "input"
    alvos.mkdir(parents=True, exist_ok=True)
    for pid, (e_jogo, eventos) in processos.items():
        d = base / str(pid)
        (d / "fd").mkdir(parents=True, exist_ok=True)
        env = f"{ENV_DO_JOGO}=/algum/prefixo\0HOME=/x\0" if e_jogo else "HOME=/x\0"
        (d / "environ").write_bytes(env.encode("utf-8"))
        for i, evento in enumerate(eventos):
            alvo = alvos / evento
            alvo.touch(exist_ok=True)
            os.symlink(alvo, d / "fd" / str(i + 3))
    return base


class TestOSinalBruto:
    def test_o_uniq_sai_do_sysfs_de_cada_evdev(self, tmp_path):
        base = _input_de_mentira(tmp_path, {"event7": P1, "event8": P3})
        assert uniq_por_evdev(base) == {"event7": P1, "event8": P3}

    def test_so_e_jogo_quem_tem_a_env_do_proton(self, tmp_path):
        base = _proc_de_mentira(tmp_path, {11: (True, []), 22: (False, [])})
        assert pids_de_jogo(base) == {11}

    def test_os_descritores_abertos_viram_eventos(self, tmp_path):
        base = _proc_de_mentira(tmp_path, {11: (True, ["event7", "event9"])})
        assert nos_abertos_por([11], base)[0] == {"event7", "event9"}


class TestAMesaDeQuatro:
    """O arranjo DIFÍCIL — o fácil («um jogando») não separa as regras."""

    def test_o_jogo_le_um_e_so_ele_vibra(self, tmp_path):
        """O caso dela: PRAGMATA, um jogador, três controles quietos."""
        inp = _input_de_mentira(
            tmp_path,
            {"event1": P1, "event2": P2, "event3": P3, "event4": P4},
        )
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(
            fisicos=MESA, raiz_proc=proc, raiz_input=inp
        ) == {P1}

    def test_o_jogo_le_dois_dos_quatro_e_so_esses_dois_vibram(self, tmp_path):
        """**A régua que separa a decisão dela de «sempre o P1».**"""
        inp = _input_de_mentira(
            tmp_path,
            {"event1": P1, "event2": P2, "event3": P3, "event4": P4},
        )
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event2", "event4"])})
        assert quem_o_jogo_le(
            fisicos=MESA, raiz_proc=proc, raiz_input=inp
        ) == {P2, P4}

    def test_um_controle_publica_varios_eventos_e_conta_uma_vez(self, tmp_path):
        """Botões, movimento, touchpad e o conector do fone são quatro nós."""
        inp = _input_de_mentira(
            tmp_path,
            {"event1": P1, "event2": P1, "event3": P1, "event9": P3},
        )
        proc = _proc_de_mentira(
            tmp_path, {77: (True, ["event1", "event2", "event3"])}
        )
        assert quem_o_jogo_le(
            fisicos=MESA, raiz_proc=proc, raiz_input=inp
        ) == {P1}


class TestAAusenciaEResposta:
    """E aqui ela tem LADO: o vazio cala, e calar é o seguro."""

    def test_sem_jogo_ninguem_vibra(self, tmp_path):
        inp = _input_de_mentira(tmp_path, {"event1": P1})
        proc = _proc_de_mentira(tmp_path, {22: (False, ["event1"])})
        assert quem_o_jogo_le(fisicos=MESA, raiz_proc=proc, raiz_input=inp) == set()

    def test_proc_ilegivel_nao_vira_mesa_inteira(self, tmp_path):
        """MORDIDA: devolver `set(fisicos)` no ramo de erro."""
        inp = _input_de_mentira(tmp_path, {"event1": P1})
        assert quem_o_jogo_le(
            fisicos=MESA, raiz_proc=tmp_path / "nao-existe", raiz_input=inp
        ) == set()

    def test_sem_fisicos_declarados_ninguem_vibra(self, tmp_path):
        inp = _input_de_mentira(tmp_path, {"event1": P1})
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(fisicos=[], raiz_proc=proc, raiz_input=inp) == set()


class TestADobraDoVpad:
    """Com máscara, o evdev que o jogo segura é o do VIRTUAL — e ignorá-lo cala quem joga.

    Com o GE-Proton o jogo não segura evdev de DualSense nenhum, só o
    ``hidraw`` (A-HAPTICA-QUEM-JOGA-01, 26/09/2026); quem joga, aí, é quem
    mexeu desde que o jogo abriu (``test_a_haptica_quem_joga_e_quem_mexe.py``).
    Este caminho fica para o processo de jogo que segura um evdev com ``uniq``.

    Quem diz de quem é cada vpad é o co-op, que liga cada físico ao vpad dele
    (A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01, 25/09/2026). A tradução
    derivava o MAC do vpad de cada físico, e isso responde de quem ele
    NASCEU: o posto troca de mão sem renascer. A matriz inteira, na bancada
    honesta, está em ``test_a_haptica_segue_quem_alimenta_o_vpad.py``.
    """

    def test_o_vpad_se_traduz_no_fisico_que_o_alimenta(self):
        """MORDIDA: devolver `None` sempre."""
        coop = SimpleNamespace(quem_alimenta_cada_vpad=lambda: {vpad_mac(P3, 1): "aabbcc000003"})
        assert dono_do_vpad_pelo_coop(coop, MESA)(vpad_mac(P3, 1)) == P3

    def test_o_mac_nao_depende_do_numero_nem_de_quem_dirige(self):
        """O MAC segue o APARELHO de que o vpad nasceu (a E3), e não o número."""
        assert len({vpad_mac(P2, n) for n in (1, 2, 3, 4)}) == 1
        coop = SimpleNamespace(quem_alimenta_cada_vpad=lambda: {vpad_mac(P1, 1): "aabbcc000002"})
        assert dono_do_vpad_pelo_coop(coop, MESA)(vpad_mac(P1, 1)) == P2

    def test_o_jogo_lendo_so_o_vpad_ainda_acha_o_dono(self, tmp_path):
        """Um processo de jogo segura o evdev do vpad, e nunca o do físico."""
        virtual = vpad_mac(P1, 1)
        coop = SimpleNamespace(quem_alimenta_cada_vpad=lambda: {virtual: "aabbcc000001"})
        inp = _input_de_mentira(tmp_path, {"event1": virtual, "event2": P3})
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(
            fisicos=MESA,
            dono_do_vpad=dono_do_vpad_pelo_coop(coop, MESA),
            raiz_proc=proc,
            raiz_input=inp,
        ) == {P1}

    def test_vpad_sem_dono_nao_vira_chute(self, tmp_path):
        """Um vpad que ninguém alimenta não pertence a ninguém."""
        coop = SimpleNamespace(quem_alimenta_cada_vpad=lambda: {})
        inp = _input_de_mentira(tmp_path, {"event1": "02:fe:00:00:00:01"})
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(
            fisicos=MESA,
            dono_do_vpad=dono_do_vpad_pelo_coop(coop, MESA),
            raiz_proc=proc,
            raiz_input=inp,
        ) == set()


class TestOGateEstaLigado:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def _corpo(self) -> str:
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py"
        ).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _casar_as_pontes") :]
        return corpo[: corpo.index("\n    def ", 1)]

    def test_o_subsystem_consulta_quem_joga_antes_de_decidir_o_modo(self) -> None:
        """MORDIDA: tire a chamada a `_quem_mexeu_na_partida` (o voto e a"""
        corpo = self._corpo()
        antes_do_modo = corpo[: corpo.index("modo = self._modo_pelo_sinal(")]
        assert "jogando = self._quem_mexeu_na_partida(controles)" in antes_do_modo, (
            "o voto de quem joga não é consultado dentro de `_casar_as_pontes`"
        )
        assert "self._quem_o_jogo_le(controles)" not in corpo, (
            "a varredura de /proc voltou a rodar a cada volta"
        )

    def test_o_modo_haptica_exige_os_dois_sinais(self) -> None:
        """O canal aberto E aquele controle jogando (mexeu desde que o jogo abriu)."""
        corpo = self._corpo()
        i = corpo.index("candidata = ")
        condicao = corpo[i : corpo.index("\n", i)]
        assert "este_joga" in condicao, "o gate saiu da condição do modo"
        assert "endpoint_aberto" in condicao, "o canal saiu da condição do modo"
        assert (
            "endpoint_aberto = endpoint is not None and sink_esta_tocando(endpoint.nome)"
            in corpo
        )
        chamada = corpo[corpo.index("modo = self._modo_pelo_sinal(") :]
        assert "candidata=candidata" in chamada[: chamada.index("\n            )")], (
            "o modo deixou de receber o portão"
        )
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py"
        ).read_text(encoding="utf-8")
        regra = fonte[fonte.index("def _modo_pelo_sinal") :]
        regra = regra[regra.index('"""', regra.index('"""') + 3) + 3 :]
        primeira = regra.strip().splitlines()[0]
        assert primeira.startswith("if not candidata"), (
            "o portão não é a primeira pergunta do modo: sem ele, tem de ser som"
        )


@pytest.mark.parametrize("quem", [P1, P2, P3, P4])
def test_qualquer_um_dos_quatro_pode_ser_o_que_joga(tmp_path, quem):
    """Nenhum índice é privilegiado — é o que a decisão dela pede."""
    inp = _input_de_mentira(
        tmp_path, {f"event{i + 1}": u for i, u in enumerate(MESA)}
    )
    evento = f"event{MESA.index(quem) + 1}"
    proc = _proc_de_mentira(tmp_path, {77: (True, [evento])})
    assert quem_o_jogo_le(fisicos=MESA, raiz_proc=proc, raiz_input=inp) == {quem}
