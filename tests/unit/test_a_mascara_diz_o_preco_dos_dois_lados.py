"""MASCARA-QUE-GRUDA-01 — a aba Perfis diz o preço, dos DOIS lados e na tela.

Decisão dela, 22/08/2026: *"A máscara deve vir da escolha do user."* E a sprint,
na mesma página: uma tela que oferece Xbox e DualSense **sem dizer o que cada um
custa não é escolha, é sorteio**.

O que existia antes deste arquivo: a frase do preço do Xbox
(`texto_do_custo_da_mascara`, MASCARA-CUSTO-01, 01/08) e um **tooltip** no botão
do Xbox (ESCOLHA-DELA-VENCE-01/E4). Tooltip é para quem já desconfia — ela pediu
a etiqueta em 01/08 e seguiu trocando a máscara à mão perfil a perfil. Agora a
frase fica na tela, embaixo dos botões, para a máscara marcada.

O que este arquivo trava é o que a tela pode e não pode AFIRMAR:

* Xbox: o que o descritor não tem. É medido — os 8 eixos do vpad uinput são
  ABS_X/Y/RX/RY/Z/RZ/HAT0X/HAT0Y, nenhum IMU, e não há campo de touchpad;
* DualSense: o que ela ganha, MAIS o endereço da medição que sustenta. A H1 de
  julho ("o jogo ignora o gamepad virtual") FOI remedida em 22/07 pela
  HARMONIA-MASK-01, em três jogos nomeados — corrigido em 23/08, quando se
  mediu que este arquivo pinava a afirmação contrária;
* nenhum dos dois marcado: o que `gamepad_flavor: null` faz. Não é erro — é o
  que os presets de gênero shipam desde hoje.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# TESTE-HONESTO-01/E1 (24/08/2026): a guarda vem ANTES do import de
# `home_actions`/`profiles_actions`, que fazem `import gi` incondicional
# (`home_actions.py:34` via `base.py:9`; `profiles_actions.py:16`). Sem ela,
# este arquivo estourava ERRO DE COLETA no CI sem PyGObject (medido: simulação
# do job `lint-test` com `gi`/`cairo` bloqueados via `sys.meta_path`).
exigir_gi_real("o preço da máscara dos dois lados")

from typing import Any

from hefesto_dualsense4unix.app.actions.home_actions import (
    TEXTO_CUSTO_MASCARA_XBOX,
)
from hefesto_dualsense4unix.app.actions.profiles_actions import (
    TEXTO_MASCARA_DUALSENSE_VALIDADA,
    TEXTO_MASCARA_SEM_ESCOLHA,
    texto_do_preco_da_mascara,
)


class _Selector:
    """O dublê mínimo de seletor que o editor usa (mesmo da ESCOLHA-DELA-VENCE)."""

    def __init__(self, ativo: str | None = None) -> None:
        self._active_id = ativo

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        self._active_id = the_id

    def limpar_ativo(self) -> None:
        self._active_id = None


class _Etiqueta:
    """O dublê do `Gtk.Label` do preço: guarda o último texto escrito."""

    def __init__(self) -> None:
        self.texto = ""

    def set_text(self, texto: str) -> None:
        self.texto = texto


def _editor(flavor: str | None) -> Any:
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    class _Editor(ProfilesActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self._mode_kind_selector = _Selector("gamepad")
            self._mode_flavor_selector = _Selector(flavor)
            self._mode_flavor_price_label = _Etiqueta()

    return _Editor()


# ---------------------------------------------------------------------------
# A frase de cada lado
# ---------------------------------------------------------------------------


def test_o_xbox_diz_os_tres_campos_que_o_descritor_nao_tem() -> None:
    """O preço do Xbox é REUSADO da frase-dona, e nomeia os três.

    Um teste que só exigisse `texto != ""` passaria com qualquer frase. As três
    palavras são exigidas pelo nome porque é por elas que se decide: quem joga
    com mira por movimento, quem usa o touchpad como botão.

    Mordida: escrever um texto NOVO aqui em vez de reusar a frase-dona.
    """
    texto = texto_do_preco_da_mascara("xbox")

    assert texto == TEXTO_CUSTO_MASCARA_XBOX, (
        "dois donos da mesma frase derivam — o preço do Xbox vem de "
        "`home_actions.TEXTO_CUSTO_MASCARA_XBOX`"
    )
    for campo in ("giroscópio", "acelerômetro", "touchpad"):
        assert campo in texto, (
            f"o descritor do vpad Xbox não tem {campo}, e a tela não disse"
        )


def test_o_dualsense_diz_o_que_ganha_e_que_foi_validado_em_jogo() -> None:
    """A linha do DualSense diz o que ela ganha, e que isso foi MEDIDO.

    NOTA DATADA — 23/08/2026. Este teste nascera em 22/08 exigindo o contrário:
    que a tela dissesse *"não sabemos"*, porque a H1 de julho *"nunca foi
    reconferida"*. Era o teste PINANDO um fato errado — a forma mais cara do
    defeito, porque arrancar a mentira reprovava a suíte.

    A H1 foi remedida, e a cronologia fecha: portão da H1 em **14/07**
    (`56564de`), vpad em `uhid` em **16/07** (`b0596f0`), e em **22/07** a
    HARMONIA-MASK-01 — decisão dela — registra a máscara dualsense *"validada em
    jogo real (Sackboy/Mad King/Pragmata)"* e a razão do xbox como
    *"**superado** pela validação da Onda Harmonia"*. É essa remedição que virou
    o `DaemonConfig.gamepad_flavor = "dualsense"` de instalação nova.

    Mordida: devolver o "não sabemos"/"nunca foi reconferida" à frase, ou apagar
    a menção aos três jogos e deixar a validação sem endereço.
    """
    texto = texto_do_preco_da_mascara("dualsense")

    assert texto == TEXTO_MASCARA_DUALSENSE_VALIDADA
    baixo = texto.lower()
    for fantasma in ("não sabemos", "nunca foi reconferida", "não foi reconferida"):
        assert fantasma not in baixo, (
            f"a tela voltou a dizer {fantasma!r} sobre a máscara DualSense — a "
            "H1 foi remedida em 22/07 (HARMONIA-MASK-01), em três jogos "
            "nomeados, e é essa remedição que virou o default do daemon"
        )
    assert "validada em jogo real" in baixo, (
        "a linha do DualSense deixou de dizer que a máscara foi validada — sem "
        "isso ela lê como escolha sem respaldo, e empurra para a Xbox"
    )
    # Os três jogos são o ENDEREÇO da medição: sem eles é afirmação sem prova.
    for jogo in ("Sackboy", "Mad King", "Pragmata"):
        assert jogo in texto, (
            f"a validação perdeu o endereço: {jogo} saiu da frase"
        )
    # E o que se GANHA também é dito: é a metade que faz a escolha ser escolha.
    for campo in ("giroscópio", "acelerômetro", "touchpad"):
        assert campo in texto, (
            f"o {campo} é o que o DualSense preserva, e a tela não disse"
        )


def test_sem_escolha_a_tela_explica_o_vazio_em_vez_de_parecer_defeito() -> None:
    """Dois botões apagados são o estado NORMAL, e leem como tela quebrada.

    É o que os presets de gênero shipam desde 22/08 e o que um perfil novo
    nasce sendo. A frase existe para o vazio ter nome.

    Mordida: devolver `""` para `None` — a linha some e o vazio volta a parecer
    erro de carregamento.
    """
    assert texto_do_preco_da_mascara(None) == TEXTO_MASCARA_SEM_ESCOLHA
    assert texto_do_preco_da_mascara(None), "o vazio ficou sem explicação"
    assert "mantém" in texto_do_preco_da_mascara(None), (
        "a frase tem de dizer o que ATIVAR o perfil faz com a máscara: nada"
    )


def test_payload_desconhecido_nao_vira_afirmacao_sobre_giroscopio() -> None:
    """Máscara que ninguém reconhece cai no "sem escolha", nunca num preço.

    Mesma família do `or "xbox"` que esta aba já teve: um valor estranho
    virando afirmação sobre o que o jogo recebe.
    """
    for estranho in ("", "desconhecido", 0, [], {}, "nintendo"):
        assert texto_do_preco_da_mascara(estranho) == TEXTO_MASCARA_SEM_ESCOLHA, (
            f"{estranho!r} virou preço: a janela afirmou o que não sabe"
        )


# ---------------------------------------------------------------------------
# A etiqueta acompanha o gesto dela
# ---------------------------------------------------------------------------


def test_o_gesto_na_mascara_troca_a_etiqueta() -> None:
    """Clicar em Xbox troca a linha, e a marca de gesto continua subindo.

    Mordida: tirar o `_atualizar_preco_da_mascara` do handler — a etiqueta
    congela no preço da máscara ANTERIOR, que é pior que não haver etiqueta.
    """
    editor = _editor(None)
    editor._mode_flavor_selector.set_active_id("xbox")
    editor._on_mode_flavor_changed(editor._mode_flavor_selector)

    assert editor._mode_flavor_price_label.texto == TEXTO_CUSTO_MASCARA_XBOX
    assert editor._modo_tocado is True, (
        "mexer na máscara é gesto de modo (PERFIL-SALVA-TUDO-01)"
    )

    editor._mode_flavor_selector.set_active_id("dualsense")
    editor._on_mode_flavor_changed(editor._mode_flavor_selector)
    assert editor._mode_flavor_price_label.texto == TEXTO_MASCARA_DUALSENSE_VALIDADA


def test_abrir_outro_perfil_troca_a_etiqueta_sem_gesto_nenhum() -> None:
    """O populate atualiza a etiqueta — e `limpar_ativo` NÃO emite "changed".

    Este é o caminho que morde de verdade: abrir um perfil em Xbox e depois um
    sem opinião deixaria, sem esta linha, o preço do Xbox na tela sobre um
    perfil que não escolhe máscara nenhuma.

    Mordida: tirar o `_atualizar_preco_da_mascara` do `_set_mode_editor`.
    """
    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    editor = _editor("xbox")
    editor._set_mode_editor(ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox"))
    assert editor._mode_flavor_price_label.texto == TEXTO_CUSTO_MASCARA_XBOX

    editor._set_mode_editor(ProfileModeConfig(kind="gamepad", gamepad_flavor=None))
    assert editor._mode_flavor_price_label.texto == TEXTO_MASCARA_SEM_ESCOLHA
    assert editor._mode_flavor_selector.get_active_id() is None
    assert editor._modo_tocado is False, "populate não é gesto dela"


def test_a_etiqueta_e_montada_na_secao_do_modo_e_e_visivel() -> None:
    """A frase tem de estar num `Gtk.Label` da seção, não só em tooltip.

    O pedido de 01/08 era a etiqueta; o que se entregou naquele dia foi o
    tooltip, e ela continuou trocando a máscara perfil a perfil.

    Mordida: apagar o `pack_start` da etiqueta e deixar só o `set_tooltips`.
    """
    import inspect

    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    fonte = inspect.getsource(ProfilesActionsMixin._install_mode_section)
    assert "texto_do_preco_da_mascara" in fonte
    assert "opts.pack_start(preco" in fonte, (  # (noqa-acento) variável
        "a etiqueta de preço não é empacotada na seção do modo — sem isso ela "
        "existe no código e não na tela"
    )
    # E o tooltip continua: ele serve ao botão que NÃO está marcado.
    assert "flavor_sel.set_tooltips(" in fonte


def test_a_montagem_nao_nasce_com_xbox_marcado() -> None:
    """Nenhum botão marcado antes de alguém escolher.

    A montagem fazia `flavor_sel.set_active_id("xbox")`. Se algum caminho
    mostrar o editor sem passar por `_set_mode_editor`, o Salvar gravaria
    `xbox` no arquivo dela — e desde `2b11172` isso gruda.

    Mordida: devolver o `set_active_id("xbox")` à montagem.
    """
    import inspect

    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    fonte = inspect.getsource(ProfilesActionsMixin._install_mode_section)
    assert 'flavor_sel.set_active_id("xbox")' not in fonte, (
        "a montagem voltou a marcar Xbox sozinha"
    )
    assert "flavor_sel.limpar_ativo()" in fonte
