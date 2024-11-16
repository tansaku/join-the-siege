import base64
from pydantic import BaseModel
from pdf2image import convert_from_path
import os
from openai import OpenAI
from PIL import Image


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


class DocumentAnalysis(BaseModel):
    document_type: str
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
    try:
        # Convert PDF to images
        image_path = convert_pdf_to_jpeg(pdf_path)
        if not image_path:
            raise ValueError("No images were generated from the PDF.")

        # encode the first image
        base64_image = encode_image(image_path)

        # Send the image to the model
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
        return response.choices[0]
    except Exception as e:
        return {"error": str(e)}


# Usage
pdf_path = "files/bank_statement_3.pdf"
result = send_pdf_to_gpt4(pdf_path)
print(result)
