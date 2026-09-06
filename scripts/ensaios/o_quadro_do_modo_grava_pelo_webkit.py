#!/usr/bin/env python3
"""Clica os QUATRO botões do quadro "Modo" dentro do WebKit, e lê o `.json`.

POR QUE ELE EXISTE (PERFIL-MODO-01, 06/09/2026): os testes de unidade provam a
CONTA — que `ProfileModeConfig` grava, que "none" remove a seção, que a máscara
não é inventada. O que eles NÃO provam é que **o clique dela chega**: o quadro
Modo nasceu hoje, e um botão que você acrescentou e nunca clicou não está
entregue. É a regra da casa, e o caso que a fundou foi o `--prova-gesto` dando
verde sobre dois botões mortos.

E ELE MEDE MAIS TRÊS COISAS que régua de Python nenhuma alcança:

1. **o alvo `classe`**: o pacote manda UM valor (`"gamepad"`) e o piloto tem de
   acender o botão certo e apagar os outros três;
2. **a lista dos jogos desta máquina**: que o `<datalist>` recebe as opções pelo
   `blocos` e que o `<input>` REALMENTE o consulta (`input.list` resolvendo para
   o elemento, no motor que ela usa — não no Chrome da bancada);
3. **o custo da espera pelo `--publicar 10`**: a mesma pintura na página
   PUBLICADA, onde o quadro ainda não existe.

**O DAEMON FICA DE FORA** e **NADA TOCA O PERFIL DELA**: o `HOME` e os quatro
`XDG_*` vão para um diretório temporário ANTES do primeiro import do pacote, e a
ponte é um dublê que anota.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_quadro_do_modo_grava_pelo_webkit.py
    scripts/ensaios/o_quadro_do_modo_grava_pelo_webkit.py --foto-antes a.png --foto-depois b.png
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
_LAR = pathlib.Path(tempfile.mkdtemp(prefix="ensaio-modo-"))
os.environ["HOME"] = str(_LAR)
for _x in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
    os.environ[_x] = str(_LAR / _x.lower())
os.environ["HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"] = "1"
# A CARONA DA STEAM FICA DESLIGADA: ela varre o `/proc` e a biblioteca DELA, e
# um ensaio não reescreve a `localconfig.vdf` de ninguém. É o mesmo portão que a
# `conftest.py` usa (`carona_do_wrapper.ligada()`).
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
from hefesto_dualsense4unix.interface import hefesto_vivo, onde  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes import a10_perfis, ponte  # noqa: E402
from hefesto_dualsense4unix.profiles.loader import (  # noqa: E402
    load_profile,
    profiles_dir,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile  # noqa: E402

ABA = "10-perfis.html"
PERFIL = "Ensaio do Modo"

#: A MESA DE MENTIRA — endereços MASCARADOS (octetos 4 e 5 zerados).
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
]

#: QUANTAS VOLTAS A MEDIDA NO TEMPO DÁ. 100 é o mesmo número do
#: `--conta-mutacoes` do piloto.
VOLTAS_NO_TEMPO = 100

#: O CATÁLOGO DE MENTIRA — a biblioteca DELA nunca é lida por um ensaio.
JOGOS = {"851100": "Sea of Stars", "1245620": "ELDEN RING"}

_FERRAMENTAS = r"""
  function estadoDoModo(){
    const bs = Array.prototype.slice.call(
      document.querySelectorAll('[data-hef="editor.modo"]'));
    const campo = document.querySelector('[data-hef="editor.jogo"]');
    const lista = document.querySelector('datalist[data-hef="editor.jogo.lista"]');
    return {
      botoes: bs.map(function(b){
        return {modo: b.dataset.hefQuando, texto: b.textContent,
                aceso: b.classList.contains('on')};
      }),
      // A METADE QUE SÓ O MOTOR DELA RESPONDE: o `<input>` acha o `<datalist>`?
      campoLigado: !!(campo && campo.list && lista && campo.list === lista),
      itens: lista ? Array.prototype.map.call(lista.querySelectorAll('option'),
                function(o){ return o.value + '|' + o.label; }) : null
    };
  }
"""

#: A MEDIDA NO TEMPO — a régua da `A-TELA-SAMBA-01` aplicada a estes dois
#: endereços. Pintar a MESMA carga N vezes tem de escrever ZERO depois da
#: primeira: o alvo `classe` compara antes de mexer e o `blocos` só reescreve
#: quando o `innerHTML` diverge. Um alvo que devolvesse 1 sempre repintaria o
#: `<datalist>` e o quadro dez vezes por segundo, para sempre.
ROTEIRO_NO_TEMPO = r"""
(function(){
  const carga = __CARGA__;
  const conta = [];
  for(let i = 0; i < __VOLTAS__; i++){ conta.push(window.__hef.pintar(carga)); }
  return JSON.stringify({primeira: conta[0],
                         depois: conta.slice(1).reduce(function(a,b){return a+b;}, 0),
                         voltas: conta.length});
})()
"""

ROTEIRO_PINTAR = r"""
(function(){
""" + _FERRAMENTAS + r"""
  const desenho = estadoDoModo();
  const escreveu = window.__hef.pintar(__CARGA__);
  return JSON.stringify({desenho: desenho, escreveu: escreveu,
                         pintado: estadoDoModo()});
})()
"""


def _roteiro_do_clique(modo: str) -> str:
    return r"""
(function(){
""" + _FERRAMENTAS + r"""
  const b = document.querySelector('[data-hef="editor.modo"][data-hef-quando="__MODO__"]');
  if(!b){ return JSON.stringify({achou:false}); }
  b.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  return JSON.stringify({achou:true, texto:b.textContent});
})()
""".replace("__MODO__", modo)


BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


class PonteDeMentira:
    """Anota, e não fala com o daemon dela."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch({nome!r})")
        return True

    def chamar(self, metodo: str, *a: object, **kw: object) -> bool:
        self.chamadas.append(f"chamar({metodo!r})")
        return True

    def resultado(self, metodo: str, *a: object, **kw: object) -> object:
        self.chamadas.append(f"resultado({metodo!r})")
        return {}


def _modo_no_disco() -> object:
    prof = load_profile(PERFIL)
    modo = getattr(prof, "mode", None)
    if modo is None:
        return None
    return {"kind": modo.kind, "gamepad_flavor": modo.gamepad_flavor}


def _carga() -> dict[str, object]:
    """O que o pacote manda para a página — o editor e o bloco da lista."""
    prof = load_profile(PERFIL)
    editor = perfis_web._pacote_do_editor(prof)
    return {"mesa": {"editor.modo": editor["modo"],
                     "editor.jogo": editor.get("jogo") or "—"},
            "blocos": {a10_perfis.SELETOR_DOS_JOGOS: a10_perfis._html_dos_jogos()}}


def _uma_volta(publicado: bool, cliques: list[str],
               foto_antes: str = "", foto_depois: str = "") -> dict[str, object]:
    """Abre a página, pinta, clica cada modo, e devolve o que a tela mostrou."""
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    piloto._mesa_de_agora = list(MESA)
    piloto._ctx_de_agora.mesa = list(MESA)
    piloto._ctx_de_agora.conectados = list(MESA)
    piloto._ctx_de_agora.state = {"active_profile": None}
    a10_perfis._ESCOLHIDO = PERFIL
    saida: dict[str, object] = {"cliques": []}

    def abrir() -> bool:
        piloto.view.load_uri(onde.pagina(ABA, publicado=publicado).as_uri())
        return False

    def _pintar(chave: str):
        def passo() -> bool:
            if not piloto.pronto:
                return True

            def respondeu(texto: str | None, erro: Exception | None) -> None:
                saida[chave] = json.loads(texto) if texto and not erro else None
                saida[f"erro-{chave}"] = str(erro) if erro else ""
            piloto.ponte.perguntar(
                ROTEIRO_PINTAR.replace("__CARGA__", json.dumps(_carga())),
                respondeu)
            return False
        return passo

    def _clicar(modo: str):
        def passo() -> bool:
            def respondeu(texto: str | None, erro: Exception | None) -> None:
                lista = saida["cliques"]
                assert isinstance(lista, list)
                lista.append({"modo": modo,
                              "js": json.loads(texto) if texto and not erro else None,
                              "erro": str(erro) if erro else ""})
            piloto.ponte.perguntar(_roteiro_do_clique(modo), respondeu)
            return False
        return passo

    def _ler_o_disco(modo: str):
        def passo() -> bool:
            lista = saida["cliques"]
            assert isinstance(lista, list)
            for entrada in lista:
                if entrada["modo"] == modo and "disco" not in entrada:
                    entrada["disco"] = _modo_no_disco()
            return False
        return passo

    def _foto(caminho: str):
        def passo() -> bool:
            if caminho:
                piloto.tela.fotografar(caminho)
            return False
        return passo

    GLib.timeout_add(400, abrir)
    GLib.timeout_add(2600, _pintar("antes"))
    GLib.timeout_add(3400, _foto(foto_antes))
    # UM CLIQUE POR VEZ, com folga entre eles: o gesto roda em THREAD
    # (`hefesto_vivo._gesto`), e ler o disco cedo demais mediria o clique
    # anterior. 1200 ms é o dobro do tique desta aba.
    t = 4200
    for modo in cliques:
        GLib.timeout_add(t, _clicar(modo))
        GLib.timeout_add(t + 900, _ler_o_disco(modo))
        t += 1200
    GLib.timeout_add(t, _pintar("depois"))
    t += 900

    def _no_tempo() -> bool:
        def respondeu(texto: str | None, erro: Exception | None) -> None:
            saida["no_tempo"] = json.loads(texto) if texto and not erro else None
            saida["erro-no_tempo"] = str(erro) if erro else ""
        piloto.ponte.perguntar(
            ROTEIRO_NO_TEMPO.replace("__CARGA__", json.dumps(_carga()))
            .replace("__VOLTAS__", str(VOLTAS_NO_TEMPO)), respondeu)
        return False

    GLib.timeout_add(t, _no_tempo)
    GLib.timeout_add(t + 800, _foto(foto_depois))
    GLib.timeout_add(t + 1600, Gtk.main_quit)
    Gtk.main()
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foto-antes", default="",
                        help="a BANCADA com o quadro Modo, antes dos cliques")
    parser.add_argument("--foto-depois", default="",
                        help="a BANCADA depois dos quatro cliques")
    parser.add_argument("--foto-publicado", default="",
                        help="o que ela vê HOJE: a página que o produto "
                             "renderiza, sem o quadro Modo")
    opcoes = parser.parse_args()

    profiles_dir().mkdir(parents=True, exist_ok=True)
    save_profile(Profile(name=PERFIL, match=MatchAny(), priority=40),
                 origem="ensaio")

    dubie = PonteDeMentira()
    ponte.profile_switch = dubie.profile_switch    # type: ignore[assignment]
    ponte.chamar = dubie.chamar                    # type: ignore[assignment]
    ponte.resultado = dubie.resultado              # type: ignore[assignment]
    a10_perfis._nomes_dos_jogos = lambda: dict(JOGOS)  # type: ignore[assignment]

    def _mudo() -> dict[str, object]:
        raise RuntimeError("ensaio: o daemon dela fica de fora")
    hefesto_vivo.mesa_viva.estado_do_daemon = _mudo  # type: ignore[assignment]

    ordem = [ident for ident, _ in perfis_web.MODO_DO_PERFIL.items()
             if ident != perfis_web.MODO_SEM_OPINIAO] + [perfis_web.MODO_SEM_OPINIAO]

    print(f"  o lar de mentira    {profiles_dir()}")
    print(f"  o modo ANTES        {_modo_no_disco()}")
    bancada = _uma_volta(False, ordem, opcoes.foto_antes, opcoes.foto_depois)
    print(f"  o modo DEPOIS       {_modo_no_disco()}")
    print(f"  a ponte ouviu       {dubie.chamadas}")

    falhas: list[str] = []
    antes = bancada.get("antes") or {}
    if not isinstance(antes, dict) or not antes.get("pintado"):
        return _reprovar(["a página da bancada não pintou — "
                          f"{bancada.get('erro-antes')!r}"])
    pintado = antes["pintado"]
    acesos = [b["modo"] for b in pintado["botoes"] if b["aceso"]]
    print(f"  --- BANCADA, antes do primeiro clique ---")
    print(f"    botões no desenho  {[b['modo'] for b in pintado['botoes']]}")
    print(f"    aceso pela pintura {acesos}")
    print(f"    a pintura escreveu {antes.get('escreveu')} valor(es)")
    print(f"    o campo consulta a lista?  {pintado['campoLigado']}")
    print(f"    opções da lista    {pintado['itens']}")

    if len(pintado["botoes"]) != len(perfis_web.MODO_DO_PERFIL):
        falhas.append(f"o quadro tem {len(pintado['botoes'])} botões e o dono "
                      f"tem {len(perfis_web.MODO_DO_PERFIL)}")
    if acesos != [perfis_web.MODO_SEM_OPINIAO]:
        falhas.append(f"um perfil SEM seção `mode` devia acender só «Não mexer "
                      f"no modo»; acendeu {acesos}")
    if not pintado["campoLigado"]:
        falhas.append("o `<input>` do jogo NÃO consulta o `<datalist>` no "
                      "WebKit — a lista existe e ninguém a lê")
    if sorted(pintado["itens"] or []) != sorted(
            f"{a}|{n} (appid {a})" for a, n in JOGOS.items()):
        falhas.append(f"a lista dos jogos não chegou ao DOM: {pintado['itens']}")

    print("  --- OS QUATRO CLIQUES ---")
    cliques = bancada.get("cliques") or []
    assert isinstance(cliques, list)
    for entrada in cliques:
        print(f"    {entrada['modo']:<8} achou={(entrada['js'] or {}).get('achou')} "
              f"texto={(entrada['js'] or {}).get('texto')!r} "
              f"-> disco {entrada.get('disco')}")
        if not (entrada["js"] or {}).get("achou"):
            falhas.append(f"não achei o botão do modo `{entrada['modo']}`")
            continue
        disco = entrada.get("disco")
        if entrada["modo"] == perfis_web.MODO_SEM_OPINIAO:
            if disco is not None:
                falhas.append(f"«Não mexer no modo» deixou {disco} no perfil")
        elif not isinstance(disco, dict) or disco.get("kind") != entrada["modo"]:
            falhas.append(f"o clique em `{entrada['modo']}` não gravou: {disco}")

    no_tempo = bancada.get("no_tempo") or {}
    print(f"  --- NO TEMPO ({no_tempo.get('voltas')} pinturas da MESMA carga) ---")
    print(f"    a primeira escreveu {no_tempo.get('primeira')} valor(es)")
    print(f"    as outras somaram   {no_tempo.get('depois')}")
    if no_tempo.get("depois") not in (0, None):
        falhas.append(f"a pintura NÃO é idempotente: {no_tempo.get('depois')} "
                      f"escritas depois da primeira — a tela repinta o quadro e "
                      f"a lista a cada tique, para sempre")
    if no_tempo.get("primeira") is None:
        falhas.append(f"a medida no tempo não voltou: {bancada.get('erro-no_tempo')!r}")

    depois = bancada.get("depois") or {}
    if isinstance(depois, dict) and depois.get("pintado"):
        acesos_no_fim = [b["modo"] for b in depois["pintado"]["botoes"] if b["aceso"]]
        print(f"  aceso no fim         {acesos_no_fim}")
        if acesos_no_fim != [perfis_web.MODO_SEM_OPINIAO]:
            falhas.append(f"o último clique foi «Não mexer no modo» e a tela "
                          f"acende {acesos_no_fim}")

    # A VOLTA NO PUBLICADO — o custo da espera pelo `--publicar 10`, que é dela.
    save_profile(Profile(name=PERFIL, match=MatchAny(), priority=40),
                 origem="ensaio")
    publicado = _uma_volta(True, [], opcoes.foto_publicado)
    p_ant = (publicado.get("antes") or {}).get("pintado") or {}
    print("  --- PUBLICADO, a mesma pintura ---")
    print(f"    botões do modo     {len(p_ant.get('botoes') or [])}")
    print(f"    o campo consulta a lista?  {p_ant.get('campoLigado')}")
    print("    (zero é o esperado HOJE: o quadro e a lista esperam o "
          "`--publicar 10`, que é ato dela)")

    return _reprovar(falhas)


def _reprovar(falhas: list[str]) -> int:
    if falhas:
        print("\nREPROVA:\n  " + "\n  ".join(falhas))
        return 1
    print("\nAPROVA: os quatro cliques chegaram, os quatro gravaram o que "
          "prometem, «Não mexer no modo» removeu a seção, e o campo do jogo "
          "consulta a lista desta máquina no motor que ela usa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
