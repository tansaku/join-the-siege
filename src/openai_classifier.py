import base64
from typing import Literal
from pydantic import BaseModel
from pdf2image import convert_from_bytes
import os
from io import BytesIO
from werkzeug.datastructures import FileStorage
from openai import OpenAI
from PIL import Image
from mimetypes import guess_type


# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


class DocumentAnalysis(BaseModel):
    document_type: Literal[
        "drivers_licence", "bank_statement", "invoice", "unknown file"
    ]
    notes: str


def convert_pdf_to_jpeg(file_bytes, file_name, output_folder="output_images", dpi=200):
    """
    Convert a PDF (in bytes) to a single stitched JPEG image.
    """
    os.makedirs(output_folder, exist_ok=True)

    # Convert PDF bytes to images
    images = convert_from_bytes(file_bytes, dpi=dpi, fmt="jpeg")

    # Stitch images together
    widths, heights = zip(*(img.size for img in images))
    total_width = max(widths)
    total_height = sum(heights)

    stitched_image = Image.new("RGB", (total_width, total_height))

    # Paste each image below the previous one
    y_offset = 0
    for img in images:
        stitched_image.paste(img, (0, y_offset))
        y_offset += img.height

    # Save the final stitched image
    output_name = file_name.replace(".pdf", ".jpg")
    output_path = os.path.join(output_folder, output_name)
    stitched_image.save(output_path, "JPEG")

    return output_path


def encode_image(image_path):
    """
    Encode an image to Base64.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def process_document_file(file_storage, output_folder="output_images"):
    """
    Process a document file from FileStorage and return the path to a valid image (JPEG/PNG/WEBP/GIF).
    """
    # Read the file bytes
    file_bytes = file_storage.read()
    file_name = file_storage.filename

    mime_type, _ = guess_type(file_name)

    # Handle supported image types
    if mime_type in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
        os.makedirs(output_folder, exist_ok=True)
        output_path = os.path.join(output_folder, file_name)
        with open(output_path, "wb") as f:
            f.write(file_bytes)
        return output_path, mime_type

    # Handle PDFs by converting them to JPEG
    elif mime_type == "application/pdf":
        return (
            convert_pdf_to_jpeg(file_bytes, file_name, output_folder=output_folder),
            "image/jpeg",
        )

    # Raise an error for unsupported types
    else:
        raise ValueError(
            "Unsupported file type. Supported types: PDF, JPEG, PNG, WEBP, GIF."
        )


def query_gpt4(file_storage, model="gpt-4o-mini"):
    """
    Analyze a document file using GPT-4 and classify it.
    """
    image_path, mime_type = process_document_file(file_storage)
    base64_image = encode_image(image_path)

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert at classifying documents and understanding their contents."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this image and provide the document_type and notes on the content.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                    },
                ],
            },
        ],
        response_format=DocumentAnalysis,  # Structured response
    )

    return completion


def classify_file(file_storage, model="gpt-4o-mini"):
    """
    Classify a document file uploaded via FileStorage.
    """
    completion = query_gpt4(file_storage, model)
    document_analysis = completion.choices[0].message.parsed
    return document_analysis.document_type


def create_filestorage_from_path(file_path):
    """
    Create a FileStorage object from a local file path.

    Args:
        file_path (str): Path to the local file.

    Returns:
        FileStorage: FileStorage object wrapping the file.
    """
    with open(file_path, "rb") as f:
        file_data = BytesIO(f.read())
        return FileStorage(
            stream=file_data,
            filename=os.path.basename(file_path),
            content_type=None,  # Content type can be detected dynamically if needed
        )


if __name__ == "__main__":
    a_file_path = "files/bank_statement_3.pdf"
    result = classify_file(create_filestorage_from_path(a_file_path))
    print(result)
