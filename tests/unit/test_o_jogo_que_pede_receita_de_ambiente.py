"""O jogo que só abre com uma receita de ambiente a recebe pelo wrapper, ele e a família.

A família GDK recebe a peça do Hefesto pelo par `xgameruntime=b` + `WINEDLLPATH=@hefesto-wine`
(A-PECA-GDK-DO-HEFESTO-CUMPRE-O-CONTRATO-DO-XASYNC-01): a peça conta só com o sha256 do pino, e
o wrapper passa o par inteiro ou nada.
"""
from __future__ import annotations

import hashlib
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
_ESPERADO = "xgameruntime=b"
_PASTA = "@hefesto-wine"
_PAR = {"WINEDLLOVERRIDES": _ESPERADO, "WINEDLLPATH": _PASTA}
_PECA_DE_MENTIRA = b"MZ a peca de mentira do teste"


def _jogo(
    biblioteca: Path,
    appid: str,
    *,
    sinal: str | None = "MicrosoftGame.config",
    dll_ao_lado_do_exe: bool = False,
    dll_so_na_raiz: bool = False,
) -> Path:
    """Um jogo de mentira no `steamapps` da biblioteca: manifesto, pasta, executável e, se
    pedida, uma DLL do usuário ao lado do executável (que a peça do Hefesto não precisa)."""
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


def _instalar_peca(casa: Path, conteudo: bytes = _PECA_DE_MENTIRA) -> Path:
    """O que o install faz: a DLL na pasta da peça, dentro do lar de mentira."""
    alvo = rda.pasta_da_peca(casa) / "x86_64-windows" / _DLL
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(conteudo)
    return alvo


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Biblioteca Steam num HOME de mentira, com a peça do Hefesto instalada e um pino de
    mentira que bate com ela (o pino de verdade é o sha256 do binário compilado)."""
    casa = tmp_path / "casa"
    biblioteca = casa / ".local" / "share" / "Steam"
    (biblioteca / "steamapps").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    pino = tmp_path / "pino.txt"
    pino.write_text(
        f"name=peca-de-mentira\nsha256={hashlib.sha256(_PECA_DE_MENTIRA).hexdigest()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rda, "PINO_DA_PECA", pino)
    _instalar_peca(casa)
    return biblioteca


def _casa(biblioteca: Path) -> Path:
    return biblioteca.parents[2]


def test_a_tabela_traz_a_familia_gdk_sem_appid_embarcado() -> None:
    tabela = {r.id: r for r in rda.carregar_tabela()}
    gdk, pasta = tabela["gdk-xgameruntime"], tabela["gdk-xgameruntime-pasta"]
    assert (gdk.variavel, gdk.valor, gdk.peca) == ("WINEDLLOVERRIDES", _ESPERADO, "@hefesto")
    assert (pasta.variavel, pasta.valor, pasta.peca) == ("WINEDLLPATH", _PASTA, "@hefesto")
    assert gdk.sinais == pasta.sinais, "o par tem de ligar pelos mesmos sinais"
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
        "ok-b,A.cfg,WINEDLLOVERRIDES,foo=b,@hefesto\n"
        "ok-pasta,A.cfg,WINEDLLPATH,@hefesto-wine,@hefesto\n"
        "var-fora,A.cfg,LD_PRELOAD,foo=n,foo.dll\n"
        "forma-fora,A.cfg,WINEDLLOVERRIDES,foo=x,foo.dll\n"
        "pasta-livre,A.cfg,WINEDLLPATH,/tmp/pasta,@hefesto\n"
        "pasta-de-outra-peca,A.cfg,WINEDLLPATH,@hefesto-wine,foo.dll\n"
        "sinal-fora,../A.cfg,WINEDLLOVERRIDES,foo=n,foo.dll\n"
        "sem-peca,A.cfg,WINEDLLOVERRIDES,foo=n,\n",
        encoding="utf-8",
    )
    assert [r.id for r in rda.carregar_tabela(csv)] == ["ok", "ok-b", "ok-pasta"]
    assert rda.carregar_tabela(tmp_path / "nao-existe.csv") == ()


def test_o_jogo_com_o_sinal_e_a_peca_recebe_a_receita(lar: Path) -> None:
    raiz = _jogo(lar, "700001")
    assert rda.ambiente_do_jogo(raiz) == _PAR
    assert rda.pecas_que_faltam(raiz) == ()


def test_o_outro_sinal_da_familia_tambem_liga(lar: Path) -> None:
    raiz = _jogo(lar, "700002", sinal="installscript-gamingrepair.vdf")
    assert rda.ambiente_do_jogo(raiz) == _PAR


def test_sem_a_peca_a_receita_nao_sai_e_o_prontuario_diz_falta(lar: Path) -> None:
    """Sem a peça o `=b` deixaria o Wine sem DLL: nada é passado, e a peça é nomeada uma vez."""
    (rda.pasta_da_peca(_casa(lar)) / "x86_64-windows" / _DLL).unlink()
    raiz = _jogo(lar, "700003")
    assert rda.ambiente_do_jogo(raiz) == {}
    assert rda.pecas_que_faltam(raiz) == (rda.NOME_DA_PECA_DO_HEFESTO,)
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    (ficha,) = [j for j in censo.jogos if j.appid == "700003"]
    estorvo = next(e for e in ficha.estorvos if e.chave == pdj.FALTA_A_PECA)
    assert rda.NOME_DA_PECA_DO_HEFESTO in estorvo.o_que and not estorvo.automatica
    assert "instalador" in estorvo.a_cura
    assert ficha.veredito == pdj.IMPEDIDO


def test_a_peca_que_nao_bate_com_o_pino_nao_conta(lar: Path) -> None:
    _instalar_peca(_casa(lar), b"MZ outra DLL, de outra origem")
    raiz = _jogo(lar, "700004")
    assert rda.ambiente_do_jogo(raiz) == {}
    assert rda.pecas_que_faltam(raiz) == (rda.NOME_DA_PECA_DO_HEFESTO,)


def test_a_dll_do_usuario_ao_lado_do_exe_nao_e_a_peca_do_hefesto(lar: Path) -> None:
    """Prova da D-1710-A-PECA-GDK-DO-HEFESTO-VAI-PELO-PAR-B-E-WINEDLLPATH."""
    (rda.pasta_da_peca(_casa(lar)) / "x86_64-windows" / _DLL).unlink()
    raiz = _jogo(lar, "700012", dll_ao_lado_do_exe=True)
    assert rda.ambiente_do_jogo(raiz) == {}


def test_a_peca_de_arquivo_ainda_e_ao_lado_do_executavel(lar: Path, tmp_path: Path) -> None:
    """O modo de peça por nome de arquivo continua: só ao lado do exe, não na raiz."""
    csv = tmp_path / "t.csv"
    csv.write_text(
        "id,sinais,variavel,valor,peca\nx,MicrosoftGame.config,WINEDLLOVERRIDES,xgameruntime=n,"
        f"{_DLL}\n",
        encoding="utf-8",
    )
    tabela = rda.carregar_tabela(csv)
    so_na_raiz = _jogo(lar, "700013", dll_so_na_raiz=True)
    assert rda.ambiente_do_jogo(so_na_raiz, tabela) == {}
    assert rda.pecas_que_faltam(so_na_raiz, tabela) == (_DLL,)
    ao_lado = _jogo(lar, "700014", dll_ao_lado_do_exe=True)
    assert rda.ambiente_do_jogo(ao_lado, tabela) == {"WINEDLLOVERRIDES": "xgameruntime=n"}


def test_o_jogo_sem_o_sinal_nao_recebe_nada_e_nao_acusa_falta(lar: Path) -> None:
    (rda.pasta_da_peca(_casa(lar)) / "x86_64-windows" / _DLL).unlink()
    raiz = _jogo(lar, "700005", sinal=None)
    assert rda.ambiente_do_jogo(raiz) == {} and rda.pecas_que_faltam(raiz) == ()
    censo = pdj.levantar_censo(allowlist=[], pontes={})
    (ficha,) = [j for j in censo.jogos if j.appid == "700005"]
    assert pdj.FALTA_A_PECA not in [e.chave for e in ficha.estorvos]


def test_o_censo_acha_o_jogo_pelo_manifesto_sem_lista_embarcada(lar: Path) -> None:
    _jogo(lar, "700006")
    _jogo(lar, "700007", sinal=None)
    assert rda.ambientes_dos_jogos() == {"700006": _PAR}


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
    _jogo(lar, "700009", sinal=None)
    materialize_launch_env(_daemon_de_mentira())
    com = _env(pasta / "steam_app_700008.env")
    assert com["WINEDLLOVERRIDES"] == _ESPERADO and com["WINEDLLPATH"] == _PASTA
    assert com["SDL_ACCELEROMETER_AS_JOYSTICK"] == "0", "a receita não pode tirar o resto"
    assert not (pasta / "steam_app_700009.env").exists(), "jogo sem o sinal ganhou arquivo"
    padrao = _env(pasta / "default.env")
    assert "WINEDLLOVERRIDES" not in padrao and "WINEDLLPATH" not in padrao


def test_o_jogo_que_deixa_de_ter_a_receita_perde_o_arquivo(
    lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: pasta)
    raiz = _jogo(lar, "700010")
    materialize_launch_env(_daemon_de_mentira())
    assert (pasta / "steam_app_700010.env").is_file() and raiz.is_dir()
    (rda.pasta_da_peca(_casa(lar)) / "x86_64-windows" / _DLL).unlink()
    materialize_launch_env(_daemon_de_mentira())
    assert not (pasta / "steam_app_700010.env").exists()


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


def _lancar_par(
    tmp_path: Path,
    linhas_do_env: list[str],
    *,
    extra: dict[str, str] | None = None,
    com_logger: Path | None = None,
    wrapper: Path = _WRAPPER,
    com_peca: bool = False,
    antes: tuple[str, ...] = (),
) -> tuple[str, str]:
    """Roda o wrapper com o daemon de mentira vivo e devolve o `WINEDLLOVERRIDES` e o
    `WINEDLLPATH` do processo (``ausente`` quando a variável não chegou). ``antes`` são as
    atribuições `VAR=VAL` que a Launch Option põe antes do comando."""
    if com_peca:
        _instalar_peca(tmp_path / "casa")
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
            [
                "sh", str(wrapper), *antes, "sh", "-c",
                'printf "%s|%s" "${WINEDLLOVERRIDES-ausente}" "${WINEDLLPATH-ausente}"',
            ],
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
    dll, _, pasta = feito.stdout.partition("|")
    return dll, pasta


def _lancar(tmp_path: Path, linhas_do_env: list[str], **kw: object) -> str:
    """Só o `WINEDLLOVERRIDES`, para as receitas sem par."""
    return _lancar_par(tmp_path, linhas_do_env, **kw)[0]  # type: ignore[arg-type]


def _pasta_real(tmp_path: Path) -> str:
    return str(rda.pasta_da_peca(tmp_path / "casa"))


def test_o_par_atravessa_o_arquivo_e_o_wrapper_ate_o_processo_do_jogo(tmp_path: Path) -> None:
    """Prova da D-1710-A-PECA-GDK-DO-HEFESTO-VAI-PELO-PAR-B-E-WINEDLLPATH."""
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}", f"WINEDLLPATH={_PASTA}"], com_peca=True
    )
    assert saida == (_ESPERADO, _pasta_real(tmp_path))


@pytest.mark.parametrize(
    "valor",
    ["foo=x", "foo=n,b,x", "foo", "=n", "foo=n;bar", "fo o=n", "foo;bar=n=n", "$(id)=n", "foo=n,"],
)
def test_a_forma_fora_da_regra_nao_passa_e_fica_no_diario(tmp_path: Path, valor: str) -> None:
    diario = tmp_path / "diario.txt"
    saida = _lancar(tmp_path, [f"WINEDLLOVERRIDES={valor}"], com_logger=diario)
    assert saida == "ausente", f"«{valor}» passou pelo wrapper"
    assert "descartada" in diario.read_text(encoding="utf-8"), "o descarte não deixou linha"


@pytest.mark.parametrize("valor", ["foo=n", "foo,bar=n", "foo=n,b", "a=n;b=n,b", "xgameruntime=n;"])
def test_as_formas_da_regra_passam(tmp_path: Path, valor: str) -> None:
    assert _lancar(tmp_path, [f"WINEDLLOVERRIDES={valor}"]) == valor


def test_o_b_sem_a_pasta_nao_passa_e_fica_no_diario(tmp_path: Path) -> None:
    """O `=b` sozinho faria o Wine recusar a DLL (erro 126) e o jogo não abriria."""
    diario = tmp_path / "diario.txt"
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}"], com_logger=diario, com_peca=True
    )
    assert saida == ("ausente", "ausente")
    assert "=b sem a pasta" in diario.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "pasta", ["/tmp/pasta", "@hefesto-wine/../x", "$HOME/x", "@hefesto-wine:/tmp", "", "@hefesto"]
)
def test_o_caminho_livre_no_winedllpath_derruba_o_par_inteiro(tmp_path: Path, pasta: str) -> None:
    diario = tmp_path / "diario.txt"
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}", f"WINEDLLPATH={pasta}"],
        com_logger=diario, com_peca=True,
    )
    assert saida == ("ausente", "ausente"), f"«{pasta}» passou pelo wrapper"
    assert "WINEDLLPATH fora do literal" in diario.read_text(encoding="utf-8")


def test_sem_a_peca_no_disco_o_par_nao_passa(tmp_path: Path) -> None:
    diario = tmp_path / "diario.txt"
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}", f"WINEDLLPATH={_PASTA}"], com_logger=diario
    )
    assert saida == ("ausente", "ausente")
    assert "não está em" in diario.read_text(encoding="utf-8")


def test_a_pasta_sem_o_override_nao_passa(tmp_path: Path) -> None:
    saida = _lancar_par(tmp_path, [f"WINEDLLPATH={_PASTA}"], com_peca=True)
    assert saida == ("ausente", "ausente")


def test_a_variavel_ja_posta_no_ambiente_nao_e_sobrescrita(tmp_path: Path) -> None:
    saida = _lancar(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}"], extra={"WINEDLLOVERRIDES": "dela=b"}
    )
    assert saida == "dela=b"


@pytest.mark.parametrize(
    ("extra", "esperado"),
    [
        ({"WINEDLLOVERRIDES": "dela=n"}, ("dela=n", "ausente")),
        ({"WINEDLLPATH": "/dela"}, ("ausente", "/dela")),
    ],
)
def test_o_que_quem_lancou_pos_derruba_a_receita_inteira(
    tmp_path: Path, extra: dict[str, str], esperado: tuple[str, str]
) -> None:
    diario = tmp_path / "diario.txt"
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}", f"WINEDLLPATH={_PASTA}"],
        extra=extra, com_logger=diario, com_peca=True,
    )
    assert saida == esperado
    assert "o que ele pôs manda" in diario.read_text(encoding="utf-8")


def test_a_launch_option_var_igual_valor_tambem_derruba_a_receita(tmp_path: Path) -> None:
    """`WINEDLLOVERRIDES="xgameruntime=n" %command%` chega como argumento, não como ambiente."""
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_ESPERADO}", f"WINEDLLPATH={_PASTA}"],
        com_peca=True, antes=("DXVK_HUD=0", "WINEDLLOVERRIDES=xgameruntime=n"),
    )
    assert saida == ("xgameruntime=n", "ausente")


def _funcoes_do_wrapper(tmp_path: Path) -> Path:
    texto = _WRAPPER.read_text(encoding="utf-8")
    corte = texto.split("override_de_dll_valido() {", 1)[1].split("\n}\n", 1)[0]
    alvo = tmp_path / "funcoes.sh"
    alvo.write_text("override_de_dll_valido() {" + corte + "\n}\n", encoding="utf-8")
    return alvo


def test_o_espelho_python_e_o_sh_dizem_o_mesmo_de_cada_forma(tmp_path: Path) -> None:
    """A mesma tabela de vetores nas duas pontas: o dono em Python não pode divergir do `sh`."""
    vetores = [
        "foo=n", "foo=b", "foo=b,n", "foo=bb", "a=b;c=n", "foo,bar=n", "foo=n,b", "foo=n,b,x",
        "=n", "foo", "a=n;b=n",
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
    corpo = texto.split("decide_envs() {", 1)[1].split("\n}\n", 1)[0]
    for var in rda.VARIAVEIS_DO_WRAPPER:
        assert var not in ENV_ALLOWLIST and var not in corpo, var
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
        f"WINEDLLOVERRIDES={_ESPERADO}\nWINEDLLPATH={_PASTA}\n", encoding="utf-8"
    )
    ponte = cpe.ambiente_da_ponte(pasta)
    assert "WINEDLLOVERRIDES" not in ponte and "WINEDLLPATH" not in ponte
