from absl import app
from absl import flags
from absl import logging
from pymongo import MongoClient
import re
from tqdm import tqdm

FLAGS = flags.FLAGS
flags.DEFINE_string('hostname', None, 'The Mongo DB database hostname.')
flags.DEFINE_string('database', None, 'The Mongo DB database name.')
flags.DEFINE_string('collection', None, 'The Mongo DB collection name.')
flags.DEFINE_string('username', None, 'The Mongo DB username.')
flags.DEFINE_string('password', None, 'The Mongo DB password.')
flags.DEFINE_string('output_csv', None, 'The CSV file for saving the results.')

IMAGE_URL_PATTERN = re.compile(
    r'^https://storage.googleapis.com/(.+)/(.+)/(.+)/(.+\..+)$')
OUTPUT_CSV_HEADER = 'Set,File,Left,Top,Width,Height\n'
OUTPUT_CSV_PATTERN = '%s,%s,%d,%d,%d,%d\n'


def main(_):
    # Connect to the database.
    client = MongoClient(
        host=FLAGS.hostname,
        username=FLAGS.username,
        password=FLAGS.password,
        authSource=FLAGS.database,
        authMechanism='SCRAM-SHA-1')
    database = client[FLAGS.database]
    collection = database[FLAGS.collection]

    # Collect the annotation results.
    bounding_boxes = {}
    num_images = 0
    num_boxes = 0
    num_missing = 0
    results = collection.find()
    for result in tqdm(results):
        if result['status'] != 'completed':
            logging.warning('Skipping task: %s (%s)' % (result['task_id'],
                                                        result['status']))
            continue

        annotations = result['response']['annotations']
        if not annotations:
            num_missing += 1
            continue

        image_url = result['params']['attachment']
        image_url_match = IMAGE_URL_PATTERN.match(image_url)
        image_set = image_url_match.group(2)
        image_file = image_url_match.group(4)
        num_images += 1

        for annotation in annotations:
            left = annotation['left']
            top = annotation['top']
            width = annotation['width']
            height = annotation['height']
            bounding_box = left, top, width, height

            index = (image_set, image_file)
            if index in bounding_boxes:
                bounding_boxes[index].append(bounding_box)
            else:
                bounding_boxes[index] = [bounding_box]
            num_boxes += 1
    logging.info('Found %d images with %d bounding boxes. '
                 'Skipped %d images without annotations.' % (
                     num_images, num_boxes, num_missing))

    # Write the output CSV.
    with open(FLAGS.output_csv, 'w') as csv_file:
        csv_file.write(OUTPUT_CSV_HEADER)
        for image_set, image_file in tqdm(sorted(bounding_boxes)):
            for bounding_box in bounding_boxes[(image_set, image_file)]:
                left, top, width, height = bounding_box
                csv_file.write(OUTPUT_CSV_PATTERN % (image_set, image_file,
                                                     left, top, width, height))


if __name__ == '__main__':
    app.run(main)
