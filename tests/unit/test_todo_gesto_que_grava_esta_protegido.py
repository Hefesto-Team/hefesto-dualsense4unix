#!/usr/bin/env python3
"""Todo gesto que ESCREVE no disco dela está em `hefesto_vivo.PERIGOSOS`.

A LISTA FICOU PARA TRÁS DE UMA CURA TRÊS VEZES EM 03/09/2026, e a terceira foi
achada por um CONFERENTE ADVERSÁRIO — não por esta casa:

1. `rodape.salvar` — a lista tinha sido montada sobre a frase *"é o único gesto
   desta leva que escreve"*, e a frase era falsa: `a03_gatilhos.guardar` também
   gravava. A régua anunciou `pulados: salvar` e deixou para trás um
   `profile_salvo arquivo=meu_perfil.json`;
2. `08-conexoes.ignorar` — o ⊘ dispensava uma ORDEM DE SERVIÇO dela a cada
   volta, e o Check-up dela perdia uma das duas linhas que acusam nesta máquina;
3. `editor.prioridade` e `editor.estilo` — ensinados a gravar na leva das nove
   pendências, e não acrescentados aqui no mesmo commit. O conferente rodou a
   régua contra a lista real e imprimiu o que ela FARIA:

       SERÃO CLICADOS (8): … editor.estilo … editor.prioridade
       PULADOS        (9): novo remover editor.nome … salvar

**O ESTRAGO É REAL E É NA MÁQUINA DELA.** A régua de clique roda com o daemon
vivo e o perfil dela em disco: um gesto que grava e não está aqui faz o produto
escolher o estilo de jogo dela, mudar a prioridade de um perfil ou dispensar um
achado do Check-up — para provar que sabe clicar.

O QUE ESTA RÉGUA MEDE, e por que ela não é uma quarta lista
------------------------------------------------------------
Ela LÊ o fonte de cada gesto registrado e pergunta se ele chama alguma coisa que
grava (``save_profile``, ``gravar_e_reaplicar``, ``machine.declare``…). Os nomes
que ela procura são poucos e vêm do produto — não uma lista de gestos, que
envelheceria igual.

**A conta é por ÁRVORE, não por texto:** procurar `save_profile` no fonte casaria
a docstring de quem só o MENCIONA — e é a forma que esta casa mais paga.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

#: O QUE CONTA COMO ESCRITA. Cada nome é uma porta para o disco dela ou para o
#: aparelho de um jeito que persiste. Vindos do produto, não inventados.
ESCREVEM = {
    "save_profile",            # grava o perfil em disco
    "gravar_e_reaplicar",      # grava E manda o perfil inteiro ao daemon
    "_gravar",                 # o helper das abas que grava a seção
    "_gravar_a_forca",         # idem, na Vibração
    "salvar_perfil",
    "machine_declare",         # grava `MesaDeclarada` no `maquina.json`
    "set_mask",                # grava a máscara daquele aparelho
    "clear_mask",
    # ACRESCENTADA EM 04/09/2026, e a razão é o buraco que ela deixou aberto:
    # a frente da aba 01 pôs na tela o cadeado do `autoswitch`, cujo gesto
    # grava no disco DELA a preferência de não trocar de perfil sozinho — e
    # esta régua NÃO O ACUSOU, porque a porta não estava na lista. O gesto
    # irmão da aba 04 (que usa `gravar_e_reaplicar`) foi acusado no mesmo dia.
    #
    # A LIÇÃO, e vale para a próxima porta: uma régua com lista incompleta
    # protege o que alguém já lembrou, e chama isso de cobertura. Quem ensinar
    # um gesto a escrever acrescenta a porta AQUI no mesmo commit.
    "autoswitch_lock_set",     # grava a trava da troca automática
    "save_autoswitch_locked",  # o escritor por baixo dela
}

#: E O QUE CHEGA LÁ POR IPC, pelo nome do método. `p.chamar("machine.declare")`
#: não aparece como chamada de função com esse nome.
METODOS_QUE_ESCREVEM = {
    "machine.declare",
    "gamepad.mask.set",
    "profile.save",
    "autoswitch.lock",         # 04/09/2026 — ver a nota em `ESCREVEM`
}


#: AS ISENÇÕES, e cada uma carrega a MEDIÇÃO que a sustenta.
#:
#: Um gesto que "escreve" mas grava EXATAMENTE o que já estava no disco não faz
#: estrago nenhum quando a régua de clique o aciona — e protegê-lo custaria
#: cobertura: a régua deixaria de provar que aquele botão responde.
#:
#: A MEDIÇÃO É DE 03/09/2026, e está no `hefesto_vivo`: *"os outros clicam o
#: valor que a PÁGINA mostra, e a página mostra o que a declaração já dizia —
#: re-declarar é idempotente. `sala-altura`, `sala-visada` e `mic-existe`
#: gravaram exatamente o que já estava lá, e o ÚNICO campo que mudou no arquivo
#: foi `ordens_dispensadas`"* — que é o ⊘, e ele ESTÁ protegido.
#:
#: **A ISENÇÃO É DO PAR, NUNCA DA PORTA.** Isentar `machine_declare` inteiro
#: deixaria o ⊘ passar no dia em que alguém o renomeasse. Cada linha aqui é um
#: gesto nomeado, com a razão do lado.
ISENTOS: dict[tuple[str, str], str] = {
    ("02-controles.html", "mic-modo"):
        "`machine.declare` idempotente: grava o valor que a própria página "
        "mostra, medido em 03/09/2026",
    ("08-conexoes.html", "mic-existe"):
        "idem — foi um dos três medidos por nome naquela volta",
    ("09-sistema.html", "perfil-da-mesa"):
        "idem: o clique manda o valor que a tela já exibe",
}


def _gestos_registrados():
    """O registro do produto, chaveado por (página, nome) — nunca digitado."""
    from hefesto_dualsense4unix.interface import pacotes

    return dict(pacotes.GESTOS)


def _escreve(fn) -> str:
    """O nome da porta de escrita que este gesto usa, ou `""`.

    LÊ A ÁRVORE. Um `grep` por `save_profile` casaria a docstring de quem apenas
    explica por que NÃO grava — e marcaria como perigoso um gesto inócuo, que é
    o erro na direção oposta e igualmente caro: a régua de clique deixaria de
    cobrir um botão que precisa ser coberto.
    """
    try:
        arvore = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, SyntaxError):  # pragma: no cover - defesa
        return ""
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        nome = (no.func.id if isinstance(no.func, ast.Name)
                else no.func.attr if isinstance(no.func, ast.Attribute) else "")
        if nome in ESCREVEM:
            return nome
        # `p.chamar("machine.declare", …)` — o método vai no primeiro argumento
        if nome in ("chamar", "chamar_detalhado") and no.args:
            alvo = no.args[0]
            if isinstance(alvo, ast.Constant) and alvo.value in METODOS_QUE_ESCREVEM:
                return str(alvo.value)
    return ""


def test_todo_gesto_que_escreve_esta_na_lista() -> None:
    """A régua inteira, e ela é a que faltava nas três vezes."""
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    perigosos = set(PERIGOSOS)
    desprotegidos = []
    for (pagina, nome), fn in sorted(_gestos_registrados().items()):
        porta = _escreve(fn)
        if not porta:
            continue
        if (pagina, nome) in perigosos or ("*", nome) in perigosos:
            continue
        if (pagina, nome) in ISENTOS:
            continue
        desprotegidos.append(f"{pagina}·{nome} (escreve por `{porta}`)")

    assert not desprotegidos, (
        "gesto(s) que ESCREVEM e a régua de clique vai acionar sozinha:\n  "
        + "\n  ".join(desprotegidos)
        + "\n\nAcrescente cada um a `hefesto_vivo.PERIGOSOS`, NO MESMO COMMIT "
          "que o ensinou a gravar. Sem isso, a próxima volta da régua escreve "
          "no perfil dela para provar que sabe clicar.")


def test_a_regua_acha_alguma_escrita() -> None:
    """Guarda de vacuidade: se ela não achar NENHUM gesto que escreve, morreu.

    Bastaria alguém renomear `save_profile` para o teste acima ficar verde para
    sempre sobre um produto que grava em toda parte.
    """
    achados = {f"{p}·{n}": _escreve(fn)
               for (p, n), fn in _gestos_registrados().items() if _escreve(fn)}
    assert len(achados) >= 3, (
        f"a régua só achou {len(achados)} gesto(s) que escrevem — os nomes de "
        f"`ESCREVEM` provavelmente mudaram no produto: {achados}")


def test_a_lista_nao_protege_gesto_que_nao_existe() -> None:
    """E o outro lado: um nome errado em `PERIGOSOS` protege NADA.

    Um `("10-perfis.html", "editor.prioridad")` com um erro de digitação
    pareceria proteger e não protegeria — e ninguém notaria, porque a lista só
    é lida para PULAR.
    """
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    registrados = set(_gestos_registrados())
    fantasmas = [
        f"{p}·{n}" for (p, n) in PERIGOSOS
        if p != "*" and (p, n) not in registrados
    ]
    assert not fantasmas, (
        "entrada(s) de `PERIGOSOS` que não casam gesto nenhum — protegem "
        f"nada:\n  {fantasmas}")


@pytest.mark.parametrize("nome", ["editor.prioridade", "editor.estilo"])
def test_os_dois_da_leva_das_nove_estao_protegidos(nome: str) -> None:
    """Os dois que o conferente pegou, nomeados — para a regressão ter nome."""
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    assert ("10-perfis.html", nome) in set(PERIGOSOS), (
        f"`{nome}` saiu de PERIGOSOS. Ele grava no perfil dela desde a leva "
        "das nove pendências de 03/09/2026.")


def test_toda_isencao_aponta_um_gesto_e_tem_razao() -> None:
    """Isenção sem razão é ponto cego com nome bonito.

    E isenção que aponta um gesto que não existe é pior: ela parece cobrir um
    caso e não cobre nada — o mesmo defeito que a entrada
    `09-sistema·restaurar-de-fabrica` teve em `PERIGOSOS`, protegendo NADA
    enquanto o gesto se chamava `refazer-proton`.
    """
    registrados = set(_gestos_registrados())
    fantasmas = [f"{p}·{n}" for (p, n) in ISENTOS if (p, n) not in registrados]
    assert not fantasmas, f"isenção(ões) para gesto inexistente: {fantasmas}"

    sem_razao = [f"{p}·{n}" for (p, n), r in ISENTOS.items() if len(r.strip()) < 30]
    assert not sem_razao, (
        f"isenção(ões) sem razão medida: {sem_razao}. Escreva o que foi medido "
        "e quando — quem ler daqui a um mês precisa poder conferir.")


def test_a_isencao_nao_alcanca_o_que_grava_valor_novo() -> None:
    """A lista de isentos não pode crescer para dentro do perigo.

    O ⊘ da Conexões é o caso que prova: ele CHAMA `machine.declare`, como os
    três isentos, e grava algo que a página NÃO mostra — o resultado do EXAME.
    Se alguém isentar a porta em vez do par, ele passa.
    """
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    assert ("08-conexoes.html", "ignorar") not in ISENTOS, (
        "o ⊘ da Conexões foi isentado: ele dispensa uma ORDEM DE SERVIÇO dela, "
        "e o Check-up perde a linha para sempre — `ordens_da_mesa.ordens_novas` "
        "só a devolve se os cabos mudarem")
    assert ("08-conexoes.html", "ignorar") in set(PERIGOSOS), (
        "o ⊘ saiu de PERIGOSOS — foi o defeito medido em 03/09/2026")
