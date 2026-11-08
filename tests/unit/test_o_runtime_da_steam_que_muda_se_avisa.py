"""O runtime da Steam que muda por baixo do Proton se avisa (contrato `runtime-do-proton`).

O-RUNTIME-DA-STEAM-QUE-MUDA-POR-BAIXO-DO-PROTON-SE-AVISA-01. O GE pede o Steam Linux Runtime pelo
`require_tool_appid` do `toolmanifest.vdf`, e a Steam troca o runtime sozinha. A sonda lê o
`buildid` do runtime em toda biblioteca e o compara com o `runtime` da linha «passou» do recibo.
Uma Steam de mentira em `tmp_path`, nas três raízes: nada do disco de verdade é lido.

A MORDIDA: comparar só o appid do runtime (e não o buildid) faz o caso «diferente» passar, e
`test_o_buildid_diferente_avisa_com_os_dois_numeros` reprova.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf

RAIZES = (".steam/steam", ".local/share/Steam", ".var/app/com.valvesoftware.Steam/.steam/steam")
GE = "GE-Proton11-12-x86_64"
APPID = "4183110"


def _casa(home: Path, raiz: str, *, buildid: str | None) -> cf.Ambiente:
    steam = home / raiz
    pasta = steam / "compatibilitytools.d" / GE
    pasta.mkdir(parents=True)
    (pasta / "toolmanifest.vdf").write_text(
        f'"manifest"\n{{\n  "commandline" "/proton %verb%"\n  "require_tool_appid" "{APPID}"\n}}\n',
        encoding="utf-8",
    )
    (steam / "steamapps").mkdir()
    if buildid is not None:
        (steam / "steamapps" / f"appmanifest_{APPID}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{APPID}"\n\t"buildid"\t\t"{buildid}"\n}}\n',
            encoding="utf-8",
        )
    return cf.Ambiente(home=home, env={})


def _recibo(monkeypatch: pytest.MonkeyPatch, runtime: str, veredito: str = "passou") -> None:
    linha = {"versão": GE, "veredito": veredito, "runtime": runtime}
    monkeypatch.setattr(cf, "_o_recibo_do_proton", lambda: [linha])


def _linha(amb: cf.Ambiente) -> tuple[str, str]:
    contrato = next(c for c in cf.CONTRATOS if c.id == "runtime-do-proton")
    ((tag, mensagem),) = cf.linhas_do_doctor(amb, [contrato])
    return tag, mensagem


@pytest.mark.parametrize("raiz", RAIZES)
def test_o_buildid_igual_ao_recibo_cala(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raiz: str
) -> None:
    _recibo(monkeypatch, "26116036")
    assert _linha(_casa(tmp_path, raiz, buildid="26116036"))[0] == "[ OK ]"


@pytest.mark.parametrize("raiz", RAIZES)
def test_o_buildid_diferente_avisa_com_os_dois_numeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raiz: str
) -> None:
    """D-0811-O-RUNTIME-DA-STEAM-SE-COMPARA-COM-O-RECIBO."""
    _recibo(monkeypatch, "26116036")
    tag, mensagem = _linha(_casa(tmp_path, raiz, buildid="26300001"))
    assert tag == "[WARN]", mensagem
    assert "o runtime da Steam mudou depois da prova do Proton fixado" in mensagem
    assert "26116036" in mensagem and "26300001" in mensagem


@pytest.mark.parametrize("raiz", RAIZES)
def test_sem_o_manifesto_do_runtime_e_ausente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raiz: str
) -> None:
    _recibo(monkeypatch, "26116036")
    tag, mensagem = _linha(_casa(tmp_path, raiz, buildid=None))
    assert tag == "[INFO]" and "biblioteca nenhuma" in mensagem, mensagem


def test_a_linha_que_nao_passou_nao_e_prova(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _recibo(monkeypatch, "26116036", veredito="não medida")
    tag, mensagem = _linha(_casa(tmp_path, RAIZES[0], buildid="26300001"))
    assert tag == "[INFO]" and "não tem a rodada" in mensagem, mensagem


def test_sem_steam_e_informacao(tmp_path: Path) -> None:
    assert _linha(cf.Ambiente(home=tmp_path / "ninguem", env={}))[0] == "[INFO]"


def test_o_recibo_vem_do_dono() -> None:
    linhas = cf._o_recibo_do_proton()
    assert linhas and all("runtime" in linha for linha in linhas)
