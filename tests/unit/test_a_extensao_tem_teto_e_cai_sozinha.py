"""A extensão tem teto de memória e de processos, e cai sozinha.

Nenhuma prova abre uma unidade de verdade no gerenciador de usuário: o ``systemd-run`` é um
dublê que grava os argumentos e troca o processo pelo comando, como o ``--scope`` faz. O que
não se prova aqui é o limite do kernel agindo (a extensão que aloca até morrer): fica para a
prova de quem usa.

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- os tetos tirados do ``comando_com_teto`` reprovam
  ``test_a_linha_da_extensao_traz_os_tetos_de_fabrica`` e
  ``test_o_supervisor_abre_a_extensao_pela_unidade_com_teto``;
- o ``--size`` tirado do ``comando_na_caixa`` reprova ``test_o_tmp_da_caixa_tem_teto``;
- o ajuste do ``oom_score_adj`` tirado do ``preexec`` reprova
  ``test_sem_a_unidade_a_extensao_nasce_com_o_oom_score_alto``;
- o ``OOMPolicy`` tirado da unidade do serviço reprova
  ``test_o_servico_nao_cai_quando_o_kernel_mata_um_filho``.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.instalador import Lugares, instalar
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

curto, lar = _base.curto, _base.lar
_ate, _supervisor, _ligar_vendo = _base._ate, _base._supervisor, _base._ligar_vendo
_manifesto = _base._manifesto

_UNIDADE = Path(__file__).resolve().parents[2] / "assets" / "hefesto-dualsense4unix.service"

_FILHO_QUE_RELATA = textwrap.dedent('''
    import os, time
    dados = os.environ["HEFESTO_MOD_DADOS"]
    with open(os.path.join(dados, "relato"), "w") as f:
        f.write(f"{os.getpid()} {open('/proc/self/oom_score_adj').read().strip()}")
    while True:
        time.sleep(1)
''')


def _systemd_run_de_mentira(base: Path) -> tuple[Path, Path]:
    """O dublê do ``systemd-run --scope``: grava os argumentos e troca o processo pelo comando."""
    registro = base / "argumentos-do-systemd-run"
    programa = base / "systemd-run"
    programa.write_text(textwrap.dedent(f'''\
        #!/bin/sh
        : > "{registro}"
        for a in "$@"; do printf '%s\\n' "$a" >> "{registro}"; done
        while [ "$1" != "--" ]; do shift; done
        shift
        exec "$@"
    '''), encoding="utf-8")
    programa.chmod(programa.stat().st_mode | stat.S_IXUSR)
    return programa, registro


def _instalar_filho(base: Path, lar: Lugares) -> None:
    pasta = base / "fonte-exemplo"
    pasta.mkdir()
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto()), encoding="utf-8")
    (pasta / "mod.py").write_text(_FILHO_QUE_RELATA, encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)


def _relato(lar: Lugares) -> list[str]:
    return (lar.dados / "exemplo" / "relato").read_text(encoding="utf-8").split()


def _corrida(sup_: Any, depois: Any) -> None:
    async def andar() -> None:
        await sup_.iniciar()
        try:
            await _ate(lambda: (e := sup_.estado_de("exemplo")) is not None
                       and e.estado == "rodando" and sup_.pid_de("exemplo") is not None)
            await depois()
        finally:
            await sup_.parar()

    asyncio.run(andar())


def test_a_linha_da_extensao_traz_os_tetos_de_fabrica() -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: a linha traz memória, tarefas e CPU."""
    linha = sup.comando_com_teto(["bwrap", "--", "python3", "mod.py"], "/usr/bin/systemd-run", "x")
    assert linha[:4] == ["/usr/bin/systemd-run", "--user", "--scope", "--quiet"]
    propriedades = [linha[i + 1] for i, a in enumerate(linha) if a == "-p"]
    assert propriedades == [f"MemoryMax={sup.TETO_DA_MEMORIA}", "MemorySwapMax=0",
                            f"TasksMax={sup.TETO_DAS_TAREFAS}", f"CPUWeight={sup.PESO_DA_CPU}"]
    assert linha[linha.index("--") + 1:] == ["bwrap", "--", "python3", "mod.py"]
    assert (sup.TETO_DA_MEMORIA, sup.TETO_DAS_TAREFAS) == ("512M", 256)
    sem_unidade = ["python3", "mod.py"]
    assert sup.comando_com_teto(sem_unidade, None, "x") == sem_unidade


def test_o_supervisor_abre_a_extensao_pela_unidade_com_teto(curto: Path, lar: Lugares) -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: o PID, o cano e o parar seguem os mesmos."""
    programa, registro = _systemd_run_de_mentira(curto)
    _instalar_filho(curto, lar)
    sup_ = _supervisor(lar, procurar_bwrap=False, systemd_run=str(programa))

    async def conferir() -> None:
        await _ate(lambda: (lar.dados / "exemplo" / "relato").exists())
        argumentos = registro.read_text(encoding="utf-8").split("\n")
        assert "MemoryMax=512M" in argumentos and "TasksMax=256" in argumentos
        assert "--user" in argumentos and "--scope" in argumentos
        assert int(_relato(lar)[0]) == sup_.pid_de("exemplo"), "o --scope trocou o PID"

    _corrida(sup_, conferir)


def test_sem_a_unidade_a_extensao_nasce_com_o_oom_score_alto(curto: Path, lar: Lugares) -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: sem systemd, o kernel a mata primeiro."""
    _instalar_filho(curto, lar)
    sup_ = _supervisor(lar, procurar_bwrap=False)

    async def conferir() -> None:
        await _ate(lambda: (lar.dados / "exemplo" / "relato").exists())
        assert int(_relato(lar)[1]) >= sup.OOM_SCORE_DA_EXTENSAO

    _corrida(sup_, conferir)


def test_o_tmp_da_caixa_tem_teto(curto: Path) -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: o /tmp da caixa nasce com tamanho."""
    exigir_caixa_do_bwrap()
    bwrap = shutil.which("bwrap") or "bwrap"
    if not sup.bwrap_aceita_o_tamanho(bwrap):
        pytest.skip("o bwrap desta máquina não tem --size")
    manifesto = Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
    })
    for pasta in ("fonte", "dados", "casa"):
        (curto / pasta).mkdir()
    porta = curto / "porta.sock"
    porta.touch()
    medir = "import os; s = os.statvfs('/tmp'); print(s.f_blocks * s.f_frsize)"
    argv = sup.comando_na_caixa(
        bwrap=bwrap, comando=[sys.executable, "-c", medir], codigo=curto / "fonte",
        dados=curto / "dados", porta=porta, manifesto=manifesto, casa=curto / "casa",
        execucao=())
    feito = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    assert feito.returncode == 0, feito.stderr
    assert int(feito.stdout) == sup.TAMANHO_DO_TMP_BYTES


def test_o_bwrap_sem_o_tamanho_abre_sem_a_opcao(curto: Path) -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: o bwrap velho fica sem a opção."""
    def bwrap_que_diz(ajuda: str, nome: str) -> str:
        programa = curto / nome
        programa.write_text(f"#!/bin/sh\necho '{ajuda}'\n", encoding="utf-8")
        programa.chmod(programa.stat().st_mode | stat.S_IXUSR)
        return str(programa)

    novo = bwrap_que_diz("    --size BYTES    Set size", "bwrap-novo")
    velho = bwrap_que_diz("    --tmpfs DEST    Mount new tmpfs", "bwrap-velho")
    assert sup.bwrap_aceita_o_tamanho(novo) and not sup.bwrap_aceita_o_tamanho(velho)
    assert not sup.bwrap_aceita_o_tamanho(str(curto / "nao-existe"))


def test_a_unidade_so_se_usa_com_o_gerenciador_de_usuario_e_os_tres_controladores(
        curto: Path) -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: sem delegação ou sem barramento, sem unidade."""
    uid = 4242
    sistema = curto / "sistema"
    pasta = curto / "pasta-de-run"
    pasta.mkdir()
    (pasta / "bus").touch()
    gerenciador = sistema / "user.slice" / f"user-{uid}.slice" / f"user@{uid}.service"
    gerenciador.mkdir(parents=True)

    def pergunta(achar: Any = lambda nome: "/usr/bin/systemd-run", execucao: Path = pasta) -> Any:
        return sup.systemd_run_com_teto(raiz=sistema, uid=uid, achar=achar,
                                        execucao=str(execucao))

    (gerenciador / "cgroup.controllers").write_text("cpuset cpu io memory pids\n")
    assert pergunta() == "/usr/bin/systemd-run"
    (gerenciador / "cgroup.controllers").write_text("cpu memory\n")
    assert pergunta() is None, "sem o pids delegado a unidade não teria teto de tarefas"
    (gerenciador / "cgroup.controllers").unlink()
    assert pergunta() is None
    (gerenciador / "cgroup.controllers").write_text("cpu memory pids\n")
    assert pergunta(achar=lambda nome: None) is None
    assert pergunta(execucao=curto / "sem-bus") is None


def test_o_servico_nao_cai_quando_o_kernel_mata_um_filho() -> None:
    """D-2511-A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA: o OOMPolicy do serviço é continue."""
    diretivas = [linha.strip() for linha in _UNIDADE.read_text(encoding="utf-8").splitlines()
                 if linha.strip() and not linha.startswith("#")]
    assert "OOMPolicy=continue" in diretivas
