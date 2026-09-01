#!/usr/bin/env python3
"""O PILOTO ÚNICO: uma janela, as dez abas, tudo pintado pelo despachante.

DECISÃO DELA, 01/09/2026: *"melhor assim mesmo. aba a aba. igual vc falou. mas
já usando o trabalho do specs pra fazermos tudo de uma vez. já o trampo final."*
E depois: *"a única que não faremos, só deixamos o botão levando pra ela, é a de
lançadores."*

O QUE ELE SUBSTITUI, e é o motivo de existir: até aqui havia CINCO pilotos, um
por aba — `controles_vivos`, `jogar_vivo`, `conexoes_vivas`, `perfis_vivos`,
`sistema_viva`. Cada um abre a sua página e morre nela; clicar na tira levava a
uma página ESTÁTICA, o mockup sem dado. O produto que ela pediu é uma janela em
que as dez abas estão vivas e a navegação entre elas funciona.

COMO ELE SABE O QUE PINTAR: pelo nome do arquivo à vista. O `load-changed` do
WebView chega em toda carga, e o `pacotes.pacote_da_pagina()` devolve o pacote
daquela página — ou `None`, que quer dizer "esta aba ainda não tem quem a pinte"
e é diferente de um pacote vazio.

AS DUAS LÍNGUAS, e a tradução mora AQUI de propósito:

    o daemon fala `uniq`   — `d4:2f:00:00:…`, o endereço do aparelho
    o desenho fala `pref`  — `p1`, `p2`, que é o que o `data-controle` traz

As funções de pacote falam a língua do daemon, porque é dele que leem. A tela
fala a língua do desenho, porque é o mockup dela. Traduzir no pacote misturaria
as duas e faria cada aba carregar a mesa; traduzir no JS espalharia a regra por
dez páginas. Fica no piloto, que é quem já tem a mesa na mão.
"""
from __future__ import annotations

import argparse
import contextlib
import pathlib
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
import mesa_viva  # noqa: E402
import onde  # noqa: E402
import pacotes  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402
from pacotes import ponte  # noqa: E402

from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402

#: A PRIMEIRA PÁGINA é a Jogar, que é a primeira da tira. Não é escolha de
#: gosto: é a aba que o `.desktop` dela abre.
PRIMEIRA = "01-jogar.html"

#: O tique da pintura. 500 ms é o mesmo do `controles_vivos`, medido lá: o custo
#: por volta ficou em 0,9% do orçamento, com IPC de mediana 0,8 ms.
TIQUE_MS = 500

#: OS QUATRO LUGARES DA MESA DO DESENHO. O HTML nasce com eles todos — dois
#: conectados e dois vazios, por decisão dela em 31/08 — e o produto tem de
#: apagar o que a mesa de agora não preenche.
TODOS_OS_LUGARES = {"p1", "p2", "p3", "p4"}

#: A aba que NÃO tem pacote, por decisão dela — só o botão que leva a ela.
SEM_PACOTE = {"07-lancadores.html"}

#: O QUE A GUARDA DE CARGA ACEITA. Os pilotos de uma aba só passavam o nome
#: dela — `"Controles"` — e a guarda matava a janela em qualquer outra página.
#: Aqui as DEZ são legítimas, então o esperado é o que as dez compartilham:
#:
#:     Hefesto — aba JOGAR (mockup 26/08/2026)
#:     Hefesto — aba GATILHOS (mockup 26/08/2026)
#:
#: A guarda casa por SUBSTRING, e `"Jogar"` não casa com `"aba JOGAR"` — foi o
#: que matou a primeira execução deste piloto. Continua servindo para o que ela
#: existe: uma página que NÃO é do mockup (um erro de carga, um `about:blank`)
#: não tem este título e a guarda a pega.
TITULO_DE_QUALQUER_ABA = "Hefesto — aba "

#: O BOOTSTRAP: uma função de pintura, genérica, para as dez.
#:
#: Ela NÃO sabe nada de nenhuma aba — recebe endereço e valor e escreve. Toda a
#: inteligência está do lado Python, nos pacotes, que são puros e testáveis sem
#: abrir janela. Foi assim que 143 valores puderam ser medidos antes de existir
#: esta janela.
#:
#: O CONTADOR É O QUE IMPEDE O VERDE SOBRE NADA. `pintar()` devolve quantos
#: valores escreveu, e o piloto imprime. Uma aba que devolve 0 com pacote não
#: vazio é endereço que não existe na página — e é o defeito que fez a
#: `06-navegacao` publicar zero endereços em 01/09 sem ninguém ver.
BOOTSTRAP = r"""
(function(){
  window.__hef = window.__hef || {};
  function escrever(el, v){
    if(!el) return 0;
    const t = (v === null || v === undefined || v === '') ? '—' : String(v);
    // O ALVO PADRÃO É O TEXTO. `data-hef-alvo` desvia para um atributo quando a
    // tela precisa de outra coisa — a largura de uma barra, o `value` de um
    // campo. Sem isso, pintar uma barra escreveria o número DENTRO dela.
    const alvo = el.dataset.hefAlvo || 'texto';
    if(alvo === 'largura'){
      if(el.style.width !== t + '%'){ el.style.width = t + '%'; return 1; }
      return 0;
    }
    if(alvo === 'fundo'){
      if(el.style.background !== t){ el.style.background = t; return 1; }
      return 0;
    }
    if(alvo === 'valor'){ if(el.value !== t){ el.value = t; return 1; } return 0; }
    if(el.textContent !== t){ el.textContent = t; return 1; }
    return 0;
  }
  // OS TRÊS VOCABULÁRIOS DE ENDEREÇO, e nenhum se aposenta. Medido em
  // 01/09/2026, nas dez páginas publicadas:
  //
  //     data-campo   oito abas          o mais novo, e o do piloto único
  //     data-papel   só a Vibração (28) um PAR com `data-lado`
  //     data-hef     só a Perfis (77)   nomes com ponto: `perfis.linha.nome`
  //
  // Cada um nasceu com o piloto da sua aba, e os pilotos ainda os usam. Trocar
  // tudo por um só renomearia 105 endereços e quebraria cinco pilotos vivos
  // para ganhar consistência de nome — o piloto único aceita os três, que é o
  // que custa uma linha aqui.
  function achar(raiz, chave){
    const esc = chave.replace(/"/g, '\\"');
    return raiz.querySelectorAll(
      '[data-campo="' + esc + '"],[data-papel="' + esc + '"],[data-hef="' + esc + '"]');
  }
  window.__hef.pintar = function(p){
    let n = 0;
    // A FITA SE TROCA INTEIRA, e não campo a campo: o número de chips muda com
    // a mesa, e não há endereço para um chip que ainda não existe.
    if(p.fita){
      const f = document.querySelector('.fita');
      if(f && f.outerHTML !== p.fita){ f.outerHTML = p.fita; n += 1; }
    }
    // 1. OS CAMPOS DA MESA — soltos no documento, valem para a página toda.
    for(const [k, v] of Object.entries(p.mesa || {})){
      const alvos = achar(document, k);
      // UMA LISTA SE DISTRIBUI pelos elementos de mesmo endereço, na ordem.
      // É como a aba Conexões mostra os achados do exame e a Perfis a lista de
      // perfis: N blocos iguais, um por item, todos com o mesmo `data-campo`.
      // Sem isto o pacote teria de emitir `achado-0`, `achado-1`… e o gerador
      // teria de saber de antemão QUANTOS itens o exame acha.
      if(Array.isArray(v)){
        alvos.forEach(function(el, i){ n += escrever(el, i < v.length ? v[i] : ''); });
        continue;
      }
      if(v !== null && typeof v === 'object') continue;
      for(const el of alvos) n += escrever(el, v);
    }
    // 1b. OS LUGARES VAZIOS ganham a marca do desenho. `data-conectado` e a
    // classe `off` são o que o gerador escreve nos dois lugares que ela mandou
    // deixar desconectados — usar as MESMAS marcas é o que faz o produto
    // parecer o desenho, em vez de inventar um terceiro estado.
    for(const pref of (p.vazios || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        if(el.dataset.conectado !== 'nao'){  // (noqa-acento) valor do atributo
          el.dataset.conectado = 'nao'; n += 1;  // (noqa-acento) idem
        }
        if(!el.classList.contains('off')){ el.classList.add('off'); }
        el.classList.remove('alvo');
      }
    }
    // 2. OS CAMPOS POR CONTROLE — dentro do bloco daquele `data-controle`.
    for(const [pref, campos] of Object.entries(p.colunas || {})){
      for(const raiz of document.querySelectorAll('[data-controle="' + pref + '"]')){
        for(const [k, v] of Object.entries(campos)){
          if(v !== null && typeof v === 'object') continue;
          for(const el of achar(raiz, k)) n += escrever(el, v);
        }
      }
    }
    return n;
  };
  // O OUVINTE DE CLIQUE, e ele é UM SÓ para a página inteira. Um
  // `addEventListener` por botão seria N ouvintes a religar a cada repintura —
  // e um botão que a pintura substitua perde o seu, calado. Delegar no
  // documento sobrevive a qualquer troca de HTML, que é o que a fita faz a
  // cada mudança de mesa.
  if(!window.__hef.ouvindo){
    window.__hef.ouvindo = true;
    // O `change` ALÉM DO `click`, e ele é o que faltava para metade dos botões
    // sem dono. Um `<select>` não se "clica" no sentido útil — ele MUDA; e um
    // `<input>` de texto nunca dispara clique com o valor novo. Medido em
    // 01/09/2026: os quatro campos do editor da aba Perfis, os selects da
    // Conexões e o nome da face nova ficaram sem dono por isto, e o relato dos
    // agentes nomeia a causa uma vez por aba — *"o ouvinte manda `texto:
    // alvo.textContent`, que num `<input>` é vazio"*.
    document.addEventListener('change', function(ev){ manda_do_alvo(ev); }, true);
    document.addEventListener('click', function(ev){
      // Os quatro atributos que marcam algo CLICÁVEL nas dez páginas. Eles já
      // existiam — cada piloto de aba usava o seu.
      manda_do_alvo(ev);
    }, true);
  }
  function manda_do_alvo(ev){
      const alvo = ev.target.closest(
        '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
        '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
        '.r-aplicar,.r-salvar,.r-importar,.r-exportar');
      if(!alvo) return;
      const d = alvo.dataset;
      // DE QUAL CONTROLE, e sem isto o gesto é ambíguo: a mesa tem quatro
      // colunas iguais e um "Desligar" clicado na terceira não diz em qual
      // barra de luz mexer. O `closest` sobe até o bloco do controle — é o
      // mesmo `data-controle` que a pintura usa para achar onde escrever.
      // O RODAPÉ ENDEREÇA POR CLASSE, e não por `data-`: ele mora no
      // `topo.html`, o esqueleto das dez, e um `data-gesto` ali mudaria as dez
      // páginas de uma vez. A classe `r-<nome>` já era o endereço dele no
      // `jogar_vivo.py` — este é o quarto vocabulário, e é o último.
      const doRodape = (alvo.className.match(/\br-([a-z]+)\b/) || [])[1];
      const dono = alvo.closest('[data-controle],[data-uniq]');
      manda({
        gesto: d.gesto || d.hefGesto || d.papel || doRodape || 'clique',
        modo: d.modo || '', forca: d.forca || '', player: d.player || '',
        lado: d.lado || '', campo: d.campo || '', hef: d.hef || '',
        hex: d.hex || '', sensor: d.sensor || '', rota: d.rota || '',
        mudo: d.mudo || '', micModo: d.micModo || '', v: d.v || '',
        controle: dono ? (dono.dataset.controle || dono.dataset.uniq || '') : '',
        // O VALOR, e ele é o que o `textContent` não alcança: num `<input>` o
        // texto é vazio, e num `<select>` é a lista INTEIRA de opções. Sem
        // isto, um campo digitado chega ao Python sem o que ela digitou.
        valor: (('value' in alvo) ? String(alvo.value ?? '') : ''),
        // `selectedOptions` dá o rótulo VISÍVEL da opção escolhida — o que ela
        // leu na tela — enquanto `value` dá a chave do contrato. Os dois vão,
        // porque o gesto precisa de um e a mensagem de erro do outro.
        rotulo: (alvo.selectedOptions && alvo.selectedOptions[0]
                 ? alvo.selectedOptions[0].textContent.trim() : ''),
        tipo: (alvo.tagName || '').toLowerCase(),
        evento: ev.type,
        texto: (alvo.textContent || '').trim().slice(0, 60),
      });
  }
  function manda(o){
    o.pagina = location.pathname.split('/').pop();
    window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o));
  }
  return 'ok';
})();
"""


#: A TABELA LOCAL MORREU em 01/09/2026, e a razão é de processo: ela era um
#: dicionário num arquivo só, e ligar as dez abas em paralelo significaria oito
#: pessoas editando a MESMA linha. Cada pacote passa a declarar os seus com
#: `@gesto(...)`, no próprio arquivo — território exclusivo, zero merge.
#:
#: Os dois que moravam aqui foram para `a09_sistema.py` e `a10_perfis.py`.


def _fita(mesa: list[dict]) -> str:
    """A fita de chips com a mesa VIVA, pelo mesmo gerador do desenho.

    `monta.fita()` é o dono dela nas dez páginas. Passar `mesa` é obrigatório:
    sem o argumento ele cai nos `CONECTADOS` do mockup, que são derivados no
    IMPORT e nunca recalculados — trocar `monta.MESA` de fora não alcança.
    """
    if not mesa or any(not c.get("cor") for c in mesa):
        # A COR AINDA NÃO CHEGOU. O leitor do plástico é perguntado em thread e
        # a mesa nasce sem cor — `monta.fita` levanta `SystemExit: colorway ''
        # não existe` nesse instante. Devolver "" deixa a fita como está e o
        # tique seguinte a pinta; erguer aqui derrubaria a aba inteira por meio
        # segundo de espera.
        #
        # `SystemExit` NÃO é `Exception` — herda de `BaseException`, e um
        # `except Exception` passa ao lado. Foi o que aconteceu na primeira
        # execução: o piloto morreu com a mensagem do portão de cores, que é um
        # portão e está certo em erguer.
        return ""
    try:
        import monta

        return monta.fita(ativo=(mesa[0]["pref"] if mesa else "todos"), mesa=mesa)
    except (Exception, SystemExit):
        return ""


#: O SELETOR DO CLIQUE SINTÉTICO, e ele cobre os QUATRO vocabulários das dez
#: páginas — `data-gesto`, `data-hef-gesto`, `data-papel` e a classe `r-<nome>`
#: do rodapé, que endereça assim porque mora no esqueleto compartilhado.
#:
#: Um seletor que cobrisse só o primeiro daria "clicou" sobre um `null` — e
#: `null.click()` não levanta com o `||{click(){}}`, então a prova passaria em
#: silêncio sobre um botão nunca tocado. Foi assim que o `--prova-gesto` da
#: Controles deu verde sobre dois botões mortos em 29/08.
SELETOR = ("(document.querySelector('[data-gesto=\"%s\"],[data-hef-gesto=\"%s\"],"
           "[data-papel=\"%s\"],.r-%s')||{click(){}}).click()")

#: O MÉTODO LENTO DE CADA GESTO, para a prova esperar o tempo dele. Só os que
#: passam do padrão precisam de linha aqui.
_METODO_DO_GESTO = {
    "atualizar": "daemon.reload", "modo-dualsense": "gamepad.emulation.set",
    "modo-xbox": "gamepad.emulation.set", "modo-navegacao": "mouse.emulation.set",
    "hefesto": "native.mode.set", "ativar": "profile.switch",
    "aplicar": "profile.apply_draft", "reconectar": "coop.sync",
}

#: OS GESTOS QUE MEXEM NA MÁQUINA DELA, e que a prova botão a botão NÃO clica
#: sozinha. Não é timidez: `desligar` para o daemon e ela fica sem controle no
#: meio do trabalho; `restaurar-de-fabrica` apaga configuração; `reiniciar`
#: derruba a sessão do daemon. Uma régua não mexe na máquina de alguém para
#: provar que sabe clicar.
#:
#: Para incluí-los, `--incluir-perigosos` — e aí é escolha de quem roda.
#: A chave é `(página, gesto)`, e a qualificação NÃO é preciosismo: `modo` na
#: Navegação liga a emulação de mouse e MEXE NO CURSOR DELA — na tela dela,
#: enquanto ela trabalha. O mesmo `modo` nos Gatilhos escolhe um efeito e é
#: inócuo. Uma lista por nome cru trataria os dois igual, e a escolha seria
#: entre não provar o seguro ou estragar o trabalho dela.
PERIGOSOS = {
    ("09-sistema.html", "desligar"), ("09-sistema.html", "reiniciar"),
    ("09-sistema.html", "restaurar-de-fabrica"), ("09-sistema.html", "refazer-proton"),
    ("09-sistema.html", "autostart"),
    ("10-perfis.html", "remover"), ("10-perfis.html", "novo"),
    ("10-perfis.html", "voltar-a-de-ontem"),
    # O CURSOR É DELA. Ligar a emulação de mouse move o ponteiro na tela em que
    # ela está trabalhando — é o mesmo motivo de toda janela desta casa nascer
    # com `--oculta`.
    ("06-navegacao.html", "modo"),
}


def _achatar(o, prefixo="") -> dict:
    """O estado do daemon como `{caminho: valor}` — para comparar antes/depois.

    Achatar é o que torna a comparação LEGÍVEL: sem isso, "o estado mudou" seria
    um diff de dois dicionários aninhados de 49 chaves, e ninguém leria qual
    campo se mexeu. Com isso, o relato diz
    `controllers.0.lightbar_rgb: [0,0,255] → [126,184,212]`.
    """
    fora = {}
    if isinstance(o, dict):
        for k, v in o.items():
            fora.update(_achatar(v, f"{prefixo}.{k}" if prefixo else str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o[:4]):
            fora.update(_achatar(v, f"{prefixo}.{i}"))
    else:
        fora[prefixo] = o
    return fora


#: OS CAMPOS QUE MUDAM SOZINHOS a cada tique — o relógio do daemon, os contadores
#: de força-feedback, a posição dos analógicos. Compará-los faria TODO gesto
#: parecer que mudou alguma coisa, que é o mesmo que não medir nada.
RUIDO = ("visto_ha_s", "ha_s", "_count", "nascimento", "age_sec", "uptime",
         "inputs.", "motion_", "forwards", "counters.", "_ultimos_",
         # OS EIXOS NA RAIZ DO STATE, e não só dentro de `inputs`. O daemon
         # publica `lx`, `ly`, `rx`, `ry`, `l2_raw` e `r2_raw` nos DOIS lugares,
         # e o filtro só cobria o segundo. Um analógico em repouso oscila um
         # ponto — `ry: 128 → 129` — e isso fazia um botão qualquer parecer que
         # mudou o aparelho. Medido em 01/09 na aba Conexões: o `sala-altura`
         # deu ✓ sobre o tremor do polegar dela.
         "lx", "ly", "rx", "ry", "l2_raw", "r2_raw", "buttons",
         "battery_pct", "bt_mic")


def _pagina_da_uri(uri: str | None) -> str:
    """O nome do arquivo à vista, ou `""`.

    É o que o despachante usa de chave, e é o que o `load-changed` entrega. Sai
    da URI e não de um estado que o piloto guarde: guardar seria uma segunda
    fonte da verdade sobre em que aba a janela está, e as duas divergiriam na
    primeira navegação que falhasse no meio.
    """
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


class Piloto:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.agendado = False
        self.relatou = False
        self.pagina = PRIMEIRA
        self.voltas = 0
        #: Quantos valores cada aba pintou, na ordem em que foram visitadas. É o
        #: relato do fim, e é o que distingue "a aba não tem dado" de "a aba tem
        #: pacote e nenhum endereço casou".
        self.pinturas: dict[str, list[int]] = {}
        self.visitadas: list[str] = []
        self.custos: list[float] = []
        #: O que ESTE processo mandou ao daemon, e o que recusou por falta de
        #: dono. Os dois contados: sem o segundo, "nada aconteceu" e "não havia
        #: quem atendesse" ficariam indistinguíveis.
        self.gestos: list[dict] = []
        self.aplicados: list[str] = []
        self.recusados: list[str] = []
        #: A mesa e o contexto do último tique — é o que o gesto recebe. Sem
        #: eles, um clique que chega entre dois tiques não teria com que
        #: trabalhar, e resolver o `uniq` na hora exigiria um IPC a mais por
        #: clique.
        #: O que a prova botão a botão mediu, um por gesto.
        self.provas: list[dict] = []
        self._fila: list[str] = []
        self._mesa_de_agora: list[dict] = []
        self._ctx_de_agora = pacotes.Contexto(state={})
        self.leitor = mesa_viva.LeitorDeCor(ligado=not args.sem_cor)
        #: Os `uniq` já perguntados ao leitor de cor. Sem esta trava, cada tique
        #: abriria uma thread nova para o mesmo controle — 2 por segundo.
        self.perguntados: set[str] = set()

        self.tela = JanelaDaAba(
            arquivo=onde.pagina(PRIMEIRA, publicado=True),
            titulo_esperado=TITULO_DE_QUALQUER_ABA,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._navegou,
            oculta=args.oculta,
            subtitulo="as dez abas, vivas",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        # O SEGUNDO OUVINTE, e ele precisa ser próprio: o `ao_sair_da_aba` da
        # biblioteca dispara UMA vez, na saída da aba desta janela. Daqui em
        # diante toda página é "fora da aba" e o callback não volta. Sem este
        # `connect`, Jogar → Gatilhos → Jogar não produziria evento nenhum e o
        # piloto ficaria pintando a página errada. É a mesma nota que o
        # `controles_vivos` carrega, e a razão é a mesma.
        self.view.connect("load-changed", self._carregou)

        # O SELETOR DE ARQUIVO É DA JANELA, e por isso é ligado AQUI. Os pacotes
        # são puros — um `import gi` neles obrigaria toda régua a ter GTK e o CI
        # a rodar com display. A ponte declara o ponto de extensão recusando; o
        # piloto o preenche ao subir.
        ponte.escolher_arquivo = self._escolher_arquivo
        ponte.salvar_arquivo = self._salvar_arquivo

    # -- o seletor de arquivo, que é do sistema ---------------------------
    def _dialogo(self, titulo: str, acao, rotulo: str, *, sugestao="", padrao="*"):
        """Um `FileChooserDialog` modal, e ele RODA NO LAÇO DO GTK.

        POR QUE `Gtk.Dialog.run()` E NÃO UM CALLBACK: o gesto está numa thread
        (os gestos correm fora do laço, porque `daemon.reload` leva 9,5 s), e
        precisa do caminho para seguir. `run()` bombeia o laço do GTK por
        dentro, então a janela continua viva enquanto ela escolhe.

        COM A JANELA OCULTA NÃO HÁ DIÁLOGO: uma `Gtk.OffscreenWindow` não tem
        onde pôr um modal, e abrir um sem pai o jogaria NA TELA DELA — que é
        exatamente o que `--oculta` existe para impedir. Nesse caso devolve
        `None`, e o gesto o lê como "cancelou".
        """
        if self.args.oculta:
            print(f"[seletor] {titulo}: a janela está oculta, não abro diálogo",
                  file=sys.stderr)
            return None
        dlg = Gtk.FileChooserDialog(title=titulo, transient_for=self.tela.janela,
                                    action=acao)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        rotulo, Gtk.ResponseType.ACCEPT)
        if sugestao:
            dlg.set_current_name(pathlib.Path(sugestao).name)
            with contextlib.suppress(Exception):
                dlg.set_current_folder(str(pathlib.Path(sugestao).parent))
        if padrao != "*":
            f = Gtk.FileFilter()
            f.set_name(padrao)
            f.add_pattern(padrao)
            dlg.add_filter(f)
        try:
            escolhido = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        finally:
            dlg.destroy()
        return escolhido

    def _escolher_arquivo(self, titulo: str, padrao: str = "*", **_):
        return self._dialogo(titulo, Gtk.FileChooserAction.OPEN, "Abrir", padrao=padrao)

    def _salvar_arquivo(self, titulo: str, sugestao: str = "", **_):
        return self._dialogo(titulo, Gtk.FileChooserAction.SAVE, "Guardar",
                             sugestao=sugestao)

    # -- os gestos ---------------------------------------------------------
    def _gesto(self, o: dict) -> None:
        """tela → Python, já em JSON. Quem recusa o que não é objeto é a ponte.

        O QUE ELE FAZ E O QUE NÃO FAZ, e a diferença é a regra desta casa: ele
        despacha o que tem DONO no daemon e RECUSA o resto **com o motivo na
        tela**. Um botão que responde calado quando não há quem atenda é a
        `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura — quem clica conclui que
        funcionou.
        """
        self.gestos.append(o)
        nome = str(o.get("gesto") or "")
        pagina = str(o.get("pagina") or self.pagina)  # (noqa-acento: verbo)  (nome de variável)
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.recusados.append(f"{pagina}:{nome}")
            print(f"[gesto sem dono] {pagina} · {nome} · {o.get('texto', '')!r}")
            return
        # O `uniq` É RESOLVIDO AQUI, e não dentro do gesto: a tela endereça por
        # `pref` (`p1`), o daemon por `uniq` (`d4:2f:00:00:…`), e a mesa que traduz é
        # do piloto. Cada gesto resolvendo por conta própria seria a mesma
        # tradução escrita nove vezes — e a nona estaria errada.
        pref = str(o.get("controle") or "")
        for c in self._mesa_de_agora:
            if c.get("pref") == pref or str(c.get("uniq") or "") == pref:
                o = {**o, "uniq": str(c.get("uniq") or "")}
                break

        # EM THREAD, e não no laço do GTK. MEDIDO em 01/09/2026, com o daemon
        # dela: `daemon.reload` leva **9,5 segundos** — `daemon.resume` leva 1
        # ms e `daemon.status` 57. Um gesto síncrono congelaria a janela inteira
        # por nove segundos e meio, sem nada na tela dizendo por quê, e quem
        # clicou concluiria que o app travou.
        def trabalhar() -> None:
            try:
                acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                # O `erro` é AMARRADO no argumento do lambda, e não capturado
                # do escopo: o `except ... as` do Python apaga o nome ao sair do
                # bloco, e o lambda roda DEPOIS, no laço do GTK. Sem a amarra é
                # `NameError` na hora de relatar a falha — o erro comendo o
                # relato do erro.
                GLib.idle_add(lambda x=erro: (print(f"[gesto falhou] {pagina} · {nome}: {x}",
                                                    file=sys.stderr), False)[1])
                return
            GLib.idle_add(lambda: (self._deu_certo(pagina, nome), False)[1])

        threading.Thread(target=trabalhar, daemon=True).start()

    def _deu_certo(self, pagina: str, nome: str) -> None:
        self.aplicados.append(f"{pagina}:{nome}")
        print(f"[gesto] {pagina} · {nome} → aplicado")

    # O `_ipc` CRU MORREU em 01/09/2026. Ele abria o socket à mão e montava o
    # JSON-RPC — reescrevendo o que o `app/ipc_bridge.py` já faz há meses, com
    # timeout pensado e a recusa do daemon traduzida em frase de tela. Quem
    # escreve agora é `pacotes/ponte.py`, e ele é UM caminho só.

    # -- navegação ---------------------------------------------------------
    def _navegou(self, titulo: str) -> None:
        """Ela clicou na tira. Aqui isso não pausa nada — é o ponto do piloto."""
        print(f"[navegou] {titulo}")

    def _carregou(self, _view, evento) -> None:
        from gi.repository import WebKit2

        if evento != WebKit2.LoadEvent.FINISHED:
            return
        nova = _pagina_da_uri(self.view.get_uri())
        if not nova or (nova == self.pagina and self.pronto):
            return
        self.pagina = nova
        if nova not in self.visitadas:
            self.visitadas.append(nova)
        # A PONTE MORRE A CADA CARGA — o `window.__hef` é do documento antigo.
        # Reinstalar é obrigatório, e esquecer isso é como uma aba nova nasce
        # muda sem uma linha de erro.
        self.pronto = False
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _instalar(self) -> None:
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _instalado(self, _valor, erro) -> None:
        if erro is not None:
            print(f"ERRO: o bootstrap não instalou em {self.pagina}: {erro}", file=sys.stderr)
            return
        self.pronto = True
        # O TIMER E A SAÍDA SÓ UMA VEZ, e a flag é própria. Testar `voltas == 0`
        # aqui não funciona: `_tique()` roda logo acima e já a incrementa, então
        # a condição era sempre falsa — a janela ficava viva para sempre, sem
        # tique periódico e sem relato. Medido na primeira execução deste piloto.
        self._tique()
        if not self.agendado:
            self.agendado = True
            GLib.timeout_add(TIQUE_MS, self._tique)
            self._agendar()

    # -- a pintura ---------------------------------------------------------
    def _contexto(self, st: dict) -> tuple[pacotes.Contexto, dict[str, str]]:
        """O contexto do tique, e o dicionário `uniq → pref` para traduzir."""
        ctx_conectados = [c for c in (st.get("controllers") or [])
                          if c.get("connected", True)]
        # A COR DO PLÁSTICO vem do leitor, que responde `{}` até a primeira
        # pergunta voltar — por isso a mesa nasce "Não sei" e vira "Starlight
        # Blue" na segunda remontagem. Perguntar é BLOQUEANTE (fala com o
        # aparelho), então vai em thread: no tique ela travaria a janela.
        for c in ctx_conectados:
            uniq = str(c.get("uniq") or "")
            if uniq and uniq not in self.perguntados:
                self.perguntados.add(uniq)
                threading.Thread(
                    target=self.leitor.perguntar, args=(uniq,), daemon=True
                ).start()
        conectados = ctx_conectados
        mesa = mesa_viva.mesa_do_estado(st, self.leitor.conhecidos())
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=conectados, estados={})
        return ctx, para_pref

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        try:
            st = mesa_viva.estado_do_daemon()
        except Exception as e:
            print(f"[daemon mudo] {e}", file=sys.stderr)
            return True

        try:
            ctx, para_pref = self._contexto(st)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return True
        # A MESA DE AGORA fica guardada para o gesto: um clique chega entre dois
        # tiques, e sem ela resolver o `uniq` custaria um IPC a mais por clique.
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx
        try:
            pacote = pacotes.pacote_da_pagina(self.pagina, ctx)
        except Exception as e:
            # UMA ABA QUE LEVANTA NÃO DERRUBA A JANELA. Ela para de pintar e o
            # motivo sai no relato — que é diferente de a tela congelar sem
            # dizer por quê, e é o estado que o `Contexto.por_uniq` já protege.
            print(f"[{self.pagina}] o pacote levantou: {e}", file=sys.stderr)
            return True
        if pacote is None:
            return True

        # A FORMA CANÔNICA E A TRADUÇÃO `uniq → pref`, as duas no despachante.
        # Ele é quem conhece as três palavras que as abas usam para a mesma
        # coisa (`colunas`, `cartoes`, `cards`) e o que cada uma deixa solto na
        # raiz. Repetir isso aqui seria um segundo dono da mesma regra.
        carga = pacotes.normalizar(pacote, para_pref)
        # O CABEÇALHO É DE TODAS AS ABAS, e não de nenhum pacote: a contagem e o
        # perfil ativo moram no `topo.html`, que é um só para as dez. Sem esta
        # linha os três campos ficavam vazios em TODA aba — cada pacote cuidava
        # da sua e ninguém cuidava do que era de todas.
        for chave, valor in pacotes.topo(ctx).items():
            carga["mesa"].setdefault(chave, valor)

        # A FITA É DE TODAS AS ABAS, e ela MENTE se não for repintada: o HTML
        # publicado traz os dois chips do mockup ("P1 · Cosmic Red · USB",
        # "P2 · Starlight Blue · BT"), e com UM controle no cabo a tela dizia
        # que havia dois, um deles no rádio. É a quinta reincidência do mesmo
        # defeito nesta casa — *uma frase que nomeia um controle fora da mesa* —
        # e a foto da aba Perfis o mostrou de novo em 01/09/2026, já com o topo
        # e a tabela corretos ao lado.
        carga["fita"] = _fita(ctx.mesa)

        # OS LUGARES VAZIOS RECEBEM TRAVESSÃO, e sem isto a tela MENTE. O HTML
        # publicado nasce com quatro colunas — a mesa do desenho, dois
        # conectados e dois vazios. Com UM controle na mesa, a coluna do P2
        # continuava mostrando o que o mockup escreveu: "Sony · Player 2 ·
        # Starlight Blue · BT · 64%". Visível na foto de 01/09, ao lado de um
        # topo que dizia "1 controle" e de uma fita já correta.
        #
        # É a sétima aparição do mesmo defeito nesta casa — *a tela afirmando um
        # controle que não está na mesa* — e a única cura que não depende de
        # cada aba lembrar-se dela é esta: quem pinta apaga o que sobra.
        chaves = set()
        for campos in carga["colunas"].values():
            chaves |= set(campos)
        vivos = set(carga["colunas"])
        apagar = sorted(TODOS_OS_LUGARES - vivos)
        for pref in apagar:
            carga["colunas"][pref] = dict.fromkeys(chaves, "—")
        # A MOLDURA TAMBÉM, e não só o texto: com os travessões escritos, o card
        # do P2 continuava com a borda de CONECTADO e os botões de máscara
        # acesos. Meio apagado é pior que aceso — quem olha lê a borda antes de
        # ler o campo.
        carga["vazios"] = apagar

        def contou(valor, erro) -> None:
            if erro is not None:
                print(f"[{self.pagina}] a pintura falhou: {erro}", file=sys.stderr)
                return
            try:
                n = int(str(valor))
            except (TypeError, ValueError):
                n = -1
            # O `-1` (página trocada no meio) NÃO entra na conta: contá-lo
            # como zero faria uma aba viva parecer muda na travessia.
            if n >= 0:
                self.pinturas.setdefault(self.pagina, []).append(n)

        # A GUARDA `window.__hef &&` NÃO É ZELO: entre o tique começar e o JS
        # rodar, a página pode ter trocado — e o `__hef` é do DOCUMENTO, morre
        # com ele. Medido em 01/09/2026, passeando pelas dez: duas abas
        # devolviam `TypeError: undefined is not an object` a cada travessia.
        # O `-1` diz "a página trocou no meio", que é diferente de "pintei
        # nada" — e o relato conta os dois separados.
        self.ponte.perguntar(
            f"(window.__hef && window.__hef.pintar({_json(carga)})) || -1", contou)
        self.voltas += 1
        self.custos.append((time.perf_counter() - t0) * 1000)
        return True

    # -- o roteiro e o relato ---------------------------------------------
    def _agendar(self) -> None:
        if self.args.passear:
            # O PASSEIO: clica a tira aba por aba, para provar que as dez
            # pintam. Sem ele o relato só teria a primeira — e "a aba abre" não
            # é o mesmo que "a aba pinta", que é a distinção inteira desta leva.
            for i, alvo in enumerate(sorted(pacotes.PACOTES)):
                GLib.timeout_add(
                    1200 + i * self.args.parada,
                    lambda a=alvo: (self._ir(a), False)[1],
                )
            total = 1600 + len(pacotes.PACOTES) * self.args.parada
        else:
            total = int(self.args.segundos * 1000)
        GLib.timeout_add(total, lambda: (self._relatar(), Gtk.main_quit(), False)[2])

    def _provar_cliques(self) -> None:
        """Cliques SINTÉTICOS nos gestos INÓCUOS, para provar o caminho.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato — o
        ouvinte delegado do bootstrap é o que responde. Clicar por coordenada é
        a armadilha que esta casa já pagou duas vezes, e a janela é Offscreen.

        SÓ OS INÓCUOS, e a lista é curta de propósito: `atualizar` é
        `daemon.reload` e `retomar` é `daemon.resume` num daemon que não está
        pausado. `desligar`, `restaurar-de-fabrica` e `refazer-proton` NÃO
        entram — uma régua não mexe na máquina dela para provar que sabe clicar.
        """
        for i, gesto in enumerate(self.args.prova_clique.split(",")):
            GLib.timeout_add(600 + i * 900, lambda g=gesto: (self._js(SELETOR % (g, g, g, g)),
                                                             False)[1])

    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _provar_no_aparelho(self) -> None:
        """A PROVA BOTÃO A BOTÃO, no aparelho dela — pedido dela, 01/09/2026.

        *"no aparelho por favor valida botão a botão tá bom?"*

        E ela está certa sobre o que basta: `[gesto] → aplicado` só prova que a
        função rodou sem levantar. O que prova de verdade é o ESTADO DO DAEMON
        MUDAR — e é o que este modo mede, um gesto por vez:

            lê o estado → clica → espera → lê de novo → diz o que mudou

        Um gesto que aplica e não muda nada aparece como `SEM EFEITO`, que é
        informação e não falha: pode ser um botão que já estava no valor pedido.
        O que ele nunca faz é passar por sucesso calado.
        """
        alvos = [n for (p, n) in sorted(pacotes.GESTOS) if p == self.pagina]
        if not self.args.incluir_perigosos:
            alvos = [n for n in alvos if (self.pagina, n) not in PERIGOSOS]
        if not alvos:
            print(f"[prova] {self.pagina} não tem gesto seguro a clicar")
            return
        print(f"[prova] {len(alvos)} gesto(s) em {self.pagina}: {', '.join(alvos)}")
        # UMA FILA SERIAL, e não timers fixos. Com `timeout_add` de intervalo
        # constante os gestos se ATROPELAM: `daemon.reload` leva 9,5 s e o
        # intervalo era 2,5 — o segundo gesto começava com o primeiro no ar, o
        # `_antes_do_gesto` (que é um só) era sobrescrito, e o relato saiu com
        # `retomar` DUAS vezes e `perfil-da-mesa` nenhuma. Medido em 01/09.
        #
        # Cada gesto agenda o próximo quando o SEU termina. O relato passa a ter
        # uma linha por gesto, na ordem, e nenhuma medição pega o efeito da
        # anterior.
        self._fila = list(alvos)
        GLib.timeout_add(400, lambda: (self._proximo_da_fila(), False)[1])

    def _proximo_da_fila(self) -> None:
        if not self._fila:
            return
        self._um_botao(self._fila.pop(0))

    def _um_botao(self, nome: str) -> None:
        """Um gesto: fotografa o daemon, clica, e mede o que mudou."""
        try:
            antes = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon antes ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return
        self._antes_do_gesto = (nome, antes)
        self._js(SELETOR % (nome, nome, nome, nome))
        # A ESPERA É OBRIGATÓRIA e não é folga: o daemon escreve no aparelho e
        # só então republica o estado. Medir na hora leria o valor VELHO e diria
        # "sem efeito" sobre um botão que funcionou.
        #
        # E ELA É POR GESTO: o `TETOS` da ponte diz que `daemon.reload` leva 15 s
        # e `gamepad.emulation.set` 2 — esperar o mesmo para os dois faz o
        # instrumento medir antes de o lento terminar, e ler "sem efeito".
        from pacotes import ponte as _p

        espera = max(self.args.espera, int(_p.teto(_METODO_DO_GESTO.get(nome, "")) * 1000) + 800)
        GLib.timeout_add(espera, lambda: (self._depois_do_gesto(), False)[1])

    def _depois_do_gesto(self) -> None:
        nome, antes = getattr(self, "_antes_do_gesto", (None, {}))
        if nome is None:
            return
        try:
            depois = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon depois ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return
        mudou = {k: (antes.get(k), v) for k, v in depois.items()
                 if antes.get(k) != v and not any(r in k for r in RUIDO)}
        # SEM ECO NÃO É SEM EFEITO, e confundir os dois é o que faria esta régua
        # acusar um botão que funciona. O `state_full` do daemon não publica
        # gatilho — o DualSense não devolve o modo em que está, é comando de ida
        # — então um `trigger.set` aceito não muda campo nenhum aqui.
        #
        # Quem declara isso é o PACOTE, em `SEM_ECO`, e a prova daqueles gestos
        # é outra: o gesto usa a porta `_detalhado`, que levanta quando o daemon
        # recusa. Chegar a "aplicado" já é o daemon ter aceitado.
        sem_eco = nome in self._sem_eco_da_pagina()
        self.provas.append({"gesto": nome, "mudou": mudou, "sem_eco": sem_eco})
        if mudou:
            print(f"[PROVA] {self.pagina} · {nome} → MUDOU {len(mudou)} campo(s):")
            for k, (a, d) in sorted(mudou.items())[:6]:
                print(f"          {k}: {a!r} → {d!r}")
        elif sem_eco:
            print(f"[PROVA] {self.pagina} · {nome} → ACEITO, sem eco no state "
                  f"(o daemon não publica este assunto)")
        else:
            print(f"[PROVA] {self.pagina} · {nome} → SEM EFEITO no estado do daemon")
        self._proximo_da_fila()

    def _sem_eco_da_pagina(self) -> set:
        """Os gestos daquela aba cujo efeito o daemon não publica."""
        import importlib

        for arq in sorted((AQUI / "pacotes").glob("a[0-9][0-9]_*.py")):
            mod = importlib.import_module(f"pacotes.{arq.stem}")
            if getattr(mod, "PAGINA", "") == self.pagina:
                return set(getattr(mod, "SEM_ECO", ()))
        return set()

    def _ir(self, pagina: str) -> None:
        self.view.load_uri(onde.pagina(pagina, publicado=True).as_uri())

    def _relatar(self) -> None:
        # UMA VEZ SÓ. O `_agendar` roda no `_instalado`, que dispara a cada
        # carga de página; sem esta trava o passeio agendava dez saídas e o
        # relato saía repetido — dois "foto:" no log de 01/09.
        if self.relatou:
            return
        self.relatou = True
        if self.args.foto:
            # `fotografar()` JÁ IMPRIME o caminho — a linha que estava aqui era
            # a segunda, e foi ela que fez o log de 01/09 mostrar dois "foto:"
            # e parecer que o relato rodava duas vezes. Não rodava.
            self.tela.fotografar(self.args.foto)
        print(f"\nvoltas: {self.voltas} · abas visitadas: {len(self.visitadas)}")
        print(f"{'aba':22s} {'pinturas':>8s} {'valores':>8s}")
        mudas = []
        for pagina in sorted(pacotes.PACOTES):
            conta = self.pinturas.get(pagina) or []
            pico = max(conta) if conta else 0
            print(f"{pagina:22s} {len(conta):8d} {pico:8d}")
            if conta and pico == 0:
                mudas.append(pagina)
        if self.provas:
            mudaram = sum(1 for p in self.provas if p["mudou"])
            aceitos = sum(1 for p in self.provas if not p["mudou"] and p["sem_eco"])
            mudos = [p["gesto"] for p in self.provas
                     if not p["mudou"] and not p["sem_eco"]]
            print(f"\nPROVA NO APARELHO: {mudaram} mudaram o daemon · "
                  f"{aceitos} aceitos sem eco · {len(mudos)} sem efeito")
            for p in self.provas:
                marca = "✓" if p["mudou"] else ("·" if p["sem_eco"] else "—")
                print(f"   {marca} {p['gesto']}")
            if mudos:
                # UM GESTO MUDO E NÃO DECLARADO é o que esta régua persegue: ou
                # ele não faz nada, ou faz algo que o daemon não conta e ninguém
                # escreveu isso. As duas coisas precisam de alguém.
                print(f"   sem efeito e sem `SEM_ECO`: {', '.join(mudos)}")
        if self.gestos:
            print(f"gestos: {len(self.gestos)} · aplicados: {len(self.aplicados)} · "
                  f"sem dono: {len(set(self.recusados))}")
            for r in sorted(set(self.recusados)):
                print(f"   sem dono: {r}")
        if self.custos:
            ordenado = sorted(self.custos)
            print(f"custo do tique: mediana {ordenado[len(ordenado)//2]:.2f} ms · "
                  f"max {ordenado[-1]:.2f} ms")
        if mudas:
            # ZERO É ERRO, NÃO SILÊNCIO. Uma aba que foi visitada, tem pacote e
            # escreveu zero valores é endereço que não casou — e essa é a forma
            # exata do defeito que deixou a `06-navegacao` publicar sem
            # endereço nenhum.
            print(f"\nABAS MUDAS (pacote sem endereço que case): {', '.join(mudas)}")
            raise SystemExit(1)


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true",
                   help="Gtk.OffscreenWindow — nada aparece na tela dela. "
                        "Ela tem UMA tela; é o padrão de toda régua desta casa.")
    p.add_argument("--segundos", type=float, default=6.0)
    p.add_argument("--passear", action="store_true",
                   help="visita as dez abas e mede a pintura de cada uma")
    p.add_argument("--parada", type=int, default=900,
                   help="ms em cada aba durante o passeio")
    p.add_argument("--foto", default="")
    p.add_argument("--abre", default="", help="abrir direto numa aba")
    p.add_argument("--prova-no-aparelho", action="store_true",
                   help="clica CADA gesto da aba, um por vez, e mede o que mudou "
                        "no estado do daemon — a prova que ela pediu")
    p.add_argument("--entre", type=int, default=2500,
                   help="ms entre um gesto e o próximo")
    p.add_argument("--espera", type=int, default=1200,
                   help="ms entre o clique e a leitura do daemon")
    p.add_argument("--incluir-perigosos", action="store_true",
                   help="inclui os gestos que mexem na máquina dela (desligar, "
                        "reiniciar, restaurar) — escolha de quem roda")
    p.add_argument("--prova-clique", default="",
                   help="lista de gestos a clicar, separada por vírgula — "
                        "eles chegam ao daemon de verdade")
    p.add_argument("--sem-cor", action="store_true",
                   help="MORDIDA: sem o leitor de cor do plástico")
    args = p.parse_args()

    piloto = Piloto(args)
    if args.prova_no_aparelho:
        GLib.timeout_add(2500, lambda: (piloto._provar_no_aparelho(), False)[1])
    if args.prova_clique:
        GLib.timeout_add(2000, lambda: (piloto._provar_cliques(), False)[1])
    if args.abre:
        GLib.timeout_add(400, lambda: (piloto._ir(args.abre), False)[1])
    Gtk.main()


if __name__ == "__main__":
    main()
