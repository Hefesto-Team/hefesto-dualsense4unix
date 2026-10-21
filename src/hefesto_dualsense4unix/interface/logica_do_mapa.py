"""A janela onde ela desenha o gabinete — clique no aparelho, clique na entrada."""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
    MAXIMO_DO_NOME_DA_ENTRADA,
    com_artigo,
    na_frase,
    nome_que_vale,
)

logger = get_logger(__name__)

TITULO_DA_JANELA = "Mapear Entradas"
EXPLICACAO = (
    "Clique no aparelho, depois na entrada em que ele está. O Hefesto passa a "
    "chamar cada aparelho pelo número que você escreveu no gabinete."
)

ROTULO_APARELHOS = "O que o Hefesto encontrou"
ROTULO_SEM_FACE = "Você ainda não criou nenhuma face."
DICA_SEM_FACE = (
    "Crie uma para cada conjunto de entradas que você enxerga junto: a frente "
    "do gabinete, a traseira, o hub."
)
ROTULO_TIRAR = "Tirar daqui"
ROTULO_EXTENSAO = "Tem uma extensão aqui"
ROTULO_NOVA_ENTRADA = "Acrescentar entrada"
ROTULO_NOVA_FACE = "Acrescentar face"
ROTULO_FECHAR = "Fechar"
ROTULO_VAZIA = "Vazia"
ROTULO_POR_EXTENSAO = "Por extensão"
NOME_DA_FACE_EM_BRANCO = "Nome da face"
ROTULO_NOVO_HUB = "Acrescentar hub"
ROTULO_LIGADO = "Ligado"
NOME_DO_HUB_EM_BRANCO = "Nome do hub (opcional)"
ROTULO_ACRESCENTAR = "Acrescentar"
ROTULO_CANCELAR = "Cancelar"
DICA_NOVO_HUB = "Pergunta em qual entrada o hub está ligado e acrescenta a face dele."

DICA_JA_COLOCADO = "Você já colocou este aparelho {onde}."
DICA_ENUMERA = "O sistema enumera este aparelho como {c}."
DICA_EXTENSAO = (
    "Foi você quem disse que há uma extensão aqui. Nenhuma "
    "leitura do sistema distingue isto de um aparelho na "
    "própria entrada do hub."
)


ESPERA_O_APLICAR = (
    "O desenho vale quando você clicar em Aplicar, na barra de baixo da janela."
)

GRAVA_NO_CLIQUE = "Tudo aqui é gravado no clique."

_LETRAS = "abcdefghijklmnopqrstuvwxyz"

_COLUNAS = 7

CONFISSAO_ABERTURA = "O que eu não consegui conferir neste desenho:"
CONFISSAO: dict[str, str] = {
    mapa_das_portas.LACUNA_POSICAO: (
        "em que ponto da fileira cada entrada fica. Sem isso eu não conto a "
        "folga entre dois adaptadores de rádio, e duas entradas nas pontas "
        "opostas do hub recebem o mesmo juízo de duas coladas."
    ),
    mapa_das_portas.LACUNA_PAR: (
        "quais entradas ficam coladas no metal: alguma face está com um "
        "número sobrando. Eu as leio de duas em duas, na ordem em que você as "
        "desenhou."
    ),
    mapa_das_portas.LACUNA_VELOCIDADE: (
        "quais entradas são azuis. Enquanto você não passar por "
        "\"Mapear entrada a entrada\", eu trato todas como pretas."
    ),
    mapa_das_portas.LACUNA_REGIAO: (
        "se alguma face é do gabinete ou de um hub — nenhuma entrada dela tem "
        "aparelho declarado."
    ),
    mapa_das_portas.LACUNA_ESPECIE: (
        "o que é algum dos aparelhos da lista: o sistema não diz o que ele é, "
        "e sobre ele eu não tenho juízo nenhum."
    ),
}


class LogicaDoMapa:
    """O rascunho do gabinete e os quatro gestos que o mudam — sem GTK."""

    def __init__(self, mapa: MapaDaMesa) -> None:
        bruto = mapa.model_dump(mode="json")
        self.faces: list[dict[str, Any]] = [
            {
                "nome": face.get("nome", ""),
                "portas": list(face.get("portas", [])),
                "perto": bool(face.get("perto", False)),
                "alto": bool(face.get("alto", False)),
            }
            for face in bruto.get("faces", [])
        ]
        self.portas: dict[str, dict[str, Any]] = {
            numero: dict(valor) for numero, valor in bruto.get("portas", {}).items()
        }
        self.escolhido: str = ""
        #: A pergunta curta do «Acrescentar hub» está aberta? É estado de tela, não vai ao disco.
        self.perguntando_o_hub: bool = False


    def como_documento(self) -> dict[str, Any]:
        """O rascunho no formato do ``maquina.json``, pronto para o rodapé."""
        return {
            "faces": [
                {
                    "nome": face["nome"],
                    "portas": list(face["portas"]),
                    "perto": bool(face.get("perto", False)),
                    "alto": bool(face.get("alto", False)),
                }
                for face in self.faces
            ],
            "portas": {
                numero: dict(valor) for numero, valor in sorted(self.portas.items())
            },
        }


    def filhas_de(self, numero: str) -> list[str]:
        """As entradas que nascem de uma extensão plugada nesta."""
        return sorted(
            outro
            for outro, valor in self.portas.items()
            if valor.get("filha_de") == numero and outro != numero
        )

    def entrada_do_caminho(self, caminho: str) -> str:
        """Em que entrada este aparelho já está — ``""`` se em nenhuma."""
        if not caminho:
            return ""
        for numero, valor in sorted(self.portas.items()):
            if valor.get("caminho") == caminho:
                return numero
        return ""


    def escolher(self, caminho: str) -> None:
        """Primeiro tempo: escolhe o aparelho. Escolher de novo desescolhe."""
        self.escolhido = "" if self.escolhido == caminho else caminho

    def colocar(self, numero: str) -> bool:
        """Segundo tempo: põe o aparelho escolhido nesta entrada."""
        if not self.escolhido or numero not in self._todas_as_entradas():
            return False
        anterior = self.entrada_do_caminho(self.escolhido)
        if anterior and anterior != numero:
            self._esvaziar(anterior)
        entrada = self.portas.setdefault(numero, {})
        entrada["caminho"] = self.escolhido
        self.escolhido = ""
        return True

    def tirar(self, numero: str) -> bool:
        """Tira o aparelho desta entrada — escrevendo ``None``, não sumindo."""
        if numero not in self.portas:
            return False
        if not self.portas[numero].get("caminho"):
            return False
        self._esvaziar(numero)
        return True

    def acrescentar_extensao(self, numero: str) -> str:
        """Cria a entrada-filha desta entrada — ``15`` vira ``15a``."""
        if numero not in self._todas_as_entradas() or not numero.isdigit():
            return ""
        usadas = {filha[len(numero) :] for filha in self.filhas_de(numero)}
        for letra in _LETRAS:
            if letra in usadas:
                continue
            nova = f"{numero}{letra}"
            self.portas[nova] = {"caminho": None, "filha_de": numero}
            return nova
        return ""

    def entradas_para_o_hub(self) -> list[str]:
        """As entradas onde um hub pode estar ligado: as de número, sem letra (não há neta)."""
        return sorted((n for n in self._todas_as_entradas() if n.isdigit()), key=int)

    def perguntar_o_hub(self) -> bool:
        """Abre a pergunta do hub. Sem entrada no desenho não há onde ligar: recusa."""
        self.perguntando_o_hub = bool(self.entradas_para_o_hub())
        return self.perguntando_o_hub

    def desistir_do_hub(self) -> None:
        """Fecha a pergunta sem acrescentar nada."""
        self.perguntando_o_hub = False

    def acrescentar_hub(self, numero: str, nome: str = "") -> str:
        """Liga um hub nesta entrada: a filha dela (`15` vira `15a`), com o nome, se houver.

        Nome acima do limite recusa e a pergunta continua aberta. O nome que é só o
        número da entrada não vale e não é gravado (`nome_que_vale`).
        """
        limpo = " ".join(str(nome or "").split())
        if len(limpo) > MAXIMO_DO_NOME_DA_ENTRADA:
            return ""
        nova = self.acrescentar_extensao(numero)
        if not nova:
            return ""
        valido = nome_que_vale(nova, limpo)
        if valido:
            self.portas[nova]["nome"] = valido
        self.perguntando_o_hub = False
        return nova

    def acrescentar_entrada(self, indice: int) -> str:
        """Acrescenta a próxima entrada livre a esta face."""
        if not 0 <= indice < len(self.faces):
            return ""
        usados = {
            int(numero)
            for numero in self._todas_as_entradas()
            if numero.isdigit()
        }
        proximo = 1
        while proximo in usados:
            proximo += 1
        numero = str(proximo)
        self.faces[indice]["portas"].append(numero)
        return numero

    def acrescentar_face(self, nome: str) -> bool:
        """Cria uma face com o nome que O usuário escreveu. Sem nome, não cria."""
        limpo = nome.strip()
        if not limpo:
            return False
        self.faces.append(
            {"nome": limpo, "portas": [], "perto": False, "alto": False}
        )
        return True


    def _todas_as_entradas(self) -> set[str]:
        numeros = {numero for face in self.faces for numero in face["portas"]}
        numeros.update(self.portas)
        return numeros

    def _esvaziar(self, numero: str) -> None:
        entrada = self.portas.setdefault(numero, {})
        entrada["caminho"] = None
        if "filha_de" not in entrada:
            entrada["filha_de"] = None


def bancada_do_rascunho(logica: LogicaDoMapa, censo: Censo) -> mapa_das_portas.Bancada:
    """A mesa do motor montada a partir do RASCUNHO — não do disco."""
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return mapa_das_portas.mesa_do_motor(
        MapaDaMesa.model_validate(logica.como_documento()), censo,
        mapa_das_portas.tipos_declarados(carregar_maquina()),
    )


def classe_do_escolhido(bancada: mapa_das_portas.Bancada, caminho: str) -> str:
    """A classe que o motor julga para o aparelho na mão — ``""`` se ele não a tem.

    ``""`` acontece de verdade e não é borda: o Archer T3U desta bancada
    declina de se classificar e o DualSense por cabo é HID sem protocolo de
    arranque. Para eles não há regra no motor, e o quadrado cala em vez de
    julgar pelo aparelho errado.
    """
    if not caminho:
        return ""
    for aparelho in bancada.mesa.aparelhos:
        if aparelho.id == caminho:
            return aparelho.classe
    return ""


def veredito_do_quadrado(
    bancada: mapa_das_portas.Bancada, numero: str, escolhido: str
) -> motor.Veredito | None:
    """O que este quadrado diz sobre o aparelho que está na mão do usuário."""
    entrada = motor.por_num(bancada.mesa.faces, numero)
    if entrada is None:
        return None
    return motor.julgar(
        entrada,
        classe_do_escolhido(bancada, escolhido) or None,
        bancada.mesa,
        escolhido or None,
    )


def confissao_do_desenho(bancada: mapa_das_portas.Bancada) -> tuple[str, ...]:
    """As frases do que o desenho não diz, na ordem das chaves."""
    return tuple(
        _(CONFISSAO[chave]) if chave in CONFISSAO else chave
        for chave in bancada.lacunas
    )


def aparelhos_para_colocar(censo: Censo) -> tuple[Aparelho, ...]:
    """Tudo que o censo achou, menos os hubs-raiz — na ordem do barramento."""
    return censo.conectados()


def na_entrada(numero: str, nome: str | None = None) -> str:
    """«na Entrada 15» sem nome, «na entrada Meio» com o nome dado: a grafia é do dono."""
    return com_artigo(na_frase(numero, nome), em=True)


def rotulo_do_aparelho(aparelho: Aparelho) -> str:
    """A palavra de tela de um aparelho da lista — espécie e caminho."""
    return f"{aparelho.especie} · {aparelho.nome_do_kernel}"


__all__ = [
    "LogicaDoMapa",
    "aparelhos_para_colocar",
    "bancada_do_rascunho",
    "classe_do_escolhido",
    "confissao_do_desenho",
    "na_entrada",
    "rotulo_do_aparelho",
    "veredito_do_quadrado",
]
