"""OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01 — as réguas.

A E1 é o dono da lista (`integrations/lista_de_exclusao.py`), e ela é um
GUARDA-CHUVA: excluir escreve nas duas listas por feature que já existiam (pino
e atalho); tirar sai delas — e SÓ das que a exclusão escreveu. A do Steam Input
NÃO entra: desde 09/08 ela põe o Hefesto NA FRENTE do jogo, não fora dele.

TODA RÉGUA AQUI DESVIA O `XDG_CONFIG_HOME` para uma pasta de teste. As listas
moram na configuração de verdade dela, e uma régua que escrevesse lá tiraria
jogos do Proton pinado na máquina dela.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import (
    ORIGEM_EXCLUSAO,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from tests.unit.test_a_cura_do_engasgo_alcanca_todos_os_prefixos import EPIC
from tests.unit.test_a_cura_do_engasgo_alcanca_todos_os_prefixos import (
    _registro as _registro_com_camadas,
)
from tests.unit.test_hefesto_launch_wrapper import (
    _PROBE,
    _FakeDaemon,
    _path_sem_game_mode,
    _runtime_dir,
    _socket_path,
    _write_env_file,
)
from tests.unit.test_proton_pin import PIN_NAME, _config_vdf
from tests.unit.test_sentinela_do_wrapper_01_a_steam_comeu_o_hefesto_launch import (
    _vdf as _localconfig,
)

_CHAVE = "steam_app_1088850"
_APPID = "1088850"


@pytest.fixture(autouse=True)
def _config_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def _nas_listas(appid: str) -> dict[str, bool]:
    def tem(caminho: Path) -> bool:
        try:
            texto = caminho.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        return appid in slo.parse_steam_input_allowlist(texto)

    return {
        "entrada": tem(slo.steam_input_allowlist_path()),
        "pino": tem(proton_pin.fora_do_pino_path()),
        "atalho": tem(slo.sem_wrapper_path()),
    }


def test_a_regua_nao_escreve_na_config_dela(_config_de_mentira: Path) -> None:
    """A trava das outras: se o desvio cair, as três listas apontariam para a
    configuração de verdade — e esta régua reprova ANTES de qualquer escrita."""
    for caminho in (slo.steam_input_allowlist_path(), proton_pin.fora_do_pino_path(),
                    slo.sem_wrapper_path(), lx.caminho()):
        assert _config_de_mentira in caminho.parents, caminho


def test_excluir_escreve_nas_duas_listas() -> None:
    """ARRANQUE o laço de `LISTAS` e este teste reprova: o jogo excluído
    continuaria com o Proton pinado e o atalho de inicialização."""
    assert lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões") == "adicionado"
    assert _nas_listas(_APPID) == {"entrada": False, "pino": True, "atalho": True}
    assert lx.contem(_CHAVE)


def test_a_exclusao_nunca_toca_na_lista_do_steam_input() -> None:
    """A CORREÇÃO DE 21/09, e ela tem dois lados.

    DE IDA — PONHA `"entrada"` de volta em `LISTAS` e este teste reprova. Desde
    09/08 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela) a marca do Steam Input
    ESCONDE O FÍSICO e mantém os virtuais de pé: *"a allowlist do Steam Input
    NÃO tira o Hefesto da frente"*. Pôr o jogo excluído nela deixaria o Hefesto
    na frente do jogo que ela quis sem Hefesto.

    DE VOLTA — o jogo que ELA marcou lá (o PRAGMATA, na máquina dela) continua
    lá depois de excluído e tirado. A primeira redação migrava essa marca para
    a exclusão, e isso desligaria a vibração da RE Engine que passa pelo
    Hefesto — a mesma que ela fez funcionar em 17/09.
    """
    slo.add_appid_to_steam_input_allowlist("3357650", nota="dela")
    assert not hasattr(lx, "migrar_a_lista_velha"), (
        "a migração da lista do Steam Input voltou — ela desligaria a vibração "
        "do PRAGMATA")
    lx.adicionar("steam_app_3357650", lancador="steam", nome="PRAGMATA")
    assert _nas_listas("3357650")["entrada"] is True
    lx.tirar("steam_app_3357650")
    assert _nas_listas("3357650")["entrada"] is True, (
        "tirar da exclusão apagou a marca que ELA pôs no Steam Input")
    lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões")
    assert _nas_listas(_APPID)["entrada"] is False


def test_tirar_sai_das_duas() -> None:
    """ARRANQUE o laço do `tirar` e este teste reprova: a exclusão viraria mão
    única — o jogo sairia da lista e continuaria sem nenhuma feature."""
    lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões")
    assert lx.tirar(_CHAVE) == "removido"
    assert _nas_listas(_APPID) == {"entrada": False, "pino": False, "atalho": False}
    assert not lx.contem(_CHAVE)


def test_tirar_nao_apaga_a_escolha_anterior_dela() -> None:
    """ARRANQUE o `if status == "adicionado"` (registre toda lista) e este
    teste reprova.

    Ela já tinha tirado o atalho deste jogo ANTES de excluí-lo. Excluir e tirar
    não pode apagar essa escolha — a exclusão viraria borracha, calada.
    """
    assert slo.marcar_jogo_sem_wrapper(_APPID, nota="dela") == "adicionado"
    lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões")
    (entrada,) = lx.ler()
    assert "atalho" not in entrada.escritas
    lx.tirar(_CHAVE)
    assert _nas_listas(_APPID)["atalho"] is True, (
        "o «Tirar» apagou uma escolha que ela tinha feito antes da exclusão")
    assert _nas_listas(_APPID)["pino"] is False


def test_o_emulador_entra_sem_tocar_nas_listas() -> None:
    """As listas falam appid da Steam; o emulador é um processo para todas as
    ROMs e não tem atalho nem pino. Ele entra na lista e nenhuma ganha linha."""
    assert lx.adicionar("processo:retroarch", lancador="retroarch",
                        nome="RetroArch — todos os jogos") == "adicionado"
    (entrada,) = lx.ler()
    assert entrada.escritas == ()
    for caminho in (slo.steam_input_allowlist_path(), proton_pin.fora_do_pino_path(),
                    slo.sem_wrapper_path()):
        assert not caminho.exists()


def test_chave_vazia_nao_escreve_nada() -> None:
    assert lx.adicionar("  ", lancador="steam", nome="x") == "chave_invalida"
    assert not lx.caminho().exists()


def test_excluir_duas_vezes_nao_duplica() -> None:
    lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões")
    assert lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões") == "ja_estava"
    assert len(lx.ler()) == 1


def test_arquivo_torto_e_recusado_e_nunca_sobrescrito() -> None:
    """ARRANQUE a recusa do `_ArquivoTortoError` no `adicionar` e este teste
    reprova: um JSON torto seria SOBRESCRITO com uma linha só, e a lista dela
    inteira sumiria para gravar um jogo."""
    destino = lx.caminho()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text('{"formato": 1, "jogos": [ ESTRAGADO', encoding="utf-8")
    assert lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões") == "erro"
    assert destino.read_text(encoding="utf-8").endswith("ESTRAGADO")
    assert _nas_listas(_APPID)["entrada"] is False, (
        "o arquivo foi recusado e mesmo assim as listas ganharam a linha")
    assert lx.ler() == []


def test_uma_lista_que_falha_desfaz_as_outras(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o desfazer do ramo de erro e este teste reprova: o jogo ficaria
    MEIO excluído — fora do pino, mas com o atalho —, que é o estado que a
    D-2109-A-EXCLUSAO-E-TUDO-OU-NADA existe para não ter."""
    monkeypatch.setitem(lx._POR, "atalho", lambda a: "erro")
    assert lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões") == "erro"
    assert _nas_listas(_APPID) == {"entrada": False, "pino": False, "atalho": False}
    assert lx.ler() == []


def test_a_linha_de_comando_do_pino_passa_pelo_dono() -> None:
    """Um dono só para o formato do `jogos_fora_do_pino.txt`: a CLI e a lista
    de exclusão escrevem pela MESMA função."""
    assert "nomear_fora_do_pino" in inspect.getsource(proton_pin._cmd_fora_do_pino)
    assert "devolver_ao_pino" in inspect.getsource(proton_pin._cmd_de_volta_ao_pino)


# ---------------------------------------------------------------------------
# E2 — tirar o pino de UM jogo (`proton_pin.destravar_um_jogo`)
# ---------------------------------------------------------------------------
#
# O `jogos_fora_do_pino.txt` só tira o jogo do PRÓXIMO lock, e o único
# desfazer que existia era o do desinstalar, que devolve TODOS. A exclusão
# precisa devolver UM — e com a regra do desinstalar: só o que é nosso.

@pytest.fixture
def _steam_fechada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proton_pin, "steam_running", lambda: False)
    monkeypatch.setattr(proton_pin, "steam_game_running", lambda: False)


def _pinar(tmp_path: Path, jogos: list[str]) -> tuple[Path, Path]:
    vdf = tmp_path / "config.vdf"
    vdf.write_text(_config_vdf({"1245620": "proton_11"}), encoding="utf-8")
    estado = tmp_path / "estado" / "proton-pin-lock.json"
    r = proton_pin.lock_games_to_pinned_proton(
        tool_name=PIN_NAME, appids=jogos, config_vdf=vdf, state_path=estado)
    assert r["status"] == "locked", r
    return vdf, estado


def test_destravar_um_jogo_devolve_so_ele(tmp_path: Path, _steam_fechada: None) -> None:
    """ARRANQUE o recorte `changes={alvo: …}` (passe o registro inteiro) e este
    teste reprova: excluir UM jogo tiraria o pino de TODOS — o desinstalar
    disfarçado de botão."""
    vdf, estado = _pinar(tmp_path, ["1599660", "1971870"])
    r = proton_pin.destravar_um_jogo("1599660", config_vdf=vdf, state_path=estado)
    assert r["status"] == "destravado" and r["reverted"] == 1, r
    mapa = proton_pin.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))
    assert "1599660" not in mapa, "o jogo excluído continua pinado"
    assert mapa.get("1971870") == PIN_NAME, "o OUTRO jogo perdeu o pino"
    registro = json.loads(estado.read_text(encoding="utf-8"))
    assert "1599660" not in registro["changes"]
    assert "1971870" in registro["changes"], "o registro do outro jogo sumiu"


def test_destravar_nao_desfaz_o_proton_que_ela_trocou(
        tmp_path: Path, _steam_fechada: None) -> None:
    """A regra do desinstalar, recortada: se ela trocou o Proton do jogo DEPOIS
    do pino, a escolha é dela e fica — e a linha sai do registro, para um
    desinstalar futuro não tentar desfazer o que não é mais nosso."""
    vdf, estado = _pinar(tmp_path, ["1599660"])
    texto = vdf.read_text(encoding="utf-8")
    vdf.write_text(texto.replace(f'"{PIN_NAME}"', '"proton_9"', 2), encoding="utf-8")
    trocado = proton_pin.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))
    assert trocado.get("1599660") == "proton_9"
    r = proton_pin.destravar_um_jogo("1599660", config_vdf=vdf, state_path=estado)
    assert r["status"] == "destravado" and r["reverted"] == 0, r
    assert proton_pin.extract_compat_tool_mapping(
        vdf.read_text(encoding="utf-8")).get("1599660") == "proton_9"
    assert "1599660" not in json.loads(estado.read_text(encoding="utf-8"))["changes"]


def test_destravar_com_a_steam_aberta_nao_toca_em_nada(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _steam_fechada: None) -> None:
    """ARRANQUE o `_steam_gate()` e este teste reprova: a Steam viva regrava o
    `config.vdf` ao sair, e a edição seria perdida — ou pior, corrompida."""
    vdf, estado = _pinar(tmp_path, ["1599660"])
    antes = vdf.read_text(encoding="utf-8"), estado.read_text(encoding="utf-8")
    monkeypatch.setattr(proton_pin, "steam_running", lambda: True)
    r = proton_pin.destravar_um_jogo("1599660", config_vdf=vdf, state_path=estado)
    assert r["status"] == "recusado", r
    assert (vdf.read_text(encoding="utf-8"), estado.read_text(encoding="utf-8")) == antes


def test_destravar_o_que_nao_e_nosso_e_noop(tmp_path: Path, _steam_fechada: None) -> None:
    vdf, estado = _pinar(tmp_path, ["1599660"])
    antes = vdf.read_text(encoding="utf-8")
    r = proton_pin.destravar_um_jogo("424242", config_vdf=vdf, state_path=estado)
    assert (r["status"], r["reason"]) == ("noop", "nao_era_nosso")
    assert vdf.read_text(encoding="utf-8") == antes


# ---------------------------------------------------------------------------
# E2 — tirar o atalho de UM jogo, e o vigia honrando a lista nos dois sentidos
# ---------------------------------------------------------------------------
#
# A lista `jogos_sem_wrapper.txt` só fazia o jogo ser PULADO: o que ele já
# tinha ficava. Agora o dono do atalho sabe tirar de um jogo só, e o reparo do
# vigia tira de quem está na lista.

#: A linha dela que tem de sobreviver byte a byte (a do PRAGMATA, 14/08).
_DELA = "VKD3D_CONFIG=no_upload_hvv %command%"


@pytest.fixture
def _steam_fechada_no_atalho(monkeypatch: pytest.MonkeyPatch) -> None:
    for modulo in (slo, sw):
        monkeypatch.setattr(modulo, "steam_running", lambda: False)
        monkeypatch.setattr(modulo, "steam_game_running", lambda: False)


def _biblioteca(tmp_path: Path) -> Path:
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_localconfig({
        "1599660": slo.migrate_value(_DELA),
        "1971870": slo.WRAPPER_LAUNCH,
    }), encoding="utf-8")
    return vdf


def test_tirar_o_atalho_tira_so_o_jogo_pedido(
        tmp_path: Path, _steam_fechada_no_atalho: None) -> None:
    """ARRANQUE o filtro `so_os_jogos` do `transform_vdf_text` e este teste
    reprova: excluir UM jogo tiraria o atalho da biblioteca inteira — o
    `--strip` do desinstalar disfarçado de botão."""
    vdf = _biblioteca(tmp_path)
    r = slo.tirar_o_atalho_dos_jogos(["1599660"], vdfs=[vdf])
    apps = slo.read_apps_by_appid(vdf.read_text(encoding="utf-8"))
    assert [i["appid"] for i in r["removed"]] == ["1599660"], r
    assert apps["1599660"] == _DELA, "a linha dela não sobreviveu"
    assert slo.WRAPPER_PREFIX in (apps["1971870"] or ""), "o OUTRO jogo perdeu o atalho"


def test_tirar_o_atalho_com_a_steam_aberta_nao_toca(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        _steam_fechada_no_atalho: None) -> None:
    vdf = _biblioteca(tmp_path)
    antes = vdf.read_text(encoding="utf-8")
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    r = slo.tirar_o_atalho_dos_jogos(["1599660"], vdfs=[vdf])
    assert [e["reason"] for e in r["errors"]] == ["steam_aberta"], r
    assert vdf.read_text(encoding="utf-8") == antes


def test_o_vigia_tira_o_atalho_de_quem_esta_na_lista(
        tmp_path: Path, _steam_fechada_no_atalho: None) -> None:
    """ARRANQUE o `recusados_com_wrapper` do censo e este teste reprova: o
    reparo do vigia diria «nada a fazer», e o jogo que ela excluiu continuaria
    abrindo pelo Hefesto."""
    vdf = _biblioteca(tmp_path)
    assert slo.marcar_jogo_sem_wrapper("1599660") == "adicionado"
    status, censo, resultado = sw.reparar_ou_adiar(
        vdfs=[vdf], registro=tmp_path / "visto.json")
    assert status == sw.REPARO_FEITO, (status, censo)
    assert resultado is not None
    assert [i["appid"] for i in resultado["removed"]] == ["1599660"]
    apps = slo.read_apps_by_appid(vdf.read_text(encoding="utf-8"))
    assert apps["1599660"] == _DELA
    assert slo.WRAPPER_PREFIX in (apps["1971870"] or "")


def test_o_vigia_nao_repoe_o_atalho_de_quem_esta_na_lista(
        tmp_path: Path, _steam_fechada_no_atalho: None) -> None:
    """O avesso, que já valia e tem de continuar valendo: o jogo da lista sem
    o atalho é o estado CERTO, e o reparo não briga com ele."""
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text(_localconfig({"1599660": _DELA}), encoding="utf-8")
    slo.marcar_jogo_sem_wrapper("1599660")
    status, _, _ = sw.reparar_ou_adiar(vdfs=[vdf], registro=tmp_path / "visto.json")
    assert status == sw.REPARO_NADA
    assert slo.read_apps_by_appid(vdf.read_text(encoding="utf-8"))["1599660"] == _DELA


# ---------------------------------------------------------------------------
# E2 — «tirar do disco»: o passo do vigia, feito na hora do clique
# ---------------------------------------------------------------------------

@pytest.fixture
def _steam_do_teste(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        _steam_fechada: None, _steam_fechada_no_atalho: None) -> tuple[Path, Path, Path]:
    """Os três arquivos da Steam apontados para a pasta de teste — nenhum
    caminho padrão alcança a Steam de verdade dela."""
    config_vdf, estado = _pinar(tmp_path, ["1599660", "1971870"])
    biblioteca = _biblioteca(tmp_path)
    monkeypatch.setattr(proton_pin, "default_config_vdf", lambda home=None: config_vdf)
    monkeypatch.setattr(proton_pin, "default_lock_state_path", lambda home=None: estado)
    monkeypatch.setattr(slo, "discover_vdfs", lambda home=None: [biblioteca])
    return config_vdf, estado, biblioteca


def test_excluir_com_a_steam_fechada_tira_pino_e_atalho_na_hora(
        _steam_do_teste: tuple[Path, Path, Path]) -> None:
    """ARRANQUE uma das duas chamadas do `tirar_do_disco` e este teste reprova:
    o jogo abriria UMA vez pelo Hefesto antes de a Steam fechar e o vigia
    terminar o serviço."""
    config_vdf, _, biblioteca = _steam_do_teste
    assert lx.tirar_do_disco("steam_app_1599660") == "feito"
    mapa = proton_pin.extract_compat_tool_mapping(config_vdf.read_text(encoding="utf-8"))
    assert "1599660" not in mapa and mapa.get("1971870") == PIN_NAME
    apps = slo.read_apps_by_appid(biblioteca.read_text(encoding="utf-8"))
    assert apps["1599660"] == _DELA
    assert slo.WRAPPER_PREFIX in (apps["1971870"] or "")
    assert lx.tirar_do_disco("steam_app_1599660") == "nada_a_tirar"


def test_excluir_com_a_steam_aberta_espera_e_nao_escreve(
        _steam_do_teste: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    config_vdf, estado, biblioteca = _steam_do_teste
    antes = [p.read_text(encoding="utf-8") for p in (config_vdf, estado, biblioteca)]
    for modulo in (proton_pin, slo):
        monkeypatch.setattr(modulo, "steam_running", lambda: True)
    assert lx.tirar_do_disco("steam_app_1599660") == "espera_a_steam"
    assert [p.read_text(encoding="utf-8") for p in (config_vdf, estado, biblioteca)] == antes


def test_o_emulador_nao_tem_o_que_tirar_do_disco() -> None:
    assert lx.tirar_do_disco("retroarch") == "sem_appid"


# ---------------------------------------------------------------------------
# E2 — o wrapper consulta a lista: a exclusão vale com a Steam aberta
# ---------------------------------------------------------------------------
#
# Até o vigia tirar o atalho (na saída da Steam), a LaunchOptions do jogo
# excluído ainda chama o `hefesto-launch`. É o wrapper quem faz a exclusão
# valer no primeiro lançamento depois do clique.

_O_WRAPPER = Path(__file__).resolve().parents[2] / "assets" / "hefesto-launch.sh"


@pytest.fixture
def _runtime_com_daemon() -> Iterator[Path]:
    """Daemon de mentira de pé: sem a lista, o wrapper EXPORTARIA as envs — é
    o que prova que a ausência delas é a exclusão, e não um gate que caiu."""
    base = _runtime_dir()
    daemon = _FakeDaemon(_socket_path(base))
    try:
        yield base
    finally:
        daemon.stop()
        shutil.rmtree(base, ignore_errors=True)


def _lancar(runtime: Path, casa: Path, appid: str, *, com_config: bool = True
            ) -> tuple[subprocess.CompletedProcess[str], Path]:
    estado = casa / "estado"
    _write_env_file(estado, "default.env", ["SDL_JOYSTICK_HIDAPI=0"])
    env = {
        "PATH": _path_sem_game_mode(runtime),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(estado),
        "SteamAppId": appid,
    }
    if com_config:
        env["HOME"] = str(casa / "casa-vazia")
        env["XDG_CONFIG_HOME"] = str(casa)
    r = subprocess.run(["sh", str(_O_WRAPPER), "sh", "-c", _PROBE], env=env,
                       capture_output=True, text=True, timeout=15, check=False)
    return r, estado / "hefesto-dualsense4unix" / "launch_env" / "last_run"


def test_o_jogo_excluido_abre_sem_nada_do_hefesto(
        tmp_path: Path, _runtime_com_daemon: Path) -> None:
    """ARRANQUE o `if jogo_excluido` do wrapper e este teste reprova: com a
    Steam aberta o atalho ainda está na LaunchOptions, e o jogo que ela
    excluiu abriria com as envs, o device KS e a camada Vulkan do Hefesto."""
    assert lx.adicionar("steam_app_1599660", lancador="steam", nome="Wo Long") == "adicionado"
    fora, marca_fora = _lancar(_runtime_com_daemon, tmp_path, "1599660")
    assert fora.returncode == 0, fora.stderr
    assert "HIDAPI=|" in fora.stdout, fora.stdout
    assert not marca_fora.exists(), "o marcador de lançamento do Hefesto foi gravado"

    dentro, marca_dentro = _lancar(_runtime_com_daemon, tmp_path, "1971870")
    assert "HIDAPI=0|" in dentro.stdout, "o controle: sem a lista, as envs chegam"
    assert marca_dentro.exists()


def test_steam_app_1_nao_casa_steam_app_15(
        tmp_path: Path, _runtime_com_daemon: Path) -> None:
    """As aspas dos dois lados do número: excluir um jogo não exclui o de
    appid que começa igual."""
    lx.adicionar("steam_app_1599660", lancador="steam", nome="Wo Long")
    r, _ = _lancar(_runtime_com_daemon, tmp_path, "159966")
    assert "HIDAPI=0|" in r.stdout, r.stdout


def test_sem_home_o_jogo_abre_do_mesmo_jeito(
        tmp_path: Path, _runtime_com_daemon: Path) -> None:
    """O wrapper roda com `set -u`: um `$HOME` cru na leitura da lista
    abortaria o script, e o jogo não abriria."""
    r, _ = _lancar(_runtime_com_daemon, tmp_path, "1599660", com_config=False)
    assert r.returncode == 0, r.stderr
    assert "IGNORE=" in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# E2 — o prefixo Wine: o device KS sai, e as camadas Vulkan que NÓS
# desligamos voltam, sem virar escolha dela
# ---------------------------------------------------------------------------

@pytest.fixture
def _prefixo_curado(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        _steam_do_teste: tuple[Path, Path, Path]) -> Path:
    """O prefixo de um jogo que o Hefesto já tocou: o device KS gravado e a
    camada do Epic desligada pela cura do lançamento — como no uso real."""
    compatdata = tmp_path / "steamapps" / "compatdata"
    raiz = compatdata / "1599660"
    (raiz / "pfx").mkdir(parents=True)
    texto = ks.texto_novo(_registro_com_camadas((EPIC, "00000000")),
                          [ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=None)], 1)
    (raiz / "pfx" / "system.reg").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(cv, "pastas_compatdata", lambda home=None: [compatdata])
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado-das-camadas"))
    assert cv.curar_um_prefixo(raiz, appid="1599660").desligadas
    assert _nossos_blocos_ks(raiz)
    return raiz


def _nossos_blocos_ks(raiz: Path) -> list[str]:
    texto = (raiz / "pfx" / "system.reg").read_text(encoding="utf-8")
    return [b for b in ks._blocos(texto) if ks.e_bloco_nosso(b)]


def _epic_ligada(raiz: Path) -> bool:
    camadas = cv.ler_camadas(raiz / "pfx" / "system.reg", prefixo=raiz)
    return next(c for c in camadas if c.caminho_windows == EPIC).ligada


def test_excluir_tira_o_ks_e_devolve_a_camada(_prefixo_curado: Path) -> None:
    """ARRANQUE o `_devolver_o_prefixo` do `tirar_do_disco` e este teste
    reprova: o jogo excluído seguiria com o device KS do Hefesto e sem a
    camada do Epic que ele tinha."""
    assert lx.tirar_do_disco("steam_app_1599660") == "feito"
    assert not _nossos_blocos_ks(_prefixo_curado), "o device KS do Hefesto ficou"
    assert _epic_ligada(_prefixo_curado), "a camada que o Hefesto desligou não voltou"


def test_tirar_da_lista_a_cura_do_lancamento_volta(_prefixo_curado: Path) -> None:
    """ARRANQUE o `pela_exclusao` (religue como o «devolver», com `manter`) e
    este teste reprova: a exclusão viraria uma escolha permanente que ela
    nunca fez, e tirar o jogo da lista não devolveria a cura."""
    lx.tirar_do_disco("steam_app_1599660")
    memoria = cv.ler_estado()["1599660"]
    assert all("escolha" not in m for m in memoria.values()), memoria
    assert cv.curar_um_prefixo(_prefixo_curado, appid="1599660").desligadas
    assert not _epic_ligada(_prefixo_curado)


def test_o_botao_vulkan_pula_o_jogo_excluido(_prefixo_curado: Path) -> None:
    """ARRANQUE o `excluir` do `curar_todos` e este teste reprova: o botão da
    aba Sistema desligaria de novo a camada do jogo que ela excluiu."""
    lx.tirar_do_disco("steam_app_1599660")
    cv.curar_todos(excluir=["1599660"])
    assert _epic_ligada(_prefixo_curado)
    cv.curar_todos()
    assert not _epic_ligada(_prefixo_curado), "o controle: sem o excluir, o botão cura"


def test_com_o_jogo_aberto_o_prefixo_espera(
        _prefixo_curado: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `wineserver` vivo regravaria o registro ao sair: nada se escreve."""
    antes = (_prefixo_curado / "pfx" / "system.reg").read_text(encoding="utf-8")
    monkeypatch.setattr(ks, "wineserver_do_prefixo_vivo", lambda *a, **k: True)
    assert lx.tirar_do_disco("steam_app_1599660") == "espera_a_steam"
    assert (_prefixo_curado / "pfx" / "system.reg").read_text(encoding="utf-8") == antes


def test_os_appids_da_lista_sao_so_os_de_steam() -> None:
    lx.adicionar("steam_app_1599660", lancador="steam", nome="Wo Long")
    lx.adicionar("retroarch", lancador="emulador", nome="RetroArch")
    assert lx.appids() == ["1599660"]


# ---------------------------------------------------------------------------
# E3 — a camada ao vivo: a janela excluída em foco liga o Modo Nativo
# ---------------------------------------------------------------------------
#
# O Modo Nativo JÁ é o «Hefesto fora»: gatilhos Off na mesa inteira, vibração
# do jogo, emulação desligada e guardada, o físico exposto ao jogo. A exclusão
# o liga com a origem dela, anota a POSSE no stash, e solta ao sair do foco.

_JANELA = "steam_app_1599660"


class _NativoCapturado:
    """O `set_native_mode` do daemon trocado por um que só registra — a régua
    mede a POLÍTICA, e nada aqui escreve no controle dela."""

    def __init__(self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
        self.chamadas: list[tuple[bool, str]] = []

        def _nativo(enabled: bool, *, reapply: bool = True,
                    restore_stash: bool = False, origin: str = "manual") -> bool:
            self.chamadas.append((enabled, origin))
            daemon._native_mode = enabled
            return enabled

        monkeypatch.setattr(daemon, "set_native_mode", _nativo)


@pytest.fixture
def _daemon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Daemon:
    """O flag do Modo Nativo vai para a pasta do teste: o lar de mentira da
    suíte é COMPARTILHADO, e um `native_mode.flag` que sobrasse faria o
    próximo daemon da suíte nascer solto."""
    casa = tmp_path / "config-do-daemon"
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: casa.mkdir(
        parents=True, exist_ok=True) or casa)
    return Daemon(controller=FakeController(), config=DaemonConfig())


def test_a_janela_excluida_liga_o_modo_nativo(
        _daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    nativo = _NativoCapturado(_daemon, monkeypatch)
    _daemon.aplicar_a_exclusao(chave=_JANELA)
    _daemon.aplicar_a_exclusao(chave=_JANELA)
    assert nativo.chamadas == [(True, ORIGEM_EXCLUSAO)], "um pedido por episódio"
    _daemon.reverter_a_exclusao()
    assert nativo.chamadas[-1] == (False, ORIGEM_EXCLUSAO)
    assert _daemon._exclusao_viva is None


def test_o_modo_nativo_dela_nao_e_desligado_pela_exclusao(
        _daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `ligou_nativo` e este teste reprova: sair do jogo excluído
    desligaria o Modo Nativo que ELA tinha ligado antes."""
    nativo = _NativoCapturado(_daemon, monkeypatch)
    _daemon._native_mode = True
    _daemon.aplicar_a_exclusao(chave=_JANELA)
    _daemon.reverter_a_exclusao()
    assert nativo.chamadas == []
    assert _daemon._native_mode is True


def test_a_posse_da_exclusao_atravessa_o_reinicio(
        _daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE a leitura da posse do `_carregar_o_modo_nativo` e este teste
    reprova: o daemon reiniciado com o jogo excluído em foco leria o Modo
    Nativo como gesto dela, e o controle ficaria solto depois do jogo."""
    _NativoCapturado(_daemon, monkeypatch)
    _daemon.aplicar_a_exclusao(chave=_JANELA)

    renascido = Daemon(controller=FakeController(), config=DaemonConfig())
    nativo = _NativoCapturado(renascido, monkeypatch)
    renascido._carregar_o_modo_nativo()
    assert renascido._native_mode is True
    assert renascido._exclusao_viva is not None
    assert renascido._exclusao_viva.chave == _JANELA
    renascido.reverter_a_exclusao()
    assert nativo.chamadas == [(False, ORIGEM_EXCLUSAO)]


class _EspiaoDaExclusao:
    def __init__(self) -> None:
        self.aplicadas: list[str] = []
        self.revertidas = 0
        self.modo_padrao: list[str] = []

    def aplicar(self, *, chave: str) -> str:
        self.aplicadas.append(chave)
        return "aplicado"

    def reverter(self) -> str:
        self.revertidas += 1
        return "aplicado"

    def modo_jogo_padrao(self, *, wm_class: str = "") -> str:
        self.modo_padrao.append(wm_class)
        return "aplicado"


def _o_autoswitch(espiao: _EspiaoDaExclusao) -> AutoSwitcher:
    controle = FakeController()
    controle.connect()
    store = StateStore()
    return AutoSwitcher(
        manager=ProfileManager(controller=controle, store=store),
        window_reader=lambda: {},
        store=store,
        modo_jogo_padrao_applier=espiao.modo_jogo_padrao,
        modo_jogo_padrao_reverter=lambda **_: "aplicado",
        exclusao_applier=espiao.aplicar,
        exclusao_reverter=espiao.reverter,
        exclusao_reader=lx.contem,
    )


def test_a_janela_excluida_nao_pede_perfil_nem_modo_jogo(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `_na_exclusao` do tique e este teste reprova: o jogo que ela
    excluiu ganharia o modo jogo padrão — o gamepad virtual na frente dele."""
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: tmp_path)
    lx.adicionar(_JANELA, lancador="steam", nome="Wo Long")
    espiao = _EspiaoDaExclusao()
    sw = _o_autoswitch(espiao)
    for t in (0.0, 0.6, 60.0):
        sw._tick({"wm_class": _JANELA, "wm_name": "Wo Long"}, t)
    assert espiao.aplicadas == [_JANELA] * 3
    assert espiao.modo_padrao == []
    assert sw._current_profile is None

    sw._tick({"wm_class": "firefox", "wm_name": "Mozilla"}, 61.0)
    assert espiao.revertidas == 1


def test_fora_da_lista_nada_muda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: tmp_path)
    espiao = _EspiaoDaExclusao()
    sw = _o_autoswitch(espiao)
    sw._tick({"wm_class": _JANELA, "wm_name": "Wo Long"}, 0.0)
    sw._tick({"wm_class": "firefox"}, 1.0)
    assert espiao.aplicadas == [] and espiao.revertidas == 0


@pytest.mark.parametrize("rota", ["subsistema", "utilitaria"])
def test_as_duas_rotas_de_subida_ligam_os_tres_fios(
        rota: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE um dos três fios de uma das rotas e este teste reprova: o
    autoswitch subiria sem saber da lista, e a E3 inteira ficaria escrita e
    desligada — a cura que ninguém chama, o defeito mais caro desta casa."""
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch as sub
    from hefesto_dualsense4unix.profiles import autoswitch as perfis
    from hefesto_dualsense4unix.profiles import manager as gerente

    capturado: dict[str, object] = {}

    class _Captura:
        def __init__(self, **kwargs: object) -> None:
            capturado.update(kwargs)

        def disabled(self) -> bool:
            return True

    monkeypatch.setattr(sub, "_ensure_display_env", lambda: None)
    monkeypatch.setattr(sub, "_build_diag_window_reader", lambda store: lambda: {})
    monkeypatch.setattr(perfis, "AutoSwitcher", _Captura)
    monkeypatch.setattr(gerente, "gerente_do_daemon", lambda *a, **k: object())
    daemon = SimpleNamespace(
        store=StateStore(),
        aplicar_a_exclusao=lambda **_: "aplicado",
        reverter_a_exclusao=lambda: "aplicado",
    )
    if rota == "subsistema":
        ctx = SimpleNamespace(daemon=daemon, controller=None, store=daemon.store)
        asyncio.run(sub.AutoswitchSubsystem().start(ctx))  # type: ignore[arg-type]
    else:
        asyncio.run(sub.start_autoswitch(daemon))  # type: ignore[arg-type]
    assert capturado["exclusao_applier"] is daemon.aplicar_a_exclusao
    assert capturado["exclusao_reverter"] is daemon.reverter_a_exclusao
    assert capturado["exclusao_reader"] is lx.contem


# ---------------------------------------------------------------------------
# E5 — os oito cartões iguais, a escolha do jogo e os gestos
# ---------------------------------------------------------------------------
_APPID_WO_LONG = "1599660"


@pytest.fixture()
def _aba07(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple]:
    """O desenho e o pacote da aba 07, com a VIGIA parada.

    Os gestos devolvem `_resposta(VIGIA.agora(), …)`, e a vigia sem dado dispara
    a thread que lê o disco de verdade — o vazamento medido em 13/09/2026 em
    `test_a_aba_07_lancadores_fecha_as_linhas.py`. Aqui ela responde nada, e a
    escolha que um teste abre não sobra para o seguinte.
    """
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: None)
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: None)
    a07._ESCOLHA.limpar()
    yield desenho, a07
    a07._ESCOLHA.limpar()


def _o_dia_bom(desenho) -> object:
    """A Steam em ordem e os outros achados — os cartões no estado LOCALIZADO."""
    achados = tuple((item.chave, f"/opt/{item.chave}") for item in desenho.EMBUTIDOS
                    if item.chave != desenho.STEAM)
    return desenho.Leitura(com_wrapper=("620", "440"), instalados=2,
                           onde_estao=achados)


def test_os_cartoes_localizados_tem_a_mesma_fileira(_aba07) -> None:
    """Os cartões ACHADOS oferecem os mesmos botões — o pedido dela, *"todos os
    lançadores com os botões da Steam"*.

    A régua PERGUNTA ao dono dos rótulos (`fileira_comum`), nunca digita — régua
    de dono mede DONO. ARRANQUE a `fileira_comum` de um cartão e ela reprova
    nomeando qual.
    """
    desenho, _a07 = _aba07
    cartoes = desenho.cartoes(_o_dia_bom(desenho))
    assert len(cartoes) >= 6, [c.chave for c in cartoes]
    for lanc in cartoes:
        if lanc.chave == "flatpak":
            continue                    # o pacote dos outros, sem jogo próprio
        esperado = [a.rotulo for a in desenho.fileira_comum(lanc.chave)]
        rotulos = [a.rotulo for a in lanc.acoes]
        faltam = [r for r in esperado if r not in rotulos]
        assert not faltam, (lanc.chave, rotulos)


def test_nenhum_botao_do_cartao_nasce_sem_gesto(_aba07) -> None:
    """O «Criar perfil para um jogo» era um botão SEM gesto (§1 da sprint).
    ARRANQUE o gesto dele e este teste reprova: é o botão morto de antes,
    multiplicado por oito."""
    desenho, _a07 = _aba07
    for lanc in desenho.cartoes(_o_dia_bom(desenho)):
        mortos = [a.rotulo for a in lanc.acoes if not a.gesto]
        assert not mortos, (lanc.chave, mortos)


def test_o_emulador_nao_promete_exclusao_por_rom(_aba07) -> None:
    """Um processo para todas as ROMs (§4.3): a lista oferece UMA linha.
    ARRANQUE o ramo do emulador e este teste reprova — a lista ofereceria uma
    ROM que o daemon não sabe distinguir."""
    _desenho, a07 = _aba07
    jogos, janelas, emulador = a07._jogos_para_escolher("retroarch", "RetroArch", None)
    assert emulador and len(jogos) == 1
    assert jogos[0].chave == "emulador:retroarch"
    assert "com.libretro.RetroArch" in janelas[jogos[0].chave]


def test_a_exclusao_do_emulador_casa_pela_janela_medida(_aba07) -> None:
    """A janela do RetroArch diz `com.libretro.RetroArch`, e o flatpak é `org.`
    (medido em 10/09/2026). A lista casa pela JANELA, sem caixa."""
    _desenho, a07 = _aba07
    jogos, janelas, _ = a07._jogos_para_escolher("retroarch", "RetroArch", None)
    lx.adicionar(jogos[0].chave, lancador="retroarch", nome=jogos[0].nome,
                 janelas=janelas[jogos[0].chave])
    assert lx.contem("com.libretro.RetroArch")
    assert lx.contem("COM.LIBRETRO.RETROARCH")
    assert not lx.contem("steam_app_1599660")


class _Ctx:
    state: dict | None = None


def _escolher(monkeypatch: pytest.MonkeyPatch, a07, modo: str) -> None:
    monkeypatch.setattr(
        a07, "_jogos_para_escolher",
        lambda lancador, nome, state: (
            [a07.desenho.JogoParaEscolher(chave=_JANELA, nome="Wo Long")], {}, False))
    a07._abrir_a_escolha(modo, a07.desenho.STEAM, None)


def test_confirmar_a_exclusao_grava_e_tira_do_disco(
        _aba07, monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `tirar_do_disco` do confirmar e este teste reprova: o jogo
    entraria na lista com o pino e o atalho de antes."""
    desenho, a07 = _aba07
    tirados: list[str] = []
    monkeypatch.setattr(lx, "tirar_do_disco",
                        lambda chave: tirados.append(chave) or "feito")
    _escolher(monkeypatch, a07, desenho.EXCLUIR)
    assert f"#{desenho.MIOLO_DA_ESCOLHA}" in a07._pintura([])["blocos"]
    a07.confirmar_a_exclusao(_Ctx(), {"forma": {desenho.ESCOLHA: _JANELA}}, None)
    assert lx.contem(_JANELA)
    assert tirados == [_JANELA]
    assert f"#{desenho.MIOLO_DA_ESCOLHA}" not in a07._pintura([])["blocos"], (
        "a pop-up continuaria com o jogo que ela acabou de excluir")


def test_confirmar_sem_escolha_recusa_dizendo(
        _aba07, monkeypatch: pytest.MonkeyPatch) -> None:
    desenho, a07 = _aba07
    _escolher(monkeypatch, a07, desenho.EXCLUIR)
    with pytest.raises(RuntimeError, match="Escolha um jogo"):
        a07.confirmar_a_exclusao(_Ctx(), {"forma": {}}, None)
    assert not lx.contem(_JANELA)


def test_tirar_da_lista_pelo_rodape(_aba07) -> None:
    """O «Tirar da lista» do rodapé leva a CHAVE no `data-v`, e o gesto a tira.
    ARRANQUE o `lista_de_exclusao.tirar` do gesto e este teste reprova."""
    desenho, a07 = _aba07
    lx.adicionar(_JANELA, lancador=desenho.STEAM, nome="Wo Long")
    rodape = desenho.rodape_da_exclusao_html([(_JANELA, "Wo Long")])
    assert (f'data-gesto="{desenho.TIRAR_DA_EXCLUSAO}" data-v="{_JANELA}"'
            in rodape)
    a07.tirar_da_exclusao(_Ctx(), {"v": _JANELA}, None)
    assert not lx.contem(_JANELA)


def test_o_rodape_diz_o_excluido_e_a_lista_da_steam_nao_o_repete(_aba07) -> None:
    """ARRANQUE o filtro dos recusados e este teste reprova: o jogo excluído
    apareceria duas vezes no cartão, uma delas com um «Voltar a usar» que
    desfaria só o atalho — metade da exclusão."""
    desenho, a07 = _aba07
    lx.adicionar(_JANELA, lancador=desenho.STEAM, nome="Wo Long")
    lida = desenho.Leitura(
        com_wrapper=("620",), instalados=1,
        recusados=((_APPID_WO_LONG, "Wo Long"), ("70", "Jogo tirado")))
    steam = a07.com_a_exclusao(desenho.cartoes(lida), lida)[0]
    assert "Na lista de exclusão" in steam.fora and "Wo Long" in steam.fora
    assert steam.fora.count("Wo Long") == 1, steam.fora
    assert "Jogo tirado" in steam.fora, "o recusado DELA continua na lista"


def test_criar_perfil_passa_pelo_gravador_da_aba_perfis(
        _aba07, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2109-O-CRIAR-PERFIL-LEVA-A-ABA-PERFIS: um gravador, dois caminhos de
    chegada. ARRANQUE a chamada ao `a10_perfis.criar_para_o_jogo` e este teste
    reprova — a aba Lançadores teria um segundo gravador de perfil."""
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis

    desenho, a07 = _aba07
    pedidos: list[tuple] = []
    monkeypatch.setattr(a10_perfis, "criar_para_o_jogo",
                        lambda ctx, p, *, classes, nome_do_jogo:
                        pedidos.append((classes, nome_do_jogo)) or "ok")
    _escolher(monkeypatch, a07, desenho.CRIAR_PERFIL)
    a07.confirmar_o_perfil(_Ctx(), {"forma": {desenho.ESCOLHA: _JANELA}}, None)
    assert pedidos == [((_JANELA,), "Wo Long")]
    miolo = desenho.miolo_da_escolha_html(
        desenho.CRIAR_PERFIL, "Steam",
        [desenho.JogoParaEscolher(chave=_JANELA, nome="Wo Long")])
    assert 'href="10-perfis.html"' in miolo, (
        "o confirmar do perfil não leva à aba Perfis — o perfil nasceria sem "
        "ela ver onde")
