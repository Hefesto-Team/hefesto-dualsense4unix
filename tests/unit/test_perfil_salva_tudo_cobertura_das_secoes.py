"""PERFIL-SALVA-TUDO — O PORTÃO: nenhuma seção do perfil nasce sem prova."""
from __future__ import annotations

import ast
import shutil
from collections.abc import Iterable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import Profile

_RAIZ = Path(__file__).resolve().parents[2]
_APP = _RAIZ / "src" / "hefesto_dualsense4unix" / "app"
_IRMAO = Path(__file__).with_name("test_perfil_salva_tudo_ida_e_volta.py")

#: fica: o valor não é escolha dela, ou a isenção é do instrumento e o campo tem régua própria
ISENTOS: dict[str, str] = {
    "button_actions": (
        "FEAT-ACOES-DE-BOTAO-01 (01/09/2026). A isenção é do INSTRUMENTO, não do "
        "campo: o irmão deste portão dirige a JANELA GTK — ele exige `gi` real e "
        "aciona os mixins de `app/actions/` —, e este campo não tem superfície "
        "lá. Quem o escreve é a interface nova, no gesto `guardar-definicoes` da "
        "aba Navegação (`interface/pacotes/a06_navegacao.py`), e o caminho dele "
        "não passa por widget nenhum. Um caso de ida e volta aqui teria de "
        "fabricar um rascunho que a janela nunca produz — mediria o dublê. "
        "ELE TEM RÉGUA, e são duas, com mordida: "
        "`test_o_que_cada_botao_faz_tem_campo.py` cobre os quatro elos (padrão "
        "derivado, campo no perfil, resolução, device obedecendo) e "
        "`test_a_tela_entrega_as_vinte_e_uma_linhas.py` dirige a página "
        "publicada num Chrome e confere que as 21 linhas chegam ao Python. "
        "A ISENÇÃO CAI no dia em que a aba Navegação virar tela GTK — o que a "
        "decisão dela de 01/09 (*'a versão antiga não segue disponível'*) torna "
        "improvável, mas quem a reverter tem de reler esta linha."
    ),
    "remapeamento": (
        "F1-REMAPEAR (13/09/2026). A isenção é do INSTRUMENTO, pela mesma razão "
        "do `button_actions`: o irmão deste portão dirige a JANELA GTK, e este "
        "campo não tem superfície lá — quem o escreve é a interface nova, nos "
        "gestos `guardar-remapeamento` e `padrao-remapeamento` da aba Navegação "
        "(`interface/pacotes/a06_navegacao.py`). O rascunho o TRANSPORTA "
        "(`DraftConfig.source_remapeamento`), porque `to_profile` reconstrói o "
        "perfil do zero e sem o transporte todo Salvar da aba Perfis apagaria a "
        "troca. ELE TEM RÉGUA COM MORDIDA: "
        "`test_migra_navegacao_13_o_remapeamento_botao_a_botao.py` cobre o motor, "
        "o campo omitido quando vazio, o depósito na ativação, os dois "
        "`forward_buttons`, o transporte do Salvar e os quatro gestos da tela."
    ),
    "movimento": (
        "MOVIMENTO-EM-QUALQUER-MASCARA-01 (21/09/2026). A isenção é do "
        "INSTRUMENTO, pela mesma razão do `remapeamento`: o irmão deste portão "
        "dirige a JANELA GTK, e a mira por movimento não tem superfície lá — nem "
        "na interface nova, ainda: quem a escreve hoje é o JSON do perfil. O "
        "rascunho a TRANSPORTA (`DraftConfig.source_movimento`), porque "
        "`to_profile` reconstrói o perfil do zero — e esta régua achou o "
        "defeito no dia em que o campo nasceu: o Salvar devolvia `None`. ELE "
        "TEM RÉGUA COM MORDIDA em `test_o_movimento_vale_em_qualquer_mascara.py` "
        "(o transporte do Salvar, com o mesmo nome e com nome novo, e a ida e "
        "volta pelo disco)."
    ),
    "version": (
        "constante do esquema (`Literal[1] = 1`). Não é configuração dela, não "
        "há gesto que a mude e o pydantic recusa qualquer outro valor no load "
        "— um caso de ida e volta aqui mediria o pydantic, não o produto."
    ),
    "ponte": (
        "PONTE-CONFIRMADA-01 (19/08/2026): não é preferência dela, é REGISTRO "
        "de uma confirmação — a ponte que já pegou naquele jogo, carimbada pelo "
        "gesto no controle, pelo silêncio de quem jogou sem reclamar, ou pela "
        "escolha direta dela. Não existe gesto de aba que a produza, e é por "
        "isso que ela não tem ida e volta aqui. O rascunho a TRANSPORTA desde "
        "22/08/2026 (`DraftConfig.source_ponte`, passthrough somente-leitura no "
        "molde do `source_match`): `to_profile` reconstrói o perfil do zero, e "
        "sem o transporte todo 'Salvar Perfil' apagava o carimbo — o jogo caía "
        "do `manager.pontes_confirmadas()` e a escada recomeçava do primeiro "
        "degrau no lançamento seguinte. TRANSPORTAR NÃO É ESCREVER, e a "
        "diferença é a feature: se a janela ganhasse campo para este valor, "
        "todo save carimbaria como confirmada uma ponte que ninguém confirmou e "
        "a escada pararia em TODO jogo — o defeito mais silencioso desta "
        "frente, o que faz o produto jurar que sabe o que não sabe. Quem "
        "escreve é `manager.confirmar_ponte`, e o ida e volta dela está em "
        "`test_ponte_confirmada_01_o_perfil_guarda_a_ponte_que_funcionou.py`; o "
        "passthrough tem testemunha própria em "
        "`test_o_carimbo_de_ponte_sobrevive_ao_salvar.py`."
    ),
    # sai com: AS-ISENCOES-QUE-ESPERAM-A-PALAVRA-DELA-01
    "teclado_emulado": (
        "Z4/T14 (24/08/2026), PROVISÓRIO — decisão dela em aberto (D-A do "
        "2026-08-24-ONDA0-Z4). O campo e a precedência pura "
        "(`profiles.schema.resolver_teclado_emulado`) já existem e têm "
        "testemunha própria em `test_z4_perfil_sem_modo.py`, mas NENHUM "
        "mixin escreve nele ainda — o widget é da Onda 9 (Emulação) e da "
        "Onda 10 (Navegação), e ligar o fio sem a palavra dela sobre a "
        "frase de tela seria escolher em silêncio (regra da casa). Este "
        "isento sai no dia em que o widget nascer — aí ele vira caso de "
        "ida e volta aqui, não isenção. "
        "METADE DISTO CADUCOU em 17/09/2026 (POINT-AND-CLICK-01), e a "
        "distinção importa: quem LÊ o campo já existe — "
        "`Daemon.aplicar_o_arranjo_do_desktop` chama "
        "`schema.resolver_teclado_emulado` ao entrar no modo Navegação. O que "
        "continua sem existir, e é o que esta isenção mede, é o MIXIN que "
        "escreve o campo no rascunho do perfil."
    ),
}

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

_SEM_ESCRITOR_HOJE: dict[str, str] = {}


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
    """As chaves (str) de um dicionário LITERAL de módulo."""
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


class _ColetorDeEscritas(ast.NodeVisitor):
    """Junta as chaves de ``model_copy(update={...})`` e os escritores nomeados."""

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
                    self.chaves.update(
                        sub.arg for sub in kw.value.keywords if sub.arg
                    )
        self.generic_visit(node)


def _vocabulario_de_escrita_da_janela(
    raiz: Path | None = None,
) -> tuple[set[str], set[str], set[str]]:
    """(chaves, escritores, classes) que a JANELA usa para escrever no rascunho."""
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
    """As seções do perfil que NENHUMA superfície da janela escreve."""
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
    """As seções que o esquema tem e a bancada não cobre. O miolo do portão."""
    return sorted(set(campos_do_esquema) - set(cobertas) - set(isentos))


class TestTodaSecaoDoPerfilTemIdaEVolta:
    """A lista de seções sai do esquema em RUNTIME, nunca de uma cópia."""

    def test_nenhuma_secao_do_perfil_fica_sem_caso(self) -> None:
        """Campo novo em ``Profile`` sem ida e volta reprova aqui."""
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
        """Seção removida do esquema não pode deixar caso órfão para trás."""
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


class TestORegistroNaoPodeSerDecorativo:
    """Um literal bonito satisfaria a pergunta 1 sem cobrir coisa nenhuma."""

    def test_cada_secao_coberta_tem_gesto_e_conferencia(self) -> None:
        """``SECOES_COBERTAS`` e ``_GESTOS`` têm de ter as mesmas chaves."""
        arvore = _arvore(_IRMAO)
        cobertas = set(_chaves_de_dicionario_literal(arvore, "SECOES_COBERTAS"))
        gestos = set(_funcoes_citadas_em_gestos(arvore))
        assert cobertas == gestos, (
            "o registro de ida e volta divergiu dos casos que rodam de fato — "
            f"só no literal: {sorted(cobertas - gestos)}; "
            f"só nos gestos: {sorted(gestos - cobertas)}"
        )

    def test_as_funcoes_citadas_existem_no_modulo_irmao(self) -> None:
        """Gesto e conferência nomeados no registro têm de existir."""
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
        """A descrição de cada seção não pode ser um enfeite vazio."""
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


class TestTodaSecaoTemEscritorNaJanela:
    """A metade de CIMA do caminho: o dedo dela chega ao rascunho?"""

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
        """Alguma superfície de ``app/`` escreve esta seção no rascunho?"""
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
        """Toda lacuna declarada tem razão longa, e é uma lacuna de verdade."""
        for campo, razao in _SEM_ESCRITOR_HOJE.items():
            assert campo in _SINAIS_DE_ESCRITOR, (
                f"{campo!r} está na lista de lacunas e não é seção vigiada"
            )
            assert len(razao) > 120, (
                f"a razão da lacuna de {campo!r} não diz onde o dado se perde: "
                f"{razao!r}"
            )


class TestOPortaoMorde:
    """Um portão que nunca reprovou é uma decoração com nome de portão."""

    def test_a_varredura_enxerga_as_escritas_que_existem(self) -> None:
        """A régua conferida contra contagem independente."""
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
        """A prova de que a lista de lacunas não é sempre vazia por construção."""
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
        """O miolo do portão de cobertura, apontado para um esquema FABRICADO."""
        cobertas = set(_chaves_de_dicionario_literal(_arvore(_IRMAO), "SECOES_COBERTAS"))
        inventado = {*Profile.model_fields, "gyro"}
        assert secoes_sem_ida_e_volta(inventado, cobertas, ISENTOS) == ["gyro"]
        assert secoes_sem_ida_e_volta(Profile.model_fields, cobertas, ISENTOS) == []

    def test_arrancar_um_escritor_da_copia_acusa_a_secao(self, tmp_path: Path) -> None:
        """A varredura de escritores, provada numa CÓPIA mutilada de ``app/``."""
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
        """Seção do perfil que passa pelo rascunho tem de estar vigiada aqui."""
        fora_do_rascunho = {"name", "match", "priority", *ISENTOS}
        esperadas = set(Profile.model_fields) - fora_do_rascunho
        vigiadas = set(_SINAIS_DE_ESCRITOR)
        assert esperadas == vigiadas, (
            "o conjunto de seções vigiadas por escritor divergiu do esquema — "
            f"sem vigia: {sorted(esperadas - vigiadas)}; "
            f"vigiadas a mais: {sorted(vigiadas - esperadas)}"
        )
