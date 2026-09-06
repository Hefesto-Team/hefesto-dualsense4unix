#!/usr/bin/env python3
"""As quatro linhas novas da aba Jogar, medidas DENTRO do WebKit que ela usa.

POR QUE ELE EXISTE (JOGAR-O-QUE-FALTA-01, 06/09/2026): os testes de unidade
provam a CONTA — que `is_primary` vira `"1"`, que a máscara clicada entra na
seção `mode`, que o serviço calado ganha uma linha na coluna Atenção. O que eles
**não** provam é que o clique dela chega e que a tela muda: um endereço que você
acrescentou e nunca viu pintar não está entregue. É a regra desta casa, e o caso
que a fundou foi o `--prova-gesto` dando verde sobre dois botões mortos.

**ELE ABRE A BANCADA, e não o publicado** — `mockup/01-jogar.html`. Publicar é
ato dela; até o OK, o desenho está à frente do produto, e uma régua apontada
para a página publicada daria verde sobre a tela de ontem. É a armadilha que o
`COMO-OLHAR-A-TELA` chama de *"régua que pergunta no lugar errado"*. A foto do
publicado sai junto, com `--foto-publicado`, e é o ANTES desta entrega.

O QUE ELE MEDE, e cada linha é um passo da sprint:

1. **o marcador "primário" ANDA** — dois controles, um primário; troque o
   primário no dublê e o marcador muda de cartão. E o **alvo de edição da fita
   NÃO se move junto**: os dois significados ficam em pixels diferentes;
2. **a marca da emulação degradada** aparece com motivo e **some sem ele**;
3. **o serviço calado** — com o estado vazio a coluna Atenção DIZ, e os quatro
   cartões param de afirmar;
4. **o clique no chip Xbox chega ao PERFIL ATIVO**, e o valor é lido de volta
   pelo caminho da **aba 10** (`perfis_web._pacote_do_editor`) — a mordida do
   Passo 1: um dono, duas telas;
5. **as mutações por tique com a mesa parada**, que é a régua da
   `A-TELA-SAMBA-01`. O alvo é ZERO no que não mudou.

**O DAEMON FICA DE FORA** e **NADA TOCA O PERFIL DELA**: o `HOME` e os quatro
`XDG_*` vão para um diretório temporário ANTES do primeiro import do pacote, a
ponte é um dublê que anota, e `mesa_viva.estado_do_daemon` é trocado por uma
função que devolve a cena. **O interruptor NÃO é clicado**, e é decisão: o gesto
`hefesto` chama `a09_sistema.ativar_o_servico()`, que roda `systemctl` na
máquina dela de verdade.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/a_jogar_diz_quem_e_o_primario.py
    scripts/ensaios/a_jogar_diz_quem_e_o_primario.py \
        --foto-publicado antes.png --foto-depois depois.png
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# O LAR DE MENTIRA VEM ANTES DE TUDO: `profiles_dir()` resolve o caminho no
# primeiro uso, e um import antes desta linha o prenderia na pasta DELA.
_LAR = pathlib.Path(tempfile.mkdtemp(prefix="ensaio-jogar-"))
os.environ["HOME"] = str(_LAR)
for _x in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
    os.environ[_x] = str(_LAR / _x.lower())
os.environ["HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"] = "1"
os.environ["HEFESTO_CARONA_WRAPPER"] = "0"

sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
from hefesto_dualsense4unix.utils.tela_de_mentira import (  # noqa: E402
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

from hefesto_dualsense4unix.app.actions import perfis_web  # noqa: E402
from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, onde  # noqa: E402
from hefesto_dualsense4unix.profiles.loader import (  # noqa: E402
    load_profile,
    profiles_dir,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile  # noqa: E402

ABA = "01-jogar.html"
PERFIL = "Ensaio da Jogar"

#: OS DOIS ENDEREÇOS SÃO MASCARADOS — octetos 4 e 5 zerados, a máscara da casa.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

#: QUANTAS VOLTAS A MEDIDA NO TEMPO DÁ. 100 é o mesmo número do
#: `--conta-mutacoes` do piloto.
VOLTAS_NO_TEMPO = 100


def cena(*, primario: str = P1, motivo: str | None = "uhid_indisponivel",
         ) -> dict[str, object]:
    """Um `state_full` de dois controles — o P1 no cabo, o P2 no rádio.

    O primeiro argumento diz de quem é o `is_primary`; o `motivo` liga (ou não)
    a degradação do gamepad virtual do P1. As duas coisas são as que os Passos 3
    e 4 medem.
    """
    def um(uniq: str, slot: int, transporte: str, carga: int) -> dict[str, object]:
        entrada: dict[str, object] = {
            "uniq": uniq, "connected": True, "player_slot": slot,
            "player": slot, "is_primary": uniq == primario,
            "transport": transporte, "battery_pct": carga,
        }
        if uniq == P1 and motivo:
            entrada["vpad_backend"] = "uinput"
            entrada["vpad_motivo"] = motivo
        return entrada

    return {
        "connected": True, "native_mode": False, "paused": False,
        "active_profile": PERFIL,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [um(P1, 1, "usb", 80), um(P2, 2, "bt", 40)],
    }


_FERRAMENTAS = r"""
  function cartoes(){
    return Array.prototype.map.call(
      document.querySelectorAll('.cartao'), function(c){
        const marca = c.querySelector('[data-campo="marcador-principal"]');
        const sup = c.querySelector('[data-campo="degradou-cartao"]');
        const ident = c.querySelector('[data-campo="identidade"]');
        return {
          lugar: c.dataset.controle || '',
          identidade: ident ? ident.textContent : null,
          // O MARCADOR: o alvo `classe` acende a classe declarada no desenho.
          primario: !!(marca && marca.classList.contains('ha')),  // (noqa-acento) chave de JSON
          // e ele TEM DE ESTAR VISÍVEL quando aceso — a folha é metade da cura.
          primarioVisivel: !!(marca &&
              getComputedStyle(marca).display !== 'none'),
          // A MARCA DA DEGRADAÇÃO: o alvo `atributo` põe (ou tira) o `title`.
          degradou: sup ? (sup.getAttribute('title') || '') : null,
          degradouVisivel: !!(sup && getComputedStyle(sup).display !== 'none'),
          // O ALVO DE EDIÇÃO DA FITA — a OUTRA pergunta, no mesmo cartão.
          alvoDaFita: c.classList.contains('alvo')
        };
      });
  }
  function atencao(){
    const selos = Array.prototype.map.call(
      document.querySelectorAll('[data-campo="aviso-selo"]'),
      function(e){ return e.textContent; });
    const textos = Array.prototype.map.call(
      document.querySelectorAll('[data-campo="aviso-texto"]'),
      function(e){ return e.textContent; });
    const conta = document.querySelector('[data-campo="atencao-conta"]');
    return {selos: selos, textos: textos,
            conta: conta ? conta.textContent : null};
  }
  function tudo(){ return {cartoes: cartoes(), atencao: atencao()}; }  // (noqa-acento) chaves de JSON
"""

ROTEIRO_LER = "(function(){\n" + _FERRAMENTAS + """
  return JSON.stringify(tudo());
})()
"""

ROTEIRO_CLICAR_XBOX = """
(function(){
  const b = document.querySelector('[data-gesto="modo-xbox"]');
  if(!b){ return JSON.stringify({achou:false}); }
  b.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  return JSON.stringify({achou:true, texto:b.textContent});
})()
"""

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=True,
                 prova_no_aparelho=False, entre=2500, conta_mutacoes=0,
                 sem_ondas=True)


class PonteDeMentira:
    """Anota, e não fala com o daemon dela."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *a: object, **kw: object) -> bool:
        self.chamadas.append(f"chamar({metodo!r}, {kw!r})")
        return True

    def chamar_detalhado(self, metodo: str, *a: object, **kw: object) -> object:
        self.chamadas.append(f"detalhado({metodo!r})")
        return (True, "")

    def autoswitch_lock_set(self, **kw: object) -> object:
        self.chamadas.append(f"autoswitch_lock_set({kw!r})")
        return {}

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch({nome!r})")
        return True

    def resultado(self, metodo: str, *a: object, **kw: object) -> object:
        self.chamadas.append(f"resultado({metodo!r})")
        return {}


def _modo_no_disco() -> object:
    """O que o `.json` guarda AGORA, pelo caminho do disco."""
    modo = getattr(load_profile(PERFIL), "mode", None)
    if modo is None:
        return None
    return {"kind": modo.kind, "gamepad_flavor": modo.gamepad_flavor}


def _modo_pela_aba_dez() -> object:
    """O MESMO valor, lido pelo caminho da aba **Perfis** — a mordida do Passo 1.

    `perfis_web._pacote_do_editor` é o que a aba 10 mostra no quadro «Modo»
    (PERFIL-MODO-01). Ler por aqui é o que separa *"gravou num arquivo"* de
    *"a outra tela vê"* — e é o que a sprint pede com todas as letras: *"clique
    o modo na 01 e leia o valor na 10"*.
    """
    return perfis_web._pacote_do_editor(load_profile(PERFIL)).get("modo")


def _uma_volta(*, publicado: bool, foto: str = "",
               fazer_o_clique: bool = True) -> dict[str, object]:
    """Abre a página, pinta as cenas, clica, e devolve o que a tela mostrou."""
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    # A PONTE QUE O GESTO RECEBE É O **MÓDULO** `pacotes.ponte`, importado no
    # topo do piloto (`hefesto_vivo.py:85`), e ele chega ao gesto pelo terceiro
    # argumento do despachante — ver `hefesto_vivo._gesto`, no `trabalhar()`.
    # Trocá-lo aqui é o que impede um clique de ensaio de sair pelo socket dela.
    dubie = PonteDeMentira()
    hefesto_vivo.ponte = dubie  # type: ignore[assignment]
    saida: dict[str, object] = {"cliques": []}

    # O ESTADO VEM DA CENA, e não do socket: o daemon dela não é tocado. Trocar
    # a função dona é o que faz o `_tique` REAL rodar — o mesmo caminho do
    # produto, e não uma segunda montagem da carga.
    cenas: dict[str, object] = {"agora": cena()}

    def _do_duble(**_kw: object) -> dict[str, object]:
        # AS DUAS MANEIRAS DE O SERVIÇO CALAR, e a diferença é o passo 5 inteiro:
        #
        #   `{}`   o estado VAZIO chega ao pacote — é o dublê que a sprint pede,
        #          e é a metade desta posse: a aba diz e para de afirmar;
        #   `None` `estado_do_daemon` LEVANTA, que é o que o socket fechado faz
        #          de verdade — e aí o `_tique` do piloto imprime `[daemon mudo]`
        #          e RETORNA SEM CHAMAR O PACOTE. É a metade que não é desta
        #          posse (`hefesto_vivo.py` é `nao_toca`), e este ramo existe
        #          para MEDIR que ela falta, em vez de afirmar que falta.
        atual = cenas["agora"]
        if atual is None:
            raise mesa_viva.DaemonMudo("dublê: o serviço não respondeu")
        return dict(atual)  # type: ignore[arg-type]

    mesa_viva.estado_do_daemon = _do_duble  # type: ignore[assignment]

    def abrir() -> bool:
        piloto.view.load_uri(onde.pagina(ABA, publicado=publicado).as_uri())
        return False

    def _tique() -> bool:
        if piloto.pronto:
            piloto._tique()
        return False

    def _por(nome: str, nova: object):
        def passo() -> bool:
            cenas["agora"] = nova
            saida[f"cena-{nome}"] = "posta"
            return False
        return passo

    def _ler(nome: str):
        def passo() -> bool:
            def respondeu(texto: str | None, erro: Exception | None) -> None:
                saida[nome] = json.loads(texto) if texto and not erro else None
                saida[f"erro-{nome}"] = str(erro) if erro else ""
            piloto.ponte.perguntar(ROTEIRO_LER, respondeu)
            return False
        return passo

    def _clicar() -> bool:
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            lista = saida["cliques"]
            assert isinstance(lista, list)
            lista.append({"js": json.loads(texto) if texto and not erro else None,
                          "erro": str(erro) if erro else ""})
        piloto.ponte.perguntar(ROTEIRO_CLICAR_XBOX, respondeu)
        return False

    def _ler_o_perfil() -> bool:
        saida["modo-no-disco"] = _modo_no_disco()
        saida["modo-pela-aba-dez"] = _modo_pela_aba_dez()
        saida["ipc-do-clique"] = list(dubie.chamadas)
        return False

    def _foto(caminho: str):
        def passo() -> bool:
            if caminho:
                piloto.tela.fotografar(caminho)
            return False
        return passo

    def _no_tempo() -> bool:
        """A régua da A-TELA-SAMBA-01: N tiques com a MESA PARADA."""
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida["no_tempo"] = json.loads(texto) if texto and not erro else None
            saida["erro-no_tempo"] = str(erro) if erro else ""
        piloto.ponte.perguntar(
            "(function(){const c=[];for(let i=0;i<" + str(VOLTAS_NO_TEMPO)
            + ";i++){c.push(window.__hef.pintar(" + json.dumps(
                piloto._carga_de_agora, ensure_ascii=False, default=str)
            + "));} return JSON.stringify({primeira:c[0],"
              "depois:c.slice(1).reduce(function(a,b){return a+b;},0),"
              "voltas:c.length});})()", respondeu)
        return False

    t = 400
    GLib.timeout_add(t, abrir)
    # A CENA 1 — o P1 é o primário e o gamepad virtual dele degradou.
    for _ in range(3):
        t += 500
        GLib.timeout_add(t, _tique)
    t += 700
    GLib.timeout_add(t, _ler("p1-primario"))
    t += 500
    GLib.timeout_add(t, _foto(foto))
    # A CENA 2 — o primário PASSA para o P2. O marcador tem de andar.
    t += 500
    GLib.timeout_add(t, _por("p2", cena(primario=P2)))
    for _ in range(3):
        t += 400
        GLib.timeout_add(t, _tique)
    t += 700
    GLib.timeout_add(t, _ler("p2-primario"))
    # A CENA 3 — o backend continua `uinput` e o MOTIVO some. A marca some.
    t += 500
    GLib.timeout_add(t, _por("sem-motivo", cena(motivo=None)))
    for _ in range(3):
        t += 400
        GLib.timeout_add(t, _tique)
    t += 700
    GLib.timeout_add(t, _ler("sem-motivo"))
    # A MEDIDA NO TEMPO, com a mesa parada — antes de qualquer clique.
    t += 500
    GLib.timeout_add(t, _no_tempo)
    # O CLIQUE — o chip Xbox, que grava no perfil ativo.
    if fazer_o_clique:
        t += 900
        GLib.timeout_add(t, _clicar)
        t += 1500
        GLib.timeout_add(t, _ler_o_perfil)
    # A CENA 4 — o socket FECHA e `estado_do_daemon` LEVANTA, que é o caminho
    # REAL de hoje. O piloto sai do tique sem chamar o pacote, e a tela FICA
    # COM OS ÚLTIMOS VALORES: dois controles afirmados, nenhuma palavra de que
    # ninguém respondeu. É o RELATO desta sprint, medido em vez de afirmado —
    # e vem ANTES da cena 5 de propósito, com a mesa cheia na tela.
    t += 500
    GLib.timeout_add(t, _por("levanta", None))
    for _ in range(3):
        t += 400
        GLib.timeout_add(t, _tique)
    t += 700
    GLib.timeout_add(t, _ler("socket-fechado"))
    # A CENA 5 — o estado VAZIO chega ao pacote. A coluna tem de DIZER, e os
    # cartões, PARAR DE AFIRMAR. É o dublê que a sprint pede, e é a metade
    # desta posse.
    t += 500
    GLib.timeout_add(t, _por("calado", {}))
    for _ in range(3):
        t += 400
        GLib.timeout_add(t, _tique)
    t += 700
    GLib.timeout_add(t, _ler("servico-calado"))
    t += 800
    GLib.timeout_add(t, Gtk.main_quit)
    Gtk.main()
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foto-depois", default="",
                        help="a BANCADA com o marcador e a marca acesos")
    parser.add_argument("--foto-publicado", default="",
                        help="o que ela vê HOJE: a página publicada, sem os "
                             "dois endereços novos")
    opcoes = parser.parse_args()

    profiles_dir().mkdir(parents=True, exist_ok=True)
    save_profile(Profile(name=PERFIL, match=MatchAny(), priority=40),
                 origem="ensaio")

    print(f"lar de mentira: {_LAR}")
    print(f"perfil de ensaio: {PERFIL} — modo no disco: {_modo_no_disco()!r}")

    if opcoes.foto_publicado:
        print("\n=== O PUBLICADO — o que ela vê hoje ===")
        antes = _uma_volta(publicado=True, foto=opcoes.foto_publicado,
                           fazer_o_clique=False)
        _relatar(antes, "publicado")

    print("\n=== A BANCADA — o desenho de hoje ===")
    depois = _uma_volta(publicado=False, foto=opcoes.foto_depois)
    _relatar(depois, "bancada")
    return 0


def _relatar(saida: dict[str, object], onde_: str) -> None:
    for nome in ("p1-primario", "p2-primario", "sem-motivo", "socket-fechado",
                 "servico-calado"):
        bloco = saida.get(nome)
        print(f"\n-- {onde_} · {nome}")
        if not isinstance(bloco, dict):
            print(f"   SEM LEITURA ({saida.get(f'erro-{nome}')!r})")
            continue
        for c in bloco.get("cartoes") or []:
            print(f"   {c['lugar']:>3} · {str(c['identidade'])[:28]:<28} "
                  f"primário={c['primario']!s:<5} "  # (noqa-acento) chave de JSON
                  f"visível={c['primarioVisivel']!s:<5} "  # (noqa-acento) chave de JSON
                  f"alvo-da-fita={c['alvoDaFita']!s:<5} "
                  f"degradou={str(c['degradou'])[:44]!r}")
        at = bloco.get("atencao") or {}  # (noqa-acento) chave de JSON
        print(f"   Atenção: conta={at.get('conta')!r}")
        pares = zip(at.get("selos") or [], at.get("textos") or [], strict=False)
        for selo, texto in pares:
            if selo or texto:
                print(f"      [{selo}] {texto[:110]}")
    if "modo-no-disco" in saida:
        print(f"\n-- {onde_} · O CLIQUE NO CHIP «Xbox»")
        print(f"   js            : {saida.get('cliques')}")
        print(f"   IPC do gesto  : {saida.get('ipc-do-clique')}")
        print(f"   modo no disco : {saida.get('modo-no-disco')!r}")
        print(f"   modo pela a10 : {saida.get('modo-pela-aba-dez')!r}")
    if saida.get("no_tempo"):
        print(f"\n-- {onde_} · MUTAÇÕES com a mesa parada: {saida['no_tempo']}")


if __name__ == "__main__":
    raise SystemExit(main())
