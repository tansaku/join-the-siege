import base64
from typing import Literal
from pydantic import BaseModel
from pdf2image import convert_from_path
import os
from openai import OpenAI
from PIL import Image


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


def send_pdf_to_gpt4(pdf_path, model="gpt-4o-mini"):
    """Convert PDF to images, encode the first image, and send it to the GPT model."""
    image_path = convert_pdf_to_jpeg(pdf_path)
    if not image_path:
        raise ValueError("No images were generated from the PDF.")

    # encode the first image
    base64_image = encode_image(image_path)

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
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
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
        response_format=DocumentAnalysis,  # Structured response
    )

    document_analysis = completion.choices[0].message.parsed
    return document_analysis


# Usage
pdf_path = "files/bank_statement_3.pdf"
result = send_pdf_to_gpt4(pdf_path)
print(result)
