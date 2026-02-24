import streamlit as st
import pandas as pd
import psycopg2

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NutraIQX Project Manager",
    page_icon="📋",
    layout="wide",
)

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1f4e79; }
    .sub-header  { font-size: 1rem; color: #666; margin-bottom: 1.5rem; }

    /* Sidebar background */
    div[data-testid="stSidebarContent"] { background-color: #1e2a3a; }

    /* All text inside sidebar */
    div[data-testid="stSidebarContent"] * { color: #e8edf2 !important; }

    /* Sidebar selectbox, inputs */
    div[data-testid="stSidebarContent"] .stSelectbox > div,
    div[data-testid="stSidebarContent"] .stTextInput > div > div {
        background-color: #2c3e50 !important;
        color: #e8edf2 !important;
        border-color: #4a6080 !important;
    }

    /* Sidebar buttons */
    div[data-testid="stSidebarContent"] button {
        background-color: #2c3e50 !important;
        color: #e8edf2 !important;
        border: 1px solid #4a6080 !important;
    }
    div[data-testid="stSidebarContent"] button:hover {
        background-color: #3d5166 !important;
    }

    /* Sidebar headings */
    div[data-testid="stSidebarContent"] h1,
    div[data-testid="stSidebarContent"] h2,
    div[data-testid="stSidebarContent"] h3 {
        color: #ffffff !important;
    }

    /* Sidebar expander label */
    div[data-testid="stSidebarContent"] .streamlit-expanderHeader {
        color: #e8edf2 !important;
    }

    /* Sidebar divider */
    div[data-testid="stSidebarContent"] hr { border-color: #4a6080; }
</style>
""", unsafe_allow_html=True)

# ── DB connection ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return psycopg2.connect(st.secrets["aiven"]["uri"])

def db():
    """Return a live connection, reconnecting if dropped."""
    conn = get_conn()
    try:
        conn.cursor().execute("SELECT 1")
    except Exception:
        st.cache_resource.clear()
        conn = get_conn()
    return conn

# ── DB bootstrap ──────────────────────────────────────────────────────────────
def init_db():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id   SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id         SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    sno        INTEGER NOT NULL,
                    task       TEXT NOT NULL DEFAULT '',
                    comments   TEXT NOT NULL DEFAULT '',
                    status     TEXT NOT NULL DEFAULT 'Pending'
                );
            """)
        conn.commit()

init_db()

# ── Project helpers ───────────────────────────────────────────────────────────
def get_projects():
    with db().cursor() as cur:
        cur.execute("SELECT name FROM projects ORDER BY id")
        return [r[0] for r in cur.fetchall()]

def get_project_id(name):
    with db().cursor() as cur:
        cur.execute("SELECT id FROM projects WHERE name = %s", (name,))
        row = cur.fetchone()
        return row[0] if row else None

def create_project(name):
    conn = db()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO projects (name) VALUES (%s)", (name,))
    conn.commit()

def delete_project(name):
    conn = db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM projects WHERE name = %s", (name,))
    conn.commit()

# ── Task helpers ──────────────────────────────────────────────────────────────
def load_tasks(project_name) -> pd.DataFrame:
    pid = get_project_id(project_name)
    if pid is None:
        return empty_df()
    with db().cursor() as cur:
        cur.execute(
            "SELECT sno, task, comments, status FROM tasks WHERE project_id = %s ORDER BY sno",
            (pid,)
        )
        rows = cur.fetchall()
    if not rows:
        return empty_df()
    df = pd.DataFrame(rows, columns=["S.No.", "Task", "Comments", "Status"])
    df["S.No."] = pd.to_numeric(df["S.No."], errors="coerce").fillna(0).astype(int)
    df["Task"]     = df["Task"].fillna("").astype(str)
    df["Comments"] = df["Comments"].fillna("").astype(str)
    df["Status"]   = df["Status"].fillna("Pending").astype(str)
    return df.reset_index(drop=True)

def save_tasks(project_name, df: pd.DataFrame):
    pid = get_project_id(project_name)
    if pid is None:
        return
    conn = db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE project_id = %s", (pid,))
        if not df.empty:
            rows = [
                (pid, int(row["S.No."]), str(row["Task"]), str(row["Comments"]), str(row["Status"]))
                for _, row in df.iterrows()
            ]
            cur.executemany(
                "INSERT INTO tasks (project_id, sno, task, comments, status) VALUES (%s, %s, %s, %s, %s)",
                rows
            )
    conn.commit()

def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["S.No.", "Task", "Comments", "Status"])

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📁 Projects")

    projects = get_projects()

    if projects:
        selected_project = st.selectbox("Active project", projects, key="proj_select")
    else:
        selected_project = None
        st.info("No projects yet. Add one below.")

    st.divider()

    with st.expander("➕ Add Project"):
        new_name = st.text_input("Project name", key="new_proj")
        if st.button("Create", key="btn_create"):
            name = new_name.strip()
            if not name:
                st.warning("Enter a name.")
            elif name in projects:
                st.warning("Already exists.")
            else:
                create_project(name)
                st.success(f"'{name}' created!")
                st.rerun()

    if selected_project:
        with st.expander("🗑️ Delete Project"):
            st.warning(f"Permanently deletes **{selected_project}** and all its tasks.")
            if st.button("Delete", type="primary", key="btn_del_proj"):
                delete_project(selected_project)
                st.success("Deleted.")
                st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">📋 NutraIQX Project Manager</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Track tasks · Powered by Aiven PostgreSQL · Deployable free on Streamlit Cloud</div>', unsafe_allow_html=True)

if not selected_project:
    st.info("👈 Create or select a project from the sidebar.")
    st.stop()

st.markdown(f"### 📂 {selected_project}")

# ── Session state per project ─────────────────────────────────────────────────
state_key = f"df_{selected_project}"
if state_key not in st.session_state:
    with st.spinner("Loading tasks…"):
        st.session_state[state_key] = load_tasks(selected_project)

df: pd.DataFrame = st.session_state[state_key]

# ── Toolbar ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("➕ Add Task", use_container_width=True):
        next_sno = int(df["S.No."].max()) + 1 if not df.empty else 1
        new_row = pd.DataFrame([{"S.No.": next_sno, "Task": "", "Comments": "", "Status": "Pending"}])
        st.session_state[state_key] = pd.concat([df, new_row], ignore_index=True)
        st.rerun()

with c2:
    if st.button("🗑️ Delete Selected", use_container_width=True):
        to_drop = st.session_state.get("_selected_rows", [])
        if to_drop:
            df = st.session_state[state_key].drop(index=to_drop).reset_index(drop=True)
            df["S.No."] = range(1, len(df) + 1)
            st.session_state[state_key] = df
            st.session_state["_selected_rows"] = []
            st.rerun()
        else:
            st.toast("Tick checkboxes below to select rows first.", icon="ℹ️")

with c3:
    if st.button("💾 Save Changes", use_container_width=True, type="primary"):
        with st.spinner("Saving…"):
            save_tasks(selected_project, st.session_state[state_key])
        st.toast("Saved to database ✅", icon="✅")

with c4:
    if st.button("🔄 Reload", use_container_width=True):
        del st.session_state[state_key]
        st.rerun()

st.divider()

# ── Color-coded HTML table ────────────────────────────────────────────────────
STATUS_STYLE = {
    "Resolved": ("background:#1a3d2b; color:#4ade80; border:1px solid #4ade80;", "🟢"),
    "Pending":  ("background:#3d3000; color:#facc15; border:1px solid #facc15;", "🟡"),
    "Partial":  ("background:#3d1f00; color:#fb923c; border:1px solid #fb923c;", "🟠"),
}

def build_table(df: pd.DataFrame) -> str:
    rows_html = ""
    for _, row in df.iterrows():
        status = str(row["Status"])
        style, icon = STATUS_STYLE.get(status, ("background:#333; color:#ccc; border:1px solid #666;", "⚪"))
        badge = f'<span style="padding:3px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; {style}">{icon} {status}</span>'
        task_text = str(row["Task"]).replace("<", "&lt;").replace(">", "&gt;")
        comment_text = str(row["Comments"]).replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        rows_html += f"""
        <tr style="border-bottom:1px solid #2a2a2a;">
            <td style="padding:10px 12px; color:#aaa; text-align:center; width:60px;">{int(row['S.No.'])}</td>
            <td style="padding:10px 12px; color:#e8edf2;">{task_text}</td>
            <td style="padding:10px 12px; color:#9aabb8; font-size:0.85rem;">{comment_text}</td>
            <td style="padding:10px 12px; text-align:center; white-space:nowrap;">{badge}</td>
        </tr>"""
    return f"""
    <table style="width:100%; border-collapse:collapse; background:#0e1117; border-radius:8px; overflow:hidden;">
        <thead>
            <tr style="background:#1a1f2e; border-bottom:2px solid #2a2a2a;">
                <th style="padding:10px 12px; color:#7a8a9a; text-align:center; width:60px;">S.No.</th>
                <th style="padding:10px 12px; color:#7a8a9a; text-align:left;">Task</th>
                <th style="padding:10px 12px; color:#7a8a9a; text-align:left;">Comments</th>
                <th style="padding:10px 12px; color:#7a8a9a; text-align:center; width:140px;">Status</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>"""

current_df = st.session_state[state_key]
if not current_df.empty:
    st.markdown(build_table(current_df), unsafe_allow_html=True)

st.divider()
st.markdown("**✏️ Edit tasks below, then click Save Changes:**")

edited = st.data_editor(
    st.session_state[state_key],
    column_config={
        "S.No.":    st.column_config.NumberColumn("S.No.", width="small", disabled=True),
        "Task":     st.column_config.TextColumn("Task",     width="large"),
        "Comments": st.column_config.TextColumn("Comments", width="large"),
        "Status":   st.column_config.SelectboxColumn(
            "Status",
            options=["Pending", "Resolved", "Partial"],
            width="medium",
            required=True,
        ),
    },
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    key="task_editor",
)
st.session_state[state_key] = edited

# ── Row selection for deletion ────────────────────────────────────────────────
if not df.empty:
    st.markdown("**Select rows to delete:**")
    selected = []
    num_cols = min(len(df), 10)
    cols = st.columns(num_cols)
    for i, row in df.iterrows():
        with cols[i % num_cols]:
            if st.checkbox(f"#{int(row['S.No.'])}", key=f"chk_{selected_project}_{i}"):
                selected.append(i)
    st.session_state["_selected_rows"] = selected

# ── Legend + metrics ──────────────────────────────────────────────────────────
st.divider()
l1, l2, l3 = st.columns(3)
l1.markdown("🟡 **Pending** — Not started")
l2.markdown("🟢 **Resolved** — Done")
l3.markdown("🟠 **Partial** — In progress")

if not edited.empty:
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Tasks",    len(edited))
    m2.metric("🟡 Pending",     (edited["Status"] == "Pending").sum())
    m3.metric("🟢 Resolved",    (edited["Status"] == "Resolved").sum())
    m4.metric("🟠 Partial",     (edited["Status"] == "Partial").sum())
