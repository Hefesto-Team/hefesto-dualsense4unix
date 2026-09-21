"""QUEM-JOGA-E-QUEM-VIBRA-01 — num jogo de um jogador, um controle vibra.

A correção é dela, 20/09/2026, e derrubou a premissa de uma sprint inteira:

    "na real o certo não era somente o controle do player 1 receber a vibração?
     pq é um jogo de um player e o erro era que o player 3 tava recebendo a
     vibração de forma espelhada e somente ele diferente dos demais bt que
     estavam corretos estava recebendo."

**AS RÉGUAS AQUI COBREM A MESA DE QUATRO DE PROPÓSITO.** Uma régua que só
exercita «um jogando» passa verde sobre a regra «sempre o P1», que é
exatamente a que ela recusou ao escolher entre as três opções — e a família
`regua-que-mede-o-arranjo-facil` já mordeu esta casa neste mesmo dia, duas
vezes.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from hefesto_dualsense4unix.integrations.quem_o_jogo_le import (
    ENV_DO_JOGO,
    dono_do_vpad_pela_forja,
    evdevs_abertos_por,
    pids_de_jogo,
    quem_o_jogo_le,
    uniq_por_evdev,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

#: Faixa sintética da casa. NUNCA derivar de endereço real, nem em fixture —
#: a máscara preserva o OUI e um endereço "mascarado" ainda identifica o dono.
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
        assert evdevs_abertos_por([11], base) == {"event7", "event9"}


class TestAMesaDeQuatro:
    """O arranjo DIFÍCIL — o fácil («um jogando») não separa as regras."""

    def test_o_jogo_le_um_e_so_ele_vibra(self, tmp_path):
        """O caso dela: PRAGMATA, um jogador, três controles quietos.

        MORDIDA: devolver `set(fisicos)` em vez do que o jogo abriu.
        """
        inp = _input_de_mentira(
            tmp_path,
            {"event1": P1, "event2": P2, "event3": P3, "event4": P4},
        )
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(
            fisicos=MESA, raiz_proc=proc, raiz_input=inp
        ) == {P1}

    def test_o_jogo_le_dois_dos_quatro_e_so_esses_dois_vibram(self, tmp_path):
        """**A régua que separa a decisão dela de «sempre o P1».**

        Ela recusou a regra fixa no jogador 1 pensando no co-op do amigo dela.
        Uma régua que só exercita «um jogando» passaria verde sobre as duas
        regras, e esta casa já perdeu um dia inteiro com isso.

        MORDIDA: trocar o gate por `{fisicos[0]}`.
        """
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
    """Com máscara, o jogo abre o VIRTUAL — e ignorá-lo cala quem joga."""

    def test_o_vpad_se_traduz_no_fisico_que_o_forjou(self):
        """A forja é `blake2b` e não se inverte — mas se DERIVA.

        MORDIDA: devolver `None` sempre.
        """
        virtual = vpad_mac(P3, 1)
        assert dono_do_vpad_pela_forja(virtual, MESA) == P3

    def test_a_forja_nao_depende_do_numero_do_jogador(self):
        """É o que torna a tradução pura.

        O número é REUSADO (`_next_player_index` devolve o menor livre e o
        teardown o devolve ao poço), e a `COOP-QUE-NÃO-DESMONTA-01/E3`
        desacoplou o MAC dele de propósito.
        """
        assert len({vpad_mac(P2, n) for n in (1, 2, 3, 4)}) == 1

    def test_o_jogo_lendo_so_o_vpad_ainda_acha_o_dono(self, tmp_path):
        """O caso da mesa dela: máscara Xbox, e o jogo nunca abre o físico.

        MORDIDA: não passar `dono_do_vpad` — o resultado vira vazio e o
        controle de quem está jogando fica mudo.
        """
        virtual = vpad_mac(P1, 1)
        inp = _input_de_mentira(tmp_path, {"event1": virtual, "event2": P3})
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(
            fisicos=MESA,
            dono_do_vpad=lambda v: dono_do_vpad_pela_forja(v, MESA),
            raiz_proc=proc,
            raiz_input=inp,
        ) == {P1}

    def test_vpad_sem_dono_nao_vira_chute(self, tmp_path):
        """Um vpad que caiu no piso (`player_mac`) não pertence a ninguém.

        Chutar aqui faria um controle vibrar na mão de quem não está jogando —
        o defeito que ela reportou.
        """
        inp = _input_de_mentira(tmp_path, {"event1": "02:fe:00:00:00:01"})
        proc = _proc_de_mentira(tmp_path, {77: (True, ["event1"])})
        assert quem_o_jogo_le(
            fisicos=MESA,
            dono_do_vpad=lambda v: dono_do_vpad_pela_forja(v, MESA),
            raiz_proc=proc,
            raiz_input=inp,
        ) == set()


class TestOGateEstaLigado:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_subsystem_consulta_quem_joga_antes_de_decidir_o_modo(self):
        """MORDIDA: tirar a chamada a `_quem_o_jogo_le` do `_casar_as_pontes`.

        Sem ela o gate existe, tem régua verde, e o produto segue mandando
        háptica para quem não joga — que é exatamente o estado de 20/09 às
        13h36, com o P3 espelhando o jogo do P1.
        """
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py"
        ).read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def _casar_as_pontes") :]
        corpo = corpo[: corpo.index('modo = (')]
        assert "self._quem_o_jogo_le(controles)" in corpo, (
            "o gate não é consultado dentro de `_casar_as_pontes`"
        )

    def test_o_modo_haptica_exige_os_dois_sinais(self):
        """O canal aberto E o jogo lendo aquele controle.

        Só o primeiro deixava três controles vibrarem num jogo de um jogador.

        MORDIDA: tirar `o_jogo_le_este` da condição.
        """
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py"
        ).read_text(encoding="utf-8")
        i = fonte.index('modo = (')
        condicao = fonte[i : i + 240]
        assert "o_jogo_le_este" in condicao, "o gate saiu da condição do modo"
        assert "sink_esta_tocando" in condicao, "o sinal do canal saiu"


@pytest.mark.parametrize("quem", [P1, P2, P3, P4])
def test_qualquer_um_dos_quatro_pode_ser_o_que_joga(tmp_path, quem):
    """Nenhum índice é privilegiado — é o que a decisão dela pede.

    MORDIDA: cravar `P1` no gate. Três dos quatro casos reprovam.
    """
    inp = _input_de_mentira(
        tmp_path, {f"event{i + 1}": u for i, u in enumerate(MESA)}
    )
    evento = f"event{MESA.index(quem) + 1}"
    proc = _proc_de_mentira(tmp_path, {77: (True, [evento])})
    assert quem_o_jogo_le(fisicos=MESA, raiz_proc=proc, raiz_input=inp) == {quem}
