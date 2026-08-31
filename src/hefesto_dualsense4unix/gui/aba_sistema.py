"""aba_sistema — a aba 09 no motor novo: do que o produto LÊ ao que a tela DIZ.

A janela, as duas pontes e a guarda de carga são de todas as abas e moram em
:mod:`hefesto_dualsense4unix.gui.ponte_da_tela`. **Este módulo é o que sobra
quando aquilo sai: a aba Sistema.** Ele traduz uma leitura da máquina no pacote
que a página recebe numa chamada só, e não sabe o que é um ``WebView``.

    from hefesto_dualsense4unix.gui import aba_sistema

    leitura = aba_sistema.Leitura(status="offline", state=None, ...)
    janela.ponte.dizer("HEF.pinta", aba_sistema.pacote(leitura))

POR QUE ELE É PURO, E ISSO NÃO É PREFERÊNCIA
--------------------------------------------
Nada aqui roda ``systemctl``, abre soquete ou lê disco: quem faz isso é o
chamador, e entrega o resultado no :class:`Leitura`. É o que deixa a régua medir
**este** código — o mesmo que a interface roda — sem daemon, sem rede e sem
tocar a mesa dela. O piloto ``novo-layout/_ferramentas/sistema_viva.py`` é quem
faz as chamadas de verdade.

A REGRA QUE MAIS PESA AQUI: A AUSÊNCIA DE DADO É UM VALOR
---------------------------------------------------------
Com o Hefesto desligado, o mockup diz *"O Hefesto está **Ligado**"*, *"Pausado:
**Sim, e volta pausado**"*, *"**Os 4** controles"* — são literais do desenho
(``novo-layout/_ferramentas/aba09.py``), e a tela nova que os deixasse à mostra
estaria **afirmando o estado do desenho**. É o defeito mais caro possível nesta
aba. Toda função deste módulo devolve, no lugar do branco, **o que faltou**:
:data:`NAO_DEU`, com o motivo, no lugar do valor.

E o que não tem fonte de dado nenhuma no produto de hoje está em
:data:`SEM_FONTE`, com o endereço e o porquê — **um número plausível e falso é
pior que um traço honesto**, porque ela confia nele.
"""
from __future__ import annotations

import html
import re
from typing import Any, NamedTuple

# ---------------------------------------------------------------------------
# O CONTRATO: os endereços e os gestos, num lugar só
# ---------------------------------------------------------------------------
#: O ENDEREÇO DE CADA VALOR DA TELA, e quem é a fonte dele no produto.
#:
#: Esta tabela é a fonte única: o gerador do desenho
#: (``novo-layout/_ferramentas/aba09.py``) a lê por AST para emitir os
#: ``data-id``, a pintura a lê para saber o que escrever, e a régua a lê para
#: exigir que a página tenha exatamente estes endereços. **Nenhum dos três a
#: digita** — foi assim que onze réguas desta casa reprovaram a melhora em vez
#: do defeito, em 26/08: digitavam o que deviam LER.
#:
#: São DOZE endereços para DEZENOVE valores, e a diferença é de propósito: a
#: lista de achados do exame é **um** endereço, não oito. O exame varia de 6 a 8
#: linhas hoje (``storm_report`` devolve seis, e as duas condicionais devolvem
#: ``None`` quando não há o que dizer); ``achado-1``..``8`` congelaria em oito o
#: que o produto não congela.
ENDERECOS: dict[str, str] = {
    "hefesto-estado": "a matriz de três fontes de `daemon_actions._daemon_status`",
    "hefesto-pausa": '`state_full["paused"]` (daemon/ipc_handlers.py:2081)',
    "hefesto-troca-de-perfil": "`daemon_actions.descrever_deteccao_de_janela:123`",
    "hefesto-ambiente": "`app/actions/ambiente_na_tela.descrever_display_grafico:76`",
    "hefesto-autostart": "`systemctl --user is-enabled` da unidade normal",
    "bateria-perfil": "`app/actions/config/secao_orcamento.ROTULOS_DOS_PERFIS:125`",
    "bateria-impoe": "`core.rumble.teto_do_orcamento` + `TETO_POR_PERFIL:137`",
    "bateria-vale-para": '`state_full["controllers"]`',
    "bateria-frase": "`secao_orcamento.LINHAS_DO_TETO:206`",
    "exame-contagem": "DERIVADA da lista — nunca digitada",
    "exame-lista": "`integrations/storm_doctor.storm_report:755`",
    "registro-texto": "NÃO TEM FONTE — ver SEM_FONTE",
}

#: O DONO REAL DE CADA GESTO, DECLARADO NUM LUGAR SÓ. É a mesma disciplina do
#: ``DONOS_DOS_GESTOS`` do piloto da aba Controles: o gesto chega ao Python, e
#: quem o aplica está escrito aqui — inclusive quando a resposta é "ninguém".
GESTOS: dict[str, str] = {
    "retomar": "IPC `daemon.resume` (daemon/ipc_server.py:121 → ipc_handlers.py:2374). "
    "O ÚNICO chamador em src/ é `cli/app.py:421` — o terminal. A pausa fica "
    "gravada em disco e sobrevive a desligar o computador; até hoje só o "
    "terminal saía dela.",
    "reiniciar": "`daemon_actions.on_daemon_service_restart:2277`",
    "atualizar": "`daemon_actions.on_daemon_refresh:2267`",
    "desligar": "`daemon_actions.on_daemon_stop:2234` — e ele arma "
    "`_user_stopped_daemon` para o `ensure_daemon_running` não o ressuscitar "
    "na próxima abertura.",
    "autostart": "`daemon_actions.on_daemon_autostart_toggled:2398`",
    "perfil-da-mesa": "`app/actions/config/secao_orcamento._ao_escolher`",
    "refazer-consertos": "`daemon_actions.on_storm_fix_safe:1218`",
    "refazer-proton": "`daemon_actions.on_proton_lock:1793`",
    "procurar-camadas": "`emulation_actions.on_camadas_engasgo` — MORA NA ABA QUE "
    "MORRE. Quem desmontar a Emulação leva o handler junto sem perceber, e o "
    "achado `Nenhuma sobreposição` perde o motor no mesmo commit.",
    "restaurar-de-fabrica": "`app/actions/footer_actions.on_restore_default:1477`, "
    "hoje no RODAPÉ (`main.glade:4272`, botão `btn_footer_restore_default`), "
    "com confirmação em `app/gui_dialogs.confirm_restore_default:696`.",
    "ver-plugins": "IPC `plugin.list`/`plugin.reload` (daemon/ipc_server.py:184-185). "
    "Só a CLI chama (`cli/cmd_plugin.py`). Não há botão no produto de hoje.",
    "ver-detalhes": "`daemon_actions.on_daemon_view_logs:2387` — e ele mostra "
    "OUTRA coisa: o `systemctl status`, não as últimas linhas de registro que "
    "o desenho pediu.",
}

#: O QUE A TELA DESENHOU E O PRODUTO NÃO TEM COMO PREENCHER. Fica declarado, com
#: o endereço e o porquê, e a pintura escreve :data:`NAO_DEU` no lugar — nunca o
#: literal bonito do mockup.
SEM_FONTE: dict[str, str] = {
    "registro-texto": "O desenho pediu as últimas linhas do registro técnico "
    "('Joga as últimas 80 linhas do registro técnico no painel ao lado'). NÃO "
    "HÁ MÉTODO DE IPC que as devolva: o que existe é `on_daemon_view_logs`, "
    "que mostra `systemctl status` da unidade. Ou o painel passa a dizer que é "
    "o `systemctl status`, ou nasce um método de log — é decisão dela "
    "(MIGRA-SISTEMA-10).",
}

#: O que se diz de um gesto SEM linha em :data:`GESTOS`. Era um ``KeyError`` cru
#: no piloto da aba Controles, e derrubar a tela dela para relatar um dono
#: desconhecido é o pior dos dois males. O gerador só emite chaves conhecidas —
#: mas quem lê não é só o gerador: é qualquer DOM, inclusive um adulterado por
#: régua.
SEM_DONO = (
    "SEM LINHA na tabela de donos — este gesto chegou de um endereço que o "
    "gerador não escreve. Nada foi aplicado."
)

#: A resposta honesta no lugar do valor. Um traço, e o motivo na dica.
NAO_DEU = "—"

#: Os três selos que o desenho tem para uma linha de estado, e mais nada:
#: ``.est.ok`` (verde), ``.est.warn`` (laranja) e ``.est.info`` (ciano)
#: (``aba09.py:247-249``). **NÃO HÁ classe vermelha para linha de estado** — o
#: desenho não a tem, e inventá-la mudaria o que ela aprovou. Por isso o
#: "Desligado" sai em ``warn``, e isso está declarado em vez de escondido.
OK, AVISO, INFO, NEUTRO = "ok", "warn", "info", ""
GLIFO_OK, GLIFO_AVISO, GLIFO_INFO, GLIFO_NENHUM = "✓", "!", "◆", ""


class Linha(NamedTuple):
    """Uma linha de estado pronta para a tela: o valor, o selo e a dica.

    ``cls`` e ``g`` andam JUNTOS de propósito — o selo carrega símbolo e cor ao
    mesmo tempo, para quem não distingue verde de laranja ler o estado pelo
    desenho (é a regra que a própria aba explica no "?" do exame).
    """

    txt: str
    cls: str = NEUTRO
    g: str = GLIFO_NENHUM
    dica: str = ""


class Leitura(NamedTuple):
    """O que o produto conseguiu ler AGORA. ``None`` é sempre "não deu para ler".

    Cada campo nomeia quem o produz, e nenhum deles é produzido aqui:

    :param status: ``daemon_actions._daemon_status()`` — um de
        ``online_systemd``, ``online_avulso``, ``iniciando``, ``offline``.
    :param autostart: a saída crua de ``systemctl --user is-enabled``.
    :param state: o ``daemon.state_full``, ou ``None`` com o daemon calado.
    :param achados: o retorno de ``storm_doctor.storm_report()`` — pares
        ``(veredito, frase)``.
    :param deteccao: ``daemon_actions.descrever_deteccao_de_janela(state)``, em
        markup do Pango.
    :param ambiente: ``ambiente_na_tela.descrever_display_grafico(state)``.
    :param perfil: a chave do perfil da mesa (``secao_orcamento.PERFIS``), ou
        ``None`` quando ninguém escolheu.
    """

    status: str | None = None
    autostart: str | None = None
    state: dict[str, Any] | None = None
    achados: list[tuple[str, str]] | None = None
    deteccao: str | None = None
    ambiente: str | None = None
    perfil: str | None = None


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
_MARCACAO = re.compile(r"<[^>]+>")


def sem_markup(frase: str) -> str:
    """O texto de uma frase do produto, sem o markup do Pango.

    As frases de ``descrever_deteccao_de_janela`` e companhia nascem para um
    ``Gtk.Label``: elas trazem ``<b>`` e ``<span foreground="#ffb86c">``. Numa
    página isso ou apareceria cru ou injetaria marcação de outro dono no HTML
    dela. **Nós tiramos a marcação e ficamos com o texto** — a frase continua
    tendo UM dono, que é a função do produto.
    """
    return html.unescape(_MARCACAO.sub("", frase)).strip()


def _campos_de_janela(state: object) -> dict[str, Any] | None:
    """Os três campos que decidem a linha da troca de perfil, ou ``None``.

    São os mesmos que ``descrever_deteccao_de_janela`` lê
    (``window_detect_backend``/``_seeing``/``_reason``), e ler os mesmos campos
    é de propósito: a frase LONGA continua sendo daquela função, que vai para a
    dica; o que sai daqui é só o valor CURTO da coluna, que aquela função não
    tem como dar (ela devolve uma sentença inteira, com prefixo).
    """
    if not isinstance(state, dict) or "window_detect_backend" not in state:
        return None
    return {
        "backend": state.get("window_detect_backend"),
        "vendo": bool(state.get("window_detect_seeing")),
        "motivo": state.get("window_detect_reason"),
    }


# ---------------------------------------------------------------------------
# As linhas, uma função por linha
# ---------------------------------------------------------------------------
#: O que cada estado da matriz de três fontes diz NESTA tela. O produto de hoje
#: tem as suas próprias palavras em ``_set_daemon_status_markup`` (" Funcionando
#: (liga sozinho com o computador)"), e elas são de OUTRA tela — a do Glade. O
#: desenho que ela aprovou diz "Ligado", numa coluna de respostas curtas. As
#: duas viram uma no dia em que a aba velha morrer.
_ESTADO_DO_HEFESTO: dict[str, Linha] = {
    "online_systemd": Linha(
        "Ligado", OK, GLIFO_OK,
        "O Hefesto está rodando. Se travar, ele volta sozinho.",
    ),
    "online_avulso": Linha(
        "Ligado, em modo improvisado",
        AVISO,
        GLIFO_AVISO,
        "Está rodando, mas de um jeito improvisado: não liga sozinho com o "
        "computador nem volta sozinho se travar.",
    ),
    "iniciando": Linha(
        "Ligando…",
        AVISO,
        GLIFO_AVISO,
        "Está terminando de ligar. Aguarde alguns segundos e clique em Atualizar.",
    ),
    "offline": Linha(
        "Desligado",
        AVISO,
        GLIFO_AVISO,
        "O Hefesto não está rodando — o controle funciona, mas sem luzes, "
        "gatilhos nem os seus ajustes.",
    ),
}


def linha_do_hefesto(status: str | None) -> Linha:
    """"Ligado" / "Desligado" / "Ligando…" — e o traço quando não deu para ler."""
    if status is None:
        return Linha(
            NAO_DEU, INFO, GLIFO_INFO,
            "Não consegui perguntar ao systemd em que estado o Hefesto está.",
        )
    linha = _ESTADO_DO_HEFESTO.get(status)
    if linha is None:
        # Estado novo, vindo de um produto mais novo que esta tela: dizer o
        # código cru é feio e honesto; inventar leitura é o defeito antigo.
        return Linha(status, INFO, GLIFO_INFO, "Estado que esta tela ainda não sabe nomear.")
    return linha


def linha_da_pausa(state: object) -> Linha:
    """A pausa, que CHEGA À TELA PELA PRIMEIRA VEZ.

    ``state_full["paused"]`` é publicado desde sempre
    (``daemon/ipc_handlers.py:2081``) e os dois únicos leitores em ``app/`` são
    a aba inicial e a Emulação — **esta aba nunca o leu**.

    E o texto diz **o que a pausa é**: ela fica gravada em disco e sobrevive a
    desligar o computador. Sem essa frase, "Pausado: Sim" lê como estado do
    momento, e a pessoa desliga o computador esperando que passe.
    """
    if not isinstance(state, dict) or "paused" not in state:
        return Linha(
            NAO_DEU, INFO, GLIFO_INFO,
            "O Hefesto não respondeu — não dá para saber se está pausado.",
        )
    if state.get("paused"):
        return Linha(
            "Sim, e volta pausado",
            AVISO,
            GLIFO_AVISO,
            "A pausa fica gravada em disco e sobrevive a desligar o "
            "computador. O botão Retomar, ao lado, é a saída.",
        )
    return Linha("Não", OK, GLIFO_OK, "O Hefesto está despachando as entradas normalmente.")


def linha_da_troca_de_perfil(state: object, frase: str | None) -> Linha:
    """O valor CURTO da troca de perfil; a frase longa do produto vai na dica."""
    dica = sem_markup(frase) if frase else ""
    campos = _campos_de_janela(state)
    if campos is None:
        return Linha(NAO_DEU, INFO, GLIFO_INFO, dica or "O Hefesto pode estar desligado.")
    backend = campos["backend"]
    if not isinstance(backend, str) or backend in ("", "null"):
        return Linha("Não funciona neste sistema", AVISO, GLIFO_AVISO, dica)
    if campos["vendo"]:
        return Linha("Ligado", OK, GLIFO_OK, dica)
    return Linha("Sem ver a janela agora", AVISO, GLIFO_AVISO, dica)


def linha_do_ambiente(frase: str | None) -> Linha:
    """Como o Hefesto enxerga a janela — o MECANISMO, não a promessa.

    A frase inteira é de ``ambiente_na_tela.descrever_display_grafico``, que até
    hoje tem **zero chamadores** no produto: é a cura escrita e nunca ligada que
    esta casa nomeou de ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ``. O que sai aqui é o
    predicado dela, depois dos dois-pontos — o rótulo da linha já diz o sujeito.
    """
    if not frase:
        return Linha(
            NAO_DEU, INFO, GLIFO_INFO,
            "Ninguém respondeu por qual caminho o Hefesto enxerga a janela.",
        )
    limpa = sem_markup(frase)
    valor = limpa.split(":", 1)[1].strip() if ":" in limpa else limpa
    valor = valor.rstrip(".")
    return Linha(valor[:1].upper() + valor[1:], INFO, GLIFO_INFO, limpa)


def autostart_ligado(autostart: str | None) -> bool | None:
    """A chave "Ligar junto com o computador". ``None`` = não deu para ler.

    ``None`` **não é** ``False``: a chave desenhada tem dois estados e nenhum
    deles quer dizer "não sei". Quem pinta trata os três.
    """
    if autostart is None:
        return None
    return autostart.strip() == "enabled"


def quantos_controles(state: object) -> int | None:
    """Quantos controles conectados o ``state_full`` traz. ``None`` = não deu."""
    if not isinstance(state, dict):
        return None
    controles = state.get("controllers")
    if not isinstance(controles, list):
        return None
    return sum(1 for c in controles if isinstance(c, dict) and c.get("connected") is not False)


def linha_do_vale_para(state: object) -> Linha:
    """"Os N controles" — e ZERO é estado legítimo, não erro.

    A página nasce da mesa REAL. O desenho tem quatro; a mesa dela tem dois; e
    uma mesa vazia tem de dizer que está vazia, em vez de mostrar o número do
    desenho.
    """
    quantos = quantos_controles(state)
    if quantos is None:
        return Linha(
            NAO_DEU, INFO, GLIFO_INFO,
            "O Hefesto não respondeu quantos controles estão na mesa.",
        )
    if quantos == 0:
        return Linha(
            "Nenhum controle na mesa", INFO, GLIFO_INFO,
            "O teto continua valendo para quem chegar.",
        )
    if quantos == 1:
        return Linha(
            "O controle da mesa", INFO, GLIFO_INFO,
            "É o teto da MESA; o controle pode sobrepô-lo na linha dele.",
        )
    return Linha(
        f"Os {quantos} controles",
        INFO,
        GLIFO_INFO,
        "É o teto da MESA. Cada controle pode sobrepô-lo na linha dele.",
    )


def forca_do_perfil(perfil: str | None) -> str | None:
    """"30% da força", ou ``None`` quando o perfil não põe teto nenhum.

    **O 0,3 não se escreve aqui**, nem a tradução perfil→disco: as duas pontas
    vêm do produto (``secao_orcamento.TETO_POR_PERFIL`` e
    ``core.rumble.teto_do_orcamento``, que por sua vez lê o
    ``RUMBLE_POLICY_MULT`` do daemon). Um número digitado nesta tela divergiria
    do que o daemon entrega no primeiro degrau que mudasse.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import TETO_POR_PERFIL
    from hefesto_dualsense4unix.core.rumble import teto_do_orcamento

    if perfil is None:
        return None
    teto = teto_do_orcamento(TETO_POR_PERFIL.get(perfil))
    return None if teto is None else f"{round(teto * 100)}% da força"


def linha_do_impoe(perfil: str | None) -> Linha:
    """O que o perfil escolhido impõe, hoje, na mesa inteira."""
    if perfil is None:
        return Linha(
            NAO_DEU, INFO, GLIFO_INFO,
            "Ninguém escolheu um perfil de bateria para a mesa.",
        )
    forca = forca_do_perfil(perfil)
    valor = f"Vibração em {forca}" if forca else "Nada é limitado"
    return Linha(
        valor,
        INFO,
        GLIFO_INFO,
        "O que este perfil limita hoje, na mesa inteira. O degrau vem de "
        "RUMBLE_POLICY_MULT, no daemon — nenhum número escrito nesta tela.",
    )


def rotulo_do_perfil(perfil: str | None) -> str | None:
    """O nome que a pessoa vê para uma chave de perfil, lido do produto."""
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import ROTULOS_DOS_PERFIS

    return None if perfil is None else ROTULOS_DOS_PERFIS.get(perfil)


def perfil_do_rotulo(rotulo: str) -> str | None:
    """O caminho de volta: o que a página mandou vira a chave do produto.

    É o que fecha o gesto ``perfil-da-mesa``. Sem ele, o Python receberia
    "Bateria longa" e teria de adivinhar a chave — e adivinhar é o que faz uma
    escolha dela cair no perfil errado.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import ROTULOS_DOS_PERFIS

    for chave, nome in ROTULOS_DOS_PERFIS.items():
        if nome == rotulo:
            return chave
    return None


def frase_do_teto() -> str:
    """A frase de duas linhas do Perfil de Bateria, derivada de ``LINHAS_DO_TETO``.

    No dia em que a barra de luz ganhar ponto de aplicação, ela sai da frase
    sozinha — porque a lista tem um dono só, no produto.

    **A frase tem duas linhas de orçamento, e o número é medido**
    (``aba09.py``): com TRÊS linhas o bloco vai a 159,4 px, o irmão estica junto
    e o miolo passa a rolar 3 px por dentro. Encurtar o texto é a cura; esconder
    o que sobra não.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        LINHAS_DO_TETO,
        PERFIS,
        ROTULOS_DOS_PERFIS,
    )

    com_teto = [p for p in PERFIS if forca_do_perfil(p) is not None]
    alcanca = [linha.nome for linha in LINHAS_DO_TETO if linha.ponto_de_aplicacao]
    pendentes = [linha.nome for linha in LINHAS_DO_TETO if not linha.ponto_de_aplicacao]
    if len(com_teto) != 1:
        # A frase está escrita no singular ("é o único que põe teto"). Ela tem
        # de reprovar EM VOZ ALTA no dia em que isso deixar de valer, em vez de
        # a tela afirmar sozinha uma coisa que o produto desmentiu.
        return (
            f"{len(com_teto)} perfis põem teto hoje — esta frase foi escrita "
            "para um só e precisa ser reescrita."
        )
    unico = com_teto[0]
    return (
        f"{ROTULOS_DOS_PERFIS[unico]} é o único que põe teto — "
        f"{forca_do_perfil(unico)} — e alcança {_lista(alcanca)} e nada mais. "
        f"{_lista(pendentes)} não têm por onde ser limitados."
    )


def _lista(nomes: list[str]) -> str:
    """``a``, ``b`` e ``c`` — em português, com "e" antes do último."""
    if not nomes:
        return "nada"
    if len(nomes) == 1:
        return nomes[0]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


# ---------------------------------------------------------------------------
# O exame
# ---------------------------------------------------------------------------
#: Como o veredito de ``storm_doctor`` vira selo na tela. Os três selos são os
#: do desenho (``.selo.ok``, ``.selo.aviso``, ``.selo.nt``) e mais nada.
#:
#: **As chaves são normalizadas, e isso foi medido:** o produto devolve
#: ``"[ OK ]"``, ``"[WARN]"`` e ``"[INFO]"`` — com colchetes, e o OK com espaços
#: dentro, porque a origem é a coluna alinhada do ``doctor`` no terminal. Uma
#: tabela com a chave ``"OK"`` casaria com NADA e a tela inteira sairia como
#: NOTA, calada.
_SELO_DO_VEREDITO: dict[str, tuple[str, str, str]] = {
    "OK": ("OK", "ok", "✓"),
    "WARN": ("AVISO", "aviso", "!"),
    "INFO": ("NOTA", "nt", "i"),
    "NOTE": ("NOTA", "nt", "i"),
}


def _selo(veredito: object) -> tuple[str, str, str]:
    """O selo de um veredito do ``storm_doctor``, com os colchetes tirados.

    Um veredito NOVO, de um produto mais novo que esta tela, cai em NOTA — e
    não some: dizer "NOTA" sobre uma linha que existe é honesto; engoli-la não.
    """
    chave = str(veredito).strip().strip("[]").strip().upper()
    return _SELO_DO_VEREDITO.get(chave, ("NOTA", "nt", "i"))


def exame(achados: list[tuple[str, str]] | None) -> dict[str, Any]:
    """A lista de achados e a CONTAGEM DERIVADA dela.

    **A contagem é derivada, e é aí que mora o defeito que esta função evita.**
    O desenho congelou em "8 linhas · nenhum aviso" — mas ``storm_report``
    devolve SEIS, e as duas condicionais do produto devolvem ``None`` quando não
    há divergência. Um "8" digitado seria falso na primeira máquina que não
    tivesse oito.
    """
    if achados is None:
        return {
            "contagem": NAO_DEU,
            "linhas": [],
            "vazio": "O exame não respondeu — não dá para dizer o que esta máquina tem.",
        }
    linhas = []
    avisos = 0
    for veredito, frase in achados:
        selo, cls, glifo = _selo(veredito)
        if cls == "aviso":
            avisos += 1
        linhas.append({"selo": selo, "cls": cls, "g": glifo, "txt": frase})
    quantas = len(linhas)
    if avisos == 0:
        cauda = "nenhum aviso"
    elif avisos == 1:
        cauda = "1 aviso"
    else:
        cauda = f"{avisos} avisos"
    plural = "linha" if quantas == 1 else "linhas"
    return {
        "contagem": f"{quantas} {plural} · {cauda}",
        "linhas": linhas,
        "vazio": "" if linhas else "O exame não achou nada a relatar nesta máquina.",
    }


# ---------------------------------------------------------------------------
# As travas
# ---------------------------------------------------------------------------
#: Os estados em que o Hefesto está DE PÉ. É a mesma matriz de
#: ``daemon_actions._ESTADOS_COM_DAEMON_DE_PE``, e a razão de ela existir aqui é
#: que o botão cinza precisa dela ANTES de haver widget: a tela nova não tem
#: `set_sensitive`, tem `disabled` na página.
DE_PE = ("online_systemd", "online_avulso")


def travas(leitura: Leitura) -> dict[str, str]:
    """Qual gesto está cinza AGORA, e POR QUÊ — o motivo vai para o tooltip.

    Botão cinza sem explicação manda a pessoa procurar defeito onde não há. E o
    contrário custa mais: o clique inútil dispara ``systemctl`` de verdade, o
    ``rc=0`` volta (``systemctl start`` numa unidade já ativa é sucesso) e a
    tela confirma um trabalho que não houve — é o defeito que
    ``_aplicar_sensibilidade_ligar_desligar`` curou na aba velha, e ele não pode
    renascer na nova.

    Devolve ``{gesto: motivo}``; gesto ausente = clicável.
    """
    presas: dict[str, str] = {}
    de_pe = leitura.status in DE_PE
    pausado = bool(isinstance(leitura.state, dict) and leitura.state.get("paused"))

    if not pausado:
        presas["retomar"] = (
            "O Hefesto não está pausado — não há de que retomar."
            if leitura.status is not None
            else "Não deu para saber se o Hefesto está pausado."
        )
    if not de_pe:
        presas["desligar"] = "O Hefesto já está desligado."
        presas["reiniciar"] = "O Hefesto está desligado — não há o que reiniciar."
    for gesto in ("ver-plugins", "ver-detalhes"):
        if not de_pe:
            presas[gesto] = "O Hefesto está desligado — não há o que perguntar a ele."
    return presas


# ---------------------------------------------------------------------------
# O pacote — UMA chamada por tique, não uma por valor
# ---------------------------------------------------------------------------
def pacote(leitura: Leitura) -> dict[str, Any]:
    """Tudo o que a tela precisa, numa estrutura só.

    **UMA chamada por TIQUE, não por valor.** Com doze endereços e dez tiques
    por segundo, uma chamada por valor seriam 120 travessias de fronteira por
    segundo para escrever o que cabe em dez.
    """
    linhas: dict[str, Linha] = {
        "hefesto-estado": linha_do_hefesto(leitura.status),
        "hefesto-pausa": linha_da_pausa(leitura.state),
        "hefesto-troca-de-perfil": linha_da_troca_de_perfil(leitura.state, leitura.deteccao),
        "hefesto-ambiente": linha_do_ambiente(leitura.ambiente),
        "bateria-impoe": linha_do_impoe(leitura.perfil),
        "bateria-vale-para": linha_do_vale_para(leitura.state),
    }
    return {
        "valores": {nome: linha._asdict() for nome, linha in linhas.items()},
        "autostart": autostart_ligado(leitura.autostart),
        "perfil": rotulo_do_perfil(leitura.perfil),
        "frase": frase_do_teto(),
        "exame": exame(leitura.achados),
        "registro": {"txt": NAO_DEU, "dica": SEM_FONTE["registro-texto"]},
        "travas": travas(leitura),
    }


__all__ = [
    "DE_PE",
    "ENDERECOS",
    "GESTOS",
    "GLIFO_AVISO",
    "GLIFO_INFO",
    "GLIFO_OK",
    "NAO_DEU",
    "SEM_DONO",
    "SEM_FONTE",
    "Leitura",
    "Linha",
    "autostart_ligado",
    "exame",
    "forca_do_perfil",
    "frase_do_teto",
    "linha_da_pausa",
    "linha_da_troca_de_perfil",
    "linha_do_ambiente",
    "linha_do_hefesto",
    "linha_do_impoe",
    "linha_do_vale_para",
    "pacote",
    "perfil_do_rotulo",
    "quantos_controles",
    "rotulo_do_perfil",
    "sem_markup",
    "travas",
]
