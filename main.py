import csv
import io
import re
import tempfile
from datetime import datetime
import boto3
import fitz
import os

from secrets import bucket, __aws_access_key_id, __aws_secret_access_key
from flask import Flask, request, jsonify, Response

app = Flask(__name__)


def extract_and_save_images(pdf_path, output_dir):
    doc = fitz.open(pdf_path)
    image_info = []

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for page_num, page in enumerate(doc):
        image_list = page.get_images(full=True)

        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)

            if base_image:
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image_rect = page.get_image_bbox(img)

                # Determine the column based on the x-coordinate
                page_width = page.rect.width
                if image_rect.x0 < page_width / 2:
                    column = "Left"
                else:
                    column = "Right"

                # Save the image
                image_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                final_file_name = main(image_filename, image_bytes)

                image_info.append({
                    "page": page_num + 1,
                    "index": img_index + 1,
                    "filename": final_file_name,
                    "position": {
                        "x0": round(image_rect.x0, 2),
                        "y0": round(image_rect.y0, 2),
                        "x1": round(image_rect.x1, 2),
                        "y1": round(image_rect.y1, 2),
                    },
                    "column": column
                })

    doc.close()
    return image_info


def upload_to_s3(content, bucket_name, s3_client, object_name, is_image=True):
    try:
        content_type = 'image/png' if is_image else 'text/plain'
        s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=content, ContentType=content_type)
        print(f"Uploaded {object_name} to {bucket_name}")
    except Exception as e:
        print(f"Failed to upload {object_name}: {e}")


def image_position(page_no, x1, y1, image_results):
    specific_image = get_image_at_position(image_results, page_no, x1, y1)
    if specific_image:
        print(f"Image found: {specific_image['filename']}")
        return True
    else:
        print("No image found at the specified position.")
        return False


def get_image_at_position(image_info, target_page, target_x, target_y):
    for img in image_info:
        if img["page"] == target_page:
            pos = img["position"]
            if pos["x0"] <= target_x <= pos["x1"] and pos["y0"] <= target_y <= pos["y1"]:
                return img
    return None


def main(image_filename, image_bytes, ):
    global image_url
    s3_client = boto3.client(
        's3',
        aws_access_key_id=__aws_access_key_id,
        aws_secret_access_key=__aws_secret_access_key
    )

    date_str = datetime.now().strftime("%Y-%m-%d")

    folder_name = f"{date_str}/"

    object_name = f'{folder_name}{image_filename}'
    final_image_url = 'https://upload-file-pdf.s3.ap-south-1.amazonaws.com/' + object_name
    image_url.append(final_image_url)
    upload_to_s3(image_bytes, bucket, s3_client, object_name)
    return final_image_url


def extract_text_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    num_pages = document.page_count

    all_pages_bboxlog = []
    for page_num in range(num_pages):
        page = document.load_page(page_num)
        # Extract text with its font information
        text_bbox = page.get_bboxlog()
        filtered_bbox_log = [entry for entry in text_bbox if entry[0] in ['fill-image', 'fill-text']]
        print(filtered_bbox_log)
        all_pages_bboxlog.append(filtered_bbox_log)

    return all_pages_bboxlog


def process_pymupdf_data(data, pdf_path):
    document = fitz.open(pdf_path)
    items = []
    for index, item_list in enumerate(data):
        page = document.load_page(index)

        for index, item in item_list:
            if index == "fill-text":
                text = page.get_textbox(item)
                items.append(text)
            elif index == "fill-image":
                items.append({'image': round_tuple_values(item)})

    __items = clean_list(items)
    products = parse_items(__items)

    filtered_data = [item for item in products if item.get('item_id')]
    print(filtered_data)
    return filtered_data


def round_tuple_values(t, decimal_places=2):
    return tuple(round(v, decimal_places) for v in t)


def clean_list(items):
    # Initialize an empty list to store cleaned items
    cleaned_items = []

    # Iterate through the input list
    for item in items:
        # Append item to cleaned list if it's not an empty string
        if item != '':
            cleaned_items.append(item)

    return cleaned_items


def parse_items(items):
    products = []
    i = 0

    currency_pattern = re.compile(r'^\$|₹|£')

    while i < len(items):
        if isinstance(items[i], str):
            product = {
                "name": items[i],
                "size": [],
                "price": [],
                "item_id": [],
                "image": None
            }
            i += 1  # Move to next item

            # Check if the next item is an image dictionary
            if i < len(items) and isinstance(items[i], dict) and 'image' in items[i]:
                product["image"] = items[i]['image']
                i += 1

            while i < len(items):
                if isinstance(items[i], str) and ':' in items[i]:
                    # Process size, price, and item_id
                    size = items[i].strip(": ")
                    price = items[i + 1].strip()
                    item_id = int(items[i + 2].strip())
                    product["size"].append(size)
                    product["price"].append(price)
                    product["item_id"].append(item_id)
                    i += 3
                elif isinstance(items[i], str) and currency_pattern.match(items[i]):
                    # Process item without size
                    product["price"].append(items[i].strip())
                    i += 1
                elif isinstance(items[i], str) and items[i].isdigit():
                    # Process item_id for item without size
                    product["item_id"].append(items[i].strip())
                    i += 1
                elif isinstance(items[i], dict) and 'image' in items[i]:
                    # Process image for item without size
                    product["image"] = items[i]['image']
                    i += 1
                else:
                    break

            products.append(product)
        else:
            i += 1

    return products


def bbox_to_image_dict(image_data):
    """Create a dictionary from bbox positions to filenames."""
    image_dict = {}
    for item in image_data:
        pos = (round(item['position']['x0'], 2), round(item['position']['y0'], 2), round(item['position']['x1'], 2),
               round(item['position']['y1'], 2))
        image_dict[pos] = item['filename']
    return image_dict


def update_items_with_images(items, image_dict):
    print(image_dict)
    """Update items' image field based on bbox and image_dict."""
    for item in items:
        bbox = ''
        if item['image']:
            bbox = item['image']
            print(bbox)
            images_closest = check_bbox(bbox, image_dict)
            print(images_closest)
            item['image'] = images_closest
    return items


def check_bbox(bbox_to_check, image_dict):
    for bbox, url in image_dict.items():
        # Check if bbox_to_check exactly matches a bbox in image_dict
        if bbox_to_check == bbox:
            print("Exact match found")
            return url
        # Check if bbox_to_check is within the bbox in image_dict
        if (bbox_to_check[0] >= bbox[0] and
                bbox_to_check[1] >= bbox[1] and
                bbox_to_check[2] <= bbox[2] and
                bbox_to_check[3] <= bbox[3]):
            print("Bounding box is within:")
            return url
    return []


def makeCsv(json_array, csv_path):
    result = []
    print(json_array)
    for index, item in enumerate(json_array):
        name = item['name']
        price = item['price'][0] if item['price'] else None
        sizes = item['size']
        item_ids = item['item_id']
        image = item['image']

        if sizes and item_ids:
            for size, item_id in zip(sizes, item_ids):
                result.append({"name": name, "size": size, "price": price, "item_id": item_id, "image": image})
        else:
            size = sizes[0] if sizes else ""
            item_id = item_ids[0] if item_ids else ""
            result.append({"name": name, "size": size, "price": price, "item_id": item_id, "image": image})

    filtered_result = [item for item in result if not (item['item_id'] == "" and item['price'] is None)]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "size", "price", "item_id", "image"])
    writer.writeheader()
    for item in filtered_result:
        writer.writerow(item)

    return output.getvalue()


image_url = []


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file:
            # Save uploaded file to a temporary directory
            temp_dir = tempfile.mkdtemp()
            temp_pdf_path = os.path.join(temp_dir, file.filename)
            file.save(temp_pdf_path)

            # Process PDF file
            image_results = extract_and_save_images(temp_pdf_path, app.config['OUTPUT_DIR'])
            text_results = extract_text_from_pdf(temp_pdf_path)
            items = process_pymupdf_data(text_results, temp_pdf_path)
            image_dict = bbox_to_image_dict(image_results)
            updated_items = update_items_with_images(items, image_dict)
            csv_path = os.path.join(app.config['OUTPUT_DIR'], 'output.csv')
            csv_output = makeCsv(updated_items, csv_path)

            # Return JSON response
            return Response(
                csv_output,
                mimetype="text/csv",
                headers={"Content-disposition": "attachment; filename=output.csv"}
            )
    except Exception as e:
        return f'Exception occurred {e}'

    return jsonify({'error': 'Unexpected error occurred'}), 500


if __name__ == '__main__':
    app.config['OUTPUT_DIR'] = '/Users/safwanoffice/PycharmProjects/items-pdf/output'
    app.run()
