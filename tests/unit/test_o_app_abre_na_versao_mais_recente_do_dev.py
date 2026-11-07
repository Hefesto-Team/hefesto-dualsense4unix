"""O app baixa o ``dev`` ao abrir e o traz ao fechar, com guarda, num repositório de mentira.

Nenhum caso toca a árvore real: o remoto é um repositório nu com o caminho do produto, o clone é
de mentira, e o ``git`` real só roda com a configuração global e a do sistema desligadas.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca
from hefesto_dualsense4unix.app.actions import versao_ao_abrir as va
from hefesto_dualsense4unix.interface import abrir as ai

RAIZ = Path(__file__).resolve().parents[2]


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(pasta), *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


def _commitar(pasta: Path, caminho: str, texto: str = "x\n") -> str:
    arquivo = pasta / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    _git(pasta, "add", caminho)
    _git(pasta, "commit", "-q", "-m", f"muda {caminho}")
    return _git(pasta, "rev-parse", "HEAD")


class Casa:
    """O remoto do produto, o clone de quem usa e o clone de quem publica."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.remoto = base / "Hefesto-Team" / "hefesto-dualsense4unix.git"
        self.remoto.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "dev", str(self.remoto)], check=True)
        self.autor = base / "autor"
        subprocess.run(["git", "clone", "-q", str(self.remoto), str(self.autor)], check=True,
                       capture_output=True)
        _git(self.autor, "checkout", "-q", "-B", "dev")
        self.inicio = _commitar(self.autor, "README.md")
        _git(self.autor, "push", "-q", "origin", "dev")
        self.clone = base / "clone"
        subprocess.run(["git", "clone", "-q", "-b", "dev", str(self.remoto), str(self.clone)],
                       check=True, capture_output=True)

    def publicar(self, caminho: str) -> str:
        alvo = _commitar(self.autor, caminho)
        _git(self.autor, "push", "-q", "origin", "dev")
        return alvo

    def publicar_mudanca_de_lugar(self) -> str:
        _git(self.autor, "mv", "assets/uma-unit.service", "docs-uma-unit.service")
        _git(self.autor, "commit", "-q", "-m", "muda de lugar")
        _git(self.autor, "push", "-q", "origin", "dev")
        _git(self.clone, "fetch", "-q", "origin", "dev")
        return _git(self.autor, "rev-parse", "HEAD")

    def topo(self) -> str:
        return _git(self.clone, "rev-parse", "HEAD")

    def retrato(self) -> tuple[str, str, str]:
        return (self.topo(), _git(self.clone, "rev-parse", "--abbrev-ref", "HEAD"),
                _git(self.clone, "status", "--porcelain"))


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Casa:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@t.t")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@t.t")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    (tmp_path / "run").mkdir()
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "state_dir", lambda ensure=False: _pasta(tmp_path / "estado"))
    monkeypatch.setattr(troca, "_jogo_aberto", lambda: False)
    return Casa(tmp_path)


def _pasta(caminho: Path) -> Path:
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def _sem_jogo() -> bool:
    return False


def _sujar(casa: Casa) -> None:
    (casa.clone / "README.md").write_text("trabalho de quem desenvolve\n", encoding="utf-8")


def _criar_arquivo_novo(casa: Casa) -> None:
    (casa.clone / "rascunho.txt").write_text("y\n", encoding="utf-8")


def _outro_ramo(casa: Casa) -> None:
    _git(casa.clone, "checkout", "-q", "-b", "trabalho")


def _marca_de_voo(casa: Casa) -> None:
    (casa.clone / ".git" / va.MARCA_DE_VOO).write_text("um-conjunto\n", encoding="utf-8")


def _sem_o_remoto(casa: Casa) -> None:
    casa.remoto.rename(casa.base / "fora-do-ar.git")


def _remoto_de_outro(casa: Casa) -> None:
    destino = casa.base / "outra-pessoa" / "hefesto-dualsense4unix.git"
    destino.parent.mkdir()
    casa.remoto.rename(destino)
    _git(casa.clone, "remote", "set-url", "origin", str(destino))


@pytest.mark.parametrize("preparar", [
    _sujar, _criar_arquivo_novo, _outro_ramo, _marca_de_voo, _sem_o_remoto, _remoto_de_outro,
], ids=lambda f: f.__name__)
def test_cada_guarda_para_a_baixa_e_nada_muda(
    casa: Casa, preparar: Callable[[Casa], None],
) -> None:
    casa.publicar("src/novo.py")
    preparar(casa)
    antes = casa.retrato()
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) is None
    assert casa.retrato() == antes


def test_o_jogo_aberto_para_a_baixa_antes_da_rede(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.publicar("src/novo.py")
    monkeypatch.setattr(va, "remoto_do_produto", lambda _r: pytest.fail("foi à rede"))
    assert va.baixar(casa.clone, jogo_aberto=lambda: True) is None


def test_a_marca_vazia_nao_segura_e_a_guarda_olha_a_marca_comum_numa_worktree(casa: Casa) -> None:
    (casa.clone / ".git" / va.MARCA_DE_VOO).write_text("", encoding="utf-8")
    alvo = casa.publicar("src/novo.py")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo

    arvore = casa.base / "arvore"
    _git(casa.clone, "checkout", "-q", "--detach")
    _git(casa.clone, "worktree", "add", "-q", str(arvore), "dev")
    assert (arvore / ".git").is_file()
    assert va.por_que_nao(arvore, _sem_jogo) == ""
    _marca_de_voo(casa)
    assert va.por_que_nao(arvore, _sem_jogo) == "trabalho em voo"


def test_baixar_nao_toca_a_arvore_e_aplicar_avanca_e_reinicia_o_servico(casa: Casa) -> None:
    alvo = casa.publicar("src/hefesto/novo.py")
    inicio = casa.topo()
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    assert casa.topo() == inicio and not (casa.clone / "src").exists()

    pedidos: list[Any] = []
    assert va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert casa.topo() == alvo
    assert pedidos == [("daemon",)]


def test_ja_na_mais_recente_nao_ha_o_que_aplicar(casa: Casa) -> None:
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) is None


@pytest.mark.parametrize("caminho", [
    "install.sh", "pyproject.toml", "constraints.txt", "assets/logo.png", "scripts/portoes.sh",
    "packaging/hefesto.desktop", "locale/en/LC_MESSAGES/hefesto.mo",
    *(n for n in va.PEDEM_INSTALL if n.startswith(va.PASTA_DO_SERVICO)),
])
def test_a_faixa_que_pede_install_nao_roda_nada_e_fica_anotada(casa: Casa, caminho: str) -> None:
    casa.publicar("src/hefesto/novo.py")
    alvo = casa.publicar(caminho)
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    pedidos: list[Any] = []
    assert va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert casa.topo() == alvo
    assert pedidos == []
    nota = casa.base / "estado" / va.ANOTACAO_DO_INSTALL
    assert nota.read_text(encoding="utf-8").strip().endswith(alvo[:va.CURTO])


def _o_que_o_install_le() -> set[str]:
    fontes = [RAIZ / "install.sh", *sorted((RAIZ / "scripts" / "lib").glob("*.sh"))]
    return {
        achado for fonte in fontes
        for achado in re.findall(r'\$\{ROOT_DIR\}/([\w./-]+)', fonte.read_text(encoding="utf-8"))
    }


def test_toda_copia_que_o_install_faz_do_codigo_pede_install() -> None:
    copias = set()
    for fonte in (RAIZ / "install.sh", *sorted((RAIZ / "scripts" / "lib").glob("*.sh"))):
        copias |= set(re.findall(
            r'_(?:SRC|src)="\$\{ROOT_DIR\}/(src/[^"]+)"', fonte.read_text(encoding="utf-8")))
    assert len(copias) >= 5
    assert {c: va.o_que_a_faixa_pede([c]) for c in copias} == dict.fromkeys(copias, "install")


def test_toda_pasta_que_o_install_le_esta_classificada() -> None:
    lidos_na_hora = {".venv", "dist", "run.sh", "src"}
    topos = {caminho.split("/")[0] for caminho in _o_que_o_install_le()}
    assert len(topos) >= 6
    assert {
        t for t in topos - lidos_na_hora
        if va.o_que_a_faixa_pede([f"{t}/um-arquivo", t]) != "install"
    } == set()


def test_a_mudanca_de_lugar_conta_os_dois_lados(casa: Casa) -> None:
    casa.publicar("assets/uma-unit.service")
    _git(casa.clone, "pull", "-q", "--ff-only", "origin", "dev")
    assert va.aplicar(casa.clone, casa.publicar_mudanca_de_lugar(), jogo_aberto=_sem_jogo,
                      disparar=lambda _i: None)
    assert (casa.base / "estado" / va.ANOTACAO_DO_INSTALL).read_text(encoding="utf-8").strip()


def test_o_arquivo_ignorado_de_quem_desenvolve_nunca_e_sobrescrito(casa: Casa) -> None:
    _commitar(casa.autor, ".gitignore", "rascunho-local.md\n")
    _git(casa.autor, "push", "-q", "origin", "dev")
    _git(casa.clone, "pull", "-q", "--ff-only", "origin", "dev")
    (casa.autor / "rascunho-local.md").write_text("do remoto\n", encoding="utf-8")
    _git(casa.autor, "add", "-f", "rascunho-local.md")
    _git(casa.autor, "commit", "-q", "-m", "o remoto passa a versionar")
    _git(casa.autor, "push", "-q", "origin", "dev")
    (casa.clone / "rascunho-local.md").write_text("de quem desenvolve\n", encoding="utf-8")

    alvo = va.baixar(casa.clone, jogo_aberto=_sem_jogo)
    assert alvo
    inicio = casa.topo()
    pedidos: list[Any] = []
    assert not va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert (casa.clone / "rascunho-local.md").read_text(encoding="utf-8") == "de quem desenvolve\n"
    assert casa.topo() == inicio and pedidos == []


def test_a_anotacao_sai_com_o_install_no_mesmo_caminho_que_o_produto_grava(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    linha = next(
        linha for linha in (RAIZ / "install.sh").read_text(encoding="utf-8").splitlines()
        if va.ANOTACAO_DO_INSTALL in linha
    )
    nota = state_dir(ensure=True) / va.ANOTACAO_DO_INSTALL
    assert nota.is_relative_to(tmp_path)
    nota.write_text("a..b\n", encoding="utf-8")

    subprocess.run(["bash", "-c", f"DRY_RUN=1; {linha}"], check=True)
    assert nota.exists(), "o ensaio do install apagou a anotação"
    subprocess.run(["bash", "-c", f"DRY_RUN=0; {linha}"], check=True)
    assert not nota.exists()


def test_a_faixa_so_de_documento_nao_reinicia_nada(casa: Casa) -> None:
    alvo = casa.publicar("docs/uma-pagina.md")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    pedidos: list[Any] = []
    assert va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert pedidos == []
    assert not (casa.base / "estado" / va.ANOTACAO_DO_INSTALL).exists()


def test_o_servico_parado_pela_aba_sistema_segue_parado(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.utils import marca_do_parar as mp

    marca = casa.base / "parado"
    marca.touch()
    monkeypatch.setattr(mp, "marca_do_parar", lambda: marca)
    alvo = casa.publicar("src/hefesto/novo.py")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    pedidos: list[Any] = []
    assert va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert casa.topo() == alvo
    assert pedidos == []


def test_a_guarda_volta_no_fecho(casa: Casa) -> None:
    alvo = casa.publicar("src/hefesto/novo.py")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    inicio = casa.topo()
    pedidos: list[Any] = []

    assert not va.aplicar(casa.clone, alvo, jogo_aberto=lambda: True, disparar=pedidos.append)
    _sujar(casa)
    assert not va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert casa.topo() == inicio and pedidos == []
    assert "trabalho de quem desenvolve" in (casa.clone / "README.md").read_text(encoding="utf-8")


def test_o_ramo_a_frente_do_remoto_nem_promete_a_baixada(
    casa: Casa, capsys: pytest.CaptureFixture[str],
) -> None:
    _commitar(casa.clone, "trabalho.txt")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) is None
    saida = capsys.readouterr().out
    assert va.FORA_DO_AVANCO in saida and "entra quando" not in saida


def test_a_marca_ilegivel_conta_como_voo(casa: Casa) -> None:
    (casa.clone / ".git" / va.MARCA_DE_VOO).mkdir()
    assert va.por_que_nao(casa.clone, _sem_jogo) == "trabalho em voo"


def test_o_ramo_que_divergiu_fica_como_esta(casa: Casa) -> None:
    alvo = casa.publicar("src/hefesto/novo.py")
    local = _commitar(casa.clone, "trabalho.txt")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) is None
    _git(casa.clone, "fetch", "-q", "origin", "dev")
    pedidos: list[Any] = []
    assert not va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append)
    assert casa.topo() == local and pedidos == []


def _capturar_o_fim(monkeypatch: pytest.MonkeyPatch) -> list[Callable[[], None]]:
    fins: list[Callable[[], None]] = []
    monkeypatch.setattr(va, "_a_suite_esta_rodando", lambda: False)
    monkeypatch.setattr(va.atexit, "register", fins.append)
    return fins


def test_o_avanco_so_acontece_no_fim_do_processo(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fins = _capturar_o_fim(monkeypatch)
    pedidos: list[Any] = []
    monkeypatch.setattr(troca, "disparar", pedidos.append)
    alvo = casa.publicar("src/hefesto/novo.py")
    inicio = casa.topo()

    fio = va.baixar_ao_abrir(casa.clone)
    assert fio is not None
    fio.join(10)
    assert not fio.is_alive()
    assert casa.topo() == inicio, "a árvore andou com a janela de pé"

    assert len(fins) == 1
    fins[0]()
    assert casa.topo() == alvo
    assert pedidos == [("daemon",)]


def test_a_instalacao_sem_clone_nem_solta_o_fio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fins = _capturar_o_fim(monkeypatch)
    monkeypatch.setattr(va.threading, "Thread", lambda **_k: pytest.fail("soltou o fio"))
    assert va.baixar_ao_abrir(tmp_path) is None
    assert fins == []


def test_a_suite_nunca_baixa(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert va.baixar_ao_abrir(tmp_path) is None


def _git_que_dorme(pasta: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``git`` que dorme 60 s num neto e anota o pid dele, como o ssh do fetch."""
    livro = pasta / "neto.pid"
    binario = _pasta(pasta / "bin") / "git"
    binario.write_text(
        "#!/bin/bash\n"
        f"sleep 60 & echo $! > {livro}\n"
        "wait\n", encoding="utf-8")
    binario.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binario.parent}:{os.environ['PATH']}")
    return livro


def test_o_git_que_dorme_nao_segura_a_abertura_e_morre_no_teto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    livro = _git_que_dorme(tmp_path, monkeypatch)
    _capturar_o_fim(monkeypatch)
    monkeypatch.setattr(va, "TETO_DO_GIT_S", 0.4)

    inicio = time.monotonic()
    fio = va.baixar_ao_abrir(tmp_path)
    tempo_da_chamada = time.monotonic() - inicio
    assert fio is not None
    assert tempo_da_chamada < 0.3
    fio.join(10)
    assert not fio.is_alive()
    neto = int(livro.read_text(encoding="utf-8"))
    for _ in range(100):
        if not Path(f"/proc/{neto}").exists():
            break
        time.sleep(0.02)
    assert not Path(f"/proc/{neto}").exists(), "o neto do git passou do teto"


def test_o_fio_que_erra_nao_derruba_a_janela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / ".git").mkdir()
    fins = _capturar_o_fim(monkeypatch)

    def _explodir(_raiz: Path) -> None:
        raise RuntimeError("quebrou")

    monkeypatch.setattr(va, "baixar", _explodir)
    fio = va.baixar_ao_abrir(tmp_path)
    assert fio is not None
    fio.join(5)
    fins[0]()
    assert "quebrou" in capsys.readouterr().out


def test_sem_o_git_no_computador_a_janela_segue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / ".git").mkdir()
    _capturar_o_fim(monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path))
    fio = va.baixar_ao_abrir(tmp_path)
    assert fio is not None
    fio.join(5)
    assert not fio.is_alive()
    assert "fica como está" in capsys.readouterr().out


def test_o_avanco_nunca_morre_no_teto_e_a_rede_sempre(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidos: list[tuple[tuple[str, ...], bool]] = []
    real = va._git

    def _anotar(raiz: Path, *args: str, com_teto: bool = True) -> str | None:
        pedidos.append((args, com_teto))
        return real(raiz, *args, com_teto=com_teto)

    monkeypatch.setattr(va, "_git", _anotar)
    alvo = casa.publicar("src/hefesto/novo.py")
    assert va.baixar(casa.clone, jogo_aberto=_sem_jogo) == alvo
    assert va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=lambda _i: None)
    assert [c for a, c in pedidos if a[0] == "merge"] == [False]
    assert [c for a, c in pedidos if a[0] == "fetch"] == [True]


@pytest.mark.parametrize(("endereco", "casa_"), [
    ("git@github.com-personal:Hefesto-Team/hefesto-dualsense4unix.git", True),
    ("git@github.com:Hefesto-Team/hefesto-dualsense4unix.git", True),
    ("https://github.com/Hefesto-Team/hefesto-dualsense4unix.git", True),
    ("https://github.com/hefesto-team/hefesto-dualsense4unix", True),
    ("ssh://git@github.com/Hefesto-Team/hefesto-dualsense4unix.git/", True),
    ("https://github.com/outra/hefesto-dualsense4unix.git", False),
    ("https://github.com/Falso-Hefesto-Team/hefesto-dualsense4unix.git", False),
    ("https://github.com/Hefesto-Team/hefesto-dualsense4unix-velho.git", False),
])
def test_o_remoto_se_acha_pelo_endereco(endereco: str, casa_: bool) -> None:
    assert bool(va.REPOSITORIO.search(endereco)) is casa_


def test_o_remoto_se_acha_por_qualquer_nome(casa: Casa) -> None:
    _git(casa.clone, "remote", "rename", "origin", "upstream")
    _git(casa.clone, "remote", "add", "fork", "https://github.com/outra/hefesto-dualsense4unix.git")
    assert va.remoto_do_produto(casa.clone) == "upstream"


@pytest.fixture
def abertura(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """``abrir`` inteiro, com tudo que abre janela de mentira, anotando a ordem."""
    ordem: list[str] = []
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja

    monkeypatch.setattr(ai, "garantir_tela_de_mentira", lambda: None)
    monkeypatch.setattr(ai, "diario_da_janela", lambda: None)
    monkeypatch.setattr(ai, "achar_o_piloto", lambda: "piloto_de_mentira")
    monkeypatch.setattr(ai, "tomar_a_vez", lambda _a: "")
    monkeypatch.setattr(ai, "vestir_a_identidade", lambda _c: [])
    monkeypatch.setattr(ai, "trazer_o_servico", lambda: ordem.append("serviço"))
    monkeypatch.setattr(atos_da_bandeja, "garantir_a_bandeja", lambda: ordem.append("bandeja"))
    monkeypatch.setattr(va, "baixar_ao_abrir", lambda r: ordem.append(f"baixa:{r}"))
    monkeypatch.setattr(ai.runpy, "run_module", lambda *_a, **_k: ordem.append("piloto"))
    monkeypatch.setattr(ai.sys, "argv", ["abrir"])
    return {"ordem": ordem}


def test_a_baixa_nasce_antes_do_piloto_com_a_janela_na_tela(
    abertura: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEFESTO_NA_TELA", "1")
    assert ai.abrir([]) == 0
    assert abertura["ordem"] == ["bandeja", "serviço", f"baixa:{ai.RAIZ}", "piloto"]


@pytest.mark.parametrize("args", [["--oculta"], []], ids=["oculta", "sem-tela"])
def test_a_janela_fora_da_tela_nao_baixa(
    abertura: dict[str, Any], monkeypatch: pytest.MonkeyPatch, args: list[str],
) -> None:
    if args:
        monkeypatch.setenv("HEFESTO_NA_TELA", "1")
    else:
        monkeypatch.delenv("HEFESTO_NA_TELA", raising=False)
    assert ai.abrir(list(args)) == 0
    assert abertura["ordem"] == ["piloto"]


def test_o_fio_de_baixa_nao_e_o_fio_da_janela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    _capturar_o_fim(monkeypatch)
    viu: list[threading.Thread] = []
    monkeypatch.setattr(va, "baixar", lambda _r: viu.append(threading.current_thread()))
    fio = va.baixar_ao_abrir(tmp_path)
    assert fio is not None
    fio.join(5)
    assert viu == [fio] and fio.daemon and fio.name == "versao-ao-abrir"
