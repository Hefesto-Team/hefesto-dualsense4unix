#!/usr/bin/env python3
"""o_painel_do_brilho.py — o `common[42]` num controle deslizante, nos dois aparelhos.

A ENCOMENDA É DELA, 09/09/2026: *"pode fazer um slicer pra eu controlar do
controle branco e do controle bt?"*

POR QUE ELE EXISTE, e a diferença para a escada
------------------------------------------------
O `o_brilho_de_hardware_da_barra.py` percorre 0 → 2 → 1 → 0 no relógio DELE, e
ela tem de estar olhando na hora certa. Este painel inverte o dono do tempo:
**ela mexe, ela compara, e os dois aparelhos ficam lado a lado** — que é a única
forma de responder "escureceu" sem depender de memória de oito segundos atrás.

A pergunta que os dois decidem é a mesma (BRILHO-DE-HARDWARE-01, decisão dela
*"2b"*): o `common[42]` (`led_brightness`, 0 alto · 1 médio · 2 baixo) escurece
a barra, e ele precisa do `flag2` bit0 que o kernel desta máquina não define?

O MARTELO, e por que ele é obrigatório no cabo
-----------------------------------------------
Quando o daemon é dono das luzes, cada report dele leva `common[42] = 0`: uma
escrita minha é desfeita antes de ela olhar. Cada aparelho tem aqui um martelo
a 10 Hz enquanto o painel vive. Se a barra PISCAR entre dois brilhos, isso é um
**sim** do firmware — é o daemon e eu disputando, e disputa só existe se o byte
age.

A TELA É DELA, DE PROPÓSITO
----------------------------
A guarda `tela_de_mentira` (TELA-DELA-02) desvia toda janela de `scripts/` para
um `Xvfb`. Aqui o escape é declarado, como no `validar.sh`: este painel só serve
se ela o vir. `--oculta` devolve o comportamento de instrumento, para régua
automática.

Porta: o broker (`escrita_pelo_broker.Escritor`), com o daemon VIVO.
Escreve no aparelho? SIM — cor, `common[42]` e `flag2` bit0.

USO
    o_painel_do_brilho.py                 # na tela dela, os controles que houver
    o_painel_do_brilho.py --oculta        # sem tela, para régua
"""

from __future__ import annotations

import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
_SRC = os.path.join(_RAIZ, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# O ESCAPE É DECLARADO, e a responsabilidade é de quem declara (TELA-DELA-02).
# Sem `--oculta`, esta janela é DELA e nasce na tela dela — é o ponto do painel.
if "--oculta" not in sys.argv:
    os.environ["HEFESTO_NA_TELA"] = "1"

from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gdk, Gtk

from comum import CABO
from escrita_pelo_broker import (
    Escritor,
    alvos_da_mesa,
    linha_do_caderno,
    mascarar,
)
from o_brilho_de_hardware_da_barra import (
    LINHA_DO_MAPA,
    NOME_DO_NIVEL,
    common_do_nivel,
)

#: O ritmo do martelo. 10 Hz é o do instrumento da escada, medido lá.
HZ = 10.0

#: Branco: o brilho é mais legível na cor mais clara que o aparelho faz.
COR_PADRAO = (255, 255, 255)


class Coluna:
    """Um aparelho no painel: a porta aberta, o martelo e os controles dela."""

    def __init__(self, alvo, ao_mudar) -> None:
        self.alvo = alvo
        self.ao_mudar = ao_mudar
        self.nivel = 0
        self.com_bit = True
        self.cor = COR_PADRAO
        self.escritas = 0
        self.erro: str | None = None
        self.piscando = 0
        self.escritor = Escritor(alvo)
        try:
            self.escritor.abrir()
        except Exception as erro:  # a porta é do broker; sem ela a coluna diz por quê
            self.erro = str(erro)

    # -- o fio ---------------------------------------------------------------
    def _common(self):
        return common_do_nivel(self.nivel, com_bit=self.com_bit, cor=self.cor)

    def bater(self) -> None:
        """Uma martelada. Chamada a `HZ` pelo laço do GTK."""
        if self.erro is not None:
            return
        try:
            if self.piscando > 0:
                self.piscando -= 1
                apagado = self.piscando % 6 < 3
                self.escritor.escrever(
                    common_do_nivel(0, com_bit=True, cor=(0, 0, 0) if apagado else (0, 90, 255))
                )
            else:
                self.escritor.escrever(self._common())
            self.escritas += 1
        except Exception as erro:
            self.erro = str(erro)

    def devolver(self) -> None:
        """O nível 0 com o bit — a base. O daemon reassume na próxima escrita dele."""
        self.nivel = 0
        self.com_bit = True
        self.cor = COR_PADRAO
        if self.erro is None:
            try:
                self.escritor.escrever(self._common())
            except Exception as erro:
                self.erro = str(erro)

    def fechar(self) -> None:
        self.devolver()
        self.escritor.fechar()

    # -- a tela --------------------------------------------------------------
    def montar(self) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        caixa.set_margin_top(12)
        caixa.set_margin_bottom(12)
        caixa.set_margin_start(14)
        caixa.set_margin_end(14)

        transporte = "CABO" if self.alvo.transporte == CABO else "RÁDIO"
        titulo = Gtk.Label()
        titulo.set_markup(f"<b>{transporte}</b>  ·  <tt>{mascarar(self.alvo.mac)}</tt>")
        titulo.set_xalign(0.0)
        caixa.pack_start(titulo, False, False, 0)

        qual = Gtk.Button(label="Qual é este?")
        qual.set_tooltip_text("Pisca a barra em azul três vezes, para achar o aparelho na mão.")
        qual.connect("clicked", self._piscar)
        caixa.pack_start(qual, False, False, 0)

        caixa.pack_start(Gtk.Separator(), False, False, 4)

        rotulo = Gtk.Label(label="Brilho de hardware")
        rotulo.set_xalign(0.0)
        caixa.pack_start(rotulo, False, False, 0)

        ajuste = Gtk.Adjustment(value=0, lower=0, upper=2, step_increment=1, page_increment=1)
        self.escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        self.escala.set_digits(0)
        self.escala.set_round_digits(0)
        self.escala.set_draw_value(False)
        self.escala.set_hexpand(True)
        for valor, texto in ((0, "ALTO"), (1, "MÉDIO"), (2, "BAIXO")):
            self.escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        self.escala.connect("value-changed", self._mudou_nivel)
        caixa.pack_start(self.escala, False, False, 0)

        linha_bit = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.chave = Gtk.Switch()
        self.chave.set_active(True)
        self.chave.set_tooltip_text(
            "O flag2 bit0 autoriza o byte. O kernel desta máquina não o define — "
            "desligue para ver se o firmware obedece mesmo sem autorização."
        )
        self.chave.connect("notify::active", self._mudou_bit)
        linha_bit.pack_start(Gtk.Label(label="Autorização do byte"), False, False, 0)
        linha_bit.pack_end(self.chave, False, False, 0)
        caixa.pack_start(linha_bit, False, False, 0)

        linha_cor = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        botao_cor = Gtk.ColorButton()
        botao_cor.set_rgba(Gdk.RGBA(1.0, 1.0, 1.0, 1.0))
        botao_cor.connect("color-set", self._mudou_cor)
        linha_cor.pack_start(Gtk.Label(label="Cor"), False, False, 0)
        linha_cor.pack_end(botao_cor, False, False, 0)
        caixa.pack_start(linha_cor, False, False, 0)

        self.estado = Gtk.Label()
        self.estado.set_xalign(0.0)
        self.estado.get_style_context().add_class("dim-label")
        caixa.pack_start(self.estado, False, False, 0)

        devolver = Gtk.Button(label="Devolver ao daemon")
        devolver.connect("clicked", lambda *_: self._devolver_da_tela())
        caixa.pack_start(devolver, False, False, 0)

        self.pintar()
        return caixa

    def _piscar(self, *_) -> None:
        self.piscando = int(HZ * 3)

    def _mudou_nivel(self, escala) -> None:
        self.nivel = round(escala.get_value())
        self.pintar()
        self.ao_mudar()

    def _mudou_bit(self, chave, *_) -> None:
        self.com_bit = chave.get_active()
        self.pintar()
        self.ao_mudar()

    def _mudou_cor(self, botao) -> None:
        rgba = botao.get_rgba()
        self.cor = (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        self.pintar()
        self.ao_mudar()

    def _devolver_da_tela(self) -> None:
        self.devolver()
        self.escala.set_value(0)
        self.chave.set_active(True)
        self.pintar()

    def pintar(self) -> None:
        if self.erro is not None:
            self.estado.set_markup(f"<span foreground='#c01c28'>sem porta: {self.erro}</span>")
            return
        self.estado.set_text(
            f"nível {self.nivel} · {NOME_DO_NIVEL[self.nivel]} · "
            f"autorização {'ligada' if self.com_bit else 'apagada'} · "
            f"{self.escritas} escritas"
        )


class Painel:
    def __init__(self, colunas: list[Coluna]) -> None:
        self.colunas = colunas
        self.janela = Gtk.Window(title="Brilho da barra de luz")
        self.janela.set_default_size(720, 420)
        self.janela.connect("destroy", self._fechar)

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.janela.add(raiz)

        aviso = Gtk.Label()
        aviso.set_markup(
            "<b>Mexa e olhe a barra.</b>  Se ela piscar entre dois brilhos, o byte age — "
            "é o daemon e este painel disputando."
        )
        aviso.set_line_wrap(True)
        aviso.set_margin_top(10)
        raiz.pack_start(aviso, False, False, 0)

        corpo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        corpo.set_homogeneous(True)
        for i, coluna in enumerate(colunas):
            if i:
                corpo.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
            corpo.pack_start(coluna.montar(), True, True, 0)
        raiz.pack_start(corpo, True, True, 0)

        raiz.pack_start(Gtk.Separator(), False, False, 0)
        rodape = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        rodape.set_margin_top(8)
        rodape.set_margin_bottom(10)
        rodape.set_margin_start(14)
        rodape.set_margin_end(14)
        self.nota = Gtk.Entry()
        self.nota.set_placeholder_text("O que eu vi (escreva com as suas palavras)")
        self.nota.set_hexpand(True)
        rodape.pack_start(self.nota, True, True, 0)
        gravar = Gtk.Button(label="Gravar o que eu vi")
        gravar.connect("clicked", lambda *_: self.propor_linhas())
        rodape.pack_start(gravar, False, False, 0)
        raiz.pack_start(rodape, False, False, 0)

        GLib.timeout_add(int(1000 / HZ), self._tique)

    def _tique(self) -> bool:
        for coluna in self.colunas:
            coluna.bater()
            coluna.pintar()
        return True

    def propor_linhas(self) -> None:
        """O painel NÃO conclui: imprime as linhas, e quem coordena as escreve."""
        nota = self.nota.get_text().strip()
        print("\nLINHAS PROPOSTAS PARA O CADERNO (docs/data/ensaios.csv):")
        for coluna in self.colunas:
            print(
                linha_do_caderno(
                    id=f"painel-do-brilho-nivel{coluna.nivel}-"
                    f"{'com' if coluna.com_bit else 'sem'}-bit-{time.strftime('%d%m')}",
                    linha_id=LINHA_DO_MAPA,
                    transporte="cabo" if coluna.alvo.transporte == CABO else "radio",
                    suspeito="o firmware obedece ao common[42] (3 níveis) — "
                    "e exige o flag2 bit0 que o kernel não define",
                    presente="sim" if coluna.com_bit else "não",
                    resultado="",
                    observado_por="olho-dela",
                    fonte="scripts/ensaios/o_painel_do_brilho.py",
                    nota=f"nível {coluna.nivel} ({NOME_DO_NIVEL[coluna.nivel]}), "
                    f"bit {'ligado' if coluna.com_bit else 'apagado'}, cor {coluna.cor}, "
                    f"martelo {HZ:g} Hz, {coluna.escritas} escritas; "
                    f"ela: {nota or '(sem resposta)'}",
                )
            )
        sys.stdout.flush()

    def _fechar(self, *_) -> None:
        for coluna in self.colunas:
            coluna.fechar()
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def abrir(self) -> None:
        self.janela.show_all()
        Gtk.main()


def main() -> int:
    aparelhos = alvos_da_mesa()
    if not aparelhos:
        print("nenhum DualSense físico encontrado. Plugue ou pareie e rode de novo.")
        return 1

    print(f"aparelhos: {', '.join(mascarar(a.mac) + ' ' + a.transporte for a in aparelhos)}")
    colunas = [Coluna(a, lambda: None) for a in aparelhos]
    painel = Painel(colunas)
    if "--oculta" in sys.argv:
        # Régua automática: monta, bate uma vez e sai sem entrar no laço do GTK.
        painel._tique()
        painel.propor_linhas()
        painel._fechar()
        return 0
    painel.abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
