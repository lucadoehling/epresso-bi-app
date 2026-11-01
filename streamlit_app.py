"""E-Presso BI Analyst interface.

Checkpoint 1 loads multiple source exports, profiles every table, states its
grain, and validates relationship keys before combined metrics are allowed.
Business calculations stay in analytics.py; assistant routing stays in agent.py.
"""
import streamlit as st

import agent
import analytics

MAX_QUESTIONS = 15  # per-session limit for the assistant

st.set_page_config(page_title='E-Presso BI Analyst', layout='wide')
st.title('E-Presso BI Analyst')
st.caption('Upload, profile, and validate the E-Presso source-table exports.')


@st.cache_data(show_spinner=False)
def cached_load(file_bytes: bytes, filename: str, sheet_name):
    # The cache is keyed on file CONTENTS, so an updated file is never confused
    # with an earlier upload that happened to use the same filename.
    return analytics.load_table(file_bytes, filename, sheet_name)


with st.sidebar:
    st.header('E-Presso data')
    st.caption('Upload the five CSV exports together, or upload CSV/Excel files to profile individually.')
    uploads = st.file_uploader(
        'Upload CSV or Excel files',
        type=['csv', 'txt', 'tsv', 'xlsx', 'xls'],
        accept_multiple_files=True,
    )

    sheet_choices = {}
    for item in uploads:
        if item.name.lower().endswith(analytics.EXCEL_EXT):
            sheet_choices[item.name] = st.selectbox(
                f'Sheet — {item.name}',
                analytics.excel_sheet_names(item.getvalue()),
                key=f'sheet-{item.name}',
            )

if not uploads:
    st.info(
        'Upload one or more files in the sidebar. For the full relationship check, '
        'upload categories.csv, products.csv, stores.csv, survey_results.csv, and sales.csv.'
    )
    st.stop()

loaded_files = {}
load_errors = []
for item in uploads:
    try:
        sheet = sheet_choices.get(item.name, 0)
        loaded_files[item.name] = cached_load(item.getvalue(), item.name, sheet)
    except Exception as exc:  # show readable errors without exposing a traceback
        load_errors.append(f'{item.name}: {exc}')

for message in load_errors:
    st.error(f'Could not read {message}')
if not loaded_files:
    st.stop()

# Identify tables from required columns rather than trusting filenames. This
# preserves correct grain/key documentation if a user renames an export.
epresso_tables = {}
file_types = {}
for filename, frame in loaded_files.items():
    table_name = analytics.identify_epresso_table(frame)
    file_types[filename] = table_name
    if table_name and table_name not in epresso_tables:
        epresso_tables[table_name] = frame
    elif table_name:
        st.warning(f'{filename} also looks like {table_name}; only the first matching table is used for joins.')

tab_profile, tab_relationships, tab_dash, tab_assistant = st.tabs(
    ['Data profiles', 'Grain and relationships', 'Dashboard', 'Assistant']
)

with tab_profile:
    st.subheader('Loaded datasets')
    inventory = []
    for filename, frame in loaded_files.items():
        table_name = file_types[filename]
        inventory.append({
            'file': filename,
            'identified_table': table_name or 'Unrecognized / generic table',
            'rows': len(frame),
            'columns': frame.shape[1],
        })
    st.dataframe(inventory, use_container_width=True, hide_index=True)

    selected_file = st.selectbox('Profile a dataset', list(loaded_files))
    df = loaded_files[selected_file]
    table_name = file_types[selected_file]
    profile = analytics.profile_table(df)

    if table_name:
        spec = analytics.EPRESSO_TABLES[table_name]
        st.markdown(f"**Table:** {table_name}  ")
        st.markdown(f"**Grain:** {spec['grain']}  ")
        st.markdown(f"**Candidate primary key:** `{spec['key']}`")
        key = analytics.key_profile(df, spec['key'])
        if key['unique']:
            st.success(f"{spec['key']} is complete and unique at the stated grain.")
        else:
            st.warning(
                f"{spec['key']} is not a safe one-side key: "
                f"{key['missing']} missing and {key['duplicate_values']} duplicate value(s)."
            )
    else:
        st.warning('This file does not match a documented E-Presso table structure.')

    c1, c2, c3 = st.columns(3)
    c1.metric('Rows', f"{profile['rows']:,}")
    c2.metric('Columns', profile['columns'])
    c3.metric('Duplicate rows', profile['duplicate_rows'])

    st.subheader('Preview')
    st.dataframe(df.head(50), use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.subheader('Missing values')
        st.dataframe(profile['missing'], use_container_width=True, hide_index=True)
    with right:
        st.subheader('Field names and data types')
        st.dataframe(profile['dtypes'], use_container_width=True, hide_index=True)

with tab_relationships:
    st.subheader('Documented table grain')
    grain_rows = []
    for name, spec in analytics.EPRESSO_TABLES.items():
        grain_rows.append({
            'table': name,
            'loaded': name in epresso_tables,
            'one row represents': spec['grain'],
            'candidate key': spec['key'],
        })
    st.dataframe(grain_rows, use_container_width=True, hide_index=True)

    required = set(analytics.EPRESSO_TABLES)
    missing_tables = sorted(required - set(epresso_tables))
    if missing_tables:
        st.info(
            'Upload all five recognized table exports to run relationship checks. '
            f"Still needed: {', '.join(missing_tables)}."
        )
    else:
        checks = analytics.check_epresso_relationships(epresso_tables)
        if not checks.empty and checks['passed'].all():
            st.success(
                'All four many-to-one joins matched every Sales row and preserved '
                'both the Sales row count and the uploaded Revenue total.'
            )
        else:
            st.error('At least one proposed relationship failed. Do not calculate combined metrics yet.')
        st.dataframe(checks, use_container_width=True, hide_index=True)
        st.caption(
            'Revenue before and after each join is calculated from the uploaded Sales table. '
            'The app does not hardcode a source total.'
        )

with tab_dash:
    st.info(
        'Checkpoint 2 will add KPIs, filters, and charts here. Combined metrics remain '
        'disabled until the Checkpoint 1 relationship checks pass.'
    )

with tab_assistant:
    st.caption('Mode: rules-based starter. It answers only through approved analytical functions.')
    assistant_file = st.selectbox('Assistant dataset', list(loaded_files), key='assistant-file')
    assistant_df = loaded_files[assistant_file]
    st.session_state.setdefault('n_questions', 0)
    st.session_state.setdefault('history', [])
    for item in st.session_state['history']:
        with st.chat_message('user'):
            st.write(item['question'])
        with st.chat_message('assistant'):
            st.markdown(f"**Scope:** {item['answer']['scope']}")
            st.markdown(f"**Findings:** {item['answer']['findings']}")
            if item['answer']['interpretation']:
                st.markdown(f"**Interpretation:** {item['answer']['interpretation']}")
            with st.expander('Tool-call log'):
                st.json(item['answer']['tool_log'])
    question = st.chat_input('Ask about missing values or duplicates in the selected dataset')
    if question:
        if st.session_state['n_questions'] >= MAX_QUESTIONS:
            st.warning('Question limit reached for this session. Reload the page to start over.')
        else:
            st.session_state['n_questions'] += 1
            answer = agent.answer_question(question, assistant_df, mode='rules')
            st.session_state['history'].append({'question': question, 'answer': answer})
            st.rerun()
