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
