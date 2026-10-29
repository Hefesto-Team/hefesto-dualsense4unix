#!/usr/bin/env python3
"""O pacote da aba `01` Jogar — a que MAIS escreve, e a única com gesto ligado.

Tem dono no `state_full` (medido em 01/09/2026): `active_profile` (perfil em vigor), `controllers[]`
(a mesa: quantos, por qual transporte), `battery_pct`, `player`, `vpad_backend` (a máscara que o
jogo vê) e `emulation_suppressed` (o Hefesto está fora do meio?). O MODO (o chip aceso da fileira)
não sai do state direto: quem o lê é `mode_transition.mode_of_state`, o ponto único de leitura do
modo vivo, que devolve TRÊS valores, nunca um quarto; o piloto já o usa para acender o interruptor.
"""
from __future__ import annotations

import dataclasses
import html
import sys
import threading
import time
from typing import Any, NamedTuple

from . import TRAVESSAO, Contexto, confirmacao, fios, jogador_de, registrar

CADEADO_CEGO = "cadeado-cego"

DA_PAGINA: tuple[str, ...] = (
    "abas-externos",
    "cadeado",
    "externos",
    CADEADO_CEGO,
    "hef-posicao",
    "modo-aceso",
    "steam-input-aceso",
)


ORDEM_DA_GRAVIDADE: tuple[str, ...] = (
    "PAUSA", "ERRO", "GAMEPAD", "MODO", "PONTE", "JOGO", "CONTROLE", "RÁDIO",
    "PERFIL",
)

SELO_DA_PONTE = "PONTE"

SELO_DA_CURA = "CONTROLE"

POSICAO_COM_O_SERVICO_PARADO = "desligado"


def lugares_da_mesa() -> int:
    """Quantos cartões a página publica. Lido de `monta.MESA`, nunca digitado."""
    return len(_monta().MESA)


ESPERA_DICA = "O número acende quando o jogo receber o controle"

CADEADO_ROTULO = "Modo Freestyle"
CADEADO_DICA = "O perfil ativo vale em qualquer jogo"

CADEADO_RECUSA = "O Hefesto está desligado: a trava não foi aplicada."


CADEADO_LIGADO = "LIGADO"
CADEADO_DESLIGADO = "DESLIGADO"


def _cadeado(state: dict[str, Any]) -> str:
    """``LIGADO`` · ``DESLIGADO`` · travessão — as três respostas da trava."""
    lido = state.get("freestyle_ligado")
    if lido is True:
        return CADEADO_LIGADO
    if lido is False:
        return CADEADO_DESLIGADO
    return TRAVESSAO


MARCA_DO_PRIMARIO = "primário"

PRIMARIO_DICA = "Este controle navega o computador"


def _e_o_primario(c: dict[str, Any]) -> str:
    """``"1"`` no cartão do primário, ``""`` nos outros — na língua do `classe`.

    Passo 3 da JOGAR-O-QUE-FALTA-01 (06/09/2026), linha 18 do CSV: `is_primary` não era lido em
    `interface/pacotes/`. Medido em 02/09: o controle BT com `player 1`, `player_slot 1`,
    `is_primary TRUE`; o USB com `player None`, `player_slot 2`, `is_primary false`.

    **Só o `True` literal acende** (disciplina do `_cadeado` e do `wrapper_used`): chave ausente
    (daemon antigo, ou controle que o co-op ainda não classificou) é *não sei*, e a resposta a *não
    sei* nesta casa é não mostrar; `bool` é o único tipo que passa, e ``1`` de payload malformado
    não acende. **Não é o alvo de edição da fita**: a classe `.cartao.alvo` responde a outra
    pergunta (qual controle os ajustes das outras abas tocam), é escrita pelo piloto
    (`carga["alvo"]`) e pode ser outro controle: o primário é fato do daemon e o alvo é escolha do
    usuário, dois endereços.
    """
    return "1" if c.get("is_primary") is True else ""


def _jogador_esperando(c: dict[str, Any]) -> str:
    """``"1"`` enquanto o jogo não recebeu este controle, ``""`` quando recebeu.

    Decisão [02] desta aba (*"'Player N', esmaecido enquanto espera."*). Medido em 02/09/2026: o
    controle BT com `player 1`, `player_slot 1` e o USB com `player None`, `player_slot 2`, cujo
    cartão dizia "Player 2". O `None` não é do transporte (`jogador_de` carrega a medição): quem
    volta ``None`` é quem o co-op ainda não promoveu a jogador
    (`daemon/subsystems/coop.CoopManager.player_indexes`).

    As duas chaves são lidas na ordem do cartão, o que impede a função de discordar do número que
    esmaece: se `jogador_de` não achou número, o cartão mostra travessão e não há jogador a
    ressalvar (esmaecer travessão prometeria que ALGUÉM espera). O ``player`` é lido CRU:
    `jogador_de` responde *"que número o cartão mostra"* e cai no `player_slot` primeiro; aqui a
    pergunta é *"o JOGO já viu este controle?"*, que só a chave `player` responde.

    **A Conexão Nativa parou de esmaecer tudo (06/09/2026, COOP-NA-CONEXAO-NATIVA-01, Caminho B)**:
    `coop.resolve_player_numbers` devolvia ``[None] * N`` naquele modo e a função esmaecia a mesa
    inteira para sempre, prometendo promoção que nunca viria (não há grab nem vpad a esperar). Agora
    o número vem do ``identity_registry``; nada mudou aqui, a função já estava certa e quem mentia
    era a fonte.
    """
    if jogador_de(c) is None:
        return ""
    return "" if c.get("player") is not None else "1"


def mascaras_montaveis() -> frozenset[str]:
    """Os rótulos de máscara que o produto SABE MONTAR — para o desenho perguntar."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascaras_validas
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    return frozenset(
        NOME_DA_MASCARA[f] for f in mascaras_validas() if f in NOME_DA_MASCARA)


@registrar("01-jogar.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Os valores da aba Jogar, com os NOMES que a página tem."""
    _relatar_a_pendencia(_faixa_do_pendente(ctx.state)[0])
    tela = _a_fileira_com_a_mesa(_estado_da_tela(ctx.state), ctx.mesa)

    fora: dict[str, Any] = {
        "cadeado": _cadeado(ctx.state),
        CADEADO_CEGO: _cadeado_cego(ctx.state),
        "cartoes": {},
        "externos": _html_dos_externos(ctx),
        "abas-externos": _abas_dos_externos(ctx),
        **tela,
        "blocos": _o_rotulo_do_chip(ctx.state),
    }
    fora["cobertura"] = {"pintados": len(DA_PAGINA), "sem_dono": 0}
    from . import a02_controles

    if a02_controles.a_secao_esta_na_pagina(PAGINA):
        _com_a_secao_dos_controles(fora, a02_controles.pacote(ctx))
    return fora


def _com_a_secao_dos_controles(fora: dict[str, Any], secao: dict[str, Any]) -> None:
    """A seção Controles na Jogar, pintada pelo pacote da 02: o card dela vale sobre o cartão."""
    from . import LUGAR_VAZIO

    cartoes = fora["cartoes"]
    for uniq, campos in (secao.get("cards") or {}).items():
        cartoes[uniq] = {**cartoes.get(uniq, {}), **campos}
    for chave, valor in (secao.get("mesa") or {}).items():
        fora.setdefault(chave, valor)
    fora[LUGAR_VAZIO] = {**(secao.get(LUGAR_VAZIO) or {}), **(fora.get(LUGAR_VAZIO) or {})}
    fora["cobertura"]["pintados"] += int((secao.get("cobertura") or {}).get("pintados") or 0)


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda."""
    if not slug:
        return ""
    try:
        import monta

        return str(monta.cor_de_css(slug))
    except BaseException:
        return ""


def _monta() -> Any:
    """O `monta`, importado tarde — o `pacotes/__init__` põe `interface/` no path."""
    import monta

    return monta


def _colorway_do_desenho(slug: str) -> str:
    """O slug que o `data-colorway` do SVG recebe, ou `""` quando não dá.

    Não é segunda tabela: é a pergunta de `_cor_do_plastico` ao mesmo dono (`monta.cor_da_zona`, que
    lê a folha gerada de `docs/data/cores-do-dualsense.csv`), devolvendo o SLUG com que o desenho se
    pinta e não o HEX da borda. A amarração é o ponto: slug que o SVG não conhece (modelo novo no
    CSV, colorway que o gerador não emitiu) casaria regra nenhuma e deixaria o desenho no cinza cru
    (`rgb(58, 63, 75)`).

    **A pergunta mudou em 03/09/2026**: valia `slug if _cor_do_plastico(slug) else ""` (*"sem cor,
    sem desenho colorido"*) enquanto **sem hex** quisesse dizer **a folha não conhece**. Não quer:
    OITO dos vinte e oito modelos pintam com `<pattern>` ou gradiente, a folha os conhece e o SVG os
    veste; só a PELE não pode receber `url(…)`. Calá-los com a pele deixaria o controle SEM
    IDENTIDADE na tela, quando o aparelho tem. A pergunta certa é `monta.o_desenho_conhece`.
    """
    return slug if slug and _monta().o_desenho_conhece(slug) else ""


def _do_exame() -> list[dict[str, Any]]:
    """Os achados do exame da mesa, ou lista vazia. Nunca levanta.

    O selo é do produto. Medido em 03/09/2026 esta função montava ``{"selo": "RÁDIO" if i["grave"]
    else "AVISO", **i}``, e o ``**i`` DEPOIS sobrescreve a chave: `a08_conexoes._linha` já emite
    ``selo`` de `interface.conexoes.SELO_DO_ESTADO`, dono da palavra, e as duas digitadas aqui nunca
    chegaram a uma tela. Chegava o selo do exame, de quatro estados incluindo o **CERTO**
    (fotografado na 01 em 02/09: o selo `CERTO` sob o cabeçalho laranja **Atenção**, "Economia de
    energia desligada", boa notícia vestida de alarme). Repor as palavras devolveria a divergência
    no primeiro estado novo; sai o que o exame diz, e quem escolhe o que vai para **Atenção** é
    :func:`_avisos`, que só leva o ``grave``.

    O `except` largo continua, e o preço está no dono (`a08_conexoes._exame`): um `AttributeError`
    já virou lista vazia e apagou meia coluna sem erro. O silêncio acabou: :func:`_avisos`
    transforma a falha em aviso de selo ``ERRO``, a política de `painel.avisos_do_estado`.
    """
    from . import a08_conexoes

    return list(a08_conexoes._exame())


def _avisos(ctx: Contexto) -> list[dict[str, str]]:
    """As dez fontes de aviso do produto: ``[{"selo", "texto", "fonte"}, …]``.

    **Perdeu a tela em 07/09/2026, não as fontes.** Ordem de produto: a seção Atenção sai da aba
    Jogar e fica só o Reconectar controles. Os quatro endereços (`atencao-conta`, `aviso-selo`,
    `aviso-texto`, `aviso-vivo`) saíram de :data:`DA_PAGINA` (endereço sem elemento é órfão). Das
    dez fontes **só a 5** (o exame, `a08_conexoes._exame`) tem segunda casa publicada, a aba
    Conexões; as outras nove chegavam à tela SÓ por aqui (na medição, a coluna tinha UMA linha viva,
    `home_actions.texto_do_cadeado_cego`). **Foram para a aba 09, Sistema (28/09/2026,
    A-TELA-PERGUNTA-AO-DONO-01)**, cujo trabalho é a máquina se explicar: `a09_sistema.pacote`
    pergunta a :func:`coluna_de_atencao` e acrescenta as linhas ao exame, com o selo de aviso do
    exame. Vão as SEM outra casa (:func:`_avisos_sem_outra_casa`); as já mostradas em outro lugar
    ficam no canal e fora da 09 (:func:`_avisos_com_outra_casa`).

    **Nada se escreve aqui**: as fontes existiam fora do arquivo e faltava o produto novo CHAMÁ-LAS.
    Medido em 03/09/2026 quem consumia `painel.AVISOS_DA_TELA` era `jogar_vivo.py`
    (BANCADA), e a aba publicada mostrava no lugar o Check-up da Conexões, dois conjuntos DISJUNTOS.

    O que entra, em ordem:

    1. **as seis de `painel.AVISOS_DA_TELA`**: pausa, vpad degradado, rádio frágil, jogo sem
      wrapper, cadeado da troca automática e detector cego; funções puras de `home_actions`, e
      `painel.avisos_do_estado` trata a que levanta (selo ``ERRO``);
    2. **o opt-out antigo** (`home_actions.aviso_de_opt_out_antigo`): fora de `AVISOS_DA_TELA`
      porque pede dois argumentos que só a tela sabe (escolha de disco DESLIGADA,
      `painel.modo_lembrado()` lendo o ``gamepad_disabled.flag``; e quantos controles há,
      `ctx.conectados`); é a pergunta de 31/08 (*"não sei se segue desativado"*);
    3. **a ponte com o jogo** (:func:`_aviso_da_ponte`), só quando é má notícia; fica no canal e
      fora da 09 (:func:`_avisos_com_outra_casa`); 3-bis. **a divergência de máscara**
      (:func:`_aviso_da_divergencia_de_mascara`), o ALARME do daemon desde a MASCARA-01; mora aqui e
      não em `AVISOS_DA_TELA` porque volta em markup do Pango, como a ponte (portão);
    4. **a cura do travamento do USB** (:func:`_aviso_da_cura_do_travamento`), ONDA5-01-01,
      06/09/2026; lê o disco e não o `state`;
    5. **os achados GRAVES do exame** (`a08_conexoes._exame`); os ``certo`` ficam de fora, a coluna
      chama-se Atenção.

    O que fica escrito é a LISTA, que se conta sozinha: o número desta docstring errou três vezes
    (06/09/2026); quem acrescentar uma fonte acrescenta um item, não um número. O selo do opt-out é
    ``GAMEPAD``, o mesmo que `AVISOS_DA_TELA` dá ao vpad degradado (mesmo assunto, o gamepad virtual
    que o jogo vê); selo novo poria palavra de tela num arquivo que não é dono de nenhuma.
    """
    fora: list[dict[str, str]] = _avisos_sem_outra_casa(ctx)
    fora += _avisos_com_outra_casa(ctx)
    return fora


FONTES_DO_PAINEL_COM_OUTRA_CASA: dict[str, str] = {
    "home_actions.texto_da_pausa":
        "a linha «Serviço» do Status da 09 diz PAUSADO",
    "home_actions.texto_do_cadeado_cego":
        "a linha «Troca de perfil ao abrir o jogo» do Status da 09 diz SEM VER",
    "home_actions.autoswitch_lock_text":
        "a pílula «Modo Freestyle» da Jogar acende",
}


def _do_painel(ctx: Contexto, com_outra_casa: bool) -> list[dict[str, str]]:
    """As fontes de `painel.AVISOS_DA_TELA`, de um lado ou do outro da 09.

    Uma leitura do dono (`painel.avisos_do_estado`), cortada pelo nome da fonte
    em :data:`FONTES_DO_PAINEL_COM_OUTRA_CASA`. A linha de ``ERRO`` de uma fonte
    que levantou vai para o mesmo lado da fonte.
    """
    painel = _painel()
    return [a for a in painel.avisos_do_estado(ctx.state)
            if (a.get("fonte") in FONTES_DO_PAINEL_COM_OUTRA_CASA) is com_outra_casa]


def _avisos_sem_outra_casa(ctx: Contexto) -> list[dict[str, str]]:
    """As fontes que SÓ a coluna Atenção publicava — as que vão à aba Sistema.

    Separadas das outras em 28/09/2026 (A-TELA-PERGUNTA-AO-DONO-01) para a lista do exame da 09 as
    receber (:func:`coluna_de_atencao`). As que ficam de fora já têm casa e levá-las poria a mesma
    notícia duas vezes: o serviço calado (Status da 09), a ponte com o jogo (fileira da Jogar), a
    cura do travamento do USB (o exame da 09 a lê pelo mesmo dono, `storm_doctor.check_snd_quirk`,
    dentro do `storm_report`), os achados do exame dos controles (aba Conexões) e as três do
    `painel` de :data:`FONTES_DO_PAINEL_COM_OUTRA_CASA`.
    """
    painel = _painel()
    fora: list[dict[str, str]] = _do_painel(ctx, com_outra_casa=False)

    try:
        from hefesto_dualsense4unix.app.actions import home_actions

        texto = home_actions.aviso_de_opt_out_antigo(
            ctx.state,
            opt_out=painel.modo_lembrado().ligado is False,
            conectados=len(ctx.conectados),
        )
        if texto:
            fora.append({"selo": "GAMEPAD", "texto": str(texto),
                         "fonte": "home_actions.aviso_de_opt_out_antigo"})
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"o opt-out antigo não respondeu ({type(erro).__name__}).",
                     "fonte": "home_actions.aviso_de_opt_out_antigo"})

    try:
        divergencia = _aviso_da_divergencia_de_mascara(ctx.state)
        if divergencia:
            fora.append(divergencia)
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"a divergência de máscara não respondeu "
                              f"({type(erro).__name__}).",
                     "fonte": "home_actions.mascara_divergente_do_daemon"})

    return fora


def _avisos_com_outra_casa(ctx: Contexto) -> list[dict[str, str]]:
    """As fontes do canal que a tela já mostra em outro lugar."""
    fora: list[dict[str, str]] = _do_painel(ctx, com_outra_casa=True)
    ponte = _aviso_da_ponte(ctx.state)
    if ponte:
        fora.append(ponte)
    try:
        cura = _aviso_da_cura_do_travamento()
        if cura:
            fora.append(cura)
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"a cura do travamento não respondeu ({type(erro).__name__}).",
                     "fonte": "storm_doctor.check_snd_quirk"})

    try:
        fora += [{"selo": str(i["selo"]), "texto": str(i["titulo"]),
                  "fonte": "a08_conexoes._exame"}
                 for i in _do_exame() if i.get("grave")]
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"o exame dos controles não respondeu ({type(erro).__name__}).",
                     "fonte": "a08_conexoes._exame"})
    return fora


def _aviso_da_ponte(state: dict[str, Any]) -> dict[str, str] | None:
    """A linha *"Ponte com o jogo"*, e só quando ela é MÁ NOTÍCIA.

    Órfã da D-10 (*"Todas na coluna Atenção"*): das três frases da decisão, **duas já estavam na
    coluna** desde 03/09 (a PAUSA é `AVISOS_DA_TELA[0]`; o cadeado são as duas últimas,
    `autoswitch_lock_text` e `texto_do_cadeado_cego`) e a ponte era a única sem canal.

    **Quem decide se é má notícia é o produto, pela cor dele.** `texto_da_ponte` devolve markup do
    Pango e pinta o veredito: `_COR_OK` nos dois desfechos bons ("direto (Sony)", "pelo Hefesto"),
    `_COR_AVISO` nos dois ruins ("de pé, e vazia", "nenhuma") e cor NENHUMA no "não sei" de daemon
    desligado. Ler a cor é ler a escada de gravidade da função; reescrever as quatro perguntas seria
    a segunda cópia da regra. A boa notícia e o "não sei" ficam de fora (a coluna chama-se Atenção;
    sem daemon não se afirma nada, como em `autoswitch_lock_text`).

    O markup não chega à tela: `interface.sistema.sem_markup` o tira (a `a09_sistema` já o usa),
    senão o `<span foreground="#ffb86c">` iria LITERAL ao `textContent`. A constante privada é de
    propósito, e a guarda também: `_COR_AVISO` é o único lugar em que a função declara *"isto é
    ruim"*; se sumir, a régua **cala** em vez de alarmar (um `"" in frase` casaria com tudo e
    encheria a coluna de boa notícia vestida de alerta, o defeito que `_do_exame` já custou).
    """
    if not state:
        return None
    from hefesto_dualsense4unix.app.actions import home_actions

    ruim = str(getattr(home_actions, "_COR_AVISO", "") or "")
    if not ruim:
        return None
    frase = home_actions.texto_da_ponte(state)
    if ruim not in frase:
        return None
    texto = _sem_markup(frase)
    if texto.startswith(home_actions.PONTE_PREFIXO):
        texto = texto[len(home_actions.PONTE_PREFIXO):]
    return {"selo": SELO_DA_PONTE, "texto": texto,
            "fonte": "home_actions.texto_da_ponte"}


def _sem_markup(frase: str) -> str:
    """O texto de uma frase do produto, sem o markup do Pango. UMA porta só."""
    from hefesto_dualsense4unix.interface.sistema import sem_markup

    return sem_markup(frase)


def _aviso_da_divergencia_de_mascara(state: dict[str, Any]) -> dict[str, str] | None:
    """A escolha de máscara que não chegou ao aparelho; ``None`` quando chegou."""
    if not state:
        return None
    from hefesto_dualsense4unix.app.actions import home_actions

    alarme = home_actions.mascara_divergente_do_daemon(state)
    if alarme is None:
        return None
    frase = home_actions.texto_da_divergencia(
        alarme.get("mascara_perfil"),
        alarme.get("mascara_viva"),
        jogo_aberto=home_actions.jogo_com_autoridade(state),
        fonte=home_actions.FONTE_PERFIL,
        perfil=alarme.get("profile"),
    )
    if not frase:
        return None
    return {"selo": "GAMEPAD", "texto": _sem_markup(frase),
            "fonte": "home_actions.mascara_divergente_do_daemon"}


def _aviso_da_cura_do_travamento() -> dict[str, str] | None:
    """A linha da **cura do travamento do USB**, e só quando ela pede ação.

    Palavra do usuário (05/09/2026) sobre o aviso do modo nativo: *"Não me lembro disso acontecer. E
    não deveria. Mas caso ocorra na coluna atenção"*; a medição confirma. O Hefesto **conserta** a
    causa desde a SPRINT-GAME-RUMBLE-01 (o quirk `054c:0ce6:…ignore_ctl_error` do `snd_usb_audio`,
    que torna o probe do mixer UAC tolerante e para de martelar o EP0) e o `install.sh` o instala;
    na máquina do usuário a cura está de pé (``[ OK ]``, 06/09/2026). A linha aparece no dia em que
    ela cai (kernel novo, `/etc/modprobe.d` limpo, instalação sem replug).

    **Fecha o defeito de duas telas discordando sobre a mesma máquina**: `check_snd_quirk` já
    chegava à aba **Sistema** (`storm_report`, em `a09_sistema._achados`) e a **Jogar**, aberta
    enquanto o jogo roda, dizia *"nenhum aviso"*. Nada se digita aqui: a frase vem de
    `storm_doctor.check_snd_quirk`, com o ``O que fazer:`` do ``PREFIXO_DA_CURA`` e o gesto desta
    instalação (`gesto_de_atualizar`); reescrevê-la seria a segunda cópia de palavra com dono (o
    defeito do "RÁDIO"/"AVISO" de `_do_exame`). **Só ``check_snd_quirk``, nunca ``storm_report``**:
    o pacote da 09 roda seis exames e cinco não têm a ver com esta coluna.

    Entram ``[WARN]`` (a cura em lugar nenhum) e ``[INFO]`` (agendada, esperando o replug), trabalho
    pendente; ``[ OK ]`` fica de fora (boa notícia não é Atenção, como os ``certo`` do exame e os
    desfechos bons de :func:`_aviso_da_ponte`; foi um ``CERTO`` sob o cabeçalho laranja, fotografado
    em 02/09, que ensinou).

    **Custo por tique, medido antes de ligar** (06/09/2026, máquina do usuário, `.venv` da raiz):
    **0,030 ms** no caminho ``[ OK ]`` (dois ``open``, de
    `/sys/module/snd_usb_audio/parameters/quirk_flags` e
    `/etc/modprobe.d/hefesto-dualsense-storm.conf`), **0,075 ms** no ``[WARN]`` (chama
    `gesto_de_atualizar`) e **0,79 ms** na PRIMEIRA chamada do ``[WARN]`` por processo (o
    `main.glade` lido para o rótulo do botão, em `_ROTULOS_EM_CACHE`). O tique é de 100 ms
    (`interface/hefesto_vivo.TIQUE_MS`): pior caso **0,8%**, normal **0,03%**, **sem cache** de
    propósito, pois o que estes arquivos dizem muda no replug e no boot e a coluna seguiria
    alarmando depois do que a frase mandou. A MORDIDA está em
    `tests/unit/test_a01_a_coluna_atencao_acende_o_mais_grave.py`.
    """
    from hefesto_dualsense4unix.integrations import storm_doctor

    selo, frase = storm_doctor.check_snd_quirk()
    if selo == storm_doctor.OK:
        return None
    return {"selo": SELO_DA_CURA, "texto": str(frase),
            "fonte": "storm_doctor.check_snd_quirk"}


def _em_ordem(avisos: list[dict[str, str]]) -> list[dict[str, str]]:
    """Os avisos com o mais grave em cima — a metade da D-09 que sobreviveu."""
    posto = {selo: i for i, selo in enumerate(ORDEM_DA_GRAVIDADE)}
    fim = len(ORDEM_DA_GRAVIDADE)
    return sorted(avisos, key=lambda a: posto.get(str(a.get("selo") or ""), fim))


def coluna_de_atencao(ctx: Contexto) -> list[dict[str, str]]:
    """Os avisos que SÓ a coluna Atenção publicava, o mais grave em cima."""
    return _em_ordem(_avisos_sem_outra_casa(ctx))


def _html_dos_externos(ctx: Contexto) -> str:
    """Uma linha por externo (o Hefesto VÊ e NÃO adota) na seção Controles; sem nenhum, o marcador.

    D-2810-O-EXTERNO-ENTRA-NA-SECAO-CONTROLES-DA-JOGAR: a linha vem depois dos assentos, na forma
    da linha fechada (`aba01.py`, `.quadro.estica .ext-cartao`). Nenhum texto se escreve aqui: o
    título, o transporte e o aviso do `hid-nintendo` são da janela antiga
    (``_format_external_title``, ``_format_external_subtitle``, ``nintendo_bt_warning``), e a cor
    e os botões declarados são de ``a08_conexoes.marcas_do_externo``. Não leva `.ctl`, `.cartao`
    nem `data-controle`: essas marcas são dos assentos.
    """
    if not ctx.externos:
        return str(_monta().NADA_A_DIZER)
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        nintendo_bt_warning,
    )
    from hefesto_dualsense4unix.app.actions.home_actions import (
        _format_external_subtitle,
        _format_external_title,
        externos_na_mesa,
    )

    from . import a08_conexoes

    def _e(x: object) -> str:
        return html.escape(str(x), quote=True)

    fora = []
    for entrada in externos_na_mesa(None, ctx.externos):
        aviso = nintendo_bt_warning(entrada)
        linha_do_aviso = (f'<div class="ext-aviso">{_e(aviso)}</div>'
                          if aviso else "")
        da_borda, botoes = a08_conexoes.marcas_do_externo(entrada, "div")
        fora.append(
            f'<div class="ext-cartao"{da_borda}>'
            f'<input class="radio-mesa" type="radio" name="mesa" id="c-{_id_do_externo(entrada)}">'
            f'<div class="ext-nome">{_e(_format_external_title(entrada))}</div>'
            f'<div class="ext-via">{_e(_format_external_subtitle(entrada))}</div>'
            f'{botoes}{linha_do_aviso}</div>')
    return "".join(fora) or str(_monta().NADA_A_DIZER)


def _id_do_externo(entrada: dict[str, Any]) -> str:
    """O endereço da aba e do cartão do externo: `x` e o número do jogador, como o `pN`."""
    from hefesto_dualsense4unix.app.actions.external_controllers import slot_label, slot_of

    return f"x{slot_label(slot_of(entrada, 0, 0))}"


def _abas_dos_externos(ctx: Contexto) -> str:
    """Uma aba por externo na fileira das abas da Jogar, com o número, a marca e o glifo da via.

    O externo é um controle conectado como o DualSense, e ganha a aba dele ao lado das dos
    assentos (D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR). A borda é a cor que o usuário declarou,
    pelo mesmo `tom_para_a_borda` do assento, e o neutro sem declaração. O clique só abre o
    cartão: o Hefesto não escreve no externo, e por isso a aba não leva gesto nem `data-controle`.
    """
    if not ctx.externos:
        return str(_monta().NADA_A_DIZER)
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        brand_of,
        slot_label,
        slot_of,
    )
    from hefesto_dualsense4unix.app.actions.home_actions import (
        externos_na_mesa,
        palavra_do_transporte,
    )
    from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_para_a_borda

    from . import a02_controles, a08_conexoes

    def _e(x: object) -> str:
        return html.escape(str(x), quote=True)

    fora = []
    for entrada in externos_na_mesa(None, ctx.externos):
        numero = slot_label(slot_of(entrada, 0, 0))
        marca = brand_of(entrada)
        via = palavra_do_transporte(entrada.get("bus"))
        tom = tom_para_a_borda(a08_conexoes.a_declaracao_do_externo(entrada)["cor"])
        borda = tom or a02_controles.BORDA_SEM_COR
        tinta = a02_controles.tinta_sobre(tom) if tom else "var(--fg)"
        fora.append(
            f'<label class="aba-ctl aba-ext" for="c-{_id_do_externo(entrada)}" role="tab" '
            f'data-dica="{_e(f"{marca} · {via}")}" '
            f'style="order:{_e(numero)};--plastico:{borda};--tinta:{tinta}">'
            f'<span class="n-jog">{_e(numero)}</span>'
            f'<span class="aba-nome">{_e(marca)}</span>'
            f'<span class="via-g" data-via="{a02_controles.VIAS_DA_ABA.get(via, "")}"></span>'
            f'</label>')
    return "".join(fora) or str(_monta().NADA_A_DIZER)


def _cadeado_cego(state: dict[str, Any]) -> str:
    """A ressalva do cadeado: o detector está cego? — marcador quando não.

    Existe desde 07/09/2026: a caixa *"Não trocar de perfil sozinho ao abrir um jogo"* governa a
    troca automática POR JANELA, que com o detector cego **não acontece de jeito nenhum**, e a caixa
    passaria a oferecer congelar algo já parado. Quem dizia isso era a coluna **Atenção**, que saiu
    da aba por ordem de produto (a frase era a única linha acesa dela na medição); sem ela a tela
    oferece controle sem dizer que não tem sobre o que agir.

    A fonte é a da janela antiga, `home_actions.texto_do_cadeado_cego`, palavra por palavra (texto
    de tela é decisão de produto; o que ela já leu não, como `CADEADO_ROTULO` e `CADEADO_DICA`). A
    ausência da chave conta como "não sei", e o dono garante: daemon mais velho não publica
    `window_detect_seeing` e a função devolve `""` em vez de acender aviso sobre detector que
    ninguém leu. O marcador no lugar do vazio é `monta.NADA_A_DIZER` (razão paga pelos externos em
    06/09): `escrever()` troca vazio por `—`, que numa linha de ressalva vira travessão solto;
    `monta.ressalva` já nasce com o marcador e a chave tem de devolvê-lo, senão a PRIMEIRA pintura o
    substitui por um traço.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        texto_do_cadeado_cego,
    )

    return texto_do_cadeado_cego(state) or str(_monta().NADA_A_DIZER)


TTL_DO_STEAM_INPUT_S = 20.0

CHIP_DO_STEAM_INPUT = "steam"

CHIP_DO_NATIVO = "nativo"
ROTULO_DO_NATIVO = "Nativo"

CHIPS_DO_DESLIGADO: tuple[str, ...] = (CHIP_DO_NATIVO, CHIP_DO_STEAM_INPUT, "navegacao")

CHIP_DA_NAVEGACAO = "navegacao"


class LinhaDaFileira(NamedTuple):
    """O que o clique num chip da fileira faz — uma linha de :func:`o_que_o_chip_faz`."""

    modo: str
    caminho: str | None
    steam_input: bool


def o_que_o_chip_faz(chave: str) -> LinhaDaFileira:
    """A TABELA DA FILEIRA: o dono único do que cada um dos seis chips faz.

    A fileira é um grupo de rádio: qualquer chip deixa AQUELE aceso, e clicar no aceso REAPLICA.
    Todos tiram o jogo da vez do Steam Input; só o Steam Input o põe. Nativo e Steam Input são o
    modo `native`; a Navegação, o `desktop`. Cada linha sai da `ponte` em
    `painel.CHIPS_DA_ESCADA`, sem digitar o caminho aqui; a máscara vira caminho em
    `virtual_pad.caminho_resolvido`.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_NATIVE
    from hefesto_dualsense4unix.integrations.virtual_pad import caminho_resolvido

    if chave == CHIP_DO_NATIVO:
        return LinhaDaFileira(MODE_NATIVE, None, False)
    chip = next((c for c in _painel().CHIPS_DA_ESCADA if c.chave == chave), None)
    if chip is None or (chip.ponte is None and not chip.modo):
        raise ValueError(f"modo: {chave!r} não é chip da fileira desta aba")
    if chip.ponte is None:
        return LinhaDaFileira(str(chip.modo), None, False)
    ponte = chip.ponte
    if chave == CHIP_DO_STEAM_INPUT:
        return LinhaDaFileira(MODE_NATIVE, None, bool(ponte.steam_input))
    if chip.modo:
        return LinhaDaFileira(str(chip.modo), None, bool(ponte.steam_input))
    return LinhaDaFileira(str(ponte.kind),
                          caminho_resolvido(chip.caminho, ponte.mascara),
                          bool(ponte.steam_input))


@dataclasses.dataclass(frozen=True)
class _DoSteamInput:
    """O que a TELA precisa saber sobre o Steam Input, e nada mais."""

    lista: frozenset[str] = frozenset()
    ligados: frozenset[str] = frozenset()
    pendentes: frozenset[str] = frozenset()
    frase: str = ""
    o_guarda_liga: bool = False


class _VigiaDoSteamInput:
    """Guarda a última leitura do disco e a refaz FORA da thread da janela."""

    def __init__(self) -> None:
        self._dado: _DoSteamInput | None = None
        self._quando = 0.0
        self._em_curso = False
        self._trava = threading.Lock()
        self._geracao = 0

    def agora(self) -> _DoSteamInput | None:
        """O que se sabe AGORA. Nunca bloqueia, nunca levanta."""
        if self._precisa():
            self._disparar()
        return self._dado

    def _precisa(self) -> bool:
        return not self._em_curso and (
            self._dado is None
            or (time.monotonic() - self._quando) > TTL_DO_STEAM_INPUT_S
        )

    def _disparar(self) -> None:
        with self._trava:
            if self._em_curso:
                return
            self._em_curso = True
        fios.soltar(
            "hefesto-steam-input", self._corpo
        )

    def _corpo(self) -> None:
        try:
            self.ler()
        except Exception:
            pass
        finally:
            self._em_curso = False

    def esquecer(self) -> None:
        """Invalida o cache — a próxima :meth:`agora` dispara a releitura."""
        self._quando = 0.0

    def renovar(self) -> None:
        """Relê AGORA — é o que o gesto faz depois de escrever. Nunca levanta."""
        with self._trava:
            self._geracao += 1
        try:
            self.ler()
        except Exception:
            self.esquecer()

    def ler(self) -> _DoSteamInput:
        """BLOQUEIA — lê o disco. Só de thread worker ou de gesto, nunca do tique."""
        geracao = self._geracao
        ponte = _ponte_do_steam_input()
        lista = ponte.ler_allowlist()
        if not lista:
            dado = _DoSteamInput(frase=ponte.Estado().frase())
        else:
            estado = ponte.estado_da_ponte(allowlist=lista)
            dado = _DoSteamInput(
                lista=frozenset(estado.lista),
                ligados=frozenset(estado.ligados),
                pendentes=frozenset(p.appid for p in estado.pendentes),
                frase=estado.frase(),
                o_guarda_liga=o_guarda_liga_o_steam_input(),
            )
        with self._trava:
            if geracao == self._geracao:
                self._dado = dado
                self._quando = time.monotonic()
        return dado


VIGIA_DO_STEAM_INPUT = _VigiaDoSteamInput()


def _ponte_do_steam_input() -> Any:
    """`integrations/steam_input_ponte` — o dono da ponte. Importado TARDE."""
    from hefesto_dualsense4unix.integrations import steam_input_ponte

    return steam_input_ponte


def _qual_jogo(state: dict[str, Any] | None) -> tuple[int | None, str]:
    """`(appid, "aberto"|"fechado")` — as TRÊS evidências, e ela NÃO é daqui."""
    from .a07_lancadores import a_escada_do_jogo

    return a_escada_do_jogo(state)


def _steam_input_da_tela(state: dict[str, Any]) -> str:
    """O chip «Steam Input» acende? — a ESCOLHA do usuário, e não o arquivo da Steam.

    | o que se sabe | como | a tela |
    | --- | --- | --- |
    | **LIGADO** | o jogo da vez está na lista dela **e** o vdf vivo diz diferente de `"0"` | chip
    aceso | | **PENDENTE** | na lista dela, e o vdf ainda diz `"0"` | chip **aceso**, e a pendência
    vai ao diário (:func:`_faixa_do_pendente`) | | **DESLIGADO** | não está na lista |
    chip apagado | | **NÃO SE SABE** | sem appid, ou a vigia ainda não voltou | chip apagado |

    Fato substituído (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026): o PENDENTE ficava apagado
    (acender seria afirmar ponte que não está de pé, o `excecao_inerte` da PONTE-STEAM-INPUT-01). Na
    fileira que é grupo de rádio o chip aceso é o que o usuário ESCOLHEU: com a Steam aberta o
    clique voltava apagado, a queixa «cliquei e nada acendeu». A ponte que não subiu vai para a
    faixa com a frase curta dela, e o guarda do vdf completa quando a Steam fechar. O quarto estado
    não é buraco: acender chip por padrão afirmaria escolha que ninguém fez. A escolha é **POR
    JOGO** (ordem de produto, *"setar o jogo pra funcionar usando os controladores da própria
    steam"*): a chave da Steam é indexada por appid (`UseSteamControllerConfig`), e chip que
    acendesse para a MÁQUINA mentiria em 15 dos 16 jogos do usuário.
    """
    return (CHIP_DO_STEAM_INPUT
            if _o_jogo_na_lista(state, VIGIA_DO_STEAM_INPUT.agora())
            else "")


def _o_jogo_na_lista(state: dict[str, Any] | None,
                     dado: _DoSteamInput | None) -> str:
    """O appid do jogo da vez se ele está na lista do Steam Input — `""` se não.

    Um alvo só para acender e para clicar (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026): o jogo
    da vez de `a_escada_do_jogo`, ABERTO OU FECHADO, o mesmo que :func:`_o_clique_da_fileira` põe ou
    tira da lista. A primeira cura (22/09) só acendia para o ABERTO e gravava para o fechado, a
    assimetria do «cliquei e nada acendeu».
    """
    if dado is None or not dado.lista:
        return ""
    appid, _quando = _qual_jogo(state)
    if appid is None:
        return ""
    return str(appid) if str(appid) in dado.lista else ""


def _a_ponte_que_falta(state: dict[str, Any] | None) -> str:
    """A frase do dono quando o jogo da vez está na lista e o vdf ainda não."""
    dado = VIGIA_DO_STEAM_INPUT.agora()
    if dado is None or not dado.pendentes:
        return ""
    appid, _quando = _qual_jogo(state)
    if appid is None or str(appid) not in dado.pendentes:
        return ""
    return dado.frase


def _unidade_do_guarda() -> str:
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        GUARDA_STEAM_INPUT_TIMER,
    )

    return GUARDA_STEAM_INPUT_TIMER.rsplit(".", 1)[0]


def o_guarda_liga_o_steam_input() -> bool:
    """O vigia do vdf vai ligar (e desligar) o Steam Input quando a Steam fechar?"""
    import os

    from hefesto_dualsense4unix.daemon.service_install import user_unit_dir

    try:
        base = _unidade_do_guarda()
        pasta = user_unit_dir()
        texto = (pasta / f"{base}.service").read_text(encoding="utf-8")
        habilitado = any(os.path.lexists(pasta / quer / f"{base}.{tipo}")
                         for quer, tipo in (("default.target.wants", "path"),
                                            ("timers.target.wants", "timer")))
    except Exception:
        return False
    liga = any(linha.startswith("ExecStart=") and "disable_steam_input.sh" in linha
               and "--apply-quiet" in linha for linha in texto.splitlines())
    return liga and habilitado


def _a_fileira_com_a_mesa(tela: dict[str, str], mesa: list[dict[str, Any]]) -> dict[str, str]:
    """SEM CONTROLE NA MESA, NENHUM BOTÃO DO MODO ACENDE — 22/09/2026.

    Pedido do usuário olhando a aba sem controle e com o «Steam Input» aceso: *"ligado mesmo sem
    controle"*. O Modo é o caminho de UM CONTROLE até o jogo, e sem controle não há caminho em uso;
    acender o «Sony DualSense» seria botão aceso sobre nada. O INTERRUPTOR fica (`Ligado` é o
    serviço, de pé com ou sem controle) e `_estado_da_tela` segue respondendo sobre o DAEMON; esta
    função, que conhece a mesa, decide que a tela cala.
    """
    if mesa:
        return tela
    return {**tela, "modo-aceso": "", "steam-input-aceso": ""}


ARRANJO_DO_CHIP: dict[str, str] = {
    CHIP_DA_NAVEGACAO: "navegacao",
}


def _estado_da_tela(state: dict[str, Any]) -> dict[str, str]:
    """A POSIÇÃO DO INTERRUPTOR e o CHIP ACESO — os dois lidos, nunca cravados.

    Fotografado: com o daemon em ``native_mode false`` e ``gamepad_emulation.enabled false``
    (`mode_of_state` = **desktop**) a página mostrava **Ligado** e **Sony DualSense** aceso, porque
    nem o rótulo do interruptor nem os chips tinham endereço e o que estava na tela era o que o
    gerador cravou em 31/08.

    Os dois leitores são do produto: `painel.hefesto_ligado` (``True`` Ligado, ``False`` Desligado,
    ``None`` não se sabe; DERIVADO de propósito, Ligado é ``gamepad`` **ou** ``desktop``, pois
    comparar um botão só deixaria a tela muda na Navegação, e mudo é pior que errado) e
    `painel.caminho_vivo` (o `gamepad_emulation.caminho`, ``None`` sem saber). O chip aceso é o
    inverso do `_plano_do_chip`, da MESMA tabela (`painel.CHIPS_DA_ESCADA`): chip com ``modo`` é
    modo do produto (a **Navegação**), os outros são CAMINHOS do modo ``gamepad``; um ``if chave ==
    "dualsense"`` seria a segunda cópia da tradução do gesto.

    Fato substituído (MODO-DE-CONEXAO-01, 13/09/2026): o chip acendia pela MÁSCARA
    (`home_actions.mascara_do_aparelho`), que mentia com máscara no cartão (no `uinput` cai no
    `flavor` da sessão; com o P1 em Xbox 360 o «Sony DualSense» ficava aceso). O chip de modo não lê
    a máscara.

    Fato substituído (STEAM-INPUT-01, 20/09/2026): dizia-se que o Steam Input NUNCA acende por não
    ter caminho (`Chip.caminho` é `None`) nem IPC. A primeira metade é o desenho (§4.1: o `caminho`
    escolhe o CANAL do vpad, e o Steam Input senta EM CIMA do DualSense); a segunda caiu: quem o diz
    é o `localconfig.vdf` contra a lista dela, lido por `ponte.estado_da_ponte` (read-only, roda com
    a Steam aberta). Acende por :func:`_steam_input_da_tela`, em CAMPO PRÓPRIO (a razão está em
    :data:`DA_PAGINA`).

    **Serviço parado (estado vazio): Desligado, sem chip aceso.** Posição vazia cai no rádio do
    gerador (`HEFESTO_LIGADO`) e mostrava Ligado com o serviço fora (15/10/2026).
    """
    if not state:
        return {"hef-posicao": POSICAO_COM_O_SERVICO_PARADO, "modo-aceso": "",
                "steam-input-aceso": ""}

    ligado = _painel().hefesto_ligado(state)
    aceso = _chip_do_caminho(state)

    steam = ""
    if ligado is False:
        steam = _steam_input_da_tela(state)
        aceso = "" if steam else CHIP_DO_NATIVO
    elif aceso == CHIP_DA_NAVEGACAO:
        ligado = False
    return {
        "hef-posicao": "" if ligado is None else ("ligado" if ligado else "desligado"),
        "modo-aceso": aceso,
        "steam-input-aceso": steam,
    }


def _chip_do_caminho(state: dict[str, Any]) -> str:
    """A chave do chip que o modo e o caminho VIVOS acendem, sem o Steam Input.

    Inverso de :func:`o_que_o_chip_faz`, da MESMA tabela: o chip cujo modo é o vivo e cujo caminho é
    o vivo (a Navegação não escolhe caminho). O Steam Input fica de fora porque não é caminho (senta
    sobre o do «Sony DualSense») e quem diz se está de pé é a lista (:func:`_estado_da_tela`). `""`
    quando nenhum casa: o Nativo, ou caminho que o daemon não publicou.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD

    painel = _painel()
    modo = painel.modo_vivo(state)
    unico = painel.modo_unico_vivo(state)
    for chip in painel.CHIPS_DA_ESCADA:
        linha = o_que_o_chip_faz(str(chip.chave))
        if linha.steam_input or linha.modo != modo:
            continue
        if linha.modo != MODE_GAMEPAD or str(chip.chave) == unico:
            return str(chip.chave)
    return ""


def _mascara_da_sessao(state: dict[str, Any] | None) -> str | None:
    """A máscara do PROCESSO — a herança de quem não escolheu, e nada mais.

    Um degrau só, e ele existe para que `pacote()` não importe `home_actions`
    no meio do laço dos cartões. O leitor continua sendo o do produto; esta
    função não decide nada.
    """
    if not state:
        return None
    from hefesto_dualsense4unix.app.actions.home_actions import mascara_do_aparelho

    return mascara_do_aparelho(state)


def _mascara_do_cartao(casa: dict[str, Any], da_sessao: str) -> str:
    """A máscara DAQUELE aparelho, na palavra do desenho — ``""`` quando não há.

    O dono do valor é a mesa: `mesa_viva.mesa_do_estado` lê `gamepad_emulation.por_aparelho` (o
    `{uniq: máscara efetiva}` publicado desde 03/09) e cai na máscara da sessão para quem não
    escolheu (a herança do `external_mask`, escrita uma vez, lá); reler o ``state`` seria a segunda
    cópia. O filtro é `NOME_DA_MASCARA` e não lista digitada: só passa o que a tela sabe nomear, o
    que impede o travessão da mesa vazia de virar rótulo (desde 07/09/2026 também o Nintendo Pro,
    que o produto passou a saber montar). Sem correspondência, ``""``, e o alvo `classe` apaga os
    três chips: campo sem informação não mostra nada.
    """
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    rotulo = str(casa.get("mascara") or "")
    if rotulo in set(NOME_DA_MASCARA.values()):
        return rotulo
    return da_sessao if not rotulo or rotulo not in _MASCARAS_DESENHADAS() else ""


def _MASCARAS_DESENHADAS() -> set[str]:  # noqa: N802
    """Os rótulos que o DESENHO tem, do dono deles (`monta.MASCARAS`).

    Separa duas ausências que se pareciam: rótulo que ESTÁ na tela e o produto não sabe montar
    (resposta ``""``, chip apagado, a verdade) e mesa que não falou de máscara (resposta: a da
    sessão, o que valia antes). Hoje nenhum rótulo ilustra o primeiro caso (o **Nintendo Pro**
    deixou de servir em 07/09/2026 porque a máscara existe); é estado do catálogo, não defeito da
    função.
    """
    import monta

    return set(monta.MASCARAS)


def _rotulo_da_mascara(mascara: str | None) -> str:
    """A máscara do produto na palavra do DESENHO — ``""`` quando não há."""
    from hefesto_dualsense4unix.integrations import ponte_escada

    return {
        ponte_escada.MASCARA_DUALSENSE: "DualSense",
        ponte_escada.MASCARA_XBOX: "Xbox 360",
    }.get(str(mascara or ""), "")


_ESCOLHA: dict[str, str] = {}
_ROTULO: dict[str, str] = {}


def _lembrar(campo: str, valor: str, rotulo: str) -> None:
    """Anota o que ela acabou de pedir. Escritor ÚNICO dos dois dicionários."""
    if not valor:
        return
    _ESCOLHA[campo] = valor
    _ROTULO[campo] = rotulo or _rotulo_de(campo, valor)


def _rotulo_de(campo: str, valor: str) -> str:
    """A palavra aprovada pelo usuário para aquela chave, sem passar pela tela.

    Rede de segurança para quando o clique não trouxe `texto` (um dublê de
    régua, um botão que a pintura trocou no meio). Sai de
    `painel.CHIPS_DA_ESCADA`, que é o dono dos rótulos da fileira — digitá-los
    aqui seria a segunda cópia da palavra de produto.
    """
    for chip in _painel().CHIPS_DA_ESCADA:
        if (campo, valor) in (("caminho", chip.caminho), ("mascara", chip.chave)):
            return str(chip.rotulo)
    return valor


def _pendencia(state: dict[str, Any]) -> dict[str, str]:
    """O que o usuário pediu MENOS o que o daemon já alcançou. Devolve o que sobra.

    A regra é de `home_actions.reconciliar_pendente` (AGORA-E-DEPOIS-01): *"uma pendência só existe
    enquanto DIVERGE do vigente"*. Lê tudo por `getattr`, então serve a qualquer objeto (aqui um
    `SimpleNamespace`, pois esta interface não tem `janela`). As pontas também têm dono: o modo vivo
    é `mode_transition.mode_of_state` (o do interruptor) e a máscara viva é
    `home_actions.mascara_do_aparelho`, que separa a máscara EXPLÍCITA da deduzida do `backend` e
    devolve `None` sem saber; comparar contra `None` não apaga pendência, certo: não saber não é ter
    alcançado.

    **Daemon calado não reconcilia** (ramo `visivel=False` de `home_actions.render_pendente`: *"sem
    daemon não há como aplicar, mas o que o usuário decidiu não pode evaporar por causa de um
    engasgo de IPC"*); sem isto `mode_of_state({})` devolveria `desktop` e pedido de Navegação seria
    dado por cumprido por tique sem resposta.
    """
    if not state:
        return dict(_ESCOLHA)
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.home_actions import (
        mascara_do_aparelho,
        reconciliar_pendente,
    )
    from hefesto_dualsense4unix.app.actions.mode_transition import mode_of_state
    from hefesto_dualsense4unix.integrations.virtual_pad import par_do_modo

    unico = _painel().modo_unico_vivo(state)
    lembrete = SimpleNamespace(
        _escolha_pendente=dict(_ESCOLHA) or None,
        _modo_vigente_do_daemon=mode_of_state(state),
        _caminho_vigente_do_daemon=par_do_modo(unico)[0] if unico else None,
        _mascara_vigente_do_daemon=mascara_do_aparelho(state),
    )
    sobra: dict[str, str] = dict(reconciliar_pendente(lembrete) or {})
    _ESCOLHA.clear()
    _ESCOLHA.update(sobra)
    for campo in [c for c in _ROTULO if c not in sobra]:
        del _ROTULO[campo]
    return sobra


def _faixa_do_pendente(state: dict[str, Any]) -> tuple[str, str]:
    """`(frase, alvo)` da faixa laranja — `("", "")` quando não há pendência.

    A frase é do produto: `relancar.texto_do_pendente` (função pura, zero GTK) é a MESMA que a
    estável escreve na linha do pendente, e o marcador `●` também (`relancar.MARCADOR_PENDENTE`).
    **A maiúscula é regra desta linha** (usuário, 28/08/2026, *"o `●` que vem antes é MARCADOR, não
    palavra: a frase começa aqui"*): a estável a escreve em minúscula por ser rótulo no meio de
    outros, aqui é a linha inteira isolada na caixa tracejada; é a única coisa que este arquivo faz
    com o texto do produto, o que evita segunda cópia.

    O vazio é `""` de propósito: o piloto escreve `—` no lugar de vazio (`hefesto_vivo.BOOTSTRAP`,
    `escrever`, a palavra da casa para *"não há"*, como `painel.SEM_LEITOR`), e faixa tracejada com
    travessão solto diz que algo faltou (fotografado em 02/09). Quem some é a CAIXA inteira, por
    `pendente-ha` (alvo `classe`, na `.faixa-final`); desde 21/10 por `display`, com a linha de cima
    (A-JOGAR-SEM-EXTERNO-NAO-DEIXA-FAIXA-VAZIA-01): o «Reconectar» saiu da fileira em 15/10.

    **O `pendente-alvo` morre na primeira pintura** (medido): o `<b>` dele está DENTRO do `<div
    data-campo="pendente">` e o alvo padrão do piloto é `textContent`, então escrever a frase apaga
    os filhos. A tela não mente (a frase já nomeia o alvo, da mesma função do produto); perde-se o
    ENDEREÇO. Curar pede um alvo de pintura que escreva TRECHO de um nó (do piloto) ou o desenho
    parar de repetir o alvo na frase (do usuário). A ponte do Steam Input que não subiu entra aqui
    (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026): o chip acende pela escolha e o que falta
    aplicar é pendência como o caminho que o daemon não alcançou; a frase é do dono
    (:func:`_a_ponte_que_falta`), depois da do modo.
    """
    from hefesto_dualsense4unix.app.actions.relancar import (
        MARCADOR_PENDENTE,
        texto_do_pendente,
    )

    sobra = _pendencia(state)
    da_ponte = _a_ponte_que_falta(state)
    marca = f"{MARCADOR_PENDENTE} "
    if not sobra:
        return (marca + da_ponte, _rotulo_do_chip(CHIP_DO_STEAM_INPUT)) if da_ponte else ("", "")
    rotulos = [_ROTULO.get(c, sobra[c])
               for c in ("modo", "caminho", "mascara") if c in sobra]
    eixo_do_modo = next((c for c in ("modo", "caminho") if c in sobra), None)
    frase = texto_do_pendente(
        modo=(_ROTULO.get(eixo_do_modo, sobra[eixo_do_modo])
              if eixo_do_modo else None),
        mascara=(_ROTULO.get("mascara", sobra.get("mascara"))
                 if "mascara" in sobra else None),
    )
    if frase.startswith(marca):
        resto = frase[len(marca):]
        frase = marca + resto[:1].upper() + resto[1:]
    if da_ponte:
        frase = f"{frase} {da_ponte}"
        rotulos.append(_rotulo_do_chip(CHIP_DO_STEAM_INPUT))
    return frase, ", ".join(rotulos)


def _rotulo_do_chip(chave: str) -> str:
    """A palavra aprovada pelo usuário para o chip, de `painel.CHIPS_DA_ESCADA`."""
    if chave == CHIP_DO_NATIVO:
        return ROTULO_DO_NATIVO
    return next((str(c.rotulo) for c in _painel().CHIPS_DA_ESCADA
                 if c.chave == chave), chave)


_PENDENCIA_RELATADA = ""


def _relatar_a_pendencia(frase: str) -> None:
    """Leva a pendência ao diário da janela — e não mais à tela."""
    global _PENDENCIA_RELATADA
    if frase == _PENDENCIA_RELATADA:
        return
    _PENDENCIA_RELATADA = frase
    if frase:
        print(f"[relato] {PAGINA} · pendente: {frase}", file=sys.stderr)


from . import gesto  # noqa: E402

BOTOES_SEM_DONO: dict[str, str] = {}


def _painel() -> Any:
    """`app/actions/jogar/painel` — o dono das perguntas desta aba."""
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


def _plano(
    chave: str, mascara: str | None = None, caminho: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """A sequência de IPC daquele modo — DELEGADA, sem uma linha de regra aqui."""
    painel = _painel()
    plano: list[tuple[str, dict[str, Any]]] | None = painel.plano_do_modo(
        chave, mascara, **({"caminho": caminho} if caminho else {}))
    if plano is None:
        raise RuntimeError(painel.porque_nao_aplica(chave))
    return plano


def _aplicar(p: Any, plano: list[tuple[str, dict[str, Any]]]) -> bool:
    """Despacha o plano na ORDEM, pelo degrau 3 da ponte."""
    confirmou = True
    for metodo, params in plano:
        if not p.chamar(metodo, **params):
            confirmou = False
    return confirmou


MODO_SEM_CONFIRMACAO = (
    "O Hefesto demorou a responder, e a troca pode não ter acontecido. Se o "
    "botão não acender, clique de novo."
)


def _dizer_se_nao_confirmou(confirmou: bool) -> None:
    """Levanta com :data:`MODO_SEM_CONFIRMACAO` quando `_aplicar` voltou falso."""
    if not confirmou:
        raise RuntimeError(MODO_SEM_CONFIRMACAO)


ACHADO_DO_TIMEOUT = (
    "ponte.TETOS dá 2,0 s à troca de modo, o mesmo valor de mode_transition."
    "MODE_IPC_TIMEOUT_S, e ao gesto que pede o P1 o prazo do daemon com folga; "
    "o teto de 250 ms é só o dos métodos fora da tabela."
)


@gesto("01-jogar.html", "hefesto",
       grava="o modo no perfil ativo, pelo native.mode.set e pelo "
             "gamepad.emulation.set à mão (o daemon grava)")
def hefesto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O INTERRUPTOR: Ligado (`gamepad`) ou Desligado (`native`).

    A posição é o `data-modo` do rótulo clicado, que chega em `o["modo"]` (o mesmo endereço da
    pintura viva, que acende a posição a partir de `mode_of_state`); um segundo atributo só para o
    clique daria endereço para ler e outro para escrever. **"Desligado" é o modo nativo e não "parar
    o Hefesto"** (31/08/2026: *"o modo nativo já existe ali (…) e se eu quiser desligar modo hefesto
    clico em desligado e o modo nativo fica online."*): **parar** o serviço é só da aba Sistema, e
    este gesto nunca chama `daemon.pause` nem `stop`.

    **Ligado passou a ligar o serviço também (03/09/2026):** *"Adiciona essa função extra quando
    clicar em ligar. E em sistema um específico pra parar o Daemon E Ativar o Daemon (sendo que em
    jogar também consegue isso)."* Vem ANTES do plano porque os três IPCs atravessam a ponte e com o
    serviço parado ela não tem socket; a ordem inversa recusaria o clique e deixaria o serviço
    parado, falhando no caso que o usuário pediu que funcionasse. O ato é
    `a09_sistema.ativar_o_servico()`, o mesmo do botão "Ativar o serviço", com o
    `_user_stopped_daemon` desarmado junto (sem ele o `ensure_daemon_running` mata o daemon na
    próxima abertura por um caminho e não pelo outro); duas cópias se afastariam. Só nas posições
    **LIGADAS** (`painel.MODOS_LIGADOS`: `gamepad` e `desktop` são o Hefesto no meio, `native`
    fora): ligar o serviço no "Desligado" subiria o que acabou de mandar sair da frente.
    """
    if str(o.get("modo") or "") in _painel().MODOS_LIGADOS:
        from . import a09_sistema

        a09_sistema.ativar_o_servico()
    return _hefesto_o_modo(ctx, o, p)


def _hefesto_o_modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O interruptor propriamente dito: o plano do modo, e a anotação da faixa."""
    chave = str(o.get("modo") or "")
    if not chave:
        raise ValueError(
            "hefesto: o clique não disse qual posição do interruptor — o "
            "`data-modo` do rótulo não chegou")
    confirmou = _aplicar(p, _plano(chave))
    _lembrar("modo", chave, str(o.get("texto") or ""))
    _dizer_se_nao_confirmou(confirmou)


def _plano_do_chip(chave: str) -> list[tuple[str, dict[str, Any]]]:
    """A sequência daquele chip da fileira — o modo e o CAMINHO saem da tabela.

    Quem diz modo e caminho de cada chip é :func:`o_que_o_chip_faz` (de `painel.CHIPS_DA_ESCADA`);
    digitar `"dualsense"` seria a segunda cópia. Dois eixos (`painel`): a **Navegação** É um modo do
    produto e vai por ele; os outros são CAMINHOS do modo `gamepad` e vão pelo `caminho` do plano, o
    «Steam Input» também, com o caminho sobre o qual o degrau 4 senta
    (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026; sem ele, vindo do «Xbox», mexia só na lista e
    o «Xbox» seguia aceso).

    Fato substituído (MODO-DE-CONEXAO-01, 13/09/2026): o plano levava a MÁSCARA da ponte do chip
    (`flavor`, só o padrão da máscara no daemon), e com máscara no cartão do P1 o daemon respondia
    `ja_estava` e o piloto escrevia «aplicado» sobre nada. A máscara não sai mais daqui.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import (
        MODE_DESKTOP,
        MODE_GAMEPAD,
        plan_mode_transition,
    )
    from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_modo

    linha = o_que_o_chip_faz(chave)
    if linha.modo == MODE_DESKTOP and chave in ARRANJO_DO_CHIP:
        return plan_mode_transition(MODE_DESKTOP, arranjo=ARRANJO_DO_CHIP[chave])
    if linha.modo != MODE_GAMEPAD:
        return _plano(linha.modo)
    if linha.caminho:
        return _plano(MODE_GAMEPAD, caminho=linha.caminho)
    sem_caminho = normalizar_modo(chave)
    if sem_caminho is None:
        raise RuntimeError(BOTOES_SEM_DONO.get(f"modo-{chave}", "sem dono no produto"))
    return _plano(MODE_GAMEPAD, mascara=sem_caminho)


def _lembrar_do_chip(chave: str, o: dict[str, Any]) -> None:
    """Anota o que o chip clicado pediu, no EIXO dele — e só nele.

    Um chip mexe num eixo só (a Navegação **é** um modo, os outros são CAMINHOS do `gamepad`);
    anotar `modo=gamepad` junto com o caminho poria na faixa a palavra do CHIP ("Xbox") sob a do
    INTERRUPTOR ("Ligado"), dois nomes colados numa linha. Fato substituído (MODO-DE-CONEXAO-01,
    13/09/2026): o chip anotava a MÁSCARA, comparada com a viva, e com o cartão do P1 em DualSense
    «● Vai mudar para: Xbox» nunca sumia; anota o `"caminho"`. O eixo de cada chip sai de
    :func:`o_que_o_chip_faz`, de onde `_plano_do_chip` tira o caminho, não de `if` por nome.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD

    try:
        linha = o_que_o_chip_faz(chave)
    except ValueError:
        return
    rotulo = str(o.get("texto") or "") or _rotulo_do_chip(chave)
    if linha.modo != MODE_GAMEPAD:
        _lembrar("modo", linha.modo, rotulo)
        return
    campo, outro = ("caminho", "mascara") if linha.caminho else ("mascara", "caminho")
    _ESCOLHA.pop(outro, None)
    _ROTULO.pop(outro, None)
    _lembrar(campo, linha.caminho or chave, rotulo)


def _o_clique_da_fileira(ctx: Contexto, o: dict[str, Any], p: Any,
                         chave: str) -> dict[str, Any] | None:
    """O CLIQUE NUM CHIP DO MODO — os quatro gestos passam por aqui, e só por aqui."""
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    from .a07_lancadores import METODO_DA_RECARGA

    linha = o_que_o_chip_faz(chave)
    _desarmar_o_chip()
    appid, _quando = _qual_jogo(ctx.state)
    if linha.steam_input and appid is None:
        raise RuntimeError(str(format_game_broken_result(status="sem_jogo")))

    confirmou = _aplicar(p, _plano_do_chip(chave))
    _lembrar_do_chip(chave, o)

    recado = ""
    if appid is not None:
        alvo = str(appid)
        if linha.steam_input:
            status = slo.add_appid_to_steam_input_allowlist(alvo, nota=NOTA_DA_ESCOLHA)
        else:
            status = slo.remove_appid_from_steam_input_allowlist(alvo)
        if status in ("appid_invalido", "erro"):
            raise RuntimeError(str(format_game_broken_result(status=status, appid=alvo)))
        if status != "nao_estava":
            p.chamar(METODO_DA_RECARGA)
            try:
                recado = _reconciliar_o_vdf(alvo, linha.steam_input)
            finally:
                VIGIA_DO_STEAM_INPUT.renovar()

    _dizer_se_nao_confirmou(confirmou)
    return {"recado": recado} if recado else None


@gesto("01-jogar.html", "modo-dualsense",
       grava="o caminho no perfil ativo, pelo gamepad.emulation.set à mão "
             "(o daemon grava)")
def modo_dualsense(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Sony DualSense": o Hefesto entrega o controle pelo canal do DualSense.

    É o CAMINHO `uhid` (o relatório do DualSense, por onde voltam do jogo gatilho, luz e LED de
    jogador), o PRIMEIRO degrau que o produto tenta, `ponte_escada.ESCADA[0]`: **dez** linhas do
    `mapa-controles.csv` só chegam ao jogo por `uhid` (a razão está no cabeçalho de lá). O modo
    segue `gamepad`; o que muda entre este chip e o "Xbox" é o CAMINHO, não o modo nem a máscara,
    que é do cartão de cada controle (MODO-DE-CONEXAO-01, 13/09/2026): com máscara Xbox 360 no
    cartão este caminho fica escolhido e aceso e o aparelho sai no canal comum (o `uhid` só se
    constrói com máscara DualSense, `virtual_pad.quer_uhid`). Tira o jogo da vez do Steam Input
    (:func:`o_que_o_chip_faz`; o clique é :func:`_o_clique_da_fileira`).
    """
    return _o_clique_da_fileira(ctx, o, p, "dualsense")


@gesto("01-jogar.html", "modo-xbox",
       grava="o caminho no perfil ativo, pelo gamepad.emulation.set à mão "
             "(o daemon grava)")
def modo_xbox(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Xbox": o canal comum, o do controle de Xbox — o SEGUNDO que o Hefesto tenta.

    Nasceu em 31/08/2026, dívida paga: `Ponte(gamepad, xbox)` é degrau da `ESCADA` desde 19/08 e
    nenhum chip o nomeava (o que a conferência da escada contra a tela denunciava). É o CAMINHO
    `uinput` (MODO-DE-CONEXAO-01, 13/09/2026) e NÃO escolhe a máscara: com o P1 em DualSense o jogo
    segue vendo o DualSense, pelo canal comum (até 13/09 mandava a máscara Xbox 360 e dizia
    «aplicado» sem mudar nada com máscara no cartão). Tira o jogo da vez do Steam Input, venha de
    onde vier: com ele na lista a Steam pegaria o controle por baixo do «Xbox» aceso
    (:func:`o_que_o_chip_faz`).
    """
    return _o_clique_da_fileira(ctx, o, p, "xbox")


@gesto("01-jogar.html", "modo-nintendo",
       grava="o modo no perfil ativo, pelo gamepad.emulation.set à mão (o daemon grava)")
def modo_nintendo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Nintendo Pro": todos os controles chegam ao jogo como o Pro Controller.

    É o modo único sem caminho (`virtual_pad.par_do_modo`): o plano leva a máscara `nintendo` e o
    daemon a vale para todos os controles, pelo escritor único do modo. Tira o jogo da vez do Steam
    Input, como o «Xbox» (:func:`o_que_o_chip_faz`; o clique é :func:`_o_clique_da_fileira`).
    """
    return _o_clique_da_fileira(ctx, o, p, "nintendo")


@gesto("01-jogar.html", "modo-nativo",
       grava="remove_appid_from_steam_input_allowlist")
def modo_nativo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Nativo": o Hefesto fora do meio, e a Steam fora do jogo da vez.

    NO-DESLIGADO-A-STEAM-NAO-SE-METE-E-O-JOGO-MANDA-01, 08/10/2026: *«Desligado seria garantir que a
    steam não se mete e o jogo manda.»* O clique é o da fileira (:func:`_o_clique_da_fileira`): modo
    `native`, jogo da vez fora da lista do Steam Input e `localconfig.vdf` relido. Com a Steam
    aberta a escrita espera e o guarda do vdf completa quando ela fechar (e tira a Steam de todo
    jogo fora da lista a cada saída dela).
    """
    return _o_clique_da_fileira(ctx, o, p, CHIP_DO_NATIVO)


NOTA_DA_ESCOLHA = "escolhido na aba Jogar: usar os controles da própria Steam"

def _o_que_o_vdf_diz(alvo: str) -> str | None:
    """O `UseSteamControllerConfig` do appid na árvore VIVA, relido do zero.

    **O veredito é o arquivo** (HONESTIDADE-STEAM-01, aplicado também pela aba 07 ao desligar): o
    `rc` da escrita pode ser 0 e o valor não ter mudado. Depois de escrever, abre o vdf de novo e
    diz o que ficou, separando o recado VERDE da recusa. `None` = o produto não sabe (nenhum vdf
    legível, árvore viva não provada, jogo fora deste vdf); nunca `"0"` por omissão: *ausência é
    resposta*, e responder "desligado" sobre o que não se leu é o defeito que esta casa mede toda
    semana.
    """
    ponte = _ponte_do_steam_input()
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    for vdf in slo.discover_vdfs(None):
        if slo.is_sandboxed_layout(vdf):
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        viva = ponte.arvore_viva(ponte.ler_arvores(texto))
        if viva is None:
            continue
        achado = viva.chaves.get(alvo)
        if achado is not None:
            return str(achado[0]).strip()
    return None


def _os_que_ficam(alvo: str) -> list[str]:
    """Os appids que o DESLIGAR tem de preservar — tudo menos o `alvo`."""
    ponte = _ponte_do_steam_input()
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    todos: set[str] = set()
    for vdf in slo.discover_vdfs(None):
        if slo.is_sandboxed_layout(vdf):
            continue
        pasta = ponte.pasta_das_configs_por_jogo(vdf)
        if pasta is None:
            continue
        configurados = ponte.configuracao_por_jogo(pasta)
        if configurados:
            todos |= configurados
    return sorted(todos - {alvo})


STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA = (
    "Tirei este jogo da lista. A Steam sai do comando dele quando você fechar "
    "a Steam."
)
STEAM_INPUT_NAO_MUDOU_O_ARQUIVO = (
    "Anotei este jogo, mas a Steam ainda não mudou de lado para ele. Abra-o "
    "uma vez pela Steam e clique aqui de novo."
)
STEAM_INPUT_SAIU_E_A_STEAM_CONTINUA = (
    "Tirei este jogo da lista, mas a Steam continua no comando dele."
)
STEAM_INPUT_SAIU_MAS_CONTINUA = (
    f"{STEAM_INPUT_SAIU_E_A_STEAM_CONTINUA} O Hefesto a tira de lá em até meia "
    "hora, ou na próxima vez que a Steam fechar."
)


def _reconciliar_o_vdf(alvo: str, ligar: bool) -> str:
    """Faz o `localconfig.vdf` concordar com a vontade dela — ou diz o que falta.

    **A escrita é do dono, inteira** (`steam_input_ponte`): backup `.bak.…` ao lado, `tmp` +
    `replace`, segunda régua conferindo o texto antes de trocar o arquivo; a ORDEM DOS PORTÕES é a
    dele (jogo aberto, Steam aberta, e só então a escrita). **Nunca fecha a Steam do usuário**: com
    ela aberta o dono ADIA, e quem pode fechá-la é só o segundo clique já armado
    (:func:`_fechar_a_steam_e_ligar`). Sem ele o produto completa sozinho:
    `hefesto-steam-input-guard.path` (**active** e **enabled** em 20/09/2026,
    `PathChanged=%h/.steam/steam/userdata`) acorda quando a Steam acaba de sair, o único instante em
    que a escrita sobrevive, e roda `disable_steam_input.sh --apply-quiet`, que zera o
    `UseSteamControllerConfig` de todo jogo FORA da lista e liga os que estão nela, **nos dois
    sentidos, sem novo clique**.

    **O que a Steam ainda não fez não é recusa** (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026):
    o adiamento levantava e a tela piscava recusa sobre clique que valeu (lista e caminho mudaram, o
    chip acende). Hoje o LIGAR adiado volta calado e a frase do dono (`Estado.frase()`, que nomeia o
    jogo e diz quando) vai à pendência (:func:`_a_ponte_que_falta`); o DESLIGAR adiado, que o dono
    não sabe dizer, volta como recado. Só levanta a Steam FECHADA sem o arquivo mudar: o jogo não
    está no vdf e o passo seguinte é abri-lo uma vez pela Steam.

    **O veredito é o arquivo** (HONESTIDADE-STEAM-01): o `status` do dono diz `nada_a_fazer` tanto
    de jogo já certo quanto de jogo que o vdf desconhece, desfechos opostos para a tela; quem separa
    é a releitura.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    ponte = _ponte_do_steam_input()

    def _acao() -> Any:
        if ligar:
            return ponte.garantir_ponte(allowlist=[alvo])
        return ponte.garantir_fora_da_lista_desligado(allowlist=_os_que_ficam(alvo))

    resultado = _acao()

    atual = _o_que_o_vdf_diz(alvo)
    adiado = (resultado[0] in (ponte.PONTE_ADIADA_JOGO, ponte.PONTE_ADIADA_STEAM)
              or slo.steam_running())
    if ligar:
        if atual == ponte.LIGADO or adiado:
            return ""
        raise RuntimeError(STEAM_INPUT_NAO_MUDOU_O_ARQUIVO)
    if atual in (None, ponte.DESLIGADO):
        return ""
    if not o_guarda_liga_o_steam_input():
        return STEAM_INPUT_SAIU_E_A_STEAM_CONTINUA
    return STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA if adiado else STEAM_INPUT_SAIU_MAS_CONTINUA


GESTO_DO_STEAM_INPUT = "modo-steam"


@gesto("01-jogar.html", GESTO_DO_STEAM_INPUT,
       grava="add_appid_to_steam_input_allowlist")
def modo_steam(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Steam Input": a Steam entrega a ENTRADA **daquele jogo**, e só dele.

    O escopo é por jogo (ordem de produto: *"setar **o jogo** pra funcionar usando os controladores
    da própria steam"*): a chave é indexada por appid (`UseSteamControllerConfig`,
    `steam_input_ponte`) e chip que escrevesse para a MÁQUINA aplicaria ao jogo que estivesse aberto
    (`CAMINHO-CONTAGIO-01` com outro campo). **É um botão do Desligado**
    (NO-DESLIGADO-A-STEAM-NAO-SE-METE-E-O-JOGO-MANDA-01, 08/10/2026: *«Steam Input sai de
    Ligado.»*): manda o modo `native` (:func:`o_que_o_chip_faz`) e põe o jogo da vez na lista; o
    Nativo o tira. O terceiro termo da `Ponte` tem casa no disco (`steam_input_apps.txt` e o carimbo
    `PonteConfirmada.steam_input`) e não vai ao `mode`.

    **O clique PÕE, sempre, não é mais interruptor** (até 22/09 o sentido saía da ponte do jogo da
    vez): clicar no aceso REAPLICA, o que completa a ponte PENDENTE, e tirar o jogo da lista é
    clicar em qualquer dos outros três.

    As duas metades têm preços diferentes, e só uma acontece sempre:

    1. **a vontade dela**: uma linha num arquivo NOSSO, reversível, com a recarga atrás. A lista é
    relida do disco a cada consulta, mas o que entrega a entrada do jogo ao controle só nasce quando
    o daemon rematerializa o `steam_app_<appid>.env`; sem `launch_env.refresh` a marca só valeria no
    próximo arranque e ela clicaria de novo achando que não pegou;
    2. **a ponte**: reescreve o `localconfig.vdf` DO USUÁRIO, e a Steam tem de estar FECHADA (ela
      regrava o arquivo ao sair e engole a edição). Aberta, o dono ADIA; o chip acende pela escolha
      e a pendência vai ao diário (:func:`_faixa_do_pendente`).

    **O primeiro clique avisa, o segundo fecha** (23/09/2026,
    `D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`). Com a Steam aberta, sem jogo aberto e o jogo em `"0"`,
    o primeiro ARMA (:func:`_armar_se_a_steam_segura`): o rótulo vira «Fechar a Steam?» por
    `confirmacao.SEGUNDOS_PARA_CONFIRMAR`. O segundo traz esse rótulo (só existe no chip armado) e
    fecha a Steam, liga e a reabre (:func:`_fechar_a_steam_e_ligar`). Com jogo aberto nada arma
    (fechar a Steam o derrubaria); o guarda do vdf completa quando os dois saírem. Fato substituído
    (24/09/2026): dizia-se que o gesto *"não fecha a Steam"* porque chip é `<span>` estático sem
    rótulo para trocar; o `blocos:` troca o miolo como nos botões armados da aba 09
    (:func:`_o_rotulo_do_chip`), e o rótulo lido de volta no clique prova que ela LEU a pergunta.

    **O veredito é o arquivo:** nenhum desfecho verde sai sem :func:`_o_que_o_vdf_diz` reler o vdf.
    `status` de sucesso sobre arquivo que não mudou é o `excecao_inerte` que a PONTE-STEAM-INPUT-01
    existiu para matar (*"a lista só preserva o que já estava ligado, ela nunca liga"*), e foi assim
    que a janela velha cantou "Steam Input desligado" sobre um no-op até a HONESTIDADE-STEAM-01. Sem
    jogo, nada acontece: a recusa é a frase do dono (`format_game_broken_result(status="sem_jogo")`)
    e nem lista, vdf ou caminho são tocados (o quarto estado de :func:`_steam_input_da_tela` do lado
    do clique).
    """
    confirmado = _o_clique_que_confirma(ctx, o)
    if confirmado:
        return _fechar_a_steam_e_ligar(confirmado)
    recado = _o_clique_da_fileira(ctx, o, p, CHIP_DO_STEAM_INPUT)
    return recado or _armar_se_a_steam_segura(ctx)


STEAM_INPUT_ARMADO = "Fechar a Steam?"


def _chave_do_chip(appid: object) -> str:
    """A chave do chip «Steam Input» armado para AQUELE jogo."""
    return confirmacao.chave(PAGINA, GESTO_DO_STEAM_INPUT, appid)


def _desarmar_o_chip() -> None:
    """Desarma o chip, e SÓ ele: o botão armado da aba 09 não é desta fileira."""
    if confirmacao.armado_agora().startswith(_chave_do_chip("")):
        confirmacao.desarmar()


def _o_rotulo_do_chip(state: dict[str, Any] | None) -> dict[str, str]:
    """O `blocos:` do chip — «Fechar a Steam?» armado, «Steam Input» em repouso.

    Sai em todo tique, como os botões da aba 09 (`a09_sistema.blocos_dos_botoes`): o gesto arma e o
    tique REPÕE o rótulo quando o relógio vence. O piloto só reescreve o miolo quando ele muda,
    então o repouso não custa nada, e só pergunta qual é o jogo quando há algo armado nesta fileira
    (em repouso, zero disco). O rótulo em repouso é o de `painel.CHIPS_DA_ESCADA`
    (:func:`_rotulo_do_chip`).
    """
    rotulo = _rotulo_do_chip(CHIP_DO_STEAM_INPUT)
    armado = confirmacao.armado_agora()
    if armado.startswith(_chave_do_chip("")):
        appid, _quando = _qual_jogo(state)
        if appid is not None and armado == _chave_do_chip(appid):
            rotulo = STEAM_INPUT_ARMADO
    return {f'[data-gesto="{GESTO_DO_STEAM_INPUT}"]': html.escape(rotulo)}


def _armar_se_a_steam_segura(ctx: Contexto) -> dict[str, Any] | None:
    """O PRIMEIRO CLIQUE AVISA — arma o chip se só a Steam aberta segura a ponte.

    Arma com as três condições, cada uma pergunta ao dono na hora: o vdf diz `"0"` para o jogo
    (:func:`_o_que_o_vdf_diz`; sem o jogo no vdf, `None`, fechar a Steam não muda nada e não se
    oferece); a Steam está aberta (`steam_running`, ela segura a escrita); NENHUM jogo aberto
    (`steam_game_running`; fechar a Steam o mataria e `with_steam_closed` recusaria, e oferecer
    segundo clique que só pode recusar é pedir consentimento para nada). Devolve o `blocos:` com o
    rótulo armado para a troca ser INSTANTÂNEA (o tique também o põe); `None` quando não arma.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    appid, _quando = _qual_jogo(ctx.state)
    if appid is None:
        return None
    alvo = str(appid)
    if _o_que_o_vdf_diz(alvo) != _ponte_do_steam_input().DESLIGADO:
        return None
    if not slo.steam_running() or slo.steam_game_running():
        return None
    confirmacao.armar(_chave_do_chip(alvo))
    return {"blocos": _o_rotulo_do_chip(ctx.state)}


def _o_clique_que_confirma(ctx: Contexto, o: dict[str, Any]) -> str:
    """O appid, se ESTE clique é o segundo — `""` se é um primeiro clique."""
    if str(o.get("texto") or "").strip() != STEAM_INPUT_ARMADO:
        return ""
    appid, _quando = _qual_jogo(ctx.state)
    armado = confirmacao.armado_agora()
    confirmacao.desarmar()
    if appid is None or armado != _chave_do_chip(appid):
        raise RuntimeError(STEAM_INPUT_A_PERGUNTA_VENCEU)
    return str(appid)


STEAM_INPUT_A_PERGUNTA_VENCEU = (
    f"Passaram-se mais de {int(confirmacao.SEGUNDOS_PARA_CONFIRMAR)} segundos "
    "desde a pergunta — não fechei a Steam. Clique de novo para começar.")


def _fechar_a_steam_e_ligar(alvo: str) -> dict[str, Any]:
    """O SEGUNDO CLIQUE: fecha a Steam, liga o jogo no vdf e a reabre.

    Nada é mecanismo novo: `with_steam_closed` é o dono do fechar e reabrir a Steam
    (portão de JOGO aberto antes de tudo, Steam que não fecha não é editada, reabertura em
    `finally`), a escrita é `garantir_ponte` com `allowlist=[alvo]`, como no primeiro clique, e a
    recusa é `daemon_actions.format_steam_janela_recusa`. A lista é garantida antes (o primeiro
    clique a gravou e um segundo `add_…` devolve `ja_estava`; sem ela o guarda do vdf desligaria o
    jogo na próxima saída da Steam). O veredito é o arquivo (:func:`_o_que_o_vdf_diz`).
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
        format_steam_janela_recusa,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    ponte = _ponte_do_steam_input()
    status = slo.add_appid_to_steam_input_allowlist(alvo, nota=NOTA_DA_ESCOLHA)
    if status in ("appid_invalido", "erro"):
        raise RuntimeError(str(format_game_broken_result(status=status, appid=alvo)))
    try:
        if _o_que_o_vdf_diz(alvo) == ponte.LIGADO:
            return {"blocos": _o_rotulo_do_chip(None)}
        janela, _resultado = slo.with_steam_closed(
            lambda: ponte.garantir_ponte(allowlist=[alvo]))
        recusa = format_steam_janela_recusa(janela)
        if recusa is not None:
            raise RuntimeError(recusa)
        if _o_que_o_vdf_diz(alvo) != ponte.LIGADO:
            raise RuntimeError(STEAM_INPUT_NAO_MUDOU_O_ARQUIVO)
    finally:
        VIGIA_DO_STEAM_INPUT.renovar()
    return {"blocos": _o_rotulo_do_chip(None)}


@gesto("01-jogar.html", "modo-navegacao",
       grava="liga o mouse emulado e o ponteiro anda na tela dela")
def modo_navegacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Navegação" (Desligado): o controle vira teclado e mouse do computador.

    O caso do meio (`painel` o explica): a Navegação **não é degrau da `ESCADA`** (`KIND_DESKTOP`
    existe e `indice_do_degrau` devolve -1) e **tem escritor**, `apply_mode('desktop')`; confundir
    as perguntas pintaria "sem dono" sobre um botão que dá.

    São três IPCs, e o terceiro separa entrar no modo de entrar num modo sem função
    (`MODO-QUE-NAO-CONTROLA-01`, medido ao vivo: *"cliquei em aplicar e nada"*). Vai POR ÚLTIMO:
    ligar o mouse antes de o gamepad sair faria a exclusão mútua do daemon derrubá-lo; a ordem é do
    plano.

    **O terceiro passo trocou de fonte** (POINT-AND-CLICK-01, 17/09/2026, ordem de produto: *"o modo
    point and click é o modo navegação e o modo que nós mesmos podemos usar e configurar na aba
    navegação. **Ele ativa o modo configurado lá.**"*): era `mouse.emulation.restore`, que lê a flag
    de sessão da MÁQUINA; é `desktop.arranjo.apply`, que lê o PERFIL ATIVO (mouse, `key_bindings`,
    `button_actions`, `teclado_emulado` e a queda da supressão). As cinco coisas que a aba Navegação
    grava chegavam ao disco e não voltavam, e o chip daqui é a única porta (a aba manda ir à Jogar
    trocar o modo). O PS+R3 para na Navegação desde 13/09/2026 (`hotkey.CICLO_DE_PONTES`) e desde
    17/09 entra pela MESMA porta deste clique; o que ela não tem é degrau na `ESCADA` automática,
    outra pergunta. Tira o jogo da vez do Steam Input, como o «Xbox» (:func:`o_que_o_chip_faz`; o
    clique é :func:`_o_clique_da_fileira`).
    """
    return _o_clique_da_fileira(ctx, o, p, "navegacao")


@gesto("01-jogar.html", "cadeado", grava="freestyle_set")
def cadeado(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O botão «Modo Freestyle» — até 23/09/2026, a caixa «Trava o perfil ativo».

    Pedido nomeado do usuário (23/07/2026) que saiu do desenho por escolha declarada na legenda (*"A
    caixa saiu — o perfil ativo já diz isso"*). Desde então a coluna **Atenção** passou a ler
    `painel.AVISOS_DA_TELA` (`autoswitch_lock_text` e `texto_do_cadeado_cego` são duas das seis
    fontes): **a tela EXPLICAVA o cadeado e não oferecia onde ligá-lo, em nenhuma das dez abas**. A
    decisão [03] do PO o traz de volta (*"Volta para a Jogar, embaixo de Modo"*), a única posição em
    que a frase que explica e o botão que resolve ficam na mesma tela. O escritor existia
    (`ponte.freestyle_set` → `app/ipc_bridge.freestyle_set`, o mesmo de
    `_on_home_autoswitch_lock_toggled` da antiga); desde 28/09/2026 (O-FREESTYLE-E-UMA-CAMADA-SO-01)
    ligar é o «Ativar» do Freestyle na aba Perfis, e ele manda em todo jogo.

    **O valor vai ABSOLUTO, nunca como toggle** (a ponte aceita `locked=None` e o daemon inverte),
    por duas razões medidas:

    1. **um clique chega DUAS vezes**: o ouvinte único do piloto está em `click` **e** `change`
    (`hefesto_vivo.BOOTSTRAP`) e `<input type="checkbox">` dispara os dois (o `change` nasceu para
    `<select>` e campos de texto); dois toggles seriam NO-OP;
    2. **o daemon poderia inverter a partir de outro estado**: o absoluto é a escolha lida da tela,
      o toggle é a tela obedecendo a estado que ela não viu.

    O `evento` filtra a segunda entrega para o disco receber UMA escrita por clique
    (`profiles.manager.ligar_o_freestyle` grava). O `change` é o escolhido por só disparar quando a
    caixa MUDOU (clique em rótulo, espaço e `el.click()` sintético passam pelos três caminhos);
    clique sem `evento` (a régua dos botões, que monta o recado à mão) vale, e o padrão é `change`.
    A verdade volta do DAEMON: o alvo `marcado` repinta a caixa a cada tique a partir de
    `freestyle_ligado`, e se a escrita não pegar a caixa **volta sozinha**.

    Relato fechado (06/09/2026, `ONDA3-GESTO-DECLARA-01`): a declaração mora no PRÓPRIO decorador
    (`grava="freestyle_set"`) e `PERIGOSOS` deriva dela; quem escreve o gesto fecha o contrato. Fato
    substituído (06/09/2026): a caixa está na página publicada (`onde.PUBLICADO`; a régua
    `test_o_cadeado_esta_publicado` lê o arquivo). O `--prova-gesto` não a clica por outra razão,
    `PERIGOSOS`: clicar GRAVA no disco do usuário (`utils/session.save_freestyle_ligado`, pelo
    `freestyle.set`), e régua que mudasse preferência dela para provar que sabe clicar seria pior
    que a cobertura que compra.

    **O verde é o recibo e só acende quando o serviço confirmou** (05/09/2026, `03-Q4`: *"O campo
    que você acabou de mexer ganha uma borda verde por cerca de um segundo e meio"*, *"nenhuma
    palavra nova entra na tela"*). É o gesto que mais precisava dele: o único cujo efeito **não
    aparece em lugar nenhum** (trocar de modo acende um chip, a máscara muda o cartão; o cadeado
    muda um booleano no disco e a caixa já está marcada pelo clique). Pedir o verde é VOLTAR SEM
    LEVANTAR, mecanismo do piloto: `hefesto_vivo._gesto` anota `"aplicou"` no ramo sem exceção e o
    `finally` leva o desfecho ao pouso, que acende `hef-deu-certo` por `MS_DA_PISCADA` no elemento
    clicado.

    O que faltava era o direito de pedi-lo: a resposta da ponte ia para o lixo.
    `ipc_bridge.freestyle_set` devolve o estado que FICOU valendo (e `None` sem resposta); sem
    lê-lo, clique com o serviço parado piscava VERDE e a caixa desmarcava no tique seguinte
    (`_cadeado` sem `freestyle_ligado` devolve `""`), *guardei* e *não está guardado* com 100 ms de
    intervalo. A guarda é `is None` e não comparação: `_handle_freestyle_set`
    (`daemon/ipc_handlers.py`) usa o `ligado` quando vem no pedido (o toggle é para quem NÃO manda
    valor, e este gesto sempre manda), então bool que discordasse do pedido é ramo que o daemon não
    produz.
    """
    if str(o.get("evento") or "click") != "click":
        return
    pedido = _cadeado(ctx.state) != CADEADO_LIGADO
    if p.freestyle_set(ligado=pedido) is None:
        raise RuntimeError(CADEADO_RECUSA)


def _o_radio_de_volta(ctx: Contexto) -> tuple[int, int]:
    """PASSO 0 — o RÁDIO. Devolve `(voltaram, esperam_o_ps)`."""
    from . import perfil

    return perfil.o_radio_de_volta(ctx)


@gesto("01-jogar.html", "reconectar")
def reconectar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Reconectar Controles": os jogadores voltam, e a numeração se ajeita.

    O nome é do usuário e novo; o gesto não (a legenda registra *"'Reconciliar jogadores' virou
    'Reconectar Controles'"*; o botão antigo é `home_actions._on_home_reconciliar_clicked`, os
    mesmos dois passos encadeados). **Não é o `Connect` do BlueZ**, decisão de produto e contrato de
    `integrations/gesto_de_reconexao.py` (o botão PS é do usuário): o que volta é o JOGADOR, não o
    rádio.

    * Passo 1, `coop.sync`: ciclo FORÇADO de reconciliação (`CoopManager.sync(force=True)`), o único
    caminho capaz de trazer o jogador cujo grab foi recusado ou cujo vpad morreu sem `/dev/input`
    mudar (o ciclo normal só reenumera quando `/dev/input` muda; `ipc_handlers.py`). * Passo 2,
    `identity.renumber`: compacta a numeração preservando a ordem relativa. **A ordem é a entrega**
    (`home_actions.py`): *"renumerar antes de reconciliar compactaria uma mesa que ainda não está
    completa."* A recusa do segundo não é erro: com jogo aberto o daemon recusa renumerar (repintar
    o LED do controle em uso é o defeito que a NUMA-03 fechou) e os jogadores já voltaram no passo
    1; tratar como falha seria a interface mentindo (regra do `reported_step_index`). Por isso o
    segundo passo vai sem levantar.

    **Deixou de responder calado (JOGAR-OS-SEIS-AVISOS-01, 06/09/2026):** as duas linhas eram
    `p.chamar(…)`, que devolve um `bool` que ninguém lia, e clicar com o serviço fora do ar ou vivo
    produzia a mesma tela. A antiga tem QUATRO desfechos nomeados no gesto e nenhum chegava aqui.
    `resultado` e não `chamar_detalhado`, pelo CORPO: `chamar_detalhado` devolve ``(ok, motivo)`` e
    joga o corpo fora, e o passo 2 precisa dele porque a recusa por jogo aberto chega DENTRO de
    resposta bem-sucedida (``{ok: false, reason: "sessao_de_jogo_aberta"}``). Nota de 24/09/2026: a
    numeração que deu certo deixou de ter frase (`D-2409-O-RECONECTAR-NAO-DIZ-NADA`) e o
    ``renumbered`` não é mais lido (`painel.recibo_do_reconectar`).

    **A falha do passo 1 LEVANTA; a do passo 2, não.** O `coop.sync` responde *"meus jogadores
    voltaram?"* e sem ele não há gesto (vira `RuntimeError`, o canal da recusa laranja); o
    `identity.renumber` é acabamento e, sem resposta, o recibo diz que a numeração não foi conferida
    (`painel._NAO_CONFERIU`) e os jogadores seguem de pé. O `except Exception` LARGO nos dois é de
    propósito: `ponte.resultado` levanta `RuntimeError` sem daemon, mas o `_safe_call` por baixo
    **propaga** `ValueError`/`TypeError` de bug interno de propósito (`app/ipc_bridge.py`);
    deixá-los subir mataria o gesto sem palavra na tela.
    """
    voltaram, esperam_o_ps = _o_radio_de_volta(ctx)
    from . import perfil

    try:
        sync, renumerou = perfil.os_jogadores_de_volta(p)
    except Exception as erro:
        raise RuntimeError(_painel().RECONECTAR_SEM_SERVICO) from erro
    jogadores = sync.get("players") if isinstance(sync, dict) else None
    recibo = _painel().recibo_do_reconectar(jogadores, renumerou)
    do_radio = _painel().recado_do_radio(voltaram, esperam_o_ps)
    junto = " ".join(parte for parte in (do_radio, recibo) if parte)
    return {"recado": junto} if junto else None


OS_DOIS_DA_LISTA_DOS_DEZESSEIS: dict[str, str] = {
    "hefesto": (
        "aplicou e não havia o que mudar: a prova clica a posição Ligado e o "
        "daemon já estava em `gamepad` (`native_mode false`, "
        "`gamepad_emulation.enabled true`). Os dois IPCs são idempotentes."
    ),
    "reconectar": (
        "aplicou e não havia o que mudar: `coop.sync` reconcilia uma lista já "
        "reconciliada e `identity.renumber` compacta uma numeração já compacta. "
        "Os dois ecoam em `coop` e em `controllers[].player` quando há o que fazer."
    ),
}

PONTE = {"chamar", "chamar_detalhado", "freestyle_set", "resultado"}
METODOS_DA_TROCA_DE_MODO = {
    "native.mode.set",
    "gamepad.emulation.set",
    "coop.sync",
    "identity.renumber",
}
METODOS = METODOS_DA_TROCA_DE_MODO | {
    "desktop.arranjo.apply",
    "launch_env.refresh",
}


PAGINA = "01-jogar.html"
PISO_DA_ABA = 7

_MANUAL_ON = {"enabled": True, "origin": "manual"}
_MANUAL_OFF = {"enabled": False, "origin": "manual"}

PROVAS = [
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "gamepad"},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_ON)]},
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "native"},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_ON)]},
    {"pagina": PAGINA, "gesto": "modo-dualsense", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "caminho": "dualsense"})]},
    {"pagina": PAGINA, "gesto": "modo-xbox", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "caminho": "xbox"})]},
    {"pagina": PAGINA, "gesto": "modo-navegacao", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_OFF),
               ("chamar", ["desktop.arranjo.apply"],
                {"origin": "manual", "arranjo": "navegacao"})]},
    {"pagina": PAGINA, "gesto": "reconectar", "clique": {},  # (noqa-acento)
     "chama": [("resultado", ["coop.sync"], {}),
               ("resultado", ["identity.renumber"], {})]},
    {"pagina": PAGINA,  # (noqa-acento)
     "gesto": "cadeado", "clique": {"evento": "click"},
     "chama": [("freestyle_set", [], {"ligado": True})]},
]
