#!/usr/bin/env python3
"""Clica "Parar o serviço" NO PRODUTO VIVO e mede a pergunta — sem parar nada.

POR QUE ELE EXISTE, e é a regra desta casa: os testes de unidade provam a CONTA
do consentimento em dois cliques (`tests/unit/test_a_09_sistema_confirma_em_dois_
cliques.py`, com o `_invoke_systemctl` dublado). O que prova o PRODUTO é o mesmo
clique dentro do ``WebKit2.WebView`` que ela usa, com o daemon vivo e a folha de
estilo real — porque o que ela vê não é um dicionário, é a palavra no botão.

ELE NÃO PARA O DAEMON DELA, e essa é a garantia inteira: o PRIMEIRO clique arma,
e é só ele que este ensaio dá. O segundo — o único que manda `stop` — nunca é
disparado aqui; o ensaio confere, ao contrário, que o systemd **não** foi tocado,
lendo o `MainPID` da unit antes e depois.

Os quatro tempos:

1. lê o rótulo do botão como o desenho o deixou;
2. clica UMA vez, e relê — tem de dizer "Confirma?";
3. espera a janela do consentimento passar (`a09_sistema.segundos_para_confirmar`
   — perguntada, nunca digitada) e relê: o TIQUE tem de ter reposto o rótulo;
4. confere que o `MainPID` do daemon é o mesmo do começo.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_botao_pergunta_antes_de_parar.py
    scripts/ensaios/o_botao_pergunta_antes_de_parar.py --foto /tmp/armado.png
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.interface.pacotes import a09_sistema

ABA = a09_sistema.PAGINA
SELETOR = '[data-gesto="desligar"]'

#: LER O BOTÃO, e nada mais — este roteiro não clica. Quem clica é o
#: `document.querySelector(...).click()`, disparado uma vez só, no tempo 2.
LER = f"""
(function(){{
  const el = document.querySelector('{SELETOR}');
  if(!el) return JSON.stringify(null);
  return JSON.stringify({{rotulo: (el.textContent || '').trim(),
                         classe: el.className}});
}})()
"""

CLICAR = f"document.querySelector('{SELETOR}').click(); 'ok'"

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _main_pid() -> str:
    """O `MainPID` da unit — a prova de que NADA foi parado.

    A unit não se digita: sai de `a09_sistema._unidade()`, que a pede ao dono
    (`daemon/service_install.SERVICE_NORMAL`).
    """
    try:
        r = subprocess.run(
            ["systemctl", "--user", "show", "-p", "MainPID", "--value",
             a09_sistema._unidade()],
            capture_output=True, text=True, timeout=5)
        return (r.stdout or "").strip()
    except Exception as erro:  # pragma: no cover - sem sessão systemd
        return f"?({erro})"


def main() -> int:
    corta = argparse.ArgumentParser(description=__doc__)
    corta.add_argument("--foto", default="", help="PNG do momento ARMADO")
    escolha = corta.parse_args()

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    saida: dict[str, object] = {}
    espera = a09_sistema.segundos_para_confirmar()

    def ler(chave: str, depois=None):
        def passo() -> bool:
            if not piloto.pronto:
                return True

            def respondeu(texto: str | None, erro: Exception | None) -> None:
                saida[chave] = json.loads(texto) if texto and not erro else None
                if erro:
                    saida[f"{chave}-erro"] = str(erro)
                if depois is not None:
                    depois()

            piloto.ponte.perguntar(LER, respondeu)
            return False
        return passo

    def clicar() -> bool:
        piloto.ponte.perguntar(CLICAR, lambda *_: None)
        return False

    def fotografar() -> bool:
        if escolha.foto:
            piloto.tela.fotografar(escolha.foto)
        return False

    # OS TEMPOS SÃO MEDIDOS, NÃO CHUTADOS — 03/09/2026, nesta máquina: uma volta
    # de `ponte.perguntar` leva ~2,5 s (o `run_javascript` do WebKit espera o
    # laço do GTK, que está pintando a cada 500 ms). A primeira versão deste
    # ensaio lia 1,5 s depois do clique e REPROVOU a cura: o rótulo trocado só
    # chegou aos 2,3 s. É a armadilha do `COMO-OLHAR-A-TELA.md` — *régua que
    # pergunta cedo demais produz não-achado convincente*.
    CLIQUE_MS = 5000
    saida["pid-antes"] = _main_pid()
    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(2500, ler("desenho"))
    GLib.timeout_add(CLIQUE_MS, clicar)
    GLib.timeout_add(CLIQUE_MS + 3500, ler("armado"))
    GLib.timeout_add(CLIQUE_MS + 4500, fotografar)
    # O TIQUE TEM DE REPOR, e a espera é a do DONO do consentimento contada A
    # PARTIR DO CLIQUE, mais folga para duas voltas de leitura.
    GLib.timeout_add(CLIQUE_MS + int((espera + 5) * 1000), ler("reposto"))
    GLib.timeout_add(CLIQUE_MS + int((espera + 9) * 1000), Gtk.main_quit)
    Gtk.main()
    saida["pid-depois"] = _main_pid()

    for tempo in ("desenho", "armado", "reposto"):
        lido = saida.get(tempo)
        if not lido:
            print(f"REPROVA: não li o botão no tempo `{tempo}`. "
                  f"{saida.get(f'{tempo}-erro', '')}")
            return 1
        print(f"  {tempo:8s} rótulo={lido['rotulo']!r}")

    print(f"  MainPID  antes={saida['pid-antes']} · depois={saida['pid-depois']}")

    if saida["desenho"]["rotulo"] == a09_sistema.CONFIRMA:
        print("\nATENÇÃO: o botão já nasceu armado — este ensaio não prova nada "
              "assim. Rode-o num processo novo.")
        return 1
    if saida["armado"]["rotulo"] != a09_sistema.CONFIRMA:
        print(f"\nREPROVA: um clique não armou o botão — ele diz "
              f"{saida['armado']['rotulo']!r} e devia dizer "
              f"{a09_sistema.CONFIRMA!r}.")
        return 1
    if saida["reposto"]["rotulo"] != saida["desenho"]["rotulo"]:
        print(f"\nREPROVA: passados {espera:.0f}s o tique não repôs o rótulo — "
              f"o botão ficou em {saida['reposto']['rotulo']!r}. A tela mente "
              "sobre o estado.")
        return 1
    if saida["pid-antes"] != saida["pid-depois"] or saida["pid-antes"] in ("", "0"):
        print(f"\nREPROVA: o daemon mudou de PID (ou não estava de pé) — "
              f"{saida['pid-antes']} -> {saida['pid-depois']}. Um clique só NÃO "
              "pode parar nada.")
        return 1

    print(f"\nOK: um clique troca {saida['desenho']['rotulo']!r} por "
          f"{a09_sistema.CONFIRMA!r}, o tique repõe em {espera:.0f}s, e o daemon "
          f"dela continua no MainPID {saida['pid-antes']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
