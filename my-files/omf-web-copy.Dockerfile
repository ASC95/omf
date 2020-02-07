FROM ubuntu:18.04
RUN apt-get -y update && apt-get -y upgrade
RUN apt-get -y install python3-pip
RUN apt-get install -y sudo vim
RUN ln -s /usr/bin/python3.6 /usr/local/bin/python
RUN ln -s /usr/bin/pip3 /usr/local/bin/pip
WORKDIR /home/omf/omf
COPY omf .
WORKDIR /home/omf
COPY install.py .
COPY requirements.txt .
COPY setup.py .
RUN python install.py
RUN pip install -r requirements.txt
RUN pip install tensorflow fbprophet
WORKDIR /home/omf/omf
#ENV LC_ALL C.UTF-8
#ENV LANG C.UTF-8
#ENV LANGUAGE C.UTF-8
ENTRYPOINT ["python"]
CMD ["-m", "web"]
