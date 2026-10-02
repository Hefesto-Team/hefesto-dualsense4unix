"""O-UNINSTALL-NAO-DEIXA-RASTRO-01 — quem desinstala o Hefesto não perde o controle nos jogos.

A auditoria da ESQUECER-OS-CONTROLES-01 (25/09/2026) mediu, num lar de
mentira: depois do ``uninstall.sh --purge-config``, o ``config.json`` do Heroic
e o override do Flatpak de cada lançador continuavam com
``SDL_GAMECONTROLLER_IGNORE_DEVICES`` e ``PROTON_DISABLE_HIDRAW`` — os jogos
ficavam sem o DualSense físico, e sem o Hefesto para servi-lo. O
``conexao-zumbi.json`` segurava a pasta de estado de pé, e o XDG era ignorado.

DUAS METADES, e as duas mordem:

1. **O dono de «o que é nosso»** (``integrations/cura_por_estrada``): a escrita
   anota, o desfazer lê. O que ela pôs fica; o que ela mudou depois fica; o que
   estava lá antes volta; o arquivo que nasceu com o Hefesto sai. E a escrita
   usa a mesma conta: a chave nossa que sai do ambiente (o Modo Nativo) sai do
   arquivo.
2. **O ``uninstall.sh`` DE VERDADE, num lar de mentira.** HOME e os XDG_*
   desviados, sem barramento de sessão, uma guarda que sai se qualquer um
   apontar para a casa de verdade, e um PATH que só tem o que o teste pôs:
   os comandos que mudam a máquina (``sudo``, ``systemctl``, ``pkill``,
   ``flatpak``, ``busctl``…) são dublês que anotam e não fazem nada, e os que
   mexem em arquivo (``rm``, ``mv``, ``cp``…) RECUSAM caminho fora do lar de
   mentira. Os donos reais escrevem (o atalho da Steam, o Proton pinado, a
   carona da cura por estrada), o uninstall roda, e o «limpa?» da
   ESQUECER-OS-CONTROLES-01 (``memoria_dos_controles.conferir_a_casa``) tem de
   responder limpo.

A MORDIDA DA SPRINT está escrita como teste: o mesmo uninstall sem o passo
dos lançadores deixa o ambiente, e o «limpa?» acusa.
"""
from __future__ import annotations

import json
import os
import pwd
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import cura_por_estrada as cura
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.utils import memoria_dos_controles as m

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
SISTEMA = "/usr/local/bin:/usr/bin:/bin"

HEROIC = "com.heroicgameslauncher.hgl"
LUTRIS = "net.lutris.Lutris"
MGBA = "io.mgba.mGBA"

AMBIENTE_EMULADO = (
    "# Materializado pelo daemon do Hefesto\n"
    "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6\n"
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff\n"
    "__GL_SHADER_DISK_CACHE=1\n__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1\n"
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0\nSDL_ACCELEROMETER_AS_JOYSTICK=0\n"
)
AMBIENTE_NATIVO = (
    "# Materializado pelo daemon do Hefesto\n"
    "__GL_SHADER_DISK_CACHE=1\n__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1\n"
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0\nSDL_ACCELEROMETER_AS_JOYSTICK=0\n"
)

HEROIC_DELA = {
    "version": "v0",
    "defaultSettings": {
        "language": "pt",
        "enviromentOptions": [
            {"key": "MANGOHUD", "value": "1"},
            {"key": "__GL_SHADER_DISK_CACHE", "value": "0"},
        ],
    },
}
LUTRIS_DELA = "[Context]\ndevices=all;\nfilesystems=host;\n"


def _instalar_flatpak(lar: Path, app_id: str) -> None:
    meta = lar / ".local/share/flatpak/app" / app_id / "current/active/metadata"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(f"[Application]\nname={app_id}\n\n[Context]\ndevices=all;\n",
                    encoding="utf-8")


def _heroic(lar: Path, *, nativo: bool) -> Path:
    if not nativo:
        _instalar_flatpak(lar, HEROIC)
    pasta = lar / (".config/heroic" if nativo else f".var/app/{HEROIC}/config/heroic")
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / "config.json"
    alvo.write_text(json.dumps(HEROIC_DELA, indent=2) + "\n", encoding="utf-8")
    return alvo


def _lutris(lar: Path) -> Path:
    _instalar_flatpak(lar, LUTRIS)
    alvo = lar / ".local/share/flatpak/overrides" / LUTRIS
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(LUTRIS_DELA, encoding="utf-8")
    return alvo


def _ambiente(pasta: Path, corpo: str = AMBIENTE_EMULADO) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "default.env").write_text(corpo, encoding="utf-8")
    return pasta


def _curar(lar: Path, pasta: Path) -> tuple[str, ...]:
    """A carona do daemon — `curar_todas_as_estradas`, o chamador de verdade."""
    escritos: tuple[str, ...] = cura.curar_todas_as_estradas(
        lar=lar, pasta_do_ambiente=pasta, raiz_sistema=lar.parent / "flatpak-do-sistema")
    return escritos


def _opcoes(alvo: Path) -> dict[str, str]:
    dado = json.loads(alvo.read_text(encoding="utf-8"))
    return {x["key"]: x["value"] for x in dado["defaultSettings"]["enviromentOptions"]}


def _heroic_copia_para_o_jogo(config: Path, jogo: str, *, dela: list[dict[str, str]] | None = None,
                              ) -> Path:
    """O que o Heroic faz quando ela muda uma opção de um jogo — pelo fonte dele."""
    global_ = json.loads(config.read_text(encoding="utf-8"))["defaultSettings"]
    lista = [dict(x) for x in global_.get("enviromentOptions", [])] + list(dela or [])
    alvo = config.parent / "GamesConfig" / f"{jogo}.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(
        {jogo: {"wineVersion": {"name": "Proton - GE", "type": "proton"},
                "language": "", "enviromentOptions": lista},
         "version": "v0", "explicit": False}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    return alvo


def _lista_do_jogo(alvo: Path) -> list[tuple[str, str]]:
    dado = json.loads(alvo.read_text(encoding="utf-8"))
    return [(x["key"], x["value"]) for x in dado[alvo.stem]["enviromentOptions"]]


@pytest.fixture
def mesa(tmp_path: Path) -> dict[str, Path]:
    """Heroic (Flatpak), Lutris com o override dela, mGBA sem override."""
    lar = tmp_path / "lar"
    lar.mkdir()
    _instalar_flatpak(lar, MGBA)
    return {"lar": lar, "heroic": _heroic(lar, nativo=False), "lutris": _lutris(lar),
            "mgba": lar / ".local/share/flatpak/overrides" / MGBA,
            "pasta": _ambiente(tmp_path / "estado/launch_env")}


@pytest.mark.parametrize("nativo", [False, True], ids=["heroic-flatpak", "heroic-nativo"])
def test_o_desfazer_tira_so_o_que_e_nosso_e_devolve_o_que_era_dela(
    tmp_path: Path, nativo: bool
) -> None:
    """A MORDIDA: faça `_devolver_chaves` ignorar o `antes` e o cache de shader"""
    lar = tmp_path / "lar"
    lar.mkdir()
    _instalar_flatpak(lar, MGBA)
    heroic, lutris = _heroic(lar, nativo=nativo), _lutris(lar)
    mgba = lar / ".local/share/flatpak/overrides" / MGBA
    pasta = _ambiente(tmp_path / "estado/launch_env")

    assert set(_curar(lar, pasta)) == {"heroic", "lutris", "mgba"}
    assert _opcoes(heroic)["SDL_GAMECONTROLLER_IGNORE_DEVICES"] == "0x054c/0x0ce6,0x28de/0x11ff"
    assert "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6" in lutris.read_text(encoding="utf-8")
    assert mgba.is_file()
    assert cura.caminho_do_registro(pasta).is_file()

    feitos, completo = cura.desfazer_as_estradas([pasta], lar)

    assert completo
    assert json.loads(heroic.read_text(encoding="utf-8")) == HEROIC_DELA, (
        "o Heroic não voltou a ser o dela: o MANGOHUD e o cache de shader "
        "desligado são dela, e o resto é nosso")
    assert lutris.read_text(encoding="utf-8") == LUTRIS_DELA, (
        "o override do Lutris não voltou byte a byte ao que ela deu à mão")
    assert not mgba.exists(), "o override que nasceu com o Hefesto ficou"
    assert not cura.caminho_do_registro(pasta).exists(), "o registro sobreviveu ao desfazer"
    frases = " ".join(cura.frase_do_desfeito(f) for f in feitos)
    assert "devolvi o seu valor de antes em __GL_SHADER_DISK_CACHE" in frases


def test_o_valor_de_antes_volta_no_lugar_em_que_estava(mesa: dict[str, Path]) -> None:
    """A escrita põe o nosso por cima do dela, NA MESMA POSIÇÃO; o desfazer o"""
    dela = json.loads(json.dumps(HEROIC_DELA))
    dela["defaultSettings"]["enviromentOptions"].reverse()
    mesa["heroic"].write_text(json.dumps(dela, indent=2) + "\n", encoding="utf-8")
    _curar(mesa["lar"], mesa["pasta"])

    cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    assert json.loads(mesa["heroic"].read_text(encoding="utf-8")) == dela, (
        "o valor de antes voltou, mas fora do lugar em que ela o tinha")


def test_o_valor_que_ela_mudou_depois_do_hefesto_fica(mesa: dict[str, Path]) -> None:
    _curar(mesa["lar"], mesa["pasta"])
    dado = json.loads(mesa["heroic"].read_text(encoding="utf-8"))
    for item in dado["defaultSettings"]["enviromentOptions"]:
        if item["key"] == "PROTON_DISABLE_HIDRAW":
            item["value"] = "0x045e/0x028e"
    mesa["heroic"].write_text(json.dumps(dado, indent=2), encoding="utf-8")

    feitos, _ = cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    opcoes = _opcoes(mesa["heroic"])
    assert opcoes.get("PROTON_DISABLE_HIDRAW") == "0x045e/0x028e", (
        "o desfazer tirou um valor que ela escreveu depois do Hefesto")
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in opcoes
    assert any("ficaram as que você mudou" in cura.frase_do_desfeito(f) for f in feitos)


def test_a_chave_nossa_que_sai_do_ambiente_sai_do_arquivo(mesa: dict[str, Path]) -> None:
    """O Modo Nativo não tem `IGNORE` nem `DISABLE_HIDRAW` — todo modo, toda"""
    _curar(mesa["lar"], mesa["pasta"])
    _ambiente(mesa["pasta"], AMBIENTE_NATIVO)
    _curar(mesa["lar"], mesa["pasta"])

    opcoes = _opcoes(mesa["heroic"])
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in opcoes
    assert "PROTON_DISABLE_HIDRAW" not in opcoes
    assert opcoes["MANGOHUD"] == "1" and opcoes["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] == "0"
    lutris = mesa["lutris"].read_text(encoding="utf-8")
    assert "IGNORE_DEVICES" not in lutris and "DISABLE_HIDRAW" not in lutris
    assert "[Context]" in lutris and "SDL_ACCELEROMETER_AS_JOYSTICK=0" in lutris


def test_sem_registro_o_nome_do_produto_decide(mesa: dict[str, Path]) -> None:
    """A instalação de antes do registro escreveu sem anotar (o escritor de"""
    ambiente = cura.ambiente_da_ponte(mesa["pasta"])
    cura._escrever_no_heroic(mesa["heroic"], ambiente)
    cura._escrever_no_override(mesa["lutris"], ambiente)
    assert not cura.caminho_do_registro(mesa["pasta"]).exists()

    _, completo = cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    assert completo
    opcoes = _opcoes(mesa["heroic"])
    assert not set(opcoes) & cura._DO_PRODUTO_SEM_REGISTRO, opcoes
    assert opcoes["MANGOHUD"] == "1" and opcoes["__GL_SHADER_DISK_CACHE"] == "1"
    lutris = mesa["lutris"].read_text(encoding="utf-8")
    assert "IGNORE_DEVICES" not in lutris and "[Context]" in lutris


def test_um_valor_do_produto_de_antes_do_registro_nao_volta(mesa: dict[str, Path]) -> None:
    """A primeira escrita com registro acha um `IGNORE` de uma versão que"""
    cura._escrever_no_heroic(
        mesa["heroic"], {"SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054c/0x0ce6"})
    _curar(mesa["lar"], mesa["pasta"])

    cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in _opcoes(mesa["heroic"])


def test_arquivo_que_nao_abre_nao_e_reescrito_e_o_registro_fica(
    mesa: dict[str, Path]
) -> None:
    """Um `config.json` truncado pode ser o Heroic que morreu no meio de um"""
    _curar(mesa["lar"], mesa["pasta"])
    mesa["heroic"].write_text('{"defaultSettings": {"enviromentOpt', encoding="utf-8")
    antes = mesa["heroic"].read_bytes()

    feitos, completo = cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    assert not completo
    assert mesa["heroic"].read_bytes() == antes, "o desfazer reescreveu um arquivo que não abriu"
    assert str(mesa["heroic"]) in cura.ler_registro(mesa["pasta"])
    assert mesa["lutris"].read_text(encoding="utf-8") == LUTRIS_DELA, (
        "um arquivo que não abriu não pode segurar o desfazer dos outros")
    assert any("não consegui ler" in cura.frase_do_desfeito(f) for f in feitos)


@pytest.mark.parametrize("com_registro", [True, False], ids=["com-registro", "sem-registro"])
@pytest.mark.parametrize("nativo", [False, True], ids=["heroic-flatpak", "heroic-nativo"])
def test_a_copia_por_jogo_do_heroic_perde_so_o_que_e_nosso(
    tmp_path: Path, nativo: bool, com_registro: bool
) -> None:
    """O Heroic copia a lista global para dentro do jogo em que ela muda uma
    opção, e dali em diante a do jogo vale SOZINHA. Medido no disco dela em
    25/09: um jogo com o `IGNORE` e o `DISABLE_HIDRAW` copiados em 22/09. Sem
    o desfazer nas cópias, o uninstall deixa AQUELE jogo sem o DualSense.

    Nas duas casas do Heroic, com e sem registro (a instalação de antes dele).
    O que ela pôs só naquele jogo fica; o `__GL_SHADER_*` da cópia fica (pode
    ser a escolha dela para o jogo); o jogo cuja lista ela escreveu sem nada
    nosso sai byte a byte igual.

    A MORDIDA: tire de `desfazer_as_estradas` o laço das cópias e o `IGNORE`
    fica no jogo.
    """
    lar = tmp_path / "lar"
    lar.mkdir()
    heroic = _heroic(lar, nativo=nativo)
    pasta = _ambiente(tmp_path / "estado/launch_env")
    if com_registro:
        _curar(lar, pasta)
    else:
        cura._escrever_no_heroic(heroic, cura.ambiente_da_ponte(pasta))
    copia = _heroic_copia_para_o_jogo(heroic, "Jogo1",
                                      dela=[{"key": "DXVK_HUD", "value": "fps"}])
    sem_nada_nosso = heroic.parent / "GamesConfig" / "Jogo2.json"
    sem_nada_nosso.write_text(json.dumps(
        {"Jogo2": {"enviromentOptions": [{"key": "MANGOHUD", "value": "0"}]},
         "version": "v0", "explicit": True}, indent=2), encoding="utf-8")
    intocado = sem_nada_nosso.read_bytes()
    assert ("SDL_GAMECONTROLLER_IGNORE_DEVICES", "0x054c/0x0ce6,0x28de/0x11ff") in (
        _lista_do_jogo(copia))

    feitos, completo = cura.desfazer_as_estradas([pasta], lar)

    assert completo
    lista = _lista_do_jogo(copia)
    assert not {k for k, _ in lista} & cura._DO_PRODUTO_SEM_REGISTRO, (
        f"a cópia por jogo ficou com o ambiente do Hefesto: {lista}")
    assert lista[0] == ("MANGOHUD", "1") and lista[-1] == ("DXVK_HUD", "fps"), lista
    assert ("__GL_SHADER_DISK_CACHE_SKIP_CLEANUP", "1") in lista, (
        "a cópia do jogo perdeu uma variável que pode ser a escolha dela para ele")
    dado = json.loads(copia.read_text(encoding="utf-8"))
    assert dado["Jogo1"]["wineVersion"]["name"] == "Proton - GE" and dado["explicit"] is False
    assert not copia.read_text(encoding="utf-8").endswith("\n"), (
        "a cópia tem de sair no formato do dono (`JSON.stringify(c, null, 2)`)")
    assert sem_nada_nosso.read_bytes() == intocado
    assert any(str(copia) in cura.frase_do_desfeito(f) for f in feitos)


def test_a_copia_por_jogo_que_nao_abre_segura_o_registro(mesa: dict[str, Path]) -> None:
    """Uma cópia truncada que CITA uma variável nossa pode estar com ela: o"""
    _curar(mesa["lar"], mesa["pasta"])
    jogos = mesa["heroic"].parent / "GamesConfig"
    jogos.mkdir()
    (jogos / "torto.json").write_text(
        '{"x": {"enviromentOptions": [{"key": "SDL_GAMECONTROLLER_IGNORE_DEVICES", "va',
        encoding="utf-8")
    (jogos / "alheio.json").write_text("{nada", encoding="utf-8")
    torto = (jogos / "torto.json").read_bytes()

    feitos, completo = cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    assert not completo
    assert str(mesa["heroic"]) in cura.ler_registro(mesa["pasta"])
    erros = [f.arquivo.name for f in feitos if f.erro]
    assert erros == ["torto.json"], erros
    assert (jogos / "torto.json").read_bytes() == torto


NASCIDAS_DEPOIS_DO_REGISTRO: frozenset[str] = frozenset()


def test_os_espelhos_do_desfazer() -> None:
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST

    allowlist = set(ENV_ALLOWLIST)
    assert cura.PODEM_SER_DELA | cura.DELA_MANDA == m._VARIAVEIS_QUE_PODEM_SER_DELA
    assert not cura._DO_PRODUTO_SEM_REGISTRO & cura.DELA_MANDA
    assert allowlist >= cura.PODEM_SER_DELA
    assert not cura._DO_PRODUTO_SEM_REGISTRO & cura.PODEM_SER_DELA
    historico = allowlist - cura.PODEM_SER_DELA - NASCIDAS_DEPOIS_DO_REGISTRO
    assert historico == cura._DO_PRODUTO_SEM_REGISTRO
    assert cura._PASTA_DOS_OVERRIDES == m.PASTA_DOS_OVERRIDES
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    lar = Path("/lar")
    casas = censo._casas("Heroic", censo._onde(lar))
    assert tuple(str(config.relative_to(lar)) for config, _ in casas) == m.PASTAS_DO_HEROIC


_SO_A_BIBLIOTECA_PADRAO = (
    "import os, runpy, sys\n"
    "class _Recusa:\n"
    "    def find_spec(self, nome, path=None, target=None):\n"
    "        topo = nome.partition('.')[0]\n"
    "        if (topo in sys.stdlib_module_names or topo.startswith('_')\n"
    "                or topo == 'hefesto_dualsense4unix'):\n"
    "            return None\n"
    "        raise ImportError(f'fora da biblioteca padrão: {nome}')\n"
    "sys.meta_path.insert(0, _Recusa())\n"
    "script = sys.argv[1]\n"
    "sys.argv = sys.argv[1:]\n"
    "sys.path.insert(0, os.path.dirname(script))\n"
    "runpy.run_path(script, run_name='__main__')\n"
)


@pytest.mark.parametrize("pasta_pedida", [True, False], ids=["pasta-pedida", "pasta-padrao"])
def test_o_desfazer_roda_com_o_python_do_sistema(tmp_path: Path, pasta_pedida: bool) -> None:
    """Depois de a `.venv` sair, o uninstall o roda com o `python3` do sistema"""
    py = shutil.which("python3", path=SISTEMA)
    if py is None:
        pytest.skip("sem python3 no sistema")
    lar = tmp_path / "lar"
    lar.mkdir()
    _instalar_flatpak(lar, MGBA)
    heroic = _heroic(lar, nativo=False)
    mgba = lar / ".local/share/flatpak/overrides" / MGBA
    pasta = _ambiente(lar / ".local/state" / m.SLUG / "launch_env")
    _curar(lar, pasta)
    recusa = tmp_path / "so_a_biblioteca_padrao.py"
    recusa.write_text(_SO_A_BIBLIOTECA_PADRAO, encoding="utf-8")
    arquivo = RAIZ / "src/hefesto_dualsense4unix/integrations/cura_por_estrada.py"
    argv = [py, "-I", str(recusa), str(arquivo), "--desfazer"]
    if pasta_pedida:
        argv += ["--lar", str(lar), "--pasta-do-ambiente", str(pasta)]
    r = subprocess.run(
        argv, env={"HOME": str(lar), "PATH": SISTEMA, "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=60, check=False, cwd=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(heroic.read_text(encoding="utf-8")) == HEROIC_DELA
    assert not mgba.exists()
    assert not cura.caminho_do_registro(pasta).exists()
    assert "tirei" in r.stdout


_REAIS = ("cat", "grep", "sed", "awk", "head", "tail", "ls", "date", "id", "uname",
          "dirname", "basename", "sort", "uniq", "tr", "cut", "wc", "readlink",
          "realpath", "stat", "mktemp", "env", "true", "false", "diff", "cmp",
          "timeout", "printf", "echo", "test", "expr")
_GUARDADOS = ("rm", "rmdir", "mv", "cp", "mkdir", "ln", "chmod", "chown", "touch",
              "install", "tee", "find")
_DUBLES = {
    "sudo": "exit 1",
    "systemctl": 'case "$*" in *is-active*|*is-enabled*|*is-failed*) exit 1;; esac; exit 0',
    **dict.fromkeys((
        "pkill", "killall", "flatpak", "dkms", "udevadm", "apt-get", "apt",
        "gtk-update-icon-cache", "update-desktop-database", "gpasswd", "groupdel",
        "bash", "sh", "sleep", "bluetoothctl", "nmcli", "gsettings", "dconf",
        "modprobe", "depmod"), "exit 0"),
    "busctl": "exit 1", "dpkg": "exit 1", "btmgmt": "exit 1",
}
_PY_QUE_RODAM = ("proton_pin.py", "steam_launch_options.py", "cura_por_estrada.py")

NADA_RODANDO: dict[int, str] = {}


def _montar_o_path(raiz: Path, diario: Path,
                   processos: dict[int, str] | None = None) -> Path:
    binp = raiz / "bin"
    binp.mkdir()
    for nome in _REAIS:
        real = shutil.which(nome, path=SISTEMA)
        if real:
            (binp / nome).symlink_to(real)
    for nome in _GUARDADOS:
        real = shutil.which(nome, path=SISTEMA)
        assert real, f"sem {nome} no sistema"
        (binp / nome).write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do\n'
            '  case "$a" in\n'
            f'    */../*) printf "RECUSADO %s\\n" "{nome} $*" >> "{diario}"; exit 1;;\n'
            f'    "{raiz}"/*) ;;\n'
            f'    /*) printf "RECUSADO %s\\n" "{nome} $*" >> "{diario}"; exit 1;;\n'
            "  esac\n"
            "done\n"
            f'exec "{real}" "$@"\n', encoding="utf-8")
    for nome, corpo in _DUBLES.items():
        (binp / nome).write_text(
            f'#!/bin/sh\nprintf "%s\\n" "{nome} $*" >> "{diario}"\n{corpo}\n',
            encoding="utf-8")
    real_py = shutil.which("python3", path=SISTEMA)
    assert real_py, "sem python3 no sistema"
    tabela = raiz / "processos.json"
    tabela.write_text(json.dumps(processos or NADA_RODANDO), encoding="utf-8")
    partida = raiz / "py_guardado.py"
    partida.write_text(
        "import builtins, importlib, json, os, re, subprocess, sys\n"
        f"RAIZ = {str(raiz)!r}\n"
        f"DIARIO = {str(diario)!r}\n"
        'if not os.environ["HOME"].startswith(RAIZ + "/"):\n'
        '    sys.exit("guarda: o HOME saiu do lar de mentira")\n'
        "def _recusa(*a, **k):\n"
        '    raise RuntimeError(f"o lar de mentira não abre processo: {a!r}")\n'
        "subprocess.Popen = _recusa\n"
        "os.system = _recusa\n"
        f"PROCESSOS = {{int(k): v for k, v in json.load(open({str(tabela)!r})).items()}}\n"
        "def _leu_a_maquina(caminho):\n"
        '    with open(DIARIO, "a", encoding="utf-8") as d:\n'
        '        d.write(f"RECUSADO leu a tabela de processos da máquina: {caminho}\\n")\n'
        '    raise PermissionError(f"o lar de mentira não lê a tabela da máquina: {caminho}")\n'
        "_listdir, _scandir, _open = os.listdir, os.scandir, builtins.open\n"
        "def _caminho(x):\n"
        "    return os.fsdecode(x) if isinstance(x, (str, bytes, os.PathLike)) else ''\n"
        "def _e_proc(caminho):\n"
        '    return _caminho(caminho).rstrip("/") == "/proc"\n'
        "def _listdir_do_lar(caminho='.'):\n"
        "    return [str(p) for p in PROCESSOS] if _e_proc(caminho) else _listdir(caminho)\n"
        "def _scandir_do_lar(caminho='.'):\n"
        "    return _leu_a_maquina(caminho) if _e_proc(caminho) else _scandir(caminho)\n"
        "def _open_do_lar(arquivo, *a, **k):\n"
        '    if re.match(r"/proc/\\d", _caminho(arquivo)):\n'
        "        _leu_a_maquina(arquivo)\n"
        "    return _open(arquivo, *a, **k)\n"
        "os.listdir, os.scandir, builtins.open = _listdir_do_lar, _scandir_do_lar, _open_do_lar\n"
        "script = sys.argv[1]\n"
        "sys.argv = sys.argv[1:]\n"
        "sys.path.insert(0, os.path.dirname(script))\n"
        "import steam_launch_options as slo\n"
        "def _cmdline_do_lar(pid):\n"
        '    return PROCESSOS.get(int(pid), "")\n'
        "def _steam_do_lar():\n"
        "    return any('steamrt64/steam' in c\n"
        "               or os.path.basename(c.split(' ')[0])[:15] == 'steamwebhelper'\n"
        "               for c in PROCESSOS.values())\n"
        "slo._cmdline_of = slo.cmdline_de_pid = _cmdline_do_lar\n"
        "slo.steam_running = _steam_do_lar\n"
        "slo.stop_steam = _recusa\n"
        "mod = importlib.import_module(os.path.basename(script)[:-3])\n"
        "sys.exit(mod.main())\n", encoding="utf-8")
    casos = "|".join(f"*/{n}" for n in _PY_QUE_RODAM)
    (binp / "python3").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-" ] || { [ "$1" = "-I" ] && [ "$2" = "-c" ]; }; then\n'
        f'  exec "{real_py}" "$@"\nfi\n'
        f'case "$1" in {casos})\n'
        f'  printf "%s\\n" "python3 $*" >> "{diario}"; exec "{real_py}" "{partida}" "$@";;\n'
        "esac\n"
        f'printf "%s\\n" "python3 (anotado) $*" >> "{diario}"\nexit 0\n', encoding="utf-8")
    for arq in binp.iterdir():
        if not arq.is_symlink():
            arq.chmod(arq.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return binp


_TAB = "\t"


def _localconfig() -> str:
    blocos = "".join(
        f'{_TAB * 5}"{a}"\n{_TAB * 5}{{\n{_TAB * 6}"LaunchOptions"{_TAB * 2}'
        f'"VKD3D_CONFIG=dxr %command%"\n{_TAB * 5}}}\n' for a in ("100", "200"))
    return ('"UserLocalConfigStore"\n{\n'
            f'{_TAB}"Software"\n{_TAB}{{\n{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
            f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
            f"{blocos}{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n")


def _config_vdf() -> str:
    return ('"InstallConfigStore"\n{\n'
            f'{_TAB}"Software"\n{_TAB}{{\n{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
            f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n{_TAB * 4}"CompatToolMapping"\n{_TAB * 4}{{\n'
            f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n")


def _instalar_pelos_donos(r: m.Raizes, repo: Path, *, heroic_nativo: bool,
                          com_venv: bool) -> dict[str, Path]:
    """O que o install e o daemon escrevem nesta casa, pelos DONOS do código."""
    lar = r.lar
    steam = lar / ".steam/steam"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    vdf = steam / "userdata/12345/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(slo.apply_wrapper_vdf_text(_localconfig())[0], encoding="utf-8")
    cfg = steam / "config/config.vdf"
    cfg.parent.mkdir(parents=True)
    nome = proton_pin.parse_pin_conf(
        (RAIZ / "assets/proton-pin.conf").read_text(encoding="utf-8"))["name"]
    travado, mudancas = proton_pin.build_compat_tool_mapping(
        _config_vdf(), tool_name=nome, appids=["100", "200"])
    cfg.write_text(travado, encoding="utf-8")
    estado = r.estado / m.SLUG
    estado.mkdir(parents=True)
    (estado / "proton-pin-lock.json").write_text(
        json.dumps({"tool_name": nome, "changes": mudancas}), encoding="utf-8")
    _instalar_flatpak(lar, MGBA)
    heroic, lutris = _heroic(lar, nativo=heroic_nativo), _lutris(lar)
    pasta = _ambiente(estado / "launch_env")
    assert set(_curar(lar, pasta)) == {"heroic", "lutris", "mgba"}
    jogo = _heroic_copia_para_o_jogo(heroic, "Jogo1")
    for nome_do_arquivo, corpo in (
        ("conexao-zumbi.json", '{"links": {}}'), ("lugares-dos-adaptadores.json", "{}"),
        ("wrapper-visto.json", "{}"), ("camadas-vulkan.json", '{"prefixos": {}}'),
        ("radio-diario.jsonl", "{}\n"), ("kernel.log", "boot\n"),
    ):
        (estado / nome_do_arquivo).write_text(corpo, encoding="utf-8")
    (estado / "mesa-de-medicao").mkdir()
    (estado / "mesa-de-medicao/registro.json").write_text("{}", encoding="utf-8")
    no_lar = lar / ".local/state" / m.SLUG
    no_lar.mkdir(parents=True, exist_ok=True)
    (no_lar / "gabinete.json").write_text("{}", encoding="utf-8")
    (no_lar / "teclado-na-tela.conf").write_text("resultado=pulado\n", encoding="utf-8")
    wp_xdg = r.config / "wireplumber/wireplumber.conf.d"
    wp_lar = lar / ".config/wireplumber/wireplumber.conf.d"
    for pasta_wp, nome_wp, corpo_wp in (
        (wp_xdg, "51-hefesto-dualsense-no-default-source.conf",
         "# recriado manualmente apos o uninstall\n"),
        (wp_xdg, "52-hefesto-dualsense-disable-source.conf", "# do Hefesto\n"),
        (wp_xdg, "54-hefesto-dualsense-alto-falante-nunca-dorme.conf", "# do Hefesto\n"),
        (wp_lar, "53-hefesto-dualsense-disable-output.conf", "# do Hefesto\n"),
    ):
        pasta_wp.mkdir(parents=True, exist_ok=True)
        (pasta_wp / nome_wp).write_text(corpo_wp, encoding="utf-8")
    (r.config / m.SLUG / "profiles").mkdir(parents=True)
    (r.config / m.SLUG / "profiles/fallback.json").write_text("{}", encoding="utf-8")
    (r.dados / m.SLUG).mkdir(parents=True, exist_ok=True)
    (r.cache / m.SLUG).mkdir(parents=True, exist_ok=True)
    (r.cache / m.SLUG / "bluez-obra").mkdir()
    for rel in (".config/systemd/user/hefesto-dualsense4unix.service",
                ".config/autostart/hefesto-dualsense4unix-tray.desktop",
                ".local/share/applications/hefesto-dualsense4unix.desktop",
                ".local/share/hefesto-dualsense4unix/bin/hefesto-launch",
                ".local/bin/hefesto-dualsense4unix-gui"):
        (lar / rel).parent.mkdir(parents=True, exist_ok=True)
        (lar / rel).write_text("# do install\n", encoding="utf-8")
    venv_bin = repo / ".venv/bin/hefesto-dualsense4unix"
    if com_venv:
        venv_bin.parent.mkdir(parents=True)
        venv_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    (lar / ".local/bin/hefesto-dualsense4unix").symlink_to(venv_bin)
    return {"heroic": heroic, "lutris": lutris, "jogo": jogo,
            "mgba": lar / ".local/share/flatpak/overrides" / MGBA}


def _casa_de_mentira(tmp_path: Path, *, xdg_fora: bool) -> tuple[m.Raizes, Path]:
    lar = tmp_path / "lar"
    base = tmp_path / "xdg" if xdg_fora else None
    r = m.Raizes(
        lar=lar,
        config=base / "config" if base else lar / ".config",
        estado=base / "state" if base else lar / ".local/state",
        dados=base / "data" if base else lar / ".local/share",
        cache=base / "cache" if base else lar / ".cache",
        execucao=tmp_path / "run",
        bluez=tmp_path / "var/lib/bluetooth",
        varlib=tmp_path / "var/lib/hefesto-dualsense4unix",
        guardado_do_root=tmp_path / "var/lib/hefesto-memoria-guardada",
        sistema=tmp_path / "sistema",
        repositorio=RAIZ,
    )
    for pasta in (lar, r.config, r.estado, r.dados, r.cache, r.execucao):
        pasta.mkdir(parents=True, exist_ok=True)
    r.execucao.chmod(0o700)
    repo = tmp_path / "repo"
    repo.mkdir()
    for nome in ("src", "scripts", "assets"):
        (repo / nome).symlink_to(RAIZ / nome)
    return r, repo


def _desinstalar(tmp_path: Path, r: m.Raizes, repo: Path, texto: str, *, xdg_fora: bool,
                 flags: str = "--purge-config --yes",
                 processos: dict[int, str] | None = None,
                 ) -> tuple[subprocess.CompletedProcess[str], str]:
    """Roda o uninstall — por uma GUARDA que sai antes se o lar vazar."""
    (repo / "uninstall.sh").write_text(texto, encoding="utf-8")
    diario = tmp_path / "diario.log"
    binp = _montar_o_path(tmp_path, diario, processos)
    (tmp_path / "tmp").mkdir()
    (tmp_path / "sys-bluetooth").mkdir()
    env = {"HOME": str(r.lar), "XDG_RUNTIME_DIR": str(r.execucao), "PATH": str(binp),
           "LANG": "C.UTF-8", "TMPDIR": str(tmp_path / "tmp"),
           "PYTHONDONTWRITEBYTECODE": "1",
           "HEFESTO_SYSFS_BLUETOOTH": str(tmp_path / "sys-bluetooth")}
    if xdg_fora:
        env.update({"XDG_CONFIG_HOME": str(r.config), "XDG_STATE_HOME": str(r.estado),
                    "XDG_DATA_HOME": str(r.dados), "XDG_CACHE_HOME": str(r.cache)})
    casa_de_verdade = pwd.getpwuid(os.getuid()).pw_dir
    guarda = tmp_path / "guarda.sh"
    guarda.write_text(
        "#!/bin/bash\n"
        f'raiz="{tmp_path}"\nreal="{casa_de_verdade}"\n'
        "for v in HOME XDG_CONFIG_HOME XDG_STATE_HOME XDG_DATA_HOME XDG_CACHE_HOME "
        "XDG_RUNTIME_DIR TMPDIR; do\n"
        '  val="${!v:-}"; [[ -z "$val" ]] && continue\n'
        '  case "$val" in "$raiz"/*) ;; *) echo "guarda: $v=$val fora do lar" >&2; exit 97;; esac\n'
        '  case "$val" in "$real"|"$real"/*)\n'
        '    echo "guarda: $v é a casa de verdade" >&2; exit 97;;\n'
        "  esac\n"
        "done\n"
        '[[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && { echo "guarda: barramento" >&2; exit 97; }\n'
        f'exec /bin/bash "{repo / "uninstall.sh"}" {flags}\n', encoding="utf-8")
    r_ = subprocess.run(["/bin/bash", str(guarda)], env=env, capture_output=True, text=True,
                        timeout=300, check=False, cwd=str(tmp_path))
    assert r_.returncode != 97, f"a guarda do lar de mentira saiu:\n{r_.stderr}"
    return r_, diario.read_text(encoding="utf-8") if diario.exists() else ""


def _defeitos(r: m.Raizes, tmp_path: Path) -> list[str]:
    return sorted(f"{x.onde.replace(str(tmp_path), '')} — {x.o_que}"
                  for x in m.conferir_a_casa(r) if not x.de_proposito and not x.nao_sei)


def _limpa(r: m.Raizes, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """O INSTRUMENTO de verdade: `guardar-e-devolver-a-casa.py limpa`, com o"""
    py = shutil.which("python3", path=SISTEMA)
    assert py, "sem python3 no sistema"
    env = {"HOME": str(r.lar), "XDG_CONFIG_HOME": str(r.config),
           "XDG_STATE_HOME": str(r.estado), "XDG_DATA_HOME": str(r.dados),
           "XDG_CACHE_HOME": str(r.cache), "XDG_RUNTIME_DIR": str(r.execucao),
           "HEFESTO_MEMORIA_BLUEZ": str(r.bluez), "HEFESTO_MEMORIA_VARLIB": str(r.varlib),
           "HEFESTO_MEMORIA_GUARDADO_ROOT": str(r.guardado_do_root),
           "HEFESTO_MEMORIA_SISTEMA": str(r.sistema), m.ENV_ENSAIO: "1",
           "PATH": SISTEMA, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [py, "-I", str(RAIZ / "scripts/guardar-e-devolver-a-casa.py"), "limpa"],
        env=env, capture_output=True, text=True, timeout=120, check=False,
        cwd=str(tmp_path))


@pytest.mark.parametrize(
    ("xdg_fora", "heroic_nativo", "com_venv"),
    [(False, False, True), (True, True, False)],
    ids=["lar-heroic-flatpak", "xdg-fora-do-lar-heroic-nativo-sem-venv"])
def test_o_uninstall_de_verdade_nao_deixa_rastro(
    tmp_path: Path, xdg_fora: bool, heroic_nativo: bool, com_venv: bool
) -> None:
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=xdg_fora)
    alvos = _instalar_pelos_donos(r, repo, heroic_nativo=heroic_nativo, com_venv=com_venv)
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in _opcoes(alvos["heroic"])

    rodou, diario = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                                 xdg_fora=xdg_fora)

    assert rodou.returncode == 0, rodou.stdout[-3000:] + rodou.stderr[-3000:]
    assert "RECUSADO" not in diario, (
        "o uninstall tentou mexer fora do lar sem sudo:\n"
        + "\n".join(x for x in diario.splitlines() if x.startswith("RECUSADO")))
    defeitos = _defeitos(r, tmp_path)
    assert not defeitos, "o «limpa?» achou rastro do Hefesto:\n" + "\n".join(defeitos)
    limpa = _limpa(r, tmp_path)
    assert limpa.returncode == 0, limpa.stdout + limpa.stderr
    assert json.loads(alvos["heroic"].read_text(encoding="utf-8")) == HEROIC_DELA, (
        "o Heroic dela não voltou a ser o dela")
    no_jogo = {k for k, _ in _lista_do_jogo(alvos["jogo"])}
    assert not no_jogo & cura._DO_PRODUTO_SEM_REGISTRO, (
        f"o jogo com opção própria no Heroic ficou com o ambiente do Hefesto: {no_jogo}")
    assert alvos["lutris"].read_text(encoding="utf-8") == LUTRIS_DELA
    assert not alvos["mgba"].exists()
    for estado in {r.estado / m.SLUG, r.lar / ".local/state" / m.SLUG}:
        assert not estado.exists(), f"a pasta de estado ficou: {sorted(os.listdir(estado))}"
    wps = {p.name for casa in {r.config, r.lar / ".config"}
           for p in (casa / "wireplumber/wireplumber.conf.d").glob("*hefesto*")}
    assert wps == {"51-hefesto-dualsense-no-default-source.conf"}, wps
    assert list(r.config.glob(f"{m.SLUG}.backup-*/*/mesa-de-medicao/registro.json")), (
        "o que nenhum passo nomeia tem de ir para o backup, e não sumir sem rede")


def test_a_mordida_sem_o_passo_dos_lancadores_o_limpa_acusa(tmp_path: Path) -> None:
    """A mordida da sprint, como teste: o MESMO uninstall sem o passo dos"""
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.index("# O AMBIENTE NOS OUTROS LANÇADORES")
    fim = texto.index("# PLAT-01: destrava o CompatToolMapping")
    sem_a_cura = texto[:inicio] + "_estradas_desfeitas=1\n\n" + texto[fim:]
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)

    rodou, _ = _desinstalar(tmp_path, r, repo, sem_a_cura, xdg_fora=False)

    assert rodou.returncode == 0, rodou.stderr[-3000:]
    defeitos = " ".join(_defeitos(r, tmp_path))
    assert "heroic/config.json" in defeitos, defeitos
    assert f"overrides/{LUTRIS}" in defeitos and f"overrides/{MGBA}" in defeitos, defeitos
    limpa = _limpa(r, tmp_path)
    assert limpa.returncode == 1, limpa.stdout + limpa.stderr
    assert "SOBROU" in limpa.stdout and "heroic/config.json" in limpa.stdout


def test_sem_purge_fica_so_o_historico_e_o_uninstall_diz(tmp_path: Path) -> None:
    """Sem `--purge-config`, o histórico fica de propósito (o kernel.log e o"""
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    alvos = _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)

    rodou, _ = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                            xdg_fora=False, flags="--yes")

    assert rodou.returncode == 0, rodou.stderr[-3000:]
    estado = r.estado / m.SLUG
    ficou = sorted(p.name for p in estado.iterdir())
    assert "conexao-zumbi.json" not in ficou, ficou
    assert "kernel.log" in ficou
    assert [n for n in ficou if n.startswith("radio-diario.pre-uninstall-")], ficou
    historico = {"kernel.log"} | {n for n in ficou if n.startswith("radio-diario.pre-")}
    assert set(ficou) <= historico | {"mesa-de-medicao"}, (
        f"sem --purge-config, só o histórico (e o que ninguém nomeia) fica: {ficou}")
    assert f"a pasta de estado {estado} fica, com:" in rodou.stdout
    assert "mesa-de-medicao" in rodou.stdout
    assert json.loads(alvos["heroic"].read_text(encoding="utf-8")) == HEROIC_DELA
    assert not alvos["mgba"].exists()


def test_o_desfazer_adiado_termina_depois_e_a_casa_fica_limpa(tmp_path: Path) -> None:
    """O caminho do ADIADO, de ponta a ponta: o `config.json` do Heroic não"""
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    alvos = _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)
    inteiro = alvos["heroic"].read_text(encoding="utf-8")
    alvos["heroic"].write_text(inteiro[: len(inteiro) // 2], encoding="utf-8")

    rodou, _ = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                            xdg_fora=False)

    assert rodou.returncode == 0, rodou.stderr[-3000:]
    assert "ADIADO" in rodou.stdout
    estado = r.estado / m.SLUG
    assert sorted(os.listdir(estado)) == ["launch_env"], sorted(os.listdir(estado))
    assert sorted(os.listdir(estado / "launch_env")) == ["estradas.json"]
    assert alvos["lutris"].read_text(encoding="utf-8") == LUTRIS_DELA, (
        "o arquivo que não abriu segurou o desfazer dos outros lançadores")
    assert _limpa(r, tmp_path).returncode == 1, "o «limpa?» não viu o desfazer pendente"

    alvos["heroic"].write_text(inteiro, encoding="utf-8")
    py = shutil.which("python3", path=SISTEMA)
    assert py, "sem python3 no sistema"
    depois = subprocess.run(
        [py, "-I", str(RAIZ / "src/hefesto_dualsense4unix/integrations/cura_por_estrada.py"),
         "--desfazer"],
        env={"HOME": str(r.lar), "PATH": SISTEMA, "LANG": "C.UTF-8",
             "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=60, check=False, cwd=str(tmp_path))

    assert depois.returncode == 0, depois.stdout + depois.stderr
    assert json.loads(alvos["heroic"].read_text(encoding="utf-8")) == HEROIC_DELA, (
        "o desfazer de depois não sabia mais o que era nosso: o registro se perdeu")
    assert not estado.exists(), f"a pasta de estado ficou: {sorted(os.listdir(estado))}"
    limpa = _limpa(r, tmp_path)
    assert limpa.returncode == 0, limpa.stdout + limpa.stderr


UM_JOGO_ABERTO: dict[int, str] = {
    4242: "/lar/.local/share/Steam/ubuntu12_64/steamrt64/steam -silent",
    4243: "reaper SteamLaunch AppId=100 -- /lar/jogo/jogo.exe",
}


def test_o_uninstall_le_a_tabela_de_processos_do_lar(tmp_path: Path) -> None:
    """Os testes do uninstall não dependem do que roda na máquina."""
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)

    rodou, diario = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                                 xdg_fora=False, processos=UM_JOGO_ABERTO)

    assert rodou.returncode == 0, rodou.stdout[-3000:] + rodou.stderr[-3000:]
    assert "RECUSADO" not in diario, (
        "o uninstall do lar leu fora do lar:\n"
        + "\n".join(x for x in diario.splitlines() if x.startswith("RECUSADO")))
    assert "JOGO da Steam em execução" in rodou.stdout, (
        "o atalho da Steam saiu com um jogo aberto na tabela do lar: a detecção "
        "não leu a tabela do lar\n" + rodou.stdout[-3000:])
    defeitos = " ".join(_defeitos(r, tmp_path))
    assert "localconfig.vdf" in defeitos, (
        f"com o jogo aberto o atalho da Steam fica, e o «limpa?» o acusa: {defeitos}")


SO_A_STEAM: dict[int, str] = {
    4244: "/lar/.local/share/Steam/ubuntu12_64/steamwebhelper --type=renderer",
}


def test_o_uninstall_ve_a_steam_aberta_na_tabela_do_lar(tmp_path: Path) -> None:
    """O segundo leitor da tabela, o `steam_running`, também pergunta ao lar."""
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)

    rodou, diario = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                                 xdg_fora=False, processos=SO_A_STEAM)

    assert rodou.returncode == 0, rodou.stdout[-3000:] + rodou.stderr[-3000:]
    assert "RECUSADO" not in diario, (
        "o uninstall do lar leu fora do lar:\n"
        + "\n".join(x for x in diario.splitlines() if x.startswith("RECUSADO")))
    assert "ADIADO: feche a Steam" in rodou.stdout, (
        "a Steam aberta na tabela do lar não adiou o destravamento do Proton: o "
        "`steam_running` não leu a tabela do lar\n" + rodou.stdout[-3000:])
    assert "JOGO da Steam em execução" not in rodou.stdout, rodou.stdout[-3000:]


def test_o_zumbi_sai_das_duas_casas_sem_purge(tmp_path: Path) -> None:
    """O daemon grava o `conexao-zumbi.json` pelo XDG do AMBIENTE DELE (a unit"""
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=True)
    _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)
    no_lar = r.lar / ".local/state" / m.SLUG
    (no_lar / "conexao-zumbi.json").write_text('{"links": {}}', encoding="utf-8")

    rodou, _ = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                            xdg_fora=True, flags="--yes")

    assert rodou.returncode == 0, rodou.stderr[-3000:]
    for estado in (r.estado / m.SLUG, no_lar):
        assert not (estado / "conexao-zumbi.json").exists(), estado
