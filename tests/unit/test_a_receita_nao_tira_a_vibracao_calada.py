"""A receita não tira a vibração do jogo GDK calada quando o pino do GameInput anda.

O pino guarda, em `gameinput_sha256_anteriores`, os sha que a casa já pinou e que ainda servem.
O `gameinput.dll` de `nativa/` num desses sha é a peça de antes, posta por um install: a receita
`gameinput=n,b` segue no ambiente do jogo até o install pôr a do pino. Um sha estranho ou o arquivo
ausente tiram a receita, como antes. A receita é do processo do jogo, igual para os quatro
jogadores, cabo e rádio.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import receitas_de_ambiente as rda
from tests.unit.test_o_jogo_gdk_vibra_pelo_gameinput import _PAR, _TRIO, _jogo, _por

_PINO_DA_CASA = Path(__file__).resolve().parents[2] / "assets" / "gdk-runtime" / "pino.txt"
_XGR = b"MZ a xgameruntime de mentira"
_GI_NOVO = b"MZ o gameinput de mentira do pino"
_GI_ANTES = b"MZ o gameinput de mentira de antes"


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Biblioteca Steam num HOME de mentira, a xgameruntime no lugar e um pino de mentira que pina
    o GameInput novo e aceita o de antes."""
    casa = tmp_path / "casa"
    biblioteca = casa / ".local" / "share" / "Steam"
    (biblioteca / "steamapps").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    pino = tmp_path / "pino.txt"
    pino.write_text(
        f"sha256={_sha(_XGR)}\n"
        f"gameinput_sha256={_sha(_GI_NOVO)}\n"
        f"gameinput_sha256_anteriores={'0' * 64} {_sha(_GI_ANTES)}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rda, "PINO_DA_PECA", pino)
    _por(casa, "x86_64-windows/xgameruntime.dll", _XGR)
    return biblioteca


def _casa(biblioteca: Path) -> Path:
    return biblioteca.parents[2]


def test_o_gameinput_do_pino_leva_a_receita(lar: Path) -> None:
    _por(_casa(lar), "nativa/gameinput.dll", _GI_NOVO)
    raiz = _jogo(lar, "720001")
    assert rda.ambiente_do_jogo(raiz) == _TRIO
    assert rda.gameinput_do_hefesto_instalado() and not rda.gameinput_do_hefesto_de_antes()


def test_o_gameinput_de_antes_segue_com_a_receita(lar: Path) -> None:
    """O pino andou e o install não pôs a DLL nova: a de antes segue vibrando."""
    _por(_casa(lar), "nativa/gameinput.dll", _GI_ANTES)
    raiz = _jogo(lar, "720002")
    assert rda.ambiente_do_jogo(raiz) == _TRIO, "a DLL de antes tira a vibração calada"
    assert rda.pecas_que_faltam(raiz) == ()
    assert rda.gameinput_do_hefesto_de_antes() and not rda.gameinput_do_hefesto_instalado()


@pytest.mark.parametrize("como", ["ausente", "estranho", "pino-sem-a-lista"])
def test_o_gameinput_estranho_ou_ausente_tira_a_receita(lar: Path, como: str) -> None:
    dll = rda.pasta_da_peca(_casa(lar)) / "nativa" / "gameinput.dll"
    if como == "estranho":
        _por(_casa(lar), "nativa/gameinput.dll", b"MZ um gameinput de outra origem")
    elif como == "pino-sem-a-lista":
        _por(_casa(lar), "nativa/gameinput.dll", _GI_ANTES)
        rda.PINO_DA_PECA.write_text(
            f"sha256={_sha(_XGR)}\ngameinput_sha256={_sha(_GI_NOVO)}\n", encoding="utf-8"
        )
    assert como != "ausente" or not dll.exists()
    raiz = _jogo(lar, "720003")
    assert rda.ambiente_do_jogo(raiz) == _PAR
    assert not rda.gameinput_do_hefesto_de_antes()


def test_o_gameinput_de_antes_sem_a_peca_gdk_nao_entra(lar: Path) -> None:
    """Sem a xgameruntime ninguém carrega o `gameinput.dll`, novo ou de antes."""
    _por(_casa(lar), "nativa/gameinput.dll", _GI_ANTES)
    (rda.pasta_da_peca(_casa(lar)) / "x86_64-windows" / "xgameruntime.dll").unlink()
    assert rda.ambiente_do_jogo(_jogo(lar, "720004")) == {}


def test_a_lista_de_antes_do_pino_da_casa_e_bem_formada() -> None:
    """Cada sha de antes tem 64 dígitos hex e nenhum é o sha de hoje."""
    linhas = dict(
        ln.split("=", 1) for ln in _PINO_DA_CASA.read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#") and "=" in ln
    )
    anteriores = linhas["gameinput_sha256_anteriores"].split()
    assert anteriores, "o pino perdeu a lista dos GameInput de antes"
    assert rda._shas_anteriores_do_pino(_PINO_DA_CASA, "gameinput_sha256") == set(anteriores)
    assert linhas["gameinput_sha256"] not in anteriores
