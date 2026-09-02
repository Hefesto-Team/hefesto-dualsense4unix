"""Z4/T13+T14 — o modo que falta, e o teclado que ganha campo de perfil.

Frente **Z4** da ONDA 0 (24/08/2026).

**T13** — medido na sprint (§2.2): 22 dos 34 perfis dela não têm `mode`, e
`sackboy.json` é o caso que ela nomeou. A PERGUNTA que falta responder —
"o que a TELA diz ao ativar um perfil sem `mode`" — é **[ESTRUTURAL]**: texto
novo de interface, e a regra da casa (`COMO-EXECUTAR-UMA-SPRINT.md` §8) é
"escolha em silêncio vira fato consumado que ela descobre na tela". Este
módulo não escreve essa frase — só prova, campo a campo, que a MEDIÇÃO
continua batendo (o número muda se o corpo de prova mudar, e este teste
acusa antes de alguém confiar num "22" que envelheceu).

**T14** — o campo `Profile.teclado_emulado` e a função pura
`resolver_teclado_emulado` (`profiles/schema.py`). O contrato: perfil SEM
opinião (`None`) deixa a flag global mandar; perfil COM opinião vence —
inclusive quando a opinião é "desligado" e a flag está ligada (a mesma
proteção do `mic.muted`, MIC-GRAVACAO-01: perfil sem opinião nunca apaga o
que já valia). **Nenhum widget foi ligado** — é a régua e o campo, não o fio
(ver a nota datada em `Profile.teclado_emulado`).
"""

from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.profiles.schema import Profile, resolver_teclado_emulado

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES_REAIS = RAIZ / "tests" / "fixtures" / "perfis_do_ciclo" / "reais"


class TestOsVinteEDoisSemModo:
    """T13 — a medição da §2.2, reproduzida contra o corpo de prova (T1)."""

    def test_sackboy_nao_tem_mode(self) -> None:
        dados = json.loads((FIXTURES_REAIS / "sackboy.json").read_text())
        assert "mode" not in dados, (
            "sackboy.json ganhou `mode` — se foi migração automática, ela é "
            "proibida pela sprint ('não migre os 22 automaticamente'); se foi "
            "escolha dela pela tela, este teste está desatualizado, não errado"
        )

    def test_a_contagem_dos_sem_mode_bate_com_a_sprint(self) -> None:
        sem_mode = []
        for f in sorted(FIXTURES_REAIS.glob("*.json")):
            if f.name.startswith("z_fabricado_"):
                continue  # sintéticos da T1, fora da amostra dela
            dados = json.loads(f.read_text())
            if "mode" not in dados:
                sem_mode.append(f.name)
        assert len(sem_mode) == 22, (
            f"{len(sem_mode)} perfis sem `mode` — a sprint mediu 22 em "
            f"24/08/2026 contra os mesmos 34; achei {sorted(sem_mode)!r}. Se "
            "o número mudou, é bom (alguém já decidiu por ela) — mas a T13 "
            "segue aberta até a frase de tela existir."
        )

    def test_perfil_sem_mode_nao_tem_opiniao_sobre_o_modo(self) -> None:
        """Perfil sem a seção `mode` não opina sobre modo nenhum.

        É a consequência que importa: ativar um perfil assim libera só o modo
        que outro PERFIL tinha ligado, e não desfaz gesto manual dela.
        """
        dados = json.loads((FIXTURES_REAIS / "sackboy.json").read_text())
        perfil = Profile.model_validate(dados)
        assert perfil.mode is None


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
        """Aditivo — nenhum dos 46 perfis do corpo de prova (T1) tem
        `teclado_emulado`, e todos continuam validando."""
        for f in sorted(FIXTURES_REAIS.glob("*.json")):
            dados = json.loads(f.read_text())
            assert "teclado_emulado" not in dados
            perfil = Profile.model_validate(dados)
            assert perfil.teclado_emulado is None
