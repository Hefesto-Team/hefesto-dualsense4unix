"""A recusa de ler o teclado ou o pedal no «Esperar a próxima tecla» sai do dono da abertura.

A-08-DIZ-A-RECUSA-DE-LER-O-APARELHO-PELO-DONO-DA-FRASE-01: as duas recusas (a falta de permissão e o
aparelho que some ou não abre) têm a frase em ``utils/maquina.py``, e a 08 não escreve frase.

MORDIDAS: a frase do ``OSError`` de volta na 08 reprova o clique e a régua da 08; a abertura que
deixa o ``OSError`` cru sair do dono reprova o dono; a régua da tela que não confessa sem ler o dono
reprova a forma antiga.
"""

from __future__ import annotations

import ast
import errno
import importlib.util
import inspect
import shutil
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.utils import maquina
from tests.unit.test_os_acionadores_usb_entram_como_botoes import (
    CHAVE,
    _cena,
    _declarado,
    _sys_de_mentira,
    a08,
)

__all__ = ["a08"]

RAIZ = Path(__file__).resolve().parents[2]
REGUA = RAIZ / "scripts" / "check_a_tela_nao_confessa.py"
FONTE = RAIZ / "src" / "hefesto_dualsense4unix"

#: As duas recusas da abertura: o erro do sistema e o nome da frase no dono.
RECUSAS = (
    (PermissionError(errno.EACCES, "Permission denied"), "FRASE_SEM_PERMISSAO_DE_LER"),
    (FileNotFoundError(errno.ENOENT, "No such file or directory"), "FRASE_O_APARELHO_NAO_ABRE"),
    (OSError(errno.ENODEV, "No such device"), "FRASE_O_APARELHO_NAO_ABRE"),
)
IDS = ("sem-permissao", "o-no-sumiu", "o-aparelho-saiu")


def _frase(nome: str) -> str:
    frase = getattr(maquina, nome, None)
    assert isinstance(frase, str) and frase, f"`utils/maquina.py` não tem a frase {nome}"
    return frase


@pytest.fixture
def evdev_que_recusa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """O ``evdev.InputDevice`` que levanta o erro pedido, sem broker e sem ``/sys`` de verdade."""
    import evdev

    pedido: dict[str, OSError] = {}

    def abrir(caminho: str) -> Any:
        raise pedido["erro"]

    monkeypatch.setattr(evdev, "InputDevice", abrir)
    (tmp_path / "sem-sys").mkdir()
    monkeypatch.setattr(maquina, "RAIZ_DAS_ENTRADAS", str(tmp_path / "sem-sys"))
    monkeypatch.setattr(maquina, "_pedir_o_acionador_ao_broker", lambda no, chave: None)
    return pedido


# --- 1. o dono diz as duas recusas ------------------------------------------------------------
@pytest.mark.parametrize(("erro", "nome"), RECUSAS, ids=IDS)
def test_o_dono_da_abertura_levanta_a_recusa_com_a_frase_dela(
        evdev_que_recusa: Any, erro: OSError, nome: str) -> None:
    evdev_que_recusa["erro"] = erro
    with pytest.raises(OSError) as recusa:
        maquina.abrir_o_aparelho_de_entrada("event7")
    assert str(recusa.value) == _frase(nome)
    assert isinstance(recusa.value, PermissionError) is isinstance(erro, PermissionError), (
        "a recusa do dono mudou de família: o doctor e a ponte separam a permissão por ela")


# --- 2. o clique da 08 diz a frase do dono ----------------------------------------------------
@pytest.mark.parametrize(("erro", "nome"), RECUSAS, ids=IDS)
@pytest.mark.parametrize("abertura", ["pelo-dono", "crua"])
def test_o_clique_diz_a_recusa_do_dono_e_nao_fica_esperando(
        a08: Any, evdev_que_recusa: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        erro: OSError, nome: str, abertura: str) -> None:
    """Pelo dono ou com a abertura crua (o erro do sistema sem frase), o clique diz a do dono."""
    _cena(a08, monkeypatch, _declarado())
    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(_sys_de_mentira(tmp_path / "input")))
    evdev_que_recusa["erro"] = erro
    if abertura == "crua":
        def crua(evento: str) -> Any:
            raise erro

        monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", crua)
    else:
        monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", None)
    a08.usar_como_botoes(None, {"alvo": CHAVE}, None)
    with pytest.raises(RuntimeError) as recusa:
        a08.acionador_nova_tecla(None, {}, None)
    assert str(recusa.value) == _frase(nome)
    assert not a08._RASCUNHO.esperando


def test_nenhuma_frase_da_recusa_de_ler_mora_na_08() -> None:
    """As recusas da abertura no «Esperar a próxima tecla» não levam texto escrito na 08."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    fonte = inspect.getsource(a08_conexoes.acionador_nova_tecla)
    arvore = ast.parse(fonte)
    tratadores = [h for n in ast.walk(arvore) if isinstance(n, ast.Try) for h in n.handlers]
    assert tratadores, "a abertura do nó saiu do clique"
    escritas = [ast.get_source_segment(fonte, c) for h in tratadores for c in ast.walk(h)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)]
    assert escritas == [], f"a 08 escreve a frase da recusa: {escritas}"


# --- 3. a régua da tela que não confessa lê o dono --------------------------------------------
def _a_regua() -> Any:
    spec = importlib.util.spec_from_file_location("_regua_da_confissao_p1fio", REGUA)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _recado_da_08(tmp_path: Path, trocar: tuple[str, str] | None = None) -> tuple[Any, str]:
    """A régua sobre a 08 e o dono copiados, com uma frase do dono reescrita se pedido."""
    regua = _a_regua()
    raiz = tmp_path / "arvore"
    pacotes = raiz / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes"
    utils = raiz / "src" / "hefesto_dualsense4unix" / "utils"
    pacotes.mkdir(parents=True)
    utils.mkdir(parents=True)
    shutil.copy(FONTE / "interface" / "pacotes" / "a08_conexoes.py", pacotes)
    texto = (FONTE / "utils" / "maquina.py").read_text(encoding="utf-8")
    if trocar is not None:
        nome, nova = trocar
        arvore = ast.parse(texto)
        no = next(n for n in arvore.body if isinstance(n, ast.AnnAssign)
                  and isinstance(n.target, ast.Name) and n.target.id == nome)
        assert no.value is not None
        linhas = texto.splitlines(keepends=True)
        antes = "".join(linhas[:no.lineno - 1])
        depois = "".join(linhas[no.end_lineno:])
        texto = f"{antes}{nome}: Final = {nova!r}\n{depois}"
    (utils / "maquina.py").write_text(texto, encoding="utf-8")
    regua.RAIZ = raiz
    regua.FONTE = raiz / "src"
    regua.PACOTES = pacotes
    lidos, _mudos = regua._recados()
    fonte = (pacotes / "a08_conexoes.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.FunctionDef)
              and n.name == "acionador_nova_tecla")
    linhas_do_clique = {f"src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:{n.lineno}"
                        for n in ast.walk(fn) if isinstance(n, ast.Raise)}
    recados = " ".join(t for onde, t in lidos if onde in linhas_do_clique)
    return regua, recados


def test_a_regua_le_as_duas_frases_do_dono_no_clique(tmp_path: Path) -> None:
    _regua, recados = _recado_da_08(tmp_path)
    for nome in ("FRASE_SEM_PERMISSAO_DE_LER", "FRASE_O_APARELHO_NAO_ABRE"):
        assert _frase(nome) in recados, f"a régua não alcança {nome} pelo clique da 08"


@pytest.mark.parametrize("nome", ["FRASE_SEM_PERMISSAO_DE_LER", "FRASE_O_APARELHO_NAO_ABRE"])
def test_a_regua_reprova_a_frase_do_dono_na_forma_antiga(tmp_path: Path, nome: str) -> None:
    """A forma que a régua já reprovou na leva («o Hefesto não conseguiu abrir»), posta no dono."""
    antiga = "o Hefesto não conseguiu abrir este aparelho pelo serviço dele"
    regua, recados = _recado_da_08(tmp_path, (nome, antiga))
    assert antiga in recados, f"a régua não leu {nome} reescrita"
    declaradas = {**regua.FATOS, **regua.A_DIVIDA}
    soltas = [t for t in regua._forma(recados)
              if not any(k.lower() in t.lower() for k in declaradas)]
    assert soltas, f"a régua deixou passar {nome} na forma antiga"


def test_a_frase_do_aparelho_que_nao_abre_nao_manda_ao_grupo_input() -> None:
    frase = _frase("FRASE_O_APARELHO_NAO_ABRE")
    assert "input" not in frase and "usermod" not in frase
    assert "Hefesto" not in frase, "o sujeito é o aparelho, não o Hefesto"
