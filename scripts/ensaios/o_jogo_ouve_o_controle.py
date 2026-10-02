#!/usr/bin/env python3
"""o_jogo_ouve_o_controle.py — o NOSSO comando e o JOGO, lado a lado, no mesmo tom."""

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

TOM_HZ = 1300.0
TOM_MS = 400
AMPLITUDE = 22000.0
TAXA = 48000

CANAIS_DO_NO = 2
CANAL_DO_ALTO_FALANTE = 1

SEGUNDOS_DO_MICROFONE = 3.0

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
    """O PCM s16le do tom, intercalado: o tom no `canal`, ZERO nos outros."""
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

    chave: str
    base: str
    pergunta: str
    nosso: str
    sala: str
    sentido: str


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
    transporte: str

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
        """O texto com os nomes de nó deste controle refeitos a partir da MÁSCARA."""
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
    fica_aberto: bool = False
    ouve_o_padrao: str = ""

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
    if p.nosso == "nivel" and not c.no_do_microfone:
        return Gesto(f"Abrir a Forja ({p.sala})", recusa="controle sem identidade legível")
    return Gesto(
        f"Abrir a Forja ({p.sala})",
        argv=[str(forja.godot), "--path", str(forja.raiz / "godot"), "--", f"--sala={p.sala}"],
        fica_aberto=True,
        ouve_o_padrao=c.no_do_microfone if p.nosso == "nivel" else "",
    )


def microfone_padrao() -> str:
    """O microfone PADRÃO do sistema agora — o que o jogo vai ouvir. Só lê."""
    if shutil.which("pactl") is None:
        return ""
    try:
        feito = subprocess.run(
            ["pactl", "get-default-source"], capture_output=True, text=True, timeout=5,
            check=False, env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return feito.stdout.strip() if feito.returncode == 0 else ""


def recusa_do_padrao(g: Gesto, padrao: str) -> str:
    """Por que o jogo NÃO ouviria este controle — ``""`` quando ouviria."""
    if not g.ouve_o_padrao:
        return ""
    if not padrao:
        return "não consegui perguntar qual é o microfone padrão: o jogo ouviria um que eu não sei"
    if padrao != g.ouve_o_padrao:
        return (
            "o jogo ouve o microfone PADRÃO, e o padrão agora é outro: escolha o deste "
            "controle como entrada nas configurações de Som e abra de novo"
        )
    return ""


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
    """A linha do caderno — e ela NÃO SAI sem gesto."""
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


def _pico_em_db(bruto: bytes) -> float:
    n = len(bruto) // 2
    if n == 0:
        return -80.0
    pico = max(abs(v) for v in struct.unpack(f"<{n}h", bruto[: n * 2]))
    return -80.0 if pico == 0 else max(20.0 * math.log10(pico / 32768.0), -80.0)


def executar(g: Gesto) -> tuple[str, bool]:
    """Roda o gesto: o que ela precisa ler na célula, e se ele RODOU."""
    if not g.argv:
        return g.recusa, False
    if shutil.which(g.argv[0]) is None and not os.access(g.argv[0], os.X_OK):
        return f"{g.argv[0]} não está nesta máquina", False
    recusa = recusa_do_padrao(g, microfone_padrao()) if g.ouve_o_padrao else ""
    if recusa:
        return recusa, False
    if g.fica_aberto:
        subprocess.Popen(g.argv, start_new_session=True)
        return "a Forja abriu — faça o gesto nela, e feche quando acabar", True
    if g.argv[0] == "parec":
        proc = subprocess.Popen(g.argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        time.sleep(SEGUNDOS_DO_MICROFONE)
        proc.terminate()
        bruto, _ = proc.communicate(timeout=5)
        return f"pico {_pico_em_db(bruto):.0f} dB em {SEGUNDOS_DO_MICROFONE:g} s", True
    feito = subprocess.run(
        g.argv, input=g.pcm or None, capture_output=True, timeout=15, check=False
    )
    saida = (feito.stdout + feito.stderr).decode("utf-8", "replace").strip().splitlines()
    return f"rc={feito.returncode} · " + (" / ".join(saida[-2:]) if saida else "sem saída"), True


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

        def _no_fio() -> None:
            try:
                texto, rodou = executar(g)
            except (OSError, subprocess.SubprocessError) as erro:
                texto, rodou = f"não rodou: {erro}", False
            GLib.idle_add(self._contar, p, c, g, rodou, recado, f"{g.rotulo}: {texto}")

        threading.Thread(target=_no_fio, daemon=True).start()

    def _contar(
        self, p: Pergunta, c: Controle, g: Gesto, rodou: bool, recado: Gtk.Label, texto: str
    ) -> bool:
        """No laço do GTK: o gesto que RODOU entra na conta da célula; o recado sempre."""
        if rodou:
            self.feitos.setdefault((p.chave, c.mac), []).append(g)
        recado.set_text(texto)
        return False

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
