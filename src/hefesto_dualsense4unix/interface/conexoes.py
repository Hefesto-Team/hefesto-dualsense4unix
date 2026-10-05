"""As frases, os desenhos e as contas da aba 08 (Conexões), sem GTK."""
from __future__ import annotations

import html
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.dicas_da_conexao import NADA_A_MUDAR, PALAVRA_DO_NIVEL

TRACO = "—"

FAMILIAS: frozenset[str] = frozenset(
    {"mesa", "controle", "exame", "ordem", "adaptador", "vizinho", "pista", "rodape"}
)


SEM_FONTE: tuple[tuple[str, str, str], ...] = (
    (
        "exame.quando",
        'A tela diz "Examinado há 3 minutos". O exame não guarda quando correu: '
        "`exame_da_mesa` devolve os cinco `Item` e nenhum carimbo de tempo.",
        "MIGRA-CONEXOES-07 — quem der o carimbo dá o texto.",
    ),
    (
        "controle.*.mascara",
        "A tela mostra uma máscara POR CONTROLE (o mockup pinta quatro "
        "diferentes). O produto guarda UMA por máquina, em "
        "`state['gamepad_emulation']['flavor']` — o item de `controllers` não "
        "tem o campo.",
        "Contradição NOVA, sem sprint: não está no §0 do índice desta onda.",
    ),
    (
        "controle.*.mic.escopo",
        "A tela oferece a escolha por controle. O produto guarda um valor por "
        "máquina, em `state['mic_button_toggles_system']`.",
        "MIGRA-CONEXOES-06 — §0.7 do índice, e é palavra dela.",
    ),
    (
        "controle.*.vibracao.sem-teto",
        "'Sem teto' é a única das TRÊS opções sem representação possível: "
        "`ControllerRumbleOverride` (`profiles/schema.py:752`) só diz QUAL "
        "política a peça usa, nunca 'esta peça ignora o teto do orçamento'; e o "
        "`min` que imporia um teto de verdade vive em "
        "`core.rumble._effective_mult`, que não conhece `uniq` e roda antes de a "
        "peça ser endereçada. Traduzi-la por 'balanceado' deixaria a peça mais "
        "FRACA que as outras sob um global 'max'; por 'max', mais FORTE que o "
        "global sob 'balanceado' — um campo chamado teto AUMENTANDO a força. "
        "A CONTA ESTÁ EM `politica_do_rotulo`, derivada do `RUMBLE_POLICY_MULT` "
        "e não digitada: ela estava escrita à mão aqui e em mais dois lugares, e "
        "os três diziam 0,667 com o degrau mordido para outra coisa. "
        "As outras duas ganharam fonte em 01/09/2026.",
        "MIGRA-CONEXOES-11 — §0.5 do índice, e é palavra dela.",
    ),
    (
        "vizinho.*.qual",
        "O que cada rádio vizinho É ('Wi-Fi', 'Teclado'...) é declaração dela, "
        "guardada em `maquina.json`. Sem declaração o produto sabe o "
        "vid:pid e mais nada — e adivinhar pelo vid:pid seria inventar.",
        "Já responde: `ordens_da_mesa.Leitura.nomes_declarados` quando existe.",
    ),
)


class EnderecoInvalido(ValueError):  # noqa: N818 — o projeto é em português
    """Endereço fora da gramática. É erro de programação, não de dado."""


def familia_de(endereco: str) -> str:
    """A família de um ``data-v``, recusando o que está fora do conjunto fechado."""
    familia = endereco.split(".", 1)[0]
    if familia not in FAMILIAS:
        raise EnderecoInvalido(
            f"{endereco!r}: família {familia!r} não é uma das {sorted(FAMILIAS)}"
        )
    return familia


def endereco_por_posicao(endereco: str) -> bool:
    """O endereço fala de POSIÇÃO na mesa em vez de identidade?"""
    return any(
        pedaco[:1] == "p" and pedaco[1:].isdigit() for pedaco in endereco.split(".")
    )


def v(*partes: str) -> str:
    """Monta um ``data-v`` e o valida na hora. ``v("controle", uniq, "bateria")``."""
    endereco = ".".join(str(p) for p in partes)
    familia_de(endereco)
    if endereco_por_posicao(endereco):
        raise EnderecoInvalido(
            f"{endereco!r}: endereço por POSIÇÃO. A chave de um controle é o "
            "uniq — p1..p4 é a mesa de exemplo do mockup."
        )
    return endereco


def _e(texto: object) -> str:
    """Escapa para HTML. Todo texto que vem de fora passa por aqui."""
    return html.escape(str(texto), quote=True)


NOME_DO_TRANSPORTE = {"usb": "USB", "bt": "BT", "bluetooth": "BT"}

NOME_DA_MASCARA = {"dualsense": "DualSense", "xbox": "Xbox 360", "nintendo": "Nintendo Pro"}


@dataclass(frozen=True)
class Controle:
    """Uma linha do quadro "Gestão Controles" — só o que ESTA aba mostra."""

    uniq: str
    jogador: int
    via: str
    bateria: int | None
    plastico: str = ""
    cor_nome: str = ""
    fabricante: str = "Sony"
    mic_ligado: bool = True

    @property
    def nome(self) -> str:
        """``Sony • Player 1 • Cosmic Red • USB`` — a linha de identidade."""
        pedacos = [self.fabricante, f"Player {self.jogador}"]
        if self.cor_nome:
            pedacos.append(self.cor_nome)
        pedacos.append(NOME_DO_TRANSPORTE.get(self.via, self.via.upper()))
        return " • ".join(pedacos)

    @property
    def texto_da_bateria(self) -> str:
        return TRACO if self.bateria is None else f"{self.bateria}%"

    @property
    def pelo_radio(self) -> bool:
        return self.via not in ("usb", "cabo")

    @property
    def texto_do_microfone(self) -> str:
        """*Ligado, pelo BT • Pela ponte* — e o "por onde" NÃO é escolha.

        Pelo cabo o microfone chega pela placa de áudio do próprio aparelho;
        pelo rádio, pela ponte do Hefesto, porque o DualSense não tem A2DP nem
        HFP. Quem decide é o transporte, e por isso esta frase é derivada, nunca
        perguntada.

        A PALAVRA DO TRANSPORTE É A DA TELA (:data:`NOME_DO_TRANSPORTE`) desde
        24/09/2026 — era «pelo cabo»/«pelo rádio», de antes da decisão dela de
        21/09. É a mesma frase de ``pacotes.a08_conexoes.caminho_do_microfone``.
        """
        estado = "Ligado" if self.mic_ligado else "Desligado"
        if self.pelo_radio:
            return f"{estado}, pelo {NOME_DO_TRANSPORTE['bt']} • Pela ponte"
        return f"{estado}, pelo {NOME_DO_TRANSPORTE['usb']} • Placa do controle"


def texto_da_contagem(controles: Sequence[Controle]) -> str:
    """``4 controles • 2 USB • 2 BT`` — o canto do quadro 1."""
    radio = sum(1 for c in controles if c.pelo_radio)
    usb = len(controles) - radio
    pedacos = [f"{len(controles)} {'controle' if len(controles) == 1 else 'controles'}"]
    if usb:
        pedacos.append(f"{usb} {NOME_DO_TRANSPORTE['usb']}")
    if radio:
        pedacos.append(f"{radio} {NOME_DO_TRANSPORTE['bt']}")
    return " • ".join(pedacos)


SEGUE_O_GLOBAL = "Segue o global"

NAO_SEI_A_FORCA = "e não dá para dizer quanta força chega ao motor agora"


def por_cento(fracao: float) -> str:
    """`0.3` → `"30% da força"`. A ÚNICA grafia desta frase nesta casa.

    Ela existia em QUATRO — `secao_orcamento.celula_do_teto:379`,
    `secao_orcamento._dica_da_bateria_longa:240`, `interface.sistema
    .forca_do_perfil:417` e a que este arquivo digitou em 01/09/2026 —, e a
    quarta era a única que não passava pelo dono do NÚMERO. Aqui só a FORMA é
    própria; o número vem sempre de quem o calcula.
    """
    return f"{round(fracao * 100)}% da força"


def fala_do_teto(chave: str | None) -> str:
    """A frase de tela do teto que uma chave de ORÇAMENTO DA MESA impõe."""
    from hefesto_dualsense4unix.core.rumble import SEM_TETO, teto_do_orcamento

    teto = teto_do_orcamento(chave)
    return str(SEM_TETO) if teto is None else por_cento(teto)


def opcoes_do_teto() -> tuple[str, str, str]:
    """As três opções do campo, NA ORDEM DA TELA — o desenho que ela aprovou."""
    from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO

    return (SEGUE_O_GLOBAL, fala_do_teto(""), fala_do_teto(_ORCAMENTO_COM_TETO))


CASA_DO_TETO_GLOBAL = "Perfil de Bateria"
ABA_DO_TETO_GLOBAL = "Sistema"


def politica_do_rotulo(rotulo: str) -> str | None:
    """A ``policy`` de disco que uma opção do campo grava. ``None`` = não grava."""
    from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    segue, sem_teto, economia = opcoes_do_teto()
    if rotulo == segue:
        return None
    if rotulo == economia:
        return str(_ORCAMENTO_COM_TETO)
    if rotulo == sem_teto:
        base, alto = RUMBLE_POLICY_MULT["balanceado"], RUMBLE_POLICY_MULT["max"]
        conta = f"{base:g}/{alto:g} = {base / alto:.3f}".replace(".", ",")
        raise ValueError(
            f"{sem_teto!r} é a única das três opções sem tradução para o "
            f"perfil. `ControllerRumbleOverride` só diz QUAL política esta peça "
            f"usa, nunca 'esta peça ignora o teto do orçamento': gravar "
            f"'balanceado' a deixaria mais FRACA que as outras quando o global "
            f"for 'max' ({conta}), e gravar 'max' a deixaria mais FORTE "
            f"que o global quando ele for 'balanceado' — um campo chamado teto "
            f"aumentando a força. A frase que falta é dela "
            f"(MIGRA-CONEXOES-11).")
    raise ValueError(f"{rotulo!r} não é resposta desta lista: {list(opcoes_do_teto())}")


def rotulo_da_politica(policy: str | None) -> str | None:
    """O que o CAMPO mostra para uma ``policy`` guardada. ``None`` = não sabe.

    ``None`` de entrada é "sem override" e vira :data:`SEGUE_O_GLOBAL`. ``None``
    de SAÍDA é outra coisa: o perfil guarda uma política que este campo não sabe
    mostrar, e quem chama tem de DECLARAR isso em vez de escolher uma das três.

    POR QUE NÃO SERVE A :func:`fala_do_teto` AQUI, e a diferença custou um
    defeito nesta mesma leva: ela responde pelo ORÇAMENTO DA MESA, onde só o
    `economia` impõe teto e todo o resto é "Sem teto". Aplicada a um override
    por controle, ela traduziria `balanceado` e `max` — os dois — como "Sem
    teto", que é justamente a opção sem tradução. Aqui a pergunta é outra: das
    quatro políticas que `ControllerRumbleOverride` aceita
    (`profiles/schema.py:752`), **uma só** tem opção no campo.
    """
    from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO

    if not policy:
        return SEGUE_O_GLOBAL
    if policy == _ORCAMENTO_COM_TETO:
        return fala_do_teto(_ORCAMENTO_COM_TETO)
    return None


@dataclass(frozen=True)
class Vibracao:
    """AS QUATRO COISAS QUE DECIDEM A FORÇA NO MOTOR DE UM CONTROLE.

    TRÊS DELAS SE CHAMAVAM "O GLOBAL" ATÉ 01/09/2026, e a tela reportava a
    errada — foi o defeito que segurou esta leva. A conta inteira, do disco ao
    motor, é::

        no motor = forca_do_global(a_viva, orcamento) * MULT[do_controle]/MULT[do_perfil]
                   └────── core.rumble ───────┘   └── profiles.manager.fator_da_unidade ──┘

    :param do_controle: ``controllers[uniq].rumble.policy`` do perfil — o
        override desta peça, ``None`` quando ela não sobrepõe nada.
    :param do_perfil: ``Profile.rumble.policy`` — **o DENOMINADOR**. O fator por
        peça é RELATIVO a ele (`profiles/manager.py:1959`), e não à política que
        multiplica. Sem opinião, o produto assume ``balanceado``.
    :param a_viva: ``state['rumble_policy']`` — **o que MULTIPLICA**, e é o único
        "global" que o motor sente (`daemon/ipc_handlers.py:2493` publica o
        ``DaemonConfig.rumble_policy`` que `core.rumble._effective_mult` lê).
        ``None`` = o serviço não disse, e aí a tela não afirma número nenhum.
    :param orcamento: a chave do ``maquina.json`` — o teto por CIMA da viva,
        aplicado com ``min``. ``None`` = ninguém declarou, que não impõe teto.
    :param a_mesa_respondeu: ``False`` quando não deu para LER o ``maquina.json``.
        Sem isto, "não consegui ler" e "ninguém declarou" viravam o mesmo
        ``None``, e a tela publicava a ausência de notícia como uma afirmação —
        exatamente o que o dono da fonte proíbe (`secao_orcamento
        .orcamento_em_vigor`: *"None aqui significa 'não sei', nunca 'sem teto'"*).

    OS CAMPOS SÃO NOMEADOS E A CLASSE É CONGELADA de propósito: os quatro são
    ``str | None`` e uma troca de posição entre ``do_perfil`` e ``a_viva`` é
    silenciosa, verde em toda régua e errada no motor. Foi como o defeito
    nasceu.
    """

    do_controle: str | None = None
    do_perfil: str | None = None
    a_viva: str | None = None
    orcamento: str | None = None
    a_mesa_respondeu: bool = True


def forca_no_motor(v: Vibracao) -> float | None:
    """A fração do que o JOGO pediu que chega ao motor DESTE controle."""
    from hefesto_dualsense4unix.core.rumble import forca_do_global
    from hefesto_dualsense4unix.profiles.manager import fator_da_unidade

    if not v.a_mesa_respondeu:
        return None
    global_ = forca_do_global(v.a_viva, v.orcamento)
    if global_ is None:
        return None
    if not v.do_controle:
        return global_
    fator = fator_da_unidade(v.do_controle, v.do_perfil)
    return None if fator is None else global_ * fator


def teto_que_vale(v: Vibracao) -> tuple[str | None, str]:
    """``(o que o CAMPO mostra, a frase de quem manda neste controle)``."""
    no_motor = forca_no_motor(v)
    entrega = (NAO_SEI_A_FORCA if no_motor is None
               else f"e o motor recebe <b>{por_cento(no_motor)}</b>")
    if not v.do_controle:
        return SEGUE_O_GLOBAL, f"este controle <b>segue o global</b>, {entrega}"
    meu = rotulo_da_politica(v.do_controle)
    if meu is None:
        return None, (
            f"o perfil guarda <code>{_e(v.do_controle)}</code> para este "
            f"controle, e este campo não sabe mostrar essa política — o perfil "
            f"manda, a caixa fica como está, {entrega}")
    if no_motor is not None and meu == por_cento(no_motor):
        return meu, f"este controle <b>sobrepõe</b> o global, {entrega}"
    return meu, (f"este controle <b>sobrepõe</b> o global com <b>{meu}</b>, que é "
                 f"RELATIVO ao global — hoje {entrega.removeprefix('e ')}")


def dica_do_teto(v: Vibracao) -> str:
    """A frase inteira do ``?`` do campo, com marcação — dono único das duas telas."""
    return (f"O teto da vibração <b>deste controle</b>. O global manda e o do controle "
            f"sobrepõe: hoje {teto_que_vale(v)[1]}. Quem muda o global é o "
            f"<b>{CASA_DO_TETO_GLOBAL}</b>, na aba <b>{ABA_DO_TETO_GLOBAL}</b> — ele decide "
            f"o que custa bateria, e esta aba mede o rádio. O degrau vem de "
            f"<code>RUMBLE_POLICY_MULT</code>, que é o dono dele — a vibração é o único "
            f"recurso com teto real hoje.")


SELO_DO_ESTADO = {
    "certo": ("ok", "CERTO"),
    "atencao": ("warn", "AJUSTAR"),  # (noqa-acento): chave de máquina, ASCII por contrato
    "problema": ("warn", "AJUSTAR"),
    "nao_sei": ("info", "NOTA"),
}


def _o_botao_da_dica(acao: Any, classe: str) -> str:
    """O botão de um cartão: âncora quando navega, botão quando faz gesto."""
    rotulo = _e(acao.rotulo)
    if acao.href:
        return f'<a class="btn {classe}" href="{_e(acao.href)}">{rotulo}</a>'
    dados = "".join(f' data-{_e(k)}="{_e(v)}"' for k, v in acao.dados)
    dica = f' title="{_e(acao.titulo)}"' if acao.titulo else ""
    return (f'<button class="btn {classe}" type="button" data-gesto="{_e(acao.gesto)}"'
            f'{dados}{dica}>{rotulo}</button>')


def _o_cartao_da_dica(dica: Any, n: int, icone: Callable[[str], str]) -> str:
    """Um cartão: título, o de→para, UM botão, e o porquê atrás do ⓘ."""
    quem = f"dica-{n}"
    detalhe = f'<p class="cd-detalhe">{_e(dica.detalhe)}</p>' if dica.detalhe else ""
    desenho = (
        f'<p class="cd-pic" aria-label="de {_e(dica.de)} para {_e(dica.para)}">'
        f'<span>{_e(dica.de)}</span><i aria-hidden="true">→</i><span>{_e(dica.para)}</span></p>'
        if dica.de and dica.para else "")
    ignora = (_o_botao_da_dica(dica.ignorar, "cd-ignora")
              if dica.ignorar is not None and not dica.calada else "")
    cura = f'<p class="cd-cura">{_e(dica.cura)}</p>' if dica.cura else ""
    porque = (
        f'<div class="cd-porque" id="{quem}-p" hidden><p>{_e(dica.porque)}</p>{cura}{ignora}</div>'
        if dica.porque or cura or ignora else "")
    info = (
        f'<button class="cd-info" type="button" aria-expanded="false" aria-controls="{quem}-p" '
        f'aria-label="Por quê: {_e(dica.titulo)}">i</button>' if porque else "")
    return (
        f'<section class="cartao-dica nivel-{_e(dica.nivel)}{" calada" if dica.calada else ""}" '
        f'role="region" aria-labelledby="{quem}-t" data-dica="{_e(dica.chave)}">'
        f'<div class="cd-cab"><span class="cd-ic">{icone(dica.icone)}</span>'
        f'<h4 id="{quem}-t"><span class="so-leitor">{_e(PALAVRA_DO_NIVEL[dica.nivel])}: </span>'
        f'<span class="t">{_e(dica.titulo)}</span></h4>{info}</div>'
        f"{detalhe}{desenho}{porque}"
        f'<div class="cd-acao">{_o_botao_da_dica(dica.acao, "cd-botao")}</div></section>')


def html_das_dicas(painel: Any, icone: Callable[[str], str] = lambda _nome: "") -> str:
    """As dicas da aba Conexões: os cartões que pesam, «mais N» e a linha do que está certo.

    ``icone`` desenha o símbolo de um cartão (o sprite é da página; este módulo não o conhece).
    """
    if painel.vazio:
        corpo = f'<p class="nada-a-mudar">{_e(NADA_A_MUDAR)}</p>'
    else:
        corpo = '<div class="dicas-fileira">' + "".join(
            _o_cartao_da_dica(d, n, icone) for n, d in enumerate(painel.visiveis)) + "</div>"
    if painel.demais:
        base = len(painel.visiveis)
        corpo += (
            f'<details class="mais-dicas"><summary>mais {len(painel.demais)}</summary>'
            '<div class="dicas-fileira">' + "".join(
                _o_cartao_da_dica(d, base + n, icone) for n, d in enumerate(painel.demais))
            + "</div></details>")
    if painel.certos:
        corpo += '<p class="dicas-certas">' + " · ".join(
            f"<span>✓ {_e(c)}</span>" for c in painel.certos) + "</p>"
    return f'<div class="dicas">{corpo}</div>'


RESPOSTAS_DO_VIZINHO = (
    "— O que é? —",
    "Wi-Fi",
    "Teclado",
    "Mouse",
    "Webcam",
    "Caixa de som",
    "Outro",
    "Não sei",
)


#      (`confissao_do_desenho`). A tela mostrava menos e podia mostrar diferente.


DICA_NOVA_ENTRADA = "Cria uma entrada nova nesta face, com o próximo número livre."
DICA_NOVO_HUB = (
    "Acrescenta um hub ou uma extensão. O sistema não os enxerga — quem diz "
    "onde estão é você."
)


def html_do_mapa(
    faces: Sequence[Mapping[str, Any]],
    *,
    quem_esta: Mapping[str, tuple[str, str]],
    extensoes: Mapping[str, str],
    veredito_de: Any,
    rotulos: Mapping[str, str],
    dicas: Mapping[str, str],
) -> str:
    """As faces do gabinete, com um quadrado por entrada.

    `faces` é `[{"nome": …, "portas": [numero, …]}, …]` — a forma do
    `MapaDaMesa`, para que o chamador não precise traduzir nada.

    `quem_esta` é `numero -> (espécie, nome do kernel)`. A espécie é o que o
    quadrado mostra; o nome do kernel é o que a dica diz, porque é ele que
    distingue dois aparelhos iguais.

    `veredito_de(numero, esticada)` devolve `(classe, texto, porque)`. Ele é
    INJETADO e não importado: o motor de verdade (`arranjo_da_mesa.julgar`,
    pelo `mapa_da_mesa.veredito_do_quadrado`) precisa de uma `Bancada`, que
    precisa do censo do barramento — e este módulo não lê `/sys` por decisão,
    escrita no cabeçalho dele. Quem lê é quem chama.

    O `data-v` E O `data-gesto` CONVIVEM no quadrado, e não se trocam: a CSS
    pinta por `data-v` (`.mm-sq[data-v="cheia"]`) e o piloto ouve o
    `data-gesto`. Trocar um pelo outro apagaria a cor.
    """
    def quadrado(numero: str, esticada: bool = False) -> str:
        classe, texto, porque = veredito_de(numero, esticada)
        dentro = quem_esta.get(numero)
        corpo = dentro[0] if dentro else rotulos["vazia"]
        dizeres = []
        if esticada:
            dizeres.append(dicas["esticada"])
        elif dentro:
            dizeres.append(dicas["enumera"].format(c=dentro[1]))
        dizeres.append(porque)
        linhas = [f'<span class="mm-n">{_e(numero)}</span>',
                  f'<span class="mm-c{"" if dentro else " mm-vazia"}">{_e(corpo)}</span>']
        if esticada:
            linhas.append(f'<span class="mm-ext">{_e(rotulos["por_extensao"])}</span>')
        linhas.append(f'<span class="mm-v">{_e(texto)}</span>')
        return (f'<button class="mm-sq" data-v="{_e(classe)}" '
                f'data-gesto="escolher-entrada" data-entrada="{_e(numero)}" '
                f'title="{_e(" ".join(dizeres))}">' + "".join(linhas) + "</button>")

    face_da_entrada = {n: str(f.get("nome", "")) for f in faces for n in f.get("portas", [])}

    if not faces:
        # branco — e "não há nada aqui" é indistinguível de "isto quebrou".
        from hefesto_dualsense4unix.interface.logica_do_mapa import ROTULO_SEM_FACE

        return f'            <div class="tn-frase">{_e(ROTULO_SEM_FACE)}</div>'

    blocos = []
    for indice, face in enumerate(faces):
        grade = "".join(f'<div class="mm-cel">{quadrado(str(n))}</div>'
                        for n in face.get("portas", []))
        blocos.append(
            f'''            <div class="mm-face" data-face="{indice}">
              <div class="mm-face-cab"><span class="mm-face-nome">{_e(face.get("nome", ""))}</span>
                <button class="btn mini" data-gesto="nova-entrada" data-face="{indice}" '''
            f'''title="{_e(dicas["nova_entrada"])}">{_e(rotulos["nova_entrada"])}</button></div>
              <div class="mm-grade">{grade}</div>
            </div>''')

    if extensoes:
        celulas = "".join(
            f'<div class="mm-cel">{quadrado(filha, esticada=True)}'
            f'<span class="mm-ligado">ligado na entrada <b>{_e(mae)}</b>'
            f' <span class="mudo">· {_e(face_da_entrada.get(mae, ""))}</span></span></div>'
            for mae, filha in extensoes.items())
        blocos.append(
            f'''            <div class="mm-face" data-face="hubs">
              <div class="mm-face-cab"><span class="mm-face-nome">Hubs e extensões</span>
                <button class="btn mini" data-gesto="novo-hub" '''
            f'''title="{_e(dicas["novo_hub"])}">Acrescentar hub</button></div>
              <div class="mm-grade mm-grade-hubs">{celulas}</div>
            </div>''')
    return "\n".join(blocos)
