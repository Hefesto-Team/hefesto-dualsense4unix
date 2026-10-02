#!/usr/bin/env python3
"""A TELA NÃO FICA NUA — a régua que vive no TEMPO, e a mordida que a prova."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))
sys.path.insert(0, str(_RAIZ / "src"))

_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[2] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

import hefesto_vivo as hv

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
    """Os PIDs FILHOS deste processo, com o comando inteiro."""
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
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=a.abre, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=False,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)

    if a.sem_cura:
        from hefesto_dualsense4unix.interface import janela as ponte_da_tela

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

    GLib.timeout_add(400, lambda: piloto._ir(a.abre))
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
        print(f"VEREDITO: VERMELHO — a página não respondeu em {', '.join(mudas)}")
        return 1
    print(f"VEREDITO: VERDE — {len(leituras)} leituras, a folha viva em todas "
          f"(fundo {leituras[-1]['fundo']}, {leituras[-1]['letrasDeEstilo']} "
          f"letras de estilo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
