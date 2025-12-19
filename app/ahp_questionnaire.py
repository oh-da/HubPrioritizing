"""
AHP Expert Questionnaire for Hub Prioritization
================================================

A professional Streamlit application for collecting expert pairwise comparisons
using the Analytic Hierarchy Process (AHP) methodology.

Streamlit Cloud Compatible - Saves results to CSV automatically.

Run with: streamlit run app/ahp_questionnaire.py
"""

import streamlit as st
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import os

# =============================================================================
# Configuration & Data Loading
# =============================================================================

# Page configuration
st.set_page_config(
    page_title="AHP Hub Prioritization Questionnaire",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CRITERIA_FILE = DATA_DIR / "criteria.csv"
RESULTS_FILE = DATA_DIR / "ahp_results.csv"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

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
# Load Criteria from CSV
# =============================================================================

@st.cache_data
def load_criteria():
    """Load criteria definitions from CSV file."""
    try:
        if not CRITERIA_FILE.exists():
            st.error(f"Criteria file not found: {CRITERIA_FILE}")
            st.stop()

        df = pd.read_csv(CRITERIA_FILE)

        # Validate required columns
        required_cols = ['criterion_id', 'label_en', 'label_he', 'description', 'icon']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            st.error(f"Missing required columns in criteria.csv: {missing}")
            st.stop()

        # Create dictionaries
        criteria = df['criterion_id'].tolist()
        labels = dict(zip(df['criterion_id'], df['label_en']))
        labels_heb = dict(zip(df['criterion_id'], df['label_he']))
        descriptions = dict(zip(df['criterion_id'], df['description']))
        icons = dict(zip(df['criterion_id'], df['icon']))

        return criteria, labels, labels_heb, descriptions, icons

    except Exception as e:
        st.error(f"Error loading criteria: {e}")
        st.stop()


# Load criteria
CRITERIA, CRITERIA_LABELS, CRITERIA_LABELS_HEB, CRITERIA_DESCRIPTIONS, CRITERIA_ICONS = load_criteria()


# =============================================================================
# Results Persistence Functions
# =============================================================================

def save_results_to_csv(expert_name: str, comparisons: dict, results: dict):
    """
    Save expert results to CSV file (append mode).

    Creates one row per expert submission with all comparisons and weights.
    """
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Build the result row
        row_data = {
            'timestamp': timestamp,
            'expert_name': expert_name or 'anonymous',
            'consistency_ratio': results['cr'],
            'lambda_max': results['lambda_max'],
            'is_consistent': results['is_consistent']
        }

        # Add weights
        for i, crit in enumerate(CRITERIA):
            row_data[f'weight_{crit}'] = results['weights'][i]

        # Add comparisons
        for (crit_a, crit_b), value in comparisons.items():
            row_data[f'comp_{crit_a}_vs_{crit_b}'] = value

        # Create DataFrame
        result_df = pd.DataFrame([row_data])

        # Append to file or create new
        if RESULTS_FILE.exists():
            # Read existing and append
            existing_df = pd.read_csv(RESULTS_FILE)
            combined_df = pd.concat([existing_df, result_df], ignore_index=True)
            combined_df.to_csv(RESULTS_FILE, index=False)
        else:
            # Create new file
            result_df.to_csv(RESULTS_FILE, index=False)

        return True, "Results saved successfully!"

    except PermissionError:
        # Streamlit Cloud may have read-only filesystem
        return False, "Cannot write to file system (Streamlit Cloud limitation). Please use the download button instead."

    except Exception as e:
        return False, f"Error saving results: {str(e)}"


def get_results_summary():
    """Load and summarize all submitted results."""
    try:
        if not RESULTS_FILE.exists():
            return None

        df = pd.read_csv(RESULTS_FILE)
        return df

    except Exception as e:
        st.warning(f"Could not load results history: {e}")
        return None


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

    /* Success button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #28a745 0%, #34ce57 100%);
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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
            help="This will identify your responses in the results file"
        )
        st.session_state.expert_name = expert_name

        st.divider()

        st.subheader("📋 Instructions")
        st.markdown("""
        1. **Enter your name** above
        2. **Compare criteria pairs** using the sliders
        3. **Review your weights** and consistency
        4. **Submit results** to save automatically
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
                direction_text = "Equal importance"
            elif slider_value > 0:
                direction_text = f"{CRITERIA_LABELS[crit_a]} is {saaty_value:.0f}× more important"
            else:
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


def render_submit_section(comparisons: dict, results: dict, expert_name: str):
    """Render the submission section with save and download options."""

    if not results:
        return

    st.subheader("💾 Submit & Export Results")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### Save Results to Database")
        st.markdown("Click below to save your responses to the central results file.")

        if st.button("✅ Submit Results", type="primary", use_container_width=True):
            success, message = save_results_to_csv(expert_name, comparisons, results)

            if success:
                st.success(message)
                st.balloons()
            else:
                st.warning(message)
                st.info("💡 **Tip:** Use the download button instead to save your results locally.")

    with col2:
        st.markdown("### Download Results (Backup)")
        st.markdown("Download your responses as a CSV file for backup.")

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
            label="📥 Download Backup CSV",
            data=csv_comparisons,
            file_name=filename,
            mime='text/csv',
            use_container_width=True
        )

    st.divider()

    # Show results summary if available
    results_summary = get_results_summary()
    if results_summary is not None and len(results_summary) > 0:
        with st.expander(f"📊 View All Submissions ({len(results_summary)} total)"):
            st.dataframe(results_summary, use_container_width=True)


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
    tab1, tab2, tab3 = st.tabs(["📋 Criteria Overview", "⚖️ Pairwise Comparisons", "📊 Results & Submit"])

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
        5. **Submit your responses** to save them to the central database

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

    # Tab 3: Results & Submit
    with tab3:
        comparisons = st.session_state.get('comparisons', {})

        if comparisons:
            results = render_results(comparisons, CRITERIA)

            if results:
                st.divider()
                render_submit_section(comparisons, results, expert_name)
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
