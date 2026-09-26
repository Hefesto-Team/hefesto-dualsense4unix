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

#: O `default.env` do daemon com a emulação ligada — os pares VID/PID são de
#: aparelho (Sony, Valve), não endereço de rádio.
AMBIENTE_EMULADO = (
    "# Materializado pelo daemon do Hefesto\n"
    "PROTON_DISABLE_HIDRAW=0x054C/0x0CE6\n"
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x28de/0x11ff\n"
    "__GL_SHADER_DISK_CACHE=1\n__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1\n"
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0\nSDL_ACCELEROMETER_AS_JOYSTICK=0\n"
)
#: O do Modo Nativo: sem `IGNORE` nem `DISABLE_HIDRAW` (`launch_env.env_do_modo`).
AMBIENTE_NATIVO = (
    "# Materializado pelo daemon do Hefesto\n"
    "__GL_SHADER_DISK_CACHE=1\n__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1\n"
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0\nSDL_ACCELEROMETER_AS_JOYSTICK=0\n"
)

#: O que ela tem no Heroic antes do Hefesto: o `MANGOHUD` e um cache de shader
#: DESLIGADO — uma das duas variáveis que o Hefesto também escreve.
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
#: O override do Lutris que ela deu à mão — a caixa aberta, nada de ambiente.
LUTRIS_DELA = "[Context]\ndevices=all;\nfilesystems=host;\n"


# ─── o lar de mentira dos donos ───────────────────────────────────────────


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
    """O que o Heroic faz quando ela muda uma opção de um jogo — pelo fonte dele.

    `GameConfigV0.getSettings` monta `{...globais, ...do jogo}` com
    `enviromentOptions: [...enviromentOptions]` (a CÓPIA da lista global), e o
    `setSetting` grava tudo em `GamesConfig/<jogo>.json` com
    `JSON.stringify(config, null, 2)`. `dela` são as que ela pôs só naquele
    jogo, depois da cópia.
    """
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


# ─── 1. o dono de «o que é nosso» ─────────────────────────────────────────


@pytest.mark.parametrize("nativo", [False, True], ids=["heroic-flatpak", "heroic-nativo"])
def test_o_desfazer_tira_so_o_que_e_nosso_e_devolve_o_que_era_dela(
    tmp_path: Path, nativo: bool
) -> None:
    """A MORDIDA: faça `_devolver_chaves` ignorar o `antes` e o cache de shader
    dela (`0`) não volta; troque o `nossos` por «qualquer valor» e o teste do
    valor mudado depois (logo abaixo) reprova."""
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
    """A escrita põe o nosso por cima do dela, NA MESMA POSIÇÃO; o desfazer o
    devolve ali. O `HEROIC_DELA` tem o cache de shader por ÚLTIMO, e por isso
    não via a ordem — aqui ele vem PRIMEIRO, antes do `MANGOHUD`.

    A MORDIDA: devolva o «antes» com `pares.append` (no fim da lista), como
    era, e o `config.json` dela volta com a ordem trocada.
    """
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
            item["value"] = "0x045e/0x028e"  # ela mudou à mão, depois
    mesa["heroic"].write_text(json.dumps(dado, indent=2), encoding="utf-8")

    feitos, _ = cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    opcoes = _opcoes(mesa["heroic"])
    assert opcoes.get("PROTON_DISABLE_HIDRAW") == "0x045e/0x028e", (
        "o desfazer tirou um valor que ela escreveu depois do Hefesto")
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in opcoes
    assert any("ficaram as que você mudou" in cura.frase_do_desfeito(f) for f in feitos)


def test_a_chave_nossa_que_sai_do_ambiente_sai_do_arquivo(mesa: dict[str, Path]) -> None:
    """O Modo Nativo não tem `IGNORE` nem `DISABLE_HIDRAW` — todo modo, toda
    estrada. Antes, a escrita FUNDIA e nunca tirava: o `IGNORE` da emulação
    ficava congelado no Heroic, e o jogo do Modo Nativo abria sem o controle.

    A MORDIDA: tire de `_tomar` a chamada a `_devolver_chaves` e o `IGNORE`
    fica nos dois arquivos.
    """
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
    """A instalação de antes do registro escreveu sem anotar (o escritor de
    09/09 e a carona de 21/09). As variáveis que só o produto usa saem; as
    duas que podem ser dela ficam — o «limpa?» também não as conta."""
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
    """A primeira escrita com registro acha um `IGNORE` de uma versão que
    escrevia sem anotar — com OUTRO valor (a lista de aparelhos cresceu). Ele é
    presumido do produto: devolvê-lo no desfazer deixaria o jogo sem controle.

    A MORDIDA: guarde o «antes» de toda chave em `_tomar` (e não só das que
    podem ser dela) e o `IGNORE` velho volta ao Heroic depois do uninstall.
    """
    cura._escrever_no_heroic(
        mesa["heroic"], {"SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054c/0x0ce6"})
    _curar(mesa["lar"], mesa["pasta"])

    cura.desfazer_as_estradas([mesa["pasta"]], mesa["lar"])

    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in _opcoes(mesa["heroic"])


def test_arquivo_que_nao_abre_nao_e_reescrito_e_o_registro_fica(
    mesa: dict[str, Path]
) -> None:
    """Um `config.json` truncado pode ser o Heroic que morreu no meio de um
    `write`: reescrevê-lo jogaria fora a biblioteca dela. O desfazer não toca,
    diz, e o registro fica para o desfazer de depois."""
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
    """Uma cópia truncada que CITA uma variável nossa pode estar com ela: o
    desfazer não reescreve, diz, e o registro da casa fica para depois. Uma
    que não cita nada nosso não é conosco e não segura nada."""
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


#: As variáveis que a `ENV_ALLOWLIST` ganhar DEPOIS de 25/09/2026 nascem com
#: registro e não entram no conjunto histórico — anote-as aqui, não lá.
NASCIDAS_DEPOIS_DO_REGISTRO: frozenset[str] = frozenset()


def test_os_espelhos_do_desfazer() -> None:
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST

    allowlist = set(ENV_ALLOWLIST)
    assert cura.PODEM_SER_DELA == m._VARIAVEIS_QUE_PODEM_SER_DELA
    assert allowlist >= cura.PODEM_SER_DELA
    assert not cura._DO_PRODUTO_SEM_REGISTRO & cura.PODEM_SER_DELA
    historico = allowlist - cura.PODEM_SER_DELA - NASCIDAS_DEPOIS_DO_REGISTRO
    assert historico == cura._DO_PRODUTO_SEM_REGISTRO
    assert cura._PASTA_DOS_OVERRIDES == m.PASTA_DOS_OVERRIDES
    assert cura._PASTAS_DO_HEROIC == m.PASTAS_DO_HEROIC


def test_o_desfazer_roda_com_o_python_do_sistema(mesa: dict[str, Path], tmp_path: Path) -> None:
    """Depois de a `.venv` sair, o uninstall o roda com o `python3` do sistema
    (`-I`: nem PYTHONPATH, nem o site do usuário) — o pacote se acha pelo
    caminho do arquivo, e a corrente do desfazer é só biblioteca padrão."""
    py = shutil.which("python3", path=SISTEMA)
    if py is None:
        pytest.skip("sem python3 no sistema")
    _curar(mesa["lar"], mesa["pasta"])
    arquivo = RAIZ / "src/hefesto_dualsense4unix/integrations/cura_por_estrada.py"
    r = subprocess.run(
        [py, "-I", str(arquivo), "--desfazer", "--lar", str(mesa["lar"]),
         "--pasta-do-ambiente", str(mesa["pasta"])],
        env={"HOME": str(mesa["lar"]), "PATH": SISTEMA, "LANG": "C.UTF-8",
             "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=60, check=False, cwd=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(mesa["heroic"].read_text(encoding="utf-8")) == HEROIC_DELA
    assert not mesa["mgba"].exists()
    assert "tirei" in r.stdout


# ─── 2. o uninstall.sh de verdade, num lar de mentira ────────────────────

#: Leem, e só leem: o PATH de mentira os aponta para os de verdade.
_REAIS = ("cat", "grep", "sed", "awk", "head", "tail", "ls", "date", "id", "uname",
          "dirname", "basename", "sort", "uniq", "tr", "cut", "wc", "readlink",
          "realpath", "stat", "mktemp", "env", "true", "false", "diff", "cmp",
          "timeout", "printf", "echo", "test", "expr")
#: Mexem em arquivo: RECUSAM qualquer caminho fora do lar de mentira.
_GUARDADOS = ("rm", "rmdir", "mv", "cp", "mkdir", "ln", "chmod", "chown", "touch",
              "install", "tee", "find")
#: Mudam a máquina: anotam e não fazem nada (o `sudo` responde «sem privilégio»).
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
#: Os `.py` que o uninstall roda e que rodam de verdade aqui — com a Steam do
#: lar FECHADA (a detecção olharia os processos da máquina) e sem poder abrir
#: processo nenhum. Os demais (camadas, device KS) só são anotados.
_PY_QUE_RODAM = ("proton_pin.py", "steam_launch_options.py", "cura_por_estrada.py")


def _montar_o_path(raiz: Path, diario: Path) -> Path:
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
    partida = raiz / "py_guardado.py"
    partida.write_text(
        "import importlib, os, subprocess, sys\n"
        f"RAIZ = {str(raiz)!r}\n"
        'if not os.environ["HOME"].startswith(RAIZ + "/"):\n'
        '    sys.exit("guarda: o HOME saiu do lar de mentira")\n'
        "def _recusa(*a, **k):\n"
        '    raise RuntimeError(f"o lar de mentira não abre processo: {a!r}")\n'
        "subprocess.Popen = _recusa\n"
        "os.system = _recusa\n"
        "script = sys.argv[1]\n"
        "sys.argv = sys.argv[1:]\n"
        "sys.path.insert(0, os.path.dirname(script))\n"
        "import steam_launch_options as slo\n"
        "slo.steam_running = lambda: False\n"
        "slo.stop_steam = _recusa\n"
        "mod = importlib.import_module(os.path.basename(script)[:-3])\n"
        'if hasattr(mod, "steam_running"):\n'
        "    mod.steam_running = lambda: False\n"
        'if hasattr(mod, "_steam_gate"):\n'
        "    mod._steam_gate = lambda *a, **k: None\n"
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
    # Os lançadores dela, e a carona do daemon com o default.env dele.
    _instalar_flatpak(lar, MGBA)
    heroic, lutris = _heroic(lar, nativo=heroic_nativo), _lutris(lar)
    pasta = _ambiente(estado / "launch_env")
    assert set(_curar(lar, pasta)) == {"heroic", "lutris", "mgba"}
    # O jogo em que ela mudou uma opção: o Heroic copia a lista global para ele.
    jogo = _heroic_copia_para_o_jogo(heroic, "Jogo1")
    # O estado do daemon (pelo XDG) e o que o install grava no lar (sem ele).
    for nome_do_arquivo, corpo in (
        ("conexao-zumbi.json", '{"links": {}}'), ("lugares-dos-adaptadores.json", "{}"),
        ("wrapper-visto.json", "{}"), ("camadas-vulkan.json", '{"prefixos": {}}'),
        ("radio-diario.jsonl", "{}\n"), ("kernel.log", "boot\n"),
    ):
        (estado / nome_do_arquivo).write_text(corpo, encoding="utf-8")
    # Um que nenhum passo do uninstall nomeia (o registro da mesa de medição,
    # `scripts/mesa_de_medicao.py`): com --purge-config ele vai para o backup.
    (estado / "mesa-de-medicao").mkdir()
    (estado / "mesa-de-medicao/registro.json").write_text("{}", encoding="utf-8")
    no_lar = lar / ".local/state" / m.SLUG
    no_lar.mkdir(parents=True, exist_ok=True)
    (no_lar / "gabinete.json").write_text("{}", encoding="utf-8")
    (no_lar / "teclado-na-tela.conf").write_text("resultado=pulado\n", encoding="utf-8")
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
    # O symlink do comando aponta para a `.venv` (install.sh, passo 5); sem
    # ela — um uninstall que roda de novo —, ele fica pendurado.
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
                 ) -> tuple[subprocess.CompletedProcess[str], str]:
    """Roda o uninstall — por uma GUARDA que sai antes se o lar vazar."""
    (repo / "uninstall.sh").write_text(texto, encoding="utf-8")
    diario = tmp_path / "diario.log"
    binp = _montar_o_path(tmp_path, diario)
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
    """O INSTRUMENTO de verdade: `guardar-e-devolver-a-casa.py limpa`, com o
    `python3` do sistema (é assim que ela o roda depois do uninstall) e a
    guarda de ensaio da ESQUECER ligada — ela RECUSA se uma raiz for a real."""
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
    assert list(r.config.glob(f"{m.SLUG}.backup-*/*/mesa-de-medicao/registro.json")), (
        "o que nenhum passo nomeia tem de ir para o backup, e não sumir sem rede")


def test_a_mordida_sem_o_passo_dos_lancadores_o_limpa_acusa(tmp_path: Path) -> None:
    """A mordida da sprint, como teste: o MESMO uninstall sem o passo dos
    lançadores deixa o ambiente no Heroic e nos dois overrides, e o «limpa?»
    acusa os três. Se este teste passar sem o passo, o de cima não mede nada."""
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
    """Sem `--purge-config`, o histórico fica de propósito (o kernel.log e o
    diário guardado, decisão de 23/09) — e SÓ ele: o `conexao-zumbi.json` é
    estado, como o dos lugares. E o `rmdir` que falhava calado passa a dizer o
    que ficou.

    A MORDIDA: tire o `rm` do `conexao-zumbi.json` no bloco do rádio e ele fica
    ao lado do histórico.
    """
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
    # O que nenhum passo nomeia (a mesa de medição) também fica sem
    # --purge-config — e é DITO, que é o que o `rmdir` calado não fazia.
    assert set(ficou) <= historico | {"mesa-de-medicao"}, (
        f"sem --purge-config, só o histórico (e o que ninguém nomeia) fica: {ficou}")
    assert f"a pasta de estado {estado} fica, com:" in rodou.stdout
    assert "mesa-de-medicao" in rodou.stdout
    # Os lançadores saem com ou sem --purge-config: não são configuração do Hefesto.
    assert json.loads(alvos["heroic"].read_text(encoding="utf-8")) == HEROIC_DELA
    assert not alvos["mgba"].exists()
