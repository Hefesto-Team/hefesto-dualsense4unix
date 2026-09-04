#!/usr/bin/env python3
"""A TELA NÃO FICA NUA — a régua que vive no TEMPO, e a mordida que a prova.

> **Ela, 04/09/2026, 12h15, com foto:** *"interface quebrou sozinha oxi"*.

A aba Gatilhos do piloto, sem estilo nenhum: `h1` de navegador, as dez abas como
links sublinhados, o conteúdo encostado na borda. **Sem clique dela** — estava
vestida e ficou nua.

POR QUE ELE VIVE VINTE MINUTOS, e não é zelo: **uma régua que roda o tique uma
vez mede um INSTANTE, não um comportamento.** Em 29/08 uma leva introduziu uma
regressão que só aparecia aos **181 segundos**, com 67 testes verdes ao lado. O
que esta página cobra não acontece no primeiro minuto — se acontecesse, a foto
dela seria a foto da abertura.

O QUE ELE LÊ, a cada minuto, e por que é este número:

    getComputedStyle(document.body).backgroundColor

Com a folha viva, o corpo é `rgb(17, 18, 26)` — o `--bg` do `topo.html`. Com a
folha morta, o navegador devolve `rgba(0, 0, 0, 0)`, que é o fundo de um `body`
sem uma regra sequer. **É o sinal mais barato que separa vestida de nua**, e ele
não depende de nenhuma aba: as dez herdam o mesmo esqueleto.

E ele lê MAIS TRÊS COISAS, porque `backgroundColor` sozinho tem um ponto cego —
uma página que morreu CONGELADA continua devolvendo a última cor:

===========================  =================================================
o que                        o que ele denuncia
===========================  =================================================
``letrasDeEstilo``           a ``<style>`` inline sumindo do documento
``styleSheets``              a folha caindo do CSSOM sem a tag sumir
o JS **respondendo**         o processo web morto — aí a leitura não volta, e
                             silêncio de instrumento é indistinguível de
                             ausência de defeito
===========================  =================================================

AS DUAS MORDIDAS, e as duas são de quem escreve, não de quem confere:

    --matar-aos 90        mata o ``WebKitWebProcess`` FILHO aos 90 s, **por PID
                          conferido com `ps -o pid,ppid,cmd`**. Nunca por padrão
                          de nome: um ``pkill -f`` casou com o compositor DELA em
                          04/09, a tela caiu e a sessão morreu com ela.
    --sem-cura            arranca a recarga do produto. Com ela, o ensaio tem de
                          REPROVAR — e se continuar verde, ele não mede nada.

O QUE A MEDIÇÃO DE 04/09 JÁ DERRUBOU, para ninguém remedir: matar o
``WebKitNetworkProcess`` e recarregar **não** deixa a página nua (a folha é
inline; o ``<link>`` do Google só traz fonte), e as dez páginas publicadas não
foram reescritas no disco no dia da foto — `03-gatilhos.html` é de 04/09 02:54,
nove horas antes.

USO:

    scripts/ensaios/a_tela_nao_fica_nua.py                     # os 20 min
    scripts/ensaios/a_tela_nao_fica_nua.py --minutos 3 --intervalo 20
    scripts/ensaios/a_tela_nao_fica_nua.py --minutos 3 --matar-aos 60
    scripts/ensaios/a_tela_nao_fica_nua.py --minutos 3 --matar-aos 60 --sem-cura

A janela nasce SEMPRE oculta: ela tem UMA tela, e janela que aparece na frente
dela quebra o que ela está fazendo.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA — a armadilha que oito arquivos desta
# casa já pagaram quando a pasta mudou de nome.
_RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))
sys.path.insert(0, str(_RAIZ / "src"))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

import hefesto_vivo as hv  # noqa: E402

#: O fundo de um ``body`` que perdeu toda regra de estilo. É a assinatura da
#: tela nua, e o WebKit a devolve com este espaçamento exato.
NUA = "rgba(0, 0, 0, 0)"

MEDIR = r"""
(function(){
  const cs = getComputedStyle(document.body);
  const estilos = document.querySelectorAll('style');
  let letras = 0;
  for(const s of estilos) letras += (s.textContent||'').length;
  return JSON.stringify({
    fundo: cs.backgroundColor,
    padding: cs.padding,
    styleTags: estilos.length,
    letrasDeEstilo: letras,
    styleSheets: document.styleSheets.length,
    campos: document.querySelectorAll('[data-campo],[data-papel],[data-hef]').length,
    temHef: !!(window.__hef && window.__hef.pintar),
    uri: location.href.split('/').pop(),
  });
})()
"""


def filhos_deste_processo() -> list[tuple[int, str]]:
    """Os PIDs FILHOS deste processo, com o comando inteiro.

    **A régua é o parentesco, nunca o nome.** Casar um padrão contra a tabela de
    processos da máquina dela é como se derruba um compositor: em 04/09 um
    ``pkill -f 'cosmic-comp'`` casou com o processo DELA e a sessão morreu.
    Aqui só entra quem tem este processo como pai.
    """
    saida = subprocess.run(["ps", "-eo", "pid,ppid,cmd", "--no-headers"],
                           capture_output=True, text=True).stdout
    fora: list[tuple[int, str]] = []
    for linha in saida.splitlines():
        partes = linha.split(None, 2)
        if len(partes) >= 3 and partes[1].strip() == str(os.getpid()):
            fora.append((int(partes[0]), partes[2]))
    return fora


def matar_o_processo_web() -> list[int]:
    """Mata o ``WebKitWebProcess`` filho, conferindo cada PID antes do sinal."""
    alvos = [p for p, cmd in filhos_deste_processo() if "WebKitWebProcess" in cmd]
    for pid in alvos:
        conferido = subprocess.run(["ps", "-o", "pid=,ppid=,cmd=", "-p", str(pid)],
                                   capture_output=True, text=True).stdout.strip()
        print(f"[mordida] conferido antes do sinal: {conferido}")
        os.kill(pid, 9)
    if not alvos:
        print("[mordida] nenhum WebKitWebProcess filho — nada a matar")
    return alvos


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minutos", type=float, default=20.0,
                   help="quanto tempo a janela fica de pé (padrão: 20)")
    p.add_argument("--intervalo", type=float, default=60.0,
                   help="segundos entre uma leitura e a próxima (padrão: 60)")
    p.add_argument("--abre", default="03-gatilhos.html",
                   help="a aba a vigiar — a da foto dela, por omissão")
    p.add_argument("--passear", action="store_true",
                   help="troca de aba entre as leituras, para exercitar as dez")
    p.add_argument("--matar-aos", type=float, default=0.0,
                   help="MORDIDA: mata o WebKitWebProcess FILHO neste segundo")
    p.add_argument("--sem-cura", action="store_true",
                   help="MORDIDA: arranca a recarga do produto. O ensaio TEM de "
                        "reprovar — se ficar verde, ele não mede nada")
    a = p.parse_args()

    args = argparse.Namespace(
        # OCULTA SEMPRE, e não é uma flag: ela tem UMA tela.
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=a.abre, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=False,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)

    if a.sem_cura:
        # A MORDIDA ARRANCA A CURA DO PRODUTO, e arranca no lugar certo: quem
        # recarrega é a JANELA. Zerar o teto faz o `_morreu_a_pagina` desistir
        # na primeira morte, que é exatamente o estado de antes desta frente.
        from hefesto_dualsense4unix.gui import ponte_da_tela

        ponte_da_tela.RECARGAS_SEGUIDAS = 0
        piloto.tela.recargas = 0
        print("[mordida] --sem-cura: a janela NÃO vai recarregar")

    leituras: list[dict[str, object]] = []
    nuas: list[str] = []
    mudas: list[str] = []
    t0 = time.monotonic()
    fim_em = a.minutos * 60.0
    abas = sorted(hv.pacotes.PACOTES) if a.passear else []
    estado = {"proxima_aba": 0, "matou": False}

    def carimbo() -> str:
        s = time.monotonic() - t0
        return f"{int(s // 60):02d}:{int(s % 60):02d}"

    def leu(valor: object, erro: object) -> None:
        quando = carimbo()
        if erro is not None:
            # O INSTRUMENTO MUDO É UM ACHADO, e não uma falha de medição: com o
            # processo web morto o JS não volta, e ler isso como "não houve
            # defeito" é a armadilha que esta casa chama de *silêncio de
            # instrumento morto*.
            mudas.append(quando)
            print(f"[{quando}] A PÁGINA NÃO RESPONDEU — {erro}")
            return
        try:
            d = json.loads(str(valor))
        except ValueError as e:
            mudas.append(quando)
            print(f"[{quando}] a leitura não veio em JSON — {e}")
            return
        d["quando"] = quando
        leituras.append(d)
        nu = d.get("fundo") == NUA or int(d.get("letrasDeEstilo") or 0) == 0
        if nu:
            nuas.append(quando)
        print(f"[{quando}] {d['uri']:<20} fundo={d['fundo']:<18} "
              f"padding={d['padding']:<8} style={d['styleTags']} "
              f"letras={d['letrasDeEstilo']} folhas={d['styleSheets']} "
              f"campos={d['campos']} hef={d['temHef']}"
              + ("   <<< NUA" if nu else ""))

    def bater() -> bool:
        if time.monotonic() - t0 >= fim_em:
            Gtk.main_quit()
            return False
        piloto.ponte.perguntar(MEDIR, leu)
        if abas:
            piloto._ir(abas[estado["proxima_aba"] % len(abas)])
            estado["proxima_aba"] += 1
        return True

    def morder() -> bool:
        if estado["matou"]:
            return False
        estado["matou"] = True
        print(f"[{carimbo()}] [mordida] matando o processo web...")
        matar_o_processo_web()
        return False

    # A ABA PEDIDA, e ela é a da FOTO dela. O `--abre` do piloto só é lido no
    # `main()` do produto; aqui quem navega é o ensaio.
    GLib.timeout_add(400, lambda: piloto._ir(a.abre))
    # A PRIMEIRA LEITURA É CEDO, e ela é a LINHA DE BASE: sem ela, uma página que
    # já nasce nua sai do ensaio indistinguível de uma que ficou nua no caminho.
    GLib.timeout_add(3000, lambda: (bater(), False)[1])
    GLib.timeout_add(int(a.intervalo * 1000), bater)
    if a.matar_aos > 0:
        GLib.timeout_add(int(a.matar_aos * 1000), morder)
    guarda = GLib.timeout_add(int(fim_em * 1000) + 5000, Gtk.main_quit)

    print(f"a_tela_nao_fica_nua — {a.minutos:g} min, uma leitura a cada "
          f"{a.intervalo:g} s, aba {a.abre}"
          + (" (passeando)" if a.passear else ""))
    print(f"python: {sys.executable}")
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()

    print()
    print(f"leituras            : {len(leituras)}")
    print(f"mortes da página    : {len(piloto.tela.mortes)} {piloto.tela.mortes}")
    print(f"recargas            : {piloto.tela.recargas}")
    if not leituras and not mudas:
        print("VEREDITO: INCONCLUSIVO — nenhuma leitura voltou. O ensaio não "
              "mediu nada, e isso não é um verde.")
        return 2
    if nuas:
        print(f"VEREDITO: VERMELHO — a folha morreu em {', '.join(nuas)}")
        return 1
    if mudas:
        # A PÁGINA MUDA CONTA COMO VERMELHO, e ela é o defeito de 04/09 em
        # pessoa: com o processo web morto e sem a cura, o JS falha para sempre
        # e a tela fica congelada. Ler isso como "não houve defeito" seria o
        # instrumento morto sendo confundido com ausência de defeito.
        print(f"VEREDITO: VERMELHO — a página não respondeu em {', '.join(mudas)}")
        return 1
    print(f"VEREDITO: VERDE — {len(leituras)} leituras, a folha viva em todas "
          f"(fundo {leituras[-1]['fundo']}, {leituras[-1]['letrasDeEstilo']} "
          f"letras de estilo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
