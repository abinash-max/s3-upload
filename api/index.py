import os
from flask import Flask, request, render_template, jsonify
import boto3
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, template_folder='../templates')

# --- Configuration ---
S3_BUCKET = os.getenv('S3_BUCKET_NAME')
S3_REGION = os.getenv('S3_REGION')
# NOTE: The folder name in your logs was 'SKUs/', I have updated it here.
# Change it if you prefer 'products/'.
S3_FOLDER = 'SKUs/'

# Initialize the S3 client
s3_client = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """Handles the image upload and conversion."""
    if 'image' not in request.files or 'sku' not in request.form:
        return jsonify({'error': 'Missing image or SKU name'}), 400

    image_file = request.files['image']
    sku = request.form['sku']

    if image_file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    try:
        # 1. Convert image to WebP in memory
        with Image.open(image_file.stream) as img:
            # Create an in-memory byte stream
            webp_buffer = io.BytesIO()
            img.save(webp_buffer, 'webp')
            webp_buffer.seek(0) # Rewind the buffer to the beginning

        # 2. Upload to S3
        s3_object_key = f"{S3_FOLDER}{sku}.webp"
        
        print(f"Uploading to s3://{S3_BUCKET}/{s3_object_key}...")

        # --- FIX APPLIED HERE ---
        # Removed 'ACL': 'public-read' from ExtraArgs because the bucket
        # does not allow ACLs and relies on a bucket policy for public access.
        s3_client.upload_fileobj(
            webp_buffer,
            S3_BUCKET,
            s3_object_key,
            ExtraArgs={'ContentType': 'image/webp'}
        )

        # 3. Generate the public S3 URL
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_object_key}"

        return jsonify({'s3_link': s3_url})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)