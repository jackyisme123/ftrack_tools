FROM alpine:3.6

RUN apk add --no-cache python git && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools && \
    rm -r /root/.cache

RUN pip install ftrack-python-api git+https://bitbucket.org/ftrack/ftrack-action-handler.git

COPY clone_task_with_all_notes.py /clone_task_with_all_notes.py

ENV FTRACK_SERVER=http://192.168.9.82/ FTRACK_API_USER=root FTRACK_API_KEY=72baaed0-1816-11e7-8c7e-005056a84326 FTRACK_LOGLEVEL=info

CMD python /clone_task_with_all_notes.py -v ${FTRACK_LOGLEVEL}
