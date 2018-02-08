# :coding: utf-8
# :copyright: Copyright (c) 2017 Weta Workshop

# This event listener can be used to make uploaded images reviewable when
# running a local installation.
# This event listener was tested against server version 3.3.21 and requires at
# least 3.3.18.
# Note: This action will currently not handle versions added via the upload
# media dialog, since their versions are created after the components.
# Version 1.1
# - Update thumbnail for task as well when a new version is uploaded
# Version 1.0
# - Initial release

import os
import logging
import time
import ftrack_api.symbol
import subprocess
import shlex
import urllib
import json
import sys
import argparse


ftrack_api.symbol.SERVER_LOCATION_ID
UPLOAD_TYPE_ID = '8f4144e0-a8e6-11e2-9e96-0800200c9a66'
# set all file types which can be accepted
FILE_TYPE_ACCEPTED = ['.jpg', '.png', '.jpeg', '.tif', '.tiff', '.pdf', '.psd']
# set thumbnail size and quality
THUMBNAIL_IMAGE_SIZE = '80%'
THUMBNAIL_IMAGE_QUALITY = '90%'

def main(arguments=None):
    """Set up logging and register action."""
    if arguments is None:
        arguments = []

    parser = argparse.ArgumentParser()
    # Allow setting of logging level from arguments.
    logging_levels = {}
    for level in (
            logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING,
            logging.ERROR, logging.CRITICAL
    ):
        logging_levels[logging.getLevelName(level).lower()] = level

    parser.add_argument(
        '-v', '--verbosity',
        help='Set the logging output verbosity.',
        choices=logging_levels.keys(),
        default='info'
    )
    namespace = parser.parse_args(arguments)

    # Set up basic logging.
    logging.basicConfig(
        format='%(asctime)s %(message)s',
        level=logging_levels[namespace.verbosity]
    )

    def callback(event):
        """Handle callback."""
        logging.debug('callback called')
        data = event.get('data')
        server_location = session.query('Location where name is "ftrack.server"').one()
        component_id = data.get('component_id')
        component = session.query(
            'select version.thumbnail_id, version.asset.type_id, version.components from Component where id is {0}'.format(
                component_id
            )
        ).one()
        version_id = component['version_id']
        original_file_name = component['name']
        # change component name to lower case
        original_file_type = component['file_type'].lower()
        if original_file_type not in FILE_TYPE_ACCEPTED:
            logging.debug('Uploading file type not in JPG/JPEG, TIFF/TIF, PSD, PNG, PDF')
            return
        if component['name'] == 'ftrackreview-image':
            logging.debug('Thumbnail has been existed')
            return
        version1 = component['version']
        task = version1['task']
        if not version1:
            logging.debug('Not a version')
            return
        img_url = server_location.get_url(component)
        input_url = '/tmp/' + original_file_name + original_file_type
        # adjust input file name, remove " " and "_", which can not be accepted in subprocess call
        input_url = input_url.replace(" ", "")
        input_url = input_url.replace("_", "")
        logging.debug('start copying the uploading file')
        urllib.urlretrieve(img_url, input_url)
        urllib.urlcleanup()
        logging.debug('copying finished')
        output_url = '/tmp/thumbnail.jpg'

        if original_file_type == '.pdf':
            cmd = 'gs -dNOPAUSE -dBATCH -sDEVICE=jpeg -dNumRenderingThreads=2  -dLastPage=1 -sOutputFile=' + output_url +\
                  ' -c 30000000 setvmthreshold -f "' + input_url + '"'
            args = shlex.split(cmd)
            logging.debug('start converting file type = ' + original_file_type + 'filename = ' + original_file_name)
            result = subprocess.call(args)
            if result == 0:        # if result is 0, work successfully, otherwise fails
                logging.debug('converting finished')
            else:
                logging.critical('fail to convert file' + original_file_name)
        else:
            # modify thumbnail size and quality by adjusting parameter '-resize and -quality'
            cmd = 'magick convert "' + input_url + '[0]"' + ' -resize ' + THUMBNAIL_IMAGE_SIZE + ' -quality '\
                  + THUMBNAIL_IMAGE_QUALITY + ' ' + output_url
            logging.debug('start converting file type = ' + original_file_type + 'filename = ' + original_file_name)
            args = shlex.split(cmd)
            start_time = time.time()
            result = subprocess.call(args)
            # check file converting time
            cost_time = str(time.time() - start_time)
            if result == 0:        # if result is 0, work successfully, otherwise fails
                logging.debug('converting finished cost ' + cost_time + ' s')
            else:
                logging.critical('fail to convert file' + original_file_name)
        thumbnail_file_size = str(os.path.getsize(output_url))
        logging.debug('thumbnail size is ' + thumbnail_file_size)
        components = version1['components']
        thumbnail_component = session.create_component(
            output_url,
            data={
                'name': 'ftrackreview-image'
            },
            location=server_location
        )
        # use thumbnail component as the component of view
        component = thumbnail_component
        task['thumbnail'] = thumbnail_component
        if version1['asset']['type_id'] != UPLOAD_TYPE_ID:
            logging.warning('Asset is not of upload type.')
            return

        if version1['thumbnail_id']:
            logging.info('Skipping since version has thumbnail.')
            return

        if len(components) != 1:
            logging.critical('More than one component, not sure what to do.')
            return

    # links with version and component one another
        version1['thumbnail_id'] = component['id']
        component['version_id'] = version_id  # if lose this statement, thumbnail won't be showed in version
        component['metadata']['ftr_meta'] = json.dumps({
            'format': 'image'
        })

        # remove the two files in docker /tmp/
        try:
            os.remove(input_url)
            os.remove(output_url)
        except Exception:
            logging.error("files cannot be removed")
            raise
        logging.debug('thumbnail and uploading images have been removed')

        try:
            session.commit()
            logging.info(original_file_name + original_file_type + ' successfully finished work.')
        except Exception:
            session.rollback()
            raise


    # Subscribe to events with the update topic.
    session = ftrack_api.Session()
    session.event_hub.subscribe(
        'topic=ftrack.location.component-added and data.location_id={0}'.format(
            ftrack_api.symbol.SERVER_LOCATION_ID
        ),
        callback
    )
    session.event_hub.wait()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

