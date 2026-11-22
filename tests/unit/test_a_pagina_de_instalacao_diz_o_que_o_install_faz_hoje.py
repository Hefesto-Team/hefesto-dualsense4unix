"""A página de instalação lista cada escrita de root do install e não carrega fato trocado.

D-2211-A-PAGINA-DE-INSTALACAO-LISTA-CADA-ESCRITA-DE-ROOT: a seção «O que o instalador muda
no sistema» tem uma linha, com o caminho e a opção que a pula, para cada destino em
`/etc`, `/usr` e `/var` que o `install.sh` anuncia em `_faria_root`; os quatro fatos que a
auditoria mediu trocados (a versão do BlueZ, o pydantic do .deb, o `+` do `hidraw`, o nome
do bundle do Flatpak) saem das páginas e o `caducos.csv` os guarda fora do ar.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTALACAO = RAIZ / "docs" / "usage" / "instalacao.md"
FLATPAK = RAIZ / "docs" / "usage" / "flatpak.md"
README = RAIZ / "README.md"
INSTALL_SH = RAIZ / "install.sh"
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
RELEASE = RAIZ / ".github" / "workflows" / "release.yml"
CADUCOS = RAIZ / "docs" / "data" / "caducos.csv"
DESTINO = re.compile(r"(/(?:etc|usr|var)/[A-Za-z0-9_./*-]*[A-Za-z0-9_*/-])")
SUDOERS = re.compile(r"/etc/sudoers\.d/[A-Za-z0-9_.-]+")


def _linhas_de_root() -> list[str]:
    texto = INSTALL_SH.read_text(encoding="utf-8") + CAMADA.read_text(encoding="utf-8")
    return [linha for linha in texto.splitlines() if '_faria_root "' in linha]


def _destinos_de_root() -> set[str]:
    return {t for linha in _linhas_de_root() for t in DESTINO.findall(linha)}


def _formas_aceitas(destino: str) -> set[str]:
    formas = {destino, destino.rstrip("/") + "/"}
    pasta = str(PurePosixPath(destino).parent) + "/"
    if pasta.count("/") > 2:
        formas.add(pasta)
    return formas


def _sem_linha(pagina: str) -> list[str]:
    return sorted(
        d for d in _destinos_de_root() if not any(f in pagina for f in _formas_aceitas(d))
    )


def _secao(pagina: str, titulo: str) -> str:
    achado = re.search(rf"^## {re.escape(titulo)}\n(.*?)(?=^## |\Z)", pagina, re.M | re.S)
    assert achado, f"a página perdeu a seção {titulo!r}"
    return achado.group(1)


def _tabela() -> str:
    return _secao(INSTALACAO.read_text(encoding="utf-8"), "O que o instalador muda no sistema")


def test_o_install_anuncia_destinos_de_root() -> None:
    destinos = _destinos_de_root()
    assert "/etc/sudoers.d/49-hefesto-bt-ponte" in destinos, sorted(destinos)
    assert "/etc/apt/preferences.d/hefesto-pipewire" in destinos, sorted(destinos)
    assert len(destinos) > 20, sorted(destinos)


def test_todo_destino_de_root_do_install_tem_linha_na_pagina() -> None:
    faltam = _sem_linha(_tabela())
    assert not faltam, f"a página não diz onde o install grava: {faltam}"


def test_a_regua_morde_a_linha_do_sudoers_que_sumiu() -> None:
    """Tira (só da cópia do texto) a linha do sudoers: a régua acusa os três arquivos."""
    tabela = _tabela()
    sem = "\n".join(linha for linha in tabela.splitlines() if "/etc/sudoers.d/" not in linha)
    assert _sem_linha(tabela) == []
    faltam = _sem_linha(sem)
    assert {d for d in faltam if "/etc/sudoers.d/" in d} == set(
        SUDOERS.findall("\n".join(_linhas_de_root()))
    ), faltam


def test_cada_arquivo_do_sudoers_aparece_inteiro_com_a_opcao_que_o_pula() -> None:
    tabela = _tabela()
    arquivos = set(SUDOERS.findall("\n".join(_linhas_de_root())))
    assert len(arquivos) == 3, arquivos
    for arquivo in arquivos:
        assert Path(arquivo).name in tabela, f"a página não diz {arquivo}"
    assert "--sem-sudo-sem-senha" in tabela
    assert "visudo -c" in tabela


@pytest.mark.parametrize(
    "termo",
    [
        "NOPASSWD",
        "grupo `hefesto`",
        "PipeWire",
        "WirePlumber",
        "preferences.d",
        "NetworkManager",
        "desempenho",
        "--no-fechar-o-no",
        "--sem-sudo-sem-senha",
        "--no-udev",
        "--sem-desempenho",
        "reinicia o som da sessão",
    ],
)
def test_o_mais_sensivel_esta_dito(termo: str) -> None:
    if termo == "NOPASSWD":
        assert "sem senha" in _tabela()
        return
    assert termo in _tabela(), f"a seção do que o instalador muda não diz {termo!r}"


def test_o_readme_nao_cala_o_mais_sensivel() -> None:
    texto = README.read_text(encoding="utf-8")
    for termo in ("/etc/sudoers.d", "grupo `hefesto`", "PipeWire", "WirePlumber"):
        assert termo in texto, f"o README não diz {termo!r}"


def test_a_versao_do_bluez_sai_da_pagina_e_aponta_o_baseline() -> None:
    pagina = INSTALACAO.read_text(encoding="utf-8")
    assert "5.86" not in pagina
    assert "assets/bluez-backport/BASELINE" in pagina
    baseline = (RAIZ / "assets" / "bluez-backport" / "BASELINE").read_text(encoding="utf-8")
    assert re.search(r"^VERSAO_UPSTREAM=", baseline, re.M)


def test_o_deb_nao_manda_instalar_pydantic_antes() -> None:
    pagina = INSTALACAO.read_text(encoding="utf-8")
    assert "pydantic>=2" not in pagina
    assert "pydantic` do apt" not in pagina
    build = (RAIZ / "scripts" / "build_deb.sh").read_text(encoding="utf-8")
    assert "venv" in build, "o .deb deixou de levar o ambiente Python dele"


def test_a_conferencia_das_permissoes_diz_o_que_esperar_de_cada_no() -> None:
    pagina = INSTALACAO.read_text(encoding="utf-8")
    secao = _secao(pagina, "Reaplicar as regras udev")
    assert "ls -l /dev/hidraw*" not in secao
    assert "ls -l /dev/uinput /dev/uhid" in secao
    assert "pad\nvirtual" in secao or "pad virtual" in secao
    assert "nasce" in secao and "só do root" in secao
    assert "hefesto-dualsense4unix doctor" in secao


def test_o_nome_do_bundle_do_flatpak_e_o_da_release() -> None:
    release = RELEASE.read_text(encoding="utf-8")
    achado = re.search(r'"(Hefesto-Dualsense4Unix-\$\{VERSION\}-x86_64\.flatpak)"', release)
    assert achado, "a release deixou de nomear o bundle"
    nome = achado.group(1).replace("${VERSION}", "<versão>")
    pagina = FLATPAK.read_text(encoding="utf-8")
    instalar = _secao(pagina, "Instalar")
    assert f"flatpak install --user {nome}" in instalar
    assert (
        "flatpak install --user io.github.hefesto_team.hefesto_dualsense4unix.flatpak" not in pagina
    )


def test_os_fatos_trocados_estao_no_caducos_e_fora_do_ar() -> None:
    texto = CADUCOS.read_text(encoding="utf-8")
    assert "O BlueZ corrigido (5.86)" in texto
    assert "do apt é o 1.x; rode antes" in texto
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "validar-caducos.py"), "--all"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_o_validador_morde_o_5_86_devolvido(tmp_path: Path) -> None:
    """O fato caduco devolvido a uma cópia da página reprova o `validar-caducos.py`."""
    raiz = tmp_path / "arvore"
    (raiz / "docs" / "usage").mkdir(parents=True)
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "data" / "caducos.csv").write_text(
        CADUCOS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (raiz / "README.md").write_text("", encoding="utf-8")
    pagina = raiz / "docs" / "usage" / "instalacao.md"
    pagina.write_text("- **O BlueZ corrigido (5.86).** texto\n", encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts" / "validar-caducos.py"),
            "--all",
            "--raiz",
            str(raiz),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert r.returncode != 0, r.stdout
    assert "O BlueZ corrigido (5.86)" in r.stdout + r.stderr
