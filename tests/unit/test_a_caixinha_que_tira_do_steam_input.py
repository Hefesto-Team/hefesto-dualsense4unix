"""A caixinha que TIRA um jogo do Steam Input — decisão dela de 07/08/2026.

*"no editor do perfil, logo abaixo do jogo escolhido"* — resposta 1 do painel
(`docs/process/2026-08-07-DECISOES-DELA-as-onze-respostas-do-painel.md`).

O buraco que ela fecha, medido e registrado desde 26/07: pôr um jogo na exceção
do Steam Input era **um clique** (o botão "Este jogo não funciona", aba Sistema)
e tirar exigia **abrir um arquivo de texto**. A função que desmarca
(`remove_appid_from_steam_input_allowlist`) tinha nove testes de unidade, uma
linha de comando — e nenhum caminho pela janela.

Por que este arquivo usa **GTK real e o glade real**, e não dublês: a família de
testes do "Aplica a" usa um `_FakeBox` com atributo `.visivel` e nunca pergunta
pelos FILHOS — foi assim que a `CAMPO-QUE-NAO-NASCIA-01` passou despercebida
(*"quando eu clico em jogo da steam não aparece nenhum campo pra digitar"*). A
caixinha nasce escondida pelo mesmo mecanismo, então repetir o dublê aqui seria
repetir o mesmo ponto cego.

E o handler é ligado pelo `install_profiles_tab` DE VERDADE: um teste que
conectasse o sinal à mão passaria com a fiação de produção arrancada, que é
exatamente o defeito desta entrega (função pronta, sem gatilho).

Armadilha da casa (`docs/process/COMO-OLHAR-A-TELA.md`): sob Xvfb não há
gerenciador de janelas e uma `Gtk.Window` fica 1x1 para sempre — daí a
`Gtk.OffscreenWindow`, e o laço drenado mais de uma vez antes de medir.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub
# (`Gtk.Box = object`) este arquivo passaria sem mostrar nada a ninguém.
exigir_gi_real("a caixinha que tira do steam input")

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.app.actions.profiles_actions import (
    ProfilesActionsMixin,
    texto_da_marca_do_steam_input,
)
from hefesto_dualsense4unix.app.constants import MAIN_GLADE

#: O appid do Mullet Mad Jack — o jogo com que ELA mediu a semântica em 06/08.
APPID = "2111190"

#: Um segundo jogo, para provar que a remoção tira só a linha pedida.
OUTRO = "3357650"

CABECALHO = (
    "# hefesto-dualsense4unix — allowlist do Steam Input per-app\n"
    "# (STEAM-INPUT-ALLOWLIST-01)\n"
    "#\n"
    "# Uma linha por AppID; '#' comenta.\n"
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: Janelas vivas até o fim do módulo: uma `OffscreenWindow` coletada no meio do
#: teste leva os widgets junto, e a medição vira sorte.
_janelas_vivas: list[Any] = []


def _assentar(vezes: int = 8) -> None:
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


class _Editor(ProfilesActionsMixin):  # type: ignore[misc]
    """O mixin REAL sobre o glade REAL, montado como a janela monta.

    `install_profiles_tab` é chamado de verdade — é ele que liga a caixinha e o
    campo do jogo. As duas únicas coisas substituídas são as que sairiam da
    máquina: a leitura dos perfis do disco e o toast.
    """

    def __init__(self) -> None:
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(MAIN_GLADE))
        raiz = self.builder.get_object("root_box")
        pai = raiz.get_parent()
        if pai is not None:
            pai.remove(raiz)
        self.janela = Gtk.OffscreenWindow()
        self.janela.add(raiz)
        self.janela.set_size_request(1180, 800)
        self.janela.show_all()
        _janelas_vivas.append(self.janela)

        self.toasts: list[str] = []
        self.avisos_ao_daemon = 0
        self._profiles_cache: list[Any] = []
        self._duplicate_source = None
        self._new_profile = False
        self._regra_tocada = False
        self.install_profiles_tab()
        _assentar()

    # --- o que não pode sair da máquina no teste ---
    def _reload_profiles_store(self, select_name: Any = None, on_done: Any = None) -> None:
        return None

    def _status_toast(self, _contexto: str, msg: str) -> None:
        self.toasts.append(msg)

    def _avisar_o_daemon_da_allowlist(self) -> None:
        self.avisos_ao_daemon += 1

    # --- os gestos dela ---
    def escolher(self, id_do_botao: str) -> None:
        self._aplica_a.set_active_id(id_do_botao)
        _assentar()

    def digitar_o_jogo(self, appid: str) -> None:
        self.builder.get_object("profile_simple_custom_name").set_text(appid)
        _assentar()

    def caixa(self) -> Any:
        return self.builder.get_object("profile_steam_input_box")

    def check(self) -> Any:
        return self.builder.get_object("profile_steam_input_check")

    def clicar_na_caixinha(self) -> None:
        """O gesto: um clique, que no GTK é `toggled` sobre o estado invertido."""
        check = self.check()
        check.set_active(not check.get_active())
        _assentar()


@pytest.fixture
def allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME hermético com a allowlist dela — nunca a configuração de verdade."""
    config = tmp_path / "config"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    arquivo = config / "hefesto-dualsense4unix" / "steam_input_apps.txt"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(f"{CABECALHO}{APPID}\n{OUTRO}\n", encoding="utf-8")
    return arquivo


@pytest.fixture
def sem_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silencia o `call_async` do prefill de appid (best-effort, assíncrono)."""
    monkeypatch.setattr(pa, "call_async", lambda **_kw: None)


def vivos(arquivo: Path) -> list[str]:
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        parse_steam_input_allowlist,
    )

    return parse_steam_input_allowlist(arquivo.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# O lugar — a metade da decisão que é geometria, não comportamento
# ---------------------------------------------------------------------------


def test_a_caixinha_mora_logo_abaixo_do_jogo_escolhido() -> None:
    """"No editor do perfil, logo abaixo do jogo escolhido" — ao pé da letra.

    Lido do glade: os dois blocos são irmãos dentro da página simples do editor,
    e o da caixinha vem IMEDIATAMENTE depois do campo do jogo. Mover a caixinha
    para a aba Sistema, para o rodapé ou para o fim da página reprova aqui.
    """
    raiz = ET.parse(str(MAIN_GLADE)).getroot()
    pagina = [
        obj
        for obj in raiz.iter("object")
        if obj.get("id") == "profile_stack_simples"
    ]
    assert pagina, "a página simples do editor sumiu do glade"

    filhos = [
        neto.get("id")
        for filho in pagina[0].findall("child")
        for neto in filho.findall("object")
    ]
    assert "profile_game_entry_box" in filhos
    assert "profile_steam_input_box" in filhos, (
        "a caixinha do Steam Input não está no editor do perfil"
    )
    assert filhos.index("profile_steam_input_box") == filhos.index(
        "profile_game_entry_box"
    ) + 1, (
        "a decisão dela é 'logo abaixo do jogo escolhido': a caixinha tem de "
        f"ser o bloco seguinte ao campo do jogo, e a ordem lida é {filhos}"
    )


def test_a_janela_nao_avisa_mais_que_nao_da_para_desmarcar(allowlist: Path) -> None:
    """O aviso da aba Sistema caducou: agora dá, e o texto tem de dizer onde.

    Enquanto não havia desmarcar, o tooltip avisava com todas as letras. Deixar
    o aviso depois da entrega seria a mesma doença de antes, pelo avesso: a tela
    negando o que o produto faz.
    """
    raiz = ET.parse(str(MAIN_GLADE)).getroot()
    botao = [o for o in raiz.iter("object") if o.get("id") == "btn_steam_game_broken"]
    assert botao, "o botão 'Este jogo não funciona' sumiu do glade"

    textos = " ".join(
        (prop.text or "")
        for obj in botao[0].iter("object")
        for prop in obj.findall("property")
        if prop.get("name")
        in ("tooltip-text", "AtkObject::accessible-description")
    )
    assert "não existe um botão para desmarcar" not in textos, (
        "o aviso deixou de ser verdade em 07/08 — a caixinha existe"
    )
    assert "Perfis" in textos, (
        "quem lê o botão que MARCA precisa descobrir onde se DESMARCA"
    )


# ---------------------------------------------------------------------------
# A caixinha aparece — e aparece INTEIRA (a lição da CAMPO-QUE-NAO-NASCIA-01)
# ---------------------------------------------------------------------------


def test_a_caixinha_nasce_escondida(allowlist: Path, sem_daemon: None) -> None:
    editor = _Editor()

    assert editor.caixa().get_no_show_all() is True
    assert editor.caixa().get_visible() is False
    assert editor.check().get_visible() is False, (
        "o `show_all()` da janela não desce num box com `no-show-all`"
    )


def test_escolher_jogo_da_steam_revela_a_caixinha_inteira(
    allowlist: Path, sem_daemon: None
) -> None:
    """A asserção é sobre o FILHO, não sobre a caixa: é ali que o defeito mora."""
    editor = _Editor()

    editor.escolher("steam_game")

    assert editor.caixa().get_visible() is True
    assert editor.check().get_visible() is True, (
        "um `show()` seco revelaria a caixa e deixaria a caixinha invisível — "
        "o vão vazio da queixa dela de 05/08"
    )


def test_outros_contextos_nao_mostram_a_caixinha(
    allowlist: Path, sem_daemon: None
) -> None:
    """A marca é por appid: sem jogo da Steam escolhido, ela não faz sentido."""
    editor = _Editor()

    editor.escolher("steam_game")
    editor.escolher("browser")

    assert editor.caixa().get_visible() is False


# ---------------------------------------------------------------------------
# O que a caixinha faz no arquivo dela
# ---------------------------------------------------------------------------


def test_a_caixinha_abre_marcada_para_um_jogo_que_ja_esta_na_lista(
    allowlist: Path, sem_daemon: None
) -> None:
    editor = _Editor()

    editor.escolher("steam_game")
    editor.digitar_o_jogo(APPID)

    assert editor.check().get_active() is True
    assert editor.check().get_sensitive() is True


def test_desmarcar_tira_o_appid_do_arquivo(allowlist: Path, sem_daemon: None) -> None:
    """A MORDIDA desta entrega: com o handler arrancado o appid CONTINUA lá.

    É o defeito de 26/07 na sua forma exata — a função existia, os nove testes
    de unidade dela passavam, e nenhum clique da janela chegava nela.
    """
    editor = _Editor()
    editor.escolher("steam_game")
    editor.digitar_o_jogo(APPID)
    assert vivos(allowlist) == [APPID, OUTRO]

    editor.clicar_na_caixinha()

    assert vivos(allowlist) == [OUTRO], (
        "desmarcar não tirou o jogo da allowlist — o desfazer continua sem "
        "gatilho na janela"
    )
    assert editor.check().get_active() is False
    assert editor.avisos_ao_daemon == 1, (
        "sem o aviso ao daemon a marca só valeria no próximo boot"
    )
    assert any(APPID in t for t in editor.toasts)


def test_marcar_poe_o_appid_no_arquivo(allowlist: Path, sem_daemon: None) -> None:
    novo = "1599660"
    editor = _Editor()
    editor.escolher("steam_game")
    editor.digitar_o_jogo(novo)
    assert editor.check().get_active() is False

    editor.clicar_na_caixinha()

    assert vivos(allowlist) == [APPID, OUTRO, novo]
    assert editor.check().get_active() is True


def test_abrir_um_jogo_marcado_nao_escreve_na_allowlist(
    allowlist: Path, sem_daemon: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O guard do sincronismo, e ele não é ornamento.

    `set_active` emite "toggled" igual a um clique. Sem o guard, apenas ABRIR o
    editor num jogo já marcado dispara o handler de escrita.

    A asserção é sobre a CHAMADA, e não sobre os bytes do arquivo, porque o
    `add` devolve "ja_estava" sem reescrever nada: medir o arquivo deixaria o
    teste verde com o guard arrancado — foi o que aconteceu na primeira versão
    deste caso. O que denuncia o defeito é o produto tentar escrever no arquivo
    dela num gesto que foi só abrir a tela, e o toast do nada que vem junto.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    chamadas: list[str] = []
    for nome in (
        "add_appid_to_steam_input_allowlist",
        "remove_appid_from_steam_input_allowlist",
    ):
        original = getattr(slo, nome)

        def _espiao(*args: Any, _nome: str = nome, _orig: Any = original, **kw: Any) -> Any:
            chamadas.append(_nome)
            return _orig(*args, **kw)

        monkeypatch.setattr(slo, nome, _espiao)

    antes = allowlist.read_bytes()
    editor = _Editor()

    editor.escolher("steam_game")
    editor.digitar_o_jogo(APPID)

    assert chamadas == [], (
        "abrir o editor num jogo já marcado chamou a escrita da allowlist: "
        f"{chamadas} — o guard do sincronismo caiu"
    )
    assert allowlist.read_bytes() == antes
    assert editor.toasts == [], f"toast do nada ao abrir a tela: {editor.toasts}"
    assert editor.avisos_ao_daemon == 0


def test_sem_numero_do_jogo_a_caixinha_fica_apagada(
    allowlist: Path, sem_daemon: None
) -> None:
    """Caixa clicável que não sabe de qual jogo fala é pior que caixa apagada."""
    editor = _Editor()

    editor.escolher("steam_game")
    editor.digitar_o_jogo("")

    assert editor.check().get_sensitive() is False
    assert editor.check().get_active() is False


def test_trocar_o_numero_do_jogo_troca_o_estado_da_caixinha(
    allowlist: Path, sem_daemon: None
) -> None:
    """A caixinha fala do jogo que está no campo AGORA, não do anterior."""
    editor = _Editor()
    editor.escolher("steam_game")
    editor.digitar_o_jogo(APPID)
    assert editor.check().get_active() is True

    editor.digitar_o_jogo("1599660")

    assert editor.check().get_active() is False, (
        "o campo mudou de jogo e a caixinha continuou mostrando a marca do "
        "appid anterior"
    )


def test_desmarcar_preserva_os_comentarios_do_arquivo_dela(
    allowlist: Path, sem_daemon: None
) -> None:
    """O arquivo é dela: sai a linha do appid, e mais nada."""
    editor = _Editor()
    editor.escolher("steam_game")
    editor.digitar_o_jogo(APPID)

    editor.clicar_na_caixinha()

    texto = allowlist.read_text(encoding="utf-8")
    assert "allowlist do Steam Input per-app" in texto
    assert f"\n{APPID}\n" not in texto


# ---------------------------------------------------------------------------
# O texto — a semântica que ELA mediu em 06/08
# ---------------------------------------------------------------------------


def test_o_toast_nao_contradiz_o_que_ela_mediu() -> None:
    """"O Hefesto sai da frente" é meia verdade, e a metade que falta é a dela.

    `CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*, 06/08: com o jogo na lista, o
    Hefesto entrega a ENTRADA e mantém a SAÍDA — os gatilhos dela seguraram e a
    cor dela ficou, com o jogo aberto. Um toast que dissesse "o Hefesto sai da
    frente" contaria à mantenedora o contrário do que ela viu na tela.
    """
    marcou = texto_da_marca_do_steam_input("adicionado", APPID)
    tirou = texto_da_marca_do_steam_input("removido", APPID)

    assert "sai da frente" not in marcou
    assert "dobrado" in marcou, "o defeito que a marca cura é o controle dobrado"
    assert "gatilhos continuam valendo" in marcou
    assert APPID in marcou and APPID in tirou
    assert texto_da_marca_do_steam_input("erro") .startswith("Não consegui")
    assert "não estava" in texto_da_marca_do_steam_input("nao_estava", APPID)
