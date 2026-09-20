"""POINT-AND-CLICK-01 — o modo Navegação carregando o PERFIL, e não a sessão.

A ordem dela, 17/09/2026, olhando a aba principal do produto aberto:

    *"E o modo point and click é o modo navegação e o modo que nós mesmos
    podemos usar e configurar na aba navegação. **Ele ativa o modo configurado
    lá.**"*

A primeira metade já existia. A segunda era o defeito: o terceiro passo da
transição para o `MODE_DESKTOP` era `mouse.emulation.restore`, que lê a **flag
de sessão no disco** — um arquivo único da máquina, que não abre perfil nenhum.
Entrar no modo descartava, em silêncio, as cinco coisas que a aba Navegação
grava no perfil: `mouse`, `teclado_emulado`, `key_bindings`, `button_actions` e
a supressão.

O QUE ESTA RÉGUA LÊ é o que o **daemon RECEBEU**, nunca o que a tela pediu. O
dublê é SUBCLASSE do `Daemon` real — herda as assinaturas, e por isso um dublê
mais frouxo que o produto não pode nascer aqui (*foi assim que a máscara nunca
gravou um byte*). Toda a política medida é a do produto: `apply_profile_mouse`,
`resolver_teclado_emulado` e o recuo rodam de verdade.

OS TRÊS NÚMEROS SÃO 11, 3 E 6 DE PROPÓSITO, e escolhê-los é o que faz esta
régua medir:

    perfil ativo     mouse.speed = 11
    flag de sessão   speed = 3
    default da config speed = 6

Com o perfil em 6 e a flag ausente, o recuo devolveria o MESMO 6 e a régua
passaria com o defeito de pé. Este é o furo que mata réguas desta família, e
ele se fecha escolhendo os números — não escrevendo mais asserções.

O FURO DESTA RÉGUA, dito porque a casa exige: ela mede o **daemon**, não o
**aparelho**. Um `set_mouse_emulation` que devolve `True` não prova cursor na
tela — foi assim que *"aplicado"* apareceu sobre nada quatro vezes numa
madrugada. A prova do aparelho é da bancada dela.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Literal

import pytest

RAIZ = Path(__file__).resolve().parents[2]
#: O `pacotes/` mora dentro de `interface/` e não é pacote instalável — é o
#: mesmo empurrão de `sys.path` que `test_a_aba01_le_o_estado_em_vez_de_cravar`
#: faz, e ele existe porque o `ponte.TETOS` é o dono do teto de tempo.
for _caminho in (
    str(RAIZ / "src"),
    str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"),
):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    plan_mode_transition,
)
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.session import config_dir

#: O QUE O PERFIL DIZ. Diferente da flag de sessão em TODOS os campos.
PERFIL_DA_NAVEGACAO: dict[str, Any] = {
    "name": "A Navegação Dela",
    "match": {"type": "any"},
    "mouse": {"enabled": True, "speed": 11, "scroll_speed": 4},
    "key_bindings": {"l1": ["KEY_LEFTSHIFT"], "options": ["KEY_ESC"]},
    "teclado_emulado": True,
}

#: O QUE A FLAG DE SESSÃO DIZ — o que o produto lia ANTES da cura.
FLAG_DA_SESSAO: dict[str, Any] = {"enabled": True, "speed": 3, "scroll_speed": 1}


class _TecladoDeMentira:
    """Device de teclado que só anota. Sem uinput, sem nó em `/dev`."""

    def __init__(self) -> None:
        self.bindings: list[dict[str, Any]] = []

    def set_bindings(self, mapping: Any) -> None:
        self.bindings.append(dict(mapping))


class _DaemonQueAnota(Daemon):
    """SUBCLASSE do daemon real — herda as assinaturas, anota o que recebeu.

    Só os três setters que tocam aparelho são interceptados. Tudo o que decide
    (`apply_profile_mouse`, o recuo, `resolver_teclado_emulado`) é o código do
    produto rodando.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.recebeu: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._keyboard_device = _TecladoDeMentira()

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        # SEM DEFAULT em `origin`, porque o produto também não tem. Medido em
        # 17/09/2026 com `inspect.signature`: o dublê nascera com
        # `origin: str = "manual"`, e um chamador que ESQUECESSE a origem
        # estouraria no daemon real e passaria aqui. *Dublê mais frouxo que o
        # produto é como a máscara nunca gravou um byte.*
        self.recebeu.append(
            ("set_mouse_emulation", (enabled, speed, scroll_speed), {"origin": origin})
        )
        self.config.mouse_emulation_enabled = bool(enabled)
        return True

    def set_mouse_speed(
        self, speed: int | None = None, scroll_speed: int | None = None
    ) -> bool:
        self.recebeu.append(("set_mouse_speed", (speed, scroll_speed), {}))
        return True

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        self.recebeu.append(
            ("set_keyboard_emulation", (enabled,), {"persist": persist})
        )
        return True

    def set_emulation_suppressed(
        self,
        value: bool | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        self.recebeu.append(
            ("set_emulation_suppressed", (value,), {"origin": origin})
        )
        return bool(value)

    # --- as perguntas que a régua faz ao que foi recebido -------------------
    def chamada(self, metodo: str) -> tuple[Any, ...] | None:
        for nome, args, _kwargs in self.recebeu:
            if nome == metodo:
                return args
        return None

    def metodos(self) -> list[str]:
        return [nome for nome, _a, _k in self.recebeu]


def _gravar_perfil(nome_do_arquivo: str, corpo: dict[str, Any]) -> None:
    pasta = Path(config_dir()) / "profiles"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome_do_arquivo}.json").write_text(
        json.dumps(corpo, ensure_ascii=False), encoding="utf-8"
    )


def _gravar_flag_do_mouse(corpo: dict[str, Any] | None) -> None:
    alvo = Path(config_dir()) / "mouse_emulation.flag"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if corpo is None:
        alvo.unlink(missing_ok=True)
        return
    alvo.write_text(json.dumps(corpo), encoding="utf-8")


def _daemon_com(perfil: dict[str, Any] | None) -> _DaemonQueAnota:
    """Um daemon com o perfil de teste ATIVO, ou sem perfil nenhum."""
    d = _DaemonQueAnota(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(mouse_speed=6, mouse_scroll_speed=1),
    )
    if perfil is not None:
        _gravar_perfil("a-navegacao-dela", perfil)
        d.store.set_active_profile("a-navegacao-dela")
    return d


# ---------------------------------------------------------------------------
# 1. O PLANO — a fonte trocou, e a ordem NÃO
# ---------------------------------------------------------------------------
def test_o_terceiro_passo_do_modo_le_o_perfil_e_nao_a_sessao() -> None:
    """O plano do `MODE_DESKTOP` termina em `desktop.arranjo.apply`.

    Ele vem POR ÚLTIMO pelo mesmo motivo de sempre (HARM-06): ligar o mouse
    antes de o gamepad sair faria a exclusão mútua do daemon derrubar o mouse
    recém-ligado.
    """
    passos = plan_mode_transition(MODE_DESKTOP)
    metodos = [m for m, _p in passos]
    assert metodos == [
        "native.mode.set",
        "gamepad.emulation.set",
        "desktop.arranjo.apply",
    ], f"a definição do modo desktop se moveu: {metodos}"
    assert passos[-1][1] == {"origin": "manual"}, (
        "o arranjo tem de DECLARAR que é gesto dela — o silêncio é lido como "
        "reconciliação (ORIGEM-QUE-MENTE-01) e não fura o lock de 30 s do "
        f"`apply_profile_mouse`: {passos[-1][1]}"
    )
    assert "mouse.emulation.restore" not in metodos, (
        "o passo que lê a FLAG DE SESSÃO voltou ao plano. Ele não abre perfil "
        "nenhum, e o modo volta a descartar o que a aba Navegação gravou."
    )


# ---------------------------------------------------------------------------
# 2. O MOUSE — o perfil manda, e o número prova de onde ele veio
# ---------------------------------------------------------------------------
def test_o_arranjo_liga_o_mouse_com_as_velocidades_do_perfil() -> None:
    """11 e 4 saem do PERFIL. 3 seria a flag de sessão; 6, o default."""
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    args = d.chamada("set_mouse_emulation")
    assert args is not None, (
        "o daemon não recebeu `set_mouse_emulation` nenhum — o arranjo não "
        f"chegou ao mouse. Recebeu: {d.metodos()}"
    )
    ligado, speed, scroll = args
    assert ligado is True
    assert speed == 11, (
        f"o mouse ligou com speed {speed}, e o perfil dela diz 11. "
        "3 é a flag de sessão (o defeito) e 6 é o default da config."
    )
    assert scroll == 4, (
        f"o mouse ligou com scroll_speed {scroll}, e o perfil dela diz 4."
    )


def test_o_recuo_e_a_flag_de_sessao_e_nunca_um_segundo_default() -> None:
    """Perfil SEM a seção `mouse` recua para a flag — 3, e não 6.

    *Nenhum perfil existente muda de comportamento no dia da cura*: quem não
    opina continua governado pela preferência da máquina. Se aqui saísse 6, o
    recuo teria virado um segundo default digitado no meio do caminho — o
    defeito com outra roupa.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    sem_mouse = {k: v for k, v in PERFIL_DA_NAVEGACAO.items() if k != "mouse"}
    d = _daemon_com(sem_mouse)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    args = d.chamada("set_mouse_emulation")
    assert args is not None, f"o recuo não chegou ao mouse: {d.metodos()}"
    _ligado, speed, scroll = args
    assert (speed, scroll) == (3, 1), (
        f"o recuo devolveu speed={speed}, scroll={scroll}. A flag de sessão diz "
        "(3, 1); (6, 1) é o default da config — um segundo default digitado."
    )


def test_o_socorro_do_ps_r3_ignora_o_perfil_que_desliga_o_mouse() -> None:
    """`forcar_mouse=True` devolve o cursor mesmo com `enabled: false`.

    O PS + R3 é uma das duas saídas de emergência quando o jogo não responde.
    Obedecer a um perfil com o mouse desligado tiraria dela o cursor justamente
    quando ela não tem outro caminho — é a diferença entre uma escolha e um
    socorro. As velocidades continuam saindo do perfil.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    desligado = dict(PERFIL_DA_NAVEGACAO)
    desligado["mouse"] = {"enabled": False, "speed": 11, "scroll_speed": 4}
    d = _daemon_com(desligado)

    d.aplicar_o_arranjo_do_desktop(origin="manual", forcar_mouse=True)

    args = d.chamada("set_mouse_emulation")
    assert args is not None, f"o socorro não chegou ao mouse: {d.metodos()}"
    ligado, speed, scroll = args
    assert ligado is True, (
        "o PS + R3 obedeceu ao `mouse.enabled: false` do perfil e deixou ela "
        "sem cursor no modo que existe para lhe devolver o cursor."
    )
    assert (speed, scroll) == (11, 4), (
        f"o socorro ligou o mouse com ({speed}, {scroll}) e o perfil diz (11, 4)"
    )


def test_o_clique_no_chip_obedece_ao_perfil_que_desliga_o_mouse() -> None:
    """O contrapeso do socorro: sem `forcar_mouse`, a escolha dela vence.

    Sem esta metade, `forcar_mouse` viraria "sempre liga" e o perfil voltaria a
    não ser lido — a cura teria o nome novo e o comportamento velho.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    desligado = dict(PERFIL_DA_NAVEGACAO)
    desligado["mouse"] = {"enabled": False, "speed": 11, "scroll_speed": 4}
    d = _daemon_com(desligado)
    d.config.mouse_emulation_enabled = True
    d._mouse_device = object()

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    args = d.chamada("set_mouse_emulation")
    assert args is not None, f"o chip não chegou ao mouse: {d.metodos()}"
    assert args[0] is False, (
        "o chip ligou o mouse que o perfil dela manda deixar desligado — o "
        "perfil deixou de ser lido."
    )


# ---------------------------------------------------------------------------
# 3. O TECLADO — o fio que a T14 entregou e ninguém tinha ligado
# ---------------------------------------------------------------------------
def test_o_arranjo_liga_o_teclado_emulado_do_perfil() -> None:
    """`resolver_teclado_emulado` ganhou o primeiro chamador de ativação real.

    Até 17/09/2026 os únicos chamadores daquela função eram duas réguas e uma
    isenção declarada: a "Função do teclado" que ela escolhe na aba Navegação ia
    ao disco e **nunca voltava**.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    args = d.chamada("set_keyboard_emulation")
    assert args is not None, (
        "o daemon nunca recebeu `set_keyboard_emulation` — o `teclado_emulado` "
        f"do perfil continua sem fio nenhum. Recebeu: {d.metodos()}"
    )
    assert args[0] is True


def test_o_teclado_do_perfil_nao_vira_a_preferencia_global() -> None:
    """`persist=False`, e a razão é a precedência da T14.

    Gravar o valor RESOLVIDO em `keyboard_emulation.flag` faria a opinião do
    PERFIL virar a preferência GLOBAL: o perfil que dissesse `true` uma vez
    mandaria para sempre, inclusive nos perfis sem opinião. É o
    SEGUNDO-ESCRITOR-01 com outro nome.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    for nome, _args, kwargs in d.recebeu:
        if nome == "set_keyboard_emulation":
            assert kwargs.get("persist") is False, (
                "o arranjo persistiu o teclado. A opinião do perfil vira a "
                "preferência global e a precedência da T14 deixa de existir."
            )
            return
    pytest.fail("nenhum `set_keyboard_emulation` para conferir")


def test_o_perfil_sem_opiniao_deixa_a_flag_global_mandar() -> None:
    """`teclado_emulado: null` = sem opinião, e a flag continua mandando.

    A proteção do `mic.muted`, aplicada ao teclado: perfil SEM opinião nunca
    pode apagar o que a flag diz.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    (Path(config_dir()) / "keyboard_emulation.flag").write_text(
        json.dumps({"enabled": False}), encoding="utf-8"
    )
    sem_opiniao = {k: v for k, v in PERFIL_DA_NAVEGACAO.items()
                   if k != "teclado_emulado"}
    d = _daemon_com(sem_opiniao)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    args = d.chamada("set_keyboard_emulation")
    assert args is not None, f"o teclado não foi tocado: {d.metodos()}"
    assert args[0] is False, (
        "o perfil sem opinião apagou o `false` da flag global — a precedência "
        "da T14 inverteu."
    )


# ---------------------------------------------------------------------------
# 4. AS TECLAS E A SUPRESSÃO
# ---------------------------------------------------------------------------
def test_as_teclas_do_perfil_chegam_ao_device_virtual() -> None:
    """Os `key_bindings` que ela escreveu na aba Navegação sobem no device."""
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    teclado = d._keyboard_device
    assert isinstance(teclado, _TecladoDeMentira)
    assert teclado.bindings, (
        "o device de teclado não recebeu binding nenhum — as teclas do perfil "
        "continuam morrendo no disco."
    )
    assert len(teclado.bindings[-1]) == 2, (
        f"o perfil tem duas teclas e o device recebeu {teclado.bindings[-1]}"
    )


def test_o_arranjo_derruba_a_supressao_senao_a_ponte_sobe_muda() -> None:
    """É a supressão que gateia o dispatch de mouse/teclado no laço do poll.

    Sem derrubá-la, o modo entra, o device sobe e NADA anda — que é a forma
    mais cara do "cliquei em aplicar e nada".
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    d.aplicar_o_arranjo_do_desktop(origin="manual")

    args = d.chamada("set_emulation_suppressed")
    assert args is not None, (
        f"a supressão não foi tocada — a ponte sobe muda. Recebeu: {d.metodos()}"
    )
    assert args[0] is False


def test_o_relatorio_distingue_nao_havia_o_que_aplicar_de_nao_deu() -> None:
    """O arranjo devolve `seção → estado`, e não um `bool` calado.

    Um botão que responde `True`/`False` não diz se a seção estava ausente ou
    se falhou, e a casa já pagou por isso.
    """
    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    relatorio = d.aplicar_o_arranjo_do_desktop(origin="manual")

    assert isinstance(relatorio, dict)
    assert relatorio.get("mouse") == "aplicado"
    assert relatorio.get("teclado_emulado") == "aplicado"
    assert relatorio.get("supressao") == "aplicado"

    sem_perfil = _daemon_com(None)
    sem_perfil.store.set_active_profile(None)
    relatorio_vazio = sem_perfil.aplicar_o_arranjo_do_desktop(origin="manual")
    assert relatorio_vazio.get("keyboard") == "ignorado_sem_perfil", (
        f"sem perfil o relatório tem de DIZER isso: {relatorio_vazio}"
    )


# ---------------------------------------------------------------------------
# 5. O TETO DE TEMPO — medido, não cravado
# ---------------------------------------------------------------------------
def test_o_teto_do_arranjo_cabe_no_que_o_produto_declara() -> None:
    """A sprint manda MEDIR antes de cravar o número, e é o que esta faz.

    O passo abre um `.json` de perfil do disco, resolve `key_bindings` e fala
    com dois devices — é mais do que o `mouse.emulation.restore` de 2,0 s. O
    teto declarado em `ponte.TETOS` é o da família do `profile.switch`, que
    também abre perfil.

    A folga cobrada aqui é de DEZ VEZES: uma régua que exigisse o custo exato
    reprovaria sob carga do CI e viraria vermelho intermitente, que é pior que
    portão nenhum.
    """
    from pacotes import ponte

    _gravar_flag_do_mouse(FLAG_DA_SESSAO)
    d = _daemon_com(PERFIL_DA_NAVEGACAO)

    inicio = time.monotonic()
    d.aplicar_o_arranjo_do_desktop(origin="manual")
    custo = time.monotonic() - inicio

    teto = ponte.teto("desktop.arranjo.apply")
    assert teto >= 2.0, (
        f"o teto do arranjo é {teto}s e o do `mouse.emulation.restore`, que faz "
        "MENOS, é 2,0 s"
    )
    assert custo * 10 < teto, (
        f"o arranjo custou {custo * 1000:.1f} ms contra um teto de {teto}s — a "
        "folga de dez vezes acabou, e o número precisa ser medido de novo."
    )
