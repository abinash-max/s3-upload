import os
from flask import Flask, request, render_template, jsonify
import boto3
from PIL import Image
import io

# Vercel loads environment variables automatically from the project settings.
# The `dotenv` library is not needed for deployment, but can be kept for local testing.
from dotenv import load_dotenv
load_dotenv()


# --- Vercel Deployment Fix ---
# When Vercel builds the project, this 'index.py' file is in the '/api' directory.
# We must tell Flask that the 'templates' folder is one level up ('../').
app = Flask(__name__, template_folder='../templates')


# --- Configuration ---
# These variables are read from the Environment Variables set in your Vercel project settings.
S3_BUCKET = os.getenv('S3_BUCKET_NAME')
S3_REGION = os.getenv('S3_REGION')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
S3_FOLDER = 'SKUs/' # The folder within your S3 bucket.


# --- Error Handling ---
# Check if environment variables are loaded correctly upon application start.
if not all([S3_BUCKET, S3_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]):
    # This error will be visible in the Vercel deployment logs if variables are missing.
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
    """
    Renders the main HTML page. This route catches all requests and serves the UI.
    """
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    """
    Handles the image upload, conversion to WebP, and upload to S3.
    This is the API endpoint called by the frontend JavaScript.
    """
    if 'image' not in request.files or 'sku' not in request.form:
        return jsonify({'error': 'Missing image or SKU name'}), 400

    image_file = request.files['image']
    sku = request.form['sku']

    if image_file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    try:
        # 1. Convert image to WebP in memory to avoid saving a temporary file
        with Image.open(image_file.stream) as img:
            webp_buffer = io.BytesIO()
            img.save(webp_buffer, 'webp')
            webp_buffer.seek(0) # Rewind the buffer to the beginning for reading

        # 2. Define the object key and upload to S3
        s3_object_key = f"{S3_FOLDER}{sku}.webp"
        
        print(f"Uploading to s3://{S3_BUCKET}/{s3_object_key}...")

        # --- S3 ACL Error Fix ---
        # Removed 'ACL': 'public-read' from ExtraArgs. Access is now controlled
        # by the S3 Bucket Policy, as required by modern S3 settings.
        s3_client.upload_fileobj(
            webp_buffer,
            S3_BUCKET,
            s3_object_key,
            ExtraArgs={'ContentType': 'image/webp'}
        )

        # 3. Generate the public S3 URL for the newly uploaded object
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_object_key}"

        return jsonify({'s3_link': s3_url})

    except Exception as e:
        # This will log the specific error to the Vercel deployment logs for debugging.
        print(f"An error occurred: {e}")
        return jsonify({'error': str(e)}), 500

# The following is for local development and is not used by Vercel
if __name__ == '__main__':
    app.run(debug=True)