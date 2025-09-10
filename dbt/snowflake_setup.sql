------------------------------------------------------------------------------
-- Configure users, roles, and permissions

create role if not exists st_assistant_user;
create role if not exists st_assistant_pipeline;

create user if not exists st_assistant_user;
alter user st_assistant_user set type = service;

create user if not exists st_assistant_pipeline;
alter user st_assistant_pipeline set type = service;

grant role st_assistant_user to user st_assistant_user;
grant role st_assistant_pipeline to user st_assistant_pipeline;

grant usage on warehouse compute_wh to role st_assistant_user;
grant usage on warehouse compute_wh to role st_assistant_pipeline;

-- Grant privileges to the current role, so we can debug things easily.
set current_role = (select current_role());
grant role st_assistant_user to role identifier($current_role);
grant role st_assistant_pipeline to role identifier($current_role);

------------------------------------------------------------------------------
-- Configure network rules

create or replace network rule st_assistant_github_network_rule
  mode = egress
  type = host_port
  value_list = ('raw.githubusercontent.com');

create or replace network rule st_assistant_docs_network_rule
  mode = egress
  type = host_port
  value_list = ('docs.streamlit.io');

create or replace external access integration st_assistant_external_integrations
  allowed_network_rules = (st_assistant_github_network_rule, st_assistant_docs_network_rule)
  enabled = true;

------------------------------------------------------------------------------
-- Configure things that need to be duplicated for dev vs prod

-- IMPORTANT: Uncomment the database you'd like to use.
-- set db_name = 'st_assistant';  -- Used for production.
set db_name = 'st_assistant_dev';  -- Used for development.

create database if not exists identifier($db_name);
use database identifier($db_name);

create schema if not exists public;
use schema public;

-- Grant privileges to the role that the AI assistant will be running as.
grant usage on database identifier($db_name) to role st_assistant_user;
grant usage on schema public to role st_assistant_user;

-- Grant privileges to the role that pipeline will be running as.
grant usage on database identifier($db_name) to role st_assistant_pipeline;
grant usage on schema public to role st_assistant_pipeline;
grant create cortex search service on schema public to role st_assistant_pipeline;
grant create table on schema public to role st_assistant_pipeline;
grant modify on schema public to role st_assistant_pipeline;
grant usage on schema public to role st_assistant_pipeline;

-- Create tables and set them up

create table if not exists streamlit_docstrings_chunks (
  streamlit_version string,
  command_name string,
  docstring_chunk string
);

create table if not exists streamlit_docs_pages_chunks (
  page_url string,
  page_chunk string
);

grant ownership on table streamlit_docstrings_chunks to role st_assistant_pipeline;
grant ownership on table streamlit_docs_pages_chunks to role st_assistant_pipeline;

-- Create a UDF that can read text from a public URL.
create or replace function http_get_or_fail(url string)
  returns table(text string)
  language python
  runtime_version = '3.12'
  external_access_integrations = (st_assistant_external_integrations)
  packages = ('requests')
  handler = 'Generator'
as $$
import requests

class Generator:
    def process(self, url):
        response = requests.get(url)
        response.raise_for_status()
        for line in response.text.splitlines():
            yield (line,)
$$;

grant usage on function http_get_or_fail(string) to st_assistant_pipeline;
