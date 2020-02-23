FROM lambci/lambda:build-python3.8

WORKDIR /layer
COPY requirements.txt .

ENV PY_DIR='python/lib/python3.8/site-packages'

RUN pip install -r requirements.txt --upgrade --upgrade-strategy only-if-needed --target=$PY_DIR \
    && zip -r -9 core.zip $PY_DIR
