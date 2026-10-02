"""A janela onde ela desenha o gabinete — clique no aparelho, clique na entrada."""
from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping
from typing import Any

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa
from hefesto_dualsense4unix.utils.rotulo_da_entrada import com_artigo, na_frase

logger = get_logger(__name__)

TITULO_DA_JANELA = "Mapear Entradas"
EXPLICACAO = (
    "Clique no aparelho, depois na entrada em que ele está. O Hefesto passa a "
    "chamar cada aparelho pelo número que você escreveu no gabinete."
)

ROTULO_APARELHOS = "O que o Hefesto encontrou"
ROTULO_SEM_FACE = (
    "Você ainda não criou nenhuma face. Crie uma para cada conjunto de "
    "entradas que você enxerga junto: a frente do gabinete, a traseira, o hub."
)
ROTULO_TIRAR = "Tirar daqui"
ROTULO_EXTENSAO = "Tem uma extensão aqui"
ROTULO_NOVA_ENTRADA = "Acrescentar entrada"
ROTULO_NOVA_FACE = "Acrescentar face"
ROTULO_FECHAR = "Fechar"
ROTULO_VAZIA = "vazia"
ROTULO_POR_EXTENSAO = "por extensão"
NOME_DA_FACE_EM_BRANCO = "Nome da face"

DICA_JA_COLOCADO = "Você já colocou este aparelho {onde}."
DICA_ENUMERA = "O sistema enumera este aparelho como {c}."
DICA_EXTENSAO = (
    "Foi você quem disse que há uma extensão aqui. Nenhuma "
    "leitura do sistema distingue isto de um aparelho na "
    "própria entrada do hub."
)

ROTULO_EMBUTIDO = "Dentro da máquina"

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
        "\"Mapear Entrada a Entrada\", eu trato todas como pretas."
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

    def caminho_em(self, numero: str) -> str:
        """O caminho declarado nesta entrada, ou ``""``."""
        return str(self.portas.get(numero, {}).get("caminho") or "")

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
        """Cria uma face com o nome que ELA escreveu. Sem nome, não cria."""
        limpo = nome.strip()
        if not limpo:
            return False
        self.faces.append(
            {"nome": limpo, "portas": [], "perto": False, "alto": False}
        )
        return True

    def tirar_face(self, indice: int) -> bool:
        """Tira uma face e as entradas dela — inclusive as por extensão."""
        if not 0 <= indice < len(self.faces):
            return False
        face = self.faces.pop(indice)
        for numero in face["portas"]:
            for filha in self.filhas_de(numero):
                self._esvaziar(filha)
            self._esvaziar(numero)
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
    return mapa_das_portas.mesa_do_motor(
        MapaDaMesa.model_validate(logica.como_documento()), censo
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
    """O que este quadrado diz sobre o aparelho que está na mão dela."""
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


def rotulo_do_aparelho(aparelho: Aparelho) -> str:
    """A palavra de tela de um aparelho da lista — espécie e caminho."""
    return f"{aparelho.especie} · {aparelho.nome_do_kernel}"


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):  # pragma: no cover - ambiente sem PyGObject
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class JanelaDoMapaDaMesa(Gtk.Window):  # type: ignore[misc]
        """A janela do desenho. Todo estado mora na :class:`LogicaDoMapa`."""

        def __init__(
            self,
            host: Any,
            mapa: MapaDaMesa,
            censo: Censo,
            *,
            ao_fechar: Callable[[], None] | None = None,
        ) -> None:
            Gtk.Window.__init__(self, title=_(TITULO_DA_JANELA))
            self._host = host
            self._censo = censo
            self._ao_fechar = ao_fechar
            self.logica = LogicaDoMapa(mapa)
            self._em_foco = ""
            self.quadrados: dict[str, Any] = {}
            self.aparelhos: dict[str, Any] = {}
            self.vereditos: dict[str, motor.Veredito] = {}
            self.confissao: tuple[str, ...] = ()
            self._bancada = mapa_das_portas.Bancada(
                mesa=motor.Mesa(aparelhos=(), faces=(), mapa={}, leitura={})
            )

            self.set_default_size(720, 520)
            with contextlib.suppress(Exception):
                self.set_transient_for(getattr(host, "window", None))
            self.connect("delete-event", self._ao_fechar_a_janela)

            self._raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self._raiz.set_margin_start(12)
            self._raiz.set_margin_end(12)
            self._raiz.set_margin_top(12)
            self._raiz.set_margin_bottom(12)
            self.add(self._raiz)

            self._caixa_aparelhos = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            self._caixa_faces = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=8
            )
            self._caixa_confissao = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self._montar()
            self._redesenhar()


        def _montar(self) -> None:
            explicacao = Gtk.Label(label=_(EXPLICACAO))
            explicacao.set_xalign(0.0)
            explicacao.set_halign(Gtk.Align.START)
            explicacao.set_line_wrap(True)
            explicacao.set_max_width_chars(84)
            self._raiz.pack_start(explicacao, False, False, 0)

            corpo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            esquerda = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            titulo = Gtk.Label(label=_(ROTULO_APARELHOS))
            titulo.set_xalign(0.0)
            esquerda.pack_start(titulo, False, False, 0)
            esquerda.pack_start(self._caixa_aparelhos, False, False, 0)
            corpo.pack_start(esquerda, False, False, 0)
            corpo.pack_start(self._caixa_faces, True, True, 0)
            self._raiz.pack_start(corpo, True, True, 0)
            self._raiz.pack_start(self._caixa_confissao, False, False, 0)

            acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.botao_tirar = Gtk.Button(label=_(ROTULO_TIRAR))
            self.botao_tirar.connect("clicked", self._ao_tirar)
            acoes.pack_start(self.botao_tirar, False, False, 0)
            self.botao_extensao = Gtk.Button(label=_(ROTULO_EXTENSAO))
            self.botao_extensao.connect("clicked", self._ao_acrescentar_extensao)
            acoes.pack_start(self.botao_extensao, False, False, 0)
            self._raiz.pack_start(acoes, False, False, 0)

            nova_face = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.campo_da_face = Gtk.Entry()
            self.campo_da_face.set_placeholder_text(_(NOME_DA_FACE_EM_BRANCO))
            self.campo_da_face.set_width_chars(16)
            nova_face.pack_start(self.campo_da_face, False, False, 0)
            botao_face = Gtk.Button(label=_(ROTULO_NOVA_FACE))
            botao_face.connect("clicked", self._ao_acrescentar_face)
            nova_face.pack_start(botao_face, False, False, 0)
            self._raiz.pack_start(nova_face, False, False, 0)

            espera = Gtk.Label(label=_(ESPERA_O_APLICAR))
            espera.set_xalign(0.0)
            espera.set_line_wrap(True)
            espera.set_max_width_chars(84)
            with contextlib.suppress(Exception):
                espera.get_style_context().add_class("dim-label")
            self._raiz.pack_start(espera, False, False, 0)

            rodape = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            fechar = Gtk.Button(label=_(ROTULO_FECHAR))
            fechar.connect("clicked", lambda _b: self.close())
            rodape.pack_end(fechar, False, False, 0)
            self._raiz.pack_start(rodape, False, False, 0)


        def _redesenhar(self) -> None:
            """Redesenha a lista e as faces a partir do rascunho."""
            self._remontar_a_bancada()
            self._desenhar_aparelhos()
            self._desenhar_faces()
            self._desenhar_confissao()
            self.botao_tirar.set_sensitive(
                bool(self._em_foco) and bool(self.logica.caminho_em(self._em_foco))
            )
            self.botao_extensao.set_sensitive(
                bool(self._em_foco) and self._em_foco.isdigit()
            )
            self.show_all()

        def _remontar_a_bancada(self) -> None:
            """A mesa do motor, refeita a cada gesto — o desenho mudou de forma."""
            try:
                self._bancada = bancada_do_rascunho(self.logica, self._censo)
            except Exception:
                logger.debug("o rascunho do mapa ainda não monta a mesa", exc_info=True)

        def _desenhar_confissao(self) -> None:
            """O que o desenho não diz, escrito — nunca calado."""
            for filho in self._caixa_confissao.get_children():
                self._caixa_confissao.remove(filho)
            self.confissao = confissao_do_desenho(self._bancada)
            if not self.confissao:
                return
            for texto in (_(CONFISSAO_ABERTURA), *self.confissao):
                linha = Gtk.Label(label=texto)
                linha.set_xalign(0.0)
                linha.set_line_wrap(True)
                linha.set_max_width_chars(84)
                with contextlib.suppress(Exception):
                    linha.get_style_context().add_class("dim-label")
                self._caixa_confissao.pack_start(linha, False, False, 0)

        def _desenhar_aparelhos(self) -> None:
            for filho in self._caixa_aparelhos.get_children():
                self._caixa_aparelhos.remove(filho)
            self.aparelhos = {}
            for aparelho in aparelhos_para_colocar(self._censo):
                botao = Gtk.ToggleButton(label=rotulo_do_aparelho(aparelho))
                botao.set_active(self.logica.escolhido == aparelho.nome_do_kernel)
                onde = self.logica.entrada_do_caminho(aparelho.nome_do_kernel)
                if onde:
                    botao.set_tooltip_text(
                        _(DICA_JA_COLOCADO).format(onde=com_artigo(na_frase(onde), em=True))
                    )
                botao.connect("clicked", self._ao_escolher, aparelho.nome_do_kernel)
                self._caixa_aparelhos.pack_start(botao, False, False, 0)
                self.aparelhos[aparelho.nome_do_kernel] = botao

        def _desenhar_faces(self) -> None:
            for filho in self._caixa_faces.get_children():
                self._caixa_faces.remove(filho)
            self.quadrados = {}
            self.vereditos = {}
            if not self.logica.faces:
                vazio = Gtk.Label(label=_(ROTULO_SEM_FACE))
                vazio.set_xalign(0.0)
                vazio.set_line_wrap(True)
                vazio.set_max_width_chars(60)
                self._caixa_faces.pack_start(vazio, False, False, 0)
                return
            for indice, face in enumerate(self.logica.faces):
                self._caixa_faces.pack_start(
                    self._desenhar_uma_face(indice, face), False, False, 0
                )

        def _desenhar_uma_face(self, indice: int, face: dict[str, Any]) -> Any:
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            cabecalho = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            nome = Gtk.Label(label=face["nome"])
            nome.set_xalign(0.0)
            cabecalho.pack_start(nome, False, False, 0)
            mais = Gtk.Button(label=_(ROTULO_NOVA_ENTRADA))
            mais.connect("clicked", self._ao_acrescentar_entrada, indice)
            cabecalho.pack_start(mais, False, False, 0)
            caixa.pack_start(cabecalho, False, False, 0)

            grade = Gtk.Grid()
            grade.set_column_spacing(4)
            grade.set_row_spacing(4)
            for posicao, numero in enumerate(face["portas"]):
                grade.attach(
                    self._quadrado(numero),
                    posicao % _COLUNAS,
                    posicao // _COLUNAS,
                    1,
                    1,
                )
            caixa.pack_start(grade, False, False, 0)
            return caixa

        def _quadrado(self, numero: str) -> Any:
            """Um quadrado da fileira, com as filhas por extensão dentro dele."""
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.pack_start(self._botao_de_entrada(numero), False, False, 0)
            for filha in self.logica.filhas_de(numero):
                caixa.pack_start(
                    self._botao_de_entrada(filha, extensao=True), False, False, 0
                )
            return caixa

        def _botao_de_entrada(self, numero: str, *, extensao: bool = False) -> Any:
            caminho = self.logica.caminho_em(numero)
            corpo = self._o_que_esta_em(caminho)
            if extensao:
                corpo = f"{corpo}\n{_(ROTULO_POR_EXTENSAO)}"
            veredito = self._veredito_em(numero)
            if veredito is not None:
                corpo = f"{corpo}\n{veredito.texto}"
            botao = Gtk.Button(label=f"{numero}\n{corpo}")
            with contextlib.suppress(Exception):
                botao.get_child().set_justify(Gtk.Justification.CENTER)
            botao.set_size_request(84, 56)
            dizeres: list[str] = []
            if extensao:
                dizeres.append(
                    _(DICA_EXTENSAO)
                )
            elif caminho:
                dizeres.append(
                    _(DICA_ENUMERA).format(c=caminho)
                )
            if veredito is not None and veredito.porque:
                dizeres.append(veredito.porque)
            if dizeres:
                botao.set_tooltip_text("\n".join(dizeres))
            botao.connect("clicked", self._ao_clicar_na_entrada, numero)
            self.quadrados[numero] = botao
            return botao

        def _veredito_em(self, numero: str) -> motor.Veredito | None:
            """O juízo do motor sobre esta entrada, guardado para quem olhar."""
            if not self.logica.escolhido:
                return None
            veredito = veredito_do_quadrado(
                self._bancada, numero, self.logica.escolhido
            )
            if veredito is not None:
                self.vereditos[numero] = veredito
            return veredito

        def _o_que_esta_em(self, caminho: str) -> str:
            if not caminho:
                return _(ROTULO_VAZIA)
            for aparelho in self._censo.conectados():
                if aparelho.nome_do_kernel == caminho:
                    return aparelho.especie
            return caminho

        # -- gestos --------------------------------------------------------

        def _ao_escolher(self, _botao: Any, caminho: str) -> None:
            self.logica.escolher(caminho)
            self._redesenhar()

        def _ao_clicar_na_entrada(self, _botao: Any, numero: str) -> None:
            self._em_foco = numero
            if self.logica.escolhido:
                self.logica.colocar(numero)
                self._acumular()
            self._redesenhar()

        def _ao_tirar(self, _botao: Any) -> None:
            if self._em_foco and self.logica.tirar(self._em_foco):
                self._acumular()
            self._redesenhar()

        def _ao_acrescentar_extensao(self, _botao: Any) -> None:
            if self._em_foco and self.logica.acrescentar_extensao(self._em_foco):
                self._acumular()
            self._redesenhar()

        def _ao_acrescentar_entrada(self, _botao: Any, indice: int) -> None:
            if self.logica.acrescentar_entrada(indice):
                self._acumular()
            self._redesenhar()

        def _ao_acrescentar_face(self, _botao: Any) -> None:
            if self.logica.acrescentar_face(self.campo_da_face.get_text()):
                self.campo_da_face.set_text("")
                self._acumular()
            self._redesenhar()

        def _ao_fechar_a_janela(self, *_args: Any) -> bool:
            if self._ao_fechar is not None:
                with contextlib.suppress(Exception):
                    self._ao_fechar()
            return False

        def _acumular(self) -> None:
            acumular_no_rascunho(self._host, self.logica)

else:  # pragma: no cover - ambiente sem PyGObject

    class JanelaDoMapaDaMesa:  # type: ignore[no-redef]
        """Sem GTK não há janela — e quem chama não pode cair por isso."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PyGObject não está disponível nesta máquina")


def acumular_no_rascunho(host: Any, logica: LogicaDoMapa) -> None:
    """Escreve o mapa inteiro em ``host._maquina_pendente``, sob a chave ``mapa``."""
    with contextlib.suppress(Exception):
        pendente = getattr(host, "_maquina_pendente", None)
        documento: dict[str, Any] = (
            dict(pendente) if isinstance(pendente, Mapping) else {}
        )
        documento["mapa"] = logica.como_documento()
        host._maquina_pendente = documento
    marcar = getattr(host, "_marcar_declaracao_por_aplicar", None)
    if marcar is not None:
        with contextlib.suppress(Exception):
            marcar()


__all__ = [
    "JanelaDoMapaDaMesa",
    "LogicaDoMapa",
    "acumular_no_rascunho",
    "aparelhos_para_colocar",
    "bancada_do_rascunho",
    "classe_do_escolhido",
    "confissao_do_desenho",
    "rotulo_do_aparelho",
    "veredito_do_quadrado",
]
