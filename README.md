# FLIR ADAS Faces

Face bounding boxes for the [FLIR ADAS Thermal Dataset](https://www.flir.com/oem/adas/adas-dataset-form/).

## License

Only the annotation data ([bounding-boxes.csv](https://github.com/maxbbraun/flir-adas-faces/releases/download/v1.0/bounding-boxes.csv)) is licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/) license.

The original terms and conditions of the [FLIR ADAS Terms of Use](https://www.flir.com/oem/adas/adas-dataset-form) apply to the images.

## Method

#### 1. Follow the [instructions](https://www.flir.com/oem/adas/adas-dataset-form/) to download the `FLIR_ADAS_1_3.tar.*` files, then extract them:

```bash
FLIR_ADAS_DIR="flir-adas-database"
mkdir $FLIR_ADAS_DIR
tar -C $FLIR_ADAS_DIR -xvf FLIR_ADAS_1_3.tar.001 --strip-components=1
```

#### 2. Filter the dataset down to images with people.

```bash
TMP_FLIR_ADAS_DIR="/tmp/$FLIR_ADAS_DIR"
TRAIN_CSV="train-people.csv"
VAL_CSV="val-people.csv"
VIDEO_CSV="video-people.csv"

python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt

python flir_convert.py \
  --input_dir=$FLIR_ADAS_DIR/train \
  --output_dir=$TMP_FLIR_ADAS_DIR/train \
  --output_csv=$TRAIN_CSV
python flir_convert.py \
  --input_dir=$FLIR_ADAS_DIR/val \
  --output_dir=$TMP_FLIR_ADAS_DIR/val \
  --output_csv=$VAL_CSV
python flir_convert.py \
  --input_dir=$FLIR_ADAS_DIR/video \
  --output_dir=$TMP_FLIR_ADAS_DIR/video \
  --output_csv=$VIDEO_CSV

FLIR_ADAS_PEOPLE_CSV="flir-adas-people.csv"
rm -f $FLIR_ADAS_PEOPLE_CSV
cat $TRAIN_CSV >> $FLIR_ADAS_PEOPLE_CSV
cat $VAL_CSV >> $FLIR_ADAS_PEOPLE_CSV
cat $VIDEO_CSV >> $FLIR_ADAS_PEOPLE_CSV
```

#### 3. Upload the images to [Cloud Storage](https://cloud.google.com/storage).

```bash
FLIR_ADAS_BUCKET="gs://$FLIR_ADAS_DIR"
LOCATION="us-central1"
gsutil mb -l $LOCATION $FLIR_ADAS_BUCKET
gsutil iam ch allUsers:objectViewer $FLIR_ADAS_BUCKET

gsutil -m rsync -r $TMP_FLIR_ADAS_DIR $FLIR_ADAS_BUCKET
sed -E -i '' "s#$TMP_FLIR_ADAS_DIR#$FLIR_ADAS_BUCKET#" $FLIR_ADAS_PEOPLE_CSV
gsutil cp $FLIR_ADAS_PEOPLE_CSV $FLIR_ADAS_BUCKET
```

#### 4. Set up a callback server using [Node.js and MongoDB on Heroku](https://github.com/scaleapi/sample-callback-server-node).

#### 5. Create the [Scale](https://scale.com) annotation tasks:
```bash
SCALE_API_KEY=""  # Insert "Live API Key" from Scale dashboard.
SCALE_PROJECT=""  # Insert project name from Scale dashboard.
CALLBACK_URL=""  # Insert callback server URL from step 4.
INSTRUCTION="Draw a box around each face. The top should be above the forehead. The bottom should be below the chin. The left and right should span the width of the face, ignoring ears."

for f in $(cat $FLIR_ADAS_PEOPLE_CSV)
do
  path=$(printf '%s\n' "${f//$FLIR_ADAS_BUCKET\//}")
  url="https://storage.googleapis.com/$FLIR_ADAS_DIR/$path"
  curl "https://api.scale.com/v1/task/annotation" \
    -u "$SCALE_API_KEY:" \
    -d callback_url="$CALLBACK_URL" \
    -d instruction="$INSTRUCTION" \
    -d attachment_type=image \
    -d attachment="$url" \
    -d objects_to_annotate[0]="face" \
    -d with_labels=false \
    -d project="$SCALE_PROJECT"
done
```

#### 6. Check the [Scale Dashboard](https://dashboard.scale.com) for all annotation tasks to be completed.

#### 7. Export the annotations as a CSV file:
```bash
MONGO_HOSTNAME=""  # Insert database host from Heroku/mLab dashboard.
MONGO_DATABASE=""  # Insert database name from Heroku/mLab dashboard.
MONGO_USERNAME=""  # Insert username from Heroku/mLab dashboard.
MONGO_PASSWORD=""  # Insert password from Heroku/mLab dashboard.
MONGO_COLLECTION="tasks"
BBOXES_CSV="bounding-boxes.csv"

python mongo_export.py \
  --hostname=$MONGO_HOSTNAME \
  --database=$MONGO_DATABASE \
  --collection=$MONGO_COLLECTION \
  --username=$MONGO_USERNAME \
  --password=$MONGO_PASSWORD \
  --output_csv=$BBOXES_CSV
```

#### 8. Clean up
```bash
rm FLIR_ADAS_1_3.tar.*
rm -rf $FLIR_ADAS_DIR
rm -rf $TMP_FLIR_ADAS_DIR
rm *-people.csv
gsutil rm -r $FLIR_ADAS_BUCKET
```
