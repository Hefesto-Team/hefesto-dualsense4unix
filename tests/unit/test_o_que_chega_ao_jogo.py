"""O «Corrigir Vulkan» age onde a camada carrega — O-ENGASGO-SE-CURA-PELO-QUE-CHEGA-AO-JOGO-01.

Ela, em 27/09: *«ou seja não resolveu e meteu uma placa falando que não
presta.»* E a decisão dela:
*«Nao sai. Passa a funcionar do jeito certo.»* <!-- noqa-acento: citação literal dela -->

Até 28/09 o botão e o gancho do lançador mexiam só no registro do prefixo
Wine, que nenhum jogo desta máquina lê: o `vulkan-1` do Wine devolve zero
camadas. O que chega ao jogo são as camadas do LADO LINUX, e as duas da Steam
(a sobreposição e o gravador de shaders) saem pelo ambiente que o lançador
entrega ao jogo. Esta régua roda o lançador DE VERDADE, num lar de mentira,
com o comando final sendo o `env` — o que ele imprime é o ambiente do jogo.

AS MORDIDAS:

- tire as duas linhas `DISABLE_VK_LAYER_VALVE_*` do `case` de
  `camadas_da_steam_fora` em `assets/hefesto-launch.sh` e
  `test_com_o_botao_ligado_o_jogo_recebe_as_duas` reprova;
- tire o `traz_o_carregador_da_khronos` do modo `--prefixo` de
  `integrations/camadas_vulkan.py` e
  `test_o_registro_nao_se_mexe_sem_o_carregador_da_khronos` reprova.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "assets" / "hefesto-launch.sh"
FONTE_DO_CURADOR = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "camadas_vulkan.py"

EPIC = r"C:\Program Files (x86)\Epic Games\EOSOverlayVkLayer-Win64.json"
DRIVER = '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000'


def _registro(valor: str = "00000000") -> str:
    """Um `system.reg` com o driver do Wine e UMA camada de terceiro."""
    return "\n".join([
        "WINE REGISTRY Version 2",
        ";; All keys relative to REGISTRY\\\\Machine",
        "",
        "[Software\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238072",
        DRIVER,
        "",
        "[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
        f'"{cv._escapar(EPIC)}"=dword:{valor}',
        "",
    ])


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    """O lar de mentira: casa, config, estado e o PATH sem o Game Mode.

    `system76-power`, `busctl` e `dbus-send` mudos na frente do PATH: o
    lançador pede o perfil de energia a quem responder, e a régua não pode
    falar com o daemon de energia da máquina de quem a roda.
    """
    casa = tmp_path / "casa"
    (casa / ".config").mkdir(parents=True)
    mudos = tmp_path / "mudos"
    mudos.mkdir()
    for nome in ("system76-power", "busctl", "dbus-send"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    return tmp_path


def _config(lar: Path) -> Path:
    return lar / "casa" / ".config"


def _instalar_o_curador(lar: Path) -> None:
    """O que o `install.sh` monta: o curador avulso, executável, no lar."""
    alvo = lar / "casa" / ".local" / "share" / "hefesto-dualsense4unix" / "bin" / "hefesto-camadas"
    alvo.parent.mkdir(parents=True)
    alvo.write_bytes(FONTE_DO_CURADOR.read_bytes())
    alvo.chmod(0o755)


def _lancar(lar: Path, **extra: str) -> dict[str, str]:
    """Roda o lançador com o `env` como jogo; devolve o ambiente que o jogo viu."""
    ambiente = {
        "HOME": str(lar / "casa"),
        "XDG_CONFIG_HOME": str(_config(lar)),
        "XDG_STATE_HOME": str(lar / "estado"),
        "XDG_RUNTIME_DIR": str(lar / "runtime"),
        "PATH": f"{lar / 'mudos'}:/usr/bin:/bin",
        # O que a Steam põe no jogo, medido no `environ` do PRAGMATA em 28/09.
        "ENABLE_VK_LAYER_VALVE_steam_overlay_1": "1",
        "ENABLE_VK_LAYER_VALVE_steam_fossilize_1": "1",
        **extra,
    }
    saida = subprocess.run(
        ["sh", str(LANCADOR), "/usr/bin/env"],
        env=ambiente, capture_output=True, text=True, timeout=60, check=False,
    )
    assert saida.returncode == 0, saida.stderr
    visto: dict[str, str] = {}
    for linha in saida.stdout.splitlines():
        chave, _, valor = linha.partition("=")
        visto[chave] = valor
    return visto


def _as_da_steam(visto: dict[str, str]) -> set[str]:
    return {f"{k}={v}" for k, v in visto.items() if k.startswith("DISABLE_VK_LAYER_VALVE_")}


# ---------------------------------------------------------------------------
# 1. O AMBIENTE QUE O LANÇADOR ENTREGA AO JOGO
# ---------------------------------------------------------------------------


def test_com_o_botao_ligado_o_jogo_recebe_as_duas(lar: Path) -> None:
    """Ligado pelo dono, o jogo nasce com as duas `DISABLE_…_1=1` — sem daemon.

    O lar não tem daemon nenhum: a escolha é dela sobre o jogo, e não pode
    depender de o serviço estar de pé.
    """
    cv.gravar_camadas_da_steam_fora(True, config_home=_config(lar))
    visto = _lancar(lar, SteamAppId="1599660")
    assert _as_da_steam(visto) == set(cv.AMBIENTE_SEM_AS_CAMADAS_DA_STEAM), (
        "o botão está ligado e o jogo não recebeu as duas linhas do dono: "
        f"{sorted(_as_da_steam(visto))}")


def test_com_o_botao_desligado_a_steam_decide(lar: Path) -> None:
    """Sem a escolha, nenhuma das duas: o jogo fica como a Steam o abre."""
    cv.gravar_camadas_da_steam_fora(False, config_home=_config(lar))
    visto = _lancar(lar, SteamAppId="1599660")
    assert _as_da_steam(visto) == set()
    assert visto.get("ENABLE_VK_LAYER_VALVE_steam_overlay_1") == "1"


def test_o_arquivo_adulterado_nao_exporta_outra_coisa(lar: Path) -> None:
    """Só as duas linhas que o lançador conhece, e só as duas juntas."""
    arquivo = cv.caminho_da_escolha(_config(lar))
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(
        "LD_PRELOAD=/tmp/nao-existe.so\n"
        f"{cv.AMBIENTE_SEM_AS_CAMADAS_DA_STEAM[0]}\n", encoding="utf-8")
    visto = _lancar(lar, SteamAppId="1599660")
    assert "LD_PRELOAD" not in visto
    assert _as_da_steam(visto) == set(), (
        "um arquivo pela metade entregou ao jogo metade do que a pílula diz")
    assert cv.camadas_da_steam_fora(_config(lar)) is False


_SOBREPOSICAO, _GRAVADOR = cv.AMBIENTE_SEM_AS_CAMADAS_DA_STEAM


@pytest.mark.parametrize("escrito", [
    f"{_SOBREPOSICAO}\n{_GRAVADOR}\n",
    f"# comentário\n{_GRAVADOR}\n{_SOBREPOSICAO}",       # sem a quebra no fim
    f"{_SOBREPOSICAO} \n{_GRAVADOR}\n",                 # espaço no fim da linha
    f" {_SOBREPOSICAO}\n{_GRAVADOR}\n",                 # espaço no começo
    f"{_SOBREPOSICAO}\r\n{_GRAVADOR}\r\n",              # salvo com \r\n
    f"{_SOBREPOSICAO}\n{_GRAVADOR}\n".encode() + b"\xff\xfe\n",  # byte fora do UTF-8
], ids=["exato", "sem-quebra-no-fim", "espaco-no-fim", "espaco-no-comeco", "crlf",
        "byte-torto"])
def test_a_pilula_e_o_lancador_leem_o_mesmo_arquivo_do_mesmo_jeito(
        lar: Path, escrito: str | bytes) -> None:
    """A pílula acende se, e só se, o jogo recebe as duas.

    Há DOIS leitores do mesmo arquivo — o dono em Python (a pílula e a linha do
    exame) e o lançador em shell puro (o jogo). Se discordam, a tela diz «sem a
    da Steam» sobre um jogo que nasceu com ela. MORDIDA: devolva o `strip()` ao
    `camadas_da_steam_fora` do dono e o caso do espaço reprova.
    """
    arquivo = cv.caminho_da_escolha(_config(lar))
    arquivo.parent.mkdir(parents=True)
    if isinstance(escrito, bytes):
        arquivo.write_bytes(escrito)
    else:
        arquivo.write_bytes(escrito.encode("utf-8"))
    o_jogo_recebeu = _as_da_steam(_lancar(lar, SteamAppId="1599660")) == set(
        cv.AMBIENTE_SEM_AS_CAMADAS_DA_STEAM)
    assert cv.camadas_da_steam_fora(_config(lar)) is o_jogo_recebeu, (
        f"a pílula diz {'acesa' if not o_jogo_recebeu else 'apagada'} e o jogo "
        f"{'recebeu' if o_jogo_recebeu else 'não recebeu'} as duas: {escrito!r}")


def test_o_jogo_da_lista_de_exclusao_abre_sem_nada(
        lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O jogo que ela tirou do Hefesto abre como se ele não estivesse instalado.

    A lista se escreve PELO DONO: uma mudança de formato lá reprova aqui.
    """
    from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx

    monkeypatch.setenv("XDG_CONFIG_HOME", str(_config(lar)))
    cv.gravar_camadas_da_steam_fora(True, config_home=_config(lar))
    assert lx.adicionar("steam_app_1599660", lancador="steam", nome="Wo Long") == "adicionado"
    assert _as_da_steam(_lancar(lar, SteamAppId="1599660")) == set()
    assert _as_da_steam(_lancar(lar, SteamAppId="1971870")) == set(
        cv.AMBIENTE_SEM_AS_CAMADAS_DA_STEAM)


# ---------------------------------------------------------------------------
# 2. O REGISTRO DO PREFIXO, SÓ NO JOGO QUE O LÊ
# ---------------------------------------------------------------------------


def _prefixo_e_jogo(lar: Path, *, com_carregador: bool) -> tuple[Path, Path, str]:
    prefixo = lar / "biblioteca" / "compatdata" / "1599660"
    (prefixo / "pfx").mkdir(parents=True)
    texto = _registro()
    (prefixo / "pfx" / "system.reg").write_text(texto, encoding="utf-8")
    jogo = lar / "biblioteca" / "common" / "Jogo"
    (jogo / "Binaries" / "Win64").mkdir(parents=True)
    (jogo / "Binaries" / "Win64" / "Jogo.exe").write_bytes(b"MZ")
    if com_carregador:
        (jogo / "Binaries" / "Win64" / "VULKAN-1.DLL").write_bytes(b"MZ")
    return prefixo, jogo, texto


def test_o_registro_nao_se_mexe_sem_o_carregador_da_khronos(lar: Path) -> None:
    """Botão ligado, camada ligada no registro, e o jogo sem `vulkan-1.dll`: nada.

    Era o gancho que editava todo prefixo em todo lançamento — e nenhum jogo
    desta máquina lia a chave.
    """
    _instalar_o_curador(lar)
    cv.gravar_camadas_da_steam_fora(True, config_home=_config(lar))
    prefixo, jogo, antes = _prefixo_e_jogo(lar, com_carregador=False)
    _lancar(lar, SteamAppId="1599660", STEAM_COMPAT_DATA_PATH=str(prefixo),
            STEAM_COMPAT_INSTALL_PATH=str(jogo))
    registro = prefixo / "pfx" / "system.reg"
    assert registro.read_text(encoding="utf-8") == antes
    assert not list(registro.parent.glob("system.reg.bak.hefesto-camadas-*"))


def test_o_registro_se_mexe_no_jogo_que_traz_o_carregador(lar: Path) -> None:
    """Com o carregador da Khronos na pasta do jogo, a camada de terceiro sai."""
    _instalar_o_curador(lar)
    cv.gravar_camadas_da_steam_fora(True, config_home=_config(lar))
    prefixo, jogo, _ = _prefixo_e_jogo(lar, com_carregador=True)
    _lancar(lar, SteamAppId="1599660", STEAM_COMPAT_DATA_PATH=str(prefixo),
            STEAM_COMPAT_INSTALL_PATH=str(jogo))
    texto = (prefixo / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert 'EOSOverlayVkLayer-Win64.json"=dword:00000001' in texto
    assert DRIVER in texto, "o driver do Wine não pode sair da posição de ligado"


def test_religado_depois_de_devolver_o_gancho_volta_a_tirar(lar: Path) -> None:
    """Desligar devolve e grava `manter`; ligar de novo é a voz dela por cima.

    O botão é um ligável desde 25/09 e a escolha é o arquivo que o lançador lê:
    desligar apaga a escolha E devolve (o `religar` grava `escolha: manter`).
    Quando ela liga de novo, o gancho do jogo que traz o carregador tem de
    voltar a tirar — é o `forcar=True` do modo `--prefixo`. Sem ele, o `manter`
    de ontem venceria o clique de hoje, e a pílula acesa mentiria sobre esse
    jogo. MORDIDA: troque o `forcar=True` do `main` por `forcar=False`.
    """
    _instalar_o_curador(lar)
    prefixo, jogo, _ = _prefixo_e_jogo(lar, com_carregador=True)
    marca = cv.chave_de_estado(r"Software\Khronos\Vulkan\ImplicitLayers", EPIC)
    estado = lar / "estado" / "hefesto-dualsense4unix" / cv.ESTADO_BASENAME
    estado.parent.mkdir(parents=True)
    estado.write_text(json.dumps({"prefixos": {"1599660": {
        marca: {"feito": "religada", "escolha": "manter", "quando": "2026-09-28T01:00:00"},
    }}}), encoding="utf-8")
    cv.gravar_camadas_da_steam_fora(True, config_home=_config(lar))
    _lancar(lar, SteamAppId="1599660", STEAM_COMPAT_DATA_PATH=str(prefixo),
            STEAM_COMPAT_INSTALL_PATH=str(jogo))
    texto = (prefixo / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert 'EOSOverlayVkLayer-Win64.json"=dword:00000001' in texto, (
        "a pílula está acesa e o `manter` de antes segurou a camada no jogo "
        "que a lê")


def test_com_o_botao_desligado_o_registro_nao_se_mexe(lar: Path) -> None:
    """Nem no jogo que traz o carregador: desligado, o gancho sai do caminho."""
    _instalar_o_curador(lar)
    prefixo, jogo, antes = _prefixo_e_jogo(lar, com_carregador=True)
    _lancar(lar, SteamAppId="1599660", STEAM_COMPAT_DATA_PATH=str(prefixo),
            STEAM_COMPAT_INSTALL_PATH=str(jogo))
    assert (prefixo / "pfx" / "system.reg").read_text(encoding="utf-8") == antes


# ---------------------------------------------------------------------------
# 3. O DONO
# ---------------------------------------------------------------------------


def test_ligar_e_desligar_pelo_dono(tmp_path: Path) -> None:
    config = tmp_path / "config"
    assert cv.camadas_da_steam_fora(config) is False
    cv.gravar_camadas_da_steam_fora(True, config_home=config)
    assert cv.camadas_da_steam_fora(config) is True
    cv.gravar_camadas_da_steam_fora(False, config_home=config)
    assert cv.camadas_da_steam_fora(config) is False
    assert not cv.caminho_da_escolha(config).exists()
    cv.gravar_camadas_da_steam_fora(False, config_home=config)  # desligar duas vezes


def test_a_busca_do_carregador(tmp_path: Path) -> None:
    """Qualquer caixa, até quatro níveis, sem seguir link de pasta."""
    jogo = tmp_path / "jogo"
    fundo = jogo / "a" / "b" / "c"
    fundo.mkdir(parents=True)
    assert cv.traz_o_carregador_da_khronos(jogo) is False
    (fundo / "Vulkan-1.dll").write_bytes(b"MZ")
    assert cv.traz_o_carregador_da_khronos(jogo) is True
    longe = tmp_path / "longe" / "a" / "b" / "c" / "d"
    longe.mkdir(parents=True)
    (longe / "vulkan-1.dll").write_bytes(b"MZ")
    assert cv.traz_o_carregador_da_khronos(tmp_path / "longe") is False
    laco = tmp_path / "laco"
    laco.mkdir()
    os.symlink(tmp_path, laco / "volta")
    assert cv.traz_o_carregador_da_khronos(laco) is False
    assert cv.traz_o_carregador_da_khronos(tmp_path / "nao-existe") is False


def test_o_prefixo_sem_a_pasta_do_jogo_nao_mexe(tmp_path: Path) -> None:
    """O modo `--prefixo` sem `--jogo` não sabe se há leitor, e não mexe."""
    prefixo = tmp_path / "compatdata" / "222"
    (prefixo / "pfx").mkdir(parents=True)
    antes = _registro()
    (prefixo / "pfx" / "system.reg").write_text(antes, encoding="utf-8")
    assert cv.main(["--prefixo", str(prefixo)]) == 0
    assert (prefixo / "pfx" / "system.reg").read_text(encoding="utf-8") == antes
