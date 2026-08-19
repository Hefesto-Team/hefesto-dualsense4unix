"""PERFIL-SALVA-TUDO — O PORTÃO: nenhuma seção do perfil nasce sem prova.

Este é o arquivo que "impede regressões futuras" do pedido dela (09/08/2026).
Ele não mede comportamento nenhum: ele mede a COBERTURA da medição — se o dia
em que alguém acrescentar um campo ao ``Profile`` e esquecer de ligá-lo à
janela vai ser um dia de vermelho ou de silêncio.

Três perguntas, e todas as três são derivadas em RUNTIME (nada de lista escrita
à mão que envelhece junto com o defeito que ela deveria pegar):

1. **toda seção de ``Profile`` tem ida e volta?** A lista de seções sai de
   ``Profile.model_fields`` no momento do teste; a lista de seções cobertas sai
   do ``SECOES_COBERTAS`` do módulo irmão
   (``test_perfil_salva_tudo_ida_e_volta.py``). Campo novo sem caso reprova
   aqui, com o texto do que fazer;

2. **o registro do módulo irmão descreve os casos que existem de verdade?** Um
   literal decorativo satisfaria a pergunta 1 sem cobrir nada. Então este
   portão confere, por AST, que cada chave de ``SECOES_COBERTAS`` tem entrada em
   ``_GESTOS`` e que as funções de gesto/conferência nomeadas ali EXISTEM no
   arquivo;

3. **a seção tem quem a escreva na janela?** Esta é a metade de CIMA do
   caminho, e é onde mora o defeito-mãe desta casa — *"a casa sabe e o produto
   não faz"*: a seção existe no esquema, no rascunho, no ``to_profile``, no
   ``to_ipc_dict`` e no aplicador do daemon, e não existe **uma linha** na
   janela que a escreva. O portão varre ``src/hefesto_dualsense4unix/app/`` por
   AST e diz quais seções não têm escritor.

POR QUE LER O MÓDULO IRMÃO POR AST, E NÃO IMPORTÁ-LO. O irmão precisa de
PyGObject real (os mixins da janela importam ``gi`` na primeira linha) e PULA
onde não há GTK. Um portão que pula é um portão que não existe justamente na
máquina em que ninguém está olhando. Lido por AST, este arquivo roda em
qualquer lugar — inclusive no CI headless — e continua reprovando.

É por isso que ``SECOES_COBERTAS`` e ``_GESTOS``, lá no irmão, têm de continuar
sendo dicionários LITERAIS: há teste aqui que reprova se alguém os transformar
em compreensão, ``dict()`` ou qualquer coisa que o ``ast`` não consiga ler sem
executar.
"""
from __future__ import annotations

import ast
import shutil
from collections.abc import Iterable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import Profile

#: Raiz do pacote e o módulo irmão que guarda os casos de ida e volta.
_RAIZ = Path(__file__).resolve().parents[2]
_APP = _RAIZ / "src" / "hefesto_dualsense4unix" / "app"
_IRMAO = Path(__file__).with_name("test_perfil_salva_tudo_ida_e_volta.py")

#: Campos de ``Profile`` que NÃO precisam de ida e volta, com a razão escrita.
#: Isenção sem razão é lista de exceções disfarçada de decisão; a razão é o que
#: permite a próxima pessoa discordar com conhecimento de causa.
ISENTOS: dict[str, str] = {
    "version": (
        "constante do esquema (`Literal[1] = 1`). Não é configuração dela, não "
        "há gesto que a mude e o pydantic recusa qualquer outro valor no load "
        "— um caso de ida e volta aqui mediria o pydantic, não o produto."
    ),
    "ponte": (
        "PONTE-CONFIRMADA-01 (19/08/2026): não é preferência dela, é REGISTRO "
        "de uma confirmação — a ponte que já pegou naquele jogo, carimbada pelo "
        "gesto no controle, pelo silêncio de quem jogou sem reclamar, ou pela "
        "escolha direta dela. E ela tem de ficar FORA do rascunho da janela por "
        "uma razão de produto, não de conveniência: se o 'Salvar Perfil' "
        "escrevesse este campo, todo save carimbaria como confirmada uma ponte "
        "que ninguém confirmou, e a escada pararia de rodar em todo jogo — o "
        "defeito mais silencioso desta frente, o que faz o produto jurar que "
        "sabe o que não sabe. Quem escreve é `manager.confirmar_ponte`, e o "
        "ida e volta dela está em "
        "`test_ponte_confirmada_01_o_perfil_guarda_a_ponte_que_funcionou.py`."
    ),
}

#: Seções que a JANELA escreve no rascunho, e os sinais no código-fonte que
#: provam que existe escritor. TRÊS famílias de sinal, porque há três idiomas
#: de escrita no rascunho congelado — e um portão preso a um só idioma acusaria
#: lacuna onde a cura já entrou por outra porta:
#:
#: - ``chaves``: chaves de um ``model_copy(update={...})`` (o idioma das abas
#:   Lightbar, Gatilhos, Rumble, Mouse e Teclado);
#: - ``escritores``: os escritores nomeados do ``DraftConfig`` e as funções de
#:   módulo que são o dono único de uma seção (``with_mode``,
#:   ``registrar_alto_falante_no_rascunho``…);
#: - ``classes``: construir o sub-rascunho da seção fora do ``draft_config``
#:   (``MicDraft(...)``) — ninguém instancia um sub-rascunho para ler.
#:
#: ``name``/``match``/``priority`` ficam de fora: eles não passam pelo rascunho
#: como seção — nascem no gesto de SALVAR (``_regra_do_save``,
#: ``_prioridade_do_save``, o nome do diálogo) e têm testemunhas próprias em
#: ``test_gravacao_de_perfil_passa_pelo_funil.py``.
_SINAIS_DE_ESCRITOR: dict[str, dict[str, tuple[str, ...]]] = {
    "triggers": {
        "chaves": ("triggers",),
        "escritores": ("with_controller_triggers", "with_override_fields_cleared"),
        "classes": ("TriggerDraft", "TriggersDraft"),
    },
    "leds": {
        "chaves": ("leds",),
        "escritores": ("with_controller_leds", "with_controller_fields_cleared"),
        "classes": ("LedsDraft",),
    },
    "rumble": {"chaves": ("rumble",), "escritores": (), "classes": ("RumbleDraft",)},
    "key_bindings": {"chaves": ("key_bindings",), "escritores": (), "classes": ()},
    "mouse": {"chaves": ("mouse",), "escritores": (), "classes": ("MouseDraft",)},
    "mic": {
        "chaves": ("mic",),
        # PERFIL-GUARDA-O-MIC-01 (18/08/2026): o escritor único do microfone,
        # irmão do `registrar_alto_falante_no_rascunho`. O card o chama no
        # callback de sucesso do daemon (volume, mudo e a devolução da posse).
        "escritores": ("with_mic", "registrar_microfone_no_rascunho"),
        "classes": ("MicDraft",),
    },
    "speaker": {
        "chaves": ("speaker",),
        "escritores": (
            "with_speaker",
            "without_speaker",
            "registrar_alto_falante_no_rascunho",
        ),
        "classes": ("SpeakerDraft",),
    },
    "mode": {
        "chaves": ("source_mode",),
        "escritores": ("with_mode", "registrar_modo_no_rascunho"),
        "classes": (),
    },
    "suppress_desktop_emulation": {
        "chaves": ("source_suppress",),
        "escritores": ("with_suppress", "registrar_modo_jogo_no_rascunho"),
        "classes": (),
    },
    "controllers": {
        "chaves": ("source_controllers",),
        "escritores": ("with_controller_leds", "with_controller_triggers"),
        "classes": (),
    },
}

#: Seções SEM escritor na janela hoje, com o endereço da lacuna e o que fazer.
#: ``xfail(strict=True)``: no dia em que o escritor nascer, o caso passa e o
#: pytest REPROVA o xfail que sobrou — a lápide não pode envelhecer calada.
#: Quem entregar a cura APAGA a entrada daqui, e é essa a única manutenção.
#:
#: ESTÁ VAZIO desde 18/08/2026, e o vazio é a CURA, não descuido. A única
#: entrada que existiu aqui era a do ``mic``, medida em 09/08/2026: nenhuma
#: superfície da janela escrevia a seção. Ela saiu quando o escritor nasceu
#: (``draft_config.registrar_microfone_no_rascunho``, chamado pelo card do
#: controle no callback de sucesso do daemon) — PERFIL-GUARDA-O-MIC-01, o
#: pedido dela depois de o microfone ficar mudo e o DON'T SCREAM não ouvir
#: nada: *"temos que salvar isso no perfil sempre"*.
_SEM_ESCRITOR_HOJE: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Leitura do módulo irmão por AST (sem importar — ele exige GTK real)
# ---------------------------------------------------------------------------


def _arvore(caminho: Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))


def _atribuicao(arvore: ast.Module, nome: str) -> ast.expr:
    """O valor da atribuição de módulo ``nome``, ou reprova dizendo o que falta."""
    for no in arvore.body:
        alvos: list[ast.expr] = []
        if isinstance(no, ast.Assign):
            alvos = list(no.targets)
        elif isinstance(no, ast.AnnAssign):
            alvos = [no.target]
        else:
            continue
        for alvo in alvos:
            if isinstance(alvo, ast.Name) and alvo.id == nome:
                valor = no.value
                assert valor is not None, f"{nome} declarado sem valor"
                return valor
    raise AssertionError(
        f"{nome} sumiu de {_IRMAO.name} — este portão o lê por AST e ficou cego"
    )


def _chaves_de_dicionario_literal(arvore: ast.Module, nome: str) -> list[str]:
    """As chaves (str) de um dicionário LITERAL de módulo.

    Reprova quando o dicionário deixa de ser literal. Não é preciosismo de
    forma: um ``dict(...)``, uma compreensão ou uma concatenação exigiriam
    IMPORTAR o módulo irmão para saber o que ele contém — e o irmão exige GTK,
    o que faria este portão PULAR exatamente onde ele é mais necessário.
    """
    valor = _atribuicao(arvore, nome)
    assert isinstance(valor, ast.Dict), (
        f"{nome} deixou de ser um dicionário literal em {_IRMAO.name} "
        f"(virou {type(valor).__name__}). Este portão o lê por AST, sem "
        "importar o módulo (que exige PyGObject real) — devolva-o a um "
        "literal, ou o portão fica cego onde não há GTK."
    )
    chaves: list[str] = []
    for chave in valor.keys:
        assert isinstance(chave, ast.Constant) and isinstance(chave.value, str), (
            f"{nome} tem uma chave que não é literal de texto: "
            f"{ast.dump(chave) if chave is not None else '**expansão'}"
        )
        chaves.append(chave.value)
    return chaves


def _nomes_de_funcao(arvore: ast.Module) -> set[str]:
    return {
        no.name for no in arvore.body if isinstance(no, ast.FunctionDef)
    }


def _funcoes_citadas_em_gestos(arvore: ast.Module) -> dict[str, tuple[str, ...]]:
    """``campo -> (nome do gesto, nome da conferência)`` lido do ``_GESTOS``."""
    valor = _atribuicao(arvore, "_GESTOS")
    assert isinstance(valor, ast.Dict), "_GESTOS deixou de ser um literal"
    saida: dict[str, tuple[str, ...]] = {}
    for chave, item in zip(valor.keys, valor.values, strict=True):
        assert isinstance(chave, ast.Constant) and isinstance(chave.value, str)
        assert isinstance(item, ast.Tuple), (
            f"o valor de _GESTOS[{chave.value!r}] não é um par (gesto, confere)"
        )
        nomes: list[str] = []
        for elemento in item.elts:
            assert isinstance(elemento, ast.Name), (
                f"_GESTOS[{chave.value!r}] cita algo que não é um nome de função"
            )
            nomes.append(elemento.id)
        saida[chave.value] = tuple(nomes)
    return saida


# ---------------------------------------------------------------------------
# Varredura dos ESCRITORES da janela (também por AST, também sem importar)
# ---------------------------------------------------------------------------


class _ColetorDeEscritas(ast.NodeVisitor):
    """Junta as chaves de ``model_copy(update={...})`` e os escritores nomeados.

    O critério é ESTRUTURAL de propósito: um ``grep`` por ``"mic"`` acharia a
    palavra em qualquer comentário, e um comentário nunca escreveu nada no
    rascunho de ninguém.
    """

    def __init__(self) -> None:
        self.chaves: set[str] = set()
        self.escritores: set[str] = set()
        self.classes: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        alvo = node.func
        nome = (
            alvo.attr
            if isinstance(alvo, ast.Attribute)
            else alvo.id
            if isinstance(alvo, ast.Name)
            else ""
        )
        if nome.startswith(("with_", "without_", "registrar_")):
            self.escritores.add(nome)
        # Construir um sub-rascunho FORA do `draft_config` é escrita por
        # definição — ninguém instancia um `MicDraft` para ler. Este terceiro
        # sinal existe para o portão não ficar preso a UM idioma: quem curar a
        # lacuna do microfone pode fazê-lo com `MicDraft(...)` em vez de
        # `model_copy`, e um portão que só conhecesse o segundo continuaria
        # dizendo que a lacuna existe depois de ela ter sido fechada.
        if nome.endswith("Draft"):
            self.classes.add(nome)
        if nome == "model_copy":
            for kw in node.keywords:
                if kw.arg != "update":
                    continue
                if isinstance(kw.value, ast.Dict):
                    for chave in kw.value.keys:
                        if isinstance(chave, ast.Constant) and isinstance(
                            chave.value, str
                        ):
                            self.chaves.add(chave.value)
                elif isinstance(kw.value, ast.Call):
                    # `model_copy(update=dict(mic=...))` — mesmo gesto, outra
                    # grafia. Sem isto o portão seria surdo a metade do idioma.
                    self.chaves.update(
                        sub.arg for sub in kw.value.keywords if sub.arg
                    )
        self.generic_visit(node)


def _vocabulario_de_escrita_da_janela(
    raiz: Path | None = None,
) -> tuple[set[str], set[str], set[str]]:
    """(chaves, escritores, classes) que a JANELA usa para escrever no rascunho.

    ``app/draft_config.py`` fica de fora: ele é o LUGAR de guardar, não a
    superfície que a usuária toca. Contá-lo faria toda seção parecer escrita —
    é justamente o engano que esconde o defeito do microfone.

    ``raiz`` existe para o portão poder ser apontado para uma CÓPIA mutilada de
    si mesmo (``TestOPortaoMorde``) sem que ninguém precise mexer em ``src/``
    — arrancar cura na árvore viva é o que a ARVORE-CONGELADA-01 mostrou que
    contamina medição alheia quando há mais de uma pessoa trabalhando.
    """
    alvo = _APP if raiz is None else raiz
    chaves: set[str] = set()
    escritores: set[str] = set()
    classes: set[str] = set()
    for caminho in sorted(alvo.rglob("*.py")):
        if caminho.name == "draft_config.py":
            continue
        coletor = _ColetorDeEscritas()
        coletor.visit(_arvore(caminho))
        chaves |= coletor.chaves
        escritores |= coletor.escritores
        classes |= coletor.classes
    return chaves, escritores, classes


def secoes_sem_escritor(raiz: Path | None = None) -> list[str]:
    """As seções do perfil que NENHUMA superfície da janela escreve.

    Função de módulo (e não corpo de teste) porque ela é o instrumento, e o
    instrumento tem de poder ser apontado para si mesmo — ver
    ``TestOPortaoMorde``.
    """
    chaves, escritores, classes = _vocabulario_de_escrita_da_janela(raiz)
    orfas: list[str] = []
    for campo, sinais in _SINAIS_DE_ESCRITOR.items():
        tem = (
            bool(set(sinais["chaves"]) & chaves)
            or bool(set(sinais["escritores"]) & escritores)
            or bool(set(sinais["classes"]) & classes)
        )
        if not tem:
            orfas.append(campo)
    return sorted(orfas)


def secoes_sem_ida_e_volta(
    campos_do_esquema: Iterable[str],
    cobertas: Iterable[str],
    isentos: Iterable[str],
) -> list[str]:
    """As seções que o esquema tem e a bancada não cobre. O miolo do portão.

    Função PURA e separada do teste de propósito: é ela que precisa provar que
    morde, e a única forma honesta de provar isso sem esperar alguém
    acrescentar um campo ao ``Profile`` é apontá-la para um conjunto de campos
    fabricado (``TestOPortaoMorde``).
    """
    return sorted(set(campos_do_esquema) - set(cobertas) - set(isentos))


# ---------------------------------------------------------------------------
# 1. Toda seção de Profile tem ida e volta
# ---------------------------------------------------------------------------


class TestTodaSecaoDoPerfilTemIdaEVolta:
    """A lista de seções sai do esquema em RUNTIME, nunca de uma cópia."""

    def test_nenhuma_secao_do_perfil_fica_sem_caso(self) -> None:
        """Campo novo em ``Profile`` sem ida e volta reprova aqui.

        É este caso que cumpre o *"impede regressões futuras"* do pedido dela:
        no dia em que uma feature nova nascer sem chegar ao arquivo, o vermelho
        aparece sozinho — ninguém precisa lembrar de nada.

        MORDIDA: o miolo é a função PURA ``secoes_sem_ida_e_volta``, e a
        mordida dela está provada em
        ``TestOPortaoMorde::test_um_campo_novo_no_esquema_aparece_como_descoberto``
        — apontada para um conjunto de campos FABRICADO, que é a única forma de
        provar que ela acusa sem esperar alguém mexer no esquema de verdade (e
        sem mutilar ``src/`` no meio da sessão de outra pessoa, que é o que a
        ARVORE-CONGELADA-01 mostrou contaminar medição alheia).
        """
        cobertas = set(_chaves_de_dicionario_literal(_arvore(_IRMAO), "SECOES_COBERTAS"))
        descobertas = secoes_sem_ida_e_volta(Profile.model_fields, cobertas, ISENTOS)
        assert not descobertas, (
            "seções do perfil SEM caso de ida e volta: "
            f"{descobertas}\n"
            "Cada uma delas é uma configuração que a janela pode estar "
            "perdendo em silêncio no 'Salvar Perfil'.\n"
            "O que fazer: em tests/unit/test_perfil_salva_tudo_ida_e_volta.py, "
            "acrescente a entrada em SECOES_COBERTAS (dizendo QUAL superfície a "
            "escreve) e o par (gesto, conferência) em _GESTOS. Se o campo "
            "realmente não for configuração dela, isente-o em ISENTOS aqui, "
            "COM a razão escrita."
        )

    def test_o_registro_nao_guarda_secao_que_nao_existe_mais(self) -> None:
        """Seção removida do esquema não pode deixar caso órfão para trás.

        MORDIDA: acrescente ``"gyro": "..."`` a ``SECOES_COBERTAS`` sem o campo
        no esquema e este teste reprova. Sem ele, o registro viraria um
        cemitério e a pergunta 1 passaria a ser respondida por entradas mortas.
        """
        cobertas = set(_chaves_de_dicionario_literal(_arvore(_IRMAO), "SECOES_COBERTAS"))
        fantasmas = sorted(cobertas - set(Profile.model_fields))
        assert not fantasmas, (
            f"o registro de ida e volta cita seções que o esquema não tem mais: "
            f"{fantasmas}"
        )

    def test_toda_isencao_tem_razao_escrita(self) -> None:
        """Isenção sem razão é lista de exceções fingindo ser decisão."""
        for campo, razao in ISENTOS.items():
            assert campo in Profile.model_fields, (
                f"{campo!r} está isento e nem existe no esquema"
            )
            assert len(razao) > 60, (
                f"a razão da isenção de {campo!r} é curta demais para alguém "
                f"discordar dela com conhecimento de causa: {razao!r}"
            )


# ---------------------------------------------------------------------------
# 2. O registro descreve os casos que existem de verdade
# ---------------------------------------------------------------------------


class TestORegistroNaoPodeSerDecorativo:
    """Um literal bonito satisfaria a pergunta 1 sem cobrir coisa nenhuma."""

    def test_cada_secao_coberta_tem_gesto_e_conferencia(self) -> None:
        """``SECOES_COBERTAS`` e ``_GESTOS`` têm de ter as mesmas chaves.

        MORDIDA: apague uma entrada de ``_GESTOS`` mantendo a de
        ``SECOES_COBERTAS`` e este teste reprova nomeando a seção.
        """
        arvore = _arvore(_IRMAO)
        cobertas = set(_chaves_de_dicionario_literal(arvore, "SECOES_COBERTAS"))
        gestos = set(_funcoes_citadas_em_gestos(arvore))
        assert cobertas == gestos, (
            "o registro de ida e volta divergiu dos casos que rodam de fato — "
            f"só no literal: {sorted(cobertas - gestos)}; "
            f"só nos gestos: {sorted(gestos - cobertas)}"
        )

    def test_as_funcoes_citadas_existem_no_modulo_irmao(self) -> None:
        """Gesto e conferência nomeados no registro têm de existir.

        MORDIDA: renomeie ``_confere_leds`` sem atualizar ``_GESTOS`` e este
        teste reprova — antes de a suíte inteira quebrar por ``NameError`` numa
        coleta que ninguém lê.
        """
        arvore = _arvore(_IRMAO)
        existentes = _nomes_de_funcao(arvore)
        faltando: list[str] = []
        for campo, nomes in _funcoes_citadas_em_gestos(arvore).items():
            assert len(nomes) == 2, (
                f"_GESTOS[{campo!r}] não é um par (gesto, conferência)"
            )
            faltando.extend(n for n in nomes if n not in existentes)
        assert not faltando, (
            f"o registro cita funções que não existem em {_IRMAO.name}: "
            f"{sorted(set(faltando))}"
        )

    def test_o_registro_diz_qual_superficie_escreve_cada_secao(self) -> None:
        """A descrição de cada seção não pode ser um enfeite vazio.

        É a linha que a próxima pessoa vai ler para saber ONDE olhar quando a
        configuração dela sumir. Um ``"ok"`` ali seria pior que nada.
        """
        valor = _atribuicao(_arvore(_IRMAO), "SECOES_COBERTAS")
        assert isinstance(valor, ast.Dict)
        curtas: list[str] = []
        for chave, item in zip(valor.keys, valor.values, strict=True):
            assert isinstance(chave, ast.Constant)
            texto = ast.literal_eval(item) if isinstance(item, ast.Constant) else ""
            if isinstance(item, ast.JoinedStr):  # pragma: no cover — f-string
                texto = ""
            if not isinstance(texto, str) or len(texto) < 20:
                curtas.append(str(chave.value))
        assert not curtas, (
            "estas seções não dizem qual superfície da janela as escreve: "
            f"{curtas}"
        )


# ---------------------------------------------------------------------------
# 3. A seção tem quem a escreva NA JANELA
# ---------------------------------------------------------------------------


class TestTodaSecaoTemEscritorNaJanela:
    """A metade de CIMA do caminho: o dedo dela chega ao rascunho?

    A metade de baixo (rascunho -> arquivo) é o módulo irmão. As duas juntas
    são a resposta inteira ao pedido — e separá-las é o que permite dizer, de
    uma seção quebrada, se falta a superfície ou falta a persistência.
    """

    @pytest.mark.parametrize(
        "campo",
        [
            pytest.param(
                nome,
                id=nome,
                marks=(
                    [pytest.mark.xfail(strict=True, reason=_SEM_ESCRITOR_HOJE[nome])]
                    if nome in _SEM_ESCRITOR_HOJE
                    else []
                ),
            )
            for nome in _SINAIS_DE_ESCRITOR
        ],
    )
    def test_a_secao_tem_escritor_na_janela(self, campo: str) -> None:
        """Alguma superfície de ``app/`` escreve esta seção no rascunho?

        MORDIDA: provada em
        ``TestOPortaoMorde::test_arrancar_um_escritor_da_copia_acusa_a_secao``,
        que copia ``app/`` para um tmp, arranca de lá a linha que escreve
        ``key_bindings`` e cobra que a seção apareça como órfã. A cópia é
        deliberada: mutilar ``src/`` na árvore viva contamina a medição de quem
        estiver trabalhando ao lado (ARVORE-CONGELADA-01).

        O caso ``mic`` já reprova HOJE, sem arrancar nada — e é por isso que ele
        carrega o ``xfail`` estrito com o endereço da lacuna por extenso.
        """
        assert campo not in secoes_sem_escritor(), (
            f"a seção {campo!r} do perfil NÃO tem escritor na janela: nenhum "
            f"arquivo de {_APP} escreve "
            f"{_SINAIS_DE_ESCRITOR[campo]['chaves']} num "
            "`model_copy(update=...)`, nem chama "
            f"{_SINAIS_DE_ESCRITOR[campo]['escritores']}, nem constrói "
            f"{_SINAIS_DE_ESCRITOR[campo]['classes']}.\n"
            "A configuração existe no esquema e no rascunho, e não há onde ela "
            "possa tocá-la — a seção nasce morta no arquivo dela."
        )

    def test_a_lista_de_lacunas_conhecidas_nao_envelhece_calada(self) -> None:
        """Toda lacuna declarada tem razão longa, e é uma lacuna de verdade.

        Sem isto, ``_SEM_ESCRITOR_HOJE`` viraria o lugar onde se esconde o que
        incomoda — que é o oposto do que um portão serve para fazer.
        """
        for campo, razao in _SEM_ESCRITOR_HOJE.items():
            assert campo in _SINAIS_DE_ESCRITOR, (
                f"{campo!r} está na lista de lacunas e não é seção vigiada"
            )
            assert len(razao) > 120, (
                f"a razão da lacuna de {campo!r} não diz onde o dado se perde: "
                f"{razao!r}"
            )


# ---------------------------------------------------------------------------
# O portão apontado para si mesmo
# ---------------------------------------------------------------------------


class TestOPortaoMorde:
    """Um portão que nunca reprovou é uma decoração com nome de portão.

    Estes casos exercitam o INSTRUMENTO — não o produto. Se a varredura de AST
    parasse de enxergar escritas (um refactor que trocasse ``model_copy`` por
    outra coisa, por exemplo), todos os casos acima ficariam verdes sem medir
    nada, e é exatamente essa a falha que esta classe pega.
    """

    def test_a_varredura_enxerga_as_escritas_que_existem(self) -> None:
        """A régua conferida contra contagem independente.

        Os quatro nomes abaixo estão no código de produção hoje, em quatro
        arquivos diferentes de ``app/actions/``. Se a varredura não os vir, ela
        não vê nada — e a lista de lacunas viraria a lista de seções.
        """
        chaves, escritores, classes = _vocabulario_de_escrita_da_janela()
        assert "leds" in chaves, "a varredura não vê a aba Lightbar escrevendo"
        assert "rumble" in chaves, "a varredura não vê a aba Rumble escrevendo"
        assert "with_mode" in escritores, "a varredura não vê o escritor do modo"
        assert "registrar_alto_falante_no_rascunho" in escritores, (
            "a varredura não vê o escritor do alto-falante"
        )
        assert "TriggerDraft" in classes, (
            "a varredura não vê a aba Gatilhos construindo o sub-rascunho — o "
            "terceiro idioma de escrita ficou cego"
        )

    def test_uma_secao_inventada_aparece_como_orfa(self) -> None:
        """A prova de que a lista de lacunas não é sempre vazia por construção.

        Inventa-se uma seção cujos sinais não existem em lugar nenhum do
        código; ela TEM de sair como órfã. É o mesmo raciocínio da mordida:
        um instrumento que nunca acusa nada não está medindo.
        """
        sinais_originais = dict(_SINAIS_DE_ESCRITOR)
        try:
            _SINAIS_DE_ESCRITOR["secao_que_nao_existe"] = {
                "chaves": ("chave_que_ninguem_escreve_jamais",),
                "escritores": ("with_um_escritor_que_nao_existe",),
                "classes": ("SubRascunhoQueNaoExisteDraft",),
            }
            assert "secao_que_nao_existe" in secoes_sem_escritor()
        finally:
            _SINAIS_DE_ESCRITOR.clear()
            _SINAIS_DE_ESCRITOR.update(sinais_originais)

    def test_um_campo_novo_no_esquema_aparece_como_descoberto(self) -> None:
        """O miolo do portão de cobertura, apontado para um esquema FABRICADO.

        Um campo ``gyro`` que ninguém cobriu tem de sair na lista; os campos
        reais, cobertos, não. Sem este caso, ``secoes_sem_ida_e_volta`` poderia
        estar devolvendo lista vazia por construção e o portão inteiro seria
        uma decoração.
        """
        cobertas = set(_chaves_de_dicionario_literal(_arvore(_IRMAO), "SECOES_COBERTAS"))
        inventado = {*Profile.model_fields, "gyro"}
        assert secoes_sem_ida_e_volta(inventado, cobertas, ISENTOS) == ["gyro"]
        assert secoes_sem_ida_e_volta(Profile.model_fields, cobertas, ISENTOS) == []

    def test_arrancar_um_escritor_da_copia_acusa_a_secao(self, tmp_path: Path) -> None:
        """A varredura de escritores, provada numa CÓPIA mutilada de ``app/``.

        Copia-se a árvore da janela para um tmp, arranca-se de lá a única linha
        que escreve ``key_bindings`` no rascunho
        (``app/actions/input_actions.py``) e cobra-se que a seção passe a
        aparecer como órfã. Devolvida a árvore original (a de verdade nunca foi
        tocada), a seção some da lista.

        É a mordida do instrumento sem tocar em ``src/`` — e a razão de não
        tocar está escrita em ``_vocabulario_de_escrita_da_janela``.
        """
        copia = tmp_path / "app"
        shutil.copytree(
            _APP, copia, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        alvo = copia / "actions" / "input_actions.py"
        texto = alvo.read_text(encoding="utf-8")
        assert '"key_bindings"' in texto, (
            "a linha que escreve os bindings mudou de forma — esta mordida "
            "precisa de outro alvo, senão ela deixa de morder em silêncio"
        )
        alvo.write_text(texto.replace('"key_bindings"', '"__arrancado__"'), "utf-8")

        assert "key_bindings" in secoes_sem_escritor(copia), (
            "a varredura NÃO acusou a seção depois de o escritor dela ser "
            "arrancado da cópia — o portão de escritores não morde"
        )
        assert "key_bindings" not in secoes_sem_escritor(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_o_conjunto_vigiado_cobre_o_que_o_rascunho_carrega(self) -> None:
        """Seção do perfil que passa pelo rascunho tem de estar vigiada aqui.

        MORDIDA: apague uma entrada de ``_SINAIS_DE_ESCRITOR`` e este teste
        reprova. Sem ele, esquecer de vigiar uma seção nova produziria o mesmo
        silêncio que o portão existe para acabar.
        """
        fora_do_rascunho = {"name", "match", "priority", *ISENTOS}
        esperadas = set(Profile.model_fields) - fora_do_rascunho
        vigiadas = set(_SINAIS_DE_ESCRITOR)
        assert esperadas == vigiadas, (
            "o conjunto de seções vigiadas por escritor divergiu do esquema — "
            f"sem vigia: {sorted(esperadas - vigiadas)}; "
            f"vigiadas a mais: {sorted(vigiadas - esperadas)}"
        )
