"""Read-only inspection of installed browser matrix declarations and identities."""

from veriagent.browser_catalog import CONTROL_CATALOG
from veriagent.browser_controls import control_budget, matrix_contract


def inspect_browser_matrices(matrix_ids: tuple[str, ...] | None = None) -> dict:
    catalog = {matrix.name: matrix for matrix in CONTROL_CATALOG}
    selected = tuple(catalog) if matrix_ids is None else matrix_ids
    if (
        not 1 <= len(selected) <= len(catalog)
        or len(set(selected)) != len(selected)
        or any(name not in catalog for name in selected)
    ):
        raise ValueError("Select unique installed browser matrix names")
    rows = []
    for name in selected:
        definition = catalog[name]
        rows.append(
            {
                "matrix": name,
                "description": definition.description,
                "cli_option": definition.cli_option,
                "control_count": definition.control_count,
                "batch_count": len(definition.batches),
                "requires_budget_metadata": definition.requires_budget_metadata,
                "matrix_contract": matrix_contract(definition),
                "batches": [
                    {
                        "tasks": spec["tasks"],
                        "scenarios": spec["scenarios"],
                        "modes": spec["modes"],
                        "budget": control_budget(spec).model_dump(mode="json"),
                    }
                    for spec in definition.specs()
                ],
            }
        )
    return {
        "schema_version": 1,
        "installed_matrix_count": len(catalog),
        "selected_matrices": list(selected),
        "control_count": sum(row["control_count"] for row in rows),
        "matrices": rows,
        "limitations": "Unsigned installed declarations; no evaluations were run.",
    }


def render_matrix_inspection(result: dict) -> str:
    lines = [
        "Installed browser matrix contracts",
        f"Selected: {len(result['matrices'])}/{result['installed_matrix_count']} matrices; "
        f"{result['control_count']} controls",
    ]
    for row in result["matrices"]:
        option = row["cli_option"] or "default selection"
        identity = row["matrix_contract"]
        batches = "batch" if row["batch_count"] == 1 else "batches"
        lines.extend(
            [
                f"- {row['matrix']}: {row['control_count']} controls, "
                f"{row['batch_count']} {batches} ({option})",
                f"  Contract v{identity['version']}: {identity['sha256']}",
            ]
        )
    return "\n".join(lines + ["", result["limitations"]]) + "\n"
