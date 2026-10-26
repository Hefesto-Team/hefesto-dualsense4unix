"""O jogo com o kit Bluetooth da Lovense abre no Proton: a DLL do kit se desliga pela pasta.

O WinRT de Bluetooth do Wine é parcial e a `LovenseWinrtBleDll.dll` não trata o erro dele: a exceção
C++ derruba o processo (Third Crisis: Neon Nights). Sem a DLL, a Unity registra o
`DllNotFoundException` e segue. A receita liga pelo caminho com curinga
`*_Data/Plugins/x86_64/LovenseWinrtBleDll.dll`, sem appid, e o valor `=d` (desligar) passa nos três
lugares que conferem a forma: a tabela, o espelho em Python e o wrapper.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env
from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
from hefesto_dualsense4unix.integrations import receitas_de_ambiente as rda
from tests.unit import test_o_jogo_que_pede_receita_de_ambiente as base

_ESPERADO = "LovenseWinrtBleDll=d"
_DLL = "LovenseWinrtBleDll.dll"


def _jogo_unity(
    biblioteca: Path,
    appid: str,
    *,
    produto: str = "Jogo Unity",
    com_a_dll: bool = True,
    onde: str = "Plugins/x86_64",
    sinal_da_pasta: str | None = None,
) -> Path:
    """Um jogo Unity de mentira: manifesto, executável na raiz e, se for o caso, a DLL do kit."""
    apps = biblioteca / "steamapps"
    raiz = apps / "common" / produto
    dados = raiz / (sinal_da_pasta or f"{produto}_Data")
    (dados / "Managed").mkdir(parents=True)
    (raiz / f"{produto}.exe").write_bytes(b"MZ" + b"\0" * 64)
    (dados / "Managed" / "LovenseRemote.dll").write_bytes(b"MZ")
    if com_a_dll:
        (dados / onde).mkdir(parents=True)
        (dados / onde / _DLL).write_bytes(b"MZ")
    (apps / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{produto}"\n'
        f'\t"installdir"\t\t"{produto}"\n}}\n',
        encoding="utf-8",
    )
    return raiz


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    biblioteca = casa / ".local" / "share" / "Steam"
    (biblioteca / "steamapps").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    return biblioteca


def test_a_tabela_traz_a_receita_do_kit_sem_appid_embarcado() -> None:
    (ble,) = [r for r in rda.carregar_tabela() if r.id == "lovense-ble-winrt"]
    assert ble.variavel == "WINEDLLOVERRIDES" and ble.valor == _ESPERADO
    assert ble.sinais == (f"*_Data/Plugins/x86_64/{_DLL}",)
    dados = [
        ln for ln in rda.TABELA.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    assert not [ln for ln in dados if re.search(r"\b\d{5,}\b", ln)], "appid embarcado na tabela"


def test_o_jogo_com_a_dll_do_kit_recebe_o_override_mesmo_com_o_nome_da_pasta_diferente(
    lar: Path,
) -> None:
    """Prova da D-1610-A-DLL-DO-KIT-DA-LOVENSE-SE-DESLIGA-PELA-PASTA."""
    raiz = _jogo_unity(lar, "710001", produto="Third Crisis Neon Nights")
    assert rda.ambiente_do_jogo(raiz) == {"WINEDLLOVERRIDES": _ESPERADO}
    assert rda.pecas_que_faltam(raiz) == (), "a DLL do sinal é a própria peça: nada falta"
    outro = _jogo_unity(lar, "710002", produto="Outro", sinal_da_pasta="NomeQueNaoEOProduto_Data")
    assert rda.ambiente_do_jogo(outro) == {"WINEDLLOVERRIDES": _ESPERADO}


def test_o_jogo_com_o_kit_sem_a_dll_ble_nao_recebe_nada_e_nao_acusa_falta(lar: Path) -> None:
    """O Third Crisis (1260820) traz o kit sem o BLE: a receita não é dele, e nada «falta»."""
    raiz = _jogo_unity(lar, "710003", com_a_dll=False)
    assert rda.ambiente_do_jogo(raiz) == {} and rda.pecas_que_faltam(raiz) == ()
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    (ficha,) = [j for j in censo.jogos if j.appid == "710003"]
    assert pdj.FALTA_A_PECA not in [e.chave for e in ficha.estorvos]


def test_a_dll_fora_do_caminho_do_plugin_nao_liga(lar: Path) -> None:
    raiz = _jogo_unity(lar, "710004", onde="Managed/x86_64")
    assert rda.ambiente_do_jogo(raiz) == {}
    fora = _jogo_unity(lar, "710005", produto="Solta", com_a_dll=False)
    (fora / _DLL).write_bytes(b"MZ")
    assert rda.ambiente_do_jogo(fora) == {}, "a DLL na raiz não é o caminho do kit"


def test_o_leitor_de_curinga_nao_sai_da_pasta_do_jogo(lar: Path, tmp_path: Path) -> None:
    raiz = _jogo_unity(lar, "710006", com_a_dll=False)
    vizinha = tmp_path / "casa" / ".local" / "share" / "Fora_Data" / "Plugins" / "x86_64"
    vizinha.mkdir(parents=True)
    (vizinha / _DLL).write_bytes(b"MZ")
    assert rda.achar_sinal(raiz, f"*_Data/Plugins/x86_64/{_DLL}") is None
    assert rda.achar_sinal(raiz, f"../*_Data/Plugins/x86_64/{_DLL}") is None


def test_a_linha_com_caminho_perigoso_ou_peca_com_barra_nao_entra(tmp_path: Path) -> None:
    csv = tmp_path / "t.csv"
    csv.write_text(
        "id,sinais,variavel,valor,peca\n"
        "ok,*_Data/Plugins/x86_64/A.dll,WINEDLLOVERRIDES,A=d,@sinal\n"
        "sobe,../A.dll,WINEDLLOVERRIDES,A=d,@sinal\n"
        "sobe-no-meio,X/../A.dll,WINEDLLOVERRIDES,A=d,@sinal\n"
        "absoluto,/etc/A.dll,WINEDLLOVERRIDES,A=d,@sinal\n"
        "desce-tudo,**/A.dll,WINEDLLOVERRIDES,A=d,@sinal\n"
        "peca-com-barra,A.dll,WINEDLLOVERRIDES,A=n,x/A.dll\n",
        encoding="utf-8",
    )
    assert [r.id for r in rda.carregar_tabela(csv)] == ["ok"]


def test_o_daemon_escreve_o_override_no_env_do_jogo_com_o_kit_e_so_dele(
    lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: pasta)
    _jogo_unity(lar, "710007", produto="Com Kit")
    _jogo_unity(lar, "710008", produto="Sem Dll", com_a_dll=False)
    materialize_launch_env(base._daemon_de_mentira())
    com = base._env(pasta / "steam_app_710007.env")
    assert com["WINEDLLOVERRIDES"] == _ESPERADO
    assert com["SDL_ACCELEROMETER_AS_JOYSTICK"] == "0", "a receita não pode tirar o resto"
    assert not (pasta / "steam_app_710008.env").exists(), "jogo sem a DLL ganhou arquivo"
    assert "WINEDLLOVERRIDES" not in base._env(pasta / "default.env")


def test_o_override_de_desligar_atravessa_o_arquivo_e_o_wrapper_ate_o_processo_do_jogo(
    tmp_path: Path,
) -> None:
    assert base._lancar(tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}"]) == _ESPERADO


@pytest.mark.parametrize(
    "valor",
    [
        "foo=d,b", "foo=dd", "foo=D", "foo=x", "foo=d,", "foo=,d", "=d", "foo=d=d", "$(id)=d",
        "foo=n,d",
    ],
)
def test_a_forma_de_desligar_fora_da_regra_continua_descartada(tmp_path: Path, valor: str) -> None:
    diario = tmp_path / "diario.txt"
    saida = base._lancar(tmp_path, [f"WINEDLLOVERRIDES={valor}"], com_logger=diario)
    assert saida == "ausente", f"«{valor}» passou pelo wrapper"
    assert "descartada" in diario.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "valor", ["foo=d", "foo,bar=d", "a=n;b=d", "x=d;y=n,b", "LovenseWinrtBleDll=d;"]
)
def test_as_formas_de_desligar_da_regra_passam(tmp_path: Path, valor: str) -> None:
    assert base._lancar(tmp_path, [f"WINEDLLOVERRIDES={valor}"]) == valor


def test_o_espelho_python_e_o_sh_dizem_o_mesmo_das_formas_com_d(tmp_path: Path) -> None:
    vetores = [
        "foo=d", "foo=D", "foo=d,b", "foo,bar=d", "a=n;b=d", "a=d;;b=d", "a=d;b", "=d", "foo=dd",
        "foo=n,d", "foo=d,", "LovenseWinrtBleDll=d",
    ]
    funcoes = base._funcoes_do_wrapper(tmp_path)
    for v in vetores:
        no_sh = subprocess.run(
            ["sh", "-c", '. "$1"; override_de_dll_valido "$2"', "x", str(funcoes), v],
            capture_output=True, text=True, timeout=10, check=False,
        ).returncode == 0
        no_py = rda.override_valido(v)
        assert no_sh == no_py, f"«{v}»: sh={no_sh}, python={no_py}"
