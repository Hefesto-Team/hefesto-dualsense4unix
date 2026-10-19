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
from hefesto_dualsense4unix.utils.maquina import _CHAVE_DE_LANCADOR

NOME_DO_MANIFESTO = "hefesto-mod.json"

#: O que uma modificação pode ser. ``processo`` é a única que leva código; as
#: outras três são declaração, e o Hefesto as lê sem abrir processo nenhum.
TIPOS = ("processo", "lancador", "tema", "perfil")

#: ``ler:<tópico>``: o nome público de cada tópico e os tópicos do barramento
#: que ele entrega. O nome público é o contrato; o do barramento pode mudar.
TOPICOS_DE_LEITURA: dict[str, tuple[str, ...]] = {
    "estado": (EventTopic.STATE_UPDATE,),
    "botoes": (EventTopic.BUTTON_DOWN, EventTopic.BUTTON_UP),
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
    # O que o jogo pede a um brinquedo, passado de uma extensão a outra (`eventos.publicar`). O
    # Hefesto não sabe o que é brinquedo: o vocabulário é por função, e quem assina traduz.
    "jogo.brinquedo": (EventTopic.JOGO_BRINQUEDO,),  # (noqa-acento): contrato ASCII
    # Os gestos do PS que comandam os acessórios (sobe, desce, para, perfil…). A mesma permissão
    # deixa a modificação devolver o estado (`acessorios.estado`), que liga e desliga os gestos.
    "acessorios.gesto": (EventTopic.ACESSORIOS_GESTO,),  # (noqa-acento): contrato ASCII
}

#: ``publicar:<tópico>``: os tópicos que uma extensão pode publicar para as outras
#: (``eventos.publicar``), com o tópico do barramento que cada um entrega. Quem lê pede
#: ``ler:<tópico>``; quem publica pede ``publicar:<tópico>``.
TOPICOS_DE_PUBLICACAO: dict[str, str] = {
    "jogo.brinquedo": EventTopic.JOGO_BRINQUEDO,  # (noqa-acento): contrato ASCII
}

#: As funções de um pedido ao brinquedo, cada uma de 0 a 1; o resto é recusado.
FUNCOES_DO_BRINQUEDO = (
    "vibrar", "girar", "bombear", "empurrar", "sugar", "oscilar", "profundidade", "curso",
    "dedilhar",
)

#: ``escrever:<canal>``: os canais do controle que uma modificação pode pedir.
CANAIS_DE_ESCRITA = ("luz", "vibracao", "gatilho")

#: ``rede:<alcance>``. Sem a palavra, vale ``nenhuma``.
ALCANCES_DE_REDE = ("nenhuma", "local", "internet")

#: As permissões de uma palavra só.
PERMISSOES_SIMPLES = ("bluetooth", "lancador", "tema", "aparelhos")

_O_QUE_DEIXA: dict[str, str] = {
    "ler:estado": "Ler os botões, os eixos, os gatilhos e a bateria a cada tique.",
    "ler:botoes": "Saber quando um botão é apertado e solto.",
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
    "ler:jogo.brinquedo": (  # (noqa-acento): contrato ASCII
        "Receber o que o jogo pede a um brinquedo, passado por outra extensão."
    ),
    "publicar:jogo.brinquedo": (  # (noqa-acento): contrato ASCII
        "Passar a outras extensões o que o jogo pede a um brinquedo."
    ),
    "ler:acessorios.gesto": (  # (noqa-acento): contrato ASCII
        "Receber os gestos do botão PS que comandam os acessórios, sem receber botão nenhum."
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
    "tema": "Trocar as cores da interface.",
    "aparelhos": "Abrir aparelhos ligados ao computador.",
}

#: A cor de uma opção ``cor``: ``#rrggbb``, minúsculas ou maiúsculas.
COR_HEXA = re.compile(r"^#[0-9a-fA-F]{6}$")

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
    """``">=1,<3"`` vira ``[(">=", 1), ("<", 2)]``; número solto vale ``==``."""
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
        primeiro = valor[0]
        if not primeiro.strip():
            raise ValueError("processo.executar começa vazio")
        if primeiro.startswith("/") or ".." in Path(primeiro).parts:
            raise ValueError("processo.executar aponta para fora da pasta da modificação")
        return valor


class Opcao(BaseModel):
    """Uma opção que a modificação declara e a tela mostra no botão de configurações."""

    model_config = ConfigDict(extra="forbid")

    id: str
    rotulo: str = Field(min_length=1, max_length=60)
    tipo: Literal["escolha", "ligado", "numero", "cor", "deslizante", "jogos"]
    escolhas: list[str] = Field(default_factory=list)
    padrao: str | bool | float | list[str] | None = None
    # O ``deslizante`` declara a faixa inteira e a posição inicial (obrigatória e
    # dentro da faixa); os três ficam vazios nos outros tipos.
    minimo: float | None = None
    maximo: float | None = None
    passo: float | None = None
    # A aba interna da janela em que a opção mora; sem ela, a opção vai à primeira aba. Com
    # um grupo só, a janela não desenha aba nenhuma.
    grupo: str | None = Field(default=None, min_length=1, max_length=30)

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
        return self

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


class Manifesto(BaseModel):
    """O ``hefesto-mod.json`` inteiro."""

    model_config = ConfigDict(extra="forbid")

    id: str
    nome: str = Field(min_length=1, max_length=60)
    versao: str = Field(min_length=1, max_length=40)
    api: str
    licenca: str
    descricao: str = Field(default="", max_length=400)
    # O aviso de uso (marca, jogo comprado, idade): a tela o mostra antes de instalar e
    # antes do «sim» que liga; o aviso que muda volta a pedir os dois.
    aviso: str = Field(default="", max_length=400)
    tipos: list[Literal["processo", "lancador", "tema", "perfil"]] = Field(min_length=1)
    processo: Processo | None = None
    permissoes: list[str] = Field(default_factory=list)
    opcoes: list[Opcao] = Field(default_factory=list)
    # A coluna «Agora» da janela: o que mostrar ao vivo do que a extensão devolve em
    # ``acessorios.estado``. Pede ``ler:acessorios.gesto``, a permissão desse retorno.
    agora: list[Literal["nivel", "perfil", "aparelhos"]] = Field(default_factory=list)
    # O botão «Parar tudo», sempre à vista: manda o gesto ``para`` à extensão, que o recebe por
    # ``ler:acessorios.gesto``. O nível e o perfil ficam guardados.
    parar_tudo: bool = False
    # O conteúdo destes três é das sprints que os consomem (o lançador do
    # KytyPS5, o tema da interface, a ponte dos acessórios): aqui só a forma.
    lancador: dict[str, Any] | None = None
    tema: dict[str, Any] | None = None
    aparelhos: list[dict[str, Any]] | None = None

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

    @model_validator(mode="after")
    def _processo_quando_e_processo(self) -> Manifesto:
        if len(set(self.tipos)) != len(self.tipos):
            raise ValueError("tipo repetido")
        if ("processo" in self.tipos) != (self.processo is not None):
            raise ValueError("o tipo processo e o bloco processo andam juntos")
        if len(set(self.agora)) != len(self.agora):
            raise ValueError("pedaço repetido em agora")
        if (self.agora or self.parar_tudo) and "ler:acessorios.gesto" not in self.permissoes:
            raise ValueError("agora e parar_tudo pedem a permissão ler:acessorios.gesto")
        return self

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
    "ALCANCES_DE_REDE",
    "CANAIS_DE_ESCRITA",
    "COR_HEXA",
    "FUNCOES_DO_BRINQUEDO",
    "NOME_DO_MANIFESTO",
    "PERMISSOES_SIMPLES",
    "TIPOS",
    "TOPICOS_DE_LEITURA",
    "TOPICOS_DE_PUBLICACAO",
    "Manifesto",
    "ManifestoRecusadoError",
    "Opcao",  # (noqa-acento): contrato ASCII
    "Processo",
    "aceita_a_api",
    "frase_da_api",
    "ler_manifesto",
    "o_que_a_permissao_deixa",
    "permissao_valida",
    "permissoes_novas",
]
