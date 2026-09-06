"""A aba Configurações montada SEM a janela GTK — o berço que sobrou.

POR QUE ELE EXISTE — 06/09/2026, sprint `GTK-3`
-----------------------------------------------

A aba Configurações **nunca morou no `gui/main.glade`**: o XML reservava o
container (`tab_config_box`) e as cinco seções nasciam em código, em
`app/actions/config/`, que é MOTOR e a sprint manda ficar. Três réguas de
redação e de saúde montavam a aba de verdade para medir o texto e os selos, e
todas as três abriam o glade **só para pegar a caixa vazia**.

Com o XML apagado (`D-0609-GTK-LEVA-INTEIRA`), o berço passa a ser feito em
código. O que se mede continua sendo o mesmo: o que o MOTOR escreve dentro da
caixa.

O DUBLÊ NASCEU FROUXO, E A MEDIÇÃO PEGOU — a razão de ele ter DOIS widgets
--------------------------------------------------------------------------

A primeira versão devolvia só a caixa. Medido no mesmo dia, contra o
`main.glade` de `98f2a6a4` restaurado do git e montado no MESMO processo:

    com o glade   5 seções · 196 textos
    com a caixa   5 seções · 193 textos      ← TRÊS A MENOS, em silêncio

As três eram *"Ligar junto com o computador"*, *"Desligado"* e *"Este valor é
um espelho. Quem liga e desliga é o interruptor da aba Sistema."* —
`secao_janela._linha_do_espelho` (`:440`) devolve `None` quando
`daemon_autostart_switch` não existe, e a linha inteira some sem levantar. Uma
régua de redação que não vê três frases é uma régua que passa com a frase
errada dentro.

**É a cicatriz desta casa, e ela é literal:** *"três dublês eram mais frouxos
que o daemon vivo"* (05/09/2026). Por isso o berço declara o interruptor, e por
isso `FRASES_DO_ESPELHO` existe: a régua
`test_o_berco_nao_e_mais_frouxo_que_o_glade` cobra as três pelo NOME.

E A CONTAGEM ABSOLUTA NÃO SERVE DE RÉGUA, e isso também foi medido
-------------------------------------------------------------------

A mesma aba colhe **199** textos num processo solto e **196** sob a suíte: três
frases da seção do arranjo leem o DMI da placa (*"A BIOS desta placa conta 5
entradas USB"*) e o `conftest` desvia o `HOME` e os quatro `XDG_*` para um lar
de mentira. Um número cravado aqui mediria a BANCADA, não o produto — que é a
família de defeito que esta casa persegue. Por isso a régua cobra as frases que
somem e um PISO, nunca a igualdade.

`ConfigActionsMixin._get` é o único caminho pelo qual as seções pedem widget, e
`daemon_autostart_switch` é o ÚNICO id que elas pedem — conferido com

    grep -rn '_get("' src/hefesto_dualsense4unix/app/actions/config/
"""
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG
from hefesto_dualsense4unix.app.actions.config.mixin import (
    ConfigActionsMixin,
)

#: Quantas seções a aba tinha no `gui/main.glade`, medido em 06/09/2026 no XML
#: restaurado do git antes de ele ser apagado.
SECOES_NO_GLADE = 5

#: As três frases que somem quando o berço não entrega o `daemon_autostart_switch`
#: — a `secao_janela._linha_do_espelho` devolve `None` e a linha inteira
#: desaparece sem levantar. São a prova de que o berço não é mais frouxo.
FRASES_DO_ESPELHO = (
    "Ligar junto com o computador",
    "Este valor é um espelho. Quem liga e desliga é o interruptor da aba Sistema.",
)

#: PISO da colheita, e ele é piso e não igualdade: três frases da seção do
#: arranjo leem o DMI da placa e somem sob o `HOME` de mentira do `conftest`
#: (196 sob a suíte, 199 num processo solto). Piso baixo o bastante para não
#: medir a bancada, alto o bastante para acusar uma seção que sumiu inteira —
#: a menor delas custa 16 textos.
PISO_DA_COLHEITA = 190


class BercoDaAbaConfig:
    """O que o `Gtk.Builder` do glade entregava às seções, e nada mais."""

    def __init__(self) -> None:
        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.caixa.set_name(ABA_CONFIG)
        #: O original do espelho da `secao_janela`. No XML ele morava na aba
        #: Sistema; aqui ele é só a fonte de `notify::active` que a linha do
        #: espelho acompanha.
        self.interruptor_do_arranque = Gtk.Switch()

    def get_object(self, nome: str) -> Any:
        if nome == ABA_CONFIG:
            return self.caixa
        if nome == "daemon_autostart_switch":
            return self.interruptor_do_arranque
        return None


class HospedeiroDaAbaConfig(ConfigActionsMixin):
    """O mínimo que o mixin precisa para montar a aba: um `builder`."""

    def __init__(self, builder: BercoDaAbaConfig | None = None) -> None:
        self.builder = builder or BercoDaAbaConfig()


def aba_config_montada() -> Any:
    """Monta as cinco seções em código e devolve a caixa da aba."""
    hospedeiro = HospedeiroDaAbaConfig()
    hospedeiro.install_config_tab()
    return hospedeiro.builder.get_object(ABA_CONFIG)


def textos_da_arvore(raiz: Any) -> list[str]:
    """Todo texto visível da árvore — rótulo, rótulo de botão e dica."""
    achados: list[str] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        if isinstance(widget, Gtk.Label):
            texto = widget.get_text()
            if texto:
                achados.append(texto)
        obter_rotulo = getattr(widget, "get_label", None)
        if obter_rotulo is not None and not isinstance(widget, Gtk.Label):
            texto = obter_rotulo()
            if texto:
                achados.append(texto)
        dica = widget.get_tooltip_text()
        if dica:
            achados.append(dica)
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        obter_filhos = getattr(widget, "get_children", None)
        if obter_filhos is not None:
            pilha.extend(obter_filhos())
    return achados
