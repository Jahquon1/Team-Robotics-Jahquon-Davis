import json
import math
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Team Robotics | Career Venture Lab (ROB-2)",
    layout="wide",
)

# --- Constants & Defaults (ROB-2 Precalculus Advanced) ---
TEAM_ID = "Team Robotics"
COURSE = "Precalculus"
PATHWAY_ID = "ROB-2"
DEFAULT_LEVEL = "Advanced"

def to_money(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def default_state() -> dict:
    return {
        "team_id": TEAM_ID,
        "course": COURSE,
        "pathway_id": PATHWAY_ID,
        "selected_level": DEFAULT_LEVEL,
        "teacher_approved_level": True,
        "snapshot_id": "SNAP-000",
        "state_version": 0,
        "simulation_date": "2026-12-31",
        "base_period": "monthly",
        "working_days": 22,
        "currency": "USD",
        "random_seed": 2027,
        "inputs": {
            "base_price": 120.00,
            "D0": 40,
            "staff_hours": 90.0,
            "hours_per_unit": 3.0,
            "opening_cash": 5000.00,
            "opening_stock_units": 100,
            "component_unit_cost": 30.00,
            "restock_units": 0,
            "defect_rate": 0.0,
            "refund_amount": 0.00,
            "loan_principal": 0.00,
            "interest": 0.00,
            "additional_capex": 0.00,
        },
        "startup": {
            "owner_contribution": 12000.00,
            "equipment_assets": 4000.00,
            "pre_opening_expense": 0.00,
            "opening_inventory": 3000.00,
            "post_startup_cash": 5000.00,
            "retained_earnings": 0.00,
        },
        "variable_lines": {
            "components_COGS": 30.00,
            "assembly_labor": 20.00,
            "packaging": 10.00,
            "warranty_consumables": 5.00,
        },
        "fixed_lines": {
            "workspace": 250.00,
            "software": 100.00,
            "equipment_maintenance": 150.00,
            "admin": 100.00,
        },
        "cash": 5000.00,
        "stock_units": 100,
        "debt": 0.00,
        "equipment_net": 4000.00,
        "retained_earnings": 0.00,
        "ledger": [],
        "processed_run_ids": [],
        "recommendations": [],
        "decisions": [],
        "advanced_extension": "Seasonal Trigonometric Model",
    }

def step_simulation(
    state: dict,
    run_id: str,
    sim_date: str,
    requested: int,
    ad_cost: float = 0.0,
    capacity_override: int | None = None,
    price_override: float | None = None,
    restock_override: int | None = None,
    defect_override: float | None = None,
) -> tuple[dict, bool, str]:
    """Deterministic ROB monthly step with duplicate run_id protection and exact accounting rules."""
    if run_id in state["processed_run_ids"]:
        return state, False, f"Duplicate run_id '{run_id}' rejected; no transaction created."

    inp = state["inputs"]
    price = to_money(price_override if price_override is not None else inp["base_price"])
    staff_hours = float(inp["staff_hours"])
    hours_per_unit = float(inp["hours_per_unit"])
    defect_rate = float(defect_override if defect_override is not None else inp["defect_rate"])
    restock_units = int(restock_override if restock_override is not None else inp["restock_units"])
    comp_unit_cost = to_money(inp["component_unit_cost"])

    if requested < 0 or restock_units < 0 or not (0.0 <= defect_rate <= 1.0):
        return state, False, "Validation error: negative quantities or invalid defect rate."

    if capacity_override is not None:
        capacity = int(capacity_override)
    else:
        capacity = math.floor(staff_hours / hours_per_unit) if hours_per_unit > 0 else 0

    available_stock = int(state["stock_units"]) + restock_units
    attempted = min(int(requested), capacity, available_stock)
    failed = math.floor(attempted * defect_rate)
    sold = attempted - failed
    lost_demand = max(0, int(requested) - attempted)

    # Variable expense: ROB incurs variable cost on every ATTEMPTED kit
    vlines = state["variable_lines"]
    # Keep components_COGS synced with component_unit_cost if updated
    effective_vlines = dict(vlines)
    effective_vlines["components_COGS"] = float(comp_unit_cost)
    var_per_unit = sum(to_money(v) for v in effective_vlines.values())
    non_comp_var_per_unit = var_per_unit - comp_unit_cost

    total_var_expense = (var_per_unit * attempted).quantize(Decimal("0.01"))
    non_comp_var_cash = (non_comp_var_per_unit * attempted).quantize(Decimal("0.01"))
    restock_cash_outflow = (comp_unit_cost * restock_units).quantize(Decimal("0.01"))

    fixed_expense = sum(to_money(v) for v in state["fixed_lines"].values())
    marketing_expense = to_money(ad_cost)
    refunds = to_money(inp["refund_amount"])
    interest = to_money(inp["interest"])
    principal = to_money(inp["loan_principal"])
    capex = to_money(inp["additional_capex"])

    gross_revenue = (price * sold).quantize(Decimal("0.01"))
    net_revenue = gross_revenue - refunds
    operating_profit = net_revenue - total_var_expense - fixed_expense - marketing_expense
    net_profit = operating_profit - interest

    # Cash rule for Robotics: component cash outflow occurs on restock, NOT on consumption of startup stock
    opening_cash = to_money(state["cash"])
    ending_cash = (
        opening_cash
        + net_revenue
        - non_comp_var_cash
        - restock_cash_outflow
        - fixed_expense
        - marketing_expense
        - interest
        - principal
        - capex
    )

    ending_stock = available_stock - attempted
    ending_inventory_value = (comp_unit_cost * ending_stock).quantize(Decimal("0.01"))
    new_version = state["state_version"] + 1

    record = {
        "run_id": run_id,
        "state_version": new_version,
        "date": sim_date,
        "mode": "FIXTURE_OVERRIDE" if capacity_override is not None else "NORMAL",
        "price": float(price),
        "requested": int(requested),
        "capacity": capacity,
        "attempted": attempted,
        "failed": failed,
        "sold": sold,
        "lost_demand": lost_demand,
        "revenue": float(net_revenue),
        "variable_expense": float(total_var_expense),
        "fixed_expense": float(fixed_expense),
        "marketing_expense": float(marketing_expense),
        "total_expense": float(total_var_expense + fixed_expense + marketing_expense),
        "operating_profit": float(operating_profit),
        "net_profit": float(net_profit),
        "restock_units": restock_units,
        "restock_cash_outflow": float(restock_cash_outflow),
        "opening_cash": float(opening_cash),
        "closing_cash": float(ending_cash),
        "closing_stock_units": ending_stock,
        "closing_inventory_value": float(ending_inventory_value),
    }

    state["cash"] = float(ending_cash)
    state["stock_units"] = ending_stock
    state["equipment_net"] = float(to_money(state["equipment_net"]) + capex)
    state["debt"] = float(max(Decimal("0.00"), to_money(state["debt"]) - principal))
    state["retained_earnings"] = float(to_money(state["retained_earnings"]) + net_profit)
    state["state_version"] = new_version
    state["snapshot_id"] = f"SNAP-{new_version:03d}"
    state["simulation_date"] = sim_date
    state["ledger"].append(record)
    state["processed_run_ids"].append(run_id)
    return state, True, f"Committed {run_id} -> {state['snapshot_id']} (v{new_version})."

def validate_and_import_snapshot(raw_json: str, current_state: dict) -> tuple[dict | None, str]:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}"

    required = [
        "team_id", "course", "pathway_id", "snapshot_id", "state_version",
        "simulation_date", "inputs", "cash", "stock_units", "ledger"
    ]
    missing = [k for k in required if k not in data]
    if missing:
        return None, f"Rejected import: missing required fields {missing}."

    if data["team_id"] != current_state["team_id"]:
        return None, f"Rejected import: team_id '{data['team_id']}' does not match '{current_state['team_id']}'."

    if int(data["state_version"]) < int(current_state["state_version"]):
        return None, (
            f"Rejected stale snapshot v{data['state_version']} "
            f"(current state is v{current_state['state_version']})."
        )

    if float(data["cash"]) < 0 or int(data["stock_units"]) < 0:
        return None, "Rejected import: negative cash or stock_units."

    return data, f"Imported snapshot {data['snapshot_id']} (v{data['state_version']})."

if "sim_state" not in st.session_state:
    st.session_state.sim_state = default_state()

state = st.session_state.sim_state

# --- Sidebar: Persistent Control & Persistence ---
with st.sidebar:
    st.header("Team Robotics | ROB-2")
    st.caption(f"Course: **{state['course']}** | Pathway: **{state['pathway_id']}**")
    st.metric("Snapshot / Version", f"{state['snapshot_id']} (v{state['state_version']})")
    st.metric("Spendable Cash", f"${state['cash']:,.2f}")
    st.metric("Component Stock", f"{state['stock_units']} sets (${state['stock_units']*state['inputs']['component_unit_cost']:,.2f})")

    st.divider()
    st.subheader("Durable Save / Restore (JSON)")
    snapshot_json = json.dumps(state, indent=2)
    st.download_button(
        label="Export Snapshot JSON",
        data=snapshot_json,
        file_name=f"team_robotics_{state['snapshot_id']}_v{state['state_version']}.json",
        mime="application/json",
    )
    uploaded = st.file_uploader("Restore Snapshot JSON", type=["json"])
    if uploaded is not None:
        imported, msg = validate_and_import_snapshot(uploaded.read().decode("utf-8"), state)
        if imported is not None:
            st.session_state.sim_state = imported
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    if st.button("Reset to Opening State (v0)"):
        st.session_state.sim_state = default_state()
        st.rerun()

# --- Main Header ---
st.title("Career Venture Lab: Robotics Kit & Repair Studio")
st.info(
    "**Stage 1 Build Active** | Team: `Team Robotics` | Course: `Precalculus` | "
    "Level: `Advanced` | Simulation only: fictional business, customers, and funds."
)

tabs = st.tabs([
    "Overview & Math Skills (ROB-2)",
    "Inputs & Monthly Simulation",
    "Fixture Acceptance Tests",
    "Ledger & Balance Check",
    "Stage 2-4 Roadmap",
])

# === TAB 1: Overview & Precalculus Math Panel ===
with tabs[0]:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("Math Skills & Challenge Level")
        chosen_level = st.selectbox(
            "Challenge Level (requires teacher approval to change)",
            ["Foundation", "Applied", "Advanced"],
            index=["Foundation", "Applied", "Advanced"].index(state["selected_level"]),
        )
        if chosen_level != state["selected_level"]:
            state["selected_level"] = chosen_level
            st.warning(f"Level switched to **{chosen_level}**. Ensure teacher approval is logged.")

        p0 = float(state["inputs"]["base_price"])
        D0 = int(state["inputs"]["D0"])
        v_cost = sum(state["variable_lines"].values())
        F_cost = sum(state["fixed_lines"].values())
        cap = math.floor(state["inputs"]["staff_hours"] / state["inputs"]["hours_per_unit"])

        st.markdown(f"""
        - **Course:** Precalculus (`ROB-2`)
        - **Approved Level:** `{state['selected_level']}`
        - **Parameters:** $p_0 = \${p0:.2f}$, $D_0 = {D0}$ kits, $v = \${v_cost:.2f}$/kit, $F = \${F_cost:.2f}$/mo, $\text{{cap}} = {cap}$ kits
        - **Units:** $p$ in USD/kit; $s, q, D$ in integer kits/month; $C, R, P$ in USD/month; $A(s)$ in USD/kit
        """)

    with col_b:
        if state["selected_level"] == "Foundation":
            st.subheader("Foundation: Rational Average Cost Function $A(s)$")
            st.latex(rf"C(s) = {F_cost:.0f} + {v_cost:.0f}s, \qquad A(s) = rac{{{F_cost:.0f}}}{{s}} + {v_cost:.0f} \quad (0 < s \le {cap})")
            st.caption(
                f"Domain: $(0, {cap}]$ kits/month. Vertical asymptote at $s = 0$ ($A(0)$ is undefined); "
                f"horizontal asymptote at $y = {v_cost:.2f}$ USD/kit."
            )
            s_vals = list(range(1, max(2, cap + 1)))
            a_vals = [F_cost / s + v_cost for s in s_vals]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=s_vals, y=a_vals, mode="lines+markers", name="Average Cost A(s)"))
            fig.add_hline(y=v_cost, line_dash="dash", annotation_text=f"Horizontal Asymptote y = ${v_cost:.0f}")
            fig.update_layout(
                title=f"ROB-2 Average Cost Curve ({state['snapshot_id']} | Projection)",
                xaxis_title="Completed Kits s (units/month)",
                yaxis_title="Average Cost A(s) (USD/kit)",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(pd.DataFrame({"s (kits)": s_vals, "Total Cost C(s) ($)": [F_cost + v_cost*s for s in s_vals], "Average Cost A(s) ($/kit)": [round(x, 2) for x in a_vals]}), use_container_width=True)

        elif state["selected_level"] == "Applied":
            st.subheader("Applied: Function Composition & Capacity Breakpoint")
            slope = D0 / p0
            p_break = p0 * (2 - cap / D0)
            st.latex(rf"q(p) = \max\left(0, {2*D0} - {slope:.5f}pight), \quad s(p) = \min({cap}, q(p)), \quad P(p) = p\cdot s(p) - ({F_cost:.0f} + {v_cost:.0f}s(p))")
            st.caption(f"Price domain: $[0, {2*p0:.0f}]$. Capacity breakpoint occurs at $p = \${p_break:.2f}$ where $q(p) = {cap}$ kits.")
            prices = [p for p in range(0, int(2 * p0) + 5, 5)]
            rows = []
            for p in prices:
                q_cont = max(0.0, 2 * D0 - slope * p)
                s_cont = min(float(cap), q_cont)
                rev = p * s_cont
                cost = F_cost + v_cost * s_cont
                prof = rev - cost
                rows.append({"Price ($)": p, "Demand q(p)": round(q_cont, 2), "Constrained s(p)": round(s_cont, 2), "Revenue R(p) ($)": round(rev, 2), "Cost C(s(p)) ($)": round(cost, 2), "Profit P(p) ($)": round(prof, 2)})
            df_app = pd.DataFrame(rows)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_app["Price ($)"], y=df_app["Revenue R(p) ($)"], name="Revenue R(p)"))
            fig.add_trace(go.Scatter(x=df_app["Price ($)"], y=df_app["Cost C(s(p)) ($)"], name="Cost C(s(p))"))
            fig.add_trace(go.Scatter(x=df_app["Price ($)"], y=df_app["Profit P(p) ($)"], name="Profit P(p)"))
            fig.add_hline(y=0, line_dash="dot", annotation_text="Zero Profit Line")
            fig.add_vline(x=p_break, line_dash="dash", annotation_text=f"Capacity Breakpoint p=${p_break:.0f}")
            fig.update_layout(title="ROB-2 Composed Revenue, Cost & Profit (Continuous Model)", xaxis_title="Price p (USD/kit)", yaxis_title="Monthly USD")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_app, use_container_width=True)

        else:
            st.subheader("Advanced: Seasonal Trigonometric Demand Extension & Capacity Clipping")
            st.latex(rf"D(t) = {D0}\left(1 + 0.20\sin\left(rac{{2\pi(t-1)}}{{12}}ight)ight), \qquad S_{	ext{{realized}}}(t) = \min\left({cap},\ \lfloor D(t) flooright)")
            st.caption(
                f"Assumed 12-month periodic model (requires trigonometry instruction). Peak at $t=4$ ($D(4)={1.2*D0:.1f}$ kits); "
                f"minimum at $t=10$ ($D(10)={0.8*D0:.1f}$ kits). Realized sales are clipped at capacity ({cap} kits/month)."
            )
            months_t = list(range(1, 13))
            rows = []
            for t in months_t:
                d_t = D0 * (1.0 + 0.20 * math.sin(2 * math.pi * (t - 1) / 12))
                s_real = min(cap, math.floor(d_t))
                lost = max(0, math.floor(d_t) - s_real)
                prof_proj = p0 * s_real - (F_cost + v_cost * s_real)
                rows.append({
                    "Month Index t": t,
                    "Seasonal Demand D(t) (continuous)": round(d_t, 2),
                    "Capacity Cap": cap,
                    "Realized Integer Sales": s_real,
                    "Lost Demand (kits)": lost,
                    "Projected Operating Profit ($)": round(prof_proj, 2),
                })
            df_adv = pd.DataFrame(rows)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_adv["Month Index t"], y=df_adv["Seasonal Demand D(t) (continuous)"], mode="lines+markers", name="Unclipped Seasonal Demand D(t)"))
            fig.add_trace(go.Bar(x=df_adv["Month Index t"], y=df_adv["Realized Integer Sales"], name="Realized Sales (Clipped at Capacity)", opacity=0.65))
            fig.add_hline(y=cap, line_dash="dash", annotation_text=f"Capacity Limit = {cap} kits")
            fig.update_layout(title="ROB-2 Advanced Seasonal Demand vs. Realized Sales (Assumed Projection)", xaxis_title="Month Index t (1..12)", yaxis_title="Kits / Month")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_adv, use_container_width=True)

            st.markdown("#### Independent Transfer Check & Disruption Prompt")
            st.write(
                f"- **Check 1:** Compare $C({cap}) = \${F_cost + v_cost*cap:,.2f}$ with $A({cap}) = \${(F_cost/cap + v_cost):,.2f}$/kit, and explain why $s=0$ is excluded from $A(s)$.
"
                "- **Check 2 (Required Disruption):** If a supplier raises component cost by 15% ($\$30 \rightarrow \$34.50$/set) and delays delivery by 1 week, how does unit variable cost change ($\$65 \rightarrow \$69.50$), and how does stock cover protect against lost sales?"
            )

# === TAB 2: Inputs & Monthly Simulation ===
with tabs[1]:
    st.subheader("Editable Business Parameters & Monthly Step")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Pricing & Staffing**")
        state["inputs"]["base_price"] = st.number_input("Base Price ($/kit)", min_value=1.0, value=float(state["inputs"]["base_price"]), step=5.0)
        state["inputs"]["staff_hours"] = st.number_input("Staff Hours / Month", min_value=0.0, value=float(state["inputs"]["staff_hours"]), step=5.0)
        state["inputs"]["hours_per_unit"] = st.number_input("Assembly Hours / Kit", min_value=0.5, value=float(state["inputs"]["hours_per_unit"]), step=0.5)
        state["inputs"]["defect_rate"] = st.slider("Defect Rate (0 to 1)", 0.0, 1.0, float(state["inputs"]["defect_rate"]), 0.01)
    with c2:
        st.markdown("**Inventory & Component Costs**")
        state["inputs"]["component_unit_cost"] = st.number_input("Component Unit Cost ($/set)", min_value=0.0, value=float(state["inputs"]["component_unit_cost"]), step=1.5)
        state["variable_lines"]["components_COGS"] = state["inputs"]["component_unit_cost"]
        restock_in = st.number_input("Restock Units This Month (cash outflow now)", min_value=0, value=0, step=10)
        ad_in = st.number_input("Approved Own-Business Ad Expense ($)", min_value=0.0, value=0.0, step=25.0)
    with c3:
        st.markdown("**Step Execution (Commits to Ledger)**")
        run_id_in = st.text_input("Unique Run ID", value=f"RUN-{state['state_version']+1:03d}")
        sim_date_in = st.text_input("Simulation Period End Date", value=f"2027-{state['state_version']+1:02d}-28" if state["state_version"] < 12 else "2027-12-31")
        req_in = st.number_input("Requested Demand (kits)", min_value=0, value=int(state["inputs"]["D0"]), step=1)
        if st.button("Approve & Advance Simulation One Month", type="primary"):
            state, ok, msg = step_simulation(
                state,
                run_id=run_id_in.strip(),
                sim_date=sim_date_in.strip(),
                requested=int(req_in),
                ad_cost=float(ad_in),
                restock_override=int(restock_in),
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

# === TAB 3: Fixture Acceptance Tests ===
with tabs[2]:
    st.subheader("ROB Package Acceptance Tests (Page 80)")
    st.warning("Fixture replay uses explicit `capacity_override` to verify ledger math. Do not mix fixture runs with normal runs.")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("**Test 1: Replay `monthly_fixture.csv` (2027-01 to 2027-03)**")
        if st.button("Run 3-Month Fixture Suite"):
            test_state = default_state()
            fixture_rows = [
                ("FIX-2027-01", "2027-01-31", 40, 30, 0.0),
                ("FIX-2027-02", "2027-02-28", 44, 30, 100.0),
                ("FIX-2027-03", "2027-03-31", 36, 22, 0.0),
            ]
            for rid, dt, req, cap_ov, ad in fixture_rows:
                test_state, _, _ = step_simulation(test_state, rid, dt, req, ad_cost=ad, capacity_override=cap_ov)
            # Duplicate run test
            _, dup_ok, dup_msg = step_simulation(test_state, "FIX-2027-01", "2027-01-31", 40, ad_cost=0.0, capacity_override=30)

            df_res = pd.DataFrame(test_state["ledger"])[[
                "date", "sold", "revenue", "total_expense", "operating_profit", "closing_cash", "closing_stock_units"
            ]]
            st.dataframe(df_res, use_container_width=True)
            expected_ok = (
                df_res.iloc[0]["closing_cash"] == 6950.0 and df_res.iloc[0]["closing_stock_units"] == 70
                and df_res.iloc[1]["closing_cash"] == 8800.0 and df_res.iloc[1]["closing_stock_units"] == 40
                and df_res.iloc[2]["closing_cash"] == 10070.0 and df_res.iloc[2]["closing_stock_units"] == 18
                and not dup_ok
            )
            if expected_ok:
                st.success(f"PASS: All 3 fixture months, stock balances (100->70->40->18), and duplicate rejection ({dup_msg}) matched handbook values.")
            else:
                st.error("FAIL: Fixture output did not match handbook expected values.")

    with col_t2:
        st.markdown("**Test 2: Low-Stock Business-Specific Test & Zero-Sales Check**")
        if st.button("Run Low-Stock & Zero-Sales Checks"):
            s_low = default_state()
            s_low["stock_units"] = 10
            s_low, _, _ = step_simulation(s_low, "TEST-LOW-STOCK", "2027-01-31", requested=40, restock_override=0)
            row_low = s_low["ledger"][-1]

            s_zero = default_state()
            s_zero, _, _ = step_simulation(s_zero, "TEST-ZERO-SALES", "2027-01-31", requested=0)
            row_zero = s_zero["ledger"][-1]

            st.write("Low-Stock Result (stock=10, defects=0, restock=0):", row_low)
            st.write("Zero-Sales Result (requested=0):", row_zero)
            if (
                row_low["sold"] == 10 and row_low["revenue"] == 1200.0 and row_low["operating_profit"] == -50.0 and row_low["closing_stock_units"] == 0
                and row_zero["revenue"] == 0.0 and row_zero["operating_profit"] == -600.0
            ):
                st.success("PASS: Low-stock profit = -$50 (closing stock = 0) and zero-sales profit = -$600.")
            else:
                st.error("FAIL: Business-specific test mismatch.")

# === TAB 4: Ledger & Balance Check ===
with tabs[3]:
    st.subheader("Dated Event Ledger & Accounting Reconciliation")
    if state["ledger"]:
        df_led = pd.DataFrame(state["ledger"])
        st.dataframe(df_led, use_container_width=True)
        st.download_button(
            "Export Ledger CSV",
            data=df_led.to_csv(index=False),
            file_name=f"team_robotics_ledger_{state['snapshot_id']}.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions recorded yet. Advance a month on the Inputs tab or run the Fixture Acceptance Tests.")

    inv_val = state["stock_units"] * state["inputs"]["component_unit_cost"]
    total_assets = state["cash"] + inv_val + state["equipment_net"]
    total_liab_eq = state["debt"] + state["startup"]["owner_contribution"] + state["retained_earnings"]
    st.markdown("### Simplified Balance Sheet Check")
    b1, b2, b3 = st.columns(3)
    b1.metric("Total Assets (Cash + Inventory + Equip)", f"${total_assets:,.2f}")
    b2.metric("Liabilities + Equity", f"${total_liab_eq:,.2f}")
    b3.metric("Reconciliation Difference", f"${(total_assets - total_liab_eq):,.2f}")

# === TAB 5: Roadmap ===
with tabs[4]:
    st.subheader("Staged Build Status (ROB-2)")
    st.markdown("""
    - **Stage 1 (Implemented):** Typed ROB inputs, startup balances, deterministic capacity/defect/stock ledger, Precalculus Math Skills panel (Foundation/Applied/Advanced), duplicate `run_id` guard, stale-snapshot validation, Save/Restore JSON, CSV export, and fixture acceptance checks.
    - **Stage 2 (Planned):** Departmental AI handoff importer (`Finance`, `Operations`, `Market/Marketing`, `Independent Reviewer`), full Report Center (PDF/CSV), and costed Marketing Studio.
    - **Stage 3 (Planned):** Frozen-snapshot Practice Assessment generator, Cross-Course Connections panel (Engineering sensor/defect testing + Economics/English), and two-report Decision Memos.
    - **Stage 4 (Optional Lowest Priority):** Fictional storefront with test orders only after Stages 1-3 pass.
    """)
