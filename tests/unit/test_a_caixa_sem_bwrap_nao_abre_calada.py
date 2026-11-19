"""A caixa sem bwrap não abre calada (A-CAIXA-SEM-BWRAP-NAO-ABRE-CALADA-01).

Sem o ``bwrap``, a extensão fica «recusada» e nenhum processo nasce, a não ser com a chave
«Rodar sem caixa» gravada no registro. O leitor e o fixador do censo obedecem à mesma chave.
O ``install.sh`` declara o ``bubblewrap`` nas três famílias, e o ``doctor`` avisa quando falta.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.mods.instalador import (
    Lugares,
    instalar,
    ler_estado,
    ler_registro,
    rodar_sem_caixa,
)
from hefesto_dualsense4unix.mods.supervisor import FALTA_O_BWRAP
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import (
    _ate,
    _instalar_e_ligar,
    _pasta_do_mod,
    _relato,
    _supervisor,
    curto,
    lar,
)

__all__ = ["curto", "lar"]

RAIZ = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "/bin/bash"


def test_sem_bwrap_a_extensao_fica_recusada_e_nenhum_processo_nasce(
    lar: Lugares, curto: Path
) -> None:
    _instalar_e_ligar(lar, curto, "fica")

    async def corrida() -> None:
        supervisor = _supervisor(lar, bwrap=None, procurar_bwrap=False)
        rodar_sem_caixa("exemplo", False, lugares=lar)
        await supervisor.iniciar()
        try:
            await asyncio.sleep(0.5)
            estado = supervisor.estado_de("exemplo")
            assert estado is not None and estado.estado == "recusada"
            assert estado.motivo == FALTA_O_BWRAP
            assert ler_estado(lar.estado)["exemplo"]["motivo"] == FALTA_O_BWRAP
            assert supervisor.pid_de("exemplo") is None
            assert _relato(lar) is None, "o processo nasceu sem a caixa"
            assert not supervisor.porta.aberta
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_com_a_chave_gravada_abre_sem_caixa_e_ao_tirar_a_chave_para(
    lar: Lugares, curto: Path
) -> None:
    _instalar_e_ligar(lar, curto, "fica")
    rodar_sem_caixa("exemplo", True, lugares=lar)
    assert ler_registro(lar.registro)["exemplo"].sem_caixa

    async def corrida() -> None:
        supervisor = _supervisor(lar, bwrap=None, procurar_bwrap=False, intervalo_s=0.05)
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None)
            estado = ler_estado(lar.estado)["exemplo"]
            assert estado["estado"] == "rodando" and estado["caixa"] == ""
            assert estado["motivo"] == "Roda sem caixa: o bwrap não está instalado."
            rodar_sem_caixa("exemplo", False, lugares=lar)
            await _ate(lambda: (e := supervisor.estado_de("exemplo")) is not None
                       and e.estado == "recusada")
            assert supervisor.pid_de("exemplo") is None
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_a_chave_sobrevive_a_reinstalacao(lar: Lugares, curto: Path) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    rodar_sem_caixa("exemplo", True, lugares=lar)
    instalar(str(pasta), lugares=lar)
    assert ler_registro(lar.registro)["exemplo"].sem_caixa


def _leitor(tmp_path: Path, **mais: object) -> censo.LeitorPorProcesso:
    pasta = tmp_path / "leitor"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "ler.py").write_text(
        "import json\nprint(json.dumps([{'chave': 'j1', 'nome': 'Jogo', 'caminho': '/x'}]))\n",
        encoding="utf-8")
    return censo.LeitorPorProcesso("emu", "Emu", (sys.executable, "ler.py"), pasta,
                                   5.0, **mais)  # type: ignore[arg-type]


def _fixador(tmp_path: Path, **mais: object) -> censo.FixadorPorProcesso:
    pasta = tmp_path / "fixador"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "fixar.py").write_text(
        "import json\nprint(json.dumps({'fixados': 2, 'fora': []}))\n", encoding="utf-8")
    return censo.FixadorPorProcesso("emu", "Emu", (sys.executable, "fixar.py"), pasta, (),
                                    5.0, **mais)  # type: ignore[arg-type]


@pytest.fixture
def sem_bwrap(monkeypatch: pytest.MonkeyPatch) -> None:
    real = shutil.which

    def which(nome: str, *args: object, **kwargs: object) -> str | None:
        return None if nome == "bwrap" else real(nome, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(censo.shutil, "which", which)


@pytest.mark.usefixtures("sem_bwrap")
def test_o_leitor_sem_bwrap_nao_abre_sem_a_chave(tmp_path: Path) -> None:
    lida = censo.ler_por_processo(_leitor(tmp_path))
    assert lida.estado == censo.ILEGIVEL
    assert lida.erros == [censo.FALTA_O_BWRAP_NO_LEITOR]
    com_a_chave = censo.ler_por_processo(_leitor(tmp_path, sem_caixa=True))
    assert com_a_chave.estado == censo.LIDO, com_a_chave
    assert [j.chave for j in com_a_chave.jogos] == ["j1"]


@pytest.mark.usefixtures("sem_bwrap")
def test_o_fixador_sem_bwrap_nao_abre_sem_a_chave(tmp_path: Path) -> None:
    feito = censo.fixar_por_processo(_fixador(tmp_path), nome="p", pino_dir=None,
                                     tarball=None, lar=tmp_path)
    assert feito.reescritas == 0
    assert [f.porque for f in feito.fora] == [censo.FALTA_O_BWRAP_NO_LEITOR]
    com_a_chave = censo.fixar_por_processo(_fixador(tmp_path, sem_caixa=True), nome="p",
                                           pino_dir=None, tarball=None, lar=tmp_path)
    assert com_a_chave.reescritas == 2 and com_a_chave.fora == ()


def _manifesto_de_lancador() -> dict[str, object]:
    return {
        "id": "emu", "nome": "Emu", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["lancador"], "permissoes": ["lancador"],  # (noqa-acento)
        "lancador": {"rotulo": "Emu", "comandos": ["emu"],
                     "leitor": {"executar": ["python3", "ler.py"]}},
    }


def test_a_chave_do_registro_chega_ao_leitor_do_censo(lar: Lugares, curto: Path) -> None:
    from hefesto_dualsense4unix.mods.instalador import ligar, manifesto_instalado
    from hefesto_dualsense4unix.mods.manifesto import pedidos_do_sim

    pasta = curto / "fonte-emu"
    pasta.mkdir()
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto_de_lancador()))
    (pasta / "ler.py").write_text("print('[]')\n")
    instalar(str(pasta), lugares=lar)
    ligar("emu", permissoes_vistas=pedidos_do_sim(manifesto_instalado("emu", lugares=lar)),
          lugares=lar)
    antes = censo.lancadores_das_extensoes(lar)
    assert [e.bloco.leitor.sem_caixa for e in antes if e.bloco.leitor] == [False]
    rodar_sem_caixa("emu", True, lugares=lar)
    depois = censo.lancadores_das_extensoes(lar)
    assert [e.bloco.leitor.sem_caixa for e in depois if e.bloco.leitor] == [True]


def _funcao_do_shell(arquivo: Path, nome: str) -> str:
    import re

    texto = arquivo.read_text(encoding="utf-8")
    inicio = re.search(rf"^{re.escape(nome)}\(\) \{{\n", texto, re.MULTILINE)
    assert inicio is not None, f"{nome}() sumiu de {arquivo.name}"
    fim = re.search(r"^\}\n", texto[inicio.end():], re.MULTILINE)
    assert fim is not None
    return texto[inicio.start():inicio.end() + fim.end()]


@pytest.mark.parametrize("familia", ["apt", "dnf", "pacman"])
def test_o_install_da_nome_ao_bubblewrap_nas_tres_familias(familia: str) -> None:
    corpo = _funcao_do_shell(RAIZ / "install.sh", "_pkg_nome")
    saida = subprocess.run([BASH, "-c", f"{corpo}\n_pkg_nome bubblewrap {familia}"],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert saida == "bubblewrap"


def test_o_install_confere_o_bwrap_no_censo_das_dependencias() -> None:
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    assert '"bubblewrap|importante|cmd:bwrap|' in texto


def test_o_doctor_avisa_quando_falta_o_bwrap(tmp_path: Path) -> None:
    corpo = _funcao_do_shell(RAIZ / "scripts/doctor.sh", "check_caixa_das_extensoes")
    magro = tmp_path / "bin"
    magro.mkdir()
    roteiro = ("pass() { echo \"OK $*\"; }\nwarn() { echo \"WARN $*\"; }\n"
               "conselho_de_instalacao() { echo conselho; }\n"
               f"{corpo}\ncheck_caixa_das_extensoes\n")
    saida = subprocess.run([BASH, "-c", roteiro], capture_output=True, text=True,
                           check=True, env={"PATH": str(magro)}).stdout
    assert saida.startswith("WARN bwrap AUSENTE"), saida
    (magro / "bwrap").symlink_to("/bin/true")
    saida = subprocess.run([BASH, "-c", roteiro], capture_output=True, text=True,
                           check=True, env={"PATH": str(magro)}).stdout
    assert saida.startswith("OK bwrap presente"), saida


def test_o_doctor_roda_a_conferencia_da_caixa() -> None:
    texto = (RAIZ / "scripts/doctor.sh").read_text(encoding="utf-8")
    assert "\n    check_caixa_das_extensoes\n" in texto


@pytest.mark.parametrize("chave", [False, True])
def test_o_ligar_sem_bwrap_diz_o_que_a_chave_gravada_faz(
        lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch, chave: bool) -> None:
    instalar(str(_pasta_do_mod(curto / "fontes", "fica")), lugares=lar)
    rodar_sem_caixa("exemplo", chave, lugares=lar)
    original = shutil.which
    monkeypatch.setattr(cmd_mod.shutil, "which",
                        lambda c, *a, **k: None if c == "bwrap" else original(c, *a, **k))
    saida = CliRunner().invoke(cmd_mod.app, ["ligar", "exemplo"], input="n\n").output
    roda = "Sem o bwrap, a extensão roda sem caixa e pode mais do que estas permissões."
    nao_abre = "Sem o bwrap, a extensão não abre: instale o bubblewrap."
    assert (roda in saida, nao_abre in saida) == (chave, not chave), saida
