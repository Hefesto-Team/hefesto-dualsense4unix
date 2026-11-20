"""A gravação que funde segura a trava entre processos: a janela e o serviço não se apagam."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import textwrap
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from filelock import FileLock

from hefesto_dualsense4unix.utils import maquina, xdg_paths

PRAZO_S = 60
RODADAS_DO_MAQUINA = 5
NOMES_POR_PROCESSO = 60
REPETICOES_DO_PERFIL = 20
SOMAS_POR_PROCESSO = 30
SEGURA_A_TRAVA_S = 3

_QUEM_GRAVA_NOMES = textwrap.dedent(
    """
    import sys
    from hefesto_dualsense4unix.utils import maquina
    quem = sys.argv[1]
    sys.stdin.readline()
    for n in range(int(sys.argv[2])):
        assert maquina.gravar_o_nome_do_controle(f"aabbcc{quem}{n:05x}", f"P{quem}-{n}")
    """
)

_O_PAPEL_NO_PERFIL = textwrap.dedent(
    """
    import sys
    import threading
    from hefesto_dualsense4unix.profiles import loader, manager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, PonteConfirmada, Profile

    def dizer(texto):
        sys.stdout.write(texto + "\\n")
        sys.stdout.flush()

    def carimbar(perfil):
        ponte = PonteConfirmada(kind="gamepad", gamepad_flavor="dualsense", steam_input=True)
        dizer("segurando")
        sys.stdin.readline()
        return perfil.model_copy(update={"ponte": ponte}), None

    lido = None
    for pedido in sys.stdin:
        pedido = pedido.strip()
        if pedido == "zerar":
            loader.save_profile(Profile(name="corrida", match=MatchAny(), priority=10))
        elif pedido == "ler":
            lido = loader.load_profile("corrida")
        elif pedido == "espiar":
            fio = threading.Thread(target=loader.load_profile, args=("corrida",))
            fio.start()
            fio.join()
        elif pedido == "gravar":
            loader.save_profile(lido.model_copy(update={"priority": 77}), origem="interface-nova")
        elif pedido == "carimbar":
            manager.mudar_o_perfil("corrida", carimbar)
        elif pedido.startswith("somar"):
            for _ in range(int(pedido.split()[1])):
                manager.mudar_o_perfil(
                    "corrida", lambda p: (p.model_copy(update={"priority": p.priority + 1}), None))
        dizer("feito")
    """
)


def _ambiente(tmp_path: Path) -> dict[str, str]:
    lar = tmp_path / "lar"
    raiz_do_sys = tmp_path / "sys"
    raiz_do_sys.mkdir(exist_ok=True)
    ambiente = dict(os.environ)
    ambiente.update(
        HOME=str(lar),
        XDG_CONFIG_HOME=str(lar / ".config"),
        XDG_STATE_HOME=str(lar / ".local/state"),
        XDG_DATA_HOME=str(lar / ".local/share"),
        XDG_CACHE_HOME=str(lar / ".cache"),
        HEFESTO_RAIZ_DO_SYS=str(raiz_do_sys),
        HEFESTO_DUALSENSE4UNIX_FAKE="1",
    )
    return ambiente


@pytest.mark.parametrize("rodada", range(RODADAS_DO_MAQUINA))
def test_dois_processos_gravam_todos_os_nomes_no_maquina_json(tmp_path: Path, rodada: int) -> None:
    """D-1911-A-GRAVACAO-QUE-FUNDE-SEGURA-A-TRAVA: 120 nomes de dois processos, todos no disco."""
    ambiente = _ambiente(tmp_path)
    processos = [
        subprocess.Popen(
            [sys.executable, "-c", _QUEM_GRAVA_NOMES, str(quem), str(NOMES_POR_PROCESSO)],
            env=ambiente, stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for quem in (1, 2)
    ]
    for processo in processos:
        assert processo.stdin is not None
        processo.stdin.write("vai\n")
        processo.stdin.flush()
    for processo in processos:
        _, erro = processo.communicate(timeout=PRAZO_S)
        assert processo.returncode == 0, erro

    disco = json.loads(
        (tmp_path / "lar/.config/hefesto-dualsense4unix/maquina.json").read_text(encoding="utf-8")
    )
    assert len(disco["controles"]) == 2 * NOMES_POR_PROCESSO


class _Papel:
    def __init__(self, ambiente: dict[str, str]) -> None:
        self.processo = subprocess.Popen(
            [sys.executable, "-c", _O_PAPEL_NO_PERFIL], env=ambiente,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        )

    def pedir(self, pedido: str) -> None:
        assert self.processo.stdin is not None
        self.processo.stdin.write(pedido + "\n")
        self.processo.stdin.flush()

    def ouvir(self, esperado: str) -> None:
        assert self.processo.stdout is not None
        assert self.processo.stdout.readline().strip() == esperado

    def fechar(self) -> None:
        if self.processo.stdin is not None:
            self.processo.stdin.close()
        self.processo.wait(timeout=PRAZO_S)


@pytest.fixture
def janela_e_servico(tmp_path: Path) -> Iterator[tuple[_Papel, _Papel, Path]]:
    ambiente = _ambiente(tmp_path)
    janela, servico = _Papel(ambiente), _Papel(ambiente)
    yield janela, servico, tmp_path / "lar/.config/hefesto-dualsense4unix/profiles/corrida.json"
    janela.fechar()
    servico.fechar()


def _no_disco(arquivo: Path) -> dict[str, object]:
    return dict(json.loads(arquivo.read_text(encoding="utf-8")))


@pytest.mark.parametrize("outro_fio_le", [False, True])
def test_a_janela_que_leu_antes_do_carimbo_nao_apaga_a_ponte(
    janela_e_servico: tuple[_Papel, _Papel, Path], outro_fio_le: bool,
) -> None:
    """D-1911-A-GRAVACAO-QUE-FUNDE-SEGURA-A-TRAVA: o perfil inteiro relido sob a trava."""
    janela, servico, arquivo = janela_e_servico
    for _ in range(REPETICOES_DO_PERFIL):
        janela.pedir("zerar")
        janela.ouvir("feito")
        janela.pedir("ler")
        janela.ouvir("feito")
        servico.pedir("carimbar")
        servico.ouvir("segurando")
        servico.pedir("solta")
        servico.ouvir("feito")
        if outro_fio_le:
            janela.pedir("espiar")
            janela.ouvir("feito")
        janela.pedir("gravar")
        janela.ouvir("feito")

        disco = _no_disco(arquivo)
        assert disco["priority"] == 77
        assert disco.get("ponte") is not None


def test_a_janela_que_grava_durante_o_carimbo_espera_a_trava(
    janela_e_servico: tuple[_Papel, _Papel, Path],
) -> None:
    """D-1911-A-GRAVACAO-QUE-FUNDE-SEGURA-A-TRAVA: quem grava no meio do ciclo do outro espera."""
    janela, servico, arquivo = janela_e_servico
    for _ in range(REPETICOES_DO_PERFIL):
        janela.pedir("zerar")
        janela.ouvir("feito")
        janela.pedir("ler")
        janela.ouvir("feito")
        servico.pedir("carimbar")
        servico.ouvir("segurando")
        janela.pedir("gravar")
        servico.pedir("solta")
        servico.ouvir("feito")
        janela.ouvir("feito")

        disco = _no_disco(arquivo)
        assert disco["priority"] == 77
        assert disco.get("ponte") is not None


def test_dois_servicos_que_somam_nao_perdem_a_conta(
    janela_e_servico: tuple[_Papel, _Papel, Path],
) -> None:
    """D-1911-A-GRAVACAO-QUE-FUNDE-SEGURA-A-TRAVA: o ciclo relê sob a trava, e nada se perde."""
    um, outro, arquivo = janela_e_servico
    um.pedir("zerar")
    um.ouvir("feito")

    um.pedir(f"somar {SOMAS_POR_PROCESSO}")
    outro.pedir(f"somar {SOMAS_POR_PROCESSO}")
    um.ouvir("feito")
    outro.ouvir("feito")

    assert _no_disco(arquivo)["priority"] == 10 + 2 * SOMAS_POR_PROCESSO


def _placa(modelo: str) -> dict[str, object]:
    return {
        "fabricante": {"de_onde_sei": "lido-do-firmware", "valor": "Fabricante"},
        "modelo": {"de_onde_sei": "lido-do-firmware", "valor": modelo},
    }


def test_a_migracao_no_laco_nao_espera_a_trava_de_outro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-3110-O-LACO-DO-DAEMON-NUNCA-ESPERA-TRAVA-DE-OUTRO: no laço, migra sem gravar."""
    casa = tmp_path / "config"
    casa.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: casa)
    dmi = tmp_path / "sys/class/dmi/id"
    dmi.mkdir(parents=True)
    (dmi / "board_vendor").write_text("Fabricante\n", encoding="utf-8")
    (dmi / "board_name").write_text("Placa B\n", encoding="utf-8")
    monkeypatch.setenv(maquina.RAIZ_DO_SYS_ENV, str(tmp_path / "sys"))
    arquivo = casa / "maquina.json"
    documento = {"version": 1, "placa": _placa("Placa A"), "mesa": {"altura_da_antena": "acima"}}
    arquivo.write_text(json.dumps(documento), encoding="utf-8")

    segurando, soltar = threading.Event(), threading.Event()

    def dono() -> None:
        with FileLock(str(casa / "maquina.json.lock")):
            segurando.set()
            soltar.wait(SEGURA_A_TRAVA_S)

    fio = threading.Thread(target=dono)
    fio.start()
    segurando.wait()

    async def no_laco() -> maquina.MaquinaConfig:
        return maquina.carregar_maquina()

    lida = asyncio.run(no_laco())
    no_disco = json.loads(arquivo.read_text(encoding="utf-8"))
    soltar.set()
    fio.join()

    assert lida.mesa == maquina.MesaDeclarada()
    assert no_disco == documento
    maquina.carregar_maquina()
    assert json.loads(arquivo.read_text(encoding="utf-8"))["placa"] == _placa("Placa B")
