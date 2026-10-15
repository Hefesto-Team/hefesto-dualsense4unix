"""O botão «Padrão» do volume do alto-falante (desenho aprovado em 04/10/2026).

O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01, item 2 da seção «A decisão de 04/10». Ela, sobre o volume:
*«Mesmo do anterior»* (o «Padrão» da vibração). Ligado, o volume do alto-falante deste controle é o
do JOGO (os 100% de sempre, sem ajuste do Hefesto) e a barra fica verde e travada; desligado, ela
ajusta, e o volume que tinha escolhido volta. O microfone fica de fora.

Tudo de mentira: o ``XDG_CONFIG_HOME`` no ``tmp_path``, a ponte que confirma, o WebKit fora da tela.

MORDIDAS: o ``VOLUME_DO_PADRAO`` do applier do perfil; o ``volume_padrao`` do ``DraftConfig`` (o
«Salvar» o apagaria); o ``volume_padrao`` que o gesto grava; o ``:has(.padrao-i.on)`` da folha (a
barra continua arrastável); o «Padrão» no lugar do número.
"""

from __future__ import annotations

import gc
import json
import sys
from typing import Any

import pytest

from tests.unit import test_a02_o_som_de_cada_controle_vai_para_o_perfil as base
from tests.unit.test_a02_o_som_de_cada_controle_vai_para_o_perfil import (  # noqa: F401
    CHAVE_P1,
    P1,
    Ponte,
    _bytes_do_perfil,
    _do_controle,
    _gesto,
    casa,
)

sys.path.insert(0, str(base.RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.core.speaker_scale import (
    percentual_do_volume,
    volume_do_percentual,
)

CEM = volume_do_percentual(100)


def _dele(uniq: str, registrador: int) -> dict[str, Any]:
    return {"uniq": uniq, "transport": "usb", "connected": True, "inputs": {},
            "audio": {"mic_mudo": False}, "speaker": {"volume": registrador, "muted": False}}


def _ctx(registrador: int | None = CEM) -> Any:
    import pacotes

    entrada = _dele(P1, registrador) if registrador is not None else {
        "uniq": P1, "transport": "usb", "connected": True, "inputs": {},
        "audio": {"mic_mudo": False}}
    return pacotes.Contexto(state={"active_profile": base.NOME}, mesa=[],
                            conectados=[entrada], estados={})


def _grava_o_perfil(secao: dict[str, Any] | None) -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchManual,
        Profile,
        ProfileSpeakerConfig,
    )

    controllers = ({CHAVE_P1: ControllerOverrides(speaker=ProfileSpeakerConfig(**secao))}
                   if secao is not None else None)
    loader.save_profile(Profile(name=base.NOME, match=MatchManual(), controllers=controllers),
                        origem="regua")


# --- o que o perfil diz e o que o gesto faz ---------------------------------------------------


def test_perfil_sem_secao_com_o_aparelho_nos_cem_por_cento_e_padrao(casa: Any) -> None:  # noqa: F811
    from pacotes import a02_controles as a02

    assert a02.volume_em_padrao(_ctx(CEM), P1, (CEM, False)) is True
    assert a02.volume_em_padrao(_ctx(), P1, (volume_do_percentual(60), False)) is False, (
        "um volume que ela arrastou sem perfil não é Padrão")
    assert a02.volume_em_padrao(_ctx(None), P1, None) is False, "sem leitura a tela não afirma"


def test_o_perfil_com_volume_escolhido_nao_vira_padrao_sozinho(casa: Any) -> None:  # noqa: F811
    """Quem tinha um volume escolhido segue com ele: o campo novo ausente não muda nada."""
    from pacotes import a02_controles as a02

    _grava_o_perfil({"volume": volume_do_percentual(62), "muted": False})
    assert a02.volume_em_padrao(_ctx(CEM), P1, (CEM, False)) is False


def test_ligar_manda_os_cem_ao_aparelho_e_guarda_o_volume_dela(casa: Any) -> None:  # noqa: F811
    guardado = volume_do_percentual(62)
    _grava_o_perfil({"volume": guardado, "muted": False})
    p = Ponte()
    _gesto("volume-padrao")(_ctx(guardado), {"uniq": P1}, p)

    chamadas = [(n, k) for n, k in p.chamadas if n == "speaker_set"]
    assert chamadas and chamadas[0][1]["volume"] == CEM, p.chamadas
    dele = _do_controle(CHAVE_P1).get("speaker") or {}
    assert dele.get("volume_padrao") is True and dele.get("volume") == guardado, dele


def test_desligar_devolve_o_volume_que_ela_tinha_escolhido(casa: Any) -> None:  # noqa: F811
    guardado = volume_do_percentual(62)
    _grava_o_perfil({"volume": guardado, "muted": False, "volume_padrao": True})
    p = Ponte()
    _gesto("volume-padrao")(_ctx(CEM), {"uniq": P1}, p)

    chamadas = [k for n, k in p.chamadas if n == "speaker_set"]
    assert chamadas and chamadas[0]["volume"] == guardado, p.chamadas
    dele = _do_controle(CHAVE_P1).get("speaker") or {}
    assert dele.get("volume_padrao") is False and dele.get("volume") == guardado, dele


def test_ida_e_volta_nao_perde_o_volume_dela(casa: Any) -> None:  # noqa: F811
    guardado = volume_do_percentual(40)
    _grava_o_perfil({"volume": guardado, "muted": False})
    p = Ponte()
    _gesto("volume-padrao")(_ctx(guardado), {"uniq": P1}, p)   # liga
    _gesto("volume-padrao")(_ctx(CEM), {"uniq": P1}, p)        # desliga
    volumes = [k["volume"] for n, k in p.chamadas if n == "speaker_set"]
    assert volumes == [CEM, guardado], volumes


def test_a_recusa_do_daemon_nao_chega_ao_perfil(casa: Any) -> None:  # noqa: F811
    antes = _bytes_do_perfil()
    p = Ponte(recusa="speaker_set")
    with pytest.raises(RuntimeError, match="não confirmou"):
        _gesto("volume-padrao")(_ctx(CEM), {"uniq": P1}, p)
    assert _bytes_do_perfil() == antes


# --- a tela: a palavra, a barra, o botão --------------------------------------------------------


def test_o_pacote_diz_padrao_no_lugar_do_numero_e_enche_a_barra(
        casa: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from pacotes import a02_controles as a02

    _grava_o_perfil({"volume": volume_do_percentual(62), "muted": False, "volume_padrao": True})
    card = a02.pacote(_ctx(CEM))["cards"][P1]
    assert (card["alto-padrao"], card["alto-num"], card["alto-barra"]) == ("1", "Padrão", 100)

    _grava_o_perfil({"volume": volume_do_percentual(62), "muted": False})
    card = a02.pacote(_ctx(volume_do_percentual(62)))["cards"][P1]
    assert card["alto-padrao"] == "" and card["alto-num"] == percentual_do_volume(
        volume_do_percentual(62))


# --- o perfil: o disco, o «Salvar» e a ativação --------------------------------------------------


def test_sem_opiniao_a_chave_nem_aparece_no_arquivo() -> None:
    from hefesto_dualsense4unix.profiles.schema import ProfileSpeakerConfig

    assert "volume_padrao" not in ProfileSpeakerConfig(volume=102).model_dump(mode="json")
    assert ProfileSpeakerConfig(volume=102, volume_padrao=True).model_dump(
        mode="json")["volume_padrao"] is True


def test_o_salvar_do_rodape_nao_apaga_o_padrao() -> None:
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchManual,
        Profile,
        ProfileSpeakerConfig,
    )

    prof = Profile(
        name="x", match=MatchManual(),
        speaker=ProfileSpeakerConfig(volume=70, volume_padrao=True),
        controllers={CHAVE_P1: ControllerOverrides(
            speaker=ProfileSpeakerConfig(volume=50, volume_padrao=True))})
    volta = DraftConfig.from_profile(prof).to_profile("x", priority=prof.priority)
    assert volta.speaker is not None and volta.speaker.volume_padrao is True
    assert volta.controllers is not None
    assert volta.controllers[CHAVE_P1].speaker.volume_padrao is True  # type: ignore[union-attr]


@pytest.mark.parametrize(("flag", "esperado"), [(True, CEM), (False, 60), (None, 60)])
def test_a_ativacao_aplica_os_cem_so_com_o_botao_ligado(flag: bool | None, esperado: int) -> None:
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile, ProfileSpeakerConfig

    chamadas: list[int] = []
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.speaker_applier = lambda volume, muted, **_k: chamadas.append(volume) or "aplicado"
    prof = Profile(name="x", match=MatchManual(),
                   speaker=ProfileSpeakerConfig(volume=60, volume_padrao=flag))
    gerente.apply_speaker(prof, origin="regua")
    assert chamadas == [esperado]


# --- sem perfil ativo: o computador é o dono (O-PADRAO-DO-ALTO-FALANTE-DESLIGA-SEM-PERFIL-01) ---


def _ctx_sem_perfil(registrador: int | None = CEM, uniq: str = P1) -> Any:
    import pacotes

    entrada = _dele(uniq, registrador) if registrador is not None else {
        "uniq": uniq, "transport": "usb", "connected": True, "inputs": {},
        "audio": {"mic_mudo": False}}
    return pacotes.Contexto(state={"active_profile": ""}, mesa=[],
                            conectados=[entrada], estados={})


def _do_computador(chave: str = CHAVE_P1) -> dict[str, Any]:
    """O que o ``maquina.json`` guarda deste controle, lido do disco, nunca do cache."""
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    entrada = carregar_maquina().computador.controles.get(chave)
    return entrada.model_dump(mode="json", exclude_unset=True) if entrada is not None else {}


def _bytes_do_computador() -> bytes:
    from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina

    alvo = caminho_da_maquina()
    return alvo.read_bytes() if alvo.exists() else b""


def test_sem_perfil_o_clique_desliga_o_padrao_e_o_computador_guarda(casa: Any) -> None:  # noqa: F811
    """O defeito de 05/10: sem perfil, o clique mandava os 100% e a tela seguia em «Padrão».

    MORDIDA: devolver o ``if not nome: return`` ao ``_lembrar_do_som`` — nada é gravado, o pacote
    seguinte volta a dizer «Padrão» e a barra segue travada.
    """
    from pacotes import a02_controles as a02

    assert a02.volume_em_padrao(_ctx_sem_perfil(), P1, (CEM, False)) is True, (
        "o ponto de partida: aparelho nos 100% e nada gravado é Padrão")
    p = Ponte()
    _gesto("volume-padrao")(_ctx_sem_perfil(), {"uniq": P1}, p)

    chamadas = [k for n, k in p.chamadas if n == "speaker_set"]
    assert chamadas and chamadas[0]["volume"] == CEM, p.chamadas
    dele = _do_computador().get("speaker") or {}
    assert dele.get("volume_padrao") is False and dele.get("volume") == CEM, (
        f"o clique não ficou no computador: {dele!r}")
    assert a02.volume_em_padrao(_ctx_sem_perfil(), P1, (CEM, False)) is False, (
        "a tela segue em «Padrão»: a barra fica travada e ela não ajusta o volume")


def test_sem_perfil_a_tela_destrava_a_barra_e_diz_o_numero(
        casa: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from pacotes import a02_controles as a02

    monkeypatch.setattr(a02, "_ENDERECOS", frozenset({*a02._enderecos_da_pagina(), "alto-padrao"}))
    card = a02.pacote(_ctx_sem_perfil())["cards"][P1]
    assert (card["alto-padrao"], card["alto-num"]) == ("1", "Padrão"), "antes do clique, Padrão"

    _gesto("volume-padrao")(_ctx_sem_perfil(), {"uniq": P1}, Ponte())
    card = a02.pacote(_ctx_sem_perfil())["cards"][P1]
    assert card["alto-padrao"] == "" and card["alto-num"] == percentual_do_volume(CEM), card


def test_sem_perfil_ida_e_volta_guarda_o_volume_que_ela_escolheu(casa: Any) -> None:  # noqa: F811
    """Desliga, arrasta para 40%, liga (100% no aparelho) e desliga: os 40% voltam."""
    guardado = volume_do_percentual(40)
    p = Ponte()
    _gesto("volume-padrao")(_ctx_sem_perfil(), {"uniq": P1}, p)                     # desliga
    _gesto("volume")(_ctx_sem_perfil(CEM), {"uniq": P1, "volume": "alto-falante",
                                            "valor": "40"}, p)                      # arrasta
    _gesto("volume-padrao")(_ctx_sem_perfil(guardado), {"uniq": P1}, p)             # liga
    ligado = _do_computador().get("speaker") or {}
    assert ligado.get("volume_padrao") is True and ligado.get("volume") == guardado, ligado
    _gesto("volume-padrao")(_ctx_sem_perfil(CEM), {"uniq": P1}, p)                  # desliga
    volumes = [k["volume"] for n, k in p.chamadas if n == "speaker_set"]
    assert volumes == [CEM, guardado, CEM, guardado], volumes
    assert (_do_computador().get("speaker") or {}).get("volume_padrao") is False


def test_sem_perfil_o_mudo_e_a_rota_tambem_ficam_no_computador(casa: Any) -> None:  # noqa: F811
    p = Ponte()
    _gesto("mudo")(_ctx_sem_perfil(), {"uniq": P1, "mudo": "alto-falante"}, p)
    assert (_do_computador().get("speaker") or {}).get("muted") is True, _do_computador()
    _gesto("rota")(_ctx_sem_perfil(), {"uniq": P1, "rota": "jogo"}, p)
    assert (_do_computador().get("speaker") or {}).get("rota") == 2, _do_computador()


def test_sem_perfil_o_computador_e_por_controle_e_o_outro_nao_muda(casa: Any) -> None:  # noqa: F811
    """O P2 tem o computador dele; o clique no P1 não encosta ali (de um a quatro jogadores)."""
    p = Ponte()
    _gesto("volume-padrao")(_ctx_sem_perfil(uniq=P1), {"uniq": P1}, p)
    assert _do_computador(CHAVE_P1) and _do_computador("aabbcc000002") == {}


def test_sem_perfil_e_sem_endereco_estavel_fica_calado_como_sempre(casa: Any) -> None:  # noqa: F811
    """Sem identidade não há onde guardar: o gesto funciona e não escreve nada (nem levanta)."""
    antes = _bytes_do_computador()
    avulso = "path:/dev/hidraw3"
    _gesto("volume-padrao")(_ctx_sem_perfil(uniq=avulso), {"uniq": avulso}, Ponte())
    assert _bytes_do_computador() == antes


def test_sem_perfil_e_sem_volume_publicado_a_rota_fica_calada(casa: Any) -> None:  # noqa: F811
    """O aparelho que ainda não publicou o volume: sem jogo, nada a guardar e nenhum recado.

    MORDIDA: tirar o ``sem_jogo`` do ``_o_som_lembrado`` — o gesto levanta «arraste o volume».
    """
    antes = _bytes_do_computador()
    _gesto("rota")(_ctx_sem_perfil(None), {"uniq": P1, "rota": "jogo"}, Ponte())
    assert _bytes_do_computador() == antes


def test_a_recusa_do_daemon_sem_perfil_nao_chega_ao_computador(casa: Any) -> None:  # noqa: F811
    antes = _bytes_do_computador()
    with pytest.raises(RuntimeError, match="não confirmou"):
        _gesto("volume-padrao")(_ctx_sem_perfil(), {"uniq": P1}, Ponte(recusa="speaker_set"))
    assert _bytes_do_computador() == antes


def test_com_perfil_ativo_o_clique_segue_no_perfil_e_o_computador_nao_muda(casa: Any) -> None:  # noqa: F811
    """O caminho de hoje: o jogo guarda o que mudou, o computador fica como estava."""
    antes = _bytes_do_computador()
    _gesto("volume-padrao")(_ctx(CEM), {"uniq": P1}, Ponte())
    assert (_do_controle(CHAVE_P1).get("speaker") or {}).get("volume_padrao") is False
    assert _bytes_do_computador() == antes


# --- a página (WebKit, bancada) -------------------------------------------------------------------

LER = r"""
(function(){
  const chip = document.querySelector('.padrao-i');
  const barra = document.querySelector('.puxa-vol[data-volume="alto-falante"]');
  const cheio = barra.parentElement.querySelector('.cheio');
  const mic = document.querySelector('.puxa-vol[data-volume="microfone"]');
  let focou = false;
  barra.blur(); barra.focus(); focou = document.activeElement === barra; barra.blur();
  return JSON.stringify({
    chip: !!chip, ligado: chip.classList.contains('on'),
    barra_visivel: getComputedStyle(barra).display !== 'none', focou: focou,
    cor: getComputedStyle(cheio).backgroundColor, largura: cheio.style.width,
    mic_visivel: getComputedStyle(mic).display !== 'none',
    chip_h: Math.round(chip.getBoundingClientRect().height),
    gesto: chip.dataset.gesto,
  });
})()
"""


def _na_pagina(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    try:
        return _na_pagina_sem_recolher(passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _na_pagina_sem_recolher(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    mensagens: list[dict[str, Any]] = []
    respostas: list[str] = []
    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("hefesto")
    ucm.connect("script-message-received::hefesto",
                lambda _u, r: mensagens.append(json.loads(r.get_js_value().to_string())))
    view = WebKit2.WebView.new_with_user_content_manager(ucm)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1500, 1200)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(300, lambda: (Gtk.main_quit(), False)[1])
            return False
        js = fila.pop(0)

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.idle_add(seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina("02-controles.html", publicado=False).as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    assert respostas[0] == "ok", f"o BOOTSTRAP do piloto não instalou: {respostas[0]}"
    return [json.loads(r) if r.startswith("{") else r for r in respostas[1:]], mensagens


LIGAR = "document.querySelector('.padrao-i').classList.add('on'); 'ok'"
CLICAR = "document.querySelector('.padrao-i').click(); 'ok'"


def test_ligado_a_barra_do_alto_falante_fica_verde_travada_e_sem_teclado() -> None:
    lidas, _m = _na_pagina([LER, LIGAR, LER])
    antes, _o, depois = lidas
    assert antes["chip"] and antes["barra_visivel"] and not antes["ligado"], antes
    assert antes["chip_h"] == 16, "o botão custa uma linha a mais no cartão"
    assert not depois["barra_visivel"] and not depois["focou"], (
        f"a barra ainda aceita arrasto ou teclado: {depois}")
    assert depois["cor"] != antes["cor"] and depois["largura"] != "", depois
    assert depois["mic_visivel"], "o microfone fica de fora do Padrão"


def test_o_clique_no_botao_manda_o_gesto_com_o_controle() -> None:
    _l, mensagens = _na_pagina([CLICAR])
    gestos = [m for m in mensagens if m.get("gesto") == "volume-padrao"]
    assert gestos, f"o clique não mandou o gesto: {mensagens}"


def test_o_cartao_nao_cresce_com_o_botao() -> None:
    """A conta de altura do cartão (0,37 px de folga) é medida pelo próprio gerador."""
    from hefesto_dualsense4unix.interface import aba02

    assert aba02.ROTULO_PADRAO == "Padrão"
    assert "padrao-i{height:16px" in aba02.CSS.replace(" ", "")
