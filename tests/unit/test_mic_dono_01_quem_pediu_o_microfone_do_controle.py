"""MIC-DONO-01 — a mesma pergunta, feita a dois donos diferentes, dá duas respostas.

O `doctor.sh` e o `system_check.py` perguntam a MESMA coisa: *a pessoa quer o
microfone do controle como fonte padrão do sistema?* O doctor responde com
CINCO degraus (`_prefere_mic_do_dualsense`, `doctor.sh:1199`); o `system_check`
respondia com UM — uma variável de ambiente que o daemon **nunca recebe**::

    $ systemctl --user show hefesto-dualsense4unix.service -p Environment
    Environment=PYTHONUNBUFFERED=1

E o estado em que os dois se contradizem é o que o PRÓPRIO INSTALADOR produz.
`install.sh --keep-dualsense-mic` grava a marca do gesto (`install.sh:4039`) e
não instala o drop-in 51. A partir daí, a cada boot do daemon::

    doctor.sh ....... [OK] microfone ativo é o DualSense (foi pedido)
    system_check .... WirePlumber fixou o DualSense — rode doctor.sh --fix

**O produto mandava desfazer a escolha que a pessoa fez no instalador** — e
`--fix` instala o 51, que rebaixa justamente o microfone pedido. Para quem usa
o mic do controle por acessibilidade, seguir a instrução do produto custa o
microfone.

Esta régua trava os cinco degraus e, acima deles, a única coisa que importa: os
dois lados da casa respondem IGUAL. O `doctor.sh` é o dono da hierarquia; o
Python a espelha.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import system_check as sc

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

D51 = "51-hefesto-dualsense-no-default-source.conf"
D52 = "52-hefesto-dualsense-disable-source.conf"
VARIAVEL = "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED"


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Um lar de mentira com os dois endereços que a função lê.

    O `XDG_STATE_HOME` é desviado de verdade — e é por isso que a função tem de
    lê-lo NA HORA. Uma cópia no topo do módulo congelaria o lar real.
    """
    lar = tmp_path / "lar"
    conf = lar / ".config" / "wireplumber" / "wireplumber.conf.d"
    estado = lar / ".local" / "state"
    conf.mkdir(parents=True)
    estado.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_STATE_HOME", str(estado))
    monkeypatch.delenv(VARIAVEL, raising=False)

    class Mesa:
        def __init__(self) -> None:
            self.conf = conf

        def dropin(self, nome: str) -> None:
            (conf / nome).write_text("# de mentira\n", encoding="utf-8")

        def marca(self) -> None:
            alvo = sc._marca_do_gesto_do_mic()
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text("gesto=de mentira\n", encoding="utf-8")

    return Mesa()


class TestOsCincoDegraus:
    def test_1_quem_desligou_de_proposito_vence_a_variavel(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O drop-in 52 é «o controle é só-HID», e vem ANTES de tudo.

        MORDIDA: apagar o degrau 1 faz a variável ganhar de quem desligou o
        microfone de propósito.
        """
        mesa.dropin(D52)
        monkeypatch.setenv(VARIAVEL, "1")
        assert sc._dualsense_mic_intended() is False

    def test_2_o_opt_in_por_ambiente_continua_valendo(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quem roda o daemon à mão, ou põe um drop-in de systemd, não se perde.

        O degrau 2 não morre com esta cura — ele deixa de ser o ÚNICO sinal.
        """
        monkeypatch.setenv(VARIAVEL, "1")
        assert sc._dualsense_mic_intended() is True

    def test_3_o_dropin_51_e_a_politica_default_do_install(self, mesa) -> None:
        """Com o 51 no lugar, o controle é a ÚLTIMA opção — não a primeira.

        MORDIDA: apagar o degrau 3 faz a marca de uma instalação ANTIGA passar
        por cima da política que o install acabou de escrever.
        """
        mesa.dropin(D51)
        mesa.marca()
        assert sc._dualsense_mic_intended() is False

    def test_4_a_marca_do_gesto_e_o_que_o_keep_dualsense_mic_deixa(
        self, mesa
    ) -> None:
        """**O CASO QUE ORIGINOU ESTA RÉGUA.**

        Sem o 51 e com a marca: é o estado de quem instalou com
        `--keep-dualsense-mic`. Antes da cura isto devolvia False e o daemon
        avisava a pessoa para desligar o próprio microfone.

        MORDIDA: apagar o degrau 4 devolve exatamente o defeito de 16/09.
        """
        mesa.marca()
        assert sc._dualsense_mic_intended() is True

    def test_5_nao_sei_nunca_e_ela_pediu(self, mesa) -> None:
        """Nem o 51 nem a marca: a ausência tem DUAS origens e o disco não as separa.

        Lê-las como uma já custou uma noite em 04/08/2026 (DROPIN-AMBIGUO-01).
        """
        assert sc._dualsense_mic_intended() is False


class TestOAvisoNaoMandaDesfazerAEscolhaDela:
    def test_com_a_marca_o_daemon_cala_sobre_o_microfone(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PONTA QUE CHEGA NA PESSOA — e é ela que importa.

        O degrau certo não vale nada se o aviso sair assim mesmo. Aqui o
        WirePlumber ESTÁ com o DualSense fixado (é o que ela pediu) e o produto
        tem de ficar quieto sobre isso.
        """
        mesa.marca()
        monkeypatch.setattr(sc, "_wireplumber_hijacks_mic", lambda: True)
        monkeypatch.setattr(sc, "_udev_hotplug_outdated", lambda: False)
        assert sc.system_warnings() == []

    def test_sem_sinal_nenhum_o_aviso_continua_saindo(
        self, mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura não pode calar o aviso legítimo — senão troca um defeito por outro.

        MORDIDA: fazer `_dualsense_mic_intended` devolver True sempre.
        """
        monkeypatch.setattr(sc, "_wireplumber_hijacks_mic", lambda: True)
        monkeypatch.setattr(sc, "_udev_hotplug_outdated", lambda: False)
        avisos = sc.system_warnings()
        assert len(avisos) == 1 and "WirePlumber" in avisos[0]


class TestOsDoisLadosDaCasaConcordam:
    def test_o_python_espelha_os_cinco_degraus_do_doctor(self) -> None:
        """O `doctor.sh` é o DONO da hierarquia; o Python a espelha.

        Se alguém acrescentar um sexto sinal ao doctor e esquecer o Python, a
        contradição volta — e ela volta calada, que é o pior jeito. Esta régua
        não compara aritmética: ela confere que os TRÊS endereços que os dois
        lados leem são os mesmos, por nome.

        MORDIDA: trocar o nome de um drop-in no Python.
        """
        texto = DOCTOR.read_text(encoding="utf-8")
        bloco = re.search(
            r"_prefere_mic_do_dualsense\(\)\s*\{(.*?)\n\}", texto, re.S
        )
        assert bloco, "`_prefere_mic_do_dualsense` sumiu do doctor.sh"
        corpo = bloco.group(1)

        for nome in (D51, D52):
            assert nome in corpo, f"o doctor não cita mais {nome}"
            assert nome in Path(sc.__file__).read_text(encoding="utf-8"), (
                f"o system_check não cita {nome}, que o doctor pesa"
            )

        assert "_marca_do_gesto_do_mic" in corpo
        assert sc._marca_do_gesto_do_mic().name == "mic-do-dualsense-pedido.conf", (
            "o Python e o doctor apontam para marcas com nomes diferentes"
        )
        assert VARIAVEL in corpo, "o doctor não pesa mais a variável de ambiente"

    def test_o_caminho_da_marca_bate_com_o_do_doctor(self) -> None:
        """O `doctor.sh` monta o caminho com `XDG_STATE_HOME` e o mesmo sufixo."""
        texto = DOCTOR.read_text(encoding="utf-8")
        bloco = re.search(
            r"_marca_do_gesto_do_mic\(\)\s*\{(.*?)\n\}", texto, re.S
        )
        assert bloco, "`_marca_do_gesto_do_mic` sumiu do doctor.sh"
        corpo = bloco.group(1)
        assert "XDG_STATE_HOME" in corpo
        assert "hefesto-dualsense4unix/mic-do-dualsense-pedido.conf" in corpo
