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

A mesma aba colhe **189** textos num processo solto e **186** sob a suíte: as
três frases do censo do gabinete saem de um arquivo que o `install.sh` grava
sob o `HOME`, e o `conftest` desvia o `HOME` e os quatro `XDG_*` para um lar de
mentira. Um número cravado aqui mediria a BANCADA, não o produto — que é a
família de defeito que esta casa persegue. Por isso a régua cobra as frases que
somem e um PISO, nunca a igualdade.

**MAS A FOLGA DO PISO TEM TAMANHO, e ele é o dos 3 acima.** Um piso frouxo o
bastante é a mesma mentira em letra menor: ele valeu 175 contra uma colheita de
186, e uma seção cortada a menos da metade passava por ele. Ver
`FRASES_DO_CENSO_DO_GABINETE` e `PISO_DA_COLHEITA`.

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

#: Quanto o censo do gabinete acrescenta à colheita, e ele é a ÚNICA diferença
#: medida entre os dois ambientes: a contagem que a SMBIOS declara, a que o
#: barramento entrega, e a pergunta que a divergência entre as duas abre. As
#: três moram na seção "Conexões", saem do `gabinete.json` que o `install.sh`
#: grava sob o `HOME`, e o `conftest` desvia o `HOME` e os quatro `XDG_*` para
#: um lar de mentira — então **a suíte nunca as vê**.
#:
#: Conferido nos dois sentidos em 08/09/2026: 189 num processo solto, 186 sob a
#: suíte, e a colheita solta repetida sob um lar VAZIO devolve os mesmos 186 —
#: o que prova que o censo é o mecanismo inteiro, e não um dos vários.
FRASES_DO_CENSO_DO_GABINETE = 3

#: PISO da colheita, e ele é piso e não igualdade: com o censo no lugar a mesma
#: aba colhe `FRASES_DO_CENSO_DO_GABINETE` textos a mais.
#:
#: **A FOLGA DELE É A DIFERENÇA ENTRE OS DOIS AMBIENTES, E ESTÁ TODA GASTA** —
#: 189 solto menos as 3 do censo dá os 186 que a suíte vê, e é aqui que ele
#: para. Ele valeu 175 até 08/09/2026, contra uma colheita de 186: onze de
#: folga que ambiente nenhum explicava, e o preço disso foi medido, não
#: deduzido. Cortada a seção "Está tudo certo?" de 20 textos para 9, a aba caiu
#: a exatos 175 e as quatro réguas deste arquivo deram `4 passed`, `rc=0`: uma
#: seção perdendo 55% do conteúdo atravessava os dois pisos em silêncio.
#: `test_a_folga_do_piso_tem_tamanho_medido` passa a cobrar o tamanho da folga,
#: e é ela que reprova um piso comprado de novo.
#:
#: A RAZÃO QUE ESTAVA ESCRITA AQUI CAIU NA MEDIÇÃO, e fica registrada para
#: ninguém a rederivar: ela dizia que os textos que faltavam saíam da seção "Os
#: controles" por não haver controle na mesa. Não é o que acontece.
#: `HospedeiroDaAbaConfig` não tem `_controles_leitor`, e o pedido que sobra
#: (`daemon.state_full`) é assíncrono — a colheita é tomada antes de qualquer
#: resposta poder chegar. Medido em 08/09/2026 com QUATRO DualSense adotados na
#: mesa: a seção montou os mesmos 8 textos, dizendo "Nenhum controle ligado
#: agora". **A colheita não enxerga a mesa**, e é por isso que o número acima é
#: estável o bastante para ser cobrado sem folga.
PISO_DA_COLHEITA = 186

#: Piso POR MOLDURA. A menor é "Os controles", com 8, e ela não cresce com a
#: mesa (ver acima); abaixo disto a seção montou oca, que é o defeito que o
#: berço pode causar sem levantar exceção nenhuma.
#:
#: ELE NÃO SUBSTITUI O TOTAL, e a medição acima é a prova: a seção do exame
#: cortada de 20 para 9 passa por aqui com folga de três, e quem a pega é o
#: `PISO_DA_COLHEITA`. Os dois cobram defeitos diferentes — este, a seção que
#: sobe oca; aquele, a seção que perde metade sem esvaziar.
PISO_POR_SECAO = 6


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
