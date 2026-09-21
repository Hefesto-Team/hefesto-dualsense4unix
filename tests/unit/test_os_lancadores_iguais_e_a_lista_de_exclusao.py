"""OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01 — as réguas.

A E1 é o dono da lista (`integrations/lista_de_exclusao.py`), e ela é um
GUARDA-CHUVA: excluir escreve nas três listas por feature que já existiam
(entrada, pino, atalho); tirar sai delas — e SÓ das que a exclusão escreveu.

TODA RÉGUA AQUI DESVIA O `XDG_CONFIG_HOME` para uma pasta de teste. As três
listas moram na configuração de verdade dela, e uma régua que escrevesse lá
tiraria jogos do Proton pinado na máquina dela.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

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


def test_excluir_escreve_nas_tres_listas() -> None:
    """ARRANQUE o laço de `LISTAS` e este teste reprova: o jogo excluído
    continuaria com o Proton pinado e o atalho de inicialização."""
    assert lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões") == "adicionado"
    assert _nas_listas(_APPID) == {"entrada": True, "pino": True, "atalho": True}
    assert lx.contem(_CHAVE)


def test_tirar_sai_das_tres() -> None:
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
    """As três listas falam appid da Steam; o emulador é um processo para todas
    as ROMs e não tem atalho nem pino. Ele entra na lista e nenhuma das três
    ganha linha."""
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
    MEIO excluído — sem entrada e sem pino, mas com o atalho —, que é o estado
    que a D-2109-A-EXCLUSAO-E-TUDO-OU-NADA existe para não ter."""
    monkeypatch.setitem(lx._POR, "atalho", lambda a: "erro")
    assert lx.adicionar(_CHAVE, lancador="steam", nome="Guardiões") == "erro"
    assert _nas_listas(_APPID) == {"entrada": False, "pino": False, "atalho": False}
    assert lx.ler() == []


def test_a_migracao_traz_o_este_jogo_nao_funciona() -> None:
    """D-2109-A-LISTA-VELHA-VIRA-EXCLUSAO. ARRANQUE `escritas_herdadas` e o
    último assert reprova: tirar o jogo migrado deixaria a entrada para trás, e
    ele voltaria ao Hefesto pela metade."""
    slo.add_appid_to_steam_input_allowlist("3357650", nota="este jogo não funciona")
    migradas = lx.migrar_a_lista_velha(lambda a: "PRAGMATA")
    assert migradas == ["steam_app_3357650"]
    (entrada,) = lx.ler()
    assert entrada.nome == "PRAGMATA" and entrada.nota == lx.NOTA_DA_MIGRACAO
    assert set(entrada.escritas) == {"entrada", "pino", "atalho"}
    assert lx.migrar_a_lista_velha(lambda a: "PRAGMATA") == [], "migrou duas vezes"
    lx.tirar("steam_app_3357650")
    assert _nas_listas("3357650") == {"entrada": False, "pino": False, "atalho": False}


def test_a_migracao_sem_nome_nao_cai() -> None:
    slo.add_appid_to_steam_input_allowlist("42", nota="x")

    def explode(appid: str) -> str:
        raise RuntimeError("sem manifest")

    assert lx.migrar_a_lista_velha(explode) == ["steam_app_42"]
    assert lx.ler()[0].nome == "o jogo 42"


def test_a_linha_de_comando_do_pino_passa_pelo_dono() -> None:
    """Um dono só para o formato do `jogos_fora_do_pino.txt`: a CLI e a lista
    de exclusão escrevem pela MESMA função."""
    assert "nomear_fora_do_pino" in inspect.getsource(proton_pin._cmd_fora_do_pino)
    assert "devolver_ao_pino" in inspect.getsource(proton_pin._cmd_de_volta_ao_pino)
