#!/usr/bin/env python3
"""comum.py — o chão compartilhado pelos instrumentos do ensaio 2+2.

POR QUE ESTE MÓDULO EXISTE
--------------------------
Os quatro instrumentos de `scripts/ensaios/` fazem a MESMA pergunta antes de
qualquer medição: *quais aparelhos estão na mesa, em que transporte, e o daemon
está no caminho?* Escrever essa resposta quatro vezes seria escrever quatro
réguas — e nesta casa já se mediu o preço disso (`identidade_do_vpad.py`, que
nasceu porque três instrumentos respondiam "isto é um vpad?" de três jeitos, e
um deles respondia errado).

O precedente de forma é o próprio `identidade_do_vpad.py`, importado por
`sys.path.insert` do diretório-pai. Aqui se faz igual, e a régua do vpad é
REUSADA, nunca reimplementada.

A PROCEDÊNCIA, DECLARADA (regra da casa, e o defeito que a criou)
-----------------------------------------------------------------
"Medir contra a biblioteca errada produz alarme convincente e falso" — já
aconteceu três vezes aqui. Por isso todo instrumento desta pasta imprime, ANTES
da primeira linha de medição, de qual arquivo veio cada biblioteca que ele usa.
Não o nome: o **caminho**. O `python3` do sistema e o `.venv/bin/python` deste
projeto não têm o mesmo `evdev`, e a diferença já enganou gente.

A PORTA, DECLARADA (A-PORTA-QUE-A-CASA-CONSTRUIU-01, 15/08/2026)
-----------------------------------------------------------------
O mesmo raciocínio vale para **por onde** se mediu. Com a mesa 2+2 montada e o
co-op ligado, nenhum dos DualSense físicos abre por `open()`: o próprio Hefesto
os esconde do jogo (`broker/hidraw_broker.py`, `chmod 0600` + ACL removida).
Quem bate ali mede `EACCES`; quem bate na porta certa — o `cmd open` do broker,
que devolve o fd por SCM_RIGHTS — mede o aparelho. As duas coisas produzem
relatório, e só uma delas produz medição. **Por isso a porta usada vai no
cabeçalho, ao lado da biblioteca.**

E um andar abaixo, o mesmo modo de falha: o co-op faz `EVIOCGRAB` no evdev
físico, e um instrumento ingênuo lê zero evento e conclui que o aparelho está
calado. *"O controle não emitiu"* e *"eu não posso ler"* têm de sair diferentes
na tela — é o que `estado_do_grab` e `leitura_de_zero` existem para garantir.

O QUE ESTES INSTRUMENTOS NUNCA FAZEM
-------------------------------------
**Não escrevem no aparelho.** Nenhum deles. Leitura pura: `GET_FEATURE` por
ioctl, `read()` de evdev, arquivos de `/sys` e de `/proc`. Onde um ensaio
exigiria escrita — a cor de fábrica exige um `SET_FEATURE 0x80` antes do
`GET_FEATURE 0x81` — o instrumento **imprime o comando exato e para**, para
que a decisão de escrever seja dela, não minha.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_AQUI)
_SRC = os.path.join(os.path.dirname(_SCRIPTS), "src")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from identidade_do_vpad import campos_do_uevent, e_vpad_do_hefesto

try:
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        GRAB_DE_TERCEIRO,  # noqa: F401 - reexportado para os instrumentos
        GRAB_LIVRE,  # noqa: F401 - reexportado para os instrumentos
        GRAB_SEM_NO,  # noqa: F401 - reexportado para os instrumentos
        GRAB_SEM_PERMISSAO,  # noqa: F401 - reexportado para os instrumentos
        PORTA_DIRETA,  # noqa: F401 - reexportado para os instrumentos
        NoAberto,
        PortaFechadaError,  # noqa: F401 - reexportado para os instrumentos
        abrir_hidraw,
        estado_do_grab,
        leitura_de_zero,  # noqa: F401 - reexportado para os instrumentos
        linha_da_porta,
        linha_do_grab,
        porta_provavel,
    )

    PORTA_IMPORTAVEL = ""
except ImportError as _erro:  # pragma: no cover - só fora do venv do projeto
    PORTA_IMPORTAVEL = str(_erro)

VERSAO_DOS_INSTRUMENTOS = "2026-08-15"

# O DualSense de fábrica. O `0x0DF2` (DualSense Edge) fica DE FORA de propósito:
VID_SONY = 0x054C
PID_DUALSENSE = 0x0CE6

BUS_USB = 0x0003
BUS_BLUETOOTH = 0x0005

CABO = "cabo"
RADIO = "rádio"

# DualSense Edge no cabo — então a leitura ingênua do barramento o classifica
VPAD = "vpad (sem transporte)"


@dataclass(frozen=True)
class Aparelho:
    """Um nó `hidraw` já classificado: quem é, por onde fala, e onde mora."""

    hidraw: str
    caminho_hidraw: str
    dir_device: str
    mac: str
    nome: str
    transporte: str
    e_vpad: bool
    rotulo: str

    @property
    def apelido(self) -> str:
        """Como ele aparece nas tabelas: curto, e único na mesa."""
        if self.e_vpad:
            return f"vpad {self.rotulo}"
        return self.mac or self.hidraw


@dataclass
class EstadoDoDaemon:
    """O que se sabe do daemon do Hefesto, e o que isso custa à medição."""

    unidade_ativa: bool = False
    processos: list[str] = field(default_factory=list)
    broker_ativo: bool = False
    socket: str = ""

    @property
    def rodando(self) -> bool:
        return self.unidade_ativa or bool(self.processos)


def ler_texto(caminho: str) -> str:
    """O conteúdo de `caminho`, ou "" se ilegível. Nunca levanta."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def _transporte_do_hid_id(hid_id: str) -> str:
    """`cabo` ou `rádio` a partir do campo `HID_ID` do `uevent` do pai HID."""
    partes = hid_id.split(":")
    if not partes:
        return "?"
    try:
        barramento = int(partes[0], 16)
    except ValueError:
        return "?"
    if barramento == BUS_BLUETOOTH:
        return RADIO
    if barramento == BUS_USB:
        return CABO
    return f"bus 0x{barramento:04x}"


def _e_dualsense_fisico(hid_id: str) -> bool:
    partes = hid_id.split(":")
    if len(partes) != 3:
        return False
    try:
        barramento, vendor, product = (int(parte, 16) for parte in partes)
    except ValueError:
        return False
    return (
        vendor == VID_SONY
        and product == PID_DUALSENSE
        and barramento in (BUS_USB, BUS_BLUETOOTH)
    )


def _rotulo_do_vpad(campos: dict[str, str]) -> str:
    """"P1".."P4" a partir do que o produto carimba no vpad, ou "?"."""
    nome = campos.get("HID_NAME", "")
    if "(Hefesto P" in nome:
        depois = nome.split("(Hefesto P", 1)[1]
        numero = depois.split(")", 1)[0].strip()
        if numero.isdigit():
            return f"P{numero}"
    uniq = campos.get("HID_UNIQ", "").strip()
    if uniq.lower().startswith("02:fe:"):
        último = uniq.split(":")[-1]
        try:
            return f"P{int(último, 16)}"
        except ValueError:
            return "?"
    return "?"


def descobrir_aparelhos() -> list[Aparelho]:
    """Todos os DualSense da mesa — físicos e vpads — lidos do sysfs.

    Resolve a cada chamada, de propósito: **os números de nó não são estáveis**.
    Medido em 15/08/2026, entre duas chamadas com segundos de diferença, um
    controle sumiu e outro reapareceu com `event` diferente. Instrumento que
    guarda caminho mede o aparelho errado, ou nenhum.
    """
    achados: list[Aparelho] = []
    base = "/sys/class/hidraw"
    try:
        nos = sorted(os.listdir(base), key=lambda n: int(n.removeprefix("hidraw") or 0))
    except OSError:
        return achados

    for no in nos:
        dir_device = os.path.realpath(os.path.join(base, no, "device"))
        campos = campos_do_uevent(ler_texto(os.path.join(dir_device, "uevent")))
        hid_id = campos.get("HID_ID", "")
        nome = campos.get("HID_NAME", "")
        vpad = e_vpad_do_hefesto(campos, nome=nome)
        if not vpad and not _e_dualsense_fisico(hid_id):
            continue
        achados.append(
            Aparelho(
                hidraw=no,
                caminho_hidraw=f"/dev/{no}",
                dir_device=dir_device,
                mac=campos.get("HID_UNIQ", "").strip().lower(),
                nome=nome,
                transporte=VPAD if vpad else _transporte_do_hid_id(hid_id),
                e_vpad=vpad,
                rotulo=_rotulo_do_vpad(campos) if vpad else "",
            )
        )
    return achados


def fisicos(aparelhos: list[Aparelho]) -> list[Aparelho]:
    return [a for a in aparelhos if not a.e_vpad]


def vpads(aparelhos: list[Aparelho]) -> list[Aparelho]:
    return [a for a in aparelhos if a.e_vpad]


_TAMANHO_DO_ITEM = {0: 0, 1: 1, 2: 2, 3: 4}


def tamanhos_do_descritor(dir_device: str) -> dict[str, dict[int, int]]:
    """Os tamanhos em bytes de cada report FEATURE/OUTPUT/INPUT declarado."""
    bruto = b""
    try:
        with open(os.path.join(dir_device, "report_descriptor"), "rb") as arquivo:
            bruto = arquivo.read()
    except OSError:
        return {"feature": {}, "output": {}, "input": {}}

    bits: dict[str, dict[int, int]] = {"feature": {}, "output": {}, "input": {}}
    onde = {0x80: "input", 0x90: "output", 0xB0: "feature"}
    indice = 0
    report_id = 0
    tamanho_do_campo = 0
    quantidade = 0

    while indice < len(bruto):
        prefixo = bruto[indice]
        indice += 1
        largura = _TAMANHO_DO_ITEM[prefixo & 0x03]
        valor = int.from_bytes(bruto[indice : indice + largura], "little") if largura else 0
        indice += largura
        etiqueta = prefixo & 0xFC
        if etiqueta == 0x84:
            report_id = valor
        elif etiqueta == 0x74:
            tamanho_do_campo = valor
        elif etiqueta == 0x94:
            quantidade = valor
        elif etiqueta in onde:
            acumulado = bits[onde[etiqueta]]
            acumulado[report_id] = acumulado.get(report_id, 0) + tamanho_do_campo * quantidade

    return {
        classe: {rid: math.ceil(n / 8) + 1 for rid, n in sorted(mapa.items()) if rid}
        for classe, mapa in bits.items()
    }


def estado_do_daemon() -> EstadoDoDaemon:
    """Descobre se o daemon do Hefesto está vivo, e se o broker está no caminho."""
    estado = EstadoDoDaemon()

    if shutil.which("systemctl"):
        try:
            saida = subprocess.run(
                ["systemctl", "--user", "is-active", "hefesto-dualsense4unix"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            estado.unidade_ativa = saida.stdout.strip() == "active"
        except (OSError, subprocess.SubprocessError):
            pass

    if shutil.which("pgrep"):
        try:
            saida = subprocess.run(
                ["pgrep", "-af", "hefesto"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            for linha in saida.stdout.splitlines():
                if "daemon" in linha and "storm_watch" not in linha:
                    estado.processos.append(linha.strip())
                if "hidraw-broker" in linha:
                    estado.broker_ativo = True
        except (OSError, subprocess.SubprocessError):
            pass

    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    candidato = os.path.join(runtime, "hefesto-dualsense4unix", "hefesto-dualsense4unix.sock")
    if os.path.exists(candidato):
        estado.socket = candidato

    return estado


def diagnostico_de_acesso(caminho: str) -> str:
    """Por que `caminho` não abre — em português, e apontando a causa provável."""
    if not os.path.exists(caminho):
        return "o nó não existe (controle desconectado?)"
    try:
        modo = os.stat(caminho).st_mode & 0o777
    except OSError as erro:
        return f"stat falhou: {erro}"
    if not os.access(caminho, os.R_OK):
        if modo == 0o600:
            return (
                f"sem permissão (modo {modo:04o}, root:root) — assinatura do "
                "broker do Hefesto ESCONDENDO o físico; a porta é o broker"
            )
        return f"sem permissão (modo {modo:04o})"
    return "acessível"


def abrir_no_hidraw(caminho: str, *, escrita: bool = True) -> NoAberto:
    """Abre um hidraw pela porta do broker, com queda declarada para `open()`."""
    if PORTA_IMPORTAVEL:
        raise SystemExit(
            "ERRO: o cliente do broker não é importável neste interpretador "
            f"({PORTA_IMPORTAVEL}).\n"
            "Sem ele eu só saberia abrir o hidraw por `open()` direto, que na "
            "mesa com o co-op ligado mede EACCES e não o aparelho.\n"
            "Rode com o interpretador do projeto:\n"
            "    .venv/bin/python scripts/ensaios/<instrumento>.py"
        )
    return abrir_hidraw(caminho, escrita=escrita)


def _largura(texto: str) -> int:
    return len(texto)


def tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    """Uma tabela alinhada, para ler na tela. Ela lê isto, não JSON."""
    if not linhas:
        colunas = [_largura(c) for c in cabecalho]
    else:
        colunas = [
            max(_largura(cabecalho[i]), *(_largura(linha[i]) for linha in linhas))
            for i in range(len(cabecalho))
        ]
    partes = ["  ".join(c.ljust(colunas[i]) for i, c in enumerate(cabecalho)).rstrip()]
    partes.append("  ".join("-" * colunas[i] for i in range(len(cabecalho))))
    for linha in linhas:
        partes.append("  ".join(str(c).ljust(colunas[i]) for i, c in enumerate(linha)).rstrip())
    return "\n".join(partes)


def _procedencia(modulo_nome: str) -> str:
    """De qual ARQUIVO veio o módulo — não o nome dele."""
    modulo = sys.modules.get(modulo_nome)
    if modulo is None:
        return "NÃO IMPORTADO"
    caminho = getattr(modulo, "__file__", None)
    if caminho:
        return caminho
    if modulo_nome in sys.builtin_module_names:
        return "embutido no interpretador (stdlib estática)"
    return "sem __file__ (extensão da stdlib)"


def declaracao_da_porta() -> str:
    """A linha `porta ...` do cabeçalho — a mesma frase em toda a casa."""
    if PORTA_IMPORTAVEL:
        return (
            "porta ............ NÃO SEI — o cliente do broker não é importável "
            f"neste interpretador ({PORTA_IMPORTAVEL})"
        )
    return linha_da_porta(*porta_provavel())


def cabecalho_do_instrumento(
    nome: str,
    pergunta: str,
    *,
    bibliotecas: list[str],
    escreve_no_aparelho: bool = False,
    daemon_precisa_parar: bool = False,
    nos_evdev: list[str] | None = None,
) -> str:
    """O bloco que todo instrumento desta pasta imprime ANTES de medir."""
    estado = estado_do_daemon()
    linhas = [
        "=" * 78,
        f"  {nome}   (instrumentos do ensaio 2+2, versão {VERSAO_DOS_INSTRUMENTOS})",
        "=" * 78,
        f"  pergunta ......... {pergunta}",
        f"  interpretador .... {sys.executable}",
    ]
    for lib in bibliotecas:
        linhas.append(f"  biblioteca ....... {lib:<22} de {_procedencia(lib)}")
    linhas.append("  " + declaracao_da_porta())
    for caminho in nos_evdev or []:
        if PORTA_IMPORTAVEL:
            linhas.append(f"  grab do evdev .... {caminho}: NÃO SEI (cliente não importável)")
            continue
        linhas.append("  " + linha_do_grab(caminho, estado_do_grab(caminho)))
    linhas.append(
        "  escreve no aparelho? .. "
        + ("SIM" if escreve_no_aparelho else "NÃO — leitura pura, nesta rodada")
    )

    if daemon_precisa_parar:
        exigencia = "SIM — pare o daemon antes, senão o broker esconde o hidraw do físico"
    else:
        exigencia = "não — este instrumento não disputa o hidraw com o daemon"
    linhas.append(f"  daemon precisa parar? . {exigencia}")

    if estado.rodando:
        detalhe = "unidade de usuário ativa" if estado.unidade_ativa else "processo vivo"
        linhas.append(f"  daemon AGORA .......... RODANDO ({detalhe})")
        if estado.broker_ativo:
            linhas.append(
                "  broker AGORA .......... RODANDO — os hidraw dos FÍSICOS estão escondidos"
            )
        if daemon_precisa_parar:
            linhas.append("")
            linhas.append("  >> AVISO: este instrumento vai medir com o daemon no caminho.")
            linhas.append("  >> Para a medição limpa, rode antes:")
            linhas.append("  >>     systemctl --user stop hefesto-dualsense4unix")
    else:
        linhas.append("  daemon AGORA .......... parado")
    linhas.append("=" * 78)
    return "\n".join(linhas)


def resumo(texto: str) -> str:
    """A linha final. Uma só, e ela diz o que a medição decidiu."""
    return "\n" + "-" * 78 + f"\nRESUMO: {texto}\n" + "-" * 78


def censo_da_mesa(aparelhos: list[Aparelho]) -> str:
    """A frase honesta sobre a mesa que este instrumento ENCONTROU."""
    reais = fisicos(aparelhos)
    por_transporte: dict[str, int] = {}
    for a in reais:
        por_transporte[a.transporte] = por_transporte.get(a.transporte, 0) + 1
    if not reais:
        return "NENHUM DualSense físico na mesa — não há o que medir."
    desenho = ", ".join(f"{n} no {t}" for t, n in sorted(por_transporte.items()))
    if len(por_transporte) < 2:
        return (
            f"mesa com {len(reais)} controle(s): {desenho}. "
            "SÓ UM TRANSPORTE presente — isto NÃO é o ensaio 2+2, e nenhuma "
            "coluna cabo-x-rádio abaixo compara coisa alguma."
        )
    return f"mesa com {len(reais)} controle(s): {desenho} — os dois transportes presentes."


# *"fora que nao deu pra ler nada nos botoes"*.  # noqa-acento: citação literal dela


def o_tema_e_escuro() -> bool:
    """Escuro pelo que o tema PINTA, e não pelo sinalizador que ninguém liga."""
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    ajustes = Gtk.Settings.get_default()
    if ajustes is not None:
        if bool(ajustes.get_property("gtk-application-prefer-dark-theme")):
            return True
        nome = str(ajustes.get_property("gtk-theme-name") or "")
        if "dark" in nome.lower():
            return True

    janela = Gtk.OffscreenWindow()
    botao = Gtk.Button(label="x")
    janela.add(botao)
    try:
        letra = botao.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        luminancia = 0.2126 * letra.red + 0.7152 * letra.green + 0.0722 * letra.blue
        return bool(luminancia > 0.5)
    finally:
        janela.destroy()


def pintar_fundo_solido(janela: object) -> None:
    """Um fundo SÓLIDO e LEGÍVEL para a folha — razão dela: *"o fundo tá muito transparente"*."""
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    escuro = o_tema_e_escuro()
    if escuro:
        fundo, letra, moldura = "#1f1f1f", "#f2f2f2", "#2a2a2a"
        campo, borda = "#333333", "#555555"
    else:
        fundo, letra, moldura = "#f6f5f4", "#1b1b1b", "#ffffff"
        campo, borda = "#ffffff", "#c0bfbc"
    css = (
        f"window, window.background {{ background-color: {fundo}; color: {letra}; }}"
        f"frame {{ background-color: {moldura}; border-radius: 6px; }}"
        f"scrolledwindow {{ background-color: {fundo}; }}"
        f"label {{ color: {letra}; }}"
        f"button {{ background-image: none; background-color: {campo}; color: {letra};"
        f" border: 1px solid {borda}; }}"
        f"button:hover {{ background-color: {borda}; }}"
        f"entry {{ background-image: none; background-color: {campo}; color: {letra};"
        f" border: 1px solid {borda}; }}"
        f"entry placeholder {{ color: {borda}; }}"
        f"combobox button {{ background-color: {campo}; color: {letra}; }}"
        f"scale value {{ color: {letra}; }}"
        f"scale marks label {{ color: {letra}; }}"
    )
    provedor = Gtk.CssProvider()
    provedor.load_from_data(css.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provedor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    janela.set_app_paintable(False)  # type: ignore[attr-defined]
