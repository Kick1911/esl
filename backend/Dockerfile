FROM python:3 AS build

WORKDIR /compose/hello-docker
COPY requirements.txt ./
RUN apt update && apt install swig -y
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py main.py

# FROM scratch
# COPY --from=build /compose/hello-docker/backend /usr/local/bin/backend
CMD ["python", "main.py"]


