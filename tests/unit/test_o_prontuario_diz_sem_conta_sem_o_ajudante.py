"""O prontuário diz «sem conta» quando o jogo GDK recebe a peça e o ajudante de login falta.

A peça GDK (`assets/gdk-runtime/xgameruntime.c`) não fabrica token do Xbox Live: o login é do
ajudante que a pessoa instalou, e a peça o procura em `~/.local/share/dungeons2-compat/xauth.py`.
Sem ele o jogo abre e joga local, sem conta, amigos nem online. O dono do caminho é o fonte C
(compilado e pinado); o Python o segue, e uma régua lê o C.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
from hefesto_dualsense4unix.integrations import receitas_de_ambiente as rda

_RAIZ = Path(__file__).resolve().parents[2]
_FONTE_C = _RAIZ / "assets" / "gdk-runtime" / "xgameruntime.c"
_DLL = "xgameruntime.dll"
_PECA_DE_MENTIRA = b"MZ a peca de mentira do teste"


def _jogo(biblioteca: Path, appid: str, *, sinal: str | None = "MicrosoftGame.config") -> Path:
    """Um jogo de mentira no `steamapps` da biblioteca, com o sinal da família GDK."""
    apps = biblioteca / "steamapps"
    raiz = apps / "common" / f"Jogo{appid}"
    exe_dir = raiz / "Binaries" / "Win64"
    exe_dir.mkdir(parents=True)
    (exe_dir / "Jogo-Win64-Shipping.exe").write_bytes(b"MZ" + b"\0" * 64)
    (apps / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"Jogo {appid}"\n'
        f'\t"installdir"\t\t"Jogo{appid}"\n}}\n',
        encoding="utf-8",
    )
    if sinal:
        (raiz / sinal).write_text("<Game/>", encoding="utf-8")
    return raiz


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um HOME de mentira com a biblioteca Steam, a peça no sha do pino e SEM o ajudante."""
    lar = tmp_path / "casa"
    (lar / ".local" / "share" / "Steam" / "steamapps").mkdir(parents=True)
    assert not str(lar).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.delenv("WINE_HOST_HOME", raising=False)
    pino = tmp_path / "pino.txt"
    pino.write_text(f"sha256={hashlib.sha256(_PECA_DE_MENTIRA).hexdigest()}\n", encoding="utf-8")
    monkeypatch.setattr(rda, "PINO_DA_PECA", pino)
    dll = rda.pasta_da_peca(lar) / "x86_64-windows" / _DLL
    dll.parent.mkdir(parents=True)
    dll.write_bytes(_PECA_DE_MENTIRA)
    return lar


def _biblioteca(casa: Path) -> Path:
    return casa / ".local" / "share" / "Steam"


def _ficha(appid: str, *, examinar: bool = True) -> pdj.Prontuario:
    censo = pdj.levantar_censo(allowlist=[], pontes={}, examinar=examinar)
    (ficha,) = [j for j in censo.jogos if j.appid == appid]
    return ficha


def _chaves(ficha: pdj.Prontuario) -> list[str]:
    return [e.chave for e in ficha.estorvos]


def _por_o_ajudante(casa: Path) -> Path:
    alvo = rda.caminho_do_ajudante_de_login(casa)
    alvo.parent.mkdir(parents=True)
    alvo.write_text("# o ajudante de login da origem\n", encoding="utf-8")
    return alvo


# --- o prontuário ---------------------------------------------------------------------------


def test_o_jogo_gdk_com_a_peca_e_sem_o_ajudante_ganha_o_estorvo_sem_conta(casa: Path) -> None:
    # D-1710-O-JOGO-GDK-SEM-O-AJUDANTE-AVISA-QUE-ABRE-SEM-CONTA
    _jogo(_biblioteca(casa), "800001")
    ficha = _ficha("800001")
    assert pdj.SEM_CONTA in _chaves(ficha)
    estorvo = next(e for e in ficha.estorvos if e.chave == pdj.SEM_CONTA)
    assert ficha.sem_conta is True
    assert not estorvo.automatica
    assert pdj.FALTA_A_PECA not in _chaves(ficha), "a peça está no lugar: nada falta"


def test_o_texto_diz_o_que_acontece_e_a_saida_com_o_caminho_do_codigo(casa: Path) -> None:
    _jogo(_biblioteca(casa), "800002")
    estorvo = next(e for e in _ficha("800002").estorvos if e.chave == pdj.SEM_CONTA)
    onde = "/".join((*rda.PASTA_DO_AJUDANTE, rda.NOME_DO_AJUDANTE))
    for pedaco in ("sem conta", "amigos", "online", "só neste computador"):
        assert pedaco in estorvo.o_que, pedaco
    assert onde in estorvo.o_que, "o texto cita o caminho que a peça procura"
    assert "ajudante de login" in estorvo.a_cura and "não instala" in estorvo.a_cura
    assert "jogar local não precisa" in estorvo.a_cura


def test_com_o_ajudante_no_lugar_o_estorvo_some(casa: Path) -> None:
    _jogo(_biblioteca(casa), "800003")
    assert pdj.SEM_CONTA in _chaves(_ficha("800003"))
    _por_o_ajudante(casa)
    ficha = _ficha("800003")
    assert pdj.SEM_CONTA not in _chaves(ficha) and ficha.sem_conta is False


def test_jogo_que_nao_e_gdk_nunca_ganha_o_estorvo(casa: Path) -> None:
    _jogo(_biblioteca(casa), "800004", sinal=None)
    assert pdj.SEM_CONTA not in _chaves(_ficha("800004"))


def test_a_peca_faltando_diz_so_a_peca_e_nao_diz_sem_conta(casa: Path) -> None:
    (rda.pasta_da_peca(casa) / "x86_64-windows" / _DLL).unlink()
    _jogo(_biblioteca(casa), "800005")
    chaves = _chaves(_ficha("800005"))
    assert pdj.FALTA_A_PECA in chaves and pdj.SEM_CONTA not in chaves


def test_a_peca_fora_do_pino_tambem_nao_conta(casa: Path) -> None:
    (rda.pasta_da_peca(casa) / "x86_64-windows" / _DLL).write_bytes(b"MZ outra DLL")
    _jogo(_biblioteca(casa), "800006")
    assert pdj.SEM_CONTA not in _chaves(_ficha("800006"))


def test_o_kit_da_lovense_nao_recebe_a_peca_e_nao_ganha_o_estorvo(casa: Path) -> None:
    raiz = _jogo(_biblioteca(casa), "800007", sinal=None)
    dll = raiz / "Jogo_Data" / "Plugins" / "x86_64" / "LovenseWinrtBleDll.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"MZ")
    assert pdj.SEM_CONTA not in _chaves(_ficha("800007"))


def test_a_varredura_rapida_nao_examina_e_nao_diz(casa: Path) -> None:
    _jogo(_biblioteca(casa), "800008")
    assert pdj.SEM_CONTA not in _chaves(_ficha("800008", examinar=False))


def test_o_estorvo_vai_no_json_e_o_veredito_e_impedido(casa: Path) -> None:
    _jogo(_biblioteca(casa), "800009")
    ficha = _ficha("800009")
    dado = ficha.como_dicionario()
    assert dado["sem_conta"] is True
    assert pdj.SEM_CONTA in [e["chave"] for e in dado["estorvos"]]  # type: ignore[attr-defined]
    assert ficha.veredito == pdj.IMPEDIDO


# --- o caminho: o fonte C é o dono ----------------------------------------------------------


def _formatos_do_c() -> dict[str, str]:
    """Os formatos de `snprintf` e os `getenv` que `compat_paths` usa para achar o ajudante."""
    c = _FONTE_C.read_text(encoding="utf-8")
    inicio = c.index("static void compat_paths(void)")
    corpo = c[inicio : c.index("\n}\n", inicio)]
    pasta = re.search(r'snprintf\(g_compat_unix, sizeof g_compat_unix, "([^"]+)", home\)', corpo)
    ajudante = re.search(
        r'snprintf\(g_xauth_unix, sizeof g_xauth_unix, "([^"]+)", g_compat_unix\)', corpo
    )
    sem_home = re.search(r'snprintf\(homebuf, sizeof homebuf, "([^"]+)", user\)', corpo)
    ultimo = re.findall(r'user = "([^"]+)";', corpo)
    assert pasta and ajudante and sem_home and ultimo, "o fonte C mudou: releia compat_paths"
    return {
        "pasta": pasta.group(1),
        "ajudante": ajudante.group(1),
        "sem_home": sem_home.group(1),
        "ultimo_usuario": ultimo[-1],
        "ambiente": ",".join(re.findall(r'getenv\("(\w+)"\)', corpo)),
    }


def test_o_caminho_do_python_e_o_que_o_fonte_c_monta() -> None:
    c = _formatos_do_c()
    casa = "/casa/de/mentira"
    no_c = c["ajudante"] % (c["pasta"] % casa)
    assert str(rda.caminho_do_ajudante_de_login(Path(casa))) == no_c


def test_a_escada_da_casa_e_a_do_fonte_c(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _formatos_do_c()
    assert c["ambiente"] == "HOME,WINE_HOST_HOME,USER,LOGNAME", "a escada do C mudou"
    sem_home = c["sem_home"]
    for nome in ("HOME", "WINE_HOST_HOME", "USER", "LOGNAME"):
        monkeypatch.delenv(nome, raising=False)

    def onde(casa: str) -> str:
        return c["ajudante"] % (c["pasta"] % casa)

    monkeypatch.setenv("HOME", "/h/a")
    monkeypatch.setenv("WINE_HOST_HOME", "/h/b")
    assert str(rda.caminho_do_ajudante_de_login()) == onde("/h/a")
    monkeypatch.setenv("HOME", "relativa")  # só caminho absoluto vale
    assert str(rda.caminho_do_ajudante_de_login()) == onde("/h/b")
    monkeypatch.delenv("WINE_HOST_HOME")
    monkeypatch.setenv("USER", "fulana")
    assert str(rda.caminho_do_ajudante_de_login()) == onde(sem_home % "fulana")
    monkeypatch.delenv("USER")
    monkeypatch.setenv("LOGNAME", "sicrana")
    assert str(rda.caminho_do_ajudante_de_login()) == onde(sem_home % "sicrana")
    monkeypatch.delenv("LOGNAME")
    assert str(rda.caminho_do_ajudante_de_login()) == onde(sem_home % c["ultimo_usuario"])
