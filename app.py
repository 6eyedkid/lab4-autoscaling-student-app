from flask import Flask, render_template, request, redirect, url_for, flash
import boto3, os, uuid
from datetime import datetime, timezone
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET') or os.urandom(32)
REGION = os.environ.get('AWS_REGION', 'us-east-1')
TABLE_NAME = os.environ.get('TABLE_NAME', '').strip()
BUCKET_NAME = (os.environ.get('BUCKET_NAME') or os.environ.get('S3_BUCKET', '')).strip()
VERSION = os.environ.get('APP_VERSION', '1.0')
if not TABLE_NAME or not BUCKET_NAME:
    raise RuntimeError('Set TABLE_NAME and BUCKET_NAME (or S3_BUCKET) in the container environment.')
ddb = boto3.resource('dynamodb', region_name=REGION)
table = ddb.Table(TABLE_NAME)
s3 = boto3.client('s3', region_name=REGION)
ALLOWED = {'png','jpg','jpeg','webp','svg'}

def image_url(key):
    if not key:
        return ''
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': key}, ExpiresIn=3600)

@app.get('/')
def index():
    rows = table.scan().get('Items', [])
    rows.sort(key=lambda x: (x.get('name','').lower(), x.get('id','')))
    for row in rows:
        row['image_url'] = image_url(row.get('file_key'))
    return render_template('index.html', rows=rows, version=VERSION)

@app.route('/add', methods=['GET','POST'])
def add():
    if request.method == 'GET':
        return render_template('add.html', version=VERSION)
    name = request.form.get('name','').strip()
    group = request.form.get('group','').strip()
    description = request.form.get('description','').strip()
    if not name or not group:
        flash('Укажите ФИО студента и группу.', 'error')
        return redirect(url_for('add'))
    upload = request.files.get('file')
    file_key = ''
    file_name = ''
    if upload and upload.filename:
        original = secure_filename(upload.filename)
        ext = original.rsplit('.',1)[-1].lower() if '.' in original else ''
        if ext not in ALLOWED:
            flash('Допустимы изображения PNG, JPG, WEBP и SVG.', 'error')
            return redirect(url_for('add'))
        file_name = original
        file_key = f"students/{uuid.uuid4().hex}_{original}"
        s3.upload_fileobj(upload, BUCKET_NAME, file_key, ExtraArgs={'ContentType': upload.mimetype or 'application/octet-stream'})
    item = {'id': uuid.uuid4().hex, 'name': name, 'group': group, 'description': description,
            'file_key': file_key, 'file_name': file_name,
            'created_at': datetime.now(timezone.utc).isoformat()}
    table.put_item(Item=item)
    flash('Запись студента добавлена.', 'success')
    return redirect(url_for('index'))

@app.get('/health')
def health():
    return {'status':'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
