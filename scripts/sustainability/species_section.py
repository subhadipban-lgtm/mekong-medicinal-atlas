"""Species-page Sustainability section for the atlas generator.

build_site.py calls render(d, sid) and embeds the returned HTML; this keeps the quoting of the
section's HTML out of the page templates.
"""
from __future__ import annotations

import html


def _e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render(d: dict, sid: str) -> str:
    hp = d["sust_pressure_by"].get(sid)
    hy = d["sust_hydro_by"].get(sid)
    sdm = d["sust_sdm_by"].get(sid)
    cult = d["sust_cult_by"].get(sid)
    rows = []
    if sdm and sdm.get("projected_range_change_pct"):
        rows.append(
            '<tr><th scope="row">Climate vulnerability</th>'
            f'<td>{_e(sdm.get("climate_vulnerability_tier", "—"))}</td>'
            f'<td>projected range change {_e(sdm.get("projected_range_change_pct"))}% (conditional scenario projection)</td></tr>')
    elif not d["sust_sdm"]:
        rows.append('<tr><th scope="row">Climate vulnerability</th><td>in progress</td>'
                    '<td>SDM analysis in progress; see the Sustainability page</td></tr>')
    else:
        rows.append(
            '<tr><th scope="row">Climate vulnerability</th>'
            f'<td>{_e(sdm.get("climate_vulnerability_tier", "not assessed"))}</td>'
            '<td>fewer than 10 in-basin records — insufficient data for SDM</td></tr>')
    if cult:
        rows.append(
            '<tr><th scope="row">Cultivation feasibility</th>'
            f'<td>{_e(cult.get("cultivation_feasibility_class", "—"))}</td>'
            f'<td>{_e(cult.get("cultivation_feasible_area_km2", ""))} km&sup2; feasible (screening)</td></tr>')
    else:
        rows.append('<tr><th scope="row">Cultivation feasibility</th><td>in progress</td><td>analysis in progress</td></tr>')
    if hp:
        rows.append(
            '<tr><th scope="row">Harvest pressure</th>'
            f'<td>{_e(hp["harvest_pressure_class"])}</td>'
            f'<td>mean proxy {_e(hp["mean_harvest_pressure_in_range"])} across {_e(hp["n_cells"])} cells; '
            'a proxy, not measured offtake</td></tr>')
    else:
        rows.append('<tr><th scope="row">Harvest pressure</th><td>—</td>'
                    '<td>no use records in the atlas, so the taxon is outside the index</td></tr>')
    if hy:
        rows.append(
            '<tr><th scope="row">Hydrological vulnerability</th>'
            f'<td>{_e(hy["hydrological_vulnerability_class"])}</td>'
            f'<td>{_e(hy["pct_within_10km_major_dam"])}% of {_e(hy["n_occurrences_in_basin"])} in-basin records '
            'within 10 km of a major dam (distance-based proxy)</td></tr>')
    else:
        rows.append('<tr><th scope="row">Hydrological vulnerability</th><td>not assessed</td><td>no in-basin records</td></tr>')
    return ('<details class="mt-3"><summary class="h5 section-title" style="display:list-item">Harvest pressure &amp; hydrological risk</summary>'
            '<p class="small text-muted">Screening layers from the hydroclimatic synthesis of Tiwari et al. 2023 '
            '(<a href="https://doi.org/10.5281/zenodo.7803254" target="_blank" rel="noopener">Zenodo 7803254</a>); '
            'methods are linked from the <a href="sustainability.html">Harvest pressure &amp; hydrological risk page</a>.</p>'
            '<div class="table-responsive"><table class="table table-sm table-atlas"><tbody>'
            + "".join(rows) + '</tbody></table></div></details>')
