#!/usr/bin/env python3
"""Todo gesto que MEXE na máquina dela declara isso — e a árvore confere.

A LISTA FICOU PARA TRÁS DE UMA CURA QUATRO VEZES, e a quarta foi maior que as
três primeiras:

1. `rodape.salvar` — a lista tinha sido montada sobre a frase *"é o único gesto
   desta leva que escreve"*, e a frase era falsa: `a03_gatilhos.guardar` também
   gravava. A régua anunciou `pulados: salvar` e deixou para trás um
   `profile_salvo arquivo=meu_perfil.json`;
2. `08-conexoes.ignorar` — o ⊘ dispensava uma ORDEM DE SERVIÇO dela a cada
   volta, e o Check-up dela perdia uma das duas linhas que acusam nesta máquina;
3. `editor.prioridade` e `editor.estilo` — ensinados a gravar na leva das nove
   pendências, e não acrescentados aqui no mesmo commit;
4. **a ABA 07 INTEIRA** — achado pela `STEAM-INPUT-01` em 06/09/2026. Não era
   uma porta esquecida: eram OITO, e nenhuma estava em `ESCREVEM`. A régua deu
   verde sobre `tirar-daqui`, `voltar-a-usar`, `nao-perguntar`,
   `voltar-a-perguntar`, `consertar`, `consertar-fechando-a-steam`,
   `este-jogo-nao-funciona` e `deixar-tudo-pronto` — o último reescreve a linha
   de lançamento de TODOS os jogos dela.

**O ESTRAGO É REAL E É NA MÁQUINA DELA.** A régua de clique roda com o daemon
vivo e o perfil dela em disco: um gesto que grava e não está protegido faz o
produto escolher o estilo de jogo dela, mudar a prioridade de um perfil, marcar
um jogo dela ou dispensar um achado do Check-up — para provar que sabe clicar.

O QUE MUDOU EM 06/09/2026 (`ONDA3-GESTO-DECLARA-01`)
-----------------------------------------------------
`hefesto_vivo.PERIGOSOS` **deixou de ser digitada**: cada gesto declara no
próprio decorador o que muda — `@gesto(…, grava="save_profile")` — e a lista é
`pacotes.perigosos()`. Quem escreve o gesto passou a poder fechar o próprio
contrato, que era a raiz das quatro repetições: as duas linhas moravam em
arquivos que a sprint da aba tinha no `nao_toca`.

**E ESTA RÉGUA MUDOU DE PAPEL.** Ela não é mais a lista — é o CONFERENTE, e
cobra as DUAS direções:

* **grava e não declarou** → reprova nomeando. É o buraco que a derivação
  sozinha NÃO fecha: quem esquece a linha também esquece o `grava=`. A árvore é
  a segunda fonte, e ela é independente de propósito;
* **declarou e a árvore não acha** → reprova também. Sem isso a declaração vira
  ruído e a régua de clique perde cobertura de graça — um botão protegido é um
  botão que ninguém prova.

O QUE ELA MEDE, e por que a lista de PORTAS continua escrita à mão
------------------------------------------------------------------
Ela LÊ o fonte de cada gesto registrado e pergunta se ele chama alguma coisa
que grava (``save_profile``, ``gravar_e_reaplicar``, ``machine.declare``…).

**A conta é por ÁRVORE, não por texto:** procurar `save_profile` no fonte
casaria a docstring de quem só o MENCIONA — e é a forma que esta casa mais paga.

**E DERIVAR `ESCREVEM` DAS FOLHAS FOI MEDIDO E RECUSADO** — 06/09/2026, duas
voltas. A ideia era seguir as chamadas ATRAVÉS dos módulos até primitivas de
persistência (`write_text`, `open(…,"w")`, `unlink`) e assim nunca mais precisar
lembrar de um nome. As duas voltas saíram falsas nas duas direções:

* com `mkdir` entre as folhas, **47 de 105 gestos** acusam — quase todos por
  `utils.xdg_paths.*_dir → mkdir`, que é a porta de toda LEITURA de configuração;
* sem ele, sobram 28 — e agora **faltam 24** que esta régua já pegava
  (`05-vibracao·forca`, `08-conexoes·ignorar`, `06-navegacao·vel-cursor`…),
  enquanto `10-perfis·recarregar` e `*·aplicar` continuam acusados por
  `profiles.loader.migrate_default_profile_name`, que roda na LEITURA.

O caminho até o disco passa, em quase todo gesto, por algo que garante a pasta
ou migra o nome do perfil ao ler. Separar leitura de escrita ali exigiria
interpretar argumentos e ramos — escrever um interpretador, que é a linha que o
teto de `_FUNDO` já recusa a cruzar. **Os nomes ficam escritos, e a régua que os
cobra é a de cima: um nome que falte aparece como gesto SEM declaração.**
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

#: O QUE CONTA COMO ESCRITA. Cada nome é uma porta para o disco dela, para a
#: máquina ou para o aparelho de um jeito que persiste. Vindos do produto, não
#: inventados.
#:
#: NÃO É "grava no disco", é **"muda algo dela que ela não mandou mudar"** — o
#: `set_text` (a área de transferência) está aqui pela mesma razão que o
#: `save_profile`. A quarta repetição foi o que autorizou a generalização; as
#: três primeiras ainda podiam passar por azar.
ESCREVEM = {
    "save_profile",            # grava o perfil em disco
    "gravar_e_reaplicar",      # grava E manda o perfil inteiro ao daemon
    "_gravar",                 # o helper das abas que grava a seção
    "_gravar_a_forca",         # idem, na Vibração
    "_gravar_so_o_gatilho",    # grava o perfil dela SEM reaplicá-lo
    # A SEÇÃO `mode` DO PERFIL ATIVO, escrita de FORA da aba Perfis —
    # JOGAR-O-QUE-FALTA-01, 06/09/2026. O interruptor e os chips da aba Jogar
    # passaram a levar a escolha dela para o `.json`, pelo dono compartilhado
    # (`interface/pacotes/perfil.gravar_o_modo_no_ativo`). Sem este nome aqui, a
    # régua de clique trocaria o que ATIVAR o perfil dela liga — quatro botões,
    # numa aba que ela deixa aberta — para provar que sabe clicar.
    "gravar_o_modo_no_ativo",
    "salvar_perfil",
    "machine_declare",         # grava `MesaDeclarada` no `maquina.json`
    "set_mask",                # grava a máscara daquele aparelho
    "clear_mask",
    "autoswitch_lock_set",     # grava a trava da troca automática
    "save_autoswitch_locked",  # o escritor por baixo dela
    "renomear_o_dongle",       # grava o alias do adaptador no BlueZ
    "rumble_motores_set",      # grava a barra de cada motor no perfil dela
    "rumble_policy_set_checked",  # muda o degrau de vibração de TODOS, ao vivo
    "set_text",                # `Gtk.Clipboard.set_text` — a área dela
    # AS OITO DA ABA 07 — a quarta repetição, e a maior. Achadas pela
    # `STEAM-INPUT-01` em 06/09/2026: a régua estava cega para a aba INTEIRA,
    # e por isso deu verde sobre dois gestos que a própria frente tinha
    # escrito naquele dia.
    "marcar_jogo_sem_wrapper",     # escreve o `jogos_sem_wrapper.txt` dela
    "desmarcar_jogo_sem_wrapper",  # o par de volta, e escreve o mesmo arquivo
    "add_dismissed_appid",         # escreve o `launch_dialog_dismissed.json`
    "remove_dismissed_appid",      # idem, na volta
    "reparar_ou_adiar",            # REESCREVE a linha de lançamento no vdf da Steam
    "add_appid_to_steam_input_allowlist",  # marca um jogo dela como exceção
    "apply_wrapper_to_all_games",  # a linha de lançamento de TODOS os jogos dela
    "with_steam_closed",           # FECHA a Steam dela (escala para `pkill -KILL`)
    # E MAIS QUATRO, que apareceram ao declarar `grava=` gesto a gesto. A
    # cegueira era mais larga que o relato dizia — quatro portas fora da aba 07
    # também não estavam aqui, e os seis gestos delas só estavam protegidos
    # porque alguém tinha escrito a linha à mão em `PERIGOSOS`. No dia em que a
    # linha caísse, nada acusaria.
    "delete_profile",          # apaga um perfil dela do disco
    "restaurar_do_historico",  # troca o perfil pelo backup de ontem
    "_systemctl",              # liga, para e reinicia o serviço na máquina dela
    "curar_todos",             # tira ou devolve as camadas Vulkan dos prefixos dela

    # A CURA POR ESTRADA — 09/09/2026, `LANCADORES-ZERO-01`. Ela escreve
    # arquivo de OUTRO programa: o `config.json` do Heroic e o override do
    # Flatpak dos demais lançadores. O gesto declarou `grava=` no mesmo commit
    # que nasceu, e a DIREÇÃO B desta régua reprovou porque o nome não estava
    # aqui: *"declara `grava='escrever_a_estrada'` e a árvore acha NADA"*. É a
    # metade que falta de toda declaração — a porta declarada tem de ser uma
    # porta que esta lista conhece.
    "escrever_a_estrada",      # escreve o ambiente na configuração do lançador
}

#: E O QUE CHEGA LÁ POR IPC, pelo nome do método. `p.chamar("machine.declare")`
#: não aparece como chamada de função com esse nome.
METODOS_QUE_ESCREVEM = {
    "machine.declare",
    "gamepad.mask.set",
    "profile.save",
    "autoswitch.lock",
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
    ("08-conexoes.html", "sala-altura"):
        "`machine.declare` idempotente: um dos TRÊS medidos por nome em "
        "03/09/2026, e a medição está citada acima",
    ("08-conexoes.html", "sala-visada"):
        "idem — o segundo dos três daquela volta",
    ("09-sistema.html", "perfil-da-mesa"):
        "idem: o clique manda o valor que a tela já exibe",
}


#: OS PERIGOS QUE A ÁRVORE NÃO TEM COMO VER — e por isso a declaração deles é
#: uma FRASE, não o nome de uma porta.
#:
#: A DIREÇÃO B DESTA RÉGUA (*"declarou e a árvore não acha"*) reprovaria os
#: quatro, e reprovar estaria errado: eles mexem na máquina dela por caminhos
#: que uma leitura de árvore não alcança — um `getattr`, um `subprocess` com o
#: script montado em variável, o cursor que anda na tela, uma janela que nasce
#: por cima do trabalho dela.
#:
#: **É O MESMO CONTRATO DO `ISENTOS`: a assinatura é do PAR, com a razão do
#: lado.** Um "declarou por frase" solto seria a porta por onde qualquer gesto
#: escaparia da conferência — bastaria escrever uma frase em vez do nome.
FORA_DA_ARVORE: dict[tuple[str, str], str] = {
    ("01-jogar.html", "modo-navegacao"):
        "liga o mouse emulado pela preferência persistida (`mouse.emulation."
        "restore`); o perigo é o CURSOR andando na tela dela, e cursor não é "
        "chamada de função. Desde 06/09/2026 ele também GRAVA (a seção `mode` "
        "do perfil ativo, por `gravar_o_modo_no_ativo`) — a árvore acharia essa "
        "porta, e a declaração continua por frase porque o cursor é o perigo "
        "MAIOR e o único que só a frase alcança",
    ("07-lancadores.html", "abrir-lancador"):
        "`reopen_steam` abre a janela da Steam DESANEXADA: ela não nasce oculta "
        "e não some quando a prova termina. Decisão 17 dela, 03/09/2026 — o "
        "botão liga *e* o gesto entra na lista, e as duas metades são uma só",
    ("09-sistema.html", "refazer-consertos"):
        "roda os scripts de `CONSERTOS` por `subprocess.run([\"bash\", "
        "str(caminho), …])`, com o caminho montado em variável — a árvore vê um "
        "`run`, que é genérico demais para virar porta sem encher de falso",
    ("09-sistema.html", "refazer-proton"):
        "chama `travar()`, que é um `getattr(pin, \"lock_proton_for_all_games\")` "
        "— o nome não está no fonte como chamada, e trava o Proton de TODOS os "
        "jogos dela",
}


def _gestos_registrados():
    """O registro do produto, chaveado por (página, nome) — nunca digitado."""
    from hefesto_dualsense4unix.interface import pacotes

    return dict(pacotes.GESTOS)


def _declaracoes():
    """O que cada gesto DECLAROU com `grava=` — a fonte de `PERIGOSOS`."""
    from hefesto_dualsense4unix.interface import pacotes

    return dict(pacotes.GESTOS_QUE_MEXEM)


#: Quantos ajudantes de profundidade a régua segue. DOIS basta para todo caso
#: medido nas dez abas, e um teto existe para a régua não virar um interpretador.
_FUNDO = 2


def _portas(fn, _visto: frozenset[str] = frozenset(),
            _fundo: int = _FUNDO) -> set[str]:
    """TODAS as portas de escrita que este gesto alcança, ou um conjunto vazio.

    LÊ A ÁRVORE. Um `grep` por `save_profile` casaria a docstring de quem apenas
    explica por que NÃO grava — e marcaria como perigoso um gesto inócuo, que é
    o erro na direção oposta e igualmente caro: a régua de clique deixaria de
    cobrir um botão que precisa ser coberto.

    E ELA DESCE PELOS AJUDANTES DO PRÓPRIO MÓDULO — acrescentado em 04/09/2026,
    e a razão é um defeito vivo que ela deixou passar. O gesto
    `08-conexoes·renomear-adaptador` grava o alias no BlueZ, e esta régua deu
    VERDE sobre ele: o corpo do gesto chama `_gravar_o_apelido(...)`, um
    ajudante do mesmo arquivo, e é o AJUDANTE que chama `renomear_o_dongle`.
    Ler um nível só é ler o que o autor teve a gentileza de deixar na
    superfície.

    **DEVOLVE UM CONJUNTO, e não a primeira porta que achar** — 06/09/2026. A
    direção B cobra que a porta DECLARADA esteja na árvore; com "a primeira",
    um gesto que passa por duas portas reprovaria por declarar a outra, e a
    régua ensinaria a declarar o que ela quer ouvir em vez do que o código faz.
    """
    try:
        fonte = inspect.getsource(fn)
        arvore = ast.parse(textwrap.dedent(fonte))
    except (OSError, SyntaxError, TypeError):  # pragma: no cover - defesa
        return set()

    modulo = inspect.getmodule(fn)
    achadas: set[str] = set()
    a_descer: list[str] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        nome = (no.func.id if isinstance(no.func, ast.Name)
                else no.func.attr if isinstance(no.func, ast.Attribute) else "")
        if nome in ESCREVEM:
            achadas.add(nome)
            continue
        # `p.chamar("machine.declare", …)` — o método vai no primeiro argumento
        if nome in ("chamar", "chamar_detalhado") and no.args:
            alvo = no.args[0]
            if isinstance(alvo, ast.Constant) and alvo.value in METODOS_QUE_ESCREVEM:
                achadas.add(str(alvo.value))
                continue
        # UM AJUDANTE DO MESMO MÓDULO, chamado pelo nome.
        if (
            _fundo > 0
            and isinstance(no.func, ast.Name)
            and nome not in _visto
            and modulo is not None
            and callable(getattr(modulo, nome, None))
        ):
            a_descer.append(nome)

    visto = _visto | {getattr(fn, "__name__", "")} | set(a_descer)
    for nome in a_descer:
        achadas |= _portas(getattr(modulo, nome), visto, _fundo - 1)
    return achadas


def _escreve(fn) -> str:
    """Uma porta, para a mensagem de erro. `""` quando a árvore não acha nada."""
    achadas = _portas(fn)
    return sorted(achadas)[0] if achadas else ""


def test_todo_gesto_que_escreve_declara_grava() -> None:
    """DIREÇÃO A — a que faltou quatro vezes: grava e não declarou.

    É o buraco que a derivação sozinha NÃO fecha. Se `PERIGOSOS` sai só do que
    o autor escreveu, o autor que esquecia a linha passa a esquecer o `grava=`,
    e nada acusa. A árvore é a segunda fonte.
    """
    declarados = _declaracoes()
    desprotegidos = []
    for (pagina, nome), fn in sorted(_gestos_registrados().items()):
        portas = _portas(fn)
        if not portas or (pagina, nome) in declarados:
            continue
        if (pagina, nome) in ISENTOS:
            continue
        desprotegidos.append(
            f"{pagina}·{nome} (escreve por `{sorted(portas)[0]}`)")

    assert not desprotegidos, (
        "gesto(s) que ESCREVEM e a régua de clique vai acionar sozinha:\n  "
        + "\n  ".join(desprotegidos)
        + "\n\nDeclare a porta no PRÓPRIO decorador — `@gesto(…, "
          'grava="save_profile")` —, NO MESMO COMMIT que o ensinou a gravar. '
          "Sem isso, a próxima volta da régua escreve no perfil dela para "
          "provar que sabe clicar.")


def test_toda_declaracao_a_arvore_confirma() -> None:
    """DIREÇÃO B — declarou e a árvore não acha.

    Sem ela a declaração vira ruído: qualquer gesto entra em `PERIGOSOS`
    escrevendo uma palavra, a régua de clique para de acioná-lo, e ninguém
    prova mais que aquele botão responde. Cobertura perdida de graça.

    E ela pega o caso mais provável de todos: a declaração que ENVELHECEU. O
    gesto deixou de chamar a porta, ou ela mudou de nome, e o `grava=` continua
    apontando para um nome que não existe mais — do mesmo jeito que
    `restaurar-de-fabrica` apontava para um gesto que nunca existiu.
    """
    registrados = _gestos_registrados()
    mentiras = []
    for (pagina, nome), declarado in sorted(_declaracoes().items()):
        fn = registrados.get((pagina, nome))
        assert fn is not None, (
            f"declaração de gesto inexistente: {pagina}·{nome} — impossível "
            "pelo decorador, logo alguém escreveu em `GESTOS_QUE_MEXEM` à mão")
        if " " in declarado:                       # é frase, não porta
            if (pagina, nome) not in FORA_DA_ARVORE:
                mentiras.append(
                    f"{pagina}·{nome} declarou por FRASE ({declarado!r}) e não "
                    "está em `FORA_DA_ARVORE`")
            continue
        portas = _portas(fn)
        if declarado not in portas:
            mentiras.append(
                f"{pagina}·{nome} declara `grava={declarado!r}` e a árvore acha "
                f"{sorted(portas) or 'NADA'}")

    assert not mentiras, (
        "declaração(ões) que a árvore não confirma:\n  " + "\n  ".join(mentiras)
        + "\n\nOu o gesto deixou de gravar (tire o `grava=` e devolva a "
          "cobertura), ou a porta mudou de nome (acerte o `grava=` e, se o "
          "nome for novo, acrescente-o a `ESCREVEM`), ou o perigo não é uma "
          "chamada (declare por frase e assine em `FORA_DA_ARVORE`).")


def test_a_regua_acha_alguma_escrita() -> None:
    """Guarda de vacuidade: se ela não achar NENHUM gesto que escreve, morreu.

    Bastaria alguém renomear `save_profile` para os testes acima ficarem verdes
    para sempre sobre um produto que grava em toda parte.
    """
    achados = {f"{p}·{n}": sorted(_portas(fn))
               for (p, n), fn in _gestos_registrados().items() if _portas(fn)}
    assert len(achados) >= 3, (
        f"a régua só achou {len(achados)} gesto(s) que escrevem — os nomes de "
        f"`ESCREVEM` provavelmente mudaram no produto: {achados}")


def test_a_lista_nao_protege_gesto_que_nao_existe() -> None:
    """E o outro lado: um nome errado em `PERIGOSOS` protege NADA.

    Um `("10-perfis.html", "editor.prioridad")` com um erro de digitação
    pareceria proteger e não protegeria — e ninguém notaria, porque a lista só
    é lida para PULAR. Foi o que aconteceu com `("09-sistema.html",
    "restaurar-de-fabrica")`, que passou meses ali enquanto o gesto se chamava
    `refazer-proton`.

    DESDE 06/09/2026 O FANTASMA NÃO TEM COMO NASCER — a chave sai do registro,
    não de um literal. Este teste passou a medir isso: que `PERIGOSOS` continua
    DERIVADA. Alguém que volte a digitá-la reprova aqui.
    """
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    registrados = set(_gestos_registrados())
    fantasmas = [
        f"{p}·{n}" for (p, n) in PERIGOSOS
        if p != "*" and (p, n) not in registrados
    ]
    assert not fantasmas, (
        "entrada(s) de `PERIGOSOS` que não casam gesto nenhum — protegem "
        f"nada:\n  {fantasmas}")
    assert set(PERIGOSOS) == pacotes.perigosos(), (
        "`hefesto_vivo.PERIGOSOS` divergiu de `pacotes.perigosos()` — alguém "
        "voltou a digitar a lista, e a digitada é a que chega atrasada")


@pytest.mark.parametrize("nome", ["editor.prioridade", "editor.estilo"])
def test_os_dois_da_leva_das_nove_estao_protegidos(nome: str) -> None:
    """Os dois que o conferente pegou, nomeados — para a regressão ter nome."""
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    assert ("10-perfis.html", nome) in set(PERIGOSOS), (
        f"`{nome}` saiu de PERIGOSOS. Ele grava no perfil dela desde a leva "
        "das nove pendências de 03/09/2026.")


@pytest.mark.parametrize("nome", [
    "tirar-daqui", "voltar-a-usar", "nao-perguntar", "voltar-a-perguntar",
    "consertar", "consertar-fechando-a-steam", "este-jogo-nao-funciona",
    "deixar-tudo-pronto",
])
def test_as_oito_portas_da_aba_07_estao_protegidas(nome: str) -> None:
    """A quarta repetição, nomeada — para a regressão ter nome.

    A `STEAM-INPUT-01` mediu que a régua era cega para a aba INTEIRA. Os oito
    escrevem em arquivos DELA: `jogos_sem_wrapper.txt`,
    `launch_dialog_dismissed.json`, o `localconfig.vdf` da Steam e a lista de
    exceções do Steam Input. O `deixar-tudo-pronto` é o mais caro — ele reescreve
    a linha de lançamento de TODOS os jogos.
    """
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    assert ("07-lancadores.html", nome) in set(PERIGOSOS), (
        f"`{nome}` saiu de PERIGOSOS — é uma das OITO portas da aba 07 que a "
        "régua não enxergava até 06/09/2026.")


def test_toda_isencao_aponta_um_gesto_e_tem_razao() -> None:
    """Isenção sem razão é ponto cego com nome bonito.

    E isenção que aponta um gesto que não existe é pior: ela parece cobrir um
    caso e não cobre nada.
    """
    registrados = set(_gestos_registrados())
    declarados = _declaracoes()
    for tabela, rotulo in ((ISENTOS, "isenção"), (FORA_DA_ARVORE, "assinatura")):
        fantasmas = [f"{p}·{n}" for (p, n) in tabela if (p, n) not in registrados]
        assert not fantasmas, f"{rotulo}(ões) para gesto inexistente: {fantasmas}"

        sem_razao = [f"{p}·{n}" for (p, n), r in tabela.items()
                     if len(r.strip()) < 30]
        assert not sem_razao, (
            f"{rotulo}(ões) sem razão medida: {sem_razao}. Escreva o que foi "
            "medido e quando — quem ler daqui a um mês precisa poder conferir.")

    # E AS DUAS TABELAS NÃO PODEM SE CRUZAR: isento é "escreve e não faz mal";
    # assinado é "faz mal e a árvore não vê". Um par nos dois seria uma
    # contradição que a régua leria como isenção, calada.
    nos_dois = sorted(set(ISENTOS) & set(FORA_DA_ARVORE))
    assert not nos_dois, f"gesto(s) isentos E assinados ao mesmo tempo: {nos_dois}"
    isentos_declarados = sorted(p for p in ISENTOS if p in declarados)
    assert not isentos_declarados, (
        f"gesto(s) isentos que declaram `grava=`: {isentos_declarados}. A "
        "isenção existe para NÃO proteger; declarar protege. Escolha uma.")


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


def test_a_regua_desce_pelo_ajudante_do_mesmo_modulo() -> None:
    """A MORDIDA QUE FALTAVA — e ela existe porque a outra não pegou.

    Arrancar a descida (fazer `_portas` ler UM nível só, como era antes de
    04/09/2026) não derrubava régua nenhuma: as entradas a mais em `PERIGOSOS`
    passavam a ser apenas inúteis, e nada reclama de proteção sobrando. Ou
    seja, a cura podia ser desfeita em silêncio — que é a definição de cura sem
    régua.

    Aqui a profundidade é medida DIRETAMENTE, no caso que a revelou: o gesto
    `08-conexoes·renomear-adaptador` não chama `renomear_o_dongle`; ele chama
    `_gravar_o_apelido`, do mesmo arquivo, e é o ajudante que grava no BlueZ.
    """
    gestos = _gestos_registrados()
    fn = gestos[("08-conexoes.html", "renomear-adaptador")]

    assert "renomear_o_dongle" in _portas(fn), (
        "a régua parou de descer pelos ajudantes do módulo: ela voltou a ler "
        "só o corpo do gesto, e é assim que `renomear-adaptador` ficou "
        "desprotegido até 04/09/2026."
    )
    # E a superfície do próprio gesto NÃO tem a porta — é isso que torna o
    # caso uma prova de profundidade, e não uma coincidência.
    fonte = inspect.getsource(fn)
    assert "renomear_o_dongle" not in fonte.split('"""')[-1], (
        "o gesto passou a chamar a porta DIRETAMENTE; este caso deixou de "
        "provar a descida. Escolha outro gesto que grave por ajudante."
    )
