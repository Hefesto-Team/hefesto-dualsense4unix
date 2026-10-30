"""Z4/T13+T14 — o modo que falta, e o teclado que ganha campo de perfil."""

from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.profiles.schema import Profile, resolver_teclado_emulado

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES_SINTETICOS = RAIZ / "tests" / "fixtures" / "perfis_do_ciclo" / "sinteticos"
SEM_MODE_COM_MIC = FIXTURES_SINTETICOS / "jogo_ficticio_sem_modo_com_mic.json"
OS_SEM_MODE = frozenset(
    {
        "bow.json",
        "fallback.json",
        "fps.json",
        "jogo_ficticio_nome_com_dois_pontos.json",
        "jogo_ficticio_nome_com_ponto.json",
        "jogo_ficticio_nome_em_caixa_alta.json",
        "jogo_ficticio_sem_modo.json",
        "jogo_ficticio_sem_modo_com_mic.json",
        "navegacao.json",
        "point_and_click.json",
    }
)


class TestOsPerfisSemModo:
    """T13 — a medição da §2.2, reproduzida contra o corpo de prova sintético."""

    def test_o_perfil_com_mic_nao_tem_mode(self) -> None:
        dados = json.loads(SEM_MODE_COM_MIC.read_text())
        assert "mode" not in dados, (
            f"{SEM_MODE_COM_MIC.name} ganhou `mode` — migração automática do "
            "corpo de prova é proibida pela sprint ('não migre os 22 "
            "automaticamente'); o perfil sem a seção é a forma que se mede"
        )

    def test_os_sem_mode_sao_os_que_o_corpo_de_prova_garante(self) -> None:
        sem_mode = set()
        for f in sorted(FIXTURES_SINTETICOS.glob("*.json")):
            if f.name.startswith("z_fabricado_"):
                continue
            dados = json.loads(f.read_text())
            if "mode" not in dados:
                sem_mode.add(f.name)
        assert sem_mode == OS_SEM_MODE, (
            f"o corpo de prova garante {len(OS_SEM_MODE)} perfis sem `mode`; "
            f"sobraram {sorted(OS_SEM_MODE - sem_mode)!r} sem a forma e "
            f"apareceram {sorted(sem_mode - OS_SEM_MODE)!r} — migração no "
            "corpo de prova apaga a forma que a T13 mede"
        )

    def test_perfil_sem_mode_nao_tem_opiniao_sobre_o_modo(self) -> None:
        """Perfil sem a seção `mode` não opina sobre modo nenhum."""
        for nome in sorted(OS_SEM_MODE):
            dados = json.loads((FIXTURES_SINTETICOS / nome).read_text())
            assert Profile.model_validate(dados).mode is None, nome


class TestAPrecedenciaDoTecladoEmulado:
    """T14 — perfil vence a flag; perfil sem opinião não apaga a flag."""

    def _perfil(self, *, teclado_emulado: bool | None) -> Profile:
        from hefesto_dualsense4unix.profiles.schema import MatchCriteria

        return Profile(
            name="z4-t14",
            match=MatchCriteria(window_class=["steam_app_0"]),
            priority=1,
            teclado_emulado=teclado_emulado,
        )

    def test_perfil_sem_opiniao_deixa_a_flag_mandar(self) -> None:
        perfil = self._perfil(teclado_emulado=None)
        assert resolver_teclado_emulado(perfil, flag_global=True) is True
        assert resolver_teclado_emulado(perfil, flag_global=False) is False

    def test_perfil_com_opiniao_vence_a_flag_ligada(self) -> None:
        perfil = self._perfil(teclado_emulado=False)
        assert resolver_teclado_emulado(perfil, flag_global=True) is False, (
            "a flag global venceu o perfil — é o inverso do que a D-A pede "
            "('perfil com opinião vence a flag')"
        )

    def test_perfil_com_opiniao_vence_a_flag_desligada(self) -> None:
        perfil = self._perfil(teclado_emulado=True)
        assert resolver_teclado_emulado(perfil, flag_global=False) is True

    def test_sem_perfil_ativo_a_flag_manda(self) -> None:
        assert resolver_teclado_emulado(None, flag_global=True) is True
        assert resolver_teclado_emulado(None, flag_global=False) is False

    def test_o_campo_e_opcional_e_perfis_existentes_continuam_validos(self) -> None:
        """Aditivo — nenhum perfil do corpo de prova sintético tem o campo."""
        arquivos = sorted(FIXTURES_SINTETICOS.glob("*.json"))
        assert len(arquivos) == 24, f"o corpo de prova tem 24 perfis, achei {len(arquivos)}"
        for f in arquivos:
            dados = json.loads(f.read_text())
            assert "teclado_emulado" not in dados
            perfil = Profile.model_validate(dados)
            assert perfil.teclado_emulado is None
