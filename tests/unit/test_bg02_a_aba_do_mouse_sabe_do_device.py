"""BG-02, lado da janela — a aba para de adivinhar se o mouse virtual subiu.

O rótulo `mouse_uinput_status_label` respondia "o mouse virtual está pronto?"
com uma sonda LOCAL: `import uinput` e `os.access("/dev/uinput")` dentro do
processo da JANELA. Ela erra nos dois sentidos, e os dois são casos reais:

- num Flatpak a janela olha o SANDBOX e grita "sem permissão" sobre um
  `/dev/uinput` que o daemon abre sem dificuldade nenhuma;
- com a permissão em ordem e o device fora do ar — a flag persistida religa no
  boot, `UinputMouseDevice.start()` falha, `_mouse_device` fica `None` com o
  interruptor EM PÉ — a sonda diz *"Pronto para usar como mouse"* enquanto o
  cursor não anda. É a queixa que abriu esta frente.

Quem abre o device é o daemon, e agora ele publica a resposta
(`mouse_emulation.device_ativo` / `bloqueio`). A sonda local continua aqui e
continua útil: é a única que sabe QUAL é o defeito (falta o módulo? falta
permissão no nó?) e é o melhor palpite quando ninguém respondeu.

**Nenhuma frase nova entra na tela.** As quatro do rótulo são as de sempre; o
que muda é qual delas é a verdadeira. O lado do daemon está em
`test_bg02_o_mouse_ganha_razao.py`.

Cada teste MORDE: fixar `_mouse_virtual_no_ar` de volta em `None` (a leitura
arrancada) faz o rótulo voltar a comemorar sobre um cursor parado, e
`test_a_mordida_*` reprova dizendo isso.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi` (mesma disciplina dos
# irmãos desta aba — o stub que outro arquivo planta passaria pelo importorskip).
exigir_gi_real("a aba do mouse sabe do device")

import os
import sys
import types
from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import mouse_actions as ma
from hefesto_dualsense4unix.app.actions.mouse_actions import (
    BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    MouseActionsMixin,
)
from hefesto_dualsense4unix.daemon.lifecycle import CALADA_VPAD_SUSPENSO

PRONTO = "Pronto para usar como mouse"
SEM_PERMISSAO = "está sem permissão"
NAO_ESTA_PRONTO = "ainda não está pronto"
FALTA_COMPONENTE = "Falta um componente"


class _FakeLabel:
    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _Aba(MouseActionsMixin):
    def __init__(self) -> None:
        self.rotulo = _FakeLabel()

    def _get(self, widget_id: str) -> Any:
        return self.rotulo if widget_id == "mouse_uinput_status_label" else None


def _sonda_local(
    monkeypatch: pytest.MonkeyPatch,
    *,
    com_uinput: bool = True,
    existe: bool = True,
    gravavel: bool = True,
) -> None:
    """Finge a máquina que a JANELA enxerga — módulo, nó e permissão.

    Dublê que sabe RECUSAR: `com_uinput=False` faz o `import uinput` levantar
    ImportError de verdade (é o que `sys.modules[nome] = None` provoca), e não
    um objeto que finge não existir.
    """
    monkeypatch.setitem(
        sys.modules, "uinput", types.ModuleType("uinput") if com_uinput else None
    )
    exists_real, access_real = os.path.exists, os.access
    monkeypatch.setattr(
        os.path,
        "exists",
        lambda p: existe if p == ma.UINPUT_DEV else exists_real(p),
    )
    monkeypatch.setattr(
        os,
        "access",
        lambda p, m: gravavel if p == ma.UINPUT_DEV else access_real(p, m),
    )


def test_a_sonda_dublada_sabe_recusar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua da régua: sem isto, todo teste abaixo mediria a máquina do CI."""
    _sonda_local(monkeypatch, com_uinput=False, existe=False, gravavel=False)
    with pytest.raises(ImportError):
        import uinput  # noqa: F401
    assert os.path.exists(ma.UINPUT_DEV) is False
    assert os.access(ma.UINPUT_DEV, os.W_OK) is False
    # E não pode ter cegado o resto do sistema de arquivos junto.
    assert os.path.exists(__file__) is True


# ---------------------------------------------------------------------------
# A leitura do estado vivo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bloco", "esperado"),
    [
        ({"device_ativo": True, "bloqueio": None}, True),
        ({"device_ativo": True, "bloqueio": "modo_jogo"}, True),
        ({"device_ativo": False, "bloqueio": "sem_device"}, False),
        # Desligada NÃO é defeito: ela baixou o interruptor. Mandá-la em
        # "Aplicar correções" por isso é alarme falso.
        ({"device_ativo": False, "bloqueio": "desligada"}, None),
        ({"device_ativo": False, "bloqueio": CALADA_VPAD_SUSPENSO}, None),
        # Daemon MAIS VELHO que esta janela: sem as chaves novas, "não sei".
        ({"enabled": True, "speed": 6, "scroll_speed": 1}, None),
        ({}, None),
    ],
)
def test_o_tri_estado_do_mouse_virtual(bloco: dict[str, Any], esperado: Any) -> None:
    aba = _Aba()
    aba._anotar_mouse_virtual({"mouse_emulation": bloco})
    assert aba._mouse_virtual_no_ar is esperado


def test_sem_resposta_a_aba_volta_a_nao_saber() -> None:
    """Guardar o último valor bom seria afirmar sobre quem não respondeu."""
    aba = _Aba()
    aba._anotar_mouse_virtual({"mouse_emulation": {"device_ativo": True}})
    assert aba._mouse_virtual_no_ar is True
    aba._anotar_mouse_virtual(None)
    assert aba._mouse_virtual_no_ar is None


def test_o_tri_estado_e_por_instancia() -> None:
    """Duas janelas no mesmo processo (a suíte monta várias) não se misturam."""
    assert MouseActionsMixin._mouse_virtual_no_ar is None
    aba = _Aba()
    aba._anotar_mouse_virtual({"mouse_emulation": {"device_ativo": True}})
    assert MouseActionsMixin._mouse_virtual_no_ar is None


# ---------------------------------------------------------------------------
# A MORDIDA — o rótulo
# ---------------------------------------------------------------------------


def test_a_mordida_o_device_fora_do_ar_desmente_a_sonda_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permissão em ordem, interruptor em pé, cursor parado: o rótulo avisa.

    Arrancar a leitura (`_mouse_virtual_no_ar` de volta em `None`) faz o mesmo
    rótulo, na mesma máquina, comemorar "Pronto para usar como mouse" — que é
    o produto afirmando o contrário do que ela está vendo na tela.
    """
    _sonda_local(monkeypatch)  # a janela não vê defeito NENHUM
    aba = _Aba()

    aba._anotar_mouse_virtual(
        {"mouse_emulation": {"device_ativo": False, "bloqueio": "sem_device"}}
    )

    assert NAO_ESTA_PRONTO in aba.rotulo.markup, (
        f"o rótulo diz {aba.rotulo.markup!r} com o device fora do ar — a aba "
        "voltou a adivinhar pela sonda local em vez de ouvir quem abre o device"
    )
    assert PRONTO not in aba.rotulo.markup


def test_no_flatpak_o_daemon_desmente_o_alarme_da_sonda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O erro no outro sentido: sandbox sem `/dev/uinput`, device VIVO.

    A janela num Flatpak enxerga o sandbox. Se ela mandar em "Aplicar
    correções" um sistema que já está funcionando, o produto está inventando um
    defeito — e o custo é ela mexer no que estava certo.
    """
    _sonda_local(monkeypatch, existe=True, gravavel=False)
    aba = _Aba()

    aba._anotar_mouse_virtual({"mouse_emulation": {"device_ativo": True}})

    assert PRONTO in aba.rotulo.markup
    assert SEM_PERMISSAO not in aba.rotulo.markup


def test_desligada_nao_manda_ninguem_aplicar_correcoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O alarme falso que o tri-estado existe para não dar.

    Sem device porque ela DESLIGOU o mouse não é defeito. Se "sem device"
    bastasse, todo interruptor baixado viraria um pedido de conserto.
    """
    _sonda_local(monkeypatch)
    aba = _Aba()

    aba._anotar_mouse_virtual(
        {"mouse_emulation": {"device_ativo": False, "bloqueio": "desligada"}}
    )
    # `install_mouse_tab` é quem pinta na abertura; aqui a pintura é explícita
    # porque "desligada" não MUDA o tri-estado (segue `None`) e o guard de
    # repintura — que existe para não redesenhar a aba a 10 Hz — não dispara.
    aba._refresh_mouse_view()

    assert PRONTO in aba.rotulo.markup
    assert "Aplicar correções" not in aba.rotulo.markup


@pytest.mark.parametrize(
    ("com_uinput", "existe", "gravavel", "trecho"),
    [
        (True, True, True, PRONTO),
        (True, True, False, SEM_PERMISSAO),
        (True, False, False, NAO_ESTA_PRONTO),
        (False, True, True, FALTA_COMPONENTE),
    ],
)
def test_sem_resposta_do_daemon_a_sonda_local_manda_como_sempre(
    monkeypatch: pytest.MonkeyPatch,
    com_uinput: bool,
    existe: bool,
    gravavel: bool,
    trecho: str,
) -> None:
    """Os quatro desfechos históricos do rótulo, intactos.

    O daemon offline não pode PIORAR a aba: sem resposta, o melhor palpite da
    janela continua sendo o único palpite que ela tem.
    """
    _sonda_local(monkeypatch, com_uinput=com_uinput, existe=existe, gravavel=gravavel)
    aba = _Aba()
    assert aba._mouse_virtual_no_ar is None
    aba._refresh_mouse_view()
    assert trecho in aba.rotulo.markup


def test_o_modulo_ausente_vence_o_device_fora_do_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Falta um componente" manda rodar o install; "não está pronto" não.

    Quando a sonda sabe MAIS que o daemon (o daemon só sabe que não subiu; a
    sonda sabe que falta o módulo `uinput` neste sistema), quem tem o texto
    mais acionável ganha.
    """
    _sonda_local(monkeypatch, com_uinput=False)
    aba = _Aba()
    aba._anotar_mouse_virtual(
        {"mouse_emulation": {"device_ativo": False, "bloqueio": "sem_device"}}
    )
    assert FALTA_COMPONENTE in aba.rotulo.markup


# ---------------------------------------------------------------------------
# O dado chega pelo TIQUE, não por um segundo poller
# ---------------------------------------------------------------------------


class _AbaViva(_Aba):
    """A aba com o mínimo que `_refresh_mouse_from_daemon_async` toca."""

    def __init__(self) -> None:
        super().__init__()
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        self.draft = DraftConfig.default()


def test_a_mordida_o_estado_vivo_chega_a_aba(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fiação: sem a chamada em `_refresh_mouse_from_daemon_async`, o campo
    viaja no socket e a aba continua sem ele — o dado publicado que ninguém lê,
    que é o mesmo defeito, uma casa adiante.

    E ela mora ANTES dos `return` daquele callback de propósito: sair por
    "edição pendente" ou "seção do perfil" com o dado na mão deixaria o rótulo
    mentindo exatamente quando ela está mexendo na aba.
    """
    from hefesto_dualsense4unix.app import ipc_bridge

    _sonda_local(monkeypatch)
    estado = {
        "mouse_emulation": {
            "enabled": True,
            "speed": 6,
            "scroll_speed": 1,
            "device_ativo": False,
            "despachando": False,
            "bloqueio": "sem_device",
        }
    }
    monkeypatch.setattr(
        ipc_bridge,
        "call_async",
        lambda method, params=None, on_success=None, on_failure=None, **_kw: (
            on_success(estado)
        ),
    )

    aba = _AbaViva()
    # A edição pendente é o cenário cruel: os `return` do callback estão logo
    # abaixo, e é onde a leitura se perderia se ela fosse posta no lugar errado.
    aba.draft = aba.draft.model_copy(
        update={"mouse": aba.draft.mouse.model_copy(update={"dirty": True})}
    )
    aba._refresh_mouse_from_daemon_async()

    assert aba._mouse_virtual_no_ar is False, (
        "o `state_full` trouxe o motivo e a aba não o leu — a fiação do tique "
        "sumiu, ou está depois dos `return` do callback"
    )
    assert NAO_ESTA_PRONTO in aba.rotulo.markup


# ---------------------------------------------------------------------------
# O vocabulário é um só, dos dois lados do socket
# ---------------------------------------------------------------------------


def test_todo_motivo_que_o_daemon_emite_tem_traducao() -> None:
    """A régua contra a divergência silenciosa entre daemon e janela.

    `_bloqueio_da_emulacao_de_desktop` emite estes quatro códigos, e são os
    quatro que a tabela traduz. Um código novo do daemon sem linha aqui sai na
    tela como texto cru (`frase_da_recusa_do_mouse` é honesta nesse caso) — o
    que este teste impede é que ele sirva DUAS vezes, com dois vocabulários.
    """
    do_daemon = {"desligada", "sem_device", "modo_jogo", CALADA_VPAD_SUSPENSO}
    assert do_daemon == set(BLOQUEIO_DO_MOUSE_EM_PORTUGUES), (
        "o vocabulário do daemon e o da janela divergiram: "
        f"{do_daemon ^ set(BLOQUEIO_DO_MOUSE_EM_PORTUGUES)}"
    )


# "Conhece-te a ti mesmo." — Sócrates
