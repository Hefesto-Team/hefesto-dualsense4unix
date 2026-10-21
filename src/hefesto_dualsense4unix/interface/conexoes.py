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
        24/09/2026 — era «pelo cabo»/«pelo rádio», de antes da decisão de
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


CASA_DO_TETO_GLOBAL = "Perfil de bateria"
ABA_DO_TETO_GLOBAL = "Sistema"


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


def _o_x_da_dica(acao: Any) -> str:
    """O X no canto do cartão: o mesmo gesto do «Ignorar», sem palavra, com a dica no hover."""
    dados = "".join(f' data-{_e(k)}="{_e(v)}"' for k, v in acao.dados)
    return (f'<button class="cd-x" type="button" data-gesto="{_e(acao.gesto)}"{dados} '
            f'aria-label="{_e(acao.rotulo)}" data-dica="{_e(acao.titulo or acao.rotulo)}">'
            "\u00d7</button>")


def _o_cartao_da_dica(dica: Any, n: int, icone: Callable[[str], str]) -> str:
    """Um cartão: título (o porquê no hover), o de→para, UM botão e o X que ignora no canto."""
    quem = f"dica-{n}"
    detalhe = f'<p class="cd-detalhe">{_e(dica.detalhe)}</p>' if dica.detalhe else ""
    desenho = (
        f'<p class="cd-pic" aria-label="De {_e(dica.de)} para {_e(dica.para)}">'
        f'<span>{_e(dica.de)}</span><i aria-hidden="true">→</i><span>{_e(dica.para)}</span></p>'
        if dica.de and dica.para else "")
    x = _o_x_da_dica(dica.ignorar) if dica.ignorar is not None and not dica.calada else ""
    porque = " ".join(t for t in (dica.porque, dica.cura) if t)
    no_titulo = f' data-dica="{_e(porque)}"' if porque else ""
    return (
        f'<section class="cartao-dica nivel-{_e(dica.nivel)}{" calada" if dica.calada else ""}" '
        f'role="region" aria-label="{_e(PALAVRA_DO_NIVEL[dica.nivel])}: {_e(dica.titulo)}" '
        f'data-dica-id="{_e(dica.chave)}"><div class="cd-cab"><span class="cd-ic">'
        f'{icone(dica.icone)}</span><h4 id="{quem}-t"{no_titulo}><span class="t">'
        f'{_e(dica.titulo)}</span></h4>{x}</div>'
        f"{detalhe}{desenho}"
        f'<div class="cd-acao">{_o_botao_da_dica(dica.acao, "cd-botao")}</div></section>')


def html_das_dicas(painel: Any, icone: Callable[[str], str] = lambda _nome: "") -> str:
    """As dicas da aba Conexões: os cartões que pesam, numa fileira só; sem dica, «Tudo certo».

    Sem «mais N» e sem a linha dos ✓ (desenho aprovado de 05/10/2026): o próximo cartão entra
    quando ela ignora ou resolve um. ``icone`` desenha o símbolo de um cartão (o sprite é da
    página; este módulo não o conhece).
    """
    if not painel.visiveis:
        corpo = f'<p class="nada-a-mudar"><i aria-hidden="true"></i>{_e(NADA_A_MUDAR)}</p>'
    else:
        corpo = '<div class="dicas-fileira">' + "".join(
            _o_cartao_da_dica(d, n, icone) for n, d in enumerate(painel.visiveis)) + "</div>"
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
#: A face «Hubs e extensões» está SEMPRE no desenho, com o botão «Acrescentar hub»: ele abre a
#: pergunta curta (em qual entrada, nome opcional) e o ato é `LogicaDoMapa.acrescentar_hub`.
DICA_DOS_HUBS = (
    "O sistema não enxerga hubs nem extensões — quem diz onde estão é você."
)


def _primeira_maiuscula(frase: str) -> str:
    """Só a primeira letra sobe: o resto da frase fica como o dono a escreveu."""
    return frase[:1].upper() + frase[1:]


def html_do_mapa(
    faces: Sequence[Mapping[str, Any]],
    *,
    quem_esta: Mapping[str, tuple[str, str]],
    extensoes: Mapping[str, str],
    veredito_de: Any,
    rotulos: Mapping[str, str],
    dicas: Mapping[str, str],
    nomes: Mapping[str, str] | None = None,
    nomes_das_entradas: Mapping[str, str] | None = None,
    pergunta: Mapping[str, Any] | None = None,
) -> str:
    """As faces do gabinete, com um quadrado por entrada.

    `nomes` é `filha -> nome` do hub, se ela deu; `nomes_das_entradas`, `entrada -> nome` dado a
    ela; `pergunta` é a do «Acrescentar hub» (`{"aberta", "entradas"}`), estado de tela.

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
        corpo = _primeira_maiuscula(dentro[0] if dentro else rotulos["vazia"])
        texto, porque = _primeira_maiuscula(texto), _primeira_maiuscula(porque)
        dizeres = []
        if esticada:
            dizeres.append(dicas["esticada"])
        elif dentro:
            dizeres.append(dicas["enumera"].format(c=dentro[1]))
        dizeres.append(porque)
        linhas = [f'<span class="mm-n">{_e(numero)}</span>',
                  f'<span class="mm-c{"" if dentro else " mm-vazia"}">{_e(corpo)}</span>']
        if esticada:
            por_extensao = _primeira_maiuscula(rotulos["por_extensao"])
            linhas.append(f'<span class="mm-ext">{_e(por_extensao)}</span>')
        linhas.append(f'<span class="mm-v">{_e(texto)}</span>')
        return (f'<button class="mm-sq" data-v="{_e(classe)}" '
                f'data-gesto="escolher-entrada" data-entrada="{_e(numero)}" '
                f'title="{_e(" ".join(dizeres))}">' + "".join(linhas) + "</button>")

    face_da_entrada = {n: str(f.get("nome", "")) for f in faces for n in f.get("portas", [])}

    if not faces:
        # branco — e "não há nada aqui" é indistinguível de "isto quebrou".
        from hefesto_dualsense4unix.interface.logica_do_mapa import (
            DICA_SEM_FACE,
            ROTULO_SEM_FACE,
        )

        return (f'            <div class="tn-frase" title="{_e(DICA_SEM_FACE)}">'
                f'{_e(ROTULO_SEM_FACE)}</div>')

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

    from hefesto_dualsense4unix.interface import logica_do_mapa as _mm
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
        MAXIMO_DO_NOME_DA_ENTRADA,
        com_artigo,
        na_frase,
        rotulo,
    )

    nomes = nomes or {}
    nomes_das_entradas = nomes_das_entradas or {}
    aberta = bool(pergunta and pergunta.get("aberta"))
    celulas = "".join(
        f'<div class="mm-cel">{quadrado(filha, esticada=True)}'
        + (f'<span class="mm-hub-nome">{_e(nomes[filha])}</span>' if nomes.get(filha) else "")
        + f'<span class="mm-ligado">{_e(_mm.ROTULO_LIGADO)} '
        + com_artigo(f'<b>{_e(na_frase(mae, nomes_das_entradas.get(mae)))}</b>', em=True)
        + f' <span class="mudo">· {_e(face_da_entrada.get(mae, ""))}</span></span></div>'
        for mae, filha in extensoes.items())
    pergunta_html = ""
    if aberta:
        gravar = 'data-gesto="novo-hub-gravar" data-hef-forma="hub-pergunta"'
        cancelar = 'data-gesto="novo-hub-cancelar"'
        opcoes = "".join(
            f'<option value="{_e(n)}">'
            f'{_e(_primeira_maiuscula(rotulo(n, nomes_das_entradas.get(n))))}</option>'
            for n in (pergunta or {}).get("entradas", ()))
        pergunta_html = (
            f'''
              <div class="hub-pergunta" id="hub-pergunta">
                <label class="hub-rot">{_e(_mm.ROTULO_LIGADO)}
                  <select class="hub-sel" data-linha="hub-entrada">{opcoes}</select></label>
                <input class="mm-campo hub-nome" type="text" data-linha="hub-nome"
                  maxlength="{MAXIMO_DO_NOME_DA_ENTRADA}"
                  placeholder="{_e(_mm.NOME_DO_HUB_EM_BRANCO)}">
                <button class="btn" {gravar}>{_e(_mm.ROTULO_ACRESCENTAR)}</button>
                <button class="btn" {cancelar}>{_e(_mm.ROTULO_CANCELAR)}</button>
              </div>''')
    expandido = "true" if aberta else "false"
    blocos.append(
        f'''            <div class="mm-face" data-face="hubs">
              <div class="mm-face-cab"><span class="mm-face-nome" '''
        f'''title="{_e(DICA_DOS_HUBS)}">Hubs e extensões</span>
                <button class="btn mini" data-gesto="novo-hub" aria-expanded="{expandido}" '''
        f'''title="{_e(_mm.DICA_NOVO_HUB)}">{_e(_mm.ROTULO_NOVO_HUB)}</button></div>{pergunta_html}
              <div class="mm-grade mm-grade-hubs">{celulas}</div>
            </div>''')
    return "\n".join(blocos)
