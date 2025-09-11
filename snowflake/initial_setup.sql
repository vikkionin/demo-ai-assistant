------------------------------------------------------------------------------
-- Set up users, roles, and permissions

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

grant execute task on account to role st_assistant_pipeline;

-- Grant the _user and _pipeline roles to the current role, so we can
-- debug things easily.
set current_role = (select current_role());
grant role st_assistant_user to role identifier($current_role);
grant role st_assistant_pipeline to role identifier($current_role);


------------------------------------------------------------------------------
-- Set up network rules, so we can access docs.streamlit.io and github.

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

grant usage on integration st_assistant_external_integrations to role st_assistant_pipeline;


------------------------------------------------------------------------------
-- Set up DBs, schemas, and tables

set db_name = 'st_assistant';

create database if not exists identifier($db_name);
use database identifier($db_name);

create schema if not exists public;
use schema public;

grant create task on schema public to role st_assistant_pipeline;
grant create git repository on schema public to role st_assistant_pipeline;

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

alter table streamlit_docstrings_chunks set change_tracking = true;
alter table streamlit_docs_pages_chunks set change_tracking = true;

grant ownership on table streamlit_docstrings_chunks to role st_assistant_pipeline;
grant ownership on table streamlit_docs_pages_chunks to role st_assistant_pipeline;


------------------------------------------------------------------------------
-- Set up Cortex Search services

create or replace cortex search service streamlit_docstrings_search_service
    on docstring_chunk
    attributes streamlit_version, command_name
    warehouse = compute_wh
    target_lag = '1 minute'
    as (
        select *
        from streamlit_docstrings_chunks
    );

create or replace cortex search service streamlit_docs_pages_search_service
    on page_chunk
    attributes page_url
    warehouse = compute_wh
    target_lag = '1 minute'
    as (
        select *
        from streamlit_docs_pages_chunks
    );

grant usage on
    cortex search service
    streamlit_docs_pages_search_service
    to st_assistant_user;

grant usage on
    cortex search service
    streamlit_docstrings_search_service
    to st_assistant_user;
