#!/usr/bin/env python3
"""o_jogo_ouve_o_controle.py — o NOSSO comando e o JOGO, lado a lado, no mesmo tom.

A ENCOMENDA É DELA, 21/09/2026 (A-FORJA-VALIDA-O-SOM-01, E7):

    *"podermos validar em tempo real coisa que ainda não fizemos"* — e em
    23/09 ela corrigiu o que a Forja é: *"a forja é um jogo que temos
    desenvolvido (…) testarmos ao vivo esse feature pra cada controle."*
    <!-- noqa-acento: citação literal dela -->

A PERGUNTA QUE O MAPA NÃO TEM: o mapa sabe que o aparelho obedece ao NOSSO
comando (`O APARELHO OBEDECEU`) e não sabe se obedece a um JOGO — o degrau
«chegou ao JOGO» não existe para o som. Esta folha é a irmã de
`a_folha_do_som_por_controle.py`: uma COLUNA por controle, uma LINHA por
pergunta, e uma diferença que é a sprint inteira — **em cada célula, o nosso
comando e o do jogo, lado a lado, no mesmo tom.** Sem o positivo ao lado,
«não ouvi» não distingue *o jogo não alcança* de *o meu tom está mudo*.

O JOGO é a Forja (`Hefesto-Forja`, repositório dela): ele não sabe que o
Hefesto existe. Ele acha o alto-falante do controle PELO NOME que um jogo
mostra — sob Proton, a descrição do nó —, e é por isso que o nome dela ganhou
o nome da Sony atrás (a forma A, 23/09/2026).

AS QUATRO LINHAS, uma por chave `.jogo` do mapa
------------------------------------------------
=================================  ==========================  =============================
chave                              o nosso                     o jogo (a Forja)
=================================  ==========================  =============================
``audio.alto_falante.jogo``        o tom no nó do controle     o MESMO tom, achado pelo nome
``audio.microfone.jogo``           o nível do nó do controle   a Forja na sala Voz (F5)
``gatilho.direito.adaptativo.jogo`` o degrau do mapa            a Forja na Galeria (R2)
``vibracao.rumble.jogo``           o degrau do mapa            a Forja no Impacto (motores)
=================================  ==========================  =============================

Nas duas de baixo o positivo JÁ está medido (`O APARELHO OBEDECEU`, no mapa);
a folha o lê do dono em vez de mandar um gatilho pelo daemon, que gravaria no
perfil dela. As linhas do mapa em si entram pela `PARIDADE-NO-JOGO-BANCADA-01`,
que é dona do arquivo; esta folha propõe a linha do caderno, com data e gesto.

O QUE É DO PRODUTO, e o que é daqui
------------------------------------
Do PRODUTO: o nome do nó de som (`alto_falante_bt.nome_do_sink`), o do canal do
microfone (`canal_do_microfone.nome_do_canal`), a mesa
(`escrita_pelo_broker.alvos_da_mesa`, que só lê o sysfs) e a máscara.
Daqui: o tom (a MESMA conta do `forja_tom` da Forja — `tom_da_forja`), as
linhas, os gestos e a linha do caderno.

A MORDIDA, e ela está nos botões
---------------------------------
1. **o positivo** — o NOSSO tom. Se ela não ouvir aqui, a sessão para: o
   problema não é o jogo.
2. **o jogo** — o mesmo tom pela Forja. Ouviu no nosso e não no do jogo: o jogo
   não alcança. A Forja responde com `rc=2` quando NÃO ACHA o alto-falante — e
   isso é diferente de achar e ficar mudo.
3. **o gesto vai junto** — nenhuma linha de caderno sai sem a data e o comando
   que a produziu.

Porta: nenhuma. Escreve no aparelho? NÃO — o som vai pelo servidor de som, e o
gatilho e a vibração quem manda é a Forja. `--listar` e `--oculta` não rodam
comando nenhum.

USO
    o_jogo_ouve_o_controle.py --listar                # a mesa, as linhas, os comandos — só lê
    o_jogo_ouve_o_controle.py                         # na tela dela
    o_jogo_ouve_o_controle.py --forja ~/Hefesto-Forja # outra pasta da Forja
    o_jogo_ouve_o_controle.py --oculta                # sem tela, para régua
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
_SRC = os.path.join(_RAIZ, "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# O ESCAPE É DECLARADO (TELA-DELA-02): sem `--oculta` esta folha é DELA e nasce
# na tela dela — vê-la é o ponto inteiro. Com `--oculta` a guarda desvia para um
# Xvfb próprio, que é o que a régua usa.
if "--oculta" not in sys.argv:
    os.environ["HEFESTO_NA_TELA"] = "1"

from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from escrita_pelo_broker import alvos_da_mesa, linha_do_caderno, mascarar
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink
from hefesto_dualsense4unix.integrations.canal_do_microfone import nome_do_canal

#: O TOM — os MESMOS números do `forja-speak` (``src/forja_speak.c`` e
#: ``src/forja_alto_falante.c`` na Forja): 1300 Hz, 400 ms, amplitude 22000,
#: rampa de 10 ms nas duas pontas, a 48 kHz. Um tom por caminho seria uma
#: segunda variável escondida dentro do controle positivo.
TOM_HZ = 1300.0
TOM_MS = 400
AMPLITUDE = 22000.0
TAXA = 48000

#: O nó de som por controle tem DOIS canais, e o alto-falante do plástico come
#: o da direita (FR) — no cabo pela rota `front-left,front-right` do loopback,
#: no rádio pelo firmware (`CANAIS_DO_ENCODER`).
CANAIS_DO_NO = 2
CANAL_DO_ALTO_FALANTE = 1

#: Quanto dura a escuta do microfone. Três segundos é o que ela leva para
#: dizer uma frase sem pressa.
SEGUNDOS_DO_MICROFONE = 3.0

#: Onde a Forja mora, por padrão: ao lado desta árvore, como está na mesa dela.
FORJA_PADRAO = Path(_RAIZ).parent / "Hefesto-Forja"
GODOT_DA_FORJA = "tools/Godot_v4.4.1-stable_linux.x86_64"

MAPA = Path(_RAIZ) / "docs" / "data" / "mapa-controles.csv"
FONTE = "scripts/ensaios/o_jogo_ouve_o_controle.py"


def tom_da_forja(
    hz: float = TOM_HZ,
    ms: int = TOM_MS,
    canais: int = CANAIS_DO_NO,
    canal: int = CANAL_DO_ALTO_FALANTE,
) -> bytes:
    """O PCM s16le do tom, intercalado: o tom no `canal`, ZERO nos outros.

    A MESMA conta do `forja_tom` da Forja, linha a linha — o zero nos outros
    canais é o que transforma «ouvi» em «ouvi ALI».
    """
    quadros = TAXA * ms // 1000
    rampa = TAXA // 100
    amostras: list[int] = []
    for i in range(quadros):
        env = 1.0
        if i < rampa:
            env = i / rampa
        elif quadros - i < rampa:
            env = (quadros - i) / rampa
        v = int(env * AMPLITUDE * math.sin(2.0 * math.pi * hz * i / TAXA))
        amostras.extend(v if c == canal else 0 for c in range(canais))
    return struct.pack(f"<{len(amostras)}h", *amostras)


@dataclass(frozen=True)
class Pergunta:
    """Uma linha da folha: a chave `.jogo` do mapa e o que se aperta de cada lado."""

    chave: str  #: a chave nova do mapa, com `.jogo`
    base: str  #: a chave em que o NOSSO já está medido
    pergunta: str
    nosso: str  #: "tom" · "nivel" · "mapa"
    sala: str  #: a sala da Forja: "" (o forja-speak) · "voz" · "galeria" · "impacto"
    sentido: str  #: o que ela observa: "ouvi" · "vi" · "senti"


LINHAS: tuple[Pergunta, ...] = (
    Pergunta(
        "audio.alto_falante.jogo",
        "audio.alto_falante",
        "O som de um JOGO sai no plástico deste controle?",
        "tom",
        "",
        "ouvi",
    ),
    Pergunta(
        "audio.microfone.jogo",
        "audio.microfone",
        "O jogo ouve o microfone deste controle?",
        "nivel",
        "voz",
        "vi",
    ),
    Pergunta(
        "gatilho.direito.adaptativo.jogo",
        "gatilho.direito.adaptativo",
        "O gatilho que o JOGO pediu endurece neste controle?",
        "mapa",
        "galeria",
        "senti",
    ),
    Pergunta(
        "vibracao.rumble.jogo",
        "vibracao.rumble.ff",
        "O motor que o JOGO pediu treme, e só neste controle?",
        "mapa",
        "impacto",
        "senti",
    ),
)


@dataclass(frozen=True)
class Controle:
    """Um controle da mesa. O endereço cru nunca sai daqui — só o mascarado."""

    mac: str
    transporte: str  #: "cabo" · "radio", como o mapa escreve

    @property
    def mascarado(self) -> str:
        return mascarar(self.mac)

    @property
    def no_de_som(self) -> str:
        return nome_do_sink(self.mac)

    @property
    def no_do_microfone(self) -> str:
        return nome_do_canal(self.mac)

    def mascarar_no_texto(self, texto: str) -> str:
        """O texto com os nomes de nó deste controle refeitos a partir da MÁSCARA.

        O nome do nó leva o rabo do endereço (``hefesto_som_<hex6>``), e dois
        daqueles seis dígitos são os octetos que a máscara da casa zera. O que
        vai para a tela e para o caderno sai mascarado; o comando que RODA usa
        o nome de verdade.
        """
        for real, falso in (
            (self.no_de_som, nome_do_sink(self.mascarado)),
            (self.no_do_microfone, nome_do_canal(self.mascarado)),
        ):
            if real:
                texto = texto.replace(real, falso)
        return texto


@dataclass(frozen=True)
class Forja:
    """Onde o jogo mora. Não a encontrar é RESPOSTA, dita na célula."""

    raiz: Path

    @property
    def speak(self) -> Path:
        return self.raiz / "bin" / "forja-speak"

    @property
    def godot(self) -> Path:
        de_fora = os.environ.get("GODOT", "")
        return Path(de_fora) if de_fora else self.raiz / GODOT_DA_FORJA

    def falta_para(self, sala: str) -> str:
        """A frase de por que o jogo não sobe — ``""`` quando nada falta."""
        if not self.raiz.is_dir():
            return f"a Forja não está em {self.raiz}: use --forja <pasta>"
        if not sala and not os.access(self.speak, os.X_OK):
            return f"o forja-speak não foi compilado: rode make em {self.raiz}"
        if sala and not os.access(self.godot, os.X_OK):
            if os.environ.get("GODOT"):
                return f"o GODOT={self.godot} não roda"
            return f"o Godot da Forja não foi baixado: rode ./run-local.sh uma vez em {self.raiz}"
        return ""


@dataclass
class Gesto:
    """O que um botão faz — ou a frase de por que ele não faz nada."""

    rotulo: str
    argv: list[str] = field(default_factory=list)
    pcm: bytes = b""
    recusa: str = ""
    fica_aberto: bool = False  #: a janela do jogo, que ela fecha quando acabar

    @property
    def texto(self) -> str:
        """O gesto por escrito, como vai para o caderno."""
        return " ".join(self.argv) if self.argv else self.recusa


def gesto_nosso(p: Pergunta, c: Controle) -> Gesto:
    """O NOSSO lado da célula: o positivo, que diz se o tom está vivo."""
    if p.nosso == "tom":
        if not c.no_de_som:
            return Gesto("Tocar o nosso tom", recusa="controle sem identidade legível")
        return Gesto(
            "Tocar o nosso tom",
            argv=[
                "pw-cat", "--playback", "--raw", f"--target={c.no_de_som}",
                f"--rate={TAXA}", f"--channels={CANAIS_DO_NO}", "--format=s16",
                "--channel-map=FL,FR", "--latency=40ms", "-",
            ],
            pcm=tom_da_forja(),
        )
    if p.nosso == "nivel":
        if not c.no_do_microfone:
            return Gesto("Medir o nosso nível", recusa="controle sem identidade legível")
        # A latência vai EXPLÍCITA: sem ela o `parec` entrega dois segundos
        # depois, e a barra respondia à frase de antes (memória da casa).
        return Gesto(
            "Medir o nosso nível",
            argv=[
                "parec", f"--device={c.no_do_microfone}", "--raw", "--format=s16le",
                "--channels=1", f"--rate={TAXA}", "--latency-msec=20",
            ],
        )
    return Gesto("o degrau do mapa", recusa=degrau_do_mapa(p.base, c.transporte))


def gesto_do_jogo(p: Pergunta, c: Controle, forja: Forja) -> Gesto:
    """O lado do JOGO: a Forja, que não sabe que o Hefesto existe."""
    falta = forja.falta_para(p.sala)
    if not p.sala:
        if falta:
            return Gesto("Tocar pelo jogo", recusa=falta)
        # PELO NOME: o jogo acha o alto-falante como a pessoa o aponta na lista
        # dele. O `--nome` casa o nome do nó ou o que o jogo mostra; quem decide
        # se ele é um alto-falante de DualSense é a Forja, pela palavra da Sony.
        return Gesto(
            "Tocar pelo jogo",
            argv=[
                str(forja.speak), "--nome", c.no_de_som,
                "--hz", f"{TOM_HZ:g}", "--ms", str(TOM_MS),
            ],
        )
    if falta:
        return Gesto(f"Abrir a Forja ({p.sala})", recusa=falta)
    return Gesto(
        f"Abrir a Forja ({p.sala})",
        argv=[str(forja.godot), "--path", str(forja.raiz / "godot"), "--", f"--sala={p.sala}"],
        fica_aberto=True,
    )


def degrau_do_mapa(chave: str, transporte: str) -> str:
    """O degrau que o mapa já tem para a chave base, NO transporte — lido do dono."""
    lado = "radio" if transporte == "radio" else "cabo"
    try:
        with MAPA.open(encoding="utf-8") as f:
            for linha in csv.DictReader(f):
                if linha.get("chave") == chave and linha.get("controle") == "dualsense":
                    degrau = (linha.get(f"{lado}_ate_onde_foi") or "").strip()
                    quando = (linha.get("provado_em") or "").strip()
                    if not degrau:
                        return f"o mapa ainda não mediu {chave} no {lado}"
                    return f"o mapa: {degrau}" + (f" ({quando})" if quando else "")
    except OSError:
        return "o mapa não se deixou ler"
    return f"o mapa não tem {chave}"


def linha_para_o_caderno(
    p: Pergunta, c: Controle, resultado: str, feitos: Sequence[Gesto], nota: str = ""
) -> str:
    """A linha do caderno — e ela NÃO SAI sem gesto.

    Um veredito sem a data e sem o comando que o produziu é opinião, e é o que
    o degrau `.jogo` do mapa não pode virar (a mordida do E7). ``""`` quando
    nada foi feito ainda.
    """
    gestos = [c.mascarar_no_texto(g.texto) for g in feitos if g.argv]
    if not gestos:
        return ""
    return linha_do_caderno(
        id=f"jogo-{p.chave}-{c.transporte}-{time.strftime('%d%m')}",
        linha_id=f"{p.chave}@dualsense",
        transporte=c.transporte,
        suspeito=p.pergunta,
        presente="sim",
        resultado=resultado,
        observado_por={"ouvi": "orelha-dela", "vi": "olho-dela"}.get(p.sentido, "mão-dela"),
        fonte=FONTE,
        nota=f"controle {c.mascarado}; " + " ; ".join(gestos) + (f" ; ela: {nota}" if nota else ""),
    )


def mesa() -> list[Controle]:
    """Os DualSense FÍSICOS da mesa, pelo sysfs. Só lê."""
    return [Controle(a.mac, a.transporte) for a in alvos_da_mesa() if a.mac]


def listar(controles: Sequence[Controle], forja: Forja) -> str:
    """A folha por escrito: cada linha, cada controle, e os dois comandos."""
    linhas = [f"a Forja: {forja.raiz}"]
    if not controles:
        linhas.append("nenhum DualSense físico na mesa")
    for p in LINHAS:
        linhas.append(f"\n{p.chave} — {p.pergunta}")
        for c in controles:
            nosso, jogo = gesto_nosso(p, c), gesto_do_jogo(p, c, forja)
            linhas.append(f"  {c.mascarado} ({c.transporte})")
            linhas.append(f"    nosso: {c.mascarar_no_texto(nosso.texto)}")
            linhas.append(f"    jogo:  {c.mascarar_no_texto(jogo.texto)}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# A FOLHA NA TELA
# ---------------------------------------------------------------------------


def _pico_em_db(bruto: bytes) -> float:
    n = len(bruto) // 2
    if n == 0:
        return -80.0
    pico = max(abs(v) for v in struct.unpack(f"<{n}h", bruto[: n * 2]))
    return -80.0 if pico == 0 else max(20.0 * math.log10(pico / 32768.0), -80.0)


def executar(g: Gesto) -> str:
    """Roda o gesto e devolve o que ela precisa ler na célula."""
    if not g.argv:
        return g.recusa
    if shutil.which(g.argv[0]) is None and not os.access(g.argv[0], os.X_OK):
        return f"{g.argv[0]} não está nesta máquina"
    if g.fica_aberto:
        subprocess.Popen(g.argv, start_new_session=True)
        return "a Forja abriu — faça o gesto nela, e feche quando acabar"
    if g.argv[0] == "parec":
        proc = subprocess.Popen(g.argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        time.sleep(SEGUNDOS_DO_MICROFONE)
        proc.terminate()  # o processo que ESTE gesto abriu, pelo objeto — nunca por nome
        bruto, _ = proc.communicate(timeout=5)
        return f"pico {_pico_em_db(bruto):.0f} dB em {SEGUNDOS_DO_MICROFONE:g} s"
    feito = subprocess.run(
        g.argv, input=g.pcm or None, capture_output=True, timeout=15, check=False
    )
    saida = (feito.stdout + feito.stderr).decode("utf-8", "replace").strip().splitlines()
    return f"rc={feito.returncode} · " + (" / ".join(saida[-2:]) if saida else "sem saída")


class Folha:
    """Uma coluna por controle, uma linha por pergunta, dois lados por célula."""

    def __init__(self, controles: Sequence[Controle], forja: Forja) -> None:
        self.controles = list(controles)
        self.forja = forja
        self.feitos: dict[tuple[str, str], list[Gesto]] = {}
        self.recados: dict[tuple[str, str], Gtk.Label] = {}
        self.janela = Gtk.Window(title="O jogo ouve o controle — o nosso e o jogo, lado a lado")
        self.janela.set_default_size(1100, 760)
        self.janela.connect("destroy", self._fechar)
        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        corpo.set_border_width(14)
        topo = Gtk.Label(xalign=0)
        topo.set_markup(
            "<b>Aperte o NOSSO primeiro.</b> Se ele não sair, a sessão para: "
            "o problema não é o jogo.\n"
            f"O jogo é a Forja ({GLib.markup_escape_text(str(forja.raiz))}), "
            "que não sabe que o Hefesto existe."
        )
        corpo.pack_start(topo, False, False, 0)
        if not self.controles:
            vazio = Gtk.Label(label="nenhum DualSense físico na mesa", xalign=0)
            corpo.pack_start(vazio, False, False, 0)
        for p in LINHAS:
            corpo.pack_start(self._secao(p), False, False, 0)
        rolagem.add(corpo)
        self.janela.add(rolagem)

    def _secao(self, p: Pergunta) -> Gtk.Widget:
        moldura = Gtk.Frame()
        dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dentro.set_border_width(10)
        titulo = Gtk.Label(xalign=0)
        titulo.set_markup(f"<b>{GLib.markup_escape_text(p.pergunta)}</b>  <tt>{p.chave}</tt>")
        dentro.pack_start(titulo, False, False, 0)
        colunas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        for c in self.controles:
            colunas.pack_start(self._celula(p, c), True, True, 0)
        dentro.pack_start(colunas, False, False, 0)
        moldura.add(dentro)
        return moldura

    def _celula(self, p: Pergunta, c: Controle) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cabeca = Gtk.Label(label=f"{c.mascarado} · {c.transporte}", xalign=0)
        caixa.pack_start(cabeca, False, False, 0)
        recado = Gtk.Label(xalign=0)
        recado.set_line_wrap(True)
        self.recados[(p.chave, c.mac)] = recado
        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for gesto in (gesto_nosso(p, c), gesto_do_jogo(p, c, self.forja)):
            if gesto.argv:
                botao = Gtk.Button(label=gesto.rotulo)
                botao.connect("clicked", self._apertar, p, c, gesto)
                fileira.pack_start(botao, False, False, 0)
            else:
                aviso = Gtk.Label(label=gesto.recusa, xalign=0)
                aviso.set_line_wrap(True)
                fileira.pack_start(aviso, False, False, 0)
        caixa.pack_start(fileira, False, False, 0)
        caixa.pack_start(recado, False, False, 0)
        veredito = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        vereditos = (
            (f"{p.sentido.capitalize()} no jogo", "obedece"),
            ("Nada no jogo", "não obedece"),
            ("Não sei", "inconclusivo"),
        )
        for rotulo, resultado in vereditos:
            b = Gtk.Button(label=rotulo)
            b.connect("clicked", self._gravar, p, c, resultado)
            veredito.pack_start(b, False, False, 0)
        caixa.pack_start(veredito, False, False, 0)
        return caixa

    def _apertar(self, _b: Gtk.Button, p: Pergunta, c: Controle, g: Gesto) -> None:
        recado = self.recados[(p.chave, c.mac)]
        recado.set_text(f"{g.rotulo}…")
        self.feitos.setdefault((p.chave, c.mac), []).append(g)

        def _no_fio() -> None:
            try:
                texto = executar(g)
            except (OSError, subprocess.SubprocessError) as erro:
                texto = f"não rodou: {erro}"
            GLib.idle_add(recado.set_text, f"{g.rotulo}: {texto}")

        threading.Thread(target=_no_fio, daemon=True).start()

    def _gravar(self, _b: Gtk.Button, p: Pergunta, c: Controle, resultado: str) -> None:
        linha = linha_para_o_caderno(p, c, resultado, self.feitos.get((p.chave, c.mac), []))
        recado = self.recados[(p.chave, c.mac)]
        if not linha:
            recado.set_text("aperte os dois lados antes: veredito sem gesto não vira linha")
            return
        print(linha, flush=True)
        recado.set_text(f"gravado: {resultado}")

    def _fechar(self, *_: object) -> None:
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def abrir(self) -> None:
        self.janela.show_all()
        Gtk.main()


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--listar", action="store_true", help="a mesa, as linhas e os comandos; só lê")
    ap.add_argument("--oculta", action="store_true", help="monta a folha sem tela e sai")
    ap.add_argument("--forja", type=Path, default=FORJA_PADRAO, help="a pasta da Forja")
    args = ap.parse_args(argv)
    forja = Forja(args.forja.expanduser())
    controles = mesa()
    if args.listar:
        print(listar(controles, forja))
        return 0
    folha = Folha(controles, forja)
    if args.oculta:
        print(listar(controles, forja))
        folha.janela.destroy()
        return 0
    folha.abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
