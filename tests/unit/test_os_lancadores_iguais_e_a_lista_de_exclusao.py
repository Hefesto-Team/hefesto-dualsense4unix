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

import inspect
import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
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
