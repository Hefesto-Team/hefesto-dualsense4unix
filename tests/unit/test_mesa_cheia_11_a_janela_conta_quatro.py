from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. A primeira versão deste
# arquivo plantava um stub cru em `sys.modules` (copiado de um vizinho) e o
# portão `test_guarda_gi_falso_precisa_de_exigir_gi_real` o reprovou com razão:
# contra `Gtk.Box = object` este arquivo ficaria verde sem nunca entrar no job
# gtk-real. Aqui o `gi` só é preciso porque `home_actions` importa o
# `ipc_bridge` — nada nesta suíte abre janela.
exigir_gi_real("mesa cheia 11: a janela conta um quando são quatro")

import gettext
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, ClassVar

import pytest

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "state_full_quatro_controles.json"
)
GLADE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "main.glade"
)

from hefesto_dualsense4unix.app.actions.home_actions import (
    VPAD_COOP_DEGRADED_TEXT,
    jogadores_degradados,
    texto_coop_degradado,
    vpad_degradation_text,
)
from hefesto_dualsense4unix.integrations import storm_doctor as sd


def mesa_cheia() -> dict[str, Any]:
    """O payload REAL de quatro controles (dois USB, dois BT), cópia fresca."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# E2 (1.8) — o banner do co-op NOMEIA o jogador
# ---------------------------------------------------------------------------


class TestBannerDoCoopNomeiaOJogador:
    def _mesa_com_jogadores_caidos(self, motivo: str) -> dict[str, Any]:
        state = mesa_cheia()
        gp = state["gamepad_emulation"]
        gp["dedup_ok"] = False
        gp["dedup_motivo"] = motivo
        return state

    def test_le_os_numeros_do_dedup_motivo(self) -> None:
        # O campo chega como lista separada por vírgula e MISTURA motivos.
        assert jogadores_degradados("jogador_3_uinput") == [3]
        assert jogadores_degradados(
            "jogador_2_uinput, jogador_4_uinput, jogo_sem_wrapper"
        ) == [2, 4]
        assert jogadores_degradados("jogador_2_uinput, jogador_2_uinput") == [2]
        assert jogadores_degradados("sem_uhid") == []
        assert jogadores_degradados("jogador_?_uinput") == []
        assert jogadores_degradados(None) == []

    def test_o_banner_diz_o_numero_do_jogador(self) -> None:
        state = self._mesa_com_jogadores_caidos("jogador_3_uinput")
        texto = vpad_degradation_text(state)
        assert texto is not None
        assert "Jogador 3" in texto
        # A mordida: a frase antiga não pode sobreviver disfarçada.
        assert "um dos jogadores" not in texto
        assert texto != VPAD_COOP_DEGRADED_TEXT

    def test_dois_jogadores_saem_no_plural_e_com_os_dois_numeros(self) -> None:
        state = self._mesa_com_jogadores_caidos("jogador_2_uinput, jogador_4_uinput")
        texto = vpad_degradation_text(state)
        assert texto is not None
        assert "Jogadores 2 e 4" in texto
        assert "gamepads virtuais" in texto

    def test_tres_jogadores_usam_o_mesmo_lexico_de_lista_da_casa(self) -> None:
        assert "Jogadores 2, 3 e 4" in texto_coop_degradado([2, 3, 4])

    def test_sem_numero_mantem_o_texto_generico(self) -> None:
        """O `?` é real: `dedup_status` o emite quando falta `player_index`."""
        state = self._mesa_com_jogadores_caidos("jogador_?_uinput")
        assert vpad_degradation_text(state) == VPAD_COOP_DEGRADED_TEXT

    def test_a_saida_continua_sendo_dita(self) -> None:
        """Nomear não pode custar o conselho — o banner ainda diz o que fazer."""
        for texto in (texto_coop_degradado([1]), texto_coop_degradado([1, 2])):
            assert "aba Sistema" in texto
            assert "vibração" in texto


# ---------------------------------------------------------------------------
# E3 (1.9) — o áudio se CONTA
# ---------------------------------------------------------------------------

#: O `/proc/asound/cards` real da mesa cheia (14/08/2026, quatro controles: dois
#: no cabo e dois no rádio). Cada placa ocupa DUAS linhas e a palavra
#: "DualSense" aparece nas duas — contar ocorrências daria 4 onde há 2 placas.
CARDS_MESA_CHEIA = """\
 0 [NVidia         ]: HDA-Intel - HDA NVidia
                      HDA NVidia at 0xfc080000 irq 83
 1 [Controller     ]: USB-Audio - DualSense Wireless Controller
                      Sony Interactive Ent. DualSense Wireless Controller at usb-1
 2 [Generic        ]: HDA-Intel - HD-Audio Generic
                      HD-Audio Generic at 0xfc400000 irq 85
 3 [Controller_1   ]: USB-Audio - DualSense Wireless Controller
                      Sony Interactive Ent. DualSense Wireless Controller at usb-1
"""

CARDS_UM_SO = """\
 0 [NVidia         ]: HDA-Intel - HDA NVidia
                      HDA NVidia at 0xfc080000 irq 83
 1 [Controller     ]: USB-Audio - DualSense Wireless Controller
                      Sony Interactive Ent. DualSense Wireless Controller at usb-1
"""


class TestAudioSeConta:
    def test_conta_placas_e_nao_ocorrencias_da_palavra(self) -> None:
        """A régua antes do veredito: duas placas, quatro citações do nome."""
        assert CARDS_MESA_CHEIA.count("DualSense") == 4
        assert sd.contar_placas_dualsense(CARDS_MESA_CHEIA) == 2
        assert sd.contar_placas_dualsense(CARDS_UM_SO) == 1
        assert sd.contar_placas_dualsense("") == 0

    def test_o_denominador_e_quem_esta_no_cabo(self) -> None:
        """Dois USB e dois BT: só o cabo cria placa ALSA (medido na mesa dela)."""
        assert sd.controles_no_cabo(mesa_cheia()) == 2
        assert sd.controles_no_cabo(None) is None
        assert sd.controles_no_cabo({}) is None
        # Sem controle nenhum o `describe_controllers` devolve UMA entrada
        # offline (`{"connected": False, "transport": None, ...}`, contrato do
        # backend) — ela não pode virar um controle no cabo.
        assert sd.controles_no_cabo(
            {"controllers": [{"connected": False, "transport": None}]}
        ) == 0

    def test_um_com_audio_nao_responde_pelos_quatro(self) -> None:
        """A mordida: hoje UM DualSense no texto faz o veredito ser OK.

        Quatro controles no cabo, um só com placa de áudio: o veredito tem de
        deixar de ser "tudo certo" e a frase tem de dizer 1 de 4.
        """
        tag, msg = sd.check_snd_audio_healthy(CARDS_UM_SO, controles_no_cabo=4)
        assert tag != sd.OK, "contar sem mudar o veredito é cosmética"
        assert "1 de 4" in msg

    def test_a_mesa_cheia_de_verdade_fica_ok(self) -> None:
        """Dois no cabo com as duas placas presentes = tudo certo, sem alarme."""
        tag, msg = sd.check_snd_audio_healthy(
            CARDS_MESA_CHEIA, controles_no_cabo=sd.controles_no_cabo(mesa_cheia())
        )
        assert tag == sd.OK
        assert "2" in msg

    def test_bt_sozinho_nao_vira_alarme_falso(self) -> None:
        """Nenhum no cabo, nenhuma placa: não há áudio USB a cobrar.

        Conserto de 14/08: este teste dizia só `tag != sd.WARN`, e com isso o
        ramo podia passar a MENTIR ("[ OK ] áudio presente") sem nada ficar
        vermelho — dois vereditos dos cinco não tinham dono. Agora a asserção é
        de TAG **e** de TEXTO.
        """
        state = mesa_cheia()
        for c in state["controllers"]:
            c["transport"] = "bt"
        assert sd.controles_no_cabo(state) == 0
        tag, msg = sd.check_snd_audio_healthy("", controles_no_cabo=0)
        assert tag == sd.INFO, "sem ninguém no cabo não há nem OK nem alarme a dar"
        assert msg.startswith("nenhum controle no cabo")
        assert "áudio presente" not in msg, "não há áudio USB a declarar presente"
        assert "áudio ausente" not in msg, "nem ausente: ele simplesmente não se aplica"

    def test_sem_denominador_o_texto_nao_inventa_fracao(self) -> None:
        """Sem daemon não há quantos controles são — e a frase não mente."""
        tag, msg = sd.check_snd_audio_healthy(CARDS_UM_SO)
        assert tag == sd.OK
        assert " de " not in msg

    def test_o_doctor_do_cli_nao_explode_sem_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O denominador vem do daemon — e o doctor roda com ele desligado."""
        import asyncio

        from hefesto_dualsense4unix.cli import cmd_doctor

        def _boom(*_a: object, **_k: object) -> object:
            raise FileNotFoundError("socket ausente")

        monkeypatch.setattr(cmd_doctor.IpcClient, "connect", _boom)
        assert asyncio.run(cmd_doctor._state_full_ou_none()) is None
        assert sd.controles_no_cabo(None) is None

    def test_o_relatorio_repassa_o_denominador(self) -> None:
        linhas = sd.storm_report(
            Path("/nao-existe"),
            quirks_text="",
            dropin_dir=Path("/nao-existe"),
            rules_dir=Path("/nao-existe"),
            snd_quirk_text="",
            snd_conf_path=Path("/nao-existe/ausente.conf"),
            cards_text=CARDS_UM_SO,
            controles_no_cabo=4,
        )
        assert any("1 de 4" in msg for _tag, msg in linhas)


# ---------------------------------------------------------------------------
# E3 / conserto de 14/08 — os CINCO vereditos e o português do caso comum
# ---------------------------------------------------------------------------
#
# Por que este bloco existe: a primeira entrega da E3 escreveu oito testes com
# denominador `None`, `0`, `2` e `4` — **nunca `1`**, que é o caso mais comum do
# produto (um controle no cabo). O resultado saía verbatim pela tela e pelo
# `doctor`: "áudio presente nos 1 controles no cabo". E dois dos cinco
# vereditos não tinham asserção nenhuma de tag, então trocar INFO por WARN — ou
# fazer o ramo mentir "áudio presente" — deixava a suíte verde.


class TestOsCincoVereditosDoAudio:
    """Cada ramo com TAG e TEXTO — inclusive o denominador 1, que ninguém testou."""

    def test_um_no_cabo_com_audio_fala_portugues(self) -> None:
        """A MORDIDA do defeito B: o caso padrão do produto, um controle."""
        tag, msg = sd.check_snd_audio_healthy(CARDS_UM_SO, controles_no_cabo=1)
        assert tag == sd.OK
        assert "nos 1 controles" not in msg, "português quebrado no caso mais comum"
        assert "áudio presente no único controle no cabo" in msg
        assert "mic+fone do DualSense ativos" in msg

    def test_um_no_cabo_sem_audio_tambem_fala_portugues(self) -> None:
        tag, msg = sd.check_snd_audio_healthy("", controles_no_cabo=1)
        assert tag == sd.INFO
        assert "nos 1 controles" not in msg
        assert "áudio ausente no único controle no cabo" in msg

    def test_zero_placas_com_gente_no_cabo_e_informativo_e_diz_ausente(self) -> None:
        """Veredito órfão nº 1: só havia `tag != sd.OK` cobrindo este ramo.

        É INFO de propósito, e o texto explica por quê: com o áudio-off ligado
        a placa não sobe, e logo depois do plug ela ainda está subindo. Alarme
        vermelho aqui viraria ruído permanente.
        """
        tag, msg = sd.check_snd_audio_healthy("", controles_no_cabo=4)
        assert tag == sd.INFO, "este ramo não é alarme — é informação"
        assert "áudio ausente nos 4 controles no cabo" in msg
        assert "áudio-off ligado?" in msg
        assert "a placa ainda subindo" in msg

    def test_falta_um_so_diz_o_outro_e_nao_os_demais(self) -> None:
        """Terceira frase da mesma família: "os demais" com um só sobrando."""
        tag, msg = sd.check_snd_audio_healthy(CARDS_UM_SO, controles_no_cabo=2)
        assert tag == sd.WARN
        assert "áudio presente em 1 de 2 controles no cabo" in msg
        assert "o outro está sem mic nem fone" in msg
        assert "os demais" not in msg

    def test_faltando_mais_de_um_volta_ao_plural(self) -> None:
        tag, msg = sd.check_snd_audio_healthy(CARDS_UM_SO, controles_no_cabo=4)
        assert tag == sd.WARN
        assert "áudio presente em 1 de 4 controles no cabo" in msg
        assert "os demais estão sem mic nem fone" in msg

    def test_placa_sobrando_sem_ninguem_no_cabo_conta_no_singular(self) -> None:
        """Veredito órfão nº 2: o "(s)" de formulário, e nada afirmava a tag.

        Uma placa DualSense de pé com ninguém no cabo é o resto do controle que
        acabou de sair — não é defeito, e a frase tem de contar quantas placas.
        """
        tag, msg = sd.check_snd_audio_healthy(CARDS_UM_SO, controles_no_cabo=0)
        assert tag == sd.OK
        assert "placa(s)" not in msg, "'(s)' é formulário, não português"
        assert "áudio presente em 1 placa DualSense (nenhum no cabo)" in msg

    def test_duas_placas_sem_ninguem_no_cabo_falam_no_plural(self) -> None:
        tag, msg = sd.check_snd_audio_healthy(CARDS_MESA_CHEIA, controles_no_cabo=0)
        assert tag == sd.OK
        assert "áudio presente em 2 placas DualSense (nenhum no cabo)" in msg

    def test_nenhuma_frase_do_check_sai_com_numero_grudado_no_plural(self) -> None:
        """Varredura: nenhum denominador pode voltar a produzir " 1 <plural>s".

        Rede contra a regressão inteira da família, não só contra as três
        frases medidas — se alguém acrescentar um ramo novo interpolando o
        plural fixo, o `1` o denuncia aqui.
        """
        errado = re.compile(r"\b1 \w+s\b")
        for placas_texto in ("", CARDS_UM_SO, CARDS_MESA_CHEIA):
            for denominador in (None, 0, 1, 2, 4):
                _tag, msg = sd.check_snd_audio_healthy(
                    placas_texto, controles_no_cabo=denominador
                )
                assert not errado.search(msg), f"plural com 1: {msg!r}"


# ---------------------------------------------------------------------------
# E3 / conserto de 14/08 — os DOIS chamadores, agora COM dente
# ---------------------------------------------------------------------------
#
# A manchete da entrega era "os dois chamadores foram ligados", e nada em
# `tests/` chamava `_print_storm_block` nem `_refresh_storm_diag` com
# denominador: arrancando `controles_no_cabo=no_cabo` dos dois, a suíte INTEIRA
# ficava verde. Havia até um teste com APARÊNCIA de cobrir o fio do CLI
# (`test_o_doctor_do_cli_nao_explode_sem_daemon`), mas ele só exercita o helper
# `_state_full_ou_none` — nunca afirma que o denominador atravessa.
#
# É o defeito mais caro desta casa: a cura escrita e nunca ligada. Os dois
# testes abaixo percorrem o fio inteiro — `state_full` dublado -> denominador
# -> `storm_report` -> a saída que ela lê — e exigem a fração no fim.


def _dublar_cards(monkeypatch: pytest.MonkeyPatch, texto: str) -> None:
    """Faz o `/proc/asound/cards` do check ser `texto`, e só ele.

    Sem isto o teste leria as placas REAIS da máquina de quem roda a suíte —
    quatro controles na mesa dela — e o resultado mudaria conforme o que está
    plugado. Hermeticidade: os demais arquivos continuam sendo lidos de fato.
    """
    original = sd._safe_read

    def _lendo(path: Path) -> str:
        if str(path) == "/proc/asound/cards":
            return texto
        return original(path)

    monkeypatch.setattr(sd, "_safe_read", _lendo)
    # A varredura das localconfig.vdf da Steam não tem nada a ver com áudio e
    # custa I/O na home de verdade.
    monkeypatch.setattr(sd, "find_localconfig_vdfs", lambda *_a, **_k: [])


def _mesa_toda_no_cabo() -> dict[str, Any]:
    """Os quatro controles reais, todos no cabo — denominador 4, placas 1."""
    state = mesa_cheia()
    for c in state["controllers"]:
        c["transport"] = "usb"
    return state


class _ConsoleFalso:
    """Coleta o que o `doctor` imprimiria, sem quebra de linha do rich."""

    def __init__(self) -> None:
        self.linhas: list[str] = []

    def print(self, *args: object, **_kwargs: object) -> None:
        self.linhas.append(" ".join(str(a) for a in args))

    def texto(self) -> str:
        return "\n".join(self.linhas)


class _ExecutorSincrono:
    """Roda o worker na mesma thread — asserts síncronos depois da chamada."""

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)


class _RotuloFalso:
    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, markup: str) -> None:
        self.markup = markup


class TestOsDoisChamadoresLevamODenominador:
    def test_o_doctor_do_cli_leva_o_denominador_ate_a_saida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`cli/cmd_doctor._print_storm_block` — o fio inteiro, com dente.

        Arrancar `controles_no_cabo=no_cabo` da chamada a `storm_report` faz a
        saída voltar a "áudio do controle presente" e este teste reprovar.
        """
        import contextlib as _contextlib

        from hefesto_dualsense4unix.cli import cmd_doctor

        estado = _mesa_toda_no_cabo()
        perguntas: list[str] = []

        class _ClienteFalso:
            async def call(self, metodo: str, *_a: object, **_k: object) -> object:
                perguntas.append(metodo)
                return estado

        @_contextlib.asynccontextmanager
        async def _connect(*_a: object, **_k: object) -> Any:
            yield _ClienteFalso()

        monkeypatch.setattr(cmd_doctor.IpcClient, "connect", _connect)
        _dublar_cards(monkeypatch, CARDS_UM_SO)
        console = _ConsoleFalso()
        monkeypatch.setattr(cmd_doctor, "console", console)

        cmd_doctor._print_storm_block()

        saida = console.texto()
        assert perguntas == ["daemon.state_full"], (
            "o doctor nem perguntou ao daemon quantos estão no cabo"
        )
        assert "áudio presente em 1 de 4 controles no cabo" in saida, (
            "o denominador não atravessou do state_full até a saída do doctor:\n"
            + saida
        )
        assert "áudio do controle presente" not in saida, (
            "a frase sem denominador voltou — um controle respondendo pelos quatro"
        )

    def test_o_cartao_da_janela_leva_o_denominador_ate_a_tela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`app/actions/daemon_actions._refresh_storm_diag` — o mesmo fio, na GUI.

        Arrancar `controles_no_cabo=no_cabo` daqui faz o cartão anti-storm
        voltar a dizer "áudio do controle presente" com um só no cabo de quatro
        — e este teste reprovar.
        """
        from hefesto_dualsense4unix.app import ipc_bridge
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        estado = _mesa_toda_no_cabo()
        perguntas: list[str] = []

        def _state_full() -> dict[str, Any]:
            perguntas.append("daemon.state_full")
            return estado

        monkeypatch.setattr(ipc_bridge, "daemon_state_full", _state_full)
        monkeypatch.setattr(da, "_get_executor", lambda: _ExecutorSincrono())
        monkeypatch.setattr(
            da.GLib, "idle_add", lambda fn, *a, **k: (fn(*a, **k), 0)[1]
        )
        _dublar_cards(monkeypatch, CARDS_UM_SO)

        rotulo = _RotuloFalso()

        class _HostDoCartao(da.DaemonActionsMixin):
            def _get(self, widget_id: str) -> Any:
                return rotulo if widget_id == "storm_diag_label" else None

        _HostDoCartao()._refresh_storm_diag()

        assert perguntas == ["daemon.state_full"], (
            "a janela nem perguntou quantos estão no cabo"
        )
        assert "áudio presente em 1 de 4 controles no cabo" in rotulo.markup, (
            "o denominador não atravessou até o cartão anti-storm:\n" + rotulo.markup
        )
        assert "áudio do controle presente" not in rotulo.markup


# ---------------------------------------------------------------------------
# E4 (1.11) — o singular que virou mentira com quatro na mesa
# ---------------------------------------------------------------------------
#
# O CENSO, refeito em 14/08/2026 sobre o `main.glade` de hoje. A sprint de
# 13/08 listou OITO frases; o censo completo achou **61 textos traduzíveis**
# dizendo "o/do/ao/no controle" no singular — as oito eram a amostra, não o
# total, e o número certo entra no lugar do errado (regra da casa: fato errado
# se SUBSTITUI).
#
# A CONTAGEM ABAIXO TAMBÉM FOI SUBSTITUÍDA (conserto de 14/08, à tarde). A
# primeira versão dizia "38 corrigidos — 18 plural, 20 sujeito", e nenhum dos
# três números resistiu a ser medido de novo: a soma nem fechava com o total.
# Os de hoje saem de uma comparação entre o `main.glade` de `CENSO_BASE` e o da
# árvore, e `test_o_censo_do_comentario_bate_com_a_arvore` os recomputa a cada
# rodada, para que este
# comentário não volte a envelhecer calado. Dos 61:
#
#   41 mexidos aqui — em 16 o singular SUMIU (viraram plural ou foram
#      reescritos), 22 ganharam sujeito ou alvo, e 3 foram corrigidos EM PARTE
#      (o singular que restou em cada um tem motivo escrito na lista abaixo);
#   20 intocados — 5 já diziam "controle selecionado" antes (a Lightbar, que
#      deu o léxico) e 15 continuam singulares com o motivo escrito na lista.
#
# Fora do `.glade`, mais duas frases do `integrations/storm_doctor.py`
# ("reconecte o controle" → os quatro é que reconectam).
#
# E uma quarta cura que a régua NÃO enxergava, porque o erro dela estava no
# PLURAL: o `profile_steam_input_hint` — o rótulo itálico sempre visível abaixo
# da caixinha do Steam Input — dizia "Marque quando o jogo mostrar dois
# controles", que é o mundo de um controle só (com quatro na mesa o jogo mostra
# OITO). Passou a dizer "os seus controles dobrados", que é o léxico da
# caixinha logo acima. O portão que a pegaria está em
# `test_nenhuma_frase_promete_o_mundo_de_dois_controles`.
#
# As três curas, e elas NÃO são intercambiáveis:
#   PLURAL   — o gesto atinge os quatro (Ativar perfil, Desligar o Hefesto,
#              esconder o físico, Aplicar do rodapé);
#   SUJEITO  — o efeito é de UM só e a frase não dizia qual. Existe um
#              `EvdevReader`, atrelado ao primário ("single-controller por
#              construção", `core/backend_pydualsense.py:read_state`): mouse,
#              teclado e o combo PS+Options são "quem comanda o PC" (D-10).
#              Pluralizar aqui PIORA a mentira;
#   ALVO     — o gesto vai para quem está no seletor (`_edit_target_uniq`,
#              compartilhado por Lightbar, Gatilhos, LEDs e Rumble): a palavra
#              é "controle selecionado", que a Lightbar já usava.

#: O padrão do censo: "o/do/ao/no controle" no singular.
SINGULAR_RE = re.compile(r"\b(?:o|do|ao|no)\s+controle\b(?!s)", re.IGNORECASE)

#: As curas que dão sujeito ou alvo — quem as traz não é mentira no singular.
#:
#: E cada marca vem AMARRADA ao substantivo, não solta. O mecanismo que furou
#: as duas versões anteriores do portão não era o tamanho da unidade — era
#: `marca in unidade` com a marca solta, que isenta a oração inteira mesmo
#: quando a palavra qualifica OUTRO substantivo. Com a marca solta,
#: *"Aplica o perfil selecionado no controle."* — uma oração só, sem vírgula
#: nem travessão, portanto fora do alcance do corte fino — atravessa calada: o
#: "selecionado" fala do PERFIL. Medido em 14/08/2026: amarrar as quatro marcas
#: custa ZERO na árvore de hoje (as 24 orações que as trazem dizem todas
#: "controle selecionado" ou "controle que comanda o PC") e fecha a escotilha
#: que sobrava. `test_a_marca_de_alvo_tem_de_falar_do_controle` cobra isso.
SUJEITO_OU_ALVO = (
    "controle selecionado",
    "controle que comanda o PC",
    "deste controle",
    "neste controle",
)

#: O corte em ORAÇÕES, e ele é a diferença entre portão e escotilha.
#:
#: DUAS versões deste portão já foram furadas pelo MESMO mecanismo, e a segunda
#: só encolheu a unidade em vez de trocá-la:
#:
#:   1ª — `marca in texto` sobre o texto INTEIRO. Bastava a palavra
#:        "selecionado" aparecer em QUALQUER ponto para isentar tudo o que
#:        viesse depois. A prova é a frase número 1 da própria sprint:
#:        *"Passa a usar o perfil selecionado agora: … vão para o controle."*
#:        O "selecionado" fala do PERFIL, o "controle" ofensor está na outra
#:        oração, e o portão dizia que estava tudo bem.
#:   2ª — o mesmo `marca in unidade`, com a unidade cortada só em `[.!?;:]`.
#:        Sentença única com VÍRGULA, TRAVESSÃO ou PARÊNTESES continuava sendo
#:        uma unidade só, e a escotilha continuava aberta. Medido no `.glade`
#:        de 14/08/2026: dos **470** trechos que aquela régua chamava de
#:        "sentença", **88 tinham vírgula dentro, 34 travessão e 42 um
#:        parêntese de abertura** (45, contando também os que só trazem o de
#:        fechamento). Somar os três dá 164 e conta o mesmo trecho duas vezes;
#:        a UNIÃO, que é o número honesto, é **135** — e a régua de hoje parte
#:        **133** deles em mais de uma oração. Cada um é um lugar onde a frase
#:        número 1 voltava a passar calada, bastando trocar os dois-pontos por
#:        uma vírgula. `test_a_regua_anterior_calava_na_pontuacao_fraca` reconta
#:        tudo isso na árvore e cobra as RELAÇÕES (a união é menor que a soma; a
#:        superfície é de centenas; a régua parte quase todas) — números fixos
#:        ficariam vermelhos a cada palavra mexida no `.glade`, e alarme falso
#:        ninguém investiga duas vezes.
#:
#: Agora a pergunta é feita à ORAÇÃO que ofende: o corte inclui a pontuação
#: fraca que separa orações coordenadas em português — vírgula, travessão (o
#: EM DASH e o EN DASH), hífen entre espaços e parênteses. Quem declara o alvo
#: numa oração NÃO compra silêncio para as vizinhas, estejam elas atrás de um
#: ponto ou de uma vírgula.
#: `test_declarar_o_alvo_numa_oracao_nao_isenta_as_outras` planta as quatro
#: pontuações e cobra as quatro.
#:
#: O preço do corte fino, declarado: uma marca de `SINGULAR_LEGITIMO` não pode
#: atravessar o corte, ou nunca casa. Foi o caso de "o controle navega na
#: Steam, mas fica morto", encurtada para caber numa oração —
#: `test_nenhuma_excecao_atravessa_o_corte_das_oracoes` impede que a próxima
#: entre torta.
ORACAO_RE = re.compile(r"(?<=[.!?;:,])\s+|\n+|\s+[—\u2013]\s+|\s+-\s+|[()]")


#: O `.glade` de ANTES da E4, para o censo se recontar sozinho. É o commit que
#: tocou o arquivo por último antes desta leva; se a árvore for rebaseada e o
#: blob sumir, `test_o_censo_do_comentario_bate_com_a_arvore` PULA em vez de
#: reprovar — a contagem é histórica, e história perdida não é defeito de hoje.
CENSO_BASE = "874fddaf003bc7b81971b74e915242b06ff4f865"


def _textos_de_xml(raiz: ET.Element) -> list[tuple[str, str]]:
    """(dono, texto) de todo `translatable="yes"` de uma árvore Glade.

    O dono é o `id` do objeto MAIS PRÓXIMO — `iter()` sobre o objeto raiz
    devolveria "main_window" para a janela inteira, e foi assim que a primeira
    versão deste instrumento mentiu sobre quem dizia o quê.
    """
    saida: list[tuple[str, str]] = []

    def anda(el: ET.Element, dono: str) -> None:
        if el.tag == "object":
            dono = el.get("id") or el.get("class") or dono
        for filho in el:
            if filho.tag == "property" and filho.get("translatable") == "yes":
                texto = (filho.text or "").strip()
                if texto:
                    saida.append((f"{dono}.{filho.get('name')}", texto))
            anda(filho, dono)

    anda(raiz, "?")
    return saida


def textos_traduziveis() -> list[tuple[str, str]]:
    """(dono, texto) de todo `translatable="yes"` do main.glade de hoje."""
    return _textos_de_xml(ET.parse(GLADE).getroot())


#: A lista de exceções da MORDIDA 4, e cada linha traz a CATEGORIA e o MOTIVO.
#:
#: O CONTRATO, reescrito no conserto de 14/08 porque o anterior se contradizia:
#: a docstring dizia "só entra quando o singular é VERDADE", e a linha do
#: "Como o jogo vê o controle" dizia "pluralizar é dela" — que é adiamento, não
#: verdade. Um contrato que a própria lista viola não segura ninguém. Em vez de
#: apagar a linha (o que forçaria a pluralização e responderia POR ELA pela
#: porta dos fundos — o erro que o `test_a_intensidade_global_fica_de_fora_ate_
#: a_d_4` já existe para impedir), o contrato passou a admitir DUAS categorias,
#: e o prefixo de cada valor diz qual:
#:
#:   VERDADE: — o singular é verdade naquela linha, e o motivo diz por quê.
#:   ADIADO:  — o singular MENTE, e a correção NÃO é minha para fazer. Só vale
#:              para léxico dela; o motivo tem de nomear o dono (a palavra
#:              "dela") e o preço. Categoria cara de propósito: hoje tem UMA
#:              linha, e `test_toda_excecao_declara_categoria` cobra o formato.
#:
#: Ressalva de método, declarada: varredura de texto erra nas duas direções.
#: Este teste é AVISO COM LISTA, não portão cego — ele cobra que toda frase
#: nova no singular seja justificada por escrito, e é isso que impede as
#: frases de voltarem em três meses.
SINGULAR_LEGITIMO: dict[str, str] = {
    "Ouvir no controle":
        "VERDADE: nome do botão; o alvo é o CARTÃO, e há um cartão por controle",
    "alto-falante do controle": "VERDADE: idem — o gesto é do cartão daquele controle",
    "A cor só vai ao controle quando você clicar":
        "VERDADE: cita o NOME do botão; o alvo real está no tooltip, que diz selecionado",
    "Aplicar no controle":
        "VERDADE: nome do botão da Lightbar; o tooltip já diz 'controle selecionado'",
    "o número do controle continua sendo o do cabeçalho":
        "VERDADE: o número é DAQUELE controle, um por cabeçalho",
    "no limite do controle":
        "VERDADE: o limite é do MOTOR — característica do aparelho, não alvo de gesto",
    "a bateria do controle":
        "VERDADE: a política lê a bateria de cada um; a frase descreve a REGRA",
    "sem tirar o controle dele":
        "VERDADE: aqui 'o controle' é COMANDO (tirar o controle do jogo), não aparelho",
    "antes de chegar ao controle":
        "VERDADE: descreve o caminho do valor até o alvo escolhido logo acima",
    "ajusta o áudio do controle":
        "VERDADE: config de sistema para o MODELO DualSense, não para uma peça",
    "o comportamento do controle do nada": "VERDADE: fala do modelo, não de uma peça",
    "Testar o controle virtual": "VERDADE: cria UM vpad de teste, de propósito",
    "layout PS sem o controle dobrado":
        "VERDADE: descreve o sintoma como ele aparece em cada controle",
    "o controle navega na Steam":
        "VERDADE: sintoma de jogo Xbox-only, igual em qualquer controle. A marca "
        "termina antes da vírgula de propósito: com o corte por ORAÇÃO, uma marca "
        "que atravessa o corte não casa com nada",
    "Como o jogo vê o controle":
        "ADIADO: é léxico DELA — 'O jogo vê o controle como:' está em quatro "
        "módulos (home_actions, profiles_actions, painel_no_jogo, relancar), "
        "nos testes e em docs/usage/{interface,modos}.md. A máscara é da SESSÃO "
        "(D-6) e vira do JOGADOR na D-5, que ainda não foi medida com a mesa "
        "cheia; pluralizar antes é responder por ela",
    "escolha um botão do controle": "VERDADE: o atalho é do PERFIL, não de uma peça",
}

#: Os prefixos que a lista admite. Fora deles, o motivo não conta como motivo.
CATEGORIAS = ("VERDADE:", "ADIADO:")


def _justificado(texto: str) -> str | None:
    for marca, motivo in SINGULAR_LEGITIMO.items():
        if marca in texto:
            return motivo
    return None


def _diz_o_sujeito(texto: str) -> bool:
    """A régua Nº 2, preservada como está PORQUE ela ainda é usada como réu.

    Esta é a pergunta `marca in unidade` — a que furou as duas versões
    anteriores. Ela continua aqui, e continua exatamente assim, porque
    `test_declarar_o_alvo_numa_oracao_nao_isenta_as_outras` a chama para
    mostrar o silêncio dela nas frases plantadas. Quem decide hoje é
    `oracoes_ofensoras`, que não pergunta isto.
    """
    return any(marca in texto for marca in SUJEITO_OU_ALVO)


def _sem_as_marcas(texto: str) -> str:
    """O texto com as marcas de `SUJEITO_OU_ALVO` apagadas.

    É o que fecha o TERCEIRO andar do mesmo mecanismo. Amarrar a marca ao
    substantivo (2º conserto) e cortar em orações (idem) ainda deixavam de pé
    a pergunta "a marca APARECE aqui?", que isenta a oração INTEIRA — inclusive
    um segundo "o controle" sem dono na MESMA oração, onde não há vírgula nem
    travessão para cortar:

        *"Envia ao controle selecionado a cor, o brilho e a vibração do
        controle."*

    A marca legítima está lá, a oração é uma só, e o "do controle" final segue
    prometendo a UM o que o gesto faz nos QUATRO. Apagando a marca antes de
    perguntar, o que sobra é exatamente o singular sem dono.
    Medido em 14/08/2026: apagar as marcas antes da pergunta custa **ZERO**
    frase nova no `.glade` de hoje — nenhuma oração viva traz marca amarrada
    E outro "o controle" solto. `test_a_marca_nao_compra_silencio_para_a_
    oracao_inteira` planta a frase acima e cobra as duas leituras.
    """
    for marca in SUJEITO_OU_ALVO:
        texto = texto.replace(marca, "")
    return texto


def oracoes(texto: str) -> list[str]:
    """O texto partido nas ORAÇÕES que o compõem, sem as vazias."""
    cruas = (s.strip().strip("—\u2013-").strip() for s in ORACAO_RE.split(texto))
    return [s for s in cruas if s]


def oracoes_ofensoras(texto: str) -> list[str]:
    """As orações que dizem "o controle" sem dizer QUAL, e sem motivo escrito.

    A pergunta é feita por ORAÇÃO de propósito: perguntá-la ao texto inteiro —
    ou à sentença, que é o texto inteiro sempre que a pontuação é fraca — é a
    escotilha que dois céticos abriram. Ver `ORACAO_RE`.

    E ela NÃO é `marca in oração`: a marca é APAGADA antes da pergunta, e o
    que sobrar de singular sem dono acusa a oração ainda que a marca esteja
    presente nela. Ver `_sem_as_marcas` — é o terceiro andar do mecanismo, e
    o único que sobrava.
    """
    return [
        s
        for s in oracoes(texto)
        if SINGULAR_RE.search(_sem_as_marcas(s)) and _justificado(s) is None
    ]


class TestAsFrasesNoSingular:
    """As frases medidas hoje (14/08/2026) e o que cada uma passou a dizer."""

    def _todos(self) -> str:
        return "\n".join(t for _n, t in textos_traduziveis())

    def _texto_do_widget(self, alvo: str) -> str:
        for nome, texto in textos_traduziveis():
            if nome == alvo:
                return texto
        raise AssertionError(f"widget {alvo} sumiu do main.glade")

    @pytest.mark.parametrize(
        ("agulha", "porque"),
        [
            ("a vibração dele vão para os controles",
             "Ativar perfil: o profile.switch atinge os quatro"),
            ("Desliga o Hefesto: os controles continuam jogando",
             "Desligar: são quatro que continuam jogando"),
            ("Esconder os controles físicos neste jogo",
             "a máscara esconde TODO Sony físico, não um"),
            ("Envia toda a configuração (gatilhos, LEDs, rumble, mouse) aos controles",
             "o Aplicar do rodapé manda o rascunho inteiro, que é de todos"),
            ("Esconde os controles físicos no último jogo aberto",
             "o mesmo gesto pelo atalho da aba Sistema"),
        ],
    )
    def test_o_que_atinge_os_quatro_fala_no_plural(
        self, agulha: str, porque: str
    ) -> None:
        assert agulha in self._todos(), porque

    def test_o_que_e_de_um_so_ganha_sujeito_e_nao_plural(self) -> None:
        """A mordida 3: pluralizar a frase dos combos PIORA a mentira.

        Existe UM `EvdevReader`, atrelado ao primário
        (`core/backend_pydualsense.py:read_state`) — P2, P3 e P4 apertam PS +
        Options e nada acontece, sem erro e sem aviso. Prometer aos quatro
        seria mentira nova; a frase tem de dizer QUEM comanda (D-10).

        E ela diz na DICA, não no rótulo: o rótulo tem teto MEDIDO de 78
        caracteres visíveis (`test_fiacao_da_janela_teclado_e_detector`, porque
        ele não quebra linha e define o mínimo de largura da aba Emulação) e
        hoje usa 77. Declarar o sujeito ali engordaria a aba — a sprint
        prometeu zero pixel novo, e a dica cumpre a promessa.
        """
        textos = textos_traduziveis()
        rotulo = next(t for n, t in textos if "PS + Options" in t and "label" in n)
        assert "os controles" not in rotulo, "plural mecânico: promete a quatro o de um"
        assert len(rotulo.replace("<b>", "").replace("</b>", "")) <= 78

        dica = next(t for n, t in textos if "PS + Options" in t and "tooltip" in n)
        assert "controle que comanda o PC" in dica
        assert "Nos outros controles, PS + Options não faz nada" in dica

    def test_o_mouse_e_o_teclado_dizem_de_quem_sao(self) -> None:
        mouse = self._texto_do_widget("mouse_emulation_toggle.tooltip-text")
        teclado = self._texto_do_widget("keyboard_emulation_toggle.tooltip-text")
        assert "o controle que comanda o PC" in mouse
        assert "Liga o controle como mouse do computador" not in mouse
        assert "o controle que comanda o PC" in teclado

    def test_o_gesto_do_alvo_diz_selecionado_como_a_lightbar_ja_dizia(self) -> None:
        """Léxico existente: a Lightbar já dizia "do controle selecionado"."""
        for agulha in (
            "Faz o controle selecionado vibrar por meio segundo",
            "Envia ao controle selecionado a vibração escolhida",
            "Envia ao controle selecionado o modo e os ajustes escolhidos aqui, "
            "no gatilho L2",
            "Reenvia ao controle selecionado o desenho escolhido",
        ):
            assert agulha in self._todos(), agulha

    def test_toda_frase_no_singular_tem_motivo_escrito(self) -> None:
        """MORDIDA 4 — a frase nova no singular não passa calada.

        Uma frase acrescentada ao `.glade` dizendo "o controle" num gesto que
        atinge os quatro reprova aqui até alguém escrever POR QUE o singular é
        verdade naquela linha — e reprova AINDA QUE a frase esteja colada, por
        vírgula ou travessão, a uma oração que declara o alvo. Era essa a
        ressalva que faltava: a versão anterior desta docstring prometia o
        portão e entregava silêncio para toda frase sem ponto final.

        A pergunta é feita à ORAÇÃO que ofende, não ao texto nem à sentença: as
        duas versões anteriores isentavam um tooltip inteiro porque UMA oração
        dele dizia "selecionado" — ver `ORACAO_RE`.
        """
        sem_motivo = [
            (nome, s)
            for nome, texto in textos_traduziveis()
            for s in oracoes_ofensoras(texto)
        ]
        assert not sem_motivo, (
            "orações no singular sem justificativa em SINGULAR_LEGITIMO:\n"
            + "\n".join(f"  {n}: {t[:120]}" for n, t in sem_motivo)
        )

    #: A frase número 1 da sprint, nas quatro pontuações que unem duas orações.
    #:
    #: A oração que ISENTA usa o léxico REAL da casa — "ao controle
    #: selecionado", que a Lightbar e os Gatilhos já escrevem — e não a palavra
    #: solta: com a marca amarrada, é essa a única forma que ainda compra
    #: silêncio, e portanto é ela que o corte por oração tem de derrotar.
    #: A primeira variante usa dois-pontos (pontuação FORTE, que a régua
    #: anterior já cortava); as três seguintes usam a pontuação FRACA que ela
    #: não cortava — e é por ela que o defeito voltou depois do 1º conserto.
    MENTIRA = "os gatilhos e a vibração vão para o controle"
    PLANTADAS = (
        ("dois-pontos", f"Envia a cor ao controle selecionado: {MENTIRA}."),
        ("vírgula", f"Envia a cor ao controle selecionado, e {MENTIRA}."),
        ("travessão", f"Envia a cor ao controle selecionado — {MENTIRA}."),
        ("parênteses", f"Envia a cor ao controle selecionado ({MENTIRA})."),
    )

    @pytest.mark.parametrize(("pontuacao", "plantada"), PLANTADAS)
    def test_declarar_o_alvo_numa_oracao_nao_isenta_as_outras(
        self, pontuacao: str, plantada: str
    ) -> None:
        """A MORDIDA DO PORTÃO — as escotilhas de DOIS céticos, viradas teste.

        É a forma da frase número 1 da própria sprint, escrita nas quatro
        pontuações que unem duas orações. A primeira oração declara o alvo com
        o léxico real da casa; a segunda promete a UM o que o gesto faz nos
        QUATRO, e é ela que tem de ser nomeada.

        A régua nº 1 (`marca in texto` sobre o texto inteiro) calava nas
        QUATRO. A régua nº 2 (corte em `[.!?;:]`) só pegava a primeira — e o
        `.glade` escreve as outras três: 88 trechos com vírgula, 34 com
        travessão e 42 com parênteses, medidos em 14/08/2026. O nome deste
        teste afirmava o que ele não garantia; agora garante.
        """
        # A régua nº 1, reproduzida aqui para se ver o silêncio dela.
        assert _diz_o_sujeito(plantada), "era assim que a escotilha se abria"
        # A régua de hoje nomeia a oração que mente, seja qual for a pontuação.
        ofensoras = oracoes_ofensoras(plantada)
        assert len(ofensoras) == 1, (pontuacao, ofensoras)
        assert ofensoras[0].rstrip(".").endswith(self.MENTIRA), (pontuacao, ofensoras)
        # A oração acusada NÃO é a que declara o alvo.
        assert "selecionado" not in ofensoras[0], (pontuacao, ofensoras)
        # E tirar a palavra que abria a escotilha só ACRESCENTA acusação: a
        # oração que declarava o alvo passa a mentir também.
        sem_marca = oracoes_ofensoras(plantada.replace(" selecionado", ""))
        assert ofensoras[0] in sem_marca and len(sem_marca) == 2, sem_marca

    def test_a_regua_anterior_calava_na_pontuacao_fraca(self) -> None:
        """O defeito de ontem, PINADO — para ninguém "simplificar" a régua.

        Se alguém trocar `ORACAO_RE` de volta por um corte só em pontuação
        forte, as três frases de pontuação fraca voltam a passar caladas. Este
        teste reproduz a régua velha e cobra que ela erre — é o que prova que o
        corte fino de hoje é o que carrega o portão, e não decoração.
        """
        velha = re.compile(r"(?<=[.!?;:])\s+|\n+")

        def ofensoras_pela_regua_velha(texto: str) -> list[str]:
            return [
                s
                for s in (p.strip() for p in velha.split(texto))
                if s
                and SINGULAR_RE.search(s)
                and not _diz_o_sujeito(s)
                and _justificado(s) is None
            ]

        por_pontuacao = {
            pont: ofensoras_pela_regua_velha(frase) for pont, frase in self.PLANTADAS
        }
        assert por_pontuacao["dois-pontos"], "a régua velha via a pontuação forte"
        calou = [p for p in ("vírgula", "travessão", "parênteses") if not por_pontuacao[p]]
        assert calou == ["vírgula", "travessão", "parênteses"], (
            "a régua velha tinha de calar nas três — se ela já as vê, o corte "
            f"fino virou redundante e este teste precisa de outro motivo: {por_pontuacao}"
        )

        # E a SUPERFÍCIE, recontada na árvore de hoje. O que se cobra aqui são
        # as RELAÇÕES, não os números: um número fixo ficaria vermelho a cada
        # palavra mexida no `.glade` — alarme falso que ninguém investiga duas
        # vezes. Os valores de 14/08/2026 estão datados no comentário de
        # `ORACAO_RE`, e a mensagem abaixo os reimprime quando algo muda.
        sentencas = [
            s.strip()
            for _n, texto in textos_traduziveis()
            for s in velha.split(texto)
            if s.strip()
        ]
        fraca = re.compile(r",|\s[—\u2013]\s|\s-\s|[()]")
        com_fraca = [s for s in sentencas if fraca.search(s)]
        medido = {
            "sentenças": len(sentencas),
            "vírgula": sum("," in s for s in sentencas),
            "travessão": sum(("—" in s or "\u2013" in s) for s in sentencas),
            "parêntese de abertura": sum("(" in s for s in sentencas),
            "união": len(com_fraca),
            "partidas pela régua de hoje": sum(len(oracoes(s)) > 1 for s in com_fraca),
        }
        soma = sum(medido[k] for k in ("vírgula", "travessão", "parêntese de abertura"))
        assert medido["união"] < soma, (
            "somar as três pontuações conta o mesmo trecho mais de uma vez; se "
            f"a soma virar igual à união, o comentário mente ao dizer isso: {medido}"
        )
        assert medido["união"] >= 100, (
            "a superfície que a régua velha não via era de CENTENAS de trechos; "
            f"se encolheu a este ponto, o motivo do corte fino mudou: {medido}"
        )
        assert medido["partidas pela régua de hoje"] >= medido["união"] - 5, (
            "a régua de hoje tem de partir praticamente toda sentença de "
            f"pontuação fraca — se parou de partir, ela regrediu: {medido}"
        )

    def test_as_duas_camadas_carregam_o_portao_e_nenhuma_sobra(self) -> None:
        """Nem o corte fino nem o apaga-marca é decoração — medido, não suposto.

        A defesa de hoje tem DUAS camadas (`ORACAO_RE` e `_sem_as_marcas`), e a
        pergunta que um cético faz é se uma delas virou redundante depois da
        outra. A resposta é não, e ela se mede com DUAS isenções diferentes:

        * isenção por MARCA — "Envia a cor ao controle selecionado, e …". Aqui
          o apaga-marca sozinho já acusa; o corte fino apenas melhora a mira,
          apontando a oração culpada em vez da sentença inteira.
        * isenção por EXCEÇÃO — "Mostra a bateria do controle, e …", com uma
          linha VIVA de `SINGULAR_LEGITIMO` na primeira oração. O apaga-marca
          não toca em `_justificado`, então com corte grosso ele CALA. Só o
          corte fino separa a oração justificada da mentirosa.

        Tirar qualquer uma das duas devolve silêncio a um dos dois casos.
        """
        velha = re.compile(r"(?<=[.!?;:])\s+|\n+")

        def julga(
            texto: str, rx: re.Pattern[str], apaga_marca: bool, usa_diz: bool
        ) -> list[str]:
            fora = []
            for s in (p.strip().strip("—\u2013-").strip() for p in rx.split(texto)):
                if not s:
                    continue
                alvo = _sem_as_marcas(s) if apaga_marca else s
                if not SINGULAR_RE.search(alvo):
                    continue
                if usa_diz and _diz_o_sujeito(s):
                    continue
                if _justificado(s) is not None:
                    continue
                fora.append(s)
            return fora

        por_marca = f"Envia a cor ao controle selecionado, e {self.MENTIRA}."
        por_excecao = f"Mostra a bateria do controle, e {self.MENTIRA}."
        assert "a bateria do controle" in SINGULAR_LEGITIMO, (
            "o caso da exceção precisa de uma linha VIVA da lista, ou não mede nada"
        )

        # A régua nº 2 — a que a cética derrubou — cala nos dois.
        assert not julga(por_marca, velha, False, True)
        assert not julga(por_excecao, velha, False, True)
        # Apaga-marca com corte GROSSO: pega a isenção por marca, e só ela.
        assert julga(por_marca, velha, True, False)
        assert not julga(por_excecao, velha, True, False), (
            "se este caso passar a acusar, o corte fino virou redundante e a "
            "docstring desta função precisa de outro motivo"
        )
        # Corte fino com `marca in unidade`: pega os dois, mas deixa de pé a
        # oração única de `test_a_marca_nao_compra_silencio_para_a_oracao_inteira`.
        assert julga(por_marca, ORACAO_RE, False, True)
        assert julga(por_excecao, ORACAO_RE, False, True)
        # A de hoje: acusa os dois, e acusa a oração certa.
        for frase in (por_marca, por_excecao):
            assert oracoes_ofensoras(frase) == [f"e {self.MENTIRA}."], frase

    def test_a_marca_de_alvo_tem_de_falar_do_controle(self) -> None:
        """A escotilha que o corte fino NÃO fecharia — e por que ele não bastava.

        Cortar mais fino encolhe a unidade; não mata o mecanismo. Enquanto a
        marca for solta ("selecionado"), uma ORAÇÃO ÚNICA em que a palavra
        qualifica outro substantivo isenta o "o controle" mentiroso da mesma
        oração — e aí não há vírgula nem travessão para cortar.

        Por isso as marcas de `SUJEITO_OU_ALVO` são amarradas ao substantivo.
        Se alguém as afrouxar de volta, esta frase volta a passar calada.
        """
        solta = "Aplica o perfil selecionado no controle."
        assert oracoes(solta) == [solta], "é UMA oração: o corte fino não a alcança"
        assert oracoes_ofensoras(solta) == [solta], (
            "com marca solta esta frase atravessa o portão: o 'selecionado' "
            "fala do PERFIL, e o gesto do rodapé atinge os quatro"
        )
        # E a forma amarrada, que é o léxico real da Lightbar, segue isenta.
        assert not oracoes_ofensoras("Aplica a cor no controle selecionado.")
        assert all(
            "controle" in marca or "PC" in marca for marca in SUJEITO_OU_ALVO
        ), f"marca solta em SUJEITO_OU_ALVO: {SUJEITO_OU_ALVO}"

    def test_a_marca_nao_compra_silencio_para_a_oracao_inteira(self) -> None:
        """O TERCEIRO andar do mesmo mecanismo — e o último que sobrava.

        Amarrar a marca ao substantivo e cortar em orações não matam
        `marca in unidade`: enquanto a pergunta for "a marca APARECE aqui?",
        uma oração que traz a marca LEGÍTIMA fica isenta INTEIRA, e um segundo
        "o controle" sem dono dentro dela passa calado. Aqui não há vírgula
        nem travessão para cortar, e a marca é a de verdade — as duas defesas
        anteriores erram esta frase.

        A cura é apagar a marca ANTES de perguntar (`_sem_as_marcas`): o que
        sobra é exatamente o singular sem dono. Custou zero na árvore de hoje.
        """
        frase = "Envia ao controle selecionado a vibração do controle."

        # UMA oração só — sem vírgula, travessão ou parêntese: o corte fino
        # não tem onde morder, e a marca legítima está dentro dela.
        assert oracoes(frase) == [frase], oracoes(frase)
        assert _diz_o_sujeito(frase), (
            "esta frase só prova alguma coisa se a marca ESTIVER na mesma "
            "oração do singular ofensor"
        )

        # A régua nº 3 (marca in oração, com marca amarrada e corte fino)
        # calava: o `not _diz_o_sujeito(s)` isentava a oração inteira.
        calados = [
            s
            for s in oracoes(frase)
            if SINGULAR_RE.search(s) and not _diz_o_sujeito(s) and _justificado(s) is None
        ]
        assert calados == [], f"a régua nº 3 tinha de calar aqui: {calados}"

        # A de hoje acusa — e acusa a oração certa.
        assert oracoes_ofensoras(frase) == [frase], oracoes_ofensoras(frase)

    def test_nenhuma_excecao_atravessa_o_corte_das_oracoes(self) -> None:
        """O preço do corte fino, cobrado: marca partida nunca casa.

        `_justificado` pergunta `marca in oração`. Uma marca que contenha
        vírgula, travessão ou parênteses fica maior que qualquer oração e vira
        linha morta silenciosa — a exceção parece escrita e não isenta nada.
        Aconteceu com "o controle navega na Steam, mas fica morto", encurtada
        no conserto de 14/08.
        """
        partidas = {m: oracoes(m) for m in SINGULAR_LEGITIMO if len(oracoes(m)) > 1}
        assert not partidas, (
            "exceções que o corte por oração parte ao meio (nunca vão casar):\n"
            + "\n".join(f"  {m!r} -> {ps}" for m, ps in partidas.items())
        )

    def test_a_lista_de_excecoes_nao_tem_linha_morta(self) -> None:
        """Exceção que não corresponde a nenhuma frase viva vira desculpa velha."""
        todos = self._todos()
        mortas = [marca for marca in SINGULAR_LEGITIMO if marca not in todos]
        assert not mortas, f"exceções que não existem mais na tela: {mortas}"

    def test_toda_excecao_declara_categoria(self) -> None:
        """O contrato da lista, cobrado — e o ADIADO tem de nomear o dono.

        A contradição que este teste fecha: a docstring prometia "só entra
        quando o singular é VERDADE" enquanto uma linha dizia "pluralizar é
        dela". Agora são duas categorias declaradas, e a cara delas custa uma
        palavra: quem adia tem de escrever de quem é a decisão.
        """
        sem_categoria = [
            m for m, motivo in SINGULAR_LEGITIMO.items()
            if not motivo.startswith(CATEGORIAS)
        ]
        assert not sem_categoria, (
            f"exceções sem categoria VERDADE:/ADIADO: {sem_categoria}"
        )
        adiadas = {
            m: motivo
            for m, motivo in SINGULAR_LEGITIMO.items()
            if motivo.startswith("ADIADO:")
        }
        sem_dono = [m for m, motivo in adiadas.items() if "dela" not in motivo.lower()]
        assert not sem_dono, f"ADIADO sem nomear o dono da decisão: {sem_dono}"
        assert len(adiadas) == 1, (
            "o ADIADO é caro de propósito: se virou dois, a categoria virou "
            f"escotilha — {sorted(adiadas)}"
        )

    def test_nenhuma_frase_promete_o_mundo_de_dois_controles(self) -> None:
        """A quarta cura — a que a régua do singular NÃO via.

        `profile_steam_input_hint` dizia "Marque quando o jogo mostrar dois
        controles". Com quatro na mesa o jogo mostra OITO, e o texto está no
        plural — então `SINGULAR_RE` passava por ele sem ver nada. O léxico
        certo já existia na caixinha logo acima: controles DOBRADOS.
        """
        dois = re.compile(r"\bdois\s+controles\b", re.IGNORECASE)
        acusados = [
            (nome, texto) for nome, texto in textos_traduziveis() if dois.search(texto)
        ]
        assert not acusados, (
            "frases que ainda contam DOIS controles:\n"
            + "\n".join(f"  {n}: {t[:120]}" for n, t in acusados)
        )
        dica = self._texto_do_widget("profile_steam_input_hint.label")
        assert "os seus controles dobrados" in dica
        assert "A marca vale para o jogo inteiro" in dica

    def test_o_censo_do_comentario_bate_com_a_arvore(self) -> None:
        """DEFEITO D — o comentário do censo dizia 38/18/20, e nada disso era o
        medido. Fato errado se SUBSTITUI; e para não envelhecer calado de novo,
        a contagem é recomputada aqui, contra o `.glade` de HEAD.

        Se este teste reprovar depois de uma mexida legítima no `.glade`, a
        correção é atualizar o comentário do censo — não afrouxar o teste.
        """
        velho_xml = subprocess.run(
            ["git", "show", f"{CENSO_BASE}:src/hefesto_dualsense4unix/gui/main.glade"],
            capture_output=True,
            text=True,
            cwd=GLADE.parents[3],
            check=False,
        )
        if velho_xml.returncode != 0:
            pytest.skip("sem git ou sem a base do censo nesta árvore")

        velho = _textos_de_xml(ET.fromstring(velho_xml.stdout))
        novo = textos_traduziveis()
        textos_novos = {t for _n, t in novo}
        partida = [(n, t) for n, t in velho if SINGULAR_RE.search(t)]
        mexidos = [(n, t) for n, t in partida if t not in textos_novos]
        intocados = [(n, t) for n, t in partida if t in textos_novos]

        assert len(partida) == 61, "o ponto de partida do censo"
        assert len(mexidos) == 41
        assert len(intocados) == 20
        assert sum(_diz_o_sujeito(t) for _n, t in intocados) == 5, (
            "os que já diziam 'controle selecionado' antes (a Lightbar)"
        )

    def test_o_doctor_tambem_para_de_falar_no_singular(self) -> None:
        """`storm_doctor` manda RECONECTAR — e são os quatro a reconectar."""
        conf = Path("/nao-existe/hefesto-dualsense-storm.conf")
        _tag, msg = sd.check_snd_quirk(quirk_flags_text="", conf_path=conf)
        assert "os controles" in msg
        assert "reconecte o controle " not in msg

    def test_as_tres_frases_da_sprint_que_ficam_como_estao_e_por_que(self) -> None:
        """DEFEITO B — os itens 4, 5 e 7 da sprint ficaram intocados, e a
        primeira entrega não disse UMA palavra sobre eles. Silêncio não é
        decisão; aqui cada um tem veredito escrito, e o veredito é PINADO — se
        alguém mudar a frase, este teste reprova e obriga a rever o motivo.

        Nenhum dos três é alcançado por `SINGULAR_RE`: dois não dizem "o
        controle" (dizem "do DualSense" e "Gamepad"), e o terceiro vive em
        Python, fora da varredura do `.glade`. Foi por isso que passaram.

        4) "Microfone do DualSense:" — FICA. Não é um gesto sobre uma peça: o
           botão roda um script do WirePlumber
           (`assets/wireplumber/51-hefesto-dualsense-no-default-source.conf`,
           `emulation_actions._run_mic`) que é regra de SISTEMA para o MODELO
           DualSense, e vale para todo DualSense da máquina de uma vez. É o
           mesmo motivo já escrito na exceção "ajusta o áudio do controle".
           Pluralizar aqui inventaria a ideia de quatro microfones ajustáveis
           um a um, que não existe.

        5) "Gamepad para os jogos:" — FICA. Nomeia o CANAL, e o estado embaixo
           dele é o MODO da máquina, não uma contagem: a D-6 diz por escrito
           que "`mode` e a máscara do gamepad são da SESSÃO, não da peça"
           (`profiles/schema.py:637`). Há um valor só para os quatro, e é ele
           que o rótulo anuncia. Se a D-5 (máscara por jogador) for medida e
           executada, este rótulo volta à mesa — e é o único dos três que muda
           de resposta se a D-5 mudar.

        7) "O jogo vê o controle como:" — MENTE, e a correção NÃO é minha: a
           máscara é reescrita nos quatro vpads a partir de um `gamepad_flavor`
           só. É léxico DELA, em quatro módulos, nos testes e em dois documentos
           de uso. Está registrado como `ADIADO:` na `SINGULAR_LEGITIMO` — a
           única linha dessa categoria — para que a dívida apareça na lista em
           vez de sumir num relatório.
        """
        textos = [t for _n, t in textos_traduziveis()]
        assert "Microfone do DualSense:" in textos
        assert "Gamepad para os jogos:" in textos
        assert SINGULAR_LEGITIMO["Como o jogo vê o controle"].startswith("ADIADO:")

        # O item 7 no Python: a frase é UMA e vive em quatro lugares. Se ela
        # for pluralizada, é para ser pluralizada em todos — e é por isso que a
        # decisão é dela.
        raiz = GLADE.parents[2] / "hefesto_dualsense4unix"
        donos = sorted(
            p.name
            for p in raiz.rglob("*.py")
            if "O jogo vê o controle como:" in p.read_text(encoding="utf-8")
        )
        assert donos == [
            "home_actions.py",
            "painel_no_jogo.py",
            "profiles_actions.py",
            "relancar.py",
        ], donos

    def test_a_intensidade_global_fica_de_fora_ate_a_d_4(self) -> None:
        """Nota datada, não esquecimento: "Intensidade global:" é o único
        rótulo honesto sobre o daemon hoje e mentiroso sobre a gravação (que é
        por peça, `app/actions/rumble_actions.py`). Mudá-lo antes da D-4 é
        escolher a resposta pela porta dos fundos — a sprint o tirou da E4 de
        propósito, e este teste é o lembrete de que a omissão é deliberada."""
        assert "Intensidade global:" in [t for _n, t in textos_traduziveis()]

    def test_o_glade_continua_sendo_xml_valido(self) -> None:
        raiz = ET.parse(GLADE).getroot()
        assert raiz.find(".//object[@id='main_window']") is not None


# ---------------------------------------------------------------------------
# DEFEITO C — trocar o texto troca o MSGID, e o inglês fica para trás
# ---------------------------------------------------------------------------
#
# A E4 trocou 43 textos traduzíveis do `.glade`. Cada troca cria um msgid novo,
# e o msgid velho — com a tradução dele — vira lixo. Sete tooltips que TINHAM
# inglês passaram a sair em português numa sessão `LANG=en`, sem nada ficar
# vermelho: a suíte não olhava para `locale/`.
#
# Medido com o `.mo` compilado (não com o `.po`, que conta fuzzy que o `msgfmt`
# descarta): 107 de 318 textos do `.glade` tinham inglês antes; depois da E4,
# 100 de 319; hoje, 107 de 319. Os sete voltaram.
#
# O caminho é o da casa, e ele já existia: `scripts/i18n_extract.sh` (xgettext
# + msgmerge) e `scripts/i18n_compile.sh` (msgfmt). O que NÃO é automático é
# traduzir — o msgmerge só marca `fuzzy`, e fuzzy o msgfmt não compila. As sete
# entradas foram preenchidas à mão no `po/en.po`, que é o arquivo de tradutor;
# o `.mo` continua sendo só saída de compilação.
#
# O QUE ESTE BLOCO NÃO COBRE, declarado: rodar o extract mostrou que o catálogo
# estava rançoso MUITO além da E4 — 197 mensagens sem inglês nenhum, de várias
# levas. Isso é dívida antiga, não regressão desta leva, e não se conserta aqui.


class TestOInglesNaoFicaParaTras:
    #: Cada um pelo TRECHO que o identifica no `.glade`. Por trecho e não pelo
    #: msgid inteiro por um motivo escrito: dois deles são as descrições
    #: acessíveis dos gatilhos, e o `.glade` escreve ali a palavra "configuração"
    #: sem a cedilha e sem o til. O portão de acentuação isenta `.glade`
    #: (whitelist `.*\.glade$`, decisão da casa), então o erro passou; copiá-lo
    #: para cá reprovaria o portão, e corrigi-lo no `.glade` trocaria o msgid
    #: OUTRA VEZ — que é justamente o defeito que este bloco existe para pegar.
    #: Fica no relatório, para ela decidir.
    SETE: ClassVar[tuple[str, ...]] = (
        "do gatilho esquerdo ao controle selecionado",
        "do gatilho direito ao controle selecionado",
        "Envia cor selecionada para a barra de LED do controle selecionado",
        "Desliga a barra de LED do controle selecionado",
        "Máscara Xbox 360: a vibração funciona em jogo e os controles não "
        "aparecem duplicados.",
        "Envia toda a configuração (gatilhos, LEDs, rumble, mouse) aos controles",
        "Envia gatilhos LEDs rumble e mouse aos controles",
    )

    def _catalogo(self) -> gettext.NullTranslations:
        mo = GLADE.parents[3] / "locale" / "en" / "LC_MESSAGES"
        mo = mo / "hefesto-dualsense4unix.mo"
        with mo.open("rb") as f:
            return gettext.GNUTranslations(f)

    def _msgids(self) -> list[str]:
        """Os sete msgids inteiros, resolvidos contra o `.glade` de hoje."""
        textos = [t for _n, t in textos_traduziveis()]
        achados = []
        for trecho in self.SETE:
            iguais = [t for t in textos if trecho in t]
            assert iguais, f"o trecho sumiu do .glade: {trecho[:60]}"
            achados.append(iguais[0])
        return achados

    def test_os_sete_tooltips_falam_ingles_de_novo(self) -> None:
        """A MORDIDA do defeito C: cada um sai em inglês no `.mo` COMPILADO."""
        cat = self._catalogo()
        msgids = self._msgids()
        mudos = [t for t in msgids if cat.gettext(t) == t]
        assert not mudos, (
            "tooltips que voltaram a sair em português sob LANG=en "
            "(rode scripts/i18n_extract.sh e scripts/i18n_compile.sh):\n"
            + "\n".join(f"  {t[:90]}" for t in mudos)
        )
        # E o inglês tem de acompanhar a MUDANÇA, não repetir o texto velho.
        assert "selected controller" in cat.gettext(msgids[0])
        assert "controllers" in cat.gettext(msgids[5])

    def test_a_cobertura_de_ingles_nao_regride(self) -> None:
        """O piso medido hoje. Trocar texto sem regenerar derruba este número.

        Não é meta de tradução — é catraca: 107 é o que havia ANTES da E4, e a
        E4 tinha derrubado para 100 sem ninguém perceber.
        """
        cat = self._catalogo()
        com_ingles = sum(1 for _n, t in textos_traduziveis() if cat.gettext(t) != t)
        assert com_ingles >= 107, (
            f"{com_ingles} textos do .glade com inglês; eram 107 antes da E4. "
            "Trocar msgid sem rodar scripts/i18n_extract.sh + i18n_compile.sh "
            "deixa o inglês para trás."
        )

    def test_os_catalogos_compilados_estao_versionados(self) -> None:
        """O `.mo` é artefato, mas é artefato VERSIONADO — os builds o leem."""
        raiz = GLADE.parents[3]
        for alvo in (
            raiz / "locale" / "en" / "LC_MESSAGES" / "hefesto-dualsense4unix.mo",
            raiz
            / "src"
            / "hefesto_dualsense4unix"
            / "locale"
            / "en"
            / "LC_MESSAGES"
            / "hefesto-dualsense4unix.mo",
        ):
            assert alvo.exists(), alvo


# ---------------------------------------------------------------------------
# E1 (1.7) — o `native_bt_fragil` POR CONTROLE
# ---------------------------------------------------------------------------
#
# O pior dos três defeitos desta sprint, porque é FALSO NEGATIVO: a flag era
# `native_mode and transport == "bt"` com o `transport` do PRIMÁRIO, então com
# o Controle 1 no cabo e os outros no rádio o aviso calava justamente para os
# frágeis — e ela concluía que estava tudo bem.
#
# A AMBIGUIDADE DO DADO DE HOJE, resolvida e escrita aqui para não se
# reinvestigar: o payload real de 14/08 tem DOIS controles em BT e
# `native_bt_fragil: false`. Isso NÃO prova o defeito — o mesmo payload traz
# `native_mode: false`, e com o Modo Nativo desligado `false` é a resposta
# CERTA. A prova está no primeiro teste abaixo, que liga o Modo Nativo sobre o
# mesmo payload: a regra velha continua dizendo `False` com dois frágeis na
# mesa.

import asyncio
from unittest.mock import MagicMock

from hefesto_dualsense4unix.app.actions.base import numero_do_controle
from hefesto_dualsense4unix.app.actions.home_actions import (
    NATIVE_BT_FRAGIL_TEXT,
    controles_bt_frageis,
    texto_native_bt_fragil,
)
from hefesto_dualsense4unix.daemon import ipc_handlers as ih


def regra_velha(state: dict[str, Any]) -> bool:
    """A flag como ela era até 14/08: o Modo Nativo e o transporte do PRIMÁRIO."""
    return bool(state["native_mode"] and state["transport"] == "bt")


class TestOAvisoDeBtFragilOlhaTodaAMesa:
    def test_o_payload_real_com_o_nativo_desligado_nao_prova_nada(self) -> None:
        """A ressalva do dado, virada teste: `false` ali é `false` legítimo."""
        state = mesa_cheia()
        assert state["native_mode"] is False
        assert [c["transport"] for c in state["controllers"]] == [
            "usb",
            "usb",
            "bt",
            "bt",
        ]
        assert state["native_bt_fragil"] is False
        assert ih.controles_bt_frageis(state["controllers"], native_mode=False) == []

    def test_a_mordida_o_primario_no_cabo_calava_pelos_do_radio(self) -> None:
        """MORDIDA 1: mesmo payload, Modo Nativo LIGADO — a regra velha cala.

        Dois controles no rádio, o primário no cabo: `native_mode and
        transport == "bt"` devolve False e a janela não diz nada. A regra nova
        nomeia os dois.
        """
        state = mesa_cheia()
        state["native_mode"] = True
        assert state["transport"] == "usb"  # o primário está no cabo
        assert regra_velha(state) is False, "a régua da mordida"

        frageis = ih.controles_bt_frageis(state["controllers"], native_mode=True)
        assert frageis == [2, 3], "os dois do rádio, pelo número do CARD"
        assert "Controles 2 e 3" in texto_native_bt_fragil(frageis)

    def test_o_caso_da_sprint_um_no_cabo_e_tres_no_radio(self) -> None:
        state = mesa_cheia()
        state["native_mode"] = True
        for c in state["controllers"]:
            if not c["is_primary"]:
                c["transport"] = "bt"
        assert regra_velha(state) is False
        frageis = ih.controles_bt_frageis(state["controllers"], native_mode=True)
        assert len(frageis) == 3
        assert "Controles 1, 2 e 3" in texto_native_bt_fragil(frageis)

    def test_todos_no_cabo_nao_inventa_aviso(self) -> None:
        state = mesa_cheia()
        for c in state["controllers"]:
            c["transport"] = "usb"
        assert ih.controles_bt_frageis(state["controllers"], native_mode=True) == []

    def test_o_controle_que_saiu_da_mesa_nao_conta(self) -> None:
        """Entrada desconectada não é um controle frágil — é um ausente."""
        state = mesa_cheia()
        for c in state["controllers"]:
            c["transport"] = "bt"
            c["connected"] = False
        assert ih.controles_bt_frageis(state["controllers"], native_mode=True) == []

    def test_payload_dublado_nao_derruba_o_state_full(self) -> None:
        """Um aviso de tela nunca pode explodir o handler que roda a 10 Hz."""
        assert ih.controles_bt_frageis(None, native_mode=True) == []
        assert ih.controles_bt_frageis(MagicMock(), native_mode=True) == []
        assert ih.controles_bt_frageis(["lixo", 7, None], native_mode=True) == []
        assert ih.controles_bt_frageis([{}], native_mode=True) == []


class TestONumeroEODoCard:
    def test_o_daemon_numera_igualzinho_a_janela(self) -> None:
        """O portão contra a divergência das duas cópias da regra.

        `daemon/ipc_handlers._numero_de_exibicao` e
        `app/actions/base.numero_do_controle` são a MESMA regra em dois lados
        do socket (a da janela mora em `base.py`, que importa `gi` — o daemon
        não pode importá-la). Se uma mudar sozinha, o aviso passa a apontar um
        card que não existe.
        """
        for entry in mesa_cheia()["controllers"]:
            assert ih._numero_de_exibicao(entry) == numero_do_controle(entry)

    def test_o_numero_e_o_do_controle_e_nao_o_do_jogador(self) -> None:
        """No payload real os dois DIVERGEM — por isso a escolha importa."""
        state = mesa_cheia()
        slots = [c["player_slot"] for c in state["controllers"]]
        jogadores = [c["player"] for c in state["controllers"]]
        assert slots == [4, 1, 3, 2]
        assert jogadores == [1, 2, 3, 4]
        assert slots != jogadores, "a medição que torna a escolha visível"

        state["native_mode"] = True
        frageis = ih.controles_bt_frageis(state["controllers"], native_mode=True)
        # Os frágeis são os índices 2 e 3: slots 3 e 2, jogadores 3 e 4.
        assert frageis == [2, 3]
        assert frageis != sorted(jogadores[2:])

    def test_sem_slot_cai_na_posicao_como_a_janela_cai(self) -> None:
        entry = {"index": 2, "connected": True, "transport": "bt"}
        assert ih._numero_de_exibicao(entry) == 3
        assert numero_do_controle(entry) == 3


class TestOBannerDaJanelaNomeiaOsFrageis:
    def test_a_janela_le_a_lista_e_nomeia(self) -> None:
        state = mesa_cheia()
        state["native_mode"] = True
        state["native_bt_fragil"] = True
        state["native_bt_fragil_controles"] = [2, 3]
        texto = vpad_degradation_text(state)
        assert texto is not None
        assert "Controles 2 e 3" in texto
        assert texto != NATIVE_BT_FRAGIL_TEXT

    def test_um_so_fragil_fala_no_singular_com_o_numero(self) -> None:
        assert "o Controle 4 em Bluetooth" in texto_native_bt_fragil([4])

    def test_daemon_velho_ainda_acende_o_aviso_generico(self) -> None:
        """Install editable: o daemon vivo é mais velho que a janela.

        Sem a chave nova, o booleano antigo continua acendendo o banner — só
        que sem nomes. Perder o aviso aqui seria trocar um falso negativo por
        outro.
        """
        state = mesa_cheia()
        state["native_mode"] = True
        state["native_bt_fragil"] = True
        state.pop("native_bt_fragil_controles", None)
        assert controles_bt_frageis(state) == []
        assert vpad_degradation_text(state) == NATIVE_BT_FRAGIL_TEXT

    def test_sem_fragil_nenhum_a_janela_continua_calada(self) -> None:
        state = mesa_cheia()
        state["native_bt_fragil"] = False
        state["native_bt_fragil_controles"] = []
        assert vpad_degradation_text(state) is None

    def test_a_lista_suja_nao_vira_texto_torto(self) -> None:
        state = mesa_cheia()
        state["native_bt_fragil"] = True
        state["native_bt_fragil_controles"] = ["dois", None, True]
        assert controles_bt_frageis(state) == []
        assert vpad_degradation_text(state) == NATIVE_BT_FRAGIL_TEXT

    def test_o_texto_novo_nao_perde_a_saida(self) -> None:
        """Nomear não pode custar o conselho: cabo USB ou emulação."""
        for texto in (texto_native_bt_fragil([1]), texto_native_bt_fragil([1, 2])):
            assert "cabo USB" in texto
            assert "emulação de gamepad" in texto
            assert "Bluetooth" in texto


#: Primário no CABO, os outros três no rádio — o caso da sprint. MACs com a
#: máscara de `tests/` (prefixo `aabbcc`, allowlist do portão de anonimato).
MESA_UM_NO_CABO = [
    {"index": 0, "connected": True, "transport": "usb",
     "is_primary": True, "uniq": "aabbcc0000d8"},
    {"index": 1, "connected": True, "transport": "bt",
     "is_primary": False, "uniq": "aabbcc000003"},
    {"index": 2, "connected": True, "transport": "bt",
     "is_primary": False, "uniq": "aabbcc0000f0"},
    {"index": 3, "connected": True, "transport": "bt",
     "is_primary": False, "uniq": "aabbcc0000ab"},
]


class TestAFiacaoNoStateFull:
    """Fiação de verdade: `daemon.state_full` por um IpcServer real."""

    def _resultado(self, controllers: list[dict[str, Any]], *, nativo: bool) -> dict:
        from hefesto_dualsense4unix.cli.ipc_client import IpcClient
        from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
        from hefesto_dualsense4unix.daemon.state_store import StateStore
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.testing import FakeController

        async def corpo(caminho: Path) -> dict[str, Any]:
            fc = FakeController(transport="usb")
            fc.connect()
            fc.describe_controllers = lambda: [dict(c) for c in controllers]
            store = StateStore()
            daemon = MagicMock()
            daemon._last_state = None
            daemon.is_native_mode.return_value = nativo
            daemon.is_paused.return_value = False
            server = IpcServer(
                controller=fc,
                store=store,
                profile_manager=ProfileManager(controller=fc, store=store),
                socket_path=caminho,
                daemon=daemon,
            )
            await server.start()
            try:
                async with IpcClient.connect(caminho) as client:
                    resultado = await client.call("daemon.state_full")
            finally:
                await server.stop()
            assert isinstance(resultado, dict)
            return resultado

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            return asyncio.run(corpo(Path(tmp) / "hefesto.sock"))

    def test_o_state_full_publica_os_quatro_numeros(self) -> None:
        resultado = self._resultado(MESA_UM_NO_CABO, nativo=True)
        # O `transport` do topo é o do PRIMÁRIO — aqui ele não é "bt" (o
        # FakeController não alimenta o último estado, então sai `None`), e é
        # exatamente por isso que a flag velha calaria com três no rádio.
        assert resultado["transport"] != "bt"
        assert resultado["controllers"][0]["transport"] == "usb"
        assert regra_velha(resultado) is False, "a régua: a flag velha calaria"
        assert resultado["native_bt_fragil_controles"] == [2, 3, 4]
        assert resultado["native_bt_fragil"] is True
        texto = vpad_degradation_text(resultado)
        assert texto is not None and "Controles 2, 3 e 4" in texto

    def test_fora_do_modo_nativo_o_state_full_cala(self) -> None:
        resultado = self._resultado(MESA_UM_NO_CABO, nativo=False)
        assert resultado["native_bt_fragil_controles"] == []
        assert resultado["native_bt_fragil"] is False

    def test_o_doctor_le_a_lista_nova(self) -> None:
        """Rede de RENOME — a mordida do doctor NÃO está aqui (CONSERTO 1.7).

        Este assert é substring de fonte, e substring de fonte não morde: em
        14/08/2026 um cético arrancou a cura inteira do `scripts/doctor.sh` (o
        ramo que nomeia, a variável e o `sed` que a extrai, deixando só o
        `print` do trecho python) e 756 testes seguiram verdes, este inclusive
        — o anti-padrão que TESTE-HONESTO-01 condenou por escrito para ESTA
        MESMA flag. Quem EXECUTA o doctor contra um daemon de mentira é
        `tests/unit/test_conserto_1_7_o_ramo_sem_mesa_e_o_plural_do_doctor.py`.
        O que sobra aqui é só a mensagem legível para quem renomear a chave.
        """
        doctor = (
            Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"
        ).read_text(encoding="utf-8")
        assert "native_bt_fragil_controles" in doctor
        assert "native_bt_quais" in doctor
