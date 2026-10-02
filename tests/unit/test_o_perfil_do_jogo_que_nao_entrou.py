"""PERFIL-MUDO-01 — o perfil do jogo que não entrou, e a janela que não dizia."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_o_perfil_do_jogo_que_nao_entrou: importa código da janela GTK")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.painel_no_jogo import aviso_do_perfil
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.profiles.porque_nao_entrou import (
    campos_reprovados,
    frase_do_perfil_que_nao_entrou,
    perfis_que_nao_entraram,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
)

JANELA_DO_PRAGMATA: dict[str, Any] = {
    "wm_class": "steam_app_3357650",
    "wm_name": "PRAGMATA",
    "exe_basename": "wine64-preloader",
}


def _perfil(nome: str, **criterio: Any) -> Profile:
    return Profile(name=nome, match=MatchCriteria(**criterio))


def test_o_perfil_do_pragmata_aparece_com_o_campo_que_reprovou() -> None:
    """O caso literal de 10/08. Morde em `perfis_que_nao_entraram`."""
    pragmata = _perfil(
        "Pragmata",
        window_class=["steam_app_3357650"],
        process_name=["PRAGMATA.exe"],
    )
    achados = perfis_que_nao_entraram(JANELA_DO_PRAGMATA, [pragmata])

    assert len(achados) == 1
    achado = achados[0]
    assert achado.nome == "Pragmata"
    assert achado.e_regra_deste_jogo is True
    assert [r.campo for r in achado.reprovados] == ["process_name"]
    assert achado.reprovados[0].exigido == ["PRAGMATA.exe"]
    assert achado.reprovados[0].observado == "wine64-preloader"


def test_a_frase_diz_o_exigido_e_o_observado_lado_a_lado() -> None:
    """A frase é FACTUAL: nunca manda apagar campo, nunca fala em Proton."""
    achado = perfis_que_nao_entraram(
        JANELA_DO_PRAGMATA,
        [
            _perfil(
                "Pragmata",
                window_class=["steam_app_3357650"],
                process_name=["PRAGMATA.exe"],
            )
        ],
    )[0]
    frase = frase_do_perfil_que_nao_entrou(achado)

    assert 'O seu perfil "Pragmata" é deste jogo, mas não entrou' in frase
    assert "nome do processo" in frase, "o rótulo tem de ser o do editor"
    assert '"PRAGMATA.exe"' in frase, "o exigido"
    assert '"wine64-preloader"' in frase, "o observado"
    for proibido in ("apague", "remova", "errado", "incorreto", "Proton", "wine"):
        assert proibido.lower() not in frase.lower().replace("wine64-preloader", "")


def test_sem_o_process_name_o_perfil_entra_e_o_aviso_some() -> None:
    """A contraprova: com o campo fora, não há o que avisar."""
    entra = _perfil("Pragmata", window_class=["steam_app_3357650"])
    assert entra.matches(dict(JANELA_DO_PRAGMATA)) is True
    assert perfis_que_nao_entraram(JANELA_DO_PRAGMATA, [entra]) == []


def test_perfil_generico_que_nao_casou_nao_e_regra_deste_jogo() -> None:
    """Um perfil de FPS que não casou é o funcionamento normal, não defeito."""
    fps = _perfil("FPS", process_name=["cs2", "Cyberpunk2077.exe"])
    achados = perfis_que_nao_entraram(JANELA_DO_PRAGMATA, [fps])

    assert len(achados) == 1
    assert achados[0].e_regra_deste_jogo is False
    frase = frase_do_perfil_que_nao_entrou(achados[0])
    assert frase.startswith('O perfil "FPS" não entrou')
    assert "é deste jogo" not in frase


def test_catch_all_e_manual_ficam_de_fora() -> None:
    """Catch-all casa com tudo; ``MatchManual`` nunca casa POR ESCOLHA dela."""
    catch_all = Profile(name="fallback", match=MatchAny())
    so_manual = Profile(name="coop_local", match=MatchManual())
    vazio = _perfil("vazio")

    achados = perfis_que_nao_entraram(
        JANELA_DO_PRAGMATA, [catch_all, so_manual, vazio]
    )
    assert achados == []


def test_fora_de_janela_de_jogo_nada_e_regra_deste_jogo() -> None:
    """No desktop não há appid em foco — nenhum perfil pode ser "deste jogo"."""
    janela_de_desktop = {
        "wm_class": "firefox",
        "wm_name": "Aurora",
        "exe_basename": "firefox",
    }
    pragmata = _perfil(
        "Pragmata",
        window_class=["steam_app_3357650"],
        process_name=["PRAGMATA.exe"],
    )
    achados = perfis_que_nao_entraram(janela_de_desktop, [pragmata])
    assert len(achados) == 1
    assert achados[0].e_regra_deste_jogo is False


@pytest.mark.parametrize(
    ("criterio", "campo", "rotulo"),
    [
        ({"window_class": ["steam_app_999"]}, "window_class", "classe da janela"),
        ({"window_title_regex": "ZELDA"}, "window_title_regex", "título da janela"),
        ({"process_name": ["PRAGMATA.exe"]}, "process_name", "nome do processo"),
    ],
)
def test_cada_campo_reprova_com_o_rotulo_do_editor(
    criterio: dict[str, Any], campo: str, rotulo: str
) -> None:
    """Os três campos são cobertos, e o rótulo é o que ela lê no editor."""
    reprovados = campos_reprovados(
        MatchCriteria(**criterio), dict(JANELA_DO_PRAGMATA)
    )
    assert [r.campo for r in reprovados] == [campo]
    assert reprovados[0].rotulo == rotulo


def test_campo_que_casa_nao_entra_na_lista_de_reprovados() -> None:
    """Só o que reprovou é relatado — o resto passou e não é assunto."""
    match = MatchCriteria(
        window_class=["steam_app_3357650"],
        process_name=["PRAGMATA.exe"],
    )
    reprovados = campos_reprovados(match, dict(JANELA_DO_PRAGMATA))
    assert [r.campo for r in reprovados] == ["process_name"]


def test_a_caixa_do_r12_continua_valendo_no_diagnostico() -> None:
    """`Sackboy.exe` vs. `sackboy.exe` casa — e não pode virar "reprovado"."""
    janela = {"wm_class": "steam_app_1", "wm_name": "", "exe_basename": "Sackboy.exe"}
    assert campos_reprovados(MatchCriteria(process_name=["sackboy.exe"]), janela) == []


def test_sem_dado_no_campo_a_frase_diz_isso_em_vez_de_aspas_vazias() -> None:
    """Os dois backends de Wayland devolvem ``exe_basename`` vazio, sempre."""
    janela = {"wm_class": "steam_app_3357650", "wm_name": "", "exe_basename": ""}
    achado = perfis_que_nao_entraram(
        janela,
        [
            _perfil(
                "Pragmata",
                window_class=["steam_app_3357650"],
                process_name=["PRAGMATA.exe"],
            )
        ],
    )[0]
    frase = frase_do_perfil_que_nao_entrou(achado)
    assert "não vê nome do processo nesta janela" in frase
    assert '""' not in frase


def test_varios_valores_exigidos_saem_com_ou() -> None:
    """Lista é OR dentro do campo, e a frase tem de dizer isso."""
    achado = perfis_que_nao_entraram(
        JANELA_DO_PRAGMATA,
        [
            _perfil(
                "Ação",
                window_class=["steam_app_3357650"],
                process_name=["NieR.exe", "Sifu.exe", "HiFiRush.exe"],
            )
        ],
    )[0]
    frase = frase_do_perfil_que_nao_entrou(achado)
    assert '"NieR.exe", "Sifu.exe" ou "HiFiRush.exe"' in frase


def test_a_aba_mostra_a_frase_e_diz_qual_perfil_valeu() -> None:
    """Morde em `aviso_do_perfil`. Arranque: não anexar o `active_profile`."""
    aviso = aviso_do_perfil(
        {
            "active_profile": "fallback",
            "perfil_do_jogo_que_nao_entrou": [
                {"nome": "Pragmata", "frase": 'O seu perfil "Pragmata" não entrou: X.'}
            ],
        }
    )
    assert aviso is not None
    assert 'O seu perfil "Pragmata" não entrou' in aviso
    assert 'Enquanto isso, vale o perfil "fallback".' in aviso


def test_a_aba_cala_quando_nao_ha_o_que_dizer() -> None:
    """Lista vazia, chave ausente e estado sem daemon: nada na tela."""
    assert aviso_do_perfil(None) is None
    assert aviso_do_perfil({}) is None
    assert aviso_do_perfil({"perfil_do_jogo_que_nao_entrou": []}) is None
    assert aviso_do_perfil({"perfil_do_jogo_que_nao_entrou": "não é uma lista"}) is None


def test_duas_regras_do_mesmo_jogo_aparecem_as_duas() -> None:
    """Ela teve ``Pragmata`` e ``Pragmata2`` no disco em 01/08."""
    aviso = aviso_do_perfil(
        {
            "active_profile": "fallback",
            "perfil_do_jogo_que_nao_entrou": [
                {"nome": "Pragmata", "frase": "A."},
                {"nome": "Pragmata2", "frase": "B."},
            ],
        }
    )
    assert aviso is not None
    assert aviso.splitlines()[:2] == ["A.", "B."]


def test_sem_perfil_ativo_o_aviso_sai_sem_o_fecho() -> None:
    """Daemon sem perfil ativo: afirma o que sabe e cala sobre o resto."""
    aviso = aviso_do_perfil(
        {"perfil_do_jogo_que_nao_entrou": [{"nome": "P", "frase": "A."}]}
    )
    assert aviso == "A."


class _StoreDublado:
    def __init__(self, classe: str, exe: str = "wine64-preloader") -> None:
        self.window_detect_current_class = classe
        self.window_detect_current_name = ""
        self.window_detect_current_exe = exe


class _Handlers(IpcHandlersMixin):
    """Só o que `_perfil_que_nao_entrou` consome — molde do JOGO-01."""

    def __init__(self, store: Any) -> None:
        self.store = store


@pytest.fixture
def _disco(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Conta quantas vezes o disco foi lido, e serve o perfil do caso dela."""
    leituras: list[int] = []
    pragmata = _perfil(
        "Pragmata",
        window_class=["steam_app_3357650"],
        process_name=["PRAGMATA.exe"],
    )

    generico = _perfil("FPS", process_name=["cs2", "Cyberpunk2077.exe"])

    def _load() -> list[Profile]:
        leituras.append(1)
        return [pragmata, generico]

    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.loader.load_all_profiles", _load
    )
    return leituras


def test_o_daemon_manda_a_frase_pronta_do_perfil_deste_jogo(
    _disco: list[int],
) -> None:
    """A ponta do daemon: o estado carrega nome e frase, prontos para a tela."""
    handlers = _Handlers(_StoreDublado("steam_app_3357650"))
    achados = handlers._perfil_que_nao_entrou()

    assert [a["nome"] for a in achados] == ["Pragmata"]
    assert "PRAGMATA.exe" in achados[0]["frase"]
    assert "wine64-preloader" in achados[0]["frase"]


def test_fora_de_jogo_nao_toca_no_disco(_disco: list[int]) -> None:
    """No desktop a resposta é `[]` — e sem `load_all_profiles`.

    Morde na guarda do appid. Arranque: remover o `return []` antecipado, e o
    `state_full` (10 Hz) passa a ler os 14 perfis do disco dela a cada tique,
    com ela parada no navegador. É o poller cego que esta casa já pagou uma vez
    (104% de um núcleo).
    """
    handlers = _Handlers(_StoreDublado("firefox", exe="firefox"))
    assert handlers._perfil_que_nao_entrou() == []
    assert _disco == [], "leu o disco fora de janela de jogo"


def test_o_cache_evita_reler_o_disco_a_cada_tique(_disco: list[int]) -> None:
    """Dez tiques com a mesma janela = UMA leitura de disco.

    Morde no cache. Arranque: sem ele são 10 leituras aqui — e ~140 JSON por
    segundo na máquina dela, já que o `state_full` roda a 10 Hz.
    """
    handlers = _Handlers(_StoreDublado("steam_app_3357650"))
    for _ in range(10):
        handlers._perfil_que_nao_entrou()
    assert len(_disco) == 1


def test_mudar_de_janela_invalida_o_cache(_disco: list[int]) -> None:
    """Cache que não invalida vira mentira: o aviso do jogo anterior ficaria."""
    store = _StoreDublado("steam_app_3357650")
    handlers = _Handlers(store)
    handlers._perfil_que_nao_entrou()
    store.window_detect_current_exe = "PRAGMATA.exe"
    achados = handlers._perfil_que_nao_entrou()

    assert len(_disco) == 2, "a mudança de executável tinha de recalcular"
    assert achados == [], "com o exe casando, o perfil entra e não há aviso"
