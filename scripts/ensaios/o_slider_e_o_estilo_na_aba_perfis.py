#!/usr/bin/env python3
"""Arrasta a Prioridade e escolhe um Estilo de Jogo **dentro do WebKit**, e lê o
`.json` que saiu do outro lado.

POR QUE ELE EXISTE, e é a regra desta casa: os testes de unidade provam a CONTA
— que o gesto grava a prioridade certa, que o estilo escreve gatilho, vibração e
uma cor por unidade. O que eles NÃO provam é que o clique dela CHEGA: o
`<input type=range>` nasceu hoje, e um campo que o ouvinte do piloto não
alcançasse daria verde em toda régua de Python e silêncio na tela.

O ENSAIO FAZ O CAMINHO DELA, no motor que ela usa:

1. abre a página **da BANCADA** (`mockup/10-perfis.html`) no
   ``WebKit2.WebView`` do piloto — ver `A PÁGINA É A DA BANCADA` abaixo;
2. **pinta** o que o pacote emite (`window.__hef.pintar`) e lê o punho e a
   barra — é a prova de que o endereço novo existe e recebe;
3. arrasta o slider como o navegador arrasta (`el.value = …` + um ``change``
   de verdade, `bubbles:true`), que é o evento que o ouvinte do piloto escuta;
4. escolhe "Terror" no `<select>` do Estilo de Jogo, do mesmo jeito;
5. lê o `.json` do perfil no disco, ANTES e DEPOIS.

**O DAEMON FICA DE FORA, e é escolha.** `mesa_viva.estado_do_daemon` é trocado
por um que levanta, então o tique do piloto sai antes de tocar a mesa — o que
este ensaio mede é o CAMINHO DO CLIQUE e o da PINTURA, não a leitura do
aparelho. Sem isso ele dependeria de quantos controles estão na mesa dela agora,
e um ensaio que muda de resultado conforme o cabo não mede nada.

**A PÁGINA É A DA BANCADA, e isto é a coisa mais importante deste arquivo.** O
piloto abre `interface/paginas/` (`onde.pagina(..., publicado=True)`), e o
DESENHO do slider ainda não foi publicado — publicar é ato dela
(`check_o_desenho_aprovado.py --publicar 10`), e nenhuma frente o faz. Então o
ensaio carrega o `mockup/` à mão. O que ele mede é exatamente o que ela vai
receber quando aprovar: o mesmo HTML, o mesmo motor, o mesmo despachante.

**NADA TOCA O PERFIL DELA.** O `HOME` e os quatro `XDG_*` são desviados para um
diretório temporário ANTES do primeiro import do pacote, e o perfil de ensaio é
escrito lá. E a ponte é trocada por um dublê que ANOTA em vez de falar com o
daemon vivo: `gravar_e_reaplicar` termina em `launch_env.refresh`, e um ensaio
não tem por que mexer no daemon que ela está usando.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/o_slider_e_o_estilo_na_aba_perfis.py
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
_LAR = pathlib.Path(tempfile.mkdtemp(prefix="ensaio-perfis-"))
os.environ["HOME"] = str(_LAR)
for _x in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
    os.environ[_x] = str(_LAR / _x.lower())
os.environ["HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"] = "1"

sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo, onde
from hefesto_dualsense4unix.interface.pacotes import ponte
from hefesto_dualsense4unix.profiles.loader import (
    load_profile,
    profiles_dir,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    MatchAny,
    Profile,
)

ABA = "10-perfis.html"
PERFIL = "Ensaio do Slider"

#: A MESA DE MENTIRA — endereços MASCARADOS (octetos 4 e 5 zerados), a máscara
#: da casa. Dois lugares, porque é o que a mesa dela tem e porque é com DOIS que
#: a regra da cor dela pode ser conferida: as duas unidades têm de sair
#: diferentes.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "white",
     "nome": "White", "via": "BT", "transporte": "bt", "alvo": False},
]

#: A PRIORIDADE QUE O ENSAIO ARRASTA. Ela é o valor NOVO; o perfil nasce noutro.
DE, PARA = 40, 137
#: E A LARGURA DA BARRA É A CONTA — pelo TETO do esquema, nunca por 100.
PCT = round(DE * 100 / PRIORIDADE_MAXIMA)
ESTILO = "Terror"

#: AS FUNÇÕES QUE OS DOIS ROTEIROS COMPARTILHAM. `el.value = …` sozinho NÃO
#: dispara evento nenhum (é a regra do DOM para escrita programática), e o
#: ouvinte do piloto é delegado no `document` — por isso o `change` vai com
#: `bubbles:true`. É o que o navegador faz quando ela solta o punho.
_FERRAMENTAS = r"""
  function mexer(sel, valor){
    const el = document.querySelector(sel);
    if(!el){ return {achou:false}; }
    el.value = valor;
    el.dispatchEvent(new Event('change', {bubbles:true}));
    return {achou:true, valor:String(el.value), tag:el.tagName,
            min:el.min || null, max:el.max || null};
  }
  function ler(sel, prop){
    const el = document.querySelector(sel);
    if(!el){ return null; }
    return prop === 'largura' ? el.style.width : String(el.value ?? el.textContent);
  }
  function trio(){
    return {punho: ler('[data-hef="editor.prioridade.escolha"]', 'valor'),
            barra: ler('[data-hef="editor.prioridade"]', 'largura'),
            n: ler('[data-hef="editor.prioridade.n"]', 'texto')};
  }
"""

#: O PRIMEIRO TEMPO — a PINTURA e o ARRASTO.
#:
#: A pintura é metade da prova: o pacote emite `editor.prioridade.escolha` (o
#: número cru), `editor.prioridade` (a largura) e `editor.prioridade.n` (a
#: legenda). `pintar()` devolve QUANTOS valores escreveu — zero seria endereço
#: que a página não tem, que é o defeito que fez a `06-navegacao` publicar zero
#: endereços em 01/09 sem ninguém ver.
ROTEIRO_1 = (r"""
(function(){
""" + _FERRAMENTAS + r"""
  const desenho = trio();
  const escreveu = window.__hef.pintar({mesa: {
      "editor.prioridade.escolha": "__DE__",
      "editor.prioridade": "__PCT__",
      "editor.prioridade.n": "__DE__"}});
  const pintado = trio();
  const punho = mexer('[data-hef="editor.prioridade.escolha"]', '__PARA__');
  return JSON.stringify({desenho: desenho, escreveu: escreveu,
                         pintado: pintado, punho: punho});
})()
""").replace("__PARA__", str(PARA)).replace("__DE__", str(DE)) \
    .replace("__PCT__", str(PCT))

#: O SEGUNDO TEMPO — o ESTILO, e ele roda DEPOIS que o primeiro gravou.
#:
#: OS DOIS NÃO PODEM IR JUNTOS, e o ensaio mediu por quê: cada gesto roda em
#: THREAD (`hefesto_vivo._gesto`) e os dois leem o perfil do disco antes de
#: escrever. Disparados no mesmo instante, o segundo grava por cima do que o
#: primeiro acabou de salvar — e o `.json` sai com metade da entrega. Isso não
#: é caminho DELA (ninguém arrasta o punho e escolhe no `<select>` no mesmo
#: milissegundo), mas é um instrumento que mentiria: ele acusaria de mudo um
#: gesto que trabalhou.
ROTEIRO_2 = (r"""
(function(){
""" + _FERRAMENTAS + r"""
  const estilo = mexer('[data-hef="editor.estilo"]', '__ESTILO__');
  return JSON.stringify({estilo: estilo, apos_o_arrasto: trio()});
})()
""").replace("__ESTILO__", ESTILO)

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


class PonteDeMentira:
    """Anota, e não fala com o daemon dela. Ver o cabeçalho."""

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


def _retrato() -> dict[str, object]:
    """O que o `.json` guarda, nas três coisas que o estilo mexe."""
    prof = load_profile(PERFIL)
    cores = {}
    for uniq, cfg in (prof.controllers or {}).items():
        leds = getattr(cfg, "leds", None)
        if leds is not None:
            cores[uniq] = (tuple(leds.lightbar), round(leds.lightbar_brightness, 3))
    return {
        "prioridade": prof.priority,
        "gatilho": (prof.triggers.left.mode, prof.triggers.right.mode),
        "params": list(prof.triggers.left.params),
        "vibracao": prof.rumble.policy,
        "cores": cores,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foto", default="",
                        help="retrata a BANCADA com o punho já arrastado")
    opcoes = parser.parse_args()

    profiles_dir().mkdir(parents=True, exist_ok=True)
    save_profile(Profile(name=PERFIL, match=MatchAny(), priority=DE),
                 origem="ensaio")
    antes = _retrato()

    dubie = PonteDeMentira()
    ponte.profile_switch = dubie.profile_switch  # type: ignore[assignment]
    ponte.chamar = dubie.chamar                  # type: ignore[assignment]
    ponte.resultado = dubie.resultado            # type: ignore[assignment]

    # O DAEMON DELA FICA FORA — ver o cabeçalho. Com o `estado_do_daemon`
    # levantando, o tique do piloto sai ANTES de tocar `_mesa_de_agora`, e a
    # mesa de mentira abaixo sobrevive ao ensaio inteiro.
    def _mudo() -> dict[str, object]:
        raise RuntimeError("ensaio: o daemon dela fica de fora")
    hefesto_vivo.mesa_viva.estado_do_daemon = _mudo  # type: ignore[assignment]

    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    # A MESA É IMPOSTA: sem daemon o piloto veria mesa vazia, e o estilo não
    # teria a quem dar cor — o ensaio daria verde sobre a metade da entrega.
    piloto._mesa_de_agora = list(MESA)
    piloto._ctx_de_agora.mesa = list(MESA)
    piloto._ctx_de_agora.conectados = list(MESA)
    piloto._ctx_de_agora.state = {"active_profile": None}
    saida: dict[str, object] = {"tela": None}

    def abrir() -> bool:
        piloto.view.load_uri(onde.pagina(ABA, publicado=False).as_uri())
        return False

    def escolher_o_perfil() -> bool:
        # O EDITOR AGE SOBRE O PERFIL ESCOLHIDO, e sem isto `_perfil_do_editor`
        # recusa dizendo "escolha um perfil na lista primeiro" — que é o certo.
        from hefesto_dualsense4unix.interface.pacotes import a10_perfis
        a10_perfis._ESCOLHIDO = PERFIL
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

    def entre_os_dois() -> bool:
        saida["meio"] = _retrato()
        return False

    GLib.timeout_add(400, abrir)
    GLib.timeout_add(2600, escolher_o_perfil)
    GLib.timeout_add(3000, _mandar(ROTEIRO_1, "tela"))
    # O GESTO RODA EM THREAD (`hefesto_vivo._gesto`), então o laço tem de
    # continuar vivo depois do clique — senão o ensaio lê o disco antes de o
    # gesto o escrever, e acusaria a cura de não fazer nada.
    GLib.timeout_add(5500, entre_os_dois)
    GLib.timeout_add(5800, _mandar(ROTEIRO_2, "tela2"))

    def retratar() -> bool:
        if opcoes.foto:
            piloto.tela.fotografar(opcoes.foto)
        return False
    GLib.timeout_add(8800, retratar)
    GLib.timeout_add(9500, Gtk.main_quit)
    Gtk.main()

    tela, tela2 = saida.get("tela"), saida.get("tela2")
    if not tela or not tela2:
        print(f"REPROVA: não consegui mexer nos campos no DOM vivo. "
              f"{saida.get('erro-tela', '')} {saida.get('erro-tela2', '')}")
        return 1
    tela = {**tela, **tela2}
    print(f"  a página            {onde.pagina(ABA, publicado=False)}")
    print(f"  o lar de mentira    {profiles_dir()}")
    print(f"  o desenho cravava   {tela['desenho']}")
    print(f"  a pintura escreveu  {tela['escreveu']} valor(es) -> {tela['pintado']}")
    print(f"  punho no DOM        {tela['punho']}")
    print(f"  apos o arrasto      {tela['apos_o_arrasto']}")
    print(f"  estilo no DOM       {tela['estilo']}")
    print(f"  a ponte ouviu       {dubie.chamadas}")

    if not tela["punho"].get("achou"):
        print("\nREPROVA: não há `[data-hef=\"editor.prioridade.escolha\"]` na "
              "página — o slider não chegou ao desenho.")
        return 1
    if tela["punho"].get("tag") != "INPUT":
        print(f"\nREPROVA: o endereço do punho não é um `<input>`, e sim "
              f"{tela['punho'].get('tag')!r} — barra não se arrasta.")
        return 1
    # A PINTURA TEM DE TER ESCRITO OS TRÊS. Zero é endereço que a página não
    # tem; menos que três é um dos três caindo no vazio.
    if int(tela["escreveu"] or 0) < 3:
        print(f"\nREPROVA: a pintura escreveu {tela['escreveu']} de 3 valores — "
              f"algum endereço da Prioridade não existe na página.")
        return 1
    if tela["pintado"]["punho"] != str(DE) or tela["pintado"]["barra"] != f"{PCT}%":
        print(f"\nREPROVA: o produto pintou {tela['pintado']!r}, e devia ser "
              f"punho={DE!r} · barra='{PCT}%'.")
        return 1
    faixa = (tela["punho"].get("min"), tela["punho"].get("max"))
    if faixa != ("0", str(PRIORIDADE_MAXIMA)):
        print(f"\nREPROVA: a faixa do slider é {faixa}, e o esquema diz "
              f"0..{PRIORIDADE_MAXIMA}.")
        return 1

    meio = saida.get("meio") or {}
    depois = _retrato()
    print("\n  o `.json` do perfil — nascimento · após o arrasto · após o estilo:")
    for chave in ("prioridade", "gatilho", "params", "vibracao", "cores"):
        print(f"    {chave:11s} {antes[chave]!r}\n"
              f"                -> {meio.get(chave)!r}\n"
              f"                -> {depois[chave]!r}")

    falhas = []
    if depois["prioridade"] != PARA:
        falhas.append(f"a prioridade não virou {PARA}: {depois['prioridade']}")
    if depois["gatilho"] == antes["gatilho"]:
        falhas.append(f"o gatilho não mudou: {depois['gatilho']}")
    if not depois["params"]:
        falhas.append("o gatilho foi gravado sem parâmetros — o firmware vê "
                      "zero zona ativa e o gatilho fica solto")
    if depois["vibracao"] == antes["vibracao"]:
        falhas.append(f"o degrau de vibração não mudou: {depois['vibracao']}")
    cores = depois["cores"]
    if len(cores) != len(MESA):
        falhas.append(f"a cor não alcançou os {len(MESA)} controles: {cores}")
    rgbs = [c[0] for c in cores.values()]
    if len(set(rgbs)) != len(rgbs):
        falhas.append(f"DUAS UNIDADES COM A MESMA COR — a regra dela caiu: {cores}")

    if falhas:
        print("\nREPROVA:")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"\nOK: o arrasto gravou a prioridade ({antes['prioridade']} -> "
          f"{depois['prioridade']}) e “{ESTILO}” gravou gatilho, vibração e "
          f"{len(cores)} cores distintas — tudo pelo clique, dentro do WebKit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
