FROM apache/airflow:2.6.2-python3.11

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
           build-essential \
           bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


USER airflow
COPY requirements.txt ./
RUN pip install --user -r requirements.txt