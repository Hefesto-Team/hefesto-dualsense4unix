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

PAGINAS_DA_SECAO_DOS_CONTROLES: tuple[str, ...] = ("01-jogar.html",)

_DA_SECAO_DOS_CONTROLES: dict[str, str] = {
    "analogico-lado": _J,
    "mic-retorno": _W,
    "modo-dos-controles": _J,
    "mudo": _C,
    "rota": _C,
    "sensor": _C,
    "touchpad": _C,
    "volume": _C,
    "volume-padrao": _C,
}

CAMADA: dict[tuple[str, str], str] = {
    **{(pagina, gesto): dono for pagina in PAGINAS_DA_SECAO_DOS_CONTROLES
       for gesto, dono in _DA_SECAO_DOS_CONTROLES.items()},
    ("01-jogar.html", "cadeado"): _C,
    ("01-jogar.html", "escolher-na-fita"): _W,
    ("01-jogar.html", "hefesto"): _J,
    ("01-jogar.html", "modo-dualsense"): _J,
    ("01-jogar.html", "modo-nintendo"): _J,
    ("01-jogar.html", "modo-nativo"): _J,
    ("01-jogar.html", "modo-navegacao"): _J,
    ("01-jogar.html", "modo-steam"): _J,
    ("01-jogar.html", "modo-xbox"): _J,
    ("01-jogar.html", "reconectar"): _A,
    ("03-gatilhos.html", "criar-efeito"): _C,
    ("03-gatilhos.html", "imersao"): _J,
    ("03-gatilhos.html", "intensidade-do-gatilho"): _C,
    ("03-gatilhos.html", "modo"): _J,
    ("03-gatilhos.html", "modo-dos-gatilhos"): _J,
    ("03-gatilhos.html", "sentir"): _A,
    ("04-iluminacao.html", "apagar"): _C,
    ("04-iluminacao.html", "brilho"): _C,
    ("04-iluminacao.html", "brilho-luzes"): _C,
    ("04-iluminacao.html", "cor"): _C,
    ("04-iluminacao.html", "efeito-da-luz"): _C,
    ("04-iluminacao.html", "modo-da-luz"): _C,
    ("04-iluminacao.html", "player"): _T,
    ("05-vibracao.html", "efeito-haptico"): _C,
    ("05-vibracao.html", "efeito-imersao"): _C,
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
    ("06-navegacao.html", "novo-gesto"): _C,
    ("06-navegacao.html", "padrao-da-aba"): _C,
    ("06-navegacao.html", "permitir-navegacao"): _C,
    ("06-navegacao.html", "point-and-click-perfil"): _C,
    ("06-navegacao.html", "remover-gesto"): _C,
    ("06-navegacao.html", "teclado"): _C,
    ("06-navegacao.html", "vel-cursor"): _C,
    ("06-navegacao.html", "vel-rolagem"): _C,
    ("07-lancadores.html", "aba-da-modificacao"): _W,
    ("07-lancadores.html", "acao-da-modificacao"): _A,
    ("07-lancadores.html", "adicionar-lancador"): _C,
    ("07-lancadores.html", "cancelar-modificacao"): _W,
    ("07-lancadores.html", "configurar-lancador"): _W,
    ("07-lancadores.html", "configurar-modificacao"): _W,
    ("07-lancadores.html", "criar-perfil-do-jogo"): _J,
    ("07-lancadores.html", "criar-perfil-para-um-jogo"): _J,
    ("07-lancadores.html", "editar-o-css-da-modificacao"): _C,
    ("07-lancadores.html", "escolher-arquivo-da-modificacao"): _C,
    ("07-lancadores.html", "escolher-o-lancador"): _W,
    ("07-lancadores.html", "esquecer-a-forma-do-livre"): _W,
    ("07-lancadores.html", "gravar-o-livre-da-modificacao"): _W,
    ("07-lancadores.html", "guardar-lancador"): _C,
    ("07-lancadores.html", "guardar-opcao-da-modificacao"): _W,
    ("07-lancadores.html", "identificar-lancador"): _A,
    ("07-lancadores.html", "instalar-modificacao"): _C,
    ("07-lancadores.html", "ligar-modificacao"): _C,
    ("07-lancadores.html", "mais-da-modificacao"): _C,
    ("07-lancadores.html", "modo-do-livre-da-modificacao"): _W,
    ("07-lancadores.html", "parar-tudo-da-modificacao"): _A,
    ("07-lancadores.html", "procurar-o-arquivo"): _C,
    ("07-lancadores.html", "resolver-impedimento"): _C,
    ("07-lancadores.html", "resolver-todos-os-impedimentos"): _C,
    ("07-lancadores.html", "soltar-o-livre-da-modificacao"): _A,
    ("07-lancadores.html", "ver-impedimentos"): _A,
    ("08-conexoes.html", "abrir-adaptador"): _W,
    ("08-conexoes.html", "aceitar-sugestao"): _A,
    ("08-conexoes.html", "acionador-botao"): _W,
    ("08-conexoes.html", "acionador-guardar"): _C,
    ("08-conexoes.html", "acionador-nova-tecla"): _W,
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
    ("08-conexoes.html", "usar-como-botoes"): _W,
    ("08-conexoes.html", "vizinho-o-que-e"): _C,
    ("09-sistema.html", "atualizar"): _A,
    ("09-sistema.html", "autostart"): _C,
    ("09-sistema.html", "bandeja"): _C,
    ("09-sistema.html", "copiar-registro"): _A,
    ("09-sistema.html", "corrigir-modo"): _A,
    ("09-sistema.html", "correcoes-automaticas"): _C,
    ("09-sistema.html", "parar-ou-retomar"): _A,
    ("09-sistema.html", "perfil-da-mesa"): _C,
    ("09-sistema.html", "reiniciar"): _A,
    ("09-sistema.html", "restaurar-de-fabrica"): _C,
    ("09-sistema.html", "salvar-registro"): _A,
    ("09-sistema.html", "tamanho-da-interface"): _W,
    ("10-perfis.html", "ativar"): _J,
    ("10-perfis.html", "duplicar"): _J,
    ("10-perfis.html", "editor.alvo"): _J,
    ("10-perfis.html", "editor.estilo"): _J,
    ("10-perfis.html", "editor.jogo"): _J,
    ("10-perfis.html", "perfis.renomear"): _J,
    ("10-perfis.html", "editor.ordem"): _J,
    ("10-perfis.html", "editor.quando"): _J,
    ("10-perfis.html", "largura-da-coluna"): _W,
    ("10-perfis.html", "novo"): _J,
    ("10-perfis.html", "ordenar"): _W,
    ("10-perfis.html", "recarregar"): _A,
    ("10-perfis.html", "remover"): _J,
    ("10-perfis.html", "selecionar"): _W,
}

ABAS_POR_CONTROLE: frozenset[str] = frozenset({
    "01-jogar.html", "03-gatilhos.html", "04-iluminacao.html", "05-vibracao.html",
})

VIVOS_NO_NATIVO: frozenset[tuple[str, str]] = frozenset({
    ("01-jogar.html", "cadeado"),
    ("01-jogar.html", "hefesto"),
    ("01-jogar.html", "modo-nativo"),
    ("01-jogar.html", "modo-steam"),
    ("01-jogar.html", "modo-navegacao"),
    ("01-jogar.html", "reconectar"),
})

RODAPE_VIVO_NO_NATIVO = frozenset({"exportar"})

GESTOS_DO_MENU = frozenset({"menu-atualizar", "menu-desligar", "menu-reiniciar", "menu-reconectar",
                            "menu-fechar"})

GESTOS_DA_MOLDURA = frozenset({"travar-navegacao"})
FRASE_NO_NATIVO = "Em modo nativo o jogo lê este controle direto, e o Hefesto não grava aqui."
MIRA_CINZA_NO_NATIVO = (
    "Em modo nativo o jogo lê este controle direto, e o analógico virtual não grava."
)

FRASES_NO_NATIVO: dict[tuple[str, str], str] = {
    (pagina, "analogico-lado"): MIRA_CINZA_NO_NATIVO for pagina in PAGINAS_DA_SECAO_DOS_CONTROLES
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
            or gesto in RODAPE_VIVO_NO_NATIVO or gesto in GESTOS_DO_MENU
            or gesto in GESTOS_DA_MOLDURA):
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
    "GESTOS_DA_MOLDURA",
    "GESTOS_DO_MENU",
    "JANELA",
    "JOGO",
    "MIRA_CINZA_NO_NATIVO",
    "PAGINAS_DA_SECAO_DOS_CONTROLES",
    "RODAPE_VIVO_NO_NATIVO",
    "VIVOS_NO_NATIVO",
    "no_nativo",
    "recusa_no_nativo",
]
