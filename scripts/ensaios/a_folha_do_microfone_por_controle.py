#!/usr/bin/env python3
"""a_folha_do_microfone_por_controle.py — o microfone de cada controle, nos dois transportes, com o pico ao vivo.
"""

from __future__ import annotations

import array
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

BANDEIRAS_SEM_TELA = ("--oculta", "--listar")

_E_O_PROGRAMA = os.path.basename(sys.argv[0] or "") == os.path.basename(__file__)
if _E_O_PROGRAMA and not any(b in sys.argv for b in BANDEIRAS_SEM_TELA):
    os.environ["HEFESTO_NA_TELA"] = "1"

from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gtk

import hefesto_dualsense4unix.core.ds_output_report as rep

from hefesto_dualsense4unix.integrations.audio_control import fonte_de_captura_do_uniq
from hefesto_dualsense4unix.integrations.canal_do_microfone import nome_do_canal
from comum import CABO, RADIO, cabecalho_do_instrumento, pintar_fundo_solido, resumo
from escrita_pelo_broker import (
    Escritor,
    alvos_da_mesa,
    common_vazio,
    linha_do_caderno,
    mascarar,
)
from microfone_no_cabo import placas_de_dualsense
from os_nos_de_som_por_controle import blocos_longos, pactl

HZ = 10.0

RELER_A_LISTA_S = 2.0

LEITOR_DO_PICO = "parec"

LATENCIA_DO_PICO_MS = 40

TAXA_DO_PICO = 48000
PEDACO_DO_PICO = 4096

QUEDA_DA_BARRA = 0.18

VOLUME_DA_FONTE_INICIAL = 100

COALESCE_DO_DESLIZANTE_MS = 250


def _agora_ddmm() -> str:
    return time.strftime("%d%m")


def common_do_byte(valor: int, *, com_bit: bool = True) -> bytearray:
    """Um `common` de 47 bytes com o volume do microfone, e nada mais."""
    if not 0 <= valor <= rep.TETO_MIC_VOLUME:
        raise ValueError(f"volume do mic fora de 0..{rep.TETO_MIC_VOLUME:#x}: {valor:#x}")
    c = common_vazio()
    c[rep.COMMON_MIC_VOLUME] = valor
    if com_bit:
        c[0] |= rep.VALID_FLAG0_MIC_VOLUME
    return c


def no_do_canal(uniq: str) -> str:
    """`hefesto_mic_<marca>` deste controle — "" se ele não tem identidade."""
    try:
        return nome_do_canal(uniq) or ""
    except Exception:
        return ""


def fonte_do_produto(uniq: str) -> str:
    """O que o PRODUTO responde a *"qual é o microfone deste controle"*."""
    try:
        return fonte_de_captura_do_uniq(uniq) or ""
    except Exception:
        return ""


@dataclass
class LeituraDoSistema:
    """O que a lista VIVA publica para um controle, num instante."""

    canal: str = ""
    descricao: str = ""
    estado: str = ""
    placa_usb: str = ""
    do_produto: str = ""

    @property
    def publica(self) -> bool:
        """O sistema publica ALGUMA entrada para este controle?"""
        return bool(self.canal or self.placa_usb)

    @property
    def escolhida(self) -> str:
        """Onde o pico escuta: o que o produto resolve, e o endereço como rede."""
        return self.do_produto or self.canal or self.placa_usb

    def frase(self) -> str:
        if not self.publica:
            return "NÃO EXISTE — o sistema não publica entrada nenhuma para este controle"
        partes = []
        if self.canal:
            rotulo = self.descricao or "(sem descrição)"
            partes.append(f"canal «{rotulo}» ({self.canal}, {self.estado or 'estado ?'})")
        if self.placa_usb:
            partes.append("placa USB do cabo")
        partes.append(f"o produto responde: {self.do_produto or 'None'}")
        return " · ".join(partes)


def ler_o_sistema(alvos: list[Any]) -> dict[str, LeituraDoSistema]:
    """A lista viva, por `uniq`. Roda FORA da linha do GTK — ver `RELER_A_LISTA_S`."""
    fontes = blocos_longos(pactl("list", "sources"))
    por_nome = {f.get("Name", ""): f for f in fontes if f.get("Name")}
    placas = {p.dono.hidraw: p for p in placas_de_dualsense(alvos) if p.dono is not None}
    leituras: dict[str, LeituraDoSistema] = {}
    for a in alvos:
        leitura = LeituraDoSistema()
        canal = no_do_canal(a.mac)
        if canal and canal in por_nome:
            leitura.canal = canal
            leitura.descricao = por_nome[canal].get("Description", "")
            leitura.estado = por_nome[canal].get("State", "")
        placa = placas.get(a.hidraw)
        if placa is not None:
            for nome, bloco in por_nome.items():
                if nome.startswith("alsa_input") and bloco.get("alsa.card") == placa.numero:
                    leitura.placa_usb = nome
                    if not leitura.canal:
                        leitura.descricao = bloco.get("Description", "")
                        leitura.estado = bloco.get("State", "")
                    break
        leitura.do_produto = fonte_do_produto(a.mac)
        leituras[a.mac] = leitura
    return leituras


def pico_do_pedaco(pedaco: bytes) -> float:
    """O pico de um pedaço de s16 little-endian, em 0..1 — e A AMOSTRA MORRE AQUI."""
    if not pedaco:
        return 0.0
    amostras = array.array("h")
    amostras.frombytes(pedaco[: len(pedaco) // 2 * 2])
    if not amostras:
        return 0.0
    return max(abs(min(amostras)), abs(max(amostras))) / 32768.0


class OuvidoDoPico:
    """Lê o nível de uma fonte e DESCARTA a amostra. Nada vai para disco."""

    def __init__(self, fonte: str) -> None:
        self.fonte = fonte
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self._ultimo = 0.0
        self.maximo = 0.0
        self.pedacos = 0
        self.erro = ""

    @staticmethod
    def argv(fonte: str) -> list[str]:
        """O comando do leitor. Sem caminho de saída: o destino é o `stdout`."""
        return [
            LEITOR_DO_PICO,
            f"--device={fonte}",
            f"--rate={TAXA_DO_PICO}",
            "--channels=1",
            "--format=s16le",
            f"--latency-msec={LATENCIA_DO_PICO_MS}",
        ]

    def abrir(self) -> str | None:
        """Liga o ouvido. Devolve o MOTIVO quando não dá — nunca fica mudo."""
        if self._proc is not None:
            return None
        if not self.fonte:
            return "este controle não publica entrada nenhuma — peça o canal primeiro"
        if not shutil.which(LEITOR_DO_PICO):
            return f"não há `{LEITOR_DO_PICO}` nesta máquina, e é ele que lê o nível"
        try:
            self._proc = subprocess.Popen(
                self.argv(self.fonte),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as erro:
            self._proc = None
            return str(erro)
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="pico", daemon=True)
        self._thread.start()
        return None

    def _laco(self) -> None:
        saida = self._proc.stdout if self._proc is not None else None
        if saida is None:
            return
        while not self._parar.is_set():
            pedaco = saida.read(PEDACO_DO_PICO)
            if not pedaco:
                break
            nivel = pico_do_pedaco(pedaco)
            with self._trava:
                self._ultimo = nivel
                self.maximo = max(self.maximo, nivel)
                self.pedacos += 1

    def tomar(self) -> float:
        """O nível do último pedaço, e ele se ZERA na leitura."""
        with self._trava:
            valor, self._ultimo = self._ultimo, 0.0
            return valor

    def zerar_o_maximo(self) -> None:
        with self._trava:
            self.maximo = 0.0

    @property
    def ligado(self) -> bool:
        return self._proc is not None

    def fechar(self) -> None:
        """Termina PELO OBJETO do processo — nunca por padrão de linha de comando."""
        self._parar.set()
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()
        self._thread = None


@dataclass(frozen=True)
class Linha:
    """Uma linha da folha: o que ela pergunta e com que forma ela pergunta."""

    id: str
    titulo: str
    forma: str
    pergunta: str
    sprint: str
    linha_do_mapa: str
    olhar: str = ""


LINHAS: tuple[Linha, ...] = (
    Linha(
        id="o-no-existe",
        titulo="1 · O nó existe?",
        forma="leitura",
        pergunta="o que o SISTEMA publica para este controle, agora — relido a cada volta",
        olhar="O nome que ela vê na lista de som. «NÃO EXISTE» aqui é a metade "
        "de cima da pergunta 3.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
    Linha(
        id="pedir-o-canal",
        titulo="2 · Pedir o canal",
        forma="pedido",
        pergunta="a ponte sobe sob demanda: com o pedido, o nó nasce? sem ele, some?",
        olhar="Aperte e olhe a linha 1. É o mesmo ato do 🎙 da tela "
        "(`mic.canal.set`), e ele mexe no mudo do firmware.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
    Linha(
        id="o-pico-ao-vivo",
        titulo="3 · O pico da captura, ao vivo",
        forma="pico",
        pergunta="o nó CAPTA? — fale «aaaa» e a barra sobe, ou não sobe",
        olhar="A barra. E o «máx», que é quem decide: o ouvido não guarda o "
        "patamar anterior. Nada é gravado.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
    Linha(
        id="o-byte-do-aparelho",
        titulo="4 · O byte do aparelho (common[6], 0 a 0x40)",
        forma="byte",
        pergunta="o byte do aparelho muda a captura, ou quem manda é só a fonte do sistema?",
        olhar="Arraste ENQUANTO fala e olhe o «máx» de cada parada. Com a chave "
        "«Assumir» desligada, este é o negativo: sem o bit, nada deve mudar.",
        sprint="MIC-VOLUME-02",
        linha_do_mapa="audio.microfone.volume@dualsense",
    ),
    Linha(
        id="o-campo-da-tela",
        titulo="5 · O campo que a tela oferece (a FONTE, 0-100 %)",
        forma="campo",
        pergunta="o ganho da fonte no PipeWire — a outra coisa, e ela mexe mesmo",
        olhar="É o deslizante do card na aba Controles. Compare com a linha 4: "
        "se só este move o pico, o byte não ganha campo.",
        sprint="MIC-VOLUME-02",
        linha_do_mapa="audio.microfone.volume@dualsense",
    ),
    Linha(
        id="o-daemon-responde",
        titulo="6 · O que o daemon responde",
        forma="resposta",
        pergunta="o daemon diz `sem_fonte` sobre um controle que TEM nó publicado?",
        olhar="Compare com a linha 1. Discordância aqui é a tarja da aba "
        "Controles, com a causa à mostra.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
)


def linha_de(id_: str) -> Linha:
    """A linha pelo `id`. Indexar `LINHAS` por posição quebra ao inserir uma linha."""
    for linha in LINHAS:
        if linha.id == id_:
            return linha
    raise KeyError(f"não há linha {id_!r} nesta folha")


def veredito_da_tarja(
    leitura: LeituraDoSistema, corpo: dict[str, Any] | None, *, perguntou: bool
) -> str:
    """A frase que põe o SISTEMA e o DAEMON lado a lado. Ela não conclui a sprint."""
    if not perguntou:
        return (
            "ninguém perguntou ainda — aperte «Perguntar ao daemon», ou mexa no "
            "deslizante da linha 5"
        )
    if corpo is None:
        return "o daemon não respondeu — ou o Hefesto está parado, ou o socket não abriu"
    status = str(corpo.get("status") or "")
    fonte = str(corpo.get("fonte") or "")
    if status == "sem_fonte" and leitura.publica:
        return (
            "OS DOIS DISCORDAM: o sistema publica entrada para este controle e o "
            "daemon respondeu «sem_fonte» — é a tarja da aba Controles, e a causa "
            "está aqui"
        )
    if status == "sem_fonte":
        return (
            "concordam: ninguém publica entrada para este controle e o daemon diz "
            "«sem_fonte» — falta o canal, não a frase"
        )
    if fonte and leitura.escolhida and fonte != leitura.escolhida:
        return (
            f"O DAEMON MEXEU EM OUTRO NÓ: ele atendeu em «{fonte}» e o nó deste "
            f"controle é «{leitura.escolhida}»"
        )
    if status == "ok":
        return f"concordam: o daemon atendeu em «{fonte or '?'}»"
    return f"o daemon respondeu «{status or '?'}» — nem ok nem sem_fonte"


def frase_da_resposta_do_daemon(
    leitura: LeituraDoSistema, corpo: dict[str, Any] | None, *, perguntou: bool
) -> str:
    """A linha 6 inteira: a resposta CRUA e, embaixo, o veredito da tarja."""
    veredito = veredito_da_tarja(leitura, corpo, perguntou=perguntou)
    if not perguntou:
        return veredito
    return f"CRU: {corpo}\n{veredito}"


@dataclass
class ControleNaFolha:
    """Uma coluna: o aparelho, o `common` vivo, a porta, o ouvido e as respostas."""

    alvo: Any
    common: bytearray = field(default_factory=common_vazio)
    assumido: bool = False
    escritas: int = 0
    erro: str = ""
    escritor: Escritor | None = None
    ouvido: OuvidoDoPico | None = None
    barra: float = 0.0
    leitura: LeituraDoSistema = field(default_factory=LeituraDoSistema)
    resposta_do_canal: dict[str, Any] | None = None
    resposta_do_volume: dict[str, Any] | None = None
    perguntou_ao_daemon: bool = False
    canal_pedido: bool = False
    volume_da_fonte: int = VOLUME_DA_FONTE_INICIAL

    @property
    def nome(self) -> str:
        return ("CABO" if self.alvo.transporte == CABO else "RÁDIO") + " · " + mascarar(
            self.alvo.mac
        )

    @property
    def curto(self) -> str:
        return "cabo" if self.alvo.transporte == CABO else "radio"

    @property
    def papel(self) -> str:
        """O cabo é o CONTROLE POSITIVO, e a folha diz isso na coluna dele."""
        if self.alvo.transporte == CABO:
            return "CONTROLE POSITIVO — o som pelo cabo funciona (placa USB própria)"
        return "o que se mede CONTRA o positivo do lado"

    def _garantir_porta(self) -> bool:
        """Abre o hidraw no primeiro «Assumir». Antes disso, nada é escrito."""
        if self.escritor is not None:
            return not self.erro
        self.escritor = Escritor(self.alvo)
        try:
            self.escritor.abrir()
        except Exception as erro:
            self.erro = str(erro)
            return False
        self.erro = ""
        return True

    def assumir(self, ligado: bool) -> None:
        """Liga o bit `0x40` do `valid_flag0` — a posse, por controle e por ensaio."""
        if ligado and not self._garantir_porta():
            self.assumido = False
            return
        self.assumido = ligado
        if ligado:
            self.common[0] |= rep.VALID_FLAG0_MIC_VOLUME
        else:
            self.common[0] &= ~rep.VALID_FLAG0_MIC_VOLUME & 0xFF

    def escrever_byte(self, valor: int) -> None:
        self.common[rep.COMMON_MIC_VOLUME] = valor & 0xFF

    @property
    def byte(self) -> int:
        return self.common[rep.COMMON_MIC_VOLUME]

    def bater(self) -> None:
        """O martelo. Só bate o que ela assumiu — e só se a porta abriu."""
        if not self.assumido or self.escritor is None or self.erro:
            return
        try:
            self.escritor.escrever(self.common)
            self.escritas += 1
        except Exception as erro:
            self.erro = str(erro)

    def devolver(self) -> None:
        """Devolve o byte ao daemon. Só escreve se a porta chegou a abrir."""
        self.common = common_vazio()
        self.assumido = False
        if self.escritor is not None and not self.erro:
            try:
                self.escritor.escrever(self.common)
            except Exception as erro:
                self.erro = str(erro)

    def fechar(self) -> None:
        if self.ouvido is not None:
            self.ouvido.fechar()
            self.ouvido = None
        self.devolver()
        if self.escritor is not None:
            self.escritor.fechar()
            self.escritor = None

    def pedir_o_canal(self, ligado: bool) -> dict[str, Any] | None:
        """`mic.canal.set` — o mesmo ato do 🎙 da tela. Bloqueia: chame no fundo."""
        from hefesto_dualsense4unix.app import ipc_bridge

        corpo = ipc_bridge.mic_canal_set_detalhado(ligado, uniq=self.alvo.mac)
        self.resposta_do_canal = corpo
        self.canal_pedido = ligado and bool(corpo) and corpo.get("status") in ("ok", "incompleto")
        return corpo

    def mandar_o_volume(self, por_cento: int) -> dict[str, Any] | None:
        """`mic.volume.set` — o campo da tela. Bloqueia: chame no fundo."""
        from hefesto_dualsense4unix.app import ipc_bridge

        self.volume_da_fonte = por_cento
        corpo = ipc_bridge.mic_volume_set_detalhado(por_cento, uniq=self.alvo.mac)
        self.resposta_do_volume = corpo
        self.perguntou_ao_daemon = True
        return corpo

    def ouvir(self) -> str | None:
        if self.ouvido is not None and self.ouvido.ligado:
            self.ouvido.fechar()
            self.ouvido = None
            return None
        self.ouvido = OuvidoDoPico(self.leitura.escolhida)
        motivo = self.ouvido.abrir()
        if motivo:
            self.ouvido = None
        return motivo


def frase_da_mesa(alvos: list[Any]) -> str:
    """A mesa que esta folha ENCONTROU — e o que falta, com todas as letras."""
    cabos = sum(1 for a in alvos if a.transporte == CABO)
    radios = sum(1 for a in alvos if a.transporte == RADIO)
    if cabos and radios:
        return f"a mesa tem o par: {cabos} no cabo e {radios} no rádio."

    def conta(n: int, onde: str) -> str:
        if n == 0:
            return f"nenhum no {onde}"
        return f"{'um' if n == 1 else n} no {onde}"

    achei = " e ".join(x for x in (conta(cabos, "cabo"), conta(radios, "rádio")) if x)
    return (
        "FALTA O PAR: preciso de um no cabo e um no rádio; achei "
        + achei
        + ". Sem o positivo do cabo ao lado, silêncio no rádio não distingue "
        "«o aparelho não aceita» de «o meu tom está mudo»."
    )


class Folha:
    _BOTOES: ClassVar[dict[str, tuple[str, str]]] = {
        "pedido": ("Pedir o canal", "Soltar o canal"),
        "pico": ("Ouvir o pico", "Parar de ouvir"),
    }

    def __init__(self, controles: list[ControleNaFolha], *, enxuta: bool = False) -> None:
        self.controles = controles
        self.enxuta = enxuta
        self._relendo = False
        self.notas: dict[tuple[str, str], Gtk.Entry] = {}
        self.recados: dict[tuple[str, str], Gtk.Label] = {}
        self.barras: list[tuple[Gtk.DrawingArea, ControleNaFolha]] = []
        self.contadores: list[tuple[ControleNaFolha, Gtk.Label]] = []
        self.chaves: dict[str, Gtk.Switch] = {}

        self.janela = Gtk.Window(
            title="Ajustes do microfone" if enxuta else "O microfone de cada controle"
        )
        self.janela.set_default_size(960, 720 if enxuta else 820)
        self.janela.connect("destroy", self._fechar)
        self._fundo_opaco()

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.janela.add(raiz)
        raiz.pack_start(self._topo(), False, False, 0)

        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        corpo.set_margin_top(10)
        corpo.set_margin_bottom(16)
        corpo.set_margin_start(14)
        corpo.set_margin_end(14)
        for linha in LINHAS:
            corpo.pack_start(self._secao(linha), False, False, 0)
        rolagem.add(corpo)
        raiz.pack_start(rolagem, True, True, 0)

        GLib.timeout_add(int(1000 / HZ), self._tique)
        GLib.timeout_add(int(RELER_A_LISTA_S * 1000), self._reler_a_lista)

    def _fundo_opaco(self) -> None:
        """Fundo SÓLIDO. A razão é do usuário: *"o fundo tá muito transparente"*."""
        # do próprio botão. *"nao deu pra ler nada nos botoes"*.  # (noqa-acento: citação literal)
        pintar_fundo_solido(self.janela)

    def _topo(self) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.set_margin_top(10)
        caixa.set_margin_start(14)
        caixa.set_margin_end(14)

        quem = Gtk.Label()
        quem.set_markup("<b>" + "</b>   ·   <b>".join(c.nome for c in self.controles) + "</b>")
        quem.set_xalign(0.0)
        caixa.pack_start(quem, False, False, 0)

        texto_da_mesa = frase_da_mesa([c.alvo for c in self.controles])
        mesa = Gtk.Label()
        mesa.set_xalign(0.0)
        mesa.set_line_wrap(True)
        if texto_da_mesa.startswith("FALTA O PAR"):
            mesa.set_markup(
                f"<span foreground='#e5a50a'>{GLib.markup_escape_text(texto_da_mesa)}</span>"
            )
        else:
            mesa.set_text(texto_da_mesa)
            mesa.get_style_context().add_class("dim-label")
        caixa.pack_start(mesa, False, False, 0)

        if not self.enxuta:
            dica = Gtk.Label(
                label="Ligue «Assumir» na coluna, arraste o byte e FALE. Se o pico "
                "piscar entre dois patamares, o byte age — é o daemon disputando. "
                "Nada do que o microfone capta é gravado."
            )
            dica.set_xalign(0.0)
            dica.set_line_wrap(True)
            dica.get_style_context().add_class("dim-label")
            caixa.pack_start(dica, False, False, 0)

        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for controle in self.controles:
            conta = Gtk.Label()
            conta.get_style_context().add_class("dim-label")
            self.contadores.append((controle, conta))
            linha.pack_start(conta, False, False, 0)
        tudo = Gtk.Button(label="Devolver TUDO ao daemon")
        tudo.connect("clicked", self._devolver_tudo)
        linha.pack_end(tudo, False, False, 0)
        caixa.pack_start(linha, False, False, 0)
        caixa.pack_start(Gtk.Separator(), False, False, 6)
        return caixa

    def _devolver_tudo(self, *_: Any) -> None:
        for controle in self.controles:
            controle.devolver()
        for chave in self.chaves.values():
            chave.set_active(False)

    def _secao(self, linha: Linha) -> Gtk.Widget:
        moldura = Gtk.Frame()
        dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for lado in ("top", "bottom", "start", "end"):
            getattr(dentro, f"set_margin_{lado}")(10 if lado in ("top", "bottom") else 12)

        titulo = Gtk.Label()
        titulo.set_markup(
            f"<b>{GLib.markup_escape_text(linha.titulo)}</b>"
            + ("" if self.enxuta else f"   <span size='small'>{linha.sprint}</span>")
        )
        titulo.set_xalign(0.0)
        dentro.pack_start(titulo, False, False, 0)

        if not self.enxuta:
            for texto, classe in ((linha.pergunta, None), (f"OLHE: {linha.olhar}", "dim-label")):
                if not texto:
                    continue
                rot = Gtk.Label(label=texto)
                rot.set_xalign(0.0)
                rot.set_line_wrap(True)
                if classe:
                    rot.get_style_context().add_class(classe)
                dentro.pack_start(rot, False, False, 0)

        colunas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        colunas.set_homogeneous(True)
        colunas.set_margin_top(6)
        for controle in self.controles:
            colunas.pack_start(self._coluna(linha, controle), True, True, 0)
        dentro.pack_start(colunas, False, False, 0)

        if not self.enxuta:
            gravar = Gtk.Button(label="Gravar o que eu vi")
            gravar.connect("clicked", lambda _b, ln=linha: self.propor(ln))
            gravar.set_margin_top(6)
            dentro.pack_start(gravar, False, False, 0)

        moldura.add(dentro)
        return moldura

    def _coluna(self, linha: Linha, controle: ControleNaFolha) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        nome = Gtk.Label()
        nome.set_markup(f"<small>{GLib.markup_escape_text(controle.nome)}</small>")
        nome.set_xalign(0.0)
        caixa.pack_start(nome, False, False, 0)

        recado = Gtk.Label()
        recado.set_xalign(0.0)
        recado.set_line_wrap(True)
        recado.set_selectable(True)
        recado.get_style_context().add_class("dim-label")
        self.recados[(linha.id, controle.alvo.mac)] = recado

        montar = {
            "leitura": self._corpo_leitura,
            "pedido": self._corpo_pedido,
            "pico": self._corpo_pico,
            "byte": self._corpo_byte,
            "campo": self._corpo_campo,
            "resposta": self._corpo_resposta,
        }[linha.forma]
        montar(caixa, linha, controle)
        caixa.pack_start(recado, False, False, 0)

        if not self.enxuta:
            nota = Gtk.Entry()
            nota.set_placeholder_text(f"O que eu vi no {controle.curto}")
            nota.set_hexpand(True)
            self.notas[(linha.id, controle.alvo.mac)] = nota
            caixa.pack_start(nota, False, False, 4)
        return caixa

    def _corpo_leitura(self, caixa: Gtk.Box, _linha: Linha, controle: ControleNaFolha) -> None:
        papel = Gtk.Label()
        papel.set_markup(f"<small>{GLib.markup_escape_text(controle.papel)}</small>")
        papel.set_xalign(0.0)
        papel.set_line_wrap(True)
        caixa.pack_start(papel, False, False, 0)

    def _corpo_pedido(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        botao = Gtk.Button(label=self._BOTOES["pedido"][0])
        botao.connect("clicked", self._clicar_pedido, controle, linha)
        caixa.pack_start(botao, False, False, 0)

    def _corpo_pico(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        botoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ouvir = Gtk.Button(label=self._BOTOES["pico"][0])
        ouvir.connect("clicked", self._clicar_pico, controle, linha)
        botoes.pack_start(ouvir, True, True, 0)
        zerar = Gtk.Button(label="Zerar o máx")
        zerar.connect("clicked", self._zerar_o_maximo, controle)
        botoes.pack_start(zerar, False, False, 0)
        caixa.pack_start(botoes, False, False, 0)

        barra = Gtk.DrawingArea()
        barra.set_size_request(-1, 26)
        barra.connect("draw", self._pintar_barra, controle)
        barra.set_tooltip_text(
            "O nível AGORA (barra) e o máximo desde que ela zerou (o traço). "
            "A amostra é descartada: nada vai para disco."
        )
        self.barras.append((barra, controle))
        caixa.pack_start(barra, False, False, 0)

    def _corpo_byte(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        cabeca = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cabeca.pack_start(Gtk.Label(label="common[6]"), False, False, 0)
        chave = Gtk.Switch()
        chave.set_tooltip_text(
            "Assumir: liga o flag0 0x40 deste controle e começa a martelar a 10 Hz. "
            "Desligada, o deslizante é o NEGATIVO do ensaio."
        )
        chave.connect("notify::active", self._virar_a_chave, controle, linha)
        self.chaves[controle.alvo.mac] = chave
        cabeca.pack_end(chave, False, False, 0)
        cabeca.pack_end(Gtk.Label(label="Assumir"), False, False, 0)
        caixa.pack_start(cabeca, False, False, 0)

        ajuste = Gtk.Adjustment(
            value=rep.TETO_MIC_VOLUME,
            lower=0,
            upper=rep.TETO_MIC_VOLUME,
            step_increment=1,
            page_increment=8,
        )
        escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        escala.set_digits(0)
        escala.set_round_digits(0)
        escala.set_value_pos(Gtk.PositionType.RIGHT)
        escala.set_hexpand(True)
        for valor, texto in ((0, "0"), (0x20, "meio"), (rep.TETO_MIC_VOLUME, "teto 0x40")):
            escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        controle.escrever_byte(rep.TETO_MIC_VOLUME)
        escala.connect(
            "value-changed", lambda s, c=controle: c.escrever_byte(round(s.get_value()))
        )
        caixa.pack_start(escala, False, False, 0)

    def _corpo_campo(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        ajuste = Gtk.Adjustment(
            value=VOLUME_DA_FONTE_INICIAL, lower=0, upper=100, step_increment=1, page_increment=10
        )
        escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        escala.set_digits(0)
        escala.set_round_digits(0)
        escala.set_value_pos(Gtk.PositionType.RIGHT)
        escala.set_hexpand(True)
        for valor, texto in ((0, "0 %"), (50, "50 %"), (100, "100 %")):
            escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        pendente: dict[str, int] = {}

        def marcar(escala_: Gtk.Scale) -> None:
            novo = round(escala_.get_value())
            ja_havia = "v" in pendente
            pendente["v"] = novo
            if not ja_havia:
                GLib.timeout_add(COALESCE_DO_DESLIZANTE_MS, soltar)

        def soltar() -> bool:
            valor = pendente.pop("v", None)
            if valor is not None:
                self._dizer(linha, controle, f"mandando {valor} % ao daemon…")
                self._mandar_volume(controle, valor)
            return False

        escala.connect("value-changed", marcar)
        caixa.pack_start(escala, False, False, 0)

    def _corpo_resposta(self, caixa: Gtk.Box, _linha: Linha, controle: ControleNaFolha) -> None:
        botao = Gtk.Button(label="Perguntar ao daemon")
        botao.set_tooltip_text(
            "Manda o `mic.volume.set` com o valor que a linha 5 já está mostrando "
            "— não muda nada, e traz a resposta CRUA."
        )
        botao.connect(
            "clicked", lambda _b, c=controle: self._mandar_volume(c, c.volume_da_fonte)
        )
        caixa.pack_start(botao, False, False, 0)

    def _virar_a_chave(
        self, chave: Gtk.Switch, _p: Any, controle: ControleNaFolha, linha: Linha
    ) -> None:
        controle.assumir(chave.get_active())
        if chave.get_active() and not controle.assumido:
            chave.set_active(False)
        self._dizer(linha, controle, controle.erro or "", erro=bool(controle.erro))

    def _clicar_pedido(self, botao: Gtk.Button, controle: ControleNaFolha, linha: Linha) -> None:
        quero = not controle.canal_pedido
        botao.set_sensitive(False)
        self._dizer(linha, controle, "pedindo ao daemon…")

        def no_fundo() -> None:
            try:
                corpo = controle.pedir_o_canal(quero)
                frase = self._frase_do_pedido(corpo, quero)
            except Exception as erro:
                corpo, frase = None, f"o pedido falhou: {erro}"
            GLib.idle_add(terminar, frase, corpo is None)

        def terminar(frase: str, ruim: bool) -> bool:
            botao.set_sensitive(True)
            botao.set_label(self._BOTOES["pedido"][1 if controle.canal_pedido else 0])
            self._dizer(linha, controle, frase, erro=ruim)
            return False

        threading.Thread(target=no_fundo, name="pedir-canal", daemon=True).start()

    @staticmethod
    def _frase_do_pedido(corpo: dict[str, Any] | None, quero: bool) -> str:
        """As DUAS metades do ato viajam separadas — e é isso que ela precisa ver."""
        if corpo is None:
            return "o daemon não respondeu ao `mic.canal.set`"
        status = corpo.get("status")
        canal = corpo.get("canal_feito")
        firmware = corpo.get("firmware_pedido")
        motivo = corpo.get("motivo") or ""
        verbo = "ligar" if quero else "desligar"
        return (
            f"{verbo}: status={status} · canal_feito={canal} · firmware_pedido={firmware}"
            + (f" · {motivo}" if motivo else "")
            + " — olhe a linha 1"
        )

    def _clicar_pico(self, botao: Gtk.Button, controle: ControleNaFolha, linha: Linha) -> None:
        motivo = controle.ouvir()
        ligado = controle.ouvido is not None and controle.ouvido.ligado
        botao.set_label(self._BOTOES["pico"][1 if ligado else 0])
        if motivo:
            self._dizer(linha, controle, motivo, erro=True)
        elif ligado:
            self._dizer(
                linha, controle, f"ouvindo «{controle.leitura.escolhida}» — fale «aaaa»"
            )
        else:
            self._dizer(linha, controle, "ouvido fechado")

    def _zerar_o_maximo(self, _b: Gtk.Button, controle: ControleNaFolha) -> None:
        if controle.ouvido is not None:
            controle.ouvido.zerar_o_maximo()
        controle.barra = 0.0

    def _mandar_volume(self, controle: ControleNaFolha, valor: int) -> None:
        """O `mic.volume.set`, no FUNDO: ele tem teto de 6 s e travaria a folha."""
        linha = linha_de("o-daemon-responde")

        def no_fundo() -> None:
            try:
                controle.mandar_o_volume(valor)
            except Exception as erro:
                controle.resposta_do_volume = None
                controle.perguntou_ao_daemon = True
                GLib.idle_add(self._dizer, linha, controle, f"o pedido falhou: {erro}", True)
                return
            GLib.idle_add(self._pintar_a_resposta, controle)

        threading.Thread(target=no_fundo, name="mic-volume", daemon=True).start()

    def _pintar_a_resposta(self, controle: ControleNaFolha) -> bool:
        """A linha 6, do jeito que ela é: o corpo CRU e o veredito da tarja."""
        frase = frase_da_resposta_do_daemon(
            controle.leitura,
            controle.resposta_do_volume,
            perguntou=controle.perguntou_ao_daemon,
        )
        self._dizer(
            linha_de("o-daemon-responde"),
            controle,
            frase,
            erro="DISCORDAM" in frase or "OUTRO NÓ" in frase,
        )
        return False

    def _dizer(
        self, linha: Linha, controle: ControleNaFolha, texto: str, erro: bool = False
    ) -> bool:
        recado = self.recados.get((linha.id, controle.alvo.mac))
        if recado is None:
            return False
        if erro:
            recado.set_markup(
                f"<span foreground='#c01c28'>{GLib.markup_escape_text(texto)}</span>"
            )
        else:
            recado.set_text(texto)
        return False

    def _pintar_barra(self, area: Gtk.DrawingArea, cr: Any, controle: ControleNaFolha) -> bool:
        largura, altura = area.get_allocated_width(), area.get_allocated_height()
        cr.set_source_rgb(0.16, 0.16, 0.16)
        cr.rectangle(0, 0, largura, altura)
        cr.fill()
        nivel = max(0.0, min(1.0, controle.barra))
        cr.set_source_rgb(0.18, 0.76, 0.49)
        cr.rectangle(0, 0, largura * nivel, altura)
        cr.fill()
        maximo = controle.ouvido.maximo if controle.ouvido is not None else 0.0
        if maximo > 0:
            x = largura * max(0.0, min(1.0, maximo))
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.set_line_width(2.0)
            cr.move_to(x, 0)
            cr.line_to(x, altura)
            cr.stroke()
        cr.set_source_rgb(0.92, 0.92, 0.92)
        cr.move_to(6, altura - 8)
        cr.show_text(f"agora {nivel:.4f}   máx {maximo:.4f}")
        return False

    def _tique(self) -> bool:
        for controle in self.controles:
            controle.bater()
            if controle.ouvido is not None:
                controle.barra = max(controle.ouvido.tomar(), controle.barra - QUEDA_DA_BARRA)
            else:
                controle.barra = 0.0
        for barra, _ in self.barras:
            barra.queue_draw()
        for controle, conta in self.contadores:
            if controle.erro:
                conta.set_markup(
                    f"<span foreground='#c01c28'>{GLib.markup_escape_text(controle.nome)}: "
                    f"{GLib.markup_escape_text(controle.erro)}</span>"
                )
            else:
                conta.set_text(
                    f"{controle.nome}: byte {controle.byte:#04x}, "
                    f"{'assumido' if controle.assumido else 'do daemon'}, "
                    f"{controle.escritas} escritas"
                )
        return True

    def _reler_a_lista(self) -> bool:
        """A lista viva, num TRABALHADOR: o `pactl` tem teto de 8 s e travaria a folha."""
        if self._relendo:
            return True
        self._relendo = True

        def no_fundo() -> None:
            try:
                leituras = ler_o_sistema([c.alvo for c in self.controles])
            except Exception:
                leituras = {}
            GLib.idle_add(pintar, leituras)

        def pintar(leituras: dict[str, LeituraDoSistema]) -> bool:
            for controle in self.controles:
                nova = leituras.get(controle.alvo.mac)
                if nova is not None:
                    controle.leitura = nova
                self._dizer(linha_de("o-no-existe"), controle, controle.leitura.frase())
                self._pintar_a_resposta(controle)
                ouvindo = controle.ouvido is not None and controle.ouvido.ligado
                if not ouvindo:
                    onde = controle.leitura.escolhida
                    self._dizer(
                        linha_de("o-pico-ao-vivo"),
                        controle,
                        f"ouvido fechado — abriria em «{onde}»"
                        if onde
                        else "não há entrada para ouvir: peça o canal na linha 2",
                    )
            self._relendo = False
            return False

        threading.Thread(target=no_fundo, name="reler-a-lista", daemon=True).start()
        return True

    def propor(self, linha: Linha) -> None:
        """A folha NÃO conclui: imprime as linhas, e quem roda as escreve."""
        print(f"\nLINHAS PROPOSTAS — {linha.titulo} (docs/data/ensaios.csv):")
        for controle in self.controles:
            caixa = self.notas.get((linha.id, controle.alvo.mac))
            nota = caixa.get_text().strip() if caixa is not None else ""
            if not nota:
                print(f"  (o {controle.nome} ficou sem resposta — nada a propor por ele)")
                continue
            print(
                linha_do_caderno(
                    id=f"folha-mic-{linha.id}-{controle.curto}-{_agora_ddmm()}",
                    linha_id=linha.linha_do_mapa,
                    transporte=controle.curto,
                    suspeito=linha.pergunta,
                    presente="sim" if controle.leitura.publica else "não",
                    resultado="",
                    observado_por="olho-dela",
                    fonte="scripts/ensaios/a_folha_do_microfone_por_controle.py",
                    nota=self._nota_da_linha(linha, controle, nota),
                )
            )
        sys.stdout.flush()

    def _nota_da_linha(self, linha: Linha, controle: ControleNaFolha, dela: str) -> str:
        """O que a linha do caderno carrega de MEDIDO, além da frase de produto."""
        maximo = controle.ouvido.maximo if controle.ouvido is not None else 0.0
        medido = [
            f"sistema: {controle.leitura.frase()}",
            f"byte common[6]={controle.byte:#04x}",
            f"flag0 0x40 {'ligado' if controle.assumido else 'apagado'}",
            f"martelo {HZ:g} Hz",
            f"pico máx {maximo:.4f}",
            f"fonte {controle.volume_da_fonte} %",
            "daemon: "
            + (
                str(controle.resposta_do_volume)
                if controle.perguntou_ao_daemon
                else "não perguntei"
            ),
        ]
        if linha.forma == "pedido":
            medido.append(f"mic.canal.set: {controle.resposta_do_canal}")
        return "; ".join(medido) + f"; ela: {dela}"

    def _fechar(self, *_: Any) -> None:
        for controle in self.controles:
            controle.fechar()
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def abrir(self) -> None:
        self.janela.show_all()
        Gtk.main()


def _cabecalho() -> str:
    return cabecalho_do_instrumento(
        "a_folha_do_microfone_por_controle",
        "o mic de cada controle sobe, capta, e o byte do aparelho muda a captura?",
        bibliotecas=[
            "hefesto_dualsense4unix.core.ds_output_report",
            "hefesto_dualsense4unix.integrations.canal_do_microfone",
            "hefesto_dualsense4unix.integrations.audio_control",
        ],
        escreve_no_aparelho=True,
    )


def listar(alvos: list[Any]) -> int:
    """`--listar`: SÓ LÊ. Nenhuma porta abre, nenhum byte sai, nenhum mic liga."""
    print(_cabecalho())
    print(
        "\nnesta corrida NADA foi escrito: a porta do hidraw só abre no primeiro\n"
        "«Assumir», e o ouvido do pico só no botão «Ouvir o pico».\n"
    )
    print(frase_da_mesa(alvos) + "\n")
    leituras = ler_o_sistema(alvos)
    largura = f"{'controle':<22} {'transp.':<7} o que o sistema publica"
    print(largura)
    print("-" * 100)
    for a in alvos:
        leitura = leituras.get(a.mac, LeituraDoSistema())
        print(f"{mascarar(a.mac):<22} {a.transporte:<7} {leitura.frase()}")
    print(f"\n{'linha':<22} {'sprint':<20} o que ela decide")
    print("-" * 100)
    for linha in LINHAS:
        print(f"{linha.id:<22} {linha.sprint:<20} {linha.pergunta}")
    faltando = [
        f"{mascarar(a.mac)} ({a.transporte})"
        for a in alvos
        if not leituras.get(a.mac, LeituraDoSistema()).publica
    ]
    if faltando:
        print(
            resumo(
                "sem entrada publicada: "
                + " · ".join(faltando)
                + " — é a linha 2 desta folha (o botão «Pedir o canal») que responde."
            )
        )
        return 0
    print(resumo(f"os {len(alvos)} controles têm entrada publicada na lista viva."))
    return 0


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    desconhecidas = [
        a for a in argumentos if a not in (*BANDEIRAS_SEM_TELA, "--so-ajustes")
    ]
    if desconhecidas:
        print(f"bandeira que esta folha não conhece: {desconhecidas} — veja o bloco USO.")
        return 2

    alvos = alvos_da_mesa()
    if not alvos:
        print("nenhum DualSense físico encontrado. Plugue ou pareie e rode de novo.")
        return 1

    if "--listar" in argumentos:
        return listar(alvos)

    print(_cabecalho())
    print("\n" + frase_da_mesa(alvos))
    controles = [ControleNaFolha(a) for a in alvos]
    try:
        for mac, leitura in ler_o_sistema(alvos).items():
            for controle in controles:
                if controle.alvo.mac == mac:
                    controle.leitura = leitura
    except Exception as erro:
        print(f"a lista viva não respondeu ({erro}) — as linhas dirão por quê")
    print(f"controles: {', '.join(c.nome for c in controles)}")
    print(f"linhas na folha: {len(LINHAS)}")

    folha = Folha(controles, enxuta="--so-ajustes" in argumentos)
    if "--oculta" in argumentos:
        folha._tique()
        for linha in LINHAS:
            folha.propor(linha)
        folha._fechar()
        return 0
    folha.abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
