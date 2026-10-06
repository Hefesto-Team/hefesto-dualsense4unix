#!/usr/bin/env python3
"""A MESA VIVA — do daemon do usuário até o desenho aprovado, sem GTK e sem escrever.

Este módulo é a metade que NÃO tem tela: ele lê o `daemon.state_full`, ordena a
mesa como o produto ordena, junta a cor do plástico e devolve (a) os itens de
mesa que o gerador do mockup sabe desenhar e (b) o pacote de valores que a ponte
escreve na página a cada tique.

TRÊS DISCIPLINAS, e as três nasceram de defeito medido nesta casa:

1. **A ORDEM DA TELA NÃO É A ORDEM DO IPC.** Medido no daemon do usuário em 29/08:
   `controllers[0]` é o primário e é o **jogador 2**; `controllers[1]` é o
   jogador 1. Desenhar por índice inverte os dois controles do usuário na primeira
   execução. Quem ordena é a mesma regra do produto
   (`status_actions._por_numero_de_identidade`: por `player_slot`, sem slot vai
   para o fim), e o número que se escreve é o de `actions/base.numero_do_controle`.

2. **A CHAVE DO CARD É O `uniq`, NÃO A POSIÇÃO.** O `index` muda quando um
   controle cai. Foi casando `keys` ordenadas com `conectados` crus por posição
   que o card do Controle 1 passou a mostrar o registro do Controle 2, em 25/08.

3. **O MAPA DE CANAIS É PORTÃO, E ELE RESPONDE POR TRANSPORTE.**
   `docs/data/mapa-controles.csv` é lido aqui, não decorado: nenhuma linha deste
   arquivo escreve "no rádio não tem cor" — ela é perguntada ao mapa. A tela não
   pode mostrar como ativo o que aquele transporte não entrega.

NADA AQUI ESCREVE. O único método de IPC que este módulo conhece é
`daemon.state_full`, e ele é leitura.
"""
from __future__ import annotations

import csv
import json
import pathlib
import socket
import threading
from typing import Any

from hefesto_dualsense4unix.app.actions.base import numero_do_controle
from hefesto_dualsense4unix.app.mesa import controles_conectados
from hefesto_dualsense4unix.core.speaker_scale import percentual_do_volume
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    MODELO_GENERICO,
    AgendaDaPergunta,
    CorDoPlastico,
    IdentidadeDeFabrica,
    nome_do_aparelho,
)
from hefesto_dualsense4unix.utils import xdg_paths

RAIZ = str(pathlib.Path(__file__).resolve().parents[3])


def socket_do_daemon() -> str:
    """O socket do daemon, perguntado a quem já é dono dele."""
    return str(xdg_paths.ipc_socket_path())


METODO = "daemon.state_full"


class DaemonMudo(Exception):
    """O daemon não respondeu. NÃO é o mesmo que mesa vazia."""

def estado_do_daemon(*, timeout: float = 2.0) -> dict[str, Any]:
    """O `state_full` de agora, ou :class:`DaemonMudo`.

    Os DOIS estados são diferentes e a tela os separa: daemon calado ("não sei
    quem está na mesa") e daemon vivo com mesa vazia ("sei, e não há ninguém").
    Confundi-los é o defeito que o `_render_offline` do produto existe para não
    cometer.
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(socket_do_daemon())
    except OSError as erro:
        raise DaemonMudo(str(erro)) from erro
    try:
        pedido = {"jsonrpc": "2.0", "id": 1, "method": METODO, "params": {}}
        sock.sendall((json.dumps(pedido) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            pedaco = sock.recv(65536)
            if not pedaco:
                break
            buf += pedaco
    except OSError as erro:
        raise DaemonMudo(str(erro)) from erro
    finally:
        sock.close()
    try:
        resposta = json.loads(buf.decode())
    except ValueError as erro:
        raise DaemonMudo(f"resposta ilegível: {erro}") from erro
    if "result" not in resposta:
        raise DaemonMudo(str(resposta.get("error")))
    resultado: dict[str, Any] = resposta["result"]
    return resultado


def _carregar_mapa() -> dict[str, tuple[str, str]]:
    """`{chave: (cabo_aciona, radio_aciona)}` do DualSense."""
    fora: dict[str, tuple[str, str]] = {}
    with open(f"{RAIZ}/docs/data/mapa-controles.csv", encoding="utf-8") as arq:
        for linha in csv.DictReader(arq):
            if (linha.get("controle") or "").strip().lower() != "dualsense":
                continue
            fora[(linha.get("chave") or "").strip()] = (
                (linha.get("cabo_aciona") or "").strip(),
                (linha.get("radio_aciona") or "").strip(),
            )
    return fora


MAPA = _carregar_mapa()


def aciona(chave: str, transporte: str) -> str:
    """"sim" | "parcial" | "não" | "" — o que AQUELE transporte entrega.

    `transporte` é o do `state_full` ("usb"/"bt"). Chave sem linha no mapa
    devolve "" — que é "o mapa não responde por isto", e não "sim".
    """
    par = MAPA.get(chave)
    if par is None:
        return ""
    return par[0] if str(transporte).lower() == "usb" else par[1]


def _via_do_transporte(transporte: object) -> str:
    """A PALAVRA DA TELA para o transporte — da dona da frase, nunca redigitada."""
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    return palavra_do_transporte(transporte)


def _codigo_para_colorway() -> dict[str, tuple[str, str]]:
    """`{código de fábrica: (slug do desenho, nome)}` do mapa das cores."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import TABELA

    return {codigo: (cor.id, cor.nome) for codigo, cor in TABELA.items()}


CORES = _codigo_para_colorway()

#: `mesa_do_estado` escrevia no lugar do nome quando a cor não era legível —
COR_DESCONHECIDA = "Não sei"


class LeitorDeCor:
    """Pergunta a cor do plástico por endereço, nos DOIS transportes.

    Não é um caminho novo: é `integrations/cor_do_plastico.ler_identidade_pelo_cabo`,
    o mesmo leitor que a aba Configurações e o daemon chamam. Fica atrás desta
    classe por três razões medidas:

    * o pedido é um `SET_FEATURE` da família `0x80` — a mesma em que um par
      errado RESETA o aparelho —, então ele NÃO pode entrar num tique de 10 Hz;
      a trava do módulo confere o pedido byte a byte antes do `ioctl`;
    * quem decide a quem perguntar é o MAPA (`identidade.cor_do_aparelho`,
      coluna `aciona` do lado daquele transporte), não um `if` decorado. **A
      célula do rádio virou `sim` em 02/09/2026**: o `EIO` de 15/08 era a
      semente do NOSSO CRC, e com a semente de escrita `0x53` o controle do usuário
      no rádio devolveu o serial em 13,6 ms;
    * QUANDO perguntar de novo é da `AgendaDaPergunta`, o dono que o daemon
      também chama. **SUBSTITUÍDO em 22/09/2026** o *"uma vez por endereço por
      sessão basta"*: a resposta não muda, mas a FALHA não é resposta, e
      guardá-la como `None` apagou modelo e cor dos dois controles do usuário
      (A-FITA-PERDEU-O-MODELO-E-A-COR-01).

    O `leitor` injetado fala o contrato da fonte: `uniq -> IdentidadeDeFabrica`.

    **O MODELO FICA MESMO QUANDO A COR NÃO VEM** — 25/09/2026. A resposta traz
    o nome do modelo pelo PID (`IdentidadeDeFabrica.modelo`), e ele é lido do
    sysfs, sem byte nenhum ao aparelho: por isso chega até numa falha. Ele é
    guardado à parte da cor (`_modelos`) e `conhecidos` o entrega como uma cor
    SEM código, sem tom e sem desenho — só o nome. É o que faz um Edge com
    código fora do mapa, ou com a pergunta falhando, se chamar «DualSense
    Edge» e não «DualSense».
    """

    def __init__(
        self,
        *,
        ligado: bool = True,
        leitor: Any = None,
        agenda: AgendaDaPergunta | None = None,
    ) -> None:
        self.ligado = ligado
        self._leitor = leitor
        self._agenda = agenda if agenda is not None else AgendaDaPergunta()
        self._cache: dict[str, Any] = {}
        self._modelos: dict[str, str] = {}

    def conhecidos(self) -> dict[str, Any]:
        """`{uniq: cor}` do que a tela sabe — a cor lida, ou só o nome do modelo.

        A cor lida vence. Sem ela, quem tem o modelo guardado recebe
        `CorDoPlastico(codigo="", nome=<modelo>)`: sem `id`, o desenho fica no
        neutro, e o nome é o do aparelho. Quem não tem nem uma coisa nem outra
        segue `None` (ou ausente), e `mesa_do_estado` escreve o nome da família.
        """
        fora = dict(self._cache)
        for uniq, modelo in self._modelos.items():
            if fora.get(uniq) is None:
                fora[uniq] = CorDoPlastico(codigo="", nome=modelo)
        return fora

    def pendentes(self, entradas: list[dict[str, Any]]) -> list[str]:
        """Quem perguntar AGORA — e cada um devolvido fica em voo até `perguntar`."""
        fora = []
        for entrada in entradas:
            uniq = str(entrada.get("uniq") or "")
            if not uniq:
                continue
            transporte = str(entrada.get("transport") or "")
            if aciona("identidade.cor_do_aparelho", transporte) != "sim":
                self._cache.setdefault(uniq, None)
                self._agenda.fechar(uniq)
                continue
            if self._agenda.reservar(uniq):
                fora.append(uniq)
        return fora

    def disparar(self, entradas: list[dict[str, Any]]) -> None:
        """`pendentes` + uma thread por pergunta. É o que o tique chama."""
        for uniq in self.pendentes(entradas):
            threading.Thread(
                target=self.perguntar, args=(uniq,), name=f"cor-{uniq[-6:]}", daemon=True
            ).start()

    def perguntar(self, uniq: str) -> Any:
        """Bloqueia. Quem chama põe numa thread — nunca na do GTK."""
        if not self.ligado:
            self._cache[uniq] = None
            self._agenda.registrar(
                uniq, IdentidadeDeFabrica(nao_pode=True, motivo="a leitura está desligada")
            )
            return None
        leitor = self._leitor
        if leitor is None:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                ler_identidade_pelo_cabo,
            )

            leitor = ler_identidade_pelo_cabo
        achado = IdentidadeDeFabrica(motivo="o leitor não devolveu")
        try:
            achado = leitor(uniq)
        except Exception as erro:
            achado = IdentidadeDeFabrica(motivo=f"o leitor levantou {type(erro).__name__}")
        finally:
            if achado.definitiva:
                self._cache[uniq] = achado.cor
            modelo = getattr(achado, "modelo", None)
            if isinstance(modelo, str) and modelo:
                self._modelos[uniq] = modelo
            self._agenda.registrar(uniq, achado)
        return achado.cor

    def esquecer_ausentes(self, vivos: set[str]) -> None:
        for uniq in list(self._cache):
            if uniq not in vivos:
                del self._cache[uniq]
        for uniq in list(self._modelos):
            if uniq not in vivos:
                del self._modelos[uniq]
        self._agenda.esquecer_ausentes(vivos)


#: linhas diziam *"o catálogo do produto tem DUAS máscaras, não três"* e
NOME_DA_MASCARA = {
    "dualsense": "DualSense",
    "xbox": "Xbox 360",
    "nintendo": "Nintendo Pro",
}


#: A FAMÍLIA DOS BOTÕES DE FACE que a tela escreve, e `""` é o desenho do DualSense
#: (✕ ○ □ △). As duas outras trocam só o rótulo dos quatro botões da face, pela
#: POSIÇÃO: sul, leste, oeste, norte.
LETRAS_DA_FACE: dict[str, dict[str, str]] = {
    "xbox": {"cross": "A", "circle": "B", "square": "X", "triangle": "Y"},
    "nintendo": {"cross": "B", "circle": "A", "square": "Y", "triangle": "X"},
}

#: `ControleDeclarado.modo` (a chave física do controle genérico) -> família. O
#: `dinput` fica de fora de propósito: a disposição dos botões nele varia de
#: modelo para modelo, e o produto não sabe qual. Sem resposta, o desenho fica
#: no do DualSense, que é «não sei».
FAMILIA_DO_MODO: dict[str, str] = {"xinput": "xbox", "switch": "nintendo"}

_DECLARACAO_DO_DISCO: tuple[tuple[int, int, int] | None, Any] | None = None


def _declaracao_do_disco() -> Any:
    """O `maquina.json` validado, relido SÓ quando o arquivo muda (inode, mtime, tamanho).

    A mesa é montada a 10 Hz por três pilotos; um `stat` por volta é o que se
    paga, e a leitura inteira só acontece depois de um gesto do usuário.
    """
    global _DECLARACAO_DO_DISCO
    from hefesto_dualsense4unix.utils.maquina import (
        MaquinaConfig,
        caminho_da_maquina,
        carregar_maquina,
    )

    try:
        st = caminho_da_maquina().stat()
        selo: tuple[int, int, int] | None = (st.st_ino, st.st_mtime_ns, st.st_size)
    except OSError:
        selo = None
    if _DECLARACAO_DO_DISCO is None or _DECLARACAO_DO_DISCO[0] != selo:
        _DECLARACAO_DO_DISCO = (selo, carregar_maquina() if selo else MaquinaConfig())
    return _DECLARACAO_DO_DISCO[1]


def _declarado(uniq: str, declaracao: Any = None) -> Any:
    """O `ControleDeclarado` deste controle, ou `None` quando ela não disse nada."""
    from hefesto_dualsense4unix.utils.maquina import chave_do_controle

    chave = chave_do_controle(uniq)
    if chave is None:
        return None
    base = declaracao if declaracao is not None else _declaracao_do_disco()
    return (getattr(base, "controles", None) or {}).get(chave)


def cor_declarada(uniq: str, declaracao: Any = None) -> CorDoPlastico | None:
    """A cor do plástico que ELA declarou para este controle (`controles.cor`).

    É o fio que faltava: o campo existia no `maquina.json` e nenhuma tela o lia.
    Vale onde o aparelho não responde a cor (o rádio, o controle de outra marca),
    e a cor LIDA do aparelho vence sempre: ver :func:`mesa_do_estado`. Nome que o
    mapa não conhece (o campo «Outra») não pinta nada: `None`.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import cor_do_nome

    declarado = _declarado(uniq, declaracao)
    nome = getattr(declarado, "cor", None)
    return cor_do_nome(nome) if isinstance(nome, str) and nome.strip() else None


def familia_dos_botoes(uniq: str, declaracao: Any = None) -> str:
    """`"xbox"`, `"nintendo"` ou `""` (o desenho do DualSense) para este controle.

    O que ela declarou manda: `controles.botoes` (só o desenho da tela) vence o
    `controles.modo` (a chave física do controle). Sem nenhum dos dois, `""`.
    """
    declarado = _declarado(uniq, declaracao)
    botoes = getattr(declarado, "botoes", None)
    if botoes in LETRAS_DA_FACE:
        return str(botoes)
    return FAMILIA_DO_MODO.get(str(getattr(declarado, "modo", None) or ""), "")


def _por_numero_de_identidade(conectados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A MESMA regra do produto (`status_actions._por_numero_de_identidade`)."""

    def chave(entrada: dict[str, Any]) -> tuple[int, int]:
        slot = entrada.get("player_slot")
        if isinstance(slot, int) and not isinstance(slot, bool):
            return (0, slot)
        return (1, 0)

    return sorted(conectados, key=chave)


def _quantos_lugares() -> int:
    """Quantos cartões o desenho tem. O dono é `pacotes.TODOS_OS_LUGARES`."""
    from hefesto_dualsense4unix.interface.pacotes import TODOS_OS_LUGARES

    return len(TODOS_OS_LUGARES)


def _lugares_da_mesa(numeros: list[int]) -> list[str]:
    """O `pref` de cada um — e ele SEGUE O NÚMERO, não a ordem da lista.

    APARELHO-NAO-SE-CONTRADIZ-01, PARTE 2. Decisão, 20/09/2026:
    **«Curar — renomear junto com mover»**.

    **O QUE FOI MEDIDO**, lido pela ponte JS no WebKit vivo, a 400 ms, com o
    daemon e os quatro controles na bancada:

    ======================  =================================  ================
    ..                      ``23:56:17.998``                   ``23:56:19.604``
    ======================  =================================  ================
    cartão ``p3``           **«Player 4»** Galactic Purple     «Player 3» …
    chip da fita            **«P4 • Galactic Purple»**         «P3 • …»
    ======================  =================================  ================

    Por **1,6 segundo** o endereço do cartão e o texto dentro dele se
    contradiziam — medido duas vezes na mesma noite, 1,60 s e 1,61 s. A tela
    REPOSICIONAVA antes de RENOMEAR, e o vão era interno a ela: a mesma
    leitura do daemon dava as duas respostas.

    **A CAUSA, e ela é de forma.** O ``pref`` era a POSIÇÃO na lista — ela
    compacta no instante em que alguém sai — e o ``jogador`` é o
    ``player_slot``, que é do daemon e leva um batimento para se refazer. Dois
    donos para o mesmo fato, em cadências diferentes.

    **A CURA É A POSIÇÃO CEDER, e não o número.** Quem manda no número é o
    daemon (``actions/base.numero_do_controle``, fonte única desde a COR-01):
    deixar a tela compactar o número por conta própria seria duas verdades
    sobre qual é o Player 3 — o defeito que aquela função existe para matar. O
    cartão fica onde está até o daemon renomear, e aí ele move e renomeia no
    mesmo tique. É literalmente a decisão de produto.

    **DOIS CASOS CAEM FORA, e os dois voltam à contagem por posição:** número
    acima do último cartão (um externo na mesa empurra os DualSense para
    cima — ver ``_external_present_ranks_locked``) e número repetido (só
    possível por daemon velho, sem ``player_slot``, em que
    ``numero_do_controle`` cai na posição). Em qualquer dos dois a mesa inteira
    volta a contar 1..N, que é o comportamento anterior a esta sprint.
    """
    teto = _quantos_lugares()
    cabem = all(1 <= n <= teto for n in numeros)
    if cabem and len(set(numeros)) == len(numeros):
        return [f"p{n}" for n in numeros]
    return [f"p{posicao}" for posicao, _ in enumerate(numeros, start=1)]


def mesa_do_estado(
    state: dict[str, Any],
    cores: dict[str, Any],
    *,
    alvo: str | None = None,
    declaracao: Any = None,
) -> list[dict[str, Any]]:
    """Os itens de mesa que `monta`/`aba02` sabem desenhar, na ordem da tela.

    `declaracao` é o `maquina.json` já lido (os testes); sem ela, o disco, relido
    só quando o arquivo muda. A cor e a família dos botões que ELA declarou saem
    daqui para as dez abas de uma vez: é a mesa que todas leem.
    """
    conectados = _por_numero_de_identidade(controles_conectados(state))
    emulacao = state.get("gamepad_emulation") or {}
    sabor = str(emulacao.get("flavor") or "")
    mascara = NOME_DA_MASCARA.get(sabor, sabor or "—")
    por_aparelho = emulacao.get("por_aparelho") or {}

    numeros = [numero_do_controle(entrada) for entrada in conectados]
    prefs = _lugares_da_mesa(numeros)
    fora: list[dict[str, Any]] = []
    for posicao, entrada in enumerate(conectados, start=1):
        uniq = str(entrada.get("uniq") or "")
        transporte = str(entrada.get("transport") or "").lower()
        # guardou do sysfs) ou o da família, e o desenho fica no neutro: um
        cor = cores.get(uniq)
        if cor is None or not getattr(cor, "codigo", ""):  # (noqa-acento): nome de atributo
            # sem cor LIDA do aparelho: a que ela declarou (`controles.cor`).
            cor = cor_declarada(uniq, declaracao) or cor
        slug, nome = "", MODELO_GENERICO
        if cor is not None:
            de_fabrica = str(getattr(cor, "codigo", "") or "")  # (noqa-acento): nome de atributo
            slug, nome = CORES.get(de_fabrica, (str(getattr(cor, "id", "") or ""), ""))
            nome = nome or nome_do_aparelho(cor)
        fora.append(
            {
                "pref": prefs[posicao - 1],
                "uniq": uniq,
                "jogador": numeros[posicao - 1],
                "cor": slug,
                "nome": nome,
                "botoes": familia_dos_botoes(uniq, declaracao),
                # O TRAVESSÃO NÃO É "BT" — corrigido em 05/09/2026. Este
                # `if/else` devolvia "BT" quando o daemon NÃO publicava o
                # transporte, e a aba 01 afirmava rádio sobre um campo que
                # ninguém leu. O dono da palavra curta é
                # `pacotes.VIA_DO_TRANSPORTE`, cujo `.get(..., "")` já
                # respondia certo na aba 02 — e o comentário DELE já afirmava
                # (errado) que as duas traduções eram a mesma. Agora são.
                # A razão está escrita no dono da frase longa
                # (`app/actions/home_actions.py`): *"'?' não é resposta —
                # é a tela encolhendo os ombros"*.
                "via": _via_do_transporte(transporte),
                "transporte": transporte,
                "alvo": (uniq == alvo) if alvo else (posicao == 1),
                # O `mascara` da sessão é o FALLBACK, e não o valor: um daemon
                # velho (sem `por_aparelho`) devolve exatamente o que devolvia
                # antes deste campo existir.
                "mascara": NOME_DA_MASCARA.get(
                    str(por_aparelho.get(uniq) or ""),
                    str(por_aparelho.get(uniq) or "") or mascara),
            }
        )
    return fora


def texto_da_contagem(mesa: list[dict[str, Any]]) -> tuple[str, str]:
    """O cabeçalho: `("● N controles: ", "X USB · Y BT")`.

    Devolve as duas metades porque o desenho as separa (a segunda é `<b>`), e
    porque escrever a frase inteira num `textContent` apagaria o `<b>`.

    A FRASE FICA EM `USB`/`BT` POR GRAMÁTICA — decisão de 06/09/2026. A
    palavra que nomeia UM controle virou `cabo`/`rádio` (D-05), e a contagem
    não acompanha porque *"2 cabo · 0 rádio"* não é português. Ver
    `docs/A-LINGUA-DESTA-CASA-…`, §1: esta é a única exceção declarada.

    **QUEM CONTA LÊ O TRANSPORTE, NUNCA A PALAVRA** — ONDA4-S10, 06/09/2026.
    Esta linha somava `c["via"] == "USB"`, e assim a conta ficava presa à
    palavra: o dia em que a `via` passasse a dizer `cabo`, a tela mostraria
    `● 2 controles: 0 USB · 2 BT` com os dois no cabo — o número errado, sem
    erro, sem log e sem uma linha vermelha. `transporte` é a chave CRUA do
    daemon que `mesa_do_estado` já publica ao lado da palavra; contar por ela
    é o que faz a palavra poder mudar sem que uma única conta se mexa.
    """
    n = len(mesa)
    usb = sum(1 for c in mesa if str(c.get("transporte") or "").strip().lower() == "usb")
    bt = n - usb
    palavra = "controle" if n == 1 else "controles"
    return (f"● {n} {palavra}: ", frase_dos_transportes(usb, bt))


def frase_dos_transportes(usb: int, bt: int) -> str:
    """`1 BT` · `2 USB` · `2 USB · 1 BT` — o transporte VAZIO não aparece."""
    pedacos = []
    if usb:
        pedacos.append(f"{usb} USB")
    if bt:
        pedacos.append(f"{bt} BT")
    return " · ".join(pedacos)


#: (`interface/sensores.ESCALA_GYRO_GRAUS_S`), lida de lá.
from hefesto_dualsense4unix.interface.sensores import (  # noqa: E402
    ESCALA_GYRO_GRAUS_S,
)

PISO_DA_ONDA = 16
QUADROS_DA_ONDA = 14

LIMIAR_L2_R2 = 30

TRADUZ_GLIFO = {"create": "share"}

SEM_LEITOR = "—"


def _barra_bipolar(valor: float | None, escala: float) -> dict[str, str]:
    """O `style` da barrinha de um eixo — a mesma gramática do desenho."""
    if valor is None:
        return {"left": "50%", "width": "0%", "background": "var(--border-forte)"}
    fracao = max(-1.0, min(1.0, float(valor) / escala))
    largura = abs(fracao) * 50.0
    esquerda = 50.0 + (fracao * 50.0 if fracao < 0 else 0.0)
    cor = "var(--border-forte)" if abs(fracao) < 0.01 else (
        "var(--green)" if fracao > 0 else "var(--red)"
    )
    return {
        "left": f"{esquerda:.1f}%",
        "width": f"{max(largura, 0.4):.1f}%",
        "background": cor,
    }


def _texto_do_eixo(valor: float | None) -> str:
    if valor is None:
        return SEM_LEITOR
    return f"{valor:+.2f}"


def _eixo_do_analogico(inputs: dict[str, Any], nome: str) -> int:
    """O valor cru de um eixo de analógico. Repouso é 128; **ausência é `None`**.

    DEFEITO MEDIDO E CURADO EM 29/08/2026. Estas quatro linhas eram
    `int(inputs.get(nome) or 128)`, e `0 or 128` é `128`: o zero — que num
    analógico é o EXTREMO, o talo à esquerda ou para cima — virava o CENTRO.
    Erro de 128 unidades, o máximo possível, e exatamente no fim do curso.

    Medido antes da cura, alimentando esta função pela faixa inteira:
    `0 → 128` (MENTIU), `1 → 1`, `64 → 64`, `128 → 128`, `255 → 255`. Só o zero
    mentia, e mentia sozinho. O zero é alcançável na bancada: o `absinfo` dos
    dois DualSense dá `ABS_X/ABS_Y/ABS_RX/ABS_RY min=0 max=255`, e
    `core/evdev_reader.py` já escreve que "num stick o mínimo é um EXTREMO".

    É REGRESSÃO SÓ DAQUI: o produto que ela usa há meses faz
    `int(inputs.get("lx", 128))` (`interface/cartao_do_controle.py`), a forma com
    default, imune ao falsy. Os outros `or` deste arquivo NÃO têm o defeito —
    `l2_raw`/`r2_raw` caem em `or 0`, e ali o zero É o repouso.
    """
    valor = inputs.get(nome)
    return 128 if valor is None else int(valor)


def selo_do_mic(mudo: bool, sabemos: bool) -> str:
    """O selo do microfone no card: `MUDO`, `ATIVO`, ou `—` quando não se leu.

    UM DONO PARA OS DOIS PINTORES (auditoria de 02/09/2026). O mesmo ternário
    vivia escrito duas vezes — em `pacotes/a02_controles.py` e no
    `Janela._pacote_do_card` de `interface/controles_vivos.py`. O commit da
    MIC-DA-MESA-ELEICAO-01 diz com todas as letras que *"curar só um deixaria
    as duas versões vivas, que é o defeito que a regra da casa existe para
    matar"* — e curou os dois. O que ficou aberto é o outro lado da mesma
    regra: **guardou um só**. A régua do segundo pintor era
    `inspect.getsource` + `assert '<literal>' in fonte`, que mede o TEXTO:
    medido em 02/09, trocar `mic_sabemos` por `True` deixa o controle caído
    voltando a pintar ATIVO com a régua VERDE.

    Com uma função só, a régua passa a ser sobre COMPORTAMENTO, e vale para os
    dois pintores de uma vez.

    O terceiro estado não é enfeite: `mic_sabemos` é falso quando o
    `state_full` não trouxe a chave `audio` — o byte é atributo de INSTÂNCIA do
    handle, e o handle novo do hotplug-out ainda não leu nada. Num contrato em
    que aceso = "estou no ar", pintar ATIVO ali é o controle que acabou de cair
    anunciando que está capturando, na frente de quatro pessoas.
    """
    if not sabemos:
        return SEM_LEITOR
    return DESLIGADO if mudo else ATIVO


#: <!-- noqa-acento: citação literal -->
ATIVO = "ATIVO"
DESLIGADO = "DESLIGADO"


def selo_do_alto_falante(mudo: bool, sabemos: bool) -> str:
    """O selo do alto-falante: `ATIVO`, `DESLIGADO`, ou `—` quando não se leu."""
    if not sabemos:
        return SEM_LEITOR
    return DESLIGADO if mudo else ATIVO


#: pegar o controle de primeira)"*.  <!-- noqa-acento: citação literal -->

BOTAO_MIC_RETORNO = "retorno"

#:      tambem.  <!-- noqa-acento: citação literal, a digitação não se limpa -->
NINGUEM_TE_OUVE = ""

LIMITE_DA_LINHA_DE_QUEM_OUVE = 46


def frase_de_quem_te_ouve(ouvintes: object) -> str:
    """Quem está com o microfone deste controle aberto, em uma linha."""
    if not isinstance(ouvintes, (list, tuple)):
        return ""
    nomes = [t for t in (str(x).strip() for x in ouvintes) if t]
    if not nomes:
        return NINGUEM_TE_OUVE
    if len(nomes) == 1:
        frase = f"{nomes[0]} está te ouvindo."
    else:
        frase = f"{' e '.join((', '.join(nomes[:-1]), nomes[-1]))} estão te ouvindo."
    if len(frase) <= LIMITE_DA_LINHA_DE_QUEM_OUVE:
        return frase
    if len(nomes) == 1:
        return "Um programa está te ouvindo."
    return f"{len(nomes)} programas estão te ouvindo."


def estado_do_card(
    entrada: dict[str, Any],
    *,
    mic: Any = None,
    mic_vol: int | None = None,
    rota_nada: bool | None = None,
    onda_mic: list[int] | None = None,
) -> dict[str, Any]:
    """Os kwargs que `aba02.bloco()` pede, a partir de UM `entry` do IPC."""
    inputs = entrada.get("inputs") or {}
    transporte = str(entrada.get("transport") or "").lower()

    bateria = entrada.get("battery_pct")
    bateria = bateria if isinstance(bateria, int) else None

    apertados = set()
    for nome in inputs.get("buttons") or []:
        apertados.add(TRADUZ_GLIFO.get(str(nome), str(nome)))
    l2 = int(inputs.get("l2_raw") or 0)
    r2 = int(inputs.get("r2_raw") or 0)
    if l2 > LIMIAR_L2_R2:
        apertados.add("l2")
    if r2 > LIMIAR_L2_R2:
        apertados.add("r2")

    toque = inputs.get("touchpad") or {}
    largura = float(toque.get("width") or 1920) or 1920
    altura = float(toque.get("height") or 1080) or 1080
    touch = (
        round(float(toque.get("x") or 0) / largura * 100, 1),
        round(float(toque.get("y") or 0) / altura * 100, 1),
    )
    tocando = bool(toque.get("touching"))

    giro = inputs.get("gyro") or {}
    tem_giro = bool(giro) and aciona("movimento.giroscopio", transporte) != "não"
    giro_linhas = []
    for eixo in ("x", "y", "z"):
        valor = giro.get(eixo) if tem_giro else None
        estilo = _barra_bipolar(valor, ESCALA_GYRO_GRAUS_S)
        giro_linhas.append(
            (eixo.upper(), _texto_do_eixo(valor), ";".join(f"{k}:{v}" for k, v in estilo.items()))
        )

    # aqui porque é ela que impede alguém de o desenhar de novo: o `state_full`

    # do `state_full`.
    audio = entrada.get("audio") or {}
    mic_sabemos = isinstance(audio.get("mic_mudo"), bool)
    mic_mudo = bool(audio.get("mic_mudo"))
    mic_posse = audio.get("mic_mudo_desejado") is not None
    onda = list(onda_mic or [])
    if len(onda) < QUADROS_DA_ONDA:
        onda = [PISO_DA_ONDA] * (QUADROS_DA_ONDA - len(onda)) + onda

    # e pelo rádio o DualSense não publica placa de som nenhuma. Um número de
    alto = entrada.get("speaker") or {}
    volume_cru = alto.get("volume")
    alto_pct = percentual_do_volume(int(volume_cru)) if isinstance(volume_cru, int) else None
    if aciona("audio.alto_falante", transporte) == "não":
        alto_pct = None
    alto_mudo = bool(alto.get("muted"))
    alto_pode = alto_pct is not None

    return {
        "bat": bateria if bateria is not None else 0,
        "glifos_on": apertados,
        "l2": l2,
        "r2": r2,
        "touch": touch,
        "tocando": tocando,
        "sticks": (
            _eixo_do_analogico(inputs, "lx"),
            _eixo_do_analogico(inputs, "ly"),
            _eixo_do_analogico(inputs, "rx"),
            _eixo_do_analogico(inputs, "ry"),
        ),
        "giro": giro_linhas,
        "mic_v": onda[-QUADROS_DA_ONDA:],
        "mic_mudo": mic_mudo,
        "mic_sabemos": mic_sabemos,
        "mic_posse": mic_posse,
        "alto_mudo": alto_mudo,
        "alto_pode": alto_pode,
        "mic_vol": mic_vol if mic_vol is not None else 0,
        "alto_v": [alto_pct if alto_pct is not None else 0] + [PISO_DA_ONDA] * (QUADROS_DA_ONDA - 1),
        "rota_nada": bool(rota_nada),
        # `None` = NÃO SEI, e é diferente de zero. O DualSense não devolve o
        "alto_pct": alto_pct,
    }
