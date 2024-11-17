import base64
from typing import Literal
from pydantic import BaseModel
from pdf2image import convert_from_path
import os
from openai import OpenAI
from PIL import Image
from mimetypes import guess_type


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


class DocumentAnalysis(BaseModel):
    document_type: Literal[
        "drivers_licence", "bank_statement", "invoice", "unknown file"
    ]
    notes: str


def convert_pdf_to_jpeg(pdf_path, output_folder="output_images", dpi=200):
    """Convert a PDF to a single stitched JPEG image."""
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
    os.makedirs(output_folder, exist_ok=True)

    # Convert PDF to images
    images = convert_from_path(
        pdf_path, dpi=dpi, fmt="jpeg", output_folder=output_folder
    )

    # Stitch images together
    widths, heights = zip(*(img.size for img in images))
    total_width = max(widths)
    total_height = sum(heights)

    # Create a blank image for the stitched result
    stitched_image = Image.new("RGB", (total_width, total_height))

    # Paste each image below the previous one
    y_offset = 0
    for img in images:
        stitched_image.paste(img, (0, y_offset))
        y_offset += img.height

    # Remove intermediate images
    for img in images:
        os.remove(img.filename)

    # Save the final image
    output_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".jpg"
    output_path = os.path.join(output_folder, output_name)
    stitched_image.save(output_path, "JPEG")
    return output_path


def encode_image(image_path):
    """Encode an image to Base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def process_document_file(file_path, output_folder="output_images"):
    """Process a document file and return the path to a valid image (JPEG/PNG/WEBP/GIF)."""
    mime_type, _ = guess_type(file_path)

    # Handle supported image types
    if mime_type in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
        return file_path, mime_type  # File is already a supported image format

    # Handle PDFs by converting them to JPEG
    elif mime_type == "application/pdf":
        return convert_pdf_to_jpeg(file_path, output_folder=output_folder), "image/jpeg"

    # Raise an error for unsupported types
    else:
        raise ValueError(
            "Unsupported file type. Supported types: PDF, JPEG, PNG, WEBP, GIF."
        )


def query_gpt4(file_path, model="gpt-4o-mini"):
    """Convert PDF to images, encode the first image, and send it to the GPT model."""
    image_path, mime_type = process_document_file(file_path)
    base64_image = encode_image(image_path)

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert at classifying documents and understanding their contents"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this image and provide the document_type and notes on the content",
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


def classify_file(file_path, model="gpt-4o-mini"):
    completion = query_gpt4(file_path, model)
    document_analysis = completion.choices[0].message.parsed
    return document_analysis


# TODO:
# scalability/cost analysis
# how quickly could we set up similar with off the shelf functionality?

if __name__ == "__main__":
    a_file_path = "files/bank_statement_3.pdf"
    result = classify_file(a_file_path)
    print(result)
