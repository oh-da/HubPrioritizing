"""
AHP Expert Questionnaire for Hub Prioritization
================================================

A professional Streamlit application for collecting expert pairwise comparisons
using the Analytic Hierarchy Process (AHP) methodology.

Run with: streamlit run app/ahp_questionnaire.py
"""

import streamlit as st
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# =============================================================================
# Configuration
# =============================================================================

# Page configuration
st.set_page_config(
    page_title="AHP Hub Prioritization Questionnaire",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Criteria definitions
CRITERIA = [
    'activity_score',
    'service_score',
    'location_score',
    'pop_jobs_score',
    'terminal_score'
]

CRITERIA_LABELS = {
    'activity_score': 'Passenger Activity',
    'service_score': 'Service & Modes',
    'location_score': 'Location',
    'pop_jobs_score': 'Population & Jobs',
    'terminal_score': 'Bus Terminal'
}

CRITERIA_LABELS_HEB = {
    'activity_score': 'ציון פעילות',
    'service_score': 'ציון שירות',
    'location_score': 'ציון מיקום',
    'pop_jobs_score': 'אוכלוסייה ותעסוקה',
    'terminal_score': 'ציון מסוף'
}

CRITERIA_DESCRIPTIONS = {
    'activity_score': 'Forecasted passenger demand for 2050 (log-transformed to prevent mega-station dominance)',
    'service_score': 'Quality of transit service including mode types, frequencies, and multimodal diversity',
    'location_score': 'Strategic geographic importance (periphery vs. center, core vs. outer ring)',
    'pop_jobs_score': 'Population and employment density within walking distance (catchment area)',
    'terminal_score': 'Integration with bus network through proximity to bus terminals'
}

CRITERIA_ICONS = {
    'activity_score': '👥',
    'service_score': '🚇',
    'location_score': '📍',
    'pop_jobs_score': '🏘️',
    'terminal_score': '🚌'
}

# Random Index values for consistency ratio (Saaty, 1980)
RANDOM_INDEX = {
    1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
    6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49
}

# Saaty scale
SAATY_SCALE = {
    9: "Extreme importance",
    8: "Very to extreme importance",
    7: "Very strong importance",
    6: "Strong to very strong importance",
    5: "Strong importance",
    4: "Moderate to strong importance",
    3: "Moderate importance",
    2: "Slight importance",
    1: "Equal importance"
}

# =============================================================================
# Custom CSS Styling
# =============================================================================

def apply_custom_css():
    """Apply custom CSS for professional appearance."""
    st.markdown("""
    <style>
    /* Main container styling */
    .main {
        padding: 2rem;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }

    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
    }

    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }

    /* Card styling */
    .criterion-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    .criterion-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border-color: #1e3a5f;
    }

    /* Comparison card */
    .comparison-card {
        background: linear-gradient(to right, #f8f9fa 0%, #ffffff 50%, #f8f9fa 100%);
        border: 2px solid #e9ecef;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
    }

    .comparison-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .criterion-label {
        font-weight: 600;
        color: #1e3a5f;
        font-size: 1.1rem;
    }

    .vs-badge {
        background: #e9ecef;
        color: #6c757d;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-weight: 500;
    }

    /* Scale visualization */
    .scale-container {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }

    .scale-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.8rem;
        color: #6c757d;
        margin-top: 0.5rem;
    }

    /* Results styling */
    .results-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        border: 2px solid #28a745;
        border-radius: 12px;
        padding: 2rem;
        margin: 1rem 0;
    }

    .results-card.warning {
        border-color: #ffc107;
    }

    .results-card.danger {
        border-color: #dc3545;
    }

    /* Consistency indicator */
    .consistency-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        margin: 0.5rem 0;
    }

    .consistency-badge.success {
        background: #d4edda;
        color: #155724;
    }

    .consistency-badge.warning {
        background: #fff3cd;
        color: #856404;
    }

    .consistency-badge.danger {
        background: #f8d7da;
        color: #721c24;
    }

    /* Progress bar */
    .progress-container {
        background: #e9ecef;
        border-radius: 10px;
        height: 10px;
        margin: 1rem 0;
        overflow: hidden;
    }

    .progress-bar {
        background: linear-gradient(90deg, #1e3a5f 0%, #28a745 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.3s ease;
    }

    /* Sidebar styling */
    .sidebar .sidebar-content {
        background: #f8f9fa;
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        font-weight: 600;
        transition: transform 0.2s, box-shadow 0.2s;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(30, 58, 95, 0.3);
    }

    /* Info boxes */
    .info-box {
        background: #e7f3ff;
        border-left: 4px solid #1e3a5f;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }

    /* Step indicator */
    .step-indicator {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin: 2rem 0;
    }

    .step {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        background: #e9ecef;
        color: #6c757d;
    }

    .step.active {
        background: #1e3a5f;
        color: white;
    }

    .step.completed {
        background: #28a745;
        color: white;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Slider styling */
    .stSlider > div > div > div > div {
        background: linear-gradient(90deg, #dc3545 0%, #ffc107 50%, #28a745 100%);
    }
    </style>
    """, unsafe_allow_html=True)


# =============================================================================
# AHP Calculation Functions
# =============================================================================

def build_comparison_matrix(comparisons: dict, criteria: list) -> np.ndarray:
    """Build pairwise comparison matrix from comparison values."""
    n = len(criteria)
    matrix = np.eye(n)
    criteria_idx = {c: i for i, c in enumerate(criteria)}

    for (crit_a, crit_b), value in comparisons.items():
        i = criteria_idx[crit_a]
        j = criteria_idx[crit_b]
        matrix[i, j] = value
        matrix[j, i] = 1.0 / value if value != 0 else 1.0

    return matrix


def calculate_priority_weights(matrix: np.ndarray) -> tuple:
    """Calculate priority weights using eigenvector method."""
    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    max_idx = np.argmax(eigenvalues.real)
    max_eigenvector = eigenvectors[:, max_idx].real
    weights = max_eigenvector / max_eigenvector.sum()
    return weights, eigenvalues.real[max_idx]


def calculate_consistency_ratio(matrix: np.ndarray, lambda_max: float) -> tuple:
    """Calculate Consistency Index (CI) and Consistency Ratio (CR)."""
    n = matrix.shape[0]
    ci = (lambda_max - n) / (n - 1) if n > 1 else 0
    ri = RANDOM_INDEX.get(n, 1.12)
    cr = ci / ri if ri > 0 else 0
    return ci, cr


def slider_to_saaty(value: int) -> float:
    """Convert slider value (-8 to 8) to Saaty scale value."""
    if value == 0:
        return 1.0
    elif value > 0:
        return float(value + 1)
    else:
        return 1.0 / (abs(value) + 1)


def saaty_to_slider(saaty_value: float) -> int:
    """Convert Saaty scale value to slider value."""
    if saaty_value >= 1:
        return int(saaty_value - 1)
    else:
        return -int(1.0 / saaty_value - 1)


# =============================================================================
# UI Components
# =============================================================================

def render_header():
    """Render the main header."""
    st.markdown("""
    <div class="main-header">
        <h1>🚆 AHP Hub Prioritization Questionnaire</h1>
        <p>Analytic Hierarchy Process for Expert Weight Determination</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with expert info and instructions."""
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/train.png", width=80)
        st.title("Expert Information")

        expert_name = st.text_input(
            "Your Name / ID",
            value=st.session_state.get('expert_name', ''),
            placeholder="e.g., transport_planner",
            help="This will identify your responses in the output file"
        )
        st.session_state.expert_name = expert_name

        st.divider()

        st.subheader("📋 Instructions")
        st.markdown("""
        1. **Enter your name** above
        2. **Compare criteria pairs** using the sliders
        3. **Review your weights** and consistency
        4. **Export results** to CSV
        """)

        st.divider()

        st.subheader("📊 The Saaty Scale")
        with st.expander("View Scale Definitions"):
            for value, meaning in SAATY_SCALE.items():
                st.markdown(f"**{value}** - {meaning}")

        st.divider()

        st.subheader("ℹ️ About AHP")
        st.markdown("""
        The **Analytic Hierarchy Process** (AHP)
        is a structured decision-making method
        developed by Thomas Saaty.

        It uses pairwise comparisons to derive
        relative weights for criteria.

        **Consistency Ratio (CR)** should be
        below 0.10 for valid results.
        """)

        return expert_name


def render_criteria_overview():
    """Render an overview of all criteria."""
    st.subheader("📋 Hub Prioritization Criteria")

    cols = st.columns(len(CRITERIA))
    for idx, crit in enumerate(CRITERIA):
        with cols[idx]:
            st.markdown(f"""
            <div class="criterion-card">
                <h4>{CRITERIA_ICONS[crit]} {CRITERIA_LABELS[crit]}</h4>
                <p style="font-size: 0.9rem; color: #6c757d; direction: rtl;">
                    {CRITERIA_LABELS_HEB[crit]}
                </p>
                <p style="font-size: 0.85rem;">
                    {CRITERIA_DESCRIPTIONS[crit]}
                </p>
            </div>
            """, unsafe_allow_html=True)


def render_comparison_slider(crit_a: str, crit_b: str, idx: int) -> float:
    """Render a comparison slider for two criteria."""

    # Create unique key for this comparison
    key = f"comp_{crit_a}_{crit_b}"

    # Get labels
    label_a = f"{CRITERIA_ICONS[crit_a]} {CRITERIA_LABELS[crit_a]}"
    label_b = f"{CRITERIA_ICONS[crit_b]} {CRITERIA_LABELS[crit_b]}"

    # Container for the comparison
    with st.container():
        st.markdown(f"""
        <div style="background: #f8f9fa; border-radius: 10px; padding: 1rem; margin: 0.5rem 0; border-left: 4px solid #1e3a5f;">
            <strong>Comparison {idx}</strong>
        </div>
        """, unsafe_allow_html=True)

        # Three columns: Left criterion, slider, right criterion
        col1, col2, col3 = st.columns([2, 4, 2])

        with col1:
            st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem;">
                <div style="font-size: 2rem;">{CRITERIA_ICONS[crit_a]}</div>
                <div style="font-weight: 600; color: #1e3a5f;">{CRITERIA_LABELS[crit_a]}</div>
                <div style="font-size: 0.8rem; color: #6c757d; direction: rtl;">{CRITERIA_LABELS_HEB[crit_a]}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            # Slider from -8 to 8 (0 = equal)
            slider_value = st.slider(
                label=f"How important is {CRITERIA_LABELS[crit_a]} compared to {CRITERIA_LABELS[crit_b]}?",
                min_value=-8,
                max_value=8,
                value=st.session_state.get(key, 0),
                key=key,
                help="Move left if right criterion is more important, right if left is more important",
                label_visibility="collapsed"
            )

            # Convert to Saaty value
            saaty_value = slider_to_saaty(slider_value)

            # Display current value
            if slider_value == 0:
                intensity_text = "Equal importance"
                direction_text = "Both criteria are equally important"
            elif slider_value > 0:
                intensity_text = SAATY_SCALE.get(slider_value + 1, "")
                direction_text = f"{CRITERIA_LABELS[crit_a]} is {saaty_value:.0f}× more important"
            else:
                intensity_text = SAATY_SCALE.get(abs(slider_value) + 1, "")
                direction_text = f"{CRITERIA_LABELS[crit_b]} is {1/saaty_value:.0f}× more important"

            st.markdown(f"""
            <div style="text-align: center; margin-top: 0.5rem;">
                <span style="background: #1e3a5f; color: white; padding: 0.25rem 0.75rem; border-radius: 15px; font-size: 0.9rem;">
                    {direction_text}
                </span>
            </div>
            """, unsafe_allow_html=True)

            # Scale labels
            st.markdown("""
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #6c757d; margin-top: 0.25rem;">
                <span>← More important</span>
                <span>Equal</span>
                <span>More important →</span>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem;">
                <div style="font-size: 2rem;">{CRITERIA_ICONS[crit_b]}</div>
                <div style="font-weight: 600; color: #1e3a5f;">{CRITERIA_LABELS[crit_b]}</div>
                <div style="font-size: 0.8rem; color: #6c757d; direction: rtl;">{CRITERIA_LABELS_HEB[crit_b]}</div>
            </div>
            """, unsafe_allow_html=True)

    return saaty_value


def render_results(comparisons: dict, criteria: list):
    """Render the results section with weights and consistency check."""

    if not comparisons:
        st.warning("Please complete the comparisons above first.")
        return None

    # Build matrix and calculate
    matrix = build_comparison_matrix(comparisons, criteria)
    weights, lambda_max = calculate_priority_weights(matrix)
    ci, cr = calculate_consistency_ratio(matrix, lambda_max)

    is_consistent = cr < 0.10

    st.subheader("📊 Results")

    # Consistency status
    col1, col2 = st.columns([1, 2])

    with col1:
        if is_consistent:
            st.success(f"✅ **Consistent** (CR = {cr:.4f})")
            st.markdown("Your judgments are logically consistent.")
        else:
            st.error(f"⚠️ **Inconsistent** (CR = {cr:.4f})")
            st.markdown("""
            Your consistency ratio exceeds 0.10.
            Please review your comparisons for logical consistency.

            **Tips:**
            - Check transitivity (if A > B and B > C, then A > C)
            - Avoid extreme values unless truly justified
            """)

    with col2:
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("λ_max", f"{lambda_max:.4f}")
        m2.metric("CI", f"{ci:.4f}")
        m3.metric("CR", f"{cr:.4f}", delta="OK" if is_consistent else "High", delta_color="normal" if is_consistent else "inverse")

    st.divider()

    # Weights visualization
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📈 Priority Weights")

        # Create DataFrame
        weights_df = pd.DataFrame({
            'Criterion': [f"{CRITERIA_ICONS[c]} {CRITERIA_LABELS[c]}" for c in criteria],
            'Weight': weights,
            'Percentage': weights * 100
        })
        weights_df = weights_df.sort_values('Weight', ascending=True)

        # Horizontal bar chart
        fig = px.bar(
            weights_df,
            x='Weight',
            y='Criterion',
            orientation='h',
            color='Weight',
            color_continuous_scale=['#f8d7da', '#1e3a5f'],
            text=[f"{w:.1%}" for w in weights_df['Weight']]
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            xaxis_title="Weight",
            yaxis_title="",
            height=350,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥧 Weight Distribution")

        # Pie chart
        fig = go.Figure(data=[go.Pie(
            labels=[f"{CRITERIA_ICONS[c]} {CRITERIA_LABELS[c]}" for c in criteria],
            values=weights,
            hole=0.4,
            textinfo='label+percent',
            textposition='outside',
            marker_colors=['#1e3a5f', '#2d5a87', '#3d7ab5', '#6c9bc3', '#9bbcd1']
        )])
        fig.update_layout(
            showlegend=False,
            height=350,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Comparison matrix
    with st.expander("📋 View Pairwise Comparison Matrix"):
        matrix_df = pd.DataFrame(
            matrix,
            index=[CRITERIA_LABELS[c] for c in criteria],
            columns=[CRITERIA_LABELS[c] for c in criteria]
        )
        st.dataframe(matrix_df.round(3), use_container_width=True)

    # Weights table
    with st.expander("📊 View Weights Table"):
        display_df = pd.DataFrame({
            'Criterion': [CRITERIA_LABELS[c] for c in criteria],
            'Hebrew': [CRITERIA_LABELS_HEB[c] for c in criteria],
            'Weight': weights,
            'Percentage': [f"{w*100:.2f}%" for w in weights]
        })
        st.dataframe(display_df, use_container_width=True)

    return {
        'matrix': matrix,
        'weights': weights,
        'lambda_max': lambda_max,
        'ci': ci,
        'cr': cr,
        'is_consistent': is_consistent
    }


def render_export_section(comparisons: dict, results: dict, expert_name: str):
    """Render the export section."""

    if not results:
        return

    st.subheader("💾 Export Results")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Export Pairwise Comparisons**")
        st.markdown("CSV file compatible with the AHP scoring module.")

        # Prepare comparison CSV data
        rows = []
        for (crit_a, crit_b), value in comparisons.items():
            rows.append({
                'expert': expert_name or 'expert1',
                'criterion_a': crit_a,
                'criterion_b': crit_b,
                'value': value
            })

        comparisons_df = pd.DataFrame(rows)
        csv_comparisons = comparisons_df.to_csv(index=False)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ahp_comparisons_{expert_name or 'expert'}_{timestamp}.csv"

        st.download_button(
            label="📥 Download Comparisons CSV",
            data=csv_comparisons,
            file_name=filename,
            mime='text/csv',
            use_container_width=True
        )

    with col2:
        st.markdown("**Export Weights Summary**")
        st.markdown("Summary of calculated weights for reference.")

        # Prepare weights summary
        weights_df = pd.DataFrame({
            'criterion': CRITERIA,
            'weight': results['weights'],
            'percentage': [f"{w*100:.2f}%" for w in results['weights']]
        })
        # Add metadata rows
        meta_rows = pd.DataFrame([
            {'criterion': '_consistency_ratio', 'weight': results['cr'], 'percentage': f"CR={results['cr']:.4f}"},
            {'criterion': '_lambda_max', 'weight': results['lambda_max'], 'percentage': f"λ={results['lambda_max']:.4f}"},
            {'criterion': '_expert', 'weight': 0, 'percentage': expert_name or 'expert1'}
        ])
        weights_df = pd.concat([weights_df, meta_rows], ignore_index=True)

        csv_weights = weights_df.to_csv(index=False)

        st.download_button(
            label="📥 Download Weights CSV",
            data=csv_weights,
            file_name=f"ahp_weights_{expert_name or 'expert'}_{timestamp}.csv",
            mime='text/csv',
            use_container_width=True
        )

    st.divider()

    # Preview of exportable data
    with st.expander("👁️ Preview Export Data"):
        st.markdown("**Pairwise Comparisons:**")
        st.dataframe(comparisons_df, use_container_width=True)


def render_progress_bar(completed: int, total: int):
    """Render a progress bar."""
    progress = completed / total if total > 0 else 0
    st.markdown(f"""
    <div style="margin: 1rem 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
            <span style="font-weight: 600;">Progress</span>
            <span>{completed}/{total} comparisons ({progress*100:.0f}%)</span>
        </div>
        <div style="background: #e9ecef; border-radius: 10px; height: 10px; overflow: hidden;">
            <div style="background: linear-gradient(90deg, #1e3a5f 0%, #28a745 100%);
                        width: {progress*100}%; height: 100%; border-radius: 10px;
                        transition: width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Main application entry point."""

    # Apply custom styling
    apply_custom_css()

    # Render header
    render_header()

    # Render sidebar and get expert name
    expert_name = render_sidebar()

    # Generate all pairwise combinations
    all_comparisons = []
    for i in range(len(CRITERIA)):
        for j in range(i + 1, len(CRITERIA)):
            all_comparisons.append((CRITERIA[i], CRITERIA[j]))

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📋 Criteria Overview", "⚖️ Pairwise Comparisons", "📊 Results & Export"])

    # Tab 1: Criteria Overview
    with tab1:
        render_criteria_overview()

        st.divider()

        st.subheader("🎯 How to Use This Tool")
        st.markdown("""
        1. **Review the criteria** above to understand what each one measures
        2. **Go to the Comparisons tab** to make your pairwise judgments
        3. **Use the sliders** to indicate which criterion is more important
        4. **Check the Results tab** for your calculated weights and consistency
        5. **Export your responses** to CSV for use in the scoring pipeline

        **Remember:** Your consistency ratio (CR) should be below 0.10 for valid results.
        """)

    # Tab 2: Pairwise Comparisons
    with tab2:
        st.subheader("⚖️ Pairwise Comparisons")

        st.info("""
        **Instructions:** For each pair of criteria, use the slider to indicate which criterion
        is more important for hub prioritization, and by how much.

        - **Slide left** if the RIGHT criterion is more important
        - **Slide right** if the LEFT criterion is more important
        - **Keep centered** if they are equally important
        """)

        # Progress bar
        completed = sum(1 for i, (a, b) in enumerate(all_comparisons)
                       if st.session_state.get(f"comp_{a}_{b}", 0) != 0)
        render_progress_bar(completed, len(all_comparisons))

        st.divider()

        # Render all comparison sliders
        comparisons = {}
        for idx, (crit_a, crit_b) in enumerate(all_comparisons, 1):
            saaty_value = render_comparison_slider(crit_a, crit_b, idx)
            comparisons[(crit_a, crit_b)] = saaty_value
            st.divider()

        # Store comparisons in session state
        st.session_state.comparisons = comparisons

    # Tab 3: Results & Export
    with tab3:
        comparisons = st.session_state.get('comparisons', {})

        if comparisons:
            results = render_results(comparisons, CRITERIA)

            if results:
                st.divider()
                render_export_section(comparisons, results, expert_name)
        else:
            st.warning("Please complete the pairwise comparisons in the previous tab first.")

    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #6c757d; font-size: 0.85rem;">
        <p>Hub Prioritization Framework | AHP Expert Questionnaire</p>
        <p>Based on Saaty, T.L. (1980). <em>The Analytic Hierarchy Process</em>. McGraw-Hill.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
