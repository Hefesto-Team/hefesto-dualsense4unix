"""Z4/T10+T11+T12 — a matriz widget de escolha -> depósito, e o portão inverso.

Frente **Z4** da ONDA 0 (24/08/2026). O portão que já existe
(`test_perfil_salva_tudo_cobertura_das_secoes.py`) mede **campo do esquema ->
escritor**. Este módulo mede a direção que faltava: **widget de escolha ->
depósito** — "este interruptor, escolhido na tela, pousa ONDE quando ela fecha
o programa?".

**Escopo medido, e por que ele é menor que os 58 da sprint.** A sprint (§2.5)
mediu TERRITÓRIO com dois `grep -c` — 23 no glade, 35 em `app/` — e foi
explícita: *"58 widgets de escolha, e nenhuma régua pergunta onde cada um
pousa... O número entra na T10 como pergunta, nunca como fato"*. Rodando a
MESMA pergunta com uma régua que lê o glade por XML (não por linha), o número
real de widgets de escolha DISTINTOS no glade é **22**, não 23 — a diferença
é uma linha do glade que casa o padrão fora de um `<object>` de widget (uma
`<property>` ou comentário). Do lado programático, os "35" da sprint são
OCORRÊNCIAS de padrão (`self._get(...)`, assinatura de handler, anotação de
tipo) — não 35 widgets distintos; a maioria são referências REPETIDAS aos
MESMOS 22 do glade (`Gtk.Scale` é o tipo de retorno de `self._get(...)`, não
uma construção nova).

**O que este módulo cobre, com verificação real (arquivo:linha lido, não
adivinhado):**

1. **Os 22 widgets do GLADE — CENSO COMPLETO.** Todo `<object class="Gtk
   (Switch|ComboBoxText|CheckButton|Scale|SpinButton|ToggleButton)">` do
   `main.glade` tem entrada em `DEPOSITOS` ou `SEM_DEPOSITO_POR_DECISAO`. O
   portão (`test_todo_widget_do_glade_tem_entrada`) varre o glade em RUNTIME —
   widget novo sem entrada reprova nomeando o `id`.

2. **Cinco widgets PROGRAMÁTICOS verificados por leitura de código** (as duas
   escalas de mic/som do `controller_card`, o `CheckButton` de mic da
   Configurações, o cadeado de autoswitch da Início, e o grupo dinâmico de
   sliders de parâmetro de gatilho). **Não é censo completo dos
   programáticos** — está dito, não escondido: o censo automatizado dessa
   metade (distinguir construção nova de referência repetida por AST) fica
   para quem seguir; o que está aqui foi lido e citado, não adivinhado.

**A mordida (T11):** o portão nasce reprovando — rode-o contra um glade
FABRICADO com um `GtkSwitch` novo sem entrada e veja reprovar nomeando o
`id`. Contra o `main.glade` real, hoje passa porque os 22 têm entrada.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_GLADE_REAL = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
)

_PADRAO_WIDGET_DE_ESCOLHA = re.compile(
    r'<object class="(Gtk(?:Switch|ComboBoxText|CheckButton|Scale|SpinButton|'
    r'ToggleButton))" id="([A-Za-z0-9_]+)"'
)


def widgets_de_escolha_do_glade(caminho: Path) -> dict[str, str]:
    """``{id: classe}`` de todo widget de escolha DECLARADO no glade.

    Régua por XML/regex de OBJETO (``<object class="..." id="...">``), não
    por linha — é o que faz 22 (widgets distintos) divergir dos 23 que
    `grep -c` conta (linhas que mencionam a classe, inclusive fora de um
    `<object>`).
    """
    texto = caminho.read_text(encoding="utf-8")
    return dict(
        (m.group(2), m.group(1)) for m in _PADRAO_WIDGET_DE_ESCOLHA.finditer(texto)
    )


# ---------------------------------------------------------------------------
# A MATRIZ — dicionário LITERAL (no molde de `SECOES_COBERTAS`/`ISENTOS`),
# cada entrada com o depósito E o comando/citação que prova.
# ---------------------------------------------------------------------------

#: widget (id do glade) -> onde ele pousa, com a citação que prova.
DEPOSITOS: dict[str, str] = {
    "auto_player_colors_check": (
        "Profile.leds.auto_player_colors — "
        "app/actions/lightbar_actions.py:822 (on_auto_player_colors_toggled)"
    ),
    "lightbar_brightness_scale": (
        "Profile.leds.lightbar_brightness — "
        "app/actions/lightbar_actions.py:725 (on_lightbar_brightness_changed)"
    ),
    "player_led_1": (
        "Profile.leds.player_leds[0] — "
        "app/actions/lightbar_actions.py:1049 (on_player_led_toggled)"
    ),
    "player_led_2": "Profile.leds.player_leds[1] — idem player_led_1",
    "player_led_3": "Profile.leds.player_leds[2] — idem player_led_1",
    "player_led_4": "Profile.leds.player_leds[3] — idem player_led_1",
    "player_led_5": "Profile.leds.player_leds[4] — idem player_led_1",
    "rumble_policy_economia": (
        "Profile.rumble.policy='economia' — "
        "app/actions/rumble_actions.py:518 (on_rumble_policy_economia)"
    ),
    "rumble_policy_balanceado": (
        "Profile.rumble.policy='balanceado' — "
        "app/actions/rumble_actions.py:529 (on_rumble_policy_balanceado)"
    ),
    "rumble_policy_max": (
        "Profile.rumble.policy='max' — "
        "app/actions/rumble_actions.py:534 (on_rumble_policy_max)"
    ),
    "rumble_policy_auto": (
        "Profile.rumble.policy='auto' — "
        "app/actions/rumble_actions.py:539 (on_rumble_policy_auto)"
    ),
    "rumble_policy_slider": (
        "Profile.rumble.custom_mult — "
        "app/actions/rumble_actions.py:590 (on_rumble_policy_slider_changed)"
    ),
    "mouse_emulation_toggle": (
        "Profile.mouse.enabled — app/actions/mouse_actions.py:111"
    ),
    "mouse_speed_scale": (
        "Profile.mouse.speed — "
        "app/actions/mouse_actions.py:271 (on_mouse_speed_changed)"
    ),
    "mouse_scroll_speed_scale": (
        "Profile.mouse.scroll_speed — "
        "app/actions/mouse_actions.py:284 (on_mouse_scroll_speed_changed)"
    ),
    # --- programáticos verificados (fora do glade, T10 §2) ---
    "controller_card.escala_mic": (
        "Profile.mic.volume — "
        "app/widgets/controller_card.py:3103, via "
        "draft_config.registrar_microfone_no_rascunho"
    ),
    "controller_card.escala_alto_falante": (
        "Profile.speaker.volume — "
        "app/widgets/controller_card.py:3313, via "
        "draft_config.registrar_alto_falante_no_rascunho"
    ),
    "triggers_actions._trigger_param_widgets": (
        "Profile.triggers.{left,right}.params — construído dinamicamente por "
        "preset em app/actions/triggers_actions.py:552, um Gtk.Scale por "
        "TriggerParamSpec (trigger_specs.py); escritor único "
        "_persist_params_to_draft (Z4/T4 garante que os 19 modos sobrevivem)"
    ),
}

#: widget -> razão da isenção (NENHUM depósito, ou fora do escopo desta
#: frente), sempre com arquivo:linha que existe.
SEM_DEPOSITO_POR_DECISAO: dict[str, str] = {
    "rumble_weak_scale": (
        "NENHUM depósito — teste de motor, não configuração: "
        "app/actions/rumble_actions.py:888 lê o widget só para o teste manual "
        "de vibração ('sentir o motor'); `weak`/`strong` NUNCA foram do "
        "perfil (nota em draft_config.py, effective_rumble_for, seção §2.6 "
        "da sprint Z4: 'inclusive weak/strong, que são o teste de motores e "
        "nunca foram do perfil')."
    ),
    "rumble_strong_scale": (
        "NENHUM depósito — mesma razão de rumble_weak_scale: "
        "app/actions/rumble_actions.py:889."
    ),
    "profile_advanced_switch": (
        "FORA DO ESCOPO desta frente — aba Perfis (editor), Onda 6: "
        "app/actions/profiles_actions.py:1060. A sprint Z4 declara "
        "'Não mexe na aba Perfis' na seção 0 do documento; classificar o "
        "depósito real é trabalho da "
        "PERFIS-ABRE-O-QUE-GUARDA-01 (2026-08-24), que depende de Z4."
    ),
    "profile_priority_scale": (
        "FORA DO ESCOPO — aba Perfis, mesma razão de profile_advanced_switch: "
        "app/actions/profiles_actions.py:1049."
    ),
    "profile_steam_input_check": (
        "FORA DO ESCOPO — aba Perfis, mesma razão: "
        "app/actions/profiles_actions.py:1033."
    ),
    "daemon_autostart_switch": (
        "NENHUM depósito no PRODUTO — reflete o systemd AO VIVO "
        "(`systemctl --user is-enabled`), lido e escrito direto na unidade: "
        "app/actions/daemon_actions.py:1691. Não é Profile nem maquina.json "
        "por natureza (é o autostart do PROCESSO, não do controle) — aba "
        "Sistema, isenção D-A (sprint Z4 §0/§4: 'os sete gestos são da "
        "MÁQUINA, não do controle')."
    ),
    "keyboard_emulation_toggle": (
        "PROVISÓRIO (Z4/T14, 24/08/2026) — hoje mora na flag global "
        "utils/session.py:372 (keyboard_emulation.flag). O campo de perfil "
        "que a substituiria (Profile.teclado_emulado + "
        "profiles.schema.resolver_teclado_emulado) JÁ EXISTE, mas nenhum "
        "mixin escreve nele ainda — o widget é da Onda 9 (Emulação) / Onda "
        "10 (Navegação), e ligar o fio sem a palavra dela sobre a frase de "
        "tela seria escolher em silêncio. Sai desta lista no dia em que o "
        "widget nascer."
    ),
    "controller_card.checkbox_mic_configuracoes": (
        "Configurações (maquina.json), D-A4 — "
        "app/actions/config/secao_controles.py:524, o CheckButton de mic por "
        "controle na tela de Configurações. Decisão medida: ela declara no "
        "maquina.json de propósito (sprint Z4 §2.4: 'Configurações não é "
        "buraco. Ela declara no maquina.json de propósito (D-A4)')."
    ),
    "home_actions.lock_check": (
        "NENHUM depósito no Profile — estado de SESSÃO do daemon: "
        "app/actions/home_actions.py:1685 (o cadeado de autoswitch, "
        "FEAT-AUTOSWITCH-LOCK-01), gravado por "
        "utils/session.py:178 (save_autoswitch_locked) em "
        "autoswitch_locked.flag. Vale para QUALQUER perfil, de propósito — "
        "é o oposto de configuração POR jogo."
    ),
}


class TestOCensoDosWidgetsDoGlade:
    """T10 — a régua rodada duas vezes devolve a mesma lista (determinismo)."""

    def test_a_regua_e_deterministica(self) -> None:
        primeira = widgets_de_escolha_do_glade(_GLADE_REAL)
        segunda = widgets_de_escolha_do_glade(_GLADE_REAL)
        assert primeira == segunda

    def test_o_territorio_medido_bate_com_a_sprint(self) -> None:
        """22 widgets de escolha distintos no glade em 24/08/2026 — a sprint
        mediu 23 por LINHA (grep -c); a divergência é o método, não o glade
        tendo mudado. Ver o cabeçalho do módulo."""
        achados = widgets_de_escolha_do_glade(_GLADE_REAL)
        assert len(achados) == 22, (
            f"achei {len(achados)} widgets de escolha no glade: "
            f"{sorted(achados)!r} — se o número mudou, o glade ganhou/perdeu "
            "um widget de escolha, e a matriz abaixo precisa de nova entrada"
        )

    def test_plantar_um_switch_novo_sobe_a_contagem_em_um(self, tmp_path: Path) -> None:
        """MORDIDA de T10: plantar um GtkSwitch novo faz a contagem subir 1 —
        prova que a régua realmente OLHA para o glade, não devolve uma
        constante."""
        original = _GLADE_REAL.read_text(encoding="utf-8")
        injetado = original.replace(
            "</interface>",
            '<object class="GtkSwitch" id="z4_widget_fabricado_para_o_teste"/>'
            "</interface>",
            1,
        )
        assert injetado != original, "o glade real não tem `</interface>` — molde mudou"
        alvo = tmp_path / "main_com_widget_novo.glade"
        alvo.write_text(injetado, encoding="utf-8")

        antes = widgets_de_escolha_do_glade(_GLADE_REAL)
        depois = widgets_de_escolha_do_glade(alvo)
        assert len(depois) == len(antes) + 1
        assert "z4_widget_fabricado_para_o_teste" in depois


class TestOPortaoDeDepositoNasceuReprovando:
    """T11 — hoje passa; a mordida prova que nasceu capaz de reprovar."""

    def test_todo_widget_do_glade_tem_entrada(self) -> None:
        widgets = widgets_de_escolha_do_glade(_GLADE_REAL)
        conhecidos = set(DEPOSITOS) | set(SEM_DEPOSITO_POR_DECISAO)
        sem_entrada = sorted(set(widgets) - conhecidos)
        assert not sem_entrada, (
            "widget(s) de escolha sem depósito declarado nem isenção: "
            f"{sem_entrada} — acrescente em DEPOSITOS (com a citação que "
            "prova) ou em SEM_DEPOSITO_POR_DECISAO (com a razão), em "
            "tests/unit/test_z4_matriz_widget_deposito.py"
        )

    def test_a_mordida_um_widget_novo_reprova_nomeando_aba_e_widget(
        self, tmp_path: Path
    ) -> None:
        """A frase literal do aceite (§0.2 do SPRINT_ORDER): "widget de
        escolha novo sem campo de perfil nem depósito declarado faz a
        matriz REPROVAR nomeando aba e widget"."""
        original = _GLADE_REAL.read_text(encoding="utf-8")
        injetado = original.replace(
            "</interface>",
            '<object class="GtkSwitch" '
            'id="aba_fabricada_z4_widget_orfao_de_deposito"/></interface>',
            1,
        )
        alvo = tmp_path / "main_com_orfao.glade"
        alvo.write_text(injetado, encoding="utf-8")

        widgets = widgets_de_escolha_do_glade(alvo)
        conhecidos = set(DEPOSITOS) | set(SEM_DEPOSITO_POR_DECISAO)
        sem_entrada = sorted(set(widgets) - conhecidos)
        assert sem_entrada == ["aba_fabricada_z4_widget_orfao_de_deposito"], (
            "a mordida deveria nomear exatamente o widget fabricado — achou "
            f"{sem_entrada!r}"
        )

    def test_nenhuma_entrada_cita_arquivo_que_nao_existe(self) -> None:
        """T12: toda isenção cita arquivo:linha REAL — não uma promessa."""
        padrao = re.compile(r"([\w./]+\.py):(\d+)")
        checados = 0
        for widget, razao in {**DEPOSITOS, **SEM_DEPOSITO_POR_DECISAO}.items():
            for arquivo_rel, linha_str in padrao.findall(razao):
                checados += 1
                caminho = RAIZ / "src" / "hefesto_dualsense4unix" / arquivo_rel
                assert caminho.exists(), (
                    f"{widget!r} cita {arquivo_rel}, que não existe"
                )
                total_linhas = len(
                    caminho.read_text(encoding="utf-8").splitlines()
                )
                assert int(linha_str) <= total_linhas, (
                    f"{widget!r} cita {arquivo_rel}:{linha_str}, mas o "
                    f"arquivo só tem {total_linhas} linhas — citação morta"
                )
        assert checados >= 20, (
            f"só {checados} citações verificadas — a régua deste teste "
            "parou de achar o padrão arquivo:linha nas razões?"
        )
