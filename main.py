import csv
import re
from datetime import datetime
import boto3
import fitz
import os
import json


def extract_and_save_images(pdf_path):
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


def image_position(page_no, x1, y1):
    global image_results
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
    global __aws_access_key_id
    global __aws_secret_access_key
    global bucket
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
    page = document.load_page(0)

    # Extract text with its font information
    text_bbox = page.get_bboxlog()
    # print(text_bbox)
    filtered_bbox_log = [entry for entry in text_bbox if entry[0] in ['fill-image', 'fill-text']]
    print(filtered_bbox_log)

    return filtered_bbox_log


def process_pymupdf_data(data):
    document = fitz.open(__pdf_path)
    page = document.load_page(0)
    items = []
    for index, item in data:
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

def makeCsv(json_array):
    result = []
    print(json_array)
    for index, item in enumerate(json_array):
        name = item['name']
        price = item['price'][0] if item['price'] else None
        sizes = item['size']
        item_ids = item['item_id']
        image = item['image']
        # image = images[index]

        if sizes and item_ids:
            for size, item_id in zip(sizes, item_ids):
                result.append({"name": name, "size": size, "price": price, "item_id": item_id, "image": image})
        else:
            size = sizes[0] if sizes else ""
            item_id = item_ids[0] if item_ids else ""
            result.append({"name": name, "size": size, "price": price, "item_id": item_id, "image": image})

    filtered_result = [item for item in result if not (item['item_id'] == "" and item['price'] is None)]

    with open('items.csv', mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=["name", "size", "price", "item_id", "image"])
        writer.writeheader()
        for item in filtered_result:
            writer.writerow(item)


image_url = []
__pdf_path = "s3.pdf"
bucket = 'upload-file-pdf'
__aws_access_key_id = 'AKIAZI2LE63SKS2TUFGI'
__aws_secret_access_key = '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'
output_dir = "/Users/safwanoffice/PycharmProjects/items-pdf/output"
# image_results = extract_and_save_images(__pdf_path)
# print(json.dumps(image_results, indent=2))

image_results = [
  {
    "page": 1,
    "index": 1,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img1.png",
    "position": {
      "x0": 46.0,
      "y0": 109.64,
      "x1": 126.0,
      "y1": 162.92
    },
    "column": "Left"
  },
  {
    "page": 1,
    "index": 2,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img2.png",
    "position": {
      "x0": 316.0,
      "y0": 109.64,
      "x1": 396.0,
      "y1": 162.92
    },
    "column": "Right"
  },
  {
    "page": 1,
    "index": 3,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img3.png",
    "position": {
      "x0": 46.0,
      "y0": 216.07,
      "x1": 111.28,
      "y1": 296.07
    },
    "column": "Left"
  },
  {
    "page": 1,
    "index": 4,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img4.png",
    "position": {
      "x0": 316.0,
      "y0": 229.43,
      "x1": 396.0,
      "y1": 282.71
    },
    "column": "Right"
  },
  {
    "page": 1,
    "index": 5,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img5.png",
    "position": {
      "x0": 46.0,
      "y0": 349.21,
      "x1": 126.0,
      "y1": 402.49
    },
    "column": "Left"
  },
  {
    "page": 1,
    "index": 6,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img6.png",
    "position": {
      "x0": 316.0,
      "y0": 357.53,
      "x1": 396.0,
      "y1": 394.17
    },
    "column": "Right"
  },
  {
    "page": 1,
    "index": 7,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img7.png",
    "position": {
      "x0": 46.0,
      "y0": 475.07,
      "x1": 126.0,
      "y1": 516.19
    },
    "column": "Left"
  },
  {
    "page": 1,
    "index": 8,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img8.png",
    "position": {
      "x0": 316.0,
      "y0": 474.59,
      "x1": 396.0,
      "y1": 516.67
    },
    "column": "Right"
  },
  {
    "page": 1,
    "index": 9,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img9.png",
    "position": {
      "x0": 46.0,
      "y0": 589.33,
      "x1": 126.0,
      "y1": 641.49
    },
    "column": "Left"
  },
  {
    "page": 1,
    "index": 10,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page1_img10.png",
    "position": {
      "x0": 316.0,
      "y0": 575.41,
      "x1": 383.77,
      "y1": 655.41
    },
    "column": "Right"
  },
  {
    "page": 2,
    "index": 1,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page2_img1.png",
    "position": {
      "x0": 46.0,
      "y0": 108.04,
      "x1": 126.0,
      "y1": 164.52
    },
    "column": "Left"
  },
  {
    "page": 2,
    "index": 2,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page2_img2.png",
    "position": {
      "x0": 316.0,
      "y0": 96.28,
      "x1": 368.48,
      "y1": 176.28
    },
    "column": "Right"
  },
  {
    "page": 2,
    "index": 3,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page2_img3.png",
    "position": {
      "x0": 46.0,
      "y0": 237.03,
      "x1": 126.0,
      "y1": 275.11
    },
    "column": "Left"
  },
  {
    "page": 2,
    "index": 4,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page2_img4.png",
    "position": {
      "x0": 316.0,
      "y0": 232.39,
      "x1": 396.0,
      "y1": 279.75
    },
    "column": "Right"
  },
  {
    "page": 2,
    "index": 5,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page2_img5.png",
    "position": {
      "x0": 46.0,
      "y0": 335.85,
      "x1": 99.28,
      "y1": 415.85
    },
    "column": "Left"
  },
  {
    "page": 2,
    "index": 6,
    "filename": "https://upload-file-pdf.s3.ap-south-1.amazonaws.com/2024-07-24/page2_img6.png",
    "position": {
      "x0": 316.0,
      "y0": 343.77,
      "x1": 396.0,
      "y1": 407.93
    },
    "column": "Right"
  }
]
image_position(1, x1=315, y1=316)
reusult_bbox = extract_text_from_pdf(pdf_path=__pdf_path)
# items = process_pymupdf_data(reusult_bbox)

items = [{'name': 'JJ - Photo Dateback Tee', 'size': ['S', 'M', 'L', 'XL', '2XL', '3XL'],
          'price': ['$45', '$45', '$45', '$45', '$45', '$45'],
          'item_id': [939530103, 939530104, 939530105, 939530106, 939530107, 939530108],
          'image': []},
         {'name': 'JJ - Vintage Black White Photo Tee', 'size': ['S', 'M', 'L', 'XL', '2XL'],
          'price': ['$45', '$45', '$45', '$45', '$45'],
          'item_id': [939530113, 939530114, 939530115, 939530116, 939530117], 'image': (316.0, 109.64, 396.0, 162.92)},
         {'name': 'JJ - Y2K Pepper Tee', 'size': ['S', 'M', 'L', 'XL', '2XL'],
          'price': ['$45', '$45', '$45', '$45', '$45'],
          'item_id': [939530123, 939530124, 939530125, 939530126, 939530127], 'image': (46.0, 216.07, 111.28, 296.07)},
         {'name': 'JJ - Photo Shoulder Dateback Tee', 'size': ['S', 'M', 'L', 'XL', '2XL', '3XL'],
          'price': ['$45', '$45', '$45', '$45', '$45', '$45'],
          'item_id': [939530133, 939530134, 939530135, 939530136, 939530137, 939530138],
          'image': (316.0, 229.43, 396.0, 282.71)},
         {'name': 'JJ - Nasty Tee', 'size': ['S', 'M', 'L', 'XL', '2XL'], 'price': ['$45', '$45', '$45', '$45', '$45'],
          'item_id': [939530143, 939530144, 939530145, 939530146, 939530147], 'image': (46.0, 349.21, 126.0, 402.49)},
         {'name': 'JJ - Rhythm Nation Longsleeve', 'size': ['S', 'M', 'L', 'XL', '2XL'],
          'price': ['$55', '$55', '$55', '$55', '$55'],
          'item_id': [939530153, 939530154, 939530155, 939530156, 939530157], 'image': (316.0, 357.53, 396.0, 394.17)},
         {'name': 'JJ - I Love Janet Longsleeve', 'size': ['S', 'M', 'L', 'XL', '2XL'],
          'price': ['$55', '$55', '$55', '$55', '$55'],
          'item_id': [939530163, 939530164, 939530165, 939530166, 939530167], 'image': (46.0, 475.07, 126.0, 516.19)},
         {'name': 'JJ - Photo Hood', 'size': ['S', 'M', 'L', 'XL', '2XL'], 'price': ['$80', '$80', '$80', '$80', '$80'],
          'item_id': [939530173, 939530174, 939530175, 939530176, 939530177], 'image': (316.0, 474.59, 396.0, 516.67)},
         {'name': 'JANET- TOUR BOOK 2023', 'size': [], 'price': ['$40'], 'item_id': ['939530021'],
          'image': (46.0, 0.34, 1.0, 641.49)},
         {'name': 'JANET- TOUR BOOK 2024', 'size': [], 'price': ['$0'], 'item_id': ['939530109'],
          'image': (316.0, 575.41, 383.77, 655.41)}]

# print(json.dumps(image_results, indent=2))

image_dict = bbox_to_image_dict(image_results)

# Update items with image filenames
updated_items = update_items_with_images(items, image_dict)
makeCsv(updated_items)



# Output the result
print(json.dumps(updated_items, indent=2))
