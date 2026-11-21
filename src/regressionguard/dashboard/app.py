"""Painel opcional (Streamlit) sobre o DuckDB: lista de runs, comparacao e casos regredidos.

Execucao: `streamlit run src/regressionguard/dashboard/app.py` a partir da raiz do repositorio.
Variaveis opcionais: REGRESSIONGUARD_DB (por omissao regressionguard.duckdb) e
REGRESSIONGUARD_GATES (por omissao config/gates.yaml).

O painel nao escreve nada e nao executa rollbacks: mostra a recomendacao gravada na comparacao.
A base de dados abre-se e fecha-se em cada pedido, para nao manter o ficheiro bloqueado.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from regressionguard.comparison.engine import ComparisonError, compare
from regressionguard.comparison.gates import load_gates
from regressionguard.store.duck import RunStore

DB_PATH = Path(os.environ.get("REGRESSIONGUARD_DB", "regressionguard.duckdb"))
GATES_PATH = Path(os.environ.get("REGRESSIONGUARD_GATES", "config/gates.yaml"))


def _pct(value: float | None) -> str:
    return "n/d" if value is None else f"{value * 100:.1f}%"


def _list_runs() -> list[dict]:
    with RunStore(DB_PATH) as store:
        return store.list_runs()


def _load(run_id: str):
    with RunStore(DB_PATH) as store:
        return store.load_run(run_id)


def main() -> None:
    st.set_page_config(page_title="RegressionGuard", layout="wide")
    st.title("RegressionGuard")
    if not DB_PATH.exists():
        st.info(f"Ainda nao existe base de dados em {DB_PATH}. Corra `ai-eval run` primeiro.")
        return

    runs = _list_runs()
    if not runs:
        st.info("Sem runs guardadas.")
        return
    st.subheader("Runs")
    st.dataframe(runs, use_container_width=True)

    ids = [row["run_id"] for row in runs]
    left, right = st.columns(2)
    baseline_id = left.selectbox("Baseline", ids, index=0)
    candidate_id = right.selectbox("Candidato", ids, index=len(ids) - 1)
    if baseline_id == candidate_id:
        st.info("Escolha duas runs diferentes para comparar.")
        return

    try:
        report = compare(_load(baseline_id), _load(candidate_id), load_gates(GATES_PATH))
    except ComparisonError as exc:
        st.error(str(exc))
        return

    st.subheader("Comparacao")
    cols = st.columns(4)
    cols[0].metric("Sucesso baseline", _pct(report.pass_rate_baseline))
    cols[1].metric(
        "Sucesso candidato",
        _pct(report.pass_rate_candidate),
        f"{report.pass_rate_diff * 100:+.1f} pp",
    )
    cols[2].metric("IC 95% (diferenca)", f"[{report.ci_low:+.3f}, {report.ci_high:+.3f}]")
    cols[3].metric("Casos regredidos", len(report.regressions))
    for warning in report.warnings:
        st.warning(warning)
    if report.insufficient_sample_size:
        st.warning("Comparacao nao conclusiva: " + "; ".join(report.insufficient_reasons))

    st.markdown("**Gates**")
    st.dataframe(
        [
            {
                "gate": g.name,
                "severidade": g.severity,
                "valor": g.value,
                "limiar": g.threshold,
                "resultado": "nao avaliavel"
                if g.passed is None
                else ("ok" if g.passed else "falhou"),
            }
            for g in report.gates
        ],
        use_container_width=True,
    )
    if report.recommendation.get("action") == "rollback":
        st.error(
            f"Recomendacao: rollback para {report.recommendation['rollback_to']['run_id']}. "
            "Nenhum rollback foi executado."
        )

    st.markdown("**Segmentos**")
    st.dataframe(
        [
            {
                "categoria": k,
                "n": v["n"],
                "baseline": v["baseline"],
                "candidato": v["candidate"],
                "diff": v["diff"],
            }
            for k, v in report.by_category.items()
        ],
        use_container_width=True,
    )

    st.markdown("**Casos regredidos** (passavam no baseline e falham no candidato)")
    for entry in report.regressions:
        label = f"{entry.case_id} [{entry.severity}] {', '.join(entry.reasons) or 'falha'}"
        with st.expander(label):
            st.write("Entrada")
            st.code(str(entry.input))
            left, right = st.columns(2)
            left.write("Saida do baseline")
            left.code(entry.baseline_output or "(vazia)")
            right.write("Saida do candidato")
            right.code(entry.candidate_output or "(vazia)")
            st.write(
                "Avaliadores que falharam: " + (", ".join(entry.failed_evaluators) or "nenhum")
            )


main()
