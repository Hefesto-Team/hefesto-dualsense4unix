"""O que só vale quando o jogo reabre — a decisão, pura e sem GTK."""

from __future__ import annotations

from typing import Final, Literal

EXIGEM_RELANCAR: Final[frozenset[str]] = frozenset(
    {
        # "O que o controle faz agora" — trocar o modo mexe no `compose_env` ao
        # vivo, e o jogo já leu o ambiente na abertura.
        #
        # AGORA-E-DEPOIS-01 (08/08/2026, noite): "modo" VOLTOU a esta lista, e a
        # ida e a volta são a mesma decisão dela vista de dois lugares.
        #
        # Ele saiu na RELANCAR-ORDEM-01 porque o diálogo nascia no CLIQUE do
        # seletor — antes de ela poder escolher a máscara: *"como já aparece a
        # tela de aplicar e reiniciar se nem sei o que ele vai aplicar?"*. Estava
        # certa: perguntar ali é perguntar sobre uma decisão pela metade.
        #
        # Com o clique deixando de aplicar, a pergunta mudou de lugar — ela mora
        # no "Aplicar" do rodapé, onde modo E máscara já estão escolhidos. O
        # motivo da retirada caducou, e ela disse o que quer, vendo a tela:
        # *"se o jogo tiver aberto aparece o popup falando em fechar o jogo pra
        # aplicar e afins. e isso vai permitir aplicar tudo que alterar em todas
        # as abas"*.
        #
        # Sem isto, mudar SÓ o modo com o jogo aberto aplicava direto — que é o
        # caminho que produziu o "Jogador 3" fantasma. A JOGADOR-3-FANTASMA-01
        # continua sendo a cura do estado meio-a-meio; este diálogo é o que
        # impede de chegar lá sem ela saber.
        "modo",
        # TENTAR sem fechar o jogo" — pedido dela em 14/09, com a luz avisando o
        "mascara",
        "steam_input_do_jogo",
        "perfil_com_modo",
        "mouse_ou_teclado",
    }
)

MUDA_NA_HORA: Final[frozenset[str]] = frozenset(
    {
        "cor_da_luz",
        "brilho_da_luz",
        "efeito_da_luz",
        "gatilhos",
        "vibracao",
        "microfone",
        "audio_do_controle",
        "cadeado_do_autoswitch",
        "perfil_sem_modo",
        "reconciliar_jogadores",
    }
)

Escolha = Literal["fechar_e_abrir", "na_proxima_abertura", "cancelar"]

MARCADOR_PENDENTE: Final = "●"


def texto_do_pendente(*, modo: str | None = None, mascara: str | None = None) -> str:
    """A linha que diz o que ainda NÃO valeu — função pura, sem GTK."""
    partes = [p for p in (modo, mascara) if p]
    if not partes:
        return ""
    return f"{MARCADOR_PENDENTE} vai mudar para: " + ", ".join(partes)


TOAST_ESCOLHA_ANOTADA: Final = (
    'Anotado. Clique em "Aplicar" para valer — o jogo vê a mudança quando abrir.'
)

TOAST_ESCOLHA_DESFEITA: Final = (
    "Isso já é o que está valendo — não há o que aplicar."
)


def precisa_perguntar(*, mudanca: str, jogo_aberto: bool) -> bool:
    """True quando esta mudança, agora, exige decidir sobre o jogo aberto."""
    return jogo_aberto and mudanca in EXIGEM_RELANCAR


def frase_da_mudanca(mudanca: str, valor: str | None = None) -> str:
    """A primeira linha do diálogo, no léxico dos rótulos da janela."""
    if mudanca == "modo":
        return f"Você mudou: O que o controle faz agora: {valor}."
    if mudanca == "mascara":
        return f"Você mudou: O jogo vê o controle como: {valor}."
    if mudanca == "steam_input_do_jogo":
        if valor == "marcado":
            return "Você marcou este jogo: a entrada dele passa a vir da Steam."
        return (
            "Você tirou a marca deste jogo: ele volta a ver o controle virtual "
            "do Hefesto."
        )
    if mudanca == "perfil_com_modo":
        return f"Você ativou o perfil {valor}, e ele muda o que o jogo vê."
    if mudanca == "mouse_ou_teclado":
        return "Você mexeu no mouse/teclado do controle, e isso desliga o gamepad."
    return "Você mudou um ajuste que o jogo só vê quando abre."


def corpo_do_dialogo(*, mudanca: str, valor: str | None, jogo: str | None) -> str:
    """O corpo do diálogo. Puro, para o texto ser testável sem abrir janela."""
    alvo = jogo or "O jogo"
    return (
        f"{frase_da_mudanca(mudanca, valor)}\n\n"
        f"{alvo} está aberto, e ele recebeu os ajustes do controle na hora em "
        "que abriu — mudar isso agora não chega até ele. E mexer no controle "
        "com o jogo aberto é pior: isso já deixou você sem controle nenhum no "
        "meio da partida.\n\n"
        "Se eu fechar agora, o que você não salvou se perde. Depois eu abro o "
        "jogo de novo pela Steam, já com a mudança valendo.\n\n"
        "Se preferir terminar primeiro, eu guardo a mudança e aplico assim que "
        "este jogo fechar — na próxima abertura já vale.\n\n"
        "A cor da luz, os gatilhos e a vibração continuam mudando na hora, com "
        "o jogo aberto. Só isto aqui precisa da abertura."
    )


TITULO: Final = "Posso fechar o jogo e abrir de novo?"

ROTULO_CANCELAR: Final = "Cancelar"
ROTULO_DEPOIS: Final = "Aplicar na próxima abertura"
ROTULO_FECHAR: Final = "Aplicar agora e reiniciar o jogo"


def toast_da_escolha(
    escolha: Escolha, *, jogo: str | None = None, guardou: bool = True
) -> str:
    """O que o rodapé diz depois. Cada saída tem a sua frase honesta."""
    if escolha == "cancelar":
        return "Nada mudou — o jogo continua como estava."
    if escolha == "na_proxima_abertura":
        alvo = jogo or "o jogo"
        if guardou:
            return (
                f"Guardado — aplico assim que {alvo} fechar. Na próxima abertura "
                "já vale."
            )
        return (
            "Não mudei nada agora — isto só vale quando o jogo abre. Refaça a "
            f"escolha depois de fechar {alvo}."
        )
    return "Pronto — o jogo fechou, a mudança valeu e eu pedi a abertura à Steam."


def toast_do_relancamento(
    *, fechou: bool, reabriu: bool, appid: int | None = None
) -> str:
    """O que o rodapé diz DEPOIS do relançamento — o que de fato aconteceu."""
    if not fechou:
        return (
            "A Steam não fechou — a mudança está gravada e vale na próxima vez "
            "que você abrir o jogo."
        )
    if not reabriu:
        if appid is None:
            return (
                "Fechei a Steam e a mudança valeu. Não consegui identificar qual "
                "jogo reabrir — abra pela Steam quando quiser."
            )
        return (
            "Fechei a Steam e a mudança valeu, mas não consegui pedir a abertura "
            "do jogo — abra pela Steam."
        )
    return (
        "Pronto: fechei o jogo, a mudança valeu, e pedi à Steam para abrir de "
        "novo. Pode demorar alguns segundos."
    )

