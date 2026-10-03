#!/usr/bin/env python3
"""A RECUSA DO PRODUTO CHEGAVA AO CARTÃO — e desde 13/09/2026 não chega mais.

**O CONTRATO MUDOU EM 13/09/2026** (FRASES-E-DICAS-01), e esta régua mudou junto
em vez de ser apagada: o roteiro no tempo é o mesmo, e as perguntas viraram o
avesso. A palavra dela está no índice da leva
(o registro «A-TERCEIRA-LISTA-DELA-INDICE» de 13/09/2026, linha 19):
a caixa laranja da foto era uma recusa pousada no cartão, e ela mandou esse tipo
de frase parar de aparecer. O clique recusado responde pela piscada de recusa
no botão (`test_a_recusa_pisca_no_botao`), e a frase vai ao diário da janela.
Hoje a régua cobra que, em cada parada do roteiro — logo depois do clique, seis
tiques depois, depois de o bloco ser trocado, no segundo e no terceiro clique,
com o controle fora da mesa e de volta, e depois do prazo que valia —, **a tela
não tenha recado nenhum nem a frase da recusa**.

A MORDIDA DE HOJE: devolva o piloto de `249af1f6` (o depósito e a pintura do
recado) e as paradas voltam a mostrar a frase — as réguas de 1 a 5 reprovam.

O QUE SEGUE É A HISTÓRIA do contrato de 02/09/2026, medido na JANELA:

POR QUE ESTA RÉGUA EXISTE, e a data é 02/09/2026. O contrato desta casa é
explícito: `RuntimeError` num gesto quer dizer *"o produto recusou, e a frase
VAI PARA A TELA"*, escrita para quem está com o controle na mão. A recusa
humanizada existia, estava testada — e saía no `stderr` do processo:

    [gesto falhou] 02-controles.html · mudo: o daemon não confirmou o mudo do
    microfone — ou o Hefesto está parado, ou este controle saiu da mesa

Quem clica na janela não lê o terminal de quem a lançou. **É a forma de defeito
mais cara desta casa: alguém curou o caminho e provou a cura num caminho que ela
não usa.** Medido pelo caminho DELA — dois cliques no 🎙 da `02-controles`, com
um dublê que faz o `mic.set` recusar: os dois recusaram com a frase certa, o
`desfechos` do piloto a guardou, e o DOM não tinha uma letra dela. O segundo
clique parecia o primeiro.

AS OITO COISAS QUE ESTA RÉGUA COBRA, e cada uma é um jeito diferente de o
canal mentir:

1. **A FRASE CHEGA AO DOM.** Não ao `desfechos`, não ao `stderr` — ao documento
   que ela está olhando.
2. **ELA CHEGA AO CARTÃO DAQUELE CONTROLE.** Na mesa de quatro, a recusa de um
   no cartão do vizinho é pior que recusa nenhuma.
3. **ELA SOBREVIVE À REPINTURA.** A tela repinta a cada 500 ms e troca blocos
   inteiros. Uma frase que só existe no instante do clique não é vista por
   ninguém — é a mesma razão pela qual
   `daemon/subsystems/recado_do_microfone.py` é um DEPÓSITO e não um evento.
4. **O SEGUNDO CLIQUE TAMBÉM RESPONDE**, que é o enunciado desta frente em uma
   linha.
5. **ELA APARECE NO CLIQUE, e não no próximo tique.** Meio segundo de silêncio
   basta para ela clicar de novo achando que o primeiro não pegou.
6. **ELA É DO CONTROLE, E NÃO DA COLUNA** — o item de 02/09/2026, e o único que
   só existe no TEMPO. Ver abaixo.
7. **ELA VENCE**, e vence no prazo QUE ELA DECIDIU: *"a frase de recusa SOME
   depois de um tempo — ~30 s e desaparece. É aviso, não estado."*

E A OITAVA, que é sobre o instrumento e não sobre o produto: **o aviso não pode
entrar na conta da régua do mockup.** Ele é um nó que o piloto desenha, e se
ganhasse `data-campo`/`data-papel`/`data-hef` o `LER_CAMPOS` passaria a contá-lo
como campo da página — a régua mediria o próprio instrumento.

O ITEM 6, e por que ele precisou de um roteiro no TEMPO: o depósito nasceu
`{pref: frase}`, e `pref` é a POSIÇÃO — `mesa_viva.mesa_do_estado` enumera os
conectados de 1 a cada tique (*"o `pref` continua sendo a POSIÇÃO … e `jogador`
continua sendo a IDENTIDADE"*, `mesa_viva.py`). Com dois controles na mesa,
recusa no 🎙 do `p1` (o do cabo) e o do cabo saindo, o cartão de QUEM FICOU
passava a mostrar, por até 30 s, uma frase que termina em *"ou este controle
saiu da mesa"* — sobre outro controle. É o item 2 um nível acima: num INSTANTE
a coluna ainda é de quem foi clicado, e por isso o item 2 dava verde sobre o
defeito. A cura é reuso: a chave passou a ser o `uniq` normalizado
(`core/sysfs_leds.norm_mac`, o dono que esta casa já tinha do endereço) e a
coluna é resolvida no instante da pintura, contra a mesa daquele tique.

A MORDIDA DE 02/09, e eram SETE — uma por item. **Devolva por CÓPIA (`cp`), nunca por
`git checkout --`** — isso já custou trabalho quatro vezes nesta casa. Os
números são os MEDIDOS em 02/09/2026, com o arquivo de DOZE testes:

* apague o `self._recados[uniq] = …` de `Piloto._recusou_dizendo`
  → **8 reprovam** (a frase não chega a lugar nenhum);
* troque `pai.insertBefore(el, pai.firstChild)` do BOOTSTRAP por
  `document.body.appendChild(el)` → **2 reprovam** (a frase não está no cartão);
* apague o `carga["recados"] = self._recados_para_a_tela()` de `Piloto._tique`
  → **3 reprovam** (o aviso não volta depois de o bloco ser trocado, não
  sobrevive à saída de um controle, e não vence nunca);
* troque `alvo = norm_mac(…)` por `alvo = pref` em `_gesto` **e** `"cartao":
  onde_esta.get(chave, "")` por `"cartao": chave` — que é a base de 02/09 de
  volta → **3 reprovam**, e uma delas é o item 6;
* apague o `self._js(…)` de `_recusou_dizendo` (a pintura na hora)
  → **1 reprova**;
* troque `SEGUNDOS_DO_RECADO = 30.0` por `3.0` → **1 reprova**;
* dê `data-campo` ao aviso no BOOTSTRAP → **1 reprova**.

**E O NÚMERO ANTERIOR ESTAVA ERRADO, o que é o motivo de ele estar aqui de novo
com a data:** este bloco dizia "reprovam 4 / 1 / 2", que soma SETE num arquivo
que já tinha OITO testes. Os números tinham sido medidos numa versão de sete e
não foram remedidos quando o oitavo nasceu. Quem conferisse a mordida no dia
seguinte concluiria que introduziu um teste a mais reprovando.

POR QUE ELA ABRE UM WEBKIT DE VERDADE: porque foi a leitura do fonte que se
enganou da primeira vez. `Gtk.OffscreenWindow` — sob Xvfb não há gerenciador de
janelas e uma `Gtk.Window` fica 1x1 para sempre.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
sys.path.insert(0, str(INTERFACE))

UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

#: O ESTADO DUBLÊ. Ele é o mínimo que `mesa_viva.mesa_do_estado` precisa para
def _ctl(uniq: str, transporte: str, jogador: int) -> dict:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "audio": {"mic_mudo": False}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}

#: rádio) HERDA A POSIÇÃO 1: `mesa_viva.mesa_do_estado` enumera os conectados de
SEM_O_DO_CABO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P2, "bt", 2)],
}

CHAVE_P1 = "aabbcc000001"

MESA = {"estado": ESTADO}

VENCE_EM_S = 8.0

RECUSA_DO_ATO = "o volume deste alto-falante ainda é desconhecido"

LER_A_TELA = r"""
(function(){
  const recados = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    const cartao = el.closest('[data-controle],[data-uniq]');
    recados.push({
      chave: el.getAttribute('data-hef-recado') || '',
      texto: (el.textContent || '').trim(),
      dentro_de: cartao ? (cartao.dataset.controle || cartao.dataset.uniq || '') : '',
    });
  }
  return JSON.stringify({
    recados: recados,
    // A FRASE NO TEXTO VISÍVEL — 13/09/2026: sem recado, a pergunta é se ela
    // chegou à tela por qualquer outro caminho.
    frase_na_tela: (document.body ? (document.body.innerText || '') : '')
      .indexOf(__FRASE__) >= 0,
    // A CONTA DA RÉGUA DO MOCKUP, no mesmo instante: os três vocabulários de
    // endereço que o `LER_CAMPOS` varre. O aviso não pode mexer neste número.
    enderecos: document.querySelectorAll('[data-campo],[data-papel],[data-hef]').length,
  });
})()
""".replace("__FRASE__", json.dumps(RECUSA_DO_ATO))

CLICAR_NO_MIC = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="alto-falante"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  b.click();
  return 'cliquei';
})()
"""

MATAR_O_CARTAO = r"""
(function(){
  const c = document.querySelector('[data-controle="p1"]');
  if(!c) return 'sem cartao';
  for(const el of document.querySelectorAll('.hef-recado')) el.remove();
  c.innerHTML = c.innerHTML;
  return String(document.querySelectorAll('.hef-recado').length);
})()
"""

APAGAR_OS_RECADOS = r"""
(function(){
  for(const el of document.querySelectorAll('.hef-recado')) el.remove();
  return String(document.querySelectorAll('.hef-recado').length);
})()
"""


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre o piloto DE VERDADE, oculto, e roda o roteiro de tempo."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse

    import hefesto_vivo as hv

    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado)
    fora_do_produto = hasattr(hv, "SEGUNDOS_DO_RECADO")
    MESA["estado"] = ESTADO
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: MESA["estado"]  # type: ignore[assignment]
    hv.ponte.mic_canal_set_detalhado = lambda *a, **k: {  # type: ignore[assignment]
        "status": "incompleto", "canal_feito": False, "firmware_pedido": True,
        "motivo": RECUSA_DO_ATO}

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="02-controles.html", prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def antes_do_clique() -> bool:
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(LER_A_TELA, ler("antes"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique"))
        GLib.timeout_add(700, logo_depois)
        return False

    def logo_depois() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("logo-depois"))
        GLib.timeout_add(2300, sobreviveu)
        return False

    def sobreviveu() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-seis-tiques"))
        piloto.ponte.perguntar(MATAR_O_CARTAO, anotar("matei-o-cartao"))
        GLib.timeout_add(1100, voltou)
        return False

    def voltou() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-da-troca-de-bloco"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("segundo-clique"))
        GLib.timeout_add(900, depois_do_segundo)
        return False

    def depois_do_segundo() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-segundo-clique"))
        GLib.timeout_add(120, com_o_tique_parado)
        return False

    def com_o_tique_parado() -> bool:
        # o `_recusou_dizendo` pode repor a frase.
        piloto.pronto = False
        piloto.ponte.perguntar(APAGAR_OS_RECADOS, anotar("apaguei-os-recados"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("terceiro-clique"))
        GLib.timeout_add(600, mediu_a_pintura_na_hora)
        return False

    def mediu_a_pintura_na_hora() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("sem-tique-depois-do-clique"))
        piloto.pronto = True
        MESA["estado"] = SEM_O_DO_CABO
        GLib.timeout_add(2300, um_saiu)
        return False

    def um_saiu() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-um-sair"))
        fora["mesa-de-um-so"] = [f"{c['pref']}:{c['uniq']}"
                                 for c in piloto._mesa_de_agora]
        fora["chaves-do-deposito"] = sorted(getattr(piloto, "_recados", {}))
        MESA["estado"] = ESTADO
        GLib.timeout_add(1300, voltou_a_mesa)
        return False

    def voltou_a_mesa() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-o-controle-voltar"))
        GLib.timeout_add(int(VENCE_EM_S * 1000), venceu)
        return False

    def venceu() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-vencer"))
        GLib.timeout_add(900, fim)
        return False

    def fim() -> bool:
        fora["desfechos"] = {k: list(v) for k, v in piloto.desfechos.items()}
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2000, antes_do_clique)
    guarda = GLib.timeout_add(int(30000 + VENCE_EM_S * 1000), Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon,
         hv.ponte.mic_canal_set_detalhado) = guardado
        MESA["estado"] = ESTADO
    fora["prazo-no-produto"] = fora_do_produto
    assert "depois-de-vencer" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}")
    return fora


def _frases(leitura: object) -> list[str]:
    assert isinstance(leitura, dict), leitura
    return [r["texto"] for r in leitura["recados"]]


def _muda(medido: dict, rotulo: str) -> None:
    """A parada do roteiro sem recado e sem a frase da recusa — ou a reprova."""
    leitura = medido[rotulo]
    assert isinstance(leitura, dict), f"{rotulo}: {leitura!r}"
    assert _frases(leitura) == [], (
        f"{rotulo}: a tela tem recado {_frases(leitura)!r} — a recusa voltou a "
        f"pousar no cartão, que é a caixa que ela mandou parar de aparecer")
    assert not leitura["frase_na_tela"], (
        f"{rotulo}: a frase da recusa está no texto visível por outro caminho")


def test_o_gesto_recusou_dizendo(medido: dict) -> None:
    assert medido["clique"] == "cliquei", medido["clique"]
    desfechos = medido["desfechos"]
    assert isinstance(desfechos, dict)
    assert "02-controles.html:mudo" in desfechos, (
        f"o clique não chegou ao gesto — os desfechos foram {desfechos}")
    classe, frase = desfechos["02-controles.html:mudo"]
    assert classe == "recusou dizendo", (classe, frase)
    assert frase.startswith("RuntimeError:"), frase
    assert RECUSA_DO_ATO in frase, frase


def test_a_frase_da_recusa_nao_chega_ao_dom(medido: dict) -> None:
    """ERA `test_a_frase_da_recusa_chega_ao_dom` — o contrato mudou em 13/09/2026."""
    _muda(medido, "antes")
    _muda(medido, "logo-depois")


def test_a_frase_nao_pousa_em_cartao_nenhum(medido: dict) -> None:
    """ERA `test_a_frase_pousa_no_cartao_de_quem_foi_clicado` — 13/09/2026."""
    leitura = medido["logo-depois"]
    assert isinstance(leitura, dict)
    assert [r["dentro_de"] for r in leitura["recados"]] == [], leitura["recados"]


def test_nada_volta_nos_tiques(medido: dict) -> None:
    """ERA `test_o_aviso_sobrevive_aos_tiques` — 13/09/2026."""
    _muda(medido, "depois-de-seis-tiques")


def test_nada_volta_quando_a_pintura_troca_o_bloco(medido: dict) -> None:
    """ERA `test_o_aviso_volta_quando_a_pintura_troca_o_bloco` — 13/09/2026."""
    assert medido["matei-o-cartao"] == "0", (
        f"a simulação não trocou o bloco ({medido['matei-o-cartao']!r}) — sem "
        f"isso este teste passa sobre nada")
    _muda(medido, "depois-da-troca-de-bloco")


def test_o_segundo_clique_tambem_nao_fala(medido: dict) -> None:
    """ERA `test_o_segundo_clique_tambem_responde_na_tela` — 13/09/2026."""
    assert medido["segundo-clique"] == "cliquei", medido["segundo-clique"]
    _muda(medido, "depois-do-segundo-clique")


def test_o_clique_nao_pinta_frase_na_hora(medido: dict) -> None:
    """ERA `test_a_frase_aparece_no_clique_e_nao_no_proximo_tique` — 13/09/2026."""
    assert medido["terceiro-clique"] == "cliquei", medido["terceiro-clique"]
    assert medido["apaguei-os-recados"] == "0", medido["apaguei-os-recados"]
    _muda(medido, "sem-tique-depois-do-clique")


def test_o_piloto_nao_guarda_recado_de_controle_nenhum(medido: dict) -> None:
    """ERA `test_o_recado_e_do_endereco_e_nao_da_posicao` — 13/09/2026."""
    assert medido["mesa-de-um-so"] == [f"p1:{UNIQ_P2}"], (
        f"a mesa do piloto não trocou de dono ({medido['mesa-de-um-so']!r}) — "
        f"sem a troca esta régua passa sobre nada")
    assert medido["chaves-do-deposito"] == [], (
        f"o piloto guardou recado para {medido['chaves-do-deposito']!r}")
    _muda(medido, "depois-de-um-sair")


def test_nada_volta_quando_o_controle_volta(medido: dict) -> None:
    """ERA `test_o_aviso_volta_ao_cartao_quando_o_controle_volta` — 13/09/2026."""
    _muda(medido, "depois-de-o-controle-voltar")


def test_nada_ha_a_vencer(medido: dict) -> None:
    """ERA `test_o_aviso_vence_e_some` — 13/09/2026."""
    _muda(medido, "depois-de-vencer")


def test_o_prazo_saiu_com_o_canal(medido: dict) -> None:
    """ERA `test_o_prazo_do_produto_e_o_que_ela_decidiu` — 13/09/2026."""
    assert medido["prazo-no-produto"] is False, (
        "voltou ao piloto o prazo da frase de recusa na tela")


def test_o_aviso_nao_conta_como_campo_da_pagina(medido: dict) -> None:
    """Nada que a recusa faça pode mexer na conta de endereços da página."""
    antes, com_aviso = medido["antes"], medido["logo-depois"]
    assert isinstance(antes, dict) and isinstance(com_aviso, dict)
    assert antes["enderecos"] == com_aviso["enderecos"], (
        f"a página tinha {antes['enderecos']} endereços de pintura e passou a "
        f"ter {com_aviso['enderecos']} depois da recusa. O `LER_CAMPOS` varre "
        f"`data-campo`/`data-papel`/`data-hef`, e a régua do mockup passaria a "
        f"contar o que a recusa pôs na página.")
