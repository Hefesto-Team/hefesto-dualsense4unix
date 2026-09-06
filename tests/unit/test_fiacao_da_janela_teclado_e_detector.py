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
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
APP_PY = PACOTE / "app" / "app.py"
EMULACAO_PY = PACOTE / "app" / "actions" / "emulation_actions.py"
DAEMON_PY = PACOTE / "app" / "actions" / "daemon_actions.py"


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

    def test_o_interruptor_do_teclado_esta_ligado_de_ponta_a_ponta(self) -> None:
        """Glade -> dict de sinais do app -> método do mixin, sem elo frouxo."""
        assert "on_keyboard_toggle_set" in _chaves_de_signal_handlers()
        metodos = _metodos(EMULACAO_PY)
        assert "on_keyboard_toggle_set" in metodos
        assert "_refresh_keyboard_switch" in metodos
        # A chave é populada no bootstrap e relida pelo agregador da aba
        # Emulação (que é o que o botão "Atualizar" e o `switch-page` da aba
        # Emulação chamam) e, desde 22/08/2026, também pelo gancho da aba onde
        # ela DESENHA — ver o teste do segundo escritor logo abaixo.
        fonte = EMULACAO_PY.read_text(encoding="utf-8")
        assert '"_refresh_keyboard_switch",' in fonte, (
            "a chave do teclado saiu do agregador `_refresh_emulation_tab`: ela "
            "para de ser relida no botão Atualizar e mostra a posição do "
            "bootstrap pelo resto da sessão"
        )
        assert "_refresh_keyboard_switch()" in fonte, (
            "a chave do teclado não é mais populada no bootstrap da janela"
        )
        # O gancho da aba Navegação, congelado com `==` aqui e em
        # `tests/unit/test_notebook_switch_page.py` (que congela as CHAMADAS):
        # mexer na tupla exige os dois arquivos no mesmo passe.
        assert _refreshers_da_aba("tab_navegacao_dsx") == (
            "_refresh_mouse_tab",
            "_refresh_key_bindings_from_draft",
            "_refresh_keyboard_switch",
        )

    def test_o_segundo_escritor_da_flag_obriga_o_gancho_da_aba(self) -> None:
        """SEGUNDO-ESCRITOR-01 (22/08/2026): o gesto PS + R3 virou o interruptor.

        Enquanto esta janela era o único caminho até a
        `keyboard_emulation.flag`, deixar `_refresh_keyboard_switch` fora do
        gancho da aba Navegação era decisão medida: não havia posição a
        reconciliar. A ponte mouse+teclado do PS + R3
        (`daemon/subsystems/hotkey.py`, `_aplicar_ponte`) chama
        `daemon.set_keyboard_emulation(True)`, que persiste por padrão
        (`daemon/protocols.py`) — o interruptor passou a poder estar virado
        quando ela entra na aba.

        A régua é `set_keyboard_emulation(`, não `keyboard.emulation.set`: o
        segundo é o nome do método IPC e NÃO pega a chamada em processo, e foi
        esse grep que sustentou a razão caduca por uma leva inteira. É o portão
        contra repetir o erro: enquanto houver escritor no daemon, o refresher
        fica na tupla.

        Mordida: tirei `_refresh_keyboard_switch` da tupla em `app.py` e
        reprovou; tirei a linha do `set_keyboard_emulation` do `_aplicar_ponte`
        e o `pytest.skip` abaixo apagou o portão, que é o comportamento certo —
        sem segundo escritor não há o que reconciliar.
        """
        hotkey = (PACOTE / "daemon" / "subsystems" / "hotkey.py").read_text(
            encoding="utf-8"
        )
        chamadas = [
            linha
            for linha in hotkey.splitlines()
            if "set_keyboard_emulation(" in linha
            and not linha.lstrip().startswith("#")
        ]
        if not chamadas:
            pytest.skip(
                "o gesto deixou de escrever a flag — sem segundo escritor, o "
                "gancho da aba Navegação volta a ser opcional"
            )

        assert "_refresh_keyboard_switch" in _refreshers_da_aba("tab_navegacao_dsx"), (
            "o gesto PS + R3 escreve a `keyboard_emulation.flag` em "
            f"{len(chamadas)} ponto(s) de `hotkey.py`, e a aba onde o "
            "interruptor DESENHA não o relê ao ser exibida: ela vê a posição "
            "de antes do gesto"
        )


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
        foi desligado, está em pausa. A frase tem de ABRIR afirmando "Ligado" —
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

    def test_a_pausa_do_steam_input_nao_promete_perder_a_luz(self) -> None:
        """NOTA DATADA — 07/08/2026: a frase dizia "o jogo assumiu o controle".

        `CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*, 06/08, grau MEDIDO: num
        jogo da lista de exceções o jogo assume a **entrada**, e a cor e os
        gatilhos dela continuam valendo — o contrário do que "assumiu o
        controle" faz a pessoa concluir. Quem assume tudo é o jogo de **fora**
        da lista.
        """
        _ligado, dica = descrever_teclado_emulado(
            {"enabled": True, "bloqueio": "vpad_suspenso_pelo_steam_input"}
        )
        assert "assumiu o controle" not in dica
        assert "quem entrega o controle é a Steam" in dica

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
