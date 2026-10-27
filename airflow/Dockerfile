FROM apache/airflow:3.3.2

COPY airflow/requirements.txt /opt/airflow/requirements-solar.txt

RUN pip install --no-cache-dir \
    "apache-airflow==3.3.2" \
    -r /opt/airflow/requirements-solar.txt
