#!/usr/bin/env python3
"""O trilho que ela está arrastando não é repintado por baixo do dedo.

A QUEIXA É DELA, 09/09/2026, com o produto aberto: *"o slicer do brilho tá
super estranho"*, *"oscila, aplica e não aplica"*.

O DEFEITO, e ele é do MOTOR, não da aba
----------------------------------------
O trilho do brilho carrega ``data-campo="brilho-pct"`` com alvo ``valor``, e o
tique do piloto repinta ``el.value`` dez vezes por segundo com o número que
está NO DISCO. O gesto só grava no ``change`` — ou seja, no SOLTAR. Entre o
primeiro milímetro do arraste e o soltar, cada tique devolve o polegar para
onde ele estava:

    ela arrasta para 60   →   tique (100 ms)   →   el.value = 82   (o do disco)
    ela arrasta para 61   →   tique            →   el.value = 82
    ela solta em 63       →   `change`         →   grava 63

«Oscila, aplica e não aplica» descreve isso com precisão: aplica no soltar, e
não aplica no caminho.

A CURA é a guarda ``sob_o_dedo`` no BOOTSTRAP (``hefesto_vivo.py``), nos dois
alvos que escrevem em controle de formulário — ``valor`` e ``marcado``.

O QUE ESTE INSTRUMENTO MEDE, e ele traz a própria mordida
----------------------------------------------------------
Dois casos no mesmo trilho, sem tocar no fonte:

    SEM FOCO   escreve-se um valor diferente e ninguém segura o campo.
               O pintor DEVE sobrescrever. Se ele não sobrescrever, a régua
               está medindo um campo morto e o outro caso não valeria nada.
    COM FOCO   o mesmo valor, com o campo focado (é o que o arraste faz).
               O pintor NÃO pode sobrescrever.
    SOLTANDO   tira-se o foco e espera-se: o valor do disco volta, o que prova
               que a guarda ADIA e não MATA a pintura.

Os três têm de casar. Um sozinho não decide nada.

Porta: nenhuma — o daemon é de mentira (`_Gravador`), e o disco dela não é
tocado. Escreve no aparelho? NÃO.

USO
    o_trilho_sob_o_dedo_nao_e_repintado.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.interface.pacotes import ponte

ABA = "04-iluminacao.html"  # (noqa-acento) nome de arquivo

#: Um valor que o disco não vai ter, para a leitura não confundir os dois.
MEU_VALOR = "37"

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)

_ACHAR = """
  const t = document.querySelector('input.puxador[data-campo="brilho-pct"]');
  if(!t){ return JSON.stringify({erro: 'NAO ACHEI O TRILHO DO BRILHO'}); }
"""

SEM_FOCO = "(function(){" + _ACHAR + f"""
  t.blur();
  const disco = t.value;
  t.value = '{MEU_VALOR}';
  return JSON.stringify({{disco: disco, pus: t.value}});
}})()"""

COM_FOCO = "(function(){" + _ACHAR + f"""
  t.focus();
  t.value = '{MEU_VALOR}';
  return JSON.stringify({{focado: document.activeElement === t, pus: t.value}});
}})()"""

LER = "(function(){" + _ACHAR + """
  return JSON.stringify({valor: t.value, focado: document.activeElement === t});
})()"""

SOLTAR = "(function(){" + _ACHAR + """
  t.blur();
  return JSON.stringify({focado: document.activeElement === t});
})()"""


class _Gravador:
    """O daemon de mentira. Ele existe para o daemon DELA não ser tocado."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def __call__(self, metodo: str, timeout: float | None = None,
                 **params: object) -> dict:
        self.chamadas.append((metodo, dict(params)))
        return {}


def main() -> int:
    ponte.resultado = _Gravador()  # type: ignore[assignment]
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {}

    def perguntar(js: str, chave: str, depois=None):
        def anotou(texto: str | None, erro: Exception | None) -> None:
            saida[chave] = json.loads(texto) if texto and not erro else None
            if erro:
                saida[chave + "-erro"] = str(erro)
            if depois is not None:
                depois()

        def passo() -> bool:
            if not piloto.pronto:
                return True
            piloto.ponte.perguntar(js, anotou)
            return False

        return passo

    # A ORDEM É O ENSAIO. Entre um passo e o seguinte cabem vários tiques — é
    # justamente disso que se trata.
    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3000, perguntar(SEM_FOCO, "sem-foco"))
    GLib.timeout_add(5000, perguntar(LER, "sem-foco-depois"))
    GLib.timeout_add(6000, perguntar(COM_FOCO, "com-foco"))
    GLib.timeout_add(8000, perguntar(LER, "com-foco-depois"))
    GLib.timeout_add(9000, perguntar(SOLTAR, "soltar"))
    GLib.timeout_add(11000, perguntar(LER, "soltou-depois", Gtk.main_quit))
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    for chave in ("sem-foco", "sem-foco-depois", "com-foco", "com-foco-depois",
                  "soltar", "soltou-depois"):
        if saida.get(chave) is None:
            print(f"INCONCLUSIVO: o passo {chave!r} não respondeu "
                  f"({saida.get(chave + '-erro', 'sem erro')})")
            return 2
        if isinstance(saida[chave], dict) and saida[chave].get("erro"):  # type: ignore[union-attr]
            print(f"INCONCLUSIVO: {saida[chave]['erro']}")  # type: ignore[index]
            return 2

    disco = str(saida["sem-foco"]["disco"])            # type: ignore[index]
    sem = str(saida["sem-foco-depois"]["valor"])       # type: ignore[index]
    com = str(saida["com-foco-depois"]["valor"])       # type: ignore[index]
    solto = str(saida["soltou-depois"]["valor"])       # type: ignore[index]

    print(f"\n  o disco dizia ............ {disco}")
    print(f"  SEM foco, pus {MEU_VALOR} e esperei .... {sem}"
          f"   {'(o pintor sobrescreveu — o campo está VIVO)' if sem != MEU_VALOR else '(NÃO sobrescreveu)'}")
    print(f"  COM foco, pus {MEU_VALOR} e esperei .... {com}"
          f"   {'(a guarda segurou)' if com == MEU_VALOR else '(SOBRESCREVEU sob o dedo dela)'}")
    print(f"  soltei e esperei ......... {solto}"
          f"   {'(a pintura voltou)' if solto != MEU_VALOR else '(NÃO voltou — a guarda MATOU o campo)'}")

    vivo = sem != MEU_VALOR
    segurou = com == MEU_VALOR
    voltou = solto != MEU_VALOR
    print()
    if not vivo:
        print("INCONCLUSIVO: sem foco o pintor também não escreveu. A régua "
              "está medindo um campo morto, e o caso COM FOCO não prova nada.")
        return 2
    if not segurou:
        print("REPROVA: o trilho foi repintado com o campo focado. É o defeito "
              "que ela viu — o polegar volta sozinho no meio do arraste.")
        return 1
    if not voltou:
        print("REPROVA: depois de soltar, o valor do disco não voltou. A guarda "
              "ADIA a pintura; se ela a MATA, a tela para de dizer a verdade.")
        return 1
    print("PASSA: sob o dedo o trilho é dela; solto, ele volta a ser do disco.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
