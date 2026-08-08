"""O que só vale quando o jogo reabre — a decisão, pura e sem GTK.

RELANCAR-01 (08/08/2026). Nasceu de um defeito medido na máquina dela: mudar a
máscara do controle com o jogo aberto **deixou-a sem controle nenhum no meio da
partida**. O motivo é estrutural e não tem contorno:

    o wrapper termina em `exec env "$@"` (`assets/hefesto-launch.sh:320`)

O jogo recebe as variáveis **uma vez**, na abertura, e elas ficam. Reescrever o
`launch_env` depois não alcança o processo em curso, e mexer no grab/vpad ao vivo
invalida os handles que o jogo já abriu (R-04). Sobram dois estados honestos:

===========================  =======================================
mudança acontece…            resultado
===========================  =======================================
**antes** de o jogo abrir    o jogo e a máquina concordam — funciona
**com o jogo aberto**        cada um com uma configuração — quebra
===========================  =======================================

Foram oferecidas a ela duas saídas — recusar o gesto, ou fazê-lo valer só na
próxima abertura. **Ela recusou as duas**, e com a razão certa: *"não gosto de
nenhuma das duas. Temos que fazer isso funcionar."* E propôs a terceira, que é a
única que resolve em vez de evitar — se a mudança exige relançar, **ofereça
relançar**, e o tempo de reconexão é o preço, que ela aceita pagar.

POR QUE A LISTA DO QUE **NÃO** EXIGE É METADE DA ENTREGA
========================================================
Se o diálogo aparecer quando ela troca a cor da luz, ele vira ruído e ela aprende
a clicar sem ler — e aí o diálogo que importa **não é lido**. A separação abaixo
é a entrega tanto quanto o diálogo, e ela vem da medição dela de 06/08
(`CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*): dentro de um jogo, a **saída**
continua sendo do Hefesto — cor, gatilho e vibração mudam na hora. O que não muda
ao vivo é a **entrada**.
"""

from __future__ import annotations

from typing import Final, Literal

#: As mudanças que o jogo só enxerga na próxima abertura, porque mexem na
#: ENTRADA — quem entrega os eventos ao jogo — e portanto no `compose_env`
#: (`daemon/launch_env.py`) ou na borda da exceção de Steam Input
#: (`daemon/subsystems/gamepad.py:sync_steam_input_exception`).
#:
#: Cada uma foi conferida contra o caminho de código que ela dispara; nenhuma
#: entrou por suspeita.
EXIGEM_RELANCAR: Final[frozenset[str]] = frozenset(
    {
        # "O que o controle faz agora" — muda `native_mode`/`emulation_enabled`.
        "modo",
        # "O jogo vê o controle como" — máscara diferente recria o vpad, e o
        # Xbox ainda acrescenta `SDL_JOYSTICK_HIDAPI=0`.
        "mascara",
        # A caixinha do Steam Input do jogo: escrever no `steam_input_apps.txt`
        # cria uma BORDA em `sync_steam_input_exception`, que faz ungrab e
        # suspende os vpads com o jogo aberto. Foi o que produziu o "Jogador 3"
        # fantasma que ela fotografou.
        "steam_input_do_jogo",
        # Ativar um perfil cuja seção `mode` difere da vigente — mesmo eixo.
        "perfil_com_modo",
        # Mouse/teclado e gamepad são mutuamente exclusivos: ligar um derruba o
        # outro (`gamepad.py`, a exclusão do modo jogo).
        "mouse_ou_teclado",
    }
)

#: O que muda NA HORA, com o jogo aberto, e por isso nunca pergunta nada.
#: Não é usada em código — é documentação executável do outro lado da fronteira,
#: e o teste a compara com `EXIGEM_RELANCAR` para garantir que ninguém escreva
#: uma mudança nas duas listas.
MUDA_NA_HORA: Final[frozenset[str]] = frozenset(
    {
        "cor_da_luz",
        "brilho_da_luz",
        "efeito_da_luz",
        "gatilhos",
        "vibracao",
        "microfone",
        "audio_do_controle",
        # O cadeado "Não trocar de perfil sozinho" não escreve no aparelho.
        "cadeado_do_autoswitch",
        # Salvar/renomear perfil SEM mexer na seção `mode`.
        "perfil_sem_modo",
        # É justamente o gesto de partida aberta.
        "reconciliar_jogadores",
    }
)

#: O que a pessoa escolheu no diálogo.
Escolha = Literal["fechar_e_abrir", "na_proxima_abertura", "cancelar"]


def precisa_perguntar(*, mudanca: str, jogo_aberto: bool) -> bool:
    """True quando esta mudança, agora, exige decidir sobre o jogo aberto.

    **Sem jogo aberto não se pergunta nada** — a mudança aplica direto, como
    sempre fez. O diálogo é caro (interrompe) e só se paga quando há um jogo
    para o qual a mudança não chegaria.

    Mudança desconhecida devolve ``False`` de propósito: uma tela nova que
    esqueça de se registrar aqui continua funcionando como antes, em vez de
    passar a interromper a partida dela por engano. Falha para o lado de não
    incomodar — e o teste de cobertura acusa a ausência, que é onde ela deve
    doer.
    """
    return jogo_aberto and mudanca in EXIGEM_RELANCAR


def frase_da_mudanca(mudanca: str, valor: str | None = None) -> str:
    """A primeira linha do diálogo, no léxico dos rótulos da janela.

    O vocabulário sai de `home_actions._MODE_ITEMS`/`_FLAVOR_ITEMS` e do rótulo
    "O jogo vê o controle como:" — ela recusa nome novo que não deriva do que já
    existe, e aqui não há nenhum.
    """
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
    """O corpo do diálogo. Puro, para o texto ser testável sem abrir janela.

    Diz TRÊS coisas, nesta ordem, e nenhuma é decorativa:

    1. **o que ela mudou** — senão o diálogo pergunta sobre algo que ela não
       lembra ter feito;
    2. **por que não chega ao jogo aberto**, com o custo medido de tentar ao
       vivo. É a frase que impede alguém de "melhorar" isto para aplicar na
       marra;
    3. **o que continua mudando na hora** — sem isso ela conclui que precisa
       fechar o jogo para trocar a cor da luz, que é falso e é a metade da
       medição dela de 06/08.
    """
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


#: O título. Interrogativo, como o precedente HONESTIDADE-STEAM-01
#: ("Posso fechar a Steam por uns 20 segundos?") — a janela PEDE, não avisa.
TITULO: Final = "Posso fechar o jogo e abrir de novo?"

#: Os rótulos, na ordem em que entram no diálogo. O terceiro leva a classe
#: `destructive-action` (a mesma do "Desligar Hefesto") porque é o único que
#: toca no processo do jogo dela.
ROTULO_CANCELAR: Final = "Cancelar"
ROTULO_DEPOIS: Final = "Aplicar na próxima abertura"
#: RELANCAR-AGORA-01 (08/08/2026): ela leu o rótulo e apontou o que ele deveria
#: dizer — *"a última opção deveria ser aplicar agora e reiniciar jogo"*. O nome
#: antigo ("Fechar o jogo e abrir de novo") descrevia o MEIO e calava o fim: ela
#: não clica ali para fechar o jogo, clica para a mudança valer AGORA. E, na
#: versão anterior, ele nem reabria — só fechava.
ROTULO_FECHAR: Final = "Aplicar agora e reiniciar o jogo"


def toast_da_escolha(escolha: Escolha, *, jogo: str | None = None) -> str:
    """O que o rodapé diz depois. Cada saída tem a sua frase honesta."""
    if escolha == "cancelar":
        return "Nada mudou — o jogo continua como estava."
    if escolha == "na_proxima_abertura":
        alvo = jogo or "o jogo"
        return (
            f"Guardado — aplico assim que {alvo} fechar. Na próxima abertura já "
            "vale."
        )
    return "Pronto — o jogo fechou, a mudança valeu e eu pedi a abertura à Steam."


def toast_do_relancamento(
    *, fechou: bool, reabriu: bool, appid: int | None = None
) -> str:
    """O que o rodapé diz DEPOIS do relançamento — o que de fato aconteceu.

    RELANCAR-AGORA-01. A frase anterior era uma só, fixa, dizendo "o jogo fechou,
    a mudança valeu e eu pedi a abertura à Steam" — dita ANTES de qualquer uma
    das três coisas acontecer. Ela viu e disse: *"não sei nem se aplicou"*.

    Agora há uma frase por desfecho, e nenhuma promete o que não foi conferido.
    Em especial: reabrir é **pedir** à Steam. Ela leva de segundos a minutos
    (shader cache, atualização), e afirmar "abriu" seria mentir de novo — no
    mesmo lugar, na segunda tentativa.
    """
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

