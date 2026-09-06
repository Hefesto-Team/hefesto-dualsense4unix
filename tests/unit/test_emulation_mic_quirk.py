"""BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01 — ligar o mic do DualSense SEM o quirk de
áudio USB ativo na SESSÃO ATUAL pode reabrir o storm -71 (o controle cai no meio
do jogo). A GUI avisa por toast ANTES de ligar (sem bloquear) e expõe o helper
estático _usb_quirk_active(), espelhando o check_usb_quirk do doctor.sh (só
/proc/cmdline e /sys/module/usbcore/parameters/quirks valem para a sessão).

Stubs de gi como em test_emulation_actions_modo_jogo.py (armadilha A-12).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01 (TESTE-HONESTO-01/E1, lote A): a guarda vem ANTES de
# qualquer plantio de `gi`. Sem PyGObject REAL este módulo rodava verde contra
# widgets que são `object` — e nunca entrava no job `gtk-real`, que seleciona
# por `grep exigir_gi_real|skip_sem_gi_real`. Agora ele pula honestamente.
exigir_gi_real("emulação: o quirk do microfone")

import sys
import types

import pytest


def _rotulo_do_botao_de_consertar() -> str:
    """O rótulo VIVO do botão da aba Sistema — na TELA QUE ELA USA.

    **A FONTE MUDOU EM 06/09/2026** (`GTK-3`, primeira volta). Até aqui esta
    função lia o `<property name="label">` do `gui/main.glade` — a janela GTK,
    que sai inteira (`D-0609-GTK-LEVA-INTEIRA`). O dono é a página publicada:
    `interface/paginas/09-sistema.html`, o botão de `data-gesto`
    ``refazer-consertos``. É o botão que ela tem na frente quando lê a
    mensagem.

    A leitura continua sendo LEITURA, e não uma constante digitada aqui: uma
    palavra melhor no botão não pode fazer esta régua reprovar a melhora — foi
    esse o defeito corrigido em 26/08/2026.
    """
    import html as _html
    import re
    from pathlib import Path

    pagina = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "hefesto_dualsense4unix"
        / "interface"  # noqa-acento (nome de pasta)
        / "paginas"  # noqa-acento (nome de pasta)
        / "09-sistema.html"
    ).read_text(encoding="utf-8")
    achado = re.search(
        r'data-gesto="refazer-consertos"[^>]*>([^<]+)</button>', pagina
    )
    assert achado, (
        "o botão `refazer-consertos` sumiu de `interface/paginas/09-sistema."
        "html` — a régua ficou cega sobre a tela que ela usa"
    )
    return _html.unescape(achado.group(1)).strip()


#: O RÓTULO DA JANELA QUE ESTÁ SAINDO, e o defeito VIVO que ele guarda.
#:
#: `app/actions/emulation_actions.py:1406` digita *"Consertar problemas
#: conhecidos"* — o rótulo do `gui/main.glade`. Na aba Sistema que ela usa esse
#: botão se chama **"Refazer os consertos automáticos"**
#: (`interface/paginas/09-sistema.html`), então a mensagem do microfone manda
#: clicar num botão que não está na tela.
#:
#: É o defeito que a `GTK-2` mediu no `storm_doctor` (§3.2 do relatório dela),
#: com um terceiro escritor que nenhuma régua via: a costura de 06/09 curou o
#: `storm_doctor` (a página virou a fonte nº 1 de `rotulo_do_botao`) e **esta
#: linha ficou para trás**, porque ela não passa por `rotulo_do_botao`.
#:
#: A cura é de UMA linha e mora em `app/actions/`, que é `nao_toca` da `GTK-3`.
#: Enquanto ela não vier, o caso abaixo é `xfail(strict=True)`: no dia em que
#: alguém trocar a frase, ele passa, o `strict` reprova o xpass e obriga a
#: apagar esta marca. Instrumento que se limpa sozinho.
_A_FRASE_AINDA_NOMEIA_O_BOTAO_DA_JANELA = (
    "Consertar problemas conhecidos"
    in (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "src"
        / "hefesto_dualsense4unix"
        / "app"
        / "actions"
        / "emulation_actions.py"
    ).read_text(encoding="utf-8")
)

def _install_gi_stubs() -> None:
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # o merge abaixo mutaria o gi REAL (sobrescreve GLib.idle_add e
    # require_version) e fazia testes de GUI pularem como "ambiente sem GTK".
    # Um stub instalado por outro módulo de teste (__spec__ None) segue
    # sendo reaproveitado para merge de atributos.
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )
    for cls_name in ("Builder", "Window", "Button", "Label", "Box"):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import emulation_actions

Mixin = emulation_actions.EmulationActionsMixin


# --- _usb_quirk_active() ---------------------------------------------------


def test_usb_quirk_active_true_no_cmdline(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cmdline = tmp_path / "cmdline"
    cmdline.write_text(
        "BOOT_IMAGE=/vmlinuz usbcore.quirks=054c:0ce6:gn,054c:0df2:gn ro\n"
    )
    quirks = tmp_path / "quirks"
    quirks.write_text("")
    monkeypatch.setattr(Mixin, "_USB_QUIRK_PATHS", (str(cmdline), str(quirks)))
    assert Mixin._usb_quirk_active() is True


def test_usb_quirk_active_true_em_runtime_sysfs(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cmdline = tmp_path / "cmdline"
    cmdline.write_text("BOOT_IMAGE=/vmlinuz ro quiet\n")
    quirks = tmp_path / "quirks"
    quirks.write_text("054c:0ce6:gn\n")
    monkeypatch.setattr(Mixin, "_USB_QUIRK_PATHS", (str(cmdline), str(quirks)))
    assert Mixin._usb_quirk_active() is True


def test_usb_quirk_active_false_quando_ausente(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cmdline = tmp_path / "cmdline"
    cmdline.write_text("BOOT_IMAGE=/vmlinuz ro quiet splash\n")
    quirks = tmp_path / "quirks"
    quirks.write_text("0781:5567:bk\n")  # outro quirk qualquer
    monkeypatch.setattr(Mixin, "_USB_QUIRK_PATHS", (str(cmdline), str(quirks)))
    assert Mixin._usb_quirk_active() is False


def test_usb_quirk_active_false_quando_paths_inexistentes(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # OSError ao ler arquivos ausentes é engolido — resultado é False, sem raise.
    monkeypatch.setattr(
        Mixin, "_USB_QUIRK_PATHS", (str(tmp_path / "a"), str(tmp_path / "b"))
    )
    assert Mixin._usb_quirk_active() is False


# --- on_emulation_mic_on avisa (mas não bloqueia) --------------------------


def _wire(obj, monkeypatch):
    toasts: list[str] = []
    ran: list[tuple[str, str]] = []
    monkeypatch.setattr(obj, "_toast_emulation", lambda m: toasts.append(m))
    monkeypatch.setattr(obj, "_run_mic", lambda flag, msg: ran.append((flag, msg)))
    return toasts, ran


@pytest.mark.xfail(
    _A_FRASE_AINDA_NOMEIA_O_BOTAO_DA_JANELA,
    reason=(
        "DEFEITO VIVO, medido em 06/09/2026 (GTK-3, primeira volta): "
        "`app/actions/emulation_actions.py:1406` manda clicar em “Consertar "
        "problemas conhecidos”, que é o rótulo do `gui/main.glade`. Na aba "
        "Sistema que ela usa o botão se chama “Refazer os consertos "
        "automáticos”. A cura é uma linha, e `app/actions/` é `nao_toca` da "
        "GTK-3 — o diff está no relatório. Curou? Apague esta marca."
    ),
    strict=True,
)
def test_mic_on_avisa_quando_quirk_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = Mixin()
    _toasts, ran = _wire(obj, monkeypatch)
    monkeypatch.setattr(Mixin, "_usb_quirk_active", staticmethod(lambda: False))
    obj.on_emulation_mic_on(None)
    # PROSSEGUE ligando o mic (não bloqueia)...
    assert len(ran) == 1
    flag, msg = ran[0]
    assert flag == "--enable-mic"
    # ...e o aviso persiste na mensagem FINAL (não num toast que é sobrescrito).
    # EMU-04: sem jargão ("storm -71"/nome de script) — o leigo é mandado para
    # um BOTÃO da aba Sistema, e o teste prende o VÍNCULO, não a palavra.
    #
    # CORRIGIDO em 26/08/2026: esta linha prendia o rótulo "Aplicar correções"
    # letra por letra. A leva de 26/08 renomeou o botão para "Consertar
    # problemas conhecidos" no `main.glade` — o renomeio estava CERTO (o rótulo
    # velho não dizia o que o botão faz), e o teste ficou vermelho acusando a
    # melhora. É o mesmo defeito de forma que esta casa nomeia: a régua confunde
    # a PALAVRA com o ATO. Agora ela lê o rótulo do glade, que é o dono único.
    assert "travar" in msg
    assert _rotulo_do_botao_de_consertar() in msg, (
        f"a mensagem manda a pessoa para um botão que não existe na tela: {msg!r}"
    )
    assert "storm" not in msg


def test_mic_on_nao_avisa_quando_quirk_ativo(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = Mixin()
    _toasts, ran = _wire(obj, monkeypatch)
    monkeypatch.setattr(Mixin, "_usb_quirk_active", staticmethod(lambda: True))
    obj.on_emulation_mic_on(None)
    assert ran == [("--enable-mic", "Mic do DualSense ligado")]  # sem aviso de storm


def test_mic_off_nunca_avisa_de_quirk(monkeypatch: pytest.MonkeyPatch) -> None:
    """on_emulation_mic_off não foi tocado: desligar o mic nunca reabre o storm."""
    obj = Mixin()
    toasts, ran = _wire(obj, monkeypatch)
    # mesmo sem quirk, desligar não dispara aviso.
    monkeypatch.setattr(Mixin, "_usb_quirk_active", staticmethod(lambda: False))
    obj.on_emulation_mic_off(None)
    assert toasts == []
    assert ran == [("--disable-source", "Mic do DualSense desligado")]
