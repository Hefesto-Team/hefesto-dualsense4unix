"""A porta do servidor de som: o `pactl` em JSON e o diretório dos módulos do PipeWire.

O-SOM-LE-O-PACTL-EM-JSON-E-ACHA-OS-MODULOS-PELA-PORTA-01 (08/10/2026), filha do
censo de contratos de fora.

**O DEFEITO, medido em 07/10/2026:** dez módulos de `src/` e cinco scripts liam o
texto longo do `pactl list sinks|sources|source-outputs|sink-inputs` pelo rótulo
(`Name:`, `Sink:`, `sysfs.path = `) e pela posição. O `pactl` traduz os rótulos e o
servidor muda a ordem, e a leitura devolve lixo sem erro. A porta existe: o
`pactl --format=json` (16.1) entrega os mesmos campos com NOME.

**A CURA, na origem:** este módulo é o único que sabe a forma do JSON. Quem quer
os nós, os fluxos, o `sysfs.path` de cada nó ou a placa ALSA de cada fonte pede
aqui, com o executor que já tinha (o do retrato, o do `rodar_pactl`, o dublê da
régua), e recebe estrutura.

**SEM A PORTA, O CAMINHO CURTO** (`pactl` anterior ao 16, que não conhece
`--format`): a leitura devolve `None` («não sei»), e cada chamador cai no que já
fazia sem o dado — o casamento por USB some e o nome do nó decide, o volume lido
vira cem por cento. O formato curto (`list short`) segue sendo texto de colunas
estáveis, lido onde só o índice e o nome bastam.

**O QUE O `pactl` 16.1 NÃO DÁ EM JSON, medido em 08/10/2026 nesta máquina:**

* texto com acento vira `null` no campo inteiro (`Invalid non-ASCII character`
  no stderr, e o valor sai como a cadeia `(null)`): a descrição «Estéreo digital» de
  uma placa e o `node.name` do Sackboy™ vêm `(null)`. O leitor desta porta
  (:func:`ler_a_lista`) completa o que se perdeu pelo grafo do PipeWire (o
  ``pw-dump``, que fala UTF-8), casando pela identidade do nó, numa leitura só
  por pergunta e só quando algo se perdeu (:func:`completar_o_json`). Sem o
  grafo, o campo fica VAZIO e marcado (:attr:`Fluxo.perdidos`,
  :attr:`NoDeSom.descricao_nula`), nunca inventado;
* `list modules` em JSON não traz o ÍNDICE do módulo. Quem precisa dele (os
  módulos que o Hefesto carrega e descarrega) lê `list short modules`, de colunas
  estáveis.

**A LÍNGUA FICA PRESA EM C** pelo executor de quem chama (a razão que esta casa já
pagou duas vezes); o JSON dispensa a tradução dos rótulos, mas a descrição vem do
servidor, e o idioma dele não é o nosso problema.

**O DIRETÓRIO DOS MÓDULOS** do PipeWire não é escrito aqui: vem de
`PIPEWIRE_MODULE_DIR` (o que o próprio PipeWire honra), do
`pkg-config --variable=moduledir libpipewire-0.3` ou da pasta da própria
`libpipewire-0.3.so` que o `ldconfig` lista (a máquina sem o pacote de
desenvolvimento não tem o `.pc`). O `0.3` é a versão da API, e o nome da pasta
sai do nome da biblioteca achada.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

Leitor = Callable[[list[str]], "str | None"]

FORMATO_JSON: Final[str] = "--format=json"

#: quanto esperar pelo `pkg-config`/`ldconfig` antes de dizer «não sei».
PRAZO_DA_PERGUNTA_S: Final[int] = 5

#: o que o `pactl` imprime no lugar de um texto que o JSON não conseguiu escrever.
NULO_DO_PACTL: Final[str] = "(null)"

#: a marca do objeto já conferido contra o grafo: o que ainda falta nele, o grafo não tem.
CHAVE_DO_GRAFO: Final[str] = "hefesto.grafo"

#: quem lê o grafo do PipeWire: o texto do ``pw-dump``, ou ``None`` («não sei»).
Grafo = Callable[[], "str | None"]

TIPOS_DE_NO: Final[tuple[str, ...]] = ("sinks", "sources")
TIPOS_DE_FLUXO: Final[tuple[str, ...]] = ("sink-inputs", "source-outputs")


def argv_da_lista(tipo: str) -> list[str]:
    """O argv da lista completa de um tipo, pela porta do JSON."""
    return ["pactl", FORMATO_JSON, "list", tipo]


def argv_do_curto(tipo: str) -> list[str]:
    """O argv da lista curta de um tipo: colunas separadas por tabulação."""
    return ["pactl", "list", tipo, "short"]


def sem_o_formato(argv: Sequence[object]) -> tuple[list[str], bool]:
    """``(argv sem as opções de formato, pediu JSON?)``. ``-f json`` e ``--format json`` contam."""
    resto: list[str] = []
    json_pedido = False
    pular = False
    for i, bruto in enumerate(argv):
        parte = str(bruto)
        if pular:
            pular = False
            continue
        if i == 0:
            resto.append(parte)
            continue
        if parte in ("--format=json", "-fjson"):
            json_pedido = True
            continue
        if parte in ("-f", "--format") and i + 1 < len(argv) and str(argv[i + 1]) == "json":
            json_pedido = True
            pular = True
            continue
        resto.append(parte)
    return resto, json_pedido


def _texto(valor: object) -> str:
    """Um campo de texto do JSON. Ausente, ``null`` e ``(null)`` são vazios."""
    if valor is None:
        return ""
    texto = str(valor)
    return "" if texto == NULO_DO_PACTL else texto


def _sim_ou_nao(valor: object) -> bool | None:
    return valor if isinstance(valor, bool) else None


@dataclass(frozen=True)
class Canal:
    """O volume de UM canal: o valor bruto, o por cento e os dB, como o servidor os diz."""

    nome: str
    bruto: int
    porcento: str
    db: str

    @property
    def inteiro(self) -> int | None:
        """O por cento sem o sinal, ou ``None`` se o servidor não deu número."""
        corte = self.porcento.rstrip("%").strip()
        return int(corte) if corte.lstrip("-").isdigit() else None


@dataclass(frozen=True)
class NoDeSom:
    """Um nó de saída (`sink`) ou de entrada (`source`), como o servidor o diz."""

    indice: int
    nome: str
    descricao: str = ""
    driver: str = ""
    formato: str = ""
    estado: str = ""
    mudo: bool | None = None
    canais: tuple[Canal, ...] = ()
    balanco: str = ""
    propriedades: Mapping[str, str] = field(default_factory=dict)
    #: o servidor perdeu a descrição (``null`` ou ``(null)``): a de cima é o recuo
    descricao_nula: bool = False
    #: as propriedades cujo texto o ``pactl`` perdeu (``(null)``): vazias aqui, não ausentes
    perdidos: frozenset[str] = frozenset()

    def perdeu(self, chave: str) -> bool:
        """O ``pactl`` perdeu o texto desta propriedade (o acento, o ™)?"""
        return chave in self.perdidos

    @property
    def volume(self) -> str:
        """O volume na forma que o `get-sink-volume` imprime. Vazio sem canais."""
        return ",   ".join(f"{c.nome}: {c.bruto} / {c.porcento} / {c.db}" for c in self.canais)

    @property
    def porcentos(self) -> list[int]:
        """O por cento de cada canal, na ordem do mapa. Canal sem número fica de fora."""
        return [c.inteiro for c in self.canais if c.inteiro is not None]


@dataclass(frozen=True)
class Fluxo:
    """Um fluxo de um programa: `sink-input` (tocando) ou `source-output` (gravando)."""

    indice: int
    alvo: str
    cliente: str = ""
    driver: str = ""
    formato: str = ""
    corked: bool | None = None
    mudo: bool | None = None
    propriedades: Mapping[str, str] = field(default_factory=dict)
    #: as propriedades cujo texto o ``pactl`` perdeu (``(null)``): vazias aqui, não ausentes
    perdidos: frozenset[str] = frozenset()

    def perdeu(self, chave: str) -> bool:
        """O ``pactl`` perdeu o texto desta propriedade (o nome do jogo com ™)?"""
        return chave in self.perdidos

    def carrega(self, marca: str) -> bool:
        """A ``marca`` aparece em alguma propriedade do fluxo (o nome que o dono deu)?"""
        return bool(marca) and any(marca in v for v in self.propriedades.values())


def _inteiro(valor: object) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().lstrip("-").isdigit():
        return int(valor.strip())
    return None


def _propriedades(bruto: object) -> dict[str, str]:
    if not isinstance(bruto, Mapping):
        return {}
    return {str(k): _texto(v) for k, v in bruto.items()}


def _perdidos(bruto: object) -> frozenset[str]:
    """As chaves cujo valor o ``pactl`` trocou por ``(null)``: o texto existia e se perdeu."""
    if not isinstance(bruto, Mapping):
        return frozenset()
    return frozenset(str(k) for k, v in bruto.items() if v == NULO_DO_PACTL)


def _canais(bruto: object) -> tuple[Canal, ...]:
    if not isinstance(bruto, Mapping):
        return ()
    fora: list[Canal] = []
    for nome, dado in bruto.items():
        if not isinstance(dado, Mapping):
            continue
        valor = _inteiro(dado.get("value"))
        if valor is None:
            continue
        fora.append(Canal(str(nome), valor, _texto(dado.get("value_percent")),
                          _texto(dado.get("db"))))
    return tuple(fora)


def _balanco(bruto: object) -> str:
    if isinstance(bruto, bool) or not isinstance(bruto, (int, float)):
        return ""
    return f"balance {bruto:.2f}"


def lista_do_json(texto: str | None) -> list[dict[str, Any]] | None:
    """A lista de objetos de um ``pactl --format=json list``, ou ``None``.

    ``None`` é «não sei»: o texto não é JSON (o `pactl` sem a porta imprime erro ou
    o formato longo), ou é JSON de outra forma. Lista vazia é resposta: o servidor
    respondeu e não há nó.
    """
    if texto is None or not texto.strip():
        return None
    try:
        bruto = json.loads(texto)
    except ValueError:
        logger.debug("pactl_json_ilegivel", inicio=texto[:40])
        return None
    if not isinstance(bruto, list):
        return None
    return [o for o in bruto if isinstance(o, dict)]


def _no_do_json(o: Mapping[str, Any]) -> NoDeSom | None:
    indice = _inteiro(o.get("index"))
    if indice is None:
        return None
    props = _propriedades(o.get("properties"))
    descricao = _texto(o.get("description"))
    nula = not descricao
    if nula:
        descricao = _texto(props.get("device.description"))
    return NoDeSom(
        indice=indice,
        nome=_texto(o.get("name")),
        descricao=descricao,
        driver=_texto(o.get("driver")),
        formato=_texto(o.get("sample_specification")),
        estado=_texto(o.get("state")),
        mudo=_sim_ou_nao(o.get("mute")),
        canais=_canais(o.get("volume")),
        balanco=_balanco(o.get("balance")),
        propriedades=props,
        descricao_nula=nula,
        perdidos=_perdidos(o.get("properties")),
    )


@dataclass(frozen=True)
class NosDoGrafo:
    """As propriedades de texto dos nós do ``pw-dump``, pelo serial, pelo id e pelo nome."""

    por_serial: Mapping[str, Mapping[str, str]]
    por_id: Mapping[str, Mapping[str, str]]
    por_nome: Mapping[str, Mapping[str, str]]


def nos_do_grafo(texto: str | None) -> NosDoGrafo | None:
    """Os nós do ``pw-dump``, ou ``None`` («não sei»: o texto não é JSON). Função pura.

    O serial, que o grafo dá como número, vira texto como no ``pactl``.
    """
    objetos = lista_do_json(texto)
    if objetos is None:
        return None
    por_serial: dict[str, dict[str, str]] = {}
    por_id: dict[str, dict[str, str]] = {}
    por_nome: dict[str, dict[str, str]] = {}
    for o in objetos:
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        info = o.get("info")
        bruto = info.get("props") if isinstance(info, dict) else None
        if not isinstance(bruto, dict):
            continue
        props = {str(k): str(v) for k, v in bruto.items()
                 if isinstance(v, (str, int)) and not isinstance(v, bool)}
        if props.get("object.serial"):
            por_serial[props["object.serial"]] = props
        ident = _inteiro(o.get("id"))
        if ident is not None:
            por_id[str(ident)] = props
        nome = _texto(props.get("node.name"))
        if nome:
            por_nome[nome] = props
    return NosDoGrafo(por_serial, por_id, por_nome)


def ler_o_grafo() -> str | None:
    """O texto do ``pw-dump``, pelo leitor do retrato (que cala na suíte), ou ``None``."""
    from hefesto_dualsense4unix.integrations import retrato_do_som

    return retrato_do_som.ler_o_pw_dump()


def _perdeu_algo(o: Mapping[str, Any]) -> bool:
    """O ``pactl`` perdeu algum texto deste objeto, e ele ainda não foi ao grafo?"""
    if CHAVE_DO_GRAFO in o:
        return False
    props = o.get("properties")
    return (o.get("name") == NULO_DO_PACTL or o.get("description") == NULO_DO_PACTL
            or (isinstance(props, Mapping) and NULO_DO_PACTL in props.values()))


def _o_mesmo_no(o: Mapping[str, Any], nos: NosDoGrafo) -> Mapping[str, str] | None:
    """O nó do grafo que É este objeto do ``pactl``, ou ``None``.

    A identidade decide: o ``object.serial`` (o índice do ``pipewire-pulse``), e sem
    ele o ``object.id``; sem os dois, o índice como serial. O nome só casa nó (que
    tem ``name``) sem identidade nenhuma, e só nome inteiro. Nome inteiro dos dois
    lados que não bate desfaz o par: nome vazio nunca casa.
    """
    props = _propriedades(o.get("properties"))
    serial, ident = props.get("object.serial", ""), props.get("object.id", "")
    nome = props.get("node.name", "") or _texto(o.get("name"))
    if serial or ident:
        achado = nos.por_serial.get(serial) if serial else nos.por_id.get(ident)
    else:
        indice = _inteiro(o.get("index"))
        achado = None if indice is None else nos.por_serial.get(str(indice))
        if achado is None and "name" in o:
            achado = nos.por_nome.get(nome)
    if achado is None:
        return None
    do_grafo = _texto(achado.get("node.name"))
    if nome and do_grafo and nome != do_grafo:
        return None
    return achado


def _completo(o: Mapping[str, Any], nos: NosDoGrafo) -> dict[str, Any]:
    """O objeto com o texto perdido devolvido pelo grafo, e marcado como conferido.

    O monitor de uma saída (``device.class=monitor``) é o MESMO nó do grafo, com o
    serial dela, mas o nome e a descrição dele são do ``pipewire-pulse``
    («….monitor», «Monitor of …»): dele só as propriedades vêm do nó, e o nome e a
    descrição perdidos seguem perdidos, nunca os da saída.
    """
    novo = {**o, CHAVE_DO_GRAFO: "lido"}
    achado = _o_mesmo_no(o, nos)
    if achado is None:
        return novo
    bruto = o.get("properties")
    if isinstance(bruto, Mapping):
        novo["properties"] = {
            k: (achado.get(str(k)) or v) if v == NULO_DO_PACTL else v
            for k, v in bruto.items()}
    if _propriedades(bruto).get("device.class") == "monitor":
        return novo
    for campo, chave in (("name", "node.name"), ("description", "node.description")):
        if o.get(campo) == NULO_DO_PACTL and achado.get(chave):
            novo[campo] = achado[chave]
    return novo


def completar_o_json(texto: str | None, grafo: Grafo | None = None) -> str | None:
    """O JSON de um ``pactl --format=json list`` com o texto perdido vindo do grafo.

    O dono único do completar: ``(null)`` é o texto que o ``pactl`` 16.1 não soube
    escrever (™, acento, japonês), e o ``pw-dump`` (``grafo``, por padrão
    :func:`ler_o_grafo`) o tem inteiro; o par é pela identidade (:func:`_o_mesmo_no`).
    O grafo é lido UMA vez, só se algum objeto perdeu texto. Sem grafo, o campo
    segue perdido; o que o grafo não tem (o ``module-stream-restore.id``) também, e o
    objeto sai marcado (:data:`CHAVE_DO_GRAFO`). Idempotente.
    """
    if texto is None or f'"{NULO_DO_PACTL}"' not in texto:
        return texto
    objetos = lista_do_json(texto)
    if objetos is None or not any(_perdeu_algo(o) for o in objetos):
        return texto
    nos = nos_do_grafo((grafo or ler_o_grafo)())
    if nos is None:
        return texto
    return json.dumps([_completo(o, nos) if _perdeu_algo(o) else o for o in objetos],
                      ensure_ascii=False)


def _fluxo_do_json(o: Mapping[str, Any]) -> Fluxo | None:
    indice = _inteiro(o.get("index"))
    if indice is None:
        return None
    alvo = o.get("sink") if "sink" in o else o.get("source")
    return Fluxo(
        indice=indice,
        alvo="" if alvo is None else str(alvo),
        cliente=_texto(o.get("client")),
        driver=_texto(o.get("driver")),
        formato=_texto(o.get("sample_specification")),
        corked=_sim_ou_nao(o.get("corked")),
        mudo=_sim_ou_nao(o.get("mute")),
        propriedades=_propriedades(o.get("properties")),
        perdidos=_perdidos(o.get("properties")),
    )


def _colunas(texto: str) -> Iterable[list[str]]:
    for linha in texto.splitlines():
        colunas = linha.split("\t")
        if len(colunas) >= 2 and colunas[0].strip().isdigit():
            yield colunas


def nos_do_texto(texto: str) -> tuple[NoDeSom, ...]:
    """Os nós de um ``list sinks|sources``: JSON, ou o curto quando é o que se tem. Pura."""
    if texto.lstrip().startswith("["):
        lista = lista_do_json(texto) or []
        return tuple(n for n in (_no_do_json(o) for o in lista) if n is not None)
    return tuple(
        NoDeSom(
            indice=int(c[0]), nome=c[1].strip(),
            driver=c[2].strip() if len(c) > 2 else "",
            formato=c[3].strip() if len(c) > 3 else "",
            estado=c[4].strip() if len(c) > 4 else "")
        for c in _colunas(texto))


def fluxos_do_texto(texto: str) -> tuple[Fluxo, ...]:
    """Os fluxos de um ``list sink-inputs|source-outputs``: JSON, ou o curto. Pura."""
    if texto.lstrip().startswith("["):
        lista = lista_do_json(texto) or []
        return tuple(f for f in (_fluxo_do_json(o) for o in lista) if f is not None)
    return tuple(
        Fluxo(
            indice=int(c[0]), alvo=c[1].strip(),
            cliente="" if len(c) < 3 or c[2].strip() in ("-", "n/a") else c[2].strip(),
            driver=c[3].strip() if len(c) > 3 else "",
            formato=c[4].strip() if len(c) > 4 else "")
        for c in _colunas(texto))


def ler_a_lista(tipo: str, ler: Leitor, grafo: Grafo | None = None) -> str | None:
    """O JSON da lista de um tipo, já completo pelo grafo (:func:`completar_o_json`)."""
    if tipo not in (*TIPOS_DE_NO, *TIPOS_DE_FLUXO):
        raise ValueError(tipo)
    return completar_o_json(ler(argv_da_lista(tipo)), grafo)


def ler_nos(tipo: str, ler: Leitor, grafo: Grafo | None = None) -> tuple[NoDeSom, ...] | None:
    """Os nós de ``sinks`` ou ``sources``, ou ``None`` («não sei», ou sem a porta do JSON)."""
    if tipo not in TIPOS_DE_NO:
        raise ValueError(tipo)
    lista = lista_do_json(ler_a_lista(tipo, ler, grafo))
    if lista is None:
        return None
    return tuple(n for n in (_no_do_json(o) for o in lista) if n is not None)


def ler_fluxos(tipo: str, ler: Leitor, grafo: Grafo | None = None) -> tuple[Fluxo, ...] | None:
    """Os fluxos de ``sink-inputs`` ou ``source-outputs``, ou ``None`` («não sei»)."""
    if tipo not in TIPOS_DE_FLUXO:
        raise ValueError(tipo)
    lista = lista_do_json(ler_a_lista(tipo, ler, grafo))
    if lista is None:
        return None
    return tuple(f for f in (_fluxo_do_json(o) for o in lista) if f is not None)


def sysfs_por_no(tipo: str, ler: Leitor) -> dict[str, str] | None:
    """``{nome do nó: sysfs.path}`` de ``sinks`` ou ``sources``; ``None`` = não sei.

    Nó sem ``sysfs.path`` entra com ``""``: é o caso de todo nó virtual (a ponte de
    microfone, o endpoint), e «não tem dispositivo USB» é um fato usado para
    decidir, não uma ausência de dado.
    """
    nos = ler_nos(tipo, ler)
    if nos is None:
        return None
    return {n.nome: n.propriedades.get("sysfs.path", "") for n in nos if n.nome}


def placa_de_cada_fonte(ler: Leitor) -> dict[str, str] | None:
    """``{nome do nó: placa ALSA}`` das fontes que têm placa; ``None`` = não sei."""
    nos = ler_nos("sources", ler)
    if nos is None:
        return None
    return {n.nome: n.propriedades["alsa.card"]
            for n in nos if n.nome and n.propriedades.get("alsa.card")}


def volumes_do_no(tipo: str, nome: str, ler: Leitor) -> list[int] | None:
    """O por cento de cada canal deste nó; ``None`` = o nó não veio, ou não se sabe."""
    nos = ler_nos(tipo, ler)
    if nos is None:
        return None
    for no in nos:
        if nome and no.nome == nome:
            return no.porcentos or None
    return None


# ---------------------------------------------------------------------------
# O diretório dos módulos do PipeWire

AMBIENTE_DO_DIRETORIO: Final[str] = "PIPEWIRE_MODULE_DIR"

_BIBLIOTECA_DO_PIPEWIRE: Final[re.Pattern[str]] = re.compile(
    r"^\s*libpipewire-(\d+(?:\.\d+)*)\.so\S*\s.*=>\s*(/\S+)$", re.M)

_TRAVA_DOS_DIRETORIOS = threading.Lock()
_DIRETORIOS_ACHADOS: list[str] | None = None


def _pergunta(argv: list[str]) -> str | None:
    exe = shutil.which(argv[0])
    if exe is None and argv[0] == "ldconfig" and Path("/sbin/ldconfig").exists():
        exe = "/sbin/ldconfig"
    if exe is None:
        return None
    try:
        proc = subprocess.run(
            [exe, *argv[1:]], capture_output=True, text=True, check=False,
            timeout=PRAZO_DA_PERGUNTA_S, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError) as erro:
        logger.debug("pergunta_do_sistema_falhou", comando=argv[0], erro=type(erro).__name__)
        return None
    return proc.stdout if proc.returncode == 0 else None


def diretorios_de_modulos(
    perguntar: Callable[[list[str]], str | None] | None = None,
    ambiente: Mapping[str, str] | None = None,
) -> list[str]:
    """As pastas onde o PipeWire guarda os módulos, na ordem de confiança. Pode ser vazia.

    Sem ``perguntar`` nem ``ambiente`` (o uso do produto) a resposta é lembrada por
    processo: a pasta não muda enquanto o programa roda. Com eles (as réguas), nada
    é lembrado.
    """
    global _DIRETORIOS_ACHADOS
    do_produto = perguntar is None and ambiente is None
    if do_produto:
        with _TRAVA_DOS_DIRETORIOS:
            if _DIRETORIOS_ACHADOS is not None:
                return list(_DIRETORIOS_ACHADOS)
    pergunta = perguntar or _pergunta
    env = os.environ if ambiente is None else ambiente
    achados: list[str] = []

    def _anota(pasta: str) -> None:
        pasta = pasta.strip()
        if pasta and pasta not in achados:
            achados.append(pasta)

    for pasta in (env.get(AMBIENTE_DO_DIRETORIO, "")).split(os.pathsep):
        _anota(pasta)
    _anota(pergunta(["pkg-config", "--variable=moduledir", "libpipewire-0.3"]) or "")
    if not achados:
        for versao, caminho in _BIBLIOTECA_DO_PIPEWIRE.findall(
                pergunta(["ldconfig", "-p"]) or ""):
            _anota(str(Path(caminho).parent / f"pipewire-{versao}"))
    if do_produto:
        with _TRAVA_DOS_DIRETORIOS:
            _DIRETORIOS_ACHADOS = list(achados)
    return achados


def tem_modulo(arquivo: str, diretorios: Iterable[str] | None = None) -> bool:
    """O arquivo ``libpipewire-module-*.so`` existe em alguma das pastas dos módulos?"""
    return any(Path(d).joinpath(arquivo).exists()
               for d in (diretorios if diretorios is not None else diretorios_de_modulos()))


__all__ = [
    "AMBIENTE_DO_DIRETORIO",
    "CHAVE_DO_GRAFO",
    "FORMATO_JSON",
    "NULO_DO_PACTL",
    "Canal",
    "Fluxo",
    "Grafo",
    "NoDeSom",
    "NosDoGrafo",
    "argv_da_lista",
    "argv_do_curto",
    "completar_o_json",
    "diretorios_de_modulos",
    "fluxos_do_texto",
    "ler_a_lista",
    "ler_fluxos",
    "ler_nos",
    "ler_o_grafo",
    "lista_do_json",
    "nos_do_grafo",
    "nos_do_texto",
    "placa_de_cada_fonte",
    "sem_o_formato",
    "sysfs_por_no",
    "tem_modulo",
    "volumes_do_no",
]
