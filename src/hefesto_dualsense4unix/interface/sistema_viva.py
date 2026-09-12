#!/usr/bin/env python3
"""sistema_viva.py — a aba SISTEMA viva: o desenho dela com a máquina dela.

O mockup aprovado rodando num `WebKit2.WebView` dentro de uma janela GTK3
(`D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK`), pintado pelo que o
produto já sabe ler: o estado do daemon, a pausa, o detector de janela, o perfil
de bateria e o exame de saúde.

    sistema_viva.py                     # a janela, na tela
    sistema_viva.py --oculta            # Gtk.OffscreenWindow: nada aparece
    sistema_viva.py --oculta --segundos 4 --foto a.png

AS DUAS MORDIDAS, e as duas são as do piloto da aba Controles:

    --sem-ponte           desliga a ponte: a tela tem de ficar na cena FIXA do
                          mockup ("Ligado", "Sim — e continua depois de
                          reiniciar", "Os 4
                          controles", "8 linhas"). Se ela mostrar a máquina
                          dela, o dado não está vindo do Python.
    --arranca-enderecos   apaga os `data-id` que o `aba09.py` escreve: a pintura
                          tem de DESABAR. Se não desabar, os endereços não
                          estavam sendo usados.

E o resto:

    --duble a.json        o `state_full` vem de um arquivo, não do daemon
    --status <estado>     finge a matriz de três fontes (`offline`,
                          `online_systemd`, `online_avulso`, `iniciando`)
    --sem-exame           não roda o `storm_report` (a lista fica no traço)
    --prova-gesto         cliques sintéticos, para provar tela → Python → eco

**ESTA LEVA NÃO ESCREVE NADA, e a exceção é uma só.** Os doze gestos chegam ao
Python, são registrados com o dono declarado em
`hefesto_dualsense4unix.gui.aba_sistema.GESTOS` e **ecoam de volta**. O único
que AGE é o `atualizar`, e ele só relê — nenhum perfil dela é tocado, nenhum
`systemctl start/stop/restart` é disparado, nenhum byte vai a aparelho.

A TRADUÇÃO NÃO MORA AQUI. Ela é produto e mora em
`hefesto_dualsense4unix.gui.aba_sistema` — versionado, medido por `ruff` e
`mypy`, e viajando em worktree. O que sobra aqui é a JANELA, o TIQUE e as
LEITURAS de verdade (soquete, `systemctl`, disco), que é justamente o que uma
régua não deve precisar montar para medir a tela.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

# A JANELA, AS DUAS PONTES E A GUARDA DE CARGA VÊM DA BIBLIOTECA, e é ela que
# crava os quatro pinos de `gi.require_version` (com o Gdk DEPOIS do Gtk).
# Importá-la ANTES de `gi.repository` é o que garante a ordem — não é import
# decorativo, é a ordem de inicialização do gi.
from hefesto_dualsense4unix.gui import aba_sistema  # noqa: E402  isort:skip
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402  isort:skip

from gi.repository import GLib, Gtk  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

# A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito arquivos
# desta casa cravavam o caminho absoluto da árvore DELA, e por isso rodar uma
# CÓPIA reescrevia o mockup dela.
# A RAIZ É `parents[2]` — ver a nota em `hefesto_vivo.py`, medida em
# 04/09/2026: com `[1]` o `RAIZ / "src"` virava `src/src`, que não existe.
RAIZ = AQUI.parents[2]
PAGINA = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / "09-sistema.html"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)
TITULO_ESPERADO = "Hefesto — aba SISTEMA"

import mesa_viva  # noqa: E402  (só pelo `estado_do_daemon`, que é leitura pura)

#: O tique rápido: o mesmo período da janela de hoje
#: (`app/constants.LIVE_POLL_INTERVAL_MS`). Ele lê SÓ o IPC.
TIQUE_MS = 100
#: A faixa lenta: `systemctl` e o exame de disco. São subprocessos e leituras de
#: arquivo — a 10 Hz seriam vinte por segundo, que é o custo que a carona de
#: 0,5 Hz existe para não pagar.
TIQUE_LENTO_MS = 2000


# ---------------------------------------------------------------------------
# As leituras de verdade — tudo o que sai deste processo
# ---------------------------------------------------------------------------
def _systemctl(*args: str) -> str | None:
    """Uma linha de `systemctl --user`, ou `None` quando nem deu para perguntar.

    `None` **não é** "desligado": é "não sei". A diferença chega à tela.
    """
    try:
        proc = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True, text=True, timeout=4.0, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (proc.stdout or proc.stderr or "").strip().splitlines()[0] if (
        proc.stdout or proc.stderr
    ) else ""


def _unidade() -> str:
    """O nome da unidade, lido do produto — nunca digitado."""
    from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL

    return str(SERVICE_NORMAL)


def _status_do_daemon() -> str | None:
    """A matriz de três fontes, com as DUAS que este processo pode consultar.

    O `_daemon_status` do produto cruza três: `is-active`, `is-enabled` e o
    `is_alive(pid)` do arquivo de pid. As três estão aqui, e a matriz é a mesma
    — mas ela vive em `daemon_actions.DaemonActionsMixin`, que é método de
    classe GTK e não se importa sem a janela inteira. **Este é um segundo
    leitor da mesma regra, e está declarado como tal:** o dia em que a
    MIGRA-SISTEMA-01 enxertar o WebView no lugar do Glade, a regra passa a ter
    um dono só de novo.
    """
    ativo = _systemctl("is-active", _unidade())
    if ativo is None:
        return None
    vivo = _processo_vivo()
    if ativo == "active" and vivo:
        return "online_systemd"
    if ativo != "active" and vivo:
        return "online_avulso"
    if ativo == "active" and not vivo:
        return "iniciando"
    return "offline"


def _processo_vivo() -> bool:
    """O daemon está de pé fora do systemd? Pelo arquivo de pid, como o produto."""
    try:
        from hefesto_dualsense4unix.utils.single_instance import is_alive
    except Exception:
        return False
    for caminho in _lugares_do_pid():
        try:
            pid = int(pathlib.Path(caminho).read_text().strip())
        except (OSError, ValueError):
            continue
        try:
            return bool(is_alive(pid))
        except Exception:
            return False
    return False


def _lugares_do_pid() -> list[str]:
    import os

    base = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return [f"{base}/hefesto-dualsense4unix/hefesto-dualsense4unix.pid"]


def _exame() -> list[tuple[str, str]] | None:
    """O `storm_report`, que é READ-ONLY por contrato do próprio módulo.

    Custa 2 a 5 ms nesta máquina (medido em 29/08), e por isso anda na faixa
    lenta e não no tique de 100 ms.
    """
    try:
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            controles_no_cabo,
            storm_report,
        )
    except Exception:
        return None
    try:
        return storm_report(controles_no_cabo=controles_no_cabo(_ULTIMO_STATE[0]))
    except Exception:
        return None


#: O último `state_full` visto, para o exame poder usar o denominador honesto
#: (quantos controles estão NO CABO). Uma lista de um elemento porque o exame
#: roda noutro tique.
_ULTIMO_STATE: list[dict[str, Any] | None] = [None]


def _frases_de_janela(state: Any) -> tuple[str | None, str | None]:
    """As duas frases do produto sobre o detector de janela.

    A longa da PROMESSA (`descrever_deteccao_de_janela`, o perfil troca sozinho?)
    e a do MECANISMO (`descrever_display_grafico`, por onde ele enxerga). A
    segunda tem **zero chamadores** no produto de hoje — é a cura escrita e
    nunca ligada, e esta aba é o primeiro chamador dela.
    """
    try:
        from hefesto_dualsense4unix.app.actions.ambiente_na_tela import (
            descrever_display_grafico,
        )
        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            descrever_deteccao_de_janela,
        )
    except Exception:
        return None, None
    return descrever_deteccao_de_janela(state), descrever_display_grafico(state)


# ---------------------------------------------------------------------------
# O bootstrap: o que a PÁGINA passa a saber fazer
# ---------------------------------------------------------------------------
BOOTSTRAP = r"""
window.HEF = (function(){
  const qa = (s,r)=>Array.from((r||document).querySelectorAll(s));
  const q  = (s,r)=>(r||document).querySelector(s);
  const end = id => q('[data-id="'+id+'"]');

  // AS ESCRITAS DEVOLVEM QUANTOS VALORES ESCREVERAM — 0 quando o endereço não
  // existe. É o que faz a conta do fim ser uma RÉGUA e não um enfeite: com
  // `n++` cego, apagar um endereço não mudava o número e a régua aprovava uma
  // pintura que não pintava nada.
  //
  // E o `textContent` só vai em FOLHA SEM FILHO: num container ele APAGA os
  // filhos e força layout — é a armadilha da pintura, e ela continua sendo
  // deste arquivo porque é da ABA, não da ponte.
  function txt(el,v){ if(!el) return 0; if(el.textContent !== v) el.textContent = v; return 1; }
  function cls(el,c,on){ if(!el) return 0; el.classList.toggle(c, !!on); return 1; }
  function dica(el,v){ if(!el) return 0; if(el.title !== v) el.title = v; return 1; }
  // TRAVAR É ESCRITA, e por isso conta na régua. Um botão que a tela oferece e
  // o produto recusa é mentira: o `disabled` é o "não dá" dito no lugar certo.
  function trava(el,off){ if(!el) return 0; if(el.disabled!==!!off) el.disabled=!!off; return 1; }

  // Uma LINHA DE ESTADO: o valor, o selo (símbolo E cor juntos) e a dica.
  function linha(id, d){
    const el = end(id); if(!el) return 0; let n = 0;
    n += txt(q('.val', el), d.txt);
    n += txt(q('.g', el), d.g);
    for(const c of ['ok','warn','info']) n += cls(el, c, d.cls===c);
    n += dica(el, d.dica||'');
    return n;
  }

  function achado(a){
    const d = document.createElement('div'); d.className = 'saude';
    const s = document.createElement('span'); s.className = 'selo ' + a.cls;
    const sg = document.createElement('span'); sg.className = 'sg'; sg.textContent = a.g;
    s.appendChild(sg); s.appendChild(document.createTextNode(a.selo));
    const t = document.createElement('span'); t.className = 'txt';
    const dentro = document.createElement('span'); dentro.textContent = a.txt;
    t.appendChild(dentro);
    d.appendChild(s); d.appendChild(t);
    return d;
  }

  // A LISTA DO EXAME É UM ENDEREÇO, NÃO OITO. O Python entrega a lista; a
  // página a desenha nas duas colunas — e as duas continuam sendo
  // `MEIO = len/2 + len%2`, que é o que o gerador faz.
  function exame(e){
    let n = 0;
    n += txt(end('exame-contagem'), e.contagem);
    const caixa = end('exame-lista'); if(!caixa) return n;
    const cols = qa('.col-lista', caixa); if(cols.length !== 2) return n;
    for(const c of cols) c.innerHTML = '';
    const meio = Math.ceil(e.linhas.length / 2);
    e.linhas.forEach((a,i)=>{ cols[i<meio?0:1].appendChild(achado(a)); n++; });
    if(!e.linhas.length && e.vazio){
      const d = document.createElement('div');
      d.className = 'saude'; d.style.cssText = 'color:var(--texto-mudo)';
      d.textContent = e.vazio; cols[0].appendChild(d); n++;
    }
    return n;
  }

  function pinta(p){
    const t0 = performance.now(); let n = 0;
    for(const id in p.valores) n += linha(id, p.valores[id]);

    // A CHAVE TEM TRÊS ESTADOS, e o terceiro é "não sei". `null` NÃO é `false`:
    // a chave desenhada tem dois, e nenhum deles quer dizer que não deu para
    // ler — deixar "desligado" no lugar de "não sei" é mentira pela posição.
    //
    // A marca do "não sei" é OPACIDADE INLINE, e é de propósito: uma classe
    // nova (`.chave.nao-sei`) exigiria CSS que o desenho dela não tem, e
    // acrescentar CSS é mudar o que ela aprovou. O inline marca só o estado que
    // o mockup nunca desenhou, e a dica diz por quê.
    const ch = end('hefesto-autostart');
    if(ch){
      const b = q('.chave', ch);
      n += cls(b, 'on', p.autostart === true);
      if(b){ const o = p.autostart === null ? '0.35' : '';
             if(b.style.opacity !== o) b.style.opacity = o; n++; }
      n += dica(ch, p.autostart === null
        ? 'Não deu para perguntar ao systemd se o Hefesto liga junto com o computador.'
        : (p.autostart ? 'Liga junto com o computador.' : 'Não liga junto com o computador.'));
    }

    // NENHUM PERFIL ESCOLHIDO É UM ESTADO, e o produto já decidiu qual: a
    // ausência NÃO afunda "Tudo ligado" (a nota de `PERFIL_POR_TETO`, em
    // `secao_orcamento`). Num `<select>` isso é `selectedIndex = -1` — a caixa
    // fica vazia, que é a forma de dizer "ninguém escolheu" sem escolher por
    // ela. Deixar a opção do desenho marcada seria a tela afirmando uma escolha
    // que ela não fez.
    const sel = end('bateria-perfil');
    if(sel){
      if(p.perfil === null){ if(sel.selectedIndex !== -1) sel.selectedIndex = -1; }
      else { for(const o of sel.options) if(o.selected !== (o.text === p.perfil)) o.selected = (o.text === p.perfil); }
      n++;
      n += dica(sel, p.perfil === null
        ? 'Ninguém escolheu um perfil de bateria para esta mesa ainda.'
        : sel.title);
    }
    n += txt(end('bateria-frase'), p.frase);
    n += exame(p.exame);
    const reg = end('registro-texto');
    n += txt(reg, p.registro.txt) + dica(reg, p.registro.dica);

    // AS TRAVAS. Um botão cinza sem explicação manda a pessoa procurar defeito
    // onde não há; um botão vivo que o produto recusa dispara trabalho que não
    // acontece e a tela confirma. Os dois males têm a mesma cura.
    for(const b of qa('[data-gesto]')){
      const g = b.dataset.gesto, motivo = p.travas[g];
      n += trava(b, !!motivo);
      if(motivo) n += dica(b, motivo);
    }

    // QUANTOS VALORES A PINTURA ESCREVEU, de volta ao Python. Sem isto uma
    // pintura que não acha NADA (um endereço que sumiu do gerador) passaria
    // calada.
    if(n !== window.__hefN){ window.__hefN = n;
      manda({gesto:'pintou', valores:n, ms: Math.round((performance.now()-t0)*100)/100}); }
    return n;
  }

  function manda(o){ window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o)); }

  function ligarGestos(){
    for(const b of qa('[data-gesto]')){
      if(b.dataset.ligado) continue; b.dataset.ligado='1';
      const nome = b.dataset.gesto;
      if(b.tagName === 'SELECT'){
        b.addEventListener('change', ()=>manda({gesto:nome, valor:b.value}));
        continue;
      }
      b.addEventListener('click', ev=>{
        ev.preventDefault(); ev.stopPropagation();
        if(b.disabled) return;
        manda({gesto:nome, estava: b.classList.contains('on') ? 'on' : 'off'});
      });
    }
  }

  // O ECO: o Python confirma o que ouviu, e a tela mostra que ouviu. Nenhum
  // gesto desta leva pinta a tela sozinho — quem repinta é a ponte de leitura,
  // e escrever direto no DOM a partir do gesto criaria o segundo escritor.
  function eco(o){
    const el = q('[data-gesto="'+o.gesto+'"]');
    if(el) el.dataset.eco = String(o.recibo || '');
  }

  ligarGestos();
  return {pinta:pinta, eco:eco, ligarGestos:ligarGestos,
          quem:function(){ return document.title + '|' + qa('[data-id]').length; }};
})();
'HEF-PRONTO'
"""


# ---------------------------------------------------------------------------
# A janela
# ---------------------------------------------------------------------------
class Janela:
    """A aba Sistema viva: o tique, a pintura e os doze gestos."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.gestos: list[dict[str, Any]] = []
        self.valores: list[int] = []
        self.lento: dict[str, Any] = {"status": None, "autostart": None, "achados": None}
        self._t_lento = 0.0

        self.tela = JanelaDaAba(
            arquivo=PAGINA,
            titulo_esperado=TITULO_ESPERADO,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._saiu_da_aba,
            oculta=args.oculta,
            subtitulo="Sistema — a máquina de verdade",
        )
        self.ponte = self.tela.ponte
        self.janela = self.tela.janela

    # -- carga -------------------------------------------------------------
    def _saiu_da_aba(self, titulo: str) -> None:
        """Ela clicou na tira. Sair da Sistema só DESLIGA a pintura."""
        self.pronto = False
        print(f"[fora da Sistema] {titulo} — o mockup estático; a pintura pausou.")

    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _instalar(self) -> None:
        if self.args.sem_ponte:
            print("MORDIDA: a ponte está DESLIGADA — a tela fica na cena fixa do mockup.")
            self.pronto = True
            self._agendar_saida()
            return

        def pronto(_valor: str | None, erro: Exception | None) -> None:
            if erro is not None:
                print(f"ERRO DE CARGA: o bootstrap não instalou: {erro}", file=sys.stderr)
                Gtk.main_quit()
                return
            self.pronto = True
            self._tique_lento()
            self._tique()
            GLib.timeout_add(TIQUE_MS, self._tique)
            GLib.timeout_add(TIQUE_LENTO_MS, self._tique_lento)
            if self.args.prova_gesto:
                self._marcar_gestos_de_mentira()
            if self.args.arranca_enderecos:
                # A MORDIDA DO ENDEREÇO: arranca os `data-id` que o `aba09.py`
                # escreve e vê a pintura DESABAR. Um endereço a menos não
                # levanta erro nenhum no WebKit — o `querySelector` devolve
                # `null` e o valor simplesmente não é escrito. Se a conta não
                # cair, os endereços não estavam sendo usados.
                GLib.timeout_add(
                    2000,
                    lambda: (
                        self._js(
                            "for(const e of document.querySelectorAll('[data-id]'))"
                            " delete e.dataset.id; window.__hefN=-1;"
                        ),
                        False,
                    )[1],
                )
            self._agendar_saida()

        self.ponte.perguntar(BOOTSTRAP, pronto)

    def _agendar_saida(self) -> None:
        foto = self.args.foto
        self.tela.agendar_saida(
            self.args.segundos or 0.0,
            antes=(lambda: self.tela.fotografar(foto)) if foto else None,
        )

    def _marcar_gestos_de_mentira(self) -> None:
        """Cliques SINTÉTICOS, para provar o caminho tela → Python → eco.

        A ORDEM É A MORDIDA. O "Retomar" é clicado PRIMEIRO, com o Hefesto sem
        pausa: ele está travado e tem de produzir ZERO gestos. Uma régua que
        clicasse os doze em qualquer ordem não distinguiria "travado" de "sem
        ouvinte" — que é exatamente o defeito que a aba Controles pagou em 29/08,
        quando dois botões de som eram pintados, tinham `cursor:pointer` e não
        tinham ouvinte nenhum.
        """
        roteiro = [(1400, "retomar"), (1700, "atualizar"), (2000, "ver-detalhes"),
                   (2300, "restaurar-de-fabrica"), (2600, "refazer-consertos")]
        for ms, gesto in roteiro:
            script = f"document.querySelector('[data-gesto=\"{gesto}\"]').click()"
            GLib.timeout_add(ms, lambda s=script: (self._js(s), False)[1])

    # -- os tiques ---------------------------------------------------------
    def _estado(self) -> dict[str, Any] | None:
        """O `state_full` de agora — do daemon dela, ou do dublê, ou `None`.

        `None` é o daemon CALADO, e é diferente de mesa vazia. A tela separa os
        dois.
        """
        if self.args.duble:
            return dict(json.loads(pathlib.Path(self.args.duble).read_text()))
        try:
            return dict(mesa_viva.estado_do_daemon())
        except Exception:
            return None

    def _tique_lento(self) -> bool:
        """`systemctl` e o exame — as leituras caras, a 0,5 Hz."""
        if not self.pronto:
            return True
        self.lento["status"] = self.args.status or _status_do_daemon()
        self.lento["autostart"] = _systemctl("is-enabled", _unidade())
        self.lento["achados"] = None if self.args.sem_exame else _exame()
        self._t_lento = time.monotonic()
        return True

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        t0 = time.perf_counter()
        state = self._estado()
        _ULTIMO_STATE[0] = state
        promessa, mecanismo = _frases_de_janela(state)
        leitura = aba_sistema.Leitura(
            status=self.lento["status"],
            autostart=self.lento["autostart"],
            state=state,
            achados=self.lento["achados"],
            deteccao=promessa,
            ambiente=mecanismo,
            perfil=self._perfil_da_mesa(),
        )
        self.ponte.dizer("HEF.pinta", aba_sistema.pacote(leitura))
        self.valores.append(int((time.perf_counter() - t0) * 1_000_000))
        return True

    def _perfil_da_mesa(self) -> str | None:
        """O perfil de bateria escolhido hoje — do produto, inteiro.

        `perfil_na_tela(None)` já é exatamente esta pergunta, e já traz a
        decisão que importa escrita no produto: **`None` quer dizer NENHUM, e a
        ausência não afunda "Tudo ligado"** (a nota de `PERFIL_POR_TETO`). A
        primeira versão desta função refazia a tradução chave→perfil com um
        laço próprio — um segundo dono do mesmo mapa, e o dono existia ao lado.
        """
        try:
            from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
                perfil_na_tela,
            )

            return perfil_na_tela(None)
        except Exception:
            return None

    # -- os gestos ---------------------------------------------------------
    def _gesto(self, o: dict[str, Any]) -> None:
        """Um gesto da tela chegou. Registrado, com o dono, e ecoado de volta.

        NADA É APLICADO, e a exceção é o `atualizar` — que só relê. É a mesma
        disciplina do piloto da aba Controles: a aba é para ela AVALIAR, e um
        gesto que grave sem ela mandar é dano.
        """
        nome = str(o.get("gesto") or "")
        if nome == "pintou":
            self.valores.append(-int(o.get("valores") or 0))
            return
        dono = aba_sistema.GESTOS.get(nome, aba_sistema.SEM_DONO)
        self.gestos.append({**o, "dono": dono})
        print(f"GESTO {nome!r}{' valor=' + repr(o['valor']) if 'valor' in o else ''}")
        print(f"   dono: {dono}")
        recibo = "relido" if nome == "atualizar" else "ouvido, e nada foi aplicado"
        if nome == "atualizar":
            self._tique_lento()
        self.ponte.dizer("HEF.eco", {"gesto": nome, "recibo": recibo})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="A aba SISTEMA viva.")
    p.add_argument("--oculta", action="store_true", help="Gtk.OffscreenWindow")
    p.add_argument("--segundos", type=float, default=0.0)
    p.add_argument("--foto", default="")
    p.add_argument("--sem-ponte", action="store_true")
    p.add_argument("--arranca-enderecos", action="store_true")
    p.add_argument("--sem-exame", action="store_true")
    p.add_argument("--prova-gesto", action="store_true")
    p.add_argument("--duble", default="")
    p.add_argument("--status", default="", help="finge a matriz de três fontes")
    args = p.parse_args(argv)

    if not PAGINA.exists():
        print(f"ERRO: {PAGINA} não existe. Rode `aba09.py` primeiro.", file=sys.stderr)
        return 2
    janela = Janela(args)
    Gtk.main()
    pinturas = [v for v in janela.valores if v < 0]
    if pinturas:
        print(f"pintura: {-pinturas[-1]} valores por vez, {len(pinturas)} contas relatadas")
    custos = [v for v in janela.valores if v > 0]
    if custos:
        custos.sort()
        meio = custos[len(custos) // 2] / 1000.0
        print(f"tique: {len(custos)} voltas · mediana {meio:.2f} ms "
              f"· {meio / TIQUE_MS * 100:.1f}% do orçamento de {TIQUE_MS} ms")
    print(f"gestos ouvidos: {len(janela.gestos)}")
    print(f"recusas da ponte: {len(janela.ponte.recusas)}")

    # UMA BANCADA QUE NÃO DEU UMA VOLTA NÃO MEDIU NADA, E NÃO SAI VERDE — a
    # guarda que a `jogar_vivo.main` ganhou na `ONDA5-07-03`, estendida às cinco
    # na costura da ONDA C. Aqui a contagem não é um `voltas`: esta bancada
    # guarda os custos do tique em `janela.valores`, e um tique medido é uma
    # volta dada. O `--sem-ponte` é a exceção e é a MORDIDA: ele desliga a
    # pintura de propósito, e zero volta ali é o resultado esperado.
    if not custos and not args.sem_ponte:
        print("ERRO: a bancada não deu uma volta — nada foi medido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
