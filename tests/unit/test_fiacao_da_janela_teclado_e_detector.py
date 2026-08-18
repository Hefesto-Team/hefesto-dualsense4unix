"""A fiação na JANELA (onda 2): o interruptor do teclado, o gesto que funciona
e a linha honesta do detector de janela.

Três queixas medidas, três portões:

1. **EMULACAO-NO-JOGO-01/E1.** O único interruptor da aba dizia "Emular
   mouse+teclado" e governava só o mouse — o teclado emulado não tinha
   interruptor nenhum. Foi por isso que ela concluiu, com razão, que estar "com
   o modo mouse teclado desligado" não deveria mandar Alt+Tab dentro do jogo.
2. **EMULACAO-NO-JOGO-01/E2.** A tela ensinava "segure o botão PS", e o hold do
   PS vem desligado de fábrica por decisão registrada. Ela seguiu a tela e o
   gesto não fez nada.
3. **JANELA-CEGA-01.** O ``state_full`` publica o estado do detector de janela
   desde 28/07 e nenhuma aba lia: "o perfil não troca quando eu abro o jogo"
   não tinha como ser distinguido de "o perfil está errado".

Os portões de estrutura leem o XML do Glade e a árvore de sintaxe do Python —
rodam na CI sem GTK e ainda assim mordem quando alguém reescreve o texto. Os
portões de TEXTO chamam as duas funções puras, que são o miolo do que ela vê.
"""
from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
GLADE = PACOTE / "gui" / "main.glade"
APP_PY = PACOTE / "app" / "app.py"
EMULACAO_PY = PACOTE / "app" / "actions" / "emulation_actions.py"
DAEMON_PY = PACOTE / "app" / "actions" / "daemon_actions.py"

#: Teto de caracteres do rótulo "Modo jogo" do `emulation_combo_grid`.
#:
#: MEDIDO nesta leva, numa `Gtk.OffscreenWindow` de 1180px com o tema na escala
#: que sai: aquele rótulo NÃO quebra linha, então o comprimento dele é o mínimo
#: de largura do `emulation_combo_grid` (654px com o texto antigo, de 71
#: caracteres) e, somado ao card irmão, é o que define o mínimo de largura da
#: aba Emulação inteira (971px antes, 1006px depois). Cada caractere a mais
#: custa ~8px de largura mínima numa janela que abre com 1180 e cuja aba mais
#: larga já pede 1126. O número 78 dá folga de um punhado de caracteres sobre o
#: texto de hoje sem chegar perto do limite — se alguém precisar de mais, tem de
#: REMEDIR, não subir a constante.
TETO_DO_ROTULO_DE_MODO_JOGO = 78


def _raiz_glade() -> ET.Element:
    return ET.parse(str(GLADE)).getroot()


def _objeto(raiz: ET.Element, ident: str) -> ET.Element:
    for obj in raiz.iter("object"):
        if obj.get("id") == ident:
            return obj
    raise AssertionError(f"objeto {ident!r} não existe em main.glade")


def _prop(obj: ET.Element, nome: str) -> str | None:
    for prop in obj.findall("property"):
        if prop.get("name") == nome:
            return prop.text or ""
    return None


def _rotulos_da_linha_do_switch(raiz: ET.Element, switch_id: str) -> list[str]:
    """Textos dos GtkLabel que dividem a mesma caixa com um GtkSwitch.

    É o rótulo que NOMEIA o interruptor — o que a pessoa lê antes de clicar.
    """
    for caixa in raiz.iter("object"):
        if caixa.get("class") != "GtkBox":
            continue
        filhos = [
            neto
            for filho in caixa.findall("child")
            for neto in filho.findall("object")
        ]
        if not any(
            f.get("class") == "GtkSwitch" and f.get("id") == switch_id
            for f in filhos
        ):
            continue
        return [
            _prop(f, "label") or ""
            for f in filhos
            if f.get("class") == "GtkLabel"
        ]
    raise AssertionError(f"nenhuma caixa contém o switch {switch_id!r}")


def _chaves_de_signal_handlers() -> set[str]:
    """As chaves do dict literal de ``HefestoApp._signal_handlers``.

    Por AST e não por busca de texto: é esse dict que o
    ``builder.connect_signals`` recebe, e um ``<signal>`` do Glade sem entrada
    nele vira botão MORTO em silêncio (BUG-GUI-EMULATION-HANDLERS-UNWIRED-01).
    """
    arvore = ast.parse(APP_PY.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == "_signal_handlers":
            for interno in ast.walk(no):
                if isinstance(interno, ast.Dict):
                    return {
                        chave.value
                        for chave in interno.keys
                        if isinstance(chave, ast.Constant)
                        and isinstance(chave.value, str)
                    }
    raise AssertionError("_signal_handlers não encontrado em app.py")


def _metodos(caminho: Path) -> set[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    return {
        no.name for no in ast.walk(arvore) if isinstance(no, ast.FunctionDef)
    }


def _refreshers_da_aba(aba: str) -> tuple[str, ...]:
    """A tupla de ``_REFRESH_POR_ABA`` para uma aba, lida por AST."""
    arvore = ast.parse(APP_PY.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Dict):
            continue
        for chave, valor in zip(no.keys, no.values, strict=False):
            if (
                isinstance(chave, ast.Constant)
                and chave.value == aba
                and isinstance(valor, ast.Tuple)
            ):
                return tuple(
                    item.value
                    for item in valor.elts
                    if isinstance(item, ast.Constant)
                )
    raise AssertionError(f"{aba!r} não está em _REFRESH_POR_ABA")


# --- E1: o interruptor do teclado existe e o do mouse para de mentir --------


class TestOsDoisInterruptores:
    def test_o_interruptor_do_mouse_nao_promete_mais_o_teclado(self) -> None:
        rotulos = _rotulos_da_linha_do_switch(_raiz_glade(), "mouse_emulation_toggle")
        assert rotulos, "a linha do switch do mouse perdeu o rótulo"
        texto = " ".join(rotulos).lower()
        assert "teclado" not in texto, (
            "o rótulo do interruptor do mouse volta a prometer teclado: "
            f"{rotulos!r}. Ele chama `mouse.emulation.set` e o teclado emulado "
            "tem interruptor próprio — prometer os dois é o defeito que fez ela "
            "concluir que o Alt+Tab não deveria estar acontecendo."
        )
        assert "mouse" in texto

    def test_o_teclado_tem_interruptor_proprio_dentro_da_coluna_teclado(self) -> None:
        raiz = _raiz_glade()
        switch = _objeto(raiz, "keyboard_emulation_toggle")
        assert switch.get("class") == "GtkSwitch"
        sinais = {
            s.get("name"): s.get("handler") for s in switch.findall("signal")
        }
        assert sinais.get("state-set") == "on_keyboard_toggle_set"
        # Dentro da coluna Teclado, ao lado do do mouse: é onde ela procurou.
        coluna = _objeto(raiz, "tab_keyboard")
        assert any(
            obj.get("id") == "keyboard_emulation_toggle"
            for obj in coluna.iter("object")
        ), "o interruptor do teclado saiu da coluna Teclado"
        rotulos = " ".join(_rotulos_da_linha_do_switch(raiz, switch.get("id") or ""))
        assert "teclado" in rotulos.lower()

    def test_o_interruptor_do_teclado_avisa_o_que_se_perde_ao_desligar(self) -> None:
        """Medido no daemon e NÃO é óbvio: desligar não tira só o Alt+Tab.

        Sai também o teclado na tela em L3/R3 e as três regiões do touchpad
        (Backspace/Enter/Delete) — quem usa o controle como teclado de
        acessibilidade perde tudo de uma vez. O aviso é obrigação da interface.
        """
        tooltip = (
            _prop(_objeto(_raiz_glade(), "keyboard_emulation_toggle"), "tooltip-text")
            or ""
        ).lower()
        assert "l3" in tooltip and "touchpad" in tooltip, (
            "o tooltip do interruptor do teclado parou de avisar que desligar "
            f"tira o teclado na tela (L3/R3) e o touchpad: {tooltip!r}"
        )

    def test_o_interruptor_do_teclado_esta_ligado_de_ponta_a_ponta(self) -> None:
        """Glade -> dict de sinais do app -> método do mixin, sem elo frouxo."""
        assert "on_keyboard_toggle_set" in _chaves_de_signal_handlers()
        metodos = _metodos(EMULACAO_PY)
        assert "on_keyboard_toggle_set" in metodos
        assert "_refresh_keyboard_switch" in metodos
        # A chave é populada no bootstrap e relida pelo agregador da aba
        # Emulação (que é o que o botão "Atualizar" e o `switch-page` da aba
        # Emulação chamam). Ela NÃO entrou no gancho da aba Navegação de
        # propósito — hoje esta janela é o único escritor da
        # `keyboard_emulation.flag` no projeto, então não há staleness para
        # corrigir ali; o "por que" está em `app._REFRESH_POR_ABA`.
        fonte = EMULACAO_PY.read_text(encoding="utf-8")
        assert '"_refresh_keyboard_switch",' in fonte, (
            "a chave do teclado saiu do agregador `_refresh_emulation_tab`: ela "
            "para de ser relida no botão Atualizar e mostra a posição do "
            "bootstrap pelo resto da sessão"
        )
        assert "_refresh_keyboard_switch()" in fonte, (
            "a chave do teclado não é mais populada no bootstrap da janela"
        )
        # O gancho da aba Navegação segue com os dois de sempre — se alguém
        # acrescentar o terceiro, `tests/unit/test_notebook_switch_page.py`
        # (que congela a lista com `==`) tem de ser atualizado no mesmo passe.
        assert _refreshers_da_aba("tab_navegacao_dsx") == (
            "_refresh_mouse_tab",
            "_refresh_key_bindings_from_draft",
        )


# --- E2: a tela ensina o gesto que FUNCIONA --------------------------------


def _rotulo_do_modo_jogo() -> str:
    grade = _objeto(_raiz_glade(), "emulation_combo_grid")
    for obj in grade.iter("object"):
        rotulo = _prop(obj, "label") or ""
        if "Modo jogo" in rotulo:
            return rotulo
    raise AssertionError("o rótulo 'Modo jogo' saiu do emulation_combo_grid")


class TestOGestoQueFunciona:
    def test_a_tela_ensina_ps_mais_options(self) -> None:
        rotulo = _rotulo_do_modo_jogo()
        assert "PS + Options" in rotulo, (
            "a linha do 'Modo jogo' parou de ensinar o combo que funciona: "
            f"{rotulo!r}"
        )

    def test_a_tela_nao_manda_mais_segurar_o_ps_para_ligar(self) -> None:
        rotulo = _rotulo_do_modo_jogo().lower()
        assert "segure o botão ps" not in rotulo, (
            "a linha voltou a ensinar o gesto que está DESLIGADO por padrão "
            "(DEFAULT_PS_LONG_PRESS_MS = 0, decisão registrada porque o hold "
            "ligava modo jogo acidental)"
        )

    def test_a_tela_diz_que_segurar_o_ps_vem_desligado(self) -> None:
        rotulo = _rotulo_do_modo_jogo().lower()
        assert "segurar o ps" in rotulo and "desligad" in rotulo, (
            "a linha deixou de avisar que segurar o PS vem desligado — sem isso "
            f"ela tenta o gesto e não entende por que nada acontece: {rotulo!r}"
        )

    def test_o_rotulo_do_modo_jogo_nao_engorda_a_aba_emulacao(self) -> None:
        rotulo = _rotulo_do_modo_jogo()
        # Sem a marcação: o que mede largura é o texto pintado.
        visivel = rotulo.replace("<b>", "").replace("</b>", "")
        assert len(visivel) <= TETO_DO_ROTULO_DE_MODO_JOGO, (
            f"o rótulo tem {len(visivel)} caracteres visíveis (teto "
            f"{TETO_DO_ROTULO_DE_MODO_JOGO}). Ele NÃO quebra linha, então cada "
            "caractere sobe o mínimo de largura da aba Emulação em ~8px — e a "
            "janela abre com 1180. Pôr `wrap` aqui foi medido e recusado: os "
            "dois cards já pedem 1293px naturais contra 1160, então com quebra "
            "o rótulo wrapa no tamanho de projeto e a aba estoura a ALTURA."
        )

    def test_o_rotulo_do_modo_jogo_continua_sem_quebra_de_linha(self) -> None:
        grade = _objeto(_raiz_glade(), "emulation_combo_grid")
        for obj in grade.iter("object"):
            if "Modo jogo" in (_prop(obj, "label") or ""):
                assert _prop(obj, "wrap") is None, (
                    "`wrap` voltou ao rótulo do 'Modo jogo'. Medido nesta leva: "
                    "com quebra o mínimo de largura da aba Emulação cai de "
                    "1006px para 707px (tentador), mas a aba sobe de 626px para "
                    "648px contra um teto de 654px — porque os dois cards pedem "
                    "1293px naturais contra 1160 alocados e o rótulo quebra já "
                    "no tamanho de projeto. Seis pixels não são folga: a CI mede "
                    "com outras fontes e já pediu 431px onde esta máquina pedia "
                    "357."
                )
                return
        raise AssertionError("rótulo não encontrado")


# --- E3: a linha honesta do detector de janela -----------------------------


class TestALinhaDoDetectorNaAbaSistema:
    def test_a_aba_sistema_tem_a_linha_e_ela_reconcilia(self) -> None:
        raiz = _raiz_glade()
        cartao = _objeto(raiz, "storm_card")
        assert any(
            obj.get("id") == "window_detect_diag_label"
            for obj in cartao.iter("object")
        ), "a linha do detector saiu do cartão de saúde da aba Sistema"
        rotulo = _objeto(raiz, "window_detect_diag_label")
        assert _prop(rotulo, "wrap") == "True", (
            "sem `wrap` a frase do detector empurra a largura mínima da aba "
            "Sistema, que não tem rolagem horizontal para onde fugir"
        )
        fonte = DAEMON_PY.read_text(encoding="utf-8")
        # Três entradas: bootstrap, entrar na aba e o botão "Atualizar". Cegar e
        # voltar a ver é o comportamento NORMAL do detector (`seeing` decai),
        # então uma foto só do bootstrap mentiria o resto da sessão.
        assert fonte.count("self._refresh_window_detect_diag()") >= 3


# --- o miolo: as duas funções puras ---------------------------------------
# GUARDA-GI-REAL-01: os dois módulos fazem `import gi` no topo, então a guarda
# vem ANTES do import deles. `pytest.importorskip("gi")` aceitaria o stub que
# outro arquivo de teste planta em sys.modules, e sem guarda nenhuma este módulo
# derrubaria a COLETA no CI headless em vez de pular.
from tests.conftest import exigir_gi_real

exigir_gi_real("fiacao da janela: teclado emulado e detector de janela")

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    MOTIVO_DA_CEGUEIRA_EM_PORTUGUES,
    descrever_deteccao_de_janela,
)
from hefesto_dualsense4unix.app.actions.emulation_actions import (
    descrever_teclado_emulado,
)


class TestAFraseDoTecladoEmulado:
    def test_emitindo_nao_diz_nada(self) -> None:
        ligado, dica = descrever_teclado_emulado(
            {"enabled": True, "device_ativo": True, "despachando": True,
             "bloqueio": None}
        )
        assert ligado is True
        assert dica == ""

    def test_desligado_avisa_o_que_ela_perde(self) -> None:
        ligado, dica = descrever_teclado_emulado(
            {"enabled": False, "device_ativo": False, "despachando": False,
             "bloqueio": "desligada"}
        )
        assert ligado is False
        baixo = dica.lower()
        assert "l3" in baixo and "touchpad" in baixo

    @pytest.mark.parametrize(
        "bloqueio", ["modo_jogo", "vpad_suspenso_pelo_steam_input"]
    )
    def test_pausa_nunca_e_chamada_de_desligado(self, bloqueio: str) -> None:
        """Invariante que o daemon deixou por escrito.

        Nos dois casos de pausa o `enabled` continua TRUE: o teclado dela não
        foi desligado, saiu da frente. A frase tem de ABRIR afirmando "Ligado" —
        abrir com "Desligado" a mandaria procurar um interruptor que já está
        ligado. (Dizer "não foi desligado" mais adiante é o contrário: é a
        explicação.)
        """
        ligado, dica = descrever_teclado_emulado(
            {"enabled": True, "device_ativo": True, "despachando": False,
             "bloqueio": bloqueio}
        )
        assert ligado is True
        assert dica.startswith("Ligado"), (
            f"a frase da pausa abre afirmando o estado errado: {dica!r}"
        )
        assert "pausa" in dica.lower()

    def test_o_jogo_assumiu_promete_a_volta(self) -> None:
        _ligado, dica = descrever_teclado_emulado(
            {"enabled": True, "bloqueio": "vpad_suspenso_pelo_steam_input"}
        )
        assert "fechar o jogo" in dica.lower()

    def test_sem_device_manda_para_a_cura(self) -> None:
        _ligado, dica = descrever_teclado_emulado(
            {"enabled": True, "bloqueio": "sem_device"}
        )
        assert "Sistema" in dica

    @pytest.mark.parametrize("bloco", [None, {}, {"enabled": "sim"}, 7])
    def test_sem_bloco_o_interruptor_nao_afirma_posicao(self, bloco: object) -> None:
        """`None` = "não sei": a chave fica insensível e nada é afirmado."""
        ligado, dica = descrever_teclado_emulado(bloco)
        assert ligado is None
        assert "Sistema" in dica

    def test_motivo_novo_de_um_daemon_mais_novo_nao_vira_mentira(self) -> None:
        ligado, dica = descrever_teclado_emulado(
            {"enabled": True, "bloqueio": "motivo_que_ainda_nao_existe"}
        )
        assert ligado is True
        assert "motivo_que_ainda_nao_existe" in dica


class TestAFraseDoDetectorDeJanela:
    def test_vendo_a_janela_diz_funcionando_e_qual(self) -> None:
        texto = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "xlib",
                "window_detect_healthy": True,
                "window_detect_seeing": True,
                "window_detect_current_class": "steam_app_3357650",
                "window_detect_last_class": "steam_app_3357650",
                "window_detect_reason": None,
            }
        )
        assert "funcionando" in texto
        assert "steam_app_3357650" in texto

    def test_cego_por_janela_wayland_explica_em_portugues(self) -> None:
        """A pendência declarada da JANELA-CEGA-01, na tela e sem jargão."""
        texto = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "xlib",
                "window_detect_healthy": True,
                "window_detect_seeing": False,
                "window_detect_current_class": None,
                "window_detect_last_class": "Hefesto-Dualsense4Unix",
                "window_detect_reason": "sem_foco_x",
            }
        )
        assert "Wayland" in texto and "XWayland" in texto
        assert "não troca sozinho" in texto
        # O sticky NÃO pode reaparecer como se fosse a janela da frente: era
        # exatamente ele que fazia o daemon afirmar saúde estando cego.
        assert "Hefesto-Dualsense4Unix" not in texto
        assert "sem_foco_x" not in texto, "o código cru vazou para a tela"

    def test_healthy_sozinho_nao_declara_sucesso(self) -> None:
        """`healthy` é trinco de mão única e `last_class` é sticky.

        Medido ao vivo em 28/07: os dois afirmavam saúde com o backend
        devolvendo `None` a 2 Hz. Quem manda na frase é `seeing`.
        """
        texto = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "xlib",
                "window_detect_healthy": True,
                "window_detect_last_class": "steam",
                "window_detect_seeing": False,
                "window_detect_reason": "sem_foco_x",
            }
        )
        assert "funcionando" not in texto

    def test_sem_backend_diz_que_nao_funciona_neste_sistema(self) -> None:
        for backend in (None, "", "null"):
            texto = descrever_deteccao_de_janela(
                {"window_detect_backend": backend, "window_detect_seeing": False}
            )
            assert "não funciona neste sistema" in texto
            assert "aba Perfis" in texto, "sem saída, a frase é só má notícia"

    def test_sem_estado_nao_finge_saber(self) -> None:
        for estado in (None, {}, 7, {"outra_coisa": 1}):
            assert "não consegui ler" in descrever_deteccao_de_janela(estado)

    def test_a_frase_nao_diz_a_mesma_coisa_duas_vezes(self) -> None:
        """O motivo do X11 já nomeia o XWayland; repetir é ruído na frase que
        ela mais vai ler. Já quando o motivo é genérico, o caminho ENTRA — é a
        única pista de qual mecanismo está sendo usado."""
        com_caminho_no_motivo = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "xlib",
                "window_detect_seeing": False,
                "window_detect_reason": "sem_foco_x",
            }
        )
        assert com_caminho_no_motivo.count("XWayland") == 1

        motivo_generico = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "wlrctl",
                "window_detect_seeing": False,
                "window_detect_reason": "backend_sem_motivo",
            }
        )
        assert "O Hefesto procura pelo wlrctl" in motivo_generico

    def test_motivo_desconhecido_aparece_cru_em_vez_de_inventado(self) -> None:
        texto = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "portal",
                "window_detect_seeing": False,
                "window_detect_reason": "motivo_novo_do_futuro",
            }
        )
        assert "motivo_novo_do_futuro" in texto
        assert "portal" in texto

    def test_nome_de_janela_com_e_comercial_nao_apaga_a_frase(self) -> None:
        """Pango: um `&` cru fecha o parser e o rótulo fica EM BRANCO.

        Seria a linha honesta desaparecendo justamente quando o nome da janela
        é estranho.
        """
        texto = descrever_deteccao_de_janela(
            {
                "window_detect_backend": "xlib",
                "window_detect_seeing": True,
                "window_detect_current_class": "Dungeons & Dragons <beta>",
            }
        )
        assert "&amp;" in texto and "&lt;beta&gt;" in texto
        assert "& D" not in texto

    def test_todos_os_motivos_do_projeto_tem_traducao(self) -> None:
        """Portão de completude: motivo novo no daemon = frase nova aqui.

        Sem ele, um motivo acrescentado em `window_backends/` cairia no ramo
        "código cru" e ela leria `foco_sem_top_level` na tela.
        """
        from hefesto_dualsense4unix.integrations import window_detect
        from hefesto_dualsense4unix.integrations.window_backends import null, xlib

        do_projeto = {
            valor
            for modulo in (xlib, null, window_detect)
            for nome, valor in vars(modulo).items()
            if nome.startswith("MOTIVO_") and isinstance(valor, str)
        }
        faltando = sorted(do_projeto - set(MOTIVO_DA_CEGUEIRA_EM_PORTUGUES))
        assert not faltando, (
            f"motivos do detector sem tradução: {faltando}. Cada um deles vira "
            "código cru na tela da aba Sistema."
        )
        sobrando = sorted(set(MOTIVO_DA_CEGUEIRA_EM_PORTUGUES) - do_projeto)
        assert not sobrando, (
            f"traduções para motivos que não existem mais: {sobrando}"
        )
