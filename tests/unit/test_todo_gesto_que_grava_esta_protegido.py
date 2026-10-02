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


import pytest


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


