FROM python:2.7

RUN pip install Paste
RUN apt-get update -qq && apt-get install -y sqlite3

COPY README.txt development.ini setup.py /members/
COPY members /members/members
WORKDIR /members
RUN python setup.py develop

COPY docs /members/docs
COPY graphdata  /members/graphdata
COPY mails /members/mails

COPY scripts /members/scripts
RUN ["python", "scripts/mksqlitedb.py", "yy"]

ENTRYPOINT ["pserve", "development.ini", "--reload"]
