"""AS-REGRAS-DO-SOM-VALEM-NO-WIREPLUMBER-DA-DISTRO-01 — a pasta que o WirePlumber lê.

O WirePlumber 0.5 lê SPA-JSON em ``wireplumber.conf.d/``. O 0.4 (Ubuntu 24.04, Linux
Mint 22, Debian 12) lê Lua em ``main.lua.d/`` e IGNORA a pasta do 0.5 sem erro: o 51
(o microfone do controle não vira padrão), o 52/53 (o controle só HID) e o 54 (o
alto-falante não dorme) não valiam ali, e o doctor dava verde porque só conferia se o
arquivo existia.

A pergunta é pela capacidade, não pela versão: a pasta ``main.lua.d`` na configuração
de sistema que o próprio WirePlumber traz. Três lugares fazem essa pergunta (o Python
do produto, o script de instalação e o doctor) e o teste os compara.

Tudo aqui roda num lar de mentira, com ``HEFESTO_WIREPLUMBER_SISTEMA`` apontando para
um ``/usr/share/wireplumber`` falso: nada toca o WirePlumber nem o ``~/.config`` de
quem roda a régua.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import memoria_dos_controles as memoria
from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.xdg_paths import (
    WIREPLUMBER_SISTEMA_ENV_VAR,
    wireplumber_config_dir,
    wireplumber_dropin,
    wireplumber_forma,
    wireplumber_nome_do_dropin,
)

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
ASSETS = RAIZ / "assets" / "wireplumber"
UNINSTALL = RAIZ / "uninstall.sh"

N51 = "51-hefesto-dualsense-no-default-source"
N52 = "52-hefesto-dualsense-disable-source"
N53 = "53-hefesto-dualsense-disable-output"
N54 = "54-hefesto-dualsense-alto-falante-nunca-dorme"
NOMES = (N51, N52, N53, N54)

SISTEMA_04 = ("wireplumber.conf", "main.lua.d")
SISTEMA_05 = ("wireplumber.conf", "wireplumber.conf.d")
SISTEMA_SO_LUA = ("main.lua.d",)
SISTEMA_VAZIO: tuple[str, ...] = ()


def _sistema(tmp_path: Path, itens: tuple[str, ...], nome: str = "sistema") -> Path:
    """Um ``/usr/share/wireplumber`` de mentira com os ``itens`` (pasta se acaba em ``.d``)."""
    raiz = tmp_path / nome
    raiz.mkdir()
    for item in itens:
        if item.endswith(".d"):
            (raiz / item).mkdir()
        else:
            (raiz / item).write_text("# dublê\n", encoding="utf-8")
    return raiz


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return casa


def _com_sistema(monkeypatch: pytest.MonkeyPatch, raiz: Path) -> None:
    monkeypatch.setenv(WIREPLUMBER_SISTEMA_ENV_VAR, str(raiz))


@pytest.mark.parametrize(
    ("itens", "forma", "pasta"),
    [
        (SISTEMA_SO_LUA, "lua", "main.lua.d"),
        (SISTEMA_04, "lua", "main.lua.d"),
        (SISTEMA_05, "conf", "wireplumber.conf.d"),
        (SISTEMA_VAZIO, "conf", "wireplumber.conf.d"),
    ],
)
def test_o_dono_devolve_a_pasta_que_o_wireplumber_instalado_le(
    tmp_path: Path,
    lar: Path,
    monkeypatch: pytest.MonkeyPatch,
    itens: tuple[str, ...],
    forma: str,
    pasta: str,
) -> None:
    _com_sistema(monkeypatch, _sistema(tmp_path, itens))
    assert wireplumber_forma() == forma
    assert wireplumber_config_dir() == lar / ".config" / "wireplumber" / pasta


def test_o_dono_honra_o_xdg_config_home_nas_duas_formas(
    tmp_path: Path, lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    _com_sistema(monkeypatch, _sistema(tmp_path, SISTEMA_04))
    assert wireplumber_config_dir() == xdg / "wireplumber" / "main.lua.d"
    _com_sistema(monkeypatch, _sistema(tmp_path, SISTEMA_05, "sistema5"))
    assert wireplumber_config_dir() == xdg / "wireplumber" / "wireplumber.conf.d"


def test_o_nome_do_dropin_troca_a_extensao_e_so_ela() -> None:
    assert wireplumber_nome_do_dropin(f"{N51}.conf", "lua") == f"{N51}.lua"
    assert wireplumber_nome_do_dropin(f"{N51}.conf", "conf") == f"{N51}.conf"
    assert wireplumber_nome_do_dropin(f"{N54}.lua", "conf") == f"{N54}.conf"


def test_o_dropin_mora_na_pasta_e_na_forma_certas(
    tmp_path: Path, lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _com_sistema(monkeypatch, _sistema(tmp_path, SISTEMA_04))
    assert wireplumber_dropin(f"{N54}.conf") == (
        lar / ".config/wireplumber/main.lua.d" / f"{N54}.lua"
    )
    _com_sistema(monkeypatch, _sistema(tmp_path, SISTEMA_05, "sistema5"))
    assert wireplumber_dropin(f"{N54}.conf") == (
        lar / ".config/wireplumber/wireplumber.conf.d" / f"{N54}.conf"
    )


def test_a_variavel_vazia_cai_no_padrao(lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(WIREPLUMBER_SISTEMA_ENV_VAR, "")
    assert wireplumber_forma() in {xdg_paths.FORMA_CONF, xdg_paths.FORMA_LUA}


def _ambiente(tmp_path: Path, itens: tuple[str, ...]) -> tuple[Path, dict[str, str]]:
    casa = tmp_path / "casa-script"
    (casa / ".config" / "wireplumber").mkdir(parents=True)
    binario = tmp_path / "bin-script"
    binario.mkdir()
    for nome in ("systemctl", "wpctl", "pactl"):
        alvo = binario / nome
        alvo.write_text(f'#!/bin/bash\nprintf "DUBLE {nome} %s\\n" "$*" >&2\nexit 0\n')
        alvo.chmod(0o755)
    env = {
        "PATH": f"{binario}:/usr/bin:/bin",
        "HOME": str(casa),
        "WP_FIX": str(WP_FIX),
        WIREPLUMBER_SISTEMA_ENV_VAR: str(_sistema(tmp_path, itens, "sistema-script")),
    }
    return casa / ".config" / "wireplumber", env


def _rodar(func: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, "-c", f'set --; source "$WP_FIX"; {func}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )


def _arquivos(raiz: Path) -> set[str]:
    return {str(p.relative_to(raiz)) for p in raiz.rglob("*") if p.is_file()}


@pytest.mark.parametrize("itens", [SISTEMA_04, SISTEMA_SO_LUA])
def test_o_script_grava_o_lua_e_nenhum_conf_no_wireplumber_04(
    tmp_path: Path, itens: tuple[str, ...]
) -> None:
    wp, env = _ambiente(tmp_path, itens)
    for func in ("install_dropin", "install_dropin_acordado", "install_disable_dropin"):
        res = _rodar(func, env)
        assert res.returncode in (0, 3), res.stderr + res.stdout
    achados = _arquivos(wp)
    assert achados == {f"main.lua.d/{n}.lua" for n in NOMES}, achados
    assert not (wp / "wireplumber.conf.d").exists(), "o 0.4 ignora esta pasta: nada vai para lá"
    for nome in NOMES:
        assert (wp / "main.lua.d" / f"{nome}.lua").read_bytes() == (
            ASSETS / f"{nome}.lua"
        ).read_bytes()


@pytest.mark.parametrize("itens", [SISTEMA_05, SISTEMA_VAZIO])
def test_o_script_grava_o_conf_e_nenhum_lua_no_wireplumber_05(
    tmp_path: Path, itens: tuple[str, ...]
) -> None:
    wp, env = _ambiente(tmp_path, itens)
    for func in ("install_dropin", "install_dropin_acordado", "install_disable_dropin"):
        res = _rodar(func, env)
        assert res.returncode in (0, 3), res.stderr + res.stdout
    achados = _arquivos(wp)
    assert achados == {f"wireplumber.conf.d/{n}.conf" for n in NOMES}, achados
    assert not (wp / "main.lua.d").exists()
    for nome in NOMES:
        assert (wp / "wireplumber.conf.d" / f"{nome}.conf").read_bytes() == (
            ASSETS / f"{nome}.conf"
        ).read_bytes()


def test_a_troca_de_wireplumber_nao_deixa_a_forma_velha(tmp_path: Path) -> None:
    """Instalou no 0.5, a distro virou 0.4: o `.conf` velho sai quando o `.lua` entra."""
    wp, env = _ambiente(tmp_path, SISTEMA_05)
    assert _rodar("install_dropin_acordado", env).returncode == 0
    assert (wp / "wireplumber.conf.d" / f"{N54}.conf").is_file()
    env_04 = {**env, WIREPLUMBER_SISTEMA_ENV_VAR: str(_sistema(tmp_path, SISTEMA_04, "s04"))}
    assert _rodar("install_dropin_acordado", env_04).returncode == 0
    assert (wp / "main.lua.d" / f"{N54}.lua").is_file()
    assert not (wp / "wireplumber.conf.d" / f"{N54}.conf").exists()
    (wp / "wireplumber.conf.d").mkdir(exist_ok=True)
    (wp / "wireplumber.conf.d" / f"{N54}.conf").write_text("# sobra\n", encoding="utf-8")
    assert _rodar("install_dropin_acordado", env_04).returncode == 3
    assert not (wp / "wireplumber.conf.d" / f"{N54}.conf").exists()


@pytest.mark.parametrize(
    ("rotina", "nomes"),
    [
        ("install_dropin", (N51,)),
        ("install_disable_dropin", (N52, N53)),
    ],
)
def test_a_troca_de_wireplumber_tira_a_forma_velha_do_51_ao_53(
    tmp_path: Path, rotina: str, nomes: tuple[str, ...]
) -> None:
    """O `.conf` do 0.5 que sobrou sai quando a distro virou 0.4 e o `.lua` entra."""
    wp, env = _ambiente(tmp_path, SISTEMA_05)
    assert _rodar(rotina, env).returncode in (0, 3)
    for nome in nomes:
        assert (wp / "wireplumber.conf.d" / f"{nome}.conf").is_file()
    env_04 = {**env, WIREPLUMBER_SISTEMA_ENV_VAR: str(_sistema(tmp_path, SISTEMA_04, "s04"))}
    assert _rodar(rotina, env_04).returncode in (0, 3)
    for nome in nomes:
        assert (wp / "main.lua.d" / f"{nome}.lua").is_file()
        assert not (wp / "wireplumber.conf.d" / f"{nome}.conf").exists(), nome


def test_ligar_o_mic_tira_o_52_e_o_53_das_duas_formas(tmp_path: Path) -> None:
    wp, env = _ambiente(tmp_path, SISTEMA_04)
    (wp / "main.lua.d").mkdir()
    (wp / "wireplumber.conf.d").mkdir()
    for n in (N52, N53):
        (wp / "main.lua.d" / f"{n}.lua").write_text("-- x\n", encoding="utf-8")
        (wp / "wireplumber.conf.d" / f"{n}.conf").write_text("# x\n", encoding="utf-8")
    res = _rodar("_arma_dropins_do_mic", env)
    assert res.returncode == 0, res.stderr + res.stdout
    assert _arquivos(wp) == {f"main.lua.d/{N51}.lua"}, _arquivos(wp)


def test_a_forma_do_script_e_a_do_dono_e_a_do_doctor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Três lugares fazem a mesma pergunta; nenhum pode divergir."""
    casos = [SISTEMA_04, SISTEMA_05, SISTEMA_SO_LUA, SISTEMA_VAZIO]
    for i, itens in enumerate(casos):
        raiz = _sistema(tmp_path, itens, f"c{i}")
        _com_sistema(monkeypatch, raiz)
        esperado = wireplumber_forma()
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            WIREPLUMBER_SISTEMA_ENV_VAR: str(raiz),
        }
        script = subprocess.run(
            [BASH, "-c", f'set --; source "{WP_FIX}"; printf %s "$WP_FORMA"'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=env,
        ).stdout.strip()
        doctor = subprocess.run(
            [BASH, "-c", f'source "{DOCTOR}"; _wp_forma'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=env,
        ).stdout.strip()
        assert script == esperado == doctor, (itens, script, esperado, doctor)


def _as_tres_formas(env_sistema: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """A resposta do dono (Python), do script do som e do doctor para o mesmo sistema."""
    monkeypatch.setenv(WIREPLUMBER_SISTEMA_ENV_VAR, env_sistema)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), WIREPLUMBER_SISTEMA_ENV_VAR: env_sistema}
    script = subprocess.run(
        [BASH, "-c", f'set --; source "{WP_FIX}"; printf %s "$WP_FORMA"'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    ).stdout.strip()
    doctor = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; _wp_forma'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    ).stdout.strip()
    return {wireplumber_forma(), script, doctor}


@pytest.mark.parametrize(
    ("usr", "etc", "forma"),
    [
        (SISTEMA_05, ("main.lua.d",), "conf"),
        (SISTEMA_04, ("wireplumber.conf.d",), "lua"),
        (None, SISTEMA_04, "lua"),
        (None, SISTEMA_05, "conf"),
        (SISTEMA_VAZIO, SISTEMA_SO_LUA, "lua"),
    ],
)
def test_a_primeira_pasta_de_sistema_com_configuracao_decide(
    usr: tuple[str, ...] | None,
    etc: tuple[str, ...],
    forma: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``/usr/share`` vem antes de ``/etc``, e a primeira que traz configuração decide."""
    a = _sistema(tmp_path, usr, "usr") if usr is not None else tmp_path / "usr-ausente"
    b = _sistema(tmp_path, etc, "etc")
    assert _as_tres_formas(f"{a}:{b}", tmp_path, monkeypatch) == {forma}


def _doctor(
    tmp_path: Path,
    itens: tuple[str, ...],
    chamada: str,
    *,
    com_arquivo: str | None,
    wpctl: str | None,
) -> str:
    """Roda uma função REAL do doctor num lar de mentira, com ``wpctl`` de mentira."""
    casa = tmp_path / "casa-doctor"
    casa.mkdir(exist_ok=True)
    binario = tmp_path / "bin-doctor"
    binario.mkdir(exist_ok=True)
    if wpctl is not None:
        (binario / "wpctl").write_text(wpctl, encoding="utf-8")
        (binario / "wpctl").chmod(0o755)
    sistema = _sistema(tmp_path, itens, "sistema-doctor")
    forma_lua = "main.lua.d" in itens
    pasta = casa / ".config" / "wireplumber" / ("main.lua.d" if forma_lua else "wireplumber.conf.d")
    pasta.mkdir(parents=True)
    if com_arquivo:
        ext = "lua" if forma_lua else "conf"
        shutil.copy(ASSETS / f"{com_arquivo}.{ext}", pasta / f"{com_arquivo}.{ext}")
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; {chamada}'],
        env={
            "PATH": f"{binario}:/usr/bin:/bin",
            "HOME": str(casa),
            WIREPLUMBER_SISTEMA_ENV_VAR: str(sistema),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return r.stdout + r.stderr


def _wpctl_de_mentira(*, prop: str | None, alvo: str = "alsa_output") -> str:
    """Um ``wpctl`` com o controle na mesa; o nó dele traz (ou não) a propriedade."""
    linha_da_prop = f"    printf '%s\\n' '  * {prop}'\n" if prop else ""
    sink = " │      47. DualSense Wireless Controller [vol: 1.00]"
    return (
        "#!/bin/bash\n"
        'case "$1" in\n'
        f"  status) printf '%s\\n' ' ├─ Sinks:' '{sink}';;\n"
        "  inspect)\n"
        '    [[ "$2" == 47 ]] || exit 0\n'
        "    printf 'id 47\\n'\n"
        f"    printf '    node.name = \"{alvo}.usb-Sony_DualSense-00.analog-stereo\"\\n'\n"
        f"{linha_da_prop}"
        "    ;;\n"
        "esac\n"
        "exit 0\n"
    )


PROP_54 = 'session.suspend-timeout-seconds = "0"'
PROP_51 = 'priority.session = "1500"'


@pytest.mark.parametrize("itens", [SISTEMA_04, SISTEMA_05])
def test_o_arquivo_no_lugar_e_o_wireplumber_que_leu_a_regra_passam(
    tmp_path: Path, itens: tuple[str, ...]
) -> None:
    saida = _doctor(
        tmp_path,
        itens,
        "check_dropin_do_alto_falante_acordado",
        com_arquivo=N54,
        wpctl=_wpctl_de_mentira(prop=PROP_54),
    )
    assert "[ OK ] o alto-falante do controle não dorme no cabo" in saida, saida


@pytest.mark.parametrize("itens", [SISTEMA_04, SISTEMA_05])
def test_o_arquivo_no_lugar_mas_o_wireplumber_sem_a_propriedade_avisa(
    tmp_path: Path, itens: tuple[str, ...]
) -> None:
    """A MORDIDA do defeito: o 0.4 ignorava a pasta e o doctor dava verde."""
    saida = _doctor(
        tmp_path,
        itens,
        "check_dropin_do_alto_falante_acordado",
        com_arquivo=N54,
        wpctl=_wpctl_de_mentira(prop=None),
    )
    assert "[WARN]" in saida and "não leu a regra" in saida, saida
    assert "[ OK ]" not in saida, saida


def test_o_51_no_lugar_e_lido_passa_e_nao_lido_avisa(tmp_path: Path) -> None:
    lido = _doctor(
        tmp_path,
        SISTEMA_04,
        "check_dropin_do_mic_armado",
        com_arquivo=N51,
        wpctl=_wpctl_de_mentira(prop=PROP_51, alvo="alsa_input"),
    )
    assert "[ OK ] a política de microfone do install está armada" in lido, lido
    (tmp_path / "outro").mkdir()
    nao_lido = _doctor(
        tmp_path / "outro",
        SISTEMA_04,
        "check_dropin_do_mic_armado",
        com_arquivo=N51,
        wpctl=_wpctl_de_mentira(prop=None, alvo="alsa_input"),
    )
    assert "[WARN]" in nao_lido and "não leu a regra" in nao_lido, nao_lido


def test_sem_controle_na_mesa_so_se_confere_a_forma_na_pasta(tmp_path: Path) -> None:
    """Sem nó para perguntar, vale o arquivo na pasta certa (a medida que há)."""
    mudo = "#!/bin/sh\nexit 0\n"
    saida = _doctor(
        tmp_path,
        SISTEMA_04,
        "check_dropin_do_alto_falante_acordado",
        com_arquivo=N54,
        wpctl=mudo,
    )
    assert "[ OK ] o alto-falante do controle não dorme no cabo" in saida, saida


def test_sem_wpctl_nenhum_tambem_nao_reclama_do_que_nao_mede(tmp_path: Path) -> None:
    saida = _doctor(
        tmp_path,
        SISTEMA_04,
        "check_dropin_do_alto_falante_acordado",
        com_arquivo=N54,
        wpctl=None,
    )
    assert "falta " not in saida, saida


def test_o_0_4_com_o_arquivo_na_pasta_do_0_5_e_arquivo_faltando(tmp_path: Path) -> None:
    """O .conf na pasta do 0.5, no sistema 0.4: o doctor diz que FALTA o do 0.4."""
    casa = tmp_path / "casa-errada"
    pasta = casa / ".config/wireplumber/wireplumber.conf.d"
    pasta.mkdir(parents=True)
    shutil.copy(ASSETS / f"{N54}.conf", pasta / f"{N54}.conf")
    sistema = _sistema(tmp_path, SISTEMA_04, "sistema-errado")
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_dropin_do_alto_falante_acordado'],
        env={"PATH": "/usr/bin:/bin", "HOME": str(casa), WIREPLUMBER_SISTEMA_ENV_VAR: str(sistema)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    saida = r.stdout + r.stderr
    assert "[WARN]" in saida and "pode dormir no cabo" in saida, saida
    assert "main.lua.d" in saida, "o aviso tem de dizer a pasta que o WirePlumber lê"


def _propriedades_conf(texto: str) -> dict[str, str]:
    """As propriedades que o ``.conf`` põe em ``update-props`` (chave -> valor)."""
    saida: dict[str, str] = {}
    for m in re.finditer(r"^\s{4,}([a-z][\w.\-]+)\s*=\s*([^\s#]+)\s*$", texto, re.M):
        saida[m.group(1)] = m.group(2)
    return saida


def _propriedades_lua(texto: str) -> dict[str, str]:
    saida: dict[str, str] = {}
    for m in re.finditer(r'\["([\w.\-]+)"\]\s*=\s*([^,\s]+),', texto):
        saida[m.group(1)] = m.group(2)
    return saida


@pytest.mark.parametrize("nome", NOMES)
def test_cada_regra_em_lua_poe_as_mesmas_propriedades_do_conf(nome: str) -> None:
    conf = (ASSETS / f"{nome}.conf").read_text(encoding="utf-8")
    lua = (ASSETS / f"{nome}.lua").read_text(encoding="utf-8")
    do_conf = {k: v for k, v in _propriedades_conf(conf).items() if k != "matches"}
    do_lua = _propriedades_lua(lua)
    assert do_lua, f"{nome}.lua não põe propriedade nenhuma"
    for chave, valor in do_lua.items():
        assert chave in do_conf, f"{nome}.lua põe {chave}, que o .conf não põe"
        assert do_conf[chave].strip('"') == valor.strip('"'), (chave, do_conf[chave], valor)
    assert "alsa_monitor.rules" in lua, "o 0.4 lê as regras de ALSA em alsa_monitor.rules"
    assert "apply_properties" in lua and "matches" in lua


@pytest.mark.parametrize("nome", NOMES)
def test_o_lua_casa_todas_as_grafias_que_o_conf_casa(nome: str) -> None:
    """O ``matches`` do 0.4 é glob: ``[Dd]ual[Ss]ense`` vira as quatro grafias."""
    lua = (ASSETS / f"{nome}.lua").read_text(encoding="utf-8")
    for grafia in ("DualSense", "Dualsense", "dualSense", "dualsense"):
        assert f'"{grafia}"' in lua, f"{nome}.lua perdeu a grafia {grafia}"


def test_o_lua_do_51_rebaixa_o_cartao_e_o_monitor_da_saida() -> None:
    lua = (ASSETS / f"{N51}.lua").read_text(encoding="utf-8")
    assert '"device.name"' in lua and "alsa_card" in lua
    assert "*onitor" in lua
    assert '["priority.session"] = 1500' in lua
    assert '["priority.session"] = 50' in lua


def test_o_54_em_lua_zera_o_timeout_da_saida() -> None:
    lua = (ASSETS / f"{N54}.lua").read_text(encoding="utf-8")
    assert '["session.suspend-timeout-seconds"] = 0' in lua
    assert "alsa_output" in lua


def test_o_uninstall_tira_os_quatro_em_lua_do_lar_e_do_xdg() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert "main.lua.d" in texto, "o uninstall não conhece a pasta do 0.4"
    for nome in NOMES:
        assert f"{nome}.lua" in texto, f"o uninstall não remove {nome}.lua"
    assert re.search(r'rm -f "\$\{_wp_raiz\}/wireplumber/main\.lua\.d/\$\{_wp\}"', texto)


def test_o_uninstall_remove_o_lua_de_verdade(tmp_path: Path) -> None:
    """O bloco do uninstall roda num lar de mentira e tira o `.lua`, menos o 51 marcado."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.index("for _wp_raiz in ")
    fim = texto.index(
        "\ndone\n", texto.index('rm -f "${_wp_raiz}/wireplumber/main.lua.d/${_wp}"')
    ) + len("\ndone\n")
    bloco = texto[inicio:fim]
    casa = tmp_path / "casa-un"
    pasta = casa / ".config" / "wireplumber" / "main.lua.d"
    pasta.mkdir(parents=True)
    for n in NOMES:
        (pasta / f"{n}.lua").write_text("-- do hefesto\n", encoding="utf-8")
    (pasta / f"{N51}.lua").write_text("-- Recriado manualmente\n", encoding="utf-8")
    binario = tmp_path / "bin-un"
    binario.mkdir()
    (binario / "systemctl").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (binario / "systemctl").chmod(0o755)
    r = subprocess.run(
        [BASH, "-c", f"log() {{ :; }}\n{bloco}"],
        env={"PATH": f"{binario}:/usr/bin:/bin", "HOME": str(casa)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in pasta.iterdir()) == [f"{N51}.lua"], (
        "saem os 52, 53 e 54; o 51 marcado como «recriado manualmente» fica"
    )


def test_a_memoria_acha_o_dropin_nas_duas_formas(tmp_path: Path) -> None:
    """A troca de versão do WirePlumber deixa a forma velha: o rastro de cada uma conta."""
    lar = tmp_path / "lar-memoria"
    raizes = memoria.Raizes(
        lar=lar,
        config=lar / ".config",
        estado=lar / ".local/state",
        dados=lar / ".local/share",
        cache=lar / ".cache",
        execucao=tmp_path / "run",
        bluez=tmp_path / "var/lib/bluetooth",
        varlib=tmp_path / "var/lib/hefesto-dualsense4unix",
        guardado_do_root=tmp_path / "var/lib/hefesto-memoria-guardada",
        sistema=tmp_path / "sistema",
        repositorio=None,
    )
    esperados = set()
    for sub, ext in (("wireplumber.conf.d", "conf"), ("main.lua.d", "lua")):
        pasta = raizes.config / "wireplumber" / sub
        pasta.mkdir(parents=True)
        for nome in (N51, N54):
            (pasta / f"{nome}.{ext}").write_text("x\n", encoding="utf-8")
            esperados.add(str(pasta / f"{nome}.{ext}"))
    (raizes.config / "wireplumber" / "main.lua.d" / "50-de-outro-app.lua").write_text("x\n")
    onde = {r.onde for r in memoria._rastros_do_lar(raizes)}
    assert esperados <= onde, esperados - onde
    assert not any("de-outro-app" in o for o in onde), "o arquivo de outro app não é nosso"
