"""NASCE-LIGADO-01 — nenhuma feature do perfil nasce muda, e nenhuma nasce calada.

**A ORDEM DELA, 17/09/2026:**

    *"os jogos e perfis tem que iniciar com todas as features ativadas por
    default."*

E a de 16/09, mais estreita, que nomeia os dois valores:

    *"botão de balanceado deveria ser pré setado em todo perfil sem config
    alterada. assim como os gatilhos deveriam vir como rigidos e os controles
    com tudo ativado por default"*  # noqa-acento: a digitação é dela

O QUE ESTA RÉGUA MEDE, E POR QUE ELA NÃO É UMA LISTA DE CATORZE
==============================================================================
Ela percorre `profiles/schema.py` por INTROSPECÇÃO — todo modelo pydantic
declarado no módulo, todo campo dele — e cobra de cada campo uma linha em
`schema.NASCIMENTO_DOS_CAMPOS` dizendo DE ONDE vem o valor quando o perfil cala.
Uma lista digitada de catorze protegeria os catorze de hoje e nenhum dos
próximos; é a forma de régua que esta casa já pagou onze vezes num dia só.

O PORQUÊ DE CADA AFIRMAÇÃO ESTAR SEPARADA
------------------------------------------------------------------------------
São quatro perguntas diferentes, e uma afirmação só passaria com três quartos
da cura no lugar:

1. **todo campo tem linha** — o campo novo que ninguém classificou reprova
   nomeando a si mesmo (`TestTodoCampoTemLinha`);
2. **o que nasce no esquema não nasce mudo** — e o "mudo" de cada campo é
   digitado AQUI, não lido do esquema (`TestOQueNasceNoEsquemaNaoNasceMudo`);
3. **quem promete nascer no leitor tem leitor** — o endereço resolve por
   import, e o leitor RESPONDE ligado (`TestOsDonosRespondemLigado`);
4. **o que espera a palavra dela é uma lista fechada** — parar um campo na
   fila dela exige declará-lo nos dois lugares (`TestAFilaDela`).

A TAUTOLOGIA QUE ESTA RÉGUA EVITA, e ela é a armadilha do dia
------------------------------------------------------------------------------
Uma régua que montasse o esperado a partir da MESMA constante que o produto lê
passaria com a cura arrancada. Por isso, aqui:

* o valor **mudo** de cada campo é digitado neste arquivo, e o valor de
  **nascimento** vem do esquema — divergir é o que reprova;
* os parâmetros do gatilho rígido são comparados com o DONO deles
  (`app/actions/trigger_specs`, que é quem a tela lê), nos DOIS sentidos;
* e o gatilho é medido no APARELHO: o efeito que o nascimento constrói tem de
  ser diferente do que `off()` constrói. Isso morde um defeito que esta casa
  já teve de verdade (TRIGGER-CANON-01: `Rigid` mandava o byte do OFF, e ela
  mediu *"rígido e desligado sem diferença"*) — um nascimento que só TROCASSE
  a palavra passaria pelas outras duas.
"""
from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest
from pydantic import BaseModel

from hefesto_dualsense4unix.app.actions.trigger_specs import (
    get_spec,
    preset_to_positional_params,
)
from hefesto_dualsense4unix.core.trigger_effects import build_from_name, off
from hefesto_dualsense4unix.profiles import schema as esquema


def _campos_vivos() -> dict[str, tuple[type[BaseModel], str]]:
    """Todo campo de todo modelo declarado em `profiles/schema.py`.

    Lido do módulo, nunca digitado: é isto que faz o campo 15 reprovar junto
    com os catorze de hoje.
    """
    achados: dict[str, tuple[type[BaseModel], str]] = {}
    for nome, obj in vars(esquema).items():
        if not inspect.isclass(obj) or not issubclass(obj, BaseModel):
            continue
        if obj is BaseModel or obj.__module__ != esquema.__name__:
            continue
        for campo in obj.model_fields:
            achados[f"{nome}.{campo}"] = (obj, campo)
    return achados


CAMPOS_VIVOS = _campos_vivos()


def _valor_de_nascimento(modelo: type[BaseModel], campo: str) -> Any:
    """O que o campo VALE quando ninguém opinou, ou `_SEM_DEFAULT`."""
    from pydantic_core import PydanticUndefined

    info = modelo.model_fields[campo]
    if info.default is not PydanticUndefined:
        return info.default
    if info.default_factory is not None:
        return info.default_factory()  # type: ignore[call-arg]
    return _SEM_DEFAULT


class _SemDefault:
    def __repr__(self) -> str:  # pragma: no cover - só aparece em mensagem de erro
        return "<sem default>"


_SEM_DEFAULT = _SemDefault()


#: Sentinela: o mudo deste campo não é um valor a digitar — quem responde é o
#: APARELHO, e a pergunta é "o efeito construído é o mesmo que `off()`?".
PERGUNTE_AO_APARELHO = object()


#: O que é NASCER MUDO, campo a campo — DIGITADO AQUI de propósito.
#:
#: O esquema guarda o nascimento; esta tabela guarda o silêncio. As duas
#: grafias são independentes, e é a divergência entre elas que reprova. Se este
#: dicionário fosse montado a partir do `schema`, arrancar a cura passaria.
#:
#: REPARE NO `False` do `suppress_desktop_emulation`: ali o mudo é `True`. Uma
#: régua que recusasse `False` em bloco reprovaria a feature LIGADA — é por
#: isso que o silêncio é por campo, e não uma regra geral.
O_QUE_E_MUDO: dict[str, Any] = {
    "LedsConfig.auto_player_colors": False,
    "LedsConfig.lightbar_brightness": 0.0,
    # O brilho das luzes de número não tem degrau apagado: os três acendem. O
    # silêncio deste campo é NÃO escolher — o produto sem o bit, que era o de
    # antes de 24/09/2026 (O-BRILHO-DAS-LUZES-DE-NUMERO-01).
    "LedsConfig.player_led_brightness": None,
    "Profile.suppress_desktop_emulation": True,
    "ProfileSpeakerConfig.muted": True,
    "RumbleConfig.passthrough": False,
    "TriggersConfig.left": PERGUNTE_AO_APARELHO,
    "TriggersConfig.right": PERGUNTE_AO_APARELHO,
}


#: A FILA DELA, fechada e digitada. Parar um campo aqui custa declará-lo nos
#: DOIS lugares — no esquema e neste arquivo —, que é o que impede alguém de
#: estacionar uma feature nova na fila dela sem ninguém ver.
#:
#: A sprint é explícita sobre o que NÃO se decide: *"Os demais — LED, sensores,
#: mouse, teclado — não têm valor decidido e não se inventa aqui."* Dos quatro,
#: três saíram da fila na triagem porque JÁ nascem ligados (ver
#: `TestOsDonosRespondemLigado`); o mouse ficou, e a razão é a assimetria
#: medida com o teclado.
A_FILA_DELA = frozenset(
    {
        "Profile.mouse",
        "ProfileMicConfig.volume",
    }
)


class TestTodoCampoTemLinha:
    """A primeira mordida: campo sem classificação reprova nomeando o campo."""

    @pytest.mark.parametrize("endereco", sorted(CAMPOS_VIVOS))
    def test_o_campo_esta_declarado(self, endereco: str) -> None:
        assert endereco in esquema.NASCIMENTO_DOS_CAMPOS, (
            f"{endereco} não tem linha em `NASCIMENTO_DOS_CAMPOS`. Todo campo "
            "deste esquema precisa dizer de onde vem o valor quando o perfil "
            "cala — e se a resposta for 'ninguém decidiu', isso também se "
            "declara, com `AGUARDA_A_PALAVRA_DELA` e o que falta."
        )

    def test_nao_ha_linha_para_campo_que_nao_existe(self) -> None:
        """Nos dois sentidos: campo podado deixa linha órfã, e linha órfã mente."""
        orfas = sorted(set(esquema.NASCIMENTO_DOS_CAMPOS) - set(CAMPOS_VIVOS))
        assert orfas == [], (
            f"{len(orfas)} linha(s) classificam campo que não existe mais: "
            f"{orfas}. A tabela passou a descrever o esquema de ontem."
        )

    @pytest.mark.parametrize("endereco", sorted(esquema.NASCIMENTO_DOS_CAMPOS))
    def test_a_linha_tem_estado_conhecido_e_razao_escrita(self, endereco: str) -> None:
        linha = esquema.NASCIMENTO_DOS_CAMPOS[endereco]
        conhecidos = {
            esquema.E_CONTRATO,
            esquema.E_OBRIGATORIO,
            esquema.E_SECAO,
            *esquema.PILHA_DAS_FEATURES,
        }
        assert linha.onde in conhecidos, (
            f"{endereco}: `{linha.onde}` não é um estado conhecido de nascimento."
        )
        assert linha.razao.strip(), (
            f"{endereco} foi classificado sem razão escrita. A sprint pede a "
            "razão em CADA um — classificar sem dizer por quê é a etiqueta sem "
            "a triagem."
        )


class TestOQueNasceNoEsquemaNaoNasceMudo:
    """A segunda mordida: o default deste arquivo é a opinião, e ele não cala."""

    @pytest.mark.parametrize(
        "endereco",
        sorted(
            k
            for k, v in esquema.NASCIMENTO_DOS_CAMPOS.items()
            if v.onde == esquema.NASCE_NO_ESQUEMA
        ),
    )
    def test_o_nascimento_nao_e_o_silencio(self, endereco: str) -> None:
        assert endereco in O_QUE_E_MUDO, (
            f"{endereco} promete nascer com opinião NO ESQUEMA, e este arquivo "
            "não diz o que seria nascer MUDO para ele. Sem o silêncio digitado "
            "aqui, a régua não tem contra o que comparar — e régua que se mede "
            "contra a própria saída não mede nada."
        )
        modelo, campo = CAMPOS_VIVOS[endereco]
        nasce = _valor_de_nascimento(modelo, campo)
        mudo = O_QUE_E_MUDO[endereco]
        if mudo is PERGUNTE_AO_APARELHO:
            # Aqui o silêncio não é um valor a digitar: quem responde é o
            # aparelho. `TestOGatilhoNasceRigidoDeVerdade` mede o mesmo por
            # outros dois canais — este caso existe para que o campo não
            # escape da varredura por ser especial.
            efeito = build_from_name(nasce.mode, nasce.params)
            assert efeito != off(), (
                f"{endereco} nasce com o modo {nasce.mode!r}, e o efeito que "
                f"ele constrói é idêntico ao de `off()`: {efeito!r}."
            )
            return
        assert nasce != mudo, (
            f"{endereco} nasce {nasce!r}, que é exatamente o silêncio deste "
            f"campo. A ordem dela de 17/09 é que nenhuma feature nasça sem "
            "opinião; se o valor mudou por decisão, mude também a linha deste "
            "campo em `O_QUE_E_MUDO` e escreva a razão no esquema."
        )


class TestOGatilhoNasceRigidoDeVerdade:
    """A cura desta sprint, medida em três canais que não conversam entre si."""

    def test_o_nascimento_nao_e_off(self) -> None:
        nascido = esquema.TriggersConfig()
        for lado in ("left", "right"):
            modo = getattr(nascido, lado).mode
            assert modo != "Off", (
                f"o gatilho {lado} voltou a nascer 'Off'. A decisão dela de "
                "16/09 é gatilho RÍGIDO em todo perfil sem configuração "
                "alterada, e esta é a única das catorze features que nascia "
                "muda de verdade."
            )

    def test_o_aparelho_ve_diferenca_entre_o_nascimento_e_o_desligado(self) -> None:
        """O oráculo é o efeito construído, não a palavra escrita no modo.

        TRIGGER-CANON-01: `Rigid` já mandou o byte `0x05`, que é o OFF do bloco
        de gatilho, e ela mediu *"rígido e desligado sem diferença"*. Um
        nascimento que só trocasse o nome do modo passaria pelo caso acima.
        """
        nascido = esquema.TriggersConfig()
        desligado = off()
        for lado in ("left", "right"):
            cfg = getattr(nascido, lado)
            efeito = build_from_name(cfg.mode, cfg.params)
            assert efeito != desligado, (
                f"o gatilho {lado} nasce com o modo {cfg.mode!r}, mas o efeito "
                f"que ele constrói é idêntico ao de `off()`: {efeito!r}. A "
                "palavra mudou e o aparelho não sentiu."
            )

    def test_os_parametros_saem_do_dono_deles(self) -> None:
        """Nos DOIS sentidos, contra quem a tela lê.

        `profiles/` não importa `app/` (nenhum módulo de `profiles/` ou
        `core/` o faz), então os dois números são digitados no esquema. É a
        mesma saída do `MascaraDeGamepad`, e o preço dela é esta comparação:
        divergir do dono reprova aqui.
        """
        spec = get_spec(esquema.MODO_DE_NASCIMENTO_DO_GATILHO)
        assert spec is not None, (
            f"o modo de nascimento {esquema.MODO_DE_NASCIMENTO_DO_GATILHO!r} "
            "não existe em `trigger_specs.PRESETS` — a tela não sabe desenhá-lo."
        )
        do_dono = preset_to_positional_params(spec, {})
        assert list(esquema.PARAMS_DE_NASCIMENTO_DO_GATILHO) == do_dono, (
            "os parâmetros de nascimento do gatilho divergiram do dono deles "
            f"(`app/actions/trigger_specs`): esquema={esquema.PARAMS_DE_NASCIMENTO_DO_GATILHO}, "
            f"dono={do_dono}. Quem mudar um muda o outro."
        )

    def test_o_perfil_recem_nascido_ja_chega_rigido(self) -> None:
        """O caminho que a pessoa percorre: perfil de jogo enxuto, sem seção.

        A afirmação é sobre o APARELHO de propósito. Comparar com
        `MODO_DE_NASCIMENTO_DO_GATILHO` seria montar o esperado com a mesma
        constante que o produto lê — passaria com a cura arrancada, que é
        exatamente o que este arquivo existe para não fazer.
        """
        perfil = esquema.Profile(
            name="um jogo qualquer",
            match=esquema.MatchCriteria(window_class=["steam_app_12345"]),
        )
        desligado = off()
        for lado in ("left", "right"):
            cfg = getattr(perfil.triggers, lado)
            assert build_from_name(cfg.mode, cfg.params) != desligado, (
                f"o perfil de jogo recém-criado chega com o gatilho {lado} "
                "sem resistência nenhuma — é o caminho que a pessoa percorre "
                "sem tocar em nada, e é dele que a ordem dela fala."
            )

    def test_o_perfil_que_ela_configurou_continua_mandando(self) -> None:
        """A trava do alcance: nascimento não pisa em escolha gravada.

        `loader.save_profile` grava a seção `triggers` DENSA, então o perfil
        que ela configurou carrega a escolha dela no arquivo. Um nascimento
        que vencesse o disco apagaria trabalho dela — é o oposto do pedido.
        """
        perfil = esquema.Profile(
            name="o que ela deixou solto",
            match=esquema.MatchAny(),
            triggers=esquema.TriggersConfig(left=esquema.TriggerConfig(mode="Off")),
        )
        assert perfil.triggers.left.mode == "Off", (
            "o nascimento pisou no `Off` que o perfil declarou. Um default "
            "que vence o disco apaga trabalho dela."
        )
        direito = perfil.triggers.right
        assert build_from_name(direito.mode, direito.params) != off(), (
            "o lado que o perfil NÃO declarou deixou de herdar o nascimento."
        )


class TestOsDonosRespondemLigado:
    """Quem promete nascer NO LEITOR tem leitor, e o leitor responde ligado."""

    @pytest.mark.parametrize(
        "endereco",
        sorted(
            k
            for k, v in esquema.NASCIMENTO_DOS_CAMPOS.items()
            if v.onde in (esquema.NASCE_NO_LEITOR, esquema.NASCE_NA_ADOCAO)
        ),
    )
    def test_o_dono_declarado_resolve(self, endereco: str) -> None:
        """Endereço que ninguém abre envelhece calado — este abre todos."""
        linha = esquema.NASCIMENTO_DOS_CAMPOS[endereco]
        assert linha.dono, (
            f"{endereco} diz que o nascimento mora em outro lugar e não diz "
            "ONDE. Sem o endereço, a classificação é uma promessa."
        )
        modulo, _, simbolo = linha.dono.partition(":")
        assert simbolo, f"{endereco}: `dono` precisa da forma `módulo:símbolo`."
        alvo = importlib.import_module(modulo)
        assert hasattr(alvo, simbolo), (
            f"{endereco}: `{linha.dono}` não existe mais. O dono do "
            "nascimento mudou de endereço e esta linha ficou apontando para o "
            "mundo de ontem."
        )

    def test_a_vibracao_ja_nasce_balanceada(self) -> None:
        """O achado que derrubou o enunciado da sprint.

        A sprint contava a vibração entre as features mudas lendo `policy=None`
        no esquema. O canal certo é o LEITOR: `policy=None` é o perfil dizendo
        *não mexo*, e a política global que segue valendo nasce balanceada.
        """
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        assert DaemonConfig().rumble_policy == "balanceado"
        assert esquema.RumbleConfig().policy is None, (
            "encher este default faria TODA ativação de perfil IMPOR "
            "balanceado, e a escolha manual dela seria desfeita na primeira "
            "troca de janela depois da trava de 30 s. Se isto mudar, é "
            "decisão dela — e a linha do campo tem de mudar junto."
        )

    def test_os_dois_sensores_nascem_de_pe(self) -> None:
        from hefesto_dualsense4unix.core.virtual_motion import EstadoDosSensores

        estado = EstadoDosSensores()
        assert estado.giroscopio is True
        assert estado.acelerometro is True

    def test_o_microfone_nasce_no_ar(self) -> None:
        from hefesto_dualsense4unix.integrations.plano_de_radio import (
            microfone_nasce_ligado,
        )

        assert microfone_nasce_ligado() is True

    def test_o_teclado_emulado_nasce_ligado(self) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        assert DaemonConfig().keyboard_emulation_enabled is True

    def test_a_mascara_nasce_dualsense(self) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        assert DaemonConfig().gamepad_flavor == "dualsense"

    def test_a_fonte_do_no_nasce_sfx(self) -> None:
        """O modelo que a sprint mandou copiar: default com justificativa ao lado."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_SFX

        assert esquema.ProfileSpeakerConfig(volume=100).fonte is None
        assert FONTE_SFX == "sfx"

    def test_a_barra_e_o_numero_nascem_acesos(self) -> None:
        assert esquema.LedsConfig().auto_player_colors is True


class TestAFilaDela:
    """O que espera a palavra dela é lista FECHADA, e cada item diz o que falta."""

    def test_a_fila_e_exatamente_a_declarada(self) -> None:
        do_esquema = frozenset(
            k
            for k, v in esquema.NASCIMENTO_DOS_CAMPOS.items()
            if v.onde == esquema.AGUARDA_A_PALAVRA_DELA
        )
        assert do_esquema == A_FILA_DELA, (
            "a fila dela mudou sem ninguém declarar nos dois lugares. "
            f"no esquema: {sorted(do_esquema)}; neste arquivo: "
            f"{sorted(A_FILA_DELA)}. Estacionar uma feature em "
            "`AGUARDA_A_PALAVRA_DELA` é a única saída que esta régua deixa — "
            "e ela custa uma linha aqui de propósito."
        )

    @pytest.mark.parametrize("endereco", sorted(A_FILA_DELA))
    def test_cada_espera_diz_o_que_falta(self, endereco: str) -> None:
        linha = esquema.NASCIMENTO_DOS_CAMPOS[endereco]
        assert linha.falta.strip(), (
            f"{endereco} espera a palavra dela e não diz O QUE perguntar. Uma "
            "fila sem a pergunta escrita é uma feature esquecida com nome bonito."
        )

    def test_a_assimetria_que_poe_o_mouse_na_fila_continua_de_pe(self) -> None:
        """A razão do `Profile.mouse` estar parado é medida, não opinião.

        Os dois interruptores são vizinhos na mesma aba e nascem ao contrário
        um do outro. Se o daemon passar a ligar o mouse, este caso reprova e a
        linha do campo sai da fila dela.
        """
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        cfg = DaemonConfig()
        assert cfg.mouse_emulation_enabled is False
        assert cfg.keyboard_emulation_enabled is True
