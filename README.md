# Extract Text and Images from PDF to Amazon S3 and CSV

This Python script extracts text and images from a PDF file, uploads the images to an Amazon S3 bucket, and generates a CSV file that can be used in a spreadsheet. The script utilizes the `PyMuPDF` library for PDF manipulation and `boto3` for interacting with Amazon S3.

## Key Features

- **Extract images from the PDF and upload them to the specified S3 bucket.**
- **Extract text and bounding box information from the PDF.**
- **Process the extracted data and match images with their corresponding text.**
- **Generate a CSV file (items.csv) with the processed data.**

## Prerequisites

Before running the script, make sure you have the following:

- Python 3.x installed
- Required Python packages installed (`pymupdf`, `boto3`)
- AWS credentials (`aws_access_key_id` and `aws_secret_access_key`)
- A configured S3 bucket

## Installation

1. Clone the repository or download the script to your local machine.
2. Install the required Python packages by running:
    ```sh
    pip install -r requirements.txt
    ```

3. Create a `secrets.py` file in the same directory as the script and add the following variables:
    ```python
    bucket = 'your-s3-bucket-name'
    __aws_access_key_id = 'your-aws-access-key-id'
    __aws_secret_access_key = 'your-aws-secret-access-key'
    ```

## Script Overview

### Main Functions

- `extract_and_save_images(pdf_path)`: Extracts images from the PDF, saves them locally, and uploads them to an S3 bucket. It returns a list of image metadata.
- `upload_to_s3(content, bucket_name, s3_client, object_name, is_image=True)`: Uploads a given content (image or text) to an S3 bucket.
- `image_position(page_no, x1, y1)`: Checks if an image exists at a specific position in the PDF.
- `get_image_at_position(image_info, target_page, target_x, target_y)`: Retrieves image metadata at a specific position.
- `main(image_filename, image_bytes)`: Handles the image upload process and returns the S3 URL of the uploaded image.
- `extract_text_from_pdf(pdf_path)`: Extracts text and bounding box information from the PDF.
- `process_pymupdf_data(data)`: Processes the extracted PDF data and returns a list of cleaned items.
- `bbox_to_image_dict(image_data)`: Creates a dictionary mapping bounding box positions to image filenames.
- `update_items_with_images(items, image_dict)`: Updates items with the corresponding image filenames based on bounding box positions.
- `makeCsv(json_array)`: Generates a CSV file from the processed data.

### Usage

1. Place the PDF file you want to process in the same directory as the script and name it `s3.pdf`.
2. Run the script:
    ```sh
    python script_name.py
    ```

### Output

The script will produce the following outputs:
- Images uploaded to the S3 bucket with their URLs stored in `image_url`.
- A CSV file (`items.csv`) containing the extracted and processed data.

### Example CSV Format

The CSV file will contain the following columns:
- `name`: The name of the product.
- `size`: The size of the product.
- `price`: The price of the product.
- `item_id`: The item ID of the product.
- `image`: The S3 URL of the product image.

## Additional Notes

- Ensure the S3 bucket permissions are set correctly to allow uploads.
- The script assumes a specific format for text and image extraction. Adjustments may be necessary for different PDF layouts.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknowledgments

- [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/) for PDF manipulation.
- [Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for AWS S3 integration.

## requirements.txt

```plaintext
boto3~=1.34.145
fitz~=0.0.1.dev2
```

Including the `requirements.txt` ensures that you can install all necessary dependencies in one step. Make sure to adjust the paths and bucket names as needed for your environment.


## Sample Video

[Visit the sample Output video](https://drive.google.com/file/d/1Q5D0-hZxJMmcp-2x_Jb9U4taIjibsPuZ/view?usp=sharing)

