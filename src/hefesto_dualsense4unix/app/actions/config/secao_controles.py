"""Seção 1 da aba Configurações — um card por controle da mesa.

Aqui entra o que o aparelho não anuncia e o produto não deduz: o modo em que um
controle não-Sony foi ligado, o rótulo dos botões, e a cor do plástico quando a
leitura falha. Todo campo nasce em "não sei", e "não sei" é resposta válida.

TERRITÓRIO DE CONFIG-06. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

DE ONDE VEM CADA COISA NA TELA
-------------------------------

* **os controles adotados** — `daemon.state_full`, que é o único lugar onde o
  `player_slot` de um DualSense existe (`ipc_handlers.py:3058`); o
  `controller.list` devolve a lista sem ele;
* **os que o Hefesto só vê** — `controller.list {external: true}`, que já traz o
  `player_slot` deles resolvido pelo registro do daemon;
* **a cor do plástico** — lida DO APARELHO, pelo cabo, por
  `integrations/cor_do_plastico` (decisão T6). Antes desta leva a leitura vivia
  fora do aplicativo, em `scripts/ensaios/`, e toda linha "Cor:" nasceria em
  "Não sei" — inclusive nos controles no cabo, que o desenho mostra com a cor
  lida;
* **o resto** — declaração dela, acumulada em `_maquina_pendente` e gravada
  pelo "Aplicar" do rodapé (`D-A4`: a aba é diferida, o clique só marca).

DUAS CHAMADAS, E NUNCA NUM TIQUE
---------------------------------

Os tiques desta casa são de 100 ms, 500 ms e 2 s. Enumerar o `/dev/input`
inteiro e sondar quem segura cada `hidraw` custa de 10 a 40 ms mais um
subprocesso (`ipc_handlers.py:3679`), e nada disso muda entre dois quadros. A
leitura roda ao ENTRAR na aba, e só.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import rotulo_de_apoio
from hefesto_dualsense4unix.app.actions.external_controllers import (
    ID_DE_OUTRA_COR,
    chave_de_maquina,
    declaracoes_do_aparelho,
    external_key,
    marca_e_via,
    modo_deduzido,
    slot_of,
    via_do_controle,
)
from hefesto_dualsense4unix.app.ipc_bridge import (
    call_async,
    identity_number_set,
    run_in_thread,
)
from hefesto_dualsense4unix.app.widgets.external_card import (
    DadosDoControle,
    ExternalCard,
)
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    cor_do_nome,
    ler_pelo_cabo,
    tom_para_a_borda,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import carregar_maquina, fundir_declaracao

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "Os controles"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
    "por dentro marca qual está selecionado no cabeçalho da janela."
)

#: O nome que o `_REFRESH_POR_ABA` de `app/app.py` procura para reler a mesa ao
#: ENTRAR na aba. Ele é pendurado no hospedeiro por `montar`, como o
#: `_reexaminar_a_mesa` de CONFIG-02 e o `_refresh_saude_da_mesa` de CONFIG-09.
NOME_DO_REFRESH = "_refresh_config_controles"

#: Quantas colunas de card a grade tem. FIXO, e não `Gtk.FlowBox`: o FlowBox
#: decide as colunas pela largura que RECEBE, o rolador lhe entrega a MÍNIMA, e
#: o resultado medido em `segmented_selector.py:214-231` foi 606px de altura
#: empilhada virando o piso de TODAS as abas do notebook.
#:
#: Três, e não cinco como no desenho: um card pede 208px de largura mínima, e a
#: janela abre com 1180px sem rolagem horizontal. Cinco cards lado a lado com a
#: lista de cor de três colunas dentro não cabem — e o portão
#: `test_config_01_a_aba_nasce_vazia::test_a_aba_montada_cabe_na_largura_da_janela`
#: reprova antes de a tela existir. Com três colunas, a mesa de cinco vira duas
#: fileiras, e a altura igual continua valendo (é o `row_homogeneous`).
COLUNAS = 3

#: Espaço entre cards, o mesmo `--sp-3` do desenho.
_ESPACAMENTO = 10

#: O que a seção diz quando não há controle nenhum.
#:
#: A segunda frase é a resposta on-screen à medição 3 do aceite desta sprint
#: ("em modo D-input, o Hefesto vê o controle?"), cuja previsão é NÃO com grau
#: MÉDIO. Enquanto a medição não acontece, o estado vazio precisa ser
#: *"não estou vendo nada e sei por quê"* — que é entrega, não falha.
FRASE_SEM_CONTROLE = (
    "Nenhum controle na mesa agora. Conecte um pelo cabo ou pelo rádio e entre "
    "nesta aba de novo. Um controle ligado em modo D-input pode não aparecer "
    "aqui — esse caso ainda não foi medido nesta casa."
)

#: O que a seção diz quando o Hefesto não respondeu.
FRASE_SEM_RESPOSTA = (
    "O Hefesto está desligado, então não dá para saber quais controles estão na "
    "mesa. Ligue-o na aba Sistema e entre nesta aba de novo."
)

#: Título de um card sem número. "Jogador —" leria como defeito; esta frase diz
#: a mesma coisa e diz que é normal (é o estado dos primeiros segundos, enquanto
#: o registro do daemon ainda não opinou).
TITULO_SEM_NUMERO = "Sem número ainda"


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.

    O último gesto pendura `_refresh_config_controles` no hospedeiro. Ele
    NASCE aqui e não no `mixin.py` pela mesma razão do refresher da mesa: o
    montador da aba não conhece uma linha do que há dentro de nenhuma seção.
    """
    painel = _PainelDosControles(host)
    painel.montar(caixa)
    setattr(host, NOME_DO_REFRESH, painel.reexaminar)


class _PainelDosControles:
    """A grade de cards e as duas leituras que a preenchem.

    Uma instância por montagem. A grade mora dentro de uma caixa que FICA:
    reexaminar esvazia a caixa e a preenche de novo, em vez de mexer na página —
    assim a ordem dos filhos da seção nunca muda e a tela não pula.
    """

    def __init__(self, host: Any) -> None:
        self._host = host
        self._caixa: Any = None
        self._estado: dict[str, Any] = {}
        #: `{uniq: CorDoPlastico | None}` — `None` gravado é "já perguntei e o
        #: aparelho não respondeu". Sem guardar a falha, cada entrada na aba
        #: mandaria de novo o comando de fábrica para o mesmo controle.
        self._cores: dict[str, Any] = {}
        #: Os cards vivos, por chave, para repintar a borda sem redesenhar tudo
        #: (redesenhar tira o foco de quem está digitando no campo livre).
        self._cards: dict[str, Any] = {}

    # -- montagem ----------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        from gi.repository import Gtk

        self._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa, False, False, 0)
        # O estado vazio vai à tela AGORA, antes de qualquer pergunta: a
        # resposta chega por callback, e uma seção em branco enquanto ela não
        # chega leria como seção quebrada.
        self._desenhar([])
        self.reexaminar()

    # -- leitura -----------------------------------------------------------

    def reexaminar(self) -> None:
        """Relê a mesa e redesenha a grade. Engole a própria exceção.

        É o refresher da aba: `app.py` chama o nome direto, sem embrulhar, e uma
        leitura que falhe não pode derrubar a troca de aba.
        """
        try:
            leitor = getattr(self._host, "_controles_leitor", None)
            if leitor is not None:
                self._aplicar(leitor())
                return
            if self._e_bancada_de_retrato():
                # O retrato NUNCA publica dado vivo (F5). Sem um dublê montado,
                # a seção mostra o estado vazio em vez de fotografar a mesa dela
                # — e, principalmente, em vez de mandar o comando de fábrica que
                # lê a cor para os quatro controles durante uma captura.
                self._desenhar([])
                return
            call_async(
                "daemon.state_full",
                {},
                self._chegou_o_estado,
                self._nao_respondeu,
                timeout_s=1.0,
            )
        except Exception:
            logger.warning("config_controles_reexame_falhou", exc_info=True)

    def _e_bancada_de_retrato(self) -> bool:
        """O hospedeiro é o de `scripts/gui-captura/retratar_abas.py`?

        O sinal é o `_mesa_leitor`, que aquele host monta para a seção da mesa
        (`secao_mesa.py:333`) e que nenhum hospedeiro de produção tem. Usar um
        sinal que já existe é melhor que inventar uma segunda bandeira: uma
        bandeira nova precisaria ser posta em `retratar_abas.py`, que é
        território de outra frente nesta leva, e até lá a captura sairia falando
        com o daemon vivo — falha CALADA, do tipo que só aparece no PNG.
        """
        return getattr(self._host, "_mesa_leitor", None) is not None

    def _chegou_o_estado(self, resultado: Any) -> bool:
        """Guarda os adotados e vai buscar os que o Hefesto só vê.

        Em série e não em paralelo de propósito: o executor da ponte tem UM
        worker (`ipc_bridge._get_executor`), então duas chamadas simultâneas
        seriam duas filas na mesma fila — com a segunda pagando o tempo da
        primeira de qualquer jeito, e o código ficando com dois caminhos de
        chegada para reconciliar.
        """
        self._estado = resultado if isinstance(resultado, dict) else {}
        call_async(
            "controller.list",
            {"external": True},
            self._chegou_o_inventario,
            self._nao_respondeu,
            # O inventário externo enumera TODOS os /dev/input e sonda quem
            # segura cada hidraw: 10-40 ms mais um subprocesso. O default de
            # 0,25 s da ponte estoura.
            timeout_s=3.0,
        )
        return False

    def _chegou_o_inventario(self, resultado: Any) -> bool:
        inventario = resultado if isinstance(resultado, dict) else {}
        self._aplicar(
            {
                "controllers": self._estado.get("controllers")
                or inventario.get("controllers")
                or [],
                "external": inventario.get("external") or [],
            }
        )
        return False

    def _nao_respondeu(self, erro: Exception) -> bool:
        logger.debug("config_controles_sem_resposta", erro=str(erro))
        self._desenhar(None)
        return False

    def _aplicar(self, payload: Any) -> None:
        """Traduz o que chegou em cards e redesenha."""
        bruto = payload if isinstance(payload, dict) else {}
        adotados = [c for c in _lista(bruto.get("controllers")) if c.get("connected")]
        externos = _lista(bruto.get("external"))
        self._desenhar(self._cards_da_mesa(adotados, externos))
        self._perguntar_as_cores(adotados)

    def _cards_da_mesa(
        self, adotados: list[dict[str, Any]], externos: list[dict[str, Any]]
    ) -> list[DadosDoControle]:
        """Os dados de cada card, ordenados pelo número de jogador."""
        declarado = self._declaracoes()
        alvo = getattr(self._host, "_edit_target_uniq", None)
        cards: list[DadosDoControle] = []
        for entrada in adotados:
            cards.append(
                self._card(
                    {**entrada, "bus": str(entrada.get("transport") or "")},
                    adotado=True,
                    # Sem fallback posicional, e a ausência dele é a cura: com
                    # `player_slot` nulo (o registro do daemon ainda sem opinião)
                    # a conta `índice + 1` deu "Jogador 4" a DOIS cards da mesa
                    # de cinco, medido em 22/08/2026 contra
                    # `tests/fixtures/inventario_externos.json`. É o mesmo ponto
                    # cego que a NUMA-05 curou nos externos
                    # (`external_controllers.slot_of`): null honesto vale mais
                    # que número errado, e o card tem título para dizê-lo.
                    slot=_inteiro(entrada.get("player_slot")),
                    declarado=declarado,
                    alvo=alvo,
                )
            )
        for indice, entrada in enumerate(externos):
            cards.append(
                self._card(
                    entrada,
                    adotado=False,
                    slot=slot_of(entrada, len(adotados), indice),
                    declarado=declarado,
                    alvo=alvo,
                )
            )
        return _sem_chave_repetida(_por_numero_de_jogador(cards))

    def _card(
        self,
        entrada: dict[str, Any],
        *,
        adotado: bool,
        slot: int | None,
        declarado: dict[str, Any],
        alvo: Any,
    ) -> DadosDoControle:
        chave = external_key(entrada)
        endereco = chave_de_maquina(entrada)
        meu = declarado.get(endereco or "", {})
        campos = dict(
            (nome, valor)
            for nome, _rotulo, valor in declaracoes_do_aparelho(
                entrada, adotado=adotado, declarado=meu
            )
        )
        uniq = str(entrada.get("uniq") or chave or "")
        lida = self._cores.get(uniq)
        cor_id, cor_livre, nome_da_cor = _cor_na_tela(campos.get("cor"), lida)
        return DadosDoControle(
            chave=chave,
            titulo=f"Jogador {slot}" if slot is not None else TITULO_SEM_NUMERO,
            subtitulo=marca_e_via(entrada, marca="Sony" if adotado else None),
            uniq=uniq,
            slot=slot,
            adotado=adotado,
            modo="" if adotado else modo_deduzido(entrada),
            cor_id=cor_id,
            cor_lida=nome_da_cor if not cor_id else "",
            cor_livre=cor_livre,
            tom=_tom_da_cor(campos.get("cor"), lida),
            botoes=campos.get("botoes"),
            no_cabo=via_do_controle(entrada) == "cabo",
            endereco=endereco or "",
            selecionado=bool(alvo) and alvo == uniq,
        )

    def _declaracoes(self) -> dict[str, Any]:
        """O que está no disco, com a pendência desta sessão por cima.

        Decisão C5 — entrar na aba RELÊ o disco. E a pendência vence porque ela
        é mais nova: o "Aplicar" ainda não rodou, e mostrar o valor antigo faria
        o clique dela parecer perdido.
        """
        gravado: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            gravado = {
                chave: valor.model_dump()
                for chave, valor in carregar_maquina().controles.items()
            }
        pendente = getattr(self._host, "_maquina_pendente", None)
        if isinstance(pendente, dict):
            controles = pendente.get("controles")
            if isinstance(controles, dict):
                gravado = fundir_declaracao(gravado, controles)
        return gravado

    def _perguntar_as_cores(self, adotados: list[dict[str, Any]]) -> None:
        """Pergunta a cor do plástico a cada DualSense NOVO que está no cabo.

        Uma vez por endereço e por sessão, porque a resposta não muda: a cor
        está no serial de fábrica. Sem esse cache, cada entrada na aba mandaria
        de novo um comando da família `0x80` para os quatro controles dela — e
        essa família é a mesma em que um par errado RESETA o aparelho. A trava
        de `integrations/cor_do_plastico` recusa qualquer par que não seja o do
        serial, mas não mandar é melhor que mandar e ser recusado.
        """
        leitor = getattr(self._host, "_cor_do_plastico_leitor", None)
        for entrada in adotados:
            uniq = str(entrada.get("uniq") or "")
            transporte = str(entrada.get("transport") or "").lower()
            if not uniq or uniq in self._cores or transporte != "usb":
                continue
            self._cores[uniq] = None
            alvo = leitor if leitor is not None else ler_pelo_cabo
            run_in_thread(_pergunta_de_cor(uniq, alvo), self._chegou_a_cor)

    def _chegou_a_cor(self, resultado: Any) -> bool:
        """Repinta SÓ a borda do card que ganhou cor.

        Redesenhar a grade inteira tiraria o foco de quem estivesse digitando no
        campo livre de outro card — e a resposta chega segundos depois da
        montagem, que é exatamente quando ela poderia estar digitando.
        """
        try:
            uniq, cor = resultado
        except (TypeError, ValueError):
            return False
        if cor is None:
            return False
        self._cores[uniq] = cor
        for card in self._cards.values():
            if card.dados.uniq != uniq or card.dados.cor_id:
                continue
            with contextlib.suppress(Exception):
                card.repintar_a_borda(tom_para_a_borda(cor.tom))
                card.repintar_o_nome_da_cor(cor.nome)
        return False

    # -- desenho -----------------------------------------------------------

    def _desenhar(self, cards: list[DadosDoControle] | None) -> None:
        """A grade, ou a frase de que não há o que mostrar.

        `None` distingue "o Hefesto não respondeu" de "respondeu e a mesa está
        vazia". As duas frases são diferentes porque a ação dela é diferente:
        uma pede ligar o Hefesto, a outra pede conectar um controle.
        """
        if self._caixa is None:
            return
        from gi.repository import Gtk

        self._esvaziar(self._caixa)
        self._cards = {}
        if not cards:
            self._caixa.pack_start(
                rotulo_de_apoio(
                    FRASE_SEM_RESPOSTA if cards is None else FRASE_SEM_CONTROLE
                ),
                False,
                False,
                0,
            )
            self._caixa.show_all()
            return

        grade = Gtk.Grid()
        grade.set_column_spacing(_ESPACAMENTO)
        grade.set_row_spacing(_ESPACAMENTO)
        grade.set_column_homogeneous(True)
        # `row_homogeneous` iguala LINHAS entre si — é o que faz o card da
        # segunda fileira ter a mesma altura do da primeira. O que iguala dois
        # cards da MESMA fileira é o `valign=FILL` + `vexpand` de cada card
        # (`app/widgets/external_card.py`). Precisa das duas metades.
        grade.set_row_homogeneous(True)
        for indice, dados in enumerate(cards):
            card = ExternalCard(
                dados, ao_declarar=self._ao_declarar, ao_numerar=self._ao_numerar
            )
            self._cards[dados.chave] = card
            grade.attach(card, indice % COLUNAS, indice // COLUNAS, 1, 1)
        self._caixa.pack_start(grade, False, False, 0)
        self._caixa.show_all()

    @staticmethod
    def _esvaziar(caixa: Any) -> None:
        for filho in caixa.get_children():
            caixa.remove(filho)
            filho.destroy()

    # -- gestos ------------------------------------------------------------

    def _ao_declarar(self, chave: str, campo: str, valor: str | None) -> None:
        """Acumula a escolha dela no rascunho. NÃO grava — quem grava é o rodapé.

        `D-A4`, sem exceção: o clique marca o rascunho e o efeito sai no
        "Aplicar". Chamar `machine.declare` daqui criaria um segundo dono do
        gesto de gravar, que é a classe de defeito que a `ABAS-01` curou.
        """
        card = self._cards.get(chave)
        endereco = "" if card is None else card.dados.endereco
        if not endereco:
            # Sem endereço de doze hexa não há chave no `maquina.json`, e o card
            # já mostra a frase que diz isso. A escolha continua valendo na tela
            # — a borda repinta — e morre com a janela.
            self._repintar(chave, campo, valor)
            return
        self._host._maquina_pendente = fundir_declaracao(
            getattr(self._host, "_maquina_pendente", None),
            {"controles": {endereco: {campo: valor}}},
        )
        logger.info("config_controle_declarado", campo=campo, tem_valor=valor is not None)
        self._repintar(chave, campo, valor)

    def _repintar(self, chave: str, campo: str, valor: str | None) -> None:
        """A borda acompanha a escolha na hora — é o que o desenho promete."""
        if campo != "cor":
            return
        card = self._cards.get(chave)
        if card is None:
            return
        lida = self._cores.get(card.dados.uniq)
        with contextlib.suppress(Exception):
            card.repintar_a_borda(_tom_da_cor(valor, lida))

    def _ao_numerar(self, uniq: str, numero: int) -> None:
        """Pede o número ao daemon e RELÊ quando ele confirmar.

        Nada é pintado por conta própria: o número que aparece é o que o daemon
        devolveu no reexame, nunca o que a janela achou que ia acontecer. É a
        mesma disciplina do chip da aba Status (`status_actions.py:1854-1868`),
        e ela existe porque a alternativa cria a terceira verdade — três
        superfícies, dois números, o mesmo controle.
        """

        def _fim(resultado: Any) -> bool:
            ok, motivo = resultado
            if not ok:
                logger.info("config_numero_recusado", motivo=motivo or "sem resposta")
            self.reexaminar()
            return False

        run_in_thread(lambda: identity_number_set(uniq, numero), _fim)


# ---------------------------------------------------------------------------
# Tradução — pura, sem GTK e sem IPC
# ---------------------------------------------------------------------------


def _sem_chave_repetida(cards: list[DadosDoControle]) -> list[DadosDoControle]:
    """Garante que dois cards nunca respondam pela mesma chave.

    A chave sai de `external_key`, que degrada para `evdev_path`, `hidraw`,
    `name` e, no fim da fila, `"?"`. Dois aparelhos que caiam no MESMO degrau de
    degradação teriam a MESMA chave — e então declarar a cor de um repintaria a
    borda do outro, que é o defeito de CLONE-01 voltando pela porta dos fundos
    (dois Nintendo-class no cabo, com o `uniq` sintetizado igual pelo
    `hid-nintendo`, respondendo pelo mesmo botão).

    O sufixo é posicional e vive só na sessão: ele NUNCA chega ao disco, porque
    quem indexa o `maquina.json` é o `endereco`, e um aparelho sem endereço já
    não persiste nada.
    """
    from dataclasses import replace

    vistas: set[str] = set()
    saida: list[DadosDoControle] = []
    for indice, dados in enumerate(cards):
        chave = dados.chave
        if chave in vistas:
            chave = f"{dados.chave}#{indice}"
        vistas.add(chave)
        saida.append(dados if chave == dados.chave else replace(dados, chave=chave))
    return saida



def _por_numero_de_jogador(
    cards: list[DadosDoControle],
) -> list[DadosDoControle]:
    """Ordena os cards por jogador, e põe quem não tem número no fim.

    A mesa entrega os controles na ordem em que os viu — que é a ordem de
    enumeração do kernel, não a de chegada nem a dos jogadores. Numa foto de
    quatro controles isso saiu como "Jogador 4, Jogador 1, Jogador 3, Jogador 2"
    (medido em 22/08/2026 contra o fixture da mesa cheia), e uma fileira assim
    lê como erro de montagem antes de ler como informação.

    Estável: dois cards sem número guardam a ordem em que a mesa os entregou, em
    vez de dançarem entre duas leituras. Quem não tem número vai para o fim
    porque ele ainda não é jogador de ninguém — e o começo da fileira é onde o
    olho procura o Jogador 1.
    """
    return sorted(
        cards,
        key=lambda card: (card.slot is None, card.slot if card.slot else 0),
    )


def _pergunta_de_cor(
    uniq: str, ler: Callable[[str], Any]
) -> Callable[[], tuple[str, Any]]:
    """Fecha o endereço e o leitor numa função de zero argumento.

    Um `lambda` com valor por omissão faria o mesmo e é o que estava aqui — o
    `mypy --strict` recusa inferir o tipo dele, e um `# type: ignore` num
    fechamento sobre variável de laço é onde um dia se esconde o bug clássico
    de todas as threads lerem o ÚLTIMO endereço do laço.
    """

    def _perguntar() -> tuple[str, Any]:
        return uniq, ler(uniq)

    return _perguntar


def _lista(valor: Any) -> list[dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _cor_na_tela(declarada: str | None, lida: Any) -> tuple[str, str, str]:
    """`(id a marcar na lista, texto do campo livre, nome a mostrar)`.

    Três situações, e a ordem é a decisão dela de 21/08/2026 — *"a pessoa pode
    escolher a cor, e a escolha dela vence a tabela"*:

    1. **declarou um nome de fábrica** → a lista marca aquele botão;
    2. **declarou outro nome** → a lista marca "Outra" e o campo livre traz o
       texto dela;
    3. **não declarou** → a lista nasce sem marca e o nome mostrado é o que o
       aparelho respondeu, se respondeu.
    """
    if declarada:
        conhecida = cor_do_nome(declarada)
        if conhecida is not None:
            return conhecida.codigo, "", conhecida.nome
        return ID_DE_OUTRA_COR, declarada, declarada
    return "", "", "" if lida is None else lida.nome


def _tom_da_cor(declarada: str | None, lida: Any) -> str:
    """O hexa da borda, já clareado. "" quando ninguém sabe a cor.

    A escolha dela vence a leitura; um nome que a casa não conhece não tem tom,
    e o card fica com a borda neutra em vez de uma cor inventada.
    """
    if declarada:
        conhecida = cor_do_nome(declarada)
        return "" if conhecida is None else tom_para_a_borda(conhecida.tom)
    if lida is None:
        return ""
    return tom_para_a_borda(lida.tom)
