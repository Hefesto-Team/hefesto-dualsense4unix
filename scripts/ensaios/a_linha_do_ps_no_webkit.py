#!/usr/bin/env python3
"""A 22ª linha — o botão PS — clicada DENTRO do WebKit dela.

POR QUE ELE EXISTE, e é a regra da casa (ONDA5-06-02, §7): *"Botão que você
acrescentou e nunca clicou não está entregue."* As réguas de unidade provam que
o gerador emite a linha e que o pacote a lê. O que prova o PRODUTO é a escolha
saindo do `<select>` do PS, chegando ao Python pelo ouvinte do piloto, e o
"Guardar" gravando `button_actions["ps"]` no perfil — no motor que ela usa, que
é o `WebKit2.WebView`, e não no Chrome de uma régua.

E ELE MEDE TAMBÉM O INTERRUPTOR (06-Q1): pinta as DUAS cenas do portão — mouse
ligado e mouse desligado, as duas com o interruptor APAGADO — e lê a cor do pino
com `getComputedStyle`. **Uma cena só não prova nada**, porque o defeito era
justamente as duas serem iguais.

O HOME É DE MENTIRA, e isto não é zelo: `hefesto_vivo` dispara migrações
one-shot no `~/.config` REAL, e o "Guardar" desta aba grava no perfil ativo. Rode
sempre assim::

    LAR=$(mktemp -d)
    mkdir -p "$LAR/.config" "$LAR/.local/share" "$LAR/.cache" "$LAR/.local/state"
    cp -r ~/.config/hefesto-dualsense4unix "$LAR/.config/"   # cópia, nunca o dela
    env HOME=$LAR XDG_CONFIG_HOME=$LAR/.config \\
        XDG_DATA_HOME=$LAR/.local/share XDG_CACHE_HOME=$LAR/.cache \\
        XDG_STATE_HOME=$LAR/.local/state \\
        scripts/ensaios/a_linha_do_ps_no_webkit.py --fotos /tmp/ps

A janela nasce OCULTA (`Gtk.OffscreenWindow`) — ela tem UMA tela.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

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
from hefesto_dualsense4unix.interface import hefesto_vivo  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes.a06_navegacao import (  # noqa: E402
    DESLIGADO,
    LIGADO,
    NADA_A_DIZER,
    RAZAO_DO_PORTAO,
)

ABA = "06-navegacao.html"
#: A tecla que a prova escolhe para o PS. Ela NÃO é um `KEY_*` digitado na tela:
#: o que se manda ao `<select>` é o RÓTULO que o produto lhe dá.
TECLA = "KEY_F11"

BANDEIRAS = dict(oculta=True, segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 conta_mutacoes=0, prova_no_aparelho=False, entre=2500)

#: 1. ABRE A POP-UP e LÊ a linha do PS como ela nasce.
LER_A_LINHA = r"""
(function(){
  location.hash = 'definicoes-mouse';
  const sel = document.querySelector('#definicoes-mouse [data-linha="ps"]');
  if(!sel) return JSON.stringify({achou:false});
  const tr = sel.closest('tr');
  const linhas = document.querySelectorAll('#definicoes-mouse [data-linha]').length;
  return JSON.stringify({
    achou:true,
    linhas:linhas,
    nome:(tr.querySelector('td.b')||{}).textContent.trim(),
    valor:sel.value,
    gesto:sel.dataset.gesto || null,
    campo:sel.dataset.campo || null,
    quantas:Array.from(sel.options).length
  });
})()
"""

#: 2. ESCOLHE a tecla como uma pessoa escolheria — pelo evento `change`, que é
#:    o único que o ouvinte do piloto reconhece nestes `<select>`.
ESCOLHER = r"""
(function(){
  const sel = document.querySelector('#definicoes-mouse [data-linha="ps"]');
  const alvo = %s;
  const op = Array.from(sel.options).find(o => o.textContent.trim() === alvo);
  if(!op) return JSON.stringify({ok:false, porque:'a lista não oferece ' + alvo});
  sel.value = op.value || op.textContent;
  sel.dispatchEvent(new Event('change', {bubbles:true}));
  return JSON.stringify({ok:true, agora:sel.value});
})()
"""

#: 3. CLICA no "Guardar" — o mesmo caminho do rato, pelo ouvinte delegado.
GUARDAR = r"""
(function(){
  const b = document.querySelector('#definicoes-mouse [data-gesto="guardar-definicoes"]');
  if(!b) return JSON.stringify({ok:false});
  b.click();
  return JSON.stringify({ok:true});
})()
"""

#: 4. AS DUAS CENAS DO PORTÃO, pelas mesmas duas escritas que o pacote produz.
#:
#: O ENDEREÇO DO LADO É ARRANCADO ANTES DE PINTAR, e é a única liberdade que
#: este roteiro toma — declarada porque foi MEDIDA: a cena pintada durava menos
#: que o obturador. O tique é de 100 ms e reescreve `rato-ligado` a partir do
#: daemon; as duas fotos saíam com a palavra do daemon nas duas, provando o
#: contrário do que provam. Sem o `data-campo` o `escrever()` do piloto não
#: acha o elemento e a cena fica de pé para a foto.
#:
#: A CASCATA NÃO DEPENDE DELE: as regras do portão casam por
#: `.tog[data-gesto="modo"]`, pela classe `ligado` e pelo `.laranja` da tira —
#: nenhuma delas olha o `data-campo`. O que a foto mostra é exatamente o que a
#: leitura de `getComputedStyle` mede no mesmo instante, e as duas saem daqui.
CENA = r"""
(function(){
  location.hash = '';
  const est = document.querySelector('[data-campo="modo-portao"]');
  const tog = document.querySelector('.tog[data-gesto="modo"]');
  for(const el of document.querySelectorAll('[data-campo="rato-ligado"]'))
    el.removeAttribute('data-campo');
  est.innerHTML = %s;
  tog.classList.toggle('ligado', %s);
  tog.querySelector('.txt').textContent = %s;
  const linha = tog.closest('.at-linha');
  const g = (el, p) => getComputedStyle(el).getPropertyValue(p);
  return JSON.stringify({
    palavra: tog.querySelector('.txt').textContent,
    pino: g(tog.querySelector('.pino'), 'background-color'),
    fundo: g(tog, 'background-color'),
    borda: g(tog, 'border-top-color'),
    ponteiro: g(tog, 'pointer-events'),
    cursor_da_linha: g(linha, 'cursor')
  });
})()
"""


def _perfil_no_disco(nome: str) -> dict:
    from pacotes import perfil

    return perfil.ativo(nome) or {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fotos", default="", help="prefixo dos PNG (sem extensão)")
    escolha = ap.parse_args()

    rotulo = acoes.rotulo(TECLA)
    args = argparse.Namespace(**BANDEIRAS, abre=ABA, foto="")
    piloto = hefesto_vivo.Piloto(args)
    passos: list[tuple[str, object]] = []
    ativo = {"nome": ""}

    def js(script: str, guarda: str, retrato: str = "") -> None:
        """Pergunta ao DOM e, opcionalmente, fotografa NO RETORNO.

        A FOTO TEM DE SAIR NO MESMO INSTANTE DA LEITURA, e isto foi medido em
        06/09/2026: fotografando 700 ms depois de pintar a cena do portão, o
        PNG saía com o valor do DAEMON — o tique é de 100 ms e já tinha
        repintado o `rato-ligado`. A leitura estava certa e a foto contava
        outra coisa; duas fotos assim, lado a lado, provariam o contrário do
        que provam.
        """
        def voltou(texto: str | None, erro: Exception | None) -> None:
            passos.append((guarda, json.loads(texto) if texto and not erro
                           else {"erro": str(erro)}))
            # E ELA SAI UM POUCO DEPOIS, não no retorno: o `fotografar` da
            # janela oculta entrega o quadro ANTERIOR quando chamado no mesmo
            # instante da escrita — medido em 06/09/2026, com as duas cenas
            # saindo trocadas uma da outra. Com o endereço já arrancado (ver
            # `CENA`), esperar é seguro: o tique não tem mais como desfazer.
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
        js(LER_A_LINHA, "a linha nasce")
        GLib.timeout_add(900, passo2)
        return False

    def passo2() -> bool:
        foto("popup")
        js(ESCOLHER % json.dumps(rotulo), "ela escolhe")
        GLib.timeout_add(900, passo3)
        return False

    def passo3() -> bool:
        js(LER_A_LINHA, "a tela depois do change")
        js(GUARDAR, "clica no Guardar")
        GLib.timeout_add(1600, passo4)
        return False

    def passo4() -> bool:
        passos.append(("o perfil no disco", _perfil_no_disco(ativo["nome"])
                       .get("button_actions")))
        js(CENA % (json.dumps(f'<span class="laranja">{RAZAO_DO_PORTAO}</span>'),
                   "true", json.dumps(LIGADO)), "portão + mouse LIGADO",
           retrato="portao-ligado")
        GLib.timeout_add(700, passo5)
        return False

    def passo5() -> bool:
        js(CENA % (json.dumps(f'<span class="laranja">{RAZAO_DO_PORTAO}</span>'),
                   "false", json.dumps(DESLIGADO)), "portão + mouse DESLIGADO",
           retrato="portao-desligado")
        GLib.timeout_add(700, passo6)
        return False

    def passo6() -> bool:
        js(CENA % (json.dumps(NADA_A_DIZER), "true", json.dumps(LIGADO)),
           "sem portão + mouse LIGADO")
        GLib.timeout_add(900, lambda: (Gtk.main_quit(), False)[1])
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3500, passo1)
    GLib.timeout_add(45000, Gtk.main_quit)
    Gtk.main()

    print(f"perfil ativo (segundo o daemon): {ativo['nome']!r}")
    print(f"a tecla escolhida: {TECLA} -> rótulo {rotulo!r}\n")
    for nome, valor in passos:
        print(f"  {nome:28s} {valor}")

    # O VEREDITO, e ele é do produto: o `button_actions['ps']` tem de estar no
    # disco com o TOKEN — não com o rótulo da tela.
    gravado = dict(passos).get("o perfil no disco") or {}
    ok = gravado.get(acoes.BOTAO_PS) == TECLA
    print(f"\n{'PASSOU' if ok else 'REPROVA'}: o perfil guarda "
          f"button_actions[{acoes.BOTAO_PS!r}] = "
          f"{gravado.get(acoes.BOTAO_PS)!r} (esperado {TECLA!r})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
