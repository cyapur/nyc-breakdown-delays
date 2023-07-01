from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator
from sodapy import Socrata
import pandas as pd
import os
import json

from airflow import models, settings

default_args = {
    "start_date": datetime(2023, 6, 26),
}

dag = DAG(
    "nyc_bus_data_ingestion",
    default_args=default_args,
    description="A DAG to ingest NYC bus data",
    schedule_interval="0 12 * * *",
    catchup=False,
)

# Set up the connection details for PostgreSQL
conn = models.Connection(
    conn_id='postgres_default_2',
    conn_type='postgres',
    host='postgres',
    schema='postgres_db',
    login='admin',
    password='admin'
)

def create_conn_and_var():
    session = settings.Session()
    session.add(conn)
    session.commit()

create_conn = PythonOperator(
    task_id="create_conn",
    python_callable=create_conn_and_var,
    dag=dag
)

def get_bus_data(ti):
    client = Socrata("data.cityofnewyork.us", None)
    results = client.get("ez4e-fazm", limit=2000)
    ti.xcom_push(key="data", value=results)

def get_pg_table_columns():
    pg_hook = PostgresHook(postgres_conn_id='postgres_default_2')
    query = "SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'nyc_bus_data' ORDER BY ordinal_position"
    result = pg_hook.get_records(query)
    print(result)

get_columns = PythonOperator(
    task_id="get_pg_table_columns",
    python_callable=get_pg_table_columns,
    dag=dag,
)

def save_data_to_csv(ti, **kwargs):
    data = ti.xcom_pull(task_ids='get_bus_data', key='data')
    df = pd.DataFrame(data)
    file_name = os.path.join("/opt/csv_data", "nyc_bus_data.csv")
    df.to_csv(file_name, index=False)

def save_data_to_postgres(ti, **kwargs):
    data = ti.xcom_pull(task_ids='get_bus_data', key='data')
    df = pd.DataFrame(data).astype({'school_year': str, 
                                   'busbreakdown_id': str, 
                                   'run_type': str, 
                                   'bus_no': str, 
                                   'route_number': str, 
                                   'reason': str, 
                                   'schools_serviced': str, 
                                   'occurred_on': str, 
                                   'created_on': str, 
                                   'boro': str, 
                                   'bus_company_name': str, 
                                   'number_of_students_on_the_bus': str, 
                                   'has_contractor_notified_schools': str, 
                                   'has_contractor_notified_parents': str, 
                                   'have_you_alerted_opt': str, 
                                   'informed_on': str, 
                                   'last_updated_on': str, 
                                   'breakdown_or_running_late': str, 
                                   'school_age_or_prek': str, 
                                   'how_long_delayed': str, 
                                   'incident_number': str})
    print("Dataframe dtypes: ", df.dtypes)
    pg_hook = PostgresHook(postgres_conn_id='postgres_default_2')
    pg_hook.insert_rows('nyc_bus_data', df.to_dict('records'), target_fields=df.columns.tolist())

get_data = PythonOperator(
    task_id="get_bus_data",
    python_callable=get_bus_data,
    provide_context=True,
    dag=dag,
)

save_data_csv = PythonOperator(
    task_id="save_data_csv",
    python_callable=save_data_to_csv,
    provide_context=True,
    dag=dag,
)

save_data_postgres = PythonOperator(
    task_id="save_data_postgres",
    python_callable=save_data_to_postgres,
    provide_context=True,
    dag=dag,
)

create_table = PostgresOperator(
    task_id='create_table',
    postgres_conn_id='postgres_default_2',
    sql="""
    CREATE TABLE IF NOT EXISTS nyc_bus_data (
        school_year TEXT,
        busbreakdown_id TEXT,
        run_type TEXT,
        bus_no TEXT,
        route_number TEXT,
        reason TEXT,
        schools_serviced TEXT,
        occurred_on TEXT,
        created_on TEXT,
        boro TEXT,
        bus_company_name TEXT,
        number_of_students_on_the_bus TEXT,
        has_contractor_notified_schools TEXT,
        has_contractor_notified_parents TEXT,
        have_you_alerted_opt TEXT,
        informed_on TEXT,
        last_updated_on TEXT,
        breakdown_or_running_late TEXT,
        school_age_or_prek TEXT,
        how_long_delayed TEXT,
        incident_number TEXT
    );
    """,
    dag=dag,
)

create_conn >> get_data >> create_table >> get_columns >> [save_data_csv, save_data_postgres]
