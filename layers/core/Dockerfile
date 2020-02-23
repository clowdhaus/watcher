FROM lambci/lambda:build-python3.8

WORKDIR /layer
COPY requirements.txt .

RUN pip install -r requirements.txt --upgrade --upgrade-strategy only-if-needed --target=./python \
    && zip -r -9 core.zip ./python
