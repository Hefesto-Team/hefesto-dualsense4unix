"""A-VARREDURA-DE-ORFAOS-NAO-RODA-NO-IMPORT-01: importar um módulo de som não varre processo.

Os módulos do retorno do microfone, do som do controle na TV e da háptica do cabo criam a
família de laços no nível do módulo. A varredura de órfãos corria no ``Lacos.__init__``: importar
qualquer um deles lia o ``/proc`` e mandava SIGTERM com o ``os.kill`` real. Agora a família guarda
a raiz e o ``matar`` de quem a cria e varre uma vez, no primeiro uso da família pelo processo.

Tudo aqui corre num ``/proc`` de mentira e com um ``matar`` que só anota: nunca contra a máquina.
O subprocesso troca o ``os.kill`` e a raiz antes de importar o que quer que seja do produto.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import laco_de_audio
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos

RAIZ = Path(__file__).resolve().parents[2]
FAMILIA = "teste-do-import-do-som"
P = 6_000_000

_FILHO = """
import json, os, sys
from pathlib import Path
sinais = []
os.kill = lambda pid, sinal: sinais.append(pid)
from hefesto_dualsense4unix.integrations import laco_de_audio
laco_de_audio._PROC = Path(sys.argv[1])
varreduras = []
original = laco_de_audio.varrer_orfaos
def espia(*args, **kw):
    varreduras.append(1)
    return original(*args, **kw)
laco_de_audio.varrer_orfaos = espia
from hefesto_dualsense4unix.integrations import (
    haptica_do_cabo, monitor_do_microfone, som_do_controle_na_tv)
print(json.dumps({
    "varreduras": len(varreduras),
    "sinais": sinais,
    "familias": sorted(f.familia for f in laco_de_audio._FAMILIAS),
}))
"""


@pytest.fixture(autouse=True)
def _sem_familia_de_teste() -> Any:
    antes = list(laco_de_audio._FAMILIAS)
    yield
    for familia in laco_de_audio._FAMILIAS:
        if familia not in antes:
            familia.desligar_todos()
    laco_de_audio._FAMILIAS[:] = antes


def _fingir_processo(raiz: Path, pid: int, argv: list[str], pai: int) -> None:
    pasta = raiz / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    campos = ["S", str(pai)] + ["0"] * 17 + ["12345"]
    (pasta / "stat").write_text(f"{pid} ({Path(argv[0]).name}) " + " ".join(campos) + " 0 0\n")


def _laco(familia: str, chave: str = "x1") -> list[str]:
    return ["pw-loopback", "--capture", "mic", "--name", f"hefesto-{familia}-{chave}"]


def _sem_maquina(tmp_path: Path) -> tuple[Path, list[tuple[int, int]], Any]:
    raiz = tmp_path / "proc"
    raiz.mkdir()
    sinais: list[tuple[int, int]] = []
    return raiz, sinais, lambda pid, sinal: sinais.append((pid, sinal))


def test_importar_os_tres_modulos_de_som_nao_varre_nem_manda_sinal(tmp_path: Path) -> None:
    """MORDIDA: a varredura devolvida ao ``Lacos.__init__`` corre no import dos três módulos."""
    proc_vazio = tmp_path / "proc-vazio"
    proc_vazio.mkdir()
    casa = tmp_path / "casa"
    casa.mkdir()
    ambiente = {
        **os.environ,
        "PYTHONPATH": str(RAIZ / "src"),
        "HOME": str(casa),
        "XDG_STATE_HOME": str(casa / "state"),
        "XDG_CONFIG_HOME": str(casa / "config"),
    }

    feito = subprocess.run(
        [sys.executable, "-c", _FILHO, str(proc_vazio)],
        env=ambiente, timeout=120, check=False, capture_output=True)

    assert feito.returncode == 0, feito.stderr.decode()[-600:]
    relato = json.loads(feito.stdout.decode().strip().splitlines()[-1])
    assert len(relato["familias"]) >= 3, "os três módulos não criaram a família: a régua não mede"
    assert relato["varreduras"] == 0, "importar um módulo de som varreu processo"
    assert relato["sinais"] == []


def test_criar_a_familia_nao_varre_e_o_primeiro_contato_varre_uma_vez(tmp_path: Path) -> None:
    """MORDIDA: a varredura no ``__init__`` varre ao criar; sem a marca, varreria a cada contato."""
    raiz, sinais, matar = _sem_maquina(tmp_path)
    _fingir_processo(raiz, P + 1, _laco(FAMILIA), 1)

    lacos = Lacos(FAMILIA, raiz=raiz, matar=matar)
    assert sinais == [], "criar a família varreu"

    lacos.ligados()
    lacos.esta_ligado("a1")
    lacos.ligados()
    assert sinais == [(P + 1, signal.SIGTERM)], "o primeiro contato varre uma vez, não a cada um"


def test_o_laco_so_nasce_depois_da_varredura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: lançar antes de varrer deixaria o órfão e o laço novo soando juntos."""
    raiz, _sinais, _ = _sem_maquina(tmp_path)
    _fingir_processo(raiz, P + 2, _laco(FAMILIA), 1)
    eventos: list[str] = []

    class _Lancador:
        def lancar(self, argv: Any) -> Any:
            eventos.append("lancou")
            return _Processo()

    monkeypatch.setattr(laco_de_audio, "_LANCADOR", _Lancador())
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _n: "/usr/bin/pw-loopback")
    lacos = Lacos(FAMILIA, raiz=raiz, matar=lambda pid, sinal: eventos.append("varreu"))

    assert lacos.ligar("a1", captura="mic")

    assert eventos == ["varreu", "lancou"]


def test_o_fio_que_chega_durante_a_varredura_aguarda_o_fim_para_lancar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: a marca posta antes de varrer deixa o segundo fio lançar com o órfão de pé."""
    raiz, _sinais, _ = _sem_maquina(tmp_path)
    _fingir_processo(raiz, P + 5, _laco(FAMILIA, "p1"), 1)
    eventos: list[str] = []
    na_varredura = threading.Event()
    solta = threading.Event()

    def _matar_devagar(pid: int, sinal: int) -> None:
        na_varredura.set()
        solta.wait(5.0)
        eventos.append("varreu")

    class _Lancador:
        def lancar(self, argv: Any) -> Any:
            eventos.append("lancou")
            return _Processo()

    monkeypatch.setattr(laco_de_audio, "_LANCADOR", _Lancador())
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _n: "/usr/bin/pw-loopback")
    lacos = Lacos(FAMILIA, raiz=raiz, matar=_matar_devagar)
    primeiro = threading.Thread(target=lacos.ligados)
    primeiro.start()
    assert na_varredura.wait(5.0)
    segundo = threading.Thread(target=lambda: lacos.ligar("p2", captura="mic"))
    segundo.start()
    segundo.join(0.3)
    solta.set()
    primeiro.join(5.0)
    segundo.join(5.0)

    assert eventos == ["varreu", "lancou"], "o segundo fio lançou antes de a varredura acabar"


def test_recolher_orfaos_e_a_entrada_explicita(tmp_path: Path) -> None:
    raiz, sinais, matar = _sem_maquina(tmp_path)
    _fingir_processo(raiz, P + 3, _laco(FAMILIA), 1)

    recolhidos = Lacos(FAMILIA, raiz=raiz, matar=matar).recolher_orfaos()

    assert recolhidos == [P + 3]
    assert sinais == [(P + 3, signal.SIGTERM)]


def test_a_suite_roda_a_varredura_de_producao_numa_raiz_vazia_e_sem_matar() -> None:
    """MORDIDA: sem a guarda do conftest, ``Lacos(familia)`` cru varre o ``/proc`` real."""
    assert Path("/proc") != laco_de_audio._PROC
    assert list(laco_de_audio._PROC.iterdir()) == []
    assert laco_de_audio._MATAR is not os.kill
    with pytest.raises(AssertionError, match="matar de produção"):
        laco_de_audio._MATAR(1, signal.SIGTERM)


class _Processo:
    def __init__(self) -> None:
        self.vivo = True

    def poll(self) -> int | None:
        return None if self.vivo else 0

    def kill(self) -> None:
        self.vivo = False

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_quatro_controles_o_cabo_no_meio_nao_varre_de_novo_nem_derruba_o_alheio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quatro controles no rádio (dois no mesmo adaptador); um vai ao cabo e volta ao rádio.

    O laço guarda o estado pela chave do controle, não pelo adaptador nem pelo transporte. A troca
    de transporte religa só o laço daquele controle; os outros três seguem com o mesmo processo e a
    varredura de órfãos não corre de novo.
    """
    raiz, sinais, matar = _sem_maquina(tmp_path)
    _fingir_processo(raiz, P + 4, _laco(FAMILIA, "velho"), 1)
    nascidos: dict[str, list[_Processo]] = {}

    class _Lancador:
        def lancar(self, argv: Any) -> Any:
            chave = argv[argv.index("--name") + 1].removeprefix(f"hefesto-{FAMILIA}-")
            novo = _Processo()
            nascidos.setdefault(chave, []).append(novo)
            return novo

    monkeypatch.setattr(laco_de_audio, "_LANCADOR", _Lancador())
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _n: "/usr/bin/pw-loopback")
    lacos = Lacos(FAMILIA, raiz=raiz, matar=matar)
    controles = ("p1", "p2", "p3", "p4")
    adaptador = {"p1": "a", "p2": "a", "p3": "b", "p4": "c"}
    assert adaptador["p1"] == adaptador["p2"]

    for chave in controles:
        assert lacos.ligar(chave, captura=f"{chave}.monitor", destino="sink-radio")
    antes = {c: nascidos[c][-1] for c in controles}

    assert lacos.seguir("p2", "sink-cabo")
    assert lacos.destino_de("p2") == "sink-cabo"
    assert lacos.seguir("p2", "sink-radio")

    assert lacos.ligados() == controles
    for chave in ("p1", "p3", "p4"):
        assert nascidos[chave] == [antes[chave]], f"{chave} foi religado pela troca do vizinho"
        assert antes[chave].vivo
    assert len(nascidos["p2"]) == 3 and not nascidos["p2"][0].vivo
    assert nascidos["p2"][-1].vivo
    assert lacos.destino_de("p2") == "sink-radio"
    assert [d for d in map(lacos.destino_de, controles)] == ["sink-radio"] * 4
    assert sinais == [(P + 4, signal.SIGTERM)], "a varredura correu mais de uma vez"
