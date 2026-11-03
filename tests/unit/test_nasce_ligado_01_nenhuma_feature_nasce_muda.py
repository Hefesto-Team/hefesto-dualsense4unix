"""NASCE-LIGADO-01 — nenhuma feature do perfil nasce muda, e nenhuma nasce calada."""
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
    """Todo campo de todo modelo declarado em `profiles/schema.py`."""
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
    def __repr__(self) -> str:  # pragma: no cover
        return "<sem default>"


_SEM_DEFAULT = _SemDefault()


O_QUE_E_MUDO: dict[str, Any] = {
    "ControllerSensoresOverride.touchpad": "desligado",
    "LedsConfig.auto_player_colors": False,
    "LedsConfig.lightbar_brightness": 0.0,
    "LedsConfig.player_led_brightness": None,
    "Profile.suppress_desktop_emulation": True,
    "ProfileSpeakerConfig.muted": True,
    "RumbleConfig.passthrough": False,
}


A_FILA_DO_USUARIO = frozenset(
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
            "declara, com `AGUARDA_A_PALAVRA_DO_USUARIO` e o que falta."
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
        assert nasce != mudo, (
            f"{endereco} nasce {nasce!r}, que é exatamente o silêncio deste "
            f"campo. A ordem de 17/09 é que nenhuma feature nasça sem "
            "opinião; se o valor mudou por decisão, mude também a linha deste "
            "campo em `O_QUE_E_MUDO` e escreva a razão no esquema."
        )


class TestOGatilhoNasceNoTraco:
    """D-0311-A-LISTA-SEM-ESCOLHA-SEGUE-O-ESTILO-DO-PERFIL: o gatilho novo nasce no «—»."""

    def test_o_nascimento_e_o_off_que_o_aparelho_sente(self) -> None:
        nascido = esquema.TriggersConfig()
        for lado in ("left", "right"):
            cfg = getattr(nascido, lado)
            assert cfg.mode == "Off", f"o gatilho {lado} nasce {cfg.mode!r}, e não no «—»"
            assert build_from_name(cfg.mode, cfg.params) == off()

    def test_o_gatilho_nasce_por_contrato_e_nao_no_esquema(self) -> None:
        for lado in ("left", "right"):
            linha = esquema.NASCIMENTO_DOS_CAMPOS[f"TriggersConfig.{lado}"]
            assert linha.onde == esquema.E_CONTRATO

    def test_os_parametros_saem_do_dono_deles(self) -> None:
        """Nos DOIS sentidos, contra quem a tela lê."""
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

    def test_o_perfil_recem_nascido_chega_no_traco(self) -> None:
        """O caminho que a pessoa percorre: perfil de jogo enxuto, sem seção."""
        perfil = esquema.Profile(
            name="um jogo qualquer",
            match=esquema.MatchCriteria(window_class=["steam_app_12345"]),
        )
        for lado in ("left", "right"):
            cfg = getattr(perfil.triggers, lado)
            assert build_from_name(cfg.mode, cfg.params) == off()

    def test_o_perfil_que_o_usuario_configurou_continua_mandando(self) -> None:
        """A trava do alcance: nascimento não pisa em escolha gravada."""
        perfil = esquema.Profile(
            name="o que ficou solto",
            match=esquema.MatchAny(),
            triggers=esquema.TriggersConfig(
                left=esquema.TriggerConfig(mode="Rigid", params=[5, 200])),
        )
        assert (perfil.triggers.left.mode, perfil.triggers.left.params) == ("Rigid", [5, 200]), (
            "o nascimento pisou no gatilho que o perfil declarou. Um default "
            "que vence o disco apaga trabalho do usuário."
        )
        direito = perfil.triggers.right
        assert build_from_name(direito.mode, direito.params) == off(), (
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
        """O achado que derrubou o enunciado da sprint."""
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        assert DaemonConfig().rumble_policy == "balanceado"
        assert esquema.RumbleConfig().policy is None, (
            "encher este default faria TODA ativação de perfil IMPOR "
            "balanceado, e a escolha manual do usuário seria desfeita na primeira "
            "troca de janela depois da trava de 30 s. Se isto mudar, é "
            "decisão de produto — e a linha do campo tem de mudar junto."
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


class TestAFilaDoUsuario:
    """O que espera a palavra de produto é lista FECHADA, e cada item diz o que falta."""

    def test_a_fila_e_exatamente_a_declarada(self) -> None:
        do_esquema = frozenset(
            k
            for k, v in esquema.NASCIMENTO_DOS_CAMPOS.items()
            if v.onde == esquema.AGUARDA_A_PALAVRA_DO_USUARIO
        )
        assert do_esquema == A_FILA_DO_USUARIO, (
            "a fila do usuário mudou sem ninguém declarar nos dois lugares. "
            f"no esquema: {sorted(do_esquema)}; neste arquivo: "
            f"{sorted(A_FILA_DO_USUARIO)}. Estacionar uma feature em "
            "`AGUARDA_A_PALAVRA_DO_USUARIO` é a única saída que esta régua deixa — "
            "e essa saída custa uma linha aqui de propósito."
        )

    @pytest.mark.parametrize("endereco", sorted(A_FILA_DO_USUARIO))
    def test_cada_espera_diz_o_que_falta(self, endereco: str) -> None:
        linha = esquema.NASCIMENTO_DOS_CAMPOS[endereco]
        assert linha.falta.strip(), (
            f"{endereco} espera a palavra do usuário e não diz O QUE perguntar. Uma "
            "fila sem a pergunta escrita é uma feature esquecida com nome bonito."
        )

    def test_a_assimetria_que_poe_o_mouse_na_fila_continua_de_pe(self) -> None:
        """A razão do `Profile.mouse` estar parado é medida, não opinião."""
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        cfg = DaemonConfig()
        assert cfg.mouse_emulation_enabled is False
        assert cfg.keyboard_emulation_enabled is True
