"""A escolha da tela se faz uma vez e fica (11/11/2026).

Medido: a captura apagava a ficha guardada do portal em três casos que não são a pessoa recusando
(o prazo esgotado, o ``RuntimeError`` do portal e o cancelamento), e o portal reiniciado de fora
da sessão fazia a escolha voltar a cada abertura. Só o cancelamento da pessoa (o código 1 do
``Response``) apaga a ficha; o prazo esgotado guarda a ficha e não vira laço de janelas; a queda do
portal guarda a ficha e tenta de novo depois da ``espera``. A escolha nasce no passo do install,
que aqui roda com o ``python`` e o portal de mentira: nenhuma prova abre a janela do portal.

MORDIDA: devolver o ``_esquecer`` ao braço do prazo ou ao do ``RuntimeError`` do ``abrir``, ou
arrancar a guarda do passo do install (a sessão gráfica, o COSMIC ou o ensaio), e a régua reprova.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from tests.unit.test_a_captura_nao_acorda_o_portal_antes_da_sessao import (
    _PRECISA_DO_PORTAL,
    Barramento,
    Cena,
    PortalDeTeste,
    barramento,  # noqa: F401
)

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _sessao_do_cosmic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "COSMIC")


def _escolhas(portal: PortalDeTeste) -> list[dict[str, object]]:
    return [o for m, o in portal.levados if m == "SelectSources"]


@_PRECISA_DO_PORTAL
def test_o_prazo_esgotado_guarda_a_ficha_e_nao_vira_laco(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setattr(tj, "PRAZO_DA_ESCOLHA_S", 0.2)
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-velha", encoding="utf-8")
    portal = PortalDeTeste(barramento.endereco, respostas={"Start": None})
    try:
        cena = Cena(tj.FonteDoPortal(ficha))
        cena.correr(10.0)
        assert len(_escolhas(portal)) == 1, portal.pedidos
        assert ficha.read_text(encoding="utf-8") == "ficha-velha"
        assert len(cena.publicados) == 1
        cena.fica(2)
        cena.correr(1.0)
        escolhas = _escolhas(portal)
        assert len(escolhas) == 2, portal.pedidos
        assert all(e["restore_token"] == ("s", "ficha-velha") for e in escolhas)
    finally:
        portal.fechar()


@_PRECISA_DO_PORTAL
@pytest.mark.parametrize("queda", ["dois", "sem_fluxo", "erro"])
def test_a_queda_do_portal_guarda_a_ficha_e_tenta_de_novo_pela_espera(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, queda: str  # noqa: F811
) -> None:
    monkeypatch.setattr(tj, "PRAZO_DA_ESCOLHA_S", 0.2)
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-velha", encoding="utf-8")
    jeitos: dict[str, dict[str, object]] = {
        "dois": {"respostas": {"Start": 2}},
        "sem_fluxo": {"sem_fluxo": True},
        "erro": {"erro_em": frozenset({"Start"})},
    }
    portal = PortalDeTeste(barramento.endereco, **jeitos[queda])  # type: ignore[arg-type]
    try:
        cena = Cena(tj.FonteDoPortal(ficha))
        cena.correr(10.0)
        escolhas = _escolhas(portal)
        assert len(escolhas) >= 4, portal.pedidos
        assert all(e["restore_token"] == ("s", "ficha-velha") for e in escolhas)
        assert ficha.read_text(encoding="utf-8") == "ficha-velha"
        assert len(cena.publicados) == 1
    finally:
        portal.fechar()


@_PRECISA_DO_PORTAL
def test_o_portal_que_volta_reabre_com_a_ficha_guardada(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setattr(tj, "PRAZO_DA_ESCOLHA_S", 0.2)
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    cena = Cena(tj.FonteDoPortal(ficha))
    cena.correr(6.0)
    assert ficha.read_text(encoding="utf-8") == "ficha-boa"
    portal = PortalDeTeste(barramento.endereco, sem_fluxo=True)
    try:
        cena.correr(6.0)
        escolhas = _escolhas(portal)
        assert escolhas, portal.pedidos
        assert escolhas[0]["restore_token"] == ("s", "ficha-boa")
    finally:
        portal.fechar()


class _Fonte:
    """Uma fonte de mentira para o passo do install: cada ``abrir`` faz o próximo da fila."""

    def __init__(self, *jeitos: bool | BaseException) -> None:
        self.jeitos = list(jeitos)
        self.fechadas = 0

    def abrir(self) -> bool:
        jeito = self.jeitos.pop(0)
        if isinstance(jeito, BaseException):
            raise jeito
        return jeito

    def quadro(self) -> tj.Quadro | None:
        return None

    def fechar(self) -> None:
        self.fechadas += 1

    def interromper(self) -> None:
        return None


def _escolher(fonte: _Fonte) -> tuple[int, list[float]]:
    pausas: list[float] = []
    return tj.escolher_a_tela(fonte, dormir=pausas.append), pausas


def test_o_passo_do_install_sai_com_zero_quando_a_escolha_ficou(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fonte = _Fonte(True)
    assert _escolher(fonte) == (0, [])
    assert fonte.fechadas == 1
    assert "guardada" in capsys.readouterr().out


def test_o_passo_do_install_sai_com_tres_quando_a_pessoa_cancela() -> None:
    fonte = _Fonte(tj.EscolhaCanceladaError("a pessoa cancelou"))
    assert _escolher(fonte) == (3, [])


def test_o_passo_do_install_sai_com_tres_quando_a_janela_fica_sem_resposta() -> None:
    fonte = _Fonte(tj.EscolhaSemRespostaError("sem resposta"))
    assert _escolher(fonte) == (3, [])


def test_o_portal_que_acaba_de_reiniciar_tem_tres_chances_e_depois_fica_para_o_jogo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fonte = _Fonte(RuntimeError("sem a interface"), RuntimeError("sem a interface"),
                   RuntimeError("sem a interface"))
    codigo, pausas = _escolher(fonte)
    assert codigo == 2
    assert len(pausas) == 2
    assert "primeiro jogo" in capsys.readouterr().out


def test_o_portal_que_responde_na_segunda_chance_guarda_a_escolha() -> None:
    fonte = _Fonte(RuntimeError("subindo"), True)
    assert _escolher(fonte) == (0, [3.0])


def test_sem_o_pipewiresrc_a_escolha_fica_para_o_primeiro_jogo() -> None:
    assert _escolher(_Fonte(False)) == (2, [])


@_PRECISA_DO_PORTAL
def test_a_escolha_do_install_deixa_a_ficha_no_disco_e_o_cancelamento_a_apaga(
    barramento: Barramento, tmp_path: Path  # noqa: F811
) -> None:
    portal = PortalDeTeste(barramento.endereco)
    ficha = tmp_path / "ficha"
    try:
        tj.escolher_a_tela(tj.FonteDoPortal(ficha), tentativas=1)
        assert ficha.read_text(encoding="utf-8") == "ficha-nova"
    finally:
        portal.fechar()
    portal = PortalDeTeste(barramento.endereco, respostas={"Start": 1})
    try:
        assert tj.escolher_a_tela(tj.FonteDoPortal(ficha), tentativas=1) == 3
        assert not ficha.exists()
    finally:
        portal.fechar()


def _funcao_do_install(nome: str) -> str:
    achada = re.search(rf"^{re.escape(nome)}\(\) \{{\n", INSTALL, re.MULTILINE)
    assert achada is not None, f"{nome}() não está no install.sh"
    fim = re.search(r"^\}\n", INSTALL[achada.end():], re.MULTILINE)
    assert fim is not None
    return INSTALL[achada.start():achada.end() + fim.end()]


def _rodar_o_passo(
    tmp_path: Path, *, cosmic: int, wayland: str, dry_run: int, saida_do_python: int = 0
) -> tuple[str, str]:
    """O passo real do install, com o ``python`` do ambiente e o ``timeout`` trocados por
    dublês: devolve o que ele escreveu e o que o dublê registrou."""
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    registro = tmp_path / "registro"
    python = venv / "bin" / "python"
    python.write_text(
        f'#!/bin/sh\necho "python $*" >> "{registro}"\n'
        f'echo "a escolha da tela está guardada"\nexit {saida_do_python}\n', encoding="utf-8")
    python.chmod(0o755)
    script = (
        "set -euo pipefail\n"
        f'VENV_DIR="{venv}"\nDESKTOP_IS_COSMIC={cosmic}\nDRY_RUN={dry_run}\n'
        f'export WAYLAND_DISPLAY="{wayland}"\n'
        'timeout() { shift; "$@"; }\n'
        f'_faria() {{ echo "faria: $1" >> "{registro}"; }}\n'
        f'warn() {{ echo "aviso: $1" >> "{registro}"; }}\n'
        f'{_funcao_do_install("escolher_a_tela_do_jogo")}\n'
        "escolher_a_tela_do_jogo\n"
    )
    resultado = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=15,
                               env={"PATH": "/usr/bin:/bin"})
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout, registro.read_text(encoding="utf-8") if registro.exists() else ""


def test_na_sessao_do_cosmic_o_install_roda_a_escolha_uma_vez(tmp_path: Path) -> None:
    _saida, registro = _rodar_o_passo(tmp_path, cosmic=1, wayland="wayland-1", dry_run=0)
    assert registro.count("python -c") == 1
    assert "escolher_a_tela" in registro
    assert "aviso" not in registro


def test_o_ensaio_diz_o_que_faria_e_nao_roda_o_python(tmp_path: Path) -> None:
    _saida, registro = _rodar_o_passo(tmp_path, cosmic=1, wayland="wayland-1", dry_run=1)
    assert registro.startswith("faria: ")
    assert "python -c" not in registro


def test_sem_sessao_grafica_o_install_nao_roda_o_python_e_diz_que_fica_para_o_jogo(
    tmp_path: Path,
) -> None:
    saida, registro = _rodar_o_passo(tmp_path, cosmic=1, wayland="", dry_run=0)
    assert registro == ""
    assert "primeiro jogo" in saida


def test_fora_do_cosmic_o_install_nao_roda_o_python(tmp_path: Path) -> None:
    saida, registro = _rodar_o_passo(tmp_path, cosmic=0, wayland="wayland-1", dry_run=0)
    assert registro == "" and saida == ""


@pytest.mark.parametrize(("saida_do_python", "avisa"), [(0, False), (2, False), (3, True)])
def test_a_escolha_que_nao_ficou_vira_aviso_e_a_que_fica_para_o_jogo_nao(
    tmp_path: Path, saida_do_python: int, avisa: bool
) -> None:
    _saida, registro = _rodar_o_passo(tmp_path, cosmic=1, wayland="wayland-1", dry_run=0,
                                      saida_do_python=saida_do_python)
    assert ("aviso: " in registro) is avisa


def test_o_passo_entra_depois_do_portal_da_casa_e_so_no_cosmic() -> None:
    portal = INSTALL.index('step "3f-ter"')
    passo = INSTALL.index('step "3f-quater"')
    assert portal < passo < INSTALL.index('step "3g"')
    guarda = INSTALL[INSTALL.rindex("\nif ", 0, passo):passo]
    assert 'DESKTOP_IS_COSMIC}" -eq 1' in guarda
