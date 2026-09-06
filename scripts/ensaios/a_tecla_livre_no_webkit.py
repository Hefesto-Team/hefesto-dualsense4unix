#!/usr/bin/env python3
"""A tecla escrita À MÃO, digitada DENTRO do WebKit dela.

POR QUE ELE EXISTE, e é a regra da casa: *"Botão que você acrescentou e nunca
clicou não está entregue."* As réguas de unidade provam que o gerador emite os
oito campos e que o pacote os lê. O que prova o PRODUTO é ela DIGITAR uma
combinação que a lista de 26 não oferece, o texto chegar ao Python pelo ouvinte
do piloto, o "Guardar" gravar `Profile.key_bindings` no disco — e o ↺ da linha
AO LADO não levar o dela junto.

**A PÁGINA VEM DA BANCADA, e o desvio está declarado.** O piloto renderiza
`interface/paginas/` e esta frente **não publica** (a `06-navegacao.html`
publicada está no `nao_toca:` da sprint; a leva publica de uma vez no fecho, com
a palavra dela). Para que a prova exista, o ensaio monta um PUBLICADO de mentira
num diretório temporário — cópia de todas as páginas do produto, com a `06`
trocada pela da bancada — e aponta `onde.PUBLICADO` para lá. O que corre no
WebKit é, byte a byte, o HTML que o `--publicar 06` entregaria.

O HOME É DE MENTIRA, e isto não é zelo: `hefesto_vivo` dispara migrações
one-shot no `~/.config` REAL, e o "Guardar" desta aba grava no perfil ativo.
Rode sempre assim::

    LAR=$(mktemp -d)
    mkdir -p "$LAR/.config" "$LAR/.local/share" "$LAR/.cache" "$LAR/.local/state"
    cp -r ~/.config/hefesto-dualsense4unix "$LAR/.config/"   # cópia, nunca o dela
    env HOME=$LAR XDG_CONFIG_HOME=$LAR/.config \\
        XDG_DATA_HOME=$LAR/.local/share XDG_CACHE_HOME=$LAR/.cache \\
        XDG_STATE_HOME=$LAR/.local/state \\
        scripts/ensaios/a_tecla_livre_no_webkit.py --fotos /tmp/tecla

A janela nasce OCULTA (`Gtk.OffscreenWindow`) — ela tem UMA tela.

`--mutacoes N` roda o contador de mutações de DOM da `A-TELA-SAMBA-01` sobre a
MESMA página da bancada. A medição herdada é **zero em 100 tiques**, e sair de
zero é regressão.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.utils.tela_de_mentira import (  # noqa: E402
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.core import acoes_de_botao as acoes  # noqa: E402
from hefesto_dualsense4unix.interface import hefesto_vivo, onde  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06  # noqa: E402

ABA = "06-navegacao.html"

#: O QUE ELA DIGITA, e o ponto inteiro é que NÃO ESTÁ NA LISTA. A régua confere
#: isso antes de sair do lugar: se um dia virar opção, esta prova passaria a
#: medir o caminho velho com nome novo.
ESCREVE = "Ctrl + W"
#: O que ela escreve na linha AO LADO — outra combinação livre, para o ↺ ter o
#: que desfazer.
NA_VIZINHA = "Ctrl + Shift + F"
#: E uma que o teclado virtual NÃO SABE DIGITAR. O dono é
#: `uinput_keyboard.SUPPORTED_KEYS`; `parse_binding` deixaria passar, porque ele
#: só confere o prefixo.
INVALIDA = "KEY_KP0"

BANDEIRAS = dict(oculta=True, segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 conta_mutacoes=0, prova_no_aparelho=False, entre=2500)


def _publicado_de_mentira() -> pathlib.Path:
    """Um `interface/paginas/` temporário com a `06` da BANCADA dentro.

    TODAS as páginas são copiadas, e não só a `06`: o piloto lista o publicado
    (`onde.paginas(publicado=True)`) para resolver o `--abre` e para a fita, e
    um diretório com um arquivo só o faria falhar por outra razão que não a
    medição.
    """
    destino = pathlib.Path(tempfile.mkdtemp(prefix="hef-publicado-"))
    for pagina in onde.PUBLICADO.glob("*"):
        if pagina.is_file():
            shutil.copy2(pagina, destino / pagina.name)
    shutil.copy2(onde.pagina(ABA, publicado=False), destino / ABA)
    onde.PUBLICADO = destino
    return destino


LER = r"""
(function(){
  location.hash = 'teclas-do-teclado';
  const campos = {};
  for(const el of document.querySelectorAll('#teclas-do-teclado [data-campo^="tecla-"]')){
    campos[el.dataset.campo.slice(6)] = {
      valor: el.value, gesto: el.dataset.gesto || null,
      tipo: el.tagName.toLowerCase() + ':' + (el.type || ''),
      linha: el.dataset.linha || null
    };
  }
  const cx = document.querySelector('#teclas-do-teclado');
  return JSON.stringify({
    aberta: !!(cx && cx.getBoundingClientRect().width > 0),
    campos: campos,
    reset: document.querySelectorAll('#teclas-do-teclado [data-gesto="padrao-da-tecla"]').length
  });
})()
"""

#: ELA DIGITA. `input` primeiro (o que o dedo faz, tecla a tecla) e `change`
#: depois (o que o campo dispara ao perder o foco) — os dois eventos que
#: existem de verdade. O ouvinte do piloto ouve `click` e `change`; o `input`
#: está aqui para provar que a trava aguenta a digitação, e não só o fim dela.
DIGITAR = r"""
(function(){
  const el = document.querySelector('#teclas-do-teclado [data-campo="tecla-%s"]');
  if(!el) return JSON.stringify({achou:false});
  el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  el.value = %s;
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
  return JSON.stringify({achou:true, agora: el.value});
})()
"""

GUARDAR = r"""
(function(){
  const b = document.querySelector('#teclas-do-teclado [data-gesto="guardar-teclas"]');
  if(!b) return JSON.stringify({achou:false});
  b.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  return JSON.stringify({achou:true});
})()
"""

RESETAR = r"""
(function(){
  const a = document.querySelector('#teclas-do-teclado [data-tecla="%s"]');
  if(!a) return JSON.stringify({achou:false});
  a.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  return JSON.stringify({achou:true});
})()
"""

RECADOS = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    fora.push(el.textContent.trim().slice(0, 180));
  }
  return JSON.stringify({recados: fora});
})()
"""


def _perfil_no_disco(nome: str) -> dict:
    from hefesto_dualsense4unix.interface.pacotes import perfil

    try:
        prof = perfil._com_o_src().load_profile(nome)
    except Exception as erro:  # pragma: no cover — diagnóstico
        return {"erro": str(erro)}
    return {"key_bindings": getattr(prof, "key_bindings", None),
            "button_actions": getattr(prof, "button_actions", None)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fotos", default="", help="prefixo dos PNG (sem extensão)")
    ap.add_argument("--mutacoes", type=int, default=0,
                    help="só conta mutações de DOM em N tiques e sai")
    escolha = ap.parse_args()

    de_mentira = _publicado_de_mentira()
    print(f"o publicado de mentira: {de_mentira}\n")

    if escolha.mutacoes:
        # O `main()` DO PILOTO, e não um laço próprio: o contador de mutações é
        # dele (`--conta-mutacoes`), e reescrever o laço aqui seria a segunda
        # medição do mesmo fato. O que este ensaio acrescenta é UMA coisa — a
        # página que o WebView carrega vem da bancada.
        sys.argv = [sys.argv[0], "--oculta", "--abre", ABA,
                    "--conta-mutacoes", str(escolha.mutacoes)]
        hefesto_vivo.main()
        return 0

    dominio = sorted(acoes.DOMINIO_DO_TECLADO)
    minha, vizinha = dominio[0], dominio[1]
    assert acoes.token_do_rotulo(ESCREVE) is None, (
        f"{ESCREVE!r} virou opção da lista — a prova mediria outra coisa.")

    args = argparse.Namespace(**BANDEIRAS, abre=ABA, foto="")
    piloto = hefesto_vivo.Piloto(args)
    passos: list[tuple[str, object]] = []
    ativo = {"nome": ""}

    def js(script: str, guarda: str, retrato: str = "") -> None:
        def voltou(texto: str | None, erro: Exception | None) -> None:
            passos.append((guarda, json.loads(texto) if texto and not erro
                           else {"erro": str(erro)}))
            if retrato:
                GLib.timeout_add(500, lambda: (foto(retrato), False)[1])
        piloto.ponte.perguntar(script, voltou)

    def foto(sufixo: str) -> None:
        if escolha.fotos:
            piloto.tela.fotografar(f"{escolha.fotos}-{sufixo}.png")

    def passo1() -> bool:
        if not piloto.pronto:
            return True
        ctx = getattr(piloto, "_ctx_de_agora", None)
        ativo["nome"] = str(((getattr(ctx, "state", None) or {})
                             .get("active_profile")) or "")
        passos.append(("o perfil ANTES", _perfil_no_disco(ativo["nome"])))
        js(LER, "a tela nasce")
        GLib.timeout_add(900, passo2)
        return False

    def passo2() -> bool:
        foto("teclas")
        js(DIGITAR % (minha, json.dumps(ESCREVE)), f"ela digita em {minha}")
        # E NA VIZINHA TAMBÉM, e isto é medida: na primeira redação o ↺ caía
        # sobre uma linha que já estava no de fábrica e RECUSAVA dizendo *"não
        # havia o que voltar"* — o veredito passava sem o gesto ter desfeito
        # coisa alguma. Um ↺ que não desfaz nada não prova que ele não leva a
        # linha ao lado junto.
        js(DIGITAR % (vizinha, json.dumps(NA_VIZINHA)), f"ela digita em {vizinha}")
        GLib.timeout_add(1500, passo3)
        return False

    def passo3() -> bool:
        # 1,5 s DEPOIS: quinze tiques de 100 ms. É a janela em que a pintura
        # desfazia a escolha antes da trava existir.
        js(LER, "a tela 1,5 s depois (o tique não apagou?)")
        js(GUARDAR, "clica no Guardar")
        GLib.timeout_add(1800, passo4)
        return False

    def passo4() -> bool:
        passos.append(("o perfil DEPOIS do Guardar",
                       _perfil_no_disco(ativo["nome"])))
        js(LER, "a tela depois do Guardar", retrato="depois-do-guardar")
        js(RESETAR % vizinha, f"clica no ↺ do {vizinha}")
        GLib.timeout_add(1800, passo5)
        return False

    def passo5() -> bool:
        passos.append((f"o perfil depois do ↺ do {vizinha}",
                       _perfil_no_disco(ativo["nome"])))
        js(DIGITAR % (minha, json.dumps(INVALIDA)), "ela digita uma inválida")
        GLib.timeout_add(1500, passo6)
        return False

    def passo6() -> bool:
        js(RECADOS, "o recado na tela", retrato="recusa")
        passos.append(("o perfil depois da inválida",
                       _perfil_no_disco(ativo["nome"])))
        GLib.timeout_add(900, lambda: (Gtk.main_quit(), False)[1])
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3500, passo1)
    GLib.timeout_add(45000, Gtk.main_quit)
    Gtk.main()

    print(f"perfil ativo (segundo o daemon): {ativo['nome']!r}")
    print(f"a linha dela: {minha} · a vizinha: {vizinha}")
    print(f"ela escreve: {ESCREVE!r} (fora das {len(acoes.ACOES)} opções da lista)\n")
    for nome, valor in passos:
        print(f"  {nome:42s} {valor}")

    ditos = dict(passos)
    depois = (ditos.get("o perfil DEPOIS do Guardar") or {}).get("key_bindings") or {}
    pos_reset = (ditos.get(f"o perfil depois do ↺ do {vizinha}")
                 or {}).get("key_bindings") or {}
    pos_erro = (ditos.get("o perfil depois da inválida")
                or {}).get("key_bindings") or {}
    recados = (ditos.get("o recado na tela") or {}).get("recados") or []

    veredito = [
        ("a combinação livre chegou ao perfil",
         depois.get(minha) == ["KEY_LEFTCTRL", "KEY_W"]),
        ("o ↺ da vizinha NÃO levou a dela",
         pos_reset.get(minha) == ["KEY_LEFTCTRL", "KEY_W"]),
        (f"o ↺ desfez a escrita da vizinha ({NA_VIZINHA!r} saiu)",
         (ditos.get("o perfil DEPOIS do Guardar") or {}).get("key_bindings", {})
         .get(vizinha) == ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_F"]
         and pos_reset.get(vizinha) != ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_F"]),
        ("o ↺ devolveu a vizinha ao de fábrica",
         pos_reset.get(vizinha) == acoes.padrao()[vizinha].split("+")),
        ("a inválida foi recusada DIZENDO na tela",
         any("não sabe digitar" in r for r in recados)),
        ("a inválida não encostou no perfil",
         pos_erro.get(minha) == ["KEY_LEFTCTRL", "KEY_W"]),
    ]
    print()
    for frase, ok in veredito:
        print(f"  {'PASSOU ' if ok else 'REPROVA'}  {frase}")
    return 0 if all(ok for _f, ok in veredito) else 1


if __name__ == "__main__":
    raise SystemExit(main())
