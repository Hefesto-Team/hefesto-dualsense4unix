"""O avanço que pede install o roda sozinho, fora da janela, com o ``install.sh`` dublado.

O clone é de mentira, o ``git`` é o real sem configuração global, e o dublê do install apaga a nota
com a linha que o ``install.sh`` de verdade traz. O ``sudo`` dublado anota cada chamada, e assim um
``sudo`` na frente do install apareceria no livro dele, e não no do install.

Decisão proposta (a validar):
D-2611-A-NOTA-DO-INSTALL-NASCE-DO-PULO-DE-ROOT-QUE-O-INSTALL-GRAVA, o install é o único dono do
que ficou sem root (grava ``install-pulou-root``), a nota diz o erro real quando ele falha e só
diz «sem autorização» quando ele pulou um passo de administrador.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import typer

from hefesto_dualsense4unix.app.actions import recarga_do_install as recarga
from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca
from hefesto_dualsense4unix.app.actions import versao_ao_abrir as va
from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.integrations import fora_do_servico as fora
from hefesto_dualsense4unix.interface.pacotes import a09_sistema
from hefesto_dualsense4unix.utils.marca_do_parar import lembrar_o_parar
from hefesto_dualsense4unix.utils.xdg_paths import state_dir
from tests.unit.test_o_avanco_do_dev_so_com_commit_assinado import (
    assinar_todo_commit,
    gravar_a_lista,
)

RAIZ = Path(__file__).resolve().parents[2]
ESPERA_S = troca.ESPERA_SEM_JOGO_S
GRAVA_AS_ESCOLHAS = '"--format=${FORMAT:-native}" "$@"'


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(pasta), *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


def _a_linha_do_install(trecho: str) -> str:
    return next(
        linha for linha in (RAIZ / "install.sh").read_text(encoding="utf-8").splitlines()
        if trecho in linha
    )


class Tempo:
    """O relógio da espera: dormir anda o tempo, e nada dorme de verdade."""

    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.agora += segundos


class Casa:
    """O remoto, o clone de quem usa, o livro do install e o livro do ``sudo``."""

    def __init__(self, base: Path, chave: Path) -> None:
        self.base = base
        self.livro = base / "livro-do-install"
        self.livro_do_sudo = base / "livro-do-sudo"
        self.quebra = base / "o-install-quebra"
        self.pulou = base / "o-install-pulou-o-root"
        self.dorme = base / "o-install-dorme"
        self.neto = base / "neto-do-install"
        self.fim = base / "o-trap-do-install-rodou"
        self.teimoso = base / "o-install-ignora-o-sigterm"
        self.ambiente = base / "ambiente-do-install"
        self.autor = base / "autor"
        self.autor.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "dev", str(self.autor)], check=True)
        gravar_a_lista(self.autor, chave)
        self.inicio = self.publicar("README.md")
        instalador = self.autor / "install.sh"
        instalador.write_text(
            "#!/bin/bash\n"
            f"{_a_linha_do_install(va.MARCA_DO_INSTALL)}\n"
            f'printf \'%s\\n\' "$*" >> {self.livro}\n'
            f'printf \'%s|%s\\n\' "${{VIRTUAL_ENV:-}}" "$PATH" > {self.ambiente}\n'
            "echo 'a saída do install'\n"
            f"if [ -e {self.pulou} ]; then\n"
            '  mkdir -p "${XDG_STATE_HOME}/hefesto-dualsense4unix"\n'
            "  printf '%s\\n' 'sudo recusado — passo pulado' "
            '> "${XDG_STATE_HOME}/hefesto-dualsense4unix/install-pulou-root"\n'
            "fi\n"
            f"[ ! -e {self.quebra} ] || exit 7\n"
            f"[ ! -e {self.teimoso} ] || trap '' TERM\n"
            f"if [ -e {self.dorme} ]; then\n"
            f"  trap 'touch {self.fim}' EXIT\n"
            f"  sleep 60 & echo $! > {self.neto}; wait\n"
            "fi\n"
            "DRY_RUN=0\n"
            "FORMAT=native\n"
            f"{_a_linha_do_install(va.ANOTACAO_DO_INSTALL)}\n"
            f"{_a_linha_do_install(GRAVA_AS_ESCOLHAS)}\n",
            encoding="utf-8")
        instalador.chmod(0o755)
        self.commitar("install.sh")
        self.clone = base / "clone"
        subprocess.run(["git", "clone", "-q", "-b", "dev", str(self.autor), str(self.clone)],
                       check=True, capture_output=True)

    def commitar(self, caminho: str) -> str:
        _git(self.autor, "add", caminho)
        _git(self.autor, "commit", "-q", "-m", f"muda {caminho}")
        return _git(self.autor, "rev-parse", "HEAD")

    def publicar(self, caminho: str) -> str:
        arquivo = self.autor / caminho
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(f"{caminho}\n", encoding="utf-8")
        return self.commitar(caminho)

    def avancar(self, caminho: str = "scripts/novo.sh") -> str:
        alvo = self.publicar(caminho)
        _git(self.clone, "fetch", "-q", "origin", "dev")
        return alvo

    def anotar(self, *linhas: str) -> None:
        self.nota.write_text("".join(f"{linha}\n" for linha in linhas), encoding="utf-8")

    def install_a_mao_em_curso(self) -> subprocess.Popen[bytes]:
        self.dorme.touch()
        processo = subprocess.Popen([self.clone / "install.sh"], cwd=self.clone,
                                    start_new_session=True)
        marca = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix" / va.MARCA_DO_INSTALL
        for _ in range(250):
            if marca.exists() and self.neto.exists():
                return processo
            time.sleep(0.02)
        raise AssertionError("o install de mentira não anotou o PID")

    def instalar_a_mao(self, *flags: str) -> None:
        subprocess.run([self.clone / "install.sh", *flags], check=True, cwd=self.clone)

    @property
    def nota(self) -> Path:
        return state_dir(ensure=True) / va.ANOTACAO_DO_INSTALL

    def rodadas(self) -> list[str]:
        return self.livro.read_text(encoding="utf-8").splitlines() if self.livro.exists() else []

    def chamadas_do_sudo(self) -> list[str]:
        if not self.livro_do_sudo.exists():
            return []
        return self.livro_do_sudo.read_text(encoding="utf-8").splitlines()


def _sudo_de_mentira(casa: Casa, bin_: Path, *, aceita: str) -> None:
    bin_.mkdir(exist_ok=True)
    binario = bin_ / "sudo"
    binario.write_text(
        "#!/bin/bash\n"
        f'printf \'%s\\n\' "$*" >> {casa.livro_do_sudo}\n'
        f'case "$*" in {aceita}) exit 0 ;; esac\n'
        "exit 1\n", encoding="utf-8")
    binario.chmod(0o755)


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
    monkeypatch.delenv("SUDO_ASKPASS", raising=False)
    (tmp_path / "run").mkdir()
    casa_ = Casa(tmp_path, assinar_todo_commit(tmp_path, monkeypatch))
    _sudo_de_mentira(casa_, tmp_path / "bin", aceita="'-n true'")
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    return casa_


def _sem_jogo() -> bool:
    return False


def _rodar_a_vigia(
    casa: Casa,
    jogo_aberto: Callable[[], bool] = _sem_jogo,
    tempo: Tempo | None = None,
    prazo_s: float | None = None,
) -> Tempo:
    tempo = tempo or Tempo()
    assert va.esperar_e_instalar(
        casa.clone, jogo_aberto=jogo_aberto, relogio=tempo, dormir=tempo.dormir, prazo_s=prazo_s,
    ) == 0
    return tempo


def _fechar_a_janela(casa: Casa, alvo: str) -> bool:
    pedidos: list[Any] = []

    def _instalar(_raiz: Path) -> None:
        _rodar_a_vigia(casa)

    avancou = va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=pedidos.append,
                         instalar=_instalar)
    assert pedidos == []
    return avancou


def test_a_faixa_que_pede_install_roda_uma_vez_so_e_a_nota_sai(casa: Casa) -> None:
    alvo = casa.avancar()
    assert _fechar_a_janela(casa, alvo)
    assert _git(casa.clone, "rev-parse", "HEAD") == alvo
    assert casa.rodadas() == ["--yes"]
    assert not casa.nota.exists()
    _rodar_a_vigia(casa)
    assert casa.rodadas() == ["--yes"], "a segunda vigia rodou o install de novo"


def test_duas_vigias_ao_mesmo_tempo_rodam_o_install_uma_vez_so(casa: Casa) -> None:
    casa.anotar("a..b")
    trava = va._a_trava_do_install()
    assert trava is not None
    try:
        _rodar_a_vigia(casa)
    finally:
        os.close(trava)
    assert casa.rodadas() == []
    assert casa.nota.exists()


def test_o_jogo_aberto_espera_e_o_install_roda_depois_de_fechado_de_vez(casa: Casa) -> None:
    casa.anotar("a..b")
    tempo = Tempo()
    fecha_em = 60.0
    quando: list[float] = []

    def _rodar(raiz: Path) -> str:
        quando.append(tempo.agora)
        return va._rodar_o_install(raiz)

    assert va.esperar_e_instalar(
        casa.clone, jogo_aberto=lambda: tempo.agora < fecha_em, rodar=_rodar, relogio=tempo,
        dormir=tempo.dormir,
    ) == 0
    assert len(quando) == 1 and quando[0] >= fecha_em + ESPERA_S
    assert casa.rodadas() == ["--yes"]


def test_o_jogo_que_nao_fecha_nao_roda_e_a_faixa_fica_sem_motivo(casa: Casa) -> None:
    casa.anotar("a..b")
    _rodar_a_vigia(casa, jogo_aberto=lambda: True, prazo_s=120.0)
    assert casa.rodadas() == []
    assert casa.nota.read_text(encoding="utf-8") == "a..b\n"
    assert va.pendencia_do_install() is None


def test_a_pergunta_do_jogo_se_repete_na_hora_de_rodar(casa: Casa) -> None:
    casa.anotar("a..b")
    tempo = Tempo()
    perguntas_depois_da_espera: list[float] = []

    def _jogo_que_abre_na_ultima_hora() -> bool:
        if tempo.agora < ESPERA_S:
            return False
        perguntas_depois_da_espera.append(tempo.agora)
        return len(perguntas_depois_da_espera) > 1

    _rodar_a_vigia(casa, jogo_aberto=_jogo_que_abre_na_ultima_hora, tempo=tempo, prazo_s=30.0)
    assert perguntas_depois_da_espera[:2] == [ESPERA_S, ESPERA_S]
    assert casa.rodadas() == []


def test_o_jogo_da_ultima_hora_recomeca_a_espera_e_o_install_roda_depois(casa: Casa) -> None:
    casa.anotar("a..b")
    tempo = Tempo()
    respostas = iter([False] * int(ESPERA_S / troca.PASSO_DA_VIGIA_S + 1) + [True])

    _rodar_a_vigia(casa, jogo_aberto=lambda: next(respostas, False), tempo=tempo)
    assert casa.rodadas() == ["--yes"]
    assert tempo.agora >= 2 * ESPERA_S


@pytest.mark.parametrize("gesto", ["voo", "suja", "ramo", "parado"])
def test_a_guarda_fechada_nao_roda_e_a_faixa_fica(casa: Casa, gesto: str) -> None:
    casa.anotar("a..b")
    if gesto == "voo":
        _git(casa.clone, "worktree", "add", "-q", "-b", "voo/um-conjunto",
             str(casa.base / "voo" / "um-conjunto"), "dev")
        (casa.clone / ".git" / va.MARCA_DE_VOO).write_text("um-conjunto\n", encoding="utf-8")
    elif gesto == "suja":
        (casa.clone / "README.md").write_text("trabalho\n", encoding="utf-8")
    elif gesto == "ramo":
        _git(casa.clone, "checkout", "-q", "-b", "trabalho")
    else:
        lembrar_o_parar(True)
    _rodar_a_vigia(casa)
    assert casa.rodadas() == []
    assert casa.nota.read_text(encoding="utf-8") == "a..b\n"
    assert va.pendencia_do_install() is None


def test_a_falha_deixa_a_nota_com_o_motivo_e_a_faixa(casa: Casa) -> None:
    casa.quebra.touch()
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    assert casa.nota.read_text(encoding="utf-8") == "a..b\nmotivo: o install saiu com o código 7\n"
    linha = va.pendencia_do_install()
    assert linha is not None and linha[0] == "[WARN]"
    assert "o install saiu com o código 7" in linha[1]


def test_o_install_que_nao_abre_deixa_o_motivo(casa: Casa) -> None:
    _git(casa.clone, "rm", "-q", "install.sh")
    _git(casa.clone, "commit", "-q", "-m", "sem o instalador")
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    assert "o install não abriu" in casa.nota.read_text(encoding="utf-8")


def _o_neto_morreu(casa: Casa) -> None:
    neto = int(casa.neto.read_text(encoding="utf-8"))
    for _ in range(100):
        if not Path(f"/proc/{neto}").exists():
            return
        time.sleep(0.02)
    raise AssertionError("o neto do install passou do teto")


def test_o_install_que_passa_do_teto_morre_com_os_filhos_e_deixa_o_motivo(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.dorme.touch()
    casa.anotar("a..b")
    monkeypatch.setattr(va, "TETO_DO_INSTALL_S", 0.4)
    monkeypatch.setattr(va, "FOLGA_DO_FIM_DO_INSTALL_S", 3.0)
    _rodar_a_vigia(casa)
    assert "passou de" in casa.nota.read_text(encoding="utf-8")
    _o_neto_morreu(casa)
    assert casa.fim.exists(), "sem o trap do install, a Steam fechada não reabre"


def test_o_install_que_ignora_o_sigterm_morre_no_fim_da_folga(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.dorme.touch()
    casa.teimoso.touch()
    casa.anotar("a..b")
    monkeypatch.setattr(va, "TETO_DO_INSTALL_S", 0.4)
    monkeypatch.setattr(va, "FOLGA_DO_FIM_DO_INSTALL_S", 0.4)
    _rodar_a_vigia(casa)
    assert "passou de" in casa.nota.read_text(encoding="utf-8")
    _o_neto_morreu(casa)


def test_sem_autorizacao_a_parte_do_usuario_roda_e_a_do_sistema_fica_pendente(
    casa: Casa, tmp_path: Path,
) -> None:
    _sudo_de_mentira(casa, tmp_path / "bin", aceita="nunca")
    casa.pulou.touch()
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    assert casa.rodadas() == ["--yes"]
    assert casa.chamadas_do_sudo() == []
    assert casa.nota.read_text(encoding="utf-8") == f"a..b\nmotivo: {va.SEM_AUTORIZACAO}\n"
    linha = va.pendencia_do_install()
    assert linha is not None and va.SEM_AUTORIZACAO in linha[1]


def test_o_install_que_falhou_diz_o_erro_real_mesmo_sem_autorizacao(
    casa: Casa, tmp_path: Path,
) -> None:
    """D-2611-A-NOTA-DO-INSTALL-NASCE-DO-PULO-DE-ROOT-QUE-O-INSTALL-GRAVA: a falha diz o erro."""
    _sudo_de_mentira(casa, tmp_path / "bin", aceita="nunca")
    casa.pulou.touch()
    casa.quebra.touch()
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    texto = casa.nota.read_text(encoding="utf-8")
    assert texto == "a..b\nmotivo: o install saiu com o código 7\n", texto
    assert va.SEM_AUTORIZACAO not in texto


def test_o_install_sem_passo_de_root_pulado_nao_deixa_nota_sem_autorizacao(
    casa: Casa, tmp_path: Path,
) -> None:
    _sudo_de_mentira(casa, tmp_path / "bin", aceita="nunca")
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    assert casa.rodadas() == ["--yes"]
    assert not casa.nota.exists()
    assert va.pendencia_do_install() is None


def test_o_pulo_de_um_install_antigo_nao_vale_para_o_install_de_agora(casa: Casa) -> None:
    velho = state_dir(ensure=True) / va.PULOS_DE_ROOT_DO_INSTALL
    velho.write_text("sudo recusado — passo de ontem\n", encoding="utf-8")
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    assert not casa.nota.exists()


def _o_install_de_verdade(corpo: str, home: Path, *, ensaio: bool = False) -> str:
    fonte = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = fonte.index("_PULOS_DE_ROOT=\"\"\n_PULOS_COMECARAM=0")
    fim = fonte.index("die()", inicio)
    comeco = fonte.index('if [[ "${DRY_RUN:-0}" -eq 0 ]]; then\n    _PULOS_DE_ROOT=')
    fim_do_comeco = fonte.index("\nfi\n", comeco) + 4
    final = next(
        linha for linha in fonte.splitlines()
        if linha.startswith('[[ -z "${_PULOS_DE_ROOT:-}"'))
    roteiro = (f"DRY_RUN={1 if ensaio else 0}\n{fonte[inicio:fim]}\n{fonte[comeco:fim_do_comeco]}\n"
               f"{corpo}\n{final}\n")
    ambiente = {"PATH": os.environ["PATH"], "HOME": str(home),
                "XDG_STATE_HOME": str(home / "estado")}
    return subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True,
                          check=True, timeout=20).stdout


def _os_pulos(home: Path) -> Path:
    return home / "estado" / "hefesto-dualsense4unix" / va.PULOS_DE_ROOT_DO_INSTALL


@pytest.mark.parametrize("aviso", [
    "sudo recusado — passo do portal da casa pulado (re-execute ./install.sh)",
    "sudo ausente — não consigo instalar pacote",
    "sudo indisponível/recusado — a economia de energia do Wi-Fi NÃO foi desligada; re-execute:",
    "sem o comando sudo: config do BlueZ e modprobe.d do btusb NÃO aplicados",
])
def test_o_install_grava_cada_passo_de_root_que_pulou(tmp_path: Path, aviso: str) -> None:
    _o_install_de_verdade(f'warn "{aviso}"\nwarn "um aviso qualquer"', tmp_path)
    assert _os_pulos(tmp_path).read_text(encoding="utf-8") == f"{aviso}\n"


def test_o_install_que_nao_pulou_nada_nao_deixa_o_arquivo(tmp_path: Path) -> None:
    _o_install_de_verdade('warn "o apt não leu a fonte — rode: sudo apt update"', tmp_path)
    assert not _os_pulos(tmp_path).exists()


def test_o_install_sem_pulo_apaga_o_arquivo_do_install_anterior(tmp_path: Path) -> None:
    _os_pulos(tmp_path).parent.mkdir(parents=True)
    _os_pulos(tmp_path).write_text("sudo recusado — passo de ontem\n", encoding="utf-8")
    _o_install_de_verdade('warn "um aviso qualquer"', tmp_path)
    assert not _os_pulos(tmp_path).exists()


def test_o_install_que_pulou_troca_o_arquivo_do_install_anterior(tmp_path: Path) -> None:
    _os_pulos(tmp_path).parent.mkdir(parents=True)
    _os_pulos(tmp_path).write_text("sudo recusado — passo de ontem\n", encoding="utf-8")
    _o_install_de_verdade('warn "sudo recusado — passo de hoje"', tmp_path)
    assert _os_pulos(tmp_path).read_text(encoding="utf-8") == "sudo recusado — passo de hoje\n"


def test_o_ensaio_nao_escreve_o_arquivo_dos_pulos(tmp_path: Path) -> None:
    _o_install_de_verdade('warn "sudo recusado — passo pulado"', tmp_path, ensaio=True)
    assert not (tmp_path / "estado").exists()


def _o_vocabulario_que_o_install_anota() -> list[str]:
    import re

    fonte = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = fonte.index("_anotar_o_pulo_de_root() {")
    corpo = fonte[inicio:fonte.index("\n}\n", inicio)]
    return re.findall(r'\*"([^"]+)"\*', corpo)


def test_cada_pulo_por_sudo_do_install_cai_na_lista() -> None:
    """Toda porta de root do install (`! sudo -n true`) que pula o passo avisa com uma frase que
    o vocabulário de `_anotar_o_pulo_de_root` reconhece: o aviso se lê da porta, não da lista."""
    import re

    vocabulario = _o_vocabulario_que_o_install_anota()
    assert len(vocabulario) >= 4, vocabulario
    porta = re.compile(r"^\s*(if|elif)\s+!\s+(command -v sudo[^|]*\|\|\s+!\s+)?sudo -n true\b")
    portas: list[tuple[str, int, str]] = []
    for caminho in (RAIZ / "install.sh", *sorted((RAIZ / "scripts/lib").glob("*.sh"))):
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        for numero, linha in enumerate(linhas):
            if porta.search(linha):
                aviso = next((seguinte for seguinte in linhas[numero + 1:numero + 3]
                              if 'warn "' in seguinte), "")
                portas.append((caminho.name, numero + 1, aviso.strip()))
    assert len(portas) >= 20, "a régua perdeu as portas de root do install"
    fora = [p for p in portas if not any(frase in p[2] for frase in vocabulario)]
    assert fora == []


@pytest.mark.parametrize("aviso", [
    "sudo recusado — o modo desempenho pulado (re-execute ./install.sh --desempenho)",
    "sem root agora — a tabela de conectores da BIOS não foi lida (re-execute ./install.sh)",
])
def test_o_aviso_de_cada_porta_de_root_vira_pulo_gravado(tmp_path: Path, aviso: str) -> None:
    _o_install_de_verdade(f'warn "{aviso}"', tmp_path)
    assert _os_pulos(tmp_path).read_text(encoding="utf-8") == f"{aviso}\n"


@pytest.mark.skipif(os.geteuid() == 0, reason="o install de root sai antes de pedir sudo")
def test_o_askpass_do_sudo_conf_vale_sem_a_variavel(
    casa: Casa, tmp_path: Path,
) -> None:
    """Sem ``SUDO_ASKPASS`` no ambiente, o install tenta ``sudo -A -v`` (o askpass que o
    ``sudo.conf`` declara) antes de pedir a senha."""
    _sudo_de_mentira(casa, tmp_path / "bin", aceita="'-A -v'")
    fonte = (RAIZ / "install.sh").read_text(encoding="utf-8")
    inicio = fonte.index("acquire_sudo() {")
    fim = fonte.index("_cleanup_sudo_keepalive() {", inicio)
    roteiro = ("DRY_RUN=0\n_NEEDS_SUDO=1\n_start_sudo_keepalive() { echo KEEPALIVE; }\n"
               "warn() { echo \"AVISO $*\"; }\n"
               f"{fonte[inicio:fim]}\nacquire_sudo\n")
    ambiente = {"PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}"}
    feito = subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True,
                           timeout=20, check=True, stdin=subprocess.DEVNULL)
    assert feito.stdout.strip() == "KEEPALIVE", feito.stdout
    assert casa.chamadas_do_sudo() == ["-n true", "-A -v"]


def test_o_install_nunca_leva_sudo_na_frente_nem_recebe_senha(casa: Casa) -> None:
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    assert casa.rodadas() == ["--yes"]
    assert casa.chamadas_do_sudo() == []
    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/versao_ao_abrir.py").read_text(
        encoding="utf-8")
    assert '"-S"' not in fonte


def test_o_install_nao_herda_o_interpretador_da_janela(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/um/venv")
    monkeypatch.setenv("PATH", f"{casa.base / 'bin'}:/um/venv/bin:{os.environ['PATH']}")
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    virtual, _, caminho = casa.ambiente.read_text(encoding="utf-8").partition("|")
    assert virtual == ""
    assert "/um/venv/bin" not in caminho.split(":")


def test_a_saida_do_install_fica_no_registro_do_state(casa: Casa, tmp_path: Path) -> None:
    casa.anotar("a..b")
    _rodar_a_vigia(casa)
    registro = state_dir() / va.REGISTRO_DO_INSTALL
    assert "a saída do install" in registro.read_text(encoding="utf-8")
    assert state_dir().is_relative_to(tmp_path)


def test_a_faixa_nova_tenta_de_novo_e_o_motivo_velho_nao_fica(casa: Casa) -> None:
    casa.quebra.touch()
    assert _fechar_a_janela(casa, casa.avancar())
    assert "motivo:" in casa.nota.read_text(encoding="utf-8")
    casa.quebra.unlink()
    assert _fechar_a_janela(casa, casa.avancar("scripts/outro.sh"))
    assert casa.rodadas() == ["--yes", "--yes"]
    assert not casa.nota.exists()


def test_a_faixa_nova_que_nao_chegou_a_rodar_nao_fica_presa_no_motivo_velho(casa: Casa) -> None:
    casa.anotar("a..b", f"motivo: {va.SEM_AUTORIZACAO}")
    alvo = casa.avancar()
    assert va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo, disparar=lambda _i: None,
                      instalar=lambda _r: None)
    assert va.pendencia_do_install() is None
    assert "motivo:" not in casa.nota.read_text(encoding="utf-8")
    soltos: list[Path] = []
    assert va.retomar_o_install(casa.clone, instalar=soltos.append)
    assert soltos == [casa.clone]


def test_a_vigia_que_acha_o_motivo_velho_deixa_um_motivo_so(casa: Casa) -> None:
    casa.anotar("a..b", "motivo: o install saiu com o código 7")
    casa.quebra.touch()
    _rodar_a_vigia(casa)
    assert casa.nota.read_text(encoding="utf-8").splitlines() == [
        "a..b", "motivo: o install saiu com o código 7"]


def test_a_nota_vazia_nao_e_fila(casa: Casa) -> None:
    casa.nota.write_text("", encoding="utf-8")
    soltos: list[Path] = []
    assert not va.retomar_o_install(casa.clone, instalar=soltos.append)
    _rodar_a_vigia(casa)
    assert soltos == [] and casa.rodadas() == []


def test_o_install_do_fecho_repete_as_escolhas_do_ultimo_install(casa: Casa) -> None:
    casa.instalar_a_mao("--yes", "--keep-steam-input", "--no-systemd")
    assert _fechar_a_janela(casa, casa.avancar())
    assert casa.rodadas()[-1] == "--yes --format=native --keep-steam-input --no-systemd"
    assert _fechar_a_janela(casa, casa.avancar("scripts/outro.sh"))
    assert casa.rodadas()[-1] == casa.rodadas()[-2]


def test_o_install_que_quebra_nao_troca_as_escolhas(casa: Casa) -> None:
    casa.instalar_a_mao("--keep-steam-input")
    casa.quebra.touch()
    with pytest.raises(subprocess.CalledProcessError):
        casa.instalar_a_mao("--no-udev")
    casa.quebra.unlink()
    assert _fechar_a_janela(casa, casa.avancar())
    assert casa.rodadas()[-1] == "--yes --format=native --keep-steam-input"


def test_a_janela_que_voltou_nao_fecha_no_install_e_o_proximo_fecho_retoma(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.anotar("a..b")
    monkeypatch.setattr(recarga, "janelas_abertas", lambda: [4242])
    _rodar_a_vigia(casa)
    assert casa.rodadas() == []
    assert casa.nota.read_text(encoding="utf-8") == "a..b\n"
    monkeypatch.setattr(recarga, "janelas_abertas", list)
    soltos: list[Path] = []
    assert va.retomar_o_install(casa.clone, instalar=soltos.append)
    _rodar_a_vigia(casa)
    assert casa.rodadas() == ["--yes"]


def test_o_install_a_mao_em_curso_nao_ganha_um_segundo_nem_o_avanco_da_arvore(casa: Casa) -> None:
    casa.anotar("a..b")
    alvo = casa.avancar()
    processo = casa.install_a_mao_em_curso()
    try:
        _rodar_a_vigia(casa)
        assert casa.rodadas() == [""]
        assert not va.aplicar(casa.clone, alvo, jogo_aberto=_sem_jogo,
                              disparar=lambda _i: None, instalar=lambda _r: None)
        assert _git(casa.clone, "rev-parse", "HEAD") != alvo
    finally:
        os.killpg(processo.pid, signal.SIGKILL)
        processo.wait()
    casa.dorme.unlink()
    assert not va._install_de_fora()
    _rodar_a_vigia(casa)
    assert casa.rodadas() == ["", "--yes"]


def test_a_segunda_falha_guarda_as_duas_faixas_e_um_motivo_so(casa: Casa) -> None:
    casa.quebra.touch()
    assert _fechar_a_janela(casa, casa.avancar())
    assert _fechar_a_janela(casa, casa.avancar("scripts/outro.sh"))
    linhas = casa.nota.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 3
    assert [linha.startswith("motivo:") for linha in linhas] == [False, False, True]


def test_com_install_em_curso_a_janela_nao_avanca(casa: Casa) -> None:
    alvo = casa.avancar()
    topo = _git(casa.clone, "rev-parse", "HEAD")
    trava = va._a_trava_do_install()
    assert trava is not None
    try:
        assert not _fechar_a_janela(casa, alvo)
    finally:
        os.close(trava)
    assert _git(casa.clone, "rev-parse", "HEAD") == topo


def test_a_nota_sem_motivo_volta_no_fecho_da_janela(casa: Casa) -> None:
    casa.anotar("a..b")
    pedidos: list[Path] = []
    assert va.retomar_o_install(casa.clone, instalar=pedidos.append)
    assert pedidos == [casa.clone]


def test_a_nota_com_motivo_nao_volta_a_cada_fecho(casa: Casa) -> None:
    casa.anotar("a..b", "motivo: o install saiu com o código 7")
    pedidos: list[Path] = []
    assert not va.retomar_o_install(casa.clone, instalar=pedidos.append)
    assert pedidos == []


def test_sem_nota_ou_com_a_guarda_fechada_o_fecho_nao_solta_nada(casa: Casa) -> None:
    pedidos: list[Path] = []
    assert not va.retomar_o_install(casa.clone, instalar=pedidos.append)
    casa.anotar("a..b")
    (casa.clone / "README.md").write_text("trabalho\n", encoding="utf-8")
    assert not va.retomar_o_install(casa.clone, instalar=pedidos.append)
    assert pedidos == []


def _o_fim_da_janela(casa: Casa, monkeypatch: pytest.MonkeyPatch, alvo: str | None) -> list[str]:
    fins: list[Callable[[], None]] = []
    abertos: list[str] = []

    def _abrir(argv: Any, **_k: Any) -> None:
        abertos.append(argv[-1])

    monkeypatch.setattr(va.atexit, "register", fins.append)
    monkeypatch.setattr(va, "_a_suite_esta_rodando", lambda: False)
    monkeypatch.setattr(va, "baixar", lambda _r: alvo)
    monkeypatch.setattr(va, "_atualizacao_automatica", lambda: True)
    monkeypatch.setattr(troca, "_jogo_aberto", _sem_jogo)
    monkeypatch.setattr(fora, "abrir", _abrir)
    fio = va.baixar_ao_abrir(casa.clone)
    assert fio is not None
    fio.join(10)
    fins[0]()
    return abertos


def test_a_janela_que_fecha_sem_baixada_retoma_a_nota(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.anotar("a..b")
    assert _o_fim_da_janela(casa, monkeypatch, None) == [str(casa.clone)]


def test_a_janela_que_avanca_solta_o_install_uma_vez_so(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _o_fim_da_janela(casa, monkeypatch, casa.avancar()) == [str(casa.clone)]


class _Abriu:
    def __init__(self) -> None:
        self.linhas: list[list[str]] = []

    def __call__(self, cmd: Any, _env: Any) -> subprocess.CompletedProcess[str]:
        self.linhas.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.mark.parametrize("herdaria", [None, "dentro do serviço hefesto-gui.service"])
def test_o_install_nasce_numa_unidade_propria_mesmo_com_a_janela_num_escopo_da_pessoa(
    casa: Casa, monkeypatch: pytest.MonkeyPatch, herdaria: str | None,
) -> None:
    abriu = _Abriu()
    monkeypatch.setattr(
        fora, "contexto_atual",
        lambda: fora.Contexto(gerenciador=True, herdaria=herdaria, oom_do_gerenciador=None))

    def _abrir(argv: Any, **kw: Any) -> Any:
        return fora.abrir(argv, executar=abriu, **kw)

    va.soltar_o_install(casa.clone, abrir=_abrir)
    assert len(abriu.linhas) == 1
    linha = abriu.linhas[0]
    assert linha[0] == "systemd-run"
    assert any(a.startswith("--unit=app-hefesto-install_ao_fechar-") for a in linha)
    assert linha[linha.index("--") + 1:][1:] == [
        "-m", va.MODULO, va.PEDIDO_DO_INSTALL, str(casa.clone)]


def test_sem_gerenciador_o_install_nasce_em_sessao_propria(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidos: list[dict[str, Any]] = []

    def _popen(_argv: Any, **kw: Any) -> None:
        pedidos.append(kw)

    monkeypatch.setattr(
        fora, "contexto_atual",
        lambda: fora.Contexto(gerenciador=False, herdaria=None, oom_do_gerenciador=None))
    va.soltar_o_install(casa.clone, abrir=lambda argv, **kw: fora.abrir(argv, popen=_popen, **kw))
    assert [p["start_new_session"] for p in pedidos] == [True]


def test_a_suite_nunca_abre_o_install_de_verdade(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _explodir(*_a: Any, **_k: Any) -> None:
        raise AssertionError("a suíte abriu o install")

    monkeypatch.setattr(fora, "abrir", _explodir)
    va.soltar_o_install(casa.clone)


def test_a_linha_de_comando_da_vigia_chega_a_quem_espera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidos: list[Path] = []
    monkeypatch.setattr(va, "esperar_e_instalar", lambda raiz: pedidos.append(raiz) or 0)
    assert va.main([va.PEDIDO_DO_INSTALL, str(tmp_path)]) == 0
    assert pedidos == [tmp_path]
    assert va.main([]) == 2


def _doctor_so_com_o_install(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    impressos: list[str] = []

    async def _sem_daemon() -> list[tuple[str, str]]:
        return []

    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: None)
    monkeypatch.setattr(cmd_doctor, "_avisar_ausente", lambda *_a: None)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", _sem_daemon)
    for bloco in ("_print_storm_block", "_print_bloco_perfis", "_print_bloco_contratos",
                  "_print_bloco_proton_fixado", "_print_bloco_entrada"):
        monkeypatch.setattr(cmd_doctor, bloco, lambda: 0)
    monkeypatch.setattr(cmd_doctor.console, "print", lambda texto="", **_k: impressos.append(texto))
    return impressos


def test_o_doctor_diz_o_motivo_e_avisa(casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    casa.anotar("a..b", f"motivo: {va.SEM_AUTORIZACAO}")
    impressos = _doctor_so_com_o_install(monkeypatch)
    with pytest.raises(typer.Exit) as saida:
        cmd_doctor.doctor_cmd()
    assert saida.value.exit_code == 1
    assert any(va.SEM_AUTORIZACAO in linha for linha in impressos)


def test_o_doctor_calado_sem_motivo(casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    casa.anotar("a..b")
    impressos = _doctor_so_com_o_install(monkeypatch)
    with pytest.raises(typer.Exit) as saida:
        cmd_doctor.doctor_cmd()
    assert saida.value.exit_code == 0
    assert not any("versão nova" in linha for linha in impressos)


def _exame_so_com_o_install(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    monkeypatch.setattr(a09_sistema._exame, "storm_report", lambda **_k: [])
    monkeypatch.setattr(a09_sistema._exame, "controles_no_cabo", lambda _s: 0)
    monkeypatch.setattr(a09_sistema._daemon, "medir_guarda_do_steam_input", lambda: None)
    monkeypatch.setattr(a09_sistema, "_prontuario", lambda _p: None)
    monkeypatch.setattr(a09_sistema, "linha_do_som_do_sistema", lambda _s: None)
    monkeypatch.setattr(a09_sistema, "linha_da_sobreposicao_vulkan", lambda: None)
    monkeypatch.setattr(a09_sistema, "linhas_dos_perfis", lambda _p: [])
    linhas = a09_sistema._achados(None, False)
    assert linhas is not None
    return linhas


def test_a_aba_sistema_diz_o_motivo_no_tema_do_servico(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.anotar("a..b", f"motivo: {va.SEM_AUTORIZACAO}")
    linhas = _exame_so_com_o_install(monkeypatch)
    assert len(linhas) == 1
    selo, texto, tema = linhas[0]
    assert selo == "[WARN]" and tema == "serviço"
    assert va.SEM_AUTORIZACAO in texto


def test_a_linha_do_servico_diz_a_frase_curta_e_a_dica_o_motivo_e_o_gesto(
    casa: Casa, monkeypatch: pytest.MonkeyPatch,
) -> None:
    casa.anotar("a..b", f"motivo: {va.SEM_AUTORIZACAO}")
    exame = a09_sistema._tela.exame(_exame_so_com_o_install(monkeypatch))
    monkeypatch.setattr(a09_sistema, "linha_do_gamepad_por_jogador", lambda _s: {})
    linhas = a09_sistema._so_o_que_a_tela_mostra(exame, [], None)["linhas"]
    linha = next(a for a in linhas if a["tema"] == "serviço")
    assert linha["cls"] == "aviso"
    assert linha["txt"] == "A versão nova não terminou de entrar"
    assert va.SEM_AUTORIZACAO in linha["dica"] and "install" in linha["dica"]


def test_a_aba_sistema_calada_sem_motivo(casa: Casa, monkeypatch: pytest.MonkeyPatch) -> None:
    casa.anotar("a..b")
    assert _exame_so_com_o_install(monkeypatch) == []
