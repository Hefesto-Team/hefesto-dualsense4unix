"""A bancada de mentira da foto exercita os DOIS casos da coluna "O que é".

POR QUE ESTE PORTÃO EXISTE. A seção "A mesa" é fotografada com um sysfs
inventado, e não com o barramento dela — a foto entra em `docs/usage/assets/`
sem revisão humana e nenhum portão desta casa varre imagem. A bancada é, então,
a única coisa que decide o que a documentação mostra daquela seção.

Uma bancada em que todo aparelho se declara faria a foto esconder metade da
tela: sumiriam o seletor, o `▲` e a única linha que precisa dela. Uma bancada
em que nenhum se declara mostraria a tela ANTIGA — sete botões em toda linha —
como se fosse a de hoje, e é assim que uma foto mente sem ninguém mexer no
produto.

É a lição de 22/08/2026, que esta casa pagou quatro vezes num dia: **o
instrumento mente mais que o produto.** A quarta foi neste mesmo arquivo — o
retrato montava a aba Gatilhos diferente do produto, e ela decidiu a fila de
interface olhando aquele vazio.

**A QUINTA FOI ESTE PRÓPRIO PORTÃO, MEDIDA EM 23/08/2026** (AUDITORIA-DE-
PERDA-01/E1). As quatro versões anteriores destas asserções mediam o DADO da
bancada — `_censo_de_mentira()`, `_dongles_de_mentira()`, chamadas soltas,
fora de qualquer host — e nunca que a aba Configurações de PRODUÇÃO
(`retratar_abas.py::_montar_aba_configuracoes`, que cria um `_Host` real e
chama `ConfigActionsMixin.install_config_tab()`) de fato os USA. Apagar
`self._censo_leitor = _censo_de_mentira` ou `self._dongles_leitor =
_dongles_de_mentira` daquele `_Host` — as duas linhas que ligam a bancada ao
retrato — fazia a coluna "O que é" inteira cair em "não sei" e a coluna "Nome"
sumir, e as quatro versões anteriores continuavam verdes: elas recalculavam a
mesma bancada de novo, por fora do `_Host`, e comparavam a bancada consigo
mesma.

A cura é medir a ÁRVORE MONTADA pelo `_Host` de produção — a mesma que o
`main()` do retrato fotografa — e não as funções soltas.

O QUE ELE COBRA, agora sobre a árvore montada:

1. **os dois graus na mesma foto** — pelo menos uma linha que o barramento
   classificou (`_SELO_LIDO` na tela) e pelo menos uma que ele não classificou
   (`_AVISO_NAO_SABE` na tela);
2. **as duas leituras casam** — se `_censo_leitor` e `_mesa_leitor` discordarem
   de raiz USB, TODO rádio vira "não sei" por engano do instrumento (é a
   guarda de `secao_mesa._celula_do_que_e`: `aparelho is None` cai no mesmo
   ramo de "ninguém sabe"), e o item 1 já reprova sozinho — nenhuma linha
   nasce com `_SELO_LIDO`;
3. **o nome do adaptador aparece, e o prefixo NÃO** — a foto tem de mostrar o
   que a costura faz: alias `"Nintendo Extra"`, tela `"Extra"`;
4. **nada disso é dado dela** — endereços forjados na bancada, e a leitura
   viva do BlueZ desta máquina não é chamada (a premissa de tudo acima).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub da suíte
# a árvore montada sairia vazia e as asserções abaixo passariam sem widget
# nenhum — exatamente o defeito que esta leva veio corrigir, um nível acima.
exigir_gi_real("a bancada da foto, exercitada pelo _Host de produção")

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG
from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"


def _retrato() -> Any:
    """O script importado como módulo — ele tem hífen na pasta, não no nome.

    Leitura do FONTE, não pelo `exec_module`, pela razão medida em 22/08/2026
    e documentada no irmão deste arquivo (`test_a_coluna_do_que_e_nasce_
    lida.py`): compilar bytecode em cache pode reaproveitar a versão antiga do
    arquivo quando a mordida preserva o tamanho em bytes dentro do mesmo
    segundo. Compilar o texto lido agora não tem cache por onde errar.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_retrato_da_bancada", SCRIPT)
    assert spec is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_retrato_da_bancada"] = modulo
    exec(compile(fonte, str(SCRIPT), "exec"), modulo.__dict__)
    return modulo


def _montar_a_aba_configuracoes() -> Any:
    """A aba Configurações pelo `_Host` de PRODUÇÃO do retrato.

    É o MESMO caminho que `main()` percorre para gerar a foto: um
    `Gtk.Builder` do `main.glade` de verdade, e
    `_montar_aba_configuracoes(builder)` — que cria o `_Host(ConfigActionsMixin)`
    com `_mesa_leitor`/`_censo_leitor`/`_dongles_leitor` injetados e chama
    `install_config_tab()`. Nenhuma função solta da bancada é chamada aqui.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(GLADE))
    retrato = _retrato()
    resultado = retrato._montar_aba_configuracoes(builder)
    assert "não montada" not in resultado, (
        f"a aba Configurações não montou no retrato: {resultado}"
    )
    caixa = builder.get_object(ABA_CONFIG)
    assert caixa is not None, "`tab_config_box` sumiu do glade"
    return caixa


def _textos(raiz: Any) -> list[str]:
    """Todo texto da árvore montada, fora dos botões do seletor de tipo.

    A mesma exclusão de `test_a_coluna_do_que_e_nasce_lida.py`: o seletor tem
    um botão escrito "Teclado", a mesma palavra que a coluna usa para AFIRMAR.
    """
    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, SegmentedSelector):
            return
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados


def test_a_foto_da_mesa_mostra_os_dois_graus_pelo_host_de_producao() -> None:
    """Os dois graus, na árvore que o `_Host` de produção de fato monta.

    Mordida: apagar `self._censo_leitor = _censo_de_mentira` em
    `_montar_aba_configuracoes` (retratar_abas.py). Sem ele, `_ler_o_censo`
    devolve `Censo()` vazio (`secao_mesa.py`) e TODA linha cai no ramo
    "ninguém sabe" — nenhum `_SELO_LIDO` sobra na tela.
    """
    textos = _textos(_montar_a_aba_configuracoes())
    assert secao_mesa._SELO_LIDO in textos, (
        "nenhuma linha da mesa nasceu classificada pelo barramento — a coluna "
        "'O que é' caiu inteira em 'não sei'. Isto é o que acontece se "
        "`_censo_leitor` sumir do `_Host` do retrato, ou se ele e "
        f"`_mesa_leitor` discordarem de raiz USB. Textos: {textos}"
    )
    assert secao_mesa._AVISO_NAO_SABE in textos, (
        "nenhuma linha ficou sem resposta — sumiram o seletor e o aviso que a "
        f"bancada existe para exercitar. Textos: {textos}"
    )


def test_a_foto_da_mesa_mostra_o_nome_do_adaptador_e_esconde_o_prefixo() -> None:
    """O que a costura do apelido faz tem de aparecer na foto de verdade.

    Mordida: apagar `self._dongles_leitor = _dongles_de_mentira` em
    `_montar_aba_configuracoes`. Sem ele, `_ler_os_dongles_de_bancada` não
    roda e a coluna "Nome" sai vazia — os dois nomes somem da foto.
    """
    textos = _textos(_montar_a_aba_configuracoes())
    assert any("Sala" in t for t in textos), (
        f"o nome do primeiro adaptador da bancada não chegou à foto. Textos: {textos}"
    )
    assert any("Extra" in t for t in textos), (
        "o alias sem o prefixo Nintendo não chegou à foto — a costura do "
        f"apelido existe para mostrar exatamente isto. Textos: {textos}"
    )
    assert not any("Nintendo Extra" in t for t in textos), (
        "o alias COM o prefixo Nintendo vazou para a tela; a costura existe "
        "para escondê-lo, e a foto publicaria o texto interno em vez do "
        f"nome exibido. Textos: {textos}"
    )


def test_a_bancada_nao_usa_endereco_de_verdade() -> None:
    """A premissa de tudo acima: o endereço é forjado.

    Mordida: pôr um BD Address real em `_MESA_DONGLES`.
    """
    for dongle in _retrato()._dongles_de_mentira():
        assert dongle.endereco.upper().startswith(("AA:", "00:", "02:")), (
            f"o adaptador de bancada usa {dongle.endereco!r}, que não parece "
            "forjado. O retrato publica em docs/usage/assets/."
        )
