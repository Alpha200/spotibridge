FROM python:3.7-alpine

WORKDIR /usr/src/app

RUN apk --no-cache add git

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER 1000:1000

CMD [ "python", "main.py" ]
