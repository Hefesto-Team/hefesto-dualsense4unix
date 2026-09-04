#!/usr/bin/env python3
"""A linha fechada da Gestão de Controles, medida DENTRO do WebKit dela.

POR QUE ELE EXISTE, e é a regra desta casa: o teste de unidade
``test_a_linha_fechada_da_aba08_segue_o_aparelho`` prova que o **pacote emite**
e que a **bancada tem endereço**. Isso prova a CONTA. O que prova o PRODUTO é o
mesmo valor chegando ao elemento certo dentro do ``WebKit2.WebView`` que ela
usa, com a folha de estilo real aplicando o ``apagado`` — porque o que ela vê
não é uma chave de dicionário, é um botão apagado e a palavra "Desligado".

O ENSAIO LÊ A **BANCADA**, e não a página publicada. É de propósito e está
declarado: os endereços desta leva nasceram em ``mockup/08-conexoes.html`` e só
alcançam a tela dela depois do ``--publicar``, que é ato de quem coordena.
Apontar para o publicado daria **não-achado convincente** — a armadilha mais
cara do ``docs/process/COMO-OLHAR-A-TELA.md``. O desvio é de PROCESSO
(``onde.PUBLICADO`` desta execução), nunca de disco: nenhum arquivo é copiado.

O QUE ELE MEDE, com o daemon VIVO e a mesa como ela estiver:

1. o **antes** — o que o arquivo da bancada traz cravado naquele elemento;
2. o **depois** — o que o DOM mostra depois de o piloto pintar;
3. e reprova quando os dois são iguais em TODO campo, porque aí a pintura não
   está acontecendo e o verde seria sobre o desenho.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/a_linha_fechada_da_08_no_webkit.py
    scripts/ensaios/a_linha_fechada_da_08_no_webkit.py --foto /tmp/depois.png
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
# Ela pediu duas vezes em 04/09/2026; o `park` do workspace chega tarde,
# porque move a janela DEPOIS de ela existir. Escape: HEFESTO_NA_TELA=1.
_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[2] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo, onde

ABA = "08-conexoes.html"

#: O QUE SE LÊ DO DOM. Cada linha é um campo desta leva, e o seletor é o do
#: DESENHO — quem mudar o desenho e não este ensaio verá `null` e saberá.
ROTEIRO = r"""
(function(){
  function um(raiz, campo){
    const el = raiz.querySelector('[data-campo="' + campo + '"]');
    if(!el) return null;
    return {texto: (el.textContent || '').trim(),
            titulo: el.getAttribute('title'),
            classes: el.className,
            visto: el.dataset.hefVisto || null};
  }
  const saida = {controles: {}, confissao: null};
  for(const raiz of document.querySelectorAll('[data-controle]')){
    const pref = raiz.dataset.controle;
    const botao = raiz.querySelector('[data-campo="luz-trava"]');
    saida.controles[pref] = {
      conectado: raiz.dataset.conectado || null,
      nome: um(raiz, 'nome'),
      mic_existe: um(raiz, 'mic-existe'),
      mic_caminho: um(raiz, 'mic-caminho'),
      luz: botao === null ? null : {apagado: botao.classList.contains('apagado'),
                                   visto: botao.dataset.hefVisto || null}
    };
  }
  const linha = document.querySelector('[data-campo="confissao-nada"]');
  if(linha){
    saida.confissao = {
      sumido: linha.classList.contains('sumido'),
      conta: um(linha, 'confissao-conta'),
      dica: um(linha, 'confissao-dica')
    };
  }
  return JSON.stringify(saida);
})()
"""

BANDEIRAS = dict(oculta=True, segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _do_arquivo() -> dict[str, str]:
    """O ANTES — o que a bancada crava, lido do arquivo e não do DOM.

    Ele tem de vir do arquivo: depois da primeira pintura o DOM já é a mistura
    do que o desenho escreveu com o que o produto reescreveu, e não há como
    desfazer a mistura olhando o resultado.
    """
    import re

    html = onde.pagina(ABA).read_text(encoding="utf-8")
    cravado: dict[str, str] = {}
    for campo in ("mic-existe", "mic-caminho", "confissao-conta"):
        achados = re.findall(
            rf'data-campo="{campo}"[^>]*>(.*?)<', html, flags=re.S)
        cravado[campo] = " · ".join(a.strip() for a in achados)
    return cravado


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--foto", default="", help="grava um PNG da janela oculta")
    escolha = ap.parse_args()

    # O DESVIO DE PROCESSO — a razão está no cabeçalho. Nada é copiado no disco;
    # esta execução passa a ler as páginas da bancada, e só ela.
    onde.PUBLICADO = onde.BANCADA

    antes = _do_arquivo()
    args = argparse.Namespace(**BANDEIRAS, abre=ABA, foto=escolha.foto)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {"dom": None, "erro": ""}

    def perguntar() -> bool:
        if not piloto.pronto:
            return True

        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida["dom"] = json.loads(texto) if texto and not erro else None
            saida["erro"] = str(erro) if erro else ""
            # A FOTO SAI DAQUI, e não do `--foto` do piloto: aquele é tirado no
            # `_relatar`, que só roda no fim do passeio (`--segundos`). Este
            # ensaio fecha a janela assim que lê o DOM, e a foto tem de ser do
            # MESMO instante que a leitura — senão as duas contam coisas
            # diferentes.
            if escolha.foto:
                piloto.tela.fotografar(escolha.foto)
            Gtk.main_quit()

        piloto.ponte.perguntar(ROTEIRO, respondeu)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    # DOIS TIQUES DE FOLGA (o tique é de 500 ms): o exame de entrada corre em
    # thread, e a primeira pintura pode chegar antes de ele voltar.
    GLib.timeout_add(4000, perguntar)
    GLib.timeout_add(30000, Gtk.main_quit)
    Gtk.main()

    dom = saida.get("dom")
    if not dom:
        print(f"REPROVA: não li o DOM da {ABA}. {saida.get('erro', '')}")
        return 1

    print(f"ANTES (o que a bancada crava): {antes}")
    print()
    for pref, d in sorted(dom["controles"].items()):
        print(f"  {pref}  conectado={d['conectado']!r}")
        for chave in ("nome", "mic_existe", "mic_caminho"):
            v = d[chave]
            marca = "" if v is None else ("  [pintado]" if v.get("visto") else "  [NÃO visitado]")
            print(f"        {chave:12s} {v if v is None else v['texto']!r}{marca}")
        print(f"        luz          {d['luz']}")
    print(f"\n  confissão   {dom['confissao']}")

    # A GUARDA DE VACUIDADE: pelo menos um campo desta leva tem de ter sido
    # VISITADO pelo piloto. Sem ela, uma página que o produto nunca alcançou
    # imprimiria os valores do desenho e o ensaio pareceria verde.
    visitados = [f"{pref}.{chave}"
                 for pref, d in dom["controles"].items()
                 for chave in ("mic_existe", "mic_caminho")
                 if d[chave] and d[chave].get("visto")]
    if dom["confissao"] and (dom["confissao"]["conta"] or {}).get("visto"):
        visitados.append("confissao-conta")
    if not visitados:
        print("\nREPROVA: nenhum campo desta leva foi visitado pelo piloto — "
              "ou os endereços sumiram da bancada, ou o pacote parou de emitir.")
        return 1

    print(f"\nOK: {len(visitados)} campo(s) desta leva visitados pelo produto "
          f"— {', '.join(sorted(visitados))}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
