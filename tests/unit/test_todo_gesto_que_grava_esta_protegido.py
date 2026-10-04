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

ESCREVEM = {
    "save_profile",
    "gravar_e_reaplicar",
    "_gravar",
    "_gravar_a_forca",
    "_gravar_so_o_gatilho",
    "gravar_pelo_gesto",
    "so_neste_jogo",
    "voltar_ao_do_computador",
    "voltar_o_computador_ao_de_fabrica",
    "salvar_perfil",
    "machine_declare",
    "set_mask",
    "clear_mask",
    "freestyle_set",
    "save_freestyle_ligado",
    "dar_nome_ao_adaptador",
    "declarar_a_ligacao",
    "declarar_a_velocidade",
    "dar_nome_a_entrada",
    "trocar_as_entradas",
    "ensinar_a_entrada",
    "guardar_ordem_dos_adaptadores",
    "escrever_propriedade",
    "esquecer_o_pareamento",
    "responder",
    "nao_alcanco",
    "mic_canal_set_detalhado",
    "mira_set_detalhado",
    "rumble_motores_set",
    "rumble_policy_set_checked",
    "set_text",
    "marcar_jogo_sem_wrapper",     # escreve o `jogos_sem_wrapper.txt` dela
    "desmarcar_jogo_sem_wrapper",
    "add_dismissed_appid",
    "remove_dismissed_appid",
    "reparar_ou_adiar",
    "add_appid_to_steam_input_allowlist",
    "remove_appid_from_steam_input_allowlist",
    "garantir_ponte",                    # escreve `UseSteamControllerConfig=2`
    "garantir_fora_da_lista_desligado",
    "apply_wrapper_to_all_games",
    "with_steam_closed",
    "delete_profile",
    "restaurar_do_historico",
    "_systemctl",
    "curar_todos",
    "gravar_camadas_da_steam_fora",
    # por feature (`jogos_sem_wrapper.txt` e a de fora do pino). O
    # já declara `machine_declare` e continua protegido do mesmo jeito.
    "adicionar",
    "tirar",
    "tirar_do_disco",
    "criar_para_o_jogo",

    # `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`). No dia em que a
}

METODOS_QUE_ESCREVEM = {
    "machine.declare",
    "gamepad.mask.set",
    "profile.save",
    "freestyle.set",
    "radio.mover",
    "radio.ponte.ligar_aqui",
    "radio.busca.set",
    "radio.dispensar",
    "desktop.status.set",
}

_CHAMAM_O_METODO = ("chamar", "chamar_detalhado", "resultado")


#: foi `ordens_dispensadas`"* — que é o ⊘, e ele ESTÁ protegido.
#: **A ISENÇÃO É DO PAR, NUNCA DA PORTA.** Isentar `machine_declare` inteiro
ISENTOS: dict[tuple[str, str], str] = {
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


FORA_DA_ARVORE: dict[tuple[str, str], str] = {
    ("08-conexoes.html", "mapear-gravar"):
        "grava o nome e o lugar da porta da vez no `maquina.json` dela pelo "
        "`MapearAsPortas.gravar` do dono do mapa (`entrada_a_entrada.o_mapa()`, "
        "A-08-UM-MAPEAR-SO-01): é método de um objeto devolvido por função, e a "
        "árvore só desce por ajudante chamado pelo nome",
    ("01-jogar.html", "modo-navegacao"):
        "liga o mouse emulado pelo arranjo do perfil ativo (`desktop.arranjo."
        "apply`); o perigo é o CURSOR andando na tela dela, e cursor não é "
        "chamada de função. E ele GRAVA a seção `mode` do perfil ativo: desde "
        "29/09/2026 (O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01) quem grava é o daemon, "
        "pelo `desktop.arranjo.apply` à mão, e o método sai da tabela do plano "
        "(`_plano_do_chip`), onde a árvore não o vê pelo nome",
    # 29/09/2026. Até ali o interruptor e os chips «Sony DualSense» e «Xbox»
    ("01-jogar.html", "hefesto"):
        "grava a seção `mode` do perfil ativo pelo daemon: o `native.mode.set` "
        "e o `gamepad.emulation.set` à mão saem da tabela do plano "
        "(`_plano`/`plano_do_modo`), onde a árvore não os vê pelo nome",
    ("01-jogar.html", "modo-dualsense"):
        "grava o caminho na seção `mode` do perfil ativo pelo daemon: o "
        "`gamepad.emulation.set` à mão sai da tabela do plano "
        "(`_plano_do_chip`), onde a árvore não o vê pelo nome",
    ("01-jogar.html", "modo-xbox"):
        "grava o caminho `xbox` na seção `mode` do perfil ativo pelo daemon, "
        "pela mesma porta do «Sony DualSense», fora da vista da árvore",
    ("07-lancadores.html", "abrir-lancador"):
        "`reopen_steam` abre a janela da Steam DESANEXADA: ela não nasce oculta "
        "e não some quando a prova termina. Decisão 17 dela, 03/09/2026 — o "
        "botão liga *e* o gesto entra na lista, e as duas metades são uma só",
    ("09-sistema.html", "refazer-consertos"):
        "roda os scripts de `CONSERTOS` por `subprocess.run([\"bash\", "
        "str(caminho), …])`, com o caminho montado em variável — a árvore vê um "
        "`run`, que é genérico demais para virar porta sem encher de falso",
    ("09-sistema.html", "fixar-proton"):
        "chama `travar()`, que é um `getattr(pin, \"lock_proton_for_all_games\")`, "
        "e o destravar pelo mesmo `getattr` — o nome não está no fonte como "
        "chamada, e trava ou solta o Proton de TODOS os jogos dela",
    ("09-sistema.html", "copiar-registro"):
        "põe o texto na área de transferência DELA pelo `Gtk.Clipboard`, dentro "
        "de um `GLib.idle_add` — a chamada mora numa função aninhada, e o perigo "
        "é apagar o que ela tinha copiado, que nenhuma porta de disco nomeia",
}


def _gestos_registrados():
    """O registro do produto, chaveado por (página, nome) — nunca digitado."""
    from hefesto_dualsense4unix.interface import pacotes

    return dict(pacotes.GESTOS)


def _declaracoes():
    """O que cada gesto DECLAROU com `grava=` — a fonte de `PERIGOSOS`."""
    from hefesto_dualsense4unix.interface import pacotes

    return dict(pacotes.GESTOS_QUE_MEXEM)


_FUNDO = 2


def _portas(fn, _visto: frozenset[str] = frozenset(),
            _fundo: int = _FUNDO) -> set[str]:
    """TODAS as portas de escrita que este gesto alcança, ou um conjunto vazio."""
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
        if nome in _CHAMAM_O_METODO and no.args:
            alvo = no.args[0]
            if isinstance(alvo, ast.Constant) and alvo.value in METODOS_QUE_ESCREVEM:
                achadas.add(str(alvo.value))
                continue
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
    """DIREÇÃO A — a que faltou quatro vezes: grava e não declarou."""
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
    """DIREÇÃO B — declarou e a árvore não acha."""
    registrados = _gestos_registrados()
    mentiras = []
    for (pagina, nome), declarado in sorted(_declaracoes().items()):
        fn = registrados.get((pagina, nome))
        assert fn is not None, (
            f"declaração de gesto inexistente: {pagina}·{nome} — impossível "
            "pelo decorador, logo alguém escreveu em `GESTOS_QUE_MEXEM` à mão")
        if " " in declarado:
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
    """Guarda de vacuidade: se ela não achar NENHUM gesto que escreve, morreu."""
    achados = {f"{p}·{n}": sorted(_portas(fn))
               for (p, n), fn in _gestos_registrados().items() if _portas(fn)}
    assert len(achados) >= 3, (
        f"a régua só achou {len(achados)} gesto(s) que escrevem — os nomes de "
        f"`ESCREVEM` provavelmente mudaram no produto: {achados}")


def test_a_lista_nao_protege_gesto_que_nao_existe() -> None:
    """E o outro lado: um nome errado em `PERIGOSOS` protege NADA."""
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
    "tirar-daqui", "voltar-a-usar", "voltar-a-perguntar",
    "confirmar-exclusao", "tirar-da-exclusao", "confirmar-perfil",
])
def test_as_portas_da_aba_07_estao_protegidas(nome: str) -> None:
    """A quarta repetição, nomeada — para a regressão ter nome.

    A `STEAM-INPUT-01` mediu que a régua era cega para a aba INTEIRA. Estas
    escrevem em arquivos DELA: `jogos_sem_wrapper.txt`,
    `launch_dialog_dismissed.json`, a lista de exclusão, o pino, o atalho e o
    perfil novo.
    """
    from hefesto_dualsense4unix.interface.hefesto_vivo import PERIGOSOS

    assert ("07-lancadores.html", nome) in set(PERIGOSOS), (
        f"`{nome}` saiu de PERIGOSOS — é uma das portas da aba 07 que a "
        "régua não enxergava até 06/09/2026.")


def test_toda_isencao_aponta_um_gesto_e_tem_razao() -> None:
    """Isenção sem razão é ponto cego com nome bonito."""
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

    nos_dois = sorted(set(ISENTOS) & set(FORA_DA_ARVORE))
    assert not nos_dois, f"gesto(s) isentos E assinados ao mesmo tempo: {nos_dois}"
    isentos_declarados = sorted(p for p in ISENTOS if p in declarados)
    assert not isentos_declarados, (
        f"gesto(s) isentos que declaram `grava=`: {isentos_declarados}. A "
        "isenção existe para NÃO proteger; declarar protege. Escolha uma.")


def test_a_isencao_nao_alcanca_o_que_grava_valor_novo() -> None:
    """A lista de isentos não pode crescer para dentro do perigo."""
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

    Aqui a profundidade é medida DIRETAMENTE, no herdeiro do caso que a
    revelou: o gesto `08-conexoes·adaptador-renomear` (era `renomear-adaptador`
    até 23/09/2026, TRANSPLANTE-DA-SECAO-01) não chama `dar_nome_ao_adaptador`;
    ele chama `_gravar_o_nome`, do mesmo arquivo, e é o ajudante que grava no
    disco dela.
    """
    gestos = _gestos_registrados()
    fn = gestos[("08-conexoes.html", "adaptador-renomear")]

    assert "dar_nome_ao_adaptador" in _portas(fn), (
        "a régua parou de descer pelos ajudantes do módulo: ela voltou a ler "
        "só o corpo do gesto, e é assim que o nome do adaptador ficou "
        "desprotegido até 04/09/2026."
    )
    fonte = inspect.getsource(fn)
    assert "dar_nome_ao_adaptador(" not in fonte.split('"""')[-1], (
        "o gesto passou a chamar a porta DIRETAMENTE; este caso deixou de "
        "provar a descida. Escolha outro gesto que grave por ajudante."
    )
