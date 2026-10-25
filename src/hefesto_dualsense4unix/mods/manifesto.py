"""O ``hefesto-mod.json``: o contrato de uma modificação, lido por pydantic.

Em JSON, e não em TOML, porque o produto aceita Python 3.10 (``pyproject.toml``,
``requires-python``) e o ``tomllib`` só existe a partir do 3.11. Campo que o
esquema não conhece é recusado (``extra="forbid"``): um erro de digitação numa
permissão nunca vira permissão a menos nem a mais.

Toda recusa sai como :class:`ManifestoRecusadoError`, com UMA frase para a tela.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.tema import (
    CHAVE_DA_OPCAO_DA_COR,
    CHAVE_DA_OPCAO_DO_LADO,
    CHAVE_DO_LADO,
    CHAVES_DA_COR,
    LADOS_DOS_BOTOES,
)
from hefesto_dualsense4unix.utils.maquina import _CHAVE_DE_LANCADOR

NOME_DO_MANIFESTO = "hefesto-mod.json"
PASTA_DE_FABRICA = Path(__file__).resolve().parent / "de_fabrica"


def ids_de_fabrica() -> frozenset[str]:
    """Os ids das extensões que vêm no pacote (uma pasta com manifesto em ``de_fabrica/``)."""
    try:
        return frozenset(p.name for p in PASTA_DE_FABRICA.iterdir()
                         if (p / NOME_DO_MANIFESTO).is_file())
    except OSError:
        return frozenset()

#: O que uma modificação pode ser. ``processo`` é a única que leva código; as
#: outras três são declaração, e o Hefesto as lê sem abrir processo nenhum.
TIPOS = ("processo", "lancador", "tema", "perfil")

#: O ``nome`` do evento do tópico ``entradas``.
NOME_DAS_ENTRADAS = "controle.entradas"
#: O ``nome`` do evento do tópico ``movimento``.
NOME_DO_MOVIMENTO = "controle.movimento"

#: ``ler:<tópico>``: o nome público de cada tópico e os tópicos do barramento
#: que ele entrega. O nome público é o contrato; o do barramento pode mudar.
TOPICOS_DE_LEITURA: dict[str, tuple[str, ...]] = {
    "estado": (EventTopic.STATE_UPDATE,),
    "botoes": (EventTopic.BUTTON_DOWN, EventTopic.BUTTON_UP),
    # Os analógicos, os gatilhos e o touchpad de CADA controle: como o `botoes`, o serviço enche a
    # fila (`Porta.entradas_do_tique`) e o barramento não leva este tópico.
    "entradas": (NOME_DAS_ENTRADAS,),
    # O giroscópio e o acelerômetro de CADA controle, à parte das entradas: o leitor de movimento
    # só fica vivo enquanto alguém o pede, e o serviço enche a fila (`Porta.movimento_do_tique`).
    "movimento": (NOME_DO_MOVIMENTO,),
    "bateria": (EventTopic.BATTERY_CHANGE,),
    "conexao": (  # (noqa-acento): contrato ASCII
        EventTopic.CONTROLLER_CONNECTED,
        EventTopic.CONTROLLER_DISCONNECTED,
    ),
    # A vibração que o jogo pede a cada controle (com o número do jogador) e o aviso de que o
    # jogo fechou: quem acompanha a vibração precisa dos dois, e por isso é uma permissão só.
    "jogo.vibracao": (  # (noqa-acento): contrato ASCII
        EventTopic.JOGO_VIBRACAO,
        EventTopic.JOGO_FECHOU,
    ),
    # O que o jogo pede ao gatilho de CADA controle e a intensidade da háptica por áudio dele:
    # permissões à parte da vibração, porque são dois sinais diferentes e a extensão escolhe.
    "jogo.gatilho": (EventTopic.JOGO_GATILHO,),  # (noqa-acento): contrato ASCII
    "jogo.haptica": (EventTopic.JOGO_HAPTICA,),  # (noqa-acento): contrato ASCII
    # O perfil efetivo, o jogo e o estilo de cada controle (`perfil.trocou`, sem marca nenhuma).
    # Fica à parte da vibração: saber QUAL jogo está aberto é dado da pessoa, e quem só quer a
    # vibração não o recebe.
    "perfil.jogo": (EventTopic.PERFIL_TROCOU,),
    # O que o jogo pede a um acessório, passado de uma extensão a outra (`eventos.publicar`). O
    # Hefesto não sabe que acessório é nem o que cada função faz: os nomes são das extensões.
    "jogo.acessorio": (EventTopic.JOGO_ACESSORIO,),  # (noqa-acento): contrato ASCII
    # Os gestos do PS que comandam os acessórios (sobe, desce, para, perfil…). A mesma permissão
    # deixa a modificação devolver o estado (`acessorios.estado`), que liga e desliga os gestos.
    "acessorios.gesto": (EventTopic.ACESSORIOS_GESTO,),  # (noqa-acento): contrato ASCII
}

#: ``publicar:<tópico>``: os tópicos que uma extensão pode publicar para as outras
#: (``eventos.publicar``), com o tópico do barramento que cada um entrega. Quem lê pede
#: ``ler:<tópico>``; quem publica pede ``publicar:<tópico>``.
TOPICOS_DE_PUBLICACAO: dict[str, str] = {
    "jogo.acessorio": EventTopic.JOGO_ACESSORIO,  # (noqa-acento): contrato ASCII
}

#: O nome de uma função de um pedido ao acessório: o vocabulário é das extensões que conversam.
NOME_DA_FUNCAO = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
#: Quantas funções cabem numa publicação, cada uma de 0 a 1.
FUNCOES_POR_PEDIDO = 16

#: ``escrever:<canal>``: os canais do controle que uma modificação pode pedir.
CANAIS_DE_ESCRITA = ("luz", "vibracao", "gatilho")

#: ``rede:<alcance>``. Sem a palavra, vale ``nenhuma``.
ALCANCES_DE_REDE = ("nenhuma", "local", "internet")

#: As permissões de uma palavra só.
PERMISSOES_SIMPLES = ("bluetooth", "lancador", "tema", "aparelhos")

_O_QUE_DEIXA: dict[str, str] = {
    "ler:estado": "Ler os botões, os eixos, os gatilhos e a bateria do controle do jogador 1.",
    "ler:botoes": "Saber quando um botão é apertado e solto.",
    "ler:entradas": "Ler os analógicos, os gatilhos e o touchpad de cada controle.",
    "ler:movimento": "Ler o giroscópio e o acelerômetro de cada controle.",
    "ler:bateria": "Saber a carga da bateria.",
    "ler:conexao": "Saber quando um controle entra ou sai.",  # (noqa-acento): contrato ASCII
    "ler:jogo.vibracao": (  # (noqa-acento): contrato ASCII
        "Saber a vibração que o jogo pede a cada controle e quando o jogo fecha."
    ),
    "ler:jogo.gatilho": (  # (noqa-acento): contrato ASCII
        "Saber o efeito de gatilho que o jogo pede a cada controle."
    ),
    "ler:jogo.haptica": (  # (noqa-acento): contrato ASCII
        "Saber a intensidade da vibração fina que o jogo manda a cada controle."
    ),
    "ler:perfil.jogo": "Saber o perfil, o jogo e o estilo em uso em cada controle.",
    "ler:jogo.acessorio": (  # (noqa-acento): contrato ASCII
        "Receber o que o jogo pede a um acessório, passado por outra extensão."
    ),
    "publicar:jogo.acessorio": (  # (noqa-acento): contrato ASCII
        "Passar a outras extensões o que o jogo pede a um acessório."
    ),
    "ler:acessorios.gesto": (  # (noqa-acento): contrato ASCII
        "Receber os gestos do botão PS que comandam os acessórios, sem receber botão nenhum."
    ),
    "publicar:acessorios.estado": (  # (noqa-acento): contrato ASCII
        "Mostrar na janela dela e na aba Conexões as conexões e os aparelhos que ela liga."
    ),
    "pedir:luz.pulso": (  # (noqa-acento): contrato ASCII
        "Pedir que a barra de luz de um controle pulse na cor escolhida, nos perfis «Adulto»."
    ),
    "escrever:luz": "Mudar a cor da luz de um controle.",
    "escrever:vibracao": "Fazer um controle vibrar.",
    "escrever:gatilho": "Mudar a resistência dos gatilhos de um controle.",
    "rede:nenhuma": "Sem acesso à rede.",
    "rede:local": "Usar a rede desta casa.",
    "rede:internet": "Usar a internet.",
    "bluetooth": "Falar com aparelhos por Bluetooth.",
    "lancador": "Acrescentar um lançador de jogos e abrir os jogos que ele lista.",
    "tema": "Trocar as cores da interface e o lado dos botões da janela.",
    "aparelhos": "Abrir aparelhos ligados ao computador.",
}

#: Os botões que uma opção ``por_botao`` aceita, nos nomes do tópico ``botoes``. O PS e o
#: microfone ficam de fora: são os gestos da casa.
BOTOES_DO_POR_BOTAO = (
    "cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "l3", "r3",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right", "options", "create",
    "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
)
#: Uma forma de ``por_botao``: até 16 passos ``[força 0..1, segundos]``, cada passo até 10 s.
PASSOS_DA_FORMA = 16
SEGUNDOS_DO_PASSO = 10.0
FORMAS_POR_OPCAO = 16
#: Uma ação da janela (nas duas listas do manifesto): o botão que AGE na hora, sem rascunho.
ACOES_DA_JANELA = 8
ACOES_DO_APARELHO = 6
#: A ação do aparelho com este id é a chave «ligado» do cartão, e não um botão.
ACAO_DE_LIGAR = "ligar"
#: Os desenhos que uma ação pode pedir; sem ``icone``, o botão é só o rótulo.
ICONES_DA_ACAO = ("procurar", "testar", "esquecer", "ligar", "atualizar")
#: O que o ``livre`` com ``modos`` faz ao soltar; o primeiro é o de fábrica.
MODOS_DO_LIVRE = ("soltar", "segurar", "repetir")


def forma_valida(nome: object, passos: object) -> bool:
    """A forma ``nome: [[força 0..1, segundos], ...]``: o nome de 1 a 20 letras, até 16 passos,
    cada passo até 10 s. A régua é uma só, do ``por_botao`` e do ``livre``."""
    if not isinstance(nome, str) or not 1 <= len(nome) <= 20:
        return False
    if not isinstance(passos, list) or len(passos) > PASSOS_DA_FORMA:
        return False
    for passo in passos:
        if not (isinstance(passo, (list, tuple)) and len(passo) == 2
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in passo)):
            return False
        if not (0.0 <= passo[0] <= 1.0 and 0.0 < passo[1] <= SEGUNDOS_DO_PASSO):
            return False
    return True

#: A cor de uma opção ``cor``: ``#rrggbb``, minúsculas ou maiúsculas.
COR_HEXA = re.compile(r"^#[0-9a-fA-F]{6}$")

#: As permissões que deixam a extensão devolver ``acessorios.estado``. Só a do gesto liga os
#: gestos do PS; a do estado só mostra (a janela e a aba Conexões).
PERMISSOES_DO_ESTADO = ("ler:acessorios.gesto", "publicar:acessorios.estado")

_NOME_DE_HOST = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                           r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")


def endereco_valido(texto: str) -> tuple[str, int] | None:
    """``host:porta`` de uma opção ``endereco``: ``(host, porta)``, ou ``None`` fora da forma.

    O host é um IPv4, um nome (``meu-pc.local``) ou um IPv6 entre colchetes; a porta, de 1 a 65535.
    """
    import ipaddress

    host, separador, porta = texto.strip().rpartition(":")
    if not separador or not porta.isdigit() or not 1 <= int(porta) <= 65535:
        return None
    colchetes = host.startswith("[") and host.endswith("]")
    if colchetes or host.replace(".", "").isdigit():
        try:
            ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = ipaddress.ip_address(
                host[1:-1] if colchetes else host)
        except ValueError:
            ip = None
        valido = ip is not None and ip.version == (6 if colchetes else 4)
        return (host, int(porta)) if valido else None
    return (host, int(porta)) if _NOME_DE_HOST.match(host) else None


#: A chave de um jogo numa opção ``jogos`` e no ``perfil.trocou``: a classe de janela da Steam.
CHAVE_DE_JOGO = re.compile(r"^steam_app_[0-9]{1,12}$")

_SPDX = re.compile(r"^[A-Za-z0-9.+-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+-]+)*$")
_CLAUSULA_DA_FAIXA = re.compile(r"^(>=|<=|==|>|<)?\s*(\d+)$")


class ManifestoRecusadoError(ValueError):
    """O manifesto não serve; ``frase`` é o que a tela mostra, numa linha."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


def _clausulas(faixa: str) -> list[tuple[str, int]]:
    """``">=1,<3"`` vira ``[(">=", 1), ("<", 3)]``; número solto vale ``==``."""
    saida: list[tuple[str, int]] = []
    for pedaco in faixa.split(","):
        casou = _CLAUSULA_DA_FAIXA.match(pedaco.strip())
        if casou is None:
            raise ValueError(f"faixa de api ilegível: {faixa!r}")
        saida.append((casou.group(1) or "==", int(casou.group(2))))
    return saida


def aceita_a_api(faixa: str, versao: int = API_DAS_MODIFICACOES) -> bool:
    """A faixa declarada aceita esta versão da porta?"""
    contas = {
        ">=": versao.__ge__, "<=": versao.__le__, "==": versao.__eq__,
        ">": versao.__gt__, "<": versao.__lt__,
    }
    return all(contas[op](numero) for op, numero in _clausulas(faixa))


def permissao_valida(palavra: str) -> bool:
    """A palavra é uma permissão que este Hefesto sabe mostrar e conferir?"""
    return palavra in _O_QUE_DEIXA


def o_que_a_permissao_deixa(palavra: str) -> str:
    """A frase curta que a tela mostra ao lado da permissão, antes do «sim»."""
    return _O_QUE_DEIXA.get(palavra, palavra)


def permissoes_novas(aceitas: list[str] | tuple[str, ...], pedidas: list[str]) -> list[str]:
    """O que ``pedidas`` acrescenta a ``aceitas``: é isto que volta a pedir o «sim»."""
    ja = set(aceitas)
    return [p for p in pedidas if p not in ja and p != "rede:nenhuma"]


class Processo(BaseModel):
    """O comando que o supervisor abre, relativo à pasta da modificação."""

    model_config = ConfigDict(extra="forbid")

    executar: list[str] = Field(min_length=1)

    @field_validator("executar")
    @classmethod
    def _dentro_da_pasta(cls, valor: list[str]) -> list[str]:
        return _comando_dentro_da_pasta(valor, "processo.executar")


def _comando_dentro_da_pasta(valor: list[str], campo: str) -> list[str]:
    """O primeiro da linha é um arquivo da pasta da modificação ou um nome do ``PATH``."""
    primeiro = valor[0]
    if not primeiro.strip():
        raise ValueError(f"{campo} começa vazio")
    if primeiro.startswith("/") or ".." in Path(primeiro).parts:
        raise ValueError(f"{campo} aponta para fora da pasta da modificação")
    return valor


class Opcao(BaseModel):
    """Uma opção que a modificação declara e a tela mostra no botão de configurações."""

    model_config = ConfigDict(extra="forbid")

    id: str
    rotulo: str = Field(min_length=1, max_length=60)
    tipo: Literal[
        "escolha", "ligado", "numero", "cor", "deslizante", "jogos", "css", "endereco", "por_botao",
        "livre",
    ]
    escolhas: list[str] = Field(default_factory=list)
    padrao: (str | bool | float | list[str] | dict[str, str] | dict[str, list[list[float]]]
             | None) = None
    # O ``por_botao``: as formas pelo nome (cada uma, passos ``[força, segundos]``; a lista vazia é
    # a forma que não toca) e os botões que a janela mostra. O valor é ``{botão: forma}``.
    formas: dict[str, list[list[float]]] = Field(default_factory=dict)
    botoes: list[str] = Field(default_factory=list)
    # O ``deslizante`` declara a faixa inteira e a posição inicial (obrigatória e
    # dentro da faixa); os três ficam vazios nos outros tipos.
    minimo: float | None = None
    maximo: float | None = None
    passo: float | None = None
    # A aba interna da janela em que a opção mora; sem ela, a opção vai à primeira aba. Com
    # um grupo só, a janela não desenha aba nenhuma.
    grupo: str | None = Field(default=None, min_length=1, max_length=30)
    # O ``livre`` com ``modos``: a faixa ganha «Soltar», «Segurar» e «Repetir» (``MODOS_DO_LIVRE``).
    modos: bool = False

    @field_validator("id")
    @classmethod
    def _chave(cls, valor: str) -> str:
        if not _CHAVE_DE_LANCADOR.match(valor):
            raise ValueError("id da opção fora da forma de chave")
        return valor

    @model_validator(mode="after")
    def _escolhas_da_escolha(self) -> Opcao:
        if self.tipo == "escolha" and not self.escolhas:
            raise ValueError(f"a opção {self.id} é de escolha e não lista as escolhas")
        if self.tipo == "cor" and self.padrao is not None and not (
            isinstance(self.padrao, str) and COR_HEXA.match(self.padrao)
        ):
            raise ValueError(f"a opção {self.id} é de cor e o padrão não é #rrggbb")
        if self.tipo == "deslizante":
            self._conferir_o_deslizante()
        elif (self.minimo, self.maximo, self.passo) != (None, None, None):
            raise ValueError(f"a opção {self.id} não é deslizante e declara faixa ou passo")
        if self.tipo == "jogos":
            self._conferir_os_jogos()
        elif isinstance(self.padrao, list):
            raise ValueError(f"a opção {self.id} não é de jogos e o padrão é uma lista")
        if self.tipo == "por_botao":
            self._conferir_o_por_botao()
        elif self.formas or self.botoes or (isinstance(self.padrao, dict) and self.tipo != "livre"):
            raise ValueError(f"a opção {self.id} não é por_botao e declara formas ou botões")
        if self.tipo == "livre":
            self._conferir_o_livre()
        elif self.modos:
            raise ValueError(f"a opção {self.id} não é livre e declara modos")
        if self.tipo == "endereco" and self.padrao is not None and not (
            isinstance(self.padrao, str)
            and (not self.padrao or endereco_valido(self.padrao) is not None)
        ):
            raise ValueError(f"a opção {self.id} é de endereço e o padrão não é host:porta")
        return self

    def _conferir_o_por_botao(self) -> None:
        if not self.formas or len(self.formas) > FORMAS_POR_OPCAO:
            raise ValueError(f"o por_botao {self.id} declara de 1 a {FORMAS_POR_OPCAO} formas")
        for nome, passos in self.formas.items():
            if not forma_valida(nome, passos):
                raise ValueError(f"a forma «{nome}» de {self.id} pede [força 0..1, segundos]")
        estranhos = [b for b in self.botoes if b not in BOTOES_DO_POR_BOTAO]
        if estranhos or len(set(self.botoes)) != len(self.botoes):
            raise ValueError(f"o por_botao {self.id} lista botão desconhecido ou repetido")
        if self.padrao is None:
            return
        if not isinstance(self.padrao, dict) or any(
            b not in self.botoes_da_janela or f not in self.formas for b, f in self.padrao.items()
        ):
            raise ValueError(f"o padrão do por_botao {self.id} é {{botão: forma declarada}}")

    def _conferir_o_livre(self) -> None:
        """O ``livre``: o controle ao vivo da faixa de baixo da janela. O valor são as formas
        gravadas, ``{nome: [[força, segundos], ...]}``, até 16; sem escolhas."""
        if self.escolhas:
            raise ValueError(f"o livre {self.id} não lista escolhas")
        if self.padrao is None:
            return
        if not isinstance(self.padrao, dict) or len(self.padrao) > FORMAS_POR_OPCAO or not all(
                forma_valida(n, f) for n, f in self.padrao.items()):
            raise ValueError(f"o padrão do livre {self.id} é {{nome: [[força 0..1, segundos]]}}")

    @property
    def botoes_da_janela(self) -> tuple[str, ...]:
        """Os botões do ``por_botao``, na ordem declarada; sem a lista, todos os do tópico."""
        return tuple(self.botoes) if self.botoes else BOTOES_DO_POR_BOTAO

    def _conferir_o_deslizante(self) -> None:
        if self.minimo is None or self.maximo is None or self.passo is None:
            raise ValueError(f"o deslizante {self.id} precisa de mínimo, máximo e passo")
        if not self.minimo < self.maximo or self.passo <= 0:
            raise ValueError(f"o deslizante {self.id} tem a faixa ou o passo fora de ordem")
        if isinstance(self.padrao, bool) or not isinstance(self.padrao, (int, float)):
            raise ValueError(f"o deslizante {self.id} precisa do padrão: a posição inicial")
        if not self.minimo <= self.padrao <= self.maximo:
            raise ValueError(f"o padrão do deslizante {self.id} está fora da faixa")

    def _conferir_os_jogos(self) -> None:
        if self.padrao is None:
            return
        if not isinstance(self.padrao, list) or not all(
            isinstance(x, str) and CHAVE_DE_JOGO.match(x) for x in self.padrao
        ):
            raise ValueError(f"o padrão da opção {self.id} é uma lista de chaves de jogo")


class Acao(BaseModel):
    """Um botão da janela que AGE: o clique vai à extensão como o evento ``extensao.acao``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    rotulo: str = Field(min_length=1, max_length=30)
    # A aba da janela em que o botão mora; sem ela, a primeira aba.
    grupo: str | None = Field(default=None, min_length=1, max_length=30)
    icone: Literal["procurar", "testar", "esquecer", "ligar", "atualizar"] | None = None

    @field_validator("id")
    @classmethod
    def _chave(cls, valor: str) -> str:
        if not _CHAVE_DE_LANCADOR.match(valor):
            raise ValueError("id da ação fora da forma de chave")
        return valor


class AcoesDosAparelhos(BaseModel):
    """Os aparelhos que a extensão devolve em ``acessorios.estado``, com uma ação por botão.

    A ação ``ligar`` é a chave do cartão (o ``ligado`` do aparelho); as outras são botões. Com
    ``grupo``, a lista mora naquela aba da janela; sem ele, na coluna «Agora».
    """

    model_config = ConfigDict(extra="forbid")

    grupo: str | None = Field(default=None, min_length=1, max_length=30)
    acoes: list[Acao] = Field(min_length=1, max_length=ACOES_DO_APARELHO)

    @model_validator(mode="after")
    def _sem_grupo_na_acao(self) -> AcoesDosAparelhos:
        if any(a.grupo for a in self.acoes):
            raise ValueError("a ação do aparelho mora no cartão dele e não declara grupo")
        if len({a.id for a in self.acoes}) != len(self.acoes):
            raise ValueError("ação repetida nos aparelhos")
        return self


class ControlesDosAparelhos(BaseModel):
    """A aba em que moram os ``controles`` que cada aparelho do ``acessorios.estado`` declara: um
    cartão por aparelho com controles, e a aba só aparece quando algum deles tem."""

    model_config = ConfigDict(extra="forbid")

    grupo: str = Field(min_length=1, max_length=30)


class Manifesto(BaseModel):
    """O ``hefesto-mod.json`` inteiro."""

    model_config = ConfigDict(extra="forbid")

    id: str
    nome: str = Field(min_length=1, max_length=60)
    versao: str = Field(min_length=1, max_length=40)
    api: str
    licenca: str
    descricao: str = Field(default="", max_length=400)
    # O aviso de uso (marca, jogo comprado, idade): o terminal o mostra antes de instalar, e a
    # tela, no ⋮ do primeiro «sim» da chave; o aviso que muda volta a pedir o «sim».
    aviso: str = Field(default="", max_length=400)
    tipos: list[Literal["processo", "lancador", "tema", "perfil"]] = Field(min_length=1)
    processo: Processo | None = None
    # O preparo (``instalador._preparar``): o comando, relativo à pasta da modificação, que o
    # instalador roda fora da caixa, como quem usa, depois de trocar o código e antes de ligar.
    preparar: list[str] | None = None
    permissoes: list[str] = Field(default_factory=list)
    opcoes: list[Opcao] = Field(default_factory=list)
    # A coluna «Agora» da janela: o que mostrar ao vivo do que a extensão devolve em
    # ``acessorios.estado``. Pede ``ler:acessorios.gesto`` ou ``publicar:acessorios.estado``.
    agora: list[
        Literal["nivel", "perfil", "aparelhos", "conexoes"]  # (noqa-acento): a chave do estado
    ] = Field(default_factory=list)
    # O botão «Parar tudo», sempre à vista: a extensão o recebe como o evento ``extensao.parar``
    # (e, com ``ler:acessorios.gesto``, como o gesto ``para``). O nível e o perfil ficam guardados.
    parar_tudo: bool = False
    # Os botões que agem na hora (``extensao.acao``), as ações de cada aparelho da lista e a aba dos
    # controles de cada um: os três pedem a permissão da coluna «Agora», porque a resposta da
    # extensão é o estado que ela devolve.
    acoes: list[Acao] = Field(default_factory=list, max_length=ACOES_DA_JANELA)
    aparelhos_acoes: AcoesDosAparelhos | None = None
    aparelhos_controles: ControlesDosAparelhos | None = None
    # O conteúdo destes três é das sprints que os consomem (o lançador do
    # KytyPS5, o tema da interface, a ponte dos acessórios): aqui só a forma.
    lancador: dict[str, Any] | None = None
    tema: dict[str, Any] | None = None
    aparelhos: list[dict[str, Any]] | None = None
    # As extensões que esta toma o lugar: ao instalar, as escolhas delas passam e elas saem.
    substitui: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_e_chave(cls, valor: str) -> str:
        if not _CHAVE_DE_LANCADOR.match(valor):
            raise ValueError("id fora da forma: minúsculas, dígitos, - e _, até 32")
        return valor

    @field_validator("api")
    @classmethod
    def _faixa_legivel(cls, valor: str) -> str:
        _clausulas(valor)
        return valor

    @field_validator("licenca")
    @classmethod
    def _spdx(cls, valor: str) -> str:
        if not _SPDX.match(valor):
            raise ValueError("licenca precisa ser um identificador SPDX (ex.: MIT)")
        return valor

    @field_validator("preparar")
    @classmethod
    def _preparo_dentro_da_pasta(cls, valor: list[str] | None) -> list[str] | None:
        if valor is None:
            return None
        if not valor:
            raise ValueError("preparar é uma lista vazia")
        return _comando_dentro_da_pasta(valor, "preparar")

    @field_validator("permissoes")  # (noqa-acento): contrato ASCII
    @classmethod
    def _permissoes_conhecidas(cls, valor: list[str]) -> list[str]:
        estranhas = [p for p in valor if not permissao_valida(p)]
        if estranhas:
            raise ValueError(f"permissão desconhecida: {', '.join(estranhas)}")
        if len(set(valor)) != len(valor):
            raise ValueError("permissão repetida")
        if sum(1 for p in valor if p.startswith("rede:")) > 1:
            raise ValueError("mais de um alcance de rede")
        return valor

    @field_validator("substitui")
    @classmethod
    def _substitui_so_ids_de_fora(cls, valor: list[str]) -> list[str]:
        if len(set(valor)) != len(valor):
            raise ValueError("substitui: id repetido")
        de_fabrica = ids_de_fabrica()
        for mod_id in valor:
            if not _CHAVE_DE_LANCADOR.match(mod_id):
                raise ValueError(f"substitui: «{mod_id}» está fora da forma de id")
            if mod_id in de_fabrica:
                raise ValueError(f"substitui: «{mod_id}» vem com o Hefesto e não se substitui")
        return valor

    @model_validator(mode="after")
    def _processo_quando_e_processo(self) -> Manifesto:
        if self.id in self.substitui:
            raise ValueError("substitui: uma extensão não substitui a si mesma")
        if len(set(self.tipos)) != len(self.tipos):
            raise ValueError("tipo repetido")
        if ("processo" in self.tipos) != (self.processo is not None):
            raise ValueError("o tipo processo e o bloco processo andam juntos")
        if len(set(self.agora)) != len(self.agora):
            raise ValueError("pedaço repetido em agora")
        if self.agora and not set(PERMISSOES_DO_ESTADO) & set(self.permissoes):
            raise ValueError(
                "agora pede a permissão publicar:acessorios.estado ou ler:acessorios.gesto")
        self._conferir_as_acoes_e_o_livre()
        self._conferir_o_lado_e_as_opcoes_do_tema()
        self._conferir_a_opcao_do_css()
        return self

    def _conferir_as_acoes_e_o_livre(self) -> None:
        """As ações, os aparelhos geridos e o ``livre``: a permissão do estado, ids sem repetição,
        um ``livre`` só, e a lista sem ``grupo`` só onde a coluna «Agora» mostra os aparelhos."""
        livres = [o.id for o in self.opcoes if o.tipo == "livre"]
        pedem = [nome for nome, tem in (("acoes", bool(self.acoes)),  # noqa-acento: contrato
                                        ("aparelhos_acoes", self.aparelhos_acoes is not None),
                                        ("aparelhos_controles",
                                         self.aparelhos_controles is not None),
                                        ("o livre", bool(livres))) if tem]
        if pedem and not set(PERMISSOES_DO_ESTADO) & set(self.permissoes):
            raise ValueError(f"{pedem[0]} pede a permissão publicar:acessorios.estado")
        if len(livres) > 1:
            raise ValueError("mais de uma opção livre")
        if len({a.id for a in self.acoes}) != len(self.acoes):
            raise ValueError("ação repetida em acoes")  # noqa-acento: contrato ASCII
        geridos = self.aparelhos_acoes
        if geridos is not None and geridos.grupo is None and "aparelhos" not in self.agora:
            raise ValueError(
                "aparelhos_acoes sem grupo mora na coluna Agora, e agora não lista aparelhos")

    @property
    def opcao_livre(self) -> Opcao | None:
        """A opção ``livre`` (o controle ao vivo da faixa de baixo), se o manifesto declara."""
        return next((o for o in self.opcoes if o.tipo == "livre"), None)

    def _conferir_a_opcao_do_css(self) -> None:
        """A opção ``css`` é a chave do CSS de quem usa: só uma, e só em extensão de tema."""
        css = [o.id for o in self.opcoes if o.tipo == "css"]
        if css and "tema" not in self.tipos:
            raise ValueError(f"a opção {css[0]} é de css, e só uma extensão de tema a tem")
        if len(css) > 1:
            raise ValueError("mais de uma opção de css")

    def _conferir_o_lado_e_as_opcoes_do_tema(self) -> None:
        """O lado dos botões do bloco ``tema`` e a opção que liga a cor ou o lado: só a forma e o
        vínculo. A folha em si é da régua de ``mods/tema.py``, que roda ao ligar."""
        bloco = self.tema
        if not bloco:
            return
        lado = bloco.get(CHAVE_DO_LADO)
        if CHAVE_DO_LADO in bloco and lado not in LADOS_DOS_BOTOES:
            raise ValueError(f"tema.botoes é {' ou '.join(LADOS_DOS_BOTOES)}")
        ligadas = {o.id for o in self.opcoes if o.tipo == "ligado"}
        todas = {o.id for o in self.opcoes}
        for chave, existe in ((CHAVE_DA_OPCAO_DA_COR, any(c in bloco for c in CHAVES_DA_COR)),
                              (CHAVE_DA_OPCAO_DO_LADO, CHAVE_DO_LADO in bloco)):
            if chave not in bloco:
                continue
            if not existe:
                raise ValueError(f"tema.{chave} liga uma escolha que o bloco tema não faz")
            alvo = bloco[chave]
            if not isinstance(alvo, str) or alvo not in todas:
                raise ValueError(f"tema.{chave} aponta para a opção {alvo!r}, que não existe")
            if alvo not in ligadas:
                raise ValueError(f"tema.{chave}: a opção {alvo!r} precisa ser do tipo ligado")

    @property
    def opcao_do_css(self) -> Opcao | None:
        """A opção que liga o CSS de quem usa (a extensão de tema que o aceita), se declara."""
        return next((o for o in self.opcoes if o.tipo == "css"), None)

    @property
    def rede(self) -> str:
        """O alcance de rede pedido; sem a palavra, ``nenhuma``."""
        for p in self.permissoes:
            if p.startswith("rede:"):
                return p.split(":", 1)[1]
        return "nenhuma"

    def api_aceita(self, versao: int = API_DAS_MODIFICACOES) -> bool:
        return aceita_a_api(self.api, versao)


def frase_da_api(manifesto: Manifesto) -> str:
    """A frase da recusa por versão de API, a mesma na linha de comando e na tela."""
    return (
        f"«{manifesto.nome}» pede a porta {manifesto.api}, "
        f"e este Hefesto fala a {API_DAS_MODIFICACOES}."
    )


def _frase_do_esquema(exc: ValidationError) -> str:
    primeiro = exc.errors()[0]
    onde = ".".join(str(p) for p in primeiro.get("loc", ())) or "manifesto"
    if primeiro.get("type") == "extra_forbidden":
        return f"O {NOME_DO_MANIFESTO} tem o campo «{onde}», que este Hefesto não conhece."
    if primeiro.get("type") == "missing":
        return f"O {NOME_DO_MANIFESTO} não tem o campo «{onde}»."
    motivo = str(primeiro.get("msg", "")).removeprefix("Value error, ")
    return f"O {NOME_DO_MANIFESTO} tem «{onde}» inválido: {motivo}."


def ler_manifesto(pasta: Path, *, exigir_api: bool = True) -> Manifesto:
    """Lê e valida o manifesto da pasta; recusa com :class:`ManifestoRecusadoError`."""
    arquivo = pasta / NOME_DO_MANIFESTO
    try:
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestoRecusadoError(f"A pasta não tem o {NOME_DO_MANIFESTO}.") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestoRecusadoError(f"O {NOME_DO_MANIFESTO} não pôde ser lido.") from exc
    except json.JSONDecodeError as exc:
        raise ManifestoRecusadoError(
            f"O {NOME_DO_MANIFESTO} não é JSON válido (linha {exc.lineno})."
        ) from exc
    if not isinstance(bruto, dict):
        raise ManifestoRecusadoError(f"O {NOME_DO_MANIFESTO} precisa ser um objeto JSON.")
    try:
        manifesto = Manifesto.model_validate(bruto)
    except ValidationError as exc:
        raise ManifestoRecusadoError(_frase_do_esquema(exc)) from exc
    if exigir_api and not manifesto.api_aceita():
        raise ManifestoRecusadoError(frase_da_api(manifesto))
    return manifesto


__all__ = [
    "ACAO_DE_LIGAR",
    "ACOES_DA_JANELA",
    "ACOES_DO_APARELHO",
    "ALCANCES_DE_REDE",
    "BOTOES_DO_POR_BOTAO",
    "CANAIS_DE_ESCRITA",
    "COR_HEXA",
    "FUNCOES_POR_PEDIDO",
    "ICONES_DA_ACAO",
    "MODOS_DO_LIVRE",
    "NOME_DAS_ENTRADAS",
    "NOME_DA_FUNCAO",
    "NOME_DO_MANIFESTO",
    "NOME_DO_MOVIMENTO",
    "PERMISSOES_DO_ESTADO",
    "PERMISSOES_SIMPLES",
    "TIPOS",
    "TOPICOS_DE_LEITURA",
    "TOPICOS_DE_PUBLICACAO",
    "Acao",  # noqa-acento: contrato ASCII
    "AcoesDosAparelhos",
    "Manifesto",
    "ManifestoRecusadoError",
    "Opcao",  # (noqa-acento): contrato ASCII
    "Processo",
    "aceita_a_api",
    "endereco_valido",
    "forma_valida",
    "frase_da_api",
    "ler_manifesto",
    "o_que_a_permissao_deixa",
    "permissao_valida",
    "permissoes_novas",
]
