from absl import app
from absl import flags
from absl import logging
import cv2
import json
import numpy as np
from os import makedirs
from os import path
import re
from tqdm import tqdm

FLAGS = flags.FLAGS
flags.DEFINE_string('input_dir', None, 'The directory containing one part of '
                    'the FLIR ADAS dataset.')
flags.DEFINE_string('annotations_json', 'thermal_annotations.json', 'The JSON '
                    'file with the annotations inside the dataset directory.')
flags.DEFINE_list('categories', 'person,human face', 'The list of category '
                  'labels consider.')
flags.DEFINE_integer('min_box_width', 25, 'The minimum width in pixels for an '
                     'annotation to be considered.')
flags.DEFINE_string('output_dir', None, 'The directory in which to save the '
                    'converted images.')
flags.DEFINE_string('output_csv', None, 'The CSV file for saving the results.')

# The filename patterns used to translate between image versions.
FILENAME_PATTERN_8_BIT = re.compile(r'thermal_8_bit/FLIR(_video)?_(\d+).jpeg')
FILENAME_PATTERN_16_BIT = 'thermal_16_bit/FLIR%s_%05d.tiff'
NORM_DIR = 'thermal_normalized'
FILENAME_PATTERN_NORM = path.join(NORM_DIR, 'FLIR%s_%05d.png')


def get_masked_range(image, bounding_boxes):
    min_value = None
    max_value = None

    # Find the global minimum and maximum values within the bounding boxes.
    for left, top, width, height in bounding_boxes:
        right = left + width
        bottom = top + height

        crop = image[top:bottom, left:right]

        if min_value:
            min_value = min(min_value, crop.min())
        else:
            min_value = crop.min()

        if max_value:
            max_value = max(max_value, crop.max())
        else:
            max_value = crop.max()

    return min_value, max_value


def main(_):
    annotations_path = path.join(FLAGS.input_dir, FLAGS.annotations_json)
    with open(annotations_path) as json_file:
        annotations = json.load(json_file)

    # Look up the relevant category IDs.
    category_ids = []
    for category in tqdm(annotations['categories']):
        if category['name'] in FLAGS.categories:
            category_ids.append(category['id'])
    assert category_ids

    # Build an image ID to image filename index.
    image_index = {}
    for image in tqdm(annotations['images']):
        image_index[image['id']] = image['file_name']

    # Find the images with relevant categories and save their bounding boxes.
    images = {}
    num_annotations = 0
    num_discarded_size = 0
    for annotation in tqdm(annotations['annotations']):
        # Only consider the relevant categories.
        if not annotation['category_id'] in category_ids:
            continue

        # Discard small bounding boxes.
        bounding_box = annotation['bbox']
        if bounding_box[2] < FLAGS.min_box_width:
            num_discarded_size += 1
            continue

        image_id = annotation['image_id']
        if image_id in images:
            images[image_id].append(bounding_box)
        else:
            images[image_id] = [bounding_box]
        num_annotations += 1
    logging.info('Found %d relevant annotations in %d images. '
                 'Discarded %d due to size.' % (num_annotations,
                                                len(images),
                                                num_discarded_size))

    # Save the normalized images and collect their paths.
    image_paths = []
    norm_path = path.join(FLAGS.output_dir, NORM_DIR)
    if not path.exists(norm_path):
        makedirs(norm_path)
    for image_id in tqdm(images):
        # Translate the image filenames.
        filename_8_bit = image_index[image_id]
        filename_match = FILENAME_PATTERN_8_BIT.match(filename_8_bit)
        filename_video = filename_match.group(1) or ''
        filename_id = int(filename_match.group(2))
        filename_16_bit = FILENAME_PATTERN_16_BIT % (filename_video,
                                                     filename_id)
        filename_norm = FILENAME_PATTERN_NORM % (filename_video, filename_id)

        # Read the 16-bit image.
        input_path = path.join(FLAGS.input_dir, filename_16_bit)
        image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
        assert image.dtype == np.uint16

        # Normalize the image to the maximum range within bounding boxes.
        min_value, max_value = get_masked_range(image, images[image_id])
        image = (np.float32(image) - min_value) / (max_value - min_value)

        # Convert the image to 8-bit.
        np.clip(255 * image, 0, 255, out=image)
        image = np.uint8(image)

        # Save the image.
        assert image.dtype == np.uint8
        output_path = path.join(FLAGS.output_dir, filename_norm)
        if not cv2.imwrite(output_path, image):
            raise IOError('Failed to save image: %s' % output_path)

        image_paths.append(output_path)
    image_paths.sort()

    # Save the image paths to the output CSV.
    with open(FLAGS.output_csv, 'w') as csv_file:
        for image_path in tqdm(image_paths):
            csv_file.write('%s\n' % image_path)


if __name__ == '__main__':
    app.run(main)
