#!/usr/bin/env python3
"""A RECUSA DO PRODUTO CHEGA AO CARTÃO — medida na JANELA, não no terminal.

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

A MORDIDA, e são SETE — uma por item. **Devolva por CÓPIA (`cp`), nunca por
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

#: A mesa de mentira, na faixa sintética da casa — há dois portões de anonimato
#: nesta árvore e um endereço mascarado ainda carrega o OUI do aparelho dela.
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

#: O ESTADO DUBLÊ. Ele é o mínimo que `mesa_viva.mesa_do_estado` precisa para
#: montar `p1` e `p2` — a régua não fala com o daemon dela, e em máquina sem
#: daemon o `_tique` sairia calado pelo `[daemon mudo]` e a janela nunca pintaria.
def _ctl(uniq: str, transporte: str, jogador: int) -> dict:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "audio": {"mic_mudo": False}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}

#: A MESMA MESA COM UM CONTROLE A MENOS — o do CABO saiu, e quem ficou (o do
#: rádio) HERDA A POSIÇÃO 1: `mesa_viva.mesa_do_estado` enumera os conectados de
#: 1 a cada tique. É o estado que revela o defeito de identidade de 02/09/2026,
#: e ele só existe no TEMPO: num instante só, `p1` é sempre quem foi clicado.
SEM_O_DO_CABO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P2, "bt", 2)],
}

#: O `uniq` NORMALIZADO é a chave do depósito — `core/sysfs_leds.norm_mac`, o
#: dono que esta casa já tinha do endereço. Escrito aqui à mão de propósito: a
#: régua confere o VALOR que o produto usa, e importar a mesma função dos dois
#: lados faria os dois errarem juntos em silêncio.
CHAVE_P1 = "aabbcc000001"

#: A MESA VIVA DA MEDIÇÃO. O dublê lê daqui a cada tique, e o roteiro troca o
#: conteúdo para o controle sair da mesa e voltar.
MESA = {"estado": ESTADO}

#: QUANTO O AVISO VIVE NESTA MEDIÇÃO. O produto usa 30 s (decisão dela); aqui a
#: constante encolhe para a régua poder ver a frase VENCER sem ficar meio minuto
#: parada. É a constante do produto que muda, e não uma segunda regra escrita
#: para o teste — a régua mede o mesmo caminho.
VENCE_EM_S = 8.0

#: A FRASE QUE O ATO DO MICROFONE DEVOLVE quando falha pela metade. Ela é uma
#: frase de PROVA, com forma reconhecível — o texto que o produto diz é do
#: DAEMON (`ipc_handlers._handle_mic_canal_set`), e digitá-lo aqui faria esta
#: régua medir a si mesma em vez de medir se a frase do dono ATRAVESSA da
#: resposta até o cartão. É esse atravessar que este arquivo existe para cobrar.
RECUSA_DO_ATO = ("o microfone foi ligado no canal deste controle, mas o "
                 "Hefesto não conseguiu escrever o mudo no aparelho")

#: O que se lê do DOM a cada parada do roteiro. `dentro_de` é o item 2: de quem
#: é o cartão em que a frase pousou.
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
    // A CONTA DA RÉGUA DO MOCKUP, no mesmo instante: os três vocabulários de
    // endereço que o `LER_CAMPOS` varre. O aviso não pode mexer neste número.
    enderecos: document.querySelectorAll('[data-campo],[data-papel],[data-hef]').length,
  });
})()
"""

#: O CLIQUE, no 🎙 do cartão do p1 — e é o botão do produto, com o `data-gesto`
#: que a página publicada traz. Clicar por coordenada é a armadilha que esta casa
#: já pagou duas vezes.
CLICAR_NO_MIC = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="microfone"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  b.click();
  return 'cliquei';
})()
"""

#: A TROCA DE BLOCO, simulada como a pintura a faz de verdade: `alvo.innerHTML =
#: html`, com um `html` que vem do PACOTE e não sabe que existe aviso nenhum. É o
#: que acontece com a fita, com a tabela de perfis e com o mapa do gabinete — um
#: bloco cujo número de filhos muda com o dado não tem como ser pintado campo a
#: campo.
#:
#: O `remove()` VEM ANTES, E É O PONTO: a primeira versão desta sonda fazia só
#: `c.innerHTML = c.innerHTML` e o aviso VOLTAVA sozinho — o `innerHTML` que se
#: lê já traz o `<div class="hef-recado">` serializado, e reatribuí-lo o recria.
#: Aquilo não simulava troca de bloco nenhuma: simulava o navegador copiando o
#: aviso. A sonda dizia `1` onde tinha de dizer `0`, e a régua teria passado
#: sobre nada.
MATAR_O_CARTAO = r"""
(function(){
  const c = document.querySelector('[data-controle="p1"]');
  if(!c) return 'sem cartao';
  for(const el of document.querySelectorAll('.hef-recado')) el.remove();
  c.innerHTML = c.innerHTML;
  return String(document.querySelectorAll('.hef-recado').length);
})()
"""

#: A TELA LIMPA COM O TIQUE PARADO — é o que dá dente à PINTURA NA HORA. Sem
#: parar o tique, a repintura de 500 ms recoloca a frase e a régua fica verde
#: com ou sem a cura: a leitura aos 700 ms mede o TIQUE, não o clique. Foi assim
#: que a entrega "deposita a frase E pinta na hora" atravessou a auditoria sem
#: régua nenhuma — arrancar a pintura imediata deixava os oito testes verdes.
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

    # OS DOIS DUBLÊS. O primeiro tira o daemon do caminho; o segundo faz o
    # `mic.set` recusar, que é o caminho do `RuntimeError` em
    # `a02_controles.mudo`. Nada sai para aparelho nenhum.
    #
    # E ELES SÃO DEVOLVIDOS NO FIM, o que esta fixture NÃO fazia. `mesa_viva` e
    # `pacotes.ponte` são módulos COMPARTILHADOS do produto: escrever neles sem
    # devolver deixa, no mesmo processo, uma mesa de mentira com dois controles
    # e um `mic.set` que sempre recusa para todo vizinho que abrir um `Piloto`
    # depois. Na lista ordenada dos arquivos que citam `hefesto_vivo` este corre
    # em 9º, à frente de quatro medições de GUI. Não houve vítima — mas um
    # vizinho verde sobre um dublê que ele não escreveu é a forma exata do
    # defeito que esta casa persegue, e o relatório dele diria "medido".
    # **O DUBLÊ MUDOU DE FUNÇÃO EM 04/09/2026 — S-05, a D-12 dela.** Era
    # `ponte.mic_set`, e o gesto `mudo` da aba 02 passou a chamar o ATO inteiro
    # (`mic_canal_set_detalhado`). Com o dublê no nome VELHO esta régua
    # continuava VERDE — mas pelo caminho errado: a chamada ia ao socket, não
    # achava daemon, e a recusa vinha do ramo *"o Hefesto está parado"* em vez
    # do ramo que este arquivo existe para medir. É a forma exata do defeito que
    # a nota logo abaixo persegue: **um vizinho verde sobre um dublê que ele não
    # escreveu**. O nome novo devolve a régua ao caminho que ela promete.
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado,
                hv.SEGUNDOS_DO_RECADO)
    #: O VALOR DO PRODUTO, lido ANTES de a régua o encolher. É o que dá dono à
    #: decisão 19 dela (*"~30 s e desaparece"*): sem ele, trocar `30.0` por
    #: `3.0` ou por `300.0` deixaria os testes todos verdes, porque a fixture
    #: sobrescreve a constante antes de qualquer medição.
    fora_do_produto = float(hv.SEGUNDOS_DO_RECADO)
    MESA["estado"] = ESTADO
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: MESA["estado"]  # type: ignore[assignment]
    # `status: "incompleto"` COM MOTIVO é o que o daemon responde quando o ato
    # falha pela metade, e é o corpo que `frase_do_ato_do_microfone` traduz. Um
    # `False` aqui seria mais frouxo que a ponte real, que devolve `dict|None`.
    hv.ponte.mic_canal_set_detalhado = lambda *a, **k: {  # type: ignore[assignment]
        "status": "incompleto", "canal_feito": False, "firmware_pedido": True,
        "motivo": RECUSA_DO_ATO}
    hv.SEGUNDOS_DO_RECADO = VENCE_EM_S

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
        # A PÁGINA TEM DE ESTAR PRONTA, e não "já deve ter carregado": aos 600 ms
        # o bootstrap ainda não instalou e o `el.click()` acha o botão sem
        # ouvinte que responda — o clique some, calado. Já custou uma medição.
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
        # ~6 tiques de 500 ms depois do clique: a repintura correu por cima.
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-seis-tiques"))
        piloto.ponte.perguntar(MATAR_O_CARTAO, anotar("matei-o-cartao"))
        GLib.timeout_add(1100, voltou)
        return False

    def voltou() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-da-troca-de-bloco"))
        # O SEGUNDO CLIQUE, e ele é o defeito de origem em pessoa: o relato
        # anterior dizia que ele respondia, e respondia para quem roda pelo
        # terminal. Aqui ele também RENOVA o depósito — e é o que dá dente ao
        # teste do vencimento. Sem esta renovação, o aviso já estava morto
        # (levado pela troca de bloco) quando a régua foi ver se ele tinha
        # vencido: ela dava verde sobre um DOM vazio, que é a forma exata de
        # "verde sobre nada" que esta casa persegue. Medido arrancando o
        # `carga["recados"]` do tique — a régua passava.
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("segundo-clique"))
        GLib.timeout_add(900, depois_do_segundo)
        return False

    def depois_do_segundo() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-segundo-clique"))
        GLib.timeout_add(120, com_o_tique_parado)
        return False

    def com_o_tique_parado() -> bool:
        # O TIQUE PARA, e é o que separa o clique da repintura. Com ele vivo, a
        # frase volta à tela em até 500 ms com ou sem a pintura imediata — e a
        # leitura aos 700 ms de `logo_depois` não distingue as duas. Parado, só
        # o `_recusou_dizendo` pode repor a frase.
        piloto.pronto = False
        piloto.ponte.perguntar(APAGAR_OS_RECADOS, anotar("apaguei-os-recados"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("terceiro-clique"))
        GLib.timeout_add(600, mediu_a_pintura_na_hora)
        return False

    def mediu_a_pintura_na_hora() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("sem-tique-depois-do-clique"))
        piloto.pronto = True
        # E AGORA O CONTROLE QUE RECUSOU SAI DA MESA. Quem fica herda a coluna 1.
        MESA["estado"] = SEM_O_DO_CABO
        GLib.timeout_add(2300, um_saiu)
        return False

    def um_saiu() -> bool:
        # ~4 tiques depois da troca: a mesa do piloto já refez as posições.
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-um-sair"))
        fora["mesa-de-um-so"] = [f"{c['pref']}:{c['uniq']}"
                                 for c in piloto._mesa_de_agora]
        fora["chaves-do-deposito"] = sorted(piloto._recados)
        MESA["estado"] = ESTADO
        GLib.timeout_add(1300, voltou_a_mesa)
        return False

    def voltou_a_mesa() -> bool:
        # O CONTROLE VOLTA. O aviso é dele, e volta ao cartão dele — o depósito
        # nunca perdeu o endereço, só a coluna a que ele correspondia.
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
    # O RELÓGIO DE SEGURANÇA GUARDA O SEU `id`, e isso NÃO é zelo — é um defeito
    # que esta régua causou e que foi medido em 02/09/2026. Sem o
    # `source_remove`, este `Gtk.main_quit` fica pendente depois de a fixture
    # terminar e dispara DENTRO do laço do PRÓXIMO teste de GUI do mesmo
    # processo: rodando esta régua junto das outras que tocam o piloto, as ONZE
    # medições do `test_o_pintor_acende_a_classe_e_apaga_as_irmas` morreram com
    # *"o WebKit não respondeu em 20 s"* — e o pintor está certo, ele nunca teve
    # 20 s. Aos pares os dois passavam, porque a bomba só chega ao vizinho
    # quando há trabalho suficiente entre os dois.
    #
    # A LINHA FICA, e o NÚMERO que estava aqui NÃO SE SUSTENTA. O comentário
    # afirmava, como medição, que arrancar só o `source_remove` fazia a leva
    # "voltar a 322 com os mesmos 11 erros". Arrancada exatamente esta linha e
    # nada mais, e rodada a mesma leva (os arquivos que citam `hefesto_vivo`),
    # o resultado foi **330 passed** — o mesmo do arquivo íntegro — com ZERO
    # ocorrências de *"o WebKit não respondeu"*. Medido em 02/09/2026 sobre
    # `onda/abas-0209`, e a auditoria da véspera mediu o mesmo em 2 de 2 voltas.
    #
    # O QUE O NÚMERO DESCREVIA É UMA COINCIDÊNCIA DE FASE: a bomba só alcança o
    # vizinho se cair DENTRO de um `Gtk.main()` alheio, e a leva inteira fecha
    # hoje em ~30 s — menos que os 38 s do relógio. Escrito como comportamento
    # determinístico, ele ensina o contrário do que quer: quem tentar reproduzir
    # conclui que a linha é supérflua e a apaga. Ela não é — um `timeout_add` de
    # 38 s pendente depois da fixture é bomba real, e desarmá-lo é higiene certa
    # por si só, com número ou sem.
    #
    # E ELA MUDOU DE LUGAR: agora mora num `finally`, com o `destroy()` da
    # janela e a devolução dos dublês. Se o roteiro levantar dentro do
    # `Gtk.main()`, era exatamente a limpeza que não acontecia.
    guarda = GLib.timeout_add(int(30000 + VENCE_EM_S * 1000), Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        # E O PILOTO TAMBÉM PARA. O tique dele é um `timeout_add` de 500 ms que
        # se reagenda para sempre; deixá-lo vivo faria esta janela pintar por
        # cima de todo laço GTK que vier depois, no mesmo processo.
        piloto.pronto = False
        piloto.tela.janela.destroy()
        # E OS TRÊS SÍMBOLOS DE MÓDULO VOLTAM. Ver a nota na instalação deles.
        (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado,
         hv.SEGUNDOS_DO_RECADO) = guardado
        MESA["estado"] = ESTADO
    fora["segundos-do-produto"] = fora_do_produto
    assert "depois-de-vencer" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}")
    return fora


def _frases(leitura: object) -> list[str]:
    assert isinstance(leitura, dict), leitura
    return [r["texto"] for r in leitura["recados"]]


# --------------------------------------------------------------------------
# 0. o clique aconteceu e o produto recusou — senão não há o que medir
# --------------------------------------------------------------------------
def test_o_gesto_recusou_dizendo(medido: dict) -> None:
    assert medido["clique"] == "cliquei", medido["clique"]
    desfechos = medido["desfechos"]
    assert isinstance(desfechos, dict)
    assert "02-controles.html:mudo" in desfechos, (
        f"o clique não chegou ao gesto — os desfechos foram {desfechos}")
    classe, frase = desfechos["02-controles.html:mudo"]
    assert classe == "recusou dizendo", (classe, frase)
    assert frase.startswith("RuntimeError:"), frase


# --------------------------------------------------------------------------
# 1. a frase chega ao DOM
# --------------------------------------------------------------------------
def test_a_frase_da_recusa_chega_ao_dom(medido: dict) -> None:
    """Ao DOM que ela olha — não ao `desfechos`, não ao `stderr`."""
    assert _frases(medido["antes"]) == [], (
        "a tela já tinha recado antes do clique — a medição não vale")
    frases = _frases(medido["logo-depois"])
    assert len(frases) == 1, (
        f"depois do clique recusado a tela mostra {frases!r}. Um botão que "
        f"aceita o clique e não diz nada é o defeito mais caro desta casa: o "
        f"segundo clique parece o primeiro.")
    # A FRASE É A DO DONO, E NÃO UMA DAQUI — 04/09/2026, S-05. Até hoje esta
    # linha casava um pedaço do `RuntimeError` fixo do gesto; o ato do
    # microfone traz a frase do DAEMON, que diz QUAL das duas metades faltou, e
    # o gesto a repassa por `frase_do_ato_do_microfone`. O que a régua cobra
    # agora é o ATRAVESSAR — a frase que o dublê devolveu chegou ao DOM.
    assert RECUSA_DO_ATO in frases[0], frases[0]


# --------------------------------------------------------------------------
# 2. no cartão daquele controle, e não no do vizinho
# --------------------------------------------------------------------------
def test_a_frase_pousa_no_cartao_de_quem_foi_clicado(medido: dict) -> None:
    leitura = medido["logo-depois"]
    assert isinstance(leitura, dict)
    recado = leitura["recados"][0]
    assert recado["chave"] == CHAVE_P1, (
        f"o recado foi endereçado a {recado['chave']!r}; o clique foi no "
        f"controle {CHAVE_P1} (o `uniq` normalizado, e não a coluna `p1`)")
    assert recado["dentro_de"] == "p1", (
        f"a frase está dentro de {recado['dentro_de']!r} — na mesa de quatro, a "
        f"recusa de um controle no cartão do vizinho é pior que recusa nenhuma")


# --------------------------------------------------------------------------
# 3. sobrevive à repintura — aos tiques e à troca de bloco
# --------------------------------------------------------------------------
def test_o_aviso_sobrevive_aos_tiques(medido: dict) -> None:
    """~6 repinturas depois do clique a frase continua na tela."""
    frases = _frases(medido["depois-de-seis-tiques"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"a frase sumiu na repintura: {frases!r}. Uma frase que só existe no "
        f"instante do clique não é vista por ninguém.")


def test_o_aviso_volta_quando_a_pintura_troca_o_bloco(medido: dict) -> None:
    """A pintura troca blocos inteiros — o aviso tem de renascer no tique."""
    assert medido["matei-o-cartao"] == "0", (
        f"a simulação não levou o aviso embora ({medido['matei-o-cartao']!r}) — "
        f"sem isso este teste passa sobre nada")
    frases = _frases(medido["depois-da-troca-de-bloco"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"o aviso não voltou depois de o bloco ser trocado: {frases!r}. É o "
        f"tique que o recria, lendo o depósito — sem isso ele morre com o "
        f"primeiro bloco que a pintura substituir.")


# --------------------------------------------------------------------------
# 4. o SEGUNDO clique responde — que é o defeito de origem desta frente
# --------------------------------------------------------------------------
def test_o_segundo_clique_tambem_responde_na_tela(medido: dict) -> None:
    """O enunciado desta frente em uma linha: *o segundo clique de um gesto
    continua sem resposta nenhuma na tela dela*. Aqui ele responde."""
    assert medido["segundo-clique"] == "cliquei", medido["segundo-clique"]
    frases = _frases(medido["depois-do-segundo-clique"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"o segundo clique deixou a tela em {frases!r}. Um segundo clique que "
        f"parece o primeiro é o botão que responde calado — e é ele que faz "
        f"quem clica concluir que funcionou.")


# --------------------------------------------------------------------------
# 4b. A PINTURA É NA HORA — com o tique parado, só o clique pode repor a frase
# --------------------------------------------------------------------------
def test_a_frase_aparece_no_clique_e_nao_no_proximo_tique(medido: dict) -> None:
    """O meio segundo até o próximo tique basta para ela clicar de novo.

    POR QUE A MEDIÇÃO PARA O TIQUE: porque sem parar ela não mede nada. A
    entrega "deposita a frase E pinta na hora" foi vendida como item próprio e
    atravessou a auditoria de 02/09 SEM RÉGUA — arrancar o `self._js(...)` de
    `_recusou_dizendo` deixava os oito testes verdes, porque a leitura aos
    700 ms já pegava a repintura de 500 ms. Medido dentro da página com
    `MutationObserver`, a diferença é real: **2 ms com a pintura imediata, ~300
    ms sem ela**. Aqui a régua a torna binária: com o tique parado, a única
    coisa que pode repor a frase é o clique.
    """
    assert medido["terceiro-clique"] == "cliquei", medido["terceiro-clique"]
    assert medido["apaguei-os-recados"] == "0", (
        f"a tela não foi zerada antes do clique ({medido['apaguei-os-recados']!r})"
        f" — sem isso esta régua passa sobre uma frase que já estava lá")
    frases = _frases(medido["sem-tique-depois-do-clique"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"com o tique parado a tela ficou em {frases!r}. A recusa só apareceria "
        f"na próxima repintura — e meio segundo de silêncio basta para ela "
        f"clicar de novo achando que o primeiro clique não pegou, que é o "
        f"defeito de origem deste canal e não um detalhe de acabamento.")


# --------------------------------------------------------------------------
# 4c. O RECADO É DO CONTROLE, E NÃO DA COLUNA — e isso só aparece no TEMPO
# --------------------------------------------------------------------------
def test_o_recado_e_do_endereco_e_nao_da_posicao(medido: dict) -> None:
    """O controle que recusou SAI da mesa e o vizinho herda a coluna 1.

    O DEFEITO QUE ESTA RÉGUA IMPEDE, medido em 02/09/2026 na base: o depósito
    era `{pref: frase}` e `mesa_viva.mesa_do_estado` enumera os conectados de 1
    A CADA TIQUE (*"o `pref` continua sendo a POSIÇÃO … e `jogador` continua
    sendo a IDENTIDADE"*). Com dois controles na mesa, recusa no 🎙 do `p1` (o
    do cabo), o do cabo saindo: o cartão de quem FICOU passava a mostrar, por
    até 30 s, uma frase que termina em *"ou este controle saiu da mesa"* —
    sobre outro controle. É o `test_a_frase_pousa_no_cartao_de_quem_foi_clicado`
    um nível acima: ali o endereçamento é conferido num INSTANTE, e num instante
    a coluna ainda é de quem foi clicado.
    """
    assert medido["mesa-de-um-so"] == [f"p1:{UNIQ_P2}"], (
        f"a mesa do piloto não trocou de dono ({medido['mesa-de-um-so']!r}) — "
        f"sem a troca esta régua passa sobre nada")
    assert medido["chaves-do-deposito"] == [CHAVE_P1], (
        f"o depósito guardou {medido['chaves-do-deposito']!r}; a chave tem de "
        f"ser o endereço do controle que recusou, e ele não mudou")
    leitura = medido["depois-de-um-sair"]
    assert isinstance(leitura, dict)
    frases = _frases(leitura)
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"o aviso sumiu quando a mesa mudou: {frases!r}. Ele é dela e vence "
        f"pelo relógio — não pela ida e volta de um controle.")
    recado = leitura["recados"][0]
    assert recado["dentro_de"] == "", (
        f"a frase ficou dentro do cartão {recado['dentro_de']!r}, que agora é de "
        f"{UNIQ_P2} — o controle que recusou já saiu da mesa. A recusa de um "
        f"controle no cartão de outro é a tela AFIRMANDO o que não é, e é pior "
        f"que recusa nenhuma: ela acusa quem não fez nada.")


def test_o_aviso_volta_ao_cartao_quando_o_controle_volta(medido: dict) -> None:
    """E o endereço é o que o traz de volta ao lugar certo."""
    leitura = medido["depois-de-o-controle-voltar"]
    assert isinstance(leitura, dict)
    recado = leitura["recados"][0]
    assert recado["chave"] == CHAVE_P1, recado
    assert recado["dentro_de"] == "p1", (
        f"o controle voltou à mesa e o aviso dele ficou em {recado['dentro_de']!r}. "
        f"O depósito guarda o endereço; quem resolve a coluna é a mesa do tique, "
        f"e por isso o aviso reencontra o cartão sem ninguém reendereçá-lo.")


# --------------------------------------------------------------------------
# 5. e vence — é aviso, não estado
# --------------------------------------------------------------------------
def test_o_aviso_vence_e_some(medido: dict) -> None:
    """Decisão dela: *"a frase de recusa SOME depois de um tempo (…) ~30 s"*.

    A LEITURA VEM DEPOIS DO SEGUNDO CLIQUE de propósito: ele renova o depósito,
    e sem essa renovação a régua chegava aqui com o DOM já vazio pela troca de
    bloco — verde sobre nada.
    """
    frases = _frases(medido["depois-de-vencer"])
    assert frases == [], (
        f"passados {VENCE_EM_S:.0f} s a tela ainda mostra {frases!r}. Aviso que "
        f"não vence virou estado, e a tela passa a afirmar uma recusa velha.")


def test_o_prazo_do_produto_e_o_que_ela_decidiu(medido: dict) -> None:
    """E o PRAZO tem dono — não só o mecanismo.

    O MECANISMO estava guardado e o VALOR não: a fixture encolhe
    `SEGUNDOS_DO_RECADO` para poder ver a frase vencer sem ficar meio minuto
    parada, e com isso trocar `30.0` por `3.0` ou por `300.0` deixava a régua
    inteira verde. Era a única coisa deste canal que veio direto de uma decisão
    dela — *"a frase de recusa SOME depois de um tempo — ~30 s e desaparece. É
    aviso, não estado."* (02/09/2026) — e a única sem ninguém a cobrar.

    O valor abaixo é lido do módulo ANTES de a fixture o encolher.
    """
    assert medido["segundos-do-produto"] == 30.0, (
        f"o produto faz a recusa viver {medido['segundos-do-produto']} s; ela "
        f"decidiu ~30 s. Este número não é de acabamento — é o que separa um "
        f"aviso de um estado, e mudá-lo é decisão dela, não de quem passa aqui.")


# --------------------------------------------------------------------------
# 6. o instrumento não entra na conta da régua do mockup
# --------------------------------------------------------------------------
def test_o_aviso_nao_conta_como_campo_da_pagina(medido: dict) -> None:
    """Se o aviso tivesse `data-campo`, a régua mediria o próprio instrumento."""
    antes, com_aviso = medido["antes"], medido["logo-depois"]
    assert isinstance(antes, dict) and isinstance(com_aviso, dict)
    assert antes["enderecos"] == com_aviso["enderecos"], (
        f"a página tinha {antes['enderecos']} endereços de pintura e passou a "
        f"ter {com_aviso['enderecos']} com o aviso na tela. O `LER_CAMPOS` varre "
        f"`data-campo`/`data-papel`/`data-hef`: o aviso não pode carregar "
        f"nenhum dos três, ou a régua do mockup passa a contá-lo como campo.")
