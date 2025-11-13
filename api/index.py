import os
from flask import Flask, request, render_template, jsonify
import boto3
from PIL import Image
import io
from datetime import datetime # Required for generating timestamps

# Vercel loads environment variables automatically from the project settings.
from dotenv import load_dotenv
load_dotenv()


# Tell Flask the templates folder is one directory up from the current file
app = Flask(__name__, template_folder='../templates')


# --- Configuration ---
# These variables are read from the Environment Variables set in your Vercel project settings.
S3_BUCKET = os.getenv('S3_BUCKET_NAME')
S3_REGION = os.getenv('S3_REGION')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')


# Check if environment variables are loaded correctly upon application start.
if not all([S3_BUCKET, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
    raise RuntimeError("One or more required environment variables are not set.")


# Initialize the S3 client
s3_client = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    """Renders the main HTML page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """
    Handles the image upload. The SKU becomes the folder name and the
    image is saved with a timestamp filename.
    """
    if 'image' not in request.files or 'sku' not in request.form:
        return jsonify({'error': 'Missing image or SKU name'}), 400

    image_file = request.files['image']
    sku_folder_name = request.form['sku'] # The SKU is now the folder name

    if image_file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    if not sku_folder_name.strip():
        return jsonify({'error': 'SKU name cannot be empty'}), 400

    try:
        # 1. Convert image to WebP in memory
        with Image.open(image_file.stream) as img:
            webp_buffer = io.BytesIO()
            img.save(webp_buffer, 'webp')
            webp_buffer.seek(0) # Rewind buffer to the beginning for reading

        # 2. Generate a unique filename using a timestamp (e.g., "20251113173055.webp")
        timestamp_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}.webp"
        
        # 3. Construct the full S3 object path (key)
        #    Format: <SKU_NAME_FOLDER>/<TIMESTAMP_FILENAME>.webp
        s3_object_key = f"{sku_folder_name}/{timestamp_filename}"
        
        print(f"Uploading to s3://{S3_BUCKET}/{s3_object_key}...")

        # 4. Upload the object to S3
        s3_client.upload_fileobj(
            webp_buffer,
            S3_BUCKET,
            s3_object_key,
            ExtraArgs={'ContentType': 'image/webp'}
        )

        # 5. Generate the public S3 URL for the newly uploaded file
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_object_key}"

        return jsonify({'s3_link': s3_url})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'error': str(e)}), 500


# For local development only (not used by Vercel)
if __name__ == '__main__':
    app.run(debug=True)