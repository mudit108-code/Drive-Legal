"""DriveLegal India Streamlit application.

All runtime data is bundled locally. Calculation and validation logic lives in
app_core.py so it can be tested independently of the UI.
"""

from __future__ import annotations

import streamlit as st

from app_core import (
    ALL_STATES,
    CITIZEN_RIGHTS,
    LEGAL_SECTIONS,
    METADATA,
    NATIONAL_FINES,
    STATE_DATA,
    VEHICLE_TYPES,
    CalculatorInputError,
    calculate_fine,
    calculate_multi_fine,
    get_allowed_vehicle_types,
    get_source_details,
    get_violation_options,
)


st.set_page_config(
    page_title="DriveLegal India",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .main-header { background: linear-gradient(135deg,#1a237e 0%,#283593 50%,#1565c0 100%); padding:2rem; border-radius:12px; margin-bottom:1.5rem; color:white; text-align:center; }
        .main-header h1 { font-size:2.5rem; margin:0; }
        .main-header p { font-size:1.1rem; opacity:.85; margin:.5rem 0 0; }
        .fine-box { background:#fff3e0; border:2px solid #ff6f00; padding:1.2rem; border-radius:10px; margin-top:1rem; }
        .fine-total { font-size:2rem; font-weight:bold; color:#e65100; }
        .section-badge { background:#1565c0; color:white; padding:.2rem .7rem; border-radius:20px; font-size:.8rem; font-weight:bold; }
        .state-note { background:#e8f5e9; border-left:4px solid #2e7d32; padding:.6rem 1rem; border-radius:4px; margin:.3rem 0; font-size:.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="main-header">
        <h1>🚦 DriveLegal India</h1>
        <p>Location-specific traffic-law reference and challan estimator</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## 📍 Select Location")
    selected_state = st.selectbox("State / Union Territory", ALL_STATES, index=ALL_STATES.index("Delhi"))
    state_info = STATE_DATA[selected_state]
    st.markdown("---")
    st.markdown(f"### 🏛 {selected_state}")
    st.metric("City Speed Limit", f"{state_info['speed_city']} km/h")
    st.metric("Highway Speed Limit", f"{state_info['speed_highway']} km/h")
    st.metric("Reference Surcharge", f"{state_info['surcharge'] * 100:.0f}%")
    st.markdown(f"**Helmet Law:** {state_info['helmet_law']}")
    st.markdown("---")
    st.caption("Offline data package: no runtime API or remote image dependency.")
    st.caption(f"Data reviewed: {METADATA['last_reviewed']}")


tab1, tab2, tab3, tab4 = st.tabs([
    "🧮 Challan Estimator",
    "📋 Traffic Laws",
    "🗺️ State-wise Rules",
    "ℹ️ About DriveLegal",
])

with tab1:
    st.markdown(f"## 🧮 Challan Estimator — {selected_state}")
    st.info(METADATA["disclaimer"])

    if "challan_cart" not in st.session_state:
        st.session_state.challan_cart = []

    violation_options = get_violation_options()
    sorted_violation_labels = sorted(violation_options)
    selected_violation_label = st.selectbox("Select violation", sorted_violation_labels)
    selected_violation_key = violation_options[selected_violation_label]
    violation = NATIONAL_FINES[selected_violation_key]
    allowed_vehicles = get_allowed_vehicle_types(selected_violation_key)
    vehicle_type = st.selectbox("Vehicle type", allowed_vehicles)

    quantity = None
    if violation["fine_basis"] == "per_excess_passenger":
        quantity = st.number_input(violation["quantity_label"], min_value=1, value=1, step=1)
    elif violation["fine_basis"] == "base_plus_excess_tonne":
        quantity = st.number_input(violation["quantity_label"], min_value=0.0, value=0.0, step=0.1)

    repeat = False
    if violation["repeat_policy"] == "explicit":
        repeat = st.checkbox(f"Use repeat-offence reference amount (₹{violation['repeat_fine']:,})")
    elif violation["repeat_policy"] == "reference_only":
        st.caption("A repeat calculation is not available for this offence because its bundled repeat treatment is not verified.")
    else:
        st.caption("A repeat calculation does not apply to this offence under its statutory record.")

    with st.expander("🚗 Vehicle-type reference"):
        st.dataframe(
            [{"Vehicle category": name, "Multiplier": f"{factor:.1f}x"} for name, factor in VEHICLE_TYPES.items()],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Vehicle multipliers are applied only to offence records that explicitly opt in. They are not used to invent statutory fine amounts.")

    if st.button("⚡ Calculate reference amount", type="primary", use_container_width=True):
        try:
            result = calculate_fine(selected_violation_key, vehicle_type, selected_state, repeat, quantity)
        except CalculatorInputError as exc:
            st.error(str(exc))
        else:
            st.markdown("---")
            st.markdown(f"### 📄 Calculation Breakdown — {selected_state}")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Reference Fine", f"₹{result['base_fine']:,.2f}")
            r2.metric("Vehicle Adjustment", f"₹{result['vehicle_adjustment']:,.2f}")
            r3.metric("Applied State Surcharge", f"₹{result['state_surcharge']:,.2f}")
            r4.metric("Repeat Penalty", f"₹{result['repeat_penalty']:,.2f}")
            st.markdown(
                f"""
                <div class="fine-box">
                    <p style="margin:0;font-size:1rem;">Estimated Reference Amount</p>
                    <p class="fine-total">₹{result['total']:,.2f}</p>
                    <span class="section-badge">Rule Section {result['rule_section']} · Penalty Section {result['penalty_section']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if result["imprisonment"]:
                st.warning(f"Potential custodial consequence in the source record: {result['imprisonment']}")
            if result["legal_note"]:
                st.caption(result["legal_note"])
            if result.get("compounding_fee"):
                st.success(
                    f"🏛️ **Verified State Compounding Fee:** In **{selected_state}**, this offence can be compounded "
                    f"under Section 200 MVA for **₹{result['compounding_fee']:,}** pursuant to Notification *{result['compounding_notification_id']}* "
                    f"(effective {result['compounding_effective_date']})."
                )
            if result["source_status"] != "act_reference":
                st.warning("This amount is a reference value and must be checked against the latest state notification or official challan portal.")
            if result["state_surcharge_rate"] and not result["state_surcharge_applied"]:
                st.info(
                    f"This location has a {result['state_surcharge_rate'] * 100:.0f}% reference surcharge, "
                    "but it is not included because no offence record explicitly opts into that unverified adjustment."
                )
            with st.expander("🔎 Bundled source references"):
                st.caption(f"Source status: `{result['source_status']}`")
                for source in result["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']}) (`{source['id']}`)")
            st.markdown("#### 📌 State-specific reference notes")
            for note in state_info["notes"]:
                st.markdown(f'<div class="state-note">• {note}</div>', unsafe_allow_html=True)

            challan_summary = (
                f"DriveLegal India — Offline Reference Challan Estimate\n"
                f"=======================================================\n"
                f"State / UT: {selected_state}\n"
                f"Violation: {violation['description']}\n"
                f"Vehicle Category: {vehicle_type}\n"
                f"Statutory Basis: Rule Sec {result['rule_section']} / Penalty Sec {result['penalty_section']}\n"
                f"-------------------------------------------------------\n"
                f"Reference Fine: ₹{result['base_fine']:,.2f}\n"
                f"Vehicle Adjustment: ₹{result['vehicle_adjustment']:,.2f}\n"
                f"Applied State Surcharge: ₹{result['state_surcharge']:,.2f}\n"
                f"Repeat Penalty: ₹{result['repeat_penalty']:,.2f}\n"
                f"TOTAL ESTIMATED AMOUNT: ₹{result['total']:,.2f}\n"
                f"-------------------------------------------------------\n"
            )
            if result.get("compounding_fee"):
                challan_summary += (
                    f"State Compounding Option: ₹{result['compounding_fee']:,} "
                    f"(Notification {result['compounding_notification_id']}, Effective {result['compounding_effective_date']})\n"
                )
            if result["imprisonment"]:
                challan_summary += f"Custodial Provision: {result['imprisonment']}\n"
            if result["legal_note"]:
                challan_summary += f"Legal Note: {result['legal_note']}\n"
            challan_summary += (
                f"\nDisclaimer: {METADATA['disclaimer']}\n"
                f"Generated from local bundled data package (Version {METADATA['schema_version']}, Reviewed: {METADATA['last_reviewed']})\n"
            )
            col_dl_single, col_add_cart = st.columns([1, 1])
            with col_dl_single:
                st.download_button(
                    label="📥 Download Single Estimate",
                    data=challan_summary,
                    file_name=f"drivelegal_{selected_state.lower().replace(' ', '_')}_{selected_violation_key}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with col_add_cart:
                if st.button("➕ Add to Multi-Offence Cart", use_container_width=True):
                    st.session_state.challan_cart.append({
                        "violation_key": selected_violation_key,
                        "description": violation["description"],
                        "vehicle_key": vehicle_type,
                        "repeat": repeat,
                        "quantity": quantity,
                        "result": result,
                    })
                    st.success(f"Added '{violation['description']}' to your itemized challan cart!")
                    st.rerun()

    if st.session_state.get("challan_cart"):
        st.markdown("---")
        st.markdown(f"### 🛒 Multi-Offence Itemized Challan Summary ({len(st.session_state.challan_cart)} offences)")
        cart_items = [
            {"violation_key": it["violation_key"], "vehicle_key": it["vehicle_key"], "repeat": it["repeat"], "quantity": it["quantity"]}
            for it in st.session_state.challan_cart
        ]
        multi_result = calculate_multi_fine(cart_items, selected_state)

        cart_table = []
        for idx, it in enumerate(st.session_state.challan_cart, start=1):
            r = it["result"]
            cart_table.append({
                "#": idx,
                "Violation": it["description"],
                "Vehicle": it["vehicle_key"],
                "Sections": f"Rule {r['rule_section']} / Pen. {r['penalty_section']}",
                "Base Fine": f"₹{r['base_fine']:,.2f}",
                "State Compounding": f"₹{r['compounding_fee']:,}" if r.get("compounding_fee") else "N/A",
                "Total Fine": f"₹{r['total']:,.2f}",
            })
        st.dataframe(cart_table, use_container_width=True, hide_index=True)

        with st.expander("✏️ Manage individual items in cart"):
            for idx, it in enumerate(st.session_state.challan_cart):
                c_desc, c_del = st.columns([4, 1])
                c_desc.write(f"**{idx + 1}.** {it['description']} ({it['vehicle_key']}) — ₹{it['result']['total']:,.2f}")
                if c_del.button("❌ Remove", key=f"del_cart_item_{idx}", use_container_width=True):
                    st.session_state.challan_cart.pop(idx)
                    st.rerun()

        m1, m2, m3 = st.columns(3)
        m1.metric("Offences In Cart", len(st.session_state.challan_cart))
        m2.metric("Combined Estimated Total", f"₹{multi_result['grand_total']:,.2f}")
        if multi_result.get("total_compounding_fee"):
            m3.metric("Total Compounding Option", f"₹{multi_result['total_compounding_fee']:,.2f}")
        else:
            m3.metric("Compounding Status", "Partial / Non-compoundable")

        cart_export_text = (
            f"DriveLegal India — Multi-Offence Challan Estimate Summary\n"
            f"===========================================================\n"
            f"State / UT: {selected_state}\n"
            f"Total Offences: {len(st.session_state.challan_cart)}\n"
            f"Combined Reference Total: ₹{multi_result['grand_total']:,.2f}\n"
        )
        if multi_result.get("total_compounding_fee"):
            cart_export_text += f"Total State Compounding Option: ₹{multi_result['total_compounding_fee']:,.2f}\n"
        cart_export_text += "-----------------------------------------------------------\n"
        for idx, it in enumerate(st.session_state.challan_cart, start=1):
            r = it["result"]
            cart_export_text += (
                f"{idx}. {it['description']} ({it['vehicle_key']})\n"
                f"   Statutory Sections: Rule {r['rule_section']} / Penalty {r['penalty_section']}\n"
                f"   Reference Amount: ₹{r['total']:,.2f}\n"
            )
            if r.get("compounding_fee"):
                cart_export_text += f"   State Compounding Fee: ₹{r['compounding_fee']:,} (Notification: {r['compounding_notification_id']})\n"
        cart_export_text += (
            f"\nDisclaimer: {METADATA['disclaimer']}\n"
            f"Generated from local bundled data package (Version {METADATA['schema_version']}, Reviewed: {METADATA['last_reviewed']})\n"
        )

        col_dl, col_clr = st.columns([3, 1])
        with col_dl:
            st.download_button(
                label="📥 Download Multi-Offence Challan Summary",
                data=cart_export_text,
                file_name=f"drivelegal_multi_challan_{selected_state.lower().replace(' ', '_')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_clr:
            if st.button("🗑️ Clear Cart", use_container_width=True):
                st.session_state.challan_cart = []
                st.rerun()

    with st.expander("📊 View national fine records"):
        rows = []
        for record in NATIONAL_FINES.values():
            rows.append(
                {
                    "Violation": record["description"],
                    "Rule section": record["rule_section"],
                    "Penalty section": record["penalty_section"],
                    "Reference fine (₹)": f"₹{record['fine']:,}",
                    "Basis": record["fine_basis"],
                    "Source status": record["source_status"],
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("## 📋 Traffic Laws — India")
    st.warning("Sections are shown separately as the rule/duty section and the penalty section. Amounts are informational references, not official challan determinations.")
    search_law = st.text_input("🔍 Search traffic laws", placeholder="Search by section number, title, or topic (e.g. 184, helmet, license)")
    filtered_laws = [
        law
        for law in LEGAL_SECTIONS
        if not search_law
        or search_law.lower() in law["section"].lower()
        or search_law.lower() in law["title"].lower()
        or search_law.lower() in law["description"].lower()
    ]
    if not filtered_laws:
        st.info(f"No traffic law sections matched '{search_law}'.")
    for law in filtered_laws:
        with st.expander(f"**Section {law['section']}** — {law['title']}"):
            st.write(law["description"])

    st.markdown("### 🌐 National speed-limit reference")
    st.dataframe(
        [
            {"Category": "Cars / Jeeps / Taxis", "Urban (km/h)": 50, "NH/SH (km/h)": 100, "Expressway (km/h)": 120},
            {"Category": "Two-wheelers", "Urban (km/h)": 50, "NH/SH (km/h)": 80, "Expressway (km/h)": 80},
            {"Category": "Autorickshaw / Three-wheeler", "Urban (km/h)": 40, "NH/SH (km/h)": 60, "Expressway (km/h)": "Not permitted"},
            {"Category": "Buses", "Urban (km/h)": 50, "NH/SH (km/h)": 80, "Expressway (km/h)": 100},
            {"Category": "Trucks / HMV", "Urban (km/h)": 40, "NH/SH (km/h)": 80, "Expressway (km/h)": 80},
            {"Category": "School buses", "Urban (km/h)": 25, "NH/SH (km/h)": 60, "Expressway (km/h)": "Not permitted"},
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("### 🛡️ Motorist Rights & Dispute Redressal Guide")
    st.caption("Statutory protections, digital document validity, and grievance mechanisms under Indian law.")
    for right in CITIZEN_RIGHTS:
        with st.expander(f"**{right['title']}** — *{right['statutory_basis']}*"):
            st.markdown(f"**Summary:** {right['summary']}")
            st.markdown("**Key Provisions:**")
            for prov in right["key_provisions"]:
                st.markdown(f"- {prov}")
            source = next((s for s in METADATA["sources"] if s["id"] == right.get("source_id")), None)
            if source:
                st.caption(f"Official Source: [{source['title']}]({source['url']})")

with tab3:
    st.markdown("## 🗺️ State and UT reference rules")
    search_term = st.text_input("🔍 Search state or Union Territory", placeholder="e.g. Maharashtra, Delhi, Goa")
    filtered_states = [state for state in ALL_STATES if not search_term or search_term.lower() in state.lower()]
    for state in filtered_states:
        info = STATE_DATA[state]
        surcharge_text = f"+{info['surcharge'] * 100:.0f}% reference surcharge" if info["surcharge"] else "No reference surcharge"
        with st.expander(f"**{state}** — {info['speed_city']} km/h city · {info['speed_highway']} km/h highway · {surcharge_text}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("City speed", f"{info['speed_city']} km/h")
            c2.metric("Highway speed", f"{info['speed_highway']} km/h")
            c3.metric("Reference surcharge", f"{info['surcharge'] * 100:.0f}%")
            st.markdown(f"**Helmet law:** {info['helmet_law']}")
            for note in info["notes"]:
                st.markdown(f'<div class="state-note">• {note}</div>', unsafe_allow_html=True)
            if info.get("notification_id"):
                st.markdown(
                    f"**Official Notification:** `{info['notification_id']}` · "
                    f"**Effective:** `{info['effective_date']}` · "
                    f"**Jurisdiction:** {info['jurisdiction']}"
                )
            if info.get("compounding_schedule"):
                with st.expander("📜 Verified Compounding Schedule (Sec 200 MVA)"):
                    st.caption(f"Offences compoundable in {state} under Notification {info['notification_id']}:")
                    sched_rows = [
                        {
                            "Offence": NATIONAL_FINES[k]["description"],
                            "Statutory Section": NATIONAL_FINES[k]["penalty_section"],
                            "Central Statutory Fine": f"₹{NATIONAL_FINES[k]['fine']:,}",
                            "State Compounding Fee": f"₹{amt:,}",
                        }
                        for k, amt in info["compounding_schedule"].items()
                        if k in NATIONAL_FINES
                    ]
                    st.dataframe(sched_rows, use_container_width=True, hide_index=True)
            st.caption(f"Source status: `{info['source_status']}`")
            if info["source_ids"]:
                with st.expander("🔎 Bundled source references"):
                    st.caption("These bundled sources support the general legal context; state-specific values still require the latest local notification.")
                    for source in get_source_details(info["source_ids"]):
                        st.markdown(f"- [{source['title']}]({source['url']}) (`{source['id']}`)")
            st.caption(info["legal_note"])

with tab4:
    st.markdown("## ℹ️ About DriveLegal India")
    st.markdown(
        "DriveLegal India is an offline informational reference and challan estimator covering 28 states and 8 Union Territories. It does not query official challan records, use geolocation, or replace a government portal."
    )
    st.markdown("### Data and legal references")
    for source in METADATA["sources"]:
        st.markdown(f"- **{source['title']}**: {source['url']}")
    st.markdown("### Legal disclaimer")
    compounding_count = sum(1 for s in STATE_DATA.values() if s.get("compounding_schedule"))
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("States covered", "28")
    c2.metric("Union Territories", "8")
    c3.metric("Violation records", str(len(NATIONAL_FINES)))
    c4.metric("Legal sections", str(len(LEGAL_SECTIONS)))
    c5.metric("Compounding states", str(compounding_count))
    c6.metric("Citizen rights", str(len(CITIZEN_RIGHTS)))
