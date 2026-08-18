"""Merge do cmdline de kernel (PLAT-03 item 2) — o núcleo delicado.

ARMADILHA PROVADA (estudo 2026-07-18-estudo-kernel-hardening.md §1): o kernel
respeita SÓ UM token ``usbcore.quirks=`` no cmdline. Estes testes travam:

- máquina VIRGEM → plano adiciona os 2 params, dono "hefesto";
- máquina com Aurora (cmdline REAL do estudo) → plano é no-op, dono "terceiro";
- token de terceiro sem os nossos IDs → MERGE num token único ("compartilhado"),
  NUNCA um segundo token;
- caso patológico (2 tokens já no cmdline) → fundidos num só;
- flags mortas (``:k``) não sobrevivem nem são reintroduzidas;
- uninstall (strip) remove SÓ as entradas nossas, re-fundindo o resto.

Tudo com cmdline SINTÉTICO — nada de kernelstub/sistema real.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

# O cmdline REAL da máquina de referência (estudo §1) — Aurora já provê tudo.
CMDLINE_AURORA = (
    "initrd=\\EFI\\Pop_OS\\initrd.img root=UUID=7c6a1403 ro "
    "systemd.show_status=false loglevel=0 mitigations=off nvidia-drm.modeset=1 "
    "quiet usbcore.autosuspend=-1 acpi_enforce_resources=lax splash "
    "pcie_aspm=off nvidia-drm.fbdev=1 usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"
)

CMDLINE_VIRGEM = "quiet splash loglevel=0"


def _by_param(actions: list[kc.CmdlineAction]) -> dict[str, kc.CmdlineAction]:
    return {a.param: a for a in actions}


def _count_quirks_tokens(tokens: list[str]) -> int:
    return len(kc.tokens_for_param(tokens, kc.QUIRKS_PARAM))


class TestMaquinaVirgem:
    def test_adiciona_os_dois_params_como_hefesto(self) -> None:
        plano = _by_param(kc.plan_cmdline(CMDLINE_VIRGEM))
        auto = plano[kc.AUTOSUSPEND_PARAM]
        quirks = plano[kc.QUIRKS_PARAM]
        assert auto.op == kc.OP_ADD
        assert auto.token == "usbcore.autosuspend=-1"
        assert auto.owner == kc.OWNER_HEFESTO
        assert quirks.op == kc.OP_ADD
        assert quirks.token == "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"
        assert quirks.owner == kc.OWNER_HEFESTO

    def test_simulacao_produz_token_unico(self) -> None:
        tokens = kc.parse_cmdline(CMDLINE_VIRGEM)
        final = kc.apply_plan(tokens, kc.plan_tokens(tokens))
        assert _count_quirks_tokens(final) == 1
        assert "usbcore.autosuspend=-1" in final


class TestAuroraJaProve:
    def test_plano_e_noop_com_dono_terceiro(self) -> None:
        plano = _by_param(kc.plan_cmdline(CMDLINE_AURORA))
        for param in (kc.AUTOSUSPEND_PARAM, kc.QUIRKS_PARAM):
            assert plano[param].op == kc.OP_NONE, param
            assert plano[param].owner == kc.OWNER_TERCEIRO, param
            assert plano[param].remove_tokens == ()

    def test_simulacao_nao_muda_nada(self) -> None:
        tokens = kc.parse_cmdline(CMDLINE_AURORA)
        assert kc.apply_plan(tokens, kc.plan_tokens(tokens)) == tokens


class TestMergeTokenUnico:
    """A REGRA CRÍTICA: nunca 2 tokens usbcore.quirks=."""

    def test_token_de_terceiro_vira_merge_compartilhado(self) -> None:
        cmdline = "quiet usbcore.quirks=0bda:8153:k splash"
        plano = _by_param(kc.plan_cmdline(cmdline))
        quirks = plano[kc.QUIRKS_PARAM]
        assert quirks.op == kc.OP_REPLACE
        assert quirks.owner == kc.OWNER_COMPARTILHADO
        assert quirks.remove_tokens == ("usbcore.quirks=0bda:8153:k",)
        # Entrada do terceiro preservada NA FRENTE; as nossas apensadas.
        assert quirks.token == "usbcore.quirks=0bda:8153:k,054c:0ce6:gn,054c:0df2:gn"

    def test_nunca_dois_tokens_no_resultado(self) -> None:
        cenarios = [
            CMDLINE_VIRGEM,
            CMDLINE_AURORA,
            "usbcore.quirks=0bda:8153:k",
            "usbcore.quirks=054c:0ce6:gn",
            "usbcore.quirks=a:b:c usbcore.quirks=d:e:f",  # patológico
        ]
        for cmdline in cenarios:
            tokens = kc.parse_cmdline(cmdline)
            final = kc.apply_plan(tokens, kc.plan_tokens(tokens))
            assert _count_quirks_tokens(final) == 1, cmdline

    def test_dois_tokens_patologicos_sao_fundidos(self) -> None:
        cmdline = "usbcore.quirks=0bda:8153:k usbcore.quirks=1234:5678:g"
        plano = _by_param(kc.plan_cmdline(cmdline))
        quirks = plano[kc.QUIRKS_PARAM]
        assert quirks.op == kc.OP_REPLACE
        assert len(quirks.remove_tokens) == 2
        assert quirks.token == (
            "usbcore.quirks=0bda:8153:k,1234:5678:g,054c:0ce6:gn,054c:0df2:gn"
        )

    def test_id_parcialmente_presente_completa_sem_duplicar(self) -> None:
        cmdline = "usbcore.quirks=054c:0ce6:gn"
        plano = _by_param(kc.plan_cmdline(cmdline))
        quirks = plano[kc.QUIRKS_PARAM]
        assert quirks.token == "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"
        assert quirks.token.count("054c:0ce6") == 1


class TestFlagsMortas:
    """`054c:0ce6:k` foi removido DE PROPÓSITO (Aurora v3.24) — não volta."""

    def test_flag_k_do_dualsense_e_substituida_pela_provada(self) -> None:
        cmdline = "usbcore.quirks=054c:0ce6:k"
        plano = _by_param(kc.plan_cmdline(cmdline))
        quirks = plano[kc.QUIRKS_PARAM]
        assert "054c:0ce6:k," not in quirks.token + ","
        assert "054c:0ce6:gn" in quirks.token
        assert kc.forbidden_reintroductions(kc.plan_cmdline(cmdline)) == []

    def test_plano_nunca_reintroduz_banidos(self) -> None:
        for cmdline in (CMDLINE_VIRGEM, CMDLINE_AURORA, "usbcore.quirks=054c:0ce6:k"):
            assert kc.forbidden_reintroductions(kc.plan_cmdline(cmdline)) == []


class TestAutosuspendDivergente:
    def test_valor_diferente_e_substituido(self) -> None:
        plano = _by_param(kc.plan_cmdline("quiet usbcore.autosuspend=2"))
        auto = plano[kc.AUTOSUSPEND_PARAM]
        assert auto.op == kc.OP_REPLACE
        assert auto.remove_tokens == ("usbcore.autosuspend=2",)
        assert auto.token == "usbcore.autosuspend=-1"
        assert auto.owner == kc.OWNER_HEFESTO


class TestUninstallStrip:
    def test_strip_de_token_compartilhado_preserva_terceiro(self) -> None:
        token = "usbcore.quirks=0bda:8153:k,054c:0ce6:gn,054c:0df2:gn"
        restante, mudou = kc.strip_quirks_token(token)
        assert mudou
        assert restante == "usbcore.quirks=0bda:8153:k"

    def test_strip_de_token_so_nosso_deleta_inteiro(self) -> None:
        restante, mudou = kc.strip_quirks_token(
            "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"
        )
        assert mudou
        assert restante is None

    def test_strip_nao_toca_entrada_alterada_por_terceiro(self) -> None:
        # Alguém mudou as flags depois de nós — a entrada não é mais nossa.
        restante, mudou = kc.strip_quirks_token("usbcore.quirks=054c:0ce6:xyz")
        assert not mudou
        assert restante == "usbcore.quirks=054c:0ce6:xyz"


class TestRegistroDeDono:
    def test_chaves_do_estado_local(self) -> None:
        registro = kc.ownership_record(kc.plan_cmdline(CMDLINE_VIRGEM))
        assert registro == {
            "cmdline.usbcore.autosuspend": "hefesto",
            "cmdline.usbcore.quirks": "hefesto",
        }

    def test_aurora_registra_terceiro(self) -> None:
        registro = kc.ownership_record(kc.plan_cmdline(CMDLINE_AURORA))
        assert set(registro.values()) == {"terceiro"}
