from packaging import version
import json
import re

from langchain.text_splitter import RecursiveJsonSplitter
import pandas as pd

PAGE_SEP_RE = re.compile("^---$", flags=re.MULTILINE)
URL_RE = re.compile("^Source: (.*)$", flags=re.MULTILINE)


def update_dict_with_latest_streamlit_version(docstrings_dict):
    all_versions = []

    for v_str in docstrings_dict.keys():
        try:
            v = version.parse(v_str)
        except version.InvalidVersion:
            continue

        all_versions.append(v)

    latest_version = max(all_versions)
    docstrings_dict["latest"] = docstrings_dict[str(latest_version)]

    print("Detected latest Streamlit version as ", latest_version)


def model(dbt, session):
    dbt.config(
        materialized="table",
        packages=[
            "langchain",
            "pandas",
        ],
        post_hook="ALTER CORTEX SEARCH SERVICE streamlit_docstrings_search_service REFRESH;",
    )

    json_splitter = RecursiveJsonSplitter()

    url = "https://raw.githubusercontent.com/streamlit/docs/refs/heads/main/python/streamlit.json"
    df = session.sql(f"select http_get_or_fail('{url}') as page_text;")
    full_str = df.to_pandas().iat[0, 0]
    docstrings_dict = json.loads(full_str)

    update_dict_with_latest_streamlit_version(docstrings_dict)

    docstrings_table_rows = []

    for st_version, version_docs in docstrings_dict.items():
        for command_name, command_docstring_obj in version_docs.items():
            chunks = json_splitter.split_text(command_docstring_obj)

            for chunk in chunks:
                docstrings_table_rows.append(
                    dict(
                        STREAMLIT_VERSION=st_version,
                        COMMAND_NAME=command_name,
                        DOCSTRING_CHUNK=chunk,
                    )
                )

    return pd.DataFrame(docstrings_table_rows)
