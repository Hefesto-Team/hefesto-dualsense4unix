"""A camada de cada gesto: de quem é o valor que ele grava. Das dez abas.

**E O QUE ELA RECUSA NO NATIVO** (09/10/2026, DESLIGAR-O-HEFESTO-DEVOLVE-O-CONTROLE-AO-LINUX-01,
itens 4 e 5): com o Hefesto desligado o jogo é o dono do controle, e nas cinco abas que falam de
controle (Jogar, Controles, Gatilhos, Iluminação e Vibração) nenhum gesto chega ao daemon, a não ser
os que a tabela `VIVOS_NO_NATIVO` nomeia (o caminho de volta e o que é do computador). A recusa é
daqui, e o despachante a aplica no decorador `@gesto` — um gesto novo nasce recusado no Nativo sem
que o autor escreva um `if` na tela.
"""
from __future__ import annotations

from typing import Any

COMPUTADOR, CONTROLE, JOGO, ATO, JANELA = (
    "computador", "controle", "jogo", "ato", "janela")
CAMADAS = frozenset({COMPUTADOR, CONTROLE, JOGO, ATO, JANELA})

_J, _C, _T, _A, _W = JOGO, COMPUTADOR, CONTROLE, ATO, JANELA

CAMADA: dict[tuple[str, str], str] = {
    ("01-jogar.html", "cadeado"): _C,
    ("01-jogar.html", "escolher-na-fita"): _W,
    ("01-jogar.html", "hefesto"): _J,
    ("01-jogar.html", "mascara"): _J,
    ("01-jogar.html", "modo-dualsense"): _J,
    ("01-jogar.html", "modo-nativo"): _J,
    ("01-jogar.html", "modo-navegacao"): _J,
    ("01-jogar.html", "modo-point-and-click"): _J,
    ("01-jogar.html", "modo-steam"): _J,
    ("01-jogar.html", "modo-xbox"): _J,
    ("01-jogar.html", "reconectar"): _A,
    ("02-controles.html", "analogico-lado"): _J,
    ("02-controles.html", "escolher-na-fita"): _W,
    ("02-controles.html", "mic-retorno"): _W,
    ("02-controles.html", "modo-dos-controles"): _J,
    ("02-controles.html", "mudo"): _C,
    ("02-controles.html", "rota"): _C,
    ("02-controles.html", "sensor"): _C,
    ("02-controles.html", "touchpad"): _C,
    ("02-controles.html", "volume"): _C,
    ("02-controles.html", "volume-padrao"): _C,
    ("03-gatilhos.html", "criar-efeito"): _C,
    ("03-gatilhos.html", "imersao"): _J,
    ("03-gatilhos.html", "modo"): _J,
    ("03-gatilhos.html", "modo-dos-gatilhos"): _J,
    ("03-gatilhos.html", "sentir"): _A,
    ("04-iluminacao.html", "apagar"): _C,
    ("04-iluminacao.html", "brilho"): _C,
    ("04-iluminacao.html", "brilho-luzes"): _C,
    ("04-iluminacao.html", "cor"): _C,
    ("04-iluminacao.html", "criar-efeito"): _C,
    ("04-iluminacao.html", "efeito-da-luz"): _C,
    ("04-iluminacao.html", "modo-da-luz"): _C,
    ("04-iluminacao.html", "player"): _T,
    ("04-iluminacao.html", "reenviar"): _C,
    ("04-iluminacao.html", "sem-piscar"): _C,
    ("05-vibracao.html", "criar-efeito"): _C,
    ("05-vibracao.html", "forca"): _C,
    ("05-vibracao.html", "haptica"): _C,
    ("05-vibracao.html", "intensidade"): _C,
    ("05-vibracao.html", "lado"): _C,
    ("05-vibracao.html", "modo-da-vibracao"): _J,
    ("05-vibracao.html", "motor"): _C,
    ("05-vibracao.html", "parar"): _A,
    ("05-vibracao.html", "testar"): _A,
    ("05-vibracao.html", "testar-haptica"): _A,
    ("06-navegacao.html", "acao-do-gesto"): _C,
    ("06-navegacao.html", "linha-de-botao"): _C,
    ("06-navegacao.html", "na-steam"): _C,
    ("06-navegacao.html", "navegacao-tipo"): _C,
    ("06-navegacao.html", "padrao-da-aba"): _C,
    ("06-navegacao.html", "point-and-click-perfil"): _C,
    ("06-navegacao.html", "quem-navega"): _C,
    ("06-navegacao.html", "teclado"): _C,
    ("06-navegacao.html", "vel-cursor"): _C,
    ("06-navegacao.html", "vel-rolagem"): _C,
    ("07-lancadores.html", "abrir-lancador"): _A,
    ("07-lancadores.html", "adicionar-lancador"): _C,
    ("07-lancadores.html", "criar-perfil-para-um-jogo"): _J,
    ("07-lancadores.html", "detectar"): _A,
    ("07-lancadores.html", "procurar"): _A,
    ("07-lancadores.html", "procurar-o-arquivo"): _C,
    ("08-conexoes.html", "abrir-adaptador"): _W,
    ("08-conexoes.html", "aceitar-sugestao"): _A,
    ("08-conexoes.html", "adaptador-historico"): _W,
    ("08-conexoes.html", "adaptador-renomear"): _C,
    ("08-conexoes.html", "adaptador-reordenar"): _C,
    ("08-conexoes.html", "alvo"): _W,
    ("08-conexoes.html", "aparelho-menu"): _W,
    ("08-conexoes.html", "aparelho-renomear"): _T,
    ("08-conexoes.html", "aparelho-tipo"): _C,
    ("08-conexoes.html", "cancelar-mudanca"): _W,
    ("08-conexoes.html", "conectar-aparelho"): _A,
    ("08-conexoes.html", "confirmar-esquecer"): _A,
    ("08-conexoes.html", "confirmar-mudanca"): _A,
    ("08-conexoes.html", "custo-mic"): _T,
    ("08-conexoes.html", "dispensar-linha"): _A,
    ("08-conexoes.html", "dono-renomear"): _T,
    ("08-conexoes.html", "entrada-comecar"): _C,
    ("08-conexoes.html", "entrada-face"): _C,
    ("08-conexoes.html", "entrada-levantar"): _C,
    ("08-conexoes.html", "entrada-nao-alcanco"): _C,
    ("08-conexoes.html", "entrada-parar"): _C,
    ("08-conexoes.html", "entrada-pular"): _C,
    ("08-conexoes.html", "equilibrar-radio"): _A,
    ("08-conexoes.html", "escolher-adaptador"): _W,
    ("08-conexoes.html", "escolher-aparelho"): _W,
    ("08-conexoes.html", "escolher-entrada"): _C,
    ("08-conexoes.html", "escolher-na-fita"): _W,
    ("08-conexoes.html", "esquecer-aparelho"): _A,
    ("08-conexoes.html", "examinar-portas"): _C,
    ("08-conexoes.html", "ignorar"): _C,
    ("08-conexoes.html", "ligar-mesmo-assim"): _A,
    ("08-conexoes.html", "luz-nao-acende"): _C,
    ("08-conexoes.html", "mapear-comecar"): _C,
    ("08-conexoes.html", "mapear-gravar"): _C,
    ("08-conexoes.html", "mapear-parar"): _C,
    ("08-conexoes.html", "nova-entrada"): _C,
    ("08-conexoes.html", "nova-extensao"): _C,
    ("08-conexoes.html", "nova-face"): _C,
    ("08-conexoes.html", "novo-hub"): _C,
    ("08-conexoes.html", "novo-hub-cancelar"): _C,
    ("08-conexoes.html", "novo-hub-gravar"): _C,
    ("08-conexoes.html", "parear-aparelho"): _A,
    ("08-conexoes.html", "parear-de-novo"): _A,
    ("08-conexoes.html", "parear-o-pedido"): _A,
    ("08-conexoes.html", "radio-procurar"): _A,
    ("08-conexoes.html", "receptor-descobrir"): _A,
    ("08-conexoes.html", "sala-altura"): _C,
    ("08-conexoes.html", "sala-visada"): _C,
    ("08-conexoes.html", "sugerir-alocacao"): _A,
    ("08-conexoes.html", "tentar-de-novo"): _A,
    ("08-conexoes.html", "tirar-daqui"): _C,
    ("08-conexoes.html", "vizinho-o-que-e"): _C,
    ("09-sistema.html", "aplicar-aos-jogos"): _C,
    ("09-sistema.html", "atualizar"): _A,
    ("09-sistema.html", "autostart"): _C,
    ("09-sistema.html", "copiar-registro"): _A,
    ("09-sistema.html", "corrigir-modo"): _A,
    ("09-sistema.html", "corrigir-vulkan"): _C,
    ("09-sistema.html", "fixar-proton"): _C,
    ("09-sistema.html", "parar-ou-retomar"): _A,
    ("09-sistema.html", "perfil-da-mesa"): _C,
    ("09-sistema.html", "refazer-consertos"): _C,
    ("09-sistema.html", "reiniciar"): _A,
    ("09-sistema.html", "restaurar-de-fabrica"): _C,
    ("10-perfis.html", "ativar"): _J,
    ("10-perfis.html", "detectar"): _A,
    ("10-perfis.html", "duplicar"): _J,
    ("10-perfis.html", "editor.alvo"): _J,
    ("10-perfis.html", "editor.ambiente"): _J,
    ("10-perfis.html", "editor.estilo"): _J,
    ("10-perfis.html", "editor.jogo"): _J,
    ("10-perfis.html", "editor.nome"): _J,
    ("10-perfis.html", "editor.ordem"): _J,
    ("10-perfis.html", "editor.prioridade"): _J,
    ("10-perfis.html", "editor.quando"): _J,
    ("10-perfis.html", "largura-da-coluna"): _W,
    ("10-perfis.html", "novo"): _J,
    ("10-perfis.html", "ordenar"): _W,
    ("10-perfis.html", "recarregar"): _A,
    ("10-perfis.html", "remover"): _J,
    ("10-perfis.html", "selecionar"): _W,
}

#: as abas que falam de controle: no Nativo elas mostram quem está conectado e não deixam mexer
ABAS_POR_CONTROLE: frozenset[str] = frozenset({
    "01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
    "05-vibracao.html",
})

#: o que segue vivo no Nativo, dentro das cinco abas: o interruptor «Ligado | Desligado» (o caminho
#: de volta), os três botões do Desligado (a Navegação mora ali desde o todo de 15/10/2026, e é
#: com o Nativo ligado que ela se escolhe), o Modo Freestyle (é do computador) e o
#: Reconectar controles (um ato sobre o aparelho, não uma escolha do Hefesto). O gesto da camada
#: `janela` nem chega ao daemon e fica de fora da conta.
VIVOS_NO_NATIVO: frozenset[tuple[str, str]] = frozenset({
    ("01-jogar.html", "cadeado"),
    ("01-jogar.html", "hefesto"),
    ("01-jogar.html", "modo-nativo"),
    ("01-jogar.html", "modo-steam"),
    ("01-jogar.html", "modo-navegacao"),
    ("01-jogar.html", "reconectar"),
})

#: O rodapé é de TODA página (`("*", gesto)`), e na tabela não entra: o Aplicar, o
#: Salvar e o Importar mandam o perfil ao controle e recusam no Nativo, nas cinco
#: abas por controle; o Exportar só grava um arquivo e segue vivo.
RODAPE_VIVO_NO_NATIVO = frozenset({"exportar"})

#: O menu do botão direito é de TODA página (`("*", gesto)`) e vive no Nativo: Atualizar,
#: Desligar, Reiniciar e Fechar são atos do computador e da janela, não escolhas do Hefesto.
GESTOS_DO_MENU = frozenset({"menu-atualizar", "menu-desligar", "menu-reiniciar", "menu-fechar"})
FRASE_NO_NATIVO = "Em modo nativo o jogo lê este controle direto, e o Hefesto não grava aqui."
MIRA_CINZA_NO_NATIVO = (
    "Em modo nativo o jogo lê este controle direto, e o analógico virtual não grava."
)

#: a frase própria de um gesto, quando ele nomeia o que o chip deixou de fazer. O analógico
#: virtual se liga e troca de lado só na aba Controles (a Calibrar só ajusta).
FRASES_NO_NATIVO: dict[tuple[str, str], str] = {
    ("02-controles.html", "analogico-lado"): MIRA_CINZA_NO_NATIVO,
}


def no_nativo(state: Any) -> bool:
    """O modo nativo está de pé? É o `native_mode` do daemon, pelo leitor único dos modos.

    Daemon calado (`state` vazio ou ausente) NÃO é Nativo: a recusa é de quem sabe, e o gesto
    sem daemon já falha pelo próprio caminho.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import (
        MODE_NATIVE,
        mode_of_state,
    )

    return bool(state) and mode_of_state(state) == MODE_NATIVE


def recusa_no_nativo(pagina: str, gesto: str, state: Any) -> str | None:
    """A frase da recusa, ou `None` quando o gesto passa.

    Passa: fora do Nativo, fora das cinco abas, o que a tabela deixa vivo e o que é só da janela.
    O resto recusa, **inclusive o gesto que ainda não está na tabela** (não se sabe de quem é).
    O gesto com frase própria (`FRASES_NO_NATIVO`) recusa também fora das cinco abas.
    """
    if (pagina, gesto) not in FRASES_NO_NATIVO and (
            pagina not in ABAS_POR_CONTROLE or (pagina, gesto) in VIVOS_NO_NATIVO
            or gesto in RODAPE_VIVO_NO_NATIVO or gesto in GESTOS_DO_MENU):
        return None
    if CAMADA.get((pagina, gesto)) == JANELA or not no_nativo(state):
        return None
    return FRASES_NO_NATIVO.get((pagina, gesto), FRASE_NO_NATIVO)


__all__ = [
    "ABAS_POR_CONTROLE",
    "ATO",
    "CAMADA",
    "CAMADAS",
    "COMPUTADOR",
    "CONTROLE",
    "FRASES_NO_NATIVO",
    "FRASE_NO_NATIVO",
    "GESTOS_DO_MENU",
    "JANELA",
    "JOGO",
    "MIRA_CINZA_NO_NATIVO",
    "RODAPE_VIVO_NO_NATIVO",
    "VIVOS_NO_NATIVO",
    "no_nativo",
    "recusa_no_nativo",
]
