FROM alpine:3.6

RUN apk add --no-cache python imagemagick-dev ghostscript ca-certificates && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools && \
    rm -r /root/.cache

RUN pip install ftrack-python-api

COPY image_encode.py /image_encode.py

ENV FTRACK_SERVER=https://ftrack.wetaworkshop.co.nz FTRACK_API_USER=root FTRACK_API_KEY=72baaed0-1816-11e7-8c7e-005056a84326 FTRACK_LOGLEVEL=info

CMD python /image_encode.py -v ${FTRACK_LOGLEVEL}