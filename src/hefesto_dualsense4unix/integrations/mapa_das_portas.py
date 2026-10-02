"""mapa_das_portas.py — o número que ELA escreveu no gabinete, e o que ele responde."""

from __future__ import annotations

import itertools
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    VELOCIDADE_SUPERSPEED_MBPS,
)
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    caminho_da_porta,
    caminhos_da_porta,
)

_ARQUIVO_DO_SERIAL = "serial"

@dataclass(frozen=True)
class Resumo:
    """Os três números da linha-resumo de "Conexões" — nada de texto."""

    faces: int = 0
    entradas: int = 0
    colocados: int = 0

    @property
    def vazio(self) -> bool:
        """Ninguém desenhou nada — e este é o estado legítimo mais comum."""
        return self.faces == 0 and self.entradas == 0


def controladores_do_censo(censo: Censo) -> dict[int, str]:
    """``{busnum: controlador PCI}`` pelos hubs-raiz do censo que já está na mão."""
    return {
        aparelho.busnum: aparelho.controlador_pci
        for aparelho in censo.aparelhos
        if aparelho.e_raiz and aparelho.controlador_pci
    }


def porta_de(
    mapa: MapaDaMesa, caminho: str, controladores: Mapping[int, str] | None = None
) -> str | None:
    """O número da entrada em que este caminho de barramento está."""
    if not caminho:
        return None
    for numero, porta in sorted(mapa.portas.items()):
        if caminho_da_porta(porta, controladores) == caminho:
            return numero
    for numero, porta in sorted(mapa.portas.items()):
        if caminho in caminhos_da_porta(porta, controladores):
            return numero
    return None


def caminho_de(
    mapa: MapaDaMesa, porta: str, controladores: Mapping[int, str] | None = None
) -> str | None:
    """O caminho do lado 2.0 desta entrada, ou ``None`` — calculado, nunca guardado."""
    declarada = mapa.portas.get(porta)
    if declarada is None:
        return None
    return caminho_da_porta(declarada, controladores) or None


def filhas_de(mapa: MapaDaMesa, porta: str) -> tuple[str, ...]:
    """As entradas que nascem de uma extensão plugada NESTA entrada."""
    return tuple(
        sorted(
            numero
            for numero, declarada in mapa.portas.items()
            if declarada.filha_de == porta and numero != porta
        )
    )


def irmas_de(mapa: MapaDaMesa) -> dict[str, str]:
    """A irmã FIXA de cada entrada — **inclusive da vazia**."""
    achadas: dict[str, str] = {}
    vistos: set[str] = set()
    for face in mapa.faces:
        numeros: list[str] = []
        for numero in face.portas:
            if numero in vistos:
                continue
            vistos.add(numero)
            numeros.append(numero)
        for primeira, segunda in zip(numeros[0::2], numeros[1::2], strict=False):
            achadas[primeira] = segunda
            achadas[segunda] = primeira
    return achadas


def resumo_do_mapa(mapa: MapaDaMesa, censo: Censo) -> Resumo:
    """Quantas faces, quantas entradas e quantos aparelhos colocados."""
    entradas = {numero for face in mapa.faces for numero in face.portas}
    presentes = _caminhos_do_censo(censo)
    controladores = controladores_do_censo(censo)
    colocados = sum(
        1
        for declarada in mapa.portas.values()
        if caminho_da_porta(declarada, controladores) in presentes
    )
    return Resumo(faces=len(mapa.faces), entradas=len(entradas), colocados=colocados)


def portas_livres(mapa: MapaDaMesa, censo: Censo) -> tuple[str, ...]:
    """As entradas da fileira que estão VAZIAS agora, na ordem do desenho."""
    presentes = _caminhos_do_censo(censo)
    controladores = controladores_do_censo(censo)
    livres: list[str] = []
    for numero in _entradas_da_fileira(mapa):
        if filhas_de(mapa, numero):
            continue
        if _caminho_presente(mapa, numero, presentes, controladores):
            continue
        livres.append(numero)
    return tuple(livres)


def ocupante_de(mapa: MapaDaMesa, numero: str, censo: Censo) -> str:
    """O caminho do aparelho que está NESTA entrada agora, ou o declarado."""
    controladores = controladores_do_censo(censo)
    return (_caminho_presente(mapa, numero, _caminhos_do_censo(censo), controladores)
            or caminho_de(mapa, numero, controladores) or "")


def _caminho_presente(
    mapa: MapaDaMesa,
    numero: str,
    presentes: frozenset[str],
    controladores: Mapping[int, str] | None = None,
) -> str:
    """O caminho, dos dois lados do buraco, em que há aparelho agora — ``""`` se nenhum."""
    porta = mapa.portas.get(numero)
    if porta is None:
        return ""
    for caminho in caminhos_da_porta(porta, controladores):
        if caminho in presentes:
            return caminho
    return ""


def vizinhas_de_verdade(
    mapa: MapaDaMesa, censo: Censo
) -> tuple[tuple[str, str], ...]:
    """Os pares de entradas OCUPADAS que estão coladas no metal."""
    presentes = _caminhos_do_censo(censo)
    controladores = controladores_do_censo(censo)

    def ocupada(numero: str) -> bool:
        return bool(_caminho_presente(mapa, numero, presentes, controladores))

    pares: list[tuple[str, str]] = []
    vistos: set[tuple[str, str]] = set()
    for face in mapa.faces:
        for primeira, segunda in itertools.pairwise(face.portas):
            if not (ocupada(primeira) and ocupada(segunda)):
                continue
            if (primeira, segunda) in vistos:
                continue
            vistos.add((primeira, segunda))
            pares.append((primeira, segunda))
    for numero in _entradas_da_fileira(mapa):
        irmas = [filha for filha in filhas_de(mapa, numero) if ocupada(filha)]
        for primeira, segunda in itertools.pairwise(irmas):
            if (primeira, segunda) in vistos:
                continue
            vistos.add((primeira, segunda))
            pares.append((primeira, segunda))
    return tuple(pares)


LACUNA_PAR = "par"
LACUNA_POSICAO = "posicao"  # noqa-acento: chave de contrato ASCII, não texto de tela
LACUNA_VELOCIDADE = "velocidade"
LACUNA_REGIAO = "regiao"  # noqa-acento: chave de contrato ASCII, não texto de tela
LACUNA_ESPECIE = "especie"  # noqa-acento: chave de contrato ASCII, não texto de tela

_CLASSE_DO_MOTOR_POR_TRIPLA: dict[tuple[str, str, str], str] = {
    ("e0", "01", "01"): "bt",
    ("03", "01", "01"): "teclado",
    ("03", "01", "02"): "mouse",
}

_CLASSE_DE_VIDEO = "0e"

_SUFIXO_DO_NO = "-port"


@dataclass(frozen=True)
class Bancada:
    """A mesa do motor **e** o que o desenho não disse para montá-la."""

    mesa: motor.Mesa
    lacunas: tuple[str, ...] = ()
    usb_de: Mapping[str, str] = field(default_factory=dict)


def mesa_do_motor(mapa: MapaDaMesa, censo: Censo) -> Bancada:
    """O desenho dela mais a leitura de agora, na forma que o motor entende."""
    controladores = controladores_do_censo(censo)
    leitura, fora = _leitura_pelas_entradas(mapa, censo.conectados(), controladores)
    aparelhos = tuple(
        _aparelho_do_motor(a) for a in censo.conectados() if a.nome_do_kernel not in fora
    )
    leitura = {aparelho.id: leitura[aparelho.id] for aparelho in aparelhos}
    declarado = {
        numero: caminho
        for numero, porta in sorted(mapa.portas.items())
        if (caminho := caminho_da_porta(porta, controladores))
    }

    esboco = motor.Mesa(
        aparelhos=aparelhos, faces=(), mapa=declarado, leitura=leitura
    )
    caminho_hub = motor.caminho_do_hub(esboco)

    pares = irmas_de(mapa)
    velocidades = _velocidade_por_hub(censo)
    aparelhos_medidos = velocidades_dos_aparelhos(censo)
    lacunas: set[str] = set()
    origens: dict[str, str] = {}
    if any(not aparelho.classe for aparelho in aparelhos):
        lacunas.add(LACUNA_ESPECIE)
    if mapa.faces:
        # NÃO é condicional, e por isso não olha entrada nenhuma: `Entrada.pos`
        # é a posição do buraco na fileira do metal, e ela não existe em fonte
        # alguma — nem no `MapaDaMesa`, nem no censo, nem no `/sys`. Sem ela o
        # `_bonus_separacao` (+6 por posição de folga, teto 6) nunca dispara, e
        # dois adaptadores de rádio nas pontas opostas da fileira do hub
        # recebem o mesmo juízo de dois colados.
        lacunas.add(LACUNA_POSICAO)

    faces: list[motor.Face] = []
    for face in mapa.faces:
        numeros = _entradas_da_fileira_da_face(mapa, face.portas)
        regioes: dict[str, str | None] = {}
        for numero in _entradas_da_face(mapa, numeros):
            regioes[numero] = motor.regiao_do_caminho(
                declarado.get(numero), caminho_hub
            )
        conhecidas = [regiao for regiao in regioes.values() if regiao]
        if not conhecidas:
            lacunas.add(LACUNA_REGIAO)
        regiao_da_face = (
            "hub" if conhecidas.count("hub") > conhecidas.count("pc") else "pc"
        )
        entradas: list[motor.Entrada] = []
        for numero in numeros:
            entrada = _entrada_do_motor(
                mapa,
                numero,
                pares=pares,
                regiao=regioes.get(numero) or regiao_da_face,
                velocidades=velocidades,
                aparelhos=aparelhos_medidos,
                lacunas=lacunas,
                origens=origens,
            )
            filhas = filhas_de(mapa, numero)
            if filhas:
                filho = _entrada_do_motor(
                    mapa,
                    filhas[0],
                    pares=pares,
                    regiao=regioes.get(filhas[0]) or regiao_da_face,
                    velocidades=velocidades,
                    aparelhos=aparelhos_medidos,
                    lacunas=lacunas,
                    esticada=True,
                    usb_de_quem_hospeda=entrada.usb,
                    origens=origens,
                    origem_de_quem_hospeda=origens.get(numero, ""),
                )
                entrada = replace(entrada, filho=filho)
            entradas.append(entrada)
        faces.append(
            motor.Face(
                nome=face.nome,
                regiao=regiao_da_face,
                entradas=tuple(entradas),
                perto=face.perto,
                alto=face.alto,
            )
        )

    return Bancada(
        mesa=motor.Mesa(
            aparelhos=aparelhos,
            faces=tuple(faces),
            mapa=declarado,
            leitura=leitura,
        ),
        lacunas=tuple(sorted(lacunas)),
        usb_de=origens,
    )


def _leitura_pelas_entradas(
    mapa: MapaDaMesa,
    conectados: Sequence[Aparelho],
    controladores: Mapping[int, str] | None = None,
) -> tuple[dict[str, str], frozenset[str]]:
    """``(aparelho -> caminho em que o mapa o lê, os hubs que não são aparelho)``."""
    da_entrada: dict[str, str] = {}
    anfitrioes: set[str] = set()
    for _numero, porta in sorted(mapa.portas.items()):
        principal = caminho_da_porta(porta, controladores)
        for no in porta.nos:
            anfitrioes.add(no.rpartition(_SUFIXO_DO_NO)[0])
        for caminho in caminhos_da_porta(porta, controladores):
            if principal:
                da_entrada.setdefault(caminho, principal)
    leitura: dict[str, str] = {}
    fora: set[str] = set()
    lidos_de_hub: set[str] = set()
    for aparelho in sorted(conectados, key=lambda a: a.nome_do_kernel not in da_entrada.values()):
        nome = aparelho.nome_do_kernel
        caminho = da_entrada.get(nome, nome)
        leitura[nome] = caminho
        if not aparelho.e_hub:
            continue
        if (nome not in da_entrada and nome in anfitrioes) or caminho in lidos_de_hub:
            fora.add(nome)
        else:
            lidos_de_hub.add(caminho)
    return leitura, frozenset(fora)


def _aparelho_do_motor(aparelho: Aparelho) -> motor.Aparelho:
    """Um aparelho do censo na forma do motor — sem inventar o que falta."""
    return motor.Aparelho(
        id=aparelho.nome_do_kernel,
        tipo=aparelho.especie,
        nome=aparelho.produto.strip() or aparelho.especie,
        classe=_classe_do_motor(aparelho),
    )


def _classe_do_motor(aparelho: Aparelho) -> str:
    """A classe que o motor julga, ou ``""`` quando o kernel não disse.

    ``""`` é resposta, e é a resposta certa para o Archer T3U (``ff/ff/ff``) e
    para o DualSense por cabo (``03/00/00``, HID sem protocolo de arranque):
    nenhuma regra do motor fala deles, e forçá-los numa classe faria o quadrado
    julgar pelo aparelho errado.
    """
    if aparelho.e_hub:
        return "hub"
    achada = _CLASSE_DO_MOTOR_POR_TRIPLA.get(
        (aparelho.classe, aparelho.subclasse, aparelho.protocolo)
    )
    if achada:
        return achada
    return "webcam" if aparelho.classe == _CLASSE_DE_VIDEO else ""


def _entrada_do_motor(
    mapa: MapaDaMesa,
    numero: str,
    *,
    pares: Mapping[str, str],
    regiao: str,
    velocidades: Mapping[str, float],
    lacunas: set[str],
    aparelhos: Mapping[str, float] | None = None,
    esticada: bool = False,
    filho: motor.Entrada | None = None,
    usb_de_quem_hospeda: int | None = None,
    origens: dict[str, str] | None = None,
    origem_de_quem_hospeda: str = "",
) -> motor.Entrada:
    """Uma entrada do desenho na forma do motor, anotando o que faltou."""
    par = pares.get(numero)
    if par is None and not esticada:
        lacunas.add(LACUNA_PAR)
    declarada = mapa.portas.get(numero)
    rapido, origem = _velocidade_do_no(
        () if declarada is None else declarada.nos,
        velocidades,
        None if declarada is None else declarada.usb,
        aparelhos,
    )
    if rapido is None and usb_de_quem_hospeda is not None:
        rapido, origem = usb_de_quem_hospeda == 3, origem_de_quem_hospeda
    if rapido is None:
        lacunas.add(LACUNA_VELOCIDADE)
    if origens is not None:
        origens[numero] = origem
    return motor.Entrada(
        n=numero,
        usb=3 if rapido else 2,
        onde="hub" if regiao == "hub" else "pc",
        par=par,
        pos=None,
        esticada=esticada,
        filho=filho,
    )


def _entradas_da_fileira_da_face(
    mapa: MapaDaMesa, numeros: Sequence[str]
) -> tuple[str, ...]:
    """Os números da fileira desta face, sem repetir — a regra de ``irmas_de``."""
    achados: list[str] = []
    vistos: set[str] = set()
    for numero in numeros:
        if numero in vistos:
            continue
        vistos.add(numero)
        achados.append(numero)
    return tuple(achados)


def _velocidade_por_hub(censo: Censo) -> dict[str, float]:
    """``hub -> Mbps``, para os hubs-raiz e para os hubs da mesa."""
    achadas = {
        barramento.nome_do_kernel: barramento.velocidade_mbps
        for barramento in censo.barramentos
    }
    for aparelho in censo.aparelhos:
        if aparelho.e_hub:
            achadas[aparelho.nome_do_kernel] = aparelho.velocidade_mbps
    return achadas


def _rapido_do_no(
    nos: Sequence[str],
    velocidades: Mapping[str, float],
    declarada: int | None = None,
    aparelhos: Mapping[str, float] | None = None,
) -> bool | None:
    """O buraco declarado alcança SuperSpeed? ``None`` = não deu para saber."""
    return _velocidade_do_no(nos, velocidades, declarada, aparelhos)[0]


def _velocidade_do_no(
    nos: Sequence[str],
    velocidades: Mapping[str, float],
    declarada: int | None = None,
    aparelhos: Mapping[str, float] | None = None,
) -> tuple[bool | None, str]:
    """:func:`_rapido_do_no` com a origem: ``(é USB 3?, de onde veio)``."""
    lidas = [
        velocidades[hub]
        for hub in (no.rpartition(_SUFIXO_DO_NO)[0] for no in nos)
        if hub in velocidades
    ]
    placa: bool | None
    if not lidas or all(valor <= 0 for valor in lidas):
        placa = None
    else:
        placa = any(valor >= VELOCIDADE_SUPERSPEED_MBPS for valor in lidas)
    return velocidade_da_entrada(
        placa, declarada, _aparelho_usb3_nos_nos(nos, aparelhos or {})
    )


USB_PELO_APARELHO = "aparelho"
USB_DECLARADA = "declarada"
USB_PELA_PLACA = "placa"


def velocidade_da_entrada(
    placa: bool | None, declarada: int | None, aparelho_usb3: bool = False
) -> tuple[bool | None, str]:
    """``(é USB 3?, de onde veio)`` — o dono ÚNICO da precedência."""
    if aparelho_usb3:
        return True, USB_PELO_APARELHO
    if declarada in (2, 3):
        return declarada == 3, USB_DECLARADA
    return placa, (USB_PELA_PLACA if placa is not None else "")


def velocidades_dos_aparelhos(censo: Censo) -> dict[str, float]:
    """``nome do kernel -> Mbps`` de tudo que enumerou — o lado de :func:`velocidade_da_entrada`"""
    return {a.nome_do_kernel: a.velocidade_mbps for a in censo.conectados()}


def _aparelho_usb3_nos_nos(nos: Sequence[str], aparelhos: Mapping[str, float]) -> bool:
    """Algum aparelho encaixado num destes nós enumerou a 5000M ou mais?"""
    from hefesto_dualsense4unix.utils.lugar import caminho_do_no

    return any(
        aparelhos.get(caminho_do_no(no), 0.0) >= VELOCIDADE_SUPERSPEED_MBPS for no in nos
    )


def aparelho_usb3_na_entrada(nos: Sequence[str], censo: Censo) -> bool:
    """O lado «aparelho» de :func:`velocidade_da_entrada`, pelos NÓS da entrada."""
    return _aparelho_usb3_nos_nos(nos, velocidades_dos_aparelhos(censo))


def _caminhos_do_censo(censo: Censo) -> frozenset[str]:
    """Os ``nome_do_kernel`` de tudo que está plugado agora, sem os hubs-raiz."""
    return frozenset(a.nome_do_kernel for a in censo.conectados())


def _entradas_da_fileira(mapa: MapaDaMesa) -> tuple[str, ...]:
    """Os números das faces, na ordem do desenho e sem repetir."""
    achados: list[str] = []
    vistos: set[str] = set()
    for face in mapa.faces:
        for numero in face.portas:
            if numero in vistos:
                continue
            vistos.add(numero)
            achados.append(numero)
    return tuple(achados)


def _entradas_da_face(mapa: MapaDaMesa, numeros: Sequence[str]) -> tuple[str, ...]:
    """As entradas de uma face MAIS as que nascem de extensão nelas."""
    achadas: list[str] = []
    for numero in numeros:
        achadas.append(numero)
        achadas.extend(filhas_de(mapa, numero))
    return tuple(achadas)


# ---------------------------------------------------------------------------
# O QUE O METAL DE UMA PORTA É — A-08-UM-MAPEAR-SO-01 (25/09/2026)
# ---------------------------------------------------------------------------
#

USB_3 = "3.0"
USB_2 = "2.0"

BLUETOOTH_DA_PLACA = "placa"
BLUETOOTH_DONGLE = "dongle"

_TRIPLA_DO_BLUETOOTH = ("e0", "01", "01")

_ENCAIXE_INTERNO = "hardwired"
_ENCAIXE_DE_FORA = "hotplug"


@dataclass(frozen=True)
class FatosDoBuraco:
    """O que o ``/sys`` diz de UM buraco, cheio ou vazio — nada declarado."""

    usb: str = ""
    controlador: str = ""
    hub: str = ""
    hub_produto: str = ""
    encaixe: str = ""
    ocupada: bool | None = None
    aparelho: str = ""
    especie: str = ""
    produto: str = ""
    e_dualsense: bool = False
    e_bluetooth: bool = False
    bluetooth: str = ""
    storm: int | None = None


def fatos_do_buraco(
    nos: Sequence[str],
    entradas: Sequence[object],
    censo: Censo,
    controladores: Mapping[int, str],
    *,
    storm: Mapping[str, int] | None = None,
) -> FatosDoBuraco:
    """Os fatos medidos de um buraco — pelos NÓS dele, que existem vazios."""
    from hefesto_dualsense4unix.utils.lugar import caminho_do_no

    meus = [e for e in entradas if getattr(e, "no", "") in set(nos)]
    velocidades = [float(getattr(e, "velocidade_mbps", 0.0) or 0.0) for e in meus]
    if any(v >= VELOCIDADE_SUPERSPEED_MBPS for v in velocidades):
        usb = USB_3
    elif velocidades and not all(v <= 0 for v in velocidades):
        usb = USB_2
    else:
        usb = ""

    # O lado 2.0 primeiro: é onde o DualSense e os dongles enumeram.
    ordenados = sorted(
        (no for no in nos if caminho_do_no(no)),
        key=lambda no: int(caminho_do_no(no).partition("-")[0]),
    )
    controlador = ""
    hub = ""
    for no in ordenados:
        busnum = int(caminho_do_no(no).partition("-")[0])
        controlador = controlador or controladores.get(busnum, "")
        dono = no.rpartition(_SUFIXO_DO_NO)[0]
        if dono and not dono.startswith("usb") and not hub:
            hub = dono
    por_nome = {a.nome_do_kernel: a for a in censo.aparelhos}
    hub_produto = por_nome[hub].produto.strip() if hub in por_nome else ""

    estados = [str(getattr(e, "estado", "") or "") for e in meus]
    dentro = next((str(getattr(e, "aparelho", "")) for e in meus if getattr(e, "aparelho", "")), "")
    if dentro:
        ocupada: bool | None = True
    elif meus and all(estado == "not attached" for estado in estados):
        ocupada = False
    else:
        ocupada = None
    encaixe = next((str(getattr(e, "tipo_de_encaixe", "")) for e in meus
                    if getattr(e, "tipo_de_encaixe", "")), "")

    aparelho = por_nome.get(dentro)
    e_bluetooth = aparelho is not None and (
        aparelho.classe, aparelho.subclasse, aparelho.protocolo
    ) == _TRIPLA_DO_BLUETOOTH
    bluetooth = _origem_do_bluetooth(nos, entradas) if e_bluetooth else ""

    medido: int | None = None
    caminhos = {caminho_do_no(no) for no in nos} | ({dentro} if dentro else set())
    caminhos.discard("")
    if storm is not None and caminhos:
        medido = sum(storm.get(caminho, 0) for caminho in caminhos)

    return FatosDoBuraco(
        usb=usb,
        controlador=controlador,
        hub=hub,
        hub_produto=hub_produto,
        encaixe=encaixe,
        ocupada=ocupada,
        aparelho=dentro,
        especie="" if aparelho is None else aparelho.especie,
        produto="" if aparelho is None else aparelho.produto.strip(),
        e_dualsense=aparelho is not None and aparelho.vid.lower() == "054c",
        e_bluetooth=e_bluetooth,
        bluetooth=bluetooth,
        storm=medido,
    )


def _origem_do_bluetooth(nos: Sequence[str], entradas: Sequence[object]) -> str:
    """Placa, dongle ou ``""`` — pelo ``connect_type`` do buraco e de quem o hospeda."""
    por_no = {str(getattr(e, "no", "")): e for e in entradas}
    alvo = set(nos)
    vistos: set[str] = set()
    degraus = 0
    interno = False
    while alvo and not alvo <= vistos:
        vistos |= alvo
        tipos = {
            str(getattr(por_no[no], "tipo_de_encaixe", "") or "")
            for no in alvo
            if no in por_no
        }
        if _ENCAIXE_INTERNO in tipos:
            if not degraus:
                return BLUETOOTH_DA_PLACA
            interno = True
        if _ENCAIXE_DE_FORA in tipos:
            return BLUETOOTH_DONGLE
        hubs = {
            dono
            for no in alvo
            if (dono := no.rpartition(_SUFIXO_DO_NO)[0]) and not dono.startswith("usb")
        }
        if not hubs:
            break
        degraus += 1
        alvo = {
            no
            for no, e in por_no.items()
            if str(getattr(e, "aparelho", "") or "") in hubs
        }
        if not alvo:
            return ""
    return BLUETOOTH_DONGLE if degraus and not interno else ""


def _serial_do_no(no: str) -> str:
    """O ``serial`` de um nó USB; ``""`` em qualquer erro — sysfs some sob a mão."""
    try:
        with open(
            os.path.join(no, _ARQUIVO_DO_SERIAL), encoding="utf-8", errors="replace"
        ) as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def serial_do_no(no: str) -> str:
    """O ``serial`` de um nó USB, para a identidade do aparelho no mapa das conexões."""
    return _serial_do_no(no)


__all__ = [
    "BLUETOOTH_DA_PLACA",
    "BLUETOOTH_DONGLE",
    "LACUNA_ESPECIE",
    "LACUNA_PAR",
    "LACUNA_POSICAO",
    "LACUNA_REGIAO",
    "LACUNA_VELOCIDADE",
    "USB_2",
    "USB_3",
    "USB_DECLARADA",
    "USB_PELA_PLACA",
    "USB_PELO_APARELHO",
    "Bancada",
    "FatosDoBuraco",
    "Resumo",
    "aparelho_usb3_na_entrada",
    "caminho_de",
    "fatos_do_buraco",
    "filhas_de",
    "irmas_de",
    "mesa_do_motor",
    "porta_de",
    "portas_livres",
    "resumo_do_mapa",
    "serial_do_no",
    "velocidade_da_entrada",
    "velocidades_dos_aparelhos",
    "vizinhas_de_verdade",
]
