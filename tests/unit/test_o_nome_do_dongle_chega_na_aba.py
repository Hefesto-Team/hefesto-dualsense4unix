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
3. **o que vai ao BlueZ é o costurado.** Salvar `"Extra"` num adaptador que
   hospeda Nintendo escreve `"Nintendo Extra"` de volta — a régua olha o que
   chegaria ao `set-property`, não o que a função devolveu;
4. **nome igual não escreve.** Sem essa comparação, cada troca de aba
   reescreveria o alias dos três adaptadores;
5. **a junção da tabela é por `hciN` e nunca é guardada**; a junção do medidor
   é por ENDEREÇO dos dois lados;
6. **a captura não fala com o BlueZ.** O alias é texto que ela escreveu.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("o nome do adaptador na seção A mesa")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations import apelido_do_dongle
from hefesto_dualsense4unix.integrations.apelido_do_dongle import Dongle
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa
from hefesto_dualsense4unix.integrations.radio_da_mesa import Ocupacao

#: Endereços forjados, faixa `aa:bb:cc` — a mesma que a suíte usa e que
#: `check_anonymity.sh` não confunde com OUI de verdade.
_SALA = "AA:BB:CC:00:00:01"
_EXTRA = "AA:BB:CC:00:00:02"


class _Hospedeiro:
    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


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
            ),
            Adaptador(
                interface="hci1",
                no="/bancada/usb1/1-2/1-2.1",
                vid="2357",
                pid="0604",
                busnum=1,
                devpath="2.1",
                atras_de_hub=True,
            ),
        )
    )


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
    """Os campos de nome NA ORDEM DAS LINHAS da tabela.

    Andar a árvore não serve aqui, e a diferença é o teste inteiro: o
    `Gtk.Grid.get_children()` devolve os filhos na ordem INVERSA de inserção,
    então uma lista montada assim diria que o nome do `hci0` é o do `hci1`. A
    posição na grade é a única coisa que responde "de quem é esta linha".
    """
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


class _BusctlDeMentira:
    """Um `executar` que registra o que o produto MANDARIA ao BlueZ.

    A régua tem de olhar o argumento do `set-property`, e não o que a função
    devolveu: uma costura que só existe no valor de retorno protege o Pro em
    lugar nenhum.
    """

    def __init__(self) -> None:
        self.escritas: list[tuple[str, str]] = []

    def __call__(self, argumentos: Any) -> str | None:
        partes = list(argumentos)
        if partes and partes[0] == "set-property":
            self.escritas.append((partes[2], partes[-1]))
        return ""


# --- 1. A coluna existe quando alguém respondeu ----------------------------


def test_a_coluna_do_nome_nasce_com_o_nome_dela() -> None:
    """Dois campos, e o segundo mostra "Extra" — sem o prefixo.

    Mordida: trocar `dongle.nome` por `dongle.alias` em `_campo_do_nome` — o
    campo passa a mostrar "Nintendo Extra" e este teste reprova.
    """
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
    """Coluna que só sabe dizer "não sei" ocupa a largura que a janela não tem.

    Mordida: montar a coluna incondicionalmente em `_desenhar_adaptadores`.
    """
    caixa, _ = _montar(_Hospedeiro(), dongles=())

    assert not _campos(caixa), (
        "a coluna do nome apareceu sem o BlueZ ter respondido por adaptador "
        "nenhum — no Flatpak e com o serviço parado é sempre este o caso"
    )
    assert secao_mesa._COLUNA_NOME not in _textos(caixa), (
        "o cabeçalho da coluna ficou na tabela sem coluna embaixo"
    )


def test_a_nota_do_prefixo_so_aparece_onde_ha_nintendo() -> None:
    """Explicação sobre coisa nenhuma é ruído; explicação ausente é armadilha.

    Mordida: tirar o `if any(d.hospeda_nintendo ...)` — a nota passa a aparecer
    em mesa sem Pro nenhum.
    """
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
    """Duas semânticas na mesma seção, e a segunda não pode ficar calada.

    As três declarações desta seção esperam o "Aplicar" do rodapé; o nome vai
    ao BlueZ no Enter. Quem clica e não vê nada acontecer conclui uma de duas
    coisas, e as duas são ruins.

    Mordida: tirar o `rotulo_de_apoio(_NOME_VALE_JA, ...)`.
    """
    caixa, _ = _montar(_Hospedeiro())
    assert secao_mesa._NOME_VALE_JA in _textos(caixa)


# --- 2. O que vai ao BlueZ é o costurado -----------------------------------


def test_salvar_um_nome_escreve_o_alias_costurado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Casa" num adaptador com Pro chega ao BlueZ como "Nintendo Casa".

    A régua não é "a função foi chamada": é o argumento do `set-property`. Um
    produto que costurasse só o valor de retorno deixaria o Pro caindo sob
    carga e passaria num teste de chamada.

    Mordida: passar `nome` cru para o `set-property` (isto é, chamar
    `_busctl` direto em vez de `renomear_o_dongle`).
    """
    busctl = _BusctlDeMentira()
    monkeypatch.setattr(
        secao_mesa,
        "renomear_o_dongle",
        lambda endereco, nome, **kw: apelido_do_dongle.renomear_o_dongle(
            endereco, nome, executar=busctl, **kw
        ),
    )

    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[1]
    campo.set_text("Casa")
    painel._ao_salvar_o_nome(campo, _EXTRA)

    assert busctl.escritas == [("/org/bluez/hci1", "Nintendo Casa")], (
        "o produto não costurou o prefixo ao gravar. Sem ele o Pro Controller "
        f"cai sob carga — rumble e IMU juntos. Escritas: {busctl.escritas}"
    )


def test_salvar_num_adaptador_sem_nintendo_nao_acrescenta_palavra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O produto não põe palavra que não protege nada.

    Mordida: costurar sempre, sem olhar `hospeda_nintendo`.
    """
    busctl = _BusctlDeMentira()
    monkeypatch.setattr(
        secao_mesa,
        "renomear_o_dongle",
        lambda endereco, nome, **kw: apelido_do_dongle.renomear_o_dongle(
            endereco, nome, executar=busctl, **kw
        ),
    )

    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[0]
    campo.set_text("Sofá")
    painel._ao_salvar_o_nome(campo, _SALA)

    assert busctl.escritas == [("/org/bluez/hci0", "Sofá")]


def test_nome_que_nao_mudou_nao_vai_ao_bluez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sair do campo sem ter mexido não escreve nada.

    Sem esta guarda, cada troca de aba reescreveria o alias dos três
    adaptadores dela com o valor que eles já têm — e uma dessas escritas cai
    bem em cima do prefixo que segura o Pro.

    Mordida: apagar o `if novo == alvo.nome: return`.
    """
    chamadas: list[Any] = []
    monkeypatch.setattr(
        secao_mesa,
        "renomear_o_dongle",
        lambda *a, **k: chamadas.append(a),
    )

    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[1]
    painel._ao_sair_do_nome(campo, None, _EXTRA)

    assert not chamadas, (
        "sair do campo sem mexer escreveu no BlueZ. O texto do campo é o nome "
        "LIMPO; comparar contra o alias faria toda saída de campo gravar."
    )


def test_o_espelho_de_memoria_impede_a_segunda_escrita_igual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Depois de gravar, o produto sabe o nome novo sem reler o BlueZ.

    Reler não é opção: a escrita do `Alias` é assíncrona e ler logo depois
    devolve o valor ANTIGO (medido em `apelido_do_dongle`). Sem o espelho, o
    próximo `focus-out` compararia contra o nome velho e mandaria o mesmo alias
    de novo.

    Mordida: apagar a reconstrução de `self._dongles` em `_ao_salvar_o_nome`.
    """
    busctl = _BusctlDeMentira()
    monkeypatch.setattr(
        secao_mesa,
        "renomear_o_dongle",
        lambda endereco, nome, **kw: apelido_do_dongle.renomear_o_dongle(
            endereco, nome, executar=busctl, **kw
        ),
    )

    caixa, painel = _montar(_Hospedeiro())
    campo = _campos(caixa)[1]
    campo.set_text("Casa")
    painel._ao_salvar_o_nome(campo, _EXTRA)
    painel._ao_salvar_o_nome(campo, _EXTRA)

    assert len(busctl.escritas) == 1, (
        f"o mesmo nome foi ao BlueZ {len(busctl.escritas)} vezes"
    )


# --- 3. As duas junções ----------------------------------------------------


def test_a_tabela_junta_por_hci_e_o_hci_nao_e_guardado() -> None:
    """A linha do `hci1` recebe o campo do `/org/bluez/hci1`, e nada mais.

    É a única junção desta seção que passa por `hciN`, e ela é refeita a cada
    leitura: o índice inverte entre boots, e o que segue para a escrita é
    sempre o BD Address.

    Mordida: juntar por POSIÇÃO (o primeiro adaptador com o primeiro dongle) —
    inverta a ordem dos dongles abaixo e a tabela passa a nomear o adaptador
    errado, que é ela renomeando o dongle do sofá achando que é o da mesa.
    """
    invertidos = tuple(reversed(_dongles()))
    caixa, _ = _montar(_Hospedeiro(), dongles=invertidos)

    assert [c.get_text() for c in _campos(caixa)] == ["Sala", "Extra"], (
        "a ordem em que o BlueZ respondeu mudou de quem é cada nome — a "
        "junção não está usando o `hciN` do objeto"
    )

    por_interface = secao_mesa._dongle_por_interface(invertidos)
    assert por_interface["hci1"].endereco == _EXTRA


def test_o_medidor_passa_a_se_chamar_pelo_nome_dela() -> None:
    """`Rádio em uso · Sala` em vez de um endereço hexa.

    Esta junção é por ENDEREÇO dos dois lados — o `HID_PHYS` do controle contra
    o `Address` do adaptador —, então não há chute nenhum. Endereço que não bate
    continua se chamando pelo endereço, que é a resposta honesta.

    Mordida: devolver `f"Rádio em uso · {nome}"` sempre em `_rotulo_do_medidor`.
    """
    apelidos = secao_mesa._apelido_por_endereco(_dongles())

    assert (
        secao_mesa._rotulo_do_medidor(_SALA.lower(), apelidos) == "Rádio em uso · Sala"
    ), "o medidor continua nomeado pelo endereço mesmo com nome dado"
    assert (
        secao_mesa._rotulo_do_medidor("AA:BB:CC:00:00:09", apelidos)
        == "Rádio em uso · AA:BB:CC:00:00:09"
    ), "o medidor inventou um nome para um endereço que ninguém batizou"


def test_a_barra_desenhada_carrega_o_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua de ponta a ponta: o nome tem de chegar ao rótulo DESENHADO.

    `_rotulo_do_medidor` pode estar certo e a fileira continuar chamando a
    versão sem apelidos — foi assim que o instrumento mentiu quatro vezes nesta
    casa em 22/08.

    Mordida: chamar `_rotulo_do_medidor(nome)` sem os apelidos em
    `_fileira_do_medidor`.
    """
    _, painel = _montar(_Hospedeiro())
    painel._ocupacoes = lambda: {_SALA.lower(): Ocupacao()}  # type: ignore[method-assign]
    painel._desenhar_medidores()

    assert "Rádio em uso · Sala" in _textos(painel._caixa_medidores), (
        "a barra desenhada não usa o nome, mesmo com a função de rótulo "
        f"sabendo dele. Textos: {_textos(painel._caixa_medidores)}"
    )


def test_a_barra_em_zero_tambem_se_chama_pelo_nome() -> None:
    """Com tudo no cabo, três adaptadores iguais davam três rótulos iguais.

    É o estado mais comum da mesa dela, e o que a versão anterior desenhava era
    `2357:0604` repetido — exatamente o problema que os nomes vieram resolver.
    Aqui a barra não tem endereço nenhum para juntar (não há controle no
    rádio), então quem nomeia é o `hciN` da MESMA leitura.

    Mordida: apagar o argumento `por_interface` da chamada de
    `_medidores_da_mesa` em `_desenhar_medidores`.
    """
    _, painel = _montar(_Hospedeiro())
    painel._ocupacoes = lambda: {}  # type: ignore[method-assign]
    painel._desenhar_medidores()

    textos = _textos(painel._caixa_medidores)
    assert "Rádio em uso · Sala" in textos and "Rádio em uso · Extra" in textos, (
        "as barras em zero continuam nomeadas pela identidade física. Com três "
        f"adaptadores iguais, os três rótulos ficam idênticos. Textos: {textos}"
    )


def test_a_barra_em_zero_sem_nome_volta_para_a_identidade_fisica() -> None:
    """Sem BlueZ não se inventa nome — o rótulo é o `vid:pid`, como antes.

    Mordida: fazer `_medidores_da_mesa` devolver `""` quando não há dongle.
    """
    _, painel = _montar(_Hospedeiro(), dongles=())
    painel._ocupacoes = lambda: {}  # type: ignore[method-assign]
    painel._desenhar_medidores()

    assert "Rádio em uso · 2357:0604" in _textos(painel._caixa_medidores)


# --- 4. A captura não fala com o BlueZ -------------------------------------


def test_durante_a_captura_a_secao_nao_le_o_bluez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O alias é texto que ELA escreveu, e a foto vai para `docs/` sem revisão.

    A régua registra EFEITO: o espião substitui `ler_os_dongles` e conta.

    Mordida: apagar a guarda do `_mesa_leitor` em `_pedir_os_dongles`.
    """
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
    """Sem adaptador não há nome a dar — e é o caso mais comum lá fora.

    É esta guarda que mantém treze `busctl` fora de toda máquina sem Bluetooth,
    e fora da bateria de testes.

    Mordida: apagar o `if not self._mesa.adaptadores`.
    """
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
    """A contraparte das duas guardas acima, e sem ela as duas são satisfeitas
    por um método que nunca lê nada.

    Mordida: fazer `_pedir_os_dongles` retornar antes de tudo.
    """
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
