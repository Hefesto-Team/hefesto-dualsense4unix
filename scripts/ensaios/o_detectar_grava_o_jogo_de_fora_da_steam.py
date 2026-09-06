#!/usr/bin/env python3
"""Clica **Detectar** dentro do WebKit com uma janela que NÃO é da Steam, e lê o
`.json` que saiu do outro lado.

POR QUE ELE EXISTE (ONDA5-10-01, 06/09/2026, decisão 10-Q2 dela): os testes de
unidade provam a CONTA — que `from_simple_choice("janela", …)` grava, que
`detect_simple_preset` reconhece, que o gesto devolve a notícia. O que eles NÃO
provam é que o CLIQUE DELA CHEGA: o botão "Detectar" prometia no `title`
*"funciona com jogo de qualquer lugar"* e recusava todo jogo de fora da Steam,
mandando a pessoa para a linha de comando. **Botão que você mudou e nunca
clicou não está entregue.**

E ELE MEDE UMA SEGUNDA COISA, que é a razão de a divergência do desenho estar
declarada em `mockup/DIVERGENCIAS.md`: o seletor "Funciona em" ganhou a sexta
opção na BANCADA e o PUBLICADO ainda não a tem. Este ensaio pinta o mesmo perfil
nas DUAS páginas e mostra o que o campo fica mostrando em cada uma — o custo
exato da espera pelo `--publicar 10`, que é ato dela.

O CAMINHO DELA, no motor que ela usa:

1. abre a página no ``WebKit2.WebView`` do piloto (a da BANCADA e a do
   PUBLICADO, uma por vez);
2. **pinta** o que o pacote emite e lê o seletor, o cadeado e o campo do jogo;
3. **clica** no `[data-hef-gesto="detectar"]` como o navegador clica
   (`click` de verdade, `bubbles:true`) — é o evento que o ouvinte delegado do
   piloto escuta;
4. lê o `.json` do perfil no disco, ANTES e DEPOIS.

**O DAEMON FICA DE FORA**, e a mesa e a classe de janela são impostas: o que se
mede é o CAMINHO DO CLIQUE, não a leitura do aparelho.

**NADA TOCA O PERFIL DELA.** O `HOME` e os quatro `XDG_*` vão para um diretório
temporário ANTES do primeiro import do pacote, e a ponte é um dublê que anota.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_detectar_grava_o_jogo_de_fora_da_steam.py
    scripts/ensaios/o_detectar_grava_o_jogo_de_fora_da_steam.py --foto-antes a.png --foto-depois b.png
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
_LAR = pathlib.Path(tempfile.mkdtemp(prefix="ensaio-detectar-"))
os.environ["HOME"] = str(_LAR)
for _x in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
    os.environ[_x] = str(_LAR / _x.lower())
os.environ["HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"] = "1"

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

from hefesto_dualsense4unix.interface import hefesto_vivo, onde  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes import ponte  # noqa: E402
from hefesto_dualsense4unix.profiles.loader import (  # noqa: E402
    load_profile,
    profiles_dir,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile  # noqa: E402
from hefesto_dualsense4unix.profiles.simple_match import (  # noqa: E402
    detect_simple_preset,
)

ABA = "10-perfis.html"
PERFIL = "Ensaio do Detectar"
#: A CLASSE QUE O DETECTOR VÊ, e ela NÃO é da Steam de propósito: um
#: `steam_app_<id>` mediria o ramo velho e daria verde sobre a entrega inteira.
#: `GrimFandango` é a classe de um perfil de fábrica de verdade
#: (`assets/profiles_default/point_and_click.json`).
CLASSE = "GrimFandango"

#: A MESA DE MENTIRA — endereços MASCARADOS (octetos 4 e 5 zerados).
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
]

_FERRAMENTAS = r"""
  function ler(sel){
    const el = document.querySelector(sel);
    if(!el){ return null; }
    return String(el.value ?? el.textContent);
  }
  function estado(){
    const trava = document.querySelector('[data-hef="editor.ambiente.travado"]');
    return {ambiente: ler('[data-hef="editor.ambiente"]'),
            jogo: ler('[data-hef="editor.jogo"]'),
            cadeado: trava ? trava.className : null,
            itens: Array.prototype.map.call(
              document.querySelectorAll('select[data-hef="editor.ambiente"] option'),
              function(o){ return o.text; })};
  }
"""

#: PRIMEIRO TEMPO — pinta o perfil e lê o que a tela mostra ANTES do clique.
ROTEIRO_ANTES = r"""
(function(){
""" + _FERRAMENTAS + r"""
  const desenho = estado();
  const escreveu = window.__hef.pintar({mesa: __PACOTE__});
  return JSON.stringify({desenho: desenho, escreveu: escreveu,
                         pintado: estado()});
})()
"""

#: SEGUNDO TEMPO — O CLIQUE. `el.click()` não basta para o ouvinte delegado com
#: captura? Basta: ele dispara um `click` que borbulha. Mas o ensaio manda o
#: evento à mão para deixar explícito que é o MESMO evento do navegador.
ROTEIRO_CLIQUE = r"""
(function(){
""" + _FERRAMENTAS + r"""
  const b = document.querySelector('[data-hef-gesto="detectar"]');
  if(!b){ return JSON.stringify({achou:false}); }
  b.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  return JSON.stringify({achou:true, title: b.getAttribute('title') || '',
                         apos_o_clique: estado()});
})()
"""

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


def _regra_no_disco() -> dict[str, object]:
    prof = load_profile(PERFIL)
    return {"tipo": getattr(prof.match, "type", "?"),
            "window_class": list(getattr(prof.match, "window_class", []) or []),
            "process_name": list(getattr(prof.match, "process_name", []) or []),
            "preset": detect_simple_preset(prof.match)}


def _uma_volta(publicado: bool, foto: str = "") -> dict[str, object]:
    """Abre a página, pinta, clica, e devolve o que a tela mostrou."""
    from hefesto_dualsense4unix.app.actions import perfis_web
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis

    prof = load_profile(PERFIL)
    editor = perfis_web._pacote_do_editor(prof)
    pacote = {"editor.ambiente": editor.get("ambiente") or "—",
              "editor.jogo": editor.get("jogo") or "—",
              "editor.ambiente.travado": "sim" if editor.get("ambiente_travado") else "",
              "editor.ambiente.recado": editor.get("ambiente_recado") or ""}

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    piloto._mesa_de_agora = list(MESA)
    piloto._ctx_de_agora.mesa = list(MESA)
    piloto._ctx_de_agora.conectados = list(MESA)
    # A CLASSE É IMPOSTA: sem daemon não há `window_detect_last_class`, e é
    # exatamente ela que o gesto lê.
    piloto._ctx_de_agora.state = {"active_profile": None,
                                  "window_detect_last_class": CLASSE}
    a10_perfis._ESCOLHIDO = PERFIL
    saida: dict[str, object] = {}

    def abrir() -> bool:
        piloto.view.load_uri(onde.pagina(ABA, publicado=publicado).as_uri())
        return False

    def _mandar(roteiro: str, chave: str):
        def passo() -> bool:
            if not piloto.pronto:
                return True

            def respondeu(texto: str | None, erro: Exception | None) -> None:
                saida[chave] = json.loads(texto) if texto and not erro else None
                saida[f"erro-{chave}"] = str(erro) if erro else ""
            piloto.ponte.perguntar(roteiro, respondeu)
            return False
        return passo

    def retratar() -> bool:
        if foto:
            piloto.tela.fotografar(foto)
        return False

    GLib.timeout_add(400, abrir)
    GLib.timeout_add(2600, _mandar(ROTEIRO_ANTES.replace(
        "__PACOTE__", json.dumps(pacote)), "antes"))
    GLib.timeout_add(3600, retratar)
    GLib.timeout_add(4200, _mandar(ROTEIRO_CLIQUE, "clique"))
    # O GESTO RODA EM THREAD (`hefesto_vivo._gesto`): o laço tem de continuar
    # vivo depois do clique, senão o ensaio lê o disco antes de o gesto escrever.
    GLib.timeout_add(7000, Gtk.main_quit)
    Gtk.main()
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foto-antes", default="")
    parser.add_argument("--foto-depois", default="")
    opcoes = parser.parse_args()

    profiles_dir().mkdir(parents=True, exist_ok=True)
    save_profile(Profile(name=PERFIL, match=MatchAny(), priority=40),
                 origem="ensaio")
    antes = _regra_no_disco()

    dubie = PonteDeMentira()
    ponte.profile_switch = dubie.profile_switch  # type: ignore[assignment]
    ponte.chamar = dubie.chamar                  # type: ignore[assignment]
    ponte.resultado = dubie.resultado            # type: ignore[assignment]

    def _mudo() -> dict[str, object]:
        raise RuntimeError("ensaio: o daemon dela fica de fora")
    hefesto_vivo.mesa_viva.estado_do_daemon = _mudo  # type: ignore[assignment]

    # VOLTA 1 — A BANCADA com o perfil em "Todos": a foto do ANTES, e o CLIQUE.
    bancada = _uma_volta(publicado=False, foto=opcoes.foto_antes)
    depois = _regra_no_disco()

    # VOLTA 2 — A BANCADA de novo, com a regra já no disco: a foto do DEPOIS.
    # É onde se vê o seletor mostrando "Jogo (pela janela)" e o cadeado APAGADO
    # — o perfil que antes desta sprint abriria travado.
    reaberto = _uma_volta(publicado=False, foto=opcoes.foto_depois)

    # VOLTA 3 — O PUBLICADO, com a MESMA regra no disco. Ela mede o custo da
    # espera pelo `--publicar 10`, que é ato dela.
    publicado = _uma_volta(publicado=True)

    print(f"  o lar de mentira    {profiles_dir()}")
    print(f"  a classe em foco    {CLASSE!r} (NÃO é da Steam)")
    print(f"  a regra ANTES       {antes}")
    print(f"  a regra DEPOIS      {depois}")
    print(f"  a ponte ouviu       {dubie.chamadas}")
    for nome, volta in (("BANCADA · antes do clique", bancada),
                        ("BANCADA · reaberto com a regra no disco", reaberto),
                        ("PUBLICADO · a mesma regra, sem a opção", publicado)):
        clique = volta.get("clique") or {}
        antes_da_tela = volta.get("antes") or {}
        print(f"  --- {nome} ---")
        print(f"    opções do seletor  {(antes_da_tela.get('pintado') or {}).get('itens')}")
        print(f"    a pintura escreveu {antes_da_tela.get('escreveu')} valor(es)")
        print(f"    o campo mostrou    {(antes_da_tela.get('pintado') or {}).get('ambiente')!r}")
        print(f"    o title promete    {str(clique.get('title'))[:70]!r}")
        print(f"    após o clique      {clique.get('apos_o_clique')}")

    falhas: list[str] = []
    if depois["window_class"] != [CLASSE]:
        falhas.append(f"o Detectar não gravou a classe: {depois}")
    if depois["preset"] != "janela":
        falhas.append(f"a regra gravada não volta como forma que a tela mostra: {depois}")
    da_bancada = ((bancada.get("antes") or {}).get("pintado") or {})
    if "Jogo (pela janela)" not in (da_bancada.get("itens") or []):
        falhas.append("a BANCADA não oferece a sexta opção no seletor")
    if not ((bancada.get("clique") or {}).get("achou")):
        falhas.append("não achei o botão Detectar na página")
    reab = ((reaberto.get("antes") or {}).get("pintado") or {})
    if reab.get("ambiente") != "Jogo (pela janela)":
        falhas.append(f"a BANCADA reaberta não mostra o rótulo da regra nova: "
                      f"{reab.get('ambiente')!r} — o perfil abriria dizendo "
                      f"outra coisa")
    # O ALVO `classe` acende com a classe `on` (`hefesto_vivo.escrever`, ramo
    # `classe`, `el.dataset.hefClasse || 'on'`).
    if "on" in str(reab.get("cadeado") or "").split():
        falhas.append("o cadeado continua aceso sobre uma regra que a tela "
                      "agora sabe mostrar")
    if falhas:
        print("\nREPROVA:\n  " + "\n  ".join(falhas))
        return 1
    print("\nAPROVA: o clique chegou, a classe virou regra, e a regra volta como "
          "“janela” — a forma que a tela sabe mostrar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
