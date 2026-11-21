"""O-INSTALL-NAO-REBAIXA-O-QUE-O-ATUALIZADOR-PROVOU-01: a versão provada tem um dono só.

O atualizador sobe a biblioteca e prova que o Hefesto sobe com a versão nova; o install, que roda
ao fechar a janela, instalava com ``-c constraints.txt`` de igualdade e a rebaixava. Agora o
``constraints.txt`` é o piso da primeira instalação e o atualizador grava o que provou, também como
piso (``python-provado.txt``), que o install lê depois do primeiro.

O passo do pip do ``install.sh`` roda extraído, com um ``pip`` de mentira no ``VENV_DIR`` de um lar
de mentira que anota os argumentos; nada instala. As travas que ele pediu se leem com o
``packaging``: a pergunta é se o ``evdev`` 2.0.0 cabe no que o install pediu.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o ``constraints.txt`` de volta ao ``==``
reprova os dois primeiros casos; o install sem a linha do registro reprova o terceiro; o registro
gravado com ``==`` reprova o quarto; a troca e a volta sem gravar reprovam as duas que gravam.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa
from hefesto_dualsense4unix.app.actions.atualizador import EtapaFalhouError

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
BASH = shutil.which("bash") or "/bin/bash"
_ACHADO = re.search(r'^_extras="emulation,cosmic"\n.*?^ok\n', INSTALL, re.MULTILINE | re.DOTALL)
assert _ACHADO is not None, "o passo do pip do install.sh mudou de forma"
TRECHO = _ACHADO.group(0)

NA_MAQUINA = {"evdev": "2.0.0", "pydantic": "2.14.3"}


def _rodar_o_passo(lar: Path, provadas: dict[str, str] | None) -> list[Path]:
    """Roda o passo do pip com ``HOME`` de mentira; devolve os arquivos que ele passou a ``-c``."""
    cache = lar / ".cache" / "hefesto-dualsense4unix" / "atualizador"
    cache.mkdir(parents=True, exist_ok=True)
    if provadas is not None:
        (cache / "python-provado.txt").write_text(
            "".join(f"{n}>={v}\n" for n, v in provadas.items()), encoding="utf-8")
    venv = lar / "venv"
    (venv / "bin").mkdir(parents=True)
    pip = venv / "bin" / "pip"
    pip.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "${LOG_DO_PIP}"\n', encoding="utf-8")
    pip.chmod(0o755)
    roteiro = lar / "passo.sh"
    roteiro.write_text(
        "set -euo pipefail\n"
        'die() { printf "ERRO: %s\\n" "$*" >&2; exit 42; }\n'
        'warn() { printf "aviso: %s\\n" "$*"; }\n'
        "ok() { :; }\n"
        "DRY_RUN=0\nWITH_DEV=0\n"
        f'ROOT_DIR="{RAIZ}"\nVENV_DIR="{venv}"\n' + TRECHO,
        encoding="utf-8")
    ambiente = {"PATH": os.environ["PATH"], "HOME": str(lar), "LOG_DO_PIP": str(lar / "pip.log")}
    feito = subprocess.run([BASH, str(roteiro)], env=ambiente, capture_output=True, text=True,
                           check=False)
    assert feito.returncode == 0, feito.stderr
    argumentos = (lar / "pip.log").read_text(encoding="utf-8").splitlines()
    return [Path(argumentos[i + 1]) for i, a in enumerate(argumentos) if a == "-c"]


def _cabe(arquivos: list[Path], nome: str, versao: str) -> bool:
    """A versão cabe em TODAS as linhas que as travas pedem para o pacote."""
    for arquivo in arquivos:
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha and Requirement(linha).name == nome \
                    and not Requirement(linha).specifier.contains(Version(versao)):
                return False
    return True


def test_a_primeira_instalacao_pede_o_piso_e_aceita_a_versao_mais_nova(tmp_path: Path) -> None:
    travas = _rodar_o_passo(tmp_path, None)
    assert travas == [RAIZ / "constraints.txt"]
    for nome, versao in NA_MAQUINA.items():
        assert _cabe(travas, nome, versao), f"o piso da primeira instalação trava {nome}"
    assert not _cabe(travas, "evdev", "1.9.2"), "o piso deixou de ser piso"


def test_o_install_nao_pede_o_que_rebaixa_a_versao_provada(tmp_path: Path) -> None:
    travas = _rodar_o_passo(tmp_path, NA_MAQUINA)
    for nome, versao in NA_MAQUINA.items():
        assert _cabe(travas, nome, versao), f"o install pediu o que tira {nome} {versao}"
    assert not any("==1.9.3" in a.read_text(encoding="utf-8") for a in travas)


def test_o_install_instala_pelo_registro_das_provadas_depois_do_piso(tmp_path: Path) -> None:
    travas = _rodar_o_passo(tmp_path, NA_MAQUINA)
    assert [a.name for a in travas] == ["constraints.txt", "python-provado.txt"]
    assert not _cabe(travas, "evdev", "1.9.3"), "o registro das provadas não entrou nas travas"


@pytest.fixture
def lar_do_atualizador(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O cache do atualizador no lar de mentira, o mesmo que o install lê."""
    cache = tmp_path / ".cache" / "hefesto-dualsense4unix" / "atualizador"
    cache.mkdir(parents=True)
    monkeypatch.setattr(pa, "_cache", lambda: cache)
    monkeypatch.setattr(pa, "_instalar_rodas", lambda _pasta, _alvo: (0, ""))
    monkeypatch.setattr(pa, "_voltar_as_de_antes", lambda _pacotes, _corte=None: (0, ""))
    monkeypatch.setattr(pa, "_rodas_de_agora", lambda: dict(NA_MAQUINA))
    return tmp_path


def _registro(lar: Path) -> Path:
    return lar / ".cache" / "hefesto-dualsense4unix" / "atualizador" / "python-provado.txt"


def test_o_registro_mora_onde_o_install_olha() -> None:
    """O ``python-provado.txt`` fica na pasta ``atualizador`` do cache do produto."""
    assert pa._cache().parts[-2:] == ("hefesto-dualsense4unix", "atualizador")
    assert pa.ARQUIVO_DAS_PROVADAS == "python-provado.txt"
    assert (".cache}/hefesto-dualsense4unix/atualizador/" + pa.ARQUIVO_DAS_PROVADAS) in INSTALL


def test_a_troca_provada_grava_o_registro_e_o_install_o_le(
        lar_do_atualizador: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "")
    pa._trocar_o_python({"pacotes": {"evdev": ["1.9.3", "2.0.0"]}})
    assert _registro(lar_do_atualizador).read_text(encoding="utf-8").splitlines() == [
        "evdev>=2.0.0", "pydantic>=2.14.3"]
    travas = _rodar_o_passo(lar_do_atualizador, None)
    assert _registro(lar_do_atualizador) in travas


def test_o_registro_velho_nao_barra_a_arvore_que_pede_mais(lar_do_atualizador: Path) -> None:
    """A árvore nova que pede uma versão acima da provada (``pydantic>=2.15``) ainda instala: com o
    registro em ``==``, o pip recusa as duas travas juntas e o install morre no passo 2."""
    pa._anotar_as_que_provou()
    travas = _rodar_o_passo(lar_do_atualizador, None)
    for nome, versao in NA_MAQUINA.items():
        acima = Version(versao)
        assert _cabe(travas, nome, f"{acima.major}.{acima.minor + 1}.0"), (
            f"o registro das provadas barra {nome} acima de {versao}")
    assert not _cabe(travas, "evdev", "1.9.3")


def test_a_troca_que_nao_prova_nao_grava_o_registro(
        lar_do_atualizador: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "o evdev novo não chama o gancho")
    with pytest.raises(EtapaFalhouError):
        pa._trocar_o_python({"pacotes": {"evdev": ["1.9.3", "2.0.0"]}})
    assert not _registro(lar_do_atualizador).exists()


def test_a_volta_provada_regrava_o_registro_com_o_que_voltou(
        lar_do_atualizador: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.app.actions import atualizador as at

    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "")
    monkeypatch.setattr(at, "_reiniciar_o_servico", lambda: True)
    monkeypatch.setattr(pa, "_rodas_de_agora", lambda: {"evdev": "1.9.3", "pydantic": "2.13.5"})
    _registro(lar_do_atualizador).write_text("evdev>=2.0.0\n", encoding="utf-8")
    pa._voltar_o_python({"dados": {"pacotes": {"evdev": ["1.9.3", "2.0.0"]}}})
    assert _registro(lar_do_atualizador).read_text(encoding="utf-8").splitlines() == [
        "evdev>=1.9.3", "pydantic>=2.13.5"]
