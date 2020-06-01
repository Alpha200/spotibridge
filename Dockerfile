FROM python:3.8-alpine

RUN apk add --no-cache git zlib-dev jpeg-dev gcc musl-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER 1000:1000

CMD [ "python", "-u", "main.py" ]
