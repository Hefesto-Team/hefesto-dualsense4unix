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
#: resposta válida: o `ler_pelo_cabo` do produto devolve `None` sem levantar, e
#: pelo rádio o mapa de canais diz `identidade.cor_do_aparelho = não`.
COR_DESCONHECIDA = "Não sei"


class LeitorDeCor:
    """Pergunta a cor do plástico UMA VEZ por endereço, e só no cabo.

    Não é um caminho novo: é `integrations/cor_do_plastico.ler_pelo_cabo`, o
    mesmo que a aba Configurações já chama ao entrar. Fica atrás desta classe
    por três razões medidas:

    * o pedido é um `SET_FEATURE` da família `0x80` — a mesma em que um par
      errado RESETA o aparelho —, então ele NÃO pode entrar num tique de 10 Hz;
      a trava do módulo confere o pedido byte a byte antes do `ioctl`;
    * pelo rádio a resposta não vem, e quem diz isso é o mapa
      (`identidade.cor_do_aparelho`, `radio_aciona = não`), não um `if` decorado;
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
#: O catálogo do produto tem DUAS máscaras, não três
#: (`integrations/uinput_gamepad.FLAVORS`). "Nintendo Pro" não existe.
NOME_DA_MASCARA = {"dualsense": "DualSense", "xbox": "Xbox 360"}


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


def mesa_do_estado(
    state: dict[str, Any],
    cores: dict[str, Any],
    *,
    alvo: str | None = None,
) -> list[dict[str, Any]]:
    """Os itens de mesa que `monta`/`aba02` sabem desenhar, na ordem da tela.

    O item ganha DOIS campos que a `monta.MESA` fixa não tem: `uniq` (a chave
    estável do card, que vira `data-controle`) e `transporte` (o cru do IPC, que
    o mapa de canais consome). O `pref` continua sendo a POSIÇÃO — é ele que
    nomeia o rádio do acordeão —, e `jogador` continua sendo a IDENTIDADE.
    """
    conectados = _por_numero_de_identidade(controles_conectados(state))
    emulacao = state.get("gamepad_emulation") or {}
    sabor = str(emulacao.get("flavor") or "")
    mascara = NOME_DA_MASCARA.get(sabor, sabor or "—")

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
                "pref": f"p{posicao}",
                "uniq": uniq,
                "jogador": numero_do_controle(entrada),
                "cor": slug,
                "nome": nome,
                "via": "USB" if transporte == "usb" else "BT",
                "transporte": transporte,
                "alvo": (uniq == alvo) if alvo else (posicao == 1),
                "mascara": mascara,
            }
        )
    return fora


def texto_da_contagem(mesa: list[dict[str, Any]]) -> tuple[str, str]:
    """O cabeçalho: `("● N controles: ", "X USB · Y BT")`.

    Devolve as duas metades porque o desenho as separa (a segunda é `<b>`), e
    porque escrever a frase inteira num `textContent` apagaria o `<b>`.
    """
    n = len(mesa)
    # `.get` E NÃO `[...]`: uma mesa pode chegar sem a chave — a de uma régua,
    # ou a de um controle que o daemon publicou antes de resolver o transporte.
    # Derrubar a contagem por isso derruba a aba INTEIRA, e o que se perde é uma
    # palavra. Medido em 01/09/2026: `KeyError: 'via'` na suíte completa, vindo
    # do pacote da Vibração, que passou a chamar esta função.
    usb = sum(1 for c in mesa if c.get("via") == "USB")
    bt = n - usb
    palavra = "controle" if n == 1 else "controles"
    return (f"● {n} {palavra}: ", f"{usb} USB · {bt} BT")


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

    audio = entrada.get("audio") or {}
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
