"""SOM-ECO-02 — a ponte de som lia o MICROFONE e mandava ao alto-falante."""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as afb

SINKS_SHORT = (
    "75833\thefesto_som_000003\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
    "75840\talsa_output.pci-0000_0a_00.1.hdmi-stereo\tPipeWire\ts16le 2ch\tRUNNING\n"
)


PIPEWIRE_PULSE = "PulseAudio (on PipeWire 1.0.5)"


def _pactl(
    monkeypatch: pytest.MonkeyPatch,
    *,
    saida: str = SINKS_SHORT,
    rc: int = 0,
    servidor: str = PIPEWIRE_PULSE,
):
    """Dubla o `pactl list sinks short` e o `pactl info`; o resto passa reto."""
    real = subprocess.run

    def run(argv, *a, **k):
        if list(argv[:4]) == ["pactl", "list", "sinks", "short"]:
            return SimpleNamespace(returncode=rc, stdout=saida, stderr="")
        if list(argv[:2]) == ["pactl", "info"]:
            texto = f"Server String: /run/user/1000/pulse/native\nServer Name: {servidor}\n"
            return SimpleNamespace(returncode=0, stdout=texto, stderr="")
        return real(argv, *a, **k)

    monkeypatch.setattr(afb.subprocess, "run", run)


class TestOAlvoVaiPorSerial:
    def test_o_pw_record_e_mirado_pelo_object_serial(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**O CASO QUE ORIGINOU ESTA RÉGUA.**"""
        _pactl(monkeypatch)
        monkeypatch.setattr(afb.shutil, "which", lambda b: f"/usr/bin/{b}")
        argv = afb.argv_do_gravador("hefesto_som_000003.monitor")
        assert argv[0] == "pw-record"
        assert "-P" in argv, "o gravador subiu sem rótulo — a conferência fica cega"
        assert "--target=75833" in argv, f"não foi pelo serial: {argv}"
        assert not any("hefesto_som_000003" in a for a in argv), (
            "o NOME voltou para a linha de comando, e é ele que cai no microfone"
        )

    def test_o_serial_do_sink_serve_para_o_monitor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pedir `<sink>.monitor` resolve pelo serial do SINK — medido."""
        _pactl(monkeypatch)
        assert afb.serial_do_no("hefesto_som_000003.monitor") == 75833
        assert afb.serial_do_no("hefesto_som_000003") == 75833

    def test_sem_serial_o_parec_assume_e_acerta_pelo_nome(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nó ausente do `pactl`: o `pw-record` sai de cena e o `parec` entra."""
        _pactl(monkeypatch, saida="75840\toutro_no\tPipeWire\ts16le\tRUNNING\n")
        monkeypatch.setattr(afb.shutil, "which", lambda b: f"/usr/bin/{b}")
        argv = afb.argv_do_gravador("hefesto_som_000003.monitor")
        assert argv[0] == "parec", f"o pw-record ficou sem serial e mesmo assim veio: {argv}"
        assert "--device=hefesto_som_000003.monitor" in argv

    def test_sem_pactl_nenhum_ainda_sobra_o_parec(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Servidor em recuo / sem `pactl`: `serial_do_no` devolve None e não levanta."""
        def run(argv, *a, **k):
            raise OSError("sem pactl")

        monkeypatch.setattr(afb.subprocess, "run", run)
        monkeypatch.setattr(afb.shutil, "which", lambda b: f"/usr/bin/{b}")
        assert afb.serial_do_no("hefesto_som_000003") is None
        assert afb.argv_do_gravador("hefesto_som_000003.monitor")[0] == "parec"

    def test_a_fonte_vazia_continua_recusada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A guarda velha não morre com a nova — ela só deixou de ser a única."""
        monkeypatch.setattr(afb.shutil, "which", lambda b: f"/usr/bin/{b}")
        assert afb.argv_do_gravador("") == []

    def test_so_o_parec_na_maquina_continua_funcionando(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Máquina sem `pw-record`: o `parec` assume, com ou sem serial."""
        _pactl(monkeypatch)
        monkeypatch.setattr(
            afb.shutil, "which", lambda b: None if b == "pw-record" else f"/usr/bin/{b}"
        )
        argv = afb.argv_do_gravador("hefesto_som_000003.monitor")
        assert argv[0] == "parec"

    def test_no_pulseaudio_o_indice_nao_vira_serial_do_pipewire(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PulseAudio no som e `pw-record` instalado: o `parec` assume."""
        _pactl(monkeypatch, servidor="pulseaudio")
        monkeypatch.setattr(afb.shutil, "which", lambda b: f"/usr/bin/{b}")
        argv = afb.argv_do_gravador("hefesto_som_000003.monitor")
        assert argv[0] == "parec", f"o índice do PulseAudio foi ao pw-record: {argv}"
        assert "--device=hefesto_som_000003.monitor" in argv

    def test_o_servidor_sem_resposta_nao_e_pipewire(self) -> None:
        """Sem `pactl info`, a dúvida vai para o gravador que acerta pelo nome."""
        assert afb.o_servidor_e_o_pipewire(lambda _argv: None) is False
        assert afb.o_servidor_e_o_pipewire(
            lambda _argv: f"Server Name: {PIPEWIRE_PULSE}\n"
        ) is True
        assert afb.o_servidor_e_o_pipewire(lambda _argv: "Server Name: pulseaudio\n") is False


def _dump(origem: str, *, rotulo: str = "hefesto-ponte-000003",
          vizinho: tuple[str, str] | None = None) -> str:
    """Um `pw-dump` de mentira: o gravador `rotulo` alimentado por `origem`."""
    objetos = [
        {"id": 10, "type": "PipeWire:Interface:Node",
         "info": {"props": {"node.name": origem}}},
        {"id": 20, "type": "PipeWire:Interface:Node",
         "info": {"props": {"node.name": rotulo,
                            "application.process.id": None}}},
        {"id": 30, "type": "PipeWire:Interface:Link",
         "info": {"input-node-id": 20, "output-node-id": 10, "props": {}}},
    ]
    if vizinho:
        rot_v, org_v = vizinho
        objetos += [
            {"id": 40, "type": "PipeWire:Interface:Node",
             "info": {"props": {"node.name": org_v}}},
            {"id": 50, "type": "PipeWire:Interface:Node",
             "info": {"props": {"node.name": rot_v}}},
            {"id": 60, "type": "PipeWire:Interface:Link",
             "info": {"input-node-id": 50, "output-node-id": 40, "props": {}}},
        ]
    return json.dumps(objetos)


def _pwlink(monkeypatch: pytest.MonkeyPatch, saida: str, rc: int = 0):
    real = subprocess.run

    def run(argv, *a, **k):
        if list(argv[:1]) == ["pw-dump"]:
            return SimpleNamespace(returncode=rc, stdout=saida, stderr="")
        return real(argv, *a, **k)

    monkeypatch.setattr(afb.subprocess, "run", run)


class TestAConferenciaDepoisDeSubir:
    """A metade que MORDE: o serial é resolvido antes, e o nó pode sumir no meio."""

    def test_reconhece_o_alvo_certo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _pwlink(monkeypatch, _dump("hefesto_som_000003"))
        assert afb.conferir_o_alvo_do_gravador("hefesto-ponte-000003") == (
            "hefesto_som_000003"
        )

    def test_flagra_o_gravador_ligado_ao_microfone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**O flagrante que a cura existe para dar.**"""
        _pwlink(monkeypatch, _dump("hefesto_mic_000003"))
        ligado = afb.conferir_o_alvo_do_gravador("hefesto-ponte-000003")
        assert ligado == "hefesto_mic_000003", (
            "a conferência não viu que o gravador pegou o microfone"
        )

    def test_nao_sei_nunca_e_esta_certo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sem `pw-link` ou com ele reprovando: `None`, e o chamador não derruba."""
        def run(argv, *a, **k):
            raise OSError("sem pw-link")

        monkeypatch.setattr(afb.subprocess, "run", run)
        assert afb.conferir_o_alvo_do_gravador("hefesto-ponte-000003") is None

        _pwlink(monkeypatch, "", rc=1)
        assert afb.conferir_o_alvo_do_gravador("hefesto-ponte-000003") is None

        _pwlink(monkeypatch, "isto não é json")
        assert afb.conferir_o_alvo_do_gravador("hefesto-ponte-000003") is None

    def test_cada_controle_tem_o_seu_rotulo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**Numa mesa de quatro há um gravador POR CONTROLE.**"""
        _pwlink(monkeypatch, _dump(
            "hefesto_som_000003",
            vizinho=("hefesto-ponte-0000d8", "hefesto_mic_0000d8"),
        ))
        assert afb.conferir_o_alvo_do_gravador("hefesto-ponte-000003") == (
            "hefesto_som_000003"
        )
        assert afb.conferir_o_alvo_do_gravador("hefesto-ponte-0000d8") == (
            "hefesto_mic_0000d8"
        )

    def test_o_rotulo_carrega_a_peca(self) -> None:
        """Dois controles, dois rótulos — senão a conferência é a do vizinho."""
        a = afb.rotulo_do_gravador(uniq="aa:bb:cc:00:00:03")
        b = afb.rotulo_do_gravador(uniq="aa:bb:cc:00:00:d8")
        assert a != b, "o rótulo não distingue as peças"
        assert a.startswith("hefesto-ponte-")

    def test_a_mesa_de_quatro_em_dois_papeis_da_oito_rotulos(self) -> None:
        """**A RÉGUA ANTERIOR MEDIA O ARRANJO FÁCIL, e passou sobre o defeito.**"""
        uniqs = ["aa:bb:cc:00:00:03", "aa:bb:cc:00:00:ab",
                 "aa:bb:cc:00:00:d8", "aa:bb:cc:00:00:f0"]
        rotulos = [afb.rotulo_do_gravador(uniq=u, papel=papel)
                   for u in uniqs for papel in ("som", "haptica")]
        assert len(set(rotulos)) == 8, (
            f"oito gravadores, {len(set(rotulos))} nome(s): {sorted(set(rotulos))}"
        )

    def test_sem_uniq_o_rotulo_e_vazio_e_nao_generico(self) -> None:
        """Ausência é resposta: sem identidade, NENHUM nome."""
        assert afb.rotulo_do_gravador(uniq="") == ""
        assert afb.rotulo_do_gravador(uniq="", papel="haptica") == ''


class TestACuraEstaLIGADA:
    def test_o_chamador_confere_e_derruba(self) -> None:
        """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""
        from pathlib import Path

        fonte = Path(afb.__file__).read_text(encoding="utf-8")
        assert "conferir_o_alvo_do_gravador(rotulo)" in fonte, (
            "o chamador não confere o alvo — a ponte pode subir no microfone"
        )
        assert "som_gravador_no_alvo_errado" in fonte, "o flagrante não vai ao journal"
        assert "som_gravador_alvo_nao_conferido" in fonte, (
            "«não conferido» tem de ser dito, senão lê-se como «conferido e certo»"
        )
