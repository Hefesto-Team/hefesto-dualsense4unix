"""O nome de cada adaptador chega à tela, e o prefixo que segura o Pro não.

O DEFEITO, medido em 22/08/2026: `integrations/apelido_do_dongle.py` nasceu
naquele dia — lê e escreve `org.bluez.Adapter1.Alias` por BD Address, costura o
prefixo `Nintendo` em quem hospeda um Pro Controller, respeita o teto de 247
bytes medido — e tinha **zero consumidores em `app/`**. Ela tem três
adaptadores `2357:0604` idênticos no barramento e pediu para diferenciá-los; a
aba mostrava `vid:pid` três vezes.

Decisão dela: *"você escreve, o produto protege o prefixo"*.

O QUE ESTE PORTÃO COBRA:

1. **a coluna existe quando o BlueZ respondeu, e só então.** Sem `busctl`, no
   Flatpak ou com o serviço parado, uma coluna vazia em toda linha ocuparia a
   largura que esta janela não tem — é a mesma régua que manteve "Firmware"
   fora desta tabela;
2. **o que a tela mostra é o nome DELA.** O alias guardado é
   `"Nintendo Extra"`; o campo diz `"Extra"`;
3. **o nome vai ao dono do LUGAR, cru** — MUDOU EM 23/09/2026
   (TRANSPLANTE-DA-SECAO-01, item 1). Até ali salvar `"Extra"` escrevia
   `"Nintendo Extra"` no `Alias` do BlueZ por endereço; eram três escritores
   do mesmo nome (esta janela, a aba 08 e o `bt_active_mode.sh`), e o último
   ganhava. Agora o nome mora no `maquina.json` pelo ENDEREÇO do adaptador
   (`entrada_a_entrada.dar_nome_ao_adaptador`, desde 26/09/2026 — antes era o
   nome da entrada, e os dois se confundiam), e a costura do prefixo que
   segura o Pro é do único escritor do `Alias`, o `bt_active_mode.sh`;
4. **nome igual não escreve.** Sem essa comparação, cada troca de aba
   regravaria o nome dos três adaptadores;
5. **a junção da tabela é por `hciN` e nunca é guardada**; a junção do medidor
   é por ENDEREÇO dos dois lados;
6. **a captura não fala com o BlueZ.** O alias é texto que ela escreveu.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("o nome do adaptador na seção A mesa")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations.apelido_do_dongle import Dongle
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa
from hefesto_dualsense4unix.integrations.radio_da_mesa import Ocupacao

_SALA = "AA:BB:CC:00:00:01"
_EXTRA = "AA:BB:CC:00:00:02"


class _Hospedeiro:
    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


_PCI = "0000:00:14.0"


def _mesa() -> Mesa:
    """Dois adaptadores: um em porta direta, um atrás de hub."""
    return Mesa(
        adaptadores=(
            Adaptador(
                interface="hci0",
                no="/bancada/usb1/1-1",
                vid="2357",
                pid="0604",
                busnum=1,
                devpath="1",
                painel="back",
                controlador_pci=_PCI,
            ),
            Adaptador(
                interface="hci1",
                no="/bancada/usb1/1-2/1-2.1",
                vid="2357",
                pid="0604",
                busnum=1,
                devpath="2.1",
                atras_de_hub=True,
                controlador_pci=_PCI,
            ),
        )
    )


class _DonoDoNome:
    """O `dar_nome_ao_adaptador` de mentira: registra o que o produto GRAVARIA,
    e responde como o dono — com um `NomeDado` e nunca mais frouxo que ele (a
    assinatura é a mesma: `endereco` e `nome`, posicionais)."""

    def __init__(self, gravou: bool = True) -> None:
        self.gravacoes: list[tuple[str, str]] = []
        self._gravou = gravou

    def __call__(self, endereco: str, nome: str) -> Any:
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import NomeDado

        self.gravacoes.append((endereco, nome))
        return NomeDado(endereco, nome, self._gravou, "")


@pytest.fixture
def dono_do_nome(monkeypatch: pytest.MonkeyPatch) -> _DonoDoNome:
    from hefesto_dualsense4unix.integrations import entrada_a_entrada

    dono = _DonoDoNome()
    monkeypatch.setattr(entrada_a_entrada, "dar_nome_ao_adaptador", dono)
    return dono


def _dongles() -> tuple[Dongle, ...]:
    """O segundo hospeda Nintendo: é ele que carrega a costura no alias."""
    return (
        Dongle(
            endereco=_SALA,
            alias="Sala",
            hospeda_nintendo=False,
            ligado=True,
            objeto="/org/bluez/hci0",
        ),
        Dongle(
            endereco=_EXTRA,
            alias="Nintendo Extra",
            hospeda_nintendo=True,
            ligado=True,
            objeto="/org/bluez/hci1",
        ),
    )


def _montar(
    host: Any, *, dongles: tuple[Dongle, ...] | None = None
) -> tuple[Gtk.Box, Any]:
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    painel = secao_mesa._PainelDaMesa(host)
    painel._ler = lambda: _mesa()  # type: ignore[method-assign]
    painel._ler_o_censo = lambda: Censo()  # type: ignore[method-assign]
    painel._pedir_o_estado = lambda: None  # type: ignore[method-assign]
    host._dongles_leitor = (
        (lambda: _dongles()) if dongles is None else (lambda: dongles)
    )
    painel.montar(caixa)
    return caixa, painel


def _campos(raiz: Any) -> list[Any]:
    """Os campos de nome NA ORDEM DAS LINHAS da tabela."""
    grade = _grade(raiz)
    if grade is None:
        return []
    achados: list[Any] = []
    linha = 1
    while True:
        celula = grade.get_child_at(0, linha)
        if celula is None:
            return achados
        if isinstance(celula, Gtk.Entry):
            achados.append(celula)
        linha += 1


def _grade(raiz: Any) -> Any:
    """A primeira `Gtk.Grid` da seção — a tabela de adaptadores."""
    pilha = [raiz]
    while pilha:
        widget = pilha.pop(0)
        if isinstance(widget, Gtk.Grid):
            return widget
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            pilha.extend(obter())
    return None


def _textos(raiz: Any) -> list[str]:
    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados


def test_a_coluna_do_nome_nasce_com_o_nome_dela() -> None:
    """Dois campos, e o segundo mostra "Extra" — sem o prefixo."""
    caixa, _ = _montar(_Hospedeiro())
    campos = _campos(caixa)

    assert len(campos) == 2, (
        f"a tabela de adaptadores tem {len(campos)} campos de nome e devia ter "
        "2 — um por adaptador que o BlueZ conhece"
    )
    assert [c.get_text() for c in campos] == ["Sala", "Extra"], (
        "o que a tela mostra não é o nome DELA. O prefixo que segura o Pro "
        f"fora do sniff frágil é costura do produto: {[c.get_text() for c in campos]}"
    )


def test_sem_resposta_do_bluez_a_coluna_nao_aparece() -> None:
    """Coluna que só sabe dizer "não sei" ocupa a largura que a janela não tem."""
    caixa, _ = _montar(_Hospedeiro(), dongles=())

    assert not _campos(caixa), (
        "a coluna do nome apareceu sem o BlueZ ter respondido por adaptador "
        "nenhum — no Flatpak e com o serviço parado é sempre este o caso"
    )
    assert secao_mesa._COLUNA_NOME not in _textos(caixa), (
        "o cabeçalho da coluna ficou na tabela sem coluna embaixo"
    )


def test_a_nota_do_prefixo_so_aparece_onde_ha_nintendo() -> None:
    """Explicação sobre coisa nenhuma é ruído; explicação ausente é armadilha."""
    com, _ = _montar(_Hospedeiro())
    assert secao_mesa._NOTA_DO_PREFIXO in _textos(com)

    sem_pro = tuple(
        Dongle(
            endereco=d.endereco,
            alias=d.nome,
            hospeda_nintendo=False,
            ligado=True,
            objeto=d.objeto,
        )
        for d in _dongles()
    )
    outra, _ = _montar(_Hospedeiro(), dongles=sem_pro)
    assert secao_mesa._NOTA_DO_PREFIXO not in _textos(outra), (
        "a tela explicou o prefixo Nintendo numa mesa que não tem Pro nenhum"
    )


def test_a_secao_diz_que_o_nome_nao_espera_o_aplicar() -> None:
    """Duas semânticas na mesma seção, e a segunda não pode ficar calada."""
    caixa, _ = _montar(_Hospedeiro())
    assert secao_mesa._NOME_VALE_JA in _textos(caixa)


def test_salvar_um_nome_grava_no_lugar_e_sem_a_costura(dono_do_nome: _DonoDoNome) -> None:
    """"Casa" num adaptador com Pro vai ao dono do nome como "Casa"."""
    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[1]
    campo.set_text("Casa")
    painel._ao_salvar_o_nome(campo, _EXTRA)

    assert dono_do_nome.gravacoes == [(_EXTRA, "Casa")], (
        f"o nome não foi ao dono, cru e pelo endereço: {dono_do_nome.gravacoes}")


def test_salvar_num_adaptador_sem_nintendo_grava_o_nome_dela(
    dono_do_nome: _DonoDoNome,
) -> None:
    """O produto não põe palavra no nome dela — em adaptador nenhum."""
    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[0]
    campo.set_text("Sofá")
    painel._ao_salvar_o_nome(campo, _SALA)

    assert dono_do_nome.gravacoes == [(_SALA, "Sofá")]


def test_nome_que_nao_mudou_nao_grava(dono_do_nome: _DonoDoNome) -> None:
    """Sair do campo sem ter mexido não grava nada."""
    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[1]
    painel._ao_sair_do_nome(campo, None, _EXTRA)

    assert not dono_do_nome.gravacoes, (
        "sair do campo sem mexer gravou o nome. O texto do campo é o nome "
        "LIMPO; comparar contra o alias faria toda saída de campo gravar."
    )


def test_o_espelho_de_memoria_impede_a_segunda_escrita_igual(
    dono_do_nome: _DonoDoNome,
) -> None:
    """Depois de gravar, o produto sabe o nome novo sem reler o BlueZ."""
    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[1]
    campo.set_text("Casa")
    painel._ao_salvar_o_nome(campo, _EXTRA)
    painel._ao_salvar_o_nome(campo, _EXTRA)

    assert len(dono_do_nome.gravacoes) == 1, (
        f"o mesmo nome foi gravado {len(dono_do_nome.gravacoes)} vezes"
    )


def test_o_adaptador_sem_lugar_tambem_ganha_nome(
    dono_do_nome: _DonoDoNome,
) -> None:
    """O adaptador da placa-mãe não pendura em entrada, e ganha nome do mesmo jeito."""
    caixa, painel = _montar(_Hospedeiro())
    painel._mesa = Mesa(adaptadores=tuple(
        Adaptador(interface=a.interface, no=a.no, vid=a.vid, pid=a.pid,
                  busnum=a.busnum, devpath=a.devpath) for a in _mesa().adaptadores))
    campo = _campos(caixa)[0]
    campo.set_text("Sofá")
    painel._ao_salvar_o_nome(campo, _SALA)

    assert dono_do_nome.gravacoes == [(_SALA, "Sofá")]


def test_a_tabela_junta_por_hci_e_o_hci_nao_e_guardado() -> None:
    """A linha do `hci1` recebe o campo do `/org/bluez/hci1`, e nada mais."""
    invertidos = tuple(reversed(_dongles()))
    caixa, _ = _montar(_Hospedeiro(), dongles=invertidos)

    assert [c.get_text() for c in _campos(caixa)] == ["Sala", "Extra"], (
        "a ordem em que o BlueZ respondeu mudou de quem é cada nome — a "
        "junção não está usando o `hciN` do objeto"
    )

    por_interface = secao_mesa._dongle_por_interface(invertidos)
    assert por_interface["hci1"].endereco == _EXTRA


def test_o_medidor_passa_a_se_chamar_pelo_nome_dela() -> None:
    """`Rádio em uso · Sala` em vez de um endereço hexa."""
    apelidos = secao_mesa._apelido_por_endereco(_dongles())

    assert (
        secao_mesa._rotulo_do_medidor(_SALA.lower(), apelidos) == "Rádio em uso · Sala"
    ), "o medidor continua nomeado pelo endereço mesmo com nome dado"
    assert (
        secao_mesa._rotulo_do_medidor("AA:BB:CC:00:00:09", apelidos)
        == "Rádio em uso · AA:BB:CC:00:00:09"
    ), "o medidor inventou um nome para um endereço que ninguém batizou"


def test_a_barra_desenhada_carrega_o_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua de ponta a ponta: o nome tem de chegar ao rótulo DESENHADO."""
    _, painel = _montar(_Hospedeiro())
    painel._ocupacoes = lambda: {_SALA.lower(): Ocupacao()}  # type: ignore[method-assign]
    painel._desenhar_medidores()

    assert "Rádio em uso · Sala" in _textos(painel._caixa_medidores), (
        "a barra desenhada não usa o nome, mesmo com a função de rótulo "
        f"sabendo dele. Textos: {_textos(painel._caixa_medidores)}"
    )


def test_a_barra_em_zero_tambem_se_chama_pelo_nome() -> None:
    """Com tudo no cabo, três adaptadores iguais davam três rótulos iguais."""
    _, painel = _montar(_Hospedeiro())
    painel._ocupacoes = lambda: {}  # type: ignore[method-assign]
    painel._desenhar_medidores()

    textos = _textos(painel._caixa_medidores)
    assert "Rádio em uso · Sala" in textos and "Rádio em uso · Extra" in textos, (
        "as barras em zero continuam nomeadas pela identidade física. Com três "
        f"adaptadores iguais, os três rótulos ficam idênticos. Textos: {textos}"
    )


def test_a_barra_em_zero_sem_nome_volta_para_a_identidade_fisica() -> None:
    """Sem BlueZ não se inventa nome — o rótulo é o `vid:pid`, como antes."""
    _, painel = _montar(_Hospedeiro(), dongles=())
    painel._ocupacoes = lambda: {}  # type: ignore[method-assign]
    painel._desenhar_medidores()

    assert "Rádio em uso · 2357:0604" in _textos(painel._caixa_medidores)


def test_durante_a_captura_a_secao_nao_le_o_bluez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O alias é texto que ELA escreveu, e a foto vai para `docs/` sem revisão."""
    chamadas: list[int] = []
    monkeypatch.setattr(
        secao_mesa, "ler_os_dongles", lambda *a, **k: (chamadas.append(1), ())[1]
    )

    host = _Hospedeiro()
    host._mesa_leitor = _mesa  # type: ignore[attr-defined]
    painel = secao_mesa._PainelDaMesa(host)
    painel._mesa = _mesa()
    painel._pedir_os_dongles()

    assert not chamadas


def test_mesa_sem_adaptador_nao_gasta_subprocesso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem adaptador não há nome a dar — e é o caso mais comum lá fora."""
    chamadas: list[int] = []
    monkeypatch.setattr(
        secao_mesa, "ler_os_dongles", lambda *a, **k: (chamadas.append(1), ())[1]
    )

    painel = secao_mesa._PainelDaMesa(_Hospedeiro())
    painel._mesa = Mesa()
    painel._pedir_os_dongles()

    assert not chamadas


def test_com_adaptador_e_sem_duble_a_secao_pergunta_ao_bluez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contraparte das duas guardas acima, e sem ela as duas são satisfeitas"""
    pedidos: list[Any] = []
    monkeypatch.setattr(
        secao_mesa,
        "run_in_thread",
        lambda fn, ok, falhou=None: pedidos.append(fn),
        raising=False,
    )
    import hefesto_dualsense4unix.app.ipc_bridge as ponte

    monkeypatch.setattr(
        ponte, "run_in_thread", lambda fn, ok, falhou=None: pedidos.append(fn)
    )

    painel = secao_mesa._PainelDaMesa(_Hospedeiro())
    painel._mesa = _mesa()
    painel._pedir_os_dongles()

    assert pedidos == [secao_mesa.ler_os_dongles], (
        "a seção não pediu o nome dos adaptadores ao BlueZ na máquina que TEM "
        f"adaptador. Pedidos: {pedidos}"
    )
