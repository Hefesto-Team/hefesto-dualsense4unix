"""A fita do alvo mudou em seis abas e nenhuma foto podia mostrar — 24/08/2026.

O DEFEITO
---------

A Z2-8 generalizou o que só a aba Configurações fazia: **cada** aba esmaece a
fita "Ajustes vão para:" quando não lê o alvo de edição (`_ALVO_POR_ABA`, em
`src/hefesto_dualsense4unix/app/app.py`). De uma leva, seis abas — Início, No
jogo, Perfis, Sistema, Emulação e Navegação — passaram a esmaecer.

Isso mora no `header_bar`, e o `scripts/gui-captura/retratar_abas.py`
fotografa o `main_notebook`: o cabeçalho fica **fora do recorte de toda foto
de aba**. Consequência medida no dia da integração da Onda 0, com
`git status docs/usage/assets` depois de rodar o script: as onze fotos saíram
**byte a byte idênticas**, e o único arquivo modificado foi o recibo. O portão
`test_as_fotos_nao_ficam_atras_do_codigo_da_tela` cobrava um ensaio que,
rodado, não provava nada — a mudança da leva estava fora do recorte.

Havia `_fotografar_o_cabecalho` no script desde 14/08/2026, e a docstring dela
já dizia que a fita "NENHUMA foto mostrava". Ela só era chamada sob
`--mesa-cheia`, cujo destino fica FORA de `docs/usage/assets` de propósito.
Cura escrita e nunca ligada, que é o defeito mais caro desta casa.

O QUE ESTE ARQUIVO COBRA
------------------------

1. as duas fotos existem em `docs/usage/assets/` e o `interface.md` publica as
   duas;
2. a foto da fita esmaecida sai **diferente** da fita viva — se ela saísse
   igual, teríamos duas cópias do mesmo retrato e nenhuma prova;
3. o `main` fotografa o cabeçalho no modo **padrão**, e não só sob
   `--mesa-cheia`;
4. as duas abas da foto saem do mapa do PRODUTO, não de uma lista repetida no
   script.

AS MORDIDAS
-----------

* Arranque a chamada de `set_alvo_inativo` de `_fotografar_o_cabecalho` (ou
  troque-a por um `pass`): `test_a_fita_esmaecida_sai_diferente_da_fita_viva`
  reprova, porque os dois PNGs saem byte a byte iguais.
* Devolva a chamada do cabeçalho para dentro de um `if mesa_cheia`:
  `test_o_main_fotografa_o_cabecalho_no_modo_padrao` reprova — é o estado
  exato de antes desta data.
* Troque `_as_duas_abas_do_alvo` por uma tupla fixa:
  `test_as_duas_abas_saem_do_mapa_do_produto` reprova assim que o mapa do
  produto e a escolha do script divergirem.
* Tire a guarda `_tema_ja_aplicado` de `_aplicar_tema`:
  `test_o_tema_nao_infla_a_fonte_a_cada_janela` reprova, porque a segunda foto
  do MESMO cabeçalho sai maior que a primeira.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: o script importado abaixo faz `gi.require_version` e
# `from gi.repository import Gtk` no escopo do módulo. Contra o stub, a foto
# não sairia e as comparações de byte passariam sem imagem nenhuma.
exigir_gi_real("a foto do cabeçalho e a fita do alvo")

import contextlib
import importlib.util
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card — sem ele não há pixel a comparar.
pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"
ASSETS = RAIZ / "docs/usage/assets"
INTERFACE = RAIZ / "docs/usage/interface.md"


@pytest.fixture(autouse=True)
def _a_fonte_global_volta_como_estava() -> Any:
    """Devolve o `gtk-font-name` do processo depois de cada teste daqui.

    ACHADO PELO CÉTICO DESTA MESMA LEVA, 24/08/2026, e é a razão de esta
    fixture existir antes de qualquer teste deste arquivo rodar.

    `_script()` reimporta o `retratar_abas.py` a cada chamada, e a carga do
    módulo aplica o tema. `app.theme.apply_theme` LÊ o `gtk-font-name`, soma o
    delta de acessibilidade e GRAVA de volta — não é idempotente, e não precisa
    ser: em produção roda uma vez por processo (`app/app.py:286`). Aqui rodava
    seis vezes, uma por teste, e a base inflava a cada uma:

        carga 1: Fira Sans 12.25    carga 4: Fira Sans 19
        carga 2: Fira Sans 14.5     carga 5: Fira Sans 21.25
        carga 3: Fira Sans 16.75    carga 6: Fira Sans 23.5

    `gtk-font-name` é global do PROCESSO, e o pytest roda a suíte num processo
    só, em ordem alfabética — este arquivo vem antes de
    `test_layout_orcamento_altura.py` e dos outros que medem pixel. Sem esta
    restauração, 13 testes de layout reprovavam com alarme falso de cara de
    defeito real (*"o conteúdo pede 1672px e a janela abre com 1180px"*), e não
    era flaky: era determinístico, e só aparecia com este arquivo na frente.

    A casa já tinha escrito a regra — em `test_layout_orcamento_altura.py:161`,
    justamente o vizinho que este arquivo derrubava: *"`gtk-font-name` é global
    do processo; a restauração impede que as medidas daqui vazem para outros
    arquivos de teste da mesma sessão do pytest."* A fixture de lá salva e
    restaura; esta faz o mesmo, do lado de cá.

    **SÃO DOIS CANAIS, e restaurar só o primeiro não basta** — medido depois de
    a primeira versão desta fixture ainda derrubar
    `test_som_acordado_01_os_dois_estados_na_aba_status.py`, que mede pixel e
    não isola fonte. `apply_theme` também empilha um `Gtk.CssProvider` por
    chamada em `add_provider_for_screen`, com os `font-size` já reescritos, e
    nenhuma guarda o desfaz. Como o provider nasce DENTRO do script, não há
    referência a ele aqui: a saída é interceptar o `add_provider_for_screen`
    enquanto o teste roda, guardar o que passar por ele, e remover os
    provedores no fim.
    """
    settings = Gtk.Settings.get_default()
    tela = Gdk.Screen.get_default()
    anterior = None
    if settings is not None:
        anterior = settings.get_property("gtk-font-name")

    adicionados: list[Any] = []
    original = Gtk.StyleContext.add_provider_for_screen

    def _espiao(screen: Any, provider: Any, prioridade: int) -> Any:
        adicionados.append((screen, provider))
        return original(screen, provider, prioridade)

    Gtk.StyleContext.add_provider_for_screen = _espiao  # type: ignore[assignment]
    try:
        yield
    finally:
        Gtk.StyleContext.add_provider_for_screen = original  # type: ignore[assignment]
        for screen, provider in adicionados:
            with contextlib.suppress(Exception):
                Gtk.StyleContext.remove_provider_for_screen(screen or tela, provider)
        if settings is not None and anterior is not None:
            settings.set_property("gtk-font-name", anterior)


def _script() -> Any:
    """Importa o script de retrato como módulo, sem rodar o `main`."""
    assert SCRIPT.is_file(), f"{SCRIPT} sumiu — o retrato das abas é rotina desta casa"
    spec = importlib.util.spec_from_file_location("_retrato_do_cabecalho", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _builder(modulo: Any) -> Any:
    """O glade montado, com o notebook fora do caminho — como o `main` monta.

    O `main` arranca o `main_notebook` do `root_box` para fotografá-lo. Aqui o
    interesse é o `header_bar`, que fica no `root_box`; arrancar o notebook
    reproduz o mesmo estado de árvore em que a foto do cabeçalho é tirada.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(modulo.GLADE))
    notebook = builder.get_object("main_notebook")
    assert notebook is not None, "`main_notebook` sumiu do glade"
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela = Gtk.OffscreenWindow()
    janela.add(notebook)
    janela.set_size_request(modulo.LARGURA, modulo.ALTURA)
    janela.show_all()
    modulo._assentar()
    return builder


# ----------------------------------------------------------------------
# 1 e 2 — as duas fotos existem, e não são a mesma imagem
# ----------------------------------------------------------------------


def test_as_duas_fotos_do_cabecalho_estao_publicadas() -> None:
    """Gravar e não publicar desfaz a cura: o `interface.md` cita as duas."""
    modulo = _script()
    interface = INTERFACE.read_text(encoding="utf-8")

    for nome in (modulo.NOME_DO_CABECALHO, modulo.NOME_DO_CABECALHO_INERTE):
        arquivo = f"{nome}.png"
        assert (ASSETS / arquivo).is_file(), (
            f"{arquivo} não existe em {ASSETS}. O `retratar_abas.py` grava as "
            "duas no modo padrão desde 24/08/2026 — sem elas, a fita do alvo "
            "volta a não ter foto nenhuma neste repositório."
        )
        assert arquivo in interface, (
            f"{arquivo} não é citada no `interface.md`. A seção 'O cabeçalho' "
            "voltaria a ser escrita contra o código, que é o estado que esta "
            "leva corrigiu."
        )


def test_a_fita_esmaecida_sai_diferente_da_fita_viva(tmp_path: Path) -> None:
    """A MORDIDA principal: os dois estados da fita têm de sair em PIXEL.

    Sem a chamada de `ConfigActionsMixin.set_alvo_inativo` dentro de
    `_fotografar_o_cabecalho`, as duas fotos saem byte a byte iguais — duas
    cópias do mesmo retrato, e a mudança da Z2-8 continua sem prova visual.

    Quem esmaece é o método de PRODUÇÃO, e é isso que esta régua mede pelo
    resultado: uma chamada a `set_sensitive(False)` escrita no script seria um
    segundo dono da regra, e a foto passaria a mentir no dia em que o produto
    mudasse de ideia.
    """
    modulo = _script()
    builder = _builder(modulo)
    host = modulo._host_do_cabecalho(builder)
    estado = modulo.ESTADO_PADRAO_DE_DOIS

    viva = modulo._fotografar_o_cabecalho(
        builder, estado, tmp_path, "viva", host=host
    )
    inerte = modulo._fotografar_o_cabecalho(
        builder, estado, tmp_path, "inerte", host=host, motivo="a aba não lê o alvo"
    )

    for recado in (viva, inerte):
        assert "não fotografado" not in recado, recado

    bytes_viva = (tmp_path / "viva.png").read_bytes()
    bytes_inerte = (tmp_path / "inerte.png").read_bytes()
    assert bytes_viva and bytes_inerte, "uma das duas fotos saiu vazia"
    assert bytes_viva != bytes_inerte, (
        "a foto da fita ESMAECIDA saiu idêntica à da fita viva. O `motivo` "
        "chegou e nada mudou na tela: ou `set_alvo_inativo` não foi chamado, "
        "ou a fita não estava montada no cabeçalho. As duas imagens de "
        "`docs/usage/assets/` seriam a mesma coisa duas vezes, e a mudança da "
        "Z2-8 continuaria sem prova visual — que é o defeito que abriu esta "
        f"leva.\nO script disse: {viva!r} / {inerte!r}"
    )


def test_o_tema_nao_infla_a_fonte_a_cada_janela(tmp_path: Path) -> None:
    """Duas fotos do MESMO cabeçalho têm de sair byte a byte iguais.

    `apply_theme` não é idempotente — e não precisa ser: em produção ele roda
    uma vez (`app/app.py:286`). Ele lê `gtk-font-name`, soma o delta de
    acessibilidade e grava de volta, então a segunda chamada soma o delta sobre
    o nome já somado.

    Medido em 24/08/2026, fotografando o cabeçalho cinco vezes com o MESMO
    conteúdo e os MESMOS 17 widgets visíveis: 117, 119, 122, 126, 130 px. Com
    duas fotos de cabeçalho na documentação, a segunda sairia com a tipografia
    maior que a primeira — e quem as comparasse concluiria que esmaecer a fita
    muda o tamanho do texto.

    A MORDIDA: tire a guarda `_tema_ja_aplicado` de `_aplicar_tema` e rode este
    teste; ele reprova dizendo quantos px a segunda foto cresceu.
    """
    modulo = _script()
    builder = _builder(modulo)
    modulo._aplicar_tema(Gtk.OffscreenWindow())
    host = modulo._host_do_cabecalho(builder)
    estado = modulo.ESTADO_PADRAO_DE_DOIS

    modulo._fotografar_o_cabecalho(builder, estado, tmp_path, "um", host=host)
    modulo._fotografar_o_cabecalho(builder, estado, tmp_path, "dois", host=host)

    um = (tmp_path / "um.png").read_bytes()
    dois = (tmp_path / "dois.png").read_bytes()
    assert um and dois, "uma das duas fotos saiu vazia"
    assert um == dois, (
        "duas fotos do MESMO cabeçalho saíram diferentes "
        f"({len(um)} bytes contra {len(dois)}). O tema está sendo reaplicado a "
        "cada janela nova e inflando a fonte da tela inteira — a foto do "
        "cabeçalho sai com tipografia maior que a das abas, e a segunda maior "
        "que a primeira."
    )


# ----------------------------------------------------------------------
# 3 — no modo PADRÃO, que é o que a documentação publica
# ----------------------------------------------------------------------


def test_o_main_fotografa_o_cabecalho_no_modo_padrao(tmp_path: Path) -> None:
    """A cura escrita e nunca ligada: o `main` SEM argumento tem de gravar as duas.

    Roda o `main` inteiro apontado para `tmp_path` — o argumento posicional que
    o `USO` do script chama de "grava nessa pasta e não toca no repositório".
    Custa ~6 s e é a única régua que não se engana: uma leitura de AST diria
    que a chamada existe mesmo com ela num ramo que o modo padrão nunca
    alcança, que é exatamente o estado de antes de 24/08/2026 — as duas
    chamadas viviam sob `if mesa_cheia and estado_da_mesa is not None`, e o
    destino daquele modo fica FORA de `docs/usage/assets` de propósito.

    A MORDIDA: devolva as chamadas para dentro de um `if mesa_cheia` e rode
    este teste; ele reprova nomeando o PNG que não saiu.
    """
    modulo = _script()

    assert modulo.main(str(tmp_path)) == 0, "o `main` do retrato saiu com erro"

    gravados = sorted(q.name for q in tmp_path.glob("*.png"))
    for nome in (modulo.NOME_DO_CABECALHO, modulo.NOME_DO_CABECALHO_INERTE):
        assert f"{nome}.png" in gravados, (
            f"o modo PADRÃO não gravou {nome}.png. A fita 'Ajustes vão para:' "
            "mora no `header_bar`, fora do recorte de toda foto de aba: sem "
            "esta imagem, uma mudança só do cabeçalho deixa o portão das fotos "
            "cobrando um ensaio que, rodado, não move um pixel.\n"
            f"O que saiu: {gravados}"
        )


# ----------------------------------------------------------------------
# 4 — a escolha das duas abas é do PRODUTO
# ----------------------------------------------------------------------


def test_as_duas_abas_saem_do_mapa_do_produto() -> None:
    """A aba que lê e a que não lê vêm de `_ALVO_POR_ABA`, não de uma cópia.

    Uma lista repetida no script continuaria fotografando o estado de ontem
    quando uma onda ligasse o leitor de mais uma aba — e a documentação
    passaria a mostrar como inerte uma fita que já está viva.
    """
    from hefesto_dualsense4unix.app.app import HefestoApp

    modulo = _script()
    escolha = modulo._as_duas_abas_do_alvo()
    assert escolha is not None, (
        "`_as_duas_abas_do_alvo` não achou os dois lados em "
        "`HefestoApp._ALVO_POR_ABA`. Sem eles, a foto da fita esmaecida não "
        "sai e a mudança da Z2-8 fica sem prova."
    )

    aba_que_le, aba_inerte, motivo = escolha
    mapa = HefestoApp._ALVO_POR_ABA

    assert mapa[aba_que_le] is None, (
        f"o script escolheu `{aba_que_le}` como a aba que LÊ o alvo, e o mapa "
        f"do produto diz que ela não lê ({mapa[aba_que_le]!r}). A foto da fita "
        "viva estaria retratando uma aba em que ela está esmaecida."
    )
    assert mapa[aba_inerte] == motivo, (
        f"o script escolheu `{aba_inerte}` como a aba INERTE com o motivo "
        f"{motivo!r}, e o mapa do produto diz {mapa[aba_inerte]!r}."
    )
    assert isinstance(motivo, str) and motivo, (
        "a aba inerte veio sem motivo. `set_alvo_inativo(True)` sem motivo "
        "LEVANTA (contrato Z2 §5), e a foto sairia com a fita sensível."
    )


def test_o_duble_de_dois_tem_um_dono_so() -> None:
    """A mesa da foto do cabeçalho é a MESMA que as abas mostram.

    `ESTADO_PADRAO_DE_DOIS` nasceu de dentro do `_montar_aba_inicio` em
    24/08/2026, quando a foto do cabeçalho passou a existir no modo padrão.
    Dois dublês seriam duas mesas: a fita podendo dizer "2 controles" ao lado
    de uma aba Início com outros dois, e ninguém percebendo.
    """
    modulo = _script()
    controles = modulo.ESTADO_PADRAO_DE_DOIS["controllers"]

    assert len(controles) == 2, (
        f"o dublê padrão saiu com {len(controles)} controle(s). As imagens de "
        "`docs/usage/assets/` são as do README e do guia da interface: trocar "
        "a mesa delas é mudança que ninguém pediu."
    )
    assert all(c.get("uniq") for c in controles), (
        "um controle do dublê padrão está sem `uniq`. A fita 'Ajustes vão "
        "para:' só ganha chip de controle com endereço — sem ele a foto do "
        "cabeçalho sai com a legenda e nenhum botão."
    )
    assert {c["transport"] for c in controles} == {"usb", "bt"}, (
        "o dublê padrão deixou de ser um controle no cabo e um no rádio, que "
        "é o cenário que o `interface.md` descreve."
    )

    origem = SCRIPT.read_text(encoding="utf-8")
    corpo_do_inicio = origem.split("def _montar_aba_inicio", 1)[1].split(
        "\ndef ", 1
    )[0]
    assert "ESTADO_PADRAO_DE_DOIS" in corpo_do_inicio, (
        "o `_montar_aba_inicio` voltou a montar o próprio dublê em vez de ler "
        "`ESTADO_PADRAO_DE_DOIS` — a foto do cabeçalho e a da aba Início "
        "podem passar a mostrar mesas diferentes."
    )
