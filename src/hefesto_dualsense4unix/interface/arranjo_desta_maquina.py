#!/usr/bin/env python3
"""O arranjo do computador de QUEM ABRE, na forma que o `mapa-das-portas` desenha."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import secrets
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from hefesto_dualsense4unix.integrations import diario_do_usb
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    ESPECIE_DESCONHECIDA,
    HubFisico,
    cadeia_de_hubs,
    enlace_abaixo,
    hubs_fisicos,
)
from hefesto_dualsense4unix.interface import pagina_do_mapa

PAGINA = "mapa-das-portas.html"

QUANDO_DE_AGORA = "leitura deste computador · {quando}"

ROTULO_DE_AGORA = "lido agora"
ROTULO_DE_ANTES = "a leitura anterior — ainda é esta"
ROTULO_DA_ANTERIOR = "a leitura anterior"

CHAVE_DA_ENTREGA = "arranjo"

CHAVE_DEPOIS_DE_GRAVAR = "arranjoGravado"

COMO_ABRE = ""
COMO_REEXAME = "releitura"
COMO_GRAVOU = "gravou"

_SAL = secrets.token_bytes(16)
_PREFIXO_DO_ID = "ap-"

Lida = dict[str, tuple[str, str]]

_FILEIRA_DO_HUB = "fileira"
_COLUNA_CURTA = "coluna"
_GRADE = "grade-tras"

_TETO_DA_COLUNA = 2

CABO_DECLARADO = "Extensor, declarado por você"

ENTRADAS_DO_HUB_DECLARADO = 4


def arranjo(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
    *,
    antes: Mapping[str, tuple[str, str]] | None = None,
    ler_o_serial: Callable[[str], str] | None = None,
    ler_o_diario: Callable[[], list[dict[str, Any]]] | None = None,
    boot_id: Callable[[], str | None] | None = None,
) -> dict[str, Any] | None:
    """O arranjo desta máquina, ou ``None`` quando não há o que desenhar."""
    lido = _ler_a_maquina(agora, carregar, ler_o_barramento, antes=antes,
                          ler_o_serial=ler_o_serial, ler_o_diario=ler_o_diario, boot_id=boot_id)
    return None if lido is None else lido[0]


def _ler_a_maquina(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
    *,
    antes: Mapping[str, tuple[str, str]] | None = None,
    ler_o_serial: Callable[[str], str] | None = None,
    faixas: Callable[[], Mapping[str, Any]] | None = None,
    ler_o_diario: Callable[[], list[dict[str, Any]]] | None = None,
    boot_id: Callable[[], str | None] | None = None,
) -> tuple[dict[str, Any], Lida] | None:
    """O :func:`arranjo` e a :data:`Lida` dele, que o reexame seguinte confere."""
    try:
        from hefesto_dualsense4unix.integrations import mapa_das_portas
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento as _ler,
        )
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import (
            nome_da_entrada,
            rotulo_do_numero,
            rotulos_das_entradas,
        )
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina, entradas_do_mapa
    except Exception:
        return None

    try:
        documento = (carregar or carregar_maquina)()
        declarado = getattr(documento, "mapa", None)
        if declarado is None or not _ha_o_que_desenhar(declarado):
            return None
        censo = (ler_o_barramento or _ler)()
        tipos = mapa_das_portas.tipos_declarados(documento)
        bancada = mapa_das_portas.mesa_do_motor(declarado, censo, tipos)
        conectados = censo.conectados()
        ids = identidades(
            conectados, ler_o_serial or mapa_das_portas.serial_do_no, antes,
            lido_em=bancada.mesa.leitura)
        modelos = _modelos(conectados)
    except Exception:
        return None

    try:
        das_faixas = dict(faixas()) if faixas is not None else {}
    except Exception:
        das_faixas = {}
    mesa = bancada.mesa
    pelo_caminho = {a.nome_do_kernel: a for a in conectados}
    sem_lugar = _a_fileira_sem_lugar(declarado, censo, mapa_das_portas)
    if not mesa.faces and sem_lugar is None:
        return None

    quando = (agora or _dt.datetime.now()).strftime("%d/%m/%Y %Hh%M")
    caminhos = {ids.get(a.id, a.id): mesa.leitura.get(a.id, a.id) for a in mesa.aparelhos}
    faces = _faces(mesa.faces)
    hub_lido = _o_que_ela_declarou_nas_entradas(
        faces, declarado, lambda numero: nome_da_entrada(numero, maquina=documento))
    if sem_lugar is not None:
        faces.append(sem_lugar)
    _a_leitura_da_maquina(faces, declarado, censo, mapa_das_portas)
    anterior = (
        {"rotulo": ROTULO_DE_ANTES, "caminho": dict(caminhos)}
        if antes is None
        else {"rotulo": ROTULO_DA_ANTERIOR,
              "caminho": {i: caminho for i, (caminho, _m) in antes.items()}}
    )
    lida = {ids.get(a.id, a.id): (mesa.leitura.get(a.id, a.id), modelos.get(a.id, ""))
            for a in mesa.aparelhos}
    da_cadeia = _a_cadeia_usb(censo, {a.id: ids.get(a.id, a.id) for a in mesa.aparelhos})
    sumiram, registro = _o_diario_na_tela(
        ler_o_diario, boot_id, agora or _dt.datetime.now(), conectados,
        dict(mesa.mapa), _apelidos(documento), tipos,
        lambda numero: rotulo_do_numero(numero, maquina=documento) or SEM_ENTRADA_MARCADA)
    return {
        "quando": QUANDO_DE_AGORA.format(quando=quando),
        "aparelhos": [
            _aparelho(a, ids.get(a.id, a.id), pelo_caminho.get(a.id), tipos,
                      _apelidos(documento), censo, das_faixas,
                      da_cadeia.get(ids.get(a.id, a.id)))
            for a in mesa.aparelhos
        ],
        "faces": faces,
        "mapa": dict(mesa.mapa),
        "leituras": {
            "agora": {"rotulo": ROTULO_DE_AGORA, "caminho": caminhos},
            "antes": anterior,
        },
        "declarado": _declarado(
            declarado,
            entradas_do_mapa(declarado),
            lambda numero: nome_da_entrada(numero, maquina=documento),
        ),
        "rotulos": rotulos_das_entradas(documento),
        "hubLido": hub_lido,
        "usbDe": dict(bancada.usb_de),
        "sumiram": sumiram,
        "registro": registro,
    }, lida


class _ALeituraNaTela:
    """A :data:`Lida` da última leitura entregue à página."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._lida: Lida | None = None

    def ler(self) -> Lida | None:
        with self._trava:
            return None if self._lida is None else dict(self._lida)

    def guardar(self, lida: Mapping[str, tuple[str, str]]) -> None:
        copia = dict(lida)
        with self._trava:
            self._lida = copia


_NA_TELA = _ALeituraNaTela()


def para_a_pagina(**fontes: Any) -> dict[str, Any] | None:
    """A leitura que a página recebe ao abrir — e que vira o «antes» do reexame."""
    return _guardar_e_entregar(_ler_a_maquina(**fontes))


def reexaminar(**fontes: Any) -> dict[str, Any] | None:
    """O «Examinar»: relê a máquina, e o «antes» é a leitura que a página tem."""
    return _guardar_e_entregar(_ler_a_maquina(antes=_NA_TELA.ler(), **fontes))


def depois_de_gravar(**fontes: Any) -> dict[str, Any] | None:
    """O arranjo relido depois de uma gravação do editor — ver"""
    return _guardar_e_entregar(_ler_a_maquina(antes=_NA_TELA.ler(), **fontes))


def _guardar_e_entregar(lido: tuple[dict[str, Any], Lida] | None) -> dict[str, Any] | None:
    """A leitura que vai à página vira o «antes» do próximo «Examinar»."""
    if lido is None:
        return None
    dado, lida = lido
    _NA_TELA.guardar(lida)
    return dado


def _ha_o_que_desenhar(declarado: Any) -> bool:
    """Há face declarada, ou entrada numerada fora de face: sem isso o mapa não tem desenho."""
    return declarado is not None and bool(declarado.faces or _numeradas(declarado))


def porque_sem_leitura(carregar: Callable[[], Any] | None = None) -> str:
    """Por que :func:`para_a_pagina` não leu: nada mapeado, ou o computador não deixa ler."""
    try:
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina

        documento = (carregar or carregar_maquina)()
    except Exception:
        return pagina_do_mapa.SEM_LEITURA
    if _ha_o_que_desenhar(getattr(documento, "mapa", None)):
        return pagina_do_mapa.SEM_LEITURA
    return pagina_do_mapa.SEM_MAPA


def js_sem_leitura(porque: str) -> str:
    """O JavaScript que diz à página que não há leitura, e por quê: o exemplo sai."""
    if porque not in pagina_do_mapa.FRASES_SEM_LEITURA:
        raise ValueError(f"{porque!r} não é um porquê que a página conheça")
    return f"window.hefestoSemLeitura({json.dumps(porque)})"


def js_da_entrega(
    dado: Mapping[str, Any] | None, *, reexame: bool = False, como: str = COMO_ABRE,
    porque: str = "",
) -> str:
    """O JavaScript que entrega um arranjo à página — a abertura, o reexame e a"""
    if dado is None:
        return js_sem_leitura(porque)
    corpo = json.dumps(dado, ensure_ascii=False)
    if reexame:
        como = COMO_REEXAME
    if como not in (COMO_ABRE, COMO_REEXAME, COMO_GRAVOU):
        raise ValueError(f"{como!r} não é um jeito de a página receber o arranjo")
    if como == COMO_GRAVOU:
        return f"window.hefestoArranjo({corpo}, {json.dumps(COMO_GRAVOU)})"
    return f"window.hefestoArranjo({corpo}, {'true' if como == COMO_REEXAME else 'false'})"


def identidades(
    aparelhos: Sequence[Any],
    ler_o_serial: Callable[[str], str],
    antes: Mapping[str, tuple[str, str]] | None = None,
    *,
    lido_em: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """``caminho -> id`` de cada aparelho, o mesmo enquanto ele for o mesmo."""
    modelos = _modelos(aparelhos)
    sementes: dict[str, str] = {}
    for aparelho in aparelhos:
        caminho = aparelho.nome_do_kernel
        serial = (ler_o_serial(aparelho.no) or "").strip()
        if serial:
            sementes[caminho] = f"serial|{modelos[caminho]}|{serial}"
        elif aparelho.vid or aparelho.pid:
            sementes[caminho] = f"modelo|{modelos[caminho]}"
        else:
            sementes[caminho] = ""
    repetidas = Counter(sementes.values())
    parados = {(caminho, modelo): i for i, (caminho, modelo) in (antes or {}).items()}
    fora: dict[str, str] = {}
    for caminho, semente in sementes.items():
        if semente.startswith("serial|") and repetidas[semente] == 1:
            fora[caminho] = _resumo(semente)
    usados = set(fora.values())
    for caminho in sementes:
        de_antes = parados.get(((lido_em or {}).get(caminho, caminho), modelos[caminho]))
        if caminho not in fora and de_antes is not None and de_antes not in usados:
            fora[caminho] = de_antes
            usados.add(de_antes)
    for caminho, semente in sementes.items():
        if caminho in fora:
            continue
        pelo_caminho = _resumo(f"caminho|{modelos[caminho]}|{caminho}")
        resumo = pelo_caminho if not semente or repetidas[semente] > 1 else _resumo(semente)
        fora[caminho] = pelo_caminho if resumo in usados else resumo
        usados.add(fora[caminho])
    return fora


def _modelos(aparelhos: Sequence[Any]) -> dict[str, str]:
    """``caminho -> vid:pid`` — o modelo, que não separa dois iguais."""
    return {a.nome_do_kernel: f"{a.vid}:{a.pid}" for a in aparelhos}


def _resumo(semente: str) -> str:
    feito = hashlib.blake2s(semente.encode("utf-8"), key=_SAL, digest_size=8)
    return _PREFIXO_DO_ID + feito.hexdigest()


def _declarado(
    mapa: Any, numeros: Any, nome_de: Callable[[str], str | None] | None = None
) -> dict[str, dict[str, Any]]:
    """O que o usuário disse de cada entrada DO MAPA DO USUÁRIO, para o editor da página."""
    saida: dict[str, dict[str, Any]] = {}
    for numero in sorted(numeros):
        porta = mapa.portas.get(numero)
        dito: dict[str, Any] = {}
        if porta is not None and porta.liga:
            dito["liga"] = porta.liga
        if porta is not None and porta.extensor:
            dito["extensor"] = True
        if porta is not None and porta.usb:
            dito["usb"] = porta.usb
        nome = nome_de(numero) if nome_de is not None else None
        if nome:
            dito["nome"] = nome
        saida[numero] = dito
    return saida


def _o_que_ela_declarou_nas_entradas(
    faces: list[dict[str, Any]],
    mapa: Any,
    nome_de: Callable[[str], str | None] = lambda _n: None,
) -> dict[str, bool]:
    """Cada face diz de qual entrada pende; o hub sem face ganha a dele; o"""
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import (
        de_quem_pende,
        faces_dos_hubs,
    )
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
        frase_do_hub_lido,
        titulo_do_hub,
    )

    pendencias = de_quem_pende(mapa)
    por_numero: dict[str, dict[str, Any]] = {}
    for face in faces:
        for entrada in face["portas"]:
            por_numero.setdefault(entrada["n"], entrada)
            if "filho" in entrada:
                por_numero.setdefault(entrada["filho"]["n"], entrada["filho"])
    hub_lido: dict[str, bool] = {}
    for face in faces:
        dela = pendencias.get(face["nome"])
        if dela is None:
            continue
        face["daEntrada"] = dela.entrada
        face["titulo"] = titulo_do_hub(dela.entrada, nome_de(dela.entrada))
        if dela.lida is not None:
            face["diverge"] = frase_do_hub_lido(dela.lida, nome_de(dela.lida))
        if dela.barramento is not None:
            hub_lido[dela.barramento] = True
    ligadas = {dela.entrada for dela in pendencias.values()}
    for numero, nome in faces_dos_hubs(mapa).items():
        entrada = por_numero.get(numero)
        if entrada is None or numero in ligadas:
            continue
        faces.append({
            "nome": nome,
            "titulo": titulo_do_hub(numero, nome_de(numero)),
            "forma": _FILEIRA_DO_HUB,
            "regiao": "hub",
            "daEntrada": numero,
            "fantasma": True,
            "portas": [
                {"n": f"{numero}.{i}", "usb": entrada["usb"], "onde": "hub", "pos": i}
                for i in range(1, ENTRADAS_DO_HUB_DECLARADO + 1)
            ],
        })
    for numero, entrada in por_numero.items():
        porta = mapa.portas.get(numero)
        if porta is not None and porta.extensor:
            entrada["extensor"] = True
    return hub_lido


def _aparelho(
    aparelho: Any,
    identidade: str,
    do_censo: Any = None,
    tipos: Mapping[str, str] | None = None,
    apelidos: Mapping[str, str] | None = None,
    censo: Any = None,
    faixas: Mapping[str, Any] | None = None,
    da_cadeia: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Um aparelho do motor nos campos que a página LÊ, com o que o painel dele diz.

    ``modelo`` é o ``vid:pid`` (a chave do que ela declara do aparelho) e ``etiquetas`` é «o que
    a máquina vê», em palavras, sem botão. ``da_cadeia`` é o que :func:`_a_cadeia_usb` diz dele
    (o hub físico, o enlace abaixo, onde ele pende).
    """
    corpo: dict[str, Any] = {
        "id": identidade,
        "tipo": aparelho.tipo,
        "nome": aparelho.nome,
        "classe": aparelho.classe,
        "cor": pagina_do_mapa.CORES_POR_CLASSE.get(
            aparelho.classe, pagina_do_mapa.COR_SEM_CLASSE),
    }
    if do_censo is None:
        return corpo
    modelo = f"{do_censo.vid}:{do_censo.pid}" if do_censo.vid or do_censo.pid else ""
    corpo["modelo"] = modelo
    declarado = (tipos or {}).get(modelo, "")
    if declarado:
        corpo["tipoDeclarado"] = declarado
        corpo["cor"] = pagina_do_mapa.COR_POR_TIPO_DECLARADO.get(
            declarado, pagina_do_mapa.CORES_POR_CLASSE.get(declarado, corpo["cor"]))
    if (apelidos or {}).get(modelo):
        corpo["nomeDeclarado"] = (apelidos or {})[modelo]
    if not do_censo.produto.strip() and do_censo.produto_da_base.strip():
        corpo["nome"] = do_censo.produto_da_base.strip()
    corpo.update(da_cadeia or {})
    corpo["etiquetas"] = _etiquetas_do_aparelho(do_censo, censo)
    if getattr(do_censo, "receptor", False):
        corpo["receptor"] = True
    if (faixas or {}).get(modelo):
        corpo["faixa"] = faixas[modelo]  # type: ignore[index]
    return corpo


def _apelidos(documento: Any) -> dict[str, str]:
    """``{vid:pid: apelido}`` do que ela chamou cada aparelho."""
    radios = getattr(getattr(documento, "mesa", None), "radios", None) or {}
    return {chave: radio.apelido for chave, radio in radios.items() if radio.apelido}


_VELOCIDADE_SUPERSPEED_MBPS = 5000


def _etiquetas_do_aparelho(aparelho: Any, censo: Any) -> list[str]:
    """O que a máquina vê do aparelho: o chip, a velocidade, os hubs e quem divide o hub."""
    etiquetas: list[str] = []
    if getattr(aparelho, "receptor", False):
        etiquetas.append("receptor 2.4G")
    elif aparelho.especie and aparelho.especie != ESPECIE_DESCONHECIDA:
        etiquetas.append(aparelho.especie)
    enlace = enlace_abaixo(censo, aparelho) if censo is not None else None
    if enlace is not None:
        etiquetas.append(frase_do_enlace(enlace.velocidade_mbps))
    elif aparelho.velocidade_mbps > 0:
        etiquetas.append(
            "USB 3.0" if aparelho.velocidade_mbps >= _VELOCIDADE_SUPERSPEED_MBPS else "USB 2.0")
    cadeia = cadeia_de_hubs(censo, aparelho.no) if censo is not None else ()
    if cadeia:
        etiquetas.append(f"atrás de {len(cadeia)} hub" + ("s" if len(cadeia) > 1 else ""))
        vizinhos = [
            outro for outro in censo.conectados()
            if outro.no != aparelho.no and cadeia[0] in cadeia_de_hubs(censo, outro.no)
            and not outro.e_hub
        ]
        if any(v.velocidade_mbps >= _VELOCIDADE_SUPERSPEED_MBPS for v in vizinhos):
            etiquetas.append("USB 3.0 no mesmo hub")
        elif len(vizinhos) >= 2:
            etiquetas.append("outros rádios no mesmo hub")
    return etiquetas


SABE_SUPERSPEED = "Sabe 5 Gb/s"

_CLASSE_DO_TIPO = {
    "Bluetooth": "bt", "Wi-Fi": "wifi", "Câmera": "webcam", "Webcam": "webcam",
    "Teclado": "teclado",
    "Mouse": "mouse", "Hub": "hub",
}

LIMITE_DO_REGISTRO = 30
SEM_ENTRADA_MARCADA = "Sem entrada marcada"
NAO_TEM_ENTRADA = "—"
_JANELA_DO_HUB_S = 5.0
_SEM_REGISTRO = "Ainda sem registro"


def frase_do_enlace(velocidade_mbps: float) -> str:
    """«480 Mb/s · Sabe 5 Gb/s»: o fato do enlace abaixo, sem causa."""
    return f"{_mbps(velocidade_mbps)} · {SABE_SUPERSPEED}"


def _mbps(velocidade: float) -> str:
    return f"{velocidade:g}".replace(".", ",") + " Mb/s"


def frase_do_hub(usb: int, entradas: int) -> str:
    """«Hub USB 3 · 7 entradas»: o hub de plástico, um só."""
    return f"Hub USB {usb} · {entradas} " + ("entrada" if entradas == 1 else "entradas")


def _a_cadeia_usb(censo: Any, presentes: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """O que a cadeia USB diz de cada aparelho que a página desenha (``nome do kernel -> id``).

    ``hubFisico`` vai no chip que representa o hub de plástico (os dois lados e a cascata interna
    são UM); os outros nós dele levam ``parteDe`` e a página não os desenha. ``dentroDe`` é o hub
    físico mais perto acima, ``enlace`` o fato de quem sabe SuperSpeed e negociou menos.
    """
    por_no = {a.no: a for a in censo.aparelhos}
    hubs = hubs_fisicos(censo)
    do_hub: dict[str, HubFisico] = {no: hub for hub in hubs for no in hub.nos}
    chip_de: dict[str, str] = {}
    for hub in hubs:
        for no in hub.nos:
            if por_no[no].nome_do_kernel in presentes:
                chip_de[hub.representante] = presentes[por_no[no].nome_do_kernel]
                break
    saida: dict[str, dict[str, Any]] = {}
    for aparelho in censo.conectados():
        identidade = presentes.get(aparelho.nome_do_kernel)
        if identidade is None:
            continue
        dele: dict[str, Any] = {}
        do_aparelho = do_hub.get(aparelho.no)
        if do_aparelho is not None:
            if chip_de.get(do_aparelho.representante) == identidade:
                usb = 3 if any(por_no[no].velocidade_mbps >= _VELOCIDADE_SUPERSPEED_MBPS
                               for no in do_aparelho.nos) else 2
                dele["hubFisico"] = frase_do_hub(usb, do_aparelho.entradas)
            else:
                dele["parteDe"] = chip_de[do_aparelho.representante]
        for acima in cadeia_de_hubs(censo, aparelho.no):
            pai = chip_de.get(acima)
            if pai and pai != identidade:
                dele["dentroDe"] = pai
                break
        enlace = enlace_abaixo(censo, aparelho)
        if enlace is not None:
            dele["enlace"] = frase_do_enlace(enlace.velocidade_mbps)
        saida[identidade] = dele
    return saida


def _o_diario_na_tela(
    ler_o_diario: Callable[[], list[dict[str, Any]]] | None,
    boot_id: Callable[[], str | None] | None,
    agora: _dt.datetime,
    conectados: Sequence[Any],
    mapa: Mapping[str, str],
    apelidos: Mapping[str, str],
    tipos: Mapping[str, str],
    rotulo_de: Callable[[str], str],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """``(os que não apareceram neste início, o registro)``, lidos do arquivo do diário.

    O diário vazio dá a lista vazia: o registro diz desde quando ouve e nunca inventa linha.
    ``rotulo_de`` é o dono do nome da entrada (`entrada_a_entrada.rotulo_do_numero`): o nome
    que o usuário deu, ou «Entrada N».
    """
    try:
        linhas = (ler_o_diario or _ler_o_diario_do_disco)()
    except Exception:
        linhas = []
    try:
        boot = (boot_id or _boot_id_deste_boot)() or ""
    except Exception:
        boot = ""
    presentes = {f"{a.vid}:{a.pid}" for a in conectados}
    return (
        _os_que_sumiram(linhas, boot, presentes, apelidos, tipos),
        _o_registro(linhas, agora, mapa, apelidos, tipos, rotulo_de),
    )


def _ler_o_diario_do_disco() -> list[dict[str, Any]]:
    return diario_do_usb.ler(limite=_LINHAS_LIDAS)


_LINHAS_LIDAS = 600


def _boot_id_deste_boot() -> str | None:
    from hefesto_dualsense4unix.daemon.subsystems.identity import _read_boot_id

    return _read_boot_id()


def _cor_do_tipo(tipo: str, vid_pid: str, tipos: Mapping[str, str]) -> str:
    cor = pagina_do_mapa.CORES_POR_CLASSE.get(
        _CLASSE_DO_TIPO.get(tipo, ""), pagina_do_mapa.COR_SEM_CLASSE)
    declarado = tipos.get(vid_pid, "")
    if declarado:
        cor = pagina_do_mapa.COR_POR_TIPO_DECLARADO.get(
            declarado, pagina_do_mapa.CORES_POR_CLASSE.get(declarado, cor))
    return cor


def _nome_da_linha(linha: Mapping[str, Any], apelidos: Mapping[str, str]) -> str:
    vid_pid = f"{linha.get('vid', '')}:{linha.get('pid', '')}"
    return (apelidos.get(vid_pid) or str(linha.get("produto") or "").strip()
            or str(linha.get("produto_da_base") or "").strip())


def _os_que_sumiram(
    linhas: Sequence[Mapping[str, Any]],
    boot: str,
    presentes: set[str],
    apelidos: Mapping[str, str],
    tipos: Mapping[str, str],
) -> list[dict[str, str]]:
    """Quem o diário diz que não apareceu neste início e continua fora do censo de agora."""
    if not boot:
        return []
    ultimo: dict[str, Mapping[str, Any]] = {}
    for linha in linhas:
        if linha.get("boot_id") != boot or linha.get("o_que") not in (
                diario_do_usb.NAO_APARECEU, diario_do_usb.ENTROU, diario_do_usb.VOLTOU):
            continue
        ultimo[f"{linha.get('vid', '')}:{linha.get('pid', '')}|{linha.get('tipo', '')}"] = linha
    saida: list[dict[str, str]] = []
    for chave, linha in ultimo.items():
        vid_pid = chave.split("|", 1)[0]
        if linha.get("o_que") != diario_do_usb.NAO_APARECEU or vid_pid in presentes:
            continue
        tipo = str(linha.get("tipo", ""))
        saida.append({"tipo": tipo, "nome": _nome_da_linha(linha, apelidos),
                      "cor": _cor_do_tipo(tipo, vid_pid, tipos)})
    return saida


def _a_hora(carimbo: float, agora: _dt.datetime) -> str:
    quando = _dt.datetime.fromtimestamp(carimbo).astimezone()
    hoje = agora.astimezone().date() if agora.tzinfo else agora.date()
    texto = quando.strftime("%H:%M")
    return texto if quando.date() == hoje else quando.strftime("%d/%m ") + texto


def _o_evento(linha: Mapping[str, Any]) -> tuple[str, str] | None:
    """``(a palavra, o tom)`` do evento, ou ``None`` quando ele não é uma linha do registro."""
    o_que = linha.get("o_que")
    if o_que == diario_do_usb.ENTROU:
        return "Entrou", ""
    if o_que == diario_do_usb.SAIU:
        return "Saiu", "sai"
    if o_que == diario_do_usb.VOLTOU:
        return "Voltou", ""
    if o_que == diario_do_usb.NAO_APARECEU:
        return "Não apareceu", "sumiu"
    if o_que == diario_do_usb.MUDOU_DE_VELOCIDADE:
        antes, depois = linha.get("antes"), linha.get("depois")
        if isinstance(antes, (int, float)) and isinstance(depois, (int, float)):
            if depois < antes:
                return "Ficou mais lento", "lento"
            if depois > antes:
                return "Ficou mais rápido", ""
        return "Mudou de velocidade", ""
    return None


def _o_registro(
    linhas: Sequence[Mapping[str, Any]],
    agora: _dt.datetime,
    mapa: Mapping[str, str],
    apelidos: Mapping[str, str],
    tipos: Mapping[str, str],
    rotulo_de: Callable[[str], str],
) -> dict[str, Any]:
    """O registro da quarta aba: desde quando se ouve e até 30 linhas, a mais nova em cima."""
    entrada_de: dict[str, str] = {}
    for numero in sorted(mapa, key=lambda n: (not n.isdigit(), int(n) if n.isdigit() else 0, n)):
        entrada_de.setdefault(mapa[numero], numero)
    ouvindo = ""
    if not linhas:
        ouvindo = _SEM_REGISTRO
    else:
        for linha in linhas:
            if linha.get("o_que") == diario_do_usb.COMECOU_A_OUVIR:
                ouvindo = "Ouvindo desde " + _a_hora(float(linha["carimbo"]), agora)
            elif linha.get("o_que") == diario_do_usb.PAROU_DE_OUVIR and ouvindo:
                ouvindo = "Sem ouvir desde " + _a_hora(float(linha["carimbo"]), agora)
    saida: list[dict[str, str]] = []
    hubs_vistos: dict[tuple[str, str], float] = {}
    for linha in reversed(linhas):
        evento = _o_evento(linha)
        if evento is None or "carimbo" not in linha:
            continue
        tipo = str(linha.get("tipo", ""))
        carimbo = float(linha["carimbo"])
        if tipo == "Hub":
            chave = (str(linha.get("o_que")), str(linha.get("hub_fisico") or linha.get("no")))
            if chave in hubs_vistos and abs(hubs_vistos[chave] - carimbo) <= _JANELA_DO_HUB_S:
                continue
            hubs_vistos[chave] = carimbo
        vid_pid = f"{linha.get('vid', '')}:{linha.get('pid', '')}"
        sumiu = linha.get("o_que") == diario_do_usb.NAO_APARECEU
        entrada = entrada_de.get(str(linha.get("no", "")))
        saida.append({
            "hora": _a_hora(carimbo, agora),
            "evento": evento[0],
            "tom": evento[1],
            "tipo": tipo,
            "nome": _nome_da_linha(linha, apelidos),
            "cor": _cor_do_tipo(tipo, vid_pid, tipos),
            "onde": (NAO_TEM_ENTRADA if sumiu
                     else rotulo_de(entrada) if entrada else SEM_ENTRADA_MARCADA),
        })
        if len(saida) == LIMITE_DO_REGISTRO:
            break
    return {"ouvindo": ouvindo, "linhas": saida}


def _numeradas(mapa: Any) -> list[str]:
    """As entradas numeradas do mapa que não são ponta de extensão e não estão em face."""
    nas_faces = {numero for face in mapa.faces for numero in face.portas}
    return sorted(
        (n for n, porta in mapa.portas.items()
         if n not in nas_faces and not porta.filha_de and n.isdigit()),
        key=int,
    )


SEM_LUGAR = "Sem Lugar"


def _a_fileira_sem_lugar(mapa: Any, censo: Any, mapa_das_portas: Any) -> dict[str, Any] | None:
    """A fileira das entradas numeradas que nenhuma face tem — fora do plano.

    A-ENTRADA-SEM-LUGAR-APARECE-NO-MAPA-01 (absorvida em 04/10/2026): o «Salvar» do Mapear com o
    lugar vazio numera a entrada e ela nasce fora de toda face. O motor não a vê (ela não é face:
    as sugestões nunca mandam ninguém para lá); a página a desenha depois das faces.
    """
    numeros = _numeradas(mapa)
    if not numeros:
        return None
    return {
        "nome": SEM_LUGAR,
        "titulo": SEM_LUGAR,
        "forma": _COLUNA_CURTA if len(numeros) <= _TETO_DA_COLUNA else _GRADE,
        "regiao": "pc",
        "semLugar": True,
        "portas": [_entrada(e) for e in mapa_das_portas.entradas_sem_lugar(mapa, censo, numeros)],
    }


def _a_leitura_da_maquina(
    faces: list[dict[str, Any]], mapa: Any, censo: Any, mapa_das_portas: Any
) -> None:
    """A leitura da máquina em palavras curtas, embaixo da face do hub (ou da última face)."""
    frases = mapa_das_portas.leitura_da_maquina(mapa, censo)
    if not frases or not faces:
        return
    alvo = next((f for f in faces if f.get("regiao") == "hub"), faces[-1])
    alvo["leitura"] = frases


def _faces(faces: Any) -> list[dict[str, Any]]:
    """As faces do motor mais a FORMA do desenho, que não vem de fonte nenhuma."""
    saida = []
    dona = _dona_da_faixa(faces)
    for face in faces:
        corpo: dict[str, Any] = {
            "nome": face.nome,
            "forma": _forma(face),
            "regiao": face.regiao,
            "portas": [_entrada(e) for e in face.entradas],
        }
        if face.perto:
            corpo["perto"] = True
        if face.alto:
            corpo["alto"] = True
        if face is dona:
            corpo["donaDaFaixaPc"] = True
        saida.append(corpo)
    return saida


def _dona_da_faixa(faces: Any) -> Any:
    """A face do PC com mais entradas, ou ``None`` se nenhuma face é do PC."""
    do_pc = [f for f in faces if f.regiao == "pc"]
    return max(do_pc, key=lambda f: len(f.entradas)) if do_pc else None


def _forma(face: Any) -> str:
    if face.regiao == "hub":
        return _FILEIRA_DO_HUB
    return _COLUNA_CURTA if len(face.entradas) <= _TETO_DA_COLUNA else _GRADE


def _entrada(entrada: Any) -> dict[str, Any]:
    """Uma entrada do motor, sem os campos que ela não tem."""
    corpo: dict[str, Any] = {"n": entrada.n, "usb": entrada.usb, "onde": entrada.onde}
    if entrada.par:
        corpo["par"] = entrada.par
    if entrada.pos is not None:
        corpo["pos"] = entrada.pos
    if entrada.esticada:
        corpo["esticada"] = True
        corpo["cabo"] = CABO_DECLARADO
    if entrada.filho is not None:
        corpo["filho"] = _entrada(entrada.filho)
    return corpo
