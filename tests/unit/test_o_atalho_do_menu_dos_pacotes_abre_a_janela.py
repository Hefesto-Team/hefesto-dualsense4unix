"""O atalho do menu dos pacotes é renderizado para o executável do formato, nunca copiado cru.

D-2211-O-ATALHO-DO-MENU-DOS-PACOTES-APONTA-PARA-O-GUI: os quatro pacotes levam o atalho
apontando para `hefesto-dualsense4unix-gui`, que o `pyproject.toml` já instala; o modelo
versionado continua com `@RAIZ@/run.sh` e a chave `X-HefestoNaoEmpacotado`, e só o
renderizador `scripts/atalho_do_pacote.sh` o entrega a um pacote.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
MODELO = RAIZ / "packaging" / "hefesto-dualsense4unix.desktop"
RENDERIZADOR = RAIZ / "scripts" / "atalho_do_pacote.sh"
PARIDADE = RAIZ / "scripts" / "check_packaging_parity.sh"
RELEASE = RAIZ / ".github" / "workflows" / "release.yml"
RECEITAS = {
    "deb": RAIZ / "scripts" / "build_deb.sh",
    "arch": RAIZ / "packaging" / "arch" / "PKGBUILD",
    "fedora": RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
    "nix": RAIZ / "packaging" / "nix" / "package.nix",
}
SUBSTITUICOES = {
    "deb": {},
    "arch": {},
    "fedora": {"%{_bindir}": "/usr/bin"},
    "nix": {"$out": "/nix/store/aaaa-hefesto"},
}


def _sem_comentario(texto: str) -> str:
    return "\n".join(linha for linha in texto.splitlines() if not linha.lstrip().startswith("#"))


def _chamada_do_renderizador(formato: str) -> list[str]:
    """Os argumentos que a receita passa ao renderizador, com as macros do formato resolvidas."""
    texto = _sem_comentario(RECEITAS[formato].read_text(encoding="utf-8"))
    achado = re.search(r"atalho_do_pacote\.sh((?:[^\n]*\\\n)*[^\n]*)", texto)
    assert achado, f"a receita do {formato} não chama o renderizador do atalho"
    argumentos = achado.group(1).replace("\\\n", " ").split()
    argumentos = [a for a in argumentos if a not in (">", "/dev/null")]
    resolvidos = []
    for arg in argumentos:
        for macro, valor in SUBSTITUICOES[formato].items():
            arg = arg.replace(macro, valor)
        resolvidos.append(arg.strip('"'))
    return resolvidos


def _renderizar(
    tmp: Path, executavel: str, *args: str, modelo: Path = MODELO, script: Path = RENDERIZADOR
) -> tuple[subprocess.CompletedProcess[str], Path]:
    saida = tmp / "saida" / "atalho.desktop"
    r = subprocess.run(
        ["bash", str(script), str(modelo), str(saida), executavel, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return r, saida


def _exec(arquivo: Path) -> str:
    achado = re.search(r"^Exec=(.*)$", arquivo.read_text(encoding="utf-8"), re.M)
    assert achado, arquivo
    return achado.group(1)


def _argv_do_exec(valor: str) -> list[str]:
    """O Exec= do Desktop Entry: desfaz a barra do tipo string, depois as aspas do comando."""
    texto = re.sub(r"\\(\\|s|n|t|r)", lambda m: {"\\": "\\"}.get(m.group(1), " "), valor)
    partes: list[str] = []
    atual = ""
    em_aspas = False
    tem = False
    i = 0
    while i < len(texto):
        c = texto[i]
        if em_aspas:
            if c == "\\" and i + 1 < len(texto) and texto[i + 1] in '"`$\\':
                atual += texto[i + 1]
                i += 1
            elif c == '"':
                em_aspas = False
            else:
                atual += c
        elif c == '"':
            em_aspas = True
            tem = True
        elif c == " ":
            if tem or atual:
                partes.append(atual)
            atual, tem = "", False
        else:
            atual += c
        i += 1
    if tem or atual:
        partes.append(atual)
    return [p.replace("%%", "%") for p in partes]


@pytest.mark.parametrize("formato", sorted(RECEITAS))
def test_cada_formato_renderiza_o_atalho_para_o_gui_que_o_pacote_instala(
    tmp_path: Path, formato: str
) -> None:
    modelo, destino, executavel, *resto = _chamada_do_renderizador(formato)
    assert modelo == "packaging/hefesto-dualsense4unix.desktop"
    assert resto == [], resto
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = projeto["project"]["scripts"]
    assert Path(executavel).name in scripts, f"{executavel} não é um console script do projeto"
    assert Path(executavel).name == "hefesto-dualsense4unix-gui"
    r, saida = _renderizar(tmp_path, executavel)
    assert r.returncode == 0, r.stderr
    texto = saida.read_text(encoding="utf-8")
    assert "@RAIZ@" not in texto
    assert not re.search(r"@[A-Za-z_]+@", texto)
    assert "X-HefestoNaoEmpacotado" not in texto
    assert "run.sh" not in texto
    assert _argv_do_exec(_exec(saida)) == ["env", "HEFESTO_NA_TELA=1", executavel]
    assert not any(linha.startswith("#") for linha in texto.splitlines())
    assert destino.endswith(".desktop") or destino.endswith('.desktop"'), destino


@pytest.mark.skipif(shutil.which("desktop-file-validate") is None, reason="sem desktop-file-utils")
@pytest.mark.parametrize("formato", sorted(RECEITAS))
def test_o_atalho_renderizado_passa_no_desktop_file_validate(tmp_path: Path, formato: str) -> None:
    executavel = _chamada_do_renderizador(formato)[2]
    r, saida = _renderizar(tmp_path, executavel)
    assert r.returncode == 0, r.stderr
    v = subprocess.run(
        ["desktop-file-validate", str(saida)], capture_output=True, text=True, check=False
    )
    assert v.returncode == 0, v.stdout + v.stderr


def test_nenhuma_receita_copia_o_atalho_cru() -> None:
    """A MORDIDA da cópia crua vive na seguinte: aqui, as quatro receitas de verdade."""
    for formato, receita in RECEITAS.items():
        codigo = _sem_comentario(receita.read_text(encoding="utf-8"))
        cru = re.findall(
            r"(?:^|[\s;&|])(?:cp|install)\s[^\n]*hefesto-dualsense4unix\.desktop", codigo
        )
        assert not cru, f"{formato} copia o .desktop cru: {cru}"


def test_o_gui_que_o_atalho_abre_existe_no_deb() -> None:
    codigo = _sem_comentario(RECEITAS["deb"].read_text(encoding="utf-8"))
    assert '"${STAGING}/usr/bin/hefesto-dualsense4unix-gui"' in codigo


def test_o_executavel_com_espaco_e_citado_e_vira_um_argumento_so(tmp_path: Path) -> None:
    """O anexo da auditoria: a raiz `x y/hefesto` não pode virar dois argumentos."""
    pasta = tmp_path / "x y" / "hefesto"
    pasta.mkdir(parents=True)
    exe = str(pasta / "run.sh")
    r, saida = _renderizar(tmp_path, exe, "--gui")
    assert r.returncode == 0, r.stderr
    assert _argv_do_exec(_exec(saida)) == ["env", "HEFESTO_NA_TELA=1", exe, "--gui"]
    if shutil.which("desktop-file-validate"):
        v = subprocess.run(
            ["desktop-file-validate", str(saida)], capture_output=True, text=True, check=False
        )
        assert v.returncode == 0, v.stdout + v.stderr


def test_a_regua_morde_o_executavel_sem_aspas(tmp_path: Path) -> None:
    """Tira a citação (só na cópia do renderizador): o caminho com espaço vira dois argumentos."""
    texto = RENDERIZADOR.read_text(encoding="utf-8")
    assert '" $(_citar "${_parte}")"' in texto
    mordido = tmp_path / "mordido.sh"
    mordido.write_text(texto.replace('" $(_citar "${_parte}")"', '" ${_parte}"'), encoding="utf-8")
    exe = str(tmp_path / "x y" / "run.sh")
    r, saida = _renderizar(tmp_path, exe, "--gui", script=mordido)
    assert r.returncode == 0, r.stderr
    assert _argv_do_exec(_exec(saida)) != ["env", "HEFESTO_NA_TELA=1", exe, "--gui"]


@pytest.mark.parametrize("caractere", ['"', "$", "`", "\\", "%", "'", "&", ";"])
def test_o_caractere_reservado_no_caminho_volta_inteiro(tmp_path: Path, caractere: str) -> None:
    exe = str(tmp_path / f"a{caractere}b" / "gui")
    r, saida = _renderizar(tmp_path, exe)
    assert r.returncode == 0, r.stderr
    assert _argv_do_exec(_exec(saida)) == ["env", "HEFESTO_NA_TELA=1", exe]


def test_recusa_marcador_sobrando_e_nao_entrega_o_arquivo(tmp_path: Path) -> None:
    modelo = tmp_path / "modelo.desktop"
    modelo.write_text(
        MODELO.read_text(encoding="utf-8").replace(
            "\nName=Hefesto\n", "\nName=Hefesto @NOME@\n", 1
        ),
        encoding="utf-8",
    )
    r, saida = _renderizar(tmp_path, "/usr/bin/hefesto-dualsense4unix-gui", modelo=modelo)
    assert r.returncode == 1
    assert "@NOME@" in r.stderr
    assert not saida.exists()
    assert list(saida.parent.glob("*")) == [], "sobrou arquivo parcial"


def test_recusa_executavel_que_nao_e_caminho_absoluto(tmp_path: Path) -> None:
    r, saida = _renderizar(tmp_path, "hefesto-dualsense4unix-gui")
    assert r.returncode == 2
    assert not saida.exists()


def test_recusa_modelo_que_nao_e_de_arvore(tmp_path: Path) -> None:
    modelo = tmp_path / "modelo.desktop"
    modelo.write_text("[Desktop Entry]\nExec=hefesto\n", encoding="utf-8")
    r, saida = _renderizar(tmp_path, "/usr/bin/hefesto-dualsense4unix-gui", modelo=modelo)
    assert r.returncode == 1
    assert not saida.exists()


def _repo_de_paridade(tmp: Path, receita_do_deb: str) -> Path:
    for pasta in ("scripts", "assets", "packaging/arch", "packaging/fedora", "packaging/nix"):
        (tmp / pasta).mkdir(parents=True, exist_ok=True)
    shutil.copy2(PARIDADE, tmp / "scripts" / "check_packaging_parity.sh")
    shutil.copy2(MODELO, tmp / "packaging" / "hefesto-dualsense4unix.desktop")
    icone = (
        "install -Dm644 i.png /usr/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png\n"
    )
    renderiza = (
        "bash scripts/atalho_do_pacote.sh packaging/hefesto-dualsense4unix.desktop "
        "$d/a.desktop /usr/bin/hefesto-dualsense4unix-gui\n"
    )
    (tmp / "scripts" / "build_deb.sh").write_text(icone + receita_do_deb, encoding="utf-8")
    for receita in ("packaging/arch/PKGBUILD", "packaging/nix/package.nix"):
        (tmp / receita).write_text(icone + renderiza, encoding="utf-8")
    (tmp / "packaging/fedora/hefesto-dualsense4unix.spec").write_text(
        icone + renderiza, encoding="utf-8"
    )
    return tmp


def _paridade(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/check_packaging_parity.sh"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _secao_do_atalho(saida: str) -> str:
    return saida.split("== Atalho do menu dos pacotes", 1)[1].split("\n== ", 1)[0]


def test_o_portao_barra_o_cp_cru_do_atalho_no_deb(tmp_path: Path) -> None:
    """A mordida pedida: devolver o `cp` ao `build_deb.sh` reprova a paridade."""
    renderiza = (
        "bash scripts/atalho_do_pacote.sh packaging/hefesto-dualsense4unix.desktop "
        "$d/a.desktop /usr/bin/hefesto-dualsense4unix-gui\n"
    )
    ok = _paridade(_repo_de_paridade(tmp_path / "ok", renderiza))
    assert "[FAIL]" not in _secao_do_atalho(ok.stdout), ok.stdout
    cru = "cp packaging/hefesto-dualsense4unix.desktop $d/hefesto-dualsense4unix.desktop\n"
    mordido = _paridade(_repo_de_paridade(tmp_path / "cru", cru))
    assert mordido.returncode == 1, mordido.stdout
    secao = _secao_do_atalho(mordido.stdout)
    assert "[FAIL] scripts/build_deb.sh" in secao, secao
    assert "cru" in secao


def test_o_portao_barra_o_cp_cru_mesmo_sem_a_chave_de_nao_empacotado(tmp_path: Path) -> None:
    """Quem tira a chave do modelo não desliga a régua: o marcador `@RAIZ@` basta."""
    cru = "cp packaging/hefesto-dualsense4unix.desktop $d/hefesto-dualsense4unix.desktop\n"
    repo = _repo_de_paridade(tmp_path, cru)
    modelo = repo / "packaging" / "hefesto-dualsense4unix.desktop"
    modelo.write_text(
        "".join(
            linha
            for linha in modelo.read_text(encoding="utf-8").splitlines(keepends=True)
            if not linha.startswith("X-HefestoNaoEmpacotado")
        ),
        encoding="utf-8",
    )
    r = _paridade(repo)
    assert r.returncode == 1, r.stdout
    assert "[FAIL] scripts/build_deb.sh" in _secao_do_atalho(r.stdout), r.stdout


def test_o_portao_barra_a_receita_que_esquece_o_atalho(tmp_path: Path) -> None:
    repo = _repo_de_paridade(tmp_path, "echo nada\n")
    r = _paridade(repo)
    assert r.returncode == 1, r.stdout
    assert "[FAIL] scripts/build_deb.sh: não leva o atalho do menu" in r.stdout


def test_a_isencao_da_chave_nao_vale_para_o_atalho_que_uma_receita_leva(tmp_path: Path) -> None:
    """Com a chave de não empacotado e uma receita que o leva, o Icon= volta a ser cobrado."""
    renderiza = (
        "bash scripts/atalho_do_pacote.sh packaging/hefesto-dualsense4unix.desktop "
        "$d/a.desktop /usr/bin/hefesto-dualsense4unix-gui\n"
    )
    repo = _repo_de_paridade(tmp_path, renderiza)
    (repo / "scripts" / "build_deb.sh").write_text(renderiza, encoding="utf-8")
    r = _paridade(repo)
    assert r.returncode == 1, r.stdout
    assert "sem apps/hefesto-dualsense4unix.png em: scripts/build_deb.sh" in r.stdout


def test_o_portao_real_esta_verde_no_atalho() -> None:
    r = subprocess.run(
        ["bash", "scripts/check_packaging_parity.sh"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    secao = _secao_do_atalho(r.stdout)
    assert "[FAIL]" not in secao, secao
    assert secao.count("[ OK ]") == 4, secao


def test_as_tres_fumacas_olham_o_atalho_e_o_alvo_dele() -> None:
    fluxo = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    for job in ("deb-install-smoke", "arch-smoke", "fedora-smoke"):
        passos = fluxo["jobs"][job]["steps"]
        corpo = "\n".join(p.get("run", "") for p in passos)
        assert "desktop-file-validate" in corpo, job
        assert "test -x" in corpo, f"{job}: a fumaça não confere o alvo do Exec="
        assert "X-HefestoNaoEmpacotado" in corpo, job
