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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.tema import conferir_o_bloco_e_as_opcoes
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

TIPOS = ("processo", "lancador", "tema", "perfil")

NOME_DAS_ENTRADAS = "controle.entradas"
NOME_DO_MOVIMENTO = "controle.movimento"

TOPICOS_DE_LEITURA: dict[str, tuple[str, ...]] = {
    "estado": (EventTopic.STATE_UPDATE,),
    "botoes": (EventTopic.BUTTON_DOWN, EventTopic.BUTTON_UP),
    "entradas": (NOME_DAS_ENTRADAS,),
    "movimento": (NOME_DO_MOVIMENTO,),
    "bateria": (EventTopic.BATTERY_CHANGE,),
    "conexao": (  # (noqa-acento)
        EventTopic.CONTROLLER_CONNECTED,
        EventTopic.CONTROLLER_DISCONNECTED,
    ),
    "jogo.vibracao": (
        EventTopic.JOGO_VIBRACAO,
        EventTopic.JOGO_FECHOU,
    ),
    "jogo.gatilho": (EventTopic.JOGO_GATILHO,),
    "jogo.haptica": (EventTopic.JOGO_HAPTICA,),
    "perfil.jogo": (EventTopic.PERFIL_TROCOU,),
    "jogo.acessorio": (EventTopic.JOGO_ACESSORIO,),
    "acessorios.gesto": (EventTopic.ACESSORIOS_GESTO,),
    "jogo.som": (EventTopic.JOGO_SOM,),
    "microfone.nivel": (EventTopic.MICROFONE_NIVEL,),
    "jogo.identidade": (EventTopic.JOGO_IDENTIDADE,),
    "modo.aba": (EventTopic.MODO_ABA,),
    "jogo.memoria": ("jogo.memoria",),
}

TOPICOS_DE_PUBLICACAO: dict[str, str] = {
    "jogo.acessorio": EventTopic.JOGO_ACESSORIO,
}

NOME_DA_FUNCAO = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
FUNCOES_POR_PEDIDO = 16

CANAIS_DE_ESCRITA = ("luz", "vibracao", "gatilho")

ALCANCES_DE_REDE = ("nenhuma", "local", "internet")

PERMISSOES_SIMPLES = ("bluetooth", "lancador", "tema", "aparelhos", "jogos")

_O_QUE_DEIXA: dict[str, str] = {
    "ler:estado": "Ler os botões, os eixos, os gatilhos e a bateria do controle do jogador 1.",
    "ler:botoes": "Saber quando um botão é apertado e solto.",
    "ler:entradas": "Ler os analógicos, os gatilhos e o touchpad de cada controle.",
    "ler:movimento": "Ler o giroscópio e o acelerômetro de cada controle.",
    "ler:bateria": "Saber a carga da bateria.",
    "ler:conexao": "Saber quando um controle entra ou sai.",  # (noqa-acento)
    "ler:jogo.vibracao": (
        "Saber a vibração que o jogo pede a cada controle e quando o jogo fecha."
    ),
    "ler:jogo.gatilho": (
        "Saber o efeito de gatilho que o jogo pede a cada controle."
    ),
    "ler:jogo.haptica": (
        "Saber a intensidade da vibração fina que o jogo envia a cada controle."
    ),
    "ler:perfil.jogo": "Saber o perfil, o jogo e o estilo em uso em cada controle.",
    "ler:jogo.acessorio": (
        "Receber o que o jogo pede a um acessório, passado por outra extensão."
    ),
    "publicar:jogo.acessorio": (
        "Passar a outras extensões o que o jogo pede a um acessório."
    ),
    "ler:acessorios.gesto": (
        "Receber os gestos do botão PS que comandam os acessórios, sem receber botão nenhum."
    ),
    "publicar:acessorios.estado": (
        "Mostrar na janela da extensão e na aba Conexões as conexões e os aparelhos ligados."
    ),
    "pedir:luz.pulso": (
        "Pedir que a barra de luz de um controle pulse na cor escolhida, nos perfis «Adulto»."
    ),
    "ler:jogo.som": (
        "Saber quando o som do jogo estala, de que lado e com que timbre, sem receber o áudio."
    ),
    "ler:microfone.nivel": (
        "Saber o volume do microfone de cada controle e se o jogo o escuta, sem receber a voz."
    ),
    "ler:jogo.identidade": "Saber qual jogo está aberto, a versão dele e a loja de onde veio.",
    "ler:jogo.memoria": (
        "Ler do jogo só os valores que a receita declara, como a vida, com a chave «Memória» "
        "daquele jogo ligada."
    ),
    "ler:modo.aba": (
        "Saber em que seções de cada controle o modo que a extensão traz está aceso."
    ),
    "escrever:luz": "Mudar a cor da luz de um controle.",
    "escrever:vibracao": "Fazer um controle vibrar.",
    "escrever:gatilho": "Mudar a resistência dos gatilhos de um controle.",
    "escrever:haptica": "Tocar na vibração fina de um controle os padrões que a extensão traz.",
    "escrever:som": (
        "Tocar no alto-falante de um controle um som curto, ou o estalo que o jogo acabou de fazer."
    ),
    "escrever:leds": "Acender por um instante as cinco luzes de jogador de um controle.",
    "rede:nenhuma": "Sem acesso à rede.",
    "rede:local": "Usar a rede desta casa.",
    "rede:internet": "Usar a internet.",
    "bluetooth": "Falar com aparelhos por Bluetooth.",
    "lancador": "Acrescentar um lançador de jogos e abrir os jogos que ele lista.",
    "tema": "Trocar as cores da interface e o lado dos botões da janela.",
    "aparelhos": "Abrir aparelhos ligados ao computador.",
    "jogos": "Ler as pastas dos jogos instalados na Steam, sem mudar nada.",
}

BOTOES_DO_POR_BOTAO = (
    "cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "l3", "r3",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right", "options", "create",
    "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
)
PASSOS_DA_FORMA = 16
SEGUNDOS_DO_PASSO = 10.0
FORMAS_POR_OPCAO = 16
ACOES_DA_JANELA = 8
ACOES_DO_APARELHO = 6
ACAO_DE_LIGAR = "ligar"
ICONES_DA_ACAO = ("procurar", "testar", "esquecer", "ligar", "atualizar")
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

COR_HEXA = re.compile(r"^#[0-9a-fA-F]{6}$")

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
        "livre", "importar",
    ]
    escolhas: list[str] = Field(default_factory=list)
    padrao: (str | bool | float | list[str] | dict[str, str] | dict[str, list[list[float]]]
             | None) = None
    formas: dict[str, list[list[float]]] = Field(default_factory=dict)
    botoes: list[str] = Field(default_factory=list)
    minimo: float | None = None
    maximo: float | None = None
    passo: float | None = None
    grupo: str | None = Field(default=None, min_length=1, max_length=30)
    modos: bool = False
    aparece_com: dict[str, str | bool | list[str]] | None = None
    dica: str | None = Field(default=None, min_length=1, max_length=120)
    unidade: str | None = Field(default=None, min_length=1, max_length=4)
    zero: str | None = Field(default=None, min_length=1, max_length=24)
    degraus: int | None = Field(default=None, ge=1, le=1000)
    formato: Literal["tema", "logo"] | None = None
    herda: dict[str, dict[str, str | bool]] | None = None

    @field_validator("id")
    @classmethod
    def _chave(cls, valor: str) -> str:
        if not _CHAVE_DE_LANCADOR.match(valor):
            raise ValueError("id da opção fora da forma de chave")
        return valor

    @field_validator("herda")
    @classmethod
    def _herda_de_outra_extensao(cls, valor: dict[str, dict[str, str | bool]] | None
                                 ) -> dict[str, dict[str, str | bool]] | None:
        """``{opção da antiga: {valor antigo em JSON: valor daqui}}``, lido pelo ``substitui``."""
        for antiga, mapa in (valor or {}).items():
            if not _CHAVE_DE_LANCADOR.match(antiga) or not mapa:
                raise ValueError(f"herda: «{antiga}» precisa de um id e de ao menos um valor")
        return valor

    @field_validator("aparece_com", mode="before")
    @classmethod
    def _aparece_com_sem_conversao(cls, bruto: Any, info: ValidationInfo) -> Any:
        """O valor pedido chega como foi escrito: o ``1`` não vira ``true``."""
        for alvo, valor in (bruto.items() if isinstance(bruto, dict) else ()):
            if not (isinstance(valor, (str, bool)) or (
                    isinstance(valor, list) and all(isinstance(v, str) for v in valor))):
                raise ValueError(f"a opção {info.data.get('id')} aparece com {alvo!r} valendo "
                                 f"{valor!r}: um texto, uma lista deles, true ou false")
        return bruto

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
        elif self.unidade is not None or self.zero is not None:
            raise ValueError(f"a opção {self.id} não é deslizante e declara unidade ou zero")
        elif self.degraus is not None:
            raise ValueError(f"a opção {self.id} não é deslizante e declara degraus")
        if (self.tipo == "importar") != (self.formato is not None) or (
                self.tipo == "importar" and self.padrao not in (None, "")):
            raise ValueError(f"a opção {self.id}: importar e formato andam juntos, sem padrão")
        if self.tipo == "jogos":
            self._conferir_os_jogos()
        elif isinstance(self.padrao, list):
            raise ValueError(f"a opção {self.id} não é de jogos e o padrão é uma lista")
        if self.tipo == "por_botao":
            self._conferir_o_por_botao()
        elif self.formas or self.botoes or (isinstance(self.padrao, dict) and self.tipo != "livre"):
            raise ValueError(f"a opção {self.id} não é por_botao e declara formas ou botões")
        if self.aparece_com is not None:
            self._conferir_o_aparece_com()
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

    def _conferir_o_aparece_com(self) -> None:
        """A forma do ``aparece_com`` que se confere sem as outras opções."""
        assert self.aparece_com is not None
        if not self.aparece_com:
            raise ValueError(f"o aparece_com de {self.id} está vazio")
        if self.id in self.aparece_com:
            raise ValueError(f"a opção {self.id} aparece consigo mesma")
        if self.tipo == "livre":
            raise ValueError(f"o livre {self.id} mora na faixa de baixo e não declara aparece_com")

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
        if self.zero is not None and self.minimo != 0:
            raise ValueError(f"o deslizante {self.id} declara zero e o mínimo não é 0")
        if self.degraus is not None and self.unidade is not None:
            raise ValueError(f"o deslizante {self.id} declara degraus e unidade")

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


class LigaDaConexao(BaseModel):
    """O que uma linha da coluna das conexões liga no clique: a opção ``ligado`` (``liga``) e,
    com ``escolha``, a opção ``escolha`` cujo valor a linha oferece pelo nome."""

    model_config = ConfigDict(extra="forbid")

    liga: str = Field(min_length=1, max_length=40)
    escolha: str | None = Field(default=None, min_length=1, max_length=40)


CONEXOES_DA_JANELA = 8

SUFIXOS_DA_PAGINA = (".html", ".htm")
ROTULO_DA_PAGINA = 40
ALTURA_DA_PAGINA = (80, 720)
TETO_DO_ARQUIVO_DA_PAGINA = 1_048_576


class Pagina(BaseModel):
    """A página própria da extensão: um HTML da pasta do código, mostrado isolado abaixo das
    opções da janela, que fala só com a própria extensão (``extensao.mensagem``)."""

    model_config = ConfigDict(extra="forbid")

    arquivo: str = Field(min_length=1, max_length=200)
    rotulo: str = Field(min_length=1, max_length=ROTULO_DA_PAGINA)
    altura_max: int = Field(ge=ALTURA_DA_PAGINA[0], le=ALTURA_DA_PAGINA[1])

    @field_validator("arquivo")
    @classmethod
    def _html_dentro_da_pasta(cls, valor: str) -> str:
        caminho = Path(valor)
        if valor.startswith("/") or "\\" in valor or ".." in caminho.parts:
            raise ValueError("pagina.arquivo aponta para fora da pasta do código")
        if caminho.suffix.lower() not in SUFIXOS_DA_PAGINA:
            raise ValueError("pagina.arquivo precisa ser um arquivo .html")
        return valor


def arquivo_da_pagina(pasta: Path, pagina: Pagina) -> Path:
    """O arquivo da página, conferido: dentro da pasta (inclusive por link), um arquivo comum, até
    ``TETO_DO_ARQUIVO_DA_PAGINA`` bytes e em UTF-8; recusa com :class:`ManifestoRecusadoError`."""
    raiz = pasta.resolve()
    alvo = (pasta / pagina.arquivo).resolve()
    if not alvo.is_relative_to(raiz):
        raise ManifestoRecusadoError("A página da extensão aponta para fora da pasta do código.")
    try:
        if not alvo.is_file():
            raise ManifestoRecusadoError(
                f"A página da extensão ({pagina.arquivo}) não está na pasta do código.")
        if alvo.stat().st_size > TETO_DO_ARQUIVO_DA_PAGINA:
            raise ManifestoRecusadoError("A página da extensão passa de 1 MB.")
        texto = alvo.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestoRecusadoError("A página da extensão não é HTML em UTF-8.") from exc
    except OSError as exc:
        raise ManifestoRecusadoError("A página da extensão não pôde ser lida.") from exc
    if "<" not in texto:
        raise ManifestoRecusadoError("A página da extensão não é HTML.")
    return alvo

ABAS_DO_MODO = ("02", "03", "04", "05", "10")
ROTULO_DO_MODO_DE_ABA = 20
DICA_DO_MODO_DE_ABA = 120
PREFIXO_DO_MODO_DE_EXTENSAO = "extensao:"


class ModoDeAba(BaseModel):
    """O modo que a extensão traz, irmão do Modo automático nas abas listadas."""

    model_config = ConfigDict(extra="forbid")

    id: str
    rotulo: str = Field(min_length=1, max_length=ROTULO_DO_MODO_DE_ABA)
    dica: str = Field(min_length=1, max_length=DICA_DO_MODO_DE_ABA)
    abas: list[Literal["02", "03", "04", "05", "10"]] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _id_curto(cls, valor: str) -> str:
        if not _CHAVE_DE_LANCADOR.match(valor):
            raise ValueError("modos_de_aba: id fora da forma: minúsculas, dígitos, - e _, até 32")
        return valor

    @field_validator("abas")
    @classmethod
    def _abas_sem_repetir(cls, valor: list[str]) -> list[str]:
        if len(set(valor)) != len(valor):
            raise ValueError("modos_de_aba: aba repetida")
        return valor


class Manifesto(BaseModel):
    """O ``hefesto-mod.json`` inteiro."""

    model_config = ConfigDict(extra="forbid")

    id: str
    nome: str = Field(min_length=1, max_length=60)
    versao: str = Field(min_length=1, max_length=40)
    api: str
    licenca: str
    descricao: str = Field(default="", max_length=400)
    aviso: str = Field(default="", max_length=400)
    tipos: list[Literal["processo", "lancador", "tema", "perfil"]] = Field(min_length=1)
    processo: Processo | None = None
    preparar: list[str] | None = None
    permissoes: list[str] = Field(default_factory=list)
    opcoes: list[Opcao] = Field(default_factory=list)
    agora: list[
        Literal["nivel", "perfil", "aparelhos", "conexoes"]  # (noqa-acento)
    ] = Field(default_factory=list)
    conexoes: dict[str, LigaDaConexao] = Field(
        default_factory=dict, max_length=CONEXOES_DA_JANELA)
    parar_tudo: bool = False
    chave: str | None = Field(default=None, min_length=1, max_length=32)
    acoes: list[Acao] = Field(default_factory=list, max_length=ACOES_DA_JANELA)
    aparelhos_acoes: AcoesDosAparelhos | None = None
    aparelhos_controles: ControlesDosAparelhos | None = None
    lancador: dict[str, Any] | None = None
    tema: dict[str, Any] | None = None
    aparelhos: list[dict[str, Any]] | None = None
    substitui: list[str] = Field(default_factory=list)
    estilos: list[str] = Field(default_factory=list)
    modos_de_aba: list[ModoDeAba] = Field(default_factory=list, max_length=1)
    pagina: Pagina | None = None

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

    @field_validator("permissoes")  # (noqa-acento)
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

    @field_validator("estilos")
    @classmethod
    def _estilos_que_se_pedem(cls, valor: list[str]) -> list[str]:
        from hefesto_dualsense4unix.profiles.estilos_de_jogo import PEDIVEIS, POR_CHAVE

        if len(set(valor)) != len(valor):
            raise ValueError("estilos: estilo repetido")
        for chave in valor:
            if chave not in POR_CHAVE:
                raise ValueError(f"estilos: «{chave}» não é um estilo de jogo")
            if chave not in PEDIVEIS:
                raise ValueError(f"estilos: o estilo «{chave}» aparece sempre e não se pede")
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
        self._conferir_a_chave()
        self._conferir_as_ligas()
        self._conferir_o_aparece_com()
        self._conferir_o_lado_e_as_opcoes_do_tema()
        self._conferir_a_opcao_do_css()
        return self

    def _conferir_as_acoes_e_o_livre(self) -> None:
        """As ações, os aparelhos geridos e o ``livre``: a permissão do estado, ids sem repetição,
        um ``livre`` só, e a lista sem ``grupo`` só onde a coluna «Agora» mostra os aparelhos."""
        livres = [o.id for o in self.opcoes if o.tipo == "livre"]
        pedem = [nome for nome, tem in (("acoes", bool(self.acoes)),  # (noqa-acento)
                                        ("aparelhos_acoes", self.aparelhos_acoes is not None),
                                        ("aparelhos_controles",
                                         self.aparelhos_controles is not None),
                                        ("o livre", bool(livres))) if tem]
        if pedem and not set(PERMISSOES_DO_ESTADO) & set(self.permissoes):
            raise ValueError(f"{pedem[0]} pede a permissão publicar:acessorios.estado")
        if len(livres) > 1:
            raise ValueError("mais de uma opção livre")
        if len({a.id for a in self.acoes}) != len(self.acoes):
            raise ValueError("ação repetida em acoes")  # (noqa-acento)
        geridos = self.aparelhos_acoes
        if geridos is not None and geridos.grupo is None and "aparelhos" not in self.agora:
            raise ValueError(
                "aparelhos_acoes sem grupo mora na coluna Agora, e agora não lista aparelhos")

    def _conferir_a_chave(self) -> None:
        """A ``chave`` (o Ligado/Desligado do topo da janela) nomeia uma opção ``ligado`` daqui,
        sempre à vista, e pede a permissão do estado: desligar publica o gesto ``para``, que o
        supervisor confere pelo ``ligado`` do estado."""
        if self.chave is None:
            return
        opcao = next((o for o in self.opcoes if o.id == self.chave), None)
        if opcao is None:
            raise ValueError(f"a chave aponta para a opção {self.chave!r}, que não existe")
        if opcao.tipo != "ligado":
            raise ValueError(f"a chave: a opção {self.chave!r} precisa ser do tipo ligado")
        if opcao.aparece_com:
            raise ValueError(
                f"a chave: a opção {self.chave!r} fica sempre à vista, sem aparece_com")
        if not set(PERMISSOES_DO_ESTADO) & set(self.permissoes):
            raise ValueError("a chave pede a permissão publicar:acessorios.estado")

    def _conferir_as_ligas(self) -> None:
        """Cada linha do mapa das conexões tem id de chave, liga uma opção ``ligado`` daqui (nunca a
        chave do topo) e, com ``escolha``, aponta para uma ``escolha``; e a coluna mostra as
        conexões."""
        if not self.conexoes:
            return
        if "conexoes" not in self.agora:  # (noqa-acento)
            raise ValueError("conexoes pede o pedaço conexoes em agora")  # (noqa-acento)
        por_id = {o.id: o for o in self.opcoes}
        for linha, liga in self.conexoes.items():
            if not _CHAVE_DE_LANCADOR.match(linha):
                raise ValueError(f"a conexão {linha!r} fora da forma de chave")
            opcao = por_id.get(liga.liga)
            if opcao is None or opcao.tipo != "ligado" or opcao.id == self.chave:
                raise ValueError(f"a conexão {linha!r} liga {liga.liga!r}, que não é uma opção "
                                 "ligado daqui (nem a chave)")
            if liga.escolha is not None and getattr(por_id.get(liga.escolha), "tipo",
                                                    None) != "escolha":
                raise ValueError(f"a conexão {linha!r} escolhe {liga.escolha!r}, que não é uma "
                                 "opção escolha daqui")

    @property
    def opcao_da_chave(self) -> Opcao | None:
        """A opção ``ligado`` que a chave do topo da janela liga e desliga, quando declarada."""
        return next((o for o in self.opcoes if o.id == self.chave), None) if self.chave else None

    def _conferir_o_aparece_com(self) -> None:
        """Cada ``aparece_com`` aponta para outra ``escolha`` ou ``ligado`` daqui, com um valor que
        a opção tem, e nenhuma cadeia volta à opção de onde saiu."""
        por_id = {o.id: o for o in self.opcoes}
        for opcao in self.opcoes:
            for alvo, valor in (opcao.aparece_com or {}).items():
                outra = por_id.get(alvo)
                if outra is None:
                    raise ValueError(f"a opção {opcao.id} aparece com {alvo!r}, que não existe")
                if outra.tipo == "ligado":
                    if not isinstance(valor, bool):
                        raise ValueError(
                            f"a opção {opcao.id} aparece com {alvo!r}, que é ligado: true ou false")
                elif outra.tipo == "escolha":
                    valores = valor if isinstance(valor, list) else [valor]
                    if not valores or any(v not in outra.escolhas for v in valores):
                        raise ValueError(f"a opção {opcao.id} aparece com {alvo!r} valendo "
                                         f"{valor!r}, que não é escolha de {alvo!r}")
                else:
                    raise ValueError(f"a opção {opcao.id} aparece com {alvo!r}, que não é "
                                     "escolha nem ligado")
        aponta = {o.id: tuple(o.aparece_com or ()) for o in self.opcoes}
        for inicio in aponta:
            pilha: list[tuple[str, tuple[str, ...]]] = [(inicio, (inicio,))]
            vistos = {inicio}
            while pilha:
                atual, caminho = pilha.pop()
                for alvo in aponta[atual]:
                    if alvo == inicio:
                        raise ValueError(f"a opção {inicio} fecha um ciclo de aparece_com: "
                                         f"{', '.join((*caminho, alvo))}")
                    if alvo not in vistos:
                        vistos.add(alvo)
                        pilha.append((alvo, (*caminho, alvo)))

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
        """O bloco ``tema`` e as opções que ele lê: só a forma e o vínculo (``mods/tema.py``)."""
        conferir_o_bloco_e_as_opcoes(self.tema, self.opcoes, self.tipos)

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
    if manifesto.pagina is not None:
        arquivo_da_pagina(pasta, manifesto.pagina)
    return manifesto


_PEDIDOS: dict[str, Any] = {"marca": None, "estilos": frozenset(), "modos": ()}


def _marca_dos_pedidos(lg: Any, registro: dict[str, Any]) -> tuple[Any, ...]:
    def carimbo(arquivo: Path) -> tuple[int, int]:
        try:
            st = arquivo.stat()
        except OSError:
            return (0, 0)
        return (st.st_mtime_ns, st.st_size)

    return (str(lg.codigo), carimbo(lg.registro), *sorted(
        (e.id, carimbo(lg.codigo / e.id / NOME_DO_MANIFESTO)) for e in registro.values()
        if e.ligada))


def _o_que_a_extensao_pede(pasta: Path) -> list[Manifesto]:
    """O manifesto que abre; o que não abre não roda (o supervisor a impede) e não pede nada."""
    try:
        return [ler_manifesto(pasta)]
    except ManifestoRecusadoError:
        return []


def _pedidos(lugares: Any) -> dict[str, Any]:
    from hefesto_dualsense4unix.mods import instalador

    lg = lugares or instalador.Lugares.do_xdg()
    try:
        registro = instalador.ler_registro(lg.registro)
    except instalador.InstalacaoRecusadaError:
        return {"estilos": frozenset(), "modos": ()}
    marca = _marca_dos_pedidos(lg, registro)
    if _PEDIDOS["marca"] == marca:
        return _PEDIDOS
    lidos = [m for entrada in sorted(registro.values(), key=lambda e: e.id) if entrada.ligada
             for m in _o_que_a_extensao_pede(lg.codigo / entrada.id)]
    _PEDIDOS.update(
        marca=marca,
        estilos=frozenset(chave for m in lidos for chave in m.estilos),
        modos=tuple(
            {"valor": f"{PREFIXO_DO_MODO_DE_EXTENSAO}{m.id}", "rotulo": modo.rotulo,
             "dica": modo.dica, "abas": tuple(modo.abas)}
            for m in lidos for modo in m.modos_de_aba),
    )
    return _PEDIDOS


def estilos_pedidos(lugares: Any = None) -> frozenset[str]:
    """Os estilos que as extensões instaladas e ligadas pedem; a desligada não pede nada."""
    return frozenset(_pedidos(lugares)["estilos"])


def modos_pedidos(lugares: Any = None) -> tuple[dict[str, Any], ...]:
    """Os modos de aba que as extensões instaladas e ligadas trazem, um por extensão, com o
    ``valor`` que o perfil guarda (o prefixo e o id); a desligada não traz nada."""
    return tuple(dict(m) for m in _pedidos(lugares)["modos"])


__all__ = [
    "ABAS_DO_MODO",
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
    "PREFIXO_DO_MODO_DE_EXTENSAO",
    "TIPOS",
    "TOPICOS_DE_LEITURA",
    "TOPICOS_DE_PUBLICACAO",
    "Acao",  # (noqa-acento)
    "AcoesDosAparelhos",
    "Manifesto",
    "ManifestoRecusadoError",
    "ModoDeAba",
    "Opcao",  # (noqa-acento)
    "Pagina",  # (noqa-acento)
    "Processo",
    "aceita_a_api",
    "arquivo_da_pagina",
    "endereco_valido",
    "estilos_pedidos",
    "forma_valida",
    "frase_da_api",
    "ler_manifesto",
    "modos_pedidos",
    "o_que_a_permissao_deixa",
    "permissao_valida",
    "permissoes_novas",
]
