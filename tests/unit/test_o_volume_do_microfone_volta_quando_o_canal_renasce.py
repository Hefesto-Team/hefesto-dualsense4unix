"""O volume do microfone é do CONTROLE: o nó que renasce recebe de volta o do perfil ou o da tela.

O servidor de som é o de mentira e guarda o volume de cada nó. O canal e a voz são os reais
(``canal_do_microfone`` e ``microfone_filtrado``), com o ``pipewire`` e o ``parec`` de mentira.
Renomear o canal derruba e sobe o filtro, e o nó novo nasce no volume de nascença (100): o dono
em ``audio_control`` guarda o último pedido de cada controle e, avisado do nó que nasce, escreve
o valor nele.

MORDIDAS: tirar o ``avisar_no_de_pe`` de ``microfone_filtrado.abrir`` reprova o renascimento, a
ativação que chega antes do nó e o cru sem voz; tirar o ``guardar_o_volume_do_controle`` do
``pedir`` reprova a ativação que chega antes do nó; tirar o do ``mic.volume.set`` reprova o valor
da tela.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.core.formas_do_endereco import mascarar
from hefesto_dualsense4unix.integrations import (
    audio_control,
    canal_do_microfone,
    microfone_filtrado,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import marca_do_aparelho
from hefesto_dualsense4unix.profiles.manager import PEDIDOS_DO_VOLUME_DO_MIC
from hefesto_dualsense4unix.utils.logging_config import (
    EVENTOS_DE_ESTADO_NORMAL,
    desce_o_estado_normal,
)

MESA = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "02:fe:00:00:00:03", "02:fe:00:00:00:04")
VOLUMES = (49, 32, 39, 97)
CABO = "alsa_input.usb-fake-00.HiFi__Mic__source"
NASCENCA = 100
FRASE = "o volume do perfil não voltou ao canal que renasceu"


def _cru(uniq: str) -> str:
    return f"hefesto_mic_{marca_do_aparelho(uniq)}"


def _voz(uniq: str) -> str:
    return f"hefesto_mic_voz_{marca_do_aparelho(uniq)}"


class _Som:
    """O `pactl` de mentira: nós com volume e o nó fantasma que a lista traz e a escrita recusa."""

    def __init__(self) -> None:
        self.nos: dict[str, int] = {}
        self.fantasmas: set[str] = set()
        self.escritas: list[tuple[str, str, int]] = []

    def nasce(self, *nomes: str) -> None:
        for nome in nomes:
            self.fantasmas.discard(nome)
            self.nos[nome] = NASCENCA

    def morre(self, nome: str, *, fantasma: bool = False) -> None:
        self.nos.pop(nome, None)
        if fantasma:
            self.fantasmas.add(nome)

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            nomes = list(self.nos) + sorted(self.fantasmas)
            texto = "".join(f"{i}\t{n}\tPipeWire\ts16le\tIDLE\n" for i, n in enumerate(nomes))
            return subprocess.CompletedProcess(argv, 0, stdout=texto, stderr="")
        if argv[:2] == ["pactl", "set-source-volume"]:
            nome, pct = argv[2], int(argv[3].rstrip("%"))
            if nome not in self.nos:
                self.escritas.append(("recusada", nome, pct))
                return subprocess.CompletedProcess(
                    argv, 1, stdout="", stderr="Failed to get source information: No such entity")
            self.nos[nome] = pct
            self.escritas.append(("escrita", nome, pct))
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if argv[:2] == ["pactl", "get-source-volume"] and argv[2] in self.nos:
            pct = self.nos[argv[2]]
            return subprocess.CompletedProcess(
                argv, 0, stdout=f"Volume: mono: 1 / {pct}% / -0.00 dB\n", stderr="")
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")

    def escritas_em(self, nome: str) -> list[int]:
        return [pct for ok, no, pct in self.escritas if ok == "escrita" and no == nome]


class _Processo:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.stdout = io.BytesIO(b"")
        self.codigo: int | None = None

    def poll(self) -> int | None:
        return self.codigo

    def terminate(self) -> None:
        self.codigo = 0

    def kill(self) -> None:
        self.codigo = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.codigo is None:
            self.codigo = 0
        return self.codigo


class _Source:
    def __init__(self, nome: str, descricao: str) -> None:
        self.nome = nome
        self.descricao = descricao

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        return None


class _Mundo:
    def __init__(self, som: _Som) -> None:
        self.som = som

    def abrir(self, uniq: str, descricao: str = "Microfone do Controle 1", *,
              cabo: bool = False) -> Any:
        return canal_do_microfone.abrir(
            uniq, descricao, fonte=CABO if cabo else None, fabrica=_Source,
            lancar=_Processo, rodar=lambda _a: True)

    def renomear(self, uniq: str, descricao: str) -> Any:
        return canal_do_microfone.renomear(
            uniq, descricao, fabrica=_Source, lancar=_Processo, rodar=lambda _a: True)

    def perfil(self, uniq: str, volume: int, origem: str = "replug") -> None:
        PEDIDOS_DO_VOLUME_DO_MIC.pedir(uniq, (None, volume, uniq, origem))
        assert PEDIDOS_DO_VOLUME_DO_MIC.esperar(5.0)

    def sobe_a_mesa(self, uniqs: tuple[str, ...]) -> None:
        for uniq in uniqs:
            self.abrir(uniq)
            self.som.nasce(_cru(uniq), _voz(uniq))
        assert audio_control.esperar_os_avisos(5.0)


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Mundo]:
    som = _Som()
    monkeypatch.setattr(audio_control, "_rodar_pelo_recuo", som)
    monkeypatch.setattr(audio_control, "PASSO_DO_NO_NASCER_S", 0.005)
    monkeypatch.setattr(audio_control, "TETO_DO_NO_NASCER_S", 4.0)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/pipewire")
    monkeypatch.setattr(microfone_filtrado, "_lancar_processo", _Processo)
    monkeypatch.setattr(canal_do_microfone, "_lancar_processo", _Processo)
    monkeypatch.setattr(canal_do_microfone, "_passar_a_escolha_do_usuario", lambda *_a: None)
    monkeypatch.setattr(canal_do_microfone, "_a_palavra_do_usuario", lambda _u: None)
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio

    monkeypatch.setattr(dualsense_bt_audio, "pactl_mudo", lambda: False)
    audio_control.esquecer_os_volumes_dos_controles()
    microfone_filtrado.fechar_todos()
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    yield _Mundo(som)
    audio_control.esperar_os_avisos(5.0)
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    microfone_filtrado.fechar_todos()
    audio_control.esquecer_os_volumes_dos_controles()


def _aguardar(condicao: Callable[[], bool], teto_s: float = 5.0) -> bool:
    limite = time.monotonic() + teto_s
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(0.005)
    return condicao()


class TestOCanalRenasceEOVolumeVolta:
    def test_dois_controles_o_de_um_renasce_e_leva_o_volume_dele(self, mundo: _Mundo) -> None:
        a, b = MESA[0], MESA[1]
        mundo.sobe_a_mesa((a, b))
        mundo.perfil(a, VOLUMES[0])
        mundo.perfil(b, VOLUMES[1])
        assert mundo.som.nos[_voz(a)] == VOLUMES[0]
        assert mundo.som.nos[_voz(b)] == VOLUMES[1]

        escritas_no_outro = len(mundo.som.escritas_em(_voz(b)))
        mundo.som.morre(_voz(a), fantasma=True)
        mundo.som.morre(_cru(a))
        mundo.renomear(a, "Microfone do Controle 3")
        assert _aguardar(lambda: any(e[0] == "recusada" for e in mundo.som.escritas)), (
            "o pedido não tentou o nó que a lista ainda trazia")
        mundo.som.nasce(_cru(a), _voz(a))
        assert audio_control.esperar_os_avisos(5.0)

        assert mundo.som.nos[_voz(a)] == VOLUMES[0], FRASE
        assert mundo.som.nos[_voz(b)] == VOLUMES[1], "o volume do outro controle mudou"
        assert len(mundo.som.escritas_em(_voz(b))) == escritas_no_outro, (
            "o canal de um renasceu e o outro foi reescrito")

    def test_a_escrita_recusada_nao_desiste_e_vale_no_no_que_nasce(self, mundo: _Mundo) -> None:
        a = MESA[2]
        mundo.sobe_a_mesa((a,))
        mundo.perfil(a, VOLUMES[2])
        mundo.som.morre(_voz(a), fantasma=True)
        mundo.renomear(a, "Microfone do Controle 4")
        assert _aguardar(lambda: any(e[0] == "recusada" for e in mundo.som.escritas))
        mundo.som.nasce(_voz(a))
        assert audio_control.esperar_os_avisos(5.0)
        assert mundo.som.nos[_voz(a)] == VOLUMES[2], FRASE

    def test_o_valor_da_tela_volta_no_no_novo(
        self, mundo: _Mundo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
        from hefesto_dualsense4unix.daemon.state_store import StateStore

        a = MESA[3]
        mundo.sobe_a_mesa((a,))
        mundo.perfil(a, VOLUMES[3])

        class _Host(IpcHandlersMixin):
            def __init__(self) -> None:
                self.controller: Any = SimpleNamespace()
                self.daemon = SimpleNamespace(controller=self.controller)
                self.store = StateStore()

        resposta = asyncio.run(_Host()._handle_mic_volume_set({"volume": 21, "uniq": a}))
        assert resposta["status"] == "ok"
        assert mundo.som.nos[_voz(a)] == 21

        mundo.som.morre(_voz(a))
        mundo.som.morre(_cru(a))
        mundo.renomear(a, "Microfone do Controle 2")
        mundo.som.nasce(_cru(a), _voz(a))
        assert audio_control.esperar_os_avisos(5.0)
        assert mundo.som.nos[_voz(a)] == 21, (
            "o nó novo voltou ao valor do perfil, e o último pedido foi o da tela")

    def test_o_pedido_da_tela_sem_fonte_fica_guardado(self, mundo: _Mundo) -> None:
        import asyncio

        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
        from hefesto_dualsense4unix.daemon.state_store import StateStore

        a = MESA[0]

        class _Host(IpcHandlersMixin):
            def __init__(self) -> None:
                self.controller: Any = SimpleNamespace()
                self.daemon = SimpleNamespace(controller=self.controller)
                self.store = StateStore()

        resposta = asyncio.run(_Host()._handle_mic_volume_set({"volume": 64, "uniq": a}))
        assert resposta["status"] == "sem_fonte"
        mundo.sobe_a_mesa((a,))
        assert mundo.som.nos[_voz(a)] == 64, "o gesto da tela sem nó não esperou o nó nascer"


class TestAAtivacaoChegaAntesDoNo:
    @pytest.mark.parametrize("cabo", [True, False], ids=["cabo", "radio"])
    def test_o_no_que_nasce_leva_o_volume_pedido(self, mundo: _Mundo, cabo: bool) -> None:
        a = MESA[1]
        mundo.perfil(a, VOLUMES[1])
        assert mundo.som.escritas == [], "escreveu num nó que não existia"
        mundo.abrir(a, cabo=cabo)
        mundo.som.nasce(_cru(a), _voz(a))
        assert audio_control.esperar_os_avisos(5.0)
        assert mundo.som.nos[_voz(a)] == VOLUMES[1], FRASE

    def test_sem_a_voz_o_cru_e_o_no_do_controle(
        self, mundo: _Mundo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _n: None)
        a = MESA[2]
        mundo.perfil(a, VOLUMES[2])
        mundo.abrir(a)
        mundo.som.nasce(_cru(a))
        assert audio_control.esperar_os_avisos(5.0)
        assert mundo.som.nos[_cru(a)] == VOLUMES[2], FRASE

    def test_sem_volume_guardado_nada_se_escreve(self, mundo: _Mundo) -> None:
        a = MESA[3]
        mundo.abrir(a)
        mundo.som.nasce(_cru(a), _voz(a))
        assert audio_control.esperar_os_avisos(5.0)
        assert mundo.som.escritas == []
        assert mundo.som.nos[_voz(a)] == NASCENCA


class TestOsQuatroNosDePe:
    def test_cada_escrita_leva_o_volume_do_seu_controle(self, mundo: _Mundo) -> None:
        mundo.sobe_a_mesa(MESA)
        for uniq, volume in zip(MESA, VOLUMES, strict=True):
            mundo.perfil(uniq, volume)
        for uniq, volume in zip(MESA, VOLUMES, strict=True):
            assert mundo.som.nos[_voz(uniq)] == volume
            assert mundo.som.escritas_em(_voz(uniq)) == [volume]
        assert not [n for n in mundo.som.nos if n.startswith("hefesto_mic_voz_")
                    and n not in {_voz(u) for u in MESA}]

    def test_quatro_renascem_em_ordem_trocada_e_cada_um_volta_ao_seu(self, mundo: _Mundo) -> None:
        mundo.sobe_a_mesa(MESA)
        for uniq, volume in zip(MESA, VOLUMES, strict=True):
            mundo.perfil(uniq, volume)
        ordem = (2, 0, 3, 1)
        for i in ordem:
            mundo.som.morre(_voz(MESA[i]))
            mundo.som.morre(_cru(MESA[i]))
            mundo.renomear(MESA[i], f"Microfone do Controle {i + 5}")
            mundo.som.nasce(_cru(MESA[i]), _voz(MESA[i]))
        assert audio_control.esperar_os_avisos(8.0)
        for uniq, volume in zip(MESA, VOLUMES, strict=True):
            assert mundo.som.nos[_voz(uniq)] == volume, FRASE


class TestODesfechoSaiEmInfo:
    def test_o_evento_nao_e_dos_que_o_diario_derruba_no_info(self) -> None:
        assert "mic_volume_desfecho" not in EVENTOS_DE_ESTADO_NORMAL
        evento = {"event": "mic_volume_desfecho"}
        assert desce_o_estado_normal(None, "info", evento) is evento

    def test_aplicado_sem_fonte_e_recusado_um_por_episodio_e_por_controle(
        self, mundo: _Mundo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        a, b = MESA[0], MESA[1]
        with capture_logs() as linhas:
            mundo.perfil(a, VOLUMES[0])
            mundo.sobe_a_mesa((b,))
            mundo.perfil(b, VOLUMES[1])
            monkeypatch.setattr(audio_control, "TETO_DO_NO_NASCER_S", 0.05)
            mundo.som.morre(_voz(b), fantasma=True)
            mundo.renomear(b, "Microfone do Controle 4")
            assert audio_control.esperar_os_avisos(5.0)
        desfechos = [
            (linha["controle"], linha["desfecho"], linha["origem"])
            for linha in linhas
            if linha["event"] == "mic_volume_desfecho" and linha["log_level"] == "info"
        ]
        controle_a = mascarar(a)
        controle_b = mascarar(b)
        assert (controle_a, "sem_fonte", "replug") in desfechos
        assert (controle_b, "aplicado", "replug") in desfechos
        assert (controle_b, "recusado", "no_de_pe") in desfechos
