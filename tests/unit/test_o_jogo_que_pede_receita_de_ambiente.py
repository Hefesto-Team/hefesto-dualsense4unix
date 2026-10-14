"""O jogo que só abre com uma receita de ambiente a recebe pelo wrapper, ele e a família."""
from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST, materialize_launch_env
from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
from hefesto_dualsense4unix.integrations import receitas_de_ambiente as rda

_RAIZ = Path(__file__).resolve().parents[2]
_WRAPPER = _RAIZ / "assets" / "hefesto-launch.sh"
_DLL = "xgameruntime.dll"
_ESPERADO = "xgameruntime=n"


def _jogo(
    biblioteca: Path,
    appid: str,
    *,
    sinal: str | None = "MicrosoftGame.config",
    dll_ao_lado_do_exe: bool = True,
    dll_so_na_raiz: bool = False,
) -> Path:
    """Um jogo de mentira no `steamapps` da biblioteca: manifesto, pasta, executável e peça."""
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
    if dll_ao_lado_do_exe:
        (exe_dir / _DLL).write_bytes(b"MZ")
    if dll_so_na_raiz:
        (raiz / _DLL).write_bytes(b"MZ")
    return raiz


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    biblioteca = casa / ".local" / "share" / "Steam"
    (biblioteca / "steamapps").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    return biblioteca


# --- a tabela -------------------------------------------------------------------------------


def test_a_tabela_traz_a_familia_gdk_sem_appid_embarcado() -> None:
    (gdk,) = [r for r in rda.carregar_tabela() if r.id == "gdk-xgameruntime"]
    assert gdk.variavel == "WINEDLLOVERRIDES" and gdk.valor == _ESPERADO and gdk.peca == _DLL
    assert "MicrosoftGame.config" in gdk.sinais
    dados = [
        ln for ln in rda.TABELA.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    assert not [ln for ln in dados if re.search(r"\b\d{5,}\b", ln)], "appid embarcado na tabela"


def test_a_linha_fora_da_regra_nao_entra(tmp_path: Path) -> None:
    csv = tmp_path / "t.csv"
    csv.write_text(
        "id,sinais,variavel,valor,peca\n"
        "ok,A.cfg,WINEDLLOVERRIDES,foo=n,foo.dll\n"
        "var-fora,A.cfg,LD_PRELOAD,foo=n,foo.dll\n"
        "forma-fora,A.cfg,WINEDLLOVERRIDES,foo=b,foo.dll\n"
        "sinal-fora,../A.cfg,WINEDLLOVERRIDES,foo=n,foo.dll\n"
        "sem-peca,A.cfg,WINEDLLOVERRIDES,foo=n,\n",
        encoding="utf-8",
    )
    assert [r.id for r in rda.carregar_tabela(csv)] == ["ok"]
    assert rda.carregar_tabela(tmp_path / "nao-existe.csv") == ()


# --- o disco do jogo ------------------------------------------------------------------------


def test_o_jogo_com_o_sinal_e_a_peca_recebe_a_receita(lar: Path) -> None:
    raiz = _jogo(lar, "700001")
    assert rda.ambiente_do_jogo(raiz) == {"WINEDLLOVERRIDES": _ESPERADO}
    assert rda.pecas_que_faltam(raiz) == ()


def test_o_outro_sinal_da_familia_tambem_liga(lar: Path) -> None:
    raiz = _jogo(lar, "700002", sinal="installscript-gamingrepair.vdf")
    assert rda.ambiente_do_jogo(raiz) == {"WINEDLLOVERRIDES": _ESPERADO}


def test_sem_a_peca_a_receita_nao_sai_e_o_prontuario_diz_falta(lar: Path) -> None:
    """Sem a DLL o override quebraria o jogo: nada é passado, e a peça é nomeada."""
    raiz = _jogo(lar, "700003", dll_ao_lado_do_exe=False)
    assert rda.ambiente_do_jogo(raiz) == {}
    assert rda.pecas_que_faltam(raiz) == (_DLL,)
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    (ficha,) = [j for j in censo.jogos if j.appid == "700003"]
    estorvo = next(e for e in ficha.estorvos if e.chave == pdj.FALTA_A_PECA)
    assert _DLL in estorvo.o_que and not estorvo.automatica
    assert ficha.veredito == pdj.IMPEDIDO


def test_a_peca_so_na_raiz_nao_basta_ela_e_ao_lado_do_executavel(lar: Path) -> None:
    raiz = _jogo(lar, "700004", dll_ao_lado_do_exe=False, dll_so_na_raiz=True)
    assert rda.ambiente_do_jogo(raiz) == {}
    assert rda.pecas_que_faltam(raiz) == (_DLL,)


def test_o_jogo_sem_o_sinal_nao_recebe_nada_e_nao_acusa_falta(lar: Path) -> None:
    raiz = _jogo(lar, "700005", sinal=None, dll_ao_lado_do_exe=False)
    assert rda.ambiente_do_jogo(raiz) == {} and rda.pecas_que_faltam(raiz) == ()
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    (ficha,) = [j for j in censo.jogos if j.appid == "700005"]
    assert pdj.FALTA_A_PECA not in [e.chave for e in ficha.estorvos]


def test_o_censo_acha_o_jogo_pelo_manifesto_sem_lista_embarcada(lar: Path) -> None:
    _jogo(lar, "700006")
    _jogo(lar, "700007", sinal=None)
    assert rda.ambientes_dos_jogos() == {"700006": {"WINEDLLOVERRIDES": _ESPERADO}}


# --- o arquivo de ambiente que o daemon escreve ---------------------------------------------


def _daemon_de_mentira() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
    )


def _env(path: Path) -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, _, valor = linha.partition("=")
            saida[chave] = valor
    return saida


def test_o_daemon_escreve_a_receita_no_env_do_jogo_e_so_dele(
    lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: pasta)
    _jogo(lar, "700008")
    _jogo(lar, "700009", dll_ao_lado_do_exe=False)
    materialize_launch_env(_daemon_de_mentira())
    com = _env(pasta / "steam_app_700008.env")
    assert com["WINEDLLOVERRIDES"] == _ESPERADO
    assert com["SDL_ACCELEROMETER_AS_JOYSTICK"] == "0", "a receita não pode tirar o resto"
    assert not (pasta / "steam_app_700009.env").exists(), "jogo sem a peça ganhou arquivo"
    assert "WINEDLLOVERRIDES" not in _env(pasta / "default.env")


def test_o_jogo_que_deixa_de_ter_a_receita_perde_o_arquivo(
    lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: pasta)
    raiz = _jogo(lar, "700010")
    materialize_launch_env(_daemon_de_mentira())
    assert (pasta / "steam_app_700010.env").is_file()
    (raiz / "Binaries" / "Win64" / _DLL).unlink()
    materialize_launch_env(_daemon_de_mentira())
    assert not (pasta / "steam_app_700010.env").exists()


# --- o wrapper ------------------------------------------------------------------------------


class _SocketQueResponde:
    def __init__(self, caminho: Path) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(2)
        self._parar = threading.Event()
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                self._sock.settimeout(0.2)
                conexao, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conexao:
                try:
                    conexao.settimeout(1.0)
                    pedido = json.loads(conexao.recv(4096).decode("utf-8"))
                    resposta = {"jsonrpc": "2.0", "id": pedido.get("id"), "result": {}}
                    conexao.sendall(json.dumps(resposta).encode("utf-8") + b"\n")
                except (OSError, ValueError):
                    pass

    def parar(self) -> None:
        self._parar.set()
        self._sock.close()
        self._fio.join(timeout=2)


def _path_minimo(pasta: Path, *, com_logger: Path | None = None) -> str:
    pasta.mkdir()
    for ferramenta in ("sh", "python3", "env", "date", "mkdir", "mv"):
        real = shutil.which(ferramenta)
        assert real is not None, ferramenta
        (pasta / ferramenta).symlink_to(real)
    if com_logger is not None:
        falso = pasta / "logger"
        falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{com_logger}"\n', encoding="utf-8")
        falso.chmod(0o755)
    return str(pasta)


def _lancar(
    tmp_path: Path,
    linhas_do_env: list[str],
    *,
    extra: dict[str, str] | None = None,
    com_logger: Path | None = None,
    wrapper: Path = _WRAPPER,
) -> str:
    """Roda o wrapper com o daemon de mentira vivo e devolve o `WINEDLLOVERRIDES` do processo."""
    estado = tmp_path / "estado"
    pasta = estado / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True)
    (pasta / "steam_app_700011.env").write_text("\n".join(linhas_do_env) + "\n", encoding="utf-8")
    runtime = Path(tempfile.mkdtemp(prefix="hefr-"))
    (runtime / "hefesto-dualsense4unix").mkdir()
    servidor = _SocketQueResponde(
        runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock"
    )
    try:
        feito = subprocess.run(
            ["sh", str(wrapper), "sh", "-c", 'printf "%s" "${WINEDLLOVERRIDES-ausente}"'],
            env={
                "PATH": _path_minimo(tmp_path / "bin", com_logger=com_logger),
                "HOME": str(tmp_path / "casa"),
                "XDG_RUNTIME_DIR": str(runtime),
                "XDG_STATE_HOME": str(estado),
                "XDG_CONFIG_HOME": str(tmp_path / "casa" / ".config"),
                "SteamAppId": "700011",
                **(extra or {}),
            },
            capture_output=True, text=True, timeout=20.0, check=False,
        )
    finally:
        servidor.parar()
        shutil.rmtree(runtime, ignore_errors=True)
    assert feito.returncode == 0, feito.stderr
    return feito.stdout


def test_a_receita_atravessa_o_arquivo_e_o_wrapper_ate_o_processo_do_jogo(tmp_path: Path) -> None:
    assert _lancar(tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}"]) == _ESPERADO


@pytest.mark.parametrize(
    "valor",
    ["foo=b", "foo=n,b,x", "foo", "=n", "foo=n;bar", "fo o=n", "foo;bar=n=n", "$(id)=n", "foo=n,"],
)
def test_a_forma_fora_da_regra_nao_passa_e_fica_no_diario(tmp_path: Path, valor: str) -> None:
    diario = tmp_path / "diario.txt"
    saida = _lancar(tmp_path, [f"WINEDLLOVERRIDES={valor}"], com_logger=diario)
    assert saida == "ausente", f"«{valor}» passou pelo wrapper"
    assert "descartada" in diario.read_text(encoding="utf-8"), "o descarte não deixou linha"


@pytest.mark.parametrize("valor", ["foo=n", "foo,bar=n", "foo=n,b", "a=n;b=n,b", "xgameruntime=n;"])
def test_as_formas_da_regra_passam(tmp_path: Path, valor: str) -> None:
    assert _lancar(tmp_path, [f"WINEDLLOVERRIDES={valor}"]) == valor


def test_a_variavel_ja_posta_no_ambiente_nao_e_sobrescrita(tmp_path: Path) -> None:
    saida = _lancar(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}"], extra={"WINEDLLOVERRIDES": "dela=b"}
    )
    assert saida == "dela=b"


def _funcoes_do_wrapper(tmp_path: Path) -> Path:
    texto = _WRAPPER.read_text(encoding="utf-8")
    corte = texto.split("override_de_dll_valido() {", 1)[1].split("\n}\n", 1)[0]
    alvo = tmp_path / "funcoes.sh"
    alvo.write_text("override_de_dll_valido() {" + corte + "\n}\n", encoding="utf-8")
    return alvo


def test_o_espelho_python_e_o_sh_dizem_o_mesmo_de_cada_forma(tmp_path: Path) -> None:
    """A mesma tabela de vetores nas duas pontas: o dono em Python não pode divergir do `sh`."""
    vetores = [
        "foo=n", "foo=b", "foo,bar=n", "foo=n,b", "foo=n,b,x", "=n", "foo", "a=n;b=n",
        "a=n;;b=n", "a=n;b", "foo bar=n", "foo=n=n", ",foo=n", "foo,=n", "foo,,bar=n", "x=n;",
        ";", "", "a-b_c.d=n",
    ]
    funcoes = _funcoes_do_wrapper(tmp_path)
    for v in vetores:
        no_sh = subprocess.run(
            ["sh", "-c", '. "$1"; override_de_dll_valido "$2"', "x", str(funcoes), v],
            capture_output=True, text=True, timeout=10, check=False,
        ).returncode == 0
        no_py = rda.override_valido(v)
        assert no_sh == no_py, f"«{v}»: sh={no_sh}, python={no_py}"


def test_a_variavel_tem_canal_proprio_fora_da_allowlist_dos_lancadores() -> None:
    """A allowlist é o que o Hefesto escreve em todo lançador e o uninstall devolve; o
    `WINEDLLOVERRIDES` também é do usuário, e por isso a receita tem canal próprio no wrapper."""
    texto = _WRAPPER.read_text(encoding="utf-8")
    assert "WINEDLLOVERRIDES" not in ENV_ALLOWLIST
    corpo = texto.split("decide_envs() {", 1)[1].split("\n}\n", 1)[0]
    assert "WINEDLLOVERRIDES" not in corpo
    canal = texto.split("receita_do_jogo() {", 1)[1].split("\n}\n", 1)[0]
    for var in rda.VARIAVEIS_DO_WRAPPER:
        assert f"{var}=*)" in canal, var


def test_a_carona_dos_outros_lancadores_nao_leva_a_receita(tmp_path: Path) -> None:
    """A receita é de UM jogo: o `default.env`, que as estradas copiam, nunca a traz."""
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    (pasta / "default.env").write_text("SDL_JOYSTICK_HIDAPI=0\n", encoding="utf-8")
    (pasta / "steam_app_700011.env").write_text(
        f"WINEDLLOVERRIDES={_ESPERADO}\n", encoding="utf-8"
    )
    assert "WINEDLLOVERRIDES" not in cpe.ambiente_da_ponte(pasta)
