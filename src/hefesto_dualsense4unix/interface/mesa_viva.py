#!/usr/bin/env python3
"""A MESA VIVA — do daemon dela até o desenho aprovado, sem GTK e sem escrever.

Este módulo é a metade que NÃO tem tela: ele lê o `daemon.state_full`, ordena a
mesa como o produto ordena, junta a cor do plástico e devolve (a) os itens de
mesa que o gerador do mockup sabe desenhar e (b) o pacote de valores que a ponte
escreve na página a cada tique.

TRÊS DISCIPLINAS, e as três nasceram de defeito medido nesta casa:

1. **A ORDEM DA TELA NÃO É A ORDEM DO IPC.** Medido no daemon dela em 29/08:
   `controllers[0]` é o primário e é o **jogador 2**; `controllers[1]` é o
   jogador 1. Desenhar por índice inverte os dois controles dela na primeira
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
from typing import Any

from hefesto_dualsense4unix.app.actions.base import numero_do_controle
from hefesto_dualsense4unix.app.mesa import controles_conectados
from hefesto_dualsense4unix.core.speaker_scale import percentual_do_volume
from hefesto_dualsense4unix.utils import xdg_paths

#: A raiz do repositório é a DESTE arquivo — nunca um caminho escrito à mão.
#:
#: FATO ERRADO, SUBSTITUÍDO (30/08/2026): era o literal
#: ``"/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix"``, a árvore DELA. Quem
#: rodasse uma aba viva de uma árvore de agente lia o
#: ``docs/data/mapa-controles.csv`` **dela**, e o mapa de canais é portão — uma
#: linha corrigida na árvore do agente não valia nada, sem erro nenhum.
RAIZ = str(pathlib.Path(__file__).resolve().parents[3])

# ---------------------------------------------------------------------------
# O IPC, por leitura e só por leitura
# ---------------------------------------------------------------------------


def socket_do_daemon() -> str:
    """O socket do daemon, perguntado a quem já é dono dele.

    É FUNÇÃO e não constante DE PROPÓSITO: uma constante calculada no import
    congela o nome de quem importou primeiro, e cega qualquer régua que queira
    medir o caminho num processo que já importou o módulo.

    FATO ERRADO, SUBSTITUÍDO (30/08/2026). Aqui havia um caminho montado à mão::

        SOCKET = os.path.join(XDG_RUNTIME_DIR, "hefesto-dualsense4unix",
                              "hefesto-dualsense4unix.sock")

    com o nome do app ESCRITO COMO LITERAL. Era o mesmo valor com dois donos, e
    o segundo dono estava errado em dois pontos de uma vez:

    1. **O nome.** ``xdg_paths`` deriva o diretório de
       ``identidade.atual().slug``; o literal ignorava isso e passava a apontar
       para o lugar errado assim que o nome mudasse. MEDIDO em 30/08 às 00:26,
       com o daemon no ar e vendo um controle: as cinco abas vivas diziam
       ``[Errno 111] Conexão recusada`` e pintavam **5 valores** — a tela de
       "Hefesto desligado" — enquanto o daemon respondia normalmente no
       diretório ao lado.
    2. **O modo fake.** ``ipc_socket_name()`` isola o socket quando
       ``HEFESTO_DUALSENSE4UNIX_FAKE=1`` e respeita o override explícito de
       nome. O literal atravessava os dois e falava com o socket de produção —
       que é o footgun que o ``BUG-FAKE-SOCKET-SYNC-01`` já tinha pago no
       produto e que esta cópia reintroduziu.

    Este é o ÚNICO ponto de resolução de socket das abas vivas: as cinco
    (Controles, Jogar, Perfis, Conexões, Sistema) chegam ao daemon por
    :func:`estado_do_daemon`, logo por aqui.
    """
    return str(xdg_paths.ipc_socket_path())


#: O ÚNICO método que este módulo sabe pronunciar. Escrito como constante para
#: que uma leitura de `grep` responda a pergunta "esta leva escreve?" com um
#: nome só — e para que acrescentar um segundo seja uma mudança visível.
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


# ---------------------------------------------------------------------------
# O MAPA DE CANAIS — portão, lido, nunca decorado
# ---------------------------------------------------------------------------
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
    """A PALAVRA DA TELA para o transporte — da dona da frase, nunca redigitada.

    **ELA PASSOU A SER A PALAVRA — costura da ONDA B, 06/09/2026, e é o degrau
    que a ONDA4-S10 desenhou e não pôde executar.** A decisão dela (D-05) é
    *"cabo / rádio, pela função que já existe"*, e a dona da frase mora em
    `app/actions/home_actions.py:1483`.

    **FATO SUBSTITUÍDO.** Aqui estava escrito que esta função devolvia a SIGLA
    DE MÁQUINA, porque a chave `via` que ela alimenta era COMPARADA em cinco
    pontos — `interface/monta.py`, quatro linhas de
    `interface/pacotes/a08_conexoes.py`. Os cinco passaram a ler o `transporte`
    cru (`_e_radio` na 08, a contagem do topo em `monta`), e a chave ficou livre
    para dizer o que a tela lê. Nenhum ponto compara `via` hoje; quem comparar
    de novo quebra a decisão dela, e o `_e_radio` é o caminho.

    O NOME DA DONA NÃO SE SOLETRA NESTE ARQUIVO, e não é preciosismo: o portão
    da paridade (`docs/data/paridade-gtk-html.csv:18`) vigia a AUSÊNCIA desse
    símbolo aqui, e em 05/09/2026 um comentário que o soletrou já foi lido como
    uso. A forma desta casa é citar o ENDEREÇO.

    A AUSÊNCIA CONTINUA DEVOLVENDO "" — a tela mostra travessão —, e um
    transporte desconhecido volta **cru**, com a razão da dona: *"um transporte
    novo tem de aparecer na tela para alguém o ver, em vez de ser escondido
    atrás de uma frase genérica"*.
    """
    # IMPORT TARDIO de propósito: `home_actions` puxa o motor inteiro, e
    # `mesa_viva` é importado pelo piloto no arranque da janela.
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    return palavra_do_transporte(transporte)


# ---------------------------------------------------------------------------
# A COR DO PLÁSTICO — o código de fábrica vira o `colorway` do desenho
# ---------------------------------------------------------------------------
def _codigo_para_colorway() -> dict[str, tuple[str, str]]:
    """`{código de fábrica: (slug do desenho, nome)}` do CSV das cores.

    A JUNTA EXISTIA COMO DADO E NÃO EXISTIA COMO CÓDIGO: a primeira coluna do
    `docs/data/cores-do-dualsense.csv` é o MESMO código que
    `integrations/cor_do_plastico.NOMES_DE_FABRICA` indexa, e nenhuma linha de
    `src/` lê esse CSV. Esta função é a costura, e ela mora aqui porque é a
    tela que precisa do slug — o produto entrega `CorDoPlastico(codigo, nome,  (noqa-acento: assinatura citada, não prosa)
    tom)`, e o desenho pinta por `data-colorway`.
    """
    fora: dict[str, tuple[str, str]] = {}
    with open(f"{RAIZ}/docs/data/cores-do-dualsense.csv", encoding="utf-8") as arq:
        for bruta in arq:
            if bruta.startswith("#") or not bruta.strip():
                continue
            campos = bruta.split(",")
            if len(campos) < 3 or campos[0] == "codigo_da_cor":
                continue
            codigo = campos[0].strip()
            if codigo:
                fora.setdefault(codigo, (campos[1].strip(), campos[2].strip()))
    return fora


CORES = _codigo_para_colorway()

#: O que a linha do rótulo diz quando a cor não é legível. É "não sei", e é
#: resposta válida: o `ler_pelo_cabo` do produto devolve `None` sem levantar
#: quando o aparelho não responde, quando o broker fecha a porta ou quando o
#: código de fábrica está fora da tabela de vinte e uma entradas.
COR_DESCONHECIDA = "Não sei"


class LeitorDeCor:
    """Pergunta a cor do plástico UMA VEZ por endereço, nos DOIS transportes.

    Não é um caminho novo: é `integrations/cor_do_plastico.ler_pelo_cabo`, o
    mesmo que a aba Configurações já chama ao entrar. Fica atrás desta classe
    por três razões medidas:

    * o pedido é um `SET_FEATURE` da família `0x80` — a mesma em que um par
      errado RESETA o aparelho —, então ele NÃO pode entrar num tique de 10 Hz;
      a trava do módulo confere o pedido byte a byte antes do `ioctl`;
    * quem decide a quem perguntar é o MAPA (`identidade.cor_do_aparelho`,
      coluna `aciona` do lado daquele transporte), não um `if` decorado. **A
      célula do rádio virou `sim` em 02/09/2026** — SUBSTITUÍDO o que esta
      docstring dizia até então (*"pelo rádio a resposta não vem"*, com
      `radio_aciona = não`): o `EIO` de 15/08 era a semente do NOSSO CRC, e com
      a semente de escrita `0x53` o controle dela no rádio devolveu o serial em
      13,6 ms. O mecanismo aqui não mudou uma linha — mudou a célula, e o
      produto seguiu;
    * a resposta não muda — está no serial de fábrica —, então uma vez por
      endereço por sessão basta.
    """

    def __init__(self, *, ligado: bool = True, leitor: Any = None) -> None:
        self.ligado = ligado
        self._leitor = leitor
        self._cache: dict[str, Any] = {}

    def conhecidos(self) -> dict[str, Any]:
        return dict(self._cache)

    def pendentes(self, entradas: list[dict[str, Any]]) -> list[str]:
        """Quem ainda não foi perguntado E pode responder neste transporte."""
        fora = []
        for entrada in entradas:
            uniq = str(entrada.get("uniq") or "")
            transporte = str(entrada.get("transport") or "")
            if not uniq or uniq in self._cache:
                continue
            if aciona("identidade.cor_do_aparelho", transporte) != "sim":
                # O mapa respondeu que aquele transporte não entrega. Marca como
                # perguntado para não voltar aqui a cada tique.
                self._cache[uniq] = None
                continue
            fora.append(uniq)
        return fora

    def perguntar(self, uniq: str) -> Any:
        """Bloqueia. Quem chama põe numa thread — nunca na do GTK."""
        if not self.ligado:
            self._cache[uniq] = None
            return None
        leitor = self._leitor
        if leitor is None:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import ler_pelo_cabo

            leitor = ler_pelo_cabo
        try:
            cor = leitor(uniq)
        except Exception:
            cor = None
        self._cache[uniq] = cor
        return cor

    def esquecer_ausentes(self, vivos: set[str]) -> None:
        for uniq in list(self._cache):
            if uniq not in vivos:
                del self._cache[uniq]


# ---------------------------------------------------------------------------
# A MESA
# ---------------------------------------------------------------------------
#: flavor -> o rótulo que a tela mostra. NOTA DATADA — 07/09/2026: estas duas
#: linhas diziam *"o catálogo do produto tem DUAS máscaras, não três"* e
#: *"'Nintendo Pro' não existe"*. **Existe desde 07/09/2026**, por ordem dela, e
#: as duas frases mediam o mundo de ontem. O `uinput_gamepad.FLAVORS` tem TRÊS,
#: e a `gui/aba_conexoes.NOME_DA_MASCARA` já nomeava as três antes de haver a
#: terceira — era esta tabela que estava atrás, não aquela.
NOME_DA_MASCARA = {
    "dualsense": "DualSense",
    "xbox": "Xbox 360",
    "nintendo": "Nintendo Pro",
}


def _por_numero_de_identidade(conectados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A MESMA regra do produto (`status_actions._por_numero_de_identidade`).

    Copiada de propósito em vez de importada: `status_actions` é um mixin que
    puxa GTK e a janela inteira no import. A regra é três linhas e o teste
    abaixo a confere contra a do produto.
    """

    def chave(entrada: dict[str, Any]) -> tuple[int, int]:
        slot = entrada.get("player_slot")
        if isinstance(slot, int) and not isinstance(slot, bool):
            return (0, slot)
        return (1, 0)

    return sorted(conectados, key=chave)


def _quantos_lugares() -> int:
    """Quantos cartões o desenho tem. O dono é `pacotes.TODOS_OS_LUGARES`.

    Import LAZY, e não por preguiça: `pacotes/__init__` importa as dez abas no
    fim do arquivo, e várias delas leem ESTE módulo. Ao nível de módulo o
    import fecharia um ciclo; aqui ele roda quando a mesa já existe.

    Digitar `4` seria a segunda verdade sobre quantos lugares a tela tem — e o
    dia em que ela pedir um quinto cartão, a régua daqui mentiria calada.
    """
    from hefesto_dualsense4unix.interface.pacotes import TODOS_OS_LUGARES

    return len(TODOS_OS_LUGARES)


def _lugares_da_mesa(numeros: list[int]) -> list[str]:
    """O `pref` de cada um — e ele SEGUE O NÚMERO, não a ordem da lista.

    APARELHO-NAO-SE-CONTRADIZ-01, PARTE 2. Decisão dela, 20/09/2026:
    **«Curar — renomear junto com mover»**.

    **O QUE FOI MEDIDO**, lido pela ponte JS no WebKit vivo, a 400 ms, com o
    daemon e os quatro controles na mesa dela:

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
    mesmo tique. É literalmente a decisão dela.

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
) -> list[dict[str, Any]]:
    """Os itens de mesa que `monta`/`aba02` sabem desenhar, na ordem da tela.

    O item ganha DOIS campos que a `monta.MESA` fixa não tem: `uniq` (a chave
    estável do card, que vira `data-controle`) e `transporte` (o cru do IPC, que
    o mapa de canais consome).

    **O `pref` SEGUE O NÚMERO desde 20/09/2026** — APARELHO-NAO-SE-CONTRADIZ-01,
    PARTE 2, decisão dela: *«Curar — renomear junto com mover»*. Ele era a
    POSIÇÃO na lista, e era essa a contradição: a posição compactava na hora e o
    número esperava o daemon, então o cartão `p3` dizia «Player 4» por 1,6 s. A
    regra e os dois casos em que ela cede estão em :func:`_lugares_da_mesa`.

    `jogador` continua sendo a IDENTIDADE, e continua vindo do daemon — é a
    fonte única (`actions/base.numero_do_controle`), e nada aqui a substitui.
    """
    conectados = _por_numero_de_identidade(controles_conectados(state))
    emulacao = state.get("gamepad_emulation") or {}
    sabor = str(emulacao.get("flavor") or "")
    mascara = NOME_DA_MASCARA.get(sabor, sabor or "—")
    # A MÁSCARA É DE CADA APARELHO — MASCARA-NA-TELA-01, 03/09/2026, e o pedido
    # é dela: *"é uma máscara por controle. Mesmo caso do anterior."*
    #
    # Esta linha escrevia a máscara da SESSÃO nos quatro cartões. O registro por
    # aparelho existe desde 15/08 (`external_mask`, decisão dela) e o daemon já
    # o consulta ao criar cada vpad — a tela era o único lugar que não sabia.
    # `por_aparelho` traz `{uniq: máscara efetiva}`, e o `sabor` da sessão fica
    # como o que vale para quem não escolheu, que é a herança do registro.
    por_aparelho = emulacao.get("por_aparelho") or {}

    numeros = [numero_do_controle(entrada) for entrada in conectados]
    prefs = _lugares_da_mesa(numeros)
    fora: list[dict[str, Any]] = []
    for posicao, entrada in enumerate(conectados, start=1):
        uniq = str(entrada.get("uniq") or "")
        transporte = str(entrada.get("transport") or "").lower()
        cor = cores.get(uniq)
        slug, nome = ("", COR_DESCONHECIDA)
        if cor is not None:
            slug, nome = CORES.get(getattr(cor, "codigo", ""), ("", getattr(cor, "nome", "")))  # (noqa-acento): nome de atributo
            nome = nome or getattr(cor, "nome", COR_DESCONHECIDA)
        fora.append(
            {
                "pref": prefs[posicao - 1],
                "uniq": uniq,
                "jogador": numeros[posicao - 1],
                "cor": slug,
                "nome": nome,
                # O TRAVESSÃO NÃO É "BT" — corrigido em 05/09/2026. Este
                # `if/else` devolvia "BT" quando o daemon NÃO publicava o
                # transporte, e a aba 01 afirmava rádio sobre um campo que
                # ninguém leu. O dono da palavra curta é
                # `pacotes.VIA_DO_TRANSPORTE`, cujo `.get(..., "")` já
                # respondia certo na aba 02 — e o comentário DELE já afirmava
                # (errado) que as duas traduções eram a mesma. Agora são.
                # A razão está escrita no dono da frase longa
                # (`app/actions/home_actions.py:1548`): *"'?' não é resposta —
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

    A FRASE FICA EM `USB`/`BT` POR GRAMÁTICA — decisão dela de 06/09/2026. A
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
    # `.get` E NÃO `[...]`: uma mesa pode chegar sem a chave — a de uma régua,
    # ou a de um controle que o daemon publicou antes de resolver o transporte.
    # Derrubar a contagem por isso derruba a aba INTEIRA, e o que se perde é uma
    # palavra. Medido em 01/09/2026: `KeyError: 'via'` na suíte completa, vindo
    # do pacote da Vibração, que passou a chamar esta função.
    usb = sum(1 for c in mesa if str(c.get("transporte") or "").strip().lower() == "usb")
    bt = n - usb
    palavra = "controle" if n == 1 else "controles"
    return (f"● {n} {palavra}: ", frase_dos_transportes(usb, bt))


def frase_dos_transportes(usb: int, bt: int) -> str:
    """`1 BT` · `2 USB` · `2 USB · 1 BT` — o transporte VAZIO não aparece.

    DECISÃO DELA, 17/09/2026, com um controle só no rádio na mesa: *"só tem 1
    controle conectado ainda assim aparece no canto superior direito 0 usb 1 bt
    deveria mostrar só o que tá conectado que é 1 bt nesse caso"*.

    Ela REFINA a decisão de 06/09 e não a contradiz: aquela escolheu a PALAVRA
    (`USB`/`BT` em vez de `cabo`/`rádio`, porque *"2 cabo · 0 rádio"* não é
    português, e é a única exceção declarada da língua desta casa). Esta
    escolhe o que se OMITE. A palavra continua a mesma.

    O `0 USB ·` custava uma leitura a cada olhada — a pessoa tinha de somar
    para descobrir que o zero não queria dizer nada. O produto é de
    acessibilidade: o que não está lá não se escreve.

    A FUNÇÃO É PÚBLICA porque a frase tem DOIS escritores — esta, viva, e o
    `interface/monta.py`, que a grava no esqueleto das dez páginas. Enquanto
    cada um formatava por conta própria, uma mudança aqui deixava o esqueleto
    dizendo outra coisa até o piloto repintar.

    Com os dois zerados devolve string vazia: o `● 0 controles:` ao lado já diz
    tudo, e `0 USB · 0 BT` era a frase que a tela mostrava quando o daemon nem
    tinha respondido.
    """
    pedacos = []
    if usb:
        pedacos.append(f"{usb} USB")
    if bt:
        pedacos.append(f"{bt} BT")
    return " · ".join(pedacos)


# ---------------------------------------------------------------------------
# O ESTADO DE CADA CARD — o que muda de segundo a segundo
# ---------------------------------------------------------------------------
#: A escala do desenho para a barra bipolar do giroscópio. É a mesma do produto
#: (`app/widgets/sensor_widgets.ESCALA_GYRO_GRAUS_S`), lida de lá.
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (  # noqa: E402
    ESCALA_GYRO_GRAUS_S,
)

#: O piso da onda, que é o do desenho (`aba02.onda`): com o microfone mudo os
#: valores caem a 4-6 % e as barras somem — silêncio é uma linha baixa e
#: visível, não a ausência do desenho.
PISO_DA_ONDA = 16
QUADROS_DA_ONDA = 14

#: O limiar em que L2/R2 acendem o glifo. É o do produto
#: (`controller_card.L2_R2_THRESHOLD`), não `> 0`.
LIMIAR_L2_R2 = 30

#: O daemon emite `create` (BTN_SELECT); o glifo e o arquivo chamam-se `share`.
#: A tradução carrega número de defeito no produto
#: (BUG-GLYPH-SHARE-NAME-MISMATCH-01); sem ela o glifo fica morto e ninguém vê.
TRADUZ_GLIFO = {"create": "share"}

#: O texto do eixo sem leitor. É o "—" do produto (`controller_card.reset_inputs`):
#: nunca o último valor como se fosse vivo, nunca zero fingindo repouso.
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
    mentia, e mentia sozinho. O zero é alcançável na mesa dela: o `absinfo` dos
    dois DualSense dá `ABS_X/ABS_Y/ABS_RX/ABS_RY min=0 max=255`, e
    `core/evdev_reader.py` já escreve que "num stick o mínimo é um EXTREMO".

    É REGRESSÃO SÓ DAQUI: o produto que ela usa há meses faz
    `int(inputs.get("lx", 128))` (`app/widgets/controller_card.py`), a forma com
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


#: A LÍNGUA DOS DOIS SELOS DO SOM, e ela é uma só por ordem dela — 19/09/2026.
#: A pergunta dela, sobre o par que o alto-falante usava (`acordado`/`dormindo`):
#: *"Ativo e Desligado pros dois não seria melhor que dormindo?"*
#: <!-- noqa-acento: citação literal dela -->
#:
#: O QUE ISSO SUBSTITUIU, e por que é melhor: o microfone dizia `MUDO` e o
#: alto-falante dizia `dormindo` — duas palavras, duas grafias e dois conceitos
#: para a mesma pergunta de quem olha (*"sai som por aqui agora?"*). `dormindo`
#: ainda era pior: descreve o SERVIDOR DE SOM suspender um nó, que é vocabulário
#: de dentro, e ela já baniu esse tipo de palavra da tela.
#:
#: A RAZÃO NÃO SE PERDE, MUDA DE LUGAR: ela sai da palavra e vai para a dica
#: (`dica_do_canal`), que é onde esta casa põe o porquê desde 13/09.
ATIVO = "ATIVO"
DESLIGADO = "DESLIGADO"


def selo_do_alto_falante(mudo: bool, dormindo: bool, sabemos: bool) -> str:
    """O selo do alto-falante: `ATIVO`, `DESLIGADO`, ou `—` quando não se leu.

    **É A MESMA PERGUNTA QUE O SELO DO MICROFONE RESPONDE**, e por isso fala a
    mesma língua: *sai som por aqui agora?* Ele nasceu em 19/09/2026 da ordem
    dela — *"esse auto falante que tá com o acordado ali (…) consegue colocar o
    mesmo ativado lá de cima? vai ter o mesmo efeito"*
    <!-- noqa-acento: citação literal dela --> — e substituiu o chip cinza que
    dizia `acordado`.

    DOIS FATOS, UMA PALAVRA, e é isso que o chip velho não fazia: o som não sai
    quando ela CALOU o alto-falante **ou** quando o canal está dormindo no
    servidor de som. O chip velho só contava o segundo, ao lado de um botão `♪`
    que só contava o primeiro — duas leituras parciais, no mesmo bloco, que
    podiam se contradizer na cara dela.

    `sabemos` É O TERCEIRO ESTADO, pela mesma razão do microfone: sem leitura do
    bloco de áudio, pintar `ATIVO` é o controle que acabou de cair anunciando
    que está tocando.
    """
    if not sabemos:
        return SEM_LEITOR
    return DESLIGADO if (mudo or dormindo) else ATIVO


#: As palavras dos TRÊS estados do botão 🎙 — MIC-NA-TELA-01, 10/09/2026.
#: Pedido dela: *"ele aceso (vai indicar que agora tá gravando audio), ele
#: captando audio vai ficar no estado de piscando (guia visual pro leigo que
#: pegar o controle de primeira)"*.  <!-- noqa-acento: citação literal dela -->
#:
#: São palavras e não números porque quem as lê é um SELETOR DE CSS, e um
#: seletor com o número do protocolo dentro (`[data-mic-luz="2"]`) não diz nada
#: a quem abre a folha. O número fica do lado de quem fala com o aparelho.
BOTAO_MIC_GRAVANDO = "gravando"
BOTAO_MIC_CAPTANDO = "captando"

#: **O RETORNO LIGADO** — 21/09/2026, ordem dela sobre o 🎙:
#:
#:     "SE EU ATIVAR COM UM CLICK E ELE FICAR VERDE ELE TÁ ATIVADO E SEGUE
#:      ASSIM ATÉ EU DESATIVAR CLICANDO NOVAMENTE E ELE FICANDO CINZA. POR
#:      DEFAULT SEGUE DESLIGADO"
#:
#: **ELE NÃO É A LUZ DO PLÁSTICO, e essa distinção é o desenho inteiro.** A
#: luz (`BOTAO_MIC_GRAVANDO`/`BOTAO_MIC_CAPTANDO`) tem dono no daemon —
#: `luz_do_mic.decidir`, o mesmo byte que acende o LED vermelho do controle —,
#: e o que a mostra é o SELO ao lado, mais a frase de quem está gravando.
#: Fazer o botão publicar aquele estado poria a tela e o controle na mão dela
#: discordando no primeiro dia em que um dos dois fosse corrigido.
#:
#: **O BOTÃO MOSTRA O QUE O BOTÃO CAUSA**, que é a regra desta casa e a mesma
#: do ♪: ele liga o retorno, e acende enquanto o retorno está de pé.
BOTAO_MIC_RETORNO = "retorno"

#: O que o daemon publica em `audio.luz_do_mic`, e é o MESMO byte que acende a
#: luz do plástico (`daemon/subsystems/luz_do_mic`: 0 apagada · 1 acesa ·
#: 2 piscando · 3 piscando devagar, que é piscando com bateria baixa).
_LUZ_ACESA, _LUZ_PISCA, _LUZ_PISCA_LENTO = 1, 2, 3


def estado_do_botao_do_mic(luz: object) -> str:
    """A palavra do botão 🎙 para o estado da luz — `""` quando não se sabe.

    **UM DONO, E ELE NÃO DECIDE NADA** — traduz. Quem decide os três estados é
    `luz_do_mic.decidir`, no daemon, e é o mesmo byte que acende a luz no
    plástico; escrever um segundo ternário aqui (mudo? canal? nível?) poria a
    tela e o controle na mão dela discordando no primeiro dia em que um dos
    dois fosse corrigido.

    `""` é resposta de primeira classe: nenhuma classe acende, e o botão fica
    com o cinza de base — *"ninguém leu o microfone deste controle"*. É a mesma
    disciplina do terceiro estado do ♪.

    O `3` (piscando devagar, bateria baixa) devolve a mesma palavra do `2`: a
    diferença entre eles é um aviso de CARGA, e a carga já tem lugar próprio no
    cartão. Duas piscadas diferentes no mesmo botão seriam duas gramáticas para
    quem só quer saber se está sendo ouvido.
    """
    if isinstance(luz, bool) or not isinstance(luz, int):
        return ""
    if luz in (_LUZ_PISCA, _LUZ_PISCA_LENTO):
        return BOTAO_MIC_CAPTANDO
    return BOTAO_MIC_GRAVANDO if luz == _LUZ_ACESA else ""


#: A FRASE DE QUEM TE OUVE — 19/09/2026, a outra metade da decisão dela na
#: `A-LUZ-DO-MIC-ESPELHA-O-BOTAO-01`. A luz do plástico passou a espelhar o
#: BOTÃO (mudo apaga, ligado acende), e com isso ela deixou de distinguir
#: sozinha *"ligado"* de *"ligado e alguém te ouvindo"*. A aba Controle é quem
#: passa a dizer QUEM, por escrito, e esta é a única cópia dessas palavras.
#: **A FRASE SAIU DA TELA EM 21/09/2026, POR ORDEM DELA**, e a constante fica
#: vazia em vez de sumir: quem a lia é a régua, e apagar o nome deixaria a
#: decisão sem sujeito.
#:
#:     "Ninguém está te ouvindo ainda. na real essa frase não faz sentido
#:      tambem.  <!-- noqa-acento: a digitação dela não se limpa -->
#:      pq sinceramente se o mic tá ativo tá subentendido que ele tá
#:      funcionando sempre. pode remover ela."
#:
#: **A DECISÃO DE 19/09 NÃO SE APAGA — ela CADUCOU, e a razão é medida.** A
#: frase nasceu porque o microfone LIGADO com nenhum app gravando apagava a luz
#: do controle, e ela desligou o próprio microfone achando que o ligava; a
#: linha existia para explicar que *acesa* não quer dizer *alguém te escuta*.
#: **A luz passou a acender em 19/09**, e com ela a premissa da frase caiu: o
#: selo «ATIVO» do cartão já diz o que ela precisa saber.
#:
#: E AS OUTRAS FRASES FICAM. *"Discord está te ouvindo."* é informação que
#: nada mais na tela dá, e ela não pediu para tirar — o que saiu é o estado
#: VAZIO, que é o normal e não merece uma linha.
NINGUEM_TE_OUVE = ""

#: Quantos caracteres cabem em UMA linha da `.ressalva` do bloco do microfone,
#: e o número é MEDIDO — Chrome headless sobre `mockup/02-controles.html` na
#: janela do produto (1180px), 19/09/2026:
#:
#:     coluna do som            281,0 px de largura
#:     uma linha da .ressalva    17,3 px (11,5px x 1,5 + 5 de margem)
#:     card aberto              329,6 -> 351,9 px com a linha escrita
#:     .quadro-corpo            sem rolagem (scrollHeight == clientHeight)
#:
#: **A SEGUNDA LINHA É QUE NÃO CABE.** A coluna do som é uma das duas que
#: MANDAM na altura do card, e um bloco que dobra de linha já tirou o P4 da
#: tela dela em 30/08. Acima deste limite a frase troca os NOMES pela
#: CONTAGEM, que cabe sempre — e a contagem continua verdadeira.
LIMITE_DA_LINHA_DE_QUEM_OUVE = 46


def frase_de_quem_te_ouve(ouvintes: object) -> str:
    """Quem está com o microfone deste controle aberto, em uma linha.

    `""` quando não se sabe (ninguém perguntou, ou o daemon é velho e não
    publica a chave) — e `""` faz a `.ressalva` sumir sem cobrar um pixel, que
    é o contrato da D-02 dela: *"linha fixa só quando HÁ ressalva"*.

    **A LISTA VAZIA NÃO É AUSÊNCIA**, e é justamente ela que vira a frase mais
    importante: *"medi, e ninguém te ouve"*. Foi esse estado — o microfone
    LIGADO com nenhum app gravando — que apagava a luz do controle até 19/09 e
    fez ela desligar o próprio microfone achando que o ligava. A luz agora
    acende; esta linha é quem explica que acesa não quer dizer *"alguém te
    escuta"*.

    **QUEM CONTA SÃO OS APPS DE FORA.** O daemon já entrega a lista sem os
    gravadores do próprio Hefesto (`integrations.quem_ouve_o_microfone.
    e_stream_do_hefesto`, regra 3) — o medidor de nível desta mesma aba grava
    o canal o tempo todo, e contá-lo faria a tela dizer que alguém te ouve
    porque a tela está aberta.

    **ACIMA DE `LIMITE_DA_LINHA_DE_QUEM_OUVE` A FRASE CONTA em vez de nomear.**
    Um nome de app longo (ou três nomes) quebraria a `.ressalva` em duas
    linhas, e a segunda linha não cabe no card — ver a constante.
    """
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
    canal: str = "",
    rota_pc: bool | None = None,
    onda_mic: list[int] | None = None,
) -> dict[str, Any]:
    """Os kwargs que `aba02.bloco()` pede, a partir de UM `entry` do IPC.

    É a mesma função que alimenta a primeira montagem e o tique: o desenho e a
    repintura leem a MESMA conta, e por isso não há como o card nascer diferente
    do que ele vira meio segundo depois.
    """
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
    # O DEDO ESTÁ LÁ OU NÃO — e sem isto a superfície do touchpad nunca dizia
    # nada. Medido em 29/08: 238 leituras dos dois controles dela com
    # `touching` FALSO em todas as 238; o ponto ficava invisível e o retângulo
    # de 148x83 não mostrava coisa alguma, o tempo inteiro.
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

    # O ACELERÔMETRO NÃO TEM MAIS LINHA NA TELA, e a medição que o tirou fica
    # aqui porque é ela que impede alguém de o desenhar de novo: o `state_full`
    # não publica chave nenhuma de acelerômetro (medido nos dois controles da
    # mesa dela em 29/08 — `inputs` traz buttons, gyro, l2_raw, lx, ly, r2_raw,
    # rx, ry, speaker, touchpad), e `docs/data/mapa-controles.csv` dá
    # `movimento.acelerometro` como não/não nos DOIS transportes, os dois
    # medidos. Estas três linhas escreviam "—" três vezes: honesto, e ainda
    # assim 81px de tela para dizer "não sei". O registro completo da mudança de
    # especificação está no cabeçalho de `aba02.py`
    # (D-A-LEITURA-DO-ACELERÔMETRO-SAI-DA-TELA).

    # A AUSÊNCIA DE LEITURA DEIXOU DE VIRAR MENTIRA (MIC-DA-MESA-ELEICAO-01).
    #
    # Aqui se lia `bool(audio.get("mic_mudo"))`, e `bool(None)` é `False`, que a
    # tela pinta como **ATIVO**. Só que `None` ali não quer dizer "não está
    # mudo": quer dizer que NINGUÉM LEU. O byte de estado de áudio é atributo
    # de INSTÂNCIA do handle; o handle morre no hotplug-out, o novo nasce sem
    # leitura, `audio_status_for` devolve `None` e a chave `audio` some inteira
    # do `state_full`.
    #
    # Num contrato em que ACESO = "este microfone está no ar", isso faz o
    # controle que acabou de cair anunciar que está no ar — o pior default
    # possível numa mesa de quatro. `mic_sabemos=False` é o terceiro estado, e
    # a tela pinta DESCONHECIDO em vez de escolher um dos dois.
    audio = entrada.get("audio") or {}
    mic_sabemos = isinstance(audio.get("mic_mudo"), bool)
    mic_mudo = bool(audio.get("mic_mudo"))
    # QUEM MANDA NO MUDO DO MICROFONE — e é o que diz se há o que "Liberar".
    # `mic_mudo_desejado` é `None` enquanto a posse for do kernel
    # (`hid_playstation`), e booleano depois que o Hefesto assumiu o registrador.
    # Medido na mesa dela em 29/08: `null` nos DOIS controles — logo o "Liberar"
    # nasce apagado, que é a resposta honesta: não há o que devolver.
    mic_posse = audio.get("mic_mudo_desejado") is not None
    onda = list(onda_mic or [])
    if len(onda) < QUADROS_DA_ONDA:
        onda = [PISO_DA_ONDA] * (QUADROS_DA_ONDA - len(onda)) + onda

    # O ALTO-FALANTE PASSA PELO PORTÃO DO MAPA. `audio.alto_falante` tem
    # `radio_aciona = não` (medido), e a ressalva do CSV diz por quê: o Hefesto
    # NÃO envia PCM, ele mexe no volume e na rota de algo que outra pessoa toca,
    # e pelo rádio o DualSense não publica placa de som nenhuma. Um número de
    # volume desenhado ali seria a tela afirmando o que aquele transporte não
    # entrega — e é exatamente o que o mapa existe para impedir.
    alto = entrada.get("speaker") or {}
    volume_cru = alto.get("volume")
    alto_pct = percentual_do_volume(int(volume_cru)) if isinstance(volume_cru, int) else None
    if aciona("audio.alto_falante", transporte) == "não":
        alto_pct = None
    # O MUDO DO ALTO-FALANTE, QUE O DAEMON PUBLICA E ESTA TELA IGNORAVA. Medido
    # na mesa dela: `speaker = {"volume": 101, "muted": false, …}` — a chave
    # sempre esteve lá, e o ♪ não tinha como acender nem com o alto-falante mudo.
    alto_mudo = bool(alto.get("muted"))
    # E `speaker.set {muted}` é RECUSADO sem volume conhecido (`ipc_handlers.py`):
    # sem posse o par mudo/desmudo trancaria o alto-falante em zero. Então o ♪
    # só é clicável quando há volume — a mesma pré-condição que o botão do
    # produto já respeita nascendo insensível.
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
        "rota_pc": bool(rota_pc),
        "estado_alto": canal or "",
        # `None` = NÃO SEI, e é diferente de zero. O DualSense não devolve o
        # volume que tem — a chave `speaker` só aparece depois de um
        # `speaker.set` NOSSO —, então antes disso o produto escreve
        # "Não ajustado" (controller_card.py:631) em vez de inventar um número.
        "alto_pct": alto_pct,
    }
